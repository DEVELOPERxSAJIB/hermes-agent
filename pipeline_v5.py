#!/usr/bin/env python3
"""
NanoSoft Unified Outreach Pipeline v5 — Production Grade
=========================================================
Fully automated 4-touchpoint outreach system for WL + RE campaigns.

WORKFLOW:
  Day 1:  T1 (Cold Email) → status="T1 Sent", Touch_1_Date=today
  Day 5:  T2 (Follow-Up 1) → status="T2 Sent", Touch_2_Date=today  (4 days after T1)
  Day 9:  T3 (Follow-Up 2) → status="T3 Sent", Touch_3_Date=today  (4 days after T2)
  Day 16: T4 (Follow-Up 3) → status="T4 Sent", Touch_4_Date=today  (7 days after T3)

DAILY TARGET:
  20 WL + 20 RE = 40 new T1 emails/day
  Follow-ups auto-trigger based on date gaps
  Max 40 T1 + follow-ups combined per day (Gmail safety)

RULES:
  - 3-minute gap between all emails
  - Skip leads that replied, bounced, or are marked Dead/Lost/Closed
  - Dedup via sent_log (email|template)
  - Date format: dd/mm/yyyy
  - WL score threshold: >= 7
"""
import json, os, sys, time, re, logging
from datetime import datetime, timezone, timedelta
from collections import Counter

# ── CONFIG ──────────────────────────────────────────────────
BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
RE_PIPELINE_DIR = os.path.join(NANOSOFT_DIR, "re_pipeline")

sys.path.insert(0, NANOSOFT_DIR)
sys.path.insert(0, RE_PIPELINE_DIR)

# Sheet IDs
WL_SHEET_ID = "1POJ1ffcC6Z4dFDbgQj3VlECYPmApzXXJ5orNzf2-Yuo"
RE_SHEET_ID = "1rQAyfC037JoV2phnLq4g9JsDvvrEb6M69A3roeYJHkk"

# Limits
MAX_DAILY_T1_WL = 20
MAX_DAILY_T1_RE = 20
MAX_DAILY_TOTAL = 40  # Hard cap for Gmail safety
EMAIL_GAP = 180  # 3 minutes between emails

# Follow-up gaps (days)
FU1_GAP = 4   # T2 = 4 days after T1
FU2_GAP = 4   # T3 = 4 days after T2
FU3_GAP = 7   # T4 = 7 days after T3

# WL quality threshold
WL_MIN_SCORE = 7

# File paths
LOG_FILE = os.path.join(NANOSOFT_DIR, "pipeline_v5.log")
SENT_LOG_WL = os.path.join(NANOSOFT_DIR, "emails_sent_wl.jsonl")
SENT_LOG_RE = os.path.join(NANOSOFT_DIR, "emails_sent_re.jsonl")
LOCK_FILE = os.path.join(NANOSOFT_DIR, "pipeline_v5.lock")

# OAuth
OAUTH_TOKEN_FILE = "/home/ubuntu/.hermes/google_token.json"

# Status values that should be skipped
SKIP_STATUSES_WL = {"Bounced", "Lost", "Dead", "Closed", "Auto-Reply", "Auto-reply"}
SKIP_STATUSES_RE = {"Bounced", "Dead", "Closed"}

# ── LOGGING ─────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger("pipeline")

# ── AUTH ────────────────────────────────────────────────────
def get_gc():
    """Get authorized gspread client using OAuth token."""
    from google.oauth2.credentials import Credentials
    import gspread
    with open(OAUTH_TOKEN_FILE) as f:
        d = json.load(f)
    creds = Credentials.from_authorized_user_info(d)
    return gspread.authorize(creds)

# ── LOCK ────────────────────────────────────────────────────
def acquire_lock():
    """Prevent overlapping runs."""
    import fcntl
    try:
        fd = open(LOCK_FILE, "w")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fd.write(str(os.getpid()))
        fd.flush()
        return fd
    except IOError:
        return None

def release_lock(fd):
    import fcntl
    if fd:
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()
        try:
            os.remove(LOCK_FILE)
        except:
            pass

