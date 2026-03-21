#!/usr/bin/env python3
"""
Backfill Database from Existing Weekly Reports
================================================
One-time script to parse existing weekly HTML reports and populate
the SQLite database with historical data.

Usage: python backfill_db.py
"""

import glob
import os
import re
import sys

from bs4 import BeautifulSoup

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import init_db, save_weekly_snapshots_batch, save_report_metadata, save_watchlist_diff

REPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'reports')


def parse_date_from_filename(filename: str) -> str:
    """Extract YYYY-MM-DD from weekly_YYYYMMDD_HHMM.html."""
    match = re.search(r'weekly_(\d{4})(\d{2})(\d{2})_(\d{4})\.html', filename)
    if not match:
        return None
    return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"


def parse_time_from_filename(filename: str) -> str:
    """Extract HHMM from filename for deduplication."""
    match = re.search(r'weekly_\d{8}_(\d{4})\.html', filename)
    return match.group(1) if match else '0000'


def parse_report(filepath: str) -> dict:
    """Parse a weekly report HTML file and extract structured data."""
    with open(filepath, 'r') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')

    result = {
        'total_stocks': 0,
        'gainers': 0,
        'losers': 0,
        'avg_change_pct': 0.0,
        'top_gainers': [],   # list of (symbol, price, change_pct)
        'top_losers': [],
        'sector_stocks': [], # list of (symbol, change_pct, sector)
    }

    # Parse Week Overview stats
    overview_rows = []
    for h2 in soup.find_all('h2'):
        if 'Week Overview' in h2.get_text():
            # Find the stats table that follows
            table_cell = h2.find_parent('td')
            if table_cell:
                parent_tr = table_cell.find_parent('tr')
                if parent_tr:
                    next_tr = parent_tr.find_next_sibling('tr')
                    if next_tr:
                        stat_rows = next_tr.find_all('tr')
                        for row in stat_rows:
                            cells = row.find_all('td')
                            if len(cells) == 2:
                                label = cells[0].get_text(strip=True)
                                value = cells[1].get_text(strip=True)
                                overview_rows.append((label, value))
            break

    for label, value in overview_rows:
        if 'Total Stocks' in label:
            result['total_stocks'] = int(re.sub(r'[^\d]', '', value) or 0)
        elif 'Gainers' in label:
            result['gainers'] = int(re.sub(r'[^\d]', '', value) or 0)
        elif 'Losers' in label:
            result['losers'] = int(re.sub(r'[^\d]', '', value) or 0)
        elif 'Avg' in label or 'Performance' in label:
            match = re.search(r'([+-]?\d+\.?\d*)', value)
            if match:
                result['avg_change_pct'] = float(match.group(1))
                if '-' in value:
                    result['avg_change_pct'] = -abs(result['avg_change_pct'])

    # Parse Top Gainers and Top Losers sections
    current_section = None
    for h2 in soup.find_all('h2'):
        text = h2.get_text()
        if 'Top Gainers' in text or 'Biggest Gains' in text:
            current_section = 'gainers'
        elif 'Biggest Declines' in text or 'Top Losers' in text or 'Biggest Losses' in text:
            current_section = 'losers'
        elif 'Movers by Sector' in text:
            current_section = 'sectors'
        else:
            continue

        if current_section in ('gainers', 'losers'):
            # Walk sibling rows until next section header
            parent_td = h2.find_parent('td')
            if not parent_td:
                continue
            parent_tr = parent_td.find_parent('tr')
            if not parent_tr:
                continue

            sibling = parent_tr.find_next_sibling('tr')
            while sibling:
                # Stop if we hit another section header
                h2_check = sibling.find('h2')
                if h2_check:
                    break
                # Stop at spacer rows that precede next section
                spacer = sibling.find('td', attrs={'style': lambda s: s and 'height: 10px' in s})
                if spacer:
                    break

                # Look for stock data: symbol (font-weight: 600), price ($), change%
                divs = sibling.find_all('div')
                symbol = None
                price = None
                change_pct = None

                for div in divs:
                    style = div.get('style', '')
                    text = div.get_text(strip=True)

                    if 'font-weight: 600' in style and not text.startswith('$') and not text.startswith('+') and not text.startswith('-'):
                        if re.match(r'^[A-Z]{1,6}(-USD)?$', text):
                            symbol = text
                    elif text.startswith('$'):
                        match = re.search(r'\$(\d+\.?\d*)', text)
                        if match:
                            price = float(match.group(1))
                    elif re.match(r'^[+-]?\d+\.?\d*%$', text):
                        change_pct = float(text.replace('%', ''))

                if symbol and change_pct is not None:
                    entry = (symbol, price, change_pct)
                    if current_section == 'gainers':
                        result['top_gainers'].append(entry)
                    else:
                        result['top_losers'].append(entry)

                sibling = sibling.find_next_sibling('tr')

        elif current_section == 'sectors':
            # Parse Movers by Sector: sector headers followed by stock rows
            parent_td = h2.find_parent('td')
            if not parent_td:
                continue
            parent_tr = parent_td.find_parent('tr')
            if not parent_tr:
                continue

            current_sector = None
            sibling = parent_tr.find_next_sibling('tr')
            while sibling:
                # Stop at next major section
                h2_check = sibling.find('h2')
                if h2_check:
                    break
                spacer = sibling.find('td', attrs={'style': lambda s: s and 'height: 10px' in s})
                if spacer:
                    break

                # Check for sector header
                sector_span = sibling.find('span', class_='text-accent')
                if sector_span:
                    sector_text = sector_span.get_text(strip=True)
                    if sector_text and not any(c.isdigit() for c in sector_text):
                        current_sector = sector_text

                # Check for stock data in sector
                spans = sibling.find_all('span')
                symbol = None
                change_pct = None
                for span in spans:
                    text = span.get_text(strip=True)
                    classes = span.get('class', [])
                    if 'text-primary' in classes and re.match(r'^[A-Z]{1,6}(-USD)?$', text):
                        symbol = text
                    elif ('text-green' in classes or 'text-red' in classes):
                        match = re.search(r'([+-]?\d+\.?\d*)%', text)
                        if match:
                            change_pct = float(match.group(1))

                if symbol and change_pct is not None and current_sector:
                    result['sector_stocks'].append((symbol, change_pct, current_sector))

                sibling = sibling.find_next_sibling('tr')

    return result


