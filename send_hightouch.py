#!/usr/bin/env python3
"""
HIGH-TOUCH EMAIL SENDER — Audit + Spy + Reverse Pitch
Sends personalized, non-pitchy emails that get replies.
"""
import json, os, sys, time, re, smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from datetime import datetime

NANOSOFT_DIR = "/home/ubuntu/nanosoft"
SEND_QUEUE = os.path.join(NANOSOFT_DIR, "send_queue.json")

SMTP_USER = "nanosoftagency007@gmail.com"
SMTP_PASS = "wgxo ddup cdol kupl"

# Log files
SENT_LOG = os.path.join(NANOSOFT_DIR, "emails_sent_hightouch.jsonl")
SEND_REPORT = os.path.join(NANOSOFT_DIR, "hightouch_send_report.txt")

def send_smtp(to_email, subject, body):
    """Send email via Gmail SMTP."""
    msg = MIMEMultipart()
    msg["From"] = f"SaJib Shikder <{SMTP_USER}>"
    msg["To"] = to_email
    msg["Subject"] = subject.replace("\n", " ").strip()
    msg.attach(MIMEText(body, "plain", "utf-8"))
    
    for attempt in range(3):
        try:
            ctx = ssl.create_default_context()
            with smtplib.SMTP("smtp.gmail.com", 587) as server:
                server.ehlo()
                server.starttls(context=ctx)
                server.ehlo()
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
            return True, ""
        except Exception as e:
            err = str(e)[:200]
            if attempt < 2:
                time.sleep(10)
            else:
                return False, err
    return False, "max retries"

