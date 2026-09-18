#!/usr/bin/env python
"""Dữ liệu demo cho môi trường development/test."""

import argparse
import os
from datetime import datetime, timedelta

from app import create_app
from app.extensions import db
from app.models import (
    User,
    UserRole,
    Restaurant,
    RestaurantStatus,
    Category,
    Dish,
    Order,
    OrderStatus,
    OrderDetail,
    PaymentMethod,
    PaymentStatus,
    Review,
    SentimentLabel,
    DishPairing,
    UserDishInteraction,
    SystemConfig,
)


def _seed_admin_from_env():
    values = {
        "username": os.getenv("ADMIN_USERNAME", "").strip(),
        "email": os.getenv("ADMIN_EMAIL", "").strip(),
        "password": os.getenv("ADMIN_PASSWORD", ""),
        "full_name": os.getenv("ADMIN_FULL_NAME", "Administrator").strip(),
    }

    missing = [
        f"ADMIN_{name.upper()}"
        for name in ("username", "email", "password")
        if not values[name]
    ]
    if missing:
        raise RuntimeError(
            f"Missing required admin settings: {', '.join(missing)}"
        )

    if (
        len(values["password"]) < 12
        or values["password"].lower().startswith("replace_with")
    ):
        raise RuntimeError(
            "ADMIN_PASSWORD must be non-placeholder and contain at least 12 characters."
        )

    existing = User.query.filter(
        (User.username == values["username"])
        | (User.email == values["email"])
    ).first()

    if existing:
        print("Tài khoản admin đã tồn tại; không thay đổi.")
        return

    admin = User(
        username=values["username"],
        email=values["email"],
        full_name=values["full_name"],
        role=UserRole.ADMIN,
    )
    admin.set_password(values["password"])

    db.session.add(admin)
    db.session.commit()
    print("Tạo tài khoản admin thành công.")


def _new_user(username, email, full_name, role, phone):
    user = User(
        username=username,
        email=email,
        full_name=full_name,
        phone=phone,
        address="TP.HCM",
        role=role,
    )
    user.set_password("123456")
    return user


def _create_order(
    *,
    user,
    restaurant,
    items,
    status,
    created_at,
    address="25 Lê Thánh Tôn, Quận 1, TP.HCM",
    note=None,
):
    total = sum(dish.price * quantity for dish, quantity in items)

    order = Order(
        created_date=created_at,
        delivery_address=address,
        phone=user.phone or "0900000000",
        note=note,
        total_amount=total,
        status=status,
        payment_method=PaymentMethod.ONLINE,
        payment_status=PaymentStatus.PAID,
        paid_at=created_at,
        user_id=user.id,
        restaurant_id=restaurant.id,
    )
    db.session.add(order)
    db.session.flush()

    order.set_confirm_deadline()

    if status != OrderStatus.PENDING:
        order.confirmed_at = created_at + timedelta(minutes=1)

    for dish, quantity in items:
        db.session.add(
            OrderDetail(
                order_id=order.id,
                dish_id=dish.id,
                quantity=quantity,
                unit_price=dish.price,
            )
        )

    return order


def _add_interaction(user, dish, interaction_type, hour, days_ago=0):
    db.session.add(
        UserDishInteraction(
            user_id=user.id,
            dish_id=dish.id,
            interaction_type=interaction_type,
            hour_of_day=hour,
            created_date=datetime.now() - timedelta(days=days_ago),
        )
    )


