# Hệ thống đặt món ăn trực tuyến

## Giới thiệu

Đây là website trung gian giữa khách hàng và nhà hàng. Khách hàng có thể tìm món,
quản lý giỏ hàng, đặt món và thanh toán trực tuyến. Nhà hàng quản lý thực đơn và
xử lý các đơn nhận được. Hệ thống còn có gợi ý món cá nhân hóa, gợi ý món đi kèm
và phân tích cảm xúc từ bình luận.

## Công nghệ sử dụng

- Python 3.11
- Flask, Flask-Login, Flask-Migrate
- SQLAlchemy, Alembic
- MySQL, PyMySQL
- Jinja2, Bootstrap, JavaScript
- PayOS
- Google OAuth
- Gemini API
- scikit-learn, NumPy
- Gunicorn
- Git, GitHub

## Chức năng chính

### Khách hàng

- Đăng ký, đăng nhập và đặt lại mật khẩu
- Đăng nhập bằng Google OAuth
- Tìm kiếm nhà hàng và món ăn
- Xem thực đơn của nhà hàng
- Thêm, cập nhật và xóa món trong giỏ hàng
- Đặt hàng và thanh toán qua PayOS
- Theo dõi trạng thái đơn hàng
- Đánh giá món đã đặt

### Nhà hàng

- Đăng ký nhà hàng
- Quản lý danh mục và món ăn
- Bật hoặc tắt món đang bán
- Tiếp nhận, xác nhận và xử lý đơn
- Cấu hình bán kính giao hàng, giá trị đơn tối thiểu và thời gian xác nhận

### Quản trị viên

- Duyệt, khóa và mở khóa nhà hàng
- Quản lý tài khoản người dùng
- Xem dashboard và thống kê
- Cập nhật cấu hình hệ thống

### Tính năng thông minh

- Gợi ý món cá nhân hóa bằng Matrix Factorization (NMF)
- Gợi ý món đi kèm bằng association rules
- Phân tích cảm xúc bình luận bằng Gemini

## Yêu cầu môi trường

- Python 3.11
- MySQL
- `pip`
- Python virtual environment
- Git

Google OAuth, PayOS live, Gemini và SMTP cần tài khoản hoặc API key tương ứng.
Khi phát triển local có thể dùng PayOS mock và bỏ trống các dịch vụ chưa dùng.

## Cài đặt

Clone project:

```bash
git clone https://github.com/trangok2005/food-ordering-system.git
cd food-ordering-system
```

Tạo và kích hoạt virtual environment trên Windows:

```powershell
python -m venv venv
.\venv\Scripts\activate
python -m pip install -r requirements.txt
```

## Cấu hình `.env`

Tạo file `.env` ở thư mục gốc. Ví dụ cấu hình development:

```env
APP_ENV=development
APP_BASE_URL=http://127.0.0.1:5000
SECRET_KEY=thay_bang_chuoi_ngau_nhien_dai

DATABASE_URL=mysql+pymysql://root:password@127.0.0.1:3306/tvtfooddb?charset=utf8mb4

GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

PAYOS_MODE=mock
PAYOS_CLIENT_ID=
PAYOS_API_KEY=
PAYOS_CHECKSUM_KEY=

GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash

SMTP_HOST=
SMTP_PORT=587
SMTP_FROM=
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_USE_SSL=false
```

Có thể thay `DATABASE_URL` bằng các biến riêng:

```env
DATABASE_USERNAME=root
DATABASE_PASSWORD=password
DATABASE_HOST=127.0.0.1
DATABASE_PORT=3306
DATABASE_NAME=tvtfooddb
```

Không đưa file `.env` hoặc API key thật lên GitHub.

## Khởi tạo database

Tạo database MySQL trước, sau đó chạy migration:

```bash
python -m flask db upgrade
```

Nạp dữ liệu demo:

```bash
python seed.py --demo
```

Xóa dữ liệu cũ và seed lại:

```bash
python seed.py --demo --reset
```

Không dùng `--demo --reset` trên production.

## Chạy hệ thống

```bash
python -m flask run
```

Truy cập:

```text
http://127.0.0.1:5000
```

## Tài khoản demo

Các tài khoản sau chỉ dùng cho môi trường demo/dev:

| Vai trò | Tài khoản | Mật khẩu |
|---|---|---|
| Quản trị viên | `admin` | `?` |
| Khách hàng | `nguyenvana` | `?` |
| Nhà hàng Sushi House | `sushi` | `?` |
| Nhà hàng Cơm Tấm Sài Gòn | `comtam` | `?` |

## Kiểm thử

Chạy toàn bộ test:

```bash
pytest
```

Hoặc chạy test trong thư mục ứng dụng:

```bash
pytest app/test -q
```

## Cấu trúc project

```text
app/
|-- auth/
|-- browse/
|-- cart/
|-- restaurant/
|-- admin/
|-- ai/
|-- templates/
|-- static/
`-- test/

migrations/
seed.py
requirements.txt
render.sh
run.py
```

## Triển khai

Project hỗ trợ deploy trên Render. Production sử dụng MySQL bên ngoài và cần cấu
hình `DATABASE_URL`, `SECRET_KEY`, `APP_BASE_URL` cùng các key dịch vụ cần dùng.
Script `render.sh` chạy migration trước khi khởi động Gunicorn.

Thiết lập cơ bản trên Render:

```text
Build Command: pip install -r requirements.txt
Start Command: sh render.sh
Health Check Path: /health
```

## Thành viên

| Thành viên | Vai trò |
|---|---|
| Trần Văn Trạng | Trưởng nhóm |
| Phạm Tuấn Anh | Thành viên |
| Phạm Tấn Thành | Thành viên |
