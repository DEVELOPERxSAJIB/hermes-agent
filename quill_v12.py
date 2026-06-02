#!/usr/bin/env python3
"""
NanoSoft QUILL v12 — Expert Cold Email Generator
Based on 2025/2026 best practices from Woodpecker, Smartlead, Lemlist, Saleshandy, Mailshake.

KEY PRINCIPLES (from research):
1. NO links in body (spam trigger #1)
2. NO spam trigger words (free, guarantee, act now, limited, click, buy, etc.)
3. Under 100 words (shorter = better deliverability)
4. Subject: 2-4 words, no caps, no numbers, no special chars
5. First sentence: specific observation about THEM (not "I" or "we")
6. One pain point only, stated as consequence not feature
7. CTA: low-commitment yes/no question
8. Signature: name + company only (no links, no phone)
9. Plain text only, no HTML
10. Unique sentence structure per email (no template feel)
11. No tracking pixels
12. Include List-Unsubscribe header (Google 2025 requirement)
13. Send during business hours in recipient timezone
14. Bounce rate must stay under 2%, spam complaints under 0.1%

DNS STATUS (nanosoft.agency):
- SPF: v=spf1 include:_spf.mx.cloudflare.net ~all (exists, softfail)
- DMARC: v=DMARC1; p=none (exists, monitoring only)
- DKIM: MISSING (CRITICAL - must be added for Gmail deliverability)
- MTA-STS: MISSING
- List-Unsubscribe: Will be added in send headers
"""

import json, os, re, sys, time
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
LOG_FILE = os.path.join(NANOSOFT_DIR, "quill_v12.log")
SENT_LOG = os.path.join(NANOSOFT_DIR, "emails_sent.jsonl")

sys.path.insert(0, NANOSOFT_DIR)

# ── EXPERT RULES ────────────────────────────────────────────
MAX_WORDS = 100        # Smartlead: under 150, Woodpecker: 100-150. We go shorter.
MAX_SUBJECT = 35       # Under 35 chars, 2-4 words ideal
MAX_SENTENCES = 5      # Short emails get more replies

# Spam trigger words (from Woodpecker + Smartlead research)
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

# Banned phrases (AI-speak)
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
]

SIGNATURE = "Sajib Shikder\nNanoSoft Agency"


def check_spam_score(text):
    """Check text against spam trigger words. Returns list of violations."""
    text_lower = text.lower()
    violations = []
    
    for word in BANNED_WORDS:
        if word in text_lower:
            violations.append(f"spam_word:{word}")
    
    for phrase in BANNED_PHRASES:
        if phrase in text_lower:
            violations.append(f"banned_phrase:{phrase}")
    
    # Check for excessive caps
    words = text.split()
    caps_count = sum(1 for w in words if w.isupper() and len(w) > 1)
    if caps_count > 2:
        violations.append(f"excessive_caps:{caps_count}")
    
    # Check for excessive punctuation
    if text.count('!') > 1:
        violations.append("excessive_exclamation")
    if text.count('?') > 2:
        violations.append("excessive_questions")
    
    # Check for dollar signs
    if '$' in text:
        violations.append("dollar_sign")
    
    # Check for numbers with % 
    if re.search(r'\d+%', text):
        violations.append("percentage_sign")
    
    # Check for URL shorteners (with word boundaries to avoid false positives)
    for shortener in ['bit.ly', 'tinyurl', 'goo.gl', 't.co', 'ow.ly']:
        pattern = r'\b' + re.escape(shortener) + r'\b'
        if re.search(pattern, text_lower):
            violations.append(f"url_shortener:{shortener}")
    
    # Check for links (should be zero)
    links = len(re.findall(r'https?://', text))
    if links > 0:
        violations.append(f"contains_links:{links}")
    
    # Check first word isn't "I" or "We"
    first_word = text.strip().split()[0].lower().rstrip('.,') if text.strip() else ""
    if first_word in ('i', 'we', "i'm", "we're", "i've", "we've"):
        violations.append(f"starts_with_I/we:{first_word}")
    
    return violations


