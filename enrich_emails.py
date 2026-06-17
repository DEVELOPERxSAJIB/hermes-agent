#!/usr/bin/env python3
"""Enrich New leads without email by scraping their websites"""
import sys, os, re, time, json, urllib.request
from urllib.parse import urljoin, urlparse
from html import unescape
from urllib.request import unquote

sys.path.insert(0, '/home/ubuntu/nanosoft')
from crm import get_crm

BD_TZ = __import__('datetime').timezone(__import__('datetime').timedelta(hours=6))

EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
GENERIC_EMAILS = {'user@domain.com','info@example.com','test@test.com','admin@localhost',
    'john@example.com','jane@example.com','email@example.com','name@example.com',
    'yourname@example.com','info@domain.com','contact@domain.com','mail@domain.com'}

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def fetch_page(url, timeout=6):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode('utf-8', errors='ignore')
    except:
        return None

def scrape_emails(url):
    emails = set()
    html = fetch_page(url)
    if not html:
        return emails
    
    # Decode obfuscated HTML
    html = unescape(html)
    
    # mailto links
    for m in re.findall(r'mailto:([^\s"<>]+)', html):
        email = unquote(m).strip().rstrip('\\')
        if '@' in email and not any(g in email for g in GENERIC_EMAILS):
            emails.add(email.lower())
    
    # Plain text emails
    for m in EMAIL_RE.findall(html):
        if not any(g in m for g in GENERIC_EMAILS):
            emails.add(m.lower())
    
    # Try contact page
    if len(emails) < 2:
        contact_urls = []
        for m in re.findall(r'href=["\']([^"\']*contact[^"\']*)["\']', html, re.I):
            contact_urls.append(urljoin(url, m))
        for cu in contact_urls[:2]:
            ch = fetch_page(cu)
            if ch:
                ch = unescape(ch)
                for m in re.findall(r'mailto:([^\s"<>]+)', ch):
                    email = unquote(m).strip().rstrip('\\')
                    if '@' in email and not any(g in email for g in GENERIC_EMAILS):
                        emails.add(email.lower())
                for m in EMAIL_RE.findall(ch):
                    if not any(g in m for g in GENERIC_EMAILS):
                        emails.add(m.lower())
            if len(emails) >= 2:
                break
            time.sleep(2)
    
    return emails

crm = get_crm()
wl = crm.get_wl_all()

# New leads without email but with website
to_enrich = []
for l in wl:
    if l.get('Status','').strip() != 'New': continue
    if l.get('Email','').strip(): continue
    website = l.get('Website','').strip()
    if website:
        to_enrich.append(l)

print(f'Leads to enrich: {len(to_enrich)}')

enriched = 0
for i, l in enumerate(to_enrich):
    company = l.get('Company Name','')
    website = l.get('Website','')
    
    print(f'[{i+1}/{len(to_enrich)}] {company} ({website})')
    emails = scrape_emails(website)
    
    if emails:
        # Pick best email (prefer info@, hello@, contact@)
        best = None
        for prefix in ['info@', 'hello@', 'contact@', 'sales@', 'team@']:
            for e in emails:
                if e.startswith(prefix):
                    best = e
                    break
            if best:
                break
        if not best:
            best = sorted(emails)[0]
        
        print(f'  Found: {best}')
        try:
            crm.update_wl_lead(company, {'Email': best})
            enriched += 1
            time.sleep(1)
        except Exception as e:
            print(f'  CRM error: {e}')
    else:
        print(f'  No email found')
    
    time.sleep(2)  # Rate limit

print(f'\nEnriched {enriched} leads with emails')
