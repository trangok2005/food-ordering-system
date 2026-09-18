import time
import math
import json
from urllib.parse import urlparse

from flask import (
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    abort,
    jsonify,
)
from flask_login import login_required, current_user


from app.cart import cart_bp
from app.cart import dao
from app.cart import payos
from app.cart.service import PaymentAttemptStatus, PaymentService


@cart_bp.before_request
def _block_restaurant_ordering():
    """Tài khoản nhà hàng ko được đặt món."""
    if (
        current_user.is_authenticated
        and current_user.role
        and current_user.role.name == 'RESTAURANT'
    ):
        abort(403)


def _poll_payment_status(payment_request_id):
    """Poll trạng thái PayOS khi localhost ko nhận được webhook."""
    if not payment_request_id:
        return 'PENDING'

    if payos.PAYOS_MODE == 'live':
        tries, delay = 10, 1.0
    else:
        tries, delay = 3, 0.2

    try:
        client = payos.get_client()
    except Exception:
        return 'PENDING'

    for _ in range(tries):
        try:
            response = client.get_payment_request(
                payment_request_id
            )

            status = (
                response.get('status')
                if isinstance(response, dict)
                else None
            )

            if status in (
                'PAID',
                'FAILED',
                'CANCELLED',
                'EXPIRED',
            ):
                return status

        except Exception:
            # chưa có kết quả thì thử lại
            pass

        time.sleep(delay)

    return 'PENDING'


@cart_bp.route('/')
@login_required
def cart_view():
    try:
        carts = dao.get_user_carts(current_user.id)

    except Exception:
        flash(
            'Không thể tải giỏ hàng. Vui lòng thử lại sau.',
            'error'
        )
        carts = []

    return render_template(
        'cart.html',
        carts=carts
    )


@cart_bp.route('/checkout')
@login_required
def checkout_view():
    try:
        carts = dao.get_user_carts(current_user.id)

        total = sum(
            c.total_amount()
            for c in carts
        )

        issues = dao.validate_checkout(
            current_user.id
        )

    except Exception:
        flash(
            'Không thể kiểm tra giỏ hàng. Vui lòng thử lại sau.',
            'error'
        )

        carts = []
        total = 0
        issues = [
            'Không thể kiểm tra điều kiện thanh toán.'
        ]

    return render_template(
        'checkout.html',
        carts=carts,
        total=total,
        issues=issues
    )


@cart_bp.route('/create-payment', methods=['POST'])
@login_required
def create_payment():
    """Chỉ tạo đơn sau khi PayOS xác nhận PAID."""

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
        return redirect(url_for('cart.checkout_view'))

    if len(address) > 255 or len(note) > 255:
        flash('Địa chỉ và ghi chú chỉ được dài tối đa 255 ký tự.', 'error')
        return redirect(url_for('cart.checkout_view'))
    if not (phone.isdigit() and 10 <= len(phone) <= 11):
        flash('Số điện thoại phải từ 10 đến 11 ký số.', 'error')
        return redirect(url_for('cart.checkout_view'))
    if ((lat is None) != (lng is None) or
            (lat is not None and (not math.isfinite(lat) or not -90 <= lat <= 90)) or
            (lng is not None and (not math.isfinite(lng) or not -180 <= lng <= 180))):
        flash('Tọa độ GPS không hợp lệ.', 'error')
        return redirect(url_for('cart.checkout_view'))
    try:
        attempt = PaymentService().create_payment(
            current_user.id, address, phone, note, lat, lng
        )

    except KeyError:
        flash(
            'Thiếu cấu hình PayOS. Vui lòng kiểm tra file .env.',
            'error'
        )
        return redirect(
            url_for('cart.checkout_view')
        )

    except ValueError as e:
        flash(
            f'PayOS từ chối yêu cầu thanh toán: {e}',
            'error'
        )
        return redirect(
            url_for('cart.checkout_view')
        )

    except Exception:
        flash(
            'Không thể kết nối đến PayOS. '
            'Vui lòng thử lại sau.',
            'error'
        )
        return redirect(
            url_for('cart.checkout_view')
        )

    pending = json.loads(attempt.payload)
    pending['order_code'] = attempt.order_code
    pending['payment_request_id'] = attempt.payment_request_id

    session['pending_payment'] = pending
    session.modified = True

    return redirect(
        attempt.checkout_url
    )


