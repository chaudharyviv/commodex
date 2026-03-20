"""
COMMODEX — Technical Indicator Engine
Converts raw Groww candles into a full indicator set.

Uses 'ta' library (Windows compatible, Python 3.12 compatible)
instead of pandas-ta which has posix module issues on Windows.

Input:  raw candles from GrowwClient.get_historical()
Output: TechnicalData dataclass ready for Agent 1 prompt
"""

import logging
import pandas as pd
import ta
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────
# OUTPUT DATACLASS
# ─────────────────────────────────────────────────────────────────

@dataclass
class TechnicalData:
    """
    Complete technical indicator set for one commodity contract.
    All float values rounded to 2 decimal places.
    None means insufficient data to compute.
    """
    symbol:          str
    timeframe:       str
    candle_count:    int
    latest_price:    float
    latest_time:     str

    # ── Trend ─────────────────────────────────────
    ema_20:          Optional[float] = None
    ema_50:          Optional[float] = None
    ema_trend:       Optional[str]   = None

    # ── Momentum ──────────────────────────────────
    rsi_14:          Optional[float] = None
    rsi_signal:      Optional[str]   = None

    # ── MACD ──────────────────────────────────────
    macd_line:       Optional[float] = None
    macd_signal:     Optional[float] = None
    macd_histogram:  Optional[float] = None
    macd_cross:      Optional[str]   = None

    # ── Bollinger Bands ───────────────────────────
    bb_upper:        Optional[float] = None
    bb_mid:          Optional[float] = None
    bb_lower:        Optional[float] = None
    bb_position:     Optional[str]   = None
    bb_width:        Optional[float] = None

    # ── Volatility ────────────────────────────────
    atr_14:          Optional[float] = None
    atr_pct:         Optional[float] = None

    # ── Pivot Points ──────────────────────────────
    pivot:           Optional[float] = None
    r1:              Optional[float] = None
    r2:              Optional[float] = None
    s1:              Optional[float] = None
    s2:              Optional[float] = None

    # ── Key Levels ────────────────────────────────
    day_high:        Optional[float] = None
    day_low:         Optional[float] = None
    prev_day_high:   Optional[float] = None
    prev_day_low:    Optional[float] = None
    week_high:       Optional[float] = None
    week_low:        Optional[float] = None

    # ── Volume ────────────────────────────────────
    volume_current:  Optional[int]   = None
    volume_avg_20:   Optional[float] = None
    volume_signal:   Optional[str]   = None

    def to_prompt_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}

    def summary_string(self) -> str:
        """Compact summary for Agent 1 prompt injection."""
        lines = [
            f"Symbol: {self.symbol} | Timeframe: {self.timeframe} | "
            f"Price: Rs{self.latest_price:,.2f} | "
            f"Candles: {self.candle_count} | Time: {self.latest_time}",
        ]
        if self.rsi_14 is not None:
            lines.append(
                f"RSI(14)   : {self.rsi_14} [{self.rsi_signal}]"
            )
        if self.macd_line is not None:
            lines.append(
                f"MACD      : line={self.macd_line}  "
                f"signal={self.macd_signal}  "
                f"hist={self.macd_histogram}  [{self.macd_cross}]"
            )
        if self.ema_20 and self.ema_50:
            lines.append(
                f"EMA       : 20={self.ema_20:,.0f}  "
                f"50={self.ema_50:,.0f}  [{self.ema_trend}]"
            )
        if self.bb_upper:
            lines.append(
                f"BB        : upper={self.bb_upper:,.0f}  "
                f"mid={self.bb_mid:,.0f}  "
                f"lower={self.bb_lower:,.0f}  "
                f"[{self.bb_position}]  width={self.bb_width}%"
            )
        if self.atr_14:
            lines.append(
                f"ATR(14)   : {self.atr_14:,.0f}  ({self.atr_pct}% of price)"
            )
        if self.pivot:
            lines.append(
                f"Pivots    : P={self.pivot:,.0f}  "
                f"R1={self.r1:,.0f}  R2={self.r2:,.0f}  "
                f"S1={self.s1:,.0f}  S2={self.s2:,.0f}"
            )
        if self.day_high and self.day_low:
            lines.append(
                f"Day range : H={self.day_high:,.0f}  L={self.day_low:,.0f}  "
                f"| PDH={self.prev_day_high:,.0f}  PDL={self.prev_day_low:,.0f}"
            )
        if self.volume_signal:
            lines.append(
                f"Volume    : {self.volume_current:,}  "
                f"(avg20={self.volume_avg_20:,.0f})  [{self.volume_signal}]"
            )
        return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────
