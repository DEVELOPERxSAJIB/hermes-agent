#!/usr/bin/env python3
"""Set proper follow-up dates for stuck leads so date-gap logic can process them"""
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import json, time

with open('/home/ubuntu/.hermes/google_token.json') as f:
    d = json.load(f)
creds = Credentials.from_authorized_user_info(d)
service = build('sheets', 'v4', credentials=creds)

today = datetime.now()

# ═══ WL: Set FU dates for stuck leads ═══
# Strategy: Set dates so follow-ups are due NOW (4+ days ago)
WL_SHEET_ID = "1POJ1ffcC6Z4dFDbgQj3VlECYPmApzXXJ5orNzf2-Yuo"
result = service.spreadsheets().values().get(
    spreadsheetId=WL_SHEET_ID, range='White Label!A1:V600'
).execute()
rows = result.get('values', [])
headers = rows[0]

idx_status = headers.index('Status')
idx_sent = headers.index('Sent date')
idx_fu1 = headers.index('FU 1')
idx_fu2 = headers.index('FU 2')
idx_fu3 = headers.index('FU 3')

batch = []
for i, row in enumerate(rows[1:], start=2):
    status = row[idx_status].strip() if idx_status < len(row) else ''
    sent = row[idx_sent].strip() if idx_sent < len(row) else ''
    fu1 = row[idx_fu1].strip() if idx_fu1 < len(row) else ''
    fu2 = row[idx_fu2].strip() if idx_fu2 < len(row) else ''
    fu3 = row[idx_fu3].strip() if idx_fu3 < len(row) else ''

    # T1 Sent with no FU1 → set FU1 to 5 days ago (so T2 is due)
    if status == 'T1 Sent' and sent and not fu1:
        d = (today - timedelta(days=5)).strftime('%d/%m/%Y')
        batch.append({'range': 'White Label!P' + str(i), 'values': [[d]]})

    # T2 Sent with no FU2 → set FU2 to 5 days ago (so T3 is due)
    elif status == 'T2 Sent' and fu1 and not fu2:
        d = (today - timedelta(days=5)).strftime('%d/%m/%Y')
        batch.append({'range': 'White Label!Q' + str(i), 'values': [[d]]})

    # T3 Sent with no FU3 → set FU3 to 8 days ago (so T4 is due)
    elif status == 'T3 Sent' and fu2 and not fu3:
        d = (today - timedelta(days=8)).strftime('%d/%m/%Y')
        batch.append({'range': 'White Label!R' + str(i), 'values': [[d]]})

print("WL: {} date fixes".format(len(batch)))
for i in range(0, len(batch), 50):
    chunk = batch[i:i+50]
    try:
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=WL_SHEET_ID,
            body={'valueInputOption': 'RAW', 'data': chunk}
        ).execute()
        print("  Batch {}: {} OK".format(i//50+1, len(chunk)))
        time.sleep(1)
    except Exception as e:
        print("  Error: {}".format(e))

# ═══ RE: Set FU dates for stuck leads ═══
RE_SHEET_ID = "1rQAyfC037JoV2phnLq4g9JsDvvrEb6M69A3roeYJHkk"
result = service.spreadsheets().values().get(
    spreadsheetId=RE_SHEET_ID, range='Pipeline!A1:T200'
).execute()
rows = result.get('values', [])
headers = rows[0]

idx_status = headers.index('Status')
idx_t1 = headers.index('Touch_1_Date')
idx_t2 = headers.index('Touch_2_Date')
idx_t3 = headers.index('Touch_3_Date')
idx_t4 = headers.index('Touch_4_Date')

batch = []
t1_count = 0
t2_count = 0
t3_count = 0

for i, row in enumerate(rows[1:], start=2):
    status = row[idx_status].strip() if idx_status < len(row) else ''
    t1 = row[idx_t1].strip() if idx_t1 < len(row) else ''
    t2 = row[idx_t2].strip() if idx_t2 < len(row) else ''
    t3 = row[idx_t3].strip() if idx_t3 < len(row) else ''
    t4 = row[idx_t4].strip() if idx_t4 < len(row) else ''

    # Contacted with T1 but no T2 → set T2 date to 5 days after T1
    if status == 'Contacted' and t1 and not t2:
        try:
            d = datetime.strptime(t1, '%d/%m/%Y')
            t2_date = (d + timedelta(days=5)).strftime('%d/%m/%Y')
        except:
            t2_date = (today - timedelta(days=5)).strftime('%d/%m/%Y')
        batch.append({'range': 'Pipeline!Q' + str(i), 'values': [[t2_date]]})
        t1_count += 1

    # T3 Sent with T2 but no T3 → set T3 date
    elif status == 'T3 Sent' and t2 and not t3:
        try:
            d = datetime.strptime(t2, '%d/%m/%Y')
            t3_date = (d + timedelta(days=5)).strftime('%d/%m/%Y')
        except:
            t3_date = (today - timedelta(days=5)).strftime('%d/%m/%Y')
        batch.append({'range': 'Pipeline!R' + str(i), 'values': [[t3_date]]})
        t2_count += 1

    # T3 Sent with T3 but no T4 → set T4 date
    elif status == 'T3 Sent' and t3 and not t4:
        try:
            d = datetime.strptime(t3, '%d/%m/%Y')
            t4_date = (d + timedelta(days=8)).strftime('%d/%m/%Y')
        except:
            t4_date = (today - timedelta(days=2)).strftime('%d/%m/%Y')
        batch.append({'range': 'Pipeline!S' + str(i), 'values': [[t4_date]]})
        t3_count += 1

    # Followed-Up with T2 but no T3
    elif status == 'Followed-Up' and t2 and not t3:
        try:
            d = datetime.strptime(t2, '%d/%m/%Y')
            t3_date = (d + timedelta(days=5)).strftime('%d/%m/%Y')
        except:
            t3_date = (today - timedelta(days=5)).strftime('%d/%m/%Y')
        batch.append({'range': 'Pipeline!R' + str(i), 'values': [[t3_date]]})
        t2_count += 1

print("\nRE: {} date fixes (T1→T2: {}, T2→T3: {}, T3→T4: {})".format(
    len(batch), t1_count, t2_count, t3_count))

for i in range(0, len(batch), 50):
    chunk = batch[i:i+50]
    try:
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=RE_SHEET_ID,
            body={'valueInputOption': 'RAW', 'data': chunk}
        ).execute()
        print("  Batch {}: {} OK".format(i//50+1, len(chunk)))
        time.sleep(1)
    except Exception as e:
        print("  Error: {}".format(e))

print("\nAll stuck leads now have proper follow-up dates!")
print("The pipeline will pick them up on the next run.")
