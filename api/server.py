#!/usr/bin/env python3
"""
Stock Monitor Dashboard - API Server
=====================================
Flask server providing REST endpoints for the dashboard.
Reuses existing data_fetcher.py and news_fetcher.py modules.

Endpoints:
    GET /api/quotes   - All watchlist quotes with sparkline data
    GET /api/sectors  - Sector performance (aggregated from quotes)
    GET /api/movers   - Top gainers and losers
    GET /api/indices  - Market indices
    GET /api/news     - Latest market news

Run:
    python api/server.py
"""

import sys
import os
import logging
import threading
import time
from datetime import datetime
from typing import Dict, List, Tuple

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, jsonify, request
from flask_cors import CORS

from data_fetcher import StockDataFetcher
from news_fetcher import NewsFetcher
from notion_watchlist import get_watchlist, get_watchlist_with_metadata
from notion_sync import SECTOR_MAP, COMPANY_NAMES

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for frontend requests

# Cache configuration
CACHE_DURATION_MINUTES = 5


class DashboardDataService:
    """
    Service class that handles data fetching and aggregation for the dashboard.
    Caches results to minimize API calls.
    """

    def __init__(self):
        self._quotes_cache = None
        self._quotes_time = None
        self._indices_cache = None
        self._indices_time = None
        self._weekly_cache = None
        self._weekly_time = None
        self._watchlist_meta = None

    def _is_cache_valid(self, cache_time) -> bool:
        """Check if cached data is still valid."""
        if cache_time is None:
            return False
        elapsed = (datetime.now() - cache_time).total_seconds() / 60
        return elapsed < CACHE_DURATION_MINUTES

    def get_watchlist_symbols(self) -> List[str]:
        """Get the list of symbols from Notion watchlist."""
        return get_watchlist()

    def get_watchlist_metadata(self) -> List[Dict]:
        """Get watchlist with metadata (sector, company name, etc.)."""
        if self._watchlist_meta is None:
            self._watchlist_meta = get_watchlist_with_metadata()
        return self._watchlist_meta

    def get_quotes(self, force_refresh: bool = False) -> Dict:
        """
        Get all watchlist quotes with weekly data for sparklines.
        Returns dict keyed by symbol.
        """
        if not force_refresh and self._is_cache_valid(self._quotes_time):
            logger.info("Returning cached quotes")
            return self._quotes_cache

        logger.info("Fetching fresh quotes...")
        symbols = self.get_watchlist_symbols()

        if not symbols:
            logger.warning("No symbols in watchlist")
            return {}

        # Create fetcher
        fetcher = StockDataFetcher(symbols, cache_duration_minutes=CACHE_DURATION_MINUTES)

        # Get current quotes
        quotes = fetcher.get_batch_quotes()

        # Get weekly performance for sparklines
        weekly = fetcher.get_weekly_performance()

        # Get watchlist metadata for sectors
        meta = {m['ticker']: m for m in self.get_watchlist_metadata()}

        # Merge data
        result = {}
        for symbol in symbols:
            quote = quotes.get(symbol, {})
            week = weekly.get(symbol, {})
            meta_info = meta.get(symbol, {})

            # Get sector from metadata, fallback to SECTOR_MAP
            sector = meta_info.get('sector') or SECTOR_MAP.get(symbol, 'Other')

            # Get company name
            name = COMPANY_NAMES.get(symbol) or quote.get('name') or meta_info.get('company') or symbol

            result[symbol] = {
                'symbol': symbol,
                'name': name,
                'price': quote.get('price', 0),
                'change': quote.get('change', 0),
                'change_percent': quote.get('change_percent', 0),
                'previous_close': quote.get('previous_close', 0),
                'open': quote.get('open', 0),
                'day_high': quote.get('day_high', 0),
                'day_low': quote.get('day_low', 0),
                'volume': quote.get('volume', 0),
                'avg_volume': quote.get('avg_volume', 0),
                'volume_ratio': quote.get('volume_ratio', 1.0),
                'market_cap': quote.get('market_cap', 0),
                'sector': sector,
                'daily_closes': week.get('daily_closes', []),
                'week_change_percent': week.get('week_change_percent', 0),
            }

        self._quotes_cache = result
        self._quotes_time = datetime.now()

        logger.info(f"Fetched {len(result)} quotes")
        return result

    def get_sectors(self, quotes: Dict = None) -> List[Dict]:
        """
        Calculate sector performance from quotes.
        Returns list of sectors sorted by average change.
        """
        if quotes is None:
            quotes = self.get_quotes()

        # Aggregate by sector
        sector_data = {}
        for stock in quotes.values():
            sector = stock.get('sector', 'Other')
            if sector not in sector_data:
                sector_data[sector] = {
                    'name': sector,
                    'stocks': [],
                    'changes': []
                }
            sector_data[sector]['stocks'].append(stock['symbol'])
            sector_data[sector]['changes'].append(stock.get('change_percent', 0))

        # Calculate averages
        result = []
        for sector, data in sector_data.items():
            if data['changes']:
                avg_change = sum(data['changes']) / len(data['changes'])
                result.append({
                    'name': sector,
                    'change': avg_change,
                    'stock_count': len(data['stocks']),
                    'stocks': data['stocks'][:5]  # Top 5 for preview
                })

        # Sort by change descending
        result.sort(key=lambda x: x['change'], reverse=True)

        return result

    def get_movers(self, quotes: Dict = None, n: int = 10) -> Dict:
        """
        Get top gainers and losers from quotes.
        Returns dict with 'gainers' and 'losers' lists.
        """
        if quotes is None:
            quotes = self.get_quotes()

        # Sort by change percent
        sorted_stocks = sorted(
            quotes.values(),
            key=lambda x: x.get('change_percent', 0),
            reverse=True
        )

        gainers = [s for s in sorted_stocks if s.get('change_percent', 0) > 0][:n]
        losers = [s for s in sorted_stocks if s.get('change_percent', 0) < 0][-n:]
        losers.reverse()  # Most negative first

        return {
            'gainers': gainers,
            'losers': losers
        }

    def get_indices(self, force_refresh: bool = False) -> Dict:
        """
        Get market indices with sparkline data.
        """
        if not force_refresh and self._is_cache_valid(self._indices_time):
            logger.info("Returning cached indices")
            return self._indices_cache

        logger.info("Fetching market indices...")

        # Create a minimal fetcher just for indices
        fetcher = StockDataFetcher([], cache_duration_minutes=CACHE_DURATION_MINUTES)
        indices = fetcher.get_market_indices()

        # Get weekly data for sparklines
        index_symbols = list(indices.keys())
        if index_symbols:
            index_fetcher = StockDataFetcher(index_symbols, cache_duration_minutes=CACHE_DURATION_MINUTES)
            weekly = index_fetcher.get_weekly_performance()

            # Merge weekly data into indices
            for symbol, data in indices.items():
                week = weekly.get(symbol, {})
                data['daily_closes'] = week.get('daily_closes', [])
                data['week_change_percent'] = week.get('week_change_percent', 0)

        self._indices_cache = indices
        self._indices_time = datetime.now()

        logger.info(f"Fetched {len(indices)} indices")
        return indices

    def get_news(self) -> List[Dict]:
        """Get market news."""
        logger.info("Fetching news...")
        fetcher = NewsFetcher(max_news_per_stock=5)
        news = fetcher.get_market_news()
        return news


