#!/usr/bin/env python
"""Database seeding script for food ordering system."""
from app import create_app
from app.models import (
    db, User, UserRole, Restaurant, RestaurantStatus, Category, Dish,
    Cart, CartItem, Order, OrderStatus, OrderDetail, PaymentMethod, PaymentStatus,
    Review, SentimentLabel, DishPairing, UserDishInteraction, SystemConfig,
    OAuthAccount, AuthProvider
)
from datetime import datetime, timedelta


def seed_database():
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()

        # ---------- Cau hinh he thong mac dinh ----------
        configs = [
            SystemConfig(key='DEFAULT_CONFIRM_TIMEOUT_MINUTES', value='5',
                         description='Thoi gian mac dinh de nha hang xac nhan don'),
            SystemConfig(key='DEFAULT_MIN_ORDER_AMOUNT', value='2000',
                         description='Gia tri don hang toi thieu mac dinh'),
            SystemConfig(key='MAX_QUANTITY_PER_ITEM', value='20',
                         description='So luong toi da cho 1 mon trong gio hang'),
            SystemConfig(key='SEARCH_PAGE_SIZE', value='24',
                         description='So ket qua tim kiem moi trang (20-30)'),
        ]
        db.session.add_all(configs)
        db.session.commit()

        # ---------- Tai khoan ----------
        admin = User(username='admin', email='admin@foodapp.vn',
                     full_name='Quan tri vien', phone='0901234567',
                     address='Quan 1, TP.HCM', role=UserRole.ADMIN)
        admin.set_password('123456')

        owner1 = User(username='sushihouse_owner', email='owner1@foodapp.vn',
                      full_name='Nguyen Van Chu', phone='0909111222',
                      address='Quan 3, TP.HCM', role=UserRole.RESTAURANT)
        owner1.set_password('123456')

        owner2 = User(username='comtam_owner', email='owner2@foodapp.vn',
                      full_name='Tran Thi Chu', phone='0909333444',
                      address='Quan 5, TP.HCM', role=UserRole.RESTAURANT)
        owner2.set_password('123456')

        cus1 = User(username='nguyenvana', email='vana@gmail.com',
                    full_name='Nguyen Van A', phone='0988888888',
                    address='Tan Binh, TP.HCM', role=UserRole.CUSTOMER)
        cus1.set_password('123456')

        cus2 = User(username='lethib', email='thib@gmail.com',
                    full_name='Le Thi B', phone='0977777777',
                    address='Thu Duc, TP.HCM', role=UserRole.CUSTOMER)
        cus2.set_password('123456')

        db.session.add_all([admin, owner1, owner2, cus1, cus2])
        db.session.commit()

        # Dang nhap ngoai (OAuth) minh hoa cho cus1
        db.session.add(OAuthAccount(provider=AuthProvider.GOOGLE,
                                     provider_uid='109283746510293',
                                     user_id=cus1.id))
        db.session.commit()

        # ---------- Nha hang ----------
        r1 = Restaurant(name='Sushi House', description='Sushi & Sashimi tuoi moi ngay',
                        address='12 Nguyen Hue, Q1', phone='0281111111',
                        status=RestaurantStatus.APPROVED, confirm_timeout_minutes=5,
                        latitude=10.7769, longitude=106.7009, delivery_radius_km=5,
                        owner_id=owner1.id)
        r2 = Restaurant(name='Com Tam Sai Gon', description='Com tam suong bi cha truyen thong',
                        address='45 Le Loi, Q1', phone='0282222222',
                        status=RestaurantStatus.APPROVED, confirm_timeout_minutes=10,
                        latitude=10.7765, longitude=106.6997, delivery_radius_km=8,
                        owner_id=owner2.id)
        db.session.add_all([r1, r2])
        db.session.commit()

        # ---------- Danh muc & Mon an ----------
        c1 = Category(name='Sashimi', restaurant_id=r1.id)
        c2 = Category(name='Nigiri', restaurant_id=r1.id)
        c3 = Category(name='Nuoc uong', restaurant_id=r1.id)
        c4 = Category(name='Com', restaurant_id=r2.id)
        c5 = Category(name='Nuoc uong', restaurant_id=r2.id)
        db.session.add_all([c1, c2, c3, c4, c5])
        db.session.commit()

        dishes = [
            Dish(name='Ca hoi Sashimi', description='Ca hoi tuoi thai lat kem wasabi',
                 price=1000, image='https://picsum.photos/seed/sashimi1/400',
                 is_available=True, restaurant_id=r1.id, category_id=c1.id),
            Dish(name='Nigiri Ca Hoi', description='Sushi ca hoi tren nen com dam Nhat',
                 price=3000, image='https://picsum.photos/seed/nigiri1/400',
                 is_available=True, restaurant_id=r1.id, category_id=c2.id),
            Dish(name='Nigiri Tom', description='Sushi tom luoc tuoi ngot',
                 price=49000, image='https://picsum.photos/seed/nigiri2/400',
                 is_available=False, restaurant_id=r1.id, category_id=c2.id),
            Dish(name='Coca Cola', description='Lon 330ml',
                 price=16000, image='https://picsum.photos/seed/coca/400',
                 is_available=True, restaurant_id=r1.id, category_id=c3.id),
            Dish(name='Com Tam Suong Bi Cha', description='Suong nuong, bi, cha trung',
                 price=45000, image='https://picsum.photos/seed/comtam1/400',
                 is_available=True, restaurant_id=r2.id, category_id=c4.id),
            Dish(name='Com Tam Suong Nuong', description='Suong nuong mat ong',
                 price=40000, image='https://picsum.photos/seed/comtam2/400',
                 is_available=True, restaurant_id=r2.id, category_id=c4.id),
            Dish(name='Tra da', description='Tra da mien phi kem ly to',
                 price=5000, image='https://picsum.photos/seed/trada/400',
                 is_available=True, restaurant_id=r2.id, category_id=c5.id),
        ]
        db.session.add_all(dishes)
        db.session.commit()
        salmon_sashimi, nigiri_salmon, nigiri_shrimp, coca, comtam1, comtam2, trada = dishes

        # ---------- Gio hang (cus2 dang co gio tai Com Tam Sai Gon) ----------
        cart2 = Cart(user_id=cus2.id, restaurant_id=r2.id)
        db.session.add(cart2)
        db.session.commit()
        db.session.add_all([
            CartItem(cart_id=cart2.id, dish_id=comtam1.id, quantity=2),
            CartItem(cart_id=cart2.id, dish_id=trada.id, quantity=2),
        ])
        db.session.commit()

        # ---------- Don hang mau ----------
        order1 = Order(delivery_address='12 Nguyen Hue, Q1', phone='0988888888',
                       total_amount=salmon_sashimi.price + nigiri_salmon.price,
                       status=OrderStatus.COMPLETED,
                       payment_method=PaymentMethod.ONLINE, payment_status=PaymentStatus.PAID,
                       paid_at=datetime.now() - timedelta(days=1),
                       user_id=cus1.id, restaurant_id=r1.id)
        db.session.add(order1)
        db.session.commit()
        order1.set_confirm_deadline()
        order1.confirmed_at = order1.created_date + timedelta(minutes=3)
        db.session.commit()

        db.session.add_all([
            OrderDetail(order_id=order1.id, dish_id=salmon_sashimi.id, quantity=1,
                       unit_price=salmon_sashimi.price),
            OrderDetail(order_id=order1.id, dish_id=nigiri_salmon.id, quantity=1,
                       unit_price=nigiri_salmon.price),
        ])
        db.session.commit()

        # Don thu 2 dang cho nha hang xac nhan
        order2 = Order(delivery_address='Thu Duc, TP.HCM', phone='0977777777',
                       total_amount=comtam2.price, status=OrderStatus.PENDING,
                       payment_method=PaymentMethod.ONLINE, payment_status=PaymentStatus.PAID,
                       paid_at=datetime.now(),
                       user_id=cus2.id, restaurant_id=r2.id)
        db.session.add(order2)
        db.session.commit()
        order2.set_confirm_deadline()
        db.session.commit()
        db.session.add(OrderDetail(order_id=order2.id, dish_id=comtam2.id, quantity=1,
                                    unit_price=comtam2.price))
        db.session.commit()

        # Don thu 3 da hoan thanh voi 2 mon - de luat ket hop (AI pairing)
        # co du lieu tinh ngay khi demo
        order3 = Order(delivery_address='Quan 5, TP.HCM', phone='0977777777',
                       total_amount=comtam1.price + trada.price,
                       status=OrderStatus.COMPLETED,
                       payment_method=PaymentMethod.ONLINE, payment_status=PaymentStatus.PAID,
                       paid_at=datetime.now() - timedelta(days=2),
                       confirmed_at=datetime.now() - timedelta(days=2),
                       user_id=cus2.id, restaurant_id=r2.id)
        db.session.add(order3)
        db.session.commit()
        order3.set_confirm_deadline()
        db.session.commit()
        db.session.add_all([
            OrderDetail(order_id=order3.id, dish_id=comtam1.id, quantity=2,
                        unit_price=comtam1.price),
            OrderDetail(order_id=order3.id, dish_id=trada.id, quantity=2,
                        unit_price=trada.price),
        ])
        db.session.commit()

        # ---------- Danh gia + phan tich cam xuc (AI) ----------
        db.session.add(Review(rating=5, comment='Ca hoi rat tuoi, se ung ho tiep!',
                              sentiment_label=SentimentLabel.POSITIVE, sentiment_score=0.92,
                              user_id=cus1.id, dish_id=salmon_sashimi.id, order_id=order1.id))
        db.session.commit()

        # ---------- Luat ket hop mon an kem (AI) ----------
        db.session.add(DishPairing(dish_id=salmon_sashimi.id, paired_dish_id=nigiri_salmon.id,
                                   support=0.35, confidence=0.7))
        db.session.commit()

        # ---------- Log hanh vi phuc vu goi y ca nhan hoa (AI) ----------
        db.session.add_all([
            UserDishInteraction(user_id=cus1.id, dish_id=salmon_sashimi.id,
                                interaction_type='ORDER', hour_of_day=19),
            UserDishInteraction(user_id=cus1.id, dish_id=nigiri_salmon.id,
                                interaction_type='ORDER', hour_of_day=19),
            UserDishInteraction(user_id=cus2.id, dish_id=comtam1.id,
                                interaction_type='ADD_TO_CART', hour_of_day=11),
        ])
        db.session.commit()

        print('Khoi tao CSDL va du lieu mau thanh cong!')


if __name__ == '__main__':
    seed_database()