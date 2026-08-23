import secrets
import time

from flask import (
    render_template,
    request,
    redirect,
    url_for,
    flash,
<<<<<<< Updated upstream
    session
)

from flask_login import (
    login_required,
    current_user
)

=======
    session,
    abort,
    jsonify
)
from flask_login import login_required, current_user

>>>>>>> Stashed changes
from app.cart import cart_bp
from app.cart import dao
from app.cart import payos


<<<<<<< Updated upstream
=======
@cart_bp.before_request
def _block_restaurant_ordering():
    """
    Tài khoản nhà hàng (RESTAURANT) chỉ quản lý đơn,
    KHÔNG được thao tác giỏ hàng / thanh toán như khách hàng.
    """

    if (
        current_user.is_authenticated
        and current_user.role
        and current_user.role.name == 'RESTAURANT'
    ):
        abort(403)


>>>>>>> Stashed changes
def _gen_order_code():
    """
    Sinh mã orderCode dùng cho PayOS.

    PayOS yêu cầu orderCode là số nguyên.
    """

    return secrets.randbelow(900000000) + 100000000


def _app_url(path):
    """
    Chuyển path thành URL đầy đủ dựa trên host hiện tại.
    """

    return request.host_url.rstrip('/') + path


<<<<<<< Updated upstream
def _poll_payment_status(
    payment_request_id,
    tries=10,
    delay=1.0
):
    """
    Kiểm tra trạng thái PayOS nhiều lần.
    Dùng polling thay cho webhook khi chạy localhost.
    """

=======
def _poll_payment_status(payment_request_id, tries=10, delay=1.0):
    """
    Kiểm tra trạng thái PayOS nhiều lần.

    Dùng polling thay cho webhook khi chạy localhost.
    """

    if not payment_request_id:
        return 'PENDING'

>>>>>>> Stashed changes
    client = payos.get_client()

    for _ in range(tries):
        try:
<<<<<<< Updated upstream
            status = (
                client
                .get_payment_request(payment_request_id)
                .get('status')
            )

=======
            response = client.get_payment_request(
                payment_request_id
            )

            status = response.get('status')

>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
    carts = dao.get_user_carts(
        current_user.id
    )
=======
    carts = dao.get_user_carts(current_user.id)
>>>>>>> Stashed changes

    return render_template(
        'cart.html',
        carts=carts
    )


@cart_bp.route('/checkout')
@login_required
def checkout_view():
<<<<<<< Updated upstream
    carts = dao.get_user_carts(
        current_user.id
    )
=======
    carts = dao.get_user_carts(current_user.id)
>>>>>>> Stashed changes

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
<<<<<<< Updated upstream
=======

    # Nếu có lat/lng thì phải có đủ cả hai
    if (
        (lat is None and lng is not None)
        or
        (lat is not None and lng is None)
    ):
        flash(
            'Tọa độ giao hàng không hợp lệ',
            'error'
        )

        return redirect(
            url_for('cart.checkout_view')
        )

    # Kiểm tra phạm vi GPS hợp lệ
    if lat is not None and lng is not None:
        if not (-90 <= lat <= 90):
            flash(
                'Vĩ độ không hợp lệ',
                'error'
            )

            return redirect(
                url_for('cart.checkout_view')
            )

        if not (-180 <= lng <= 180):
            flash(
                'Kinh độ không hợp lệ',
                'error'
            )

            return redirect(
                url_for('cart.checkout_view')
            )
>>>>>>> Stashed changes

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
<<<<<<< Updated upstream
=======

    except Exception:
        flash(
            'Có lỗi xảy ra khi kiểm tra giỏ hàng, vui lòng thử lại sau',
            'error'
        )

        return redirect(
            url_for('cart.checkout_view')
        )
>>>>>>> Stashed changes

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
<<<<<<< Updated upstream
=======

    # Kiểm tra PayOS trả về payment link hợp lệ
    if not link:
        flash(
            'PayOS không trả về thông tin thanh toán',
            'error'
        )

        return redirect(
            url_for('cart.checkout_view')
        )

    if not link.get('id'):
        flash(
            'PayOS không trả về mã thanh toán',
            'error'
        )

        return redirect(
            url_for('cart.checkout_view')
        )

    if not link.get('checkoutUrl'):
        flash(
            'PayOS không trả về đường dẫn thanh toán',
            'error'
        )

        return redirect(
            url_for('cart.checkout_view')
        )
>>>>>>> Stashed changes

    pending.update({
        'order_code': code,
        'payment_request_id': link.get('id'),
        'address': address,
        'phone': phone,
        'note': note,
        'lat': lat,
        'lng': lng,
    })
<<<<<<< Updated upstream

    session['pending_payment'] = pending

=======

    session['pending_payment'] = pending
    session.modified = True

>>>>>>> Stashed changes
    return redirect(
        link['checkoutUrl']
    )


@cart_bp.route('/payment-return')
@login_required
def payment_return():
    """
    PayOS chuyển trình duyệt về đây sau thanh toán.
<<<<<<< Updated upstream

    Kiểm tra trạng thái:
    PAID -> tạo Order -> xóa Cart.
    """

    payment_request_id = request.args.get(
        'id'
    )

