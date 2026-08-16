import hashlib
import hmac
import os

import requests


PAYOS_BASE_URL = os.getenv(
    'PAYOS_BASE_URL',
    'https://api-merchant.payos.vn'
)


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
        resp = requests.request(
            method,
            f'{self.base_url}{path}',
            headers=self._headers(),
            timeout=15,
            **kwargs
        )

        resp.raise_for_status()

        body = resp.json()

        if body.get('code') != '00':
            raise ValueError(
                body.get('desc') or 'payOS error'
            )

        return body.get('data', {})

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

        order_code = int(reference)
        amount = int(amount)

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
        """
        Kiểm tra trạng thái payment request.
        Dùng polling khi chạy localhost vì PayOS
        không thể gọi webhook trực tiếp vào localhost.
        """

        return self._request_json(
            'GET',
            f'/v2/payment-requests/{payment_request_id}'
        )


def get_client():
    return PayOSClient(
        client_id=os.environ['PAYOS_CLIENT_ID'],
        api_key=os.environ['PAYOS_API_KEY'],
        checksum_key=os.environ['PAYOS_CHECKSUM_KEY'],
    )