@cart_bp.route('/mock-payos/<payment_id>')
@login_required
def mock_checkout_view(payment_id):
    """Trang PayOS giả lập cho môi trường local."""

    if payos.PAYOS_MODE == 'live':
        abort(404)

    payment = payos.MockPayOSClient.payments.get(
        str(payment_id)
    )

    if not payment:
        abort(404)
    if not dao.get_payment_attempt(payment_id, current_user.id):
        abort(404)

    return render_template(
        'cart/mock_payos.html',
        payment=payment
    )


@cart_bp.route(
    '/mock-payos/<payment_id>/pay',
    methods=['POST']
)
def mock_pay(payment_id):

    if payos.PAYOS_MODE == 'live':
        abort(404)

    payment = payos.MockPayOSClient.payments.get(
        str(payment_id)
    )

    if not payment:
        abort(404)
    if not current_user.is_authenticated or not dao.get_payment_attempt(
            payment_id, current_user.id):
        abort(403)

    payment['status'] = 'PAID'

    return_url = payment.get(
        'return_url'
    )

    if not return_url:
        abort(500)

    separator = (
        '&'
        if '?' in return_url
        else '?'
    )

    return redirect(
        f"{return_url}{separator}id={payment_id}"
    )


@cart_bp.route(
    '/mock-payos/<payment_id>/cancel',
    methods=['POST']
)
def mock_cancel(payment_id):

    if payos.PAYOS_MODE == 'live':
        abort(404)

    payment = payos.MockPayOSClient.payments.get(
        str(payment_id)
    )

    if not payment:
        abort(404)
    if not current_user.is_authenticated or not dao.get_payment_attempt(
            payment_id, current_user.id):
        abort(403)

    payment['status'] = 'CANCELLED'
    PaymentService().mark_terminal(
        payment_id, PaymentAttemptStatus.CANCELLED,
        user_id=current_user.id,
    )

    cancel_url = payment.get(
        'cancel_url'
    )

    if not cancel_url:
        abort(500)

    return redirect(
        cancel_url
    )


