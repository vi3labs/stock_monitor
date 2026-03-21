#!/usr/bin/env python3
"""
Stock Monitor - SQLite Database Layer
======================================
Stores weekly snapshots, watchlist changes, and report metadata
for historical analysis and dashboard features.
"""

import json
import os
import sqlite3
from contextlib import contextmanager
from typing import Dict, List, Optional

DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
DB_PATH = os.path.join(DB_DIR, 'stock_history.db')


@contextmanager
def get_connection():
    """Context manager for database connections with WAL mode."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create tables if they don't exist."""
    os.makedirs(DB_DIR, exist_ok=True)
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS weekly_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_date TEXT NOT NULL,
                symbol TEXT NOT NULL,
                price REAL,
                week_change_pct REAL,
                volume INTEGER,
                sector TEXT,
                UNIQUE(report_date, symbol)
            );

            CREATE TABLE IF NOT EXISTS watchlist_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                change_date TEXT NOT NULL,
                symbol TEXT NOT NULL,
                action TEXT NOT NULL CHECK(action IN ('added', 'removed'))
            );

            CREATE TABLE IF NOT EXISTS report_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_date TEXT NOT NULL UNIQUE,
                report_type TEXT DEFAULT 'weekly',
                file_path TEXT,
                total_stocks INTEGER,
                gainers INTEGER,
                losers INTEGER,
                avg_change_pct REAL,
                top_gainer TEXT,
                top_gainer_pct REAL,
                top_loser TEXT,
                top_loser_pct REAL,
                summary_json TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_snapshots_symbol ON weekly_snapshots(symbol);
            CREATE INDEX IF NOT EXISTS idx_snapshots_date ON weekly_snapshots(report_date);
            CREATE INDEX IF NOT EXISTS idx_watchlist_date ON watchlist_changes(change_date);
        """)


def save_weekly_snapshot(report_date: str, symbol: str, price: Optional[float],
                         week_change_pct: Optional[float], volume: Optional[int],
                         sector: Optional[str]):
    """Save a single stock's weekly snapshot."""
    with get_connection() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO weekly_snapshots
               (report_date, symbol, price, week_change_pct, volume, sector)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (report_date, symbol, price, week_change_pct, volume, sector)
        )


