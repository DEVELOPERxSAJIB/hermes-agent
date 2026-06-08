#!/usr/bin/env python3
"""
NanoSoft PIPELINE ORCHESTRATOR v2
Independent cron jobs for each step. No LLM. No dependencies between steps.
Each script runs, does its job, exits. Cron handles scheduling.
"""
import json, os, sys, time, subprocess
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
LOG_DIR = os.path.join(NANOSOFT_DIR, "pipeline_logs")
os.makedirs(LOG_DIR, exist_ok=True)

def log(step, msg):
    ts = datetime.now(BD_TZ).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{step}] {msg}"
    print(line, flush=True)
    log_file = os.path.join(LOG_DIR, f"{step.lower()}.log")
    try:
        with open(log_file, 'a') as f:
            f.write(line + "\n")
    except:
        pass

def run_cmd(cmd, timeout=300, desc=""):
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=timeout, cwd=NANOSOFT_DIR
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        log("ERROR", f"TIMEOUT: {desc}")
        return "", "TIMEOUT", 1
    except Exception as e:
        log("ERROR", f"ERROR: {desc}: {e}")
        return "", str(e), 1


# ── STEP 1: SCOUT ──────────────────────────────────────────
def run_scout():
    log("SCOUT", "Starting scout...")
    stdout, stderr, rc = run_cmd(
        "python3 -u scout_wl_v5.py",
        timeout=900, desc="Scout WL v5"
    )
    scraped = added = 0
    for line in stdout.split('\n'):
        if 'DONE:' in line:
            try:
                scraped = int(line.split('scraped')[0].split()[-1]) if 'scraped' in line else 0
            except:
                pass
            try:
                added = int(line.split('+')[1].split('new')[0].strip()) if '+' in line else 0
            except:
                pass
        if 'CRM: +' in line:
            try:
                added = int(line.split('+')[1].split('new')[0].strip())
            except:
                pass
    log("SCOUT", f"DONE: {scraped} scraped, {added} added to CRM")
    return added


# ── STEP 2: ENRICH ─────────────────────────────────────────
def run_enrich():
    log("ENRICH", "Starting enrichment...")
    stdout, stderr, rc = run_cmd(
        "python3 -u enrich_wl_leads.py",
        timeout=600, desc="Enrich WL leads"
    )
    enriched = 0
    for line in stdout.split('\n'):
        if 'Enriched:' in line:
            try:
                enriched = int(line.split('Enriched:')[1].strip())
            except:
                pass
    log("ENRICH", f"DONE: {enriched} enriched")
    return enriched


# ── STEP 3: JUDGE ──────────────────────────────────────────
def run_judge():
    log("JUDGE", "Starting judge...")
    stdout, stderr, rc = run_cmd(
        "python3 -u judge_wl.py",
        timeout=120, desc="Judge WL leads"
    )
    qualified = 0
    for line in stdout.split('\n'):
        if 'Qualified:' in line:
            try:
                qualified = int(line.split('Qualified:')[1].strip())
            except:
                pass
    log("JUDGE", f"DONE: {qualified} qualified")
    return qualified


# ── STEP 4: SEND T1 ────────────────────────────────────────
def run_send_t1():
    log("SEND", "Starting T1 send...")
    stdout, stderr, rc = run_cmd(
        "python3 -u quill_wl.py send -t T1 --limit 50",
        timeout=1800, desc="QUILL-WL T1 send"
    )
    sent = failed = 0
    for line in stdout.split('\n'):
        if 'DONE:' in line:
            try:
                parts = line.split(',')
                for p in parts:
                    if 'sent' in p:
                        sent = int(p.split()[0])
                    if 'failed' in p:
                        failed = int(p.split()[0])
            except:
                pass
    log("SEND", f"T1 DONE: {sent} sent, {failed} failed")
    return sent


# ── STEP 5: SEND T2 (follow-up) ────────────────────────────
def run_send_t2():
    log("SEND", "Starting T2 follow-up...")
    stdout, stderr, rc = run_cmd(
        "python3 -u quill_wl.py send -t T2 --limit 50",
        timeout=1800, desc="QUILL-WL T2 send"
    )
    sent = failed = 0
    for line in stdout.split('\n'):
        if 'DONE:' in line:
            try:
                parts = line.split(',')
                for p in parts:
                    if 'sent' in p:
                        sent = int(p.split()[0])
                    if 'failed' in p:
                        failed = int(p.split()[0])
            except:
                pass
    log("SEND", f"T2 DONE: {sent} sent, {failed} failed")
    return sent


