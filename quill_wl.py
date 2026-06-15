#!/usr/bin/python3
"""
NanoSoft QUILL-WL v2 — White Label Agency Outreach
4-email sequence: Hook → Value Add → Reframe → Breakup

RULES (from Chairman's original templates):
1. NO links in body
2. NO spam trigger words
3. Under 100 words
4. Subject: short, no caps, no special chars, no hyphens
5. First sentence: about THEM, not "I" or "We"
6. Conversational tone — 4th grade English, human voice
7. No jargon: "white-labeled" → "under your brand", "silent extension" → "quiet partner"
8. Yes/no CTA only
9. "SaJib" signature only (no company name in sig)
10. List-Unsubscribe headers
11. 3-min gap between sends
12. Unique sentence structure per email — no template feel

T1 (Day 1): Hook — problem question about their overflow/capacity
T2 (Day 4-5): Value Add — social proof scenario, zero pressure
T3 (Day 9-10): Reframe — disarm with genuine question, no pitch
T4 (Day 14-16): Breakup — low-stakes closure, one-line pitch
"""
import json, os, re, sys, time
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
LOG_FILE = os.path.join(NANOSOFT_DIR, "quill_wl.log")
SENT_LOG = os.path.join(NANOSOFT_DIR, "emails_sent_wl.jsonl")

sys.path.insert(0, NANOSOFT_DIR)

# ── RULES ───────────────────────────────────────────────────
MAX_WORDS = 110
MAX_SUBJECT = 35

BANNED_WORDS = [
    "free", "guarantee", "guaranteed", "act now", "limited time", "click here",
    "buy now", "order now", "call now", "subscribe", "unsubscribe", "winner",
    "congratulations", "risk-free", "no obligation", "this is not spam",
    "earn money", "make money", "extra income", "work from home", "double your",
    "earn extra", "financial freedom", "free consultation", "free access",
    "free gift", "free info", "free investment", "free membership",
    "free offer", "free preview", "free quote", "free trial",
    "amazing", "fantastic", "incredible", "revolutionary", "breakthrough",
    "exclusive deal", "special promotion", "best price", "cheap",
    "discount", "save big", "act immediately", "urgent", "important information",
    "you have been selected", "no catch", "no experience", "no purchase necessary",
    "not junk", "not spam", "please read", "take action", "while supplies last",
    "will not believe", "your chance", "100% satisfied", "100% free",
    "million dollars", "cash bonus", "consolidate credit", "consolidate debt",
    "eliminate bad credit", "get paid", "lower interest rate", "lowest price",
    "mortgage rates", "pre-approved", "credit card offers", "in accordance with laws",
    "direct marketing", "email marketing", "marketing solutions",
    "increase sales", "increase traffic", "web traffic", "more website visits",
    "the best rates", "#1", "5-star", "top-rated", "best in class",
    "visit our website", "click below", "click to", "sign up", "sign up free",
    "register free", "join millions", "be your own boss", "no cost",
]

BANNED_PHRASES = [
    "i hope this email finds you well", "i came across your website",
    "i am passionate about", "we are a dedicated team", "i would love to connect",
    "please feel free to reach out", "looking forward to hearing from you",
    "best regards", "sincerely", "to whom it may concern",
    "i noticed you might benefit from", "no obligation", "risk free",
    "act now", "click here", "limited time", "special offer",
    "as a leading", "we specialize in", "our team of experts",
    "i wanted to reach out", "i am writing to", "allow me to",
    "i would like to", "we believe that", "at the end of the day",
    "going forward", "moving forward", "in today's world",
    "in today's market", "cutting-edge", "state-of-the-art",
    "leverage", "synergy", "paradigm", "disruptive", "innovative solution",
    "game-changer", "value-add", "circle back", "touch base",
    "i hope you are doing well", "great speaking with you",
    "per my last email", "just checking in", "following up on",
    "genuinely curious",
]

SIGNATURE = "SaJib"


