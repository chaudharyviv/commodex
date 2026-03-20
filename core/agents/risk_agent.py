"""
COMMODEX — Agent 3: Risk & Execution Assessor
Takes signal + analysis + data and produces precise risk parameters.
Position sizing is handled by config.get_position_size() — not LLM.
"""

import logging
from core.llm_client import LLMClient, RiskParameters, load_prompt
from core.llm_client import MarketAnalysis, SignalDecision
from core.data_bundle import DataBundle
from config import get_position_size, LOT_CONFIG

logger = logging.getLogger(__name__)

PROMPT_VERSION = "1.0"


class RiskAgent:
    """
    Agent 3 — Risk Assessor.
    Input:  DataBundle + MarketAnalysis + SignalDecision
    Output: RiskParameters + position sizing from config formula
    """

    def __init__(self, llm_client: LLMClient):
        self._llm    = llm_client
        self._prompt = load_prompt("risk", PROMPT_VERSION)

    def assess(
        self,
        bundle:   DataBundle,
        analysis: MarketAnalysis,
        signal:   SignalDecision,
    ) -> dict:
        """
        Assess risk for the given signal.
        Returns combined dict:
        {
            "risk_params":     RiskParameters,
            "position_sizing": dict from get_position_size(),
            "final_approved":  bool,
            "block_reason":    str or None
        }
        """
        # If HOLD — skip LLM call entirely
        if signal.action == "HOLD":
            logger.info("Signal is HOLD — skipping risk assessment")
            return {
                "risk_params":     None,
                "position_sizing": None,
                "final_approved":  False,
                "block_reason":    "Signal is HOLD — no position to size",
            }

        user_prompt = self._build_user_prompt(bundle, analysis, signal)

        logger.info(
            f"RiskAgent running — {bundle.symbol} "
            f"{signal.action} prompt_v{PROMPT_VERSION}"
        )

        risk = self._llm.call(
            system_prompt = self._prompt,
            user_prompt   = user_prompt,
            output_model  = RiskParameters,
            max_tokens    = 800,
            temperature   = 0.1,   # very low — we want consistent risk math
        )

        # Override position sizing with deterministic formula
        # Never trust LLM for this — use config.get_position_size()
        position_sizing = None
        if risk.risk_approved and risk.stop_loss and risk.entry_price:
            position_sizing = get_position_size(
                symbol      = bundle.symbol,
                entry_price = risk.entry_price,
                stop_loss   = risk.stop_loss,
            )
            logger.info(
                f"Position sizing: {position_sizing.get('position_lots')} lots | "
                f"risk=Rs{position_sizing.get('actual_risk_inr'):,.0f} "
                f"({position_sizing.get('actual_risk_pct')}%)"
            )

        # Validate R:R ratio
        from config import MIN_RR_RATIO
        if risk.risk_reward_ratio < MIN_RR_RATIO:
            risk.risk_approved   = False
            risk.risk_block_reason = (
                f"R:R ratio {risk.risk_reward_ratio:.1f} "
                f"below minimum {MIN_RR_RATIO}"
            )
            logger.warning(f"Risk blocked: {risk.risk_block_reason}")

        final_approved = risk.risk_approved
        block_reason   = risk.risk_block_reason

        logger.info(
            f"Risk assessment: approved={final_approved} | "
            f"entry={risk.entry_price} SL={risk.stop_loss} "
            f"T1={risk.target_1} RR={risk.risk_reward_ratio}"
        )

        return {
            "risk_params":     risk,
            "position_sizing": position_sizing,
            "final_approved":  final_approved,
            "block_reason":    block_reason,
        }

    def _build_user_prompt(
        self,
        bundle:   DataBundle,
        analysis: MarketAnalysis,
        signal:   SignalDecision,
    ) -> str:
        tech = bundle.technicals
        atr  = tech.atr_14 if tech else "unknown"
        ltp  = bundle.ltp or 0

        lot_cfg = LOT_CONFIG.get(bundle.symbol, {})

        return f"""Define risk parameters for this MCX trade.

SIGNAL: {signal.action}
SYMBOL: {bundle.symbol} ({bundle.contract})
CURRENT PRICE: Rs{ltp:,.2f}
ATR(14): {atr}

LOT DETAILS:
  Contract: {lot_cfg.get('friendly_name', bundle.symbol)}
  P&L per tick: Rs{lot_cfg.get('pl_per_tick', 'unknown')}
  Tick size: Rs{lot_cfg.get('tick_size', 1)}

ANALYST SUPPORT LEVELS: {analysis.key_support_levels}
ANALYST RESISTANCE LEVELS: {analysis.key_resistance_levels}

SIGNAL DETAILS:
  Action:     {signal.action}
  Confidence: {signal.confidence}%
  Quality:    {signal.signal_quality}
  Reason:     {signal.primary_reason}
  Timeframe:  {signal.recommended_timeframe}
  Invalidation: {signal.invalidation_condition}

ATR-BASED STOP LOSS FORMULA (use this):
  GOLDM BUY:      stop = entry - (1.5 × ATR)
  GOLDM SELL:     stop = entry + (1.5 × ATR)
  CRUDEOILM BUY:  stop = entry - (2.0 × ATR)
  CRUDEOILM SELL: stop = entry + (2.0 × ATR)

Return a JSON object with these exact fields:
{{
    "entry_price": float,
    "entry_type": "market | limit",
    "stop_loss": float,
    "stop_loss_basis": "ATR | support_level | percentage",
    "target_1": float,
    "target_2": float,
    "risk_reward_ratio": float,
    "max_hold_duration": "string e.g. same session | 2 days | 5 days",
    "exit_conditions": ["condition1", "condition2"],
    "margin_required_approx": float,
    "execution_notes": "slippage warnings, time of day, liquidity notes",
    "risk_approved": true | false,
    "risk_block_reason": "string or null"
}}"""