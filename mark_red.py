"""
Mark bounced and unqualified leads RED in the White Label Google Sheet.
Uses gspread to find rows, then Google Sheets API v4 for coloring.
"""
import json, os, sys, time
from datetime import datetime, timezone, timedelta

NANOSOFT_DIR = "/home/ubuntu/nanosoft"
BD_TZ = timezone(timedelta(hours=6))

def log(msg):
    ts = datetime.now(BD_TZ).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def get_sheet_id_and_service():
    """Get the White Label sheet ID and a Sheets API service."""
    sys.path.insert(0, NANOSOFT_DIR)
    from crm import NanoSoftCRM
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    crm = NanoSoftCRM()
    crm._refresh()
    ws = crm.ws_wl
    sheet_id = ws.id  # gspread gives us the sheet ID

    # Build Sheets API service from the same creds
    creds = Credentials.from_service_account_file(
        os.path.join(NANOSOFT_DIR, "gcp_service_account.json"),
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    service = build("sheets", "v4", credentials=creds)

    return sheet_id, service, crm

def find_rows_to_color(crm):
    """Find rows that need RED: Bounced status or Unqualified status."""
    crm._refresh()
    ws = crm.ws_wl
    all_values = ws.get_all_values()

    bounced_rows = []
    unqualified_rows = []

    for i, row in enumerate(all_values[1:], start=1):  # 0-based index, skip header
        company = str(row[0]).strip() if len(row) > 0 else ""
        email = str(row[6]).strip() if len(row) > 6 else ""
        status = str(row[18]).strip() if len(row) > 18 else ""

        if not company:
            continue

        if status == "Bounced" or email.startswith("BOUNCED_"):
            bounced_rows.append(i)
        elif status == "Unqualified":
            unqualified_rows.append(i)

    return bounced_rows, unqualified_rows

def color_rows(sheet_id, row_indices, service, spreadsheet_id):
    """Color entire rows RED using Sheets API v4 batchUpdate."""
    if not row_indices:
        return

    red_color = {"red": 1.0, "green": 0.27, "blue": 0.0}
    requests = []

    for row_idx in row_indices:
        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": row_idx,
                    "endRowIndex": row_idx + 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": 22,
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": red_color,
                    }
                },
                "fields": "userEnteredFormat.backgroundColor"
            }
        })

    # Execute in batches of 100
    batch_size = 100
    total = len(requests)
    done = 0
    for start in range(0, total, batch_size):
        batch = requests[start:start + batch_size]
        body = {"requests": batch}
        try:
            result = service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body=body
            ).execute()
            done += len(batch)
            log(f"  Batch {start//batch_size + 1}: {done}/{total}")
        except Exception as e:
            log(f"  Batch {start//batch_size + 1} ERROR: {e}")
            if "404" in str(e):
                log("  -> Spreadsheet not found. Check service account permissions.")
            break

def main():
    log("=" * 50)
    log("MARKING BOUNCED + UNQUALIFIED ROWS RED")
    log("=" * 50)

    # 1. Get sheet ID and service
    log("\nConnecting to Google Sheets API...")
    try:
        sheet_id, service, crm = get_sheet_id_and_service()
        log(f"  White Label sheet ID: {sheet_id}")
    except Exception as e:
        log(f"  ERROR: {e}")
        return

    # Get spreadsheet ID from the CRM
    spreadsheet_id = crm.sh.id

    # 2. Find rows
    log("\nScanning for bounced/unqualified leads...")
    bounced, unqualified = find_rows_to_color(crm)
    log(f"  Bounced: {len(bounced)}")
    log(f"  Unqualified: {len(unqualified)}")

    all_rows = list(set(bounced + unqualified))
    all_rows.sort()

    if not all_rows:
        log("\nNo rows to color. All clean!")
        return

    log(f"\nTotal rows to mark RED: {len(all_rows)}")

    # 3. Color them
    log("Applying red background...")
    color_rows(sheet_id, all_rows, service, spreadsheet_id)

    log("\n" + "=" * 50)
    log("DONE! Check your Google Sheet.")
    log("=" * 50)

if __name__ == "__main__":
    main()