# ── STEP 6: SEND T3 ────────────────────────────────────────
def run_send_t3():
    log("SEND", "Starting T3 follow-up...")
    stdout, stderr, rc = run_cmd(
        "python3 -u quill_wl.py send -t T3 --limit 50",
        timeout=1800, desc="QUILL-WL T3 send"
    )
    sent = failed = 0
    for line in stdout.split('\n'):
        if 'DONE:' in line:
            try:
                parts = line.split(',')
                for p in parts:
                    if 'sent' in p:
                        sent = int(p.split()[0])
                    if 'failed' in p:
                        failed = int(p.split()[0])
            except:
                pass
    log("SEND", f"T3 DONE: {sent} sent, {failed} failed")
    return sent


# ── STEP 7: SEND T4 ────────────────────────────────────────
def run_send_t4():
    log("SEND", "Starting T4 breakup...")
    stdout, stderr, rc = run_cmd(
        "python3 -u quill_wl.py send -t T4 --limit 50",
        timeout=1800, desc="QUILL-WL T4 send"
    )
    sent = failed = 0
    for line in stdout.split('\n'):
        if 'DONE:' in line:
            try:
                parts = line.split(',')
                for p in parts:
                    if 'sent' in p:
                        sent = int(p.split()[0])
                    if 'failed' in p:
                        failed = int(p.split()[0])
            except:
                pass
    log("SEND", f"T4 DONE: {sent} sent, {failed} failed")
    return sent


# ── STEP 8: REPLY MONITOR ──────────────────────────────────
def run_reply_monitor():
    log("REPLY", "Starting reply monitor...")
    stdout, stderr, rc = run_cmd(
        "python3 -u reply_monitor_wl.py",
        timeout=120, desc="Reply monitor"
    )
    new_replies = 0
    for line in stdout.split('\n'):
        if 'REPLY:' in line:
            new_replies += 1
    log("REPLY", f"DONE: {new_replies} new replies")
    return new_replies


# ── STATUS REPORT ──────────────────────────────────────────
def get_stats():
    try:
        sys.path.insert(0, NANOSOFT_DIR)
        from crm import get_crm
        crm = get_crm()
        leads = crm.get_wl_all()
        from collections import Counter
        counts = Counter(l.get('Status', '') for l in leads)
        total = len(leads)
        sent_log = os.path.join(NANOSOFT_DIR, "emails_sent_wl.jsonl")
        total_sent = 0
        try:
            with open(sent_log) as f:
                total_sent = sum(1 for line in f if line.strip())
        except:
            pass
        return {
            "total": total,
            "total_sent": total_sent,
            "qualified": counts.get("Qualified", 0),
            "t1_sent": counts.get("T1 Sent", 0),
            "t2_sent": counts.get("T2 Sent", 0),
            "t3_sent": counts.get("T3 Sent", 0),
            "t4_sent": counts.get("T4 Sent", 0),
            "new": counts.get("New", 0),
            "unqualified": counts.get("Unqualified", 0),
            "bounced": counts.get("Bounced", 0),
        }
    except:
        return {}


# ── MAIN ───────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='NanoSoft Pipeline v2')
    parser.add_argument('step', choices=[
        'scout', 'enrich', 'judge', 'send-t1', 'send-t2', 'send-t3', 'send-t4',
        'reply', 'full', 'status'
    ])
    args = parser.parse_args()

    start = datetime.now(BD_TZ)

    if args.step == 'scout':
        run_scout()
    elif args.step == 'enrich':
        run_enrich()
    elif args.step == 'judge':
        run_judge()
    elif args.step == 'send-t1':
        run_send_t1()
    elif args.step == 'send-t2':
        run_send_t2()
    elif args.step == 'send-t3':
        run_send_t3()
    elif args.step == 'send-t4':
        run_send_t4()
    elif args.step == 'reply':
        run_reply_monitor()
    elif args.step == 'full':
        log("FULL", "=== FULL PIPELINE START ===")
        run_scout()
        time.sleep(10)
        run_enrich()
        time.sleep(10)
        run_judge()
        time.sleep(10)
        run_send_t1()
        time.sleep(10)
        run_send_t2()
        time.sleep(10)
        run_reply_monitor()
        log("FULL", "=== FULL PIPELINE COMPLETE ===")
    elif args.step == 'status':
        stats = get_stats()
        if stats:
            print(f"\nNanoSoft Pipeline Status")
            print(f"{'='*40}")
            for k, v in stats.items():
                print(f"  {k}: {v}")
        else:
            print("Could not load stats")

    # Always print stats at end
    stats = get_stats()
    if stats:
        log("STATS", f"Total: {stats.get('total',0)} | Sent: {stats.get('total_sent',0)} | "
                    f"Qualified: {stats.get('qualified',0)} | T1: {stats.get('t1_sent',0)} | "
                    f"T2: {stats.get('t2_sent',0)} | T3: {stats.get('t3_sent',0)} | "
                    f"T4: {stats.get('t4_sent',0)} | New: {stats.get('new',0)}")
