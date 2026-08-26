# Đặc tả Use Case chi tiết (UC-01 Xử lý đơn, UC-02 Tìm kiếm)

> Tài liệu thuộc **lớp UC (nghiệp vụ)** — tách bạch với lớp SDS.
> Mọi bước dưới đây đối chiếu trực tiếp với luồng code thật đang chạy
> (`app/restaurant/*`, `app/browse/*`), không mô tả tính năng chưa cài đặt.
> Phần phụ lục cuối tài liệu mới là ánh xạ kỹ thuật (SDS) để tra vết.

---

## UC-01 — Xử lý đơn

| Thuộc tính | Nội dung |
|---|---|
| Mã Use Case | UC-01 |
| Tên Use Case | Xử lý đơn |
| Mô tả | Chức năng cho phép chủ nhà hàng tiếp nhận, xác nhận, chuyển trạng thái chế biến – giao hàng, hoàn tất hoặc hủy đơn hàng của khách. Khi hủy đơn đã thanh toán online, nhà hàng **tự liên hệ và hoàn tiền trực tiếp cho khách ngoài hệ thống**; hệ thống chỉ lưu lý do hủy và cung cấp thao tác đánh dấu "đã hoàn tiền" để đối soát nội bộ. |
| Actor chính | Quản lý nhà hàng |
| Actor phụ | Không có |
| Tiền điều kiện | • Nhân viên đăng nhập bằng tài khoản vai trò Nhà hàng.<br>• Nhà hàng của nhân viên đã được quản trị viên duyệt và đang hoạt động.<br>• Có ít nhất một đơn hàng thuộc nhà hàng này ở trạng thái cần xử lý. |
| Hậu điều kiện | **Thành công:**<br>- Xác nhận: đơn chuyển "Đã xác nhận", ghi nhận thời điểm xác nhận.<br>- Chuyển trạng thái: đơn lần lượt qua Chuẩn bị → Đang giao → Hoàn thành.<br>- Hủy đơn: đơn chuyển "Đã hủy", lưu lý do + thời điểm hủy; nhà hàng tự hoàn tiền ngoài nghiệp vụ, sau đó có thể đánh dấu "Đã hoàn tiền" trên đơn.<br>**Thất bại:** trạng thái đơn không thay đổi, dữ liệu giữ nguyên, hiển thị thông báo lỗi tương ứng. |

### Luồng hoạt động chính

1. Nhân viên chọn chức năng "Quản lý nhà hàng" từ header sau khi đăng nhập.
2. Hệ thống hiển thị dashboard tổng quan (số đơn chờ, đang chuẩn bị, đang giao, doanh thu) và **tự động chuyển các đơn "Chờ xác nhận" đã quá hạn thành "Quá hạn"**, kèm cảnh báo số lượng.
3. Nhân viên vào tab "Đơn hàng"; hệ thống liệt kê đơn của **chỉ nhà hàng mình**, phân loại theo bộ lọc trạng thái kèm số đếm mỗi trạng thái (Chờ xác nhận, Đã xác nhận, Đang chuẩn bị, Đang giao, Hoàn thành, Đã hủy, Quá hạn).
4. Nhân viên chọn một đơn ở trạng thái "Chờ xác nhận".
5. Hệ thống hiển thị chi tiết: tên khách, SĐT, địa chỉ giao hàng, danh sách món + số lượng + **giá tại thời điểm đặt**, ghi chú, tổng tiền và thời hạn xác nhận còn lại.
6. Nhân viên kiểm tra khả năng phục vụ và bấm "Xác nhận".
7. Hệ thống kiểm tra đơn còn trong thời hạn xác nhận → chuyển trạng thái thành "Đã xác nhận", ghi nhận thời điểm xác nhận, làm mới danh sách.
8. Nhân viên chuẩn bị món; xong thì bấm nút chuyển trạng thái tiếp theo trên đơn: "Đã xác nhận" → "Đang chuẩn bị".
9. Bàn giao cho shipper → bấm chuyển sang "Đang giao"; giao thành công → bấm "Hoàn thành". Mỗi lần bấm, hệ thống cập nhật đúng một bước trạng thái và làm mới danh sách.

### Luồng thay thế

