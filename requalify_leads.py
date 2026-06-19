#!/usr/bin/env python3
"""
Batch requalify Unqualified leads with score >= 7 to New status.
Uses direct gspread batch update to avoid 195 individual API calls.
"""
import sys
import time
sys.path.insert(0, '/home/ubuntu/nanosoft')

from crm import get_crm, WL_COLUMNS

crm = get_crm()
leads = crm.get_wl_all()

# Find Unqualified leads with score >= 7
to_requalify = []
for lead in leads:
    if lead.get('Status') != 'Unqualified':
        continue
    score = str(lead.get('Judge Score', ''))
    if score and score.isdigit() and int(score) >= 7:
        to_requalify.append(lead.get('Company Name', ''))

print(f"Found {len(to_requalify)} Unqualified leads with score >= 7 to requalify")

if not to_requalify:
    print("Nothing to do.")
    sys.exit(0)

# Use direct sheet access for batch update
ws = crm.ws_wl
all_rows = ws.get_all_values()
status_col = WL_COLUMNS.index('Status') + 1  # 1-indexed

# Build list of cell updates
cells_to_update = []
for i, row in enumerate(all_rows[1:], start=2):  # start=2 (skip header)
    company = str(row[0]).strip()
    current_status = str(row[status_col - 1]).strip() if status_col - 1 < len(row) else ''
    if current_status == 'Unqualified' and company in to_requalify:
        cells_to_update.append((i, company))

print(f"Found {len(cells_to_update)} rows to update in sheet")

# Batch update in chunks of 20
batch_size = 20
updated = 0
for batch_start in range(0, len(cells_to_update), batch_size):
    batch = cells_to_update[batch_start:batch_start + batch_size]
    cell_list = []
    for row_idx, company in batch:
        cell = ws.cell(row_idx, status_col)
        cell.value = 'New'
        cell_list.append(cell)
    
    try:
        ws.update_cells(cell_list)
        updated += len(batch)
        print(f"  Batch {batch_start//batch_size + 1}: updated {len(batch)} leads ({updated}/{len(cells_to_update)})")
    except Exception as e:
        print(f"  Batch {batch_start//batch_size + 1} ERROR: {e}")
    
    time.sleep(2)  # Rate limit between batches

print(f"\n=== DONE: {updated} leads requalified from Unqualified to New ===")
