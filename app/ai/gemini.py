import json
import os

from google import genai
from google.genai import types


def _api_key():
    return os.getenv('GEMINI_API_KEY', '').strip()


def is_configured():
    return bool(_api_key() and not _api_key().startswith('your_'))


def get_client():
    if not is_configured():
        raise RuntimeError('Chưa cấu hình GEMINI_API_KEY')

    return genai.Client(api_key=_api_key())


def analyze_sentiment(comment):
    """Trả về (label, score), score trong [-1, 1]."""
    comment = (comment or '').strip()

    if not comment or len(comment) > 1000:
        raise ValueError('Bình luận phải có từ 1 đến 1000 ký tự')

    client = get_client()
    prompt = (
        'Phân tích cảm xúc của bình luận đánh giá món ăn tiếng Việt sau. '
        'Trả về label là POSITIVE, NEUTRAL hoặc NEGATIVE và score từ -1 đến 1.\n\n'
        f'Bình luận: {comment}'
    )

    response = client.models.generate_content(
        model=os.getenv('GEMINI_MODEL', 'gemini-3.6-flash').strip()
        or 'gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type='application/json',
            response_schema={
                'type': 'object',
                'properties': {
                    'label': {
                        'type': 'string',
                        'enum': ['POSITIVE', 'NEUTRAL', 'NEGATIVE'],
                    },
                    'score': {'type': 'number'},
                },
                'required': ['label', 'score'],
            },
        ),
    )

    if not response.text:
        raise RuntimeError('Gemini không trả về kết quả')

    data = json.loads(response.text)
    label = data['label'].upper()
    score = float(data['score'])

    return label, max(-1.0, min(1.0, score))
