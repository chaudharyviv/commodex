"""
COMMODEX — Shared UI Helpers v2.0
Reusable Streamlit components used across all pages.
Import these instead of duplicating display logic.

v2.0: Added rendering for VWAP, ADX, StochRSI, Supertrend,
      Fibonacci, OI, RSI divergence, BB squeeze, volume-price confirm
"""

import streamlit as st
from datetime import datetime
from zoneinfo import ZoneInfo
from config import TRADING_MODE, LOT_CONFIG
from core.market_hours import get_market_schedule_text, is_market_open

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
    now = datetime.now(IST)
    is_open = is_market_open(now)
    return {
        "is_open":    is_open,
        "time_ist":   now.strftime("%H:%M:%S IST"),
        "date":       now.strftime("%d %b %Y"),
        "day":        now.strftime("%A"),
        "label":      "🟢 OPEN" if is_open else "🔴 CLOSED",
        "schedule":   get_market_schedule_text(),
    }


def render_market_status():
    """Render market status pill."""
    status = get_market_status()
    message = (
        f"MCX {status['label']}  |  {status['time_ist']}  |  "
        f"{status['day']}  |  {status['schedule']}"
    )
    if status["is_open"]:
        st.success(message)
    else:
        st.error(message)


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
# TECHNICAL INDICATORS TABLE v2.0
# ─────────────────────────────────────────────────────────────────

