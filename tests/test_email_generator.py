"""
Tests for email_generator.py
"""

import pytest
from email_generator import EmailGenerator


class TestGeneratePremarketEmpty:
    def test_generate_premarket_empty_data(self):
        """All empty inputs produces valid HTML (no crash)."""
        gen = EmailGenerator()
        html = gen.generate_premarket_report(
            futures={},
            premarket_data={},
            quotes={},
            earnings=[],
            dividends=[],
            news={},
            market_news=[],
        )
        assert "<!DOCTYPE html>" in html
        assert "Pre-Market Briefing" in html
        assert "</html>" in html


class TestGeneratePostmarketEmpty:
    def test_generate_postmarket_empty_data(self):
        """All empty inputs produces valid HTML (no crash)."""
        gen = EmailGenerator()
        html = gen.generate_postmarket_report(
            indices={},
            quotes={},
            postmarket_data={},
            news={},
        )
        assert "<!DOCTYPE html>" in html
        assert "Market Close Report" in html
        assert "</html>" in html


class TestFormatChangeEdgeCases:
    def test_format_change_zero(self):
        """Zero change returns neutral formatting."""
        gen = EmailGenerator()
        text, color = gen._format_change(0.0)
        assert text == "0.00%"
        assert color == gen.COLORS["neutral"]

    def test_format_change_positive(self):
        """Positive change returns green with plus sign."""
        gen = EmailGenerator()
        text, color = gen._format_change(5.25)
        assert text == "+5.25%"
        assert color == gen.COLORS["green"]

    def test_format_change_negative(self):
        """Negative change returns red."""
        gen = EmailGenerator()
        text, color = gen._format_change(-3.14)
        assert text == "-3.14%"
        assert color == gen.COLORS["red"]

    def test_format_change_very_small(self):
        """Very small positive change still shows plus sign."""
        gen = EmailGenerator()
        text, color = gen._format_change(0.01)
        assert text.startswith("+")
        assert color == gen.COLORS["green"]


class TestTruncation:
    def test_name_truncation(self):
        """Long stock names are truncated at MAX_NAME_LENGTH."""
        gen = EmailGenerator()
        long_name = "A" * 50
        html = gen._stock_row("TEST", long_name, 100.0, 1.5)
        truncated = "A" * gen.MAX_NAME_LENGTH + "..."
        assert truncated in html

    def test_title_truncation(self):
        """Long news titles are truncated at MAX_TITLE_LENGTH."""
        gen = EmailGenerator()
        long_title = "B" * 100
        html = gen._news_item("TEST", long_title, "Source", "http://example.com")
        truncated = "B" * gen.MAX_TITLE_LENGTH + "..."
        assert truncated in html
