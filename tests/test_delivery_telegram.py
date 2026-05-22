"""Tests for Telegram delivery."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sentrix.delivery.telegram import TelegramDelivery
from sentrix.models.alert import Alert
from sentrix.models.position import AlertSeverity, AlertType, DerivativePosition, PositionDirection


@pytest.fixture
def mock_telegram_bot():
    """Mock the python-telegram-bot library."""
    mock_bot_class = MagicMock()
    mock_bot_instance = AsyncMock()
    mock_bot_class.return_value = mock_bot_instance

    mock_module = MagicMock()
    mock_module.Bot = mock_bot_class

    with patch.dict("sys.modules", {"telegram": mock_module}):
        yield mock_bot_class, mock_bot_instance


@pytest.mark.asyncio
async def test_telegram_delivery_success(mock_telegram_bot) -> None:
    """Test successful Telegram message send."""
    mock_bot_class, mock_bot_instance = mock_telegram_bot

    delivery = TelegramDelivery("test_token", "test_chat")
    alert = Alert(
        address="inj1test",
        alert_type=AlertType.LIQUIDATION_WARNING,
        severity=AlertSeverity.HIGH,
        title="Test Alert",
        message="Test message",
        recommendation="Do something"
    )

    await delivery.send(alert)

    mock_bot_class.assert_called_once_with(token="test_token")
    mock_bot_instance.send_message.assert_called_once()

    kwargs = mock_bot_instance.send_message.call_args.kwargs
    assert kwargs["chat_id"] == "test_chat"
    assert kwargs["parse_mode"] == "HTML"
    assert "Test Alert" in kwargs["text"]
    assert "Test message" in kwargs["text"]
    assert "Do something" in kwargs["text"]


@pytest.mark.asyncio
async def test_telegram_delivery_with_position(mock_telegram_bot) -> None:
    """Test Telegram message format with position data."""
    mock_bot_class, mock_bot_instance = mock_telegram_bot

    delivery = TelegramDelivery("test_token", "test_chat")
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
    alert = Alert(
        address="inj1test",
        alert_type=AlertType.LIQUIDATION_WARNING,
        severity=AlertSeverity.CRITICAL,
        title="Crit Risk",
        message="Margin is critical",
        position=pos,
    )

    await delivery.send(alert)

    kwargs = mock_bot_instance.send_message.call_args.kwargs
    text = kwargs["text"]

    assert "Position:" in text
    assert "Long 5x" in text
    assert "Entry: $14.00" in text
    assert "Now: $13.00" in text
    assert "Liquidation: $12.50" in text


@pytest.mark.asyncio
async def test_telegram_delivery_missing_dependency() -> None:
    """Test behavior when python-telegram-bot is not installed."""
    delivery = TelegramDelivery("test_token", "test_chat")
    alert = Alert(
        address="inj1test",
        alert_type=AlertType.LIQUIDATION_WARNING,
        severity=AlertSeverity.HIGH,
        title="Test",
        message="Msg"
    )

    # Hide the telegram module by setting it to None in sys.modules
    with patch.dict("sys.modules", {"telegram": None}), pytest.raises(ImportError):
        await delivery.send(alert)


@pytest.mark.asyncio
async def test_telegram_delivery_send_error(mock_telegram_bot) -> None:
    """Test handling of Telegram API errors."""
    mock_bot_class, mock_bot_instance = mock_telegram_bot
    mock_bot_instance.send_message.side_effect = Exception("API Error")

    delivery = TelegramDelivery("test_token", "test_chat")
    alert = Alert(
        address="inj1test",
        alert_type=AlertType.LIQUIDATION_WARNING,
        severity=AlertSeverity.HIGH,
        title="Test",
        message="Msg"
    )

    with pytest.raises(Exception, match="API Error"):
        await delivery.send(alert)
