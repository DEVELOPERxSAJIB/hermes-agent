#!/usr/bin/env python3
"""
Quick email re-finder for bounced leads.
Tries multiple approaches:
1. Scrape homepage with more patterns
2. Try common prefixes @domain
3. Check LinkedIn for contact info
"""
import re, sys, time
from urllib.request import urlopen, Request

sys.path.insert(0, '/home/ubuntu/nanosoft')

BOUNCED = [
    {
        'company': 'Darly Solutions',
        'domain': 'darly.solutions',
        'website': 'https://www.darly.solutions/',
    },
    {
        'company': 'Future Processing',
        'domain': 'future-processing.com',
        'website': 'https://www.future-processing.com/',
    },
    {
        'company': 'Plavno',
        'domain': 'plavno.io',
        'website': 'https://plavno.io/',
    },
]

COMMON_PREFIXES = [
    'info', 'hello', 'contact', 'sales', 'team', 'hi', 'us',
    'enquiries', 'office', 'admin', 'inbox', 'mail', 'general',
    'inquiries', 'business', 'partners', 'work', 'hey',
]

def scrape_emails(domain, paths=None):
    if paths is None:
        paths = ['/', '/contact', '/about', '/contact-us', '/about-us', '/team', '/careers', '/support']
    
    emails_found = []
    for path in paths:
        try:
            url = f"https://{domain}{path}"
            req = Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0'})
            resp = urlopen(req, timeout=8)
            html = resp.read().decode('utf-8', errors='ignore')
            # Also decode HTML entities
            html = html.replace('&#64;', '@').replace('&#46;', '.').replace('&amp;', '&')
            
            emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', html)
            for e in emails:
                el = e.lower()
                bad = ['example@','test@','noreply','no-reply','sentry','@whois','vue@3','@scorebig',
                       '@afternic','john@doe','feedback@','user@domain','@sentry','@bytedance',
                       'help@','admin@','webmaster@','postmaster@','abuse@','privacy@','janedoe',
                       'acme.com','test.com','example.com']
                if not any(b in el for b in bad) and el not in emails_found:
                    emails_found.append(el)
            if emails_found:
                break
        except:
            continue
    return emails_found

def try_common_patterns(domain):
    """Try to guess email without SMTP verification."""
    for prefix in COMMON_PREFIXES:
        yield f"{prefix}@{domain}"

def main():
    from crm import get_crm
    crm = get_crm()
    
    for lead in BOUNCED:
        company = lead['company']
        domain = lead['domain']
        print(f"\n{company} ({domain}):")
        
        # Scrape website
        emails = scrape_emails(domain)
        if emails:
            best = emails[0]
            # Prioritize info/hello/sales
            for e in emails:
                if any(kw in e for kw in ['info@','hello@','sales@','contact@','team@']):
                    best = e
                    break
            crm.update_wl_lead(company, {'Email': best, 'Email Score': 'refound'})
            print(f"  Found via scrape: {best}")
        else:
            # Try homepage only with broader patterns
            try:
                req = Request(f"https://{domain}/", headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'})
                resp = urlopen(req, timeout=8)
                html = resp.read().decode('utf-8', errors='ignore')
                # Look for obfuscated emails
                obfuscated = re.findall(r'(\w+)\s*@\s*(\w+)\s*\.\s*(\w+)', html)
                if obfuscated:
                    print(f"  Obfuscated: {obfuscated[:3]}")
                
                # Look for mailto links
                mailtos = re.findall(r'mailto:([\w.+-]+@[\w-]+\.[\w.-]+)', html)
                if mailtos:
                    crm.update_wl_lead(company, {'Email': mailtos[0], 'Email Score': 'refound'})
                    print(f"  Found via mailto: {mailtos[0]}")
                    continue
            except:
                pass
            
            print(f"  Not found. Trying info@{domain} as fallback...")
            crm.update_wl_lead(company, {'Email': f'info@{domain}', 'Email Score': 'guessed'})
        
        time.sleep(1)
    
    print("\nDone.")

if __name__ == '__main__':
    main()
