#!/usr/bin/env python3
"""
Scrape emails from White Label agency websites.
Visits each site's contact/about/team pages and extracts email addresses.
"""
import urllib.request, re, time, json, sys

sys.path.insert(0, '/home/ubuntu/nanosoft')
from crm import get_crm

# Pages to check on each site
PATHS = ['', '/contact', '/about', '/team', '/about-us', '/contact-us', '/people', '/staff', '/leadership', '/founders']

# Email regex pattern
EMAIL_PATTERN = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

# Skip generic emails
SKIP_PATTERNS = [
    r'.*@example\.', r'.*@domain\.', r'.*@test\.', r'.*@sentry\.',
    r'.*@bytedance\.', r'.*@scorebig\.', r'.*@afternic\.', r'.*@whois\.',
    r'vue@3\.', r'.*feedback@.*', r'.*@s3\.amazonaws\.', r'@wixpress\.',
    r'.*@googletagmanager\.', r'.*@googleapis\.', r'.*@cloudflare\.',
    r'.*@doubleclick\.', r'.*@facebook\.', r'.*@linkedin\.', r'.*@twitter\.',
    r'.*@github\.', r'.*@gravatar\.', r'.*@wordpress\.', r'.*@nginx\.',
    r'.*@godaddy\.', r'.*@aws\.', r'.*@hubspot\.', r'.*@mailchimp\.',
    r'.*@intercom\.', r'.*@zendesk\.', r'.*@typeform\.', r'.*@calendly\.',
    r'.*@stripe\.', r'.*@paypal\.', r'.*@shopify\.', r'.*@cloudfront\.',
    r'^\d+@',  # skip numbered emails like 311286545@qq.com
]

# Priority: look for these role words near emails
ROLE_KEYWORDS = ['founder', 'ceo', 'co-founder', 'cto', 'director', 'head', 'lead', 'manager', 'partner', 'principal', 'owner', 'president']

def is_good_email(email):
    """Check if email is worth keeping."""
    email_lower = email.lower()
    for pat in SKIP_PATTERNS:
        if re.match(pat, email_lower):
            return False
    # Skip image file extensions that get caught by regex
    for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico']:
        if email_lower.endswith(ext):
            return False
    return True


def scrape_emails_from_page(url, domain):
    """Try to fetch a page and extract emails."""
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml',
        })
        with urllib.request.urlopen(req, timeout=12) as resp:
            content = resp.read().decode('utf-8', errors='replace')
            
            # Look for mailto: links first (highest quality)
            mailto_emails = re.findall(r'mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', content)
            
            # Also look for emails in text
            all_emails = re.findall(EMAIL_PATTERN, content)
            
            combined = list(set(mailto_emails + all_emails))
            
            # Filter
            good = [e for e in combined if is_good_email(e)]
            
            # Remove common false positives
            filtered = []
            for e in good:
                # Skip if it looks like a variable name (e.g., "name@company" in JS code)
                if any(kw in e.lower() for kw in ['noreply', 'no-reply', 'donotreply', 'mailer-daemon', 'postmaster', 'info', 'hello', 'contact', 'support', 'sales', 'admin', 'webmaster', 'abuse', 'spam', 'legal', 'privacy', 'security', 'jobs', 'careers', 'press', 'media', 'partners', 'affiliates', 'advertising', 'billing', 'accounts', 'finance', 'hr', 'recruiting', 'tech', 'help', 'feedback', 'suggestions', 'enquiries', 'inquiries']):
                    # These are team emails, still useful but lower priority
                    pass
                filtered.append(e)
            
            return filtered
    except Exception as e:
        return []


def scrape_agency(company, website):
    """Scrape all pages of an agency website for emails."""
    base = website.rstrip('/')
    domain = re.sub(r'^https?://(www\.)?', '', base).split('/')[0]
    
    all_emails = set()
    pages_checked = []
    
    for path in PATHS:
        url = base + path
        emails = scrape_emails_from_page(url, domain)
        if emails:
            pages_checked.append(f"{path or '/'}: {emails}")
            for e in emails:
                # Only keep emails from the target domain
                email_domain = e.split('@')[-1].lower()
                domain_lower = domain.lower()
                if email_domain == domain_lower or email_domain.endswith('.' + domain_lower):
                    all_emails.add(e)
                elif domain_lower in email_domain or email_domain in domain_lower:
                    all_emails.add(e)
                else:
                    # Keep personal-looking emails from other domains (firstname.lastname@)
                    local = e.split('@')[0]
                    if '.' in local and len(local) > 3:
                        all_emails.add(e)
    
    return list(all_emails), pages_checked


def main():
    crm = get_crm()
    wl_leads = crm.get_wl_all()
    
    print(f"Scraping emails from {len(wl_leads)} White Label agency websites...\n")
    
    results = []
    
    for i, lead in enumerate(wl_leads):
        company = lead.get('Company Name', '').strip()
        website = lead.get('Website', '').strip()
        email_existing = lead.get('Email', '').strip()
        
        # Skip if already has email
        if email_existing:
            print(f"[{i+1}/{len(wl_leads)}] SKIP {company} (already has email: {email_existing})")
            results.append({'company': company, 'existing': email_existing, 'found': []})
            continue
        
        print(f"[{i+1}/{len(wl_leads)}] Scraping {company} ({website})...")
        
        emails, pages = scrape_agency(company, website)
        
        if emails:
            print(f"  FOUND: {emails}")
        else:
            print(f"  No emails found on website pages")
        
        for p in pages:
            print(f"    {p}")
        
        results.append({
            'company': company,
            'website': website,
            'existing': email_existing,
            'found': emails,
            'owner_name': lead.get('Owner Name', ''),
            'owner_linkedin': lead.get('Owner LinkedIn URL', ''),
            'country': lead.get('Country', ''),
        })
        
        time.sleep(1)  # Be polite
    
    # Summary
    print(f"\n{'='*60}")
    print("RESULTS SUMMARY")
    print('='*60)
    
    with_email = []
    without_email = []
    
    for r in results:
        if r['found'] or r['existing']:
            with_email.append(r)
        else:
            without_email.append(r)
    
    print(f"\nLeads WITH emails found: {len(with_email)}")
    for r in with_email:
        email = r['existing'] if r['existing'] else r['found']
        print(f"  ✅ {r['company']}: {email}")
    
    print(f"\nLeads WITHOUT emails (need alternative approach): {len(without_email)}")
    for r in without_email:
        print(f"  ❌ {r['company']} | {r['website']} | Owner: {r['owner_name'] or 'N/A'} | LinkedIn: {r['owner_linkedin'] or 'N/A'}")
    
    # Update CRM with found emails
    print(f"\n{'='*60}")
    print("Updating CRM with found emails...")
    updated = 0
    for r in results:
        if r['found'] and not r['existing']:
            # Use first found email
            email = r['found'][0]
            try:
                crm.update_wl_lead(r['company'], {'Email': email, 'Email Score': 'scraped'})
                print(f"  Updated {r['company']}: {email}")
                updated += 1
            except Exception as e:
                print(f"  Error updating {r['company']}: {e}")
    
    print(f"\nCRM updated: {updated} leads")
    
    # Save results to file
    with open('/home/ubuntu/nanosoft/wl_email_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to wl_email_results.json")

if __name__ == "__main__":
    main()
