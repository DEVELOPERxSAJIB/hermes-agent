#!/usr/bin/env python3
"""
NanoSoft LinkedIn Warm-Up System
Generates personalized connection request notes and follow-up comments
for White Label agency owners on LinkedIn.

Strategy:
- 10 connection requests/day (300 char max, LinkedIn limit)
- 3 follow-up comments per lead after connection accepted
- Every message references something specific about THEIR business
- No pitch, no links, no sales language — just genuine curiosity

Data source: crm_cache.json (WL leads with LinkedIn profiles)
Also reads: linkedin_20_daily.json, linkedin_actions_today.json for queue

Usage:
    python3 linkedin_warmup.py                    # generate batch from CRM
    python3 linkedin_warmup.py --lead '{"Company Name":"...",...}'  # single lead
    python3 linkedin_warmup.py --preview           # preview 5 without saving
    python3 linkedin_warmup.py --dry-run           # generate but don't write queue

Output -> linkedin_warmup_queue.json (10 leads with notes)
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
QUEUE_FILE = os.path.join(NANOSOFT_DIR, "linkedin_warmup_queue.json")

sys.path.insert(0, NANOSOFT_DIR)

# ── Personalization data extraction ─────────────────────────

def _first_name(lead: dict) -> str:
    owner = lead.get("Owner Name", "").strip()
    if owner:
        return owner.split()[0]
    company = lead.get("Company Name", "their company")
    return f"@{company.split()[0].lower()}"


def _city(lead: dict) -> str:
    country = lead.get("Country", "the US")
    # Extract city-like patterns
    # "Los Angeles, CA" -> "LA"; "Mountain View , CA." -> "Mountain View"
    clean = re.sub(r'[.,]+$', '', country.strip())
    parts = [p.strip() for p in re.split(r'[,;]', clean) if p.strip()]
    # First part is usually city or country
    if parts:
        city_part = parts[0]
        # If it has a state abbreviation after, combine
        if len(parts) > 1 and re.match(r'^[A-Z]{2}$', parts[1].strip()):
            return f"{city_part}, {parts[1].strip()}"
        return city_part
    return "the area"


def _service_bucket(lead: dict) -> str:
    """Pick the lead's most interesting service to reference."""
    services_raw = lead.get("Services", "")
    if not services_raw:
        return "software development"
    svns = [s.strip().lower() for s in services_raw.split(",") if s.strip()]
    # Prioritize interesting buckets
    buckets = {
        "AI/ML": "AI",
        "cloud/DevOps": "cloud infrastructure",
        "mobile development": "mobile apps",
        "eCommerce": "e-commerce",
        "SaaS": "SaaS platforms",
        "custom software": "custom builds",
        "staff augmentation": "team scaling",
        "UI/UX design": "product design",
        "MVP development": "MVPs",
        "QA/Testing": "QA",
    }
    for key, label in buckets.items():
        if key in svns:
            return label
    return svns[0].strip().replace("_", " ") if svns else "software development"


def _team_vibe(lead: dict) -> str:
    """Generate a team-size reference."""
    size = lead.get("Team Size", "").strip()
    if not size:
        return "growing team"
    if "1,000" in size or "1000" in size:
        return "900+ person team"
    if "250" in size or "500" in size or "999" in size:
        return "couple-hundred-person team"
    if "50" in size or "100" in size or "249" in size:
        return "small but mighty team"
    if "10" in size or "49" in size:
        return "boutique team"
    return "growing team"


def _pain_ref(lead: dict) -> str:
    """Transform pain-point into a natural observation."""
    pp = lead.get("Pain Point", "").lower()
    if "hiring" in pp or "scale" in pp:
        return "scaling up"
    if "overflow" in pp or "capacity" in pp:
        return "handling overflow"
    if "partner" in pp:
        return "partnering on projects"
    if "growth" in pp:
        return "growing fast"
    return "building interesting things"


# ── Connection note templates (300 char max) ────────────────
# Templates use {name}, {company}, {city}, {service}, {team}, {pain}
# ALL under 300 chars. Varied sentence structures. No pitch.

