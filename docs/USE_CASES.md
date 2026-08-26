# Đặc tả Use Case (lớp nghiệp vụ)

> **Phân tầng tài liệu — đọc kỹ trước khi dùng:**
>
> | Tầng | Dành cho | Nội dung | File |
> |---|---|---|---|
> | **UC** (tài liệu này) | Người đọc, giảng viên, khách hàng | Nghiệp vụ: ai làm gì, vì mục đích gì, kết quả gì. KHÔNG chứa route, hàm, bảng, code. | `docs/USE_CASES.md` |
> | **SDS / Execution trace** | Lập trình viên | Luồng kỹ thuật: request nào gọi router nào → DAO nào → bảng nào, xử lý lỗi ở đâu. | `docs/DEMO_SCRIPT.md`, phần phụ lục ánh xạ ở cuối file này |
>
> Mọi bước trong UC dưới đây đều rút ra từ luồng thật đã chạy được của hệ thống
> (đã kiểm chứng bằng test client + 175 test tự động), không bịa thêm và không
> bỏ bớt bước nghiệp vụ nào so với Project Charter.

---

## 1. Tác nhân (Actors)

| Tác nhân | Mô tả |
|---|---|
| Khách hàng (Customer) | Người đặt món qua nền tảng; gồm tài khoản nội bộ và tài khoản Google OAuth |
| Chủ nhà hàng (Restaurant Staff) | Người quản lý thực đơn, xác nhận/xử lý đơn hàng của nhà hàng mình |
| Quản trị viên (Admin) | Người vận hành nền tảng: duyệt nhà hàng, quản lý người dùng, cấu hình |
| Cổng thanh toán payOS *(tác nhân phụ)* | Hệ thống ngoài thực hiện thu tiền và xác nhận kết quả thanh toán |

## 2. Danh mục Use Case

| Mã | Tên Use Case | Tác nhân chính | Mức |
|---|---|---|---|
| **UC-01** | Đặt món và thanh toán trực tuyến | Khách hàng | Chi tiết bên dưới |
| UC-02 | Quản lý tài khoản (đăng ký, đăng nhập nội bộ/Google, quên/đổi mật khẩu, hồ sơ) | Khách hàng, Chủ nhà hàng, Admin | Tóm tắt §4 |
| UC-03 | Đăng ký bán hàng (nhà hàng tự đăng ký, chờ duyệt) | Khách hàng | Tóm tắt §4 |
| UC-04 | Quản lý thực đơn (danh mục, món ăn, ẩn món hết hàng) | Chủ nhà hàng | Tóm tắt §4 |
| UC-05 | Xử lý đơn hàng (xác nhận, chuyển trạng thái, hủy, quá hạn) | Chủ nhà hàng | Tóm tắt §4 |
| UC-06 | Vận hành nền tảng (duyệt/khóa nhà hàng, quản lý user, cấu hình hệ thống) | Admin | Tóm tắt §4 |
| UC-07 | Đánh giá món ăn & phân tích cảm xúc bình luận | Khách hàng | Tóm tắt §4 |
| UC-08 | Nhận gợi ý món cá nhân hóa & dự đoán món đi kèm | Khách hàng | Tóm tắt §4 |

---

## 3. UC-01 — Đặt món và thanh toán trực tuyến

| Thuộc tính | Giá trị |
|---|---|
| Mã | UC-01 |
| Tên | Đặt món và thanh toán trực tuyến |
| Tác nhân chính | Khách hàng |
| Tác nhân phụ | Cổng thanh toán payOS |
| Mô tả | Khách hàng chọn món từ một nhà hàng, thanh toán trực tuyến; đơn hàng chỉ hình thành sau khi thanh toán thành công. |
| Tiền điều kiện | Khách hàng đã đăng nhập (giỏ hàng gắn với tài khoản). Có ít nhất một nhà hàng đang được duyệt và mở cửa. |
| Hậu điều kiện thành công | Đơn hàng tồn tại ở trạng thái "Chờ xác nhận", đã đánh dấu đã trả tiền; giỏ hàng tương ứng bị xóa. Nhà hàng thấy đơn mới trong trang quản lý. |
| Hậu điều kiện thất bại (thanh toán không hoàn tất) | Không có đơn hàng nào được tạo; giỏ hàng giữ nguyên để khách thử lại. |

### 3.1 Luồng chính (Main Success Scenario)

