from flask import render_template, request, abort

from app.browse import browse_bp
from app.browse import dao


@browse_bp.route('/search')
def search_view():
    # Lấy keyword từ URL.
    # Ví dụ: /browse/search?q=pizza
    keyword = request.args.get('q', '')

    # Lấy số trang, mặc định là trang 1
    page = request.args.get(
        'page',
        1,
        type=int
    )

    # Gọi DAO để tìm nhà hàng
    pagination = dao.search(
        keyword,
        page=page
    )

    results = []

    if pagination:
        # Chuyển keyword về chữ thường
        # để so sánh với tên món ăn.
        kw = keyword.strip().lower()

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

    return render_template(
        'browse/search.html',
        keyword=keyword.strip(),
        results=results,
        pagination=pagination
    )


@browse_bp.route('/restaurant/<int:restaurant_id>')
def restaurant_menu_view(restaurant_id):
    # Kiểm tra nhà hàng có tồn tại,
    # đã được duyệt và đang hoạt động hay không.
    restaurant = dao.get_approved_restaurant(
        restaurant_id
    )

    # Không tìm thấy thì trả về 404
    if not restaurant:
        abort(404)

    # Lấy menu của nhà hàng
    menu = dao.get_restaurant_menu(
        restaurant_id
    )

    return render_template(
        'browse/restaurant_menu.html',
        restaurant=restaurant,
        menu=menu
    )