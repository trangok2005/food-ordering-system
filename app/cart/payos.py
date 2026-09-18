import hashlib
import hmac
import os
import secrets
import json

import requests


PAYOS_BASE_URL = os.getenv(
    'PAYOS_BASE_URL',
    'https://api-merchant.payos.vn'
)

PAYOS_MODE = os.getenv('PAYOS_MODE', 'mock').strip().lower()
if PAYOS_MODE not in ('mock', 'live'):
    raise RuntimeError('PAYOS_MODE chỉ nhận giá trị mock hoặc live')


def _sign_payment_request(
    amount,
    cancel_url,
    description,
    order_code,
    return_url,
    checksum_key
):
    """Ký các trường thanh toán theo đúng thứ tự payOS yêu cầu."""
    data_str = (
        f"amount={amount}"
        f"&cancelUrl={cancel_url}"
        f"&description={description}"
        f"&orderCode={order_code}"
        f"&returnUrl={return_url}"
    )

    return hmac.new(
        checksum_key.encode(),
        data_str.encode(),
        hashlib.sha256
    ).hexdigest()


def sign_webhook_data(data, checksum_key):
    """Tạo chữ ký webhook theo thứ tự khóa tăng dần như tài liệu payOS."""
    parts = []
    for key in sorted(data):
        value = data[key]
        if value is None:
            value = ''
        elif isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
        elif isinstance(value, bool):
            value = str(value).lower()
        parts.append(f'{key}={value}')
    return hmac.new(
        checksum_key.encode(), '&'.join(parts).encode(), hashlib.sha256
    ).hexdigest()


def verify_webhook(payload):
    data = payload.get('data') if isinstance(payload, dict) else None
    signature = payload.get('signature') if isinstance(payload, dict) else None
    checksum_key = os.getenv('PAYOS_CHECKSUM_KEY', '').strip()
    if not data or not signature or not checksum_key:
        return False
    return hmac.compare_digest(sign_webhook_data(data, checksum_key), signature)


class PayOSClient:

    def __init__(
        self,
        client_id,
        api_key,
        checksum_key,
        base_url=PAYOS_BASE_URL
    ):
        self.client_id = client_id
        self.api_key = api_key
        self.checksum_key = checksum_key
        self.base_url = base_url

    def _headers(self):
        return {
            'x-client-id': self.client_id,
            'x-api-key': self.api_key,
            'Content-Type': 'application/json',
        }

    def _request_json(self, method, path, **kwargs):
        try:
            resp = requests.request(
                method,
                f'{self.base_url}{path}',
                headers=self._headers(),
                timeout=15,
                **kwargs
            )

        except requests.Timeout:
            raise ValueError('PayOS phản hồi quá lâu, vui lòng thử lại.')

        except requests.RequestException:
            raise ValueError('Không thể kết nối đến PayOS.')

        try:
            resp.raise_for_status()

        except requests.HTTPError:
            try:
                body = resp.json()
                message = (
                    body.get('desc')
                    or body.get('message')
                    or 'PayOS trả về lỗi HTTP.'
                )
            except ValueError:
                message = f'PayOS trả về HTTP {resp.status_code}.'

            raise ValueError(message)

        try:
            body = resp.json()

        except ValueError:
            raise ValueError('PayOS trả về dữ liệu không hợp lệ.')

        if body.get('code') != '00':
            raise ValueError(body.get('desc') or 'PayOS error')

        data = body.get('data', {})

        if data is None:
            return {}

        return data

    def create_payment_link(
        self,
        amount,
        description,
        reference,
        return_url,
        cancel_url
    ):
        """Dùng mã đơn làm reference."""
        try:
            order_code = int(reference)
            amount = int(amount)

        except (TypeError, ValueError):
            raise ValueError('Thông tin mã đơn hàng hoặc số tiền không hợp lệ.')

        if amount <= 0:
            raise ValueError('Số tiền thanh toán phải lớn hơn 0.')

        description = (description or '')[:255]

        signature = _sign_payment_request(
            amount,
            cancel_url,
            description,
            order_code,
            return_url,
            self.checksum_key
        )

        payload = {
            'orderCode': order_code,
            'amount': amount,
            'description': description,
            'cancelUrl': cancel_url,
            'returnUrl': return_url,
            'signature': signature,
        }

        return self._request_json(
            'POST',
            '/v2/payment-requests',
            json=payload
        )

    def get_payment_request(self, payment_request_id):
        if not payment_request_id:
            raise ValueError('Thiếu mã thanh toán PayOS.')

        return self._request_json(
            'GET',
            f'/v2/payment-requests/{payment_request_id}'
        )


class MockPayOSClient:

    payments = {}

    def create_payment_link(
        self,
        amount,
        description,
        reference,
        return_url,
        cancel_url
    ):
        from flask import url_for

        try:
            amount = int(amount)
            reference = int(reference)

        except (TypeError, ValueError):
            raise ValueError('Thông tin thanh toán không hợp lệ.')

        if amount <= 0:
            raise ValueError('Số tiền thanh toán phải lớn hơn 0.')

        payment_id = str(reference)

        MockPayOSClient.payments[payment_id] = {
            'id': payment_id,
            'amount': amount,
            'description': (description or '')[:255],
            'status': 'PENDING',
            'return_url': return_url,
            'cancel_url': cancel_url,
        }

        return {
            'id': payment_id,
            'orderCode': reference,
            'amount': amount,
            'description': description,
            'checkoutUrl': url_for(
                'cart.mock_checkout_view',
                payment_id=payment_id,
                _external=True
            ),
        }

    def get_payment_request(self, payment_request_id):
        payment = MockPayOSClient.payments.get(str(payment_request_id))

        if not payment:
            raise ValueError('Không tìm thấy phiên thanh toán giả lập')

        return dict(payment)


def get_client():
    if PAYOS_MODE == 'live':
        client_id = os.environ.get('PAYOS_CLIENT_ID')
        api_key = os.environ.get('PAYOS_API_KEY')
        checksum_key = os.environ.get('PAYOS_CHECKSUM_KEY')

        if not client_id or not api_key or not checksum_key:
            raise ValueError(
                'Thiếu cấu hình PAYOS_CLIENT_ID, '
                'PAYOS_API_KEY hoặc PAYOS_CHECKSUM_KEY.'
            )

        return PayOSClient(
            client_id=client_id,
            api_key=api_key,
            checksum_key=checksum_key,
        )

    return MockPayOSClient()
