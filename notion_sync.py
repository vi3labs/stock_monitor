#!/usr/bin/env python3
"""
Notion Sync Module
==================
Syncs stock data to your Notion Stock Watchlist database.
Can run standalone or be called by the scheduler.

Usage:
    python notion_sync.py              # Sync all stocks
    python notion_sync.py --summary    # Update daily summary section
"""

import yaml
import logging
from datetime import datetime
from typing import Dict, List, Optional
import argparse
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_fetcher import StockDataFetcher
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


# Stock sector mapping
SECTOR_MAP = {
    # Major Tech
    'GOOGL': 'Tech', 'AMZN': 'Tech', 'META': 'Tech', 'NVDA': 'Tech',
    'TSLA': 'Tech', 'INTC': 'Tech', 'MU': 'Tech', 'TSM': 'Tech',
    'MRVL': 'Tech', 'CRM': 'Tech', 'PYPL': 'Tech', 'INTU': 'Tech',
    
    # Semiconductors
    'ASML': 'Semiconductors', 'AMAT': 'Semiconductors', 'LRCX': 'Semiconductors',
    'APH': 'Semiconductors', 'RMBS': 'Semiconductors', 'SIMO': 'Semiconductors',
    'TSEM': 'Semiconductors', 'STX': 'Semiconductors', 'SNDK': 'Semiconductors',
    'WDC': 'Semiconductors', 'PSTG': 'Semiconductors', 'NTAP': 'Semiconductors',
    
    # Defense & Aerospace
    'LMT': 'Defense', 'NOC': 'Defense', 'RTX': 'Defense', 'BA': 'Defense',
    'GD': 'Defense', 'HII': 'Defense', 'LDOS': 'Defense', 'KTOS': 'Defense',
    'HEI': 'Defense', 'TDY': 'Defense', 'MOG-A': 'Defense', 'AVAV': 'Defense',
    'BAESY': 'Defense', 'PKE': 'Defense',
    
    # Space & Satellites
    'RKLB': 'Space', 'PL': 'Space', 'ASTS': 'Space', 'LUNR': 'Space',
    'IRDM': 'Space', 'GSAT': 'Space', 'VSAT': 'Space', 'BKSY': 'Space',
    'MNTS': 'Space', 'SATS': 'Space',
    
    # Energy - Oil & Gas
    'XOM': 'Energy', 'CVX': 'Energy', 'COP': 'Energy', 'VLO': 'Energy',
    'MPC': 'Energy', 'PSX': 'Energy', 'HAL': 'Energy', 'BKR': 'Energy',
    'CVE': 'Energy', 'FRO': 'Energy', 'STNG': 'Energy', 'NAT': 'Energy',
    
    # Energy - Nuclear & Other
    'LEU': 'Nuclear', 'SMR': 'Nuclear', 'URAN': 'Nuclear',
    'AES': 'Energy', 'EOSE': 'Energy', 'CF': 'Energy', 'TE': 'Energy',
    
    # Crypto Related
    'COIN': 'Crypto', 'MSTR': 'Crypto', 'HOOD': 'Crypto', 'CIFR': 'Crypto',
    'BMNR': 'Crypto', 'IREN': 'Crypto', 'IBIT': 'Crypto ETF', 'FETH': 'Crypto ETF',
    'ETHA': 'Crypto ETF', 'BTC-USD': 'Crypto', 'ETH-USD': 'Crypto', 'LINK-USD': 'Crypto',
    
    # Robotics & Automation
    'BOTT': 'Robotics', 'KRKNF': 'Robotics', 'SSYS': 'Robotics', 'OUST': 'Robotics',
    
    # Financials
    'BAC': 'Financials', 'MCO': 'Financials',
    
    # Industrial & Hardware
    'HON': 'Industrial', 'JBL': 'Industrial', 'LASR': 'Industrial',
    'LPTH': 'Industrial', 'OSS': 'Industrial', 'ONDS': 'Industrial',
    
    # Other
    'PLTR': 'Tech', 'PRME': 'Biotech', 'WMT': 'Consumer', 'GRAB': 'Consumer',
    
    # Small Cap / Speculative
    'RIME': 'Speculative', 'SBET': 'Speculative', 'UAMY': 'Speculative',
    'VOYG': 'Speculative', 'KDEF': 'Defense',
    
    # ETFs
    'VOO': 'ETF - Index', 'SMH': 'ETF - Sector', 'VGT': 'ETF - Sector',
    'SDY': 'ETF - Dividend', 'SCHD': 'ETF - Dividend', 'DVY': 'ETF - Dividend',
    'VIG': 'ETF - Dividend', 'VYM': 'ETF - Dividend', 'SPHD': 'ETF - Dividend',
    'JEPI': 'ETF - Income', 'JEPQ': 'ETF - Income', 'LCDS': 'ETF - Income',
    'CLOD': 'ETF - Thematic', 'AUMI': 'ETF - Thematic', 'AGMI': 'ETF - Thematic',
    'NATO': 'ETF - Thematic', 'LIMI': 'ETF - Thematic',
}

