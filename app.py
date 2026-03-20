"""
COMMODEX — Main Entry Point
Run with: streamlit run app.py
"""

import streamlit as st
import logging
from config import TRADING_MODE, validate_config
from core.db import init as db_init, health_check
from core.ui_helpers import render_sidebar

logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
)

st.set_page_config(
    page_title         = "COMMODEX",
    page_icon          = "⬡",
    layout             = "wide",
    initial_sidebar_state = "expanded",
)

def startup():
    if "app_initialised" not in st.session_state:
        db_init()
        st.session_state["app_initialised"] = True

startup()
render_sidebar()

# ── Config warnings ────────────────────────────────────────
warnings = validate_config()
for w in warnings:
    st.warning(f"⚠ {w}")

# ── Home page ──────────────────────────────────────────────
st.title("⬡ COMMODEX")
st.caption("AI-Assisted MCX Commodity Signal Platform")
st.divider()

mode_info = {
    "demo":       ("🟡", "Demo Mode",        "OpenAI GPT-4o",       "info"),
    "paper":      ("🔵", "Paper Trading",    "Claude Sonnet 4.6",   "info"),
    "production": ("🔴", "PRODUCTION",       "Claude Sonnet 4.6",   "error"),
}
icon, label, model, kind = mode_info.get(
    TRADING_MODE, ("⚪", TRADING_MODE, "Unknown", "info")
)
getattr(st, kind)(f"{icon} **{label}** — {model}")

st.divider()

c1, c2, c3 = st.columns(3)

with c1:
    st.subheader("System Status")
    db_status = health_check()
    if db_status["status"] == "ok":
        st.success("✓ Database ready")
    else:
        st.error(f"✗ Database: {db_status.get('error')}")

with c2:
    st.subheader("Active Scope")
    st.info("◈ Gold Mini (GOLDM)\n\n⬡ Crude Oil Mini (CRUDEOILM)")

with c3:
    st.subheader("Quick Start")
    st.markdown("1. Go to **Signal Engine**")
    st.markdown("2. Select commodity + style")
    st.markdown("3. Click **Run Analysis**")
    st.markdown("4. Review signal and mark followed/ignored")

st.divider()
st.caption(
    "COMMODEX v1.0 | Phase 5 Complete | "
    "For personal use only | Not financial advice"
)