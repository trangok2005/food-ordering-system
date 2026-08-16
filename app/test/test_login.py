import pytest
from app.test.test_base import test_client, test_session
from app.auth.dao import auth_user
from app.models import User, UserRole


def _make_user(test_session, **kwargs):
    username = kwargs.pop('username', 'kh1')
    password = kwargs.pop('password', '123456')
    email_base = kwargs.pop('email_base', 'user')
    email = f'{email_base}@example.com'
    phone = kwargs.pop('phone', '0901234567')
    address = kwargs.pop('address', '123 Nguyễn Huệ')
    role = kwargs.pop('role', UserRole.USER)
    user = User(
        username=username,
        email=email,
        phone=phone,
        address=address,
        role=role,
    )
    user.set_password(password)
    test_session.add(user)
    test_session.commit()
    return user


@pytest.fixture
def setup_users(test_session):
    customer = _make_user(test_session, username='kh1', email_base='kh1', role=UserRole.USER)
    inactive = _make_user(test_session, username='duy', email_base='duy', password='123456', role=UserRole.USER, active=False)
    admin = _make_user(test_session, username='admin', email_base='admin', password='admin123', role=UserRole.ADMIN)
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
    mocker.patch('app.auth.dao.auth_user', return_value=customer)
    mock_login = mocker.patch('app.index.login_user')

    res = test_client.post('/login', data={'username': 'kh1', 'password': '123456'})

    assert res.status_code == 302
    assert res.headers['Location'] == '/'
    mock_login.assert_called_once()


def test_login_success_customer_with_next(test_client, setup_users, mocker):
    customer, _, _ = setup_users
    mocker.patch('app.auth.dao.auth_user', return_value=customer)
    mocker.patch('app.index.login_user')

    res = test_client.post('/login?next=/api/pay', data={'username': 'kh1', 'password': '123456'})

    assert res.status_code == 302
    assert res.headers['Location'] == '/api/pay'


def test_login_success_admin_always_to_admin(test_client, setup_users, mocker):
    _, _, admin = setup_users
    mocker.patch('app.auth.dao.auth_user', return_value=admin)
    mocker.patch('app.index.login_user')

    res = test_client.post('/login?next=/api/pay', data={'username': 'admin_sushi', 'password': 'admin123'})

    assert res.status_code == 302
    assert res.headers['Location'] == '/admin'


def test_login_failed_wrong_credentials(test_client, setup_users, mocker):
    mocker.patch('app.auth.dao.auth_user', return_value=None)
    mock_login = mocker.patch('app.index.login_user')
    mock_render = mocker.patch('app.index.render_template', return_value='Trang HTML Sai Mật Khẩu')

    res = test_client.post('/login', data={'username': 'kh1', 'password': 'trangok'})

    assert res.status_code == 200
    assert res.data.decode('utf-8') == 'Trang HTML Sai Mật Khẩu'
    mock_login.assert_not_called()
    mock_render.assert_called_once_with('login.html', err_msg='Sai tên đăng nhập hoặc mật khẩu')
