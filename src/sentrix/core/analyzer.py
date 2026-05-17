"""AI risk analyzer — converts RiskEvents into human-readable Alerts."""

from __future__ import annotations

import logging

from sentrix.clients.llm import LLMClient
from sentrix.models.alert import Alert, RiskEvent
from sentrix.models.position import AlertSeverity

logger = logging.getLogger(__name__)


class RiskAnalyzer:
    """Transforms raw RiskEvents into AI-enhanced Alert objects.

    Uses LLM client for natural-language generation with template fallback.
    """

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm = llm_client

    async def analyze(self, event: RiskEvent) -> Alert:
        """Analyze a risk event and generate an Alert with AI insights.

        Args:
            event: Raw risk event from the detector

        Returns:
            Alert with natural-language title, message, and recommendation
        """
        if event.position and event.snapshot:
            title, message = await self.llm.generate_alert_message(
                position=event.position,
                snapshot=event.snapshot,
                alert_context=self._describe_event(event),
            )
        else:
            title, message = self._generic_alert(event)

        # Split recommendation from message if present
        recommendation = None
        if "💡" in message:
            parts = message.split("💡", 1)
            message = parts[0].strip()
            recommendation = "💡" + parts[1].strip()

        return Alert(
            address=event.address,
            alert_type=event.alert_type,
            severity=event.severity,
            title=title,
            message=message,
            recommendation=recommendation,
            position=event.position,
            snapshot=event.snapshot,
        )

    async def analyze_batch(self, events: list[RiskEvent]) -> list[Alert]:
        """Analyze multiple risk events.

        Args:
            events: List of risk events

        Returns:
            List of alerts
        """
        alerts: list[Alert] = []
        for event in events:
            alert = await self.analyze(event)
            alerts.append(alert)
        return alerts

    def _describe_event(self, event: RiskEvent) -> str:
        """Create a brief context description for the LLM."""
        alert_val = event.alert_type.value
        if alert_val == "liquidation_warning":
            margin = event.raw_data.get("margin_ratio", 0)
            thresh = event.raw_data.get("threshold", "?")
            return f"Margin ratio at {margin:.2f}x, threshold is {thresh}x"
        elif alert_val == "balance_change":
            direction = event.raw_data.get("direction", "changed")
            change = event.raw_data.get("change_usd", 0)
            return f"Balance {direction} by ${change:,.2f}"
        elif alert_val == "margin_degradation":
            return "Margin ratio declining rapidly"
        return "Risk detected"

    def _generic_alert(self, event: RiskEvent) -> tuple[str, str]:
        """Generate a generic alert when no position context is available."""
        severity_emoji = {
            AlertSeverity.LOW: "ℹ️",
            AlertSeverity.MEDIUM: "⚡",
            AlertSeverity.HIGH: "⚠️",
            AlertSeverity.CRITICAL: "🚨",
        }
        emoji = severity_emoji.get(event.severity, "⚠️")
        title = f"{emoji} {event.alert_type.value.replace('_', ' ').title()}"
        message = f"Risk event detected for {event.address}: {event.alert_type.value}"
        return title, message
