#!/usr/bin/env python3
"""
AUTO-AUDIT: Full system health check
Runs every 6 hours via cron. Finds problems, fixes them, reports.
"""
import json
import os
import re
import sys
import time
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
SENT_LOG_WL = os.path.join(NANOSOFT_DIR, "emails_sent_wl.jsonl")
SENT_LOG_RE = os.path.join(NANOSOFT_DIR, "emails_sent_re.jsonl")
PENDING_FILE = os.path.join(NANOSOFT_DIR, "pending_t1_resume.json")
LOG_FILE = os.path.join(NANOSOFT_DIR, "audit.log")

sys.path.insert(0, NANOSOFT_DIR)

def log(msg):
    ts = datetime.now(BD_TZ).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def check_crm_health():
    """Check WL CRM for data issues."""
    from crm import get_crm
    crm = get_crm()
    leads = crm.get_wl_all()
    
    issues = []
    fixes = []
    
    # Count by status
    status_counts = {}
    for l in leads:
        s = l.get('Status', 'Unknown')
        status_counts[s] = status_counts.get(s, 0) + 1
    
    # Check for bad emails (image filenames, JS files, etc.)
    bad_email_patterns = [
        r'@2x\.(png|jpg|gif|webp|svg)$',
        r'@3x\.(png|jpg|gif|webp|svg)$',
        r'\.(js|css|woff|ttf|mjs|json)@',
        r'^[0-9a-f]{20,}@',  # hex hash local part
    ]
    
    bad_emails = []
    for lead in leads:
        email = str(lead.get('Email', ''))
        status = str(lead.get('Status', ''))
        if status in ('Lost', 'Bounced'):
            continue
        for pat in bad_email_patterns:
            if re.search(pat, email, re.IGNORECASE):
                bad_emails.append((lead.get('Company Name', ''), email, status))
                break
    
    if bad_emails:
        issues.append(f"Found {len(bad_emails)} leads with bad email addresses")
        # Fix: mark as Bounced
        for company, email, status in bad_emails:
            try:
                # Strip any existing BOUNCED_ prefix to avoid stacking
                clean_email = email
                while clean_email.startswith('BOUNCED_'):
                    clean_email = clean_email[len('BOUNCED_'):]
                crm.update_wl_lead(company, {'Status': 'Bounced', 'Email': f'BOUNCED_{clean_email}'})
                fixes.append(f"Marked {company[:30]} as Bounced (bad email: {email[:40]})")
            except:
                pass
    
    # Check for double BOUNCED emails
    double_bounced = []
    for lead in leads:
        email = str(lead.get('Email', ''))
        if email.startswith('BOUNCED_BOUNCED_'):
            double_bounced.append((lead.get('Company Name', ''), email))
    
    if double_bounced:
        issues.append(f"Found {len(double_bounced)} double-BOUNCED emails")
        for company, email in double_bounced:
            actual = email
            while actual.startswith('BOUNCED_'):
                actual = actual[len('BOUNCED_'):]
            actual = actual.strip().lower()
            if '@' in actual and '.' in actual:
                try:
                    crm.update_wl_lead(company, {'Email': actual})
                    fixes.append(f"Cleaned double-BOUNCED: {company[:30]} -> {actual}")
                except:
                    pass
    
    # Check for Unqualified leads with high scores (should be New)
    requalified = 0
    for lead in leads:
        if lead.get('Status') != 'Unqualified':
            continue
        score = str(lead.get('Judge Score', ''))
        if score and score.isdigit() and int(score) >= 7:
            company = lead.get('Company Name', '')
            try:
                crm.update_wl_lead(company, {'Status': 'New'})
                requalified += 1
            except:
                pass
    
    if requalified > 0:
        fixes.append(f"Requalified {requalified} Unqualified leads (score>=7) to New")
    
    return status_counts, issues, fixes

def check_sent_log_health():
    """Check sent logs for duplicates and corruption."""
    issues = []
    fixes = []
    
    for fname in [SENT_LOG_WL, SENT_LOG_RE]:
        if not os.path.exists(fname):
            issues.append(f"Missing sent log: {fname}")
            continue
        
        entries = []
        seen = set()
        dupes = 0
        corrupt = 0
        
        with open(fname) as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    e = json.loads(line)
                    key = f"{e.get('to','').lower()}|{e.get('template','')}"
                    if key not in seen:
                        seen.add(key)
                        entries.append(line.strip())
                    else:
                        dupes += 1
                except:
                    corrupt += 1
        
        if dupes > 0:
            issues.append(f"{os.path.basename(fname)}: {dupes} duplicate entries")
            # Dedup in place
            import shutil
            shutil.copy(fname, fname + '.bak')
            with open(fname, 'w') as f:
                for e in entries:
                    f.write(e + '\n')
            fixes.append(f"Deduped {os.path.basename(fname)}: removed {dupes} duplicates")
        
        if corrupt > 0:
            issues.append(f"{os.path.basename(fname)}: {corrupt} corrupt lines")
    
    return issues, fixes

