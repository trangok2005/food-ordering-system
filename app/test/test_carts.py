import pytest
from app.test.test_base import test_app, test_session, test_client, sample_products, logged_in_user, \
    cart_standard


@pytest.fixture
def mock_restaurant_open(mocker):
    return mocker.patch('app.utils.is_restaurant_available', return_value=True)


# post
def test_add_to_cart_first(test_client, logged_in_user, mock_restaurant_open, sample_products):
    res = test_client.post('/api/carts',
                           json={"id": 1, "name": "Cá hồi Sashimi", "price": 120000, "quantity": 1})
    data = res.get_json()

    assert res.status_code == 200
    assert data['total_quantity'] == 1
    assert data['total_amount'] == 120000

    with test_client.session_transaction() as sess:
        assert '1' in sess['cart']
        assert sess['cart']['1']['quantity'] == 1


def test_add_to_cart_accumulate_quantity(test_client, logged_in_user, mock_restaurant_open, sample_products):
    test_client.post('/api/carts', json={"id": 1, "name": "Cá hồi Sashimi", "price": 120000, "quantity": 1})
    res = test_client.post('/api/carts', json={"id": 1, "name": "Cá hồi Sashimi", "price": 120000, "quantity": 1})
    data = res.get_json()

    assert res.status_code == 200
    assert data['total_amount'] == 240000
    assert data['total_quantity'] == 2

    with test_client.session_transaction() as sess:
        assert sess['cart']['1']['quantity'] == 2


def test_add_different_items(test_client, logged_in_user, mock_restaurant_open, sample_products):
    test_client.post('/api/carts', json={"id": 1, "name": "Cá hồi Sashimi", "price": 120000, "quantity": 2})
    res = test_client.post('/api/carts', json={"id": 3, "name": "Cá Nigiri", "price": 90000, "quantity": 1})
    data = res.get_json()

    assert res.status_code == 200
    assert data['total_quantity'] == 3
    assert data['total_amount'] == 120000 * 2 + 90000

    with test_client.session_transaction() as sess:
        assert len(sess['cart']) == 2


def test_add_to_cart_restaurant_closed(test_client, logged_in_user, mocker, sample_products):
    mocker.patch('app.utils.is_restaurant_available', side_effect=ValueError('Nhà hàng hiện đã đóng cửa'))
    res = test_client.post('/api/carts', json={"id": 1, "name": "Cá hồi Sashimi", "price": 120000})
    data = res.get_json()

    assert res.status_code == 400
    assert data['err_msg'] == 'Nhà hàng hiện đã đóng cửa'


@pytest.mark.parametrize('payload, expected_msg', [
    ({"id": 1, "name": "Cá hồi", "price": 120000, "quantity": 0}, "Số lượng không hợp lệ"),
    ({"id": 10, "name": "Không tồn tại", "price": 120000}, "Sản phẩm không tồn tại"),
    ({"id": 2, "name": "Hết hàng", "price": 50000}, "Tồn kho không đủ"),
    ({"id": 1, "name": "Cá hồi", "price": 120000, "quantity": 11}, "Mỗi món chỉ được đặt tối đa 10 phần"),
])
def test_add_to_cart_validations(test_client, logged_in_user, mock_restaurant_open, sample_products, payload,
                                 expected_msg):
    res = test_client.post('/api/carts', json=payload)
    data = res.get_json()

    assert res.status_code == 400
    assert data['status'] == 400
    assert expected_msg in data['err_msg']


def test_add_to_cart_exceed_total_50(test_client, logged_in_user, mock_restaurant_open, sample_products):
    with test_client.session_transaction() as sess:
        sess['cart'] = {
            str(i): {"id": i, "name": "Món", "price": 10000, "quantity": 7}
            for i in range(1, 8)
        }

    res = test_client.post('/api/carts', json={"id": 1, "name": "Cá hồi Sashimi", "price": 120000, "quantity": 2})

    assert res.status_code == 400
    assert res.get_json()['status'] == 400


# put--
def test_update_cart_success(test_client, sample_products):
    with test_client.session_transaction() as sess:
        sess['cart'] = {"1": {"id": 1, "name": "Cá hồi Sashimi", "price": 120000, "quantity": 2}}

    res = test_client.put('/api/carts/1', json={"quantity": 5})
    data = res.get_json()

    assert res.status_code == 200
    assert data['data']['total_quantity'] == 5
    assert data['data']['total_amount'] == 600000

    with test_client.session_transaction() as sess:
        assert sess['cart']['1']['quantity'] == 5


def test_update_cart_not_in_cart(test_client, sample_products):
    with test_client.session_transaction() as sess:
        sess['cart'] = {"1": {"id": 1, "name": "Cá hồi Sashimi", "price": 120000, "quantity": 2}}

    res = test_client.put('/api/carts/99', json={"quantity": 3})
    data = res.get_json()

    assert res.status_code == 400
    assert data['err_msg'] == 'Sản phẩm không có trong giỏ'


def test_update_cart_exceed_stock(test_client, sample_products):
    with test_client.session_transaction() as sess:
        sess['cart'] = {"1": {"id": 1, "name": "Cá hồi Sashimi", "price": 120000, "quantity": 2}}

    res = test_client.put('/api/carts/1', json={"quantity": 51})

    assert res.status_code == 400


def test_update_cart_exceed_item_limit_10(test_client, sample_products):
    with test_client.session_transaction() as sess:
        sess['cart'] = {"1": {"id": 1, "name": "Cá hồi Sashimi", "price": 120000, "quantity": 2}}

    res = test_client.put('/api/carts/1', json={"quantity": 11})
    data = res.get_json()

    assert res.status_code == 400
    assert 'tối đa 10' in data['err_msg']


def test_update_cart_max_total_limit(test_client, sample_products):
    with test_client.session_transaction() as sess:
        sess['cart'] = {
            str(i): {"id": i, "name": "Món", "price": 100000, "quantity": 7}
            for i in range(1, 8)
        }

    res = test_client.put('/api/carts/1', json={"quantity": 9})
    data = res.get_json()

    assert res.status_code == 400
    assert 'Vượt quá 50 món' in data['err_msg']


def test_delete_cart_item_success(test_client, sample_products):
    with test_client.session_transaction() as sess:
        sess['cart'] = {
            "1": {"id": 1, "name": "Cá hồi Sashimi", "price": 120000, "quantity": 5},
            "2": {"id": 2, "name": "Cá ngừ Sashimi", "price": 100000, "quantity": 10},
        }

    res = test_client.delete('/api/carts/1')
    data = res.get_json()

    assert data['total_quantity'] == 10
    assert data['total_amount'] == 1000000

    with test_client.session_transaction() as sess:
        assert '1' not in sess['cart']
        assert len(sess['cart']) == 1


def test_delete_cart_all_items(test_client, sample_products):
    with test_client.session_transaction() as sess:
        sess['cart'] = {"1": {"id": 1, "name": "Cá hồi", "price": 120000, "quantity": 2}}

    res = test_client.delete('/api/carts/1')
    data = res.get_json()

    assert data['total_quantity'] == 0
    assert data['total_amount'] == 0

    with test_client.session_transaction() as sess:
        assert sess['cart'] == {}
