import os
import smtplib
import ssl
from email.message import EmailMessage


class MailDeliveryError(RuntimeError):
    pass


def send_password_reset(recipient, reset_url):
    host = os.getenv('SMTP_HOST', '').strip()
    sender = os.getenv('SMTP_FROM', '').strip()
    if not host or not sender:
        raise MailDeliveryError('Password reset email is not configured')

    try:
        port = int(os.getenv('SMTP_PORT', '587'))
    except ValueError as exc:
        raise MailDeliveryError('SMTP_PORT is invalid') from exc

    message = EmailMessage()
    message['Subject'] = 'Đặt lại mật khẩu TvT-food'
    message['From'] = sender
    message['To'] = recipient
    message.set_content(
        'Bạn đã yêu cầu đặt lại mật khẩu. Link này có hiệu lực 30 phút '
        f'và chỉ dùng một lần:\n\n{reset_url}\n\n'
        'Nếu bạn không thực hiện yêu cầu này, hãy bỏ qua email.'
    )

    username = os.getenv('SMTP_USERNAME', '').strip()
    password = os.getenv('SMTP_PASSWORD', '')
    use_ssl = os.getenv('SMTP_USE_SSL', '').lower() in {'1', 'true', 'yes'}

    smtp_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    with smtp_class(host, port, timeout=15) as smtp:
        if not use_ssl:
            smtp.starttls(context=ssl.create_default_context())
        if username:
            smtp.login(username, password)
        smtp.send_message(message)
