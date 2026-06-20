#!/usr/bin/env python3
"""
Scout new RE leads from multiple cities and add to sheet.
Uses OpenStreetMap (free) + website email scraping.
"""
import sys, os, time, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import US_CITIES, GCC_CITIES, SHEET_ID, SHEET_NAME, COL, TOKEN_PATH
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from osm_sourcing import scout_single_city, enrich_lead, guess_domain_emails
from urllib.parse import urlparse

def get_sheet_service():
    with open(TOKEN_PATH) as f:
        d = json.load(f)
    creds = Credentials(
        token=d['token'], refresh_token=d.get('refresh_token'),
        token_uri=d.get('token_uri', 'https://oauth2.googleapis.com/token'),
        client_id=d['client_id'], client_secret=d['client_secret'],
        scopes=d.get('scopes')
    )
    return build('sheets', 'v4', credentials=creds)

def get_existing_leads(service):
    result = service.spreadsheets().values().get(
        spreadsheetId=SHEET_ID,
        range=f'{SHEET_NAME}!A1:T1000'
    ).execute()
    rows = result.get('values', [])
    existing_emails = set()
    existing_names = set()
    for row in rows[1:]:
        if len(row) > 8 and row[8]:
            existing_emails.add(row[8].lower().strip())
        if len(row) > 1 and row[1]:
            existing_names.add(row[1].lower().strip())
    return existing_emails, existing_names

def add_leads_to_sheet(service, leads):
    if not leads:
        return 0
    
    # Get next Lead_ID
    result = service.spreadsheets().values().get(
        spreadsheetId=SHEET_ID,
        range=f'{SHEET_NAME}!A1:A1000'
    ).execute()
    rows = result.get('values', [])
    next_id = len(rows)
    
    values = []
    for lead in leads:
        next_id += 1
        row = [''] * 20
        row[0] = str(next_id)  # Lead_ID
        row[1] = lead.get('Brokerage_Name', '')
        row[2] = lead.get('Contact_Name', '')
        row[4] = lead.get('City', '')
        row[5] = lead.get('State_Country', '')
        row[6] = lead.get('Market', '')
        row[7] = lead.get('Website', '')
        row[8] = lead.get('Email', '')
        row[11] = lead.get('Lead_Source', 'osm_scout')
        row[13] = lead.get('Angle', 'A')
        row[14] = 'New'
        values.append(row)
    
    body = {'values': values}
    service.spreadsheets().values().append(
        spreadsheetId=SHEET_ID,
        range=f'{SHEET_NAME}!A1',
        valueInputOption='RAW',
        body=body
    ).execute()
    return len(values)

def main():
    print("=== RE LEAD SCOUT ===")
    service = get_sheet_service()
    existing_emails, existing_names = get_existing_leads(service)
    print(f"Existing: {len(existing_emails)} emails, {len(existing_names)} names")
    
    # Scout all US cities
    all_new_leads = []
    cities_to_scout = US_CITIES  # All 10 cities
    
    for city in cities_to_scout:
        print(f"\nScouting {city}...")
        try:
            results = scout_single_city(city, max_results=15)
            for r in results:
                email = r.get('Email', '')
                name = r.get('Brokerage_Name', '')
                if not email or email.lower() in existing_emails:
                    continue
                if name.lower() in existing_names:
                    continue
                # Enrich with email if missing
                if not email and r.get('Website'):
                    guessed = guess_domain_emails(r['Website'])
                    if guessed:
                        r['Email'] = guessed[0]
                        email = guessed[0]
                if email:
                    all_new_leads.append(r)
                    existing_emails.add(email.lower())
                    existing_names.add(name.lower())
                    print(f"  NEW: {name[:35]} | {email}")
        except Exception as e:
            print(f"  ERROR: {e}")
        time.sleep(2)
    
    print(f"\nTotal new leads found: {len(all_new_leads)}")
    
    if all_new_leads:
        added = add_leads_to_sheet(service, all_new_leads)
        print(f"Added {added} leads to sheet")
    else:
        print("No new leads to add")

if __name__ == "__main__":
    main()
