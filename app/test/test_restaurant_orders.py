import pytest
from datetime import datetime, timedelta

from flask import Flask
from flask_login import LoginManager, current_user

from app import db
from app.models import (User, UserRole, Restaurant, RestaurantStatus,
                        Order, OrderDetail, OrderStatus,
                        PaymentMethod, PaymentStatus, Category, Dish)
from app.restaurant import dao


def _make_app():
    app = Flask(__name__, template_folder='../templates', static_folder='../static')
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.secret_key = 'test'

    db.init_app(app)
    login = LoginManager()
    login.init_app(app)
    login.login_view = 'auth.login_view'

    @login.user_loader
    def load_user(user_id):
        from app.auth import dao as auth_dao
        return auth_dao.get_user_by_id(user_id)

    from app.auth import auth_bp
    app.register_blueprint(auth_bp)
    from app.browse import browse_bp
    app.register_blueprint(browse_bp)
    from app.cart import cart_bp
    app.register_blueprint(cart_bp)
    from app.restaurant import restaurant_bp
    app.register_blueprint(restaurant_bp)

    from app import index
    index.register_routers(app)

    @app.context_processor
    def inject_common():
        from app.models import Category
        from app.cart import dao as cart_dao
        try:
            categories = Category.query.all()
        except Exception:
            categories = []
        try:
            if current_user.is_authenticated:
                cart_stats = cart_dao.get_cart_stats(current_user.id)
            else:
                cart_stats = {'total_quantity': 0, 'total_amount': 0}
        except Exception:
            cart_stats = {'total_quantity': 0, 'total_amount': 0}
        return {'categories': categories, 'cart_stats': cart_stats}

    return app


@pytest.fixture
def app():
    application = _make_app()
    with application.app_context():
        db.create_all()
        yield application
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _make_restaurant_owner(prefix=''):
    owner = User(username=f'owner{prefix}', email=f'owner{prefix}@test.vn', full_name='Chu nha hang',
                 role=UserRole.RESTAURANT)
    owner.set_password('123456')
    db.session.add(owner)
    db.session.flush()
    restaurant = Restaurant(name=f'Test Restaurant{prefix}', address='123 Nguyen Hue',
                            phone='0900000000', status=RestaurantStatus.APPROVED,
                            confirm_timeout_minutes=5, owner_id=owner.id)
    db.session.add(restaurant)
    db.session.flush()
    return owner, restaurant


def _make_customer():
    customer = User(username='customer', email='customer@test.vn',
                    role=UserRole.CUSTOMER)
    customer.set_password('123456')
    db.session.add(customer)
    db.session.flush()
    return customer


def _make_order(restaurant, customer, status=OrderStatus.PENDING):
    order = Order(delivery_address='45 Le Loi', phone='0900000000',
                  total_amount=100000, status=status,
                  payment_method=PaymentMethod.ONLINE,
                  payment_status=PaymentStatus.PAID,
                  paid_at=datetime.now(),
                  user_id=customer.id, restaurant_id=restaurant.id)
    db.session.add(order)
    db.session.flush()
    order.set_confirm_deadline()
    return order


def _login(client, username='owner', password='123456'):
    return client.post('/auth/login',
                       data={'username': username, 'password': password})


def _make_menu(restaurant):
    cat = Category(name='Menu', restaurant_id=restaurant.id)
    db.session.add(cat)
    db.session.flush()
    dish = Dish(name='Com tam', price=30000,
                restaurant_id=restaurant.id, category_id=cat.id)
    db.session.add(dish)
    db.session.flush()
    return dish


# ---------------- DAO ----------------

def test_get_restaurant_for_owner(app):
    owner, restaurant = _make_restaurant_owner()
    db.session.commit()
    assert dao.get_restaurant_for_owner(owner.id).id == restaurant.id
    assert dao.get_restaurant_for_owner(99999) is None


def test_get_restaurant_orders_filter_by_status(app):
    owner, restaurant = _make_restaurant_owner()
    customer = _make_customer()
    pending = _make_order(restaurant, customer)
    confirmed = _make_order(restaurant, customer, OrderStatus.CONFIRMED)
    db.session.commit()

    assert {o.id for o in dao.get_restaurant_orders(restaurant.id)} == {pending.id, confirmed.id}
    assert [o.id for o in dao.get_restaurant_orders(restaurant.id, OrderStatus.PENDING)] == [pending.id]


def test_confirm_order_success(app):
    _, restaurant = _make_restaurant_owner()
    customer = _make_customer()
    order = _make_order(restaurant, customer)
    db.session.commit()

    dao.confirm_order(order)

    assert order.status == OrderStatus.CONFIRMED
    assert order.confirmed_at is not None


