"""
Signal Analyzer Module
======================
Uses Grok (xAI) to analyze fetched content and generate the daily signal digest.
"""

import os
import json
import requests
from datetime import datetime
from typing import Dict, Optional, Union
import logging

logger = logging.getLogger(__name__)

# The full signal digest prompt template
SIGNAL_DIGEST_PROMPT = """You are generating a daily market signal digest for an investor-focused email newsletter.

TIME FLAG
Current mode: {mode}
Use this flag to determine what to search for, how to interpret it, and how to frame insights.

CORE TASK
Analyze recent content from the following trusted market voices:
* Warren Buffett / Berkshire Hathaway (only if new commentary exists)
* Josh Brown (Ritholtz Wealth Management, The Compound & Friends)
* Joseph Carlson (YouTube portfolio updates)
* TearRepresentative56 (r/tradingedge posts)
* Alex Green (Oxford Communiqué / Oxford Club commentary)
* Cathie Wood (ARK Invest commentary or daily trades)
* Elliant Capital (X / Twitter posts or threads)
* Reformed Trader (X / Twitter posts or blog)

FETCHED CONTENT TO ANALYZE:
{fetched_content}

SOURCE RULES (ALWAYS APPLY)
* Prefer original commentary, not scraped headlines
* X (Twitter): original posts or threads only (no replies)
* Reddit: original analytical posts only (no comments)
* Ignore hype language, price targets, or day-trading calls
* Include stock mentions only if they support a broader insight

MODE-SPECIFIC BEHAVIOR
IF PRE_MARKET:
* Time window: last 12–36 hours
* Ignore intraday price action (market not open)
* Focus on: • overnight macro developments • liquidity, positioning, or risk framing • expectations, uncertainty, and scenarios
* Avoid definitive conclusions; use setup language
Insight framing: "What matters today" / "What to watch" / "What could surprise"

IF POST_CLOSE:
* Time window: last 12–24 hours
* Ignore raw news unless interpreted by the person
* Focus on: • why markets moved (or didn't) • confirmation or rejection of narratives • regime signals (trend, breadth, liquidity) • behavioral insights
* Emphasize meaning over movement
Insight framing: "What changed" / "What held" / "What failed"

OUTPUT FORMAT (STRICT)
For each person with meaningful signal, return:
Name: [Name]
Source: [Platform]
Date: [Date]
Insight: [One-sentence insight, max 25 words]
Market Regime: [Bull / Bear / Sideways]
Tone: [Cautious / Neutral / Constructive]
{"What to watch today: [1 phrase]" if PRE_MARKET else "Expectation result: [Confirm / Contradict / Mixed]"}

Omit any person with no meaningful signal.

FINAL SYNTHESIS (REQUIRED)
If PRE_MARKET:
"Pre-Market Focus"
* Key risk: [one phrase]
* Key theme: [one phrase]
* Invalidation condition: [one phrase]

If POST_CLOSE:
"What Changed Today?"
* Confirmed theme: [one phrase]
* Weakened narrative: [one phrase]
* Open question: [one phrase]

CROSS-SIGNAL CHECK
Add a section titled: "Cross-Signals"
List any themes or insights independently mentioned by 2 or more of these voices.
Only include genuine overlap — not generic market commentary.
"""


class SignalAnalyzer:
    """Analyzes market signals using Grok."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get('XAI_API_KEY')
        self.base_url = "https://api.x.ai/v1"
        self.model = "grok-3-latest"

        if not self.api_key:
            logger.warning("XAI_API_KEY not set - Signal analysis disabled")

    def analyze_signals(self, fetched_content: str, mode: str) -> Optional[str]:
        """
        Analyze fetched signals and generate the digest.

        Args:
            fetched_content: Formatted string of fetched signals from SignalFetcher
            mode: 'PRE_MARKET' or 'POST_CLOSE'

        Returns:
            Formatted signal digest text, or None if analysis fails
        """
        if not self.api_key:
            return None

        prompt = SIGNAL_DIGEST_PROMPT.format(
            mode=mode,
            fetched_content=fetched_content
        )

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
                    "max_tokens": 2000,
                    "temperature": 0.3
                },
                timeout=60
            )

            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content']
            else:
                logger.error(f"Grok API error: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.error(f"Error analyzing signals with Grok: {e}")
            return None

    def generate_full_digest(self, mode: str) -> Optional[Union[dict, str]]:
        """
        Convenience method that does full fetch + analyze in one call via Grok.
        Grok has real-time X access so it can fetch Twitter content directly.

        Args:
            mode: 'PRE_MARKET' or 'POST_CLOSE'

        Returns:
            Structured dict with voices/synthesis/cross_signals, or raw string as fallback
        """
        if not self.api_key:
            return None

        time_window = "last 12-36 hours" if mode == 'PRE_MARKET' else "last 12-24 hours"
        watch_field = "watch_or_result"

        # Single prompt that asks Grok to both fetch and analyze
        prompt = f"""You are generating a daily market signal digest for an investor-focused email newsletter.