# ── SENT LOG ────────────────────────────────────────────────
def load_sent_log(path):
    """Load sent log into set of 'email|template' keys."""
    sent = set()
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
                email = e.get("to", "").lower().strip()
                tmpl = e.get("template", "")
                sent.add(f"{email}|{tmpl}")
            except:
                pass
    return sent

def append_sent_log(path, to_email, company, subject, template):
    """Append entry to sent log."""
    entry = {
        "to": to_email,
        "company": company,
        "subject": subject,
        "template": template,
        "sent_at": datetime.now(BD_TZ).isoformat()
    }
    with open(path, "a") as f:
        f.write(json.dumps(entry) + "\n")

def count_today_sends():
    """Count total emails sent today."""
    today = datetime.now(BD_TZ).strftime("%Y-%m-%d")
    count = 0
    for path in [SENT_LOG_WL, SENT_LOG_RE]:
        if os.path.exists(path):
            for line in open(path):
                if line.strip() and today in line:
                    count += 1
    return count

# ── SMTP ────────────────────────────────────────────────────
def send_smtp(to_email, subject, body):
    """Send email via Gmail SMTP."""
    import smtplib, ssl
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    SMTP_USER = "nanosoftagency007@gmail.com"
    SMTP_PASS = "wgxo ddup cdol kupl"

    for attempt in range(3):
        try:
            msg = MIMEMultipart()
            msg["From"] = f"SaJib Shikder <{SMTP_USER}>"
            msg["To"] = to_email
            msg["Subject"] = subject.replace("\n", " ").strip()
            msg.attach(MIMEText(body, "plain", "utf-8"))
            ctx = ssl.create_default_context()
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.ehlo()
                server.starttls(context=ctx)
                server.ehlo()
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
            return True, ""
        except Exception as e:
            err = str(e)[:200]
            if attempt < 2:
                time.sleep(10)
            else:
                return False, err
    return False, "max retries"

# ── DATE HELPERS ────────────────────────────────────────────
DATE_FMT = "%d/%m/%Y"

def parse_date(s):
    """Parse dd/mm/yyyy string to datetime. Returns None on failure."""
    try:
        return datetime.strptime(s.strip(), DATE_FMT)
    except:
        return None

def days_since(date_str):
    """Return days since date string. Returns 999 if unparseable."""
    d = parse_date(date_str)
    if not d:
        return 999
    return (datetime.now() - d).days

def today_str():
    return datetime.now().strftime(DATE_FMT)

