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

import json
import logging
import os
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://api.coingecko.com/api/v3"
COIN_LIST_TTL_HOURS = 24
DEFAULT_TIMEOUT = 10

# Free-tier CoinGecko allows ~5-15 req/min depending on time of day. Pace
# crypto-batch loops so we don't burn through that budget on the watchlist.
INTER_REQUEST_SLEEP = 1.5            # seconds between successive market_chart calls
RATE_LIMIT_MAX_RETRIES = 3           # total attempts on 429 = 1 + retries
RATE_LIMIT_BACKOFF = (5, 12, 25)     # seconds between retries (additive, not exponential —
                                      # CoinGecko's 429 window is ~30s on free tier; the
                                      # third attempt at +25s should land in a fresh window
                                      # even when the prior pair both 429'd)

# Persistent cache for `get_24h_range` results. When a live fetch fails after
# all retries (e.g. an extra-stubborn 429 burst), the renderer falls back to
# the most recent cached value within DISK_CACHE_STALE_OK_SECONDS. Better to
# show yesterday's range with a slightly off price than to silently drop the
# ticker from the email — Tom flagged TIG-USD missing exactly this way on
# 2026-04-30 when CoinGecko 429'd the-innovation-game three times in a row.
DEFAULT_DISK_CACHE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "data",
    "coingecko_24h_cache.json",
)
DISK_CACHE_STALE_OK_SECONDS = 25 * 60 * 60  # 25h — survives a full day-skip


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
        disk_cache_path: Optional[str] = None,
    ):
        self._overrides = {k.upper(): v for k, v in (overrides or {}).items()}
        self.cache_duration = cache_duration_minutes

        self._cache: Dict[str, dict] = {}
        self._cache_time: Dict[str, datetime] = {}
        self._cache_lock = threading.Lock()

        self._coin_list: Optional[List[dict]] = None
        self._coin_list_time: Optional[datetime] = None
        self._coin_list_lock = threading.Lock()

        # Disk cache for stale-OK 24h fallback. Pass `disk_cache_path=""` to
        # disable (useful in tests). None falls back to the module default.
        if disk_cache_path is None:
            self._disk_cache_path: Optional[str] = DEFAULT_DISK_CACHE_PATH
        else:
            self._disk_cache_path = disk_cache_path or None
        self._disk_cache_lock = threading.Lock()

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

    # ── Disk cache (stale-OK fallback for 24h range fetches) ──

    def _read_disk_cache(self) -> Dict[str, dict]:
        """Load the on-disk cache map. Returns {} on any error so callers
        can treat the disk cache as best-effort."""
        if not self._disk_cache_path:
            return {}
        with self._disk_cache_lock:
            try:
                with open(self._disk_cache_path, "r") as f:
                    raw = json.load(f)
                if isinstance(raw, dict):
                    return raw
                return {}
            except (FileNotFoundError, ValueError, OSError):
                return {}

    def _write_disk_cache_entry(self, symbol: str, data: dict) -> None:
        """Merge a single symbol's 24h range into the on-disk cache. Best-effort
        — disk write failures are logged at debug and never raised, since the
        in-memory caller already has the fresh value."""
        if not self._disk_cache_path:
            return
        with self._disk_cache_lock:
            try:
                existing: Dict[str, dict] = {}
                try:
                    with open(self._disk_cache_path, "r") as f:
                        loaded = json.load(f)
                    if isinstance(loaded, dict):
                        existing = loaded
                except (FileNotFoundError, ValueError, OSError):
                    existing = {}

                existing[symbol] = {
                    "data": data,
                    "saved_at": datetime.now().isoformat(timespec="seconds"),
                }

                os.makedirs(os.path.dirname(self._disk_cache_path), exist_ok=True)
                tmp_path = f"{self._disk_cache_path}.tmp"
                with open(tmp_path, "w") as f:
                    json.dump(existing, f)
                os.replace(tmp_path, self._disk_cache_path)
            except OSError as e:
                logger.debug(f"CoinGecko disk-cache write failed for {symbol}: {e}")

    def _read_disk_cache_entry(self, symbol: str) -> Optional[dict]:
        """Return the cached `data` dict for `symbol` if it exists and is
        younger than DISK_CACHE_STALE_OK_SECONDS, else None."""
        cache = self._read_disk_cache()
        entry = cache.get(symbol)
        if not entry or not isinstance(entry, dict):
            return None
        saved_at = entry.get("saved_at")
        data = entry.get("data")
        if not saved_at or not isinstance(data, dict):
            return None
        try:
            age = (datetime.now() - datetime.fromisoformat(saved_at)).total_seconds()
        except ValueError:
            return None
        if age > DISK_CACHE_STALE_OK_SECONDS:
            return None
        return data

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

    def get_24h_range(self, symbol: str) -> Optional[dict]:
        """
        Fetch 24-hour price range (low/high) plus current price and 24h change.

        Uses `/coins/{id}/market_chart?days=1` which returns ~5-minute granularity
        on the free tier. Picks min/max from that series to get a true 24h range
        (the `simple/price` endpoint doesn't expose low/high — only current).

        Returns dict with: symbol, name, price, change_percent, low_24h, high_24h,
        coin_id, _source. None if the symbol can't be resolved or the call fails.
        """
        cache_key = f"range24h_{symbol}"
        if self._is_cache_valid(cache_key):
            return self._get_cache(cache_key)

        coin_id = self.resolve_coin_id(symbol)
        if not coin_id:
            logger.debug(f"CoinGecko could not resolve {symbol} for 24h range")
            return None

        # Retry on 429 (rate limit) — free tier randomly drops 1-of-N requests
        # per ~30-second window. 1 base attempt + RATE_LIMIT_MAX_RETRIES retries.
        params = {"vs_currency": "usd", "days": 1}
        payload: Optional[dict] = None
        last_exc = None
        for attempt in range(RATE_LIMIT_MAX_RETRIES + 1):
            try:
                resp = requests.get(
                    f"{BASE_URL}/coins/{coin_id}/market_chart",
                    params=params,
                    timeout=DEFAULT_TIMEOUT,
                )
                if resp.status_code == 429 and attempt < RATE_LIMIT_MAX_RETRIES:
                    backoff = RATE_LIMIT_BACKOFF[min(attempt, len(RATE_LIMIT_BACKOFF) - 1)]
                    logger.info(
                        f"CoinGecko 429 for {coin_id} (attempt {attempt + 1}); "
                        f"backing off {backoff}s"
                    )
                    time.sleep(backoff)
                    continue
                resp.raise_for_status()
                payload = resp.json()
                break
            except requests.HTTPError as e:
                # Non-429 HTTP error: don't retry, surface and bail
                logger.warning(f"CoinGecko 24h range fetch failed for {symbol} ({coin_id}): {e}")
                return self._stale_24h_fallback(symbol, coin_id, reason=str(e))
            except Exception as e:
                last_exc = e
                if attempt >= RATE_LIMIT_MAX_RETRIES:
                    logger.warning(
                        f"CoinGecko 24h range fetch failed for {symbol} ({coin_id}) "
                        f"after {attempt + 1} attempts: {e}"
                    )
                    return self._stale_24h_fallback(symbol, coin_id, reason=str(e))
                # Network blip — retry without backoff
                logger.debug(f"CoinGecko 24h range transient error for {coin_id} attempt {attempt + 1}: {e}")

        if payload is None:
            # Loop exhausted without a successful response (all 429s).
            logger.warning(
                f"CoinGecko 24h range fetch gave up on {symbol} ({coin_id}) "
                f"after {RATE_LIMIT_MAX_RETRIES + 1} attempts: {last_exc}"
            )
            return self._stale_24h_fallback(symbol, coin_id, reason="all attempts 429")

        prices = payload.get("prices", [])  # [[ms_ts, price], ...]
        if len(prices) < 2:
            logger.warning(f"CoinGecko 24h range for {coin_id} returned <2 points")
            return self._stale_24h_fallback(symbol, coin_id, reason="empty payload")

        closes = [p[1] for p in prices if p and len(p) >= 2 and p[1] is not None]
        if not closes:
            return self._stale_24h_fallback(symbol, coin_id, reason="no closes")

        current = closes[-1]
        start = closes[0]
        low_24h = min(closes)
        high_24h = max(closes)
        change_pct = ((current - start) / start * 100) if start else 0

        result = {
            "symbol": symbol,
            "name": self._lookup_name(coin_id) or symbol,
            "price": current,
            "change_percent": change_pct,
            "low_24h": low_24h,
            "high_24h": high_24h,
            "coin_id": coin_id,
            "_source": "coingecko",
        }
        self._set_cache(cache_key, result)
        # Persist for the stale-OK fallback so tomorrow's 429 burst doesn't
        # drop this ticker from the email.
        self._write_disk_cache_entry(symbol, result)
        return result

    def _stale_24h_fallback(
        self, symbol: str, coin_id: str, *, reason: str
    ) -> Optional[dict]:
        """Return the most recent on-disk 24h range entry for `symbol` if
        it's within DISK_CACHE_STALE_OK_SECONDS, otherwise None. Tags the
        result with `_stale=True` so callers / templates can flag it if
        they care; existing renderers ignore the field, which is fine — a
        stale row beats a missing row."""
        cached = self._read_disk_cache_entry(symbol)
        if not cached:
            return None
        logger.warning(
            f"CoinGecko 24h range using stale disk cache for {symbol} "
            f"({coin_id}); reason: {reason}"
        )
        return {**cached, "_stale": True}

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
        range_24h = fetcher.get_24h_range(sym)
        print(f"\n=== {sym} ===")
        if quote:
            print(f"  price:  ${quote['price']:.4f}")
            print(f"  24h:    {quote['change_percent']:+.2f}%")
            print(f"  name:   {quote['name']}")
        else:
            print("  quote:  (no data)")
        if range_24h:
            print(f"  range:  ${range_24h['low_24h']:.4f} - ${range_24h['high_24h']:.4f}")
        else:
            print("  range:  (no data)")
        if weekly:
            print(f"  week:   {weekly['week_change_percent']:+.2f}% over {len(weekly['daily_closes'])} days")
        else:
            print("  weekly: (no data)")
