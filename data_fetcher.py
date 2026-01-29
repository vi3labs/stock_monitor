"""
Data Fetcher Module
===================
Fetches stock prices, pre/post market data, earnings dates, and other financial data.
Uses yfinance (free) as the primary data source.

Parallelization:
- Uses ThreadPoolExecutor for concurrent fetching
- Configurable batch sizes and delays to respect rate limits
- Thread-safe caching
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Callable, Any
import logging
from functools import lru_cache
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

logger = logging.getLogger(__name__)

# Parallelization configuration
DEFAULT_MAX_WORKERS = 10  # Conservative default to avoid rate limits
DEFAULT_BATCH_SIZE = 20   # Process symbols in batches
DEFAULT_BATCH_DELAY = 0.5  # Seconds between batches


class StockDataFetcher:
    """
    Fetches stock data from Yahoo Finance with parallel processing.

    Parallelization is used for:
    - Pre-market/post-market data fetching
    - Earnings and dividend calendar lookups
    - Weekly performance calculations
    - Market indices and futures

    Rate limit protection:
    - Configurable max workers (default: 10)
    - Batch processing with delays between batches
    - Thread-safe caching
    """

    def __init__(
        self,
        symbols: List[str],
        cache_duration_minutes: int = 5,
        max_workers: int = DEFAULT_MAX_WORKERS,
        batch_size: int = DEFAULT_BATCH_SIZE,
        batch_delay: float = DEFAULT_BATCH_DELAY
    ):
        self.symbols = symbols
        self.cache_duration = cache_duration_minutes
        self.max_workers = max_workers
        self.batch_size = batch_size
        self.batch_delay = batch_delay

        # Thread-safe cache
        self._cache = {}
        self._cache_time = {}
        self._cache_lock = threading.Lock()

        # Separate crypto symbols (they have different behavior)
        self.crypto_symbols = [s for s in symbols if s.endswith('-USD')]
        self.stock_symbols = [s for s in symbols if not s.endswith('-USD')]
    
    def _is_cache_valid(self, key: str) -> bool:
        """Check if cached data is still valid (thread-safe)."""
        with self._cache_lock:
            if key not in self._cache_time:
                return False
            elapsed = (datetime.now() - self._cache_time[key]).total_seconds() / 60
            return elapsed < self.cache_duration

    def _set_cache(self, key: str, value: Any) -> None:
        """Set cache value (thread-safe)."""
        with self._cache_lock:
            self._cache[key] = value
            self._cache_time[key] = datetime.now()

    def _get_cache(self, key: str) -> Optional[Any]:
        """Get cache value (thread-safe)."""
        with self._cache_lock:
            return self._cache.get(key)

    def _parallel_fetch(
        self,
        symbols: List[str],
        fetch_func: Callable[[str], Optional[dict]],
        description: str = "symbols"
    ) -> Dict[str, dict]:
        """
        Generic parallel fetch helper.

        Processes symbols in batches with configurable delays to respect rate limits.

        Args:
            symbols: List of symbols to fetch
            fetch_func: Function that takes a symbol and returns a dict or None
            description: Description for logging

        Returns:
            Dict mapping symbol to fetched data
        """
        results = {}
        total_symbols = len(symbols)

        if total_symbols == 0:
            return results

        # Process in batches to avoid overwhelming the API
        for batch_start in range(0, total_symbols, self.batch_size):
            batch_end = min(batch_start + self.batch_size, total_symbols)
            batch = symbols[batch_start:batch_end]

            logger.debug(f"Processing batch {batch_start // self.batch_size + 1} "
                        f"({batch_start + 1}-{batch_end} of {total_symbols} {description})")

            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_symbol = {
                    executor.submit(fetch_func, symbol): symbol
                    for symbol in batch
                }

                for future in as_completed(future_to_symbol):
                    symbol = future_to_symbol[future]
                    try:
                        result = future.result()
                        if result is not None:
                            results[symbol] = result
                    except Exception as e:
                        logger.warning(f"Error fetching {symbol}: {e}")

            # Delay between batches to respect rate limits
            if batch_end < total_symbols:
                time.sleep(self.batch_delay)

        return results
    
    def get_batch_quotes(self, symbols: List[str] = None) -> Dict[str, dict]:
        """
        Get current quotes for multiple symbols efficiently using parallel processing.

        Uses yfinance batch download for initial ticker objects, then parallelizes
        the extraction of detailed info for each symbol.

        Returns dict with symbol as key and quote data as value.
        """
        symbols = symbols or self.symbols
        cache_key = f"quotes_{'_'.join(sorted(symbols[:10]))}_{len(symbols)}"  # Simplified cache key

        if self._is_cache_valid(cache_key):
            return self._get_cache(cache_key)

        results = {}
        start_time = time.time()

        try:
            # Process in batches to avoid memory issues with large symbol lists
            all_tickers = {}
            for batch_start in range(0, len(symbols), self.batch_size):
                batch_end = min(batch_start + self.batch_size, len(symbols))
                batch_symbols = symbols[batch_start:batch_end]

                logger.debug(f"Loading tickers batch {batch_start // self.batch_size + 1}")
                tickers = yf.Tickers(' '.join(batch_symbols))
                all_tickers.update(tickers.tickers)

                if batch_end < len(symbols):
                    time.sleep(self.batch_delay * 0.5)  # Shorter delay for ticker loading

            def extract_quote_data(symbol: str) -> Optional[dict]:
                """Extract quote data for a single symbol."""
                ticker = all_tickers.get(symbol)
                if ticker is None:
                    return None

                try:
                    info = ticker.fast_info
                    full_info = ticker.info

                    data = {
                        'symbol': symbol,
                        'name': full_info.get('shortName', symbol),
                        'price': info.get('lastPrice', 0),
                        'previous_close': info.get('previousClose', 0),
                        'open': info.get('open', 0),
                        'day_high': info.get('dayHigh', 0),
                        'day_low': info.get('dayLow', 0),
                        'volume': info.get('lastVolume', 0),
                        'avg_volume': full_info.get('averageVolume', 0),
                        'market_cap': info.get('marketCap', 0),
                        'fifty_two_week_high': info.get('yearHigh', 0),
                        'fifty_two_week_low': info.get('yearLow', 0),
                        'pre_market_price': full_info.get('preMarketPrice'),
                        'pre_market_change': full_info.get('preMarketChangePercent'),
                        'post_market_price': full_info.get('postMarketPrice'),
                        'post_market_change': full_info.get('postMarketChangePercent'),
                        'currency': full_info.get('currency', 'USD'),
                    }

                    # Calculate change
                    if data['previous_close'] > 0:
                        change = data['price'] - data['previous_close']
                        change_pct = (change / data['previous_close']) * 100
                        data['change'] = change
                        data['change_percent'] = change_pct
                    else:
                        data['change'] = 0
                        data['change_percent'] = 0

                    # Calculate volume ratio
                    if data['avg_volume'] > 0:
                        data['volume_ratio'] = data['volume'] / data['avg_volume']
                    else:
                        data['volume_ratio'] = 1.0

                    return data

                except Exception as e:
                    logger.warning(f"Error extracting data for {symbol}: {e}")
                    return None

            # Parallel extraction of quote data
            results = self._parallel_fetch(symbols, extract_quote_data, "quotes")

            elapsed = time.time() - start_time
            logger.info(f"Fetched {len(results)} quotes in {elapsed:.2f}s")

            self._set_cache(cache_key, results)

        except Exception as e:
            logger.error(f"Error in batch quote fetch: {e}")

        return results
    
    def get_premarket_data(self) -> Dict[str, dict]:
        """
        Get pre-market data for all symbols using parallel processing.

        Returns dict with pre-market prices and changes for symbols
        that have pre-market data available.
        """
        cache_key = f"premarket_{len(self.symbols)}"

        if self._is_cache_valid(cache_key):
            return self._get_cache(cache_key)

        start_time = time.time()

        def fetch_premarket(symbol: str) -> Optional[dict]:
            """Fetch pre-market data for a single symbol."""
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info

                pre_price = info.get('preMarketPrice')
                prev_close = info.get('previousClose', 0)

                if pre_price and prev_close > 0:
                    change = pre_price - prev_close
                    change_pct = (change / prev_close) * 100

                    return {
                        'symbol': symbol,
                        'name': info.get('shortName', symbol),
                        'pre_market_price': pre_price,
                        'previous_close': prev_close,
                        'pre_market_change': change,
                        'pre_market_change_percent': change_pct,
                    }
                return None
            except Exception as e:
                logger.warning(f"Error fetching pre-market for {symbol}: {e}")
                return None

        results = self._parallel_fetch(self.symbols, fetch_premarket, "pre-market")

        elapsed = time.time() - start_time
        logger.info(f"Fetched {len(results)} pre-market quotes in {elapsed:.2f}s")

        self._set_cache(cache_key, results)
        return results
    
    def get_postmarket_data(self) -> Dict[str, dict]:
        """
        Get post-market (after hours) data for all symbols using parallel processing.

        Returns dict with post-market prices and changes for symbols
        that have post-market data available.
        """
        cache_key = f"postmarket_{len(self.symbols)}"

        if self._is_cache_valid(cache_key):
            return self._get_cache(cache_key)

        start_time = time.time()

        def fetch_postmarket(symbol: str) -> Optional[dict]:
            """Fetch post-market data for a single symbol."""
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info

                post_price = info.get('postMarketPrice')
                regular_close = info.get('regularMarketPrice', 0)

                if post_price and regular_close > 0:
                    change = post_price - regular_close
                    change_pct = (change / regular_close) * 100

                    return {
                        'symbol': symbol,
                        'name': info.get('shortName', symbol),
                        'post_market_price': post_price,
                        'regular_close': regular_close,
                        'post_market_change': change,
                        'post_market_change_percent': change_pct,
                    }
                return None
            except Exception as e:
                logger.warning(f"Error fetching post-market for {symbol}: {e}")
                return None

        results = self._parallel_fetch(self.symbols, fetch_postmarket, "post-market")

        elapsed = time.time() - start_time
        logger.info(f"Fetched {len(results)} post-market quotes in {elapsed:.2f}s")

        self._set_cache(cache_key, results)
        return results
    
    def get_earnings_calendar(self, days_ahead: int = 14) -> List[dict]:
        """
        Get upcoming earnings dates for watchlist stocks using parallel processing.

        Checks both calendar and earnings_dates attributes for each ticker.
        Returns deduplicated and sorted list of upcoming earnings.
        """
        cache_key = f"earnings_{days_ahead}_{len(self.stock_symbols)}"

        if self._is_cache_valid(cache_key):
            return self._get_cache(cache_key)

        start_time = time.time()
        cutoff_date = (datetime.now() + timedelta(days=days_ahead)).date()
        today = datetime.now().date()

        # Thread-safe collection for earnings
        earnings_lock = threading.Lock()
        all_earnings = []

        def fetch_earnings(symbol: str) -> Optional[dict]:
            """Fetch earnings data for a single symbol."""
            symbol_earnings = []
            try:
                ticker = yf.Ticker(symbol)
                name = None

                # Try to get earnings dates from calendar
                try:
                    cal = ticker.calendar
                    if cal is not None and not cal.empty:
                        if 'Earnings Date' in cal.index:
                            earnings_dates = cal.loc['Earnings Date']
                            if isinstance(earnings_dates, pd.Timestamp):
                                earnings_dates = [earnings_dates]

                            for date in earnings_dates:
                                if isinstance(date, pd.Timestamp):
                                    if date.date() <= cutoff_date:
                                        if name is None:
                                            name = ticker.info.get('shortName', symbol)
                                        symbol_earnings.append({
                                            'symbol': symbol,
                                            'name': name,
                                            'date': date.strftime('%Y-%m-%d'),
                                            'time': 'TBD'
                                        })
                except Exception:
                    pass

                # Also check earnings_dates attribute
                try:
                    ed = ticker.earnings_dates
                    if ed is not None and not ed.empty:
                        for date in ed.index[:2]:
                            if date.date() <= cutoff_date and date.date() >= today:
                                if name is None:
                                    name = ticker.info.get('shortName', symbol)
                                symbol_earnings.append({
                                    'symbol': symbol,
                                    'name': name,
                                    'date': date.strftime('%Y-%m-%d'),
                                    'time': 'TBD'
                                })
                except Exception:
                    pass

                # Add to shared list if we found earnings
                if symbol_earnings:
                    with earnings_lock:
                        all_earnings.extend(symbol_earnings)

            except Exception as e:
                logger.warning(f"Error fetching earnings for {symbol}: {e}")

            return None  # Results collected via shared list

        # Parallel fetch
        self._parallel_fetch(self.stock_symbols, fetch_earnings, "earnings")

        # Remove duplicates and sort by date
        seen = set()
        unique_earnings = []
        for e in all_earnings:
            key = (e['symbol'], e['date'])
            if key not in seen:
                seen.add(key)
                unique_earnings.append(e)

        unique_earnings.sort(key=lambda x: x['date'])

        elapsed = time.time() - start_time
        logger.info(f"Fetched earnings calendar ({len(unique_earnings)} events) in {elapsed:.2f}s")

        self._set_cache(cache_key, unique_earnings)
        return unique_earnings
    
    def get_dividend_calendar(self, days_ahead: int = 30) -> List[dict]:
        """
        Get upcoming ex-dividend dates for watchlist stocks using parallel processing.

        Returns sorted list of upcoming dividends within the specified window.
        """
        cache_key = f"dividends_{days_ahead}_{len(self.stock_symbols)}"

        if self._is_cache_valid(cache_key):
            return self._get_cache(cache_key)

        start_time = time.time()
        today = datetime.now().date()
        cutoff_date = (datetime.now() + timedelta(days=days_ahead)).date()

        def fetch_dividend(symbol: str) -> Optional[dict]:
            """Fetch dividend data for a single symbol."""
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info

                ex_div_date = info.get('exDividendDate')
                if ex_div_date:
                    # Convert timestamp to datetime
                    if isinstance(ex_div_date, (int, float)):
                        ex_date = datetime.fromtimestamp(ex_div_date)
                    else:
                        ex_date = ex_div_date

                    if ex_date.date() >= today and ex_date.date() <= cutoff_date:
                        return {
                            'symbol': symbol,
                            'name': info.get('shortName', symbol),
                            'ex_date': ex_date.strftime('%Y-%m-%d'),
                            'dividend_rate': info.get('dividendRate', 0),
                            'dividend_yield': info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 0
                        }
                return None
            except Exception as e:
                logger.warning(f"Error fetching dividend for {symbol}: {e}")
                return None

        results = self._parallel_fetch(self.stock_symbols, fetch_dividend, "dividends")

        # Convert to list and sort by date
        dividends = list(results.values())
        dividends.sort(key=lambda x: x['ex_date'])

        elapsed = time.time() - start_time
        logger.info(f"Fetched dividend calendar ({len(dividends)} events) in {elapsed:.2f}s")

        self._set_cache(cache_key, dividends)
        return dividends
    
    def get_historical_data(self, symbol: str, period: str = "1mo") -> pd.DataFrame:
        """
        Get historical price data for a symbol.
        period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
        """
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period)
            return hist
        except Exception as e:
            logger.error(f"Error fetching historical data for {symbol}: {e}")
            return pd.DataFrame()
    
    def get_weekly_performance(self) -> Dict[str, dict]:
        """
        Calculate weekly performance for all symbols using parallel processing.

        Returns dict with weekly price change, daily closes for sparklines,
        high/low range, and total volume.
        """
        cache_key = f"weekly_{len(self.symbols)}"

        if self._is_cache_valid(cache_key):
            return self._get_cache(cache_key)

        start_time = time.time()
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)

        def fetch_weekly(symbol: str) -> Optional[dict]:
            """Fetch weekly performance for a single symbol."""
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(start=start_date, end=end_date)

                if not hist.empty and len(hist) >= 2:
                    start_price = hist['Close'].iloc[0]
                    end_price = hist['Close'].iloc[-1]

                    change = end_price - start_price
                    change_pct = (change / start_price) * 100

                    # Daily changes for sparkline
                    daily_changes = hist['Close'].pct_change().dropna().tolist()

                    return {
                        'symbol': symbol,
                        'start_price': start_price,
                        'end_price': end_price,
                        'week_change': change,
                        'week_change_percent': change_pct,
                        'daily_closes': hist['Close'].tolist(),
                        'daily_changes': daily_changes,
                        'high': hist['High'].max(),
                        'low': hist['Low'].min(),
                        'total_volume': hist['Volume'].sum(),
                    }
                return None
            except Exception as e:
                logger.warning(f"Error fetching weekly data for {symbol}: {e}")
                return None

        results = self._parallel_fetch(self.symbols, fetch_weekly, "weekly performance")

        elapsed = time.time() - start_time
        logger.info(f"Fetched weekly performance for {len(results)} symbols in {elapsed:.2f}s")

        self._set_cache(cache_key, results)
        return results
    
    def get_market_indices(self) -> Dict[str, dict]:
        """
        Get major market index data for context using parallel processing.

        Fetches S&P 500, NASDAQ, Dow Jones, VIX, and Russell 2000 concurrently.
        """
        cache_key = "market_indices"

        if self._is_cache_valid(cache_key):
            return self._get_cache(cache_key)

        start_time = time.time()

        indices = {
            '^GSPC': 'S&P 500',
            '^IXIC': 'NASDAQ',
            '^DJI': 'Dow Jones',
            '^VIX': 'VIX',
            '^RUT': 'Russell 2000',
        }

        def fetch_index(symbol: str) -> Optional[dict]:
            """Fetch data for a single market index."""
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.fast_info
                full_info = ticker.info

                prev_close = info.get('previousClose', 0)
                current = info.get('lastPrice', 0)

                if prev_close > 0:
                    change = current - prev_close
                    change_pct = (change / prev_close) * 100
                else:
                    change = 0
                    change_pct = 0

                return {
                    'symbol': symbol,
                    'name': indices[symbol],
                    'price': current,
                    'change': change,
                    'change_percent': change_pct,
                    'pre_market_price': full_info.get('preMarketPrice'),
                    'pre_market_change': full_info.get('preMarketChangePercent'),
                }
            except Exception as e:
                logger.warning(f"Error fetching index {symbol}: {e}")
                return None

        # Use higher parallelism for small fixed set of indices
        with ThreadPoolExecutor(max_workers=len(indices)) as executor:
            future_to_symbol = {
                executor.submit(fetch_index, symbol): symbol
                for symbol in indices.keys()
            }

            results = {}
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    result = future.result()
                    if result is not None:
                        results[symbol] = result
                except Exception as e:
                    logger.warning(f"Error fetching index {symbol}: {e}")

        elapsed = time.time() - start_time
        logger.info(f"Fetched {len(results)} market indices in {elapsed:.2f}s")

        self._set_cache(cache_key, results)
        return results
    
    def get_top_movers(self, quotes: Dict[str, dict], n: int = 10) -> Tuple[List[dict], List[dict]]:
        """
        Get top gainers and losers from quotes.
        Returns (gainers, losers) sorted by change percent.
        """
        sorted_stocks = sorted(
            quotes.values(),
            key=lambda x: x.get('change_percent', 0),
            reverse=True
        )
        
        gainers = [s for s in sorted_stocks if s.get('change_percent', 0) > 0][:n]
        losers = [s for s in sorted_stocks if s.get('change_percent', 0) < 0][-n:][::-1]
        
        return gainers, losers


class FuturesDataFetcher:
    """Fetches futures data for pre-market context using parallel processing."""

    FUTURES_SYMBOLS = {
        'ES=F': 'S&P 500 Futures',
        'NQ=F': 'NASDAQ Futures',
        'YM=F': 'Dow Futures',
        'RTY=F': 'Russell 2000 Futures',
    }

    def __init__(self):
        self._cache = {}
        self._cache_time = {}
        self._cache_lock = threading.Lock()
        self.cache_duration = 2  # Minutes

    def _is_cache_valid(self) -> bool:
        """Check if cached data is still valid."""
        with self._cache_lock:
            if 'futures' not in self._cache_time:
                return False
            elapsed = (datetime.now() - self._cache_time['futures']).total_seconds() / 60
            return elapsed < self.cache_duration

    def get_futures(self) -> Dict[str, dict]:
        """Get current futures data using parallel processing."""
        if self._is_cache_valid():
            with self._cache_lock:
                return self._cache.get('futures', {})

        start_time = time.time()

        def fetch_future(symbol: str) -> Optional[dict]:
            """Fetch data for a single futures contract."""
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.fast_info

                prev_close = info.get('previousClose', 0)
                current = info.get('lastPrice', 0)

                if prev_close > 0:
                    change = current - prev_close
                    change_pct = (change / prev_close) * 100
                else:
                    change = 0
                    change_pct = 0

                return {
                    'symbol': symbol,
                    'name': self.FUTURES_SYMBOLS[symbol],
                    'price': current,
                    'change': change,
                    'change_percent': change_pct,
                }
            except Exception as e:
                logger.warning(f"Error fetching futures {symbol}: {e}")
                return None

        # Parallel fetch for all futures contracts
        with ThreadPoolExecutor(max_workers=len(self.FUTURES_SYMBOLS)) as executor:
            future_to_symbol = {
                executor.submit(fetch_future, symbol): symbol
                for symbol in self.FUTURES_SYMBOLS.keys()
            }

            results = {}
            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    result = future.result()
                    if result is not None:
                        results[symbol] = result
                except Exception as e:
                    logger.warning(f"Error fetching futures {symbol}: {e}")

        elapsed = time.time() - start_time
        logger.info(f"Fetched {len(results)} futures contracts in {elapsed:.2f}s")

        with self._cache_lock:
            self._cache['futures'] = results
            self._cache_time['futures'] = datetime.now()

        return results


class TrendsFetcher:
    """
    Fetches Google Trends data for stock symbols.

    Provides "silent attention" signals - shows which tickers are gaining
    or losing public search interest.

    Rate limiting:
    - Batch size: 5 symbols max per request (Google's limit)
    - Delay: 3 seconds between batches
    - Cache: 60 minutes (trends don't change fast)
    """

    def __init__(self, cache_duration_minutes: int = 60):
        self._cache = {}
        self._cache_time = {}
        self._cache_lock = threading.Lock()
        self.cache_duration = cache_duration_minutes
        self._pytrends = None

    def _get_pytrends(self):
        """Lazy-load pytrends to avoid import errors if not installed."""
        if self._pytrends is None:
            try:
                from pytrends.request import TrendReq
                self._pytrends = TrendReq(hl='en-US', tz=300, timeout=(10, 25))
            except ImportError:
                logger.warning("pytrends not installed. Run: pip install pytrends")
                return None
        return self._pytrends

    def _is_cache_valid(self, key: str) -> bool:
        """Check if cached data is still valid."""
        with self._cache_lock:
            if key not in self._cache_time:
                return False
            elapsed = (datetime.now() - self._cache_time[key]).total_seconds() / 60
            return elapsed < self.cache_duration

    def _set_cache(self, key: str, value) -> None:
        """Set cache value."""
        with self._cache_lock:
            self._cache[key] = value
            self._cache_time[key] = datetime.now()

    def _get_cache(self, key: str):
        """Get cache value."""
        with self._cache_lock:
            return self._cache.get(key)

    def get_trends(
        self,
        symbols: List[str],
        company_names: Optional[Dict[str, str]] = None,
        max_symbols: int = 30
    ) -> Dict[str, dict]:
        """
        Fetch Google Trends data for stock symbols.

        Args:
            symbols: List of stock tickers
            company_names: Optional dict mapping ticker -> company name
            max_symbols: Maximum symbols to fetch (default 30)

        Returns:
            Dict mapping symbol to trends data:
            {
                "NVDA": {
                    "interest_score": 75,      # 0-100 scale
                    "interest_change": 15,     # % change vs avg
                    "direction": "rising",     # rising|falling|stable
                    "top_query": "nvidia earnings"  # related query
                }
            }
        """
        cache_key = f"trends_{len(symbols)}"
        if self._is_cache_valid(cache_key):
            cached = self._get_cache(cache_key)
            if cached:
                return cached

        pytrends = self._get_pytrends()
        if pytrends is None:
            return {}

        start_time = time.time()
        results = {}

        # Limit symbols to avoid rate limits
        symbols_to_fetch = symbols[:max_symbols]
        company_names = company_names or {}

        # Build search terms (use "SYMBOL stock" for better results)
        search_terms = {}
        for symbol in symbols_to_fetch:
            # Use company name if available for ambiguous tickers
            if symbol in ['META', 'CAT', 'F', 'V', 'T', 'C']:
                term = f"{company_names.get(symbol, symbol)} stock"
            else:
                term = f"{symbol} stock"
            search_terms[symbol] = term

        # Process in batches of 5 (Google's limit per request)
        batch_size = 5
        batches = [
            list(search_terms.items())[i:i + batch_size]
            for i in range(0, len(search_terms), batch_size)
        ]

        for batch_idx, batch in enumerate(batches):
            try:
                # Build keyword list for this batch
                keywords = [term for _, term in batch]

                # Build payload with 7-day timeframe
                pytrends.build_payload(keywords, timeframe='now 7-d', geo='US')

                # Get interest over time
                interest_df = pytrends.interest_over_time()

                if interest_df is not None and not interest_df.empty:
                    # Remove 'isPartial' column if present
                    if 'isPartial' in interest_df.columns:
                        interest_df = interest_df.drop(columns=['isPartial'])

                    for symbol, term in batch:
                        if term in interest_df.columns:
                            values = interest_df[term].values
                            if len(values) > 0:
                                # Current value is last data point
                                current = int(values[-1])
                                # Average is mean of all values
                                avg = float(values.mean())

                                # Calculate change vs average
                                if avg > 0:
                                    change = ((current - avg) / avg) * 100
                                else:
                                    change = 0

                                # Determine direction
                                if change > 20:
                                    direction = "surging"
                                elif change > 5:
                                    direction = "rising"
                                elif change < -5:
                                    direction = "falling"
                                else:
                                    direction = "stable"

                                results[symbol] = {
                                    'interest_score': current,
                                    'interest_change': round(change, 1),
                                    'direction': direction,
                                    'top_query': None  # Will try to get related queries
                                }

                # Try to get related queries for context
                try:
                    related = pytrends.related_queries()
                    for symbol, term in batch:
                        if term in related and related[term]['top'] is not None:
                            top_queries = related[term]['top']
                            if len(top_queries) > 0:
                                # Get top related query (excluding the search term itself)
                                for _, row in top_queries.head(3).iterrows():
                                    query = row['query'].lower()
                                    if symbol.lower() not in query and 'stock' not in query:
                                        if symbol in results:
                                            results[symbol]['top_query'] = row['query']
                                        break
                except Exception as e:
                    logger.debug(f"Could not fetch related queries: {e}")

            except Exception as e:
                logger.warning(f"Error fetching trends batch {batch_idx + 1}: {e}")

            # Delay between batches to avoid rate limits
            if batch_idx < len(batches) - 1:
                time.sleep(3)

        elapsed = time.time() - start_time
        logger.info(f"Fetched trends for {len(results)}/{len(symbols_to_fetch)} symbols in {elapsed:.1f}s")

        self._set_cache(cache_key, results)
        return results

    def get_top_trends_movers(self, trends_data: Dict[str, dict], n: int = 5) -> List[dict]:
        """
        Get top trends movers sorted by absolute interest change.
        Returns mix of rising and falling.
        """
        if not trends_data:
            return []

        # Convert to list with symbol included
        items = [
            {'symbol': symbol, **data}
            for symbol, data in trends_data.items()
        ]

        # Sort by absolute change
        items.sort(key=lambda x: abs(x.get('interest_change', 0)), reverse=True)

        return items[:n]


if __name__ == "__main__":
    # Test the fetcher with parallelization
    from notion_watchlist import get_watchlist

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    all_symbols = get_watchlist()  # Fetch from Notion
    print(f"\n{'='*60}")
    print(f"PARALLELIZED DATA FETCHER TEST")
    print(f"{'='*60}")
    print(f"Total symbols in watchlist: {len(all_symbols)}")

    # Test with different sample sizes
    for test_size in [10, 30, len(all_symbols)]:
        symbols = all_symbols[:test_size]
        print(f"\n{'-'*40}")
        print(f"Testing with {len(symbols)} symbols")
        print(f"{'-'*40}")

        fetcher = StockDataFetcher(
            symbols,
            max_workers=10,
            batch_size=20,
            batch_delay=0.5
        )

        # Test batch quotes
        start = time.time()
        quotes = fetcher.get_batch_quotes()
        elapsed = time.time() - start
        print(f"\nBatch quotes: {len(quotes)} results in {elapsed:.2f}s")

        if quotes and test_size <= 10:
            for symbol, data in quotes.items():
                print(f"  {symbol}: ${data['price']:.2f} ({data['change_percent']:+.2f}%)")

        # Test pre-market (skip cache)
        fetcher._cache.clear()
        fetcher._cache_time.clear()

        start = time.time()
        premarket = fetcher.get_premarket_data()
        elapsed = time.time() - start
        print(f"Pre-market data: {len(premarket)} results in {elapsed:.2f}s")

        # Test weekly performance (use small sample to save time)
        if test_size <= 30:
            fetcher._cache.clear()
            fetcher._cache_time.clear()

            start = time.time()
            weekly = fetcher.get_weekly_performance()
            elapsed = time.time() - start
            print(f"Weekly performance: {len(weekly)} results in {elapsed:.2f}s")

        # Only run full test once
        if test_size == len(all_symbols):
            break

    print(f"\n{'='*60}")
    print("Testing market indices and futures")
    print(f"{'='*60}")

    start = time.time()
    indices = fetcher.get_market_indices()
    elapsed = time.time() - start
    print(f"\nMarket indices: {len(indices)} results in {elapsed:.2f}s")
    for symbol, data in indices.items():
        print(f"  {data['name']}: {data['change_percent']:+.2f}%")

    futures_fetcher = FuturesDataFetcher()
    start = time.time()
    futures = futures_fetcher.get_futures()
    elapsed = time.time() - start
    print(f"\nFutures: {len(futures)} results in {elapsed:.2f}s")
    for symbol, data in futures.items():
        print(f"  {data['name']}: {data['change_percent']:+.2f}%")

    print(f"\n{'='*60}")
    print("All tests completed successfully!")
    print(f"{'='*60}")