def deduplicate_reports(files: list) -> dict:
    """For same-day reports, keep only the latest (highest HHMM)."""
    by_date = {}
    for f in files:
        date = parse_date_from_filename(os.path.basename(f))
        hhmm = parse_time_from_filename(os.path.basename(f))
        if date is None:
            continue
        if date not in by_date or hhmm > by_date[date][1]:
            by_date[date] = (f, hhmm)
    return {date: info[0] for date, info in sorted(by_date.items())}


def main():
    init_db()

    # Find all weekly reports
    pattern = os.path.join(REPORTS_DIR, 'weekly_*.html')
    files = sorted(glob.glob(pattern))
    print(f"Found {len(files)} weekly report files")

    # Deduplicate same-day reports
    reports = deduplicate_reports(files)
    print(f"After deduplication: {len(reports)} unique report dates")

    # Track symbols per date for watchlist diff
    prev_symbols = set()
    dates_in_order = sorted(reports.keys())

    for report_date in dates_in_order:
        filepath = reports[report_date]
        rel_path = os.path.relpath(filepath, os.path.dirname(os.path.abspath(__file__)))
        print(f"\nProcessing {report_date} ({os.path.basename(filepath)})...")

        data = parse_report(filepath)

        # Build a combined stock set from all sections
        all_stocks = {}  # symbol -> {price, change_pct, sector}

        # From gainers/losers (these have price data)
        for symbol, price, change_pct in data['top_gainers']:
            all_stocks[symbol] = {'price': price, 'change_pct': change_pct, 'sector': None}
        for symbol, price, change_pct in data['top_losers']:
            all_stocks[symbol] = {'price': price, 'change_pct': change_pct, 'sector': None}

        # From sector movers (these have sector data)
        for symbol, change_pct, sector in data['sector_stocks']:
            if symbol in all_stocks:
                all_stocks[symbol]['sector'] = sector
                # Sector data might not have price, keep existing
            else:
                all_stocks[symbol] = {'price': None, 'change_pct': change_pct, 'sector': sector}

        print(f"  Stats: {data['total_stocks']} total, {data['gainers']} up, {data['losers']} down, avg {data['avg_change_pct']:+.2f}%")
        print(f"  Parsed {len(all_stocks)} unique symbols from gainers/losers/sectors")

        # Save snapshots
        snapshots = [
            (sym, info['price'], info['change_pct'], None, info['sector'])
            for sym, info in all_stocks.items()
        ]
        if snapshots:
            save_weekly_snapshots_batch(report_date, snapshots)

        # Save report metadata
        top_gainer = data['top_gainers'][0] if data['top_gainers'] else ('', 0, 0)
        top_loser = data['top_losers'][0] if data['top_losers'] else ('', 0, 0)

        save_report_metadata(
            report_date=report_date,
            file_path=rel_path,
            total_stocks=data['total_stocks'],
            gainers=data['gainers'],
            losers=data['losers'],
            avg_change_pct=data['avg_change_pct'],
            top_gainer=top_gainer[0],
            top_gainer_pct=top_gainer[2],
            top_loser=top_loser[0],
            top_loser_pct=top_loser[2],
        )

        # Watchlist diff
        current_symbols = set(all_stocks.keys())
        if prev_symbols and current_symbols:
            added = current_symbols - prev_symbols
            removed = prev_symbols - current_symbols
            if added or removed:
                save_watchlist_diff(report_date, list(added), list(removed))
                if added:
                    print(f"  Watchlist +{len(added)}: {', '.join(sorted(added)[:5])}{'...' if len(added) > 5 else ''}")
                if removed:
                    print(f"  Watchlist -{len(removed)}: {', '.join(sorted(removed)[:5])}{'...' if len(removed) > 5 else ''}")
        prev_symbols = current_symbols

    print(f"\nBackfill complete! Database at data/stock_history.db")


if __name__ == '__main__':
    main()
