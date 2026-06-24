import imaplib, re, json
from datetime import datetime, timedelta

SMTP_USER = 'nanosoftagency007@gmail.com'
SMTP_PASS = 'wgxo ddup cdol kupl'

try:
    mail = imaplib.IMAP4_SSL('imap.gmail.com')
    mail.login(SMTP_USER, SMTP_PASS)
    mail.select('INBOX')

    since_date = (datetime.now() - timedelta(hours=24)).strftime('%d-%b-%Y')
    status, messages = mail.search(None, f'(SINCE {since_date})')

    if status == 'OK':
        msg_ids = messages[0].split()
        replies = []
        for msg_id in msg_ids[-100:]:
            try:
                status2, msg_data = mail.fetch(msg_id, '(RFC822.HEADER)')
                if status2 != 'OK':
                    continue
                header = msg_data[0][1].decode('utf-8', errors='ignore')
                from_line = header.split('From:')[-1].split('\n')[0] if 'From:' in header else ''
                from_match = re.search(r'<([^>]+)>', from_line)
                subj_match = re.search(r'Subject: (.+)', header)
                if from_match:
                    sender = from_match.group(1)
                    subject = subj_match.group(1).strip() if subj_match else '(no subject)'
                    if sender == SMTP_USER:
                        continue
                    skip_keywords = [
                        'bounce', 'delivery failure', 'auto-reply', 'out of office',
                        'vacation reply', 'mailer-daemon', 'delivery status',
                        'automatic reply', 'noreply', 'no-reply', 'postmaster',
                        'mail delivery', 'shop faster'
                    ]
                    if any(k in subject.lower() or k in sender.lower() for k in skip_keywords):
                        continue
                    replies.append({'from': sender, 'subject': subject})
            except Exception:
                continue
        print(json.dumps(replies, indent=2))
    mail.logout()
except Exception as e:
    print(json.dumps({'error': str(e)}))
