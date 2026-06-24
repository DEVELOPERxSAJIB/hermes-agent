#!/usr/bin/env python3
"""
NanoSoft Reverse Pitch Email Templates
Generates curiosity-driven ONE-QUESTION emails for WL and RE leads.

Strategy: Instead of pitching our service, send ONE genuine question about
their business that they MUST answer. The goal is to start a conversation,
not sell.

For WL (White Label) leads:
    - Questions about overflow, capacity, hiring, delivery bottlenecks
    - Triggered by: hiring signals, pain points, team size

For RE (Real Estate) leads:
    - Questions about market trends, buyer/seller dynamics, local insights
    - Triggered by: city, market, recent activity

Usage:
    python3 reverse_pitch_templates.py                    # demo with sample leads
    python3 reverse_pitch_templates.py --from-crm          # generate for all CRM leads
    python3 reverse_pitch_templates.py --lead '{"Company Name":"..."}' --type wl
    python3 reverse_pitch_templates.py --lead '{"Brokerage_Name":"..."}' --type re

Functions:
    generate_reverse_pitch_email(lead, type='wl'|'re') -> {subject, body}
    generate_wl_batch(leads) -> list
    generate_re_batch(leads) -> list
"""
import json
import os
import re
import sys
import random
from datetime import datetime, timezone, timedelta
from typing import Optional

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
CRM_CACHE = os.path.join(NANOSOFT_DIR, "crm_cache.json")
RE_PIPELINE_DIR = os.path.join(NANOSOFT_DIR, "re_pipeline")
RE_LEADS = os.path.join(RE_PIPELINE_DIR, "enriched_leads.json")
OUTPUT_DIR = os.path.join(NANOSOFT_DIR, "reverse_pitch_output")

sys.path.insert(0, NANOSOFT_DIR)

# ── WL Reverse Pitch Templates ──────────────────────────────
# Each template is ONE question. Subject line is short + specific.
# Body is under 80 words. No pitch. No links. Just curiosity.

WL_TEMPLATES = [
    {
        "subject": "quick question about {company}'s dev capacity",
        "body": (
            "Hi {name},\n\n"
            "I noticed {company} is {pain_ref} — and I'm genuinely curious about something.\n\n"
            "When you get more project requests than your {team} can handle, "
            "what happens to the overflow?\n\n"
            "Do you turn them down, hire more, or work with outside partners?\n\n"
            "Just trying to understand how agencies like yours deal with it.\n\n"
            "— SaJib"
        ),
    },
    {
        "subject": "{company} and the hiring question",
        "body": (
            "Hey {name},\n\n"
            "Saw that {company} has been {pain_ref} — exciting times.\n\n"
            "Here's what I'm curious about: when you're scaling this fast, "
            "is it harder to find good dev talent or to manage the workload you already have?\n\n"
            "I talk to a lot of agency owners and everyone has a different answer.\n\n"
            "— SaJib"
        ),
    },
    {
        "subject": "what's your biggest bottleneck right now?",
        "body": (
            "Hi {name},\n\n"
            "I've been looking at {service} agencies in {city} and {company} keeps coming up.\n\n"
            "One question: what's the one thing slowing down your delivery the most right now — "
            "is it people, process, or something else entirely?\n\n"
            "Genuinely curious.\n\n"
            "— SaJib"
        ),
    },
    {
        "subject": "how do you handle the overflow at {company}?",
        "body": (
            "Hey {name},\n\n"
            "Random question — when {company} lands a big {service} project "
            "and your {team} is already stretched, what do you do?\n\n"
            "I'm asking because I work with agencies on exactly this and "
            "everyone's approach is different.\n\n"
            "Would love to hear how it works on your end.\n\n"
            "— SaJib"
        ),
    },
    {
        "subject": "{company}'s {service} work — one question",
        "body": (
            "Hi {name},\n\n"
            "Stumbled across {company}'s work in {service} — really solid.\n\n"
            "Quick question: do you keep all your dev work in-house, "
            "or do you ever bring in outside help when things get busy?\n\n"
            "Just curious how a {team} handles the ups and downs.\n\n"
            "— SaJib"
        ),
    },
    {
        "subject": "the {service} capacity question",
        "body": (
            "Hey {name},\n\n"
            "I help {service} agencies in {city} with a specific problem — "
            "and I'm wondering if {company} ever runs into it.\n\n"
            "Here's the question: when your {team} is at full capacity "
            "and a great project comes in, what do you do?\n\n"
            "No pitch — just genuinely curious.\n\n"
            "— SaJib"
        ),
    },
    {
        "subject": "curious about {company}'s growth",
        "body": (
            "Hi {name},\n\n"
            "{company} seems to be {pain_ref} right now — always impressive to see.\n\n"
            "One thing I'm curious about: as you grow, do you find it's easier "
            "to scale the team or to find reliable partners for the extra work?\n\n"
            "Would love your take.\n\n"
            "— SaJib"
        ),
    },
    {
        "subject": "a question about your {team}",
        "body": (
            "Hey {name},\n\n"
            "I work with {team} in {service} and I've got a question "
            "that only someone running the show can answer.\n\n"
            "What's harder right now — finding people who can actually deliver, "
            "or managing the projects you already have lined up?\n\n"
            "Genuinely want to know.\n\n"
            "— SaJib"
        ),
    },
]


