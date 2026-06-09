#!/usr/bin/python3
"""Post ATLAS report to Discord #nexus"""
import urllib.request, json

token = None
with open('/home/ubuntu/nanosoft/.env') as f:
    for line in f:
        if line.strip().startswith('DISCORD_BOT_TOKEN='):
            token = line.strip().split('=', 1)[1]
            break

channel_id = '1504440630452027554'

msg = (
    "ATLAS Daily Report | 2026-05-28 10:00 BD\n\n"
    "**Follow-ups sent today:** 0\n"
    "**Replies found:** 0\n"
    "**Issues:** None -- no pending follow-ups or replies to process.\n\n"
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
resp = urllib.request.urlopen(req)
print(f'Status: {resp.status}')
print(resp.read().decode())