def test_confirm_order_wrong_status(app):
    _, restaurant = _make_restaurant_owner()
    customer = _make_customer()
    order = _make_order(restaurant, customer, OrderStatus.CONFIRMED)
    db.session.commit()

    with pytest.raises(ValueError):
        dao.confirm_order(order)


def test_confirm_order_expired(app):
    _, restaurant = _make_restaurant_owner()
    customer = _make_customer()
    order = _make_order(restaurant, customer)
    order.confirm_deadline = datetime.now() - timedelta(minutes=1)
    db.session.commit()

    with pytest.raises(ValueError):
        dao.confirm_order(order)
    assert order.status == OrderStatus.EXPIRED


def test_expire_overdue_orders(app):
    _, restaurant = _make_restaurant_owner()
    customer = _make_customer()
    overdue = _make_order(restaurant, customer)
    overdue.confirm_deadline = datetime.now() - timedelta(minutes=1)
    fresh = _make_order(restaurant, customer)
    db.session.commit()

    expired = dao.expire_overdue_orders(restaurant.id)

    assert [o.id for o in expired] == [overdue.id]
    assert overdue.status == OrderStatus.EXPIRED
    assert fresh.status == OrderStatus.PENDING


def test_advance_order_flow(app):
    _, restaurant = _make_restaurant_owner()
    customer = _make_customer()
    order = _make_order(restaurant, customer, OrderStatus.CONFIRMED)
    db.session.commit()

    dao.advance_order(order)
    assert order.status == OrderStatus.PREPARING
    dao.advance_order(order)
    assert order.status == OrderStatus.DELIVERING
    dao.advance_order(order)
    assert order.status == OrderStatus.COMPLETED


def test_advance_order_from_pending_fail(app):
    _, restaurant = _make_restaurant_owner()
    customer = _make_customer()
    order = _make_order(restaurant, customer)
    db.session.commit()

    with pytest.raises(ValueError):
        dao.advance_order(order)


def test_cancel_order_success(app):
    _, restaurant = _make_restaurant_owner()
    customer = _make_customer()
    order = _make_order(restaurant, customer)
    db.session.commit()

    dao.cancel_order(order, 'Het nguyen lieu')

    assert order.status == OrderStatus.CANCELLED
    assert order.cancel_reason == 'Het nguyen lieu'
    assert order.cancelled_at is not None


def test_cancel_order_requires_reason(app):
    _, restaurant = _make_restaurant_owner()
    customer = _make_customer()
    order = _make_order(restaurant, customer)
    db.session.commit()

    with pytest.raises(ValueError):
        dao.cancel_order(order, '  ')


def test_cancel_order_completed_fail(app):
    _, restaurant = _make_restaurant_owner()
    customer = _make_customer()
    order = _make_order(restaurant, customer, OrderStatus.COMPLETED)
    db.session.commit()

    with pytest.raises(ValueError):
        dao.cancel_order(order, 'ly do')


def test_mark_refunded_success(app):
    _, restaurant = _make_restaurant_owner()
    customer = _make_customer()
    order = _make_order(restaurant, customer)
    db.session.commit()
    dao.cancel_order(order, 'ly do')

    dao.mark_refunded(order)

    assert order.payment_status == PaymentStatus.REFUNDED


def test_mark_refunded_non_cancelled_fail(app):
    _, restaurant = _make_restaurant_owner()
    customer = _make_customer()
    order = _make_order(restaurant, customer)
    db.session.commit()

    with pytest.raises(ValueError):
        dao.mark_refunded(order)


# ---------------- ROUTER ----------------

def test_orders_view_requires_login(client, app):
    res = client.get('/restaurant/orders')
    assert res.status_code == 302
    assert '/auth/login' in res.headers['Location']


def test_orders_view_forbidden_for_customer(client, app):
    _make_restaurant_owner()
    _make_customer()
    db.session.commit()
    _login(client, username='customer')

    assert client.get('/restaurant/orders').status_code == 403


def test_orders_view_success(client, app):
    _, restaurant = _make_restaurant_owner()
    customer = _make_customer()
    _make_order(restaurant, customer)
    db.session.commit()
    _login(client)

    res = client.get('/restaurant/orders')

    assert res.status_code == 200
    assert 'Test Restaurant'.encode() in res.data
    assert b'order-1' in res.data


def test_orders_view_expires_overdue(client, app):
    _, restaurant = _make_restaurant_owner()
    customer = _make_customer()
    order = _make_order(restaurant, customer)
    order.confirm_deadline = datetime.now() - timedelta(minutes=1)
    db.session.commit()
    _login(client)

    client.get('/restaurant/orders')

    assert order.status == OrderStatus.EXPIRED


