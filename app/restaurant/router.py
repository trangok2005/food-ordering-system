from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.models import OrderStatus, PaymentStatus
from app.restaurant import restaurant_bp
from app.restaurant import dao


def _current_restaurant():
    """Trả về nhà hàng của user đang đăng nhập (phải là chủ nhà hàng)."""
    if not current_user.is_authenticated or current_user.role.name != 'RESTAURANT':
        abort(403)
    restaurant = dao.get_restaurant_for_owner(current_user.id)
    if not restaurant:
        abort(404)
    return restaurant


def _load_order(order_id, restaurant):
    order = dao.get_order_for_restaurant(order_id, restaurant.id)
    if not order:
        abort(404)
    return order


def _status_from_name(name):
    if not name:
        return None
    for member in OrderStatus:
        if member.name == name:
            return member
    return None


@restaurant_bp.route('/')
@login_required
def dashboard():
    restaurant = _current_restaurant()
    dao.expire_overdue_orders(restaurant.id)
    stats = dao.get_dashboard_stats(restaurant.id)
    orders = dao.get_restaurant_orders(restaurant.id)[:6]
    return render_template('restaurant/dashboard.html',
                           restaurant=restaurant,
                           stats=stats,
                           orders=orders,
                           active='dashboard')


@restaurant_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings_view():
    restaurant = _current_restaurant()
    if request.method == 'POST':
        try:
            dao.update_restaurant_settings(restaurant, request.form)
            flash('Đã lưu cấu hình nhà hàng')
            return redirect(url_for('restaurant.settings_view'))
        except ValueError as e:
            flash(str(e), 'error')
    return render_template('restaurant/settings.html',
                           restaurant=restaurant,
                           active='settings')


@restaurant_bp.route('/orders')
@login_required
def orders_view():
    restaurant = _current_restaurant()
    expired = dao.expire_overdue_orders(restaurant.id)
    if expired:
        flash(f'{len(expired)} đơn quá hạn xác nhận đã tự động hủy', 'warning')

    status = _status_from_name(request.args.get('status'))
    orders = dao.get_restaurant_orders(restaurant.id, status)
    counts = dao.get_order_status_counts(restaurant.id)
    return render_template('restaurant/orders.html',
                           restaurant=restaurant,
                           orders=orders,
                           statuses=OrderStatus,
                           current_status=status,
                           counts=counts,
                           PaymentStatus=PaymentStatus,
                           active='orders')


@restaurant_bp.route('/orders/<int:order_id>/confirm', methods=['POST'])
@login_required
def confirm_order(order_id):
    restaurant = _current_restaurant()
    order = _load_order(order_id, restaurant)
    try:
        dao.confirm_order(order)
        flash(f'Đã xác nhận đơn #{order.id}')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('restaurant.orders_view'))


@restaurant_bp.route('/orders/<int:order_id>/advance', methods=['POST'])
@login_required
def advance_order(order_id):
    restaurant = _current_restaurant()
    order = _load_order(order_id, restaurant)
    try:
        dao.advance_order(order)
        flash(f'Đơn #{order.id} đã chuyển sang trạng thái {order.status.value}')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('restaurant.orders_view'))


@restaurant_bp.route('/orders/<int:order_id>/cancel', methods=['POST'])
@login_required
def cancel_order(order_id):
    restaurant = _current_restaurant()
    order = _load_order(order_id, restaurant)
    reason = request.form.get('reason', '').strip()
    try:
        dao.cancel_order(order, reason)
        flash(f'Đã hủy đơn #{order.id}')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('restaurant.orders_view'))


@restaurant_bp.route('/orders/<int:order_id>/mark-refunded', methods=['POST'])
@login_required
def mark_refunded(order_id):
    restaurant = _current_restaurant()
    order = _load_order(order_id, restaurant)
    try:
        dao.mark_refunded(order)
        flash(f'Đã đánh dấu đơn #{order.id} là đã hoàn tiền (nhà hàng tự hoàn ngoài hệ thống)')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('restaurant.orders_view'))