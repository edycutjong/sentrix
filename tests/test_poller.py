import asyncio
import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sentrix.core.poller import Poller
from sentrix.models.alert import Alert, AlertType
from sentrix.models.position import DeliveryChannel


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.network = "testnet"
    config.demo = True
    config.llm = MagicMock()
    config.llm.provider = "openai"
    config.llm.model = "gpt-4o"
    config.llm.api_key = "test-key"

    rule = MagicMock()
    rule.alert_type = AlertType.LIQUIDATION_WARNING
    rule.threshold = 0.5
    rule.enabled = True
    rule.cooldown_seconds = 3600
    config.alert_rules = [rule]

    address = MagicMock()
    address.address = "inj1test"
    address.label = "Test Wallet"
    config.addresses = [address]

    config.poll_interval_seconds = 0
    config.telegram.enabled = True
    config.telegram.bot_token = "token"
    config.telegram.chat_id = "123"
    config.discord.enabled = True
    config.discord.webhook_url = "http://test.com"
    return config


@pytest.fixture
def poller(mock_config):
    with patch("sentrix.core.poller.InjectiveClient", autospec=True) as mock_injective, \
         patch("sentrix.core.poller.LLMClient", autospec=True) as mock_llm, \
         patch("sentrix.core.poller.RiskDetector", autospec=True) as mock_detector, \
         patch("sentrix.core.poller.RiskAnalyzer", autospec=True) as mock_analyzer:

        p = Poller(mock_config)
        p.injective = mock_injective.return_value
        p.llm = mock_llm.return_value
        p.detector = mock_detector.return_value
        p.analyzer = mock_analyzer.return_value

        p.injective.initialize = AsyncMock()
        p.injective.close = AsyncMock()
        p.llm.initialize = AsyncMock()

        yield p


@pytest.mark.asyncio
async def test_poller_setup_deliveries(mock_config):
    p = Poller(mock_config)
    assert len(p.deliveries) == 3
    channels = [ch for ch, _ in p.deliveries]
    assert DeliveryChannel.CONSOLE in channels
    assert DeliveryChannel.TELEGRAM in channels
    assert DeliveryChannel.DISCORD in channels


@pytest.mark.asyncio
async def test_start_no_addresses(poller):
    poller.config.addresses = []
    await poller.start()
    assert poller._running is False
    poller.injective.initialize.assert_awaited_once()
    poller.llm.initialize.assert_awaited_once()


@pytest.mark.asyncio
async def test_poll_once(poller):
    snapshot_mock = MagicMock()
    event_mock = MagicMock()
    alert_mock = MagicMock(spec=Alert)
    alert_mock.delivered_via = []

    poller.injective.fetch_portfolio = AsyncMock(return_value=snapshot_mock)
    poller.detector.detect.return_value = [event_mock]
    poller.analyzer.analyze_batch = AsyncMock(return_value=[alert_mock])

    # Mock deliveries
    for _, d in poller.deliveries:
        d.send = AsyncMock()

    alerts = await poller.poll_once()

    assert len(alerts) == 1
    poller.injective.fetch_portfolio.assert_awaited_once()
    poller.detector.detect.assert_called_once_with(snapshot_mock)
    poller.analyzer.analyze_batch.assert_awaited_once_with([event_mock])

    for _, d in poller.deliveries:
        d.send.assert_awaited_once_with(alert_mock)

    assert len(alert_mock.delivered_via) == 3


@pytest.mark.asyncio
async def test_poll_cycle_error_handling(poller):
    poller.injective.fetch_portfolio = AsyncMock(side_effect=Exception("API Error"))

    # Should not raise exception
    await poller._poll_cycle()

    poller.injective.fetch_portfolio.assert_awaited_once()
    poller.detector.detect.assert_not_called()


@pytest.mark.asyncio
async def test_start_and_stop(poller):
    poller.injective.fetch_portfolio = AsyncMock(return_value=MagicMock())
    poller.detector.detect.return_value = []

    task = asyncio.create_task(poller.start())
    await asyncio.sleep(0.1)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task

    assert poller._poll_count > 0
    poller.injective.close.assert_awaited_once()

@pytest.mark.asyncio
async def test_poll_cycle_success(poller):
    snapshot_mock = MagicMock()
    event_mock = MagicMock()
    alert_mock = MagicMock(spec=Alert)
    alert_mock.delivered_via = []

    poller.injective.fetch_portfolio = AsyncMock(return_value=snapshot_mock)
    poller.detector.detect.return_value = [event_mock]
    poller.analyzer.analyze_batch = AsyncMock(return_value=[alert_mock])

    for _, d in poller.deliveries:
        d.send = AsyncMock()

    await poller._poll_cycle()

    poller.analyzer.analyze_batch.assert_awaited_once_with([event_mock])
    assert len(alert_mock.delivered_via) == 3

@pytest.mark.asyncio
async def test_deliver_alert_failure(poller):
    alert_mock = MagicMock(spec=Alert)
    alert_mock.delivered_via = []

    # Make the first delivery fail
    poller.deliveries[0][1].send = AsyncMock(side_effect=Exception("Delivery failed"))
    for i in range(1, len(poller.deliveries)):
        poller.deliveries[i][1].send = AsyncMock()

    await poller._deliver_alert(alert_mock)

    assert len(alert_mock.delivered_via) == len(poller.deliveries) - 1


@pytest.mark.asyncio
async def test_get_status(poller):
    status = poller.get_status()
    assert "running" in status
    assert "poll_count" in status
    assert status["running"] is False
    assert status["poll_count"] == 0