def test_confirm_order_route(client, app):
    _, restaurant = _make_restaurant_owner()
    customer = _make_customer()
    order = _make_order(restaurant, customer)
    db.session.commit()
    _login(client)

    res = client.post(f'/restaurant/orders/{order.id}/confirm', follow_redirects=True)

    assert res.status_code == 200
    assert order.status == OrderStatus.CONFIRMED


def test_cancel_order_route(client, app):
    _, restaurant = _make_restaurant_owner()
    customer = _make_customer()
    order = _make_order(restaurant, customer)
    db.session.commit()
    _login(client)

    res = client.post(f'/restaurant/orders/{order.id}/cancel',
                      data={'reason': 'Het nguyen lieu'}, follow_redirects=True)

    assert res.status_code == 200
    assert order.status == OrderStatus.CANCELLED
    assert order.cancel_reason == 'Het nguyen lieu'


def test_advance_order_route(client, app):
    _, restaurant = _make_restaurant_owner()
    customer = _make_customer()
    order = _make_order(restaurant, customer, OrderStatus.CONFIRMED)
    db.session.commit()
    _login(client)

    client.post(f'/restaurant/orders/{order.id}/advance', follow_redirects=True)

    assert order.status == OrderStatus.PREPARING


def test_restaurant_cannot_touch_other_orders(client, app):
    _, restaurant = _make_restaurant_owner()
    customer = _make_customer()
    order = _make_order(restaurant, customer)
    db.session.commit()

    other_owner = User(username='owner2', email='owner2@test.vn', role=UserRole.RESTAURANT)
    other_owner.set_password('123456')
    db.session.add(other_owner)
    db.session.flush()
    db.session.add(Restaurant(name='Other', address='ABC', owner_id=other_owner.id))
    db.session.commit()
    _login(client, username='owner2')

    res = client.post(f'/restaurant/orders/{order.id}/confirm')

    assert res.status_code == 404
    assert order.status == OrderStatus.PENDING


# ---------------- CẤU HÌNH NHÀ HÀNG (DAO) ----------------

def test_update_restaurant_settings_success(app):
    _, restaurant = _make_restaurant_owner()
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
    _, restaurant = _make_restaurant_owner()
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
    _, restaurant = _make_restaurant_owner()
    db.session.commit()

    with pytest.raises(ValueError):
        dao.update_restaurant_settings(restaurant, {'phone': 'abc', 'confirm_timeout_minutes': '5'})


def test_update_restaurant_settings_invalid_timeout(app):
    _, restaurant = _make_restaurant_owner()
    db.session.commit()

    with pytest.raises(ValueError):
        dao.update_restaurant_settings(restaurant, {'confirm_timeout_minutes': '0'})
    with pytest.raises(ValueError):
        dao.update_restaurant_settings(restaurant, {'confirm_timeout_minutes': ''})


def test_update_restaurant_settings_invalid_radius(app):
    _, restaurant = _make_restaurant_owner()
    db.session.commit()

    with pytest.raises(ValueError):
        dao.update_restaurant_settings(restaurant,
                                       {'confirm_timeout_minutes': '5',
                                        'delivery_radius_km': '-1'})


# ---------------- DASHBOARD & SETTINGS (ROUTER) ----------------

def test_dashboard_requires_login(client):
    assert client.get('/restaurant/').status_code == 302


def test_dashboard_success(client, app):
    _, restaurant = _make_restaurant_owner()
    customer = _make_customer()
    _make_order(restaurant, customer)
    db.session.commit()
    _login(client)

    res = client.get('/restaurant/')

    assert res.status_code == 200
    assert 'Đơn #1'.encode('utf-8') in res.data
    assert b'feature-card' in res.data


def test_dashboard_stats_route_shows_revenue(client, app):
    _, restaurant = _make_restaurant_owner()
    customer = _make_customer()
    completed = _make_order(restaurant, customer, OrderStatus.COMPLETED)
    completed.total_amount = 120000
    db.session.commit()
    _login(client)

    res = client.get('/restaurant/')

    assert res.status_code == 200
    assert '120.000'.encode('utf-8') in res.data


def test_dashboard_stats_dao(app):
    _, restaurant = _make_restaurant_owner()
    customer = _make_customer()
    _make_order(restaurant, customer)
    completed = _make_order(restaurant, customer, OrderStatus.COMPLETED)
    completed.total_amount = 100000
    db.session.commit()

    stats = dao.get_dashboard_stats(restaurant.id)

    assert stats['counts'][OrderStatus.PENDING] == 1
    assert stats['counts'][OrderStatus.COMPLETED] == 1
    assert stats['revenue'] == 100000


def test_settings_view_requires_login(client):
    assert client.get('/restaurant/settings').status_code == 302


def test_settings_view_forbidden_for_customer(client, app):
    _make_restaurant_owner()
    _make_customer()
    db.session.commit()
    _login(client, username='customer')

    assert client.get('/restaurant/settings').status_code == 403


