#!/usr/bin/env python3
import json
from datetime import datetime, timezone, timedelta
from collections import Counter

tz = timezone(timedelta(hours=6))
today = datetime(2026, 6, 10, tzinfo=tz).date()

interested = []
all_replies = []
with open('/home/ubuntu/nanosoft/replies_wl.jsonl') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except:
            continue
        all_replies.append(r)
        if r.get('classification') == 'Interested':
            detected = r.get('detected_at','')
            try:
                dt = datetime.fromisoformat(detected)
                if dt.astimezone(tz).date() == today:
                    interested.append(r)
            except:
                pass

print(f'Total replies in file: {len(all_replies)}')
print(f'Interested replies today ({today}): {len(interested)}')
print()

# Show all interested replies regardless of date
all_interested = [r for r in all_replies if r.get('classification') == 'Interested']
print(f'All interested replies (any date): {len(all_interested)}')
for r in all_interested:
    print(f'  Company: {r.get("company","?")}')
    print(f'  Email: {r.get("from_email","?")}')
    print(f'  Detected: {r.get("detected_at","?")}')
    print(f'  Snippet: {r.get("snippet","?")[:200]}')
    print()

# Show breakdown by classification
classifications = Counter(r.get('classification','Unknown') for r in all_replies)
print('Classification breakdown:')
for c, n in classifications.most_common():
    print(f'  {c}: {n}')
