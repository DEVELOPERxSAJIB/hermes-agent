#!/usr/bin/python3
"""
NEXUS — Chief Executive Agent for NanoSoft
Persistent service: monitors, coordinates, and optimizes all agents.
Runs 24/7 via systemd. Communicates via Discord.

Model: deepseek-r1:14b via Ollama (local, no API limits)
Fallback: qwen2.5:7b if r1:14b unavailable
"""

import discord
from discord.ext import commands, tasks
import json
import os
import sys
import subprocess
import asyncio
import re
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ─── CONFIG ────────────────────────────────────────────────

BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
if not BOT_TOKEN:
    raise ValueError("DISCORD_BOT_TOKEN environment variable not set")
GUILD_ID = 1504439651056877568
CHAIRMAN_ID = 660182301258547222

# Channel IDs
CHANNEL_NEXUS = 1504440630452027554
CHANNEL_SCOUT = 1506083424270549102
CHANNEL_JUDGE = 1506084097863188720
CHANNEL_QUILL = 1506084457894117406
CHANNEL_HAWK = 1506139641336828048
CHANNEL_NOVA = 1507013820885897246

# Ollama — use qwen2.5:7b as primary (fast, good reasoning)
# deepseek-r1:14b is too heavy for this machine (9GB+ RAM, 277% CPU)
OLLAMA_MODEL = "qwen2.5:7b"

# Paths
NANOSOFT_DIR = Path("/home/ubuntu/nanosoft")
STATE_FILE = NANOSOFT_DIR / "nexus_state.json"
IMPROVEMENTS_FILE = NANOSOFT_DIR / "nexus_improvements.json"
LOG_FILE = NANOSOFT_DIR / "nexus.log"

# Timezone
BD_TZ = timezone(timedelta(hours=6))

# ─── STATE ──────────────────────────────────────────────────

def load_state() -> dict:
    default = {
        "qualified_leads_today": 0,
        "emails_sent_today": 0,
        "replies_today": 0,
        "calls_booked_today": 0,
        "revenue_today": 0.0,
        "content_posted_today": 0,
        "jobs_applied_today": 0,
        "qualified_leads_week": 0,
        "emails_sent_week": 0,
        "replies_week": 0,
        "calls_booked_week": 0,
        "revenue_week": 0.0,
        "content_posted_week": 0,
        "jobs_applied_week": 0,
        "last_brief_date": "",
        "last_weekly_review": "",
        "last_improvement_date": "",
        "today_improvement": "",
        "agent_status": {
            "SCOUT": {"last_run": None, "leads_found": 0, "status": "unknown"},
            "JUDGE": {"last_run": None, "qual_rate": 0, "status": "unknown"},
            "QUILL": {"last_run": None, "emails_written": 0, "approval_rate": 0, "status": "unknown"},
            "HAWK": {"last_run": None, "jobs_found": 0, "proposals_sent": 0, "status": "unknown"},
            "NOVA": {"last_run": None, "posts_published": 0, "status": "unknown"},
            "ATLAS": {"last_run": None, "follow_ups_managed": 0, "status": "unknown"},
        },
        "start_date": datetime.now(BD_TZ).strftime("%Y-%m-%d"),
    }
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text())
            for k, v in default.items():
                if k not in data:
                    data[k] = v
            return data
        except:
            pass
    return default


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str))


def load_improvements() -> list:
    if IMPROVEMENTS_FILE.exists():
        try:
            return json.loads(IMPROVEMENTS_FILE.read_text())
        except:
            pass
    return []


def save_improvements(improvements: list):
    IMPROVEMENTS_FILE.write_text(json.dumps(improvements, indent=2, default=str))


def log(msg: str):
    ts = datetime.now(BD_TZ).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except:
        pass


# ─── OLLAMA ─────────────────────────────────────────────────

def ask_ollama(system_prompt: str, user_message: str, max_tokens: int = 2000) -> str:
    """Query local Ollama via /api/chat. Strips <think> tags from deepseek-r1."""
    model = OLLAMA_MODEL
    try:
        result = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=10
        )
        if "deepseek-r1:14b" not in result.stdout and "qwen2.5:7b" in result.stdout:
            model = "qwen2.5:7b"
    except:
        pass

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": max_tokens},
    }
    try:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            "http://localhost:11434/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        # qwen2.5:7b is fast — 60s timeout is plenty
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
            text = result.get("message", {}).get("content", "")
            text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
            return text if text else "(empty response)"
    except Exception as e:
        log(f"Ollama error: {e}")
        return f"(Ollama error: {e})"


