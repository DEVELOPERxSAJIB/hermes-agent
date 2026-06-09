#!/usr/bin/python3
"""
Scrape founder/owner names and personal LinkedIn profiles from agency websites.
Uses ddgs to search for "[company] founder LinkedIn" and also scrapes team/about pages.
"""
import sys
import os
import json
import time
import re
import subprocess
import urllib.request
import urllib.error
from html.parser import HTMLParser

NANOSOFT_DIR = "/home/ubuntu/nanosoft"
sys.path.insert(0, NANOSOFT_DIR)

from crm import get_crm

class LinkedInParser(HTMLParser):
    """Extract LinkedIn URLs from HTML."""
    def __init__(self):
        super().__init__()
        self.linkedin_urls = []
        self.text_content = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        href = attrs_dict.get("href", "")
        if "linkedin.com/in/" in href:
            # Clean URL
            url = href.split("?")[0].rstrip("/")
            if url not in self.linkedin_urls:
                self.linkedin_urls.append(url)

    def handle_data(self, data):
        self.text_content.append(data.strip())


def fetch_page(url, timeout=10):
    """Fetch a page and return HTML content."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except:
        return ""


def extract_linkedin_from_html(html):
    """Extract personal LinkedIn URLs from HTML."""
    parser = LinkedInParser()
    try:
        parser.feed(html)
    except:
        pass
    # Filter: only personal profiles (linkedin.com/in/), not company pages
    personal = [u for u in parser.linkedin_urls if "/in/" in u]
    return personal


def search_founder_linkedin(company_name, country=""):
    """Search for founder/owner LinkedIn using ddgs."""
    queries = [
        f'"{company_name}" founder LinkedIn',
        f'"{company_name}" CEO LinkedIn',
        f'"{company_name}" owner LinkedIn',
    ]
    if country:
        queries.append(f'"{company_name}" founder {country} LinkedIn')

    results = []
    for query in queries[:2]:  # Limit to 2 queries per company
        try:
            proc = subprocess.run(
                ["ddgs", "text", "-q", query, "-n", "5"],
                capture_output=True, text=True, timeout=15
            )
            if proc.returncode == 0 and proc.stdout:
                # Extract LinkedIn URLs from results
                urls = re.findall(r'https?://(?:www\.)?linkedin\.com/in/[^\s\)\"\']+', proc.stdout)
                for url in urls:
                    url = url.split("?")[0].rstrip("/")
                    if url not in results:
                        results.append(url)
        except:
            pass
        time.sleep(1)

    return results[:3]  # Top 3 results


def scrape_website_for_founder(website):
    """Scrape team/about/contact pages for founder info."""
    pages_to_try = [
        website.rstrip("/") + "/team",
        website.rstrip("/") + "/about",
        website.rstrip("/") + "/about-us",
        website.rstrip("/") + "/contact",
        website.rstrip("/") + "/contact-us",
        website.rstrip("/"),
    ]

    all_linkedin = []
    for page_url in pages_to_try:
        html = fetch_page(page_url)
        if html:
            urls = extract_linkedin_from_html(html)
            for u in urls:
                if u not in all_linkedin:
                    all_linkedin.append(u)
            if len(all_linkedin) >= 3:
                break
        time.sleep(0.5)

    return all_linkedin


def find_common_name_patterns(text, company_name):
    """Try to extract owner name from text near LinkedIn mentions."""
    # Look for patterns like "John Doe - CEO" or "Founder: John Doe"
    patterns = [
        r'([A-Z][a-z]+ [A-Z][a-z]+)\s*[-–—]\s*(?:CEO|Founder|Co-Founder|Owner|Director)',
        r'(?:CEO|Founder|Co-Founder|Owner|Director)\s*[:]\s*([A-Z][a-z]+ [A-Z][a-z]+)',
        r'([A-Z][a-z]+ [A-Z][a-z]+)\s*is\s*(?:the\s)?(?:CEO|Founder|Owner)',
    ]
    for pat in patterns:
        matches = re.findall(pat, text)
        if matches:
            return matches[0]
    return ""


def main():
    crm = get_crm()
    leads = crm.get_wl_all()

    # Filter: leads with websites but no owner LinkedIn
    targets = []
    for l in leads:
        company = l.get("Company Name", "").strip()
        website = l.get("Website", "").strip()
        owner_linkedin = l.get("Owner LinkedIn URL", "").strip()
        owner_name = l.get("Owner Name", "").strip()
        status = l.get("Status", "").strip()

        if not website:
            continue
        # Skip if already has owner LinkedIn
        if owner_linkedin and "linkedin.com/in/" in owner_linkedin:
            continue
        # Only process T1 Sent, Sent, Qualified, New
        if status not in ("T1 Sent", "Sent", "Qualified", "New", ""):
            continue

        targets.append({
            "company": company,
            "website": website,
            "country": l.get("Country", "").strip(),
            "status": status,
        })

    print(f"[FOUNDER-SCRAPER] {len(targets)} leads need founder LinkedIn scraping")

    results = []
    for i, t in enumerate(targets):
        company = t["company"]
        website = t["website"]
        country = t["country"]

        print(f"  [{i+1}/{len(targets)}] {company}...", end=" ", flush=True)

        # Method 1: Scrape website team/about pages
        website_linkedin = scrape_website_for_founder(website)

        # Method 2: Search via ddgs
        search_linkedin = search_founder_linkedin(company, country)

        # Combine, prioritize website results
        combined = website_linkedin + [u for u in search_linkedin if u not in website_linkedin]
        best = combined[:3] if combined else []

        if best:
            print(f"Found: {best[0]}")
            results.append({
                "company": company,
                "website": website,
                "country": country,
                "status": t["status"],
                "founder_linkedin": best[0],
                "alt_linkedin": best[1] if len(best) > 1 else "",
            })
        else:
            print("Not found")

        # Rate limiting
        if i < len(targets) - 1:
            time.sleep(2)

    # Save results
    output_file = os.path.join(NANOSOFT_DIR, "founder_linkedin_results.json")
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n[FOUNDER-SCRAPER] DONE: {len(results)} founders found out of {len(targets)} leads")
    print(f"Results saved to {output_file}")

    # Update CRM with found owner LinkedIn URLs
    updated = 0
    for r in results:
        try:
            crm.update_wl_lead(r["company"], {
                "Owner LinkedIn URL": r["founder_linkedin"],
            })
            updated += 1
            time.sleep(0.5)
        except:
            pass

    print(f"[FOUNDER-SCRAPER] CRM updated: {updated} leads with owner LinkedIn")


if __name__ == "__main__":
    main()
