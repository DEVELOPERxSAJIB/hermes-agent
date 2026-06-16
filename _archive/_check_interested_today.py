#!/usr/bin/env python3
"""Check for interested replies today."""
import json
from datetime import datetime, timezone, timedelta

# Use UTC+6 timezone (Bangladesh/Dhaka) based on detected_at timestamps
tz = timezone(timedelta(hours=6))
today = datetime.now(tz).strftime('%Y-%m-%d')
print(f'Today: {today}')
print('---')

interested_today = []
all_interested = []

with open('/home/ubuntu/nanosoft/replies_wl.jsonl') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except:
            continue
        cls = d.get('classification', '')
        if cls == 'Interested':
            all_interested.append(d)
            detected = d.get('detected_at', '')
            if today in detected:
                interested_today.append(d)

print(f'Total interested replies: {len(all_interested)}')
print(f'Interested replies today ({today}): {len(interested_today)}')
print()

for r in interested_today:
    print(f'  Company: {r.get("company", "?")}')
    print(f'  Email: {r.get("from_email", "?")}')
    print(f'  Snippet: {r.get("snippet", "?")[:300]}')
    print(f'  Detected: {r.get("detected_at", "?")}')
    print()

if not interested_today:
    print('No new interested replies today.')
    print()
    print('Most recent interested replies (all time):')
    for r in all_interested[-5:]:
        print(f'  Company: {r.get("company", "?")} | Date: {r.get("detected_at", "?")} | Email: {r.get("from_email", "?")}')
