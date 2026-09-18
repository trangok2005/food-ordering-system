from collections import defaultdict
from itertools import combinations

from flask import current_app
from sqlalchemy.orm import joinedload

from app import db
from app.models import (
    Dish,
    DishPairing,
    Order,
    OrderStatus,
    RestaurantStatus,
)


MIN_SUPPORT = 0.1
MIN_CONFIDENCE = 0.2


def _completed_transactions(restaurant_id):
    orders = (
        Order.query
        .filter(
            Order.restaurant_id == restaurant_id,
            Order.status == OrderStatus.COMPLETED,
        )
        .all()
    )

    return [
        {item.dish_id for item in order.order_details}
        for order in orders
        if order.order_details
    ]


def recompute_restaurant_pairings(restaurant_id):
    transactions = _completed_transactions(restaurant_id)

    old_rules = (
        DishPairing.query
        .join(Dish, DishPairing.dish_id == Dish.id)
        .filter(Dish.restaurant_id == restaurant_id)
        .all()
    )

    for rule in old_rules:
        db.session.delete(rule)

    if not transactions:
        db.session.commit()
        return 0

    total_orders = len(transactions)
    dish_count = defaultdict(int)
    pair_count = defaultdict(int)

    for items in transactions:
        for dish_id in items:
            dish_count[dish_id] += 1

        for a, b in combinations(sorted(items), 2):
            pair_count[(a, b)] += 1

    rules = []

    for (a, b), count in pair_count.items():
        support = count / total_orders

        if support < MIN_SUPPORT:
            continue

        confidence_ab = count / dish_count[a]
        confidence_ba = count / dish_count[b]

        lift_ab = confidence_ab / (dish_count[b] / total_orders)
        lift_ba = confidence_ba / (dish_count[a] / total_orders)

        if confidence_ab >= MIN_CONFIDENCE:
            rules.append(
                DishPairing(
                    dish_id=a,
                    paired_dish_id=b,
                    support=round(support, 4),
                    confidence=round(confidence_ab, 4),
                    lift=round(lift_ab, 4),
                )
            )

        if confidence_ba >= MIN_CONFIDENCE:
            rules.append(
                DishPairing(
                    dish_id=b,
                    paired_dish_id=a,
                    support=round(support, 4),
                    confidence=round(confidence_ba, 4),
                    lift=round(lift_ba, 4),
                )
            )

    db.session.add_all(rules)
    db.session.commit()

    return len(rules)


def get_pairings_for_dish(dish_id, exclude_ids=None, limit=3):
    source = db.session.get(Dish, dish_id)

    if not source:
        return []

    exclude_ids = set(exclude_ids or [])
    exclude_ids.add(dish_id)

    rows = (
        DishPairing.query
        .options(
            joinedload(DishPairing.paired_dish)
            .joinedload(Dish.restaurant)
        )
        .filter(DishPairing.dish_id == dish_id)
        .order_by(
            DishPairing.confidence.desc(),
            DishPairing.lift.desc(),
            DishPairing.support.desc(),
        )
        .all()
    )

    result = []

    for row in rows:
        dish = row.paired_dish

        if not dish or dish.id in exclude_ids:
            continue

        if dish.restaurant_id != source.restaurant_id:
            continue

        restaurant = dish.restaurant

        if (
            not dish.active
            or not dish.is_available
            or not restaurant.active
            or not restaurant.is_open
            or restaurant.status != RestaurantStatus.APPROVED
        ):
            continue

        result.append(dish)

        if len(result) == limit:
            break

    return result


def get_pairing_suggestions_for_user(user_id, dish_id, limit=3):
    from app.cart.dao import get_user_carts

    cart_dish_ids = {
        item.dish_id
        for cart in get_user_carts(user_id)
        for item in cart.items
    }

    if dish_id not in cart_dish_ids:
        return []

    try:
        return get_pairings_for_dish(
            dish_id,
            exclude_ids=cart_dish_ids,
            limit=limit,
        )
    except Exception:
        current_app.logger.exception(
            'Không thể tạo gợi ý món đi kèm'
        )
        return []