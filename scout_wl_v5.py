#!/usr/bin/env python3
"""
NanoSoft SCOUT-WL v5 — Fast, lean, single-request-per-domain scraper
Fixes: combines all scraping into 1 HTTP call, better domain filtering,
       CRM dedup in Phase 1, relaxed email extraction
"""
import json, os, re, sys, time, csv, subprocess
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request, ProxyHandler, build_opener
from urllib.error import URLError, HTTPError

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"

# Use proxy if available (Oracle Cloud IP blacklisted for many sites)
PROXY_URL = "http://127.0.0.1:8118"  # privoxy/tinyproxy
HAS_PROXY = False
try:
    opener = build_opener(ProxyHandler({'https': PROXY_URL, 'http': PROXY_URL}))
    opener.open("https://httpbin.org/ip", timeout=5)
    HAS_PROXY = True
except:
    pass

QUERIES = [
    # Tier 1: Agencies with explicit WL/partner pages (highest intent)
    'site:.com "white label" "web development" agency',
    'site:.com "partner program" web development agency',
    'site:.io "white label" development partner',
    'site:.co "white label" software agency',
    'inurl:partners web development agency',
    'inurl:partnership software development agency',
    '"become a partner" web development agency',
    '"partner with us" software development agency',
    '"referral partner" web development agency',
    '"reseller program" software development agency',
    # Tier 2: Agencies showing capacity/staffing signals
    '"we are hiring" web development agency',
    '"join our team" software development agency',
    '"we are growing" web development agency',
    '"scaling our team" software agency',
    '"new projects welcome" web development agency',
    '"accepting new clients" software development agency',
    '"book a call" web development agency',
    '"get a quote" software development agency',
    '"free consultation" web development agency',
    '"let\'s talk" software development agency',
    # Tier 3: Agency directories and lists
    '"top web development agencies" 2025 2026',
    '"best software development agencies" usa uk',
    '"top mobile app development agencies"',
    '"top saas development agencies"',
    '"top ecommerce development agencies"',
    '"top wordpress development agencies"',
    '"top shopify development agencies"',
    '"top react development agencies"',
    '"top nodejs development agencies"',
    '"top python development agencies"',
    # Tier 4: Specific tech + country combos
    '"white label" react development agency usa',
    '"white label" node.js development agency uk',
    '"white label" python development agency canada',
    '"white label" shopify agency australia',
    '"white label" wordpress agency india',
    '"white label" mobile app agency philippines',
    '"white label" saas development agency germany',
    '"white label" web development agency netherlands',
    '"white label" software agency sweden',
    '"white label" development agency poland',
    # Tier 5: Staff augmentation / team extension
    '"staff augmentation" agency partner usa',
    '"dedicated team" agency partner uk',
    '"team extension" agency partner canada',
    '"nearshore development" agency partner',
    '"offshore development" agency partner',
    '"outsourced development" agency partner',
    '"development partner" agency program',
    '"technology partner" agency program',
    '"development partner" for agencies',
    '"software partner" for agencies',
    # Tier 6: Pain-point based (agencies that need help)
    'agency "need more developers"',
    'agency "hiring developers"',
    'agency "developer shortage"',
    'agency "capacity issues"',
    'agency "overflow work"',
    'agency "can\'t handle all projects"',
    'agency "looking for development partner"',
    'agency "need coding help"',
    'agency "need technical partner"',
    'agency "outsource development"',
    # Tier 7: Clutch/GoodFirms profiles (agencies list themselves)
    'site:clutch.co "web development" agency "contact"',
    'site:goodfirms.co "software development" agency',
    'site:designrush.com "web development" agency',
    'site:sortlist.com "software development" agency',
    '"clutch" "top developer" agency profile',
    '"goodfirms" "top developer" agency',
    # Tier 8: LinkedIn company pages
    'site:linkedin.com/company "web development agency"',
    'site:linkedin.com/company "software development agency"',
    'site:linkedin.com/company "mobile app development"',
    'site:linkedin.com/company "digital agency" "development"',
    # Tier 9: Agency blogs/content (shows they're active)
    '"web development blog" agency',
    '"software development insights" agency',
    '"tech blog" web development agency',
    '"development tips" agency blog',
    '"our work" web development agency case study',
    '"case study" web development agency',
    '"portfolio" web development agency',
    '"recent projects" software development agency',
    '"client testimonials" web development agency',
    '"what we do" software development agency',
    # Tier 10: Geographic expansion
    'web development agency "united states" "contact"',
    'web development agency "united kingdom" "contact"',
    'web development agency "canada" "contact"',
    'web development agency "australia" "contact"',
    'web development agency "germany" "contact"',
    'web development agency "netherlands" "contact"',
    'web development agency "sweden" "contact"',
    'web development agency "poland" "contact"',
    'web development agency "ukraine" "contact"',
    'web development agency "india" "contact"',
]

