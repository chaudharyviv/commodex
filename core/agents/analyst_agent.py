"""
COMMODEX — Agent 1: Market Analyst (v2.0)
Reads the full DataBundle and produces a neutral MarketAnalysis.
No buy/sell decisions — pure market description.

Includes programmatic sanity checker between Agent 1 and Agent 2
as recommended in the design review.

v2.0: Added sanity checks for ADX, OI, VWAP, Supertrend
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
# SANITY CHECKER v2.0
# Programmatic contradiction check between Agent 1 and Agent 2
# Catches hallucinated market regimes before they propagate
#
# v2.0: Added checks for ADX, OI, VWAP, Supertrend
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
        warnings       = []
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

        # ── Check 6 (NEW v2.0) ────────────────────────────
        # ADX contradicts regime — regime=trending but ADX says ranging
        if (
            tech.adx_14 is not None
            and analysis.market_regime in ("trending_up", "trending_down")
            and tech.adx_signal == "ranging"
        ):
            warnings.append(
                f"CONTRADICTION: regime={analysis.market_regime} but "
                f"ADX={tech.adx_14} [{tech.adx_signal}]. "
                f"ADX below 20 indicates no meaningful trend. "
                f"Trend-following signals will likely fail."
            )
            if confidence_cap is None or confidence_cap > 60:
                confidence_cap = 60

        # ── Check 7 (NEW v2.0) ────────────────────────────
        # ADX contradicts regime — regime=ranging but ADX says strong trend
        if (
            tech.adx_14 is not None
            and analysis.market_regime == "ranging"
            and tech.adx_signal in ("trending", "strong_trend")
        ):
            warnings.append(
                f"CONTRADICTION: regime=ranging but "
                f"ADX={tech.adx_14} [{tech.adx_signal}]. "
                f"ADX above 25 indicates directional trend. "
                f"Mean-reversion signals will likely fail."
            )
            if confidence_cap is None or confidence_cap > 65:
                confidence_cap = 65

        # ── Check 8 (NEW v2.0) ────────────────────────────
        # OI shows weak conviction — short covering on bullish,
        # or long unwinding on bearish. Signal is less reliable.
        if tech.oi_interpretation:
            if (
                analysis.overall_sentiment == "bullish"
                and tech.oi_interpretation == "short_covering"
            ):
                warnings.append(
                    f"WEAK CONVICTION: Bullish sentiment but OI shows "
                    f"short_covering (OI falling with price up). "
                    f"This is weak bullish — rally may exhaust quickly."
                )
                if confidence_cap is None or confidence_cap > 70:
                    confidence_cap = 70

            if (
                analysis.overall_sentiment == "bearish"
                and tech.oi_interpretation == "long_unwinding"
            ):
                warnings.append(
                    f"WEAK CONVICTION: Bearish sentiment but OI shows "
                    f"long_unwinding (OI falling with price down). "
                    f"This is weak bearish — dip may reverse."
                )
                if confidence_cap is None or confidence_cap > 70:
                    confidence_cap = 70

        # ── Check 9 (NEW v2.0) ────────────────────────────
        # Supertrend contradicts signal direction
        if (
            tech.supertrend_dir
            and analysis.overall_sentiment == "bullish"
            and tech.supertrend_dir == "bearish"
        ):
            warnings.append(
                f"SUPERTREND CONFLICT: Bullish sentiment but "
                f"Supertrend is bearish at Rs{tech.supertrend:,.0f}. "
                f"Price is below the Supertrend line."
            )
            if confidence_cap is None or confidence_cap > 70:
                confidence_cap = 70

        if (
            tech.supertrend_dir
            and analysis.overall_sentiment == "bearish"
            and tech.supertrend_dir == "bullish"
        ):
            warnings.append(
                f"SUPERTREND CONFLICT: Bearish sentiment but "
                f"Supertrend is bullish at Rs{tech.supertrend:,.0f}. "
                f"Price is above the Supertrend line."
            )
            if confidence_cap is None or confidence_cap > 70:
                confidence_cap = 70

        # ── Check 10 (NEW v2.0) ───────────────────────────
        # RSI divergence detected — flag prominently
        if tech.rsi_divergence and tech.rsi_divergence != "none":
            div_type = tech.rsi_divergence
            warnings.append(
                f"RSI DIVERGENCE: {div_type} divergence detected. "
                f"Price and RSI are moving in opposite directions. "
                f"{'Potential reversal to upside.' if div_type == 'bullish' else 'Potential reversal to downside.'}"
            )
            # Divergence doesn't cap — it's informational for Agent 2

        # ── Check 11 (NEW v2.0) ───────────────────────────
        # BB squeeze — breakout imminent, warn Agent 2
        if tech.bb_squeeze:
            warnings.append(
                f"BB SQUEEZE ACTIVE: Bollinger Band width at period low. "
                f"Breakout imminent — direction unknown. "
                f"Wait for confirmation candle before committing."
            )
            # Squeeze doesn't cap — it's directionally neutral

        # ── Check 12 (NEW v2.0) ───────────────────────────
        # EMA 200 conflict — positional signal against long-term trend
        if (
            tech.ema_200_trend
            and analysis.overall_sentiment == "bullish"
            and "bearish" in tech.ema_200_trend
        ):
            warnings.append(
                f"EMA200 CONFLICT: Bullish sentiment but price is below "
                f"EMA(200) at Rs{tech.ema_200:,.0f}. "
                f"Long-term bias is bearish — positional longs carry extra risk."
            )
            # Soft cap — informational for positional trades
            if confidence_cap is None or confidence_cap > 75:
                confidence_cap = 75

        if (
            tech.ema_200_trend
            and analysis.overall_sentiment == "bearish"
            and "bullish" in tech.ema_200_trend
        ):
            warnings.append(
                f"EMA200 CONFLICT: Bearish sentiment but price is above "
                f"EMA(200) at Rs{tech.ema_200:,.0f}. "
                f"Long-term bias is bullish — positional shorts carry extra risk."
            )
            if confidence_cap is None or confidence_cap > 75:
                confidence_cap = 75

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
