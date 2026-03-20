"""
COMMODEX — Central Configuration
Single source of truth for all system parameters.
Never import from .env directly elsewhere — always go through config.py.

Version: 1.1
Changes from 1.0:
  - LOT_CONFIG updated with correct pl_per_tick from MCX specs
  - Margin changed from static INR to percentage-based (margin_pct)
  - Silver contracts added but marked active=False (v2 scope)
  - ACTIVE_COMMODITIES list added
  - Position sizing formula updated to use pl_per_tick x stop_ticks
"""

import os
import pathlib
from dotenv import load_dotenv
import warnings

load_dotenv()

# ─────────────────────────────────────────────────────────────────
# TRADING MODE
# ─────────────────────────────────────────────────────────────────
TRADING_MODE = os.getenv("TRADING_MODE", "demo")  # demo | paper | production

# ─────────────────────────────────────────────────────────────────
# LLM CONFIGURATION
# ─────────────────────────────────────────────────────────────────
LLM_CONFIG = {
    "demo": {
        "provider": "openai",
        "model":    "gpt-4o",
        "api_key":  os.getenv("OPENAI_API_KEY"),
    },
    "paper": {
        "provider": "anthropic",
        "model":    "claude-sonnet-4-6",
        "api_key":  os.getenv("ANTHROPIC_API_KEY"),
    },
    "production": {
        "provider": "anthropic",
        "model":    "claude-sonnet-4-6",
        "api_key":  os.getenv("ANTHROPIC_API_KEY"),
    },
}

ACTIVE_LLM = LLM_CONFIG[TRADING_MODE]

# ─────────────────────────────────────────────────────────────────
# GROWW API
# ─────────────────────────────────────────────────────────────────
GROWW_API_KEY    = os.getenv("GROWW_API_KEY")
GROWW_API_SECRET = os.getenv("GROWW_API_SECRET")
GROWW_BASE_URL   = "https://api.groww.in/v1"

# ─────────────────────────────────────────────────────────────────
# MCX LOT CONFIGURATION
#
# Source: Official MCX contract specifications
# Last updated: March 2026
#
# pl_per_tick  : ₹ profit/loss per single tick move per lot
#                This is the authoritative number for position sizing.
#                Never let LLM compute this — hardcoded only.
#
# margin_pct   : SPAN margin as % of contract value (MCX official)
#                Actual margin in ₹ = (LTP × lot_size × margin_pct) / 100
#                This changes daily — use as conservative estimate.
#
# tick_size    : Minimum price movement in ₹
#
# recommended  : True = suitable for personal retail account
# active       : False = excluded from v1, reserved for future versions
# ─────────────────────────────────────────────────────────────────

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

if not os.getenv("TAVILY_API_KEY"):
    warnings.warn("TAVILY_API_KEY not set — news context unavailable")



