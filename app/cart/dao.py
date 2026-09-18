from datetime import datetime
from sqlalchemy.orm import aliased, joinedload, selectinload

from app import db

from app.models import (
    Cart,
    CartItem,
    Dish,
    DishPairing,
    Order,
    OrderDetail,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    PaymentAttempt,
    Restaurant,
    RestaurantStatus,
    SystemConfig,
    UserDishInteraction,
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
    """Ưu tiên giới hạn của nhà hàng, nếu chưa có thì dùng mặc định."""
    restaurant = dish.restaurant if dish else None

    if restaurant and restaurant.max_quantity_per_item:
        return restaurant.max_quantity_per_item

    return _max_quantity_per_item()


def get_cart(user_id, restaurant_id):
    return (
        Cart.query
        .filter(
            Cart.user_id == user_id,
            Cart.restaurant_id == restaurant_id
        )
        .first()
    )


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


def get_pairing_suggestions(user_id, dish_id, limit=3):
    """Gợi ý món kèm cho món đang có trong giỏ."""
    cart = Cart.query.filter_by(user_id=user_id).first()
    if not cart:
        raise ValueError('Món ăn không thuộc giỏ hàng hiện tại')

    cart_dish_ids = [item.dish_id for item in cart.items]
    if dish_id not in cart_dish_ids:
        raise ValueError('Món ăn không thuộc giỏ hàng hiện tại')

    paired_dish = aliased(Dish)
    return (
        db.session.query(paired_dish)
        .join(
            DishPairing,
            DishPairing.paired_dish_id == paired_dish.id,
        )
        .filter(
            DishPairing.dish_id == dish_id,
            paired_dish.restaurant_id == cart.restaurant_id,
            paired_dish.active.is_(True),
            paired_dish.is_available.is_(True),
            paired_dish.id != dish_id,
            paired_dish.id.notin_(cart_dish_ids),
        )
        .order_by(
            DishPairing.confidence.desc(),
            DishPairing.lift.desc(),
            DishPairing.support.desc(),
        )
        .limit(min(max(limit, 0), 3))
        .all()
    )


def add_to_cart(user_id, dish_id, quantity=1):
    if not dish_id:
        raise ValueError('Món ăn không hợp lệ')

    if not quantity or quantity < 1:
        raise ValueError('Số lượng món không hợp lệ')

    dish = db.session.get(Dish, dish_id)

    if not dish or not dish.active or not dish.is_available:
        raise ValueError('Món ăn không khả dụng')

    if (
        not dish.restaurant
        or not dish.restaurant.active
        or dish.restaurant.status != RestaurantStatus.APPROVED
        or not dish.restaurant.is_open
    ):
        raise ValueError('Nhà hàng hiện không hoạt động')

    other_cart = (
        Cart.query
        .filter(Cart.user_id == user_id)
        .with_for_update()
        .first()
    )

    if other_cart and other_cart.restaurant_id != dish.restaurant_id:
        raise CartRestaurantConflict(other_cart.restaurant, dish_id, quantity)

    cart = get_cart(user_id, dish.restaurant_id)

    if not cart:
        cart = Cart(
            user_id=user_id,
            restaurant_id=dish.restaurant_id
        )

        db.session.add(cart)
        db.session.flush()

    item = (
        CartItem.query
        .filter_by(cart_id=cart.id, dish_id=dish.id)
        .first()
    )

    new_qty = quantity + (item.quantity if item else 0)

    max_qty = _max_quantity_for_dish(dish)

    if new_qty > max_qty:
        raise ValueError(
            f'Mỗi món chỉ được đặt tối đa '
            f'{max_qty} phần'
        )

    try:
        if item:
            item.quantity = new_qty

        else:
            db.session.add(
                CartItem(
                    cart_id=cart.id,
                    dish_id=dish.id,
                    quantity=quantity
                )
            )
        db.session.add(UserDishInteraction(
            user_id=user_id, dish_id=dish.id,
            interaction_type='ADD_TO_CART', hour_of_day=datetime.now().hour,
        ))

        db.session.commit()

    except Exception:
        db.session.rollback()
        raise ValueError('Không thể thêm món vào giỏ hàng')

    return cart


def update_cart_item(user_id, cart_item_id, quantity):
    if not quantity or quantity < 1:
        raise ValueError('Số lượng không hợp lệ')

    item = db.session.get(CartItem, cart_item_id)

    if not item or item.cart.user_id != user_id:
        raise ValueError('Sản phẩm không có trong giỏ')

    if not item.dish or not item.dish.active:
        raise ValueError('Món ăn không còn khả dụng')

    max_qty = _max_quantity_for_dish(item.dish)

    if quantity > max_qty:
        raise ValueError(
            f'Mỗi món chỉ được đặt tối đa '
            f'{max_qty} phần'
        )

    try:
        item.quantity = quantity
        db.session.commit()

    except Exception:
        db.session.rollback()
        raise ValueError('Không thể cập nhật giỏ hàng')

    return item


def remove_cart_item(user_id, cart_item_id):
    item = db.session.get(CartItem, cart_item_id)

    if not item or item.cart.user_id != user_id:
        raise ValueError('Sản phẩm không có trong giỏ')

    try:
        cart = item.cart
        db.session.delete(item)
        db.session.flush()
        if not cart.items:
            db.session.delete(cart)
        db.session.commit()

    except Exception:
        db.session.rollback()
        raise ValueError('Không thể xóa sản phẩm khỏi giỏ hàng')


def clear_cart(user_id, cart_id):
    cart = (
        Cart.query
        .filter_by(id=cart_id, user_id=user_id)
        .first()
    )

    if not cart:
        raise ValueError('Giỏ hàng không tồn tại')

    try:
        db.session.delete(cart)
        db.session.commit()

    except Exception:
        db.session.rollback()
        raise ValueError('Không thể xóa giỏ hàng')


def clear_all_carts(user_id):
    carts = get_user_carts(user_id)

    try:
        for cart in carts:
            db.session.delete(cart)

        db.session.commit()

    except Exception:
        db.session.rollback()
        raise ValueError('Không thể xóa giỏ hàng cũ')


def switch_restaurant_cart(user_id, dish_id, quantity=1):
    dish = db.session.get(Dish, dish_id)
    if (
        not dish or not dish.active or not dish.is_available
        or not dish.restaurant or not dish.restaurant.active
        or dish.restaurant.status != RestaurantStatus.APPROVED
        or not dish.restaurant.is_open
    ):
        raise ValueError('Món ăn hoặc nhà hàng không khả dụng')
    max_qty = _max_quantity_for_dish(dish)
    if not quantity or quantity < 1 or quantity > max_qty:
        raise ValueError(f'Mỗi món chỉ được đặt từ 1 đến {max_qty} phần')
    try:
        carts = (Cart.query.filter_by(user_id=user_id)
                 .with_for_update().all())
        for cart in carts:
            db.session.delete(cart)
        db.session.flush()
        cart = Cart(user_id=user_id, restaurant_id=dish.restaurant_id)
        db.session.add(cart)
        db.session.flush()
        db.session.add(CartItem(
            cart_id=cart.id, dish_id=dish.id, quantity=quantity
        ))
        db.session.commit()
        return cart
    except Exception:
        db.session.rollback()
        raise ValueError('Không thể chuyển sang nhà hàng mới')


def validate_checkout(user_id, lat=None, lng=None):
    carts = get_user_carts(user_id)

    issues = []

    default_min = SystemConfig.get(
        'DEFAULT_MIN_ORDER_AMOUNT',
        20000,
        cast=int
    )

    for cart in carts:
        restaurant = cart.restaurant

        if not restaurant:
            issues.append('Một nhà hàng trong giỏ hàng không còn tồn tại')
            continue

        if (
            not restaurant.active
            or restaurant.status != RestaurantStatus.APPROVED
        ):
            issues.append(
                f'Nhà hàng {restaurant.name} '
                f'hiện không hoạt động'
            )
            continue

        if not restaurant.is_open:
            issues.append(
                f"Nhà hàng {restaurant.name} hiện đang đóng cửa, "
                f"không nhận đơn"
            )
            continue

        min_amount = restaurant.min_order_amount or default_min

        if cart.total_amount() < min_amount:
            issues.append(
                f"Đơn hàng tại {restaurant.name} "
                f"chưa đạt giá trị tối thiểu "
                f"{min_amount:,.0f}"
                .replace(',', '.')
                + 'đ'
            )

        for item in cart.items:
            if not item.dish or not item.dish.active:
                issues.append('Có món ăn không còn khả dụng')
                continue

            if not item.dish.is_available:
                issues.append(
                    f"Món {item.dish.name} "
                    f"({restaurant.name}) đã hết hàng"
                )

            max_qty = _max_quantity_for_dish(item.dish)

            if item.quantity > max_qty:
                issues.append(
                    f"Món {item.dish.name} "
                    f"chỉ được đặt tối đa "
                    f"{max_qty} phần"
                )

        if restaurant.latitude is not None and restaurant.longitude is not None:
            if lat is None or lng is None:
                issues.append(
                    f'Vui lòng cấp quyền vị trí GPS để kiểm tra '
                    f'bán kính giao hàng của {restaurant.name}'
                )
                continue
            distance = restaurant.distance_km_to(lat, lng)

            if (
                distance is not None
                and not restaurant.is_within_delivery_radius(lat, lng)
            ):
                issues.append(
                    f"Địa chỉ giao hàng cách "
                    f"{restaurant.name} "
                    f"{distance:.1f}km, ngoài bán kính phục vụ "
                    f"({restaurant.delivery_radius_km:.0f}km)"
                )

    return issues


def build_checkout_payload(user_id, lat=None, lng=None):
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
            if not item.dish:
                raise ValueError('Một món trong giỏ không còn tồn tại')

            unit_price = item.dish.price
            subtotal = unit_price * item.quantity

            items.append({
                'cart_item_id': item.id,
                'dish_id': item.dish.id,
                'name': item.dish.name,
                'quantity': item.quantity,
                'unit_price': unit_price,
                'subtotal': subtotal,
            })

            cart_total += subtotal

        carts_data.append({
            'cart_id': cart.id,
            'restaurant_id': cart.restaurant_id,
            'restaurant_name': cart.restaurant.name,
            'items': items,
            'total': cart_total
        })

        total += cart_total

    if total <= 0:
        raise ValueError('Tổng tiền đơn hàng không hợp lệ')

    return {
        'carts': carts_data,
        'total': total
    }


def get_user_orders(user_id, page=None, per_page=20):
    query = (
        Order.query
        .options(
            joinedload(Order.restaurant),
            selectinload(Order.order_details).joinedload(OrderDetail.dish),
        )
        .filter(Order.user_id == user_id)
        .order_by(Order.created_date.desc(), Order.id.desc())
    )
    if page is not None:
        return query.paginate(page=page, per_page=per_page, error_out=False)
    return query.all()


def save_payment_attempt(user_id, pending):
    from app.cart.service import PaymentService

    return PaymentService.save_legacy_attempt(user_id, pending)


def get_payment_attempt(payment_request_id, user_id=None):
    query = PaymentAttempt.query.filter(
        PaymentAttempt.payment_request_id == str(payment_request_id)
    )
    if user_id is not None:
        query = query.filter(PaymentAttempt.user_id == user_id)
    return query.first()


def get_payment_attempt_by_order_code(order_code):
    return PaymentAttempt.query.filter(
        PaymentAttempt.order_code == str(order_code)
    ).first()


def finalize_payment_attempt(payment_request_id, user_id=None):
    from app.cart.service import PaymentService

    return PaymentService().finalize(
        payment_request_id, user_id=user_id, assume_paid=True
    )


def create_orders_from_pending(user_id, pending, payment_attempt=None):
    """Chỉ tạo đơn sau khi payOS xác nhận thanh toán thành công."""

    from datetime import datetime

    if not pending:
        raise ValueError('Thông tin thanh toán không tồn tại')

    if not pending.get('carts'):
        raise ValueError('Không có dữ liệu giỏ hàng để tạo đơn')

    orders = []

    try:
        for c in pending['carts']:
            restaurant = db.session.get(Restaurant, c['restaurant_id'])

            if not restaurant:
                raise ValueError('Nhà hàng không còn tồn tại')

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
                payment_attempt_id=(payment_attempt.id if payment_attempt else None),
            )

            db.session.add(order)

            db.session.flush()

            order.set_confirm_deadline()

            for item in c['items']:
                dish = db.session.get(Dish, item['dish_id'])

                if not dish:
                    raise ValueError(
                        f'Món ăn #{item["dish_id"]} '
                        f'không còn tồn tại'
                    )

                db.session.add(
                    OrderDetail(
                        order_id=order.id,
                        dish_id=item['dish_id'],
                        quantity=item['quantity'],
                        unit_price=item['unit_price']
                    )
                )
                db.session.add(UserDishInteraction(
                    user_id=user_id, dish_id=item['dish_id'],
                    interaction_type='ORDER', hour_of_day=datetime.now().hour,
                ))

            orders.append(order)

        for cart_data in pending['carts']:
            cart_id = cart_data.get('cart_id')
            if not cart_id:
                continue
            cart = (Cart.query.filter_by(id=cart_id, user_id=user_id)
                    .with_for_update().first())
            if not cart:
                continue
            expected = sorted(
                (int(item['cart_item_id']), int(item['dish_id']),
                 int(item['quantity']), int(item['unit_price']))
                for item in cart_data['items']
                if item.get('cart_item_id') is not None
            )
            actual = sorted(
                (item.id, item.dish_id, item.quantity,
                 item.dish.price if item.dish else -1)
                for item in cart.items
            )
            if expected and actual == expected:
                db.session.delete(cart)
        if payment_attempt:
            payment_attempt.status = 'FINALIZED'
            payment_attempt.snapshot_key = None
            payment_attempt.processed_at = datetime.now()
            payment_attempt.result_order_ids = ','.join(
                str(order.id) for order in orders
            )
        db.session.commit()

    except ValueError:
        db.session.rollback()
        raise
    except Exception:
        db.session.rollback()
        raise ValueError('Không thể tạo đơn hàng')

    return orders
