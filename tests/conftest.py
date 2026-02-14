"""
Shared pytest fixtures for the stock monitor test suite.
"""

import os
import sys
import pytest

# Ensure the project root is on sys.path so imports work
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Set a fake Notion token so the module does not warn during imports
os.environ.setdefault("NOTION_TOKEN", "fake_token_for_tests")


@pytest.fixture
def sample_symbols():
    """List of 5 test ticker symbols."""
    return ["NVDA", "TSLA", "GOOGL", "BTC-USD", "AMZN"]


@pytest.fixture
def sample_quotes():
    """Dict of quote data for 3 stocks."""
    return {
        "NVDA": {
            "symbol": "NVDA",
            "name": "NVIDIA Corporation",
            "price": 145.50,
            "previous_close": 140.00,
            "change": 5.50,
            "change_percent": 3.93,
            "volume": 50_000_000,
            "avg_volume": 40_000_000,
            "volume_ratio": 1.25,
            "market_cap": 3_500_000_000_000,
        },
        "TSLA": {
            "symbol": "TSLA",
            "name": "Tesla, Inc.",
            "price": 248.20,
            "previous_close": 252.00,
            "change": -3.80,
            "change_percent": -1.51,
            "volume": 30_000_000,
            "avg_volume": 35_000_000,
            "volume_ratio": 0.86,
            "market_cap": 790_000_000_000,
        },
        "GOOGL": {
            "symbol": "GOOGL",
            "name": "Alphabet Inc.",
            "price": 175.00,
            "previous_close": 175.00,
            "change": 0.0,
            "change_percent": 0.0,
            "volume": 20_000_000,
            "avg_volume": 25_000_000,
            "volume_ratio": 0.80,
            "market_cap": 2_100_000_000_000,
        },
    }


@pytest.fixture
def sample_config():
    """Minimal config dict matching config.yaml structure."""
    return {
        "email": {
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
            "sender_email": "test@example.com",
            "sender_password": "fake_password",
            "recipient_email": "recipient@example.com",
        },
        "schedule": {
            "premarket_time": "06:30",
            "postmarket_time": "16:30",
            "weekly_day": "saturday",
            "weekly_time": "09:00",
        },
        "report": {
            "news_per_stock": 3,
        },
        "alerts": {
            "big_mover_threshold": 3.0,
            "volume_spike_threshold": 2.0,
        },
        "watchlist": ["NVDA", "TSLA", "GOOGL", "AMZN", "META"],
    }


@pytest.fixture
def mock_notion_response():
    """Mock Notion API response with results array."""
    return {
        "object": "list",
        "results": [
            {
                "id": "page-id-1",
                "properties": {
                    "Ticker": {
                        "title": [{"text": {"content": "NVDA"}}]
                    },
                    "Status": {
                        "select": {"name": "Watching"}
                    },
                },
            },
            {
                "id": "page-id-2",
                "properties": {
                    "Ticker": {
                        "title": [{"text": {"content": "TSLA"}}]
                    },
                    "Status": {
                        "select": {"name": "Holding"}
                    },
                },
            },
            {
                "id": "page-id-3",
                "properties": {
                    "Ticker": {
                        "title": [{"text": {"content": "GOOGL"}}]
                    },
                    "Status": {
                        "select": {"name": "Watching"}
                    },
                },
            },
        ],
        "has_more": False,
        "next_cursor": None,
    }


@pytest.fixture
def sample_premarket_data():
    """Pre-market quote data for 2 stocks."""
    return {
        "NVDA": {
            "symbol": "NVDA",
            "name": "NVIDIA Corporation",
            "pre_market_price": 147.00,
            "previous_close": 140.00,
            "pre_market_change": 7.00,
            "pre_market_change_percent": 5.0,
        },
        "TSLA": {
            "symbol": "TSLA",
            "name": "Tesla, Inc.",
            "pre_market_price": 245.00,
            "previous_close": 252.00,
            "pre_market_change": -7.00,
            "pre_market_change_percent": -2.78,
        },
    }


@pytest.fixture
def sample_weekly_data():
    """Weekly performance data for 3 stocks."""
    return {
        "NVDA": {
            "symbol": "NVDA",
            "start_price": 138.00,
            "end_price": 145.50,
            "week_change": 7.50,
            "week_change_percent": 5.43,
            "daily_closes": [138.0, 140.0, 142.0, 143.5, 145.5],
            "daily_changes": [0.0, 0.0145, 0.0143, 0.0105, 0.0139],
            "high": 146.0,
            "low": 137.5,
            "total_volume": 200_000_000,
        },
        "TSLA": {
            "symbol": "TSLA",
            "start_price": 255.00,
            "end_price": 248.20,
            "week_change": -6.80,
            "week_change_percent": -2.67,
            "daily_closes": [255.0, 253.0, 250.0, 249.0, 248.2],
            "daily_changes": [0.0, -0.0078, -0.0119, -0.004, -0.0032],
            "high": 256.0,
            "low": 247.0,
            "total_volume": 150_000_000,
        },
        "GOOGL": {
            "symbol": "GOOGL",
            "start_price": 174.00,
            "end_price": 175.00,
            "week_change": 1.00,
            "week_change_percent": 0.57,
            "daily_closes": [174.0, 174.5, 175.0, 174.8, 175.0],
            "daily_changes": [0.0, 0.0029, 0.0029, -0.0011, 0.0011],
            "high": 175.5,
            "low": 173.5,
            "total_volume": 100_000_000,
        },
    }
