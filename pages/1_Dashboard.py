"""
COMMODEX — Dashboard
Live prices, latest signals, daily summary, market alerts.
"""

import streamlit as st
import os
from dotenv import load_dotenv
load_dotenv()

from core.ui_helpers import render_sidebar, render_signal_badge
from core.db import get_connection, init as db_init
from core.inr_usd import get_inr_usd_rate
from config import TRADING_MODE, CAPITAL_INR

st.set_page_config(
    page_title="Dashboard — COMMODEX",
    page_icon="📊",
    layout="wide",
)

db_init()
render_sidebar()

st.title("📊 Dashboard")
st.caption("Live MCX prices and latest signals")

# ── Refresh button ─────────────────────────────────────────
if st.button("🔄 Refresh Prices", type="secondary"):
    st.cache_data.clear()
    st.rerun()

# ── Live Prices ────────────────────────────────────────────
st.subheader("Live MCX Prices")

@st.cache_data(ttl=30)   # refresh every 30 seconds
def fetch_live_prices():
    try:
        from generate_token import generate_totp_token, save_token_to_env
        token = generate_totp_token()
        save_token_to_env(token)
        os.environ["GROWW_ACCESS_TOKEN"] = token

        from core.groww_client import GrowwClient
        client = GrowwClient(access_token=token)

        gold  = client.find_active_contract("GOLDM")
        crude = client.find_active_contract("CRUDEOILM")

        prices = {}
        quotes = {}

        if gold and crude:
            symbols = [
                f"MCX_{gold['trading_symbol']}",
                f"MCX_{crude['trading_symbol']}",
            ]
            ltp = client.get_ltp(symbols)
            prices = ltp

            # Full quote for day change
            try:
                gq = client.get_quote(gold["trading_symbol"])
                cq = client.get_quote(crude["trading_symbol"])
                quotes = {
                    "GOLDM":     gq,
                    "CRUDEOILM": cq,
                }
            except Exception:
                pass

        return {
            "gold_symbol":  gold["trading_symbol"] if gold else None,
            "crude_symbol": crude["trading_symbol"] if crude else None,
            "prices":       prices,
            "quotes":       quotes,
        }
    except Exception as e:
        return {"error": str(e)}

with st.spinner("Fetching live prices..."):
    price_data = fetch_live_prices()

if "error" in price_data:
    st.error(f"Price fetch failed: {price_data['error']}")
else:
    col1, col2 = st.columns(2)

    # Gold
    with col1:
        st.markdown("### ◈ Gold Mini (GOLDM)")
        gold_sym = price_data.get("gold_symbol")
        if gold_sym:
            key = f"MCX_{gold_sym}"
            ltp = price_data["prices"].get(key, 0)
            quote = price_data["quotes"].get("GOLDM", {})
            day_change = quote.get("day_change_perc", 0) if quote else 0

            st.metric(
                label    = "LTP (per 10g)",
                value    = f"Rs{ltp:,.2f}",
                delta    = f"{day_change:+.2f}%" if day_change else None,
            )
            if quote:
                qc1, qc2 = st.columns(2)
                with qc1:
                    st.caption(f"Open: Rs{quote.get('ohlc', {}).get('open', 'N/A') if isinstance(quote.get('ohlc'), dict) else 'N/A'}")
                with qc2:
                    st.caption(f"Volume: {quote.get('volume', 'N/A'):,}" if quote.get("volume") else "Volume: N/A")
        else:
            st.warning("Gold contract not found")

    # Crude
    with col2:
        st.markdown("### ⬡ Crude Oil Mini (CRUDEOILM)")
        crude_sym = price_data.get("crude_symbol")
        if crude_sym:
            key = f"MCX_{crude_sym}"
            ltp = price_data["prices"].get(key, 0)
            quote = price_data["quotes"].get("CRUDEOILM", {})
            day_change = quote.get("day_change_perc", 0) if quote else 0

            st.metric(
                label = "LTP (per barrel)",
                value = f"Rs{ltp:,.2f}",
                delta = f"{day_change:+.2f}%" if day_change else None,
            )
        else:
            st.warning("Crude contract not found")

