"""
COMMODEX — Signal Engine
Run AI analysis and generate trading signals.
The core page of the application.
"""

import streamlit as st
import os
import json
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

from core.ui_helpers import (
    render_sidebar, render_signal_badge,
    render_technicals, render_risk_params,
    render_guardrails,
)
from core.db import get_connection, init as db_init
from config import TRADING_MODE, ACTIVE_LLM, MIN_CONFIDENCE_THRESHOLD

st.set_page_config(
    page_title="Signal Engine — COMMODEX",
    page_icon="⚡",
    layout="wide",
)

db_init()
render_sidebar()

st.title("⚡ Signal Engine")
st.caption(
    f"AI-powered MCX commodity signal generation  |  "
    f"Provider: {ACTIVE_LLM['provider'].upper()}  |  "
    f"Model: {ACTIVE_LLM['model']}"
)

# ── Controls ───────────────────────────────────────────────
st.subheader("Analysis Parameters")

ctrl1, ctrl2, ctrl3 = st.columns([2, 2, 1])

with ctrl1:
    commodity = st.selectbox(
        "Commodity",
        options=["GOLDM", "CRUDEOILM"],
        format_func=lambda x: {
            "GOLDM":     "◈ Gold Mini (GOLDM)",
            "CRUDEOILM": "⬡ Crude Oil Mini (CRUDEOILM)",
        }.get(x, x)
    )

with ctrl2:
    trading_style = st.selectbox(
        "Trading Style",
        options=["system", "intraday", "swing"],
        format_func=lambda x: {
            "system":   "🤖 System Decides",
            "intraday": "⚡ Intraday Only",
            "swing":    "📈 Swing / Positional",
        }.get(x, x)
    )

with ctrl3:
    st.write("")
    st.write("")
    run_button = st.button(
        "▶ Run Analysis",
        type    = "primary",
        use_container_width = True,
    )

