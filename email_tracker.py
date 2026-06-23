"""
Email Verification + Bounce Tracker
====================================
1. Pre-send: verify domain has MX records (free, instant)
2. Post-send: detect bounces from SMTP responses + inbox monitoring
3. CRM update: mark bounced/invalid emails so we never send again
"""
import json, os, re, sys, time, socket, dns.resolver
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
LOG_FILE = os.path.join(NANOSOFT_DIR, "bounce_log.jsonl")

# ─── DNS MX check (free, no API needed) ──────────────────────
def check_mx(domain):
    """Check if domain has MX records. Returns (has_mx, mx_records)."""
    try:
        answers = dns.resolver.resolve(domain, 'MX')
        records = sorted([(r.preference, str(r.exchange).rstrip('.')) for r in answers])
        return True, records
    except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers):
        return False, []
    except Exception as e:
        return False, [str(e)]

# ─── SMTP mailbox verification (lightweight) ────────────────
def verify_email(email):
    """
    Verify email: syntax + MX record check.
    Port 25 is blocked on most cloud providers, so we can't do SMTP RCPT TO.
    Returns: "valid" | "invalid" | "unknown"
    """
    from email_validator import validate_email, EmailNotValidError

    # Step 1: syntax + basic domain check
    try:
        result = validate_email(email, check_deliverability=True)
        normalized = result.normalized
    except EmailNotValidError as ex:
        return "invalid", str(ex)

    domain = normalized.split('@')[1]

    # Step 2: MX record check (DNS-based, works even when port 25 is blocked)
    has_mx, mx_records = check_mx(domain)
    if not has_mx:
        return "invalid", f"No MX records for {domain}"

    return "valid", f"MX found: {mx_records[0][1]}"

# ─── Bounce detection from SMTP response ────────────────────
def detect_bounce_from_smtp(error_msg):
    """Check if an SMTP error is a permanent bounce."""
    bounce_codes = ['550', '551', '552', '553', '554', '5.1.1', '5.7.1']
    error_lower = error_msg.lower()
    for code in bounce_codes:
        if code in error_lower:
            return True
    bounce_keywords = ['user unknown', 'recipient rejected', 'mailbox not found',
                       'no such user', 'invalid recipient', 'does not exist',
                       'bounce', 'undeliverable', 'delivery failed']
    for kw in bounce_keywords:
        if kw in error_lower:
            return True
    return False

# ─── Bounce log management ──────────────────────────────────
def load_bounce_log():
    entries = []
    try:
        with open(LOG_FILE) as f:
            for line in f:
                if line.strip():
                    entries.append(json.loads(line))
    except:
        pass
    return entries

def append_bounce_log(email, reason, source="smtp"):
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps({
            "email": email.lower(),
            "reason": reason,
            "source": source,
            "detected_at": datetime.now(BD_TZ).isoformat(),
        }) + "\n")

def is_known_bounced(email):
    """Check if email is already in bounce log."""
    email_lower = email.lower()
    for entry in load_bounce_log():
        if entry.get("email") == email_lower:
            return True
    return False

# ─── CRM update for bounced/invalid emails ──────────────────
def mark_wl_bounced(email, reason):
    """Mark a WL lead's email as bounced in CRM."""
    sys.path.insert(0, NANOSOFT_DIR)
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
            crm.update_wl_lead(company, {
                "Status": "Bounced",
                "Email": f"BOUNCED_{_clean}",
            })
            return company
    return None

def mark_re_bounced(email, reason):
    """Mark a RE lead's email as bounced in sheet."""
    sys.path.insert(0, NANOSOFT_DIR)
    sys.path.insert(0, os.path.join(NANOSOFT_DIR, "re_pipeline"))
    from sheets import get_leads, update_status
    leads = get_leads()
    for lead in leads:
        if str(lead.get("Email", "")).strip().lower() == email.lower():
            lead_id = lead.get("Lead_ID")
            if lead_id:
                update_status(lead_id, "Bounced")
            return str(lead.get("Brokerage_Name", "")).strip()
    return None

