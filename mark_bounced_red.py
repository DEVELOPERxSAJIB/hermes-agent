"""
Mark ONLY truly bounced leads RED — NOT "Unqualified" (those are leads we can still email).
Bounced = Status is "Bounced" or Email starts with "BOUNCED_"
"""
import sys, os
from datetime import datetime, timezone, timedelta

NANOSOFT_DIR = "/home/ubuntu/nanosoft"
RE_PIPELINE_DIR = os.path.join(NANOSOFT_DIR, "re_pipeline")
BD_TZ = timezone(timedelta(hours=6))

def log(msg):
    ts = datetime.now(BD_TZ).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def mark_wl_red():
    """Mark only truly bounced WL leads red (not Unqualified)."""
    sys.path.insert(0, NANOSOFT_DIR)
    from crm import NanoSoftCRM
    crm = NanoSoftCRM()
    crm._refresh()
    ws = crm.ws_wl
    all_values = ws.get_all_values()

    rows_to_color = []
    for i, row in enumerate(all_values[1:], start=2):
        company = str(row[0]).strip() if len(row) > 0 else ""
        email = str(row[6]).strip() if len(row) > 6 else ""
        status = str(row[18]).strip() if len(row) > 18 else ""

        # ONLY mark truly bounced — NOT Unqualified
        if company and (status == "Bounced" or email.startswith("BOUNCED_")):
            rows_to_color.append(i)

    log(f"WL: {len(rows_to_color)} truly bounced rows to color RED")

    if not rows_to_color:
        return

    red_format = {
        "backgroundColor": {"red": 1.0, "green": 0.27, "blue": 0.0}
    }

    done = 0
    for rng in [f"A{row}:V{row}" for row in rows_to_color]:
        try:
            ws.format(rng, red_format)
            done += 1
        except:
            pass
    log(f"WL: {done}/{len(rows_to_color)} rows colored RED")

def mark_re_red():
    """Mark only truly bounced RE leads red."""
    sys.path.insert(0, NANOSOFT_DIR)
    sys.path.insert(0, RE_PIPELINE_DIR)
    from sheets import read_all_rows
    from config import COL

    all_rows = read_all_rows()
    if len(all_rows) <= 1:
        log("RE: No data")
        return

    rows_to_color = []
    for i, row in enumerate(all_rows[1:], start=2):
        email = str(row[COL["Email"]]).strip() if len(row) > COL["Email"] else ""
        status = str(row[COL["Status"]]).strip() if len(row) > COL["Status"] else ""
        brokerage = str(row[COL["Brokerage_Name"]]).strip() if len(row) > COL["Brokerage_Name"] else ""
        if brokerage and (status == "Bounced" or email.startswith("BOUNCED_")):
            rows_to_color.append(i)

    log(f"RE: {len(rows_to_color)} truly bounced rows to color RED")

    if not rows_to_color:
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

    red_color = {"red": 1.0, "green": 0.27, "blue": 0.0}
    requests = []
    for row in rows_to_color:
        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": row - 1,
                    "endRowIndex": row,
                    "startColumnIndex": 0,
                    "endColumnIndex": 20,
                },
                "cell": {
                    "userEnteredFormat": {"backgroundColor": red_color}
                },
                "fields": "userEnteredFormat.backgroundColor"
            }
        })

    total = len(requests)
    done = 0
    for start in range(0, total, 100):
        batch = requests[start:start + 100]
        try:
            service.spreadsheets().batchUpdate(
                spreadsheetId=SHEET_ID, body={"requests": batch}
            ).execute()
            done += len(batch)
            log(f"RE: {done}/{total}")
        except Exception as e:
            log(f"RE: ERROR - {e}")
            break

def main():
    log("=" * 50)
    log("MARKING ONLY TRULY BOUNCED RED (not Unqualified)")
    log("=" * 50)

    log("\n[1/2] White Label Sheet...")
    mark_wl_red()

    log("\n[2/2] RE Pipeline Sheet...")
    mark_re_red()

    log("\n" + "=" * 50)
    log("DONE!")
    log("=" * 50)

if __name__ == "__main__":
    main()
