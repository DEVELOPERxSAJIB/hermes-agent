#!/usr/bin/env python3
"""
NanoSoft QUILL v9 — Cold Email Generator
Generates personalized cold emails for Qualified leads.
Reads from CRM, uses Ollama LLM for personalization.
Follows strict email rules from Chairman.
"""
import json, os, sys, time, smtplib, ssl, re, urllib.request
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
DRAFTS_FILE = os.path.join(NANOSOFT_DIR, "email_drafts.jsonl")
SENT_LOG = os.path.join(NANOSOFT_DIR, "emails_sent.jsonl")
LOG_FILE = os.path.join(NANOSOFT_DIR, "quill_v9.log")

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = "nanosoftagency007@gmail.com"
SMTP_PASS = os.environ.get("SMTP_PASS", "wnvp mpne dyvu dheq")
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:7b"

sys.path.insert(0, NANOSOFT_DIR)

# ── EMAIL RULES (from Chairman) ──────────────────────────
MAX_WORDS = 125
MAX_SUBJECT = 33
MAX_LINKS = 1

BANNED_PHRASES = [
    "i hope this email finds you well", "i came across your website",
    "i am passionate about", "we are a dedicated team", "i would love to connect",
    "please feel free to reach out", "looking forward to hearing from you",
    "best regards", "sincerely", "to whom it may concern",
    "i noticed you might benefit from", "no obligation", "risk free",
    "act now", "click here", "limited time", "special offer",
]

# ── PAIN POINT → CONSEQUENCE ──────────────────────────────
PAIN_CONSEQUENCE = {
    "not mobile responsive": "When more than half your visitors browse on phones and see a broken layout, they leave before they ever read about your services",
    "not mobile": "When more than half your visitors browse on phones and see a broken layout, they leave before they ever read about your services",
    "no ssl": "Chrome shows 'Not Secure' to every visitor on your site",
    "outdated ui": "People judge a business by its website — if yours looks old, they assume the business is too",
    "backdated ui": "Visitors expect modern, fast websites — heavy inline styles make your site look outdated and slow",
    "no clear call-to-action": "If a visitor does not know what to do next, they do nothing — and eventually leaves",
    "no cta": "If a visitor does not know what to do next, they do nothing — and eventually leaves",
    "no analytics": "Without analytics, you have no idea how many people visit or why they leave",
    "no live chat": "When someone has a question at 9pm and cannot get an answer, they find someone who responds faster",
    "thin content": "Google needs content to rank your site — thin content means you are invisible in search",
    "no blog": "No blog means no organic traffic from Google — you are paying for every visitor or getting none",
    "no blog or news section": "No blog means no organic traffic from Google — you are paying for every visitor or getting none",
    "no testimonials or reviews": "Most people read reviews before choosing — without testimonials on your site, they go to a competitor who has them",
    "no contact form": "If someone cannot reach you in under 5 seconds, they are gone",
    "no privacy policy page": "Missing privacy policy is a trust gap — and Google uses it as a ranking signal",
    "no privacy policy": "Missing privacy policy is a trust gap — and Google uses it as a ranking signal",
}

IMPACT_SHORT = {
    "not mobile responsive": "losing mobile visitors",
    "not mobile": "losing mobile visitors",
    "no ssl": "not secure",
    "outdated ui": "looking outdated",
    "backdated ui": "looking outdated",
    "no clear call-to-action": "no clear next step",
    "no cta": "no clear next step",
    "no analytics": "no visitor data",
    "no live chat": "losing after-hours leads",
    "thin content": "invisible on Google",
    "no blog": "no Google traffic",
    "no blog or news section": "no Google traffic",
    "no testimonials or reviews": "no social proof",
    "no contact form": "hard to reach you",
    "no privacy policy page": "trust gap",
    "no privacy policy": "trust gap",
}


def log(msg):
    ts = datetime.now(BD_TZ).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, 'a') as f:
            f.write(line + "\n")
    except:
        pass


def fetch_url(url, timeout=10):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return r.status, r.read().decode('utf-8', errors='ignore')
    except:
        return 0, ''


def get_website_info(website):
    """Fetch website title, description, text sample."""
    status, html = fetch_url(website)
    if not html:
        return {'title': '', 'desc': '', 'text': '', 'mobile': False, 'ssl': website.startswith('https')}
    
    title_m = re.search(r'<title[^>]*>(.*?)</title>', html, re.I | re.S)
    title = ''
    if title_m:
        title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip()
        title = re.sub(r'\s*[|\-–—·•]\s*.+$', '', title).strip()[:80]
    
    desc_m = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']+)["\']', html, re.I)
    desc = desc_m.group(1).strip()[:200] if desc_m else ''
    
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text).strip()[:500]
    mobile = bool(re.search(r'<meta[^>]*viewport', html.lower()))
    
    return {'title': title, 'desc': desc, 'text': text, 'mobile': mobile, 'ssl': website.startswith('https')}


