from config import get_margin_estimate_inr, get_position_size


def test_margin_estimate_supports_gold_and_crude_contract_math():
    assert get_margin_estimate_inr("GOLDM", 72000) == 59400.0
    assert get_margin_estimate_inr("CRUDEOILM", 6500) == 22262.5


def test_position_size_blocks_underlotted_risk_for_wide_gold_stop():
    result = get_position_size(
        symbol="GOLDM",
        entry_price=71250,
        stop_loss=70850,
        capital=100000,
        risk_pct=2.5,
        signal_quality="A",
    )

    assert result["position_lots"] == 1
    assert result["underlotted"] is True
    assert result["risk_overbudget_ratio"] == 1.6
    assert result["risk_blocked"] is True
    assert "Stop too wide" in result["risk_block_reason"]


def test_position_size_flags_insufficient_margin_before_execution():
    result = get_position_size(
        symbol="CRUDEOILM",
        entry_price=6500,
        stop_loss=6490,
        capital=20000,
        risk_pct=2.5,
        signal_quality="A",
    )

    assert result["position_lots"] == 3
    assert result["margin_sufficient"] is False
    assert result["margin_pct_of_capital"] == 333.9
    assert result["risk_blocked"] is False
    assert "Margin insufficient" in result["risk_block_reason"]


def test_position_size_reduces_b_grade_signals_deterministically():
    a_grade = get_position_size(
        symbol="GOLDM",
        entry_price=71250,
        stop_loss=71200,
        capital=100000,
        risk_pct=2.5,
        signal_quality="A",
    )
    b_grade = get_position_size(
        symbol="GOLDM",
        entry_price=71250,
        stop_loss=71200,
        capital=100000,
        risk_pct=2.5,
        signal_quality="B",
    )

    assert a_grade["raw_lots_calculated"] == 5.0
    assert a_grade["position_lots"] == 3
    assert b_grade["raw_lots_calculated"] == 2.5
    assert b_grade["position_lots"] == 2
    assert b_grade["b_grade_reduced"] is True
