#!/usr/bin/env python3
import sys, re
sys.path.insert(0, '/home/ubuntu/nanosoft')
from crm import get_crm

crm = get_crm()
leads = crm.get_leads_by_status('Drafted')

print(f'Total to re-draft: {len(leads)}')
print()

# Check for bad emails
bad_patterns = [
    r'user@domain', r'example@', r'test@', r'@domain\.', r'@example\.',
    r'@whois\.', r'@sentry\.', r'@bytedance\.', r'vue@3\.', r'@scorebig\.',
    r'@afternic\.', r'john@doe\.', r'feedback@',
]

bad_leads = []
good_leads = []
for l in leads:
    email = l.get('Owner Email', '').strip()
    is_bad = False
    for pat in bad_patterns:
        if re.search(pat, email, re.IGNORECASE):
            is_bad = True
            break
    if is_bad:
        bad_leads.append(f'{l.get("Company Name","?")} | {email}')
    else:
        good_leads.append(l)

print(f'Bad emails (placeholder/scraped junk): {len(bad_leads)}')
for b in bad_leads:
    print(f'  BAD: {b}')
print(f'Good emails: {len(good_leads)}')
print()

# Categorize good leads by niche
niches = {}
for l in good_leads:
    company = l.get('Company Name', '').lower()
    pain = l.get('Pain Point', '').lower()
    website = l.get('Website', '').lower()
    combined = company + ' ' + website + ' ' + pain
    
    if any(w in combined for w in ['dent', 'dental', 'tooth']):
        niche = 'dental'
    elif any(w in combined for w in ['law', 'attorney', 'lawyer', 'legal', 'lawclinic']):
        niche = 'law'
    elif any(w in combined for w in ['realty', 'real estate', 'realtor', 'property']):
        niche = 'realty'
    elif any(w in combined for w in ['auto', 'car', 'automotive', 'repair', 'dfw auto', 'groupauto', 'plusauto', 'grove auto']):
        niche = 'auto'
    elif any(w in combined for w in ['gym', 'fitness', 'workout']):
        niche = 'gym'
    elif any(w in combined for w in ['salon', 'hair', 'beauty', 'massage']):
        niche = 'beauty'
    elif any(w in combined for w in ['clean', 'maid', 'housekeep']):
        niche = 'cleaning'
    elif any(w in combined for w in ['landscape', 'lawn', 'garden', 'tree']):
        niche = 'landscaping'
    elif any(w in combined for w in ['pest']):
        niche = 'pest'
    elif any(w in combined for w in ['roof', 'roofing']):
        niche = 'roofing'
    elif any(w in combined for w in ['plumb', 'heating', 'hvac']):
        niche = 'plumbing'
    elif any(w in combined for w in ['restaurant', 'food', 'cafe', 'best restaurant']):
        niche = 'restaurant'
    elif any(w in combined for w in ['movers', 'moving']):
        niche = 'moving'
    elif any(w in combined for w in ['realt', 'realty']):
        niche = 'realty'
    else:
        niche = 'other'
    
    if niche not in niches:
        niches[niche] = []
    niches[niche].append(l)

for niche in sorted(niches.keys(), key=lambda x: -len(niches[x])):
    print(f'{niche}: {len(niches[niche])} leads')
    for l in niches[niche]:
        print(f'  - {l.get("Company Name","?")} | {l.get("Owner Email","?")} | Score: {l.get("Judge Score","?")}')

print()
print(f'SUMMARY:')
print(f'  Total leads: {len(leads)}')
print(f'  Bad emails (skip): {len(bad_leads)}')
print(f'  Good emails (re-draft): {len(good_leads)}')
