import pytest
from datetime import datetime

from flask import Flask
from flask_login import LoginManager, current_user

from app import db
from app.models import (User, UserRole, Restaurant, RestaurantStatus,
                        Category, Dish, Order, OrderStatus,
                        PaymentMethod, PaymentStatus)


def make_app():
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
    from app.ai import ai_bp
    app.register_blueprint(ai_bp)

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


# ---------------- HÀM TẠO DỮ LIỆU DÙNG CHUNG ----------------

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
    """Tạo luôn chủ + nhà hàng, trả về (owner, restaurant)."""
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
