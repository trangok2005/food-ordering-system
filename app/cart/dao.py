from app import db
from app.models import (Cart, CartItem, Dish, Order, OrderDetail, OrderStatus,
                        PaymentMethod, PaymentStatus, Restaurant, SystemConfig)


def _max_quantity_per_item():
    return SystemConfig.get('MAX_QUANTITY_PER_ITEM', 20, cast=int)


def get_cart(user_id, restaurant_id):
    return (Cart.query
            .filter(Cart.user_id == user_id,
                    Cart.restaurant_id == restaurant_id)
            .first())


def get_user_carts(user_id):
    return Cart.query.filter(Cart.user_id == user_id).all()


def get_cart_stats(user_id):
    total_quantity, total_amount = 0, 0
    for cart in Cart.query.filter(Cart.user_id == user_id).all():
        total_amount += cart.total_amount()
        total_quantity += sum(item.quantity for item in cart.items)
    return {'total_quantity': total_quantity, 'total_amount': total_amount}


def add_to_cart(user_id, dish_id, quantity=1):
    dish = Dish.query.get(dish_id)
    if not dish or not dish.active or not dish.is_available:
        raise ValueError('Món ăn không khả dụng')

    cart = get_cart(user_id, dish.restaurant_id)
    if not cart:
        cart = Cart(user_id=user_id, restaurant_id=dish.restaurant_id)
        db.session.add(cart)
        db.session.flush()

    item = CartItem.query.filter_by(cart_id=cart.id, dish_id=dish.id).first()
    new_qty = quantity + (item.quantity if item else 0)
    max_qty = _max_quantity_per_item()
    if new_qty > max_qty:
        raise ValueError(f'Mỗi món chỉ được đặt tối đa {max_qty} phần')

    if item:
        item.quantity = new_qty
    else:
        db.session.add(CartItem(cart_id=cart.id, dish_id=dish.id, quantity=quantity))
    db.session.commit()
    return cart


def update_cart_item(user_id, cart_item_id, quantity):
    if not quantity or quantity < 1:
        raise ValueError('Số lượng không hợp lệ')
    max_qty = _max_quantity_per_item()
    if quantity > max_qty:
        raise ValueError(f'Mỗi món chỉ được đặt tối đa {max_qty} phần')

    item = CartItem.query.get(cart_item_id)
    if not item or item.cart.user_id != user_id:
        raise ValueError('Sản phẩm không có trong giỏ')
    item.quantity = quantity
    db.session.commit()
    return item


def remove_cart_item(user_id, cart_item_id):
    item = CartItem.query.get(cart_item_id)
    if not item or item.cart.user_id != user_id:
        raise ValueError('Sản phẩm không có trong giỏ')
    db.session.delete(item)
    db.session.commit()


def clear_cart(user_id, cart_id):
    cart = Cart.query.filter_by(id=cart_id, user_id=user_id).first()
    if not cart:
        raise ValueError('Giỏ hàng không tồn tại')
    cart.items.clear()
    db.session.commit()


def validate_checkout(user_id, lat=None, lng=None):
    """Kiểm tra ràng buộc nghiệp vụ trước thanh toán, đúng UC-04:
    - B2: nhà hàng đang mở cửa, giá trị đơn tối thiểu, món còn hàng.
    - B4: địa chỉ giao hàng trong bán kính phục vụ (chỉ kiểm tra nếu đã
      có lat/lng - lúc hiển thị trang checkout ban đầu có thể chưa có
      tọa độ vì trình duyệt chưa xin quyền GPS)."""
    carts = get_user_carts(user_id)
    issues = []
    default_min = SystemConfig.get('DEFAULT_MIN_ORDER_AMOUNT', 20000, cast=int)

    for cart in carts:
        restaurant = cart.restaurant

        if not restaurant.is_open:
            issues.append(f"Nhà hàng {restaurant.name} hiện đang đóng cửa, không nhận đơn")
            continue  # các kiểm tra khác của nhà hàng này không còn ý nghĩa

        min_amount = restaurant.min_order_amount or default_min
        if cart.total_amount() < min_amount:
            issues.append(
                f"Đơn hàng tại {restaurant.name} chưa đạt giá trị tối thiểu "
                f"{min_amount:,.0f}".replace(',', '.') + 'đ'
            )

        for item in cart.items:
            if not item.dish.is_available:
                issues.append(f"Món {item.dish.name} ({restaurant.name}) đã hết hàng")

        if lat is not None and lng is not None:
            if not restaurant.is_within_delivery_radius(lat, lng):
                issues.append(
                    f"Địa chỉ giao hàng nằm ngoài bán kính phục vụ "
                    f"({restaurant.delivery_radius_km:.0f}km) của {restaurant.name}"
                )

    return issues


def build_checkout_payload(user_id, lat=None, lng=None):
    """Chuẩn bị dữ liệu thanh toán từ giỏ hàng hiện tại. Ném ValueError nếu
    vi phạm ràng buộc nghiệp vụ. unit_price snapshot giá tại thời điểm đặt."""
    carts = get_user_carts(user_id)
    if not carts:
        raise ValueError('Giỏ hàng trống')

    issues = validate_checkout(user_id, lat=lat, lng=lng)
    if issues:
        raise ValueError(' '.join(issues))

    carts_data = []
    total = 0
    for cart in carts:
        items = []
        cart_total = 0
        for item in cart.items:
            unit_price = item.dish.price
            subtotal = unit_price * item.quantity
            items.append({
                'dish_id': item.dish.id,
                'name': item.dish.name,
                'quantity': item.quantity,
                'unit_price': unit_price,
                'subtotal': subtotal,
            })
            cart_total += subtotal
        carts_data.append({'restaurant_id': cart.restaurant_id,
                           'restaurant_name': cart.restaurant.name,
                           'items': items, 'total': cart_total})
        total += cart_total

    return {'carts': carts_data, 'total': total}


def get_user_orders(user_id):
    return (Order.query
            .filter(Order.user_id == user_id)
            .order_by(Order.created_date.desc(), Order.id.desc())
            .all())


def create_orders_from_pending(user_id, pending):
    """Chỉ được gọi SAU KHI payOS xác nhận thanh toán thành công (PAID).
    Tạo 1 Order cho mỗi nhà hàng trong giỏ, rồi xóa giỏ hàng."""
    from datetime import datetime

    orders = []
    for c in pending['carts']:
        restaurant = Restaurant.query.get(c['restaurant_id'])
        order = Order(
            user_id=user_id,
            restaurant_id=restaurant.id,
            delivery_address=pending.get('address', ''),
            delivery_latitude=pending.get('lat'),
            delivery_longitude=pending.get('lng'),
            phone=pending.get('phone', ''),
            note=pending.get('note'),
            total_amount=c['total'],
            status=OrderStatus.PENDING,
            payment_method=PaymentMethod.ONLINE,
            payment_status=PaymentStatus.PAID,
            paid_at=datetime.now(),
        )
        db.session.add(order)
        db.session.flush()
        order.set_confirm_deadline()
        for item in c['items']:
            db.session.add(OrderDetail(order_id=order.id,
                                       dish_id=item['dish_id'],
                                       quantity=item['quantity'],
                                       unit_price=item['unit_price']))
        orders.append(order)

    db.session.commit()

    for cart in Cart.query.filter(Cart.user_id == user_id).all():
        db.session.delete(cart)
    db.session.commit()
    return orders