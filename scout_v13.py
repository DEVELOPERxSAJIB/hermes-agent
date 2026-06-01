#!/usr/bin/env python3
"""
NanoSoft SCOUT v13 — Local Business Lead Discovery
Playwright email scraping with crash-proof error handling.
"""
import json, os, re, sys, time, urllib.request, urllib.error, ssl, urllib.parse
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
LOG_FILE = os.path.join(NANOSOFT_DIR, "scout_v13.log")
STATE_FILE = os.path.join(NANOSOFT_DIR, "scout_v13_state.json")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

sys.path.insert(0, NANOSOFT_DIR)

SKIP_E_DOMAINS = {
    'gmail.com','yahoo.com','hotmail.com','outlook.com','aol.com','mail.com',
    'protonmail.com','icloud.com','live.com','msn.com','example.com','test.com',
    'sentry.io','github.com','twitter.com','facebook.com','linkedin.com','medium.com',
    'youtube.com','wikipedia.org','amazonaws.com','cloudflare.com','googleapis.com',
    'herokuapp.com','vercel.app','netlify.app','mailgun.org','sendgrid.net',
    'stripe.com','gkg.net','whois.gkg.net','godaddy.com','afternic.com','sedo.com',
    'google.com','googlemail.com','googlegroups.com',
}
BAD_E_PATS = [
    r'^info@',r'^contact@',r'^hello@',r'^support@',r'^admin@',r'^sales@',
    r'^marketing@',r'^office@',r'^press@',r'^leadsync@',r'^promote@',
    r'^information@',r'^jobs@',r'^careers@',r'^noreply@',r'^no-reply@',
    r'^webmaster@',r'^postmaster@',r'^abuse@',r'^hr@',r'^hr\.',
    r'\.(js|css|png|jpg|gif|svg|json|ico|webp)@',
    r'@.*\.(tk|ml|ga|cf|gq)$',
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

def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except:
        return {"runs":0,"total_leads":0,"seen_domains":[],"seen_emails":[]}

def save_state(state):
    for key in ["seen_domains","seen_emails"]:
        if len(state.get(key,[])) > 10000:
            state[key] = state[key][-5000:]
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def clean_domain(url):
    return re.sub(r'^https?://(www\.)?','',url).split('/')[0].split('?')[0].lower().strip()

def extract_emails_from_html(html, site_domain):
    found = []
    seen = set()
    for m in re.finditer(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', html):
        e = m.group().lower()
        ed = e.split('@')[1] if '@' in e else ''
        local = e.split('@')[0]
        if ed in SKIP_E_DOMAINS: continue
        if any(re.match(p, e) for p in BAD_E_PATS): continue
        if re.match(r'^[0-9a-f]{8,}$', local): continue
        if len(local) > 50: continue
        if e in seen: continue
        seen.add(e)
        if ed == site_domain: found.insert(0, e)
        else: found.append(e)
    for m in re.finditer(r'mailto:([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})', html):
        e = m.group(1).lower()
        if e not in seen:
            seen.add(e)
            ed = e.split('@')[1] if '@' in e else ''
            if ed == site_domain: found.insert(0, e)
            else: found.append(e)
    return found[:10]


def check_website_playwright(url, scrape_contact_pages=True):
    """Use Playwright to render JS. Crash-proof: per-page timeouts, no fatal errors."""
    from playwright.sync_api import sync_playwright

    result = {
        'emails': [], 'title': '', 'location': '', 'pain_points': [],
        'contact_form': False, 'booking_url': False, 'has_ssl': url.startswith('https'),
        'content_length': 0, 'mobile': False,
    }

    site_domain = clean_domain(url)
    all_html = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
            )
            context = browser.new_context(
                user_agent=UA,
                viewport={'width': 1280, 'height': 720},
            )

            pages_to_check = [('', url)]
            if scrape_contact_pages:
                for path in ['/contact', '/contact-us', '/about']:
                    pages_to_check.append((path, url.rstrip('/') + path))

            for path, page_url in pages_to_check:
                page = None
                try:
                    page = context.new_page()
                    page.goto(page_url, timeout=20000, wait_until='domcontentloaded')
                    page.wait_for_timeout(1500)
                    html = page.content()
                    all_html.append(html)

                    if not result['title'] and path == '':
                        title_m = re.search(r'<title[^>]*>(.*?)</title>', html, re.I|re.S)
                        if title_m:
                            result['title'] = re.sub(r'<[^>]+>','',title_m.group(1)).strip()
                            result['title'] = re.sub(r'\s*[|\-–—·•]\s*.+$','',result['title']).strip()[:80]

                    if not result['location']:
                        loc_patterns = [
                            r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)*,\s*[A-Z]{2})\b',
                            r'(?:located?\s+in|serving|based\s+in)\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)',
                        ]
                        for lp in loc_patterns:
                            lm = re.search(lp, html[:3000])
                            if lm:
                                result['location'] = lm.group(1)
                                break

                    text = re.sub(r'<[^>]+>',' ',html)
                    result['content_length'] += len(text.split())
                    if re.search(r'<meta[^>]*viewport', html.lower()):
                        result['mobile'] = True

                    try:
                        forms = page.query_selector_all('form')
                        for f in forms:
                            try:
                                fh = f.inner_html()
                                if fh and any(k in fh.lower() for k in ['email','name','message','contact','inquiry']):
                                    result['contact_form'] = True
                            except:
                                pass
                    except:
                        pass

                    try:
                        links = page.query_selector_all('a')
                        for link in links:
                            try:
                                href = link.get_attribute('href') or ''
                                text = (link.inner_text() or '').lower()
                                if any(k in href.lower() or k in text for k in ['book','schedule','appointment','calendly','square','mindbody','acuity']):
                                    result['booking_url'] = True
                            except:
                                pass
                    except:
                        pass

                except Exception as e:
                    log(f"  Page error {path}: {type(e).__name__}")
                finally:
                    if page:
                        try:
                            page.close()
                        except:
                            pass

            try:
                browser.close()
            except:
                pass

    except Exception as e:
        log(f"  Playwright error: {e}")

    # Extract all emails from all HTML we got
    seen_emails = set()
    for html in all_html:
        emails = extract_emails_from_html(html, site_domain)
        for e in emails:
            if e not in seen_emails:
                seen_emails.add(e)
                result['emails'].append(e)
    result['emails'] = result['emails'][:5]

    combined = ' '.join(all_html) if all_html else ''
    result['pain_points'] = detect_pain_points(combined)

    return result


