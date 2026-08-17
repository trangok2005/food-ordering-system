from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from app import db
from app.models import (Dish, Order, OrderDetail, OrderStatus, PaymentStatus,
                        Restaurant, RestaurantStatus, User, UserRole)


admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.before_request
@login_required
def _require_admin():
    if current_user.role.name != 'ADMIN':
        abort(403)


def _status_from_name(name):
    if not name:
        return None
    for member in RestaurantStatus:
        if member.name == name:
            return member
    return None


def _load_restaurant(restaurant_id):
    restaurant = Restaurant.query.get(restaurant_id)
    if not restaurant:
        abort(404)
    return restaurant


# ---------------- DAO ----------------

def get_dashboard_stats():
    restaurant_count = Restaurant.query.count()
    restaurant_by_status = dict(
        db.session.query(Restaurant.status, func.count(Restaurant.id))
        .group_by(Restaurant.status)
        .all()
    )
    user_count = (User.query
                  .filter(User.role.in_([UserRole.CUSTOMER, UserRole.USER]))
                  .count())
    owner_count = (User.query
                   .filter(User.role == UserRole.RESTAURANT)
                   .count())
    order_count = Order.query.count()
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
    """Nhà hàng có doanh thu cao nhất (đơn đã giao/hoàn thành)."""
    return (
        db.session.query(
            Restaurant,
            func.count(Order.id).label('order_count'),
            func.coalesce(func.sum(Order.total_amount), 0).label('revenue'),
        )
        .join(Order, Order.restaurant_id == Restaurant.id)
        .filter(Order.status.in_([OrderStatus.COMPLETED,
                                  OrderStatus.DELIVERING]))
        .group_by(Restaurant.id)
        .order_by(func.sum(Order.total_amount).desc())
        .limit(limit)
        .all()
    )


def get_top_dishes(limit=5):
    """Món ăn được đặt nhiều nhất."""
    return (
        db.session.query(
            Dish,
            func.coalesce(func.sum(OrderDetail.quantity), 0).label('total_qty'),
            func.coalesce(func.sum(OrderDetail.unit_price * OrderDetail.quantity), 0)
            .label('revenue'),
        )
        .join(OrderDetail, OrderDetail.dish_id == Dish.id)
        .join(Order, Order.id == OrderDetail.order_id)
        .filter(Order.status.in_([OrderStatus.COMPLETED,
                                  OrderStatus.DELIVERING]))
        .group_by(Dish.id)
        .order_by(func.sum(OrderDetail.quantity).desc())
        .limit(limit)
        .all()
    )


def get_recent_orders(limit=8):
    return (Order.query
            .order_by(Order.created_date.desc(), Order.id.desc())
            .limit(limit)
            .all())


def get_restaurants(status=None):
    query = Restaurant.query
    if status:
        query = query.filter(Restaurant.status == status)
    return query.order_by(Restaurant.id.desc()).all()


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


# ---------------- ROUTES ----------------

@admin_bp.route('/')
def dashboard():
    stats = get_dashboard_stats()
    pending = (Restaurant.query
               .filter(Restaurant.status == RestaurantStatus.PENDING)
               .order_by(Restaurant.id.desc())
               .all())
    recent_orders = get_recent_orders()
    return render_template('admin/index.html',
                           stats=stats,
                           pending=pending,
                           recent_orders=recent_orders,
                           active='dashboard')


@admin_bp.route('/stats')
def stats_view():
    stats = get_dashboard_stats()
    order_counts = get_order_status_counts()
    top_restaurants = get_top_restaurants()
    top_dishes = get_top_dishes()
    return render_template('admin/stats.html',
                           stats=stats,
                           order_counts=order_counts,
                           top_restaurants=top_restaurants,
                           top_dishes=top_dishes,
                           OrderStatus=OrderStatus,
                           active='stats')


@admin_bp.route('/restaurants')
def restaurants_view():
    status = _status_from_name(request.args.get('status'))
    restaurants = get_restaurants(status)
    return render_template('admin/restaurants.html',
                           restaurants=restaurants,
                           statuses=RestaurantStatus,
                           current_status=status,
                           active='restaurants')


@admin_bp.route('/restaurants/<int:restaurant_id>/approve', methods=['POST'])
def approve_restaurant_view(restaurant_id):
    restaurant = _load_restaurant(restaurant_id)
    try:
        approve_restaurant(restaurant)
        flash(f'Đã duyệt nhà hàng {restaurant.name}')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('admin.restaurants_view'))


@admin_bp.route('/restaurants/<int:restaurant_id>/lock', methods=['POST'])
def lock_restaurant_view(restaurant_id):
    restaurant = _load_restaurant(restaurant_id)
    try:
        lock_restaurant(restaurant)
        flash(f'Đã khóa nhà hàng {restaurant.name}')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('admin.restaurants_view'))


@admin_bp.route('/restaurants/<int:restaurant_id>/unlock', methods=['POST'])
def unlock_restaurant_view(restaurant_id):
    restaurant = _load_restaurant(restaurant_id)
    try:
        unlock_restaurant(restaurant)
        flash(f'Đã mở khóa nhà hàng {restaurant.name}')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('admin.restaurants_view'))
