"""
COMMODEX — Groww SDK Method Inspector
Prints all available methods and key method signatures
Run: python inspect_sdk.py
"""

import os
import inspect
from dotenv import load_dotenv
from growwapi import GrowwAPI

load_dotenv()

token = os.getenv("GROWW_ACCESS_TOKEN")
groww = GrowwAPI(token)

# ── All Methods ────────────────────────────────────────────
print("=" * 55)
print("GrowwAPI — All Available Methods")
print("=" * 55)
methods = [m for m in dir(groww) if not m.startswith("__")]
for m in sorted(methods):
    print(f"  {m}")
print(f"\nTotal: {len(methods)} attributes/methods")

# ── Key Method Signatures ──────────────────────────────────
print("\n" + "=" * 55)
print("Key Method Signatures")
print("=" * 55)

for method_name in [
    "get_ltp",
    "get_historical_candles",
    "get_historical_candle_data",
    "get_quote",
    "get_ohlc",
    "get_user_profile",
]:
    try:
        method = getattr(groww, method_name)
        sig    = inspect.signature(method)
        print(f"\n  {method_name}{sig}")
    except AttributeError:
        print(f"\n  {method_name} — NOT FOUND")
    except Exception as e:
        print(f"\n  {method_name} — ERROR: {e}")

# ── Auth Test ──────────────────────────────────────────────
print("\n" + "=" * 55)
print("Auth Test — get_user_profile()")
print("=" * 55)
try:
    profile = groww.get_user_profile()
    print(f"  OK — {profile}")
except Exception as e:
    print(f"  FAIL — {e}")

print("\n" + "=" * 55)