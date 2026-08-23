from sqlalchemy import or_, case

from app.models import (
    Restaurant,
    RestaurantStatus,
    Dish,
    SystemConfig
)

def _page_size():

    value = SystemConfig.get(
        'SEARCH_PAGE_SIZE',
        24,
        cast=int
    )

    if value < 20:
        value = 20

    if value > 30:
        value = 30

    return value


def _normalize_sort(sort):
    allowed_sort = {
        'relevance',
        'name_asc',
        'name_desc'
    }

    if sort not in allowed_sort:
        return 'relevance'

    return sort


def search(keyword, page=1, sort='relevance'):
    """
    Tìm nhà hàng theo từ khóa.
    Từ khóa được tìm trong:
    - Tên nhà hàng
    - Tên món ăn
    Kết quả:
    - Chỉ nhà hàng APPROVED
    - Chỉ nhà hàng active
    - Phân trang 20-30 kết quả/trang
    - Hỗ trợ sắp xếp:
        + relevance
        + name_asc
        + name_desc
    """

    kw = (keyword or '').strip()

    # Không có keyword thì không tìm kiếm
    if not kw:
        return None

    # Chuẩn hóa tiêu chí sort
    sort = _normalize_sort(sort)

    # Tạo pattern tìm kiếm
    search_pattern = f'%{kw}%'

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
                Restaurant.name.ilike(search_pattern),
                Dish.name.ilike(search_pattern)
            )
        )
        # Tránh một nhà hàng xuất hiện nhiều lần
        # khi có nhiều món ăn cùng khớp keyword.
        .distinct()
    )

    if sort == 'name_asc':

        query = query.order_by(
            Restaurant.name.asc()
        )

    elif sort == 'name_desc':

        query = query.order_by(
            Restaurant.name.desc()
        )

    else:

        relevance = case(
            (
                Restaurant.name.ilike(search_pattern),
                0
            ),
            else_=1
        )

        query = query.order_by(
            relevance,
            Restaurant.name.asc()
        )

    return query.paginate(
        page=page,
        per_page=_page_size(),
        error_out=False
    )


def get_approved_restaurant(restaurant_id):

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