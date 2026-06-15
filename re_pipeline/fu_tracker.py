"""
CRM Follow-Up Tracker — sends FU1/FU2/FU3 to leads that got T1 but no follow-up.
Sheet columns: Col 16=FU 1, Col 17=FU 2, Col 18=FU 3, Col 19=Status
"""
import sys
import os
import json
import time
from datetime import datetime, timedelta

sys.path.insert(0, '/home/ubuntu/nanosoft')
os.chdir('/home/ubuntu/nanosoft')
from crm import get_crm
from smtp_sender import send_email

# Follow-up templates
FU1_TEMPLATE = """Subject: Quick follow-up — NanoSoft Agency

Hi {first_name},

I sent you an email a few days ago about NanoSoft's white-label development services.

Just wanted to make sure it didn't get buried. We help agencies like yours ship overflow projects under your brand — 4-week delivery, full handoff, client never knows.

Worth a quick 15-minute call this week?

SaJib Shikder
NanoSoft Agency
nanosoft.agency"""

FU2_TEMPLATE = """Subject: One more thing about {company}

Hi {first_name},

Following up one more time. I know you're busy, so I'll keep it short.

We just finished a food ordering app for an agency in Amsterdam — 4 weeks, fully handed off. If you ever hit capacity or can't hire fast enough, we're one Slack message away.

Open to a quick chat?

SaJib Shikder
NanoSoft Agency"""

FU3_TEMPLATE = """Subject: Closing the loop

Hi {first_name},

I've reached out a few times — I'll assume the timing isn't right.

Whenever you need extra dev capacity, I'm one message away.

Good luck with everything.

SaJib Shikder
NanoSoft Agency"""

def get_first_name(contact_name, email):
    if contact_name:
        return contact_name.strip().split()[0]
    if email and '@' in email:
        local = email.split('@')[0]
        name = local.split('.')[0].split('_')[0]
        return name.capitalize()
    return ""

def extract_subject_body(template, first_name, company):
    """Extract subject and body from template."""
    body = template.format(first_name=first_name, company=company)
    subject = ""
    body_lines = []
    for line in body.split("\n"):
        if line.startswith("Subject:"):
            subject = line.replace("Subject:", "").strip()
        else:
            body_lines.append(line)
    body = "\n".join(body_lines).strip()
    return subject, body

def get_leads_needing_fu():
    """Get all leads that need follow-up."""
    crm = get_crm()
    all_leads = crm.get_wl_all()
    today = datetime.now()

    needs_fu1 = []
    needs_fu2 = []
    needs_fu3 = []

    for lead in all_leads:
        status = str(lead.get("Status", "")).strip()
        if status in ("Partner", "Lost", "Bounced", "Unqualified"):
            continue

        company = str(lead.get("Company Name", "")).strip()
        email = str(lead.get("Email", "")).strip()
        contact = str(lead.get("Owner Name", "")).strip()
        sent_date = str(lead.get("Sent date", "")).strip()
        fu1 = str(lead.get("FU 1", "")).strip()
        fu2 = str(lead.get("FU 2", "")).strip()
        fu3 = str(lead.get("FU 3", "")).strip()

        if not email or not sent_date:
            continue

        lead_info = {
            "company": company,
            "email": email,
            "contact": contact,
            "sent_date": sent_date,
            "fu1": fu1,
            "fu2": fu2,
            "fu3": fu3,
        }

        if not fu1:
            needs_fu1.append(lead_info)
        elif not fu2:
            try:
                d = datetime.strptime(fu1, "%d/%m/%Y")
                if (today - d).days >= 3:
                    needs_fu2.append(lead_info)
            except ValueError:
                needs_fu2.append(lead_info)
        elif not fu3:
            try:
                d = datetime.strptime(fu2, "%d/%m/%Y")
                if (today - d).days >= 4:
                    needs_fu3.append(lead_info)
            except ValueError:
                needs_fu3.append(lead_info)

    return needs_fu1, needs_fu2, needs_fu3

