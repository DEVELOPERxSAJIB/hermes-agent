#!/usr/bin/env python3
"""
NanoSoft SCOUT-WL v3 — Uses Playwright to search Google/DuckDuckGo
More reliable than urllib for search results.
"""
import json, os, re, sys, time, csv
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"

QUERIES = [
    '"white label" web development agency usa',
    '"white label" software development partner uk',
    'agency "white label development" canada',
    '"white label" mobile app development agency australia',
    '"staff augmentation" agency partner program usa',
    'outsourced development partner agency uk',
    '"white label" saas development partner',
    'agency overflow development partner',
    'white label web design agency uk',
    '"white label" wordpress agency usa',
    'outsourced web development agency partner',
    '"private label" software development',
    'B2B web development white label partner',
    'agency dedicated development team partner',
    '"white label" react native agency',
    'outsourcing partner for agencies',
    '"white label" django development agency',
    'agency technology partner program',
    '"white label" node.js development partner',
    'software development reseller program',
]

def log(msg):
    ts = datetime.now(BD_TZ).strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{ts}] [SCOUT-WL] {msg}', flush=True)

def search_playwright(query, max_results=10):
    """Use Playwright CLI to search DuckDuckGo and extract result URLs."""
    # Try urllib fallback only (Playwright not reliably installed)
    import urllib.request, urllib.parse
    try:
        q = urllib.parse.quote(query)
        url = f"https://html.duckduckgo.com/html/?q={q}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/118.0.0.0'})
        resp = urllib.request.urlopen(req, timeout=15)
        html = resp.read().decode('utf-8', errors='ignore')
        # DDG HTML results
        urls = re.findall(r'<a rel="nofollow" class="result__a" href="([^"]+)"', html)
        if not urls:
            urls = re.findall(r'href="(https?://[^"]+)"', html)
        clean = []
        for u in urls:
            if 'duckduckgo' not in u and u.startswith('http'):
                clean.append(u)
        return clean[:max_results]
    except:
        return []
    m = re.search(r'https?://(?:www\.)?([^/]+)', url)
    return m.group(1) if m else ''

def extract_company(domain):
    parts = domain.split('.')
    if len(parts) >= 2:
        name = parts[-2]
        return name.replace('-', ' ').replace('_', ' ').title()
    return domain

def scrape_page(domain, path='', timeout=10):
    """Scrape a page from the domain."""
    url = f"https://{domain}{path}"
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0'})
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.read().decode('utf-8', errors='ignore')
    except:
        return None

def find_email(domain):
    """Find email from contact pages."""
    for path in ['/contact', '/about', '/contact-us', '/about-us', '/']:
        html = scrape_page(domain, path, timeout=8)
        if html:
            emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', html)
            for e in emails:
                el = e.lower()
                bad = ['example@','test@','noreply','no-reply','sentry','@whois','vue@3','@scorebig',
                       '@afternic','john@doe','feedback@','user@domain','@sentry','@bytedance',
                       'help@','support@','admin@','webmaster@','postmaster@','abuse@']
                if not any(b in el for b in bad) and '.' in e.split('@')[1]:
                    if any(kw in el for kw in ['info@','hello@','sales@','contact@','team@','us@','hi@']):
                        return e
                    # Accept any reasonable email from homepage
                    if path == '/' and '@' in e:
                        return e
    return ''

def find_services(domain):
    html = scrape_page(domain, '/', timeout=10)
    if not html:
        return []
    text = re.sub(r'<[^>]+>', ' ', html).lower()
    text = re.sub(r'\s+', ' ', text)
    
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

def find_wl_signals(domain):
    html = scrape_page(domain, '/', timeout=10)
    if not html:
        return []
    text = re.sub(r'<[^>]+>', ' ', html).lower()
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

def find_linkedin(domain):
    html = scrape_page(domain, '/', timeout=10)
    if html:
        m = re.search(r'linkedin\.com/company/([^"\'>\s\)]+)', html)
        if m:
            return f"https://www.linkedin.com/company/{m.group(1).rstrip('/')}"
    html2 = scrape_page(domain, '/about', timeout=8)
    if html2:
        m = re.search(r'linkedin\.com/company/([^"\'>\s\)]+)', html2)
        if m:
            return f"https://www.linkedin.com/company/{m.group(1).rstrip('/')}"
    return ''

