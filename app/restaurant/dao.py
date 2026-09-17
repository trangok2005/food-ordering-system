from datetime import datetime

from sqlalchemy import func

from app import db
from app.models import (
    Category,
    Dish,
    Order,
    OrderDetail,
    OrderStatus,
    PaymentStatus,
    Restaurant,
    RestaurantStatus,
    SystemConfig,
    User,
    UserRole,

)
SystemConfigModel = SystemConfig
def get_dashboard_stats():
    restaurant_count = Restaurant.query.count()

    restaurant_by_status = dict(
        db.session.query(Restaurant.status, func.count(Restaurant.id))
        .group_by(Restaurant.status)
        .all()
    )

    user_count = (
        User.query
        .filter(User.role.in_([UserRole.CUSTOMER, UserRole.USER]))
        .count()
    )
    owner_count = (
        User.query
        .filter(User.role == UserRole.RESTAURANT)
        .count()
    )

    order_count = Order.query.count()

    paid_count = (
        Order.query
        .filter(Order.payment_status == PaymentStatus.PAID)
        .count()
    )
    revenue = (
        db.session
        .query(func.coalesce(func.sum(Order.total_amount), 0))
        .filter(Order.status.in_([
            OrderStatus.COMPLETED, OrderStatus.DELIVERING
        ]))
        .scalar()
    )
    avg_order = round(revenue / paid_count) if paid_count else 0

    return {
        'restaurant_count': restaurant_count,
        'restaurant_by_status': restaurant_by_status,
        'user_count': user_count,
        'owner_count': owner_count,
        'order_count': order_count,
        'paid_count': paid_count,
        'revenue': revenue,
        'avg_order': avg_order,
    }

NEXT_STATUS = {
    OrderStatus.CONFIRMED: OrderStatus.PREPARING,
    OrderStatus.PREPARING: OrderStatus.DELIVERING,
    OrderStatus.DELIVERING: OrderStatus.COMPLETED,
}

def get_restaurant_for_owner(user_id):
    return Restaurant.query.filter(Restaurant.owner_id == user_id).first()

def register_restaurant(owner, data):
    restaurant = get_restaurant_for_owner(owner.id)

    if restaurant:
        raise ValueError('Tài khoản này đã đăng ký nhà hàng rồi')

    name = data.get('name', '').strip()
    address = data.get('address', '').strip()
    phone = data.get('phone', '').strip()
    description = data.get('description', '').strip()

    if name == '':
        raise ValueError('Vui lòng nhập tên nhà hàng.')

    if address == '':
        raise ValueError('Vui lòng nhập địa chỉ nhà hàng.')

    if phone != '':
        if not phone.isdigit():
            raise ValueError('Số điện thoại chỉ được nhập số')

        if len(phone) < 10 or len(phone) > 11:
            raise ValueError('Số điện thoại phải từ 10 đến 11 số')

    latitude = _parse_coordinate(
        data.get('latitude'), -90, 90, 'Vĩ độ'
    )

    longitude = _parse_coordinate(
        data.get('longitude'), -180, 180, 'Kinh độ'
    )

    if latitude is None or longitude is None:
        raise ValueError('Vui lòng cung cấp đầy đủ tọa độ GPS của nhà hàng')

    restaurant = Restaurant(
        name=name,
        address=address,
        phone=phone if phone != '' else None,
        description=description if description != '' else None,
        latitude=latitude,
        longitude=longitude,
        status=RestaurantStatus.PENDING,
        confirm_timeout_minutes=SystemConfig.get(
            'DEFAULT_CONFIRM_TIMEOUT_MINUTES',
            5,
            cast=int
        ),
        delivery_radius_km=10 ,
        owner_id=owner.id
    )

    db.session.add(restaurant)
    db.session.flush()

    return restaurant
def commit():
    db.session.commit()


def _parse_float(raw):
    raw = (raw or '').strip()

    if raw == '':
        return None

    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _parse_coordinate(raw, minimum, maximum, label):
    value = _parse_float(raw)

    if value is None:
        return None

    if value < minimum or value > maximum:
        raise ValueError(
            f'{label} phải nằm trong khoảng {minimum} đến {maximum}'
        )

    return value