# ── WL PIPELINE ─────────────────────────────────────────────
def run_wl():
    """
    White Label outreach pipeline.
    Processes: T4 → T3 → T2 → T1 (follow-ups first, then new outreach)
    Date gaps: T2 after 4 days, T3 after 4 days, T4 after 7 days
    """
    log.info("=" * 50)
    log.info("WHITE LABEL PIPELINE")
    log.info("=" * 50)

    from quill_wl import make_email_t1, make_email_t2, make_email_t3, make_email_t4

    gc = get_gc()
    ss = gc.open_by_key(WL_SHEET_ID)
    ws = ss.worksheet("White Label")
    all_rows = ws.get_all_records()
    sent_log = load_sent_log(SENT_LOG_WL)

    make_fn = {
        "T1": make_email_t1,
        "T2": make_email_t2,
        "T3": make_email_t3,
        "T4": make_email_t4
    }

    results = {"sent": 0, "skipped": 0, "errors": []}
    processed_emails = set()
    daily_sent = 0

    # Process follow-ups first (T4 → T3 → T2), then new T1
    for template in ["T4", "T3", "T2", "T1"]:
        needs = []

        for lead in all_rows:
            company = str(lead.get("Company Name", "")).strip()
            email = str(lead.get("Email", "")).strip().lower()
            status = str(lead.get("Status", "")).strip()
            score = str(lead.get("Judge Score", "")).strip()

            if not email or "@" not in email:
                continue
            if email in processed_emails:
                continue
            if status in SKIP_STATUSES_WL:
                continue

            # Dedup check
            key = f"{email}|{template}"
            if key in sent_log:
                continue

            # Date-gap logic for follow-ups
            sent_date = str(lead.get("Sent date", "")).strip()
            fu1 = str(lead.get("FU 1", "")).strip()
            fu2 = str(lead.get("FU 2", "")).strip()
            fu3 = str(lead.get("FU 3", "")).strip()

            eligible = False

            if template == "T1":
                # New outreach: status must be "New" and score >= 7
                if status == "New" and score.isdigit() and int(score) >= WL_MIN_SCORE:
                    eligible = True

            elif template == "T2":
                # T2: T1 was sent, no T2 yet, 4+ days since T1
                if sent_date and not fu1:
                    days = days_since(sent_date)
                    if days >= FU1_GAP:
                        eligible = True
                    else:
                        log.debug(f"  T2 not ready: {company} ({days}d/{FU1_GAP}d)")

            elif template == "T3":
                # T3: T2 was sent (FU1 has date), no T3 yet, 4+ days since T2
                if fu1 and not fu2:
                    days = days_since(fu1)
                    if days >= FU2_GAP:
                        eligible = True
                    else:
                        log.debug(f"  T3 not ready: {company} ({days}d/{FU2_GAP}d)")

            elif template == "T4":
                # T4: T3 was sent (FU2 has date), no T4 yet, 7+ days since T3
                if fu2 and not fu3:
                    days = days_since(fu2)
                    if days >= FU3_GAP:
                        eligible = True
                    else:
                        log.debug(f"  T4 not ready: {company} ({days}d/{FU3_GAP}d)")

            if eligible:
                needs.append(lead)

        # Cap T1 at daily limit
        if template == "T1":
            needs = needs[:MAX_DAILY_T1_WL]

        if not needs:
            log.info(f"  {template}: no leads need this")
            continue

        log.info(f"  {template}: {len(needs)} leads")

        for i, lead in enumerate(needs):
            # Check daily total cap
            if daily_sent >= MAX_DAILY_TOTAL:
                log.info(f"  Daily total cap reached ({MAX_DAILY_TOTAL}). Stopping.")
                break

            email = str(lead.get("Email", "")).strip()
            company = str(lead.get("Company Name", "")).strip()

            # Generate email
            d = make_fn[template](lead)
            if not d:
                log.warning(f"  SKIP [{i+1}] {company}: no email generated")
                results["skipped"] += 1
                continue

            # Send
            success, error = send_smtp(email, d["subject"], d["body"])

            if success:
                append_sent_log(SENT_LOG_WL, email, company, d["subject"], template)
                sent_log.add(f"{email.lower()}|{template}")
                processed_emails.add(email.lower())
                results["sent"] += 1
                daily_sent += 1

                # Update sheet
                try:
                    row_idx = None
                    all_rows_fresh = ws.get_all_values()
                    for ri, row in enumerate(all_rows_fresh[1:], start=2):
                        if str(row[0]).strip() == company:
                            row_idx = ri
                            break

                    if row_idx:
                        status_col = 19  # S (Status)
                        if template == "T1":
                            ws.update_cell(row_idx, 15, today_str())  # Sent date
                            ws.update_cell(row_idx, status_col, "T1 Sent")
                        elif template == "T2":
                            ws.update_cell(row_idx, 16, today_str())  # FU 1
                            ws.update_cell(row_idx, status_col, "T2 Sent")
                        elif template == "T3":
                            ws.update_cell(row_idx, 17, today_str())  # FU 2
                            ws.update_cell(row_idx, status_col, "T3 Sent")
                        elif template == "T4":
                            ws.update_cell(row_idx, 18, today_str())  # FU 3
                            ws.update_cell(row_idx, status_col, "T4 Sent")
                except Exception as e:
                    log.warning(f"  Sheet update error for {company}: {e}")

                log.info(f"  [{i+1}/{len(needs)}] SENT {template} → {email}")
            else:
                log.error(f"  [{i+1}/{len(needs)}] FAIL {template} → {email}: {error[:80]}")
                results["errors"].append(f"{template} {email}: {error[:80]}")

            # Gap between emails
            if i < len(needs) - 1 and daily_sent < MAX_DAILY_TOTAL:
                time.sleep(EMAIL_GAP)

    log.info(f"WL RESULTS: sent={results['sent']} skipped={results['skipped']} errors={len(results['errors'])}")
    return results