def send_fu(lead_info, fu_num):
    """Send a follow-up email. Returns (success, bounced)."""
    first_name = get_first_name(lead_info["contact"], lead_info["email"])
    company = lead_info["company"]

    templates = {1: FU1_TEMPLATE, 2: FU2_TEMPLATE, 3: FU3_TEMPLATE}
    template = templates.get(fu_num, FU1_TEMPLATE)

    subject, body = extract_subject_body(template, first_name, company)
    success, error = send_email(lead_info["email"], subject, body)
    bounced = "bounce" in error.lower() or "refused" in error.lower()
    return success, bounced

def update_crm_fu(crm, company, fu_num, today_str):
    """Update the FU date in CRM sheet."""
    ws = crm.ws_wl
    fu_col = {1: 16, 2: 17, 3: 18}  # Sheet columns

    try:
        cell = ws.find(company, in_column=1)
        if cell:
            row = cell.row
            ws.update_cell(row, fu_col[fu_num], today_str)
            print(f"  Updated {company} FU{fu_num} = {today_str}")
            return True
    except Exception as e:
        print(f"  Error updating {company}: {e}")
    return False

def mark_bounced(crm, company):
    """Mark a lead as bounced in CRM."""
    try:
        ws = crm.ws_wl
        cell = ws.find(company, in_column=1)
        if cell:
            ws.update_cell(cell.row, 19, "Bounced")  # Status col 19
            print(f"  Marked {company} as Bounced")
    except Exception as e:
        print(f"  Error marking bounce: {e}")

def main():
    print("=" * 60)
    print("CRM FOLLOW-UP TRACKER")
    print("=" * 60)

    crm = get_crm()
    needs_fu1, needs_fu2, needs_fu3 = get_leads_needing_fu()

    print(f"\nLeads needing FU1: {len(needs_fu1)}")
    print(f"Leads needing FU2: {len(needs_fu2)}")
    print(f"Leads needing FU3: {len(needs_fu3)}")

    today_str = datetime.now().strftime("%d/%m/%Y")
    results = {"fu1": 0, "fu2": 0, "fu3": 0, "bounced": 0, "failed": 0}

    # Send FU1
    for lead in needs_fu1:
        print(f"\n[FU1] {lead['company']} | {lead['email']}")
        success, bounced = send_fu(lead, 1)
        if success:
            update_crm_fu(crm, lead["company"], 1, today_str)
            results["fu1"] += 1
        elif bounced:
            mark_bounced(crm, lead["company"])
            results["bounced"] += 1
        else:
            results["failed"] += 1
        time.sleep(1.5)  # Rate limit

    # Send FU2
    for lead in needs_fu2:
        print(f"\n[FU2] {lead['company']} | {lead['email']}")
        success, bounced = send_fu(lead, 2)
        if success:
            update_crm_fu(crm, lead["company"], 2, today_str)
            results["fu2"] += 1
        elif bounced:
            mark_bounced(crm, lead["company"])
            results["bounced"] += 1
        else:
            results["failed"] += 1
        time.sleep(1.5)

    # Send FU3
    for lead in needs_fu3:
        print(f"\n[FU3] {lead['company']} | {lead['email']}")
        success, bounced = send_fu(lead, 3)
        if success:
            update_crm_fu(crm, lead["company"], 3, today_str)
            results["fu3"] += 1
        elif bounced:
            mark_bounced(crm, lead["company"])
            results["bounced"] += 1
        else:
            results["failed"] += 1
        time.sleep(1.5)

    # Summary
    print(f"\n{'=' * 60}")
    print("FOLLOW-UP RESULTS")
    print(f"{'=' * 60}")
    print(f"FU1 sent: {results['fu1']}")
    print(f"FU2 sent: {results['fu2']}")
    print(f"FU3 sent: {results['fu3']}")
    print(f"Bounced: {results['bounced']}")
    print(f"Failed: {results['failed']}")
    total_sent = results['fu1'] + results['fu2'] + results['fu3']
    print(f"TOTAL SENT: {total_sent}")

    return results

if __name__ == "__main__":
    main()