def detect_pain_points(html):
    pains = []
    h = html.lower()[:10000]
    if not re.search(r'<meta[^>]*viewport', h):
        pains.append(("not mobile responsive", "high", "Revenue leakage — mobile visitors bounce"))
    head_section = h.split('<head>')[1][:1000] if '<head>' in h else h[:2000]
    if not re.search(r'https:', head_section):
        pains.append(("no SSL/security", "medium", "Trust issue — browsers flag as Not Secure"))
    if not re.search(r'google-analytics|gtag|analytics\.js|googletagmanager|facebook\.net|fbevents', h):
        pains.append(("no analytics", "high", "Flying blind — no idea what marketing works"))
    if not re.search(r'livechat|intercom|zendesk|drift|hubspot|crisp|olark|tawk|liveagent', h):
        pains.append(("no live chat", "medium", "Losing after-hours and instant-gratification customers"))
    text = re.sub(r'<[^>]+>', ' ', h)
    if len(text.split()) < 200:
        pains.append(("thin content", "medium", "Google can't rank thin pages"))
    if not re.search(r'/(blog|news|articles|resources|insights)/', h):
        pains.append(("no blog", "low", "Missing free organic traffic from Google"))
    if not re.search(r'testimonial|review|google\s+rating|⭐|star\s+rating|fivestar', h):
        pains.append(("no social proof", "medium", "Customers go to competitors with reviews"))
    if not re.search(r'<form[^>]*>', h):
        pains.append(("no contact form", "low", "Hard for potential customers to reach you"))
    if re.search(r'hiring|we\s+are\s+hiring|join\s+our\s+team|career|now\s+employing|staff\s+needed', h):
        pains.append(("hiring actively", "opportunity", "Growing business = budget and urgency"))
    if not re.search(r'booking|schedule|appointment|online\s+order|reserve', h):
        pains.append(("no online booking", "high", "Manual booking = lost customers wanting instant confirmation"))
    return pains[:5]


