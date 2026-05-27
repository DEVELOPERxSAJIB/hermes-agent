"""
QUILL v8 — Autonomous Email Agent
Checks CRM daily → drafts emails → notifies Discord → waits for !send → sends 1-by-1.

This is the FULL autonomous loop. QUILL runs independently.
NEXUS just relays Discord commands to QUILL.

Flow:
1. QUILL cron runs daily → reads "New" leads from CRM
2. Drafts emails following strict rules (Section 2-9)
3. Saves drafts to email_drafts.jsonl
4. Updates CRM status from "New" → "Drafted"
5. Posts each draft to Discord #nexus channel
6. Waits for Chairman's !send command
7. Sends 1-by-1 with 3-min gap between each
"""
import json
import re
import os
import sys
import time
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
DRAFTS_FILE = "/home/ubuntu/nanosoft/email_drafts.jsonl"
SENT_LOG = "/home/ubuntu/nanosoft/emails_sent.jsonl"
DRAFTED_FLAG = "/home/ubuntu/nanosoft/quill_drafted_today.flag"
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "nanosoftagency007@gmail.com"
SMTP_PASS = "wnvp mpne dyvu dheq"
BETWEEN_EMAIL_DELAY = 180  # 3 minutes

# Add parent dir to path for CRM
sys.path.insert(0, "/home/ubuntu/nanosoft")
from crm import get_crm, STATUS_NEW, STATUS_EMAIL_SENT, STATUS_FOLLOWUP_1, STATUS_FOLLOWUP_2

# ── BANNED PHRASES & WORDS ─────────────────────────────────
BANNED_PHRASES = [
    "i hope this email finds you well",
    "i came across your website",
    "i am passionate about",
    "we are a dedicated team",
    "i would love to connect",
    "please feel free to reach out",
    "looking forward to hearing from you",
    "best regards",
    "sincerely",
    "to whom it may concern",
    "i noticed you might benefit from",
    "no obligation",
    "risk free",
    "act now",
    "click here",
    "limited time",
    "special offer",
    "guaranteed",
    "100%",
    "earn money",
    "make money",
]
BANNED_WORDS = ["free", "discount"]

# ── PAIN POINT → CONSEQUENCE MAPPING ──────────────────────
PAIN_CONSEQUENCE = {
    "not mobile responsive": {
        "consequence": "Over 60% of your visitors are on phones — they see a broken layout and leave within seconds",
        "business_impact": "lost members and bookings",
    },
    "no ssl/https": {
        "consequence": "Chrome shows a Not Secure warning to every single visitor — most people close the tab immediately",
        "business_impact": "lost trust and lost customers",
    },
    "outdated ui": {
        "consequence": "Visitors see an old design and assume your business is no longer active — 94% of first impressions are design-related",
        "business_impact": "lost trust and credibility",
    },
    "looks like early 2000s": {
        "consequence": "Visitors see an old design and assume your business is no longer active — 94% of first impressions are design-related",
        "business_impact": "lost trust and credibility",
    },
    "built before 2020": {
        "consequence": "Old code means slow load times and security vulnerabilities — visitors expect fast, smooth experiences",
        "business_impact": "lost visitors and lower Google rankings",
    },
    "slow page load": {
        "consequence": "Every extra second of load time increases bounce rate by 32% — that is happening to your site right now",
        "business_impact": "lost customers and leads",
    },
    "backdated ui": {
        "consequence": "Inline styles and no modern CSS framework means your site looks amateur — visitors question your professionalism",
        "business_impact": "lost trust and conversions",
    },
    "no clear call-to-action": {
        "consequence": "Visitors browse your site but never reach out because nothing tells them what to do next",
        "business_impact": "lost inquiries and bookings",
    },
    "no analytics": {
        "consequence": "You have no idea how many people visit, where they come from, or why they leave — you are making business decisions blind",
        "business_impact": "flying blind on marketing spend",
    },
    "no live chat": {
        "consequence": "When a potential customer has a question at 10pm and cannot get an answer, they call a competitor who responds faster",
        "business_impact": "lost leads after hours",
    },
    "thin content": {
        "consequence": "Google has almost nothing to index — websites with more quality pages rank for more keywords and get significantly more organic traffic",
        "business_impact": "invisible on Google",
    },
    "no blog": {
        "consequence": "No blog means zero organic content marketing — you are paying for every visitor or getting none from search",
        "business_impact": "missing free Google traffic",
    },
    "no testimonials": {
        "consequence": "72% of customers read reviews before choosing a local business — if they cannot see social proof on your site, they go to a competitor",
        "business_impact": "lost trust and customers",
    },
    "no easy way to contact": {
        "consequence": "If a potential customer cannot find a way to reach you in 5 seconds, they are gone — making it easy to contact you is the single biggest factor in converting visitors",
        "business_impact": "lost inquiries every day",
    },
    "no privacy policy": {
        "consequence": "Missing privacy policy and terms undermines trust — Google also considers these pages a trust signal for rankings",
        "business_impact": "lower trust and lower rankings",
    },
    "outdated font": {
        "consequence": "Typography is one of the first things visitors subconsciously judge — outdated fonts signal an outdated business",
        "business_impact": "hurts professional image",
    },
}

