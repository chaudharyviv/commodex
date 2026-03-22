from datetime import datetime as real_datetime

import core.risk_engine as risk_engine_module
from config import CONFIDENCE_CAP_INR_VOLATILE, EXPIRY_BLACKOUT_DAYS
from core.risk_engine import RiskEngine


class FixedDateTime(real_datetime):
    current = real_datetime(2026, 3, 22, 4, 30)

    @classmethod
    def now(cls, tz=None):
        dt = cls.current
        if tz is not None:
            return dt.replace(tzinfo=tz)
        return dt

    @classmethod
    def strptime(cls, date_string, fmt):
        return real_datetime.strptime(date_string, fmt)


def _freeze_time(monkeypatch, dt):
    FixedDateTime.current = dt
    monkeypatch.setattr(risk_engine_module, "datetime", FixedDateTime)


def _run_check(**overrides):
    engine = RiskEngine()
    payload = {
        "symbol": "GOLDM",
        "action": "BUY",
        "confidence": 72,
        "rr_ratio": 2.1,
        "trading_style": "system",
        "inr_change_pct": 0.1,
        "contract_expiry": "2026-03-29",
        "high_impact_event": None,
        "open_positions": 0,
        "daily_pnl_pct": 0.0,
    }
    payload.update(overrides)
    return engine.check_all(**payload)


def test_expiry_blackout_blocks_new_signal(monkeypatch):
    _freeze_time(monkeypatch, real_datetime(2026, 3, 22, 10, 0))

    result = _run_check(contract_expiry="2026-03-25")

    assert result["approved"] is False
    assert any("blackout" in reason.lower() for reason in result["block_reasons"])
    assert any(f"last {EXPIRY_BLACKOUT_DAYS} days" in reason for reason in result["block_reasons"])


def test_intraday_cutoff_blocks_late_evening_system_signal(monkeypatch):
    _freeze_time(monkeypatch, real_datetime(2026, 3, 22, 22, 15))

    result = _run_check(trading_style="intraday")

    assert result["approved"] is False
    assert any("cutoff" in reason.lower() for reason in result["block_reasons"])


def test_inr_volatility_caps_confidence_without_blocking(monkeypatch):
    _freeze_time(monkeypatch, real_datetime(2026, 3, 22, 14, 15))

    result = _run_check(inr_change_pct=0.72)

    assert result["approved"] is True
    assert result["confidence_cap"] == CONFIDENCE_CAP_INR_VOLATILE
    assert any("INR/USD moved" in reason for reason in result["cap_reasons"])
