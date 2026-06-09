#!/usr/bin/python3
"""
NanoSoft ATLAS — Follow-Up & Reply Tracker Agent
==================================================
Coordinates follow-up emails and tracks replies.

Responsibilities:
1. Check outreach sheet for emails that need follow-ups (Day 3, Day 7)
2. Generate follow-up emails via Ollama
3. Save follow-ups as Gmail drafts
4. Track replies via Gmail API
5. Update CRM with reply status

Usage: python3 atlas_agent.py
"""

import json
import os
import sys
import time
import subprocess
import re
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, '/home/ubuntu/nanosoft')
from crm import NanoSoftCRM

BD_TZ = timezone(timedelta(hours=6))
STATE_FILE = Path("/home/ubuntu/nanosoft/atlas_state.json")
LOG_FILE = Path("/home/ubuntu/nanosoft/atlas.log")

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:3b"

FOLLOWUP_1_DAYS = 3
FOLLOWUP_2_DAYS = 7

GMAIL_TOKEN_FILE = "/home/ubuntu/nanosoft/gmail_token.json"
GMAIL_USER = "nanosoftagency007@gmail.com"


def log(msg):
    ts = datetime.now(BD_TZ).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except:
        pass


def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except:
            pass
    return {
        "last_run": None,
        "followups_sent_today": 0,
        "replies_found_today": 0,
        "followups_sent_week": 0,
        "replies_found_week": 0,
    }


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str))


