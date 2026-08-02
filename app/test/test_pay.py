import pytest
from datetime import datetime
from app.test.test_base import test_app, test_client, test_session, sample_products, logged_in_user, \
    cart_standard, setup_user
from app.models import User, UserRole, Order, OrderStatus, Product
from app.dao import handle_payment, count_user_orders_today


# dao trước
def test_handle_payment_success(test_session, setup_user, sample_products):
    cart = {"1": {"id": sample_products[0].id, "name": "Cá hồi", "price": 120000, "quantity": 2}}

    result = handle_payment(cart, {"address": "123 Nguyễn Huệ", "phone": "0901234567"}, setup_user.id)

    assert result is True

    order = Order.query.filter_by(user_id=setup_user.id).first()
    assert order is not None
    assert order.status == OrderStatus.PENDING
    assert order.total_amount == 240000
    assert Product.query.get(sample_products[0].id).stock == 50 - 2


def test_handle_payment_many_product(test_session, setup_user, sample_products):
    cart = {
        "1": {"id": 1, "name": "Cá hồi Sashimi", "price": 120000, "quantity": 2},
        "2": {"id": 3, "name": "Cá ngừ Sashimi", "price": 100000, "quantity": 1}
    }
    handle_payment(cart, {"address": "HCM", "phone": "0901234567"}, setup_user.id)

    assert Product.query.get(sample_products[0].id).stock == 50 - 2
    assert Product.query.get(sample_products[2].id).stock == 20 - 1


@pytest.mark.parametrize('phone', [
    '123', 'abc'
])
def test_handle_payment_invalid_phone(phone, test_session, setup_user, sample_products):
    cart = {"1": {"id": sample_products[0].id, "name": "Cá hồi", "price": 120000, "quantity": 1}}

    with pytest.raises(ValueError):
        handle_payment(cart, {"address": "HCM", "phone": phone}, setup_user.id)


def test_handle_payment_min_amount(test_session, setup_user, sample_products):
    cart = {"5": {"id": sample_products[4].id, "name": "Coca Cola", "price": 10000, "quantity": 2}}

    with pytest.raises(ValueError):
        handle_payment(cart, {"address": "HCM", "phone": "0901234567"}, setup_user.id)


def test_handle_payment_out_of_stock(test_session, setup_user, sample_products):
    cart = {"2": {"id": sample_products[1].id, "name": "Cá ngừ", "price": 150000, "quantity": 1}}

    with pytest.raises(ValueError):
        handle_payment(cart, {"address": "HCM", "phone": "0901234567"}, setup_user.id)


def test_handle_payment_product_not_exist(test_session, setup_user):
    cart = {"9999": {"id": 9999, "name": "Ảo", "price": 100000, "quantity": 1}}

    with pytest.raises(ValueError):
        handle_payment(cart, {"address": "HCM", "phone": "0901234567"}, setup_user.id)


def test_handle_payment_order_limit(test_session, setup_user, sample_products, mocker):
    mocker.patch('app.dao.count_user_orders_today', return_value=5)
    cart = {"1": {"id": sample_products[0].id, "name": "Cá hồi", "price": 120000, "quantity": 1}}
    with pytest.raises(ValueError):
        handle_payment(cart, {"address": "HCM", "phone": "0901234567"}, setup_user.id)


def test_count_orders_today_zero(test_session, setup_user):
    assert count_user_orders_today(setup_user.id) == 0


def test_count_orders_today_correct(test_session, setup_user):
    for i in range(3):
        test_session.add(Order(
            user_id=setup_user.id, delivery_address='HCM',
            phone='0901234567', total_amount=120000,
            status=OrderStatus.PENDING
        ))
    test_session.commit()
    assert count_user_orders_today(setup_user.id) == 3


def test_count_orders_today_not_count_other_user(test_session, setup_user):
    other = User(username='other99', password='x', phone='0988888888',
                 address='HN', role=UserRole.USER)
    test_session.add(other)
    test_session.flush()
    test_session.add(Order(
        user_id=other.id, delivery_address='HN',
        phone='0988888888', total_amount=120000,
        status=OrderStatus.PENDING,
    ))
    test_session.commit()
    assert count_user_orders_today(setup_user.id) == 0


