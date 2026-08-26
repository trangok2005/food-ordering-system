import os
import secrets
from urllib.parse import urlencode

import requests
from flask import request, render_template, redirect, url_for, flash, session
from flask_login import login_user, logout_user, current_user, login_required
from app import db
from app.auth import auth_bp
from app.auth import dao
from app.auth.rate_limit import login_rate_limiter

GOOGLE_AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
GOOGLE_TOKEN_URL = 'https://oauth2.googleapis.com/token'
GOOGLE_USERINFO_URL = 'https://www.googleapis.com/oauth2/v3/userinfo'
GOOGLE_SCOPES = 'openid email profile'


def _google_client_id():
    return os.getenv('GOOGLE_CLIENT_ID', '').strip()


def _google_configured():
    return bool(_google_client_id() and os.getenv('GOOGLE_CLIENT_SECRET', '').strip()
                and not _google_client_id().startswith('your_'))


def _redirect_after_login(user):
    """Nhà hàng đăng nhập xong nhảy thẳng vào trang quản lý nhà hàng,
    admin vào trang quản trị, các vai trò khác về trang chủ."""
    if user.role.name == 'RESTAURANT':
        return url_for('restaurant.dashboard')
    if user.role.name == 'ADMIN':
        return url_for('admin.dashboard')
    return url_for('index')


@auth_bp.route('/login', methods=['GET'])
def login_view():
    if current_user.is_authenticated:
        return redirect(_redirect_after_login(current_user))
    return render_template('auth/login.html')


@auth_bp.route('/login', methods=['POST'])
def login_process():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')

    # Chặn dò mật khẩu: tối đa 10 lần thử / 5 phút cho mỗi cặp (IP, username)
    if login_rate_limiter.is_blocked(request.remote_addr, username):
        return render_template(
            'auth/login.html',
            err_msg='Bạn đã thử đăng nhập quá nhiều lần. Vui lòng đợi 5 phút rồi thử lại.')

    user = dao.auth_user(username, password)

    if not user:
        login_rate_limiter.record_failure(request.remote_addr, username)
        return render_template('auth/login.html', err_msg='Sai tên đăng nhập hoặc mật khẩu')

    if user.is_locked():
        return render_template('auth/login.html', err_msg='Tài khoản đã bị khóa do đăng nhập sai quá nhiều lần. Vui lòng thử lại sau 15 phút.')

    login_user(user)
    user.reset_failed_login()
    db.session.commit()
    login_rate_limiter.reset(request.remote_addr, username)

    if user.role.name == 'RESTAURANT':
        return redirect(url_for('restaurant.dashboard'))
    if user.role.name == 'ADMIN':
        return redirect(url_for('admin.dashboard'))
    next_page = request.args.get('next')
    return redirect(next_page if next_page else url_for('index'))


@auth_bp.route('/register', methods=['GET'])
def register_view():
    if current_user.is_authenticated:
        return redirect(_redirect_after_login(current_user))
    return render_template('auth/register.html')


@auth_bp.route('/register', methods=['POST'])
def register_process():
    data = request.form
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    confirm = data.get('confirm', '')
    full_name = data.get('full_name', '').strip()
    phone = data.get('phone', '').strip()
    address = data.get('address', '').strip()

    if password != confirm:
        return render_template('auth/register.html', err_msg='Mật khẩu không khớp')

    try:
        dao.add_user(
            username=username,
            password=password,
            email=email,
            full_name=full_name if full_name else None,
            phone=phone if phone else None,
            address=address if address else None,
        )
        flash('Đăng ký thành công. Vui lòng đăng nhập.')
        return redirect(url_for('auth.login_view'))

    except ValueError as e:
        return render_template('auth/register.html', err_msg=str(e))
    except Exception as e:
        return render_template('auth/register.html', err_msg='Đã xảy ra lỗi, vui lòng thử lại')


@auth_bp.route('/login/google')
def google_login():
    if not _google_configured():
        flash('Chưa cấu hình Google OAuth. Vui lòng điền GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET vào .env', 'error')
        return redirect(url_for('auth.login_view'))

    next_page = request.args.get('next')
    if next_page:
        session['oauth_next'] = next_page

    params = {
        'client_id': _google_client_id(),
        'redirect_uri': url_for('auth.google_callback', _external=True),
        'response_type': 'code',
        'scope': GOOGLE_SCOPES,
        'state': secrets.token_urlsafe(32),
    }
    session['oauth_state'] = params['state']
    return redirect(f'{GOOGLE_AUTH_URL}?{urlencode(params)}')


