"""
1. Remove red background from ALL WL rows (undo previous mistake)
2. Then mark ONLY truly bounced leads RED
"""
import sys, os
from datetime import datetime, timezone, timedelta

NANOSOFT_DIR = "/home/ubuntu/nanosoft"
RE_PIPELINE_DIR = os.path.join(NANOSOFT_DIR, "re_pipeline")
BD_TZ = timezone(timedelta(hours=6))

def log(msg):
    ts = datetime.now(BD_TZ).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def fix_wl():
    """Clear all red, then mark only truly bounced."""
    sys.path.insert(0, NANOSOFT_DIR)
    from crm import NanoSoftCRM
    crm = NanoSoftCRM()
    crm._refresh()
    ws = crm.ws_wl
    all_values = ws.get_all_values()
    total_rows = len(all_values) - 1  # minus header

    # Step 1: Clear red background from ALL data rows
    log(f"WL: Clearing background from all {total_rows} rows...")
    clear_format = {
        "backgroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}  # white
    }
    # Do in batches of 50 rows at a time using format for ranges
    batch_size = 50
    for start_row in range(2, total_rows + 2, batch_size):
        end_row = min(start_row + batch_size - 1, total_rows + 1)
        rng = f"A{start_row}:V{end_row}"
        try:
            ws.format(rng, clear_format)
        except Exception as e:
            log(f"  Clear error rows {start_row}-{end_row}: {e}")
    log("WL: All backgrounds cleared")

    # Step 2: Find truly bounced rows
    bounced_rows = []
    for i, row in enumerate(all_values[1:], start=2):
        company = str(row[0]).strip() if len(row) > 0 else ""
        email = str(row[6]).strip() if len(row) > 6 else ""
        status = str(row[18]).strip() if len(row) > 18 else ""
        if company and (status == "Bounced" or email.startswith("BOUNCED_")):
            bounced_rows.append(i)

    log(f"WL: {len(bounced_rows)} truly bounced rows to mark RED")

    if not bounced_rows:
        return

    red_format = {
        "backgroundColor": {"red": 1.0, "green": 0.27, "blue": 0.0}
    }

    for row in bounced_rows:
        try:
            ws.format(f"A{row}:V{row}", red_format)
        except:
            pass
    log(f"WL: {len(bounced_rows)} bounced rows colored RED")

def fix_re():
    """Mark only truly bounced RE leads red."""
    sys.path.insert(0, NANOSOFT_DIR)
    sys.path.insert(0, RE_PIPELINE_DIR)
    from sheets import read_all_rows
    from config import COL

    all_rows = read_all_rows()
    if len(all_rows) <= 1:
        log("RE: No data")
        return

    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    import json
    from config import TOKEN_PATH, SHEET_ID, SHEET_NAME

    with open(TOKEN_PATH) as f:
        d = json.load(f)
    creds = Credentials(
        token=d['token'], refresh_token=d.get('refresh_token'),
        token_uri=d.get('token_uri', 'https://oauth2.googleapis.com/token'),
        client_id=d['client_id'], client_secret=d.get('client_secret'),
        scopes=d.get('scopes')
    )
    if creds.expired and creds.refresh_token:
        from google.auth.transport.requests import Request
        creds.refresh(Request())
        d['token'] = creds.token
        with open(TOKEN_PATH, 'w') as f:
            json.dump(d, f)

    service = build('sheets', 'v4', credentials=creds)
    sheet_id = None
    spreadsheet = service.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
    for sheet in spreadsheet.get("sheets", []):
        if sheet["properties"]["title"] == SHEET_NAME:
            sheet_id = sheet["properties"]["sheetId"]
            break

    if sheet_id is None:
        log("RE: Sheet not found!")
        return

    # Clear all backgrounds first
    total = len(all_rows) - 1
    log(f"RE: Clearing background from all {total} rows...")
    white = {"red": 1.0, "green": 1.0, "blue": 1.0}
    requests = []
    for i in range(2, total + 2):
        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": i - 1,
                    "endRowIndex": i,
                    "startColumnIndex": 0,
                    "endColumnIndex": 20,
                },
                "cell": {"userEnteredFormat": {"backgroundColor": white}},
                "fields": "userEnteredFormat.backgroundColor"
            }
        })

    for start in range(0, len(requests), 100):
        batch = requests[start:start + 100]
        try:
            service.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body={"requests": batch}).execute()
        except Exception as e:
            log(f"  RE clear error: {e}")
            break
    log("RE: All backgrounds cleared")

    # Now mark only truly bounced
    bounced_rows = []
    for i, row in enumerate(all_rows[1:], start=2):
        email = str(row[COL["Email"]]).strip() if len(row) > COL["Email"] else ""
        status = str(row[COL["Status"]]).strip() if len(row) > COL["Status"] else ""
        brokerage = str(row[COL["Brokerage_Name"]]).strip() if len(row) > COL["Brokerage_Name"] else ""
        if brokerage and (status == "Bounced" or email.startswith("BOUNCED_")):
            bounced_rows.append(i)

    log(f"RE: {len(bounced_rows)} truly bounced rows")

    if not bounced_rows:
        return

    red = {"red": 1.0, "green": 0.27, "blue": 0.0}
    requests = []
    for row in bounced_rows:
        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": row - 1,
                    "endRowIndex": row,
                    "startColumnIndex": 0,
                    "endColumnIndex": 20,
                },
                "cell": {"userEnteredFormat": {"backgroundColor": red}},
                "fields": "userEnteredFormat.backgroundColor"
            }
        })

    service.spreadsheets().batchUpdate(
        spreadsheetId=SHEET_ID, body={"requests": requests}
    ).execute()
    log(f"RE: {len(bounced_rows)} bounced rows colored RED")

def main():
    log("=" * 50)
    log("FIX: CLEAR ALL RED, THEN MARK ONLY BOUNCED")
    log("=" * 50)

    log("\n[1/2] White Label Sheet...")
    fix_wl()

    log("\n[2/2] RE Pipeline Sheet...")
    fix_re()

    log("\n" + "=" * 50)
    log("DONE! Only truly bounced leads are now RED.")
    log("Unqualified leads are back to normal (can be emailed).")
    log("=" * 50)

if __name__ == "__main__":
    main()