# ── Pipeline Status ────────────────────────────────────────
if run_button:
    st.divider()
    st.subheader("Pipeline Status")

    # Stage progress placeholders
    stages = [
        ("📡", "Data Collection",  "Fetching live prices, history, news..."),
        ("🔬", "Market Analyst",   "Agent 1 analysing market conditions..."),
        ("⚡", "Signal Generator", "Agent 2 generating trading signal..."),
        ("🛡", "Risk Assessment",  "Agent 3 computing risk parameters..."),
        ("✅", "Guardrails",       "Validating against all 10 guardrails..."),
    ]

    progress_bar  = st.progress(0)
    status_text   = st.empty()
    result_holder = st.empty()

    try:
        # Initialise
        status_text.info("⏳ Initialising...")

        from generate_token import generate_totp_token, save_token_to_env
        token = generate_totp_token()
        save_token_to_env(token)
        os.environ["GROWW_ACCESS_TOKEN"] = token

        from core.orchestrator import SignalOrchestrator
        from core.risk_engine import RiskEngine

        orchestrator = SignalOrchestrator()
        risk_engine  = RiskEngine()

        # Progress updates
        for i, (icon, name, desc) in enumerate(stages):
            progress_bar.progress((i + 1) * 20)
            status_text.info(f"{icon} **{name}**: {desc}")

            if i == 0:
                # Actually run the pipeline on stage 1
                with st.spinner("Running full pipeline..."):
                    result = orchestrator.generate(
                        symbol        = commodity,
                        timeframe     = "15minute",
                        trading_style = trading_style,
                    )
                break   # pipeline runs all stages internally

        progress_bar.progress(80)
        status_text.info("🛡 Running guardrails...")

        # Run guardrails
        inr_change = None
        if result.analysis:
            from core.inr_usd import get_inr_usd_rate
            inr_data   = get_inr_usd_rate()
            inr_change = inr_data.get("change_pct")

        contract_expiry = None
        try:
            from core.groww_client import GrowwClient
            gc       = GrowwClient(access_token=token)
            contract = gc.find_active_contract(commodity)
            if contract:
                contract_expiry = contract.get("expiry_date")
        except Exception:
            pass

        guardrail_check = risk_engine.check_all(
            symbol             = commodity,
            action             = result.final_action,
            confidence         = result.final_confidence,
            rr_ratio           = result.risk.risk_reward_ratio if result.risk else None,
            trading_style      = trading_style,
            inr_change_pct     = inr_change,
            contract_expiry    = contract_expiry,
            high_impact_event  = result.analysis.high_impact_events_next_24h if result.analysis else None,
            open_positions     = risk_engine.get_open_positions_count(),
            daily_pnl_pct      = risk_engine.get_daily_pnl_pct(),
        )

        progress_bar.progress(100)
        status_text.success("✅ Analysis complete")

        # Persist to DB
        try:
            conn   = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO signals_log (
                    commodity, contract, timeframe, trading_style,
                    mode, llm_provider, llm_model, prompt_version,
                    action, confidence, signal_quality,
                    entry_price, stop_loss, target_1, target_2, rr_ratio,
                    position_lots, capital_risk_pct, capital_risk_inr,
                    market_regime, sentiment, primary_reason,
                    analyst_output, signal_output, risk_output,
                    guardrail_flags, news_available
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                commodity,
                result.contract,
                "15minute",
                trading_style,
                TRADING_MODE,
                ACTIVE_LLM["provider"],
                ACTIVE_LLM["model"],
                "1.0",
                result.final_action,
                result.final_confidence,
                result.signal.signal_quality if result.signal else None,
                result.risk.entry_price if result.risk else None,
                result.risk.stop_loss   if result.risk else None,
                result.risk.target_1    if result.risk else None,
                result.risk.target_2    if result.risk else None,
                result.risk.risk_reward_ratio if result.risk else None,
                result.position_sizing.get("position_lots") if result.position_sizing else None,
                result.position_sizing.get("actual_risk_pct") if result.position_sizing else None,
                result.position_sizing.get("actual_risk_inr") if result.position_sizing else None,
                result.analysis.market_regime if result.analysis else None,
                result.analysis.overall_sentiment if result.analysis else None,
                result.signal.primary_reason if result.signal else None,
                json.dumps(result.analysis.model_dump()) if result.analysis else None,
                json.dumps(result.signal.model_dump())   if result.signal   else None,
                json.dumps(result.risk.model_dump())     if result.risk     else None,
                json.dumps(guardrail_check["block_reasons"]),
                1,
            ))
            signal_id = cursor.lastrowid
            conn.commit()
            conn.close()
        except Exception as e:
            st.warning(f"Signal not saved to DB: {e}")
            signal_id = None

        # ── Display Results ────────────────────────────────
        st.divider()
        st.subheader("Signal Result")

        # Main signal badge
        render_signal_badge(
            result.final_action,
            result.final_confidence,
            result.signal.signal_quality if result.signal else "N/A",
        )

        # Block reasons
        if guardrail_check["block_reasons"]:
            for reason in guardrail_check["block_reasons"]:
                st.warning(f"🚫 {reason}")

        # Guardrail status
        with st.expander("Guardrail Status", expanded=False):
            render_guardrails(guardrail_check["guardrail_results"])
            for gr in guardrail_check["guardrail_results"]:
                icon = "✅" if gr.passed else "🚫"
                st.caption(f"{icon} {gr.name}: {gr.reason}")

        st.divider()

        # Two column layout — analysis + technicals
        left, right = st.columns([1, 1])

        with left:
            st.subheader("Market Analysis")
            if result.analysis:
                a = result.analysis
                st.markdown(f"**Regime**: {a.market_regime} ({a.trend_strength})")
                st.markdown(f"**Sentiment**: {a.overall_sentiment} ({a.sentiment_confidence}%)")
                st.markdown(f"**Technical**: {a.technical_summary}")
                st.markdown(f"**India Factors**: {a.india_specific_factors}")
                st.markdown(f"**Global Factors**: {a.global_risk_factors}")
                if a.high_impact_events_next_24h:
                    st.warning(f"⚠ High Impact: {a.high_impact_events_next_24h}")
                if a.analyst_notes:
                    st.caption(f"Notes: {a.analyst_notes}")

            if result.signal and result.final_action != "HOLD":
                st.divider()
                st.subheader("Signal Reasoning")
                s = result.signal
                st.markdown(f"**Primary**: {s.primary_reason}")
                if s.supporting_factors:
                    st.markdown("**Supporting:**")
                    for f in s.supporting_factors:
                        st.markdown(f"  - {f}")
                if s.contradicting_factors:
                    st.markdown("**Contradicting:**")
                    for f in s.contradicting_factors:
                        st.markdown(f"  - ⚠ {f}")
                st.caption(f"Invalidation: {s.invalidation_condition}")
                st.caption(f"Timeframe: {s.recommended_timeframe}")

            elif result.signal and result.final_action == "HOLD":
                st.divider()
                st.info(
                    f"**HOLD Reason**: "
                    f"{result.signal.hold_reasoning or result.signal.primary_reason}"
                )

        with right:
            st.subheader("Technical Indicators")
            if result.analysis:
                bundle_tech = None
                try:
                    from core.groww_client import GrowwClient
                    from core.technical_engine import TechnicalEngine
                    gc2      = GrowwClient(access_token=token)
                    contract = gc2.find_active_contract(commodity)
                    if contract:
                        candles = gc2.get_historical(
                            contract["trading_symbol"],
                            interval="15minute",
                            days=30,
                        )
                        te = TechnicalEngine()
                        bundle_tech = te.compute(
                            candles, commodity, "15minute"
                        )
                except Exception:
                    pass

                render_technicals(bundle_tech)

        # Risk parameters
        if result.risk and result.approved:
            st.divider()
            st.subheader("Risk Parameters")
            render_risk_params(result.risk, result.position_sizing)

        # Follow / Ignore buttons
        if signal_id and result.final_action != "HOLD":
            st.divider()
            st.subheader("Did you follow this signal?")
            fc1, fc2, _ = st.columns([1, 1, 3])
            with fc1:
                if st.button("✅ Yes, I followed it", key="followed"):
                    conn = get_connection()
                    conn.execute(
                        "UPDATE signals_log SET followed=1 WHERE id=?",
                        (signal_id,)
                    )
                    conn.commit()
                    conn.close()
                    st.success("Marked as followed")
            with fc2:
                if st.button("❌ No, I ignored it", key="ignored"):
                    conn = get_connection()
                    conn.execute(
                        "UPDATE signals_log SET followed=0 WHERE id=?",
                        (signal_id,)
                    )
                    conn.commit()
                    conn.close()
                    st.info("Marked as ignored")

    except Exception as e:
        progress_bar.progress(100)
        status_text.error(f"Pipeline error: {e}")
        import traceback
        st.code(traceback.format_exc())