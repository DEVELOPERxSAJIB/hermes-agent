#!/usr/bin/python3
"""
NanoSoft SCOUT-WL v2 — Multi-Source White Label Agency Lead Finder
Sources:
1. Google search: "white label web development agency" + country variations
2. Clutch.co white label agency listings
3. GoodFirms agency listings
4. Linkedin agency search (via Google)
5. Upwork agency partner directories
Output: CSV of agency leads ready for enrich + judge + send
"""
import json, os, re, sys, time, csv, random, subprocess
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from urllib.parse import quote_plus

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"

# Target countries
COUNTRIES = ['USA', 'UK', 'Canada', 'Australia', 'Germany', 'Netherlands',
             'Sweden', 'Poland', 'Ukraine', 'Romania']

# Search queries for Google
QUERIES = [
    '"white label" web development agency',
    '"white label" software development partner',
    'agency "white label development"',
    '"white label" mobile app development agency',
    'B2B software development agency partnerships',
    '"staff augmentation" agency partner program',
    'outsourced development partner agency',
    '"private label" software development agency',
    'white label SaaS development partner',
    'agency overflow development partner',
]

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/119.0.0.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/118.0.0.0',
]

def fetch_url(url, timeout=15):
    ua = random.choice(USER_AGENTS)
    req = Request(url, headers={'User-Agent': ua})
    try:
        resp = urlopen(req, timeout=timeout)
        return resp.read().decode('utf-8', errors='ignore')
    except:
        return None

def search_duckduckgo(query, max_results=10):
    """Search DDG and return list of URLs."""
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    html = fetch_url(url)
    if not html:
        return []
    # Extract result URLs
    urls = re.findall(r'<a rel="nofollow" class="result__a" href="(https?://[^"]+)"', html)
    # Filter out DDG tracking
    clean = []
    for u in urls:
        if 'duckduckgo' not in u and 'bing' not in u:
            clean.append(u)
    return clean[:max_results]

def extract_domain(url):
    m = re.search(r'https?://(?:www\.)?([^/]+)', url)
    return m.group(1) if m else ''

def extract_company_from_url(url):
    domain = extract_domain(url)
    # Remove TLD
    parts = domain.split('.')
    if len(parts) >= 2:
        name = parts[-2]
        # Clean up
        name = name.replace('-', ' ').replace('_', ' ').title()
        return name
    return domain

def scrape_contact_page(url, timeout=10):
    """Try to find email from common contact paths."""
    contact_paths = ['/contact', '/about', '/contact-us', '/about-us', '/team', '/leadership']
    domain = extract_domain(url)
    emails_found = []
    for path in contact_paths:
        full_url = f"https://{domain}{path}"
        html = fetch_url(full_url, timeout=timeout)
        if html:
            emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', html)
            for e in emails:
                if not any(bad in e for bad in ['example@', 'test@', 'noreply', 'no-reply', 'sentry', '@whois',
                                                     'vue@3', '@scorebig', '@afternic', 'john@doe', 'feedback@',
                                                     'user@domain', '@sentry', '@bytedance']):
                    # Prioritize info/hello/sales emails
                    el = e.lower()
                    if any(kw in el for kw in ['info@', 'hello@', 'sales@', 'contact@', 'team@', 'us@', 'hello']):
                        emails_found.insert(0, e)
                    elif e not in emails_found:
                        emails_found.append(e)
        if emails_found:
            break
        time.sleep(1)
    return emails_found[0] if emails_found else ''

def scrape_services(url, timeout=10):
    """Scrape service keywords from company website."""
    html = fetch_url(url, timeout=timeout)
    if not html:
        return []
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text).lower()
    
    service_keywords = {
        'web development': ['web development', 'web app', 'web application', 'frontend', 'backend', 'full stack'],
        'mobile development': ['mobile development', 'mobile app', 'ios development', 'android development', 'react native', 'flutter'],
        'AI/ML': ['artificial intelligence', 'machine learning', 'ai development', 'ml model', 'deep learning', 'nlp'],
        'UI/UX design': ['ui design', 'ux design', 'user interface', 'product design', 'design agency'],
        'cloud/DevOps': ['devops', 'cloud migration', 'aws', 'azure', 'gcp', 'kubernetes', 'infrastructure'],
        'SaaS': ['saas', 'saas development', 'software as a service'],
        'eCommerce': ['ecommerce', 'e-commerce', 'shopify', 'magento', 'woocommerce'],
        'QA/Testing': ['qa testing', 'quality assurance', 'software testing', 'test automation'],
        'custom software': ['custom software', 'bespoke software', 'enterprise software'],
        'blockchain': ['blockchain', 'web3', 'smart contract', 'defi'],
    }
    
    found = []
    for service, keywords in service_keywords.items():
        for kw in keywords:
            if kw in text:
                found.append(service)
                break
    return found[:5]

def detect_wl_signals(url, timeout=10):
    """Detect white label partnership signals on website."""
    html = fetch_url(url, timeout=timeout)
    if not html:
        return []
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text).lower()
    
    signals = []
    wl_keywords = {
        'white label': ['white label', 'white-label', 'whitelabel'],
        'partner program': ['partner program', 'partnership program', 'agency partner'],
        'outsourcing': ['outsourcing', 'outsource', 'external development'],
        'staff augmentation': ['staff augmentation', 'team extension', 'dedicated team'],
        'B2B': ['b2b', 'business to business', 'enterprise partner'],
        'reseller': ['reseller', 'referral partner', 'affiliate'],
    }
    
    for signal, keywords in wl_keywords.items():
        for kw in keywords:
            if kw in text:
                signals.append(signal)
                break
    return signals[:4]

