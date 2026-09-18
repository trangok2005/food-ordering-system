import os
import secrets
import warnings
from urllib.parse import urlsplit

import click
from dotenv import load_dotenv
from flask import Flask, jsonify
from sqlalchemy.engine import URL
from werkzeug.middleware.proxy_fix import ProxyFix

from app.extensions import db, login, migrate


load_dotenv()

__all__ = ['create_app', 'db', 'login', 'migrate']


def _is_true(value):
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


def _is_production(config):
    return (
        str(config.get('APP_ENV', '')).lower() == 'production'
        or str(os.getenv('FLASK_ENV', '')).lower() == 'production'
        or _is_true(os.getenv('RENDER', ''))
    )


def _database_uri(production):
    database_url = os.getenv('DATABASE_URL', '').strip()
    if database_url:
        return database_url

    names = (
        'DATABASE_USERNAME', 'DATABASE_PASSWORD', 'DATABASE_HOST',
        'DATABASE_PORT', 'DATABASE_NAME',
    )
    values = {name: os.getenv(name, '').strip() for name in names}
    missing = [name for name, value in values.items() if not value]
    if missing:
        if production:
            raise RuntimeError(
                'Production requires DATABASE_URL or all DATABASE_* settings; '
                f'missing: {", ".join(missing)}'
            )
        warnings.warn('Database is not configured; using local SQLite for development.')
        return 'sqlite:///food-ordering.db'

    try:
        port = int(values['DATABASE_PORT'])
    except ValueError as error:
        raise RuntimeError('DATABASE_PORT must be an integer.') from error
    return URL.create(
        'mysql+pymysql',
        username=values['DATABASE_USERNAME'],
        password=values['DATABASE_PASSWORD'],
        host=values['DATABASE_HOST'],
        port=port,
        database=values['DATABASE_NAME'],
        query={'charset': 'utf8mb4'},
    )


def _configure_app(app, test_config):
    app_env = os.getenv('APP_ENV', 'development').strip().lower()
    app.config.update(
        APP_ENV=app_env,
        APP_BASE_URL=os.getenv('APP_BASE_URL', '').strip().rstrip('/'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE=os.getenv('SESSION_COOKIE_SAMESITE', 'Lax'),
        PAGE_SIZE=9,
    )
    if test_config:
        app.config.update(test_config)

    production = _is_production(app.config) and not app.config.get('TESTING')
    secret_key = str(app.config.get('SECRET_KEY') or os.getenv('SECRET_KEY', '')).strip()
    if production and (
        len(secret_key) < 32 or secret_key.lower().startswith('replace_with')
    ):
        raise RuntimeError('Production requires a non-placeholder SECRET_KEY of 32+ characters.')
    if not secret_key:
        secret_key = secrets.token_hex(32)
        warnings.warn('SECRET_KEY is not configured; sessions reset after restart.')

    base_url = str(app.config.get('APP_BASE_URL', '')).strip().rstrip('/')
    if production:
        parsed = urlsplit(base_url)
        if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
            raise RuntimeError('Production requires an absolute APP_BASE_URL.')

    cookie_secure = os.getenv('SESSION_COOKIE_SECURE')
    app.config.update(
        SECRET_KEY=secret_key,
        APP_BASE_URL=base_url,
        PRODUCTION=production,
        SQLALCHEMY_DATABASE_URI=(
            app.config.get('SQLALCHEMY_DATABASE_URI') or _database_uri(production)
        ),
        SESSION_COOKIE_SECURE=(production if cookie_secure is None else _is_true(cookie_secure)),
        PREFERRED_URL_SCHEME='https' if production else 'http',
    )
    return production


def _register_blueprints(app):
    from app.auth import auth_bp
    from app.browse import browse_bp
    from app.cart import cart_bp
    from app.restaurant import restaurant_bp
    from app.admin import admin_bp
    from app.ai import ai_bp

    for blueprint in (auth_bp, browse_bp, cart_bp, restaurant_bp, admin_bp, ai_bp):
        app.register_blueprint(blueprint)


def create_app(test_config=None):
    app = Flask(__name__)
    production = _configure_app(app, test_config)
    if production:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    migrate.init_app(app, db)
    login.init_app(app)
    login.login_view = 'auth.login_view'

    _register_blueprints(app)

    from app import index
    from app.context import register_context_processors
    from app.errors import register_error_handlers
    from app.hooks import register_hooks

    index.register_routers(app)
    register_context_processors(app)
    register_error_handlers(app)
    register_hooks(app)

    @app.get('/health')
    def health():
        return jsonify(status='ok', service='food-ordering-system')

    @app.cli.command('expire-orders')
    def expire_orders_command():
        from app.restaurant.dao import expire_all_overdue_orders

        count = expire_all_overdue_orders()
        click.echo(f'Đã chuyển {count} đơn quá hạn sang EXPIRED.')

    return app
