import pytest
from datetime import datetime, timedelta

from app import db
from app.models import (User, UserRole, Restaurant, OrderStatus, PaymentStatus)
from app.restaurant import dao
from app.test.test_base import (app, client,
                                make_owner_and_restaurant, make_customer,
                                make_order, make_dish, login)


# ---------------- DAO ----------------

def test_get_restaurant_for_owner(app):
    owner, restaurant = make_owner_and_restaurant()
    db.session.commit()
    assert dao.get_restaurant_for_owner(owner.id).id == restaurant.id
    assert dao.get_restaurant_for_owner(99999) is None


def test_get_restaurant_orders_filter_by_status(app):
    owner, restaurant = make_owner_and_restaurant()
    customer = make_customer()
    pending = make_order(restaurant, customer)
    confirmed = make_order(restaurant, customer, OrderStatus.CONFIRMED)
    db.session.commit()

    assert {o.id for o in dao.get_restaurant_orders(restaurant.id)} == {pending.id, confirmed.id}
    assert [o.id for o in dao.get_restaurant_orders(restaurant.id, OrderStatus.PENDING)] == [pending.id]


def test_confirm_order_success(app):
    _, restaurant = make_owner_and_restaurant()
    customer = make_customer()
    order = make_order(restaurant, customer)
    db.session.commit()

    dao.confirm_order(order)

    assert order.status == OrderStatus.CONFIRMED
    assert order.confirmed_at is not None


def test_confirm_order_wrong_status(app):
    _, restaurant = make_owner_and_restaurant()
    customer = make_customer()
    order = make_order(restaurant, customer, OrderStatus.CONFIRMED)
    db.session.commit()

    with pytest.raises(ValueError):
        dao.confirm_order(order)


def test_confirm_order_expired(app):
    _, restaurant = make_owner_and_restaurant()
    customer = make_customer()
    order = make_order(restaurant, customer)
    order.confirm_deadline = datetime.now() - timedelta(minutes=1)
    db.session.commit()

    with pytest.raises(ValueError):
        dao.confirm_order(order)
    assert order.status == OrderStatus.EXPIRED


def test_expire_overdue_orders(app):
    _, restaurant = make_owner_and_restaurant()
    customer = make_customer()
    overdue = make_order(restaurant, customer)
    overdue.confirm_deadline = datetime.now() - timedelta(minutes=1)
    fresh = make_order(restaurant, customer)
    db.session.commit()

    expired = dao.expire_overdue_orders(restaurant.id)

    assert [o.id for o in expired] == [overdue.id]
    assert overdue.status == OrderStatus.EXPIRED
    assert fresh.status == OrderStatus.PENDING


def test_advance_order_flow(app):
    _, restaurant = make_owner_and_restaurant()
    customer = make_customer()
    order = make_order(restaurant, customer, OrderStatus.CONFIRMED)
    db.session.commit()

    dao.advance_order(order)
    assert order.status == OrderStatus.PREPARING
    dao.advance_order(order)
    assert order.status == OrderStatus.DELIVERING
    dao.advance_order(order)
    assert order.status == OrderStatus.COMPLETED


def test_advance_order_from_pending_fail(app):
    _, restaurant = make_owner_and_restaurant()
    customer = make_customer()
    order = make_order(restaurant, customer)
    db.session.commit()

    with pytest.raises(ValueError):
        dao.advance_order(order)


def test_cancel_order_success(app):
    _, restaurant = make_owner_and_restaurant()
    customer = make_customer()
    order = make_order(restaurant, customer)
    db.session.commit()

    dao.cancel_order(order, 'Het nguyen lieu')

    assert order.status == OrderStatus.CANCELLED
    assert order.cancel_reason == 'Het nguyen lieu'
    assert order.cancelled_at is not None


def test_cancel_order_requires_reason(app):
    _, restaurant = make_owner_and_restaurant()
    customer = make_customer()
    order = make_order(restaurant, customer)
    db.session.commit()

    with pytest.raises(ValueError):
        dao.cancel_order(order, '  ')


def test_cancel_order_completed_fail(app):
    _, restaurant = make_owner_and_restaurant()
    customer = make_customer()
    order = make_order(restaurant, customer, OrderStatus.COMPLETED)
    db.session.commit()

    with pytest.raises(ValueError):
        dao.cancel_order(order, 'ly do')


def test_mark_refunded_success(app):
    _, restaurant = make_owner_and_restaurant()
    customer = make_customer()
    order = make_order(restaurant, customer)
    db.session.commit()
    dao.cancel_order(order, 'ly do')

    dao.mark_refunded(order)

    assert order.payment_status == PaymentStatus.REFUNDED


def test_mark_refunded_non_cancelled_fail(app):
    _, restaurant = make_owner_and_restaurant()
    customer = make_customer()
    order = make_order(restaurant, customer)
    db.session.commit()

    with pytest.raises(ValueError):
        dao.mark_refunded(order)


