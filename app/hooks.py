import secrets

from flask import abort, request, session


def register_hooks(app):
    @app.template_global()
    def csrf_token():
        return session.setdefault('_csrf_token', secrets.token_urlsafe(32))

    @app.before_request
    def validate_csrf():
        if request.method != 'POST' or request.endpoint == 'cart.payment_webhook':
            return None
        expected = session.get('_csrf_token')
        supplied = request.form.get('_csrf_token') or request.headers.get('X-CSRF-Token')
        if not expected or not supplied or not secrets.compare_digest(expected, supplied):
            abort(400, description='Yêu cầu không có mã chống giả mạo hợp lệ.')

    @app.after_request
    def secure_response(response):
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        return response
