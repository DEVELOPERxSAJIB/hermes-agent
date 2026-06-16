"""
NanoSoft Market Rotation Tracker
Tracks which niche+city combinations have been completed.
300 leads per market before rotating.
"""
import json
import os

STATE_FILE = "/home/ubuntu/nanosoft/market_rotation.json"

# Priority niches and cities for cold outreach
NICHE_CITY_QUEUE = [
    # US Markets - highest value local service businesses
    ("dentist", "Dallas"),
    ("dentist", "Chicago"),
    ("dentist", "Houston"),
    ("dentist", "Phoenix"),
    ("roofer", "Dallas"),
    ("roofer", "Houston"),
    ("roofer", "Phoenix"),
    ("roofer", "Atlanta"),
    ("hvac", "Dallas"),
    ("hvac", "Houston"),
    ("hvac", "Chicago"),
    ("hvac", "Phoenix"),
    ("plumber", "Dallas"),
    ("plumber", "Houston"),
    ("plumber", "Chicago"),
    ("plumber", "Atlanta"),
    ("lawyer", "Dallas"),
    ("lawyer", "Houston"),
    ("lawyer", "Chicago"),
    ("lawyer", "Atlanta"),
    ("chiropractor", "Dallas"),
    ("chiropractor", "Houston"),
    ("chiropractor", "Phoenix"),
    ("accountant", "Dallas"),
    ("accountant", "Houston"),
    ("accountant", "Chicago"),
    # UK Markets
    ("dentist", "London"),
    ("dentist", "Manchester"),
    ("dentist", "Birmingham"),
    ("roofer", "London"),
    ("roofer", "Manchester"),
    ("hvac", "London"),
    ("hvac", "Manchester"),
    ("plumber", "London"),
    ("plumber", "Birmingham"),
    ("lawyer", "London"),
    ("lawyer", "Manchester"),
    ("lawyer", "Birmingham"),
    ("chiropractor", "London"),
    ("chiropractor", "Manchester"),
    ("accountant", "London"),
    ("accountant", "Manchester"),
]

LEADS_PER_MARKET = 300


def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except:
        return {"current_index": 0, "markets": {}}


def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def get_current_market(state):
    """Get the current niche and city to target."""
    idx = state.get("current_index", 0)
    if idx >= len(NICHE_CITY_QUEUE):
        idx = 0  # Loop back when all markets done
        state["current_index"] = 0
    niche, city = NICHE_CITY_QUEUE[idx]
    return niche, city


def record_leads(state, niche, city, count):
    """Record that leads were found for this market."""
    key = f"{niche}|{city}"
    if key not in state["markets"]:
        state["markets"][key] = {"niche": niche, "city": city, "total_leads": 0}
    state["markets"][key]["total_leads"] += count


def advance_if_done(state):
    """Check if current market has 300+ leads, advance to next."""
    idx = state.get("current_index", 0)
    niche, city = NICHE_CITY_QUEUE[idx]
    key = f"{niche}|{city}"
    market = state["markets"].get(key, {"total_leads": 0})
    if market.get("total_leads", 0) >= LEADS_PER_MARKET:
        state["current_index"] = (idx + 1) % len(NICHE_CITY_QUEUE)
        new_niche, new_city = NICHE_CITY_QUEUE[state["current_index"]]
        print(f"[ROTATION] {niche}+{city} complete ({market['total_leads']} leads). Moving to {new_niche}+{new_city}")
        return True
    return False


def get_market_progress(state):
    """Get summary of completed and current markets."""
    results = []
    for key, m in state["markets"].items():
        status = "DONE" if m["total_leads"] >= LEADS_PER_MARKET else "ACTIVE"
        results.append(f"  {status} {m['niche']}+{m['city']}: {m['total_leads']}/{LEADS_PER_MARKET}")
    return "\n".join(results)
