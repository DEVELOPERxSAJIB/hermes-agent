#!/usr/bin/python3
"""
Daily 20 Qualified Leads Pipeline
1. Judge all unjudged leads
2. Mark exactly top 20 as Qualified (rest Unqualified)
3. Send T1 to those 20 Qualified leads
4. Update CRM status to T1 Sent

Run once per day. Never sends more than 20 emails.
"""
import sys, time, random, os
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
LOG_FILE = os.path.join(NANOSOFT_DIR, "daily_20_pipeline.log")

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

log("="*60)
log("DAILY 20 PIPELINE START")
log("="*60)

# Step 1: Check Gmail token
dead_flag = os.path.join(NANOSOFT_DIR, "GMAIL_TOKEN_DEAD")
if os.path.exists(dead_flag):
    log("ERROR: GMAIL_TOKEN_DEAD flag found. Cannot send emails.")
    sys.exit(1)

# Step 2: Judge unjudged leads
from crm import get_crm
from judge_wl import judge_wl_lead

crm = get_crm()
wl = crm.get_wl_all()

# Find leads that need judging (empty status, no valid score)
to_judge = []
for l in wl:
    status = l.get('Status', '').strip()
    if status:
        continue
    score = l.get('Judge Score', '')
    if not score or (isinstance(score, str) and score.startswith('202')):
        to_judge.append(l)

log(f"Step 1: Judging {len(to_judge)} unjudged leads...")

if not to_judge:
    log("No unjudged leads found. Nothing to do.")
    sys.exit(0)

results = []
for i, lead in enumerate(to_judge):
    company = lead.get('Company Name', '?')
    score, qualified, details = judge_wl_lead(lead)
    results.append((score, lead))
    
    # Update score in CRM
    for attempt in range(5):
        try:
            crm.update_wl_lead(company, {"Judge Score": score})
            break
        except Exception as e:
            if '429' in str(e):
                wait = 30 * (attempt + 1) + random.uniform(1, 10)
                time.sleep(wait)
            else:
                break
    
    if (i+1) % 50 == 0:
        log(f"  Judged {i+1}/{len(to_judge)}...")
    time.sleep(random.uniform(0.5, 1.5))

# Sort by score descending
results.sort(key=lambda x: -x[0])

# Step 3: Mark top 20 as Qualified
qualified = results[:20]
unqualified = results[20:]

log(f"Step 2: Marking top 20 as Qualified (scores {qualified[0][0]}-{qualified[-1][0]})...")

for score, lead in qualified:
    company = lead.get('Company Name', '?')
    for attempt in range(5):
        try:
            crm.update_wl_lead(company, {"Status": "Qualified"})
            break
        except Exception as e:
            if '429' in str(e):
                wait = 30 * (attempt + 1) + random.uniform(1, 10)
                time.sleep(wait)
            else:
                break
    time.sleep(random.uniform(0.5, 1.5))

# Mark rest as Unqualified
log(f"Step 3: Marking {len(unqualified)} as Unqualified...")
for score, lead in unqualified:
    company = lead.get('Company Name', '?')
    for attempt in range(5):
        try:
            crm.update_wl_lead(company, {"Status": "Unqualified"})
            break
        except Exception as e:
            if '429' in str(e):
                wait = 30 * (attempt + 1) + random.uniform(1, 10)
                time.sleep(wait)
            else:
                break
    time.sleep(random.uniform(0.3, 0.8))

log(f"Qualified 20 leads:")
for score, lead in qualified:
    log(f"  {score}/10 | {lead.get('Company Name',''):<35} | {lead.get('Email','')[:30]}")

# Step 4: Send T1 to exactly 20 Qualified leads
log("Step 4: Sending T1 to 20 Qualified leads...")

from quill_wl import make_email_t1, check_gmail_token, create_gmail_draft

if not check_gmail_token():
    log("ERROR: Gmail token invalid. Cannot send.")
    sys.exit(1)

# Re-fetch to get the 20 Qualified leads
wl = crm.get_wl_all()
qualified_leads = [l for l in wl if l.get('Status') == 'Qualified']
log(f"Found {len(qualified_leads)} Qualified leads to send T1")

sent = 0
failed = 0
for i, lead in enumerate(qualified_leads):
    company = lead.get('Company Name', '')
    email = lead.get('Email', '')
    
    d = make_email_t1(lead)
    if not d:
        log(f"  SKIP [{i+1}] {company} (bad email)")
        continue
    
    if not d['is_valid']:
        log(f"  WARN [{i+1}] {company}: {d['violations']}")
    
    # Send via Gmail API
    try:
        draft_id = create_gmail_draft(d['to'], d['subject'], d['body'])
        if draft_id:
            sent += 1
            log(f"  [{i+1}/20] {company:<35} | {d['subject']} | {d['word_count']}w | {d['template']}")
            # Update CRM
            crm.update_wl_lead(company, {
                "Status": "T1 Sent",
                "Sent date": datetime.now(BD_TZ).strftime("%Y-%m-%d"),
                "T1 Date": datetime.now(BD_TZ).strftime("%Y-%m-%d"),
            })
        else:
            failed += 1
            log(f"  FAIL [{i+1}] {company}")
    except Exception as e:
        failed += 1
        log(f"  ERROR [{i+1}] {company}: {e}")
    
    # 3-minute gap between sends (Gmail rate limit)
    if i < len(qualified_leads) - 1:
        time.sleep(180)

log("="*60)
log(f"DONE: {sent} sent, {failed} failed out of 20 Qualified leads")
log("="*60)
