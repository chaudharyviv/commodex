from core.data_bundle import DataBundle
from core.llm_client import MarketAnalysis, RiskParameters, SignalDecision
import core.orchestrator as orchestrator_module
from core.orchestrator import SignalOrchestrator


class DummyGrowwClient:
    pass


class DummyNewsClient:
    pass


class DummyTechnicalEngine:
    pass


class DummyLLMClient:
    pass


class DummyNotifier:
    def __init__(self):
        self.sent = []

    def send_signal(self, result):
        self.sent.append(result)
        return True


class DummyAssembler:
    def __init__(self, groww, tech, news):
        self.dependencies = (groww, tech, news)
        self.bundle = None
        self.exc = None

    def assemble(self, **kwargs):
        if self.exc:
            raise self.exc
        return self.bundle


class DummyAnalystAgent:
    def __init__(self, llm):
        self.analysis = None
        self.exc = None

    def analyse(self, bundle):
        if self.exc:
            raise self.exc
        return self.analysis


class DummySanityChecker:
    def __init__(self):
        self.result = {"passed": True, "warnings": [], "confidence_cap": None}

    def check(self, analysis, bundle):
        return self.result


class DummySignalAgent:
    def __init__(self, llm):
        self.signal = None
        self.exc = None

    def generate(self, bundle, analysis, sanity, trading_style):
        if self.exc:
            raise self.exc
        return self.signal


class DummyRiskAgent:
    def __init__(self, llm):
        self.result = None
        self.exc = None

    def assess(self, bundle, analysis, signal):
        if self.exc:
            raise self.exc
        return self.result


def _make_bundle(goldm_technicals):
    bundle = DataBundle(
        symbol="GOLDM",
        contract="GOLDM26APR",
        timeframe="15minute",
        trading_style="system",
        ltp=goldm_technicals.latest_price,
        ltp_available=True,
        technicals=goldm_technicals,
        technicals_ok=True,
        news={"available": False, "summary": "offline"},
        news_available=False,
        inr_usd={"available": True, "rate": 83.15, "change_pct": 0.1, "direction": "flat", "signal": "stable"},
        inr_usd_rate=83.15,
        lot_config={"friendly_name": "Gold Mini (100g)"},
    )
    bundle.apply_confidence_caps()
    return bundle


def _patch_orchestrator_dependencies(monkeypatch):
    monkeypatch.setattr(orchestrator_module, "LLMClient", DummyLLMClient)
    monkeypatch.setattr(orchestrator_module, "GrowwClient", DummyGrowwClient)
    monkeypatch.setattr(orchestrator_module, "TechnicalEngine", DummyTechnicalEngine)
    monkeypatch.setattr(orchestrator_module, "NewsClient", DummyNewsClient)
    monkeypatch.setattr(orchestrator_module, "DataBundleAssembler", DummyAssembler)
    monkeypatch.setattr(orchestrator_module, "AnalystAgent", DummyAnalystAgent)
    monkeypatch.setattr(orchestrator_module, "SanityChecker", DummySanityChecker)
    monkeypatch.setattr(orchestrator_module, "SignalAgent", DummySignalAgent)
    monkeypatch.setattr(orchestrator_module, "RiskAgent", DummyRiskAgent)
    monkeypatch.setitem(__import__("sys").modules, "core.notifier", type("NotifierModule", (), {"TelegramNotifier": DummyNotifier}))


def test_generate_runs_full_pipeline_without_network(monkeypatch, goldm_technicals):
    _patch_orchestrator_dependencies(monkeypatch)
    orchestrator = SignalOrchestrator()
    orchestrator._assembler.bundle = _make_bundle(goldm_technicals)
    orchestrator._analyst.analysis = MarketAnalysis(
        market_regime="trending_up",
        trend_strength="strong",
        key_support_levels=[71200.0, 71120.0],
        key_resistance_levels=[71420.0, 71510.0],
        technical_summary="Trend remains constructive.",
        india_specific_factors="INR stable.",
        global_risk_factors="COMEX supportive.",
        high_impact_events_next_24h=None,
        overall_sentiment="bullish",
        sentiment_confidence=74,
        analyst_notes="Offline test analysis.",
    )
    orchestrator._signal.signal = SignalDecision(
        action="BUY",
        confidence=76,
        primary_reason="Breakout above resistance",
        supporting_factors=["EMA trend bullish", "VWAP support"],
        contradicting_factors=["No fresh news"],
        invalidation_condition="Falls below 71200",
        recommended_timeframe="intraday",
        signal_quality="A",
        hold_reasoning=None,
    )
    risk_params = RiskParameters(
        entry_price=71320.0,
        entry_type="market",
        stop_loss=71280.0,
        stop_loss_basis="ATR",
        target_1=71420.0,
        target_2=71520.0,
        risk_reward_ratio=2.5,
        max_hold_duration="same session",
        exit_conditions=["Stop hit", "Target reached"],
        margin_required_approx=59400.0,
        execution_notes="Offline test execution.",
        risk_approved=True,
        risk_block_reason=None,
    )
    orchestrator._risk.result = {
        "risk_params": risk_params,
        "position_sizing": {"position_lots": 2, "actual_risk_inr": 800.0},
        "final_approved": True,
        "block_reason": None,
    }

    result = orchestrator.generate(symbol="GOLDM", timeframe="15minute", trading_style="system")

    assert result.final_action == "BUY"
    assert result.approved is True
    assert result.pipeline_stage == "complete"
    assert result.position_sizing["position_lots"] == 2
    assert len(orchestrator._notifier.sent) == 1


def test_generate_returns_hold_when_signal_confidence_is_too_low(monkeypatch, goldm_technicals):
    _patch_orchestrator_dependencies(monkeypatch)
    orchestrator = SignalOrchestrator()
    orchestrator._assembler.bundle = _make_bundle(goldm_technicals)
    orchestrator._analyst.analysis = MarketAnalysis(
        market_regime="ranging",
        trend_strength="weak",
        key_support_levels=[71150.0, 71080.0],
        key_resistance_levels=[71380.0, 71410.0],
        technical_summary="No clear edge.",
        india_specific_factors="Offline.",
        global_risk_factors="Offline.",
        high_impact_events_next_24h=None,
        overall_sentiment="neutral",
        sentiment_confidence=58,
        analyst_notes="Confidence gate test.",
    )
    orchestrator._signal.signal = SignalDecision(
        action="BUY",
        confidence=40,
        primary_reason="Weak setup",
        supporting_factors=["Range support"],
        contradicting_factors=["Low confidence"],
        invalidation_condition="Breaks lower",
        recommended_timeframe="intraday",
        signal_quality="C",
        hold_reasoning=None,
    )

    result = orchestrator.generate(symbol="GOLDM")

    assert result.final_action == "HOLD"
    assert result.block_reason.startswith("Confidence 40% below")
    assert result.pipeline_stage == "signal_complete"


def test_generate_defaults_to_hold_when_data_assembly_fails(monkeypatch):
    _patch_orchestrator_dependencies(monkeypatch)
    orchestrator = SignalOrchestrator()
    orchestrator._assembler.exc = RuntimeError("offline data failure")

    result = orchestrator.generate(symbol="GOLDM")

    assert result.final_action == "HOLD"
    assert result.pipeline_stage == "data_failed"
    assert result.block_reason == "Data unavailable — defaulting to HOLD"
    assert "offline data failure" in result.error
