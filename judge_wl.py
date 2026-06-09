#!/usr/bin/python3
"""
NanoSoft JUDGE-WL v1 — White Label Agency Qualification
Scores agency leads on partnership potential.

Scoring criteria (threshold 7+ to qualify):
  +2  Email found (must have contact email)
  +2  White Label signals (partner, white-label, outsourcing, etc.)
  +2  Services match (relevant dev services: web, mobile, AI/ML, cloud, etc.)
  +1  Pain point clarity (overflow, capacity, growth, scaling)
  +1  Staff augmentation / dedicated team signals
  +1  Geographic fit (US/UK/CA/AU preferred, EU acceptable)
  +1  Services diversity (3+ service areas = well-rounded partner)

Reject: no email, spam, no WL signals, no relevant services
"""
import json, os, re, sys
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
LOG_FILE = os.path.join(NANOSOFT_DIR, "judge_wl.log")

sys.path.insert(0, NANOSOFT_DIR)

PREFERRED_COUNTRIES = ['US', 'USA', 'United States', 'UK', 'United Kingdom', 'GB', 'England',
                       'CA', 'Canada', 'AU', 'Australia', 'NZ', 'New Zealand',
                       'IE', 'Ireland', 'DE', 'Germany', 'NL', 'Netherlands',
                       'SE', 'Sweden', 'NO', 'Norway', 'DK', 'Denmark', 'FI', 'Finland',
                       'CH', 'Switzerland', 'AT', 'Austria', 'BE', 'Belgium',
                       'FR', 'France', 'ES', 'Spain', 'IT', 'Italy', 'PL', 'Poland',
                       'CZ', 'Czech', 'SK', 'Slovakia', 'HU', 'Hungary', 'RO', 'Romania',
                       'BG', 'Bulgaria', 'HR', 'Croatia', 'SI', 'Slovenia',
                       'EE', 'Estonia', 'LV', 'Latvia', 'LT', 'Lithuania',
                       'PT', 'Portugal', 'GR', 'Greece', 'MT', 'Malta', 'CY', 'Cyprus',
                       'AE', 'UAE', 'United Arab Emirates', 'SG', 'Singapore',
                       'JP', 'Japan', 'KR', 'South Korea', 'HK', 'Hong Kong',
                       'IL', 'Israel', 'QA', 'Qatar', 'BH', 'Bahrain', 'KW', 'Kuwait',
                       'SA', 'Saudi', 'ZA', 'South Africa', 'KE', 'Kenya', 'NG', 'Nigeria']

EU_COUNTRIES = ['PL', 'Poland', 'CZ', 'Czech', 'SK', 'Slovakia', 'HU', 'Hungary',
                'RO', 'Romania', 'BG', 'Bulgaria', 'HR', 'Croatia', 'SI', 'Slovenia',
                'EE', 'Estonia', 'LV', 'Latvia', 'LT', 'Lithuania', 'UA', 'Ukraine',
                'DE', 'Germany', 'NL', 'Netherlands', 'BE', 'Belgium', 'AT', 'Austria',
                'CH', 'Switzerland', 'FR', 'France', 'ES', 'Spain', 'IT', 'Italy',
                'PT', 'Portugal', 'GR', 'Greece', 'IE', 'Ireland', 'DK', 'Denmark',
                'SE', 'Sweden', 'NO', 'Norway', 'FI', 'Finland', 'MT', 'Malta', 'CY', 'Cyprus',
                'LU', 'Luxembourg', 'IS', 'Iceland', 'LI', 'Liechtenstein']

DEV_SERVICES = ['web development', 'mobile development', 'UI/UX design', 'cloud/DevOps',
                'AI/ML', 'eCommerce', 'SaaS', 'QA/Testing', 'custom software',
                'staff augmentation', 'consulting', 'MVP development', 'white label']

