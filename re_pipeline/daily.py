"""Daily execution routine — RE Pipeline + CRM follow-ups"""
import json
import sys
import os
import time
from datetime import datetime, timedelta

sys.path.insert(0, '/home/ubuntu/nanosoft')
sys.path.insert(0, '/home/ubuntu/nanosoft/re_pipeline')
os.chdir('/home/ubuntu/nanosoft')

from sheets import get_leads, get_next_lead_id, append_lead, update_lead, update_status, update_touch_date
from audit import run_audit
from templates import get_template
from osm_sourcing import scout_single_city
from smtp_sender import send_email
from config import MAX_EMAILS_PER_DAY, MAX_LINKEDIN_DMS_PER_DAY, MAX_NEW_LEADS_PER_DAY, US_CITIES, GCC_CITIES

def re_morning_routine(cities=None, max_new=MAX_NEW_LEADS_PER_DAY):
    """
    RE Pipeline morning routine:
    1. Send pending follow-ups (Touch 2, 3, 4)
    2. Source new leads via OSM
    3. Run social audit + enrich
    4. Send Touch 1 to new leads
    """
    results = {
        "follow_ups_sent": 0,
        "new_leads_added": 0,
        "touch1_sent": 0,
        "bounced": 0,
        "errors": []
    }

    # Step 1: Send pending follow-ups (T2/T3/T4) + T1 to unsent "New" leads
    leads = get_leads()
    today = datetime.now()
    today_str = today.strftime("%d/%m/%Y")
    emails_sent = 0

    for lead in leads:
        if emails_sent >= MAX_EMAILS_PER_DAY:
            break

        status = lead.get("Status", "")
        if status in ("Dead", "Closed", "Meeting-Set", "Proposal-Sent", "Bounced"):
            continue

        touch1 = lead.get("Touch_1_Date", "")
        touch2 = lead.get("Touch_2_Date", "")
        touch3 = lead.get("Touch_3_Date", "")
        touch4 = lead.get("Touch_4_Date", "")
        email = lead.get("Email", "")

        next_touch = None

        # FIX: If status is "New" and no Touch_1_Date, send T1 immediately
        if status == "New" and not touch1 and email:
            next_touch = 1
        # Otherwise, follow up on existing sequence
        elif touch1 and not touch2:
            try:
                d = datetime.strptime(touch1, "%d/%m/%Y")
                if (today - d).days >= 3:
                    next_touch = 2
            except ValueError:
                next_touch = 2
        elif touch2 and not touch3:
            try:
                d = datetime.strptime(touch2, "%d/%m/%Y")
                if (today - d).days >= 4:
                    next_touch = 3
            except ValueError:
                next_touch = 3
        elif touch3 and not touch4:
            try:
                d = datetime.strptime(touch3, "%d/%m/%Y")
                if (today - d).days >= 7:
                    next_touch = 4
            except ValueError:
                next_touch = 4

        if not next_touch or not email:
            continue

        angle = lead.get("Angle", "A")
        tmpl = get_template(angle, next_touch, lead.get("Brokerage_Name", ""), lead.get("Contact_Name", ""), lead.get("City", ""))

        success, error = send_email(email, tmpl["subject"], tmpl["body"])
        if success:
            update_touch_date(lead["Lead_ID"], next_touch)
            if next_touch == 1:
                update_status(lead["Lead_ID"], "Contacted")
                results["touch1_sent"] += 1
            else:
                update_status(lead["Lead_ID"], "Followed-Up")
                results["follow_ups_sent"] += 1
            emails_sent += 1
        elif "bounce" in error.lower() or "refused" in error.lower():
            update_status(lead["Lead_ID"], "Bounced")
            results["bounced"] += 1
        else:
            results["errors"].append(f"{lead['Lead_ID']}: {error}")

        time.sleep(1.5)

    # Step 2: Source new leads
    if cities:
        for city in cities:
            if results["new_leads_added"] >= max_new:
                break
            try:
                new_leads = scout_single_city(city, max_results=3)
                for lead_data in new_leads:
                    if results["new_leads_added"] >= max_new:
                        break
                    if not lead_data.get("Email"):
                        continue

                    ig_url = lead_data.get("Instagram_URL", "")
                    ig_user = ig_url.rstrip("/").split("/")[-1] if ig_url else None
                    audit = run_audit(lead_data.get("Brokerage_Name", ""), ig_user)
                    lead_data["Social_Audit"] = audit["Social_Audit"]
                    lead_data["Angle"] = audit["Angle"]
                    lead_data["Status"] = "New"
                    lead_data["Lead_ID"] = get_next_lead_id()
                    append_lead(lead_data)
                    results["new_leads_added"] += 1

                    if emails_sent < MAX_EMAILS_PER_DAY:
                        angle = lead_data["Angle"]
                        email = lead_data.get("Email", "")
                        if email:
                            tmpl = get_template(angle, 1, lead_data.get("Brokerage_Name", ""), lead_data.get("Contact_Name", ""), lead_data.get("City", ""))
                            success, error = send_email(email, tmpl["subject"], tmpl["body"])
                            if success:
                                update_status(lead_data["Lead_ID"], "Contacted")
                                update_touch_date(lead_data["Lead_ID"], 1)
                                results["touch1_sent"] += 1
                                emails_sent += 1
                            elif "bounce" in error.lower():
                                update_status(lead_data["Lead_ID"], "Bounced")
                                results["bounced"] += 1
                            time.sleep(1.5)
            except Exception as e:
                results["errors"].append(f"{city}: {e}")

    return results

