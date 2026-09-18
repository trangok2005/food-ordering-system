import pytest
import requests

from app.auth import dao as auth_dao
from app.models import UserRole
from app.test.test_base import app, client, test_session, make_user, login


@pytest.fixture
def setup_users(test_session):
    customer = make_user('kh1', full_name='Khách 1')
    inactive = make_user('duy', active=False)
    admin = make_user('admin', role=UserRole.ADMIN)
    return customer, inactive, admin



def test_auth_user_success(setup_users):
    result = auth_dao.auth_user('kh1', '123456')
    assert result is not None
    assert result.username == 'kh1'


def test_auth_user_wrong_password(setup_users):
    assert auth_dao.auth_user('kh1', '111111') is None


def test_auth_user_wrong_username(setup_users):
    assert auth_dao.auth_user('khongco', '123456') is None


@pytest.mark.parametrize('username, password', [
    (None, '123456'),
    ('kh1', None),
    (None, None),
    ('', '123456'),
    ('kh1', ''),
])
def test_auth_user_empty_inputs(username, password, setup_users):
    assert auth_dao.auth_user(username, password) is None


def test_auth_user_does_not_strip_password(setup_users):
    assert auth_dao.auth_user('  kh1  ', '  123456  ') is None


def test_auth_user_returns_user_object(setup_users):
    customer, _, _ = setup_users
    assert auth_dao.auth_user('kh1', '123456').id == customer.id



def test_get_login_page_renders(client, app):
    res = client.get('/auth/login')
    assert res.status_code == 200
    assert b'login' in res.data or b'form' in res.data


def test_get_login_redirects_when_authenticated(client, app, setup_users):
    login(client, username='kh1')
    res = client.get('/auth/login')
    assert res.status_code == 302
    assert res.headers['Location'] == '/'



def test_login_success_customer(client, app, setup_users):
    res = login(client, username='kh1')
    assert res.status_code == 302
    assert res.headers['Location'] == '/'


def test_login_success_customer_with_next(client, app, setup_users):
    res = client.post('/auth/login?next=/cart/',
                      data={'username': 'kh1', 'password': '123456'})
    assert res.status_code == 302
    assert res.headers['Location'] == '/cart/'


def test_login_success_admin_goes_to_admin(client, app, setup_users):
    res = login(client, username='admin')
    assert res.status_code == 302
    assert res.headers['Location'] == '/admin/'


def test_login_success_restaurant_goes_to_dashboard(client, app):
    make_user('owner', role=UserRole.RESTAURANT)
    res = login(client, username='owner')
    assert res.status_code == 302
    assert res.headers['Location'] == '/restaurant/'


def test_login_failed_wrong_credentials(client, app, setup_users):
    res = client.post('/auth/login',
                      data={'username': 'kh1', 'password': 'sai'})
    assert res.status_code == 200
    assert 'Sai tên đăng nhập hoặc mật khẩu'.encode('utf-8') in res.data


def test_login_locked_account_blocked(client, app, setup_users):
    customer, _, _ = setup_users
    from datetime import datetime, timedelta
    customer.locked_until = datetime.now() + timedelta(minutes=15)
    from app import db
    db.session.commit()

    res = client.post('/auth/login',
                      data={'username': 'kh1', 'password': '123456'})
    assert res.status_code == 200
    assert 'bị khóa'.encode('utf-8') in res.data


def test_google_login_clears_stale_session_when_unconfigured(
    client, app, monkeypatch
):
    monkeypatch.delenv('GOOGLE_CLIENT_ID', raising=False)
    monkeypatch.delenv('GOOGLE_CLIENT_SECRET', raising=False)
    with client.session_transaction() as auth_session:
        auth_session['oauth_state'] = 'stale-state'
        auth_session['oauth_next'] = '/cart/'

    response = client.get('/auth/login/google')

    assert response.status_code == 302
    with client.session_transaction() as auth_session:
        assert 'oauth_state' not in auth_session
        assert 'oauth_next' not in auth_session


def test_google_callback_handles_network_error_and_clears_session(
    client, app, monkeypatch
):
    monkeypatch.setenv('GOOGLE_CLIENT_ID', 'configured-client')
    monkeypatch.setenv('GOOGLE_CLIENT_SECRET', 'configured-secret')
    monkeypatch.setattr(
        'app.auth.router.requests.post',
        lambda *args, **kwargs: (_ for _ in ()).throw(requests.Timeout()),
    )
    with client.session_transaction() as auth_session:
        auth_session['oauth_state'] = 'expected-state'
        auth_session['oauth_next'] = '/cart/'

    response = client.get(
        '/auth/login/google/callback?code=code&state=expected-state'
    )

    assert response.status_code == 302
    assert response.headers['Location'].endswith('/auth/login')
    with client.session_transaction() as auth_session:
        assert 'oauth_state' not in auth_session
        assert 'oauth_next' not in auth_session
