# Hướng dẫn triển khai (Render / PythonAnywhere)

Không dùng Docker. Hai lựa chọn phổ biến cho đồ án:

---

## Phương án A — Render (khuyến nghị, có MySQL miễn phí)

### 1. Tạo MySQL

Render Dashboard → **New + → PostgreSQL/MySQL** → chọn *MySQL Free*.
Ghi lại Host, Port, User, Password, Database.

> Lưu ý: instance free của Render **hết hạn sau 30 ngày** — trước ngày demo hãy
> tạo lại và cập nhật `.env`.

### 2. Tạo Web Service

1. Push code lên GitHub (đừng commit `.env`).
2. Render → **New + → Web Service** → kết nối repo.
3. Cấu hình:
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn run:app` (thêm `gunicorn` vào `requirements.txt`)
   - **Instance type**: Free

### 3. Khai báo Environment Variables trên Render

Thêm từng biến trong `.env.example` với giá trị thật:

```
DATABASE_USERNAME=...
DATABASE_PASSWORD=...
DATABASE_HOST=...        # host MySQL của Render, KHÔNG phải 127.0.0.1
DATABASE_PORT=3306
DATABASE_NAME=...
PAYOS_MODE=live          # bật thanh toán thật khi public
PAYOS_CLIENT_ID / PAYOS_API_KEY / PAYOS_CHECKSUM_KEY
GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET
GEMINI_API_KEY
```

### 4. Khởi tạo database lần đầu

Chạy 1 lần từ máy local trỏ thẳng tới DB của Render:

```bash
# sửa tạm .env local theo thông tin MySQL Render rồi chạy:
python seed.py
```

### 5. Cập nhật URL callback

- **payOS**: thêm webhook/return domain `https://<ten-app>.onrender.com` vào dashboard payOS.
- **Google OAuth**: thêm redirect URI `https://<ten-app>.onrender.com/auth/login/google/callback`.

> Webhook payOS hoạt động được vì app đã có domain public (localhost không nhận được webhook —
> khi đó hệ thống dùng polling tại route return_url).

---

## Phương án B — PythonAnywhere

1. Đăng ký tài khoản free → tab **Web** → *Add a new web app* → Manual configuration → Python 3.11.
2. Tab **Consoles** → mở Bash:
   ```bash
   git clone <repo> ~/food-ordering-system
   cd ~/food-ordering-system
   mkvirtualenv --python=/usr/bin/python3.11 venv
   pip install -r requirements.txt
   ```
3. Tạo file `.env` bằng nano với nội dung như phương án A.
4. MySQL: tab **Databases** tạo database + user, ghi lại hostname dạng
   `<user>.mysql.pythonanywhere-services.com`. Chạy seed:
   ```bash
   workon venv && cd ~/food-ordering-system && python seed.py
   ```
5. Tab **Web** → **WSGI configuration file**, thay phần Flask:
   ```python
   import sys
   path = '/home/<username>/food-ordering-system'
   if path not in sys.path:
       sys.path.insert(0, path)

   from run import app as application
   ```
6. Virtualenv section: trỏ tới `/home/<username>/.virtualenvs/venv`.
7. **Reload** web app.

> Gói free của PythonAnywhere chỉ cho phép ra ngoài Internet qua **proxy whitelist**.
> Vào tab Consoles → chạy lệnh để add whitelist nếu cần: API payOS (`api-merchant.payos.vn`),
> Google OAuth (`oauth2.googleapis.com`, `accounts.google.com`, `www.googleapis.com`),
> Gemini (`generativelanguage.googleapis.com`). Thiếu whitelist sẽ lỗi gọi API bên thứ ba.

---

## Checklist sau khi deploy

- [ ] Trang chủ load được, đăng nhập admin OK
- [ ] Đặt món end-to-end: giỏ → checkout → payOS trả về → đơn Pending xuất hiện
- [ ] Webhook/polling payOS xác nhận PAID đúng (test số tiền nhỏ, ví dụ 2000đ)
- [ ] Google login OK (redirect URI đã thêm domain mới)
- [ ] Gemini phân tích cảm xúc OK (hoặc fallback không crash)
- [ ] `SECRET_KEY` nên đặt biến môi trường riêng thay vì chuỗi cứng trong `app/__init__.py`
