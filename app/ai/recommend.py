#Non-negative Matrix Factorization
import numpy as np
from sklearn.decomposition import NMF

from app import db
from app.models import (
    Dish,
    Order,
    OrderDetail,
    OrderStatus,
    Restaurant,
    RestaurantStatus,
    UserDishInteraction,
)


INTERACTION_WEIGHTS = {
    'ORDER': 3.0,
    'ADD_TO_CART': 2.0,
    'REVIEW': 2.0,
}


def _available_query():
    return (
        Dish.query
        .join(Restaurant, Dish.restaurant_id == Restaurant.id)
        .filter(
            Dish.active.is_(True),
            Dish.is_available.is_(True),
            Restaurant.active.is_(True),
            Restaurant.is_open.is_(True),
            Restaurant.status == RestaurantStatus.APPROVED,
        )
    )


def get_popular_dishes(limit=8, exclude_ids=None):
    """Dùng món phổ biến khi chưa đủ dl"""
    exclude_ids = set(exclude_ids or [])

    totals = (
        db.session.query(
            OrderDetail.dish_id.label('dish_id'),
            db.func.sum(OrderDetail.quantity).label('total_qty'),
        )
        .join(Order, Order.id == OrderDetail.order_id)
        .filter(Order.status == OrderStatus.COMPLETED)
        .group_by(OrderDetail.dish_id)
        .subquery()
    )

    rows = (
        _available_query()
        .with_entities(
            Dish,
            db.func.coalesce(totals.c.total_qty, 0).label('total_qty'),
        )
        .outerjoin(totals, totals.c.dish_id == Dish.id)
        .order_by(db.desc('total_qty'), Dish.name)
        .all()
    )

    return [
        dish for dish, _quantity in rows
        if dish.id not in exclude_ids
    ][:limit]


def _build_interaction_matrix():
    """Tạo ma trận User x Dish"""
    interactions = UserDishInteraction.query.all()

    valid = [
        interaction for interaction in interactions
        if interaction.interaction_type in INTERACTION_WEIGHTS
    ]

    if not valid:
        return None

    user_ids = sorted({interaction.user_id for interaction in valid})
    dish_ids = sorted({interaction.dish_id for interaction in valid})

    if len(user_ids) < 2 or len(dish_ids) < 2:
        return None

    user_index = {
        user_id: index for index, user_id in enumerate(user_ids)
    }

    dish_index = {
        dish_id: index for index, dish_id in enumerate(dish_ids)
    }

    matrix = np.zeros(
        (len(user_ids), len(dish_ids)),
        dtype=float,
    )

    for interaction in valid:
        matrix[
            user_index[interaction.user_id],
            dish_index[interaction.dish_id],
        ] += INTERACTION_WEIGHTS[interaction.interaction_type]

    return matrix, user_ids, dish_ids, user_index, dish_index


def recommend_dishes_for_user(user_id, limit=8):
    """NMF"""
    data = _build_interaction_matrix()

    # Không đủ dl NMF
    if data is None:
        return get_popular_dishes(limit)

    matrix, _user_ids, dish_ids, user_index, dish_index = data

    # User chưa có trong dữ liệu NMF
    if user_id not in user_index:
        return get_popular_dishes(limit)

    # Khởi tạo mô hình NMF
    model = NMF(
        n_components=min(3, matrix.shape[0], matrix.shape[1]),
        init='nndsvda',
        random_state=42,
        max_iter=500,
    )

    # Học đặc trưng ẩn từ ma trận User × Dish
    user_features = model.fit_transform(matrix)

    # điểm
    predicted = user_features @ model.components_

    # Lấy user hiện tại
    user_row = user_index[user_id]
    user_scores = predicted[user_row]

    # Những món user đã tương tác
    interacted_ids = {
        dish_ids[index]
        for index, value in enumerate(matrix[user_row])
        if value > 0
    }

    available_dishes = {
        dish.id: dish
        for dish in _available_query().all()
    }

    recommended = []

    for dish_id, index in dish_index.items():
        # Không recommen lại món đã tương tác
        if dish_id in interacted_ids:
            continue

        dish = available_dishes.get(dish_id)

        if dish:
            recommended.append((dish, round(float(user_scores[index]), 2)))

    recommended.sort(key=lambda item: item[1],reverse=True)

    return recommended[:limit]



