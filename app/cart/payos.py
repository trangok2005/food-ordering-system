import hashlib
import hmac
import os

import requests


PAYOS_BASE_URL = os.getenv(
    'PAYOS_BASE_URL',
    'https://api-merchant.payos.vn'
)
<<<<<<< Updated upstream


def _sign_payment_request(
    amount,
    cancel_url,
    description,
    order_code,
    return_url,
    checksum_key
):
    """
    Tạo chữ ký cho request thanh toán PayOS.
=======
>>>>>>> Stashed changes

def _sign_payment_request(
    amount,
    cancel_url,
    description,
    order_code,
    return_url,
    checksum_key
):
    """
    Tạo chữ ký cho request thanh toán PayOS.
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
    """
    Wrapper đơn giản để gọi PayOS Merchant API.
<<<<<<< Updated upstream

=======
>>>>>>> Stashed changes
    Hiện tại dùng cho:
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
<<<<<<< Updated upstream
=======
        if not client_id:
            raise ValueError(
                'Thiếu PAYOS_CLIENT_ID'
            )

        if not api_key:
            raise ValueError(
                'Thiếu PAYOS_API_KEY'
            )

        if not checksum_key:
            raise ValueError(
                'Thiếu PAYOS_CHECKSUM_KEY'
            )

>>>>>>> Stashed changes
        self.client_id = client_id
        self.api_key = api_key
        self.checksum_key = checksum_key
        self.base_url = base_url.rstrip('/')

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
        resp = requests.request(
            method,
            f'{self.base_url}{path}',
            headers=self._headers(),
            timeout=15,
            **kwargs
        )

        resp.raise_for_status()

        try:
            body = resp.json()
        except ValueError:
            raise ValueError(
                'PayOS trả về dữ liệu không hợp lệ'
            )

        if not isinstance(body, dict):
            raise ValueError(
                'Response PayOS không hợp lệ'
            )

        if body.get('code') != '00':
            raise ValueError(
<<<<<<< Updated upstream
                body.get('desc') or 'payOS error'
=======
                body.get('desc')
                or 'payOS error'
>>>>>>> Stashed changes
            )

        data = body.get(
            'data',
            {}
        )

<<<<<<< Updated upstream
=======
        if data is None:
            data = {}

        return data

>>>>>>> Stashed changes
    def create_payment_link(
        self,
        amount,
        description,
        reference,
        return_url,
        cancel_url
    ):
        """
        Tạo payment link.
        reference là mã đơn hàng duy nhất.
        """

<<<<<<< Updated upstream
        order_code = int(reference)
        amount = int(amount)

        description = (description or '')[:255]
=======
        try:
            order_code = int(reference)
        except (
            TypeError,
            ValueError
        ):
            raise ValueError(
                'Mã đơn hàng không hợp lệ'
            )

        try:
            amount = int(amount)
        except (
            TypeError,
            ValueError
        ):
            raise ValueError(
                'Số tiền thanh toán không hợp lệ'
            )

        if amount <= 0:
            raise ValueError(
                'Số tiền thanh toán phải lớn hơn 0'
            )

        description = (
            description or ''
        )[:255]

        if not return_url:
            raise ValueError(
                'Thiếu return URL'
            )

        if not cancel_url:
            raise ValueError(
                'Thiếu cancel URL'
            )
>>>>>>> Stashed changes

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
<<<<<<< Updated upstream

    def get_payment_request(self, payment_request_id):
        """
        Kiểm tra trạng thái payment request.
=======

    def get_payment_request(
        self,
        payment_request_id
    ):
        """
        Kiểm tra trạng thái payment request.

>>>>>>> Stashed changes
        Dùng polling khi chạy localhost vì PayOS
        không thể gọi webhook trực tiếp vào localhost.
        """

<<<<<<< Updated upstream
=======
        if not payment_request_id:
            raise ValueError(
                'Thiếu payment request ID'
            )

>>>>>>> Stashed changes
        return self._request_json(
            'GET',
            f'/v2/payment-requests/{payment_request_id}'
        )


def get_client():
    client_id = os.getenv(
        'PAYOS_CLIENT_ID'
    )

    api_key = os.getenv(
        'PAYOS_API_KEY'
    )

    checksum_key = os.getenv(
        'PAYOS_CHECKSUM_KEY'
    )

    if not client_id:
        raise RuntimeError(
            'Chưa cấu hình PAYOS_CLIENT_ID'
        )

    if not api_key:
        raise RuntimeError(
            'Chưa cấu hình PAYOS_API_KEY'
        )

    if not checksum_key:
        raise RuntimeError(
            'Chưa cấu hình PAYOS_CHECKSUM_KEY'
        )

    return PayOSClient(
        client_id=client_id,
        api_key=api_key,
        checksum_key=checksum_key,
    )