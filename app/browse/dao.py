from sqlalchemy import or_

from app.models import (
    Restaurant,
    RestaurantStatus,
    Dish,
    SystemConfig
)

def _page_size():
    # Lấy số lượng kết quả hiển thị trên mỗi trang.
    # Nếu chưa cấu hình thì mặc định là 24.
    return SystemConfig.get(
        'SEARCH_PAGE_SIZE',
        24,
        cast=int
    )


def search(keyword, page=1):
    """
    Tìm nhà hàng theo từ khóa.

    Từ khóa được tìm trong:
    - Tên nhà hàng
    - Tên món ăn
    """

    # Xóa khoảng trắng thừa ở đầu và cuối keyword
    kw = (keyword or '').strip()

    # Không có keyword thì không tìm kiếm
    if not kw:
        return None

    query = (
        Restaurant.query
        .outerjoin(
            Dish,
            Dish.restaurant_id == Restaurant.id
        )
        .filter(
            Restaurant.status == RestaurantStatus.APPROVED,
            Restaurant.active == True,
            or_(
                Restaurant.name.ilike(f'%{kw}%'),
                Dish.name.ilike(f'%{kw}%')
            )
        )
        # Tránh một nhà hàng xuất hiện nhiều lần
        # khi có nhiều món ăn cùng khớp keyword.
        .distinct()
        .order_by(Restaurant.name)
    )

    return query.paginate(
        page=page,
        per_page=_page_size(),
        error_out=False
    )

def get_approved_restaurant(restaurant_id):
    # Chỉ lấy nhà hàng đã được duyệt
    # và đang hoạt động.
    return (
        Restaurant.query
        .filter(
            Restaurant.id == restaurant_id,
            Restaurant.status == RestaurantStatus.APPROVED,
            Restaurant.active == True
        )
        .first()
    )

def get_restaurant_menu(restaurant_id):
    # Chỉ lấy những món:
    # - Thuộc nhà hàng
    # - Đang hoạt động
    # - Đang có sẵn để bán
    return (
        Dish.query
        .filter(
            Dish.restaurant_id == restaurant_id,
            Dish.active == True,
            Dish.is_available == True
        )
        .order_by(
            Dish.category_id,
            Dish.name
        )
        .all()
    )