def check_spam_score(text):
    import re
    text_lower = text.lower()
    violations = []
    for word in BANNED_WORDS:
        # Use word boundary to avoid false positives like "Freelancer" matching "free"
        pattern = r'\b' + re.escape(word) + r'\b'
        if re.search(pattern, text_lower):
            violations.append(f"spam_word:{word}")
    for phrase in BANNED_PHRASES:
        if phrase in text_lower:
            violations.append(f"banned_phrase:{phrase}")
    # Check for hyphens AND em dashes AND en dashes
    if ' — ' in text or ' – ' in text:
        violations.append("contains_dash_separator")
    words = text.split()
    skip_caps = {'AI/ML', 'UI/UX', 'SaaS', 'MVP', 'QA/Testing', 'DevOps', 'API', 'APIs',
                 'CEO', 'CTO', 'COO', 'CFO', 'VP', 'HR', 'IT', 'USA', 'UK', 'EU', 'UAE',
                 'AWS', 'GCP', 'IaaS', 'PaaS', 'B2B', 'B2C', 'SEO', 'IoT'}
    all_caps_words = [w for w in words if w.isupper() and len(w) > 1
                      and w not in skip_caps and not any(c.isdigit() for c in w)]
    if len(all_caps_words) > 4:
        violations.append(f"excessive_caps:{len(all_caps_words)}")
    if text.count('!') > 1:
        violations.append("excessive_exclamation")
    if text.count('?') > 2:
        violations.append("excessive_questions")
    if '$' in text:
        violations.append("dollar_sign")
    if re.search(r'\d+%', text):
        violations.append("percentage_sign")
    for shortener in ['bit.ly', 'tinyurl', 'goo.gl', 't.co', 'ow.ly']:
        pattern = r'\b' + re.escape(shortener) + r'\b'
        if re.search(pattern, text_lower):
            violations.append(f"url_shortener:{shortener}")
    links = len(re.findall(r'https?://', text))
    if links > 0:
        violations.append(f"contains_links:{links}")
    first_word = text.strip().split()[0].lower().rstrip('.,') if text.strip() else ""
    if first_word in ('i', 'we', "i'm", "we're", "i've", "we've"):
        violations.append(f"starts_with_I/we:{first_word}")
    return violations


def parse_services(services_str):
    if not services_str:
        return []
    return [s.strip() for s in services_str.split(',') if s.strip()]


def get_primary_service(services):
    priority = ['mobile development', 'web development', 'AI/ML', 'UI/UX design',
                'cloud/DevOps', 'SaaS', 'eCommerce', 'QA/Testing', 'custom software',
                'staff augmentation', 'consulting']
    for p in priority:
        for s in services:
            if p.lower() in s.lower():
                return s
    return services[0] if services else 'software development'


def get_wl_signals_list(signals_str):
    if not signals_str:
        return []
    return [s.strip() for s in signals_str.split(',') if s.strip()]


def get_first_name(owner_name):
    if not owner_name:
        return ""
    name = owner_name.strip()
    if name.startswith('http') or 'linkedin.com' in name or '.com/' in name:
        return ""
    if ',' in name:
        parts = name.split(',')
        return parts[-1].strip().split()[0]
    first = name.split()[0]
    if '@' in first or '.' in first:
        return ""
    return first


# ── SUBJECT LINES ───────────────────────────────────────────
def subject_hook(company, services):
    """Boring subject lines that look like internal emails."""
    company_short = company.split()[0]
    subjects = [
        f"{company_short} overflow",
        f"{company_short} delivery",
        f"{company_short} capacity",
        f"{company_short} question",
        f"{company_short} team",
    ]
    valid = [s for s in subjects if len(s) <= MAX_SUBJECT]
    idx = len(company) % len(valid)
    return valid[idx]


def subject_followup(company):
    return f"re: {company_short(company)}"


def subject_reframe(company):
    return f"{company_short(company)} process"


def subject_breakup(company):
    return f"{company_short(company)}"


def company_short(company):
    return company.split()[0]


# ── EMAIL TEMPLATES v8 — Hiring Signal Angle + Observation Angle ──
# Two tracks:
#   1. HIRING: Lead has "Hiring Signals" → "Noticed you're hiring. Agency vs in-house?"
#   2. STANDARD: No hiring signals → specific observation + curious question
# Chairman's exact hiring angle preserved word-for-word.

def _has_hiring_signal(lead):
    """Check if lead has active hiring signals."""
    hiring = str(lead.get("Hiring Signals", "")).strip()
    if hiring and len(hiring) > 3 and hiring not in ('0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10'):
        return True
    # Also check website text for hiring keywords
    website_text = lead.get("Website Text", "").lower()
    hiring_keywords = ["we are hiring", "join our team", "careers", "open positions",
                       "we're hiring", "job openings", "work with us"]
    return any(kw in website_text for kw in hiring_keywords)


