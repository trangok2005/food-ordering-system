import pytest

from app import db
from app.models import (User, UserRole, Restaurant, RestaurantStatus,
                        Category, Dish, Order, OrderDetail, OrderStatus,
                        PaymentStatus, Review, SentimentLabel)
from app.test.test_base import make_app, login


@pytest.fixture()
def app():
    app = make_app()
    with app.app_context():
        db.create_all()

        user = User(username='kh1', password='', email='kh1@test.com',
                    role=UserRole.CUSTOMER, full_name='Khách 1', active=True)
        user.set_password('123456')
        db.session.add(user)
        db.session.flush()

        rest = Restaurant(name='Nhà hàng A', address='Q1',
                          status=RestaurantStatus.APPROVED, owner_id=user.id)
        db.session.add(rest)
        db.session.flush()

        cat = Category(name='Món chính', restaurant_id=rest.id)
        db.session.add(cat)
        db.session.flush()

        dish = Dish(name='Cá hồi', price=100000, restaurant_id=rest.id,
                    category_id=cat.id, description='Miêu tả')
        db.session.add(dish)
        db.session.flush()

        order = Order(user_id=user.id, restaurant_id=rest.id,
                      delivery_address='Q1', phone='0901234567',
                      total_amount=100000, status=OrderStatus.COMPLETED,
                      payment_status=PaymentStatus.PAID)
        db.session.add(order)
        db.session.flush()

        db.session.add(OrderDetail(order_id=order.id, dish_id=dish.id,
                                   quantity=1, unit_price=100000))
        db.session.commit()

        app.order = order
        app.dish = dish
        app.user = user
        yield app
        db.session.remove()
        db.drop_all()


def _login(client, username='kh1'):
    return login(client, username)


def test_my_reviews_requires_login(app):
    client = app.test_client()
    res = client.get('/ai/reviews')
    assert res.status_code == 302


def test_my_reviews_empty(app):
    client = app.test_client()
    _login(client)
    res = client.get('/ai/reviews')
    assert res.status_code == 200


def test_add_review_requires_login(app):
    client = app.test_client()
    res = client.post('/ai/reviews/add', data={
        'order_id': app.order.id,
        'dish_id': app.dish.id,
        'rating': 5,
        'comment': 'Ngon',
    })
    assert res.status_code == 302


def test_add_review_success(app, monkeypatch):
    from app.ai import gemini
    monkeypatch.setattr(gemini, 'is_configured', lambda: True)
    monkeypatch.setattr(
        gemini, 'analyze_sentiment', lambda comment: ('POSITIVE', 0.9)
    )

    client = app.test_client()
    _login(client)
    res = client.post('/ai/reviews/add', data={
        'order_id': app.order.id,
        'dish_id': app.dish.id,
        'rating': 5,
        'comment': 'Rất ngon, sẽ gọi lại',
    })
    assert res.status_code == 302

    with app.app_context():
        reviews = Review.query.all()
        assert len(reviews) == 1
        r = reviews[0]
        assert r.rating == 5
        assert r.user_id == app.user.id
        assert r.dish_id == app.dish.id
        assert r.order_id == app.order.id
        assert r.sentiment_label == SentimentLabel.POSITIVE
        assert r.sentiment_score == 0.9


def test_add_review_duplicate_rejected(app):
    client = app.test_client()
    _login(client)
    payload = {
        'order_id': app.order.id,
        'dish_id': app.dish.id,
        'rating': 5,
        'comment': 'Ngon',
    }
    client.post('/ai/reviews/add', data=payload)
    res = client.post('/ai/reviews/add', data=payload)
    assert res.status_code == 302

    with app.app_context():
        assert Review.query.count() == 1


def test_duplicate_review_is_rejected_before_gemini(app, monkeypatch):
    from app.ai import dao as ai_dao
    from app.ai import gemini

    with app.app_context():
        ai_dao.add_review(app.user.id, app.order, app.dish.id, 5, 'Ngon', None)

    called = False

    def analyze(_comment):
        nonlocal called
        called = True
        return 'POSITIVE', 1.0

    monkeypatch.setattr(gemini, 'is_configured', lambda: True)
    monkeypatch.setattr(gemini, 'analyze_sentiment', analyze)
    client = app.test_client()
    _login(client)
    client.post('/ai/reviews/add', data={
        'order_id': app.order.id,
        'dish_id': app.dish.id,
        'rating': 5,
        'comment': 'Ngon',
    })
    assert called is False


def test_add_review_handles_unique_constraint_race(app, monkeypatch):
    from app.ai import dao as ai_dao

    with app.app_context():
        ai_dao.add_review(app.user.id, app.order, app.dish.id, 5, 'Ngon', None)
        monkeypatch.setattr(ai_dao, 'get_review_for_order_dish',
                            lambda order, dish_id: None)

        with pytest.raises(ValueError, match='đã đánh giá'):
            ai_dao.add_review(
                app.user.id, app.order, app.dish.id, 4, 'Vẫn ngon', None
            )
        assert Review.query.count() == 1


