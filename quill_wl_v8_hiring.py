#!/usr/bin/python3
"""
NanoSoft QUILL-WL v8 — Hiring Signal Angle
New approach: "I noticed you're hiring. Have you considered an agency instead?"

This is a fundamentally different pitch:
- NOT "we handle your overflow"
- BUT "hiring is expensive and risky — an agency is smarter"

Only used for leads with hiring signals (job postings on their website).
"""
import json, os, re, sys, time
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
LOG_FILE = os.path.join(NANOSOFT_DIR, "quill_wl.log")
SENT_LOG = os.path.join(NANOSOFT_DIR, "emails_sent_wl.jsonl")

sys.path.insert(0, NANOSOFT_DIR)

# ── RULES ───────────────────────────────────────────────────
MAX_WORDS = 100
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
        pattern = r'\b' + re.escape(word) + r'\b'
        if re.search(pattern, text_lower):
            violations.append(f"spam_word:{word}")
    for phrase in BANNED_PHRASES:
        if phrase in text_lower:
            violations.append(f"banned_phrase:{phrase}")
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


def company_short(company):
    return company.split()[0]


# ── EMAIL TEMPLATES v8 — Hiring Signal Angle ──
# For leads that are actively hiring (job postings on their website)
# Angle: "Hiring is expensive. An agency is smarter."

def make_email_t1_hiring(lead):
    """
    T1 — Hiring Signal Hook
    ~60 words. Reference their job posting. Ask if they've considered an agency.
    Based on Chairman's exact wording.
    """
    company = lead.get("Company Name", "").strip()
    email = lead.get("Email", "").strip()
    services = parse_services(lead.get("Services", ""))
    owner_name = lead.get("Owner Name", "").strip()
    hiring_signals = lead.get("Hiring Signals", "").strip()

    if not email or not company:
        return None

    first_name = get_first_name(owner_name)
    first_word = company_short(company)
    greeting = f"Hey {first_name}" if first_name else f"Hey {first_word} team"

    primary = get_primary_service(services)
    if '/' in primary:
        primary = primary.split('/')[0].strip()

    import random
    random.seed(hash(company))

    # Reference the specific job posting if we know it
    if hiring_signals:
        # Extract the role from hiring signals
        role = hiring_signals.split(":")[0].strip() if ":" in hiring_signals else "team"
        hiring_ref = f"Noticed you are hiring for {role}"
    else:
        hiring_refs = [
            f"Saw {first_word} is hiring right now",
            f"Noticed {first_word} has open positions",
            f"Looking at {first_word} careers page — you are growing",
        ]
        hiring_ref = random.choice(hiring_refs)

    body = (
        f"{greeting},\n\n"
        f"{hiring_ref}. Are you building the team in-house or have you considered working with an agency?\n\n"
        f"Hiring the wrong person is costly and time-consuming. If a hire does not work out, "
        f"you let them go, start recruiting again, conduct more interviews, handle onboarding, "
        f"payroll, and repeat the entire process.\n\n"
        f"An agency is not just one person. It gives you access to multiple experts with "
        f"different skill sets. In many cases, an agency provides better experience, stronger "
        f"results, greater flexibility, and a more cost-effective solution than hiring internally.\n\n"
        f"Worth a conversation?\n\n"
        f"SaJib"
    )

    subjects = [
        f"{first_word} hiring",
        f"{first_word} team growth",
        f"{first_word} question",
        f"re: {first_word} hiring",
    ]
    valid_subjects = [s for s in subjects if len(s) <= MAX_SUBJECT]
    subject = valid_subjects[len(company) % len(valid_subjects)]

    return _finalize(email, subject, body, company, "T1-HIRING")


def make_email_t2_hiring(lead):
    """
    T2 — Follow-up (Day 4-5)
    ~50 words. Share a specific scenario of agency vs hiring.
    """
    company = lead.get("Company Name", "").strip()
    email = lead.get("Email", "").strip()
    services = parse_services(lead.get("Services", ""))
    owner_name = lead.get("Owner Name", "").strip()

    if not email or not company:
        return None

    first_name = get_first_name(owner_name)
    first_word = company_short(company)
    greeting = f"Hey {first_name}" if first_name else f"Hey {first_word} team"

    primary = get_primary_service(services)
    kw = primary.split('/')[0].strip()

    import random
    random.seed(hash(company) + 1)

    scenarios = [
        f"An agency in {lead.get('Country','the US')} was hiring for 3 React roles. Took 4 months, 2 bad hires, "
        f"forty thousand plus wasted. They switched to an agency model. Got 5 experts in 2 weeks, "
        f"project shipped on time, sixty percent cheaper than payroll.",
        
        f"A dev shop in Europe needed 2 senior devs for a 6-month project. Hiring would take 3+ months "
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


def make_email_t3_hiring(lead):
    """
    T3 — Reframe (Day 9-10)
    ~40 words. Ask about their hiring timeline. Low pressure.
    """
    company = lead.get("Company Name", "").strip()
    email = lead.get("Email", "").strip()
    services = parse_services(lead.get("Services", ""))
    owner_name = lead.get("Owner Name", "").strip()

    if not email or not company:
        return None

    first_name = get_first_name(owner_name)
    first_word = company_short(company)
    greeting = f"Hey {first_name}" if first_name else f"Hey {first_word} team"

    primary = get_primary_service(services)
    kw = primary.split('/')[0].strip()

    questions = [
        f"Quick question. What is {first_word} hiring timeline for the {kw} roles? "
        f"If you need people faster than recruiting allows, we can help.",
        
        f"Curious. How many roles is {first_word} looking to fill this quarter? "
        f"If the timeline is tight, an agency team might be worth considering.",
    ]
    import random
    random.seed(hash(company) + 2)
    question = random.choice(questions)

    body = (
        f"{greeting},\n\n"
        f"{question}\n\n"
        f"No pitch. Just trying to understand if there is a fit.\n\n"
        f"SaJib"
    )

    subject = f"{first_word} timeline"
    return _finalize(email, subject, body, company, "T3-HIRING")


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
        r'vue@[\d.]+', r'@whois\.', r'@sentry\.', r'@bytedance\.', r'@scorebig\.',
        r'@afternic\.', r'john@doe', r'feedback@', r'your@email', r'email@company',
        r'mail@domain', r'john\.doe@gmail', r'default-utils\.js',
    ]
    for pattern in bad_patterns:
        if re.search(pattern, to):
            return None

    if '@' not in to or '.' not in to.split('@')[-1]:
        return None

    return {
        "to": to,
        "subject": subject,
        "body": body,
        "company": company,
        "template": template_type,
        "violations": violations,
        "word_count": word_count,
        "valid": is_valid,
    }


# ── Test ──
if __name__ == "__main__":
    test_lead = {
        "Company Name": "TechVentures Agency",
        "Email": "hello@techventures.com",
        "Services": "mobile development, React Native, iOS",
        "White Label Signals": "",
        "Owner Name": "John Smith",
        "Pain Points": "",
        "Hiring Signals": "Senior React Native Developer",
        "Country": "US",
        "Status": "Qualified",
    }

    print("=== TEMPLATES v8 — HIRING SIGNAL ANGLE ===\n")
    for name, fn in [("T1-HIRING", make_email_t1_hiring), ("T2-HIRING", make_email_t2_hiring), ("T3-HIRING", make_email_t3_hiring)]:
        result = fn(test_lead)
        if result:
            v = check_spam_score(result['body'])
            print(f"{name}: {result['word_count']}w, subj=\"{result['subject']}\"")
            print(f"  Body:\n{result['body']}")
            print(f"  Violations: {v or 'None'}")
            print()
