#!/usr/bin/env python3
"""
LinkedIn Owner Scraper
Visits company LinkedIn pages and extracts owner/founder profile URLs.
Free method: parses the public company page HTML for founder/owner profiles.
Rate: ~10 pages/minute (respectful delays).
"""

import os
import sys
import json
import time
import re
import random
import csv
import logging
import requests
from datetime import datetime, timedelta
from pathlib import Path

# Use playwright for LinkedIn (handles JS rendering)
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ─── Config ───────────────────────────────────────────────────────────────────
DATA_DIR = Path("/home/ubuntu/nanosoft")
CRM_CACHE = DATA_DIR / "crm_cache.json"
OUTPUT_FILE = DATA_DIR / "linkedin_owners_today.json"
PROGRESS_FILE = DATA_DIR / "linkedin_owners_progress.json"
LOG_FILE = DATA_DIR / "linkedin_owner_scraper.log"

DAILY_TARGET = 20
MIN_DELAY_SEC = 4  # between page loads
MAX_DELAY_SEC = 8

# LinkedIn session cookie (you need to log in once)
# export LINKEDIN_COOKIE="..."  # or put here
LINKEDIN_COOKIE = os.environ.get("LINKEDIN_COOKIE", "")

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
    """Load progress tracking (which leads already processed)."""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"processed": [], "last_date": "", "total_collected": 0}

def save_progress(progress):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)

def load_crm_leads():
    """Load leads from CRM cache that have company LinkedIn but no owner."""
    with open(CRM_CACHE) as f:
        crm = json.load(f)
    leads = crm.get("leads", [])
    
    # Filter: has company LinkedIn, no owner LinkedIn
    need_owner = []
    for l in leads:
        company_li = l.get("LinkedIn", "").strip()
        owner_li = l.get("Owner LinkedIn URL", "").strip()
        if company_li and not owner_li:
            need_owner.append(l)
    
    return need_owner

def normalize_url(url):
    """Normalize LinkedIn URL."""
    url = url.strip().rstrip("/")
    if not url.startswith("http"):
        url = "https://" + url
    return url

def load_existing_results():
    """Load previously collected owner data."""
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE) as f:
            return json.load(f)
    return []

