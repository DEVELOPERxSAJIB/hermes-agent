"""
Gmail Inbox Reader — checks for bounce-back emails
Uses IMAP to read Gmail and detect delivery failures.
"""
import imaplib
import email
import re
import sys
from email.header import decode_header
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))

def connect_gmail():
    """Connect to Gmail IMAP."""
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login("nanosoftagency007@gmail.com", "wgxo ddup cdol kupl")
    mail.select("INBOX")
    return mail

def fetch_recent_bounces(hours=48):
    """
    Fetch bounce-back emails from the last N hours.
    List of bounced recipient emails.
    """
    bounced_emails = []
    try:
        mail = connect_gmail()
        # Search for emails with bounce-related subjects
        since_date = (datetime.now() - __import__('datetime').timedelta(hours=hours)).strftime("%d-%b-%Y")
        
        # Search all recent emails
        status, messages = mail.search(None, f'(SINCE {since_date})')
        if status != "OK":
            mail.logout()
            return bounced_emails

        msg_ids = messages[0].split()
        print(f"Checking {len(msg_ids)} emails from last {hours}h...", file=sys.stderr)

        for msg_id in msg_ids:
            try:
                status, msg_data = mail.fetch(msg_id, "(RFC822)")
                if status != "OK":
                    continue
                    
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)
                
                # Decode subject
                subject = ""
                decoded = decode_header(msg.get("Subject", ""))
                for part, encoding in decoded:
                    if isinstance(part, bytes):
                        subject += part.decode(encoding or "utf-8", errors="replace")
                    else:
                        subject += part
                subject_lower = subject.lower()
                
                # Check if it's a bounce
                is_bounce = False
                bounce_keywords = [
                    "delivery status notification",
                    "delivery failure",
                    "mail delivery failed",
                    "undelivered mail returned",
                    "returned mail",
                    "failure notice",
                    "bounce",
                ]
                for kw in bounce_keywords:
                    if kw in subject_lower:
                        is_bounce = True
                        break
                
                if not is_bounce:
                    continue
                
                # Extract bounced email from body
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        ct = part.get_content_type()
                        if ct == "text/plain":
                            payload = part.get_payload(decode=True)
                            if payload:
                                body = payload.decode("utf-8", errors="replace")
                                break
                else:
                    payload = msg.get_payload(decode=True)
                    if payload:
                        body = payload.decode("utf-8", errors="replace")
                
                # Extract email addresses from bounce body
                found = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', body)
                for e in found:
                    e_lower = e.lower()
                    if "nanosoftagency007" not in e_lower and "mailer-daemon" not in e_lower and "google" not in e_lower:
                        bounced_emails.append(e_lower)
                        
            except Exception as ex:
                continue
        
        mail.logout()
    except Exception as ex:
        print(f"IMAP error: {ex}", file=sys.stderr)
    
    return list(set(bounced_emails))


if __name__ == "__main__":
    hours = int(sys.argv[1]) if len(sys.argv) > 1 else 48
    print(f"Checking Gmail for bounces in last {hours}h...")
    bounces = fetch_recent_bounces(hours)
    print(f"\nFound {len(bounces)} bounced emails:")
    for e in bounces:
        print(f"  {e}")