SKIP_DOMAINS = [
    'wikipedia', 'linkedin', 'glassdoor', 'indeed', 'fiverr', 'upwork',
    'facebook', 'twitter', 'youtube', 'instagram', 'pinterest', 'reddit',
    'quora', 'medium', 'amazon', 'apple', 'google', 'microsoft', 'github',
    'stackoverflow', 'crunchbase', 'bloomberg', 'reuters', 'bbc', 'cnn',
    'forbes', 'inc.com', 'entrepreneur.com', 'mashable', 'techcrunch',
    'wired', 'theverge', 'gizmodo', 'arstechnica', 'smashingmagazine',
    'css-tricks', 'sitepoint', 'tutsplus', 'codecademy', 'udemy', 'coursera',
    'clutch.co', 'goodfirms', 'designrush', 'sortlist',
    'duckduckgo', 'bing.com', 'yahoo.com',
    'dribbble', 'behance', 'awwwards', 'cssdesignawards',
    'agencies.', '.gov', '.edu',
    # Non-agency sites that pollute results
    'jotform', 'notion.so', 'figma.com', 'canva.com', 'shopify.com',
    'wordpress.com', 'wix.com', 'squarespace.com', 'webflow.com',
    'hubspot.com', 'mailchimp.com', 'zoho.com', 'salesforce.com',
    'atlassian.com', 'slack.com', 'zoom.us', 'trello.com',
    'asana.com', 'monday.com', 'clickup.com', 'basecamp.com',
]

# Known non-agency TLD patterns
BAD_DOMAIN_PATTERNS = [
    r'design-hero', r'mandyweb', r'getglow', r'viralchilly',
    r'peoplemanaging', r'singlegrain', r'octaneai', r'admitad',
    r'siptrunk', r'wowww', r'emarcom', r'onlinemark',
    r'swovo', r'appmysite', r'shieldapps', r'orangemantra',
]

def log(msg):
    ts = datetime.now(BD_TZ).strftime("%Y-%m-%d %H:%M:%S")
    print(f'[{ts}] [SCOUT] {msg}', flush=True)