# ── RE Reverse Pitch Templates ──────────────────────────────
# Questions about local market dynamics, buyer/seller behavior, trends.

RE_TEMPLATES = [
    {
        "subject": "question about the {city} market",
        "body": (
            "Hi there,\n\n"
            "I've been tracking {city} real estate trends and {brokerage} stands out.\n\n"
            "Quick question: are you seeing more first-time buyers or investors "
            "coming through right now?\n\n"
            "The data I'm looking at says one thing but I'm curious what it's "
            "actually like on the ground.\n\n"
            "— SaJib"
        ),
    },
    {
        "subject": "what's happening in {city} real estate?",
        "body": (
            "Hey,\n\n"
            "I noticed {brokerage} is active in the {city} market — and I'm curious.\n\n"
            "Is inventory still tight, or are you starting to see more listings come through?\n\n"
            "I hear different things from different markets and would love your take.\n\n"
            "— SaJib"
        ),
    },
    {
        "subject": "{city} buyers — what are you seeing?",
        "body": (
            "Hi,\n\n"
            "One question for someone who knows the {city} market:\n\n"
            "Are your buyers more motivated by price or by timing right now?\n\n"
            "I'm trying to understand how the shift in rates is actually playing out "
            "in markets like yours.\n\n"
            "— SaJib"
        ),
    },
    {
        "subject": "the {city} listing question",
        "body": (
            "Hey,\n\n"
            "I came across {brokerage} and noticed you're in {city}.\n\n"
            "Here's what I'm curious about: are sellers in your market starting to "
            "adjust prices, or are they holding firm and waiting?\n\n"
            "Would love to hear what you're actually seeing day-to-day.\n\n"
            "— SaJib"
        ),
    },
    {
        "subject": "quick one about {city} {state}",
        "body": (
            "Hi there,\n\n"
            "I'm researching {city}, {state} real estate and {brokerage} caught my eye.\n\n"
            "Simple question: what type of property is moving fastest in your area right now — "
            "residential, commercial, or land?\n\n"
            "Just trying to get a feel for where the activity is.\n\n"
            "— SaJib"
        ),
    },
    {
        "subject": "is {city} still a seller's market?",
        "body": (
            "Hey,\n\n"
            "I've been looking at {city} real estate data and I'm genuinely unsure "
            "which way the market is heading.\n\n"
            "From where you're sitting at {brokerage}, does it still feel like a seller's market, "
            "or are things starting to shift?\n\n"
            "Would love your honest take.\n\n"
            "— SaJib"
        ),
    },
    {
        "subject": "what's the vibe in {city} real estate?",
        "body": (
            "Hi,\n\n"
            "I talk to brokerages across the US and I'm curious about {city}.\n\n"
            "What's the one thing driving the most activity in your market right now — "
            "is it relocations, investors, or local buyers upgrading?\n\n"
            "Just want to understand the real story behind the numbers.\n\n"
            "— SaJib"
        ),
    },
    {
        "subject": "{brokerage} and the {city} question",
        "body": (
            "Hey,\n\n"
            "I saw {brokerage} is operating in {city} — and I've got one question.\n\n"
            "Are you finding that buyers are getting more selective, or is it still "
            "a 'list it and it sells' kind of market?\n\n"
            "Curious what your experience has been lately.\n\n"
            "— SaJib"
        ),
    },
]


