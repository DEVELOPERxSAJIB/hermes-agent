#!/usr/bin/env python3
"""
NanoSoft QUILL v10 — Cold Email Generator + Gmail Draft Creator
Generates conversational, reply-focused emails.
Creates actual drafts in Gmail Drafts tab via Gmail API.
Follows all Chairman rules.
"""
import json, os, sys, time, smtplib, ssl, re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
SENT_LOG = os.path.join(NANOSOFT_DIR, "emails_sent.jsonl")
LOG_FILE = os.path.join(NANOSOFT_DIR, "quill_v10.log")

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

# ── CONVERSATIONAL PAIN-POINT TEMPLATES ────────────────────
# Each template is specific, about THEM, not us.

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
    
    # ── SUBJECT ──
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
    
    subject = f"{domain} — {impact}"
    if len(subject) > MAX_SUBJECT:
        subject = f"{domain.split('.')[0]} — {impact}"
    if len(subject) > MAX_SUBJECT:
        subject = subject[:MAX_SUBJECT].rstrip()
    
    # ── BODY: Conversational, 4 paragraphs, reply-focused ──
    
    # S1: Specific observation — about THEM, punchy
    s1_options = {
        "not mobile": f"{domain} isn't mobile-friendly — visitors on phones see a broken layout and bounce immediately.",
        "no ssl": f"{domain} has no SSL. Chrome shows 'Not Secure' to every visitor right in the address bar.",
        "no live chat": f"{domain} has no live chat. When someone has a question at 9pm, they find someone who responds faster.",
        "no analytics": f"{domain} has no analytics. You have zero data about who visits or why they leave.",
        "no blog": f"{domain} has no blog. That means zero free traffic from Google — you're paying for every visitor.",
        "thin content": f"{domain} has very thin content. Google can't rank what it can't read.",
        "no testimonial": f"{domain} has no testimonials. 72% of buyers read reviews before choosing a business.",
        "no contact": f"{domain} has no clear way to get in touch. If it takes more than 5 seconds, they're gone.",
        "no privacy": f"{domain} has no privacy policy page. That's a trust gap and a Google ranking signal.",
        "slow": f"{domain} takes too long to load. Every extra second means 7% fewer conversions.",
        "outdated": f"{domain} looks like it was built 15+ years ago. Visitors judge the business within 3 seconds.",
        "no booking": f"{domain} has no online booking. Customers who want instant confirmation go to competitors who do.",
        "hiring actively": f"Hiring actively is a great sign — growth means operational scaling. But manual processes slow growth.",
    }
    s1 = f"{domain} has website issues that are likely costing you customers."
    for pain in pains_lower:
        for key, template in s1_options.items():
            if key in pain:
                s1 = template
                break
        if not s1.startswith(domain + " has website"):
            break
    
    # S2: Consequence — what this means for their revenue
    s2_options = {
        "not mobile": "Over 60% of web traffic is mobile. A broken mobile experience means losing the majority of potential customers before they ever see your services.",
        "no ssl": "Beyond the security risk, Google uses HTTPS as a ranking signal. No SSL = lower search visibility and lost trust.",
        "no live chat": "73% of customers prefer live chat. Without it, you lose the majority who want instant answers — especially outside business hours.",
        "no analytics": "You could be spending money on marketing that doesn't work and never know it. Analytics tells you what actually brings customers in.",
        "no blog": "Businesses that blog get 55% more website visitors. Your competitors who blog are capturing your potential customers from Google.",
        "thin content": "Google needs substance to rank. Thin pages signal low quality and get buried.",
        "no testimonial": "Social proof is the #1 factor in local service decisions. Without visible reviews, customers choose competitors.",
        "no contact": "Friction kills conversions. A simple contact form can double inquiry rates.",
        "no privacy": "Privacy policies aren't just legal compliance — they build trust and improve Google rankings.",
        "slow": "A 1-second delay in load time reduces conversions by 7%. Over a month, that's hundreds of lost visitors.",
        "outdated": "People judge a business by its website within 3 seconds. An outdated site means they assume the business is outdated too — and go elsewhere.",
        "no booking": "Customers who can't book online go to competitors who offer instant confirmation. Manual booking = lost revenue.",
        "hiring actively": "Growth is great — but if your website can't capture and convert leads automatically, you'll keep burning manual effort on tasks software could handle.",
    }
    s2 = "These issues compound every month — more lost visitors, more lost revenue."
    for pain in pains_lower:
        for key, template in s2_options.items():
            if key in pain:
                s2 = template
                break
        if not "These issues compound" in s2:
            break
    
    # S3: Proof — conversational, not salesy
    s3 = "Fixed similar issues for other businesses — here's the portfolio: nanosoft.agency/portfolio"
    
    # S4: CTA — yes/no question, low friction
    s4 = f"Is {domain} something you're looking to improve this month?"
    if any("mobile" in p or "outdated" in p for p in pains_lower):
        s4 = f"Can I send you a 2-minute screen recording showing the biggest issue on {domain}?"
    elif any("analytics" in p for p in pains_lower):
        s4 = f"Would it be worth 10 minutes to see what your competitors' analytics reveal about your market?"
    elif any("booking" in p or "live chat" in p for p in pains_lower):
        s4 = f"Would seeing how online booking doubled another {niche if 'niche' in dir() else 'local'} business's inquiries be useful?"
    elif any("hiring" in p for p in pains_lower):
        s4 = f"Can I show you how automation could reduce the manual workload as you scale?"
    
    body = f"{s1}\n\n{s2}\n\n{s3}\n\n{s4}\n\nSaJib"
    
    # Validate
    word_count = len(body.split())
    violations = []
    
    if word_count > MAX_WORDS:
        violations.append(f"too_long:{word_count}w")
        # Trim: remove S3 to get under limit
        body = f"{s1}\n\n{s2}\n\n{s4}\n\nSaJib"
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
    
    # Follow-ups
    fu1 = "Did you get a chance to look?\n\nHappy to send a 2-minute screen recording showing exactly what I would fix first."
    fu2 = "No worries if the timing is off — just let me know and I will close your file."
    if len(pains) > 1:
        p2 = pains[1]
        if len(p2) > 40: p2 = p2[:40] + "..."
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
        
        # Log as sent
        with open(SENT_LOG, 'a') as f:
            f.write(json.dumps({
                "to": draft.get("to",""),
                "company": draft.get("company",""),
                "subject": draft.get("subject",""),
                "sent_at": datetime.now(BD_TZ).isoformat()
            }) + "\n")
        
        return True
    except Exception as e:
        print(f"[SEND] Failed: {draft.get('to','')} | {e}")
        return False


