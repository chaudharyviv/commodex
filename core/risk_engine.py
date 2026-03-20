"""
COMMODEX — Risk Engine
Enforces all 10 guardrails before any signal is approved.
All guardrails are hardcoded — cannot be overridden by LLM output.

Called by the Orchestrator after Agent 3 completes.
Also called independently by the Streamlit UI for pre-checks.
"""
import os
import logging
from datetime import datetime, date
from zoneinfo import ZoneInfo
from typing import Optional

from config import (
    TRADING_MODE,
    CAPITAL_INR,
    DAILY_LOSS_LIMIT_PCT,
    MAX_OPEN_POSITIONS,
    MIN_CONFIDENCE_THRESHOLD,
    MIN_RR_RATIO,
    MCX_OPEN_TIME,
    MCX_CLOSE_TIME,
    INTRADAY_SIGNAL_CUTOFF_TIME,
    EXPIRY_BLACKOUT_DAYS,
    INR_VOLATILITY_GATE_PCT,
    CONFIDENCE_CAP_HIGH_IMPACT,
    CONFIDENCE_CAP_INR_VOLATILE,
    LOT_CONFIG,
)
from core.db import get_connection

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")



class GuardrailResult:
    """Result from a single guardrail check."""
    def __init__(
        self,
        name:    str,
        passed:  bool,
        reason:  str = "",
        cap:     Optional[int] = None,
    ):
        self.name   = name
        self.passed = passed
        self.reason = reason
        self.cap    = cap       # confidence cap if applicable

    def __repr__(self):
        status = "PASS" if self.passed else "BLOCK"
        return f"[{status}] {self.name}: {self.reason}"


