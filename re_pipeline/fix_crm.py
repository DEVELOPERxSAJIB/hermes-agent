"""CRM Fix: Detect bounces + find leads needing follow-up
Uses the existing crm.py singleton (which works)"""
import json
import os
import sys
import time
from datetime import datetime, timedelta
from collections import Counter

# Add nanosoft to path and import the working CRM
sys.path.insert(0, '/home/ubuntu/nanosoft')
os.chdir('/home/ubuntu/nanosoft')
from crm import get_crm

BOUNCE_SUBJECT_KWS = [
    "bounce", "undeliverable", "delivery failed", "mail delivery",
    "delivery status notification", "failure notice", "returned mail",
    "could not deliver", "message not delivered", "recipient address rejected",
    "email not received", "message blocked", "spam", "rejected"
]
BOUNCE_FROM_PATTERNS = ["postmaster", "mailer-daemon", "mail delivery subsystem"]

def is_bounce(from_email, subject, body=""):
    f = (from_email or "").lower()
    s = (subject or "").lower()
    b = (body or "").lower()
    for p in BOUNCE_FROM_PATTERNS:
        if p in f:
            return True
    for kw in BOUNCE_SUBJECT_KWS:
        if kw in s or kw in b:
            return True
    return False

def main():
    print("=" * 60)
    print("CRM BOUNCE DETECTION + FOLLOW-UP AUDIT")
    print("=" * 60)

    crm = get_crm()
    ws = crm.ws_wl
    all_records = ws.get_all_records()
    headers = ws.row_values(1)
    print(f"WL leads: {len(all_records)}")

    # Status breakdown
    status_counts = Counter(str(l.get("Status", "")).strip() for l in all_records)
    for s, c in status_counts.most_common():
        print(f"  {s or '(empty)'}: {c}")

    # 1. Scan reply log for bounces
    reply_log = "/home/ubuntu/nanosoft/replies_wl.jsonl"
    bounce_companies = set()
    bounces = []
    if os.path.exists(reply_log):
        with open(reply_log) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                    frm = r.get("from_email", "")
                    subj = r.get("reply_subject", "")
                    body = r.get("reply_body", r.get("reply_snippet", ""))
                    if is_bounce(frm, subj, body):
                        company = r.get("company", "")
                        bounces.append({
                            "company": company,
                            "template": r.get("template", ""),
                            "from": frm,
                            "subject": subj[:80],
                        })
                        bounce_companies.add(company)
                except json.JSONDecodeError:
                    continue

    print(f"\n[1] BOUNCES IN REPLY LOG: {len(bounces)}")
    for b in bounces:
        print(f"  {b['company']} | {b['template']} | {b['from'][:40]}")

    # 2. Mark bounces in sheet
    print(f"\n[2] Marking bounces in sheet...")
    updated = 0
    for i, record in enumerate(all_records, 2):
        company = str(record.get("Company Name", "")).strip()
        status = str(record.get("Status", "")).strip()
        if company in bounce_companies and status != "Bounced":
            try:
                ws.update_cell(i, 19, "Bounced")
                updated += 1
                time.sleep(0.5)
            except Exception as e:
                print(f"  Error updating row {i}: {e}")
                time.sleep(2)
    print(f"  Marked {updated} as Bounced")

    # 3. Find leads needing follow-up
    sent_col = "Sent date"
    fu1_col = "FU 1"
    fu2_col = "FU 2"

    t1_sent = [l for l in all_records if str(l.get("Status", "")).strip() in ("T1 Sent", "Email Sent", "Contacted", "Follow Up 1", "Follow Up 2")]

    needs_fu1 = []
    needs_fu2 = []
    for l in t1_sent:
        sent_date = str(l.get(sent_col, "")).strip()
        fu1 = str(l.get(fu1_col, "")).strip()
        fu2 = str(l.get(fu2_col, "")).strip()
        status = str(l.get("Status", "")).strip()

        if status in ("Partner", "Lost", "Bounced"):
            continue

        if not fu1 and sent_date:
            needs_fu1.append(l)
        elif fu1 and not fu2:
            try:
                d = datetime.strptime(fu1, "%d/%m/%Y")
                if (datetime.now() - d).days >= 3:
                    needs_fu2.append(l)
            except ValueError:
                needs_fu2.append(l)

    print(f"\n[3] FOLLOW-UP STATUS:")
    print(f"  T1 sent (total): {len(t1_sent)}")
    print(f"  Need FU1: {len(needs_fu1)}")
    print(f"  Need FU2: {len(needs_fu2)}")

    if needs_fu1:
        print(f"\n  LEADS NEEDING FU1:")
        for l in needs_fu1[:15]:
            print(f"    {l.get('Company Name', '')} | {l.get('Email', '')} | Sent: {l.get(sent_col, '')}")

    # 4. Summary
    print(f"\n{'=' * 60}")
    print("SUMMARY")
    print(f"{'=' * 60}")
    print(f"Total WL leads: {len(all_records)}")
    print(f"Bounces detected & marked: {updated}")
    print(f"Leads needing FU1: {len(needs_fu1)}")
    print(f"Leads needing FU2: {len(needs_fu2)}")
    print(f"Unqualified: {sum(1 for l in all_records if str(l.get('Status','')).strip() == 'Unqualified')}")

if __name__ == "__main__":
    main()
