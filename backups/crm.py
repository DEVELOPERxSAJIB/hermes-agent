"""
NanoSoft CRM — Google Sheets wrapper
Extended columns for Chairman's vision.
"""
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timezone, timedelta
import json
import time
import os

SERVICE_ACCOUNT_FILE = "/home/ubuntu/nanosoft/gcp_service_account.json"
SHEET_ID = "1S9jTTe1rKfe0GqqdVgXXgVkdtrRgHtwxu44pERYMOTo"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Extended columns — new fields added AFTER Status
LEAD_COLUMNS = [
    "Company Name",       # 1
    "Website",            # 2
    "Owner Name",         # 3
    "Owner Email",        # 4  ← PRIMARY: must have for outreach
    "Linkedin",           # 5
    "Pain Point",         # 6
    "Email sent date",    # 7
    "Follow up 01",       # 8
    "Follow up 02",       # 9
    "Status",             # 10
    # --- New columns after Status ---
    "Judge Score",        # 11  1-10
    "Severity",           # 12  low/medium/high/critical
    "Location",           # 13  City, State
    "Source",             # 14  where we found them
    "Revenue Impact",     # 15  estimated
    "Automation Potential", # 16 high/medium/low
    "Outreach Angle",     # 17  one-liner
    "Suggested Solution", # 18
    "Contact Form URL",   # 19  if no email
    "Booking URL",        # 20  if available
]

# Status values
STATUS_NEW = "New"
STATUS_QUALIFIED = "Qualified"
STATUS_DRAFTED = "Drafted"
STATUS_EMAIL_SENT = "Email Sent"
STATUS_FOLLOWUP_1 = "Follow Up 1"
STATUS_FOLLOWUP_2 = "Follow Up 2"
STATUS_REPLIED = "Replied"
STATUS_LANDED = "Landed"
STATUS_LOST = "Lost"
STATUS_UNQUALIFIED = "Unqualified"