def ollama_gen(prompt, max_tokens=300, timeout=90):
    """Generate text via Ollama."""
    import json as _json
    payload = _json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.7, "num_predict": max_tokens}
    }).encode()
    try:
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = _json.loads(r.read())
            return data.get("response", "").strip()
    except Exception as e:
        log(f"[OLLAMA] Error: {e}")
        return ""


def draft_email(lead):
    """Draft personalized cold email following Chairman's strict rules.
    Uses enhanced rule-based approach (LLM too slow/unreliable for production).
    """
    company = lead.get("Company Name", "").strip()
    website = lead.get("Website (if have)", "").strip()
    pain_points = lead.get("Pain Point", "").strip()
    email = lead.get("Owner Email", "").strip()
    
    if not email or not website:
        return None
    
    domain = re.sub(r'^https?://(www\.)?', '', website).split('/')[0]
    
    # Parse pain points
    pains_list = [p.strip() for p in pain_points.split(',') if p.strip()] if pain_points else []
    pains_lower = [p.lower() for p in pains_list]
    
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
            ("no cta", "no clear next step"),
            ("outdated", "looking outdated"),
            ("backdated", "built years ago"),
        ]:
            if key in pain:
                impact = short
                break
        if impact != "needs attention":
            break
    
    subject = f"{domain} — {impact}"
    if len(subject) > MAX_SUBJECT:
        short_d = domain.replace("www.", "").split(".")[0]
        subject = f"{short_d} — {impact}"
    if len(subject) > MAX_SUBJECT:
        subject = subject[:MAX_SUBJECT].rstrip()
    
    # ── BODY: 4 paragraphs ──
    
    # S1: Specific observation about THEM (pick the most impactful pain)
    s1_templates = {
        "not mobile": f"{domain} is not mobile responsive — visitors browsing on phones see a broken layout and leave immediately.",
        "no ssl": f"{domain} has no SSL certificate. Chrome flags it as 'Not Secure' to every single visitor.",
        "no live chat": f"{domain} has no live chat. When someone has a question outside business hours, they go to a competitor who's available.",
        "no analytics": f"{domain} has no analytics tracking. You're running blind with zero data about who visits, where they come from, or why they leave.",
        "no blog": f"{domain} has no blog. That means zero organic traffic from Google — you're relying entirely on paid ads or word of mouth.",
        "thin content": f"{domain} has very thin content. Google can't rank what it can't read.",
        "no testimonial": f"{domain} has no customer testimonials. 72% of buyers read reviews before choosing — without them, they go elsewhere.",
        "no contact": f"{domain} has no clear way to contact you. If it takes more than 5 seconds, the potential customer is gone.",
        "no privacy": f"{domain} has no privacy policy page. That's a trust gap with visitors and a ranking signal Google penalizes.",
        "slow": f"{domain} takes too long to load. Every extra second of load time increases your bounce rate.",
        "outdated": f"{domain} looks like it was built 15+ years ago — and visitors immediately judge the business by the website.",
        "backdated": f"{domain} is built with outdated code patterns — inline styles, table layouts, no CSS framework.",
        "no cta": f"{domain} has no clear call-to-action. Visitors don't know what to do next, so they do nothing.",
    }
    
    s1 = f"{domain} has issues that are likely costing you customers every day."
    for pain in pains_lower:
        for key, template in s1_templates.items():
            if key in pain:
                s1 = template
                break
        if not s1.startswith(domain + " has issues"):
            break
    
    # S2: Consequence (what this means for their business)
    consequence_map = {
        "not mobile": "More than 60% of web traffic is mobile now — broken mobile means you're losing the majority of potential customers before they ever read about your services.",
        "no ssl": "Beyond the warning message, Google uses HTTPS as a ranking signal. No SSL means lower search visibility.",
        "no live chat": "73% of customers say live chat is the most satisfying way to communicate — without it, you're losing the majority who want instant answers.",
        "no analytics": "You could be spending money on marketing that doesn't work and never know it. Analytics tells you what's actually bringing customers in.",
        "no blog": "Businesses that blog get 55% more website visitors. Your competitors who blog are taking your potential customers from Google.",
        "thin content": "Google needs substance to rank your site. Thin pages signal low quality and get buried in search results.",
        "no testimonial": "Social proof is the #1 factor in local service business decisions. Without reviews visible on your site, you lose to competitors who have them.",
        "no contact": "Friction in communication kills conversions. A simple contact form can double your inquiry rate.",
        "no privacy": "Privacy policies aren't just legal compliance — they're a trust signal that increases visitor confidence and conversions.",
        "slow": "A 1-second delay in page load can reduce conversions by 7%. Over a month, that's hundreds of lost visitors.",
        "outdated": "People judge a business by its website within 3 seconds. An outdated site means visitors assume the business is outdated too.",
        "backdated": "Outdated code means slower load times, security vulnerabilities, and lower Google rankings.",
        "no cta": "Without a clear next step, visitors browse and leave. A strong CTA can increase conversions by 42%.",
    }
    
    s2 = "These problems compound over time — every month without a fix means more lost revenue."
    for pain in pains_lower:
        for key, cons in consequence_map.items():
            if key in pain:
                s2 = cons
                break
        if not "These problems compound" in s2:
            break
    
    # S3: Proof / credibility
    s3 = "Fixed similar issues for other local service businesses — here is the portfolio: nanosoft.agency/portfolio"
    
    # S4: CTA (yes/no question, low friction)
    s4_options = [
        f"Is {domain} currently bringing in any new inquiries at all?",
        f"Would it be worth 10 minutes to go through what I'd fix first?",
        f"Can I send you a 2-minute screen recording showing the biggest issue on {domain}?",
        f"Is improving {domain} something you'd consider this month?",
    ]
    # Match CTA to the primary pain
    s4 = s4_options[0]
    for pain in pains_lower:
        if "slow" in pain or "load" in pain:
            s4 = s4_options[1]
            break
        if "mobile" in pain or "outdated" in pain:
            s4 = s4_options[2]
            break
    
    body = f"{s1}\n\n{s2}\n\n{s3}\n\n{s4}\n\nSaJib"
    
    word_count = len(body.split())
    
    # Trim if too long
    while word_count > MAX_WORDS and len(s4_options) > 1:
        body = f"{s1}\n\n{s2}\n\n{s3}\n\nSaJib"
        word_count = len(body.split())
        break
    
    # Follow-ups
    fu1 = "Did you get a chance to look?\n\nHappy to send a 2-minute screen recording showing exactly what I would fix first."
    fu2 = "No worries if the timing is off — just let me know and I will close your file."
    if len(pains_list) > 1:
        pain2 = pains_list[1]
        if len(pain2) > 40:
            pain2 = pain2[:40] + "..."
        fu3 = f"Noticed {pain2} on {domain} since my last email.\n\nThis one alone could make a real difference.\n\nWorth 10 minutes this week?"
    else:
        fu3 = f"Noticed another issue on {domain} since my last email.\n\nWorth 10 minutes this week?"
    
    # Validate
    violations = []
    if word_count > MAX_WORDS:
        violations.append("too_long:{}w".format(word_count))
    if len(subject) > MAX_SUBJECT:
        violations.append("subject:{}".format(len(subject)))
    body_lower = body.lower()
    for phrase in BANNED_PHRASES:
        if phrase in body_lower:
            violations.append("banned:{}".format(phrase))
    links = len(re.findall(r'https?://', body))
    if links > MAX_LINKS:
        violations.append("links:{}".format(links))
    first_line = body.strip().split("\n")[0].lower()
    if first_line.startswith(("i ", "we ")):
        violations.append("starts_with_I")
    
    return {
        "to": email,
        "subject": subject,
        "body": body,
        "company": company,
        "domain": domain,
        "pain_points_used": pains_list[0] if pains_list else "",
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


# ── FILE OPS ──────────────────────────────────────────────
def load_drafts():
    drafts = []
    try:
        with open(DRAFTS_FILE) as f:
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
        with open(SENT_LOG) as f:
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
            "sent_at": datetime.now(BD_TZ).isoformat(),
        }) + "\n")

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
        log(f"  ✓ SENT: {to_email} | {draft.get('company', '')[:40]}")
        return True
    except Exception as e:
        log(f"  ✗ FAIL: {to_email} | {str(e)[:60]}")
        return False


