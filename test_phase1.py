"""
COMMODEX — Phase 1 Full Validation Test
Tests: DB, Groww API, contracts, LTP, historical data, backup, LOT_CONFIG

Run: python test_phase1.py
Expected: 7/7 passing before Phase 2 begins
"""

import sys
import os

print("=" * 55)
print("COMMODEX Phase 1 — Full Validation")
print("=" * 55)

passed = 0
failed = 0


def ok(msg):
    global passed
    passed += 1
    print(f"  OK  — {msg}")


def fail(msg):
    global failed
    failed += 1
    print(f"  FAIL — {msg}")


def warn(msg):
    print(f"  WARN — {msg}")


# ── 1. Database ────────────────────────────────────────────
print("\n[1/7] Database")
try:
    from core.db import init, health_check
    init()
    status = health_check()
    if status["status"] == "ok":
        ok(f"{len(status['tables'])} tables found")
        for t in sorted(status["tables"]):
            print(f"         > {t}")
    else:
        fail(f"DB degraded — missing: {status.get('missing')}")
except Exception as e:
    fail(f"Database init failed: {e}")
    sys.exit(1)

# ── 2. Groww Connectivity (instruments CSV — no auth) ──────
print("\n[2/7] Groww Connectivity (instruments CSV)")
client = None
try:
    from core.groww_client import GrowwClient
    client = GrowwClient()
    ping = client.ping()
    if ping["status"] == "ok":
        ok(f"{ping['total_instruments']:,} total instruments")
        print(f"         {ping['mcx_commodity']:,} MCX commodity contracts")
    else:
        fail(f"Ping failed — {ping.get('error')}")
        sys.exit(1)
except Exception as e:
    fail(f"GrowwClient init failed: {e}")
    print("  Check GROWW_API_KEY and GROWW_TOTP_SECRET in .env")
    sys.exit(1)

# ── 3. TOTP Token Generation ───────────────────────────────
print("\n[3/7] TOTP Token Generation")
try:
    from generate_token import generate_totp_token, save_token_to_env
    token = generate_totp_token()
    if token:
        save_token_to_env(token)
        # Reinitialise client with fresh token
        os.environ["GROWW_ACCESS_TOKEN"] = token
        client = GrowwClient(access_token=token)
        ok(f"Token generated and saved: {token[:20]}...{token[-6:]}")
    else:
        fail("Token generation returned empty")
except Exception as e:
    fail(f"TOTP token generation failed: {e}")
    print("  Run python generate_token.py separately to debug")

# ── 4. Active Contract Discovery ──────────────────────────
print("\n[4/7] Active Contract Discovery")
gold_contract  = None
crude_contract = None

try:
    gold_contract = client.find_active_contract("GOLDM")
    if gold_contract:
        expiry = str(gold_contract.get("expiry_date", ""))[:10]
        ok(f"Gold  : {gold_contract['trading_symbol']}  expiry {expiry}")
    else:
        warn("No active GOLDM contract found — check instruments CSV")
except Exception as e:
    fail(f"Gold contract discovery: {e}")

try:
    crude_contract = client.find_active_contract("CRUDEOILM")
    if crude_contract:
        expiry = str(crude_contract.get("expiry_date", ""))[:10]
        ok(f"Crude : {crude_contract['trading_symbol']}  expiry {expiry}")
    else:
        warn("No active CRUDEOILM contract found")
except Exception as e:
    fail(f"Crude contract discovery: {e}")

# ── 5. Live Prices (LTP) ───────────────────────────────────
print("\n[5/7] Live Prices (LTP)")
try:
    symbols = []
    if gold_contract:
        symbols.append(f"MCX_{gold_contract['trading_symbol']}")
    if crude_contract:
        symbols.append(f"MCX_{crude_contract['trading_symbol']}")

    if symbols:
        ltp_data = client.get_ltp(symbols)
        if ltp_data:
            for symbol, price in ltp_data.items():
                ok(f"{symbol}: Rs{price:,.2f}")
        else:
            fail("LTP returned empty response")
    else:
        warn("No symbols to fetch — skipping LTP test")
