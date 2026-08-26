from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from app import db

from app.models import OrderStatus, PaymentStatus, UserRole
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


@restaurant_bp.route('/register', methods=['GET', 'POST'])
@login_required
def register_restaurant_view():
    """Nhà hàng tự đăng ký: tài khoản khách hàng điền thông tin nhà hàng,
    hệ thống nâng quyền lên RESTAURANT và tạo nhà hàng chờ admin duyệt."""
    if current_user.role.name == 'RESTAURANT':
        return redirect(url_for('restaurant.dashboard'))
    if current_user.role.name == 'ADMIN':
        abort(403)

    if request.method == 'POST':
        try:
            dao.register_restaurant(current_user, request.form)
            current_user.role = UserRole.RESTAURANT
            db.session.commit()
            flash('Đăng ký nhà hàng thành công! Vui lòng chờ quản trị viên duyệt.')
            return redirect(url_for('auth.logout_process'))
        except ValueError as e:
            flash(str(e), 'error')

    return render_template('restaurant/register.html')


@restaurant_bp.route('/menu')
@login_required
def menu_view():
    """Trang quản lý thực đơn: danh mục + toàn bộ món ăn của nhà hàng."""
    restaurant = _current_restaurant()
    categories = dao.get_categories(restaurant.id)
    dishes = dao.get_all_dishes(restaurant.id)
    return render_template('restaurant/menu.html',
                           restaurant=restaurant,
                           categories=categories,
                           dishes=dishes,
                           active='menu')


@restaurant_bp.route('/categories/add', methods=['POST'])
@login_required
def add_category():
    restaurant = _current_restaurant()
    try:
        dao.add_category(restaurant, request.form.get('name'))
        flash('Đã thêm danh mục')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('restaurant.menu_view'))


@restaurant_bp.route('/categories/<int:category_id>/rename', methods=['POST'])
@login_required
def rename_category(category_id):
    restaurant = _current_restaurant()
    try:
        dao.rename_category(restaurant, category_id, request.form.get('name'))
        flash('Đã đổi tên danh mục')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('restaurant.menu_view'))


@restaurant_bp.route('/categories/<int:category_id>/delete', methods=['POST'])
@login_required
def delete_category(category_id):
    restaurant = _current_restaurant()
    try:
        dao.delete_category(restaurant, category_id)
        flash('Đã xóa danh mục')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('restaurant.menu_view'))


@restaurant_bp.route('/dishes/add', methods=['POST'])
@login_required
def add_dish():
    restaurant = _current_restaurant()
    try:
        dish = dao.add_dish(restaurant, request.form)
        flash(f'Đã thêm món "{dish.name}"')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('restaurant.menu_view'))


@restaurant_bp.route('/dishes/<int:dish_id>/update', methods=['POST'])
@login_required
def update_dish(dish_id):
    restaurant = _current_restaurant()
    try:
        dao.update_dish(restaurant, dish_id, request.form)
        flash('Đã cập nhật món ăn')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('restaurant.menu_view'))


@restaurant_bp.route('/dishes/<int:dish_id>/toggle', methods=['POST'])
@login_required
def toggle_dish(dish_id):
    restaurant = _current_restaurant()
    try:
        dish = dao.toggle_dish_availability(restaurant, dish_id)
        state = 'đang bán' if dish.is_available else 'tạm ẩn (hết hàng)'
        flash(f'Món "{dish.name}" đã chuyển sang {state}')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('restaurant.menu_view'))


@restaurant_bp.route('/dishes/<int:dish_id>/delete', methods=['POST'])
@login_required
def delete_dish(dish_id):
    restaurant = _current_restaurant()
    try:
        dao.delete_dish(restaurant, dish_id)
        flash('Đã xóa món khỏi thực đơn')
    except ValueError as e:
        flash(str(e), 'error')
    return redirect(url_for('restaurant.menu_view'))


@restaurant_bp.route('/ai/recompute-pairings', methods=['POST'])
@login_required
def recompute_pairings():
    """Tính lại luật kết hợp món đi kèm (association rules) từ các
    đơn đã hoàn thành của nhà hàng - phục vụ gợi ý "món ăn kèm"."""
    restaurant = _current_restaurant()
    try:
        from app.ai import pairing
        rule_count = pairing.recompute_restaurant_pairings(restaurant.id)
        if rule_count:
            flash(f'Đã cập nhật {rule_count} luật kết hợp món ăn')
        else:
            flash('Chưa đủ dữ liệu đơn hoàn thành để tìm ra luật kết hợp (cần đơn có từ 2 món trở lên)', 'warning')
    except Exception as e:
        flash(f'Không cập nhật được luật kết hợp: {e}', 'error')
    return redirect(url_for('restaurant.dashboard'))


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