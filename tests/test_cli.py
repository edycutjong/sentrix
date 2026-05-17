import pytest
from click.testing import CliRunner
from unittest.mock import patch, AsyncMock, MagicMock

from sentrix.cli import cli, setup_logging


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
        
        mock_instance = mock_poller.return_value
        
        # Mock asyncio.run to execute the coroutine directly
        def mock_run(coro):
            import asyncio
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
        
        # Mock the async status fetch
        def mock_run(coro):
            pass
            
        with patch("asyncio.run", side_effect=mock_run):
            result = runner.invoke(cli, ["status", "--demo", "--address", "test_addr"])
            assert result.exit_code == 0
            assert cfg.demo is True
            assert len(cfg.addresses) == 1


@patch("sentrix.storage.db.AlertStore", autospec=True)
def test_history_command(mock_store, runner):
    # Mock the store behavior
    store_instance = mock_store.return_value
    
    # Mock asyncio.run to simulate history printing
    def mock_run(coro):
        pass
        
    with patch("asyncio.run", side_effect=mock_run):
        result = runner.invoke(cli, ["history"])
        assert result.exit_code == 0


def test_history_command_async_logic():
    # Directly test the async logic inside history
    from sentrix.cli import cli
    # The inner function _show_history is nested, so we need a different approach 
    # to test its async logic without invoking click if we want 100% coverage
    
    # We can mock asyncio.run to actually run the passed coroutine in a test loop
    import asyncio
    
    runner = CliRunner()
    
    with patch("sentrix.storage.db.AlertStore", autospec=True) as mock_store:
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
    runner = CliRunner()
    
    with patch("sentrix.clients.injective.InjectiveClient", autospec=True) as mock_client_cls, \
         patch("sentrix.cli.SentinelConfig.load") as mock_load:
        
        cfg = MagicMock()
        watched = MagicMock()
        watched.address = "test_addr"
        watched.label = "Test Label"
        cfg.addresses = [watched]
        mock_load.return_value = cfg
        
        client_instance = mock_client_cls.return_value
        client_instance.initialize = AsyncMock()
        client_instance.close = AsyncMock()
        
        snapshot = MagicMock()
        snapshot.label = "Test Label"
        
        # Fake derivative positions
        pos1 = MagicMock()
        pos1.ticker = "INJ/USDT"
        pos1.direction.value = "long"
        pos1.leverage = 5
        pos1.margin_ratio = 1.6
        pos1.unrealized_pnl = 100.0
        
        pos2 = MagicMock()
        pos2.ticker = "BTC/USDT"
        pos2.direction.value = "short"
        pos2.leverage = 2
        pos2.margin_ratio = 1.1
        pos2.unrealized_pnl = -50.0
        
        snapshot.derivative_positions = [pos1, pos2]
        
        # Fake spot balances
        bal = MagicMock()
        bal.amount = 10
        bal.display_denom = "INJ"
        bal.usd_value = 100.0
        
        snapshot.spot_balances = [bal]
        
        client_instance.fetch_portfolio = AsyncMock(return_value=snapshot)
        
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0
        assert "INJ/USDT" in result.output
        assert "BTC/USDT" in result.output
        assert "Spot Balances" in result.output
        
        
def test_status_demo_no_addresses(runner):
    with patch("sentrix.cli.SentinelConfig.load") as mock_load, \
         patch("sentrix.clients.injective.InjectiveClient", autospec=True) as MockClient:
        
        cfg = MagicMock()
        cfg.addresses = []
        cfg.demo = False
        mock_load.return_value = cfg
        
        client_instance = MockClient.return_value
        client_instance.fetch_portfolio = AsyncMock()
        client_instance.fetch_portfolio.return_value.derivative_positions = []
        client_instance.fetch_portfolio.return_value.spot_balances = []
        client_instance.fetch_portfolio.return_value.label = "Demo Trader"
        result = runner.invoke(cli, ["status", "--demo"])
        assert result.exit_code == 0
        assert "Demo Trader" in result.output
        assert cfg.addresses[0].address == "demo"
        

def test_watch_interrupt(runner):
    with patch("sentrix.cli.SentinelConfig.load") as mock_load, \
         patch("sentrix.cli.Poller") as mock_poller:
        cfg = MagicMock()
        cfg.addresses = [MagicMock()]
        mock_load.return_value = cfg
        
        def mock_run(coro):
            raise KeyboardInterrupt()
            
        with patch("asyncio.run", side_effect=mock_run):
            result = runner.invoke(cli, ["watch"])
            assert result.exit_code == 0
            assert "Sentrix stopped" in result.output

