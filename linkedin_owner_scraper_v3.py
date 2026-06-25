#!/usr/bin/env python3
"""
LinkedIn Owner Scraper v3
Visits company LinkedIn pages via Playwright, extracts employee profiles,
and identifies the owner/founder/CEO by cross-referencing page text mentions.
No LinkedIn login needed. Rate: ~5 pages/minute.
"""

import os
import sys
import json
import time
import re
import random
import logging
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
    # Ensure format is linkedin.com/company/xxx
    if "linkedin.com/company/" not in url and "linkedin.com/" in url:
        # Try to extract company slug
        match = re.search(r'linkedin\.com/([^/]+)(?:/|$)', url)
        if match:
            slug = match.group(1)
            if slug not in ('in', 'company', 'jobs', 'feed'):
                url = f"https://www.linkedin.com/company/{slug}"
    return url

def identify_owner_from_page(page, company_name):
    """
    Strategy:
    1. Get all profile links on the page
    2. Get page text
    3. Search for CEO/Founder/Owner mentions in text
    4. Match the mentioned name to the profile links
    5. Return best match
    """
    # Step 1: Get all profile links
    links = page.query_selector_all('a[href*="/in/"]')
    profiles = {}
    for link in links:
        href = link.evaluate("el => el.getAttribute('href')") or ""
        text = (link.evaluate("el => el.innerText") or "").strip()
        # Clean URL
        clean_url = href.split("?")[0].rstrip("/")
        if "/in/" in clean_url:
            profiles[clean_url] = text
    
    if not profiles:
        return None
    
    # Step 2: Get page text
    page_text = page.inner_text("body")
    
    # Step 3: Search for executive mentions
    # Patterns: "CEO, {Name}", "our CEO, {Name}", "Founder & CEO, {Name}"
    #           "Name, CEO", "Name is the founder", "Name, Co-founder"
    
    ceo_patterns = [
        r'(?:our\s+)?(?:CEO|Chief Executive Officer)[,\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s*,\s*(?:our\s+)?(?:CEO|Chief Executive Officer)',
        r'(?:Founder|Co-founder|Co-Founder)[&/\s]+(?:CEO\s+)?[,\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s*,\s*(?:Founder|Co-founder|Co-Founder)',
        r'(?:our\s+)?(?:Founder|Co-founder|Co-Founder)[,\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})',
    ]
    
    executive_names = []
    for pattern in ceo_patterns:
        matches = re.findall(pattern, page_text)
        for m in matches:
            name = m.strip()
            if len(name) > 3 and name not in executive_names:
                executive_names.append(name)
    
    # Also check for "Name puts it" / "Name says" patterns (common in LinkedIn posts)
    post_patterns = [
        r'(?:our|the)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:puts?|says?|explains?|notes?|shares?)',
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*,\s*(?:our|the)\s+(?:CTO|COO|CFO|CMO|VP|Head)',
    ]
    for pattern in post_patterns:
        matches = re.findall(pattern, page_text)
        for m in matches:
            name = m.strip()
            if len(name) > 3 and name not in executive_names:
                executive_names.append(name)
    
    if not executive_names:
        return None
    
    # Step 4: Match executive names to profile links
    for exec_name in executive_names:
        exec_parts = exec_name.lower().split()
        for url, link_text in profiles.items():
            link_text_lower = link_text.lower()
            # Match: all parts of exec name appear in link text
            if all(part in link_text_lower for part in exec_parts):
                return {
                    "linkedin": url,
                    "name": link_text,
                    "matched_on": exec_name,
                    "confidence": "high"
                }
    
    # Partial match: first name matches
    for exec_name in executive_names:
        first_name = exec_name.split()[0].lower()
        for url, link_text in profiles.items():
            if first_name in link_text.lower() and len(first_name) > 2:
                return {
                    "linkedin": url,
                    "name": link_text,
                    "matched_on": exec_name,
                    "confidence": "medium"
                }
    
    return None

# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    logger.info("=" * 60)
    logger.info("LinkedIn Owner Scraper v3 - Starting")
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
    
    # Start Playwright
    collected = 0
    errors = 0
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT)
        page = context.new_page()
        
        for i, lead in enumerate(today_batch):
            company_name = lead.get("Company Name", "")
            company_li = lead.get("LinkedIn", "").strip()
            
            logger.info(f"\n[{i+1}/{len(today_batch)}] {company_name}")
            
            company_url = normalize_company_url(company_li)
            
            try:
                page.goto(company_url, timeout=20000, wait_until="domcontentloaded")
                time.sleep(random.uniform(2, 4))
                
                # Check for login wall
                if "login" in page.url or "signup" in page.url:
                    logger.warning(f"  Login wall - skipping")
                    progress["processed_companies"].append(company_name)
                    errors += 1
                    continue
                
                if "checkpoint" in page.url:
                    logger.warning(f"  Checkpoint/Captcha - skipping")
                    progress["processed_companies"].append(company_name)
                    errors += 1
                    continue
                
                # Try to find owner
                result = identify_owner_from_page(page, company_name)
                
                if result:
                    entry = {
                        "company": company_name,
                        "company_linkedin": company_li,
                        "owner_name": result["name"],
                        "owner_linkedin": result["linkedin"],
                        "confidence": result["confidence"],
                        "matched_on": result.get("matched_on", ""),
                        "scraped_at": datetime.now().isoformat()
                    }
                    all_results.append(entry)
                    collected += 1
                    
                    # Update CRM cache
                    update_crm_cache(company_name, result["name"], result["linkedin"])
                    
                    logger.info(f"  ✓ Found: {result['name']} → {result['linkedin']} ({result['confidence']})")
                    progress["processed_companies"].append(company_name)
                    progress["total_collected"] = progress.get("total_collected", 0) + 1
                else:
                    logger.info(f"  ✗ No owner identified")
                    progress["processed_companies"].append(company_name)
                    errors += 1
                
            except PWTimeout:
                logger.warning(f"  Timeout - skipping")
                progress["processed_companies"].append(company_name)
                errors += 1
            except Exception as e:
                logger.error(f"  Error: {e}")
                progress["processed_companies"].append(company_name)
                errors += 1
            
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
    logger.info(f"Errors/skipped: {errors}")
    logger.info(f"Total collected overall: {len(all_results)}")
    logger.info(f"Results saved to: {OUTPUT_FILE}")
    logger.info("=" * 60)
    
    print(f"\n📊 LinkedIn Owner Scraper Report ({today})")
    print(f"   Processed: {len(today_batch)} companies")
    print(f"   Found owners: {collected}")
    print(f"   Skipped: {errors}")
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
