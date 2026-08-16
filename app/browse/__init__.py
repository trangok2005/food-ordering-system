from flask import Blueprint

browse_bp = Blueprint(
    'browse',
    __name__,
    url_prefix='/browse'
)

from app.browse import router