def make_subject(domain, niche, pain_points):
    """
    Subject line formula (expert best practices):
    - 2-4 words max
    - No caps, no numbers, no special chars
    - Plain observation or quick question
    - No colons, no hyphens, no em-dashes
    - Feels like internal email, not marketing
    """
    base = domain.split('.')[0]
    
    # Niche-specific subject patterns (varied, not template)
    subjects_by_niche = {
        'dental': [
            f"{base} website",
            f"quick question about {base}",
            f"{base} online",
        ],
        'law': [
            f"{base} site",
            f"about {base}",
            f"{base} question",
        ],
        'realty': [
            f"{base} listings",
            f"{base} online presence",
            f"quick note on {base}",
        ],
        'auto': [
            f"{base} shop",
            f"{base} question",
            f"about {base}",
        ],
        'gym': [
            f"{base} site",
            f"{base} online",
            f"quick question about {base}",
        ],
        'beauty': [
            f"{base} bookings",
            f"{base} site",
            f"about {base}",
        ],
        'cleaning': [
            f"{base} bookings",
            f"{base} site",
            f"{base} question",
        ],
        'landscaping': [
            f"{base} site",
            f"about {base}",
            f"{base} question",
        ],
        'pest': [
            f"{base} site",
            f"{base} question",
            f"about {base}",
        ],
        'roofing': [
            f"{base} site",
            f"{base} question",
            f"about {base}",
        ],
        'plumbing': [
            f"{base} site",
            f"{base} question",
            f"about {base}",
        ],
        'restaurant': [
            f"{base} site",
            f"{base} online",
            f"about {base}",
        ],
        'moving': [
            f"{base} site",
            f"{base} question",
            f"about {base}",
        ],
        'other': [
            f"{base} site",
            f"about {base}",
            f"{base} question",
        ],
    }
    
    options = subjects_by_niche.get(niche, subjects_by_niche['other'])
    
    # Pick shortest valid subject
    subject = options[0]
    for opt in options:
        if len(opt) <= MAX_SUBJECT and len(opt) < len(subject):
            subject = opt
    
    if len(subject) > MAX_SUBJECT:
        subject = subject[:MAX_SUBJECT].rstrip()
    
    return subject


