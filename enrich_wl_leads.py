#!/usr/bin/python3
"""
Enrich White Label leads - crash proof version.
Uses urllib first, Playwright as fallback only for sites that need JS.
"""
import json, os, re, sys, time, urllib.request
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"

sys.path.insert(0, NANOSOFT_DIR)
from crm import get_crm

SERVICE_KEYWORDS = {
    'web development': ['web development', 'web dev', 'website development', 'web app', 'web application', 'frontend', 'front-end', 'backend', 'back-end', 'full-stack', 'fullstack', 'react', 'angular', 'vue', 'node.js', 'django', 'laravel', 'ruby on rails'],
    'mobile development': ['mobile development', 'mobile app', 'ios development', 'android development', 'react native', 'flutter', 'swift', 'kotlin mobile'],
    'UI/UX design': ['ui/ux', 'user experience', 'user interface', 'ux design', 'ui design', 'product design', 'design system', 'figma'],
    'cloud/DevOps': ['cloud', 'devops', 'aws', 'azure', 'gcp', 'kubernetes', 'docker', 'infrastructure as code'],
    'AI/ML': ['artificial intelligence', 'machine learning', 'ai/ml', 'data science', 'deep learning', 'nlp', 'generative ai', 'chatbot'],
    'eCommerce': ['ecommerce', 'e-commerce', 'shopify', 'magento', 'woocommerce'],
    'SaaS': ['saas', 'software as a service', 'platform development', 'product development'],
    'QA/Testing': ['qa', 'quality assurance', 'testing', 'automated testing', 'test automation', 'ci/cd'],
    'consulting': ['consulting', 'strategy', 'digital transformation', 'advisory', 'cto as a service'],
    'staff augmentation': ['staff augmentation', 'team extension', 'dedicated team', 'remote team', 'outsourcing', 'nearshore', 'offshore', 'staffing', 'extended team'],
    'white label': ['white label', 'white-label', 'whitelabel', 'white label development', 'partner development', 'reseller', 'agency partner'],
    'MVP development': ['mvp', 'minimum viable', 'prototype', 'proof of concept'],
    'custom software': ['custom software', 'bespoke software', 'tailored software', 'software development'],
}

WL_SIGNALS = ['white label', 'white-label', 'whitelabel', 'partner', 'partnership', 'reseller', 'agency partner', 'staff augmentation', 'team extension', 'dedicated team', 'outsourcing', 'offshore', 'nearshore', 'staffing', 'extended team', 'development partner', 'technology partner']


def fetch_url(url):
    """Fetch URL with urllib."""
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml',
        })
        with urllib.request.urlopen(req, timeout=12) as resp:
            content = resp.read().decode('utf-8', errors='replace')
            text = re.sub(r'<script[^>]*>.*?</script>', ' ', content, flags=re.DOTALL)
            text = re.sub(r'<style[^>]*>.*?</style>', ' ', text, flags=re.DOTALL)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'&nbsp;', ' ', text)
            text = re.sub(r'&amp;', '&', text)
            text = re.sub(r'\s+', ' ', text).strip()
            return text
    except:
        return ''


