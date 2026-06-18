"""
Unified Daily Pipeline — White Label + Real Estate
Sends up to 20 WL + 20 RE emails per day with 3-min gaps.
Handles follow-ups (T2/T3/T4) for both pipelines.
Retry on failure after 1 min.
"""
import json, os, sys, time, re
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
RE_PIPELINE_DIR = os.path.join(NANOSOFT_DIR, "re_pipeline")
LOG_FILE = os.path.join(NANOSOFT_DIR, "pipeline.log")
SENT_LOG_WL = os.path.join(NANOSOFT_DIR, "emails_sent_wl.jsonl")
SENT_LOG_RE = os.path.join(NANOSOFT_DIR, "emails_sent_re.jsonl")

sys.path.insert(0, NANOSOFT_DIR)
sys.path.insert(0, RE_PIPELINE_DIR)

EMAIL_GAP = 300  # 5 minutes between emails (Gmail rate limit safety)
RETRY_GAP = 120  # 2 minute retry gap
MAX_DAILY_WL = 20
MAX_DAILY_RE = 20
MAX_DAILY_TOTAL = 40  # Hard cap to stay well under Gmail's 500/day limit

# ─── Logging ──────────────────────────────────────────────────
def log(msg):
    ts = datetime.now(BD_TZ).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

# ─── SMTP sender (RE pipeline) ──────────────────────────────
def send_smtp(to_email, subject, body):
    import smtplib, ssl
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    for attempt in range(3):
        try:
            msg = MIMEMultipart()
            msg["From"] = "SaJib Shikder <nanosoftagency007@gmail.com>"
            msg["To"] = to_email
            msg["Subject"] = subject.replace("\n", " ").strip()
            msg.attach(MIMEText(body, "plain", "utf-8"))
            ctx = ssl.create_default_context()
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.ehlo()
                server.starttls(context=ctx)
                server.ehlo()
                server.login("nanosoftagency007@gmail.com", "wgxo ddup cdol kupl")
                server.send_message(msg)
            return True, ""
        except Exception as e:
            err = str(e)[:200]
            if attempt < 2:
                log(f"  SMTP retry {attempt+1} for {to_email}: {err}")
                time.sleep(RETRY_GAP)
            else:
                return False, err
    return False, "Max retries reached"

# ─── Email verification ─────────────────────────────────────
def verify_email(email):
    """Verify syntax, block fake domains, check MX records."""
    from email_validator import validate_email, EmailNotValidError
    try:
        result = validate_email(email, check_deliverability=False)
        normalized = result.normalized
    except EmailNotValidError as ex:
        return False, str(ex)

    domain = normalized.split('@')[1].lower()

    # Block known fake/test domains
    fake_domains = ['example.com', 'test.com', 'email.com', 'domain.com', 'company.com']
    if domain in fake_domains:
        return False, f"Fake domain: {domain}"

    # Block URL-encoded garbage
    if '%20' in email or '%' in email:
        return False, f"URL-encoded email"

    # MX check
    try:
        import dns.resolver
        answers = dns.resolver.resolve(domain, 'MX', lifetime=5)
        if not answers:
            return False, f"No MX for {domain}"
    except:
        return False, f"No MX for {domain}"

    return True, normalized

# ─── Gmail API sender (WL pipeline) ─────────────────────────
def send_gmail(to_email, subject, body):
    import base64
    from email.mime.text import MIMEText
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    token_path = os.path.join(NANOSOFT_DIR, "gmail_token.json")
    if not os.path.exists(token_path):
        return False, "No gmail_token.json"

    for attempt in range(3):
        try:
            with open(token_path) as f:
                token_data = json.load(f)
            creds = Credentials(
                token=token_data.get("token"),
                refresh_token=token_data.get("refresh_token"),
                token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
                client_id=token_data.get("client_id"),
                client_secret=token_data.get("client_secret"),
                scopes=token_data.get("scopes"),
            )
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                token_data["token"] = creds.token
                with open(token_path, "w") as f:
                    json.dump(token_data, f)
            service = build("gmail", "v1", credentials=creds)
            msg = MIMEText(body)
            msg['to'] = to_email
            msg['from'] = "SaJib <nanosoftagency007@gmail.com>"
            msg['subject'] = subject
            msg['List-Unsubscribe'] = '<mailto:nanosoftagency007@gmail.com?subject=unsubscribe>'
            msg['List-Unsubscribe-Post'] = 'List-Unsubscribe=One-Click'
            raw = base64.urlsafe_b64encode(msg.as_string().encode()).decode()
            result = service.users().messages().send(userId='me', body={'raw': raw}).execute()
            if result.get('id'):
                return True, ""
            return False, "No message ID"
        except Exception as e:
            err = str(e)[:200]
            if attempt < 2:
                log(f"  Gmail retry {attempt+1} for {to_email}: {err}")
                time.sleep(RETRY_GAP)
            else:
                return False, err
    return False, "Max retries reached"

