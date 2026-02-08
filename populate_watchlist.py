#!/usr/bin/env python3
"""
Populate Stock Watchlist in Notion with selected tickers.
Fetches current prices from yfinance and creates entries in Notion.
"""

import os
import requests
from datetime import datetime
import yfinance as yf
from concurrent.futures import ThreadPoolExecutor, as_completed

# Notion API configuration
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
if not NOTION_TOKEN:
    from dotenv import load_dotenv
    load_dotenv()
    NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
if not NOTION_TOKEN:
    raise RuntimeError("NOTION_TOKEN not set. Add it to .env or set as environment variable.")
DATABASE_ID = "2f2c5966-9a07-80c8-b1cb-fc120342d72b"  # database_id from URL
NOTION_VERSION = "2022-06-28"  # Use stable version for page creation

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": NOTION_VERSION
}

# Selected tickers organized by sector
TICKERS = {
    "Tech": [
        ("GOOGL", "Alphabet Inc."),
        ("AMZN", "Amazon.com Inc."),
        ("NVDA", "NVIDIA Corporation"),
        ("INTC", "Intel Corporation"),
        ("MU", "Micron Technology"),
        ("TSM", "Taiwan Semiconductor"),
        ("MRVL", "Marvell Technology"),
        ("CRM", "Salesforce Inc."),
    ],
    "Semiconductors": [
        ("ASML", "ASML Holding N.V."),
        ("AMAT", "Applied Materials"),
        ("LRCX", "Lam Research"),
        ("APH", "Amphenol Corporation"),
        ("RMBS", "Rambus Inc."),
        ("SIMO", "Silicon Motion"),
        ("TSEM", "Tower Semiconductor"),
        ("STX", "Seagate Technology"),
        ("SNDK", "SanDisk Corporation"),
        ("WDC", "Western Digital"),
        ("PSTG", "Pure Storage"),
        ("NTAP", "NetApp Inc."),
    ],
    "Defense": [
        ("RTX", "RTX Corporation"),
        ("HII", "Huntington Ingalls"),
        ("LDOS", "Leidos Holdings"),
        ("KTOS", "Kratos Defense"),
        ("HEI", "HEICO Corporation"),
        ("TDY", "Teledyne Technologies"),
        ("MOG-A", "Moog Inc."),
        ("AVAV", "AeroVironment"),
        ("BAESY", "BAE Systems"),
        ("PKE", "Park Aerospace"),
    ],
    "Space": [
        ("RKLB", "Rocket Lab"),
        ("PL", "Planet Labs"),
        ("ASTS", "AST SpaceMobile"),
        ("LUNR", "Intuitive Machines"),
        ("IRDM", "Iridium Communications"),
        ("GSAT", "Globalstar"),
        ("VSAT", "Viasat Inc."),
        ("BKSY", "BlackSky Technology"),
        ("MNTS", "Momentus Inc."),
    ],
    "Energy": [
        ("HAL", "Halliburton"),
        ("BKR", "Baker Hughes"),
        ("CVE", "Cenovus Energy"),
        ("VLO", "Valero Energy"),
        ("FRO", "Frontline"),
        ("STNG", "Scorpio Tankers"),
        ("NAT", "Nordic American Tankers"),
        ("LEU", "Centrus Energy"),
        ("SMR", "NuScale Power"),
        ("URAN", "Themes Uranium ETF"),
        ("AES", "AES Corporation"),
        ("EOSE", "Eos Energy"),
        ("CF", "CF Industries"),
        ("TE", "T1 Energy"),
    ],
    "Crypto": [
        ("COIN", "Coinbase Global"),
        ("MSTR", "MicroStrategy"),
        ("CIFR", "Cipher Mining"),
        ("BMNR", "Bitmine Immersion"),
        ("IREN", "IREN Limited"),
        ("IBIT", "iShares Bitcoin Trust"),
        ("FETH", "Fidelity Ethereum"),
        ("ETHA", "iShares Ethereum Trust"),
        ("BTC-USD", "Bitcoin USD"),
        ("ETH-USD", "Ethereum USD"),
        ("LINK-USD", "Chainlink USD"),
    ],
    "Tech": [  # Additional categories mapped to existing sectors
        ("PLTR", "Palantir Technologies"),
    ],
    "Healthcare": [
        ("PRME", "Prime Medicine"),
    ],
    "ETF": [
        ("JEPI", "JPMorgan Equity Premium Income"),
        ("JEPQ", "JPMorgan Nasdaq Equity Premium"),
        ("SCHD", "Schwab U.S. Dividend ETF"),
    ],
    # Adding missing categories
}

