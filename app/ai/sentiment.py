from app.ai import gemini

# Các nhãn cảm xúc được hệ thống hỗ trợ.
POSITIVE = 'POSITIVE'
NEUTRAL = 'NEUTRAL'
NEGATIVE = 'NEGATIVE'

VALID_LABELS = {
    POSITIVE,
    NEUTRAL,
    NEGATIVE,
}

# Khoảng điểm cảm xúc hợp lệ.
MIN_SCORE = -1.0
MAX_SCORE = 1.0


def normalize_label(label):
    """
    Chuẩn hóa nhãn cảm xúc.

    Ví dụ:
        'positive' -> 'POSITIVE'
        ' Positive ' -> 'POSITIVE'

    Args:
        label: Nhãn cảm xúc.

    Returns:
        str: POSITIVE | NEUTRAL | NEGATIVE

    Raises:
        ValueError: Nếu nhãn không hợp lệ.
    """

    normalized = str(
        label or ''
    ).strip().upper()

    if normalized not in VALID_LABELS:
        raise ValueError(
            'Nhãn cảm xúc không hợp lệ'
        )

    return normalized


def normalize_score(score):
    """
    Chuẩn hóa score về khoảng [-1, 1].

    Nếu Gemini trả giá trị vượt phạm vi:
        1.5  -> 1.0
       -1.5  -> -1.0

    Args:
        score: Điểm cảm xúc.

    Returns:
        float: Score trong [-1, 1].

    Raises:
        ValueError: Nếu score không phải số.
    """

    try:
        score = float(score)

    except (TypeError, ValueError) as error:
        raise ValueError(
            'Điểm cảm xúc không hợp lệ'
        ) from error

    return max(
        MIN_SCORE,
        min(MAX_SCORE, score)
    )


def analyze_sentiment(comment):
    """
    Phân tích cảm xúc của bình luận.

    Hàm này sử dụng Gemini hiện có trong gemini.py.
    Không trực tiếp gọi HTTP API.

    Args:
        comment: Nội dung bình luận của khách hàng.

    Returns:
        tuple:
            (label, score)

        Ví dụ:
            ('POSITIVE', 0.85)

    Raises:
        ValueError:
            Nếu bình luận hoặc kết quả không hợp lệ.

        RuntimeError:
            Nếu Gemini API gặp lỗi.
    """


    comment = (comment or '').strip()

    if not comment:
        raise ValueError(
            'Bình luận không được để trống'
        )


    label, score = gemini.analyze_sentiment(
        comment
    )


    label = normalize_label(label)

    score = normalize_score(score)

    return label, score


def is_positive(label):
    """
    Kiểm tra label có phải cảm xúc tích cực hay không.
    """

    return normalize_label(label) == POSITIVE


def is_neutral(label):
    """
    Kiểm tra label có phải cảm xúc trung lập hay không.
    """

    return normalize_label(label) == NEUTRAL


def is_negative(label):
    """
    Kiểm tra label có phải cảm xúc tiêu cực hay không.
    """

    return normalize_label(label) == NEGATIVE

def score_to_text(score):
    """
    Chuyển score thành mô tả tiếng Việt.

    Quy ước:

        >= 0.7   -> Rất tích cực
        >= 0.3   -> Tích cực
        > -0.3   -> Trung lập
        > -0.7   -> Tiêu cực
        <= -0.7  -> Rất tiêu cực
    """

    score = normalize_score(score)

    if score >= 0.7:
        return 'Rất tích cực'

    if score >= 0.3:
        return 'Tích cực'

    if score > -0.3:
        return 'Trung lập'

    if score > -0.7:
        return 'Tiêu cực'

    return 'Rất tiêu cực'