# emailer.py
from __future__ import annotations
import os
import smtplib
from email.mime.text import MIMEText
from email.utils import formatdate

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
ALERT_TO  = os.getenv("ALERT_TO")
ALERT_FROM = os.getenv("ALERT_FROM", SMTP_USER)

def send_email(subject: str, body: str, to_addr: str | None = None) -> None:
    # no-op if email isn’t configured
    to_addr = to_addr or ALERT_TO
    if not (SMTP_USER and SMTP_PASS and to_addr):
        return

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = ALERT_FROM
    msg["To"] = to_addr
    msg["Date"] = formatdate(localtime=True)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls()
        s.login(SMTP_USER, SMTP_PASS)
        s.send_message(msg)