def send_all_pending(delay=180):
    """Send all pending drafts with configurable delay (default 3 min)."""
    drafts = load_drafts()
    sent = load_sent()
    unsent = [d for d in drafts if d.get("to", "") not in sent]
    if not unsent:
        log("[QUILL] No pending emails.")
        return 0, 0
    
    log(f"[QUILL] Sending {len(unsent)} emails ({delay}s gap)...")
    ok = 0
    fail = 0
    for i, draft in enumerate(unsent):
        if i > 0:
            log(f"  Waiting {delay}s...")
            time.sleep(delay)
        log(f"  [{i+1}/{len(unsent)}] {draft.get('to','')}...")
        if send_email(draft):
            ok += 1
        else:
            fail += 1
    log(f"[QUILL] Done: {ok} sent, {fail} failed")
    return ok, fail


# ── CLI ────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "send":
        delay = int(sys.argv[2]) if len(sys.argv) > 2 else 180
        send_all_pending(delay=delay)
    elif len(sys.argv) > 1 and sys.argv[1] == "draft":
        # Draft specific leads
        from crm import get_crm
        crm = get_crm()
        status_filter = sys.argv[2] if len(sys.argv) > 2 else "Qualified"
        leads = crm.get_leads_by_status(status_filter)
        log(f"[QUILL] Drafting {len(leads)} {status_filter} leads...")
        drafts = []
        for i, lead in enumerate(leads):
            log(f"  [{i+1}/{len(leads)}] {lead.get('Company Name','?')[:40]}")
            d = draft_email(lead)
            if d:
                drafts.append(d)
                crm.update_status(lead.get("Company Name",""), "Drafted")
                log(f"    {'✅' if d['is_valid'] else '⚠️'} {d['word_count']}w | {d['subject']}")
        save_drafts(drafts)
        log(f"[QUILL] Done: {len(drafts)} drafted")
    else:
        print("Usage: python3 quill_v9.py draft [status] | python3 quill_v9.py send [delay_seconds]")
