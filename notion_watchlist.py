#!/usr/bin/env python3
"""
Notion Watchlist Module
=======================
Fetches the active stock watchlist from Notion database.
Source of truth for which tickers to track.

Fallback priority when Notion is unavailable:
1. Notion API (primary)
2. last_watchlist.json cache (if < 24h old)
3. config.yaml watchlist (static fallback)
"""

import os
import json
import requests
import time
import yaml
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

# Load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, rely on environment variables

logger = logging.getLogger(__name__)

# Notion API configuration
# Set NOTION_TOKEN environment variable or create a .env file
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
if not NOTION_TOKEN:
    logger.warning(
        "NOTION_TOKEN environment variable not set. "
        "Notion API calls will be unavailable. "
        "Falling back to config.yaml watchlist."
    )

DATABASE_ID = os.environ.get("NOTION_DATABASE_ID", "2f2c5966-9a07-80c8-b1cb-fc120342d72b")
NOTION_VERSION = "2022-06-28"

# Build headers only if token is available
HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}" if NOTION_TOKEN else "",
    "Content-Type": "application/json",
    "Notion-Version": NOTION_VERSION
}

# Active statuses - tickers with these statuses will be included in reports
ACTIVE_STATUSES = ["Watching", "Holding"]

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 5  # Will use exponential backoff: 5, 10, 20 seconds

# Cache file path (next to this script)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(_SCRIPT_DIR, "last_watchlist.json")
CACHE_MAX_AGE_HOURS = 24


def _save_watchlist_cache(tickers: List[str]) -> None:
    """Save a successful Notion response to local cache."""
    try:
        cache_data = {
            "timestamp": datetime.now().isoformat(),
            "tickers": tickers,
        }
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache_data, f, indent=2)
        logger.debug(f"Cached {len(tickers)} tickers to {CACHE_FILE}")
    except Exception as e:
        logger.warning(f"Could not save watchlist cache: {e}")


def _load_watchlist_cache() -> Optional[List[str]]:
    """Load cached watchlist if it exists and is less than 24h old."""
    try:
        if not os.path.exists(CACHE_FILE):
            return None
        with open(CACHE_FILE, 'r') as f:
            cache_data = json.load(f)
        timestamp = datetime.fromisoformat(cache_data["timestamp"])
        age = datetime.now() - timestamp
        if age > timedelta(hours=CACHE_MAX_AGE_HOURS):
            logger.warning(f"Watchlist cache is {age.total_seconds()/3600:.1f}h old (max {CACHE_MAX_AGE_HOURS}h). Ignoring.")
            return None
        tickers = cache_data.get("tickers", [])
        if tickers:
            logger.info(f"Loaded {len(tickers)} tickers from cache ({age.total_seconds()/60:.0f}m old)")
        return tickers
    except Exception as e:
        logger.warning(f"Could not load watchlist cache: {e}")
        return None


def _load_config_watchlist() -> List[str]:
    """Load tickers from config.yaml as a static fallback."""
    try:
        config_path = os.path.join(_SCRIPT_DIR, "config.yaml")
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        tickers = config.get('watchlist', [])
        if tickers:
            logger.info(f"Loaded {len(tickers)} tickers from config.yaml fallback")
        else:
            logger.error("config.yaml watchlist is empty!")
        return tickers
    except Exception as e:
        logger.error(f"Could not load config.yaml watchlist: {e}")
        return []


def _get_fallback_watchlist() -> List[str]:
    """Try cache first, then config.yaml."""
    cached = _load_watchlist_cache()
    if cached:
        return cached
    return _load_config_watchlist()


def _request_with_retry(method: str, url: str, **kwargs) -> requests.Response:
    """
    Make HTTP request with retry logic and exponential backoff.
    Handles temporary network failures (DNS, connection timeouts).
    """
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            if method == "POST":
                response = requests.post(url, **kwargs)
            elif method == "PATCH":
                response = requests.patch(url, **kwargs)
            else:
                response = requests.get(url, **kwargs)
            return response
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                OSError) as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_DELAY_SECONDS * (2 ** attempt)
                logger.warning(f"Network error (attempt {attempt + 1}/{MAX_RETRIES}): {e}. Retrying in {delay}s...")
                time.sleep(delay)
            else:
                logger.error(f"Network error after {MAX_RETRIES} attempts: {e}")
    raise last_error


