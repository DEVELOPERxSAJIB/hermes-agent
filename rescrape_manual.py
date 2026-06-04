#!/usr/bin/env python3
"""
Re-scrape all 20 manual leads with deeper scraping.
Some emails were missed or marked low score incorrectly.
"""
import sys, re, time
sys.path.insert(0, '/home/ubuntu/nanosoft')
from urllib.request import urlopen, Request
from crm import get_crm

def scrape_all_emails(domain):
    """Deep scrape: try more pages, check mailto links, check for obfuscated emails."""
    bad = ['example@','test@','noreply','no-reply','sentry','@whois','vue@3','@scorebig',
           '@afternic','john@doe','feedback@','user@domain','@sentry','@bytedance',
           'help@','admin@','webmaster@','postmaster@','abuse@','privacy@','janedoe',
           'acme.com','test.com','example.com','bootstrap@','gsap@','jquery@','react@',
           'vue@','angular@','@npm','@github','@cdnjs','@unpkg','@jsdelivr','@wixpress',
           '@sentry','melloway@','case-study']
    
    found = []
    paths = ['/', '/contact', '/about', '/about-us', '/contact-us', '/team', '/careers',
             '/leadership', '/management', '/people', '/staff', '/about/our-team',
             '/contact.html', '/about.html']
    
    for path in paths:
        try:
            url = f"https://{domain}{path}"
            req = Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0'})
            resp = urlopen(req, timeout=8)
            html = resp.read().decode('utf-8', errors='ignore')
            
            # Decode common obfuscations
            html = html.replace('&#64;', '@').replace('&#46;', '.').replace('&amp;', '&')
            html = html.replace('[at]', '@').replace('(at)', '@').replace(' [dot] ', '.')
            
            # mailto links
            mailtos = re.findall(r'mailto:([\w.+-]+@[\w-]+\.[\w.-]+)', html)
            for e in mailtos:
                el = e.lower()
                if not any(b in el for b in bad) and not re.search(r'@\d+\.\d+', e):
                    found.append(e)
            
            # regex emails
            emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', html)
            for e in emails:
                el = e.lower()
                if not any(b in el for b in bad) and not re.search(r'@\d+\.\d+', e):
                    if e not in found:
                        found.append(e)
            
            if found:
                break
        except:
            continue
    
    # Prioritize: info/hello/sales/contact/team > others
    priority = []
    other = []
    for e in found:
        el = e.lower()
        if any(kw in el for kw in ['info@','hello@','sales@','contact@','team@','hi@','biz@','letstalk@','marketing@','office@','enquiry@','enquiries@','support@','partners@','careers@','hr@','jobs@']):
            priority.append(e)
        else:
            other.append(e)
    
    return priority + other

def find_services(domain):
    html = None
    for path in ['/', '/services', '/what-we-do', '/solutions', '/expertise']:
        try:
            req = Request(f"https://{domain}{path}", headers={'User-Agent': 'Mozilla/5.0'})
            resp = urlopen(req, timeout=8)
            html = resp.read().decode('utf-8', errors='ignore')
            break
        except:
            continue
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
        try:
            req = Request(f"https://{domain}{path}", headers={'User-Agent': 'Mozilla/5.0'})
            resp = urlopen(req, timeout=8)
            html = resp.read().decode('utf-8', errors='ignore')
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
                (r'\b(India|Mumbai|Bangalore|Delhi|Hyderabad|Pune|Chennai)\b', 'India'),
                (r'\b(Singapore)\b', 'Singapore'),
                (r'\b(Dubai|UAE|United Arab Emirates)\b', 'UAE'),
            ]
            for pattern, country in checks:
                if re.search(pattern, text, re.IGNORECASE):
                    return country
        except:
            continue
    return ''

def find_wl_signals(domain):
    try:
        req = Request(f"https://{domain}/", headers={'User-Agent': 'Mozilla/5.0'})
        resp = urlopen(req, timeout=8)
        html = resp.read().decode('utf-8', errors='ignore')
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
    except:
        return []

