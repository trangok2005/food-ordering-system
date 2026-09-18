import pytest

from app import db
from app.cart import dao as cart_dao
from sqlalchemy.exc import IntegrityError

from app.models import (Cart, Order, OrderStatus, PaymentAttempt, PaymentStatus)
from app.cart.service import PaymentAttemptStatus, PaymentService
from app.test.test_base import (app, client, test_session,
                                make_restaurant_owner, make_restaurant,
                                make_customer, make_dish, login)


def _setup_cart(customer_id=None, quantity=2):
    owner = make_restaurant_owner()
    restaurant = make_restaurant(owner)
    dish = make_dish(restaurant, name='Cá hồi Sashimi', price=120000)
    customer = make_customer()
    db.session.commit()
    cart_dao.add_to_cart(customer.id, dish.id, quantity=quantity)
    return restaurant, customer, dish



def test_build_checkout_payload_empty_cart(app):
    customer = make_customer()
    db.session.commit()

    with pytest.raises(ValueError):
        cart_dao.build_checkout_payload(customer.id)


def test_build_checkout_payload_success(app):
    restaurant, customer, dish = _setup_cart()

    pending = cart_dao.build_checkout_payload(customer.id)

    assert len(pending['carts']) == 1
    cart_data = pending['carts'][0]
    assert cart_data['restaurant_id'] == restaurant.id
    assert cart_data['items'][0]['dish_id'] == dish.id
    assert cart_data['items'][0]['quantity'] == 2
    assert cart_data['items'][0]['unit_price'] == 120000
    assert pending['total'] == 240000


def test_build_checkout_payload_restaurant_closed(app):
    restaurant, customer, _ = _setup_cart()
    restaurant.is_open = False
    db.session.commit()

    with pytest.raises(ValueError) as exc:
        cart_dao.build_checkout_payload(customer.id)
    assert 'đóng cửa' in str(exc.value)


def test_build_checkout_payload_min_order(app):
    restaurant, customer, _ = _setup_cart()
    restaurant.min_order_amount = 500000
    db.session.commit()

    with pytest.raises(ValueError) as exc:
        cart_dao.build_checkout_payload(customer.id)
    assert 'tối thiểu' in str(exc.value)


def test_build_checkout_payload_out_of_stock(app):
    _, customer, dish = _setup_cart()
    dish.is_available = False
    db.session.commit()

    with pytest.raises(ValueError) as exc:
        cart_dao.build_checkout_payload(customer.id)
    assert 'hết hàng' in str(exc.value)


def test_build_checkout_payload_outside_radius(app):
    restaurant, customer, _ = _setup_cart()
    restaurant.latitude = 10.7769
    restaurant.longitude = 106.7009
    restaurant.delivery_radius_km = 2
    db.session.commit()

    with pytest.raises(ValueError) as exc:
        cart_dao.build_checkout_payload(customer.id, lat=10.83, lng=106.73)
    assert 'ngoài bán kính' in str(exc.value)



def test_create_orders_creates_and_clears_cart(app):
    _, customer, dish = _setup_cart()
    pending = cart_dao.build_checkout_payload(customer.id)
    pending.update({
        'address': '123 Nguyễn Huệ',
        'phone': '0901234567',
    })

    orders = cart_dao.create_orders_from_pending(customer.id, pending)

    assert len(orders) == 1
    order = orders[0]
    assert order.status == OrderStatus.PENDING
    assert order.payment_status == PaymentStatus.PAID
    assert order.total_amount == 240000
    assert order.delivery_address == '123 Nguyễn Huệ'
    assert order.phone == '0901234567'
    assert order.order_details[0].dish_id == dish.id
    assert order.order_details[0].unit_price == 120000

    assert cart_dao.get_user_carts(customer.id) == []


