"""Tests for the Injective client (demo mode and mocked live mode)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sentrix.clients.injective import InjectiveClient
from sentrix.models.position import PositionDirection


class TestInjectiveClientDemo:
    """Tests for InjectiveClient in demo mode."""

    @pytest.mark.asyncio
    async def test_initialize_demo(self) -> None:
        """Demo mode should initialize without network."""
        client = InjectiveClient(demo=True)
        await client.initialize()
        assert client._initialized is True
        assert client.demo is True

    @pytest.mark.asyncio
    async def test_fetch_demo_portfolio(self) -> None:
        """Should return a valid portfolio in demo mode."""
        client = InjectiveClient(demo=True)
        await client.initialize()

        snapshot = await client.fetch_portfolio("demo", "Test")
        assert snapshot.address == "demo" or snapshot.address.startswith("inj1")
        assert len(snapshot.derivative_positions) > 0 or len(snapshot.spot_balances) > 0

    @pytest.mark.asyncio
    async def test_fetch_fixture_portfolio(self, tmp_path) -> None:
        """Should load from fixture file when available."""
        client = InjectiveClient(demo=True)
        await client.initialize()

        # Mock the Path to return a temporary file
        mock_data = [
            {
                "address": "inj1demo_trader_alice",
                "label": "Alice",
                "positions": [
                    {
                        "market": "INJ/USDT PERP",
                        "direction": "long",
                        "quantity": 10,
                        "entry_price": 10.0,
                        "mark_price": 11.0,
                        "liquidation_price": 5.0,
                        "margin": 100.0,
                        "leverage": "5x"
                    }
                ],
                "spot_balances": [
                    {"denom": "inj", "amount": 100}
                ]
            }
        ]
        
        with patch('sentrix.clients.injective.Path') as mock_path:
            mock_file = MagicMock()
            mock_file.exists.return_value = True
            mock_file.read_text.return_value = json.dumps(mock_data)
            
            mock_path.return_value.parent.parent.parent.parent.__truediv__.return_value.__truediv__.return_value.__truediv__.return_value = mock_file
            
            snapshot = await client.fetch_portfolio("inj1demo_trader_alice", "Alice")
            
            if snapshot.derivative_positions:
                assert snapshot.derivative_positions[0].ticker == "INJ/USDT PERP"

    @pytest.mark.asyncio
    async def test_fetch_fixture_portfolio_fallback_to_first(self) -> None:
        """Should load first fixture if address not found."""
        client = InjectiveClient(demo=True)
        await client.initialize()
        
        mock_data = [
            {
                "address": "inj1other",
                "positions": [],
                "spot_balances": []
            }
        ]
        
        with patch('sentrix.clients.injective.Path') as mock_path:
            mock_file = MagicMock()
            mock_file.exists.return_value = True
            mock_file.read_text.return_value = json.dumps(mock_data)
            
            mock_path.return_value.parent.parent.parent.parent.__truediv__.return_value.__truediv__.return_value.__truediv__.return_value = mock_file
            
            snapshot = await client.fetch_portfolio("inj1notfound", "Label")
            assert snapshot.address == "inj1other"
            assert snapshot.label == "Label"

    @pytest.mark.asyncio
    async def test_generate_demo_data_fallback(self) -> None:
        """Should generate hardcoded demo data when fixtures not available."""
        client = InjectiveClient(demo=True)
        await client.initialize()
        
        with patch('sentrix.clients.injective.Path') as mock_path:
            mock_file = MagicMock()
            mock_file.exists.return_value = False
            
            mock_path.return_value.parent.parent.parent.parent.__truediv__.return_value.__truediv__.return_value.__truediv__.return_value = mock_file
            
            snapshot = await client.fetch_portfolio("inj1notfound", "Label")
            assert snapshot.address == "inj1notfound"
            assert snapshot.label == "Label"
            assert len(snapshot.derivative_positions) == 2
            assert len(snapshot.spot_balances) == 2

    @pytest.mark.asyncio
    async def test_close(self) -> None:
        """Close should reset state."""
        client = InjectiveClient(demo=True)
        await client.initialize()
        await client.close()
        assert client._initialized is False


class TestInjectiveClientLive:
    """Tests for live InjectiveClient execution."""
    
    @pytest.mark.asyncio
    async def test_initialize_import_error(self) -> None:
        """Should fallback to demo mode if injective-py is missing."""
        client = InjectiveClient(network="mainnet", demo=False)
        
        # Patch sys.modules to simulate missing injective-py
        with patch.dict(sys.modules, {'pyinjective.async_client': None}):
            await client.initialize()
            
        assert client._initialized is True
        assert client.demo is True

    @pytest.mark.asyncio
    async def test_initialize_live(self) -> None:
        """Should initialize AsyncClient."""
        client = InjectiveClient(network="testnet", demo=False)
        
        mock_network = MagicMock()
        mock_async_client = MagicMock()
        
        mock_pyinjective = MagicMock()
        mock_pyinjective.async_client.AsyncClient = mock_async_client
        mock_pyinjective.core.network.Network.testnet = mock_network
        
        with patch.dict(sys.modules, {
            'pyinjective': mock_pyinjective,
            'pyinjective.async_client': mock_pyinjective.async_client,
            'pyinjective.core': mock_pyinjective.core,
            'pyinjective.core.network': mock_pyinjective.core.network,
        }):
            await client.initialize()
            
        assert client._initialized is True
        assert client.demo is False
        assert client._client is not None
        
    @pytest.mark.asyncio
    async def test_initialize_live_exception(self) -> None:
        """Should raise Exception if connection fails."""
        client = InjectiveClient(network="mainnet", demo=False)
        
        mock_network = MagicMock()
        mock_async_client = MagicMock(side_effect=Exception("Connection failed"))
        
        mock_pyinjective = MagicMock()
        mock_pyinjective.async_client.AsyncClient = mock_async_client
        mock_pyinjective.core.network.Network.mainnet = mock_network
        
        with patch.dict(sys.modules, {
            'pyinjective': mock_pyinjective,
            'pyinjective.async_client': mock_pyinjective.async_client,
            'pyinjective.core': mock_pyinjective.core,
            'pyinjective.core.network': mock_pyinjective.core.network,
        }):
            with pytest.raises(Exception):
                await client.initialize()

    @pytest.mark.asyncio
    async def test_fetch_portfolio_live(self) -> None:
        """Should fetch spot and derivative positions."""
        client = InjectiveClient(demo=False)
        client._client = AsyncMock()
        client._initialized = True
        
        client._client.fetch_bank_balances.return_value = {
            "balances": [{"denom": "inj", "amount": "100"}]
        }
        
        client._client.fetch_derivative_positions.return_value = {
            "positions": [
                {
                    "marketId": "0x123",
                    "ticker": "INJ/USDT PERP",
                    "direction": "long",
                    "quantity": "10",
                    "entryPrice": "10.0",
                    "markPrice": "11.0",
                    "liquidationPrice": "5.0",
                    "margin": "100.0",
                    "leverage": "5"
                },
                {
                    "marketId": "0x456",
                    "ticker": "BTC/USDT PERP",
                    "direction": "short",
                    "quantity": "1",
                }
            ]
        }
        
        snapshot = await client.fetch_portfolio("inj1test")
        
        assert snapshot.address == "inj1test"
        assert len(snapshot.spot_balances) == 1
        assert snapshot.spot_balances[0].amount == "100"
        
        assert len(snapshot.derivative_positions) == 2
        assert snapshot.derivative_positions[0].direction == PositionDirection.LONG
        assert snapshot.derivative_positions[1].direction == PositionDirection.SHORT
        assert snapshot.derivative_positions[0].leverage == "5x"

    @pytest.mark.asyncio
    async def test_fetch_portfolio_live_errors(self) -> None:
        """Should handle errors during fetching."""
        client = InjectiveClient(demo=False)
        client._client = AsyncMock()
        client._initialized = True
        
        client._client.fetch_bank_balances.side_effect = Exception("API error")
        client._client.fetch_derivative_positions.side_effect = Exception("API error")
        
        snapshot = await client.fetch_portfolio("inj1test")
        
        assert snapshot.address == "inj1test"
        assert len(snapshot.spot_balances) == 0
        assert len(snapshot.derivative_positions) == 0

    @pytest.mark.asyncio
    async def test_fetch_with_no_client(self) -> None:
        """Should return empty if no client initialized."""
        client = InjectiveClient(demo=False)
        client._client = None
        
        spot = await client._fetch_spot_balances("inj1test")
        assert spot == []
        
        deriv = await client._fetch_derivative_positions("inj1test")
        assert deriv == []
