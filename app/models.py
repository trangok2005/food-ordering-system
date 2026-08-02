from flask import Flask
from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy import Text, Boolean, DateTime, Enum
from sqlalchemy.orm import relationship
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import enum
from app import db, create_app


class BaseModel(db.Model):
    __abstract__ = True
    id = Column(Integer, primary_key=True, autoincrement=True)
    active = Column(Boolean, default=True)



# ĐĂNG KÝ / ĐĂNG NHẬP / QUẢN LÝ TÀI KHOẢN
#    - 2 phương thức đăng nhập: nội bộ (username/password) và OAuth
#      (Google/Facebook...) qua bảng OAuthAccount.
#    - Bảo mật: mật khẩu được hash (werkzeug), giới hạn số lần đăng
#      nhập sai bằng failed_login_count + locked_until.


class UserRole(enum.Enum):
    CUSTOMER = 'Customer'
    RESTAURANT = 'Restaurant'
    ADMIN = 'Admin'

class AuthProvider(enum.Enum):
    LOCAL = 'local'
    GOOGLE = 'google'

class User(BaseModel, UserMixin):
    __tablename__ = 'user'

    username = Column(String(255), unique=True, nullable=False)
    password = Column(String(255), nullable=True)
    email = Column(String(255), unique=True, nullable=False)
    full_name = Column(String(100))
    phone = Column(String(11))
    address = Column(String(255))
    avatar = Column(String(255))
    role = Column(Enum(UserRole), default=UserRole.CUSTOMER, nullable=False)

    # moot ti security
    failed_login_count = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)

    oauth_accounts = relationship('OAuthAccount', backref='user', lazy=True, cascade='all, delete-orphan')
    restaurant = relationship('Restaurant', backref='owner', uselist=False, lazy=True)
    carts = relationship('Cart', backref='user', lazy=True, cascade='all, delete-orphan')
    orders = relationship('Order', backref='user', lazy=True)
    reviews = relationship('Review', backref='user', lazy=True)
    interactions = relationship('UserDishInteraction', backref='user', lazy=True)

    def set_password(self, raw_password):
        self.password = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return self.password and check_password_hash(self.password, raw_password)

    def is_locked(self):
        return self.locked_until is not None and self.locked_until > datetime.now()

    def register_failed_login(self, max_attempts=5, lock_minutes=15):
        self.failed_login_count = (self.failed_login_count or 0) + 1
        if self.failed_login_count >= max_attempts:
            self.locked_until = datetime.now() + timedelta(minutes=lock_minutes)

    def reset_failed_login(self):
        self.failed_login_count = 0
        self.locked_until = None

    def __str__(self):
        return self.username


class OAuthAccount(BaseModel):
    __tablename__ = 'oauth_account'

    provider = Column(Enum(AuthProvider), nullable=False)
    provider_uid = Column(String(255), nullable=False)   # id từ gg

    user_id = Column(Integer, ForeignKey(User.id), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('provider', 'provider_uid', name='uq_provider_uid'),
    )



# 2. NHÀ HÀNG / THỰC ĐƠN
#    - Nhà hàng tự đăng ký (status PENDING -> admin duyệt APPROVED).
#    - Dish.is_available: nhà hàng tự bật/tắt món khi hết hàng.
#    - confirm_timeout_minutes: mặc định 5 phút, cho phép mỗi nhà
#      hàng tùy chỉnh.


class RestaurantStatus(enum.Enum):
    PENDING = 'Pending'
    APPROVED = 'Approved'
    LOCKED = 'Locked'


class Restaurant(BaseModel):
    __tablename__ = 'restaurant'

    name = Column(String(255), nullable=False)
    description = Column(Text)
    address = Column(String(255), nullable=False)
    phone = Column(String(11))
    logo = Column(String(255))

    is_open = Column(Boolean, default=True)
    status = Column(Enum(RestaurantStatus), default=RestaurantStatus.PENDING)

    confirm_timeout_minutes = Column(Integer, default=5)
    min_order_amount = Column(Float, nullable=True)    #ghi dè

    owner_id = Column(Integer, ForeignKey(User.id), nullable=False)

    categories = relationship('Category', backref='restaurant', lazy=True, cascade='all, delete-orphan')
    dishes = relationship('Dish', backref='restaurant', lazy=True, cascade='all, delete-orphan')
    orders = relationship('Order', backref='restaurant', lazy=True)

    def __str__(self):
        return self.name