def main():
    crm = get_crm()
    wl = crm.get_wl_all()
    
    # The 20 manual leads
    manual_names = [
        'Anigami Studio', 'You are launched', 'unicrew', 'Scalo', 'Euvic', 'Apzumi',
        'Software Mind S.A.', 'Riseapps', 'Pell Software', 'Experion Technologies',
        'DreamzTech Solutions', 'RichBrains', 'GOTOMA Software House',
        'Mallow Technologies Private Limited', 'Railsware', 'Goodface agency',
        'Caxy Consulting', 'HotShots Labs', 'ThinkPalm Technologies', 'Qualhon Informatics Pvt. Ltd'
    ]
    
    # Find leads in CRM
    manual_leads = []
    for l in wl:
        name = l.get('Company Name','').strip()
        for ml in manual_names:
            if ml in name or name in ml:
                manual_leads.append(l)
                break
    
    print(f"Found {len(manual_leads)} manual leads in CRM")
    
    # Domains mapping
    domains = {
        'Anigami Studio': 'anigami.studio',
        'You are launched': 'urlaunched.com',
        'unicrew': 'unicrew.com',
        'Scalo': 'scalosoft.com',
        'Euvic': 'euvic.com',
        'Apzumi': 'apzumi.com',
        'Software Mind S.A.': 'softwaremind.com',
        'Riseapps': 'riseapps.co',
        'Pell Software': 'pellsoftware.com',
        'Experion Technologies': 'experionglobal.com',
        'DreamzTech Solutions': 'dreamztech.com',
        'RichBrains': 'richbrains.net',
        'GOTOMA Software House': 'gotoma.pl',
        'Mallow Technologies Private Limited': 'mallow-tech.com',
        'Railsware': 'railsware.com',
        'Goodface agency': 'goodface.agency',
        'Caxy Consulting': 'caxy.com',
        'HotShots Labs': 'hotshotslabs.com',
        'ThinkPalm Technologies': 'thinkpalm.com',
        'Qualhon Informatics Pvt. Ltd': 'qualhon.com',
    }
    
    requalified = []
    
    for i, lead in enumerate(manual_leads):
        company = lead.get('Company Name', '').strip()
        # Clean up company name for matching
        clean_name = company.replace('\r','').strip()
        domain = domains.get(clean_name, '')
        
        if not domain:
            print(f"[{i+1}] SKIP: {clean_name} (no domain)")
            continue
        
        current_email = lead.get('Email', '').strip()
        current_status = lead.get('Status', '')
        
        print(f"\n[{i+1}/{len(manual_leads)}] {clean_name} ({domain})")
        print(f"  Current: {current_status} | email={current_email}")
        
        # Re-scrape email
        emails = scrape_all_emails(domain)
        services = find_services(domain)
        country = find_country(domain)
        wl_signals = find_wl_signals(domain)
        
        # Pick best email
        best_email = None
        if emails:
            # Skip bad ones
            for e in emails:
                if not any(b in e.lower() for b in ['gsap@','bootstrap@','jquery@','react@','vue@','@npm','@github','lenis@','melloway@','case-study']):
                    best_email = e
                    break
        
        print(f"  Found: email={best_email or 'NONE'} | svc={','.join(services) or 'N/A'} | country={country} | wl={','.join(wl_signals) or 'NONE'}")
        
        # Update CRM with fresh data
        update = {
            'Services': ', '.join(services),
            'Country': country,
            'White Label Signals': ', '.join(wl_signals),
        }
        if best_email and best_email != current_email:
            update['Email'] = best_email
            update['Email Score'] = 'rescraped'
        
        crm.update_wl_lead(clean_name, update)
        
        # Re-judge
        if best_email:
            from judge_wl import judge_wl_lead
            # Re-read updated lead
            wl_updated = crm.get_wl_all()
            lead_data = next((l for l in wl_updated if l.get('Company Name','').strip() == clean_name), None)
            if lead_data:
                score, is_q, _ = judge_wl_lead(lead_data)
                if is_q and current_status != 'T1 Sent':
                    crm.update_wl_lead(clean_name, {'Judge Score': str(score), 'Status': 'Qualified'})
                    requalified.append(lead_data)
                    print(f"  ✅ RE-QUALIFIED ({score}/10)")
                else:
                    print(f"  Score: {score}/10 | qualified={is_q}")
        
        time.sleep(1.5)
    
    print(f"\n{'='*50}")
    print(f"Re-qualified: {len(requalified)}")
    for l in requalified:
        print(f"  {l['Company Name'][:35]:<35} | {l['Email'][:35]:<35} | {l.get('Judge Score')}/10")
    
    return requalified

if __name__ == '__main__':
    main()
