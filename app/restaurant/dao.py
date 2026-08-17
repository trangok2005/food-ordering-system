from datetime import datetime

from sqlalchemy import func

from app import db
from app.models import (Order, OrderDetail, OrderStatus, PaymentStatus,
                        Restaurant)


NEXT_STATUS = {
    OrderStatus.CONFIRMED: OrderStatus.PREPARING,
    OrderStatus.PREPARING: OrderStatus.DELIVERING,
    OrderStatus.DELIVERING: OrderStatus.COMPLETED,
}


def get_restaurant_for_owner(user_id):
    return Restaurant.query.filter(Restaurant.owner_id == user_id).first()


def get_restaurant_orders(restaurant_id, status=None):
    query = Order.query.filter(Order.restaurant_id == restaurant_id)
    if status:
        query = query.filter(Order.status == status)
    return query.order_by(Order.created_date.desc(), Order.id.desc()).all()


def get_order_status_counts(restaurant_id):
    """Số đơn theo từng trạng thái, dùng cho tab lọc trên dashboard."""
    rows = (db.session.query(Order.status, func.count(Order.id))
            .filter(Order.restaurant_id == restaurant_id)
            .group_by(Order.status)
            .all())
    return {status: count for status, count in rows}


def get_order_for_restaurant(order_id, restaurant_id):
    return (Order.query
            .filter(Order.id == order_id,
                    Order.restaurant_id == restaurant_id)
            .first())


def expire_overdue_orders(restaurant_id):
    """Chuyển các đơn PENDING đã quá hạn xác nhận thành EXPIRED.
    Được gọi mỗi khi nhà hàng mở trang quản lý đơn (không có job nền)."""
    now = datetime.now()
    overdue = (Order.query
               .filter(Order.restaurant_id == restaurant_id,
                       Order.status == OrderStatus.PENDING,
                       Order.confirm_deadline.isnot(None),
                       Order.confirm_deadline < now)
               .all())
    for order in overdue:
        order.status = OrderStatus.EXPIRED
    if overdue:
        db.session.commit()
    return overdue


def confirm_order(order):
    """Nhà hàng xác nhận đơn đang PENDING -> CONFIRMED.
    Chỉ được xác nhận trước confirm_deadline; quá hạn thì đơn đã EXPIRED."""
    if order.is_expired():
        order.status = OrderStatus.EXPIRED
        db.session.commit()
        raise ValueError('Đơn đã quá hạn xác nhận, không thể xác nhận')
    if order.status != OrderStatus.PENDING:
        raise ValueError('Chỉ xác nhận được đơn đang chờ xác nhận')

    order.status = OrderStatus.CONFIRMED
    order.confirmed_at = datetime.now()
    db.session.commit()
    return order


def advance_order(order):
    """Chuyển đơn sang trạng thái tiếp theo:
    CONFIRMED -> PREPARING -> DELIVERING -> COMPLETED."""
    next_status = NEXT_STATUS.get(order.status)
    if not next_status:
        raise ValueError('Trạng thái hiện tại của đơn không thể chuyển tiếp')
    order.status = next_status
    db.session.commit()
    return order


def cancel_order(order, reason):
    """Nhà hàng hủy đơn đã thanh toán (hết nguyên liệu, quá tải...).
    Chỉ lưu trạng thái + lý do; việc hoàn tiền nhà hàng tự liên hệ
    và thực hiện trực tiếp với khách, ngoài hệ thống."""
    reason = (reason or '').strip()
    if not reason:
        raise ValueError('Vui lòng nhập lý do hủy đơn')
    if order.status in (OrderStatus.COMPLETED,
                        OrderStatus.CANCELLED,
                        OrderStatus.EXPIRED):
        raise ValueError('Đơn này không thể hủy')

    order.cancel_by_restaurant(reason)
    db.session.commit()
    return order


def mark_refunded(order):
    """Đánh dấu đơn đã hủy là đã hoàn tiền - dùng SAU KHI nhà hàng đã tự
    chuyển tiền cho khách ngoài hệ thống (chỉ lưu vết, không gọi API thật)."""
    if order.status != OrderStatus.CANCELLED:
        raise ValueError('Chỉ đơn đã hủy mới đánh dấu được hoàn tiền')
    if order.payment_status == PaymentStatus.REFUNDED:
        raise ValueError('Đơn này đã được đánh dấu hoàn tiền')
    order.mark_refunded_manually()
    db.session.commit()
    return order


def get_dashboard_stats(restaurant_id):
    """Số liệu tổng quan cho trang dashboard nhà hàng."""
    counts = get_order_status_counts(restaurant_id)
    revenue = (db.session.query(func.coalesce(func.sum(Order.total_amount), 0))
               .filter(Order.restaurant_id == restaurant_id,
                       Order.status.in_([OrderStatus.COMPLETED,
                                         OrderStatus.DELIVERING]))
               .scalar())
    return {'counts': counts, 'revenue': revenue}


def update_restaurant_settings(restaurant, data):
    """Cập nhật cấu hình nhà hàng: giá trị đơn tối thiểu, thời gian xác
    nhận, bán kính giao hàng, số lượng tối đa 1 món/đơn, trạng thái mở cửa.
    Trường để trống -> dùng mặc định hệ thống (None)."""
    phone = (data.get('phone') or '').strip()
    description = (data.get('description') or '').strip()

    def _int_field(name):
        raw = (data.get(name) or '').strip()
        if not raw:
            return None
        try:
            return int(float(raw))
        except (TypeError, ValueError):
            raise ValueError('Giá trị nhập không hợp lệ')

    def _float_field(name):
        raw = (data.get(name) or '').strip()
        if not raw:
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            raise ValueError('Giá trị nhập không hợp lệ')

    min_amount = _int_field('min_order_amount')
    timeout = _int_field('confirm_timeout_minutes')
    radius = _float_field('delivery_radius_km')
    max_qty = _int_field('max_quantity_per_item')
    latitude = _float_field('latitude')
    longitude = _float_field('longitude')

    if phone and not (phone.isdigit() and 10 <= len(phone) <= 11):
        raise ValueError('Số điện thoại phải từ 10 đến 11 ký số')
    if min_amount is not None and min_amount < 0:
        raise ValueError('Giá trị đơn tối thiểu không thể âm')
    if timeout is None or timeout < 1:
        raise ValueError('Thời gian xác nhận tối thiểu 1 phút')
    if max_qty is not None and max_qty < 1:
        raise ValueError('Số lượng tối đa 1 món/đơn tối thiểu 1 phần')

    if radius is not None and radius <= 0:
        raise ValueError('Bán kính giao hàng phải lớn hơn 0')

    if (latitude is None) != (longitude is None):
        raise ValueError('Vui lòng nhập đầy đủ cả kinh độ và vĩ độ')

    if latitude is not None and not (-90 <= latitude <= 90):
        raise ValueError('Vĩ độ phải nằm trong khoảng -90 đến 90')
    if longitude is not None and not (-180 <= longitude <= 180):
        raise ValueError('Kinh độ phải nằm trong khoảng -180 đến 180')

    restaurant.is_open = bool(data.get('is_open'))
    restaurant.phone = phone
    restaurant.description = description or None
    restaurant.min_order_amount = min_amount
    restaurant.confirm_timeout_minutes = timeout
    restaurant.delivery_radius_km = radius
    restaurant.max_quantity_per_item = max_qty
    restaurant.latitude = latitude
    restaurant.longitude = longitude
    db.session.commit()
    return restaurant