LOT_CONFIG = {

    # ── GOLD CONTRACTS ────────────────────────────────────────────

    "GOLD": {
        "exchange":        "MCX",
        "lot_size":        1000,            # grams
        "unit":            "grams",
        "quote_unit":      "per_10g",
        "tick_size":       1.0,             # ₹1 per 10g
        "pl_per_tick":     100.0,           # ₹100 per tick per lot
        "margin_pct":      8.25,            # % of contract value
        "friendly_name":   "Gold (1kg)",
        "recommended":     False,           # large contract, high capital
        "active":          False,           # excluded from v1
        "has_options":     True,
        "options_tick":    0.50,            # ₹0.50 per 10g
        "options_pl_tick": 50.0,            # ₹50 per tick per lot
    },

    "GOLDM": {
        "exchange":        "MCX",
        "lot_size":        100,             # grams
        "unit":            "grams",
        "quote_unit":      "per_10g",
        "tick_size":       1.0,             # ₹1 per 10g
        "pl_per_tick":     10.0,            # ₹10 per tick per lot  ← KEY NUMBER
        "margin_pct":      8.25,
        "friendly_name":   "Gold Mini (100g)",
        "recommended":     True,            # ✓ best for personal account
        "active":          True,            # ✓ v1 scope
        "has_options":     True,
        "options_tick":    0.50,
        "options_pl_tick": 5.0,             # ₹5 per tick per lot
    },

    "GOLDTEN": {
        "exchange":        "MCX",
        "lot_size":        10,              # grams
        "unit":            "grams",
        "quote_unit":      "per_10g",
        "tick_size":       1.0,
        "pl_per_tick":     1.0,             # ₹1 per tick per lot
        "margin_pct":      8.25,
        "friendly_name":   "Gold Ten (10g)",
        "recommended":     False,           # too small, low liquidity
        "active":          False,
        "has_options":     False,
        "options_tick":    None,
        "options_pl_tick": None,
    },

    "GOLDGUINEA": {
        "exchange":        "MCX",
        "lot_size":        8,               # grams
        "unit":            "grams",
        "quote_unit":      "per_8g",
        "tick_size":       1.0,
        "pl_per_tick":     1.0,
        "margin_pct":      8.25,
        "friendly_name":   "Gold Guinea (8g)",
        "recommended":     False,
        "active":          False,
        "has_options":     False,
        "options_tick":    None,
        "options_pl_tick": None,
    },

    "GOLDPETAL": {
        "exchange":        "MCX",
        "lot_size":        1,               # gram
        "unit":            "grams",
        "quote_unit":      "per_1g",
        "tick_size":       1.0,
        "pl_per_tick":     1.0,
        "margin_pct":      8.25,
        "friendly_name":   "Gold Petal (1g)",
        "recommended":     False,
        "active":          False,
        "has_options":     False,
        "options_tick":    None,
        "options_pl_tick": None,
    },

    # ── CRUDE OIL CONTRACTS ───────────────────────────────────────

    "CRUDEOIL": {
        "exchange":        "MCX",
        "lot_size":        100,             # barrels
        "unit":            "barrels",
        "quote_unit":      "per_barrel",
        "tick_size":       1.0,             # ₹1 per barrel
        "pl_per_tick":     100.0,           # ₹100 per tick per lot
        "margin_pct":      34.25,           # HIGH — crude needs more capital
        "friendly_name":   "Crude Oil (100 bbl)",
        "recommended":     False,           # high margin requirement
        "active":          False,           # excluded from v1
        "has_options":     True,
        "options_tick":    0.10,            # 10 paisa
        "options_pl_tick": 1.0,             # ₹1 per tick per lot (note: mini diff)
    },

    "CRUDEOILM": {
        "exchange":        "MCX",
        "lot_size":        10,              # barrels
        "unit":            "barrels",
        "quote_unit":      "per_barrel",
        "tick_size":       1.0,             # ₹1 per barrel
        "pl_per_tick":     10.0,            # ₹10 per tick per lot  ← KEY NUMBER
        "margin_pct":      34.25,
        "friendly_name":   "Crude Oil Mini (10 bbl)",
        "recommended":     True,            # ✓ best for personal account
        "active":          True,            # ✓ v1 scope
        "has_options":     True,
        "options_tick":    0.05,            # 5 paisa
        "options_pl_tick": 0.50,            # ₹0.50 per tick per lot
    },

    # ── SILVER CONTRACTS (v2 — not active in v1) ──────────────────
    # Excluded from v1: higher margin, correlated with Gold,
    # thinner liquidity. Revisit after 60-day paper trading validation.

    "SILVER": {
        "exchange":        "MCX",
        "lot_size":        30,              # kg
        "unit":            "kg",
        "quote_unit":      "per_kg",
        "tick_size":       1.0,             # ₹1 per kg
        "pl_per_tick":     30.0,            # ₹30 per tick per lot
        "margin_pct":      17.25,
        "friendly_name":   "Silver (30kg)",
        "recommended":     False,
        "active":          False,           # v2 scope
        "has_options":     True,
        "options_tick":    0.50,
        "options_pl_tick": 15.0,            # ₹15 per tick per lot
    },

    "SILVERM": {
        "exchange":        "MCX",
        "lot_size":        5,               # kg
        "unit":            "kg",
        "quote_unit":      "per_kg",
        "tick_size":       1.0,
        "pl_per_tick":     5.0,             # ₹5 per tick per lot
        "margin_pct":      17.25,
        "friendly_name":   "Silver Mini (5kg)",
        "recommended":     False,
        "active":          False,           # v2 scope
        "has_options":     True,
        "options_tick":    0.50,
        "options_pl_tick": 2.50,            # ₹2.50 per tick per lot
    },

    "SILVERMICRO": {
        "exchange":        "MCX",
        "lot_size":        1,               # kg
        "unit":            "kg",
        "quote_unit":      "per_kg",
        "tick_size":       1.0,
        "pl_per_tick":     1.0,             # ₹1 per tick per lot
        "margin_pct":      17.25,
        "friendly_name":   "Silver Micro (1kg)",
        "recommended":     False,
        "active":          False,           # v2 scope
        "has_options":     False,
        "options_tick":    None,
        "options_pl_tick": None,
    },

    # ── NATURAL GAS CONTRACTS (v2 — not active in v1) ─────────────
    # Noted for completeness. Extreme volatility, different
    # tick structure (10 paisa). Out of scope for v1.

    "NATURALGAS": {
        "exchange":        "MCX",
        "lot_size":        1250,            # MMBTU
        "unit":            "MMBTU",
        "quote_unit":      "per_MMBTU",
        "tick_size":       0.10,            # 10 paisa
        "pl_per_tick":     125.0,           # ₹125 per tick per lot
        "margin_pct":      24.50,
        "friendly_name":   "Natural Gas (1250 MMBTU)",
        "recommended":     False,
        "active":          False,
        "has_options":     True,
        "options_tick":    0.05,
        "options_pl_tick": 62.50,
    },

    "NATURALGASM": {
        "exchange":        "MCX",
        "lot_size":        250,             # MMBTU
        "unit":            "MMBTU",
        "quote_unit":      "per_MMBTU",
        "tick_size":       0.10,
        "pl_per_tick":     25.0,            # ₹25 per tick per lot
        "margin_pct":      24.50,
        "friendly_name":   "Natural Gas Mini (250 MMBTU)",
        "recommended":     False,
        "active":          False,
        "has_options":     True,
        "options_tick":    0.05,
        "options_pl_tick": 12.50,
    },
}

