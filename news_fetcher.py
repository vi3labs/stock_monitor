"""
News Fetcher Module
===================
Fetches stock news from free sources including Yahoo Finance and RSS feeds.
"""

import os
import requests
from bs4 import BeautifulSoup
import feedparser
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
import time
import re
from urllib.parse import quote

logger = logging.getLogger(__name__)


class NewsFetcher:
    """Fetches news from multiple free sources."""
    
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    def __init__(self, max_news_per_stock: int = 3):
        self.max_news = max_news_per_stock
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
    
    def get_yahoo_news(self, symbol: str) -> List[dict]:
        """
        Get news from Yahoo Finance for a specific stock.
        """
        news_items = []
        
        try:
            # Yahoo Finance news RSS feed
            url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"
            
            feed = feedparser.parse(url)
            
            for entry in feed.entries[:self.max_news]:
                published = entry.get('published_parsed')
                if published:
                    pub_date = datetime(*published[:6])
                else:
                    pub_date = datetime.now()
                
                news_items.append({
                    'symbol': symbol,
                    'title': entry.get('title', ''),
                    'summary': entry.get('summary', '')[:200] + '...' if len(entry.get('summary', '')) > 200 else entry.get('summary', ''),
                    'link': entry.get('link', ''),
                    'source': 'Yahoo Finance',
                    'published': pub_date.strftime('%Y-%m-%d %H:%M'),
                    'published_datetime': pub_date,
                })
                
        except Exception as e:
            logger.warning(f"Error fetching Yahoo news for {symbol}: {e}")
        
        return news_items
    
    def get_finviz_news(self, symbol: str) -> List[dict]:
        """
        Get news from Finviz for a specific stock.
        """
        news_items = []
        
        try:
            url = f"https://finviz.com/quote.ashx?t={symbol}"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'lxml')
                
                # Find news table
                news_table = soup.find('table', {'id': 'news-table'})
                
                if news_table:
                    rows = news_table.find_all('tr')
                    current_date = datetime.now().strftime('%Y-%m-%d')
                    
                    for row in rows[:self.max_news * 2]:  # Get more to filter
                        cells = row.find_all('td')
                        if len(cells) >= 2:
                            date_cell = cells[0].text.strip()
                            news_cell = cells[1]
                            
                            link_tag = news_cell.find('a')
                            if link_tag:
                                title = link_tag.text.strip()
                                link = link_tag.get('href', '')
                                source = news_cell.find('span')
                                source_text = source.text.strip() if source else 'Finviz'
                                
                                # Parse date
                                if 'Today' in date_cell or ':' in date_cell:
                                    pub_date = datetime.now()
                                else:
                                    try:
                                        pub_date = datetime.strptime(date_cell.split()[0], '%b-%d')
                                        pub_date = pub_date.replace(year=datetime.now().year)
                                    except:
                                        pub_date = datetime.now()
                                
                                news_items.append({
                                    'symbol': symbol,
                                    'title': title,
                                    'summary': '',
                                    'link': link,
                                    'source': source_text,
                                    'published': pub_date.strftime('%Y-%m-%d %H:%M'),
                                    'published_datetime': pub_date,
                                })
                        
                        if len(news_items) >= self.max_news:
                            break
                            
        except Exception as e:
            logger.warning(f"Error fetching Finviz news for {symbol}: {e}")
        
        return news_items
    
    def get_google_news_rss(self, symbol: str, company_name: str = None) -> List[dict]:
        """
        Get news from Google News RSS feed.
        """
        news_items = []
        
        try:
            search_term = f"{symbol} stock" if not company_name else f"{company_name} {symbol}"
            encoded_term = quote(search_term)
            url = f"https://news.google.com/rss/search?q={encoded_term}&hl=en-US&gl=US&ceid=US:en"
            
            feed = feedparser.parse(url)
            
            for entry in feed.entries[:self.max_news]:
                published = entry.get('published_parsed')
                if published:
                    pub_date = datetime(*published[:6])
                else:
                    pub_date = datetime.now()
                
                # Only include recent news (last 24 hours)
                if (datetime.now() - pub_date).days <= 1:
                    # Clean up title (Google News adds source at end)
                    title = entry.get('title', '')
                    if ' - ' in title:
                        title = title.rsplit(' - ', 1)[0]
                    
                    news_items.append({
                        'symbol': symbol,
                        'title': title,
                        'summary': '',
                        'link': entry.get('link', ''),
                        'source': 'Google News',
                        'published': pub_date.strftime('%Y-%m-%d %H:%M'),
                        'published_datetime': pub_date,
                    })
                    
        except Exception as e:
            logger.warning(f"Error fetching Google news for {symbol}: {e}")
        
        return news_items
    
    def get_all_news_for_symbol(self, symbol: str, company_name: str = None) -> List[dict]:
        """
        Get news from all sources for a symbol, deduplicated and sorted.
        """
        all_news = []
        
        # Get from multiple sources
        all_news.extend(self.get_yahoo_news(symbol))
        
        # Add delay to avoid rate limiting
        time.sleep(0.5)
        
        all_news.extend(self.get_finviz_news(symbol))
        
        # Deduplicate by title similarity
        seen_titles = set()
        unique_news = []
        
        for item in all_news:
            # Create a simplified title for comparison
            simple_title = re.sub(r'[^\w\s]', '', item['title'].lower())[:50]
            
            if simple_title not in seen_titles:
                seen_titles.add(simple_title)
                unique_news.append(item)
        
        # Sort by date (most recent first)
        unique_news.sort(key=lambda x: x.get('published_datetime', datetime.min), reverse=True)
        
        return unique_news[:self.max_news]
    
    def get_news_for_watchlist(self, symbols: List[str], symbol_names: Dict[str, str] = None) -> Dict[str, List[dict]]:
        """
        Get news for all symbols in watchlist.
        Returns dict with symbol as key and list of news items as value.
        """
        all_news = {}
        symbol_names = symbol_names or {}
        
        for symbol in symbols:
            logger.info(f"Fetching news for {symbol}...")
            news = self.get_all_news_for_symbol(symbol, symbol_names.get(symbol))
            if news:
                all_news[symbol] = news
            
            # Rate limiting
            time.sleep(0.3)
        
        return all_news
    
    def get_market_news(self) -> List[dict]:
        """
        Get general market news.
        """
        news_items = []
        
        try:
            # Yahoo Finance market news RSS
            url = "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC&region=US&lang=en-US"
            feed = feedparser.parse(url)
            
            for entry in feed.entries[:5]:
                published = entry.get('published_parsed')
                if published:
                    pub_date = datetime(*published[:6])
                else:
                    pub_date = datetime.now()
                
                news_items.append({
                    'title': entry.get('title', ''),
                    'summary': entry.get('summary', '')[:200],
                    'link': entry.get('link', ''),
                    'source': 'Yahoo Finance',
                    'published': pub_date.strftime('%Y-%m-%d %H:%M'),
                })
                
        except Exception as e:
            logger.warning(f"Error fetching market news: {e}")
        
        return news_items
    
    def filter_significant_news(self, news_dict: Dict[str, List[dict]], 
                                 movers: List[str]) -> Dict[str, List[dict]]:
        """
        Filter news to prioritize stocks that are big movers.
        """
        significant = {}
        
        # First add news for movers
        for symbol in movers:
            if symbol in news_dict:
                significant[symbol] = news_dict[symbol]
        
        # Then add others with news
        for symbol, news in news_dict.items():
            if symbol not in significant and news:
                significant[symbol] = news
        
        return significant


