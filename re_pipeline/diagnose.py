"""Pipeline status checker — diagnose what needs attention"""
import json
from datetime import datetime, timedelta
from sheets import get_leads, update_status, update_touch_date, update_lead
from config import COL

def diagnose():
    """Check pipeline health and identify issues."""
    leads = get_leads()
    today = datetime.now()
    today_str = today.strftime("%d/%m/%Y")

    issues = []
    follow_ups_needed = []

    for lead in leads:
        lid = lead.get("Lead_ID", "")
        status = lead.get("Status", "")
        angle = lead.get("Angle", "A")
        email = lead.get("Email", "")
        t1 = lead.get("Touch_1_Date", "")
        t2 = lead.get("Touch_2_Date", "")
        t3 = lead.get("Touch_3_Date", "")
        t4 = lead.get("Touch_4_Date", "")
        notes = lead.get("Notes", "")

        # Check for bounced emails (marked in notes)
        if "BOUNCED" in notes.upper():
            issues.append(f"  BOUNCED: {lid} {lead.get('Brokerage_Name','')} — {email}")
            continue

        # Skip completed
        if status in ("Closed", "Meeting-Set", "Proposal-Sent"):
            continue

        # Check if follow-ups are overdue
        if t1 and not t2:
            try:
                d1 = datetime.strptime(t1, "%d/%m/%Y")
                days_since = (today - d1).days
                if days_since >= 3:
                    follow_ups_needed.append({
                        "lead": lead,
                        "touch": 2,
                        "days_overdue": days_since - 3,
                        "reason": f"Touch 2 due (T1 was {t1}, {days_since} days ago)"
                    })
                else:
                    pass  # Not yet due
            except ValueError:
                issues.append(f"  BAD DATE: {lid} Touch_1_Date='{t1}'")

        elif t2 and not t3:
            try:
                d2 = datetime.strptime(t2, "%d/%m/%Y")
                days_since = (today - d2).days
                if days_since >= 4:
                    follow_ups_needed.append({
                        "lead": lead,
                        "touch": 3,
                        "days_overdue": days_since - 4,
                        "reason": f"Touch 3 due (T2 was {t2}, {days_since} days ago)"
                    })
            except ValueError:
                issues.append(f"  BAD DATE: {lid} Touch_2_Date='{t2}'")

        elif t3 and not t4:
            try:
                d3 = datetime.strptime(t3, "%d/%m/%Y")
                days_since = (today - d3).days
                if days_since >= 7:
                    follow_ups_needed.append({
                        "lead": lead,
                        "touch": 4,
                        "days_overdue": days_since - 7,
                        "reason": f"Touch 4 due (T3 was {t3}, {days_since} days ago)"
                    })
            except ValueError:
                issues.append(f"  BAD DATE: {lid} Touch_3_Date='{t3}'")

        elif status == "Contacted" and not t1:
            issues.append(f"  NO TOUCH 1 DATE: {lid} status=Contacted but Touch_1_Date empty")

        elif status == "New":
            issues.append(f"  NEVER CONTACTED: {lid} status=New, no outreach sent")

    # Print report
    print("=" * 60)
    print("PIPELINE DIAGNOSIS")
    print("=" * 60)
    print(f"\nTotal leads: {len(leads)}")
    print(f"Follow-ups needed NOW: {len(follow_ups_needed)}")
    print(f"Issues found: {len(issues)}")

    if follow_ups_needed:
        print("\n--- FOLLOW-UPS DUE ---")
        for item in follow_ups_needed:
            lead = item["lead"]
            print(f"  {lead['Lead_ID']} | {lead['Brokerage_Name']} | Touch {item['touch']} | {item['reason']}")

    if issues:
        print("\n--- ISSUES ---")
        for i in issues:
            print(i)

    return follow_ups_needed, issues

if __name__ == "__main__":
    follow_ups, issues = diagnose()
