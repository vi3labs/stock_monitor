"""
Data Fetcher Module
===================
Fetches stock prices, pre/post market data, earnings dates, and other financial data.
Uses yfinance (free) as the primary data source.
"""

import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from functools import lru_cache
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


class StockDataFetcher:
    """Fetches stock data from Yahoo Finance."""
    
    def __init__(self, symbols: List[str], cache_duration_minutes: int = 5):
        self.symbols = symbols
        self.cache_duration = cache_duration_minutes
        self._cache = {}
        self._cache_time = {}
        
        # Separate crypto symbols (they have different behavior)
        self.crypto_symbols = [s for s in symbols if s.endswith('-USD')]
        self.stock_symbols = [s for s in symbols if not s.endswith('-USD')]
    
    def _is_cache_valid(self, key: str) -> bool:
        """Check if cached data is still valid."""
        if key not in self._cache_time:
            return False
        elapsed = (datetime.now() - self._cache_time[key]).total_seconds() / 60
        return elapsed < self.cache_duration
    
    def get_batch_quotes(self, symbols: List[str] = None) -> Dict[str, dict]:
        """
        Get current quotes for multiple symbols efficiently.
        Returns dict with symbol as key and quote data as value.
        """
        symbols = symbols or self.symbols
        cache_key = f"quotes_{'_'.join(sorted(symbols))}"
        
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]
        
        results = {}
        
        try:
            # Batch download is more efficient
            tickers = yf.Tickers(' '.join(symbols))
            
            for symbol in symbols:
                try:
                    ticker = tickers.tickers.get(symbol)
                    if ticker is None:
                        continue
                    
                    info = ticker.fast_info
                    
                    # Get additional info for pre/post market
                    full_info = ticker.info
                    
                    results[symbol] = {
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
                    if results[symbol]['previous_close'] > 0:
                        change = results[symbol]['price'] - results[symbol]['previous_close']
                        change_pct = (change / results[symbol]['previous_close']) * 100
                        results[symbol]['change'] = change
                        results[symbol]['change_percent'] = change_pct
                    else:
                        results[symbol]['change'] = 0
                        results[symbol]['change_percent'] = 0
                    
                    # Calculate volume ratio
                    if results[symbol]['avg_volume'] > 0:
                        results[symbol]['volume_ratio'] = results[symbol]['volume'] / results[symbol]['avg_volume']
                    else:
                        results[symbol]['volume_ratio'] = 1.0
                        
                except Exception as e:
                    logger.warning(f"Error fetching data for {symbol}: {e}")
                    continue
            
            self._cache[cache_key] = results
            self._cache_time[cache_key] = datetime.now()
            
        except Exception as e:
            logger.error(f"Error in batch quote fetch: {e}")
        
        return results
    
    def get_premarket_data(self) -> Dict[str, dict]:
        """
        Get pre-market data for all symbols.
        Returns dict with pre-market prices and changes.
        """
        results = {}
        
        for symbol in self.symbols:
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                
                pre_price = info.get('preMarketPrice')
                prev_close = info.get('previousClose', 0)
                
                if pre_price and prev_close > 0:
                    change = pre_price - prev_close
                    change_pct = (change / prev_close) * 100
                    
                    results[symbol] = {
                        'symbol': symbol,
                        'name': info.get('shortName', symbol),
                        'pre_market_price': pre_price,
                        'previous_close': prev_close,
                        'pre_market_change': change,
                        'pre_market_change_percent': change_pct,
                    }
            except Exception as e:
                logger.warning(f"Error fetching pre-market for {symbol}: {e}")
                continue
        
        return results
    
    def get_postmarket_data(self) -> Dict[str, dict]:
        """
        Get post-market (after hours) data for all symbols.
        """
        results = {}
        
        for symbol in self.symbols:
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.info
                
                post_price = info.get('postMarketPrice')
                regular_close = info.get('regularMarketPrice', 0)
                
                if post_price and regular_close > 0:
                    change = post_price - regular_close
                    change_pct = (change / regular_close) * 100
                    
                    results[symbol] = {
                        'symbol': symbol,
                        'name': info.get('shortName', symbol),
                        'post_market_price': post_price,
                        'regular_close': regular_close,
                        'post_market_change': change,
                        'post_market_change_percent': change_pct,
                    }
            except Exception as e:
                logger.warning(f"Error fetching post-market for {symbol}: {e}")
                continue
        
        return results
    
    def get_earnings_calendar(self, days_ahead: int = 14) -> List[dict]:
        """
        Get upcoming earnings dates for watchlist stocks.
        """
        earnings = []
        
        for symbol in self.stock_symbols:  # Skip crypto
            try:
                ticker = yf.Ticker(symbol)
                
                # Try to get earnings dates
                try:
                    cal = ticker.calendar
                    if cal is not None and not cal.empty:
                        if 'Earnings Date' in cal.index:
                            earnings_dates = cal.loc['Earnings Date']
                            if isinstance(earnings_dates, pd.Timestamp):
                                earnings_dates = [earnings_dates]
                            
                            for date in earnings_dates:
                                if isinstance(date, pd.Timestamp):
                                    if date.date() <= (datetime.now() + timedelta(days=days_ahead)).date():
                                        earnings.append({
                                            'symbol': symbol,
                                            'name': ticker.info.get('shortName', symbol),
                                            'date': date.strftime('%Y-%m-%d'),
                                            'time': 'TBD'  # Yahoo doesn't always provide timing
                                        })
                except:
                    pass
                
                # Also check earnings_dates attribute
                try:
                    ed = ticker.earnings_dates
                    if ed is not None and not ed.empty:
                        for date in ed.index[:2]:  # Next 2 dates
                            if date.date() <= (datetime.now() + timedelta(days=days_ahead)).date():
                                if date.date() >= datetime.now().date():
                                    earnings.append({
                                        'symbol': symbol,
                                        'name': ticker.info.get('shortName', symbol),
                                        'date': date.strftime('%Y-%m-%d'),
                                        'time': 'TBD'
                                    })
                except:
                    pass
                    
            except Exception as e:
                logger.warning(f"Error fetching earnings for {symbol}: {e}")
                continue
        
        # Remove duplicates and sort by date
        seen = set()
        unique_earnings = []
        for e in earnings:
            key = (e['symbol'], e['date'])
            if key not in seen:
                seen.add(key)
                unique_earnings.append(e)
        
        unique_earnings.sort(key=lambda x: x['date'])
        return unique_earnings
    
    def get_dividend_calendar(self, days_ahead: int = 30) -> List[dict]:
        """
        Get upcoming ex-dividend dates for watchlist stocks.
        """
        dividends = []
        
        for symbol in self.stock_symbols:
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
                    
                    if ex_date.date() >= datetime.now().date():
                        if ex_date.date() <= (datetime.now() + timedelta(days=days_ahead)).date():
                            dividends.append({
                                'symbol': symbol,
                                'name': info.get('shortName', symbol),
                                'ex_date': ex_date.strftime('%Y-%m-%d'),
                                'dividend_rate': info.get('dividendRate', 0),
                                'dividend_yield': info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 0
                            })
            except Exception as e:
                logger.warning(f"Error fetching dividend for {symbol}: {e}")
                continue
        
        dividends.sort(key=lambda x: x['ex_date'])
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
        Calculate weekly performance for all symbols.
        """
        results = {}
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        for symbol in self.symbols:
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
                    
                    results[symbol] = {
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
            except Exception as e:
                logger.warning(f"Error fetching weekly data for {symbol}: {e}")
                continue
        
        return results
    
    def get_market_indices(self) -> Dict[str, dict]:
        """
        Get major market index data for context.
        """
        indices = {
            '^GSPC': 'S&P 500',
            '^IXIC': 'NASDAQ',
            '^DJI': 'Dow Jones',
            '^VIX': 'VIX',
            '^RUT': 'Russell 2000',
        }
        
        results = {}
        for symbol, name in indices.items():
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
                
                results[symbol] = {
                    'symbol': symbol,
                    'name': name,
                    'price': current,
                    'change': change,
                    'change_percent': change_pct,
                    'pre_market_price': full_info.get('preMarketPrice'),
                    'pre_market_change': full_info.get('preMarketChangePercent'),
                }
            except Exception as e:
                logger.warning(f"Error fetching index {symbol}: {e}")
                continue
        
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
    """Fetches futures data for pre-market context."""
    
    FUTURES_SYMBOLS = {
        'ES=F': 'S&P 500 Futures',
        'NQ=F': 'NASDAQ Futures',
        'YM=F': 'Dow Futures',
        'RTY=F': 'Russell 2000 Futures',
    }
    
    def get_futures(self) -> Dict[str, dict]:
        """Get current futures data."""
        results = {}
        
        for symbol, name in self.FUTURES_SYMBOLS.items():
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
                
                results[symbol] = {
                    'symbol': symbol,
                    'name': name,
                    'price': current,
                    'change': change,
                    'change_percent': change_pct,
                }
            except Exception as e:
                logger.warning(f"Error fetching futures {symbol}: {e}")
                continue
        
        return results


if __name__ == "__main__":
    # Test the fetcher
    from notion_watchlist import get_watchlist

    logging.basicConfig(level=logging.INFO)

    all_symbols = get_watchlist()  # Fetch from Notion
    symbols = all_symbols[:5]  # Test with first 5
    print(f"Testing with {len(symbols)} symbols from Notion watchlist")
    fetcher = StockDataFetcher(symbols)
    
    print("Testing batch quotes...")
    quotes = fetcher.get_batch_quotes()
    for symbol, data in quotes.items():
        print(f"{symbol}: ${data['price']:.2f} ({data['change_percent']:+.2f}%)")
    
    print("\nTesting market indices...")
    indices = fetcher.get_market_indices()
    for symbol, data in indices.items():
        print(f"{data['name']}: {data['change_percent']:+.2f}%")