# ── Personalization helpers ─────────────────────────────────

def _wl_first_name(lead: dict) -> str:
    owner = lead.get("Owner Name", "").strip()
    if owner:
        return owner.split()[0]
    email = lead.get("Email", "").strip()
    if email and "@" in email:
        local = email.split("@")[0]
        # Skip generic prefixes
        generic = {"hello", "hi", "info", "sales", "marketing", "contact", "support",
                   "admin", "office", "team", "mail", "enquiries", "inquiry"}
        if local.lower() in generic:
            return ""
        parts = re.split(r'[._\-]', local)
        if parts and len(parts[0]) > 1:
            return parts[0].capitalize()
    return ""


def _wl_city(lead: dict) -> str:
    country = lead.get("Country", "the US")
    clean = re.sub(r'[.,]+$', '', country.strip())
    parts = [p.strip() for p in re.split(r'[,;]', clean) if p.strip()]
    if parts:
        city_part = parts[0]
        if len(parts) > 1 and re.match(r'^[A-Z]{2}$', parts[1].strip()):
            return f"{city_part}, {parts[1].strip()}"
        return city_part
    return "your area"


def _wl_service(lead: dict) -> str:
    services_raw = lead.get("Services", "")
    if not services_raw:
        return "software development"
    svns = [s.strip().lower() for s in services_raw.split(",") if s.strip()]
    buckets = {
        "AI/ML": "AI",
        "cloud/DevOps": "cloud",
        "mobile development": "mobile",
        "eCommerce": "e-commerce",
        "SaaS": "SaaS",
        "custom software": "custom builds",
        "staff augmentation": "team scaling",
        "UI/UX design": "design",
        "MVP development": "MVPs",
        "QA/Testing": "QA",
    }
    for key, label in buckets.items():
        if key in svns:
            return label
    return svns[0] if svns else "software development"


def _wl_team(lead: dict) -> str:
    size = lead.get("Team Size", "").strip()
    if not size:
        return "team"
    if "1,000" in size or "1000" in size:
        return "large team"
    if "250" in size or "500" in size or "999" in size:
        return "mid-size team"
    if "50" in size or "100" in size or "249" in size:
        return "small team"
    if "10" in size or "49" in size:
        return "boutique team"
    return "team"


def _wl_pain_ref(lead: dict) -> str:
    pp = lead.get("Pain Point", "").lower()
    if "hiring" in pp or "scale" in pp:
        return "hiring and scaling"
    if "overflow" in pp or "capacity" in pp:
        return "handling overflow"
    if "partner" in pp:
        return "partnering on projects"
    if "growth" in pp:
        return "growing fast"
    return "building interesting things"


def _re_city(lead: dict) -> str:
    return lead.get("City", "your area").strip() or "your area"


def _re_state(lead: dict) -> str:
    return lead.get("State_Country", "").strip() or ""


def _re_brokerage(lead: dict) -> str:
    return lead.get("Brokerage_Name", "your brokerage").strip() or "your brokerage"


# ── Core generation functions ────────────────────────────────

def generate_reverse_pitch_email(lead: dict, type: str = "wl") -> dict:
    """
    Generate a curiosity-driven one-question Reverse Pitch email.

    Args:
        lead: dict with lead data (WL or RE format)
        type: 'wl' for White Label, 're' for Real Estate

    Returns:
        {subject, body, type, lead_key}
    """
    if type == "wl":
        return _generate_wl_email(lead)
    elif type == "re":
        return _generate_re_email(lead)
    else:
        raise ValueError(f"Unknown type: {type}. Use 'wl' or 're'.")


def _generate_wl_email(lead: dict) -> dict:
    """Generate a WL Reverse Pitch email."""
    template = random.choice(WL_TEMPLATES)

    name = _wl_first_name(lead)
    company = lead.get("Company Name", "your company")
    city = _wl_city(lead)
    service = _wl_service(lead)
    team = _wl_team(lead)
    pain_ref = _wl_pain_ref(lead)

    subject = template["subject"].format(
        company=company, service=service, city=city, team=team
    )
    body = template["body"].format(
        name=name if name else "there",
        company=company,
        city=city,
        service=service,
        team=team,
        pain_ref=pain_ref,
    )

    # Clean up any double spaces from empty name
    body = re.sub(r'\n{3,}', '\n\n', body)
    body = body.replace("  ", " ")

    lead_key = f"{company}|wl"

    return {
        "subject": subject,
        "body": body,
        "type": "wl",
        "lead_key": lead_key,
        "company": company,
        "email": lead.get("Email", ""),
        "personalization": {
            "name": name,
            "city": city,
            "service": service,
            "team": team,
            "pain_ref": pain_ref,
        },
    }


