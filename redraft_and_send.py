#!/usr/bin/env python3
"""
Delete old Gmail drafts for leads that are still 'Drafted' in CRM.
We will re-draft these with the new QUILL v12 template.
Then send all 37 good emails via Gmail API with 3-minute gaps.
"""
import json, os, sys, re, time, base64
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
DELAY = 180  # 3 minutes

sys.path.insert(0, NANOSOFT_DIR)
from crm import get_crm

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

def log(msg):
    ts = datetime.now(BD_TZ).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(os.path.join(NANOSOFT_DIR, "quill_v12_send.log"), "a") as f:
        f.write(line + "\n")

def main():
    log("=" * 60)
    log("QUILL v12: Delete old drafts + Re-draft + Send")
    log("=" * 60)
    
    crm = get_crm()
    service = get_service()
    
    # Step 1: Get all "Drafted" leads
    drafted_leads = crm.get_leads_by_status("Drafted")
    log(f"\n[1] Drafted leads in CRM: {len(drafted_leads)}")
    
    # Build set of emails we need to send
    good_emails = set()
    for lead in drafted_leads:
        email = lead.get("Owner Email", "").strip().lower()
        # Skip bad emails
        bad_patterns = [
            r'user@domain', r'example@', r'@whois\.', r'@sentry\.', r'@bytedance\.',
            r'vue@3\.', r'@scorebig\.', r'@afternic\.', r'john@doe\.', r'feedback@',
        ]
        is_bad = any(re.search(p, email, re.IGNORECASE) for p in bad_patterns)
        if email and not is_bad:
            good_emails.add(email)
    
    log(f"    Good emails: {len(good_emails)}")
    
    # Step 2: Delete old Gmail drafts for these emails
    log(f"\n[2] Checking Gmail drafts to delete old ones...")
    
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
    
    log(f"    Total Gmail drafts: {len(all_drafts)}")
    
    deleted = 0
    kept = 0
    for d in all_drafts:
        try:
            draft = service.users().drafts().get(userId="me", id=d["id"], format="full").execute()
            msg = draft.get("message", {})
            headers = msg.get("payload", {}).get("headers", [])
            to_addr = next((h["value"] for h in headers if h["name"].lower() == "to"), "")
            subject = next((h["value"] for h in headers if h["name"].lower() == "subject"), "")
            
            # Check if this draft is for a lead that needs re-drafting
            to_lower = to_addr.strip().lower()
            should_delete = False
            
            if to_lower in good_emails:
                should_delete = True
            else:
                # Check by domain match
                for email_addr in good_emails:
                    domain = email_addr.split("@")[-1] if "@" in email_addr else ""
                    if domain and (domain in subject.lower() or domain in to_lower):
                        should_delete = True
                        break
            
            if should_delete:
                service.users().drafts().delete(userId="me", id=d["id"]).execute()
                deleted += 1
                log(f"    DELETED draft: {to_addr} | {subject}")
            else:
                kept += 1
        except Exception as e:
            log(f"    Error processing draft {d['id']}: {e}")
    
    log(f"    Deleted: {deleted}, Kept: {kept}")
    
    # Step 3: Import QUILL v12 and generate new emails
    log(f"\n[3] Generating new emails with QUILL v12...")
    from quill_v12 import make_email
    
    new_drafts = []
    skipped = []
    
    for lead in drafted_leads:
        d = make_email(lead)
        if not d:
            skipped.append(f"{lead.get('Company Name','?')} | {lead.get('Owner Email','?')}")
            continue
        new_drafts.append(d)
    
    log(f"    Generated: {len(new_drafts)}, Skipped: {len(skipped)}")
    for s in skipped:
        log(f"    SKIP: {s}")
    
    # Step 4: Create Gmail drafts for the new emails
    log(f"\n[4] Creating {len(new_drafts)} Gmail drafts...")
    
    for i, d in enumerate(new_drafts):
        try:
            msg = MIMEText(d['body'])
            msg['to'] = d['to']
            msg['from'] = "nanosoftagency007@gmail.com"
            msg['subject'] = d['subject']
            msg['List-Unsubscribe'] = '<mailto:nanosoftagency007@gmail.com?subject=unsubscribe>'
            msg['List-Unsubscribe-Post'] = 'List-Unsubscribe=One-Click'
            
            raw = base64.urlsafe_b64encode(msg.as_string().encode()).decode()
            
            # Create draft
            draft = service.users().drafts().create(
                userId='me',
                body={'message': {'raw': raw}}
            ).execute()
            
            log(f"  [{i+1}/{len(new_drafts)}] DRAFTED: {d['to']} | {d['subject']} | {d['word_count']}w")
        except Exception as e:
            log(f"  [{i+1}/{len(new_drafts)}] DRAFT ERROR: {d['to']} | {e}")
    
    log(f"\n[GMAIL DRAFTS DONE] {len(new_drafts)} new drafts created in Gmail")
    log("Review them in Gmail Drafts tab before sending.")
    
    # Count total time needed
    total_min = (len(new_drafts) * DELAY) / 60
    eta = datetime.now(BD_TZ) + timedelta(minutes=total_min)
    log(f"\nTo send all {len(new_drafts)} emails:")
    log(f"  Delay: {DELAY}s ({DELAY/60:.0f} min) between each")
    log(f"  Total time: {total_min:.0f} minutes")
    log(f"  ETA: {eta.strftime('%H:%M')} BD time")
    log(f"\nRun: cd /home/ubuntu/nanosoft && python3 quill_v12.py send")

if __name__ == "__main__":
    main()
