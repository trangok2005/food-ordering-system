from flask import render_template


def register_routers(app):

    def _vnd(value):
        return f"{value:,.0f}".replace(",", ".") + "đ"

    app.jinja_env.filters['vnd'] = _vnd

    @app.route('/')
    def index():
        from app.models import Restaurant, RestaurantStatus

        try:
            restaurants = (Restaurant.query
                           .filter(Restaurant.status == RestaurantStatus.APPROVED,
                                   Restaurant.active == True)
                           .all())
        except Exception:
            restaurants = []

        return render_template('index.html', restaurants=restaurants)