def make_email(lead):
    """
    Generate expert-level cold email.
    Returns dict or None.
    
    EMAIL STRUCTURE (expert formula):
    1. Subject: 2-4 words, plain, no special chars
    2. Line 1: Specific observation about THEM (not "I" or "We")
    3. Line 2: Consequence of the problem (business impact)
    4. Line 3: Soft credibility (brief, not braggy)
    5. Line 4: Low-commitment yes/no CTA
    6. Signature: Name + company only
    
    TOTAL: 60-90 words, 4-5 sentences max
    """
    company = lead.get("Company Name", "").strip()
    website = lead.get("Website", "").strip()
    email = lead.get("Owner Email", "").strip()
    pain_points = lead.get("Pain Point", "").strip()
    severity = lead.get("Severity", "medium").strip()
    outreach_angle = lead.get("Outreach Angle", "").strip()
    judge_score = str(lead.get("Judge Score", "")).strip()
    
    if not email or not website:
        return None
    
    # Skip bad emails
    bad_patterns = [
        r'user@domain', r'example@', r'@whois\.', r'@sentry\.', r'@bytedance\.',
        r'vue@3\.', r'@scorebig\.', r'@afternic\.', r'john@doe\.', r'feedback@',
    ]
    for pat in bad_patterns:
        if re.search(pat, email, re.IGNORECASE):
            return None
    
    domain = re.sub(r'^https?://(www\.)?', '', website).split('/')[0].lower()
    domain_short = domain.split('.')[0]
    
    # Detect niche
    combined = (company + ' ' + website + ' ' + pain_points).lower()
    if any(w in combined for w in ['dent', 'dental', 'tooth']):
        niche = 'dental'
    elif any(w in combined for w in ['law', 'attorney', 'lawyer', 'legal', 'lawclinic']):
        niche = 'law'
    elif any(w in combined for w in ['realty', 'real estate', 'realtor', 'property', 'realtyteam']):
        niche = 'realty'
    elif any(w in combined for w in ['auto', 'car', 'automotive', 'repair', 'dfw auto', 'groupauto', 'plusauto', 'grove auto']):
        niche = 'auto'
    elif any(w in combined for w in ['gym', 'fitness', 'workout']):
        niche = 'gym'
    elif any(w in combined for w in ['salon', 'hair', 'beauty', 'massage']):
        niche = 'beauty'
    elif any(w in combined for w in ['clean', 'maid', 'housekeep']):
        niche = 'cleaning'
    elif any(w in combined for w in ['landscape', 'lawn', 'garden', 'tree']):
        niche = 'landscaping'
    elif any(w in combined for w in ['pest']):
        niche = 'pest'
    elif any(w in combined for w in ['roof', 'roofing']):
        niche = 'roofing'
    elif any(w in combined for w in ['plumb', 'heating', 'hvac']):
        niche = 'plumbing'
    elif any(w in combined for w in ['restaurant', 'food', 'cafe', 'best restaurant']):
        niche = 'restaurant'
    elif any(w in combined for w in ['movers', 'moving']):
        niche = 'moving'
    else:
        niche = 'other'
    
    # Parse pain points
    pains = [p.strip() for p in pain_points.split(',') if p.strip()] if pain_points else []
    pains_lower = [p.lower() for p in pains]
    
    # ── SUBJECT ──
    subject = make_subject(domain, niche, pains)
    
    # ── BODY: Niche-specific, unique per lead ──
    # Each email is hand-crafted style, not template-filled
    
    # LINE 1: Observation about THEM (varied patterns, never starts with "I" or "We")
    # Different opening styles to avoid pattern detection
    l1_options = {
        'dental': [
            f"Most dental offices lose patients before they even call. {domain} doesn't show reviews or ratings anywhere visible.",
            f"Patients searching for a dentist in the area probably never make it to {domain}. The site is hard to find on Google.",
            f"{domain} looks professional but it's missing the one thing that makes patients pick up the phone.",
        ],
        'law': [
            f"People looking for legal help in the area are searching Google right now. {domain} isn't showing up.",
            f"{domain} doesn't have client reviews or case results visible. That's the first thing potential clients look for.",
            f"Most people choose a lawyer within 5 minutes of searching. {domain} isn't in those results.",
        ],
        'realty': [
            f"Buyers and sellers in the area are searching online first. {domain} isn't capturing any of that traffic.",
            f"{domain} has property listings but no way for serious buyers to get alerts or save searches.",
            f"Real estate moves fast. {domain} takes too long for pages to load and visitors leave before seeing listings.",
        ],
        'auto': [
            f"People searching for auto services in the area probably never find {domain}. It's buried on page 2 of Google.",
            f"{domain} doesn't show pricing or let customers book online. Most people just call the shop that does.",
            f"Auto repair customers want to book online. {domain} only has a phone number.",
        ],
        'gym': [
            f"People looking for a gym in the area search Google first. {domain} doesn't show up in local results.",
            f"{domain} doesn't have class schedules or membership pricing visible. People just move on to the next gym.",
            f"Most gym visitors decide in under 30 seconds online. {domain} doesn't make a strong first impression.",
        ],
        'beauty': [
            f"People looking for beauty services in the area are booking online. {domain} doesn't offer that option.",
            f"{domain} doesn't show a portfolio or before/after work. That's what builds trust with new clients.",
            f"Beauty clients compare 3-4 places before booking. {domain} is missing the details that win them over.",
        ],
        'cleaning': [
            f"People searching for cleaning services want instant quotes. {domain} makes them call or email first.",
            f"{domain} doesn't show pricing or availability. Most people just book the competitor who does.",
            f"Cleaning customers are busy. {domain} doesn't let them book and pay online in under a minute.",
        ],
        'landscaping': [
            f"Homeowners looking for landscaping services compare 3-4 companies online. {domain} doesn't show project photos.",
            f"{domain} has a nice look but no clear way to request a quote. People just call the next company.",
            f"Landscaping projects are visual decisions. {domain} doesn't showcase past work effectively.",
        ],
        'pest': [
            f"People with a pest problem need help fast. {domain} doesn't show same-day or emergency availability.",
            f"{domain} doesn't have service areas or pricing visible. People just call the company that does.",
            f"Pest control customers want to know the cost upfront. {domain} makes them call for a quote.",
        ],
        'roofing': [
            f"Roofing decisions are urgent. {domain} doesn't show emergency services or instant quote options.",
            f"{domain} doesn't display past projects or reviews. Homeowners choose the company that looks most trusted.",
            f"People getting roof work done compare multiple quotes. {domain} doesn't make it easy to request one.",
        ],
        'plumbing': [
            f"Plumbing problems can't wait. {domain} doesn't show emergency availability or same-day booking.",
            f"{domain} doesn't display service areas or pricing. People just call the plumber who does.",
            f"People searching for a plumber want instant answers. {domain} makes them fill out a form and wait.",
        ],
        'restaurant': [
            f"People choose restaurants based on what they see online. {domain} doesn't showcase the menu or atmosphere well.",
            f"{domain} doesn't have online ordering or reservations. That's where most restaurant revenue comes from now.",
            f"Restaurant customers check Google before deciding. {domain} doesn't have enough reviews or photos.",
        ],
        'moving': [
            f"People planning a move compare 3-4 companies. {domain} doesn't show pricing or let them get an instant quote.",
            f"{domain} looks professional but doesn't have customer reviews visible. That's what builds trust for big moves.",
            f"Moving customers want transparency. {domain} doesn't show what's included or how pricing works.",
        ],
        'other': [
            f"People searching for services like yours compare options online first. {domain} isn't standing out.",
            f"{domain} looks good but it's missing the details that turn visitors into customers.",
            f"Most visitors decide in under 10 seconds. {domain} doesn't communicate value fast enough.",
        ],
    }
    
    l1_choices = l1_options.get(niche, l1_options['other'])
    # Use domain length to pick variation (pseudo-random but deterministic)
    l1 = l1_choices[len(domain) % len(l1_choices)]
    
    # LINE 2: Consequence (business impact, not feature list)
    l2_options = {
        'dental': [
            "That means empty appointment slots while competitors down the street are fully booked.",
            "Every month without visibility is revenue left on the table.",
            "New patients go to whoever shows up first in search results.",
        ],
        'law': [
            "Which means potential clients are calling your competitors instead.",
            "Every day invisible online is a day of lost cases.",
            "The firms showing up first get the calls. It's that simple.",
        ],
        'realty': [
            "So buyers and sellers are working with agents they found more easily.",
            "Listings sit longer and commissions go to more visible competitors.",
            "The agents capturing online leads are closing more deals.",
        ],
        'auto': [
            "So customers are going to shops that make it easier to book.",
            "Every missed booking is money walking out the door.",
            "The shops with online booking are getting all the calls.",
        ],
        'gym': [
            "So potential members join the gym that looks better online.",
            "Every month of poor visibility is a month of empty memberships.",
            "The gyms showing up in local searches are filling classes.",
        ],
        'beauty': [
            "So clients book with salons that showcase their work better.",
            "Every client that goes elsewhere is recurring revenue lost.",
            "The businesses with strong online presence are fully booked.",
        ],
        'cleaning': [
            "So customers book with companies that make it instant and easy.",
            "Every booking you miss goes to a competitor with online booking.",
            "The cleaning companies with instant quotes are winning every time.",
        ],
        'landscaping': [
            "So homeowners hire the company that shows their work best.",
            "Every lost quote is a project going to a competitor.",
            "The landscapers with strong portfolios are booked months ahead.",
        ],
        'pest': [
            "So customers call the company that shows up first and looks most trusted.",
            "Every missed call is a job going to a competitor.",
            "The pest control companies with strong online presence stay busy year-round.",
        ],
        'roofing': [
            "So homeowners hire the roofer that looks most professional online.",
            "Every lost estimate is a big-ticket job going elsewhere.",
            "The roofers with strong Google presence are booked solid.",
        ],
        'plumbing': [
            "So customers call the plumber that's easiest to find and book.",
            "Every missed emergency call is hundreds in lost revenue.",
            "The plumbers with online booking are getting all the urgent jobs.",
        ],
        'restaurant': [
            "So diners choose the restaurant that looks better online.",
            "Every empty table is revenue that could have been captured.",
            "The restaurants with strong online presence are always busy.",
        ],
        'moving': [
            "So customers hire the moving company that looks most transparent.",
            "Every lost quote is thousands in potential revenue.",
            "The movers with strong reviews and easy quotes are fully booked.",
        ],
        'other': [
            "Which means potential customers are choosing competitors they found more easily.",
            "Every day of poor visibility is lost revenue.",
            "The businesses showing up online are getting all the calls.",
        ],
    }
    
    l2_choices = l2_options.get(niche, l2_options['other'])
    l2 = l2_choices[(len(domain) + 1) % len(l2_choices)]
    
    # LINE 3: Soft credibility (NO links, NO portfolio references)
    l3_options = [
        "I help local businesses fix exactly this kind of problem.",
        "This is the kind of work I do for businesses like yours.",
        "I work with local service businesses on this exact issue.",
        "Fixing this is what I do for businesses in your area.",
        "I build websites that actually bring in customers.",
    ]
    l3 = l3_options[(len(domain) + 2) % len(l3_options)]
    
    # LINE 4: CTA (low-commitment yes/no question)
    cta_options = [
        f"Would it be worth a quick chat about fixing {domain}?",
        f"Should I send over a 2 minute screen recording showing what I'd change?",
        f"Want me to show you what a better version of {domain} could look like?",
        f"Is this something you'd want to improve this month?",
        f"Would a quick call about {domain} be useful?",
    ]
    cta = cta_options[(len(domain) + 3) % len(cta_options)]
    
    # ── ASSEMBLE ──
    body = f"{l1}\n\n{l2}\n\n{l3}\n\n{cta}\n\n{SIGNATURE}"
    
    # ── VALIDATE ──
    violations = check_spam_score(body)
    word_count = len(body.split())
    
    # Auto-fix if too long
    if word_count > MAX_WORDS:
        # Remove l3 (credibility line) to shorten
        body = f"{l1}\n\n{l2}\n\n{cta}\n\n{SIGNATURE}"
        word_count = len(body.split())
        violations.append(f"trimmed_credibility_line")
    
    # Final check
    if word_count > MAX_WORDS:
        violations.append(f"still_too_long:{word_count}")
    
    is_valid = len([v for v in violations if not v.startswith("trimmed")]) == 0
    
    return {
        "to": email,
        "subject": subject,
        "body": body,
        "company": company,
        "domain": domain,
        "niche": niche,
        "word_count": word_count,
        "subject_length": len(subject),
        "is_valid": is_valid,
        "violations": violations,
        "drafted_at": datetime.now(BD_TZ).isoformat(),
        "status": "drafted",
    }


