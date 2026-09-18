from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app import db
from app.models import (
    Dish, Order, OrderDetail, OrderStatus, PaymentStatus,
    Restaurant, RestaurantStatus, SystemConfig, User, UserRole,
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
        .options(joinedload(Order.user), joinedload(Order.restaurant))
        .order_by(Order.created_date.desc(), Order.id.desc())
        .limit(limit)
        .all()
    )


def get_orders(status=None, page=None, per_page=25):
    query = Order.query.options(
        joinedload(Order.user), joinedload(Order.restaurant)
    )
    if status:
        query = query.filter(Order.status == status)
    query = query.order_by(Order.created_date.desc(), Order.id.desc())
    if page is not None:
        return query.paginate(page=page, per_page=per_page, error_out=False)
    return query.all()


def get_pending_restaurants():
    return (
        Restaurant.query
        .filter(Restaurant.status == RestaurantStatus.PENDING)
        .order_by(Restaurant.id.desc())
        .all()
    )


def get_restaurants(status=None, page=None, per_page=25):
    query = Restaurant.query.options(joinedload(Restaurant.owner))
    if status:
        query = query.filter(Restaurant.status == status)
    query = query.order_by(Restaurant.id.desc())
    if page is not None:
        return query.paginate(page=page, per_page=per_page, error_out=False)
    return query.all()


def get_restaurant(restaurant_id):
    return db.session.get(Restaurant, restaurant_id)


def get_restaurant_dishes(restaurant_id):
    return (
        Dish.query.filter(Dish.restaurant_id == restaurant_id)
        .order_by(Dish.active.desc(), Dish.category_id, Dish.name)
        .all()
    )


def approve_restaurant(restaurant):
    changed = (Restaurant.query
               .filter(Restaurant.id == restaurant.id,
                       Restaurant.status == RestaurantStatus.PENDING)
               .update({Restaurant.status: RestaurantStatus.APPROVED},
                       synchronize_session=False))
    if not changed:
        db.session.rollback()
        raise ValueError('Chỉ duyệt được nhà hàng đang chờ duyệt')
    db.session.commit()
    db.session.refresh(restaurant)
    return restaurant


def lock_restaurant(restaurant):
    changed = (Restaurant.query
               .filter(Restaurant.id == restaurant.id,
                       Restaurant.status == RestaurantStatus.APPROVED)
               .update({Restaurant.status: RestaurantStatus.LOCKED},
                       synchronize_session=False))
    if not changed:
        db.session.rollback()
        raise ValueError('Chỉ khóa được nhà hàng đã được duyệt')
    db.session.commit()
    db.session.refresh(restaurant)
    return restaurant


def unlock_restaurant(restaurant):
    changed = (Restaurant.query
               .filter(Restaurant.id == restaurant.id,
                       Restaurant.status == RestaurantStatus.LOCKED)
               .update({Restaurant.status: RestaurantStatus.APPROVED},
                       synchronize_session=False))
    if not changed:
        db.session.rollback()
        raise ValueError('Chỉ mở khóa được nhà hàng đang bị khóa')
    db.session.commit()
    db.session.refresh(restaurant)
    return restaurant


def get_user_by_id(user_id):
    return db.session.get(User, user_id)


def get_users(role=None, keyword=None, page=None, per_page=25):
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
    query = query.order_by(User.id.desc())
    if page is not None:
        return query.paginate(page=page, per_page=per_page, error_out=False)
    return query.all()


def set_user_active(user, active, current_admin_id=None):
    if user.id == current_admin_id:
        raise ValueError('Không thể tự khóa tài khoản admin đang đăng nhập')
    changed = (User.query
               .filter(User.id == user.id, User.active.is_(not active))
               .update({User.active: active}, synchronize_session=False))
    if not changed:
        db.session.rollback()
        raise ValueError('Trạng thái tài khoản đã được thay đổi')
    db.session.commit()
    db.session.refresh(user)
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

    cfg = db.session.get(SystemConfigModel, key)
    if not cfg:
        cfg = SystemConfigModel(
            key=key, value=value, description=CONFIG_KEYS[key]
        )
        db.session.add(cfg)
    else:
        cfg.value = value
    db.session.commit()
    return cfg
