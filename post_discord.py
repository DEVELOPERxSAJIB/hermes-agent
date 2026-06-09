#!/usr/bin/python3
"""Post a message to a Discord channel using bot token from .env"""
import os, sys, json, requests

env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, val = line.split('=', 1)
            os.environ.setdefault(key, val)

token = os.environ.get("DISCORD_BOT_TOKEN", "")
channel_id = sys.argv[1] if len(sys.argv) > 1 else "1504440630452027554"
message = sys.argv[2] if len(sys.argv) > 2 else "Hello from QUILL"

url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
headers = {"Authorization": f"Bot {token}", "Content-Type": "application/json"}
payload = {"content": message}

resp = requests.post(url, headers=headers, json=payload, timeout=30)
print(f"Status: {resp.status_code}")
print(resp.text)
if resp.status_code == 200:
    print("SUCCESS")
else:
    print("FAILED")
    sys.exit(1)
