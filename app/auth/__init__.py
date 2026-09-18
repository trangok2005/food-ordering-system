from flask import Blueprint
from app.extensions import login


auth_bp = Blueprint('auth',__name__,url_prefix='/auth')


@login.user_loader
def load_user(user_id):
    from app.auth import dao

    user = dao.get_user_by_id(user_id)
    return user if user and user.active else None


from app.auth import router