Current mode: {mode}
Time window: {time_window}
Current time: {datetime.now().strftime('%Y-%m-%d %H:%M')} EST

TASK: Search for and analyze recent content from these trusted market voices:
1. Warren Buffett / Berkshire Hathaway (only if new commentary exists)
2. Josh Brown (@ReformedBroker, Ritholtz Wealth, The Compound & Friends)
3. Joseph Carlson (YouTube portfolio updates)
4. TearRepresentative56 (r/tradingedge posts on Reddit)
5. Alex Green (Oxford Communiqué / Oxford Club)
6. Cathie Wood (@CathieDWood, ARK Invest commentary or daily trades)
7. Elliant Capital (@ElliantCapital on X)
8. Reformed Trader (@reformedtrader on X)

SOURCE RULES:
* X (Twitter): original posts or threads only (no replies)
* Reddit: original analytical posts only (no comments)
* Ignore hype language, price targets, or day-trading calls
* Include stock mentions only if they support a broader insight

{"PRE_MARKET FOCUS:" if mode == 'PRE_MARKET' else "POST_CLOSE FOCUS:"}
{"* Ignore intraday price action (market not open)" if mode == 'PRE_MARKET' else "* Ignore raw news unless interpreted by the person"}
{"* Focus on: overnight macro, liquidity/positioning, risk framing, scenarios" if mode == 'PRE_MARKET' else "* Focus on: why markets moved, narrative confirmation/rejection, regime signals"}
{"* Use setup language, avoid definitive conclusions" if mode == 'PRE_MARKET' else "* Emphasize meaning over movement"}

Omit anyone with no meaningful recent signal.

Return ONLY valid JSON matching this schema (no markdown, no extra text):
{{
  "voices": [
    {{
      "name": "string",
      "source": "string (platform name)",
      "date": "string (YYYY-MM-DD or relative like 'today')",
      "insight": "string (max 25 words)",
      "regime": "Bull | Bear | Sideways",
      "tone": "Cautious | Neutral | Constructive",
      "watch_or_result": "string ({'what to watch phrase' if mode == 'PRE_MARKET' else 'Confirm / Contradict / Mixed + brief note'})"
    }}
  ],
  "synthesis": {{
    "key_risk_or_confirmed": "string ({'key risk phrase' if mode == 'PRE_MARKET' else 'confirmed theme'})",
    "key_theme_or_weakened": "string ({'key theme phrase' if mode == 'PRE_MARKET' else 'weakened narrative'})",
    "invalidation_or_question": "string ({'invalidation condition' if mode == 'PRE_MARKET' else 'open question'})"
  }},
  "cross_signals": ["string (themes mentioned by 2+ voices, or empty array if none)"]
}}"""

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
                    "max_tokens": 2000,
                    "temperature": 0.3,
                    "response_format": {"type": "json_object"}
                },
                timeout=60
            )

            if response.status_code == 200:
                raw = response.json()['choices'][0]['message']['content']
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    logger.warning("Failed to parse Grok JSON response, returning raw string")
                    return raw
            else:
                logger.error(f"Grok API error: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.error(f"Error generating digest with Grok: {e}")
            return None


def generate_signal_digest(mode: str = 'PRE_MARKET') -> Optional[str]:
    """
    Main entry point for generating signal digest.

    Args:
        mode: 'PRE_MARKET' or 'POST_CLOSE'

    Returns:
        Signal digest text ready for email insertion
    """
    analyzer = SignalAnalyzer()
    return analyzer.generate_full_digest(mode)


if __name__ == "__main__":
    # Test the analyzer
    logging.basicConfig(level=logging.INFO)

    print("Testing signal digest generation (PRE_MARKET)...")
    digest = generate_signal_digest('PRE_MARKET')

    if digest:
        print("\n" + "=" * 60)
        print("SIGNAL DIGEST")
        print("=" * 60)
        print(digest)
    else:
        print("Failed to generate digest - check XAI_API_KEY")
