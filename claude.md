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
├── email_generator.py    # HTML email + Jinja2 template generation
├── email_sender.py       # SMTP email delivery
├── notion_watchlist.py   # Fetches watchlist from Notion (source of truth)
├── notion_sync.py        # Notion database sync utilities
├── db.py                 # SQLite database for historical tracking
├── backfill_db.py        # One-time script to parse existing reports into DB
├── data/stock_history.db # SQLite database (WAL mode)
├── templates/            # Jinja2 email templates (base, weekly, pre/post-market)
│   └── macros/           # Shared email component macros
└── dashboard/
    ├── js/router.js      # Hash-based page routing
    ├── js/components/History.js     # Weekly Reports page
    └── js/components/Performance.js # Performance heatmap/streaks page
```

## Key Components

### Data Layer (`data_fetcher.py`)
- `StockDataFetcher` - Main class for stock quotes, pre/post market data, earnings, dividends
- `FuturesDataFetcher` - Futures data for pre-market context (ES, NQ, YM, RTY)
- Uses yfinance with caching to avoid rate limits
- Handles both stocks and crypto (symbols ending in `-USD`)

### Scheduler (`scheduler.py`)
- CLI flags: `--test`, `--premarket`, `--postmarket`, `--weekly`, `--force`
- `--premarket` and `--postmarket` check `is_market_day()` and skip on weekends/holidays
- `--force` overrides the trading day check; `--test` always bypasses it
- Can run as daemon or via launchd

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

### Historical Database (`db.py`)
- SQLite at `data/stock_history.db` (WAL mode for concurrent access)
- Tables: `weekly_snapshots`, `watchlist_changes`, `report_metadata`
- `weekly_report.py` writes snapshots + metadata after each report generation
- Watchlist diffs tracked automatically by comparing against `last_watchlist.json`
- Query functions: `get_all_streaks()`, `get_rolling_performers()`, `get_weekly_snapshots()`
- Backfill: `python backfill_db.py` parses existing HTML reports into DB

### Dashboard Pages
- **Hash-based routing**: `#/dashboard`, `#/history`, `#/performance`
- **Weekly Reports** (`History.js`): WoW chart, report timeline with iframe viewer, streaks, watchlist diffs
- **Performance** (`Performance.js`): period tabs (1W/1M/3M), top/bottom performers, color heatmap (archived tickers dimmed), streak leaderboard
- Watchlist status options: Watching, Holding, Archived (archived = excluded from reports, preserved in history)

### Email Templates (`templates/`)
- Jinja2 templates: `base.html`, `weekly.html`, `premarket.html`, `postmarket.html`
- Shared macros in `templates/macros/components.html`
- `JinjaEmailGenerator` class in `email_generator.py` — drop-in replacement for `EmailGenerator`
- Inline HTML bar charts (no matplotlib in emails), Performance Leaders section with streaks

## Configuration (`config.yaml`)

- **Watchlist**: ~120 symbols across tech, semiconductors, defense, space, energy, crypto, robotics, ETFs
- **Email**: Gmail SMTP with App Password authentication
- **Schedule**: EST timezone, configurable times
- **Alerts**: Big mover threshold (3%), volume spike threshold (2x avg)

## Running

```bash
# Install dependencies
pip install -r requirements.txt

# Test all reports (bypasses market day check)
python scheduler.py --test

# Run individual reports (skips on weekends/holidays)
python scheduler.py --premarket
python scheduler.py --postmarket
python scheduler.py --weekly

# Force run on non-trading day
python scheduler.py --premarket --force
python premarket_report.py --force

# Via shell wrapper
./run_report.sh premarket
./run_report.sh postmarket
./run_report.sh weekly
```

## LaunchAgent Schedule (Automated)

Reports run via macOS LaunchAgents (plists in `~/Library/LaunchAgents/`). They fire daily but the scripts self-guard against non-trading days using the NYSE calendar.

| Report | LaunchAgent | Local Time | EST Equivalent |
|--------|-------------|------------|----------------|
| Pre-market | `com.stockmonitor.premarket` | 9:00 PM daily | 9:00 AM EST |
| Post-market | `com.stockmonitor.postmarket` | 4:30 AM daily | 4:30 PM EST (prev day) |
| Weekly | `com.stockmonitor.weekly` | Saturday 9:00 AM | Friday 9:00 PM EST |

On weekends and NYSE holidays, pre-market and post-market scripts exit immediately with a log message. No email is sent.

```bash
# View LaunchAgent status
launchctl list | grep stockmonitor

# Reload after plist changes
launchctl unload ~/Library/LaunchAgents/com.stockmonitor.premarket.plist
launchctl load ~/Library/LaunchAgents/com.stockmonitor.premarket.plist
```

## Development Notes

- Email configured via Gmail SMTP with App Password
- Notion API token loaded from `.env` via python-dotenv (already migrated from hardcoded)
- Log files: `stock_monitor.log` (app), `cron.log` (scheduled runs)
- Reports saved to `reports/` directory (not in git)

## Dependencies

Core: yfinance, pandas, numpy, schedule, pytz, pyyaml
Email: smtplib (built-in), jinja2
Scraping: requests, beautifulsoup4, lxml, feedparser
Charts: matplotlib, plotly