def send_all_pending(delay=180):
    """Send all drafted-but-unsent emails with configurable delay."""
    from crm import get_crm, STATUS_EMAIL_SENT, STATUS_DRAFTED
    crm = get_crm()
    
    drafted = crm.get_leads_by_status(STATUS_DRAFTED)
    if not drafted:
        print("[QUILL] No drafted leads to send.")
        return 0, 0
    
    # Load sent log to avoid resending
    sent = set()
    try:
        with open(SENT_LOG) as f:
            for line in f:
                if line.strip():
                    sent.add(json.loads(line).get("to",""))
    except:
        pass
    
    unsent = [d for d in drafted if d.get('Owner Email','') not in sent]
    if not unsent:
        print("[QUILL] All drafted emails already sent.")
        return 0, 0
    
    print(f"[QUILL] Sending {len(unsent)} emails ({delay}s gap)...")
    ok = fail = 0
    
    for i, lead in enumerate(unsent):
        if i > 0:
            print(f"  Waiting {delay}s...")
            time.sleep(delay)
        
        # Build draft from CRM data
        draft = make_email(lead)
        if not draft:
            continue
        
        print(f"  [{i+1}/{len(unsent)}] {draft['to']} | {draft['subject']}")
        
        if send_email(draft):
            crm.update_status(lead.get("Company Name",""), STATUS_EMAIL_SENT)
            crm.update_lead(lead.get("Company Name",""), {"Email sent date": datetime.now(BD_TZ).strftime("%Y-%m-%d")})
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
    parser = argparse.ArgumentParser(description='NanoSoft QUILL v10')
    parser.add_argument('action', choices=['draft','send','test'], help='Action to perform')
    parser.add_argument('--delay', type=int, default=180, help='Seconds between emails')
    args = parser.parse_args()
    
    if args.action == 'test':
        # Test: draft one email and create Gmail draft
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
                print("\n--- BODY ---\n", d['body'])
                
                # Try creating Gmail draft
                draft_id = create_gmail_draft(d['to'], d['subject'], d['body'])
                if draft_id:
                    print("\n✅ Gmail draft created:", draft_id)
                else:
                    print("\n⚠️ Gmail draft failed (token issue)")
        else:
            print("No Qualified leads found.")
    
    elif args.action == 'draft':
        from crm import get_crm, STATUS_DRAFTED
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
                # Update CRM
                crm.update_status(lead.get("Company Name",""), STATUS_DRAFTED)
                crm.update_lead(lead.get("Company Name",""), {
                    "Follow up 01": d['follow_up_1'],
                    "Follow up 02": d['follow_up_2'],
                    "Follow up 03": d['follow_up_3'],
                })
                
                # Create Gmail draft
                draft_id = create_gmail_draft(d['to'], d['subject'], d['body'])
                
                status = "✅" if d['is_valid'] else "⚠️"
                gmail = "📧" if draft_id else "❌"
                log(f"  {status}{gmail} [{i+1}/{len(leads)}] {d['company'][:35]} | {d['word_count']}w | {d['subject']}")
                count += 1
        
        log(f"[QUILL] Done: {count} drafted")
    
    elif args.action == 'send':
        ok, fail = send_all_pending(delay=args.delay)
        print(f"\nSent: {ok}, Failed: {fail}")
