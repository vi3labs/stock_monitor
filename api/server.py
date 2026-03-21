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
import json
import logging
import queue
import threading
import time
from datetime import datetime
from typing import Dict, List, Tuple

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, jsonify, request, Response, send_from_directory
from flask_cors import CORS

from data_fetcher import StockDataFetcher
from news_fetcher import NewsFetcher
from notion_watchlist import get_watchlist, get_watchlist_with_metadata, add_to_watchlist, update_stock_metadata
from notion_sync import SECTOR_MAP, COMPANY_NAMES

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
DASHBOARD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'dashboard')
app = Flask(__name__, static_folder=DASHBOARD_DIR, static_url_path='/dashboard')
CORS(app)  # Enable CORS for frontend requests

# Cache configuration
CACHE_DURATION_MINUTES = 5

# SSE clients
_sse_clients = []


def notify_sse_clients(data):
    """Send data update to all connected SSE clients."""
    dead_clients = []
    for q in _sse_clients:
        try:
            q.put_nowait(data)
        except Exception:
            dead_clients.append(q)
    for q in dead_clients:
        if q in _sse_clients:
            _sse_clients.remove(q)


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
                'sentiment': meta_info.get('sentiment', ''),
                'status': meta_info.get('status', ''),
                'investment_thesis': meta_info.get('investment_thesis', ''),
                'catalysts': meta_info.get('catalysts', ''),
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

    def get_futures(self, force_refresh: bool = False) -> Dict:
        """Get futures data (ES, NQ, YM, RTY)."""
        if not force_refresh and hasattr(self, '_futures_cache') and self._is_cache_valid(getattr(self, '_futures_time', None)):
            logger.info("Returning cached futures")
            return self._futures_cache

        logger.info("Fetching futures data...")
        from data_fetcher import FuturesDataFetcher
        fetcher = FuturesDataFetcher()
        futures = fetcher.get_futures()
        self._futures_cache = futures
        self._futures_time = datetime.now()
        logger.info(f"Fetched {len(futures)} futures")
        return futures

    def get_earnings(self, days_ahead: int = 14) -> List[Dict]:
        """Get upcoming earnings calendar for watchlist stocks."""
        if hasattr(self, '_earnings_cache') and self._is_cache_valid(getattr(self, '_earnings_time', None)):
            logger.info("Returning cached earnings")
            return self._earnings_cache

        symbols = self.get_watchlist_symbols()
        if not symbols:
            return []

        logger.info(f"Fetching earnings calendar ({days_ahead} days ahead)...")
        fetcher = StockDataFetcher(symbols, cache_duration_minutes=CACHE_DURATION_MINUTES)
        earnings = fetcher.get_earnings_calendar(days_ahead=days_ahead)
        self._earnings_cache = earnings
        self._earnings_time = datetime.now()
        logger.info(f"Fetched {len(earnings)} earnings events")
        return earnings


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

            # Notify SSE clients
            notify_sse_clients({
                'type': 'refresh',
                'timestamp': datetime.now().isoformat(),
                'quotes_count': len(data_service._quotes_cache or {}),
            })

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


