"""
Tests for email_sender.py
"""

import pytest
from unittest.mock import patch
import os

from email_sender import EmailSender, EmailSenderFactory


class TestEmailSenderNoCredentials:
    def test_email_sender_no_credentials(self):
        """Returns False and doesn't crash when no credentials set."""
        with patch.dict(os.environ, {}, clear=True):
            sender = EmailSender(
                sender_email=None,
                sender_password=None,
            )
            result = sender.send_email(
                recipient="test@example.com",
                subject="Test",
                html_content="<p>Hello</p>",
            )
            assert result is False

    def test_email_sender_no_email_only(self):
        """Missing email address returns False."""
        with patch.dict(os.environ, {}, clear=True):
            sender = EmailSender(
                sender_email=None,
                sender_password="some_password",
            )
            result = sender.send_email(
                recipient="test@example.com",
                subject="Test",
                html_content="<p>Hello</p>",
            )
            assert result is False

    def test_email_sender_test_connection_no_creds(self):
        """test_connection returns False without credentials."""
        with patch.dict(os.environ, {}, clear=True):
            sender = EmailSender(sender_email=None, sender_password=None)
            assert sender.test_connection() is False


class TestEmailSenderEnvFallback:
    def test_email_sender_env_fallback(self):
        """Picks up env vars when config values are empty."""
        with patch.dict(os.environ, {
            "STOCK_MONITOR_EMAIL": "env@example.com",
            "STOCK_MONITOR_EMAIL_PASSWORD": "env_password",
        }):
            sender = EmailSender(sender_email=None, sender_password=None)
            assert sender.sender_email == "env@example.com"
            assert sender.sender_password == "env_password"

    def test_email_sender_password_alt_env(self):
        """Falls back to STOCK_MONITOR_PASSWORD env var."""
        with patch.dict(os.environ, {
            "STOCK_MONITOR_EMAIL": "env@example.com",
            "STOCK_MONITOR_PASSWORD": "alt_password",
        }, clear=False):
            # Clear the primary password var
            env_copy = os.environ.copy()
            env_copy.pop("STOCK_MONITOR_EMAIL_PASSWORD", None)
            with patch.dict(os.environ, env_copy, clear=True):
                sender = EmailSender(sender_email=None, sender_password=None)
                assert sender.sender_password == "alt_password"


class TestEmailSenderFactory:
    def test_from_config(self, sample_config):
        """Factory creates sender from config dict."""
        sender = EmailSenderFactory.from_config(sample_config)
        assert sender.sender_email == "test@example.com"
        assert sender.sender_password == "fake_password"
        assert sender.smtp_port == 587
