#!/usr/bin/env python3
"""
Stock Monitor Scheduler
=======================
Runs the stock monitoring reports on schedule.

Usage:
    python scheduler.py          # Run scheduler daemon
    python scheduler.py --test   # Run all reports once immediately
    python scheduler.py --premarket   # Run premarket report only
    python scheduler.py --postmarket  # Run postmarket report only
    python scheduler.py --weekly      # Run weekly report only
"""

import schedule
import time
import logging
import argparse
from datetime import datetime
import pytz
import sys
import os

from config_loader import load_config, setup_logging

setup_logging()
logger = logging.getLogger(__name__)


def run_premarket():
    """Run pre-market report."""
    logger.info("Running pre-market report...")
    try:
        from premarket_report import main as premarket_main
        premarket_main()
    except Exception as e:
        logger.exception(f"Error in pre-market report: {e}")


def run_postmarket():
    """Run post-market report."""
    logger.info("Running post-market report...")
    try:
        from postmarket_report import main as postmarket_main
        postmarket_main()
    except Exception as e:
        logger.exception(f"Error in post-market report: {e}")


def run_weekly():
    """Run weekly report."""
    logger.info("Running weekly report...")
    try:
        from weekly_report import main as weekly_main
        weekly_main()
    except Exception as e:
        logger.exception(f"Error in weekly report: {e}")


def is_market_day() -> bool:
    """Check if today is a trading day using NYSE exchange calendar.

    Covers all NYSE holidays including:
    New Year's, MLK Day, Presidents Day, Good Friday, Memorial Day,
    Juneteenth, Independence Day, Labor Day, Thanksgiving, Christmas,
    and any ad-hoc closures.
    """
    try:
        import exchange_calendars as xcals
        import pandas as pd
        nyse = xcals.get_calendar("XNYS")
        now = datetime.now(pytz.timezone('America/New_York'))
        return nyse.is_session(pd.Timestamp(now.date()))
    except ImportError:
        logger.warning("exchange_calendars not installed, using basic weekend check")
        now = datetime.now(pytz.timezone('America/New_York'))
        return now.weekday() < 5
    except Exception as e:
        logger.warning(f"Error checking market calendar: {e}, using basic weekend check")
        now = datetime.now(pytz.timezone('America/New_York'))
        return now.weekday() < 5


def run_premarket_if_market_day():
    """Run pre-market report only on trading days."""
    if is_market_day():
        run_premarket()
    else:
        logger.info("Skipping pre-market report (not a trading day)")


def run_postmarket_if_market_day():
    """Run post-market report only on trading days."""
    if is_market_day():
        run_postmarket()
    else:
        logger.info("Skipping post-market report (not a trading day)")


def setup_schedule(config: dict):
    """Set up the job schedule based on configuration."""
    schedule_config = config.get('schedule', {})
    
    premarket_time = schedule_config.get('premarket_time', '06:30')
    postmarket_time = schedule_config.get('postmarket_time', '16:30')
    weekly_day = schedule_config.get('weekly_day', 'saturday')
    weekly_time = schedule_config.get('weekly_time', '09:00')
    
    logger.info(f"Setting up schedule:")
    logger.info(f"  Pre-market: {premarket_time} EST on trading days")
    logger.info(f"  Post-market: {postmarket_time} EST on trading days")
    logger.info(f"  Weekly: {weekly_day} at {weekly_time} EST")
    
    # Schedule pre-market report (6:30 AM EST, Monday-Friday)
    schedule.every().monday.at(premarket_time).do(run_premarket_if_market_day)
    schedule.every().tuesday.at(premarket_time).do(run_premarket_if_market_day)
    schedule.every().wednesday.at(premarket_time).do(run_premarket_if_market_day)
    schedule.every().thursday.at(premarket_time).do(run_premarket_if_market_day)
    schedule.every().friday.at(premarket_time).do(run_premarket_if_market_day)
    
    # Schedule post-market report (4:30 PM EST, Monday-Friday)
    schedule.every().monday.at(postmarket_time).do(run_postmarket_if_market_day)
    schedule.every().tuesday.at(postmarket_time).do(run_postmarket_if_market_day)
    schedule.every().wednesday.at(postmarket_time).do(run_postmarket_if_market_day)
    schedule.every().thursday.at(postmarket_time).do(run_postmarket_if_market_day)
    schedule.every().friday.at(postmarket_time).do(run_postmarket_if_market_day)
    
    # Schedule weekly report
    if weekly_day.lower() == 'saturday':
        schedule.every().saturday.at(weekly_time).do(run_weekly)
    elif weekly_day.lower() == 'sunday':
        schedule.every().sunday.at(weekly_time).do(run_weekly)
    elif weekly_day.lower() == 'friday':
        schedule.every().friday.at(weekly_time).do(run_weekly)


def run_scheduler():
    """Run the scheduler loop."""
    config = load_config()
    setup_schedule(config)
    
    logger.info("=" * 50)
    logger.info("Stock Monitor Scheduler Started")
    logger.info(f"Current time (EST): {datetime.now(pytz.timezone('America/New_York')).strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)
    logger.info("Waiting for scheduled jobs...")
    logger.info("Press Ctrl+C to stop")
    
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Stock Monitor Scheduler')
    parser.add_argument('--test', action='store_true', help='Run all reports immediately')
    parser.add_argument('--premarket', action='store_true', help='Run pre-market report only')
    parser.add_argument('--postmarket', action='store_true', help='Run post-market report only')
    parser.add_argument('--weekly', action='store_true', help='Run weekly report only')
    
    args = parser.parse_args()
    
    if args.test:
        logger.info("Running all reports in test mode...")
        run_premarket()
        run_postmarket()
        run_weekly()
    elif args.premarket:
        run_premarket()
    elif args.postmarket:
        run_postmarket()
    elif args.weekly:
        run_weekly()
    else:
        run_scheduler()


if __name__ == "__main__":
    main()