# Company name overrides (for ones that might not fetch correctly)
COMPANY_NAMES = {
    'GOOGL': 'Alphabet Inc.',
    'META': 'Meta Platforms, Inc.',
    'BTC-USD': 'Bitcoin USD',
    'ETH-USD': 'Ethereum USD',
    'LINK-USD': 'Chainlink USD',
    'MOG-A': 'Moog Inc.',
    'BOTT': 'Themes Humanoid Robotics ETF',
    'URAN': 'Themes Uranium & Nuclear ETF',
    'NATO': 'Themes Transatlantic Defense ETF',
    'LIMI': 'Themes Lithium & Battery ETF',
    'CLOD': 'Themes Cloud Computing ETF',
    'AUMI': 'Themes Gold Miners ETF',
    'AGMI': 'Themes Silver Miners ETF',
}


def load_config(config_path: str = 'config.yaml') -> dict:
    """Load configuration from YAML file."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


class NotionStockSync:
    """Syncs stock data to Notion database."""
    
    # Your Notion database data source ID
    DATA_SOURCE_ID = "8e3ab2d4-9866-4578-90f6-1db8a45273d3"
    DASHBOARD_PAGE_ID = "2f0c5966-9a07-8185-8e0c-d86866e0c801"
    
    def __init__(self, symbols: List[str]):
        self.symbols = symbols
        self.fetcher = StockDataFetcher(symbols)
        self.existing_pages = {}  # Will store ticker -> page_url mapping
    
    def get_stock_data(self) -> Dict[str, dict]:
        """Fetch current stock data for all symbols."""
        logger.info("Fetching stock data...")
        quotes = self.fetcher.get_batch_quotes()
        weekly = self.fetcher.get_weekly_performance()
        
        # Merge data
        merged = {}
        for symbol in self.symbols:
            quote = quotes.get(symbol, {})
            week = weekly.get(symbol, {})
            
            merged[symbol] = {
                'symbol': symbol,
                'name': COMPANY_NAMES.get(symbol) or quote.get('name', symbol),
                'price': quote.get('price', 0),
                'day_change': quote.get('change_percent', 0),
                'week_change': week.get('week_change_percent', 0),
                'sector': SECTOR_MAP.get(symbol, 'Other'),
            }
        
        return merged
    
    def format_page_properties(self, stock: dict) -> dict:
        """Format stock data as Notion page properties."""
        today = datetime.now().strftime('%Y-%m-%d')
        
        return {
            'Ticker': stock['symbol'],
            'Company Name': stock['name'],
            'Current Price': stock['price'] if stock['price'] else None,
            'Day Change %': round(stock['day_change'], 2) if stock['day_change'] else None,
            'Week Change %': round(stock['week_change'], 2) if stock['week_change'] else None,
            'Sector': stock['sector'],
            'date:Last Updated:start': today,
            'date:Last Updated:is_datetime': 0,
            'Watchlist Status': 'In progress',
        }
    
    def generate_daily_summary_content(self, stock_data: Dict[str, dict]) -> str:
        """Generate markdown content for daily summary section."""
        now = datetime.now()
        
        # Sort by day change
        sorted_stocks = sorted(
            stock_data.values(),
            key=lambda x: x.get('day_change', 0),
            reverse=True
        )
        
        gainers = [s for s in sorted_stocks if s.get('day_change', 0) > 0][:5]
        losers = [s for s in sorted_stocks if s.get('day_change', 0) < 0][-5:][::-1]
        
        content = f"""## Daily Summary
