"""Bounce detection and tracking for both CRM and RE pipeline"""
import json
import re
import smtplib
from email.mime.text import MIMEText
from email.utils import parseaddr
from datetime import datetime

# Bounce keywords for subject and body
BOUNCE_SUBJECT_KEYWORDS = [
    "bounce", "undeliverable", "delivery failed", "mail delivery",
    "delivery status notification", "failure notice", "returned mail",
    "could not deliver", "message not delivered", "recipient address rejected"
]

BOUNCE_FROM_PATTERNS = [
    "postmaster", "mailer-daemon", "noreply", "no-reply",
    "mail delivery subsystem", "mailer-daemon"
]

def is_bounce_email(from_email, subject, body=""):
    """Check if an email is a bounce notification."""
    from_lower = (from_email or "").lower()
    subject_lower = (subject or "").lower()
    body_lower = (body or "").lower()

    # Check sender
    for pattern in BOUNCE_FROM_PATTERNS:
        if pattern in from_lower:
            return True

    # Check subject
    for kw in BOUNCE_SUBJECT_KEYWORDS:
        if kw in subject_lower:
            return True

    # Check body
    for kw in BOUNCE_SUBJECT_KEYWORDS:
        if kw in body_lower:
            return True

    return False

def send_email_with_bounce_check(to_email, subject, body, smtp_config, from_email=None):
    """
    Send email and track bounces.
    Returns: {"sent": True/False, "bounced": True/False, "error": str}
    """
    result = {"sent": False, "bounced": False, "error": ""}

    if not smtp_config:
        result["error"] = "No SMTP config"
        return result

    try:
        if not from_email:
            from_email = smtp_config.get("user", "sajib@nanosoft.agency")

        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject.replace("\n", " ").strip()
        msg["From"] = f"SaJib Shikder <{from_email}>"
        msg["To"] = to_email

        with smtplib.SMTP(smtp_config["host"], smtp_config["port"]) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_config["user"], smtp_config["password"])
            server.send_message(msg)

        result["sent"] = True
        return result

    except smtplib.SMTPRecipientsRefused as e:
        result["error"] = f"Recipient refused: {e}"
        result["bounced"] = True
        return result
    except smtplib.SMTPDataError as e:
        result["error"] = f"Data error (possible bounce): {e}"
        result["bounced"] = True
        return result
    except smtplib.SMTPServerDisconnected as e:
        result["error"] = f"Server disconnected: {e}"
        return result
    except smtplib.SMTPException as e:
        err_str = str(e).lower()
        if any(kw in err_str for kw in ["bounce", "reject", "refused", "invalid", "undeliverable"]):
            result["bounced"] = True
        result["error"] = str(e)
        return result
    except Exception as e:
        result["error"] = str(e)
        return result

def check_crm_bounces(crm_data, reply_log_path="/home/ubuntu/nanosoft/replies_wl.jsonl"):
    """
    Scan CRM reply log for bounces and return list of bounced leads.
    Each entry: {"company": str, "email": str, "bounce_reason": str}
    """
    bounces = []
    if not os.path.exists(reply_log_path):
        return bounces

    with open(reply_log_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
                from_email = r.get("from_email", "")
                subject = r.get("reply_subject", "")
                body = r.get("reply_body", r.get("reply_snippet", ""))

                if is_bounce_email(from_email, subject, body):
                    bounces.append({
                        "company": r.get("company", ""),
                        "email": r.get("to_email", r.get("from_email", "")),
                        "template": r.get("template", ""),
                        "bounce_subject": subject[:200],
                        "from": from_email,
                    })
            except json.JSONDecodeError:
                continue

    return bounces

def update_crm_bounce_status(crm, bounced_emails):
    """Update CRM sheet to mark bounced emails with 'Bounced' status."""
    updated = 0
    for email in bounced_emails:
        try:
            # Find the row with this email in the WL tab
            cell = crm.wl_sheet.find(email, in_column=7)  # Email is col 7
            if cell:
                row = cell.row
                # Update status to Bounced (col 19)
                crm.wl_sheet.update_cell(row, 19, "Bounced")
                updated += 1
        except Exception:
            continue
    return updated

# Add missing import
import os
