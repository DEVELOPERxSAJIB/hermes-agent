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

EMAIL_GAP = 180  # 3 minutes between emails
RETRY_GAP = 60   # 1 minute retry gap
MAX_DAILY_WL = 20
MAX_DAILY_RE = 20

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
    date_col = {"T1": "T1 Date", "T2": "T2 Date", "T3": "T3 Date", "T4": "T4 Date"}

    all_leads = crm.get_wl_all()
    sent_log = load_sent_log(SENT_LOG_WL)
    results = {"sent": 0, "skipped": 0, "errors": []}

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
            if email in sent_log.get(f"{email}|{template}", {}):
                continue
            needs.append(lead)

        if template == "T1":
            needs = needs[:MAX_DAILY_WL]

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

            success, error = send_smtp(d['to'], d['subject'], d['body'])
            if success:
                append_sent_log(SENT_LOG_WL, email, company, d['subject'], template)
                updates = {"Status": next_status[template], date_col[template]: datetime.now(BD_TZ).strftime("%Y-%m-%d")}
                crm.update_wl_lead(company, updates)
                results["sent"] += 1
                log(f"    [{i+1}/{len(needs)}] SENT {template} -> {email}")
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
            key = f"{email.lower()}|{template}"
            if key in sent_log:
                continue
            needs.append(lead)

        if template == "T1":
            needs = needs[:MAX_DAILY_RE]

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
            success, error = send_smtp(email, tmpl["subject"], tmpl["body"])

            if success:
                append_sent_log(SENT_LOG_RE, email, brokerage, tmpl["subject"], template)
                if lead_id:
                    update_status(lead_id, next_status[template])
                    update_touch_date(lead_id, int(template[1]))
                results["sent"] += 1
                log(f"    [{i+1}/{len(needs)}] SENT {template} -> {email}")
            elif "bounce" in error.lower() or "refused" in error.lower():
                if lead_id:
                    update_status(lead_id, "Bounced")
                results["bounced"] += 1
                log(f"    [{i+1}/{len(needs)}] BOUNCE -> {email}")
            else:
                results["errors"].append(f"{template} {email}: {error[:100]}")
                log(f"    [{i+1}/{len(needs)}] FAIL -> {email}: {error[:100]}")

            if i < len(needs) - 1:
                time.sleep(EMAIL_GAP)

    log(f"RE RESULTS: sent={results['sent']} bounced={results['bounced']} errors={len(results['errors'])}")
    return results

# ─── MAIN ────────────────────────────────────────────────────
def main():
    log("=" * 60)
    log("UNIFIED DAILY PIPELINE START")
    log("=" * 60)

    wl = run_wl()
    re = run_re()

    total = wl["sent"] + re["sent"]
    log("=" * 60)
    log(f"FINAL: WL sent={wl['sent']} | RE sent={re['sent']} | TOTAL={total}")
    log("=" * 60)

    return {"wl": wl, "re": re, "total": total}

if __name__ == "__main__":
    main()
