import secrets
import time
from urllib.parse import urlparse

from flask import render_template, request, redirect, url_for, flash, session, abort, jsonify
from flask_login import login_required, current_user


from app.cart import cart_bp
from app.cart import dao
from app.cart import payos


@cart_bp.before_request
def _block_restaurant_ordering():
    """Tài khoản nhà hàng (RESTAURANT) chỉ quản lý đơn, KHÔNG được
    thao tác giỏ hàng / thanh toán như khách hàng."""
    if current_user.is_authenticated and current_user.role.name == 'RESTAURANT':
        abort(403)


def _gen_order_code():
    return secrets.randbelow(900000000) + 100000000


def _app_url(path):
    return request.host_url.rstrip('/') + path


def _poll_payment_status(
    payment_request_id,
    tries=10,
    delay=1.0
):
    """
    Kiểm tra trạng thái PayOS nhiều lần.
    Dùng polling thay cho webhook khi chạy localhost.
    """

    client = payos.get_client()

    for _ in range(tries):
        try:
            status = (
                client
                .get_payment_request(payment_request_id)
                .get('status')
            )

            if status in (
                'PAID',
                'FAILED',
                'CANCELLED'
            ):
                return status

        except Exception:
            pass

        time.sleep(delay)

    return 'PENDING'


@cart_bp.route('/')
@login_required
def cart_view():
    carts = dao.get_user_carts(
        current_user.id
    )

    return render_template(
        'cart.html',
        carts=carts
    )


@cart_bp.route('/checkout')
@login_required
def checkout_view():
    carts = dao.get_user_carts(
        current_user.id
    )

    total = sum(
        c.total_amount()
        for c in carts
    )

    issues = dao.validate_checkout(
        current_user.id
    )

    return render_template(
        'checkout.html',
        carts=carts,
        total=total,
        issues=issues
    )


@cart_bp.route(
    '/create-payment',
    methods=['POST']
)
@login_required
def create_payment():
    """
    Tạo payment link PayOS.
    Không tạo Order ở bước này.
    Order chỉ được tạo sau khi PayOS xác nhận PAID.
    """

    address = request.form.get(
        'address',
        ''
    ).strip()

    phone = request.form.get(
        'phone',
        ''
    ).strip()

    note = request.form.get(
        'note',
        ''
    ).strip()

    lat = request.form.get(
        'lat',
        type=float
    )

    lng = request.form.get(
        'lng',
        type=float
    )

    if not address or not phone:
        flash(
            'Vui lòng nhập địa chỉ và số điện thoại nhận hàng',
            'error'
        )

        return redirect(
            url_for('cart.checkout_view')
        )

    try:
        pending = dao.build_checkout_payload(
            current_user.id,
            lat=lat,
            lng=lng
        )

    except ValueError as e:
        flash(
            str(e),
            'error'
        )

        return redirect(
            url_for('cart.checkout_view')
        )

    code = _gen_order_code()

    try:
        link = (
            payos
            .get_client()
            .create_payment_link(
                amount=pending['total'],
                description=f'Food Ordering #{code}',
                reference=code,
                return_url=_app_url(
                    url_for('cart.payment_return')
                ),
                cancel_url=_app_url(
                    url_for('cart.payment_cancel')
                ),
            )
        )

    except Exception as e:
        flash(
            f'Không tạo được link thanh toán: {e}',
            'error'
        )

        return redirect(
            url_for('cart.checkout_view')
        )

    pending.update({
        'order_code': code,
        'payment_request_id': link.get('id'),
        'address': address,
        'phone': phone,
        'note': note,
        'lat': lat,
        'lng': lng,
    })

    session['pending_payment'] = pending

    return redirect(
        link['checkoutUrl']
    )


@cart_bp.route('/payment-return')
@login_required
def payment_return():
    """
    PayOS chuyển trình duyệt về đây sau thanh toán.

    Kiểm tra trạng thái:
    PAID -> tạo Order -> xóa Cart.
    """

    payment_request_id = request.args.get(
        'id'
    )

    pending = session.get(
        'pending_payment'
    )

    if not pending or not payment_request_id:
        return redirect(
            url_for('cart.cart_view')
        )

    status = _poll_payment_status(
        payment_request_id
    )

    if status == 'PAID':
        try:
            orders = dao.create_orders_from_pending(
                current_user.id,
                pending
            )

        except Exception as e:
            flash(
                f'Thanh toán thành công nhưng lỗi tạo đơn: {e}',
                'error'
            )

            return redirect(
                url_for('cart.cart_view')
            )

        session.pop(
            'pending_payment',
            None
        )

        return render_template(
            'payment_result.html',
            success=True,
            orders=orders,
            total=pending.get('total')
        )

    return render_template(
        'payment_result.html',
        success=False,
        status=status,
        total=pending.get('total')
    )


