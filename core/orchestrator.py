"""
COMMODEX — Signal Orchestrator
Wires together the full 3-agent pipeline.
Single entry point for signal generation.

Flow:
  DataBundle → Agent1 (Analyst) → SanityChecker →
  Agent2 (Signal) → Agent3 (Risk) → SignalResult
"""

import logging
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional

from core.llm_client import LLMClient, MarketAnalysis, SignalDecision, RiskParameters
from core.agents.analyst_agent import AnalystAgent, SanityChecker
from core.agents.signal_agent import SignalAgent
from core.agents.risk_agent import RiskAgent
from core.data_bundle import DataBundle, DataBundleAssembler
from core.groww_client import GrowwClient
from core.technical_engine import TechnicalEngine
from core.news_client import NewsClient
from config import (
    TRADING_MODE, ACTIVE_LLM,
    MIN_CONFIDENCE_THRESHOLD,
    get_position_size,
)

logger = logging.getLogger(__name__)


@dataclass
class SignalResult:
    """
    Complete output from one signal generation run.
    Persisted to signals_log table.
    """
    # Request
    symbol:           str
    contract:         str
    timeframe:        str
    trading_style:    str
    mode:             str
    llm_provider:     str
    llm_model:        str
    timestamp:        str = field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

    # Agent outputs
    analysis:         Optional[MarketAnalysis]  = None
    signal:           Optional[SignalDecision]  = None
    risk:             Optional[RiskParameters]  = None
    position_sizing:  Optional[dict]            = None

    # Final decision
    final_action:     str  = "HOLD"
    final_confidence: int  = 0
    approved:         bool = False
    block_reason:     Optional[str] = None

    # Sanity check
    sanity_passed:    bool = True
    sanity_warnings:  list = field(default_factory=list)

    # Data quality
    data_quality:     str  = "unknown"
    confidence_cap:   int  = 100

    # Error tracking
    error:            Optional[str] = None
    pipeline_stage:   str  = "complete"

    def to_display_dict(self) -> dict:
        """Clean dict for Streamlit display."""
        return {
            "symbol":         self.symbol,
            "timestamp":      self.timestamp,
            "action":         self.final_action,
            "confidence":     self.final_confidence,
            "quality":        self.signal.signal_quality if self.signal else "N/A",
            "approved":       self.approved,
            "regime":         self.analysis.market_regime if self.analysis else "N/A",
            "sentiment":      self.analysis.overall_sentiment if self.analysis else "N/A",
            "primary_reason": self.signal.primary_reason if self.signal else "N/A",
            "entry":          self.risk.entry_price if self.risk else None,
            "stop_loss":      self.risk.stop_loss if self.risk else None,
            "target_1":       self.risk.target_1 if self.risk else None,
            "target_2":       self.risk.target_2 if self.risk else None,
            "rr_ratio":       self.risk.risk_reward_ratio if self.risk else None,
            "lots":           self.position_sizing.get("position_lots") if self.position_sizing else None,
            "risk_inr":       self.position_sizing.get("actual_risk_inr") if self.position_sizing else None,
            "block_reason":   self.block_reason,
            "data_quality":   self.data_quality,
        }