# ── INR/USD ────────────────────────────────────────────────
st.divider()
st.subheader("INR / USD")
inr = get_inr_usd_rate()
ic1, ic2, ic3 = st.columns(3)
with ic1:
    st.metric("Rate", f"{inr.get('rate', 'N/A')}")
with ic2:
    st.metric("Change", f"{inr.get('change_pct', 0):+.3f}%")
with ic3:
    signal = inr.get("signal", "unknown")
    if signal == "volatile":
        st.error(f"⚠ INR {inr.get('direction', '')} — VOLATILE")
    else:
        st.success(f"✓ INR {inr.get('direction', '')} — stable")

# ── Latest Signals ─────────────────────────────────────────
st.divider()
st.subheader("Latest Signals")

def get_latest_signals(limit: int = 6) -> list:
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT commodity, contract, action, confidence,
                   signal_quality, market_regime, timestamp,
                   primary_reason, followed, mode
            FROM signals_log
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows
    except Exception:
        return []

signals = get_latest_signals()

if not signals:
    st.info("No signals generated yet. Go to Signal Engine to run your first analysis.")
else:
    for sig in signals:
        with st.expander(
            f"{sig['commodity']}  |  "
            f"{'▲' if sig['action']=='BUY' else '▼' if sig['action']=='SELL' else '◆'} "
            f"{sig['action']}  |  "
            f"{sig['confidence']}%  |  "
            f"{sig['timestamp']}",
            expanded=False,
        ):
            render_signal_badge(
                sig["action"],
                sig["confidence"],
                sig["signal_quality"] or "N/A",
            )
            sc1, sc2, sc3 = st.columns(3)
            with sc1:
                st.caption(f"Regime: {sig.get('market_regime', 'N/A')}")
            with sc2:
                st.caption(f"Contract: {sig.get('contract', 'N/A')}")
            with sc3:
                followed = sig.get("followed")
                if followed == 1:
                    st.caption("✅ Followed")
                elif followed == 0:
                    st.caption("❌ Ignored")
                else:
                    st.caption("⏳ Pending")
            if sig.get("primary_reason"):
                st.caption(f"Reason: {sig['primary_reason']}")

# ── Today's Summary ────────────────────────────────────────
st.divider()
st.subheader("Today's Summary")

def get_today_summary() -> dict:
    try:
        from datetime import date
        conn   = get_connection()
        cursor = conn.cursor()
        today  = date.today().isoformat()

        cursor.execute("""
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN followed=1 THEN 1 ELSE 0 END) as followed,
                   SUM(CASE WHEN action='BUY'  THEN 1 ELSE 0 END) as buys,
                   SUM(CASE WHEN action='SELL' THEN 1 ELSE 0 END) as sells,
                   SUM(CASE WHEN action='HOLD' THEN 1 ELSE 0 END) as holds
            FROM signals_log
            WHERE DATE(timestamp) = ? AND mode = ?
        """, (today, TRADING_MODE))
        sig_row = dict(cursor.fetchone())

        cursor.execute("""
            SELECT COALESCE(SUM(pnl_inr), 0) as pnl,
                   COUNT(*) as trades
            FROM trades_log
            WHERE DATE(entry_time) = ? AND mode = ?
        """, (today, TRADING_MODE))
        pnl_row = dict(cursor.fetchone())
        conn.close()

        return {**sig_row, **pnl_row}
    except Exception:
        return {}

summary = get_today_summary()
ts1, ts2, ts3, ts4, ts5 = st.columns(5)
with ts1:
    st.metric("Signals Today", summary.get("total", 0))
with ts2:
    st.metric("Followed", summary.get("followed", 0))
with ts3:
    st.metric("BUY / SELL / HOLD",
        f"{summary.get('buys',0)} / "
        f"{summary.get('sells',0)} / "
        f"{summary.get('holds',0)}"
    )
with ts4:
    pnl = summary.get("pnl", 0) or 0
    st.metric("Paper P&L",
        f"Rs{pnl:,.0f}",
        delta=f"{pnl/CAPITAL_INR*100:.2f}%" if CAPITAL_INR else None,
    )
with ts5:
    st.metric("Trades", summary.get("trades", 0))