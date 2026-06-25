#!/usr/bin/env python3
"""
LinkedIn Owner Scraper v2
Uses Google search + DuckDuckGo to find owner/founder LinkedIn profiles from company name.
No LinkedIn login required. Works with public data only.
Rate: ~5-8 pages/minute (respectful delays).
"""

import os
import sys
import json
import time
import re
import random
import logging
import requests
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

# ─── Config ───────────────────────────────────────────────────────────────────
DATA_DIR = Path("/home/ubuntu/nanosoft")
CRM_CACHE = DATA_DIR / "crm_cache.json"
OUTPUT_FILE = DATA_DIR / "linkedin_owners_today.json"
PROGRESS_FILE = DATA_DIR / "linkedin_owners_progress.json"
LOG_FILE = DATA_DIR / "linkedin_owner_scraper.log"
COOKIE_FILE = Path.home() / ".linkedin_cookie"

DAILY_TARGET = 20
MIN_DELAY = 3
MAX_DELAY = 7

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ─── Helpers ──────────────────────────────────────────────────────────────────
def load_progress():
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"processed_companies": [], "last_date": "", "total_collected": 0}

def save_progress(progress):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)

def load_crm_leads():
    with open(CRM_CACHE) as f:
        crm = json.load(f)
    leads = crm.get("leads", [])
    need_owner = []
    for l in leads:
        company_li = l.get("LinkedIn", "").strip()
        owner_li = l.get("Owner LinkedIn URL", "").strip()
        if company_li and not owner_li:
            need_owner.append(l)
    return need_owner

def load_existing_results():
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE) as f:
            return json.load(f)
    return []

def get_session():
    """Create a requests session with browser-like headers."""
    s = requests.Session()
    s.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    })
    return s

def search_google(session, query, num=10):
    """Search Google and return result URLs."""
    url = f"https://www.google.com/search?q={quote_plus(query)}&num={num}"
    try:
        resp = session.get(url, timeout=10)
        if resp.status_code != 200:
            logger.warning(f"Google returned {resp.status_code}")
            return []
        
        # Extract URLs from search results
        # LinkedIn profile URLs from results
        linkedin_urls = re.findall(r'https?://(?:www\.)?linkedin\.com/in/[\w.%+-]+', resp.text)
        # Clean up
        results = []
        for u in linkedin_urls:
            u = re.sub(r'&.*$', '', u)
            if u not in results:
                results.append(u)
        return results
    except Exception as e:
        logger.error(f"Google search error: {e}")
        return []

def search_duckduckgo(session, query, num=10):
    """Search DuckDuckGo and return result URLs."""
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    try:
        resp = session.get(url, timeout=10)
        if resp.status_code != 200:
            return []
        
        # Extract LinkedIn URLs from DDG results
        linkedin_urls = re.findall(r'https?://(?:www\.)?linkedin\.com/in/[\w.%+-]+', resp.text)
        results = []
        for u in linkedin_urls:
            u = re.sub(r'&.*$', '', u)
            if u not in results:
                results.append(u)
        return results
    except Exception as e:
        logger.error(f"DDG search error: {e}")
        return []

def extract_name_from_url(url):
    """Extract a readable name from a LinkedIn URL."""
    # /in/john-doe/ or /in/johndoe
    match = re.search(r'/in/([\w.-]+)', url)
    if match:
        slug = match.group(1)
        # Remove trailing numbers, dots
        slug = re.sub(r'[.\-]+\d+$', '', slug)
        # Convert dashes/dots to spaces
        name = re.sub(r'[-.]', ' ', slug).strip()
        # Capitalize
        name = name.title()
        # Filter out obvious non-names
        skip = ['unavailable', 'deactivated', 'deleted', 'profile']
        if name.lower() in skip or len(name) < 3:
            return ""
        return name
    return ""

def find_owner_for_company(session, company_name, company_linkedin_url=""):
    """
    Search for the owner/founder of a company using multiple strategies:
    1. Google: site:linkedin.com/in "{company}" founder OR CEO
    2. DuckDuckGo: same query
    3. Parse company LinkedIn page directly (if accessible)
    """
    strategies = [
        lambda: search_google(session, f'site:linkedin.com/in "{company_name}" founder OR CEO OR owner', 10),
        lambda: search_duckduckgo(session, f'site:linkedin.com/in "{company_name}" founder OR CEO OR owner', 10),
        lambda: search_google(session, f'linkedin.com/in "{company_name}" co-founder OR managing director', 5),
    ]
    
    for strategy in strategies:
        try:
            urls = strategy()
            if urls:
                return urls
        except Exception as e:
            logger.debug(f"Strategy failed: {e}")
            continue
    
    return []

# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    logger.info("=" * 60)
    logger.info("LinkedIn Owner Scraper v2 - Starting")
    logger.info(f"Daily target: {DAILY_TARGET} profiles")
    logger.info("=" * 60)
    
    # Load progress
    progress = load_progress()
    today = datetime.now().strftime("%Y-%m-%d")
    if progress.get("last_date") != today:
        progress["processed_companies"] = []
        progress["last_date"] = today
        logger.info("New day - reset progress")
    
    # Load leads
    leads = load_crm_leads()
    logger.info(f"Total leads needing owner scrape: {len(leads)}")
    
    already_done = set(progress.get("processed_companies", []))
    remaining = [l for l in leads if l.get("Company Name", "") not in already_done]
    logger.info(f"Remaining: {len(remaining)}")
    
    if not remaining:
        logger.info("All leads processed!")
        return
    
    today_batch = remaining[:DAILY_TARGET]
    logger.info(f"Today's batch: {len(today_batch)} companies")
    
    # Load existing results
    all_results = load_existing_results()
    
    # Create session
    session = get_session()
    
    # Process each company
    collected = 0
    for i, lead in enumerate(today_batch):
        company_name = lead.get("Company Name", "")
        company_li = lead.get("LinkedIn", "").strip()
        
        logger.info(f"\n[{i+1}/{len(today_batch)}] {company_name}")
        
        # Find owner URLs
        owner_urls = find_owner_for_company(session, company_name, company_li)
        
        if owner_urls:
            # Take the first (best) result
            best_url = owner_urls[0]
            owner_name = extract_name_from_url(best_url)
            
            entry = {
                "company": company_name,
                "company_linkedin": company_li,
                "owner_name": owner_name,
                "owner_linkedin": best_url,
                "all_found": owner_urls[:5],
                "scraped_at": datetime.now().isoformat()
            }
            all_results.append(entry)
            collected += 1
            
            # Update CRM cache
            update_crm_cache(company_name, owner_name, best_url)
            
            logger.info(f"  ✓ Found: {owner_name} → {best_url}")
            progress["processed_companies"].append(company_name)
            progress["total_collected"] = progress.get("total_collected", 0) + 1
        else:
            logger.info(f"  ✗ No owner found")
            progress["processed_companies"].append(company_name)
        
        # Save progress
        save_progress(progress)
        
        # Delay
        if i < len(today_batch) - 1:
            delay = random.uniform(MIN_DELAY, MAX_DELAY)
            logger.info(f"  Waiting {delay:.1f}s...")
            time.sleep(delay)
    
    # Save all results
    with open(OUTPUT_FILE, "w") as f:
        json.dump(all_results, f, indent=2)
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info(f"COMPLETE - Collected: {collected} new owner profiles today")
    logger.info(f"Total collected overall: {len(all_results)}")
    logger.info(f"Results saved to: {OUTPUT_FILE}")
    logger.info("=" * 60)
    
    print(f"\n📊 LinkedIn Owner Scraper Report ({today})")
    print(f"   Processed: {len(today_batch)} companies")
    print(f"   Found owners: {collected}")
    print(f"   Total collected: {len(all_results)}/{len(leads)}")
    print(f"   Remaining: {len(leads) - len(all_results)}")


def update_crm_cache(company_name, owner_name, owner_linkin_url):
    """Update CRM cache with owner data."""
    try:
        with open(CRM_CACHE) as f:
            crm = json.load(f)
        for lead in crm.get("leads", []):
            if lead.get("Company Name") == company_name:
                lead["Owner Name"] = owner_name
                lead["Owner LinkedIn URL"] = owner_linkin_url
                break
        with open(CRM_CACHE, "w") as f:
            json.dump(crm, f, indent=2)
    except Exception as e:
        logger.error(f"CRM update failed: {e}")


if __name__ == "__main__":
    main()