def get_watchlist(statuses: List[str] = None) -> List[str]:
    """
    Fetch active tickers from Notion Stock Watchlist.

    Falls back to cached data or config.yaml if Notion is unavailable.

    Args:
        statuses: List of status values to filter by.
                  Defaults to ACTIVE_STATUSES (Watching, Holding).

    Returns:
        List of ticker symbols (e.g., ['NVDA', 'GOOGL', 'AMZN'])
    """
    # If no Notion token, skip API call entirely
    if not NOTION_TOKEN:
        logger.warning("No NOTION_TOKEN available. Using fallback watchlist.")
        return _get_fallback_watchlist()

    statuses = statuses or ACTIVE_STATUSES

    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"

    # Build filter for active statuses
    status_filters = [
        {"property": "Status", "select": {"equals": status}}
        for status in statuses
    ]

    payload = {
        "filter": {
            "or": status_filters
        },
        "page_size": 100
    }

    all_tickers = []
    has_more = True
    start_cursor = None

    try:
        while has_more:
            if start_cursor:
                payload["start_cursor"] = start_cursor

            response = _request_with_retry("POST", url, headers=HEADERS, json=payload)

            if response.status_code == 401:
                logger.critical(
                    "NOTION TOKEN EXPIRED OR INVALID (401 Unauthorized). "
                    "Update NOTION_TOKEN in .env file. Falling back to cached/config watchlist."
                )
                return _get_fallback_watchlist()

            if response.status_code != 200:
                logger.error(f"Notion API error: {response.status_code} - {response.text[:200]}")
                return _get_fallback_watchlist()

            data = response.json()

            # Extract tickers from results
            for page in data.get("results", []):
                ticker_prop = page.get("properties", {}).get("Ticker", {})
                title_array = ticker_prop.get("title", [])
                if title_array:
                    ticker = title_array[0].get("text", {}).get("content", "")
                    if ticker:
                        all_tickers.append(ticker)

            has_more = data.get("has_more", False)
            start_cursor = data.get("next_cursor")

        # If Notion returned 0 tickers but no error, something is wrong
        if len(all_tickers) == 0:
            logger.warning(
                "Notion returned 0 tickers (no error). "
                "Database may be empty or filter mismatch. Falling back."
            )
            return _get_fallback_watchlist()

        logger.info(f"Fetched {len(all_tickers)} tickers from Notion (statuses: {statuses})")

        # Cache successful result
        _save_watchlist_cache(all_tickers)

        return all_tickers

    except Exception as e:
        logger.error(f"Error fetching watchlist from Notion: {e}")
        return _get_fallback_watchlist()


def get_watchlist_with_metadata(statuses: List[str] = None) -> List[Dict]:
    """
    Fetch active tickers with full metadata from Notion.

    Falls back to ticker-only data from cache/config if Notion is unavailable.

    Returns:
        List of dicts with ticker info:
        [
            {
                'ticker': 'NVDA',
                'company': 'NVIDIA Corporation',
                'sector': 'Tech',
                'categories': ['Large Cap', 'AI'],
                'status': 'Watching',
                'sentiment': 'Bullish',
                'price_when_added': 187.67,
            },
            ...
        ]
    """
    # If no Notion token, return ticker-only fallback
    if not NOTION_TOKEN:
        logger.warning("No NOTION_TOKEN available. Returning ticker-only fallback for metadata request.")
        tickers = _get_fallback_watchlist()
        return [{'ticker': t, 'company': t, 'sector': '', 'categories': [],
                 'status': 'Unknown', 'sentiment': '', 'price_when_added': None,
                 'current_price': None, 'page_id': None} for t in tickers]

    statuses = statuses or ACTIVE_STATUSES

    url = f"https://api.notion.com/v1/databases/{DATABASE_ID}/query"

    status_filters = [
        {"property": "Status", "select": {"equals": status}}
        for status in statuses
    ]

    payload = {
        "filter": {
            "or": status_filters
        },
        "page_size": 100
    }

    all_stocks = []
    has_more = True
    start_cursor = None

    try:
        while has_more:
            if start_cursor:
                payload["start_cursor"] = start_cursor

            response = _request_with_retry("POST", url, headers=HEADERS, json=payload)

            if response.status_code == 401:
                logger.critical(
                    "NOTION TOKEN EXPIRED OR INVALID (401 Unauthorized). "
                    "Update NOTION_TOKEN in .env file. Falling back to ticker-only data."
                )
                tickers = _get_fallback_watchlist()
                return [{'ticker': t, 'company': t, 'sector': '', 'categories': [],
                         'status': 'Unknown', 'sentiment': '', 'price_when_added': None,
                         'current_price': None, 'page_id': None} for t in tickers]

            if response.status_code != 200:
                logger.error(f"Notion API error: {response.status_code} - {response.text[:200]}")
                tickers = _get_fallback_watchlist()
                return [{'ticker': t, 'company': t, 'sector': '', 'categories': [],
                         'status': 'Unknown', 'sentiment': '', 'investment_thesis': '',
                         'catalysts': '', 'price_when_added': None,
                         'current_price': None, 'page_id': None} for t in tickers]

            data = response.json()

            for page in data.get("results", []):
                props = page.get("properties", {})

                # Extract ticker
                ticker_prop = props.get("Ticker", {})
                title_array = ticker_prop.get("title", [])
                ticker = title_array[0].get("text", {}).get("content", "") if title_array else ""

                if not ticker:
                    continue

                # Extract company name
                company_prop = props.get("Company Name", {})
                company_array = company_prop.get("rich_text", [])
                company = company_array[0].get("text", {}).get("content", "") if company_array else ticker

                # Extract sector
                sector_prop = props.get("Sector", {})
                sector = sector_prop.get("select", {}).get("name", "") if sector_prop.get("select") else ""

                # Extract categories (multi-select)
                category_prop = props.get("Category", {})
                categories = [c.get("name", "") for c in category_prop.get("multi_select", [])]

                # Extract status
                status_prop = props.get("Status", {})
                status = status_prop.get("select", {}).get("name", "") if status_prop.get("select") else ""

                # Extract sentiment
                sentiment_prop = props.get("Sentiment", {})
                sentiment = sentiment_prop.get("select", {}).get("name", "") if sentiment_prop.get("select") else ""

                # Extract price when added
                price_prop = props.get("Price When Added", {})
                price_when_added = price_prop.get("number")

                # Extract current price
                current_prop = props.get("Current Price", {})
                current_price = current_prop.get("number")

                # Extract investment thesis
                thesis_prop = props.get("Investment Thesis", {})
                thesis_array = thesis_prop.get("rich_text", [])
                investment_thesis = thesis_array[0].get("text", {}).get("content", "") if thesis_array else ""

                # Extract catalysts
                catalysts_prop = props.get("Catalysts", {})
                catalysts_array = catalysts_prop.get("rich_text", [])
                catalysts = catalysts_array[0].get("text", {}).get("content", "") if catalysts_array else ""

                all_stocks.append({
                    'ticker': ticker,
                    'company': company,
                    'sector': sector,
                    'categories': categories,
                    'status': status,
                    'sentiment': sentiment,
                    'investment_thesis': investment_thesis,
                    'catalysts': catalysts,
                    'price_when_added': price_when_added,
                    'current_price': current_price,
                    'page_id': page.get("id"),
                })

            has_more = data.get("has_more", False)
            start_cursor = data.get("next_cursor")

        # If 0 results, fall back
        if len(all_stocks) == 0:
            logger.warning("Notion returned 0 stocks with metadata. Falling back.")
            tickers = _get_fallback_watchlist()
            return [{'ticker': t, 'company': t, 'sector': '', 'categories': [],
                     'status': 'Unknown', 'sentiment': '', 'investment_thesis': '',
                     'catalysts': '', 'price_when_added': None,
                     'current_price': None, 'page_id': None} for t in tickers]

        logger.info(f"Fetched {len(all_stocks)} stocks with metadata from Notion")

        # Cache the tickers from successful metadata fetch too
        _save_watchlist_cache([s['ticker'] for s in all_stocks])

        return all_stocks

    except Exception as e:
        logger.error(f"Error fetching watchlist metadata from Notion: {e}")
        tickers = _get_fallback_watchlist()
        return [{'ticker': t, 'company': t, 'sector': '', 'categories': [],
                 'status': 'Unknown', 'sentiment': '', 'price_when_added': None,
                 'current_price': None, 'page_id': None} for t in tickers]