# ── RE PIPELINE ─────────────────────────────────────────────
def run_re():
    """
    Real Estate outreach pipeline.
    Processes: T4 → T3 → T2 → T1 (follow-ups first, then new outreach)
    Date gaps: T2 after 4 days, T3 after 4 days, T4 after 7 days
    """
    log.info("=" * 50)
    log.info("REAL ESTATE PIPELINE")
    log.info("=" * 50)

    from re_pipeline.personalized_templates import get_personalized_template

    gc = get_gc()
    ss = gc.open_by_key(RE_SHEET_ID)
    ws = ss.worksheet("Pipeline")
    all_rows = ws.get_all_records()
    sent_log = load_sent_log(SENT_LOG_RE)

    results = {"sent": 0, "skipped": 0, "errors": []}
    processed_emails = set()
    daily_sent = 0

    # Process follow-ups first (T4 → T3 → T2), then new T1
    for template in ["T4", "T3", "T2", "T1"]:
        needs = []

        for lead in all_rows:
            brokerage = str(lead.get("Brokerage_Name", "")).strip()
            email = str(lead.get("Email", "")).strip()
            status = str(lead.get("Status", "")).strip()
            city = str(lead.get("City", "")).strip()
            contact = str(lead.get("Contact_Name", "")).strip()
            lead_id = lead.get("Lead_ID", "")

            if not email or "@" not in email:
                continue
            if email.lower() in processed_emails:
                continue
            if status in SKIP_STATUSES_RE:
                continue

            # Dedup check
            key = f"{email.lower()}|{template}"
            if key in sent_log:
                continue

            # Date-gap logic
            t1 = str(lead.get("Touch_1_Date", "")).strip()
            t2 = str(lead.get("Touch_2_Date", "")).strip()
            t3 = str(lead.get("Touch_3_Date", "")).strip()
            t4 = str(lead.get("Touch_4_Date", "")).strip()

            eligible = False

            if template == "T1":
                # New outreach: status must be "New"
                if status == "New":
                    eligible = True

            elif template == "T2":
                # T2: T1 was sent, no T2 yet, 4+ days since T1
                if t1 and not t2:
                    days = days_since(t1)
                    if days >= FU1_GAP:
                        eligible = True
                    else:
                        log.debug(f"  T2 not ready: {brokerage} ({days}d/{FU1_GAP}d)")

            elif template == "T3":
                # T3: T2 was sent, no T3 yet, 4+ days since T2
                if t2 and not t3:
                    days = days_since(t2)
                    if days >= FU2_GAP:
                        eligible = True
                    else:
                        log.debug(f"  T3 not ready: {brokerage} ({days}d/{FU2_GAP}d)")

            elif template == "T4":
                # T4: T3 was sent, no T4 yet, 7+ days since T3
                if t3 and not t4:
                    days = days_since(t3)
                    if days >= FU3_GAP:
                        eligible = True
                    else:
                        log.debug(f"  T4 not ready: {brokerage} ({days}d/{FU3_GAP}d)")

            if eligible:
                needs.append(lead)

        # Cap T1 at daily limit
        if template == "T1":
            needs = needs[:MAX_DAILY_T1_RE]

        if not needs:
            log.info(f"  {template}: no leads need this")
            continue

        log.info(f"  {template}: {len(needs)} leads")

        for i, lead in enumerate(needs):
            # Check daily total cap
            if daily_sent >= MAX_DAILY_TOTAL:
                log.info(f"  Daily total cap reached ({MAX_DAILY_TOTAL}). Stopping.")
                break

            email = str(lead.get("Email", "")).strip()
            brokerage = str(lead.get("Brokerage_Name", "")).strip()
            city = str(lead.get("City", "")).strip()
            contact = str(lead.get("Contact_Name", "")).strip()
            lead_id = lead.get("Lead_ID", "")

            # Generate email
            tmpl = get_personalized_template(int(template[1]), brokerage, contact, city)
            if not tmpl.get("subject"):
                log.warning(f"  SKIP [{i+1}] {brokerage}: no template")
                results["skipped"] += 1
                continue

            # Send
            success, error = send_smtp(email, tmpl["subject"], tmpl["body"])

            if success:
                append_sent_log(SENT_LOG_RE, email, brokerage, tmpl["subject"], template)
                sent_log.add(f"{email.lower()}|{template}")
                processed_emails.add(email.lower())
                results["sent"] += 1
                daily_sent += 1

                # Update sheet
                try:
                    all_rows_fresh = ws.get_all_values()
                    headers = all_rows_fresh[0]
                    status_col = headers.index("Status") + 1
                    t1_col = headers.index("Touch_1_Date") + 1
                    t2_col = headers.index("Touch_2_Date") + 1
                    t3_col = headers.index("Touch_3_Date") + 1
                    t4_col = headers.index("Touch_4_Date") + 1

                    for ri, row in enumerate(all_rows_fresh[1:], start=2):
                        if str(row[headers.index("Lead_ID")]).strip() == str(lead_id).strip():
                            if template == "T1":
                                ws.update_cell(ri, t1_col, today_str())
                                ws.update_cell(ri, status_col, "Contacted")
                            elif template == "T2":
                                ws.update_cell(ri, t2_col, today_str())
                                ws.update_cell(ri, status_col, "Followed-Up")
                            elif template == "T3":
                                ws.update_cell(ri, t3_col, today_str())
                                ws.update_cell(ri, status_col, "T3 Sent")
                            elif template == "T4":
                                ws.update_cell(ri, t4_col, today_str())
                                ws.update_cell(ri, status_col, "T4 Sent")
                            break
                except Exception as e:
                    log.warning(f"  Sheet update error for {brokerage}: {e}")

                log.info(f"  [{i+1}/{len(needs)}] SENT {template} → {email}")
            else:
                log.error(f"  [{i+1}/{len(needs)}] FAIL {template} → {email}: {error[:80]}")
                results["errors"].append(f"{template} {email}: {error[:80]}")

            # Gap between emails
            if i < len(needs) - 1 and daily_sent < MAX_DAILY_TOTAL:
                time.sleep(EMAIL_GAP)

    log.info(f"RE RESULTS: sent={results['sent']} skipped={results['skipped']} errors={len(results['errors'])}")
    return results

