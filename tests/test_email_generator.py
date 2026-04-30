"""
Tests for email_generator.py
"""

import pytest
from email_generator import EmailGenerator, JinjaEmailGenerator


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


class TestCryptoSection:
    def _crypto_payload(self):
        return {
            "BTC-USD": {
                "symbol": "BTC-USD",
                "name": "Bitcoin",
                "price": 95000.0,
                "low_24h": 92000.0,
                "high_24h": 96500.0,
                "change_percent": 2.34,
            },
            "ETH-USD": {
                "symbol": "ETH-USD",
                "name": "Ethereum",
                "price": 3200.0,
                "low_24h": 3100.0,
                "high_24h": 3300.0,
                "change_percent": -1.12,
            },
        }

    def test_legacy_generator_renders_crypto_section(self):
        """Legacy EmailGenerator includes crypto rows when crypto_data is provided."""
        gen = EmailGenerator()
        html = gen.generate_premarket_report(
            futures={}, premarket_data={}, quotes={}, earnings=[], dividends=[],
            news={}, market_news=[], crypto_data=self._crypto_payload(),
        )
        assert "Crypto (24h)" in html
        assert "BTC-USD" in html and "ETH-USD" in html
        assert "$92,000.00" in html or "$92000.00" in html  # range low
        assert "+2.34%" in html
        assert "-1.12%" in html
        assert "% of range" in html

    def test_jinja_generator_renders_crypto_section(self):
        """Jinja template renders the Crypto section end-to-end."""
        gen = JinjaEmailGenerator()
        html = gen.generate_premarket_report(
            futures={}, premarket_data={}, quotes={}, earnings=[], dividends=[],
            news={}, market_news=[], crypto_data=self._crypto_payload(),
        )
        assert "<!DOCTYPE html>" in html
        assert "Crypto (24h)" in html
        assert "BTC-USD" in html and "ETH-USD" in html
        assert "of range" in html

    def test_crypto_section_empty_is_omitted(self):
        """Empty crypto_data does not produce a Crypto section."""
        gen = JinjaEmailGenerator()
        html = gen.generate_premarket_report(
            futures={}, premarket_data={}, quotes={}, earnings=[], dividends=[],
            news={}, market_news=[], crypto_data={},
        )
        assert "Crypto (24h)" not in html

    def test_crypto_row_handles_flat_range(self):
        """When low_24h == high_24h, position bar centers at 50% (no division by zero)."""
        gen = EmailGenerator()
        html = gen._crypto_row("FLAT-USD", "Flat Coin", 1.0, 1.0, 1.0, 0.0)
        assert "50% of range" in html


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
