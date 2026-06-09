#!/usr/bin/python3
"""
NanoSoft Daily Startup Script
1. Wait for Google Places API quota reset (if needed)
2. Verify the API is working
3. Reset daily state
4. Start the pipeline
"""
import json, urllib.request, urllib.error, time, subprocess, os, sys
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
STATE_FILE = os.path.join(NANOSOFT_DIR, "pipeline_v4_state.json")

def log(msg):
    ts = datetime.now(BD_TZ).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(os.path.join(NANOSOFT_DIR, "daily_startup.log"), 'a') as f:
        f.write(line + "\n")

def verify_api():
    """Test Google Places API"""
    key_path = os.path.join(NANOSOFT_DIR, "google_places_key.json")
    if not os.path.exists(key_path):
        log("ERROR: google_places_key.json not found")
        return False
    with open(key_path) as f:
        cfg = json.load(f)
    key = cfg['api_key']
    url = f'https://maps.googleapis.com/maps/api/place/textsearch/json?query=test&key={key}'
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            status = data.get('status', 'UNKNOWN')
            if status == 'OK':
                log(f"Google Places API: OK ({len(data.get('results', []))} results)")
                return True
            elif status == 'OVER_QUERY_LIMIT':
                log("Google Places API: QUOTA EXCEEDED")
                return False
            elif status == 'REQUEST_DENIED':
                log(f"Google Places API: REQUEST DENIED - {data.get('error_message', '')}")
                return False
            else:
                log(f"Google Places API: {status}")
                return True  # API reachable, not quota
    except urllib.error.HTTPError as e:
        log(f"HTTP Error {e.code}: {e.reason}")
        try: log(e.read().decode()[:300])
        except: pass
        return False
    except Exception as e:
        log(f"Error: {e}")
        return False

def reset_daily_state():
    """Reset pipeline_v4_state so it will run fresh today"""
    today = datetime.now(BD_TZ).strftime("%Y-%m-%d")
    state = {"last_run_date": "", "runs": 0}
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)
    log(f"Daily state reset. Ready for {today}.")

def is_pipeline_running():
    """Check if pipeline_v4.py is already running"""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "pipeline_v4.py"],
            capture_output=True, text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split('\n')
            return True, pids
    except Exception:
        pass
    return False, []

def start_pipeline():
    """Start pipeline_v4.py in background"""
    pipeline_path = os.path.join(NANOSOFT_DIR, "pipeline_v4.py")
    if not os.path.exists(pipeline_path):
        log(f"ERROR: {pipeline_path} not found")
        return False
    log("Starting pipeline_v4.py...")
    proc = subprocess.Popen(
        [sys.executable, pipeline_path],
        cwd=NANOSOFT_DIR,
        stdout=open(os.path.join(NANOSOFT_DIR, "pipeline_v4.log"), 'a'),
        stderr=subprocess.STDOUT,
        start_new_session=True
    )
    log(f"Pipeline started (PID: {proc.pid})")
    time.sleep(2)
    running, pids = is_pipeline_running()
    if running:
        log(f"Pipeline confirmed running (PIDs: {', '.join(pids)})")
        return True
    else:
        log("WARNING: Pipeline process may not have started properly")
        return False

# === MAIN ===
log("=" * 50)
log("NanoSoft Daily Startup - BEGIN")
log("=" * 50)

# Step 1 & 2: Verify API with retry on quota
log("Step 1: Verifying Google Places API...")
max_retries = 3
api_ok = False
for attempt in range(1, max_retries + 1):
    api_ok = verify_api()
    if api_ok:
        break
    log(f"API check failed, attempt {attempt}/{max_retries}")
    if attempt < max_retries:
        log("Waiting 60s before retry...")
        time.sleep(60)

if not api_ok:
    log("WARNING: API still not responding after retries. Proceeding anyway...")

# Step 3: Reset daily state
log("Step 2: Resetting daily state...")
reset_daily_state()

# Step 4: Check and start pipeline
log("Step 3: Checking pipeline status...")
running, pids = is_pipeline_running()
if running:
    log(f"Pipeline already running (PIDs: {', '.join(pids)}). Not starting a new one.")
else:
    log("Pipeline not running. Starting now...")
    start_pipeline()

log("=" * 50)
log("NanoSoft Daily Startup - COMPLETE")
log("=" * 50)
