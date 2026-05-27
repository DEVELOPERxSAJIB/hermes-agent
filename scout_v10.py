"""
NanoSoft SCOUT — Lead Discovery Agent v10
Domain generation + DNS verification + HTTP analysis + email extraction + JUDGE v4.
Finds local small businesses with bad websites and extracts contact emails.
Exactly same approach as scout_v9 which was working perfectly.
"""
import json
import os
import re
import sys
import time
import socket
import urllib.request
import urllib.error
import ssl
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
LOG_FILE = os.path.join(NANOSOFT_DIR, "scout.log")
STATE_FILE = os.path.join(NANOSOFT_DIR, "scout_state.json")
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

sys.path.insert(0, NANOSOFT_DIR)

def log(msg):
    ts = datetime.now(BD_TZ).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, 'a') as f:
            f.write(line + "\n")
    except:
        pass

def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except:
        return {"last_run_date": "", "runs": 0, "total_leads_found": 0}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

# ── CONFIG ──

TARGET_LEADS_PER_DAY = 30
DNS_TIMEOUT = 5
HTTP_TIMEOUT = 10

# Domain generation - same niches that produced the 35 Drafted leads
NICHES = [
    "gym", "fitness", "dental", "dentist", "plumbing", "plumber",
    "salon", "hair", "restaurant", "realtor", "realty", "chiropractor",
    "massage", "spa", "pestcontrol", "roofing", "flooring",
    "landscaping", "lawn", "cleaning", "maid", "movers", "moving",
    "attorney", "lawyer", "accounting", "insurance", "photography",
    "towing", "autorepair", "mechanic", "petgrooming", "veterinary",
    "daycare", "preschool", "tutor", "bakery", "catering",
    "electrician", "hvac", "painting", "flooring", "windows",
]

TLDS = [".com", ".net", ".org", ".us", ".co", ".biz", ".info"]

PREFIXES = ["the", "my", "get", "go", "pro", "best", "top", "eco", "smart", "premier"]
SUFFIXES = ["pro", "hub", "spot", "lab", "plus", "max", "hq", "now"]

# Skip these email domains
SKIP_EMAIL_DOMAINS = {
    'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'aol.com',
    'mail.com', 'protonmail.com', 'icloud.com', 'live.com', 'msn.com',
    'example.com', 'test.com', 'sentry.io', 'github.com', 'twitter.com',
    'facebook.com', 'linkedin.com', 'medium.com', 'youtube.com',
    'wikipedia.org', 'amazonaws.com', 'cloudflare.com', 'googleapis.com',
    'herokuapp.com', 'vercel.app', 'netlify.app', 'mailgun.org',
    'sendgrid.net', 'stripe.com', 'gkg.net', 'whois.gkg.net',
}

# ── DNS CHECK ──────────────────────────────────────────────

def dns_resolves(domain):
    try:
        socket.setdefaulttimeout(DNS_TIMEOUT)
        result = socket.getaddrinfo(domain, None)
        return len(result) > 0
    except:
        return False
    finally:
        socket.setdefaulttimeout(None)

# ── HTTP FETCH ──────────────────────────────────────────────

def fetch_page(url):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'text/html'})
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT, context=ctx) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
            title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.I | re.S)
            title = ""
            if title_match:
                title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
                title = re.sub(r'\s*[|\-–—·•]\s*.+$', '', title).strip()
            return resp.status, html, title
    except urllib.error.HTTPError as e:
        return e.code, "", ""
    except:
        return 0, "", ""

# ── EMAIL EXTRACTION ────────────────────────────────────────

