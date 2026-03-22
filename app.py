import streamlit as st
import logging
from config import TRADING_MODE, validate_config
from core.db import init as db_init, health_check
from core.ui_helpers import render_sidebar

st.set_page_config(page_title="COMMODEX", page_icon="⬡", layout="wide", initial_sidebar_state="expanded")

if "app_initialised" not in st.session_state:
    db_init()
    st.session_state["app_initialised"] = True

# All common imports used in pages
import os
import json
import pandas as pd
from datetime import datetime, date
from dotenv import load_dotenv, set_key
from pathlib import Path

def render_dashboard():
    """
    COMMODEX — Dashboard
    Live prices, latest signals, daily summary, market alerts.
    """
    
    import streamlit as st
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    from core.ui_helpers import render_sidebar, render_signal_badge
    from core.db import get_connection, init as db_init
    from core.inr_usd import get_inr_usd_rate
    from config import (
        TRADING_MODE,
        CAPITAL_INR,
        ACTIVE_LOT_CONFIG,
        get_active_instrument_symbols,
        get_instrument_label,
        build_exchange_trading_symbol,
    )
    
    
    
    
    
    
    st.title("📊 Dashboard")
    st.caption("Live Indian commodity prices and latest signals")
    
    # ── Refresh button ─────────────────────────────────────────
    if st.button("🔄 Refresh Prices", type="secondary"):
        st.cache_data.clear()
        st.rerun()
    
    # ── Live Prices ────────────────────────────────────────────
    st.subheader("Live Commodity Prices")
    
    @st.cache_data(ttl=30)   # refresh every 30 seconds
    def fetch_live_prices():
        try:
            from generate_token import generate_totp_token, save_token_to_env
            token = generate_totp_token()
            save_token_to_env(token)
            os.environ["GROWW_ACCESS_TOKEN"] = token
    
            from core.groww_client import GrowwClient
            client = GrowwClient(access_token=token)
    
            contracts = {}
            exchange_symbols = []
            for symbol in get_active_instrument_symbols():
                contract = client.find_active_contract(symbol)
                if contract:
                    contracts[symbol] = contract
                    exchange_symbols.append(
                        build_exchange_trading_symbol(
                            trading_symbol=contract["trading_symbol"],
                            exchange=contract.get("exchange"),
                        )
                    )

            prices = client.get_ltp(exchange_symbols) if exchange_symbols else {}
            quotes = {}

            for symbol, contract in contracts.items():
                try:
                    quotes[symbol] = client.get_quote(
                        contract["trading_symbol"],
                        exchange=contract.get("exchange", "MCX"),
                    )
                except Exception:
                    continue

            return {
                "contracts": contracts,
                "prices":    prices,
                "quotes":    quotes,
            }
        except Exception as e:
            return {"error": str(e)}
    
    with st.spinner("Fetching live prices..."):
        price_data = fetch_live_prices()
    
    if "error" in price_data:
        st.error(f"Price fetch failed: {price_data['error']}")
    else:
        active_symbols = get_active_instrument_symbols()
        columns = st.columns(min(3, max(1, len(active_symbols))))

        for idx, symbol in enumerate(active_symbols):
            cfg = ACTIVE_LOT_CONFIG.get(symbol, {})
            contract = price_data["contracts"].get(symbol)
            quote = price_data["quotes"].get(symbol, {})
            with columns[idx % len(columns)]:
                st.markdown(f"### {get_instrument_label(symbol, include_exchange=False)}")
                if contract:
                    key = build_exchange_trading_symbol(
                        trading_symbol=contract["trading_symbol"],
                        exchange=contract.get("exchange"),
                    )
                    ltp = price_data["prices"].get(key, 0)
                    day_change = quote.get("day_change_perc", 0) if quote else 0
                    st.metric(
                        label=f"LTP ({cfg.get('quote_unit', 'price').replace('_', ' ')})",
                        value=f"Rs{ltp:,.2f}",
                        delta=f"{day_change:+.2f}%" if day_change else None,
                    )
                    if quote:
                        ohlc = quote.get("ohlc", {}) if isinstance(quote.get("ohlc"), dict) else {}
                        st.caption(f"Contract: {contract['trading_symbol']}")
                        st.caption(f"Open: Rs{ohlc.get('open', 'N/A')}")
                        st.caption(
                            f"Volume: {quote.get('volume', 'N/A'):,}"
                            if quote.get("volume")
                            else "Volume: N/A"
                        )
                else:
                    st.warning(f"{symbol} contract not found")
    
    # ── INR/USD ────────────────────────────────────────────────
    st.divider()
    st.subheader("INR / USD")
    inr = get_inr_usd_rate()
    ic1, ic2, ic3 = st.columns(3)
    with ic1:
        st.metric("Rate", f"{inr.get('rate', 'N/A')}")
    with ic2:
        st.metric("Change", f"{inr.get('change_pct', 0):+.3f}%")
    with ic3:
        signal = inr.get("signal", "unknown")
        if signal == "volatile":
            st.error(f"⚠ INR {inr.get('direction', '')} — VOLATILE")
        else:
            st.success(f"✓ INR {inr.get('direction', '')} — stable")
    
    # ── Latest Signals ─────────────────────────────────────────
    st.divider()
    st.subheader("Latest Signals")
    
    def get_latest_signals(limit: int = 6) -> list:
        try:
            conn   = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT commodity, contract, action, confidence,
                       signal_quality, market_regime, timestamp,
                       primary_reason, followed, mode
                FROM signals_log
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            rows = [dict(r) for r in cursor.fetchall()]
            conn.close()
            return rows
        except Exception:
            return []
    
    signals = get_latest_signals()
    
    if not signals:
        st.info("No signals generated yet. Go to Signal Engine to run your first analysis.")
    else:
        for sig in signals:
            with st.expander(
                f"{sig['commodity']}  |  "
                f"{'▲' if sig['action']=='BUY' else '▼' if sig['action']=='SELL' else '◆'} "
                f"{sig['action']}  |  "
                f"{sig['confidence']}%  |  "
                f"{sig['timestamp']}",
                expanded=False,
            ):
                render_signal_badge(
                    sig["action"],
                    sig["confidence"],
                    sig["signal_quality"] or "N/A",
                )
                sc1, sc2, sc3 = st.columns(3)
                with sc1:
                    st.caption(f"Regime: {sig.get('market_regime', 'N/A')}")
                with sc2:
                    st.caption(f"Contract: {sig.get('contract', 'N/A')}")
                with sc3:
                    followed = sig.get("followed")
                    if followed == 1:
                        st.caption("✅ Followed")
                    elif followed == 0:
                        st.caption("❌ Ignored")
                    else:
                        st.caption("⏳ Pending")
                if sig.get("primary_reason"):
                    st.caption(f"Reason: {sig['primary_reason']}")
    
    # ── Today's Summary ────────────────────────────────────────
    st.divider()
    st.subheader("Today's Summary")
    
    def get_today_summary() -> dict:
        try:
            from datetime import date
            conn   = get_connection()
            cursor = conn.cursor()
            today  = date.today().isoformat()
    
            cursor.execute("""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN followed=1 THEN 1 ELSE 0 END) as followed,
                       SUM(CASE WHEN action='BUY'  THEN 1 ELSE 0 END) as buys,
                       SUM(CASE WHEN action='SELL' THEN 1 ELSE 0 END) as sells,
                       SUM(CASE WHEN action='HOLD' THEN 1 ELSE 0 END) as holds
                FROM signals_log
                WHERE DATE(timestamp) = ? AND mode = ?
            """, (today, TRADING_MODE))
            sig_row = dict(cursor.fetchone())
    
            cursor.execute("""
                SELECT COALESCE(SUM(pnl_inr), 0) as pnl,
                       COUNT(*) as trades
                FROM trades_log
                WHERE DATE(entry_time) = ? AND mode = ?
            """, (today, TRADING_MODE))
            pnl_row = dict(cursor.fetchone())
            conn.close()
    
            return {**sig_row, **pnl_row}
        except Exception:
            return {}
    
    summary = get_today_summary()
    ts1, ts2, ts3, ts4, ts5 = st.columns(5)
    with ts1:
        st.metric("Signals Today", summary.get("total", 0))
    with ts2:
        st.metric("Followed", summary.get("followed", 0))
    with ts3:
        st.metric("BUY / SELL / HOLD",
            f"{summary.get('buys',0)} / "
            f"{summary.get('sells',0)} / "
            f"{summary.get('holds',0)}"
        )
    with ts4:
        pnl = summary.get("pnl", 0) or 0
        st.metric("Paper P&L",
            f"Rs{pnl:,.0f}",
            delta=f"{pnl/CAPITAL_INR*100:.2f}%" if CAPITAL_INR else None,
        )
    with ts5:
        st.metric("Trades", summary.get("trades", 0))
    
    # ── Live Positions (Production Mode) ───────────────────────
    if TRADING_MODE == "production":
        st.divider()
        st.subheader("Live Positions")
    
        @st.cache_data(ttl=30)
        def fetch_live_positions():
            try:
                from generate_token import generate_totp_token, save_token_to_env
                tok = generate_totp_token()
                save_token_to_env(tok)
                os.environ["GROWW_ACCESS_TOKEN"] = tok
    
                from core.groww_client import GrowwClient
                gc = GrowwClient(access_token=tok)
                return gc.get_live_positions(), None
            except Exception as e:
                return [], str(e)
    
        positions, pos_err = fetch_live_positions()
    
        if pos_err:
            st.warning(f"Could not fetch positions: {pos_err}")
        elif not positions:
            st.info("No open commodity positions.")
        else:
            import pandas as pd
            pos_df = pd.DataFrame(positions)
            st.dataframe(pos_df, width='stretch')
    
            # MTM summary
            try:
                mtm_cols = [c for c in pos_df.columns if "mtm" in c.lower() or "pnl" in c.lower()]
                if mtm_cols:
                    total_mtm = pos_df[mtm_cols[0]].sum()
                    st.metric(
                        "Total MTM P&L",
                        f"Rs{total_mtm:,.0f}",
                        delta=f"{total_mtm/CAPITAL_INR*100:.2f}%" if CAPITAL_INR else None,
                    )
            except Exception:
                pass

