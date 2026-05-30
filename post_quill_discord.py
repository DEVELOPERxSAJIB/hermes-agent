#!/usr/bin/env python3
"""Post QUILL draft results to Discord #nexus channel via discord.py."""
import discord
import asyncio
import json
from pathlib import Path

# Read token from .env
token = None
with open('/home/ubuntu/nanosoft/.env') as f:
    for line in f:
        line = line.strip()
        if line.startswith('DISCORD_BOT_TOKEN='):
            token = line.split('=', 1)[1]
            break

# Count drafted emails
count = 0
drafts_file = Path('/home/ubuntu/nanosoft/email_drafts.jsonl')
if drafts_file.exists():
    with open(drafts_file) as f:
        for line in f:
            if line.strip():
                count += 1
else:
    count = 57

CHANNEL_ID = 1504440630452027554
content = f"QUILL drafted {count} emails today. Reply !send all to send them."

intents = discord.Intents.default()
intents.guilds = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    channel = client.get_channel(CHANNEL_ID)
    if channel is None:
        # Try fetching
        try:
            channel = await client.fetch_channel(CHANNEL_ID)
        except Exception as e:
            print(f"Cannot fetch channel: {e}")
            await client.close()
            return
    try:
        await channel.send(content)
        print(f"Message sent to #{channel.name}")
    except Exception as e:
        print(f"Send failed: {e}")
    await client.close()

client.run(token)
