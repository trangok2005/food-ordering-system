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

<<<<<<< Updated upstream
def _max_quantity_per_item():
    return SystemConfig.get(
=======

class CartRestaurantConflict(ValueError):
    """Giỏ hàng đang chứa món của nhà hàng khác."""

    def __init__(
        self,
        current_restaurant,
        dish_id,
        quantity
    ):
        self.current_restaurant = current_restaurant
        self.dish_id = dish_id
        self.quantity = quantity

        super().__init__(
            f'Giỏ hàng đang chứa món của '
            f'{current_restaurant.name}, muốn thêm món nhà hàng khác '
            f'phải xóa giỏ cũ trước'
        )


def _max_quantity_per_item():
    value = SystemConfig.get(
>>>>>>> Stashed changes
        'MAX_QUANTITY_PER_ITEM',
        20,
        cast=int
    )
<<<<<<< Updated upstream

def get_cart(user_id, restaurant_id):
=======

    if value < 1:
        value = 1

    return value


def _max_quantity_for_dish(dish):
    """
    Số lượng tối đa 1 món/đơn:
    ưu tiên ghi đè riêng của nhà hàng,
    không có thì dùng mặc định hệ thống.
    """

    restaurant = (
        dish.restaurant
        if dish
        else None
    )

    if (
        restaurant
        and restaurant.max_quantity_per_item
    ):
        return restaurant.max_quantity_per_item

    return _max_quantity_per_item()


def get_cart(
    user_id,
    restaurant_id
):
>>>>>>> Stashed changes
    return (
        Cart.query
        .filter(
            Cart.user_id == user_id,
            Cart.restaurant_id == restaurant_id
        )
        .first()
    )
<<<<<<< Updated upstream

def get_user_carts(user_id):
    return Cart.query.filter(
        Cart.user_id == user_id
    ).all()

=======


def get_user_carts(user_id):
    return (
        Cart.query
        .filter(
            Cart.user_id == user_id
        )
        .all()
    )
>>>>>>> Stashed changes


def get_cart_stats(user_id):
    total_quantity = 0
    total_amount = 0

<<<<<<< Updated upstream
    for cart in Cart.query.filter(
        Cart.user_id == user_id
    ).all():
        total_amount += cart.total_amount()
=======
    carts = (
        Cart.query
        .filter(
            Cart.user_id == user_id
        )
        .all()
    )

    for cart in carts:
        total_amount += cart.total_amount()

>>>>>>> Stashed changes
        total_quantity += sum(
            item.quantity
            for item in cart.items
        )

    return {
        'total_quantity': total_quantity,
        'total_amount': total_amount
    }


def add_to_cart(
    user_id,
    dish_id,
    quantity=1
):
    if not dish_id:
        raise ValueError(
            'Món ăn không hợp lệ'
        )

    if not quantity or quantity < 1:
        raise ValueError(
            'Số lượng không hợp lệ'
        )

<<<<<<< Updated upstream
=======
    dish = Dish.query.get(
        dish_id
    )

    if (
        not dish
        or not dish.active
        or not dish.is_available
    ):
        raise ValueError(
            'Món ăn không khả dụng'
        )

    # Nhà hàng của món phải đang active
    if (
        not dish.restaurant
        or not dish.restaurant.active
    ):
        raise ValueError(
            'Nhà hàng không khả dụng'
        )

    other_cart = (
        Cart.query
        .filter(
            Cart.user_id == user_id,
            Cart.restaurant_id != dish.restaurant_id
        )
        .first()
    )

    if other_cart:
        raise CartRestaurantConflict(
            other_cart.restaurant,
            dish_id,
            quantity
        )

>>>>>>> Stashed changes
    cart = get_cart(
        user_id,
        dish.restaurant_id
    )

    if not cart:
        cart = Cart(
            user_id=user_id,
            restaurant_id=dish.restaurant_id
        )

        db.session.add(cart)
        db.session.flush()

    item = (
        CartItem.query
        .filter_by(
            cart_id=cart.id,
            dish_id=dish.id
        )
        .first()
    )

<<<<<<< Updated upstream
    new_qty = quantity + (
        item.quantity if item else 0
    )

    max_qty = _max_quantity_per_item()

    if new_qty > max_qty:
        raise ValueError(
            f'Mỗi món chỉ được đặt tối đa {max_qty} phần'
        )

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

    db.session.commit()

=======
    new_qty = (
        quantity
        + (item.quantity if item else 0)
    )

    max_qty = _max_quantity_for_dish(
        dish
    )

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

        db.session.commit()

    except Exception:
        db.session.rollback()
        raise

>>>>>>> Stashed changes
    return cart


def update_cart_item(
    user_id,
    cart_item_id,
    quantity
):
    if not quantity or quantity < 1:
        raise ValueError(
            'Số lượng không hợp lệ'
        )

<<<<<<< Updated upstream
    max_qty = _max_quantity_per_item()

    if quantity > max_qty:
        raise ValueError(
            f'Mỗi món chỉ được đặt tối đa {max_qty} phần'
        )

    item = CartItem.query.get(cart_item_id)
=======
    if not cart_item_id:
        raise ValueError(
            'Sản phẩm không hợp lệ'
        )
>>>>>>> Stashed changes

    item = CartItem.query.get(
        cart_item_id
    )

    if (
        not item
        or item.cart.user_id != user_id
    ):
        raise ValueError(
            'Sản phẩm không có trong giỏ'
        )

    max_qty = _max_quantity_for_dish(
        item.dish
    )

<<<<<<< Updated upstream
    item.quantity = quantity

    db.session.commit()
=======
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
        raise
>>>>>>> Stashed changes

    return item


def remove_cart_item(
    user_id,
    cart_item_id
):
    if not cart_item_id:
        raise ValueError(
            'Sản phẩm không hợp lệ'
        )

    item = CartItem.query.get(
        cart_item_id
    )

    if (
        not item
        or item.cart.user_id != user_id
    ):
        raise ValueError(
            'Sản phẩm không có trong giỏ'
        )

    try:
        db.session.delete(item)
        db.session.commit()

    except Exception:
        db.session.rollback()
        raise


<<<<<<< Updated upstream
def clear_cart(user_id, cart_id):
=======
def clear_cart(
    user_id,
    cart_id
):
    if not cart_id:
        raise ValueError(
            'Giỏ hàng không hợp lệ'
        )

>>>>>>> Stashed changes
    cart = (
        Cart.query
        .filter_by(
            id=cart_id,
            user_id=user_id
        )
        .first()
    )

    if not cart:
        raise ValueError(
            'Giỏ hàng không tồn tại'
        )

    try:
        cart.items.clear()
        db.session.commit()

    except Exception:
        db.session.rollback()
        raise


<<<<<<< Updated upstream
def validate_checkout(user_id, lat=None, lng=None):
    """
    Kiểm tra các ràng buộc nghiệp vụ trước khi thanh toán.

=======
def clear_all_carts(user_id):
    carts = get_user_carts(
        user_id
    )

    try:
        for cart in carts:
            db.session.delete(cart)

        db.session.commit()

    except Exception:
        db.session.rollback()
        raise


def validate_checkout(
    user_id,
    lat=None,
    lng=None
):
    """
    Kiểm tra các ràng buộc nghiệp vụ trước khi thanh toán:
>>>>>>> Stashed changes
    - Nhà hàng phải đang mở cửa.
    - Đơn hàng phải đạt giá trị tối thiểu.
    - Món ăn phải còn hàng.
    - Nếu có GPS thì kiểm tra khoảng cách giao hàng.
    """
<<<<<<< Updated upstream

    carts = get_user_carts(user_id)

=======

    carts = get_user_carts(
        user_id
    )

>>>>>>> Stashed changes
    issues = []

    default_min = SystemConfig.get(
        'DEFAULT_MIN_ORDER_AMOUNT',
        20000,
        cast=int
    )

    for cart in carts:
        restaurant = cart.restaurant

<<<<<<< Updated upstream
        if not restaurant.is_open:
            issues.append(
                f"Nhà hàng {restaurant.name} hiện đang đóng cửa, "
                f"không nhận đơn"
            )

            continue

=======
        if not restaurant:
            issues.append(
                'Nhà hàng trong giỏ hàng không tồn tại'
            )
            continue

        if not restaurant.active:
            issues.append(
                f'Nhà hàng {restaurant.name} '
                f'hiện không hoạt động'
            )
            continue

        if not restaurant.is_open:
            issues.append(
                f'Nhà hàng {restaurant.name} hiện đang đóng cửa, '
                f'không nhận đơn'
            )
            continue

>>>>>>> Stashed changes
        min_amount = (
            restaurant.min_order_amount
            or default_min
        )

        if cart.total_amount() < min_amount:
            issues.append(
<<<<<<< Updated upstream
                f"Đơn hàng tại {restaurant.name} "
                f"chưa đạt giá trị tối thiểu "
                f"{min_amount:,.0f}"
=======
                f'Đơn hàng tại {restaurant.name} '
                f'chưa đạt giá trị tối thiểu '
                f'{min_amount:,.0f}'
>>>>>>> Stashed changes
                .replace(',', '.')
                + 'đ'
            )

        for item in cart.items:
<<<<<<< Updated upstream
            if not item.dish.is_available:
                issues.append(
                    f"Món {item.dish.name} "
                    f"({restaurant.name}) đã hết hàng"
                )

        if lat is not None and lng is not None:
=======

            if not item.dish:
                issues.append(
                    'Có món ăn không còn tồn tại'
                )
                continue

            if not item.dish.active:
                issues.append(
                    f'Món {item.dish.name} '
                    f'({restaurant.name}) không còn hoạt động'
                )

            elif not item.dish.is_available:
                issues.append(
                    f'Món {item.dish.name} '
                    f'({restaurant.name}) đã hết hàng'
                )

        if (
            lat is not None
            and lng is not None
        ):
            distance = restaurant.distance_km_to(
                lat,
                lng
            )

>>>>>>> Stashed changes
            if not restaurant.is_within_delivery_radius(
                lat,
                lng
            ):
                issues.append(
<<<<<<< Updated upstream
                    f"Địa chỉ giao hàng nằm ngoài "
                    f"bán kính phục vụ "
                    f"({restaurant.delivery_radius_km:.0f}km) "
                    f"của {restaurant.name}"
=======
                    f'Địa chỉ giao hàng cách '
                    f'{restaurant.name} '
                    f'{distance:.1f}km, ngoài bán kính phục vụ '
                    f'({restaurant.delivery_radius_km:.0f}km)'
>>>>>>> Stashed changes
                )

    return issues


<<<<<<< Updated upstream
def build_checkout_payload(user_id, lat=None, lng=None):
    """
    Chuẩn bị dữ liệu thanh toán từ giỏ hàng.

=======
def build_checkout_payload(
    user_id,
    lat=None,
    lng=None
):
    """
    Chuẩn bị dữ liệu thanh toán từ giỏ hàng.
>>>>>>> Stashed changes
    Nếu có lỗi ràng buộc nghiệp vụ thì ValueError được trả về.

    unit_price được lưu lại tại thời điểm đặt hàng
    để tránh việc giá món thay đổi sau này.
    """

    carts = get_user_carts(
        user_id
    )

    if not carts:
        raise ValueError(
            'Giỏ hàng trống'
        )

    issues = validate_checkout(
        user_id,
        lat=lat,
        lng=lng
    )

<<<<<<< Updated upstream
    issues = validate_checkout(
        user_id,
        lat=lat,
        lng=lng
    )

=======
>>>>>>> Stashed changes
    if issues:
        raise ValueError(
            ' '.join(issues)
        )

    carts_data = []
    total = 0

    for cart in carts:
        if not cart.restaurant:
            raise ValueError(
                'Nhà hàng trong giỏ hàng không tồn tại'
            )

        items = []
        cart_total = 0

        for item in cart.items:

            if not item.dish:
                raise ValueError(
                    'Có món ăn không còn tồn tại'
                )

            unit_price = item.dish.price
<<<<<<< Updated upstream
            subtotal = unit_price * item.quantity
=======

            if unit_price < 0:
                raise ValueError(
                    f'Giá món {item.dish.name} không hợp lệ'
                )

            subtotal = (
                unit_price
                * item.quantity
            )
>>>>>>> Stashed changes

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

    if total <= 0:
        raise ValueError(
            'Tổng giá trị đơn hàng không hợp lệ'
        )

    return {
        'carts': carts_data,
        'total': total
    }


def get_user_orders(user_id):
    return (
        Order.query
<<<<<<< Updated upstream
        .filter(Order.user_id == user_id)
=======
        .filter(
            Order.user_id == user_id
        )
>>>>>>> Stashed changes
        .order_by(
            Order.created_date.desc(),
            Order.id.desc()
        )
        .all()
    )


def create_orders_from_pending(
    user_id,
    pending
):
    """
    Chỉ gọi hàm này sau khi PayOS xác nhận
    thanh toán thành công.

<<<<<<< Updated upstream
def create_orders_from_pending(user_id, pending):
    """
    Chỉ gọi hàm này sau khi payOS xác nhận thanh toán thành công.

    Mỗi nhà hàng trong giỏ sẽ tạo thành một Order riêng.
=======
    Mỗi nhà hàng trong giỏ sẽ tạo thành
    một Order riêng.

>>>>>>> Stashed changes
    Sau khi tạo Order thì xóa các giỏ hàng.
    """

    from datetime import datetime

<<<<<<< Updated upstream
    orders = []

    for c in pending['carts']:
        restaurant = Restaurant.query.get(
            c['restaurant_id']
        )

        order = Order(
            user_id=user_id,
            restaurant_id=restaurant.id,
            delivery_address=pending.get(
                'address',
                ''
            ),
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
            db.session.add(
                OrderDetail(
                    order_id=order.id,
                    dish_id=item['dish_id'],
                    quantity=item['quantity'],
                    unit_price=item['unit_price']
                )
            )
=======
    if not pending:
        raise ValueError(
            'Thông tin thanh toán không tồn tại'
        )

    if not pending.get('carts'):
        raise ValueError(
            'Không có dữ liệu giỏ hàng để tạo đơn'
        )

    orders = []
>>>>>>> Stashed changes

    try:
        for c in pending['carts']:

            restaurant = Restaurant.query.get(
                c['restaurant_id']
            )

<<<<<<< Updated upstream
    for cart in Cart.query.filter(
        Cart.user_id == user_id
    ).all():
        db.session.delete(cart)

    db.session.commit()

=======
            if not restaurant:
                raise ValueError(
                    'Nhà hàng không tồn tại'
                )

            if not restaurant.active:
                raise ValueError(
                    f'Nhà hàng {restaurant.name} '
                    f'không còn hoạt động'
                )

            if not c.get('items'):
                raise ValueError(
                    f'Giỏ hàng của {restaurant.name} đang trống'
                )

            order = Order(
                user_id=user_id,
                restaurant_id=restaurant.id,
                delivery_address=pending.get(
                    'address',
                    ''
                ),
                delivery_latitude=pending.get(
                    'lat'
                ),
                delivery_longitude=pending.get(
                    'lng'
                ),
                phone=pending.get(
                    'phone',
                    ''
                ),
                note=pending.get(
                    'note'
                ),
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

                if item['quantity'] < 1:
                    raise ValueError(
                        'Số lượng món không hợp lệ'
                    )

                if item['unit_price'] < 0:
                    raise ValueError(
                        'Giá món không hợp lệ'
                    )

                dish = Dish.query.get(
                    item['dish_id']
                )

                if not dish:
                    raise ValueError(
                        'Món ăn không tồn tại'
                    )

                db.session.add(
                    OrderDetail(
                        order_id=order.id,
                        dish_id=item['dish_id'],
                        quantity=item['quantity'],
                        unit_price=item['unit_price']
                    )
                )

            orders.append(order)

        db.session.commit()

    except Exception:
        db.session.rollback()
        raise

    try:
        for cart in Cart.query.filter(
            Cart.user_id == user_id
        ).all():
            db.session.delete(cart)

        db.session.commit()

    except Exception:
        db.session.rollback()
        raise

>>>>>>> Stashed changes
    return orders