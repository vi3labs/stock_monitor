"""
Email Generator Module
======================
Generates HTML emails for stock reports with inline CSS for email client compatibility.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging

# Import sector mapping
from notion_sync import SECTOR_MAP

logger = logging.getLogger(__name__)


class EmailGenerator:
    """Generates HTML emails for stock reports with inline styles."""

    # Color scheme
    COLORS = {
        'green': '#00C853',
        'red': '#FF1744',
        'neutral': '#9E9E9E',
        'bg_dark': '#1a1a2e',
        'bg_card': '#16213e',
        'bg_section': '#1e2a47',
        'text_primary': '#ffffff',
        'text_secondary': '#a0a0a0',
        'accent': '#4fc3f7',
        'border': '#2d3748',
    }

    def __init__(self):
        self.c = self.COLORS

    def _format_change(self, change_pct: float) -> tuple:
        """Format price change with color."""
        if change_pct > 0:
            return f"+{change_pct:.2f}%", self.c['green']
        elif change_pct < 0:
            return f"{change_pct:.2f}%", self.c['red']
        else:
            return "0.00%", self.c['neutral']

    def _format_price(self, price: float) -> str:
        """Format price appropriately."""
        if price >= 1000:
            return f"${price:,.2f}"
        elif price >= 1:
            return f"${price:.2f}"
        else:
            return f"${price:.4f}"

    def _base_wrapper(self, content: str) -> str:
        """Wrap content in base HTML with inline styles."""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 20px; background-color: {self.c['bg_dark']}; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;">
    <table cellpadding="0" cellspacing="0" border="0" width="100%" style="max-width: 600px; margin: 0 auto; background-color: {self.c['bg_card']}; border-radius: 12px; overflow: hidden;">
        {content}
    </table>
</body>
</html>
"""

    def _header(self, title: str, subtitle: str) -> str:
        """Generate header section."""
        return f"""
        <tr>
            <td style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center;">
                <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 600;">{title}</h1>
                <p style="margin: 8px 0 0 0; color: #ffffff; font-size: 14px; opacity: 0.9;">{subtitle}</p>
            </td>
        </tr>
"""

    def _section_title(self, title: str) -> str:
        """Generate section title."""
        return f"""
        <tr>
            <td style="padding: 20px 20px 10px 20px;">
                <h2 style="margin: 0; color: {self.c['accent']}; font-size: 14px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px;">{title}</h2>
            </td>
        </tr>
"""

    def _index_row(self, items: List[dict]) -> str:
        """Generate a row of index cards."""
        cells = ""
        cell_width = 100 // len(items) if items else 25

        for item in items:
            change_str, color = self._format_change(item.get('change_percent', 0))
            cells += f"""
                <td width="{cell_width}%" style="padding: 8px; text-align: center; background-color: {self.c['bg_section']}; border-radius: 8px;">
                    <div style="color: {self.c['text_secondary']}; font-size: 11px; margin-bottom: 4px;">{item['name']}</div>
                    <div style="color: {color}; font-size: 16px; font-weight: 600;">{change_str}</div>
                </td>
"""

        return f"""
        <tr>
            <td style="padding: 0 20px 20px 20px;">
                <table cellpadding="0" cellspacing="8" border="0" width="100%">
                    <tr>{cells}</tr>
                </table>
            </td>
        </tr>
"""

    def _stock_row(self, symbol: str, name: str, price: float, change_pct: float, extra_info: str = "") -> str:
        """Generate a single stock row."""
        change_str, color = self._format_change(change_pct)
        name_truncated = name[:25] + "..." if len(name) > 25 else name

        return f"""
        <tr>
            <td style="padding: 0 20px;">
                <table cellpadding="0" cellspacing="0" border="0" width="100%" style="border-bottom: 1px solid {self.c['border']};">
                    <tr>
                        <td style="padding: 12px 0;">
                            <div style="color: {self.c['text_primary']}; font-size: 15px; font-weight: 600;">{symbol}</div>
                            <div style="color: {self.c['text_secondary']}; font-size: 12px;">{name_truncated}</div>
                        </td>
                        <td style="padding: 12px 0; text-align: right;">
                            <div style="color: {self.c['text_primary']}; font-size: 15px;">{self._format_price(price)}</div>
                            <div style="display: inline-block; padding: 2px 8px; border-radius: 4px; background-color: {color}20; color: {color}; font-size: 13px; font-weight: 600;">{change_str}</div>
                            {f'<div style="color: {self.c["text_secondary"]}; font-size: 11px; margin-top: 2px;">{extra_info}</div>' if extra_info else ''}
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
"""

    def _calendar_item(self, date_str: str, symbol: str, event: str) -> str:
        """Generate a calendar item."""
        return f"""
        <tr>
            <td style="padding: 0 20px;">
                <table cellpadding="0" cellspacing="0" border="0" width="100%" style="border-bottom: 1px solid {self.c['border']};">
                    <tr>
                        <td width="70" style="padding: 10px 0;">
                            <div style="background-color: {self.c['accent']}30; color: {self.c['accent']}; padding: 8px; border-radius: 6px; font-size: 12px; font-weight: 600; text-align: center;">{date_str}</div>
                        </td>
                        <td style="padding: 10px 0 10px 12px;">
                            <div style="color: {self.c['text_primary']}; font-size: 14px; font-weight: 600;">{symbol}</div>
                            <div style="color: {self.c['text_secondary']}; font-size: 12px;">{event}</div>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
"""

    def _news_item(self, symbol: str, title: str, source: str, link: str) -> str:
        """Generate a news item."""
        title_truncated = title[:80] + "..." if len(title) > 80 else title
        return f"""
        <tr>
            <td style="padding: 0 20px;">
                <table cellpadding="0" cellspacing="0" border="0" width="100%" style="border-bottom: 1px solid {self.c['border']};">
                    <tr>
                        <td style="padding: 12px 0;">
                            <div style="color: {self.c['accent']}; font-size: 11px; font-weight: 600; margin-bottom: 4px;">{symbol}</div>
                            <a href="{link}" style="color: {self.c['text_primary']}; font-size: 13px; text-decoration: none;">{title_truncated}</a>
                            <div style="color: {self.c['text_secondary']}; font-size: 11px; margin-top: 4px;">{source}</div>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
"""

    def _headline_item(self, title: str, source: str, link: str) -> str:
        """Generate a headline news item (no symbol badge)."""
        title_truncated = title[:90] + "..." if len(title) > 90 else title
        return f"""
        <tr>
            <td style="padding: 0 20px;">
                <table cellpadding="0" cellspacing="0" border="0" width="100%" style="border-bottom: 1px solid {self.c['border']};">
                    <tr>
                        <td style="padding: 10px 0;">
                            <a href="{link}" style="color: {self.c['text_primary']}; font-size: 13px; text-decoration: none; line-height: 1.4;">{title_truncated}</a>
                            <div style="color: {self.c['text_secondary']}; font-size: 11px; margin-top: 4px;">{source}</div>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
"""

    def _summary_box(self, stats: List[tuple]) -> str:
        """Generate a summary statistics box."""
        rows = ""
        for label, value, color in stats:
            rows += f"""
                <tr>
                    <td style="padding: 6px 0; color: {self.c['text_secondary']}; font-size: 13px;">{label}</td>
                    <td style="padding: 6px 0; text-align: right; color: {color}; font-size: 14px; font-weight: 600;">{value}</td>
                </tr>
"""

        return f"""
        <tr>
            <td style="padding: 0 20px 20px 20px;">
                <table cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color: {self.c['bg_section']}; border-radius: 8px; padding: 16px;">
                    <tr><td>
                        <table cellpadding="0" cellspacing="0" border="0" width="100%" style="padding: 12px;">
                            {rows}
                        </table>
                    </td></tr>
                </table>
            </td>
        </tr>
"""

    def _sector_performance_section(self, quotes: Dict[str, dict], change_key: str = 'change_percent') -> str:
        """Generate sector performance section with bars."""
        # Calculate sector averages
        sector_data = {}
        for symbol, data in quotes.items():
            sector = SECTOR_MAP.get(symbol, 'Other')
            if sector not in sector_data:
                sector_data[sector] = []
            sector_data[sector].append(data.get(change_key, 0))

        sector_avg = {k: sum(v)/len(v) for k, v in sector_data.items() if v}
        sorted_sectors = sorted(sector_avg.items(), key=lambda x: x[1], reverse=True)

        # Filter to top/bottom sectors with meaningful data
        notable_sectors = [s for s in sorted_sectors if abs(s[1]) >= 0.1][:8]

        if not notable_sectors:
            return ""

        rows = ""
        max_abs = max(abs(s[1]) for s in notable_sectors) if notable_sectors else 1

        for sector, avg in notable_sectors:
            color = self.c['green'] if avg > 0 else self.c['red']
            bar_width = int(min(abs(avg) / max_abs * 60, 60))  # Max 60% width
            change_str = f"+{avg:.2f}%" if avg > 0 else f"{avg:.2f}%"

            rows += f"""
                <tr>
                    <td style="padding: 8px 0; width: 120px;">
                        <span style="color: {self.c['text_primary']}; font-size: 13px;">{sector}</span>
                    </td>
                    <td style="padding: 8px 0;">
                        <div style="background-color: {color}30; height: 20px; width: {bar_width}%; border-radius: 4px; display: inline-block;"></div>
                        <span style="color: {color}; font-size: 13px; font-weight: 600; margin-left: 8px;">{change_str}</span>
                    </td>
                </tr>
"""

        return f"""
        <tr>
            <td style="padding: 0 20px 20px 20px;">
                <table cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color: {self.c['bg_section']}; border-radius: 8px;">
                    <tr><td style="padding: 16px;">
                        <table cellpadding="0" cellspacing="0" border="0" width="100%">
                            {rows}
                        </table>
                    </td></tr>
                </table>
            </td>
        </tr>
"""

    def _stocks_by_sector(self, quotes: Dict[str, dict], limit_per_sector: int = 3, change_key: str = 'change_percent') -> str:
        """Generate stocks grouped by sector showing top movers."""
        # Group stocks by sector
        by_sector = {}
        for symbol, data in quotes.items():
            sector = SECTOR_MAP.get(symbol, 'Other')
            if sector == 'Other':
                continue  # Skip uncategorized
            if sector not in by_sector:
                by_sector[sector] = []
            by_sector[sector].append(data)

        # Sort each sector by absolute change and pick top movers
        content = ""
        sectors_shown = 0

        # Sort sectors by total absolute movement
        sector_activity = {
            s: sum(abs(d.get(change_key, 0)) for d in stocks)
            for s, stocks in by_sector.items()
        }
        sorted_sectors = sorted(sector_activity.keys(), key=lambda x: sector_activity[x], reverse=True)

        for sector in sorted_sectors:
            if sectors_shown >= 6:  # Limit to 6 sectors
                break

            stocks = by_sector[sector]
            # Get top movers (by absolute change)
            movers = sorted(stocks, key=lambda x: abs(x.get(change_key, 0)), reverse=True)[:limit_per_sector]

            # Only show sector if it has meaningful movers
            if not any(abs(s.get(change_key, 0)) >= 1.0 for s in movers):
                continue

            # Sector header
            content += f"""
        <tr>
            <td style="padding: 12px 20px 4px 20px;">
                <span style="color: {self.c['accent']}; font-size: 12px; font-weight: 600; text-transform: uppercase;">{sector}</span>
            </td>
        </tr>
"""
            # Stock rows
            for stock in movers:
                change_pct = stock.get(change_key, 0)
                if abs(change_pct) < 0.5:
                    continue
                change_str, color = self._format_change(change_pct)
                content += f"""
        <tr>
            <td style="padding: 0 20px;">
                <table cellpadding="0" cellspacing="0" border="0" width="100%">
                    <tr>
                        <td style="padding: 6px 0;">
                            <span style="color: {self.c['text_primary']}; font-size: 14px; font-weight: 500;">{stock['symbol']}</span>
                        </td>
                        <td style="padding: 6px 0; text-align: right;">
                            <span style="color: {color}; font-size: 14px; font-weight: 600;">{change_str}</span>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
"""
            sectors_shown += 1

        return content

    def _footer(self) -> str:
        """Generate footer."""
        return f"""
        <tr>
            <td style="padding: 20px; text-align: center; background-color: rgba(0,0,0,0.3); border-top: 1px solid {self.c['border']};">
                <p style="margin: 0; color: {self.c['text_secondary']}; font-size: 12px;">Generated by Stock Monitor • Data from Yahoo Finance</p>
            </td>
        </tr>
"""

    def _spacer(self, height: int = 10) -> str:
        """Generate a spacer row."""
        return f'<tr><td style="height: {height}px;"></td></tr>'

    def _signal_digest_section(self, signal_digest: str) -> str:
        """Convert signal digest markdown-like text to HTML matching email style."""
        if not signal_digest:
            return ""

        import re

        lines = signal_digest.strip().split('\n')
        html_parts = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Bold headers: **Text**
            if line.startswith('**') and line.endswith('**'):
                header_text = line.strip('*').strip()
                html_parts.append(
                    f'<div style="color: {self.c["accent"]}; font-size: 14px; font-weight: 600; '
                    f'margin: 16px 0 8px 0; text-transform: uppercase; letter-spacing: 0.5px;">{header_text}</div>'
                )
            # Blockquotes: > text (insights)
            elif line.startswith('>'):
                quote_text = line.lstrip('>').strip()
                # Process inline bold
                quote_text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', quote_text)
                html_parts.append(
                    f'<div style="border-left: 3px solid {self.c["accent"]}; padding: 8px 12px; '
                    f'margin: 4px 0; background-color: {self.c["bg_section"]}; border-radius: 0 6px 6px 0; '
                    f'color: {self.c["text_primary"]}; font-size: 13px; font-style: italic;">{quote_text}</div>'
                )
            # Bullet points: * text or - text
            elif line.startswith('* ') or line.startswith('- '):
                bullet_text = line[2:].strip()
                # Process inline bold
                bullet_text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', bullet_text)
                html_parts.append(
                    f'<div style="color: {self.c["text_primary"]}; font-size: 13px; padding: 3px 0 3px 16px; '
                    f'line-height: 1.5;">&#8226; {bullet_text}</div>'
                )
            # Separator lines: ---
            elif line.startswith('---'):
                html_parts.append(
                    f'<hr style="border: none; border-top: 1px solid {self.c["border"]}; margin: 12px 0;" />'
                )
            # Regular text with possible inline formatting
            else:
                processed = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line)
                html_parts.append(
                    f'<div style="color: {self.c["text_secondary"]}; font-size: 13px; '
                    f'padding: 2px 0; line-height: 1.5;">{processed}</div>'
                )

        inner_html = '\n'.join(html_parts)

        return f"""
        <tr>
            <td style="padding: 0 20px 20px 20px;">
                <table cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color: {self.c['bg_section']}; border-radius: 8px;">
                    <tr><td style="padding: 16px;">
                        {inner_html}
                    </td></tr>
                </table>
            </td>
        </tr>
"""

    def _trends_section(self, trends_data: Dict[str, dict], max_items: int = 5) -> str:
        """
        Generate search trends section showing Google Trends data.

        Displays top movers by interest change with direction indicators.
        """
        if not trends_data:
            return ""

        # Sort by absolute interest change
        sorted_trends = sorted(
            [(symbol, data) for symbol, data in trends_data.items()],
            key=lambda x: abs(x[1].get('interest_change', 0)),
            reverse=True
        )[:max_items]

        if not sorted_trends:
            return ""

        # Direction emoji mapping
        direction_icons = {
            'surging': '🔥',
            'rising': '📈',
            'falling': '📉',
            'stable': '➡️'
        }

        rows = ""
        for symbol, data in sorted_trends:
            direction = data.get('direction', 'stable')
            icon = direction_icons.get(direction, '➡️')
            change = data.get('interest_change', 0)
            top_query = data.get('top_query', '')

            # Color based on change
            if change > 5:
                color = self.c['green']
            elif change < -5:
                color = self.c['red']
            else:
                color = self.c['neutral']

            # Format change string
            change_str = f"+{change:.0f}%" if change > 0 else f"{change:.0f}%"

            rows += f"""
            <tr>
                <td style="padding: 8px 0; border-bottom: 1px solid {self.c['border']};">
                    <table cellpadding="0" cellspacing="0" border="0" width="100%">
                        <tr>
                            <td width="30" style="font-size: 16px;">{icon}</td>
                            <td style="color: {self.c['text_primary']}; font-size: 14px; font-weight: 600;">{symbol}</td>
                            <td width="60" style="text-align: right; color: {color}; font-size: 13px; font-weight: 600;">{change_str}</td>
                            <td width="140" style="text-align: right; color: {self.c['text_secondary']}; font-size: 11px; padding-left: 10px;">{top_query[:20] if top_query else '—'}</td>
                        </tr>
                    </table>
                </td>
            </tr>
"""

        return f"""
        <tr>
            <td style="padding: 0 20px 10px 20px;">
                <table cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color: {self.c['bg_section']}; border-radius: 8px; padding: 12px;">
                    {rows}
                </table>
            </td>
        </tr>
"""

    def generate_premarket_report(self,
                                   futures: Dict[str, dict],
                                   premarket_data: Dict[str, dict],
                                   quotes: Dict[str, dict],
                                   earnings: List[dict],
                                   dividends: List[dict],
                                   news: Dict[str, List[dict]],
                                   market_news: List[dict],
                                   world_news: List[dict] = None,
                                   trends_data: Dict[str, dict] = None,
                                   signal_digest: str = None) -> str:
        """Generate pre-market morning report."""

        now = datetime.now()
        date_str = now.strftime("%A, %B %d, %Y")

        content = self._header("📈 Pre-Market Briefing", date_str)

        # World & US Headlines (NEW - first section)
        if world_news:
            content += self._section_title("🌍 World & US Headlines")
            for item in world_news[:6]:
                content += self._headline_item(item['title'], f"{item['source']} • {item['published']}", item['link'])
            content += self._spacer(10)

        # Market News (moved up)
        if market_news:
            content += self._section_title("📰 Market News")
            for item in market_news[:4]:
                content += self._headline_item(item['title'], f"{item['source']} • {item['published']}", item['link'])
            content += self._spacer(10)

        # Signal Digest (Grok-powered market voices)
        if signal_digest:
            content += self._section_title("🧠 Signal Digest")
            content += self._signal_digest_section(signal_digest)
            content += self._spacer(10)

        # Search Trends (new sentiment signal)
        if trends_data:
            content += self._section_title("🔍 Search Trends")
            content += self._trends_section(trends_data)
            content += self._spacer(10)

        # Futures
        if futures:
            content += self._section_title("Futures")
            futures_list = [{'name': d['name'], 'change_percent': d.get('change_percent', 0)} for d in futures.values()]
            content += self._index_row(futures_list)

        # Pre-market movers
        sorted_premarket = sorted(
            [(s, d) for s, d in premarket_data.items() if d.get('pre_market_change_percent')],
            key=lambda x: abs(x[1].get('pre_market_change_percent', 0)),
            reverse=True
        )

        if sorted_premarket:
            content += self._section_title("📊 Pre-Market Movers")
            for symbol, data in sorted_premarket[:12]:
                content += self._stock_row(
                    symbol,
                    data.get('name', ''),
                    data.get('pre_market_price', 0),
                    data.get('pre_market_change_percent', 0)
                )
            content += self._spacer(10)

        # Sector performance (using previous close data from quotes)
        if quotes:
            content += self._section_title("📊 Sector Performance (Prev Close)")
            content += self._sector_performance_section(quotes)

        # Upcoming earnings
        if earnings:
            content += self._section_title("📅 Upcoming Earnings")
            for e in earnings[:8]:
                date_parts = e['date'].split('-')
                date_display = f"{date_parts[1]}/{date_parts[2]}"
                content += self._calendar_item(date_display, e['symbol'], f"{e.get('name', '')} - Earnings")
            content += self._spacer(10)

        # Upcoming dividends
        if dividends:
            content += self._section_title("💰 Upcoming Ex-Dividend Dates")
            for d in dividends[:5]:
                date_parts = d['ex_date'].split('-')
                date_display = f"{date_parts[1]}/{date_parts[2]}"
                yield_str = f"Yield: {d['dividend_yield']:.2f}%" if d['dividend_yield'] else ""
                content += self._calendar_item(date_display, d['symbol'], yield_str)
            content += self._spacer(10)

        # Stock-specific news (moved to end)
        if news:
            content += self._section_title("📈 Stock News")
            news_count = 0
            for symbol, items in news.items():
                if news_count >= 5:
                    break
                for item in items[:1]:
                    content += self._news_item(symbol, item['title'], f"{item['source']} • {item['published']}", item['link'])
                    news_count += 1
                    break

        content += self._footer()

        return self._base_wrapper(content)

    def generate_postmarket_report(self,
                                    indices: Dict[str, dict],
                                    quotes: Dict[str, dict],
                                    postmarket_data: Dict[str, dict],
                                    news: Dict[str, List[dict]],
                                    market_news: List[dict] = None,
                                    world_news: List[dict] = None,
                                    trends_data: Dict[str, dict] = None,
                                    signal_digest: str = None) -> str:
        """Generate post-market closing report."""

        now = datetime.now()
        date_str = now.strftime("%A, %B %d, %Y")

        content = self._header("📊 Market Close Report", date_str)

        # World & US Headlines (like pre-market)
        if world_news:
            content += self._section_title("🌍 World & US Headlines")
            for item in world_news[:6]:
                content += self._headline_item(item['title'], f"{item['source']} • {item['published']}", item['link'])
            content += self._spacer(10)

        # Market News (like pre-market)
        if market_news:
            content += self._section_title("📰 Market News")
            for item in market_news[:4]:
                content += self._headline_item(item['title'], f"{item['source']} • {item['published']}", item['link'])
            content += self._spacer(10)

        # Signal Digest (Grok-powered market voices)
        if signal_digest:
            content += self._section_title("🧠 Signal Digest")
            content += self._signal_digest_section(signal_digest)
            content += self._spacer(10)

        # Search Trends (sentiment signal)
        if trends_data:
            content += self._section_title("🔍 Search Trends")
            content += self._trends_section(trends_data)
            content += self._spacer(10)

        # Market indices
        if indices:
            content += self._section_title("Market Indices")
            indices_list = [{'name': d['name'], 'change_percent': d.get('change_percent', 0)} for d in indices.values()]
            content += self._index_row(indices_list[:4])

        # Portfolio summary
        sorted_stocks = sorted(quotes.values(), key=lambda x: x.get('change_percent', 0), reverse=True)
        gainers = [s for s in sorted_stocks if s.get('change_percent', 0) > 0]
        losers = [s for s in sorted_stocks if s.get('change_percent', 0) < 0]
        avg_change = sum(s.get('change_percent', 0) for s in quotes.values()) / len(quotes) if quotes else 0

        content += self._section_title("📈 Watchlist Summary")
        content += self._summary_box([
            ("Gainers", str(len(gainers)), self.c['green']),
            ("Losers", str(len(losers)), self.c['red']),
            ("Avg Change", f"{avg_change:+.2f}%", self.c['green'] if avg_change > 0 else self.c['red']),
        ])

        # Sector performance
        content += self._section_title("📊 Sector Performance")
        content += self._sector_performance_section(quotes)

        # Top gainers
        content += self._section_title("🚀 Top Gainers")
        for stock in gainers[:8]:
            vol_ratio = stock.get('volume_ratio', 1)
            extra = f"{vol_ratio:.1f}x vol" if vol_ratio > 1.5 else ""
            content += self._stock_row(
                stock['symbol'],
                stock.get('name', ''),
                stock.get('price', 0),
                stock.get('change_percent', 0),
                extra
            )
        content += self._spacer(10)

        # Top losers
        losers_sorted = sorted(losers, key=lambda x: x.get('change_percent', 0))
        content += self._section_title("📉 Top Losers")
        for stock in losers_sorted[:8]:
            vol_ratio = stock.get('volume_ratio', 1)
            extra = f"{vol_ratio:.1f}x vol" if vol_ratio > 1.5 else ""
            content += self._stock_row(
                stock['symbol'],
                stock.get('name', ''),
                stock.get('price', 0),
                stock.get('change_percent', 0),
                extra
            )
        content += self._spacer(10)

        # After-hours movers
        if postmarket_data:
            sorted_ah = sorted(
                [(s, d) for s, d in postmarket_data.items() if d.get('post_market_change_percent')],
                key=lambda x: abs(x[1].get('post_market_change_percent', 0)),
                reverse=True
            )[:8]

            if sorted_ah:
                content += self._section_title("🌙 After-Hours Movement")
                for symbol, data in sorted_ah:
                    content += self._stock_row(
                        symbol,
                        data.get('name', ''),
                        data.get('post_market_price', 0),
                        data.get('post_market_change_percent', 0)
                    )
                content += self._spacer(10)

        # Movers by sector
        sector_content = self._stocks_by_sector(quotes)
        if sector_content:
            content += self._section_title("🏢 Movers by Sector")
            content += sector_content
            content += self._spacer(10)

        # Stock-specific news (like pre-market)
        if news:
            content += self._section_title("📈 Stock News")
            news_count = 0
            for symbol, items in news.items():
                if news_count >= 5:
                    break
                for item in items[:1]:
                    content += self._news_item(symbol, item['title'], f"{item['source']} • {item['published']}", item['link'])
                    news_count += 1
                    break
            content += self._spacer(10)

        content += self._footer()

        return self._base_wrapper(content)

    def generate_weekly_report(self,
                                weekly_data: Dict[str, dict],
                                earnings_next_week: List[dict],
                                dividends_next_week: List[dict]) -> str:
        """Generate weekly summary report."""

        now = datetime.now()
        week_end = now.strftime("%B %d, %Y")
        week_start = (now - timedelta(days=7)).strftime("%B %d")

        content = self._header("📈 Weekly Summary", f"Week of {week_start} - {week_end}")

        # Sort by weekly performance
        sorted_weekly = sorted(
            weekly_data.values(),
            key=lambda x: x.get('week_change_percent', 0),
            reverse=True
        )

        week_gainers = [s for s in sorted_weekly if s.get('week_change_percent', 0) > 0]
        week_losers = [s for s in sorted_weekly if s.get('week_change_percent', 0) < 0]
        avg_change = sum(s.get('week_change_percent', 0) for s in weekly_data.values()) / len(weekly_data) if weekly_data else 0

        # Overview
        content += self._section_title("📊 Week Overview")
        content += self._summary_box([
            ("Total Stocks", str(len(weekly_data)), self.c['text_primary']),
            ("Week Gainers", str(len(week_gainers)), self.c['green']),
            ("Week Losers", str(len(week_losers)), self.c['red']),
            ("Avg Performance", f"{avg_change:+.2f}%", self.c['green'] if avg_change > 0 else self.c['red']),
        ])

        # Sector performance for the week
        content += self._section_title("📊 Sector Performance")
        content += self._sector_performance_section(weekly_data, change_key='week_change_percent')

        # Top gainers
        content += self._section_title("🚀 Week's Top Gainers")
        for stock in week_gainers[:8]:
            content += self._stock_row(
                stock['symbol'],
                "",
                stock.get('end_price', 0),
                stock.get('week_change_percent', 0)
            )
        content += self._spacer(10)

        # Top losers
        week_losers_sorted = sorted(week_losers, key=lambda x: x.get('week_change_percent', 0))
        content += self._section_title("📉 Week's Biggest Declines")
        for stock in week_losers_sorted[:8]:
            content += self._stock_row(
                stock['symbol'],
                "",
                stock.get('end_price', 0),
                stock.get('week_change_percent', 0)
            )
        content += self._spacer(10)

        # Movers by sector
        sector_content = self._stocks_by_sector(weekly_data, change_key='week_change_percent')
        if sector_content:
            content += self._section_title("🏢 Movers by Sector")
            content += sector_content
            content += self._spacer(10)

        # Earnings next week
        if earnings_next_week:
            content += self._section_title("📅 Earnings Next Week")
            for e in earnings_next_week[:8]:
                date_parts = e['date'].split('-')
                date_display = f"{date_parts[1]}/{date_parts[2]}"
                content += self._calendar_item(date_display, e['symbol'], e.get('name', ''))
            content += self._spacer(10)

        # Dividends next week
        if dividends_next_week:
            content += self._section_title("💰 Ex-Dividend Dates Next Week")
            for d in dividends_next_week[:5]:
                date_parts = d['ex_date'].split('-')
                date_display = f"{date_parts[1]}/{date_parts[2]}"
                yield_str = f"Yield: {d['dividend_yield']:.2f}%" if d['dividend_yield'] else ""
                content += self._calendar_item(date_display, d['symbol'], yield_str)

        content += self._footer()

        return self._base_wrapper(content)


if __name__ == "__main__":
    # Test the email generator
    generator = EmailGenerator()

    # Test with mock data
    test_futures = {
        'ES=F': {'name': 'S&P 500', 'change_percent': 0.36},
        'NQ=F': {'name': 'NASDAQ', 'change_percent': 0.52},
        'YM=F': {'name': 'Dow', 'change_percent': 0.22},
        'RTY=F': {'name': 'Russell', 'change_percent': 0.38},
    }

    test_premarket = {
        'NVDA': {'symbol': 'NVDA', 'name': 'NVIDIA Corporation', 'pre_market_price': 145.50, 'pre_market_change_percent': 4.2},
        'TSLA': {'symbol': 'TSLA', 'name': 'Tesla, Inc.', 'pre_market_price': 248.20, 'pre_market_change_percent': -1.5},
    }

    html = generator.generate_premarket_report(
        futures=test_futures,
        premarket_data=test_premarket,
        quotes={},
        earnings=[{'symbol': 'INTC', 'name': 'Intel', 'date': '2026-01-22'}],
        dividends=[],
        news={},
        market_news=[]
    )

    # Save test output
    with open('test_email.html', 'w') as f:
        f.write(html)

    print("Test email saved to test_email.html")
