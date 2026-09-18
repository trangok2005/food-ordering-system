from sqlalchemy import and_, case, or_
from sqlalchemy.orm import selectinload

from app.models import (
    Restaurant,
    RestaurantStatus,
    Dish,
    SystemConfig
)


def _page_size():
    return SystemConfig.get('SEARCH_PAGE_SIZE', 24, cast=int)


def search(keyword, page=1, sort='relevance'):
    kw = (keyword or '').strip()

    if not kw:
        return None

    like = f'%{kw}%'
    dish_match = and_(
        Dish.name.ilike(like),
        Dish.active.is_(True),
        Dish.is_available.is_(True),
    )
    query = (
        Restaurant.query
        .options(selectinload(Restaurant.dishes))
        .outerjoin(Dish, Dish.restaurant_id == Restaurant.id)
        .filter(
            Restaurant.status == RestaurantStatus.APPROVED,
            Restaurant.active.is_(True),
            or_(
                Restaurant.name.ilike(like),
                dish_match,
            )
        )
        # nhiều món khớp vẫn chỉ lấy nhà hàng một lần
        .distinct()
    )

    if sort == 'name_desc':
        query = query.order_by(Restaurant.name.desc())
    elif sort == 'name_asc':
        query = query.order_by(Restaurant.name.asc())
    else:
        query = query.order_by(
            case((Restaurant.name.ilike(like), 0), else_=1),
            Restaurant.name.asc(),
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
        .order_by(Dish.category_id, Dish.name)
        .all()
    )