| Tại bước | Kịch bản | Xử lý |
|---|---|---|
| 6 | Nhà hàng không đủ nguyên liệu / không thể phục vụ | Nhân viên chọn "Hủy đơn", **bắt buộc nhập lý do**. Hệ thống cập nhật đơn thành "Đã hủy", lưu lý do và thời điểm hủy. Việc hoàn tiền do nhà hàng **tự liên hệ khách và thực hiện ngoài hệ thống**; sau khi đã hoàn xong, nhân viên dùng hành động "Đánh dấu đã hoàn tiền" để ghi nhận trạng thái hoàn tiền trên đơn (chỉ phục vụ đối soát, không gọi cổng thanh toán). |

### Luồng ngoại lệ

| Tại bước | Điều kiện | Xử lý |
|---|---|---|
| 6 | Đơn "Chờ xác nhận" đã quá thời hạn (hạn do nhà hàng tự đặt, mặc định 5 phút) | Hệ thống đã tự động chuyển đơn thành "Quá hạn" ngay khi tải trang; thao tác xác nhận bị từ chối với thông báo tương ứng, danh sách được làm mới |
| 4–9 | Đơn không tồn tại hoặc không thuộc nhà hàng của nhân viên | Từ chối truy cập (trang lỗi 404) — không xem/sửa được đơn của nhà hàng khác |
| 8–9 | Trạng thái hiện tại không thể chuyển tiếp (đơn đã Hoàn thành / Đã hủy / Quá hạn) | Từ chối với thông báo "Trạng thái hiện tại của đơn không thể chuyển tiếp" |
| 6 | Lý do hủy bỏ trống | Từ chối hủy, yêu cầu nhập lý do |
| 7–9 | Lỗi kết nối cơ sở dữ liệu trong quá trình cập nhật | Giao dịch không được ghi nhận (dữ liệu giữ nguyên), hệ thống hiển thị trang lỗi 500 tùy chỉnh |

**Ghi chú khác biệt so với quy trình phổ biến (đã chốt trong Charter):**
hệ thống KHÔNG gửi thông báo tự động cho khách; khách theo dõi trạng thái tại
"Hóa đơn của tôi". Hệ thống KHÔNG hoàn tiền tự động qua cổng thanh toán.

---

## UC-02 — Tìm kiếm

| Thuộc tính | Nội dung |
|---|---|
| Mã Use Case | UC-02 |
| Tên Use Case | Tìm kiếm |
| Mô tả | Cho phép khách hàng tìm kiếm nhà hàng và món ăn thông qua **một ô tìm kiếm duy nhất**. Từ khóa được tìm đồng thời theo tên nhà hàng và tên món ăn; kết quả gom về danh sách nhà hàng, sắp xếp theo thứ tự mặc định và phân trang theo cấu hình hệ thống. |
| Actor chính | Khách hàng |
| Actor phụ | Không có |
| Tiền điều kiện | • Hệ thống đang hoạt động bình thường.<br>• Dữ liệu nhà hàng và món ăn đã được lưu trong hệ thống.<br>• Khách hàng truy cập chức năng tìm kiếm (không bắt buộc đăng nhập). |
| Hậu điều kiện | **Thành công:** hiển thị danh sách nhà hàng phù hợp (kèm các món khớp từ khóa), đã phân trang theo cấu hình.<br>**Thất bại:** không tìm thấy kết quả hoặc có lỗi xử lý — hiển thị thông báo tương ứng, dữ liệu không thay đổi. |

### Luồng hoạt động chính

1. Khách hàng chọn chức năng "Tìm món" (hoặc dùng ô tìm kiếm luôn hiển thị trên thanh điều hướng).
2. Hệ thống hiển thị **một ô tìm kiếm duy nhất**.
3. Khách hàng nhập từ khóa — có thể là tên nhà hàng hoặc tên món ăn.
4. Khách hàng nhấn nút "Tìm".
5. Hệ thống loại bỏ khoảng trắng thừa ở hai đầu từ khóa.
6. Hệ thống tìm đồng thời theo tên nhà hàng **và** tên món ăn, chỉ xét các nhà hàng **đã được duyệt và đang hoạt động**.
7. Hệ thống gom kết quả thành danh sách nhà hàng duy nhất (một nhà hàng không lặp lại dù nhiều món khớp), kèm danh sách món khớp từ khóa của từng nhà hàng.
8. Hệ thống sắp xếp kết quả theo **thứ tự mặc định: tên nhà hàng (A→Z)**.
9. Hệ thống phân trang kết quả, mỗi trang hiển thị số lượng theo cấu hình hệ thống (mặc định 24, nằm trong khung 20–30 kết quả/trang theo Charter).
10. Hệ thống hiển thị tổng số kết quả, thẻ nhà hàng (tên, mô tả, địa chỉ, các món khớp kèm giá, nhãn "Mở cửa"/"Đóng cửa").
11. Khách hàng có thể chuyển sang trang kết quả khác; hệ thống hiển thị kết quả của trang được chọn.
12. Khách hàng chọn "Xem thực đơn" trên một nhà hàng để xem thông tin chi tiết và thực đơn đang bán.

