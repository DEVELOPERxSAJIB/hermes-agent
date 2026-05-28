#!/usr/bin/env python3
"""
QUILL Daily Drafting Agent
Reads "Drafted" leads from CRM, re-drafts all emails with v8 strict rules,
notifies Discord, waits for Chairman's !send command.
"""
import json
import os
import sys
import time
import subprocess
import threading
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
DRAFTS_FILE = "/home/ubuntu/nanosoft/email_drafts.jsonl"
SENT_LOG = "/home/ubuntu/nanosoft/emails_sent.jsonl"
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "nanosoftagency007@gmail.com"
SMTP_PASS = os.environ.get("SMTP_PASS", "wnvp mpne dyvu dheq")
BETWEEN_EMAIL_DELAY = 180  # 3 minutes

sys.path.insert(0, "/home/ubuntu/nanosoft")
from crm import get_crm

# ── BANNED PHRASES ─────────────────────────────────────────
BANNED_PHRASES = [
    "i hope this email finds you well", "i came across your website",
    "i am passionate about", "we are a dedicated team", "i would love to connect",
    "please feel free to reach out", "looking forward to hearing from you",
    "best regards", "sincerely", "to whom it may concern",
    "i noticed you might benefit from", "no obligation", "risk free",
    "act now", "click here", "limited time", "special offer", None
]

# Fix: remove None from list
BANNED_PHRASES = [p for p in BANNED_PHRASES if p]

BANNED_WORDS = ["free", "discount"]  # "free" in context of offer, not "free estimate"

# ── PAIN POINT → CONSEQUENCE ──────────────────────────────
PAIN_CONSEQUENCE = {
    "not mobile responsive": "When more than half your visitors browse on phones and see a broken layout, they leave before they ever read about your services",
    "no mobile phone": "When more than half your visitors browse on phones and see a broken layout, they leave before they ever read about your services",
    "no ssl": "Chrome shows 'Not Secure' to every visitor on your site",
    "https": "Chrome shows 'Not Secure' to every visitor on your site",
    "outdated ui": "People judge a business by its website — if yours looks old, they assume the business is too",
    "looks like early 2000s": "People judge a business by its website — if yours looks old, they assume the business is too",
    "backdated ui": "Visitors expect modern, fast websites — heavy inline styles make your site look outdated and slow",
    "built before 2020": "Old code is slow code and Google ranks newer sites higher",
    "slow page load": "Every extra second of load time increases bounce rate — visitors get impatient and leave",
    "no clear call-to-action": "If a visitor does not know what to do next, they do nothing — and eventually leaves",
    "no cta": "If a visitor does not know what to do next, they do nothing — and eventually leaves",
    "no analytics": "Without analytics, you have no idea how many people visit or why they leave",
    "no live chat": "When someone has a question at 9pm and cannot get an answer, they find someone who responds faster",
    "thin content": "Google needs content to rank your site — thin content means you are invisible in search",
    "no blog": "No blog means no organic traffic from Google — you are paying for every visitor or getting none",
    "no testimonials": "Most people read reviews before choosing — without testimonials on your site, they go to a competitor who has them",
    "no contact form": "If someone cannot reach you in under 5 seconds, they are gone",
    "no easy way to contact": "If someone cannot reach you in under 5 seconds, they are gone",
    "no privacy policy": "Missing privacy policy is a trust gap — and Google uses it as a ranking signal",
    "outdated font": "Typography is one of the first things people judge — outdated fonts make your whole business feel outdated",
}

# Subject line short impact phrases
SHORT_IMPACT = {
    "losing visitors who need instant help": "losing after-hours leads",
    "lost trust and lost customers": "Chrome warns visitors",
    "lost trust and credibility": "looking outdated",
    "lost visitors and lower Google rankings": "loading slowly",
    "lost customers and leads": "losing customers",
    "lost trust and conversions": "losing conversions",
    "flying blind on marketing spend": "no visitor data",
    "invisible on Google": "invisible on Google",
    "missing free Google traffic": "no Google traffic",
    "lost inquiries every day": "losing inquiries",
    "lower trust and lower rankings": "ranking lower",
    "hurts professional image": "hurts your image",
    "lost revenue": "losing revenue",
    "lost members and bookings": "losing members",
    "lost trust and customers": "losing trust",
}


def get_consequence(pain_points_str):
    if not pain_points_str:
        return None, "needs attention"
    pains = [p.strip().lower() for p in pain_points_str.split(",") if p.strip()]
    for pain in pains:
        for key, consequence in PAIN_CONSEQUENCE.items():
            if key in pain:
                return consequence, SHORT_IMPACT.get(
                    " ".join(consequence.lower().split()[:3]),
                    "needs attention"
                )
    return "These issues are likely costing you potential customers every day", "losing customers"