def _generate_re_email(lead: dict) -> dict:
    """Generate a RE Reverse Pitch email."""
    template = random.choice(RE_TEMPLATES)

    brokerage = _re_brokerage(lead)
    city = _re_city(lead)
    state = _re_state(lead)

    subject = template["subject"].format(
        city=city, state=state, brokerage=brokerage
    )
    body = template["body"].format(
        brokerage=brokerage,
        city=city,
        state=state,
    )

    # Clean up
    body = re.sub(r'\n{3,}', '\n\n', body)
    body = body.replace("  ", " ")

    lead_key = f"{brokerage}|re"

    return {
        "subject": subject,
        "body": body,
        "type": "re",
        "lead_key": lead_key,
        "company": brokerage,
        "email": lead.get("Email", ""),
        "personalization": {
            "city": city,
            "state": state,
            "brokerage": brokerage,
        },
    }


# ── Batch generation ─────────────────────────────────────────

def generate_wl_batch(leads: Optional[list] = None, n: int = 20) -> list:
    """
    Generate Reverse Pitch emails for WL leads.

    Args:
        leads: list of WL lead dicts. If None, loads from crm_cache.json.
        n: max number of emails to generate.

    Returns:
        List of {subject, body, type, lead_key, company, email, personalization}
    """
    if leads is None:
        leads = _load_wl_leads()

    results = []
    used_templates = set()

    for i, lead in enumerate(leads[:n]):
        # Rotate templates to avoid repetition
        template_idx = i % len(WL_TEMPLATES)
        while template_idx in used_templates and len(used_templates) < len(WL_TEMPLATES):
            template_idx = (template_idx + 1) % len(WL_TEMPLATES)
        used_templates.add(template_idx)

        # Pick specific template
        template = WL_TEMPLATES[template_idx]
        name = _wl_first_name(lead)
        company = lead.get("Company Name", "your company")
        city = _wl_city(lead)
        service = _wl_service(lead)
        team = _wl_team(lead)
        pain_ref = _wl_pain_ref(lead)

        subject = template["subject"].format(
            company=company, service=service, city=city, team=team
        )
        body = template["body"].format(
            name=name if name else "there",
            company=company,
            city=city,
            service=service,
            team=team,
            pain_ref=pain_ref,
        )
        body = re.sub(r'\n{3,}', '\n\n', body)
        body = body.replace("  ", " ")

        results.append({
            "subject": subject,
            "body": body,
            "type": "wl",
            "lead_key": f"{company}|wl",
            "company": company,
            "email": lead.get("Email", ""),
            "personalization": {
                "name": name,
                "city": city,
                "service": service,
                "team": team,
                "pain_ref": pain_ref,
            },
        })

    return results


def generate_re_batch(leads: Optional[list] = None, n: int = 20) -> list:
    """
    Generate Reverse Pitch emails for RE leads.

    Args:
        leads: list of RE lead dicts. If None, loads from re_pipeline/enriched_leads.json.
        n: max number of emails to generate.

    Returns:
        List of {subject, body, type, lead_key, company, email, personalization}
    """
    if leads is None:
        leads = _load_re_leads()

    results = []
    used_templates = set()

    for i, lead in enumerate(leads[:n]):
        template_idx = i % len(RE_TEMPLATES)
        while template_idx in used_templates and len(used_templates) < len(RE_TEMPLATES):
            template_idx = (template_idx + 1) % len(RE_TEMPLATES)
        used_templates.add(template_idx)

        template = RE_TEMPLATES[template_idx]
        brokerage = _re_brokerage(lead)
        city = _re_city(lead)
        state = _re_state(lead)

        subject = template["subject"].format(
            city=city, state=state, brokerage=brokerage
        )
        body = template["body"].format(
            brokerage=brokerage,
            city=city,
            state=state,
        )
        body = re.sub(r'\n{3,}', '\n\n', body)
        body = body.replace("  ", " ")

        results.append({
            "subject": subject,
            "body": body,
            "type": "re",
            "lead_key": f"{brokerage}|re",
            "company": brokerage,
            "email": lead.get("Email", ""),
            "personalization": {
                "city": city,
                "state": state,
                "brokerage": brokerage,
            },
        })

    return results


