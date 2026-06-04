# NanoSoft 24-Hour Autonomous Plan
# Last updated: June 4, 2026

## Every 3 Hours (Auto-Pilot)
1. SCOUT — 52 ddgs queries → find 30-50 new WL agency leads
2. ENRICH — scrape services, WL signals, pain points (new leads only)
3. JUDGE — score 0-10, threshold 7+ to qualify
4. SEND T1 — to all qualified leads (180s delay between each)
5. CHECK REPLIES — scan inbox, classify, update CRM

## Every 30 Minutes
- Reply monitor — scan inbox for new replies
- If INTERESTED → immediate alert to CEO
- If BOUNCE → find replacement email, resend

## Daily Caps
- Max 80 emails sent per day
- Max 20 emails per hour
- 3-minute gap between sends
- If bounce rate > 5% → pause all sends, alert CEO

## Follow-Up Schedule
- T2 (social proof) — June 6, 08:00 BD → all T1 Sent leads
- T3 (disarming) — June 11, 08:00 BD → all T2 Sent leads
- T4 (breakup) — June 16, 08:00 BD → all T3 Sent leads

## Deliverability Rules
- All email via Gmail API (never from VPS IP)
- List-Unsubscribe header on every email
- No links in T1 emails
- No banned words, no hyphens, no em dashes
- Under 100 words per email
- 4th grade English only
- Never start with "I" or "We"
- One email per lead per day max

## Current Stats (June 4, ~04:48 BD)
- T1 emails sent: 71
- Unique companies: 66
- New leads in CRM: 34 (just added)
- Qualified and sending: 14
- Replies: 0 (normal — expect first replies June 4-7)
- Bounces: 5 (all fixed with replacement emails)

## Key Metrics to Track
- Daily send count (cap: 80)
- Bounce rate (alert if > 5%)
- Reply rate (expected: 2-5%)
- Qualified lead rate (expected: 30-40% of scraped)

## What Gets CEO Alert
1. Any INTERESTED reply
2. Bounce rate > 5%
3. System error or script failure
4. Daily summary (sent, new leads, replies)
