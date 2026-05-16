"""Tests for the Injective client (demo mode)."""

from __future__ import annotations

import pytest

from inj_sentinel.clients.injective import InjectiveClient


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
    async def test_fetch_fixture_portfolio(self) -> None:
        """Should load from fixture file when available."""
        client = InjectiveClient(demo=True)
        await client.initialize()

        snapshot = await client.fetch_portfolio("inj1demo_trader_alice", "Alice")
        # If fixtures loaded, should have positions
        if snapshot.derivative_positions:
            assert snapshot.derivative_positions[0].ticker == "INJ/USDT PERP"

    @pytest.mark.asyncio
    async def test_close(self) -> None:
        """Close should reset state."""
        client = InjectiveClient(demo=True)
        await client.initialize()
        await client.close()
        assert client._initialized is False
