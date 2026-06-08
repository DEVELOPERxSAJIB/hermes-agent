#!/usr/bin/env python3
import sys, json, os
sys.path.insert(0, '/home/ubuntu/nanosoft')
os.chdir('/home/ubuntu/nanosoft')

from crm import get_crm
crm = get_crm()
wl = crm.get_wl_all()

# Full reply log
print("=== FULL REPLY LOG ===")
replies = [l for l in wl if l.get('Reply Status')]
for l in replies:
    print(f"  Company: {l.get('Company Name', 'N/A')}")
    print(f"  Email: {l.get('Email', 'N/A')}")
    print(f"  Person: {l.get('Person Name', 'N/A')}")
    print(f"  Status: {l.get('Reply Status', 'N/A')}")
    print(f"  Template: {l.get('Template', 'N/A')}")
    snippet = l.get('Reply Snippet', 'N/A')
    print(f"  Reply Snippet: {snippet[:300]}")
    print(f"  Reply Date: {l.get('Reply Date', 'N/A')}")
    print(f"  ---")

# Interested leads
interested = [l for l in wl if l.get('Reply Status') == 'Interested']
print(f"\n=== INTERESTED LEADS: {len(interested)} ===")
for l in interested:
    print(f"  Company: {l.get('Company Name', 'N/A')}")
    print(f"  Email: {l.get('Email', 'N/A')}")
    print(f"  Person: {l.get('Person Name', 'N/A')}")
    snippet = l.get('Reply Snippet', 'N/A')
    print(f"  Reply Snippet: {snippet[:300]}")
    print(f"  Reply Date: {l.get('Reply Date', 'N/A')}")
    print(f"  ---")
