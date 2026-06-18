#!/usr/bin/env python3
"""
SCOUT — White Label Lead Sourcing
Uses DuckDuckGo search to find agency websites, then scrapes for emails.
Runs every 6 hours via cron.
"""
import json
import os
import re
import sys
import time
import subprocess
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
sys.path.insert(0, NANOSOFT_DIR)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
GENERIC = {
    "user@domain.com", "info@example.com", "test@test.com", "admin@localhost",
    "john@example.com", "jane@example.com", "email@example.com", "name@example.com",
    "yourname@example.com", "info@domain.com", "contact@domain.com", "mail@domain.com",
}


def is_valid_email(email):
    """Validate email isn't garbage."""
    if "@" not in email:
        return False
    local, domain = email.split("@", 1)
    if not domain or "." not in domain:
        return False
    if email.endswith((".png", ".jpg", ".gif", ".svg", ".ico", ".css", ".js", ".woff", ".ttf", ".webp", ".bmp", ".tiff")):
        return False
    if len(local) > 20 and all(c in "0123456789abcdef." for c in local):
        return False
    if len(local) > 30:
        return False
    return True


def ddgs_search(query, max_results=10):
    """Search using ddgs CLI."""
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
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def fetch_page(url, timeout=6):
    try:
        import urllib.request
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except:
        return None


def scrape_emails_from_page(url):
    """Scrape emails from a single page."""
    from html import unescape
    from urllib.request import unquote as url_unquote

    html = fetch_page(url)
    if not html:
        return []
    html = unescape(html)
    emails = set()
    # mailto links
    for m in re.findall(r'mailto:([^"\'>\s<]+)', html, re.IGNORECASE):
        e = url_unquote(m).strip().rstrip("\\").lower()
        if "@ in e" and e not in GENERIC and is_valid_email(e):
            emails.add(e)
    # plain text
    for m in EMAIL_RE.findall(html):
        m = m.lower()
        if m not in GENERIC and is_valid_email(m):
            emails.add(m)
    return list(emails)


def guess_email(domain):
    """Guess common email patterns."""
    prefixes = ["info", "hello", "contact", "sales", "team"]
    return [f"{p}@{domain}" for p in prefixes]


def main():
    from crm import get_crm

    crm = get_crm()
    existing = crm.get_wl_all()
    existing_emails = {str(l.get("Email", "")).lower().strip() for l in existing if l.get("Email")}
    existing_names = {str(l.get("Company Name", "")).lower().strip() for l in existing}

    # Search queries to find agency websites
    queries = [
        '"web development agency" "contact us" -linkedin -facebook -twitter',
        '"custom software development" agency site:.com "email"',
        '"white label web development" site:.com',
        '"web development company" "about us" site:.com',
        '"digital agency" web development site:.com',
    ]

    new_added = 0
    seen_urls = set()

    for query in queries:
        print(f"Searching: {query[:60]}")
        results = ddgs_search(query, max_results=5)
        for r in results:
            url = r.get("href", "")
            title = r.get("title", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            # Skip non-agency URLs
            skip_domains = ["linkedin.com", "facebook.com", "twitter.com", "instagram.com",
                           "youtube.com", "wikipedia.org", "crunchbase.com", "glassdoor.com"]
            domain = urlparse(url).netloc.replace("www.", "")
            if any(sd in domain for sd in skip_domains):
                continue

            # Extract company name from title or URL
            company = title.split(" - ")[0].split(" | ")[0].strip() if title else domain
            if len(company) < 3 or len(company) > 60:
                company = domain

            company_lower = company.lower().strip()
            if company_lower in existing_names:
                continue

            # Scrape emails from the website
            emails = scrape_emails_from_page(url)

            if not emails:
                # Try contact page
                for path in ["/contact", "/contact-us", "/about"]:
                    contact_url = url.rstrip("/") + path
                    emails = scrape_emails_from_page(contact_url)
                    if emails:
                        break
                    time.sleep(0.5)

            if not emails:
                # Guess from domain
                emails = guess_email(domain)

            if emails:
                email = emails[0]
                if email.lower() in existing_emails:
                    continue

                lead = {
                    "Company Name": company,
                    "Email": email,
                    "Website": url,
                    "Status": "New",
                    "Source": "scout_ddgs",
                    "Date Added": datetime.now(BD_TZ).strftime("%Y-%m-%d"),
                    "Judge Score": "",
                }
                try:
                    crm.add_wl_lead(lead)
                    existing_emails.add(email.lower())
                    existing_names.add(company_lower)
                    new_added += 1
                    print(f"  ADDED: {company[:35]} | {email}")
                except Exception as e:
                    print(f"  ERROR: {company[:30]}: {e}")
            else:
                print(f"  NO EMAIL: {company[:30]} | {url[:50]}")

            time.sleep(1)

        time.sleep(2)  # Rate limit between searches

    print(f"\n=== SCOUT DONE: {new_added} new leads added ===")
    return new_added


if __name__ == "__main__":
    main()