def _get_hiring_ref(lead, first_word):
    """Build a specific hiring reference for the email."""
    hiring_signals = str(lead.get("Hiring Signals", "")).strip()
    if hiring_signals and len(hiring_signals) > 3:
        # Use the specific role they're hiring for
        role = hiring_signals.split(",")[0].strip()
        if len(role) > 60:
            role = role[:60]
        return f"Noticed you are hiring for {role}"
    return f"Saw {first_word} is hiring right now"


def make_email_t1(lead):
    """
    T1: The Hook (Day 1)
    Based on Chairman's template. Human tone. Concrete proof. Forces a reply.
    """
    company = lead.get("Company Name", "").strip()
    email = lead.get("Email", "").strip()
    services = parse_services(lead.get("Services", ""))
    wl_signals = lead.get("White Label Signals", "").strip()
    owner_name = lead.get("Owner Name", "").strip()
    pain_points = lead.get("Pain Points", "").strip()

    if not email or not company:
        return None

    first_name = get_first_name(owner_name)
    first_word = company.split()[0]
    greeting = f"Hey {first_name}" if first_name else f"Hey {first_word} team"

    primary = get_primary_service(services)
    if "/" in primary:
        primary = primary.split("/")[0].strip()

    import random
    random.seed(hash(company))

    # Build a specific example based on their services
    if "mobile" in primary.lower() or "react native" in primary.lower():
        example = "Just finished a food ordering app for an agency in Amsterdam, 4 weeks, fully handed off"
    elif "ai" in primary.lower() or "ml" in primary.lower():
        example = "Just finished a recommendation engine for an agency in Texas, 3 weeks, client renewed for phase 2"
    elif "web" in primary.lower() or "saas" in primary.lower():
        example = "Just finished a SaaS dashboard rebuild for an agency in London, 5 weeks, shipped under their brand"
    elif "cloud" in primary.lower() or "devops" in primary.lower():
        example = "Just finished a cloud migration for an agency in Canada, 6 weeks, zero downtime"
    elif "ecommerce" in primary.lower() or "shopify" in primary.lower():
        example = "Just finished a Shopify store for an agency in Australia, 3 weeks, client hit record sales"
    else:
        example = f"Just finished a {primary} project for an agency in Europe, 4 weeks, fully handed off"

    # Check if they have hiring signals for a more specific hook
    has_hiring = _has_hiring_signal(lead)

    if has_hiring:
        role = str(lead.get("Hiring Signals", "")).strip().split(",")[0].strip()
        if len(role) > 40:
            role = role[:40]
        hook = f"saw you are hiring for {role}"
        body = (
            f"{greeting},\n\n"
            f"{hook}.\n\n"
            f"We are a white-label web app and custom software development team.\n\n"
            f"Agencies send us overflow, we ship under their brand, client never knows.\n\n"
            f"{example}.\n\n"
            f"If you hit capacity or cannot hire fast enough, we are one Slack message away.\n\n"
            f"Worth a quick call this week?\n\n"
            f"SaJib Shikder\n"
            f"NanoSoft Agency"
        )
        return _finalize(email, f"{first_word} hiring", body, company, "T1-HIRING")

    # Standard angle — same template, different hook based on their business
    if wl_signals and ("white label" in wl_signals.lower() or "white-label" in wl_signals.lower()):
        hook = f"noticed {first_word} already works with partner agencies"
    elif wl_signals and ("staff augmentation" in wl_signals.lower() or "outsourcing" in wl_signals.lower()):
        hook = f"looks like {first_word} already outsources some development"
    elif wl_signals and "partner" in wl_signals.lower():
        hook = f"saw {first_word} works with a lot of agency partners"
    elif pain_points and "mobile" in pain_points.lower():
        hook = f"mobile projects are brutal to staff properly"
    elif pain_points and ("capacity" in pain_points.lower() or "scale" in pain_points.lower()):
        hook = f"when the project pipeline grows faster than the team, things get stressful"
    elif primary and "mobile" in primary.lower():
        hook = f"mobile dev is a different beast, react native, native, keeping both in sync"
    elif primary and ("ai" in primary.lower() or "ml" in primary):
        hook = f"AI work needs real specialists, hard to find, harder to hire full time"
    elif primary:
        hook = f"keep hearing the same thing from {primary} agencies"
    else:
        hook = f"quick one"

    body = (
        f"{greeting},\n\n"
        f"{hook}.\n\n"
        f"We are a white-label web app and custom software development team.\n\n"
        f"Agencies send us overflow, we ship under their brand, client never knows.\n\n"
        f"{example}.\n\n"
        f"If you ever hit capacity or cannot hire fast enough, we are one Slack message away.\n\n"
        f"Worth keeping in touch?\n\n"
        f"SaJib Shikder\n"
        f"NanoSoft Agency"
    )

    return _finalize(email, f"{first_word} overflow", body, company, "T1")


