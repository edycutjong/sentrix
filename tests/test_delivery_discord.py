"""Tests for Discord delivery."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sentrix.delivery.discord import DiscordDelivery
from sentrix.models.alert import Alert
from sentrix.models.position import AlertSeverity, AlertType, DerivativePosition, PositionDirection


@pytest.mark.asyncio
async def test_discord_delivery_send_success() -> None:
    """Test successful Discord webhook send."""
    alert = Alert(
        address="inj1test",
        alert_type=AlertType.LIQUIDATION_WARNING,
        severity=AlertSeverity.HIGH,
        title="High Risk",
        message="Margin is very low",
        recommendation="Deposit more funds",
    )

    delivery = DiscordDelivery("https://test.webhook")
    
    mock_resp = AsyncMock()
    mock_resp.status = 204
    
    mock_post_cm = AsyncMock()
    mock_post_cm.__aenter__.return_value = mock_resp
    
    mock_session = MagicMock()
    mock_session.post.return_value = mock_post_cm
    
    mock_client_cm = AsyncMock()
    mock_client_cm.__aenter__.return_value = mock_session
    
    with patch("sentrix.delivery.discord.aiohttp.ClientSession", return_value=mock_client_cm):
        await delivery.send(alert)
        
        mock_session.post.assert_called_once()
        args, kwargs = mock_session.post.call_args
        assert args[0] == "https://test.webhook"
        
        payload = json.loads(kwargs["data"])
        assert payload["username"] == "Sentrix"
        assert len(payload["embeds"]) == 1
        
        embed = payload["embeds"][0]
        assert embed["title"] == "⚠️ High Risk"
        assert embed["description"] == "Margin is very low"
        assert len(embed["fields"]) == 1
        assert embed["fields"][0]["name"] == "💡 Action"
        assert embed["fields"][0]["value"] == "Deposit more funds"


@pytest.mark.asyncio
async def test_discord_delivery_send_with_position() -> None:
    """Test Discord webhook send with position data."""
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

    delivery = DiscordDelivery("https://test.webhook")
    
    mock_resp = AsyncMock()
    mock_resp.status = 200
    
    mock_post_cm = AsyncMock()
    mock_post_cm.__aenter__.return_value = mock_resp
    
    mock_session = MagicMock()
    mock_session.post.return_value = mock_post_cm
    
    mock_client_cm = AsyncMock()
    mock_client_cm.__aenter__.return_value = mock_session
    
    with patch("sentrix.delivery.discord.aiohttp.ClientSession", return_value=mock_client_cm):
        await delivery.send(alert)
        
        mock_session.post.assert_called_once()
        args, kwargs = mock_session.post.call_args
        payload = json.loads(kwargs["data"])
        
        embed = payload["embeds"][0]
        assert len(embed["fields"]) == 3
        
        assert embed["fields"][0]["name"] == "📊 Position"
        assert "Long 5x" in embed["fields"][0]["value"]
        
        assert embed["fields"][1]["name"] == "📉 Risk"
        assert "Margin: 1.04x" in embed["fields"][1]["value"]
        
        assert embed["fields"][2]["name"] == "💰 PnL"
        assert "$-1,000.00" in embed["fields"][2]["value"]


@pytest.mark.asyncio
async def test_discord_delivery_http_error() -> None:
    """Test Discord webhook send when HTTP error occurs."""
    alert = Alert(
        address="inj1test",
        alert_type=AlertType.LIQUIDATION_WARNING,
        severity=AlertSeverity.LOW,
        title="Test",
        message="Msg",
    )

    delivery = DiscordDelivery("https://test.webhook")
    
    mock_resp = AsyncMock()
    mock_resp.status = 400
    mock_resp.text.return_value = "Bad Request"
    
    mock_post_cm = AsyncMock()
    mock_post_cm.__aenter__.return_value = mock_resp
    
    mock_session = MagicMock()
    mock_session.post.return_value = mock_post_cm
    
    mock_client_cm = AsyncMock()
    mock_client_cm.__aenter__.return_value = mock_session
    
    with patch("sentrix.delivery.discord.aiohttp.ClientSession", return_value=mock_client_cm):
        # Shouldn't raise exception, just log it
        await delivery.send(alert)
        mock_session.post.assert_called_once()


@pytest.mark.asyncio
async def test_discord_delivery_network_error() -> None:
    """Test Discord webhook send when network exception occurs."""
    alert = Alert(
        address="inj1test",
        alert_type=AlertType.LIQUIDATION_WARNING,
        severity=AlertSeverity.LOW,
        title="Test",
        message="Msg",
    )

    delivery = DiscordDelivery("https://test.webhook")
    
    mock_session = MagicMock()
    mock_session.post.side_effect = Exception("Network failure")
    
    mock_client_cm = AsyncMock()
    mock_client_cm.__aenter__.return_value = mock_session
    
    with patch("sentrix.delivery.discord.aiohttp.ClientSession", return_value=mock_client_cm):
        # Should raise the exception
        with pytest.raises(Exception, match="Network failure"):
            await delivery.send(alert)
