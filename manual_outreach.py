#!/usr/bin/env python3
"""Send T3 follow-ups to T2 Sent leads + personal follow-up to Fulcrum & Pixelcrayons"""
import json, smtplib, ssl, time, sys, os
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
SMTP_EMAIL = "nanosoftagency007@gmail.com"
SMTP_PASS = "txub mxkk xcge gxdf"
LOG_FILE = "/home/ubuntu/nanosoft/pipeline.log"

def log(msg):
    ts = datetime.now(BD_TZ).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def send_smtp(to_email, subject, body):
    for attempt in range(3):
        try:
            msg = f"From: SaJib Shikder <{SMTP_EMAIL}>\nTo: {to_email}\nSubject: {subject}\nList-Unsubscribe: <mailto:{SMTP_EMAIL}?subject=unsubscribe>\nContent-Type: text/plain; charset=utf-8\n\n{body}"
            ctx = ssl.create_default_context()
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.ehlo()
                server.starttls(context=ctx)
                server.ehlo()
                server.login(SMTP_EMAIL, SMTP_PASS)
                server.sendmail(SMTP_EMAIL, to_email, msg.encode('utf-8'))
            return True, ""
        except Exception as e:
            err = str(e)[:200]
            if attempt < 2:
                log(f"  SMTP retry {attempt+1} for {to_email}: {err}")
                time.sleep(60)
            else:
                return False, err
    return False, "Max retries"

# Load T3 emails
with open('/tmp/t3_emails.json') as f:
    t3_emails = json.load(f)

# Add Fulcrum and Pixelcrayons personal follow-ups
personal_emails = [
    {
        'company': 'Fulcrum',
        'to': 'hello@fulcrum.rocks',
        'subject': 'Fulcrum partnership',
        'body': """Hey Fulcrum team,

You mentioned you'd get back to me. Haven't heard anything yet so figured I'd check in.

We're a white-label dev team. Agencies like yours send us overflow work — we ship under your brand, your client never knows the difference.

If you have a project on the backburner or a client asking for something your team can't handle right now, we can help.

Worth a 15-min call?

SaJib""",
        'score': '10',
        'fu1': '',
    },
    {
        'company': 'Pixelcrayons',
        'to': 'sales@pixelcrayons.com',
        'subject': 'following up',
        'body': """Hey Pixelcrayons team,

My last email got an auto-reply saying someone would review and revert. Following up to make sure it didn't get lost.

We help agencies like yours with white-label web and mobile development. If you ever have more work than your team can handle, we're the quiet partner that ships under your brand.

Would it make sense to have a quick chat?

SaJib""",
        'score': '8',
        'fu1': '',
    },
]

all_emails = personal_emails + t3_emails
log(f"=== MANUAL OUTREACH: {len(all_emails)} emails (2 personal + 23 T3) ===")

sent = 0
failed = 0

for i, email in enumerate(all_emails):
    company = email['company']
    to = email['to']
    subject = email['subject']
    body = email['body']
    
    log(f"[{i+1}/{len(all_emails)}] Sending to {company} ({to})")
    
    success, error = send_smtp(to, subject, body)
    if success:
        sent += 1
        log(f"  ✅ Sent to {company}")
        # Update CRM
        try:
            sys.path.insert(0, '/home/ubuntu/nanosoft')
            from crm import get_crm
            crm = get_crm()
            if company in ('Fulcrum', 'Pixelcrayons'):
                crm.update_wl_lead(company, {'Status': 'T1 Sent', 'Sent date': datetime.now(BD_TZ).strftime('%Y-%m-%d')})
            else:
                crm.update_wl_lead(company, {'Status': 'T3 Sent', 'FU 2': (datetime.now(BD_TZ) + timedelta(days=2)).strftime('%d/%m/%Y')})
            time.sleep(0.8)
        except Exception as e:
            log(f"  CRM update error: {e}")
    else:
        failed += 1
        log(f"  ❌ Failed: {error}")
    
    # 3-minute gap between emails
    if i < len(all_emails) - 1:
        log(f"  Waiting 180s...")
        time.sleep(180)

log(f"\n=== DONE: {sent} sent, {failed} failed ===")
