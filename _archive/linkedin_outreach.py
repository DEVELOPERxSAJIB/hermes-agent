#!/usr/bin/python3
"""
NanoSoft LinkedIn Outreach v1
- Reads WL leads from CRM
- Finds LinkedIn company pages
- Generates personalized connection messages
- Outputs a daily action list for manual sending (LinkedIn blocks automation)
"""

import json
import os
import sys
from datetime import datetime, timezone

NANOSOFT_DIR = "/home/ubuntu/nanosoft"
sys.path.insert(0, NANOSOFT_DIR)

from crm import get_crm

def get_linkedin_targets():
    """Get WL leads that have LinkedIn URLs or company names to search."""
    crm = get_crm()
    leads = crm.get_wl_all()
    
    targets = []
    for l in leads:
        company = l.get("Company Name", "").strip()
        linkedin = l.get("LinkedIn", "").strip()
        country = l.get("Country", "").strip()
        status = l.get("Status", "")
        pain = l.get("Pain Point", "").strip()
        services = l.get("Services", "").strip()
        
        # Target: Qualified or T1 Sent (not yet replied)
        if status in ("Qualified", "T1 Sent", "Sent", "T2 Sent"):
            if company:
                targets.append({
                    "company": company,
                    "linkedin": linkedin,
                    "country": country,
                    "status": status,
                    "pain": pain,
                    "services": services,
                })
    
    return targets


def generate_connection_msg(lead):
    """Generate a short LinkedIn connection request message (max 300 chars)."""
    company = lead["company"]
    country = lead.get("country", "")
    
    # Short, no pitch. Just observation + question.
    msgs = [
        f"Hi — noticed {company} does solid work. Quick question about how you handle overflow projects. Open to connect?",
        f"Hey — {company} caught my eye. Curious how you manage capacity during peak months. Would love to connect.",
        f"Hi — saw {company}'s work. Quick thought on white label capacity. Mind if I connect?",
    ]
    
    import random
    return random.choice(msgs)


def generate_followup_msg(lead):
    """Message to send after connection is accepted."""
    company = lead["company"]
    
    return (
        f"Thanks for connecting. Quick one — when {company} has more projects than your team can handle, "
        "what happens to the overflow? We help agencies keep those clients in-house. "
        "Worth a 10-min chat sometime?"
    )


def main():
    targets = get_linkedin_targets()
    print(f"[LINKEDIN] {len(targets)} leads available for LinkedIn outreach")
    
    # Filter: prioritize those without LinkedIn URL (need to search)
    with_linkedin = [t for t in targets if t.get("linkedin")]
    without_linkedin = [t for t in targets if not t.get("linkedin")]
    
    print(f"  With LinkedIn URL: {len(with_linkedin)}")
    print(f"  Need to search: {len(without_linkedin)}")
    
    # Generate today's action list (max 20 connection requests/day to avoid flags)
    daily_limit = 20
    today_actions = []
    
    # Prioritize: with LinkedIn first (easier), then without
    for t in (with_linkedin + without_linkedin)[:daily_limit]:
        conn_msg = generate_connection_msg(t)
        followup = generate_followup_msg(t)
        today_actions.append({
            "company": t["company"],
            "linkedin_url": t.get("linkedin", "SEARCH: " + t["company"]),
            "connection_msg": conn_msg,
            "followup_msg": followup,
            "status": t["status"],
        })
    
    # Save action list
    action_file = os.path.join(NANOSOFT_DIR, "linkedin_actions_today.json")
    with open(action_file, "w") as f:
        json.dump(today_actions, f, indent=2)
    
    print(f"\n[LINKEDIN] {len(today_actions)} actions saved to linkedin_actions_today.json")
    print("\n--- TODAY'S LINKEDIN ACTIONS ---")
    for i, a in enumerate(today_actions, 1):
        print(f"\n{i}. {a['company']}")
        print(f"   LinkedIn: {a['linkedin_url']}")
        print(f"   Connect: {a['connection_msg'][:80]}...")
    
    # Also save a CSV for easy viewing
    csv_file = os.path.join(NANOSOFT_DIR, "linkedin_actions_today.csv")
    with open(csv_file, "w") as f:
        f.write("Company,LinkedIn URL,Connection Message,Followup Message,Status\n")
        for a in today_actions:
            f.write(f"\"{a['company']}\",\"{a['linkedin_url']}\",\"{a['connection_msg']}\",\"{a['followup_msg']}\",{a['status']}\n")
    
    print(f"\nCSV saved: {csv_file}")


if __name__ == "__main__":
    main()
