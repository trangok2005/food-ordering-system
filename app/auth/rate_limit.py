import threading
import time


class LoginRateLimiter:
    """Giới hạn số lần thử đăng nhập theo cặp (IP, username).

    Mục đích: chặn dò mật khẩu tự động. Lưu trong bộ nhớ của tiến trình
    (đủ cho demo/deploy 1 tiến trình); tài khoản bị khóa lâu hơn vẫn do
    User.failed_login_count / locked_until xử lý trong DB.
    """

    def __init__(self, max_attempts=10, window_seconds=300):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts = {}
        self._lock = threading.Lock()

    def _key(self, ip, username):
        return f'{ip}|{(username or "").strip().lower()}'

    def _prune(self, now):
        expired = [k for k, hits in self._attempts.items()
                   if now - hits[-1] > self.window_seconds]
        for k in expired:
            del self._attempts[k]

    def is_blocked(self, ip, username):
        with self._lock:
            now = time.monotonic()
            self._prune(now)
            hits = self._attempts.get(self._key(ip, username), [])
            return len(hits) >= self.max_attempts

    def record_failure(self, ip, username):
        with self._lock:
            key = self._key(ip, username)
            now = time.monotonic()
            hits = [t for t in self._attempts.get(key, [])
                    if now - t <= self.window_seconds]
            hits.append(now)
            self._attempts[key] = hits

    def reset(self, ip, username):
        with self._lock:
            self._attempts.pop(self._key(ip, username), None)


login_rate_limiter = LoginRateLimiter()