### Luồng thay thế

| Tại bước | Kịch bản | Xử lý |
|---|---|---|
| 3 | Khách thay đổi từ khóa trước khi tìm | Chỉ từ khóa cuối cùng được dùng để tìm |
| 10–12 | Nhà hàng trong kết quả đang "Đóng cửa" | Vẫn hiển thị trong kết quả kèm nhãn cảnh báo; khách vẫn xem được thực đơn nhưng việc đặt món sẽ bị chặn tại bước thanh toán (theo Charter: giỏ hàng chỉ được kiểm tra điều kiện bán ở thời điểm thanh toán) |

### Luồng ngoại lệ

| Tại bước | Điều kiện | Xử lý |
|---|---|---|
| 3–4 | Từ khóa bị bỏ trống | Hiển thị hướng dẫn "Nhập từ khóa để tìm nhà hàng hoặc món ăn.", yêu cầu nhập lại |
| 6 | Không có nhà hàng/món nào phù hợp | Thông báo "Không tìm thấy kết quả nào cho …" và cho phép nhập từ khóa mới |
| 7 | Nhà hàng khớp tên nhưng món không khớp | Vẫn hiển thị nhà hàng, kèm dòng "Không có món nào khớp từ khóa." |
| 9 | Số kết quả vượt giới hạn một trang | Tự chia thành nhiều trang theo cấu hình; điều hướng Trang trước/sau bị vô hiệu hóa khi ở trang đầu/cuối |
| 6, 8 | Lỗi kết nối cơ sở dữ liệu hoặc lỗi xử lý | Hiển thị trang lỗi 500 tùy chỉnh ("Lỗi hệ thống…"), dữ liệu không thay đổi |

**Ghi chú khác biệt so với Charter:** tiêu chí "sắp xếp/phân hạng tùy chọn"
chưa được cài đặt — phiên bản hiện tại luôn sắp xếp theo tên nhà hàng (A→Z).
Hạng mục này nằm trong backlog nếu giảng viên yêu cầu bổ sung.

---

## UC-03 — Quản lý giỏ hàng

| Thuộc tính | Nội dung |
|---|---|
| Mã Use Case | UC-03 |
| Tên Use Case | Quản lý giỏ hàng |
| Mô tả | Cho phép khách hàng đã đăng nhập quản lý giỏ hàng của mình: thêm món ăn, xem giỏ, thay đổi số lượng, xóa món hoặc xóa cả giỏ theo nhà hàng. Mỗi giỏ chỉ chứa món của **một nhà hàng duy nhất**. Món đã nằm trong giỏ mà sau này bị nhà hàng ẩn (hết hàng) vẫn được giữ và hiển thị kèm cảnh báo; hệ thống chỉ kiểm tra trạng thái còn bán khi khách tiến hành thanh toán. |
| Actor chính | Khách hàng |
| Actor phụ | Không có |
| Tiền điều kiện | • Khách hàng đã đăng nhập bằng tài khoản vai trò Khách hàng.<br>• Món ăn được chọn tồn tại trong hệ thống, thuộc nhà hàng đã được duyệt và **đang còn bán**.<br>• Giỏ hàng gắn với tài khoản; mỗi giỏ áp dụng cho một nhà hàng. |
| Hậu điều kiện | **Thành công:** giỏ hàng cập nhật đúng danh sách món + số lượng; tổng tiền từng giỏ và tổng số món trên thanh điều hướng được làm mới.<br>**Thất bại:** thao tác không được thực hiện, dữ liệu giỏ giữ nguyên, hiển thị thông báo lỗi tương ứng. |

