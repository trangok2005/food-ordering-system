# Hướng dẫn cài đặt & chạy dự án (local)

## 1. Yêu cầu môi trường

| Thành phần | Phiên bản | Ghi chú |
|---|---|---|
| Python | 3.11+ | đã test với 3.11.0 |
| MySQL Server | 8.x | đang chạy local, user/pass trong `.env` |
| pip | mới nhất | đi kèm Python |

Không cần Docker, không cần Node.js.

## 2. Các bước cài đặt

### Bước 1 — Tạo virtual environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

(Linux/macOS: `source venv/bin/activate`)

### Bước 2 — Cài thư viện

```bash
pip install -r requirements.txt
```

### Bước 3 — Tạo database

Đăng nhập MySQL và tạo schema (SQLAlchemy **không tự tạo database**, chỉ tạo bảng):

```sql
CREATE DATABASE tvtfooddb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### Bước 4 — Cấu hình `.env`

Copy `.env.example` thành `.env` rồi điền thông tin thật:

```powershell
Copy-Item .env.example .env
```

Các biến bắt buộc phải đúng:

- `DATABASE_USERNAME` / `DATABASE_PASSWORD` / `DATABASE_HOST` / `DATABASE_PORT` / `DATABASE_NAME`
- `PAYOS_MODE=mock` — **giữ nguyên khi demo local** (không gọi API payOS thật, không tốn tiền)
- Google OAuth + Gemini: có thể bỏ trống (`your_...`) — app vẫn chạy, chỉ mất tính năng tương ứng

### Bước 5 — Tạo bảng + dữ liệu mẫu

```bash
python seed.py
```

Script này **xóa sạch** dữ liệu cũ rồi tạo lại toàn bộ bảng và dữ liệu demo.

### Bước 6 — Chạy app

```bash
python run.py
```

Mở trình duyệt: **http://127.0.0.1:5000**

## 3. Tài khoản demo (mật khẩu đều là `123456`)

| Vai trò | Username |
|---|---|
| Admin | `admin` |
| Chủ nhà hàng Sushi House | `sushihouse_owner` |
| Chủ nhà hàng Com Tam Sai Gon | `comtam_owner` |
| Khách hàng | `nguyenvana`, `lethib` |

## 4. Chạy kiểm thử tự động

```bash
pytest app\test -q
```

Test dùng **SQLite in-memory**, không đụng tới MySQL thật. Hiện tại 175 test, tất cả pass.

## 5. Xử lý sự cố thường gặp

| Triệu chứng | Nguyên nhân & cách xử lý |
|---|---|
| `Access denied for user 'root'@'localhost'` | Sai `DATABASE_USERNAME/PASSWORD` trong `.env` |
| `Unknown database 'tvtfooddb'` | Chưa chạy lệnh `CREATE DATABASE` ở bước 3 |
| Trang trắng / lỗi 500 khi vào `/` | Chưa chạy `seed.py`, hoặc MySQL chưa bật |
| Nút "Thêm vào giỏ" không hiện | Chưa đăng nhập bằng tài khoản CUSTOMER |
| Checkout báo ngoài bán kính giao hàng | Nhà hàng có GPS nhưng khách không gửi vị trí — bấm "Dùng vị trí hiện tại" hoặc bỏ qua nếu demo nhanh (điền tọa độ trùng nhà hàng) |
| Gemini lỗi khi đánh giá món | Kiểm tra `GEMINI_API_KEY`; hệ thống vẫn lưu đánh giá bình thường (graceful fallback) |
