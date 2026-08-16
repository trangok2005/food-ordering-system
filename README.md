# Food Ordering System — Nhóm 17

> **File này dành cho cả người và AI coding assistant (Claude Code, Copilot, Cursor...).**

## 1. Tổng quan dự án

Hệ thống đặt món ăn trực tuyến — nền tảng trung gian kết nối khách hàng với nhiều nhà hàng.
Đồ án học phần, nhóm 3 người, giảng viên: Thầy Nguyễn Trung Hậu (mã dự án Nhom17).

- **Thời gian**: 26/6/2026 → 4/9/2026
- **Stack**: Python Flask + Jinja2 + Bootstrap, MySQL (SQLAlchemy ORM), Flask-Login
- **Tài liệu gốc**: `Project_Charter_v3.docx` là nguồn sự thật cao nhất — mọi thay đổi phạm vi phải
  phản ánh lại vào Charter, không chỉ sửa code.

## 2. QUY TẮC BẮT BUỘC CHO AI — đọc kỹ trước khi gợi ý code

Đây là các quyết định **đã được chốt sau nhiều vòng phản biện** — KHÔNG tự ý đề xuất ngược lại,
kể cả khi nhìn thấy pattern phổ biến "hay hơn" ở nơi khác:

1. **KHÔNG có thanh toán COD.** Chỉ thanh toán trực tuyến qua payOS. `PaymentMethod` chỉ có
   `ONLINE`. Nếu thấy code nào tham chiếu `PaymentMethod.COD` — đó là lỗi (đã từng xảy ra do dán
   nhầm code mẫu cũ), phải xóa/sửa ngay.
2. **KHÔNG hash mật khẩu bằng `hashlib.md5`.** Luôn dùng `User.set_password()` /
   `User.check_password()` (werkzeug) đã có sẵn trong `models.py`.
3. **`Cart` chỉ unique theo cặp `(user_id, restaurant_id)`**, KHÔNG unique riêng `user_id`. Một
   user có thể có nhiều cart (ở các nhà hàng khác nhau tại các thời điểm khác nhau), nhưng chỉ 1
   cart cho mỗi nhà hàng.
4. **`Order` chỉ được tạo SAU KHI payOS xác nhận thanh toán thành công.** Không tạo `Order` ở bước
   khách hàng bấm "Đặt hàng" — lúc đó chỉ tạo payment link.
5. **Hủy đơn 10 giây**: sau khi khách bấm "Đặt hàng", có 10 giây để hủy MIỄN PHÍ, xử lý hoàn toàn
   ở client-side (JS đếm ngược) TRƯỚC khi gọi API tạo payment link / redirect payOS. Hết 10 giây,
   hệ thống KHÔNG hỗ trợ khách tự hủy nữa.
6. **KHÔNG có hoàn tiền tự động.** Nếu nhà hàng phải hủy đơn đã thanh toán (hết nguyên liệu...),
   hệ thống chỉ lưu `cancel_reason` — nhà hàng tự liên hệ và hoàn tiền trực tiếp cho khách NGOÀI
   hệ thống. Không gọi payOS payout API, không thu thập số tài khoản ngân hàng khách hàng.
7. **payOS KHÔNG có sandbox/test mode.** Mọi giao dịch qua API đều là giao dịch thật (dùng số tiền
   nhỏ để test, vd 2000đ). Tiền chảy về tài khoản của người đăng ký kênh thanh toán (đại diện
   nhóm), không phải giao dịch trực tiếp khách hàng ↔ nhà hàng.
8. **Webhook payOS không gọi được vào `localhost`.** Khi dev local, dùng cách polling
   (`GET /v2/payment-requests/{id}`) ở route `return_url` thay vì chờ webhook. Chỉ cần webhook thật
   khi đã deploy lên domain public hoặc dùng ngrok.
9. **Bán kính giao hàng tính đường chim bay (Haversine)**, mặc định 10km, cho phép **tùy chỉnh
   theo từng nhà hàng** (không phải hằng số cứng toàn hệ thống).
