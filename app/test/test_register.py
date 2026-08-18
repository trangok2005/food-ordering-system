import pytest

from app import db
from app.auth import dao as auth_dao
from app.models import User, UserRole
from app.test.test_base import app, client, test_session, make_user


# ---------------- DAO: add_user ----------------

def test_register_success(test_session):
    auth_dao.add_user(username='demo1', password='123ABC123',
                      email='demo1@test.vn', phone='0123456789',
                      address='HCM City')

    u = User.query.filter(User.username == 'demo1').first()
    assert u is not None
    assert u.username == 'demo1'
    assert u.email == 'demo1@test.vn'
    assert u.phone == '0123456789'
    assert u.address == 'HCM City'
    assert u.check_password('123ABC123')
    assert u.role == UserRole.CUSTOMER


def test_register_default_active(test_session):
    auth_dao.add_user(username='active_user', password='123ABC123',
                      email='active@test.vn')
    assert User.query.filter_by(username='active_user').first().active is True


@pytest.mark.parametrize('password', [
    '1',
    '1' * 5,
    'a' * 5,
])
def test_invalid_password(password, test_session):
    with pytest.raises(ValueError):
        auth_dao.add_user(username='demodemo', password=password,
                          email='demodemo@test.vn')


@pytest.mark.parametrize('username', ['a', 'ab'])
def test_invalid_username(username, test_session):
    with pytest.raises(ValueError):
        auth_dao.add_user(username=username, password='123ABC123',
                          email='demodemo@test.vn')


@pytest.mark.parametrize('email', ['', 'khong-hai-hop-le', 'abc'])
def test_invalid_email(email, test_session):
    with pytest.raises(ValueError):
        auth_dao.add_user(username='demodemo', password='123ABC123', email=email)


@pytest.mark.parametrize('phone', [
    '1230',
    'abc1234567',
    '012309090?',
    '111111111111',
])
def test_invalid_phone(phone, test_session):
    with pytest.raises(ValueError):
        auth_dao.add_user(username='demo123', password='123ABC123',
                          email='demo@test.vn', phone=phone)


def test_existing_username(test_session):
    auth_dao.add_user(username='demodemo', password='123ABC123',
                      email='a@test.vn')
    with pytest.raises(ValueError):
        auth_dao.add_user(username='demodemo', password='123ABC123',
                          email='b@test.vn')


def test_existing_email(test_session):
    auth_dao.add_user(username='demodemo', password='123ABC123',
                      email='a@test.vn')
    with pytest.raises(ValueError):
        auth_dao.add_user(username='demodemo2', password='123ABC123',
                          email='a@test.vn')


def test_full_name_stored(test_session):
    auth_dao.add_user(username='demo1', password='123ABC123',
                      email='demo1@test.vn', full_name='Nguyen Van A')
    assert User.query.filter_by(username='demo1').first().full_name == 'Nguyen Van A'


# ---------------- ROUTER: /auth/register ----------------

def test_get_register_page(client, app):
    assert client.get('/auth/register').status_code == 200


def test_register_route_success(client, app):
    res = client.post('/auth/register', data={
        'username': 'khmoi',
        'email': 'khmoi@test.vn',
        'password': '123ABC123',
        'confirm': '123ABC123',
        'full_name': 'Khách mới',
        'phone': '0123456789',
        'address': 'HCM',
    })
    assert res.status_code == 302
    assert res.headers['Location'].endswith('/auth/login')
    assert User.query.filter_by(username='khmoi').first() is not None


def test_register_route_password_mismatch(client, app):
    res = client.post('/auth/register', data={
        'username': 'khmoi',
        'email': 'khmoi@test.vn',
        'password': '123ABC123',
        'confirm': 'khac',
    })
    assert res.status_code == 200
    assert 'Mật khẩu không khớp'.encode('utf-8') in res.data
    assert User.query.filter_by(username='khmoi').first() is None


def test_register_route_duplicate_username(client, app):
    make_user('khmoi')
    res = client.post('/auth/register', data={
        'username': 'khmoi',
        'email': 'khmoi2@test.vn',
        'password': '123ABC123',
        'confirm': '123ABC123',
    })
    assert res.status_code == 200
    assert 'tồn tại'.encode('utf-8') in res.data


def test_register_route_redirects_when_authenticated(client, app):
    make_user('kh1')
    login = client.post('/auth/login',
                        data={'username': 'kh1', 'password': '123456'})
    assert login.status_code == 302
    assert client.get('/auth/register').status_code == 302