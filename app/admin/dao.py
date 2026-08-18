from sqlalchemy import func

from app import db
from app.models import (Dish, Order, OrderDetail, OrderStatus, PaymentStatus,
                        Restaurant, RestaurantStatus, User, UserRole)


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