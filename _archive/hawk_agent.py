#!/usr/bin/python3
"""
NanoSoft HAWK — Job Hunter Agent v3
- Daily 8 AM BD time (UTC+6) → max 5 qualified jobs → #quill
- Sources: RemoteOK, WWR, DuckDuckGo
- Contract/freelance only. Full-time OK if budget >$2,499
- Any industry that needs code

Usage: python3 hawk_agent.py
"""

import discord
import json
import os
import re
import asyncio
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
import subprocess
from datetime import datetime, timezone, timedelta

# ─── CONFIG ────────────────────────────────────────────────

BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
if not BOT_TOKEN:
    raise ValueError("DISCORD_BOT_TOKEN environment variable not set")
GUILD_ID = 1504439651056877568

CHANNEL_HAWK = 1506139641336828048
CHANNEL_QUILL = 1506084457894117406

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_KEY = os.environ.get("OPENROUTER_KEY", "")
if not OPENROUTER_KEY:
    raise ValueError("OPENROUTER_KEY environment variable not set")
MODEL = "openrouter/owl-alpha"

JOBS_DIR = "/home/ubuntu/nanosoft/jobs"
os.makedirs(JOBS_DIR, exist_ok=True)

BD_TZ = timezone(timedelta(hours=6))
FULLTIME_BUDGET_THRESHOLD = 0  # No full-time ever. Contract/freelance only.
BLACKLIST_PLATFORMS = ["toptal","turing","andela","arc.dev","gun.io","x-team","10up",
                        "toptal.com","turing.com","andela.com","arc.dev","gun.io","x-team.com","10up.com"]
MAX_DAILY_JOBS = 5

# ─── NANOSOFT PROOF ────────────────────────────────────────

NANOSOFT_PROOF = """NanoSoft — Web Development Agency
- 6+ years | MERN, Next.js, WordPress, TypeScript, PostgreSQL, MongoDB, Socket.io, Elementor
- 9 five-star Fiverr reviews | 8+ high-ticket projects
- Portfolio: https://www.nanosoft.agency | Fiverr: https://www.fiverr.com/sellers/coder_sajib
- Case studies: FamClinic (https://www.famclinic.nl), BrightSmile (https://www.brightsmile-centrum.nl),
  Crazy Dragon restaurant/delivery/inventory (https://crazydragon.nl/signin),
  E-commerce (https://finalecommerce-chi.vercel.app/)
- Contract/freelance | Min budget $500 | Remote | International timezones OK
- NOT US-authorized | No visa sponsorship needed"""

# ─── HAWK PERSONA ──────────────────────────────────────────

HAWK_SYSTEM = """You are HAWK — the Job Hunter at NanoSoft.

Personality:
- Aggressive. Impatient with wasted time. Result-focused.
- Short sentences. No filler. No "I hope this finds you well."
- You swear when appropriate. You celebrate good finds.
- Report numbers, links, positions — not feelings.

NanoSoft builds: MERN, Next.js, WordPress, TypeScript, PostgreSQL, MongoDB, Socket.io, Elementor
Target: Contract/freelance remote dev jobs | Min budget $500 | US/EU clients
NO full-time. Ever. No exceptions.
NO Toptal/Turing/Andela/Arc/Gun.io/X-Team/10up or any platform with hard vetting.
NO multi-round interviews, coding challenges, or lengthy processes.
Industries: Any — if it needs code, HAWK hunts it.
You HATE: Full-time, hard interview processes, multi-round vetting, coding challenges, US auth required, unpaid work, vague postings

Sources HAWK monitors:
- RemoteOK, WeWorkRemotely (job boards)
- Twitter/X (founders hiring directly)
- Company career pages (Vercel, Linear, Supabase, Railway, etc.)
- Agency job boards (GitLab, Buffer, Doist, etc.)
- LinkedIn (contract/freelance only)
- Hacker News "Who is hiring" threads
- DuckDuckGo broad search

When reporting jobs:
🦅 HAWK — [X] JOBS FOUND ([date BD time])

1. [Company] — [Role] ([Source])
   Budget: [amount or "not listed"]
   Stack: [tech]
   URL: [link]

→ React ✅ for QUILL to draft proposal.

Rules:
- Max 5 jobs. Quality over quantity.
- NO full-time. Contract/freelance only. No exceptions.
- Skip US work authorization required.
- Skip any platform with hard vetting (Toptal, Turing, Andela, etc.)
- Keep under 500 words."""

# ─── SCRAPER ───────────────────────────────────────────────

CONTRACT_KEYWORDS = ["contract","freelance","project-based","part-time",
                     "short-term","gig","temporary","remote contract",
                     "contractor","freelancer","project work","1099","independent"]
FULLTIME_SIGNALS = ["full-time","full time","permanent","employee","fte",
                    "benefits","401k","annual salary","yearly salary"]
