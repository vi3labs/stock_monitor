"""
Tests for scheduler.py

The is_market_day() function imports exchange_calendars inside a try/except,
falling back to a basic weekday check. We test both paths by patching the
import mechanism.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
import pytz
from freezegun import freeze_time


class TestIsMarketDay:
    @freeze_time("2026-02-14 10:00:00", tz_offset=-5)
    def test_is_market_day_weekend(self):
        """Saturday returns False."""
        # Patch exchange_calendars import to raise ImportError -> weekday check
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "exchange_calendars":
                raise ImportError("mocked")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            from scheduler import is_market_day
            result = is_market_day()
            assert result is False

    @freeze_time("2026-02-17 10:00:00", tz_offset=-5)
    def test_is_market_day_weekday(self):
        """Normal Tuesday returns True."""
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "exchange_calendars":
                raise ImportError("mocked")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            from scheduler import is_market_day
            result = is_market_day()
            assert result is True

    @freeze_time("2025-12-25 10:00:00", tz_offset=-5)
    def test_is_market_day_holiday(self):
        """Known holiday returns False when exchange_calendars available."""
        mock_calendar = MagicMock()
        mock_calendar.is_session.return_value = False

        mock_xcals_module = MagicMock()
        mock_xcals_module.get_calendar.return_value = mock_calendar

        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "exchange_calendars":
                return mock_xcals_module
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            from scheduler import is_market_day
            result = is_market_day()
            assert result is False


class TestDryRunFlagPropagation:
    """Verify --dry-run flows through scheduler dispatchers to each report's main()."""

    def test_run_premarket_passes_dry_run(self):
        with patch("premarket_report.main") as mock_main:
            from scheduler import run_premarket
            run_premarket(dry_run=True)
            mock_main.assert_called_once_with(dry_run=True)

    def test_run_postmarket_passes_dry_run(self):
        with patch("postmarket_report.main") as mock_main:
            from scheduler import run_postmarket
            run_postmarket(dry_run=True)
            mock_main.assert_called_once_with(dry_run=True)

    def test_run_weekly_passes_dry_run(self):
        with patch("weekly_report.main") as mock_main:
            from scheduler import run_weekly
            run_weekly(dry_run=True)
            mock_main.assert_called_once_with(dry_run=True)

    def test_dry_run_default_false(self):
        """Calling dispatchers without dry_run defaults to False (production behavior)."""
        with patch("premarket_report.main") as mock_main:
            from scheduler import run_premarket
            run_premarket()
            mock_main.assert_called_once_with(dry_run=False)