def find_linkedin(url, timeout=10):
    """Find LinkedIn company page from website."""
    html = fetch_url(url, timeout=timeout)
    if not html:
        return ''
    m = re.search(r'https://www\.linkedin\.com/company/["\']?([^"\'>\s"\']+)', html)
    if m:
        return f"https://www.linkedin.com/company/{m.group(1)}"
    
    # Try from domain
    domain = extract_domain(url)
    html2 = fetch_url(f"https://{domain}/about", timeout=timeout) or ''
    m = re.search(r'https://www\.linkedin\.com/company/["\']?([^"\'>\s"\']+)', html2)
    if m:
        return f"https://www.linkedin.com/company/{m.group(1)}"
    return ''

def extract_country(url, timeout=10):
    """Try to extract country from website contact info."""
    html = fetch_url(url, timeout=timeout)
    if not html:
        return ''
    text = re.sub(r'<[^>]+>', ' ', html)
    
    country_patterns = [
        (r'\b(United States|USA|U\.S\.A\.|US)\b', 'USA'),
        (r'\b(United Kingdom|UK|U\.K\.|England|Scotland|Wales)\b', 'UK'),
        (r'\b(Canada|Toronto|Vancouver|Montreal|Ontario|BC|Alberta)\b', 'Canada'),
        (r'\b(Australia|Sydney|Melbourne|Brisbane|Perth|NSW|VIC)\b', 'Australia'),
        (r'\b(Germany|Berlin|Frankfurt|Munich)\b', 'Germany'),
        (r'\b(Netherlands|Amsterdam|Rotterdam)\b', 'Netherlands'),
        (r'\b(Ukraine|Kyiv|Lviv|Odessa|Dnipro)\b', 'Ukraine'),
        (r'\b(Poland|Warsaw|Krakow|Gdansk)\b', 'Poland'),
        (r'\b(Romania|Bucharest|Cluj|Timisoara)\b', 'Romania'),
        (r'\b(Sweden|Stockholm|Gothenburg)\b', 'Sweden'),
    ]
    
    for pattern, country in country_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return country
    return ''

def log(msg):
    ts = datetime.now(BD_TZ).strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{ts}] [SCOUT-WL] {msg}', flush=True)

def main():
    log('Starting multi-source white label lead scout...')
    
    found_urls = {}  # domain -> company_name
    
    # Phase 1: Search Google/DDG
    for query in QUERIES:
        log(f'Searching: "{query}"')
        urls = search_duckduckgo(query, max_results=8)
        for url in urls:
            domain = extract_domain(url)
            if domain and domain not in found_urls:
                company = extract_company_from_url(url)
                # Skip irrelevant results
                skip = ['wikipedia', 'linkedin', 'glassdoor', 'indeed', 'upwork', 'fiverr',
                        'clutch.co', 'goodfirms', 'reddit', 'quora', 'medium', 'youtube',
                        'twitter', 'facebook', 'instagram', 'tiktok', 'pinterest',
                        'amazon', 'apple', 'google', 'microsoft', 'meta', 'twitter']
                if any(s in domain.lower() for s in skip):
                    continue
                found_urls[domain] = company
                log(f'  Found: {company} ({domain})')
        time.sleep(2)
    
    log(f'Phase 1 complete: {len(found_urls)} unique domains found')
    
    # Phase 2: Scrape each website for email, services, WL signals
    leads = []
    for i, (domain, company) in enumerate(found_urls.items()):
        log(f'[{i+1}/{len(found_urls)}] Scraping {company} ({domain})')
        url = f"https://{domain}"
        
        email = scrape_contact_page(url)
        services = scrape_services(url)
        wl_signals = detect_wl_signals(url)
        linkedin = find_linkedin(url)
        country = extract_country(url)
        
        lead = {
            'Company Name': company,
            'Website': url,
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
            'FU 1': '',
            'FU 2': '',
            'FU 3': '',
            'Status': 'New',
            'Source': 'SCOUT-WL v2',
            'Scouted At': datetime.now(BD_TZ).strftime('%Y-%m-%d'),
        }
        leads.append(lead)
        
        log(f'  Email: {email or "NONE"} | Services: {", ".join(services) or "N/A"} | WL: {", ".join(wl_signals) or "N/A"} | Country: {country or "N/A"}')
        
        time.sleep(1.5)  # polite delay
    
    # Phase 3: Save to CSV
    csv_path = os.path.join(NANOSOFT_DIR, 'new_wl_leads_raw.csv')
    if leads:
        fieldnames = list(leads[0].keys())
        with open(csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(leads)
        log(f'Saved {len(leads)} leads to {csv_path}')
    
    # Phase 4: Push to CRM
    sys.path.insert(0, NANOSOFT_DIR)
    try:
        from crm import get_crm
        crm = get_crm()
        
        # Get existing to avoid duplicates
        existing = crm.get_wl_all()
        existing_names = {l.get('Company Name','').lower().strip() for l in existing}
        existing_emails = {l.get('Email','').lower().strip() for l in existing if l.get('Email')}
        
        added = 0
        skipped = 0
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
                log(f'  CRM: Added {lead["Company Name"]}')
            except Exception as e:
                log(f'  CRM: Failed {lead["Company Name"]}: {e}')
        
        log(f'CRM: Added {added} new leads, skipped {skipped} duplicates')
    except Exception as e:
        log(f'CRM push failed: {e}')
    
    # Summary
    with_email = sum(1 for l in leads if l['Email'])
    with_wl = sum(1 for l in leads if l['White Label Signals'])
    with_services = sum(1 for l in leads if l['Services'])
    
    log(f'SUMMARY: {len(leads)} total scraped | {with_email} with email | {with_wl} with WL signals | {with_services} with services')

if __name__ == '__main__':
    main()
