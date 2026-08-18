from app import db

from app.models import (
    Cart,
    CartItem,
    Dish,
    Order,
    OrderDetail,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    Restaurant,
    SystemConfig
)

class CartRestaurantConflict(ValueError):
    """Giỏ hàng đang chứa món của nhà hàng khác."""

    def __init__(self, current_restaurant, dish_id, quantity):
        self.current_restaurant = current_restaurant
        self.dish_id = dish_id
        self.quantity = quantity
        super().__init__(
            f'Giỏ hàng đang chứa món của '
            f'{current_restaurant.name}, muốn thêm món nhà hàng khác '
            f'phải xóa giỏ cũ trước'
        )


def _max_quantity_per_item():
    return SystemConfig.get('MAX_QUANTITY_PER_ITEM', 20, cast=int)

def _max_quantity_for_dish(dish):
    """Số lượng tối đa 1 món/đơn: ưu tiên ghi đè riêng của nhà hàng,
    không có thì dùng mặc định hệ thống."""
    restaurant = dish.restaurant if dish else None
    if restaurant and restaurant.max_quantity_per_item:
        return restaurant.max_quantity_per_item
    return _max_quantity_per_item()


def get_cart(user_id, restaurant_id):
    return (Cart.query
            .filter(Cart.user_id == user_id,
                    Cart.restaurant_id == restaurant_id)
            .first())

def get_user_carts(user_id):
    return Cart.query.filter(Cart.user_id == user_id).all()



def get_cart_stats(user_id):
    total_quantity = 0
    total_amount = 0

    for cart in Cart.query.filter(Cart.user_id == user_id).all():
        total_amount += cart.total_amount()
        total_quantity += sum(item.quantity for item in cart.items)

    return {
        'total_quantity': total_quantity,
        'total_amount': total_amount
    }


def add_to_cart(user_id, dish_id, quantity=1):
    dish = Dish.query.get(dish_id)

    if not dish or not dish.active or not dish.is_available:
        raise ValueError('Món ăn không khả dụng')

    other_cart = (Cart.query
                  .filter(Cart.user_id == user_id,
                          Cart.restaurant_id != dish.restaurant_id)
                  .first())

    if other_cart:
        raise CartRestaurantConflict(other_cart.restaurant, dish_id, quantity)

    cart = get_cart(user_id, dish.restaurant_id)

    if not cart:
        cart = Cart(user_id=user_id, restaurant_id=dish.restaurant_id)
        db.session.add(cart)
        db.session.flush()

    item = CartItem.query.filter_by(cart_id=cart.id, dish_id=dish.id).first()
    new_qty = quantity + (item.quantity if item else 0)
    max_qty = _max_quantity_for_dish(dish)

    if new_qty > max_qty:
        raise ValueError(f'Mỗi món chỉ được đặt tối đa {max_qty} phần')

    if item:
        item.quantity = new_qty
    else:
        db.session.add(CartItem(cart_id=cart.id,
                                dish_id=dish.id,
                                quantity=quantity))

    db.session.commit()
    return cart


def update_cart_item(user_id, cart_item_id, quantity):
    if not quantity or quantity < 1:
        raise ValueError('Số lượng không hợp lệ')

    item = CartItem.query.get(cart_item_id)

    if not item or item.cart.user_id != user_id:
        raise ValueError('Sản phẩm không có trong giỏ')

    max_qty = _max_quantity_for_dish(item.dish)
    if quantity > max_qty:
        raise ValueError(f'Mỗi món chỉ được đặt tối đa {max_qty} phần')

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
    cart = (Cart.query
            .filter_by(id=cart_id, user_id=user_id)
            .first())

    if not cart:
        raise ValueError('Giỏ hàng không tồn tại')

    cart.items.clear()
    db.session.commit()


def clear_all_carts(user_id):
    carts = get_user_carts(user_id)
    for cart in carts:
        db.session.delete(cart)
    db.session.commit()


def validate_checkout(user_id, lat=None, lng=None):
    """Kiểm tra các ràng buộc nghiệp vụ trước khi thanh toán:
    - Nhà hàng phải đang mở cửa.
    - Đơn hàng phải đạt giá trị tối thiểu.
    - Món ăn phải còn hàng.
    - Nếu có GPS thì kiểm tra khoảng cách giao hàng."""

    carts = get_user_carts(user_id)
    issues = []
    default_min = SystemConfig.get('DEFAULT_MIN_ORDER_AMOUNT', 20000, cast=int)

    for cart in carts:
        restaurant = cart.restaurant

        if not restaurant.is_open:
            issues.append(f"Nhà hàng {restaurant.name} hiện đang đóng cửa, "
                          f"không nhận đơn")
            continue

        min_amount = restaurant.min_order_amount or default_min

        if cart.total_amount() < min_amount:
            issues.append(f"Đơn hàng tại {restaurant.name} "
                          f"chưa đạt giá trị tối thiểu "
                          f"{min_amount:,.0f}"
                          .replace(',', '.')
                          + 'đ')

        for item in cart.items:
            if not item.dish.is_available:
                issues.append(f"Món {item.dish.name} "
                              f"({restaurant.name}) đã hết hàng")

        if lat is not None and lng is not None:
            distance = restaurant.distance_km_to(lat, lng)
            if not restaurant.is_within_delivery_radius(lat, lng):
                issues.append(f"Địa chỉ giao hàng cách {restaurant.name} "
                              f"{distance:.1f}km, ngoài bán kính phục vụ "
                              f"({restaurant.delivery_radius_km:.0f}km)")

    return issues


def build_checkout_payload(user_id, lat=None, lng=None):
    """Chuẩn bị dữ liệu thanh toán từ giỏ hàng.
    Nếu có lỗi ràng buộc nghiệp vụ thì ValueError được trả về.
    unit_price được lưu lại tại thời điểm đặt hàng
    để tránh việc giá món thay đổi sau này."""

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

        carts_data.append({
            'restaurant_id': cart.restaurant_id,
            'restaurant_name': cart.restaurant.name,
            'items': items,
            'total': cart_total
        })
        total += cart_total

    return {
        'carts': carts_data,
        'total': total
    }


def get_user_orders(user_id):
    return (Order.query
            .filter(Order.user_id == user_id)
            .order_by(Order.created_date.desc(), Order.id.desc())
            .all())



def create_orders_from_pending(user_id, pending):
    """Chỉ gọi hàm này sau khi payOS xác nhận thanh toán thành công.
    Mỗi nhà hàng trong giỏ sẽ tạo thành một Order riêng.
    Sau khi tạo Order thì xóa các giỏ hàng."""

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
            db.session.add(OrderDetail(
                order_id=order.id,
                dish_id=item['dish_id'],
                quantity=item['quantity'],
                unit_price=item['unit_price']
            ))

        orders.append(order)

    db.session.commit()

    for cart in Cart.query.filter(Cart.user_id == user_id).all():
        db.session.delete(cart)

    db.session.commit()
    return orders