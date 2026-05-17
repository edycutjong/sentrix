"""Tests for the LLM client (template fallback)."""

from __future__ import annotations

import pytest

from sentrix.clients.llm import LLMClient
from sentrix.models.position import (
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

    def test_calculate_margin_to_safety_edge_cases(self) -> None:
        client = LLMClient()
        
        from sentrix.models.position import DerivativePosition, PositionDirection
        
        # Test ratio >= target_ratio
        safe_pos = DerivativePosition(
            market_id="test",
            ticker="TEST",
            direction=PositionDirection.LONG,
            quantity="1",
            entry_price="10",
            mark_price="10",
            liquidation_price="5",
            margin="10",
            leverage="1",
            unrealized_pnl="0"
        )
        # Margin ratio will be large enough
        safe_pos.margin = "100"
        margin_needed = client._calculate_margin_to_safety(safe_pos)
        assert margin_needed == 0.0
        
        # Test exception (ValueError/ZeroDivisionError)
        # We can set margin_ratio to raise an exception by setting margin to bad value
        class BadPosition:
            margin = "invalid"
            margin_ratio = 1.0
        
        margin_needed = client._calculate_margin_to_safety(BadPosition())
        assert margin_needed == 0.0

    @pytest.mark.asyncio
    async def test_initialize_openai(self) -> None:
        client = LLMClient(provider="openai", api_key="test-key")
        
        from unittest.mock import patch, MagicMock
        with patch("openai.AsyncOpenAI") as MockOpenAI:
            await client.initialize()
            assert client._client is not None
            MockOpenAI.assert_called_once_with(api_key="test-key")

    @pytest.mark.asyncio
    async def test_initialize_gemini(self) -> None:
        client = LLMClient(provider="gemini", api_key="test-key")
        
        from unittest.mock import patch, MagicMock
        with patch("google.genai.Client") as MockGenAI:
            await client.initialize()
            assert client._client is not None
            MockGenAI.assert_called_once_with(api_key="test-key")

    @pytest.mark.asyncio
    async def test_initialize_import_error(self) -> None:
        client = LLMClient(provider="openai", api_key="test-key")
        
        from unittest.mock import patch
        import builtins
        original_import = builtins.__import__
        
        def mock_import(name, *args, **kwargs):
            if name == "openai":
                raise ImportError("Mocked missing openai")
            return original_import(name, *args, **kwargs)
            
        with patch("builtins.__import__", side_effect=mock_import):
            await client.initialize()
            assert client._client is None

    @pytest.mark.asyncio
    async def test_call_llm_openai(self) -> None:
        client = LLMClient(provider="openai", api_key="test-key")
        client._client = type("MockOpenAIClient", (), {})()
        
        from unittest.mock import AsyncMock, MagicMock
        client._client.chat = MagicMock()
        client._client.chat.completions = MagicMock()
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Title\nMessage content"
        client._client.chat.completions.create = AsyncMock(return_value=mock_response)
        
        title, message = await client._call_llm("test prompt")
        assert title == "Title"
        assert message == "Message content"

    @pytest.mark.asyncio
    async def test_call_llm_gemini(self) -> None:
        client = LLMClient(provider="gemini", api_key="test-key")
        client._client = type("MockGeminiClient", (), {})()
        
        from unittest.mock import AsyncMock, MagicMock
        client._client.aio = MagicMock()
        client._client.aio.models = MagicMock()
        
        mock_response = MagicMock()
        mock_response.text = "# Risk Alert\nHere is the risk"
        client._client.aio.models.generate_content = AsyncMock(return_value=mock_response)
        
        title, message = await client._call_llm("test prompt")
        assert title == "Risk Alert"
        assert message == "Here is the risk"
        
    @pytest.mark.asyncio
    async def test_call_llm_unknown_provider(self) -> None:
        client = LLMClient(provider="unknown", api_key="test-key")
        title, message = await client._call_llm("test prompt")
        assert title == "Risk Alert"  # Fallback logic
        assert message == ""

    @pytest.mark.asyncio
    async def test_generate_alert_message_llm_error_fallback(
        self,
        risky_position: DerivativePosition,
        portfolio_with_risk: PortfolioSnapshot,
    ) -> None:
        client = LLMClient(provider="openai", api_key="test-key")
        client._client = "mocked"
        
        from unittest.mock import patch, AsyncMock
        with patch.object(client, "_call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = Exception("LLM is down")
            title, message = await client.generate_alert_message(risky_position, portfolio_with_risk)
            
            assert "⚠️" in title
            assert "liquidation" in message

    @pytest.mark.asyncio
    async def test_generate_summary_llm_error_fallback(
        self,
        portfolio_with_risk: PortfolioSnapshot,
    ) -> None:
        client = LLMClient(provider="openai", api_key="test-key")
        client._client = "mocked"
        
        from unittest.mock import patch, AsyncMock
        with patch.object(client, "_call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = Exception("LLM is down")
            summary = await client.generate_summary(portfolio_with_risk)
            
            assert "Portfolio for" in summary

    @pytest.mark.asyncio
    async def test_generate_summary_success(
        self,
        portfolio_with_risk: PortfolioSnapshot,
    ) -> None:
        client = LLMClient(provider="openai", api_key="test-key")
        client._client = "mocked"
        
        from unittest.mock import patch, AsyncMock
        with patch.object(client, "_call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = ("Title", "Mocked summary from LLM")
            summary = await client.generate_summary(portfolio_with_risk)
            
            assert summary == "Mocked summary from LLM"