def make_email_t2(lead):
    """
    T2 — Value Add (Day 4-5)
    Hiring: Agency vs hiring cost scenario
    Standard: Micro-story about agency partnership
    """
    company = lead.get("Company Name", "").strip()
    email = lead.get("Email", "").strip()
    services = parse_services(lead.get("Services", ""))
    owner_name = lead.get("Owner Name", "").strip()

    if not email or not company:
        return None

    first_name = get_first_name(owner_name)
    first_word = company.split()[0]
    greeting = f"Hey {first_name}" if first_name else f"Hey {first_word} team"

    primary = get_primary_service(services)
    kw = primary.split('/')[0].strip()

    import random
    random.seed(hash(company) + 1)

    # ── HIRING ANGLE ──
    if _has_hiring_signal(lead):
        scenarios = [
            f"A dev agency in Texas was hiring for 3 React roles. Took 4 months, 2 bad hires, "
            f"forty thousand plus wasted. They switched to an agency model. Got 5 experts in 2 weeks, "
            f"project shipped on time, sixty percent cheaper than payroll.",

            f"A dev shop in Europe needed 2 senior devs for a 6-month project. Hiring would take 3 months "
            f"and cost twenty-five thousand plus in recruiting alone. They used an agency team instead. "
            f"Started in 1 week, delivered in 5 months, no payroll overhead.",
        ]
        scenario = random.choice(scenarios)
        body = (
            f"{greeting},\n\n"
            f"{scenario}\n\n"
            f"If {first_word} is hiring for {kw} roles, this might be worth thinking about.\n\n"
            f"SaJib"
        )
        subject = f"re: {first_word} hiring"
        return _finalize(email, subject, body, company, "T2-HIRING")

    # ── STANDARD ANGLE ──
    # Same agency-vs-in-house framing but as a story/example
    if 'mobile' in primary.lower():
        stories = [
            f"A mobile agency in the US was about to hire 3React Native devs. Took one look at the recruiting cost, timeline and risk, they used an agency instead. Got 3 matching devs in one week, project shipped, zero payroll headache.",
            f"An agency had a 4-month mobile deadline and losing their leadReact developer. Posting a job ad, running interviews, would take months, they brought in an agency team. Shipped on time, client gave them a repeat order.",
        ]
    elif 'AI' in kw or 'ML' in kw:
        stories = [
            f"An agency won an AI feature contract. Hiring ML engineers would take 3 months minimum, they partnered with an agency that had the specialists ready. Delivered in 6 weeks, client never knew the difference.",
            f"A dev shop needed a recommendation engine built. No way to hire that talent fast enough, they used an agency team. Built, shipped, client renewed for phase two.",
        ]
    elif 'web' in primary.lower() or 'SaaS' in primary.lower():
        stories = [
            f"A SaaS agency landed a big rebuild but only had3 developers. Hiring more would blow the budget and timeline, they brought in an agency to handle the backend. Shipped on time, kept the margin.",
            f"An agency had a legacy codebase rewrite. Could not justify a full-time hire for a6-month project. Used an agency team instead, got clean docs, their client was happy.",
        ]
    elif 'cloud' in kw or 'devops' in kw:
        stories = [
            f"An agency won a cloud migration project but had no DevOps people. Hiring would take months, they used an agency with the right skills. Migration done in 8 weeks, client signed a retainer.",
            f"A dev shop needed AWS specialists for a 4-month contract. No point hiring full-time, they partnered with an agency. Got 2 cloud engineers Monday morning, project delivered on schedule.",
        ]
    else:
        stories = [
            f"An agency was about to post job ads for {kw} roles. Recruiting cost alone was twenty thousand plus, timeline was 3 months minimum. They used an agency instead, got experts in one week.",
            f"A dev shop had a client deadline they could not hit with their current team. Hiring was too slow, they brought in an agency. Delivered on time, agency kept the relationship.",
        ]

    story = random.choice(stories)

    body = (
        f"{greeting},\n\n"
        f"{story}\n\n"
        f"If {first_word} ever faces a gap between team size and project load, this is worth thinking about.\n\n"
        f"SaJib"
    )

    subject = f"re: {first_word} question"
    return _finalize(email, subject, body, company, "T2")


