"""
CoinGecko 24h disk-cache fallback tests.

Covers the stale-OK fallback path that keeps a ticker (e.g. TIG-USD) in
the premarket email even when CoinGecko free-tier 429s every retry. The
behaviour the tests pin down:

  - On a successful 24h fetch, the result is mirrored to the on-disk cache.
  - On a fully-failed fetch, the cache is consulted; entries within
    DISK_CACHE_STALE_OK_SECONDS are returned (tagged `_stale=True`).
  - Entries older than the stale-OK window are ignored.
  - When the disk cache is empty / unwritable, the failed fetch surfaces
    as None (preserving the existing degrade-gracefully behaviour).
"""

import json
import os
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest

from coingecko_fetcher import (
    CoinGeckoFetcher,
    DISK_CACHE_STALE_OK_SECONDS,
    RATE_LIMIT_MAX_RETRIES,
)


@pytest.fixture
def disk_cache_path(tmp_path):
    return str(tmp_path / "cache.json")


def _fetcher(disk_cache_path: str) -> CoinGeckoFetcher:
    f = CoinGeckoFetcher(
        overrides={"TIG": "the-innovation-game"},
        disk_cache_path=disk_cache_path,
    )
    # Side-step the live coin_list fetch — the override is enough.
    f._lookup_name = lambda coin_id: "The Innovation Game"
    return f


def _success_response(prices):
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = lambda: None
    resp.json.return_value = {"prices": prices}
    return resp


def _429_response():
    resp = MagicMock()
    resp.status_code = 429
    return resp


def test_successful_fetch_writes_disk_cache(disk_cache_path):
    """A live 24h fetch persists the result under symbol → {data, saved_at}."""
    fetcher = _fetcher(disk_cache_path)
    prices = [[1, 1.00], [2, 1.05], [3, 1.10]]

    with patch("coingecko_fetcher.requests.get", return_value=_success_response(prices)):
        result = fetcher.get_24h_range("TIG-USD")

    assert result is not None
    assert result["symbol"] == "TIG-USD"
    assert result["price"] == pytest.approx(1.10)
    assert "_stale" not in result

    # Disk file written, keyed by symbol.
    assert os.path.exists(disk_cache_path)
    with open(disk_cache_path) as f:
        cache = json.load(f)
    assert "TIG-USD" in cache
    assert cache["TIG-USD"]["data"]["price"] == pytest.approx(1.10)
    assert "saved_at" in cache["TIG-USD"]


def test_total_failure_falls_back_to_recent_disk_cache(disk_cache_path, caplog):
    """When live fetch 429s every retry, a fresh disk entry is returned."""
    # Pre-seed disk cache with a recent successful run.
    with open(disk_cache_path, "w") as f:
        json.dump(
            {
                "TIG-USD": {
                    "data": {
                        "symbol": "TIG-USD",
                        "name": "The Innovation Game",
                        "price": 1.04,
                        "change_percent": 3.5,
                        "low_24h": 0.96,
                        "high_24h": 1.13,
                        "coin_id": "the-innovation-game",
                        "_source": "coingecko",
                    },
                    "saved_at": datetime.now().isoformat(timespec="seconds"),
                }
            },
            f,
        )

    fetcher = _fetcher(disk_cache_path)

    # All RATE_LIMIT_MAX_RETRIES + 1 attempts return 429. Patch sleep to
    # avoid burning seconds in the test run.
    with patch("coingecko_fetcher.requests.get", return_value=_429_response()), \
         patch("coingecko_fetcher.time.sleep", lambda _s: None):
        result = fetcher.get_24h_range("TIG-USD")

    assert result is not None
    assert result["symbol"] == "TIG-USD"
    assert result["price"] == pytest.approx(1.04)
    assert result["_stale"] is True


def test_stale_entry_beyond_window_is_not_used(disk_cache_path):
    """Entries older than DISK_CACHE_STALE_OK_SECONDS are ignored."""
    too_old = datetime.now() - timedelta(seconds=DISK_CACHE_STALE_OK_SECONDS + 60)
    with open(disk_cache_path, "w") as f:
        json.dump(
            {
                "TIG-USD": {
                    "data": {
                        "symbol": "TIG-USD",
                        "name": "The Innovation Game",
                        "price": 0.50,
                        "change_percent": 0.0,
                        "low_24h": 0.5,
                        "high_24h": 0.5,
                        "coin_id": "the-innovation-game",
                        "_source": "coingecko",
                    },
                    "saved_at": too_old.isoformat(timespec="seconds"),
                }
            },
            f,
        )

    fetcher = _fetcher(disk_cache_path)
    with patch("coingecko_fetcher.requests.get", return_value=_429_response()), \
         patch("coingecko_fetcher.time.sleep", lambda _s: None):
        result = fetcher.get_24h_range("TIG-USD")

    assert result is None


def test_failure_with_empty_disk_cache_returns_none(disk_cache_path):
    """No disk cache + total failure preserves the original None contract."""
    fetcher = _fetcher(disk_cache_path)
    with patch("coingecko_fetcher.requests.get", return_value=_429_response()), \
         patch("coingecko_fetcher.time.sleep", lambda _s: None):
        result = fetcher.get_24h_range("TIG-USD")

    assert result is None
    # And no spurious file was created.
    assert not os.path.exists(disk_cache_path)


def test_disk_cache_disabled_with_empty_path(tmp_path):
    """Passing disk_cache_path='' disables the persistence layer."""
    fetcher = CoinGeckoFetcher(
        overrides={"TIG": "the-innovation-game"},
        disk_cache_path="",
    )
    fetcher._lookup_name = lambda coin_id: "The Innovation Game"
    prices = [[1, 1.00], [2, 1.10]]

    with patch("coingecko_fetcher.requests.get", return_value=_success_response(prices)):
        result = fetcher.get_24h_range("TIG-USD")

    assert result is not None
    # No file created anywhere under tmp_path because we disabled persistence.
    leftover = list(tmp_path.iterdir())
    assert leftover == []
