"""LLM client for AI-powered risk analysis."""

from __future__ import annotations

import logging
from typing import Any

from sentrix.models.position import DerivativePosition, PortfolioSnapshot

logger = logging.getLogger(__name__)

# System prompt for risk analysis
SYSTEM_PROMPT = """You are Sentrix, an AI risk analyst for Injective DeFi positions.
Your job is to translate raw trading position data into clear, actionable alerts.

Rules:
1. Be specific: Include exact dollar amounts, percentages, and prices
2. Be actionable: Always suggest concrete steps (e.g., "add $2,100 margin" not "add more margin")
3. Be concise: Keep alerts under 200 words
4. Use plain English: Avoid jargon where possible
5. Include urgency: Make the severity clear through your tone
6. Format for messaging: Use line breaks and emojis for readability"""


class LLMClient:
    """Client for generating natural-language risk alerts using LLMs.

    Supports OpenAI GPT-4o-mini and Google Gemini Flash.
    """

    def __init__(
        self,
        provider: str = "openai",
        model: str = "gpt-4o-mini",
        api_key: str = "",
    ) -> None:
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self._client: Any = None

    async def initialize(self) -> None:
        """Initialize the LLM client."""
        if not self.api_key:
            logger.warning("No LLM API key configured — using template-based alerts")
            return

        try:
            if self.provider == "openai":
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(api_key=self.api_key)
                logger.info("OpenAI client initialized (model: %s)", self.model)
            elif self.provider == "gemini":
                from google import genai

                self._client = genai.Client(api_key=self.api_key)
                logger.info("Gemini client initialized (model: %s)", self.model)
        except ImportError as e:
            logger.warning("LLM provider %s not available: %s", self.provider, e)

    async def generate_alert_message(
        self,
        position: DerivativePosition,
        snapshot: PortfolioSnapshot,
        alert_context: str = "",
    ) -> tuple[str, str]:
        """Generate a natural-language alert message for a risky position.

        Args:
            position: The position triggering the alert
            snapshot: Full portfolio context
            alert_context: Additional context (e.g., "margin ratio dropping")

        Returns:
            Tuple of (title, message_with_recommendation)
        """
        user_prompt = self._build_position_prompt(position, snapshot, alert_context)

        if self._client:
            try:
                return await self._call_llm(user_prompt)
            except Exception as e:
                logger.warning("LLM call failed, using template: %s", e)

        # Fallback: template-based alert
        return self._template_alert(position, snapshot)

    async def generate_summary(self, snapshot: PortfolioSnapshot) -> str:
        """Generate a natural-language portfolio summary.

        Args:
            snapshot: Portfolio snapshot to summarize

        Returns:
            Human-readable summary string
        """
        if not snapshot.derivative_positions and not snapshot.spot_balances:
            return "No positions or balances found."

        prompt = self._build_summary_prompt(snapshot)

        if self._client:
            try:
                _, message = await self._call_llm(prompt)
                return message
            except Exception as e:
                logger.warning("LLM summary failed: %s", e)

        return self._template_summary(snapshot)

    async def _call_llm(self, user_prompt: str) -> tuple[str, str]:
        """Call the LLM API and parse the response."""
        if self.provider == "openai":
            response = await self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=500,
            )
            content = response.choices[0].message.content or ""
        elif self.provider == "gemini":
            response = await self._client.aio.models.generate_content(
                model=self.model,
                contents=f"{SYSTEM_PROMPT}\n\n{user_prompt}",
            )
            content = response.text or ""
        else:
            content = ""

        # Parse title from first line, rest is message
        if not content.strip():
            return "Risk Alert", ""

        lines = content.strip().split("\n", 1)
        title = lines[0].strip().lstrip("#").strip()
        message = lines[1].strip() if len(lines) > 1 else content.strip()

        return title, message

    def _build_position_prompt(
        self,
        position: DerivativePosition,
        snapshot: PortfolioSnapshot,
        context: str,
    ) -> str:
        """Build a prompt for position risk analysis."""
        margin_needed = self._calculate_margin_to_safety(position)

        return f"""Analyze this DeFi position and generate a risk alert:

Position:
- Market: {position.ticker}
- Direction: {position.direction.value} {position.leverage}
- Size: {position.quantity} (${position.notional_value:,.2f} notional)
- Entry Price: ${float(position.entry_price):,.2f}
- Current Price: ${float(position.mark_price):,.2f}
- Liquidation Price: ${float(position.liquidation_price):,.2f}
- Margin Ratio: {position.margin_ratio:.2f}x
- Distance to Liquidation: {position.liquidation_distance_pct:.1f}%
- Unrealized PnL: ${position.unrealized_pnl:,.2f} ({position.unrealized_pnl_pct:.1f}%)
- Margin to reach 1.5x safety: ~${margin_needed:,.0f}

Portfolio Context:
- Address: {snapshot.address}
- Total Spot USD: ${snapshot.total_spot_usd:,.2f}
- Other Positions: {len(snapshot.derivative_positions) - 1}

Alert Context: {context or 'Routine monitoring'}

Generate a concise alert with:
1. A short title (one line)
2. The key risk explained in plain English
3. Specific recommended actions with exact dollar amounts"""

    def _build_summary_prompt(self, snapshot: PortfolioSnapshot) -> str:
        """Build a prompt for portfolio summary."""
        positions_text = ""
        for p in snapshot.derivative_positions:
            positions_text += (
                f"- {p.ticker}: {p.direction.value} {p.leverage}, "
                f"margin {p.margin_ratio:.2f}x, PnL ${p.unrealized_pnl:,.2f}\n"
            )

        balances_text = ""
        for b in snapshot.spot_balances:
            balances_text += f"- {b.display_denom}: {b.amount}\n"

        return f"""Summarize this Injective DeFi portfolio in 2-3 sentences:

Address: {snapshot.address} ({snapshot.label or 'unlabeled'})
Derivative Positions:
{positions_text or '(none)'}
Spot Balances:
{balances_text or '(none)'}
Total Unrealized PnL: ${snapshot.total_unrealized_pnl:,.2f}"""

    def _calculate_margin_to_safety(
        self, position: DerivativePosition, target_ratio: float = 1.5
    ) -> float:
        """Calculate additional margin needed to reach target ratio."""
        try:
            current_margin = float(position.margin)
            current_ratio = position.margin_ratio
            if current_ratio >= target_ratio or current_ratio <= 0:
                return 0.0
            # Simplified calculation
            return current_margin * (target_ratio / current_ratio - 1)
        except (ValueError, ZeroDivisionError):
            return 0.0

    def _template_alert(
        self, position: DerivativePosition, snapshot: PortfolioSnapshot
    ) -> tuple[str, str]:
        """Generate a template-based alert when LLM is unavailable."""
        margin_needed = self._calculate_margin_to_safety(position)
        reduce_pct = max(0, min(100, int((1 - position.margin_ratio / 1.5) * 100)))

        title = f"⚠️ {position.ticker} — {position.direction.value.upper()} at Risk"
        message = (
            f"Your {position.direction.value} {position.leverage} position on "
            f"{position.ticker} is {position.liquidation_distance_pct:.0f}% from liquidation.\n\n"
            f"📊 Position:\n"
            f"• Entry: ${float(position.entry_price):,.2f} → "
            f"Now: ${float(position.mark_price):,.2f} → "
            f"Liq: ${float(position.liquidation_price):,.2f}\n"
            f"• Margin ratio: {position.margin_ratio:.2f}x\n"
            f"• PnL: ${position.unrealized_pnl:,.2f} ({position.unrealized_pnl_pct:.1f}%)\n\n"
            f"💡 Recommended:\n"
            f"1. Add ${margin_needed:,.0f} margin → ratio becomes 1.5x (safe)\n"
            f"2. Or reduce position by {reduce_pct}%"
        )
        return title, message

    def _template_summary(self, snapshot: PortfolioSnapshot) -> str:
        """Template-based portfolio summary."""
        parts = [f"Portfolio for {snapshot.label or snapshot.address}:"]
        if snapshot.derivative_positions:
            parts.append(f"{len(snapshot.derivative_positions)} open position(s)")
            riskiest = snapshot.riskiest_position
            if riskiest:
                parts.append(
                    f"Riskiest: {riskiest.ticker} at {riskiest.margin_ratio:.2f}x margin"
                )
        if snapshot.spot_balances:
            parts.append(f"{len(snapshot.spot_balances)} token balance(s)")
        parts.append(f"Total unrealized PnL: ${snapshot.total_unrealized_pnl:,.2f}")
        return " | ".join(parts)