| # | Khách hàng | Hệ thống |
|---|---|---|
| 1 | Tra cứu bằng một ô từ khóa duy nhất | Trả về danh sách nhà hàng có tên hoặc món khớp từ khóa, phân trang theo cấu hình hệ thống |
| 2 | Chọn xem thực đơn một nhà hàng | Hiển thị các danh mục và món **đang bán** của nhà hàng đó |
| 3 | Thêm một món vào giỏ | Nếu chưa có giỏ cho nhà hàng này thì tạo giỏ mới; ghi nhận số lượng món |
| 4 | Xem giỏ hàng, điều chỉnh số lượng hoặc bỏ bớt món | Cập nhật giỏ; giới hạn số lượng mỗi món theo cấu hình (mặc định hệ thống hoặc do nhà hàng quy định) |
| 5 | Khai báo số điện thoại, địa chỉ giao hàng, ghi chú (tùy chọn), vị trí GPS (tùy chọn) và bấm đặt hàng | Kiểm tra toàn bộ điều kiện bán: nhà hàng đang mở cửa, giá trị đạt mức tối thiểu, mọi món còn bán, vị trí nằm trong bán kính giao hàng |
| 6 | — | Mở cửa sổ **hủy miễn phí 10 giây**: đếm ngược trước khi chuyển sang cổng thanh toán |
| 7 | Không hủy trong 10 giây | Tạo yêu cầu thanh toán tại payOS và chuyển trình duyệt khách sang cổng thanh toán |
| 8 | Thanh toán trên cổng payOS | Nhận kết quả từ cổng thanh toán |
| 9 | — | Khi và chỉ khi cổng xác nhận **thanh toán thành công**: tạo đơn ở trạng thái "Chờ xác nhận" kèm thời hạn xác nhận của nhà hàng (mặc định 5 phút, mỗi nhà hàng có thể tự đặt), đánh dấu đã trả tiền, và xóa giỏ hàng |
| 10 | Xem trang kết quả thanh toán và hóa đơn của mình | Hiển thị mã đơn, tổng tiền, trạng thái; đơn xuất hiện trong danh sách chờ xác nhận của nhà hàng |

### 3.2 Luồng thay thế và ngoại lệ

| Mã | Tại bước | Điều kiện | Hành vi hệ thống |
|---|---|---|---|
| A1 | 2 | Nhà hàng chưa có món đang bán | Hiển thị thông báo trống, không cho thao tác thêm giỏ |
| A2 | 3 | Giỏ hiện tại đang thuộc nhà hàng khác | Yêu cầu khách xác nhận "xóa giỏ cũ"; khách đồng ý thì xóa giỏ cũ rồi thêm món mới; từ chối thì giữ nguyên giỏ, món không được thêm |
| A3 | 4 | Số lượng vượt mức tối đa cho phép | Từ chối cập nhật và thông báo giới hạn |
| A4 | 5 | Giỏ hàng trống | Không cho vào bước thanh toán |
| A5 | 5 | Nhà hàng đóng cửa / đơn chưa đạt tối thiểu / món hết hàng / ngoài bán kính giao | Chặn việc đặt hàng và liệt kê cụ thể từng lý do |
| A6 | 6 | Khách bấm hủy trong vòng 10 giây | Quay về trang thanh toán, không tạo yêu cầu thanh toán, không phát sinh giao dịch |
| A7 | 8 | Khách hủy thanh toán hoặc thanh toán thất bại | **Không tạo đơn**; hiển thị kết quả thất bại; giỏ giữ nguyên để khách thử lại |
| A8 | 9 | Thanh toán thành công nhưng hệ thống lỗi khi tạo đơn | Báo lỗi rõ ràng cho khách; dữ liệu giỏ được bảo toàn để khắc phục (không mất tiền "ma") |

### 3.3 Quy tắc nghiệp vụ (nguồn: Project Charter — nguồn sự thật)

1. Chỉ hỗ trợ thanh toán **trực tuyến qua payOS**, không có COD.
2. **Đơn chỉ được tạo sau khi payOS xác nhận đã trả tiền**; bấm "Đặt hàng" chỉ là chuẩn bị chuyển hướng thanh toán.
3. Mỗi giỏ hàng chỉ áp dụng cho **một nhà hàng duy nhất**; đổi nhà hàng phải chủ động xóa giỏ cũ.
4. Giỏ hàng bắt buộc đăng nhập, không có giỏ ẩn danh.
5. Hủy miễn phí chỉ tồn tại **trong 10 giây sau khi bấm đặt hàng, trước khi sang cổng thanh toán**; hết thời gian đó khách không còn quyền tự hủy.
6. Nhà hàng hủy đơn đã thanh toán (hết nguyên liệu...) → lưu lý do; **việc hoàn tiền do nhà hàng tự liên hệ và thực hiện trực tiếp với khách, ngoài hệ thống**.
7. Khoảng cách giao hàng tính đường chim bay (Haversine) theo GPS thật; bán kính mặc định 10 km, nhà hàng tự chỉnh riêng.

