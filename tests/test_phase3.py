"""
COMMODEX — Phase 3 Validation Test
Tests full 3-agent pipeline end to end.
Run: python test_phase3.py
"""

import sys
import os
from dotenv import load_dotenv
load_dotenv()

print("=" * 55)
print("COMMODEX Phase 3 — Agent Pipeline Validation")
print("=" * 55)
print(f"Mode: {os.getenv('TRADING_MODE', 'demo')}")
print(f"This test makes real LLM API calls — costs apply")
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

# ── 1. LLMClient ───────────────────────────────────────────
print("\n[1/5] LLMClient Initialisation")
try:
    from core.llm_client import LLMClient
    llm = LLMClient()
    ok(f"Provider : {llm.provider}")
    ok(f"Model    : {llm.model}")
except Exception as e:
    fail(f"LLMClient init: {e}")
    sys.exit(1)

# ── 2. Prompt Loading ──────────────────────────────────────
print("\n[2/5] Prompt Files")
from core.llm_client import load_prompt
for agent in ["analyst", "signal", "risk"]:
    try:
        prompt = load_prompt(agent, "1.0")
        if len(prompt) > 50:
            ok(f"{agent}_v1.0.txt loaded ({len(prompt)} chars)")
        else:
            warn(f"{agent}_v1.0.txt too short — check file content")
    except Exception as e:
        fail(f"{agent} prompt: {e}")

# ── 3. Data Bundle ─────────────────────────────────────────
print("\n[3/5] Data Bundle Assembly")
bundle = None
try:
    from core.groww_client import GrowwClient
    from core.technical_engine import TechnicalEngine
    from core.news_client import NewsClient
    from core.data_bundle import DataBundleAssembler

    groww     = GrowwClient(access_token=token)
    tech      = TechnicalEngine()
    news      = NewsClient()
    assembler = DataBundleAssembler(groww, tech, news)
    bundle    = assembler.assemble("GOLDM", "15minute", "system")

    ok(f"Bundle quality : {bundle.data_quality}")
    ok(f"LTP            : Rs{bundle.ltp:,.2f}")
    ok(f"Confidence cap : {bundle.confidence_cap}%")
except Exception as e:
    fail(f"DataBundle: {e}")
    sys.exit(1)

# ── 4. Agent 1 + Sanity Check ──────────────────────────────
print("\n[4/5] Agent 1 — Market Analyst + Sanity Check")
analysis = None
try:
    from core.agents.analyst_agent import AnalystAgent, SanityChecker
    analyst  = AnalystAgent(llm)
    analysis = analyst.analyse(bundle)

    ok(f"Regime      : {analysis.market_regime}")
    ok(f"Trend       : {analysis.trend_strength}")
    ok(f"Sentiment   : {analysis.overall_sentiment} ({analysis.sentiment_confidence}%)")
    ok(f"Technical   : {analysis.technical_summary[:80]}...")
    ok(f"India       : {analysis.india_specific_factors[:80]}...")
    ok(f"Global      : {analysis.global_risk_factors[:80]}...")
    if analysis.high_impact_events_next_24h:
        warn(f"High impact : {analysis.high_impact_events_next_24h}")
    ok(f"Notes       : {analysis.analyst_notes[:80]}...")

    # Sanity check
    sanity = SanityChecker().check(analysis, bundle)
    if sanity["passed"]:
        ok("Sanity check : PASSED — no contradictions")
    else:
        warn(f"Sanity check : {len(sanity['warnings'])} warning(s)")
        for w in sanity["warnings"]:
            warn(f"  > {w}")

except Exception as e:
    fail(f"AnalystAgent: {e}")
    import traceback; traceback.print_exc()
    sys.exit(1)

# ── 5. Full Pipeline ───────────────────────────────────────
print("\n[5/5] Full Pipeline — SignalOrchestrator")
try:
    from core.orchestrator import SignalOrchestrator
    orchestrator = SignalOrchestrator()
    result       = orchestrator.generate(
        symbol="GOLDM",
        timeframe="15minute",
        trading_style="system",
    )

    ok(f"Pipeline stage : {result.pipeline_stage}")
    ok(f"Final action   : {result.final_action}")
    ok(f"Confidence     : {result.final_confidence}%")
    ok(f"Approved       : {result.approved}")

    if result.signal:
        ok(f"Quality        : {result.signal.signal_quality}")
        ok(f"Reason         : {result.signal.primary_reason[:80]}...")
        if result.signal.supporting_factors:
            ok(f"Supporting     : {result.signal.supporting_factors[0][:60]}...")

    if result.risk and result.approved:
        ok(f"Entry          : Rs{result.risk.entry_price:,.2f}")
        ok(f"Stop Loss      : Rs{result.risk.stop_loss:,.2f}")
        ok(f"Target 1       : Rs{result.risk.target_1:,.2f}")
        ok(f"R:R Ratio      : {result.risk.risk_reward_ratio}")

    if result.position_sizing:
        ps = result.position_sizing
        ok(f"Lots           : {ps.get('position_lots')}")
        ok(f"Capital risk   : Rs{ps.get('actual_risk_inr'):,.0f} ({ps.get('actual_risk_pct')}%)")

    if result.block_reason:
        warn(f"Block reason   : {result.block_reason}")

    if result.error:
        warn(f"Error          : {result.error}")

    print("\n  --- Full Signal Display ---")
    display = result.to_display_dict()
    for k, v in display.items():
        if v is not None:
            print(f"  {k:20s}: {v}")

except Exception as e:
    fail(f"SignalOrchestrator: {e}")
    import traceback; traceback.print_exc()

# ── Summary ────────────────────────────────────────────────
total = passed + failed
print("\n" + "=" * 55)
print(f"Phase 3 Results: {passed}/{total} passing")
if failed == 0:
    print("ALL PASSING — Phase 3 complete, ready for Phase 4")
else:
    print("Review failures above before Phase 4")
print("=" * 55)