# ─── Load sent logs ──────────────────────────────────────────
def load_sent_log(path):
    sent = {}
    try:
        with open(path) as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    key = f"{entry.get('to','').lower()}|{entry.get('template','')}"
                    sent[key] = entry
    except:
        pass
    return sent

def append_sent_log(path, to_email, company, subject, template):
    with open(path, "a") as f:
        f.write(json.dumps({
            "to": to_email, "company": company,
            "subject": subject, "template": template,
            "sent_at": datetime.now(BD_TZ).isoformat(),
        }) + "\n")

# ─── File lock to prevent overlapping runs ────────────────────
def acquire_lock():
    """Acquire a file lock. Returns True if lock acquired, False if another run is active."""
    import fcntl
    lock_path = os.path.join(NANOSOFT_DIR, ".pipeline.lock")
    try:
        fd = open(lock_path, "w")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fd.write(str(os.getpid()))
        fd.flush()
        return fd  # caller must keep reference
    except (IOError, OSError):
        return None

def release_lock(fd):
    import fcntl
    if fd:
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()
        try:
            os.remove(os.path.join(NANOSOFT_DIR, ".pipeline.lock"))
        except:
            pass

# ─── WHITE LABEL ─────────────────────────────────────────────
def run_wl():
    log("=" * 50)
    log("WHITE LABEL PIPELINE")
    log("=" * 50)

    from crm import NanoSoftCRM
    from quill_wl import make_email_t1, make_email_t2, make_email_t3, make_email_t4

    crm = NanoSoftCRM()

    make_fn = {"T1": make_email_t1, "T2": make_email_t2, "T3": make_email_t3, "T4": make_email_t4}
    status_map = {"T1": ["New", "Unqualified"], "T2": ["T1 Sent", "Contacted"], "T3": ["T2 Sent"], "T4": ["T3 Sent"]}
    next_status = {"T1": "T1 Sent", "T2": "T2 Sent", "T3": "T3 Sent", "T4": "T4 Sent"}
    date_col = {"T1": "Sent date", "T2": "FU 1", "T3": "FU 2", "T4": "FU 3"}

    all_leads = crm.get_wl_all()
    sent_log = load_sent_log(SENT_LOG_WL)
    results = {"sent": 0, "skipped": 0, "errors": []}
    processed_emails = set()  # track leads already processed in this run

    # Process: follow-ups first, then new T1
    for template in ["T4", "T3", "T2", "T1"]:
        targets = status_map[template]
        needs = []
        for lead in all_leads:
            if str(lead.get("Status", "")).strip() not in targets:
                continue
            email = str(lead.get("Email", "")).strip().lower()
            if not email or "@" not in email:
                continue
            if email in processed_emails:
                continue
            key = f"{email}|{template}"
            if key in sent_log:
                continue
            needs.append(lead)

        if template == "T1":
            # Only email leads with score >= 7 (quality filter)
            qualified_needs = []
            for lead in needs:
                score = str(lead.get("Judge Score", ""))
                if score and score.isdigit() and int(score) >= 7:
                    qualified_needs.append(lead)
                else:
                    log(f"    SKIP low score: {lead.get('Company Name','')} score={score}")
            needs = qualified_needs[:MAX_DAILY_WL]

        if not needs:
            log(f"  {template}: no leads need this")
            continue

        log(f"  {template}: {len(needs)} leads")

        for i, lead in enumerate(needs):
            email = str(lead.get("Email", "")).strip().lower()
            company = str(lead.get("Company Name", "")).strip()

            d = make_fn[template](lead)
            if not d:
                log(f"    SKIP [{i+1}] {company}: no email generated")
                results["skipped"] += 1
                continue

            # Verify email before sending
            email_to = d['to']
            is_valid, verify_detail = verify_email(email_to)
            if not is_valid:
                log(f"    SKIP [{i+1}] {company}: invalid email {email_to} - {verify_detail}")
                results["skipped"] += 1
                crm.update_wl_lead(company, {"Status": "Bounced", "Email": f"BOUNCED_{email}"})
                continue

            # Re-check sent log right before sending (prevent dupes from parallel runs)
            fresh_sent = load_sent_log(SENT_LOG_WL)
            if f"{email_to.lower()}|{template}" in fresh_sent:
                log(f"    SKIP [{i+1}] {company}: already sent (detected pre-send)")
                results["skipped"] += 1
                continue

            success, error = send_smtp(email_to, d['subject'], d['body'])
            if success:
                append_sent_log(SENT_LOG_WL, email, company, d['subject'], template)
                sent_log[f"{email}|{template}"] = {"to": email, "template": template}
                updates = {"Status": next_status[template], date_col[template]: datetime.now(BD_TZ).strftime("%Y-%m-%d")}
                crm.update_wl_lead(company, updates)
                processed_emails.add(email)
                results["sent"] += 1
                log(f"    [{i+1}/{len(needs)}] SENT {template} -> {email}")
            else:
                # Check if it's a permanent bounce
                if any(kw in error.lower() for kw in ['user unknown', 'mailbox not found', 'recipient rejected', 'invalid', 'does not exist', '550', '551', '552', '553']):
                    crm.update_wl_lead(company, {"Status": "Bounced", "Email": f"BOUNCED_{email}"})
                    log(f"    [{i+1}/{len(needs)}] BOUNCE {template} -> {email}: {error[:100]}")
                else:
                    results["errors"].append(f"{template} {email}: {error[:100]}")
                    log(f"    [{i+1}/{len(needs)}] FAIL {template} -> {email}: {error[:100]}")

            if i < len(needs) - 1:
                time.sleep(EMAIL_GAP)

    log(f"WL RESULTS: sent={results['sent']} skipped={results['skipped']} errors={len(results['errors'])}")
    return results