class Category(BaseModel):
    __tablename__ = 'category'

    name = Column(String(100), nullable=False)
    restaurant_id = Column(Integer, ForeignKey(Restaurant.id), nullable=False)

    dishes = relationship('Dish', backref='category', lazy=True)

    __table_args__ = (
        db.UniqueConstraint('name', 'restaurant_id', name='uq_category_per_restaurant'),
    )

    def __str__(self):
        return self.name


class Dish(BaseModel):
    __tablename__ = 'dish'

    name = Column(String(255), nullable=False)
    description = Column(Text)
    price = Column(Float, default=0, nullable=False)
    image = Column(String(255))
    is_available = Column(Boolean, default=True)     # ẩn món khi hết hàng, KHÔNG xóa khỏi giỏ hàng cũ

    restaurant_id = Column(Integer, ForeignKey(Restaurant.id), nullable=False)
    category_id = Column(Integer, ForeignKey(Category.id), nullable=False)

    cart_items = relationship('CartItem', backref='dish', lazy=True)
    order_details = relationship('OrderDetail', backref='dish', lazy=True)
    reviews = relationship('Review', backref='dish', lazy=True)
    interactions = relationship('UserDishInteraction', backref='dish', lazy=True)

    def __str__(self):
        return self.name



# 3. GIỎ HÀNG
#    - Gắn với tài khoản đã đăng nhập (user_id NOT NULL).
#    - Mỗi cart chỉ thuộc 1 nhà hàng (UNIQUE user_id + restaurant_id):
#      khi user thêm món từ nhà hàng khác, tầng service sẽ hỏi xác
#      nhận trước khi tạo cart mới / xóa cart cũ.
#    - Món hết hàng vẫn hiển thị trong giỏ, chỉ được kiểm tra và
#      chặn ở bước thanh toán.


class Cart(BaseModel):
    __tablename__ = 'cart'

    user_id = Column(Integer, ForeignKey(User.id), nullable=False)
    restaurant_id = Column(Integer, ForeignKey(Restaurant.id), nullable=False)

    restaurant = relationship('Restaurant')
    items = relationship('CartItem', backref='cart', lazy=True, cascade='all, delete-orphan')

    __table_args__ = (
        db.UniqueConstraint('user_id', 'restaurant_id', name='uq_cart_user_restaurant'),
    )

    def total_amount(self):
        return sum(item.dish.price * item.quantity for item in self.items)

    def __str__(self):
        return f"Cart#{self.id} - user {self.user_id}"


class CartItem(BaseModel):
    __tablename__ = 'cart_item'

    cart_id = Column(Integer, ForeignKey(Cart.id), nullable=False)
    dish_id = Column(Integer, ForeignKey(Dish.id), nullable=False)
    quantity = Column(Integer, default=1, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('cart_id', 'dish_id', name='uq_cart_dish'),
    )



# 4 & 5. ĐẶT HÀNG / THANH TOÁN / XÁC NHẬN ĐƠN (phía nhà hàng)
#    - confirm_deadline = created_date + restaurant.confirm_timeout_minutes.
#    - Nếu quá hạn chưa confirm -> job nền chuyển status = EXPIRED.
#    - unit_price lưu snapshot giá tại thời điểm đặt (đề phòng nhà
#      hàng đổi giá món về sau).


class OrderStatus(enum.Enum):
    PENDING = 'Pending'            # vừa đặt, chờ nhà hàng xác nhận
    CONFIRMED = 'Confirmed'        # nhà hàng đã xác nhận -> chuẩn bị
    PREPARING = 'Preparing'
    DELIVERING = 'Delivering'
    COMPLETED = 'Completed'
    CANCELLED = 'Cancelled'        # khách hoặc nhà hàng hủy
    EXPIRED = 'Expired'            # nhà hàng không xác nhận kịp hạn -> tự động hủy

class PaymentMethod(enum.Enum):
    COD = 'Cash on Delivery'
    ONLINE = 'Online Payment'

class PaymentStatus(enum.Enum):
    UNPAID = 'Unpaid'
    PAID = 'Paid'
    FAILED = 'Failed'
    REFUNDED = 'Refunded'


