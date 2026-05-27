"""
NanoSoft CRM — Google Sheets wrapper
Works with Chairman's Lead sheet structure.
"""
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timezone, timedelta
import json
import time
import os

# ─── CONFIG ────────────────────────────────────────────────

SERVICE_ACCOUNT_FILE = "/home/ubuntu/nanosoft/gcp_service_account.json"
SHEET_ID = "1S9jTTe1rKfe0GqqdVgXXgVkdtrRgHtwxu44pERYMOTo"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Lead sheet columns (exact match to Chairman's sheet)
LEAD_COLUMNS = [
    "Company Name",
    "Website (if have)",
    "Owner Name",
    "Owner Email",
    "Linkedin",
    "Pain Point",
    "Email sent date",
    "Follow up 01",
    "Follow up 02",
    "Status",
]

# Valid status values
STATUS_NEW = "New"
STATUS_EMAIL_SENT = "Email Sent"
STATUS_FOLLOWUP_1 = "Follow Up 1"
STATUS_FOLLOWUP_2 = "Follow Up 2"
STATUS_REPLIED = "Replied"
STATUS_LANDED = "Landed"
STATUS_LOST = "Lost"
STATUS_QUALIFIED = "Qualified"
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
        self.creds = Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        self.gc = gspread.authorize(self.creds)
        self.sh = self.gc.open_by_key(SHEET_ID)
        self.ws_leads = self.sh.worksheet("Lead")
        self._ensure_lead_headers()
        # Analytics sheet (create if not exists)
        self.ws_analytics = self._get_or_create_analytics()

    def _ensure_lead_headers(self):
        """Make sure Lead sheet has correct headers (no duplicates)."""
        existing = self.ws_leads.row_values(1)
        # Remove duplicate columns
        seen = set()
        clean = []
        for h in existing:
            if h not in seen:
                seen.add(h)
                clean.append(h)
        if clean != LEAD_COLUMNS or len(existing) != len(LEAD_COLUMNS):
            # Rewrite headers
            self.ws_leads.update('A1:J1', [LEAD_COLUMNS])
            # If there were extra columns, clear them
            if len(existing) > len(LEAD_COLUMNS):
                self.ws_leads.delete_columns(len(LEAD_COLUMNS) + 1, len(existing))

    def _get_or_create_analytics(self):
        """Get or create Analytics sheet."""
        try:
            ws = self.sh.worksheet("Analytics")
        except gspread.exceptions.WorksheetNotFound:
            ws = self.sh.add_worksheet(title="Analytics", rows=1000, cols=10)
            headers = [
                "Date", "Leads Found", "Qualified", "Emails Sent",
                "Replies", "Landed", "Revenue", "Notes"
            ]
            ws.update('A1:H1', [headers])
        return ws

    def _refresh(self):
        """Re-authorize if token expired."""
        try:
            if self.creds.expired:
                self.creds.refresh()
                self.gc = gspread.authorize(self.creds)
                self.sh = self.gc.open_by_key(SHEET_ID)
                self.ws_leads = self.sh.worksheet("Lead")
                self.ws_analytics = self._get_or_create_analytics()
        except Exception:
            pass

    def _retry(self, fn, attempts=5):
        """Retry with exponential backoff. Handles Google 429 quota errors."""
        import gspread.exceptions as gexc
        for i in range(attempts):
            try:
                return fn()
            except gexc.APIError as e:
                error_code = getattr(e, 'response', None)
                # Check if it's a rate limit (429) or server error (5xx)
                status = getattr(error_code, 'status_code', 0) if error_code else 0
                if status == 429 or status >= 500:
                    wait = 30 * (i + 1)  # 30s, 60s, 90s, 120s, 150s
                    if i < attempts - 1:
                        print(f"[CRM] Rate limited (HTTP {status}). Waiting {wait}s before retry {i+1}/{attempts}...")
                        time.sleep(wait)
                        continue
                raise
            except Exception as e:
                if i == attempts - 1:
                    raise
                # Check for 429 in error message
                error_str = str(e)
                if '429' in error_str or 'quota' in error_str.lower():
                    wait = 30 * (i + 1)
                    if i < attempts - 1:
                        print(f"[CRM] Quota error. Waiting {wait}s before retry {i+1}/{attempts}...")
                        time.sleep(wait)
                        continue
                time.sleep(2 ** i)

    # ─── LEADS TAB ──────────────────────────────────────────

    def get_all_leads(self):
        """Return all leads as list of dicts."""
        self._refresh()
        try:
            return self.ws_leads.get_all_records()
        except Exception:
            # If header issue, fix and retry
            self._ensure_lead_headers()
            return self.ws_leads.get_all_records(expected_headers=LEAD_COLUMNS)

    def get_leads_by_status(self, status):
        """Get leads filtered by status."""
        all_leads = self.get_all_leads()
        return [l for l in all_leads if l.get("Status") == status]

    def get_new_leads(self):
        """Get leads with Status='New'."""
        return self.get_leads_by_status(STATUS_NEW)

    def get_qualified_leads(self):
        """Get leads with Status='Qualified'."""
        return self.get_leads_by_status(STATUS_QUALIFIED)

    def get_leads_without_email(self):
        """Get leads that have no Owner Email yet."""
        all_leads = self.get_all_leads()
        return [l for l in all_leads if not l.get("Owner Email")]

    def get_leads_with_email(self):
        """Get leads that have an Owner Email."""
        all_leads = self.get_all_leads()
        return [l for l in all_leads if l.get("Owner Email")]

    def lead_exists(self, company_name, website=""):
        """Check if lead already exists."""
        existing = self.get_all_leads()
        for row in existing:
            if row.get("Company Name", "").lower().strip() == company_name.lower().strip():
                return True
            if website and row.get("Website (if have)", "").lower().strip() == website.lower().strip():
                return True
        return False

    def add_lead(self, lead: dict):
        """
        Add a new lead row. Returns True if added, False if duplicate.
        lead dict keys match LEAD_COLUMNS.
        """
        self._refresh()
        company = lead.get("Company Name", "")
        website = lead.get("Website (if have)", "")

        if self.lead_exists(company, website):
            return False

        row = [lead.get(col, "") for col in LEAD_COLUMNS]
        # Default status to New if not set
        if not lead.get("Status"):
            row[LEAD_COLUMNS.index("Status")] = STATUS_NEW

        def _append():
            self.ws_leads.append_row(row, value_input_option='USER_ENTERED')
        self._retry(_append)
        return True

    def add_leads_batch(self, leads: list):
        """
        Add multiple leads. Returns (added_count, skipped_count).
        Each lead is a dict with keys matching LEAD_COLUMNS.
        """
        self._refresh()
        added = 0
        skipped = 0
        existing = self.get_all_leads()
        existing_companies = {(l.get("Company Name", "").lower().strip(), l.get("Website (if have)", "").lower().strip()) for l in existing}
        
        rows_to_append = []
        for lead in leads:
            company = lead.get("Company Name", "")
            website = lead.get("Website (if have)", "")
            key = (company.lower().strip(), website.lower().strip())
            
            if key in existing_companies:
                skipped += 1
                continue
            
            existing_companies.add(key)
            row = [lead.get(col, "") for col in LEAD_COLUMNS]
            if not lead.get("Status"):
                row[LEAD_COLUMNS.index("Status")] = STATUS_NEW
            rows_to_append.append(row)
        
        if rows_to_append:
            def _batch_append():
                self.ws_leads.append_rows(rows_to_append, value_input_option='USER_ENTERED')
            self._retry(_batch_append)
            added = len(rows_to_append)
        
        return added, skipped

    def update_lead(self, company_name: str, updates: dict):
        """
        Update a lead by company name.
        updates: {column_name: new_value}
        """
        self._refresh()
        all_leads = self.ws_leads.get_all_values()
        for i, row in enumerate(all_leads[1:], 2):  # skip header, 1-indexed + header
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
        """Update the Status of a lead."""
        return self.update_lead(company_name, {"Status": new_status})

    def count_leads(self):
        """Count total non-empty leads."""
        all_leads = self.get_all_leads()
        return len([l for l in all_leads if l.get("Company Name")])

    # ─── ANALYTICS TAB ──────────────────────────────────────

    def log_analytics(self, data: dict):
        """Log a daily analytics row."""
        self._refresh()
        today = datetime.now(timezone(timedelta(hours=6))).strftime("%Y-%m-%d")
        row = [
            data.get("Date", today),
            data.get("Leads Found", 0),
            data.get("Qualified", 0),
            data.get("Emails Sent", 0),
            data.get("Replies", 0),
            data.get("Landed", 0),
            data.get("Revenue", 0),
            data.get("Notes", ""),
        ]
        def _append():
            self.ws_analytics.append_row(row, value_input_option='USER_ENTERED')
        self._retry(_append)

    def get_analytics(self):
        """Get all analytics rows."""
        self._refresh()
        return self.ws_analytics.get_all_records()


# ─── SINGLETON ────────────────────────────────────────────

_crm = None

def get_crm():
    global _crm
    if _crm is None:
        _crm = NanoSoftCRM()
    return _crm
