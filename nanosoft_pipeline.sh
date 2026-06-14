#!/bin/bash
# NanoSoft Pipeline Runner v4
# Bulletproof: explicit PATH, no env dependency, proper error reporting
# Run as: bash nanosoft_pipeline.sh [scout|enrich|judge|send-t1|send-t2|send-t3|send-t4|reply|status|full]

export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

STEP="${1:-full}"
DIR="/home/ubuntu/nanosoft"
LOG="$DIR/pipeline_logs"
mkdir -p "$LOG"

TODAY=$(date '+%Y-%m-%d')
LOGFILE="$LOG/${STEP}_${TODAY}.log"

# Random stagger: 0-60s (reduce collision between parallel crons)
SLEEP=$((RANDOM % 61))
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PID=$$ STEP=$STEP STAGGER=${SLEEP}s" >> "$LOGFILE"
sleep $SLEEP

echo "[$(date '+%Y-%m-%d %H:%M:%S')] START $STEP" >> "$LOGFILE"

# Check Gmail token before send steps
check_gmail() {
    if [ -f "$DIR/GMAIL_TOKEN_DEAD" ]; then
        echo "GMAIL_TOKEN_DEAD flag found. Skip send." >> "$LOGFILE"
        return 1
    fi
    return 0
}

# Run a Python step with error capture
run_step() {
    local script="$1"
    local timeout="${2:-600}"
    local extra_args="${3:-}"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] RUN: python3 $script $extra_args" >> "$LOGFILE"
    cd "$DIR" && timeout "$timeout" /usr/bin/python3 -u $script $extra_args >> "$LOGFILE" 2>&1
    local exit=$?
    if [ $exit -eq 0 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] OK: $script (exit 0)" >> "$LOGFILE"
    elif [ $exit -eq 124 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] TIMEOUT: $script (exit 124 after ${timeout}s)" >> "$LOGFILE"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] FAIL: $script (exit $exit)" >> "$LOGFILE"
    fi
    return $exit
}

case $STEP in
  scout)
    run_step "scout_wl_v5.py" 900
    ;;
  enrich)
    run_step "enrich_wl_leads.py" 600
    ;;
  judge)
    run_step "judge_wl.py" 120
    ;;
  send-t1)
    if check_gmail; then
      run_step "quill_wl.py" 1800 "send --template T1"
    fi
    ;;
  send-t2)
    if check_gmail; then
      run_step "quill_wl.py" 1800 "send --template T2"
    fi
    ;;
  send-t3)
    if check_gmail; then
      run_step "quill_wl.py" 1800 "send --template T3"
    fi
    ;;
  send-t4)
    if check_gmail; then
      run_step "quill_wl.py" 1800 "send --template T4"
    fi
    ;;
  reply)
    run_step "reply_monitor_wl.py" 120
    ;;
  status)
    # Quick status check: count leads, replies, last send
    run_step "daily_report_cron.py" 60
    ;;
  daily-20)
    # Judge unjudged leads, mark top 20 as Qualified, send T1 to them
    run_step "daily_20_pipeline.py" 3600
    ;;
  full)
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] FULL PIPELINE START" >> "$LOGFILE"
    for S in scout enrich judge send-t1 reply; do
      bash "$0" "$S"
      EC=$?
      if [ $EC -ne 0 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] STEP FAILED: $S (exit $EC)" >> "$LOGFILE"
      fi
      sleep 15
    done
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] FULL PIPELINE COMPLETE" >> "$LOGFILE"
    ;;
  *)
    echo "Unknown step: $STEP"
    exit 1
    ;;
esac

EXIT_CODE=$?
echo "[$(date '+%Y-%m-%d %H:%M:%S')] END $STEP (exit: $EXIT_CODE)" >> "$LOGFILE"
exit $EXIT_CODE
