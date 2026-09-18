from datetime import datetime
from pathlib import Path
import re

from app import create_app, db
from app.ai import pairing
from app.cart import dao as cart_dao
from app.cart import payos
from app.models import (Category, DishPairing, Order, OrderDetail, OrderStatus,
                        PaymentAttempt, Restaurant, UserDishInteraction,
                        UserRole)
from app.test.test_base import (app, client, login, make_app, make_customer, make_dish,
                                make_order, make_owner_and_restaurant)


def test_account_locks_after_five_wrong_passwords(app, client):
    user = make_customer()
    db.session.commit()

    for _ in range(5):
        client.post('/auth/login', data={'username': user.username,
                                         'password': 'wrong-password'})

    db.session.refresh(user)
    assert user.is_locked()
    assert user.failed_login_count == 5


def test_checkout_requires_gps_when_restaurant_has_coordinates(app):
    _, restaurant = make_owner_and_restaurant()
    restaurant.latitude = 10.7769
    restaurant.longitude = 106.7009
    customer = make_customer()
    dish = make_dish(restaurant)
    db.session.commit()
    cart_dao.add_to_cart(customer.id, dish.id)

    issues = cart_dao.validate_checkout(customer.id)

    assert any('GPS' in issue for issue in issues)


def test_restaurant_registration_requires_gps(app, client):
    customer = make_customer()
    db.session.commit()
    login(client, username=customer.username)

    response = client.post('/restaurant/register', data={
        'name': 'Quán mới', 'address': 'Quận 1', 'phone': '0901234567'})

    assert response.status_code == 200
    assert Restaurant.query.count() == 0


def test_restaurant_menu_crud_routes(app, client):
    owner, restaurant = make_owner_and_restaurant()
    db.session.commit()
    login(client, username=owner.username)

    response = client.post('/restaurant/categories', data={'name': 'Món chính'})
    category = Category.query.filter_by(restaurant_id=restaurant.id).one()
    assert response.status_code == 302

    response = client.post('/restaurant/dishes', data={
        'name': 'Bún bò', 'price': '45000', 'category_id': category.id})
    assert response.status_code == 302
    assert restaurant.dishes[0].name == 'Bún bò'


def _pending_payment(customer, restaurant, dish):
    cart_dao.add_to_cart(customer.id, dish.id)
    pending = cart_dao.build_checkout_payload(customer.id)
    pending.update({'order_code': 123456789,
                    'payment_request_id': 'pay_123456789',
                    'address': '45 Lê Lợi', 'phone': '0901234567',
                    'note': '', 'lat': None, 'lng': None})
    return pending


def test_payment_finalization_is_idempotent(app):
    _, restaurant = make_owner_and_restaurant()
    customer = make_customer()
    dish = make_dish(restaurant)
    db.session.commit()
    pending = _pending_payment(customer, restaurant, dish)
    cart_dao.save_payment_attempt(customer.id, pending)

    first = cart_dao.finalize_payment_attempt('pay_123456789', customer.id)
    second = cart_dao.finalize_payment_attempt('pay_123456789', customer.id)

    assert len(first) == len(second) == 1
    assert first[0].id == second[0].id
    assert Order.query.count() == 1
    assert PaymentAttempt.query.one().status == 'FINALIZED'


def test_payos_webhook_is_signed_and_idempotent(app, client, monkeypatch):
    monkeypatch.setenv('PAYOS_CHECKSUM_KEY', 'test-checksum-key')
    _, restaurant = make_owner_and_restaurant()
    customer = make_customer()
    dish = make_dish(restaurant)
    db.session.commit()
    pending = _pending_payment(customer, restaurant, dish)
    cart_dao.save_payment_attempt(customer.id, pending)
    data = {'orderCode': 123456789, 'amount': pending['total'], 'code': '00'}
    payload = {'success': True, 'data': data,
               'signature': payos.sign_webhook_data(data, 'test-checksum-key')}

    assert client.post('/cart/webhook/payos', json=payload).status_code == 200
    assert client.post('/cart/webhook/payos', json=payload).status_code == 200
    assert Order.query.count() == 1