# ─── REAL ESTATE ─────────────────────────────────────────────
def run_re():
    log("=" * 50)
    log("REAL ESTATE PIPELINE")
    log("=" * 50)

    from sheets import get_leads, update_status, update_touch_date
    from templates import get_template

    leads = get_leads()
    sent_log = load_sent_log(SENT_LOG_RE)
    results = {"sent": 0, "bounced": 0, "skipped": 0, "errors": []}
    processed_emails = set()  # track leads already processed in this run

    # RE status flow: New → T1 → Contacted → T2 → Followed-Up → T3 → T3 Sent → T4
    status_map = {"T1": ["New"], "T2": ["Contacted"], "T3": ["Followed-Up"], "T4": ["T3 Sent"]}
    next_status = {"T1": "Contacted", "T2": "Followed-Up", "T3": "T3 Sent", "T4": "T4 Sent"}

    for template in ["T4", "T3", "T2", "T1"]:
        targets = status_map[template]
        needs = []
        for lead in leads:
            if str(lead.get("Status", "")).strip() not in targets:
                continue
            email = str(lead.get("Email", "")).strip()
            if not email or "@" not in email:
                continue
            if email.lower() in processed_emails:
                continue
            key = f"{email.lower()}|{template}"
            if key in sent_log:
                continue
            needs.append(lead)

        if template == "T1":
            needs = needs[:MAX_DAILY_RE]

        # Dedup by email within this batch (keep first occurrence)
        seen_emails = set()
        deduped_needs = []
        for lead in needs:
            email = str(lead.get("Email", "")).strip().lower()
            if email not in seen_emails:
                seen_emails.add(email)
                deduped_needs.append(lead)
            else:
                log(f"    DEDUP SKIP: {lead.get('Brokerage_Name','')} ({email})")
        needs = deduped_needs

        if not needs:
            log(f"  {template}: no leads need this")
            continue

        log(f"  {template}: {len(needs)} leads")

        for i, lead in enumerate(needs):
            email = str(lead.get("Email", "")).strip()
            brokerage = str(lead.get("Brokerage_Name", "")).strip()
            angle = str(lead.get("Angle", "A")).strip()
            city = str(lead.get("City", "")).strip()
            lead_id = lead.get("Lead_ID")

            tmpl = get_template(angle, int(template[1]), brokerage, "", city)

            # Verify email before sending
            is_valid, verify_detail = verify_email(email)
            if not is_valid:
                log(f"    SKIP [{i+1}] {brokerage}: invalid email {email} - {verify_detail}")
                if lead_id:
                    update_status(lead_id, "Bounced")
                results["skipped"] += 1
                continue

            # Re-check sent log right before sending (prevent dupes from parallel runs)
            fresh_sent = load_sent_log(SENT_LOG_RE)
            if f"{email.lower()}|{template}" in fresh_sent:
                log(f"    SKIP [{i+1}] {brokerage}: already sent (detected pre-send)")
                results["skipped"] += 1
                continue

            success, error = send_smtp(email, tmpl["subject"], tmpl["body"])

            if success:
                append_sent_log(SENT_LOG_RE, email, brokerage, tmpl["subject"], template)
                sent_log[f"{email.lower()}|{template}"] = {"to": email, "template": template}
                if lead_id:
                    update_status(lead_id, next_status[template])
                    update_touch_date(lead_id, int(template[1]))
                processed_emails.add(email.lower())
                results["sent"] += 1
                log(f"    [{i+1}/{len(needs)}] SENT {template} -> {email}")
            elif any(kw in error.lower() for kw in ['user unknown', 'mailbox not found', 'recipient rejected', 'invalid', 'does not exist', '550', '551', '552', '553', 'bounce', 'refused']):
                if lead_id:
                    update_status(lead_id, "Bounced")
                results["bounced"] += 1
                log(f"    [{i+1}/{len(needs)}] BOUNCE -> {email}: {error[:100]}")
            else:
                results["errors"].append(f"{template} {email}: {error[:100]}")
                log(f"    [{i+1}/{len(needs)}] FAIL -> {email}: {error[:100]}")

            if i < len(needs) - 1:
                time.sleep(EMAIL_GAP)

    log(f"RE RESULTS: sent={results['sent']} bounced={results['bounced']} errors={len(results['errors'])}")
    return results

