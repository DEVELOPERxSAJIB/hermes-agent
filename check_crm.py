#!/usr/bin/env python3
import json, sys, os

crm_path = os.path.join(os.path.dirname(__file__), 'crm_wl.json')
try:
    with open(crm_path) as f:
        data = json.load(f)
except Exception as e:
    print(f"Error reading CRM: {e}")
    sys.exit(1)

leads = data if isinstance(data, list) else data.get('leads', data.get('data', []))

status_counts = {}
for l in leads:
    s = str(l.get('status', 'unknown')).strip() or '(blank)'
    status_counts[s] = status_counts.get(s, 0) + 1

print("=== CRM STATUS BREAKDOWN ===")
for s, c in sorted(status_counts.items(), key=lambda x: -x[1]):
    print(f"  {s}: {c}")
print(f"  TOTAL: {len(leads)}")

interested = [l for l in leads if str(l.get('status','')).upper() in ('INTERESTED','INTEREST')]
print(f"\n=== INTERESTED LEADS ({len(interested)}) ===")
for l in interested:
    print(f"  Name: {l.get('name','?')}")
    print(f"  Email: {l.get('email','?')}")
    print(f"  Company: {l.get('company','?')}")
    print(f"  Note: {str(l.get('note',''))[:200]}")
    print(f"  ---")

# Check for recent replies in quill log
quill_path = os.path.join(os.path.dirname(__file__), 'quill_wl.log')
if os.path.exists(quill_path):
    with open(quill_path) as f:
        lines = f.readlines()
    recent = lines[-50:]
    print(f"\n=== RECENT QUILL LOG (last 50 lines) ===")
    for l in recent:
        print(l.rstrip())
