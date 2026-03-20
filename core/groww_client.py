"""
COMMODEX — Groww API Client (SDK-based)
Uses official growwapi Python SDK instead of raw HTTP calls.
Auth: pre-generated access token via GrowwAPI.get_access_token()

Version: 1.1 — replaced hand-rolled HTTP client with growwapi SDK
"""

import os
import logging
import pandas as pd
import pyotp
from datetime import datetime, timedelta
from typing import Optional
from growwapi import GrowwAPI

from config import (
    GROWW_API_KEY,
    GROWW_API_SECRET,
    LOT_CONFIG,
    ACTIVE_COMMODITIES,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────
# TOKEN GENERATION HELPER
# Call this once to generate your access token, then store in .env
# ─────────────────────────────────────────────────────────────────

def generate_access_token(
    api_key: str,
    secret: str = None,
    totp_secret: str = None,
) -> str:
    """
    Generate a Groww access token.

    Use one of:
      generate_access_token(api_key, secret=your_secret)
      generate_access_token(api_key, totp_secret=your_totp_secret)

    Store the returned token in .env as GROWW_ACCESS_TOKEN.
    """
    if secret:
        token = GrowwAPI.get_access_token(api_key=api_key, secret=secret)
    elif totp_secret:
        totp = pyotp.TOTP(totp_secret).now()
        token = GrowwAPI.get_access_token(api_key=api_key, totp=totp)
    else:
        raise ValueError("Provide either secret or totp_secret")

    logger.info("Access token generated successfully")
    return token


# ─────────────────────────────────────────────────────────────────
# MAIN CLIENT
# ─────────────────────────────────────────────────────────────────

class GrowwClient:
    """
    COMMODEX wrapper around the official growwapi SDK.
    Focused on MCX commodity operations needed by the signal pipeline.
    """

    def __init__(self, access_token: str = None):
        """
        Initialise with access token.
        Falls back to GROWW_ACCESS_TOKEN env var if not provided.
        """
        token = access_token or os.getenv("GROWW_ACCESS_TOKEN")
        if not token:
            raise ValueError(
                "No Groww access token found. "
                "Set GROWW_ACCESS_TOKEN in .env or pass access_token directly."
            )
        self._groww = GrowwAPI(token)
        self._instruments_df: Optional[pd.DataFrame] = None
        logger.info("GrowwClient initialised via SDK")

    # ── Instruments ────────────────────────────────────────────────

    def get_instruments_df(self, force_refresh: bool = False) -> pd.DataFrame:
        """
        Load full instruments DataFrame from Groww CSV.
        Cached in memory for the session.
        """
        if self._instruments_df is not None and not force_refresh:
            return self._instruments_df
        self._instruments_df = self._groww.get_all_instruments()
        logger.info(f"Loaded {len(self._instruments_df)} instruments")
        return self._instruments_df

    def get_mcx_futures(self) -> pd.DataFrame:
        """Return only MCX futures contracts (COMMODITY segment, FUT type)."""
        df = self.get_instruments_df()
        return df[
            (df["exchange"] == "MCX") &
            (df["segment"] == "COMMODITY") &
            (df["instrument_type"] == "FUT")
        ].copy()

    def find_active_contract(self, base_symbol: str) -> Optional[dict]:
        """
        Find the nearest non-expired MCX futures contract
        for a base symbol e.g. GOLDM, CRUDEOILM.
        Returns dict of instrument details or None.
        """
        try:
            mcx_futures = self.get_mcx_futures()
            today = pd.Timestamp.today().normalize()

            # Filter by underlying symbol
            candidates = mcx_futures[
                mcx_futures["underlying_symbol"].str.upper() == base_symbol.upper()
            ].copy()

            if candidates.empty:
                # Try trading_symbol contains base_symbol
                candidates = mcx_futures[
                    mcx_futures["trading_symbol"].str.upper().str.startswith(
                        base_symbol.upper()
                    )
                ].copy()

            if candidates.empty:
                logger.warning(f"No contracts found for {base_symbol}")
                return None

            # Filter non-expired
            candidates["expiry_date"] = pd.to_datetime(
                candidates["expiry_date"], errors="coerce"
            )
            candidates = candidates[candidates["expiry_date"] >= today]

            if candidates.empty:
                logger.warning(f"All {base_symbol} contracts have expired")
                return None

            # Return nearest expiry
            candidates = candidates.sort_values("expiry_date")
            contract = candidates.iloc[0].to_dict()
            logger.info(
                f"Active contract for {base_symbol}: "
                f"{contract.get('trading_symbol')} "
                f"expiry {contract.get('expiry_date')}"
            )
            return contract

        except Exception as e:
            logger.error(f"find_active_contract({base_symbol}) failed: {e}")
            return None

    # ── Live Data ──────────────────────────────────────────────────

    def get_ltp(self, exchange_trading_symbols: list[str]) -> dict:
        """
        Get Last Traded Price for MCX commodity instruments.

        exchange_trading_symbols: list like
          ["MCX_GOLDM03APR26FUT", "MCX_CRUDEOILM20APR26FUT"]

        Returns dict: { "MCX_GOLDM03APR26FUT": 71450.0, ... }
        """
        try:
            if len(exchange_trading_symbols) == 1:
                result = self._groww.get_ltp(
                    segment=self._groww.SEGMENT_COMMODITY,
                    exchange_trading_symbols=exchange_trading_symbols[0],
                )
            else:
                result = self._groww.get_ltp(
                    segment=self._groww.SEGMENT_COMMODITY,
                    exchange_trading_symbols=tuple(exchange_trading_symbols),
                )
            logger.info(f"LTP fetched for {exchange_trading_symbols}")
            return result
        except Exception as e:
            logger.error(f"get_ltp failed: {e}")
            raise

    def get_quote(self, trading_symbol: str, exchange: str = "MCX") -> dict:
        """
        Get full market quote for a single MCX instrument.
        Returns OHLC, depth, volume, OI, circuit limits.
        """
        try:
            result = self._groww.get_quote(
                exchange=exchange,
                segment=self._groww.SEGMENT_COMMODITY,
                trading_symbol=trading_symbol,
            )
            return result
        except Exception as e:
            logger.error(f"get_quote({trading_symbol}) failed: {e}")
            raise

    # ── Historical Data ────────────────────────────────────────────

    def get_historical(
        self,
        trading_symbol: str,
        exchange: str = "MCX",
        interval: str = "15minute",
        days: int = 30,
    ) -> list[dict]:
        """
        Fetch historical OHLCV candles for an MCX contract.

        Uses SDK: get_historical_candle_data(
            trading_symbol, exchange, segment,
            start_time, end_time, interval_in_minutes
        )

        start_time / end_time format: "yyyy-MM-dd HH:mm:ss"
        interval_in_minutes: integer (1, 5, 10, 15, 30, 60, 240, 1440)
        """

        # Map string interval to integer minutes
        interval_map = {
            "1minute":  1,
            "2minute":  2,
            "3minute":  3,
            "5minute":  5,
            "10minute": 10,
            "15minute": 15,
            "30minute": 30,
            "1hour":    60,
            "4hour":    240,
            "1day":     1440,
        }
        interval_minutes = interval_map.get(interval, 15)

        end_dt   = datetime.today()
        start_dt = end_dt - timedelta(days=days)

        # SDK requires "yyyy-MM-dd HH:mm:ss" format
        start_time = start_dt.strftime("%Y-%m-%d %H:%M:%S")
        end_time   = end_dt.strftime("%Y-%m-%d %H:%M:%S")

        try:
            result = self._groww.get_historical_candle_data(
                trading_symbol=trading_symbol,
                exchange=self._groww.EXCHANGE_MCX,
                segment=self._groww.SEGMENT_COMMODITY,
                start_time=start_time,
                end_time=end_time,
                interval_in_minutes=interval_minutes,
            )

            # Normalise to list of dicts
            if isinstance(result, pd.DataFrame):
                raw = result.to_dict("records")
            elif isinstance(result, dict):
                raw = result.get("candles", result.get("data", []))
            elif isinstance(result, list):
                raw = result
            else:
                raw = []

            # Convert raw list format [ts, open, high, low, close, vol]
            # to named dict format for consistent downstream use
            candles = []
            for c in raw:
                if isinstance(c, (list, tuple)) and len(c) >= 5:
                    candles.append({
                        "timestamp": c[0],
                        "open":      c[1],
                        "high":      c[2],
                        "low":       c[3],
                        "close":     c[4],
                        "volume":    c[5] if len(c) > 5 else 0,
                    })
                elif isinstance(c, dict):
                    candles.append(c)

            logger.info(
                f"Historical: {len(candles)} candles | "
                f"{trading_symbol} | {interval} | {days}d"
            )
            return candles

        except Exception as e:
            logger.error(f"get_historical({trading_symbol}) failed: {e}")
            raise
    # ── Portfolio & Margin ─────────────────────────────────────────

    def get_positions(self) -> list[dict]:
        """Fetch current open positions."""
        try:
            result = self._groww.get_positions()
            if isinstance(result, pd.DataFrame):
                return result.to_dict("records")
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error(f"get_positions failed: {e}")
            return []

    def get_margin(self) -> dict:
        """Fetch available margin from Groww account."""
        try:
            return self._groww.get_margin()
        except Exception as e:
            logger.error(f"get_margin failed: {e}")
            return {}

    # ── Health Check ───────────────────────────────────────────────

    def ping(self) -> dict:
        """
        Test connectivity and auth.
        Loads instruments CSV — confirms token is valid.
        """
        try:
            df = self.get_instruments_df()
            mcx_count = len(df[df["exchange"] == "MCX"])
            commodity_count = len(
                df[
                    (df["exchange"] == "MCX") &
                    (df["segment"] == "COMMODITY")
                ]
            )
            return {
                "status":            "ok",
                "total_instruments": len(df),
                "mcx_total":         mcx_count,
                "mcx_commodity":     commodity_count,
                "timestamp":         datetime.now().isoformat(),
            }
        except Exception as e:
            return {
                "status":    "error",
                "error":     str(e),
                "timestamp": datetime.now().isoformat(),
            }