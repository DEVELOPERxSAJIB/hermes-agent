#!/usr/bin/python3
import sys, json, os
sys.path.insert(0, '/home/ubuntu/nanosoft')
os.chdir('/home/ubuntu/nanosoft')

from crm import get_crm
crm = get_crm()
wl = crm.get_wl_all()

stats = {}
for l in wl:
    s = l.get('Status', 'Empty')
    stats[s] = stats.get(s, 0) + 1

print('=== CRM STATUS ===')
print(f'Total WL leads: {len(wl)}')
for s, c in sorted(stats.items()):
    print(f'  {s}: {c}')

# Interested leads
interested = [l for l in wl if l.get('Reply Status') == 'Interested']
print(f'\n=== INTERESTED LEADS: {len(interested)} ===')
for l in interested:
    print(f'  Company: {l.get("Company Name", "N/A")}')
    print(f'  Email: {l.get("Email", "N/A")}')
    print(f'  Person: {l.get("Person Name", "N/A")}')
    snippet = l.get('Reply Snippet', 'N/A')
    print(f'  Reply Snippet: {snippet[:200]}')
    print(f'  Reply Date: {l.get("Reply Date", "N/A")}')
    print('  ---')

# New leads
new_leads = [l for l in wl if l.get('Status') == 'New']
print(f'\n=== NEW LEADS: {len(new_leads)} ===')
for l in new_leads[-5:]:
    print(f'  {l.get("Company Name", "N/A")} | {l.get("Email", "N/A")} | {l.get("Date Found", "N/A")}')

# Qualified
qualified = [l for l in wl if l.get('Status') == 'Qualified']
print(f'\n=== QUALIFIED (waiting): {len(qualified)} ===')

# T1 Sent
t1 = [l for l in wl if l.get('Status') == 'T1 Sent']
print(f'=== T1 SENT: {len(t1)} ===')

# T2 Sent
t2 = [l for l in wl if l.get('Status') == 'T2 Sent']
print(f'=== T2 SENT: {len(t2)} ===')

# Bounced
bounced = [l for l in wl if l.get('Status') == 'Bounced']
print(f'=== BOUNCED: {len(bounced)} ===')

# Unqualified
unq = [l for l in wl if l.get('Status') == 'Unqualified']
print(f'=== UNQUALIFIED: {len(unq)} ===')

# Empty status
empty = [l for l in wl if l.get('Status', 'Empty') == '' or l.get('Status') == 'Empty']
print(f'=== EMPTY STATUS: {len(empty)} ===')

# Also check reply log for any interested not yet in CRM
reply_log = '/home/ubuntu/nanosoft/replies_wl.jsonl'
if os.path.exists(reply_log):
    with open(reply_log) as f:
        replies = [json.loads(line.strip()) for line in f if line.strip()]
    print(f'\n=== REPLY LOG: {len(replies)} entries ===')
    for r in replies[-5:]:
        print(f"  {json.dumps(r, indent=2)[:200]}")
        print('  ---')