def make_email_t3(lead):
    """
    T3 — Reframe (Day 9-10)
    Hiring: Ask about hiring timeline
    Standard: Learn mode question about their world
    """
    company = lead.get("Company Name", "").strip()
    email = lead.get("Email", "").strip()
    services = parse_services(lead.get("Services", ""))
    owner_name = lead.get("Owner Name", "").strip()

    if not email or not company:
        return None

    first_name = get_first_name(owner_name)
    first_word = company.split()[0]
    greeting = f"Hey {first_name}" if first_name else f"Hey {first_word} team"

    primary = get_primary_service(services)
    kw = primary.split('/')[0].strip()

    import random
    random.seed(hash(company) + 2)

    # ── HIRING ANGLE ──
    if _has_hiring_signal(lead):
        questions = [
            f"Quick question. What is {first_word} hiring timeline for the {kw} roles? "
            f"If you need people faster than recruiting allows, we can help.",

            f"Curious. How many roles is {first_word} looking to fill this quarter? "
            f"If the timeline is tight, an agency team might be worth considering.",
        ]
        question = random.choice(questions)
        body = (
            f"{greeting},\n\n"
            f"{question}\n\n"
            f"No pitch. Just trying to understand if there is a fit.\n\n"
            f"SaJib"
        )
        subject = f"{first_word} timeline"
        return _finalize(email, subject, body, company, "T3-HIRING")

    # ── STANDARD ANGLE ──
    # Ask about their growth/hiring plans — keeps the agency-vs-in-house thread
    questions = [
        f"Quick question. When {first_word} lands a {kw} project that is too big for the current team, what is the usual move, hire or bring in a partner",
        f"Curious. If {first_word} had to scale the team up by 3 or 4 devs next month, would you hire or consider an agency",
        f"When {first_word} looks at the next quarter, is hiring new devs part of the plan or do you prefer flexible capacity",
    ]
    question = random.choice(questions)

    body = (
        f"{greeting},\n\n"
        f"{question}?\n\n"
        f"No pitch. Just trying to understand how agencies like yours handle growth.\n\n"
        f"SaJib"
    )

    subject = f"{first_word} growth"
    return _finalize(email, subject, body, company, "T3")


def make_email_t4(lead):
    """
    T4 — Breakup (Day 14-16)
    Clean exit for both tracks.
    """
    company = lead.get("Company Name", "").strip()
    email = lead.get("Email", "").strip()
    services = parse_services(lead.get("Services", ""))
    owner_name = lead.get("Owner Name", "").strip()

    if not email or not company:
        return None

    first_name = get_first_name(owner_name)
    first_word = company.split()[0]
    greeting = f"Hey {first_name}" if first_name else f"Hey {first_word} team"

    primary = get_primary_service(services)
    kw = primary.split('/')[0].strip()

    body = (
        f"{greeting},\n\n"
        f"Going to leave you alone now. Respect your inbox.\n\n"
        f"If you ever need {kw} backup under your brand, we are here. That is all.\n\n"
        f"Good luck with {first_word}.\n\n"
        f"SaJib"
    )

    subject = subject_breakup(company)
    return _finalize(email, subject, body, company, "T4")