@cart_bp.route('/payment-cancel')
@login_required
def payment_cancel():
    pending = session.get(
        'pending_payment'
    )

    return render_template(
        'payment_result.html',
        success=False,
        status='CANCELLED',
        total=(pending or {}).get('total')
    )


@cart_bp.route('/my-orders')
@login_required
def my_orders():
    orders = dao.get_user_orders(
        current_user.id
    )

    return render_template(
        'my_orders.html',
        orders=orders
    )


@cart_bp.route('/api/stats')
@login_required
def cart_stats_api():
    """Trả về số lượng món trong giỏ hàng của user (để header badge)."""
    stats = dao.get_cart_stats(
        current_user.id
    )

    return jsonify(
        stats
    )


@cart_bp.route(
    '/add',
    methods=['POST']
)
@login_required
def add_to_cart():
    dish_id = request.form.get(
        'dish_id',
        type=int
    )

    quantity = request.form.get(
        'quantity',
        1,
        type=int
    )

    try:
        dao.add_to_cart(
            current_user.id,
            dish_id,
            quantity
        )

        flash(
            'Đã thêm vào giỏ hàng'
        )

    except dao.CartRestaurantConflict as e:
        referrer = request.referrer
        return_path = (
            urlparse(referrer).path
            if referrer
            else None
        )

        return render_template(
            'cart_confirm.html',
            current_restaurant=e.current_restaurant,
            dish_id=dish_id,
            quantity=quantity,
            return_url=return_path
        )

    except ValueError as e:
        flash(
            str(e),
            'error'
        )

    return redirect(
        request.referrer
        or url_for('cart.cart_view')
    )


@cart_bp.route(
    '/confirm-switch',
    methods=['POST']
)
@login_required
def confirm_switch():
    dish_id = request.form.get(
        'dish_id',
        type=int
    )

    quantity = request.form.get(
        'quantity',
        1,
        type=int
    )

    return_url = request.form.get(
        'return_url'
    )

    if not (
        return_url
        and return_url.startswith('/')
        and not return_url.startswith('//')
    ):
        return_url = None

    try:
        dao.clear_all_carts(
            current_user.id
        )

        dao.add_to_cart(
            current_user.id,
            dish_id,
            quantity
        )

        flash(
            'Đã xóa giỏ cũ và thêm món mới'
        )

    except ValueError as e:
        flash(
            str(e),
            'error'
        )

    return redirect(
        return_url
        or url_for('cart.cart_view')
    )


@cart_bp.route(
    '/update',
    methods=['POST']
)
@login_required
def update_cart_item():
    item_id = request.form.get(
        'item_id',
        type=int
    )

    quantity = request.form.get(
        'quantity',
        type=int
    )

    try:
        dao.update_cart_item(
            current_user.id,
            item_id,
            quantity
        )

        flash(
            'Đã cập nhật giỏ hàng'
        )

    except ValueError as e:
        flash(
            str(e),
            'error'
        )

    return redirect(
        url_for('cart.cart_view')
    )


@cart_bp.route(
    '/remove',
    methods=['POST']
)
@login_required
def remove_cart_item():
    item_id = request.form.get(
        'item_id',
        type=int
    )

    try:
        dao.remove_cart_item(
            current_user.id,
            item_id
        )

        flash(
            'Đã xóa khỏi giỏ hàng'
        )

    except ValueError as e:
        flash(
            str(e),
            'error'
        )

    return redirect(
        url_for('cart.cart_view')
    )


@cart_bp.route(
    '/clear',
    methods=['POST']
)
@login_required
def clear_cart():
    cart_id = request.form.get(
        'cart_id',
        type=int
    )

    try:
        dao.clear_cart(
            current_user.id,
            cart_id
        )

        flash(
            'Đã xóa toàn bộ giỏ hàng'
        )

    except ValueError as e:
        flash(
            str(e),
            'error'
        )

    return redirect(
        url_for('cart.cart_view')
    )