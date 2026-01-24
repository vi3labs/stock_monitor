#!/usr/bin/env python3
"""
Notion Watchlist Module
=======================
Fetches the active stock watchlist from Notion database.
Source of truth for which tickers to track.
"""

import os
import requests
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Notion API configuration
NOTION_TOKEN = os.environ.get("NOTION_TOKEN", "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")
DATABASE_ID = "2f2c5966-9a07-80c8-b1cb-fc120342d72b"  # Stock Watchlist database_id
NOTION_VERSION = "2022-06-28"

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": NOTION_VERSION
}

# Active statuses - tickers with these statuses will be included in reports
ACTIVE_STATUSES = ["Watching", "Holding"]


def get_watchlist(statuses: List[str] = None) -> List[str]:
    """
    Fetch active tickers from Notion Stock Watchlist.

    Args:
        statuses: List of status values to filter by.
                  Defaults to ACTIVE_STATUSES (Watching, Holding).

    Returns:
        List of ticker symbols (e.g., ['NVDA', 'GOOGL', 'AMZN'])
    """
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

            response = requests.post(url, headers=HEADERS, json=payload)

            if response.status_code != 200:
                logger.error(f"Notion API error: {response.status_code} - {response.text[:200]}")
                return []

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

        logger.info(f"Fetched {len(all_tickers)} tickers from Notion (statuses: {statuses})")
        return all_tickers

    except Exception as e:
        logger.error(f"Error fetching watchlist from Notion: {e}")
        return []


def get_watchlist_with_metadata(statuses: List[str] = None) -> List[Dict]:
    """
    Fetch active tickers with full metadata from Notion.

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

            response = requests.post(url, headers=HEADERS, json=payload)

            if response.status_code != 200:
                logger.error(f"Notion API error: {response.status_code} - {response.text[:200]}")
                return []

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

                all_stocks.append({
                    'ticker': ticker,
                    'company': company,
                    'sector': sector,
                    'categories': categories,
                    'status': status,
                    'sentiment': sentiment,
                    'price_when_added': price_when_added,
                    'current_price': current_price,
                    'page_id': page.get("id"),
                })

            has_more = data.get("has_more", False)
            start_cursor = data.get("next_cursor")

        logger.info(f"Fetched {len(all_stocks)} stocks with metadata from Notion")
        return all_stocks

    except Exception as e:
        logger.error(f"Error fetching watchlist metadata from Notion: {e}")
        return []


def update_stock_price(page_id: str, current_price: float) -> bool:
    """
    Update the current price for a stock in Notion.

    Args:
        page_id: Notion page ID for the stock
        current_price: New current price

    Returns:
        True if successful, False otherwise
    """
    url = f"https://api.notion.com/v1/pages/{page_id}"

    payload = {
        "properties": {
            "Current Price": {"number": current_price}
        }
    }

    try:
        response = requests.patch(url, headers=HEADERS, json=payload)
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
