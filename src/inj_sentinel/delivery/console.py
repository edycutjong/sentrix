"""Console delivery — rich terminal output for alerts."""

from __future__ import annotations

import logging

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from inj_sentinel.models.alert import Alert
from inj_sentinel.models.position import AlertSeverity

logger = logging.getLogger(__name__)

# Severity to Rich style mapping
SEVERITY_STYLES = {
    AlertSeverity.LOW: "blue",
    AlertSeverity.MEDIUM: "yellow",
    AlertSeverity.HIGH: "dark_orange",
    AlertSeverity.CRITICAL: "bold red",
}


class ConsoleDelivery:
    """Deliver alerts to the terminal using Rich formatting."""

    def __init__(self) -> None:
        self.console = Console()

    async def send(self, alert: Alert) -> None:
        """Print a rich-formatted alert to the console.

        Args:
            alert: The alert to display
        """
        style = SEVERITY_STYLES.get(alert.severity, "white")
        border_style = "red" if alert.is_critical else "yellow"

        content = Text()
        content.append(f"{alert.severity_emoji} ", style=style)
        content.append(f"[{alert.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}] ", style="dim")
        content.append(f"{alert.severity.value.upper()} ALERT\n", style=style)
        content.append("─" * 48 + "\n", style="dim")
        content.append(alert.message + "\n")

        if alert.recommendation:
            content.append("\n" + alert.recommendation + "\n")

        # Show delivery channels
        if alert.delivered_via:
            channels = ", ".join(ch.value for ch in alert.delivered_via)
            content.append(f"\n📱 Sent to: {channels}", style="dim")

        panel = Panel(
            content,
            title=alert.title,
            border_style=border_style,
            padding=(0, 1),
        )
        self.console.print(panel)
