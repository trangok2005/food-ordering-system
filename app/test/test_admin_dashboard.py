import pytest
from datetime import datetime, timedelta

from app import db
from app.models import OrderStatus, RestaurantStatus
from app.test.test_base import (app, client,
                                make_admin, make_restaurant_owner,
                                make_restaurant, make_customer,
                                make_order, make_dish, login)



def test_admin_dashboard_requires_login(client, app):
    assert client.get('/admin/').status_code == 302


def test_non_admin_blocked(client, app):
    customer = make_customer()
    db.session.commit()
    login(client, username='customer')
    assert client.get('/admin/').status_code == 403


def test_admin_login_redirects_to_admin(client, app):
    make_admin()
    db.session.commit()
    res = login(client, username='admin')
    assert res.status_code == 302
    assert res.headers['Location'].endswith('/admin/')



def test_approve_restaurant(client, app):
    make_admin()
    owner = make_restaurant_owner()
    restaurant = make_restaurant(owner, RestaurantStatus.PENDING)
    db.session.commit()
    login(client, username='admin')

    res = client.post(f'/admin/restaurants/{restaurant.id}/approve')
    assert res.status_code == 302
    db.session.refresh(restaurant)
    assert restaurant.status == RestaurantStatus.APPROVED


def test_approve_only_pending(client, app):
    make_admin()
    owner = make_restaurant_owner()
    restaurant = make_restaurant(owner, RestaurantStatus.APPROVED)
    db.session.commit()
    login(client, username='admin')

    client.post(f'/admin/restaurants/{restaurant.id}/approve')
    db.session.refresh(restaurant)
    assert restaurant.status == RestaurantStatus.APPROVED


def test_lock_and_unlock_restaurant(client, app):
    make_admin()
    owner = make_restaurant_owner()
    restaurant = make_restaurant(owner, RestaurantStatus.APPROVED)
    db.session.commit()
    login(client, username='admin')

    client.post(f'/admin/restaurants/{restaurant.id}/lock')
    db.session.refresh(restaurant)
    assert restaurant.status == RestaurantStatus.LOCKED

    client.post(f'/admin/restaurants/{restaurant.id}/unlock')
    db.session.refresh(restaurant)
    assert restaurant.status == RestaurantStatus.APPROVED


def test_admin_transition_rejects_stale_restaurant_state(app):
    owner = make_restaurant_owner()
    restaurant = make_restaurant(owner, RestaurantStatus.PENDING)
    db.session.commit()
    db.session.query(type(restaurant)).filter_by(id=restaurant.id).update(
        {'status': RestaurantStatus.LOCKED}, synchronize_session=False)
    db.session.commit()
    restaurant.__dict__['status'] = RestaurantStatus.PENDING

    from app.admin import dao as admin_dao
    with pytest.raises(ValueError):
        admin_dao.approve_restaurant(restaurant)
    db.session.refresh(restaurant)
    assert restaurant.status == RestaurantStatus.LOCKED


def test_restaurants_view_filters_by_status(client, app):
    make_admin()
    pending_owner = make_restaurant_owner('pending')
    approved_owner = make_restaurant_owner('approved')
    make_restaurant(pending_owner, RestaurantStatus.PENDING)
    make_restaurant(approved_owner, RestaurantStatus.APPROVED)
    db.session.commit()
    login(client, username='admin')

    res = client.get('/admin/restaurants?status=APPROVED')
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'Nhà hàng' in html



def test_dashboard_stats_page(client, app):
    make_admin()
    owner = make_restaurant_owner()
    restaurant = make_restaurant(owner, RestaurantStatus.APPROVED)
    customer = make_customer()
    make_order(restaurant, customer, total=100000)
    make_dish(restaurant)
    db.session.commit()
    login(client, username='admin')

    res = client.get('/admin/stats')
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert 'Doanh thu' in html
    assert 'Món ăn bán chạy nhất' in html


def test_dashboard_stats_dao(app):
    owner = make_restaurant_owner()
    restaurant = make_restaurant(owner, RestaurantStatus.APPROVED)
    customer = make_customer()
    make_order(restaurant, customer, total=100000, status=OrderStatus.COMPLETED)
    make_order(restaurant, customer, total=50000, status=OrderStatus.DELIVERING)
    make_order(restaurant, customer, total=20000, status=OrderStatus.CANCELLED)
    db.session.commit()

    from app.admin import dao as admin_dao
    stats = admin_dao.get_dashboard_stats()
    assert stats['restaurant_count'] == 1
    assert stats['order_count'] == 3
    assert stats['paid_count'] == 3
    assert stats['revenue'] == 150000

    top = admin_dao.get_top_restaurants()
    assert top and top[0][0].id == restaurant.id
    assert top[0][2] == 150000
