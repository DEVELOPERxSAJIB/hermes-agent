import subprocess, json, sys

message = (
    "\U0001f4ca *NanoSoft Daily Report* \u2014 2026-06-07 16:01 BD\n\n"
    "\U0001f4cb *Lead Overview*\n"
    "\u2022 Total leads: 489\n"
    "\u2022 Qualified (unsent): 20\n\n"
    "\U0001f4e4 *Outreach Progress*\n"
    "\u2022 T1 Sent: 66\n"
    "\u2022 T2 Sent: 122\n"
    "\u2022 T3 Sent: 0\n"
    "\u2022 T4 Sent: 0\n"
    "\u2022 Total Sent: 188\n\n"
    "\U0001f4ac *Engagement*\n"
    "\u2022 Replied: 12\n"
    "\u2022 Interested: 2\n\n"
    "\u26a0\ufe0f *Issues*\n"
    "\u2022 Bounced: 2\n"
    "\u2022 Unqualified: 219"
)

print(message)