def _finalize(to, subject, body, company, template_type):
    violations = check_spam_score(body)
    word_count = len(body.split())

    if word_count > MAX_WORDS:
        lines = body.split('\n\n')
        if len(lines) >= 4:
            lines = [lines[0], ' '.join(lines[1:3]), lines[-2], lines[-1]]
            body = '\n\n'.join(lines)
            word_count = len(body.split())
            violations.append("trimmed_for_length")

    is_valid = len([v for v in violations if not v.startswith("trimmed")]) == 0

    bad_patterns = [
        r'user@domain', r'example@', r'@whois\.', r'@sentry\.', r'@bytedance\.',
        r'vue@3\.', r'@scorebig\.', r'@afternic\.', r'john@doe\.', r'feedback@',
        r'your@email\.', r'email@company\.', r'name@email\.', r'mail@domain\.',
        r'john\.doe@', r'jane\.doe@', r'test@example\.', r'info@domain\.',
        r'@sentry\.', r'@bytedance\.', r'@afternic\.', r'@scorebig\.',
        r'intl-tel-input@', r'default-utils\.js@', r'gsap@', r'splide@',
        r'@2x-', r'@3x\.', r'flags@', r'impact-website@',
    ]
    for pat in bad_patterns:
        if re.search(pat, to, re.IGNORECASE):
            return None

    return {
        "to": to,
        "subject": subject,
        "body": body,
        "company": company,
        "word_count": word_count,
        "subject_length": len(subject),
        "is_valid": is_valid,
        "violations": violations,
        "template": template_type,
        "drafted_at": datetime.now(BD_TZ).isoformat(),
        "status": "drafted",
    }


