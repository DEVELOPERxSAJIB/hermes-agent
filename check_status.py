#!/usr/bin/env python3
from collections import Counter
import sys
sys.path.insert(0, '/home/ubuntu/nanosoft')
from crm import get_crm

crm = get_crm()
wl = crm.get_wl_all()
qualified = [l for l in wl if l.get('Status') == 'Qualified']
unqualified = [l for l in wl if l.get('Status') == 'Unqualified']
t1_sent = [l for l in wl if l.get('Status') == 'T1 Sent']

print(f'Total leads: {len(wl)}')
print(f'Qualified: {len(qualified)}')
print(f'Unqualified: {len(unqualified)}')
print(f'T1 Sent: {len(t1_sent)}')
print()

print('Qualified leads:')
for l in qualified:
    print(f'  {l.get("Judge Score","?")}/10 | {l.get("Company Name","?")} | {l.get("Email","")[:30]}')
print()

print('T1 Sent leads:')
for l in t1_sent:
    print(f'  {l.get("Judge Score","?")}/10 | {l.get("Company Name","?")} | {l.get("Email","")[:30]}')
print()

statuses = Counter(l.get('Status','EMPTY') for l in wl)
print('All statuses:')
for s, c in statuses.most_common():
    print(f'  {s}: {c}')
