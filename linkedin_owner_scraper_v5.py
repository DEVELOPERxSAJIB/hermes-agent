#!/usr/bin/env python3
"""
LinkedIn Owner Scraper v5 (PRODUCTION)
Uses ddgs CLI (DuckDuckGo Search) to find owner/founder LinkedIn profiles.
Rate: ~20 companies in 2-3 minutes (ddgs handles rate limiting internally).
"""

import os
import sys
import json
import time
import re
import random
import logging
import subprocess
import requests
from datetime import datetime, timedelta
from pathlib import Path

# ─── Config ───────────────────────────────────────────────────────────────────
DATA_DIR = Path("/home/ubuntu/nanosoft")
CRM_CACHE = DATA_DIR / "crm_cache.json"
OUTPUT_FILE = DATA_DIR / "linkedin_owners_today.json"
PROGRESS_FILE = DATA_DIR / "linkedin_owners_progress.json"
LOG_FILE = DATA_DIR / "linkedin_owner_scraper.log"

DAILY_TARGET = 20
DDGS_DELAY = 1  # seconds between ddgs queries

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

def ddgs_search(query, max_results=5):
    """Search using ddgs CLI. Returns list of dicts with 'title', 'url', 'body'."""
    try:
        r = subprocess.run(
            ["ddgs", "text", "-q", query, "-m", str(max_results)],
            capture_output=True, text=True, timeout=30
        )
        if r.returncode != 0:
            return []
        
        # Parse plain text output
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
        return []

def extract_owner_from_results(ddgs_results, company_name):
    """
    From ddgs search results, identify the best owner/founder profile.
    Priority: founder > owner > CEO > first result.
    """
    founder_profiles = []
    ceo_profiles = []
    owner_profiles = []
    all_profiles = []
    
    for r in ddgs_results:
        url = r.get("url", r.get("href", ""))
        title = r.get("title", "")
        body = r.get("body", "")
        
        # Only personal profiles
        if "linkedin.com/in/" not in url:
            continue
        if "/company/" in url or "/school/" in url:
            continue
        
        # Clean URL
        url = re.sub(r'\?.*$', '', url).rstrip('/')
        
        # Extract name from title: "John Doe - Founder at Company - LinkedIn"
        name = ""
        if title:
            name_part = title.split(" - ")[0].strip()
            if len(name_part.split()) <= 4:
                name = name_part
        
        if not name:
            # Try to extract from URL slug
            slug = url.split("/in/")[-1] if "/in/" in url else ""
            name_parts = slug.replace("-", " ").replace("_", " ").split()
            if len(name_parts) >= 2:
                name = " ".join(p.capitalize() for p in name_parts[:2])
        
        profile = {"name": name, "url": url, "title": title, "body": body}
        all_profiles.append(profile)
        
        # Categorize by role
        text = (title + " " + body).lower()
        if any(kw in text for kw in ["founder", "co-founder", "cofounder", "co founder"]):
            founder_profiles.append(profile)
        elif any(kw in text for kw in ["ceo", "chief executive"]):
            ceo_profiles.append(profile)
        elif any(kw in text for kw in ["owner", "owner at", "proprietor"]):
            owner_profiles.append(profile)
    
    # Return best match: founder > ceo > owner > first
    for category in [founder_profiles, ceo_profiles, owner_profiles, all_profiles]:
        if category:
            return category[0]
    
    return None

def scrape_website_for_linkedin(website):
    """Fallback: scrape company website for LinkedIn profile links."""
    if not website:
        return []
    
    if not website.startswith("http"):
        website = "https://" + website
    
    profiles = []
    seen = set()
    pages = ["/", "/about", "/team", "/about-us", "/contact"]
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    
    for page in pages:
        try:
            resp = session.get(website.rstrip("/") + page, timeout=8)
            if resp.status_code != 200:
                continue
            
            linkedin_links = re.findall(
                r'https?://(?:www\.)?linkedin\.com/in/[\w.%+-]+',
                resp.text
            )
            
            for link in linkedin_links:
                link = re.sub(r'\?.*$', '', link).rstrip('/')
                if link in seen:
                    continue
                seen.add(link)
                
                slug = link.split("/in/")[-1] if "/in/" in link else ""
                name_parts = slug.replace("-", " ").replace("_", " ").split()
                if len(name_parts) >= 2:
                    name = " ".join(p.capitalize() for p in name_parts[:2])
                    profiles.append({"name": name, "url": link, "source": "website"})
            
            time.sleep(0.5)
        except:
            continue
    
    return profiles

# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    logger.info("=" * 60)
    logger.info("LinkedIn Owner Scraper v5 - Starting")
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
    
    # Process
    collected = 0
    not_found = 0
    
    for i, lead in enumerate(today_batch):
        company_name = lead.get("Company Name", "")
        company_li = lead.get("LinkedIn", "").strip()
        website = lead.get("Website", "").strip()
        owner_email = lead.get("Email", "").strip()
        
        logger.info(f"\n[{i+1}/{len(today_batch)}] {company_name}")
        
        owner_profile = None
        
        # ─── Strategy 1: ddgs search ───
        # Build search queries
        queries = [
            f"site:linkedin.com/in {company_name} founder",
            f"site:linkedin.com/in {company_name} owner",
            f"site:linkedin.com/in {company_name} CEO",
        ]
        
        # If we have owner email, use the name from it as first query
        if owner_email and '@' in owner_email:
            local = owner_email.split('@')[0]
            name_parts = re.split(r'[._\-]', local)
            if len(name_parts) >= 2:
                owner_name = ' '.join(p.capitalize() for p in name_parts if len(p) > 1)
                queries.insert(0, f"site:linkedin.com/in {owner_name} {company_name}")
        
        for query in queries:
            results = ddgs_search(query, max_results=5)
            
            if results:
                owner_profile = extract_owner_from_results(results, company_name)
                if owner_profile:
                    logger.info(f"  ✓ ddgs: {owner_profile['name']} → {owner_profile['url']}")
                    break
            
            time.sleep(DDGS_DELAY)
        
        # ─── Strategy 2: Company website fallback ───
        if not owner_profile and website:
            logger.info(f"  Trying website fallback...")
            web_profiles = scrape_website_for_linkedin(website)
            if web_profiles:
                owner_profile = web_profiles[0]
                logger.info(f"  ✓ Website: {owner_profile['name']} → {owner_profile['url']}")
        
        # ─── Record result ───
        if owner_profile:
            entry = {
                "company": company_name,
                "company_linkedin": company_li,
                "owner_name": owner_profile.get("name", ""),
                "owner_linkedin": owner_profile.get("url", ""),
                "source": owner_profile.get("source", "ddgs"),
                "scraped_at": datetime.now().isoformat()
            }
            all_results.append(entry)
            collected += 1
            
            # Update CRM cache
            update_crm_cache(company_name, owner_profile.get("name", ""), owner_profile.get("url", ""))
            
            progress["processed_companies"].append(company_name)
            progress["total_collected"] = progress.get("total_collected", 0) + 1
        else:
            logger.info(f"  ✗ No owner found")
            not_found += 1
            progress["processed_companies"].append(company_name)
        
        # Save progress
        save_progress(progress)
        
        # Small delay between companies
        if i < len(today_batch) - 1:
            time.sleep(random.uniform(1, 2))
    
    # Save all results
    with open(OUTPUT_FILE, "w") as f:
        json.dump(all_results, f, indent=2)
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info(f"COMPLETE - Collected: {collected} new owner profiles today")
    logger.info(f"Not found: {not_found}")
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
