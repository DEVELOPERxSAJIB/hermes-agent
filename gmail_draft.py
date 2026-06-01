"""
Gmail Draft via IMAP — Saves drafts to Gmail Drafts folder.
Most reliable method, works with app passwords.
"""
import imaplib
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import time

SMTP_USER = "nanosoftagency007@gmail.com"
SMTP_PASS = os.environ.get("SMTP_PASS", "wnvp mpne dyvu dheq")
IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993


def save_draft_to_gmail(to_email, subject, body, company=""):
    """Save an email as a draft in Gmail via IMAP."""
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_USER
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        # Connect to Gmail IMAP
        mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        mail.login(SMTP_USER, SMTP_PASS)
        
        # Append to Drafts folder
        # Gmail's drafts folder is called "[Gmail]/Drafts"
        draft_folder = '"[Gmail]/Drafts"'
        
        # Set the \Draft flag
        msg_str = msg.as_string()
        
        result = mail.append(draft_folder, '\\Draft', imaplib.Time2Internaldate(time.time()), msg_str.encode('utf-8'))
        mail.logout()
        
        if result[0] == 'OK':
            return True
        else:
            print(f"[GMAIL IMAP] Append failed: {result}")
            return False
    except Exception as e:
        print(f"[GMAIL IMAP] Error: {e}")
        return False


def create_draft(to_email, subject, body):
    """Alias for compatibility."""
    return save_draft_to_gmail(to_email, subject, body)
