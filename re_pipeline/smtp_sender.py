"""Email sender with SMTP — uses Gmail app password for nanosoftagency007@gmail.com"""
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "nanosoftagency007@gmail.com"
SMTP_PASS = "wgxo ddup cdol kupl"

def send_email(to_email, subject, body, from_name="SaJib Shikder", from_email="nanosoftagency007@gmail.com"):
    """Send email via Gmail SMTP. Returns (success, error_msg)."""
    try:
        msg = MIMEMultipart()
        msg["From"] = f"{from_name} <{from_email}>"
        msg["To"] = to_email
        msg["Subject"] = subject.replace("\n", " ").strip()
        msg.attach(MIMEText(body, "plain", "utf-8"))

        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)

        print(f"[SENT] {subject[:50]} -> {to_email}")
        return True, ""
    except smtplib.SMTPAuthenticationError as e:
        err = f"Auth failed: {e}"
        print(f"[FAIL] {err}")
        return False, err
    except smtplib.SMTPRecipientsRefused as e:
        err = f"Recipient refused (bounce): {e}"
        print(f"[BOUNCE] {to_email}: {err}")
        return False, err
    except smtplib.SMTPDataError as e:
        err = f"Data error (possible bounce): {e}"
        print(f"[BOUNCE] {to_email}: {err}")
        return False, err
    except smtplib.SMTPException as e:
        err = f"SMTP error: {e}"
        print(f"[FAIL] {to_email}: {err}")
        return False, err
    except Exception as e:
        err = f"Error: {e}"
        print(f"[FAIL] {to_email}: {err}")
        return False, err

def verify_connection():
    """Test SMTP connection."""
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)
        print("SMTP connection OK")
        return True
    except Exception as e:
        print(f"SMTP connection FAILED: {e}")
        return False
