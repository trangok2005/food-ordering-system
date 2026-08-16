from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash
from app import db
from app.models import User, UserRole, OAuthAccount, AuthProvider


def get_user_by_id(user_id):
    return User.query.get(user_id)


def get_user_by_username(username):
    return User.query.filter(User.username == username.strip()).first()


def get_user_by_email(email):
    return User.query.filter(User.email == email.strip()).first()


def get_user_by_oauth(provider, provider_uid):
    account = (OAuthAccount.query
               .filter_by(provider=provider, provider_uid=provider_uid)
               .first())
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
    """Tìm user đã liên kết OAuth Google. Nếu chưa có thì tìm theo email
    (link OAuth vào tài khoản nội bộ hiện có), còn không thì tạo user mới."""
    provider_uid = str(provider_uid)
    email = (email or '').strip()

    account = (OAuthAccount.query
               .filter_by(provider=AuthProvider.GOOGLE, provider_uid=provider_uid)
               .first())
    if account:
        return account.user

    user = get_user_by_email(email)
    if user:
        db.session.add(OAuthAccount(provider=AuthProvider.GOOGLE,
                                    provider_uid=provider_uid,
                                    user_id=user.id))
        db.session.commit()
        return user

    import secrets as _secrets
    user = User(
        username=_unique_username_from_email(email),
        email=email,
        full_name=full_name or None,
        avatar=avatar or None,
        role=UserRole.CUSTOMER,
    )
    user.set_password(_secrets.token_urlsafe(24))
    db.session.add(user)
    db.session.flush()
    db.session.add(OAuthAccount(provider=AuthProvider.GOOGLE,
                                provider_uid=provider_uid,
                                user_id=user.id))
    db.session.commit()
    return user


def auth_user(username, password):
    if not username or not password:
        return None

    username = username.strip()
    password = password.strip()
    user = get_user_by_username(username)
    if user and user.check_password(password):
        return user
    return None


def add_user(username, password, email, full_name=None, phone=None, address=None, role=UserRole.CUSTOMER):
    username = username.strip()
    if len(username) < 3:
        raise ValueError('Username tối thiểu 3 ký tự')

    password = password.strip()
    if len(password) < 6:
        raise ValueError('Password tối thiểu 6 ký tự')

    email = email.strip()
    if '@' not in email:
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