def test_add_review_invalid_rating(app):
    client = app.test_client()
    _login(client)
    res = client.post('/ai/reviews/add', data={
        'order_id': app.order.id,
        'dish_id': app.dish.id,
        'rating': 6,
        'comment': 'Ngon',
    })
    assert res.status_code == 302

    with app.app_context():
        assert Review.query.count() == 0


def test_add_review_rating_missing(app):
    client = app.test_client()
    _login(client)
    res = client.post('/ai/reviews/add', data={
        'order_id': app.order.id,
        'dish_id': app.dish.id,
        'comment': 'Ngon',
    })
    assert res.status_code == 302

    with app.app_context():
        assert Review.query.count() == 0


def test_add_review_unknown_order(app):
    client = app.test_client()
    _login(client)
    res = client.post('/ai/reviews/add', data={
        'order_id': 9999,
        'dish_id': app.dish.id,
        'rating': 5,
    })
    assert res.status_code == 404

    with app.app_context():
        assert Review.query.count() == 0


def test_add_review_other_users_order(app):
    client = app.test_client()
    _login(client)

    with app.app_context():
        other = User(username='kh2', password='', email='kh2@test.com',
                     role=UserRole.CUSTOMER, full_name='Khách 2', active=True)
        other.set_password('123456')
        db.session.add(other)
        db.session.flush()

        other_order = Order(user_id=other.id, restaurant_id=app.dish.restaurant_id,
                            delivery_address='Q1', phone='0901234567',
                            total_amount=100000, status=OrderStatus.COMPLETED,
                            payment_status=PaymentStatus.PAID)
        db.session.add(other_order)
        db.session.flush()
        db.session.add(OrderDetail(order_id=other_order.id, dish_id=app.dish.id,
                                   quantity=1, unit_price=100000))
        db.session.commit()
        other_order_id = other_order.id

    res = client.post('/ai/reviews/add', data={
        'order_id': other_order_id,
        'dish_id': app.dish.id,
        'rating': 5,
    })
    assert res.status_code == 404

    with app.app_context():
        assert Review.query.count() == 0


def test_add_review_dish_not_in_order(app):
    client = app.test_client()
    _login(client)

    with app.app_context():
        owner2 = User(username='owner2', email='owner2@test.com',
                      role=UserRole.RESTAURANT)
        owner2.set_password('123456')
        db.session.add(owner2)
        db.session.flush()
        rest2 = Restaurant(name='Nhà hàng B', address='Q1',
                           status=RestaurantStatus.APPROVED, owner_id=owner2.id)
        db.session.add(rest2)
        db.session.flush()
        cat2 = Category(name='Tráng miệng', restaurant_id=rest2.id)
        db.session.add(cat2)
        db.session.flush()
        dish2 = Dish(name='Kem', price=20000, restaurant_id=rest2.id,
                     category_id=cat2.id, description='Kem dừa')
        db.session.add(dish2)
        db.session.commit()
        dish2_id = dish2.id

    res = client.post('/ai/reviews/add', data={
        'order_id': app.order.id,
        'dish_id': dish2_id,
        'rating': 5,
    })
    assert res.status_code == 302

    with app.app_context():
        assert Review.query.count() == 0


def test_add_review_non_completed_order(app):
    client = app.test_client()
    _login(client)

    with app.app_context():
        pending = Order(user_id=app.user.id, restaurant_id=app.dish.restaurant_id,
                        delivery_address='Q1', phone='0901234567',
                        total_amount=100000, status=OrderStatus.PENDING,
                        payment_status=PaymentStatus.PAID)
        db.session.add(pending)
        db.session.flush()
        db.session.add(OrderDetail(order_id=pending.id, dish_id=app.dish.id,
                                   quantity=1, unit_price=100000))
        db.session.commit()
        pending_id = pending.id

    res = client.post('/ai/reviews/add', data={
        'order_id': pending_id,
        'dish_id': app.dish.id,
        'rating': 5,
    })
    assert res.status_code == 302

    with app.app_context():
        assert Review.query.count() == 0


def test_dish_rating_stats(app):
    with app.app_context():
        from app.ai import dao as ai_dao
        ai_dao.add_review(app.user.id, app.order, app.dish.id, 5, 'Ngon', None)
        stats = ai_dao.get_dish_rating_stats(app.dish.id)
        assert stats['count'] == 1
        assert stats['avg'] == 5.0


def test_log_interaction_creates_row(app):
    with app.app_context():
        from app.ai import dao as ai_dao
        from app.models import UserDishInteraction
        ai_dao.log_interaction(app.user.id, app.dish.id, 'REVIEW')
        rows = UserDishInteraction.query.all()
        assert len(rows) == 1
        assert rows[0].interaction_type == 'REVIEW'
