"""
NanoSoft Lead Email Enricher
Re-scrapes existing Drafted leads to find better contact emails.
Many SMB websites hide emails behind contact pages.
"""
import json, os, re, sys, time, urllib.request, urllib.error, ssl
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
LOG_FILE = os.path.join(NANOSOFT_DIR, "enricher.log")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

sys.path.insert(0, NANOSOFT_DIR)

SKIP_DOMAINS = {
    'gmail.com','yahoo.com','hotmail.com','outlook.com','aol.com','example.com',
    'test.com','godaddy.com','afternic.com','sentry.io','googleapis.com','cloudflare.com',
    'amazonaws.com','herokuapp.com','vercel.app','netlify.app','mailgun.org','sendgrid.net',
    'stripe.com','gkg.net','whois.gkg.net','sedo.com','facebook.com','twitter.com',
    'linkedin.com','medium.com','youtube.com','wikipedia.org','github.com',
}
BAD_PATS = [
    r'^info@',r'^contact@',r'^hello@',r'^support@',r'^admin@',r'^sales@',
    r'^marketing@',r'^office@',r'^press@',r'^leadsync@',r'^promote@',
    r'^information@',r'^jobs@',r'^careers@',r'^noreply@',r'^no-reply@',
    r'^webmaster@',r'^postmaster@',r'^abuse@',r'^hr@',r'^hr\.',
    r'\.(js|css|png|jpg|gif|svg|json|ico|webp)@',
]

def log(msg):
    ts = datetime.now(BD_TZ).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, 'a') as f:
            f.write(line + "\n")
    except:
        pass

def fetch(url, timeout=8):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'text/html'})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return r.status, r.read().decode('utf-8', errors='ignore')
    except:
        return 0, ''

def good_emails(html, site_domain):
    found = []
    seen = set()
    for m in re.finditer(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', html):
        e = m.group().lower()
        ed = e.split('@')[1] if '@' in e else ''
        if ed in SKIP_DOMAINS:
            continue
        local = e.split('@')[0]
        if any(re.match(p, e) for p in BAD_PATS):
            continue
        if re.match(r'^[0-9a-f]{8,}$', local):
            continue
        if len(local) > 50:
            continue
        if e in seen:
            continue
        seen.add(e)
        if ed == site_domain:
            found.insert(0, e)  # Prefer same-domain emails
        else:
            found.append(e)
    return found[:5]

def enrich_lead(lead):
    """Re-scrape a lead's website for better contact email."""
    website = lead.get('Website (if have)', '').strip()
    current_email = lead.get('Owner Email', '').strip()
    company = lead.get('Company Name', '')
    domain = re.sub(r'^https?://(www\.)?', '', website).split('/')[0]

    # Skip if current email looks good (owner-like)
    local_part = current_email.split('@')[0] if '@' in current_email else ''
    is_good_now = (
        current_email
        and not any(current_email.lower().startswith(p) for p in ['info','contact','hello','support','admin','sales','example','filler','user@','link@'])
        and not any(d in current_email.lower() for d in ['godaddy.com','afternic','js.','png','gif','@1.','msn.com','hotmail','gmail.com','yahoo.com','outlook'])
        and len(local_part) >= 2
    )
    if is_good_now:
        return None  # Already good

    # Deep-scrape for better emails
    all_emails = []
    seen = set()

    # Homepage
    status, html = fetch(website)
    if html:
        for e in good_emails(html, domain):
            if e not in seen:
                seen.add(e)
                all_emails.append(e)

    # Contact pages
    for path in ['/contact', '/contact-us', '/about', '/about-us', '/team',
                 '/contact.html', '/contact-us.html', '/about.html']:
        if len(all_emails) >= 3:
            break
        cstatus, chtml = fetch(website.rstrip('/') + path)
        if chtml and len(chtml) > 200:
            for e in good_emails(chtml, domain):
                if e not in seen:
                    seen.add(e)
                    all_emails.append(e)

    time.sleep(0.2)

    if all_emails:
        new_email = all_emails[0]
        if new_email.lower() != current_email.lower():
            return new_email
    return None


def run_enrichment():
    from crm import get_crm
    crm = get_crm()
    drafted = crm.get_leads_by_status('Drafted')
    
    log(f"[ENRICH] Processing {len(drafted)} Drafted leads...")
    
    improved = 0
    already_good = 0
    no_better = 0

    for i, lead in enumerate(drafted):
        company = lead.get('Company Name', '?')
        current = lead.get('Owner Email', '')
        
        new_email = enrich_lead(lead)
        
        if new_email:
            try:
                crm.update_lead(company, {'Owner Email': new_email})
                improved += 1
                log(f"  [{i+1}] {company[:40]}: {current[:25]} -> {new_email}")
            except Exception as e:
                log(f"  [{i+1}] UPDATE FAILED: {company[:40]} | {e}")
        elif current and not current.startswith(('info','contact','hello')) and 'gmail' not in current:
            already_good += 1
        else:
            no_better += 1

    log(f"\n[DONE] Improved: {improved} | Already good: {already_good} | No better: {no_better}")
    return improved


if __name__ == "__main__":
    run_enrichment()