# ─────────────────────────────────────────────────────────────────
# ACTIVE SCOPE
# ─────────────────────────────────────────────────────────────────

# v1 active contracts — everything else is reference data only
ACTIVE_COMMODITIES   = ["GOLDM", "CRUDEOILM"]

# Convenience lookups
DEFAULT_GOLD_CONTRACT  = "GOLDM"
DEFAULT_CRUDE_CONTRACT = "CRUDEOILM"

# Helper: get only active contracts
ACTIVE_LOT_CONFIG = {
    k: v for k, v in LOT_CONFIG.items()
    if v.get("active", False)
}

# ─────────────────────────────────────────────────────────────────
# POSITION SIZING FORMULA
#
# risk_per_trade_inr  = CAPITAL_INR × (RISK_PCT_PER_TRADE / 100)
# stop_distance_ticks = abs(entry_price - stop_loss) / tick_size
# risk_per_lot_inr    = stop_distance_ticks × pl_per_tick
# position_size_lots  = floor(risk_per_trade_inr / risk_per_lot_inr)
# position_size_lots  = min(position_size_lots, MAX_LOTS_PER_SIGNAL)
# position_size_lots  = max(position_size_lots, 1)
#
# Example — GOLDM:
#   capital=₹1,00,000  risk=2.5%  → risk_budget = ₹2,500
#   entry=71,450  stop=71,435  → stop_distance = 15 ticks
#   pl_per_tick = ₹10  → risk_per_lot = 15 × 10 = ₹150
#   lots = floor(2500 / 150) = 16 → capped at MAX_LOTS = 3
#
# Example — CRUDEOILM:
#   risk_budget = ₹2,500
#   entry=6,500  stop=6,450  → stop_distance = 50 ticks
#   pl_per_tick = ₹10  → risk_per_lot = 50 × 10 = ₹500
#   lots = floor(2500 / 500) = 5 → capped at MAX_LOTS = 3
# ─────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────
# MCX MARKET HOURS (IST)
# ─────────────────────────────────────────────────────────────────
MCX_OPEN_TIME               = "09:00"
MCX_CLOSE_TIME              = "23:30"
INTRADAY_SIGNAL_CUTOFF_TIME = "22:00"   # no new intraday signals after this
EXPIRY_BLACKOUT_DAYS        = 3         # block signals N days before expiry

