#!/usr/bin/env python3
"""
Continue batch requalify of Unqualified leads with score >= 7 to New status.
Resumes where previous run left off (skips already-updated leads).
"""
import sys
import time
sys.path.insert(0, '/home/ubuntu/nanosoft')

from crm import get_crm, WL_COLUMNS

crm = get_crm()
leads = crm.get_wl_all()

# Re-check current state — find remaining Unqualified with score >= 7
ws = crm.ws_wl
all_rows = ws.get_all_values()
status_col = WL_COLUMNS.index('Status') + 1  # 1-indexed
score_col = WL_COLUMNS.index('Judge Score') + 1

cells_to_update = []
for i, row in enumerate(all_rows[1:], start=2):
    if status_col - 1 >= len(row):
        continue
    current_status = str(row[status_col - 1]).strip()
    if current_status != 'Unqualified':
        continue
    score_str = str(row[score_col - 1]).strip() if score_col - 1 < len(row) else ''
    if score_str and score_str.isdigit() and int(score_str) >= 7:
        company = str(row[0]).strip()
        cells_to_update.append((i, company))

print(f"Remaining Unqualified leads with score >= 7: {len(cells_to_update)}")

if not cells_to_update:
    print("All done! No more to requalify.")
    sys.exit(0)

# Batch update in chunks of 10 with 30s delay (safer for rate limits)
batch_size = 10
updated = 0
for batch_start in range(0, len(cells_to_update), batch_size):
    batch = cells_to_update[batch_start:batch_start + batch_size]
    cell_list = []
    for row_idx, company in batch:
        try:
            cell = ws.cell(row_idx, status_col)
            cell.value = 'New'
            cell_list.append(cell)
        except Exception as e:
            print(f"  Error reading cell for {company}: {e}")
            continue
    
    if cell_list:
        try:
            ws.update_cells(cell_list)
            updated += len(cell_list)
            print(f"  Batch updated {len(cell_list)} ({updated}/{len(cells_to_update)})")
        except Exception as e:
            print(f"  Batch ERROR: {e}")
            print("  Waiting 60s before retry...")
            time.sleep(60)
            try:
                ws.update_cells(cell_list)
                updated += len(cell_list)
                print(f"  Retry OK: {len(cell_list)} updated")
            except Exception as e2:
                print(f"  Retry FAILED: {e2}")
    
    time.sleep(30)

print(f"\n=== DONE: {updated} leads requalified ===")