def get_categories(restaurant_id):
    return (
        Category.query
        .filter(Category.restaurant_id == restaurant_id)
        .order_by(Category.name)
        .all()
    )

def add_category(restaurant, name):
    name = (name or '').strip()

    if name == '':
        raise ValueError('Vui lòng nhập tên danh mục')

    if len(name) > 100:
        raise ValueError('Tên danh mục tối đa 100 ký tự')

    exists = Category.query.filter(
        Category.restaurant_id == restaurant.id,
        func.lower(Category.name) == func.lower(name)
    ).first()

    if exists:
        raise ValueError(f'Danh mục "{name}" đã tồn tại')

    category = Category(
        name=name,
        restaurant_id=restaurant.id
    )

    db.session.add(category)
    db.session.commit()

    return category


def rename_category(restaurant, category_id, name):
    category = _get_category(category_id, restaurant.id)

    if not category:
        raise ValueError('Danh mục không tồn tại')

    name = (name or '').strip()

    if name == '':
        raise ValueError('Vui lòng nhập tên danh mục')

    if len(name) > 100:
        raise ValueError('Tên danh mục tối đa 100 ký tự')

    exists = Category.query.filter(
        Category.restaurant_id == restaurant.id,
        Category.id != category_id,
        func.lower(Category.name) == func.lower(name)
    ).first()

    if exists:
        raise ValueError(f'Danh mục "{name}" đã tồn tại')

    category.name = name

    db.session.commit()

    return category


def delete_category(restaurant, category_id):
    category = _get_category(category_id, restaurant.id)

    if not category:
        raise ValueError('Danh mục không tồn tại')

    if category.dishes:
        raise ValueError('Chỉ xóa được danh mục đang trống món')

    db.session.delete(category)
    db.session.commit()


def _get_category(category_id, restaurant_id):
    category = Category.query.filter(
        Category.id == category_id,
        Category.restaurant_id == restaurant_id
    ).first()

    return category


def _validate_dish_input(name, price, category_id, restaurant):
    name = (name or '').strip()

    if name == '':
        raise ValueError('Vui lòng nhập tên món ăn')

    try:
        price = int(price)
    except (TypeError, ValueError):
        raise ValueError('Giá bán phải là số nguyên (VNĐ)')

    if price <= 0:
        raise ValueError('Giá bán phải lớn hơn 0')

    if price > 100_000_000:
        raise ValueError('Giá bán quá lớn, vui lòng kiểm tra lại')

    category = _get_category(category_id, restaurant.id)

    if not category:
        raise ValueError('Danh mục không hợp lệ')

    return name, price, category


def add_dish(restaurant, form):
    name, price, category = _validate_dish_input(
        form.get('name'),
        form.get('price'),
        form.get('category_id'),
        restaurant
    )

    dish = Dish(
        name=name,
        description=(form.get('description') or '').strip() or None,
        price=price,
        image=(form.get('image') or '').strip() or None,
        is_available=True,
        restaurant_id=restaurant.id,
        category_id=category.id
    )

    db.session.add(dish)
    db.session.commit()

    return dish


def update_dish(restaurant, dish_id, form):
    dish = get_dish_for_restaurant(dish_id, restaurant.id)

    if not dish:
        raise ValueError('Món ăn không tồn tại')

    name, price, category = _validate_dish_input(
        form.get('name'),
        form.get('price'),
        form.get('category_id'),
        restaurant
    )

    dish.name = name
    dish.price = price
    dish.category_id = category.id
    dish.description = (form.get('description') or '').strip() or None
    dish.image = (form.get('image') or '').strip() or None

    db.session.commit()

    return dish
def toggle_dish_availability(restaurant, dish_id):
    dish = get_dish_for_restaurant(dish_id, restaurant.id)

    if not dish:
        raise ValueError('Món ăn không tồn tại')

    if dish.is_available:
        dish.is_available = False
    else:
        dish.is_available = True

    db.session.commit()

    return dish


def delete_dish(restaurant, dish_id):
    dish = get_dish_for_restaurant(dish_id, restaurant.id)

    if not dish:
        raise ValueError('Món ăn không tồn tại')

    dish.active = False
    dish.is_available = False

    db.session.commit()