class RiskEngine:
    """
    Enforces all 10 guardrails.
    Call check_all() before displaying or acting on any signal.
    """

    def check_all(
        self,
        symbol:         str,
        action:         str,
        confidence:     int,
        rr_ratio:       Optional[float],
        trading_style:  str,
        inr_change_pct: Optional[float],
        contract_expiry: Optional[str],
        high_impact_event: Optional[str],
        open_positions: int = 0,
        daily_pnl_pct:  float = 0.0,
    ) -> dict:
        """
        Run all applicable guardrails.
        Returns:
        {
            "approved":          bool,
            "block_reasons":     [str, ...],
            "confidence_cap":    int,
            "cap_reasons":       [str, ...],
            "guardrail_results": [GuardrailResult, ...]
        }
        """
        results      = []
        block_reasons = []
        cap           = 100
        cap_reasons   = []

        # ── G1: Daily Loss Limit ───────────────────────────
        g1 = self._g1_daily_loss(daily_pnl_pct)
        results.append(g1)
        if not g1.passed:
            block_reasons.append(g1.reason)

        # ── G2: Max Open Positions ─────────────────────────
        g2 = self._g2_max_positions(open_positions, action)
        results.append(g2)
        if not g2.passed:
            block_reasons.append(g2.reason)

        # ── G3: Min Confidence ─────────────────────────────
        g3 = self._g3_min_confidence(confidence)
        results.append(g3)
        if not g3.passed:
            block_reasons.append(g3.reason)

        # ── G4: Market Hours ───────────────────────────────
        g4 = self._g4_market_hours()
        results.append(g4)
        if not g4.passed:
            block_reasons.append(g4.reason)

        # ── G5: High Impact Event ──────────────────────────
        g5 = self._g5_high_impact(high_impact_event)
        results.append(g5)
        if not g5.passed:
            block_reasons.append(g5.reason)
        if g5.cap and g5.cap < cap:
            cap = g5.cap
            cap_reasons.append(g5.reason)

        # ── G6: Minimum R:R ───────────────────────────────
        g6 = self._g6_min_rr(rr_ratio)
        results.append(g6)
        if not g6.passed:
            block_reasons.append(g6.reason)

        # ── G7: Production Confirmation ───────────────────
        g7 = self._g7_production_check()
        results.append(g7)
        if not g7.passed:
            block_reasons.append(g7.reason)

        # ── G8: Expiry Week ────────────────────────────────
        g8 = self._g8_expiry_week(contract_expiry)
        results.append(g8)
        if not g8.passed:
            block_reasons.append(g8.reason)

        # ── G9: INR/USD Volatility ─────────────────────────
        g9 = self._g9_inr_volatility(inr_change_pct)
        results.append(g9)
        if g9.cap and g9.cap < cap:
            cap = g9.cap
            cap_reasons.append(g9.reason)

        # ── G10: Session Boundary ──────────────────────────
        g10 = self._g10_session_boundary(trading_style)
        results.append(g10)
        if not g10.passed:
            block_reasons.append(g10.reason)

        approved = len(block_reasons) == 0 and action != "HOLD"

        if block_reasons:
            logger.warning(
                f"Guardrails BLOCKED {symbol} {action}: "
                f"{block_reasons}"
            )
        else:
            logger.info(f"All guardrails passed for {symbol} {action}")

        return {
            "approved":          approved,
            "block_reasons":     block_reasons,
            "confidence_cap":    cap,
            "cap_reasons":       cap_reasons,
            "guardrail_results": results,
        }

    # ── Individual Guardrails ──────────────────────────────

    def _g1_daily_loss(self, daily_pnl_pct: float) -> GuardrailResult:
        """G1: Block if daily loss exceeds limit."""
        limit = DAILY_LOSS_LIMIT_PCT
        if daily_pnl_pct <= -limit:
            return GuardrailResult(
                name   = "G1_DailyLoss",
                passed = False,
                reason = (
                    f"Daily loss limit reached: {daily_pnl_pct:.1f}% "
                    f"(limit: -{limit}%). No new signals until tomorrow."
                )
            )
        return GuardrailResult(
            name   = "G1_DailyLoss",
            passed = True,
            reason = f"Daily P&L: {daily_pnl_pct:.1f}% (limit: -{limit}%)"
        )

    def _g2_max_positions(
        self, open_positions: int, action: str
    ) -> GuardrailResult:
        """G2: Block if max open positions reached."""
        if action != "HOLD" and open_positions >= MAX_OPEN_POSITIONS:
            return GuardrailResult(
                name   = "G2_MaxPositions",
                passed = False,
                reason = (
                    f"Max open positions reached: {open_positions} "
                    f"(limit: {MAX_OPEN_POSITIONS})"
                )
            )
        return GuardrailResult(
            name   = "G2_MaxPositions",
            passed = True,
            reason = f"Open positions: {open_positions}/{MAX_OPEN_POSITIONS}"
        )

    def _g3_min_confidence(self, confidence: int) -> GuardrailResult:
        """G3: Block if confidence below minimum threshold."""
        if confidence < MIN_CONFIDENCE_THRESHOLD:
            return GuardrailResult(
                name   = "G3_MinConfidence",
                passed = False,
                reason = (
                    f"Confidence {confidence}% below "
                    f"minimum {MIN_CONFIDENCE_THRESHOLD}%"
                )
            )
        return GuardrailResult(
            name   = "G3_MinConfidence",
            passed = True,
            reason = f"Confidence {confidence}% ≥ {MIN_CONFIDENCE_THRESHOLD}%"
        )

    def _g4_market_hours(self) -> GuardrailResult:
        """G4: Block signals outside MCX market hours."""
        now_ist  = datetime.now(IST)
        now_time = now_ist.strftime("%H:%M")

        if MCX_OPEN_TIME <= now_time <= MCX_CLOSE_TIME:
            return GuardrailResult(
                name   = "G4_MarketHours",
                passed = True,
                reason = f"Market open: {now_time} IST"
            )
        return GuardrailResult(
            name   = "G4_MarketHours",
            passed = False,
            reason = (
                f"MCX market closed at {now_time} IST. "
                f"Hours: {MCX_OPEN_TIME}–{MCX_CLOSE_TIME} IST"
            )
        )

    def _g5_high_impact(
        self, high_impact_event: Optional[str]
    ) -> GuardrailResult:
        """G5: Cap confidence when high impact event is flagged."""
        if high_impact_event:
            return GuardrailResult(
                name   = "G5_HighImpact",
                passed = True,   # not a block — just a cap
                reason = (
                    f"High impact event: {high_impact_event} "
                    f"— confidence capped at {CONFIDENCE_CAP_HIGH_IMPACT}%"
                ),
                cap    = CONFIDENCE_CAP_HIGH_IMPACT,
            )
        return GuardrailResult(
            name   = "G5_HighImpact",
            passed = True,
            reason = "No high impact events in next 24h"
        )

    def _g6_min_rr(self, rr_ratio: Optional[float]) -> GuardrailResult:
        """G6: Block if R:R ratio below minimum."""
        if rr_ratio is None:
            return GuardrailResult(
                name   = "G6_MinRR",
                passed = True,
                reason = "R:R not yet computed (HOLD signal)"
            )
        if rr_ratio < MIN_RR_RATIO:
            return GuardrailResult(
                name   = "G6_MinRR",
                passed = False,
                reason = (
                    f"R:R ratio {rr_ratio:.1f} below "
                    f"minimum {MIN_RR_RATIO}"
                )
            )
        return GuardrailResult(
            name   = "G6_MinRR",
            passed = True,
            reason = f"R:R ratio {rr_ratio:.1f} ≥ {MIN_RR_RATIO}"
        )

    def _g7_production_check(self) -> GuardrailResult:
        """G7: In production mode, verify confirmation flag is set."""
        if TRADING_MODE != "production":
            return GuardrailResult(
                name   = "G7_ProductionCheck",
                passed = True,
                reason = f"Mode: {TRADING_MODE} (not production)"
            )
        confirmed = os.getenv("PRODUCTION_CONFIRMED", "false").lower()
        if confirmed != "true":
            return GuardrailResult(
                name   = "G7_ProductionCheck",
                passed = False,
                reason = (
                    "Production mode requires explicit confirmation. "
                    "Type 'CONFIRM REAL MONEY' in Settings."
                )
            )
        return GuardrailResult(
            name   = "G7_ProductionCheck",
            passed = True,
            reason = "Production confirmed"
        )

    def _g8_expiry_week(
        self, contract_expiry: Optional[str]
    ) -> GuardrailResult:
        """G8: Block signals in final N days before contract expiry."""
        if not contract_expiry:
            return GuardrailResult(
                name   = "G8_ExpiryWeek",
                passed = True,
                reason = "Expiry date not provided"
            )
        try:
            if hasattr(contract_expiry, 'date'):
                expiry_date = contract_expiry.date()
            else:
                expiry_date = datetime.strptime(
                    str(contract_expiry)[:10], "%Y-%m-%d"
                ).date()

            today       = datetime.now(IST).date()
            days_to_exp = (expiry_date - today).days

            if days_to_exp <= EXPIRY_BLACKOUT_DAYS:
                return GuardrailResult(
                    name   = "G8_ExpiryWeek",
                    passed = False,
                    reason = (
                        f"Contract expires in {days_to_exp} day(s) "
                        f"({expiry_date}). Blackout: last "
                        f"{EXPIRY_BLACKOUT_DAYS} days. "
                        f"Consider rolling to next contract."
                    )
                )
            return GuardrailResult(
                name   = "G8_ExpiryWeek",
                passed = True,
                reason = f"Expiry in {days_to_exp} days ({expiry_date})"
            )
        except Exception as e:
            return GuardrailResult(
                name   = "G8_ExpiryWeek",
                passed = True,
                reason = f"Expiry check skipped: {e}"
            )

    def _g9_inr_volatility(
        self, inr_change_pct: Optional[float]
    ) -> GuardrailResult:
        """G9: Cap confidence when INR/USD moves > gate threshold."""
        if inr_change_pct is None:
            return GuardrailResult(
                name   = "G9_INRVolatility",
                passed = True,
                reason = "INR/USD data unavailable"
            )
        abs_change = abs(inr_change_pct)
        if abs_change >= INR_VOLATILITY_GATE_PCT:
            return GuardrailResult(
                name   = "G9_INRVolatility",
                passed = True,   # cap not block
                reason = (
                    f"INR/USD moved {inr_change_pct:+.3f}% "
                    f"(gate: ±{INR_VOLATILITY_GATE_PCT}%) "
                    f"— confidence capped at {CONFIDENCE_CAP_INR_VOLATILE}%"
                ),
                cap    = CONFIDENCE_CAP_INR_VOLATILE,
            )
        return GuardrailResult(
            name   = "G9_INRVolatility",
            passed = True,
            reason = (
                f"INR/USD stable: {inr_change_pct:+.3f}% "
                f"(gate: ±{INR_VOLATILITY_GATE_PCT}%)"
            )
        )

    def _g10_session_boundary(self, trading_style: str) -> GuardrailResult:
        """G10: Block intraday signals after cutoff time."""
        if trading_style not in ("intraday", "system"):
            return GuardrailResult(
                name   = "G10_SessionBoundary",
                passed = True,
                reason = f"Style={trading_style} — no session cutoff applies"
            )
        now_ist  = datetime.now(IST)
        now_time = now_ist.strftime("%H:%M")

        if now_time > INTRADAY_SIGNAL_CUTOFF_TIME:
            return GuardrailResult(
                name   = "G10_SessionBoundary",
                passed = False,
                reason = (
                    f"Intraday signal cutoff passed: {now_time} IST "
                    f"(cutoff: {INTRADAY_SIGNAL_CUTOFF_TIME}). "
                    f"Overnight gap risk — no new intraday signals."
                )
            )
        return GuardrailResult(
            name   = "G10_SessionBoundary",
            passed = True,
            reason = (
                f"Within intraday window: {now_time} IST "
                f"(cutoff: {INTRADAY_SIGNAL_CUTOFF_TIME})"
            )
        )

    def get_daily_pnl_pct(self) -> float:
        """Fetch today's realised P&L % from SQLite trades_log."""
        try:
            conn   = get_connection()
            cursor = conn.cursor()
            today  = date.today().isoformat()
            cursor.execute("""
                SELECT COALESCE(SUM(pnl_inr), 0) as total_pnl
                FROM trades_log
                WHERE DATE(entry_time) = ?
                AND mode = ?
            """, (today, TRADING_MODE))
            row       = cursor.fetchone()
            conn.close()
            total_pnl = float(row["total_pnl"]) if row else 0.0
            return round(total_pnl / CAPITAL_INR * 100, 3)
        except Exception as e:
            logger.warning(f"Daily P&L fetch failed: {e}")
            return 0.0

    def get_open_positions_count(self) -> int:
        """Count currently open positions from SQLite trades_log."""
        try:
            conn   = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) as cnt
                FROM trades_log
                WHERE exit_time IS NULL
                AND mode = ?
            """, (TRADING_MODE,))
            row  = cursor.fetchone()
            conn.close()
            return int(row["cnt"]) if row else 0
        except Exception as e:
            logger.warning(f"Open positions fetch failed: {e}")
            return 0