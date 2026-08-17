import pytest
from flask import Flask
from flask_login import LoginManager, current_user

from app import db
from app.models import (User, UserRole, Restaurant, RestaurantStatus,
                        Category, Dish, Order, OrderDetail, OrderStatus,
                        PaymentMethod, PaymentStatus)
from datetime import datetime, timedelta


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
    from app.admin import admin_bp
    app.register_blueprint(admin_bp)

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


def _make_admin():
    admin = User(username='admin', email='admin@test.vn', full_name='Quan tri',
                 role=UserRole.ADMIN)
    admin.set_password('123456')
    db.session.add(admin)
    db.session.flush()
    return admin


def _make_restaurant_owner(prefix=''):
    owner = User(username=f'owner{prefix}', email=f'owner{prefix}@test.vn',
                 role=UserRole.RESTAURANT)
    owner.set_password('123456')
    db.session.add(owner)
    db.session.flush()
    return owner


def _make_restaurant(owner, status=RestaurantStatus.PENDING):
    restaurant = Restaurant(name=f'Restaurant {owner.username}',
                            address='123 Nguyen Hue', phone='0900000000',
                            status=status, owner_id=owner.id)
    db.session.add(restaurant)
    db.session.flush()
    return restaurant


def _login(client, username='admin', password='123456'):
    return client.post('/auth/login',
                       data={'username': username, 'password': password})


def _make_order(restaurant, customer, total=100000, status=OrderStatus.COMPLETED):
    order = Order(delivery_address='45 Le Loi', phone='0900000000',
                  total_amount=total, status=status,
                  payment_method=PaymentMethod.ONLINE,
                  payment_status=PaymentStatus.PAID,
                  paid_at=datetime.now(),
                  user_id=customer.id, restaurant_id=restaurant.id)
    db.session.add(order)
    db.session.flush()
    return order


def _make_customer():
    customer = User(username='customer', email='customer@test.vn',
                    role=UserRole.CUSTOMER)
    customer.set_password('123456')
    db.session.add(customer)
    db.session.flush()
    return customer


def _make_menu(restaurant):
    cat = Category(name='Menu', restaurant_id=restaurant.id)
    db.session.add(cat)
    db.session.flush()
    dish = Dish(name='Com tam', price=30000,
                restaurant_id=restaurant.id, category_id=cat.id)
    db.session.add(dish)
    db.session.flush()
    return dish


# ---------------- PHÂN QUYỀN ----------------

def test_admin_dashboard_requires_login(client, app):
    assert client.get('/admin/').status_code == 302


def test_non_admin_blocked(client, app):
    customer = _make_customer()
    db.session.commit()
    _login(client, username='customer')
    assert client.get('/admin/').status_code == 403


def test_admin_login_redirects_to_admin(client, app):
    _make_admin()
    db.session.commit()
    res = _login(client)
    assert res.status_code == 302
    assert res.headers['Location'].endswith('/admin/')


# ---------------- PHÊ DUYỆT NHÀ HÀNG ----------------

def test_approve_restaurant(client, app):
    _make_admin()
    owner = _make_restaurant_owner()
    restaurant = _make_restaurant(owner, RestaurantStatus.PENDING)
    db.session.commit()
    _login(client)

    res = client.post(f'/admin/restaurants/{restaurant.id}/approve')
    assert res.status_code == 302
    db.session.refresh(restaurant)
    assert restaurant.status == RestaurantStatus.APPROVED


def test_approve_only_pending(client, app):
    _make_admin()
    owner = _make_restaurant_owner()
    restaurant = _make_restaurant(owner, RestaurantStatus.APPROVED)
    db.session.commit()
    _login(client)

    client.post(f'/admin/restaurants/{restaurant.id}/approve')
    db.session.refresh(restaurant)
    assert restaurant.status == RestaurantStatus.APPROVED


def test_lock_and_unlock_restaurant(client, app):
    _make_admin()
    owner = _make_restaurant_owner()
    restaurant = _make_restaurant(owner, RestaurantStatus.APPROVED)
    db.session.commit()
    _login(client)

    client.post(f'/admin/restaurants/{restaurant.id}/lock')
    db.session.refresh(restaurant)
    assert restaurant.status == RestaurantStatus.LOCKED

    client.post(f'/admin/restaurants/{restaurant.id}/unlock')
    db.session.refresh(restaurant)
    assert restaurant.status == RestaurantStatus.APPROVED


def test_restaurants_view_filters_by_status(client, app):
    _make_admin()
    owner = _make_restaurant_owner()
    _make_restaurant(owner, RestaurantStatus.PENDING)
    _make_restaurant(owner, RestaurantStatus.APPROVED)
    db.session.commit()
    _login(client)

    res = client.get('/admin/restaurants?status=APPROVED')
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'Nhà hàng' in html


# ---------------- THỐNG KÊ ----------------

def test_dashboard_stats_page(client, app):
    _make_admin()
    owner = _make_restaurant_owner()
    restaurant = _make_restaurant(owner, RestaurantStatus.APPROVED)
    customer = _make_customer()
    _make_order(restaurant, customer, total=100000)
    _make_menu(restaurant)
    db.session.commit()
    _login(client)

    res = client.get('/admin/stats')
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'Doanh thu' in html
    assert 'Món ăn bán chạy nhất' in html


def test_dashboard_stats_dao(app):
    owner = _make_restaurant_owner()
    restaurant = _make_restaurant(owner, RestaurantStatus.APPROVED)
    customer = _make_customer()
    _make_order(restaurant, customer, total=100000)
    _make_order(restaurant, customer, total=50000, status=OrderStatus.DELIVERING)
    _make_order(restaurant, customer, total=20000, status=OrderStatus.CANCELLED)
    db.session.commit()

    from app.admin import get_dashboard_stats, get_top_restaurants, get_top_dishes
    stats = get_dashboard_stats()
    assert stats['restaurant_count'] == 1
    assert stats['order_count'] == 3
    assert stats['paid_count'] == 3
    assert stats['revenue'] == 150000

    top = get_top_restaurants()
    assert top and top[0][0].id == restaurant.id
    assert top[0][2] == 150000
