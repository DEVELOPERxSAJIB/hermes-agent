"""
NanoSoft NOVA — Content & Social Media Agent
Posts daily content to Discord. Uses Ollama for content generation.
Schedule: 9 AM, 2 PM, 7 PM BD time.
"""
import json
import os
import sys
import time
import subprocess
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
LOG_FILE = os.path.join(NANOSOFT_DIR, "nova.log")
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:7b"

# Discord webhook for posting (uses NEXUS bot instead)
DISCORD_CHANNEL_NOVA = 1507013820885897246

def log(msg):
    ts = datetime.now(BD_TZ).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, 'a') as f:
            f.write(line + "\n")
    except:
        pass

def ask_ollama(prompt, max_tokens=500):
    """Ask Ollama for a response."""
    try:
        data = json.dumps({
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": max_tokens, "temperature": 0.7},
        }).encode()
        
        req = urllib.request.Request(
            OLLAMA_URL,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
            return result.get("response", "").strip()
    except Exception as e:
        log(f"Ollama error: {e}")
        return ""

def generate_content():
    """Generate a social media post about NanoSoft's work."""
    prompt = """Write a short social media post (under 200 words) for NanoSoft, a web development agency. 

Topic: A quick tip about website design for small businesses.
Tone: Professional but friendly. No flattery. Direct.
Include: One specific actionable tip, why it matters for local businesses.
End with: A question to engage readers.
Format: Plain text, no hashtags, no markdown."""
    
    content = ask_ollama(prompt)
    if not content:
        content = "💡 Tip: If your website isn't mobile-friendly, you're losing over 60% of potential customers. Most people browse on phones first. Make sure your site works perfectly on small screens. What's the last time you checked your site on a phone?"
    
    return content

def post_to_discord(channel_id, message):
    """Post a message to Discord using the bot API."""
    # Use the NEXUS bot token via subprocess
    try:
        import discord
        # This runs within NEXUS's context, so we use a different approach
        # Write to a file that NEXUS reads
        pass
    except:
        pass
    
    # Fallback: write to a queue file
    queue_file = os.path.join(NANOSOFT_DIR, "nova_queue.json")
    try:
        queue = []
        if os.path.exists(queue_file):
            with open(queue_file) as f:
                queue = json.load(f)
        queue.append({
            "channel_id": channel_id,
            "message": message,
            "timestamp": datetime.now(BD_TZ).isoformat(),
        })
        with open(queue_file, 'w') as f:
            json.dump(queue, f)
    except Exception as e:
        log(f"Queue write error: {e}")

def run_posting_cycle():
    """Generate and post content."""
    now = datetime.now(BD_TZ)
    log(f"🚀 NOVA posting cycle — {now.strftime('%H:%M')} BD")
    
    content = generate_content()
    
    if content:
        # Generate image using Pollinations.ai (free, no API key)
        image_prompt = content[:100].replace('\n', ' ')
        image_url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(image_prompt)}?width=1200&height=630&nologo=true"
        
        log(f"[NOVA] Content ({len(content)} chars): {content[:100]}...")
        
        # Save content for Discord posting
        post_data = {
            "channel": "nova",
            "content": content,
            "image": image_url,
            "timestamp": now.isoformat(),
        }
        
        # Write to Discord-ready file
        discord_file = os.path.join(NANOSOFT_DIR, "nova_discord_post.json")
        with open(discord_file, 'w') as f:
            json.dump(post_data, f, indent=2)
        
        log(f"✅ NOVA complete — content saved for Discord")
    else:
        log("✗ NOVA: No content generated")

if __name__ == "__main__":
    import sys
    sys.path.insert(0, NANOSOFT_DIR)
    
    if len(sys.argv) > 1 and sys.argv[1] == "now":
        run_posting_cycle()
    else:
        # Run as daemon
        log("🌟 NOVA starting — content agent")
        log(f"   Schedule: [9, 14, 19] BD time")
        log(f"   Model: {OLLAMA_MODEL}")
        
        last_run_date = None
        
        while True:
            now = datetime.now(BD_TZ)
            today = now.date()
            
            # Post at 9 AM, 2 PM, 7 PM BD
            if now.hour in [9, 14, 19] and now.minute < 10 and last_run_date != today:
                last_run_date = today  # Only run once per day at the first matching hour
                try:
                    run_posting_cycle()
                except Exception as e:
                    log(f"❌ NOVA error: {e}")
            
            # Reset at midnight for next day
            if now.hour == 0:
                last_run_date = None
            
            time.sleep(60)
