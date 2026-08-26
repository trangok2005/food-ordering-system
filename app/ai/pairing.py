"""Dự đoán món ăn đi kèm - association rules (Apriori mức 2 item).

Chạy trên các đơn đã hoàn thành của từng nhà hàng:
- Mỗi đơn là 1 "transaction" gồm tập dish_id.
- Với mỗi cặp món (A, B) xuất hiện cùng nhau:
    support    = P(A và B)          = count(A,B) / tổng số đơn
    confidence = P(B | A)           = count(A,B) / count(A)
- Lưu cả hai chiều (A->B, B->A) vào bảng DishPairing để truy vấn nhanh.
Ngưỡng lọc: support >= MIN_SUPPORT, confidence >= MIN_CONFIDENCE.
"""

from itertools import combinations
from collections import defaultdict

from app import db
from app.models import DishPairing, Dish, Order, OrderDetail, OrderStatus


MIN_SUPPORT = 0.1        # cặp món phải xuất hiện trong >= 10% số đơn
MIN_CONFIDENCE = 0.2     # đặt A thì >= 20% khả năng đặt kèm B


def _completed_transactions(restaurant_id):
    """Danh sách transaction (set dish_id) từ các đơn hoàn thành của nhà hàng."""
    orders = (Order.query
              .filter(Order.restaurant_id == restaurant_id,
                      Order.status.in_([OrderStatus.COMPLETED,
                                        OrderStatus.DELIVERING]))
              .all())
    transactions = []
    for order in orders:
        dish_ids = {item.dish_id for item in order.order_details}
        if len(dish_ids) >= 2:
            transactions.append(dish_ids)
    return transactions


def recompute_restaurant_pairings(restaurant_id):
    """Tính lại toàn bộ luật kết hợp của một nhà hàng.
    Xóa luật cũ của nhà hàng rồi ghi luật mới. Trả về số luật tìm được."""
    transactions = _completed_transactions(restaurant_id)

    old_rules = (DishPairing.query
                 .join(Dish, DishPairing.dish_id == Dish.id)
                 .filter(Dish.restaurant_id == restaurant_id)
                 .all())
    for rule in old_rules:
        db.session.delete(rule)

    if not transactions:
        db.session.commit()
        return 0

    total_orders = len(transactions)

    pair_count = defaultdict(int)
    dish_order_count = defaultdict(int)
    for items in transactions:
        for dish_id in items:
            dish_order_count[dish_id] += 1
        for a, b in combinations(sorted(items), 2):
            pair_count[(a, b)] += 1

    rules = []
    for (a, b), count in pair_count.items():
        support = count / total_orders
        confidence_ab = count / dish_order_count[a]
        confidence_ba = count / dish_order_count[b]

        if support < MIN_SUPPORT:
            continue

        if confidence_ab >= MIN_CONFIDENCE:
            rules.append(DishPairing(dish_id=a, paired_dish_id=b,
                                     support=round(support, 4),
                                     confidence=round(confidence_ab, 4)))
        if confidence_ba >= MIN_CONFIDENCE and confidence_ba != confidence_ab:
            rules.append(DishPairing(dish_id=b, paired_dish_id=a,
                                     support=round(support, 4),
                                     confidence=round(confidence_ba, 4)))

    db.session.add_all(rules)
    db.session.commit()
    return len(rules)


def get_pairings_for_dishes(dish_ids, limit_each=3):
    """Với danh sách dish_id đang có trong giỏ, trả về các món đi kèm
    được gợi ý nhiều nhất (chỉ món còn bán). Kết quả: list[Dish]."""
    dish_ids = [d for d in dish_ids if d]
    if not dish_ids:
        return []

    rows = (DishPairing.query
            .filter(DishPairing.dish_id.in_(dish_ids))
            .order_by(DishPairing.confidence.desc(), DishPairing.support.desc())
            .limit(limit_each * len(dish_ids))
            .all())

    suggestions = {}
    for row in rows:
        if row.paired_dish_id in dish_ids:
            continue
        dish = row.paired_dish
        if not dish or not dish.active or not dish.is_available:
            continue
        current = suggestions.get(dish.id)
        if not current or row.confidence > current[0]:
            suggestions[dish.id] = (row.confidence, dish)

    ranked = sorted(suggestions.values(), key=lambda p: p[0], reverse=True)
    return [dish for _conf, dish in ranked[:limit_each]]


def get_pairing_suggestions_for_user(user_id, limit_each=3):
    """Gợi ý "món ăn thường dùng kèm" dựa trên món hiện có trong giỏ hàng."""
    from app.cart.dao import get_user_carts

    cart_dish_ids = []
    for cart in get_user_carts(user_id):
        cart_dish_ids.extend(item.dish_id for item in cart.items)

    if not cart_dish_ids:
        return []

    try:
        return get_pairings_for_dishes(cart_dish_ids, limit_each=limit_each)
    except Exception:
        # Tính năng gợi ý không được làm crash luồng chính
        return []
