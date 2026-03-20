"""
COMMODEX — Settings
API key status, risk parameters, mode switch.
"""

import streamlit as st
import os
from dotenv import load_dotenv, set_key
from pathlib import Path
load_dotenv()

from core.ui_helpers import render_sidebar
from core.db import init as db_init, health_check
from core.backup import run_backup, list_backups
from config import (
    TRADING_MODE, CAPITAL_INR, RISK_PCT_PER_TRADE,
    MAX_OPEN_POSITIONS, DAILY_LOSS_LIMIT_PCT,
    validate_config,
)

st.set_page_config(
    page_title="Settings — COMMODEX",
    page_icon="⚙",
    layout="wide",
)

db_init()
render_sidebar()

st.title("⚙ Settings")

ENV_PATH = Path(".env")

# ── Config Warnings ────────────────────────────────────────
warnings = validate_config()
if warnings:
    for w in warnings:
        st.warning(f"⚠ {w}")
else:
    st.success("✓ All configuration valid")

# ── API Key Status ─────────────────────────────────────────
st.subheader("API Key Status")

def check_key(env_var: str, label: str):
    val = os.getenv(env_var, "")
    if val and val != f"your_{env_var.lower()}_here":
        st.success(f"✓ {label} configured")
    else:
        st.error(f"✗ {label} not set — add to .env")

check_key("GROWW_API_KEY",     "Groww TOTP Token")
check_key("GROWW_TOTP_SECRET", "Groww TOTP Secret")
check_key("OPENAI_API_KEY",    "OpenAI API Key (demo mode)")
check_key("ANTHROPIC_API_KEY", "Anthropic API Key (paper/production)")
check_key("TAVILY_API_KEY",    "Tavily News API Key")

# ── Risk Parameters ────────────────────────────────────────
st.divider()
st.subheader("Risk Parameters (read-only — edit in .env)")

rc1, rc2, rc3, rc4 = st.columns(4)
with rc1:
    st.metric("Capital Deployed",    f"Rs{CAPITAL_INR:,.0f}")
with rc2:
    st.metric("Risk per Trade",      f"{RISK_PCT_PER_TRADE}%")
with rc3:
    st.metric("Max Open Positions",  MAX_OPEN_POSITIONS)
with rc4:
    st.metric("Daily Loss Limit",    f"{DAILY_LOSS_LIMIT_PCT}%")

st.caption(
    "To change risk parameters, edit the values in your .env file "
    "and restart the app."
)

# ── Trading Mode Switch ────────────────────────────────────
st.divider()
st.subheader("Trading Mode")

current_mode = TRADING_MODE
mode_options = {
    "demo":       "🟡 Demo Mode (OpenAI GPT-4o)",
    "paper":      "🔵 Paper Trading (Claude Sonnet 4.6)",
    "production": "🔴 Production — REAL MONEY",
}
st.info(f"Current mode: **{mode_options.get(current_mode, current_mode)}**")

new_mode = st.selectbox(
    "Switch to:",
    options=list(mode_options.keys()),
    format_func=lambda x: mode_options[x],
    index=list(mode_options.keys()).index(current_mode),
)

if new_mode != current_mode:
    if new_mode == "production":
        st.error(
            "⚠ PRODUCTION MODE — Real money will be at risk. "
            "Ensure you have completed 60 days of paper trading."
        )
        confirm_text = st.text_input(
            "Type 'CONFIRM REAL MONEY' to enable production mode:"
        )
        if confirm_text == "CONFIRM REAL MONEY":
            if st.button("🔴 Switch to Production", type="primary"):
                set_key(str(ENV_PATH), "TRADING_MODE", "production")
                set_key(str(ENV_PATH), "PRODUCTION_CONFIRMED", "true")
                st.success("Mode switched. Restart the app to apply.")
    else:
        if st.button(f"Switch to {mode_options[new_mode]}"):
            set_key(str(ENV_PATH), "TRADING_MODE", new_mode)
            if new_mode != "production":
                set_key(str(ENV_PATH), "PRODUCTION_CONFIRMED", "false")
            st.success("Mode switched. Restart the app to apply.")

# ── Database Status ────────────────────────────────────────
st.divider()
st.subheader("Database Status")

db_status = health_check()
if db_status["status"] == "ok":
    st.success(f"✓ Database healthy — {len(db_status['tables'])} tables")
    st.caption(f"Location: {db_status['db_path']}")
else:
    st.error(f"Database issue: {db_status}")

# ── Backup ─────────────────────────────────────────────────
st.divider()
st.subheader("Database Backup")

col1, col2 = st.columns([1, 3])
with col1:
    if st.button("💾 Run Backup Now"):
        result = run_backup()
        if result["status"] == "ok":
            st.success(
                f"Backup created: {result['backup_path']} "
                f"({result['size_kb']} KB)"
            )
        else:
            st.error(f"Backup failed: {result}")

backups = list_backups()
if backups:
    st.write(f"**Available backups ({len(backups)}):**")
    for b in backups[:5]:
        st.caption(
            f"📁 {b['filename']}  |  "
            f"{b['size_kb']} KB  |  "
            f"{b['created_at']}"
        )