class SignalOrchestrator:
    """
    Orchestrates the full signal generation pipeline.
    Handles partial failures gracefully.
    Default output is always HOLD on any failure.
    """

    def __init__(self):
        self._llm       = LLMClient()
        self._analyst   = AnalystAgent(self._llm)
        self._sanity    = SanityChecker()
        self._signal    = SignalAgent(self._llm)
        self._risk      = RiskAgent(self._llm)
        self._groww     = GrowwClient()
        self._tech      = TechnicalEngine()
        self._news      = NewsClient()
        self._assembler = DataBundleAssembler(
            self._groww, self._tech, self._news
        )
        logger.info(
            f"SignalOrchestrator ready — "
            f"mode={TRADING_MODE} provider={ACTIVE_LLM['provider']}"
        )

    def generate(
        self,
        symbol:        str,
        timeframe:     str = "15minute",
        trading_style: str = "system",
    ) -> SignalResult:
        """
        Run the full 3-agent pipeline for one commodity.
        Returns SignalResult — never raises.
        """
        result = SignalResult(
            symbol        = symbol,
            contract      = "",
            timeframe     = timeframe,
            trading_style = trading_style,
            mode          = TRADING_MODE,
            llm_provider  = ACTIVE_LLM["provider"],
            llm_model     = ACTIVE_LLM["model"],
        )

        # ── Stage 1: Data Bundle ───────────────────────────
        try:
            logger.info(f"Stage 1: Assembling data bundle for {symbol}")
            bundle = self._assembler.assemble(
                symbol=symbol,
                timeframe=timeframe,
                trading_style=trading_style,
            )
            result.contract      = bundle.contract
            result.data_quality  = bundle.data_quality
            result.confidence_cap = bundle.confidence_cap
            result.pipeline_stage = "data_complete"
        except Exception as e:
            result.error         = f"Data assembly failed: {e}"
            result.pipeline_stage = "data_failed"
            result.block_reason  = "Data unavailable — defaulting to HOLD"
            logger.error(result.error)
            return result

        # ── Stage 2: Agent 1 — Market Analyst ─────────────
        try:
            logger.info("Stage 2: Running Market Analyst")
            analysis        = self._analyst.analyse(bundle)
            result.analysis = analysis
            result.pipeline_stage = "analyst_complete"
        except Exception as e:
            result.error         = f"Analyst agent failed: {e}"
            result.pipeline_stage = "analyst_failed"
            result.block_reason  = "Analysis failed — defaulting to HOLD"
            logger.error(result.error)
            return result

        # ── Stage 2b: Sanity Checker ───────────────────────
        sanity = self._sanity.check(analysis, bundle)
        result.sanity_passed   = sanity["passed"]
        result.sanity_warnings = sanity["warnings"]

        # ── Stage 3: Agent 2 — Signal Generator ───────────
        try:
            logger.info("Stage 3: Running Signal Generator")
            signal        = self._signal.generate(
                bundle, analysis, sanity, trading_style
            )
            result.signal = signal
            result.pipeline_stage = "signal_complete"
        except Exception as e:
            result.error         = f"Signal agent failed: {e}"
            result.pipeline_stage = "signal_failed"
            result.block_reason  = "Signal generation failed — defaulting to HOLD"
            logger.error(result.error)
            return result

        # ── Confidence threshold check ─────────────────────
        if signal.confidence < MIN_CONFIDENCE_THRESHOLD:
            result.final_action     = "HOLD"
            result.final_confidence = signal.confidence
            result.block_reason     = (
                f"Confidence {signal.confidence}% below "
                f"minimum threshold {MIN_CONFIDENCE_THRESHOLD}%"
            )
            logger.info(result.block_reason)
            return result

        # ── Stage 4: Agent 3 — Risk Assessor ──────────────
        try:
            logger.info("Stage 4: Running Risk Assessor")
            risk_result          = self._risk.assess(bundle, analysis, signal)
            result.risk          = risk_result["risk_params"]
            result.position_sizing = risk_result["position_sizing"]
            result.approved      = risk_result["final_approved"]
            result.block_reason  = risk_result["block_reason"]
            result.pipeline_stage = "risk_complete"
        except Exception as e:
            result.error         = f"Risk agent failed: {e}"
            result.pipeline_stage = "risk_failed"
            result.block_reason  = "Risk assessment failed — defaulting to HOLD"
            logger.error(result.error)
            return result

        # ── Final signal ───────────────────────────────────
        result.final_action     = signal.action if result.approved else "HOLD"
        result.final_confidence = signal.confidence
        result.pipeline_stage   = "complete"

        logger.info(
            f"Pipeline complete: {symbol} | "
            f"{result.final_action} | "
            f"confidence={result.final_confidence}% | "
            f"approved={result.approved}"
        )
        return result