def test_create_orders_multi_cart_one_order_each(app):
    owner = make_restaurant_owner()
    rest_a = make_restaurant(owner)
    owner_b = make_restaurant_owner('B')
    rest_b = make_restaurant(owner_b)
    customer = make_customer()
    dish_a = make_dish(rest_a, name='Món A', price=10000)
    dish_b = make_dish(rest_b, name='Món B', price=20000)
    db.session.commit()

    pending = {
        'carts': [
            {'restaurant_id': rest_a.id, 'items': [
                {'dish_id': dish_a.id, 'quantity': 1, 'unit_price': 10000}],
             'total': 10000},
            {'restaurant_id': rest_b.id, 'items': [
                {'dish_id': dish_b.id, 'quantity': 1, 'unit_price': 20000}],
             'total': 20000},
        ],
        'address': 'HCM',
        'phone': '0901234567',
    }

    orders = cart_dao.create_orders_from_pending(customer.id, pending)

    assert len(orders) == 2
    assert {o.restaurant_id for o in orders} == {rest_a.id, rest_b.id}
    assert sum(o.total_amount for o in orders) == 30000


def test_get_user_orders(app):
    _, customer, _ = _setup_cart()
    pending = cart_dao.build_checkout_payload(customer.id)
    pending.update({'address': 'HCM', 'phone': '0901234567'})
    cart_dao.create_orders_from_pending(customer.id, pending)

    orders = cart_dao.get_user_orders(customer.id)
    assert len(orders) == 1



def test_checkout_requires_login(client, app):
    assert client.get('/cart/checkout').status_code == 302


def test_checkout_view_success(client, app):
    _, customer, _ = _setup_cart()
    login(client, username='customer')

    res = client.get('/cart/checkout')
    assert res.status_code == 200
    assert 'Cá hồi Sashimi'.encode('utf-8') in res.data


def test_checkout_view_shows_issues(client, app):
    restaurant, customer, _ = _setup_cart()
    restaurant.is_open = False
    db.session.commit()
    login(client, username='customer')

    res = client.get('/cart/checkout')
    assert res.status_code == 200
    assert 'đóng cửa'.encode('utf-8') in res.data



class FakePayOS:
    def create_payment_link(self, amount, description, reference, return_url, cancel_url):
        return {'id': 'payos_123', 'checkoutUrl': 'https://payos.test/checkout'}

    def get_payment_request(self, payment_request_id):
        return {'status': 'PAID'}


def test_create_payment_requires_login(client, app):
    assert client.post('/cart/create-payment').status_code == 302


def test_create_payment_requires_address_phone(client, app, monkeypatch):
    _, customer, _ = _setup_cart()
    login(client, username='customer')
    monkeypatch.setattr('app.cart.payos.get_client', lambda: FakePayOS())

    res = client.post('/cart/create-payment', data={'address': '', 'phone': ''})
    assert res.status_code == 302
    assert res.headers['Location'].endswith('/cart/checkout')


def test_create_payment_empty_address_with_valid_phone_returns_before_provider(
        client, app, monkeypatch):
    _, _, _ = _setup_cart()
    login(client, username='customer')
    called = False

    def get_client():
        nonlocal called
        called = True
        return FakePayOS()

    monkeypatch.setattr('app.cart.payos.get_client', get_client)
    res = client.post('/cart/create-payment', data={
        'address': '', 'phone': '0901234567',
    })

    assert res.status_code == 302
    assert res.headers['Location'].endswith('/cart/checkout')
    assert called is False
    assert PaymentAttempt.query.count() == 0


def test_create_payment_redirects_to_payos(client, app, monkeypatch):
    _, customer, _ = _setup_cart()
    login(client, username='customer')
    monkeypatch.setattr('app.cart.payos.get_client', lambda: FakePayOS())

    res = client.post('/cart/create-payment', data={
        'address': '123 Nguyễn Huệ',
        'phone': '0901234567',
    })

    assert res.status_code == 302
    assert res.headers['Location'] == 'https://payos.test/checkout'


def test_create_payment_accepts_live_payos_response_shape(app):
    _, customer, _ = _setup_cart()

    class LiveResponseProvider:
        def create_payment_link(self, **kwargs):
            return {
                'paymentLinkId': 'live_payment_link_id',
                'checkoutUrl': 'https://pay.payos.vn/web/live_payment_link_id',
            }

    attempt = PaymentService().create_payment(
        customer.id,
        '123 Nguyen Hue',
        '0901234567',
        client=LiveResponseProvider(),
    )

    assert attempt.status == PaymentAttemptStatus.CREATED
    assert attempt.payment_request_id == 'live_payment_link_id'
    assert attempt.checkout_url == 'https://pay.payos.vn/web/live_payment_link_id'


