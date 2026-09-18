from flask import render_template

from app.extensions import db


def register_error_handlers(app):
    @app.errorhandler(403)
    def forbidden(_error):
        return render_template(
            'errors/error.html',
            code=403,
            title='Không có quyền truy cập',
            message='Bạn không được phép thực hiện thao tác này.',
        ), 403

    @app.errorhandler(404)
    def not_found(_error):
        return render_template(
            'errors/error.html',
            code=404,
            title='Không tìm thấy trang',
            message='Trang bạn tìm không tồn tại hoặc đã bị xóa.',
        ), 404

    @app.errorhandler(500)
    def server_error(_error):
        db.session.rollback()
        return render_template(
            'errors/error.html',
            code=500,
            title='Lỗi hệ thống',
            message='Đã xảy ra lỗi phía máy chủ. Vui lòng thử lại sau.',
        ), 500
