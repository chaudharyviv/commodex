"""
COMMODEX — Groww API Client (SDK-based)
Uses official growwapi Python SDK instead of raw HTTP calls.
Auth: access token generated from GROWW_API_KEY + Groww TOTP when needed.

Version: 1.1 — replaced hand-rolled HTTP client with growwapi SDK
"""

import os
import logging
import pandas as pd
import pyotp
from datetime import datetime, timedelta
from typing import Any, Optional
from growwapi import GrowwAPI

from config import (
    GROWW_TOTP_SECRET,
    EXCHANGE_CONFIG,
    get_instrument_exchange,
)

logger = logging.getLogger(__name__)


def _clean_string(value: Any) -> str:
    return str(value or "").strip()


def _normalise_order_status(value: Any) -> str:
    raw = _clean_string(value).upper().replace("-", "_").replace(" ", "_")
    mapping = {
        "OPEN": "OPEN",
        "ORDER_OPEN": "OPEN",
        "TRIGGER_PENDING": "OPEN",
        "PENDING": "OPEN",
        "PUT_ORDER_REQ_RECEIVED": "OPEN",
        "COMPLETE": "FILLED",
        "COMPLETED": "FILLED",
        "EXECUTED": "FILLED",
        "FILLED": "FILLED",
        "PARTIALLY_FILLED": "PARTIALLY_FILLED",
        "PARTIAL": "PARTIALLY_FILLED",
        "PARTIALLY_EXECUTED": "PARTIALLY_FILLED",
        "CANCELLED": "CANCELLED",
        "CANCELED": "CANCELLED",
        "REJECTED": "REJECTED",
        "FAILED": "REJECTED",
        "CLOSED": "CLOSED",
        "EXIT_PENDING": "EXIT_PENDING",
        "MANUAL": "MANUAL",
        "MANUAL_OFF_PLATFORM": "MANUAL_OFF_PLATFORM",
    }
    return mapping.get(raw, raw or "UNKNOWN")


def _as_float(*values: Any) -> Optional[float]:
    for value in values:
        if value in (None, "", "null"):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _as_int(*values: Any) -> Optional[int]:
    for value in values:
        if value in (None, "", "null"):
            continue
        try:
            return int(float(value))
        except (TypeError, ValueError):
            continue
    return None


def _parse_timestamp(*values: Any) -> Optional[str]:
    for value in values:
        if not value:
            continue
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        cleaned = str(value).replace("T", " ").replace("Z", "").strip()
        for fmt in (
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ):
            try:
                return datetime.strptime(cleaned, fmt).strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
        return cleaned
    return None


def _extract_order_id(payload: dict) -> Optional[str]:
    if not isinstance(payload, dict):
        return None
    for key in ("groww_order_id", "order_id", "id"):
        value = payload.get(key)
        if value:
            return str(value)
    return None


def _extract_trading_symbol(payload: dict) -> str:
    if not isinstance(payload, dict):
        return ""
    return _clean_string(
        payload.get("trading_symbol")
        or payload.get("symbol")
        or payload.get("tradingsymbol")
        or payload.get("exchange_trading_symbol")
    ).upper().removeprefix("MCX_")


def _extract_order_avg_price(payload: dict) -> Optional[float]:
    return _as_float(
        payload.get("average_price"),
        payload.get("avg_price"),
        payload.get("filled_price"),
        payload.get("price"),
    )


def _extract_order_filled_qty(payload: dict) -> Optional[int]:
    return _as_int(
        payload.get("filled_quantity"),
        payload.get("filled_qty"),
        payload.get("executed_quantity"),
        payload.get("quantity_filled"),
        payload.get("quantity"),
    )


def _extract_position_quantity(payload: dict) -> int:
    qty = _as_int(
        payload.get("net_quantity"),
        payload.get("net_qty"),
        payload.get("quantity"),
        payload.get("qty"),
    )
    return qty or 0


