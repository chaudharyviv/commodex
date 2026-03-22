"""
COMMODEX — News Client
Fetches India-specific commodity news via Tavily API.
Results cached in SQLite for 1 hour to avoid repeated calls.

Designed so Agent 1 receives structured, relevant news context
not a raw dump of web results.
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Optional
from tavily import TavilyClient
from config import TAVILY_API_KEY, CACHE_NEWS_MIN
from core.db import get_connection

logger = logging.getLogger(__name__)

# ── India-specific search queries per commodity ────────────────
# Designed to surface MCX-relevant news, not generic global news
NEWS_QUERIES = {
    "GOLDM": [
        "MCX gold price India today",
        "gold India RBI import duty rupee",
        "COMEX gold Federal Reserve dollar index",
    ],
    "CRUDEOILM": [
        "MCX crude oil price India today",
        "OPEC production crude oil India",
        "US EIA crude inventory weekly report",
    ],
    "SILVERM": [
        "MCX silver mini price India today",
        "silver India demand rupee industrial metals",
        "COMEX silver dollar index Federal Reserve",
    ],
    "SILVER": [
        "MCX silver price India today",
        "silver India demand rupee industrial metals",
        "COMEX silver dollar index Federal Reserve",
    ],
    "NATURALGASM": [
        "MCX natural gas mini price India today",
        "Henry Hub natural gas LNG Asia demand",
        "US natural gas storage weekly report",
    ],
}

# Fallback for unknown symbols
DEFAULT_QUERIES = [
    "Indian commodity market news today",
    "MCX NCDEX commodity news India",
]


class NewsClient:
    """
    Fetches and caches commodity news for Agent 1 context.
    Uses Tavily for clean, LLM-ready search results.
    """

    def __init__(self):
        if not TAVILY_API_KEY:
            logger.warning(
                "TAVILY_API_KEY not set — news will be unavailable"
            )
            self._client = None
        else:
            self._client = TavilyClient(api_key=TAVILY_API_KEY)
            logger.info("NewsClient initialised")

    def fetch(
        self,
        symbol: str,
        max_results: int = 5,
        force_refresh: bool = False,
    ) -> dict:
        """
        Fetch latest news for a commodity symbol.
        Returns structured news dict for Agent 1 prompt.

        Returns:
        {
            "symbol":     "GOLDM",
            "fetched_at": "2026-03-20 14:30:00",
            "from_cache": True/False,
            "available":  True/False,
            "articles": [
                {
                    "headline": "...",
                    "snippet":  "...",
                    "source":   "...",
                    "url":      "..."
                },
                ...
            ],
            "summary": "Compact string for prompt injection"
        }
        """
        # Check cache first
        if not force_refresh:
            cached = self._get_cached(symbol)
            if cached:
                logger.info(f"News cache hit for {symbol}")
                return cached

        # Fetch fresh
        if not self._client:
            return self._unavailable_response(symbol, "Tavily not configured")

        try:
            queries  = NEWS_QUERIES.get(symbol, DEFAULT_QUERIES)
            articles = []

            for query in queries[:2]:   # max 2 queries per fetch
                results = self._client.search(
                    query=query,
                    max_results=3,
                    search_depth="basic",
                    include_answer=False,
                )
                for r in results.get("results", []):
                    articles.append({
                        "headline": r.get("title",   ""),
                        "snippet":  r.get("content", "")[:300],
                        "source":   r.get("source",  ""),
                        "url":      r.get("url",     ""),
                    })

            # Deduplicate by headline
            seen = set()
            unique = []
            for a in articles:
                if a["headline"] not in seen:
                    seen.add(a["headline"])
                    unique.append(a)

            articles = unique[:max_results]

            response = {
                "symbol":     symbol,
                "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "from_cache": False,
                "available":  True,
                "articles":   articles,
                "summary":    self._build_summary(symbol, articles),
            }

            # Cache it
            self._cache_news(symbol, articles)
            logger.info(f"Fetched {len(articles)} news items for {symbol}")
            return response

        except Exception as e:
            logger.error(f"News fetch failed for {symbol}: {e}")
            return self._unavailable_response(symbol, str(e))

    def _build_summary(self, symbol: str, articles: list[dict]) -> str:
        """Build compact summary string for prompt injection."""
        if not articles:
            return f"No recent news available for {symbol}."
        lines = [f"Recent news for {symbol} ({len(articles)} items):"]
        for i, a in enumerate(articles, 1):
            lines.append(f"{i}. {a['headline']} — {a['source']}")
            if a["snippet"]:
                lines.append(f"   {a['snippet'][:150]}...")
        return "\n".join(lines)

    def _unavailable_response(self, symbol: str, reason: str) -> dict:
        """Return a structured response when news is unavailable."""
        return {
            "symbol":     symbol,
            "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "from_cache": False,
            "available":  False,
            "articles":   [],
            "summary":    f"News unavailable for {symbol}: {reason}",
        }

    def _get_cached(self, symbol: str) -> Optional[dict]:
        """Return cached news if within TTL, else None."""
        try:
            conn   = get_connection()
            cursor = conn.cursor()
            cutoff = (
                datetime.now() - timedelta(minutes=CACHE_NEWS_MIN)
            ).strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute("""
                SELECT headline, snippet, source, url, fetched_at
                FROM news_cache
                WHERE commodity = ?
                AND fetched_at > ?
                ORDER BY fetched_at DESC
                LIMIT 5
            """, (symbol, cutoff))

            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return None

            articles = [
                {
                    "headline": row["headline"],
                    "snippet":  row["snippet"] or "",
                    "source":   row["source"]  or "",
                    "url":      row["url"]      or "",
                }
                for row in rows
            ]
            return {
                "symbol":     symbol,
                "fetched_at": rows[0]["fetched_at"],
                "from_cache": True,
                "available":  True,
                "articles":   articles,
                "summary":    self._build_summary(symbol, articles),
            }
        except Exception as e:
            logger.warning(f"Cache read failed: {e}")
            return None

    def _cache_news(self, symbol: str, articles: list[dict]):
        """Persist fetched articles to SQLite news_cache."""
        try:
            conn   = get_connection()
            cursor = conn.cursor()
            now    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for a in articles:
                cursor.execute("""
                    INSERT INTO news_cache
                    (commodity, headline, snippet, source, url, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    symbol,
                    a.get("headline", ""),
                    a.get("snippet",  ""),
                    a.get("source",   ""),
                    a.get("url",      ""),
                    now,
                ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"News cache write failed: {e}")
