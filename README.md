# 📈 Stock Monitor System

A comprehensive stock monitoring system that sends you daily pre-market briefings, post-market analysis, and weekly summary reports via email.

## Features

- **Pre-Market Report** (6:30 AM EST)
  - Futures overview (S&P, NASDAQ, Dow, Russell)
  - Pre-market movers from your watchlist
  - Upcoming earnings calendar
  - Ex-dividend dates
  - Top market & stock-specific news

- **Post-Market Report** (4:30 PM EST)
  - Market indices summary
  - Day's top gainers & losers
  - Volume spike alerts
  - After-hours movement
  - News on big movers

- **Weekly Summary** (Saturday 9:00 AM EST)
  - Week-over-week performance comparison
  - Top gainers & losers for the week
  - Performance charts
  - Upcoming earnings & dividends for next week

## Quick Start

### 1. Clone/Download the System

```bash
# Create directory and copy files
mkdir stock_monitor
cd stock_monitor
# Copy all files here
```

### 2. Install Dependencies

```bash
# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install packages
pip install -r requirements.txt
```

### 3. Configure Email (Gmail)

To send emails via Gmail, you need to create an **App Password**:

1. Go to your Google Account settings: https://myaccount.google.com
2. Navigate to **Security** → **2-Step Verification** (enable if not already)
3. Go to **Security** → **App passwords** (https://myaccount.google.com/apppasswords)
4. Select "Mail" and "Mac" (or your device)
5. Click **Generate** and copy the 16-character password

Now update `config.yaml`:

```yaml
email:
  smtp_server: "smtp.gmail.com"
  smtp_port: 587
  sender_email: "your.email@gmail.com"      # Your Gmail address
  sender_password: "xxxx xxxx xxxx xxxx"    # App Password (with spaces)
  recipient_email: "your.email@gmail.com"   # Where to receive reports
```

### 4. Customize Your Watchlist

Edit `config.yaml` and update the `watchlist` section with your stocks:

```yaml
watchlist:
  - AAPL
  - GOOGL
  - TSLA
  # ... add your stocks
```

### 5. Test the System

```bash
# Run all reports once to test
python scheduler.py --test

# Or run individual reports
python scheduler.py --premarket
python scheduler.py --postmarket
python scheduler.py --weekly
```

### 6. Run the Scheduler

```bash
# Run in foreground
python scheduler.py

# Run in background (Linux/Mac)
nohup python scheduler.py > /dev/null 2>&1 &

# Or use screen/tmux
screen -S stock_monitor
python scheduler.py
# Press Ctrl+A, D to detach
```

## Alternative: Run via Cron (Recommended for Mac)

Instead of running the scheduler daemon, you can use cron jobs:

```bash
# Open crontab
crontab -e

# Add these lines (adjust paths):
# Pre-market at 6:30 AM EST (Monday-Friday)
30 6 * * 1-5 cd /path/to/stock_monitor && /path/to/venv/bin/python premarket_report.py >> /path/to/stock_monitor/cron.log 2>&1

# Post-market at 4:30 PM EST (Monday-Friday)
30 16 * * 1-5 cd /path/to/stock_monitor && /path/to/venv/bin/python postmarket_report.py >> /path/to/stock_monitor/cron.log 2>&1

# Weekly report at 9:00 AM Saturday
0 9 * * 6 cd /path/to/stock_monitor && /path/to/venv/bin/python weekly_report.py >> /path/to/stock_monitor/cron.log 2>&1
```

**Important for Mac users:** Ensure your Mac doesn't sleep during scheduled times, or use `caffeinate`:
```bash
30 6 * * 1-5 caffeinate -i cd /path/to/stock_monitor && ...
```

## Alternative: macOS Launch Agent (Better for Mac)

Create a Launch Agent for more reliable scheduling on macOS:

1. Create the plist file:

```bash
nano ~/Library/LaunchAgents/com.stockmonitor.scheduler.plist
```

2. Add this content:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.stockmonitor.scheduler</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/venv/bin/python</string>
        <string>/path/to/stock_monitor/scheduler.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/path/to/stock_monitor</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/path/to/stock_monitor/scheduler.log</string>
    <key>StandardErrorPath</key>
    <string>/path/to/stock_monitor/scheduler_error.log</string>
</dict>
</plist>
```

3. Load the agent:

```bash
launchctl load ~/Library/LaunchAgents/com.stockmonitor.scheduler.plist
```

## File Structure

```
stock_monitor/
├── config.yaml           # Configuration file
├── requirements.txt      # Python dependencies
├── scheduler.py          # Main scheduler
├── premarket_report.py   # Pre-market report generator
├── postmarket_report.py  # Post-market report generator
├── weekly_report.py      # Weekly report generator
├── data_fetcher.py       # Stock data fetching module
├── news_fetcher.py       # News fetching module
├── email_generator.py    # HTML email generation
├── email_sender.py       # Email sending module
├── stock_monitor.log     # Log file
└── reports/              # Saved report copies
    ├── premarket_*.html
    ├── postmarket_*.html
    ├── weekly_*.html
    └── weekly_chart_*.png
```

## Configuration Options

### Schedule Settings
```yaml
schedule:
  timezone: "America/New_York"
  premarket_time: "06:30"    # 6:30 AM EST
  postmarket_time: "16:30"   # 4:30 PM EST
  weekly_day: "saturday"
  weekly_time: "09:00"
```

### Report Settings
```yaml
report:
  top_movers_count: 10        # Show top N gainers/losers
  news_per_stock: 3           # Max news items per stock
  include_premarket: true
  include_afterhours: true
  include_earnings: true
  include_dividends: true
```

### Alert Thresholds
```yaml
alerts:
  big_mover_threshold: 3.0    # Flag stocks moving >3%
  volume_spike_threshold: 2.0 # Flag when volume is 2x average
```

## Troubleshooting

### Email Not Sending
1. Verify App Password is correct (no typos)
2. Ensure 2FA is enabled on your Google account
3. Check if "Less secure app access" needs to be enabled (shouldn't be needed with App Password)
4. Test connection: `python email_sender.py`

### No Data for Some Stocks
- Some small-cap or OTC stocks may not have pre/post market data
- Crypto (BTC-USD, ETH-USD) trades 24/7, so pre/post market doesn't apply
- Check Yahoo Finance directly to verify data availability

### Rate Limiting
- Yahoo Finance may rate limit excessive requests
- The system has built-in delays, but if issues persist, reduce watchlist size
- Consider using a paid API (Polygon.io, Alpha Vantage) for more reliable data

### Charts Not Generating
- Ensure matplotlib is installed: `pip install matplotlib`
- Check write permissions for the reports/ directory

## Extending the System

### Adding New Data Sources
Edit `data_fetcher.py` to add additional data sources like:
- Alpha Vantage (free tier available)
- Polygon.io (paid, more reliable)
- IEX Cloud

### Customizing Email Templates
Edit `email_generator.py` to modify:
- Color scheme (COLORS dict)
- HTML template structure
- Report sections and layout

### Adding SMS Alerts
Integrate Twilio for SMS alerts on big movers:
```python
# Example integration point in postmarket_report.py
from twilio.rest import Client
# ... send SMS for stocks with >5% movement
```

## Data Sources

- **Stock Prices:** Yahoo Finance (via yfinance)
- **News:** Yahoo Finance RSS, Finviz
- **Earnings Calendar:** Yahoo Finance
- **Dividends:** Yahoo Finance

## Limitations

- Yahoo Finance is unofficial and may break occasionally
- Pre/post market data may be delayed or unavailable
- News sources are free and may miss some stories
- Rate limiting may affect large watchlists

## License

MIT License - Feel free to modify and distribute.

---

**Questions or Issues?** Check the log file (`stock_monitor.log`) for detailed error messages.
