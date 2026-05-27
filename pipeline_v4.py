"""
Pipeline v4 — 24/7 Automated Lead Generation
Uses SCOUT v9 (domain generation + DNS + HTTP analysis) + JUDGE v4 + email drafting
Runs continuously: finds 30 qualified leads/day, stops, repeats next day
"""
import sys
import time
import os
import json
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
LOG_FILE = os.path.join(NANOSOFT_DIR, "pipeline_v4.log")
STATE_FILE = os.path.join(NANOSOFT_DIR, "pipeline_v4_state.json")

sys.path.insert(0, NANOSOFT_DIR)
from crm import get_crm


def log(msg):
    ts = datetime.now(BD_TZ).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, 'a') as f:
        f.write(line + "\n")


def load_pipeline_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"last_run_date": "", "runs": 0}


def save_pipeline_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def run_pipeline():
    """Main pipeline loop. Runs forever, one cycle per day."""
    log("=== Pipeline v4 started ===")

    while True:
        try:
            today = datetime.now(BD_TZ).strftime("%Y-%m-%d")
            pstate = load_pipeline_state()

            # Check if already ran today
            if pstate.get("last_run_date") == today:
                log(f"Already ran today ({today}). Sleeping 1 hour...")
                time.sleep(3600)
                continue

            # Run daily scout (SCOUT v9)
            log(f"Starting daily scout for {today}...")

            try:
                from scout_v10 import run_daily_scout
                found = run_daily_scout(target=30)
                log(f"SCOUT found {found} qualified leads")
            except ImportError as e:
                log(f"SCOUT import error: {e}")
                time.sleep(300)
                continue
            except Exception as e:
                log(f"SCOUT error: {e}")
                time.sleep(300)
                continue

            # Update pipeline state
            pstate["last_run_date"] = today
            pstate["runs"] = pstate.get("runs", 0) + 1
            save_pipeline_state(pstate)

            # Report results
            try:
                crm = get_crm()
                total = crm.count_leads()
                log(f"Total leads in sheet: {total}")
            except Exception as e:
                log(f"CRM count error (non-fatal): {e}")

            # Sleep 1 hour, then check if it's a new day
            log("Sleeping 1 hour before next check...")
            time.sleep(3600)

        except KeyboardInterrupt:
            log("Pipeline stopped")
            break
        except Exception as e:
            log(f"ERROR: {e}")
            time.sleep(300)


if __name__ == "__main__":
    run_pipeline()