**Last Updated:** {now.strftime('%B %d, %Y at %I:%M %p')}

### 🚀 Top Gainers Today
| Ticker | Change | Price |
|--------|--------|-------|
"""
        for s in gainers:
            content += f"| **{s['symbol']}** | +{s['day_change']:.2f}% | ${s['price']:.2f} |\n"
        
        content += """
### 📉 Top Losers Today
| Ticker | Change | Price |
|--------|--------|-------|
"""
        for s in losers:
            content += f"| **{s['symbol']}** | {s['day_change']:.2f}% | ${s['price']:.2f} |\n"
        
        # Add sector summary
        sector_performance = {}
        for s in stock_data.values():
            sector = s.get('sector', 'Other')
            if sector not in sector_performance:
                sector_performance[sector] = []
            sector_performance[sector].append(s.get('day_change', 0))
        
        sector_avg = {k: sum(v)/len(v) for k, v in sector_performance.items() if v}
        sorted_sectors = sorted(sector_avg.items(), key=lambda x: x[1], reverse=True)
        
        content += """
### 📊 Sector Performance
| Sector | Avg Change |
|--------|------------|
"""
        for sector, avg in sorted_sectors[:8]:
            emoji = "🟢" if avg > 0 else "🔴" if avg < 0 else "⚪"
            content += f"| {emoji} {sector} | {avg:+.2f}% |\n"
        
        return content


def create_stock_pages(symbols: List[str], stock_data: Dict[str, dict]):
    """Create Notion pages for all stocks."""
    from datetime import datetime
    
    logger.info(f"Creating {len(symbols)} stock pages in Notion...")
    
    # Prepare pages data
    pages = []
    for symbol in symbols:
        data = stock_data.get(symbol, {})
        today = datetime.now().strftime('%Y-%m-%d')
        
        properties = {
            'Ticker': symbol,
            'Company Name': data.get('name', symbol),
            'Sector': data.get('sector', SECTOR_MAP.get(symbol, 'Other')),
            'Watchlist Status': 'In progress',
            'date:Last Updated:start': today,
            'date:Last Updated:is_datetime': 0,
        }
        
        # Add price data if available
        if data.get('price'):
            properties['Current Price'] = round(data['price'], 2)
        if data.get('day_change'):
            properties['Day Change %'] = round(data['day_change'], 2)
        if data.get('week_change'):
            properties['Week Change %'] = round(data['week_change'], 2)
        
        pages.append({'properties': properties})
    
    return pages


def main():
    """Main entry point for Notion sync."""
    parser = argparse.ArgumentParser(description='Sync stocks to Notion')
    parser.add_argument('--summary', action='store_true', help='Update daily summary only')
    parser.add_argument('--prices', action='store_true', help='Update prices only (no new pages)')
    args = parser.parse_args()
    
    logger.info("=" * 50)
    logger.info("Starting Notion Sync")
    logger.info("=" * 50)
    
    try:
        # Load config
        config = load_config()
        symbols = get_watchlist()  # Fetch from Notion (source of truth)

        logger.info(f"Syncing {len(symbols)} symbols to Notion...")
        
        # Initialize sync
        sync = NotionStockSync(symbols)
        
        # Fetch stock data
        stock_data = sync.get_stock_data()
        logger.info(f"Fetched data for {len(stock_data)} stocks")
        
        # Generate summary
        summary = sync.generate_daily_summary_content(stock_data)
        logger.info("Generated daily summary")
        
        # Print summary to console
        print("\n" + "=" * 40)
        print("NOTION SYNC SUMMARY")
        print("=" * 40)
        print(f"Stocks to sync: {len(symbols)}")
        print(f"Data fetched: {len(stock_data)}")
        print("=" * 40 + "\n")
        
        logger.info("Notion sync preparation complete")
        logger.info("Use the Notion MCP tools to create/update pages")
        
        return stock_data, summary
        
    except Exception as e:
        logger.exception(f"Error in Notion sync: {e}")
        raise


if __name__ == "__main__":
    main()
