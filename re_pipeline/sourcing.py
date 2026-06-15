"""Lead sourcing — free tools only"""
import re
import json
import requests
from config import US_CITIES, GCC_CITIES, FRANCHISES

def is_franchise(name):
    """Check if brokerage is a known franchise chain."""
    name_lower = name.lower()
    for f in FRANCHISES:
        if f.lower() in name_lower:
            return True
    return False

def scrape_website_emails(url):
    """Scrape contact page for email addresses via curl + regex."""
    if not url or not url.startswith("http"):
        return []
    try:
        # Try common contact pages
        contact_urls = [
            url.rstrip("/"),
            url.rstrip("/") + "/contact",
            url.rstrip("/") + "/contact-us",
            url.rstrip("/") + "/about",
        ]
        emails = set()
        for u in contact_urls:
            try:
                resp = requests.get(u, timeout=10, headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                })
                if resp.status_code == 200:
                    found = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', resp.text)
                    for e in found:
                        if not e.endswith(('.png', '.jpg', '.gif', '.svg')):
                            emails.add(e.lower())
            except Exception:
                continue
        return list(emails)[:5]
    except Exception:
        return []

def verify_email_mx(email):
    """Verify email domain has MX records."""
    import dns.resolver
    try:
        domain = email.split('@')[1]
        records = dns.resolver.resolve(domain, 'MX')
        return len(records) > 0
    except Exception:
        return False

def guess_email(first_name, domain):
    """Format guess: firstname@domain.com"""
    if not first_name or not domain:
        return ""
    return f"{first_name.lower().strip()}@{domain.lower().strip()}"

def source_google_maps(city, api_key=None):
    """Source brokerages from Google Maps. Requires API key."""
    if not api_key:
        return []
    results = []
    query = f"real estate brokerage {city}"
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {"query": query, "key": api_key}
    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()
        for place in data.get("results", []):
            name = place.get("name", "")
            if is_franchise(name):
                continue
            results.append({
                "Brokerage_Name": name,
                "City": city,
                "Website": place.get("website", ""),
                "Address": place.get("formatted_address", ""),
                "Phone": place.get("formatted_phone_number", ""),
                "Lead_Source": "Google Maps"
            })
    except Exception as e:
        print(f"Google Maps error for {city}: {e}")
    return results

def source_zillow(city, state=""):
    """Scrape brokerages from Zillow directory."""
    results = []
    try:
        url = f"https://www.zillow.com/brokerage-reviews/{city.lower().replace(' ', '-')}-{state.lower()}/"
        resp = requests.get(url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        if resp.status_code == 200:
            # Extract brokerage names from page
            names = re.findall(r'"brokerName":"([^"]+)"', resp.text)
            for name in names:
                if not is_franchise(name):
                    results.append({
                        "Brokerage_Name": name,
                        "City": city,
                        "Lead_Source": "Zillow"
                    })
    except Exception as e:
        print(f"Zillow error for {city}: {e}")
    return results

def source_linkedin_public(company_name):
    """Check LinkedIn public company page via curl."""
    try:
        slug = company_name.lower().replace(" ", "-").replace(".", "")
        url = f"https://www.linkedin.com/company/{slug}"
        resp = requests.get(url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        if resp.status_code == 200:
            return {
                "LinkedIn_URL": url,
                "exists": True
            }
    except Exception:
        pass
    return {"LinkedIn_URL": "", "exists": False}

def check_instagram(username):
    """Check Instagram account via oEmbed (no auth needed)."""
    if not username:
        return {"exists": False}
    try:
        url = f"https://api.instagram.com/oembed/?url=https://www.instagram.com/{username}/"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200 and resp.json().get("author_name"):
            return {
                "exists": True,
                "username": resp.json().get("author_name", username),
                "profile_url": f"https://www.instagram.com/{username}/"
            }
    except Exception:
        pass
    return {"exists": False, "username": username, "profile_url": f"https://www.instagram.com/{username}/"}
