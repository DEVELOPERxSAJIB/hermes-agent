#!/usr/bin/python3
"""
NanoSoft QUILL v11 — Cold Email Generator + Gmail Draft Creator
Human tone. No hyphens. Conversational. Reply-focused.
Creates actual drafts in Gmail Drafts tab via Gmail API.
"""
import json, os, sys, time, smtplib, ssl, re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
SENT_LOG = os.path.join(NANOSOFT_DIR, "emails_sent.jsonl")
LOG_FILE = os.path.join(NANOSOFT_DIR, "quill_v11.log")

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "nanosoftagency007@gmail.com"
SMTP_PASS = os.environ.get("SMTP_PASS", "wnvp mpne dyvu dheq")

sys.path.insert(0, NANOSOFT_DIR)

# ── CHAIRMAN'S EMAIL RULES ─────────────────────────────────
MAX_WORDS = 125
MAX_SUBJECT = 33

BANNED_PHRASES = [
    "i hope this email finds you well", "i came across your website",
    "i am passionate about", "we are a dedicated team", "i would love to connect",
    "please feel free to reach out", "looking forward to hearing from you",
    "best regards", "sincerely", "to whom it may concern",
    "i noticed you might benefit from", "no obligation", "risk free",
    "act now", "click here", "limited time", "special offer",
]

SIGNATURE = """Sajib Shikder
NanoSoft Agency"""


