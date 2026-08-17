from flask import Flask
from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy import Text, Boolean, DateTime, Enum
from sqlalchemy.orm import relationship
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import enum
from app import db
from app.utils import haversine_km


class BaseModel(db.Model):
    __abstract__ = True
    id = Column(Integer, primary_key=True, autoincrement=True)
    active = Column(Boolean, default=True)


# ĐĂNG KÝ / ĐĂNG NHẬP / QUẢN LÝ TÀI KHOẢN
#    - 2 phương thức đăng nhập: nội bộ (username/password) và OAuth
#      (Google) qua bảng OAuthAccount.
#    - Bảo mật: mật khẩu được hash (werkzeug), giới hạn số lần đăng
#      nhập sai bằng failed_login_count + locked_until.

class UserRole(enum.Enum):
    USER = 'User'
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

    # bảo mật đăng nhập
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
    provider_uid = Column(String(255), nullable=False)   # id từ Google

    user_id = Column(Integer, ForeignKey(User.id), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('provider', 'provider_uid', name='uq_provider_uid'),
        db.UniqueConstraint('user_id', 'provider', name='uq_user_provider'),
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
    address = Column(String(255), nullable=False)   # chỉ để HIỂN THỊ, không dùng để tính khoảng cách
    phone = Column(String(11))
    logo = Column(String(255))

    # tọa độ GPS thật, lấy 1 lần lúc đăng ký qua navigator.geolocation của
    # trình duyệt (nhà hàng bấm "Dùng vị trí hiện tại") - dùng để tính
    # khoảng cách đường chim bay (Haversine), KHÔNG geocode từ chuỗi địa
    # chỉ vì geocode địa chỉ tiếng Việt qua Nominatim không đáng tin cậy.
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    is_open = Column(Boolean, default=True)
    status = Column(Enum(RestaurantStatus), default=RestaurantStatus.PENDING)

    confirm_timeout_minutes = Column(Integer, default=5)
    min_order_amount = Column(Float, nullable=True)          # ghi đè giá trị mặc định của hệ thống
    delivery_radius_km = Column(Float, default=10)           # bán kính giao hàng, tùy chỉnh theo nhà hàng
    max_quantity_per_item = Column(Integer, nullable=True)   # ghi đè số lượng tối đa 1 món/đơn (mặc định hệ thống)

    owner_id = Column(Integer, ForeignKey(User.id), nullable=False)

    categories = relationship('Category', backref='restaurant', lazy=True, cascade='all, delete-orphan')
    dishes = relationship('Dish', backref='restaurant', lazy=True, cascade='all, delete-orphan')
    orders = relationship('Order', backref='restaurant', lazy=True)

    def is_within_delivery_radius(self, lat, lng):
        """Kiểm tra tọa độ (lat, lng) có nằm trong bán kính giao hàng của
        nhà hàng không. Trả về True nếu nhà hàng chưa có tọa độ (tránh
        chặn nhầm khi dữ liệu chưa đầy đủ)."""
        if self.latitude is None or self.longitude is None:
            return True
        distance = haversine_km(self.latitude, self.longitude, lat, lng)
        return distance <= (self.delivery_radius_km or 10)

    def distance_km_to(self, lat, lng):
        """Khoảng cách thực tế từ nhà hàng đến (lat, lng). Trả về None
        nếu nhà hàng chưa có tọa độ GPS."""
        if self.latitude is None or self.longitude is None or lat is None or lng is None:
            return None
        return haversine_km(self.latitude, self.longitude, lat, lng)

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
    price = Column(Integer, default=0, nullable=False)
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
#    - Mỗi cart chỉ thuộc 1 nhà hàng. Ràng buộc UNIQUE là cặp
#      (user_id, restaurant_id) chứ KHÔNG phải riêng user_id, vì một
#      user có thể có nhiều cart ở các thời điểm khác nhau (nhưng
#      không được có 2 cart cùng lúc cho cùng 1 nhà hàng).
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
#    - Chỉ hỗ trợ thanh toán trực tuyến (đã bỏ COD).

class OrderStatus(enum.Enum):
    PENDING = 'Pending'            # vừa đặt, chờ nhà hàng xác nhận
    CONFIRMED = 'Confirmed'        # nhà hàng đã xác nhận -> chuẩn bị
    PREPARING = 'Preparing'
    DELIVERING = 'Delivering'
    COMPLETED = 'Completed'
    CANCELLED = 'Cancelled'        # khách hoặc nhà hàng hủy
    EXPIRED = 'Expired'            # nhà hàng không xác nhận kịp hạn -> tự động hủy

class PaymentMethod(enum.Enum):
    ONLINE = 'Online Payment'

class PaymentStatus(enum.Enum):
    UNPAID = 'Unpaid'
    PAID = 'Paid'
    FAILED = 'Failed'
    REFUNDED = 'Refunded'


class Order(BaseModel):
    __tablename__ = 'order'

    created_date = Column(DateTime, default=datetime.now)
    delivery_address = Column(String(255), nullable=False)   # chỉ để HIỂN THỊ/in đơn
    delivery_latitude = Column(Float, nullable=True)         # tọa độ GPS thật lúc checkout
    delivery_longitude = Column(Float, nullable=True)        # dùng để tính khoảng cách, KHÔNG geocode
    phone = Column(String(11), nullable=False)
    note = Column(String(255))

    total_amount = Column(Float, default=0)
    status = Column(Enum(OrderStatus), default=OrderStatus.PENDING, nullable=False)

    payment_method = Column(Enum(PaymentMethod), default=PaymentMethod.ONLINE, nullable=False)
    payment_status = Column(Enum(PaymentStatus), default=PaymentStatus.UNPAID, nullable=False)
    paid_at = Column(DateTime, nullable=True)

    confirm_deadline = Column(DateTime, nullable=True)
    confirmed_at = Column(DateTime, nullable=True)

    # Hủy đơn: chỉ áp dụng cho trường hợp nhà hàng hủy đơn đã thanh toán
    # do lý do ngoài quy trình chuẩn (hết nguyên liệu, quá tải...).
    # Việc hoàn tiền do nhà hàng TỰ LIÊN HỆ và thực hiện trực tiếp với
    # khách hàng, NẰM NGOÀI phạm vi xử lý của hệ thống (quyết định đã
    # được giảng viên chốt - xem Project Charter, mục Giả định).
    # Order chỉ được tạo SAU KHI payOS xác nhận thanh toán PAID; nếu
    # khách hủy/không thanh toán thì không tạo đơn nên không cần xử lý
    # hủy gì ở đây.
    cancel_reason = Column(String(255), nullable=True)
    cancelled_at = Column(DateTime, nullable=True)

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

    def cancel_by_restaurant(self, reason):
        """Nhà hàng hủy đơn đã thanh toán do lý do ngoài quy trình chuẩn.
        Chỉ cập nhật trạng thái và lý do; KHÔNG gọi API hoàn tiền nào -
        nhà hàng tự liên hệ và hoàn tiền trực tiếp cho khách hàng."""
        self.status = OrderStatus.CANCELLED
        self.cancel_reason = reason
        self.cancelled_at = datetime.now()

    def mark_refunded_manually(self):
        """Đánh dấu đã hoàn tiền, dùng SAU KHI nhà hàng đã tự chuyển
        khoản hoàn tiền cho khách ngoài hệ thống. Chỉ để lưu vết/đối
        soát nội bộ, không gọi API chuyển tiền thật."""
        self.payment_status = PaymentStatus.REFUNDED

    def __str__(self):
        return f"Order #{self.id}"


class OrderDetail(BaseModel):
    __tablename__ = 'order_detail'

    order_id = Column(Integer, ForeignKey(Order.id), nullable=False)
    dish_id = Column(Integer, ForeignKey(Dish.id), nullable=False)
    quantity = Column(Integer, default=1, nullable=False)
    unit_price = Column(Integer, nullable=False)     # snapshot giá dish.price tại thời điểm đặt


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

    rating = Column(Integer, nullable=False)
    comment = Column(Text)
    created_date = Column(DateTime, default=datetime.now)

    sentiment_label = Column(Enum(SentimentLabel), nullable=True)   # kết quả Gemini API
    sentiment_score = Column(Float, nullable=True)

    user_id = Column(Integer, ForeignKey(User.id), nullable=False)
    dish_id = Column(Integer, ForeignKey(Dish.id), nullable=True)
    order_id = Column(Integer, ForeignKey(Order.id), nullable=True)

    __table_args__ = (
        db.CheckConstraint('rating >= 1 AND rating <= 5', name='chk_rating_range'),
    )


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
        db.CheckConstraint('dish_id != paired_dish_id', name='chk_different_dishes'),
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