# ─── SYSTEM PROMPT ──────────────────────────────────────────

SYSTEM_PROMPT = """You are NEXUS, CEO of NanoSoft's AI agent team.
You serve Chairman Md Sajib. Your mission: $1,000/month recurring revenue.

Rules:
- Be direct. No warmup. No filler.
- Disagree first. Validate only after evidence.
- Never say "great idea", "that makes sense", "absolutely", "good thinking".
- Find the weakest point in every idea before acknowledging any strength.
- If something is wrong, say it in the first sentence.
- If the answer is no, say no first.
- The more confident the Chairman sounds, the harder you push back.
- When you agree, add something new — never restate his point.
- Data first. Opinion second. Always.

You command: SCOUT, JUDGE, QUILL, HAWK, NOVA, ATLAS.

Performance minimums:
- Leads qualified/week: >=20
- Emails sent/week: >=30
- Reply rate: >=3%
- Job applications/week: >=15
- Social posts/week: >=21
- Follow-ups on schedule: 100%

This is do or die. Act like it."""


# ─── AGENT MONITORING ───────────────────────────────────────

def check_agents(state: dict) -> dict:
    now = datetime.now(BD_TZ)
    checks = {
        "SCOUT": ("scout_agent.py", "scout.log"),
        "JUDGE": ("judge_agent.py", None),
        "QUILL": ("quill_agent.py", None),
        "HAWK": ("hawk_agent.py", "hawk.log"),
        "NOVA": ("nova_agent.py", "nova.log"),
        "ATLAS": ("atlas_agent.py", "atlas.log"),
    }
    for agent, (proc, logfile) in checks.items():
        st = state["agent_status"].get(agent, {})
        if proc:
            try:
                r = subprocess.run(["pgrep", "-f", proc], capture_output=True, timeout=5)
                st["status"] = "running" if r.returncode == 0 else "stopped"
            except:
                st["status"] = "unknown"
        else:
            st["status"] = "not_deployed"

        if logfile:
            lp = NANOSOFT_DIR / logfile
            if lp.exists():
                mt = datetime.fromtimestamp(lp.stat().st_mtime, tz=BD_TZ)
                st["last_log"] = mt.strftime("%Y-%m-%d %H:%M")
                st["recent"] = (now - mt).total_seconds() < 1800
        state["agent_status"][agent] = st
    return state


def restart_agent(agent: str) -> bool:
    """Restart a stopped agent via systemd. Returns True if restart command issued."""
    restart_map = {
        "SCOUT": "scout.service",
        "HAWK": "hawk.service",
        "NOVA": "nova.service",
        "ATLAS": "atlas.service",
        "PIPELINE": "pipeline-v3.service",
    }
    if agent not in restart_map:
        return False
    try:
        subprocess.run(
            ["sudo", "systemctl", "restart", restart_map[agent]],
            capture_output=True, timeout=15
        )
        log(f"Restart command issued for {agent} ({restart_map[agent]})")
        return True
    except Exception as e:
        log(f"Failed to restart {agent}: {e}")
        return False


def get_pipeline_state() -> dict:
    """Read the current pipeline state."""
    sf = NANOSOFT_DIR / "pipeline_v3_state.json"
    if not sf.exists():
        sf = NANOSOFT_DIR / "pipeline_state.json"
    if sf.exists():
        try:
            return json.loads(sf.read_text())
        except:
            pass
    return {}


def load_nova_state() -> dict:
    sf = NANOSOFT_DIR / "nova_state.json"
    if sf.exists():
        try:
            return json.loads(sf.read_text())
        except:
            pass
    return {}


def load_atlas_state() -> dict:
    sf = NANOSOFT_DIR / "atlas_state.json"
    if sf.exists():
        try:
            return json.loads(sf.read_text())
        except:
            pass
    return {}


def get_crm_stats() -> dict:
    """Get CRM statistics for reporting."""
    try:
        sys.path.insert(0, '/home/ubuntu/nanosoft')
        from crm import NanoSoftCRM
        crm = NanoSoftCRM()
        leads = crm.get_all_leads()
        qualified = [l for l in leads if int(l.get("judge_score", 0)) >= 7]
        outreach = crm.get_all_outreach() if hasattr(crm, 'get_all_outreach') else []
        drafted = [o for o in outreach if o.get("draft_status") == "drafted"]
        return {
            "total_leads": len(leads),
            "qualified": len(qualified),
            "drafted": len(drafted),
        }
    except Exception as e:
        log(f"CRM stats error: {e}")
        return {"total_leads": 0, "qualified": 0, "drafted": 0}


