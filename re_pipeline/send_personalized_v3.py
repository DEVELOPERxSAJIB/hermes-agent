#!/usr/bin/env python3
"""
Fast RE Personalized Email Sender v3 (gspread)
"""
import sys, os, time, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import TOKEN_PATH, SHEET_ID, SHEET_NAME
from google.oauth2.credentials import Credentials
import gspread
from personalized_templates import get_personalized_template
import smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
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
        msg["From"] = f"SaJib Shikder <{SMTP_USER}>"
        msg["To"] = to_email
        msg["Subject"] = subject.replace("\n", " ").strip()
        msg.attach(MIMEText(body, "plain", "utf-8"))
        ctx = ssl.create_default_context()
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo(); server.starttls(context=ctx); server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        return True, ""
    except Exception as e:
        return False, str(e)[:200]

def main():
    log("=== RE PERSONALIZED SENDER v3 ===")
    
    today = datetime.now(BD_TZ).strftime("%Y-%m-%d")
    today_sheet = datetime.now(BD_TZ).strftime("%d/%m/%Y")
    sent_today = sum(1 for line in open(SENT_LOG) if line.strip() and today in line) if os.path.exists(SENT_LOG) else 0
    
    if sent_today >= MAX_DAILY:
        log(f"Limit reached: {sent_today}/{MAX_DAILY}")
        return
    
    remaining = MAX_DAILY - sent_today
    log(f"Sent today: {sent_today}/{MAX_DAILY}, can send {remaining} more")
    
    # Connect via gspread (fast)
    with open(TOKEN_PATH) as f:
        d = json.load(f)
    creds = Credentials(token=d['token'], refresh_token=d.get('refresh_token'),
        token_uri=d.get('token_uri', 'https://oauth2.googleapis.com/token'),
        client_id=d['client_id'], client_secret=d['client_secret'], scopes=d.get('scopes'))
    gc = gspread.authorize(creds)
    ws = gc.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
    all_values = ws.get_all_values()
    log(f"Fetched {len(all_values)} rows")
    
    # Load sent log for dedup
    sent_log = set()
    if os.path.exists(SENT_LOG):
        with open(SENT_LOG) as f:
            for line in f:
                if line.strip():
                    try:
                        e = json.loads(line)
                        sent_log.add(f"{e.get('to','').lower()}|{e.get('template','')}")
                    except: pass
    
    # Find New leads (skip already sent)
    to_send = []
    for i, row in enumerate(all_values[1:], start=2):
        if len(row) > 14 and row[14].strip() == 'New':
            email = row[8].strip() if len(row) > 8 else ''
            if email and '@' in email and not any(email.endswith(x) for x in ['.png','.jpg','.gif','.js','.css','.webp']):
                key = f"{email.lower()}|T1"
                if key not in sent_log:
                    to_send.append({'row': i, 'name': row[1].strip(), 'contact': row[2].strip() if len(row)>2 else '', 'city': row[4].strip() if len(row)>4 else '', 'email': email})
                else:
                    log(f"  SKIP (already sent): {row[1][:30]} | {email}")
    
    to_send = to_send[:remaining]
    log(f"Sending to {len(to_send)} leads...")
    
    sent = failed = 0
    for i, lead in enumerate(to_send):
        tmpl = get_personalized_template(1, lead['name'], lead['contact'], lead['city'])
        if not tmpl.get('subject'):
            continue
        
        log(f"  [{i+1}/{len(to_send)}] {lead['name'][:35]} | {lead['email']}")
        log(f"    {tmpl['subject']}")
        
        ok, err = send_smtp(lead['email'], tmpl['subject'], tmpl['body'])
        if ok:
            with open(SENT_LOG, "a") as f:
                f.write(json.dumps({"to": lead['email'], "company": lead['name'], "subject": tmpl['subject'], "template": "T1", "sent_at": datetime.now(BD_TZ).isoformat()}) + "\n")
            sent_log.add(f"{lead['email'].lower()}|T1")  # prevent dupes in same run
            try:
                ws.update_cell(lead['row'], 15, 'Contacted')  # Col O
                ws.update_cell(lead['row'], 16, today_sheet)  # Col P
            except: pass
            sent += 1
            log(f"    -> SENT")
        else:
            failed += 1
            log(f"    -> FAIL: {err[:60]}")
        
        if i < len(to_send) - 1:
            time.sleep(120)
    
    log(f"=== DONE: {sent} sent, {failed} failed ===")

if __name__ == "__main__":
    main()
