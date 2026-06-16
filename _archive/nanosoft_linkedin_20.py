#!/usr/bin/python3
"""
NanoSoft LinkedIn Founder Scraper v2
Scrapes exactly 20 founder/owner personal LinkedIn profiles from agency websites.
Writes to CRM "LinkedIn" tab for manual outreach by Chairman.

Strategy:
1. Read T1 Sent + Qualified leads from CRM (that don't have LinkedIn yet)
2. For each lead, search ddgs for personal LinkedIn profiles
3. Also scrape the agency website for team/about pages
4. Write 20 unique founder profiles to CRM LinkedIn tab

Usage: python3 nanosoft_linkedin_20.py
"""
import json, os, re, sys, time, signal
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
LOG_FILE = os.path.join(NANOSOFT_DIR, "linkedin_scraper.log")

sys.path.insert(0, NANOSOFT_DIR)

# Hard timeout: 15 minutes
signal.signal(signal.SIGALRM, lambda *a: (_ for _ in ()).throw(TimeoutError("15min limit")))
signal.alarm(900)

# ── Logging ──
def log(msg):
    ts = datetime.now(BD_TZ).strftime("%Y-%m-%d %H:%M")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

# ── CRM helpers ──
def get_crm():
    from crm import get_crm as _get_crm
    return _get_crm()

def read_linkedin_tab(crm):
    """Read existing LinkedIn tab to avoid duplicates."""
    try:
        ws = crm.sh.worksheet("LinkedIn")
        rows = ws.get_all_records()
        return rows
    except Exception:
        return []

def write_to_linkedin_tab(crm, new_rows):
    """Write new rows to LinkedIn tab, appending after existing data."""
    try:
        ws = crm.sh.worksheet("LinkedIn")
        # Append new rows
        for row in new_rows:
            ws.append_row(row)
        log(f"Wrote {len(new_rows)} new rows to LinkedIn tab")
        return True
    except Exception as e:
        log(f"CRM write error: {e}")
        return False

# ── Search helpers ──
def ddgs_search(query, max_results=5):
    """Search using ddgs CLI. Returns list of dicts with 'title', 'url', 'body'."""
    import subprocess
    try:
        r = subprocess.run(
            ["ddgs", "text", "-q", query, "-m", str(max_results)],
            capture_output=True, text=True, timeout=30
        )
        if r.returncode == 0 and r.stdout.strip():
            # Parse plain text output (not JSON)
            results = []
            current = {}
            for line in r.stdout.strip().split('\n'):
                line = line.strip()
                if not line:
                    if current:
                        results.append(current)
                        current = {}
                    continue
                # Numbered item start: "1.", "2.", etc.
                import re
                if re.match(r'^\d+\.$', line):
                    if current:
                        results.append(current)
                    current = {}
                    continue
                if line.startswith('title'):
                    current['title'] = line.split('title', 1)[1].strip().lstrip(' ').lstrip('- ').strip()
                elif line.startswith('href'):
                    current['url'] = line.split('href', 1)[1].strip().lstrip(' ').lstrip('- ').strip()
                elif line.startswith('body'):
                    current['body'] = line.split('body', 1)[1].strip().lstrip(' ').lstrip('- ').strip()
            if current:
                results.append(current)
            return results
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return []

def extract_linkedin_profiles(company, owner_email=""):
    """
    Find personal LinkedIn profiles for a company.
    Returns list of (name, linkedin_url) tuples.
    """
    profiles = []
    seen_urls = set()

    # Strategy 1: Search for founder/owner on LinkedIn via ddgs
    queries = [
        f"site:linkedin.com/in {company} founder",
        f"site:linkedin.com/in {company} owner",
        f"site:linkedin.com/in {company} CEO",
    ]

    # If we have an owner email, extract name from it
    owner_name = ""
    if owner_email and '@' in owner_email:
        local = owner_email.split('@')[0]
        # Convert john.doe or john_doe to "John Doe"
        name_parts = re.split(r'[._\-]', local)
        if len(name_parts) >= 2:
            owner_name = ' '.join(p.capitalize() for p in name_parts if len(p) > 1)
            queries.insert(0, f"site:linkedin.com/in {owner_name} {company}")

    for query in queries:
        results = ddgs_search(query, max_results=5)
        for r in results:
            url = r.get("url", r.get("href", ""))
            title = r.get("title", "")
            # Only personal profiles (linkedin.com/in/...)
            if "linkedin.com/in/" not in url:
                continue
            # Skip company pages
            if "/company/" in url or "/school/" in url:
                continue
            # Skip if already seen
            if url in seen_urls:
                continue
            # Extract name from title
            name = ""
            if title:
                # Title format: "John Doe - Founder at Company - LinkedIn"
                name_part = title.split(" - ")[0].strip()
                if len(name_part.split()) <= 4:  # Reasonable name length
                    name = name_part
            if name or owner_name:
                profiles.append((name or owner_name, url))
                seen_urls.add(url)

        if len(profiles) >= 2:
            break  # Found enough for this company

        time.sleep(1)  # Rate limit between searches

    return profiles