def render_technicals(tech_data):
    """Render technical indicators — full v2.0 indicator set."""
    if not tech_data:
        st.info("No technical data available")
        return

    def fmt_price(val):
        if val is None:
            return "N/A"
        return f"₹{val:,.0f}"

    def fmt_val(val, suffix=""):
        if val is None:
            return "N/A"
        return f"{val}{suffix}"

    # ── Trend Strength (ADX) + Supertrend ─────────────
    if tech_data.adx_14 is not None or tech_data.supertrend is not None:
        st.markdown("#### Trend Strength")
        ts = st.columns(4)
        with ts[0]:
            st.markdown("**ADX (14)**")
            st.markdown(f"### {fmt_val(tech_data.adx_14)}")
            st.caption(tech_data.adx_signal or "")
        with ts[1]:
            st.markdown("**+DI / -DI**")
            st.markdown(
                f"### +{fmt_val(tech_data.plus_di)} / -{fmt_val(tech_data.minus_di)}"
            )
            st.caption(tech_data.di_cross or "")
        with ts[2]:
            st.markdown("**Supertrend**")
            st.markdown(f"### {fmt_price(tech_data.supertrend)}")
            flip = " ⚡FLIP" if tech_data.supertrend_flip else ""
            st.caption(f"{tech_data.supertrend_dir or 'N/A'}{flip}")
        with ts[3]:
            st.markdown("**EMA 200**")
            st.markdown(f"### {fmt_price(tech_data.ema_200)}")
            st.caption(
                (tech_data.ema_200_trend or "N/A").replace("_", " ")
            )
        st.divider()

    # ── Momentum & Trend ──────────────────────────────
    st.markdown("#### Momentum & Trend")
    mt = st.columns(4)
    with mt[0]:
        st.markdown("**RSI (14)**")
        st.markdown(f"### {fmt_val(tech_data.rsi_14)}")
        div_tag = ""
        if tech_data.rsi_divergence and tech_data.rsi_divergence != "none":
            div_tag = f" | ⚠ {tech_data.rsi_divergence} div"
        st.caption(f"{tech_data.rsi_signal or ''}{div_tag}")
    with mt[1]:
        st.markdown("**StochRSI**")
        if tech_data.stoch_rsi_k is not None:
            st.markdown(
                f"### K={tech_data.stoch_rsi_k:.0f} D={tech_data.stoch_rsi_d:.0f}"
            )
            st.caption(tech_data.stoch_rsi_signal or "")
        else:
            st.markdown("### N/A")
    with mt[2]:
        st.markdown("**MACD**")
        st.markdown(f"### {tech_data.macd_cross or 'N/A'}")
        st.caption(f"hist = {tech_data.macd_histogram}")
    with mt[3]:
        st.markdown("**EMA 20 / 50**")
        st.markdown(f"### {fmt_price(tech_data.ema_20)}")
        st.caption(
            f"EMA 50: {fmt_price(tech_data.ema_50)} | "
            f"{(tech_data.ema_trend or 'N/A').replace('_', ' ')}"
        )
    st.divider()

    # ── VWAP ──────────────────────────────────────────
    if tech_data.vwap is not None:
        st.markdown("#### VWAP (Session)")
        vw = st.columns(4)
        with vw[0]:
            st.markdown("**VWAP**")
            st.markdown(f"### {fmt_price(tech_data.vwap)}")
            st.caption(
                (tech_data.vwap_position or "N/A").replace("_", " ")
            )
        with vw[1]:
            st.markdown("**±1σ Bands**")
            st.markdown(
                f"↑ {fmt_price(tech_data.vwap_upper_1)}  "
                f"↓ {fmt_price(tech_data.vwap_lower_1)}"
            )
        with vw[2]:
            st.markdown("**±2σ Bands**")
            st.markdown(
                f"↑ {fmt_price(tech_data.vwap_upper_2)}  "
                f"↓ {fmt_price(tech_data.vwap_lower_2)}"
            )
        with vw[3]:
            # Show price distance from VWAP as %
            if tech_data.vwap and tech_data.latest_price:
                dist = (
                    (tech_data.latest_price - tech_data.vwap)
                    / tech_data.vwap * 100
                )
                st.markdown("**Distance**")
                st.markdown(f"### {dist:+.2f}%")
                st.caption("from VWAP")
        st.divider()

    # ── Bollinger Bands ───────────────────────────────
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
        if tech_data.bb_squeeze:
            st.warning("⚠ SQUEEZE — breakout imminent")
    with bb[3]:
        st.markdown("**ATR (14)**")
        st.markdown(f"### {fmt_price(tech_data.atr_14)}")
        st.caption(f"{fmt_val(tech_data.atr_pct, '% of price')}")

    st.divider()

    # ── Key Levels + Fibonacci ────────────────────────
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
        st.markdown("**Day Range**")
        st.markdown(f"H: {fmt_price(tech_data.day_high)}")
        st.markdown(f"L: {fmt_price(tech_data.day_low)}")
        st.caption(
            f"PDH: {fmt_price(tech_data.prev_day_high)} | "
            f"PDL: {fmt_price(tech_data.prev_day_low)}"
        )

    # ── Fibonacci Retracement ─────────────────────────────
    if tech_data.fib_382:
        st.markdown("#### Fibonacci Retracement")
        trend_desc = (
            f"Swing down: H=Rs{tech_data.fib_swing_high:,.0f} "
            f"→ L=Rs{tech_data.fib_swing_low:,.0f}"
            if tech_data.fib_trend == "down"
            else
            f"Swing up: L=Rs{tech_data.fib_swing_low:,.0f} "
            f"→ H=Rs{tech_data.fib_swing_high:,.0f}"
        ) if tech_data.fib_swing_high and tech_data.fib_swing_low else ""
        st.caption(trend_desc)

        fc = st.columns(5)
        for col, (pct, val) in zip(fc, [
            ("23.6%", tech_data.fib_236),
            ("38.2%", tech_data.fib_382),
            ("50.0%", tech_data.fib_500),
            ("61.8%", tech_data.fib_618),
            ("78.6%", tech_data.fib_786),
        ]):
            with col:
                st.markdown(f"**{pct}**")
                st.markdown(
                    f"**Rs{val:,.0f}**" if val else "N/A"
                )
        st.divider()

    # ── Volume & OI ───────────────────────────────────────
    st.markdown("#### Volume & Open Interest")
    voi = st.columns(4)
    with voi[0]:
        st.markdown("**Volume**")
        vol = f"{tech_data.volume_current:,}" if tech_data.volume_current else "N/A"
        st.markdown(f"### {vol}")
        st.caption(
            f"Avg20: {tech_data.volume_avg_20:,.0f} "
            f"[{tech_data.volume_signal or 'N/A'}]"
            if tech_data.volume_avg_20 else ""
        )
    with voi[1]:
        st.markdown("**Vol-Price**")
        vpc = (tech_data.volume_price_confirm or "N/A").replace("_", " ")
        st.markdown(f"**{vpc}**")
    with voi[2]:
        st.markdown("**Open Interest**")
        if tech_data.oi_current and tech_data.oi_current > 0:
            st.markdown(f"### {tech_data.oi_current:,}")
            if tech_data.oi_change_pct is not None:
                direction = "▲" if tech_data.oi_change_pct > 0 else "▼"
                st.caption(
                    f"{direction} {abs(tech_data.oi_change_pct):.1f}% "
                    f"vs prev day"
                )
        else:
            st.markdown("### N/A")
            st.caption(
                "OI available during market hours only" 
                if tech_data.oi_current is None 
                else "OI data not in quote"
            )
    with voi[3]:
        st.markdown("**OI Signal**")
        if tech_data.oi_interpretation and tech_data.oi_interpretation != "neutral":
            oi_colors = {
                "fresh_longs":    "🟢",
                "short_covering": "🟡",
                "fresh_shorts":   "🔴",
                "long_unwinding": "🟠",
            }
            icon = oi_colors.get(tech_data.oi_interpretation, "⚪")
            label = tech_data.oi_interpretation.replace("_", " ").title()
            st.markdown(f"**{icon} {label}**")
        elif tech_data.oi_interpretation == "neutral":
            st.markdown("**⚪ Neutral**")
        else:
            st.markdown("**N/A**")
            st.caption("Market closed")
    st.divider()

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
        st.metric("Entry", f"₹{risk.entry_price:,.2f}")
        st.metric("Entry Type", risk.entry_type.upper())
    with col2:
        st.metric("Stop Loss", f"₹{risk.stop_loss:,.2f}")
        st.metric("SL Basis", risk.stop_loss_basis)
    with col3:
        st.metric("Target 1", f"₹{risk.target_1:,.2f}")
        st.metric("Target 2", f"₹{risk.target_2:,.2f}")
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
                f"₹{position_sizing['actual_risk_inr']:,.0f}")
        with pc3:
            st.metric("Risk %",
                f"{position_sizing['actual_risk_pct']}%")
        with pc4:
            st.metric("Margin Est.",
                f"₹{position_sizing['margin_est_inr']:,.0f}")

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
        selection = st.radio(
            "Navigation",
            options=["Home", "Dashboard", "Signal Engine", "Trade Log", "Settings"],
            label_visibility="collapsed"
        )
        st.divider()
        st.caption(
            f"v2.0 | Single Page | "
            f"{datetime.now(IST).strftime('%d %b %Y')}"
        )
        return selection