class GrokNewsFetcher:
    """
    Fetches real-time market sentiment and news from Grok (xAI) with X integration.
    Uses OpenAI-compatible API.
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get('XAI_API_KEY')
        self.base_url = "https://api.x.ai/v1"
        self.model = "grok-3-latest"

        if not self.api_key:
            logger.warning("XAI_API_KEY not set - Grok features disabled")

    def _query_grok(self, prompt: str, max_tokens: int = 500) -> Optional[str]:
        """Query Grok API using requests (OpenAI-compatible endpoint)."""
        if not self.api_key:
            return None

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": max_tokens,
                    "temperature": 0.3
                },
                timeout=30
            )

            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content']
            else:
                logger.warning(f"Grok API error: {response.status_code} - {response.text}")

        except Exception as e:
            logger.warning(f"Error querying Grok: {e}")

        return None

    def get_market_sentiment(self) -> Optional[dict]:
        """Get real-time market sentiment summary from X/social data."""
        prompt = """Based on current X/Twitter discussions and market sentiment, provide a brief summary:

1. Overall market mood (bullish/bearish/mixed)
2. Top 3-5 trending stock tickers being discussed
3. Any breaking news or catalysts moving markets
4. Key sentiment drivers

Keep it concise - bullet points preferred. Focus on actionable info."""

        response = self._query_grok(prompt, max_tokens=400)

        if response:
            return {
                'source': 'Grok/X',
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'content': response
            }
        return None

    def get_stock_buzz(self, symbols: List[str]) -> Optional[dict]:
        """Get X buzz/sentiment for specific stocks."""
        symbols_str = ', '.join(symbols[:10])  # Limit to 10 symbols

        prompt = f"""For these stocks: {symbols_str}

