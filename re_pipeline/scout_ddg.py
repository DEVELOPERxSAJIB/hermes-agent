#!/usr/bin/env python3
"""
RE Lead Sourcing v2 — DuckDuckGo search + deep email scraping
Searches for realtor brokerages with contact pages in target cities.
"""
import sys, os, time, json, re, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import TOKEN_PATH, SHEET_ID, SHEET_NAME, COL
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from osm_sourcing import scrape_website_emails, guess_domain_emails, _fetch_page, is_franchise
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))

# Franchise filter
FRANCHISES = ['RE/MAX', 'Keller Williams', 'Century 21', 'Coldwell Banker',
              "Sotheby's", 'Douglas Elliman', 'Compass', 'eXp Realty',
              'Better Homes', 'ERA Real Estate', 'Exit Realty', 'Realty One']

def log(msg):
    ts = datetime.now(BD_TZ).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def get_sheet_service():
    # Try OAuth first, fall back to service account
    try:
        with open(TOKEN_PATH) as f:
            d = json.load(f)
        from datetime import datetime as _dt, timezone as _tz
        expiry_str = d.get('expiry', '')
        if expiry_str:
            try:
                expiry_str_norm = expiry_str.replace('Z', '+00:00')
                expiry_dt = _dt.fromisoformat(expiry_str_norm)
                if expiry_dt.tzinfo is None:
                    expiry_dt = expiry_dt.replace(tzinfo=_tz.utc)
                if _dt.now(_tz.utc) > expiry_dt:
                    # Token expired, try refresh
                    creds = Credentials(
                        token=d['token'], refresh_token=d.get('refresh_token'),
                        token_uri=d.get('token_uri', 'https://oauth2.googleapis.com/token'),
                        client_id=d['client_id'], client_secret=d['client_secret'],
                        scopes=d.get('scopes')
                    )
                    if creds.refresh_token:
                        try:
                            import google.auth.transport.requests
                            creds.refresh(google.auth.transport.requests.Request())
                            # Verify the refreshed token works
                            svc = build('sheets', 'v4', credentials=creds)
                            svc.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
                            return svc
                        except Exception:
                            pass
                    # Fall through to service account
                    raise Exception("OAuth expired/revoked, using SA")
            except Exception:
                pass
        creds = Credentials(
            token=d['token'], refresh_token=d.get('refresh_token'),
            token_uri=d.get('token_uri', 'https://oauth2.googleapis.com/token'),
            client_id=d['client_id'], client_secret=d['client_secret'],
            scopes=d.get('scopes')
        )
        # Verify OAuth creds work before returning
        svc = build('sheets', 'v4', credentials=creds)
        svc.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
        return svc
    except Exception:
        # Service account fallback
        from google.oauth2.service_account import Credentials as SACredentials
        sa_path = os.path.expanduser("~/nanosoft/gcp_service_account.json")
        sa_creds = SACredentials.from_service_account_file(
            sa_path,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        return build('sheets', 'v4', credentials=sa_creds)

def get_existing(service):
    result = service.spreadsheets().values().get(
        spreadsheetId=SHEET_ID, range=f'{SHEET_NAME}!A1:T500'
    ).execute()
    rows = result.get('values', [])
    emails = set()
    names = set()
    for row in rows[1:]:
        if len(row) > 8 and row[8]: emails.add(row[8].lower().strip())
        if len(row) > 1 and row[1]: names.add(row[1].lower().strip())
    return emails, names

def ddg_search(query, max_results=10):
    """Search DuckDuckGo."""
    try:
        r = subprocess.run(
            ["ddgs", "text", "-q", query, "-m", str(max_results)],
            capture_output=True, text=True, timeout=30
        )
        if r.returncode != 0 or not r.stdout.strip():
            return []
        results = []
        current = {}
        for line in r.stdout.strip().split("\n"):
            line = line.strip()
            if not line:
                if current.get("href"):
                    results.append(current)
                current = {}
                continue
            if line.startswith("title"):
                current["title"] = line.split("title", 1)[1].strip().lstrip(" ").lstrip("- ").strip()
            elif line.startswith("href"):
                current["href"] = line.split("href", 1)[1].strip().lstrip(" ").lstrip("- ").strip()
            elif line.startswith("body"):
                current["body"] = line.split("body", 1)[1].strip().lstrip(" ").lstrip("- ").strip()
        if current.get("href"):
            results.append(current)
        return results
    except:
        return []

def is_valid_email(email):
    if not email or '@' not in email:
        return False
    if email.endswith(('.png', '.jpg', '.gif', '.svg', '.ico', '.css', '.js', '.woff', '.ttf', '.webp')):
        return False
    local = email.split('@')[0]
    if len(local) > 20 and all(c in '0123456789abcdef.' for c in local):
        return False
    if len(local) > 30:
        return False
    bad_domains = ['example.com', 'test.com', 'email.com', 'domain.com', 'company.com', 'facebook.com', 'google.com', 'instagram.com', 'twitter.com', 'linkedin.com', 'youtube.com']
    domain = email.split('@')[1] if '@' in email else ''
    if domain in bad_domains:
        return False
    return True

def extract_company_name(title, url):
    """Extract company name from search result title or URL."""
    if title:
        # Take first part before common separators
        name = title.split(' - ')[0].split(' | ')[0].split(' :: ')[0].strip()
        if 3 <= len(name) <= 60:
            return name
    # Fallback to domain
    domain = urlparse(url).netloc.replace('www.', '')
    name = domain.split('.')[0].replace('-', ' ').replace('_', ' ').title()
    return name if len(name) >= 3 else domain

def is_franchise_name(name):
    name_lower = name.lower()
    for f in FRANCHISES:
        if f.lower() in name_lower:
            return True
    return False

def main():
    log("=== RE LEAD SOURCING v2 (DDG Search) ===")
    service = get_sheet_service()
    existing_emails, existing_names = get_existing(service)
    log(f"Existing: {len(existing_emails)} emails, {len(existing_names)} names")
    
    cities = [
        "Miami FL", "Houston TX", "Dallas TX", "Atlanta GA", "Phoenix AZ",
        "Las Vegas NV", "Orlando FL", "Charlotte NC", "Tampa FL", "Denver CO",
        "Austin TX", "Nashville TN", "Raleigh NC", "Jacksonville FL", "San Antonio TX",
    ]
    
    # Search queries designed to find brokerage websites with contact info
    queries_per_city = [
        'real estate brokerage "{city}" contact email',
        'realtor office "{city}" about us email',
        'real estate agency "{city}" contact',
    ]
    
    all_new_leads = []
    seen_urls = set()
    
    for city in cities:
        log(f"\nSearching {city}...")
        for query_template in queries_per_city:
            query = query_template.format(city=city)
            try:
                results = ddg_search(query, max_results=8)
            except:
                results = []
            
            for r in results:
                url = r.get("href", "")
                title = r.get("title", "")
                
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                
                # Skip non-realtor URLs
                skip_domains = ['linkedin.com', 'facebook.com', 'instagram.com', 'twitter.com',
                               'youtube.com', 'wikipedia.org', 'crunchbase.com', 'glassdoor.com',
                               'yelp.com', 'zillow.com', 'realtor.com', 'redfin.com', 'trulia.com']
                domain = urlparse(url).netloc.replace('www.', '')
                if any(sd in domain for sd in skip_domains):
                    continue
                
                company = extract_company_name(title, url)
                if is_franchise_name(company):
                    continue
                if company.lower() in existing_names:
                    continue
                
                # Scrape emails from website
                emails = scrape_website_emails(url)
                
                if not emails:
                    # Try contact page specifically
                    for path in ['/contact', '/contact-us', '/about']:
                        contact_url = url.rstrip('/') + path
                        emails = scrape_website_emails(contact_url)
                        if emails:
                            break
                        time.sleep(0.5)
                
                if not emails:
                    # Guess from domain
                    guessed = guess_domain_emails(url)
                    emails = guessed[:3] if guessed else []
                
                if emails:
                    # Filter valid emails
                    valid_emails = [e for e in emails if is_valid_email(e) and e.lower() not in existing_emails]
                    if valid_emails:
                        best_email = valid_emails[0]
                        lead = {
                            'Brokerage_Name': company,
                            'City': city.split()[0],
                            'State_Country': city.split()[1] if len(city.split()) > 1 else '',
                            'Market': 'US',
                            'Website': url,
                            'Email': best_email,
                            'Lead_Source': 'ddg_search',
                            'Angle': 'A',
                            'Status': 'New',
                        }
                        all_new_leads.append(lead)
                        existing_emails.add(best_email.lower())
                        existing_names.add(company.lower())
                        log(f"  NEW: {company[:35]} | {best_email}")

                        # Write incrementally so partial results survive timeout
                        try:
                            row = [''] * 20
                            row[0] = str(len(all_new_leads))
                            row[1] = lead.get('Brokerage_Name', '')
                            row[4] = lead.get('City', '')
                            row[5] = lead.get('State_Country', '')
                            row[6] = lead.get('Market', '')
                            row[7] = lead.get('Website', '')
                            row[8] = lead.get('Email', '')
                            row[11] = lead.get('Lead_Source', 'ddg_search')
                            row[13] = lead.get('Angle', 'A')
                            row[14] = 'New'
                            service.spreadsheets().values().append(
                                spreadsheetId=SHEET_ID, range=f'{SHEET_NAME}!A1',
                                valueInputOption='RAW', body={'values': [row]}
                            ).execute()
                            log(f"    -> written to sheet")
                        except Exception as e:
                            log(f"    -> sheet write failed: {e}")
            
            time.sleep(2)  # Rate limit between searches
        
        time.sleep(3)  # Rate limit between cities
    
    log(f"\nTotal new leads found & written: {len(all_new_leads)}")
    if not all_new_leads:
        log("No new leads found")

if __name__ == "__main__":
    main()
