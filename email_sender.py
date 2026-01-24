"""
Email Sender Module
===================
Sends HTML emails via SMTP (Gmail).
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional, List
import logging
import os

logger = logging.getLogger(__name__)


class EmailSender:
    """Sends emails via SMTP."""
    
    def __init__(self, 
                 smtp_server: str = "smtp.gmail.com",
                 smtp_port: int = 587,
                 sender_email: str = None,
                 sender_password: str = None):
        """
        Initialize email sender.
        
        For Gmail, you need to:
        1. Enable 2-Factor Authentication on your Google account
        2. Generate an App Password: https://myaccount.google.com/apppasswords
        3. Use the App Password here (not your regular password)
        """
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = sender_email or os.environ.get('STOCK_MONITOR_EMAIL')
        self.sender_password = sender_password or os.environ.get('STOCK_MONITOR_PASSWORD')
        
        if not self.sender_email or not self.sender_password:
            logger.warning("Email credentials not configured. Set in config.yaml or environment variables.")
    
    def send_email(self,
                   recipient: str,
                   subject: str,
                   html_content: str,
                   attachments: List[str] = None) -> bool:
        """
        Send an HTML email.
        
        Args:
            recipient: Email address to send to
            subject: Email subject line
            html_content: HTML content of the email
            attachments: Optional list of file paths to attach
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.sender_email or not self.sender_password:
            logger.error("Email credentials not configured")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.sender_email
            msg['To'] = recipient
            
            # Create plain text version (fallback)
            text_content = "This email requires HTML support to view properly."
            part1 = MIMEText(text_content, 'plain')
            
            # Create HTML version
            part2 = MIMEText(html_content, 'html')
            
            # Attach parts (plain text first, then HTML)
            msg.attach(part1)
            msg.attach(part2)
            
            # Handle attachments
            if attachments:
                for filepath in attachments:
                    if os.path.exists(filepath):
                        with open(filepath, 'rb') as f:
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(f.read())
                            encoders.encode_base64(part)
                            part.add_header(
                                'Content-Disposition',
                                f'attachment; filename="{os.path.basename(filepath)}"'
                            )
                            msg.attach(part)
            
            # Connect and send
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {recipient}")
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP Authentication failed. Check your email credentials. Error: {e}")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error occurred: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
    
    def send_premarket_report(self, recipient: str, html_content: str) -> bool:
        """Send pre-market report email."""
        subject = f"📈 Pre-Market Briefing - {self._get_date_str()}"
        return self.send_email(recipient, subject, html_content)
    
    def send_postmarket_report(self, recipient: str, html_content: str) -> bool:
        """Send post-market report email."""
        subject = f"📊 Market Close Report - {self._get_date_str()}"
        return self.send_email(recipient, subject, html_content)
    
    def send_weekly_report(self, recipient: str, html_content: str, chart_path: str = None) -> bool:
        """Send weekly summary report email."""
        subject = f"📈 Weekly Summary - {self._get_date_str()}"
        attachments = [chart_path] if chart_path and os.path.exists(chart_path) else None
        return self.send_email(recipient, subject, html_content, attachments)
    
    def _get_date_str(self) -> str:
        """Get formatted date string for subject line."""
        from datetime import datetime
        return datetime.now().strftime("%b %d, %Y")
    
    def test_connection(self) -> bool:
        """Test SMTP connection without sending an email."""
        if not self.sender_email or not self.sender_password:
            logger.error("Email credentials not configured")
            return False
        
        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                logger.info("SMTP connection test successful")
                return True
        except Exception as e:
            logger.error(f"SMTP connection test failed: {e}")
            return False


class EmailSenderFactory:
    """Factory for creating email senders from config."""
    
    @staticmethod
    def from_config(config: dict) -> EmailSender:
        """Create EmailSender from config dictionary."""
        email_config = config.get('email', {})
        return EmailSender(
            smtp_server=email_config.get('smtp_server', 'smtp.gmail.com'),
            smtp_port=email_config.get('smtp_port', 587),
            sender_email=email_config.get('sender_email'),
            sender_password=email_config.get('sender_password'),
        )


if __name__ == "__main__":
    # Test email sender
    import yaml
    
    logging.basicConfig(level=logging.INFO)
    
    # Load config
    try:
        with open('config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        sender = EmailSenderFactory.from_config(config)
        
        print("Testing SMTP connection...")
        if sender.test_connection():
            print("✓ SMTP connection successful!")
        else:
            print("✗ SMTP connection failed. Check your credentials.")
            print("\nTo configure Gmail:")
            print("1. Enable 2-Factor Authentication")
            print("2. Go to https://myaccount.google.com/apppasswords")
            print("3. Generate an App Password for 'Mail'")
            print("4. Update config.yaml with your email and app password")
            
    except FileNotFoundError:
        print("config.yaml not found. Please create it first.")
