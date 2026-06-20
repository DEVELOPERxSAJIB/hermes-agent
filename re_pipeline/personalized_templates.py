#!/usr/bin/env python3
"""
Personalized RE Email Generator
Creates hyper-personalized emails like the example:
  "3 post ideas for your Richardson listings"
"""
import re

def _first_name(contact_name, email=""):
    """Extract first name from contact name or email."""
    if not contact_name or contact_name.strip() == '':
        if email and '@' in email:
            local = email.split('@')[0]
            name = re.split(r'[._\-]', local)[0]
            return name.capitalize() if name else "there"
        return "there"
    # Full name — take first word
    first = contact_name.strip().split()[0]
    # Remove titles
    titles = ['dr', 'mr', 'mrs', 'ms', 'prof']
    if first.lower().rstrip('.') in titles and len(contact_name.strip().split()) > 1:
        first = contact_name.strip().split()[1]
    return first.rstrip(',')

def _clean(text):
    if not text:
        return ""
    text = text.replace("\u2014", " ").replace("\u2013", " ")
    text = re.sub(r'\n{3,}', '\n\n', text)
    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in text.split('\n')]
    text = '\n'.join(lines)
    return text.strip()

# ============================================================
# PERSONALIZED T1 — Social Media Content Creator Pitch
# Mentions specific city/area, references listings
# ============================================================

def personalized_t1(brokerage_name, contact_name, city, state="", website="", instagram="", linkedin=""):
    """
    Personalized cold email referencing the brokerage's city/market.
    Style: "3 post ideas for your Richardson listings"
    """
    first = _first_name(contact_name)
    
    # City-specific hooks
    city_hooks = {
        "Miami": "Miami luxury market",
        "Houston": "Houston suburbs",
        "Dallas": "Dallas-Fort Worth listings",
        "Atlanta": "Atlanta metro",
        "Phoenix": "Phoenix Valley",
        "Las Vegas": "Las Vegas luxury",
        "Orlando": "Orlando vacation and residential",
        "Charlotte": "Charlotte metro",
        "Tampa": "Tampa Bay",
        "Denver": "Denver metro",
    }
    
    market = city_hooks.get(city, f"{city} market")
    
    # Subject lines — short, specific, curiosity-driven
    subjects = [
        f"3 post ideas for your {city} listings",
        f"Quick thought about {brokerage_name}'s {city} presence",
        f"{city} buyers are scrolling past {brokerage_name}",
    ]
    import random
    subject = random.choice(subjects)
    
    # Body — personalized, specific, valuable
    body = _clean(f"""Hi {first},

I was looking at {brokerage_name}'s listings in {city} and noticed your Instagram and LinkedIn aren't really active right now.

For brokerages in the {market}, that's usually where warm buyers are scrolling before they ever call.

I put together 3 post concepts based on what I'm seeing in {city} right now (no charge, just want your read on them). If they land, we can talk about what ongoing content support would look like.

Want me to send them over?

SaJib Shikder
NanoSoft Agency | nanosoft.agency""")
    
    return {"subject": subject, "body": body}


def personalized_t2(brokerage_name, contact_name, city, state="", website="", instagram="", linkedin=""):
    """
    T2 Follow-up — shorter, different angle
    """
    first = _first_name(contact_name)
    
    subject = f"Following up — {brokerage_name} social content"
    
    body = _clean(f"""Hi {first},

Sent you a note a few days ago about social media content for {brokerage_name}.

Wanted to follow up because I genuinely think a few consistent posts per week in {city} could move the needle for you. Most brokerages your size are leaving engagement on the table.

We handle everything — content creation, posting, engagement. Your team does nothing.

Open to a quick 15-minute call this week?

SaJib Shikder
NanoSoft Agency | nanosoft.agency""")
    
    return {"subject": subject, "body": body}


def personalized_t3(brokerage_name, contact_name, city, state="", website="", instagram="", linkedin=""):
    """
    T3 — Free sample content offer
    """
    first = _first_name(contact_name)
    
    subject = f"Free content sample for {brokerage_name}?"
    
    body = _clean(f"""Hi {first},

One more follow-up.

We typically produce 20 to 25 content pieces per month for brokerages in {city} — listing posts, market updates, agent spotlights, local area highlights.

Happy to put together a free sample content plan for {brokerage_name} with no commitment. Just so you can see what it looks like in practice.

Interested?

SaJib Shikder
NanoSoft Agency | nanosoft.agency""")
    
    return {"subject": subject, "body": body}


def personalized_t4(brokerage_name, contact_name, city, state="", website="", instagram="", linkedin=""):
    """
    T4 — Breakup email
    """
    first = _first_name(contact_name)
    
    subject = f"Closing the loop with {brokerage_name}"
    
    body = _clean(f"""Hi {first},

I've reached out a few times. I'll assume the timing isn't right.

Whenever social media content becomes a priority for {brokerage_name}, I'm one message away.

Good luck with everything in {city}.

SaJib Shikder
NanoSoft Agency""")
    
    return {"subject": subject, "body": body}


def get_personalized_template(touch_num, brokerage_name="", contact_name="", city="", state="", website="", instagram="", linkedin=""):
    """Get personalized template by touch number."""
    templates = {
        1: personalized_t1,
        2: personalized_t2,
        3: personalized_t3,
        4: personalized_t4,
    }
    fn = templates.get(touch_num)
    if not fn:
        return {"subject": "", "body": ""}
    return fn(brokerage_name, contact_name, city, state, website, instagram, linkedin)
