import pytest

from app import db
from app.browse import dao as browse_dao
from app.models import RestaurantStatus
from app.test.test_base import (app, client,
                                make_restaurant_owner, make_restaurant,
                                make_dish)


@pytest.fixture
def setup_data(app):
    owner = make_restaurant_owner()
    restaurant = make_restaurant(owner, name='Sushi Nhật Bản')
    dish1 = make_dish(restaurant, name='Cá hồi Nigiri', price=120000)
    dish2 = make_dish(restaurant, name='Cá ngừ Sashimi', price=150000)
    db.session.commit()
    return restaurant, dish1, dish2


# ---------------- DAO: search ----------------

def test_search_no_keyword_returns_none(setup_data):
    assert browse_dao.search('') is None
    assert browse_dao.search('   ') is None
    assert browse_dao.search(None) is None


def test_search_by_restaurant_name(setup_data):
    restaurant, _, _ = setup_data
    result = browse_dao.search('Sushi')
    assert result is not None
    assert restaurant.id in [r.id for r in result.items]


def test_search_by_dish_name(setup_data):
    restaurant, dish1, _ = setup_data
    result = browse_dao.search('Nigiri')
    assert result is not None
    assert restaurant.id in [r.id for r in result.items]
    assert dish1.id in [d.id for d in restaurant.dishes]


def test_search_no_match(setup_data):
    result = browse_dao.search('Bạch tuộc')
    assert result is not None
    assert result.items == []


def test_search_excludes_pending_restaurant(app):
    owner = make_restaurant_owner('2')
    pending = make_restaurant(owner, name='Sushi Chờ Duyệt',
                              status=RestaurantStatus.PENDING)
    db.session.commit()

    result = browse_dao.search('Sushi')
    assert pending.id not in [r.id for r in result.items]


def test_search_excludes_inactive_restaurant(app):
    owner = make_restaurant_owner('2')
    inactive = make_restaurant(owner, name='Sushi Đóng')
    inactive.active = False
    db.session.commit()

    result = browse_dao.search('Sushi')
    assert inactive.id not in [r.id for r in result.items]


def test_search_excludes_inactive_dish(setup_data):
    restaurant, dish1, _ = setup_data
    dish1.active = False
    db.session.commit()

    result = browse_dao.search('Nigiri')
    # nhà hàng vẫn xuất hiện vì khớp tên nhà hàng hoặc món còn active
    assert restaurant.id in [r.id for r in result.items]


# ---------------- DAO: get_approved_restaurant ----------------

def test_get_approved_restaurant(setup_data):
    restaurant, _, _ = setup_data
    assert browse_dao.get_approved_restaurant(restaurant.id).id == restaurant.id


def test_get_approved_restaurant_rejects_pending(app):
    owner = make_restaurant_owner()
    pending = make_restaurant(owner, status=RestaurantStatus.PENDING)
    db.session.commit()
    assert browse_dao.get_approved_restaurant(pending.id) is None


def test_get_approved_restaurant_not_found(setup_data):
    assert browse_dao.get_approved_restaurant(99999) is None


# ---------------- DAO: get_restaurant_menu ----------------

def test_get_menu_only_active_available(setup_data):
    restaurant, dish1, dish2 = setup_data
    dish1.active = False
    dish2.is_available = False
    db.session.commit()

    menu = browse_dao.get_restaurant_menu(restaurant.id)
    assert menu == []


def test_get_menu_returns_active(setup_data):
    restaurant, dish1, dish2 = setup_data
    db.session.commit()
    menu = browse_dao.get_restaurant_menu(restaurant.id)
    assert {d.id for d in menu} == {dish1.id, dish2.id}


# ---------------- ROUTER ----------------

def test_search_view_renders(client, app, setup_data):
    res = client.get('/browse/search?q=Sushi')
    assert res.status_code == 200
    assert 'Sushi'.encode('utf-8') in res.data


def test_search_view_no_keyword(client, app):
    res = client.get('/browse/search')
    assert res.status_code == 200


def test_restaurant_menu_view(client, app, setup_data):
    restaurant, dish1, _ = setup_data
    res = client.get(f'/browse/restaurant/{restaurant.id}')
    assert res.status_code == 200
    assert dish1.name.encode('utf-8') in res.data


def test_restaurant_menu_view_pending_404(client, app):
    owner = make_restaurant_owner()
    pending = make_restaurant(owner, status=RestaurantStatus.PENDING)
    db.session.commit()
    assert client.get(f'/browse/restaurant/{pending.id}').status_code == 404


def test_restaurant_menu_view_not_found(client, app):
    assert client.get('/browse/restaurant/99999').status_code == 404