class NanoSoftCRM:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, 'creds'):
            return
        self.creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        self.gc = gspread.authorize(self.creds)
        self.sh = self.gc.open_by_key(SHEET_ID)
        self.ws_leads = self.sh.worksheet("Lead")
        self._ensure_headers()
        self.ws_analytics = self._get_or_create_analytics()

    def _ensure_headers(self):
        existing = self.ws_leads.row_values(1)
        if len(existing) < len(LEAD_COLUMNS):
            # Extend headers
            self.ws_leads.update('A1:T1', [LEAD_COLUMNS])
        elif existing[:10] != LEAD_COLUMNS[:10]:
            self.ws_leads.update('A1:T1', [LEAD_COLUMNS])

    def _get_or_create_analytics(self):
        try:
            return self.sh.worksheet("Analytics")
        except gspread.exceptions.WorksheetNotFound:
            ws = self.sh.add_worksheet(title="Analytics", rows=1000, cols=10)
            ws.update('A1:H1', [["Date","Leads Found","Qualified","Drafted","Sent","Replies","Landed","Notes"]])
            return ws

    def _refresh(self):
        try:
            if self.creds.expired:
                self.creds.refresh()
                self.gc = gspread.authorize(self.creds)
                self.sh = self.gc.open_by_key(SHEET_ID)
                self.ws_leads = self.sh.worksheet("Lead")
        except:
            pass

    def _retry(self, fn, attempts=5):
        import gspread.exceptions as gexc
        for i in range(attempts):
            try:
                return fn()
            except gexc.APIError as e:
                status = getattr(getattr(e, 'response', None), 'status_code', 0)
                if status == 429 or status >= 500:
                    wait = 30 * (i + 1)
                    if i < attempts - 1:
                        print(f"[CRM] Rate limited. Waiting {wait}s...")
                        time.sleep(wait)
                        continue
                raise
            except Exception as e:
                if i == attempts - 1:
                    raise
                if '429' in str(e):
                    wait = 30 * (i + 1)
                    if i < attempts - 1:
                        print(f"[CRM] Quota. Waiting {wait}s...")
                        time.sleep(wait)
                        continue
                time.sleep(2 ** i)

    def get_all_leads(self):
        self._refresh()
        try:
            return self.ws_leads.get_all_records()
        except:
            self._ensure_headers()
            return self.ws_leads.get_all_records(expected_headers=LEAD_COLUMNS)

    def get_leads_by_status(self, status):
        all_leads = self.get_all_leads()
        return [l for l in all_leads if l.get("Status") == status]

    def get_new_leads(self):
        return self.get_leads_by_status(STATUS_NEW)

    def get_qualified_leads(self):
        return self.get_leads_by_status(STATUS_QUALIFIED)

    def get_drafted_leads(self):
        return self.get_leads_by_status(STATUS_DRAFTED)

    def lead_exists(self, company_name="", website="", email=""):
        existing = self.get_all_leads()
        for row in existing:
            if company_name and row.get("Company Name","").lower().strip() == company_name.lower().strip():
                return True
            if website and row.get("Website","").lower().strip() == website.lower().strip():
                return True
            if email and row.get("Owner Email","").lower().strip() == email.lower().strip():
                return True
        return False

    def add_lead(self, lead: dict):
        self._refresh()
        company = lead.get("Company Name", "")
        website = lead.get("Website", "")
        email = lead.get("Owner Email", "")
        if self.lead_exists(company, website, email):
            return False
        row = [lead.get(col, "") for col in LEAD_COLUMNS]
        if not lead.get("Status"):
            row[LEAD_COLUMNS.index("Status")] = STATUS_NEW
        def _append():
            self.ws_leads.append_row(row, value_input_option='USER_ENTERED')
        self._retry(_append)
        return True

    def add_leads_batch(self, leads: list):
        self._refresh()
        added = 0
        skipped = 0
        existing = self.get_all_leads()
        existing_keys = set()
        for l in existing:
            existing_keys.add((l.get("Company Name","").lower().strip(), l.get("Website","").lower().strip(), l.get("Owner Email","").lower().strip()))
        rows_to_append = []
        for lead in leads:
            company = lead.get("Company Name", "")
            website = lead.get("Website", "")
            email = lead.get("Owner Email", "")
            key = (company.lower().strip(), website.lower().strip(), email.lower().strip())
            # Skip if any key field matches
            if any((company.lower().strip(), "", "") in existing_keys for k in [key]):
                skipped += 1
                continue
            if any(e[2] == email.lower().strip() and e[2] != "" for e in existing_keys):
                skipped += 1
                continue
            row = [lead.get(col, "") for col in LEAD_COLUMNS]
            if not lead.get("Status"):
                row[LEAD_COLUMNS.index("Status")] = STATUS_NEW
            rows_to_append.append(row)
        if rows_to_append:
            def _batch():
                self.ws_leads.append_rows(rows_to_append, value_input_option='USER_ENTERED')
            self._retry(_batch)
            added = len(rows_to_append)
        return added, skipped

    def update_lead(self, company_name: str, updates: dict):
        self._refresh()
        all_leads = self.ws_leads.get_all_values()
        for i, row in enumerate(all_leads[1:], start=2):
            if row[0].lower().strip() == company_name.lower().strip():
                for col_name, value in updates.items():
                    if col_name in LEAD_COLUMNS:
                        col_idx = LEAD_COLUMNS.index(col_name) + 1
                        def _update():
                            self.ws_leads.update_cell(i, col_idx, value)
                        self._retry(_update)
                return True
        return False

    def update_status(self, company_name: str, new_status: str):
        return self.update_lead(company_name, {"Status": new_status})

    def count_leads(self):
        all_leads = self.get_all_leads()
        return len([l for l in all_leads if l.get("Company Name")])

    def log_analytics(self, data: dict):
        self._refresh()
        today = datetime.now(timezone(timedelta(hours=6))).strftime("%Y-%m-%d")
        row = [
            data.get("Date", today),
            data.get("Leads Found", 0),
            data.get("Qualified", 0),
            data.get("Drafted", 0),
            data.get("Sent", 0),
            data.get("Replies", 0),
            data.get("Landed", 0),
            data.get("Notes", ""),
        ]
        def _append():
            self.ws_analytics.append_row(row, value_input_option='USER_ENTERED')
        self._retry(_append)


_crm = None
def get_crm():
    global _crm
    if _crm is None:
        _crm = NanoSoftCRM()
    return _crm