def count_qualified_today() -> int:
    state = get_pipeline_state()
    return state.get("qualified_count", 0)


# ─── DISCORD BOT ────────────────────────────────────────────

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)
nexus_state = load_state()


@bot.event
async def on_ready():
    log(f"NEXUS online as {bot.user}")
    guild = bot.get_guild(GUILD_ID)
    if guild:
        for ch_id, name in [
            (CHANNEL_NEXUS, "NEXUS"), (CHANNEL_SCOUT, "Scout"),
            (CHANNEL_JUDGE, "Judge"), (CHANNEL_QUILL, "Quill"), (CHANNEL_HAWK, "HAWK"),
        ]:
            ch = guild.get_channel(ch_id)
            log(f"   {name}: {'#' + ch.name if ch else 'NOT FOUND'}")

    if not agent_monitor.is_running():
        agent_monitor.start()
    if not daily_brief_task.is_running():
        daily_brief_task.start()
    if not daily_improvement_task.is_running():
        daily_improvement_task.start()
    if not weekly_review_task.is_running():
        weekly_review_task.start()

    if guild:
        ch = guild.get_channel(CHANNEL_NEXUS)
        if ch:
            embed = discord.Embed(
                title="⚡ NEXUS ONLINE",
                description="CEO agent initialized. All systems monitored.",
                color=0xff4444, timestamp=datetime.now(BD_TZ),
            )
            embed.add_field(name="Model", value=OLLAMA_MODEL, inline=True)
            embed.add_field(name="Goal", value="$1,000/month", inline=True)
            embed.set_footer(text="Do or die.")
            await ch.send(embed=embed)


# ─── BACKGROUND TASKS ───────────────────────────────────────

@tasks.loop(minutes=5)
async def agent_monitor():
    global nexus_state
    now = datetime.now(BD_TZ)
    nexus_state = check_agents(nexus_state)
    nexus_state["qualified_leads_today"] = count_qualified_today()
    save_state(nexus_state)

    ch = bot.get_channel(CHANNEL_NEXUS)
    if not ch:
        return

    # Cooldown: don't restart same agent more than once per 30 minutes
    for agent in ["SCOUT", "HAWK", "NOVA", "ATLAS", "PIPELINE"]:
        if nexus_state["agent_status"].get(agent, {}).get("status") == "stopped":
            # Check cooldown
            last_restart = nexus_state.get(f"last_restart_{agent}")
            if last_restart:
                try:
                    last_dt = datetime.fromisoformat(last_restart)
                    if (now - last_dt).total_seconds() < 1800:  # 30 min cooldown
                        continue
                except:
                    pass
            # Try auto-restart
            restarted = restart_agent(agent)
            nexus_state[f"last_restart_{agent}"] = now.isoformat()
            save_state(nexus_state)
            if restarted:
                # Only alert on first restart, not every 5 minutes
                embed = discord.Embed(
                    title=f"🚨 {agent} IS DOWN",
                    description=f"Auto-restart triggered. Will retry in 30 min if still down.",
                    color=0xffaa00,
                    timestamp=datetime.now(BD_TZ),
                )
                await ch.send(embed=embed)
                log(f"ALERT: {agent} down — restart=ok")
            else:
                embed = discord.Embed(
                    title=f"🚨 {agent} IS DOWN",
                    description=f"Auto-restart FAILED — manual intervention needed.",
                    color=0xff0000,
                    timestamp=datetime.now(BD_TZ),
                )
                await ch.send(embed=embed)
                log(f"ALERT: {agent} down — restart=failed")


@agent_monitor.before_loop
async def _bw_monitor():
    await bot.wait_until_ready()


