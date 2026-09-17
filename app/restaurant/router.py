from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.models import OrderStatus, PaymentStatus,RestaurantStatus, UserRole
from app.restaurant import restaurant_bp, dao
from app.admin import admin_bp

def get_restaurant():
    if not current_user.is_authenticated:
        abort(403)

    if current_user.role.name != 'RESTAURANT':
        abort(403)

    restaurant = dao.get_restaurant_for_owner(current_user.id)

    if restaurant is None:
        abort(404)

    return restaurant


def _redirect_menu(action, success_message):
    restaurant = get_restaurant()
    try:
        action(restaurant)
        flash(success_message, 'success')
    except ValueError as exc:
        flash(str(exc), 'error')
    return redirect(url_for('restaurant.menu_view'))


@restaurant_bp.route('/register', methods=['GET', 'POST'])
@login_required
def register_restaurant_view():
    if current_user.role.name not in ('CUSTOMER', 'USER'):
        abort(403)
    if dao.get_restaurant_for_owner(current_user.id):
        return redirect(url_for('restaurant.dashboard'))
    if request.method == 'POST':
        try:
            dao.register_restaurant(current_user, request.form)
            current_user.role = UserRole.RESTAURANT
            dao.commit()
            flash('Đã gửi đăng ký nhà hàng. Hãy vui lòng chờ quản trị viên duyệt.', 'success')
            return redirect(url_for('restaurant.dashboard'))
        except ValueError as exc:
            flash(str(exc), 'error')
    return render_template('restaurant/register.html')


@restaurant_bp.route('/menu')
@login_required
def menu_view():
    restaurant = get_restaurant()
    return render_template('restaurant/menu.html', restaurant=restaurant,
                           categories=dao.get_categories(restaurant.id),
                           dishes=dao.get_all_dishes(restaurant.id), active='menu')


@restaurant_bp.route('/categories', methods=['POST'])
@login_required
def add_category():
    return _redirect_menu(lambda restaurant: dao.add_category(
        restaurant, request.form.get('name')), 'Đã thêm danh mục.')


@restaurant_bp.route('/categories/<int:category_id>', methods=['POST'])
@login_required
def rename_category(category_id):
    return _redirect_menu(lambda restaurant: dao.rename_category(
        restaurant, category_id, request.form.get('name')), 'Đã đổi tên danh mục')


@restaurant_bp.route('/categories/<int:category_id>/delete', methods=['POST'])
@login_required
def delete_category(category_id):
    return _redirect_menu(lambda restaurant: dao.delete_category(
        restaurant, category_id), 'Đã xóa danh mục')


@restaurant_bp.route('/dishes', methods=['POST'])
@login_required
def add_dish():
    return _redirect_menu(lambda restaurant: dao.add_dish(
        restaurant, request.form), 'Đã thêm món ăn')


@restaurant_bp.route('/dishes/<int:dish_id>', methods=['POST'])
@login_required
def update_dish(dish_id):
    return _redirect_menu(lambda restaurant: dao.update_dish(
        restaurant, dish_id, request.form), 'Đã cập nhật món ăn')


@restaurant_bp.route('/dishes/<int:dish_id>/toggle', methods=['POST'])
@login_required
def toggle_dish(dish_id):
    return _redirect_menu(lambda restaurant: dao.toggle_dish_availability(
        restaurant, dish_id), 'Đã cập nhật trạng thái món ăn ')


@restaurant_bp.route('/dishes/<int:dish_id>/delete', methods=['POST'])
@login_required
def delete_dish(dish_id):
    return _redirect_menu(lambda restaurant: dao.delete_dish(
        restaurant, dish_id), 'Đã ẩn món ăn')


@restaurant_bp.route('/pairings/recompute', methods=['POST'])
@login_required
def recompute_pairings():
    restaurant = get_restaurant()
    from app.ai.pairing import recompute_restaurant_pairings
    count = recompute_restaurant_pairings(restaurant.id)
    flash(f'Đã cập nhật {count} luật kết hợp món ăn.', 'success')
    return redirect(url_for('restaurant.dashboard'))


