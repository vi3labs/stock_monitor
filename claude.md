# Stock Monitor System

## Project Overview

A comprehensive stock monitoring system that sends daily pre-market briefings, post-market analysis, and weekly summary reports via email. **Notion is the source of truth** for the watchlist - stocks are fetched from the Stock Watchlist database.

## Architecture

```
stock_monitor/
├── config.yaml           # Configuration (email, schedule, alerts) - NOT in git
├── scheduler.py          # Main scheduler daemon (also usable via CLI)
├── run_report.sh         # Cron wrapper script with logging
├── premarket_report.py   # Pre-market report generator (6:30 AM EST)
├── postmarket_report.py  # Post-market report generator (4:30 PM EST)
├── weekly_report.py      # Weekly summary generator (Saturday 9:00 AM EST)
├── data_fetcher.py       # Stock data fetching (yfinance)
├── news_fetcher.py       # News aggregation (Yahoo Finance, Finviz)
├── email_generator.py    # HTML email template generation
├── email_sender.py       # SMTP email delivery
├── notion_watchlist.py   # Fetches watchlist from Notion (source of truth)
└── notion_sync.py        # Notion database sync utilities
```

## Key Components

### Data Layer (`data_fetcher.py`)
- `StockDataFetcher` - Main class for stock quotes, pre/post market data, earnings, dividends
- `FuturesDataFetcher` - Futures data for pre-market context (ES, NQ, YM, RTY)
- Uses yfinance with caching to avoid rate limits
- Handles both stocks and crypto (symbols ending in `-USD`)

### Scheduler (`scheduler.py`)
- CLI flags: `--test`, `--premarket`, `--postmarket`, `--weekly`
- Checks for market days (skips weekends/holidays)
- Can run as daemon or via cron/launchd

### Notion Integration (`notion_watchlist.py`)
**Notion is the source of truth for the watchlist!**

| Database | data_source_id | database_id |
|----------|----------------|-------------|
| Stock Watchlist | `2f2c5966-9a07-80e0-b8ef-000b7da7395b` | `2f2c5966-9a07-80c8-b1cb-fc120342d72b` |
| Stock Dashboard | - | `2f0c5966-9a07-8185-8e0c-d86866e0c801` |

- `get_watchlist()` fetches tickers with status "Watching" or "Holding"
- Uses direct requests to Notion API (not MCP) with token from environment
- All report scripts import from `notion_watchlist.py`

### Sector Mapping (`notion_sync.py`)
- Sector mapping and company name overrides built-in
- Generates daily summary content with top gainers/losers

## Configuration (`config.yaml`)

- **Watchlist**: ~120 symbols across tech, semiconductors, defense, space, energy, crypto, robotics, ETFs
- **Email**: Gmail SMTP with App Password authentication
- **Schedule**: EST timezone, configurable times
- **Alerts**: Big mover threshold (3%), volume spike threshold (2x avg)

## Running

```bash
# Install dependencies
pip install -r requirements.txt

# Test all reports
python scheduler.py --test

# Run individual reports
python scheduler.py --premarket
python scheduler.py --postmarket
python scheduler.py --weekly

# Via cron wrapper (used by scheduled jobs)
./run_report.sh premarket
./run_report.sh postmarket
./run_report.sh weekly
```

## Cron Schedule (Automated)

Cron is configured to run reports automatically. Times shown are local (+07) / EST:

| Report | Local Time | EST Time |
|--------|------------|----------|
| Pre-market | 6:30 PM Mon-Fri | 6:30 AM Mon-Fri |
| Post-market | 4:30 AM Tue-Sat | 4:30 PM Mon-Fri |
| Weekly | 9:00 PM Saturday | 9:00 AM Saturday |

```bash
# View cron schedule
crontab -l

# Edit cron schedule
crontab -e
```

## Development Notes

- Email configured via Gmail SMTP with App Password
- Notion API token stored in `notion_watchlist.py` (should move to env)
- Log files: `stock_monitor.log` (app), `cron.log` (scheduled runs)
- Reports saved to `reports/` directory (not in git)

## Dependencies

Core: yfinance, pandas, numpy, schedule, pytz, pyyaml
Email: smtplib (built-in), jinja2
Scraping: requests, beautifulsoup4, lxml, feedparser
Charts: matplotlib, plotly
