#!/usr/bin/env python3
"""NanoSoft Daily Progress Report - Cron version"""
import sys
sys.path.insert(0, '/home/ubuntu/nanosoft')

from crm import get_crm
from datetime import datetime, timezone, timedelta
from collections import Counter

BD_TZ = timezone(timedelta(hours=6))
crm = get_crm()
leads = crm.get_wl_all()
status_counts = Counter(l.get('Status', '') for l in leads)
total = len(leads)

sent_log = '/home/ubuntu/nanosoft/emails_sent_wl.jsonl'
total_sent = 0
try:
    with open(sent_log) as f:
        total_sent = sum(1 for line in f if line.strip())
except Exception:
    pass

now = datetime.now(BD_TZ).strftime('%Y-%m-%d %H:%M')

print(f'NanoSoft Daily Report - {now} BD')
print(f'Total leads: {total}')
print(f'Total sent: {total_sent}')
print(f'Qualified: {status_counts.get("Qualified", 0)}')
print(f'T1 Sent: {status_counts.get("T1 Sent", 0)}')
print(f'T2 Sent: {status_counts.get("T2 Sent", 0)}')
print(f'T3 Sent: {status_counts.get("T3 Sent", 0)}')
print(f'T4 Sent: {status_counts.get("T4 Sent", 0)}')
print(f'New: {status_counts.get("New", 0)}')
print(f'Unqualified: {status_counts.get("Unqualified", 0)}')
print(f'Bounced: {status_counts.get("Bounced", 0)}')
