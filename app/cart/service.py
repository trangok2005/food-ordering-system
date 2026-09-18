import hashlib
import json
import logging
import secrets
from datetime import datetime

from flask import current_app, has_request_context, request
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import PaymentAttempt, PaymentAttemptStatus, Order
from app.cart import payos


logger = logging.getLogger(__name__)


TERMINAL_STATUSES = {
    PaymentAttemptStatus.FINALIZED,
    PaymentAttemptStatus.FAILED,
    PaymentAttemptStatus.CANCELLED,
    PaymentAttemptStatus.EXPIRED,
}


class PaymentService:
    """Xử lý phiên thanh toán và hoàn tất đơn."""

    @staticmethod
    def _snapshot_hash(payload):
        canonical = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')
        )
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()

    @staticmethod
    def _callback_url(endpoint):
        base_url = str(current_app.config.get('APP_BASE_URL') or '').rstrip('/')
        if not base_url and has_request_context():
            base_url = request.url_root.rstrip('/')
        if not base_url:
            raise RuntimeError('APP_BASE_URL chưa được cấu hình')
        rule = next(
            rule for rule in current_app.url_map.iter_rules()
            if rule.endpoint == endpoint
        )
        return base_url + rule.rule

    @staticmethod
    def _order_code():
        return str(secrets.randbelow(900000000) + 100000000)

    def create_payment(self, user_id, address, phone, note='', lat=None, lng=None,
                       client=None):
        from app.cart import dao

        snapshot = dao.build_checkout_payload(user_id, lat=lat, lng=lng)
        snapshot.update({
            'address': address,
            'phone': phone,
            'note': note,
            'lat': lat,
            'lng': lng,
        })
        snapshot_hash = self._snapshot_hash(snapshot)

        existing = (PaymentAttempt.query
                    .filter_by(user_id=user_id, snapshot_key=snapshot_hash)
                    .with_for_update().first())
        if existing and existing.status == PaymentAttemptStatus.CREATED:
            return existing
        if existing:
            raise ValueError('Phiên thanh toán cho giỏ hàng này đang được xử lý')

        attempt = PaymentAttempt(
            order_code=self._order_code(),
            amount=int(snapshot['total']),
            payload=json.dumps(snapshot, ensure_ascii=False, sort_keys=True),
            snapshot_hash=snapshot_hash,
            snapshot_key=snapshot_hash,
            status=PaymentAttemptStatus.CREATING,
            user_id=user_id,
        )
        try:
            db.session.add(attempt)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            existing = PaymentAttempt.query.filter_by(
                user_id=user_id, snapshot_key=snapshot_hash
            ).first()
            if existing and existing.status == PaymentAttemptStatus.CREATED:
                return existing
            raise ValueError('Phiên thanh toán cho giỏ hàng này đang được xử lý')

        try:
            provider = client or payos.get_client()
            link = provider.create_payment_link(
                amount=attempt.amount,
                description=f'Food Ordering #{attempt.order_code}',
                reference=int(attempt.order_code),
                return_url=self._callback_url('cart.payment_return'),
                cancel_url=self._callback_url('cart.payment_cancel'),
            )
        except Exception as exc:
            db.session.rollback()
            failed = db.session.get(PaymentAttempt, attempt.id)
            failed.status = PaymentAttemptStatus.FAILED
            failed.snapshot_key = None
            failed.error_code = 'PROVIDER_ERROR'
            failed.last_error = str(exc)[:2000]
            failed.updated_at = datetime.now()
            db.session.commit()
            logger.warning(
                'Payment provider rejected attempt %s: %s',
                attempt.id,
                type(exc).__name__,
            )
            raise

        payment_request_id = (
            link.get('paymentLinkId') or link.get('id')
            if isinstance(link, dict) else None
        )
        if not payment_request_id or not link.get('checkoutUrl'):
            self._mark_provider_error(attempt.id, 'PayOS trả về dữ liệu thanh toán không hợp lệ.')
            raise ValueError('PayOS trả về dữ liệu thanh toán không hợp lệ.')

        payment_request_id = str(payment_request_id)
        checkout_url = str(link['checkoutUrl'])
        try:
            attempt.payment_request_id = payment_request_id
            attempt.checkout_url = checkout_url
            attempt.status = PaymentAttemptStatus.CREATED
            attempt.updated_at = datetime.now()
            db.session.commit()
            return attempt
        except Exception:
            db.session.rollback()
            logger.exception(
                'Provider payment exists but attempt %s update failed; retrying persistence',
                attempt.id,
            )
            recovery = (PaymentAttempt.query.filter_by(id=attempt.id)
                        .with_for_update().first())
            recovery.payment_request_id = payment_request_id
            recovery.checkout_url = checkout_url
            recovery.status = PaymentAttemptStatus.CREATED
            recovery.updated_at = datetime.now()
            db.session.commit()
            return recovery

    @staticmethod
    def _mark_provider_error(attempt_id, message):
        db.session.rollback()
        failed = db.session.get(PaymentAttempt, attempt_id)
        failed.status = PaymentAttemptStatus.FAILED
        failed.snapshot_key = None
        failed.error_code = 'PROVIDER_ERROR'
        failed.last_error = str(message)[:2000]
        failed.updated_at = datetime.now()
        db.session.commit()

    @classmethod
    def save_legacy_attempt(cls, user_id, pending):
        snapshot_hash = cls._snapshot_hash({
            key: value for key, value in pending.items()
            if key not in ('order_code', 'payment_request_id')
        })
        attempt = PaymentAttempt(
            order_code=str(pending['order_code']),
            payment_request_id=str(pending['payment_request_id']),
            amount=int(pending['total']),
            payload=json.dumps(pending, ensure_ascii=False, sort_keys=True),
            snapshot_hash=snapshot_hash,
            snapshot_key=snapshot_hash,
            status=PaymentAttemptStatus.CREATED,
            user_id=user_id,
        )
        try:
            db.session.add(attempt)
            db.session.commit()
            return attempt
        except Exception:
            db.session.rollback()
            raise ValueError('Không thể lưu phiên thanh toán')

    @staticmethod
    def get(identifier, user_id=None, by_order_code=False, lock=False):
        column = (PaymentAttempt.order_code if by_order_code
                  else PaymentAttempt.payment_request_id)
        query = PaymentAttempt.query.filter(column == str(identifier))
        if user_id is not None:
            query = query.filter(PaymentAttempt.user_id == user_id)
        if lock:
            query = query.with_for_update()
        return query.first()

    def mark_terminal(self, identifier, status, user_id=None, error=None,
                      by_order_code=False):
        if status not in TERMINAL_STATUSES - {PaymentAttemptStatus.FINALIZED}:
            raise ValueError('Trạng thái thanh toán terminal không hợp lệ')
        attempt = self.get(identifier, user_id, by_order_code, lock=True)
        if not attempt:
            raise ValueError('Phiên thanh toán không tồn tại')
        if attempt.status == PaymentAttemptStatus.FINALIZED:
            return attempt
        attempt.status = status
        attempt.snapshot_key = None
        attempt.last_error = error
        attempt.updated_at = datetime.now()
        db.session.commit()
        return attempt

    def process_provider_status(self, identifier, provider_status, user_id=None):
        status = str(provider_status or '').upper()
        if status == 'PAID':
            return self.finalize(identifier, user_id=user_id, assume_paid=True)
        if status in ('FAILED', 'CANCELLED', 'EXPIRED'):
            self.mark_terminal(identifier, status, user_id=user_id)
        return []

    def finalize(self, identifier, user_id=None, assume_paid=False,
                 by_order_code=False):
        attempt = self.get(identifier, user_id, by_order_code, lock=True)
        if not attempt:
            raise ValueError('Phiên thanh toán không tồn tại')
        if attempt.status == PaymentAttemptStatus.FINALIZED:
            return self._orders(attempt)
        if attempt.status in TERMINAL_STATUSES:
            raise ValueError('Phiên thanh toán đã kết thúc')
        if not assume_paid and attempt.status not in (
                PaymentAttemptStatus.PAID_PENDING_FINALIZE,
                PaymentAttemptStatus.FINALIZE_FAILED):
            raise ValueError('Thanh toán chưa được xác nhận')

        attempt.status = PaymentAttemptStatus.PAID_PENDING_FINALIZE
        attempt.updated_at = datetime.now()
        db.session.commit()

        try:
            return self._finalize_paid(attempt.id)
        except Exception as exc:
            db.session.rollback()
            failed = (PaymentAttempt.query.filter_by(id=attempt.id)
                      .with_for_update().first())
            if failed and failed.status != PaymentAttemptStatus.FINALIZED:
                failed.status = PaymentAttemptStatus.FINALIZE_FAILED
                failed.last_error = str(exc)[:2000]
                failed.retry_count = (failed.retry_count or 0) + 1
                failed.updated_at = datetime.now()
                db.session.commit()
            logger.exception('Finalizing paid attempt %s failed', attempt.id)
            if isinstance(exc, ValueError):
                raise
            raise ValueError('Thanh toán thành công nhưng chưa thể tạo đơn hàng')

    def _finalize_paid(self, attempt_id):
        from app.cart import dao

        attempt = (PaymentAttempt.query.filter_by(id=attempt_id)
                   .with_for_update().first())
        if attempt.status == PaymentAttemptStatus.FINALIZED:
            return self._orders(attempt)
        existing = Order.query.filter_by(payment_attempt_id=attempt.id).all()
        if existing:
            attempt.status = PaymentAttemptStatus.FINALIZED
            attempt.snapshot_key = None
            attempt.result_order_ids = ','.join(str(order.id) for order in existing)
            attempt.processed_at = datetime.now()
            db.session.commit()
            return existing

        pending = json.loads(attempt.payload)
        if int(pending.get('total', 0)) != attempt.amount:
            raise ValueError('Số tiền thanh toán không khớp')
        return dao.create_orders_from_pending(
            attempt.user_id, pending, payment_attempt=attempt
        )

    @staticmethod
    def _orders(attempt):
        ids = [int(value) for value in (attempt.result_order_ids or '').split(',')
               if value]
        return Order.query.filter(Order.id.in_(ids)).order_by(Order.id).all()

    def handle_webhook(self, payload):
        data = payload.get('data') or {}
        attempt = self.get(data.get('orderCode'), by_order_code=True, lock=True)
        if not attempt:
            logger.warning('Webhook references unknown order code')
            raise LookupError('Không tìm thấy phiên thanh toán')
        if int(data.get('amount') or 0) != attempt.amount:
            logger.warning('Webhook amount mismatch for attempt %s', attempt.id)
            raise ValueError('Số tiền không khớp')
        provider_status = str(data.get('status') or '').upper()
        if payload.get('success') is True and data.get('code') == '00':
            provider_status = 'PAID'
        if provider_status == 'PAID':
            return self.finalize(
                attempt.order_code, assume_paid=True, by_order_code=True
            )
        if provider_status in ('FAILED', 'CANCELLED', 'EXPIRED'):
            self.mark_terminal(
                attempt.order_code, provider_status, by_order_code=True
            )
        return []
