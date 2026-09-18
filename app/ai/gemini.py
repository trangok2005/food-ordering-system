import json
import os
import re
import time

import requests


GEMINI_BASE_URL = 'https://generativelanguage.googleapis.com/v1beta'


def _api_key():
    return os.getenv('GEMINI_API_KEY', '').strip()


def is_configured():
    # Bỏ qua key mẫu trong .env.
    return bool(_api_key() and not _api_key().startswith('your_'))


def analyze_sentiment(comment):
    """Trả về (label, score) cảm xúc, với score trong [-1, 1]."""
    comment = (comment or '').strip()
    if not comment or len(comment) > 1000:
        raise ValueError('Bình luận phải có từ 1 đến 1000 ký tự')
    if not is_configured():
        raise RuntimeError('Chưa cấu hình GEMINI_API_KEY')

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

    # Thử lại khi Gemini quá tải hoặc mất kết nối.
    last_error = None
    for attempt in range(2):
        try:
            resp = requests.post(
                url,
                params={'key': _api_key()},
                json=payload,
                timeout=10,
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
            # Không thử lại với lỗi 4xx.
            if resp.status_code < 500:
                raise RuntimeError(f'Gemini API lỗi: {e}')
            last_error = e

        if attempt < 1:
            time.sleep(2 * (attempt + 1))

    raise RuntimeError(f'Gemini API không phản hồi sau 2 lần thử: {last_error}')


def _parse_response(text):
    # Gemini có thể bọc thêm văn bản quanh JSON.
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

    return label, max(-1.0, min(1.0, score))