@auth_bp.route('/login/google/callback')
def google_callback():
    if request.args.get('error'):
        flash(f'Đăng nhập Google thất bại: {request.args.get("error")}', 'error')
        return redirect(url_for('auth.login_view'))

    code = request.args.get('code')
    state = request.args.get('state')
    if not code or state != session.pop('oauth_state', None):
        flash('Yêu cầu đăng nhập Google không hợp lệ', 'error')
        return redirect(url_for('auth.login_view'))

    client_id = _google_client_id()
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET', '').strip()
    redirect_uri = url_for('auth.google_callback', _external=True)

    token_resp = requests.post(GOOGLE_TOKEN_URL, data={
        'code': code,
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code',
    }, timeout=15)
    token_data = token_resp.json()
    access_token = token_data.get('access_token')
    if not access_token:
        flash('Không lấy được token từ Google', 'error')
        return redirect(url_for('auth.login_view'))

    userinfo_resp = requests.get(GOOGLE_USERINFO_URL,
                                 headers={'Authorization': f'Bearer {access_token}'},
                                 timeout=15)
    info = userinfo_resp.json()
    if not info.get('sub') or not info.get('email'):
        flash('Không lấy được thông tin tài khoản Google', 'error')
        return redirect(url_for('auth.login_view'))

    try:
        user = dao.get_or_create_google_user(
            info['sub'], info['email'],
            full_name=info.get('name'), avatar=info.get('picture'))
    except Exception:
        db.session.rollback()
        flash('Đã xảy ra lỗi khi liên kết tài khoản Google', 'error')
        return redirect(url_for('auth.login_view'))

    login_user(user)
    user.reset_failed_login()
    db.session.commit()

    if user.role.name == 'RESTAURANT':
        return redirect(url_for('restaurant.dashboard'))
    if user.role.name == 'ADMIN':
        return redirect(url_for('admin.dashboard'))
    next_page = session.pop('oauth_next', '')
    return redirect(next_page if next_page else url_for('index'))


@auth_bp.route('/logout')
def logout_process():
    logout_user()
    return redirect(url_for('auth.login_view'))


# ---------- HỒ SƠ & MẬT KHẨU ----------

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile_view():
    """Xem và cập nhật hồ sơ cá nhân + đổi mật khẩu."""
    if request.method == 'POST':
        action = request.form.get('action')

        try:
            if action == 'change_password':
                dao.change_password(current_user,
                                    request.form.get('current_password'),
                                    request.form.get('new_password'),
                                    request.form.get('confirm_password'))
                flash('Đã đổi mật khẩu thành công')
            else:
                dao.update_profile(current_user, request.form)
                flash('Đã cập nhật hồ sơ')
        except ValueError as e:
            flash(str(e), 'error')

        return redirect(url_for('auth.profile_view'))

    return render_template('auth/profile.html')


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password_view():
    """Yêu cầu đặt lại mật khẩu: nhập username hoặc email.
    Hệ thống sinh token một lần (hết hạn 30 phút). Vì demo chạy local
    không có SMTP, link đặt lại được hiển thị trực tiếp trên màn hình."""
    reset_url = None

    if request.method == 'POST':
        user, token = dao.create_reset_token(request.form.get('identifier'))
        if user and token:
            reset_url = url_for('auth.reset_password_view',
                                token=token, _external=True)

    return render_template('auth/forgot_password.html', reset_url=reset_url)


@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password_view():
    token = request.args.get('token') or request.form.get('token', '')

    if request.method == 'POST':
        try:
            dao.reset_password(token,
                               request.form.get('new_password'),
                               request.form.get('confirm_password'))
            flash('Đặt lại mật khẩu thành công. Vui lòng đăng nhập.')
            return redirect(url_for('auth.login_view'))
        except ValueError as e:
            return render_template('auth/reset_password.html',
                                   err_msg=str(e), token=token)

    return render_template('auth/reset_password.html', token=token)