# Create service instance
data_service = DashboardDataService()

# Background refresh state
_is_loading = False
_last_load_time = None


def background_refresh():
    """Background thread to refresh data periodically."""
    global _is_loading, _last_load_time

    while True:
        try:
            _is_loading = True
            logger.info("Background refresh: starting data fetch...")

            # Fetch all data
            data_service.get_quotes(force_refresh=True)
            data_service.get_indices(force_refresh=True)

            _last_load_time = datetime.now()
            _is_loading = False
            logger.info("Background refresh: complete")

        except Exception as e:
            logger.exception(f"Background refresh error: {e}")
            _is_loading = False

        # Wait 5 minutes before next refresh
        time.sleep(5 * 60)


def warmup_cache():
    """Warm up the cache on startup (runs in background)."""
    global _is_loading
    _is_loading = True
    logger.info("Warming up cache...")

    try:
        # Fetch quotes first (most important)
        data_service.get_quotes()
        # Then indices
        data_service.get_indices()
        logger.info("Cache warmup complete!")
    except Exception as e:
        logger.exception(f"Cache warmup error: {e}")
    finally:
        _is_loading = False


# ============================================================================
# API Routes
# ============================================================================

@app.route('/api/quotes', methods=['GET'])
def api_quotes():
    """Get all watchlist quotes with sparkline data."""
    try:
        quotes = data_service.get_quotes()
        return jsonify(quotes)
    except Exception as e:
        logger.exception("Error fetching quotes")
        return jsonify({'error': str(e)}), 500


