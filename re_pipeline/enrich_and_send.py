"""
Enrich leads with emails + social audit, then add to RE sheet
"""
import json, sys, os, time
sys.path.insert(0, '/home/ubuntu/nanosoft/re_pipeline')
os.chdir('/home/ubuntu/nanosoft')

from osm_sourcing import enrich_lead
from audit import run_audit
from sheets import append_lead, get_next_lead_id, update_status, update_touch_date
from smtp_sender import send_email
from templates import get_template

LOG_FILE = "/home/ubuntu/nanosoft/re_pipeline/enrich_send.log"

def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def main():
    # Load raw leads
    with open("/home/ubuntu/nanosoft/re_pipeline/raw_leads.json") as f:
        raw_leads = json.load(f)

    log(f"Raw leads: {len(raw_leads)}")

    # Phase 1: Enrich with emails (fast mode — skip MX verify for speed)
    log("--- ENRICHING WITH EMAILS ---")
    enriched = []
    for i, lead in enumerate(raw_leads):
        try:
            e = enrich_lead(lead, fast=True)
            enriched.append(e)
            has_email = "YES" if e.get("Email") else "NO"
            log(f"  [{i+1}/{len(raw_leads)}] {lead['Brokerage_Name'][:30]} | Email: {has_email}")
        except Exception as ex:
            log(f"  [{i+1}/{len(raw_leads)}] ERROR: {ex}")
            enriched.append(lead)
        time.sleep(0.3)

    with_email = [l for l in enriched if l.get("Email")]
    log(f"Leads with email: {len(with_email)} / {len(enriched)}")

    # Save enriched
    with open("/home/ubuntu/nanosoft/re_pipeline/enriched_leads.json", "w") as f:
        json.dump(enriched, f, indent=2)

    # Phase 2: Social audit + add to sheet
    log("--- SOCIAL AUDIT + ADDING TO SHEET ---")
    added = 0
    audited = 0
    angle_a = 0
    angle_b = 0

    for i, lead in enumerate(with_email):
        try:
            # Audit
            ig_url = lead.get("Instagram_URL", "")
            ig_user = ig_url.rstrip("/").split("/")[-1] if ig_url else None
            audit = run_audit(lead.get("Brokerage_Name", ""), ig_user)
            lead["Social_Audit"] = audit["Social_Audit"]
            lead["Angle"] = audit["Angle"]
            lead["Status"] = "New"

            if audit["Angle"] == "A":
                angle_a += 1
            else:
                angle_b += 1

            # Add to sheet
            lead["Lead_ID"] = get_next_lead_id()
            append_lead(lead)
            added += 1
            audited += 1

            log(f"  [{i+1}/{len(with_email)}] {lead['Brokerage_Name'][:30]} | Angle {lead['Angle']} | {audit['Social_Audit']}")
        except Exception as ex:
            log(f"  [{i+1}/{len(with_email)}] ERROR: {ex}")
        time.sleep(0.5)

    log(f"--- AUDIT COMPLETE ---")
    log(f"Added to sheet: {added}")
    log(f"Angle A: {angle_a} | Angle B: {angle_b}")

    # Phase 3: Send Touch 1 emails
    log("--- SENDING TOUCH 1 EMAILS ---")
    sent = 0
    bounced = 0
    failed = 0

    for i, lead in enumerate(with_email):
        if lead.get("Status") != "New":
            continue
        try:
            angle = lead.get("Angle", "A")
            email = lead.get("Email", "")
            if not email:
                continue

            tmpl = get_template(angle, 1, lead.get("Brokerage_Name", ""), lead.get("Contact_Name", ""), lead.get("City", ""))
            success, error = send_email(email, tmpl["subject"], tmpl["body"])

            if success:
                update_status(lead["Lead_ID"], "Contacted")
                update_touch_date(lead["Lead_ID"], 1)
                sent += 1
                log(f"  [{sent}] SENT -> {email}")
            elif "bounce" in error.lower() or "refused" in error.lower():
                update_status(lead["Lead_ID"], "Bounced")
                bounced += 1
                log(f"  BOUNCE -> {email}")
            else:
                failed += 1
                log(f"  FAIL -> {email}: {error[:60]}")
        except Exception as ex:
            failed += 1
            log(f"  ERROR: {ex}")
        time.sleep(1.5)  # Rate limit

    log(f"{'=' * 60}")
    log("FINAL RESULTS")
    log(f"{'=' * 60}")
    log(f"Raw leads scouted: {len(raw_leads)}")
    log(f"Leads with email: {len(with_email)}")
    log(f"Added to RE sheet: {added}")
    log(f"Touch 1 sent: {sent}")
    log(f"Bounced: {bounced}")
    log(f"Failed: {failed}")
    log(f"Angle A: {angle_a} | Angle B: {angle_b}")

if __name__ == "__main__":
    main()
