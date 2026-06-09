#!/bin/bash
# NanoSoft Daily Outreach Script
# Runs LinkedIn + Reddit + Email scout/enrich/judge/send pipeline

LOG_DIR="/tmp/nanosoft_daily"
mkdir -p "$LOG_DIR"
DATE=$(date +%Y%m%d_%H%M%S)
LOG="$LOG_DIR/run_$DATE.log"

echo "[$DATE] === NANOsoft DAILY PIPELINE START ===" | tee "$LOG"

# === STEP 1: Scout new leads ===
echo "[$DATE] Step 1: Scouting..." | tee -a "$LOG"
timeout 900 python3 /home/ubuntu/nanosoft/scout_wl_v5.py >> "$LOG" 2>&1
SCOUT_EXIT=$?
echo "[$DATE] Scout done (exit: $SCOUT_EXIT)" | tee -a "$LOG"

# === STEP 2: Enrich new leads ===
echo "[$DATE] Step 2: Enriching..." | tee -a "$LOG"
timeout 600 python3 /home/ubuntu/nanosoft/enrich_wl_leads.py >> "$LOG" 2>&1
echo "[$DATE] Enrich done" | tee -a "$LOG"

# === STEP 3: Judge new/enriched leads ===
echo "[$DATE] Step 3: Judging..." | tee -a "$LOG"
timeout 300 python3 /home/ubuntu/nanosoft/judge_wl.py >> "$LOG" 2>&1
echo "[$DATE] Judge done" | tee -a "$LOG"

# === STEP 4: Find emails for qualified without email ===
echo "[$DATE] Step 4: Finding emails..." | tee -a "$LOG"
timeout 600 python3 /home/ubuntu/nanosoft/scrape_wl_emails.py --status Qualified --limit 50 >> "$LOG" 2>&1
echo "[$DATE] Email find done" | tee -a "$LOG"

# === STEP 5: Send T1 to qualified ===
echo "[$DATE] Step 5: Sending T1..." | tee -a "$LOG"
if [ -f /home/ubuntu/nanosoft/GMAIL_TOKEN_DEAD ]; then
    echo "[$DATE] GMAIL TOKEN DEAD - skipping send" | tee -a "$LOG"
else
    timeout 3600 python3 /home/ubuntu/nanosoft/quill_wl.py send --template T1 --limit 100 >> "$LOG" 2>&1
    echo "[$DATE] T1 send done" | tee -a "$LOG"
fi

# === STEP 6: Send T2 to T1 Sent (3+ days ago) ===
echo "[$DATE] Step 6: Sending T2..." | tee -a "$LOG"
if [ -f /home/ubuntu/nanosoft/GMAIL_TOKEN_DEAD ]; then
    echo "[$DATE] GMAIL TOKEN DEAD - skipping send" | tee -a "$LOG"
else
    timeout 3600 python3 /home/ubuntu/nanosoft/quill_wl.py send --template T2 --limit 100 >> "$LOG" 2>&1
    echo "[$DATE] T2 send done" | tee -a "$LOG"
fi

# === STEP 7: Generate LinkedIn action list ===
echo "[$DATE] Step 7: LinkedIn outreach..." | tee -a "$LOG"
python3 /home/ubuntu/nanosoft/linkedin_outreach.py >> "$LOG" 2>&1
echo "[$DATE] LinkedIn done" | tee -a "$LOG"

# === STEP 8: Scan Reddit ===
echo "[$DATE] Step 8: Reddit scan..." | tee -a "$LOG"
timeout 300 python3 /home/ubuntu/nanosoft/reddit_outreach.py >> "$LOG" 2>&1
echo "[$DATE] Reddit done" | tee -a "$LOG"

# === SUMMARY ===
echo "[$DATE] === DAILY PIPELINE COMPLETE ===" | tee -a "$LOG"
