#!/bin/bash
# NanoSoft Auto-Pilot Watchdog
# Runs the full pipeline directly without LLM dependency
# This is a backup in case the LLM-driven cron fails

cd /home/ubuntu/nanosoft

echo "[$(date)] Auto-Pilot Watchdog starting..." >> /home/ubuntu/nanosoft/watchdog.log

# Step 1: Scout
echo "[$(date)] Step 1: Scouting..." >> /home/ubuntu/nanosoft/watchdog.log
python3 -u scout_wl_v4.py >> /home/ubuntu/nanosoft/watchdog.log 2>&1
SCOUT_EXIT=$?

# Step 2: Enrich (only new leads)
echo "[$(date)] Step 2: Enriching..." >> /home/ubuntu/nanosoft/watchdog.log
python3 -u enrich_wl_leads.py >> /home/ubuntu/nanosoft/watchdog.log 2>&1
ENRICH_EXIT=$?

# Step 3: Judge
echo "[$(date)] Step 3: Judging..." >> /home/ubuntu/nanosoft/watchdog.log
python3 -u judge_wl.py >> /home/ubuntu/nanosoft/watchdog.log 2>&1
JUDGE_EXIT=$?

# Step 4: Send T1 (only qualified)
echo "[$(date)] Step 4: Sending T1..." >> /home/ubuntu/nanosoft/watchdog.log
python3 -u quill_wl.py send -t T1 >> /home/ubuntu/nanosoft/watchdog.log 2>&1
SEND_EXIT=$?

# Step 5: Check replies
echo "[$(date)] Step 5: Checking replies..." >> /home/ubuntu/nanosoft/watchdog.log
python3 -u reply_monitor_wl.py >> /home/ubuntu/nanosoft/watchdog.log 2>&1
REPLY_EXIT=$?

echo "[$(date)] Pipeline complete. Scout=$SCOUT_EXIT Enrich=$ENRICH_EXIT Judge=$JUDGE_EXIT Send=$SEND_EXIT Reply=$REPLY_EXIT" >> /home/ubuntu/nanosoft/watchdog.log

# Count sent today
TODAY=$(TZ='Asia/Dhaka' date +%Y-%m-%d)
SENT_TODAY=$(grep -c "$TODAY" /home/ubuntu/nanosoft/emails_sent_wl.jsonl 2>/dev/null || echo "0")
echo "[$(date)] Sent today: $SENT_TODAY / 80 cap" >> /home/ubuntu/nanosoft/watchdog.log