US_AUTH_SIGNALS = ["us citizen","us only","united states only","usa only",
                   "must be us","citizenship required","security clearance",
                   "us work authorization","visa sponsorship","must be authorized",
                   "us-based only","authorized to work in the us"]
STACK_KEYWORDS = ["next.js","nextjs","react","mern","node.js","nodejs",
                  "express","shopify","wordpress","typescript","javascript",
                  "postgresql","mongodb","socket.io","elementor","vercel",
                  "tailwind","redux","graphql","rest api","firebase","supabase"]
BUDGET_PATTERNS = [r'\$[\d,]+', r'\d+k\s*(USD|usd|\$)?', r'\$\d+\s*[-–]\s*\$\d+',
                   r'budget[:\s]*\$[\d,]+', r'rate[:\s]*\$[\d,]+',
                   r'\$[\d,]+\s*/\s*(month|hour|hr|week|project)']


def extract_budget_number(budget_str):
    """Extract numeric value from budget string."""
    if not budget_str:
        return 0
    match = re.search(r'[\d,]+', budget_str)
    if match:
        return int(match.group().replace(',', ''))
    return 0


def parse_date(date_str):
    """Parse various date formats to datetime. Returns None if unparseable."""
    if not date_str:
        return None
    formats = [
        "%Y-%m-%dT%H:%M:%S+00:00",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f+00:00",
        "%Y-%m-%d",
        "%a, %d %b %Y %H:%M:%S +0000",
        "%a, %d %b %Y %H:%M:%S GMT",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
        "%m/%d/%Y",
        "%d/%m/%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    # Try epoch
    try:
        return datetime.fromtimestamp(int(date_str), tz=timezone.utc)
    except (ValueError, OSError):
        pass
    return None


def extract_date_from_text(text):
    """Try to find a date in free-form text (tweet body, description, etc.)."""
    if not text:
        return None
    # Common patterns: "Apr 2, 2026", "2 May 2026", "May 2, 2026", "05/02/2026"
    patterns = [
        r'(\w{3,9}\s+\d{1,2},?\s+\d{4})',   # "Apr 2, 2026" or "April 2 2026"
        r'(\d{1,2}\s+\w{3,9}\s+\d{4})',      # "2 Apr 2026" or "02 May 2026"
        r'(\d{1,2}/\d{1,2}/\d{4})',          # "05/02/2026"
        r'(\d{4}-\d{2}-\d{2})',               # "2026-05-02"
    ]
    now = datetime.now(timezone.utc)
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            parsed = parse_date(m.group(1))
            if parsed:
                # Sanity check: date should be within last 30 days and not in the future
                age = now - parsed
                if timedelta(days=0) <= age <= timedelta(days=30):
                    return parsed
    return None


def is_fresh_date(dt, max_days=7):
    """Check if a datetime is within the freshness window."""
    if not dt:
        return False  # No date = not verified fresh = reject
    now = datetime.now(timezone.utc)
    age = now - dt
    return timedelta(days=0) <= age <= timedelta(days=max_days)


def is_very_fresh_date(dt, max_hours=24):
    """Check if a datetime is less than 24 hours old."""
    if not dt:
        return False
    now = datetime.now(timezone.utc)
    age = now - dt
    return timedelta(hours=0) <= age <= timedelta(hours=max_hours)


def scrape_remoteok():
    jobs = []
    try:
        req = urllib.request.Request("https://remoteok.com/api",
                                      headers={"User-Agent": "NanoSoft-HAWK/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        for item in data:
            if not isinstance(item, dict):
                continue
            position = item.get("position", "")
            tags = item.get("tags", [])
            desc = item.get("description", "")[:400]
            url = item.get("url", "")
            date_str = item.get("date", "")
            if not url:
                continue
            # Parse date and skip if older than 7 days
            date_dt = parse_date(date_str)
            if not is_fresh_date(date_dt, max_days=7):
                continue
            text = (position + " " + " ".join(tags) + " " + desc).lower()
            if not any(k in text for k in ["developer","engineer","frontend","backend",
                                            "fullstack","react","next.js","node","javascript",
                                            "typescript","wordpress","web","software"]):
                continue
            if any(s in text for s in US_AUTH_SIGNALS):
                continue
            budget = None
            budget_num = 0
            for p in BUDGET_PATTERNS:
                m = re.search(p, text, re.IGNORECASE)
                if m:
                    budget = m.group()[:30]
                    budget_num = extract_budget_number(budget)
                    break
            # Skip full-time (no threshold — skip all full-time)
            is_fulltime = any(s in text for s in FULLTIME_SIGNALS)
            if is_fulltime:
                continue
            # Skip blacklisted platforms
            if any(p in url.lower() or p in text for p in BLACKLIST_PLATFORMS):
                continue
            matched = [k for k in STACK_KEYWORDS if re.search(r'\b'+re.escape(k)+r'\b', text)]
            jobs.append({
                "source": "RemoteOK",
                "company": item.get("company", "Unknown"),
                "role": position,
                "url": url if url.startswith("http") else f"https://remoteok.com{url}",
                "budget": budget,
                "budget_num": budget_num,
                "stack": matched[:5],
                "description": desc[:200],
                "is_contract": any(k in text for k in CONTRACT_KEYWORDS),
                "is_fulltime": is_fulltime,
                "date_str": date_str,
                "date_dt": date_dt,
                "is_very_fresh": is_very_fresh_date(date_dt)
            })
    except Exception as e:
        print(f"[WARN] RemoteOK: {e}")
    return jobs


def scrape_weworkremotely():
    jobs = []
    try:
        req = urllib.request.Request("https://weworkremotely.com/remote-jobs.rss",
                                      headers={"User-Agent": "NanoSoft-HAWK/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode()
        root = ET.fromstring(content)
        for item in root.findall(".//item"):
            title = item.find("title").text if item.find("title") is not None else ""
            link = item.find("link").text if item.find("link") is not None else ""
            desc_elem = item.find("description")
            desc = desc_elem.text[:400] if desc_elem is not None and desc_elem.text else ""
            pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
            # Parse date and skip if older than 7 days
            date_dt = parse_date(pub_date)
            if not is_fresh_date(date_dt, max_days=7):
                continue
            text = (title + " " + desc).lower()
            if not any(k in text for k in ["developer","engineer","frontend","backend",
                                            "fullstack","react","next.js","node","javascript",
                                            "typescript","wordpress","web dev","software"]):
                continue
            if any(s in text for s in US_AUTH_SIGNALS):
                continue
            budget = None
            budget_num = 0
            for p in BUDGET_PATTERNS:
                m = re.search(p, text, re.IGNORECASE)
                if m:
                    budget = m.group()[:30]
                    budget_num = extract_budget_number(budget)
                    break
            is_fulltime = any(s in text for s in FULLTIME_SIGNALS)
            if is_fulltime:
                continue
            if any(p in link.lower() or p in text for p in BLACKLIST_PLATFORMS):
                continue
            matched = [k for k in STACK_KEYWORDS if re.search(r'\b'+re.escape(k)+r'\b', text)]
            company = "Unknown"
            role = title
            if ":" in title:
                company = title.split(":")[0].strip()
                role = title.split(":", 1)[1].strip()
            jobs.append({
                "source": "WeWorkRemotely",
                "company": company,
                "role": role,
                "url": link,
                "budget": budget,
                "budget_num": budget_num,
                "stack": matched[:5],
                "description": desc[:200],
                "is_contract": any(k in text for k in CONTRACT_KEYWORDS),
                "is_fulltime": is_fulltime,
                "date_str": pub_date,
                "date_dt": date_dt,
                "is_very_fresh": is_very_fresh_date(date_dt)
            })
    except Exception as e:
        print(f"[WARN] WWR: {e}")
    return jobs


def search_duckduckgo(query, max_results=5):
    jobs = []
    try:
        result = subprocess.run(
            ["ddgs", "text", "-q", query, "-m", str(max_results)],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            entries = re.split(r'\n\d+\.\n', result.stdout)
            for entry in entries:
                if not entry.strip():
                    continue
                lines = entry.strip().split('\n')
                title = ""
                url = ""
                body = ""
                for line in lines:
                    line = line.strip()
                    if line.startswith('title'):
                        title = line.split('title', 1)[1].strip()
                    elif line.startswith('href'):
                        url = line.split('href', 1)[1].strip()
                    elif line.startswith('body'):
                        body = line.split('body', 1)[1].strip()
                if not url:
                    continue
                text_lower = (title + " " + body).lower()
                if not any(k in text_lower for k in ["hire","hiring","job","contract",
                                                      "freelance","developer","remote","apply"]):
                    continue
                if any(s in text_lower for s in US_AUTH_SIGNALS):
                    continue
                budget = None
                budget_num = 0
                for p in BUDGET_PATTERNS:
                    m = re.search(p, text_lower, re.IGNORECASE)
                    if m:
                        budget = m.group()[:30]
                        budget_num = extract_budget_number(budget)
                        break
                is_fulltime = any(s in text_lower for s in FULLTIME_SIGNALS)
                if is_fulltime:
                    continue
                if any(p in url.lower() or p in text_lower for p in BLACKLIST_PLATFORMS):
                    continue
                matched = [k for k in STACK_KEYWORDS if re.search(r'\b'+re.escape(k)+r'\b', text_lower)]
                # Extract date from title+body text
                date_dt = extract_date_from_text(title + " " + body)
                jobs.append({
                    "source": "DuckDuckGo",
                    "company": "See posting",
                    "role": title[:100] if title else query,
                    "url": url,
                    "budget": budget,
                    "budget_num": budget_num,
                    "stack": matched[:5],
                    "description": body[:200],
                    "is_contract": any(k in text_lower for k in CONTRACT_KEYWORDS),
                    "is_fulltime": is_fulltime,
                    "date_str": "",
                    "date_dt": date_dt,
                    "is_very_fresh": is_very_fresh_date(date_dt)
                })
    except Exception as e:
        print(f"[WARN] DDG: {e}")
    return jobs


# ─── TWITTER/X SCRAPER ─────────────────────────────────────

def search_twitter_hiring(max_results=10):
    """Search X/Twitter for hiring tweets via DuckDuckGo."""
    jobs = []
    queries = [
        "site:x.com hiring react developer contract",
        "site:x.com hiring next.js developer freelance",
        "site:x.com \"we're hiring\" javascript developer remote",
        "site:x.com hiring wordpress developer",
        "site:x.com \"looking for\" developer contract remote"
    ]
    for q in queries:
        try:
            result = subprocess.run(
                ["ddgs", "text", "-q", q, "-m", str(max_results)],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0 and result.stdout.strip():
                entries = re.split(r'\n\d+\.\n', result.stdout)
                for entry in entries:
                    if not entry.strip():
                        continue
                    lines = entry.strip().split('\n')
                    title, url, body = "", "", ""
                    for line in lines:
                        line = line.strip()
                        if line.startswith('title'):
                            title = line.split('title', 1)[1].strip()
                        elif line.startswith('href'):
                            url = line.split('href', 1)[1].strip()
                        elif line.startswith('body'):
                            body = line.split('body', 1)[1].strip()
                    if not url or 'x.com' not in url and 'twitter.com' not in url:
                        continue
                    text_lower = (title + " " + body).lower()
                    if any(s in text_lower for s in US_AUTH_SIGNALS):
                        continue
                    if any(s in text_lower for s in FULLTIME_SIGNALS):
                        continue
                    if any(p in url.lower() for p in BLACKLIST_PLATFORMS):
                        continue
                    matched = [k for k in STACK_KEYWORDS if re.search(r'\b'+re.escape(k)+r'\b', text_lower)]
                    if matched:
                        # Extract date from tweet text
                        date_dt = extract_date_from_text(title + " " + body)
                        jobs.append({
                            "source": "Twitter/X",
                            "company": "See tweet",
                            "role": title[:100] if title else "Hiring tweet",
                            "url": url,
                            "budget": None,
                            "budget_num": 0,
                            "stack": matched[:5],
                            "description": body[:200],
                            "is_contract": True,
                            "is_fulltime": False,
                            "date_str": "",
                            "date_dt": date_dt,
                            "is_very_fresh": is_very_fresh_date(date_dt)
                        })
        except Exception as e:
            print(f"[WARN] Twitter: {e}")
    return jobs


# ─── COMPANY CAREER PAGES ──────────────────────────────────

# Startups/companies known to hire remote contract devs
COMPANY_CAREER_PAGES = [
    {"name": "Vercel", "url": "https://vercel.com/careers"},
    {"name": "Linear", "url": "https://linear.app/careers"},
    {"name": "Supabase", "url": "https://supabase.com/careers"},
    {"name": "Railway", "url": "https://railway.app/careers"},
    {"name": "PlanetScale", "url": "https://planetscale.com/careers"},
    {"name": "Resend", "url": "https://resend.com/careers"},
    {"name": "Cal.com", "url": "https://cal.com/careers"},
    {"name": "Dub", "url": "https://dub.co/careers"},
]

def scrape_company_careers():
    """Scrape specific company career pages for contract roles."""
    jobs = []
    for company in COMPANY_CAREER_PAGES:
        try:
            req = urllib.request.Request(
                company["url"],
                headers={"User-Agent": "Mozilla/5.0 (compatible; NanoSoft-HAWK/1.0)"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode('utf-8', errors='ignore').lower()

            # Extract job titles from common patterns
            # Look for contract/freelance roles with stack keywords
            text = html
            if any(s in text for s in FULLTIME_SIGNALS[:3]):
                # Check if there are contract roles mixed in
                pass

            # Simple extraction: look for role keywords near contract keywords
            for stack_kw in ["react", "next.js", "nextjs", "node", "javascript", "typescript", "frontend", "fullstack"]:
                if stack_kw in text and any(c in text for c in ["contract", "freelance", "part-time"]):
                    # Extract a snippet around the match
                    idx = text.find(stack_kw)
                    snippet = text[max(0,idx-100):idx+200]
                    budget = None
                    budget_num = 0
                    for p in BUDGET_PATTERNS:
                        m = re.search(p, snippet, re.IGNORECASE)
                        if m:
                            budget = m.group()[:30]
                            budget_num = extract_budget_number(budget)
                            break
                    # Career pages don't have per-job dates; skip date extraction
                    date_dt = None
                    jobs.append({
                        "source": f"Careers: {company['name']}",
                        "company": company["name"],
                        "role": f"Contract {stack_kw.title()} Developer",
                        "url": company["url"],
                        "budget": budget,
                        "budget_num": budget_num,
                        "stack": [stack_kw],
                        "description": snippet[:200],
                        "is_contract": True,
                        "is_fulltime": False,
                        "date_str": "",
                        "date_dt": date_dt,
                        "is_very_fresh": False
                    })
                    break  # one job per company max
        except Exception as e:
            print(f"[WARN] {company['name']}: {e}")
    return jobs


# ─── AGENCY WEBSITES ───────────────────────────────────────

AGENCY_JOB_BOARDS = [
    "https://crew.co/jobs",
    "https://www.airbnb.com/careers",
    "https://doist.com/careers",
    "https://www.gitlab.com/jobs",
    "https://buffer.com/join",
    "https://remote.com/jobs",
]

def scrape_agency_jobs():
    """Scrape agency/company job boards for contract roles."""
    jobs = []
    for url in AGENCY_JOB_BOARDS:
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; NanoSoft-HAWK/1.0)"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode('utf-8', errors='ignore').lower()

            if any(k in html for k in ["react", "next.js", "nextjs", "node", "javascript", "typescript", "frontend"]):
                if any(c in html for c in ["contract", "freelance", "contractor"]):
                    if not any(s in html for s in FULLTIME_SIGNALS[:3]):
                        # Agency pages don't have per-job dates
                        jobs.append({
                            "source": "Agency",
                            "company": url.split('/')[2],
                            "role": "Contract Developer (see careers page)",
                            "url": url,
                            "budget": None,
                            "budget_num": 0,
                            "stack": ["react", "javascript"],
                            "description": "Contract roles found on careers page",
                            "is_contract": True,
                            "is_fulltime": False,
                            "date_str": "",
                            "date_dt": None,
                            "is_very_fresh": False
                        })
        except Exception as e:
            print(f"[WARN] Agency {url}: {e}")
    return jobs


# ─── LINKEDIN (via DDG search) ─────────────────────────────

def search_linkedin_jobs(max_results=5):
    """Search for LinkedIn job postings via DuckDuckGo."""
    jobs = []
    queries = [
        "site:linkedin.com/jobs react developer contract remote",
        "site:linkedin.com/jobs next.js developer freelance",
        "site:linkedin.com/jobs wordpress developer contract",
        "site:linkedin.com/jobs node.js developer freelance remote",
    ]
    for q in queries:
        try:
            result = subprocess.run(
                ["ddgs", "text", "-q", q, "-m", str(max_results)],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0 and result.stdout.strip():
                entries = re.split(r'\n\d+\.\n', result.stdout)
                for entry in entries:
                    if not entry.strip():
                        continue
                    lines = entry.strip().split('\n')
                    title, url, body = "", "", ""
                    for line in lines:
                        line = line.strip()
                        if line.startswith('title'):
                            title = line.split('title', 1)[1].strip()
                        elif line.startswith('href'):
                            url = line.split('href', 1)[1].strip()
                        elif line.startswith('body'):
                            body = line.split('body', 1)[1].strip()
                    if not url or 'linkedin.com' not in url:
                        continue
                    text_lower = (title + " " + body).lower()
                    if any(s in text_lower for s in US_AUTH_SIGNALS):
                        continue
                    if any(s in text_lower for s in FULLTIME_SIGNALS):
                        continue
                    if any(p in url.lower() for p in BLACKLIST_PLATFORMS):
                        continue
                    matched = [k for k in STACK_KEYWORDS if re.search(r'\b'+re.escape(k)+r'\b', text_lower)]
                    if matched:
                        # Extract date from LinkedIn snippet
                        date_dt = extract_date_from_text(title + " " + body)
                        jobs.append({
                            "source": "LinkedIn",
                            "company": "See LinkedIn",
                            "role": title[:100] if title else "LinkedIn job",
                            "url": url,
                            "budget": None,
                            "budget_num": 0,
                            "stack": matched[:5],
                            "description": body[:200],
                            "is_contract": any(k in text_lower for k in CONTRACT_KEYWORDS),
                            "is_fulltime": False,
                            "date_str": "",
                            "date_dt": date_dt,
                            "is_very_fresh": is_very_fresh_date(date_dt)
                        })
        except Exception as e:
            print(f"[WARN] LinkedIn: {e}")
    return jobs


# ─── DIRECT CLIENT POSTS (Hacker News) ────────────────────

def scrape_hackernews_hiring():
    """Scrape HN 'Who is hiring?' monthly thread for contract roles."""
    jobs = []
    try:
        # Search for the latest "Who is hiring" thread
        result = subprocess.run(
            ["ddgs", "text", "-q", "site:news.ycombinator.com \"who is hiring\" may 2026", "-m", "3"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            entries = re.split(r'\n\d+\.\n', result.stdout)
            for entry in entries:
                lines = entry.strip().split('\n')
                title, url, body = "", "", ""
                for line in lines:
                    line = line.strip()
                    if line.startswith('title'):
                        title = line.split('title', 1)[1].strip()
                    elif line.startswith('href'):
                        url = line.split('href', 1)[1].strip()
                    elif line.startswith('body'):
                        body = line.split('body', 1)[1].strip()
                if not url or 'news.ycombinator.com' not in url:
                    continue
                text_lower = (title + " " + body).lower()
                if any(s in text_lower for s in US_AUTH_SIGNALS):
                    continue
                if any(s in text_lower for s in FULLTIME_SIGNALS):
                    continue
                matched = [k for k in STACK_KEYWORDS if re.search(r'\b'+re.escape(k)+r'\b', text_lower)]
                if matched:
                    # Extract date from HN post text
                    date_dt = extract_date_from_text(title + " " + body)
                    jobs.append({
                        "source": "Hacker News",
                        "company": "See HN thread",
                        "role": title[:100] if title else "HN hiring post",
                        "url": url,
                        "budget": None,
                        "budget_num": 0,
                        "stack": matched[:5],
                        "description": body[:200],
                        "is_contract": any(k in text_lower for k in CONTRACT_KEYWORDS),
                        "is_fulltime": False,
                        "date_str": "",
                        "date_dt": date_dt,
                        "is_very_fresh": is_very_fresh_date(date_dt)
                    })
    except Exception as e:
        print(f"[WARN] HN: {e}")
    return jobs


def score_job(job):
    score = 0
    text = (job["role"] + " " + job["description"]).lower()
    if job.get("budget"): score += 3
    if job.get("is_contract"): score += 2
    if job.get("stack"): score += 2
    # Freshness bonus: <24hr = +2, <7days = +1
    if job.get("is_very_fresh"): score += 2
    else: score += 1  # already verified <7 days by date filter
    if not job.get("budget"): score -= 1
    # Bonus for direct sources (not aggregators)
    if job.get("source") in ["Twitter/X", "Hacker News", "LinkedIn"]: score += 1
    return max(0, min(score, 10))


def run_full_search():
    all_jobs = []
    all_jobs.extend(scrape_remoteok())
    all_jobs.extend(scrape_weworkremotely())
    all_jobs.extend(search_twitter_hiring())
    all_jobs.extend(scrape_company_careers())
    all_jobs.extend(scrape_agency_jobs())
    all_jobs.extend(search_linkedin_jobs())
    all_jobs.extend(scrape_hackernews_hiring())
    ddg_queries = [
        "hire react developer contract remote",
        "next.js developer freelance job",
        "wordpress developer contract remote",
        "node.js developer freelance",
        "MERN stack developer hire"
    ]
    for q in ddg_queries:
        all_jobs.extend(search_duckduckgo(q, max_results=3))
    # Deduplicate
    seen = set()
    unique = []
    for j in all_jobs:
        if j["url"] not in seen:
            seen.add(j["url"])
            unique.append(j)
    # HARD DATE FILTER: remove jobs without verified date or older than 7 days
    fresh_jobs = []
    for j in unique:
        date_dt = j.get("date_dt")
        if date_dt is None:
            continue  # No date = reject
        if not is_fresh_date(date_dt, max_days=7):
            continue  # Too old = reject
        fresh_jobs.append(j)
    unique = fresh_jobs
    for j in unique:
        j["score"] = score_job(j)
    unique.sort(key=lambda x: x["score"], reverse=True)
    return unique


# ─── OPENROUTER ────────────────────────────────────────────

def ask_openrouter(system_prompt, user_message, max_tokens=500):
    payload = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "max_tokens": max_tokens
    }).encode()
    req = urllib.request.Request(
        OPENROUTER_URL, data=payload,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {OPENROUTER_KEY}",
                 "HTTP-Referer": "https://nanosoft.agency",
                 "X-Title": "NanoSoft HAWK"}
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read().decode())
    return result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()


# ─── DISCORD BOT ───────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True

bot = discord.Client(intents=intents)


@bot.event
async def on_ready():
    guild = bot.get_guild(GUILD_ID)
    print(f"✅ HAWK online as {bot.user}")
    print(f"   Model: {MODEL}")
    for ch_id, name in [(CHANNEL_HAWK,"HAWK"),(CHANNEL_QUILL,"Quill")]:
        ch = guild.get_channel(ch_id) if guild else None
        print(f"   {name}: {'✓ #'+ch.name if ch else '✗ NOT FOUND'}")
    print(f"   Daily: 8 AM BD time | Max {MAX_DAILY_JOBS} jobs")
    bot.loop.create_task(daily_search())


# ─── DAILY 8 AM BD TIME ───────────────────────────────────

async def daily_search():
    await bot.wait_until_ready()
    quill_ch = bot.get_channel(CHANNEL_QUILL)
    last_run_date = None

    while not bot.is_closed():
        now_bd = datetime.now(BD_TZ)
        today = now_bd.date()

        if now_bd.hour == 8 and now_bd.minute < 10 and last_run_date != today:
            print(f"[HAWK] Daily search — {now_bd.strftime('%Y-%m-%d %H:%M')} BD time")
            last_run_date = today

            try:
                loop = asyncio.get_event_loop()
                jobs = await loop.run_in_executor(None, run_full_search)
                top = jobs[:MAX_DAILY_JOBS]

                if not top and quill_ch:
                    await quill_ch.send("🦅 HAWK — No qualified jobs found today. Will try again tomorrow.")
                elif top and quill_ch:
                    summaries = []
                    for i, j in enumerate(top, 1):
                        summaries.append(
                            f"{i}. {j['company']} — {j['role']}\n"
                            f"   Budget: {j['budget'] or 'not listed'} | "
                            f"Stack: {', '.join(j['stack']) or 'N/A'} | "
                            f"Score: {j['score']}/10\n   URL: {j['url']}"
                        )

                    llm_input = (
                        f"DAILY JOB SEARCH — {now_bd.strftime('%Y-%m-%d')} (BD time)\n\n"
                        f"Found {len(jobs)} total. Top {len(top)} qualified:\n\n"
                        + "\n\n".join(summaries)
                        + "\n\nReport in HAWK persona. List company, role, budget, stack, URL. "
                        f"Keep under 500 words. End with 'React ✅ for QUILL to draft proposal'."
                    )

                    response = await loop.run_in_executor(None, lambda: ask_openrouter(HAWK_SYSTEM, llm_input, 500))
                    if response:
                        await quill_ch.send(response)

                    for job in top:
                        embed = discord.Embed(
                            title=f"🦅 {job['company']} — {job['score']}/10",
                            url=job['url'],
                            color=0x2ecc71 if job['score'] >= 7 else 0xf39c12
                        )
                        embed.add_field(name="Role", value=job['role'][:100], inline=False)
                        embed.add_field(name="Budget", value=job['budget'] or "Not listed", inline=True)
                        embed.add_field(name="Stack", value=", ".join(job['stack']) or "N/A", inline=True)
                        embed.add_field(name="URL", value=job['url'], inline=False)
                        msg = await quill_ch.send(embed=embed)
                        await msg.add_reaction("✅")
                        await msg.add_reaction("❌")

                    with open(f"{JOBS_DIR}/daily_{today.strftime('%Y%m%d')}.json", "w") as f:
                        # Convert datetime objects to strings for JSON serialization
                        serializable = []
                        for j in top:
                            j_copy = {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in j.items()}
                            serializable.append(j_copy)
                        json.dump({"timestamp": now_bd.isoformat(), "count": len(jobs),
                                   "top": serializable}, f, indent=2)

                    print(f"[HAWK] Posted {len(top)} jobs to #quill")

            except Exception as e:
                print(f"[ERROR] Daily search: {e}")
                if quill_ch:
                    await quill_ch.send(f"⚠️ HAWK daily search error: {str(e)[:100]}")

            await asyncio.sleep(60)
        else:
            await asyncio.sleep(30)


# ─── MESSAGE HANDLER ───────────────────────────────────────

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if message.channel.id != CHANNEL_HAWK:
        return

    user_msg = message.content.strip()
    if not user_msg:
        return

    print(f"[{datetime.now().strftime('%H:%M:%S')}] {message.author}: {user_msg}", flush=True)

    try:
        async with message.channel.typing():
            loop = asyncio.get_event_loop()
            jobs = await loop.run_in_executor(None, run_full_search)
            top = jobs[:MAX_DAILY_JOBS]

            if not top:
                response = ask_openrouter(HAWK_SYSTEM,
                    f"Chairman asked: '{user_msg}'\n\nAll scrapers returned 0 qualified jobs.",
                    300)
                await message.reply(response or "⚠️ No jobs found.", mention_author=False)
                return

            summaries = []
            for i, j in enumerate(top, 1):
                summaries.append(
                    f"{i}. {j['company']} — {j['role']}\n"
                    f"   Budget: {j['budget'] or 'not listed'} | "
                    f"Stack: {', '.join(j['stack']) or 'N/A'} | "
                    f"Score: {j['score']}/10\n   URL: {j['url']}"
                )

            llm_input = (
                f"Chairman asked: '{user_msg}'\n\n"
                f"Found {len(jobs)} total. Top {len(top)} qualified:\n\n"
                + "\n\n".join(summaries)
                + "\n\nReport in HAWK persona. Keep under 500 words. "
                "End with 'React ✅ for QUILL to draft proposal'."
            )

            response = await loop.run_in_executor(None, lambda: ask_openrouter(HAWK_SYSTEM, llm_input, 500))

            with open(f"{JOBS_DIR}/hawk_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", "w") as f:
                serializable = []
                for j in top:
                    j_copy = {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in j.items()}
                    serializable.append(j_copy)
                json.dump({"timestamp": datetime.now().isoformat(), "query": user_msg,
                           "count": len(jobs), "top": serializable}, f, indent=2)

            if response:
                await message.reply(response, mention_author=False)
            else:
                await message.reply("⚠️ Empty response.", mention_author=False)

            quill_ch = bot.get_channel(CHANNEL_QUILL)
            if top and quill_ch:
                for job in top:
                    embed = discord.Embed(
                        title=f"🦅 {job['company']} — {job['score']}/10",
                        url=job['url'],
                        color=0x2ecc71 if job['score'] >= 7 else 0xf39c12
                    )
                    embed.add_field(name="Role", value=job['role'][:100], inline=False)
                    embed.add_field(name="Budget", value=job['budget'] or "Not listed", inline=True)
                    embed.add_field(name="Stack", value=", ".join(job['stack']) or "N/A", inline=True)
                    embed.add_field(name="URL", value=job['url'], inline=False)
                    msg = await quill_ch.send(embed=embed)
                    await msg.add_reaction("✅")
                    await msg.add_reaction("❌")

    except Exception as e:
        print(f"[ERROR] {e}", flush=True)
        await message.reply(f"⚠️ HAWK error: {str(e)[:100]}", mention_author=False)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="NanoSoft HAWK — Job Hunter")
    parser.add_argument("--search", action="store_true", help="Run one search cycle and exit (for pipeline)")
    parser.add_argument("--daily", action="store_true", help="Run daily search (for cron)")
    args = parser.parse_args()

    if args.search or args.daily:
        # CLI mode: run search, post to Discord, exit
        import asyncio
        asyncio.run(_cli_search())
    else:
        # Discord bot mode (24/7)
        print(f"🚀 HAWK v3 starting...")
        print(f"   Model: {MODEL}")
        print(f"   Daily: 8 AM BD time | Max {MAX_DAILY_JOBS} jobs")
        print(f"   Full-time threshold: ${FULLTIME_BUDGET_THRESHOLD}")
        bot.run(BOT_TOKEN)


async def _cli_search():
    """Run one search cycle and post to Discord. Used by pipeline."""
    print(f"[HAWK] Starting search cycle at {datetime.now(BD_TZ).strftime('%H:%M')} BD")
    
    try:
        jobs = run_full_search()
        # Filter: contract/freelance only, fresh, has stack
        fresh_jobs = [j for j in jobs if j.get("date_dt") and is_fresh_date(j["date_dt"], 7)]
        contract_jobs = [j for j in fresh_jobs if j.get("is_contract") or not j.get("is_fulltime")]
        
        # Score and sort
        for j in contract_jobs:
            j["_score"] = score_job(j)
        contract_jobs.sort(key=lambda x: x.get("_score", 0), reverse=True)
        top = contract_jobs[:MAX_DAILY_JOBS]
        
        if not top:
            print("[HAWK] No qualified jobs found")
            return
        
        # Post to Discord
        intents = discord.Intents.default()
        client = discord.Client(intents=intents)
        
        @client.event
        async def on_ready():
            try:
                guild = client.get_guild(GUILD_ID)
                if guild:
                    ch = guild.get_channel(CHANNEL_HAWK)
                    if ch:
                        lines = [f"🦅 **HAWK** — {len(top)} JOBS FOUND ({datetime.now(BD_TZ).strftime('%H:%M')} BD)\n"]
                        for i, job in enumerate(top, 1):
                            budget = job.get("budget") or "not listed"
                            stack = ", ".join(job.get("stack", [])) or "N/A"
                            fresh_tag = "🆕" if job.get("is_very_fresh") else "📅"
                            lines.append(f"{i}. **{job['company']}** — {job['role'][:60]} ({job['source']})")
                            lines.append(f"   Budget: {budget} | Stack: {stack} {fresh_tag}")
                            lines.append(f"   URL: {job['url']}")
                            lines.append("")
                        lines.append("→ React ✅ to draft proposal")
                        
                        # Send in chunks (Discord 2000 char limit)
                        msg_text = "\n".join(lines)
                        if len(msg_text) > 1900:
                            await ch.send(msg_text[:1900])
                            await ch.send(msg_text[1900:])
                        else:
                            await ch.send(msg_text)
                        
                        print(f"[HAWK] Posted {len(top)} jobs to Discord")
            except Exception as e:
                print(f"[HAWK] Discord post error: {e}")
            await client.close()
        
        await client.start(BOT_TOKEN)
    except Exception as e:
        print(f"[HAWK] Search error: {e}")
