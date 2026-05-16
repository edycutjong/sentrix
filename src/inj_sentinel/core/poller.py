"""Async position poller — the main monitoring loop."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from inj_sentinel.clients.injective import InjectiveClient
from inj_sentinel.clients.llm import LLMClient
from inj_sentinel.config import SentinelConfig
from inj_sentinel.core.analyzer import RiskAnalyzer
from inj_sentinel.core.detector import RiskDetector
from inj_sentinel.delivery.console import ConsoleDelivery
from inj_sentinel.delivery.discord import DiscordDelivery
from inj_sentinel.delivery.telegram import TelegramDelivery
from inj_sentinel.models.alert import Alert, AlertRule
from inj_sentinel.models.position import DeliveryChannel

logger = logging.getLogger(__name__)


class Poller:
    """Main monitoring loop that polls positions and dispatches alerts.

    Flow: Poll → Detect → Analyze → Deliver
    """

    def __init__(self, config: SentinelConfig) -> None:
        self.config = config
        self.injective = InjectiveClient(
            network=config.network,
            demo=config.demo,
        )
        self.llm = LLMClient(
            provider=config.llm.provider,
            model=config.llm.model,
            api_key=config.llm.api_key,
        )
        # Convert config rules to AlertRule models
        rules = [
            AlertRule(
                alert_type=r.alert_type,
                threshold=r.threshold,
                enabled=r.enabled,
                cooldown_seconds=r.cooldown_seconds,
            )
            for r in config.alert_rules
        ]
        self.detector = RiskDetector(rules=rules)
        self.analyzer = RiskAnalyzer(llm_client=self.llm)

        # Delivery channels
        self.deliveries: list[tuple[DeliveryChannel, object]] = []
        self._setup_deliveries()

        self._running = False
        self._poll_count = 0

    def _setup_deliveries(self) -> None:
        """Configure notification delivery channels."""
        # Console is always enabled
        self.deliveries.append(
            (DeliveryChannel.CONSOLE, ConsoleDelivery())
        )

        if self.config.telegram.enabled:
            self.deliveries.append(
                (
                    DeliveryChannel.TELEGRAM,
                    TelegramDelivery(
                        bot_token=self.config.telegram.bot_token,
                        chat_id=self.config.telegram.chat_id,
                    ),
                )
            )

        if self.config.discord.enabled:
            self.deliveries.append(
                (
                    DeliveryChannel.DISCORD,
                    DiscordDelivery(webhook_url=self.config.discord.webhook_url),
                )
            )

    async def start(self) -> None:
        """Initialize all clients and start the polling loop."""
        await self.injective.initialize()
        await self.llm.initialize()

        if not self.config.addresses:
            logger.error("No addresses configured. Add addresses to config.yaml")
            return

        self._running = True
        logger.info(
            "Starting INJ Sentinel — monitoring %d address(es) every %ds",
            len(self.config.addresses),
            self.config.poll_interval_seconds,
        )

        try:
            while self._running:
                await self._poll_cycle()
                self._poll_count += 1
                await asyncio.sleep(self.config.poll_interval_seconds)
        except asyncio.CancelledError:
            logger.info("Polling cancelled")
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Stop the polling loop and clean up."""
        self._running = False
        await self.injective.close()
        logger.info("INJ Sentinel stopped after %d polls", self._poll_count)

    async def _poll_cycle(self) -> None:
        """Execute a single poll cycle across all watched addresses."""
        for watched in self.config.addresses:
            try:
                # 1. Fetch portfolio snapshot
                snapshot = await self.injective.fetch_portfolio(
                    address=watched.address,
                    label=watched.label,
                )

                # 2. Detect risk events
                events = self.detector.detect(snapshot)

                if not events:
                    if self._poll_count == 0:
                        # First poll: show status even with no alerts
                        logger.info(
                            "✅ %s: %d positions, %d balances — no risks detected",
                            watched.label or watched.address[:15],
                            len(snapshot.derivative_positions),
                            len(snapshot.spot_balances),
                        )
                    continue

                # 3. Analyze with AI
                alerts = await self.analyzer.analyze_batch(events)

                # 4. Deliver alerts
                for alert in alerts:
                    await self._deliver_alert(alert)

            except Exception as e:
                logger.error(
                    "Error polling %s: %s",
                    watched.label or watched.address[:15],
                    e,
                )

    async def _deliver_alert(self, alert: Alert) -> None:
        """Send an alert through all configured delivery channels."""
        for channel, delivery in self.deliveries:
            try:
                await delivery.send(alert)
                alert.delivered_via.append(channel)
            except Exception as e:
                logger.error("Failed to deliver via %s: %s", channel.value, e)

    async def poll_once(self) -> list[Alert]:
        """Execute a single poll and return alerts (useful for testing/CLI).

        Returns:
            List of all alerts generated in this poll cycle
        """
        await self.injective.initialize()
        await self.llm.initialize()

        all_alerts: list[Alert] = []

        for watched in self.config.addresses:
            snapshot = await self.injective.fetch_portfolio(
                address=watched.address,
                label=watched.label,
            )
            events = self.detector.detect(snapshot)
            if events:
                alerts = await self.analyzer.analyze_batch(events)
                for alert in alerts:
                    await self._deliver_alert(alert)
                all_alerts.extend(alerts)

        return all_alerts

    def get_status(self) -> dict:
        """Get current monitoring status."""
        return {
            "running": self._running,
            "poll_count": self._poll_count,
            "addresses": len(self.config.addresses),
            "network": self.config.network,
            "demo_mode": self.config.demo,
            "poll_interval": self.config.poll_interval_seconds,
            "delivery_channels": [ch.value for ch, _ in self.deliveries],
            "alert_rules": len(self.config.alert_rules),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
