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

def _update_wl_crm_cached(email, wl_leads, wl_crm, reason):
    """Mark WL as bounced using pre-fetched leads list."""
    for lead in wl_leads:
        if str(lead.get("Email", "")).strip().lower() == email.lower():
            company = str(lead.get("Company Name", "")).strip()
            _clean = email
            while _clean.startswith("BOUNCED_"):
                _clean = _clean[len("BOUNCED_"):]
            wl_crm.update_wl_lead(company, {"Status": "Bounced", "Email": f"BOUNCED_{_clean}"})
            log(f"  WL CRM updated: {company} -> Bounced")
            return True
    return False

def _update_re_crm_cached(email, re_leads, reason):
    """Mark RE as bounced using pre-fetched leads list — direct sheet write."""
    from re_pipeline.sheets import COL, SHEET_ID, SHEET_NAME, _service
    svc = _service()
    for i, lead in enumerate(re_leads):
        if str(lead.get("Email", "")).strip().lower() == email.lower():
            lead_id = lead.get("Lead_ID")
            if lead_id:
                row_num = i + 2  # +1 header, +1 0-index
                col_letter = chr(65 + COL["Status"])
                cell = f"{SHEET_NAME}!{col_letter}{row_num}"
                svc.spreadsheets().values().update(
                    spreadsheetId=SHEET_ID,
                    range=cell,
                    valueInputOption="RAW",
                    body={"values": [["Bounced"]]}
                ).execute()
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

    # Deduplicate bounce emails to avoid redundant processing
    bounced_unique = list(set(bounced))
    if len(bounced_unique) < len(bounced):
        log(f"Deduplicated to {len(bounced_unique)} unique bounced emails")

    # 2. Pre-fetch all CRM leads once (avoid per-lead quota exhaustion)
    log("Pre-fetching RE leads from CRM...")
    re_leads = []
    try:
        from re_pipeline.sheets import get_leads
        re_leads = get_leads()
        log(f"Fetched {len(re_leads)} RE leads")
    except Exception as e:
        log(f"RE leads fetch error: {e}")

    log("Pre-fetching WL leads from CRM...")
    wl_crm = None
    wl_leads = []
    try:
        from crm import NanoSoftCRM
        wl_crm = NanoSoftCRM()
        wl_leads = wl_crm.get_wl_all()
        log(f"Fetched {len(wl_leads)} WL leads")
    except Exception as e:
        log(f"WL CRM init error: {e}")

    # 3. Update CRM for each bounced email (using cached leads)
    wl_updated = 0
    re_updated = 0
    for email in bounced_unique:
        if wl_crm and _update_wl_crm_cached(email, wl_leads, wl_crm, "inbox bounce"):
            wl_updated += 1
        if _update_re_crm_cached(email, re_leads, "inbox bounce"):
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
