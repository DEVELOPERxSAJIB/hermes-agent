#!/usr/bin/env python3
"""
NanoSoft AUTO-PILOT v1 — 24/7 Lead Generation + Outreach Engine
Runs continuously via cron every 6 hours:
1. Scout new WL agency leads from multiple sources
2. Enrich: scrape emails, services, WL signals
3. Judge: score each lead
4. Send: T1 emails to qualified leads
5. Track: replies, update CRM
6. Report: send summary to CEO via Telegram

This script is designed to run autonomously 24/7 on a VPS.
"""
import json, os, sys, time, subprocess
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
LOG_FILE = os.path.join(NANOSOFT_DIR, "autopilot.log")
REPORT_FILE = os.path.join(NANOSOFT_DIR, "autopilot_latest_report.txt")

sys.path.insert(0, NANOSOFT_DIR)

def log(msg):
    ts = datetime.now(BD_TZ).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [AUTOPILOT] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, 'a') as f:
            f.write(line + "\n")
    except:
        pass

def run_cmd(cmd, timeout=300, desc=""):
    """Run a command and return (stdout, stderr, returncode)."""
    if desc:
        log(f"Running: {desc}")
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=NANOSOFT_DIR
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        log(f"TIMEOUT: {desc}")
        return "", "TIMEOUT", 1
    except Exception as e:
        log(f"ERROR: {desc}: {e}")
        return "", str(e), 1

def get_crm_stats():
    """Get current CRM statistics."""
    try:
        from crm import get_crm
        crm = get_crm()
        wl = crm.get_wl_all()
        stats = {"total": len(wl), "by_status": {}}
        for l in wl:
            s = l.get("Status", "Empty")
            stats["by_status"][s] = stats["by_status"].get(s, 0) + 1
        return stats
    except:
        return {"total": 0, "by_status": {}}

def get_sent_count():
    """Count total sent emails."""
    sent_log = os.path.join(NANOSOFT_DIR, "emails_sent_wl.jsonl")
    try:
        with open(sent_log) as f:
            return sum(1 for line in f if line.strip())
    except:
        return 0

def get_reply_count():
    """Count replies received."""
    reply_log = os.path.join(NANOSOFT_DIR, "replies_wl.jsonl")
    try:
        with open(reply_log) as f:
            return sum(1 for line in f if line.strip())
    except:
        return 0

def send_telegram_report(report_text):
    """Send report via Telegram using the hermes CLI."""
    try:
        # Write report to temp file
        report_path = os.path.join(NANOSOFT_DIR, "latest_report.txt")
        with open(report_path, 'w') as f:
            f.write(report_text)
        log(f"Report saved to {report_path}")
        # Note: Actual sending is done by the cron job's delivery mechanism
        return True
    except:
        return False