# ---------------- ROUTER ----------------

def test_orders_view_requireslogin(client, app):
    res = client.get('/restaurant/orders')
    assert res.status_code == 302
    assert '/auth/login' in res.headers['Location']


def test_orders_view_forbidden_for_customer(client, app):
    make_owner_and_restaurant()
    make_customer()
    db.session.commit()
    login(client, username='customer')

    assert client.get('/restaurant/orders').status_code == 403


def test_orders_view_success(client, app):
    _, restaurant = make_owner_and_restaurant()
    customer = make_customer()
    make_order(restaurant, customer)
    db.session.commit()
    login(client)

    res = client.get('/restaurant/orders')

    assert res.status_code == 200
    assert 'Test Restaurant'.encode() in res.data
    assert b'order-1' in res.data


def test_orders_view_expires_overdue(client, app):
    _, restaurant = make_owner_and_restaurant()
    customer = make_customer()
    order = make_order(restaurant, customer)
    order.confirm_deadline = datetime.now() - timedelta(minutes=1)
    db.session.commit()
    login(client)

    client.get('/restaurant/orders')

    assert order.status == OrderStatus.EXPIRED


def test_confirm_order_route(client, app):
    _, restaurant = make_owner_and_restaurant()
    customer = make_customer()
    order = make_order(restaurant, customer)
    db.session.commit()
    login(client)

    res = client.post(f'/restaurant/orders/{order.id}/confirm', follow_redirects=True)

    assert res.status_code == 200
    assert order.status == OrderStatus.CONFIRMED


def test_cancel_order_route(client, app):
    _, restaurant = make_owner_and_restaurant()
    customer = make_customer()
    order = make_order(restaurant, customer)
    db.session.commit()
    login(client)

    res = client.post(f'/restaurant/orders/{order.id}/cancel',
                      data={'reason': 'Het nguyen lieu'}, follow_redirects=True)

    assert res.status_code == 200
    assert order.status == OrderStatus.CANCELLED
    assert order.cancel_reason == 'Het nguyen lieu'


def test_advance_order_route(client, app):
    _, restaurant = make_owner_and_restaurant()
    customer = make_customer()
    order = make_order(restaurant, customer, OrderStatus.CONFIRMED)
    db.session.commit()
    login(client)

    client.post(f'/restaurant/orders/{order.id}/advance', follow_redirects=True)

    assert order.status == OrderStatus.PREPARING


def test_restaurant_cannot_touch_other_orders(client, app):
    _, restaurant = make_owner_and_restaurant()
    customer = make_customer()
    order = make_order(restaurant, customer)
    db.session.commit()

    other_owner = User(username='owner2', email='owner2@test.vn', role=UserRole.RESTAURANT)
    other_owner.set_password('123456')
    db.session.add(other_owner)
    db.session.flush()
    db.session.add(Restaurant(name='Other', address='ABC', owner_id=other_owner.id))
    db.session.commit()
    login(client, username='owner2')

    res = client.post(f'/restaurant/orders/{order.id}/confirm')

    assert res.status_code == 404
    assert order.status == OrderStatus.PENDING


# ---------------- CẤU HÌNH NHÀ HÀNG (DAO) ----------------

def test_update_restaurant_settings_success(app):
    _, restaurant = make_owner_and_restaurant()
    db.session.commit()

    dao.update_restaurant_settings(restaurant, {
        'is_open': 'on',
        'phone': '0901234567',
        'description': 'Ngon',
        'min_order_amount': '50000',
        'confirm_timeout_minutes': '3',
        'delivery_radius_km': '5',
        'max_quantity_per_item': '10',
    })
    db.session.refresh(restaurant)

    assert restaurant.is_open is True
    assert restaurant.phone == '0901234567'
    assert restaurant.description == 'Ngon'
    assert restaurant.min_order_amount == 50000
    assert restaurant.confirm_timeout_minutes == 3
    assert restaurant.delivery_radius_km == 5
    assert restaurant.max_quantity_per_item == 10


def test_update_restaurant_settings_blank_uses_default(app):
    _, restaurant = make_owner_and_restaurant()
    db.session.commit()

    dao.update_restaurant_settings(restaurant, {
        'confirm_timeout_minutes': '5',
        'min_order_amount': '',
        'delivery_radius_km': '',
        'max_quantity_per_item': '',
    })
    db.session.refresh(restaurant)

    assert restaurant.min_order_amount is None
    assert restaurant.delivery_radius_km is None
    assert restaurant.max_quantity_per_item is None


def test_update_restaurant_settings_invalid_phone(app):
    _, restaurant = make_owner_and_restaurant()
    db.session.commit()

    with pytest.raises(ValueError):
        dao.update_restaurant_settings(restaurant, {'phone': 'abc', 'confirm_timeout_minutes': '5'})


