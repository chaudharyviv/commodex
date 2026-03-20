"""
COMMODEX — Trade Log
All signals, paper trades, P&L tracking, win rate.
"""

import streamlit as st
import pandas as pd
from dotenv import load_dotenv
load_dotenv()

from core.ui_helpers import render_sidebar
from core.db import get_connection, init as db_init
from config import TRADING_MODE, CAPITAL_INR

st.set_page_config(
    page_title="Trade Log — COMMODEX",
    page_icon="📋",
    layout="wide",
)

db_init()
render_sidebar()

st.title("📋 Trade Log")
st.caption("Signal history, paper trades, and performance tracking")

# ── Filters ────────────────────────────────────────────────
fc1, fc2, fc3 = st.columns(3)
with fc1:
    filter_commodity = st.selectbox(
        "Commodity", ["All", "GOLDM", "CRUDEOILM"]
    )
with fc2:
    filter_action = st.selectbox(
        "Action", ["All", "BUY", "SELL", "HOLD"]
    )
with fc3:
    filter_days = st.selectbox(
        "Period", [7, 14, 30, 60, 90], index=2,
        format_func=lambda x: f"Last {x} days"
    )

# ── Signal History ─────────────────────────────────────────
st.subheader("Signal History")

def get_signals(commodity, action, days) -> pd.DataFrame:
    try:
        conn   = get_connection()
        query  = """
            SELECT timestamp, commodity, contract, action,
                   confidence, signal_quality, market_regime,
                   entry_price, stop_loss, target_1, rr_ratio,
                   capital_risk_pct, primary_reason,
                   followed, mode, llm_provider
            FROM signals_log
            WHERE mode = ?
            AND timestamp >= datetime('now', ?)
        """
        params = [TRADING_MODE, f"-{days} days"]

        if commodity != "All":
            query  += " AND commodity = ?"
            params.append(commodity)
        if action != "All":
            query  += " AND action = ?"
            params.append(action)

        query += " ORDER BY timestamp DESC"
        df     = pd.read_sql_query(query, conn, params=params)
        conn.close()
        return df
    except Exception as e:
        st.error(f"DB error: {e}")
        return pd.DataFrame()

df = get_signals(filter_commodity, filter_action, filter_days)

if df.empty:
    st.info("No signals found for the selected filters.")
else:
    # Colour code action column
    def colour_action(val):
        colours = {
            "BUY":  "background-color: #1a3a1a; color: #4ade80",
            "SELL": "background-color: #3a1a1a; color: #f87171",
            "HOLD": "background-color: #3a3a1a; color: #fbbf24",
        }
        return colours.get(val, "")

    display_cols = [
        "timestamp", "commodity", "action", "confidence",
        "signal_quality", "market_regime", "entry_price",
        "stop_loss", "target_1", "rr_ratio", "followed",
    ]
    display_df = df[
        [c for c in display_cols if c in df.columns]
    ].copy()

    # Format followed column
    display_df["followed"] = display_df["followed"].map(
        {1: "✅ Yes", 0: "❌ No", None: "⏳ Pending"}
    ).fillna("⏳ Pending")

    styled = display_df.style.applymap(
        colour_action, subset=["action"]
    )
    st.dataframe(styled, use_container_width=True, height=400)

    # Expandable reasoning
    st.subheader("Signal Details")
    for _, row in df.head(5).iterrows():
        with st.expander(
            f"{row['timestamp']}  |  "
            f"{row['commodity']}  |  "
            f"{row['action']}  |  "
            f"{row['confidence']}%"
        ):
            if row.get("primary_reason"):
                st.write(f"**Reason**: {row['primary_reason']}")
            dc1, dc2, dc3 = st.columns(3)
            with dc1:
                st.caption(f"Regime: {row.get('market_regime', 'N/A')}")
            with dc2:
                st.caption(f"Quality: {row.get('signal_quality', 'N/A')}")
            with dc3:
                st.caption(f"Provider: {row.get('llm_provider', 'N/A')}")

# ── Performance Stats ──────────────────────────────────────
st.divider()
st.subheader("Performance Statistics")

if not df.empty:
    total    = len(df)
    buys     = len(df[df["action"] == "BUY"])
    sells    = len(df[df["action"] == "SELL"])
    holds    = len(df[df["action"] == "HOLD"])
    followed = len(df[df["followed"] == 1]) if "followed" in df.columns else 0
    a_grade  = len(df[df["signal_quality"] == "A"]) if "signal_quality" in df.columns else 0
    b_grade  = len(df[df["signal_quality"] == "B"]) if "signal_quality" in df.columns else 0

    sc1, sc2, sc3, sc4, sc5 = st.columns(5)
    with sc1:
        st.metric("Total Signals", total)
    with sc2:
        st.metric("BUY / SELL / HOLD", f"{buys} / {sells} / {holds}")
    with sc3:
        follow_rate = round(followed / total * 100) if total > 0 else 0
        st.metric("Follow Rate", f"{follow_rate}%")
    with sc4:
        st.metric("A-Grade Signals", a_grade)
    with sc5:
        avg_conf = round(df["confidence"].mean()) if "confidence" in df.columns else 0
        st.metric("Avg Confidence", f"{avg_conf}%")

# ── Paper Trades ───────────────────────────────────────────
st.divider()
st.subheader("Paper Trades")

def get_trades() -> pd.DataFrame:
    try:
        conn = get_connection()
        df   = pd.read_sql_query("""
            SELECT entry_time, exit_time, commodity, action,
                   lots, entry_price, exit_price,
                   stop_loss, target_1, pnl_inr, pnl_pct,
                   exit_reason
            FROM trades_log
            WHERE mode = ?
            ORDER BY entry_time DESC
        """, conn, params=[TRADING_MODE])
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()

trades_df = get_trades()
if trades_df.empty:
    st.info(
        "No paper trades logged yet. "
        "Mark signals as 'Followed' in Signal Engine to log them."
    )
else:
    st.dataframe(trades_df, use_container_width=True)

    total_pnl = trades_df["pnl_inr"].sum() if "pnl_inr" in trades_df else 0
    tc1, tc2, tc3 = st.columns(3)
    with tc1:
        st.metric(
            "Total P&L",
            f"Rs{total_pnl:,.0f}",
            delta=f"{total_pnl/CAPITAL_INR*100:.2f}%" if CAPITAL_INR else None,
        )
    with tc2:
        wins = len(trades_df[trades_df["pnl_inr"] > 0]) if "pnl_inr" in trades_df else 0
        total_closed = len(trades_df[trades_df["exit_time"].notna()])
        win_rate = round(wins / total_closed * 100) if total_closed > 0 else 0
        st.metric("Win Rate", f"{win_rate}%")
    with tc3:
        st.metric("Total Trades", len(trades_df))