def test_provider_error_is_persisted_on_local_attempt(app):
    _, customer, _ = _setup_cart()

    class BrokenProvider:
        def create_payment_link(self, **kwargs):
            assert PaymentAttempt.query.one().status == PaymentAttemptStatus.CREATING
            raise ValueError('provider unavailable')

    with pytest.raises(ValueError, match='provider unavailable'):
        PaymentService().create_payment(
            customer.id, '123 Nguyen Hue', '0901234567',
            client=BrokenProvider(),
        )

    attempt = PaymentAttempt.query.one()
    assert attempt.status == PaymentAttemptStatus.FAILED
    assert attempt.error_code == 'PROVIDER_ERROR'
    assert 'provider unavailable' in attempt.last_error


def test_provider_success_is_recovered_after_commit_failure(app, monkeypatch):
    _, customer, _ = _setup_cart()
    original_commit = db.session.commit
    commit_calls = 0

    def flaky_commit():
        nonlocal commit_calls
        commit_calls += 1
        if commit_calls == 2:
            raise RuntimeError('transient database failure')
        return original_commit()

    monkeypatch.setattr(db.session, 'commit', flaky_commit)
    attempt = PaymentService().create_payment(
        customer.id, '123 Nguyen Hue', '0901234567', client=FakePayOS()
    )

    assert commit_calls == 3
    assert attempt.status == PaymentAttemptStatus.CREATED
    assert attempt.payment_request_id == 'payos_123'
    assert attempt.checkout_url == 'https://payos.test/checkout'


def test_same_snapshot_reuses_created_attempt_without_second_provider_call(app):
    _, customer, _ = _setup_cart()

    class CountingProvider:
        calls = 0

        def create_payment_link(self, **kwargs):
            self.calls += 1
            return {
                'id': 'pay_reuse',
                'checkoutUrl': 'https://payos.test/reuse',
            }

    provider = CountingProvider()
    first = PaymentService().create_payment(
        customer.id, '123 Nguyen Hue', '0901234567', client=provider
    )
    second = PaymentService().create_payment(
        customer.id, '123 Nguyen Hue', '0901234567', client=provider
    )

    assert first.id == second.id
    assert provider.calls == 1
    assert PaymentAttempt.query.count() == 1


def test_payment_callbacks_use_configured_base_url(app):
    _, customer, _ = _setup_cart()
    app.config['APP_BASE_URL'] = 'https://orders.example.test'

    class CapturingProvider:
        kwargs = None

        def create_payment_link(self, **kwargs):
            self.kwargs = kwargs
            return {'id': 'pay_urls', 'checkoutUrl': 'https://payos.test/url'}

    provider = CapturingProvider()
    PaymentService().create_payment(
        customer.id, '123 Nguyen Hue', '0901234567', client=provider
    )

    assert provider.kwargs['return_url'].startswith('https://orders.example.test/')
    assert provider.kwargs['cancel_url'].startswith('https://orders.example.test/')


def test_payment_callbacks_use_local_request_origin_when_base_url_is_empty(app):
    _, customer, _ = _setup_cart()
    app.config['APP_BASE_URL'] = ''

    class CapturingProvider:
        kwargs = None

        def create_payment_link(self, **kwargs):
            self.kwargs = kwargs
            return {'id': 'pay_local_url', 'checkoutUrl': 'https://payos.test/url'}

    provider = CapturingProvider()
    with app.test_request_context(base_url='http://127.0.0.1:5000'):
        PaymentService().create_payment(
            customer.id, '123 Nguyen Hue', '0901234567', client=provider
        )

    assert provider.kwargs['return_url'].startswith('http://127.0.0.1:5000/')
    assert provider.kwargs['cancel_url'].startswith('http://127.0.0.1:5000/')


