"""Daily execution routine — morning + evening"""
import json
import smtplib
import re
from email.mime.text import MIMEText
from datetime import datetime, timedelta

from sheets import get_leads, get_next_lead_id, append_lead, update_lead, update_status, update_touch_date
from audit import run_audit
from templates import get_template
from osm_sourcing import scout_single_city, enrich_lead
from config import MAX_EMAILS_PER_DAY, MAX_LINKEDIN_DMS_PER_DAY, MAX_NEW_LEADS_PER_DAY, US_CITIES, GCC_CITIES

# Email sending config — set these in .env or here
SMTP_CONFIG = None  # Will be loaded from .env if available

def load_smtp_config():
    """Try to load SMTP config from .env"""
    global SMTP_CONFIG
    try:
        env_path = "/home/ubuntu/.hermes/.env"
        config = {}
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("EMAIL_") and "=" in line and not line.startswith("#"):
                    key, val = line.split("=", 1)
                    config[key.strip()] = val.strip()
        if config.get("EMAIL_SMTP_HOST"):
            SMTP_CONFIG = {
                "host": config["EMAIL_SMTP_HOST"],
                "port": int(config.get("EMAIL_SMTP_PORT", "587")),
                "user": config.get("EMAIL_ADDRESS", ""),
                "password": config.get("EMAIL_PASSWORD", ""),
            }
            print(f"SMTP config loaded: {SMTP_CONFIG['host']}")
    except Exception as e:
        print(f"Could not load SMTP config: {e}")

def send_email_smtp(to_email, subject, body, from_email=None):
    """Send email via SMTP. Returns True if sent."""
    global SMTP_CONFIG
    if not SMTP_CONFIG:
        load_smtp_config()

    if not SMTP_CONFIG:
        print(f"[DRY RUN] Would send to {to_email}: {subject}")
        print(f"  Body preview: {body[:200]}...")
        return True

    try:
        if not from_email:
            from_email = SMTP_CONFIG.get("user", "sajib@nanosoft.agency")
            if not from_email:
                from_email = "sajib@nanosoft.agency"

        # Clean subject (no newlines)
        subject = subject.replace("\n", " ").replace("\r", "").strip()

        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = f"SaJib Shikder <{from_email}>"
        msg["To"] = to_email

        with smtplib.SMTP(SMTP_CONFIG["host"], SMTP_CONFIG["port"]) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_CONFIG["user"], SMTP_CONFIG["password"])
            server.send_message(msg)

        print(f"[SENT] {subject} -> {to_email}")
        return True
    except Exception as e:
        print(f"[EMAIL FAILED] {to_email}: {e}")
        return False

def send_linkedin_dm(lead, message):
    """LinkedIn DM — queued for manual sending (no browser available)."""
    contact = lead.get("Contact_Name", "")
    brokerage = lead.get("Brokerage_Name", "")
    print(f"[LINKEDIN QUEUE] To: {contact} at {brokerage}")
    print(f"  Message: {message[:150]}...")
    return True

def get_leads_needing_touch():
    """Find leads that need Touch 2, 3, or 4 based on dates."""
    leads = get_leads()
    today = datetime.now()
    pending = []

    for lead in leads:
        status = lead.get("Status", "")
        if status in ("Dead", "Closed", "Meeting-Set", "Proposal-Sent"):
            continue
        if not lead.get("Email"):
            continue  # Can't follow up without email

        touch1 = lead.get("Touch_1_Date", "")
        touch2 = lead.get("Touch_2_Date", "")
        touch3 = lead.get("Touch_3_Date", "")
        touch4 = lead.get("Touch_4_Date", "")

        # Touch 2: 3 days after Touch 1
        if touch1 and not touch2:
            try:
                t1 = datetime.strptime(touch1, "%d/%m/%Y")
                if (today - t1).days >= 3:
                    pending.append({**lead, "next_touch": 2})
            except ValueError:
                pass
        # Touch 3: 4 days after Touch 2
        elif touch2 and not touch3:
            try:
                t2 = datetime.strptime(touch2, "%d/%m/%Y")
                if (today - t2).days >= 4:
                    pending.append({**lead, "next_touch": 3})
            except ValueError:
                pass
        # Touch 4: 7 days after Touch 3
        elif touch3 and not touch4:
            try:
                t3 = datetime.strptime(touch3, "%d/%m/%Y")
                if (today - t3).days >= 7:
                    pending.append({**lead, "next_touch": 4})
            except ValueError:
                pass

    return pending

