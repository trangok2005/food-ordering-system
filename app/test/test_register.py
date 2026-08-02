import hashlib
import pytest
from sqlalchemy.exc import IntegrityError
from app.test.test_base import test_app, test_session
from app.dao import add_user
from app.models import User, UserRole


# dao
def test_register_success(test_session):
    add_user(username='demo1', password='123ABC123',
             phone='0123456789', address='HCM City')

    u = User.query.filter(User.username == 'demo1').first()

    assert u is not None
    assert u.username == 'demo1'
    assert u.phone == '0123456789'
    assert u.address == 'HCM City'
    assert u.password == hashlib.md5('123ABC123'.encode('utf-8')).hexdigest()
    assert u.role == UserRole.USER


def test_default_active(test_session):
    add_user(username='active_user', password='123ABC123',
             phone='0123456789', address='HCM')

    u = User.query.filter(User.username == 'active_user').first()

    assert u.active is True


# pass
@pytest.mark.parametrize('password', [
    '1',
    '1' * 8,
    'a' * 8,
    '1a1' * 2,
])
def test_invalid_password(password, test_session):
    with pytest.raises(ValueError):
        add_user(username='demodemo', password=password,
                 phone='0123456789', address='HCM City')


# sdt
@pytest.mark.parametrize('phone', [
    '1230',
    'abc1234567',
    '012309090?',
    '111111111111',
])
def test_invalid_phone(phone, test_session):
    with pytest.raises(ValueError):
        add_user(username='demo123', password='123ABC123',
                 phone=phone, address='HCM')


def test_phone_required(test_session):
    with pytest.raises(Exception):
        add_user(username='demo1', password='123ABC123',
                 phone=None, address='HCM')


def test_address_required(test_session):
    with pytest.raises(Exception):
        add_user(username='demo2', password='123ABC123',
                 phone='0123456789', address=None)


def test_existing_username(test_session):
    add_user(username='demodemo', password='123ABC123',
             phone='0123456780', address='HCM')

    with pytest.raises(ValueError):
        add_user(username='demodemo', password='123ABC123',
                 phone='0199999999', address='HN')