class Order(BaseModel):
    __tablename__ = 'order'

    created_date = Column(DateTime, default=datetime.now)
    delivery_address = Column(String(255), nullable=False)
    phone = Column(String(11), nullable=False)
    note = Column(String(255))

    total_amount = Column(Float, default=0)
    status = Column(Enum(OrderStatus), default=OrderStatus.PENDING, nullable=False)

    payment_method = Column(Enum(PaymentMethod), default=PaymentMethod.COD, nullable=False)
    payment_status = Column(Enum(PaymentStatus), default=PaymentStatus.UNPAID, nullable=False)
    paid_at = Column(DateTime, nullable=True)

    confirm_deadline = Column(DateTime, nullable=True)
    confirmed_at = Column(DateTime, nullable=True)

    user_id = Column(Integer, ForeignKey(User.id), nullable=False)
    restaurant_id = Column(Integer, ForeignKey(Restaurant.id), nullable=False)

    order_details = relationship('OrderDetail', backref='order', lazy=True, cascade='all, delete-orphan')

    def set_confirm_deadline(self):
        timeout = self.restaurant.confirm_timeout_minutes if self.restaurant else 5
        self.confirm_deadline = self.created_date + timedelta(minutes=timeout)

    def is_expired(self):
        return (self.status == OrderStatus.PENDING
                and self.confirm_deadline is not None
                and datetime.now() > self.confirm_deadline)

    def __str__(self):
        return f"Order #{self.id}"


class OrderDetail(BaseModel):
    __tablename__ = 'order_detail'

    order_id = Column(Integer, ForeignKey(Order.id), nullable=False)
    dish_id = Column(Integer, ForeignKey(Dish.id), nullable=False)
    quantity = Column(Integer, default=1, nullable=False)
    unit_price = Column(Float, nullable=False)     # snapshot giá dish.price tại thời điểm đặt


# 6. TÍNH NĂNG THÔNG MINH (AI)
#    - Review: lưu đánh giá + kết quả phân tích cảm xúc (Gemini API).
#    - DishPairing: kết quả luật kết hợp (association rules) chạy
#      offline -> gợi ý "món ăn thường dùng kèm".
#    - UserDishInteraction: log hành vi (xem/thêm giỏ/đặt) kèm giờ
#      trong ngày -> input cho mô hình gợi ý món ăn cá nhân hóa
#      (dựa lịch sử, thời gian, vị trí lấy từ User.address, khẩu vị
#      suy ra từ Category các món đã tương tác).

class SentimentLabel(enum.Enum):
    POSITIVE = 'Positive'
    NEUTRAL = 'Neutral'
    NEGATIVE = 'Negative'


class Review(BaseModel):
    __tablename__ = 'review'

    rating = Column(Integer, nullable=False)     # 1-5 sao
    comment = Column(Text)
    created_date = Column(DateTime, default=datetime.now)

    sentiment_label = Column(Enum(SentimentLabel), nullable=True)   # kết quả Gemini API
    sentiment_score = Column(Float, nullable=True)                  # -1..1

    user_id = Column(Integer, ForeignKey(User.id), nullable=False)
    dish_id = Column(Integer, ForeignKey(Dish.id), nullable=True)
    order_id = Column(Integer, ForeignKey(Order.id), nullable=True)


class DishPairing(BaseModel):
    __tablename__ = 'dish_pairing'

    dish_id = Column(Integer, ForeignKey(Dish.id), nullable=False)
    paired_dish_id = Column(Integer, ForeignKey(Dish.id), nullable=False)
    support = Column(Float, default=0)
    confidence = Column(Float, default=0)

    dish = relationship('Dish', foreign_keys=[dish_id])
    paired_dish = relationship('Dish', foreign_keys=[paired_dish_id])

    __table_args__ = (
        db.UniqueConstraint('dish_id', 'paired_dish_id', name='uq_dish_pair'),
    )


class UserDishInteraction(BaseModel):
    __tablename__ = 'user_dish_interaction'

    user_id = Column(Integer, ForeignKey(User.id), nullable=False)
    dish_id = Column(Integer, ForeignKey(Dish.id), nullable=False)
    interaction_type = Column(String(20), default='VIEW')   # VIEW / ADD_TO_CART / ORDER
    hour_of_day = Column(Integer)          # 0-23
    created_date = Column(DateTime, default=datetime.now)



# CẤU HÌNH HỆ THỐNG
#    - Ràng buộc nghiệp vụ mặc định (số lượng món tối đa, giá trị
#    đơn hàng tối thiểu...) do hệ thống thiết lập, nhà hàng có thể
#    ghi đè riêng (xem Restaurant.min_order_amount).

