"""
COMMODEX — Trade Log
All signals, paper trades, P&L tracking, win rate.
"""

import streamlit as st
import pandas as pd
from datetime import datetime
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

# ── Trade Log ──────────────────────────────────────────────
st.divider()
mode_label = "Real Trades" if TRADING_MODE == "production" else "Paper Trades"
st.subheader(mode_label)

def get_trades() -> pd.DataFrame:
    try:
        conn = get_connection()
        df   = pd.read_sql_query("""
            SELECT id, entry_time, exit_time, commodity, action,
                   lots, entry_price, exit_price,
                   stop_loss, target_1, pnl_inr, pnl_pct,
                   exit_reason, order_id, order_status
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
    if TRADING_MODE == "production":
        st.info("No trades logged yet. Execute a signal from the Signal Engine.")
    else:
        st.info(
            "No paper trades logged yet. "
            "Mark signals as 'Followed' in Signal Engine to log them."
        )
else:
    display_cols = [
        c for c in [
            "entry_time", "exit_time", "commodity", "action", "lots",
            "entry_price", "exit_price", "stop_loss", "target_1",
            "pnl_inr", "pnl_pct", "exit_reason", "order_status",
        ] if c in trades_df.columns
    ]
    st.dataframe(trades_df[display_cols], use_container_width=True)

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

# ── Exit Trade Form ─────────────────────────────────────────
st.divider()
st.subheader("Log Trade Exit")

open_trades = trades_df[trades_df["exit_time"].isna()] if not trades_df.empty else pd.DataFrame()

if open_trades.empty:
    st.info("No open trades to close.")
else:
    trade_options = {
        row["id"]: (
            f"#{row['id']}  {row['commodity']}  {row['action']}  "
            f"{row['lots']} lot(s)  @ Rs{row['entry_price']:,.2f}  "
            f"(SL: Rs{row['stop_loss']:,.2f}  T1: Rs{row['target_1']:,.2f})"
        )
        for _, row in open_trades.iterrows()
    }

    selected_id = st.selectbox(
        "Select open trade to close:",
        options=list(trade_options.keys()),
        format_func=lambda x: trade_options[x],
    )

    if selected_id:
        sel_row  = open_trades[open_trades["id"] == selected_id].iloc[0]
        lots_val = int(sel_row["lots"])
        entry_px = float(sel_row["entry_price"])
        sl_px    = float(sel_row["stop_loss"]) if sel_row["stop_loss"] else 0.0
        t1_px    = float(sel_row["target_1"])  if sel_row["target_1"]  else 0.0

        ec1, ec2 = st.columns(2)
        with ec1:
            exit_price = st.number_input(
                "Exit Price (Rs)",
                min_value   = 0.0,
                value       = t1_px if t1_px else entry_px,
                step        = 0.5,
                format      = "%.2f",
                key         = "exit_px",
            )
        with ec2:
            exit_reason = st.selectbox(
                "Exit Reason",
                ["T1_HIT", "T2_HIT", "SL_HIT", "MANUAL", "SESSION_END", "OTHER"],
                key = "exit_reason",
            )

        exit_notes = st.text_input("Notes (optional)", key="exit_notes")

        # P&L preview
        action     = sel_row["action"]
        tick_size  = 1.0   # Rs1 per tick for both GOLDM & CRUDEOILM

        from config import LOT_CONFIG as _LC
        lot_cfg     = _LC.get(sel_row["commodity"], {})
        pl_per_tick = lot_cfg.get("pl_per_tick", 10)
        tick_sz     = lot_cfg.get("tick_size", 1)

        if action == "BUY":
            ticks = (exit_price - entry_px) / tick_sz
        else:
            ticks = (entry_px - exit_price) / tick_sz

        pnl_inr = ticks * pl_per_tick * lots_val
        pnl_pct = round(pnl_inr / CAPITAL_INR * 100, 3) if CAPITAL_INR else 0

        pnl_col = "🟢" if pnl_inr >= 0 else "🔴"
        st.info(
            f"{pnl_col} Estimated P&L: **Rs{pnl_inr:+,.0f}** "
            f"({pnl_pct:+.2f}% of capital)"
        )

        if st.button("✅ Log Exit", type="primary", key="log_exit"):
            try:
                _conn = get_connection()
                _conn.execute("""
                    UPDATE trades_log
                    SET exit_price  = ?,
                        exit_time   = ?,
                        pnl_inr     = ?,
                        pnl_pct     = ?,
                        exit_reason = ?,
                        notes       = ?,
                        order_status = 'CLOSED'
                    WHERE id = ?
                """, (
                    exit_price,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    round(pnl_inr, 2),
                    pnl_pct,
                    exit_reason,
                    exit_notes or None,
                    selected_id,
                ))
                _conn.commit()
                _conn.close()
                st.success(
                    f"Trade #{selected_id} closed.  "
                    f"P&L: Rs{pnl_inr:+,.0f} ({pnl_pct:+.2f}%)"
                )
                st.rerun()
            except Exception as _e:
                st.error(f"Failed to log exit: {_e}")

# ── Live Groww Positions (Production Mode) ─────────────────
if TRADING_MODE == "production":
    st.divider()
    st.subheader("Live Groww Positions")

    if st.button("🔄 Refresh from Groww", key="refresh_positions"):
        st.cache_data.clear()

    @st.cache_data(ttl=30)
    def fetch_groww_positions():
        try:
            from generate_token import generate_totp_token, save_token_to_env
            import os as _os
            tok = generate_totp_token()
            save_token_to_env(tok)
            _os.environ["GROWW_ACCESS_TOKEN"] = tok

            from core.groww_client import GrowwClient as _GC
            gc   = _GC(access_token=tok)
            return gc.get_live_positions(), None
        except Exception as _e:
            return [], str(_e)

    positions, pos_err = fetch_groww_positions()

    if pos_err:
        st.warning(f"Could not fetch positions: {pos_err}")
    elif not positions:
        st.info("No open commodity positions on Groww.")
    else:
        pos_df = pd.DataFrame(positions)
        st.dataframe(pos_df, use_container_width=True)

        # Cancel order helper (open orders)
        st.divider()
        st.subheader("Cancel Pending Order")
        cancel_id = st.text_input(
            "Enter Groww Order ID to cancel:",
            key = "cancel_order_id",
        )
        if cancel_id and st.button("Cancel Order", key="cancel_btn"):
            try:
                from core.groww_client import GrowwClient as _GC3
                import os as _os3
                _gc3 = _GC3(access_token=_os3.getenv("GROWW_ACCESS_TOKEN"))
                res = _gc3.cancel_mcx_order(cancel_id)
                st.success(f"Cancel response: {res}")
            except Exception as _ce:
                st.error(f"Cancel failed: {_ce}")