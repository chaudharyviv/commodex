"""
COMMODEX — Backtest
Historical signal performance using Groww Backtest API.
"""

import streamlit as st
from dotenv import load_dotenv
load_dotenv()

from core.ui_helpers import render_sidebar
from core.db import init as db_init

st.set_page_config(
    page_title="Backtest — COMMODEX",
    page_icon="🔬",
    layout="wide",
)

db_init()
render_sidebar()

st.title("🔬 Backtest")
st.caption("Historical signal performance analysis")

st.info(
    "Backtest module will be activated after 30 days of paper trading signals. "
    "This ensures meaningful historical data exists before running backtests."
)

st.subheader("Signal Accuracy (from logged signals)")

from core.db import get_connection
from config import TRADING_MODE
import pandas as pd

try:
    conn = get_connection()
    df   = pd.read_sql_query("""
        SELECT commodity, action, signal_quality,
               confidence, followed,
               entry_price, stop_loss, target_1, rr_ratio,
               DATE(timestamp) as date
        FROM signals_log
        WHERE mode = ?
        ORDER BY timestamp DESC
    """, conn, params=[TRADING_MODE])
    conn.close()

    if df.empty:
        st.info("No signals to analyse yet.")
    else:
        st.write(f"Total signals analysed: **{len(df)}**")

        # Quality breakdown
        st.subheader("Signal Quality Breakdown")
        quality_counts = df["signal_quality"].value_counts()
        st.bar_chart(quality_counts)

        # Confidence distribution
        st.subheader("Confidence Distribution")
        st.bar_chart(df["confidence"].value_counts().sort_index())

        # Action distribution
        st.subheader("Action Distribution")
        action_counts = df["action"].value_counts()
        st.bar_chart(action_counts)

except Exception as e:
    st.error(f"Error loading backtest data: {e}")