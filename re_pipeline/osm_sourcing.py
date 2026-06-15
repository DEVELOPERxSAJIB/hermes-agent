"""Lead sourcing via OpenStreetMap (Overpass API) — free, no API key needed"""
import re
import json
import requests
from config import US_CITIES, GCC_CITIES, FRANCHISES

# US city coordinates (lat, lon)
US_COORDS = {
    "Miami": (25.7617, -80.1918),
    "Houston": (29.7604, -95.3698),
    "Dallas": (32.7767, -96.7970),
    "Atlanta": (33.7490, -84.3880),
    "Phoenix": (33.4484, -112.0740),
    "Las Vegas": (36.1699, -115.1398),
    "Orlando": (28.5383, -81.3792),
    "Charlotte": (35.2271, -80.8431),
    "Tampa": (27.9506, -82.4572),
    "Denver": (39.7392, -104.9903),
}

# GCC city coordinates
GCC_COORDS = {
    "Dubai": (25.2048, 55.2708),
    "Abu Dhabi": (24.4539, 54.3773),
    "Riyadh": (24.7136, 46.6753),
    "Doha": (25.2854, 51.5310),
    "Kuwait City": (29.3759, 47.9774),
    "Muscat": (23.5880, 58.3829),
}

ALL_COORDS = {**US_COORDS, **GCC_COORDS}

def is_franchise(name):
    """Check if brokerage is a known franchise chain."""
    name_lower = name.lower()
    for f in FRANCHISES:
        if f.lower() in name_lower:
            return True
    return False

def _overpass_query(query):
    """Execute an Overpass API query. Returns list of elements."""
    try:
        resp = requests.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": query},
            timeout=30,
            headers={"User-Agent": "RE-Pipeline/1.0"}
        )
        if resp.status_code != 200:
            print(f"Overpass HTTP {resp.status_code}: {resp.text[:200]}")
            return []
        return resp.json().get("elements", [])
    except Exception as e:
        print(f"Overpass error: {e}")
        return []

def search_osm_city(city, radius_meters=15000):
    """
    Search OSM for real estate agencies in a city.
    Uses office=estate_agent and shop=estate_agent tags.
    """
    coords = ALL_COORDS.get(city)
    if not coords:
        return []

    lat, lon = coords
    results = []
    seen_names = set()

    for tag_key, tag_value in [("office", "estate_agent"), ("shop", "estate_agent")]:
        query = f'[out:json][timeout:30];node["{tag_key}"="{tag_value}"](around:{radius_meters},{lat},{lon});out body;'
        elements = _overpass_query(query)

        for element in elements:
            tags = element.get("tags", {})
            name = tags.get("name", "") or tags.get("name:en", "")
            if not name or len(name) < 3:
                continue
            if is_franchise(name):
                continue
            if name.lower() in seen_names:
                continue
            seen_names.add(name.lower())

            website = tags.get("website", "") or tags.get("url", "")
            if website and not website.startswith("http"):
                website = "https://" + website

            phone = tags.get("phone", "") or tags.get("contact:phone", "")
            address_parts = [
                tags.get("addr:housenumber", ""),
                tags.get("addr:street", ""),
                tags.get("addr:city", city),
            ]
            address = " ".join(p for p in address_parts if p)
            market = "US" if city in US_COORDS else "GCC"

            results.append({
                "Brokerage_Name": name,
                "City": city,
                "State_Country": tags.get("addr:state", tags.get("addr:country", "")),
                "Market": market,
                "Website": website,
                "Phone": phone,
                "Address": address,
                "Lead_Source": "OpenStreetMap",
                "OSM_ID": element.get("id"),
            })

    return results

def scrape_website_emails(url):
    """Scrape website for email addresses."""
    if not url or not url.startswith("http"):
        return []
    try:
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
                        if not e.endswith(('.png', '.jpg', '.gif', '.svg', '.ico')):
                            emails.add(e.lower())
            except Exception:
                continue
        return list(emails)[:5]
    except Exception:
        return []

def guess_email(first_name, domain):
    if not first_name or not domain:
        return ""
    return f"{first_name.lower().strip()}@{domain.lower().strip()}"

def verify_email_mx(email):
    try:
        import dns.resolver
        domain = email.split('@')[1]
        records = dns.resolver.resolve(domain, 'MX')
        return len(records) > 0
    except Exception:
        return False

def check_instagram(username):
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

def enrich_lead(lead, fast=True):
    """Enrich lead with emails and Instagram check.
    fast=True skips MX verification and Instagram check for speed."""
    if lead.get("Website"):
        emails = scrape_website_emails(lead["Website"])
        if emails:
            lead["Email"] = emails[0]

    if not lead.get("Email") and lead.get("Website"):
        domain = lead["Website"].replace("https://", "").replace("http://", "").split("/")[0]
        contact = lead.get("Contact_Name", "")
        if contact:
            guessed = guess_email(contact.split()[0] if " " in contact else contact, domain)
            if guessed:
                if fast or verify_email_mx(guessed):
                    lead["Email"] = guessed

    if not fast:
        name_slug = lead["Brokerage_Name"].lower().replace(" ", "").replace(".", "")
        ig = check_instagram(name_slug)
        if ig["exists"]:
            lead["Instagram_URL"] = ig["profile_url"]

    return lead

def scout_single_city(city, max_results=10):
    """Scout a single city and return enriched leads."""
    print(f"Scouting {city}...")
    results = search_osm_city(city)
    enriched = [enrich_lead(r) for r in results[:max_results]]
    with_email = [l for l in enriched if l.get("Email")]
    print(f"  Found {len(results)} brokerages, {len(with_email)} with email")
    return enriched
