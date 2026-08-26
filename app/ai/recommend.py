from collections import defaultdict
from datetime import datetime

from app import db
from app.models import (Category, Dish, OrderDetail, Order, OrderStatus,
                        UserDishInteraction)



INTERACTION_WEIGHTS = {
    'ORDER': 3.0,
    'ADD_TO_CART': 2.0,
    'REVIEW': 2.0,
    'VIEW': 1.0,
}


HOUR_WINDOW_HOURS = 2
HOUR_MATCH_BONUS = 0.5


CATEGORY_AFFINITY_RATIO = 0.5


def _score_interactions(interactions):
    """Trả về (dish_scores, category_scores, hour_map)."""
    dish_scores = defaultdict(float)
    category_scores = defaultdict(float)
    hour_map = defaultdict(set)

    for it in interactions:
        weight = INTERACTION_WEIGHTS.get(it.interaction_type, 1.0)
        dish_scores[it.dish_id] += weight
        hour_map[it.dish_id].add(it.hour_of_day)

        dish = Dish.query.get(it.dish_id)
        if dish and dish.category_id:
            category_scores[dish.category_id] += weight * CATEGORY_AFFINITY_RATIO

    return dish_scores, category_scores, hour_map


def _hour_bonus(hour_map_for_dish, now_hour):
    """Cộng thưởng nếu user thường tương tác món này đúng khung giờ hiện tại."""
    if not hour_map_for_dish:
        return 0.0
    for h in hour_map_for_dish:
        if h is not None and abs(h - now_hour) <= HOUR_WINDOW_HOURS:
            return HOUR_MATCH_BONUS
    return 0.0


def _available_query():
    from app.models import Restaurant, RestaurantStatus
    return (Dish.query
            .join(Restaurant, Dish.restaurant_id == Restaurant.id)
            .filter(Dish.active == True,               # noqa: E712
                    Dish.is_available == True,          # noqa: E712
                    Restaurant.status == RestaurantStatus.APPROVED,
                    Restaurant.is_open == True))        # noqa: E712


def get_popular_dishes(limit=8, exclude_ids=None):
    exclude_ids = set(exclude_ids or [])
    rows = (_available_query()
            .with_entities(Dish,
                           db.func.coalesce(db.func.sum(OrderDetail.quantity), 0)
                           .label('total_qty'))
            .outerjoin(OrderDetail, OrderDetail.dish_id == Dish.id)
            .outerjoin(Order, db.and_(Order.id == OrderDetail.order_id,
                                      Order.status.in_([OrderStatus.COMPLETED,
                                                        OrderStatus.DELIVERING])))
            .group_by(Dish.id)
            .order_by(db.desc('total_qty'), Dish.name)
            .limit(limit + len(exclude_ids))
            .all())
    return [dish for dish, _qty in rows if dish.id not in exclude_ids][:limit]


def recommend_dishes_for_user(user_id, limit=8):
    interactions = (UserDishInteraction.query
                    .filter(UserDishInteraction.user_id == user_id)
                    .all())

    if not interactions:
        return [], get_popular_dishes(limit)

    now_hour = datetime.now().hour
    dish_scores, category_scores, hour_map = _score_interactions(interactions)

    scored = []
    seen_categories_boosted = set()
    for dish in _available_query().all():
        base = dish_scores.get(dish.id, 0.0)
        affinity = category_scores.get(dish.category_id, 0.0)
        bonus = _hour_bonus(hour_map.get(dish.id, set()), now_hour)


        repeat_penalty = 0.5 if dish.id in dish_scores else 1.0
        score = (base * repeat_penalty + affinity + bonus)


        if base == 0 and affinity > 0:
            seen_categories_boosted.add(dish.category_id)

        scored.append((dish, round(score, 3)))

    scored.sort(key=lambda pair: pair[1], reverse=True)

    recommended = [(dish, score) for dish, score in scored[:limit]]
    popular = get_popular_dishes(
        limit,
        exclude_ids=[dish.id for dish, _s in recommended],
    )
    return recommended, popular


def get_favorite_category_names(user_id, top=3):
    interactions = (UserDishInteraction.query
                    .filter(UserDishInteraction.user_id == user_id)
                    .all())
    if not interactions:
        return []

    _, category_scores, _hm = _score_interactions(interactions)
    if not category_scores:
        return []

    top_ids = sorted(category_scores, key=category_scores.get, reverse=True)[:top]
    names = []
    for cid in top_ids:
        cat = Category.query.get(cid)
        if cat:
            names.append(cat.name)
    return names