def get_dish_for_restaurant(dish_id, restaurant_id):
    dish = Dish.query.filter(
        Dish.id == dish_id,
        Dish.restaurant_id == restaurant_id,
        Dish.active == True
    ).first()

    return dish


def get_all_dishes(restaurant_id):
    dishes = Dish.query.filter(
        Dish.restaurant_id == restaurant_id,
        Dish.active == True
    ).order_by(
        Dish.category_id,
        Dish.name
    ).all()

    return dishes


def get_restaurant_orders(restaurant_id, status=None):
    orders = Order.query.filter(
        Order.restaurant_id == restaurant_id
    )

    if status:
        orders = orders.filter(Order.status == status)

    orders = orders.order_by(
        Order.created_date.desc(),
        Order.id.desc()
    ).all()

    return orders


def get_order_status_counts(restaurant_id):
    rows = db.session.query(
        Order.status,
        func.count(Order.id)
    ).filter(
        Order.restaurant_id == restaurant_id
    ).group_by(
        Order.status
    ).all()

    data = {}

    for status, count in rows:
        data[status] = count

    return data


def get_order_for_restaurant(order_id, restaurant_id):
    order = Order.query.filter(
        Order.id == order_id,
        Order.restaurant_id == restaurant_id
    ).first()

    return order


def expire_overdue_orders(restaurant_id):
    now = datetime.now()

    overdue = Order.query.filter(
        Order.restaurant_id == restaurant_id,
        Order.status == OrderStatus.PENDING,
        Order.confirm_deadline.isnot(None),
        Order.confirm_deadline < now
    ).all()

    for order in overdue:
        order.status = OrderStatus.EXPIRED

    if len(overdue) > 0:
        db.session.commit()

    return overdue


def expire_all_overdue_orders():
    now = datetime.now()
    count = (Order.query
             .filter(Order.status == OrderStatus.PENDING,
                     Order.confirm_deadline.isnot(None),
                     Order.confirm_deadline < now)
             .update({Order.status: OrderStatus.EXPIRED},
                     synchronize_session=False))
    if count:
        db.session.commit()
    return count

def confirm_order(order):
    if order.is_expired():
        order.status = OrderStatus.EXPIRED
        db.session.commit()
        raise ValueError('Đơn đã quá hạn xác nhận')

    if order.status != OrderStatus.PENDING:
        raise ValueError('Đơn này không thể xác nhận')

    now = datetime.now()
    changed = (Order.query
               .filter(Order.id == order.id,
                       Order.status == OrderStatus.PENDING,
                       Order.confirm_deadline >= now)
               .update({Order.status: OrderStatus.CONFIRMED,
                        Order.confirmed_at: now}, synchronize_session=False))
    if not changed:
        db.session.rollback()
        raise ValueError('Đơn này không thể xác nhận')
    db.session.commit()
    db.session.refresh(order)

    return order

def advance_order(order):
    next_status = NEXT_STATUS.get(order.status)
    if not next_status:
        raise ValueError('Trạng thái hiện tại của đơn không thể chuyển tiếp')
    previous = order.status
    changed = (Order.query
               .filter(Order.id == order.id, Order.status == previous)
               .update({Order.status: next_status}, synchronize_session=False))
    if not changed:
        db.session.rollback()
        raise ValueError('Trạng thái đơn đã được thay đổi bởi thao tác khác')
    db.session.commit()
    db.session.refresh(order)
    return order


def cancel_order(order, reason):
    reason = (reason or '').strip()

    if not reason:
        raise ValueError('Vui lòng nhập lý do hủy đơn')

    if order.status == OrderStatus.COMPLETED:
        raise ValueError('Đơn đã hoàn thành không thể hủy')

    if order.status == OrderStatus.CANCELLED:
        raise ValueError('Đơn này đã được hủy')

    if order.status == OrderStatus.EXPIRED:
        raise ValueError('Đơn đã quá hạn không thể hủy')

    order.cancel_by_restaurant(reason)

    db.session.commit()

    return order


def get_dashboard_stats(restaurant_id):
    counts = get_order_status_counts(restaurant_id)
    revenue = (db.session.query(func.coalesce(func.sum(Order.total_amount), 0))
               .filter(Order.restaurant_id == restaurant_id,
                       Order.status.in_([OrderStatus.COMPLETED,
                                         OrderStatus.DELIVERING]))
               .scalar())
    return {'counts': counts, 'revenue': revenue}

