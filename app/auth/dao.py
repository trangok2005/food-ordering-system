from datetime import datetime
import secrets

from sqlalchemy import delete, or_, update
from sqlalchemy.exc import IntegrityError
from app.extensions import db
from app.models import (
    AuthProvider,
    OAuthAccount,
    PasswordResetToken,
    User,
    UserRole,
)


def get_user_by_id(user_id):
    return User.query.get(user_id)


def get_user_by_username(username):
    return User.query.filter(User.username == username.strip()).first()


def get_user_by_email(email):
    return User.query.filter(User.email == email.strip()).first()


def get_reset_user(identifier):
    identifier = (identifier or '').strip()
    if not identifier:
        return None
    return (
        User.query
        .filter(
            User.active.is_(True),
            or_(User.username == identifier, User.email == identifier),
        )
        .first()
    )


def get_user_by_oauth(provider, provider_uid):
    account = (
        OAuthAccount.query
        .filter_by(provider=provider, provider_uid=provider_uid)
        .first()
    )
    return account.user if account else None


def _unique_username_from_email(email):
    base = email.split('@')[0].replace('.', '_') or 'google_user'
    base = base[:20]
    candidate = base
    counter = 1
    while get_user_by_username(candidate):
        counter += 1
        candidate = f"{base}{counter}"
    return candidate


def get_or_create_google_user(provider_uid, email, full_name=None, avatar=None):
    provider_uid = str(provider_uid)
    email = (email or '').strip().lower()
    if not provider_uid or not _is_valid_email(email):
        raise ValueError('Thông tin tài khoản Google không hợp lệ')
    full_name = (full_name or '').strip()[:100] or None
    avatar = (avatar or '').strip()[:255] or None

    account = (
        OAuthAccount.query
        .filter_by(provider=AuthProvider.GOOGLE, provider_uid=provider_uid)
        .first()
    )
    if account:
        return account.user

    user = get_user_by_email(email)
    if user:
        db.session.add(OAuthAccount(
            provider=AuthProvider.GOOGLE,
            provider_uid=provider_uid,
            user_id=user.id,
        ))
        db.session.commit()
        return user

    user = User(
        username=_unique_username_from_email(email),
        email=email,
        full_name=full_name,
        avatar=avatar,
        role=UserRole.CUSTOMER,
    )
    user.set_password(secrets.token_urlsafe(24))
    db.session.add(user)
    db.session.flush()
    db.session.add(OAuthAccount(
        provider=AuthProvider.GOOGLE,
        provider_uid=provider_uid,
        user_id=user.id,
    ))
    db.session.commit()
    return user


def auth_user(username, password):
    if not username or not password:
        return None

    username = username.strip()
    user = get_user_by_username(username)
    if user and user.active and user.check_password(password):
        return user
    return None


def register_failed_login(username):
    user = get_user_by_username(username) if username else None
    if user and user.active and not user.is_locked():
        user.register_failed_login()
        db.session.commit()
    return user


def update_profile(user, data):
    phone = (data.get('phone') or '').strip()
    if phone and (not phone.isdigit() or not (10 <= len(phone) <= 11)):
        raise ValueError('Số điện thoại phải từ 10 đến 11 ký số')

    full_name = (data.get('full_name') or '').strip()
    address = (data.get('address') or '').strip()
    avatar = (data.get('avatar') or '').strip()
    if len(full_name) > 100 or len(address) > 255 or len(avatar) > 255:
        raise ValueError('Thông tin hồ sơ vượt quá độ dài cho phép')

    user.full_name = full_name or None
    user.phone = phone or None
    user.address = address or None
    user.avatar = avatar or None
    db.session.commit()
    return user


def change_password(user, current_password, new_password, confirm_password):
    if not user.password:
        raise ValueError(
            'Tài khoản Google chưa đặt mật khẩu nội bộ, '
            'hãy dùng chức năng quên mật khẩu'
        )
    if not user.check_password(current_password or ''):
        raise ValueError('Mật khẩu hiện tại không đúng')
    if (new_password or '') != (confirm_password or ''):
        raise ValueError('Mật khẩu mới không khớp')
    _validate_new_password(new_password)

    user.set_password(new_password)
    db.session.commit()