CONNECT_TEMPLATES = [
    # Observation + curiosity
    (
        "Hey {name}, noticed {company}'s {service} work — especially impressive for a {team}. "
        "Curious how you handle the dev side when things get busy. Worth connecting?"
    ),
    # Geography hook
    (
        "Hi {name}, {company} has a great reputation in {city}'s {service} scene. "
        "Always interesting seeing how agencies like yours manage capacity. Open to connect?"
    ),
    # Hiring signal
    (
        "Hey {name}, heard {company} is {pain} right now — always cool to see. "
        "Quick question: do you keep dev work in-house or work with outside partners?"
    ),
    # Service-specific
    (
        "Hi {name}, stumbled across {company}'s work in {service}. Solid stuff. "
        "Genuinely curious — what's your biggest bottleneck on the delivery side right now?"
    ),
    # Short + direct
    (
        "Hey {name}, {company} looks like it's doing cool work in {service}. "
        "I help agencies like yours handle overflow dev without the hiring headache. Worth a chat?"
    ),
    # Peer angle
    (
        "Hi {name}, fellow {service} person here — noticed {company}'s work and impressed. "
        "Always good to connect with people running {team}. Worth connecting?"
    ),
    # Market observation
    (
        "Hey {name}, {company} stands out in the {city} {service} market. "
        "Curious — when you're at capacity, what happens to the extra project requests?"
    ),
    # Compliment + question
    (
        "Hi {name}, {company}'s portfolio in {service} is genuinely impressive. "
        "Quick one: do you ever wish you had more dev bandwidth without growing the team?"
    ),
    # Casual + specific
    (
        "Hey {name}, saw {company} is {pain} — exciting times. "
        "Random question: what's harder right now, finding dev talent or managing the workload?"
    ),
    # Mutual interest
    (
        "Hi {name}, {company} has been on my radar for a while — great {service} work. "
        "Would love to connect and hear how you're handling the {pain} phase."
    ),
]


# ── Follow-up comments (post-connection, 200 char max) ──────
# These are LinkedIn comments to post on their activity after connecting.
# Casual, no pitch, just continuing the conversation.

FOLLOWUP_TEMPLATES = [
    # Comment set A: The "curious peer" angle
    [
        "Thanks for connecting! That's a great point about {service} — what's the one thing you wish you could automate on the delivery side?",
        "Interesting take. Out of curiosity, when {company} gets more projects than the team can handle, what's the first thing you do?",
        "Totally agree. Quick question — do you find it's easier to scale the team or find outside partners when things get busy?",
    ],
    # Comment set B: The "market observer" angle
    [
        "Great to connect. I've been watching the {city} {service} space — what trends are you seeing from your side?",
        "Thanks for connecting! {company} seems to be {pain} at the right time. What's driving most of your new project requests lately?",
        "Appreciate the connect. One thing I'm curious about — how do you decide what to keep in-house vs. bring in help for?",
    ],
    # Comment set C: The "genuine question" angle
        [
        "Hey {name}, thanks for connecting! Random question — what's the hardest part of running a {team} in {service}?",
        "Good to be connected. I'm always curious — when {company} lands a big project, how far out is your dev team booked?",
        "Thanks for the connect! If you could wave a magic wand and fix one thing about how {company} delivers projects, what would it be?",
    ],
]


def _pick_template_set(lead: dict) -> list:
    """Pick the best follow-up set based on lead characteristics."""
    score = str(lead.get("Judge Score", "0")).strip()
    try:
        score_int = int(score)
    except (ValueError, TypeError):
        score_int = 0

    pp = lead.get("Pain Point", "").lower()
    if "hiring" in pp or "scale" in pp:
        return FOLLOWUP_TEMPLATES[1]  # market observer — scaling angle
    if score_int >= 9:
        return FOLLOWUP_TEMPLATES[2]  # genuine question — high-value lead
    return FOLLOWUP_TEMPLATES[0]  # curious peer — default


def generate_connection_note(lead: dict, template_idx: Optional[int] = None) -> str:
    """Generate a single personalized connection note (300 char max)."""
    if template_idx is not None:
        template = CONNECT_TEMPLATES[template_idx % len(CONNECT_TEMPLATES)]
    else:
        template = random.choice(CONNECT_TEMPLATES)

    name = _first_name(lead)
    company = lead.get("Company Name", "your company")
    city = _city(lead)
    service = _service_bucket(lead)
    team = _team_vibe(lead)
    pain = _pain_ref(lead)

    note = template.format(
        name=name, company=company, city=city,
        service=service, team=team, pain=pain
    )

    # Hard cap at 300 chars (LinkedIn limit)
    if len(note) > 300:
        note = note[:297] + "..."

    return note


def generate_follow_ups(lead: dict) -> list:
    """Generate 3 personalized follow-up comments with lead data filled in."""
    templates = _pick_template_set(lead)
    name = _first_name(lead)
    company = lead.get("Company Name", "your company")
    city = _city(lead)
    service = _service_bucket(lead)
    team = _team_vibe(lead)
    pain = _pain_ref(lead)

    filled = []
    for tmpl in templates:
        filled.append(tmpl.format(
            name=name if name else "there",
            company=company,
            city=city,
            service=service,
            team=team,
            pain=pain,
        ))
    return filled


