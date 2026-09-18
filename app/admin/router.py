from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.models import OrderStatus, RestaurantStatus, UserRole
from app.admin import admin_bp
from app.admin import dao


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


def _order_status_from_name(name):
    if not name:
        return None
    return next((status for status in OrderStatus if status.name == name), None)


def _load_restaurant(restaurant_id):
    restaurant = dao.get_restaurant(restaurant_id)
    if not restaurant:
        abort(404)
    return restaurant


@admin_bp.route('/')
def dashboard():
    stats = dao.get_dashboard_stats()
    pending = dao.get_pending_restaurants()
    recent_orders = dao.get_recent_orders()
    return render_template(
        'admin/index.html',
        stats=stats,
        pending=pending,
        recent_orders=recent_orders,
        active='dashboard',
    )


@admin_bp.route('/stats')
def stats_view():
    stats = dao.get_dashboard_stats()
    order_counts = dao.get_order_status_counts()
    top_restaurants = dao.get_top_restaurants()
    top_dishes = dao.get_top_dishes()
    return render_template(
        'admin/stats.html',
        stats=stats,
        order_counts=order_counts,
        top_restaurants=top_restaurants,
        top_dishes=top_dishes,
        OrderStatus=OrderStatus,
        active='stats',
    )


@admin_bp.route('/orders')
def orders_view():
    status = _order_status_from_name(request.args.get('status'))
    pagination = dao.get_orders(
        status, page=max(request.args.get('page', 1, type=int), 1)
    )
    return render_template(
        'admin/orders.html', orders=pagination.items, pagination=pagination,
        statuses=OrderStatus, current_status=status, active='orders',
    )


@admin_bp.route('/restaurants')
def restaurants_view():
    status = _status_from_name(request.args.get('status'))
    pagination = dao.get_restaurants(
        status, page=max(request.args.get('page', 1, type=int), 1)
    )
    return render_template(
        'admin/restaurants.html',
        restaurants=pagination.items,
        pagination=pagination,
        statuses=RestaurantStatus,
        current_status=status,
        active='restaurants',
    )


@admin_bp.route('/restaurants/<int:restaurant_id>/menu')
def restaurant_menu_view(restaurant_id):
    restaurant = _load_restaurant(restaurant_id)
    return render_template(
        'admin/menu.html', restaurant=restaurant,
        dishes=dao.get_restaurant_dishes(restaurant.id), active='restaurants',
    )


@admin_bp.route('/restaurants/<int:restaurant_id>/approve', methods=['POST'])
def approve_restaurant_view(restaurant_id):
    restaurant = _load_restaurant(restaurant_id)
    try:
        dao.approve_restaurant(restaurant)
        flash(f'Đã duyệt nhà hàng {restaurant.name}')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('admin.restaurants_view'))


@admin_bp.route('/restaurants/<int:restaurant_id>/lock', methods=['POST'])
def lock_restaurant_view(restaurant_id):
    restaurant = _load_restaurant(restaurant_id)
    try:
        dao.lock_restaurant(restaurant)
        flash(f'Đã khóa nhà hàng {restaurant.name}')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('admin.restaurants_view'))


@admin_bp.route('/restaurants/<int:restaurant_id>/unlock', methods=['POST'])
def unlock_restaurant_view(restaurant_id):
    restaurant = _load_restaurant(restaurant_id)
    try:
        dao.unlock_restaurant(restaurant)
        flash(f'Đã mở khóa nhà hàng {restaurant.name}')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('admin.restaurants_view'))


def _role_from_name(name):
    if not name:
        return None
    for member in UserRole:
        if member.name == name:
            return member
    return None


@admin_bp.route('/users')
def users_view():
    role = _role_from_name(request.args.get('role'))
    keyword = request.args.get('q', '')
    pagination = dao.get_users(
        role=role,
        keyword=keyword,
        page=max(request.args.get('page', 1, type=int), 1),
    )
    return render_template(
        'admin/users.html',
        users=pagination.items,
        pagination=pagination,
        roles=UserRole,
        current_role=role,
        keyword=keyword,
        active='users',
    )


@admin_bp.route('/users/<int:user_id>/lock', methods=['POST'])
def lock_user_view(user_id):
    user = dao.get_user_by_id(user_id)
    if not user:
        abort(404)
    try:
        dao.set_user_active(user, False, current_admin_id=current_user.id)
        flash(f'Đã khóa tài khoản {user.username}')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('admin.users_view'))


@admin_bp.route('/users/<int:user_id>/unlock', methods=['POST'])
def unlock_user_view(user_id):
    user = dao.get_user_by_id(user_id)
    if not user:
        abort(404)
    dao.set_user_active(user, True)
    flash(f'Đã mở khóa tài khoản {user.username}')
    return redirect(url_for('admin.users_view'))


@admin_bp.route('/config')
def config_view():
    configs = dao.get_all_configs()
    return render_template(
        'admin/config.html', configs=configs, active='config'
    )


@admin_bp.route('/config/update', methods=['POST'])
def update_config_view():
    key = request.form.get('key', '')
    try:
        dao.update_config(key, request.form.get('value'))
        flash(f'Đã lưu cấu hình {key}')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('admin.config_view'))