# ── GMAIL TOKEN CHECK ───────────────────────────────────────
def check_gmail_token():
    """Check if Gmail token is valid before attempting any API calls."""
    token_file = os.path.join(NANOSOFT_DIR, "gmail_token.json")
    dead_flag = os.path.join(NANOSOFT_DIR, "GMAIL_TOKEN_DEAD")
    
    # If dead flag exists, token is known to be dead
    if os.path.exists(dead_flag):
        return False
    
    # Try to load and validate token
    try:
        with open(token_file) as f:
            token_data = json.load(f)
        
        if not token_data.get("refresh_token"):
            return False
            
        # Try to refresh the token
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        
        creds = Credentials(
            token=token_data.get("token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=token_data.get("client_id"),
            client_secret=token_data.get("client_secret"),
            scopes=token_data.get("scopes"),
        )
        
        if creds.expired:
            creds.refresh(Request())
            
        return True
    except Exception as e:
        error_str = str(e)
        if 'invalid_grant' in error_str:
            # Token is dead — write flag file
            try:
                with open(dead_flag, 'w') as f:
                    f.write(f"Token died at {datetime.now(BD_TZ).isoformat()}\nError: {error_str}")
            except:
                pass
        return False


# ── GMAIL DRAFT ─────────────────────────────────────────────
def create_gmail_draft(to_email, subject, body):
    try:
        import base64
        from email.mime.text import MIMEText
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        with open(os.path.join(NANOSOFT_DIR, "gmail_token.json")) as f:
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
            with open(os.path.join(NANOSOFT_DIR, "gmail_token.json"), "w") as f:
                json.dump(token_data, f)

        service = build("gmail", "v1", credentials=creds)

        msg = MIMEText(body)
        msg['to'] = to_email
        msg['from'] = "SaJib <nanosoftagency007@gmail.com>"
        msg['subject'] = subject
        msg['List-Unsubscribe'] = '<mailto:nanosoftagency007@gmail.com?subject=unsubscribe>'
        msg['List-Unsubscribe-Post'] = 'List-Unsubscribe=One-Click'

        raw = base64.urlsafe_b64encode(msg.as_string().encode()).decode()

        draft = service.users().drafts().create(
            userId='me',
            body={'message': {'raw': raw}}
        ).execute()

        return draft.get('id')
    except Exception as e:
        print(f"[DRAFT] Error for {to_email}: {e}")
        return None


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
    parser = argparse.ArgumentParser(description='NanoSoft QUILL-WL v2')
    parser.add_argument('action', choices=['preview', 'draft', 'send', 'test', 'validate'],
                        help='Action: preview, draft, send, test, validate')
    parser.add_argument('--template', '-t', choices=['T1', 'T2', 'T3', 'T4'], default='T1')
    parser.add_argument('--hiring-only', action='store_true', help='Only send to leads with hiring signals')
    parser.add_argument('--standard-only', action='store_true', help='Only send to leads without hiring signals')
    parser.add_argument('--limit', type=int, default=0, help='Limit emails (0=all)')
    args = parser.parse_args()

    # Use cached CRM to avoid Google Sheets 429 errors
    try:
        from crm_cache import get_crm
    except ImportError:
        from crm import get_crm
    crm = get_crm()
    wl_leads = crm.get_wl_all()

    qualified = [l for l in wl_leads if l.get("Status") == "Qualified"]

    # Filter by hiring signal if requested
    if args.hiring_only:
        qualified = [l for l in qualified if _has_hiring_signal(l)]
        log(f"[QUILL-WL v8] Hiring filter: {len(qualified)} leads with hiring signals")
    elif args.standard_only:
        qualified = [l for l in qualified if not _has_hiring_signal(l)]
        log(f"[QUILL-WL v8] Standard filter: {len(qualified)} leads without hiring signals")

    if args.limit > 0:
        qualified = qualified[:args.limit]

    log(f"[QUILL-WL v8] {len(qualified)} Qualified WL leads loaded")

    make_fn = {
        'T1': make_email_t1,
        'T2': make_email_t2,
        'T3': make_email_t3,
        'T4': make_email_t4,
    }[args.template]

    if args.action == 'test':
        if qualified:
            d = make_fn(qualified[0])
            if d:
                print(f"\n=== {d['company']} | {d['template']} ===")
                print(f"To: {d['to']}")
                print(f"Subject: {d['subject']} ({d['subject_length']} chars)")
                print(f"Words: {d['word_count']} | Valid: {d['is_valid']}")
                if d['violations']:
                    print(f"Violations: {d['violations']}")
                print(f"\n--- BODY ---\n{d['body']}")
            else:
                print("make_email returned None")
        else:
            print("No qualified leads.")

    elif args.action == 'validate':
        print(f"\n{'='*60}")
        print(f"VALIDATION: {args.template} on {len(qualified)} leads")
        print(f"{'='*60}")
        invalid_count = 0
        for lead in qualified:
            d = make_fn(lead)
            if not d:
                print(f"  SKIP: {lead.get('Company Name','?')} (bad email)")
                continue
            v_flag = "✅" if d['is_valid'] else "❌"
            if not d['is_valid']:
                invalid_count += 1
            print(f"  {v_flag} {d['company'][:40]:<40} | {d['word_count']:>3}w | {d['subject']}")
            if d['violations']:
                for v in d['violations']:
                    print(f"       ⚠ {v}")
        print(f"\n{invalid_count}/{len(qualified)} invalid")

    elif args.action == 'preview':
        print(f"\n[{args.template}] {len(qualified)} emails:\n")
        for i, lead in enumerate(qualified):
            d = make_fn(lead)
            if not d:
                print(f"  [{i+1}] SKIP: {lead.get('Company Name','?')}")
                continue
            v_flag = "✅" if d['is_valid'] else "⚠️"
            print(f"  [{i+1}] {v_flag} {d['company'][:40]:<40} | {d['word_count']:>3}w | {d['subject']}")
            if d['violations']:
                for v in d['violations']:
                    print(f"       ⚠ {v}")

    elif args.action == 'draft':
        log(f"[QUILL-WL v2] Drafting {args.template} for {len(qualified)} leads")
        ok = fail = skip = 0
        for i, lead in enumerate(qualified):
            d = make_fn(lead)
            if not d:
                log(f"  SKIP [{i+1}] {lead.get('Company Name','?')}")
                skip += 1
                continue
            if not d['is_valid']:
                log(f"  WARN [{i+1}] {d['company']}: {d['violations']}")
            log(f"  [{i+1}/{len(qualified)}] {d['to']} | {d['subject']} | {d['word_count']}w")
            draft_id = create_gmail_draft(d['to'], d['subject'], d['body'])
            if draft_id:
                ok += 1
                log(f"    ✅ Draft: {draft_id}")
                if args.template == 'T1':
                    crm.update_wl_lead(d['company'], {"Status": "Contacted", "Sent date": datetime.now(BD_TZ).strftime("%Y-%m-%d")})
            else:
                fail += 1
                log(f"    ❌ Failed")
            if i < len(qualified) - 1:
                time.sleep(2)
        log(f"DONE: {ok} drafted, {fail} failed, {skip} skipped")

    elif args.action == 'send':
        # Check Gmail token first
        if not check_gmail_token():
            log("ERROR: Gmail token is dead. Cannot send emails.")
            log("Run: cd /home/ubuntu/nanosoft && python3 gmail_auth.py")
            sys.exit(1)
        
        # Determine which leads need this template
        # T1: Status = "Qualified" (never sent)
        # T2: Status = "T1 Sent" (T1 done, T2 not yet)
        # T3: Status = "T2 Sent"
        # T4: Status = "T3 Sent"
        STATUS_MAP = {
            'T1': ['Qualified'],
            'T2': ['T1 Sent', 'Sent'],
            'T3': ['T2 Sent'],
            'T4': ['T3 Sent'],
        }
        NEXT_STATUS = {
            'T1': 'T1 Sent',
            'T2': 'T2 Sent',
            'T3': 'T3 Sent',
            'T4': 'T4 Sent',
        }
        DATE_COL = {
            'T1': 'T1 Date',
            'T2': 'T2 Date',
            'T3': 'T3 Date',
            'T4': 'T4 Date',
        }

        valid_statuses = STATUS_MAP.get(args.template, ['Qualified'])
        targets = [l for l in wl_leads if l.get("Status") in valid_statuses]

        # Also check SENT_LOG to avoid double-send
        sent_log = {}
        try:
            with open(SENT_LOG) as f:
                for line in f:
                    if line.strip():
                        entry = json.loads(line)
                        key = f"{entry.get('to','').lower()}|{entry.get('template','')}"
                        sent_log[key] = entry
        except:
            pass

        unsent = []
        for l in targets:
            email = l.get("Email", "").strip().lower()
            key = f"{email}|{args.template}"
            if key not in sent_log:
                unsent.append(l)

        if args.limit > 0:
            unsent = unsent[:args.limit]

        total = len(unsent)
        delay = 180

        log(f"[QUILL-WL v2] Sending {args.template} to {total} leads | Delay: {delay}s | ETA: {total * delay / 60:.0f}min")

        ok = fail = 0
        fail_details = []

        for i, lead in enumerate(unsent):
            d = make_fn(lead)
            if not d:
                log(f"  SKIP [{i+1}/{total}] {lead.get('Company Name','?')}")
                continue

            log(f"  [{i+1}/{total}] {d['to']} | {d['subject']}")

            try:
                import base64
                from email.mime.text import MIMEText
                from google.auth.transport.requests import Request
                from google.oauth2.credentials import Credentials
                from googleapiclient.discovery import build

                with open(os.path.join(NANOSOFT_DIR, "gmail_token.json")) as f:
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
                    with open(os.path.join(NANOSOFT_DIR, "gmail_token.json"), "w") as f:
                        json.dump(token_data, f)

                service = build("gmail", "v1", credentials=creds)

                msg = MIMEText(d['body'])
                msg['to'] = d['to']
                msg['from'] = "SaJib <nanosoftagency007@gmail.com>"
                msg['subject'] = d['subject']
                msg['List-Unsubscribe'] = '<mailto:nanosoftagency007@gmail.com?subject=unsubscribe>'
                msg['List-Unsubscribe-Post'] = 'List-Unsubscribe=One-Click'

                raw = base64.urlsafe_b64encode(msg.as_string().encode()).decode()
                result = service.users().messages().send(userId='me', body={'raw': raw}).execute()
                msg_id = result.get('id')

                if msg_id:
                    with open(SENT_LOG, 'a') as f:
                        f.write(json.dumps({
                            "to": d['to'], "company": d['company'],
                            "subject": d['subject'],
                            "sent_at": datetime.now(BD_TZ).isoformat(),
                            "message_id": msg_id, "template": args.template,
                        }) + "\n")
                    # Update CRM: status + date
                    update_fields = {"Status": NEXT_STATUS[args.template]}
                    date_col = DATE_COL[args.template]
                    update_fields[date_col] = datetime.now(BD_TZ).strftime("%Y-%m-%d")
                    crm.update_wl_lead(d['company'], update_fields)
                    ok += 1
                    log(f"    ✅ Sent ({msg_id})")
                else:
                    fail += 1
                    fail_details.append(f"{d['to']}: no msg ID")
                    log(f"    ❌ No msg ID")

            except Exception as e:
                error_str = str(e)
                fail += 1
                fail_details.append(f"{d['to']}: {error_str[:100]}")
                log(f"    ❌ {error_str[:200]}")

            if i < total - 1:
                remaining = total - i - 1
                next_eta = datetime.now(BD_TZ) + timedelta(seconds=delay * remaining)
                log(f"    Waiting {delay}s... ({remaining} left, ETA {next_eta.strftime('%H:%M')})")
                time.sleep(delay)

        log(f"DONE: {ok} sent, {fail} failed of {total}")
        if fail_details:
            for f in fail_details:
                log(f"  FAIL: {f}")