def test_update_restaurant_settings_invalid_timeout(app):
    _, restaurant = make_owner_and_restaurant()
    db.session.commit()

    with pytest.raises(ValueError):
        dao.update_restaurant_settings(restaurant, {'confirm_timeout_minutes': '0'})
    with pytest.raises(ValueError):
        dao.update_restaurant_settings(restaurant, {'confirm_timeout_minutes': ''})


def test_update_restaurant_settings_invalid_radius(app):
    _, restaurant = make_owner_and_restaurant()
    db.session.commit()

    with pytest.raises(ValueError):
        dao.update_restaurant_settings(restaurant,
                                       {'confirm_timeout_minutes': '5',
                                        'delivery_radius_km': '-1'})


# ---------------- DASHBOARD & SETTINGS (ROUTER) ----------------

def test_dashboard_requireslogin(client):
    assert client.get('/restaurant/').status_code == 302


def test_dashboard_success(client, app):
    _, restaurant = make_owner_and_restaurant()
    customer = make_customer()
    make_order(restaurant, customer)
    db.session.commit()
    login(client)

    res = client.get('/restaurant/')

    assert res.status_code == 200
    assert 'Đơn #1'.encode('utf-8') in res.data
    assert b'feature-card' in res.data


def test_dashboard_stats_route_shows_revenue(client, app):
    _, restaurant = make_owner_and_restaurant()
    customer = make_customer()
    completed = make_order(restaurant, customer, OrderStatus.COMPLETED)
    completed.total_amount = 120000
    db.session.commit()
    login(client)

    res = client.get('/restaurant/')

    assert res.status_code == 200
    assert '120.000'.encode('utf-8') in res.data


def test_dashboard_stats_dao(app):
    _, restaurant = make_owner_and_restaurant()
    customer = make_customer()
    make_order(restaurant, customer)
    completed = make_order(restaurant, customer, OrderStatus.COMPLETED)
    completed.total_amount = 100000
    db.session.commit()

    stats = dao.get_dashboard_stats(restaurant.id)

    assert stats['counts'][OrderStatus.PENDING] == 1
    assert stats['counts'][OrderStatus.COMPLETED] == 1
    assert stats['revenue'] == 100000


def test_settings_view_requireslogin(client):
    assert client.get('/restaurant/settings').status_code == 302


def test_settings_view_forbidden_for_customer(client, app):
    make_owner_and_restaurant()
    make_customer()
    db.session.commit()
    login(client, username='customer')

    assert client.get('/restaurant/settings').status_code == 403


def test_settings_view_success(client, app):
    _, restaurant = make_owner_and_restaurant()
    db.session.commit()
    login(client)

    res = client.get('/restaurant/settings')

    assert res.status_code == 200
    assert b'confirm_timeout_minutes' in res.data


def test_settings_post_saves(client, app):
    _, restaurant = make_owner_and_restaurant()
    db.session.commit()
    login(client)

    client.post('/restaurant/settings', follow_redirects=True, data={
        'is_open': 'on',
        'phone': '0901234567',
        'description': 'Ngon ngon',
        'min_order_amount': '40000',
        'confirm_timeout_minutes': '7',
        'delivery_radius_km': '6',
        'max_quantity_per_item': '8',
    })
    db.session.refresh(restaurant)

    assert restaurant.min_order_amount == 40000
    assert restaurant.confirm_timeout_minutes == 7
    assert restaurant.delivery_radius_km == 6
    assert restaurant.max_quantity_per_item == 8


# ---------------- CHẶN NHÀ HÀNG ĐẶT HÀNG ----------------

def test_login_redirects_restaurant_to_dashboard(client, app):
    make_owner_and_restaurant()
    db.session.commit()

    res = login(client)

    assert res.status_code == 302
    assert res.headers['Location'] == '/restaurant/'


def test_login_redirects_customer_to_index(client, app):
    make_customer()
    db.session.commit()

    res = login(client, username='customer')

    assert res.status_code == 302
    assert res.headers['Location'] == '/'

def test_restaurant_blocked_from_cart(client, app):
    make_owner_and_restaurant()
    db.session.commit()
    login(client)

    assert client.get('/cart/').status_code == 403
    assert client.post('/cart/add', data={'dish_id': 1}).status_code == 403
    assert client.get('/cart/checkout').status_code == 403


# ---------------- SỐ LƯỢNG TỐI ĐA 1 MÓN/ĐƠN ----------------

def test_cart_max_quantity_uses_restaurant_override(app):
    _, restaurant = make_owner_and_restaurant()
    restaurant.max_quantity_per_item = 2
    customer = make_customer()
    dish = make_dish(restaurant)
    db.session.commit()

    from app.cart import dao as cart_dao
    cart_dao.add_to_cart(customer.id, dish.id, quantity=2)

    with pytest.raises(ValueError):
        cart_dao.add_to_cart(customer.id, dish.id, quantity=1)


