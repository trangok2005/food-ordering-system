<<<<<<< Updated upstream
=======
from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.models import Order, Review
from app.ai import ai_bp
from app.ai import dao

# Router không gọi trực tiếp Gemini nữa.
# Sentiment service sẽ làm lớp trung gian xử lý sentiment.
from app.ai import sentiment as sentiment_service


def _load_order(order_id):
    order = (Order.query
             .filter(Order.id == order_id,
                     Order.user_id == current_user.id)
             .first())
    if not order:
        abort(404)
    return order


@ai_bp.route('/reviews')
@login_required
def my_reviews():
    reviews = (Review.query
               .filter(Review.user_id == current_user.id)
               .order_by(Review.created_date.desc())
               .all())
    return render_template('ai/reviews.html', reviews=reviews)


@ai_bp.route('/reviews/add', methods=['POST'])
@login_required
def add_review():
    order_id = request.form.get('order_id', type=int)
    dish_id = request.form.get('dish_id', type=int)
    rating = request.form.get('rating', type=int)
    comment = (request.form.get('comment') or '').strip()

    order = _load_order(order_id)

    # Chỉ đánh giá được món của đơn đã giao thành công.
    if not dao.is_completed_order(order):
        flash('Chỉ đánh giá được khi đơn đã hoàn thành', 'error')
        return redirect(url_for('cart.my_orders'))

    if not dish_id or not dao.dish_exists(dish_id):
        flash('Món ăn không tồn tại', 'error')
        return redirect(url_for('cart.my_orders'))

    # Ngăn người dùng tự sửa dish_id thành món không thuộc đơn.
    if not dao.order_has_dish(order, dish_id):
        flash('Món này không có trong đơn của bạn', 'error')
        return redirect(url_for('cart.my_orders'))

    if not rating or not (1 <= rating <= 5):
        flash('Đánh giá phải từ 1 đến 5 sao', 'error')
        return redirect(url_for('cart.my_orders'))

    sentiment_result = None

    if comment and sentiment_service.is_configured():
        try:
            # sentiment.py gọi gemini.py,
            # sau đó chuẩn hóa label và score.
            sentiment_result = (
                sentiment_service.analyze_sentiment(comment)
            )

        except Exception as e:
            flash(
                f'Không phân tích được cảm xúc: {e}',
                'warning'
            )

    try:
        dao.add_review(
            current_user.id,
            order,
            dish_id,
            rating,
            comment,
            sentiment_result
        )

        flash('Cảm ơn bạn đã đánh giá món ăn!')

    except ValueError as e:
        # Đánh giá trùng món/đơn thì báo lại.
        flash(str(e), 'error')

    return redirect(url_for('cart.my_orders'))
>>>>>>> Stashed changes
