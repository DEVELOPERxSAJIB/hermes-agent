"""Real Estate Outreach Pipeline — Configuration"""
import os

# Google Sheets
SHEET_ID = "1rQAyfC037JoV2phnLq4g9JsDvvrEb6M69A3roeYJHkk"
SHEET_NAME = "Pipeline"
SHEET_RANGE = "Pipeline!A:T"

# OAuth
TOKEN_PATH = os.path.expanduser("~/.hermes/google_token.json")

# Target cities
US_CITIES = [
    "Miami", "Houston", "Dallas", "Atlanta", "Phoenix",
    "Las Vegas", "Orlando", "Charlotte", "Tampa", "Denver"
]
GCC_CITIES = [
    "Dubai", "Abu Dhabi", "Riyadh", "Doha", "Kuwait City", "Muscat"
]

# Daily limits
MAX_EMAILS_PER_DAY = 40
MAX_LINKEDIN_DMS_PER_DAY = 20
MAX_NEW_LEADS_PER_DAY = 20

# Column mapping (0-indexed)
COL = {
    "Lead_ID": 0, "Brokerage_Name": 1, "Contact_Name": 2, "Title": 3,
    "City": 4, "State_Country": 5, "Market": 6, "Website": 7, "Email": 8,
    "LinkedIn_URL": 9, "Instagram_URL": 10, "Lead_Source": 11,
    "Social_Audit": 12, "Angle": 13, "Status": 14, "Touch_1_Date": 15,
    "Touch_2_Date": 16, "Touch_3_Date": 17, "Touch_4_Date": 18, "Notes": 19
}

# Status values
STATUSES = ["New", "Contacted", "Followed-Up", "Replied", "Meeting-Set", "Proposal-Sent", "Closed", "Dead"]

# Franchise names to exclude
FRANCHISES = [
    "RE/MAX", "Keller Williams", "Century 21", "Coldwell Banker",
    "Sotheby's", "Douglas Elliman", "Compass", "eXp Realty",
    "Better Homes and Gardens", "ERA Real Estate", "Exit Realty",
    "Realty One Group", "Keller Williams Realty", "RE/MAX",
    "Keller Williams", "Century 21 Real Estate"
]
