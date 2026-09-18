import pytest
from datetime import datetime
import secrets

from flask.testing import FlaskClient

from app import create_app
from app.extensions import db
from app.models import (User, UserRole, Restaurant, RestaurantStatus,
                        Category, Dish, Order, OrderStatus,
                        PaymentMethod, PaymentStatus)


class CsrfTestClient(FlaskClient):
    """Tự chèn CSRF vào POST trong test."""

    def open(self, *args, **kwargs):
        method = str(kwargs.get('method', '')).upper()
        if method == 'POST' and kwargs.get('json') is None:
            with self.session_transaction() as test_session:
                token = test_session.setdefault('_csrf_token', secrets.token_urlsafe(32))
            data = kwargs.get('data')
            if data is None:
                data = {}
            if hasattr(data, 'copy') and hasattr(data, 'setdefault'):
                data = data.copy()
                data.setdefault('_csrf_token', token)
                kwargs['data'] = data
        return super().open(*args, **kwargs)


def make_app():
    application = create_app({
        'TESTING': True,
        'SECRET_KEY': 'test-secret-key',
        'APP_BASE_URL': 'http://localhost',
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
    })
    application.test_client_class = CsrfTestClient
    return application


@pytest.fixture
def app():
    application = make_app()
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def test_session(app):
    yield db.session


def make_user(username, role=UserRole.CUSTOMER, password='123456', **kwargs):
    email = kwargs.pop('email', None) or f'{username}@test.vn'
    user = User(username=username, email=email, role=role, **kwargs)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    return user


def make_admin(**kwargs):
    return make_user('admin', role=UserRole.ADMIN, full_name='Quan tri', **kwargs)


def make_customer(username='customer', **kwargs):
    return make_user(username, role=UserRole.CUSTOMER, **kwargs)


def make_restaurant_owner(prefix=''):
    return make_user(f'owner{prefix}', role=UserRole.RESTAURANT,
                     full_name=f'Chu nha hang {prefix}')


def make_restaurant(owner, status=RestaurantStatus.APPROVED, name=None, **kwargs):
    restaurant = Restaurant(name=name or f'Test Restaurant {owner.username}',
                            address='123 Nguyen Hue', phone='0900000000',
                            status=status, confirm_timeout_minutes=5,
                            owner_id=owner.id, **kwargs)
    db.session.add(restaurant)
    db.session.flush()
    return restaurant


def make_owner_and_restaurant(prefix=''):
    owner = make_restaurant_owner(prefix)
    return owner, make_restaurant(owner)


def make_dish(restaurant, name='Com tam', price=30000, **kwargs):
    cat = (Category.query
           .filter_by(name='Menu', restaurant_id=restaurant.id)
           .first())
    if not cat:
        cat = Category(name='Menu', restaurant_id=restaurant.id)
        db.session.add(cat)
        db.session.flush()
    dish = Dish(name=name, price=price,
                restaurant_id=restaurant.id, category_id=cat.id, **kwargs)
    db.session.add(dish)
    db.session.flush()
    return dish


def make_order(restaurant, customer, status=OrderStatus.PENDING, total=100000, **kwargs):
    order = Order(delivery_address='45 Le Loi', phone='0900000000',
                  total_amount=total, status=status,
                  payment_method=PaymentMethod.ONLINE,
                  payment_status=PaymentStatus.PAID,
                  paid_at=datetime.now(),
                  user_id=customer.id, restaurant_id=restaurant.id, **kwargs)
    db.session.add(order)
    db.session.flush()
    order.set_confirm_deadline()
    return order


def login(client, username='owner', password='123456'):
    return client.post('/auth/login',
                       data={'username': username, 'password': password})
