"""Discord delivery — send alerts via Discord webhooks."""

from __future__ import annotations

import json
import logging

import aiohttp

from sentrix.models.alert import Alert
from sentrix.models.position import AlertSeverity

logger = logging.getLogger(__name__)

# Severity to Discord embed color (decimal)
SEVERITY_COLORS = {
    AlertSeverity.LOW: 3447003,     # Blue
    AlertSeverity.MEDIUM: 16776960,  # Yellow
    AlertSeverity.HIGH: 15105570,    # Orange
    AlertSeverity.CRITICAL: 15548997,  # Red
}


class DiscordDelivery:
    """Deliver alerts via Discord webhook embeds."""

    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    async def send(self, alert: Alert) -> None:
        """Send an alert as a Discord webhook embed.

        Args:
            alert: The alert to send
        """
        embed = self._build_embed(alert)
        payload = {
            "username": "Sentrix",
            "avatar_url": "https://injective.com/favicon.ico",
            "embeds": [embed],
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    data=json.dumps(payload),
                    headers={"Content-Type": "application/json"},
                ) as resp:
                    if resp.status not in (200, 204):
                        body = await resp.text()
                        logger.error("Discord webhook failed (%d): %s", resp.status, body)
                    else:
                        logger.info("Discord alert sent: %s", alert.title)
        except Exception as e:
            logger.error("Failed to send Discord alert: %s", e)
            raise

    def _build_embed(self, alert: Alert) -> dict:
        """Build a Discord embed object from an alert."""
        color = SEVERITY_COLORS.get(alert.severity, 3447003)

        embed: dict = {
            "title": f"{alert.severity_emoji} {alert.title}",
            "color": color,
            "timestamp": alert.created_at.isoformat(),
            "footer": {"text": "Sentrix v0.1.0"},
        }

        fields = []

        if alert.position:
            pos = alert.position
            fields.extend([
                {
                    "name": "📊 Position",
                    "value": (
                        f"{pos.direction.value.title()} {pos.leverage}\n"
                        f"{pos.quantity} {pos.ticker}"
                    ),
                    "inline": True,
                },
                {
                    "name": "📉 Risk",
                    "value": (
                        f"Margin: {pos.margin_ratio:.2f}x\n"
                        f"Liq dist: {pos.liquidation_distance_pct:.0f}%"
                    ),
                    "inline": True,
                },
                {
                    "name": "💰 PnL",
                    "value": (
                        f"${pos.unrealized_pnl:,.2f}\n"
                        f"({pos.unrealized_pnl_pct:.1f}%)"
                    ),
                    "inline": True,
                },
            ])

        if alert.recommendation:
            fields.append({
                "name": "💡 Action",
                "value": alert.recommendation[:1024],
                "inline": False,
            })

        if fields:
            embed["fields"] = fields

        # Description from AI message
        if alert.message:
            embed["description"] = alert.message[:4096]

        return embed