def check_pending_file():
    """Check if pending T1 file is valid."""
    if not os.path.exists(PENDING_FILE):
        return [], []
    
    try:
        with open(PENDING_FILE) as f:
            pending = json.load(f)
        
        # Validate entries
        valid = []
        invalid = []
        for p in pending:
            email = p.get('email', '')
            if '@' in email and '.' in email:
                valid.append(p)
            else:
                invalid.append(p.get('company', 'unknown'))
        
        if invalid:
            # Rewrite with only valid entries
            with open(PENDING_FILE, 'w') as f:
                json.dump(valid, f, indent=2)
            return [f"Removed {len(invalid)} invalid entries from pending file"], [f"Cleaned pending file: {invalid}"]
        
        return [], []
    except json.JSONDecodeError:
        # Corrupt file — back up and delete
        os.rename(PENDING_FILE, PENDING_FILE + '.corrupt')
        return ["Pending file was corrupt"], ["Backed up corrupt pending file"]
    except Exception as e:
        return [f"Pending file error: {e}"], []

def check_daily_send_count():
    """Check if we're near the daily limit."""
    from datetime import datetime
    today = datetime.now(BD_TZ).strftime("%Y-%m-%d")
    count = 0
    for path in [SENT_LOG_WL, SENT_LOG_RE]:
        try:
            with open(path) as f:
                for line in f:
                    if line.strip() and today in line:
                        count += 1
        except:
            pass
    
    if count >= 40:
        return [f"Daily limit reached: {count}/40"], []
    return [], [f"Daily sends: {count}/40"]

def check_cron_health():
    """Check if all cron scripts exist and are importable."""
    scripts = [
        'unified_daily.py',
        'scout_wl.py',
        'resume_t1.py',
        'auto_audit.py',
        'gmail_utils.py',
        'email_tracker.py',
        'crm.py',
        'sheets.py',
        'quill_wl.py',
    ]
    
    issues = []
    for script in scripts:
        path = os.path.join(NANOSOFT_DIR, script)
        if not os.path.exists(path):
            issues.append(f"Missing script: {script}")
        else:
            # Syntax check
            r = subprocess.run(
                [sys.executable, '-c', f'import ast; ast.parse(open("{path}").read())'],
                capture_output=True, timeout=10
            )
            if r.returncode != 0:
                issues.append(f"Syntax error in {script}: {r.stderr.decode()[:100]}")
    
    return issues, []

def main():
    log("=" * 60)
    log("AUTO-AUDIT START")
    log("=" * 60)
    
    all_issues = []
    all_fixes = []
    
    # 1. CRM Health
    log("Checking CRM health...")
    try:
        status_counts, issues, fixes = check_crm_health()
        all_issues.extend(issues)
        all_fixes.extend(fixes)
        log(f"  Status: {status_counts}")
        for i in issues:
            log(f"  ISSUE: {i}")
        for f in fixes:
            log(f"  FIX: {f}")
    except Exception as e:
        log(f"  ERROR: {e}")
        all_issues.append(f"CRM check failed: {e}")
    
    # 2. Sent Log Health
    log("Checking sent logs...")
    try:
        issues, fixes = check_sent_log_health()
        all_issues.extend(issues)
        all_fixes.extend(fixes)
        for i in issues:
            log(f"  ISSUE: {i}")
        for f in fixes:
            log(f"  FIX: {f}")
    except Exception as e:
        log(f"  ERROR: {e}")
    
    # 3. Pending File
    log("Checking pending file...")
    try:
        issues, fixes = check_pending_file()
        all_issues.extend(issues)
        all_fixes.extend(fixes)
    except Exception as e:
        log(f"  ERROR: {e}")
    
    # 4. Daily Send Count
    log("Checking daily send count...")
    try:
        issues, info = check_daily_send_count()
        all_issues.extend(issues)
        for i in info:
            log(f"  {i}")
    except Exception as e:
        log(f"  ERROR: {e}")
    
    # 5. Cron Script Health
    log("Checking cron scripts...")
    try:
        issues, _ = check_cron_health()
        all_issues.extend(issues)
        for i in issues:
            log(f"  ISSUE: {i}")
        if not issues:
            log("  All scripts OK")
    except Exception as e:
        log(f"  ERROR: {e}")
    
    # Summary
    log("=" * 60)
    if all_issues:
        log(f"AUDIT COMPLETE: {len(all_issues)} issues found, {len(all_fixes)} fixed")
    else:
        log("AUDIT COMPLETE: All systems healthy ✓")
    log("=" * 60)
    
    # Return summary for cron delivery
    return {
        "issues": all_issues,
        "fixes": all_fixes,
        "status_counts": status_counts if 'status_counts' in dir() else {},
    }

if __name__ == "__main__":
    result = main()
    # Print summary as last line for cron
    print(f"\nAUDIT_SUMMARY: {json.dumps({'issues_count': len(result['issues']), 'fixes_count': len(result['fixes'])})}")
