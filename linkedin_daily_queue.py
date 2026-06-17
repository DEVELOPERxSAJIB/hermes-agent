#!/usr/bin/env python3
"""
LinkedIn Daily Connection Queue
Prepares a daily batch of LinkedIn connection requests with pre-written messages.
The Chairman sends these manually from his LinkedIn account.

Usage: python3 linkedin_daily_queue.py
"""
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
QUEUE_FILE = os.path.join(NANOSOFT_DIR, "linkedin_daily_queue.json")
SENT_LOG = os.path.join(NANOSOFT_DIR, "linkedin_sent_log.json")
OUTPUT_FILE = os.path.join(NANOSOFT_DIR, "linkedin_actions_today.json")

sys.path.insert(0, NANOSOFT_DIR)

# Connection message templates
CONN_MSG_T1 = "Hi {name} — noticed {company} does solid work. Quick question about how you handle overflow projects. Open to connect?"

FOLLOWUP_MSG = "Thanks for connecting. Quick one — when {company} has more projects than your team can handle, what happens to the overflow? We help agencies keep those clients in-house. Worth a 10-min chat sometime?"


def get_first_name_from_url(url):
    """Try to extract first name from LinkedIn URL slug."""
    try:
        slug = url.rstrip("/").split("/in/")[-1]
        parts = slug.replace("-", " ").replace("_", " ").split()
        if parts:
            return parts[0].capitalize()
    except:
        pass
    return ""


def load_sent_log():
    if os.path.exists(SENT_LOG):
        with open(SENT_LOG) as f:
            return set(json.load(f))
    return set()


def save_sent_log(sent):
    with open(SENT_LOG, "w") as f:
        json.dump(list(sent), f)


def main():
    from crm import get_crm

    crm = get_crm()
    sent_log = load_sent_log()

    # Read LinkedIn tab
    try:
        ws = crm.sh.worksheet("LinkedIn")
        rows = ws.get_all_records()
    except Exception as e:
        print(f"Error reading LinkedIn tab: {e}")
        return

    # Filter pending profiles
    pending = []
    for row in rows:
        status = row.get("Status", row.get("status", "")).strip()
        url = row.get("LinkedIn URL", row.get("linkedin_url", "")).strip()
        company = row.get("Company Name", row.get("Company", "")).strip()

        if status and status != "Pending":
            continue
        if not url or "linkedin.com/in/" not in url:
            continue
        if url in sent_log:
            continue

        # Extract name from URL or row
        name = row.get("Name", row.get("name", "")).strip()
        if not name:
            name = get_first_name_from_url(url)

        pending.append({
            "company": company,
            "linkedin_url": url,
            "name": name,
        })

    # Take up to 20 per day
    daily_batch = pending[:20]

    # Generate messages
    actions = []
    for p in daily_batch:
        name = p["name"] if p["name"] else "there"
        company = p["company"] if p["company"] else "your company"

        conn_msg = CONN_MSG_T1.format(name=name, company=company)
        followup = FOLLOWUP_MSG.format(company=company)

        actions.append({
            "company": company,
            "linkedin_url": p["linkedin_url"],
            "name": p["name"],
            "connection_msg": conn_msg,
            "followup_msg": followup,
            "status": "Pending",
        })

    # Save queue
    with open(QUEUE_FILE, "w") as f:
        json.dump(actions, f, indent=2)

    # Also save as today's actions (for backward compat)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(actions, f, indent=2, ensure_ascii=False)

    print(f"LinkedIn daily queue: {len(actions)} connection requests prepared")
    print(f"Total pending: {len(pending)}")
    print(f"Queue saved to: {QUEUE_FILE}")

    # Print first 5 for preview
    if actions:
        print("\n--- PREVIEW (first 5) ---")
        for a in actions[:5]:
            print(f"  {a['company'][:30]:30} | {a['name']:15} | {a['linkedin_url'][:50]}")
            print(f"    Msg: {a['connection_msg'][:80]}...")
            print()


if __name__ == "__main__":
    main()