# ── Data loading ─────────────────────────────────────────────

def _load_wl_leads() -> list:
    """Load WL leads from crm_cache.json."""
    with open(CRM_CACHE) as f:
        data = json.load(f)
    leads = data.get("leads", [])
    # Filter: only leads with emails
    return [l for l in leads if l.get("Email", "").strip() and "@" in l.get("Email", "")]


def _load_re_leads() -> list:
    """Load RE leads from re_pipeline/enriched_leads.json."""
    with open(RE_LEADS) as f:
        data = json.load(f)
    if isinstance(data, list):
        leads = data
    elif isinstance(data, dict) and "leads" in data:
        leads = data["leads"]
    else:
        leads = []
    # Filter: only leads with emails
    return [l for l in leads if (l.get("Email", "") or l.get("All_Emails", ""))]


# ── Output ───────────────────────────────────────────────────

def save_batch(batch: list, filename: str):
    """Save batch to JSON file."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, "w") as f:
        json.dump(batch, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(batch)} emails to {path}")


def print_email(email: dict, idx: int = 0):
    """Pretty-print a single email."""
    print(f"\n{'─'*60}")
    print(f"[{idx}] {email['type'].upper()} | {email['company']}")
    print(f"    To: {email['email']}")
    print(f"    Subject: {email['subject']}")
    print(f"    Body ({len(email['body'])} chars):")
    for line in email['body'].split('\n'):
        print(f"      {line}")
    print(f"{'─'*60}")


# ── CLI ──────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Reverse Pitch Email Generator")
    parser.add_argument("--type", choices=["wl", "re", "both"], default="both",
                        help="Lead type: wl (White Label), re (Real Estate), or both")
    parser.add_argument("--n", type=int, default=10, help="Number of emails per type")
    parser.add_argument("--from-crm", action="store_true", help="Load leads from data files")
    parser.add_argument("--save", action="store_true", help="Save output to files")
    parser.add_argument("--lead", type=str, help="Single lead as JSON string")
    parser.add_argument("--preview", action="store_true", help="Preview mode (don't save)")
    args = parser.parse_args()

    if args.lead:
        # Single lead mode
        lead = json.loads(args.lead)
        lead_type = args.type if args.type != "both" else "wl"
        email = generate_reverse_pitch_email(lead, type=lead_type)
        print_email(email, 1)
        return

    results = {}

    if args.type in ("wl", "both"):
        if args.from_crm:
            wl_leads = _load_wl_leads()
        else:
            # Use sample leads from CRM cache for demo
            wl_leads = _load_wl_leads()

        wl_batch = generate_wl_batch(wl_leads, n=args.n)
        results["wl"] = wl_batch
        print(f"\n{'='*60}")
        print(f"WHITE LABEL REVERSE PITCH — {len(wl_batch)} emails")
        print(f"{'='*60}")
        for i, email in enumerate(wl_batch, 1):
            print_email(email, i)

    if args.type in ("re", "both"):
        if args.from_crm:
            re_leads = _load_re_leads()
        else:
            re_leads = _load_re_leads()

        re_batch = generate_re_batch(re_leads, n=args.n)
        results["re"] = re_batch
        print(f"\n{'='*60}")
        print(f"REAL ESTATE REVERSE PITCH — {len(re_batch)} emails")
        print(f"{'='*60}")
        for i, email in enumerate(re_batch, 1):
            print_email(email, i)

    if args.save and not args.preview:
        ts = datetime.now(BD_TZ).strftime("%Y%m%d_%H%M")
        if "wl" in results:
            save_batch(results["wl"], f"wl_reverse_pitch_{ts}.json")
        if "re" in results:
            save_batch(results["re"], f"re_reverse_pitch_{ts}.json")
        print(f"\nOutput saved to {OUTPUT_DIR}/")
    else:
        print(f"\n[PREVIEW] Not saved. Use --save to write output files.")


if __name__ == "__main__":
    main()
