import asyncio as _asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from sentrix.cli import cli, setup_logging


def _run_coro(coro):
    """Actually run the coroutine to avoid 'was never awaited' warnings."""
    loop = _asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@pytest.fixture
def runner():
    return CliRunner()


def test_cli_help(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Sentrix" in result.output


def test_setup_logging():
    setup_logging(verbose=True)
    setup_logging(verbose=False)
    # Simple coverage for logging setup


@patch("sentrix.cli.Poller", autospec=True)
def test_watch_no_addresses(mock_poller, runner):
    # When no addresses are provided and not in demo mode, it should exit with 1
    with patch("sentrix.cli.SentinelConfig.load") as mock_load:
        cfg = MagicMock()
        cfg.addresses = []
        cfg.demo = False
        mock_load.return_value = cfg

        result = runner.invoke(cli, ["watch"])
        assert result.exit_code == 1
        assert "No addresses configured" in result.output


@patch("sentrix.cli.Poller", autospec=True)
def test_watch_demo_mode_fallback(mock_poller, runner):
    with patch("sentrix.cli.SentinelConfig.load") as mock_load:
        cfg = MagicMock()
        cfg.addresses = []
        cfg.demo = True
        mock_load.return_value = cfg

        # Override run to just return instead of blocking
        with patch("asyncio.run") as mock_run:
            result = runner.invoke(cli, ["watch", "--demo"])
            assert result.exit_code == 0
            # Demo fallback should inject 'demo' address
            assert cfg.addresses[0].address == "demo"
            mock_run.assert_called_once()


@patch("sentrix.cli.Poller", autospec=True)
def test_watch_once(mock_poller, runner):
    with patch("sentrix.cli.SentinelConfig.load") as mock_load:
        cfg = MagicMock()
        cfg.addresses = [MagicMock()]
        mock_load.return_value = cfg


        # Mock asyncio.run to execute the coroutine directly
        def mock_run(coro):
            return []  # Return empty alerts

        with patch("asyncio.run", side_effect=mock_run):
            result = runner.invoke(cli, ["watch", "--once", "--address", "test_addr"])
            assert result.exit_code == 0
            assert "No risk events detected" in result.output


@patch("sentrix.clients.injective.InjectiveClient", autospec=True)
def test_status_command(mock_client, runner):
    with patch("sentrix.cli.SentinelConfig.load") as mock_load:
        cfg = MagicMock()
        cfg.addresses = []
        cfg.demo = False
        mock_load.return_value = cfg

        # Mock the async status fetch — close coroutine to prevent warning
        def mock_run(coro):
            coro.close()

        with patch("sentrix.cli.asyncio.run", side_effect=mock_run):
            result = runner.invoke(cli, ["status", "--demo", "--address", "test_addr"])
            assert result.exit_code == 0
            assert cfg.demo  # mutated to True by CLI's --demo flag
            assert len(cfg.addresses) == 1


@patch("sentrix.storage.db.AlertStore", autospec=True)
def test_history_command(mock_store, runner):

    # Mock asyncio.run — close coroutine to prevent warning
    def mock_run(coro):
        coro.close()

    with patch("sentrix.cli.asyncio.run", side_effect=mock_run):
        result = runner.invoke(cli, ["history"])
        assert result.exit_code == 0


def test_history_command_async_logic():
    """Test history command async logic by running coroutines properly."""
    from sentrix.cli import cli

    runner = CliRunner()

    with patch("sentrix.storage.db.AlertStore", autospec=True) as mock_store, \
         patch("sentrix.cli.asyncio.run", side_effect=_run_coro):
        store_instance = mock_store.return_value
        store_instance.initialize = AsyncMock()

        # Test with empty alerts
        store_instance.get_recent_alerts = AsyncMock(return_value=[])
        result = runner.invoke(cli, ["history"])
        assert result.exit_code == 0
        assert "No alerts in history" in result.output

        # Test with alerts
        store_instance.get_recent_alerts = AsyncMock(return_value=[
            {
                "created_at": "2026-05-17T12:00:00Z",
                "severity": "high",
                "alert_type": "LIQUIDATION",
                "title": "Alert 1"
            },
            {
                "created_at": "2026-05-17T12:00:00Z",
                "severity": "unknown",
                "alert_type": "OTHER",
                "title": "Alert 2"
            }
        ])
        result = runner.invoke(cli, ["history"])
        assert result.exit_code == 0
        assert "Alert 1" in result.output
        assert "Alert 2" in result.output

def test_status_command_async_logic():
    """Test status command async logic by running coroutines properly."""
    runner = CliRunner()

    with patch("sentrix.clients.injective.InjectiveClient") as mock_client_cls, \
         patch("sentrix.cli.SentinelConfig.load") as mock_load, \
         patch("sentrix.cli.asyncio.run", side_effect=_run_coro):

        cfg = MagicMock()
        watched = MagicMock()
        watched.address = "test_addr"
        watched.label = "Test Label"
        cfg.addresses = [watched]
        mock_load.return_value = cfg

        client_instance = mock_client_cls.return_value
        client_instance.initialize = AsyncMock()
        client_instance.close = AsyncMock()

        # Use SimpleNamespace instead of MagicMock for data to avoid
        # spurious AsyncMock coroutine warnings from attribute access.
        from types import SimpleNamespace

        pos1 = SimpleNamespace(
            ticker="INJ/USDT",
            direction=SimpleNamespace(value="long"),
            leverage=5,
            margin_ratio=1.6,
            unrealized_pnl=100.0,
        )
        pos2 = SimpleNamespace(
            ticker="BTC/USDT",
            direction=SimpleNamespace(value="short"),
            leverage=2,
            margin_ratio=1.1,
            unrealized_pnl=-50.0,
        )
        bal = SimpleNamespace(amount=10, display_denom="INJ", usd_value=100.0)
        snapshot = SimpleNamespace(
            label="Test Label",
            derivative_positions=[pos1, pos2],
            spot_balances=[bal],
        )

        client_instance.fetch_portfolio = AsyncMock(return_value=snapshot)

        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0
        assert "INJ/USDT" in result.output
        assert "BTC/USDT" in result.output
        assert "Spot Balances" in result.output


def test_status_demo_no_addresses(runner):
    with patch("sentrix.cli.SentinelConfig.load") as mock_load, \
         patch("sentrix.clients.injective.InjectiveClient"), \
         patch("sentrix.cli.asyncio.run", side_effect=lambda coro: coro.close()):

        cfg = MagicMock()
        cfg.addresses = []
        cfg.demo = False
        mock_load.return_value = cfg

        result = runner.invoke(cli, ["status", "--demo"])
        assert result.exit_code == 0
        assert cfg.demo  # mutated to True by CLI's --demo flag
        assert cfg.addresses[0].address == "demo"


def test_watch_interrupt(runner):
    from types import SimpleNamespace

    with patch("sentrix.cli.SentinelConfig.load") as mock_load, \
         patch("sentrix.cli.Poller") as mock_poller_cls, \
         patch("sentrix.cli.asyncio.run") as mock_asyncio_run:

        cfg = SimpleNamespace(
            network="mainnet",
            demo=False,
            addresses=[SimpleNamespace(address="test", label="Test")],
            poll_interval_seconds=30,
            alert_rules=[],
        )
        mock_load.return_value = cfg

        # Create a proper coroutine for start() to avoid AsyncMock leaking
        async def _fake_start():
            pass

        mock_poller_cls.return_value.start = _fake_start

        def _raise_interrupt(coro):
            coro.close()
            raise KeyboardInterrupt()

        mock_asyncio_run.side_effect = _raise_interrupt

        result = runner.invoke(cli, ["watch"])
        assert result.exit_code == 0
        assert "Sentrix stopped" in result.output