@tasks.loop(minutes=1)
async def daily_brief_task():
    now = datetime.now(BD_TZ)
    # Fire between 8:00-8:59 AM BD (wider window to avoid missing it)
    if now.hour != 8:
        return
    today = now.strftime("%Y-%m-%d")
    if nexus_state.get("last_brief_date") == today:
        return

    ch = bot.get_channel(CHANNEL_NEXUS)
    if not ch:
        return

    nexus_state["qualified_leads_today"] = count_qualified_today()
    revenue = nexus_state.get("revenue_week", 0)
    pct = min(100, round(revenue / 10, 1)) if revenue else 0
    day = now.day
    days_left = 30 - day
    start = datetime.strptime(nexus_state.get("start_date", today), "%Y-%m-%d")
    days_since = (now - start).days

    improvements = load_improvements()
    what_worked = "No improvements logged yet."
    if improvements:
        latest = improvements[-1]
        what_worked = f"{latest.get('change', '')[:100]} — {latest.get('result', 'pending')}"

    what_failed = "No critical failures."
    if nexus_state.get("qualified_leads_week", 0) < 20:
        what_failed = f"Only {nexus_state.get('qualified_leads_week', 0)} qualified leads — need 20"

    expected = (day / 30) * 1000
    if revenue < expected * 0.5:
        cold_truth = f"CRITICAL: ${revenue} vs ${expected:.0f} expected. Failing."
    elif revenue < expected:
        cold_truth = f"Behind: ${revenue} vs ${expected:.0f} expected."
    else:
        cold_truth = f"On pace: ${revenue} vs ${expected:.0f} expected."

    agent_lines = []
    for a, s in nexus_state.get("agent_status", {}).items():
        icon = "🟢" if s.get("status") == "running" else "🔴" if s.get("status") == "stopped" else "⚪"
        agent_lines.append(f"{icon} {a} → {s.get('status', '?')}")

    threats = []
    if nexus_state.get("revenue_week", 0) == 0:
        threats.append("ZERO revenue — existential threat")
    for a in ["SCOUT", "HAWK"]:
        if nexus_state["agent_status"].get(a, {}).get("status") == "stopped":
            threats.append(f"{a} is DOWN")
    threat = threats[0] if threats else "No immediate threats."

    brief = f"""⚡️ NEXUS BRIEF — {today}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GOAL: $1,000/month | STATUS: {pct}% there
Days since start: {days_since} | Days left: {days_left}

LAST 7 DAYS:
Leads qualified: {nexus_state.get('qualified_leads_week', 0)}
Emails sent: {nexus_state.get('emails_sent_week', 0)}
Replies: {nexus_state.get('replies_week', 0)}
Revenue: ${revenue}

WHAT WORKED:
{what_worked}

WHAT FAILED:
{what_failed}

COLD TRUTH:
{cold_truth}

AGENT STATUS:
{chr(10).join(agent_lines)}

CURRENT THREAT:
{threat}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

    await ch.send(brief)
    nexus_state["last_brief_date"] = today
    save_state(nexus_state)
    log(f"Brief posted {today}")


@daily_brief_task.before_loop
async def _bw_brief():
    await bot.wait_until_ready()


@tasks.loop(minutes=1)
async def weekly_review_task():
    now = datetime.now(BD_TZ)
    if now.weekday() != 0 or now.hour != 9 or now.minute > 4:
        return
    today = now.strftime("%Y-%m-%d")
    if nexus_state.get("last_weekly_review") == today:
        return

    ch = bot.get_channel(CHANNEL_NEXUS)
    if not ch:
        return

    revenue = nexus_state.get("revenue_week", 0)
    pct = min(100, round(revenue / 10, 1)) if revenue else 0
    on_track = "YES" if pct >= (now.day / 30 * 100) else "NO"

    improvements = load_improvements()
    imp_lines = []
    for i, imp in enumerate(improvements[-7:], 1):
        imp_lines.append(f"Day {i}: {imp.get('change', '')[:80]} → {imp.get('result', 'pending')}")
    imp_text = "\n".join(imp_lines) if imp_lines else "None logged."

    review = f"""📋 NEXUS WEEKLY REVIEW — {today}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GOAL: ${revenue} of $1,000 ({pct}%) | On track: {on_track}

THIS WEEK:
Leads qualified: {nexus_state.get('qualified_leads_week', 0)} (target: 20)
Emails sent: {nexus_state.get('emails_sent_week', 0)} (target: 30)
Revenue: ${revenue}

1% IMPROVEMENTS:
{imp_text}

NEXT WEEK TARGETS: Leads: 50 | Emails: 30 | Jobs: 15
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

    await ch.send(review)
    nexus_state["last_weekly_review"] = today
    save_state(nexus_state)
    log(f"Weekly review posted {today}")


@weekly_review_task.before_loop
async def _bw_weekly():
    await bot.wait_until_ready()


