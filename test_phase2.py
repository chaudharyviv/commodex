"""
COMMODEX — Phase 2 Validation Test
Tests: TechnicalEngine, NewsClient, INR/USD, DataBundle assembly
Run: python test_phase2.py
"""

import sys
import os
from dotenv import load_dotenv
load_dotenv()

print("=" * 55)
print("COMMODEX Phase 2 — Data Pipeline Validation")
print("=" * 55)

passed = 0
failed = 0

def ok(msg):
    global passed; passed += 1
    print(f"  OK  — {msg}")

def fail(msg):
    global failed; failed += 1
    print(f"  FAIL — {msg}")

def warn(msg):
    print(f"  WARN — {msg}")

# ── Setup ──────────────────────────────────────────────────
from generate_token import generate_totp_token, save_token_to_env
token = generate_totp_token()
save_token_to_env(token)
os.environ["GROWW_ACCESS_TOKEN"] = token

from core.groww_client import GrowwClient
from core.technical_engine import TechnicalEngine
from core.news_client import NewsClient
from core.inr_usd import get_inr_usd_rate
from core.data_bundle import DataBundleAssembler

groww = GrowwClient(access_token=token)
tech  = TechnicalEngine()
news  = NewsClient()

# ── 1. Technical Engine ────────────────────────────────────
print("\n[1/4] Technical Engine — GOLDM 30 days 15min")
try:
    contract = groww.find_active_contract("GOLDM")
    candles  = groww.get_historical(
        contract["trading_symbol"], interval="15minute", days=30
    )
    result = tech.compute(candles, symbol="GOLDM", timeframe="15minute")

    if result is None:
        fail("TechnicalEngine returned None — check return statement at end of compute()")
    else:
        ok(f"{result.candle_count} candles processed")

    ok(f"{result.candle_count} candles processed")
    ok(f"Latest price : Rs{result.latest_price:,.2f}")
    ok(f"RSI(14)      : {result.rsi_14} [{result.rsi_signal}]")
    ok(f"MACD         : line={result.macd_line} [{result.macd_cross}]")
    ok(f"EMA20={result.ema_20:,.0f}  EMA50={result.ema_50:,.0f}  [{result.ema_trend}]")
    ok(f"BB           : {result.bb_position}  width={result.bb_width}%")
    ok(f"ATR(14)      : {result.atr_14:,.0f} ({result.atr_pct}%)")
    ok(f"Pivot        : {result.pivot:,.0f}  R1={result.r1:,.0f}  S1={result.s1:,.0f}")
    ok(f"Day range    : H={result.day_high:,.0f}  L={result.day_low:,.0f}")
    ok(f"Volume       : {result.volume_current:,} [{result.volume_signal}]")

    print("\n  --- Summary String for Agent 1 ---")
    print(result.summary_string())

except Exception as e:
    fail(f"TechnicalEngine: {e}")
    import traceback; traceback.print_exc()

# ── 2. INR/USD Rate ────────────────────────────────────────
print("\n[2/4] INR/USD Rate")
try:
    inr = get_inr_usd_rate()
    if inr.get("available"):
        ok(f"Rate      : {inr['rate']} INR per USD")
        ok(f"Change    : {inr['change_pct']:+.3f}%")
        ok(f"Direction : {inr['direction']}")
        ok(f"Signal    : {inr['signal']}")
    else:
        fail(f"INR/USD unavailable: {inr.get('error')}")
except Exception as e:
    fail(f"INR/USD fetch: {e}")

# ── 3. News Client ─────────────────────────────────────────
print("\n[3/4] News Client — GOLDM")
try:
    result = news.fetch("GOLDM")
    if result["available"]:
        ok(f"{len(result['articles'])} articles fetched")
        ok(f"From cache: {result['from_cache']}")
        for i, a in enumerate(result["articles"][:3], 1):
            print(f"  {i}. {a['headline'][:70]}")
    else:
        warn(f"News unavailable: {result['summary']}")
        warn("Check TAVILY_API_KEY in .env")
except Exception as e:
    fail(f"NewsClient: {e}")

# ── 4. Full Data Bundle ────────────────────────────────────
print("\n[4/4] Full Data Bundle Assembly — GOLDM")
try:
    assembler = DataBundleAssembler(groww, tech, news)
    bundle = assembler.assemble(
        symbol="GOLDM",
        timeframe="15minute",
        trading_style="system",
    )
    ok(f"Bundle assembled — quality: {bundle.data_quality}")
    ok(f"LTP available    : {bundle.ltp_available} (Rs{bundle.ltp:,.2f})")
    ok(f"Technicals ok    : {bundle.technicals_ok}")
    ok(f"News available   : {bundle.news_available}")
    ok(f"INR/USD rate     : {bundle.inr_usd_rate}")
    ok(f"Confidence cap   : {bundle.confidence_cap}%")
    if bundle.cap_reasons:
        for r in bundle.cap_reasons:
            warn(f"Cap reason: {r}")

    print("\n  --- Full Prompt String for Agent 1 ---")
    print(bundle.to_prompt_string())

except Exception as e:
    fail(f"DataBundle: {e}")
    import traceback; traceback.print_exc()

# ── Summary ────────────────────────────────────────────────
total = passed + failed
print("\n" + "=" * 55)
print(f"Phase 2 Results: {passed}/{total} passing")
if failed == 0:
    print("ALL PASSING — Phase 2 complete, ready for Phase 3")
else:
    print("Review failures above before Phase 3")
print("=" * 55)