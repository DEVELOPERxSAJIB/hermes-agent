"""Google Sheets helper for RE Pipeline"""
import json, os, sys
from datetime import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from config import TOKEN_PATH, SHEET_ID, SHEET_NAME, COL

def _creds():
    with open(TOKEN_PATH) as f:
        d = json.load(f)
    return Credentials(
        token=d['token'], refresh_token=d.get('refresh_token'),
        token_uri=d.get('token_uri', 'https://oauth2.googleapis.com/token'),
        client_id=d['client_id'], client_secret=d['client_secret'],
        scopes=d.get('scopes')
    )

def _service():
    return build('sheets', 'v4', credentials=_creds())

def read_all_rows():
    """Returns all rows as list of lists (including header)."""
    svc = _service()
    result = svc.spreadsheets().values().get(
        spreadsheetId=SHEET_ID, range=SHEET_NAME
    ).execute()
    return result.get('values', [])

def get_leads():
    """Returns list of dicts for all leads (skipping header)."""
    rows = read_all_rows()
    if len(rows) <= 1:
        return []
    headers = rows[0]
    leads = []
    for row in rows[1:]:
        lead = {}
        for key, idx in COL.items():
            lead[key] = row[idx] if idx < len(row) else ""
        leads.append(lead)
    return leads

def get_next_lead_id():
    """Returns next Lead_ID like RE-001."""
    leads = get_leads()
    max_num = 0
    for lead in leads:
        lid = lead.get("Lead_ID", "")
        if lid.startswith("RE-"):
            try:
                n = int(lid.split("-")[1])
                max_num = max(max_num, n)
            except ValueError:
                pass
    return f"RE-{max_num + 1:03d}"

def append_lead(lead_dict):
    """Append a new lead row to the sheet. Skips if email already exists."""
    email = lead_dict.get("Email", "").lower().strip()
    if email:
        # Check for duplicate email
        existing = get_leads()
        for l in existing:
            if l.get("Email", "").lower().strip() == email:
                return False  # skip duplicate
    svc = _service()
    row = [""] * 20
    for key, idx in COL.items():
        if key in lead_dict:
            row[idx] = lead_dict[key]
    svc.spreadsheets().values().append(
        spreadsheetId=SHEET_ID,
        range=SHEET_NAME,
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]}
    ).execute()
    return True

def update_lead(lead_id, updates):
    """Update specific columns for a lead by Lead_ID. updates = {col_name: value}"""
    svc = _service()
    leads = get_leads()
    rows = read_all_rows()
    for i, lead in enumerate(leads):
        if lead.get("Lead_ID") == lead_id:
            row_num = i + 2  # +1 for header, +1 for 0-index
            for col_name, value in updates.items():
                if col_name in COL:
                    col_letter = chr(65 + COL[col_name])
                    cell = f"{col_letter}{row_num}"
                    svc.spreadsheets().values().update(
                        spreadsheetId=SHEET_ID,
                        range=f"{SHEET_NAME}!{cell}",
                        valueInputOption="RAW",
                        body={"values": [[value]]}
                    ).execute()
            return True
    return False

def update_status(lead_id, status):
    update_lead(lead_id, {"Status": status})

def update_touch_date(lead_id, touch_num):
    today = datetime.now().strftime("%d/%m/%Y")
    update_lead(lead_id, {f"Touch_{touch_num}_Date": today})
