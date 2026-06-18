#!/usr/bin/env python3
"""
Resume pending T1 sends from pending_t1_resume.json
Sends to WL leads that were queued due to Gmail daily limit.
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib
import ssl

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
PENDING_FILE = os.path.join(NANOSOFT_DIR, "pending_t1_resume.json")
SENT_LOG = os.path.join(NANOSOFT_DIR, "emails_sent_wl.jsonl")
LOG_FILE = os.path.join(NANOSOFT_DIR, "pipeline.log")

sys.path.insert(0, NANOSOFT_DIR)

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "nanosoftagency007@gmail.com"
SMTP_PASS = "wgxo ddup cdol kupl"

# Daily limit safety — stop if we've sent 40 today
MAX_DAILY_TOTAL = 40


def count_today_sends():
    today = datetime.now(BD_TZ).strftime("%Y-%m-%d")
    count = 0
    for path in [SENT_LOG, os.path.join(NANOSOFT_DIR, "emails_sent_re.jsonl")]:
        try:
            with open(path) as f:
                for line in f:
                    if line.strip() and today in line:
                        count += 1
        except:
            pass
    return count


def send_smtp(to_email, subject, body):
    try:
        msg = MIMEMultipart()
        msg["From"] = "SaJib Shikder <nanosoftagency007@gmail.com>"
        msg["To"] = to_email
        msg["Subject"] = subject.replace("\n", " ").strip()
        msg.attach(MIMEText(body, "plain", "utf-8"))
        ctx = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls(context=ctx)
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)
        return True, ""
    except Exception as e:
        return False, str(e)[:200]


def append_sent_log(to_email, company, subject, template):
    with open(SENT_LOG, "a") as f:
        f.write(json.dumps({
            "to": to_email, "company": company,
            "subject": subject, "template": template,
            "sent_at": datetime.now(BD_TZ).isoformat(),
        }) + "\n")


def log(msg):
    ts = datetime.now(BD_TZ).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def main():
    # Check daily limit
    today_count = count_today_sends()
    if today_count >= MAX_DAILY_TOTAL:
        log(f"DAILY LIMIT REACHED: {today_count}/{MAX_DAILY_TOTAL}. Skipping resume.")
        return

    # Load pending
    if not os.path.exists(PENDING_FILE):
        log("No pending_t1_resume.json found. Nothing to do.")
        return

    with open(PENDING_FILE) as f:
        pending = json.load(f)

    log(f"RESUME T1: {len(pending)} pending leads. Today sends so far: {today_count}/{MAX_DAILY_TOTAL}")

    # Load sent log for dedup
    sent_log = set()
    try:
        with open(SENT_LOG) as f:
            for line in f:
                if line.strip():
                    e = json.loads(line)
                    sent_log.add(f"{e.get('to','').lower()}|T1")
    except:
        pass

    from crm import get_crm
    crm = get_crm()

    sent = 0
    failed = 0
    remaining = []

    for i, p in enumerate(pending):
        company = p["company"]
        email = p["email"].strip()
        key = f"{email.lower()}|T1"

        if key in sent_log:
            log(f"[{i+1}] SKIP (already sent): {company}")
            continue

        # Check daily limit mid-run
        if count_today_sends() >= MAX_DAILY_TOTAL:
            log(f"Daily limit reached mid-run. Saving {len(pending)-i} remaining.")
            remaining = pending[i:]
            break

        first = "there"
        if "@" in email:
            local = email.split("@")[0]
            name = re.split(r"[._]", local)[0]
            first = name.capitalize() if name else "there"

        subject = f"Quick note about {company}"
        body = f"""Hi {first},

I was looking at {company} online.

You seem to be doing solid work, but I wanted to reach out because I noticed you might be handling a lot of projects in-house.

We are NanoSoft. We help agencies like yours with white label web development, custom software, and CRM projects. Your brand stays on everything. Your clients never know.

Typical turnaround is 4 weeks. Full handoff. You take the credit.

Worth a 15 minute call this week?

SaJib Shikder
NanoSoft | nanosoft.agency"""

        log(f"[{i+1}/{len(pending)}] {company[:35]} | {email}")
        ok, err = send_smtp(email, subject, body)
        if ok:
            append_sent_log(email, company, subject, "T1")
            try:
                crm.update_wl_lead(company, {
                    "Status": "T1 Sent",
                    "Sent date": datetime.now(BD_TZ).strftime("%Y-%m-%d")
                })
            except:
                pass
            sent += 1
            log(f"  -> SENT")
        else:
            failed += 1
            log(f"  -> FAILED: {err[:80]}")
            remaining.append(p)

        time.sleep(120)  # 2-min gap for Gmail safety

    # Save remaining
    if remaining:
        with open(PENDING_FILE, "w") as f:
            json.dump(remaining, f, indent=2)
        log(f"Saved {len(remaining)} still-pending leads")
    else:
        os.remove(PENDING_FILE)
        log("All pending leads sent. Deleted pending_t1_resume.json")

    log(f"=== RESUME DONE: {sent} sent, {failed} failed, {len(remaining)} remaining ===")


if __name__ == "__main__":
    main()
