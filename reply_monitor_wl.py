#!/usr/bin/python3
"""
NanoSoft QUILL-WL — Reply Monitor v2
Checks Gmail inbox for replies to sent outreach emails.
Updates CRM: Reply Status, Reply Date, Reply Snippet.

FIXES vs v1:
- Match replies by DOMAIN not exact email (canned.response@, noreply@, etc)
- Better auto-reply detection (after-hours, canned, noreply, etc)
- Better email extraction from From header
- Dedup by company not just email
- Handle OOOauto-replies with forwarding contacts (extract real person)
"""
import json, os, re, sys, time
from datetime import datetime, timezone, timedelta

BD_TZ = timezone(timedelta(hours=6))
NANOSOFT_DIR = "/home/ubuntu/nanosoft"
SENT_LOG = os.path.join(NANOSOFT_DIR, "emails_sent_wl.jsonl")
REPLY_LOG = os.path.join(NANOSOFT_DIR, "replies_wl.jsonl")
TOKEN_FILE = os.path.join(NANOSOFT_DIR, "gmail_token.json")

sys.path.insert(0, NANOSOFT_DIR)

def log(msg):
    ts = datetime.now(BD_TZ).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [REPLY-MONITOR] {msg}"
    print(line, flush=True)
    with open(os.path.join(NANOSOFT_DIR, "quill_wl.log"), 'a') as f:
        f.write(line + "\n")

def get_gmail_service():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    with open(TOKEN_FILE) as f:
        token_data = json.load(f)

    creds = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=token_data.get("client_id"),
        client_secret=token_data.get("client_secret"),
        scopes=token_data.get("scopes"),
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_data["token"] = creds.token
        with open(TOKEN_FILE, "w") as f:
            json.dump(token_data, f)

    return build("gmail", "v1", credentials=creds)

def extract_email_from_header(from_header):
    """Extract email address from From header like 'Name <email@domain.com>' or plain email."""
    # Try angle brackets first
    m = re.search(r'<([^>]+)>', from_header)
    if m:
        return m.group(1).lower().strip()
    # Try plain email
    m = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', from_header)
    if m:
        return m.group(0).lower().strip()
    return from_header.lower().strip()

def extract_domain(email):
    """Extract domain from email: hello+canned.response@fulcrum.rocks -> fulcrum.rocks"""
    if '@' in email:
        return email.split('@')[1].lower().strip()
    return ''

def build_sent_index():
    """
    Build multi-index for fast reply matching:
    - by_email: exact email -> entry
    - by_domain: domain -> [entries]  (for matching noreply@, canned.response@, etc)
    - by_company: company name -> entry
    """
    by_email = {}
    by_domain = {}
    by_company = {}
    try:
        with open(SENT_LOG) as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    email = entry.get("to", "").lower().strip()
                    company = entry.get("company", "").lower().strip()
                    if email:
                        by_email[email] = entry
                        domain = extract_domain(email)
                        if domain:
                            by_domain.setdefault(domain, []).append(entry)
                    if company:
                        by_company[company] = entry
    except:
        pass
    return by_email, by_domain, by_company

def match_reply_to_sent(sender_email, subject, by_email, by_domain, by_company):
    """
    Match a reply to our sent email. Returns (sent_entry, match_method) or (None, None).
    
    Matching priority:
    1. Exact email match (hello@fulcrum.rocks replied from hello@fulcrum.rocks)
    2. Same domain match (hello+canned.response@fulcrum.rocks -> fulcrum.rocks)
    3. Subject contains company name
    """
    # 1. Exact match
    if sender_email in by_email:
        return by_email[sender_email], "exact"
    
    # 2. Domain match
    domain = extract_domain(sender_email)
    if domain and domain in by_domain:
        candidates = by_domain[domain]
        if len(candidates) == 1:
            return candidates[0], "domain"
        # Multiple candidates — try to match by subject
        for c in candidates:
            company = c.get("company", "")
            if company and company.lower() in subject.lower():
                return c, "domain+subject"
        # Return most recent
        return candidates[-1], "domain-recent"
    
    # 3. Subject match — extract company from subject like "Re: quick question about Saritasa"
    subject_company = re.search(r'(?:re:|fwd:)?\s*(?:quick question about|overflow question|capacity at)\s+(\w+)', subject, re.IGNORECASE)
    if subject_company:
        company_name = subject_company.group(1).lower()
        if company_name in by_company:
            return by_company[company_name], "subject"
    
    return None, None

def get_replied_companies():
    """Get set of companies that already have replies logged."""
    replied = set()
    try:
        with open(REPLY_LOG) as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    company = entry.get("company", "").lower().strip()
                    if company:
                        replied.add(company)
    except:
        pass
    return replied