def main():
    start_time = datetime.now(BD_TZ)
    log(f"====== AUTO-PILOT CYCLE START ======")
    
    report_lines = []
    report_lines.append("NanoSoft Auto-Pilot Report")
    report_lines.append(f"Time: {start_time.strftime('%Y-%m-%d %H:%M')} BD Time")
    report_lines.append("=" * 50)
    
    # ── STEP 1: Check current state ──
    log("STEP 1: Checking CRM state...")
    stats = get_crm_stats()
    sent_total = get_sent_count()
    reply_total = get_reply_count()
    
    log(f"CRM: {stats['total']} total WL leads")
    for s, c in sorted(stats.get("by_status", {}).items()):
        log(f"  {s}: {c}")
    log(f"Emails sent (log): {sent_total} | Replies: {reply_total}")
    
    report_lines.append(f"\nCurrent Pipeline:")
    for s, c in sorted(stats.get("by_status", {}).items()):
        report_lines.append(f"  {s}: {c}")
    report_lines.append(f"Total sent: {sent_total}")
    report_lines.append(f"Replies: {reply_total}")
    
    # ── STEP 2: Scout new leads ──
    log("STEP 2: Scouting new WL leads...")
    report_lines.append("\n--- Step 2: Scouting ---")
    
    # Try v4 first (ddgs CLI), fallback to v3
    scout_script = os.path.join(NANOSOFT_DIR, "scout_wl_v4.py")
    if not os.path.exists(scout_script):
        scout_script = os.path.join(NANOSOFT_DIR, "scout_wl_v3.py")
    if os.path.exists(scout_script):
        scout_name = os.path.basename(scout_script)
        stdout, stderr, rc = run_cmd(
            f"cd {NANOSOFT_DIR} && python3 -u {scout_name}",
            timeout=600, desc=f"SCOUT ({scout_name})"
        )
        # Parse results from output
        scraped = 0
        emails_found = 0
        added = 0
        for line in stdout.split('\n'):
            if 'DONE:' in line:
                scraped = int(re.search(r'(\d+) scraped', line).group(1)) if re.search(r'(\d+) scraped', line) else 0
                emails_found = int(re.search(r'(\d+) emails', line).group(1)) if re.search(r'(\d+) emails', line) else 0
            if 'CRM: +' in line:
                added = int(re.search(r'\+(\d+) new', line).group(1)) if re.search(r'\+(\d+) new', line) else 0
        
        log(f"Scout result: {scraped} scraped, {emails_found} emails, {added} added to CRM")
        report_lines.append(f"Scraped: {scraped} | Emails: {emails_found} | CRM added: {added}")
    else:
        log("Scout script not found, using fallback...")
        report_lines.append("Scout: script not found")
    
    # ── STEP 3: Enrich new leads ──
    log("STEP 3: Enriching new leads...")
    report_lines.append("\n--- Step 3: Enriching ---")
    
    enrich_script = os.path.join(NANOSOFT_DIR, "enrich_wl_leads.py")
    if os.path.exists(enrich_script):
        stdout, stderr, rc = run_cmd(
            f"cd {NANOSOFT_DIR} && python3 -u enrich_wl_leads.py",
            timeout=300, desc="Enrich WL leads"
        )
        enriched = 0
        for line in stdout.split('\n'):
            if 'Enriched:' in line:
                enriched = int(re.search(r'Enriched: (\d+)', line).group(1)) if re.search(r'Enriched: (\d+)', line) else 0
        log(f"Enriched: {enriched} leads")
        report_lines.append(f"Enriched: {enriched}")
    else:
        report_lines.append("Enrich: script not found")
    
    # ── STEP 4: Judge leads ──
    log("STEP 4: Judging new leads...")
    report_lines.append("\n--- Step 4: Judging ---")
    
    judge_script = os.path.join(NANOSOFT_DIR, "judge_wl.py")
    if os.path.exists(judge_script):
        stdout, stderr, rc = run_cmd(
            f"cd {NANOSOFT_DIR} && python3 -u judge_wl.py",
            timeout=60, desc="Judge WL leads"
        )
        qualified = 0
        for line in stdout.split('\n'):
            if 'Qualified:' in line:
                qualified = int(re.search(r'Qualified: (\d+)', line).group(1)) if re.search(r'Qualified: (\d+)', line) else 0
        log(f"Judge result: {qualified} qualified")
        report_lines.append(f"Qualified: {qualified}")
    else:
        report_lines.append("Judge: script not found")
    
    # ── STEP 5: Send T1 to new qualified leads ──
    log("STEP 5: Sending T1 to new qualified leads...")
    report_lines.append("\n--- Step 5: Sending ---")
    
    new_qualified = stats.get("by_status", {}).get("Qualified", 0)
    if new_qualified > 0:
        log(f"{new_qualified} new qualified leads. Sending T1...")
        stdout, stderr, rc = run_cmd(
            f"cd {NANOSOFT_DIR} && python3 -u quill_wl.py send -t T1 --limit 10",
            timeout=600, desc="QUILL-WL T1 send"
        )
        sent = 0
        failed = 0
        for line in stdout.split('\n'):
            if 'DONE:' in line:
                sent = int(re.search(r'(\d+) sent', line).group(1)) if re.search(r'(\d+) sent', line) else 0
                failed = int(re.search(r'(\d+) failed', line).group(1)) if re.search(r'(\d+) failed', line) else 0
        log(f"T1 send result: {sent} sent, {failed} failed")
        report_lines.append(f"T1 sent: {sent} | Failed: {failed}")
    else:
        log("No new qualified leads to send.")
        report_lines.append("No new qualified leads.")
    
    # ── STEP 6: Check replies ──
    log("STEP 6: Checking for replies...")
    report_lines.append("\n--- Step 6: Replies ---")
    
    reply_script = os.path.join(NANOSOFT_DIR, "reply_monitor_wl.py")
    if os.path.exists(reply_script):
        stdout, stderr, rc = run_cmd(
            f"cd {NANOSOFT_DIR} && python3 -u reply_monitor_wl.py",
            timeout=60, desc="Reply monitor"
        )
        new_replies = 0
        for line in stdout.split('\n'):
            if 'REPLY:' in line:
                new_replies += 1
                log(f"  New reply: {line.strip()}")
        log(f"Reply check: {new_replies} new replies")
        report_lines.append(f"New replies: {new_replies}")
    
    # ── STEP 7: Handle replies ──
    log("STEP 7: Processing replies...")
    report_lines.append("\n--- Step 7: Reply Handling ---")
    
    try:
        from crm import get_crm
        crm = get_crm()
        wl = crm.get_wl_all()
        interested = [l for l in wl if l.get('Reply Status') == 'Interested']
        
        if interested:
            log(f"⚠ {len(interested)} INTERESTED leads need attention!")
            report_lines.append(f"\n⚠⚠⚠ INTERESTED LEADS: {len(interested)} ⚠⚠⚠")
            for l in interested:
                company = l.get('Company Name', '')
                email = l.get('Email', '')
                snippet = l.get('Reply Snippet', '')
                log(f"  {company} | {email} | {snippet[:80]}")
                report_lines.append(f"  {company} | {email}")
                report_lines.append(f"    {snippet[:100]}")
        else:
            report_lines.append("No interested replies yet.")
    except:
        pass
    
    # ── FINAL: Summary ──
    end_time = datetime.now(BD_TZ)
    duration = (end_time - start_time).total_seconds()
    
    final_stats = get_crm_stats()
    final_sent = get_sent_count()
    final_replies = get_reply_count()
    
    report_lines.append("\n" + "=" * 50)
    report_lines.append("CYCLE SUMMARY")
    report_lines.append(f"Duration: {duration:.0f}s")
    report_lines.append(f"Total WL leads: {final_stats['total']}")
    report_lines.append(f"Total sent: {final_sent}")
    report_lines.append(f"Total replies: {final_replies}")
    report_lines.append(f"Next run: ~6 hours")
    
    report = "\n".join(report_lines)
    
    # Save report
    with open(REPORT_FILE, 'w') as f:
        f.write(report)
    
    log(f"====== CYCLE COMPLETE ({duration:.0f}s) ======")
    log(f"Total sent: {final_sent} | Replies: {final_replies}")
    
    print(report)  # For cron delivery

if __name__ == "__main__":
    import re
    main()