# Flatten and deduplicate with proper sector mapping
ALL_TICKERS = [
    # Tech
    ("GOOGL", "Alphabet Inc.", "Tech", ["Large Cap", "AI"]),
    ("AMZN", "Amazon.com Inc.", "Tech", ["Large Cap", "AI"]),
    ("NVDA", "NVIDIA Corporation", "Tech", ["Large Cap", "AI"]),
    ("INTC", "Intel Corporation", "Tech", ["Large Cap"]),
    ("MU", "Micron Technology", "Tech", ["Large Cap"]),
    ("TSM", "Taiwan Semiconductor", "Tech", ["Large Cap"]),
    ("MRVL", "Marvell Technology", "Tech", ["AI"]),
    ("CRM", "Salesforce Inc.", "Tech", ["Large Cap", "AI"]),
    # Semiconductors
    ("ASML", "ASML Holding N.V.", "Semiconductors", ["Large Cap"]),
    ("AMAT", "Applied Materials", "Semiconductors", ["Large Cap"]),
    ("LRCX", "Lam Research", "Semiconductors", ["Large Cap"]),
    ("APH", "Amphenol Corporation", "Semiconductors", []),
    ("RMBS", "Rambus Inc.", "Semiconductors", []),
    ("SIMO", "Silicon Motion", "Semiconductors", ["Small Cap"]),
    ("TSEM", "Tower Semiconductor", "Semiconductors", []),
    ("STX", "Seagate Technology", "Semiconductors", []),
    ("SNDK", "SanDisk Corporation", "Semiconductors", []),
    ("WDC", "Western Digital", "Semiconductors", []),
    ("PSTG", "Pure Storage", "Semiconductors", []),
    ("NTAP", "NetApp Inc.", "Semiconductors", []),
    # Defense
    ("RTX", "RTX Corporation", "Defense", ["Large Cap"]),
    ("HII", "Huntington Ingalls", "Defense", []),
    ("LDOS", "Leidos Holdings", "Defense", []),
    ("KTOS", "Kratos Defense", "Defense", ["Small Cap"]),
    ("HEI", "HEICO Corporation", "Defense", []),
    ("TDY", "Teledyne Technologies", "Defense", []),
    ("MOG-A", "Moog Inc.", "Defense", []),
    ("AVAV", "AeroVironment", "Defense", []),
    ("BAESY", "BAE Systems", "Defense", ["Large Cap"]),
    ("PKE", "Park Aerospace", "Defense", ["Small Cap"]),
    # Space
    ("RKLB", "Rocket Lab", "Space", ["Small Cap", "Speculative"]),
    ("PL", "Planet Labs", "Space", ["Small Cap", "Speculative"]),
    ("ASTS", "AST SpaceMobile", "Space", ["Small Cap", "Speculative"]),
    ("LUNR", "Intuitive Machines", "Space", ["Small Cap", "Speculative"]),
    ("IRDM", "Iridium Communications", "Space", []),
    ("GSAT", "Globalstar", "Space", ["Small Cap"]),
    ("VSAT", "Viasat Inc.", "Space", []),
    ("BKSY", "BlackSky Technology", "Space", ["Small Cap", "Speculative"]),
    ("MNTS", "Momentus Inc.", "Space", ["Small Cap", "Speculative"]),
    # Energy - Oil & Gas
    ("HAL", "Halliburton", "Energy", ["Oil & Gas", "Cyclical"]),
    ("BKR", "Baker Hughes", "Energy", ["Oil & Gas", "Cyclical"]),
    ("CVE", "Cenovus Energy", "Energy", ["Oil & Gas", "Cyclical"]),
    ("VLO", "Valero Energy", "Energy", ["Oil & Gas", "Cyclical"]),
    # Energy - Tankers
    ("FRO", "Frontline", "Energy", ["Cyclical", "Dividend"]),
    ("STNG", "Scorpio Tankers", "Energy", ["Cyclical", "Dividend"]),
    ("NAT", "Nordic American Tankers", "Energy", ["Cyclical", "Dividend"]),
    # Energy - Nuclear
    ("LEU", "Centrus Energy", "Energy", ["Nuclear"]),
    ("SMR", "NuScale Power", "Energy", ["Nuclear", "Speculative"]),
    ("URAN", "Themes Uranium ETF", "Energy", ["Nuclear"]),
    # Energy - Other
    ("AES", "AES Corporation", "Energy", []),
    ("EOSE", "Eos Energy", "Energy", ["Speculative"]),
    ("CF", "CF Industries", "Energy", []),
    ("TE", "T1 Energy", "Energy", ["Speculative"]),
    # Crypto Stocks
    ("COIN", "Coinbase Global", "Crypto", ["Large Cap"]),
    ("MSTR", "MicroStrategy", "Crypto", []),
    ("CIFR", "Cipher Mining", "Crypto", ["Small Cap", "Speculative"]),
    ("BMNR", "Bitmine Immersion", "Crypto", ["Small Cap", "Speculative"]),
    ("IREN", "IREN Limited", "Crypto", ["Small Cap"]),
    # Crypto ETFs
    ("IBIT", "iShares Bitcoin Trust", "Crypto", []),
    ("FETH", "Fidelity Ethereum", "Crypto", []),
    ("ETHA", "iShares Ethereum Trust", "Crypto", []),
    # Crypto Direct
    ("BTC-USD", "Bitcoin USD", "Crypto", []),
    ("ETH-USD", "Ethereum USD", "Crypto", []),
    ("LINK-USD", "Chainlink USD", "Crypto", []),
    # Robotics
    ("KRKNF", "Kraken Robotics", "Tech", ["Robotics", "Small Cap"]),
    ("SSYS", "Stratasys", "Tech", ["Robotics"]),
    ("OUST", "Ouster", "Tech", ["Robotics", "Small Cap"]),
    # Industrial/Hardware
    ("LASR", "nLIGHT Inc.", "Tech", ["Small Cap"]),
    ("LPTH", "LightPath Technologies", "Tech", ["Small Cap"]),
    ("OSS", "One Stop Systems", "Tech", ["Small Cap"]),
    ("ONDS", "Ondas Inc.", "Tech", ["Small Cap"]),
    # Data & Analytics
    ("PLTR", "Palantir Technologies", "Tech", ["AI"]),
    # Biotech
    ("PRME", "Prime Medicine", "Healthcare", ["Speculative"]),
    # ETFs
    ("JEPI", "JPMorgan Equity Premium Income", "ETF", ["Dividend"]),
    ("JEPQ", "JPMorgan Nasdaq Equity Premium", "ETF", ["Dividend"]),
    ("SCHD", "Schwab U.S. Dividend ETF", "ETF", ["Dividend"]),
    # Small Cap Speculative
    ("RIME", "Algorhythm Holdings", "Tech", ["Small Cap", "Speculative"]),
    ("SBET", "SharpLink Gaming", "Tech", ["Small Cap", "Speculative"]),
    ("UAMY", "United States Antimony", "Energy", ["Small Cap", "Speculative"]),
    ("VOYG", "Voyager Technologies", "Space", ["Small Cap", "Speculative"]),
    ("KDEF", "PLUS Korea Defense", "Defense", ["Small Cap", "Speculative"]),
]


