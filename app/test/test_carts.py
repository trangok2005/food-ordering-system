import pytest

from app import db
from app.cart import dao as cart_dao
from app.models import DishPairing, RestaurantStatus
from app.test.test_base import (app, client, test_session,
                                make_restaurant_owner, make_restaurant,
                                make_customer, make_dish, login)


def _setup_restaurant_and_dish(prefix=''):
    owner = make_restaurant_owner(prefix)
    restaurant = make_restaurant(owner)
    dish = make_dish(restaurant, name='Cá hồi Sashimi', price=120000)
    db.session.commit()
    return restaurant, dish



def test_add_to_cart_creates_cart(app):
    restaurant, dish = _setup_restaurant_and_dish()
    customer = make_customer()
    db.session.commit()

    cart_dao.add_to_cart(customer.id, dish.id, quantity=2)

    carts = cart_dao.get_user_carts(customer.id)
    assert len(carts) == 1
    assert carts[0].restaurant_id == restaurant.id
    assert carts[0].items[0].dish_id == dish.id
    assert carts[0].items[0].quantity == 2


def test_add_to_cart_accumulates_quantity(app):
    _, dish = _setup_restaurant_and_dish()
    customer = make_customer()
    db.session.commit()

    cart_dao.add_to_cart(customer.id, dish.id, quantity=1)
    cart_dao.add_to_cart(customer.id, dish.id, quantity=1)

    cart = cart_dao.get_user_carts(customer.id)[0]
    assert cart.items[0].quantity == 2


def test_add_to_cart_total_amount(app):
    _, dish = _setup_restaurant_and_dish()
    customer = make_customer()
    db.session.commit()

    cart_dao.add_to_cart(customer.id, dish.id, quantity=2)

    cart = cart_dao.get_user_carts(customer.id)[0]
    assert cart.total_amount() == 240000


def test_add_to_cart_unavailable_dish(app):
    _, dish = _setup_restaurant_and_dish()
    dish.is_available = False
    db.session.commit()
    customer = make_customer()
    db.session.commit()

    with pytest.raises(ValueError):
        cart_dao.add_to_cart(customer.id, dish.id, quantity=1)


def test_add_to_cart_max_quantity(app):
    _, dish = _setup_restaurant_and_dish()
    customer = make_customer()
    db.session.commit()

    cart_dao.add_to_cart(customer.id, dish.id, quantity=20)

    with pytest.raises(ValueError):
        cart_dao.add_to_cart(customer.id, dish.id, quantity=1)


def test_add_to_cart_conflict_other_restaurant(app):
    restaurant_a, dish_a = _setup_restaurant_and_dish()
    restaurant_b, dish_b = _setup_restaurant_and_dish('B')
    customer = make_customer()
    db.session.commit()

    cart_dao.add_to_cart(customer.id, dish_a.id, quantity=1)

    with pytest.raises(cart_dao.CartRestaurantConflict):
        cart_dao.add_to_cart(customer.id, dish_b.id, quantity=1)

    carts = cart_dao.get_user_carts(customer.id)
    assert len(carts) == 1
    assert carts[0].restaurant_id == restaurant_a.id


def test_clear_all_carts_then_switch_restaurant(app):
    _, dish_a = _setup_restaurant_and_dish()
    restaurant_b, dish_b = _setup_restaurant_and_dish('B')
    customer = make_customer()
    db.session.commit()

    cart_dao.add_to_cart(customer.id, dish_a.id, quantity=1)
    cart_dao.clear_all_carts(customer.id)
    cart_dao.add_to_cart(customer.id, dish_b.id, quantity=1)

    carts = cart_dao.get_user_carts(customer.id)
    assert len(carts) == 1
    assert carts[0].restaurant_id == restaurant_b.id



def test_update_cart_item_success(app):
    _, dish = _setup_restaurant_and_dish()
    customer = make_customer()
    db.session.commit()
    cart_dao.add_to_cart(customer.id, dish.id, quantity=1)

    item = cart_dao.get_user_carts(customer.id)[0].items[0]
    cart_dao.update_cart_item(customer.id, item.id, quantity=5)

    assert item.quantity == 5


def test_update_cart_item_not_in_cart(app):
    _, dish = _setup_restaurant_and_dish()
    customer = make_customer()
    db.session.commit()

    with pytest.raises(ValueError):
        cart_dao.update_cart_item(customer.id, 9999, quantity=3)