10. **Xác nhận đơn hàng**: nhà hàng có mặc định 5 phút để xác nhận (tùy chỉnh theo nhà hàng), quá
    hạn tự động hủy (`OrderStatus.EXPIRED`).
11. **Giỏ hàng bắt buộc đăng nhập** — không có giỏ hàng ẩn danh (guest cart).
12. **Tìm kiếm bằng 1 ô từ khóa duy nhất**, áp dụng đồng thời cho tên nhà hàng VÀ tên món ăn, 20-30
    kết quả/trang.
13. Đăng nhập có **2 phương thức**: nội bộ (username/password) + Google OAuth. Khóa tài khoản sau
    5 lần đăng nhập sai (15 phút) — đã có sẵn trong `User.register_failed_login()`.
14. 3 tính năng AI ở mức: gợi ý món ăn (mô hình nhỏ, không cần deep learning tự huấn luyện), dự
    đoán món ăn đi kèm (association rules), phân tích cảm xúc bình luận (Gemini API) — **không mở
    rộng thêm mô hình phức tạp hơn** trừ khi cả nhóm thống nhất lại (rủi ro trễ tiến độ đã ghi
    trong Charter mục 6).

## 3. Cấu trúc thư mục & phân công (để AI không gợi ý sửa nhầm module người khác)

```
app/
├── __init__.py        # app factory — CHỈ sửa khi thêm blueprint mới (2 dòng)
├── extensions.py       # db, login_manager — import từ đây, KHÔNG import từ app/__init__.py
├── models.py            # schema chung — ĐÓNG BĂNG, ai sửa phải báo cả nhóm trước
├── auth/       (Trạng - PM)     — đăng ký/đăng nhập/OAuth, dao.py + router.py
├── restaurant/ (Trạng - PM)     — quản lý thực đơn, xử lý đơn, admin
├── browse/     (Thành)          — tìm kiếm/duyệt nhà hàng, xem thực đơn
├── cart/       (Tuấn Anh)       — giỏ hàng, checkout, tích hợp payOS
├── ai/                          — 3 người tự thêm file riêng (recommend.py, pairing.py, sentiment.py)
└── templates/, static/

test/
├── conftest.py          # fixture chung (app, client, db) — SQLite in-memory, không cần MySQL thật
└── test_<module>.py     # mỗi người 1 file test riêng, tránh conflict Git
```

**Nguyên tắc bất di bất dịch**: AI chỉ nên sửa file trong đúng folder module đang làm việc, không
tự ý sửa `models.py` hay `app/__init__.py` trừ khi người dùng yêu cầu rõ ràng.

## 4. Model schema (tóm tắt — xem đầy đủ ở `app/models.py`)

`User` (role: CUSTOMER/RESTAURANT/ADMIN) · `OAuthAccount` · `Restaurant` (status PENDING→APPROVED,
`confirm_timeout_minutes`, `min_order_amount`, lat/lng) · `Category` · `Dish` (`is_available` để ẩn
khi hết hàng) · `Cart`/`CartItem` (unique theo cặp user+restaurant) · `Order` (status: Pending→
Confirmed→Preparing→Delivering→Completed, hoặc Cancelled/Expired; có `cancel_reason`,
`confirm_deadline`) · `OrderDetail` (snapshot `unit_price`) · `Review` (kèm sentiment) ·
`DishPairing` (association rules) · `UserDishInteraction` (log hành vi cho gợi ý) · `SystemConfig`
(ràng buộc mặc định toàn hệ thống, nhà hàng override riêng).

## 5. Setup & chạy thử

```bash
pip install -r requirements.txt
cp .env.example .env   # điền DATABASE_*, SECRET_KEY, GOOGLE_CLIENT_*, PAYOS_*
python run.py
```

Chạy test: `pytest` (dùng SQLite in-memory, không đụng DB thật).

