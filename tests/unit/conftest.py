import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.data_bundle import DataBundle
from core.technical_engine import TechnicalEngine

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def _load_candles(name: str):
    return json.loads((FIXTURES_DIR / f"{name}_candles.json").read_text())


@pytest.fixture(scope="session")
def goldm_candles():
    return _load_candles("goldm")


@pytest.fixture(scope="session")
def crudeoilm_candles():
    return _load_candles("crudeoilm")


@pytest.fixture(scope="session")
def technical_engine():
    return TechnicalEngine()


@pytest.fixture(scope="session")
def goldm_technicals(goldm_candles, technical_engine):
    return technical_engine.compute(goldm_candles, symbol="GOLDM", timeframe="15minute")


@pytest.fixture(scope="session")
def crudeoilm_technicals(crudeoilm_candles, technical_engine):
    return technical_engine.compute(crudeoilm_candles, symbol="CRUDEOILM", timeframe="15minute")


@pytest.fixture
def offline_bundle(goldm_technicals):
    bundle = DataBundle(
        symbol="GOLDM",
        contract="GOLDM26APR",
        timeframe="15minute",
        trading_style="system",
        ltp=goldm_technicals.latest_price,
        ltp_available=True,
        technicals=goldm_technicals,
        technicals_ok=True,
        news={"available": False, "summary": "News unavailable"},
        news_available=False,
        inr_usd={
            "available": True,
            "rate": 83.21,
            "change_pct": 0.62,
            "direction": "up",
            "signal": "volatile",
        },
        inr_usd_rate=83.21,
        lot_config={"friendly_name": "Gold Mini (100g)"},
    )
    bundle.apply_confidence_caps()
    return bundle
