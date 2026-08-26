from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.models import OrderStatus, PaymentStatus
from app.restaurant import restaurant_bp, dao


# Lấy nhà hàng của tài khoản đang đăng nhập
def get_restaurant():
    if not current_user.is_authenticated:
        abort(403)

    if current_user.role.name != 'RESTAURANT':
        abort(403)

    restaurant = dao.get_restaurant_for_owner(current_user.id)

    if restaurant is None:
        abort(404)

    return restaurant


# Lấy đơn hàng thuộc nhà hàng hiện tại
def get_order(order_id, restaurant):
    order = dao.get_order_for_restaurant(order_id, restaurant.id)

    if order is None:
        abort(404)

    return order


# Đổi tên trạng thái sang OrderStatus
def get_status(status_name):
    if status_name is None:
        return None

    for status in OrderStatus:
        if status.name == status_name:
            return status

    return None


# Trang tổng quan nhà hàng
@restaurant_bp.route('/')
@login_required
def dashboard():
    restaurant = get_restaurant()

    # Tự động hủy những đơn đã quá thời gian xác nhận
    dao.expire_overdue_orders(restaurant.id)

    stats = dao.get_dashboard_stats(restaurant.id)
    orders = dao.get_restaurant_orders(restaurant.id)

    # Chỉ lấy 6 đơn đầu tiên để hiển thị trên dashboard
    orders = orders[:6]

    return render_template(
        'restaurant/dashboard.html',
        restaurant=restaurant,
        stats=stats,
        orders=orders,
        active='dashboard'
    )


# Cấu hình nhà hàng
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


# Danh sách đơn hàng
@restaurant_bp.route('/orders')
@login_required
def orders_view():
    restaurant = get_restaurant()

    # Kiểm tra những đơn đã quá thời gian xác nhận
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


# Xác nhận đơn hàng
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


# Chuyển đơn sang trạng thái tiếp theo
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


# Hủy đơn hàng
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


# Đánh dấu đơn đã hoàn tiền
@restaurant_bp.route('/orders/<int:order_id>/mark-refunded', methods=['POST'])
@login_required
def mark_refunded(order_id):
    restaurant = get_restaurant()
    order = get_order(order_id, restaurant)

    try:
        dao.mark_refunded(order)

        flash(
            f'Đã đánh dấu đơn #{order.id} là đã hoàn tiền '
            f'(nhà hàng tự hoàn ngoài hệ thống)'
        )

    except ValueError as e:
        flash(str(e), 'error')

    return redirect(url_for('restaurant.orders_view'))