WL_SIGNAL_KEYWORDS = ['partner', 'partnership', 'white label', 'white-label', 'whitelabel',
                      'reseller', 'agency partner', 'staff augmentation', 'team extension',
                      'dedicated team', 'outsourcing', 'offshore', 'nearshore', 'staffing',
                      'extended team', 'development partner', 'technology partner',
                      'outsource', 'outsource', 'subcontract', 'sub-contract',
                      'referral', 'refer', 'collaborate', 'collaboration',
                      'joint venture', 'strategic alliance', 'channel partner',
                      'vendor', 'supplier', 'contractor', 'freelance', 'talent network',
                      'capacity partner', 'overflow partner', 'backup team',
                      'silent partner', 'white label development', 'rebrand', 're-brand',
                      'private label', 'label partner', 'co-development', 'co-develop',
                      'build partner', 'delivery partner', 'engineering partner',
                      'tech partner', 'IT partner', 'dev partner', 'code partner',
                      'squad', 'pod', 'team as a service', 'TaaS', 'developers on demand',
                      'on-demand team', 'elastic team', 'flexible team', 'scale team',
                      'team scaling', 'team scale', 'ramp up', 'ramp down',
                      'quick start', 'fast start', 'immediate start', 'ready to start',
                      'available now', 'open for projects', 'accepting projects',
                      'new projects', 'project-based', 'project based',
                      'engagement model', 'cooperation', 'co-operation',
                      'mutual', 'win-win', 'win win', 'long-term', 'long term',
                      'ongoing', 'retained', 'retainer', 'monthly', 'quarterly']

PAIN_KEYWORDS = ['overflow', 'capacity', 'scaling', 'growth', 'demand', 'backlog',
                 'bandwidth', 'resource', 'staffing', 'hiring', 'talent shortage',
                 'skill gap', 'expertise gap', 'delivery', 'deadline', 'timeline',
                 'client', 'project', 'workload', 'stretch', 'turn down', 'decline',
                 'missed opportunity', 'lost revenue', 'bottleneck', 'constraint',
                 'peak', 'seasonal', 'spike', 'surge', 'ramp', 'onboard', 'offboard',
                 'attrition', 'retention', 'turnover', 'burnout', 'overworked',
                 'understaffed', 'short-staffed', 'short staffed', 'fully booked',
                 'booked', 'committed', 'capacity planning', 'resource planning',
                 'workforce planning', 'headcount', 'FTE', 'contractor', 'freelancer',
                 'augmentation', 'supplement', 'complement', 'extend', 'extension',
                 'scale', 'flexible', 'elastic', 'variable', 'fluctuating',
                 'uncertain', 'volatile', 'unpredictable', 'seasonal', 'cyclical']


def log(msg):
    ts = datetime.now(BD_TZ).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, 'a') as f:
            f.write(line + "\n")
    except:
        pass


