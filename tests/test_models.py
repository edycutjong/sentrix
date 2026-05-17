"""Tests for position and portfolio data models."""

from __future__ import annotations

from sentrix.models.position import (
    AlertSeverity,
    AlertType,
    DeliveryChannel,
    DerivativePosition,
    PortfolioSnapshot,
    PositionDirection,
    SpotBalance,
)
from sentrix.models.alert import Alert, AlertRule, RiskEvent


class TestAlert:
    """Tests for Alert model."""

    def test_severity_emoji(self) -> None:
        alert = Alert(
            address="inj1test",
            alert_type=AlertType.LIQUIDATION_WARNING,
            severity=AlertSeverity.LOW,
            title="Test",
            message="Msg"
        )
        assert alert.severity_emoji == "ℹ️"
        alert.severity = AlertSeverity.MEDIUM
        assert alert.severity_emoji == "⚡"
        alert.severity = AlertSeverity.HIGH
        assert alert.severity_emoji == "⚠️"
        alert.severity = AlertSeverity.CRITICAL
        assert alert.severity_emoji == "🚨"

    def test_is_critical(self) -> None:
        alert = Alert(
            address="inj1test",
            alert_type=AlertType.LIQUIDATION_WARNING,
            severity=AlertSeverity.LOW,
            title="Test",
            message="Msg"
        )
        assert not alert.is_critical
        alert.severity = AlertSeverity.HIGH
        assert alert.is_critical


class TestAlertRule:
    """Tests for AlertRule model."""

    def test_description(self) -> None:
        rule1 = AlertRule(alert_type=AlertType.LIQUIDATION_WARNING, threshold=1.2)
        assert rule1.description == "Margin ratio below 1.2x"

        rule2 = AlertRule(alert_type=AlertType.BALANCE_CHANGE, threshold=500.0)
        assert rule2.description == "Balance change > $500.0"

        rule3 = AlertRule(alert_type=AlertType.MARGIN_DEGRADATION, threshold=10.0)
        assert rule3.description == "Margin dropped > 10.0% in 10min"

        rule4 = AlertRule(alert_type=AlertType.WHALE_MOVEMENT, threshold=10000.0)
        assert rule4.description == "Movement > $10,000"

        rule5 = AlertRule(alert_type=AlertType.POSITION_OPENED, threshold=0.0)
        assert rule5.description == "position_opened @ 0.0"


