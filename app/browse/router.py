from flask import render_template, request, abort, flash

from app.browse import browse_bp
from app.browse import dao


@browse_bp.route('/search')
def search_view():
    keyword = request.args.get('q', '')
    sort = request.args.get('sort', 'relevance')
    if sort not in ('relevance', 'name_asc', 'name_desc'):
        sort = 'relevance'

    page = request.args.get('page', 1, type=int)

    if page is None or page < 1:
        flash(
            'Số trang không hợp lệ. Hệ thống đã chuyển về trang đầu tiên.',
            'warning'
        )
        page = 1

    pagination = dao.search(keyword, page=page, sort=sort)

    results = []

    if pagination:
        kw = keyword.strip().lower()

        for restaurant in pagination.items:
            matched = [
                d
                for d in restaurant.dishes
                if d.active
                and d.is_available
                and kw in d.name.lower()
            ]

            results.append((restaurant, matched))

        if not results:
            flash(
                f'Không tìm thấy nhà hàng hoặc món ăn phù hợp với "{keyword.strip()}".',
                'info'
            )

    else:
        flash(
            'Vui lòng nhập tên nhà hàng hoặc tên món ăn để tìm kiếm.',
            'warning'
        )

    return render_template(
        'browse/search.html',
        keyword=keyword.strip(),
        results=results,
        pagination=pagination,
        sort=sort
    )


@browse_bp.route('/restaurant/<int:restaurant_id>')
def restaurant_menu_view(restaurant_id):
    restaurant = dao.get_approved_restaurant(restaurant_id)

    if not restaurant:
        flash(
            'Nhà hàng không tồn tại, chưa được duyệt hoặc hiện không hoạt động.',
            'warning'
        )
        abort(404)

    menu = dao.get_restaurant_menu(restaurant_id)

    if not menu:
        flash(
            'Nhà hàng hiện chưa có món ăn nào đang được bán.',
            'info'
        )

    return render_template(
        'browse/restaurant_menu.html',
        restaurant=restaurant,
        menu=menu
    )
