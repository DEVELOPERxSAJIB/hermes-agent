#!/bin/bash
# NanoSoft Pipeline Runner v2
# Run as: bash pipeline_run.sh [scout|enrich|judge|send-t1|send-t2|send-t3|send-t4|reply|full]

STEP="${1:-full}"
DIR="/home/ubuntu/nanosoft"
LOG="$DIR/pipeline_logs"
mkdir -p "$LOG"

# Random delay 0-60s to spread out API calls (avoid Google Sheets 429)
SLEEP=$((RANDOM % 60))
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Random delay: ${SLEEP}s" >> "$LOG/${STEP}.log"
sleep $SLEEP

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting $STEP" >> "$LOG/${STEP}.log"

case $STEP in
  scout)
    cd "$DIR" && timeout 900 python3 -u scout_wl_v5.py >> "$LOG/scout.log" 2>&1
    ;;
  enrich)
    cd "$DIR" && timeout 600 python3 -u enrich_wl_leads.py >> "$LOG/enrich.log" 2>&1
    ;;
  judge)
    cd "$DIR" && timeout 120 python3 -u judge_wl.py >> "$LOG/judge.log" 2>&1
    ;;
  send-t1)
    if [ -f "$DIR/GMAIL_TOKEN_DEAD" ]; then
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] SKIP: Gmail token dead" >> "$LOG/send_t1.log"
    else
      cd "$DIR" && timeout 1800 python3 -u quill_wl.py send -t T1 --limit 50 >> "$LOG/send_t1.log" 2>&1
    fi
    ;;
  send-t2)
    if [ -f "$DIR/GMAIL_TOKEN_DEAD" ]; then
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] SKIP: Gmail token dead" >> "$LOG/send_t2.log"
    else
      cd "$DIR" && timeout 1800 python3 -u quill_wl.py send -t T2 --limit 50 >> "$LOG/send_t2.log" 2>&1
    fi
    ;;
  send-t3)
    if [ -f "$DIR/GMAIL_TOKEN_DEAD" ]; then
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] SKIP: Gmail token dead" >> "$LOG/send_t3.log"
    else
      cd "$DIR" && timeout 1800 python3 -u quill_wl.py send -t T3 --limit 50 >> "$LOG/send_t3.log" 2>&1
    fi
    ;;
  send-t4)
    if [ -f "$DIR/GMAIL_TOKEN_DEAD" ]; then
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] SKIP: Gmail token dead" >> "$LOG/send_t4.log"
    else
      cd "$DIR" && timeout 1800 python3 -u quill_wl.py send -t T4 --limit 50 >> "$LOG/send_t4.log" 2>&1
    fi
    ;;
  reply)
    cd "$DIR" && timeout 120 python3 -u reply_monitor_wl.py >> "$LOG/reply.log" 2>&1
    ;;
  full)
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] FULL PIPELINE START" >> "$LOG/full.log"
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] STEP: scout" >> "$LOG/full.log"
    cd "$DIR" && timeout 900 python3 -u scout_wl_v5.py >> "$LOG/scout.log" 2>&1
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] STEP: enrich" >> "$LOG/full.log"
    cd "$DIR" && timeout 600 python3 -u enrich_wl_leads.py >> "$LOG/enrich.log" 2>&1
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] STEP: judge" >> "$LOG/full.log"
    cd "$DIR" && timeout 120 python3 -u judge_wl.py >> "$LOG/judge.log" 2>&1
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] STEP: send-t1" >> "$LOG/full.log"
    cd "$DIR" && timeout 1800 python3 -u quill_wl.py send -t T1 --limit 50 >> "$LOG/send_t1.log" 2>&1
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] STEP: send-t2" >> "$LOG/full.log"
    cd "$DIR" && timeout 1800 python3 -u quill_wl.py send -t T2 --limit 50 >> "$LOG/send_t2.log" 2>&1
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] STEP: reply" >> "$LOG/full.log"
    cd "$DIR" && timeout 120 python3 -u reply_monitor_wl.py >> "$LOG/reply.log" 2>&1
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] FULL PIPELINE COMPLETE" >> "$LOG/full.log"
    ;;
esac

EXIT_CODE=$?
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Done $STEP (exit: $EXIT_CODE)" >> "$LOG/${STEP}.log"
exit $EXIT_CODE