def ddg_search(query, max_results=8):
    """Search using ddgs CLI."""
    try:
        result = subprocess.run(
            ['ddgs', 'text', '-q', query, '-m', str(max_results)],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return []

        results = []
        current = {}
        for line in result.stdout.split('\n'):
            line = line.strip()
            if not line:
                if current.get('href'):
                    results.append(current)
                    current = {}
                continue
            if line[0].isdigit() and '. ' in line[:4]:
                if current.get('href'):
                    results.append(current)
                current = {'title': line.split('. ', 1)[1] if '. ' in line else line}
            elif line.startswith('href'):
                current['href'] = line.split(' ', 1)[1] if ' ' in line else ''
            elif line.startswith('body'):
                current['body'] = line.split(' ', 1)[1] if ' ' in line else ''
        if current.get('href'):
            results.append(current)
        return results
    except:
        return []

def extract_domain(url):
    m = re.search(r'https?://(?:www\.)?([^/]+)', url)
    return m.group(1).lower() if m else ''

def extract_company(domain):
    parts = domain.split('.')
    if len(parts) >= 2:
        name = parts[-2]
        # Skip if it's just a generic word
        if name in ['the', 'my', 'we', 'get', 'go', 'app', 'web', 'dev', 'io', 'co']:
            if len(parts) >= 3:
                name = parts[-3]
        return name.replace('-', ' ').replace('_', ' ').title()
    return domain

def should_skip(domain):
    for s in SKIP_DOMAINS:
        if s in domain:
            return True
    for pat in BAD_DOMAIN_PATTERNS:
        if re.search(pat, domain):
            return True
    return False

def smart_scrape(domain, timeout=10):
    """
    ONE request per domain. Fetch the homepage with proxy.
    Extract email + services + WL signals + country + LinkedIn from single HTML.
    Falls back to /contact page if no email on homepage.
    """
    base_url = f"https://{domain}"
    html = None

    # Try homepage first
    try:
        req = Request(base_url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        if HAS_PROXY:
            resp = opener.open(req, timeout=timeout)
        else:
            resp = urlopen(req, timeout=timeout)
        html = resp.read().decode('utf-8', errors='ignore')
    except:
        pass

    # Fallback to /contact if no email found
    email = ''
    if html:
        email = _extract_email(html, domain)

    if not email:
        try:
            contact_url = f"{base_url}/contact"
            req = Request(contact_url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
            })
            if HAS_PROXY:
                resp = opener.open(req, timeout=timeout)
            else:
                resp = urlopen(req, timeout=timeout)
            contact_html = resp.read().decode('utf-8', errors='ignore')
            if not html:
                html = contact_html
            email = _extract_email(contact_html, domain)
        except:
            pass

    if not html:
        return None  # Could not fetch at all

    text = re.sub(r'<[^>]+>', ' ', html).lower()
    text = re.sub(r'\s+', ' ', text)

    services = _extract_services(text)
    wl_signals = _extract_wl_signals(text)
    country = _extract_country(html)  # use raw HTML for case-sensitive patterns
    linkedin = _extract_linkedin(html)

    return {
        'email': email,
        'services': services,
        'wl_signals': wl_signals,
        'country': country,
        'linkedin': linkedin,
    }

def _extract_email(html, domain):
    """Extract best email from HTML, preferring the target domain."""
    # Find all emails
    emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', html)
    bad = [
        'example@', 'test@', 'noreply', 'no-reply', 'sentry', '@whois',
        'vue@3', '@scorebig', '@afternic', 'john@doe', 'feedback@',
        'user@domain', '@sentry', '@bytedance', 'webmaster@', 'postmaster@',
        'abuse@', 'security@', 'legal@', 'press@', 'investor@',
        'careers@', 'jobs@', 'hr@', 'admin@', 'info@domain',
        'name@email', 'mail@domain', 'hello@domain',
        'bootstrap', 'gsap@', 'react@', 'angular@', 'jquery@', 'webpack',
        'npm', 'cdn', 'fonts', 'woff', 'ttf', 'eot', 'svg', 'png', 'jpg',
    ]

    # Filter to domain-specific emails first
    domain_emails = []
    other_emails = []
    for e in emails:
        el = e.lower()
        if any(b in el for b in bad):
            continue
        # Skip JS library version strings
        if re.match(r'^[a-z]+@[\d.]+$', el):
            continue
        if domain in el:
            domain_emails.append(e)
        else:
            other_emails.append(e)

    # Prefer certain prefixes
    preferred = ['info@', 'hello@', 'sales@', 'contact@', 'team@', 'us@', 'hi@', 'biz@', 'enquiry@', 'enquiries@', 'business@', 'partners@', 'hello@']
    for pref in preferred:
        for e in domain_emails:
            if e.lower().startswith(pref):
                return e

    # Any domain email
    if domain_emails:
        return domain_emails[0]

    # Any other email
    if other_emails:
        return other_emails[0]

    return ''

def _extract_services(text):
    services = {
        'web development': ['web development', 'web application', 'frontend', 'backend', 'full stack', 'fullstack'],
        'mobile development': ['mobile development', 'mobile app', 'ios development', 'android development', 'react native', 'flutter', 'mobile application'],
        'AI/ML': ['artificial intelligence', 'machine learning', 'ai development', 'deep learning', 'nlp', 'computer vision'],
        'UI/UX design': ['ui design', 'ux design', 'user interface', 'product design', 'web design'],
        'cloud/DevOps': ['devops', 'cloud migration', 'aws solutions', 'azure', 'cloud infrastructure', 'kubernetes'],
        'SaaS': ['saas development', 'software as a service', 'saas application'],
        'eCommerce': ['ecommerce', 'e-commerce', 'shopify', 'magento', 'woocommerce'],
        'QA/Testing': ['qa testing', 'quality assurance', 'software testing', 'test automation'],
        'custom software': ['custom software', 'bespoke software', 'enterprise application'],
    }
    found = []
    for svc, kws in services.items():
        for kw in kws:
            if kw in text:
                found.append(svc)
                break
    return found[:5]

def _extract_wl_signals(text):
    signals = []
    checks = {
        'white label': ['white label', 'white-label', 'whitelabel'],
        'partner program': ['partner program', 'partnership program', 'agency partner', 'referral partner'],
        'staff augmentation': ['staff augmentation', 'team extension', 'dedicated team', 'dedicated developers'],
        'outsourcing': ['outsourcing', 'outsource', 'external development'],
        'reseller': ['reseller', 'resell', 'referral program'],
    }
    for signal, kws in checks.items():
        for kw in kws:
            if kw in text:
                signals.append(signal)
                break
    return signals[:4]

def _extract_country(html):
    text = re.sub(r'<[^>]+>', ' ', html)
    checks = [
        (r'\b(United States|USA|U\.S\.A\.)\b(?!.*Born)', 'USA'),
        (r'\bUnited Kingdom\b', 'UK'),
        (r'\b(Toronto|Vancouver|Montreal|Canada)\b', 'Canada'),
        (r'\b(Sydney|Melbourne|Brisbane|Australia)\b', 'Australia'),
        (r'\b(Kyiv|Lviv|Ukraine)\b', 'Ukraine'),
        (r'\b(Warsaw|Krakow|Poland)\b', 'Poland'),
        (r'\b(Bucharest|Romania)\b', 'Romania'),
    ]
    for pattern, country in checks:
        if re.search(pattern, text, re.IGNORECASE):
            return country
    return ''

def _extract_linkedin(html):
    m = re.search(r'linkedin\.com/company/([^\"\'>\s\)]+)', html)
    if m:
        return f"https://www.linkedin.com/company/{m.group(1).rstrip('/')}"
    return ''

def main():
    log(f'SCOUT-WL v5 starting... (proxy: {"ON" if HAS_PROXY else "OFF"})')

    # Load existing CRM data for dedup
    sys.path.insert(0, NANOSOFT_DIR)
    existing_names = set()
    existing_emails = set()
    existing_domains = set()
    try:
        from crm import get_crm
        crm = get_crm()
        existing = crm.get_wl_all()
        for l in existing:
            n = l.get('Company Name', '').lower().strip()
            e = l.get('Email', '').lower().strip()
            w = l.get('Website', '').lower().strip()
            if n:
                existing_names.add(n)
            if e:
                existing_emails.add(e)
            if w:
                d = extract_domain(w)
                if d:
                    existing_domains.add(d)
        log(f'CRM: {len(existing)} existing leads, {len(existing_domains)} domains')
    except Exception as e:
        log(f'CRM load error: {e}')

    # Phase 1: Search
    found_domains = {}
    for i, query in enumerate(QUERIES):
        log(f'[{i+1}/{len(QUERIES)}] {query[:55]}...')
        results = ddg_search(query, max_results=10)

        for r in results:
            url = r.get('href', '')
            domain = extract_domain(url)
            if not domain or should_skip(domain):
                continue
            if domain in existing_domains:
                continue
            if domain not in found_domains:
                company = extract_company(domain)
                # Skip if company name already in CRM
                if company.lower().strip() in existing_names:
                    continue
                found_domains[domain] = company
                log(f'  NEW: {company} ({domain})')

        time.sleep(0.5)

    log(f'Phase 1: {len(found_domains)} new unique domains (after CRM dedup)')

    # Phase 2: Scrape each domain (ONE request per domain)
    leads = []
    for i, (domain, company) in enumerate(found_domains.items()):
        log(f'[{i+1}/{len(found_domains)}] {company} ({domain})...')

        data = smart_scrape(domain)
        if data is None:
            log(f'  SKIP: could not fetch')
            continue

        email = data['email']
        services = data['services']
        wl_signals = data['wl_signals']
        country = data['country']
        linkedin = data['linkedin']

        leads.append({
            'Company Name': company,
            'Website': f'https://{domain}',
            'LinkedIn': linkedin,
            'Owner Name': '',
            'Owner LinkedIn URL': '',
            'Country': country,
            'Email': email,
            'Email Score': 'scraped' if email else '',
            'Services': ', '.join(services),
            'White Label Signals': ', '.join(wl_signals),
            'Pain Point': '',
            'Team Size': '',
            'Judge Score': '',
            'Sent date': '',
            'FU 1': '', 'FU 2': '', 'FU 3': '',
            'Status': '',
            'Source': 'SCOUT-WL v5',
        })

        report_email = email or 'NONE'
        report_svc = ', '.join(services) or 'N/A'
        report_wl = ', '.join(wl_signals) or 'NONE'
        log(f'  {report_email} | {report_svc} | {report_wl} | {country}')
        time.sleep(0.3)

    # Save CSV
    csv_path = os.path.join(NANOSOFT_DIR, 'new_wl_leads_v5.csv')
    if leads:
        with open(csv_path, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(leads[0].keys()))
            w.writeheader()
            w.writerows(leads)
        log(f'Saved {len(leads)} to {csv_path}')

    # Push to CRM
    try:
        from crm import get_crm
        crm = get_crm()
        added = skipped = 0
        for lead in leads:
            name = lead['Company Name'].lower().strip()
            email = lead['Email'].lower().strip() if lead['Email'] else ''
            if name in existing_names or (email and email in existing_emails):
                skipped += 1
                continue
            try:
                crm.add_wl_lead(lead)
                existing_names.add(name)
                if email:
                    existing_emails.add(email)
                added += 1
                log(f'  CRM+ {lead["Company Name"]}')
            except Exception as e:
                log(f'  CRM ERR: {e}')
        log(f'CRM: +{added} new, {skipped} dupes')
    except Exception as e:
        log(f'CRM error: {e}')

    with_email = sum(1 for l in leads if l['Email'])
    with_wl = sum(1 for l in leads if l['White Label Signals'])
    log(f'DONE: {len(leads)} scraped | {with_email} emails | {with_wl} WL')

if __name__ == '__main__':
    main()
