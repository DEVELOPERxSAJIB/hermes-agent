#!/usr/bin/python3
"""
NanoSoft LinkedIn Connection Tracker
Use this to:
1. Generate personalized connection request messages
2. Track which connections you've sent
3. Update CRM when people accept

Usage:
  python3 linkedin_connect.py list          # Show pending profiles
  python3 linkedin_connect.py send 1,2,3    # Mark connections as sent
  python3 linkedin_connect.py accept 1,2     # Mark as accepted + send followup
  python3 linkedin_connect.py all           # Generate all messages
"""
import sys, os, json, re
sys.path.insert(0, '/home/ubuntu/nanosoft')
from crm import get_crm

LINKEDIN_MSG_LIMIT = 300  # LinkedIn connection message limit

def clean_name_from_url(url):
    """Try to extract a readable name from LinkedIn URL slug."""
    slug = url.split('/in/')[-1].rstrip('/')
    # Remove trailing numbers
    slug = re.sub(r'-\d+$', '', slug)
    parts = slug.replace('-', ' ').replace('_', ' ').split()
    # Filter out single-char parts and common non-name words
    skip = {'the', 'a', 'an', 'and', 'or', 'of', 'in', 'at', 'to', 'for', 'llc', 'inc', 'co'}
    parts = [p for p in parts if len(p) > 1 and p.lower() not in skip]
    if len(parts) >= 2:
        return f"{parts[0].capitalize()} {parts[1].capitalize()}"
    elif parts:
        return parts[0].capitalize()
    return ""

def gen_message(first_name, company, services=""):
    """Generate a personalized connection request message."""
    if first_name:
        greeting = f"Hi {first_name}"
    else:
        greeting = f"Hi there"
    
    # Keep it under 280 chars (LinkedIn limit for connection requests)
    msg = f"{greeting} — noticed {company} does solid work. Quick question about how you handle dev overflow. Open to connect?"
    return msg[:280]

def gen_followup(first_name, company, services=""):
    """Generate followup message after connection accepted."""
    if first_name:
        greeting = f"Hey {first_name}"
    else:
        greeting = "Hey"
    
    msg = (f"{greeting} — thanks for connecting. Quick one: when {company} has more "
           f"projects than your team can handle, do you turn clients away or outsource quietly? "
           f"We help agencies keep those clients in-house. Worth a 10-min chat sometime?")
    return msg

def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "list"
    
    crm = get_crm()
    ws = crm.sh.worksheet("LinkedIn")
    rows = ws.get_all_records()
    
    if action == "list":
        pending = [(i, r) for i, r in enumerate(rows) if not r.get("Connection Sent", "")]
        print(f"\n=== {len(pending)} PENDING CONNECTION REQUESTS ===\n")
        for idx, (i, r) in enumerate(pending, 1):
            company = r.get("Company Name", "")
            url = r.get("LinkedIn URL", "")
            country = r.get("Country", "")
            name = clean_name_from_url(url)
            msg = gen_message(name, company)
            print(f"{idx}. {name or '(name unknown)'} — {company} ({country})")
            print(f"   {url}")
            print(f"   \"{msg}\"")
            print()
    
    elif action == "all":
        # Generate all messages in a copy-paste friendly format
        pending = [(i, r) for i, r in enumerate(rows) if not r.get("Connection Sent", "")]
        print(f"\n=== ALL {len(pending)} CONNECTION MESSAGES ===\n")
        for idx, (i, r) in enumerate(pending, 1):
            company = r.get("Company Name", "")
            url = r.get("LinkedIn URL", "")
            name = clean_name_from_url(url)
            msg = gen_message(name, company)
            print(f"--- {idx}. {name or '(name unknown)'} | {company} ---")
            print(f"URL: {url}")
            print(f"MSG: {msg}")
            print()
    
    elif action == "send":
        # Mark connections as sent: python3 linkedin_connect.py send 1,2,3
        indices = [int(x)-1 for x in sys.argv[2].split(",")]
        pending = [(i, r) for i, r in enumerate(rows) if not r.get("Connection Sent", "")]
        
        from datetime import datetime, timezone, timedelta
        BD_TZ = timezone(timedelta(hours=6))
        today = datetime.now(BD_TZ).strftime("%Y-%m-%d")
        
        for idx in indices:
            if idx < len(pending):
                row_i, row = pending[idx]
                # row_i is 0-indexed in all_rows, but sheet rows are 1-indexed + 1 for header
                sheet_row = row_i + 2  # +1 for header, +1 for 0->1 indexing
                ws.update_cell(sheet_row, 6, "Yes")      # Connection Sent
                ws.update_cell(sheet_row, 7, today)       # Connection Date
                print(f"✓ Marked '{row.get('Company Name','')}' as sent")
    
    elif action == "accept":
        # Mark as accepted: python3 linkedin_connect.py accept 1,2
        indices = [int(x)-1 for x in sys.argv[2].split(",")]
        pending = [(i, r) for i, r in enumerate(rows) if not r.get("Connection Sent", "")]
        
        for idx in indices:
            if idx < len(pending):
                row_i, row = pending[idx]
                sheet_row = row_i + 2
                company = row.get("Company Name", "")
                url = row.get("LinkedIn URL", "")
                name = clean_name_from_url(url)
                followup = gen_followup(name, company)
                ws.update_cell(sheet_row, 10, "Accepted")  # Reply
                ws.update_cell(sheet_row, 8, followup[:280])  # Connection Message
                print(f"✓ '{company}' accepted. Followup message:")
                print(f"  \"{followup}\"")
    
    elif action == "reject":
        # Mark as rejected/ignored
        indices = [int(x)-1 for x in sys.argv[2].split(",")]
        pending = [(i, r) for i, r in enumerate(rows) if not r.get("Connection Sent", "")]
        
        for idx in indices:
            if idx < len(pending):
                row_i, row = pending[idx]
                sheet_row = row_i + 2
                ws.update_cell(sheet_row, 10, "Rejected")
                print(f"✓ '{row.get('Company Name','')}' marked rejected")

if __name__ == "__main__":
    main()
