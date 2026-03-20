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
from config import TRADING_MODE, ACTIVE_LLM, MIN_CONFIDENCE_THRESHOLD, LOT_CONFIG

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

        # ── Production: Execute Real Order ─────────────────
        if (
            signal_id
            and result.final_action != "HOLD"
            and guardrail_check["approved"]
            and TRADING_MODE == "production"
        ):
            st.divider()
            st.subheader("🔴 Execute Trade — REAL MONEY")

            lots      = result.position_sizing.get("position_lots", 1) if result.position_sizing else 1
            entry_px  = result.risk.entry_price if result.risk else 0
            sl_px     = result.risk.stop_loss   if result.risk else 0
            t1_px     = result.risk.target_1    if result.risk else 0
            risk_inr  = result.position_sizing.get("actual_risk_inr", 0) if result.position_sizing else 0
            entry_typ = (result.risk.entry_type or "market").upper() if result.risk else "MARKET"

            # Margin check
            margin_ok = True
            try:
                from core.groww_client import GrowwClient as _GC
                _gc = _GC(access_token=token)
                margin_data = _gc.get_margin_available()
                # Groww returns nested dict — try common key paths
                avail_margin = (
                    margin_data.get("available_margin")
                    or margin_data.get("commodity_available")
                    or margin_data.get("net", {}).get("available")
                    or 0
                )
                lot_cfg      = LOT_CONFIG.get(commodity, {})
                margin_pct   = lot_cfg.get("margin_pct", 10)
                lot_size     = lot_cfg.get("lot_size", 100)
                # quote_unit is "per_10g" for gold — price is per 10g
                quote_unit   = lot_cfg.get("quote_unit", "")
                if quote_unit == "per_10g":
                    contract_val = entry_px * (lot_size / 10)
                else:
                    contract_val = entry_px * lot_size
                req_per_lot  = contract_val * margin_pct / 100
                req_total    = req_per_lot * lots

                mc1, mc2, mc3 = st.columns(3)
                with mc1:
                    st.metric("Available Margin", f"Rs{avail_margin:,.0f}")
                with mc2:
                    st.metric("Required Margin", f"Rs{req_total:,.0f}")
                with mc3:
                    if avail_margin >= req_total:
                        st.success("✓ Sufficient")
                    else:
                        st.error(f"✗ Short by Rs{req_total - avail_margin:,.0f}")
                        margin_ok = False
            except Exception as _me:
                st.warning(f"Margin check unavailable: {_me}")

            # Order confirmation
            st.warning(
                f"**{result.final_action}** {lots} lot(s) of **{commodity}** at "
                f"Rs{entry_px:,.2f} ({entry_typ})  |  "
                f"SL: Rs{sl_px:,.2f}  |  T1: Rs{t1_px:,.2f}  |  "
                f"Risk: Rs{risk_inr:,.0f}"
            )
            exec_confirm = st.checkbox(
                "I confirm this places a REAL MONEY MCX order",
                key="exec_confirm",
            )
            if exec_confirm and margin_ok:
                if st.button("🔴 EXECUTE ORDER NOW", type="primary", key="exec_btn"):
                    try:
                        from core.groww_client import GrowwClient as _GC2
                        _gc2 = _GC2(access_token=token)

                        # Strip exchange prefix from contract symbol if present
                        contract_sym = result.contract
                        if contract_sym.upper().startswith("MCX_"):
                            contract_sym = contract_sym[4:]

                        order_res = _gc2.place_mcx_order(
                            trading_symbol   = contract_sym,
                            transaction_type = result.final_action,
                            lots             = lots,
                            order_type       = entry_typ,
                            price            = entry_px if entry_typ == "LIMIT" else 0.0,
                        )
                        groww_order_id = (
                            order_res.get("groww_order_id")
                            or order_res.get("order_id")
                            or str(order_res)
                        )

                        # Log to trades_log
                        _conn = get_connection()
                        _cur  = _conn.cursor()
                        _cur.execute("""
                            INSERT INTO trades_log (
                                signal_id, commodity, contract, mode, action, lots,
                                entry_price, entry_time,
                                stop_loss, target_1, target_2,
                                order_id, order_status, notes
                            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        """, (
                            signal_id,
                            commodity,
                            result.contract,
                            TRADING_MODE,
                            result.final_action,
                            lots,
                            entry_px,
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            sl_px,
                            t1_px,
                            result.risk.target_2 if result.risk else None,
                            groww_order_id,
                            "OPEN",
                            "Executed via COMMODEX production mode",
                        ))
                        _conn.execute(
                            "UPDATE signals_log SET followed=1 WHERE id=?",
                            (signal_id,),
                        )
                        _conn.commit()
                        _conn.close()

                        st.success(
                            f"✅ Order placed!  "
                            f"Groww Order ID: **{groww_order_id}**  |  "
                            f"Trade logged.  Go to Trade Log to manage exits."
                        )
                    except Exception as _oe:
                        st.error(f"Order placement failed: {_oe}")
                        import traceback
                        st.code(traceback.format_exc())

        # ── Paper / Demo: Follow / Ignore tracking ─────────
        elif signal_id and result.final_action != "HOLD" and TRADING_MODE != "production":
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