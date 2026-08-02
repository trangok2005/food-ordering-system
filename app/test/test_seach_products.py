import pytest
from app.dao import load_products
from app.models import Product
from app.test.test_base import test_app, test_session, sample_products


# ko filter
def test_load_all_products(sample_products):
    assert len(load_products()) == len(sample_products)


def test_load_products_only_active(test_session, sample_products):
    test_session.add(Product(name='ngừng bán', price=50000, stock=10, category_id=1, active=False))
    test_session.commit()

    result = load_products()
    assert 'ngừng bán' not in [p.name for p in result]
    assert len(result) == len(sample_products)


# kq
def test_kw(sample_products):
    result = load_products(kw='Nigiri')
    assert len(result) == 2
    assert all('Nigiri' in p.name for p in result)


def test_kw_no_match(sample_products):
    assert load_products(kw='Bạch tuộc') == []


# cate
def test_cate_id(sample_products):
    result = load_products(cate_id=1)
    assert len(result) == 2
    assert all(p.category_id == 1 for p in result)


def test_cate_id_not_exist(sample_products):
    assert load_products(cate_id=999) == []


# kêt hợp
def test_kw_cate(sample_products):
    result = load_products(cate_id=2, kw='Cua')
    assert len(result) == 1
    assert result[0].category_id == 2 and 'Cua' in result[0].name


def test_kw_cate_no_match(sample_products):
    assert load_products(cate_id=1, kw='Cua') == []
