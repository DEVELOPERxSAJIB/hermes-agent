#!/usr/bin/env python3
"""
NanoSoft QUILL-WL — Reply Monitor
Checks Gmail inbox for replies to sent outreach emails.
Updates CRM: Reply Status, Reply Date, Reply Snippet.

Run every 30-60 minutes via cron.
"""
import json, os, re, sys, time
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
SENT_LOG = os.path.join(NANOSOFT_DIR, "emails_sent_wl.jsonl")
REPLY_LOG = os.path.join(NANOSOFT_DIR, "replies_wl.jsonl")
TOKEN_FILE = os.path.join(NANOSOFT_DIR, "gmail_token.json")

sys.path.insert(0, NANOSOFT_DIR)

def log(msg):
    ts = datetime.now(BD_TZ).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [REPLY-MONITOR] {msg}"
    print(line, flush=True)
    with open(os.path.join(NANOSOFT_DIR, "quill_wl.log"), 'a') as f:
        f.write(line + "\n")

def get_gmail_service():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    with open(TOKEN_FILE) as f:
        token_data = json.load(f)

    creds = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=token_data.get("client_id"),
        client_secret=token_data.get("client_secret"),
        scopes=token_data.get("scopes"),
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_data["token"] = creds.token
        with open(TOKEN_FILE, "w") as f:
            json.dump(token_data, f)

    return build("gmail", "v1", credentials=creds)

def get_sent_map():
    """Build map of sender_email -> {company, template, subject, sent_at}"""
    sent = {}
    try:
        with open(SENT_LOG) as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    email = entry.get("to", "").lower().strip()
                    if email:
                        sent[email] = entry
    except:
        pass
    return sent

def get_replied_set():
    """Get set of emails that already have replies logged."""
    replied = set()
    try:
        with open(REPLY_LOG) as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    replied.add(entry.get("from_email", "").lower().strip())
    except:
        pass
    return replied

def extract_snippet(body, max_chars=200):
    """Extract first meaningful line from reply body."""
    # Remove quoted lines (starting with >)
    lines = body.split('\n')
    clean = []
    for line in lines:
        if line.strip().startswith('>'):
            continue
        if line.strip() and len(line.strip()) > 3:
            clean.append(line.strip())
        if len(clean) >= 3:
            break
    snippet = ' '.join(clean)[:max_chars]
    return snippet

def classify_reply(snippet):
    """Simple classification of reply intent."""
    s = snippet.lower()
    if any(w in s for w in ['not interested', 'no thanks', 'unsubscribe', 'remove me', 'stop', 'wrong person']):
        return 'Not Interested'
    if any(w in s for w in ['interested', 'tell me more', 'sounds good', 'let\'s talk', 'call me', 'schedule', 'book a', 'send me', 'proposal', 'pricing', 'cost', 'rate']):
        return 'Interested'
    if any(w in s for w in ['wrong person', 'not the right', 'who is', 'what is this', 'how did you']):
        return 'Confused'
    if any(w in s for w in ['out of office', 'ooo', 'on leave', 'auto-reply', 'automatic reply']):
        return 'Auto-Reply'
    return 'Other'

def main():
    log("Starting reply check...")

    try:
        service = get_gmail_service()
    except Exception as e:
        log(f"Cannot connect to Gmail: {e}")
        return

    sent_map = get_sent_map()
    replied_set = get_replied_set()

    if not sent_map:
        log("No sent emails found. Nothing to check.")
        return

    log(f"Tracking {len(sent_map)} sent emails, {len(replied_set)} already replied")

    # Search for replies in inbox from our sent-to addresses
    # Query: newer_than:14d (covers full sequence window)
    try:
        results = service.users().messages().list(
            userId='me',
            q='newer_than:14d in:inbox',
            maxResults=100
        ).execute()
    except Exception as e:
        log(f"Gmail list error: {e}")
        return

    messages = results.get('messages', [])
    log(f"Found {len(messages)} recent inbox messages to scan")

    new_replies = 0

    for msg_ref in messages:
        try:
            msg = service.users().messages().get(
                userId='me', id=msg_ref['id'], format='metadata',
                metadataHeaders=['From', 'Subject', 'Date', 'In-Reply-To', 'References']
            ).execute()
        except:
            continue

        headers = {h['name'].lower(): h['value'] for h in msg.get('payload', {}).get('headers', [])}

        from_header = headers.get('from', '')
        # Extract email from "Name <email@domain.com>"
        email_match = re.search(r'<([^>]+)>', from_header)
        sender_email = email_match.group(1).lower() if email_match else from_header.lower().strip()

        # Check if this sender is someone we emailed
        if sender_email not in sent_map:
            continue

        # Skip if already logged
        if sender_email in replied_set:
            continue

        sent_info = sent_map[sender_email]
        subject = headers.get('subject', '')
        date_str = headers.get('date', '')

        # Get snippet from body
        try:
            full_msg = service.users().messages().get(
                userId='me', id=msg_ref['id'], format='full'
            ).execute()
            body_data = full_msg.get('payload', {}).get('body', {})
            body_text = ''
            if body_data.get('data'):
                import base64
                body_text = base64.urlsafe_b64decode(body_data['data']).decode('utf-8', errors='ignore')
            elif full_msg.get('payload', {}).get('parts'):
                for part in full_msg['payload']['parts']:
                    if part.get('mimeType') == 'text/plain' and part.get('body', {}).get('data'):
                        import base64
                        body_text = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                        break
        except:
            body_text = ''

        snippet = extract_snippet(body_text)
        classification = classify_reply(snippet)

        reply_entry = {
            "from_email": sender_email,
            "from_name": from_header,
            "company": sent_info.get("company", ""),
            "template": sent_info.get("template", ""),
            "original_subject": sent_info.get("subject", ""),
            "reply_subject": subject,
            "reply_date": date_str,
            "snippet": snippet,
            "classification": classification,
            "detected_at": datetime.now(BD_TZ).isoformat(),
            "message_id": msg_ref['id'],
        }

        with open(REPLY_LOG, 'a') as f:
            f.write(json.dumps(reply_entry) + "\n")

        replied_set.add(sender_email)
        new_replies += 1

        log(f"  REPLY: {sent_info.get('company','?')} | {classification} | {snippet[:80]}")

        # Update CRM
        try:
            from crm import get_crm
            crm = get_crm()
            crm.update_wl_lead(sent_info.get('company', ''), {
                "Reply Status": classification,
                "Reply Date": datetime.now(BD_TZ).strftime("%Y-%m-%d"),
                "Reply Snippet": snippet[:150],
            })
            log(f"    CRM updated: {sent_info.get('company','?')} -> {classification}")
        except Exception as e:
            log(f"    CRM update failed: {e}")

    log(f"Done. {new_replies} new replies found and logged.")

if __name__ == "__main__":
    main()