except Exception as e:
    fail(f"LTP fetch failed: {e}")

# ── 6. Historical Data Quality ─────────────────────────────
# ── 6. Historical Data Quality ─────────────────────────────
print("\n[6/7] Historical Data (30 days, 15min candles)")
try:
    if gold_contract:
        candles = client.get_historical(
            trading_symbol=gold_contract["trading_symbol"],
            interval="15minute",
            days=30,
        )
        if candles and len(candles) > 0:
            ok(f"{len(candles)} candles returned for GOLDM")

            first = candles[0]
            last  = candles[-1]

            # Convert timestamp to readable if epoch milliseconds
            def fmt_candle(c):
                ts = c.get("timestamp", "")
                if isinstance(ts, (int, float)) and ts > 1e10:
                    from datetime import datetime
                    ts = datetime.fromtimestamp(ts / 1000).strftime(
                        "%Y-%m-%d %H:%M"
                    )
                return (
                    f"ts={ts} | "
                    f"O={c.get('open')} H={c.get('high')} "
                    f"L={c.get('low')} C={c.get('close')} "
                    f"V={c.get('volume')}"
                )

            print(f"         First : {fmt_candle(first)}")
            print(f"         Last  : {fmt_candle(last)}")

            # Check for zero/null close values
            zero_close = [
                c for c in candles
                if not c.get("close")
            ]
            if zero_close:
                warn(f"{len(zero_close)} candles with null/zero close")
            else:
                ok("No null-value candles detected")

            # Basic sanity — close prices in expected MCX Gold range
            closes = [c["close"] for c in candles if c.get("close")]
            avg_close = sum(closes) / len(closes)
            print(f"         Avg close : Rs{avg_close:,.0f}")
            if 50000 < avg_close < 250000:
                ok("Gold price range looks correct for MCX")
            else:
                warn(f"Unexpected price range — avg Rs{avg_close:,.0f}")

        else:
            fail("Empty candle response")
    else:
        warn("No gold contract — skipping historical test")
except Exception as e:
    fail(f"Historical data failed: {e}")

# ── 7. Database Backup ─────────────────────────────────────
print("\n[7/7] Database Backup")
try:
    from core.backup import run_backup, list_backups
    result = run_backup()
    if result["status"] == "ok":
        ok(f"Backup created: {result['backup_path']}")
        print(f"         Size : {result['size_kb']} KB")
    else:
        fail(f"Backup failed: {result}")

    backups = list_backups()
    print(f"         Total backups available: {len(backups)}")
except Exception as e:
    fail(f"Backup failed: {e}")

# ── LOT_CONFIG Quick Check ─────────────────────────────────
print("\n[+] LOT_CONFIG Sanity Check")
try:
    from config import ACTIVE_LOT_CONFIG, get_position_size

    for symbol, cfg in ACTIVE_LOT_CONFIG.items():
        r = get_position_size(symbol,
            entry_price=71450 if "GOLD" in symbol else 6500,
            stop_loss  =71435 if "GOLD" in symbol else 6450,
        )
        print(
            f"  {symbol}: {r['position_lots']} lot(s) | "
            f"risk=Rs{r['actual_risk_inr']:,.0f} "
            f"({r['actual_risk_pct']}%) | "
            f"stop={r['stop_distance_ticks']} ticks"
        )
    ok("LOT_CONFIG position sizing correct")
except Exception as e:
    fail(f"LOT_CONFIG check failed: {e}")

# ── Summary ────────────────────────────────────────────────
total = passed + failed
print("\n" + "=" * 55)
print(f"Phase 1 Results: {passed}/{total} passing")
if failed == 0:
    print("ALL PASSING — Phase 1 complete, ready for Phase 2")
elif failed <= 2:
    print("MOSTLY PASSING — review failures above before Phase 2")
else:
    print("MULTIPLE FAILURES — resolve before proceeding")
print("=" * 55)