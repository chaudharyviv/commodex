"""
COMMODEX — Shared UI Helpers
Reusable Streamlit components used across all pages.
Import these instead of duplicating display logic.
"""

import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo
from config import TRADING_MODE, LOT_CONFIG

IST = ZoneInfo("Asia/Kolkata")


# ─────────────────────────────────────────────────────────────────
# MODE BADGE
# ─────────────────────────────────────────────────────────────────

def render_mode_badge():
    """Render trading mode badge in sidebar."""
    badges = {
        "demo":       ("🟡", "DEMO MODE",        "warning"),
        "paper":      ("🔵", "PAPER TRADING",     "info"),
        "production": ("🔴", "PRODUCTION — LIVE", "error"),
    }
    icon, label, kind = badges.get(
        TRADING_MODE, ("⚪", TRADING_MODE.upper(), "info")
    )
    getattr(st, kind)(f"{icon} {label}")


# ─────────────────────────────────────────────────────────────────
# MARKET STATUS
# ─────────────────────────────────────────────────────────────────

def get_market_status() -> dict:
    """Return current MCX market status."""
    now      = datetime.now(IST)
    now_time = now.strftime("%H:%M")
    is_open  = "09:00" <= now_time <= "23:30"
    return {
        "is_open":    is_open,
        "time_ist":   now.strftime("%H:%M:%S IST"),
        "date":       now.strftime("%d %b %Y"),
        "label":      "🟢 OPEN" if is_open else "🔴 CLOSED",
    }


def render_market_status():
    """Render market status pill."""
    status = get_market_status()
    if status["is_open"]:
        st.success(f"MCX {status['label']}  |  {status['time_ist']}")
    else:
        st.error(f"MCX {status['label']}  |  {status['time_ist']}")


# ─────────────────────────────────────────────────────────────────
# SIGNAL BADGE
# ─────────────────────────────────────────────────────────────────

def render_signal_badge(action: str, confidence: int, quality: str):
    """Render a coloured signal badge."""
    if action == "BUY":
        st.success(f"▲ BUY  |  {confidence}% confidence  |  Grade {quality}")
    elif action == "SELL":
        st.error(f"▼ SELL  |  {confidence}% confidence  |  Grade {quality}")
    else:
        st.warning(f"◆ HOLD  |  {confidence}% confidence  |  Grade {quality}")


# ─────────────────────────────────────────────────────────────────
# TECHNICAL INDICATORS TABLE
# ─────────────────────────────────────────────────────────────────

def render_technicals(tech_data):
    """Render technical indicators using markdown — no truncation."""
    if not tech_data:
        st.info("No technical data available")
        return

    def fmt_price(val):
        if val is None:
            return "N/A"
        return f"Rs{val:,.0f}"

    def fmt_val(val, suffix=""):
        if val is None:
            return "N/A"
        return f"{val}{suffix}"

    # ── Momentum & Trend ──────────────────────────────────
    st.markdown("#### Momentum & Trend")
    mt = st.columns(4)
    with mt[0]:
        st.markdown(f"**RSI (14)**")
        st.markdown(f"### {fmt_val(tech_data.rsi_14)}")
        st.caption(tech_data.rsi_signal or "")
    with mt[1]:
        st.markdown(f"**MACD**")
        st.markdown(f"### {tech_data.macd_cross or 'N/A'}")
        st.caption(f"hist = {tech_data.macd_histogram}")
    with mt[2]:
        st.markdown(f"**EMA 20**")
        st.markdown(f"### {fmt_price(tech_data.ema_20)}")
        st.caption(f"EMA 50: {fmt_price(tech_data.ema_50)}")
    with mt[3]:
        st.markdown(f"**EMA Trend**")
        trend = (tech_data.ema_trend or "N/A").replace("_", " ")
        st.markdown(f"### {trend[:12]}")
        st.caption(trend if len(trend) > 12 else "")

    st.divider()

    # ── Bollinger Bands ───────────────────────────────────
    st.markdown("#### Bollinger Bands")
    bb = st.columns(4)
    with bb[0]:
        st.markdown("**BB Upper**")
        st.markdown(f"### {fmt_price(tech_data.bb_upper)}")
        st.caption(f"Lower: {fmt_price(tech_data.bb_lower)}")
    with bb[1]:
        st.markdown("**BB Mid**")
        st.markdown(f"### {fmt_price(tech_data.bb_mid)}")
        st.caption(f"Width: {fmt_val(tech_data.bb_width, '%')}")
    with bb[2]:
        st.markdown("**BB Position**")
        pos = (tech_data.bb_position or "N/A").replace("_", " ")
        st.markdown(f"**{pos}**")
    with bb[3]:
        st.markdown("**ATR (14)**")
        st.markdown(f"### {fmt_price(tech_data.atr_14)}")
        st.caption(f"{fmt_val(tech_data.atr_pct, '% of price')}")

    st.divider()

    # ── Key Levels ────────────────────────────────────────
    st.markdown("#### Key Levels")
    kl = st.columns(4)
    with kl[0]:
        st.markdown("**Pivot**")
        st.markdown(f"### {fmt_price(tech_data.pivot)}")
    with kl[1]:
        st.markdown("**Resistance**")
        st.markdown(f"R1: **{fmt_price(tech_data.r1)}**")
        st.markdown(f"R2: **{fmt_price(tech_data.r2)}**")
    with kl[2]:
        st.markdown("**Support**")
        st.markdown(f"S1: **{fmt_price(tech_data.s1)}**")
        st.markdown(f"S2: **{fmt_price(tech_data.s2)}**")
    with kl[3]:
        st.markdown("**Volume**")
        vol = f"{tech_data.volume_current:,}" if tech_data.volume_current else "N/A"
        avg = f"{tech_data.volume_avg_20:,.0f}" if tech_data.volume_avg_20 else "N/A"
        st.markdown(f"### {vol}")
        st.caption(f"Avg20: {avg} [{tech_data.volume_signal or 'N/A'}]")

    st.divider()

    # ── Day Range ─────────────────────────────────────────
    st.markdown("#### Day Range")
    dr = st.columns(4)
    with dr[0]:
        st.markdown("**Day High**")
        st.markdown(f"### {fmt_price(tech_data.day_high)}")
    with dr[1]:
        st.markdown("**Day Low**")
        st.markdown(f"### {fmt_price(tech_data.day_low)}")
    with dr[2]:
        st.markdown("**Prev Day High**")
        st.markdown(f"### {fmt_price(tech_data.prev_day_high)}")
    with dr[3]:
        st.markdown("**Prev Day Low**")
        st.markdown(f"### {fmt_price(tech_data.prev_day_low)}")

