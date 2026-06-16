"""
NanoSoft SCOUT v11 — Local Business Lead Discovery
Searches DuckDuckGo HTML for real local businesses.
Verifies websites, extracts contact emails via deep scraping.
"""
import json, os, re, sys, time, socket, urllib.request, urllib.error, ssl, urllib.parse
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
LOG_FILE = os.path.join(NANOSOFT_DIR, "scout_v11.log")
STATE_FILE = os.path.join(NANOSOFT_DIR, "scout_v11_state.json")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

sys.path.insert(0, NANOSOFT_DIR)

SKIP_E_DOMAINS = {
    'gmail.com','yahoo.com','hotmail.com','outlook.com','aol.com','mail.com',
    'protonmail.com','icloud.com','live.com','msn.com','example.com','test.com',
    'sentry.io','github.com','twitter.com','facebook.com','linkedin.com','medium.com',
    'youtube.com','wikipedia.org','amazonaws.com','cloudflare.com','googleapis.com',
    'herokuapp.com','vercel.app','netlify.app','mailgun.org','sendgrid.net',
    'stripe.com','gkg.net','whois.gkg.net','godaddy.com','afternic.com','sedo.com',
}
BAD_E_PATS = [
    r'^info@',r'^contact@',r'^hello@',r'^support@',r'^admin@',r'^sales@',
    r'^marketing@',r'^office@',r'^press@',r'^leadsync@',r'^promote@',
    r'^information@',r'^jobs@',r'^careers@',r'^noreply@',r'^no-reply@',
    r'^webmaster@',r'^postmaster@',r'^abuse@',r'^hr\.',
    r'\.(js|css|png|jpg|gif|svg|json|ico|webp)@',
]
PARKED = ['domain for sale','buy this domain','godaddy','afternic','sedo','parked','for sale','domain parking']


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
        return {"runs":0,"total_leads":0,"seen_domains":[]}

def save_state(state):
    if len(state.get("seen_domains",[])) > 10000:
        state["seen_domains"] = state["seen_domains"][-5000:]
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def fetch(url, timeout=10):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'text/html'})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return r.status, r.read().decode('utf-8', errors='ignore')
    except:
        return 0, ''

def clean_domain(url):
    return re.sub(r'^https?://(www\.)?','',url).split('/')[0].split('?')[0].lower().strip()

def is_parked(html):
    h = html.lower()[:3000]
    return any(p in h for p in PARKED)

def good_emails(html, site_domain):
    found = set()
    for m in re.finditer(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', html):
        e = m.group().lower()
        ed = e.split('@')[1] if '@' in e else ''
        if ed in SKIP_E_DOMAINS:
            continue
        if any(re.match(p, e) for p in BAD_E_PATS):
            continue
        if re.match(r'^[0-9a-f]{8,}$', e.split('@')[0]):
            continue
        if ed == site_domain or ed.endswith('.' + site_domain):
            found.insert(0, e)  # domain-match first
        else:
            found.add(e)
    return list(found)[:5]

def contact_emails(website, domain):
    """Scrape homepage + contact pages for emails."""
    all_emails = []
    seen = set()
    pages = ['', '/contact', '/contact-us', '/about', '/about-us', '/team', '/staff',
             '/contact.html', '/contact-us.html', '/about.html']
    for path in pages:
        url = website.rstrip('/') + path
        status, html = fetch(url, timeout=8)
        if not html or len(html) < 200:
            continue
        emails = good_emails(html, domain)
        for e in emails:
            if e not in seen:
                seen.add(e)
                all_emails.append(e)
        if len(all_emails) >= 3:
            break
        time.sleep(0.3)
    return all_emails

def detect_pains(html):
    p = []
    h = html.lower()
    if not re.search(r'<meta[^>]*viewport', h): p.append("not mobile responsive")
    if not re.search(r'(call|phone|contact|book|schedule)', h): p.append("no clear call-to-action")
    if not re.search(r'(google-analytics|gtag|analytics\.js|googletagmanager)', h): p.append("no analytics setup")
    if not re.search(r'(livechat|intercom|zendesk|drift|hubspot|crisp)', h): p.append("no live chat")
    t = re.sub(r'<[^>]+>', ' ', h)
    if len(t.split()) < 200: p.append("thin content")
    if not re.search(r'/(bl