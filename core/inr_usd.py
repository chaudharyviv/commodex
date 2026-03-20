
"""
COMMODEX — INR/USD Rate Fetcher
Fetches live INR/USD exchange rate for Guardrail 9
and Agent 1 market context.

Uses Yahoo Finance (free, no API key needed).
Cached for 15 minutes.
"""

import logging
import requests
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# Simple in-memory cache
_cache: dict = {"rate": None, "fetched_at": None}
CACHE_MINUTES = 15


def get_inr_usd_rate() -> dict:
    """
    Fetch current INR/USD exchange rate.
    Returns structured dict with rate, change, and signal.

    {
        "rate":         83.42,
        "change_pct":   0.12,
        "direction":    "weakening" | "strengthening" | "stable",
        "signal":       "normal" | "volatile",
        "fetched_at":   "2026-03-20 14:30:00",
        "from_cache":   True/False,
        "available":    True/False,
    }
    """
    # Check cache
    if _cache["rate"] and _cache["fetched_at"]:
        age = datetime.now() - _cache["fetched_at"]
        if age < timedelta(minutes=CACHE_MINUTES):
            logger.info("INR/USD cache hit")
            return {**_cache["data"], "from_cache": True}

    # Fetch from Yahoo Finance
    try:
        url     = "https://query1.finance.yahoo.com/v8/finance/chart/USDINR=X"
        headers = {"User-Agent": "Mozilla/5.0"}
        params  = {"interval": "1d", "range": "5d"}

        resp = requests.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        meta      = data["chart"]["result"][0]["meta"]
        rate      = round(float(meta["regularMarketPrice"]), 4)
        prev      = round(float(meta.get("previousClose", rate)), 4)
        change    = round(rate - prev, 4)
        change_pct = round((change / prev) * 100, 3) if prev else 0

        from config import INR_VOLATILITY_GATE_PCT
        signal = "volatile" if abs(change_pct) >= INR_VOLATILITY_GATE_PCT \
                 else "normal"

        if change_pct > 0.1:
            direction = "weakening"      # more INR per USD = INR weaker
        elif change_pct < -0.1:
            direction = "strengthening"
        else:
            direction = "stable"

        result = {
            "rate":       rate,
            "prev_close": prev,
            "change":     change,
            "change_pct": change_pct,
            "direction":  direction,
            "signal":     signal,
            "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "from_cache": False,
            "available":  True,
        }

        # Update cache
        _cache["rate"]       = rate
        _cache["fetched_at"] = datetime.now()
        _cache["data"]       = result

        logger.info(
            f"INR/USD: {rate} ({change_pct:+.3f}%) [{signal}]"
        )
        return result

    except Exception as e:
        logger.error(f"INR/USD fetch failed: {e}")
        return {
            "rate":       None,
            "available":  False,
            "signal":     "unknown",
            "direction":  "unknown",
            "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "from_cache": False,
            "error":      str(e),
        }