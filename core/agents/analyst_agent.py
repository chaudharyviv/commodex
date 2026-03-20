"""
COMMODEX — Agent 1: Market Analyst
Reads the full DataBundle and produces a neutral MarketAnalysis.
No buy/sell decisions — pure market description.

Includes programmatic sanity checker between Agent 1 and Agent 2
as recommended in the design review.
"""

import logging
from core.llm_client import LLMClient, MarketAnalysis, load_prompt
from core.data_bundle import DataBundle

logger = logging.getLogger(__name__)

PROMPT_VERSION = "1.0"


class AnalystAgent:
    """
    Agent 1 — Market Analyst.
    Input:  DataBundle
    Output: MarketAnalysis (validated Pydantic model)
    """

    def __init__(self, llm_client: LLMClient):
        self._llm    = llm_client
        self._prompt = load_prompt("analyst", PROMPT_VERSION)

    def analyse(self, bundle: DataBundle) -> MarketAnalysis:
        """
        Run market analysis on the data bundle.
        Returns validated MarketAnalysis.
        """
        user_prompt = self._build_user_prompt(bundle)

        logger.info(
            f"AnalystAgent running — {bundle.symbol} "
            f"[{bundle.timeframe}] prompt_v{PROMPT_VERSION}"
        )

        analysis = self._llm.call(
            system_prompt = self._prompt,
            user_prompt   = user_prompt,
            output_model  = MarketAnalysis,
            max_tokens    = 1200,
            temperature   = 0.2,
        )

        logger.info(
            f"Analysis complete — regime={analysis.market_regime} "
            f"sentiment={analysis.overall_sentiment} "
            f"confidence={analysis.sentiment_confidence}%"
        )
        return analysis

    def _build_user_prompt(self, bundle: DataBundle) -> str:
        """Build the user prompt from the data bundle."""
        return f"""Analyse the following MCX commodity market data and return your assessment as JSON.

{bundle.to_prompt_string()}

Return a JSON object with these exact fields:
{{
    "market_regime": "trending_up | trending_down | ranging | volatile",
    "trend_strength": "strong | moderate | weak",
    "key_support_levels": [float, float],
    "key_resistance_levels": [float, float],
    "technical_summary": "3 sentences max describing price action",
    "india_specific_factors": "2 sentences on INR/USD, RBI, import duty, seasonal",
    "global_risk_factors": "2 sentences on international drivers",
    "high_impact_events_next_24h": "string or null",
    "overall_sentiment": "bullish | bearish | neutral | mixed",
    "sentiment_confidence": integer 0-100,
    "analyst_notes": "anything unusual worth flagging"
}}"""


# ─────────────────────────────────────────────────────────────────
# SANITY CHECKER
# Programmatic contradiction check between Agent 1 and Agent 2
# Catches hallucinated market regimes before they propagate
# ─────────────────────────────────────────────────────────────────

class SanityChecker:
    """
    Checks Agent 1 output against raw technical data.
    Flags contradictions and injects warnings into Agent 2 prompt.
    No LLM call — pure deterministic code.
    """

    def check(
        self,
        analysis: MarketAnalysis,
        bundle:   DataBundle,
    ) -> dict:
        """
        Run contradiction checks.
        Returns:
        {
            "passed":   True/False,
            "warnings": ["string", ...],
            "confidence_cap": int or None
        }
        """
        warnings     = []
        confidence_cap = None
        tech = bundle.technicals

        if not tech:
            return {"passed": True, "warnings": [], "confidence_cap": None}

        # ── Check 1 ───────────────────────────────────────
        # regime=trending_up but RSI overbought AND price at resistance
        if (
            analysis.market_regime == "trending_up"
            and tech.rsi_14
            and tech.rsi_14 > 72
            and tech.bb_position == "above_upper_overbought"
        ):
            warnings.append(
                f"CONTRADICTION: regime=trending_up but RSI={tech.rsi_14} "
                f"(overbought) and price above BB upper band. "
                f"Possible exhaustion — treat with caution."
            )
            confidence_cap = 65

        # ── Check 2 ───────────────────────────────────────
        # regime=trending_down but RSI oversold AND price at support
        if (
            analysis.market_regime == "trending_down"
            and tech.rsi_14
            and tech.rsi_14 < 28
            and tech.bb_position == "below_lower_oversold"
        ):
            warnings.append(
                f"CONTRADICTION: regime=trending_down but RSI={tech.rsi_14} "
                f"(oversold) and price below BB lower band. "
                f"Possible reversal setup — treat with caution."
            )
            confidence_cap = 65

        # ── Check 3 ───────────────────────────────────────
        # regime=ranging but ATR unusually high (volatile, not ranging)
        if (
            analysis.market_regime == "ranging"
            and tech.atr_pct
            and tech.atr_pct > 1.0
        ):
            warnings.append(
                f"CONTRADICTION: regime=ranging but ATR={tech.atr_pct}% "
                f"of price (high volatility). Market may be volatile, "
                f"not truly ranging."
            )
            confidence_cap = 65

        # ── Check 4 ───────────────────────────────────────
        # Sentiment bullish but MACD bearish and EMA bearish
        if (
            analysis.overall_sentiment == "bullish"
            and tech.macd_cross
            and "bearish" in tech.macd_cross
            and tech.ema_trend
            and "bearish" in tech.ema_trend
        ):
            warnings.append(
                f"CONTRADICTION: sentiment=bullish but MACD={tech.macd_cross} "
                f"and EMA={tech.ema_trend}. Technical picture is bearish."
            )
            confidence_cap = 60

        # ── Check 5 ───────────────────────────────────────
        # High impact event flagged — cap confidence
        if analysis.high_impact_events_next_24h:
            warnings.append(
                f"HIGH IMPACT EVENT: {analysis.high_impact_events_next_24h} "
                f"— confidence automatically capped at 60%"
            )
            if confidence_cap is None or confidence_cap > 60:
                confidence_cap = 60

        passed = len(warnings) == 0

        if warnings:
            logger.warning(
                f"SanityChecker flagged {len(warnings)} issue(s) "
                f"for {bundle.symbol}"
            )
        else:
            logger.info(f"SanityChecker passed for {bundle.symbol}")

        return {
            "passed":         passed,
            "warnings":       warnings,
            "confidence_cap": confidence_cap,
        }