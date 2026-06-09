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


# ── EMAIL TEMPLATES v6 — Ultra-short, zero brag, pure question ──

def make_email_t1(lead):
    """
    T1 — The Hook (Day 1)
    ~40 words. One observation. One question. No pitch. No "we" first.
    """
    company = lead.get("Company Name", "").strip()
    email = lead.get("Email", "").strip()
    services = parse_services(lead.get("Services", ""))
    wl_signals = lead.get("White Label Signals", "").strip()
    owner_name = lead.get("Owner Name", "").strip()

    if not email or not company:
        return None

    first_name = get_first_name(owner_name)
    first_word = company.split()[0]
    greeting = f"Hey {first_name}" if first_name else f"Hey {first_word} team"

    primary = get_primary_service(services)
    if '/' in primary:
        primary = primary.split('/')[0].strip()

    import random
    random.seed(hash(company))

    # Observation: use THEIR language from their website
    if wl_signals and ('white label' in wl_signals.lower() or 'reseller' in wl_signals.lower()):
        obs = f"{first_word} handles white label delivery for partners"
    elif wl_signals and ('staff augmentation' in wl_signals.lower() or 'outsourcing' in wl_signals.lower()):
        obs = f"{first_word} scales teams through staff augmentation"
    elif primary:
        obs = f"{first_word} ships {primary} projects"
    else:
        obs = f"{first_word} takes on client development work"

    # Question: make them think about THEIR problem
    questions = [
        f"When your team hits capacity, where does the overflow go",
        f"What happens when a big project lands and your team is booked",
        f"When you are at full capacity and another project comes in, what do you do",
        f"How do you handle {primary} overflow right now",
    ]
    question = random.choice(questions)

    body = (
        f"{greeting},\n\n"
        f"{obs}. {question}?\n\n"
        f"SaJib"
    )

    subject = subject_hook(company, services)
    return _finalize(email, subject, body, company, "T1")


def make_email_t2(lead):
    """
    T2 — Value Add (Day 4-5)
    ~45 words. One concrete scenario. Zero pressure. No links. No brag.
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

    # Concrete scenario with REAL numbers (not vague "we helped an agency")
    if 'mobile' in primary.lower():
        scenarios = [
            f"Last month covered a React Native build for an agency whose lead dev was out. 14 screens, shipped on time, under their brand.",
            f"An agency sent us their mobile overflow in March. 3 devs, 6 weeks, iOS plus Android. Client gave them a 5 star review.",
        ]
    elif 'AI' in kw or 'ML' in kw:
        scenarios = [
            f"Recently helped an agency ship an ML pipeline they could not staff. 4 week sprint, their name on the repo, their client renewed.",
            f"An agency partner sent us an AI feature build last quarter. Model plus API, shipped in 3 weeks under their brand.",
        ]
    elif 'web' in primary.lower():
        scenarios = [
            f"An agency came to us at capacity on a platform rebuild. We took 2 modules, shipped in 3 sprints, their margin stayed intact.",
            f"Last quarter we handled a full SaaS dashboard for an agency booked solid. Their client, their repo, their review.",
        ]
    else:
        scenarios = [
            f"Recently plugged in on a {kw} build for an agency at capacity. 4 week sprint, under their brand, client never knew.",
            f"An agency partner sent overflow work our way last month. Delivered under their name, on their timeline, no hiccups.",
        ]

    scenario = random.choice(scenarios)

    body = (
        f"{greeting},\n\n"
        f"{scenario}\n\n"
        f"Heads up for whenever it is useful. Zero pressure.\n\n"
        f"SaJib"
    )

    subject = subject_followup(company)
    return _finalize(email, subject, body, company, "T2")


def make_email_t3(lead):
    """
    T3 — Reframe (Day 9-10)
    ~35 words. Ask about THEIR process. Learn, don't pitch.
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

    questions = [
        f"How does {first_word} usually handle {kw} overflow",
        f"When {first_word} is at capacity on {kw} work, what is the first move",
        f"Curious, do you have a go to when {kw} projects outpace the team",
    ]
    question = random.choice(questions)

    body = (
        f"{greeting},\n\n"
        f"{question}?\n\n"
        f"No agenda. Just trying to learn how agencies like yours think about this.\n\n"
        f"SaJib"
    )

    subject = subject_reframe(company)
    return _finalize(email, subject, body, company, "T3")


def make_email_t4(lead):
    """
    T4 — Breakup (Day 14-16)
    ~30 words. Clean exit. One line for later.
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
        f"Going to step back. Timing is everything and right now might not be it.\n\n"
        f"If {kw} overflow ever comes up, we plug in quietly under your brand. Just keep us in mind.\n\n"
        f"All the best with {first_word}.\n\n"
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
    parser.add_argument('--limit', type=int, default=0, help='Limit emails (0=all)')
    args = parser.parse_args()

    from crm import get_crm
    crm = get_crm()
    wl_leads = crm.get_wl_all()

    qualified = [l for l in wl_leads if l.get("Status") == "Qualified"]
    if args.limit > 0:
        qualified = qualified[:args.limit]

    log(f"[QUILL-WL v2] {len(qualified)} Qualified WL leads loaded")

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