def test_pairing_calculates_both_directions_and_lift(app):
    _, restaurant = make_owner_and_restaurant()
    customer = make_customer()
    dish_a = make_dish(restaurant, name='Cơm')
    dish_b = make_dish(restaurant, name='Canh')
    order = make_order(restaurant, customer, status=OrderStatus.COMPLETED)
    db.session.add_all([
        OrderDetail(order_id=order.id, dish_id=dish_a.id, quantity=1,
                    unit_price=dish_a.price),
        OrderDetail(order_id=order.id, dish_id=dish_b.id, quantity=1,
                    unit_price=dish_b.price),
    ])
    db.session.commit()

    assert pairing.recompute_restaurant_pairings(restaurant.id) == 2
    assert DishPairing.query.count() == 2
    assert all(rule.lift == 1 for rule in DishPairing.query.all())


def test_pairing_support_uses_all_completed_orders(app):
    _, restaurant = make_owner_and_restaurant()
    customer = make_customer()
    dish_a = make_dish(restaurant, name='Cơm')
    dish_b = make_dish(restaurant, name='Canh')
    dish_c = make_dish(restaurant, name='Nước')
    order_dishes = [
        [dish_a, dish_b], [dish_a], [dish_c], [dish_c],
    ]
    for dishes in order_dishes:
        order = make_order(restaurant, customer, status=OrderStatus.COMPLETED)
        for dish in dishes:
            db.session.add(OrderDetail(
                order_id=order.id, dish_id=dish.id,
                quantity=1, unit_price=dish.price,
            ))
    db.session.commit()

    assert pairing.recompute_restaurant_pairings(restaurant.id) == 2
    rules = DishPairing.query.order_by(DishPairing.dish_id).all()
    assert all(rule.support == 0.25 for rule in rules)
    assert sorted(rule.confidence for rule in rules) == [0.5, 1.0]


def test_pairing_only_returns_available_rule_matches(app):
    _, restaurant = make_owner_and_restaurant()
    source = make_dish(restaurant, name='Cơm')
    unavailable = make_dish(
        restaurant, name='Canh', is_available=False
    )
    available = make_dish(restaurant, name='Nước')
    db.session.add_all([
        DishPairing(
            dish_id=source.id,
            paired_dish_id=unavailable.id,
            support=0.5,
            confidence=0.9,
            lift=1.5,
        ),
        DishPairing(
            dish_id=source.id,
            paired_dish_id=available.id,
            support=0.4,
            confidence=0.8,
            lift=1.4,
        ),
    ])
    db.session.commit()

    suggestions = pairing.get_pairings_for_dish(source.id)

    assert suggestions == [available]


def test_add_to_cart_records_recommendation_input(app):
    _, restaurant = make_owner_and_restaurant()
    customer = make_customer()
    dish = make_dish(restaurant)
    db.session.commit()

    cart_dao.add_to_cart(customer.id, dish.id)

    interaction = UserDishInteraction.query.one()
    assert interaction.interaction_type == 'ADD_TO_CART'


def test_create_app_injects_and_validates_csrf_token():
    application = create_app({
        'TESTING': True,
        'SECRET_KEY': 'csrf-test-secret',
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
    })
    with application.app_context():
        db.create_all()
        client = application.test_client()
        page = client.get('/auth/login')
        assert b'_csrf_token' in page.data
        assert client.post('/auth/login', data={
            'username': 'nobody', 'password': 'wrong'}).status_code == 400
        db.drop_all()


def test_every_post_form_declares_csrf_token():
    templates = Path(__file__).parents[1] / 'templates'
    post_form = re.compile(
        r'<form\b(?=[^>]*\bmethod=["\']post["\'])[^>]*>(.*?)</form>',
        re.IGNORECASE | re.DOTALL,
    )

    missing = []
    for template in templates.rglob('*.html'):
        for index, body in enumerate(post_form.findall(template.read_text(encoding='utf-8')), 1):
            if 'name="_csrf_token"' not in body and "name='_csrf_token'" not in body:
                missing.append(f'{template.relative_to(templates)} form #{index}')

    assert not missing, f'POST forms missing CSRF token: {missing}'


def test_seed_is_repeatable_without_reset(app):
    from seed import seed_database

    seed_database(application=app)
    first_count = Restaurant.query.count()
    seed_database(application=app)

    assert first_count == 2
    assert Restaurant.query.count() == first_count
