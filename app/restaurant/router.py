from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.models import OrderStatus, PaymentStatus, UserRole
from app.restaurant import restaurant_bp, dao


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
            flash('Đã gửi đăng ký nhà hàng. Vui lòng chờ quản trị viên duyệt.', 'success')
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
        restaurant, request.form.get('name')), 'Đã thêm danh mục')


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
        restaurant, dish_id), 'Đã cập nhật trạng thái món ăn')


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
            flash('Đã lưu cấu hình nhà hàng')

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
            f'{len(expired_orders)} đơn quá hạn xác nhận đã tự động hủy',
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
        flash(f'Đã xác nhận đơn #{order.id}')

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
        flash(f'Đã hủy đơn #{order.id}')

    except ValueError as e:
        flash(str(e), 'error')

    return redirect(url_for('restaurant.orders_view'))
