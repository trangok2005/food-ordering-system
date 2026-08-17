from flask import Blueprint

restaurant_bp = Blueprint('restaurant', __name__, url_prefix='/restaurant')

from app.restaurant import router