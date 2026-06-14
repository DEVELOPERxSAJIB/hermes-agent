#!/usr/bin/python3
"""
Judge all unjudged WL leads and mark exactly top 20 as Qualified.
Handles Google Sheets 429 errors with retry + jitter.
"""
import sys, time, random, os
sys.path.insert(0, '/home/ubuntu/nanosoft')

from crm import get_crm
from judge_wl import judge_wl_lead

crm = get_crm()
wl = crm.get_wl_all()

# Get leads with empty status that have no Judge Score (or score looks like a date)
to_judge = []
for l in wl:
    status = l.get('Status', '').strip()
    if status:  # skip leads that already have a status
        continue
    score = l.get('Judge Score', '')
    # If score is empty or looks like a date (2026-xx-xx), needs re-judging
    if not score or (isinstance(score, str) and score.startswith('202')):
        to_judge.append(l)

print(f"[JUDGE] {len(to_judge)} leads need judging")

if not to_judge:
    print("Nothing to judge.")
    sys.exit(0)

# Judge all leads
results = []
for i, lead in enumerate(to_judge):
    company = lead.get('Company Name', '?')
    score, qualified, details = judge_wl_lead(lead)
    results.append((score, lead))
    
    # Update CRM with score (with retry on 429)
    for attempt in range(5):
        try:
            crm.update_wl_lead(company, {"Judge Score": score})
            break
        except Exception as e:
            if '429' in str(e):
                wait = 30 * (attempt + 1) + random.uniform(1, 10)
                print(f"  [429] Waiting {wait:.0f}s before retry...")
                time.sleep(wait)
            else:
                print(f"  [ERROR] {company}: {e}")
                break
    
    status = "✅" if qualified else "❌"
    print(f"  [{i+1}/{len(to_judge)}] {status} {company:<35} | {score}/10")
    
    # Small delay to avoid 429
    time.sleep(random.uniform(0.5, 1.5))

# Sort by score descending
results.sort(key=lambda x: -x[0])

# Mark top 20 as Qualified, rest as Unqualified
qualified = results[:20]
unqualified = results[20:]

print(f"\n[JUDGE] Marking top 20 as Qualified...")
for score, lead in qualified:
    company = lead.get('Company Name', '?')
    for attempt in range(5):
        try:
            crm.update_wl_lead(company, {"Status": "Qualified"})
            print(f"  ✅ {company:<35} | {score}/10 | {lead.get('Email','')[:30]}")
            break
        except Exception as e:
            if '429' in str(e):
                wait = 30 * (attempt + 1) + random.uniform(1, 10)
                time.sleep(wait)
            else:
                break
    time.sleep(random.uniform(0.5, 1.5))

print(f"\n[JUDGE] Marking {len(unqualified)} as Unqualified...")
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

print(f"\n[DONE] 20 Qualified, {len(unqualified)} Unqualified")
