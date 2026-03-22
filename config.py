"""
COMMODEX — Central Configuration
Single source of truth for all system parameters.
Never import from .env directly elsewhere — always go through config.py.

Version: 2.0
Changes from 1.1:
  - Added v2.0 technical indicator thresholds (ADX, VWAP, BB, OI, Supertrend)
  - Position sizing: added underlotted detection + margin sufficiency check
  - Added B-grade confidence reduction percentage
  - Margin sanity check at startup now uses real estimates instead of pass
  - Added RISK_OVERBUDGET_BLOCK_MULTIPLIER for underlotted safety gate
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
GROWW_API_KEY     = os.getenv("GROWW_API_KEY")
GROWW_TOTP_SECRET = os.getenv("GROWW_TOTP_SECRET")

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
# v2.0 addition:
#   If raw_lots < 1.0, the trade is "underlotted" — 1 lot forced
#   but actual risk exceeds budget. If actual risk > budget × 1.5
#   (RISK_OVERBUDGET_BLOCK_MULTIPLIER), the signal is blocked.
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
#
# Example — Underlotted (GOLDM wide stop):
#   risk_budget = ₹2,500
#   entry=71,450  stop=71,100  → stop_distance = 350 ticks
#   risk_per_lot = 350 × 10 = ₹3,500 > budget of ₹2,500
#   raw_lots = 0.71 → forced to 1 lot → actual risk = ₹3,500
#   actual/budget = 1.4 < 1.5 → WARNING but allowed
#   If stop=70,800 → risk_per_lot = ₹6,500 → ratio 2.6 → BLOCKED
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

# v2.0: Underlotted safety gate
# If actual risk for 1 forced lot exceeds budget × this multiplier → block
RISK_OVERBUDGET_BLOCK_MULTIPLIER = 1.5

# v2.0: B-grade position reduction
# B-grade signals (confidence 55-74%) reduce position size by this factor
B_GRADE_POSITION_REDUCTION = 0.5

# INR/USD volatility gate (Guardrail 9)
INR_VOLATILITY_GATE_PCT  = 0.5          # if INR moves > 0.5% intraday → cap confidence

# Confidence caps triggered by guardrails
CONFIDENCE_CAP_NO_NEWS        = 65      # news fetch failed
CONFIDENCE_CAP_HIGH_IMPACT    = 60      # high impact event in next 24h
CONFIDENCE_CAP_INR_VOLATILE   = 60      # INR/USD move > gate threshold

# Margin utilisation threshold
# Block signal if margin_required > this % of available capital
MARGIN_UTILISATION_MAX_PCT    = 80      # don't use more than 80% of capital as margin

# ─────────────────────────────────────────────────────────────────
# v2.0 TECHNICAL INDICATOR THRESHOLDS
#
# Externalised from technical_engine.py so they can be tuned
# during paper trading without touching engine code.
# ─────────────────────────────────────────────────────────────────

# ADX — Trend strength classification
ADX_RANGING_THRESHOLD    = 20       # below this = no meaningful trend
ADX_TRENDING_THRESHOLD   = 25       # above this = directional trend
ADX_STRONG_THRESHOLD     = 40       # above this = strong trend (trail stops)

# VWAP — Price-to-VWAP distance thresholds
VWAP_PREMIUM_PCT         = 0.3      # % above VWAP to flag as "premium" price
VWAP_DISCOUNT_PCT        = 0.3      # % below VWAP to flag as "discount" price

# Bollinger Band squeeze — breakout detection
BB_SQUEEZE_TOLERANCE     = 1.05     # within 5% of 20-period min width = squeeze active

# Open Interest — minimum change % to classify as meaningful
OI_CHANGE_THRESHOLD_PCT  = 1.0      # ±1% OI change = meaningful (fresh longs/shorts/etc.)

# Supertrend — indicator parameters
SUPERTREND_PERIOD        = 10       # ATR period for supertrend
SUPERTREND_MULTIPLIER    = 3.0      # ATR multiplier

# RSI Divergence — lookback and pivot detection
RSI_DIVERGENCE_LOOKBACK  = 30       # candles to search for divergence
RSI_PIVOT_ORDER          = 5        # bars on each side for pivot detection

# Fibonacci — swing detection
FIB_LOOKBACK_CANDLES     = 50       # candles to search for swing H/L
FIB_PIVOT_ORDER          = 5        # bars on each side for swing detection

# StochRSI — threshold levels
STOCH_RSI_OVERBOUGHT     = 80       # above this = overbought
STOCH_RSI_OVERSOLD       = 20       # below this = oversold

# Volume-price confirmation — volume ratio threshold
VOLUME_CONFIRM_RATIO     = 1.2      # volume >= 1.2× average = "high" for confirmation

# ─────────────────────────────────────────────────────────────────
# CACHE SETTINGS (minutes)
# ─────────────────────────────────────────────────────────────────
CACHE_OHLCV_INTRADAY_MIN = 5
CACHE_OHLCV_DAILY_MIN    = 60
CACHE_NEWS_MIN           = 60
CACHE_INR_USD_MIN        = 15       # v2.0: explicit INR/USD cache TTL

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

    Groww auth flow in this project:
      - GROWW_API_KEY and GROWW_TOTP_SECRET are required.
      - GROWW_ACCESS_TOKEN is optional at startup because the app can
        generate and refresh it from the TOTP secret when needed.
    """
    config_warnings = []

    if not GROWW_API_KEY or GROWW_API_KEY == "your_api_key_here":
        config_warnings.append("GROWW_API_KEY not set in .env")

    if not GROWW_TOTP_SECRET or GROWW_TOTP_SECRET == "your_totp_secret_here":
        config_warnings.append("GROWW_TOTP_SECRET not set in .env")

    if TRADING_MODE == "demo":
        if not ACTIVE_LLM["api_key"] or \
           ACTIVE_LLM["api_key"] == "your_openai_key_here":
            config_warnings.append(
                "OPENAI_API_KEY not set — demo LLM will not work"
            )

    if TRADING_MODE in ("paper", "production"):
        if not ACTIVE_LLM["api_key"] or \
           ACTIVE_LLM["api_key"] == "your_anthropic_key_here":
            config_warnings.append(
                "ANTHROPIC_API_KEY not set — paper/production LLM will not work"
            )

    if not TAVILY_API_KEY:
        config_warnings.append(
            "TAVILY_API_KEY not set — news context will be unavailable"
        )

    if CAPITAL_INR < 10000:
        config_warnings.append(
            f"CAPITAL_INR is ₹{CAPITAL_INR:,.0f} — "
            f"too low for MCX margin requirements"
        )

    # Margin sanity check against active contracts at typical prices
    # Uses conservative price estimates to warn if capital is insufficient
    TYPICAL_PRICES = {
        "GOLDM":      71000,    # ₹71,000 per 10g (approx March 2026)
        "CRUDEOILM":  6500,     # ₹6,500 per barrel (approx)
    }
    for symbol in ACTIVE_COMMODITIES:
        cfg = LOT_CONFIG.get(symbol, {})
        typical_ltp = TYPICAL_PRICES.get(symbol)
        if cfg and typical_ltp:
            margin_1_lot = get_margin_estimate_inr(symbol, typical_ltp)
            if margin_1_lot > CAPITAL_INR:
                config_warnings.append(
                    f"{cfg['friendly_name']}: margin for 1 lot ≈ "
                    f"₹{margin_1_lot:,.0f} exceeds capital ₹{CAPITAL_INR:,.0f}. "
                    f"You cannot trade this contract."
                )
            elif margin_1_lot > CAPITAL_INR * 0.6:
                config_warnings.append(
                    f"{cfg['friendly_name']}: margin for 1 lot ≈ "
                    f"₹{margin_1_lot:,.0f} uses {margin_1_lot/CAPITAL_INR*100:.0f}% "
                    f"of capital. Consider increasing CAPITAL_INR."
                )

    if TRADING_MODE == "production":
        config_warnings.append(
            "⚠ PRODUCTION MODE ACTIVE — real money at risk. "
            "Ensure paper trading validation is complete."
        )

    return config_warnings


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
    signal_quality: str = None,
) -> dict:
    """
    Calculate position size using pl_per_tick method.
    Returns full breakdown dict for transparency.

    This is the authoritative position sizing function.
    Risk Agent uses this output — never computes independently.

    v2.0 additions:
    - B-grade position reduction (50% of calculated lots)
    - Underlotted detection (raw_lots < 1.0)
    - Margin sufficiency check (margin vs capital threshold)
    - Risk overbudget blocking (actual_risk > budget × 1.5 → blocked)
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

    raw_lots = risk_budget_inr / risk_per_lot_inr

    # v2.0: B-grade signals get reduced position size
    if signal_quality == "B":
        raw_lots = raw_lots * B_GRADE_POSITION_REDUCTION

    position_lots = max(1, min(int(raw_lots), MAX_LOTS_PER_SIGNAL))
    actual_risk   = position_lots * risk_per_lot_inr

    # v2.0: Underlotted detection
    # When raw_lots < 1.0, we're forced to use 1 lot which exceeds
    # the risk budget. Flag this and check if it's dangerously over.
    underlotted = raw_lots < 1.0
    risk_overbudget_ratio = actual_risk / risk_budget_inr if risk_budget_inr > 0 else 0
    risk_blocked = (
        underlotted
        and risk_overbudget_ratio > RISK_OVERBUDGET_BLOCK_MULTIPLIER
    )

    # v2.0: Margin sufficiency check
    margin_1_lot  = get_margin_estimate_inr(symbol, entry_price)
    margin_total  = margin_1_lot * position_lots
    margin_pct_of_capital = (margin_total / capital * 100) if capital > 0 else 100
    margin_sufficient = margin_pct_of_capital <= MARGIN_UTILISATION_MAX_PCT

    return {
        "symbol":                symbol,
        "entry_price":           entry_price,
        "stop_loss":             stop_loss,
        "stop_distance":         round(stop_distance, 2),
        "stop_distance_ticks":   round(stop_distance_ticks, 1),
        "pl_per_tick":           cfg["pl_per_tick"],
        "risk_per_lot_inr":      round(risk_per_lot_inr, 2),
        "risk_budget_inr":       round(risk_budget_inr, 2),
        "raw_lots_calculated":   round(raw_lots, 2),
        "position_lots":         position_lots,
        "capped_at_max":         raw_lots > MAX_LOTS_PER_SIGNAL,
        "actual_risk_inr":       round(actual_risk, 2),
        "actual_risk_pct":       round(actual_risk / capital * 100, 2),
        "margin_est_inr":        round(margin_total, 2),
        "margin_est_per_lot":    round(margin_1_lot, 2),
        "margin_pct_of_capital": round(margin_pct_of_capital, 1),
        "margin_sufficient":     margin_sufficient,
        # v2.0 safety fields
        "underlotted":           underlotted,
        "risk_overbudget_ratio": round(risk_overbudget_ratio, 2),
        "risk_blocked":          risk_blocked,
        "risk_block_reason":     (
            f"Stop too wide: 1 lot risks ₹{actual_risk:,.0f} "
            f"({risk_overbudget_ratio:.1f}× budget of ₹{risk_budget_inr:,.0f}). "
            f"Max allowed: {RISK_OVERBUDGET_BLOCK_MULTIPLIER}×."
        ) if risk_blocked else (
            f"Margin insufficient: ₹{margin_total:,.0f} "
            f"({margin_pct_of_capital:.0f}% of capital, "
            f"max {MARGIN_UTILISATION_MAX_PCT}%)."
        ) if not margin_sufficient else None,
        "b_grade_reduced":       signal_quality == "B",
    }