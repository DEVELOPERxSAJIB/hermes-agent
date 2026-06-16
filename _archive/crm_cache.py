#!/usr/bin/python3
"""
CRM Cache Layer — reduces Google Sheets API calls dramatically.
- Reads/writes a local JSON cache file
- Only syncs to Google Sheets when explicitly requested
- All scripts use this instead of hitting Sheets directly
"""
import json
import os
import time
import sys

NANOSOFT_DIR = "/home/ubuntu/nanosoft"
CACHE_FILE = os.path.join(NANOSOFT_DIR, "crm_cache.json")
CACHE_TTL = 300  # 5 minutes


def get_crm():
    """Get CRM instance — from cache if fresh, otherwise from Google Sheets."""
    # Check if cache is fresh
    if os.path.exists(CACHE_FILE):
        cache_age = time.time() - os.path.getmtime(CACHE_FILE)
        if cache_age < CACHE_TTL:
            try:
                with open(CACHE_FILE) as f:
                    data = json.load(f)
                return CachedCRM(data)
            except:
                pass

    # Cache stale or missing — fetch from Google Sheets
    sys.path.insert(0, NANOSOFT_DIR)
    from crm import get_crm as get_real_crm
    crm = get_real_crm()
    leads = crm.get_wl_all()

    # Write cache
    cache_data = {
        "leads": leads,
        "timestamp": time.time(),
        "count": len(leads),
    }
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(cache_data, f)
    except:
        pass

    return CachedCRM(cache_data)


class CachedCRM:
    """CRM wrapper that works from cached data."""

    def __init__(self, data):
        self._data = data
        self._leads = data.get("leads", [])
        self._modified = []

    def get_wl_all(self):
        return list(self._leads)

    def get_wl_by_status(self, status):
        return [l for l in self._leads if l.get("Status", "").strip() == status]

    def get_wl_qualified(self):
        return self.get_wl_by_status("Qualified")

    def get_wl_new(self):
        return self.get_wl_by_status("New")

    def get_wl_contacted(self):
        return [l for l in self._leads if l.get("Status", "").strip() in ("T1 Sent", "Sent")]

    def update_wl_lead(self, company, updates):
        """Update a lead in cache and mark for sync."""
        for l in self._leads:
            if l.get("Company Name", "").strip() == company:
                l.update(updates)
                self._modified.append((company, updates))
                return True
        return False

    def sync_to_sheets(self):
        """Push all modifications to Google Sheets."""
        if not self._modified:
            return

        sys.path.insert(0, NANOSOFT_DIR)
        from crm import get_crm as get_real_crm
        import gspread
        from google.oauth2.service_account import Credentials
        from crm import SHEET_ID, SCOPES, SERVICE_ACCOUNT_FILE

        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(SHEET_ID)
        ws = sh.worksheet("White Label")

        # Get current headers
        headers = ws.row_values(1)
        company_idx = headers.index("Company Name") if "Company Name" in headers else 0

        for company, updates in self._modified:
            try:
                # Find row by company name
                cell = ws.find(company)
                if cell:
                    row = cell.row
                    for col_name, value in updates.items():
                        if col_name in headers:
                            col_idx = headers.index(col_name) + 1
                            ws.update_cell(row, col_idx, str(value))
                            time.sleep(0.5)
            except Exception as e:
                print(f"  SYNC ERROR: {company}: {e}")
                time.sleep(2)

        self._modified = []
        # Update cache timestamp
        self._data["timestamp"] = time.time()
        try:
            with open(CACHE_FILE, "w") as f:
                json.dump(self._data, f)
        except:
            pass


if __name__ == "__main__":
    # Test
    crm = get_crm()
    leads = crm.get_wl_all()
    print(f"Loaded {len(leads)} leads from {'cache' if time.time() - os.path.getmtime(CACHE_FILE) < CACHE_TTL else 'Google Sheets'}")
