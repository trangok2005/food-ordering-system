from flask import render_template, request, abort, flash

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

    # Kiểm tra page hợp lệ
    if page is None or page < 1:
        flash(
            'Số trang không hợp lệ. Hệ thống đã chuyển về trang đầu tiên.',
            'warning'
        )
        page = 1

    try:
        # Gọi DAO để tìm nhà hàng
        pagination = dao.search(
            keyword,
            page=page
        )

    except Exception:
        # Không để lỗi database làm văng trang Browse
        flash(
            'Không thể thực hiện tìm kiếm lúc này. Vui lòng thử lại sau.',
            'danger'
        )

        return render_template(
            'browse/search.html',
            keyword=keyword.strip(),
            results=[],
            pagination=None
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

        # Không tìm thấy nhà hàng phù hợp
        if not results:
            flash(
                f'Không tìm thấy nhà hàng hoặc món ăn phù hợp với "{keyword.strip()}".',
                'info'
            )

    else:
        # Người dùng không nhập keyword
        flash(
            'Vui lòng nhập tên nhà hàng hoặc tên món ăn để tìm kiếm.',
            'warning'
        )

    return render_template(
        'browse/search.html',
        keyword=keyword.strip(),
        results=results,
        pagination=pagination
    )


@browse_bp.route('/restaurant/<int:restaurant_id>')
def restaurant_menu_view(restaurant_id):
    try:
        # Kiểm tra nhà hàng có tồn tại,
        # đã được duyệt và đang hoạt động hay không.
        restaurant = dao.get_approved_restaurant(
            restaurant_id
        )

    except Exception:
        # Lỗi truy vấn database
        flash(
            'Không thể tải thông tin nhà hàng. Vui lòng thử lại sau.',
            'danger'
        )
        abort(500)

    # Không tìm thấy thì trả về 404
    if not restaurant:
        flash(
            'Nhà hàng không tồn tại, chưa được duyệt hoặc hiện không hoạt động.',
            'warning'
        )
        abort(404)

    try:
        # Lấy menu của nhà hàng
        menu = dao.get_restaurant_menu(
            restaurant_id
        )

    except Exception:
        # Lỗi khi lấy menu
        flash(
            'Không thể tải thực đơn của nhà hàng. Vui lòng thử lại sau.',
            'danger'
        )

        return render_template(
            'browse/restaurant_menu.html',
            restaurant=restaurant,
            menu=[]
        )

    # Nhà hàng tồn tại nhưng hiện chưa có món đang bán
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