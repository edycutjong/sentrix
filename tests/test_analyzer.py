"""Tests for AI risk analyzer."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from sentrix.core.analyzer import RiskAnalyzer
from sentrix.models.alert import AlertType, RiskEvent
from sentrix.models.position import AlertSeverity, DerivativePosition, PositionDirection


@pytest.fixture
def mock_llm_client():
    """Mock the LLM client."""
    client = AsyncMock()
    # By default return a title and message
    client.generate_alert_message.return_value = (
        "AI Generated Title",
        "AI Generated Message.\n💡 AI Recommendation"
    )
    return client


@pytest.mark.asyncio
async def test_analyzer_with_position_and_snapshot(mock_llm_client) -> None:
    """Test analysis when position and snapshot are present."""
    analyzer = RiskAnalyzer(mock_llm_client)

    pos = DerivativePosition(
        market_id="0x_test",
        ticker="INJ/USDT PERP",
        direction=PositionDirection.LONG,
        quantity="1000",
        entry_price="14.00",
        mark_price="13.00",
        liquidation_price="12.50",
        margin="2000",
        leverage="5x",
    )

    # We can mock the snapshot since it's just passed along to the LLM client and Alert
    mock_snapshot = {"address": "inj1test"}

    event = RiskEvent(
        address="inj1test",
        alert_type=AlertType.LIQUIDATION_WARNING,
        severity=AlertSeverity.HIGH,
        raw_data={"margin_ratio": 1.04, "threshold": 1.1},
        position=pos,
        snapshot=mock_snapshot  # type: ignore
    )

    alert = await analyzer.analyze(event)

    mock_llm_client.generate_alert_message.assert_called_once()
    assert alert.title == "AI Generated Title"
    assert alert.message == "AI Generated Message."
    assert alert.recommendation == "💡AI Recommendation"
    assert alert.position == pos


@pytest.mark.asyncio
async def test_analyzer_no_position(mock_llm_client) -> None:
    """Test analysis when position is missing (fallback)."""
    analyzer = RiskAnalyzer(mock_llm_client)

    event = RiskEvent(
        address="inj1test",
        alert_type=AlertType.BALANCE_CHANGE,
        severity=AlertSeverity.MEDIUM,
        raw_data={"direction": "decreased", "change_usd": 500}
    )

    alert = await analyzer.analyze(event)

    # LLM should not be called
    mock_llm_client.generate_alert_message.assert_not_called()
    assert alert.title == "⚡ Balance Change"
    assert "balance_change" in alert.message
    assert "inj1test" in alert.message
    assert alert.recommendation is None


@pytest.mark.asyncio
async def test_analyze_batch(mock_llm_client) -> None:
    """Test analyzing multiple events."""
    analyzer = RiskAnalyzer(mock_llm_client)

    events = [
        RiskEvent(
            address="inj1test",
            alert_type=AlertType.BALANCE_CHANGE,
            severity=AlertSeverity.LOW,
            raw_data={}
        ),
        RiskEvent(
            address="inj2test",
            alert_type=AlertType.MARGIN_DEGRADATION,
            severity=AlertSeverity.CRITICAL,
            raw_data={}
        )
    ]

    alerts = await analyzer.analyze_batch(events)

    assert len(alerts) == 2
    assert alerts[0].title == "ℹ️ Balance Change"
    assert alerts[1].title == "🚨 Margin Degradation"


def test_describe_event() -> None:
    """Test the event descriptions logic."""
    analyzer = RiskAnalyzer(AsyncMock())

    # Liquidation Warning
    ev1 = RiskEvent(
        address="inj1", alert_type=AlertType.LIQUIDATION_WARNING, severity=AlertSeverity.HIGH,
        raw_data={"margin_ratio": 1.5, "threshold": 2.0}
    )
    desc1 = analyzer._describe_event(ev1)
    assert "Margin ratio at 1.50x" in desc1

    # Balance Change
    ev2 = RiskEvent(
        address="inj1", alert_type=AlertType.BALANCE_CHANGE, severity=AlertSeverity.HIGH,
        raw_data={"direction": "decreased", "change_usd": 1000.5}
    )
    desc2 = analyzer._describe_event(ev2)
    assert "Balance decreased by $1,000.50" in desc2

    # Margin Degradation
    ev3 = RiskEvent(
        address="inj1", alert_type=AlertType.MARGIN_DEGRADATION, severity=AlertSeverity.HIGH,
        raw_data={}
    )
    desc3 = analyzer._describe_event(ev3)
    assert desc3 == "Margin ratio declining rapidly"

    # Unknown type fallback
    # Create an alert type that isn't explicitly handled in descriptions
    ev4 = MagicMock()
    ev4.alert_type.value = "unknown_type"
    desc4 = analyzer._describe_event(ev4)
    assert desc4 == "Risk detected"