def draft_email_v8(lead):
    """Draft email following QUILL v8 strict rules."""
    company = lead.get("Company Name", "").strip()
    website = lead.get("Website (if have)", "").strip()
    pain_points = lead.get("Pain Point", "").strip()
    email = lead.get("Owner Email", "").strip()

    if not email:
        return None

    # Extract domain
    domain = ""
    if website:
        import re
        domain = re.sub(r'^https?://(www\.)?', '', website).split('/')[0]
    if not domain:
        domain = email.split('@')[1] if '@' in email else "your site"

    consequence, impact_short = get_consequence(pain_points)

    # ── SUBJECT (max 33 chars, 6 words) ──
    subject = f"{domain} — {impact_short}"
    if len(subject) > 33:
        short_domain = domain.replace("www.", "").split(".")[0]
        subject = f"{short_domain} — {impact_short}"
    if len(subject) > 33:
        subject = subject[:33].rstrip()

    # ── BODY (4 sentences, 50-125 words) ──
    import re

    # Pick primary pain point
    primary_pain = ""
    if pain_points:
        pains = [p.strip() for p in pain_points.split(",") if p.strip()]
        primary_pain = pains[0] if pains else ""

    pain_lower = primary_pain.lower()

    # Sentence 1: Observation (specific, about THEM)
    if "no ssl" in pain_lower or "https" in pain_lower:
        s1 = f"{domain} has no SSL — Chrome shows 'Not Secure' to every visitor."
    elif "not mobile" in pain_lower or "mobile" in pain_lower:
        s1 = f"{domain} is not mobile responsive — over 60% of your visitors see a broken layout on their phones."
    elif "outdated" in pain_lower or "early 2000s" in pain_lower:
        s1 = f"{domain} looks like it was built 15+ years ago — table layout, old fonts, inline styles."
    elif "slow" in pain_lower or "load" in pain_lower:
        s1 = f"{domain} takes too long to load."
    elif "backdated" in pain_lower:
        s1 = f"{domain} uses inline styles with no modern CSS framework."
    elif "no analytics" in pain_lower:
        s1 = f"{domain} has no analytics set up."
    elif "no live chat" in pain_lower:
        s1 = f"{domain} has no live chat."
    elif "no cta" in pain_lower or "call-to-action" in pain_lower:
        s1 = f"{domain} has no clear call-to-action."
    elif "no contact" in pain_lower:
        s1 = f"{domain} has no contact form."
    elif "no testimonial" in pain_lower:
        s1 = f"{domain} has no testimonials on the homepage."
    elif "no blog" in pain_lower:
        s1 = f"{domain} has no blog."
    elif "no privacy" in pain_lower:
        s1 = f"{domain} has no privacy policy."
    elif "font" in pain_lower:
        s1 = f"{domain} uses outdated font choices."
    else:
        s1 = f"{domain} has issues that are costing you potential customers."

    # Sentence 2: Consequence
    s2 = consequence[0].upper() + consequence[1:] + "."

    # Sentence 3: Proof
    s3 = "Fixed similar issues for other local service businesses — here is the portfolio: nanosoft.agency/portfolio"

    # Sentence 4: Question (low-friction CTA)
    s4 = f"Is {domain} currently bringing in any new inquiries at all?"

    body = f"{s1}\n\n{s2}\n\n{s3}\n\n{s4}\n\nSaJib\nnanosoft.agency"

    # ── FOLLOW-UPS ──
    fu1 = "Did you get a chance to look?\n\nHappy to send a 2-minute screen recording showing exactly what I would fix first."
    fu2 = "No worries if the timing is off — just let me know and I will close your file."

    # Pick second pain point for follow-up 3
    second_pain = ""
    if len(pains) > 1:
        second_pain = pains[1]
    if second_pain:
        fu3 = f"Noticed {second_pain.lower()} on {domain} since my last email.\n\nThis one alone could make a real difference.\n\nWorth 10 minutes this week?"
    else:
        fu3 = f"Noticed another issue on {domain} since my last email.\n\nThis one alone could make a real difference.\n\nWorth 10 minutes this week?"

    # ── VALIDATE ──
    word_count = len(body.split())
    issues = []

    if word_count > 125:
        issues.append(f"too long: {word_count}w")
    if len(subject) > 33:
        issues.append(f"subject: {len(subject)}chars")
    if "**" in body or "__" in body:
        issues.append("markdown")
    if body.strip().split("\n")[0].lower().startswith(("i ", "we ", "my ")):
        issues.append("starts with I/We")
    
    # Check banned phrases
    body_lower = body.lower()
    for phrase in BANNED_PHRASES:
        if phrase in body_lower:
            issues.append(f"banned: {phrase}")

    # Count links
    link_count = len(re.findall(r'https?://', body))
    if link_count > 1:
        issues.append(f"too many links: {link_count}")

    is_valid = len(issues) == 0

    return {
        "to": email,
        "subject": subject,
        "body": body,
        "company": company,
        "domain": domain,
        "pain_points_used": primary_pain,
        "all_pain_points": pain_points,
        "word_count": word_count,
        "subject_length": len(subject),
        "follow_up_1": fu1,
        "follow_up_2": fu2,
        "follow_up_3": fu3,
        "is_valid": is_valid,
        "violations": issues,
        "drafted_at": datetime.now(BD_TZ).isoformat(),
        "status": "drafted",
    }


