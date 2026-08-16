from flask import render_template, request, abort

from app.browse import browse_bp
from app.browse import dao


@browse_bp.route('/search')
def search_view():
    keyword = request.args.get('q', '')
    page = request.args.get('page', 1, type=int)
    pagination = dao.search(keyword, page=page)

    results = []
    if pagination:
        kw = keyword.strip().lower()
        for restaurant in pagination.items:
            matched = [d for d in restaurant.dishes
                       if d.active and d.is_available and kw in d.name.lower()]
            results.append((restaurant, matched))

    return render_template('browse/search.html',
                           keyword=keyword.strip(),
                           results=results,
                           pagination=pagination)


@browse_bp.route('/restaurant/<int:restaurant_id>')
def restaurant_menu_view(restaurant_id):
    restaurant = dao.get_approved_restaurant(restaurant_id)
    if not restaurant:
        abort(404)
    menu = dao.get_restaurant_menu(restaurant_id)
    return render_template('browse/restaurant_menu.html',
                           restaurant=restaurant,
                           menu=menu)