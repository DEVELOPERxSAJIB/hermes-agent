#!/usr/bin/env python3
import json
from datetime import datetime, timezone, timedelta

tz = timezone(timedelta(hours=6))
today = datetime(2026, 6, 10, tzinfo=tz).date()

interested = []
with open('/home/ubuntu/nanosoft/replies_wl.jsonl') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except:
            continue
        if r.get('classification') == 'Interested':
            detected = r.get('detected_at','')
            try:
                dt = datetime.fromisoformat(detected)
                if dt.astimezone(tz).date() == today:
                    interested.append(r)
            except:
                pass

if interested:
    print(f'FOUND {len(interested)} INTERESTED REPLIES TODAY:')
    for r in interested:
        print(f'  Company: {r.get("company","?")}')
        print(f'  Email: {r.get("from_email","?")}')
        print(f'  Snippet: {r.get("snippet","?")[:200]}')
        print(f'  Detected: {r.get("detected_at","?")}')
        print()
else:
    print('No interested replies today (2026-06-10)')