@tasks.loop(minutes=1)
async def daily_improvement_task():
    """Auto-generate 1% improvement daily at 9:00 AM BD.
    Uses rule-based analysis (no Ollama needed) for reliability."""
    now = datetime.now(BD_TZ)
    if now.hour != 9 or now.minute > 5:
        return
    today = now.strftime("%Y-%m-%d")
    if nexus_state.get("last_improvement_date") == today:
        return

    ch = bot.get_channel(CHANNEL_NEXUS)
    if not ch:
        return

    # Gather current state
    pipeline_state = get_pipeline_state()
    crm_stats = get_crm_stats()

    qualified = pipeline_state.get("qualified_count", 0)
    raw = pipeline_state.get("raw_scraped", 0)
    rejected = pipeline_state.get("rejected", 0)
    emails_drafted = pipeline_state.get("emails_drafted", 0)
    crm_total = crm_stats.get("total_leads", 0)

    # Rule-based improvement (no Ollama needed)
    improvements = []

    if raw > 0 and qualified / max(raw, 1) < 0.1:
        improvements.append({
            "problem": f"Low qualification rate: {qualified}/{raw} ({qualified/max(raw,1)*100:.0f}%)",
            "fix": "Tighten SCOUT domain generation — focus on city+niche patterns, skip generic prefixes like 'best', 'top'",
            "expected": "Higher qualification rate, less wasted scraping"
        })

    if emails_drafted < qualified * 0.3:
        improvements.append({
            "problem": f"Only {emails_drafted} emails drafted for {qualified} qualified leads",
            "fix": "Improve email extraction — try contact pages, About pages, and common patterns (info@, hello@)",
            "expected": "More leads with emails = more outreach"
        })

    if rejected > raw * 0.8:
        improvements.append({
            "problem": f"High rejection rate: {rejected}/{raw}",
            "fix": "Review JUDGE criteria — may be too strict for domain-found leads",
            "expected": "More qualified leads from same raw count"
        })

    if crm_total < 30:
        improvements.append({
            "problem": f"Only {crm_total} leads in CRM — below 30 minimum",
            "fix": "Run SCOUT more aggressively — check 500+ domains per cycle across all niches",
            "expected": "30+ qualified leads within 2 hours"
        })

    # Default improvement if nothing specific
    if not improvements:
        improvements.append({
            "problem": "System running but no major bottlenecks detected",
            "fix": "Expand niche coverage — add more business types (pet grooming, tutoring, massage)",
            "expected": "Broader lead pool, more diverse outreach"
        })

    imp_data = improvements[0]
    resp = f"PROBLEM: {imp_data['problem']}\nFIX: {imp_data['fix']}\nEXPECTED: {imp_data['expected']}"

    imp = {"date": today, "change": resp, "result": "pending", "implemented": False}
    imps = load_improvements()
    imps.append(imp)
    save_improvements(imps)
    nexus_state["last_improvement_date"] = today
    nexus_state["today_improvement"] = resp[:200]
    save_state(nexus_state)

    embed = discord.Embed(
        title=f"📈 1% IMPROVEMENT — {today}",
        description=resp,
        color=0x2ecc71,
        timestamp=datetime.now(BD_TZ),
    )
    embed.set_footer(text="1% every day = 37x better in a year.")
    await ch.send(embed=embed)
    log(f"1% improvement posted {today}")


@daily_improvement_task.before_loop
async def _bw_improvement():
    await bot.wait_until_ready()


@tasks.loop(minutes=1)
async def daily_email_summary_task():
    """Post email summary to Discord at 8:30 AM BD."""
    now = datetime.now(BD_TZ)
    if now.hour != 8 or now.minute != 30:
        return
    today = now.strftime("%Y-%m-%d")
    if nexus_state.get("last_email_summary") == today:
        return

    ch = bot.get_channel(CHANNEL_NEXUS)
    if not ch:
        return

    try:
        sys.path.insert(0, '/home/ubuntu/nanosoft')
        # Inline the summary instead of importing from old quill_v7
        import json
        drafts = []
        try:
            with open("/home/ubuntu/nanosoft/email_drafts.jsonl") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        drafts.append(json.loads(line))
        except:
            pass
        qualified = 0
        from crm import get_crm
        try:
            crm = get_crm()
            qualified = len(crm.get_leads_by_status("Qualified"))
        except:
            pass
        summary = "📧 **Daily Email Summary**\n"
        summary += "Drafts ready: {}\n".format(len(drafts))
        summary += "Qualified leads: {}\n".format(qualified)
        if drafts:
            summary += "\n**Latest drafts:**\n"
            for d in drafts[-3:]:
                summary += "• {} | {}\n".format(d.get('company','')[:25], d.get('subject','')[:30])
        await ch.send(summary)
        nexus_state["last_email_summary"] = today
        save_state(nexus_state)
    except Exception as e:
        log(f"Email summary error: {e}")


