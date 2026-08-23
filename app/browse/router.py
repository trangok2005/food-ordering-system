from flask import render_template, request, abort

from app.browse import browse_bp
from app.browse import dao


@browse_bp.route('/search')
def search_view():
    keyword = request.args.get('q', '')

    page = request.args.get(
        'page',
        1,
        type=int
    )

    if page < 1:
        page = 1

    sort = request.args.get(
        'sort',
        'relevance'
    )

    keyword = keyword.strip()

    if not keyword:
        return render_template(
            'browse/search.html',
            keyword='',
            results=[],
            pagination=None,
            sort=sort,
            message='Vui lòng nhập từ khóa tìm kiếm'
        )

    try:
        pagination = dao.search(
            keyword,
            page=page,
            sort=sort
        )
    except Exception:
        return render_template(
            'browse/search.html',
            keyword=keyword,
            results=[],
            pagination=None,
            sort=sort,
            message='Có lỗi xảy ra trong quá trình tìm kiếm, vui lòng thử lại sau'
        )

    results = []

    if pagination:
        kw = keyword.lower()

        for restaurant in pagination.items:
            matched = [
                d
                for d in restaurant.dishes
                if d.active
                and d.is_available
                and kw in d.name.lower()
            ]

            results.append(
                (restaurant, matched)
            )

    # Không có kết quả
    message = None

    if pagination is not None and pagination.total == 0:
        message = 'Không tìm thấy kết quả phù hợp'

    return render_template(
        'browse/search.html',
        keyword=keyword,
        results=results,
        pagination=pagination,
        sort=sort,
        message=message
    )


@browse_bp.route('/restaurant/<int:restaurant_id>')
def restaurant_menu_view(restaurant_id):
    restaurant = dao.get_approved_restaurant(
        restaurant_id
    )


    if not restaurant:
        abort(404)


    menu = dao.get_restaurant_menu(
        restaurant_id
    )

    return render_template(
        'browse/restaurant_menu.html',
        restaurant=restaurant,
        menu=menu
    )