def search_ddg(niche, city, country="US"):
    """Search DuckDuckGo HTML for local business URLs."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    city_state = {
        "Dallas": "Dallas, TX", "Houston": "Houston, TX",
        "Chicago": "Chicago, IL", "Phoenix": "Phoenix, AZ",
        "Atlanta": "Atlanta, GA", "London": "London, UK",
        "Manchester": "Manchester, UK", "Birmingham": "Birmingham, UK",
    }.get(city, city)

    queries = [
        f'"{niche}" "{city_state}"',
        f'{niche} {city} website',
        f'"{niche}" near {city}',
    ]

    all_urls = []
    skip_domains = {
        'yelp.com','zocdoc.com','healthgrades.com','vitals.com','webmd.com',
        'opencare.com','facebook.com','google.com','amazon.com','wikipedia.org',
        'duckduckgo.com','bing.com','yellowpages.com','bbb.org','manta.com',
        'chamberofcommerce','angihomeservice','thumbtack.com','homestars',
        'ratemds.com','docfinder','1800dentist','mesothelioma','lawyers.com',
        'directory.dmagazine',
    }

    for q in queries:
        data = urllib.parse.urlencode({'q': q}).encode()
        req = urllib.request.Request(
            'https://html.duckduckgo.com/html/',
            data=data,
            headers={'User-Agent': UA, 'Accept': 'text/html', 'Content-Type': 'application/x-www-form-urlencoded'},
        )
        try:
            resp = urllib.request.urlopen(req, timeout=15, context=ctx)
            html = resp.read().decode('utf-8', errors='ignore')
        except:
            continue

        # DDG now returns direct links (no more uddg= redirect)
        links = re.findall(r'href="(https?://(?!duckduckgo)[^"]+)"', html)
        titles_raw = re.findall(r'<a[^>]*class="result__a"[^>]*>(.*?)</a>', html, re.DOTALL)

        # Fallback: old DDG redirect format
        if not links:
            links = re.findall(r'href="(//duckduckgo\.com/l/\?[^\"]+)"', html)
            titles_raw = []

        seen_domains = set()
        for i, link in enumerate(links):
            uddg = re.search(r'uddg=([^&]+)', link)
            if uddg:
                real_url = urllib.parse.unquote(uddg.group(1))
            else:
                real_url = link
            domain = clean_domain(real_url)
            if domain in skip_domains or domain in seen_domains:
                continue
            seen_domains.add(domain)
            title = ''
            if i < len(titles_raw):
                title = re.sub(r'<[^>]+>', '', titles_raw[i]).strip()[:80]
            all_urls.append({'url': real_url, 'domain': domain, 'title': title, 'source': 'ddg'})

        time.sleep(1)

    return all_urls[:30]


def scout_niche(niche, city, target=30, country="US"):
    """Main scouting function."""
    log(f"\n{'='*60}")
    log(f"[SCOUT] {niche} in {city}, {country} | Target: {target}")
    log(f"{'='*60}")

    from crm import get_crm
    crm = get_crm()
    state = load_state()

    existing = crm.get_all_leads()
    existing_domains = {clean_domain(l.get('Website','')) for l in existing}
    existing_emails = {str(l.get('Owner Email','')).lower() for l in existing if l.get('Owner Email')}

    log(f"[SCOUT] Existing: {len(existing)} leads, {len(existing_domains)} domains")

    raw_urls = search_ddg(niche, city, country)
    log(f"[SCOUT] Found {len(raw_urls)} raw URLs from search")

    qualified = []
    checked = no_email = parked = dup = fail = 0

    for biz in raw_urls:
        if len(qualified) >= target:
            break

        domain = biz['domain']
        url = biz['url']

        if domain in existing_domains or domain in state.get('seen_domains',[]):
            dup += 1
            continue

        checked += 1
        log(f"  [{checked}] Checking {domain}...")

        try:
            info = check_website_playwright(url, scrape_contact_pages=True)
        except Exception as e:
            log(f"    FAIL: {e}")
            fail += 1
            continue

        if not info['title'] or any(x in info['title'].lower() for x in ['for sale','domain','parking','godaddy']):
            parked += 1
            state.setdefault('seen_domains',[]).append(domain)
            continue

        if not info['emails']:
            no_email += 1
            state.setdefault('seen_domains',[]).append(domain)
            continue

        email = info['emails'][0]
        if email.lower() in existing_emails or email.lower() in state.get('seen_emails',[]):
            dup += 1
            continue

        title = info['title'] or biz['title'] or domain.split('.')[0].replace('-',' ').title()

        pain_descriptions = []
        severity = 'low'
        revenue_impact = 'medium'
        automation_potential = 'medium'
        outreach_angle = ''
        suggested_solution = ''

        for pain, sev, impact in info['pain_points']:
            pain_descriptions.append(pain)
            if sev == 'high':
                severity = 'high'
                revenue_impact = 'high'

        pain_str = ', '.join(pain_descriptions[:4])

        if pain_descriptions:
            top = pain_descriptions[0]
            if 'mobile' in top:
                outreach_angle = "Mobile experience losing visitors"
                suggested_solution = "Responsive redesign + mobile-first CTA"
                automation_potential = "high"
            elif 'analytics' in top:
                outreach_angle = "No visibility into what marketing works"
                suggested_solution = "Full analytics setup + conversion tracking"
            elif 'live chat' in top:
                outreach_angle = "Losing after-hours leads to competitors"
                suggested_solution = "Live chat integration + automated booking"
            elif 'booking' in top:
                outreach_angle = "Manual booking process losing customers"
                suggested_solution = "Online booking system + automated reminders"
                automation_potential = "high"
            elif 'ssl' in top:
                outreach_angle = "Security warning scares away visitors"
                suggested_solution = "SSL certificate + security audit"
            elif 'social proof' in top:
                outreach_angle = "No reviews visible, losing to competitors"
                suggested_solution = "Review display integration + review generation system"
            elif 'hiring' in top:
                outreach_angle = "Growing team means operational scaling needed"
                suggested_solution = "Automation to support growth without adding headcount"
                automation_potential = "high"
            else:
                outreach_angle = f"Website issues: {top}"
                suggested_solution = "Modern website redesign focused on conversions"

        lead = {
            'Company Name': title[:80],
            'Website': url,
            'Owner Name': '',
            'Owner Email': email,
            'Linkedin': '',
            'Pain Point': pain_str,
            'Email sent date': '',
            'Follow up 01': '',
            'Follow up 02': '',
            'Status': 'New',
            'Judge Score': '',
            'Severity': severity,
            'Location': info.get('location', city),
            'Source': f"scout:{niche}:{city}",
            'Revenue Impact': revenue_impact,
            'Automation Potential': automation_potential,
            'Outreach Angle': outreach_angle,
            'Suggested Solution': suggested_solution,
            'Contact Form URL': url + '/contact' if info.get('contact_form') else '',
            'Booking URL': 'yes' if info.get('booking_url') else '',
        }

        qualified.append(lead)
        existing_domains.add(domain)
        existing_emails.add(email.lower())
        state.setdefault('seen_domains',[]).append(domain)
        state.setdefault('seen_emails',[]).append(email.lower())

        log(f"    OK {title[:40]} | {email} | severity={severity} | {pain_str[:50]}")
        time.sleep(0.5)

    if qualified:
        added, skipped = crm.add_leads_batch(qualified)
        log(f"[SCOUT] Saved {added} leads to CRM")
        state['total_leads'] = state.get('total_leads', 0) + added
    else:
        added = 0

    state['runs'] = state.get('runs', 0) + 1
    save_state(state)

    log(f"[SCOUT] Done: {added}/{target} qualified")
    log(f"  Checked: {checked} | No email: {no_email} | Parked: {parked} | Dup: {dup} | Fail: {fail}")
    return qualified


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--niche', default='dentist')
    parser.add_argument('--city', default='Dallas')
    parser.add_argument('--target', type=int, default=30)
    parser.add_argument('--country', default='US')
    args = parser.parse_args()

    leads = scout_niche(args.niche, args.city, args.target, args.country)
    print(f"\nResult: {len(leads)} qualified leads")