def update_restaurant_settings(restaurant, data):
    phone = (data.get('phone') or '').strip()
    description = (data.get('description') or '').strip()

    def _int_field(name):
        raw = (data.get(name) or '').strip()
        if not raw:
            return None
        try:
            return int(float(raw))
        except (TypeError, ValueError):
            raise ValueError('Giá trị nhập không hợp lệ')

    def _float_field(name):
        raw = (data.get(name) or '').strip()
        if not raw:
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            raise ValueError('Giá trị nhập không hợp lệ')

    min_amount = _int_field('min_order_amount')
    timeout = _int_field('confirm_timeout_minutes')
    radius = _float_field('delivery_radius_km')
    max_qty = _int_field('max_quantity_per_item')
    latitude = _float_field('latitude')
    longitude = _float_field('longitude')

    if phone and not (phone.isdigit() and 10 <= len(phone) <= 11):
        raise ValueError('Số điện thoại phải từ 10 đến 11 ký số')
    if min_amount is not None and min_amount < 0:
        raise ValueError('Giá trị đơn tối thiểu không thể âm')
    if timeout is None or timeout < 1:
        raise ValueError('Thời gian xác nhận tối thiểu 1 phút')
    if max_qty is not None and max_qty < 1:
        raise ValueError('Số lượng tối đa 1 món/đơn tối thiểu 1 phần')

    if radius is not None and radius <= 0:
        raise ValueError('Bán kính giao hàng phải lớn hơn 0')

    if (latitude is None) != (longitude is None):
        raise ValueError('Vui lòng nhập đầy đủ cả kinh độ và vĩ độ')

    if latitude is not None and not (-90 <= latitude <= 90):
        raise ValueError('Vĩ độ phải nằm trong khoảng -90 đến 90')
    if longitude is not None and not (-180 <= longitude <= 180):
        raise ValueError('Kinh độ phải nằm trong khoảng -180 đến 180')

    restaurant.is_open = bool(data.get('is_open'))
    restaurant.phone = phone
    restaurant.description = description or None
    restaurant.min_order_amount = min_amount
    restaurant.confirm_timeout_minutes = timeout
    restaurant.delivery_radius_km = radius
    restaurant.max_quantity_per_item = max_qty
    restaurant.latitude = latitude
    restaurant.longitude = longitude
    db.session.commit()
    return restaurant
def get_order_status_counts():
    rows = (
        db.session.query(Order.status, func.count(Order.id))
        .group_by(Order.status)
        .all()
    )
    return {status: count for status, count in rows}


def get_top_restaurants(limit=5):
    return (
        db.session.query(
            Restaurant,
            func.count(Order.id).label('order_count'),
            func.coalesce(func.sum(Order.total_amount), 0).label('revenue'),
        )
        .join(Order, Order.restaurant_id == Restaurant.id)
        .filter(Order.status.in_([
            OrderStatus.COMPLETED, OrderStatus.DELIVERING
        ]))
        .group_by(Restaurant.id)
        .order_by(func.sum(Order.total_amount).desc())
        .limit(limit)
        .all()
    )


def get_top_dishes(limit=5):
    return (
        db.session.query(
            Dish,
            func.coalesce(func.sum(OrderDetail.quantity), 0).label('total_qty'),
            func.coalesce(
                func.sum(OrderDetail.unit_price * OrderDetail.quantity), 0
            ).label('revenue'),
        )
        .join(OrderDetail, OrderDetail.dish_id == Dish.id)
        .join(Order, Order.id == OrderDetail.order_id)
        .filter(Order.status.in_([
            OrderStatus.COMPLETED, OrderStatus.DELIVERING
        ]))
        .group_by(Dish.id)
        .order_by(func.sum(OrderDetail.quantity).desc())
        .limit(limit)
        .all()
    )


def get_recent_orders(limit=8):
    return (
        Order.query
        .order_by(Order.created_date.desc(), Order.id.desc())
        .limit(limit)
        .all()
    )


def get_orders(status=None):
    query = Order.query
    if status:
        query = query.filter(Order.status == status)
    return query.order_by(Order.created_date.desc(), Order.id.desc()).all()