def seed_database(reset=False, application=None, demo=None):
    app = application or create_app()

    with app.app_context():
        demo = app.config.get("TESTING", False) if demo is None else demo

        if app.config.get("PRODUCTION"):
            if reset or demo:
                raise RuntimeError("Production does not allow --reset or demo data.")
            _seed_admin_from_env()
            return

        if reset and not demo:
            raise RuntimeError("--reset is only allowed together with --demo.")

        if reset:
            for table in reversed(db.metadata.sorted_tables):
                db.session.execute(table.delete())
            db.session.commit()

        if not demo:
            _seed_admin_from_env()
            return

        if User.query.first():
            print(
                "CSDL đã có dữ liệu; không thay đổi. "
                "Dùng --reset --demo để tạo lại dữ liệu demo."
            )
            return

        db.session.add_all(
            [
                SystemConfig(
                    key="DEFAULT_CONFIRM_TIMEOUT_MINUTES",
                    value="5",
                    description="Thời gian mặc định để nhà hàng xác nhận đơn",
                ),
                SystemConfig(
                    key="DEFAULT_MIN_ORDER_AMOUNT",
                    value="30000",
                    description="Giá trị đơn hàng tối thiểu mặc định",
                ),
                SystemConfig(
                    key="MAX_QUANTITY_PER_ITEM",
                    value="20",
                    description="Số lượng tối đa cho một món trong giỏ",
                ),
                SystemConfig(
                    key="SEARCH_PAGE_SIZE",
                    value="24",
                    description="Số kết quả tìm kiếm mỗi trang",
                ),
            ]
        )

        admin = _new_user(
            "admin", "admin@demo.local", "Quản trị viên",
            UserRole.ADMIN, "0900000001",
        )
        customer = _new_user(
            "nguyenvana", "nguyenvana@demo.local", "Nguyễn Văn A",
            UserRole.CUSTOMER, "0900000002",
        )
        sushi_owner = _new_user(
            "sushi", "sushi@demo.local", "Chủ Sushi House",
            UserRole.RESTAURANT, "0900000003",
        )
        comtam_owner = _new_user(
            "comtam", "comtam@demo.local", "Chủ Cơm Tấm Sài Gòn",
            UserRole.RESTAURANT, "0900000004",
        )

        demo_users = [
            _new_user(
                f"demo{i}",
                f"demo{i}@demo.local",
                f"Khách demo {i}",
                UserRole.CUSTOMER,
                f"090000001{i}",
            )
            for i in range(1, 6)
        ]

        db.session.add_all(
            [admin, customer, sushi_owner, comtam_owner, *demo_users]
        )
        db.session.flush()

        sushi_restaurant = Restaurant(
            name="Sushi House",
            description="Sushi và sashimi tươi mỗi ngày",
            address="12 Nguyễn Huệ, Quận 1, TP.HCM",
            phone="0281111111",
            status=RestaurantStatus.APPROVED,
            is_open=True,
            confirm_timeout_minutes=5,
            min_order_amount=30000,
            latitude=10.7769,
            longitude=106.7009,
            delivery_radius_km=10,
            owner_id=sushi_owner.id,
        )

        comtam_restaurant = Restaurant(
            name="Cơm Tấm Sài Gòn",
            description="Cơm tấm sườn nướng, bì, chả kiểu Sài Gòn",
            address="120 Võ Văn Tần, Quận 3, TP.HCM",
            phone="0282222222",
            status=RestaurantStatus.APPROVED,
            is_open=True,
            confirm_timeout_minutes=5,
            min_order_amount=30000,
            latitude=10.7756,
            longitude=106.6888,
            delivery_radius_km=10,
            owner_id=comtam_owner.id,
        )

        db.session.add_all([sushi_restaurant, comtam_restaurant])
        db.session.flush()

        sushi_sashimi = Category(
            name="Sashimi", restaurant_id=sushi_restaurant.id
        )
        sushi_nigiri = Category(
            name="Nigiri", restaurant_id=sushi_restaurant.id
        )
        sushi_other = Category(
            name="Món kèm & Nước", restaurant_id=sushi_restaurant.id
        )

        comtam_main = Category(
            name="Cơm tấm", restaurant_id=comtam_restaurant.id
        )
        comtam_extra = Category(
            name="Món thêm", restaurant_id=comtam_restaurant.id
        )
        comtam_drink = Category(
            name="Nước uống", restaurant_id=comtam_restaurant.id
        )

        db.session.add_all(
            [
                sushi_sashimi,
                sushi_nigiri,
                sushi_other,
                comtam_main,
                comtam_extra,
                comtam_drink,
            ]
        )
        db.session.flush()

        ca_hoi = Dish(
            name="Cá hồi Sashimi",
            description="Cá hồi tươi thái lát dùng kèm wasabi",
            price=79000,
            image="https://picsum.photos/seed/ca-hoi-sashimi/600/400",
            is_available=True,
            restaurant_id=sushi_restaurant.id,
            category_id=sushi_sashimi.id,
        )
        nigiri_ca_hoi = Dish(
            name="Nigiri Cá Hồi",
            description="Cơm sushi phủ cá hồi tươi",
            price=49000,
            image="https://picsum.photos/seed/nigiri-ca-hoi/600/400",
            is_available=True,
            restaurant_id=sushi_restaurant.id,
            category_id=sushi_nigiri.id,
        )
        nigiri_tom = Dish(
            name="Nigiri Tôm",
            description="Cơm sushi với tôm luộc",
            price=49000,
            image="https://picsum.photos/seed/nigiri-tom/600/400",
            is_available=True,
            restaurant_id=sushi_restaurant.id,
            category_id=sushi_nigiri.id,
        )
        mochi = Dish(
            name="Mochi Kem",
            description="Mochi kem mát lạnh dùng sau bữa ăn",
            price=30000,
            image="https://picsum.photos/seed/mochi-kem/600/400",
            is_available=True,
            restaurant_id=sushi_restaurant.id,
            category_id=sushi_other.id,
        )
        coca = Dish(
            name="Coca Cola",
            description="Lon 330ml",
            price=15000,
            image="https://picsum.photos/seed/coca-cola/600/400",
            is_available=True,
            restaurant_id=sushi_restaurant.id,
            category_id=sushi_other.id,
        )

        com_suon_bi_cha = Dish(
            name="Cơm Tấm Sườn Bì Chả",
            description="Sườn nướng, bì, chả trứng và đồ chua",
            price=59000,
            image="https://picsum.photos/seed/com-suon-bi-cha/600/400",
            is_available=True,
            restaurant_id=comtam_restaurant.id,
            category_id=comtam_main.id,
        )
        com_suon = Dish(
            name="Cơm Tấm Sườn Nướng",
            description="Sườn nướng mật ong ăn cùng cơm tấm",
            price=49000,
            image="https://picsum.photos/seed/com-suon-nuong/600/400",
            is_available=True,
            restaurant_id=comtam_restaurant.id,
            category_id=comtam_main.id,
        )
        com_ga = Dish(
            name="Cơm Tấm Gà Nướng",
            description="Gà nướng đậm vị ăn cùng cơm tấm",
            price=49000,
            image="https://picsum.photos/seed/com-ga-nuong/600/400",
            is_available=True,
            restaurant_id=comtam_restaurant.id,
            category_id=comtam_main.id,
        )
        trung = Dish(
            name="Trứng Ốp La",
            description="Trứng gà ốp la",
            price=12000,
            image="https://picsum.photos/seed/trung-op-la/600/400",
            is_available=True,
            restaurant_id=comtam_restaurant.id,
            category_id=comtam_extra.id,
        )
        tra_tac = Dish(
            name="Trà Tắc",
            description="Trà tắc mát lạnh",
            price=18000,
            image="https://picsum.photos/seed/tra-tac/600/400",
            is_available=True,
            restaurant_id=comtam_restaurant.id,
            category_id=comtam_drink.id,
        )

        db.session.add_all(
            [
                ca_hoi,
                nigiri_ca_hoi,
                nigiri_tom,
                mochi,
                coca,
                com_suon_bi_cha,
                com_suon,
                com_ga,
                trung,
                tra_tac,
            ]
        )
        db.session.flush()

        now = datetime.now()
        d1, d2, d3, d4, d5 = demo_users

        # đơn hoàn thành cho món phổ biến và pairing
        order_a = _create_order(
            user=customer,
            restaurant=sushi_restaurant,
            items=[(ca_hoi, 1), (nigiri_ca_hoi, 1)],
            status=OrderStatus.COMPLETED,
            created_at=now - timedelta(days=8),
        )

        order_b = _create_order(
            user=d1,
            restaurant=sushi_restaurant,
            items=[(ca_hoi, 1), (nigiri_ca_hoi, 1), (nigiri_tom, 1)],
            status=OrderStatus.COMPLETED,
            created_at=now - timedelta(days=7),
        )

        order_c = _create_order(
            user=d2,
            restaurant=sushi_restaurant,
            items=[(ca_hoi, 1), (nigiri_tom, 1), (coca, 1)],
            status=OrderStatus.COMPLETED,
            created_at=now - timedelta(days=6),
        )

        order_d = _create_order(
            user=d5,
            restaurant=sushi_restaurant,
            items=[(nigiri_ca_hoi, 1), (nigiri_tom, 1), (mochi, 1)],
            status=OrderStatus.COMPLETED,
            created_at=now - timedelta(days=5),
        )

        order_e = _create_order(
            user=customer,
            restaurant=comtam_restaurant,
            items=[(com_suon_bi_cha, 1), (trung, 1), (tra_tac, 1)],
            status=OrderStatus.COMPLETED,
            created_at=now - timedelta(days=4),
        )

        order_f = _create_order(
            user=d3,
            restaurant=comtam_restaurant,
            items=[(com_suon_bi_cha, 1), (com_suon, 1), (trung, 1), (tra_tac, 1)],
            status=OrderStatus.COMPLETED,
            created_at=now - timedelta(days=3),
        )

        order_g = _create_order(
            user=d4,
            restaurant=comtam_restaurant,
            items=[(com_suon, 1), (com_ga, 1), (trung, 1), (tra_tac, 1)],
            status=OrderStatus.COMPLETED,
            created_at=now - timedelta(days=2),
        )

        sushi_pending = _create_order(
            user=customer,
            restaurant=sushi_restaurant,
            items=[(nigiri_tom, 1), (coca, 1)],
            status=OrderStatus.PENDING,
            created_at=now,
            note="Ít wasabi",
        )

        comtam_preparing = _create_order(
            user=customer,
            restaurant=comtam_restaurant,
            items=[(com_suon, 1), (tra_tac, 1)],
            status=OrderStatus.PREPARING,
            created_at=now - timedelta(minutes=3),
        )

        db.session.add_all(
            [
                Review(
                    rating=5,
                    comment="Cá hồi rất tươi, món ăn ngon và trình bày đẹp.",
                    sentiment_label=SentimentLabel.POSITIVE,
                    sentiment_score=0.95,
                    user_id=customer.id,
                    dish_id=ca_hoi.id,
                    order_id=order_a.id,
                ),
                Review(
                    rating=4,
                    comment="Cơm tấm ngon, sườn nướng vừa vị.",
                    sentiment_label=SentimentLabel.POSITIVE,
                    sentiment_score=0.88,
                    user_id=customer.id,
                    dish_id=com_suon_bi_cha.id,
                    order_id=order_e.id,
                ),
            ]
        )

        # dữ liệu gợi ý món đi kèm
        db.session.add_all(
            [
                DishPairing(
                    dish_id=ca_hoi.id,
                    paired_dish_id=nigiri_ca_hoi.id,
                    support=0.50,
                    confidence=0.67,
                    lift=1.33,
                ),
                DishPairing(
                    dish_id=ca_hoi.id,
                    paired_dish_id=nigiri_tom.id,
                    support=0.50,
                    confidence=0.67,
                    lift=1.00,
                ),
                DishPairing(
                    dish_id=nigiri_tom.id,
                    paired_dish_id=coca.id,
                    support=0.25,
                    confidence=0.33,
                    lift=1.33,
                ),
                DishPairing(
                    dish_id=com_suon.id,
                    paired_dish_id=trung.id,
                    support=0.67,
                    confidence=1.00,
                    lift=1.00,
                ),
                DishPairing(
                    dish_id=com_suon.id,
                    paired_dish_id=tra_tac.id,
                    support=0.67,
                    confidence=1.00,
                    lift=1.00,
                ),
                DishPairing(
                    dish_id=com_suon_bi_cha.id,
                    paired_dish_id=trung.id,
                    support=0.67,
                    confidence=1.00,
                    lift=1.00,
                ),
            ]
        )

        # tương tác mẫu cho NMF
        _add_interaction(customer, ca_hoi, "ORDER", 19, 8)
        _add_interaction(customer, nigiri_ca_hoi, "ORDER", 19, 8)
        _add_interaction(customer, mochi, "ADD_TO_CART", 20, 5)

        # demo1 - nhóm sushi
        _add_interaction(d1, ca_hoi, "ORDER", 19, 7)
        _add_interaction(d1, nigiri_ca_hoi, "ORDER", 19, 7)
        _add_interaction(d1, nigiri_tom, "ORDER", 19, 7)
        _add_interaction(d1, coca, "ADD_TO_CART", 20, 7)

        # demo2 - nhóm sushi
        _add_interaction(d2, ca_hoi, "ORDER", 18, 6)
        _add_interaction(d2, nigiri_ca_hoi, "REVIEW", 18, 6)
        _add_interaction(d2, nigiri_tom, "ORDER", 18, 6)
        _add_interaction(d2, coca, "ORDER", 18, 6)

        # demo3 - nhóm cơm tấm
        _add_interaction(d3, com_suon_bi_cha, "ORDER", 12, 3)
        _add_interaction(d3, com_suon, "ORDER", 12, 3)
        _add_interaction(d3, trung, "ADD_TO_CART", 12, 3)
        _add_interaction(d3, tra_tac, "ORDER", 12, 3)

        # demo4 - nhóm cơm tấm
        _add_interaction(d4, com_suon, "ORDER", 12, 2)
        _add_interaction(d4, com_ga, "ORDER", 12, 2)
        _add_interaction(d4, trung, "ORDER", 12, 2)
        _add_interaction(d4, tra_tac, "ADD_TO_CART", 12, 2)

        # nối hai nhóm để mô hình có dữ liệu chung
        _add_interaction(d5, ca_hoi, "ADD_TO_CART", 20, 5)
        _add_interaction(d5, nigiri_tom, "ORDER", 20, 5)
        _add_interaction(d5, mochi, "ORDER", 20, 5)
        _add_interaction(d5, com_ga, "ADD_TO_CART", 12, 2)

        db.session.commit()

        print("\nĐã tạo dữ liệu demo recommendation thành công.")
        print("Tài khoản chính:")
        print("  Admin      : admin / 123456")
        print("  Khách hàng : nguyenvana / 123456")
        print("  Nhà hàng 1 : sushi / 123456")
        print("  Nhà hàng 2 : comtam / 123456")
        print("")
        print("Dữ liệu:")
        print("  2 nhà hàng")
        print("  10 món")
        print("  9 đơn mẫu")
        print("  5 customer nền cho NMF")
        print("  23 interaction")
        print("  6 luật món đi kèm")
        print("  2 review có sentiment")
        print("")
        print("Demo gợi ý cá nhân hóa:")
        print("  Đăng nhập nguyenvana -> mở trang Gợi ý món")
        print("  NMF có dữ liệu để học từ các user nền.")
        print("  Nigiri Tôm / Coca Cola là các ứng viên phù hợp chưa tương tác.")
        print("")
        print("Demo món đi kèm:")
        print("  Thêm Cá hồi Sashimi vào giỏ -> bấm Gợi ý món đi kèm.")
        print("  Có thể gợi ý Nigiri Cá Hồi hoặc Nigiri Tôm.")
        print("")
        print(f"Đơn chờ xác nhận Sushi: #{sushi_pending.id}")
        print(f"Đơn đang chuẩn bị Cơm Tấm: #{comtam_preparing.id}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Nạp dữ liệu demo")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Nạp bộ dữ liệu demo (chỉ development/test)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Xóa dữ liệu hiện có trước khi nạp demo",
    )

    args = parser.parse_args()
    seed_database(reset=args.reset, demo=args.demo)
