"""
Signal Fetcher Module
=====================
Fetches recent content from trusted market voices for the daily signal digest.
Uses web scraping via Google search and Grok for X/Twitter content.
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


# Trusted market voices configuration
SIGNAL_SOURCES = {
    'warren_buffett': {
        'name': 'Warren Buffett / Berkshire Hathaway',
        'search_terms': ['Warren Buffett', 'Berkshire Hathaway commentary'],
        'platforms': ['web'],
    },
    'josh_brown': {
        'name': 'Josh Brown',
        'search_terms': ['Josh Brown Ritholtz', 'The Compound and Friends'],
        'twitter_handle': 'ReformedBroker',
        'platforms': ['web', 'twitter'],
    },
    'joseph_carlson': {
        'name': 'Joseph Carlson',
        'search_terms': ['Joseph Carlson portfolio', 'Joseph Carlson YouTube'],
        'platforms': ['web', 'youtube'],
    },
    'tear_representative': {
        'name': 'TearRepresentative56',
        'search_terms': ['TearRepresentative56 reddit tradingedge'],
        'reddit_user': 'TearRepresentative56',
        'subreddit': 'tradingedge',
        'platforms': ['reddit'],
    },
    'alex_green': {
        'name': 'Alex Green',
        'search_terms': ['Alex Green Oxford Club', 'Oxford Communiqué'],
        'platforms': ['web'],
    },
    'cathie_wood': {
        'name': 'Cathie Wood',
        'search_terms': ['Cathie Wood ARK Invest', 'ARK daily trades'],
        'twitter_handle': 'CathieDWood',
        'platforms': ['web', 'twitter'],
    },
    'elliant_capital': {
        'name': 'Elliant Capital',
        'search_terms': ['Elliant Capital market'],
        'twitter_handle': 'ElliantCapital',
        'platforms': ['twitter'],
    },
    'reformed_trader': {
        'name': 'Reformed Trader',
        'search_terms': ['Reformed Trader market'],
        'twitter_handle': 'reformedtrader',
        'platforms': ['web', 'twitter'],
    },
}


class SignalFetcher:
    """Fetches content from trusted market voices for signal digest."""

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    def __init__(self, xai_api_key: str = None):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.xai_api_key = xai_api_key or os.environ.get('XAI_API_KEY')

    def _get_time_window(self, mode: str) -> tuple:
        """Get the time window based on mode (PRE_MARKET or POST_CLOSE)."""
        now = datetime.now()

        if mode == 'PRE_MARKET':
            # Last 12-36 hours
            start = now - timedelta(hours=36)
            end = now
        else:  # POST_CLOSE
            # Last 12-24 hours
            start = now - timedelta(hours=24)
            end = now

        return start, end

    def _search_google_news(self, query: str, hours_back: int = 36) -> List[dict]:
        """Search Google News RSS for recent content."""
        results = []

        try:
            # Add time filter to query
            encoded_query = quote(f'{query} when:2d')
            url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"

            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                logger.warning(f"Google News search failed: HTTP {response.status_code}")
                return results

            feed = feedparser.parse(response.text)
            cutoff = datetime.now() - timedelta(hours=hours_back)

            for entry in feed.entries[:5]:
                published = entry.get('published_parsed')
                if published:
                    pub_date = datetime(*published[:6])
                    if pub_date < cutoff:
                        continue
                else:
                    pub_date = datetime.now()

                # Clean title
                title = entry.get('title', '')
                source = ''
                if ' - ' in title:
                    title, source = title.rsplit(' - ', 1)

                results.append({
                    'title': title,
                    'source': source,
                    'link': entry.get('link', ''),
                    'published': pub_date.strftime('%Y-%m-%d %H:%M'),
                    'published_datetime': pub_date,
                    'summary': entry.get('summary', ''),
                })

        except Exception as e:
            logger.warning(f"Error searching Google News for '{query}': {e}")

        return results

    def _search_reddit(self, subreddit: str, user: str, hours_back: int = 36) -> List[dict]:
        """Search Reddit for user posts in a subreddit."""
        results = []

        try:
            # Reddit JSON API (no auth needed for public posts)
            url = f"https://www.reddit.com/r/{subreddit}/search.json"
            params = {
                'q': f'author:{user}',
                'sort': 'new',
                'restrict_sr': 'on',
                't': 'week',
                'limit': 10
            }

            response = self.session.get(url, params=params, timeout=10)
            if response.status_code != 200:
                logger.warning(f"Reddit search failed: HTTP {response.status_code}")
                return results

            data = response.json()
            cutoff = datetime.now() - timedelta(hours=hours_back)

            for post in data.get('data', {}).get('children', []):
                post_data = post.get('data', {})

                # Check timestamp
                created = post_data.get('created_utc', 0)
                pub_date = datetime.fromtimestamp(created)
                if pub_date < cutoff:
                    continue

                results.append({
                    'title': post_data.get('title', ''),
                    'source': f"r/{subreddit}",
                    'link': f"https://reddit.com{post_data.get('permalink', '')}",
                    'published': pub_date.strftime('%Y-%m-%d %H:%M'),
                    'published_datetime': pub_date,
                    'summary': post_data.get('selftext', '')[:500],
                    'author': post_data.get('author', ''),
                })

        except Exception as e:
            logger.warning(f"Error searching Reddit for u/{user}: {e}")

        return results

    def _query_grok_for_twitter(self, handles: List[str], mode: str) -> Optional[str]:
        """Use Grok to get recent Twitter content from specific handles."""
        if not self.xai_api_key:
            logger.warning("XAI_API_KEY not set - cannot fetch Twitter content via Grok")
            return None

        handles_str = ', '.join([f'@{h}' for h in handles])
        time_window = "last 12-36 hours" if mode == 'PRE_MARKET' else "last 12-24 hours"

        prompt = f"""Find recent posts from these X/Twitter accounts from the {time_window}:
{handles_str}

