import datetime
import hashlib
import pytest
from flask import Flask
from flask_login import LoginManager

from app import db
from app.models import UserRole, User
from app.index import register_routers


def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///:memory:"
    app.config["TESTING"] = True
    app.config["PAGE_SIZE"] = 2
    app.secret_key = 'trangdeptraicomotkohaip@ok'
    db.init_app(app)

    login = LoginManager()
    login.init_app(app)

    @login.user_loader
    def load_user(user_id):
        return db.get_user_by_id(user_id)

    register_routers(app=app)

    return app


@pytest.fixture
def test_app():
    app = create_app()

    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def test_client(test_app):
    return test_app.test_client()


@pytest.fixture
def test_session(test_app):
    yield db.session


@pytest.fixture
def sample_products(test_session):
    p1 = Product(name="Cá hồi Sashimi", price=120000.0, stock=50, category_id=1)
    p2 = Product(name="Cá ngừ Sashimi", price=150000.0, stock=0, category_id=1)
    p3 = Product(name="Cá Nigiri", price=90000.0, stock=20, category_id=2)
    p4 = Product(name="Cua Nigiri", price=80000.0, stock=10, category_id=2)
    p5 = Product(name="Coca Cola", price=10000.0, stock=150, category_id=3)
    p6 = Product(name="Cá Shusi", price=190000.0, stock=35, category_id=4)
    p7 = Product(name="Cua Sushi", price=10000.0, stock=150, category_id=4)
    p8 = Product(name="Nước khoán", price=8000.0, stock=100, category_id=3)
    test_session.add_all([p1, p2, p3, p4, p5, p6, p7, p8])
    test_session.commit()
    return [p1, p2, p3, p4, p5, p6, p7, p8]


# auth
@pytest.fixture
def logged_in_user(mocker):
    class FakeUser:
        is_authenticated = True
        id = 1
        role = UserRole.USER

    mocker.patch('flask_login.utils._get_user', return_value=FakeUser())
    mocker.patch('app.index.current_user', new=FakeUser())
    return FakeUser()


@pytest.fixture
def logged_in_admin(mocker):
    class FakeAdmin:
        is_authenticated = True
        id = 1
        role = UserRole.ADMIN

    mocker.patch('flask_login.utils._get_user', return_value=FakeAdmin())
    mocker.patch('app.index.current_user', new=FakeAdmin())
    return FakeAdmin()


# set up user
@pytest.fixture
def setup_user(test_session):
    u = User(
        username='kh1',
        password=hashlib.md5('123456'.encode()).hexdigest(),
        phone='0901234567',
        address='123 Nguyễn Huệ',
        role=UserRole.USER,
    )
    test_session.add(u)
    test_session.commit()
    return u


@pytest.fixture
def setup_users(test_session):
    admin = User(
        username='admin',
        password=hashlib.md5('123456'.encode()).hexdigest(),
        phone='0911223344',
        address='Nhà hàng Q3',
        role=UserRole.ADMIN,
    )
    customer = User(
        username='kh1',
        password=hashlib.md5('123456'.encode()).hexdigest(),
        phone='0901234567',
        address='123 Nguyễn Huệ',
        role=UserRole.USER,
    )
    test_session.add_all([admin, customer])
    test_session.commit()
    return admin, customer


# setup order
@pytest.fixture
def setup_orders_user(test_session, setup_user, sample_products):
    o1 = Order(user_id=setup_user.id, delivery_address='123 Nguyễn Huệ',
               phone='0901234567', total_amount=240000,
               status=OrderStatus.PENDING)
    o2 = Order(user_id=setup_user.id, delivery_address='456 Lê Lợi',
               phone='0901234567', total_amount=90000,
               status=OrderStatus.PREPARING)
    o3 = Order(user_id=setup_user.id, delivery_address='789 Trần Hưng Đạo',
               phone='0901234567', total_amount=150000,
               status=OrderStatus.CANCELLED)
    test_session.add_all([o1, o2, o3])
    test_session.flush()

    test_session.add_all([
        OrderDetail(order_id=o1.id, product_id=sample_products[0].id, quantity=2),
        OrderDetail(order_id=o2.id, product_id=sample_products[2].id, quantity=1),
        OrderDetail(order_id=o3.id, product_id=sample_products[4].id, quantity=3),
    ])
    test_session.commit()
    return [o1, o2, o3]


@pytest.fixture
def setup_orders_admin(test_session, setup_users, sample_products):
    _, customer = setup_users
    statuses = [
        OrderStatus.PENDING,
        OrderStatus.PREPARING,
        OrderStatus.DELIVERING,
        OrderStatus.COMPLETED,
    ]
    orders = []
    for i, status in enumerate(statuses):
        o = Order(
            user_id=customer.id,
            delivery_address=f'Địa chỉ {i + 1}',
            phone='0901234567',
            total_amount=100000 + i * 50000,
            status=status,
        )
        test_session.add(o)
        orders.append(o)
    test_session.flush()

    for i, o in enumerate(orders):
        test_session.add(OrderDetail(
            order_id=o.id,
            product_id=sample_products[i % len(sample_products)].id,
            quantity=i + 1,
        ))
    test_session.commit()
    return orders


# giỏ hangf mẫu
@pytest.fixture
def cart_standard(test_client):
    with test_client.session_transaction() as sess:
        sess['cart'] = {
            "1": {"id": 1, "name": "Cá hồi Sashimi", "price": 120000, "quantity": 2},
            "2": {"id": 2, "name": "Cá ngừ Sashimi", "price": 100000, "quantity": 1},
        }