### Luồng hoạt động chính

1. Khách hàng đăng nhập vào hệ thống.
2. Khách hàng chọn một món ăn đang bán từ thực đơn nhà hàng hoặc từ trang gợi ý.
3. Khách hàng nhấn "Thêm vào giỏ".
4. Hệ thống kiểm tra món ăn hợp lệ (tồn tại, chưa bị xóa, đang còn bán) và kiểm tra giỏ hiện có của khách.
5. Nếu khách chưa có giỏ ở nhà hàng khác: hệ thống lấy/tạo giỏ cho nhà hàng của món ăn này (giỏ trống cũng được gắn với đúng một nhà hàng).
6. Nếu món đã có trong giỏ: hệ thống cộng dồn số lượng; nếu chưa có: tạo dòng món mới trong giỏ.
7. Hệ thống kiểm tra số lượng không vượt mức tối đa cho phép một món/đơn (do hệ thống mặc định hoặc nhà hàng tự quy định), lưu giỏ và thông báo thêm thành công.
8. Khách hàng chọn "Giỏ hàng" trên thanh điều hướng (biểu tượng kèm badge tổng số món).
9. Hệ thống hiển thị các giỏ **phân nhóm theo nhà hàng**: tên món, đơn giá, ô nhập số lượng, thành tiền, tổng cộng từng giỏ; món hết hàng hiển thị kèm nhãn cảnh báo "Hết hàng" (vẫn giữ trong giỏ, không tự xóa).
10. Khách hàng nhập số lượng mới và bấm "Cập nhật"; hệ thống kiểm tra tính hợp lệ (≥ 1, ≤ mức tối đa) và ghi nhận.
11. Khách hàng bấm nút xóa bên cạnh một món → hệ thống xóa dòng món đó khỏi giỏ.
12. Khách hàng có thể bấm "Xóa toàn bộ" để xóa sạch một giỏ (theo nhà hàng); hệ thống xóa giỏ và làm mới danh sách.
13. Khi muốn mua, khách hàng bấm "Thanh toán" → chuyển sang UC-04 (Đặt hàng & thanh toán).

### Luồng thay thế

| Tại bước | Kịch bản | Xử lý |
|---|---|---|
| 2 | Khách chọn trực tiếp "Giỏ hàng" để xem các món đã thêm trước đó | Hiển thị toàn bộ giỏ hiện có phân nhóm theo nhà hàng |
| 5 | Món được chọn thuộc **nhà hàng khác** với giỏ hiện có | Hệ thống hiển thị **trang xác nhận riêng**, nêu rõ giỏ đang chứa món của nhà hàng nào và hỏi khách lựa chọn: (a) đồng ý — hệ thống xóa toàn bộ giỏ cũ rồi thêm món mới vào giỏ của nhà hàng kia; (b) quay lại — giữ nguyên giỏ, món không được thêm |
| 13 | Khách chọn "Tiếp tục mua sắm" trên trang giỏ | Đưa khách về trang tìm kiếm/nhà hàng, giỏ hàng giữ nguyên |

### Luồng ngoại lệ

| Tại bước | Điều kiện | Xử lý |
|---|---|---|
| 1 | Chưa đăng nhập | Chuyển hướng tới trang đăng nhập, yêu cầu đăng nhập trước khi thao tác giỏ hàng |
| 1 | Tài khoản có vai trò **Nhà hàng** | Chặn toàn bộ chức năng giỏ/thanh toán (lỗi 403): tài khoản nhà hàng chỉ quản lý đơn, không tự đặt món |
| 4 | Món ăn không tồn tại / đã bị xóa / **đang hết hàng** | Từ chối thêm với thông báo "Món ăn không khả dụng". Lưu ý: quy tắc "hết hàng vẫn giữ trong giỏ" chỉ áp dụng cho món **đã có sẵn** trong giỏ trước khi nhà hàng ẩn món — món hết hàng **không thể thêm mới** |
| 6–7, 10 | Số lượng cộng dồn vượt mức tối đa một món/đơn | Từ chối với thông báo "Mỗi món chỉ được đặt tối đa … phần", giỏ giữ nguyên giá trị hợp lệ trước đó |
| 10 | Số lượng nhỏ hơn 1 hoặc không phải số | Thông báo "Số lượng không hợp lệ", yêu cầu điều chỉnh |
| 11–12 | Giỏ/cart không tồn tại hoặc không thuộc tài khoản đang đăng nhập | Từ chối với thông báo "Giỏ hàng không tồn tại"/"Sản phẩm không có trong giỏ" |
| 7, 10–12 | Lỗi kết nối cơ sở dữ liệu | Dữ liệu không được ghi (giữ nguyên trạng thái giỏ trước đó), hiển thị trang lỗi 500 tùy chỉnh |