def judge_wl_lead(lead):
    """
    Score WL agency lead 0-10.
    Returns (score, qualified, details_dict).
    Threshold: 7+ = Qualified, <7 = Unqualified
    """
    score = 0
    details = {}

    company = lead.get('Company Name', '').strip()
    email = lead.get('Email', '').strip()
    services_str = lead.get('Services', '').strip()
    signals_str = lead.get('White Label Signals', '').strip()
    pain_str = lead.get('Pain Point', '').strip()
    country = lead.get('Country', '').strip()
    website = lead.get('Website', '').strip()

    # ── +2 Email found ──
    if email and '@' in email and '.' in email:
        score += 2
        details['email'] = f'+2 ({email})'
    else:
        details['email'] = '+0 (no email)'

    # ── +2 White Label signals ──
    if signals_str:
        signals_lower = signals_str.lower()
        wl_score = 0
        for kw in WL_SIGNAL_KEYWORDS:
            if kw in signals_lower:
                wl_score += 1
        if wl_score >= 2:
            score += 2
            details['wl_signals'] = f'+2 ({signals_str[:60]})'
        elif wl_score >= 1:
            score += 1
            details['wl_signals'] = f'+1 ({signals_str[:60]})'
        else:
            details['wl_signals'] = '+0 (no WL signals)'
    else:
        details['wl_signals'] = '+0 (empty)'

    # ── +2 Services match ──
    if services_str:
        services_lower = services_str.lower()
        dev_match = sum(1 for s in DEV_SERVICES if s.lower() in services_lower)
        if dev_match >= 3:
            score += 2
            details['services'] = f'+2 ({services_str[:60]})'
        elif dev_match >= 1:
            score += 1
            details['services'] = f'+1 ({services_str[:60]})'
        else:
            details['services'] = '+0 (no relevant services)'
    else:
        details['services'] = '+0 (empty)'

    # ── +1 Pain point clarity ──
    if pain_str:
        pain_lower = pain_str.lower()
        pain_score = sum(1 for kw in PAIN_KEYWORDS if kw in pain_lower)
        if pain_score >= 2:
            score += 1
            details['pain'] = f'+1 ({pain_str[:60]})'
        elif pain_score >= 1:
            score += 1
            details['pain'] = f'+1 ({pain_str[:60]})'
        else:
            details['pain'] = '+0 (generic pain)'
    else:
        details['pain'] = '+0 (empty)'

    # ── +1 Staff augmentation signals ──
    sa_keywords = ['staff augmentation', 'dedicated team', 'outsourcing', 'offshore',
                   'nearshore', 'staffing', 'team extension', 'extended team']
    combined = f'{signals_str} {services_str} {pain_str}'.lower()
    if any(kw in combined for kw in sa_keywords):
        score += 1
        details['sa_signals'] = '+1'
    else:
        details['sa_signals'] = '+0'

    # ── +1 Geographic fit ──
    country_lower = country.lower()
    if any(c.lower() in country_lower for c in PREFERRED_COUNTRIES):
        score += 1
        details['geo'] = f'+1 ({country})'
    elif country:
        details['geo'] = f'+0 ({country} - non-preferred)'
    else:
        details['geo'] = '+0 (no country)'

    # ── +1 Services diversity (3+ areas) ──
    if services_str:
        svc_count = len([s.strip() for s in services_str.split(',') if s.strip()])
        if svc_count >= 4:
            score += 1
            details['diversity'] = f'+1 ({svc_count} services)'
        else:
            details['diversity'] = f'+0 ({svc_count} services)'
    else:
        details['diversity'] = '+0 (no services)'

    qualified = score >= 7
    details['total'] = score
    details['qualified'] = qualified

    return score, qualified, details


def main():
    from crm import get_crm
    crm = get_crm()
    wl = crm.get_wl_all()

    # Judge leads with empty status or "New" status (not yet judged)
    new_leads = [l for l in wl if not l.get('Status', '').strip() or l.get('Status', '').strip() == 'New']
    if not new_leads:
        print("[JUDGE-WL] No new leads to judge.")
        sys.exit(0)

    log(f"[JUDGE-WL] Judging {len(new_leads)} new WL leads...")

    qualified = []
    unqualified = []

    for i, lead in enumerate(new_leads):
        company = lead.get('Company Name', '?')
        score, is_qualified, details = judge_wl_lead(lead)

        status = "✅ QUALIFIED" if is_qualified else "❌ Unqualified"
        log(f"  [{i+1}/{len(new_leads)}] {company:<35} | Score: {score}/10 | {status}")
        for k, v in details.items():
            if k not in ('total', 'qualified'):
                log(f"    {k}: {v}")

        # Update CRM
        crm.update_wl_lead(company, {"Judge Score": score})
        if is_qualified:
            crm.update_wl_lead(company, {"Status": "Qualified"})
            qualified.append(lead)
        else:
            crm.update_wl_lead(company, {"Status": "Unqualified"})
            unqualified.append(lead)

    log(f"\n[JUDGE-WL] Results: {len(qualified)} Qualified, {len(unqualified)} Unqualified")

    print(f"\n{'='*60}")
    print(f"JUDGE-WL RESULTS")
    print(f"{'='*60}")
    print(f"\nQualified ({len(qualified)}):")
    for l in qualified:
        score, _, _ = judge_wl_lead(l)
        print(f"  ✅ {l['Company Name']:<35} | {score}/10 | {l.get('Email','N/A')}")

    print(f"\nUnqualified ({len(unqualified)}):")
    for l in unqualified:
        score, _, _ = judge_wl_lead(l)
        print(f"  ❌ {l['Company Name']:<35} | {score}/10 | {l.get('Email','N/A')}")


if __name__ == "__main__":
    main()
