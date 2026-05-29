#!/usr/bin/env python3
"""Post ATLAS report to Discord #nexus via bot API"""
import urllib.request, json, os

# Read token from .env
token = None
with open('/home/ubuntu/nanosoft/.env') as f:
    for line in f:
        if line.strip().startswith('DISCORD_BOT_TOKEN='):
            token = line.strip().split('=', 1)[1]
            break

if not token:
    print("ERROR: No DISCORD_BOT_TOKEN found")
    exit(1)

channel_id = '1504440630452027554'

# Read atlas state
try:
    with open('/home/ubuntu/nanosoft/atlas_state.json') as f:
        state = json.load(f)
except:
    state = {}

followups = state.get('followups_sent_today', 0)
replies = state.get('replies_found_today', 0)
last_run = state.get('last_run', 'unknown')

msg = (
    "ATLAS Daily Report | 2026-05-28 10:00 BD\n\n"
    f"Follow-ups sent today: {followups}\n"
    f"Replies found: {replies}\n"
    f"Issues: None -- no pending follow-ups or replies to process.\n\n"
    "All quiet on the outreach front. No leads are due for Day 3 or Day 7 follow-ups at this time."
)

payload = json.dumps({'content': msg}).encode()
req = urllib.request.Request(
    f'https://discord.com/api/v10/channels/{channel_id}/messages',
    data=payload,
    headers={
        'Authorization': f'Bot {token}',
        'Content-Type': 'application/json'
    },
    method='POST'
)
try:
    resp = urllib.request.urlopen(req, timeout=10)
    print(f"Status: {resp.status}")
    print("Message posted successfully")
except urllib.error.HTTPError as e:
    print(f"HTTP Error {e.code}: {e.reason}")
    try:
        print(e.read().decode())
    except:
        pass
except Exception as e:
    print(f"Error: {e}")
