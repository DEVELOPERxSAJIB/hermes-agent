import urllib.request, re

# Try multiple DDG endpoints
endpoints = [
    "https://html.duckduckgo.com/html/?q=white+label+web+development+agency",
    "https://lite.duckduckgo.com/lite/?q=white+label+web+development+agency",
    "https://duckduckgo.com/?q=white+label+web+development+agency&ia=web",
]

for url in endpoints:
    print(f"\n--- {url[:60]}... ---")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0'})
        resp = urllib.request.urlopen(req, timeout=10)
        html = resp.read().decode('utf-8', errors='ignore')
        print(f"Length: {len(html)}")
        
        # Extract external links
        links = re.findall(r'href="(https?://(?!duckduckgo)[^"]+)"', html)
        ext = [l[0] for l in links if not l[0].startswith('https://duckduckgo')][:10]
        for l in ext[:5]:
            print(f"  {l[:100]}")
        if not ext:
            print("  (no external links found)")
    except Exception as e:
        print(f"  Error: {e}")
