"""
NanoSoft CRM — Google Sheets wrapper
Supports both Lead (SMB) and White Label (Agency Partnership) tabs.
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

# ── Lead tab columns (original SMB outreach) ──
LEAD_COLUMNS = [
    "Company Name", "Website", "Owner Name", "Owner Email", "Linkedin",
    "Pain Point", "Email sent date", "Follow up 01", "Follow up 02", "Status",
    "Judge Score", "Severity", "Location", "Source", "Revenue Impact",
    "Automation Potential", "Outreach Angle", "Suggested Solution",
    "Contact Form URL", "Booking URL",
]

# ── White Label tab columns (agency partnership) ──
WL_COLUMNS = [
    "Company Name",       # 1
    "Website",            # 2
    "LinkedIn",           # 3
    "Owner Name",         # 4
    "Owner LinkedIn URL", # 5
    "Country",            # 6
    "Email",              # 7
    "Email Score",        # 8
    "Pain Point",         # 9
    "Services",           # 10
    "Team Size",          # 11
    "White Label Signals",# 12
    "Judge Score",        # 13
    "Sent date",          # 14
    "FU 1",               # 15
    "FU 2",               # 16
    "FU 3",               # 17
    "Status",             # 18
]

WL_STATUSES = ["New", "Contacted", "Replied", "Meeting Booked", "Partner", "Lost"]

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
        # Lead tab (original)
        self.ws_leads = self.sh.worksheet("Lead")
        self._ensure_headers(self.ws_leads, LEAD_COLUMNS)
        # White Label tab (new)
        self.ws_wl = self._get_or_create_wl_tab()
        # Analytics tab
        self.ws_analytics = self._get_or_create_analytics()

    def _ensure_headers(self, ws, columns):
        existing = ws.row_values(1)
        if len(existing) < len(columns) or existing[:5] != columns[:5]:
            ws.update('A1:R1', [columns])

    def _get_or_create_wl_tab(self):
        try:
            ws = self.sh.worksheet("White Label")
        except gspread.exceptions.WorksheetNotFound:
            ws = self.sh.add_worksheet(title="White Label", rows=2000, cols=20)
        # Ensure headers
        headers = ws.row_values(1)
        if len(headers) < len(WL_COLUMNS) or headers[:5] != WL_COLUMNS[:5]:
            ws.update('A1:R1', [WL_COLUMNS])
        return ws

    def _get_or_create_analytics(self):
        try:
            return self.sh.worksheet("Analytics")
        except gspread.exceptions.WorksheetNotFound:
            ws = self.sh.add_worksheet(title="Analytics", rows=1000, cols=10)
            ws.update('A1:H1', [["Date","Leads Found","Qualified","Drafted","Sent","Replies","Landed","Notes"]])
            return ws

    def _refresh(self):
        try:
            from google.auth.transport.requests import Request
            if self.creds.expired:
                self.creds.refresh(Request())
                self.gc = gspread.authorize(self.creds)
                self.sh = self.gc.open_by_key(SHEET_ID)
                self.ws_leads = self.sh.worksheet("Lead")
                self.ws_wl = self.sh.worksheet("White Label")
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
                        time.sleep(wait)
                        continue
                raise
            except Exception as e:
                if i == attempts - 1:
                    raise
                if '429' in str(e):
                    wait = 30 * (i + 1)
                    if i < attempts - 1:
                        time.sleep(wait)
                        continue
                time.sleep(2 ** i)

    # ═══════════════════════════════════════════════════════════
    # WHITE LABEL TAB METHODS
    # ═══════════════════════════════════════════════════════════

    def get_wl_all(self):
        self._refresh()
        try:
            return self.ws_wl.get_all_records()
        except:
            return []

    def get_wl_by_status(self, status):
        all_leads = self.get_wl_all()
        return [l for l in all_leads if str(l.get("Status", "")).strip() == status]

    def get_wl_new(self):
        return self.get_wl_by_status("New")

    def get_wl_contacted(self):
        return self.get_wl_by_status("Contacted")

    def get_wl_drafted(self):
        return self.get_wl_by_status("Contacted")  # After drafting, status = Contacted

    def wl_exists(self, company="", website="", email=""):
        existing = self.get_wl_all()
        for row in existing:
            if company and str(row.get("Company Name", "")).lower().strip() == company.lower().strip():
                return True
            if website and str(row.get("Website", "")).lower().strip() == website.lower().strip():
                return True
            if email and str(row.get("Email", "")).lower().strip() == email.lower().strip():
                return True
        return False

    def add_wl_lead(self, lead: dict):
        self._refresh()
        if self.wl_exists(lead.get("Company Name", ""), lead.get("Website", ""), lead.get("Email", "")):
            return False
        row = [str(lead.get(col, "")) for col in WL_COLUMNS]
        if not lead.get("Status"):
            row[WL_COLUMNS.index("Status")] = "New"
        def _append():
            self.ws_wl.append_row(row, value_input_option='USER_ENTERED')
        self._retry(_append)
        return True

    def add_wl_batch(self, leads: list):
        self._refresh()
        added = 0
        skipped = 0
        existing = self.get_wl_all()
        existing_emails = {str(l.get("Email", "")).lower().strip() for l in existing if l.get("Email")}
        existing_domains = {str(l.get("Website", "")).lower().strip() for l in existing if l.get("Website")}
        rows = []
        for lead in leads:
            email = str(lead.get("Email", "")).lower().strip()
            website = str(lead.get("Website", "")).lower().strip()
            if email and email in existing_emails:
                skipped += 1
                continue
            if website and website in existing_domains:
                skipped += 1
                continue
            existing_emails.add(email)
            existing_domains.add(website)
            row = [str(lead.get(col, "")) for col in WL_COLUMNS]
            if not lead.get("Status"):
                row[WL_COLUMNS.index("Status")] = "New"
            rows.append(row)
        if rows:
            def _batch():
                self.ws_wl.append_rows(rows, value_input_option='USER_ENTERED')
            self._retry(_batch)
            added = len(rows)
        return added, skipped

    def update_wl_lead(self, company_name: str, updates: dict):
        self._refresh()
        all_rows = self.ws_wl.get_all_values()
        for i, row in enumerate(all_rows[1:], start=2):
            if str(row[0]).lower().strip() == company_name.lower().strip():
                for col_name, value in updates.items():
                    if col_name in WL_COLUMNS:
                        col_idx = WL_COLUMNS.index(col_name) + 1
                        def _upd():
                            self.ws_wl.update_cell(i, col_idx, str(value))
                        self._retry(_upd)
                return True
        return False

    def update_wl_status(self, company_name: str, new_status: str):
        return self.update_wl_lead(company_name, {"Status": new_status})

    def count_wl(self):
        return len([l for l in self.get_wl_all() if l.get("Company Name")])

    # ═══════════════════════════════════════════════════════════
    # LEAD TAB METHODS (original, untouched)
    # ═══════════════════════════════════════════════════════════

    def get_all_leads(self):
        self._refresh()
        try:
            return self.ws_leads.get_all_records()
        except:
            return []

    def get_leads_by_status(self, status):
        return [l for l in self.get_all_leads() if l.get("Status") == status]

    def get_new_leads(self):
        return self.get_leads_by_status(STATUS_NEW)

    def get_qualified_leads(self):
        return self.get_leads_by_status(STATUS_QUALIFIED)

    def get_drafted_leads(self):
        return self.get_leads_by_status(STATUS_DRAFTED)

    def lead_exists(self, company="", website="", email=""):
        for row in self.get_all_leads():
            if company and row.get("Company Name", "").lower().strip() == company.lower().strip():
                return True
            if website and row.get("Website", "").lower().strip() == website.lower().strip():
                return True
            if email and row.get("Owner Email", "").lower().strip() == email.lower().strip():
                return True
        return False

    def add_lead(self, lead: dict):
        self._refresh()
        if self.lead_exists(lead.get("Company Name", ""), lead.get("Website", ""), lead.get("Owner Email", "")):
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
        added = skipped = 0
        existing = self.get_all_leads()
        existing_emails = {l.get("Owner Email", "").lower().strip() for l in existing if l.get("Owner Email")}
        existing_domains = {l.get("Website", "").lower().strip() for l in existing if l.get("Website")}
        rows = []
        for lead in leads:
            email = str(lead.get("Owner Email", "")).lower().strip()
            website = str(lead.get("Website", "")).lower().strip()
            if email in existing_emails or website in existing_domains:
                skipped += 1
                continue
            existing_emails.add(email)
            existing_domains.add(website)
            row = [lead.get(col, "") for col in LEAD_COLUMNS]
            if not lead.get("Status"):
                row[LEAD_COLUMNS.index("Status")] = STATUS_NEW
            rows.append(row)
        if rows:
            def _batch():
                self.ws_leads.append_rows(rows, value_input_option='USER_ENTERED')
            self._retry(_batch)
            added = len(rows)
        return added, skipped

    def update_lead(self, company_name, updates):
        self._refresh()
        all_rows = self.ws_leads.get_all_values()
        for i, row in enumerate(all_rows[1:], start=2):
            if row[0].lower().strip() == company_name.lower().strip():
                for col_name, value in updates.items():
                    if col_name in LEAD_COLUMNS:
                        col_idx = LEAD_COLUMNS.index(col_name) + 1
                        def _upd():
                            self.ws_leads.update_cell(i, col_idx, value)
                        self._retry(_upd)
                return True
        return False

    def update_status(self, company_name, new_status):
        return self.update_lead(company_name, {"Status": new_status})

    def count_leads(self):
        return len([l for l in self.get_all_leads() if l.get("Company Name")])

    def log_analytics(self, data: dict):
        self._refresh()
        today = datetime.now(timezone(timedelta(hours=6))).strftime("%Y-%m-%d")
        row = [
            data.get("Date", today), data.get("Leads Found", 0), data.get("Qualified", 0),
            data.get("Drafted", 0), data.get("Sent", 0), data.get("Replies", 0),
            data.get("Landed", 0), data.get("Notes", ""),
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