def extract_emails(html, base_url=""):
    emails = set()
    email_re = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
    
    for match in email_re.finditer(html):
        email = match.group().lower()
        local = email.split('@')[0]
        # Skip image filenames
        if any(local.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico', '.bmp']):
            continue
        if len(local) > 50:
            continue
        # Skip known bad domains
        domain = email.split('@')[1] if '@' in email else ""
        if domain in SKIP_EMAIL_DOMAINS:
            continue
        # Skip whois/hash emails
        if re.match(r'^[0-9a-f]{20,}$', local):
            continue
        emails.add(email)
    
    # mailto: links
    for m in re.finditer(r'mailto:([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})', html):
        emails.add(m.group(1).lower())
    
    # Try contact pages if no emails
    if not emails and base_url:
        for path in ['/contact', '/contact-us', '/about', '/about-us']:
            try:
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
                req = urllib.request.Request(base_url.rstrip('/') + path, headers={'User-Agent': USER_AGENT})
                with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
                    contact_html = resp.read().decode('utf-8', errors='ignore')
                for match in email_re.finditer(contact_html):
                    email = match.group().lower()
                    domain = email.split('@')[1] if '@' in email else ""
                    if domain not in SKIP_EMAIL_DOMAINS:
                        emails.add(email)
                if emails:
                    break
            except:
                continue
    
    # Prefer business emails over free domains
    business = [e for e in emails if not any(e.endswith('@' + d) for d in [
        'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'aol.com', 'mail.com'
    ])]
    return business if business else list(emails)

# ── PAIN POINTS (same 15 as scout_v9) ──────────────────────

def detect_pain_points(html):
    pains = []
    html_lower = html.lower()
    
    if not re.search(r'<meta[^>]*viewport', html_lower):
        pains.append("not mobile responsive")
    if re.search(r'bootstrap[/\-]?2[.\d]', html_lower):
        pains.append("outdated UI — Bootstrap 2")
    if re.search(r'jquery[/\-]?1[.\d]', html_lower) and not re.search(r'jquery[/\-]?[23]', html_lower):
        pains.append("outdated jQuery 1.x")
    inline = len(re.findall(r'style="[^"]*"', html))
    tags = len(re.findall(r'<[a-z][^>]*>', html_lower))
    if tags > 0 and (inline / max(tags, 1)) > 0.1:
        pains.append("backdated UI — heavy inline styles")
    if not re.search(r'(call|phone|contact|book|schedule|reserve|order)', html_lower):
        pains.append("no clear call-to-action")
    if not re.search(r'(google-analytics|gtag|analytics.js|mixpanel|segment)', html_lower):
        pains.append("no analytics setup")
    if not re.search(r'(livechat|intercom|zendesk|drift|hubspot|crisp)', html_lower):
        pains.append("no live chat")
    text = re.sub(r'<[^>]+>', ' ', html)
    if len(text.split()) < 200:
        pains.append("thin content")
    if not re.search(r'/(blog|news|articles|resources)/', html_lower):
        pains.append("no blog")
    if not re.search(r'(testimonial|review|star rating)', html_lower):
        pains.append("no testimonials")
    if not re.search(r'<form[^>]*>', html_lower):
        pains.append("no contact form")
    if not re.search(r'privacy', html_lower):
        pains.append("no privacy policy")
    if re.search(r'(comic sans|times new roman|courier new)', html_lower):
        pains.append("outdated fonts")
    
    return pains

# ── JUDGE v4 (same as working scout_v9) ─────────────────────

def judge_lead(company, website, email, pain_points):
    if not email:
        return 0, False, ["no email"]
    if not pain_points:
        return 0, False, ["no pain points"]
    
    score = 0
    reasons = []
    
    # Business domain email
    if not any(email.endswith('@' + d) for d in ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'aol.com']):
        score += 3
        reasons.append("business domain")
    else:
        score += 1
        reasons.append("free domain ok")
    
    # Pain points
    score += min(len(pain_points) * 2, 6)
    reasons.append(f"{len(pain_points)} pains")
    
    # Has website
    if website:
        score += 2
        reasons.append("has site")
    
    # Company name real
    if company and len(company) > 2:
        score += 1
        reasons.append("valid name")
    
    # Reject fakes
    local = email.split('@')[0]
    if any(p in email for p in ['johndoe', 'john@smith', 'test@admin', 'test@example']):
        return 0, False, ["fake email"]
    
    is_qualified = score >= 7
    return score, is_qualified, reasons

