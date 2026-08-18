import pytest

from app import db
from app.cart import dao as cart_dao
from app.models import (Order, OrderStatus, PaymentStatus)
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


# ---------------- DAO: build_checkout_payload ----------------

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


# ---------------- DAO: create_orders_from_pending ----------------

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


# ---------------- ROUTER: /cart/checkout ----------------

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


# ---------------- ROUTER: tạo payment ----------------

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