def _extract_position_price(payload: dict) -> Optional[float]:
    return _as_float(
        payload.get("average_price"),
        payload.get("avg_price"),
        payload.get("net_price"),
        payload.get("ltp"),
        payload.get("last_price"),
    )


def _pnl_for_trade(commodity: str, action: str, lots: int, entry_price: float, exit_price: float) -> float:
    lot_cfg = LOT_CONFIG.get(commodity or "", {})
    tick_size = float(lot_cfg.get("tick_size", 1) or 1)
    pl_per_tick = float(lot_cfg.get("pl_per_tick", 0) or 0)
    if str(action).upper() == "BUY":
        ticks = (exit_price - entry_price) / tick_size
    else:
        ticks = (entry_price - exit_price) / tick_size
    return round(ticks * pl_per_tick * int(lots or 0), 2)



# ─────────────────────────────────────────────────────────────────
# TOKEN GENERATION HELPER
# Generate an access token from the Groww API key and TOTP secret, then
# optionally cache it in .env as GROWW_ACCESS_TOKEN.
# ─────────────────────────────────────────────────────────────────

def generate_access_token(
    api_key: str,
    secret: str = None,
    totp_secret: str = None,
) -> str:
    """
    Generate a Groww access token.

    Use one of:
      generate_access_token(api_key, secret=your_secret)
      generate_access_token(api_key, totp_secret=your_totp_secret)

    Store the returned token in .env as GROWW_ACCESS_TOKEN.
    """
    if secret:
        token = GrowwAPI.get_access_token(api_key=api_key, secret=secret)
    elif totp_secret:
        totp = pyotp.TOTP(totp_secret).now()
        token = GrowwAPI.get_access_token(api_key=api_key, totp=totp)
    else:
        raise ValueError("Provide either secret or totp_secret")

    logger.info("Access token generated successfully")
    return token


# ─────────────────────────────────────────────────────────────────
# MAIN CLIENT
# ─────────────────────────────────────────────────────────────────