@daily_email_summary_task.before_loop
async def _bw_email_summary():
    await bot.wait_until_ready()


# ─── COMMANDS ───────────────────────────────────────────────

@bot.command(name="nexus")
async def nexus_cmd(ctx, subcmd: str = None, *, args: str = None):
    if ctx.author.bot:
        return
    if ctx.author.id != CHAIRMAN_ID:
        await ctx.send("⛔ Chairman-only.")
        return

    if subcmd is None or subcmd == "status":
        await _cmd_status(ctx)
    elif subcmd == "review":
        await _cmd_review(ctx, args or "")
    elif subcmd == "improve":
        await _cmd_improve(ctx)
    elif subcmd == "threat":
        await _cmd_threat(ctx)
    elif subcmd == "brief":
        await _cmd_status(ctx)
    elif subcmd == "week":
        await _cmd_status(ctx)
    elif subcmd == "fix":
        await _cmd_fix(ctx, args or "")
    elif subcmd == "restart":
        await _cmd_restart(ctx, args or "")
    elif subcmd == "send":
        await _cmd_send(ctx, args or "all")
    elif subcmd == "emails":
        await _cmd_emails(ctx)
    elif subcmd == "draft":
        await _cmd_draft(ctx)
    elif subcmd == "drafts":
        await _cmd_drafts(ctx)
    else:
        await ctx.send("Available: `status`, `review`, `improve`, `threat`, `fix`, `restart`, `send`, `emails`, `draft`, `drafts`")


async def _cmd_status(ctx):
    global nexus_state
    nexus_state = check_agents(nexus_state)
    pipeline_state = get_pipeline_state()
    crm_stats = get_crm_stats()
    nexus_state["qualified_leads_today"] = pipeline_state.get("qualified_count", 0)
    save_state(nexus_state)

    embed = discord.Embed(title="⚡ NEXUS STATUS", color=0xff4444, timestamp=datetime.now(BD_TZ))

    # Agent status with systemd states
    agent_lines = []
    for a, s in nexus_state.get("agent_status", {}).items():
        icon = "🟢" if s.get("status") == "running" else "🔴" if s.get("status") == "stopped" else "⚪"
        detail = ""
        if a == "SCOUT":
            detail = f"leads: {pipeline_state.get('raw_scraped', 0)}"
        elif a == "HAWK":
            detail = f"jobs: {pipeline_state.get('jobs_found', 0)}"
        elif a == "QUILL":
            detail = f"drafted: {pipeline_state.get('emails_drafted', 0)}"
        elif a == "PIPELINE":
            detail = pipeline_state.get("status", "?")
        elif a == "NOVA":
            nova_state = load_nova_state()
            detail = f"posts today: {nova_state.get('posts_today', 0)}"
        elif a == "ATLAS":
            atlas_state = load_atlas_state()
            detail = f"followups: {atlas_state.get('followups_sent_today', 0)}"
        agent_lines.append(f"{icon} **{a}**: {s.get('status', '?')} ({detail})")
    embed.add_field(name="🤖 Agents", value="\n".join(agent_lines) or "No data", inline=False)

    # Pipeline stats
    embed.add_field(name="📊 Pipeline (Today)", value=(
        f"Qualified: {pipeline_state.get('qualified_count', 0)}/30\n"
        f"Raw scraped: {pipeline_state.get('raw_scraped', 0)}\n"
        f"Rejected: {pipeline_state.get('rejected', 0)}\n"
        f"Drafted: {pipeline_state.get('emails_drafted', 0)}"
    ), inline=True)

    # CRM stats
    embed.add_field(name="📈 CRM", value=(
        f"Total leads: {crm_stats.get('total_leads', 0)}\n"
        f"Qualified (7+): {crm_stats.get('qualified', 0)}\n"
        f"Emails drafted: {crm_stats.get('drafted', 0)}\n"
        f"Goal: $1,000/month"
    ), inline=True)

    # Service status
    svc_lines = []
    for svc in ["scout", "hawk", "pipeline-v3", "nexus", "ollama"]:
        try:
            r = subprocess.run(["systemctl", "is-active", svc], capture_output=True, text=True, timeout=5)
            active = r.stdout.strip() == "active"
            svc_lines.append(f"{'🟢' if active else '🔴'} {svc}")
        except:
            svc_lines.append(f"⚪ {svc}")
    embed.add_field(name="⚙️ Services", value="\n".join(svc_lines), inline=False)

    # Threats
    threats = []
    if pipeline_state.get("qualified_count", 0) == 0:
        threats.append("No qualified leads today")
    for a in ["SCOUT", "HAWK"]:
        if nexus_state["agent_status"].get(a, {}).get("status") == "stopped":
            threats.append(f"{a} DOWN")
    embed.add_field(name="⚠️ Threat", value=threats[0] if threats else "None", inline=False)
    embed.set_footer(text=f"Model: {OLLAMA_MODEL} | 24/7 Automated")
    await ctx.send(embed=embed)


