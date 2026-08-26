from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.models import OrderStatus, RestaurantStatus, UserRole
from app.admin import admin_bp
from app.admin import dao


@admin_bp.before_request
@login_required
def _require_admin():
    # Toàn bộ trang admin chỉ dành cho ADMIN.
    if current_user.role.name != 'ADMIN':
        abort(403)


def _status_from_name(name):
    # Chuyển chuỗi trạng thái từ URL (vd: status=PENDING) về
    # member của enum, không hợp lệ thì trả None (xem tất cả).
    if not name:
        return None
    for member in RestaurantStatus:
        if member.name == name:
            return member
    return None


def _load_restaurant(restaurant_id):
    restaurant = dao.get_restaurant(restaurant_id)
    if not restaurant:
        abort(404)
    return restaurant


@admin_bp.route('/')
def dashboard():
    # Trang chính: số liệu tổng quan, nhà hàng chờ duyệt,
    # và vài đơn mới nhất.
    stats = dao.get_dashboard_stats()
    pending = dao.get_pending_restaurants()
    recent_orders = dao.get_recent_orders()
    return render_template('admin/index.html',
                           stats=stats,
                           pending=pending,
                           recent_orders=recent_orders,
                           active='dashboard')


@admin_bp.route('/stats')
def stats_view():
    stats = dao.get_dashboard_stats()
    order_counts = dao.get_order_status_counts()
    top_restaurants = dao.get_top_restaurants()
    top_dishes = dao.get_top_dishes()
    return render_template('admin/stats.html',
                           stats=stats,
                           order_counts=order_counts,
                           top_restaurants=top_restaurants,
                           top_dishes=top_dishes,
                           OrderStatus=OrderStatus,
                           active='stats')


@admin_bp.route('/restaurants')
def restaurants_view():
    # Lọc theo trạng thái nếu có ?status=... trên URL.
    status = _status_from_name(request.args.get('status'))
    restaurants = dao.get_restaurants(status)
    return render_template('admin/restaurants.html',
                           restaurants=restaurants,
                           statuses=RestaurantStatus,
                           current_status=status,
                           active='restaurants')


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


# ---------- QUẢN LÝ NGƯỜI DÙNG ----------

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
    users = dao.get_users(role=role, keyword=keyword)
    return render_template('admin/users.html',
                           users=users,
                           roles=UserRole,
                           current_role=role,
                           keyword=keyword,
                           active='users')


@admin_bp.route('/users/<int:user_id>/lock', methods=['POST'])
def lock_user_view(user_id):
    user = dao.get_user_by_id(user_id)
    if not user:
        abort(404)
    try:
        dao.remember_admin_id(current_user.id)
        dao.set_user_active(user, False)
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


# ---------- CẤU HÌNH HỆ THỐNG ----------

@admin_bp.route('/config')
def config_view():
    configs = dao.get_all_configs()
    return render_template('admin/config.html',
                           configs=configs,
                           active='config')


@admin_bp.route('/config/update', methods=['POST'])
def update_config_view():
    key = request.form.get('key', '')
    try:
        dao.update_config(key, request.form.get('value'))
        flash(f'Đã lưu cấu hình {key}')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('admin.config_view'))