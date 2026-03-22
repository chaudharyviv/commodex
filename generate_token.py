"""
COMMODEX — Groww TOTP Token Generator
Generates a fresh Groww access token using TOTP authentication.

Run:        python generate_token.py
Usage:      Run this manually or let the app refresh GROWW_ACCESS_TOKEN
            from GROWW_API_KEY + GROWW_TOTP_SECRET when needed.

TOTP secret remains the long-lived credential; access tokens are short-lived
and can be regenerated automatically.
"""

import os
import pyotp
from pathlib import Path
from dotenv import load_dotenv, set_key
from growwapi import GrowwAPI

load_dotenv()

ENV_PATH = Path(".env")


def generate_totp_token() -> str:
    """
    Generate Groww access token using TOTP.
    Exactly follows official Groww SDK documentation.
    Returns access_token string.
    """
    api_key     = os.getenv("GROWW_API_KEY")
    totp_secret = os.getenv("GROWW_TOTP_SECRET")

    if not api_key:
        raise ValueError("GROWW_API_KEY not set in .env")
    if not totp_secret:
        raise ValueError("GROWW_TOTP_SECRET not set in .env")

    # Generate current 6-digit TOTP (valid 30 seconds)
    totp_gen = pyotp.TOTP(totp_secret)
    totp     = totp_gen.now()

    # Get access token — exactly per Groww SDK docs
    access_token = GrowwAPI.get_access_token(
        api_key=api_key,
        totp=totp,
    )
    return access_token


def save_token_to_env(token: str):
    """Write the generated token back to .env file."""
    set_key(str(ENV_PATH), "GROWW_ACCESS_TOKEN", token)


if __name__ == "__main__":
    print("=" * 55)
    print("COMMODEX — Groww TOTP Token Generator")
    print("=" * 55)

    api_key     = os.getenv("GROWW_API_KEY")
    totp_secret = os.getenv("GROWW_TOTP_SECRET")

    # ── Validate inputs ────────────────────────────────────
    if not api_key:
        print("ERROR: GROWW_API_KEY not set in .env")
        exit(1)
    if not totp_secret:
        print("ERROR: GROWW_TOTP_SECRET not set in .env")
        exit(1)

    print(f"API Key     : {api_key[:20]}...{api_key[-6:]}")
    print(f"TOTP Secret : {totp_secret[:6]}...{totp_secret[-4:]}")

    # ── Generate TOTP ──────────────────────────────────────
    try:
        totp_gen  = pyotp.TOTP(totp_secret)
        totp      = totp_gen.now()
        remaining = 30 - (__import__("time").time() % 30)
        print(f"TOTP Code   : {totp}  ({int(remaining)}s remaining)")
    except Exception as e:
        print(f"ERROR generating TOTP: {e}")
        print("Check GROWW_TOTP_SECRET is the correct base32 string")
        exit(1)

    # ── Request access token ───────────────────────────────
    print("\nRequesting access token from Groww...")
    try:
        token = GrowwAPI.get_access_token(
            api_key=api_key,
            totp=totp,
        )

        print("\n" + "=" * 55)
        print("SUCCESS — Access token generated")
        print("=" * 55)
        print(f"Token       : {token[:30]}...{token[-10:]}")

        # Auto-save to .env
        save_token_to_env(token)
        print("\n.env updated — GROWW_ACCESS_TOKEN saved automatically")
        print("\nNext: python test_phase1.py")

    except Exception as e:
        print(f"\nFAILED: {e}")
        print("\nPossible causes:")
        print("  - TOTP code expired (30s window) — run again immediately")
        print("  - GROWW_API_KEY is wrong or truncated in .env")
        print("  - GROWW_TOTP_SECRET is wrong base32 string")
        print("  - Key_TOTP not showing Live on dashboard")
        exit(1)