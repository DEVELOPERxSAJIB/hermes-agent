#!/usr/bin/python3
"""Post QUILL draft results to Discord #nexus channel via discord.py."""
import discord
import asyncio
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
now = datetime.now(BD_TZ).strftime("%Y-%m-%d %H:%M BD")

# Read token from .env
token = None
with open('/home/ubuntu/nanosoft/.env') as f:
    for line in f:
        line = line.strip()
        if line.startswith('DISCORD_BOT_TOKEN='):
            token = line.split('=', 1)[1]
            break

if not token:
    print("ERROR: No DISCORD_BOT_TOKEN found in .env")
    exit(1)

# Read drafts
drafts_file = Path('/home/ubuntu/nanosoft/email_drafts.jsonl')
drafts = []
if drafts_file.exists():
    with open(drafts_file) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    drafts.append(json.loads(line))
                except:
                    pass

valid = [d for d in drafts if d.get("is_valid")]
invalid = [d for d in drafts if not d.get("is_valid")]

# Build messages (Discord limit: 2000 chars per message)
def build_messages():
    chunks = []
    
    # Message 1: Header + stats
    pain_categories = {}
    for d in valid:
        pp = d.get("pain_points_used", "unknown")
        key = pp.split("—")[0].strip() if "—" in pp else pp
        pain_categories[key] = pain_categories.get(key, 0) + 1
    
    header = f"## 📧 QUILL Daily Draft Run — {now}\n"
    header += f"**{len(valid)} drafts generated** | {len(invalid)} need review\n\n"
    header += "### 📊 Breakdown by primary pain point:\n"
    for cat, count in sorted(pain_categories.items(), key=lambda x: -x[1]):
        header += f"  • **{cat}**: {count} leads\n"
    header += "\n---\n"
    
    chunks.append(header)
    
    # Messages 2+: Individual drafts (grouped to stay under 2000 chars)
    current = ""
    for i, d in enumerate(valid, 1):
        to = d.get("to", "?")
        company = d.get("company", "?")
        subj = d.get("subject", "?")
        wc = d.get("word_count", 0)
        sl = d.get("subject_length", 0)
        pp = d.get("pain_points_used", "?")
        body = d.get("body", "")
        
        entry = f"**#{i}** — {company}\n"
        entry += f"  📨 `{to}`\n"
        entry += f"  📌 `{subj}` ({sl}ch)\n"
        entry += f"  📝 {wc}w | {pp}\n"
        entry += f"  ```{body[:300]}```\n\n"
        
        if len(current) + len(entry) > 1900:
            chunks.append(current)
            current = ""
        current += entry
    
    if current:
        chunks.append(current)
    
    # Final message: invalid + send instructions
    footer = ""
    if invalid:
        footer += "### ⚠️ Needs Review:\n"
        for d in invalid:
            footer += f"  ✗ {d.get('company','?')} — {d.get('violations',[])}\n"
        footer += "\n"
    
    footer += "---\n"
    footer += "Reply `!send all` to send all emails, or `!send 1,3,5` for specific ones."
    
    chunks.append(footer)
    
    return chunks

CHANNEL_ID = 1504440630452027554
messages = build_messages()

intents = discord.Intents.default()
intents.guilds = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    channel = client.get_channel(CHANNEL_ID)
    if channel is None:
        try:
            channel = await client.fetch_channel(CHANNEL_ID)
        except Exception as e:
            print(f"Cannot fetch channel: {e}")
            await client.close()
            return
    
    try:
        for i, msg in enumerate(messages):
            await channel.send(msg)
            print(f"Message {i+1}/{len(messages)} sent to #{channel.name}")
            await asyncio.sleep(0.5)  # Rate limit safety
        print(f"All {len(messages)} messages sent successfully")
    except Exception as e:
        print(f"Send failed: {e}")
    await client.close()

client.run(token)