@app.route('/api/sectors', methods=['GET'])
def api_sectors():
    """Get sector performance data."""
    try:
        quotes = data_service.get_quotes()
        sectors = data_service.get_sectors(quotes)
        return jsonify(sectors)
    except Exception as e:
        logger.exception("Error fetching sectors")
        return jsonify({'error': str(e)}), 500


@app.route('/api/movers', methods=['GET'])
def api_movers():
    """Get top gainers and losers."""
    try:
        quotes = data_service.get_quotes()
        movers = data_service.get_movers(quotes)
        return jsonify(movers)
    except Exception as e:
        logger.exception("Error fetching movers")
        return jsonify({'error': str(e)}), 500


@app.route('/api/indices', methods=['GET'])
def api_indices():
    """Get market indices with sparklines."""
    try:
        indices = data_service.get_indices()
        return jsonify(indices)
    except Exception as e:
        logger.exception("Error fetching indices")
        return jsonify({'error': str(e)}), 500


@app.route('/api/news', methods=['GET'])
def api_news():
    """Get latest market news."""
    try:
        news = data_service.get_news()
        return jsonify(news)
    except Exception as e:
        logger.exception("Error fetching news")
        return jsonify({'error': str(e)}), 500


@app.route('/api/all', methods=['GET'])
def api_all():
    """
    Get all dashboard data in one request.
    Much faster than multiple requests.
    """
    try:
        # Check if still loading
        if _is_loading and data_service._quotes_cache is None:
            return jsonify({
                'loading': True,
                'message': 'Data is loading, please wait...'
            }), 202

        # Get quotes (from cache if available)
        quotes = data_service.get_quotes()

        # Derive sectors and movers from quotes
        sectors = data_service.get_sectors(quotes)
        movers = data_service.get_movers(quotes)

        # Get indices
        indices = data_service.get_indices()

        # Get news (don't block if it fails)
        try:
            news = data_service.get_news()
        except Exception as news_error:
            logger.warning(f"Failed to fetch news: {news_error}")
            news = []

        return jsonify({
            'quotes': quotes,
            'sectors': sectors,
            'movers': movers,
            'indices': indices,
            'news': news,
            'timestamp': datetime.now().isoformat(),
            'loading': _is_loading
        })
    except Exception as e:
        logger.exception("Error fetching all data")
        return jsonify({'error': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def api_health():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'loading': _is_loading,
        'cache_ready': data_service._quotes_cache is not None,
        'timestamp': datetime.now().isoformat()
    })


@app.route('/', methods=['GET'])
def index():
    """Root endpoint with API info."""
    return jsonify({
        'name': 'Stock Monitor Dashboard API',
        'version': '1.0.0',
        'endpoints': {
            '/api/quotes': 'All watchlist quotes with sparkline data',
            '/api/sectors': 'Sector performance aggregated from quotes',
            '/api/movers': 'Top gainers and losers',
            '/api/indices': 'Market indices (S&P 500, NASDAQ, etc.)',
            '/api/news': 'Latest market news',
            '/api/health': 'Health check'
        }
    })


# ============================================================================
# Main
# ============================================================================

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("Stock Monitor Dashboard API")
    print("=" * 60)
    print("Starting server on http://localhost:5001")
    print("Endpoints:")
    print("  GET /api/all      - All data in one request (fastest)")
    print("  GET /api/quotes   - All watchlist quotes")
    print("  GET /api/sectors  - Sector performance")
    print("  GET /api/movers   - Top gainers/losers")
    print("  GET /api/indices  - Market indices")
    print("  GET /api/news     - Market news")
    print("  GET /api/health   - Health check")
    print("=" * 60)
    print("Starting background data warmup...")
    print("=" * 60 + "\n")

    # Start warmup in background thread
    warmup_thread = threading.Thread(target=warmup_cache, daemon=True)
    warmup_thread.start()

    app.run(host='0.0.0.0', port=5001, debug=True, use_reloader=False)
