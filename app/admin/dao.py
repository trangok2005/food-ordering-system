from sqlalchemy import func

from app import db
from app.models import (Dish, Order, OrderDetail, OrderStatus, PaymentStatus,
                        Restaurant, RestaurantStatus, SystemConfig,
                        User, UserRole)


# Bí danh ngắn cho cấu hình hệ thống
SystemConfigModel = SystemConfig


def get_dashboard_stats():
    """Số liệu tổng quan cho trang dashboard admin."""
    restaurant_count = Restaurant.query.count()

    # Đếm nhà hàng theo từng trạng thái (chờ duyệt / đã duyệt / bị khóa)
    # để hiển thị nhanh số đang chờ xử lý.
    restaurant_by_status = dict(
        db.session.query(Restaurant.status, func.count(Restaurant.id))
        .group_by(Restaurant.status)
        .all()
    )

    # Khách hàng (CUSTOMER/USER) tách riêng với chủ nhà hàng (RESTAURANT).
    user_count = (User.query
                  .filter(User.role.in_([UserRole.CUSTOMER, UserRole.USER]))
                  .count())
    owner_count = (User.query
                   .filter(User.role == UserRole.RESTAURANT)
                   .count())

    order_count = Order.query.count()

    # Doanh thu chỉ tính trên các đơn đã giao/hoàn thành,
    # không tính đơn đang xử lý hoặc bị hủy.
    paid_count = (Order.query
                  .filter(Order.payment_status == PaymentStatus.PAID)
                  .count())
    revenue = (db.session
               .query(func.coalesce(func.sum(Order.total_amount), 0))
               .filter(Order.status.in_([OrderStatus.COMPLETED,
                                         OrderStatus.DELIVERING]))
               .scalar())
    avg_order = (round(revenue / paid_count)
                 if paid_count else 0)

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
    rows = (db.session.query(Order.status, func.count(Order.id))
            .group_by(Order.status)
            .all())
    return {status: count for status, count in rows}


def get_top_restaurants(limit=5):
    # Nhà hàng có doanh thu cao nhất (chỉ tính đơn đã giao/hoàn thành).
    return (db.session.query(
            Restaurant,
            func.count(Order.id).label('order_count'),
            func.coalesce(func.sum(Order.total_amount), 0).label('revenue'))
            .join(Order, Order.restaurant_id == Restaurant.id)
            .filter(Order.status.in_([OrderStatus.COMPLETED,
                                      OrderStatus.DELIVERING]))
            .group_by(Restaurant.id)
            .order_by(func.sum(Order.total_amount).desc())
            .limit(limit)
            .all())


def get_top_dishes(limit=5):
    # Món ăn được đặt nhiều nhất (theo tổng số lượng trong các
    # đơn đã giao/hoàn thành).
    return (db.session.query(
            Dish,
            func.coalesce(func.sum(OrderDetail.quantity), 0).label('total_qty'),
            func.coalesce(func.sum(OrderDetail.unit_price * OrderDetail.quantity), 0)
            .label('revenue'))
            .join(OrderDetail, OrderDetail.dish_id == Dish.id)
            .join(Order, Order.id == OrderDetail.order_id)
            .filter(Order.status.in_([OrderStatus.COMPLETED,
                                      OrderStatus.DELIVERING]))
            .group_by(Dish.id)
            .order_by(func.sum(OrderDetail.quantity).desc())
            .limit(limit)
            .all())


def get_recent_orders(limit=8):
    return (Order.query
            .order_by(Order.created_date.desc(), Order.id.desc())
            .limit(limit)
            .all())


def get_pending_restaurants():
    return (Restaurant.query
            .filter(Restaurant.status == RestaurantStatus.PENDING)
            .order_by(Restaurant.id.desc())
            .all())


def get_restaurants(status=None):
    query = Restaurant.query
    if status:
        query = query.filter(Restaurant.status == status)
    return query.order_by(Restaurant.id.desc()).all()


def get_restaurant(restaurant_id):
    return Restaurant.query.get(restaurant_id)


def approve_restaurant(restaurant):
    # Admin duyệt nhà hàng mới đăng ký.
    if restaurant.status != RestaurantStatus.PENDING:
        raise ValueError('Chỉ duyệt được nhà hàng đang chờ duyệt')
    restaurant.status = RestaurantStatus.APPROVED
    db.session.commit()
    return restaurant


def lock_restaurant(restaurant):
    # Khóa nhà hàng vi phạm -> không nhận đơn được nữa.
    if restaurant.status != RestaurantStatus.APPROVED:
        raise ValueError('Chỉ khóa được nhà hàng đã được duyệt')
    restaurant.status = RestaurantStatus.LOCKED
    db.session.commit()
    return restaurant


def unlock_restaurant(restaurant):
    # Mở khóa để nhà hàng hoạt động trở lại.
    if restaurant.status != RestaurantStatus.LOCKED:
        raise ValueError('Chỉ mở khóa được nhà hàng đang bị khóa')
    restaurant.status = RestaurantStatus.APPROVED
    db.session.commit()
    return restaurant


# ---------- QUẢN LÝ NGƯỜI DÙNG ----------

def get_user_by_id(user_id):
    return User.query.get(user_id)


def get_users(role=None, keyword=None):
    """Danh sách người dùng, lọc theo vai trò và từ khóa (username/email/tên)."""
    query = User.query
    if role:
        query = query.filter(User.role == role)
    kw = (keyword or '').strip()
    if kw:
        like = f'%{kw}%'
        query = query.filter(db.or_(User.username.ilike(like),
                                    User.email.ilike(like),
                                    User.full_name.ilike(like)))
    return query.order_by(User.id.desc()).all()


def set_user_active(user, active):
    """Khóa / mở khóa tài khoản (soft lock qua trường active).
    Không cho admin tự khóa chính mình."""
    if user.id == _current_admin_id():
        raise ValueError('Không thể tự khóa tài khoản admin đang đăng nhập')
    user.active = active
    db.session.commit()
    return user


_current_admin_id_holder = {}


def remember_admin_id(user_id):
    """Lưu id admin đang thao tác để chặn tự khóa chính mình
    (tránh truyền current_user sâu xuống DAO)."""
    _current_admin_id_holder['id'] = user_id


def _current_admin_id():
    return _current_admin_id_holder.get('id')


# ---------- CẤU HÌNH HỆ THỐNG ----------

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
        'SEARCH_PAGE_SIZE': 5,
    }
    if int_value < minimums[key]:
        raise ValueError(f'"{key}" phải >= {minimums[key]}')

    cfg = SystemConfigModel.query.get(key)
    if not cfg:
        cfg = SystemConfigModel(key=key, value=value,
                                description=CONFIG_KEYS[key])
        db.session.add(cfg)
    else:
        cfg.value = value
    db.session.commit()
    return cfg