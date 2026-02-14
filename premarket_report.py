#!/usr/bin/env python3
"""
Pre-Market Report Generator
===========================
Generates and sends the morning pre-market briefing email.
Run this at 6:30 AM EST (before market open at 9:30 AM).
"""

import logging
from datetime import datetime
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config_loader import load_config, setup_logging
from data_fetcher import StockDataFetcher, FuturesDataFetcher, TrendsFetcher
from news_fetcher import NewsFetcher
from email_generator import EmailGenerator
from email_sender import EmailSenderFactory
from notion_watchlist import get_watchlist
from signal_analyzer import generate_signal_digest

setup_logging()
logger = logging.getLogger(__name__)


def _send_error_alert(config: dict, message: str):
    """Send error alert email using existing email infrastructure."""
    try:
        from email_sender import EmailSenderFactory
        sender = EmailSenderFactory.from_config(config)
        email_config = config['email']
        recipient = email_config.get('recipient_email', email_config.get('sender_email'))
        html = f"""<div style="font-family: monospace; background: #1a1a2e; color: #f5f2eb; padding: 20px;">
            <h2 style="color: #FF1744;">Stock Monitor Alert</h2>
            <p>{message}</p>
            <p>Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>Action: Check Notion token and watchlist database.</p>
        </div>"""
        sender.send_email(recipient, f"[ALERT] Stock Monitor Error", html)
    except Exception as e:
        logger.error(f"Could not send error alert: {e}")


def main():
    """Generate and send pre-market report."""
    logger.info("=" * 50)
    logger.info("Starting Pre-Market Report Generation")
    logger.info("=" * 50)
    
    try:
        # Load configuration
        config = load_config()
        symbols = get_watchlist()  # Fetch from Notion (source of truth)
        email_config = config['email']

        if len(symbols) == 0:
            logger.critical("ALERT: Watchlist returned 0 symbols! Aborting report.")
            _send_error_alert(config, "Watchlist returned 0 symbols - Notion may be down or token expired")
            return

        if len(symbols) < 10:
            logger.warning(f"ALERT: Only {len(symbols)} symbols returned (expected ~80+)")

        logger.info(f"Tracking {len(symbols)} symbols")
        
        # Initialize components
        stock_fetcher = StockDataFetcher(symbols)
        futures_fetcher = FuturesDataFetcher()
        news_fetcher = NewsFetcher(max_news_per_stock=config['report'].get('news_per_stock', 3))
        email_generator = EmailGenerator()
        email_sender = EmailSenderFactory.from_config(config)
        
        # Fetch futures data
        logger.info("Fetching futures data...")
        futures = futures_fetcher.get_futures()
        logger.info(f"Got futures data for {len(futures)} indices")
        
        # Fetch pre-market data
        logger.info("Fetching pre-market data...")
        premarket_data = stock_fetcher.get_premarket_data()
        logger.info(f"Got pre-market data for {len(premarket_data)} symbols")
        
        # Fetch current quotes (for context)
        logger.info("Fetching current quotes...")
        quotes = stock_fetcher.get_batch_quotes()
        logger.info(f"Got quotes for {len(quotes)} symbols")

        if len(quotes) < len(symbols) * 0.5:
            logger.warning(f"Data quality issue: Only got quotes for {len(quotes)}/{len(symbols)} symbols")

        # Fetch earnings calendar
        logger.info("Fetching earnings calendar...")
        earnings = stock_fetcher.get_earnings_calendar(days_ahead=14)
        logger.info(f"Found {len(earnings)} upcoming earnings")
        
        # Fetch dividend calendar
        logger.info("Fetching dividend calendar...")
        dividends = stock_fetcher.get_dividend_calendar(days_ahead=30)
        logger.info(f"Found {len(dividends)} upcoming ex-dividend dates")
        
        # Fetch news for big pre-market movers
        logger.info("Fetching news...")
        
        # Get top pre-market movers for news
        sorted_premarket = sorted(
            [(s, d) for s, d in premarket_data.items() if d.get('pre_market_change_percent')],
            key=lambda x: abs(x[1].get('pre_market_change_percent', 0)),
            reverse=True
        )
        top_movers = [s for s, d in sorted_premarket[:10]]
        
        # Fetch news for movers
        symbol_names = {s: quotes.get(s, {}).get('name', s) for s in top_movers}
        news = news_fetcher.get_news_for_watchlist(top_movers, symbol_names)
        
        # Fetch market news
        market_news = news_fetcher.get_market_news()
        logger.info(f"Got {len(market_news)} market news items")

        # Fetch world & US news
        logger.info("Fetching world & US news...")
        world_news = news_fetcher.get_world_us_news(max_items=6)
        logger.info(f"Got {len(world_news)} world/US news items")

        # Fetch Google Trends data for sentiment (conservative rate limiting)
        trends_data = {}
        try:
            logger.info("Fetching Google Trends data...")
            trends_fetcher = TrendsFetcher(cache_duration_minutes=240)  # 4-hour cache
            # Get company names for better search results
            company_names = {s: quotes.get(s, {}).get('name', s) for s in top_movers}
            trends_data = trends_fetcher.get_trends(top_movers, company_names, max_symbols=8)
            logger.info(f"Got trends data for {len(trends_data)} symbols")
        except Exception as e:
            logger.warning(f"Could not fetch trends data: {e}")
            # Continue without trends - it's optional

        # Generate signal digest via Grok
        signal_digest = None
        try:
            logger.info("Generating signal digest via Grok...")
            signal_digest = generate_signal_digest('PRE_MARKET')
            if signal_digest:
                logger.info("Got signal digest")
            else:
                logger.info("Signal digest skipped (no API key or no data)")
        except Exception as e:
            logger.warning(f"Could not generate signal digest: {e}")

        # Generate email
        logger.info("Generating email...")
        html_content = email_generator.generate_premarket_report(
            futures=futures,
            premarket_data=premarket_data,
            quotes=quotes,
            earnings=earnings,
            dividends=dividends,
            news=news,
            market_news=market_news,
            world_news=world_news,
            trends_data=trends_data,
            signal_digest=signal_digest
        )
        
        # Save a local copy for debugging
        debug_path = f'reports/premarket_{datetime.now().strftime("%Y%m%d_%H%M")}.html'
        os.makedirs('reports', exist_ok=True)
        with open(debug_path, 'w') as f:
            f.write(html_content)
        logger.info(f"Saved debug copy to {debug_path}")
        
        # Send email
        recipient = email_config.get('recipient_email', email_config.get('sender_email'))
        
        if recipient and email_config.get('sender_email') and email_config.get('sender_password'):
            logger.info(f"Sending email to {recipient}...")
            success = email_sender.send_premarket_report(recipient, html_content)
            
            if success:
                logger.info("✓ Pre-market report sent successfully!")
            else:
                logger.error("✗ Failed to send email")
        else:
            logger.warning("Email not configured. Report saved locally only.")
            logger.info(f"View the report at: {debug_path}")
        
        logger.info("Pre-market report generation complete")
        
    except Exception as e:
        logger.exception(f"Error generating pre-market report: {e}")
        raise


if __name__ == "__main__":
    main()