# ENGINE
# ─────────────────────────────────────────────────────────────────

class TechnicalEngine:
    """
    Computes all technical indicators from raw candle data.
    Stateless — call compute() with fresh candles each time.
    Uses 'ta' library — Windows and Python 3.12 compatible.
    """

    def candles_to_df(self, candles: list[dict]) -> pd.DataFrame:
        """
        Convert raw candle list to clean pandas DataFrame.
        Handles both dict format and raw list format from Groww.
        """
        if not candles:
            raise ValueError("Empty candles list")

        rows = []
        for c in candles:
            if isinstance(c, dict):
                rows.append({
                    "timestamp": c.get("timestamp"),
                    "open":      float(c.get("open",  0)),
                    "high":      float(c.get("high",  0)),
                    "low":       float(c.get("low",   0)),
                    "close":     float(c.get("close", 0)),
                    "volume":    int(c.get("volume",  0)),
                })
            elif isinstance(c, (list, tuple)) and len(c) >= 5:
                rows.append({
                    "timestamp": c[0],
                    "open":      float(c[1]),
                    "high":      float(c[2]),
                    "low":       float(c[3]),
                    "close":     float(c[4]),
                    "volume":    int(c[5]) if len(c) > 5 else 0,
                })

        df = pd.DataFrame(rows)

        # Convert timestamp to datetime
        sample_ts = df["timestamp"].iloc[0]
        if sample_ts > 1e12:
            df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms")
        else:
            df["datetime"] = pd.to_datetime(df["timestamp"], unit="s")

        df = df.set_index("datetime").sort_index()
        df = df[["open", "high", "low", "close", "volume"]]
        df = df[df["close"] > 0]

        logger.info(
            f"DataFrame: {len(df)} candles | "
            f"{df.index[0]} to {df.index[-1]}"
        )
        return df

    def compute(
        self,
        candles: list[dict],
        symbol: str = "UNKNOWN",
        timeframe: str = "15minute",
    ) -> TechnicalData:
        """
        Compute full indicator set from raw candles.
        Each indicator block is independent — one failure
        does not block others.
        """
        df = self.candles_to_df(candles)
        latest       = df.iloc[-1]
        latest_price = round(float(latest["close"]), 2)
        latest_time  = str(df.index[-1])

        result = TechnicalData(
            symbol       = symbol,
            timeframe    = timeframe,
            candle_count = len(df),
            latest_price = latest_price,
            latest_time  = latest_time,
        )

        # ── EMA ───────────────────────────────────────────
        try:
            ema20 = round(float(
                ta.trend.EMAIndicator(df["close"], window=20)
                .ema_indicator().iloc[-1]
            ), 2)
            ema50 = round(float(
                ta.trend.EMAIndicator(df["close"], window=50)
                .ema_indicator().iloc[-1]
            ), 2)
            result.ema_20 = ema20
            result.ema_50 = ema50

            if latest_price > ema20 > ema50:
                result.ema_trend = "above_both_bullish"
            elif latest_price < ema20 < ema50:
                result.ema_trend = "below_both_bearish"
            elif ema20 > ema50:
                result.ema_trend = "above_ema50_bullish"
            else:
                result.ema_trend = "below_ema50_bearish"
        except Exception as e:
            logger.warning(f"EMA failed: {e}")

        # ── RSI ───────────────────────────────────────────
        try:
            rsi_val = round(float(
                ta.momentum.RSIIndicator(df["close"], window=14)
                .rsi().iloc[-1]
            ), 2)
            result.rsi_14 = rsi_val

            if rsi_val >= 70:
                result.rsi_signal = "overbought"
            elif rsi_val <= 30:
                result.rsi_signal = "oversold"
            elif rsi_val >= 55:
                result.rsi_signal = "bullish_neutral"
            elif rsi_val <= 45:
                result.rsi_signal = "bearish_neutral"
            else:
                result.rsi_signal = "neutral"
        except Exception as e:
            logger.warning(f"RSI failed: {e}")

        # ── MACD ──────────────────────────────────────────
        try:
            macd_ind = ta.trend.MACD(
                df["close"], window_fast=12, window_slow=26, window_sign=9
            )
            macd_line = round(float(macd_ind.macd().iloc[-1]),          2)
            macd_sig  = round(float(macd_ind.macd_signal().iloc[-1]),   2)
            macd_hist = round(float(macd_ind.macd_diff().iloc[-1]),     2)
            prev_hist = float(macd_ind.macd_diff().iloc[-2])

            result.macd_line      = macd_line
            result.macd_signal    = macd_sig
            result.macd_histogram = macd_hist

            if macd_hist > 0 and prev_hist <= 0:
                result.macd_cross = "bullish_crossover"
            elif macd_hist < 0 and prev_hist >= 0:
                result.macd_cross = "bearish_crossover"
            elif macd_hist > 0:
                result.macd_cross = "bullish"
            else:
                result.macd_cross = "bearish"
        except Exception as e:
            logger.warning(f"MACD failed: {e}")

        # ── Bollinger Bands ───────────────────────────────
        try:
            bb_ind = ta.volatility.BollingerBands(
                df["close"], window=20, window_dev=2
            )
            bb_upper = round(float(bb_ind.bollinger_hband().iloc[-1]), 2)
            bb_mid   = round(float(bb_ind.bollinger_mavg().iloc[-1]),  2)
            bb_lower = round(float(bb_ind.bollinger_lband().iloc[-1]), 2)

            result.bb_upper = bb_upper
            result.bb_mid   = bb_mid
            result.bb_lower = bb_lower
            result.bb_width = round(
                (bb_upper - bb_lower) / bb_mid * 100, 2
            ) if bb_mid else None

            if latest_price > bb_upper:
                result.bb_position = "above_upper_overbought"
            elif latest_price > bb_mid:
                result.bb_position = "upper_half_bullish"
            elif latest_price > bb_lower:
                result.bb_position = "lower_half_bearish"
            else:
                result.bb_position = "below_lower_oversold"
        except Exception as e:
            logger.warning(f"Bollinger Bands failed: {e}")

        # ── ATR ───────────────────────────────────────────
        try:
            atr_val = round(float(
                ta.volatility.AverageTrueRange(
                    df["high"], df["low"], df["close"], window=14
                ).average_true_range().iloc[-1]
            ), 2)
            result.atr_14  = atr_val
            result.atr_pct = round(
                atr_val / latest_price * 100, 3
            ) if latest_price else None
        except Exception as e:
            logger.warning(f"ATR failed: {e}")

        # ── Pivot Points (Classic) ────────────────────────
        try:
            daily = df["close"].resample("D").ohlc()
            if len(daily) >= 2:
                prev  = daily.iloc[-2]
                h     = float(prev["high"])
                l     = float(prev["low"])
                c     = float(prev["close"])
                pivot = round((h + l + c) / 3, 2)
                result.pivot = pivot
                result.r1    = round(2 * pivot - l, 2)
                result.r2    = round(pivot + (h - l), 2)
                result.s1    = round(2 * pivot - h, 2)
                result.s2    = round(pivot - (h - l), 2)
        except Exception as e:
            logger.warning(f"Pivot Points failed: {e}")

        # ── Key Levels ────────────────────────────────────

        try:
            today    = df.index[-1].date()
            today_df = df[df.index.date == today]
            if not today_df.empty:
                result.day_high = round(float(today_df["high"].max()), 2)
                result.day_low  = round(float(today_df["low"].min()),  2)

            unique_dates = sorted(set(df.index.date.tolist()))
            if len(unique_dates) >= 2:
                prev_date = unique_dates[-2]
                prev_df   = df[df.index.date == prev_date]
                result.prev_day_high = round(float(prev_df["high"].max()), 2)
                result.prev_day_low  = round(float(prev_df["low"].min()),  2)

            week_start = df.index[-1] - pd.Timedelta(days=7)
            week_df    = df[df.index >= week_start]
            result.week_high = round(float(week_df["high"].max()), 2)
            result.week_low  = round(float(week_df["low"].min()),  2)
        except Exception as e:
            logger.warning(f"Key levels failed: {e}")
# ── Volume ────────────────────────────────────────
        try:
            vol_current      = int(latest["volume"])
            vol_avg          = round(
                float(df["volume"].tail(20).mean()), 0
            )
            result.volume_current = vol_current
            result.volume_avg_20  = vol_avg

            ratio = vol_current / vol_avg if vol_avg > 0 else 1
            if ratio >= 1.5:
                result.volume_signal = "high"
            elif ratio <= 0.5:
                result.volume_signal = "low"
            else:
                result.volume_signal = "normal"
        except Exception as e:
            logger.warning(f"Volume failed: {e}")

        logger.info(
            f"Indicators computed: {symbol} | "
            f"RSI={result.rsi_14} | "
            f"MACD={result.macd_cross} | "
            f"ATR={result.atr_14}"
        )
        return result