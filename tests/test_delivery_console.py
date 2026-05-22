"""Tests for console delivery."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from rich.panel import Panel

from sentrix.delivery.console import ConsoleDelivery
from sentrix.models.alert import Alert
from sentrix.models.position import AlertSeverity, AlertType, DeliveryChannel


@pytest.mark.asyncio
async def test_console_delivery_send() -> None:
    """Test console delivery correctly formats and prints an alert."""
    alert = Alert(
        address="inj1test",
        alert_type=AlertType.LIQUIDATION_WARNING,
        severity=AlertSeverity.HIGH,
        title="High Risk",
        message="Margin is very low",
        recommendation="Deposit more funds",
        delivered_via=[DeliveryChannel.TELEGRAM]
    )

    delivery = ConsoleDelivery()

    with patch.object(delivery.console, "print") as mock_print:
        await delivery.send(alert)

        mock_print.assert_called_once()
        args, kwargs = mock_print.call_args
        panel = args[0]

        assert isinstance(panel, Panel)
        assert panel.title == "High Risk"
        assert panel.border_style == "red"  # Because it's critical/high (is_critical=True)
