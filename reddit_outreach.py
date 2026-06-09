#!/usr/bin/python3
"""
NanoSoft Reddit Outreach v1
- Monitor relevant subreddits for agency owners needing help
- Find posts asking for dev help, overflow, capacity issues
- Generate helpful responses (not spammy)
- Outputs action list for manual comment/post

Target subreddits:
- r/webdev
- r/entrepreneur
- r/startups
- r/agencyowners (if exists)
- r/freelance
- r/smallbusiness
- r/forhire
- r/webdevjobs
"""

import json
import os
import sys
import subprocess
import re

NANOSOFT_DIR = "/home/ubuntu/nanosoft"

SUBREDDITS = [
    "webdev",
    "entrepreneur",
    "startups",
    "freelance",
    "smallbusiness",
    "forhire",
]

# Keywords that signal someone needs dev capacity
KEYWORDS = [
    "need developer",
    "need a developer",
    "looking for developer",
    "freelance developer",
    "overflow",
    "too many projects",
    "capacity",
    "need help with",
    "web development company",
    "hire a developer",
    "agency overloaded",
    "can't handle",
    "backlog",
    "looking for team",
    "outsourcing development",
]


def search_subreddit(subreddit, keyword, limit=25):
    """Search a subreddit using ddgs or curl."""
    query = f"site:reddit.com/r/{subreddit} {keyword}"
    try:
        result = subprocess.run(
            ["ddgs", "text", "-q", query, "-n", str(limit)],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except:
        pass
    return ""


def parse_posts(raw_output):
    """Parse ddgs output into structured posts."""
    posts = []
    if not raw_output:
        return posts
    
    # ddgs text output has URL, title, snippet pattern
    lines = raw_output.split("\n")
    current = {}
    
    for line in lines:
        line = line.strip()
        if line.startswith("http") and "reddit.com" in line:
            if current.get("url"):
                posts.append(current)
            current = {"url": line}
        elif line.startswith("Title:") or line.startswith("title:"):
            current["title"] = line.split(":", 1)[1].strip() if ":" in line else ""
        elif line and "snippet" not in current:
            current["snippet"] = line
    
    if current.get("url"):
        posts.append(current)
    
    return deduplicate_posts(posts)


def deduplicate_posts(posts):
    seen = set()
    out = []
    for p in posts:
        url = p.get("url", "")
        if url and url not in seen:
            seen.add(url)
            out.append(p)
    return out


def score_post(post):
    """Score how relevant a post is for NanoSoft outreach."""
    text = f"{post.get('title', '')} {post.get('snippet', '')}".lower()
    score = 0
    
    high_signal = ["need developer", "looking for developer", "freelance developer",
                   "overflow", "too many projects", "can't handle", "backlog"]
    med_signal = ["need help", "web development", "hire", "outsourcing", "agency",
                  "capacity", "team"]
    
    for kw in high_signal:
        if kw in text:
            score += 3
    for kw in med_signal:
        if kw in text:
            score += 1
    
    # Penalize: job postings (not our target)
    if "hiring" in text and "job" in text:
        score -= 2
    
    return score


def generate_comment(post):
    """Generate a helpful Reddit comment (not a pitch)."""
    title = post.get("title", "").lower()
    
    if "need developer" in title or "looking for" in title:
        return (
            "Hey — have dealt with this exact situation. "
            "The agency we work with handles our overflow white label. "
            "Happy to share how it works if useful. No pitch, just practical."
        )
    elif "overflow" in title or "capacity" in title or "backlog" in title:
        return (
            "Been there. Quick question — when you get more projects than your team can handle, "
            "do you turn clients away or outsource quietly? "
            "White label capacity solved this for us."
        )
    else:
        return (
            "This is common with growing agencies. "
            "White label partnerships help keep those clients in-house "
            "without hiring full-time. Worth exploring."
        )


def main():
    print("[REDDIT] Scanning subreddits for outreach opportunities...")
    
    all_posts = []
    
    # Search a few key subreddits with high-value keywords
    search_pairs = [
        ("webdev", "need developer white label"),
        ("freelance", "agency overflow capacity"),
        ("startups", "need web development company"),
        ("entrepreneur", "outsourcing development"),
        ("forhire", "developer needed"),
    ]
    
    for sub, kw in search_pairs:
        raw = search_subreddit(sub, kw, limit=10)
        posts = parse_posts(raw)
        for p in posts:
            p["subreddit"] = sub
            p["matched_keyword"] = kw
        all_posts.extend(posts)
    
    # Score and filter
    scored = []
    for p in all_posts:
        s = score_post(p)
        p["relevance_score"] = s
        if s >= 2:
            p["suggested_comment"] = generate_comment(p)
            scored.append(p)
    
    scored.sort(key=lambda x: x["relevance_score"], reverse=True)
    
    # Take top 10
    top = scored[:10]
    
    print(f"[REDDIT] Found {len(top)} relevant posts (from {len(all_posts)} total)")
    
    # Save results
    output_file = os.path.join(NANOSOFT_DIR, "reddit_actions_today.json")
    with open(output_file, "w") as f:
        json.dump(top, f, indent=2)
    
    if top:
        print("\n--- TOP REDDIT OPPORTUNITIES ---")
        for i, p in enumerate(top, 1):
            print(f"\n{i}. r/{p.get('subreddit','?')} | Score: {p['relevance_score']}")
            print(f"   {p.get('title','')[:80]}")
            print(f"   {p.get('url','')[:80]}")
            comment = p.get('suggested_comment','')
            print(f"   Comment: {comment[:100]}...")
    else:
        print("\nNo high-relevance posts found today. Will retry tomorrow.")
    
    print(f"\nSaved: {output_file}")


if __name__ == "__main__":
    main()
