from __future__ import annotations

import pathlib
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from config import (
    ACTIVE_LOT_CONFIG,
    build_exchange_trading_symbol,
    get_active_instrument_symbols,
    get_instrument_label,
    get_position_size,
)
from core.data_bundle import DataBundleAssembler
from core.groww_client import GrowwClient
from core.technical_engine import TechnicalData


def test_active_config_is_user_selection_source():
    symbols = get_active_instrument_symbols()

    assert symbols == list(ACTIVE_LOT_CONFIG.keys())
    assert "SILVERM" in symbols
    assert get_instrument_label("SILVERM").startswith("◇ Silver Mini")



def test_find_active_contract_uses_exchange_abstraction(monkeypatch):
    client = object.__new__(GrowwClient)
    client._instruments_df = None

    instruments = pd.DataFrame(
        [
            {
                "exchange": "MCX",
                "segment": "COMMODITY",
                "instrument_type": "FUT",
                "underlying_symbol": "TESTOIL",
                "trading_symbol": "TESTOILAPR26FUT",
                "expiry_date": "2026-04-20",
            },
            {
                "exchange": "NCDEX",
                "segment": "COMMODITY",
                "instrument_type": "FUT",
                "underlying_symbol": "TESTOIL",
                "trading_symbol": "TESTOIL30APR26FUT",
                "expiry_date": "2026-04-30",
            },
        ]
    )

    monkeypatch.setattr(client, "get_instruments_df", lambda force_refresh=False: instruments)
    monkeypatch.setattr("core.groww_client.get_instrument_exchange", lambda symbol: "NCDEX")

    contract = GrowwClient.find_active_contract(client, "TESTOIL")

    assert contract is not None
    assert contract["exchange"] == "NCDEX"
    assert contract["trading_symbol"] == "TESTOIL30APR26FUT"
    assert build_exchange_trading_symbol(contract["trading_symbol"], exchange=contract["exchange"]) == "NCDEX_TESTOIL30APR26FUT"


class FakeGroww:
    def find_active_contract(self, symbol: str) -> dict:
        assert symbol == "SILVERM"
        return {
            "exchange": "MCX",
            "trading_symbol": "SILVERM30APR26FUT",
            "expiry_date": "2026-04-30",
        }

    def get_ltp(self, exchange_trading_symbols: list[str]) -> dict:
        assert exchange_trading_symbols == ["MCX_SILVERM30APR26FUT"]
        return {"MCX_SILVERM30APR26FUT": 86_250.0}

    def get_quote(self, trading_symbol: str, exchange: str = "MCX") -> dict:
        return {
            "last_price": 86_250.0,
            "ohlc": {"close": 85_900.0},
            "open_interest": 1200,
            "previous_open_interest": 1000,
            "oi_day_change": 200,
        }

    def get_oi(self, trading_symbol: str, exchange: str = "MCX") -> dict:
        assert (trading_symbol, exchange) == ("SILVERM30APR26FUT", "MCX")
        return {
            "oi_current": 1200,
            "oi_prev_day": 1000,
            "oi_change_pct": 20.0,
            "oi_interpretation": "fresh_longs",
        }

    def get_historical(self, trading_symbol: str, exchange: str = "MCX", interval: str = "15minute", days: int = 30) -> list[dict]:
        assert (trading_symbol, exchange, interval, days) == ("SILVERM30APR26FUT", "MCX", "15minute", 5)
        return [
            {
                "timestamp": 1_711_000_000,
                "open": 86_000,
                "high": 86_400,
                "low": 85_900,
                "close": 86_250,
                "volume": 150,
            },
            {
                "timestamp": 1_711_000_900,
                "open": 86_250,
                "high": 86_500,
                "low": 86_200,
                "close": 86_300,
                "volume": 175,
            },
        ]


class FakeTech:
    def compute(self, candles: list[dict], symbol: str, timeframe: str) -> TechnicalData:
        assert symbol == "SILVERM"
        assert timeframe == "15minute"
        assert len(candles) == 2
        return TechnicalData(
            symbol=symbol,
            timeframe=timeframe,
            candle_count=len(candles),
            latest_price=86_300.0,
            latest_time="2026-03-22 10:00:00",
        )


class FakeNews:
    def fetch(self, symbol: str) -> dict:
        assert symbol == "SILVERM"
        return {
            "symbol": symbol,
            "available": True,
            "summary": "Silver news available",
            "articles": [{"headline": "Silver demand rises"}],
        }



def test_new_commodity_flows_through_bundle_and_position_sizing(monkeypatch):
    monkeypatch.setattr(
        "core.data_bundle.get_inr_usd_rate",
        lambda: {
            "available": True,
            "rate": 83.1,
            "change_pct": 0.12,
            "direction": "stable",
            "signal": "stable",
        },
    )

    assembler = DataBundleAssembler(
        groww_client=FakeGroww(),
        tech_engine=FakeTech(),
        news_client=FakeNews(),
    )

    bundle = assembler.assemble("SILVERM", timeframe="15minute", trading_style="system", days=5)
    size = get_position_size("SILVERM", entry_price=86_250.0, stop_loss=85_950.0)

    assert bundle.symbol == "SILVERM"
    assert bundle.contract == "SILVERM30APR26FUT"
    assert bundle.ltp == 86_250.0
    assert bundle.lot_config == ACTIVE_LOT_CONFIG["SILVERM"]
    assert bundle.news_available is True
    assert bundle.technicals_ok is True
    assert bundle.technicals.oi_interpretation == "fresh_longs"
    assert size["symbol"] == "SILVERM"
    assert size["position_lots"] >= 1
    assert size["pl_per_tick"] == ACTIVE_LOT_CONFIG["SILVERM"]["pl_per_tick"]
