"""Telegram delivery — send alerts via Telegram Bot API."""

from __future__ import annotations

import logging

from inj_sentinel.models.alert import Alert

logger = logging.getLogger(__name__)


class TelegramDelivery:
    """Deliver alerts via Telegram Bot API.

    Requires a bot token (from @BotFather) and a chat ID.
    """

    def __init__(self, bot_token: str, chat_id: str) -> None:
        self.bot_token = bot_token
        self.chat_id = chat_id
        self._bot = None

    async def _get_bot(self):
        """Lazy-initialize the Telegram bot."""
        if self._bot is None:
            try:
                from telegram import Bot

                self._bot = Bot(token=self.bot_token)
            except ImportError:
                logger.error(
                    "python-telegram-bot not installed. "
                    "Install with: pip install python-telegram-bot"
                )
                raise
        return self._bot

    async def send(self, alert: Alert) -> None:
        """Send an alert via Telegram.

        Args:
            alert: The alert to send
        """
        message = self._format_message(alert)

        try:
            bot = await self._get_bot()
            await bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode="HTML",
            )
            logger.info("Telegram alert sent: %s", alert.title)
        except Exception as e:
            logger.error("Failed to send Telegram alert: %s", e)
            raise

    def _format_message(self, alert: Alert) -> str:
        """Format alert for Telegram (HTML parse mode)."""
        parts = [
            "🛡️ <b>INJ Sentinel Alert</b>",
            "",
            f"{alert.severity_emoji} <b>{alert.title}</b>",
            "",
        ]

        # Position details
        if alert.position:
            pos = alert.position
            parts.extend([
                "📊 <b>Position:</b>",
                f"• {pos.direction.value.title()} {pos.leverage}, "
                f"{pos.quantity} ({pos.ticker})",
                f"• Entry: ${float(pos.entry_price):,.2f} → "
                f"Now: ${float(pos.mark_price):,.2f}",
                f"• Liquidation: ${float(pos.liquidation_price):,.2f}",
                "",
                "📉 <b>Risk:</b>",
                f"• Margin: {pos.margin_ratio:.2f}x | "
                f"Distance: {pos.liquidation_distance_pct:.0f}%",
                f"• PnL: ${pos.unrealized_pnl:,.2f} "
                f"({pos.unrealized_pnl_pct:.1f}%)",
                "",
            ])

        # AI message
        if alert.message:
            # Strip any Rich formatting
            clean_msg = alert.message.replace("\n\n", "\n")
            parts.append(clean_msg)

        # Recommendation
        if alert.recommendation:
            parts.extend(["", alert.recommendation])

        # Timestamp
        parts.extend([
            "",
            f"⏰ {alert.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        ])

        return "\n".join(parts)