class SystemConfig(db.Model):
    __tablename__ = 'system_config'

    key = Column(String(100), primary_key=True)
    value = Column(String(255), nullable=False)
    description = Column(String(255))

    @staticmethod
    def get(key, default=None, cast=str):
        cfg = SystemConfig.query.get(key)
        if not cfg:
            return default
        return cast(cfg.value)


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()

        # ---------- Cấu hình hệ thống mặc định ----------
        configs = [
            SystemConfig(key='DEFAULT_CONFIRM_TIMEOUT_MINUTES', value='5',
                         description='Thời gian mặc định để nhà hàng xác nhận đơn'),
            SystemConfig(key='DEFAULT_MIN_ORDER_AMOUNT', value='20000',
                         description='Giá trị đơn hàng tối thiểu mặc định'),
            SystemConfig(key='MAX_QUANTITY_PER_ITEM', value='20',
                         description='Số lượng tối đa cho 1 món trong giỏ hàng'),
            SystemConfig(key='SEARCH_PAGE_SIZE', value='24',
                         description='Số kết quả tìm kiếm mỗi trang (20-30)'),
        ]
        db.session.add_all(configs)
        db.session.commit()

        # ---------- Tài khoản ----------
        admin = User(username='admin', email='admin@foodapp.vn',
                     full_name='Quản trị viên', phone='0901234567',
                     address='Quận 1, TP.HCM', role=UserRole.ADMIN)
        admin.set_password('123456')

        owner1 = User(username='sushihouse_owner', email='owner1@foodapp.vn',
                      full_name='Nguyễn Văn Chủ', phone='0909111222',
                      address='Quận 3, TP.HCM', role=UserRole.RESTAURANT)
        owner1.set_password('123456')

        owner2 = User(username='comtam_owner', email='owner2@foodapp.vn',
                      full_name='Trần Thị Chủ', phone='0909333444',
                      address='Quận 5, TP.HCM', role=UserRole.RESTAURANT)
        owner2.set_password('123456')

        cus1 = User(username='nguyenvana', email='vana@gmail.com',
                    full_name='Nguyễn Văn A', phone='0988888888',
                    address='Tân Bình, TP.HCM', role=UserRole.CUSTOMER)
        cus1.set_password('123456')

        cus2 = User(username='lethib', email='thib@gmail.com',
                    full_name='Lê Thị B', phone='0977777777',
                    address='Thủ Đức, TP.HCM', role=UserRole.CUSTOMER)
        cus2.set_password('123456')

        db.session.add_all([admin, owner1, owner2, cus1, cus2])
        db.session.commit()

        # đăng nhập ngoài (OAuth) minh họa cho cus1
        db.session.add(OAuthAccount(provider=AuthProvider.GOOGLE,
                                     provider_uid='109283746510293',
                                     user_id=cus1.id))
        db.session.commit()

        # ---------- Nhà hàng ----------
        r1 = Restaurant(name='Sushi House', description='Sushi & Sashimi tươi mỗi ngày',
                        address='12 Nguyễn Huệ, Q1', phone='0281111111',
                        status=RestaurantStatus.APPROVED, confirm_timeout_minutes=5,
                        owner_id=owner1.id)
        r2 = Restaurant(name='Cơm Tấm Sài Gòn', description='Cơm tấm sườn bì chả truyền thống',
                        address='45 Lê Lợi, Q1', phone='0282222222',
                        status=RestaurantStatus.APPROVED, confirm_timeout_minutes=10,
                        owner_id=owner2.id)
        db.session.add_all([r1, r2])
        db.session.commit()

        # ---------- Danh mục & Món ăn ----------
        c1 = Category(name='Sashimi', restaurant_id=r1.id)
        c2 = Category(name='Nigiri', restaurant_id=r1.id)
        c3 = Category(name='Nước uống', restaurant_id=r1.id)
        c4 = Category(name='Cơm', restaurant_id=r2.id)
        c5 = Category(name='Nước uống', restaurant_id=r2.id)
        db.session.add_all([c1, c2, c3, c4, c5])
        db.session.commit()

        dishes = [
            Dish(name='Cá hồi Sashimi', description='Cá hồi tươi thái lát kèm wasabi',
                 price=120000.0, image='https://picsum.photos/seed/sashimi1/400',
                 is_available=True, restaurant_id=r1.id, category_id=c1.id),
            Dish(name='Nigiri Cá Hồi', description='Sushi cá hồi trên nền cơm dấm Nhật',
                 price=39000.0, image='https://picsum.photos/seed/nigiri1/400',
                 is_available=True, restaurant_id=r1.id, category_id=c2.id),
            Dish(name='Nigiri Tôm', description='Sushi tôm luộc tươi ngọt',
                 price=49000.0, image='https://picsum.photos/seed/nigiri2/400',
                 is_available=False, restaurant_id=r1.id, category_id=c2.id),   # đã hết hàng -> ẩn
            Dish(name='Coca Cola', description='Lon 330ml',
                 price=16000.0, image='https://picsum.photos/seed/coca/400',
                 is_available=True, restaurant_id=r1.id, category_id=c3.id),
            Dish(name='Cơm Tấm Sườn Bì Chả', description='Sườn nướng, bì, chả trứng',
                 price=45000.0, image='https://picsum.photos/seed/comtam1/400',
                 is_available=True, restaurant_id=r2.id, category_id=c4.id),
            Dish(name='Cơm Tấm Sườn Nướng', description='Sườn nướng mật ong',
                 price=40000.0, image='https://picsum.photos/seed/comtam2/400',
                 is_available=True, restaurant_id=r2.id, category_id=c4.id),
            Dish(name='Trà đá', description='Trà đá miễn phí kèm ly to',
                 price=5000.0, image='https://picsum.photos/seed/trada/400',
                 is_available=True, restaurant_id=r2.id, category_id=c5.id),
        ]
        db.session.add_all(dishes)
        db.session.commit()
        salmon_sashimi, nigiri_salmon, nigiri_shrimp, coca, comtam1, comtam2, trada = dishes

        # ---------- Giỏ hàng (cus2 đang có giỏ tại Cơm Tấm Sài Gòn) ----------
        cart2 = Cart(user_id=cus2.id, restaurant_id=r2.id)
        db.session.add(cart2)
        db.session.commit()
        db.session.add_all([
            CartItem(cart_id=cart2.id, dish_id=comtam1.id, quantity=2),
            CartItem(cart_id=cart2.id, dish_id=trada.id, quantity=2),
        ])
        db.session.commit()

        # ---------- Đơn hàng mẫu ----------
        order1 = Order(delivery_address='12 Nguyễn Huệ, Q1', phone='0988888888',
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

        # đơn thứ 2 đang chờ nhà hàng xác nhận (minh họa yêu cầu 5)
        order2 = Order(delivery_address='Thủ Đức, TP.HCM', phone='0977777777',
                       total_amount=comtam2.price, status=OrderStatus.PENDING,
                       payment_method=PaymentMethod.COD, payment_status=PaymentStatus.UNPAID,
                       user_id=cus2.id, restaurant_id=r2.id)
        db.session.add(order2)
        db.session.commit()
        order2.set_confirm_deadline()
        db.session.commit()
        db.session.add(OrderDetail(order_id=order2.id, dish_id=comtam2.id, quantity=1,
                                    unit_price=comtam2.price))
        db.session.commit()

        # ---------- Đánh giá + phân tích cảm xúc (AI) ----------
        db.session.add(Review(rating=5, comment='Cá hồi rất tươi, sẽ ủng hộ tiếp!',
                              sentiment_label=SentimentLabel.POSITIVE, sentiment_score=0.92,
                              user_id=cus1.id, dish_id=salmon_sashimi.id, order_id=order1.id))
        db.session.commit()

        # ---------- Luật kết hợp món ăn kèm (AI) ----------
        db.session.add(DishPairing(dish_id=salmon_sashimi.id, paired_dish_id=nigiri_salmon.id,
                                   support=0.35, confidence=0.7))
        db.session.commit()

        # ---------- Log hành vi phục vụ gợi ý cá nhân hóa (AI) ----------
        db.session.add_all([
            UserDishInteraction(user_id=cus1.id, dish_id=salmon_sashimi.id,
                                interaction_type='ORDER', hour_of_day=19),
            UserDishInteraction(user_id=cus1.id, dish_id=nigiri_salmon.id,
                                interaction_type='ORDER', hour_of_day=19),
            UserDishInteraction(user_id=cus2.id, dish_id=comtam1.id,
                                interaction_type='ADD_TO_CART', hour_of_day=11),
        ])
        db.session.commit()

        print('Khởi tạo CSDL và dữ liệu mẫu thành công!')