# Short impact phrases for subject lines (pre-counted to fit 33 chars)
SHORT_IMPACT = {
    "lost members and bookings": "losing members",
    "lost trust and lost customers": "losing trust",
    "lost trust and credibility": "looking outdated",
    "lost visitors and lower Google rankings": "loading slowly",
    "lost customers and leads": "losing leads",
    "lost trust and conversions": "losing leads",
    "flying blind on marketing spend": "no analytics data",
    "lost leads after hours": "losing after-hours leads",
    "invisible on Google": "invisible on Google",
    "missing free Google traffic": "no Google traffic",
    "lost trust and customers": "losing trust",
    "lost inquiries every day": "losing inquiries",
    "lower trust and lower rankings": "ranking lower",
    "hurts professional image": "hurts your image",
    "lost revenue": "losing revenue",
}


def _get_consequence(pain_points_str):
    """Map pain points to business consequences."""
    if not pain_points_str:
        return None, None
    pains = [p.strip().lower() for p in pain_points_str.split(",") if p.strip()]
    for pain in pains:
        for key, data in PAIN_CONSEQUENCE.items():
            if key in pain:
                return data["consequence"], data["business_impact"]
    return "These issues are likely costing you potential customers every day", "lost revenue"


def _count_words(text):
    return len(text.split())


def _check_banned(text):
    text_lower = text.lower()
    violations = []
    for phrase in BANNED_PHRASES:
        if phrase in text_lower:
            violations.append(phrase)
    for word in BANNED_WORDS:
        if re.search(rf'\b{word}\b', text_lower):
            violations.append(word)
    return violations


def _validate_draft(subject, body, pain_points, company):
    """Validate draft against all rules. Returns (is_valid, violations)."""
    violations = []

    if len(subject) > 33:
        violations.append(f"Subject too long: {len(subject)} chars (max 33)")
    if len(subject.split()) > 6:
        violations.append(f"Subject too many words: {len(subject.split())} (max 6)")
    if "?" in subject:
        violations.append("Subject contains question mark")
    if "!" in subject:
        violations.append("Subject contains exclamation mark")
    if "quick question" in subject.lower():
        violations.append("Subject contains 'quick question'")

    word_count = _count_words(body)
    if word_count > 125:
        violations.append(f"Body too long: {word_count} words (max 125)")

    if "**" in body or "__" in body or "###" in body:
        violations.append("Body contains markdown formatting")

    price_patterns = [r'\$\d+', r'\d+\s*dollars', r'pricing', r'costs?\s*\$', r'affordable price']
    for p in price_patterns:
        if re.search(p, body.lower()):
            violations.append(f"Body contains pricing reference")
            break

    first_line = body.strip().split("\n")[0].strip()
    if first_line.lower().startswith(("i ", "we ", "my ")):
        violations.append("First sentence starts with I/We/My — must be about THEM")

    banned_found = _check_banned(body)
    if banned_found:
        violations.append(f"Banned phrases: {', '.join(banned_found[:3])}")

    lines = [l.strip() for l in body.strip().split("\n") if l.strip()]
    last_lines = "\n".join(lines[-5:])
    if "?" not in last_lines:
        violations.append("No question mark in CTA area — must be yes/no question")

    if "best regards" in body.lower() or "sincerely" in body.lower() or "nanosoft team" in body.lower():
        violations.append("Signature uses banned closing — use first name only")

    link_count = len(re.findall(r'https?://', body))
    if link_count > 1:
        violations.append(f"Too many links: {link_count} (max 1)")

    return len(violations) == 0, violations