# ─────────────────────────────────────────────────────────────────
# RISK PARAMETERS
# ─────────────────────────────────────────────────────────────────
CAPITAL_INR              = float(os.getenv("CAPITAL_INR", 100000))
RISK_PCT_PER_TRADE       = float(os.getenv("RISK_PCT_PER_TRADE", 2.5))
MAX_OPEN_POSITIONS       = int(os.getenv("MAX_OPEN_POSITIONS", 2))
DAILY_LOSS_LIMIT_PCT     = float(os.getenv("DAILY_LOSS_LIMIT_PCT", 5.0))
MAX_LOTS_PER_SIGNAL      = 3            # hard cap regardless of sizing formula
MIN_CONFIDENCE_THRESHOLD = 55           # below this → signal shown as HOLD
MIN_RR_RATIO             = 1.5          # minimum acceptable risk:reward

# INR/USD volatility gate (Guardrail 9)
INR_VOLATILITY_GATE_PCT  = 0.5          # if INR moves > 0.5% intraday → cap confidence

# Confidence caps triggered by guardrails
CONFIDENCE_CAP_NO_NEWS        = 65      # news fetch failed
CONFIDENCE_CAP_HIGH_IMPACT    = 60      # high impact event in next 24h
CONFIDENCE_CAP_INR_VOLATILE   = 60      # INR/USD move > gate threshold

# ─────────────────────────────────────────────────────────────────
# CACHE SETTINGS (minutes)
# ─────────────────────────────────────────────────────────────────
CACHE_OHLCV_INTRADAY_MIN = 5
CACHE_OHLCV_DAILY_MIN    = 60
CACHE_NEWS_MIN           = 60

# ─────────────────────────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────────────────────────
BASE_DIR    = pathlib.Path(__file__).parent
DB_PATH     = BASE_DIR / "commodex.db"
BACKUP_DIR  = BASE_DIR / "data" / "backups"
PROMPTS_DIR = BASE_DIR / "prompts"

# ─────────────────────────────────────────────────────────────────
# STARTUP VALIDATION
# ─────────────────────────────────────────────────────────────────
def validate_config() -> list[str]:
    """
    Called at app startup to surface missing or invalid config.
    Returns list of warning strings.
    Does not raise — lets the app display warnings gracefully.
    """
    warnings = []

    if not GROWW_API_KEY or GROWW_API_KEY == "your_api_key_here":
        warnings.append("GROWW_API_KEY not set in .env")

    if not GROWW_API_SECRET or GROWW_API_SECRET == "your_api_secret_here":
        warnings.append("GROWW_API_SECRET not set in .env")

    if TRADING_MODE == "demo":
        if not ACTIVE_LLM["api_key"] or \
           ACTIVE_LLM["api_key"] == "your_openai_key_here":
            warnings.append("OPENAI_API_KEY not set — demo LLM will not work")

    if TRADING_MODE in ("paper", "production"):
        if not ACTIVE_LLM["api_key"] or \
           ACTIVE_LLM["api_key"] == "your_anthropic_key_here":
            warnings.append(
                "ANTHROPIC_API_KEY not set — paper/production LLM will not work"
            )

    if CAPITAL_INR < 10000:
        warnings.append(
            f"CAPITAL_INR is ₹{CAPITAL_INR:,.0f} — "
            f"too low for MCX margin requirements"
        )

    # Margin sanity check against active contracts
    for symbol in ACTIVE_COMMODITIES:
        cfg = LOT_CONFIG.get(symbol, {})
        if cfg:
            # Conservative margin estimate at a typical price
            # GOLDM at ~₹71,000/10g: contract value = 71000 × 10 = ₹7,10,000
            # margin = 8.25% = ~₹58,575 per lot
            # CRUDEOILM at ~₹6,500/bbl: contract value = 6500 × 10 = ₹65,000
            # margin = 34.25% = ~₹22,263 per lot
            pass  # detailed margin check happens in RiskEngine with live prices

    if TRADING_MODE == "production":
        warnings.append(
            "⚠ PRODUCTION MODE ACTIVE — real money at risk. "
            "Ensure paper trading validation is complete."
        )

    return warnings


