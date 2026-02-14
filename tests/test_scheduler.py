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