class GrowwClient:
    """
    COMMODEX wrapper around the official growwapi SDK.
    Focused on Indian commodity operations needed by the signal pipeline.
    """

    def __init__(self, access_token: str = None):
        """
        Initialise with access token.
        Falls back to GROWW_ACCESS_TOKEN env var if not provided.
        """
        token = access_token or os.getenv("GROWW_ACCESS_TOKEN")
        if not token:
            raise ValueError(
                "No Groww access token found. "
                "Set GROWW_ACCESS_TOKEN in .env or pass access_token directly."
            )
        self._groww = GrowwAPI(token)
        self._instruments_df: Optional[pd.DataFrame] = None
        logger.info("GrowwClient initialised via SDK")

    # ── Instruments ────────────────────────────────────────────────

    def get_instruments_df(self, force_refresh: bool = False) -> pd.DataFrame:
        """
        Load full instruments DataFrame from Groww CSV.
        Cached in memory for the session.
        """
        if self._instruments_df is not None and not force_refresh:
            return self._instruments_df
        self._instruments_df = self._groww.get_all_instruments()
        logger.info(f"Loaded {len(self._instruments_df)} instruments")
        return self._instruments_df

    def get_futures_for_exchange(self, exchange: str) -> pd.DataFrame:
        """Return futures contracts for a configured commodity exchange."""
        df = self.get_instruments_df()
        venue = (exchange or "MCX").upper()
        segment = EXCHANGE_CONFIG.get(venue, {}).get("segment", "COMMODITY")
        return df[
            (df["exchange"] == venue) &
            (df["segment"] == segment) &
            (df["instrument_type"] == "FUT")
        ].copy()

    def get_mcx_futures(self) -> pd.DataFrame:
        """Backward-compatible helper for MCX futures contracts."""
        return self.get_futures_for_exchange("MCX")

    def find_active_contract(self, base_symbol: str) -> Optional[dict]:
        """
        Find the nearest non-expired commodity futures contract
        for a configured base symbol e.g. GOLDM, CRUDEOILM, SILVERM.
        Returns dict of instrument details or None.
        """
        try:
            exchange = get_instrument_exchange(base_symbol)
            exchange_futures = self.get_futures_for_exchange(exchange)
            today = pd.Timestamp.today().normalize()

            # Filter by underlying symbol
            candidates = exchange_futures[
                exchange_futures["underlying_symbol"].fillna("").str.upper() == base_symbol.upper()
            ].copy()

            if candidates.empty:
                # Try trading_symbol contains base_symbol
                candidates = exchange_futures[
                    exchange_futures["trading_symbol"].fillna("").str.upper().str.startswith(
                        base_symbol.upper()
                    )
                ].copy()

            if candidates.empty:
                logger.warning(f"No contracts found for {base_symbol}")
                return None

            # Filter non-expired
            candidates["expiry_date"] = pd.to_datetime(
                candidates["expiry_date"], errors="coerce"
            )
            candidates = candidates[candidates["expiry_date"] >= today]

            if candidates.empty:
                logger.warning(f"All {base_symbol} contracts have expired")
                return None

            # Return nearest expiry
            candidates = candidates.sort_values("expiry_date")
            contract = candidates.iloc[0].to_dict()
            logger.info(
                f"Active contract for {base_symbol}: "
                f"{contract.get('trading_symbol')} "
                f"expiry {contract.get('expiry_date')} "
                f"on {exchange}"
            )
            return contract

        except Exception as e:
            logger.error(f"find_active_contract({base_symbol}) failed: {e}")
            return None

    # ── Live Data ──────────────────────────────────────────────────

    def get_ltp(self, exchange_trading_symbols: list[str]) -> dict:
        """
        Get Last Traded Price for MCX commodity instruments.

        exchange_trading_symbols: list like
          ["MCX_GOLDM03APR26FUT", "MCX_CRUDEOILM20APR26FUT"]

        Returns dict: { "MCX_GOLDM03APR26FUT": 71450.0, ... }
        """
        try:
            if len(exchange_trading_symbols) == 1:
                result = self._groww.get_ltp(
                    segment=self._groww.SEGMENT_COMMODITY,
                    exchange_trading_symbols=exchange_trading_symbols[0],
                )
            else:
                result = self._groww.get_ltp(
                    segment=self._groww.SEGMENT_COMMODITY,
                    exchange_trading_symbols=tuple(exchange_trading_symbols),
                )
            logger.info(f"LTP fetched for {exchange_trading_symbols}")
            return result
        except Exception as e:
            logger.error(f"get_ltp failed: {e}")
            raise

    def get_quote(self, trading_symbol: str, exchange: str = "MCX") -> dict:
        """
        Get full market quote for a commodity instrument.
        Returns OHLC, depth, volume, OI, circuit limits.
        """
        try:
            result = self._groww.get_quote(
                exchange=exchange,
                segment=self._groww.SEGMENT_COMMODITY,
                trading_symbol=trading_symbol,
            )
            return result
        except Exception as e:
            logger.error(f"get_quote({trading_symbol}) failed: {e}")
            raise

    def get_oi(self, trading_symbol: str, exchange: str = "MCX") -> dict:
        """
        Fetch Open Interest data for a commodity futures contract.
        Uses get_quote() which returns open_interest, oi_day_change,
        previous_open_interest from the Groww API.

        OI Interpretation Matrix:
          Price UP   + OI UP   = fresh_longs    (bullish, strong)
          Price DOWN + OI UP   = fresh_shorts   (bearish, strong)
          Price UP   + OI DOWN = short_covering (bullish, weak)
          Price DOWN + OI DOWN = long_unwinding (bearish, weak)
          OI change < ±2%     = neutral

        Returns dict with oi values and interpretation,
        or empty dict if fetch fails.
        """
        try:
            quote = self.get_quote(trading_symbol, exchange=exchange)

            if not quote:
                return {}

            oi_current  = int(quote.get("open_interest",          0) or 0)
            oi_prev     = int(quote.get("previous_open_interest",  0) or 0)
            oi_change   = float(quote.get("oi_day_change",         0) or 0)
            ltp         = float(quote.get("last_price",            0) or 0)

            # OI change as percentage
            oi_change_pct = round(
                (oi_change / oi_prev * 100) if oi_prev > 0 else 0, 2
            )

            # Price direction — compare LTP to previous close
            ohlc      = quote.get("ohlc", {})
            prev_close = float(ohlc.get("close", ltp) or ltp) if isinstance(ohlc, dict) else ltp
            price_up   = ltp >= prev_close

            # Interpretation matrix
            if abs(oi_change_pct) < 2.0:
                interpretation = "neutral"
            elif oi_change_pct > 0 and price_up:
                interpretation = "fresh_longs"       # strong bullish
            elif oi_change_pct > 0 and not price_up:
                interpretation = "fresh_shorts"      # strong bearish
            elif oi_change_pct < 0 and price_up:
                interpretation = "short_covering"    # weak bullish
            else:
                interpretation = "long_unwinding"    # weak bearish

            result = {
                "oi_current":        oi_current,
                "oi_prev_day":       oi_prev,
                "oi_change":         int(oi_change),
                "oi_change_pct":     oi_change_pct,
                "oi_interpretation": interpretation,
                "price_direction":   "up" if price_up else "down",
            }

            logger.info(
                f"OI: {trading_symbol} | "
                f"OI={oi_current:,} ({oi_change_pct:+.1f}%) | "
                f"{interpretation}"
            )
            return result

        except Exception as e:
            logger.warning(f"get_oi({trading_symbol}) failed: {e}")
            return {}

    # ── Historical Data ────────────────────────────────────────────

    def get_historical(
        self,
        trading_symbol: str,
        exchange: str = "MCX",
        interval: str = "15minute",
        days: int = 30,
    ) -> list[dict]:
        """
        Fetch historical OHLCV candles for an MCX contract.

        Uses SDK: get_historical_candle_data(
            trading_symbol, exchange, segment,
            start_time, end_time, interval_in_minutes
        )

        start_time / end_time format: "yyyy-MM-dd HH:mm:ss"
        interval_in_minutes: integer (1, 5, 10, 15, 30, 60, 240, 1440)
        """

        # Map string interval to integer minutes
        interval_map = {
            "1minute":  1,
            "2minute":  2,
            "3minute":  3,
            "5minute":  5,
            "10minute": 10,
            "15minute": 15,
            "30minute": 30,
            "1hour":    60,
            "4hour":    240,
            "1day":     1440,
        }
        interval_minutes = interval_map.get(interval, 15)

        end_dt   = datetime.today()
        start_dt = end_dt - timedelta(days=days)

        # SDK requires "yyyy-MM-dd HH:mm:ss" format
        start_time = start_dt.strftime("%Y-%m-%d %H:%M:%S")
        end_time   = end_dt.strftime("%Y-%m-%d %H:%M:%S")

        try:
            result = self._groww.get_historical_candle_data(
                trading_symbol=trading_symbol,
                exchange=exchange,
                segment=self._groww.SEGMENT_COMMODITY,
                start_time=start_time,
                end_time=end_time,
                interval_in_minutes=interval_minutes,
            )

            # Normalise to list of dicts
            if isinstance(result, pd.DataFrame):
                raw = result.to_dict("records")
            elif isinstance(result, dict):
                raw = result.get("candles", result.get("data", []))
            elif isinstance(result, list):
                raw = result
            else:
                raw = []

            # Convert raw list format [ts, open, high, low, close, vol]
            # to named dict format for consistent downstream use
            candles = []
            for c in raw:
                if isinstance(c, (list, tuple)) and len(c) >= 5:
                    candles.append({
                        "timestamp": c[0],
                        "open":      c[1],
                        "high":      c[2],
                        "low":       c[3],
                        "close":     c[4],
                        "volume":    c[5] if len(c) > 5 else 0,
                    })
                elif isinstance(c, dict):
                    candles.append(c)

            logger.info(
                f"Historical: {len(candles)} candles | "
                f"{trading_symbol} | {interval} | {days}d"
            )
            return candles

        except Exception as e:
            logger.error(f"get_historical({trading_symbol}) failed: {e}")
            raise
    # ── Portfolio & Margin ─────────────────────────────────────────

    def get_positions(self) -> list[dict]:
        """Fetch current open positions."""
        try:
            result = self._groww.get_positions()
            if isinstance(result, pd.DataFrame):
                return result.to_dict("records")
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error(f"get_positions failed: {e}")
            return []

    def get_margin(self) -> dict:
        """Fetch available margin from Groww account."""
        try:
            return self._groww.get_margin()
        except Exception as e:
            logger.error(f"get_margin failed: {e}")
            return {}

    # ── Order Execution (Production Only) ──────────────────────────

    def place_commodity_order(
        self,
        trading_symbol:   str,
        transaction_type: str,
        lots:             int,
        exchange:         str   = "MCX",
        order_type:       str   = "MARKET",
        price:            float = 0.0,
        reference_id:     str   = None,
    ) -> dict:
        """
        Place a commodity NRML order.

        trading_symbol:   e.g. "GOLDM03APR26FUT"
        transaction_type: "BUY" or "SELL"
        lots:             number of lots
        order_type:       "MARKET" or "LIMIT"
        price:            limit price (ignored for MARKET orders)

        Returns dict with groww_order_id and status.
        Only callable when TRADING_MODE == "production".
        """
        from config import TRADING_MODE
        if TRADING_MODE != "production":
            raise RuntimeError(
                f"Order placement blocked in '{TRADING_MODE}' mode. "
                "Switch to production mode in Settings first."
            )

        sdk_order_type = (
            self._groww.ORDER_TYPE_LIMIT
            if order_type.upper() == "LIMIT"
            else self._groww.ORDER_TYPE_MARKET
        )
        sdk_txn_type = (
            self._groww.TRANSACTION_TYPE_BUY
            if transaction_type.upper() == "BUY"
            else self._groww.TRANSACTION_TYPE_SELL
        )

        result = self._groww.place_order(
            validity           = self._groww.VALIDITY_DAY,
            exchange           = exchange,
            order_type         = sdk_order_type,
            product            = self._groww.PRODUCT_NRML,
            quantity           = lots,
            segment            = self._groww.SEGMENT_COMMODITY,
            trading_symbol     = trading_symbol,
            transaction_type   = sdk_txn_type,
            price              = price if order_type.upper() == "LIMIT" else 0.0,
            order_reference_id = reference_id,
        )
        logger.info(
            f"{exchange} order placed: {transaction_type} {lots} lots "
            f"{trading_symbol} [{order_type}] → {result}"
        )
        return result

    def place_mcx_exit_order(
        self,
        trading_symbol: str,
        entry_action: str,
        lots: int,
        order_type: str = "MARKET",
        price: float = 0.0,
        reference_id: str = None,
    ) -> dict:
        """Place the opposite-side MCX order required to exit an open position."""
        exit_side = "SELL" if _clean_string(entry_action).upper() == "BUY" else "BUY"
        return self.place_mcx_order(
            trading_symbol   = trading_symbol,
            transaction_type = exit_side,
            lots             = lots,
            order_type       = order_type,
            price            = price,
            reference_id     = reference_id,
        )

    def place_mcx_order(
        self,
        trading_symbol:   str,
        transaction_type: str,
        lots:             int,
        order_type:       str   = "MARKET",
        price:            float = 0.0,
        reference_id:     str   = None,
    ) -> dict:
        """Backward-compatible wrapper for MCX commodity orders."""
        return self.place_commodity_order(
            trading_symbol=trading_symbol,
            transaction_type=transaction_type,
            lots=lots,
            exchange="MCX",
            order_type=order_type,
            price=price,
            reference_id=reference_id,
        )

    def cancel_mcx_order(self, groww_order_id: str) -> dict:
        """Cancel an open MCX order. Production mode only."""
        from config import TRADING_MODE
        if TRADING_MODE != "production":
            raise RuntimeError("Order cancellation only allowed in production mode")
        result = self._groww.cancel_order(
            groww_order_id = groww_order_id,
            segment        = self._groww.SEGMENT_COMMODITY,
        )
        logger.info(f"MCX order cancelled: {groww_order_id} → {result}")
        return result

    def get_mcx_order_status(self, groww_order_id: str) -> dict:
        """Get status of a specific MCX order."""
        try:
            return self._groww.get_order_status(
                segment        = self._groww.SEGMENT_COMMODITY,
                groww_order_id = groww_order_id,
            )
        except Exception as e:
            logger.error(f"get_mcx_order_status({groww_order_id}) failed: {e}")
            return {}

    def get_mcx_order_book(self) -> list[dict]:
        """Get all today's MCX orders."""
        try:
            result = self._groww.get_order_list()
            if isinstance(result, pd.DataFrame):
                return result.to_dict("records")
            if isinstance(result, dict):
                return result.get("orders", result.get("data", []))
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error(f"get_mcx_order_book failed: {e}")
            return []

    def get_mcx_order_snapshot(
        self,
        groww_order_id: str,
        order_book: Optional[list[dict]] = None,
    ) -> dict:
        """Merge order-book and direct status payloads into one normalized snapshot."""
        order_book = order_book or []
        order_book_item = next(
            (item for item in order_book if _extract_order_id(item) == str(groww_order_id)),
            {},
        )
        status_payload = self.get_mcx_order_status(groww_order_id) or {}
        merged = {**order_book_item, **status_payload}
        merged["groww_order_id"] = groww_order_id
        merged["normalised_status"] = _normalise_order_status(
            merged.get("order_status")
            or merged.get("status")
            or merged.get("state")
        )
        merged["filled_quantity"] = _extract_order_filled_qty(merged)
        merged["average_price"] = _extract_order_avg_price(merged)
        merged["trading_symbol"] = _extract_trading_symbol(merged)
        merged["updated_at"] = _parse_timestamp(
            merged.get("updated_at"),
            merged.get("exchange_timestamp"),
            merged.get("order_timestamp"),
            merged.get("timestamp"),
        )
        return merged

    def get_margin_available(self) -> dict:
        """
        Get available commodity margin from Groww account.
        Returns dict with available_margin and other fields.
        """
        try:
            return self._groww.get_available_margin_details()
        except Exception as e:
            logger.error(f"get_margin_available failed: {e}")
            return {}

    def get_live_positions(self) -> list[dict]:
        """Get current open MCX positions with live MTM P&L."""
        try:
            result = self._groww.get_positions_for_user(
                segment = self._groww.SEGMENT_COMMODITY,
            )
            if isinstance(result, pd.DataFrame):
                return result.to_dict("records")
            if isinstance(result, dict):
                return result.get("positions", result.get("data", []))
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error(f"get_live_positions failed: {e}")
            return []

    def _find_matching_position(self, trade: dict, live_positions: list[dict]) -> Optional[dict]:
        trade_contract = _clean_string(trade.get("contract")).upper().removeprefix("MCX_")
        trade_commodity = _clean_string(trade.get("commodity")).upper()
        for position in live_positions:
            pos_symbol = _extract_trading_symbol(position)
            pos_qty = abs(_extract_position_quantity(position))
            if pos_qty <= 0:
                continue
            if trade_contract and pos_symbol == trade_contract:
                return position
            if trade_commodity and pos_symbol.startswith(trade_commodity):
                return position
        return None

    def reconcile_trade(self, trade: dict, live_positions: list[dict], order_book: list[dict]) -> dict:
        """Return a DB-ready update dict for a single local trade using broker state."""
        update = {"id": trade["id"]}
        entry_snapshot = {}
        exit_snapshot = {}

        if trade.get("order_id"):
            entry_snapshot = self.get_mcx_order_snapshot(str(trade["order_id"]), order_book)
            update["order_status"] = entry_snapshot.get("normalised_status") or trade.get("order_status") or "UNKNOWN"

        matching_position = self._find_matching_position(trade, live_positions)
        if matching_position:
            pos_qty = abs(_extract_position_quantity(matching_position))
            lots = int(trade.get("lots") or 0)
            if pos_qty and lots and pos_qty < lots:
                update["order_status"] = "PARTIALLY_FILLED"
            elif pos_qty:
                update["order_status"] = "OPEN"

        if trade.get("exit_order_id"):
            exit_snapshot = self.get_mcx_order_snapshot(str(trade["exit_order_id"]), order_book)
            exit_status = exit_snapshot.get("normalised_status")
            update["order_status"] = (
                "EXIT_PENDING" if exit_status in {"OPEN", "PARTIALLY_FILLED"}
                else exit_status or update.get("order_status")
            )

            if exit_status == "FILLED":
                exit_price = _extract_order_avg_price(exit_snapshot)
                if exit_price is not None:
                    pnl_inr = _pnl_for_trade(
                        trade.get("commodity"),
                        trade.get("action"),
                        int(trade.get("lots") or 0),
                        float(trade.get("entry_price") or 0),
                        float(exit_price),
                    )
                    update.update({
                        "exit_price": round(float(exit_price), 2),
                        "exit_time": exit_snapshot.get("updated_at") or _parse_timestamp(datetime.now()),
                        "exit_reason": trade.get("exit_reason") or "BROKER_EXIT_FILLED",
                        "pnl_inr": pnl_inr,
                        "pnl_pct": round((pnl_inr / trade.get("capital_base", 1)) * 100, 3) if trade.get("capital_base") else trade.get("pnl_pct"),
                        "order_status": "CLOSED",
                    })
                else:
                    update["order_status"] = "EXIT_FILLED_PENDING_PRICE"
            elif exit_status in {"CANCELLED", "REJECTED"}:
                update["order_status"] = exit_status

        elif not matching_position and update.get("order_status") == "FILLED" and not trade.get("exit_time"):
            update["order_status"] = "ENTRY_FILLED_NO_LIVE_POSITION"

        if trade.get("exit_time") and trade.get("order_status") == "MANUAL_OFF_PLATFORM":
            update["order_status"] = "MANUAL_OFF_PLATFORM"

        return update

    def reconcile_trades(self, trades: list[dict], capital_inr: Optional[float] = None) -> list[dict]:
        """Reconcile local trades against live positions plus Groww order state."""
        live_positions = self.get_live_positions()
        order_book = self.get_mcx_order_book()
        updates = []
        for raw_trade in trades:
            trade = dict(raw_trade)
            if capital_inr and not trade.get("capital_base"):
                trade["capital_base"] = capital_inr
            updates.append(self.reconcile_trade(trade, live_positions, order_book))
        return updates

    # ── Health Check ───────────────────────────────────────────────

    def ping(self) -> dict:
        """
        Test connectivity and auth.
        Loads instruments CSV — confirms token is valid.
        """
        try:
            df = self.get_instruments_df()
            mcx_count = len(df[df["exchange"] == "MCX"])
            commodity_count = len(
                df[
                    (df["exchange"] == "MCX") &
                    (df["segment"] == "COMMODITY")
                ]
            )
            return {
                "status":            "ok",
                "total_instruments": len(df),
                "mcx_total":         mcx_count,
                "mcx_commodity":     commodity_count,
                "timestamp":         datetime.now().isoformat(),
            }
        except Exception as e:
            return {
                "status":    "error",
                "error":     str(e),
                "timestamp": datetime.now().isoformat(),
            }
