import pytest
from datetime import datetime, timedelta

from app import db
from app.cart import dao as cart_dao
from app.models import OrderStatus
from app.test.test_base import (app, client, test_session,
                                make_restaurant_owner, make_restaurant,
                                make_customer, make_order, make_dish, login)


def _make_customer_with_orders():
    owner = make_restaurant_owner()
    restaurant = make_restaurant(owner)
    customer = make_customer()
    o1 = make_order(restaurant, customer, status=OrderStatus.PENDING,
                    total=120000)
    o2 = make_order(restaurant, customer, status=OrderStatus.COMPLETED,
                    total=90000)
    db.session.commit()
    return customer, [o1, o2]



def test_get_user_orders_empty(app):
    customer = make_customer()
    db.session.commit()
    assert cart_dao.get_user_orders(customer.id) == []


def test_get_user_orders_returns_only_own(app):
    customer, orders = _make_customer_with_orders()
    owner = make_restaurant_owner('B')
    restaurant_b = make_restaurant(owner)
    other = make_customer('customer2')
    make_order(restaurant_b, other, total=50000)
    db.session.commit()

    ids = {o.id for o in cart_dao.get_user_orders(customer.id)}
    assert ids == {o.id for o in orders}


def test_get_user_orders_sorted_newest_first(app):
    customer, orders = _make_customer_with_orders()
    orders[0].created_date = datetime.now() - timedelta(hours=2)
    orders[1].created_date = datetime.now() - timedelta(hours=1)
    db.session.commit()

    result = cart_dao.get_user_orders(customer.id)
    assert result[0].id == orders[1].id
    assert result[1].id == orders[0].id


def test_get_user_orders_includes_details(app):
    owner = make_restaurant_owner()
    restaurant = make_restaurant(owner)
    customer = make_customer()
    dish = make_dish(restaurant, name='Cá hồi', price=100000)
    order = make_order(restaurant, customer)
    from app.models import OrderDetail
    db.session.add(OrderDetail(
        order_id=order.id, dish_id=dish.id, quantity=1, unit_price=100000))
    db.session.commit()

    result = cart_dao.get_user_orders(customer.id)
    assert len(result) == 1
    assert result[0].order_details[0].dish_id == dish.id



def test_my_orders_requires_login(client, app):
    assert client.get('/cart/my-orders').status_code == 302


def test_my_orders_empty(client, app):
    make_customer()
    db.session.commit()
    login(client, username='customer')

    res = client.get('/cart/my-orders')
    assert res.status_code == 200


def test_my_orders_shows_orders(client, app):
    customer, orders = _make_customer_with_orders()
    login(client, username='customer')

    res = client.get('/cart/my-orders')
    assert res.status_code == 200
    assert f'Đơn #{orders[0].id}'.encode('utf-8') in res.data


def test_my_orders_not_show_other_users(client, app):
    customer, orders = _make_customer_with_orders()
    owner = make_restaurant_owner('B')
    restaurant_b = make_restaurant(owner)
    other = make_customer('customer2')
    other_order = make_order(restaurant_b, other, total=50000)
    db.session.commit()
    login(client, username='customer')

    res = client.get('/cart/my-orders')
    assert res.status_code == 200
    assert f'Đơn #{orders[0].id}'.encode('utf-8') in res.data
    assert f'Đơn #{other_order.id}'.encode('utf-8') not in res.data
