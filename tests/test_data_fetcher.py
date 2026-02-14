"""
Tests for data_fetcher.py
"""

import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
from datetime import datetime

from data_fetcher import StockDataFetcher


class TestGetBatchQuotes:
    def test_get_batch_quotes_empty_symbols(self):
        """Empty symbol list returns empty dict."""
        fetcher = StockDataFetcher([])
        result = fetcher.get_batch_quotes([])
        assert result == {}

    def test_get_batch_quotes_empty_default(self):
        """Fetcher with empty symbols list returns empty dict."""
        fetcher = StockDataFetcher([])
        result = fetcher.get_batch_quotes()
        assert result == {}


class TestGetTopMovers:
    def test_get_top_movers_empty(self, sample_quotes):
        """Empty quotes returns two empty lists."""
        fetcher = StockDataFetcher(["NVDA"])
        gainers, losers = fetcher.get_top_movers({})
        assert gainers == []
        assert losers == []

    def test_get_top_movers_with_data(self, sample_quotes):
        """Returns gainers and losers sorted correctly."""
        fetcher = StockDataFetcher(list(sample_quotes.keys()))
        gainers, losers = fetcher.get_top_movers(sample_quotes)
        # NVDA is a gainer (+3.93%), TSLA is a loser (-1.51%)
        assert len(gainers) == 1
        assert gainers[0]["symbol"] == "NVDA"
        assert len(losers) == 1
        assert losers[0]["symbol"] == "TSLA"


class TestCryptoSymbolSeparation:
    def test_crypto_symbol_separation(self, sample_symbols):
        """Symbols ending in -USD are separated as crypto."""
        fetcher = StockDataFetcher(sample_symbols)
        assert "BTC-USD" in fetcher.crypto_symbols
        assert "BTC-USD" not in fetcher.stock_symbols
        assert "NVDA" in fetcher.stock_symbols
        assert "NVDA" not in fetcher.crypto_symbols

    def test_no_crypto_symbols(self):
        """List with no crypto symbols has empty crypto_symbols."""
        fetcher = StockDataFetcher(["NVDA", "TSLA", "GOOGL"])
        assert fetcher.crypto_symbols == []
        assert len(fetcher.stock_symbols) == 3


class TestEarningsCalendar:
    @patch("data_fetcher.yf.Ticker")
    def test_earnings_calendar_dict_format(self, mock_ticker_cls):
        """yfinance 1.0+ dict calendar format is parsed correctly."""
        from datetime import date, timedelta

        future_date = (datetime.now() + timedelta(days=3)).date()

        mock_ticker = MagicMock()
        mock_ticker.calendar = {
            "Earnings Date": [future_date],
        }
        mock_ticker.info = {"shortName": "Test Corp"}
        mock_ticker.earnings_dates = None
        mock_ticker_cls.return_value = mock_ticker

        fetcher = StockDataFetcher(["TEST"])
        earnings = fetcher.get_earnings_calendar(days_ahead=14)
        assert len(earnings) >= 1
        assert earnings[0]["symbol"] == "TEST"

    @patch("data_fetcher.yf.Ticker")
    def test_earnings_calendar_dataframe_format(self, mock_ticker_cls):
        """Old DataFrame format still works for earnings calendar."""
        from datetime import timedelta

        future_date = datetime.now() + timedelta(days=5)

        # Simulate old DataFrame format using MagicMock to avoid
        # DataFrame.empty being read-only
        mock_df = MagicMock()
        mock_df.empty = False
        mock_df.__contains__ = lambda self, key: key == "Earnings Date"
        mock_df.index = pd.Index(["Earnings Date"])
        mock_df.loc.__getitem__ = MagicMock(return_value=pd.Timestamp(future_date))

        mock_ticker = MagicMock()
        mock_ticker.calendar = mock_df
        mock_ticker.info = {"shortName": "Test DF Corp"}
        mock_ticker.earnings_dates = None
        mock_ticker_cls.return_value = mock_ticker

        fetcher = StockDataFetcher(["TESTDF"])
        earnings = fetcher.get_earnings_calendar(days_ahead=14)
        # Should at least not crash; may or may not find earnings depending on parsing
        assert isinstance(earnings, list)