# ── FILE OPS ──────────────────────────────────────────────

def load_drafts():
    drafts = []
    try:
        with open(DRAFTS_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    drafts.append(json.loads(line))
    except FileNotFoundError:
        pass
    return drafts


def save_drafts(drafts):
    with open(DRAFTS_FILE, 'w') as f:
        for d in drafts:
            f.write(json.dumps(d) + "\n")


def load_sent():
    sent = set()
    try:
        with open(SENT_LOG, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    sent.add(json.loads(line).get("to", ""))
    except FileNotFoundError:
        pass
    return sent


def mark_sent(draft):
    with open(SENT_LOG, 'a') as f:
        f.write(json.dumps({
            "to": draft.get("to", ""),
            "company": draft.get("company", ""),
            "subject": draft.get("subject", ""),
            "sent_at": datetime.now(BD_TZ).isoformat(),
        }) + "\n")


# ── SEND EMAIL ─────────────────────────────────────────────

def send_email(draft):
    to_email = draft.get("to", "")
    subject = draft.get("subject", "")
    body = draft.get("body", "")
    if not to_email or not subject or not body:
        return False
    try:
        msg = MIMEMultipart()
        msg['From'] = f"SaJib <{SMTP_USER}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        ctx = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls(context=ctx)
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, to_email, msg.as_string())
        mark_sent(draft)
        print(f"  ✓ SENT: {to_email} | {draft.get('company', '')[:40]}")
        return True
    except Exception as e:
        print(f"  ✗ FAILED: {to_email} | {str(e)[:60]}")
        return False


# ── DAILY DRAFTING ─────────────────────────────────────────

def run_daily_drafting():
    """Main: read Drafted leads from CRM, re-draft all with v8 rules."""
    print(f"[QUILL] Starting daily draft run — {datetime.now(BD_TZ).strftime('%Y-%m-%d %H:%M')} BD")

    crm = get_crm()

    # Get ALL Drafted leads
    drafted_leads = crm.get_leads_by_status("Drafted")

    if not drafted_leads:
        print("[QUILL] No Drafted leads found.")
        return []

    print(f"[QUILL] Found {len(drafted_leads)} Drafted leads. Re-drafting with v8 rules...")

    new_drafts = []
    valid_count = 0
    invalid_count = 0

    for lead in drafted_leads:
        email = lead.get("Owner Email", "").strip()
        if not email:
            continue

        draft = draft_email_v8(lead)
        if not draft:
            continue

        new_drafts.append(draft)

        if draft["is_valid"]:
            valid_count += 1
        else:
            invalid_count += 1
            print(f"  ⚠ {lead.get('Company Name', '?')[:40]} | violations: {draft['violations']}")

        print(f"  {'✅' if draft['is_valid'] else '⚠️'} {lead.get('Company Name', '?')[:40]:40} | {email[:35]:35} | {draft['word_count']}w | {draft['subject']}")

    # Replace old drafts with new v8 drafts
    save_drafts(new_drafts)

    print(f"\n[QUILL] Done: {len(new_drafts)} drafted ({valid_count} valid, {invalid_count} need review)")

    # NEXUS will post to Discord automatically via daily email summary
    print(f"[QUILL] Drafts saved to {DRAFTS_FILE}. NEXUS will notify Discord.")
    print(f"[QUILL] Reply '!send all' on Discord when ready to send.")

    return new_drafts


# ── SEND ALL ───────────────────────────────────────────────

def send_all_pending():
    """Send all drafted but unsent emails, 1-by-1, 3-min gap."""
    drafts = load_drafts()
    sent = load_sent()
    unsent = [d for d in drafts if d.get("to", "") not in sent]

    if not unsent:
        print("[QUILL] No pending emails to send.")
        return 0, 0

    print(f"[QUILL] Sending {len(unsent)} emails ({BETWEEN_EMAIL_DELAY}s gap)...")
    sent_count = 0
    failed_count = 0

    for idx, draft in enumerate(unsent):
        if idx > 0:
            print(f"  Waiting {BETWEEN_EMAIL_DELAY}s...")
            time.sleep(BETWEEN_EMAIL_DELAY)

        print(f"  [{idx+1}/{len(unsent)}] {draft.get('to', '')}...")
        if send_email(draft):
            sent_count += 1
        else:
            failed_count += 1

    print(f"\n[QUILL] Done: {sent_count} sent, {failed_count} failed")
    return sent_count, failed_count


# ── CLI ────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "send":
        send_all_pending()
    else:
        run_daily_drafting()
