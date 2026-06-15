"""Email templates — Angle A (Social Media) and Angle B (Automation)
Returns dict with 'subject' and 'body' keys."""
import re

def _clean(text):
    """Remove em dashes and en dashes. Keep hyphens. Preserve paragraph breaks (double newlines)."""
    if not text:
        return ""
    text = text.replace("\u2014", " ").replace("\u2013", " ")
    # Collapse multiple blank lines into exactly one blank line
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Remove trailing spaces on each line, collapse intra-line whitespace
    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in text.split('\n')]
    # Rejoin preserving single/blank lines
    text = '\n'.join(lines)
    return text.strip()

def _first_name(contact_name):
    """Extract first name from contact_name or email."""
    if not contact_name:
        return "there"
    if "@" in contact_name:
        local = contact_name.split("@")[0]
        name = re.split(r'[._]', local)[0]
        return name.capitalize() if name else "there"
    # Full name — take first word
    return contact_name.strip().split()[0]

# ============================================================
# ANGLE A — Social Media Manager Pitch
# ============================================================

def angle_a_touch_1(brokerage_name, contact_name, city):
    """Day 1: Cold Email"""
    first = _first_name(contact_name)
    subject = f"Quick note about {brokerage_name}'s online presence"
    body = _clean(f"""Hi {first},

I was looking at {brokerage_name} online. Your listings look solid, but your social media presence is not reflecting that.

Most buyers today check Instagram and Facebook before choosing a brokerage. Without consistent content, those leads are going to someone else.

We handle done for you social media content and management specifically for real estate brokerages. Your team does nothing. The page stays active and professional.

Worth a 15-minute call this week?

SaJib Shikder
NanoSoft | nanosoft.agency""")
    return {"subject": subject, "body": body}

def angle_a_touch_2(brokerage_name, contact_name):
    """Day 3: LinkedIn DM"""
    first = _first_name(contact_name)
    return {"subject": "", "body": _clean(f"""Hi {first},

Sent you an email a couple of days ago. Wanted to connect here too.

We handle social media content and management for small brokerages. Fully done-for-you, no work needed from your team.

Open to a quick chat?""")}

def angle_a_touch_3(brokerage_name, contact_name):
    """Day 7: Email Follow-up"""
    first = _first_name(contact_name)
    subject = "Want to see an example?"
    body = _clean(f"""Hi {first},

Following up one more time.

We typically produce 20 to 25 content pieces per month for brokerages your size. Listings, market updates, agent spotlights, local area posts.

Happy to put together a free sample content plan for {brokerage_name} with no commitment. Just so you can see what it looks like in practice.

Interested?

SaJib Shikder
NanoSoft | nanosoft.agency""")
    return {"subject": subject, "body": body}

def angle_a_touch_4(brokerage_name, contact_name):
    """Day 14: Breakup Email"""
    first = _first_name(contact_name)
    subject = "Closing the loop"
    body = _clean(f"""Hi {first},

I have reached out a few times. I will assume the timing is not right.

Whenever social media becomes a priority, I am one message away.

Good luck with everything.

SaJib Shikder | nanosoft.agency""")
    return {"subject": subject, "body": body}

# ============================================================
# ANGLE B — AI Automation Pitch
# ============================================================

def angle_b_touch_1(brokerage_name, contact_name, city):
    """Day 1: Cold Email"""
    first = _first_name(contact_name)
    subject = f"Quick question about {brokerage_name}'s lead follow-up"
    body = _clean(f"""Hi {first},

Your social media looks great. Clearly you are investing in marketing.

But here is where most brokerages quietly lose money: lead follow-up speed. Studies show that 78% of leads go with the first agent who responds. If your follow-up is not instant and automatic, you are handing deals to competitors.

We build AI-powered lead follow-up systems for real estate brokerages. Instant response via email and SMS, 24/7, with zero manual work from your team.

Worth a 15-minute call this week?

SaJib Shikder
NanoSoft | nanosoft.agency""")
    return {"subject": subject, "body": body}

def angle_b_touch_2(brokerage_name, contact_name):
    """Day 3: LinkedIn DM"""
    first = _first_name(contact_name)
    return {"subject": "", "body": _clean(f"""Hi {first},

Emailed you a couple of days ago about lead automation.

Short version: the leads your agents are manually following up on. We automate that entirely. Response goes out in under 5 minutes, around the clock.

Open to a quick chat?""")}

def angle_b_touch_3(brokerage_name, contact_name):
    """Day 7: Email Follow-up"""
    first = _first_name(contact_name)
    subject = f"Free audit for {brokerage_name}?"
    body = _clean(f"""Hi {first},

One more follow-up.

I can take a look at your current lead flow and put together a free automation audit. Where leads are dropping off and how many could realistically be recovered.

No pitch, just data. Want to see it?

SaJib Shikder
NanoSoft | nanosoft.agency""")
    return {"subject": subject, "body": body}

def angle_b_touch_4(brokerage_name, contact_name):
    """Day 14: Breakup Email"""
    first = _first_name(contact_name)
    subject = "Last one from me"
    body = _clean(f"""Hi {first},

Reached out a few times. I will take the hint that timing is not right.

If lead automation ever becomes a priority, I am one message away.

Best of luck.

SaJib Shikder
NanoSoft | nanosoft.agency""")
    return {"subject": subject, "body": body}

# ============================================================
# Template dispatcher
# ============================================================

def get_template(angle, touch_num, brokerage_name="", contact_name="", city=""):
    """Get the correct template. Returns dict with 'subject' and 'body'."""
    if angle == "A":
        templates = {
            1: angle_a_touch_1,
            2: angle_a_touch_2,
            3: angle_a_touch_3,
            4: angle_a_touch_4,
        }
    else:
        templates = {
            1: angle_b_touch_1,
            2: angle_b_touch_2,
            3: angle_b_touch_3,
            4: angle_b_touch_4,
        }

    fn = templates.get(touch_num)
    if not fn:
        return {"subject": "", "body": ""}

    if touch_num == 1:
        return fn(brokerage_name, contact_name, city)
    return fn(brokerage_name, contact_name)