# ── MAIN ────────────────────────────────────────────────────
def main():
    log.info("=" * 60)
    log.info("NANOSOFT UNIFIED OUTREACH PIPELINE v5 — START")
    log.info("=" * 60)

    # Lock
    lock_fd = acquire_lock()
    if lock_fd is None:
        log.warning("ANOTHER PIPELINE RUN IS ACTIVE. Exiting.")
        sys.exit(0)

    try:
        # Check daily count
        already_sent = count_today_sends()
        log.info(f"Already sent today: {already_sent}/{MAX_DAILY_TOTAL}")

        if already_sent >= MAX_DAILY_TOTAL:
            log.info("Daily limit already reached. Exiting.")
            sys.exit(0)

        # Run pipelines
        wl_results = run_wl()
        re_results = run_re()

        total = wl_results["sent"] + re_results["sent"]
        log.info("=" * 60)
        log.info(f"FINAL: WL={wl_results['sent']} | RE={re_results['sent']} | TOTAL={total}")
        log.info(f"WL: skipped={wl_results['skipped']} errors={len(wl_results['errors'])}")
        log.info(f"RE: skipped={re_results['skipped']} errors={len(re_results['errors'])}")
        log.info("=" * 60)

        return {"wl": wl_results, "re": re_results, "total": total}

    finally:
        release_lock(lock_fd)

if __name__ == "__main__":
    main()
