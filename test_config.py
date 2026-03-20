"""
COMMODEX — Phase 1 Config Validation Test
Run: python test_config.py
"""

from config import (
    validate_config,
    get_position_size,
    get_margin_estimate_inr,
    ACTIVE_COMMODITIES,
    ACTIVE_LOT_CONFIG,
    TRADING_MODE,
)

print("=" * 50)
print("COMMODEX Phase 1 — Config Validation")
print("=" * 50)

# Config warnings
print("\n=== Config Warnings ===")
warnings = validate_config()
if warnings:
    for w in warnings:
        print(f"  > {w}")
else:
    print("  No warnings — all config present")

# Trading mode
print(f"\n=== Trading Mode ===")
print(f"  Mode: {TRADING_MODE}")

# Active contracts
print("\n=== Active Contracts ===")
for k, v in ACTIVE_LOT_CONFIG.items():
    print(f"  {k}: {v['friendly_name']}")
    print(f"       tick=Rs{v['tick_size']} | pl/tick=Rs{v['pl_per_tick']} | margin={v['margin_pct']}%")

# Position sizing - GOLDM
print("\n=== Position Size: GOLDM ===")
print("  Scenario: entry=71450, stop=71435, capital=1,00,000, risk=2.5%")
result = get_position_size("GOLDM", entry_price=71450, stop_loss=71435)
for k, v in result.items():
    print(f"  {k}: {v}")

# Position sizing - CRUDEOILM
print("\n=== Position Size: CRUDEOILM ===")
print("  Scenario: entry=6500, stop=6450, capital=1,00,000, risk=2.5%")
result = get_position_size("CRUDEOILM", entry_price=6500, stop_loss=6450)
for k, v in result.items():
    print(f"  {k}: {v}")

# Margin estimates
print("\n=== Margin Estimates (1 lot) ===")
goldm_margin = get_margin_estimate_inr("GOLDM", 71450)
crude_margin = get_margin_estimate_inr("CRUDEOILM", 6500)
print(f"  GOLDM at Rs71,450    -> Rs{goldm_margin:,.0f} per lot")
print(f"  CRUDEOILM at Rs6,500 -> Rs{crude_margin:,.0f} per lot")
print(f"  Total for 1 lot each -> Rs{goldm_margin + crude_margin:,.0f}")

print("\n" + "=" * 50)
print("Config validation complete")
print("=" * 50)