# ─────────────────────────────────────────────────────────────────
# RISK PARAMETERS TABLE
# ─────────────────────────────────────────────────────────────────

def render_risk_params(risk, position_sizing):
    """Render risk parameters in a clean table."""
    if not risk:
        st.info("No risk parameters — HOLD signal")
        return

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Entry", f"Rs{risk.entry_price:,.2f}")
        st.metric("Entry Type", risk.entry_type.upper())
    with col2:
        st.metric("Stop Loss", f"Rs{risk.stop_loss:,.2f}")
        st.metric("SL Basis", risk.stop_loss_basis)
    with col3:
        st.metric("Target 1", f"Rs{risk.target_1:,.2f}")
        st.metric("Target 2", f"Rs{risk.target_2:,.2f}")
    with col4:
        st.metric("R:R Ratio", f"{risk.risk_reward_ratio:.1f}:1")
        st.metric("Max Hold", risk.max_hold_duration)

    if position_sizing:
        st.divider()
        pc1, pc2, pc3, pc4 = st.columns(4)
        with pc1:
            st.metric("Position", f"{position_sizing['position_lots']} lot(s)")
        with pc2:
            st.metric("Capital at Risk",
                f"Rs{position_sizing['actual_risk_inr']:,.0f}")
        with pc3:
            st.metric("Risk %",
                f"{position_sizing['actual_risk_pct']}%")
        with pc4:
            st.metric("Margin Est.",
                f"Rs{position_sizing['margin_est_inr']:,.0f}")

    if risk.execution_notes:
        st.caption(f"📌 {risk.execution_notes}")


# ─────────────────────────────────────────────────────────────────
# GUARDRAIL STATUS
# ─────────────────────────────────────────────────────────────────

def render_guardrails(guardrail_results: list):
    """Render guardrail status grid."""
    if not guardrail_results:
        return
    cols = st.columns(5)
    for i, gr in enumerate(guardrail_results):
        with cols[i % 5]:
            icon = "✅" if gr.passed else "🚫"
            name = gr.name.replace("G", "").replace("_", " ", 1)
            st.caption(f"{icon} {name}")


# ─────────────────────────────────────────────────────────────────
# SIDEBAR STANDARD
# ─────────────────────────────────────────────────────────────────

def render_sidebar():
    """Render standard sidebar content for all pages."""
    with st.sidebar:
        st.title("⬡ COMMODEX")
        render_mode_badge()
        st.divider()
        render_market_status()
        st.divider()
        st.caption("Navigate:")
        st.markdown("🏠 [Home](/)  ")
        st.markdown("📊 [Dashboard](/Dashboard)")
        st.markdown("⚡ [Signal Engine](/Signal_Engine)")
        st.markdown("📋 [Trade Log](/Trade_Log)")
        st.markdown("🔬 [Backtest](/Backtest)")
        st.markdown("⚙ [Settings](/Settings)")
        st.divider()
        st.caption(
            f"v1.0 | Phase 5 | "
            f"{datetime.now(IST).strftime('%d %b %Y')}"
        )