=======
    PAID:
        tạo Order
        -> xóa Cart
    Không tạo Order nếu chưa PAID.
    """

    payment_request_id = request.args.get('id')
>>>>>>> Stashed changes
    pending = session.get(
        'pending_payment'
    )

    if not pending or not payment_request_id:
        return redirect(
            url_for('cart.cart_view')
        )

<<<<<<< Updated upstream
=======
    if (
        pending.get('payment_request_id')
        != payment_request_id
    ):
        flash(
            'Thông tin thanh toán không hợp lệ',
            'error'
        )

        return redirect(
            url_for('cart.cart_view')
        )

>>>>>>> Stashed changes
    status = _poll_payment_status(
        payment_request_id
    )

    if status == 'PAID':
        try:
            orders = dao.create_orders_from_pending(
                current_user.id,
                pending
            )
<<<<<<< Updated upstream

        except Exception as e:
            flash(
                f'Thanh toán thành công nhưng lỗi tạo đơn: {e}',
                'error'
            )

            return redirect(
                url_for('cart.cart_view')
            )

=======

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
                'Thanh toán thành công nhưng lỗi tạo đơn, vui lòng liên hệ hỗ trợ',
                'error'
            )

            return redirect(
                url_for('cart.cart_view')
            )

>>>>>>> Stashed changes
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

<<<<<<< Updated upstream
    return render_template(
        'my_orders.html',
        orders=orders
    )


@cart_bp.route(
    '/add',
    methods=['POST']
)
=======
    from app.ai import dao as ai_dao

    reviewed = ai_dao.get_reviewed_dish_ids_for_orders(
        [o.id for o in orders]
    )

    return render_template(
        'my_orders.html',
        orders=orders,
        reviewed=reviewed
    )


@cart_bp.route('/api/stats')
@login_required
def cart_stats_api():
    """
    Trả về số lượng món trong giỏ hàng
    của user để hiển thị header badge.
    """

    stats = dao.get_cart_stats(
        current_user.id
    )

    return jsonify(stats)


@cart_bp.route('/add', methods=['POST'])
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
=======

    if not dish_id:
        flash(
            'Món ăn không hợp lệ',
            'error'
        )

        return redirect(
            request.referrer
            or url_for('cart.cart_view')
        )

    if not quantity or quantity < 1:
        flash(
            'Số lượng không hợp lệ',
            'error'
        )

        return redirect(
            request.referrer
            or url_for('cart.cart_view')
        )
>>>>>>> Stashed changes

    try:
        dao.add_to_cart(
            current_user.id,
            dish_id,
            quantity
        )

        flash(
            'Đã thêm vào giỏ hàng'
        )

<<<<<<< Updated upstream
    except ValueError as e:
        flash(
            str(e),
            'error'
        )

=======
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

    except Exception:
        flash(
            'Có lỗi xảy ra khi thêm món vào giỏ hàng',
            'error'
        )

>>>>>>> Stashed changes
    return redirect(
        request.referrer
        or url_for('cart.cart_view')
    )


<<<<<<< Updated upstream
@cart_bp.route(
    '/update',
    methods=['POST']
)
=======
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

    if not dish_id:
        flash(
            'Món ăn không hợp lệ',
            'error'
        )

        return redirect(
            url_for('cart.cart_view')
        )

    if not quantity or quantity < 1:
        flash(
            'Số lượng không hợp lệ',
            'error'
        )

        return redirect(
            url_for('cart.cart_view')
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

    except Exception:
        flash(
            'Có lỗi xảy ra khi chuyển giỏ hàng',
            'error'
        )

    return redirect(
        return_url
        or url_for('cart.cart_view')
    )


@cart_bp.route('/update', methods=['POST'])
>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
=======

    if not item_id:
        flash(
            'Sản phẩm không hợp lệ',
            'error'
        )

        return redirect(
            url_for('cart.cart_view')
        )

    if not quantity or quantity < 1:
        flash(
            'Số lượng không hợp lệ',
            'error'
        )

        return redirect(
            url_for('cart.cart_view')
        )
>>>>>>> Stashed changes

    try:
        dao.update_cart_item(
            current_user.id,
            item_id,
            quantity
        )
<<<<<<< Updated upstream

        flash(
            'Đã cập nhật giỏ hàng'
        )

    except ValueError as e:
        flash(
            str(e),
            'error'
        )

=======

        flash(
            'Đã cập nhật giỏ hàng'
        )

    except ValueError as e:
        flash(
            str(e),
            'error'
        )

    except Exception:
        flash(
            'Có lỗi xảy ra khi cập nhật giỏ hàng',
            'error'
        )

>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
=======

    if not item_id:
        flash(
            'Sản phẩm không hợp lệ',
            'error'
        )

        return redirect(
            url_for('cart.cart_view')
        )
>>>>>>> Stashed changes

    try:
        dao.remove_cart_item(
            current_user.id,
            item_id
        )
<<<<<<< Updated upstream

        flash(
            'Đã xóa khỏi giỏ hàng'
        )

    except ValueError as e:
        flash(
            str(e),
            'error'
        )

=======

        flash(
            'Đã xóa khỏi giỏ hàng'
        )

    except ValueError as e:
        flash(
            str(e),
            'error'
        )

    except Exception:
        flash(
            'Có lỗi xảy ra khi xóa sản phẩm',
            'error'
        )

>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
=======

    if not cart_id:
        flash(
            'Giỏ hàng không hợp lệ',
            'error'
        )

        return redirect(
            url_for('cart.cart_view')
        )
>>>>>>> Stashed changes

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

<<<<<<< Updated upstream
=======
    except Exception:
        flash(
            'Có lỗi xảy ra khi xóa giỏ hàng',
            'error'
        )

>>>>>>> Stashed changes
    return redirect(
        url_for('cart.cart_view')
    )