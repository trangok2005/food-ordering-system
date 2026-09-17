import hashlib
import hmac
import json
import os
import secrets

import requests


PAYOS_BASE_URL = os.getenv(
    'PAYOS_BASE_URL',
    'https://api-merchant.payos.vn'
)

# PAYOS_MODE=live  -> gọi API payOS thật
# PAYOS_MODE=mock  -> dùng cổng giả lập trong app (demo local, không tốn tiền)
PAYOS_MODE = os.getenv(
    'PAYOS_MODE',
    'live'
).strip().lower()


def verify_webhook(payload, checksum_key=None):
    """Xác thực chữ ký webhook PayOS.

    Chữ ký được tính trên chuỗi JSON của trường `data` (không có
    khoảng trắng, dấu phân tách ",", ":") bằng HMAC-SHA256 với
    PAYOS_CHECKSUM_KEY.
    """
    checksum_key = checksum_key or os.environ.get('PAYOS_CHECKSUM_KEY')
    if not checksum_key:
        return False
    if not isinstance(payload, dict):
        return False
    signature = payload.get('signature')
    data = payload.get('data')
    if not signature or data is None:
        return False
    data_str = json.dumps(
        data,
        ensure_ascii=False,
        separators=(',', ':')
    )
    expected = hmac.new(
        checksum_key.encode(),
        data_str.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, str(signature))


def _sign_payment_request(
    amount,
    cancel_url,
    description,
    order_code,
    return_url,
    checksum_key
):
    """Tạo chữ ký cho request thanh toán PayOS.

    Các field phải được ghép đúng thứ tự:
    amount
    cancelUrl
    description
    orderCode
    returnUrl
    """

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


class PayOSClient:
    """Wrapper để gọi PayOS Merchant API thật.

    Dùng cho:
    - Tạo payment link
    - Kiểm tra trạng thái thanh toán
    """

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

    def _request_json(
        self,
        method,
        path,
        **kwargs
    ):
        try:
            resp = requests.request(
                method,
                f'{self.base_url}{path}',
                headers=self._headers(),
                timeout=15,
                **kwargs
            )

        except requests.Timeout:
            raise ValueError(
                'PayOS phản hồi quá lâu, vui lòng thử lại.'
            )

        except requests.RequestException:
            raise ValueError(
                'Không thể kết nối đến PayOS.'
            )

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
                message = (
                    f'PayOS trả về HTTP {resp.status_code}.'
                )

            raise ValueError(message)

        try:
            body = resp.json()

        except ValueError:
            raise ValueError(
                'PayOS trả về dữ liệu không hợp lệ.'
            )

        if body.get('code') != '00':
            raise ValueError(
                body.get('desc')
                or 'PayOS error'
            )

        data = body.get(
            'data',
            {}
        )

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
        """Tạo payment link.
        reference là mã đơn hàng duy nhất."""

        try:
            order_code = int(reference)
            amount = int(amount)

        except (TypeError, ValueError):
            raise ValueError(
                'Thông tin mã đơn hàng hoặc số tiền không hợp lệ.'
            )

        if amount <= 0:
            raise ValueError(
                'Số tiền thanh toán phải lớn hơn 0.'
            )

        description = (
            description or ''
        )[:255]

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

    def get_payment_request(
        self,
        payment_request_id
    ):
        """Kiểm tra trạng thái payment request.
        Dùng polling khi chạy localhost vì PayOS
        không thể gọi webhook trực tiếp vào localhost."""

        if not payment_request_id:
            raise ValueError(
                'Thiếu mã thanh toán PayOS.'
            )

        return self._request_json(
            'GET',
            f'/v2/payment-requests/{payment_request_id}'
        )


class MockPayOSClient:
    """Cổng thanh toán PayOS GIẢ LẬP dùng khi demo trên localhost.

    Mô phỏng đúng 2 phương thức mà hệ thống dùng của PayOSClient:
    - create_payment_link
    - get_payment_request
    """

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
            raise ValueError(
                'Thông tin thanh toán không hợp lệ.'
            )

        if amount <= 0:
            raise ValueError(
                'Số tiền thanh toán phải lớn hơn 0.'
            )

        payment_id = str(
            reference
        )

        MockPayOSClient.payments[
            payment_id
        ] = {
            'id': payment_id,
            'amount': amount,
            'description': (
                description or ''
            )[:255],
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

    def get_payment_request(
        self,
        payment_request_id
    ):
        payment = (
            MockPayOSClient.payments.get(
                str(payment_request_id)
            )
        )

        if not payment:
            raise ValueError(
                'Không tìm thấy phiên thanh toán giả lập'
            )

        return dict(
            payment
        )


def get_client():
    """Factory chọn client payOS theo cấu hình PAYOS_MODE trong .env."""

    if PAYOS_MODE == 'live':
        client_id = os.environ.get(
            'PAYOS_CLIENT_ID'
        )

        api_key = os.environ.get(
            'PAYOS_API_KEY'
        )

        checksum_key = os.environ.get(
            'PAYOS_CHECKSUM_KEY'
        )

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