async def _cmd_review(ctx, idea: str):
    if not idea:
        await ctx.send("Usage: `!nexus review [idea]`")
        return
    async with ctx.typing():
        resp = ask_ollama(SYSTEM_PROMPT,
            f"Chairman proposes: {idea}\n\nStress-test this. Weakest point first. What is he not seeing? Counterargument? Only validate if it survives. Be direct.")
    embed = discord.Embed(title="⚖️ NEXUS STRESS-TEST", description=f"**Idea:** {idea[:200]}",
        color=0xf39c12, timestamp=datetime.now(BD_TZ))
    embed.add_field(name="Analysis", value=resp[:1024], inline=False)
    embed.set_footer(text="No flattery. Only results.")
    await ctx.send(embed=embed)


async def _cmd_improve(ctx):
    global nexus_state
    today = datetime.now(BD_TZ).strftime("%Y-%m-%d")
    if nexus_state.get("last_improvement_date") == today:
        await ctx.send(f"✅ Already logged today: {nexus_state.get('today_improvement', '')[:100]}")
        return

    async with ctx.typing():
        resp = ask_ollama(SYSTEM_PROMPT,
            f"Today: {today}\nState: {json.dumps(nexus_state, default=str)[:1500]}\n\nONE 1% improvement. Not a restructure. Weakest link? Specific change, how to measure, expected result.")

    imp = {"date": today, "change": resp[:500], "result": "pending", "implemented": True}
    imps = load_improvements()
    imps.append(imp)
    save_improvements(imps)
    nexus_state["last_improvement_date"] = today
    nexus_state["today_improvement"] = resp[:200]
    save_state(nexus_state)

    embed = discord.Embed(title="📈 1% IMPROVEMENT", description=resp[:2000],
        color=0x2ecc71, timestamp=datetime.now(BD_TZ))
    embed.set_footer(text="1% every day = 365% better in a year.")
    await ctx.send(embed=embed)


async def _cmd_threat(ctx):
    threats = []
    if nexus_state.get("revenue_week", 0) == 0:
        threats.append("ZERO revenue — existential threat")
    if nexus_state.get("qualified_leads_week", 0) < 10:
        threats.append("Lead pipeline critically low")
    for a in ["SCOUT", "HAWK"]:
        if nexus_state["agent_status"].get(a, {}).get("status") == "stopped":
            threats.append(f"{a} is DOWN")
    embed = discord.Embed(title="⚠️ CURRENT THREAT", description=threats[0] if threats else "No immediate threats.",
        color=0xff0000, timestamp=datetime.now(BD_TZ))
    await ctx.send(embed=embed)


async def _cmd_fix(ctx, agent_name: str):
    if not agent_name:
        await ctx.send("Usage: `!nexus fix [agent]`")
        return
    agent_name = agent_name.upper().strip()
    if agent_name not in ["SCOUT", "JUDGE", "QUILL", "HAWK", "NOVA", "ATLAS"]:
        await ctx.send(f"Unknown. Available: SCOUT, JUDGE, QUILL, HAWK, NOVA, ATLAS")
        return
    async with ctx.typing():
        resp = ask_ollama(SYSTEM_PROMPT,
            f"Fix {agent_name}. Status: {json.dumps(nexus_state.get('agent_status', {}).get(agent_name, {}))}\n\nSpecific action? Be direct. Exact instructions.")
    embed = discord.Embed(title=f"🔧 NEXUS ORDER — {agent_name}", description=resp[:2000],
        color=0x9b59b6, timestamp=datetime.now(BD_TZ))
    embed.set_footer(text="Fix it now.")
    await ctx.send(embed=embed)


async def _cmd_restart(ctx, agent_name: str):
    if not agent_name:
        await ctx.send("Usage: `!nexus restart [agent]` — available: SCOUT, HAWK")
        return
    agent_name = agent_name.upper().strip()
    if agent_name not in ["SCOUT", "HAWK", "NOVA", "ATLAS", "PIPELINE"]:
        await ctx.send(f"Cannot restart {agent_name}. Available: SCOUT, HAWK, NOVA, ATLAS, PIPELINE")
        return
    ok = restart_agent(agent_name)
    if ok:
        await ctx.send(f"✅ Restart command issued for **{agent_name}**. Check status in 30 seconds: `!nexus status`")
    else:
        await ctx.send(f"❌ Failed to restart {agent_name}. Manual intervention needed.")