# ── GMAIL SEND via API ──────────────────────────────────────
def send_via_gmail_api(to_email, subject, body):
    """Send email via Gmail API (not SMTP). Returns message ID or None."""
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
        msg['from'] = "nanosoftagency007@gmail.com"
        msg['subject'] = subject
        
        # Add List-Unsubscribe header (Google 2025 requirement)
        msg['List-Unsubscribe'] = '<mailto:nanosoftagency007@gmail.com?subject=unsubscribe>'
        msg['List-Unsubscribe-Post'] = 'List-Unsubscribe=One-Click'
        
        raw = base64.urlsafe_b64encode(msg.as_string().encode()).decode()
        
        result = service.users().messages().send(
            userId='me',
            body={'raw': raw}
        ).execute()
        
        return result.get('id')
    except Exception as e:
        print(f"[SEND] Error for {to_email}: {e}")
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
    parser = argparse.ArgumentParser(description='NanoSoft QUILL v12')
    parser.add_argument('action', choices=['draft', 'send', 'test', 'preview'], help='Action')
    parser.add_argument('--delay', type=int, default=180, help='Seconds between sends')
    parser.add_argument('--limit', type=int, default=0, help='Limit number of emails (0=all)')
    args = parser.parse_args()
    
    from crm import get_crm
    crm = get_crm()
    
    if args.action == 'test':
        # Test with first drafted lead
        leads = crm.get_leads_by_status("Drafted")
        if leads:
            d = make_email(leads[0])
            if d:
                print("SUBJECT:", d['subject'])
                print("WORDS:", d['word_count'])
                print("VALID:", d['is_valid'])
                if d['violations']:
                    print("VIOLATIONS:", d['violations'])
                print("\n--- BODY ---\n", d['body'])
            else:
                print("make_email returned None")
        else:
            print("No Drafted leads found.")
    
    elif args.action == 'preview':
        # Preview all emails without sending
        leads = crm.get_leads_by_status("Drafted")
        print(f"Previewing {len(leads)} emails:\n")
        for i, lead in enumerate(leads):
            d = make_email(lead)
            if not d:
                print(f"  [{i+1}] SKIP (bad email): {lead.get('Company Name','?')} | {lead.get('Owner Email','?')}")
                continue
            v_flag = "⚠️" if d['violations'] else "✅"
            print(f"  [{i+1}] {v_flag} {d['company'][:40]} | {d['word_count']}w | {d['subject']}")
            if d['violations']:
                print(f"       Violations: {d['violations']}")
        print(f"\nTotal: {len(leads)} leads")
    
    elif args.action == 'draft':
        # Draft all Drafted leads (re-draft with new template)
        leads = crm.get_leads_by_status("Drafted")
        if not leads:
            print("[QUILL] No Drafted leads.")
            sys.exit(0)
        
        log(f"[QUILL v12] Drafting {len(leads)} leads...")
        count = 0
        skipped = 0
        
        for i, lead in enumerate(leads):
            d = make_email(lead)
            if not d:
                log(f"  SKIP [{i+1}/{len(leads)}] {lead.get('Company Name','?')} (bad email)")
                skipped += 1
                continue
            
            status = "OK" if d['is_valid'] else "WARN"
            v_info = f" | {d['violations']}" if d['violations'] else ""
            log(f"  {status} [{i+1}/{len(leads)}] {d['company'][:35]} | {d['word_count']}w | {d['subject']}{v_info}")
            count += 1
        
        log(f"[QUILL v12] Done: {count} drafted, {skipped} skipped")
    
    elif args.action == 'send':
        # Send all Drafted leads with delay
        leads = crm.get_leads_by_status("Drafted")
        if not leads:
            print("[QUILL] No Drafted leads.")
            sys.exit(0)
        
        # Load sent log
        sent_emails = set()
        try:
            with open(SENT_LOG) as f:
                for line in f:
                    if line.strip():
                        sent_emails.add(json.loads(line).get("to", "").lower())
        except:
            pass
        
        # Filter unsent
        unsent = []
        for lead in leads:
            email = lead.get("Owner Email", "").strip().lower()
            if email and email not in sent_emails:
                unsent.append(lead)
        
        if args.limit > 0:
            unsent = unsent[:args.limit]
        
        total = len(unsent)
        total_min = (total * args.delay) / 60
        eta = datetime.now(BD_TZ) + timedelta(minutes=total_min)
        
        log(f"[QUILL v12] Sending {total} emails | Delay: {args.delay}s | ETA: {eta.strftime('%H:%M')}")
        
        ok = 0
        fail = 0
        fail_details = []
        
        for i, lead in enumerate(unsent):
            d = make_email(lead)
            if not d:
                log(f"  SKIP [{i+1}/{total}] {lead.get('Company Name','?')} (bad email)")
                continue
            
            log(f"  [{i+1}/{total}] {d['to']} | {d['subject']}")
            
            try:
                msg_id = send_via_gmail_api(d['to'], d['subject'], d['body'])
                
                if msg_id:
                    # Log sent
                    with open(SENT_LOG, 'a') as f:
                        f.write(json.dumps({
                            "to": d['to'],
                            "company": d['company'],
                            "subject": d['subject'],
                            "sent_at": datetime.now(BD_TZ).isoformat(),
                            "message_id": msg_id,
                        }) + "\n")
                    
                    sent_emails.add(d['to'].lower())
                    
                    # Update CRM
                    all_leads = crm.get_all_leads()
                    for l in all_leads:
                        if l.get("Owner Email", "").strip().lower() == d['to'].lower():
                            crm.update_lead(l.get("Company Name", ""), {"Status": "Email Sent"})
                            crm.update_lead(l.get("Company Name", ""), {
                                "Email sent date": datetime.now(BD_TZ).strftime("%Y-%m-%d")
                            })
                            break
                    
                    ok += 1
                    log(f"    OK (msg: {msg_id})")
                else:
                    fail += 1
                    fail_details.append(f"{d['to']}: no message ID")
                    log(f"    FAIL: no message ID")
                    
            except Exception as e:
                error_str = str(e)
                if "rate" in error_str.lower() or "quota" in error_str.lower():
                    log(f"    RATE LIMIT: {error_str}")
                    log("    Waiting 60s...")
                    time.sleep(60)
                    try:
                        msg_id = send_via_gmail_api(d['to'], d['subject'], d['body'])
                        if msg_id:
                            ok += 1
                            log(f"    OK after retry")
                            continue
                    except:
                        pass
                
                fail += 1
                fail_details.append(f"{d['to']}: {error_str[:100]}")
                log(f"    FAIL: {error_str[:200]}")
            
            # Wait between sends
            if i < total - 1:
                remaining = total - i - 1
                next_eta = datetime.now(BD_TZ) + timedelta(seconds=args.delay * remaining)
                log(f"    Waiting {args.delay}s... ({remaining} left, ETA {next_eta.strftime('%H:%M')})")
                time.sleep(args.delay)
                
                # Refresh token every 10 sends
                if (i + 1) % 10 == 0:
                    try:
                        # Token refresh happens inside send_via_gmail_api
                        log("    [token check]")
                    except:
                        pass
        
        log(f"[QUILL v12] DONE: {ok} sent, {fail} failed out of {total}")
        if fail_details:
            log("Failures:")
            for f in fail_details:
                log(f"  - {f}")