def _count_today_sends():
    """Count total emails sent today from both WL and RE sent logs."""
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
    return count

# ─── MAIN ────────────────────────────────────────────────────
def main():
    # Prevent overlapping runs
    lock_fd = acquire_lock()
    if lock_fd is None:
        log("ANOTHER PIPELINE RUN IS ACTIVE. Exiting.")
        sys.exit(0)

    # Check daily send count — stop if we're near Gmail's 500/day limit
    today_count = _count_today_sends()
    if today_count >= MAX_DAILY_TOTAL:
        log(f"DAILY LIMIT REACHED: {today_count}/{MAX_DAILY_TOTAL} sent today. Skipping.")
        release_lock(lock_fd)
        sys.exit(0)
    log(f"Daily sends so far: {today_count}/{MAX_DAILY_TOTAL}")

    log("=" * 60)
    log("UNIFIED DAILY PIPELINE START")
    log("=" * 60)

    wl = run_wl()
    re = run_re()

    # Post-send: check inbox for bounce-backs
    log("Checking inbox for bounce-backs...")
    try:
        sys.path.insert(0, NANOSOFT_DIR)
        from gmail_utils import fetch_recent_bounces
        bounces = fetch_recent_bounces(hours=24)
        if bounces:
            log(f"Found {len(bounces)} bounced emails in inbox")
            from email_tracker import append_bounce_log, mark_wl_bounced, mark_re_bounced
            for bounced_email in bounces:
                append_bounce_log(bounced_email, "inbox-detected", "inbox")
                mark_wl_bounced(bounced_email, "inbox bounce")
                mark_re_bounced(bounced_email, "inbox bounce")
        else:
            log("No bounce-backs found in inbox")
    except Exception as e:
        log(f"Bounce check error: {e}")

    total = wl["sent"] + re["sent"]
    log("=" * 60)
    log(f"FINAL: WL sent={wl['sent']} | RE sent={re['sent']} | TOTAL={total}")
    log(f"WL: skipped={wl['skipped']} errors={len(wl['errors'])}")
    log(f"RE: skipped={re.get('skipped',0)} bounced={re['bounced']} errors={len(re['errors'])}")
    log("=" * 60)

    release_lock(lock_fd)
    return {"wl": wl, "re": re, "total": total}

if __name__ == "__main__":
    main()