def test_update_cart_item_exceeds_max(app):
    _, dish = _setup_restaurant_and_dish()
    customer = make_customer()
    db.session.commit()
    cart_dao.add_to_cart(customer.id, dish.id, quantity=1)

    item = cart_dao.get_user_carts(customer.id)[0].items[0]
    with pytest.raises(ValueError):
        cart_dao.update_cart_item(customer.id, item.id, quantity=21)


def test_update_cart_item_zero_raises(app):
    _, dish = _setup_restaurant_and_dish()
    customer = make_customer()
    db.session.commit()
    cart_dao.add_to_cart(customer.id, dish.id, quantity=1)

    item = cart_dao.get_user_carts(customer.id)[0].items[0]
    with pytest.raises(ValueError):
        cart_dao.update_cart_item(customer.id, item.id, quantity=0)


def test_remove_cart_item_success(app):
    _, dish = _setup_restaurant_and_dish()
    customer = make_customer()
    db.session.commit()
    cart_dao.add_to_cart(customer.id, dish.id, quantity=1)

    item = cart_dao.get_user_carts(customer.id)[0].items[0]
    cart_dao.remove_cart_item(customer.id, item.id)

    assert cart_dao.get_user_carts(customer.id) == []


def test_remove_cart_item_not_in_cart(app):
    _, dish = _setup_restaurant_and_dish()
    customer = make_customer()
    db.session.commit()

    with pytest.raises(ValueError):
        cart_dao.remove_cart_item(customer.id, 9999)


def test_clear_cart(app):
    _, dish = _setup_restaurant_and_dish()
    customer = make_customer()
    db.session.commit()
    cart_dao.add_to_cart(customer.id, dish.id, quantity=1)

    cart_id = cart_dao.get_user_carts(customer.id)[0].id
    cart_dao.clear_cart(customer.id, cart_id)

    assert cart_dao.get_user_carts(customer.id) == []


def test_cart_stats(app):
    _, dish = _setup_restaurant_and_dish()
    customer = make_customer()
    db.session.commit()
    cart_dao.add_to_cart(customer.id, dish.id, quantity=2)

    stats = cart_dao.get_cart_stats(customer.id)
    assert stats['total_quantity'] == 2
    assert stats['total_amount'] == 240000



def test_cart_view_requires_login(client, app):
    assert client.get('/cart/').status_code == 302


def test_cart_view_success(client, app):
    _, dish = _setup_restaurant_and_dish()
    customer = make_customer()
    db.session.commit()
    cart_dao.add_to_cart(customer.id, dish.id, quantity=2)
    login(client, username='customer')

    res = client.get('/cart/')
    assert res.status_code == 200
    assert 'Cá hồi Sashimi'.encode('utf-8') in res.data


def test_add_to_cart_route(client, app):
    _, dish = _setup_restaurant_and_dish()
    make_customer()
    db.session.commit()
    login(client, username='customer')

    res = client.post('/cart/add', data={'dish_id': dish.id, 'quantity': 2})
    assert res.status_code == 302

    cart = cart_dao.get_user_carts(customer_id())
    assert cart[0].items[0].quantity == 2


def customer_id():
    from app.auth import dao as auth_dao
    return auth_dao.get_user_by_username('customer').id


def _pair(source, target, confidence=0.8, lift=1.5, support=0.4):
    db.session.add(DishPairing(
        dish_id=source.id,
        paired_dish_id=target.id,
        confidence=confidence,
        lift=lift,
        support=support,
    ))


def _pairing_cart():
    restaurant, source = _setup_restaurant_and_dish()
    customer = make_customer()
    db.session.commit()
    cart_dao.add_to_cart(customer.id, source.id)
    return restaurant, source, customer


def test_pairing_suggestions_returns_ranked_valid_dishes(client, app):
    restaurant, source, _ = _pairing_cart()
    by_support = make_dish(restaurant, name='Theo support')
    by_lift = make_dish(restaurant, name='Theo lift')
    first = make_dish(restaurant, name='Confidence cao')
    _pair(source, by_support, confidence=0.7, lift=1.2, support=0.9)
    _pair(source, by_lift, confidence=0.7, lift=1.8, support=0.1)
    _pair(source, first, confidence=0.9, lift=1.0, support=0.1)
    db.session.commit()
    login(client, username='customer')

    response = client.get(f'/cart/pairing-suggestions/{source.id}')

    assert response.status_code == 200
    assert [item['name'] for item in response.get_json()['suggestions']] == [
        'Confidence cao', 'Theo lift', 'Theo support'
    ]


def test_pairing_suggestions_returns_empty_without_rules(client, app):
    _, source, _ = _pairing_cart()
    login(client, username='customer')

    response = client.get(f'/cart/pairing-suggestions/{source.id}')

    assert response.status_code == 200
    assert response.get_json() == {'suggestions': []}