def extract_snippet(body, max_chars=200):
    """Extract first meaningful line from reply body."""
    lines = body.split('\n')
    clean = []
    for line in lines:
        if line.strip().startswith('>'):
            continue
        if line.strip() and len(line.strip()) > 3:
            clean.append(line.strip())
        if len(clean) >= 3:
            break
    snippet = ' '.join(clean)[:max_chars]
    return snippet

def classify_reply(snippet, from_email='', subject=''):
    """Classify reply intent. Uses snippet, from_email, and subject for better detection."""
    s = snippet.lower()
    subj = subject.lower()
    email_lower = from_email.lower()
    
    # Auto-reply signals — STRONG indicators
    auto_reply_words = [
        'out of office', 'ooo', 'on leave', 'auto-reply', 'automatic reply',
        'after-hours', 'after hours', 'canned response', 'canned.response',
        'noreply', 'no-reply', 'notification only', 'do not respond',
        'do not reply', 'this is an automated', 'automated message',
        'team members will review', 'will get back to you shortly',
        'has reached us outside', 'away on maternity', 'away on vacation',
        'currently away', 'out of the office', 'on annual leave',
        'will return on', 'returning on', 'back on',
        'automatically generated by gmail', 'auto-generated message',
        'this message was automatically', 'delivery status notification',
        'mail delivery failed', 'delivery failure', 'bounce', 'undeliverable',
    ]
    if any(w in s for w in auto_reply_words):
        return 'Auto-Reply'
    if any(w in subj for w in ['out of office', 'ooo', 'auto-reply', 'automatic reply', 'after hours', 'unsubscribe']):
        return 'Auto-Reply'
    if any(w in email_lower for w in ['noreply', 'no-reply', 'canned.response', '+canned', 'donotreply']):
        return 'Auto-Reply'
    
    # Interested signals
    interested_words = [
        'interested', 'tell me more', 'sounds good', 'let\'s talk', 'call me',
        'schedule', 'book a', 'send me', 'proposal', 'pricing', 'cost', 'rate',
        'can we chat', 'let\'s set up', 'love to learn more', 'keen to',
        'happy to discuss', 'open to', 'worth exploring',
    ]
    if any(w in s for w in interested_words):
        return 'Interested'
    
    # Not interested signals
    not_interested_words = [
        'not interested', 'no thanks', 'unsubscribe', 'remove me',
        'stop sending', 'wrong person', 'not for us', 'pass on this',
        'declined', 'no need', 'not looking', 'already have',
    ]
    if any(w in s for w in not_interested_words):
        return 'Not Interested'
    
    # Confused
    confused_words = ['who is', 'what is this', 'how did you', 'not sure what', 'spam']
    if any(w in s for w in confused_words):
        return 'Confused'
    
    return 'Other'

def check_bounces(service):
    """Check for bounced emails and mark them in CRM."""
    try:
        crm = get_crm()
        
        results = service.users().messages().list(
            userId='me',
            q='from:mailer-daemon@googlemail.com OR subject:undeliverable after:2026/05/01',
            maxResults=50
        ).execute()
        
        msgs = results.get('messages', [])
        if not msgs:
            return 0
        
        bounced_count = 0
        for m in msgs:
            msg = service.users().messages().get(userId='me', id=m['id']).execute()
            snippet = msg.get('snippet', '')
            
            # Extract ALL emails from snippet, find the one that matches CRM
            all_emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', snippet)
            
            try:
                wl = crm.get_wl_all()
                for bounced_email_raw in all_emails:
                    bounced_email = bounced_email_raw.lower().strip().rstrip('.')
                    if any(x in bounced_email for x in ['mailer-daemon', 'googlemail', 'noreply', 'postmaster']):
                        continue
                    
                    for lead in wl:
                        lead_email = lead.get('Email', '').lower().strip()
                        if lead_email == bounced_email and lead.get('Status') not in ('Bounced', 'T1 Sent', 'T2 Sent', 'T3 Sent', 'T4 Sent'):
                            crm.update_wl_lead(lead.get('Company Name', ''), {
                                'Status': 'Bounced',
                            })
                            log(f"  BOUNCE: {lead.get('Company Name','?')} | {bounced_email}")
                            bounced_count += 1
                            break
            except:
                pass
        
        return bounced_count
    except:
        return 0


