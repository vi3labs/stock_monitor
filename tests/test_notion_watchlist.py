"""
Tests for notion_watchlist.py
"""

import pytest
from unittest.mock import patch, MagicMock
import os
import json
import tempfile

import notion_watchlist


class TestGetWatchlist:
    @patch("notion_watchlist._request_with_retry")
    def test_get_watchlist_success(self, mock_request, mock_notion_response):
        """Successful Notion API call returns tickers."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = mock_notion_response
        mock_request.return_value = mock_resp

        # Ensure token is set for this test
        with patch.object(notion_watchlist, "NOTION_TOKEN", "fake_token"):
            tickers = notion_watchlist.get_watchlist()

        assert "NVDA" in tickers
        assert "TSLA" in tickers
        assert "GOOGL" in tickers
        assert len(tickers) == 3

    @patch("notion_watchlist._request_with_retry")
    @patch("notion_watchlist._get_fallback_watchlist")
    def test_get_watchlist_401_fallback(self, mock_fallback, mock_request):
        """401 response triggers config fallback."""
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized"
        mock_request.return_value = mock_resp
        mock_fallback.return_value = ["AAPL", "MSFT"]

        with patch.object(notion_watchlist, "NOTION_TOKEN", "expired_token"):
            tickers = notion_watchlist.get_watchlist()

        assert tickers == ["AAPL", "MSFT"]
        mock_fallback.assert_called_once()

    @patch("notion_watchlist._get_fallback_watchlist")
    def test_get_watchlist_no_token(self, mock_fallback):
        """No token falls back to config without making API call."""
        mock_fallback.return_value = ["META", "AMZN"]

        with patch.object(notion_watchlist, "NOTION_TOKEN", None):
            tickers = notion_watchlist.get_watchlist()

        assert tickers == ["META", "AMZN"]
        mock_fallback.assert_called_once()


class TestLoadConfigWatchlist:
    def test_load_config_watchlist(self, sample_config, tmp_path):
        """Reads tickers from config.yaml watchlist section."""
        config_file = tmp_path / "config.yaml"
        import yaml

        config_file.write_text(yaml.dump(sample_config))

        with patch.object(notion_watchlist, "_SCRIPT_DIR", str(tmp_path)):
            tickers = notion_watchlist._load_config_watchlist()

        assert "NVDA" in tickers
        assert "TSLA" in tickers
        assert len(tickers) == 5
