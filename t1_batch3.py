#!/usr/bin/env python3
"""Send T1 emails to next batch of New leads"""
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

with open('/tmp/t1_batch3.json') as f:
    emails = json.load(f)

log(f"=== T1 BATCH 3: {len(emails)} emails ===")

sent = 0
failed = 0

for i, email in enumerate(emails):
    company = email['company']
    to = email['to']
    subject = email['subject']
    body = email['body']
    
    log(f"[{i+1}/{len(emails)}] {company} ({to})")
    
    success, error = send_smtp(to, subject, body)
    if success:
        sent += 1
        log(f"  ✅ Sent")
        try:
            sys.path.insert(0, '/home/ubuntu/nanosoft')
            from crm import get_crm
            crm = get_crm()
            crm.update_wl_lead(company, {'Status': 'T1 Sent', 'Sent date': datetime.now(BD_TZ).strftime('%Y-%m-%d')})
            time.sleep(0.8)
        except Exception as e:
            log(f"  CRM error: {e}")
    else:
        failed += 1
        log(f"  ❌ {error}")
    
    if i < len(emails) - 1:
        time.sleep(180)

log(f"=== DONE: {sent} sent, {failed} failed ===")
