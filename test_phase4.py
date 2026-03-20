"""
COMMODEX — Phase 4 Validation Test
Tests all 10 guardrails of the Risk Engine.
Run: python test_phase4.py
No LLM calls — pure deterministic tests.
"""

import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
load_dotenv()

print("=" * 55)
print("COMMODEX Phase 4 — Risk Engine Validation")
print("=" * 55)

passed = 0
failed = 0

def ok(msg):
    global passed; passed += 1
    print(f"  OK  — {msg}")

def fail(msg):
    global failed; failed += 1
    print(f"  FAIL — {msg}")

from core.risk_engine import RiskEngine
engine = RiskEngine()

# Helper — future expiry (14 days away)
future_expiry = (datetime.today() + timedelta(days=14)).strftime("%Y-%m-%d")
near_expiry   = (datetime.today() + timedelta(days=2)).strftime("%Y-%m-%d")

def run_check(label, **kwargs) -> dict:
    defaults = dict(
        symbol            = "GOLDM",
        action            = "BUY",
        confidence        = 70,
        rr_ratio          = 2.0,
        trading_style     = "system",
        inr_change_pct    = 0.1,
        contract_expiry   = future_expiry,
        high_impact_event = None,
        open_positions    = 0,
        daily_pnl_pct     = 0.0,
    )
    defaults.update(kwargs)
    return engine.check_all(**defaults)

print("\n--- BLOCK Tests (should all block) ---")

# G1 — Daily loss limit
r = run_check("G1", daily_pnl_pct=-5.5)
if not r["approved"] and any("loss limit" in b.lower() for b in r["block_reasons"]):
    ok("G1 Daily loss limit blocked correctly")
else:
    fail(f"G1 Daily loss limit: {r['block_reasons']}")

# G2 — Max positions
r = run_check("G2", open_positions=2)
if not r["approved"] and any("positions" in b.lower() for b in r["block_reasons"]):
    ok("G2 Max positions blocked correctly")
else:
    fail(f"G2 Max positions: {r['block_reasons']}")

# G3 — Min confidence
r = run_check("G3", confidence=40)
if not r["approved"] and any("confidence" in b.lower() for b in r["block_reasons"]):
    ok("G3 Min confidence blocked correctly")
else:
    fail(f"G3 Min confidence: {r['block_reasons']}")

# G6 — Min R:R
r = run_check("G6", rr_ratio=1.2)
if not r["approved"] and any("r:r" in b.lower() for b in r["block_reasons"]):
    ok("G6 Min R:R blocked correctly")
else:
    fail(f"G6 Min R:R: {r['block_reasons']}")

# G8 — Expiry week
r = run_check("G8", contract_expiry=near_expiry)
if not r["approved"] and any("expir" in b.lower() for b in r["block_reasons"]):
    ok("G8 Expiry week blocked correctly")
else:
    fail(f"G8 Expiry week: {r['block_reasons']}")

print("\n--- CAP Tests (should pass but cap confidence) ---")

# G5 — High impact event cap
r = run_check("G5", high_impact_event="FOMC rate decision today")
if r["confidence_cap"] <= 60:
    ok(f"G5 High impact capped at {r['confidence_cap']}%")
else:
    fail(f"G5 High impact cap: {r['confidence_cap']}")

# G9 — INR volatility cap
r = run_check("G9", inr_change_pct=0.6)
if r["confidence_cap"] <= 60:
    ok(f"G9 INR volatility capped at {r['confidence_cap']}%")
else:
    fail(f"G9 INR volatility cap: {r['confidence_cap']}")

print("\n--- PASS Tests (should all approve) ---")

# Clean scenario — all guardrails should pass
r = run_check("ALL_PASS")
if r["approved"]:
    ok("All guardrails passed — signal approved")
    for gr in r["guardrail_results"]:
        print(f"    {gr}")
else:
    fail(f"Clean scenario blocked: {r['block_reasons']}")

# HOLD action — should never be approved regardless
r = run_check("HOLD", action="HOLD")
if not r["approved"]:
    ok("HOLD action correctly not approved")
else:
    fail("HOLD action should never be approved")

print("\n--- DB Checks ---")
try:
    pnl = engine.get_daily_pnl_pct()
    ok(f"Daily P&L from DB: {pnl}%")
except Exception as e:
    fail(f"Daily P&L fetch: {e}")

try:
    pos = engine.get_open_positions_count()
    ok(f"Open positions from DB: {pos}")
except Exception as e:
    fail(f"Open positions fetch: {e}")

# Summary
total = passed + failed
print("\n" + "=" * 55)
print(f"Phase 4 Results: {passed}/{total} passing")
if failed == 0:
    print("ALL PASSING — Phase 4 complete, ready for Phase 5")
else:
    print("Review failures above before Phase 5")
print("=" * 55)