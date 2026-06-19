#!/usr/bin/env python3
"""
Batch mark guessed emails in Email Score column.
"""
import sys
import time
sys.path.insert(0, '/home/ubuntu/nanosoft')

from crm import get_crm, WL_COLUMNS

crm = get_crm()
ws = crm.ws_wl
all_rows = ws.get_all_values()

status_col = WL_COLUMNS.index('Status') + 1
email_col = WL_COLUMNS.index('Email') + 1
score_col = WL_COLUMNS.index('Email Score') + 1

guessed_prefixes = ('info@', 'hello@', 'contact@', 'sales@', 'team@')

cells_to_update = []
for i, row in enumerate(all_rows[1:], start=2):
    if status_col - 1 >= len(row):
        continue
    if str(row[status_col - 1]).strip() != 'New':
        continue
    email = str(row[email_col - 1]).strip().lower() if email_col - 1 < len(row) else ''
    current_score = str(row[score_col - 1]).strip() if score_col - 1 < len(row) else ''
    if email.startswith(guessed_prefixes) and current_score != 'guessed':
        cells_to_update.append(i)

print(f"Found {len(cells_to_update)} guessed emails to mark")

batch_size = 10
updated = 0
for batch_start in range(0, len(cells_to_update), batch_size):
    batch = cells_to_update[batch_start:batch_start + batch_size]
    cell_list = []
    for row_idx in batch:
        try:
            cell = ws.cell(row_idx, score_col)
            cell.value = 'guessed'
            cell_list.append(cell)
        except Exception as e:
            print(f"  Error row {row_idx}: {e}")
    
    if cell_list:
        try:
            ws.update_cells(cell_list)
            updated += len(cell_list)
            print(f"  Updated {len(cell_list)} ({updated}/{len(cells_to_update)})")
        except Exception as e:
            print(f"  ERROR: {e}")
            time.sleep(30)
            try:
                ws.update_cells(cell_list)
                updated += len(cell_list)
            except:
                pass
    time.sleep(15)

print(f"\n=== DONE: {updated} guessed emails marked ===")