def make_email(lead):
    """Generate conversational cold email. Returns dict or None."""
    company = lead.get("Company Name", "").strip()
    website = lead.get("Website", "").strip()
    email = lead.get("Owner Email", "").strip()
    pain_points = lead.get("Pain Point", "").strip()
    severity = lead.get("Severity", "medium").strip()
    outreach_angle = lead.get("Outreach Angle", "").strip()

    if not email or not website:
        return None

    domain = re.sub(r'^https?://(www\.)?', '', website).split('/')[0]
    pains = [p.strip() for p in pain_points.split(',') if p.strip()] if pain_points else []
    pains_lower = [p.lower() for p in pains]

    # ── SUBJECT (no hyphens, plain text) ──
    impact = "needs attention"
    for pain in pains_lower:
        for key, short in [
            ("not mobile", "losing mobile visitors"),
            ("no ssl", "not secure"),
            ("no live chat", "losing leads after hours"),
            ("no analytics", "no visitor data"),
            ("no blog", "no Google traffic"),
            ("thin content", "invisible on Google"),
            ("no testimonial", "no social proof"),
            ("no contact", "hard to reach you"),
            ("no privacy", "trust gap"),
            ("slow", "loading too slowly"),
            ("outdated", "looking outdated"),
            ("no booking", "manual booking losing customers"),
            ("hiring actively", "scaling operations"),
        ]:
            if key in pain:
                impact = short
                break
        if impact != "needs attention":
            break

    # Subject: no colons, no hyphens, plain question or observation
    subject_options = [
        f"{domain} {impact}",
        f"quick question about {domain}",
        f"{domain} question",
        f"about {domain}",
    ]
    subject = subject_options[0]
    for opt in subject_options:
        if len(opt) <= MAX_SUBJECT:
            subject = opt
            break
    if len(subject) > MAX_SUBJECT:
        subject = f"{domain.split('.')[0]} {impact}"
    if len(subject) > MAX_SUBJECT:
        subject = subject[:MAX_SUBJECT].rstrip()

    # ── BODY: Natural, human, conversational ──
    # No hyphens, no em-dashes, no bullet points.
    # Short paragraphs. Sounds like a real person.

    # S1: Specific observation — about THEM, casual but specific
    s1_map = {
        "not mobile": f"Pulled up {domain} on my phone earlier and the layout was pretty broken. Most people are browsing on mobile these days so that's probably sending a lot of visitors away.",
        "no ssl": f"Noticed Chrome shows 'Not Security' on {domain} right in the address bar. That's got to be hurting trust with new visitors.",
        "no live chat": f"{domain} doesn't seem to have any live chat. If someone has a question at 8pm and can't get an answer, they usually just go to the next business.",
        "no analytics": f"{domain} doesn't have basic analytics running. You'd have no idea which marketing is actually bringing people in and which is just burning money.",
        "no blog": f"{domain} doesn't have a blog. That's a lot of free Google traffic you're leaving on the table, and your competitors who do blog are grabbing those visitors.",
        "thin content": f"The pages on {domain} are pretty thin. Google needs content to rank and right now there's not much for it to read.",
        "no testimonial": f"{domain} doesn't show any testimonials or reviews. Most people check reviews before choosing a local business and without visible ones they go to competitors.",
        "no contact": f"Couldn't find a clear way to contact you through {domain}. If it takes more than a few seconds, most people just leave.",
        "no privacy": f"{domain} is missing a privacy policy page. It's a trust thing and it also affects Google rankings.",
        "slow": f"{domain} takes a while to load. Every extra second means fewer people stick around.",
        "outdated": f"{domain} looks like it was built a while ago. People judge a business fast and an outdated site sends them somewhere else.",
        "no booking": f"{domain} doesn't have online booking. People who want instant confirmation end up going to competitors who make it easy.",
        "hiring actively": f"Saw you're hiring which is a great sign. Growth is good but if the website can't capture leads automatically, a lot of that manual effort adds up fast.",
    }
    s1 = f"Had a look at {domain} and spotted a few things that are probably costing you customers."
    for pain in pains_lower:
        for key, template in s1_map.items():
            if key in pain:
                s1 = template
                break
        if "Had a look" not in s1:
            break

    # S2: Consequence — real talk, not salesy
    s2_map = {
        "not mobile": "Over half of web traffic is mobile at this point. A rough mobile experience means most visitors never even see what you offer properly.",
        "no ssl": "Beyond the trust issue, Google actually uses HTTPS as a ranking signal. No SSL means lower visibility in search results too.",
        "no live chat": "A lot of customers prefer chatting over calling, especially outside business hours. Without it they just move on to whoever responds first.",
        "no analytics": "You could be paying for ads that don't actually bring in customers and never know it. Analytics tells you what's really working.",
        "no blog": "Businesses that blog consistently get significantly more website visitors. Your competitors who create content are pulling ahead on Google.",
        "thin content": "Google can't rank pages that don't have substance. Thin pages get buried in results and customers never find you.",
        "no testimonial": "Reviews are one of the biggest factors when people choose a local service. Without them, the business with better visibility wins.",
        "no contact": "Every extra step in the process loses people. A simple form can make a real difference in how many inquiries you get.",
        "no privacy": "It's not just about compliance. Customers notice and Google uses it as a ranking factor too.",
        "slow": "Even a one second delay drops conversions noticeably. Over a month that adds up to a lot of missed visitors.",
        "outdated": "A website is usually the first impression. If it looks dated, people assume the business is dated too and look elsewhere.",
        "no booking": "Manual booking means phone tag, missed calls, and customers who just go somewhere easier. Online booking fixes all of that.",
        "hiring actively": "The faster you grow, the more manual work piles up. Automating lead capture and follow up frees up time for the actual growth.",
    }
    s2 = "These kinds of issues compound over time. More lost visitors, more lost revenue."
    for pain in pains_lower:
        for key, template in s2_map.items():
            if key in pain:
                s2 = template
                break
        if "These kinds" not in s2:
            break

    # S3: Soft proof — brief, not braggy
    s3 = f"I built the nanosoft.agency/portfolio with examples of similar fixes if you want to see what the work looks like."

    # S4: CTA — casual yes/no question
    s4 = f"Is improving {domain} something you're looking at this month?"
    if any("mobile" in p or "outdated" in p for p in pains_lower):
        s4 = f"Want me to send over a quick screen recording showing the main issue on {domain}? Takes about 2 minutes to watch."
    elif any("analytics" in p for p in pains_lower):
        s4 = f"Would it be useful to see what your competitors' online presence looks like compared to yours?"
    elif any("booking" in p or "live chat" in p for p in pains_lower):
        s4 = f"Curious if seeing how another local business doubled their inquiries with online booking would be useful?"
    elif any("hiring" in p for p in pains_lower):
        s4 = f"Want to see how automation could cut down the manual workload as you scale up?"

    body = f"{s1}\n\n{s2}\n\n{s3}\n\n{s4}\n\n{SIGNATURE}"

    # Validate
    word_count = len(body.split())
    violations = []

    if word_count > MAX_WORDS:
        violations.append(f"too_long:{word_count}w")
        body = f"{s1}\n\n{s2}\n\n{s4}\n\n{SIGNATURE}"
        word_count = len(body.split())

    if len(subject) > MAX_SUBJECT:
        violations.append(f"subject:{len(subject)}")

    body_lower = body.lower()
    for phrase in BANNED_PHRASES:
        if phrase in body_lower:
            violations.append(f"banned:{phrase}")
            body = body.replace(phrase, "").replace("  ", " ")

    links = len(re.findall(r'https?://', body))
    if links > 1:
        violations.append(f"links:{links}")

    first_line = body.strip().split("\n")[0].lower()
    if first_line.startswith(("i ", "we ")):
        violations.append("starts_with_I")

    # Check for hyphens in body (excluding signature)
    body_no_sig = body.replace(SIGNATURE, "")
    if "—" in body_no_sig or " - " in body_no_sig:
        violations.append("has_hyphens")

    # Follow-ups
    fu1 = "Did you get a chance to look?\n\nHappy to send a quick screen recording showing exactly what I would fix first."
    fu2 = "No worries if the timing is off. Just let me know and I will close your file."
    if len(pains) > 1:
        p2 = pains[1]
        if len(p2) > 40:
            p2 = p2[:40] + "..."
        fu3 = f"Noticed {p2} on {domain} since my last email.\n\nThis one alone could make a real difference.\n\nWorth 10 minutes?"
    else:
        fu3 = f"Noticed another issue on {domain} since my last.\n\nWorth 10 minutes this week?"

    return {
        "to": email,
        "subject": subject,
        "body": body,
        "company": company,
        "domain": domain,
        "pain_points_used": pains[0] if pains else "",
        "all_pain_points": pain_points,
        "word_count": word_count,
        "subject_length": len(subject),
        "follow_up_1": fu1,
        "follow_up_2": fu2,
        "follow_up_3": fu3,
        "is_valid": len(violations) == 0,
        "violations": violations,
        "drafted_at": datetime.now(BD_TZ).isoformat(),
        "status": "drafted",
    }


