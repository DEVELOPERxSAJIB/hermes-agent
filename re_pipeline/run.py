"""Cron job runner for RE Pipeline"""
import sys
sys.path.insert(0, '/home/ubuntu/nanosoft/re_pipeline')

from daily import re_morning_routine as morning_routine, re_evening_routine as evening_routine, re_weekly_report as weekly_report
from sheets import get_leads

def run_morning():
    """Morning routine: send follow-ups + add new leads."""
    print("=== MORNING ROUTINE ===")
    results = morning_routine()
    print(f"Follow-ups sent: {results['follow_ups_sent']}")
    print(f"New leads added: {results['new_leads_added']}")
    print(f"Touch 1 sent: {results['touch1_sent']}")
    if results['errors']:
        print(f"Errors: {results['errors']}")
    return results

def run_evening():
    """ evening routine: generate daily summary."""
    print("=== EVENING ROUTINE ===")
    summary = evening_routine()
    print(summary)
    return summary

def run_weekly():
    """Weekly report (Sunday)."""
    print("=== WEEKLY REPORT ===")
    report = weekly_report()
    print(report)
    return report

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("routine", choices=["morning", "evening", "weekly"])
    args = parser.parse_args()

    if args.routine == "morning":
        run_morning()
    elif args.routine == "evening":
        run_evening()
    elif args.routine == "weekly":
        run_weekly()