def get_order(order_id, restaurant):
    order = dao.get_order_for_restaurant(order_id, restaurant.id)

    if order is None:
        abort(404)

    return order


def get_status(status_name):
    if status_name is None:
        return None

    for status in OrderStatus:
        if status.name == status_name:
            return status

    return None


@restaurant_bp.route('/')
@login_required
def dashboard():
    restaurant = get_restaurant()

    dao.expire_overdue_orders(restaurant.id)

    stats = dao.get_dashboard_stats(restaurant.id)
    orders = dao.get_restaurant_orders(restaurant.id)
    orders = orders[:6]

    return render_template(
        'restaurant/dashboard.html',
        restaurant=restaurant,
        stats=stats,
        orders=orders,
        OrderStatus=OrderStatus,
        active='dashboard'
    )


@restaurant_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings_view():
    restaurant = get_restaurant()

    if request.method == 'POST':
        try:
            dao.update_restaurant_settings(restaurant, request.form)
            flash('Đã lưu cấu hình nhà hàng.')

            return redirect(url_for('restaurant.settings_view'))

        except ValueError as e:
            flash(str(e), 'error')

    return render_template(
        'restaurant/settings.html',
        restaurant=restaurant,
        active='settings'
    )


@restaurant_bp.route('/orders')
@login_required
def orders_view():
    restaurant = get_restaurant()

    expired_orders = dao.expire_overdue_orders(restaurant.id)

    if expired_orders:
        flash(
            f'{len(expired_orders)} đơn quá hạn xác nhận đã tự động hủy.',
            'warning'
        )

    status_name = request.args.get('status')
    status = get_status(status_name)

    orders = dao.get_restaurant_orders(
        restaurant.id,
        status
    )

    counts = dao.get_order_status_counts(restaurant.id)

    return render_template(
        'restaurant/orders.html',
        restaurant=restaurant,
        orders=orders,
        statuses=OrderStatus,
        current_status=status,
        counts=counts,
        PaymentStatus=PaymentStatus,
        active='orders'
    )


@restaurant_bp.route('/orders/<int:order_id>/confirm', methods=['POST'])
@login_required
def confirm_order(order_id):
    restaurant = get_restaurant()
    order = get_order(order_id, restaurant)

    try:
        dao.confirm_order(order)
        flash(f'Đã xác nhận đơn: #{order.id}')

    except ValueError as e:
        flash(str(e), 'error')

    return redirect(url_for('restaurant.orders_view'))
@restaurant_bp.route('/orders/<int:order_id>/advance', methods=['POST'])
@login_required
def advance_order(order_id):
    restaurant = get_restaurant()
    order = get_order(order_id, restaurant)

    try:
        dao.advance_order(order)

        flash(
            f'Đơn #{order.id} đã chuyển sang trạng thái '
            f'{order.status.value}'
        )

    except ValueError as e:
        flash(str(e), 'error')

    return redirect(url_for('restaurant.orders_view'))
# End of restaurant routes.
@restaurant_bp.route('/orders/<int:order_id>/cancel', methods=['POST'])
@login_required
def cancel_order(order_id):
    restaurant = get_restaurant()
    order = get_order(order_id, restaurant)

    reason = request.form.get('reason', '').strip()

    try:
        dao.cancel_order(order, reason)
        flash(f'Đã hủy đơn  #{order.id}')

    except ValueError as e:
        flash(str(e), 'error')

    return redirect(url_for('restaurant.orders_view'))
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
    return render_template(
        'admin/orders.html', orders=dao.get_orders(status),
        statuses=OrderStatus, current_status=status, active='orders',
    )


@admin_bp.route('/restaurants')
def restaurants_view():
    status = _status_from_name(request.args.get('status'))
    restaurants = dao.get_restaurants(status)
    return render_template(
        'admin/restaurants.html',
        restaurants=restaurants,
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
    users = dao.get_users(role=role, keyword=keyword)
    return render_template(
        'admin/users.html',
        users=users,
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