def scrape_website_for_linkedin(website):
    """Scrape agency website for LinkedIn profile links."""
    import urllib.request
    profiles = []
    seen_urls = set()

    if not website:
        return profiles

    if not website.startswith("http"):
        website = "https://" + website

    # Pages to check
    pages = ["/", "/about", "/team", "/about-us", "/contact"]

    for page in pages:
        try:
            url = website.rstrip("/") + page
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="ignore")

            # Find LinkedIn profile links
            linkedin_links = re.findall(
                r'https?://(?:www\.)?linkedin\.com/in/[a-zA-Z0-9\-_%]+',
                html
            )

            for link in linkedin_links:
                # Clean URL
                link = re.sub(r'\?.*$', '', link).rstrip("/")
                if link not in seen_urls:
                    # Try to extract name from URL slug
                    slug = link.split("/in/")[-1]
                    name_parts = slug.replace("-", " ").replace("_", " ").split()
                    if len(name_parts) >= 2 and all(len(p) > 1 for p in name_parts[:2]):
                        name = " ".join(p.capitalize() for p in name_parts[:2])
                        profiles.append((name, link))
                        seen_urls.add(link)

            time.sleep(0.5)

        except Exception:
            continue

    return profiles

# ── Main ──
def main():
    log("=== LinkedIn Founder Scraper v2 ===")

    crm = get_crm()

    # Read existing LinkedIn tab to avoid duplicates
    existing = read_linkedin_tab(crm)
    existing_urls = set()
    existing_companies = set()
    for row in existing:
        # row is a dict from get_all_records()
        url = row.get("LinkedIn URL", row.get("linkedin_url", ""))
        company = row.get("Company Name", row.get("Company", row.get("company", "")))
        if url:
            existing_urls.add(url)
        if company:
            existing_companies.add(company)

    log(f"LinkedIn tab: {len(existing)} existing profiles, {len(existing_companies)} companies")

    # Get leads that need LinkedIn profiles
    # Priority: T1 Sent leads (already contacted, need manual followup)
    # Then: Qualified leads (about to be contacted)
    all_leads = crm.get_wl_all()

    candidates = []
    for lead in all_leads:
        company = lead.get("Company Name", "").strip()
        status = lead.get("Status", "").strip()
        website = lead.get("Website", "").strip()
        email = lead.get("Email", "").strip()
        country = lead.get("Country", lead.get("Location", "")).strip()

        if not company or not website:
            continue
        if company in existing_companies:
            continue

        # Priority scoring
        if status in ("T1 Sent", "T2 Sent", "T3 Sent"):
            priority = 1
        elif status == "Qualified":
            priority = 2
        elif status in ("New", ""):
            priority = 3
        else:
            continue

        candidates.append({
            "company": company,
            "website": website,
            "email": email,
            "country": country,
            "status": status,
            "priority": priority,
        })

    # Sort by priority
    candidates.sort(key=lambda x: x["priority"])
    log(f"Found {len(candidates)} candidates for LinkedIn scraping")

    # Scrape profiles — use ddgs only (fast), skip website scraping (too slow)
    results = []
    for candidate in candidates:
        if len(results) >= 20:
            break

        company = candidate["company"]
        website = candidate["website"]
        email = candidate["email"]
        country = candidate["country"]

        log(f"Scraping: {company} ({candidate['status']})")

        # Only use ddgs search — fast and works
        profiles = extract_linkedin_profiles(company, email)

        if profiles:
            # Take the first (best) profile
            name, url = profiles[0]
            results.append([
                company,
                url,
                country,
                email,
                "Pending",       # Status
                "",              # Connection Sent
                "",              # Connection Date
                "",              # Connection Message
                "",              # Followup Message
                "",              # Reply
                "",              # Notes
            ])
            existing_urls.add(url)
            existing_companies.add(company)
            log(f"  Found: {name} -> {url}")
        else:
            log(f"  No profile found")

        time.sleep(1.5)  # Rate limit ddgs

    log(f"Total profiles found: {len(results)}")

    if results:
        # Append new rows to existing data
        success = write_to_linkedin_tab(crm, results)
        if success:
            log(f"✅ Wrote {len(results)} new profiles to LinkedIn tab")
        else:
            log("❌ Failed to write to CRM")
    else:
        log("No new profiles found")

    return len(results)

if __name__ == "__main__":
    try:
        count = main()
        print(f"SCRAPED: {count}")
    except TimeoutError:
        print("TIMEOUT: 15min limit reached")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