def test_settings_view_success(client, app):
    _, restaurant = _make_restaurant_owner()
    db.session.commit()
    _login(client)

    res = client.get('/restaurant/settings')

    assert res.status_code == 200
    assert b'confirm_timeout_minutes' in res.data


def test_settings_post_saves(client, app):
    _, restaurant = _make_restaurant_owner()
    db.session.commit()
    _login(client)

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
    _make_restaurant_owner()
    db.session.commit()

    res = _login(client)

    assert res.status_code == 302
    assert res.headers['Location'] == '/restaurant/'


def test_login_redirects_customer_to_index(client, app):
    _make_customer()
    db.session.commit()

    res = _login(client, username='customer')

    assert res.status_code == 302
    assert res.headers['Location'] == '/'

def test_restaurant_blocked_from_cart(client, app):
    _make_restaurant_owner()
    db.session.commit()
    _login(client)

    assert client.get('/cart/').status_code == 403
    assert client.post('/cart/add', data={'dish_id': 1}).status_code == 403
    assert client.get('/cart/checkout').status_code == 403


# ---------------- SỐ LƯỢNG TỐI ĐA 1 MÓN/ĐƠN ----------------

def test_cart_max_quantity_uses_restaurant_override(app):
    _, restaurant = _make_restaurant_owner()
    restaurant.max_quantity_per_item = 2
    customer = _make_customer()
    dish = _make_menu(restaurant)
    db.session.commit()

    from app.cart import dao as cart_dao
    cart_dao.add_to_cart(customer.id, dish.id, quantity=2)

    with pytest.raises(ValueError):
        cart_dao.add_to_cart(customer.id, dish.id, quantity=1)


def test_cart_max_quantity_default_when_no_override(app):
    _, restaurant = _make_restaurant_owner()
    customer = _make_customer()
    dish = _make_menu(restaurant)
    db.session.commit()

    from app.cart import dao as cart_dao
    cart_dao.add_to_cart(customer.id, dish.id, quantity=20)

    with pytest.raises(ValueError):
        cart_dao.add_to_cart(customer.id, dish.id, quantity=1)


# ---------------- GIỎ HÀNG MỘT NHÀ HÀNG ----------------

def test_cart_blocks_adding_from_other_restaurant(app):
    _, restaurant_a = _make_restaurant_owner()
    _, restaurant_b = _make_restaurant_owner('B')
    customer = _make_customer()
    dish_a = _make_menu(restaurant_a)
    dish_b = _make_menu(restaurant_b)
    db.session.commit()

    from app.cart import dao as cart_dao
    cart_dao.add_to_cart(customer.id, dish_a.id, quantity=1)

    with pytest.raises(cart_dao.CartRestaurantConflict):
        cart_dao.add_to_cart(customer.id, dish_b.id, quantity=1)

    assert cart_dao.get_user_carts(customer.id)[0].restaurant_id == restaurant_a.id


def test_clear_all_carts_allows_adding_other_restaurant(app):
    _, restaurant_a = _make_restaurant_owner()
    _, restaurant_b = _make_restaurant_owner('B')
    customer = _make_customer()
    dish_a = _make_menu(restaurant_a)
    dish_b = _make_menu(restaurant_b)
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
    _, restaurant = _make_restaurant_owner()
    restaurant.latitude = 10.7769
    restaurant.longitude = 106.7009
    restaurant.delivery_radius_km = 5
    db.session.commit()

    assert restaurant.is_within_delivery_radius(10.7769, 106.7009)
    assert restaurant.is_within_delivery_radius(10.79, 106.71)
    assert not restaurant.is_within_delivery_radius(11.0, 107.0)


def test_no_gps_never_blocks(app):
    _, restaurant = _make_restaurant_owner()
    db.session.commit()
    assert restaurant.is_within_delivery_radius(10.0, 106.0)


def test_update_settings_saves_coordinates(app):
    _, restaurant = _make_restaurant_owner()
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
    _, restaurant = _make_restaurant_owner()
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
    _, restaurant = _make_restaurant_owner()
    restaurant.latitude = 10.7769
    restaurant.longitude = 106.7009
    restaurant.delivery_radius_km = 2
    customer = _make_customer()
    dish = _make_menu(restaurant)
    db.session.commit()

    cart_dao.add_to_cart(customer.id, dish.id, quantity=1)
    issues = cart_dao.validate_checkout(customer.id, lat=10.83, lng=106.73)
    assert any('ngoài bán kính' in issue for issue in issues)

    issues = cart_dao.validate_checkout(customer.id, lat=10.7769, lng=106.7009)
    assert not any('ngoài bán kính' in issue for issue in issues)