def fetch_site_playwright(url):
    """Fetch URL with Playwright (crash-proof per-page)."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
            except:
                return ''
            try:
                context = browser.new_context(user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36')
            except:
                try: browser.close()
                except: pass
                return ''
            try:
                page = context.new_page()
                page.goto(url, timeout=15000, wait_until='domcontentloaded')
                time.sleep(3)
                text = page.inner_text('body') or ''
            except:
                text = ''
            finally:
                try: page.close()
                except: pass
                try: context.close()
                except: pass
                try: browser.close()
                except: pass
            return text
    except:
        return ''


def scrape_agency(website):
    """Scrape agency website for services, pain points, WL signals, LinkedIn."""
    base = website.rstrip('/')
    
    # Pages to check
    paths = ['', '/services', '/about', '/what-we-do', '/capabilities', '/expertise', '/solutions', '/offerings']
    
    all_text = ''
    linkedin_found = ''
    
    for path in paths:
        url = base + path
        text = fetch_url(url)
        if text:
            all_text += ' ' + text
        
        time.sleep(0.5)
    
    # If we got very little text, try Playwright
    if len(all_text) < 500:
        print("    Trying Playwright for JS content...")
        for path in ['', '/services', '/about']:
            text = fetch_site_playwright(base + path)
            if text:
                all_text += ' ' + text
            time.sleep(1)
    
    text_lower = all_text.lower()
    
    # Extract services
    services = []
    for service, keywords in SERVICE_KEYWORDS.items():
        # Check keyword density, not just presence
        count = sum(1 for kw in keywords if kw in text_lower)
        if count > 0:
            services.append(service)
    
    # Extract WL signals
    wl_found = []
    for signal in WL_SIGNALS:
        if signal in text_lower:
            if not any(signal in s or s in signal for s in wl_found):
                wl_found.append(signal)
    
    # Extract LinkedIn company URL
    li_match = re.search(r'(?:https?://)?(?:www\.)?linkedin\.com/company/([a-zA-Z0-9_-]+)', all_text)
    if li_match:
        linkedin_found = f"https://www.linkedin.com/company/{li_match.group(1)}"
    
    # Infer pain points
    pain_points = infer_pain_points(text_lower, services, wl_found)
    
    return {
        'services': ', '.join(services) if services else '',
        'wl_signals': ', '.join(wl_found) if wl_found else '',
        'pain_points': pain_points,
        'linkedin': linkedin_found,
    }


def infer_pain_points(text, services_list, wl_signals):
    """Infer pain points for dev agencies."""
    points = []
    services_lower = ', '.join(services_list).lower() if services_list else ''
    
    # Based on white label signals
    if any(s in ' '.join(wl_signals).lower() for s in ['partner', 'white label', 'reseller', 'agency']):
        points.append('actively seeking development partners for overflow')
    elif any(s in ' '.join(wl_signals).lower() for s in ['staff augmentation', 'outsourcing', 'offshore', 'nearshore', 'dedicated team']):
        points.append('capacity constraints during peak demand')
    
    # Based on services offered
    if 'mobile development' in services_lower and 'web development' not in services_lower:
        points.append('likely has web expertise gaps requiring partner support')
    elif 'web development' in services_lower and 'mobile development' not in services_lower:
        points.append('likely has mobile expertise gaps requiring partner support')
    
    # Based on hiring signals in text
    if 'hiring' in text or 'we are looking' in text or 'careers' in text or 'join our team' in text:
        points.append('scaling fast, likely needs reliable dev capacity')
    
    # Default
    if not points:
        points.append('standard dev agency capacity and expertise gaps')
    
    return ', '.join(points[:2])


def main():
    crm = get_crm()
    wl = crm.get_wl_all()
    
    # Only enrich leads that need it: empty services OR empty WL signals
    # Skip leads that are already enriched or have been judged/sent
    skip_statuses = {'T1 Sent', 'T2 Sent', 'T3 Sent', 'T4 Sent', 'Unqualified', 'Sent'}
    to_enrich = []
    skipped = 0
    for lead in wl:
        status = lead.get('Status', '').strip()
        if status in skip_statuses:
            skipped += 1
            continue
        existing_services = lead.get('Services', '').strip()
        existing_wl = lead.get('White Label Signals', '').strip()
        if not existing_services or not existing_wl:
            to_enrich.append(lead)
        else:
            skipped += 1
    
    print(f"Enrichment: {len(to_enrich)} leads need enrichment, {skipped} skipped (already done or judged/sent)\n")
    
    if not to_enrich:
        print("Nothing to enrich.")
        return
    
    enriched = 0
    for i, lead in enumerate(to_enrich):
        company = lead.get('Company Name', '').strip()
        website = lead.get('Website', '').strip()
        existing_services = lead.get('Services', '').strip()
        existing_pain = lead.get('Pain Point', '').strip()
        existing_wl = lead.get('White Label Signals', '').strip()
        existing_linkedin = lead.get('LinkedIn', '').strip()
        
        print(f"[{i+1}/{len(to_enrich)}] {company} ({website})")
        
        data = scrape_agency(website)
        
        updates = {}
        if data['services'] and not existing_services:
            updates['Services'] = data['services']
            print(f"    Services: {data['services']}")
        
        if data['wl_signals'] and not existing_wl:
            updates['White Label Signals'] = data['wl_signals']
            print(f"    WL Signals: {data['wl_signals']}")
        
        if data['pain_points'] and not existing_pain:
            updates['Pain Point'] = data['pain_points']
            print(f"    Pain Points: {data['pain_points']}")
        
        if data['linkedin'] and not existing_linkedin:
            updates['LinkedIn'] = data['linkedin']
            print(f"    LinkedIn: {data['linkedin']}")
        
        if updates:
            try:
                crm.update_wl_lead(company, updates)
                print(f"    Updated: {list(updates.keys())}")
                enriched += 1
            except Exception as e:
                print(f"    CRM error: {e}")
        else:
            print(f"    (no new data)")
        
        print()
        time.sleep(0.5)
    
    print(f"DONE: {enriched}/{len(to_enrich)} leads enriched")


if __name__ == "__main__":
    main()
