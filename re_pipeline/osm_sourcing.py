"""
Lead sourcing via OpenStreetMap (Overpass API) — free, no API key needed
Enrichment: deep email scraping from websites
"""
import re
import json
import time
import socket
import requests
from urllib.parse import urljoin, urlparse

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

EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')

GENERIC_EMAILS = {
    'user@domain.com', 'info@example.com', 'test@test.com', 'admin@localhost',
    'john@example.com', 'jane@example.com', 'email@example.com', 'name@example.com',
    'yourname@example.com', 'info@domain.com', 'contact@domain.com',
    'timdoylefl@gmail.com',
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

CONTACT_PATHS = [
    "/contact", "/contact-us", "/about", "/about-us",
    "/team", "/agents", "/staff", "/people",
]

MAX_EMAIL_PER_SITE = 5
PAGE_TIMEOUT = 6
CONNECT_TIMEOUT = 4
WAIT_BETWEEN_PAGES = 0.2


def is_franchise(name):
    name_lower = name.lower()
    for f in FRANCHISES:
        if f.lower() in name_lower:
            return True
    return False


def _overpass_query(query):
    try:
        resp = requests.post(
            "https://overpass-api.de/api/interpreter",
            data={"data": query},
            timeout=30,
            headers={"User-Agent": "RE-Pipeline/1.0"},
        )
        if resp.status_code == 429:
            print("  [RATE LIMIT] Waiting 30s...")
            time.sleep(30)
            return _overpass_query(query)
        if resp.status_code != 200:
            print(f"  Overpass HTTP {resp.status_code}: {resp.text[:200]}")
            return []
        return resp.json().get("elements", [])
    except Exception as e:
        print(f"  Overpass error: {e}")
        return []


def search_osm_city(city, radius_meters=15000):
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


def _fetch_page(url, timeout=PAGE_TIMEOUT):
    """Fetch a page. Returns HTML text or None."""
    try:
        resp = requests.get(url, timeout=(CONNECT_TIMEOUT, timeout), headers=HEADERS, allow_redirects=True)
        if resp.status_code == 200 and resp.text and len(resp.text) > 100:
            return resp.text
    except Exception:
        pass
    return None


def _decode_html_entities(text):
    """Decode common HTML entities in email addresses."""
    import html
    return html.unescape(text)


def _extract_emails_from_text(text):
    """Extract all email addresses from raw text, including HTML."""
    if not text:
        return []
    from urllib.parse import unquote
    text = _decode_html_entities(text)
    text = unquote(text)
    found = EMAIL_RE.findall(text)
    valid = []
    for e in found:
        e = e.lower().strip().rstrip('.')
        if e in GENERIC_EMAILS:
            continue
        # Reject image/media file extensions
        if e.endswith(('.png', '.jpg', '.gif', '.svg', '.ico', '.css', '.js', '.woff', '.ttf', '.webp', '.bmp', '.tiff')):
            continue
        # Reject hex/hash strings (like bcb8c4703eae71d5d05c0a6eec1f7daa.flags@2x.png)
        local = e.split('@')[0]
        if len(local) > 20 and all(c in '0123456789abcdef.' for c in local):
            continue
        # Reject very long local parts (likely garbage)
        if len(local) > 30:
            continue
        # Must have a valid-looking domain
        domain = e.split('@')[1] if '@' in e else ''
        if not domain or '.' not in domain:
            continue
        # Reject domains that are just numbers or hex
        domain_parts = domain.split('.')
        if all(p.isdigit() for p in domain_parts if p):
            continue
        valid.append(e)
    return list(set(valid))


def _extract_mailto_emails(html):
    """Extract emails from mailto: links."""
    if not html:
        return []
    from urllib.parse import unquote
    mailtos = re.findall(r'mailto:([^"\'>\s<]+)', html, re.IGNORECASE)
    cleaned = []
    for m in mailtos:
        m = unquote(m)
        # Strip query strings (?subject=...) and fragments
        m = m.split('?')[0].split('#')[0]
        m = _decode_html_entities(m).lower().strip().rstrip('\\').rstrip('/')
        if '@' in m and len(m) > 5:
            cleaned.append(m)
    return cleaned


def _dns_fallback_emails(domain):
    """Try to find common email patterns via DNS/nothing — just return empty.
    Placeholder for future: could use Clearbit, Hunter.io, etc."""
    return []


def _find_contact_links(html, base_url):
    """Find contact/about page links in the HTML."""
    if not html:
        return []
    links = []
    for match in re.finditer(r'href=["\']([^"\'#]+)["\']', html, re.IGNORECASE):
        href = match.group(1)
        href_lower = href.lower()
        if any(kw in href_lower for kw in ['contact', 'about', 'team', 'agent', 'staff', 'people']):
            full = urljoin(base_url, href)
            # Only same-domain links
            if urlparse(full).netloc == urlparse(base_url).netloc:
                links.append(full)
    return list(set(links))[:6]


def scrape_website_emails(url):
    """Deep email scraping. Multiple layers, fast timeouts."""
    if not url or not url.startswith("http"):
        return []

    base_url = url.rstrip('/')
    all_emails = set()

    # LAYER 1: Homepage
    home_html = _fetch_page(base_url)
    if not home_html:
        return []

    # mailto links (most reliable)
    mailto_emails = _extract_mailto_emails(home_html)
    all_emails.update(mailto_emails)

    # Plain text emails from homepage
    text_emails = _extract_emails_from_text(home_html)
    all_emails.update(text_emails)

    # data-email attributes
    data_emails = re.findall(r'data-email=["\']([^"\'>]+)', home_html, re.IGNORECASE)
    all_emails.update(e.lower() for e in data_emails if '@' in e and len(e) > 5)

    # Obfuscated: user [at] domain [dot] com
    obfuscated = re.findall(r'([\w.+\-]+)\s*\[at\]\s*([\w.\-]+)\s*\[dot\]\s*(\w{2,})', home_html, re.IGNORECASE)
    for ob in obfuscated:
        all_emails.add(f"{ob[0]}@{ob[1]}.{ob[2]}".lower())

    # LAYER 2: Contact pages (only if we haven't found enough)
    if len(all_emails) < MAX_EMAIL_PER_SITE:
        contact_links = _find_contact_links(home_html, base_url)
        for link in contact_links[:4]:
            html = _fetch_page(link)
            if html:
                all_emails.update(_extract_mailto_emails(html))
                all_emails.update(_extract_emails_from_text(html))
            if len(all_emails) >= MAX_EMAIL_PER_SITE:
                break
            time.sleep(WAIT_BETWEEN_PAGES)

    # Filter generic
    filtered = [e for e in all_emails if e not in GENERIC_EMAILS]
    return filtered[:MAX_EMAIL_PER_SITE]


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
                "profile_url": f"https://www.instagram.com/{username}/",
            }
    except Exception:
        pass
    return {"exists": False, "username": username, "profile_url": f"https://www.instagram.com/{username}/"}


def guess_domain_emails(website):
    """Guess common email patterns from website domain."""
    if not website:
        return []
    from urllib.parse import urlparse
    domain = urlparse(website).netloc.replace("www.", "").strip()
    if not domain:
        return []
    prefixes = ["info", "hello", "contact", "sales", "team", "admin", "office", "enquiries"]
    return [f"{p}@{domain}" for p in prefixes]


def enrich_lead(lead, fast=True):
    """Enrich lead with emails and Instagram check.
    fast=True skips MX verify and Instagram check for speed.
    Falls back to domain guessing if website scraping finds nothing."""
    if lead.get("Website"):
        emails = scrape_website_emails(lead["Website"])
        if emails:
            lead["Email"] = emails[0]
            if len(emails) > 1:
                lead["All_Emails"] = emails
        else:
            # Fallback: guess emails from domain
            guessed = guess_domain_emails(lead["Website"])
            if guessed:
                lead["Email"] = guessed[0]
                lead["All_Emails"] = guessed
                lead["Email_Guessed"] = True  # flag for bounce tracking

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
