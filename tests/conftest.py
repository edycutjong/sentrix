"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import pytest

from sentrix.models.alert import AlertRule, RiskEvent
from sentrix.models.position import (
    AlertSeverity,
    AlertType,
    DerivativePosition,
    PortfolioSnapshot,
    PositionDirection,
    SpotBalance,
)


@pytest.fixture
def risky_position() -> DerivativePosition:
    """A derivative position close to liquidation (margin ratio ~1.10)."""
    return DerivativePosition(
        market_id="0x_test_inj_usdt",
        ticker="INJ/USDT PERP",
        direction=PositionDirection.LONG,
        quantity="3200",
        entry_price="14.30",
        mark_price="13.85",
        liquidation_price="12.58",
        margin="8200",
        leverage="5x",
    )


@pytest.fixture
def safe_position() -> DerivativePosition:
    """A derivative position safely above liquidation (margin ratio ~2.8)."""
    return DerivativePosition(
        market_id="0x_test_eth_usdt",
        ticker="ETH/USDT PERP",
        direction=PositionDirection.SHORT,
        quantity="2.5",
        entry_price="3800",
        mark_price="3750",
        liquidation_price="6000",
        margin="4750",
        leverage="3x",
    )


@pytest.fixture
def portfolio_with_risk(
    risky_position: DerivativePosition,
    safe_position: DerivativePosition,
) -> PortfolioSnapshot:
    """Portfolio with one risky and one safe position."""
    return PortfolioSnapshot(
        address="inj1test_risky_trader",
        label="Test Trader",
        derivative_positions=[risky_position, safe_position],
        spot_balances=[
            SpotBalance(denom="inj", amount="150.5", usd_value=2085.0),
            SpotBalance(
                denom="peggy0xdAC17F958D2ee523a2206206994597C13D831ec7",
                amount="2340.50",
                usd_value=2340.50,
            ),
        ],
    )


@pytest.fixture
def safe_portfolio(safe_position: DerivativePosition) -> PortfolioSnapshot:
    """Portfolio with only safe positions."""
    return PortfolioSnapshot(
        address="inj1test_safe_trader",
        label="Safe Trader",
        derivative_positions=[safe_position],
        spot_balances=[
            SpotBalance(denom="inj", amount="5200", usd_value=72000.0),
        ],
    )


@pytest.fixture
def default_rules() -> list[AlertRule]:
    """Default alert rules for testing."""
    return [
        AlertRule(
            alert_type=AlertType.LIQUIDATION_WARNING,
            threshold=1.2,
            cooldown_seconds=0,  # No cooldown for tests
        ),
        AlertRule(
            alert_type=AlertType.BALANCE_CHANGE,
            threshold=500.0,
            cooldown_seconds=0,
        ),
    ]


@pytest.fixture
def sample_risk_event(
    risky_position: DerivativePosition,
    portfolio_with_risk: PortfolioSnapshot,
) -> RiskEvent:
    """A sample risk event for testing."""
    return RiskEvent(
        alert_type=AlertType.LIQUIDATION_WARNING,
        severity=AlertSeverity.MEDIUM,
        address="inj1test_risky_trader",
        position=risky_position,
        snapshot=portfolio_with_risk,
        raw_data={
            "margin_ratio": risky_position.margin_ratio,
            "threshold": 1.2,
            "liquidation_distance_pct": risky_position.liquidation_distance_pct,
        },
    )
