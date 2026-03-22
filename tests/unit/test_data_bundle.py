from core.data_bundle import DataBundleAssembler
from config import CONFIDENCE_CAP_INR_VOLATILE, CONFIDENCE_CAP_NO_NEWS


class FakeGrowwClient:
    def __init__(self, candles):
        self._candles = candles

    def find_active_contract(self, symbol):
        assert symbol == "GOLDM"
        return {"trading_symbol": "GOLDM26APR"}

    def get_ltp(self, symbols):
        assert symbols == ["MCX_GOLDM26APR"]
        return {"MCX_GOLDM26APR": 71892.5}

    def get_oi(self, trading_symbol):
        assert trading_symbol == "GOLDM26APR"
        return {
            "oi_current": 18050,
            "oi_prev_day": 17600,
            "oi_change_pct": 2.56,
            "oi_interpretation": "fresh_longs",
        }

    def get_historical(self, trading_symbol, interval, days):
        assert trading_symbol == "GOLDM26APR"
        assert interval == "15minute"
        assert days == 30
        return self._candles


class FakeNewsClient:
    def fetch(self, symbol):
        assert symbol == "GOLDM"
        return {
            "available": False,
            "summary": "News unavailable in offline test",
            "articles": [],
            "from_cache": False,
        }


def test_assemble_uses_mocked_clients_and_applies_caps(monkeypatch, goldm_candles):
    mocked_inr = {
        "available": True,
        "rate": 83.19,
        "change_pct": 0.61,
        "direction": "up",
        "signal": "volatile",
    }
    monkeypatch.setattr("core.data_bundle.get_inr_usd_rate", lambda: mocked_inr)

    assembler = DataBundleAssembler(
        FakeGrowwClient(goldm_candles),
        tech_engine=__import__("core.technical_engine", fromlist=["TechnicalEngine"]).TechnicalEngine(),
        news_client=FakeNewsClient(),
    )

    bundle = assembler.assemble(symbol="GOLDM", timeframe="15minute", trading_style="system")

    assert bundle.contract == "GOLDM26APR"
    assert bundle.ltp_available is True
    assert bundle.technicals_ok is True
    assert bundle.technicals.candle_count == len(goldm_candles)
    assert bundle.technicals.oi_interpretation == "fresh_longs"
    assert bundle.news_available is False
    assert bundle.inr_usd_rate == mocked_inr["rate"]
    assert bundle.confidence_cap == CONFIDENCE_CAP_INR_VOLATILE
    assert any(str(CONFIDENCE_CAP_NO_NEWS) in reason for reason in bundle.cap_reasons)
    assert any("volatile" in reason.lower() for reason in bundle.cap_reasons)
    assert bundle.data_quality == "partial"
    prompt = bundle.to_prompt_string()
    assert "News: unavailable" in prompt
    assert "fresh_longs" in prompt


def test_assemble_raises_when_no_active_contract(goldm_candles):
    class MissingContractGroww(FakeGrowwClient):
        def find_active_contract(self, symbol):
            return None

    assembler = DataBundleAssembler(
        MissingContractGroww(goldm_candles),
        tech_engine=__import__("core.technical_engine", fromlist=["TechnicalEngine"]).TechnicalEngine(),
        news_client=FakeNewsClient(),
    )

    try:
        assembler.assemble(symbol="GOLDM")
    except ValueError as exc:
        assert "No active MCX contract found" in str(exc)
    else:
        raise AssertionError("Expected assemble() to fail when no contract is available")