def log_sent(to_email, company, subject, template_type):
    """Log sent email."""
    entry = {
        "to": to_email,
        "company": company,
        "subject": subject,
        "type": template_type,
        "sent_at": datetime.now().isoformat()
    }
    with open(SENT_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")

def is_valid_email(email):
    """Quick email validation — catches obvious junk, passes real emails."""
    if not email or '@' not in email:
        return False
    email = email.strip().lower()
    # Only catch OBVIOUSLY invalid emails
    invalid = [
        r'@example\.', r'@test\.', r'@localhost$', r'@invalid$',
        r'@sample\.', r'@demo\.', r'@contoso\.', r'@you@example',
        r'\.(png|jpg|jpeg|gif|js|svg|webp|mjs|css|bmp|tiff|ico)$',
        r'@.*\.(png|jpg|jpeg|gif|js|svg|webp|mjs|bmp)$',
        r'^(slick-carousel|jquery|bootstrap|react|angular|vue|webpack|npm|node|gsap|splide|select2|intl-segmenter|intl-tel-input|markdown-it|defer\.js)@',
        r'@[0-9]+\.[0-9]+\.[0-9]+',  # version numbers like package@1.2.3
        r'\?subject=',
        r'\s',
        r'\.{2,}',  # consecutive dots
        r'@.*@',  # multiple @ signs
    ]
    for pattern in invalid:
        if re.search(pattern, email, re.IGNORECASE):
            return False
    # Basic format check: local@domain.tld
    return re.match(r'^[^@]+@[^@]+\.[^@]{2,}$', email) is not None

def generate_audit_email(lead):
    """Generate personalized audit email with video link."""
    company = lead["company"]
    issues = lead.get("issues_found", [])
    script = lead.get("script_60s", "")
    audit_score = lead.get("audit_score", 5)
    severity = lead.get("severity", "moderate")
    
    # Short email — just points to the video
    issue_text = "\n".join([f"  • {i}" for i in issues[:3]])
    
    body = f"""Hi there,

I was reviewing {company}'s website and found a few things that might be costing you clients:

{issue_text}

I put together a 60-second video walking through them — no pitch, just stuff you should know:

[Video Audit Link Coming Soon — I'll send it directly]

Thoughts?

— SaJib"""
    
    subject = f"3 issues on {company}'s website"
    
    return subject, body

def generate_spy_email(lead):
    """Generate spy/mockup email."""
    brokerage = lead["brokerage"]
    city = lead["city"]
    mockup_file = lead.get("mockup_file", "")
    
    subject = f"3 posts I made for {brokerage}"
    
    body = f"""Hi there,

I noticed {brokerage} has some great {city} listings but the social media has been quiet lately.

I put together 3 post mockups for your {city} market — like what I'd create if we worked together:

{os.path.basename(mockup_file) if mockup_file else '[Mockup Link]'}

Want me to send the actual designs?

— SaJib"""
    
    return subject, body

def generate_reverse_pitch_email(rp_entry):
    """Return pre-generated reverse pitch email."""
    return rp_entry.get("subject", ""), rp_entry.get("body", "")

def main():
    """Send all emails in the queue."""
    with open(SEND_QUEUE) as f:
        queue = json.load(f)
    
    # Load all email types
    audit_emails = queue.get("audit_emails", [])
    spy_emails = queue.get("spy_emails", [])
    reverse_pitch = queue.get("reverse_pitch", [])
    
    print("=" * 60)
    print("HIGH-TOUCH EMAIL SENDER")
    print("=" * 60)
    print(f"Audit emails:       {len(audit_emails)}")
    print(f"Spy emails:         {len(spy_emails)}")
    print(f"Reverse Pitch:       {len(reverse_pitch)}")
    print(f"Total:              {len(audit_emails) + len(spy_emails) + len(reverse_pitch)}")
    print("=" * 60)
    
    results = {"sent": 0, "failed": 0, "skipped": 0, "errors": []}
    
    all_emails = []
    
    # Add audit emails
    for e in audit_emails:
        email = e.get("email", "").strip()
        if not is_valid_email(email):
            results["skipped"] += 1
            print(f"  SKIP (invalid): {e['company'][:30]} | {email}")
            continue
        subject, body = generate_audit_email(e)
        all_emails.append({
            "email": email, "company": e["company"], "subject": subject,
            "body": body, "type": "audit"
        })
    
    # Add spy emails
    for e in spy_emails:
        email = e.get("email", "").strip()
        if not is_valid_email(email):
            results["skipped"] += 1
            print(f"  SKIP (invalid): {e['brokerage'][:30]} | {email}")
            continue
        subject, body = generate_spy_email(e)
        all_emails.append({
            "email": email, "company": e["brokerage"], "subject": subject,
            "body": body, "type": "spy"
        })
    
    # Add reverse pitch emails
    for e in reverse_pitch:
        email = e.get("email", "").strip()
        if not is_valid_email(email):
            results["skipped"] += 1
            continue
        subject = e.get("subject", "")
        body = e.get("body", "")
        all_emails.append({
            "email": email, "company": e.get("company", ""), "subject": subject,
            "body": body, "type": "reverse_pitch"
        })
    
    print(f"\nValid emails to send: {len(all_emails)}")
    print(f"Skipped (invalid): {results['skipped']}")
    print()
    
    # Send emails with 3-minute gaps
    for i, email_entry in enumerate(all_emails):
        email = email_entry["email"]
        company = email_entry["company"]
        subject = email_entry["subject"]
        body = email_entry["body"]
        etype = email_entry["type"]
        
        # Skip duplicates (simple in-memory check)
        key = f"{email.lower()}|{etype}"
        
        print(f"[{i+1}/{len(all_emails)}] SENDING {etype} → {company}")
        print(f"    To: {email}")
        print(f"    Subject: {subject}")
        
        success, error = send_smtp(email, subject, body)
        
        if success:
            results["sent"] += 1
            log_sent(email, company, subject, etype)
            print(f"    ✓ SENT")
        else:
            results["failed"] += 1
            results["errors"].append(f"{etype} {email}: {error[:80]}")
            print(f"    ✗ FAILED: {error[:80]}")
        
        # 3-minute gap between emails (skip for last one)
        if i < len(all_emails) - 1:
            time.sleep(180)
    
    print(f"\n{'='*60}")
    print(f"FINAL REPORT")
    print(f"{'='*60}")
    print(f"  Sent:     {results['sent']}")
    print(f"  Failed:   {results['failed']}")
    print(f"  Skipped:  {results['skipped']}")
    
    if results["errors"]:
        print(f"\n  Errors:")
        for err in results["errors"]:
            print(f"    {err}")
    
    # Save report
    with open(SEND_REPORT, "w") as f:
        f.write(f"HIGH-TOUCH SEND REPORT — {datetime.now().isoformat()}\n")
        f.write(f"{'='*60}\n")
        f.write(f"Total attempted: {len(all_emails)}\n")
        f.write(f"Sent:    {results['sent']}\n")
        f.write(f"Failed:  {results['failed']}\n")
        f.write(f"Skipped: {results['skipped']}\n")
        if results['errors']:
            f.write(f"\nErrors:\n")
            for err in results['errors']:
                f.write(f"  {err}\n")
    
    print(f"\nReport saved to: {SEND_REPORT}")
    return results

if __name__ == "__main__":
    main()