def draft_email(lead: dict) -> dict:
    """Draft a cold outreach email following all QUILL rules."""
    company = lead.get("Company Name", "").strip()
    website = lead.get("Website (if have)", "").strip()
    pain_points = lead.get("Pain Point", "").strip()
    email = lead.get("Owner Email", "").strip()

    # Extract domain
    domain = ""
    if website:
        domain = re.sub(r'^https?://(www\.)?', '', website).split('/')[0]
    if not domain:
        domain = email.split('@')[1] if '@' in email else "your site"

    consequence, business_impact = _get_consequence(pain_points)

    # Pick primary pain point
    primary_pain = ""
    if pain_points:
        pains = [p.strip() for p in pain_points.split(",") if p.strip()]
        critical = ["no ssl", "not mobile", "outdated ui", "slow page", "backdated", "built before"]
        for p in pains:
            for c in critical:
                if c in p.lower():
                    primary_pain = p
                    break
            if primary_pain:
                break
        if not primary_pain:
            primary_pain = pains[0]

    # ── SUBJECT LINE ──
    impact_short = SHORT_IMPACT.get(business_impact, "needs attention")
    subject = f"{domain} — {impact_short}"

    if len(subject) > 33:
        short_domain = domain.replace("www.", "").split(".")[0]
        subject = f"{short_domain} — {impact_short}"

    if len(subject) > 33:
        subject = subject[:33].rstrip()

    # ── BODY (4 sentences) ──
    # Sentence 1: The Observation — raw fact, what we see
    # Sentence 2: The Consequence — what it costs them (business impact)
    # These must NOT repeat the same point. S1 = what's wrong. S2 = what it costs.

    pain_lower = primary_pain.lower()
    if "no ssl" in pain_lower or "https" in pain_lower:
        s1 = f"{domain} has no SSL certificate — every visitor sees a 'Not Secure' warning in Chrome."
        s2 = "Most people close the tab immediately when they see that warning."
    elif "not mobile" in pain_lower or "mobile" in pain_lower:
        s1 = f"{domain} is not mobile responsive — the layout breaks on phones."
        s2 = "Over 60% of your visitors are on phones. They see a broken site and leave within seconds."
    elif "outdated" in pain_lower or "early 2000s" in pain_lower:
        s1 = f"{domain} looks like it was built 15+ years ago — table-based layout, old fonts, inline styles."
        s2 = "Visitors see an old design and assume your business is no longer active."
    elif "slow" in pain_lower or "load" in pain_lower:
        s1 = f"{domain} takes too long to load."
        s2 = "Every extra second increases bounce rate by 32% — that is happening to your site right now."
    elif "backdated" in pain_lower:
        s1 = f"{domain} uses inline styles with no modern CSS framework."
        s2 = "It looks amateur — visitors question your professionalism."
    elif "no analytics" in pain_lower:
        s1 = f"{domain} has no analytics set up."
        s2 = "You have no idea how many people visit, where they come from, or why they leave."
    elif "no live chat" in pain_lower:
        s1 = f"{domain} has no live chat."
        s2 = "When potential customers have questions after hours, they go to a competitor who responds faster."
    elif "no cta" in pain_lower or "call-to-action" in pain_lower:
        s1 = f"{domain} has no clear call-to-action."
        s2 = "Visitors browse your site but nothing tells them what to do next — so they never reach out."
    elif "no contact" in pain_lower:
        s1 = f"{domain} has no contact form."
        s2 = "If a visitor cannot reach you in 5 seconds, they are gone."
    elif "no testimonial" in pain_lower:
        s1 = f"{domain} has no testimonials on the homepage."
        s2 = "72% of customers read reviews before choosing a local business — without social proof, they go elsewhere."
    elif "no blog" in pain_lower:
        s1 = f"{domain} has no blog."
        s2 = "No blog means zero organic traffic from Google — you are paying for every visitor or getting none."
    elif "no privacy" in pain_lower:
        s1 = f"{domain} has no privacy policy."
        s2 = "Google sees this as a missing trust signal and ranks you lower."
    elif "font" in pain_lower:
        s1 = f"{domain} uses outdated font choices."
        s2 = "Visitors subconsciously judge your business by typography — outdated fonts signal an outdated business."
    else:
        s1 = f"{domain} has several issues that are likely costing you customers."
        s2 = "These problems add up — visitors leave before they ever reach out."

    # Sentence 3: The Proof
    s3 = "Fixed similar issues for other local service businesses — here is the portfolio: FamClinic.nl"

    # Sentence 4: The Question
    s4 = f"Is {domain} currently bringing in any new inquiries at all?"

    body = f"{s1}\n\n{s2}\n\n{s3}\n\n{s4}\n\nSaJib\nnanosoft.agency"

    # ── FOLLOW-UPS ──
    follow_up_1 = "Did you get a chance to look?\n\nHappy to send a 2-minute screen recording showing exactly what I would fix first."
    follow_up_2 = "No worries if the timing is off — just let me know and I will close your file."

    second_pain = ""
    if pain_points:
        pains = [p.strip() for p in pain_points.split(",") if p.strip()]
        if len(pains) > 1:
            second_pain = pains[1]

    if second_pain:
        follow_up_3 = f"Noticed {second_pain.lower()} on {domain} since my last email.\n\nFigured I would mention it before I move on — this one alone could make a real difference.\n\nWorth 10 minutes this week?"
    else:
        follow_up_3 = f"Noticed another issue on {domain} since my last email.\n\nFigured I would mention it before I move on — this one alone could make a real difference.\n\nWorth 10 minutes this week?"

    # ── VALIDATE ──
    is_valid, violations = _validate_draft(subject, body, pain_points, company)
    word_count = _count_words(body)

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
        "signature": "SaJib\nnanosoft.agency",
        "follow_up_1": follow_up_1,
        "follow_up_2": follow_up_2,
        "follow_up_3": follow_up_3,
        "is_valid": is_valid,
        "violations": violations,
        "drafted_at": datetime.now(BD_TZ).isoformat(),
        "status": "drafted",
    }


