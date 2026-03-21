"""
COMMODEX — Signal Notifier
Sends trading signals to Telegram for mobile alerts.
Free, instant, personal use.
"""

import logging
import requests
import os
from datetime import datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


class TelegramNotifier:
    """
    Sends signal alerts to your Telegram.
    Personal use — one bot, one chat.
    """

    def __init__(self):
        self._token   = os.getenv("TELEGRAM_BOT_TOKEN")
        self._chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self._enabled = bool(self._token and self._chat_id)

        if not self._enabled:
            logger.warning(
                "Telegram not configured — "
                "set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env"
            )

    def send_signal(self, result) -> bool:
        """
        Send a signal result as a Telegram message.
        Accepts SignalResult from orchestrator.
        Only sends for BUY/SELL — not HOLD.
        Returns True if sent successfully.
        """
        if not self._enabled:
            return False

        if result.final_action == "HOLD":
            return False   # don't spam HOLD notifications

        now = datetime.now(IST).strftime("%d %b %Y %H:%M IST")

        # Build message
        action_icon = "🟢 BUY" if result.final_action == "BUY" else "🔴 SELL"
        quality_icon = {
            "A": "⭐⭐⭐",
            "B": "⭐⭐",
            "C": "⭐",
        }.get(result.signal.signal_quality if result.signal else "C", "⭐")

        lines = [
            f"⬡ *COMMODEX SIGNAL*",
            f"",
            f"*{action_icon}* — {result.symbol}",
            f"Confidence: *{result.final_confidence}%* {quality_icon}",
            f"Time: {now}",
            f"",
            f"📊 *Market*",
            f"Regime: {result.analysis.market_regime if result.analysis else 'N/A'}",
            f"Sentiment: {result.analysis.overall_sentiment if result.analysis else 'N/A'}",
            f"",
        ]

        if result.signal:
            lines += [
                f"💡 *Reason*",
                f"{result.signal.primary_reason}",
                f"",
            ]

        if result.risk and result.approved:
            lines += [
                f"🎯 *Trade Parameters*",
                f"Entry:     Rs{result.risk.entry_price:,.0f}",
                f"Stop Loss: Rs{result.risk.stop_loss:,.0f}",
                f"Target 1:  Rs{result.risk.target_1:,.0f}",
                f"Target 2:  Rs{result.risk.target_2:,.0f}",
                f"R:R Ratio: {result.risk.risk_reward_ratio:.1f}:1",
            ]

        if result.position_sizing:
            ps = result.position_sizing
            lines += [
                f"",
                f"📐 *Position*",
                f"Lots: {ps.get('position_lots')}",
                f"Capital at risk: Rs{ps.get('actual_risk_inr'):,.0f} "
                f"({ps.get('actual_risk_pct')}%)",
            ]

        if result.sanity_warnings:
            lines += [
                f"",
                f"⚠️ *Warnings*",
            ]
            for w in result.sanity_warnings[:2]:  # max 2 warnings
                lines.append(f"• {w[:80]}...")

        lines += [
            f"",
            f"_Paper trading mode — advisory only_",
            f"_Review full analysis in COMMODEX app_",
        ]

        message = "\n".join(lines)
        return self._send(message)

    def send_daily_summary(
        self,
        date:             str,
        signals_count:    int,
        followed_count:   int,
        buy_count:        int,
        sell_count:       int,
        hold_count:       int,
        daily_pnl:        float = 0.0,
    ) -> bool:
        """Send end-of-day summary at market close."""
        if not self._enabled:
            return False

        message = (
            f"⬡ *COMMODEX Daily Summary*\n"
            f"📅 {date}\n\n"
            f"Signals generated: {signals_count}\n"
            f"Followed: {followed_count}\n"
            f"BUY: {buy_count} | SELL: {sell_count} | HOLD: {hold_count}\n"
            f"Paper P&L: Rs{daily_pnl:,.0f}\n\n"
            f"_MCX session closed_"
        )
        return self._send(message)

    def send_guardrail_alert(self, symbol: str, reason: str) -> bool:
        """Alert when a guardrail blocks a signal."""
        if not self._enabled:
            return False
        message = (
            f"🚫 *COMMODEX Guardrail Alert*\n"
            f"Symbol: {symbol}\n"
            f"Blocked: {reason}"
        )
        return self._send(message)

    def send_test(self) -> bool:
        """Test connectivity — send a test message."""
        return self._send(
            "✅ *COMMODEX Notifier Test*\n"
            "Telegram alerts are working correctly.\n"
            "You will receive BUY/SELL signals here."
        )

    def _send(self, message: str) -> bool:
        """Send message via Telegram Bot API."""
        try:
            url  = f"https://api.telegram.org/bot{self._token}/sendMessage"
            data = {
                "chat_id":    self._chat_id,
                "text":       message,
                "parse_mode": "Markdown",
            }
            resp = requests.post(url, data=data, timeout=10)
            resp.raise_for_status()
            logger.info("Telegram notification sent")
            return True
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False