@cart_bp.route('/payment-return')
@login_required
def payment_return():
    """Thanh toán thành công thì tạo đơn và xóa giỏ."""

    payment_request_id = request.args.get(
        'id'
    )

    attempt = dao.get_payment_attempt(payment_request_id, current_user.id)
    pending = session.get('pending_payment')
    if attempt:
        pending = json.loads(attempt.payload)

    if not pending or not payment_request_id:
        flash(
            'Phiên thanh toán không tồn tại hoặc đã hết hạn.',
            'error'
        )
        return redirect(
            url_for('cart.cart_view')
        )

    saved_payment_request_id = pending.get(
        'payment_request_id'
    )

    if (
        saved_payment_request_id
        and str(saved_payment_request_id)
        != str(payment_request_id)
    ):
        flash(
            'Thông tin thanh toán không hợp lệ.',
            'error'
        )
        return redirect(
            url_for('cart.cart_view')
        )

    status = _poll_payment_status(
        payment_request_id
    )

    if status == 'PAID':
        try:
            orders = PaymentService().process_provider_status(
                payment_request_id, status, current_user.id
            )

        except ValueError as e:
            flash(
                str(e),
                'error'
            )
            return redirect(
                url_for('cart.cart_view')
            )

        except Exception:
            flash(
                'Thanh toán đã thành công nhưng '
                'không thể tạo đơn hàng. '
                'Vui lòng liên hệ quản trị viên.',
                'error'
            )
            return redirect(
                url_for('cart.cart_view')
            )

        session.pop(
            'pending_payment',
            None
        )
        session.modified = True

        return render_template(
            'payment_result.html',
            success=True,
            orders=orders,
            total=pending.get('total')
        )

    if status in ('FAILED', 'CANCELLED', 'EXPIRED') and attempt:
        PaymentService().process_provider_status(
            payment_request_id, status, current_user.id
        )

    if status == 'FAILED':
        flash(
            'Thanh toán thất bại. Vui lòng thử lại.',
            'error'
        )

    elif status == 'CANCELLED':
        flash(
            'Bạn đã hủy thanh toán.',
            'warning'
        )

    else:
        flash(
            'Thanh toán chưa được xác nhận. '
            'Vui lòng kiểm tra lại sau.',
            'warning'
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
    payment_request_id = request.args.get('id') or (pending or {}).get(
        'payment_request_id'
    )
    if payment_request_id:
        try:
            PaymentService().mark_terminal(
                payment_request_id, PaymentAttemptStatus.CANCELLED,
                user_id=current_user.id,
            )
        except ValueError:
            pass

    flash(
        'Bạn đã hủy thanh toán. '
        'Giỏ hàng của bạn vẫn được giữ nguyên.',
        'warning'
    )

    return render_template(
        'payment_result.html',
        success=False,
        status='CANCELLED',
        total=(pending or {}).get('total')
    )


@cart_bp.route('/webhook/payos', methods=['POST'])
def payment_webhook():
    """Webhook và return URL dùng chung bước hoàn tất đơn."""
    payload = request.get_json(silent=True) or {}
    if not payos.verify_webhook(payload):
        return jsonify({'success': False, 'message': 'Chữ ký không hợp lệ'}), 400
    try:
        PaymentService().handle_webhook(payload)
    except LookupError as exc:
        return jsonify({'success': False, 'message': str(exc)}), 404
    except ValueError as exc:
        return jsonify({'success': False, 'message': str(exc)}), 409
    return jsonify({'success': True}), 200


@cart_bp.route('/my-orders')
@login_required
def my_orders():
    try:
        pagination = dao.get_user_orders(
            current_user.id,
            page=max(request.args.get('page', 1, type=int), 1),
        )
        orders = pagination.items

    except Exception:
        flash(
            'Không thể tải danh sách đơn hàng.',
            'error'
        )
        orders = []
        pagination = None

    try:
        from app.ai import dao as ai_dao

        reviewed = ai_dao.get_reviewed_dish_ids_for_orders(
            [o.id for o in orders]
        )

    except Exception:
        reviewed = set()

    return render_template(
        'my_orders.html',
        orders=orders,
        reviewed=reviewed,
        pagination=pagination,
    )


@cart_bp.route('/api/stats')
@login_required
def cart_stats_api():

    try:
        stats = dao.get_cart_stats(
            current_user.id
        )

        return jsonify(
            stats
        )

    except Exception:
        return jsonify({
            'total_quantity': 0,
            'total_amount': 0,
            'error': 'Không thể tải thông tin giỏ hàng'
        }), 500


@cart_bp.route('/pairing-suggestions/<int:dish_id>')
@login_required
def pairing_suggestions(dish_id):
    try:
        dishes = dao.get_pairing_suggestions(current_user.id, dish_id)
    except ValueError as error:
        return jsonify({'error': str(error)}), 404

    return jsonify({
        'suggestions': [
            {
                'id': dish.id,
                'name': dish.name,
                'price': dish.price,
                'image': dish.image,
            }
            for dish in dishes
        ]
    })


@cart_bp.route('/add', methods=['POST'])
@login_required
def add_to_cart():
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    dish_id = request.form.get(
        'dish_id',
        type=int
    )

    quantity = request.form.get(
        'quantity',
        1,
        type=int
    )

    if not dish_id:
        if is_ajax:
            return jsonify({'error': 'Món ăn không hợp lệ.'}), 400
        flash(
            'Món ăn không hợp lệ.',
            'error'
        )
        return redirect(
            request.referrer
            or url_for('cart.cart_view')
        )

    if not quantity or quantity < 1:
        if is_ajax:
            return jsonify({'error': 'Số lượng món không hợp lệ.'}), 400
        flash(
            'Số lượng món không hợp lệ.',
            'error'
        )
        return redirect(
            request.referrer
            or url_for('cart.cart_view')
        )

    try:
        dao.add_to_cart(
            current_user.id,
            dish_id,
            quantity
        )

        if is_ajax:
            return jsonify({
                'message': 'Đã thêm vào giỏ hàng',
                'cart': dao.get_cart_stats(current_user.id),
            })

        flash(
            'Đã thêm vào giỏ hàng',
            'success'
        )

    except dao.CartRestaurantConflict as e:
        if is_ajax:
            return jsonify({'error': str(e)}), 409
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
        if is_ajax:
            return jsonify({'error': str(e)}), 400
        flash(
            str(e),
            'error'
        )

    except Exception:
        if is_ajax:
            return jsonify({
                'error': 'Không thể thêm món vào giỏ hàng. Vui lòng thử lại.'
            }), 500
        flash(
            'Không thể thêm món vào giỏ hàng. '
            'Vui lòng thử lại.',
            'error'
        )

    return redirect(
        request.referrer
        or url_for('cart.cart_view')
    )


@cart_bp.route('/confirm-switch', methods=['POST'])
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

    if not dish_id:
        flash(
            'Món ăn không hợp lệ.',
            'error'
        )
        return redirect(
            return_url
            or url_for('cart.cart_view')
        )

    if not quantity or quantity < 1:
        flash(
            'Số lượng món không hợp lệ.',
            'error'
        )
        return redirect(
            return_url
            or url_for('cart.cart_view')
        )

    try:
        dao.switch_restaurant_cart(
            current_user.id,
            dish_id,
            quantity
        )

        flash(
            'Đã xóa giỏ cũ và thêm món mới',
            'success'
        )

    except ValueError as e:
        flash(
            str(e),
            'error'
        )

    except Exception:
        flash(
            'Không thể chuyển sang nhà hàng mới. '
            'Vui lòng thử lại.',
            'error'
        )

    return redirect(
        return_url
        or url_for('cart.cart_view')
    )


@cart_bp.route('/update', methods=['POST'])
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

    if not item_id:
        flash(
            'Sản phẩm không hợp lệ.',
            'error'
        )
        return redirect(
            url_for('cart.cart_view')
        )

    try:
        dao.update_cart_item(
            current_user.id,
            item_id,
            quantity
        )

        flash(
            'Đã cập nhật giỏ hàng',
            'success'
        )

    except ValueError as e:
        flash(
            str(e),
            'error'
        )

    except Exception:
        flash(
            'Không thể cập nhật giỏ hàng.',
            'error'
        )

    return redirect(
        url_for('cart.cart_view')
    )


@cart_bp.route('/remove', methods=['POST'])
@login_required
def remove_cart_item():
    item_id = request.form.get(
        'item_id',
        type=int
    )

    if not item_id:
        flash(
            'Sản phẩm không hợp lệ.',
            'error'
        )
        return redirect(
            url_for('cart.cart_view')
        )

    try:
        dao.remove_cart_item(
            current_user.id,
            item_id
        )

        flash(
            'Đã xóa khỏi giỏ hàng',
            'success'
        )

    except ValueError as e:
        flash(
            str(e),
            'error'
        )

    except Exception:
        flash(
            'Không thể xóa sản phẩm khỏi giỏ hàng.',
            'error'
        )

    return redirect(
        url_for('cart.cart_view')
    )


@cart_bp.route('/clear', methods=['POST'])
@login_required
def clear_cart():
    cart_id = request.form.get(
        'cart_id',
        type=int
    )

    if not cart_id:
        flash(
            'Giỏ hàng không hợp lệ.',
            'error'
        )
        return redirect(
            url_for('cart.cart_view')
        )

    try:
        dao.clear_cart(
            current_user.id,
            cart_id
        )

        flash(
            'Đã xóa toàn bộ giỏ hàng',
            'success'
        )

    except ValueError as e:
        flash(
            str(e),
            'error'
        )

    except Exception:
        flash(
            'Không thể xóa giỏ hàng.',
            'error'
        )

    return redirect(
        url_for('cart.cart_view')
    )
