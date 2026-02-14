#!/usr/bin/env python3
"""
Weekly Summary Report Generator
===============================
Generates and sends the weekly summary report with performance charts.
Run this on Saturday at 9:00 AM EST.
"""

import logging
from datetime import datetime, timedelta
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config_loader import load_config, setup_logging
from data_fetcher import StockDataFetcher
from email_generator import EmailGenerator
from email_sender import EmailSenderFactory
from notion_watchlist import get_watchlist

setup_logging()
logger = logging.getLogger(__name__)


def _send_error_alert(config: dict, message: str):
    """Send error alert email using existing email infrastructure."""
    try:
        from email_sender import EmailSenderFactory
        sender = EmailSenderFactory.from_config(config)
        email_config = config['email']
        recipient = email_config.get('recipient_email', email_config.get('sender_email'))
        html = f"""<div style="font-family: monospace; background: #1a1a2e; color: #f5f2eb; padding: 20px;">
            <h2 style="color: #FF1744;">Stock Monitor Alert</h2>
            <p>{message}</p>
            <p>Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>Action: Check Notion token and watchlist database.</p>
        </div>"""
        sender.send_email(recipient, f"[ALERT] Stock Monitor Error", html)
    except Exception as e:
        logger.error(f"Could not send error alert: {e}")


def generate_performance_chart(weekly_data: dict, output_path: str) -> bool:
    """
    Generate a performance chart image.
    Returns True if successful, False otherwise.
    """
    try:
        import matplotlib
        matplotlib.use('Agg')  # Non-interactive backend
        import matplotlib.pyplot as plt
        import numpy as np
        
        # Sort by performance
        sorted_data = sorted(
            weekly_data.items(),
            key=lambda x: x[1].get('week_change_percent', 0),
            reverse=True
        )
        
        # Get top 10 and bottom 10
        top_10 = sorted_data[:10]
        bottom_10 = sorted_data[-10:]
        
        # Combine for chart
        chart_data = top_10 + bottom_10
        symbols = [d[0] for d in chart_data]
        changes = [d[1].get('week_change_percent', 0) for d in chart_data]
        
        # Create figure
        fig, ax = plt.subplots(figsize=(12, 8), facecolor='#1a1a2e')
        ax.set_facecolor('#16213e')
        
        # Create bar chart
        colors = ['#00C853' if c >= 0 else '#FF1744' for c in changes]
        bars = ax.barh(range(len(symbols)), changes, color=colors, height=0.7)
        
        # Customize appearance
        ax.set_yticks(range(len(symbols)))
        ax.set_yticklabels(symbols, fontsize=10, color='white')
        ax.set_xlabel('Weekly Change (%)', fontsize=12, color='white')
        ax.set_title('Weekly Performance - Top & Bottom Movers', fontsize=14, color='white', pad=20)
        
        # Add value labels
        for i, (bar, change) in enumerate(zip(bars, changes)):
            width = bar.get_width()
            label_x = width + 0.3 if width >= 0 else width - 0.3
            ha = 'left' if width >= 0 else 'right'
            ax.text(label_x, bar.get_y() + bar.get_height()/2, f'{change:+.1f}%',
                   va='center', ha=ha, fontsize=9, color='white')
        
        # Style the axes
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_color('#4a5568')
        ax.spines['left'].set_color('#4a5568')
        ax.tick_params(colors='white')
        ax.xaxis.label.set_color('white')
        
        # Add zero line
        ax.axvline(x=0, color='#4a5568', linewidth=1, linestyle='-')
        
        # Add grid
        ax.xaxis.grid(True, linestyle='--', alpha=0.3, color='#4a5568')
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, facecolor='#1a1a2e', edgecolor='none')
        plt.close()
        
        logger.info(f"Chart saved to {output_path}")
        return True
        
    except ImportError:
        logger.warning("matplotlib not installed. Skipping chart generation.")
        return False
    except Exception as e:
        logger.error(f"Error generating chart: {e}")
        return False


def generate_comparison_chart(weekly_data: dict, output_path: str) -> bool:
    """
    Generate a week-over-week comparison chart.
    """
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        
        # Get stocks with daily data
        stocks_with_data = [(s, d) for s, d in weekly_data.items() 
                           if d.get('daily_closes') and len(d.get('daily_closes', [])) >= 2]
        
        if len(stocks_with_data) < 5:
            logger.warning("Not enough data for comparison chart")
            return False
        
        # Sort by volatility (most interesting)
        stocks_with_data.sort(key=lambda x: abs(x[1].get('week_change_percent', 0)), reverse=True)
        
        # Take top 8 movers
        top_movers = stocks_with_data[:8]
        
        # Create figure
        fig, ax = plt.subplots(figsize=(12, 6), facecolor='#1a1a2e')
        ax.set_facecolor('#16213e')
        
        colors = plt.cm.Set2(range(len(top_movers)))
        
        for i, (symbol, data) in enumerate(top_movers):
            closes = data.get('daily_closes', [])
            if closes:
                # Normalize to percentage change from start
                normalized = [(c / closes[0] - 1) * 100 for c in closes]
                days = list(range(len(normalized)))
                ax.plot(days, normalized, label=symbol, color=colors[i], linewidth=2, marker='o', markersize=4)
        
        # Style
        ax.set_xlabel('Day of Week', fontsize=12, color='white')
        ax.set_ylabel('Change from Monday (%)', fontsize=12, color='white')
        ax.set_title('Week Performance - Top Movers', fontsize=14, color='white', pad=20)
        
        ax.legend(loc='upper left', facecolor='#16213e', edgecolor='#4a5568', labelcolor='white')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['bottom'].set_color('#4a5568')
        ax.spines['left'].set_color('#4a5568')
        ax.tick_params(colors='white')
        ax.grid(True, linestyle='--', alpha=0.3, color='#4a5568')
        ax.axhline(y=0, color='#4a5568', linewidth=1, linestyle='-')
        
        # Set x-axis labels
        ax.set_xticks(range(5))
        ax.set_xticklabels(['Mon', 'Tue', 'Wed', 'Thu', 'Fri'])
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, facecolor='#1a1a2e', edgecolor='none')
        plt.close()
        
        logger.info(f"Comparison chart saved to {output_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error generating comparison chart: {e}")
        return False