def re_evening_routine():
    """Generate daily summary for RE pipeline."""
    leads = get_leads()
    today = datetime.now()
    today_str = today.strftime("%d/%m/%Y")

    total = len(leads)
    active = sum(1 for l in leads if l.get("Status") not in ("Dead", "Closed", "Bounced"))
    dead = sum(1 for l in leads if l.get("Status") in ("Dead", "Bounced"))
    closed = sum(1 for l in leads if l.get("Status") == "Closed")
    replied = sum(1 for l in leads if l.get("Status") == "Replied")
    meetings = sum(1 for l in leads if l.get("Status") == "Meeting-Set")

    t1 = sum(1 for l in leads if l.get("Touch_1_Date") == today_str)
    t2 = sum(1 for l in leads if l.get("Touch_2_Date") == today_str)
    t3 = sum(1 for l in leads if l.get("Touch_3_Date") == today_str)
    t4 = sum(1 for l in leads if l.get("Touch_4_Date") == today_str)

    return (
        f"Daily Report - {today.strftime('%d %b %Y')}\n\n"
        f"New leads added: {t1}\n"
        f"Touch 1 sent: {t1}\n"
        f"Touch 2 sent: {t2}\n"
        f"Touch 3 sent: {t3}\n"
        f"Touch 4 sent: {t4}\n"
        f"Replies: {replied}\n"
        f"Meetings: {meetings}\n"
        f"Bounced/Dead: {dead}\n\n"
        f"Pipeline total: {total}\n"
        f"Active: {active} | Dead: {dead} | Closed: {closed}"
    )

def re_weekly_report():
    """Generate weekly report."""
    leads = get_leads()
    total = len(leads)
    contacted = sum(1 for l in leads if l.get("Touch_1_Date"))
    replied = sum(1 for l in leads if l.get("Status") == "Replied")
    meetings = sum(1 for l in leads if l.get("Status") == "Meeting-Set")
    closed = sum(1 for l in leads if l.get("Status") == "Closed")
    dead = sum(1 for l in leads if l.get("Status") in ("Dead", "Bounced"))

    reply_rate = f"{(replied / contacted * 100):.1f}%" if contacted > 0 else "0%"
    angle_a = sum(1 for l in leads if l.get("Angle") == "A" and l.get("Status") not in ("Dead", "Closed", "Bounced"))
    angle_b = sum(1 for l in leads if l.get("Angle") == "B" and l.get("Status") not in ("Dead", "Closed", "Bounced"))
    top_angle = "A" if angle_a >= angle_b else "B"

    return (
        f"Weekly Report - Week of {datetime.now().strftime('%d %b %Y')}\n\n"
        f"Total leads: {total}\n"
        f"Contacted: {contacted}\n"
        f"Reply rate: {reply_rate}\n"
        f"Meetings: {meetings}\n"
        f"Closed: {closed}\n"
        f"Dead: {dead}\n\n"
        f"Top angle: {top_angle} (A:{angle_a}, B:{angle_b})"
    )