def get_pending_restaurants():
    return (
        Restaurant.query
        .filter(Restaurant.status == RestaurantStatus.PENDING)
        .order_by(Restaurant.id.desc())
        .all()
    )


def get_restaurants(status=None):
    query = Restaurant.query
    if status:
        query = query.filter(Restaurant.status == status)
    return query.order_by(Restaurant.id.desc()).all()


def get_restaurant(restaurant_id):
    return Restaurant.query.get(restaurant_id)


def get_restaurant_dishes(restaurant_id):
    return (
        Dish.query.filter(Dish.restaurant_id == restaurant_id)
        .order_by(Dish.active.desc(), Dish.category_id, Dish.name)
        .all()
    )


def approve_restaurant(restaurant):
    if restaurant.status != RestaurantStatus.PENDING:
        raise ValueError('Chỉ duyệt được nhà hàng đang chờ duyệt')
    restaurant.status = RestaurantStatus.APPROVED
    db.session.commit()
    return restaurant


def lock_restaurant(restaurant):
    if restaurant.status != RestaurantStatus.APPROVED:
        raise ValueError('Chỉ khóa được nhà hàng đã được duyệt')
    restaurant.status = RestaurantStatus.LOCKED
    db.session.commit()
    return restaurant


def unlock_restaurant(restaurant):
    if restaurant.status != RestaurantStatus.LOCKED:
        raise ValueError('Chỉ mở khóa được nhà hàng đang bị khóa')
    restaurant.status = RestaurantStatus.APPROVED
    db.session.commit()
    return restaurant

def get_user_by_id(user_id):
    return User.query.get(user_id)


def get_users(role=None, keyword=None):
    query = User.query
    if role:
        query = query.filter(User.role == role)
    kw = (keyword or '').strip()
    if kw:
        like = f'%{kw}%'
        query = query.filter(db.or_(
            User.username.ilike(like),
            User.email.ilike(like),
            User.full_name.ilike(like),
        ))
    return query.order_by(User.id.desc()).all()


def set_user_active(user, active, current_admin_id=None):
    if user.id == current_admin_id:
        raise ValueError('Không thể tự khóa tài khoản admin đang đăng nhập')
    user.active = active
    db.session.commit()
    return user


CONFIG_KEYS = {
    'DEFAULT_CONFIRM_TIMEOUT_MINUTES': 'Thời gian xác nhận đơn mặc định (phút)',
    'DEFAULT_MIN_ORDER_AMOUNT': 'Giá trị đơn tối thiểu mặc định (VNĐ)',
    'MAX_QUANTITY_PER_ITEM': 'Số lượng tối đa 1 món/đơn',
    'SEARCH_PAGE_SIZE': 'Số kết quả tìm kiếm mỗi trang',
}


def get_all_configs():
    configs = {cfg.key: cfg for cfg in SystemConfigModel.query.all()}
    result = []
    for key, description in CONFIG_KEYS.items():
        cfg = configs.get(key)
        result.append({
            'key': key,
            'value': cfg.value if cfg else '',
            'description': cfg.description if cfg else description,
        })
    return result


def update_config(key, value):
    value = (value or '').strip()
    if key not in CONFIG_KEYS:
        raise ValueError('Cấu hình không hợp lệ')
    try:
        int_value = int(value)
    except (TypeError, ValueError):
        raise ValueError(f'"{key}" phải là số nguyên')

    minimums = {
        'DEFAULT_CONFIRM_TIMEOUT_MINUTES': 1,
        'DEFAULT_MIN_ORDER_AMOUNT': 0,
        'MAX_QUANTITY_PER_ITEM': 1,
        'SEARCH_PAGE_SIZE': 20,
    }
    if int_value < minimums[key]:
        raise ValueError(f'"{key}" phải >= {minimums[key]}')
    if key == 'SEARCH_PAGE_SIZE' and int_value > 30:
        raise ValueError('"SEARCH_PAGE_SIZE" phải <= 30')

    cfg = SystemConfigModel.query.get(key)
    if not cfg:
        cfg = SystemConfigModel(
            key=key, value=value, description=CONFIG_KEYS[key]
        )
        db.session.add(cfg)
    else:
        cfg.value = value
    db.session.commit()
    return cfg