---

## 4. Tóm tắt các UC còn lại

### UC-02 — Quản lý tài khoản
Đăng ký/đăng nhập nội bộ; đăng nhập Google OAuth (tự liên kết theo email nếu đã có tài khoản); khóa tự động sau 5 lần sai liên tiếp (15 phút) và chặn dò mật khẩu theo IP; quên mật khẩu qua link một lần hiệu lực 30 phút; đổi mật khẩu; cập nhật hồ sơ (họ tên, SĐT, địa chỉ, avatar).

### UC-03 — Đăng ký bán hàng
Khách hàng điền thông tin nhà hàng (+ GPS), gửi đăng ký → tài khoản được nâng quyền Chủ nhà hàng, nhà hàng ở trạng thái "Chờ duyệt" → Admin duyệt mới hiển thị công khai và nhận được đơn.

### UC-04 — Quản lý thực đơn
Chủ nhà hàng CRUD danh mục (không trùng tên trong cùng nhà hàng; chỉ xóa danh mục trống), CRUD món ăn (giá nguyên dương, ảnh theo đường dẫn), **ẩn/bật món hết hàng** (món ẩn vẫn nằm trong giỏ cũ, chỉ chặn lúc thanh toán), xóa món theo kiểu soft-delete để bảo toàn lịch sử đơn/đánh giá.

### UC-05 — Xử lý đơn hàng
Nhà hàng xác nhận đơn "Chờ xác nhận" đúng hạn (quá hạn → tự động "Quá hạn/hủy"), lần lượt chuyển Chuẩn bị → Đang giao → Hoàn thành; lọc đơn theo trạng thái; hủy đơn bắt buộc nhập lý do; đánh dấu "đã hoàn tiền" sau khi tự hoàn ngoài hệ thống; dashboard doanh thu và số đếm trạng thái.

### UC-06 — Vận hành nền tảng
Admin xem dashboard/thống kê toàn hệ thống (doanh thu, top nhà hàng/món); duyệt – khóa – mở khóa nhà hàng; tìm/lọc người dùng và khóa/mở khóa tài khoản; chỉnh các cấu hình mặc định hệ thống (thời hạn xác nhận, giá trị đơn tối thiểu, số lượng tối đa mỗi món, số kết quả mỗi trang).

### UC-07 — Đánh giá món ăn & phân tích cảm xúc
Khách đánh giá sao 1–5 kèm bình luận cho từng món của đơn **đã hoàn thành** (mỗi món/đơn một lần). Bình luận được Gemini phân tích cảm xúc (Tích cực/Trung lập/Tiêu cực); nếu dịch vụ AI lỗi thì đánh giá vẫn được lưu bình thường — không cản trở người dùng.

### UC-08 — Gợi ý món & dự đoán món đi kèm
Gợi ý cá nhân hóa dựa trên lịch sử hành vi (xem/thêm giỏ/đặt/đánh giá, khung giờ, khẩu vị nhóm món); chưa có dữ liệu thì fallback sang món phổ biến. Dự đoán "món thường đặt kèm" tính bằng luật kết hợp từ các đơn hoàn thành của từng nhà hàng (chạy lại theo yêu cầu của nhà hàng). Cả hai đều là tính năng phụ trợ — lỗi AI không làm crash nghiệp vụ chính.

---

## Phụ lục — Ánh xạ UC-01 ↔ nơi cài đặt (thuộc lớp SDS, chỉ để tra vết)

| Bước UC | Nơi cài đặt |
|---|---|
| 1 | `app/browse/router.py` (`search_view`) + `app/browse/dao.py` (`search`) |
| 2 | `app/browse/router.py` (`restaurant_menu_view`) |
| 3–4 | `app/cart/router.py` (`add_to_cart`, `confirm_switch`, `update_cart_item`...) + `app/cart/dao.py` |
| 5 | `app/templates/checkout.html` + `app/static/js/checkout.js` |
| 5 (kiểm tra bán) | `app/cart/dao.py` (`validate_checkout`) |
| 6 | Modal `freeCancelModal` trong `checkout.html`, logic đếm ngược trong `checkout.js` |
| 7–8 | `app/cart/router.py` (`create_payment`) + `app/cart/payos.py` (factory mock/live) |
| 9 | `app/cart/router.py` (`payment_return`) + `app/cart/dao.py` (`create_orders_from_pending`) |
| 10 | `app/templates/payment_result.html`, `my_orders.html` |