def get_tradingview_url(ticker: str) -> str:
    """Generate TradingView URL for a ticker."""
    # Handle crypto tickers
    if ticker.endswith("-USD"):
        symbol = ticker.replace("-USD", "USD")
        return f"https://www.tradingview.com/symbols/{symbol}/"

    # For stocks, try to detect exchange
    # Common mappings
    nasdaq_stocks = {"GOOGL", "AMZN", "NVDA", "INTC", "MU", "MRVL", "CRM", "ASML", "AMAT",
                     "LRCX", "RMBS", "SIMO", "PSTG", "COIN", "PLTR", "ASTS", "LUNR", "RKLB"}

    if ticker in nasdaq_stocks:
        return f"https://www.tradingview.com/symbols/NASDAQ-{ticker}/"
    else:
        return f"https://www.tradingview.com/symbols/{ticker}/"


def fetch_price(ticker: str) -> float | None:
    """Fetch current price for a ticker using yfinance."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        price = info.get('currentPrice') or info.get('regularMarketPrice') or info.get('previousClose')
        return round(price, 2) if price else None
    except Exception as e:
        print(f"  Warning: Could not fetch price for {ticker}: {e}")
        return None


def create_notion_page(ticker: str, company: str, sector: str, categories: list, price: float | None) -> bool:
    """Create a page in the Notion database."""
    url = "https://api.notion.com/v1/pages"

    # Build properties
    properties = {
        "Ticker": {
            "title": [{"text": {"content": ticker}}]
        },
        "Company Name": {
            "rich_text": [{"text": {"content": company}}]
        },
        "Sector": {
            "select": {"name": sector}
        },
        "Status": {
            "select": {"name": "Watching"}
        },
        "Sentiment": {
            "select": {"name": "Neutral"}
        },
        "Date Added": {
            "date": {"start": datetime.now().strftime("%Y-%m-%d")}
        },
        "TradingView": {
            "url": get_tradingview_url(ticker)
        }
    }

    # Add categories if any
    if categories:
        properties["Category"] = {
            "multi_select": [{"name": cat} for cat in categories]
        }

    # Add price if available
    if price is not None:
        properties["Price When Added"] = {"number": price}
        properties["Current Price"] = {"number": price}

    payload = {
        "parent": {"database_id": DATABASE_ID},
        "properties": properties
    }

    try:
        response = requests.post(url, headers=HEADERS, json=payload)
        if response.status_code == 200:
            return True
        else:
            print(f"  Error creating {ticker}: {response.status_code} - {response.text[:200]}")
            return False
    except Exception as e:
        print(f"  Error creating {ticker}: {e}")
        return False


def main():
    print(f"Populating Stock Watchlist with {len(ALL_TICKERS)} tickers...")
    print("=" * 60)

    # Fetch all prices first (parallel)
    print("\nFetching current prices...")
    prices = {}

    def fetch_with_ticker(item):
        ticker = item[0]
        price = fetch_price(ticker)
        return ticker, price

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_with_ticker, item): item for item in ALL_TICKERS}
        for future in as_completed(futures):
            ticker, price = future.result()
            prices[ticker] = price
            if price:
                print(f"  {ticker}: ${price}")
            else:
                print(f"  {ticker}: No price available")

    # Create Notion pages
    print("\nCreating Notion entries...")
    success_count = 0
    fail_count = 0

    for ticker, company, sector, categories in ALL_TICKERS:
        price = prices.get(ticker)
        if create_notion_page(ticker, company, sector, categories, price):
            print(f"  ✓ {ticker}")
            success_count += 1
        else:
            print(f"  ✗ {ticker}")
            fail_count += 1

    print("\n" + "=" * 60)
    print(f"Complete! Created {success_count} entries, {fail_count} failed.")


if __name__ == "__main__":
    main()
