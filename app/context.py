from flask_login import current_user


def register_context_processors(app):
    @app.context_processor
    def inject_common():
        from app.cart import dao as cart_dao
        from app.models import Category

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
        return {'categories': categories, 'cart_stats': cart_stats}
