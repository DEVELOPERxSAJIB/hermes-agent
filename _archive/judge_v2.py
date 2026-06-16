"""
NanoSoft JUDGE v2 — Lead Qualification
Scores each lead 1-10 based on website quality, business legitimacy,
contact info, activity, relevance, and buying intent.

Score 8-10 = Approved (Status → 'Qualified')
Score < 8 = Rejected (Status → 'Unqualified')
"""
import json
import os
import re
import sys
import time
import urllib.request
import ssl
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
LOG_FILE = os.path.join(NANOSOFT_DIR, "judge_v2.log")

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
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.status, resp.read().decode('utf-8', errors='ignore')
    except:
        return 0, ""


def judge_lead(lead):
    """
    Score a lead from 1-10.
    Returns (score, is_qualified, reasons_dict).
    """
    score = 0
    reasons = {}

    company = lead.get('Company Name', '').strip()
    website = lead.get('Website (if have)', '').strip()
    email = lead.get('Owner Email', '').strip()
    pain_points = lead.get('Pain Point', '').strip()

    # ── 1. Website Quality (0-2 points) ──
    web_score = 0
    if website:
        status, html = fetch_url(website, timeout=10)
        if status == 200 and html:
            text = re.sub(r'<[^>]+>', ' ', html)
            word_count = len(text.split())

            if word_count > 500:
                web_score += 1  # Substantial content
            if word_count > 200:
                web_score += 0.5

            # Modern framework detection
            if re.search(r'(react|vue|angular|next\.js|nuxt|svelte)', html.lower()):
                web_score += 0.5

            # Mobile responsive
            if re.search(r'<meta[^>]*viewport', html.lower()):
                web_score += 0.5

            # Has SSL
            if website.startswith('https'):
                web_score += 0.5

            reasons['website_reachable'] = True
            reasons['word_count'] = word_count
        else:
            reasons['website_reachable'] = False
            web_score -= 2  # Dead website
    else:
        reasons['website_reachable'] = False
        web_score -= 1

    score += max(web_score, 0)
    reasons['website_quality'] = min(web_score, 2)

    # ── 2. Business Legitimacy (0-2 points) ──
    biz_score = 0

    # Real company name (not domain-as-name, not "Home", not HTML garbage)
    if company and len(company) > 2:
        biz_score += 0.5
        # Name looks like a real business
        if re.match(r'^[A-Z]', company) and not re.search(r'\.(com|net|org)', company):
            biz_score += 0.5
        # No HTML entities in name
        if not re.search(r'&#[0-9]+;', company) and not re.search(r'[<>]', company):
            biz_score += 0.5

    # US/UK phone number
    if lead.get('Phone', ''):
        biz_score += 0.5

    reasons['business_legitimacy'] = min(biz_score, 2)
    score += biz_score

    # ── 3. Contact Information Quality (0-2 points) ──
    email_score = 0
    if email:
        # Personal/owner email (firstname@, owner@, etc.)
        if re.match(r'^[a-z]+\.[a-z]+@', email) or re.match(r'^[a-z]+@[a-z]', email):
            email_score += 1.5
        # Business domain email
        elif not any(email.endswith(f'@{d}') for d in ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com']):
            email_score += 1
        # Free domain email (acceptable but lower quality)
        else:
            email_score += 0.5

        # Email domain matches website domain
        if website:
            web_domain = re.sub(r'^https?://(www\.)?', '', website).split('/')[0]
            email_domain = email.split('@')[1] if '@' in email else ""
            if web_domain == email_domain or web_domain.endswith(email_domain) or email_domain.endswith(web_domain):
                email_score += 0.5
    else:
        email_score -= 2  # No email = reject

    reasons['contact_quality'] = min(email_score, 2)
    score += max(email_score, 0)

    # ── 4. Business Activity (0-1 point) ──
    activity_score = 0
    if website:
        status, html = fetch_url(website, timeout=10) if 'html' not in dir() else (200, '')
        if status == 200 and html:
            # Recent year mentions
            if re.search(r'202[345]', html):
                activity_score += 0.5

            # Active blog/news
            if re.search(r'/(blog|news|articles)/', html.lower()):
                activity_score += 0.3

            # Active social media links
            social_count = len(re.findall(r'(facebook\.com|instagram\.com|linkedin\.com|twitter\.com|yelp\.com)', html.lower()))
            if social_count >= 2:
                activity_score += 0.2

    reasons['business_activity'] = min(activity_score, 1)
    score += activity_score

    # ── 5. Relevance to Our Services (0-1 point) ──
    relevance_score = 0
    if pain_points:
        # More pain points = more relevant (they need help)
        pains = [p.strip() for p in pain_points.split(',') if p.strip()]
        relevance_score += min(len(pains) * 0.3, 1.0)

    reasons['relevance'] = min(relevance_score, 1)
    score += relevance_score

    # ── 6. Buying Intent Signals (0-1 point) ──
    intent_score = 0
    if pain_points:
        # High-intent pain points
        high_intent = ['no analytics', 'no live chat', 'not mobile', 'no ssl', 'slow']
        for pain in pain_points.lower().split(','):
            if any(h in pain for h in high_intent):
                intent_score += 0.3
        intent_score = min(intent_score, 1.0)

    reasons['buying_intent'] = intent_score
    score += intent_score

    # ── PENALTIES ──
    # Parked domain
    if website and company and ('for sale' in company.lower() or 'is for sale' in company.lower()):
        score -= 3
        reasons['penalty'] = 'parked_domain'

    # Garbage email
    if email and any(e in email for e in ['example.com', 'filler@', 'user@domain', 'link@', 'john@doe']):
        score -= 3
        reasons['penalty'] = 'fake_email'

    # Non-US/UK business name (Chinese, etc.)
    if company and re.search(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff]', company):
        score -= 2
        reasons['penalty'] = 'foreign_language'

    final_score = max(1, min(10, round(score)))
    is_qualified = final_score >= 8

    reasons['final_score'] = final_score
    reasons['qualified'] = is_qualified

    return final_score, is_qualified, reasons


def judge_all_new():
    """
    Judge all 'New' leads in CRM.
    Approved leads → Status becomes 'Qualified'
    Rejected leads → Status becomes 'Unqualified'
    Returns (approved_count, rejected_count)
    """
    from crm import get_crm, STATUS_QUALIFIED, STATUS_UNQUALIFIED
    crm = get_crm()

    new_leads = crm.get_leads_by_status('New')
    log(f"[JUDGE] Found {len(new_leads)} New leads to judge")

    approved = 0
    rejected = 0

    for lead in new_leads:
        score, qualified, reasons = judge_lead(lead)
        company = lead.get('Company Name', '?')
        email = lead.get('Owner Email', '')

        if qualified:
            crm.update_status(company, STATUS_QUALIFIED)
            approved += 1
            log(f"  ✅ {score}/10 {company[:40]} | {email[:35]} | {reasons}")
        else:
            crm.update_status(company, STATUS_UNQUALIFIED)
            rejected += 1
            log(f"  ❌ {score}/10 {company[:40]} | {email[:35]} | {reasons}")

    log(f"[JUDGE] Done: {approved} approved, {approved + rejected} total")
    return approved, rejected


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='NanoSoft JUDGE v2')
    parser.add_argument('--judge-all', action='store_true', help='Judge all New leads')
    args = parser.parse_args()

    if args.judge_all:
        approved, rejected = judge_all_new()
        print(f"\nResult: {approved} approved, {rejected} rejected")