def test_modified_cart_survives_old_payment_finalization(app):
    _, customer, _ = _setup_cart()
    pending = cart_dao.build_checkout_payload(customer.id)
    pending.update({
        'order_code': 223456789,
        'payment_request_id': 'pay_modified_cart',
        'address': '123 Nguyen Hue',
        'phone': '0901234567',
    })
    cart_dao.save_payment_attempt(customer.id, pending)
    cart = cart_dao.get_user_carts(customer.id)[0]
    cart.items[0].quantity = 3
    db.session.commit()

    orders = cart_dao.finalize_payment_attempt(
        'pay_modified_cart', customer.id
    )

    assert len(orders) == 1
    surviving = cart_dao.get_user_carts(customer.id)
    assert len(surviving) == 1
    assert surviving[0].items[0].quantity == 3


def test_finalize_failed_can_be_retried(app, monkeypatch):
    _, customer, _ = _setup_cart()
    pending = cart_dao.build_checkout_payload(customer.id)
    pending.update({
        'order_code': 323456789,
        'payment_request_id': 'pay_retry_finalize',
        'address': '123 Nguyen Hue',
        'phone': '0901234567',
    })
    attempt = cart_dao.save_payment_attempt(customer.id, pending)
    original = cart_dao.create_orders_from_pending
    calls = 0

    def transient_failure(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ValueError('temporary database failure')
        return original(*args, **kwargs)

    monkeypatch.setattr(cart_dao, 'create_orders_from_pending', transient_failure)
    service = PaymentService()
    with pytest.raises(ValueError, match='temporary database failure'):
        service.finalize('pay_retry_finalize', customer.id, assume_paid=True)

    db.session.refresh(attempt)
    assert attempt.status == PaymentAttemptStatus.FINALIZE_FAILED
    assert attempt.retry_count == 1
    assert 'temporary database failure' in attempt.last_error

    orders = service.finalize(
        'pay_retry_finalize', customer.id, assume_paid=True
    )
    assert len(orders) == 1
    assert PaymentAttempt.query.one().status == PaymentAttemptStatus.FINALIZED


def test_database_enforces_single_cart_per_user(app):
    restaurant, customer, _ = _setup_cart()
    second_owner = make_restaurant_owner('second')
    second_restaurant = make_restaurant(second_owner)
    db.session.add(Cart(
        user_id=customer.id,
        restaurant_id=second_restaurant.id,
    ))

    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()
    assert Cart.query.filter_by(user_id=customer.id).count() == 1


def test_payment_return_paid_creates_orders(client, app, monkeypatch):
    _, customer, _ = _setup_cart()
    login(client, username='customer')
    monkeypatch.setattr('app.cart.payos.get_client', lambda: FakePayOS())

    client.post('/cart/create-payment', data={
        'address': '123 Nguyễn Huệ',
        'phone': '0901234567',
    })

    with client.session_transaction() as sess:
        assert 'pending_payment' in sess
        payment_request_id = sess['pending_payment']['payment_request_id']

    res = client.get(f'/cart/payment-return?id={payment_request_id}')

    assert res.status_code == 200
    assert 'thành công'.encode('utf-8') in res.data
    assert Order.query.count() == 1
    assert cart_dao.get_user_carts(customer_id()) == []


def customer_id():
    from app.auth import dao as auth_dao
    return auth_dao.get_user_by_username('customer').id


def test_payment_return_no_pending(client, app, monkeypatch):
    _, customer, _ = _setup_cart()
    login(client, username='customer')
    monkeypatch.setattr('app.cart.payos.get_client', lambda: FakePayOS())

    res = client.get('/cart/payment-return?id=payos_123')
    assert res.status_code == 302
    assert res.headers['Location'].endswith('/cart/')


def test_payment_cancel_page(client, app):
    _, customer, _ = _setup_cart()
    login(client, username='customer')

    with client.session_transaction() as sess:
        sess['pending_payment'] = {'total': 240000}

    res = client.get('/cart/payment-cancel')
    assert res.status_code == 200
    assert 'không thành công'.encode('utf-8') in res.data
