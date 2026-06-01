#!/usr/bin/env python3
"""
NanoSoft JUDGE v3 — Lead Qualification
7-category scoring. Threshold 7+. Prefer 8+.

Scoring:
  +2 Website quality
  +2 Contact method (email required)
  +2 Clear pain point
  +1 Active business
  +1 Hiring/growth signal
  +1 Business quality
  +1 Growth/automation signal

Reject: spam, duplicate, inactive, no contact path
"""
import json, os, re, sys, time, urllib.request, ssl
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
LOG_FILE = os.path.join(NANOSOFT_DIR, "judge_v3.log")
STATE_FILE = os.path.join(NANOSOFT_DIR, "judge_v3_state.json")

sys.path.insert(0, NANOSOFT_DIR)

def log(msg):
    ts = datetime.now(BD_TZ).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, 'a') as f:
            f.write(line + "\n")
    except:
        pass

def fetch_url(url, timeout=10):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return r.status, r.read().decode('utf-8', errors='ignore')
    except:
        return 0, ''

def judge_lead(lead):
    """Score lead 1-10. Returns (score, qualified, details)."""
    score = 0
    details = {}
    
    company = lead.get('Company Name', '').strip()
    website = lead.get('Website', '').strip()
    email = lead.get('Owner Email', '').strip()
    pain_points = lead.get('Pain Point', '').strip()
    
    # ── REJECT RULES (immediate disqualification) ──
    if not email:
        return 0, False, {'reject': 'no_email'}
    
    # Spam patterns
    spam = ['example.com','test.com','filler@','user@domain','john@doe','lorem@','sample@']
    if any(s in email.lower() for s in spam):
        return 0, False, {'reject': 'spam_email'}
    
    # Inactive/parked
    parked = ['for sale','domain for sale','godaddy','afternic','sedo','parking']
    if any(p in company.lower() for p in parked):
        return 0, False, {'reject': 'parked_domain'}
    
    # Company name is garbage
    if re.search(r'&#[0-9]+;', company) or len(company) < 2:
        return 0, False, {'reject': 'garbage_name'}
    
    # ── 1. WEBSITE QUALITY (+2) ──
    web_score = 0
    if website:
        status, html = fetch_url(website, timeout=10)
        if status == 200 and html:
            text = re.sub(r'<[^>]+>', ' ', html)
            words = len(text.split())
            
            if words > 300: web_score += 1
            if words > 800: web_score += 0.5
            if website.startswith('https'): web_score += 0.3
            if re.search(r'<meta[^>]*viewport', html.lower()): web_score += 0.2
            if re.search(r'(wp-content|wordpress|elementor|divi)', html.lower()): web_score += 0.2  # At least has a CMS
            if re.search(r'(react|vue|next\.js|nuxt)', html.lower()): web_score += 0.3  # Modern framework
            details['website_reachable'] = True
            details['word_count'] = words
        else:
            details['website_reachable'] = False
            web_score -= 1
    else:
        web_score -= 1
        details['website_reachable'] = False
    
    score += max(web_score, 0)
    details['website'] = min(web_score, 2)
    
    # ── 2. CONTACT METHOD (+2) ──
    contact_score = 0
    if email:
        ed = email.split('@')[1] if '@' in email else ''
        
        # Business domain email (not free)
        free_domains = ['gmail.com','yahoo.com','hotmail.com','outlook.com','aol.com','protonmail.com','icloud.com','live.com','msn.com','mail.com']
        if ed not in free_domains:
            contact_score += 1.5
            details['email_type'] = 'business'
        else:
            contact_score += 0.5
            details['email_type'] = 'free'
        
        # Email matches website domain
        if website:
            web_domain = re.sub(r'^https?://(www\.)?', '', website).split('/')[0]
            if ed == web_domain or ed.endswith('.' + web_domain):
                contact_score += 0.5
                details['email_matches_domain'] = True
    else:
        # No email = can't do outreach
        return 0, False, {'reject': 'no_email'}
    
    score += min(contact_score, 2)
    details['contact'] = min(contact_score, 2)
    
    # ── 3. CLEAR PAIN POINT (+2) ──
    pain_score = 0
    if pain_points:
        pains = [p.strip() for p in pain_points.split(',') if p.strip()]
        pain_count = len(pains)
        
        if pain_count >= 1: pain_score += 0.5
        if pain_count >= 2: pain_score += 0.5
        if pain_count >= 3: pain_score += 0.5
        if pain_count >= 4: pain_score += 0.5
        
        # High-value pain pains
        high_value = ['no analytics','no live chat','not mobile','no ssl','no booking','no online']
        for pain in pain_points.lower().split(','):
            if any(h in pain for h in high_value):
                pain_score = min(pain_score + 0.5, 2.0)  # Bonus for high-value pains
                details['high_value_pain'] = pain.strip()
                break
    else:
        # No pain point detected — still reachable but not ideal
        pain_score = 0.2
    
    score += min(pain_score, 2)
    details['pain_point'] = min(pain_score, 2)
    
    # ── 4. ACTIVE BUSINESS (+1) ──
    active_score = 0
    if website:
        status, html = fetch_url(website, timeout=10)
        if status == 200 and html:
            if re.search(r'202[345]', html): active_score += 0.3  # Recent year
            if re.search(r'/(blog|news|articles)/', html.lower()): active_score += 0.3  # Active blog
            social = len(re.findall(r'(facebook\.com|instagram\.com|linkedin\.com|yelp\.com|twitter\.com)', html.lower()))
            if social >= 2: active_score += 0.2
            if social >= 3: active_score += 0.2
            details['active_signals'] = active_score
    
    score += min(active_score, 1)
    details['active'] = min(active_score, 1)
    
    # ── 5. HIRING SIGNAL (+1) ──
    hiring_score = 0
    if website:
        _, html = fetch_url(website, timeout=10)
        if html:
            if re.search(r'hiring|we\s+are\s+hiring|join\s+our\s+team|career|now\s+employing|job\s+opening|we\'re\s+growing', html.lower()):
                hiring_score += 1
                details['hiring'] = True
            else:
                details['hiring'] = False
    
    score += min(hiring_score, 1)
    details['hiring'] = min(hiring_score, 1)
    
    # ── 6. BUSINESS QUALITY (+1) ──
    quality_score = 0
    # Real company name (not domain-name-as-company)
    if company and len(company) > 3:
        if re.match(r'^[A-Z]', company) and not re.search(r'\.(com|net|org)', company):
            quality_score += 0.3
        if not re.search(r'[<>]', company) and not re.search(r'[^a-zA-Z0-9\s\'\-\.&,]', company.replace('ñ','n')):
            quality_score += 0.3
    # Has content
    if lead.get('Pain Point',''):
        quality_score += 0.2
    if website and website.startswith('https'):
        quality_score += 0.2
    
    score += min(quality_score, 1)
    details['quality'] = min(quality_score, 1)
    
    # ── 7. GROWTH/AUTOMATION SIGNAL (+1) ──
    growth_score = 0
    if website:
        _, html = fetch_url(website, timeout=10)
        if html:
            # Growth signals
            if re.search(r'grand\s+opening|new\s+location|now\s+serving|expanding', html.lower()):
                growth_score += 0.3
            if re.search(r'award|best\s+of|featured|recognized|rated', html.lower()):
                growth_score += 0.2
            # Automation potential (could benefit from better tools)
            if re.search(r'call\s+us|phone|visit\s+us|walk[\s-]in', html.lower()) and not re.search(r'book|schedule|online', html.lower()):
                growth_score += 0.5  # Relies on phone = can automate
    
    score += min(growth_score, 1)
    details['growth'] = min(growth_score, 1)
    
    final_score = max(1, min(10, round(score)))
    qualified = final_score >= 7
    details['final_score'] = final_score
    details['qualified'] = qualified
    
    return final_score, qualified, details


def judge_all_new():
    """Judge all New leads. Approve 7+, reject <7."""
    from crm import get_crm, STATUS_QUALIFIED, STATUS_UNQUALIFIED
    crm = get_crm()
    
    new_leads = crm.get_leads_by_status('New')
    log(f"[JUDGE] {len(new_leads)} New leads to judge")
    
    approved = 0
    rejected = 0
    
    for lead in new_leads:
        score, qualified, details = judge_lead(lead)
        company = lead.get('Company Name', '?')
        
        # Update score in CRM
        crm.update_lead(company, {'Judge Score': score})
        
        if qualified:
            crm.update_status(company, STATUS_QUALIFIED)
            approved += 1
            log(f"  ✅ {score}/10 {company[:40]} | {details}")
        else:
            crm.update_status(company, STATUS_UNQUALIFIED)
            rejected += 1
            log(f"  ❌ {score}/10 {company[:40]} | {details.get('reject', details.get('final_score'))}")
    
    log(f"[JUDGE] Done: {approved} approved, {rejected} rejected")
    return approved, rejected


if __name__ == "__main__":
    approved, rejected = judge_all_new()
    print(f"\nApproved: {approved}, Rejected: {rejected}")
