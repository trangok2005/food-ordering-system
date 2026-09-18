from datetime import datetime, timedelta
import hashlib
import secrets

from flask import current_app, url_for

from app.auth import dao
from app.auth.mailer import send_password_reset


RESET_TOKEN_MINUTES = 30


def _digest(raw_token):
    return hashlib.sha256(raw_token.encode('utf-8')).hexdigest()


def request_password_reset(identifier):
    """Gửi link reset nhưng ko để lộ tài khoản có tồn tại."""
    user = dao.get_reset_user(identifier)
    if not user:
        return

    raw_token = secrets.token_urlsafe(32)
    token_digest = _digest(raw_token)
    dao.replace_reset_token(
        user.id,
        token_digest,
        datetime.now() + timedelta(minutes=RESET_TOKEN_MINUTES),
    )
    reset_path = url_for('auth.reset_password_view', token=raw_token)
    base_url = str(current_app.config.get('APP_BASE_URL') or '').rstrip('/')
    reset_url = (
        f'{base_url}{reset_path}'
        if base_url
        else url_for(
            'auth.reset_password_view', token=raw_token, _external=True
        )
    )
    try:
        send_password_reset(user.email, reset_url)
    except Exception:
        dao.invalidate_reset_token(token_digest)
        # ko ghi token, link hay email người nhận vào log
        current_app.logger.error(
            'Password reset email delivery failed for user_id=%s', user.id
        )


def digest_token(raw_token):
    return _digest(raw_token) if raw_token else None
