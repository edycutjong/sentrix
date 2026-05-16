"""Tests for the LLM client (template fallback)."""

from __future__ import annotations

import pytest

from inj_sentinel.clients.llm import LLMClient
from inj_sentinel.models.position import (
    DerivativePosition,
    PortfolioSnapshot,
)


class TestLLMClient:
    """Tests for LLMClient template-based alerts."""

    @pytest.mark.asyncio
    async def test_template_alert(
        self,
        risky_position: DerivativePosition,
        portfolio_with_risk: PortfolioSnapshot,
    ) -> None:
        """Template fallback should generate a useful alert."""
        client = LLMClient()  # No API key = template mode
        await client.initialize()

        title, message = await client.generate_alert_message(
            position=risky_position,
            snapshot=portfolio_with_risk,
        )

        assert "INJ/USDT PERP" in title
        assert "liquidation" in message.lower() or "liq" in message.lower()
        assert "$" in message  # Should contain dollar amounts

    @pytest.mark.asyncio
    async def test_template_summary(
        self,
        portfolio_with_risk: PortfolioSnapshot,
    ) -> None:
        """Template summary should include key stats."""
        client = LLMClient()
        await client.initialize()

        summary = await client.generate_summary(portfolio_with_risk)
        assert "Test Trader" in summary or "inj1" in summary
        assert "position" in summary.lower()

    @pytest.mark.asyncio
    async def test_empty_portfolio_summary(self) -> None:
        """Empty portfolio should return a simple message."""
        client = LLMClient()
        await client.initialize()

        snapshot = PortfolioSnapshot(address="inj1test")
        summary = await client.generate_summary(snapshot)
        assert "no" in summary.lower() or "No" in summary

    def test_calculate_margin_to_safety(
        self, risky_position: DerivativePosition
    ) -> None:
        """Should calculate margin needed to reach 1.5x."""
        client = LLMClient()
        margin_needed = client._calculate_margin_to_safety(risky_position)
        assert margin_needed > 0