**Ghi chú khác biệt so với bản nháp tham khảo:** (1) món hết hàng **không thể thêm mới**
vào giỏ — chỉ món đã nằm trong giỏ mới được giữ lại khi về sau hết hàng;
(2) thao tác đổi số lượng dùng ô nhập + nút "Cập nhật", không phải cặp nút tăng/giảm;
(3) ngoài xóa từng món còn có thao tác "Xóa toàn bộ" giỏ theo nhà hàng.

---

## Phụ lục — Ánh xạ UC ↔ nơi cài đặt (lớp SDS, chỉ để tra vết)

| Bước UC-01 | Nơi cài đặt |
|---|---|
| 2 (tự động hết hạn) | `app/restaurant/dao.py` — `expire_overdue_orders` |
| 3 (danh sách + bộ lọc + số đếm) | `app/restaurant/router.py` — `orders_view`; `dao.get_restaurant_orders`, `get_order_status_counts` |
| 5 (chi tiết đơn, giá snapshot) | `app/templates/restaurant/orders.html`; `OrderDetail.unit_price` |
| 6–7 (xác nhận + hạn) | `router.confirm_order`; `dao.confirm_order` (kiểm tra deadline), `Order.set_confirm_deadline` |
| 8–9 (chuỗi trạng thái) | `dao.advance_order` + bảng ánh xạ `NEXT_STATUS` |
| LT (hủy + lý do) | `router.cancel_order`; `dao.cancel_order`, `Order.cancel_by_restaurant` |
| LT (đánh dấu hoàn tiền) | `router.mark_refunded`; `dao.mark_refunded`, `Order.mark_refunded_manually` |
| LN (404 đơn người khác) | `_current_restaurant`, `_load_order` |

| Bước UC-02 | Nơi cài đặt |
|---|---|
| 5–6 (tìm đồng thời) | `app/browse/dao.py` — `search` (`ilike` trên `Restaurant.name` + `Dish.name`) |
| 7 (gom distinct + món khớp) | `query.distinct()`; `app/browse/router.py` — `search_view` lọc món khớp |
| 8 (thứ tự mặc định) | `query.order_by(Restaurant.name)` |
| 9 (phân trang) | `paginate(per_page=SEARCH_PAGE_SIZE)` — cấu hình trong `SystemConfig`, Admin sửa tại `/admin/config` |
| 12 (xem thực đơn) | `router.restaurant_menu_view` — chỉ trả nhà hàng APPROVED |

| Bước UC-03 | Nơi cài đặt |
|---|---|
| 1 (chặn vai trò/truy cập) | `app/cart/router.py` — `before_request` `_block_restaurant_ordering`; decorator `login_required` |
| 4–7 (thêm món, cộng dồn, giới hạn) | `app/cart/dao.py` — `add_to_cart`, `_max_quantity_for_dish`, ngoại lệ `CartRestaurantConflict` |
| LT (trang xác nhận đổi nhà hàng) | `router.add_to_cart` bắt `CartRestaurantConflict` → `cart_confirm.html`; `router.confirm_switch` + `dao.clear_all_carts` |
| 9–10 (hiển thị + cập nhật số lượng) | `templates/cart.html` (`qty-form`); `router.update_cart_item`, `dao.update_cart_item` |
| 11 (xóa món) | `router.remove_cart_item`, `dao.remove_cart_item` |
| 12 (xóa cả giỏ) | `router.clear_cart`, `dao.clear_cart` |
| Badge tổng số món trên header | context processor trong `app/__init__.py` — `get_cart_stats`; API `/cart/api/stats` cho JS |
| LN (lỗi DB → trang lỗi) | `app/__init__.py` — `errorhandler(500)` có `rollback()` |
