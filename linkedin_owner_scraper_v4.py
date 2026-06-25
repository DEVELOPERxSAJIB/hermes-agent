#!/usr/bin/env python3
"""
LinkedIn Owner Scraper v4
Strategy 1: Scrape LinkedIn company page for employee profiles (first = most senior)
Strategy 2: Fallback - search company website for founder name
Strategy 3: Mark as "not found" if nothing works
Rate: ~5-8 pages/minute with respectful delays.
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
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ─── Config ───────────────────────────────────────────────────────────────────
DATA_DIR = Path("/home/ubuntu/nanosoft")
CRM_CACHE = DATA_DIR / "crm_cache.json"
OUTPUT_FILE = DATA_DIR / "linkedin_owners_today.json"
PROGRESS_FILE = DATA_DIR / "linkedin_owners_progress.json"
LOG_FILE = DATA_DIR / "linkedin_owner_scraper.log"

DAILY_TARGET = 20
MIN_DELAY = 5
MAX_DELAY = 10

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

def normalize_company_url(url):
    url = url.strip().rstrip("/")
    if not url.startswith("http"):
        url = "https://" + url
    return url

def get_website_url(company_name, crm_leads):
    """Get company website URL from CRM data."""
    for l in crm_leads:
        if l.get("Company Name") == company_name:
            return l.get("Website", "")
    return ""

def search_company_website(website_url, company_name):
    """Search company website for founder/CEO name."""
    if not website_url:
        return None
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    
    founder_name = None
    
    for path in ["/about", "/team", "/about-us", "/who-we-are", "/"]:
        try:
            resp = session.get(website_url.rstrip("/") + path, timeout=8)
            if resp.status_code != 200:
                continue
            
            text = resp.text
            
            # Look for founder patterns with names
            patterns = [
                r'(?:CEO|Founder|Co-Founder|Co-founder)[&/\s]+(?:and\s+)?(?:CEO\s+)?[<\s]*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s*,\s*(?:our\s+)?(?:CEO|Founder|Co-Founder)',
                r'(?:founded|started|created|established)\s+(?:by\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s+(?:founded|started|created|established)',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, text)
                for m in matches:
                    name = m.strip()
                    # Filter out common non-name words
                    skip = ['the', 'our', 'this', 'that', 'with', 'for', 'and', 'but', 'from', 'inc', 'llc', 'ltd', 'corp']
                    if name.lower() not in skip and len(name) > 3:
                        founder_name = name
                        break
                if founder_name:
                    break
            if founder_name:
                break
        except:
            continue
    
    return founder_name

# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    logger.info("=" * 60)
    logger.info("LinkedIn Owner Scraper v4 - Starting")
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
    
    # Counters
    collected = 0
    not_found = 0
    errors = 0
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT, locale="en-US")
        page = context.new_page()
        
        for i, lead in enumerate(today_batch):
            company_name = lead.get("Company Name", "")
            company_li = lead.get("LinkedIn", "").strip()
            website = get_website_url(company_name, leads)
            
            logger.info(f"\n[{i+1}/{len(today_batch)}] {company_name}")
            
            owner_result = None
            
            # ─── Strategy 1: LinkedIn company page ───
            if company_li:
                company_url = normalize_company_url(company_li)
                try:
                    page.goto(company_url, timeout=20000, wait_until="domcontentloaded")
                    time.sleep(random.uniform(2, 4))
                    
                    # Check for login wall
                    if "login" not in page.url and "checkpoint" not in page.url:
                        # Scroll to load more content
                        page.evaluate("window.scrollTo(0, 1500)")
                        time.sleep(1)
                        
                        # Get profile links
                        links = page.query_selector_all('a[href*="/in/"]')
                        
                        if links:
                            # Take the first profile (LinkedIn shows most relevant/senior first)
                            first_link = links[0]
                            href = first_link.evaluate("el => el.getAttribute('href')") or ""
                            name = (first_link.evaluate("el => el.innerText") or "").strip()
                            clean_url = href.split("?")[0].rstrip("/")
                            
                            if "/in/" in clean_url and len(name) > 1:
                                owner_result = {
                                    "linkedin": clean_url,
                                    "name": name,
                                    "confidence": "high",
                                    "source": "linkedin_company_page"
                                }
                                logger.info(f"  ✓ LinkedIn page: {name} → {clean_url}")
                        
                        # Also check page text for CEO/founder mentions
                        if not owner_result:
                            text = page.inner_text("body")
                            ceo_patterns = [
                                r'(?:our\s+)?(?:CEO|Chief Executive Officer)[,\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',
                                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s*,\s*(?:Founder|Co-founder|Co-Founder)',
                            ]
                            for pattern in ceo_patterns:
                                matches = re.findall(pattern, text)
                                if matches:
                                    exec_name = matches[0].strip()
                                    # Match to a profile link
                                    for link in links:
                                        link_text = (link.evaluate("el => el.innerText") or "")
                                        if exec_name.lower() in link_text.lower():
                                            href = link.evaluate("el => el.getAttribute('href')") or ""
                                            owner_result = {
                                                "linkedin": href.split("?")[0].rstrip("/"),
                                                "name": link_text,
                                                "confidence": "high",
                                                "source": "linkedin_page_text"
                                            }
                                            logger.info(f"  ✓ CEO mention in posts: {link_text} → {href}")
                                            break
                                    if owner_result:
                                        break
                    
                except PWTimeout:
                    logger.warning(f"  Timeout on LinkedIn page")
                except Exception as e:
                    logger.error(f"  LinkedIn error: {e}")
            
            # ─── Strategy 2: Company website ───
            if not owner_result and website:
                logger.info(f"  Trying website: {website}")
                founder_name = search_company_website(website, company_name)
                if founder_name:
                    owner_result = {
                        "linkedin": "",  # No LinkedIn URL from website
                        "name": founder_name,
                        "confidence": "medium",
                        "source": "company_website"
                    }
                    logger.info(f"  ✓ Website found: {founder_name}")
            
            # ─── Record result ───
            if owner_result:
                entry = {
                    "company": company_name,
                    "company_linkedin": company_li,
                    "owner_name": owner_result["name"],
                    "owner_linkedin": owner_result.get("linkedin", ""),
                    "confidence": owner_result["confidence"],
                    "source": owner_result.get("source", "unknown"),
                    "scraped_at": datetime.now().isoformat()
                }
                all_results.append(entry)
                collected += 1
                
                # Update CRM cache
                update_crm_cache(company_name, owner_result["name"], owner_result.get("linkedin", ""))
                
                progress["processed_companies"].append(company_name)
                progress["total_collected"] = progress.get("total_collected", 0) + 1
            else:
                logger.info(f"  ✗ No owner found")
                not_found += 1
                progress["processed_companies"].append(company_name)
            
            # Save progress after each lead
            save_progress(progress)
            
            # Delay between requests
            if i < len(today_batch) - 1:
                delay = random.uniform(MIN_DELAY, MAX_DELAY)
                logger.info(f"  Waiting {delay:.1f}s...")
                time.sleep(delay)
        
        browser.close()
    
    # Save all results
    with open(OUTPUT_FILE, "w") as f:
        json.dump(all_results, f, indent=2)
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info(f"COMPLETE - Collected: {collected} new owner profiles today")
    logger.info(f"Not found: {not_found}")
    logger.info(f"Errors: {errors}")
    logger.info(f"Total collected overall: {len(all_results)}")
    logger.info(f"Results saved to: {OUTPUT_FILE}")
    logger.info("=" * 60)
    
    print(f"\n📊 LinkedIn Owner Scraper Report ({today})")
    print(f"   Processed: {len(today_batch)} companies")
    print(f"   Found owners: {collected}")
    print(f"   Not found: {not_found}")
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