def test_cart_max_quantity_default_when_no_override(app):
    _, restaurant = make_owner_and_restaurant()
    customer = make_customer()
    dish = make_dish(restaurant)
    db.session.commit()

    from app.cart import dao as cart_dao
    cart_dao.add_to_cart(customer.id, dish.id, quantity=20)

    with pytest.raises(ValueError):
        cart_dao.add_to_cart(customer.id, dish.id, quantity=1)


# ---------------- GIỎ HÀNG MỘT NHÀ HÀNG ----------------

def test_cart_blocks_adding_from_other_restaurant(app):
    _, restaurant_a = make_owner_and_restaurant()
    _, restaurant_b = make_owner_and_restaurant('B')
    customer = make_customer()
    dish_a = make_dish(restaurant_a)
    dish_b = make_dish(restaurant_b)
    db.session.commit()

    from app.cart import dao as cart_dao
    cart_dao.add_to_cart(customer.id, dish_a.id, quantity=1)

    with pytest.raises(cart_dao.CartRestaurantConflict):
        cart_dao.add_to_cart(customer.id, dish_b.id, quantity=1)

    assert cart_dao.get_user_carts(customer.id)[0].restaurant_id == restaurant_a.id


def test_clear_all_carts_allows_adding_other_restaurant(app):
    _, restaurant_a = make_owner_and_restaurant()
    _, restaurant_b = make_owner_and_restaurant('B')
    customer = make_customer()
    dish_a = make_dish(restaurant_a)
    dish_b = make_dish(restaurant_b)
    db.session.commit()

    from app.cart import dao as cart_dao
    cart_dao.add_to_cart(customer.id, dish_a.id, quantity=1)
    cart_dao.clear_all_carts(customer.id)
    cart_dao.add_to_cart(customer.id, dish_b.id, quantity=1)

    carts = cart_dao.get_user_carts(customer.id)
    assert len(carts) == 1
    assert carts[0].restaurant_id == restaurant_b.id


# ---------------- KHOẢNG CÁCH GIAO HÀNG (HAVERSINE) ----------------

def test_haversine_known_distance():
    from app.utils import haversine_km
    distance = haversine_km(10.7769, 106.7009, 10.7626, 106.6820)
    assert abs(distance - 2.5) < 0.5


def test_is_within_delivery_radius(app):
    _, restaurant = make_owner_and_restaurant()
    restaurant.latitude = 10.7769
    restaurant.longitude = 106.7009
    restaurant.delivery_radius_km = 5
    db.session.commit()

    assert restaurant.is_within_delivery_radius(10.7769, 106.7009)
    assert restaurant.is_within_delivery_radius(10.79, 106.71)
    assert not restaurant.is_within_delivery_radius(11.0, 107.0)


def test_no_gps_never_blocks(app):
    _, restaurant = make_owner_and_restaurant()
    db.session.commit()
    assert restaurant.is_within_delivery_radius(10.0, 106.0)


def test_update_settings_saves_coordinates(app):
    _, restaurant = make_owner_and_restaurant()
    db.session.commit()

    dao.update_restaurant_settings(restaurant, {
        'confirm_timeout_minutes': '5',
        'latitude': '10.7769',
        'longitude': '106.7009',
        'delivery_radius_km': '6',
    })
    db.session.refresh(restaurant)
    assert restaurant.latitude == 10.7769
    assert restaurant.longitude == 106.7009
    assert restaurant.delivery_radius_km == 6


def test_update_settings_invalid_coordinates(app):
    _, restaurant = make_owner_and_restaurant()
    db.session.commit()

    with pytest.raises(ValueError):
        dao.update_restaurant_settings(restaurant, {
            'confirm_timeout_minutes': '5',
            'latitude': '10.7769',
        })
    with pytest.raises(ValueError):
        dao.update_restaurant_settings(restaurant, {
            'confirm_timeout_minutes': '5',
            'latitude': '95',
            'longitude': '106',
        })


def test_validate_checkout_blocks_outside_radius(app):
    from app.cart import dao as cart_dao
    _, restaurant = make_owner_and_restaurant()
    restaurant.latitude = 10.7769
    restaurant.longitude = 106.7009
    restaurant.delivery_radius_km = 2
    customer = make_customer()
    dish = make_dish(restaurant)
    db.session.commit()

    cart_dao.add_to_cart(customer.id, dish.id, quantity=1)
    issues = cart_dao.validate_checkout(customer.id, lat=10.83, lng=106.73)
    assert any('ngoài bán kính' in issue for issue in issues)

    issues = cart_dao.validate_checkout(customer.id, lat=10.7769, lng=106.7009)
    assert not any('ngoài bán kính' in issue for issue in issues)