def update_stock_price(page_id: str, current_price: float) -> bool:
    """
    Update the current price for a stock in Notion.

    Args:
        page_id: Notion page ID for the stock
        current_price: New current price

    Returns:
        True if successful, False otherwise
    """
    if not NOTION_TOKEN:
        logger.error("Cannot update stock price: NOTION_TOKEN not available")
        return False

    url = f"https://api.notion.com/v1/pages/{page_id}"

    payload = {
        "properties": {
            "Current Price": {"number": current_price}
        }
    }

    try:
        response = _request_with_retry("PATCH", url, headers=HEADERS, json=payload)
        if response.status_code == 200:
            return True
        else:
            logger.error(f"Error updating price: {response.status_code} - {response.text[:200]}")
            return False
    except Exception as e:
        logger.error(f"Error updating stock price: {e}")
        return False


if __name__ == "__main__":
    # Test the module
    logging.basicConfig(level=logging.INFO)

    print("Testing Notion Watchlist Module")
    print("=" * 50)

    # Test simple ticker list
    print("\n1. Fetching active tickers...")
    tickers = get_watchlist()
    print(f"   Found {len(tickers)} active tickers")
    if tickers:
        print(f"   First 10: {tickers[:10]}")

    # Test with metadata
    print("\n2. Fetching tickers with metadata...")
    stocks = get_watchlist_with_metadata()
    print(f"   Found {len(stocks)} stocks with metadata")

    if stocks:
        print("\n   Sample stock:")
        sample = stocks[0]
        for key, value in sample.items():
            if key != 'page_id':
                print(f"     {key}: {value}")

    # Count by sector
    if stocks:
        sectors = {}
        for s in stocks:
            sector = s.get('sector', 'Unknown')
            sectors[sector] = sectors.get(sector, 0) + 1

        print("\n3. Stocks by sector:")
        for sector, count in sorted(sectors.items(), key=lambda x: -x[1]):
            print(f"     {sector}: {count}")

    # Test fallback
    print("\n4. Testing config.yaml fallback...")
    fallback = _load_config_watchlist()
    print(f"   Config fallback has {len(fallback)} tickers")