For each account with recent activity, provide:
1. The account handle
2. A brief summary of their recent posts/threads (ignore replies)
3. Any specific market insights, stock mentions, or positioning commentary
4. The approximate date/time of their posts

Focus on original analytical content, not retweets or casual posts.
Skip accounts with no meaningful recent activity.
Format as structured text that can be parsed."""

        try:
            response = requests.post(
                "https://api.x.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.xai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "grok-3-latest",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 1000,
                    "temperature": 0.3
                },
                timeout=30
            )

            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content']
            else:
                logger.warning(f"Grok API error: {response.status_code}")

        except Exception as e:
            logger.warning(f"Error querying Grok for Twitter: {e}")

        return None

    def fetch_all_signals(self, mode: str = 'PRE_MARKET') -> Dict[str, dict]:
        """
        Fetch content from all signal sources.

        Args:
            mode: 'PRE_MARKET' or 'POST_CLOSE'

        Returns:
            Dict with source key and their fetched content
        """
        hours_back = 36 if mode == 'PRE_MARKET' else 24
        all_signals = {}

        # Collect Twitter handles for batch query
        twitter_handles = []

        for source_key, source_config in SIGNAL_SOURCES.items():
            logger.info(f"Fetching signals from {source_config['name']}...")
            source_content = {
                'name': source_config['name'],
                'web_results': [],
                'reddit_results': [],
                'twitter_content': None,
            }

            # Web search
            if 'web' in source_config.get('platforms', []):
                for term in source_config.get('search_terms', []):
                    results = self._search_google_news(term, hours_back)
                    source_content['web_results'].extend(results)
                    time.sleep(0.5)  # Rate limiting

            # Reddit search
            if 'reddit' in source_config.get('platforms', []):
                reddit_user = source_config.get('reddit_user')
                subreddit = source_config.get('subreddit')
                if reddit_user and subreddit:
                    results = self._search_reddit(subreddit, reddit_user, hours_back)
                    source_content['reddit_results'] = results
                    time.sleep(0.5)

            # Collect Twitter handle for batch query
            if 'twitter' in source_config.get('platforms', []):
                handle = source_config.get('twitter_handle')
                if handle:
                    twitter_handles.append(handle)

            all_signals[source_key] = source_content

        # Batch query Grok for all Twitter handles
        if twitter_handles:
            logger.info(f"Fetching Twitter signals via Grok for {len(twitter_handles)} handles...")
            twitter_content = self._query_grok_for_twitter(twitter_handles, mode)

            if twitter_content:
                # Parse and distribute Twitter content to respective sources
                for source_key, source_config in SIGNAL_SOURCES.items():
                    handle = source_config.get('twitter_handle')
                    if handle and handle.lower() in twitter_content.lower():
                        # Extract relevant portion for this handle
                        all_signals[source_key]['twitter_content'] = twitter_content

        return all_signals

    def format_signals_for_analysis(self, signals: Dict[str, dict], mode: str) -> str:
        """
        Format fetched signals into a text block for Claude analysis.

        Args:
            signals: Dict of fetched signals from fetch_all_signals()
            mode: 'PRE_MARKET' or 'POST_CLOSE'

        Returns:
            Formatted text string for Claude prompt
        """
        formatted = f"MODE: {mode}\n"
        formatted += f"FETCH TIME: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        formatted += "=" * 60 + "\n\n"

        for source_key, content in signals.items():
            name = content['name']
            formatted += f"### {name} ###\n\n"

            # Web results
            if content['web_results']:
                formatted += "Web/News:\n"
                for item in content['web_results'][:3]:
                    formatted += f"- [{item['published']}] {item['title']}\n"
                    if item.get('summary'):
                        formatted += f"  Summary: {item['summary'][:200]}...\n"
                formatted += "\n"

            # Reddit results
            if content['reddit_results']:
                formatted += "Reddit Posts:\n"
                for item in content['reddit_results'][:2]:
                    formatted += f"- [{item['published']}] {item['title']}\n"
                    if item.get('summary'):
                        formatted += f"  Content: {item['summary'][:300]}...\n"
                formatted += "\n"

            # Twitter content
            if content.get('twitter_content'):
                formatted += "Twitter/X Activity:\n"
                formatted += f"{content['twitter_content']}\n\n"

            # No content found
            if not (content['web_results'] or content['reddit_results'] or content.get('twitter_content')):
                formatted += "(No recent content found)\n\n"

            formatted += "-" * 40 + "\n\n"

        return formatted


if __name__ == "__main__":
    # Test the signal fetcher
    logging.basicConfig(level=logging.INFO)

    fetcher = SignalFetcher()

    print("Testing signal fetcher (PRE_MARKET mode)...")
    signals = fetcher.fetch_all_signals('PRE_MARKET')

    print("\nFormatted signals:")
    formatted = fetcher.format_signals_for_analysis(signals, 'PRE_MARKET')
    print(formatted[:2000])