def ask_ollama(system_prompt, user_message, max_tokens=200):
    try:
        payload = json.dumps({
            "model": OLLAMA_MODEL,
            "prompt": f"{system_prompt}\n\n---\n\n{user_message}",
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": 0.7}
        }).encode()
        req = urllib.request.Request(
            OLLAMA_URL, data=payload,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            text = result.get("response", "").strip()
            text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
            return text if text else ""
    except Exception as e:
        log(f"Ollama error: {e}")
        return ""


def get_gmail_service():
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        if not os.path.exists(GMAIL_TOKEN_FILE):
            return None
        with open(GMAIL_TOKEN_FILE) as f:
            creds_data = json.load(f)
        creds = Credentials.from_authorized_user_info(creds_data)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        return build('gmail', 'v1', credentials=creds)
    except:
        return None


def run_followups():
    """Find emails needing follow-ups and draft them."""
    crm = NanoSoftCRM()
    outreach = crm.get_all_outreach() if hasattr(crm, 'get_all_outreach') else []
    
    now = datetime.now(BD_TZ)
    drafted = 0
    
    for row in outreach:
        draft_status = row.get("draft_status", "")
        if draft_status not in ["drafted", "sent"]:
            continue
        
        # Check if follow-up already exists
        if row.get("followup_1_status") == "drafted" and row.get("followup_2_status") == "drafted":
            continue
        
        # Parse date sent
        date_sent_str = row.get("date_sent", "") or row.get("date_found", "")
        if not date_sent_str:
            continue
        
        try:
            if isinstance(date_sent_str, str):
                date_sent = datetime.strptime(date_sent_str[:10], "%Y-%m-%d")
            else:
                continue
        except:
            continue
        
        days_since = (now.replace(tzinfo=None) - date_sent).days
        company = row.get("company_name", "Unknown")
        
        # Follow-up 1 (Day 3)
        if days_since >= FOLLOWUP_1_DAYS and row.get("followup_1_status") != "drafted":
            log(f"[FUP] Day {days_since}: Follow-up 1 for {company}")
            
            followup_text = ask_ollama(
                "You are writing a brief follow-up email. Short, friendly, no pressure. 2 sentences max.",
                f"Follow up on my previous email to {company}. Subject: quick bump. Keep it casual.",
                max_tokens=150
            )
            
            if not followup_text:
                followup_text = f"Hi — just bumping my previous message. Would a free 15-min audit be useful? — Sajib"
            
            try:
                # Save follow-up to CRM
                row["followup_1_status"] = "drafted"
                row["followup_1_text"] = followup_text[:500]
                row["followup_1_date"] = now.strftime("%Y-%m-%d")
                # Update via CRM
                if hasattr(crm, 'update_outreach'):
                    crm.update_outreach(row.get("lead_id", ""), row)
                drafted += 1
                time.sleep(2)
            except Exception as e:
                log(f"[FUP] Save error: {e}")
        
        # Follow-up 2 (Day 7)
        if days_since >= FOLLOWUP_2_DAYS and row.get("followup_2_status") != "drafted":
            log(f"[FUP] Day {days_since}: Follow-up 2 for {company}")
            
            followup_text = ask_ollama(
                "You are writing a final follow-up. Brief, no pressure. 1-2 sentences.",
                f"Final follow-up to {company}. Close the loop — if timing isn't right, no worries.",
                max_tokens=100
            )
            
            if not followup_text:
                followup_text = f"No worries if the timing isn't right. Good luck with everything! — Sajib"
            
            try:
                row["followup_2_status"] = "drafted"
                row["followup_2_text"] = followup_text[:500]
                row["followup_2_date"] = now.strftime("%Y-%m-%d")
                if hasattr(crm, 'update_outreach'):
                    crm.update_outreach(row.get("lead_id", ""), row)
                drafted += 1
                time.sleep(2)
            except Exception as e:
                log(f"[FUP] Save error: {e}")
    
    return drafted


def run_reply_tracking():
    """Check Gmail for replies from outreach contacts."""
    service = get_gmail_service()
    if not service:
        log("[REPLY] Gmail not configured")
        return 0
    
    crm = NanoSoftCRM()
    outreach = crm.get_all_outreach() if hasattr(crm, 'get_all_outreach') else []
    
    # Get list of contact emails we've sent to
    sent_emails = set()
    for row in outreach:
        email = row.get("email", "")
        if email and "@" in email:
            sent_emails.add(email.lower())
    
    if not sent_emails:
        return 0
    
    found = 0
    try:
        # Search for replies
        for contact_email in list(sent_emails)[:20]:  # Max 20 per run
            query = f"from:{contact_email} newer_than:7d"
            try:
                results = service.users().messages().list(
                    userId='me', q=query, maxResults=5
                ).execute()
                messages = results.get('messages', [])
                if messages:
                    log(f"[REPLY] Found reply from {contact_email}")
                    found += 1
                    # Update CRM
                    for msg in messages:
                        msg_data = service.users().messages().get(
                            userId='me', id=msg['id'], format='metadata'
                        ).execute()
                        # Mark as replied in outreach sheet
                        for row in outreach:
                            if row.get("email","").lower() == contact_email:
                                row["reply_received"] = "yes"
                                row["reply_date"] = datetime.now(BD_TZ).strftime("%Y-%m-%d")
                                if hasattr(crm, 'update_outreach'):
                                    crm.update_outreach(row.get("lead_id", ""), row)
                                break
            except Exception as e:
                log(f"[REPLY] Search error for {contact_email}: {e}")
                continue
    except Exception as e:
        log(f"[REPLY] Error: {e}")
    
    return found


def run_atlas():
    """Main loop — run follow-ups and reply tracking every 30 minutes."""
    log("🗺️ ATLAS starting — follow-up & reply tracker")
    
    while True:
        try:
            now = datetime.now(BD_TZ)
            state = load_state()
            
            log(f"\n── ATLAS cycle | {now.strftime('%H:%M')} BD ──")
            
            # Follow-ups
            followups = run_followups()
            state["followups_sent_today"] += followups
            
            # Reply tracking
            replies = run_reply_tracking()
            state["replies_found_today"] += replies
            
            state["last_run"] = now.isoformat()
            save_state(state)
            
            log(f"📊 Follow-ups drafted: {followups}, Replies found: {replies}")
            
        except Exception as e:
            log(f"❌ ATLAS error: {e}")
        
        # Run every 30 minutes
        time.sleep(1800)


if __name__ == "__main__":
    run_atlas()
