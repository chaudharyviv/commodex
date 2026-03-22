import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import db
from core.groww_client import GrowwClient


class MockGrowwClient(GrowwClient):
    def __init__(self, positions, orders, statuses):
        self._positions = positions
        self._orders = orders
        self._statuses = statuses

    def get_live_positions(self):
        return self._positions

    def get_mcx_order_book(self):
        return self._orders

    def get_mcx_order_status(self, groww_order_id: str):
        return self._statuses.get(groww_order_id, {})


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    test_db = tmp_path / "commodex-test.db"
    monkeypatch.setattr(db, "DB_PATH", test_db)
    db.init()
    yield test_db


def insert_trade(**overrides):
    payload = {
        "signal_id": None,
        "commodity": "CRUDEOILM",
        "contract": "MCX_CRUDEOILM20APR26FUT",
        "mode": "production",
        "action": "BUY",
        "lots": 1,
        "entry_price": 5000.0,
        "entry_time": "2026-03-22 09:30:00",
        "stop_loss": 4975.0,
        "target_1": 5030.0,
        "target_2": 5050.0,
        "order_id": "ENTRY-1",
        "order_status": "OPEN",
        "exit_order_id": None,
        "notes": None,
    }
    payload.update(overrides)

    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO trades_log (
            signal_id, commodity, contract, mode, action, lots,
            entry_price, entry_time, stop_loss, target_1, target_2,
            order_id, order_status, exit_order_id, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload["signal_id"],
            payload["commodity"],
            payload["contract"],
            payload["mode"],
            payload["action"],
            payload["lots"],
            payload["entry_price"],
            payload["entry_time"],
            payload["stop_loss"],
            payload["target_1"],
            payload["target_2"],
            payload["order_id"],
            payload["order_status"],
            payload["exit_order_id"],
            payload["notes"],
        ),
    )
    trade_id = cur.lastrowid
    conn.commit()
    conn.close()
    return trade_id


def fetch_trade(trade_id: int) -> dict:
    trades = db.get_trades(mode="production")
    return next(trade for trade in trades if trade["id"] == trade_id)


def test_reconcile_partially_filled_entry_updates_local_status(temp_db):
    trade_id = insert_trade(order_id="ENTRY-PARTIAL", lots=3)
    client = MockGrowwClient(
        positions=[
            {
                "trading_symbol": "CRUDEOILM20APR26FUT",
                "net_quantity": 1,
                "average_price": 5001,
            }
        ],
        orders=[{"groww_order_id": "ENTRY-PARTIAL", "status": "partially filled"}],
        statuses={
            "ENTRY-PARTIAL": {
                "groww_order_id": "ENTRY-PARTIAL",
                "status": "partially filled",
                "filled_quantity": 1,
                "average_price": 5001,
            }
        },
    )

    updates = client.reconcile_trades(db.get_trades(mode="production"), capital_inr=100000)
    db.apply_trade_reconciliation(updates)

    trade = fetch_trade(trade_id)
    assert trade["order_status"] == "PARTIALLY_FILLED"
    assert trade["exit_time"] is None
    assert trade["exit_order_id"] is None


def test_reconcile_cancelled_entry_marks_trade_cancelled(temp_db):
    trade_id = insert_trade(order_id="ENTRY-CANCEL")
    client = MockGrowwClient(
        positions=[],
        orders=[{"groww_order_id": "ENTRY-CANCEL", "status": "cancelled"}],
        statuses={
            "ENTRY-CANCEL": {
                "groww_order_id": "ENTRY-CANCEL",
                "status": "cancelled",
                "updated_at": "2026-03-22T10:05:00",
            }
        },
    )

    updates = client.reconcile_trades(db.get_trades(mode="production"), capital_inr=100000)
    db.apply_trade_reconciliation(updates)

    trade = fetch_trade(trade_id)
    assert trade["order_status"] == "CANCELLED"
    assert trade["exit_time"] is None
    assert trade["pnl_inr"] is None


def test_reconcile_filled_exit_closes_trade_and_persists_broker_refs(temp_db):
    trade_id = insert_trade(
        commodity="GOLDM",
        contract="MCX_GOLDM03APR26FUT",
        action="BUY",
        lots=2,
        entry_price=70250.0,
        order_id="ENTRY-CLOSED",
        order_status="OPEN",
        exit_order_id="EXIT-CLOSED",
    )
    client = MockGrowwClient(
        positions=[],
        orders=[
            {"groww_order_id": "ENTRY-CLOSED", "status": "complete", "average_price": 70250},
            {
                "groww_order_id": "EXIT-CLOSED",
                "status": "complete",
                "average_price": 70310,
                "updated_at": "2026-03-22T11:15:00",
            },
        ],
        statuses={
            "ENTRY-CLOSED": {
                "groww_order_id": "ENTRY-CLOSED",
                "status": "complete",
                "average_price": 70250,
            },
            "EXIT-CLOSED": {
                "groww_order_id": "EXIT-CLOSED",
                "status": "complete",
                "average_price": 70310,
                "updated_at": "2026-03-22T11:15:00",
            },
        },
    )

    updates = client.reconcile_trades(db.get_trades(mode="production"), capital_inr=100000)
    db.apply_trade_reconciliation(updates)

    trade = fetch_trade(trade_id)
    assert trade["order_id"] == "ENTRY-CLOSED"
    assert trade["exit_order_id"] == "EXIT-CLOSED"
    assert trade["order_status"] == "CLOSED"
    assert trade["exit_price"] == pytest.approx(70310.0)
    assert trade["exit_time"] == "2026-03-22 11:15:00"
    assert trade["exit_reason"] == "BROKER_EXIT_FILLED"
    assert trade["pnl_inr"] == pytest.approx(1200.0)
    assert trade["pnl_pct"] == pytest.approx(1.2)
