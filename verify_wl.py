"""
Quick email verification — syntax + MX only (no SMTP probe)
"""
import json, os, sys, time
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
LOG_FILE = os.path.join(NANOSOFT_DIR, "verify_results.jsonl")

def verify_email(email):
    """Quick verify: syntax + MX record check."""
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
    from crm import NanoSoftCRM
    crm = NanoSoftCRM()
    leads = crm.get_wl_all()
    
    stats = {"valid": 0, "invalid": 0, "total": 0, "bounced": 0}
    invalid_leads = []
    
    for lead in leads:
        email = str(lead.get("Email", "")).strip()
        if not email or "@" not in email:
            continue
        if email.startswith("BOUNCED_"):
            stats["bounced"] += 1
            continue
        
        stats["total"] += 1
        company = str(lead.get("Company Name", "")).strip()
        status, detail = verify_email(email)
        
        if status == "valid":
            stats["valid"] += 1
        else:
            stats["invalid"] += 1
            invalid_leads.append({"email": email, "company": company, "reason": detail})
            # Mark as bounced in CRM
            crm.update_wl_lead(company, {"Status": "Bounced", "Email": f"BOUNCED_{email}"})
        
        # Log every 50
        if stats["total"] % 50 == 0:
            print(f"  Progress: {stats['total']} checked, {stats['valid']} valid, {stats['invalid']} invalid", flush=True)
    
    print(f"\nWL Verification Complete:")
    print(f"  Total: {stats['total']}")
    print(f"  Valid: {stats['valid']}")
    print(f"  Invalid: {stats['invalid']}")
    print(f"  Already Bounced: {stats['bounced']}")
    
    if invalid_leads:
        print(f"\nInvalid emails (first 30):")
        for l in invalid_leads[:30]:
            print(f"  {l['email']} ({l['company']}) - {l['reason']}")
    
    # Save results
    with open(LOG_FILE, "w") as f:
        json.dump({
            "stats": stats,
            "invalid": invalid_leads,
            "run_at": datetime.now(BD_TZ).isoformat()
        }, f, indent=2)
    print(f"\nResults saved to {LOG_FILE}")

if __name__ == "__main__":
    main()
