"""Source new RE leads — comprehensive sweep of all cities"""
import sys, os, time, random

sys.path.insert(0, '/home/ubuntu/nanosoft')
os.chdir('/home/ubuntu/nanosoft')

from re_pipeline.osm_sourcing import scout_single_city, enrich_lead, US_COORDS, GCC_COORDS
from re_pipeline.sheets import append_lead, get_next_lead_id, get_leads
from re_pipeline.audit import run_audit

existing = get_leads()
existing_emails = {l.get('Email','').lower().strip() for l in existing if l.get('Email')}
existing_names = {l.get('Brokerage_Name','').lower().strip() for l in existing}

all_cities = list({**US_COORDS, **GCC_COORDS}.keys())
random.shuffle(all_cities)

added = 0
guessed = 0
skipped_dup = 0
no_email = 0
cities_scouted = 0

for city in all_cities:
    print(f'\nScouting {city}...')
    cities_scouted += 1
    try:
        leads = scout_single_city(city, max_results=8)
        for lead in leads:
            name = lead.get('Brokerage_Name','').lower().strip()
            if name in existing_names:
                print(f'  SKIP dup: {name[:30]}')
                skipped_dup += 1
                continue

            # Re-enrich (scout_single_city already enriched, but try again for websites that may have been missed)
            lead = enrich_lead(lead.copy(), fast=True)
            email = lead.get('Email','').lower().strip()

            if not email:
                print(f'  NO EMAIL: {lead["Brokerage_Name"][:30]}')
                no_email += 1
                continue
            if email in existing_emails:
                print(f'  SKIP email dup: {email}')
                skipped_dup += 1
                continue

            existing_emails.add(email)
            existing_names.add(name)

            ig_url = lead.get('Instagram_URL','')
            ig_user = ig_url.rstrip('/').split('/')[-1] if ig_url else None
            audit = run_audit(lead.get('Brokerage_Name',''), ig_user)
            lead['Social_Audit'] = audit['Social_Audit']
            lead['Angle'] = audit['Angle']
            lead['Status'] = 'New'
            lead['Lead_ID'] = get_next_lead_id()
            append_lead(lead)
            added += 1
            is_guessed = lead.get('Email_Guessed', False)
            if is_guessed:
                guessed += 1
            print(f'  ADDED: {lead["Brokerage_Name"][:28]} | {email} | {"(guessed)" if is_guessed else "(scraped)"} | Angle {audit["Angle"]}')
            time.sleep(0.5)
    except Exception as e:
        print(f'  Error: {e}')
    time.sleep(3)

print(f'\n=== RESULTS ===')
print(f'Cities scouted: {cities_scouted}')
print(f'New leads added: {added}')
print(f'  - Scraped emails: {added - guessed}')
print(f'  - Guessed emails: {guessed}')
print(f'Skipped (dup): {skipped_dup}')
print(f'No email found: {no_email}')
