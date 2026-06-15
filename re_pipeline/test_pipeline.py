"""Test the RE pipeline with 5 sample leads"""
import sys
sys.path.insert(0, '/home/ubuntu/nanosoft/re_pipeline')

from sheets import get_leads, get_next_lead_id, append_lead, update_lead, update_status
from audit import run_audit
from templates import get_template

# 5 sample leads for testing
test_leads = [
    {
        "Brokerage_Name": "Sunshine Realty Group",
        "Contact_Name": "Michael Torres",
        "Title": "Broker-Owner",
        "City": "Miami",
        "State_Country": "Florida",
        "Market": "US",
        "Website": "https://sunshinerealtygroup.com",
        "Email": "michael@sunshinerealtygroup.com",
        "LinkedIn_URL": "https://linkedin.com/company/sunshine-realty-group",
        "Instagram_URL": "https://instagram.com/sunshinerealtygroup",
        "Lead_Source": "Google Maps"
    },
    {
        "Brokerage_Name": "Desert Edge Properties",
        "Contact_Name": "Sarah Johnson",
        "Title": "Broker-Owner",
        "City": "Phoenix",
        "State_Country": "Arizona",
        "Market": "US",
        "Website": "https://desertedgeproperties.com",
        "Email": "sarah@desertedgeproperties.com",
        "LinkedIn_URL": "",
        "Instagram_URL": "",
        "Lead_Source": "Zillow"
    },
    {
        "Brokerage_Name": "Gulf Coast Real Estate",
        "Contact_Name": "David Chen",
        "Title": "Office Manager",
        "City": "Houston",
        "State_Country": "Texas",
        "Market": "US",
        "Website": "https://gulfcoastre.com",
        "Email": "david@gulfcoastre.com",
        "LinkedIn_URL": "https://linkedin.com/company/gulf-coast-real-estate",
        "Instagram_URL": "https://instagram.com/gulfcoastre",
        "Lead_Source": "LinkedIn"
    },
    {
        "Brokerage_Name": "Al Majid Properties",
        "Contact_Name": "Ahmed Al Rashid",
        "Title": "Broker-Owner",
        "City": "Dubai",
        "State_Country": "UAE",
        "Market": "GCC",
        "Website": "https://almajidproperties.ae",
        "Email": "ahmed@almajidproperties.ae",
        "LinkedIn_URL": "https://linkedin.com/company/al-majid-properties",
        "Instagram_URL": "https://instagram.com/almajidproperties",
        "Lead_Source": "Manual"
    },
    {
        "Brokerage_Name": "Riyadh Home Brokers",
        "Contact_Name": "Fatima Hassan",
        "Title": "Broker-Owner",
        "City": "Riyadh",
        "State_Country": "Saudi Arabia",
        "Market": "GCC",
        "Website": "https://riyadhhomebrokers.sa",
        "Email": "fatima@riyadhhomebrokers.sa",
        "LinkedIn_URL": "",
        "Instagram_URL": "https://instagram.com/riyadhhomebrokers",
        "Lead_Source": "Google Maps"
    }
]

print("=" * 60)
print("RE PIPELINE TEST — 5 Sample Leads")
print("=" * 60)

# Step 1: Run audit and add leads
for i, lead in enumerate(test_leads, 1):
    print(f"\n--- Lead {i}: {lead['Brokerage_Name']} ---")

    # Run social audit
    ig_username = lead.get("Instagram_URL", "").rstrip("/").split("/")[-1] if lead.get("Instagram_URL") else None
    audit = run_audit(lead["Brokerage_Name"], ig_username, lead.get("LinkedIn_URL"))

    lead["Social_Audit"] = audit["Social_Audit"]
    lead["Angle"] = audit["Angle"]
    lead["Status"] = "New"

    print(f"  City: {lead['City']}, Market: {lead['Market']}")
    print(f"  Social Audit: {audit['Social_Audit']}")
    print(f"  Angle: {audit['Angle']}")

    # Assign Lead ID and add to sheet
    lead["Lead_ID"] = get_next_lead_id()
    append_lead(lead)
    print(f"  Added to sheet with ID: {lead['Lead_ID']}")

    # Generate Touch 1 template
    angle = lead["Angle"]
    template = get_template(angle, 1, lead["Brokerage_Name"], lead["Contact_Name"], lead["City"])
    subject = ""
    body = template
    if template.startswith("Subject:"):
        lines = template.split("\n")
        subject = lines[0].replace("Subject: ", "").strip()
        body = "\n".join(lines[2:])

    print(f"  Touch 1 Subject: {subject}")
    print(f"  Touch 1 Body (first 150 chars): {body[:150]}...")

    # Mark as sent
    update_status(lead["Lead_ID"], "Contacted")
    from sheets import update_touch_date
    update_touch_date(lead["Lead_ID"], 1)
    print(f"  Status: Contacted, Touch 1 logged")

# Step 2: Verify all leads in sheet
print("\n" + "=" * 60)
print("VERIFICATION — All leads in sheet:")
print("=" * 60)
all_leads = get_leads()
for lead in all_leads:
    print(f"  {lead['Lead_ID']} | {lead['Brokerage_Name']} | {lead['City']} | Angle {lead['Angle']} | {lead['Status']}")

print(f"\nTotal leads in pipeline: {len(all_leads)}")
print("TEST COMPLETE")
