#!/usr/bin/python3
"""
Create LinkedIn Outreach tab in NanoSoft CRM
- Creates a new sheet tab "LinkedIn" in the Google Sheet
- Populates with WL leads that have LinkedIn URLs
- Columns: Company, LinkedIn URL, Country, Status, Connection Sent, Connection Message, Followup Message, Notes
"""
import sys
import os
import json
import time

NANOSOFT_DIR = "/home/ubuntu/nanosoft"
sys.path.insert(0, NANOSOFT_DIR)

from crm import get_crm, SHEET_ID, SCOPES, SERVICE_ACCOUNT_FILE
import gspread
from google.oauth2.service_account import Credentials

LINKEDIN_COLUMNS = [
    "Company Name",
    "LinkedIn URL",
    "Country",
    "Email",
    "Status",
    "Connection Sent",
    "Connection Date",
    "Connection Message",
    "Followup Message",
    "Reply",
    "Notes",
]

# Connection request templates (short, under 300 chars for LinkedIn limit)
CONN_TEMPLATES = [
    "Hi — noticed {company} does solid work. Quick question about how you handle overflow projects. Open to connect?",
    "Hey — {company} caught my eye. Curious how you manage capacity during peak months. Would love to connect.",
    "Hi — saw {company}'s work. Quick thought on white label capacity. Mind if I connect?",
    "Hey — quick one. When {company} has more projects than your team can handle, what happens to the overflow? Connect?",
    "Hi — {company} looks interesting. We help agencies with overflow capacity. Worth connecting?",
]

FOLLOWUP_TEMPLATE = (
    "Thanks for connecting. Quick one — when {company} has more projects than your team can handle, "
    "do you turn clients away or outsource quietly? We help agencies keep those clients in-house. "
    "Worth a 10-min chat sometime?"
)


def get_linkedin_leads():
    """Get all WL leads with LinkedIn URLs, prioritized by status."""
    crm = get_crm()
    all_leads = crm.get_wl_all()

    targets = []
    for l in all_leads:
        company = l.get("Company Name", "").strip()
        linkedin = l.get("LinkedIn", "").strip()
        country = l.get("Country", "").strip()
        email = l.get("Email", "").strip()
        status = l.get("Status", "").strip()

        if not company or not linkedin:
            continue

        # Normalize LinkedIn URL
        if not linkedin.startswith("http"):
            linkedin = "https://" + linkedin

        # Skip already-contacted leads (T2+ or Replied)
        if status in ("T2 Sent", "T3 Sent", "T4 Sent", "Lost"):
            continue

        targets.append({
            "company": company,
            "linkedin": linkedin,
            "country": country,
            "email": email,
            "status": status,
        })

    # Priority: T1 Sent first (already warmed up), then Qualified, then New
    priority = {"T1 Sent": 0, "Sent": 0, "Qualified": 1, "New": 2, "": 3, "Unqualified": 4}
    targets.sort(key=lambda x: priority.get(x["status"], 5))

    return targets


def create_linkedin_sheet():
    """Create the LinkedIn tab in the Google Sheet."""
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)

    # Check if sheet already exists
    existing = [ws.title for ws in sh.worksheets()]
    if "LinkedIn" in existing:
        print("[LINKEDIN-CRM] 'LinkedIn' tab already exists. Updating...")
        ws = sh.worksheet("LinkedIn")
        ws.clear()
    else:
        print("[LINKEDIN-CRM] Creating 'LinkedIn' tab...")
        ws = sh.add_worksheet(title="LinkedIn", rows=500, cols=len(LINKEDIN_COLUMNS))
        time.sleep(2)  # Let Google create it

    # Write headers
    ws.update("A1", [LINKEDIN_COLUMNS])
    time.sleep(1)

    # Get leads
    targets = get_linkedin_leads()
    print(f"[LINKEDIN-CRM] {len(targets)} leads with LinkedIn URLs found")

    if not targets:
        print("[LINKEDIN-CRM] No leads to add.")
        return

    # Build rows
    import random
    rows = []
    for t in targets:
        conn_msg = random.choice(CONN_TEMPLATES).format(company=t["company"])
        followup = FOLLOWUP_TEMPLATE.format(company=t["company"])
        row = [
            t["company"],
            t["linkedin"],
            t["country"],
            t["email"],
            t["status"],
            "",  # Connection Sent (empty for you to fill)
            "",  # Connection Date
            conn_msg,
            followup,
            "",  # Reply
            "",  # Notes
        ]
        rows.append(row)

    # Write in batches of 50
    for i in range(0, len(rows), 50):
        batch = rows[i:i+50]
        ws.update(f"A{i+2}", batch)
        time.sleep(2)
        print(f"[LINKEDIN-CRM] Wrote rows {i+1}-{min(i+50, len(rows))}")

    print(f"[LINKEDIN-CRM] DONE: {len(rows)} leads written to LinkedIn tab")
    print(f"[LINKEDIN-CRM] Sheet URL: https://docs.google.com/spreadsheets/d/{SHEET_ID}")


if __name__ == "__main__":
    create_linkedin_sheet()