def get_margin_estimate_inr(symbol: str, ltp: float) -> float:
    """
    Calculate approximate margin required for 1 lot.
    margin = (ltp × lot_size × margin_pct) / 100

    Note: For Gold (quoted per 10g), ltp is per 10g.
    Contract value = ltp × (lot_size / 10) for gold contracts.
    For Crude (quoted per barrel), ltp is per barrel.
    Contract value = ltp × lot_size.
    """
    cfg = LOT_CONFIG.get(symbol)
    if not cfg:
        return 0.0

    if cfg["quote_unit"] == "per_10g":
        # Gold: ltp is per 10g, lot_size in grams
        contract_value = ltp * (cfg["lot_size"] / 10)
    else:
        # Crude/Silver/others: ltp is per unit, lot_size in same units
        contract_value = ltp * cfg["lot_size"]

    return round(contract_value * cfg["margin_pct"] / 100, 2)


def get_position_size(
    symbol: str,
    entry_price: float,
    stop_loss: float,
    capital: float = None,
    risk_pct: float = None,
) -> dict:
    """
    Calculate position size using pl_per_tick method.
    Returns full breakdown dict for transparency.

    This is the authoritative position sizing function.
    Risk Agent uses this output — never computes independently.
    """
    cfg = LOT_CONFIG.get(symbol)
    if not cfg:
        return {"error": f"Unknown symbol: {symbol}"}

    capital   = capital  or CAPITAL_INR
    risk_pct  = risk_pct or RISK_PCT_PER_TRADE

    risk_budget_inr    = capital * (risk_pct / 100)
    stop_distance      = abs(entry_price - stop_loss)
    stop_distance_ticks = stop_distance / cfg["tick_size"]
    risk_per_lot_inr   = stop_distance_ticks * cfg["pl_per_tick"]

    if risk_per_lot_inr <= 0:
        return {"error": "Stop loss equals entry price"}

    raw_lots      = risk_budget_inr / risk_per_lot_inr
    position_lots = max(1, min(int(raw_lots), MAX_LOTS_PER_SIGNAL))
    actual_risk   = position_lots * risk_per_lot_inr

    return {
        "symbol":               symbol,
        "entry_price":          entry_price,
        "stop_loss":            stop_loss,
        "stop_distance":        round(stop_distance, 2),
        "stop_distance_ticks":  round(stop_distance_ticks, 1),
        "pl_per_tick":          cfg["pl_per_tick"],
        "risk_per_lot_inr":     round(risk_per_lot_inr, 2),
        "risk_budget_inr":      round(risk_budget_inr, 2),
        "raw_lots_calculated":  round(raw_lots, 2),
        "position_lots":        position_lots,
        "capped_at_max":        raw_lots > MAX_LOTS_PER_SIGNAL,
        "actual_risk_inr":      round(actual_risk, 2),
        "actual_risk_pct":      round(actual_risk / capital * 100, 2),
        "margin_est_inr":       get_margin_estimate_inr(symbol, entry_price),
    }