def save_weekly_snapshots_batch(report_date: str, snapshots: List[tuple]):
    """Save multiple snapshots in one transaction. Each tuple: (symbol, price, week_change_pct, volume, sector)."""
    with get_connection() as conn:
        conn.executemany(
            """INSERT OR REPLACE INTO weekly_snapshots
               (report_date, symbol, price, week_change_pct, volume, sector)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [(report_date, s[0], s[1], s[2], s[3], s[4]) for s in snapshots]
        )


def save_report_metadata(report_date: str, file_path: str, total_stocks: int,
                         gainers: int, losers: int, avg_change_pct: float,
                         top_gainer: str, top_gainer_pct: float,
                         top_loser: str, top_loser_pct: float,
                         summary_json: Optional[str] = None):
    """Save report metadata."""
    with get_connection() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO report_metadata
               (report_date, file_path, total_stocks, gainers, losers, avg_change_pct,
                top_gainer, top_gainer_pct, top_loser, top_loser_pct, summary_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (report_date, file_path, total_stocks, gainers, losers, avg_change_pct,
             top_gainer, top_gainer_pct, top_loser, top_loser_pct, summary_json)
        )


def save_watchlist_diff(change_date: str, added_symbols: List[str], removed_symbols: List[str]):
    """Save watchlist additions and removals."""
    with get_connection() as conn:
        for symbol in added_symbols:
            conn.execute(
                "INSERT INTO watchlist_changes (change_date, symbol, action) VALUES (?, ?, 'added')",
                (change_date, symbol)
            )
        for symbol in removed_symbols:
            conn.execute(
                "INSERT INTO watchlist_changes (change_date, symbol, action) VALUES (?, ?, 'removed')",
                (change_date, symbol)
            )


def get_weekly_snapshots(symbol: Optional[str] = None, start_date: Optional[str] = None,
                         end_date: Optional[str] = None) -> List[Dict]:
    """Get weekly snapshots, optionally filtered by symbol and date range."""
    with get_connection() as conn:
        query = "SELECT * FROM weekly_snapshots WHERE 1=1"
        params = []
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        if start_date:
            query += " AND report_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND report_date <= ?"
            params.append(end_date)
        query += " ORDER BY report_date ASC, symbol ASC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_all_report_metadata() -> List[Dict]:
    """Get all report metadata ordered by date descending."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM report_metadata ORDER BY report_date DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def get_watchlist_changes(start_date: Optional[str] = None,
                          end_date: Optional[str] = None) -> List[Dict]:
    """Get watchlist changes, optionally filtered by date range."""
    with get_connection() as conn:
        query = "SELECT * FROM watchlist_changes WHERE 1=1"
        params = []
        if start_date:
            query += " AND change_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND change_date <= ?"
            params.append(end_date)
        query += " ORDER BY change_date DESC, symbol ASC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_symbol_streak(symbol: str) -> Dict:
    """Get the current streak direction and count for a symbol."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT report_date, week_change_pct FROM weekly_snapshots
               WHERE symbol = ? AND week_change_pct IS NOT NULL
               ORDER BY report_date DESC""",
            (symbol,)
        ).fetchall()

    if not rows:
        return {'symbol': symbol, 'direction': None, 'weeks': 0, 'total_change_pct': 0.0}

    first_change = rows[0]['week_change_pct']
    if first_change == 0:
        return {'symbol': symbol, 'direction': None, 'weeks': 0, 'total_change_pct': 0.0}

    direction = 'up' if first_change > 0 else 'down'
    weeks = 0
    total_change_pct = 0.0

    for row in rows:
        change = row['week_change_pct']
        if (direction == 'up' and change > 0) or (direction == 'down' and change < 0):
            weeks += 1
            total_change_pct += change
        else:
            break

    return {'symbol': symbol, 'direction': direction, 'weeks': weeks, 'total_change_pct': round(total_change_pct, 2)}


def get_all_streaks() -> List[Dict]:
    """Get streak data for all symbols with streak >= 2."""
    with get_connection() as conn:
        symbols = conn.execute(
            "SELECT DISTINCT symbol FROM weekly_snapshots"
        ).fetchall()

    streaks = []
    for row in symbols:
        s = get_symbol_streak(row['symbol'])
        if s['weeks'] >= 2:
            streaks.append(s)

    streaks.sort(key=lambda x: x['weeks'], reverse=True)
    return streaks


def get_rolling_performers(n: int = 5, weeks: int = 4) -> Dict:
    """Get top and bottom performers based on cumulative change over a period."""
    with get_connection() as conn:
        # Get the last N distinct report dates
        dates = conn.execute(
            "SELECT DISTINCT report_date FROM weekly_snapshots ORDER BY report_date DESC LIMIT ?",
            (weeks,)
        ).fetchall()

        if not dates:
            return {'top': [], 'bottom': [], 'period_weeks': weeks}

        cutoff_date = dates[-1]['report_date']

        # Get cumulative change per symbol over the period
        rows = conn.execute(
            """SELECT symbol, SUM(week_change_pct) as cumulative_change,
                      COUNT(*) as weeks_present, AVG(week_change_pct) as avg_change
               FROM weekly_snapshots
               WHERE report_date >= ? AND week_change_pct IS NOT NULL
               GROUP BY symbol
               HAVING weeks_present >= 2
               ORDER BY cumulative_change DESC""",
            (cutoff_date,)
        ).fetchall()

    all_performers = [dict(r) for r in rows]
    for p in all_performers:
        p['cumulative_change'] = round(p['cumulative_change'], 2)
        p['avg_change'] = round(p['avg_change'], 2)

    return {
        'top': all_performers[:n],
        'bottom': all_performers[-n:][::-1] if len(all_performers) >= n else all_performers[::-1],
        'all': all_performers,
        'period_weeks': weeks,
        'from_date': cutoff_date,
        'to_date': dates[0]['report_date']
    }


if __name__ == '__main__':
    init_db()
    print(f"Database initialized at {DB_PATH}")
