"""
Daily Bounce Tracker — scans Gmail inbox for bounce-backs and updates CRM.
Runs as a cron job once per day.
"""
import json, os, sys, re
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
RE_PIPELINE_DIR = os.path.join(NANOSOFT_DIR, "re_pipeline")
LOG_FILE = os.path.join(NANOSOFT_DIR, "bounce_log.jsonl")

sys.path.insert(0, NANOSOFT_DIR)
sys.path.insert(0, RE_PIPELINE_DIR)

def log(msg):
    ts = datetime.now(BD_TZ).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)

def scan_inbox_for_bounces():
    """Scan Gmail IMAP for delivery failure notifications."""
    from gmail_utils import fetch_recent_bounces
    return fetch_recent_bounces(hours=24)

def update_wl_crm(email, reason):
    """Mark WL lead as bounced."""
    from crm import NanoSoftCRM
    crm = NanoSoftCRM()
    leads = crm.get_wl_all()
    for lead in leads:
        if str(lead.get("Email", "")).strip().lower() == email.lower():
            company = str(lead.get("Company Name", "")).strip()
            # Strip existing BOUNCED_ prefix to avoid stacking
            _clean = email
            while _clean.startswith("BOUNCED_"):
                _clean = _clean[len("BOUNCED_"):]
            crm.update_wl_lead(company, {"Status": "Bounced", "Email": f"BOUNCED_{_clean}"})
            log(f"  WL CRM updated: {company} -> Bounced")
            return True
    return False

def update_re_crm(email, reason):
    """Mark RE lead as bounced."""
    from re_pipeline.sheets import get_leads, update_status
    leads = get_leads()
    for lead in leads:
        if str(lead.get("Email", "")).strip().lower() == email.lower():
            lead_id = lead.get("Lead_ID")
            if lead_id:
                update_status(lead_id, "Bounced")
                log(f"  RE CRM updated: {lead.get('Brokerage_Name','')} -> Bounced")
            return True
    return False

def main():
    log("=" * 50)
    log("DAILY BOUNCE TRACKER")
    log("=" * 50)

    # 1. Scan inbox for bounce-backs
    log("Scanning Gmail inbox for bounce-backs...")
    bounced = []
    try:
        bounced = scan_inbox_for_bounces()
        log(f"Found {len(bounced)} bounced emails in inbox")
    except Exception as e:
        log(f"Inbox scan error: {e}")

    # 2. Update CRM for each bounced email
    wl_updated = 0
    re_updated = 0
    for email in bounced:
        if update_wl_crm(email, "inbox bounce"):
            wl_updated += 1
        if update_re_crm(email, "inbox bounce"):
            re_updated += 1
        # Log to bounce log
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps({
                "email": email,
                "reason": "inbox-detected bounce",
                "source": "inbox",
                "detected_at": datetime.now(BD_TZ).isoformat()
            }) + "\n")

    # 3. Summary
    log(f"Bounce tracker complete:")
    log(f"  Bounced emails found: {len(bounced)}")
    log(f"  WL CRM updated: {wl_updated}")
    log(f"  RE CRM updated: {re_updated}")

    # 4. Show current bounce log stats
    try:
        with open(LOG_FILE) as f:
            total_bounces = sum(1 for l in f if l.strip())
        log(f"  Total bounces in log: {total_bounces}")
    except:
        pass

if __name__ == "__main__":
    main()