def find_country(domain):
    for path in ['/contact', '/about', '/']:
        html = scrape_page(domain, path, timeout=8)
        if html:
            text = re.sub(r'<[^>]+>', ' ', html)
            checks = [
                (r'\b(United States|USA|U\.S\.A\.)[^a-zA-Z]', 'USA'),
                (r'(\bUnited Kingdom\b|UK:)', 'UK'),
                (r'\b(Toronto|Vancouver|Montreal|Canada)\b', 'Canada'),
                (r'\b(Sydney|Melbourne|Brisbane|Australia)\b', 'Australia'),
                (r'\b(Kyiv|Lviv|Ukraine)\b', 'Ukraine'),
                (r'\b(Warsaw|Krakow|Poland)\b', 'Poland'),
                (r'\b(Bucharest|Romania)\b', 'Romania'),
                (r'\b(Amsterdam|Netherlands)\b', 'Netherlands'),
                (r'\b(Stockholm|Sweden)\b', 'Sweden'),
            ]
            for pattern, country in checks:
                if re.search(pattern, text, re.IGNORECASE):
                    return country
    return ''

def main():
    log('SCOUT-WL v3 starting (Playwright + urllib)...')
    
    import urllib.parse
    
    found_domains = {}
    
    for i, query in enumerate(QUERIES):
        log(f'[{i+1}/{len(QUERIES)}] {query[:50]}...')
        
        # Try Playwright first, fallback to urllib
        urls = search_playwright(query, max_results=8)
        
        for url in urls:
            domain = extract_domain(url)
            if not domain:
                continue
            # Skip known non-agency sites
            skip = ['wikipedia','linkedin','glassdoor','indeed','fiverr','upwork',
                    'facebook','twitter','youtube','instagram','pinterest','reddit',
                    'quora','medium','amazon','apple','google','microsoft','github',
                    'stackoverflow','crunchbase','bloomberg','reuters','bbc','cnn',
                    'forbes','inc\.com','entrepreneur\.com','mashable','techcrunch',
                    'wired','theverge','gizmodo','arstechnica','smashingmagazine',
                    'css-tricks','sitepoint','tutsplus','codecademy','udemy','coursera',
                    'clutch\.co','goodfirms','designrush','sortlist','agencies\.']
            if any(re.search(s, domain.lower()) for s in skip):
                continue
            if domain not in found_domains:
                found_domains[domain] = extract_company(domain)
                log(f'  NEW: {found_domains[domain]} ({domain})')
        
        time.sleep(1.5)
    
    log(f'Phase 1: {len(found_domains)} unique domains')
    
    # Phase 2: Scrape each
    leads = []
    for i, (domain, company) in enumerate(found_domains.items()):
        log(f'[{i+1}/{len(found_domains)}] {company}...')
        email = find_email(domain)
        services = find_services(domain)
        wl_signals = find_wl_signals(domain)
        linkedin = find_linkedin(domain)
        country = find_country(domain)
        
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
            'Source': 'SCOUT-WL v3',
            'Scouted At': datetime.now(BD_TZ).strftime('%Y-%m-%d'),
        })
        
        email_str = email or 'NONE'
        svc_str = ', '.join(services) or 'N/A'
        wl_str = ', '.join(wl_signals) or 'NONE'
        log(f'  email={email_str} | svc={svc_str} | wl={wl_str} | country={country}')
        
        time.sleep(1)
    
    # Save CSV
    csv_path = os.path.join(NANOSOFT_DIR, 'new_wl_leads_v3.csv')
    if leads:
        with open(csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(leads[0].keys()))
            writer.writeheader()
            writer.writerows(leads)
        log(f'Saved {len(leads)} leads to {csv_path}')
    
    # Push to CRM
    sys.path.insert(0, NANOSOFT_DIR)
    try:
        from crm import get_crm
        crm = get_crm()
        existing = crm.get_wl_all()
        existing_names = {l.get('Company Name','').lower().strip() for l in existing}
        existing_emails = {l.get('Email','').lower().strip() for l in existing if l.get('Email')}
        
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
                log(f'  CRM ERR {lead["Company Name"]}: {e}')
        log(f'CRM: +{added} new, {skipped} dupes')
    except Exception as e:
        log(f'CRM error: {e}')
    
    with_email = sum(1 for l in leads if l['Email'])
    with_wl = sum(1 for l in leads if l['White Label Signals'])
    log(f'DONE: {len(leads)} scraped | {with_email} emails | {with_wl} WL signals')

if __name__ == '__main__':
    main()
