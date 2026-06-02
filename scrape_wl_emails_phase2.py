#!/usr/bin/env python3
"""
Try harder for the 6 agencies without emails.
1. Try common email patterns (hello@, info@, contact@, sales@, team@)
2. Try Playwright for JS-rendered sites
"""
import urllib.request, re, time, json, sys

sys.path.insert(0, '/home/ubuntu/nanosoft')

# Agencies still missing emails
MISSING = [
    ("Simform", "https://www.simform.com", "simform.com"),
    ("Kingsmen Digital Ventures", "https://go.kingsmendv.com", "kingsmendv.com"),
    ("Geniusee", "https://geniusee.com", "geniusee.com"),
    ("Euristiq", "https://euristiq.com", "euristiq.com"),
    ("BairesDev", "https://www.bairesdev.com", "bairesdev.com"),
    ("Agency Partner Interactive LL", "https://agencypartner.com", "agencypartner.com"),
]

# Common prefixes to try
PREFIXES = ['hello', 'hi', 'info', 'contact', 'sales', 'team', 'support', 'admin', 'office', 'partnerships', 'business', 'growth', 'newbiz', 'inquiry']

def try_email_verification(domain, prefix):
    """Attempt to verify an email by checking if the domain accepts it via SMTP RCPT TO."""
    # This is unreliable but worth a try
    email = f"{prefix}@{domain}"
    return email  # Just return the guess, can't verify without SMTP

def try_playwright(url):
    """Use Playwright to render JS and extract emails."""
    try:
        from playwright.sync_api import sync_playwright
        EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
            context = browser.new_context()
            page = context.new_page()
            
            try:
                page.goto(url, timeout=15000, wait_until='domcontentloaded')
                time.sleep(3)
                content = page.content()
                
                # Also check contact page
                for path in ['/contact', '/about', '/team']:
                    try:
                        page.goto(url + path, timeout=10000, wait_until='domcontentloaded')
                        time.sleep(2)
                        content += page.content()
                    except:
                        pass
                
                # Extract emails
                emails = re.findall(EMAIL_PATTERN, content)
                # Also check for mailto links
                mailto_emails = re.findall(r'mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', content)
                
                combined = list(set(mailto_emails + emails))
                
                # Filter out junk
                good = []
                for e in combined:
                    e_lower = e.lower()
                    # Skip obviously fake/generic
                    if any(x in e_lower for x in ['example', 'domain', 'test', 'sentry', '@2x.', '@3x.', 'googletagmanager', 'gravatar', '.png', '.jpg', '.svg', 'company.com']):
                        continue
                    good.append(e)
                
                return good
            finally:
                page.close()
                context.close()
                browser.close()
    except ImportError:
        return []
    except Exception as e:
        print(f"  Playwright error: {e}")
        return []

def main():
    print("Trying Playwright for 6 missing agencies...\n")
    
    results = {}
    
    for company, url, domain in MISSING:
        print(f"Checking {company} ({domain})...")
        
        # Try Playwright
        emails = try_playwright(url)
        
        # Filter to only keep emails from target domain
        domain_emails = [e for e in emails if domain in e.lower()]
        
        if domain_emails:
            print(f"  FOUND via Playwright: {domain_emails}")
            results[company] = domain_emails
        else:
            # Generate smart guesses based on company name
            company_lower = company.lower().replace(' ', '')
            guesses = [
                f"hello@{domain}",
                f"info@{domain}",
                f"contact@{domain}",
                f"sales@{domain}",
                f"partnerships@{domain}",
                f"business@{domain}",
            ]
            
            # If Playwright found emails from other domains, show them
            other_emails = [e for e in emails if domain not in e.lower()]
            if other_emails:
                print(f"  Found non-domain emails: {other_emails[:5]}")
            
            print(f"  Best guesses: {guesses}")
            results[company] = guesses
        
        time.sleep(2)
    
    print(f"\n{'='*60}")
    print("RESULTS")
    print('='*60)
    
    certain = {}
    guessed = {}
    
    for company, emails in results.items():
        # If Playwright found real emails, those are certain
        # Otherwise they're just guesses
        domain = [d for c, u, d in MISSING if c == company][0]
        real = [e for e in emails if domain in e.lower()]
        if real:
            certain[company] = real
        else:
            guessed[company] = emails
    
    print(f"\nCertain (found on website): {len(certain)}")
    for c, e in certain.items():
        print(f"  ✅ {c}: {e[0]}")
    
    print(f"\nBest guesses (not verified): {len(guessed)}")
    for c, e in guessed.items():
        print(f"  ⚠️ {c}: {e[0]} (try: {', '.join(e[:3])})")
    
    # Update CRM
    from crm import get_crm
    crm = get_crm()
    
    print(f"\nUpdating CRM...")
    updated = 0
    
    # Update certain ones
    for company, emails in certain.items():
        try:
            crm.update_wl_lead(company, {'Email': emails[0], 'Email Score': 'scraped'})
            print(f"  Updated {company}: {emails[0]}")
            updated += 1
        except Exception as e:
            print(f"  Error: {e}")
    
    # Update guessed ones (mark as guessed)
    for company, emails in guessed.items():
        try:
            crm.update_wl_lead(company, {'Email': emails[0], 'Email Score': 'guessed'})
            print(f"  Updated {company}: {emails[0]} (guessed)")
            updated += 1
        except Exception as e:
            print(f"  Error: {e}")
    
    print(f"\nCRM updated: {updated} leads")
    
    # Save
    with open('/home/ubuntu/nanosoft/wl_email_phase2.json', 'w') as f:
        json.dump({'certain': certain, 'guessed': guessed}, f, indent=2)

if __name__ == "__main__":
    main()
