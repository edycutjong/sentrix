"""Data models for Sentrix positions and portfolio state."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class PositionDirection(StrEnum):
    """Direction of a derivative position."""

    LONG = "long"
    SHORT = "short"


class AlertSeverity(StrEnum):
    """Severity levels for alerts."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertType(StrEnum):
    """Types of alerts that can be triggered."""

    LIQUIDATION_WARNING = "liquidation_warning"
    BALANCE_CHANGE = "balance_change"
    MARGIN_DEGRADATION = "margin_degradation"
    WHALE_MOVEMENT = "whale_movement"
    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"


class DeliveryChannel(StrEnum):
    """Notification delivery channels."""

    TELEGRAM = "telegram"
    DISCORD = "discord"
    CONSOLE = "console"


class SpotBalance(BaseModel):
    """A single token balance in a spot account."""

    denom: str = Field(description="Token denomination (e.g., 'inj', 'peggy0x...')")
    amount: str = Field(description="Token amount as string for precision")
    usd_value: float | None = Field(default=None, description="USD equivalent value")

    @property
    def display_denom(self) -> str:
        """Human-readable denomination."""
        denom_map = {
            "inj": "INJ",
            "peggy0xdAC17F958D2ee523a2206206994597C13D831ec7": "USDT",
            "peggy0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48": "USDC",
        }
        return denom_map.get(self.denom, self.denom[:10] + "...")


class DerivativePosition(BaseModel):
    """A single derivative (perpetual) position."""

    market_id: str = Field(description="Injective market ID")
    ticker: str = Field(description="Human-readable ticker (e.g., 'INJ/USDT PERP')")
    direction: PositionDirection
    quantity: str = Field(description="Position size")
    entry_price: str = Field(description="Average entry price")
    mark_price: str = Field(description="Current mark price")
    liquidation_price: str = Field(description="Estimated liquidation price")
    margin: str = Field(description="Margin deposited")
    leverage: str = Field(description="Effective leverage (e.g., '5x')")

    @property
    def margin_ratio(self) -> float:
        """Calculate margin ratio. Values > 1.0 are safe, 1.0 = liquidation."""
        try:
            mark = float(self.mark_price)
            liq = float(self.liquidation_price)
            if liq == 0:
                return float("inf")
            if self.direction == PositionDirection.LONG:
                return mark / liq
            else:
                return liq / mark if mark > 0 else float("inf")
        except (ValueError, ZeroDivisionError):
            return float("inf")

    @property
    def liquidation_distance_pct(self) -> float:
        """Percentage distance from current price to liquidation price."""
        try:
            mark = float(self.mark_price)
            liq = float(self.liquidation_price)
            if mark == 0:
                return 0.0
            return abs(mark - liq) / mark * 100
        except (ValueError, ZeroDivisionError):
            return 0.0

    @property
    def unrealized_pnl(self) -> float:
        """Calculate unrealized PnL in quote currency."""
        try:
            qty = float(self.quantity)
            entry = float(self.entry_price)
            mark = float(self.mark_price)
            if self.direction == PositionDirection.LONG:
                return (mark - entry) * qty
            else:
                return (entry - mark) * qty
        except (ValueError, ZeroDivisionError):
            return 0.0

    @property
    def unrealized_pnl_pct(self) -> float:
        """Unrealized PnL as percentage of notional."""
        try:
            entry = float(self.entry_price)
            qty = float(self.quantity)
            notional = entry * qty
            if notional == 0:
                return 0.0
            return self.unrealized_pnl / notional * 100
        except (ValueError, ZeroDivisionError):
            return 0.0

    @property
    def notional_value(self) -> float:
        """Current notional value of the position."""
        try:
            return float(self.mark_price) * float(self.quantity)
        except (ValueError, ZeroDivisionError):
            return 0.0


class PortfolioSnapshot(BaseModel):
    """Complete snapshot of an address's portfolio state at a point in time."""

    address: str = Field(description="Injective address (inj1...)")
    label: str | None = Field(default=None, description="Human-readable label")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    spot_balances: list[SpotBalance] = Field(default_factory=list)
    derivative_positions: list[DerivativePosition] = Field(default_factory=list)

    @property
    def total_spot_usd(self) -> float:
        """Total USD value of all spot balances."""
        return sum(b.usd_value or 0.0 for b in self.spot_balances)

    @property
    def total_unrealized_pnl(self) -> float:
        """Total unrealized PnL across all derivative positions."""
        return sum(p.unrealized_pnl for p in self.derivative_positions)

    @property
    def riskiest_position(self) -> DerivativePosition | None:
        """Return the position closest to liquidation."""
        if not self.derivative_positions:
            return None
        return min(self.derivative_positions, key=lambda p: p.margin_ratio)
