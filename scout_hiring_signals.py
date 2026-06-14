#!/usr/bin/python3
"""
NanoSoft Hiring Signal Scout v1
Finds agencies that are actively hiring by checking their careers/jobs pages.
These agencies are growing and more likely to need overflow help.

Strategy:
1. Take existing agency leads from CRM
2. Check each agency's website for /careers, /jobs, /join-us, /about pages
3. Look for hiring signals: job postings, "we are hiring", team growth
4. Score and prioritize: actively hiring = hot lead

Usage: python3 scout_hiring_signals.py
"""
import os, re, sys, time, json, signal
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
LOG_FILE = os.path.join(NANOSOFT_DIR, "hiring_scout.log")

sys.path.insert(0, NANOSOFT_DIR)

signal.signal(signal.SIGALRM, lambda *a: (_ for _ in ()).throw(TimeoutError("10min")))
signal.alarm(600)

def log(msg):
    ts = datetime.now(BD_TZ).strftime("%Y-%m-%d %H:%M")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def check_hiring_signals(website):
    """Check agency website for hiring signals. Returns (is_hiring, details)."""
    import urllib.request
    
    if not website:
        return False, ""
    
    if not website.startswith("http"):
        website = "https://" + website
    
    hiring_keywords = [
        "we are hiring", "join our team", "careers", "open positions",
        "we're hiring", "work with us", "join us", "talent wanted",
        "hiring now", "open roles", "job openings", "recruiting",
        "looking for", "want to join", "team is growing"
    ]
    
    # Pages to check for hiring signals
    pages_to_check = [
        "/careers", "/jobs", "/join-us", "/about", "/about-us",
        "/team", "/work-with-us", "/opportunities"
    ]
    
    found_signals = []
    
    # First check homepage
    try:
        req = urllib.request.Request(website, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode("utf-8", errors="ignore").lower()
            for kw in hiring_keywords:
                if kw in html:
                    found_signals.append(f"homepage: {kw}")
    except Exception:
        pass
    
    # Check careers/jobs pages
    for page in pages_to_check:
        if len(found_signals) >= 3:
            break
        try:
            url = website.rstrip("/") + page
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
            })
            with urllib.request.urlopen(req, timeout=8) as resp:
                html = resp.read().decode("utf-8", errors="ignore").lower()
                # Check for job posting patterns
                job_patterns = [
                    r'<h[1-4][^>]*>([^<]*(?:developer|engineer|designer|manager|lead|senior|junior)[^<]*)</h[1-4]>',
                    r'(?:apply now|apply here|send your cv|send your resume)',
                    r'(?:full-time|part-time|contract|remote|hybrid)',
                ]
                for pattern in job_patterns:
                    matches = re.findall(pattern, html)
                    if matches:
                        found_signals.append(f"{page}: {matches[0][:60]}")
                
                # Also check for hiring keywords
                for kw in hiring_keywords:
                    if kw in html:
                        found_signals.append(f"{page}: {kw}")
            time.sleep(0.3)
        except Exception:
            continue
    
    is_hiring = len(found_signals) > 0
    details = "; ".join(found_signals[:5]) if found_signals else ""
    return is_hiring, details

def main():
    log("=== HIRING SIGNAL SCOUT v1 ===")
    
    from crm import get_crm
    crm = get_crm()
    
    # Get all leads that have been emailed (T1 Sent) or are Qualified
    all_leads = crm.get_wl_all()
    
    # Focus on leads with websites that we've already emailed
    targets = []
    for lead in all_leads:
        status = lead.get("Status", "").strip()
        website = lead.get("Website", "").strip()
        email = lead.get("Email", "").strip()
        
        if not website or not email:
            continue
        if status in ("T1 Sent", "T2 Sent", "T3 Sent", "Qualified"):
            targets.append(lead)
    
    log(f"Checking {len(targets)} leads for hiring signals...")
    
    hiring_leads = []
    checked = 0
    
    for lead in targets:
        checked += 1
        company = lead.get("Company Name", "")
        website = lead.get("Website", "")
        
        is_hiring, details = check_hiring_signals(website)
        
        if is_hiring:
            hiring_leads.append({
                "company": company,
                "website": website,
                "email": lead.get("Email", ""),
                "status": lead.get("Status", ""),
                "services": lead.get("Services", ""),
                "signals": details,
                "country": lead.get("Country", ""),
            })
            log(f"  ✓ HIRING: {company} — {details[:80]}")
        
        if checked % 20 == 0:
            log(f"  Progress: {checked}/{len(targets)} checked, {len(hiring_leads)} hiring")
        
        time.sleep(0.5)
    
    log(f"\n=== RESULTS ===")
    log(f"Checked: {checked} leads")
    log(f"Actively hiring: {len(hiring_leads)}")
    
    if hiring_leads:
        log(f"\n=== HIRING LEADS (Priority for new outreach) ===")
        for i, hl in enumerate(hiring_leads, 1):
            log(f"{i}. {hl['company']} ({hl['country']})")
            log(f"   Email: {hl['email']}")
            log(f"   Services: {hl['services'][:60]}")
            log(f"   Signals: {hl['signals'][:100]}")
            log(f"   Current status: {hl['status']}")
            log("")
    
    # Save to file for email template generation
    output_file = os.path.join(NANOSOFT_DIR, "hiring_leads.json")
    with open(output_file, "w") as f:
        json.dump(hiring_leads, f, indent=2)
    log(f"Saved {len(hiring_leads)} hiring leads to {output_file}")
    
    return len(hiring_leads)

if __name__ == "__main__":
    try:
        count = main()
        print(f"HIRING_LEADS_FOUND: {count}")
    except TimeoutError:
        log("TIMEOUT: 10min limit")
        print("TIMEOUT")
    except Exception as e:
        log(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        print(f"ERROR: {e}")
