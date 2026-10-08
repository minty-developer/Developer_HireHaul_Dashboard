from __future__ import annotations

import smtplib
from email.message import EmailMessage


def send_email(config, recipient: str, subject: str, body: str) -> None:
    if not config.get("SMTP_HOST"):
        raise RuntimeError("SMTP_HOST가 설정되지 않았습니다.")

    message = EmailMessage()
    message["From"] = config["MAIL_FROM"]
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    smtp_class = smtplib.SMTP_SSL if config["SMTP_USE_SSL"] else smtplib.SMTP
    with smtp_class(config["SMTP_HOST"], config["SMTP_PORT"], timeout=10) as smtp:
        if config["SMTP_USE_TLS"] and not config["SMTP_USE_SSL"]:
            smtp.starttls()
        if config.get("SMTP_USERNAME"):
            smtp.login(config["SMTP_USERNAME"], config["SMTP_PASSWORD"])
        smtp.send_message(message)