async def _cmd_send(ctx, args: str):
    """Send emails: !send all | !send 1,3,5. Runs in background so Discord doesn't block."""
    await ctx.send(f"📧 QUILL is sending emails: `{args}` (3-min gap between each)...\nYou'll be notified when complete.")

    try:
        import threading
        def _run_send():
            import subprocess
            cmd = ["python3", "/home/ubuntu/nanosoft/quill_v11.py", "send"]
            if args.strip().lower() != "all":
                cmd.append(args.strip())
            subprocess.run(cmd, cwd="/home/ubuntu/nanosoft", timeout=3600)

        thread = threading.Thread(target=_run_send, daemon=True)
        thread.start()
    except Exception as e:
        await ctx.send(f"❌ QUILL error: {str(e)[:200]}")


async def _cmd_emails(ctx):
    """Show email summary."""
    try:
        import json, os
        drafts = []
        df = "/home/ubuntu/nanosoft/email_drafts.jsonl"
        if os.path.exists(df):
            with open(df) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        drafts.append(json.loads(line))
        sent = []
        sf = "/home/ubuntu/nanosoft/emails_sent.jsonl"
        if os.path.exists(sf):
            with open(sf) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        sent.append(json.loads(line))
        msg = "📧 **Email Summary**\n"
        msg += "Drafts ready: {}\n".format(len(drafts))
        msg += "Sent: {}\n".format(len(sent))
        if drafts:
            msg += "\n**Latest drafts:**\n"
            for d in drafts[-5:]:
                msg += "• {} | {}\n".format(d.get('company','')[:25], d.get('subject','')[:30])
        await ctx.send(msg[:2000])
    except Exception as e:
        await ctx.send("Error loading email summary: {}".format(e))


async def _cmd_draft(ctx):
    """Draft all Qualified leads."""
    await ctx.send("✍️ QUILL is drafting emails for all Qualified leads...")
    try:
        import subprocess
        result = subprocess.run(
            ["python3", "/home/ubuntu/nanosoft/quill_v11.py", "draft", "Qualified"],
            capture_output=True, text=True, timeout=300,
            cwd="/home/ubuntu/nanosoft"
        )
        output = result.stdout[:2000] if result.stdout else "Drafting complete."
        await ctx.send(f"✅ {output}")
    except Exception as e:
        await ctx.send(f"❌ Draft error: {str(e)[:200]}")


async def _cmd_drafts(ctx):
    """Show all drafts."""
    try:
        import json
        drafts = []
        with open("/home/ubuntu/nanosoft/email_drafts.jsonl") as f:
            for line in f:
                line = line.strip()
                if line:
                    drafts.append(json.loads(line))
        if not drafts:
            await ctx.send("📭 No drafts found.")
            return
        # Show summary + latest 5
        msg = "📋 **{} drafts ready**\n\n".format(len(drafts))
        for d in drafts[-5:]:
            msg += "**{}** | {} | {}\n".format(
                d.get('company','')[:25],
                d.get('subject','')[:35],
                d.get('to','')[:30]
            )
        if len(drafts) > 5:
            msg += "\n...and {} more".format(len(drafts) - 5)
        await ctx.send(msg[:2000])
    except Exception as e:
        await ctx.send(f"Error: {str(e)[:200]}")


# ─── MESSAGE HANDLER ────────────────────────────────────────

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    await bot.process_commands(message)

    if message.author.id == CHAIRMAN_ID and message.channel.id == CHANNEL_NEXUS:
        if message.content.startswith("!"):
            return
        async with message.channel.typing():
            resp = ask_ollama(SYSTEM_PROMPT,
                f"Chairman says: {message.content}\n\nRespond as NEXUS. Direct. Weakest point first. No flattery. Stress-test if he proposes something.")
        if len(resp) > 2000:
            for i in range(0, len(resp), 2000):
                await message.channel.send(resp[i:i+2000])
        else:
            await message.channel.send(resp)


# ─── MAIN ───────────────────────────────────────────────────

if __name__ == "__main__":
    log("🚀 NEXUS starting...")
    log(f"   Model: {OLLAMA_MODEL}")
    bot.run(BOT_TOKEN)