def format_discord_draft(draft: dict) -> str:
    """Format a draft for Discord display."""
    status = "✅ PASS" if draft["is_valid"] else "❌ FAIL"
    lines = [
        f"✍️ QUILL — EMAIL DRAFT",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"LEAD: {draft['company']}",
        f"DOMAIN: {draft['domain']}",
        f"PAIN POINTS USED: {draft['pain_points_used']}",
        f"WORD COUNT: {draft['word_count']} {'✅' if draft['word_count'] <= 125 else '❌'}",
        f"SUBJECT LENGTH: {draft['subject_length']} chars {'✅' if draft['subject_length'] <= 33 else '❌'}",
        f"VALIDATION: {status}",
    ]
    if draft["violations"]:
        lines.append("VIOLATIONS:")
        for v in draft["violations"]:
            lines.append(f"  • {v}")
    lines.extend([
        "",
        f"SUBJECT:",
        f"{draft['subject']}",
        "",
        f"BODY:",
        draft["body"],
        "",
        f"FOLLOW-UP 1 (Day 3):",
        f"{draft['follow_up_1']}",
        "",
        f"FOLLOW-UP 2 (Day 7):",
        f"{draft['follow_up_2']}",
        "",
        f"FOLLOW-UP 3 (Day 14):",
        f"{draft['follow_up_3']}",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ])
    return "\n".join(lines)


# ── FILE OPERATIONS ───────────────────────────────────────

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


def save_draft(draft: dict):
    with open(DRAFTS_FILE, 'a') as f:
        f.write(json.dumps(draft) + "\n")


