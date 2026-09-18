from datetime import datetime, timedelta
import re
from urllib.parse import parse_qs, urlparse

from app import create_app
from app.extensions import db
from app.auth import dao, service
from app.models import PasswordResetToken
from app.test.test_base import app, client, make_user, test_session


GENERIC_MESSAGE = 'Nếu tài khoản tồn tại'.encode('utf-8')


def test_forgot_password_is_generic_and_does_not_leak_token(
    client, app, monkeypatch
):
    user = make_user('reset-user', email='reset@test.vn')
    db.session.commit()
    sent = []
    monkeypatch.setattr(
        service, 'send_password_reset',
        lambda recipient, reset_url: sent.append((recipient, reset_url)),
    )

    existing = client.post(
        '/auth/forgot-password', data={'identifier': user.email},
        follow_redirects=True,
    )
    missing = client.post(
        '/auth/forgot-password', data={'identifier': 'missing@test.vn'},
        follow_redirects=True,
    )

    assert existing.status_code == missing.status_code == 200
    assert GENERIC_MESSAGE in existing.data
    assert GENERIC_MESSAGE in missing.data
    raw_token = parse_qs(urlparse(sent[0][1]).query)['token'][0]
    assert raw_token.encode() not in existing.data
    assert raw_token.encode() not in missing.data
    stored = PasswordResetToken.query.one()
    assert stored.token_digest == service.digest_token(raw_token)
    assert raw_token != stored.token_digest


def test_new_reset_request_invalidates_old_token(client, app, monkeypatch):
    user = make_user('reset-user')
    db.session.commit()
    urls = []
    monkeypatch.setattr(
        service, 'send_password_reset',
        lambda _recipient, reset_url: urls.append(reset_url),
    )

    for _ in range(2):
        client.post('/auth/forgot-password', data={'identifier': user.username})

    old_raw = parse_qs(urlparse(urls[0]).query)['token'][0]
    new_raw = parse_qs(urlparse(urls[1]).query)['token'][0]
    assert PasswordResetToken.query.count() == 1
    assert not dao.valid_reset_token_digest(service.digest_token(old_raw))
    assert dao.valid_reset_token_digest(service.digest_token(new_raw))


def test_reset_token_expiry(client, app, monkeypatch):
    user = make_user('reset-user')
    db.session.commit()
    urls = []
    monkeypatch.setattr(
        service, 'send_password_reset',
        lambda _recipient, reset_url: urls.append(reset_url),
    )
    client.post('/auth/forgot-password', data={'identifier': user.username})
    token = PasswordResetToken.query.one()
    token.expires_at = datetime.now() - timedelta(seconds=1)
    db.session.commit()

    response = client.get(urlparse(urls[0]).path + '?' + urlparse(urls[0]).query)

    assert response.status_code == 400
    assert 'hết hạn'.encode('utf-8') in response.data


def test_reset_token_is_one_time_and_not_rendered(client, app, monkeypatch):
    user = make_user('reset-user', password='old-password')
    db.session.commit()
    urls = []
    monkeypatch.setattr(
        service, 'send_password_reset',
        lambda _recipient, reset_url: urls.append(reset_url),
    )
    client.post('/auth/forgot-password', data={'identifier': user.username})
    parsed = urlparse(urls[0])
    raw_token = parse_qs(parsed.query)['token'][0]

    first_response = client.get(parsed.path + '?' + parsed.query)
    assert raw_token.encode() not in first_response.data
    assert raw_token not in first_response.headers['Location']
    opened = client.get(first_response.headers['Location'])
    assert opened.status_code == 200
    assert raw_token.encode() not in opened.data
    changed = client.post('/auth/reset-password', data={
        'new_password': '  new password  ',
        'confirm_password': '  new password  ',
    })
    assert changed.status_code == 302
    db.session.refresh(user)
    assert user.check_password('  new password  ')

    reused = client.get(parsed.path + '?' + parsed.query)
    assert reused.status_code == 400


def test_logout_requires_post(client, app):
    make_user('logout-user')
    db.session.commit()
    client.post('/auth/login', data={
        'username': 'logout-user', 'password': '123456',
    })

    assert client.get('/auth/logout').status_code == 405
    response = client.post('/auth/logout')
    assert response.status_code == 302
    assert response.headers['Location'].endswith('/auth/login')


def test_logout_form_works_with_application_csrf():
    application = create_app({
        'TESTING': True,
        'SECRET_KEY': 'logout-csrf-test',
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
    })
    with application.app_context():
        db.create_all()
        user = make_user('csrf-logout-user')
        db.session.commit()
        factory_client = application.test_client()

        login_page = factory_client.get('/auth/login')
        csrf_token = re.search(
            rb'name="_csrf_token" value="([^"]+)"', login_page.data
        ).group(1).decode()
        logged_in = factory_client.post('/auth/login', data={
            '_csrf_token': csrf_token,
            'username': user.username,
            'password': '123456',
        })
        assert logged_in.status_code == 302

        profile = factory_client.get('/auth/profile')
        assert b'action="/auth/logout"' in profile.data
        assert b'name="_csrf_token"' in profile.data
        logged_out = factory_client.post('/auth/logout', data={
            '_csrf_token': csrf_token,
        })
        assert logged_out.status_code == 302
        assert logged_out.headers['Location'].endswith('/auth/login')
        db.drop_all()
