#!/usr/bin/env python3
"""
NanoSoft ENRICH + SEND v1 — For manually gathered leads
Scrapes: email, services, country, LinkedIn, WL signals
Then judges and sends T1 to qualified ones.
"""
import json, os, re, sys, time, csv
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
sys.path.insert(0, NANOSOFT_DIR)

def log(msg):
    ts = datetime.now(BD_TZ).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [ENRICH] {msg}", flush=True)

def scrape_page(url, timeout=8):
    try:
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0'})
        resp = urlopen(req, timeout=timeout)
        return resp.read().decode('utf-8', errors='ignore')
    except:
        return None

def find_email(domain):
    bad = ['example@','test@','noreply','no-reply','sentry','@whois','vue@3','@scorebig',
           '@afternic','john@doe','feedback@','user@domain','@sentry','@bytedance',
           'help@','admin@','webmaster@','postmaster@','abuse@','privacy@','janedoe',
           'acme.com','test.com','example.com']
    for path in ['/', '/contact', '/about', '/contact-us', '/about-us', '/team']:
        html = scrape_page(f"https://{domain}{path}", timeout=8)
        if html:
            # Check mailto links first
            mailtos = re.findall(r'mailto:([\w.+-]+@[\w-]+\.[\w.-]+)', html)
            for e in mailtos:
                if not any(b in e.lower() for b in bad):
                    return e
            # Then regex
            emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', html)
            for e in emails:
                if not any(b in e.lower() for b in bad):
                    el = e.lower()
                    if any(kw in el for kw in ['info@','hello@','sales@','contact@','team@','hi@','us@']):
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
        'blockchain': ['blockchain', 'web3', 'smart contract', 'defi'],
    }
    found = []
    for svc, kws in services.items():
        for kw in kws:
            if kw in text:
                found.append(svc)
                break
    return found[:5]

def find_country(domain):
    for path in ['/contact', '/about', '/']:
        html = scrape_page(f"https://{domain}{path}", timeout=8)
        if html:
            text = re.sub(r'<[^>]+>', ' ', html)
            checks = [
                (r'\b(United States|USA|U\.S\.A\.)\b', 'USA'),
                (r'\b(United Kingdom|UK|U\.K\.|England|Scotland|Wales)\b', 'UK'),
                (r'\b(Toronto|Vancouver|Montreal|Canada|Ontario|BC)\b', 'Canada'),
                (r'\b(Sydney|Melbourne|Brisbane|Australia|NSW|VIC)\b', 'Australia'),
                (r'\b(Kyiv|Lviv|Ukraine)\b', 'Ukraine'),
                (r'\b(Warsaw|Krakow|Poland)\b', 'Poland'),
                (r'\b(Bucharest|Romania)\b', 'Romania'),
                (r'\b(Amsterdam|Netherlands)\b', 'Netherlands'),
                (r'\b(Stockholm|Sweden)\b', 'Sweden'),
                (r'\b(Berlin|Frankfurt|Germany)\b', 'Germany'),
                (r'\b(India|Mumbai|Bangalore|Delhi|Hyderabad|Pune)\b', 'India'),
                (r'\b(Singapore)\b', 'Singapore'),
                (r'\b(Dubai|UAE|United Arab Emirates)\b', 'UAE'),
            ]
            for pattern, country in checks:
                if re.search(pattern, text, re.IGNORECASE):
                    return country
    return ''

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

def extract_domain(url):
    m = re.search(r'https?://(?:www\.)?([^/]+)', url)
    return m.group(1).lower().strip() if m else ''

def main():
    from crm import get_crm
    from judge_wl import judge_wl_lead
    
    crm = get_crm()
    wl = crm.get_wl_all()
    
    # Find leads with empty status (the 20 new ones)
    empty_status = [l for l in wl if not l.get('Status','').strip()]
    log(f"Found {len(empty_status)} leads to enrich")
    
    enriched = 0
    qualified = []
    
    for i, lead in enumerate(empty_status):
        company = lead.get('Company Name', '')
        website = lead.get('Website', '')
        domain = extract_domain(website)
        
        if not domain:
            log(f"[{i+1}/{len(empty_status)}] SKIP: {company} (no domain)")
            crm.update_wl_lead(company, {'Status': 'Unqualified'})
            continue
        
        log(f"[{i+1}/{len(empty_status)}] {company} ({domain})")
        
        email = find_email(domain)
        services = find_services(domain)
        country = find_country(domain)
        wl_signals = find_wl_signals(domain)
        linkedin = find_linkedin(domain)
        
        # Update CRM
        update = {
            'Email': email,
            'Email Score': 'scraped' if email else '',
            'Services': ', '.join(services),
            'Country': country,
            'LinkedIn': linkedin,
            'White Label Signals': ', '.join(wl_signals),
        }
        crm.update_wl_lead(company, update)
        
        log(f"  email={email or 'NONE'} | svc={','.join(services) or 'N/A'} | country={country} | wl={','.join(wl_signals) or 'NONE'}")
        
        # Judge
        if email:
            # Re-read the lead with updated data
            wl_updated = crm.get_wl_all()
            lead_data = next((l for l in wl_updated if l.get('Company Name') == company), None)
            if lead_data:
                score, is_q, details = judge_wl_lead(lead_data)
                if is_q:
                    crm.update_wl_lead(company, {'Judge Score': str(score), 'Status': 'Qualified'})
                    qualified.append(lead_data)
                    log(f"  ✅ QUALIFIED ({score}/10)")
                else:
                    crm.update_wl_lead(company, {'Judge Score': str(score), 'Status': 'Unqualified'})
                    log(f"  ❌ Unqualified ({score}/10)")
        else:
            crm.update_wl_lead(company, {'Status': 'Unqualified'})
            log(f"  ❌ No email found")
        
        enriched += 1
        time.sleep(1.5)
    
    log(f"\nEnriched: {enriched}/{len(empty_status)}")
    log(f"Qualified: {len(qualified)}")
    
    if qualified:
        log(f"\nQualified leads:")
        for l in qualified:
            log(f"  {l['Company Name']} | {l['Email']} | {l.get('Judge Score')}/10")
    
    return qualified

if __name__ == '__main__':
    main()