@app.route('/api/stream')
def api_stream():
    """SSE endpoint for real-time data updates."""
    def event_stream():
        q = queue.Queue()
        _sse_clients.append(q)
        try:
            while True:
                try:
                    data = q.get(timeout=30)  # 30s keepalive
                    yield f"data: {json.dumps(data)}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        except GeneratorExit:
            pass
        finally:
            if q in _sse_clients:
                _sse_clients.remove(q)

    return Response(event_stream(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@app.route('/api/futures', methods=['GET'])
def api_futures():
    """Get futures data (ES, NQ, YM, RTY)."""
    try:
        futures = data_service.get_futures()
        return jsonify(futures)
    except Exception as e:
        logger.exception("Error fetching futures")
        return jsonify({'error': str(e)}), 500


@app.route('/api/earnings', methods=['GET'])
def api_earnings():
    """Get upcoming earnings calendar for watchlist stocks."""
    try:
        days = request.args.get('days', 14, type=int)
        earnings = data_service.get_earnings(days)
        return jsonify(earnings)
    except Exception as e:
        logger.exception("Error fetching earnings")
        return jsonify({'error': str(e)}), 500


@app.route('/api/watchlist', methods=['POST'])
def api_add_ticker():
    """Add a new ticker to the Notion watchlist."""
    try:
        data = request.get_json()
        if not data or not data.get('ticker'):
            return jsonify({'error': 'ticker is required'}), 400

        ticker = data['ticker'].upper().strip()

        # Validate ticker exists via yfinance
        try:
            import yfinance as yf
            info = yf.Ticker(ticker).info
            if not info or info.get('regularMarketPrice') is None:
                return jsonify({'error': f'Invalid ticker: {ticker}'}), 400
            company_name = data.get('company_name') or info.get('shortName') or info.get('longName') or ticker
        except Exception as e:
            logger.warning(f"yfinance validation failed for {ticker}: {e}")
            company_name = data.get('company_name', ticker)

        # Create in Notion
        result = add_to_watchlist(
            ticker=ticker,
            sector=data.get('sector', ''),
            status=data.get('status', 'Watching'),
            sentiment=data.get('sentiment', ''),
            investment_thesis=data.get('investment_thesis', ''),
            catalysts=data.get('catalysts', ''),
            company_name=company_name,
        )

        if result is None:
            return jsonify({'error': 'Failed to add ticker to Notion'}), 500

        # Invalidate caches so new ticker appears immediately
        data_service._quotes_cache = None
        data_service._quotes_time = None
        data_service._watchlist_meta = None

        return jsonify(result), 201

    except Exception as e:
        logger.exception("Error adding ticker")
        return jsonify({'error': str(e)}), 500


@app.route('/api/watchlist/<symbol>', methods=['PATCH'])
def api_update_ticker(symbol):
    """Update metadata for an existing ticker in the Notion watchlist."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Request body is required'}), 400

        # Find the page_id for this symbol from cached metadata
        meta = data_service.get_watchlist_metadata()
        stock = next((s for s in meta if s['ticker'].upper() == symbol.upper()), None)

        if not stock or not stock.get('page_id'):
            return jsonify({'error': f'Ticker {symbol} not found in watchlist'}), 404

        # Update in Notion
        success = update_stock_metadata(
            page_id=stock['page_id'],
            sentiment=data.get('sentiment'),
            investment_thesis=data.get('investment_thesis'),
            catalysts=data.get('catalysts'),
            status=data.get('status'),
            sector=data.get('sector'),
        )

        if not success:
            return jsonify({'error': 'Failed to update in Notion'}), 500

        # Invalidate metadata cache so changes are reflected
        data_service._watchlist_meta = None

        # Build updated stock data to return
        updated = {**stock}
        for field in ['sentiment', 'investment_thesis', 'catalysts', 'status', 'sector']:
            if data.get(field) is not None:
                updated[field] = data[field]

        return jsonify(updated)

    except Exception as e:
        logger.exception(f"Error updating ticker {symbol}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/watchlist/<symbol>', methods=['DELETE'])
def api_delete_ticker(symbol):
    """Archive a ticker from the Notion watchlist (sets archived=true)."""
    try:
        meta = data_service.get_watchlist_metadata()
        stock = next((s for s in meta if s['ticker'].upper() == symbol.upper()), None)

        if not stock or not stock.get('page_id'):
            return jsonify({'error': f'Ticker {symbol} not found in watchlist'}), 404

        # Archive in Notion (not hard delete — recoverable)
        from notion_watchlist import _request_with_retry, HEADERS
        url = f"https://api.notion.com/v1/pages/{stock['page_id']}"
        response = _request_with_retry("PATCH", url, headers=HEADERS, json={"archived": True})

        if response.status_code != 200:
            return jsonify({'error': f'Failed to archive: {response.status_code}'}), 500

        # Invalidate all caches
        data_service._quotes_cache = None
        data_service._quotes_time = None
        data_service._watchlist_meta = None

        logger.info(f"Archived {symbol} from watchlist")
        return jsonify({'status': 'archived', 'ticker': symbol})

    except Exception as e:
        logger.exception(f"Error archiving ticker {symbol}")
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

        # Get futures (don't block if it fails)
        try:
            futures = data_service.get_futures()
        except Exception as futures_error:
            logger.warning(f"Failed to fetch futures: {futures_error}")
            futures = {}

        # Get earnings (don't block if it fails)
        try:
            earnings = data_service.get_earnings()
        except Exception as earnings_error:
            logger.warning(f"Failed to fetch earnings: {earnings_error}")
            earnings = []

        return jsonify({
            'quotes': quotes,
            'sectors': sectors,
            'movers': movers,
            'indices': indices,
            'news': news,
            'futures': futures,
            'earnings': earnings,
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
        'version': '1.1.0',
        'endpoints': {
            '/api/all': 'All dashboard data in one request (fastest)',
            '/api/quotes': 'All watchlist quotes with sparkline data',
            '/api/sectors': 'Sector performance aggregated from quotes',
            '/api/movers': 'Top gainers and losers',
            '/api/indices': 'Market indices (S&P 500, NASDAQ, etc.)',
            '/api/futures': 'Futures data (ES, NQ, YM, RTY)',
            '/api/earnings': 'Upcoming earnings calendar for watchlist stocks',
            '/api/news': 'Latest market news',
            '/api/stream': 'SSE endpoint for real-time data updates',
            '/api/health': 'Health check',
            '/api/history/reports': 'Weekly report metadata timeline',
            '/api/history/report/<date>/html': 'Raw HTML for a specific weekly report',
            '/api/history/snapshots': 'Weekly snapshot data (filterable by symbol, date range)',
            '/api/history/watchlist-changes': 'Watchlist additions and removals',
            '/api/history/streaks': 'Symbols with consecutive week streaks',
            '/api/performance/rolling': 'Top/bottom performers over rolling period',
        }
    })


@app.route('/api/history/reports')
def api_history_reports():
    """All weekly report metadata for timeline."""
    from db import get_all_report_metadata
    return jsonify(get_all_report_metadata())


@app.route('/api/history/report/<date>/html')
def api_history_report_html(date):
    """Raw HTML for a specific weekly report."""
    from db import get_all_report_metadata
    reports = get_all_report_metadata()
    report = next((r for r in reports if r['report_date'] == date), None)
    if not report or not report.get('file_path'):
        return jsonify({'error': 'Report not found'}), 404
    filepath = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), report['file_path'])
    if not os.path.exists(filepath):
        return jsonify({'error': 'Report file not found'}), 404
    with open(filepath, 'r') as f:
        return Response(f.read(), mimetype='text/html')


@app.route('/api/history/snapshots')
def api_history_snapshots():
    """Weekly snapshot data, filterable by symbol and date range."""
    from db import get_weekly_snapshots
    symbol = request.args.get('symbol')
    start = request.args.get('start')
    end = request.args.get('end')
    return jsonify(get_weekly_snapshots(symbol=symbol, start_date=start, end_date=end))


@app.route('/api/history/watchlist-changes')
def api_history_watchlist_changes():
    """Watchlist additions and removals over time."""
    from db import get_watchlist_changes
    return jsonify(get_watchlist_changes())


@app.route('/api/history/streaks')
def api_history_streaks():
    """Symbols with consecutive week streaks (up or down)."""
    from db import get_all_streaks
    return jsonify(get_all_streaks())


@app.route('/api/performance/rolling')
def api_performance_rolling():
    """Top/bottom performers over a rolling period."""
    from db import get_rolling_performers
    period = request.args.get('period', '1m')
    n = request.args.get('n', 5, type=int)
    weeks_map = {'1w': 1, '1m': 4, '3m': 13}
    weeks = weeks_map.get(period, 4)
    result = get_rolling_performers(n=n, weeks=weeks)
    for lst in [result.get('top', []), result.get('bottom', []), result.get('all', [])]:
        for p in lst:
            if 'cumulative_change' in p:
                p['change_pct'] = p.pop('cumulative_change')
    return jsonify(result)


@app.route('/dashboard/')
def dashboard_index():
    """Serve the dashboard UI."""
    return send_from_directory(DASHBOARD_DIR, 'index.html')


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
    print("  GET /api/futures  - Futures data (ES, NQ, YM, RTY)")
    print("  GET /api/earnings - Upcoming earnings calendar")
    print("  GET /api/news     - Market news")
    print("  GET /api/stream   - SSE real-time updates")
    print("  GET /api/health   - Health check")
    print("  GET /api/history/reports    - Report metadata timeline")
    print("  GET /api/history/snapshots  - Historical snapshots")
    print("  GET /api/history/streaks    - Consecutive week streaks")
    print("  GET /api/performance/rolling - Rolling top/bottom performers")
    print("=" * 60)
    print("Starting background data warmup...")
    print("=" * 60 + "\n")

    # Start warmup in background thread
    warmup_thread = threading.Thread(target=warmup_cache, daemon=True)
    warmup_thread.start()

    app.run(host='0.0.0.0', port=5001, debug=True, use_reloader=False)
