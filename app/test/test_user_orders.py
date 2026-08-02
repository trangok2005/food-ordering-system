import pytest
from datetime import datetime
from app.test.test_base import test_app, test_client, test_session, sample_products, logged_in_user, \
    setup_user, setup_orders_user
from app.models import User, UserRole, Order, OrderDetail, OrderStatus
from app.dao import cancel_order


# dao
def test_cancel_pending_success(test_session, setup_orders_user, sample_products):
    order = setup_orders_user[0]
    product = sample_products[0]
    stock_before = product.stock

    result = cancel_order(order.id, is_admin=False)

    assert result.status == OrderStatus.CANCELLED
    test_session.refresh(product)
    assert product.stock == stock_before + 2


def test_cancel_preparing_fail(test_session, setup_orders_user):
    with pytest.raises(ValueError):
        cancel_order(setup_orders_user[1].id, is_admin=False)


def test_cancel_delivering_fail(test_session, setup_user):
    o = Order(user_id=setup_user.id, delivery_address='HCM', phone='0901234567',
              total_amount=120000, status=OrderStatus.DELIVERING,
              created_date=datetime.now())
    test_session.add(o)
    test_session.commit()

    with pytest.raises(ValueError):
        cancel_order(o.id, is_admin=False)


def test_cancel_completed_admin_fail(test_session, setup_user):
    o = Order(user_id=setup_user.id, delivery_address='HCM', phone='0901234567',
              total_amount=120000, status=OrderStatus.COMPLETED,
              created_date=datetime.now())
    test_session.add(o)
    test_session.commit()

    with pytest.raises(ValueError):
        cancel_order(o.id, is_admin=True)


def test_cancel_already_cancelled_admin_fail(test_session, setup_orders_user):
    with pytest.raises(ValueError):
        cancel_order(setup_orders_user[2].id, is_admin=True)


def test_cancel_admin_can_cancel_preparing(test_session, setup_orders_user, sample_products):
    order = setup_orders_user[1]
    product = sample_products[2]
    stock_before = product.stock

    result = cancel_order(order.id, is_admin=True)

    assert result.status == OrderStatus.CANCELLED
    test_session.refresh(product)
    assert product.stock == stock_before + 1


def test_cancel_not_found(test_session):
    with pytest.raises(ValueError):
        cancel_order(99999999, is_admin=False)


def test_cancel_restores_multiple_items(test_session, setup_user, sample_products):
    o = Order(user_id=setup_user.id, delivery_address='HCM', phone='0901234567',
              total_amount=3000000000, status=OrderStatus.PENDING)
    test_session.add(o)
    test_session.flush()

    test_session.add_all([
        OrderDetail(order_id=o.id, product_id=sample_products[0].id, quantity=3),
        OrderDetail(order_id=o.id, product_id=sample_products[2].id, quantity=5),
    ])
    test_session.commit()

    s0 = sample_products[0].stock
    s2 = sample_products[2].stock

    cancel_order(o.id, is_admin=False)

    test_session.refresh(sample_products[0])
    test_session.refresh(sample_products[2])
    assert sample_products[0].stock == s0 + 3
    assert sample_products[2].stock == s2 + 5


# /api/user/my-orders
def test_get_orders_success(test_client, logged_in_user, setup_orders_user, mocker):
    mocker.patch('app.dao.get_orders_by_date', return_value=setup_orders_user)
    res = test_client.get('/api/user/my-orders')
    data = res.get_json()

    assert res.status_code == 200
    assert len(data) == 3


def test_get_orders_empty(test_client, logged_in_user, mocker):
    mocker.patch('app.dao.get_orders_by_date', return_value=[])
    assert test_client.get('/api/user/my-orders').get_json() == []


def test_get_orders_requires_login(test_client):
    assert test_client.get('/api/user/my-orders').status_code == 401


def test_get_orders_response_fields(test_client, logged_in_user, setup_orders_user, mocker):
    mocker.patch('app.dao.get_orders_by_date', return_value=setup_orders_user)

    data = test_client.get('/api/user/my-orders').get_json()

    required = {'order_id', 'created_date', 'status',
                'delivery_address', 'items', 'total_amount', 'total_items'}
    for order in data:
        assert required.issubset(order.keys())


def test_get_orders_passes_user_id(test_client, logged_in_user, mocker):
    mock_dao = mocker.patch('app.dao.get_orders_by_date', return_value=[])

    test_client.get('/api/user/my-orders')

    _, kwargs = mock_dao.call_args
    assert kwargs.get('user_id') == 1


def test_get_orders_filter_by_status(test_client, logged_in_user, mocker):
    mock_dao = mocker.patch('app.dao.get_orders_by_date', return_value=[])
    test_client.get('/api/user/my-orders?status=PENDING')

    _, kwargs = mock_dao.call_args
    assert kwargs.get('status') == 'PENDING'


def test_get_orders_item_subtotal(test_client, logged_in_user, setup_orders_user, mocker):
    mocker.patch('app.dao.get_orders_by_date', return_value=[setup_orders_user[0]])
    data = test_client.get('/api/user/my-orders').get_json()

    for item in data[0]['items']:
        assert item['sub_total'] == item['quantity'] * item['price']


# /api/orders/<id>/cancel
def test_cancel_pending_success(test_client, logged_in_user, setup_orders_user, mocker):
    o = setup_orders_user[0]
    mocker.patch('app.dao.get_order_by_id', return_value=o)
    mocker.patch('app.dao.cancel_order', return_value=o)

    res = test_client.post(f'/api/orders/{o.id}/cancel')
    data = res.get_json()

    assert res.status_code == 200
    assert data['msg'] == 'Hủy đơn hàng thành công'


def test_cancel_preparing_fail(test_client, logged_in_user, setup_orders_user, mocker):
    o = setup_orders_user[1]
    mocker.patch('app.dao.get_order_by_id', return_value=o)
    mocker.patch('app.dao.cancel_order',
                 side_effect=ValueError('Khách hàng chỉ được hủy đơn khi đang chờ xử lý'))

    res = test_client.post(f'/api/orders/{o.id}/cancel')
    assert res.status_code == 400
    assert 'chờ xử lý' in res.get_json()['err_msg']


def test_cancel_not_found(test_client, logged_in_user, mocker):
    mocker.patch('app.dao.get_order_by_id', return_value=None)

    res = test_client.post('/api/orders/9999/cancel')
    assert res.status_code == 404


def test_cancel_route_forbidden(test_client, logged_in_user, setup_orders_user, mocker):
    o = setup_orders_user[0]
    o.user_id = 100
    mocker.patch('app.dao.get_order_by_id', return_value=o)

    res = test_client.post(f'/api/orders/{o.id}/cancel')
    assert res.status_code == 403
    assert 'quyền' in res.get_json()['err_msg']


def test_cancel_requires_login(test_client):
    assert test_client.post('/api/orders/1/cancel').status_code == 401