def main():
    """Generate and send weekly report."""
    logger.info("=" * 50)
    logger.info("Starting Weekly Summary Report Generation")
    logger.info("=" * 50)
    
    try:
        # Load configuration
        config = load_config()
        symbols = get_watchlist()  # Fetch from Notion (source of truth)
        email_config = config['email']

        if len(symbols) == 0:
            logger.critical("ALERT: Watchlist returned 0 symbols! Aborting report.")
            _send_error_alert(config, "Watchlist returned 0 symbols - Notion may be down or token expired")
            return

        if len(symbols) < 10:
            logger.warning(f"ALERT: Only {len(symbols)} symbols returned (expected ~80+)")

        logger.info(f"Tracking {len(symbols)} symbols")
        
        # Initialize components
        stock_fetcher = StockDataFetcher(symbols)
        email_generator = EmailGenerator()
        email_sender = EmailSenderFactory.from_config(config)
        
        # Fetch weekly performance data
        logger.info("Fetching weekly performance data...")
        weekly_data = stock_fetcher.get_weekly_performance()
        logger.info(f"Got weekly data for {len(weekly_data)} symbols")

        if len(weekly_data) < len(symbols) * 0.5:
            logger.warning(f"Data quality issue: Only got quotes for {len(weekly_data)}/{len(symbols)} symbols")

        # Fetch upcoming earnings (next 2 weeks)
        logger.info("Fetching upcoming earnings...")
        earnings = stock_fetcher.get_earnings_calendar(days_ahead=14)
        logger.info(f"Found {len(earnings)} upcoming earnings")
        
        # Fetch upcoming dividends
        logger.info("Fetching upcoming dividends...")
        dividends = stock_fetcher.get_dividend_calendar(days_ahead=14)
        logger.info(f"Found {len(dividends)} upcoming ex-dividend dates")
        
        # Generate charts
        os.makedirs('reports', exist_ok=True)
        chart_path = f'reports/weekly_chart_{datetime.now().strftime("%Y%m%d")}.png'
        comparison_chart_path = f'reports/weekly_comparison_{datetime.now().strftime("%Y%m%d")}.png'
        
        logger.info("Generating performance chart...")
        generate_performance_chart(weekly_data, chart_path)
        
        logger.info("Generating comparison chart...")
        generate_comparison_chart(weekly_data, comparison_chart_path)
        
        # Generate email
        logger.info("Generating email...")
        html_content = email_generator.generate_weekly_report(
            weekly_data=weekly_data,
            earnings_next_week=earnings,
            dividends_next_week=dividends
        )
        
        # Save a local copy
        debug_path = f'reports/weekly_{datetime.now().strftime("%Y%m%d_%H%M")}.html'
        with open(debug_path, 'w') as f:
            f.write(html_content)
        logger.info(f"Saved debug copy to {debug_path}")
        
        # Print summary to console
        logger.info("\n" + "=" * 40)
        logger.info("WEEKLY SUMMARY")
        logger.info("=" * 40)
        
        sorted_weekly = sorted(weekly_data.values(), key=lambda x: x.get('week_change_percent', 0), reverse=True)
        
        logger.info("\nWeek's Top Gainers:")
        for g in sorted_weekly[:5]:
            logger.info(f"  {g['symbol']:8} {g.get('week_change_percent', 0):+6.2f}%")
        
        logger.info("\nWeek's Biggest Losers:")
        for l in sorted_weekly[-5:]:
            logger.info(f"  {l['symbol']:8} {l.get('week_change_percent', 0):+6.2f}%")
        
        logger.info("=" * 40 + "\n")
        
        # Send email
        recipient = email_config.get('recipient_email', email_config.get('sender_email'))
        
        if recipient and email_config.get('sender_email') and email_config.get('sender_password'):
            logger.info(f"Sending email to {recipient}...")
            
            # Include chart as attachment if it exists
            attachments = []
            if os.path.exists(chart_path):
                attachments.append(chart_path)
            if os.path.exists(comparison_chart_path):
                attachments.append(comparison_chart_path)
            
            success = email_sender.send_weekly_report(
                recipient, 
                html_content, 
                chart_path if os.path.exists(chart_path) else None
            )
            
            if success:
                logger.info("✓ Weekly report sent successfully!")
            else:
                logger.error("✗ Failed to send email")
        else:
            logger.warning("Email not configured. Report saved locally only.")
            logger.info(f"View the report at: {debug_path}")
        
        logger.info("Weekly report generation complete")
        
    except Exception as e:
        logger.exception(f"Error generating weekly report: {e}")
        raise


if __name__ == "__main__":
    main()
