#!/usr/bin/python3
"""
Send all Gmail drafts via Gmail API with configurable delay.
Deletes draft after sending. Updates CRM status to 'Email Sent'.
"""
import json, os, sys, re, time, base64
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
LOG_FILE = os.path.join(NANOSOFT_DIR, "send_via_api.log")
SENT_LOG = os.path.join(NANOSOFT_DIR, "emails_sent.jsonl")
DELAY = 180  # 3 minutes

sys.path.insert(0, NANOSOFT_DIR)
from crm import get_crm

def log(msg):
    ts = datetime.now(BD_TZ).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def get_service():
    with open(os.path.join(NANOSOFT_DIR, "gmail_token.json")) as f:
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
        with open(os.path.join(NANOSOFT_DIR, "gmail_token.json"), "w") as f:
            json.dump(token_data, f)
    return build("gmail", "v1", credentials=creds)

def send_draft(service, draft_id):
    """Send a draft message via Gmail API. Returns True on success."""
    # Get the draft
    draft = service.users().drafts().get(userId="me", id=draft_id, format="full").execute()
    msg = draft.get("message", {})
    raw = msg.get("raw")
    
    if not raw:
        # Reconstruct from parts
        headers = msg.get("payload", {}).get("headers", [])
        to_addr = next((h["value"] for h in headers if h["name"].lower() == "to"), "")
        from_addr = next((h["value"] for h in headers if h["name"].lower() == "from"), "nanosoftagency007@gmail.com")
        subject = next((h["value"] for h in headers if h["name"].lower() == "subject"), "")
        
        body = ""
        parts = msg.get("payload", {}).get("parts", [])
        if parts:
            for part in parts:
                if part.get("mimeType") == "text/plain":
                    body = base64.urlsafe_b64decode(part["body"].get("data", "")).decode("utf-8", errors="replace")
        elif msg.get("payload", {}).get("body", {}).get("data"):
            body = base64.urlsafe_b64decode(msg["payload"]["body"]["data"]).decode("utf-8", errors="replace")
        
        from email.mime.text import MIMEText
        mime_msg = MIMEText(body)
        mime_msg["to"] = to_addr
        mime_msg["from"] = from_addr
        mime_msg["subject"] = subject
        raw = base64.urlsafe_b64encode(mime_msg.as_string().encode()).decode()
    
    # Send
    result = service.users().messages().send(userId="me", body={"raw": raw}).execute()
    return result.get("id")

def main():
    log("=" * 60)
    log(f"SEND ALL DRAFTS via Gmail API | Delay: {DELAY}s")
    log("=" * 60)
    
    service = get_service()
    crm = get_crm()
    
    # Load sent log to avoid duplicates
    sent_emails = set()
    try:
        with open(SENT_LOG) as f:
            for line in f:
                if line.strip():
                    sent_emails.add(json.loads(line).get("to", ""))
    except:
        pass
    
    # Get all drafts
    all_drafts = []
    page_token = None
    while True:
        kwargs = {"userId": "me", "maxResults": 100}
        if page_token:
            kwargs["pageToken"] = page_token
        results = service.users().drafts().list(**kwargs).execute()
        drafts = results.get("drafts", [])
        all_drafts.extend(drafts)
        page_token = results.get("nextPageToken")
        if not page_token:
            break
    
    log(f"Total drafts in Gmail: {len(all_drafts)}")
    
    # Filter out already-sent
    to_send = []
    skipped = []
    for d in all_drafts:
        draft = service.users().drafts().get(userId="me", id=d["id"], format="full").execute()
        msg = draft.get("message", {})
        headers = msg.get("payload", {}).get("headers", [])
        to_addr = next((h["value"] for h in headers if h["name"].lower() == "to"), "")
        subject = next((h["value"] for h in headers if h["name"].lower() == "subject"), "")
        
        if to_addr.lower() in sent_emails:
            skipped.append(f"{to_addr} | {subject}")
        else:
            to_send.append({
                "draft_id": d["id"],
                "to": to_addr,
                "subject": subject,
            })
    
    log(f"Already sent (skip): {len(skipped)}")
    for s in skipped:
        log(f"  SKIP: {s}")
    log(f"To send: {len(to_send)}")
    
    if not to_send:
        log("Nothing to send. All done.")
        return
    
    # Estimate total time
    total_min = (len(to_send) * DELAY) / 60
    eta = datetime.now(BD_TZ) + timedelta(minutes=total_min)
    log(f"Estimated time: {total_min:.0f} min | ETA: {eta.strftime('%H:%M')}")
    log("-" * 60)
    
    ok = 0
    fail = 0
    fail_details = []
    
    for i, item in enumerate(to_send):
        to_addr = item["to"]
        subject = item["subject"]
        draft_id = item["draft_id"]
        
        log(f"[{i+1}/{len(to_send)}] Sending to {to_addr} | {subject}")
        
        try:
            msg_id = send_draft(service, draft_id)
            
            if msg_id:
                # Delete the draft
                try:
                    service.users().drafts().delete(userId="me", id=draft_id).execute()
                except:
                    pass
                
                # Log sent
                with open(SENT_LOG, "a") as f:
                    f.write(json.dumps({
                        "to": to_addr,
                        "subject": subject,
                        "sent_at": datetime.now(BD_TZ).isoformat(),
                        "message_id": msg_id,
                    }) + "\n")
                
                sent_emails.add(to_addr.lower())
                
                # Update CRM
                # Find lead by email
                all_leads = crm.get_all_leads()
                for lead in all_leads:
                    if lead.get("Owner Email", "").strip().lower() == to_addr.lower():
                        crm.update_lead(lead.get("Company Name", ""), {"Status": "Email Sent"})
                        crm.update_lead(lead.get("Company Name", ""), {
                            "Email sent date": datetime.now(BD_TZ).strftime("%Y-%m-%d")
                        })
                        break
                
                ok += 1
                log(f"  OK (msg: {msg_id})")
            else:
                fail += 1
                fail_details.append(f"{to_addr}: no message ID")
                log(f"  FAIL: no message ID")
                
        except Exception as e:
            error_str = str(e)
            # Check for rate limit
            if "rate" in error_str.lower() or "quota" in error_str.lower():
                log(f"  RATE LIMIT: {error_str}")
                log("  Waiting 60s then retrying...")
                time.sleep(60)
                try:
                    msg_id = send_draft(service, draft_id)
                    if msg_id:
                        ok += 1
                        log(f"  OK after retry (msg: {msg_id})")
                        continue
                except Exception as e2:
                    error_str = str(e2)
            
            fail += 1
            fail_details.append(f"{to_addr}: {error_str[:100]}")
            log(f"  FAIL: {error_str[:200]}")
        
        # Wait between sends (skip wait on last one)
        if i < len(to_send) - 1:
            remaining = len(to_send) - i - 1
            next_eta = datetime.now(BD_TZ) + timedelta(seconds=DELAY * remaining)
            log(f"  Waiting {DELAY}s... ({remaining} left, ETA {next_eta.strftime('%H:%M')})")
            time.sleep(DELAY)
            
            # Refresh token periodically
            if (i + 1) % 10 == 0:
                try:
                    service = get_service()
                    log("  [token refreshed]")
                except:
                    pass
    
    log("=" * 60)
    log(f"[DONE] {ok} sent, {fail} failed out of {len(to_send)}")
    if fail_details:
        log("Failures:")
        for f in fail_details:
            log(f"  - {f}")
    log("=" * 60)

if __name__ == "__main__":
    main()