def render_signal_engine():
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
    from config import (
        TRADING_MODE,
        ACTIVE_LLM,
        MIN_CONFIDENCE_THRESHOLD,
        LOT_CONFIG,
        ACTIVE_LOT_CONFIG,
        get_active_instrument_symbols,
        get_instrument_label,
        get_instrument_exchange,
        strip_exchange_prefix,
    )
    
    
    
    
    
    
    st.title("⚡ Signal Engine")
    st.caption(
        f"AI-powered Indian commodity signal generation  |  "
        f"Provider: {ACTIVE_LLM['provider'].upper()}  |  "
        f"Model: {ACTIVE_LLM['model']}"
    )
    
    # ── Controls ───────────────────────────────────────────────
    st.subheader("Analysis Parameters")
    
    ctrl1, ctrl2, ctrl3 = st.columns([2, 2, 1])
    commodity_options = get_active_instrument_symbols()
    
    with ctrl1:
        commodity = st.selectbox(
            "Commodity",
            options=commodity_options,
            format_func=get_instrument_label,
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
            width="stretch",
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
                        if a.high_impact_events_next_24h.lower() not in ("null", "none", ""):
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
    
                            contract_sym = strip_exchange_prefix(result.contract)

                            order_res = _gc2.place_commodity_order(
                                trading_symbol   = contract_sym,
                                transaction_type = result.final_action,
                                lots             = lots,
                                exchange         = get_instrument_exchange(commodity),
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

def render_trade_log():
    """
    COMMODEX — Trade Log
    All signals, paper trades, P&L tracking, win rate.
    """
    
    import streamlit as st
    import pandas as pd
    from datetime import datetime
    from dotenv import load_dotenv
    load_dotenv()
    
    from core.ui_helpers import render_sidebar
    from core.db import get_connection, init as db_init
    from config import (
        TRADING_MODE,
        CAPITAL_INR,
        get_active_instrument_symbols,
        LOT_CONFIG,
    )
    
    
    
    
    
    
    st.title("📋 Trade Log")
    st.caption("Signal history, paper trades, and performance tracking")
    
    # ── Filters ────────────────────────────────────────────────
    commodity_filter_options = ["All", *get_active_instrument_symbols()]
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        filter_commodity = st.selectbox(
            "Commodity",
            commodity_filter_options,
        )
    with fc2:
        filter_action = st.selectbox(
            "Action", ["All", "BUY", "SELL", "HOLD"]
        )
    with fc3:
        filter_days = st.selectbox(
            "Period", [7, 14, 30, 60, 90], index=2,
            format_func=lambda x: f"Last {x} days"
        )
    
    # ── Signal History ─────────────────────────────────────────
    st.subheader("Signal History")
    
    def get_signals(commodity, action, days) -> pd.DataFrame:
        try:
            conn   = get_connection()
            query  = """
                SELECT timestamp, commodity, contract, action,
                       confidence, signal_quality, market_regime,
                       entry_price, stop_loss, target_1, rr_ratio,
                       capital_risk_pct, primary_reason,
                       followed, mode, llm_provider
                FROM signals_log
                WHERE mode = ?
                AND timestamp >= datetime('now', ?)
            """
            params = [TRADING_MODE, f"-{days} days"]
    
            if commodity != "All":
                query  += " AND commodity = ?"
                params.append(commodity)
            if action != "All":
                query  += " AND action = ?"
                params.append(action)
    
            query += " ORDER BY timestamp DESC"
            df     = pd.read_sql_query(query, conn, params=params)
            conn.close()
            return df
        except Exception as e:
            st.error(f"DB error: {e}")
            return pd.DataFrame()
    
    df = get_signals(filter_commodity, filter_action, filter_days)
    
    if df.empty:
        st.info("No signals found for the selected filters.")
    else:
        # Colour code action column
        def colour_action(val):
            colours = {
                "BUY":  "background-color: #1a3a1a; color: #4ade80",
                "SELL": "background-color: #3a1a1a; color: #f87171",
                "HOLD": "background-color: #3a3a1a; color: #fbbf24",
            }
            return colours.get(val, "")
    
        display_cols = [
            "timestamp", "commodity", "action", "confidence",
            "signal_quality", "market_regime", "entry_price",
            "stop_loss", "target_1", "rr_ratio", "followed",
        ]
        display_df = df[
            [c for c in display_cols if c in df.columns]
        ].copy()
    
        # Format followed column
        display_df["followed"] = display_df["followed"].map(
            {1: "✅ Yes", 0: "❌ No", None: "⏳ Pending"}
        ).fillna("⏳ Pending")
    
        styled = display_df.style.map(
            colour_action, subset=["action"]
        )
        st.dataframe(styled, width='stretch', height=400)
    
        # Expandable reasoning
        st.subheader("Signal Details")
        for _, row in df.head(5).iterrows():
            with st.expander(
                f"{row['timestamp']}  |  "
                f"{row['commodity']}  |  "
                f"{row['action']}  |  "
                f"{row['confidence']}%"
            ):
                if row.get("primary_reason"):
                    st.write(f"**Reason**: {row['primary_reason']}")
                dc1, dc2, dc3 = st.columns(3)
                with dc1:
                    st.caption(f"Regime: {row.get('market_regime', 'N/A')}")
                with dc2:
                    st.caption(f"Quality: {row.get('signal_quality', 'N/A')}")
                with dc3:
                    st.caption(f"Provider: {row.get('llm_provider', 'N/A')}")
    
    # ── Performance Stats ──────────────────────────────────────
    st.divider()
    st.subheader("Performance Statistics")
    
    if not df.empty:
        total    = len(df)
        buys     = len(df[df["action"] == "BUY"])
        sells    = len(df[df["action"] == "SELL"])
        holds    = len(df[df["action"] == "HOLD"])
        followed = len(df[df["followed"] == 1]) if "followed" in df.columns else 0
        a_grade  = len(df[df["signal_quality"] == "A"]) if "signal_quality" in df.columns else 0
        b_grade  = len(df[df["signal_quality"] == "B"]) if "signal_quality" in df.columns else 0
    
        sc1, sc2, sc3, sc4, sc5 = st.columns(5)
        with sc1:
            st.metric("Total Signals", total)
        with sc2:
            st.metric("BUY / SELL / HOLD", f"{buys} / {sells} / {holds}")
        with sc3:
            follow_rate = round(followed / total * 100) if total > 0 else 0
            st.metric("Follow Rate", f"{follow_rate}%")
        with sc4:
            st.metric("A-Grade Signals", a_grade)
        with sc5:
            avg_conf = round(df["confidence"].mean()) if "confidence" in df.columns else 0
            st.metric("Avg Confidence", f"{avg_conf}%")
    
    # ── Trade Log ──────────────────────────────────────────────
    st.divider()
    mode_label = "Real Trades" if TRADING_MODE == "production" else "Paper Trades"
    st.subheader(mode_label)
    
    def get_trades() -> pd.DataFrame:
        try:
            conn = get_connection()
            df   = pd.read_sql_query("""
                SELECT id, entry_time, exit_time, commodity, action,
                       lots, entry_price, exit_price,
                       stop_loss, target_1, pnl_inr, pnl_pct,
                       exit_reason, order_id, order_status
                FROM trades_log
                WHERE mode = ?
                ORDER BY entry_time DESC
            """, conn, params=[TRADING_MODE])
            conn.close()
            return df
        except Exception:
            return pd.DataFrame()
    
    trades_df = get_trades()
    
    if trades_df.empty:
        if TRADING_MODE == "production":
            st.info("No trades logged yet. Execute a signal from the Signal Engine.")
        else:
            st.info(
                "No paper trades logged yet. "
                "Mark signals as 'Followed' in Signal Engine to log them."
            )
    else:
        display_cols = [
            c for c in [
                "entry_time", "exit_time", "commodity", "action", "lots",
                "entry_price", "exit_price", "stop_loss", "target_1",
                "pnl_inr", "pnl_pct", "exit_reason", "order_status",
            ] if c in trades_df.columns
        ]
        st.dataframe(trades_df[display_cols], width='stretch')
    
        total_pnl = trades_df["pnl_inr"].sum() if "pnl_inr" in trades_df else 0
        tc1, tc2, tc3 = st.columns(3)
        with tc1:
            st.metric(
                "Total P&L",
                f"Rs{total_pnl:,.0f}",
                delta=f"{total_pnl/CAPITAL_INR*100:.2f}%" if CAPITAL_INR else None,
            )
        with tc2:
            wins = len(trades_df[trades_df["pnl_inr"] > 0]) if "pnl_inr" in trades_df else 0
            total_closed = len(trades_df[trades_df["exit_time"].notna()])
            win_rate = round(wins / total_closed * 100) if total_closed > 0 else 0
            st.metric("Win Rate", f"{win_rate}%")
        with tc3:
            st.metric("Total Trades", len(trades_df))
    
    # ── Exit Trade Form ─────────────────────────────────────────
    st.divider()
    st.subheader("Log Trade Exit")
    
    open_trades = trades_df[trades_df["exit_time"].isna()] if not trades_df.empty else pd.DataFrame()
    
    if open_trades.empty:
        st.info("No open trades to close.")
    else:
        trade_options = {
            row["id"]: (
                f"#{row['id']}  {row['commodity']}  {row['action']}  "
                f"{row['lots']} lot(s)  @ Rs{row['entry_price']:,.2f}  "
                f"(SL: Rs{row['stop_loss']:,.2f}  T1: Rs{row['target_1']:,.2f})"
            )
            for _, row in open_trades.iterrows()
        }
    
        selected_id = st.selectbox(
            "Select open trade to close:",
            options=list(trade_options.keys()),
            format_func=lambda x: trade_options[x],
        )
    
        if selected_id:
            sel_row  = open_trades[open_trades["id"] == selected_id].iloc[0]
            lots_val = int(sel_row["lots"])
            entry_px = float(sel_row["entry_price"])
            sl_px    = float(sel_row["stop_loss"]) if sel_row["stop_loss"] else 0.0
            t1_px    = float(sel_row["target_1"])  if sel_row["target_1"]  else 0.0
    
            ec1, ec2 = st.columns(2)
            with ec1:
                exit_price = st.number_input(
                    "Exit Price (Rs)",
                    min_value   = 0.0,
                    value       = t1_px if t1_px else entry_px,
                    step        = 0.5,
                    format      = "%.2f",
                    key         = "exit_px",
                )
            with ec2:
                exit_reason = st.selectbox(
                    "Exit Reason",
                    ["T1_HIT", "T2_HIT", "SL_HIT", "MANUAL", "SESSION_END", "OTHER"],
                    key = "exit_reason",
                )
    
            exit_notes = st.text_input("Notes (optional)", key="exit_notes")
    
            # P&L preview
            action     = sel_row["action"]
            lot_cfg     = LOT_CONFIG.get(sel_row["commodity"], {})
            pl_per_tick = lot_cfg.get("pl_per_tick", 10)
            tick_sz     = lot_cfg.get("tick_size", 1)
    
            if action == "BUY":
                ticks = (exit_price - entry_px) / tick_sz
            else:
                ticks = (entry_px - exit_price) / tick_sz
    
            pnl_inr = ticks * pl_per_tick * lots_val
            pnl_pct = round(pnl_inr / CAPITAL_INR * 100, 3) if CAPITAL_INR else 0
    
            pnl_col = "🟢" if pnl_inr >= 0 else "🔴"
            st.info(
                f"{pnl_col} Estimated P&L: **Rs{pnl_inr:+,.0f}** "
                f"({pnl_pct:+.2f}% of capital)"
            )
    
            if st.button("✅ Log Exit", type="primary", key="log_exit"):
                try:
                    _conn = get_connection()
                    _conn.execute("""
                        UPDATE trades_log
                        SET exit_price  = ?,
                            exit_time   = ?,
                            pnl_inr     = ?,
                            pnl_pct     = ?,
                            exit_reason = ?,
                            notes       = ?,
                            order_status = 'CLOSED'
                        WHERE id = ?
                    """, (
                        exit_price,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        round(pnl_inr, 2),
                        pnl_pct,
                        exit_reason,
                        exit_notes or None,
                        selected_id,
                    ))
                    _conn.commit()
                    _conn.close()
                    st.success(
                        f"Trade #{selected_id} closed.  "
                        f"P&L: Rs{pnl_inr:+,.0f} ({pnl_pct:+.2f}%)"
                    )
                    st.rerun()
                except Exception as _e:
                    st.error(f"Failed to log exit: {_e}")
    
    # ── Live Groww Positions (Production Mode) ─────────────────
    if TRADING_MODE == "production":
        st.divider()
        st.subheader("Live Groww Positions")
    
        if st.button("🔄 Refresh from Groww", key="refresh_positions"):
            st.cache_data.clear()
    
        @st.cache_data(ttl=30)
        def fetch_groww_positions():
            try:
                from generate_token import generate_totp_token, save_token_to_env
                import os as _os
                tok = generate_totp_token()
                save_token_to_env(tok)
                _os.environ["GROWW_ACCESS_TOKEN"] = tok
    
                from core.groww_client import GrowwClient as _GC
                gc   = _GC(access_token=tok)
                return gc.get_live_positions(), None
            except Exception as _e:
                return [], str(_e)
    
        positions, pos_err = fetch_groww_positions()
    
        if pos_err:
            st.warning(f"Could not fetch positions: {pos_err}")
        elif not positions:
            st.info("No open commodity positions on Groww.")
        else:
            pos_df = pd.DataFrame(positions)
            st.dataframe(pos_df, width='stretch')
    
            # Cancel order helper (open orders)
            st.divider()
            st.subheader("Cancel Pending Order")
            cancel_id = st.text_input(
                "Enter Groww Order ID to cancel:",
                key = "cancel_order_id",
            )
            if cancel_id and st.button("Cancel Order", key="cancel_btn"):
                try:
                    from core.groww_client import GrowwClient as _GC3
                    import os as _os3
                    _gc3 = _GC3(access_token=_os3.getenv("GROWW_ACCESS_TOKEN"))
                    res = _gc3.cancel_mcx_order(cancel_id)
                    st.success(f"Cancel response: {res}")
                except Exception as _ce:
                    st.error(f"Cancel failed: {_ce}")

def render_settings():
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


def main():
    selection = render_sidebar()
    if selection == "Home":
        st.title("⬡ COMMODEX")
        st.caption("AI-Assisted MCX Commodity Signal Platform")
        st.divider()
        mode_info = {"demo": ("🟡", "Demo Mode", "OpenAI GPT-4o", "info"), "paper": ("🔵", "Paper Trading", "Claude Sonnet 4.6", "info"), "production": ("🔴", "PRODUCTION", "Claude Sonnet 4.6", "error")}
        icon, label, model, kind = mode_info.get(TRADING_MODE, ("⚪", TRADING_MODE, "Unknown", "info"))
        getattr(st, kind)(f"{icon} **{label}** — {model}")
        st.divider()
        st.info("Home Page - Select a tool from the sidebar to continue.")
    elif selection == "Dashboard":
        render_dashboard()
    elif selection == "Signal Engine":
        render_signal_engine()
    elif selection == "Trade Log":
        render_trade_log()
    elif selection == "Settings":
        render_settings()

if __name__ == "__main__":
    main()
