#!/usr/bin/python3
"""
NanoSoft EMAIL-FINDER v1 — Pattern-based + SMTP verification
For leads that don't have scraped emails, try common patterns:
- info@domain, hello@domain, contact@domain etc.
- Verify via SMTP RCPT TO
"""
import os, re, sys, time, subprocess, socket, csv, json
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
sys.path.insert(0, NANOSOFT_DIR)

COMMON_PREFIXES = [
    'info', 'hello', 'contact', 'sales', 'team', 'hi', 'us',
    'enquiries', 'enquiry', 'support', 'business', 'partners',
    'office', 'admin', 'inbox', 'mail', 'general',
]

def log(msg):
    ts = datetime.now(BD_TZ).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [EMAIL-FIND] {msg}", flush=True)

def smtp_verify(domain, email, timeout=10):
    """Verify email exists via SMTP RCPT TO."""
    try:
        # Get MX record
        import dns.resolver
        try:
            mx_records = dns.resolver.resolve(domain, 'MX')
            mx_host = str(mx_records[0].exchange).rstrip('.')
        except:
            mx_host = domain
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((mx_host, 25))
        
        banner = sock.recv(1024).decode('utf-8', errors='ignore')
        if not banner.startswith('220'):
            sock.close()
            return False
        
        sock.send(f'HELO nanosoft.test\r\n'.encode())
        sock.recv(1024)
        
        sock.send(f'MAIL FROM:<verify@nanosoft.test>\r\n'.encode())
        sock.recv(1024)
        
        sock.send(f'RCPT TO:<{email}>\r\n'.encode())
        resp = sock.recv(1024).decode('utf-8', errors='ignore')
        
        sock.send(b'QUIT\r\n')
        sock.close()
        
        return resp.startswith('250')
    except:
        return False

def guess_emails(domain):
    """Try common email patterns with SMTP verification."""
    for prefix in COMMON_PREFIXES:
        email = f"{prefix}@{domain}"
        # Quick check: try SMTP
        if smtp_verify(domain, email):
            return email
        time.sleep(0.5)
    return ''

def find_emails_from_website(domain):
    """Try to find emails by scraping more pages."""
    from urllib.request import urlopen, Request
    
    paths = ['/team', '/about', '/contact', '/people', '/staff', '/leadership', '/management']
    for path in paths:
        try:
            url = f"https://{domain}{path}"
            req = Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
            resp = urlopen(req, timeout=8)
            html = resp.read().decode('utf-8', errors='ignore')
            emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', html)
            for e in emails:
                el = e.lower()
                bad = ['example@','test@','noreply','no-reply','sentry','@whois','vue@3','@scorebig',
                       '@afternic','john@doe','feedback@','user@domain','@sentry','@bytedance',
                       'help@','support@','admin@','webmaster@','postmaster@','abuse@','privacy@','janedoe']
                if not any(b in el for b in bad):
                    if any(kw in el for kw in ['info@','hello@','sales@','contact@','team@','enquir']):
                        return e
        except:
            continue
    return ''

def main():
    log("Email Finder v1 starting...")
    
    try:
        import dns.resolver
        HAS_DNS = True
    except:
        HAS_DNS = False
        log("dnspython not installed, SMTP verify disabled. pip install dnspython")
    
    from crm import get_crm
    crm = get_crm()
    leads = crm.get_wl_all()
    
    # Find leads without emails that are New or Unqualified (but have wl signals)
    no_email_leads = [l for l in leads if l.get('Status') in ['New', 'Unqualified'] 
                      and l.get('Website') and not l.get('Email','').strip()]
    
    log(f"Found {len(no_email_leads)} leads without emails")
    
    found = 0
    for l in no_email_leads:
        company = l.get('Company Name', '')
        website = l.get('Website', '')
        domain_match = re.search(r'https?://(?:www\.)?([^/]+)', website)
        if not domain_match:
            continue
        domain = domain_match.group(1)
        
        log(f"  Trying {company} ({domain})...")
        
        # Try website scraping first
        email = find_emails_from_website(domain)
        
        # If not found, try SMTP verification
        if not email and HAS_DNS:
            email = guess_emails(domain)
        
        if email:
            crm.update_wl_lead(company, {'Email': email, 'Email Score': 'found_v1'})
            log(f"    ✅ Found: {email}")
            found += 1
        else:
            log(f"    ❌ Nothing")
        
        time.sleep(1)
    
    log(f"DONE: Found emails for {found}/{len(no_email_leads)} leads")

if __name__ == '__main__':
    main()