# ─── Batch verify all leads ─────────────────────────────────
def batch_verify_wl():
    """Verify all WL leads with emails. Returns stats."""
    sys.path.insert(0, NANOSOFT_DIR)
    from crm import NanoSoftCRM
    crm = NanoSoftCRM()
    leads = crm.get_wl_all()

    stats = {"valid": 0, "invalid": 0, "unknown": 0, "skipped": 0, "total": 0}
    results = []

    for lead in leads:
        email = str(lead.get("Email", "")).strip()
        if not email or "@" not in email or email.startswith("BOUNCED_"):
            stats["skipped"] += 1
            continue
        stats["total"] += 1
        company = str(lead.get("Company Name", "")).strip()

        status, detail = verify_email(email)
        results.append({"email": email, "company": company, "status": status, "detail": detail})

        if status == "valid":
            stats["valid"] += 1
        elif status == "invalid":
            stats["invalid"] += 1
            # Mark in CRM
            mark_wl_bounced(email, detail)
            append_bounce_log(email, detail, "pre-send")
        else:
            stats["unknown"] += 1

    return stats, results

def batch_verify_re():
    """Verify all RE leads with emails. Returns stats."""
    sys.path.insert(0, NANOSOFT_DIR)
    sys.path.insert(0, os.path.join(NANOSOFT_DIR, "re_pipeline"))
    from sheets import get_leads

    leads = get_leads()
    stats = {"valid": 0, "invalid": 0, "unknown": 0, "skipped": 0, "total": 0}
    results = []

    for lead in leads:
        email = str(lead.get("Email", "")).strip()
        if not email or "@" not in email:
            stats["skipped"] += 1
            continue
        stats["total"] += 1
        brokerage = str(lead.get("Brokerage_Name", "")).strip()

        status, detail = verify_email(email)
        results.append({"email": email, "brokerage": brokerage, "status": status, "detail": detail})

        if status == "valid":
            stats["valid"] += 1
        elif status == "invalid":
            stats["invalid"] += 1
            mark_re_bounced(email, detail)
            append_bounce_log(email, detail, "pre-send")
        else:
            stats["unknown"] += 1

    return stats, results

# ─── Bounce email detection from inbox ──────────────────────
def check_inbox_for_bounces():
    """
    Check Gmail inbox for bounce-back emails.
    Returns list of bounced email addresses.
    """
    sys.path.insert(0, NANOSOFT_DIR)
    sys.path.insert(0, os.path.join(NANOSOFT_DIR, "re_pipeline"))
    from gmail_utils import fetch_recent_bounces

    bounced = []
    try:
        bounced = fetch_recent_bounces(hours=48)
    except Exception as e:
        print(f"Bounce check error: {e}")

    return list(set(bounced))

# ─── Main ────────────────────────────────────────────────────
if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "help"

    if action == "verify-wl":
        print("Verifying WL leads...")
        stats, results = batch_verify_wl()
        print(f"\nWL Results: {stats}")
        for r in results:
            if r["status"] == "invalid":
                print(f"  INVALID: {r['email']} ({r['company']}) - {r['detail']}")

    elif action == "verify-re":
        print("Verifying RE leads...")
        stats, results = batch_verify_re()
        print(f"\nRE Results: {stats}")
        for r in results:
            if r["status"] == "invalid":
                print(f"  INVALID: {r['email']} ({r['brokerage']}) - {r['detail']}")

    elif action == "verify-all":
        print("Verifying WL leads...")
        wl_stats, wl_results = batch_verify_wl()
        print(f"WL: {wl_stats}")
        print("\nVerifying RE leads...")
        re_stats, re_results = batch_verify_re()
        print(f"RE: {re_stats}")

    elif action == "check-bounces":
        print("Checking inbox for bounce-backs...")
        bounced = check_inbox_for_bounces()
        print(f"Found {len(bounced)} bounced emails:")
        for e in bounced:
            print(f"  {e}")
            append_bounce_log(e, "inbox-detected bounce", "inbox")

    elif action == "bounce-log":
        entries = load_bounce_log()
        print(f"Bounce log: {len(entries)} entries")
        for e in entries[-20:]:
            print(f"  {e['detected_at'][:16]} | {e['email']} | {e['source']} | {e['reason'][:60]}")

    else:
        print("Usage: python3 email_tracker.py [verify-wl|verify-re|verify-all|check-bounces|bounce-log]")
