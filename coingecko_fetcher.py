"""
CoinGecko Fetcher Module
========================
Fallback price source for crypto tickers that yfinance does not list
(small-cap tokens, DEX-only assets, etc.).

Convention: Watchlist crypto symbols use Yahoo's `<SYM>-USD` format
(e.g. `BTC-USD`, `TIG-USD`). Yahoo handles majors; CoinGecko picks up
the rest. The `crypto_overrides` map in `config.yaml` resolves
ambiguous tickers to a specific CoinGecko coin_id.
"""

import logging
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.coingecko.com/api/v3"
COIN_LIST_TTL_HOURS = 24
DEFAULT_TIMEOUT = 10


class CoinGeckoFetcher:
    """
    Resolves ticker symbols to CoinGecko coin IDs and fetches price data.

    Returns dicts shaped to match `StockDataFetcher.get_batch_quotes()` and
    `get_weekly_performance()` so callers can merge results without branching.
    """

    def __init__(
        self,
        overrides: Optional[Dict[str, str]] = None,
        cache_duration_minutes: int = 5,
    ):
        self._overrides = {k.upper(): v for k, v in (overrides or {}).items()}
        self.cache_duration = cache_duration_minutes

        self._cache: Dict[str, dict] = {}
        self._cache_time: Dict[str, datetime] = {}
        self._cache_lock = threading.Lock()

        self._coin_list: Optional[List[dict]] = None
        self._coin_list_time: Optional[datetime] = None
        self._coin_list_lock = threading.Lock()

    def _is_cache_valid(self, key: str) -> bool:
        with self._cache_lock:
            if key not in self._cache_time:
                return False
            elapsed = (datetime.now() - self._cache_time[key]).total_seconds() / 60
            return elapsed < self.cache_duration

    def _set_cache(self, key: str, value: dict) -> None:
        with self._cache_lock:
            self._cache[key] = value
            self._cache_time[key] = datetime.now()

    def _get_cache(self, key: str) -> Optional[dict]:
        with self._cache_lock:
            return self._cache.get(key)

    def _get_coin_list(self) -> List[dict]:
        """Fetch and cache CoinGecko's full coin list (id/symbol/name)."""
        with self._coin_list_lock:
            if self._coin_list is not None and self._coin_list_time is not None:
                age_h = (datetime.now() - self._coin_list_time).total_seconds() / 3600
                if age_h < COIN_LIST_TTL_HOURS:
                    return self._coin_list

            try:
                resp = requests.get(f"{BASE_URL}/coins/list", timeout=DEFAULT_TIMEOUT)
                resp.raise_for_status()
                self._coin_list = resp.json()
                self._coin_list_time = datetime.now()
                logger.info(f"Loaded CoinGecko coin list ({len(self._coin_list)} coins)")
                return self._coin_list
            except Exception as e:
                logger.warning(f"Failed to load CoinGecko coin list: {e}")
                return self._coin_list or []

    def resolve_coin_id(self, symbol: str) -> Optional[str]:
        """
        Map a watchlist symbol to a CoinGecko coin_id.

        Strips a `-USD` suffix, then checks overrides, then falls back to
        symbol-match on the public coin list. Multiple matches log a warning
        and return the first — pin via `crypto_overrides` in config.yaml.
        """
        sym = symbol.upper().replace("-USD", "")

        if sym in self._overrides:
            return self._overrides[sym]

        coin_list = self._get_coin_list()
        if not coin_list:
            return None

        matches = [c for c in coin_list if c.get("symbol", "").upper() == sym]
        if not matches:
            return None
        if len(matches) > 1:
            logger.warning(
                f"Multiple CoinGecko matches for {sym}: "
                f"{[m['id'] for m in matches[:5]]}. Using first — "
                f"add to crypto_overrides in config.yaml to pin."
            )
        return matches[0]["id"]

    def get_quote(self, symbol: str) -> Optional[dict]:
        """
        Fetch a single quote in StockDataFetcher.get_batch_quotes() shape.

        Returns None if the symbol can't be resolved or the API call fails.
        """
        cache_key = f"quote_{symbol}"
        if self._is_cache_valid(cache_key):
            return self._get_cache(cache_key)

        coin_id = self.resolve_coin_id(symbol)
        if not coin_id:
            logger.debug(f"CoinGecko could not resolve {symbol}")
            return None

        try:
            params = {
                "ids": coin_id,
                "vs_currencies": "usd",
                "include_24hr_change": "true",
                "include_24hr_vol": "true",
                "include_market_cap": "true",
            }
            resp = requests.get(
                f"{BASE_URL}/simple/price", params=params, timeout=DEFAULT_TIMEOUT
            )
            resp.raise_for_status()
            data = resp.json().get(coin_id)
            if not data:
                logger.warning(f"CoinGecko returned no data for {coin_id}")
                return None

            price = data.get("usd", 0) or 0
            change_pct = data.get("usd_24h_change", 0) or 0
            volume = data.get("usd_24h_vol", 0) or 0
            market_cap = data.get("usd_market_cap", 0) or 0

            # Derive previous close from 24h % change so downstream math works.
            if change_pct != 0:
                previous_close = price / (1 + change_pct / 100)
            else:
                previous_close = price
            change = price - previous_close

            name = self._lookup_name(coin_id) or symbol

            quote = {
                "symbol": symbol,
                "name": name,
                "price": price,
                "previous_close": previous_close,
                "open": previous_close,
                "day_high": price,
                "day_low": price,
                "volume": volume,
                "avg_volume": volume,
                "market_cap": market_cap,
                "fifty_two_week_high": 0,
                "fifty_two_week_low": 0,
                "pre_market_price": None,
                "pre_market_change": None,
                "post_market_price": None,
                "post_market_change": None,
                "currency": "USD",
                "change": change,
                "change_percent": change_pct,
                "volume_ratio": 1.0,
                "_source": "coingecko",
            }
            self._set_cache(cache_key, quote)
            return quote
        except Exception as e:
            logger.warning(f"CoinGecko quote fetch failed for {symbol} ({coin_id}): {e}")
            return None

    def get_weekly(self, symbol: str) -> Optional[dict]:
        """
        Fetch 7-day price history in get_weekly_performance() shape.
        """
        cache_key = f"weekly_{symbol}"
        if self._is_cache_valid(cache_key):
            return self._get_cache(cache_key)

        coin_id = self.resolve_coin_id(symbol)
        if not coin_id:
            return None

        try:
            params = {"vs_currency": "usd", "days": 7, "interval": "daily"}
            resp = requests.get(
                f"{BASE_URL}/coins/{coin_id}/market_chart",
                params=params,
                timeout=DEFAULT_TIMEOUT,
            )
            resp.raise_for_status()
            payload = resp.json()
            prices = payload.get("prices", [])  # [[ms_ts, price], ...]
            volumes = payload.get("total_volumes", [])

            if len(prices) < 2:
                return None

            closes = [p[1] for p in prices]
            volume_total = sum(v[1] for v in volumes) if volumes else 0
            start_price = closes[0]
            end_price = closes[-1]
            change = end_price - start_price
            change_pct = (change / start_price * 100) if start_price else 0

            daily_changes = []
            for i in range(1, len(closes)):
                prev = closes[i - 1]
                if prev:
                    daily_changes.append((closes[i] - prev) / prev)

            weekly = {
                "symbol": symbol,
                "start_price": start_price,
                "end_price": end_price,
                "week_change": change,
                "week_change_percent": change_pct,
                "daily_closes": closes,
                "daily_changes": daily_changes,
                "high": max(closes),
                "low": min(closes),
                "total_volume": volume_total,
                "_source": "coingecko",
            }
            self._set_cache(cache_key, weekly)
            return weekly
        except Exception as e:
            logger.warning(f"CoinGecko weekly fetch failed for {symbol} ({coin_id}): {e}")
            return None

    def _lookup_name(self, coin_id: str) -> Optional[str]:
        for c in self._get_coin_list() or []:
            if c.get("id") == coin_id:
                return c.get("name")
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    fetcher = CoinGeckoFetcher(overrides={"TIG": "the-innovation-game"})

    for sym in ("TIG-USD", "BTC-USD"):
        quote = fetcher.get_quote(sym)
        weekly = fetcher.get_weekly(sym)
        print(f"\n=== {sym} ===")
        if quote:
            print(f"  price:  ${quote['price']:.4f}")
            print(f"  24h:    {quote['change_percent']:+.2f}%")
            print(f"  name:   {quote['name']}")
        else:
            print("  quote:  (no data)")
        if weekly:
            print(f"  week:   {weekly['week_change_percent']:+.2f}% over {len(weekly['daily_closes'])} days")
        else:
            print("  weekly: (no data)")