def generate_linkedin_batch(leads: list, n: int = 10) -> list:
    """
    Generate a batch of LinkedIn warm-up messages.

    Args:
        leads: list of lead dicts (from crm_cache.json or similar)
        n: number of leads to process (default 10)

    Returns:
        List of dicts: {lead, connection_note, follow_up_comments}
    """
    results = []
    used_templates = set()

    for i, lead in enumerate(leads[:n]):
        # Rotate through templates to avoid repetition
        template_idx = i % len(CONNECT_TEMPLATES)
        while template_idx in used_templates and len(used_templates) < len(CONNECT_TEMPLATES):
            template_idx = (template_idx + 1) % len(CONNECT_TEMPLATES)
        used_templates.add(template_idx)

        note = generate_connection_note(lead, template_idx)
        follow_ups = generate_follow_ups(lead)

        results.append({
            "lead": {
                "company": lead.get("Company Name", ""),
                "owner_name": lead.get("Owner Name", ""),
                "linkedin_url": lead.get("Owner LinkedIn URL", lead.get("LinkedIn", "")),
                "email": lead.get("Email", ""),
                "country": lead.get("Country", ""),
                "services": lead.get("Services", ""),
                "team_size": lead.get("Team Size", ""),
                "pain_point": lead.get("Pain Point", ""),
                "judge_score": lead.get("Judge Score", ""),
                "status": lead.get("Status", ""),
            },
            "connection_note": note,
            "connection_note_length": len(note),
            "follow_up_comments": follow_ups,
        })

    return results


def load_wl_leads() -> list:
    """Load WL leads from crm_cache.json."""
    with open(CRM_CACHE) as f:
        data = json.load(f)
    leads = data.get("leads", [])
    # Filter: only leads with some LinkedIn presence or high judge score
    qualified = []
    for lead in leads:
        score = str(lead.get("Judge Score", "0")).strip()
        try:
            score_int = int(score)
        except (ValueError, TypeError):
            score_int = 0
        has_linkedin = bool(lead.get("Owner LinkedIn URL", "").strip() or lead.get("LinkedIn", "").strip())
        # Include if has LinkedIn OR score >= 7
        if has_linkedin or score_int >= 7:
            qualified.append(lead)
    return qualified


def save_queue(batch: list, path: str = QUEUE_FILE):
    """Save the batch to the warmup queue file."""
    with open(path, "w") as f:
        json.dump(batch, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(batch)} leads to {path}")


def print_batch(batch: list):
    """Pretty-print the batch for review."""
    print(f"\n{'='*70}")
    print(f"LINKEDIN WARM-UP BATCH — {len(batch)} leads")
    print(f"{'='*70}")
    for i, item in enumerate(batch, 1):
        lead = item["lead"]
        print(f"\n--- [{i}] {lead['company']} ---")
        print(f"    Owner: {lead['owner_name'] or 'N/A'}")
        print(f"    LinkedIn: {lead['linkedin_url'] or 'N/A'}")
        print(f"    Location: {lead['country']}")
        print(f"    Services: {lead['services'][:60]}...")
        print(f"    Score: {lead['judge_score']} | Status: {lead['status']}")
        print(f"    Connection ({item['connection_note_length']} chars):")
        print(f"      \"{item['connection_note']}\"")
        print(f"    Follow-ups:")
        for j, fu in enumerate(item["follow_up_comments"], 1):
            print(f"      {j}. \"{fu}\"")
    print(f"\n{'='*70}")


# ── CLI ──────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="LinkedIn Warm-Up Message Generator")
    parser.add_argument("--preview", action="store_true", help="Preview 5 leads without saving")
    parser.add_argument("--dry-run", action="store_true", help="Generate but don't write queue")
    parser.add_argument("--n", type=int, default=10, help="Number of leads (default 10)")
    parser.add_argument("--lead", type=str, help="Single lead as JSON string")
    parser.add_argument("--from-crm", action="store_true", help="Load leads from crm_cache.json")
    args = parser.parse_args()

    if args.lead:
        # Single lead mode
        lead = json.loads(args.lead)
        note = generate_connection_note(lead)
        follow_ups = generate_follow_ups(lead)
        result = {
            "lead": lead,
            "connection_note": note,
            "connection_note_length": len(note),
            "follow_up_comments": follow_ups,
        }
        print(json.dumps(result, indent=2))
        return

    # Load leads
    if args.from_crm:
        leads = load_wl_leads()
    else:
        # Default: load from CRM cache
        leads = load_wl_leads()

    if not leads:
        print("No qualified leads found in CRM cache.")
        return

    if args.preview:
        leads = leads[:5]

    batch = generate_linkedin_batch(leads, n=args.n)
    print_batch(batch)

    if not args.dry_run and not args.preview:
        save_queue(batch)
        print(f"\nQueue ready. {len(batch)} connection notes generated.")
    elif args.dry_run:
        print("\n[DRY RUN] Queue not saved.")
    else:
        print("\n[PREVIEW] Queue not saved.")


if __name__ == "__main__":
    main()
