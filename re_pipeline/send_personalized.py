#!/usr/bin/env python3
"""
Personalized RE Email Sender
For each New lead:
1. Scrapes their website for actual listing data
2. Generates a personalized email referencing specific listings/areas
3. Sends via SMTP
4. Updates CRM status
"""
import sys, os, time, json, re, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import TOKEN_PATH, SHEET_ID, SHEET_NAME, COL
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from personalized_templates import get_personalized_template
from osm_sourcing import scrape_website_emails, _fetch_page, _decode_html_entities
from urllib.parse import urlparse
import smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "nanosoftagency007@gmail.com"
SMTP_PASS = "wgxo ddup cdol kupl"

SENT_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'emails_sent_re.jsonl')
MAX_DAILY = 20  # Max RE emails per day

def log(msg):
    ts = datetime.now(BD_TZ).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)

def get_sheet_service():
    with open(TOKEN_PATH) as f:
        d = json.load(f)
    creds = Credentials(
        token=d['token'], refresh_token=d.get('refresh_token'),
        token_uri=d.get('token_uri', 'https://oauth2.googleapis.com/token'),
        client_id=d['client_id'], client_secret=d['client_secret'],
        scopes=d.get('scopes')
    )
    return build('sheets', 'v4', credentials=creds)

def get_new_leads(service):
    """Get all New leads from RE sheet."""
    result = service.spreadsheets().values().get(
        spreadsheetId=SHEET_ID,
        range=f'{SHEET_NAME}!A1:T500'
    ).execute()
    rows = result.get('values', [])
    leads = []
    for i, row in enumerate(rows[1:], start=2):
        if len(row) > 14 and row[14].strip() == 'New':
            lead = {
                'row': i,
                'Lead_ID': row[0] if len(row) > 0 else '',
                'Brokerage_Name': row[1] if len(row) > 1 else '',
                'Contact_Name': row[2] if len(row) > 2 else '',
                'City': row[4] if len(row) > 4 else '',
                'State_Country': row[5] if len(row) > 5 else '',
                'Website': row[7] if len(row) > 7 else '',
                'Email': row[8] if len(row) > 8 else '',
                'Instagram_URL': row[10] if len(row) > 10 else '',
                'LinkedIn_URL': row[9] if len(row) > 9 else '',
            }
            if lead['Email'] and '@' in lead['Email']:
                leads.append(lead)
    return leads

def count_today_sends():
    today = datetime.now(BD_TZ).strftime("%Y-%m-%d")
    count = 0
    try:
        with open(SENT_LOG) as f:
            for line in f:
                if line.strip() and today in line:
                    count += 1
    except:
        pass
    return count

def append_sent_log(to_email, company, subject, template):
    with open(SENT_LOG, "a") as f:
        f.write(json.dumps({
            "to": to_email, "company": company,
            "subject": subject, "template": template,
            "sent_at": datetime.now(BD_TZ).isoformat(),
        }) + "\n")

def send_smtp(to_email, subject, body):
    try:
        msg = MIMEMultipart()
        msg["From"] = "SaJib Shikder <nanosoftagency007@gmail.com>"
        msg["To"] = to_email
        msg["Subject"] = subject.replace("\n", " ").strip()
        msg.attach(MIMEText(body, "plain", "utf-8"))
        ctx = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls(context=ctx)
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        return True, ""
    except Exception as e:
        return False, str(e)[:200]

def update_lead_status(service, row, new_status, touch_date_col=None):
    """Update lead status in sheet."""
    try:
        service.spreadsheets().values().update(
            spreadsheetId=SHEET_ID,
            range=f'{SHEET_NAME}!O{row}',
            valueInputOption='RAW',
            body={'values': [[new_status]]}
        ).execute()
        if touch_date_col:
            today = datetime.now(BD_TZ).strftime("%d/%m/%Y")
            col_letter = chr(64 + touch_date_col)  # A=1, B=2, ...
            service.spreadsheets().values().update(
                spreadsheetId=SHEET_ID,
                range=f'{SHEET_NAME}!{col_letter}{row}',
                valueInputOption='RAW',
                body={'values': [[today]]}
            ).execute()
    except Exception as e:
        log(f"  Update error: {e}")

def is_valid_email(email):
    """Basic email validation."""
    if not email or '@' not in email:
        return False
    if email.endswith(('.png', '.jpg', '.gif', '.svg', '.ico', '.css', '.js', '.woff', '.ttf', '.webp')):
        return False
    local = email.split('@')[0]
    if len(local) > 20 and all(c in '0123456789abcdef.' for c in local):
        return False
    return True

def main():
    log("=== PERSONALIZED RE EMAIL SENDER ===")
    
    # Check daily limit
    today_count = count_today_sends()
    if today_count >= MAX_DAILY:
        log(f"Daily limit reached: {today_count}/{MAX_DAILY}. Exiting.")
        return
    
    remaining = MAX_DAILY - today_count
    log(f"Today sends: {today_count}/{MAX_DAILY}. Can send {remaining} more.")
    
    service = get_sheet_service()
    new_leads = get_new_leads(service)
    log(f"New leads with email: {len(new_leads)}")
    
    if not new_leads:
        log("No New leads to send.")
        return
    
    # Limit to remaining daily budget
    to_send = new_leads[:remaining]
    log(f"Sending to {len(to_send)} leads...")
    
    sent = 0
    failed = 0
    skipped = 0
    
    for i, lead in enumerate(to_send):
        brokerage = lead['Brokerage_Name']
        email = lead['Email'].strip()
        contact = lead['Contact_Name']
        city = lead['City']
        state = lead['State_Country']
        website = lead['Website']
        
        # Validate email
        if not is_valid_email(email):
            log(f"  [{i+1}] SKIP bad email: {brokerage[:30]} | {email[:40]}")
            skipped += 1
            continue
        
        # Generate personalized email
        tmpl = get_personalized_template(
            touch_num=1,
            brokerage_name=brokerage,
            contact_name=contact,
            city=city,
            state=state,
            website=website,
        )
        
        if not tmpl or not tmpl.get('subject'):
            log(f"  [{i+1}] SKIP no template: {brokerage[:30]}")
            skipped += 1
            continue
        
        log(f"  [{i+1}/{len(to_send)}] {brokerage[:35]} | {email}")
        log(f"    Subject: {tmpl['subject']}")
        
        ok, err = send_smtp(email, tmpl['subject'], tmpl['body'])
        
        if ok:
            append_sent_log(email, brokerage, tmpl['subject'], "T1")
            update_lead_status(service, lead['row'], 'Contacted', touch_date_col=15)
            sent += 1
            log(f"    -> SENT")
        else:
            failed += 1
            log(f"    -> FAILED: {err[:80]}")
        
        # 2-minute gap between emails
        if i < len(to_send) - 1:
            time.sleep(120)
    
    log(f"\n=== DONE: {sent} sent, {failed} failed, {skipped} skipped ===")

if __name__ == "__main__":
    main()