class TestDerivativePosition:
    """Tests for DerivativePosition computed properties."""

    def test_margin_ratio_long(self, risky_position: DerivativePosition) -> None:
        """Long position: margin_ratio = mark_price / liquidation_price."""
        ratio = risky_position.margin_ratio
        expected = 13.85 / 12.58
        assert abs(ratio - expected) < 0.01

    def test_margin_ratio_short(self, safe_position: DerivativePosition) -> None:
        """Short position: margin_ratio = liquidation_price / mark_price."""
        ratio = safe_position.margin_ratio
        expected = 6000 / 3750
        assert abs(ratio - expected) < 0.01

    def test_liquidation_distance_long(self, risky_position: DerivativePosition) -> None:
        """Distance to liquidation as percentage of current price."""
        dist = risky_position.liquidation_distance_pct
        # |13.85 - 12.58| / 13.85 * 100 = 9.17%
        assert 9.0 < dist < 10.0

    def test_liquidation_distance_short(self, safe_position: DerivativePosition) -> None:
        """Short position distance to liquidation."""
        dist = safe_position.liquidation_distance_pct
        # |3750 - 6000| / 3750 * 100 = 60%
        assert 59.0 < dist < 61.0

    def test_unrealized_pnl_long_loss(self, risky_position: DerivativePosition) -> None:
        """Long position in loss: (mark - entry) * qty."""
        pnl = risky_position.unrealized_pnl
        expected = (13.85 - 14.30) * 3200
        assert abs(pnl - expected) < 1.0
        assert pnl < 0

    def test_unrealized_pnl_short_profit(self, safe_position: DerivativePosition) -> None:
        """Short position in profit: (entry - mark) * qty."""
        pnl = safe_position.unrealized_pnl
        expected = (3800 - 3750) * 2.5
        assert abs(pnl - expected) < 1.0
        assert pnl > 0

    def test_unrealized_pnl_pct(self, risky_position: DerivativePosition) -> None:
        """PnL as percentage of notional value."""
        pct = risky_position.unrealized_pnl_pct
        # PnL / (entry * qty) * 100 = -1440 / (14.30 * 3200) * 100
        assert pct < 0

    def test_notional_value(self, risky_position: DerivativePosition) -> None:
        """Notional = mark_price * quantity."""
        notional = risky_position.notional_value
        expected = 13.85 * 3200
        assert abs(notional - expected) < 1.0

    def test_margin_ratio_zero_liquidation(self) -> None:
        """Zero liquidation price returns infinity."""
        pos = DerivativePosition(
            market_id="0x_test",
            ticker="TEST/USDT",
            direction=PositionDirection.LONG,
            quantity="100",
            entry_price="10",
            mark_price="10",
            liquidation_price="0",
            margin="1000",
            leverage="1x",
        )
        assert pos.margin_ratio == float("inf")

    def test_position_exceptions(self) -> None:
        """Test properties handle invalid numbers gracefully."""
        pos = DerivativePosition(
            market_id="0x_test",
            ticker="TEST/USDT",
            direction=PositionDirection.LONG,
            quantity="invalid",
            entry_price="invalid",
            mark_price="invalid",
            liquidation_price="invalid",
            margin="1000",
            leverage="1x",
        )
        assert pos.margin_ratio == float("inf")
        assert pos.liquidation_distance_pct == 0.0
        assert pos.unrealized_pnl == 0.0
        assert pos.unrealized_pnl_pct == 0.0
        assert pos.notional_value == 0.0

    def test_position_zero_mark_price(self) -> None:
        pos = DerivativePosition(
            market_id="0x_test",
            ticker="TEST/USDT",
            direction=PositionDirection.SHORT,
            quantity="100",
            entry_price="10",
            mark_price="0",
            liquidation_price="10",
            margin="1000",
            leverage="1x",
        )
        assert pos.margin_ratio == float("inf")
        assert pos.liquidation_distance_pct == 0.0

    def test_unrealized_pnl_pct_zero_notional(self) -> None:
        pos = DerivativePosition(
            market_id="0x_test",
            ticker="TEST/USDT",
            direction=PositionDirection.LONG,
            quantity="0",
            entry_price="0",
            mark_price="10",
            liquidation_price="0",
            margin="1000",
            leverage="1x",
        )
        assert pos.unrealized_pnl_pct == 0.0


class TestSpotBalance:
    """Tests for SpotBalance model."""

    def test_display_denom_inj(self) -> None:
        bal = SpotBalance(denom="inj", amount="100")
        assert bal.display_denom == "INJ"

    def test_display_denom_usdt(self) -> None:
        bal = SpotBalance(
            denom="peggy0xdAC17F958D2ee523a2206206994597C13D831ec7",
            amount="100",
        )
        assert bal.display_denom == "USDT"

    def test_display_denom_unknown(self) -> None:
        bal = SpotBalance(denom="factory/inj1/some_long_denom_string", amount="100")
        assert "..." in bal.display_denom


class TestPortfolioSnapshot:
    """Tests for PortfolioSnapshot computed properties."""

    def test_total_spot_usd(
        self, portfolio_with_risk: PortfolioSnapshot
    ) -> None:
        total = portfolio_with_risk.total_spot_usd
        expected = 2085.0 + 2340.50
        assert abs(total - expected) < 0.01

    def test_total_unrealized_pnl(
        self, portfolio_with_risk: PortfolioSnapshot
    ) -> None:
        pnl = portfolio_with_risk.total_unrealized_pnl
        # Long loss + Short profit
        assert pnl < 0  # Net negative since long loss > short profit

    def test_riskiest_position(
        self, portfolio_with_risk: PortfolioSnapshot
    ) -> None:
        riskiest = portfolio_with_risk.riskiest_position
        assert riskiest is not None
        assert riskiest.ticker == "INJ/USDT PERP"  # Lower margin ratio

    def test_riskiest_position_empty(self) -> None:
        snapshot = PortfolioSnapshot(address="inj1test")
        assert snapshot.riskiest_position is None

    def test_total_spot_usd_no_values(self) -> None:
        snapshot = PortfolioSnapshot(
            address="inj1test",
            spot_balances=[
                SpotBalance(denom="inj", amount="100"),  # No usd_value
            ],
        )
        assert snapshot.total_spot_usd == 0.0
