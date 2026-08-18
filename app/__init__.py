from flask import Flask, session
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