# ── GMAIL DRAFT CREATION ───────────────────────────────────
def create_gmail_draft(to_email, subject, body):
    """Create an actual draft in Gmail via Gmail API."""
    try:
        import base64
        from email.mime.text import MIMEText
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        with open("/home/ubuntu/nanosoft/gmail_token.json") as f:
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
            with open("/home/ubuntu/nanosoft/gmail_token.json", "w") as f:
                json.dump(token_data, f)

        service = build("gmail", "v1", credentials=creds)

        msg = MIMEText(body)
        msg['to'] = to_email
        msg['from'] = SMTP_USER
        msg['subject'] = subject

        raw = base64.urlsafe_b64encode(msg.as_string().encode()).decode()

        draft = service.users().drafts().create(
            userId='me',
            body={'message': {'raw': raw}}
        ).execute()

        return draft.get('id')
    except Exception as e:
        print(f"[GMAIL] Draft error for {to_email}: {e}")
        return None


# ── SEND EMAIL ─────────────────────────────────────────────
def send_email(draft):
    """Send email via SMTP."""
    try:
        msg = MIMEMultipart()
        msg['From'] = f"SaJib <{SMTP_USER}>"
        msg['To'] = draft.get("to", "")
        msg['Subject'] = draft.get("subject", "")
        msg.attach(MIMEText(draft.get("body", ""), 'plain'))

        ctx = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls(context=ctx)
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, draft.get("to", ""), msg.as_string())

        with open(SENT_LOG, 'a') as f:
            f.write(json.dumps({
                "to": draft.get("to", ""),
                "company": draft.get("company", ""),
                "subject": draft.get("subject", ""),
                "sent_at": datetime.now(BD_TZ).isoformat()
            }) + "\n")

        return True
    except Exception as e:
        print(f"[SEND] Failed: {draft.get('to', '')} | {e}")
        return False


