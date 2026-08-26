from flask import Flask, session, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
import cloudinary
from dotenv import load_dotenv
import os

load_dotenv()

DATABASE_USERNAME = os.getenv("DATABASE_USERNAME")
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD")
DATABASE_HOST = os.getenv("DATABASE_HOST")
DATABASE_NAME = os.getenv("DATABASE_NAME")
DATABASE_PORT = os.getenv("DATABASE_PORT")


db = SQLAlchemy()
login = LoginManager()

def create_app():

    app = Flask(__name__)
    app.secret_key = 'trangdeptraicomotkohaip@ok'

    app.config["SQLALCHEMY_DATABASE_URI"] = (
        f"mysql+pymysql://{os.environ['DATABASE_USERNAME']}:{os.environ['DATABASE_PASSWORD']}"
        f"@{os.environ['DATABASE_HOST']}:{os.environ['DATABASE_PORT']}/{os.environ['DATABASE_NAME']}?charset=utf8mb4"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = True
    app.config["PAGE_SIZE"] = 9

    db.init_app(app)
    login.init_app(app)
    login.login_view = 'auth.login_view'

    from app.auth import auth_bp
    app.register_blueprint(auth_bp)

    from app.browse import browse_bp
    app.register_blueprint(browse_bp)

    from app.cart import cart_bp
    app.register_blueprint(cart_bp)

    from app.restaurant import restaurant_bp
    app.register_blueprint(restaurant_bp)

    from app.admin import admin_bp
    app.register_blueprint(admin_bp)

    from app.ai import ai_bp
    app.register_blueprint(ai_bp)

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template('errors/error.html',
                               code=403,
                               title='Không có quyền truy cập',
                               message='Bạn không được phép thực hiện thao tác này.'), 403

    @app.errorhandler(404)
    def not_found(_error):
        return render_template('errors/error.html',
                               code=404,
                               title='Không tìm thấy trang',
                               message='Trang bạn tìm không tồn tại hoặc đã bị xóa.'), 404

    @app.errorhandler(500)
    def server_error(_error):
        db.session.rollback()
        return render_template('errors/error.html',
                               code=500,
                               title='Lỗi hệ thống',
                               message='Đã xảy ra lỗi phía máy chủ. Vui lòng thử lại sau.'), 500

    from app import index
    index.register_routers(app)

    @app.context_processor
    def inject_common():
        from app.models import Category
        from app.cart import dao as cart_dao
        try:
            categories = Category.query.all()
        except Exception:
            categories = []
        try:
            if current_user.is_authenticated:
                cart_stats = cart_dao.get_cart_stats(current_user.id)
            else:
                cart_stats = {'total_quantity': 0, 'total_amount': 0}
        except Exception:
            cart_stats = {'total_quantity': 0, 'total_amount': 0}
        return {
            'categories': categories,
            'cart_stats': cart_stats,
        }

    return app
