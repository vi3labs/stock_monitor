#!/usr/bin/env python3
"""
Post-Market Report Generator
============================
Generates and sends the end-of-day market close report.
Run this at 4:30 PM EST (after market close at 4:00 PM).
"""

import yaml
import logging
from datetime import datetime
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_fetcher import StockDataFetcher
from news_fetcher import NewsFetcher
from email_generator import EmailGenerator
from email_sender import EmailSenderFactory
from notion_watchlist import get_watchlist

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('stock_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def load_config(config_path: str = 'config.yaml') -> dict:
    """Load configuration from YAML file."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def main():
    """Generate and send post-market report."""
    logger.info("=" * 50)
    logger.info("Starting Post-Market Report Generation")
    logger.info("=" * 50)
    
    try:
        # Load configuration
        config = load_config()
        symbols = get_watchlist()  # Fetch from Notion (source of truth)
        email_config = config['email']
        report_config = config.get('report', {})
        
        logger.info(f"Tracking {len(symbols)} symbols")
        
        # Initialize components
        stock_fetcher = StockDataFetcher(symbols)
        news_fetcher = NewsFetcher(max_news_per_stock=report_config.get('news_per_stock', 3))
        email_generator = EmailGenerator()
        email_sender = EmailSenderFactory.from_config(config)
        
        # Fetch market indices
        logger.info("Fetching market indices...")
        indices = stock_fetcher.get_market_indices()
        logger.info(f"Got data for {len(indices)} indices")
        
        # Fetch all quotes
        logger.info("Fetching quotes for all symbols...")
        quotes = stock_fetcher.get_batch_quotes()
        logger.info(f"Got quotes for {len(quotes)} symbols")
        
        # Fetch after-hours data
        logger.info("Fetching after-hours data...")
        postmarket_data = stock_fetcher.get_postmarket_data()
        logger.info(f"Got after-hours data for {len(postmarket_data)} symbols")
        
        # Identify big movers for news
        big_mover_threshold = config.get('alerts', {}).get('big_mover_threshold', 3.0)
        big_movers = [
            s for s, d in quotes.items() 
            if abs(d.get('change_percent', 0)) >= big_mover_threshold
        ]
        logger.info(f"Found {len(big_movers)} big movers (>{big_mover_threshold}% change)")
        
        # Fetch news for big movers
        logger.info("Fetching news for big movers...")
        if big_movers:
            symbol_names = {s: quotes.get(s, {}).get('name', s) for s in big_movers}
            news = news_fetcher.get_news_for_watchlist(big_movers[:15], symbol_names)
        else:
            # If no big movers, get news for top/bottom performers
            sorted_quotes = sorted(quotes.values(), key=lambda x: x.get('change_percent', 0))
            notable = [s['symbol'] for s in sorted_quotes[:5]] + [s['symbol'] for s in sorted_quotes[-5:]]
            symbol_names = {s: quotes.get(s, {}).get('name', s) for s in notable}
            news = news_fetcher.get_news_for_watchlist(notable, symbol_names)
        
        logger.info(f"Got news for {len(news)} symbols")
        
        # Generate email
        logger.info("Generating email...")
        html_content = email_generator.generate_postmarket_report(
            indices=indices,
            quotes=quotes,
            postmarket_data=postmarket_data,
            news=news
        )
        
        # Save a local copy for debugging
        debug_path = f'reports/postmarket_{datetime.now().strftime("%Y%m%d_%H%M")}.html'
        os.makedirs('reports', exist_ok=True)
        with open(debug_path, 'w') as f:
            f.write(html_content)
        logger.info(f"Saved debug copy to {debug_path}")
        
        # Print summary to console
        logger.info("\n" + "=" * 40)
        logger.info("TODAY'S SUMMARY")
        logger.info("=" * 40)
        
        # Top gainers
        gainers = sorted(quotes.values(), key=lambda x: x.get('change_percent', 0), reverse=True)[:5]
        logger.info("\nTop Gainers:")
        for g in gainers:
            logger.info(f"  {g['symbol']:8} {g.get('change_percent', 0):+6.2f}%  ${g.get('price', 0):.2f}")
        
        # Top losers
        losers = sorted(quotes.values(), key=lambda x: x.get('change_percent', 0))[:5]
        logger.info("\nTop Losers:")
        for l in losers:
            logger.info(f"  {l['symbol']:8} {l.get('change_percent', 0):+6.2f}%  ${l.get('price', 0):.2f}")
        
        logger.info("=" * 40 + "\n")
        
        # Send email
        recipient = email_config.get('recipient_email', email_config.get('sender_email'))
        
        if recipient and email_config.get('sender_email') and email_config.get('sender_password'):
            logger.info(f"Sending email to {recipient}...")
            success = email_sender.send_postmarket_report(recipient, html_content)
            
            if success:
                logger.info("✓ Post-market report sent successfully!")
            else:
                logger.error("✗ Failed to send email")
        else:
            logger.warning("Email not configured. Report saved locally only.")
            logger.info(f"View the report at: {debug_path}")
        
        logger.info("Post-market report generation complete")
        
    except Exception as e:
        logger.exception(f"Error generating post-market report: {e}")
        raise


if __name__ == "__main__":
    main()
