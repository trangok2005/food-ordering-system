import json
import os
import re
import time

import requests


GEMINI_BASE_URL = 'https://generativelanguage.googleapis.com/v1beta'


def _api_key():
    return os.getenv('GEMINI_API_KEY', '').strip()


def is_configured():
    # Key giữ "your_" là key mẫu, chưa thật sự cấu hình.
    return bool(_api_key() and not _api_key().startswith('your_'))


def analyze_sentiment(comment):
    """Gọi Gemini phân tích cảm xúc của bình luận đánh giá món ăn.

    Trả về (label, score), label là 'POSITIVE' | 'NEUTRAL' |
    'NEGATIVE', score nằm trong [-1, 1].
    """
    if not is_configured():
        raise RuntimeError('Chưa cấu hình GEMINI_API_KEY')

    # Yêu cầu Gemini trả về đúng 1 chuỗi JSON để dễ parse.
    prompt = (
        'Phân tích cảm xúc của bình luận đánh giá món ăn tiếng Việt '
        'dưới đây. Chỉ trả về JSON đúng định dạng: '
        '{"label": "POSITIVE"|"NEUTRAL"|"NEGATIVE", "score": số thực trong [-1, 1]}.\n\n'
        f'Bình luận: "{comment}"'
    )

    model = os.getenv('GEMINI_MODEL', 'gemini-3.6-flash')

    url = f'{GEMINI_BASE_URL}/models/{model}:generateContent'
    payload = {
        'contents': [{
            'parts': [{'text': prompt}]
        }]
    }

    # Gemini đôi khi quá tải (timeout/5xx) nên thử lại vài lần,
    # chờ dần dần giữa các lần để không dập server.
    last_error = None
    for attempt in range(3):
        try:
            resp = requests.post(
                url,
                params={'key': _api_key()},
                json=payload,
                timeout=45,
            )
            resp.raise_for_status()

            text = (
                resp
                .json()
                .get('candidates', [{}])[0]
                .get('content', {})
                .get('parts', [{}])[0]
                .get('text', '')
            )
            return _parse_response(text)

        except (requests.Timeout, requests.ConnectionError) as e:
            last_error = e
        except requests.HTTPError as e:
            # Lỗi 5xx là lỗi phía server, thử lại được;
            # 4xx là lỗi do ta gửi sai -> báo luôn.
            if resp.status_code < 500:
                raise RuntimeError(f'Gemini API lỗi: {e}')
            last_error = e

        if attempt < 2:
            time.sleep(2 * (attempt + 1))

    raise RuntimeError(f'Gemini API không phản hồi sau 3 lần thử: {last_error}')


def _parse_response(text):
    """Bóc label/score từ chuỗi JSON Gemini trả về."""
    # Gemini hay bọc thêm văn bản quanh JSON, nên chỉ lấy
    # đoạn {...} đầu tiên rồi parse.
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if not match:
        raise ValueError('Gemini không trả về JSON hợp lệ')

    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        raise ValueError('Gemini trả về JSON không parse được')

    label = str(data.get('label', '')).upper()
    score = float(data.get('score', 0))

    if label not in ('POSITIVE', 'NEUTRAL', 'NEGATIVE'):
        raise ValueError('Nhãn cảm xúc không hợp lệ')

    # Giới hạn score trong [-1, 1] phòng Gemini trả quá ngưỡng.
    return label, max(-1.0, min(1.0, score))