# ─── Scraper ──────────────────────────────────────────────────────────────────
class LinkedInOwnerScraper:
    def __init__(self, cookie=""):
        self.cookie = cookie
        self.browser = None
        self.context = None
        self.page = None
        self.results = []
        self.processed_urls = set()
        
    def start(self):
        """Launch browser with LinkedIn session."""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True)
        
        context_opts = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "viewport": {"width": 1920, "height": 1080},
        }
        
        if self.cookie:
            context_opts["extra_http_headers"] = {"Cookie": self.cookie}
        
        self.context = self.browser.new_context(**context_opts)
        self.page = self.context.new_page()
        
        # If we have a cookie, go to LinkedIn to verify session
        if self.cookie:
            logger.info("Verifying LinkedIn session...")
            self.page.goto("https://www.linkedin.com/feed/", timeout=15000)
            time.sleep(3)
            url = self.page.url
            if "login" in url or "signup" in url:
                logger.warning("LinkedIn session expired! Need new cookie.")
                return False
            logger.info("LinkedIn session active!")
        else:
            logger.warning("No LinkedIn cookie provided. Will try public pages (limited).")
        
        return True
    
    def scrape_company_page(self, company_url):
        """
        Visit a company LinkedIn page and extract owner/founder profile URLs.
        Looks for: "Founder", "CEO", "Owner", "Co-founder" in the overview.
        """
        company_url = normalize_url(company_url)
        
        if company_url in self.processed_urls:
            return None
        self.processed_urls.add(company_url)
        
        logger.info(f"Visiting: {company_url}")
        
        try:
            self.page.goto(company_url, timeout=20000, wait_until="domcontentloaded")
            time.sleep(random.uniform(2, 4))
            
            # Check if blocked / login wall
            current_url = self.page.url
            if "login" in current_url or "signup" in current_url:
                logger.warning(f"Login wall hit for {company_url}")
                return {"error": "login_required", "url": company_url}
            
            # Check for challenge/captcha
            if "checkpoint" in current_url:
                logger.warning(f"Checkpoint/Captcha for {company_url}")
                return {"error": "captcha", "url": company_url}
            
            # Try to extract founder/owner info from the page
            owner_data = self._extract_owner_data()
            
            if owner_data:
                logger.info(f"  ✓ Found: {owner_data.get('name', 'unknown')} -> {owner_data.get('linkedin', '')}")
                return owner_data
            else:
                logger.info(f"  ✗ No owner found on page")
                return {"error": "not_found", "url": company_url}
                
        except PWTimeout:
            logger.warning(f"  Timeout loading {company_url}")
            return {"error": "timeout", "url": company_url}
        except Exception as e:
            logger.error(f"  Error: {e}")
            return {"error": str(e), "url": company_url}
    
    def _extract_owner_data(self):
        """Extract owner/founder LinkedIn URL from the company page."""
        page = self.page
        
        # Strategy 1: Look for founder/CEO links in the page
        # LinkedIn company pages often have links to founder profiles
        
        # Try to find all LinkedIn profile links on the page
        profile_links = page.query_selector_all('a[href*="/in/"]')
        
        candidates = []
        
        for link in profile_links:
            href = link.get_attribute("href") or ""
            text = (link.inner_text() or "").strip()
            
            # Filter out obvious non-people links
            if "/company/" in href or "/jobs/" in href or "/feed/" in href:
                continue
            
            # Check if the link text or surrounding context mentions founder/CEO/owner
            parent = link.evaluate_handle("el => el.closest('section') || el.parentElement")
            parent_text = ""
            try:
                parent_text = parent.inner_text() or ""
            except:
                pass
            
            founder_keywords = ["founder", "ceo", "owner", "co-founder", "managing director", 
                              "president", "chief executive", "creator", "started this company"]
            
            is_founder = any(kw in parent_text.lower() for kw in founder_keywords)
            high_confidence = is_founder and len(text) > 2
            
            candidates.append({
                "linkedin": href.split("?")[0],
                "name": text,
                "is_founder": is_founder,
                "confidence": "high" if high_confidence else "medium",
                "context": parent_text[:200] if parent_text else ""
            })
        
        if not candidates:
            return None
        
        # Sort: founder matches first
        candidates.sort(key=lambda x: (x["is_founder"], x["confidence"] == "high"), reverse=True)
        
        best = candidates[0]
        return {
            "linkedin": best["linkedin"],
            "name": best["name"],
            "confidence": best["confidence"],
            "is_founder": best["is_founder"]
        }
    
    def scrape_alternative_method(self, company_name):
        """
        Alternative: Use Google search to find owner LinkedIn.
        Visits google.com/search?q=site:linkedin.com/in "{company_name}" founder
        Falls back when company page doesn't show owner directly.
        """
        search_query = f'site:linkedin.com/in "{company_name}" founder OR CEO OR owner'
        search_url = f"https://www.google.com/search?q={requests.utils.quote(search_query)}"
        
        try:
            self.page.goto(search_url, timeout=15000, wait_until="domcontentloaded")
            time.sleep(2)
            
            # Extract LinkedIn profile URLs from search results
            results = self.page.query_selector_all('a[href*="/in/"]')
            for r in results:
                href = r.get_attribute("href") or ""
                if "/in/" in href and "/company/" not in href:
                    return href.split("?")[0]
        except:
            pass
        
        return None
    
    def close(self):
        if self.browser:
            self.browser.close()
        if hasattr(self, 'playwright'):
            self.playwright.stop()


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    logger.info("=" * 60)
    logger.info("LinkedIn Owner Scraper - Starting")
    logger.info(f"Daily target: {DAILY_TARGET} profiles")
    logger.info("=" * 60)
    
    # Load progress
    progress = load_progress()
    
    # Reset if new day
    today = datetime.now().strftime("%Y-%m-%d")
    if progress.get("last_date") != today:
        progress["processed"] = []
        progress["last_date"] = today
        logger.info("New day - reset progress")
    
    # Load leads needing owner data
    leads = load_crm_leads()
    logger.info(f"Total leads needing owner scrape: {len(leads)}")
    
    # Filter out already processed
    already_done = set(progress.get("processed", []))
    remaining = [l for l in leads if normalize_url(l.get("LinkedIn", "")) not in already_done]
    logger.info(f"Remaining (not processed): {len(remaining)}")
    
    if not remaining:
        logger.info("All leads processed! Nothing to do.")
        return
    
    # Take only today's batch
    today_batch = remaining[:DAILY_TARGET]
    logger.info(f"Today's batch: {len(today_batch)} leads")
    
    # Load existing results
    all_results = load_existing_results()
    
    # Start scraper
    scraper = LinkedInOwnerScraper(cookie=LINKEDIN_COOKIE)
    
    if not scraper.start():
        logger.error("Cannot start scraper - no valid LinkedIn session")
        logger.info("To use this scraper, set LINKEDIN_COOKIE environment variable")
        logger.info("Get it from: browser DevTools → Application → Cookies → li_at")
        sys.exit(1)
    
    # Scrape each company
    collected = 0
    for i, lead in enumerate(today_batch):
        company_li = lead.get("LinkedIn", "").strip()
        company_name = lead.get("Company Name", "")
        
        logger.info(f"\n[{i+1}/{len(today_batch)}] {company_name}")
        
        # Scrape company page
        result = scraper.scrape_company_page(company_li)
        
        if result and "error" not in result:
            # Success!
            entry = {
                "company": company_name,
                "company_linkedin": normalize_url(company_li),
                "owner_name": result.get("name", ""),
                "owner_linkedin": result.get("linkedin", ""),
                "confidence": result.get("confidence", "medium"),
                "is_founder": result.get("is_founder", False),
                "scraped_at": datetime.now().isoformat()
            }
            all_results.append(entry)
            collected += 1
            
            # Update CRM cache
            update_crm_cache(company_name, result)
            
            progress["processed"].append(normalize_url(company_li))
            progress["total_collected"] = progress.get("total_collected", 0) + 1
        else:
            # Record the attempt
            progress["processed"].append(normalize_url(company_li))
        
        # Save progress after each lead
        save_progress(progress)
        
        # Delay between requests (respectful)
        if i < len(today_batch) - 1:
            delay = random.uniform(MIN_DELAY_SEC, MAX_DELAY_SEC)
            logger.info(f"  Waiting {delay:.1f}s before next...")
            time.sleep(delay)
    
    # Save results
    with open(OUTPUT_FILE, "w") as f:
        json.dump(all_results, f, indent=2)
    
    scraper.close()
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info(f"COMPLETE - Collected: {collected} new owner profiles today")
    logger.info(f"Total collected overall: {len(all_results)}")
    logger.info(f"Results saved to: {OUTPUT_FILE}")
    logger.info("=" * 60)
    
    # Print summary for cron report
    print(f"\n📊 LinkedIn Owner Scraper Report ({today})")
    print(f"   Processed: {len(today_batch)} company pages")
    print(f"   Found owners: {collected}")
    print(f"   Total collected: {len(all_results)}/{len(leads)}")
    print(f"   Remaining: {len(leads) - len(all_results)}")


def update_crm_cache(company_name, result):
    """Update the CRM cache with owner data."""
    try:
        with open(CRM_CACHE) as f:
            crm = json.load(f)
        
        for lead in crm.get("leads", []):
            if lead.get("Company Name") == company_name:
                lead["Owner Name"] = result.get("name", "")
                lead["Owner LinkedIn URL"] = result.get("linkedin", "")
                break
        
        with open(CRM_CACHE, "w") as f:
            json.dump(crm, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to update CRM cache: {e}")


if __name__ == "__main__":
    main()
