#!/usr/bin/env python3
"""
RE Send Remaining — one-shot script, run inline
Reads leads from sheet, sends remaining emails up to daily limit
"""
import sys, os, time, json, subprocess

SENT_LOG = '/home/ubuntu/nanosoft/emails_sent_re.jsonl'
TOKEN_PATH = '/home/ubuntu/.hermes/google_token.json'
SHEET_ID = '1rQAyfC037JoV2phnLq4g9JsDvvrEb6M69A3roeYJHkk'
SMTP_USER = 'nanosoftagency007@gmail.com'
SMTP_PASS = 'wgxo ddup cdol kupl'

from datetime import datetime, timezone, timedelta
BD_TZ = timezone(timedelta(hours=6))
today_log = datetime.now(BD_TZ).strftime('%Y-%m-%d')
today_sheet = datetime.now(BD_TZ).strftime('%d/%m/%Y')

# Count today's sends
sent_today = set()
try:
    with open(SENT_LOG) as f:
        for line in f:
            if line.strip() and today_log in line:
                try:
                    e = json.loads(line)
                    sent_today.add(f"{e.get('to','').lower()}|T1")
                except: pass
except: pass

print(f"Sent today: {len(sent_today)}")

# Get New leads from sheet using gspread
import gspread
from google.oauth2.credentials import Credentials

with open(TOKEN_PATH) as f:
    d = json.load(f)
creds = Credentials(token=d['token'], refresh_token=d.get('refresh_token'),
    token_uri=d.get('token_uri', 'https://oauth2.googleapis.com/token'),
    client_id=d['client_id'], client_secret=d['client_secret'], scopes=d.get('scopes'))
gc = gspread.authorize(creds)
ws = gc.open_by_key(SHEET_ID).worksheet('Pipeline')
all_values = ws.get_all_values()
print(f"Sheet rows: {len(all_values)}")

# Find unsent New leads
to_send = []
for i, row in enumerate(all_values[1:], start=2):
    if len(row) > 14 and row[14].strip() == 'New':
        email = row[8].strip() if len(row) > 8 else ''
        if email and '@' in email and f'{email.lower()}|T1' not in sent_today:
            to_send.append({'row': i, 'name': row[1].strip(), 'city': row[4].strip() if len(row)>4 else '', 'email': email})

remaining = 20 - len(sent_today)
to_send = to_send[:remaining]
print(f"Will send: {len(to_send)} emails")

if not to_send:
    print("Nothing to send.")
    sys.exit(0)

# Import template
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from personalized_templates import get_personalized_template

import smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

sent = 0
for i, lead in enumerate(to_send):
    tmpl = get_personalized_template(1, lead['name'], '', lead['city'])
    if not tmpl.get('subject'):
        print(f"  SKIP: no template for {lead['name']}")
        continue
    
    try:
        msg = MIMEMultipart()
        msg['From'] = f'SaJib Shikder <{SMTP_USER}>'
        msg['To'] = lead['email']
        msg['Subject'] = tmpl['subject']
        msg.attach(MIMEText(tmpl['body'], 'plain', 'utf-8'))
        ctx = ssl.create_default_context()
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.ehlo(); server.starttls(context=ctx); server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        
        with open(SENT_LOG, 'a') as f:
            f.write(json.dumps({'to': lead['email'], 'company': lead['name'], 'subject': tmpl['subject'], 'template': 'T1', 'sent_at': datetime.now(BD_TZ).isoformat()}) + '\n')
        
        try:
            ws.update_cell(lead['row'], 15, 'Contacted')  # Col O = Status
            ws.update_cell(lead['row'], 16, today_sheet)        # Col P = Touch_1_Date
        except: pass
        
        sent += 1
        print(f"  [{i+1}/{len(to_send)}] SENT: {lead['name'][:35]} | {lead['email']}")
    except Exception as e:
        print(f"  [{i+1}/{len(to_send)}] FAIL: {lead['name'][:35]} | {str(e)[:60]}")
    
    if i < len(to_send) - 1:
        time.sleep(120)

print(f"\nDONE: {sent} sent today (total: {len(sent_today)+sent}/20)")
