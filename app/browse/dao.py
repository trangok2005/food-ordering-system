from sqlalchemy import or_

from app.models import Restaurant, RestaurantStatus, Dish, SystemConfig


def _page_size():
    return SystemConfig.get('SEARCH_PAGE_SIZE', 24, cast=int)


def search(keyword, page=1):
    """Tìm nhà hàng theo 1 từ khóa duy nhất: áp dụng đồng thời cho tên
    nhà hàng VÀ tên món ăn. Trả về Pagination các nhà hàng khớp."""
    kw = (keyword or '').strip()
    if not kw:
        return None

    query = (
        Restaurant.query
        .outerjoin(Dish, Dish.restaurant_id == Restaurant.id)
        .filter(Restaurant.status == RestaurantStatus.APPROVED,
                Restaurant.active == True,
                or_(Restaurant.name.ilike(f'%{kw}%'),
                    Dish.name.ilike(f'%{kw}%')))
        .distinct()
        .order_by(Restaurant.name)
    )
    return query.paginate(page=page, per_page=_page_size(), error_out=False)


def get_approved_restaurant(restaurant_id):
    return (Restaurant.query
            .filter(Restaurant.id == restaurant_id,
                    Restaurant.status == RestaurantStatus.APPROVED,
                    Restaurant.active == True)
            .first())


def get_restaurant_menu(restaurant_id):
    return (Dish.query
            .filter(Dish.restaurant_id == restaurant_id,
                    Dish.active == True,
                    Dish.is_available == True)
            .order_by(Dish.category_id, Dish.name)
            .all())