def test_pairing_suggestions_excludes_dish_already_in_cart(client, app):
    restaurant, source, customer = _pairing_cart()
    existing = make_dish(restaurant, name='Đã có trong giỏ')
    _pair(source, existing)
    db.session.commit()
    cart_dao.add_to_cart(customer.id, existing.id)
    login(client, username='customer')

    response = client.get(f'/cart/pairing-suggestions/{source.id}')

    assert response.get_json() == {'suggestions': []}


def test_pairing_suggestions_excludes_unavailable_dish(client, app):
    restaurant, source, _ = _pairing_cart()
    unavailable = make_dish(
        restaurant, name='Hết hàng', is_available=False
    )
    _pair(source, unavailable)
    db.session.commit()
    login(client, username='customer')

    response = client.get(f'/cart/pairing-suggestions/{source.id}')

    assert response.get_json() == {'suggestions': []}


def test_pairing_suggestions_excludes_other_restaurant(client, app):
    _, source, _ = _pairing_cart()
    other_owner = make_restaurant_owner('other')
    other_restaurant = make_restaurant(other_owner)
    other_dish = make_dish(other_restaurant, name='Khác nhà hàng')
    _pair(source, other_dish)
    db.session.commit()
    login(client, username='customer')

    response = client.get(f'/cart/pairing-suggestions/{source.id}')

    assert response.get_json() == {'suggestions': []}


def test_pairing_suggestions_returns_at_most_three(client, app):
    restaurant, source, _ = _pairing_cart()
    for index in range(4):
        target = make_dish(restaurant, name=f'Món kèm {index}')
        _pair(source, target, confidence=0.9 - index / 10)
    db.session.commit()
    login(client, username='customer')

    response = client.get(f'/cart/pairing-suggestions/{source.id}')

    assert len(response.get_json()['suggestions']) == 3


def test_pairing_suggestions_requires_login(client, app):
    response = client.get('/cart/pairing-suggestions/1')

    assert response.status_code == 302
    assert '/auth/login' in response.headers['Location']


def test_pairing_suggestions_rejects_dish_not_in_cart(client, app):
    restaurant, _, _ = _pairing_cart()
    not_in_cart = make_dish(restaurant, name='Không nằm trong giỏ')
    db.session.commit()
    login(client, username='customer')

    response = client.get(f'/cart/pairing-suggestions/{not_in_cart.id}')

    assert response.status_code == 404
    assert response.get_json()['error'] == 'Món ăn không thuộc giỏ hàng hiện tại'


def test_update_cart_route(client, app):
    _, dish = _setup_restaurant_and_dish()
    customer = make_customer()
    db.session.commit()
    cart_dao.add_to_cart(customer.id, dish.id, quantity=1)
    login(client, username='customer')

    item = cart_dao.get_user_carts(customer.id)[0].items[0]
    res = client.post('/cart/update',
                      data={'item_id': item.id, 'quantity': 5})
    assert res.status_code == 302
    assert item.quantity == 5


def test_remove_cart_route(client, app):
    _, dish = _setup_restaurant_and_dish()
    customer = make_customer()
    db.session.commit()
    cart_dao.add_to_cart(customer.id, dish.id, quantity=1)
    login(client, username='customer')

    item = cart_dao.get_user_carts(customer.id)[0].items[0]
    res = client.post('/cart/remove', data={'item_id': item.id})
    assert res.status_code == 302
    assert cart_dao.get_user_carts(customer.id) == []


def test_clear_cart_route(client, app):
    _, dish = _setup_restaurant_and_dish()
    customer = make_customer()
    db.session.commit()
    cart_dao.add_to_cart(customer.id, dish.id, quantity=1)
    login(client, username='customer')

    cart_id = cart_dao.get_user_carts(customer.id)[0].id
    res = client.post('/cart/clear', data={'cart_id': cart_id})
    assert res.status_code == 302
    assert cart_dao.get_user_carts(customer.id) == []


def test_cart_stats_api(client, app):
    _, dish = _setup_restaurant_and_dish()
    customer = make_customer()
    db.session.commit()
    cart_dao.add_to_cart(customer.id, dish.id, quantity=3)
    login(client, username='customer')

    res = client.get('/cart/api/stats')
    assert res.status_code == 200
    assert res.get_json() == {'total_quantity': 3, 'total_amount': 360000}


def test_cart_blocks_restaurant_role(client, app):
    make_restaurant_owner()
    db.session.commit()
    login(client, username='owner')
    assert client.get('/cart/').status_code == 403
