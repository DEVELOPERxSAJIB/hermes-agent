#!/usr/bin/python3
"""
NanoSoft SCOUT-WL v4 — Uses ddgs CLI for search (works on Oracle Cloud)
"""
import json, os, re, sys, time, csv, subprocess
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"

QUERIES = [
    # White label specific
    '"white label" web development agency usa',
    '"white label" software development partner uk',
    'agency "white label development"',
    '"white label" mobile app development agency',
    '"white label" saas development partner',
    'agency overflow development partner',
    'white label web design agency uk',
    '"white label" wordpress agency',
    'outsourced web development agency partner',
    'B2B web development white label partner',
    'agency dedicated development team partner',
    '"white label" react native agency',
    'outsourcing partner for agencies',
    '"white label" django development agency',
    'agency technology partner program',
    '"white label" node.js development partner',
    'software development reseller program',
    'white label ecommerce development agency',
    'white label shopify agency partner',
    '"white label" flutter agency',
    'agency white label mobile development',
    'white label software partner australia',
    # Staff augmentation
    '"staff augmentation" agency partner program usa',
    '"staff augmentation" web development agency uk',
    'dedicated development team agency partner',
    'team extension agency partner program',
    'nearshore development partner agency',
    'offshore development partner agency',
    # Outsourcing
    'outsourced development agency partner program',
    'software development outsourcing partner',
    'IT outsourcing agency partner',
    'development partner for agencies',
    'agency development partner program',
    # Reseller
    'software reseller program agency',
    'white label reseller development',
    'agency reseller development partner',
    # Specific tech
    '"white label" python development agency',
    '"white label" php development agency',
    '"white label" ruby on rails agency',
    'white label angular development agency',
    'white label vue.js development agency',
    # By country
    'white label development agency canada',
    'white label development agency australia',
    'white label development agency india',
    'white label development agency philippines',
    'white label development agency vietnam',
    'white label development agency brazil',
    'white label development agency mexico',
    'white label development agency colombia',
    # Agency partnerships
    'agency partnership program development',
    'web development agency collaboration',
    'software agency joint venture partner',
    'development agency subcontractor',
    'agency white label app development',
    'mobile app white label agency partner',
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
]

def log(msg):
    ts = datetime.now(BD_TZ).strftime("%Y-%m-%d %H:%M:%S")
    print(f'[{ts}] [SCOUT] {msg}', flush=True)

def ddg_search(query, max_results=10):
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
        return name.replace('-', ' ').replace('_', ' ').title()
    return domain

def should_skip(domain):
    for s in SKIP_DOMAINS:
        if s in domain:
            return True
    return False

def scrape_page(url, timeout=8):
    try:
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0'})
        resp = urlopen(req, timeout=timeout)
        return resp.read().decode('utf-8', errors='ignore')
    except:
        return None

def find_email(domain):
    for path in ['/contact', '/about', '/contact-us', '/about-us', '/']:
        html = scrape_page(f"https://{domain}{path}", timeout=8)
        if html:
            emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', html)
            for e in emails:
                el = e.lower()
                bad = ['example@','test@','noreply','no-reply','sentry','@whois','vue@3','@scorebig',
                       '@afternic','john@doe','feedback@','user@domain','@sentry','@bytedance',
                       'help@','support@','admin@','webmaster@','postmaster@','abuse@','privacy@',
                       'security@','legal@','press@','media@','investor@','careers@','jobs@','hr@']
                if not any(b in el for b in bad):
                    tld = e.split('@')[1].split('.')[-1] if '@' in e else ''
                    if tld in ['com','org','net','io','co','co.uk','com.au','ca','de','fr','eu']:
                        if any(kw in el for kw in ['info@','hello@','sales@','contact@','team@','us@','hi@']):
                            return e
                        if path == '/':
                            return e
    return ''

def find_services(domain):
    html = scrape_page(f"https://{domain}/", timeout=10)
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
    html = scrape_page(f"https://{domain}/", timeout=10)
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
    for path in ['/', '/about']:
        html = scrape_page(f"https://{domain}{path}", timeout=8)
        if html:
            m = re.search(r'linkedin\.com/company/([^"\'>\s\)]+)', html)
            if m:
                return f"https://www.linkedin.com/company/{m.group(1).rstrip('/')}"
    return ''

def find_country(domain):
    for path in ['/contact', '/about', '/']:
        html = scrape_page(f"https://{domain}{path}", timeout=8)
        if html:
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

def main():
    log('SCOUT-WL v4 starting...')
    
    found_domains = {}
    
    for i, query in enumerate(QUERIES):
        log(f'[{i+1}/{len(QUERIES)}] {query[:55]}...')
        results = ddg_search(query, max_results=8)
        
        for r in results:
            url = r.get('href', '')
            domain = extract_domain(url)
            if domain and not should_skip(domain) and domain not in found_domains:
                company = extract_company(domain)
                found_domains[domain] = company
                log(f'  NEW: {company} ({domain})')
        
        time.sleep(1)
    
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
            'Source': 'SCOUT-WL v4',
        })
        
        report_email = email or 'NONE'
        report_svc = ', '.join(services) or 'N/A'
        report_wl = ', '.join(wl_signals) or 'NONE'
        log(f'  {report_email} | {report_svc} | {report_wl} | {country}')
        time.sleep(0.8)
    
    # Save CSV
    csv_path = os.path.join(NANOSOFT_DIR, 'new_wl_leads_v4.csv')
    if leads:
        with open(csv_path, 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(leads[0].keys()))
            w.writeheader()
            w.writerows(leads)
        log(f'Saved {len(leads)} to {csv_path}')
    
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
                log(f'  CRM ERR: {e}')
        log(f'CRM: +{added} new, {skipped} dupes')
    except Exception as e:
        log(f'CRM error: {e}')
    
    with_email = sum(1 for l in leads if l['Email'])
    with_wl = sum(1 for l in leads if l['White Label Signals'])
    log(f'DONE: {len(leads)} scraped | {with_email} emails | {with_wl} WL')

if __name__ == '__main__':
    from urllib.request import urlopen, Request
    main()
