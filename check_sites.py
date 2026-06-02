#!/usr/bin/env python3
import urllib.request, re

websites = [
    ("Works Landscape", "https://workslandscape.com"),
    ("Prime Landscape", "https://primelandscape.com"),
    ("Star Landscape", "https://star-landscape.com"),
    ("Dallas Dental", "https://dallasdentalspecialists.com"),
    ("Redefine Dental", "https://dnadentaldallas.com"),
    ("Janet Texas Realty", "https://texasrealty.com"),
    ("North Gym", "https://northgym.net"),
    ("Care Cleaning", "https://carecleaning.com"),
    ("Pro Plumbing", "https://proplumbing.net"),
    ("bestroofing", "https://bestroofing.net"),
    ("pestpro", "https://pestpro.net"),
    ("cleaning.com", "https://cleaning.com"),
    ("massage.com", "https://massage.com"),
    ("moving.co", "https://moving.co"),
    ("topmoving", "https://topmoving.com"),
]

for name, url in websites:
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15',
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read().decode('utf-8', errors='replace')
            title_match = re.search(r'<title[^>]*>(.*?)</title>', content, re.DOTALL | re.IGNORECASE)
            title = title_match.group(1).strip() if title_match else 'N/A'
            title = re.sub(r'\s+', ' ', title)
            
            desc_match = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', content, re.IGNORECASE)
            if not desc_match:
                desc_match = re.search(r'<meta[^>]*content=["\']([^"\']*)["\'][^>]*name=["\']description["\']', content, re.IGNORECASE)
            desc = desc_match.group(1).strip()[:200] if desc_match else 'N/A'
            desc = re.sub(r'\s+', ' ', desc)
            
            has_viewport = 'viewport' in content.lower()
            
            print(f'{name} ({url}):')
            print(f'  Title: {title[:120]}')
            print(f'  Desc: {desc[:150]}')
            print(f'  Mobile viewport: {has_viewport}')
            print()
    except Exception as e:
        print(f'{name} ({url}): ERROR - {e}')
        print()
