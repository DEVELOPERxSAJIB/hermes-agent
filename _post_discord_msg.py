#!/usr/bin/env python3
"""Post a message to Discord channel via HTTP API."""
import sys
import json
import urllib.request

def main():
    if len(sys.argv) < 3:
        print("Usage: _post_discord_msg.py <channel_id> <message>")
        sys.exit(1)

    channel_id = sys.argv[1]
    message_text = sys.argv[2]

    token = None
    with open('/home/ubuntu/nanosoft/.env', 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('DISCORD_BOT_TOKEN='):
                token = line.split('=', 1)[1]
                break

    if not token:
        print("ERROR: No DISCORD_BOT_TOKEN found in .env")
        sys.exit(1)

    payload = json.dumps({"content": message_text}).encode()
    req = urllib.request.Request(
        f"https://discord.com/api/v10/channels/{channel_id}/messages",
        data=payload,
        headers={
            "Authorization": "Bot " + token,
            "Content-Type": "application/json"
        },
        method="POST"
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        print("SUCCESS: HTTP " + str(resp.status) + " - posted to channel " + channel_id)
    except Exception as e:
        print("ERROR: " + str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()
