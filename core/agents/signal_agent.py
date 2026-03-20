"""
COMMODEX — Agent 2: Signal Generator
Takes MarketAnalysis + DataBundle and produces a trading signal.
Receives sanity checker warnings as additional constraints.
"""

import logging
from core.llm_client import LLMClient, SignalDecision, load_prompt
from core.llm_client import MarketAnalysis
from core.data_bundle import DataBundle

logger = logging.getLogger(__name__)

PROMPT_VERSION = "1.0"


class SignalAgent:
    """
    Agent 2 — Signal Generator.
    Input:  DataBundle + MarketAnalysis + sanity warnings
    Output: SignalDecision (validated Pydantic model)
    """

    def __init__(self, llm_client: LLMClient):
        self._llm    = llm_client
        self._prompt = load_prompt("signal", PROMPT_VERSION)

    def generate(
        self,
        bundle:         DataBundle,
        analysis:       MarketAnalysis,
        sanity_result:  dict,
        trading_style:  str = "system",
    ) -> SignalDecision:
        """
        Generate trading signal from analysis and data.
        Sanity warnings and confidence caps are injected into prompt.
        """
        user_prompt = self._build_user_prompt(
            bundle, analysis, sanity_result, trading_style
        )

        logger.info(
            f"SignalAgent running — {bundle.symbol} "
            f"style={trading_style} prompt_v{PROMPT_VERSION}"
        )

        signal = self._llm.call(
            system_prompt = self._prompt,
            user_prompt   = user_prompt,
            output_model  = SignalDecision,
            max_tokens    = 1000,
            temperature   = 0.2,
        )

        # Apply confidence cap from sanity checker
        cap = sanity_result.get("confidence_cap")
        if cap and signal.confidence > cap:
            logger.warning(
                f"Confidence capped: {signal.confidence} → {cap} "
                f"(sanity checker)"
            )
            signal.confidence = cap

        # Also apply bundle-level confidence cap
        if bundle.confidence_cap < 100 and signal.confidence > bundle.confidence_cap:
            signal.confidence = bundle.confidence_cap

        logger.info(
            f"Signal: {signal.action} | "
            f"confidence={signal.confidence}% | "
            f"quality={signal.signal_quality}"
        )
        return signal

    def _build_user_prompt(
        self,
        bundle:        DataBundle,
        analysis:      MarketAnalysis,
        sanity_result: dict,
        trading_style: str,
    ) -> str:

        # Build sanity warning block
        sanity_block = ""
        if sanity_result.get("warnings"):
            sanity_block = "\n⚠ SANITY CHECKER WARNINGS (you MUST consider these):\n"
            for w in sanity_result["warnings"]:
                sanity_block += f"  - {w}\n"
            if sanity_result.get("confidence_cap"):
                sanity_block += (
                    f"  → Maximum confidence allowed: "
                    f"{sanity_result['confidence_cap']}%\n"
                )

        # Style constraint
        style_constraint = {
            "intraday":   "INTRADAY ONLY — only consider setups closeable within today's session (before 11:30 PM IST). Output HOLD if best setup is positional.",
            "swing":      "SWING/POSITIONAL ONLY — only consider 2-7 day holds with daily chart setups. Output HOLD if best setup is intraday.",
            "system":     "MIXED — you decide the best timeframe based on market regime.",
        }.get(trading_style, "MIXED — you decide the best timeframe.")

        return f"""Generate a trading signal based on the following data.

TRADING STYLE CONSTRAINT: {style_constraint}

--- MARKET DATA BUNDLE ---
{bundle.to_prompt_string()}

--- ANALYST ASSESSMENT ---
Market Regime:    {analysis.market_regime} ({analysis.trend_strength})
Sentiment:        {analysis.overall_sentiment} ({analysis.sentiment_confidence}%)
Technical:        {analysis.technical_summary}
India Factors:    {analysis.india_specific_factors}
Global Factors:   {analysis.global_risk_factors}
Support levels:   {analysis.key_support_levels}
Resistance:       {analysis.key_resistance_levels}
High impact next 24h: {analysis.high_impact_events_next_24h or 'None'}
Notes:            {analysis.analyst_notes}
{sanity_block}
Return a JSON object with these exact fields:
{{
    "action": "BUY | SELL | HOLD",
    "confidence": integer 0-100,
    "primary_reason": "single strongest reason for this signal",
    "supporting_factors": ["factor1", "factor2"],
    "contradicting_factors": ["factor1"],
    "invalidation_condition": "what price/event would make this signal wrong",
    "recommended_timeframe": "intraday | positional_2d | positional_5d | swing",
    "signal_quality": "A | B | C",
    "hold_reasoning": "string if HOLD, else null"
}}"""