def load_sent():
    sent = set()
    try:
        with open(SENT_LOG, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    d = json.loads(line)
                    sent.add(d.get("to", ""))
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


# ── EMAIL SENDING ─────────────────────────────────────────

def send_email(draft: dict) -> bool:
    to_email = draft.get("to", "")
    subject = draft.get("subject", "")
    body = draft.get("body", "")

    if not to_email or not subject or not body:
        print(f"  SKIP: Missing fields for {to_email}")
        return False

    try:
        msg = MIMEMultipart()
        msg['From'] = f"NanoSoft <{SMTP_USER}>"
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

    except smtplib.SMTPRecipientsRefused:
        print(f"  ✗ REFUSED: {to_email}")
        return False
    except smtplib.SMTPAuthenticationError:
        print(f"  ✗ AUTH ERROR — check SMTP credentials")
        return False
    except Exception as e:
        print(f"  ✗ ERROR: {to_email} | {str(e)[:60]}")
        return False


def send_all_pending():
    """Send all pending (drafted but not sent) emails, 1-by-1 with 3-min gap."""
    drafts = load_drafts()
    sent = load_sent()
    unsent = [(i, d) for i, d in enumerate(drafts) if d.get("to", "") not in sent]

    if not unsent:
        print("[QUILL] No pending emails to send.")
        return 0, 0

    print(f"[QUILL] Sending {len(unsent)} emails (3-min gap)...")
    sent_count = 0
    failed_count = 0

    for idx, (orig_idx, draft) in enumerate(unsent):
        if idx > 0:
            print(f"  Waiting {BETWEEN_EMAIL_DELAY}s before next...")
            time.sleep(BETWEEN_EMAIL_DELAY)

        print(f"  [{idx+1}/{len(unsent)}] Sending to {draft.get('to', '')}...")
        if send_email(draft):
            sent_count += 1
            # Update CRM status to "Email Sent"
            try:
                crm = get_crm()
                crm.update_status(draft.get("company", ""), STATUS_EMAIL_SENT)
                crm.update_lead(draft.get("company", ""), {
                    "Email sent date": datetime.now(BD_TZ).strftime("%Y-%m-%d")
                })
            except Exception as e:
                print(f"  [CRM] Update failed: {e}")
        else:
            failed_count += 1

    print(f"\n[QUILL] Done: {sent_count} sent, {failed_count} failed")
    return sent_count, failed_count


# ── AUTONOMOUS DAILY DRAFTING ─────────────────────────────

def run_daily_drafting():
    """
    Main autonomous function:
    1. Read "New" leads from CRM
    2. Draft emails for each
    3. Save drafts to file
    4. Update CRM status to "Drafted"
    5. Return formatted Discord messages
    """
    print(f"[QUILL] Starting daily draft run at {datetime.now(BD_TZ).strftime('%Y-%m-%d %H:%M')} BD")

    crm = get_crm()
    new_leads = crm.get_new_leads()

    if not new_leads:
        print("[QUILL] No new leads found. Nothing to draft.")
        return []

    print(f"[QUILL] Found {len(new_leads)} new leads. Drafting...")

    results = []
    drafted_count = 0
    failed_count = 0

    for lead in new_leads:
        email = lead.get("Owner Email", "").strip()
        if not email:
            print(f"  SKIP: {lead.get('Company Name', '?')} — no email")
            failed_count += 1
            continue

        try:
            draft = draft_email(lead)

            if not draft["is_valid"]:
                print(f"  ⚠ VALIDATION FAIL: {lead.get('Company Name', '?')} — {draft['violations']}")
                # Still save it but flag it
                draft["needs_review"] = True

            save_draft(draft)

            # Update CRM status
            crm.update_status(lead.get("Company Name", ""), "Drafted")

            results.append({
                "company": draft["company"],
                "email": draft["to"],
                "subject": draft["subject"],
                "word_count": draft["word_count"],
                "is_valid": draft["is_valid"],
                "violations": draft["violations"],
                "discord_message": format_discord_draft(draft),
            })

            drafted_count += 1
            status = "✅" if draft["is_valid"] else "⚠️ NEEDS REVIEW"
            print(f"  {status}: {draft['company']} → {draft['to']} ({draft['word_count']} words)")

        except Exception as e:
            print(f"  ✗ ERROR drafting for {lead.get('Company Name', '?')}: {e}")
            failed_count += 1

    print(f"\n[QUILL] Draft run complete: {drafted_count} drafted, {failed_count} failed, {len(results)} ready")

    # Write flag file
    with open(DRAFTED_FLAG, 'w') as f:
        f.write(datetime.now(BD_TZ).strftime('%Y-%m-%d %H:%M'))

    return results


def format_daily_summary(drafts_results: list) -> str:
    """Format a daily summary message for Discord."""
    if not drafts_results:
        return "📧 QUILL: No new leads today. Nothing to draft."

    valid = [d for d in drafts_results if d["is_valid"]]
    needs_review = [d for d in drafts_results if not d["is_valid"]]

    lines = [
        f"📧 **QUILL — Daily Draft Complete**",
        f"Date: {datetime.now(BD_TZ).strftime('%Y-%m-%d %H:%M')} BD",
        f"",
        f"✅ Drafted: {len(drafts_results)} emails",
        f"  • {len(valid)} passed validation",
        f"  • {len(needs_review)} need review",
        f"",
        f"**Drafts ready for review:**",
    ]

    for i, d in enumerate(drafts_results[:20], 1):
        status = "✅" if d["is_valid"] else "⚠️"
        lines.append(f"  {i}. {status} {d['company']} → {d['email']} | \"{d['subject']}\" ({d['word_count']}w)")

    if len(drafts_results) > 20:
        lines.append(f"  ... and {len(drafts_results) - 20} more")

    lines.extend([
        f"",
        f"Reply `!send all` to send all emails (3-min gap between each).",
        f"Reply `!send 1,3,5` to send specific ones.",
    ])

    return "\n".join(lines)


# ── CLI ENTRY POINTS ──────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "draft":
            # Run daily drafting
            results = run_daily_drafting()
            if results:
                print("\n" + format_daily_summary(results))
                # Also print each full draft
                for r in results:
                    print("\n" + r["discord_message"])
            else:
                print("No new leads to draft.")

        elif cmd == "send":
            # Send all pending emails
            indices = None
            if len(sys.argv) > 2 and sys.argv[2] != "all":
                indices = [int(x)-1 for x in sys.argv[2].split(",")]
                drafts = load_drafts()
                to_send = [(i, drafts[i]) for i in indices if i < len(drafts)]
                sent_count = 0
                failed_count = 0
                for idx, (orig_idx, draft) in enumerate(to_send):
                    if idx > 0:
                        time.sleep(BETWEEN_EMAIL_DELAY)
                    if send_email(draft):
                        sent_count += 1
                        try:
                            crm = get_crm()
                            crm.update_status(draft.get("company", ""), STATUS_EMAIL_SENT)
                        except:
                            pass
                    else:
                        failed_count += 1
                print(f"Sent: {sent_count}, Failed: {failed_count}")
            else:
                send_all_pending()

        elif cmd == "summary":
            drafts = load_drafts()
            sent = load_sent()
            total = len(drafts)
            already_sent = sum(1 for d in drafts if d.get("to", "") in sent)
            pending = total - already_sent
            print(f"📧 QUILL Status: {total} total | {already_sent} sent | {pending} pending")
            if pending > 0:
                print("\nPending emails:")
                for i, d in enumerate(drafts):
                    if d.get("to", "") not in sent:
                        print(f"  {i+1}. {d.get('company', '?')} → {d.get('to', '?')} | {d.get('subject', '?')}")

        elif cmd == "test":
            # Test with sample lead
            test_lead = {
                "Company Name": "North Gym",
                "Website (if have)": "https://northgym.net",
                "Owner Name": "",
                "Owner Email": "northgym@seznam.cz",
                "Pain Point": "Backdated UI — inline styles, no modern CSS framework, No analytics, No live chat",
            }
            draft = draft_email(test_lead)
            print(format_discord_draft(draft))
            print(f"\nValidation: {'PASS' if draft['is_valid'] else 'FAIL'}")
            if draft["violations"]:
                for v in draft["violations"]:
                    print(f"  • {v}")

        else:
            print("Usage: python3 quill_v8.py [draft|send [all|1,3,5]|summary|test]")
    else:
        # Default: run daily drafting
        results = run_daily_drafting()
        if results:
            print(format_daily_summary(results))