def _validate_new_password(new_password):
    new_password = new_password or ''
    if len(new_password) < 6:
        raise ValueError('Password tối thiểu 6 ký tự')
    if len(new_password) > 128:
        raise ValueError('Password tối đa 128 ký tự')


def replace_reset_token(user_id, token_digest, expires_at):
    """Xóa token cũ và chỉ lưu mã băm."""
    db.session.execute(
        delete(PasswordResetToken).where(PasswordResetToken.user_id == user_id)
    )
    db.session.add(PasswordResetToken(
        user_id=user_id,
        token_digest=token_digest,
        expires_at=expires_at,
    ))
    db.session.commit()


def invalidate_reset_token(token_digest):
    db.session.execute(
        delete(PasswordResetToken).where(
            PasswordResetToken.token_digest == token_digest
        )
    )
    db.session.commit()


def valid_reset_token_digest(token_digest):
    if not token_digest:
        return False
    now = datetime.now()
    return db.session.query(
        PasswordResetToken.query.filter(
            PasswordResetToken.token_digest == token_digest,
            PasswordResetToken.consumed_at.is_(None),
            PasswordResetToken.expires_at > now,
        ).exists()
    ).scalar()


def reset_password(token_digest, new_password, confirm_password):
    """Dùng token một lần rồi đổi mật khẩu trong cùng giao dịch."""
    if not token_digest:
        raise ValueError('Link đặt lại mật khẩu không hợp lệ')
    if (new_password or '') != (confirm_password or ''):
        raise ValueError('Mật khẩu mới không khớp')
    _validate_new_password(new_password)

    now = datetime.now()
    try:
        reset_token = (
            PasswordResetToken.query
            .filter(PasswordResetToken.token_digest == token_digest)
            .with_for_update()
            .first()
        )
        if not reset_token:
            raise ValueError('Link đặt lại mật khẩu không hợp lệ hoặc đã được dùng')

        consumed = db.session.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.id == reset_token.id,
                PasswordResetToken.consumed_at.is_(None),
                PasswordResetToken.expires_at > now,
            )
            .values(consumed_at=now)
        )
        if consumed.rowcount != 1:
            raise ValueError(
                'Link đặt lại mật khẩu không hợp lệ, đã hết hạn hoặc đã được dùng'
            )

        user = reset_token.user
        user.set_password(new_password)
        user.failed_login_count = 0
        user.locked_until = None
        db.session.commit()
        return user
    except Exception:
        db.session.rollback()
        raise


def _is_valid_email(email):
    if not email or len(email) > 255 or email.count('@') != 1:
        return False
    local, domain = email.rsplit('@', 1)
    return bool(local and '.' in domain and not domain.startswith('.'))


def add_user(
    username, password, email, full_name=None, phone=None, address=None,
    role=UserRole.CUSTOMER,
):
    username = username.strip()
    if not 3 <= len(username) <= 255:
        raise ValueError('Username phải từ 3 đến 255 ký tự')

    _validate_new_password(password)

    email = email.strip().lower()
    if not _is_valid_email(email):
        raise ValueError('Email không hợp lệ')

    if phone:
        phone = phone.strip()
        if not phone.isdigit() or not (10 <= len(phone) <= 11):
            raise ValueError('Số điện thoại phải từ 10 đến 11 ký số')

    if get_user_by_username(username):
        raise ValueError('Username đã tồn tại')

    if get_user_by_email(email):
        raise ValueError('Email đã tồn tại')

    new_user = User(
        username=username,
        email=email,
        full_name=full_name,
        phone=phone,
        address=address,
        role=role,
    )
    new_user.set_password(password)

    try:
        db.session.add(new_user)
        db.session.commit()
        return new_user
    except IntegrityError:
        db.session.rollback()
        raise ValueError('Username hoặc email đã tồn tại')
    except Exception as ex:
        db.session.rollback()
        raise ex