# post api/pay
def test_pay_success(test_client, logged_in_user, cart_standard, mocker):
    mock_payment = mocker.patch('app.dao.handle_payment', return_value=True)
    mocker.patch('app.utils.is_restaurant_available', return_value=True)

    res = test_client.post('/api/pay', json={'address': '123 Nguyễn Huệ', 'phone': '0901234567'})
    data = res.get_json()

    assert res.status_code == 200
    assert data['status'] == 200
    assert data['msg'] == 'Đặt hàng thành công'

    with test_client.session_transaction() as sess:
        assert 'cart' not in sess

    mock_payment.assert_called_once()


def test_pay_requires_login(test_client, cart_standard):
    res = test_client.post('/api/pay', json={'address': 'Q1', 'phone': '0901234567'})
    assert res.status_code == 401


def test_pay_empty_cart(test_client, logged_in_user):
    res = test_client.post('/api/pay', json={'address': 'Q1', 'phone': '0901234567'})
    data = res.get_json()
    assert res.status_code == 400
    assert data['err_msg'] == 'Giỏ hàng trống'


def test_pay_restaurant_closed(test_client, logged_in_user, cart_standard, mocker):
    mocker.patch('app.utils.is_restaurant_available', side_effect=ValueError('Nhà hàng hiện đã đóng cửa'))
    res = test_client.post('/api/pay', json={'address': 'Q1', 'phone': '0901234567'})
    data = res.get_json()

    assert res.status_code == 400
    assert 'đóng cửa' in data['err_msg']

    with test_client.session_transaction() as sess:
        assert 'cart' in sess


@pytest.mark.parametrize('error_message, payload', [
    ("Bạn đã đạt giới hạn 5 đơn hàng hôm nay", {"address": "Q1", "phone": "0901234567"}),
    ("Số điện thoại không hợp lệ (phải từ 10-11 số)", {"address": "Q1", "phone": "abc"}),
    ("Sản phẩm Cá hồi không đủ tồn kho", {"address": "Q1", "phone": "0901234567"}),
    ("Sản phẩm không tồn tại", {"address": "Q1", "phone": "0901234567"}),
    ("Đơn hàng tối thiểu phải từ 50.000đ", {"address": "Q1", "phone": "0901234567"}),
], ids=["limit_reached", "invalid_phone", "out_of_stock", "not_found", "min_amount"])
def test_pay_business_validations(test_client, logged_in_user, cart_standard, mocker,
                                  error_message, payload):
    mocker.patch('app.dao.handle_payment', side_effect=ValueError(error_message))
    mocker.patch('app.utils.is_restaurant_available', return_value=True)
    res = test_client.post('/api/pay', json=payload)
    data = res.get_json()

    assert res.status_code == 400
    assert error_message in data['err_msg']

    with test_client.session_transaction() as sess:
        assert 'cart' in sess


def test_pay_system_error(test_client, logged_in_user, cart_standard, mocker):
    mocker.patch('app.dao.handle_payment', side_effect=Exception('Hệ thống đang bận'))
    mocker.patch('app.utils.is_restaurant_available', return_value=True)

    res = test_client.post('/api/pay', json={'address': 'Q1', 'phone': '0901234567'})
    data = res.get_json()

    assert res.status_code == 500
    assert data['err_msg'] == 'Hệ thống đang bận'

    with test_client.session_transaction() as sess:
        assert 'cart' in sess


def test_pay_cart_cleared_only_on_success(test_client, logged_in_user, cart_standard, mocker):
    mocker.patch('app.utils.is_restaurant_available', return_value=True)
    mocker.patch('app.dao.handle_payment', side_effect=ValueError('Lỗi'))

    test_client.post('/api/pay', json={'address': 'Q1', 'phone': '0901234567'})

    with test_client.session_transaction() as sess:
        assert 'cart' in sess

    mocker.patch('app.dao.handle_payment', return_value=True)
    test_client.post('/api/pay', json={'address': 'Q1', 'phone': '0901234567'})

    with test_client.session_transaction() as sess:
        assert 'cart' not in sess
