#!/usr/bin/env python3
"""
Draft all 'Drafted' leads that don't already have Gmail drafts.
Matches by domain to avoid duplicates.
"""
import json, os, sys, re, base64
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

sys.path.insert(0, "/home/ubuntu/nanosoft")
from crm import get_crm

NANOSOFT_DIR = "/home/ubuntu/nanosoft"
SMTP_USER = "nanosoftagency007@gmail.com"

def get_existing_draft_domains():
    """Get domains that already have Gmail drafts."""
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
    service = build("gmail", "v1", credentials=creds)
    
    results = service.users().drafts().list(userId="me", maxResults=100).execute()
    drafts = results.get("drafts", [])
    
    domains = set()
    for d in drafts:
        try:
            draft = service.users().drafts().get(userId="me", id=d["id"], format="full").execute()
            msg = draft.get("message", {})
            parts = msg.get("payload", {}).get("parts", [])
            body = ""
            if parts:
                for part in parts:
                    if part.get("mimeType") == "text/plain":
                        body = base64.urlsafe_b64decode(part["body"].get("data", "")).decode("utf-8", errors="replace")
            elif msg.get("payload", {}).get("body", {}).get("data"):
                body = base64.urlsafe_b64decode(msg["payload"]["body"]["data"]).decode("utf-8", errors="replace")
            
            m = re.search(r'([a-z0-9-]+\.(?:com|net|org|co|us|uk|ca|au|nl|cn|io|info|biz))', body.lower())
            if m:
                domains.add(m.group(1))
        except Exception as e:
            print(f"  [WARN] Error reading draft {d['id']}: {e}")
    
    return domains


def create_gmail_draft(to_email, subject, body):
    """Create a draft in Gmail."""
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
    
    service = build("gmail", "v1", credentials=creds)
    
    msg = MIMEText(body)
    msg["to"] = to_email
    msg["from"] = SMTP_USER
    msg["subject"] = subject
    
    raw = base64.urlsafe_b64encode(msg.as_string().encode()).decode()
    
    draft = service.users().drafts().create(
        userId="me",
        body={"message": {"raw": raw}}
    ).execute()
    
    return draft.get("id")


def main():
    print("=" * 60)
    print("QUILL: Draft all missing 'Drafted' leads")
    print("=" * 60)
    
    # Step 1: Get existing draft domains
    print("\n[1] Checking existing Gmail drafts...")
    existing_domains = get_existing_draft_domains()
    print(f"    Found {len(existing_domains)} existing drafts:")
    for d in sorted(existing_domains):
        print(f"      - {d}")
    
    # Step 2: Get all 'Drafted' leads from CRM
    print("\n[2] Loading 'Drafted' leads from CRM...")
    crm = get_crm()
    all_leads = crm.get_drafted_leads()
    print(f"    Found {len(all_leads)} leads with 'Drafted' status")
    
    # Step 3: Filter out leads that already have drafts
    needs_draft = []
    skipped = []
    no_email = []
    
    for lead in all_leads:
        email = lead.get("Owner Email", "").strip()
        website = lead.get("Website", "").strip()
        
        if not email:
            no_email.append(lead.get("Company Name", "?"))
            continue
        
        domain = re.sub(r'^https?://(www\.)?', '', website).split('/')[0].lower()
        
        # Check if domain already has a draft
        domain_match = False
        for existing in existing_domains:
            if existing in domain or domain in existing:
                domain_match = True
                break
        
        if domain_match:
            skipped.append(f"{lead.get('Company Name', '?')} ({domain})")
        else:
            needs_draft.append(lead)
    
    print(f"\n    Already drafted (skip): {len(skipped)}")
    for s in skipped:
        print(f"      - {s}")
    print(f"    No email (skip): {len(no_email)}")
    print(f"    Needs draft: {len(needs_draft)}")
    
    if not needs_draft:
        print("\n[DONE] All leads already have drafts. Nothing to do.")
        return
    
    # Step 4: Import quill's make_email
    print(f"\n[3] Drafting {len(needs_draft)} emails...")
    sys.path.insert(0, NANOSOFT_DIR)
    from quill_v11 import make_email
    
    ok = 0
    fail = 0
    fail_details = []
    
    for i, lead in enumerate(needs_draft):
        company = lead.get("Company Name", "?")
        email = lead.get("Owner Email", "").strip()
        
        d = make_email(lead)
        if not d:
            print(f"  [SKIP] {company} - make_email returned None")
            fail += 1
            fail_details.append(f"{company}: make_email returned None")
            continue
        
        draft_id = create_gmail_draft(d["to"], d["subject"], d["body"])
        
        if draft_id:
            status = "OK" if d["is_valid"] else "WARN"
            violations = f" | violations: {d['violations']}" if d["violations"] else ""
            print(f"  [{i+1}/{len(needs_draft)}] {status} {company[:40]} | {d['word_count']}w | {d['subject']}{violations}")
            ok += 1
        else:
            print(f"  [{i+1}/{len(needs_draft)}] FAIL {company[:40]} | Gmail API error")
            fail += 1
            fail_details.append(f"{company}: Gmail API error")
    
    print(f"\n{'=' * 60}")
    print(f"[DONE] {ok} drafted, {fail} failed, {len(skipped)} already existed")
    if fail_details:
        print(f"\nFailures:")
        for f in fail_details:
            print(f"  - {f}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
