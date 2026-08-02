import hashlib
import pytest
from app.dao import auth_user
from app.models import User, UserRole
from app.test.test_base import test_app, test_client, test_session


@pytest.fixture
def setup_users(test_session):
    customer = User(
        username='kh1',
        password=hashlib.md5('123456'.encode()).hexdigest(),
        phone='0901234567', address='123 Nguyễn Huệ',
        role=UserRole.USER
    )
    inactive = User(
        username='duy',
        password=hashlib.md5('123456'.encode()).hexdigest(),
        phone='0909090909', address='ở đâu',
        role=UserRole.USER, active=False,
    )
    admin = User(
        username='admin',
        password=hashlib.md5('admin123'.encode()).hexdigest(),
        phone='0911223344', address='Nhà hàng Q3',
        role=UserRole.ADMIN
    )
    test_session.add_all([customer, inactive, admin])
    test_session.commit()
    return customer, inactive, admin


# test dao auth_user
def test_auth_user_success(setup_users):
    customer, _, _ = setup_users
    result = auth_user('kh1', '123456')
    assert result is not None
    assert result.username == 'kh1'


def test_auth_user_wrong_password(setup_users):
    result = auth_user('kh1', '111111')
    assert result is None


def test_auth_user_wrong_username(setup_users):
    result = auth_user('trangdeptrai', '123456')
    assert result is None


def test_auth_user_inactive_account(setup_users):
    result = auth_user('banned', '123456')
    assert result is None


@pytest.mark.parametrize('username, password', [
    (None, '123456'),
    ('kh1', None),
    (None, None),
    ('', '123456'),
    ('kh1', ''),
])
def test_auth_user_empty_inputs(username, password, setup_users):
    assert auth_user(username, password) is None


def test_auth_user_strips_whitespace(setup_users):
    result = auth_user('  kh1  ', '  123456  ')
    assert result is not None
    assert result.username == 'kh1'


def test_get_login_page_renders_template(test_client, mocker):
    mock_render = mocker.patch(
        'app.index.render_template',
        return_value='<html>Login</html>'
    )
    res = test_client.get('/login')
    assert res.status_code == 200
    mock_render.assert_called_once()


# post login
def test_login_success_customer_no_next(test_client, setup_users, mocker):
    customer, _, _ = setup_users
    mocker.patch('app.dao.auth_user', return_value=customer)
    mock_login = mocker.patch('app.index.login_user')

    res = test_client.post('/login', data={'username': 'kh1', 'password': '123456'})

    assert res.status_code == 302
    assert res.headers['Location'] == '/'
    mock_login.assert_called_once()


def test_login_success_customer_with_next(test_client, setup_users, mocker):
    customer, _, _ = setup_users
    mocker.patch('app.dao.auth_user', return_value=customer)
    mocker.patch('app.index.login_user')

    res = test_client.post('/login?next=/api/pay', data={'username': 'kh1', 'password': '123456'})

    assert res.status_code == 302
    assert res.headers['Location'] == '/api/pay'


def test_login_success_admin_always_to_admin(test_client, setup_users, mocker):
    _, _, admin = setup_users
    mocker.patch('app.dao.auth_user', return_value=admin)
    mocker.patch('app.index.login_user')

    res = test_client.post('/login?next=/api/pay', data={'username': 'admin_sushi', 'password': 'admin123'})

    assert res.status_code == 302
    assert res.headers['Location'] == '/admin'


def test_login_failed_wrong_credentials(test_client, setup_users, mocker):
    mocker.patch('app.dao.auth_user', return_value=None)
    mock_login = mocker.patch('app.index.login_user')
    mock_render = mocker.patch('app.index.render_template', return_value='Trang HTML Sai Mật Khẩu')

    res = test_client.post('/login', data={'username': 'kh1', 'password': 'trangok'})

    assert res.status_code == 200
    assert res.data.decode('utf-8') == 'Trang HTML Sai Mật Khẩu'
    mock_login.assert_not_called()
    mock_render.assert_called_once_with('login.html', err_msg='Sai tên đăng nhập hoặc mật khẩu')
