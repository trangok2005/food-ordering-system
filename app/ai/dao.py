from datetime import datetime

from app import db
from app.models import (Dish, Order, OrderStatus, Review, SentimentLabel,
                        UserDishInteraction)


def get_review_for_order_dish(order, dish_id):
    # Trả về review của (user, order, dish) nếu đã đánh giá rồi,
    # dùng để chặn đánh giá 2 lần cho cùng một món trong cùng đơn.
    return (Review.query
            .filter(Review.order_id == order.id,
                    Review.dish_id == dish_id)
            .first())


def get_reviewed_dish_ids_for_orders(order_ids):
    # Những món đã được đánh giá trong từng đơn, để trang hóa đơn
    # hiển thị nút "Đã đánh giá" thay vì nút mở form.
    if not order_ids:
        return {}
    rows = (db.session.query(Review.order_id, Review.dish_id)
            .filter(Review.order_id.in_(order_ids))
            .all())
    result = {}
    for order_id, dish_id in rows:
        result.setdefault(order_id, set()).add(dish_id)
    return result


def get_dish_rating_stats(dish_id):
    # Điểm trung bình + số lượt đánh giá của một món,
    # dùng cho trang chi tiết món ăn.
    avg, count = (db.session
                  .query(db.func.avg(Review.rating),
                         db.func.count(Review.id))
                  .filter(Review.dish_id == dish_id)
                  .first())
    return {
        'avg': round(avg, 1) if avg else 0,
        'count': count or 0,
    }


def log_interaction(user_id, dish_id, interaction_type):
    # Ghi nhận hành vi của người dùng với món ăn (xem, thêm giỏ, đặt,
    # đánh giá) kèm giờ trong ngày - là dữ liệu đầu vào cho gợi ý
    # cá nhân hóa. Gọi đơn giản, không ảnh hưởng luồng chính.
    db.session.add(UserDishInteraction(
        user_id=user_id,
        dish_id=dish_id,
        interaction_type=interaction_type,
        hour_of_day=datetime.now().hour,
    ))
    db.session.commit()


def add_review(user_id, order, dish_id, rating, comment, sentiment):
    """Lưu đánh giá của khách cho một món trong đơn đã hoàn thành.

    sentiment là (label, score) trả về từ Gemini; nếu LLM không dùng
    được thì truyền None -> vẫn lưu sao + bình luận như bình thường.
    """
    existing = get_review_for_order_dish(order, dish_id)
    if existing:
        raise ValueError('Bạn đã đánh giá món này trong đơn này rồi')

    label, score = sentiment if sentiment else (None, None)

    review = Review(
        rating=rating,
        comment=comment or None,
        user_id=user_id,
        dish_id=dish_id,
        order_id=order.id,
        sentiment_label=(SentimentLabel[label] if label else None),
        sentiment_score=score,
    )
    db.session.add(review)
    db.session.commit()

    # Đánh giá cũng là một hành vi hữu ích cho gợi ý món ăn.
    log_interaction(user_id, dish_id, 'REVIEW')
    return review


def is_completed_order(order):
    return order.status == OrderStatus.COMPLETED


def order_has_dish(order, dish_id):
    # Kiểm tra món có thật sự nằm trong đơn không,
    # tránh người dùng tự sửa dish_id trên form.
    return any(item.dish_id == dish_id for item in order.order_details)


def dish_exists(dish_id):
    return Dish.query.get(dish_id) is not None