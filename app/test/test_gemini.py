import json
from types import SimpleNamespace

import pytest

from app.ai import gemini


class FakeModels:
    def __init__(self, text):
        self.text = text
        self.call = None

    def generate_content(self, **kwargs):
        self.call = kwargs
        return SimpleNamespace(text=self.text)


def test_analyze_sentiment_uses_structured_gemini_response(monkeypatch):
    models = FakeModels(json.dumps({'label': 'POSITIVE', 'score': 0.85}))
    monkeypatch.setattr(gemini, 'get_client', lambda: SimpleNamespace(models=models))
    monkeypatch.delenv('GEMINI_MODEL', raising=False)

    result = gemini.analyze_sentiment('Món ăn rất ngon')

    assert result == ('POSITIVE', 0.85)
    assert models.call['config'].response_mime_type == 'application/json'


def test_analyze_sentiment_clamps_score(monkeypatch):
    models = FakeModels(json.dumps({'label': 'negative', 'score': -2}))
    monkeypatch.setattr(gemini, 'get_client', lambda: SimpleNamespace(models=models))

    assert gemini.analyze_sentiment('Quá tệ') == ('NEGATIVE', -1.0)


def test_analyze_sentiment_rejects_invalid_comment():
    with pytest.raises(ValueError, match='1 đến 1000'):
        gemini.analyze_sentiment('')


def test_analyze_sentiment_rejects_empty_response(monkeypatch):
    models = FakeModels(None)
    monkeypatch.setattr(gemini, 'get_client', lambda: SimpleNamespace(models=models))

    with pytest.raises(RuntimeError, match='không trả về kết quả'):
        gemini.analyze_sentiment('Bình thường')


def test_get_client_requires_api_key(monkeypatch):
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)

    with pytest.raises(RuntimeError, match='GEMINI_API_KEY'):
        gemini.get_client()