def morning_routine(cities=None, max_new=MAX_NEW_LEADS_PER_DAY):
    """
    Morning routine (9:00 AM Dhaka):
    1. Send pending follow-ups (Touch 2, 3, 4)
    2. Source new leads via OSM
    3. Run social audit + enrich
    4. Send Touch 1 to new leads
    """
    results = {
        "follow_ups_sent": 0,
        "new_leads_added": 0,
        "touch1_sent": 0,
        "errors": []
    }

    # Step 1: Send pending follow-ups
    pending = get_leads_needing_touch()
    emails_sent_today = 0

    for lead in pending:
        if emails_sent_today >= MAX_EMAILS_PER_DAY:
            break

        touch_num = lead["next_touch"]
        angle = lead.get("Angle", "A")
        brokerage = lead.get("Brokerage_Name", "")
        contact = lead.get("Contact_Name", "")
        city = lead.get("City", "")
        email = lead.get("Email", "")

        tmpl = get_template(angle, touch_num, brokerage, contact, city)

        if touch_num == 2:
            send_linkedin_dm(lead, tmpl["body"])
        else:
            if email and emails_sent_today < MAX_EMAILS_PER_DAY:
                if send_email_smtp(email, tmpl["subject"], tmpl["body"]):
                    emails_sent_today += 1

        update_touch_date(lead["Lead_ID"], touch_num)
        update_status(lead["Lead_ID"], "Followed-Up")
        results["follow_ups_sent"] += 1

    # Step 2: Source new leads via OSM
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
                        continue  # Skip leads without email

                    # Run social audit
                    ig_url = lead_data.get("Instagram_URL", "")
                    ig_user = ig_url.rstrip("/").split("/")[-1] if ig_url else None
                    audit = run_audit(lead_data.get("Brokerage_Name", ""), ig_user)
                    lead_data["Social_Audit"] = audit["Social_Audit"]
                    lead_data["Angle"] = audit["Angle"]
                    lead_data["Status"] = "New"

                    # Assign Lead ID and add
                    lead_data["Lead_ID"] = get_next_lead_id()
                    append_lead(lead_data)
                    results["new_leads_added"] += 1

                    # Send Touch 1
                    if emails_sent_today < MAX_EMAILS_PER_DAY:
                        angle = lead_data["Angle"]
                        email = lead_data.get("Email", "")
                        if email:
                            tmpl = get_template(angle, 1,
                                lead_data.get("Brokerage_Name", ""),
                                lead_data.get("Contact_Name", ""),
                                lead_data.get("City", ""))
                            if send_email_smtp(email, tmpl["subject"], tmpl["body"]):
                                update_status(lead_data["Lead_ID"], "Contacted")
                                update_touch_date(lead_data["Lead_ID"], 1)
                                results["touch1_sent"] += 1
                                emails_sent_today += 1
            except Exception as e:
                results["errors"].append(f"{city}: {e}")

    return results

def evening_routine():
    """Evening routine: generate daily summary."""
    leads = get_leads()
    today = datetime.now()

    total = len(leads)
    active = sum(1 for l in leads if l.get("Status") not in ("Dead", "Closed"))
    dead = sum(1 for l in leads if l.get("Status") == "Dead")
    closed = sum(1 for l in leads if l.get("Status") == "Closed")
    replied = sum(1 for l in leads if l.get("Status") == "Replied")
    meetings = sum(1 for l in leads if l.get("Status") == "Meeting-Set")

    today_str = today.strftime("%d/%m/%Y")
    today_touch1 = sum(1 for l in leads if l.get("Touch_1_Date") == today_str)
    today_touch2 = sum(1 for l in leads if l.get("Touch_2_Date") == today_str)
    today_touch3 = sum(1 for l in leads if l.get("Touch_3_Date") == today_str)
    today_touch4 = sum(1 for l in leads if l.get("Touch_4_Date") == today_str)

    # Count new leads today (approximated by Touch_1_Date = today)
    new_today = today_touch1

    summary = (
        f"Daily Report - {today.strftime('%d %b %Y')}\n\n"
        f"New leads added: {new_today}\n"
        f"Touch 1 sent: {today_touch1}\n"
        f"Touch 2 sent: {today_touch2}\n"
        f"Touch 3 sent: {today_touch3}\n"
        f"Touch 4 sent: {today_touch4}\n"
        f"Replies received: {replied}\n"
        f"Meetings set: {meetings}\n"
        f"Dead leads: {dead}\n\n"
        f"Pipeline total: {total}\n"
        f"Active: {active} | Dead: {dead} | Closed: {closed}"
    )
    return summary

def weekly_report():
    """Generate weekly report (Sunday)."""
    leads = get_leads()
    total = len(leads)
    active = sum(1 for l in leads if l.get("Status") not in ("Dead", "Closed"))
    dead = sum(1 for l in leads if l.get("Status") == "Dead")
    closed = sum(1 for l in leads if l.get("Status") == "Closed")
    meetings = sum(1 for l in leads if l.get("Status") == "Meeting-Set")
    contacted = sum(1 for l in leads if l.get("Touch_1_Date"))
    replied = sum(1 for l in leads if l.get("Status") == "Replied")

    reply_rate = f"{(replied / contacted * 100):.1f}%" if contacted > 0 else "0%"

    angle_a = sum(1 for l in leads if l.get("Angle") == "A" and l.get("Status") not in ("Dead", "Closed"))
    angle_b = sum(1 for l in leads if l.get("Angle") == "B" and l.get("Status") not in ("Dead", "Closed"))
    top_angle = "A" if angle_a >= angle_b else "B"

    report = (
        f"Weekly Report - Week of {datetime.now().strftime('%d %b %Y')}\n\n"
        f"Total leads in pipeline: {total}\n"
        f"Total contacted this week: {contacted}\n"
        f"Reply rate: {reply_rate}\n"
        f"Meetings set this week: {meetings}\n"
        f"Deals closed: {closed}\n"
        f"Dead this week: {dead}\n\n"
        f"Top performing angle: {top_angle}\n"
        f"Notes: Angle A leads: {angle_a}, Angle B leads: {angle_b}"
    )
    return report
