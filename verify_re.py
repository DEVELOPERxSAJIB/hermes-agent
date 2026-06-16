"""
Quick RE email verification — syntax + MX only
"""
import json, os, sys
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
RE_PIPELINE_DIR = os.path.join(NANOSOFT_DIR, "re_pipeline")

def verify_email(email):
    from email_validator import validate_email, EmailNotValidError
    try:
        result = validate_email(email, check_deliverability=False)
        normalized = result.normalized
    except EmailNotValidError as ex:
        return "invalid", str(ex)
    domain = normalized.split('@')[1]
    try:
        import dns.resolver
        answers = dns.resolver.resolve(domain, 'MX', lifetime=5)
        if answers:
            return "valid", domain
    except:
        pass
    return "invalid", f"No MX for {domain}"

def main():
    sys.path.insert(0, NANOSOFT_DIR)
    sys.path.insert(0, RE_PIPELINE_DIR)
    from sheets import get_leads, update_status
    
    leads = get_leads()
    stats = {"valid": 0, "invalid": 0, "total": 0, "bounced": 0}
    invalid_leads = []
    
    for lead in leads:
        email = str(lead.get("Email", "")).strip()
        if not email or "@" not in email:
            continue
        lead_id = lead.get("Lead_ID")
        status = str(lead.get("Status", "")).strip()
        if status == "Bounced":
            stats["bounced"] += 1
            continue
        
        stats["total"] += 1
        brokerage = str(lead.get("Brokerage_Name", "")).strip()
        vstatus, detail = verify_email(email)
        
        if vstatus == "valid":
            stats["valid"] += 1
        else:
            stats["invalid"] += 1
            invalid_leads.append({"email": email, "brokerage": brokerage, "reason": detail, "lead_id": lead_id})
            if lead_id:
                update_status(lead_id, "Bounced")
    
    print(f"RE Verification Complete:")
    print(f"  Total: {stats['total']}")
    print(f"  Valid: {stats['valid']}")
    print(f"  Invalid: {stats['invalid']}")
    print(f"  Already Bounced: {stats['bounced']}")
    
    if invalid_leads:
        print(f"\nInvalid emails:")
        for l in invalid_leads:
            print(f"  {l['email']} ({l['brokerage']}) - {l['reason']}")

if __name__ == "__main__":
    main()
