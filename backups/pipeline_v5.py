#!/usr/bin/env python3
"""
NanoSoft Daily Pipeline v5 — FULL AUTO
SCOUT → JUDGE → QUILL(draft to Gmail) → (Chairman reviews) → SEND

Flow:
1. SCOUT: Find 30 new local business leads (Playwright + DDG)
2. JUDGE: Score 1-10, approve 7+, reject <7
3. QUILL: Draft emails for all Qualified → save to Gmail Drafts + CRM status = "Drafted"
4. CHAIRMAN: Reviews drafts in Gmail, runs !send all
5. QUILL: Sends 1-by-1 with 3-min gap

No compromise. Runs every single day.
"""
import sys, os, json, time, subprocess
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
LOG_FILE = os.path.join(NANOSOFT_DIR, "pipeline_v5.log")
STATE_FILE = os.path.join(NANOSOFT_DIR, "pipeline_v5_state.json")

sys.path.insert(0, NANOSOFT_DIR)

def log(msg):
    ts = datetime.now(BD_TZ).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, 'a') as f:
            f.write(line + "\n")
    except:
        pass

def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except:
        return {"last_run": "", "runs": 0, "total_scouted": 0, "total_qualified": 0, "total_drafted": 0, "total_sent": 0}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def run_phase(cmd, timeout=600):
    """Run a phase as subprocess."""
    log(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=NANOSOFT_DIR)
        output = result.stdout[-2000:] if result.stdout else ""
        if result.returncode != 0:
            log(f"  ERROR (exit {result.returncode}): {result.stderr[:500]}")
        return output, result.returncode
    except subprocess.TimeoutExpired:
        log(f"  TIMEOUT after {timeout}s")
        return "", 1
    except Exception as e:
        log(f"  EXCEPTION: {e}")
        return "", 1

def get_crm_counts():
    """Get current lead counts from CRM."""
    try:
        from crm import get_crm
        crm = get_crm()
        return {
            'new': len(crm.get_leads_by_status('New')),
            'qualified': len(crm.get_leads_by_status('Qualified')),
            'drafted': len(crm.get_leads_by_status('Drafted')),
            'sent': len(crm.get_leads_by_status('Email Sent')),
            'total': crm.count_leads(),
        }
    except:
        return {}

def run_full_pipeline(target=30):
    """Run the full daily pipeline."""
    today = datetime.now(BD_TZ).strftime("%Y-%m-%d")
    state = load_state()
    
    log(f"\n{'='*60}")
    log(f"[PIPELINE] Daily Run — {today}")
    log(f"{'='*60}")
    
    # Check if already ran today
    if state.get("last_run") == today:
        log("[PIPELINE] Already ran today. Skipping.")
        return
    
    counts_before = get_crm_counts()
    log(f"[PIPELINE] CRM before: {counts_before}")
    
    # ── PHASE 1: SCOUT ──
    log("\n── PHASE 1: SCOUT ──")
    output, rc = run_phase(["python3", "scout_v12.py", "--niche", "dentist", "--city", "Dallas", "--target", str(target)])
    log(output[-500:] if output else "No output")
    
    # ── PHASE 2: JUDGE ──
    log("\n── PHASE 2: JUDGE ──")
    output, rc = run_phase(["python3", "judge_v3.py"])
    log(output[-500:] if output else "No output")
    
    # ── PHASE 3: QUILL (draft to Gmail + CRM) ──
    log("\n── PHASE 3: QUILL ──")
    output, rc = run_phase(["python3", "quill_v11.py", "draft"])
    log(output[-1000:] if output else "No output")
    
    # ── SUMMARY ──
    counts_after = get_crm_counts()
    
    # Update state
    state["last_run"] = today
    state["runs"] = state.get("runs", 0) + 1
    state["total_scouted"] = state.get("total_scouted", 0) + max(0, counts_after.get('new',0) - counts_before.get('new',0))
    state["total_qualified"] = state.get("total_qualified", 0) + max(0, counts_after.get('qualified',0) - counts_before.get('qualified',0))
    state["total_drafted"] = state.get("total_drafted", 0) + max(0, counts_after.get('drafted',0) - counts_before.get('drafted',0))
    save_state(state)
    
    log(f"\n{'='*60}")
    log(f"[PIPELINE] COMPLETE — {today}")
    log(f"  New leads: {counts_after.get('new', '?')}")
    log(f"  Qualified: {counts_after.get('qualified', '?')}")
    log(f"  Drafted:   {counts_after.get('drafted', '?')}")
    log(f"  Sent:      {counts_after.get('sent', '?')}")
    log(f"  Total:     {counts_after.get('total', '?')}")
    log(f"{'='*60}")
    
    # Build report for Discord
    report = {
        "date": today,
        "new_leads": counts_after.get('new', 0),
        "qualified": counts_after.get('qualified', 0),
        "drafted": counts_after.get('drafted', 0),
        "sent": counts_after.get('sent', 0),
        "total": counts_after.get('total', 0),
        "market": "dentist+Dallas",
    }
    
    log(f"[REPORT] {json.dumps(report)}")
    return report

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', nargs='?', default='full', 
                        choices=['full','scout','judge','draft','send'],
                        help='Pipeline phase to run')
    parser.add_argument('--target', type=int, default=30)
    parser.add_argument('--delay', type=int, default=180)
    args = parser.parse_args()
    
    if args.phase == 'full':
        report = run_full_pipeline(target=args.target)
    elif args.phase == 'scout':
        output, rc = run_phase(["python3", "scout_v12.py", "--target", str(args.target)])
        print(output)
    elif args.phase == 'judge':
        output, rc = run_phase(["python3", "judge_v3.py"])
        print(output)
    elif args.phase == 'draft':
        output, rc = run_phase(["python3", "quill_v11.py", "draft"])
        print(output)
    elif args.phase == 'send':
        from quill_v11 import send_all_pending
        ok, fail = send_all_pending(delay=args.delay)
        print(f"Sent: {ok}, Failed: {fail}")
