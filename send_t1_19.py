#!/usr/bin/python3
"""
Send T1 to all Qualified leads (max 20). 3-min gap between sends.
"""
import sys, time, random, os
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
LOG_FILE = os.path.join(NANOSOFT_DIR, "t1_send_19.log")

sys.path.insert(0, NANOSOFT_DIR)

def log(msg):
    ts = datetime.now(BD_TZ).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, 'a') as f:
            f.write(line + "\n")
    except:
        pass

from crm import get_crm
from quill_wl import make_email_t1, check_gmail_token, create_gmail_draft

# Check Gmail token
if not check_gmail_token():
    log("ERROR: Gmail token is dead. Cannot send.")
    sys.exit(1)

crm = get_crm()
wl = crm.get_wl_all()
qualified = [l for l in wl if l.get('Status') == 'Qualified']

log(f"Sending T1 to {len(qualified)} Qualified leads")
log("="*60)

sent = 0
failed = 0
skipped = 0

for i, lead in enumerate(qualified):
    company = lead.get('Company Name', '')
    email = lead.get('Email', '')
    
    d = make_email_t1(lead)
    if not d:
        log(f"  SKIP [{i+1}] {company} (bad email or template returned None)")
        skipped += 1
        continue
    
    if not d['is_valid']:
        log(f"  WARN [{i+1}] {company}: violations={d['violations']}")
    
    try:
        draft_id = create_gmail_draft(d['to'], d['subject'], d['body'])
        if draft_id:
            sent += 1
            log(f"  [{i+1}/{len(qualified)}] OK {company:<35} | {d['template']} | {d['subject']} | {d['word_count']}w")
            # Update CRM
            crm.update_wl_lead(company, {
                "Status": "T1 Sent",
                "Sent date": datetime.now(BD_TZ).strftime("%Y-%m-%d"),
                "T1 Date": datetime.now(BD_TZ).strftime("%Y-%m-%d"),
            })
        else:
            failed += 1
            log(f"  FAIL [{i+1}] {company} (draft creation returned None)")
    except Exception as e:
        failed += 1
        log(f"  ERROR [{i+1}] {company}: {e}")
    
    # 3-minute gap between sends (except after last one)
    if i < len(qualified) - 1:
        log(f"  Waiting 180s before next send...")
        time.sleep(180)

log("="*60)
log(f"DONE: {sent} sent, {failed} failed, {skipped} skipped out of {len(qualified)}")