def main():
    log("Starting reply check...")

    # Check if token is known to be dead
    dead_flag = os.path.join(NANOSOFT_DIR, "GMAIL_TOKEN_DEAD")
    if os.path.exists(dead_flag):
        log("⚠ GMAIL TOKEN DEAD — Skipping reply check")
        log("⚠ Manual re-authentication required")
        return

    try:
        service = get_gmail_service()
    except Exception as e:
        error_str = str(e)
        log(f"Cannot connect to Gmail: {e}")
        # Check if token is dead — needs human re-auth
        if 'invalid_grant' in error_str or 'Token has been expired' in error_str:
            log("⚠ GMAIL TOKEN DEAD — Manual re-authentication required")
            log("⚠ Run: cd /home/ubuntu/nanosoft && python3 gmail_auth.py")
            # Write flag file so other scripts can detect this
            try:
                with open(os.path.join(NANOSOFT_DIR, "GMAIL_TOKEN_DEAD"), 'w') as f:
                    f.write(f"Token died at {datetime.now(BD_TZ).isoformat()}\nError: {error_str}")
            except:
                pass
        return

    by_email, by_domain, by_company = build_sent_index()
    replied_companies = get_replied_companies()

    total_sent = len(by_email)
    total_domains = len(by_domain)
    if not total_sent:
        log("No sent emails found. Nothing to check.")
        return

    log(f"Tracking {total_sent} sent emails ({total_domains} domains), {len(replied_companies)} companies already replied")

    # ── Check for bounces first ──
    log("Checking for bounced emails...")
    bounced = check_bounces(service)
    if bounced:
        log(f"  {bounced} bounced emails detected and marked in CRM")

    # ── Check for replies ──
    # Search inbox for recent messages
    try:
        results = service.users().messages().list(
            userId='me',
            q='newer_than:14d in:inbox',
            maxResults=100
        ).execute()
    except Exception as e:
        log(f"Gmail list error: {e}")
        return

    messages = results.get('messages', [])
    log(f"Found {len(messages)} recent inbox messages to scan")

    new_replies = 0

    for msg_ref in messages:
        try:
            msg = service.users().messages().get(
                userId='me', id=msg_ref['id'], format='metadata',
                metadataHeaders=['From', 'Subject', 'Date', 'In-Reply-To', 'References']
            ).execute()
        except:
            continue

        headers = {h['name'].lower(): h['value'] for h in msg.get('payload', {}).get('headers', [])}

        from_header = headers.get('from', '')
        sender_email = extract_email_from_header(from_header)
        subject = headers.get('subject', '')
        date_str = headers.get('date', '')

        # Match this reply to a sent email
        sent_entry, match_method = match_reply_to_sent(
            sender_email, subject, by_email, by_domain, by_company
        )
        
        if not sent_entry:
            continue  # Not related to our outreach

        company = sent_entry.get('company', '')
        
        # Skip if this company already has a reply logged
        if company.lower().strip() in replied_companies:
            continue

        # Get message body for classification
        try:
            full_msg = service.users().messages().get(
                userId='me', id=msg_ref['id'], format='full'
            ).execute()
            body_data = full_msg.get('payload', {}).get('body', {})
            body_text = ''
            if body_data.get('data'):
                import base64
                body_text = base64.urlsafe_b64decode(body_data['data']).decode('utf-8', errors='ignore')
            elif full_msg.get('payload', {}).get('parts'):
                for part in full_msg['payload']['parts']:
                    if part.get('mimeType') == 'text/plain' and part.get('body', {}).get('data'):
                        import base64
                        body_text = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                        break
        except:
            body_text = ''

        snippet = extract_snippet(body_text)
        classification = classify_reply(snippet, sender_email, subject)

        reply_entry = {
            "from_email": sender_email,
            "from_name": from_header,
            "company": company,
            "template": sent_entry.get("template", ""),
            "original_subject": sent_entry.get("subject", ""),
            "reply_subject": subject,
            "reply_date": date_str,
            "snippet": snippet[:300] if snippet else msg.get('snippet', '')[:300],
            "classification": classification,
            "match_method": match_method,
            "detected_at": datetime.now(BD_TZ).isoformat(),
            "message_id": msg_ref['id'],
        }

        with open(REPLY_LOG, 'a') as f:
            f.write(json.dumps(reply_entry) + "\n")

        replied_companies.add(company.lower().strip())
        new_replies += 1

        log(f"  REPLY: {company} | {classification} | match={match_method} | {snippet[:80]}")

        # Update CRM
        try:
            try:
                from crm_cache import get_crm
            except ImportError:
                from crm import get_crm
            crm = get_crm()
            crm.update_wl_lead(company, {
                "Reply Status": classification,
                "Reply Date": datetime.now(BD_TZ).strftime("%Y-%m-%d"),
                "Reply Snippet": snippet[:150] if snippet else '',
            })
            log(f"    CRM updated: {company} -> {classification}")
        except Exception as e:
            log(f"    CRM update failed: {e}")

    log(f"Done. {new_replies} new replies found and logged.")

if __name__ == "__main__":
    main()
