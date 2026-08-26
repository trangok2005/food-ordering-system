# Kịch bản demo (script chạy theo trình tự)

Chuẩn bị: `python seed.py` rồi `python run.py`, mở http://127.0.0.1:5000.
Mật khẩu tất cả tài khoản: `123456`.

## 1. Khách hàng — tìm món, đặt món, thanh toán (mock)

1. Đăng nhập `nguyenvana`.
2. Ô "Tìm món" gõ `sushi` → thấy Sushi House kèm các món khớp từ khóa (phân trang 24 kết quả/trang).
3. Vào menu nhà hàng, thêm 2 món vào giỏ. Thử thêm món của nhà hàng khác → hệ thống hỏi
   **xóa giỏ cũ để đổi nhà hàng** (mỗi giỏ chỉ thuộc 1 nhà hàng).
4. Vào Giỏ hàng → sửa số lượng, xóa món.
5. Checkout: điền địa chỉ + SĐT → bấm "Đặt hàng" → đếm ngược hủy miễn phí 10 giây
   (client-side) → chuyển sang trang **PayOS giả lập** (`/cart/mock-payos/...`).
6. Bấm "Giả lập thanh toán thành công" → về trang kết quả, đơn được tạo với trạng thái
   **Pending**, có hạn xác nhận 5 phút.
7. Menu "Hóa đơn của tôi" xem trạng thái đơn.

## 2. Nhà hàng — quản lý thực đơn & xử lý đơn

Đăng xuất, đăng nhập `sushihouse_owner`:

1. Dashboard: doanh thu, số đơn theo trạng thái, cấu hình hiện tại.
2. Tab **Thực đơn**: thêm danh mục → thêm món → thử **Ẩn món** (badge chuyển "Hết hàng")
   → khách sẽ không thấy món đó nữa nhưng món trong giỏ cũ vẫn giữ đến lúc checkout.
3. Tab **Cấu hình**: bật/tắt mở cửa, đổi thời gian xác nhận, bán kính giao hàng.
4. Tab **Đơn hàng**: xác nhận đơn Pending của `nguyenvana` → chuyển lần lượt
   Đang chuẩn bị → Đang giao → Hoàn thành. Thử Hủy đơn (bắt buộc nhập lý do;
   hoàn tiền do nhà hàng tự liên hệ khách ngoài hệ thống).
5. Bấm nút **"Cập nhật luật kết hợp món ăn (AI)"** trên dashboard → tính association rules
   từ các đơn hoàn thành (seed đã có sẵn đơn 2 món).

## 3. Admin — duyệt & quản trị

Đăng xuất, đăng nhập `admin`:

1. **Tổng quan**: số liệu toàn hệ thống, danh sách nhà hàng chờ duyệt.
2. **Người dùng**: lọc theo vai trò / tìm kiếm; thử khóa và mở khóa một tài khoản.
3. **Duyệt nhà hàng**: duyệt nhà hàng PENDING (tạo bằng kịch bản 4 bên dưới) →
   chủ nhà hàng đăng nhập lại là dùng được.
4. **Cấu hình**: đổi ví dụ `SEARCH_PAGE_SIZE = 10` → quay lại trang tìm kiếm thấy số
   kết quả/trang thay đổi ngay.
5. Vô tình truy cập `/admin/users` bằng tài khoản thường → trang **403**; truy cập URL
   lạ → trang **404** tùy chỉnh.

## 4. Đăng ký nhà hàng mới + AI

1. Đăng nhập `lethib` (khách hàng) → Hồ sơ cá nhân → nút **"Đăng ký bán hàng"** →
   điền thông tin, bấm "Dùng vị trí hiện tại" lấy GPS → gửi → chờ admin duyệt
   (kịch bản 3, mục 3).
2. Vẫn đang đăng nhập `lethib`: menu **"Gợi ý cho bạn"** → trang gợi ý món cá nhân hóa
   (dựa trên lịch sử hành vi trong seed) + mục "Món thường được đặt kèm giỏ hàng"
   (association rules) + món nổi bật toàn hệ thống.
3. Sau khi có đơn Hoàn thành: mở "Hóa đơn của tôi" → đánh giá món, nhập bình luận →
   Gemini phân tích cảm xúc (POSITIVE/NEUTRAL/NEGATIVE); nếu API lỗi thì đánh giá vẫn lưu,
   hiện cảnh báo nhẹ (graceful fallback).

## 5. Quên mật khẩu

1. Đăng xuất → Đăng nhập → "Quên mật khẩu?" → nhập `nguyenvana` hoặc email.
2. Link đặt lại hiện trực tiếp trên màn hình (demo local không có SMTP), hiệu lực 30 phút.
3. Mở link → đặt mật khẩu mới → đăng nhập bằng mật khẩu mới.

## 6. Google OAuth (tùy chọn khi demo)

Chỉ hoạt động khi `.env` có GOOGLE_CLIENT_ID/SECRET hợp lệ và redirect URI
`http://127.0.0.1:5000/auth/login/google/callback` được khai báo trên Google Console.
Nếu chưa cấu hình: bấm nút Google sẽ hiện flash báo chưa cấu hình, không crash.