Summarize what X/Twitter is saying about each (if discussed):
- Sentiment (bullish/bearish/neutral)
- Key topics or news being discussed
- Notable accounts or influencers mentioning them

Skip stocks with no significant discussion. Be concise."""

        response = self._query_grok(prompt, max_tokens=600)

        if response:
            return {
                'source': 'Grok/X',
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'symbols': symbols,
                'content': response
            }
        return None

    def get_premarket_movers_sentiment(self) -> Optional[dict]:
        """Get sentiment on pre-market movers."""
        prompt = """What stocks are moving in pre-market trading right now according to X discussions?

List top movers with:
- Ticker and direction (up/down)
- Why it's moving (news, earnings, etc.)
- X sentiment on the move

Focus on significant moves (>3%) with social buzz."""

        response = self._query_grok(prompt, max_tokens=500)

        if response:
            return {
                'source': 'Grok/X',
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'content': response
            }
        return None


class EarningsNewsFetcher:
    """Fetches earnings-related news and analysis."""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
    
    def get_earnings_surprises(self, symbol: str) -> Optional[dict]:
        """
        Get recent earnings surprise data if available.
        """
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            
            # Get earnings history
            earnings = ticker.earnings_history
            
            if earnings is not None and not earnings.empty:
                latest = earnings.iloc[-1]
                return {
                    'symbol': symbol,
                    'eps_estimate': latest.get('epsEstimate'),
                    'eps_actual': latest.get('epsActual'),
                    'surprise': latest.get('surprise'),
                    'surprise_percent': latest.get('surprisePercent'),
                }
        except Exception as e:
            logger.warning(f"Error fetching earnings surprise for {symbol}: {e}")
        
        return None


class FDACalendarFetcher:
    """
    Fetches FDA calendar events for biotech stocks.
    Note: This is a simplified implementation. For production,
    consider using a paid API like BioPharmCatalyst.
    """
    
    # Known biotech stocks from watchlist that might have FDA events
    BIOTECH_SYMBOLS = ['PRME']  # Add more as needed
    
    def get_fda_calendar(self, symbols: List[str]) -> List[dict]:
        """
        Get upcoming FDA events for biotech stocks.
        This is a placeholder - real implementation would need
        a specialized data source.
        """
        events = []
        
        biotech_in_watchlist = [s for s in symbols if s in self.BIOTECH_SYMBOLS]
        
        if biotech_in_watchlist:
            logger.info("FDA calendar checking is enabled but requires manual updates or paid API")
            # In a real implementation, you'd fetch from:
            # - BioPharmCatalyst API
            # - FDA RSS feeds
            # - SEC filings
        
        return events


if __name__ == "__main__":
    # Test the news fetcher
    logging.basicConfig(level=logging.INFO)
    
    fetcher = NewsFetcher(max_news_per_stock=3)
    
    print("Testing Yahoo Finance news...")
    news = fetcher.get_yahoo_news('NVDA')
    for item in news:
        print(f"  - {item['title'][:60]}...")
    
    print("\nTesting Finviz news...")
    news = fetcher.get_finviz_news('TSLA')
    for item in news:
        print(f"  - {item['title'][:60]}...")
    
    print("\nTesting market news...")
    market_news = fetcher.get_market_news()
    for item in market_news:
        print(f"  - {item['title'][:60]}...")

    print("\nTesting Grok market sentiment...")
    grok = GrokNewsFetcher()
    if grok.api_key:
        sentiment = grok.get_market_sentiment()
        if sentiment:
            print(f"  Grok sentiment ({sentiment['timestamp']}):")
            print(f"  {sentiment['content'][:200]}...")
    else:
        print("  Skipped - XAI_API_KEY not set")
