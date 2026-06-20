#!/usr/bin/env python3
"""
Fast RE Personalized Email Sender v2
Optimized for larger sheets — sends T1 to New leads with 2-min gaps.
"""
import sys, os, time, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import TOKEN_PATH, SHEET_ID, SHEET_NAME, COL
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from personalized_templates import get_personalized_template
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
MAX_DAILY = 20

def log(msg):
    ts = datetime.now(BD_TZ).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

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

def main():
    log("=== RE PERSONALIZED SENDER v2 ===")
    
    # Check daily limit
    today = datetime.now(BD_TZ).strftime("%Y-%m-%d")
    sent_today = 0
    try:
        with open(SENT_LOG) as f:
            for line in f:
                if line.strip() and today in line:
                    sent_today += 1
    except:
        pass
    
    if sent_today >= MAX_DAILY:
        log(f"Daily limit reached: {sent_today}/{MAX_DAILY}")
        return
    
    remaining = MAX_DAILY - sent_today
    log(f"Sent today: {sent_today}/{MAX_DAILY}. Can send {remaining} more.")
    
    # Connect and fetch
    with open(TOKEN_PATH) as f:
        d = json.load(f)
    creds = Credentials(token=d['token'], refresh_token=d.get('refresh_token'),
        token_uri=d.get('token_uri', 'https://oauth2.googleapis.com/token'),
        client_id=d['client_id'], client_secret=d['client_secret'], scopes=d.get('scopes'))
    service = build('sheets', 'v4', credentials=creds)
    
    # Fetch only columns we need: A, B, C, E, H, I, O (Name, Contact, Title, City, Website, Email, Status)
    result = service.spreadsheets().values().get(
        spreadsheetId=SHEET_ID,
        range=f'{SHEET_NAME}!A1:O500'
    ).execute()
    rows = result.get('values', [])
    log(f"Fetched {len(rows)} rows")
    
    # Find New leads with email
    to_send = []
    for i, row in enumerate(rows[1:], start=2):
        if len(row) > 14 and row[14].strip() == 'New':
            email = row[8].strip() if len(row) > 8 else ''
            if email and '@' in email and not email.endswith(('.png', '.jpg', '.gif', '.js', '.css')):
                to_send.append({
                    'row': i,
                    'name': row[1].strip() if len(row) > 1 else '',
                    'contact': row[2].strip() if len(row) > 2 else '',
                    'city': row[4].strip() if len(row) > 4 else '',
                    'email': email,
                })
    
    log(f"New leads with email: {len(to_send)}")
    to_send = to_send[:remaining]
    log(f"Sending to {len(to_send)} leads...")
    
    sent = 0
    failed = 0
    
    for i, lead in enumerate(to_send):
        tmpl = get_personalized_template(
            touch_num=1,
            brokerage_name=lead['name'],
            contact_name=lead['contact'],
            city=lead['city'],
        )
        
        if not tmpl.get('subject'):
            log(f"  [{i+1}] SKIP: no template for {lead['name'][:30]}")
            continue
        
        log(f"  [{i+1}/{len(to_send)}] {lead['name'][:35]} | {lead['email']}")
        log(f"    Subject: {tmpl['subject']}")
        
        ok, err = send_smtp(lead['email'], tmpl['subject'], tmpl['body'])
        
        if ok:
            with open(SENT_LOG, "a") as f:
                f.write(json.dumps({
                    "to": lead['email'], "company": lead['name'],
                    "subject": tmpl['subject'], "template": "T1",
                    "sent_at": datetime.now(BD_TZ).isoformat(),
                }) + "\n")
            # Update status to Contacted
            try:
                service.spreadsheets().values().update(
                    spreadsheetId=SHEET_ID,
                    range=f'{SHEET_NAME}!O{lead["row"]}',
                    valueInputOption='RAW',
                    body={'values': [['Contacted']]}
                ).execute()
                # Update touch date
                service.spreadsheets().values().update(
                    spreadsheetId=SHEET_ID,
                    range=f'{SHEET_NAME}!P{lead["row"]}',
                    valueInputOption='RAW',
                    body={'values': [[today]]}
                ).execute()
            except Exception as e:
                log(f"    Update error: {e}")
            sent += 1
            log(f"    -> SENT")
        else:
            failed += 1
            log(f"    -> FAILED: {err[:80]}")
        
        if i < len(to_send) - 1:
            time.sleep(120)
    
    log(f"\n=== DONE: {sent} sent, {failed} failed ===")

if __name__ == "__main__":
    main()
