import numpy as np

from app import db
from app.ai import recommend
from app.models import OrderDetail, OrderStatus, UserDishInteraction
from app.test.test_base import (
    app,
    make_customer,
    make_dish,
    make_order,
    make_owner_and_restaurant,
)


def _add_interaction(user, dish, kind):
    db.session.add(UserDishInteraction(
        user_id=user.id,
        dish_id=dish.id,
        interaction_type=kind,
        hour_of_day=12,
    ))


def test_interaction_matrix_uses_weights_and_ignores_unsupported_types(app):
    _, restaurant = make_owner_and_restaurant()
    first_user = make_customer('first')
    second_user = make_customer('second')
    first_dish = make_dish(restaurant, name='Món một')
    second_dish = make_dish(restaurant, name='Món hai')
    _add_interaction(first_user, first_dish, 'ORDER')
    _add_interaction(first_user, first_dish, 'ADD_TO_CART')
    _add_interaction(first_user, second_dish, 'REVIEW')
    _add_interaction(first_user, second_dish, 'VIEW')
    _add_interaction(first_user, second_dish, 'UNKNOWN')
    _add_interaction(second_user, second_dish, 'ORDER')
    db.session.commit()

    matrix, _users, _dishes, user_index, dish_index = (
        recommend._build_interaction_matrix()
    )

    assert matrix[user_index[first_user.id], dish_index[first_dish.id]] == 5.0
    assert matrix[user_index[first_user.id], dish_index[second_dish.id]] == 2.0
    assert matrix[user_index[second_user.id], dish_index[second_dish.id]] == 3.0
    assert np.count_nonzero(matrix) == 3


def test_view_only_user_falls_back_to_popular_dishes(app):
    _, restaurant = make_owner_and_restaurant()
    customer = make_customer()
    popular = make_dish(restaurant, name='Món phổ biến')
    viewed = make_dish(restaurant, name='Món đã xem')
    order = make_order(restaurant, customer, status=OrderStatus.COMPLETED)
    db.session.add(OrderDetail(
        order_id=order.id,
        dish_id=popular.id,
        quantity=3,
        unit_price=popular.price,
    ))
    _add_interaction(customer, viewed, 'VIEW')
    db.session.commit()

    personalized, fallback = recommend.recommend_dishes_for_user(customer.id)

    assert personalized == []
    assert fallback[0] == popular


def test_nmf_recommends_unseen_available_dish(app):
    _, restaurant = make_owner_and_restaurant()
    customer = make_customer('first')
    other = make_customer('second')
    interacted = make_dish(restaurant, name='Đã tương tác')
    candidate = make_dish(restaurant, name='Có thể gợi ý')
    _add_interaction(customer, interacted, 'ORDER')
    _add_interaction(other, interacted, 'ADD_TO_CART')
    _add_interaction(other, candidate, 'ORDER')
    db.session.commit()

    personalized, _fallback = recommend.recommend_dishes_for_user(customer.id)

    assert [dish for dish, _score in personalized] == [candidate]
    assert all(dish != interacted for dish, _score in personalized)


def test_nmf_filters_unavailable_candidates(app):
    _, restaurant = make_owner_and_restaurant()
    customer = make_customer('first')
    other = make_customer('second')
    interacted = make_dish(restaurant, name='Đã tương tác')
    unavailable = make_dish(
        restaurant, name='Hết hàng', is_available=False
    )
    _add_interaction(customer, interacted, 'ORDER')
    _add_interaction(other, interacted, 'ORDER')
    _add_interaction(other, unavailable, 'ORDER')
    db.session.commit()

    personalized, _fallback = recommend.recommend_dishes_for_user(customer.id)

    assert personalized == []


def test_favorite_categories_ignore_view_and_unknown_types(app):
    _, restaurant = make_owner_and_restaurant()
    _, other_restaurant = make_owner_and_restaurant('other')
    customer = make_customer()
    valid = make_dish(restaurant, name='Món hợp lệ')
    ignored = make_dish(other_restaurant, name='Món bị bỏ qua')
    ignored.category.name = 'Danh mục bị bỏ qua'
    _add_interaction(customer, valid, 'ORDER')
    _add_interaction(customer, ignored, 'VIEW')
    _add_interaction(customer, ignored, 'UNKNOWN')
    db.session.commit()

    assert recommend.get_favorite_category_names(customer.id) == ['Menu']
