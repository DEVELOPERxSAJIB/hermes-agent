"""Social media audit logic — Instagram + LinkedIn scoring"""
import re
import requests
from datetime import datetime, timedelta

def audit_instagram(username):
    """
    Score Instagram presence via oEmbed (no auth).
    Returns: "STRONG" or "WEAK"
    """
    if not username:
        return "WEAK"

    try:
        url = f"https://api.instagram.com/oembed/?url=https://www.instagram.com/{username}/"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200 and resp.json().get("author_name"):
            # Account exists — without browser we can't check post frequency
            # Mark as STRONG if account exists (has presence)
            return "STRONG"
    except Exception:
        pass
    return "WEAK"

def audit_linkedin(company_name):
    """
    Score LinkedIn presence.
    LinkedIn blocks most curl requests to company pages.
    We check if the page returns a 200 with company-like content.
    Returns: "STRONG" or "WEAK"
    """
    if not company_name:
        return "WEAK"

    try:
        slug = company_name.lower().replace(" ", "-").replace(".", "").replace(",", "")
        url = f"https://www.linkedin.com/company/{slug}"
        resp = requests.get(url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        if resp.status_code == 200:
            page = resp.text.lower()
            # Check for actual company page indicators
            if any(kw in page for kw in ['"companyname"', '"companynamealternate"', 'org-top-card', 'organization']):
                return "STRONG"
            # Page exists but might be blocked/empty
            if len(resp.text) > 5000:
                return "STRONG"
    except Exception:
        pass
    return "WEAK"

def assign_angle(ig_score, li_score):
    """
    Assign pitch angle based on audit results.
    Angle B (AI Automation) if either channel is STRONG — they're already investing in marketing.
    Angle A (Social Media Management) if both are WEAK — they need help with presence.
    """
    if ig_score == "STRONG" or li_score == "STRONG":
        return "B"
    return "A"

def run_audit(brokerage_name, instagram_username=None, linkedin_url=None):
    """Run full social audit and return results."""
    ig_score = audit_instagram(instagram_username) if instagram_username else "WEAK"
    li_score = audit_linkedin(brokerage_name) if brokerage_name else "WEAK"
    angle = assign_angle(ig_score, li_score)

    return {
        "Social_Audit": f"IG:{ig_score}|LI:{li_score}",
        "Angle": angle,
        "IG_Score": ig_score,
        "LI_Score": li_score
    }