def send_all_pending(delay=180):
    """Send all drafted-but-unsent emails with configurable delay."""
    from crm import get_crm
    crm = get_crm()

    drafted = crm.get_leads_by_status("Drafted")
    if not drafted:
        print("[QUILL] No drafted leads to send.")
        return 0, 0

    sent = set()
    try:
        with open(SENT_LOG) as f:
            for line in f:
                if line.strip():
                    sent.add(json.loads(line).get("to", ""))
    except:
        pass

    unsent = [d for d in drafted if d.get('Owner Email', '') not in sent]
    if not unsent:
        print("[QUILL] All drafted emails already sent.")
        return 0, 0

    print(f"[QUILL] Sending {len(unsent)} emails ({delay}s gap)...")
    ok = fail = 0

    for i, lead in enumerate(unsent):
        if i > 0:
            print(f"  Waiting {delay}s...")
            time.sleep(delay)

        draft = make_email(lead)
        if not draft:
            continue

        print(f"  [{i+1}/{len(unsent)}] {draft['to']} | {draft['subject']}")

        if send_email(draft):
            crm.update_lead(lead.get("Company Name", ""), {"Status": "Sent"})
            crm.update_lead(lead.get("Company Name", ""), {"Email sent date": datetime.now(BD_TZ).strftime("%Y-%m-%d")})
            ok += 1
        else:
            fail += 1

    print(f"[QUILL] Done: {ok} sent, {fail} failed")
    return ok, fail


def log(msg):
    ts = datetime.now(BD_TZ).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, 'a') as f:
            f.write(line + "\n")
    except:
        pass


# ── CLI ────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='NanoSoft QUILL v11')
    parser.add_argument('action', choices=['draft', 'send', 'test'], help='Action to perform')
    parser.add_argument('--delay', type=int, default=180, help='Seconds between emails')
    args = parser.parse_args()

    if args.action == 'test':
        from crm import get_crm
        crm = get_crm()
        leads = crm.get_leads_by_status("Qualified")
        if leads:
            lead = leads[0]
            d = make_email(lead)
            if d:
                print("SUBJECT:", d['subject'])
                print("WORDS:", d['word_count'])
                print("VALID:", d['is_valid'])
                if d['violations']:
                    print("VIOLATIONS:", d['violations'])
                print("\n--- BODY ---\n", d['body'])

                draft_id = create_gmail_draft(d['to'], d['subject'], d['body'])
                if draft_id:
                    print("\nGmail draft created:", draft_id)
                else:
                    print("\nGmail draft failed")
        else:
            print("No Qualified leads found.")

    elif args.action == 'draft':
        from crm import get_crm
        crm = get_crm()
        leads = crm.get_leads_by_status("Qualified")
        if not leads:
            print("[QUILL] No Qualified leads.")
            sys.exit(0)

        log(f"[QUILL] Drafting {len(leads)} Qualified leads...")
        count = 0
        for i, lead in enumerate(leads):
            d = make_email(lead)
            if d:
                crm.update_lead(lead.get("Company Name", ""), {"Status": "Drafted"})
                crm.update_lead(lead.get("Company Name", ""), {
                    "Follow up 01": d['follow_up_1'],
                    "Follow up 02": d['follow_up_2'],
                    "Follow up 03": d['follow_up_3'],
                })

                draft_id = create_gmail_draft(d['to'], d['subject'], d['body'])

                status = "OK" if d['is_valid'] else "WARN"
                gmail = "GMAIL" if draft_id else "NO_GMAIL"
                log(f"  {status} {gmail} [{i+1}/{len(leads)}] {d['company'][:35]} | {d['word_count']}w | {d['subject']}")
                count += 1

        log(f"[QUILL] Done: {count} drafted")

    elif args.action == 'send':
        ok, fail = send_all_pending(delay=args.delay)
        print(f"\nSent: {ok}, Failed: {fail}")
