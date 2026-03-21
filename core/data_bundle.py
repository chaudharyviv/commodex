"""
COMMODEX — Data Bundle Assembler
Collects all data inputs and assembles the structured bundle
that gets passed to Agent 1 (Market Analyst).

This is the single entry point for data collection.
All three agents receive this bundle as their primary input.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

from core.groww_client import GrowwClient
from core.technical_engine import TechnicalEngine, TechnicalData
from core.news_client import NewsClient
from core.inr_usd import get_inr_usd_rate
from config import (
    ACTIVE_COMMODITIES,
    CONFIDENCE_CAP_NO_NEWS,
    CONFIDENCE_CAP_INR_VOLATILE,
    LOT_CONFIG,
)

logger = logging.getLogger(__name__)


@dataclass
class DataBundle:
    """
    Complete market data package for one commodity signal request.
    Passed unchanged through all three agents.
    """
    # Request metadata
    symbol:          str
    contract:        str
    timeframe:       str
    trading_style:   str
    timestamp:       str = field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    # Live price
    ltp:             Optional[float] = None
    ltp_available:   bool = False

    # Technical indicators
    technicals:      Optional[TechnicalData] = None
    technicals_ok:   bool = False

    # News context
    news:            Optional[dict] = None
    news_available:  bool = False

    # INR/USD
    inr_usd:         Optional[dict] = None
    inr_usd_rate:    Optional[float] = None

    # Confidence caps from data quality
    confidence_cap:  int = 100
    cap_reasons:     list = field(default_factory=list)

    # Contract metadata
    lot_config:      Optional[dict] = None

    # Data quality flags
    data_quality:    str = "full"   # full | partial | minimal

    def apply_confidence_caps(self):
        """
        Apply confidence caps based on data availability.
        Called after bundle is assembled.
        """
        if not self.news_available:
            if self.confidence_cap > CONFIDENCE_CAP_NO_NEWS:
                self.confidence_cap = CONFIDENCE_CAP_NO_NEWS
                self.cap_reasons.append(
                    f"News unavailable — confidence capped at {CONFIDENCE_CAP_NO_NEWS}%"
                )

        if self.inr_usd and self.inr_usd.get("signal") == "volatile":
            if self.confidence_cap > CONFIDENCE_CAP_INR_VOLATILE:
                self.confidence_cap = CONFIDENCE_CAP_INR_VOLATILE
                self.cap_reasons.append(
                    f"INR/USD volatile ({self.inr_usd.get('change_pct'):+.2f}%) "
                    f"— confidence capped at {CONFIDENCE_CAP_INR_VOLATILE}%"
                )

        # Set data quality
        if self.technicals_ok and self.news_available and self.ltp_available:
            self.data_quality = "full"
        elif self.technicals_ok and self.ltp_available:
            self.data_quality = "partial"
        else:
            self.data_quality = "minimal"

    def to_prompt_string(self) -> str:
        """
        Build the complete context string for Agent 1 prompt.
        Structured, token-efficient, all key data in one block.
        """
        lines = [
            "=" * 60,
            "MARKET DATA BUNDLE",
            "=" * 60,
            f"Symbol    : {self.symbol} ({self.contract})",
            f"Timeframe : {self.timeframe}",
            f"Style     : {self.trading_style}",
            f"Timestamp : {self.timestamp}",
            f"Data      : {self.data_quality}",
        ]

        if self.confidence_cap < 100:
            lines.append(f"⚠ Confidence cap: {self.confidence_cap}%")
            for r in self.cap_reasons:
                lines.append(f"  Reason: {r}")

        # Live price
        lines.append("\n--- LIVE PRICE ---")
        if self.ltp_available:
            lines.append(f"LTP: Rs{self.ltp:,.2f}")
        else:
            lines.append("LTP: unavailable")

        # INR/USD
        lines.append("\n--- INR/USD ---")
        if self.inr_usd and self.inr_usd.get("available"):
            lines.append(
                f"Rate    : {self.inr_usd['rate']} "
                f"({self.inr_usd['change_pct']:+.3f}%)"
            )
            lines.append(
                f"Signal  : {self.inr_usd['direction']} "
                f"[{self.inr_usd['signal']}]"
            )
        else:
            lines.append("INR/USD: unavailable")

        # Technicals
        lines.append("\n--- TECHNICAL INDICATORS ---")
        if self.technicals_ok and self.technicals:
            lines.append(self.technicals.summary_string())
        else:
            lines.append("Technicals: unavailable")

        # News
        lines.append("\n--- NEWS CONTEXT ---")
        if self.news_available and self.news:
            lines.append(self.news["summary"])
        else:
            lines.append("News: unavailable")

        lines.append("=" * 60)
        return "\n".join(lines)


class DataBundleAssembler:
    """
    Orchestrates data collection from all sources.
    Returns a fully populated DataBundle.
    Handles partial failures gracefully — never raises.
    """

    def __init__(
        self,
        groww_client: GrowwClient,
        tech_engine: TechnicalEngine,
        news_client: NewsClient,
    ):
        self._groww = groww_client
        self._tech  = tech_engine
        self._news  = news_client

    def assemble(
        self,
        symbol: str,
        timeframe: str = "15minute",
        trading_style: str = "system",
        days: int = 30,
    ) -> DataBundle:
        """
        Assemble complete data bundle for a commodity symbol.
        Each data source is fetched independently — one failure
        does not block others.
        """
        # Find active contract
        contract_info = self._groww.find_active_contract(symbol)
        if not contract_info:
            logger.error(f"No active contract for {symbol}")
            raise ValueError(f"No active MCX contract found for {symbol}")

        trading_symbol = contract_info["trading_symbol"]
        bundle = DataBundle(
            symbol         = symbol,
            contract       = trading_symbol,
            timeframe      = timeframe,
            trading_style  = trading_style,
            lot_config     = LOT_CONFIG.get(symbol),
        )

        # ── 1. Live Price ──────────────────────────────────
        try:
            ltp_data = self._groww.get_ltp(
                [f"MCX_{trading_symbol}"]
            )
            ltp_key = f"MCX_{trading_symbol}"
            if ltp_data and ltp_key in ltp_data:
                bundle.ltp           = float(ltp_data[ltp_key])
                bundle.ltp_available = True
                logger.info(f"LTP: Rs{bundle.ltp:,.2f}")
        except Exception as e:
            logger.warning(f"LTP fetch failed: {e}")

        # ── 1b. Open Interest ──────────────────────────────
        # Injected into technicals after they are computed
        # so we store temporarily here
        _oi_data = {}
        try:
            _oi_data = self._groww.get_oi(trading_symbol)
            if _oi_data:
                logger.info(
                    f"OI fetched: {_oi_data.get('oi_interpretation')} | "
                    f"change={_oi_data.get('oi_change_pct'):+.1f}%"
                )
        except Exception as e:
            logger.warning(f"OI fetch failed: {e}")

        # ── 2. Historical + Technicals ─────────────────────
        try:
            candles = self._groww.get_historical(
                trading_symbol=trading_symbol,
                interval=timeframe,
                days=days,
            )
            if candles:
                bundle.technicals    = self._tech.compute(
                    candles, symbol, timeframe
                )
                bundle.technicals_ok = True

                # Inject OI data into technicals
                # (OI comes from quote, not candles)
                if _oi_data and bundle.technicals:
                    bundle.technicals.oi_current        = _oi_data.get("oi_current")
                    bundle.technicals.oi_prev_day       = _oi_data.get("oi_prev_day")
                    bundle.technicals.oi_change_pct     = _oi_data.get("oi_change_pct")
                    bundle.technicals.oi_interpretation = _oi_data.get("oi_interpretation")
                    logger.info(
                        f"OI injected into technicals: "
                        f"{_oi_data.get('oi_interpretation')}"
                    )
        except Exception as e:
            logger.warning(f"Technicals failed: {e}")

        # ── 3. INR/USD ─────────────────────────────────────
        try:
            bundle.inr_usd      = get_inr_usd_rate()
            bundle.inr_usd_rate = bundle.inr_usd.get("rate")
        except Exception as e:
            logger.warning(f"INR/USD failed: {e}")

        # ── 4. News ────────────────────────────────────────
        try:
            news = self._news.fetch(symbol)
            bundle.news           = news
            bundle.news_available = news.get("available", False)
        except Exception as e:
            logger.warning(f"News fetch failed: {e}")

        # ── Apply confidence caps ──────────────────────────
        bundle.apply_confidence_caps()

        logger.info(
            f"Bundle assembled: {symbol} | "
            f"quality={bundle.data_quality} | "
            f"cap={bundle.confidence_cap}%"
        )
        return bundle