# ── DOMAIN GENERATION (same as scout_v9) ────────────────────

def generate_domains():
    domains = set()
    for niche in NICHES:
        for tld in TLDS:
            domains.add(f"{niche}{tld}")
            domains.add(f"{niche}pro{tld}")
        for prefix in PREFIXES:
            for tld in TLDS[:3]:
                domains.add(f"{prefix}{niche}{tld}")
        for suffix in SUFFIXES:
            for tld in TLDS[:3]:
                domains.add(f"{niche}{suffix}{tld}")
    return list(domains)

# ── MAIN ───────────────────────────────────────────────────

def run_daily_scout(target=TARGET_LEADS_PER_DAY):
    log(f"=== SCOUT v10 starting | target: {target} ===")
    
    from crm import get_crm
    crm = get_crm()
    
    state = load_state()
    state["runs"] = state.get("runs", 0) + 1
    
    # Check if already hit target today
    new_leads_today = [l for l in crm.get_new_leads() if l.get("Status") == "New"]
    if len(new_leads_today) >= target:
        log(f"Already have {len(new_leads_today)} new leads. Done.")
        return len(new_leads_today)
    
    needed = target - len(new_leads_today)
    log(f"Need {needed} more leads")
    
    domains = generate_domains()
    log(f"Generated {len(domains)} domains")
    
    found = 0
    checked = 0
    dns_ok = 0
    http_ok = 0
    email_found = 0
    
    batch_to_save = []
    
    for domain in domains:
        if found >= needed:
            break
        
        checked += 1
        
        if not dns_resolves(domain):
            continue
        dns_ok += 1
        
        for scheme in ["https", "http"]:
            url = f"{scheme}://{domain}"
            status, html, title = fetch_page(url)
            
            if status == 200 and html:
                http_ok += 1
                pains = detect_pain_points(html)
                emails = extract_emails(html, url)
                email = emails[0] if emails else ""
                company = title[:80] if title else domain.split('.')[0].replace('-', ' ').title()
                
                score, qualified, reasons = judge_lead(company, url, email, pains)
                
                if qualified and email:
                    email_found += 1
                    batch_to_save.append({
                        "Company Name": company,
                        "Website (if have)": url,
                        "Owner Name": "",
                        "Owner Email": email,
                        "Linkedin": "",
                        "Pain Point": ", ".join(pains),
                        "Email sent date": "",
                        "Follow up 01": "",
                        "Follow up 02": "",
                        "Status": "New",
                    })
                    found += 1
                    log(f"  ✓ [{found}/{needed}] {company[:40]} | {email[:35]} | {score}p | {', '.join(pains[:2])}")
                
                break  # Don't retry HTTP if HTTPS worked
        
        if checked % 50 == 0:
            log(f"  Progress: {checked} checked, {dns_ok} DNS, {http_ok} HTTP, {email_found} emails, {found} qualified")
        
        time.sleep(0.3)
    
    # Batch save to CRM
    if batch_to_save:
        try:
            added, skipped = crm.add_leads_batch(batch_to_save)
            log(f"Saved {added} leads ({skipped} duplicates)")
            state["total_leads_found"] = state.get("total_leads_found", 0) + added
        except Exception as e:
            log(f"Batch save error: {e}, falling back to individual saves")
            added = 0
            for lead_data in batch_to_save:
                try:
                    if crm.add_lead(lead_data):
                        added += 1
                except:
                    pass
            log(f"Saved {added} leads individually")
    
    save_state(state)
    log(f"=== SCOUT done: {found} leads from {checked} domains | DNS:{dns_ok} HTTP:{http_ok} Email:{email_found} ===")
    return found


if __name__ == "__main__":
    import sys
    sys.path.insert(0, NANOSOFT_DIR)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        run_daily_scout(target=int(sys.argv[2]) if len(sys.argv) > 2 else 30)
    else:
        while True:
            run_daily_scout()
            log("Sleeping 1 hour...")
            time.sleep(3600)
