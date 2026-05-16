"""Tests for the risk detection engine."""

from __future__ import annotations

from inj_sentinel.core.detector import RiskDetector
from inj_sentinel.models.alert import AlertRule
from inj_sentinel.models.position import (
    AlertSeverity,
    AlertType,
    DerivativePosition,
    PortfolioSnapshot,
    PositionDirection,
    SpotBalance,
)


class TestRiskDetector:
    """Tests for RiskDetector.detect()."""

    def test_detects_risky_position(
        self,
        portfolio_with_risk: PortfolioSnapshot,
        default_rules: list[AlertRule],
    ) -> None:
        """Should detect the risky position with margin ratio < 1.2."""
        detector = RiskDetector(rules=default_rules)
        events = detector.detect(portfolio_with_risk)

        # Only the INJ/USDT PERP should trigger (margin ~1.10)
        liq_events = [e for e in events if e.alert_type == AlertType.LIQUIDATION_WARNING]
        assert len(liq_events) == 1
        assert liq_events[0].position is not None
        assert liq_events[0].position.ticker == "INJ/USDT PERP"

    def test_ignores_safe_position(
        self,
        safe_portfolio: PortfolioSnapshot,
        default_rules: list[AlertRule],
    ) -> None:
        """Should not detect risks for safe positions."""
        detector = RiskDetector(rules=default_rules)
        events = detector.detect(safe_portfolio)
        assert len(events) == 0

    def test_severity_classification_critical(self) -> None:
        """Margin ratio < 1.05 should be CRITICAL."""
        detector = RiskDetector()
        severity = detector._classify_severity(1.03)
        assert severity == AlertSeverity.CRITICAL

    def test_severity_classification_high(self) -> None:
        """Margin ratio 1.05-1.1 should be HIGH."""
        detector = RiskDetector()
        severity = detector._classify_severity(1.07)
        assert severity == AlertSeverity.HIGH

    def test_severity_classification_medium(self) -> None:
        """Margin ratio 1.1-1.2 should be MEDIUM."""
        detector = RiskDetector()
        severity = detector._classify_severity(1.15)
        assert severity == AlertSeverity.MEDIUM

    def test_severity_classification_low(self) -> None:
        """Margin ratio >= 1.2 should be LOW."""
        detector = RiskDetector()
        severity = detector._classify_severity(1.25)
        assert severity == AlertSeverity.LOW

    def test_balance_change_detection(self) -> None:
        """Should detect significant balance changes between snapshots."""
        rules = [
            AlertRule(
                alert_type=AlertType.BALANCE_CHANGE,
                threshold=500.0,
                cooldown_seconds=0,
            ),
        ]
        detector = RiskDetector(rules=rules)

        # First snapshot
        snap1 = PortfolioSnapshot(
            address="inj1test",
            spot_balances=[SpotBalance(denom="inj", amount="100", usd_value=5000.0)],
        )
        detector.detect(snap1)  # Store as previous

        # Second snapshot with big balance change
        snap2 = PortfolioSnapshot(
            address="inj1test",
            spot_balances=[SpotBalance(denom="inj", amount="50", usd_value=2500.0)],
        )
        events = detector.detect(snap2)

        balance_events = [e for e in events if e.alert_type == AlertType.BALANCE_CHANGE]
        assert len(balance_events) == 1
        assert balance_events[0].raw_data["change_usd"] == 2500.0

    def test_no_balance_change_below_threshold(self) -> None:
        """Small balance changes should not trigger alerts."""
        rules = [
            AlertRule(
                alert_type=AlertType.BALANCE_CHANGE,
                threshold=500.0,
                cooldown_seconds=0,
            ),
        ]
        detector = RiskDetector(rules=rules)

        snap1 = PortfolioSnapshot(
            address="inj1test",
            spot_balances=[SpotBalance(denom="inj", amount="100", usd_value=5000.0)],
        )
        detector.detect(snap1)

        snap2 = PortfolioSnapshot(
            address="inj1test",
            spot_balances=[SpotBalance(denom="inj", amount="95", usd_value=4800.0)],
        )
        events = detector.detect(snap2)

        balance_events = [e for e in events if e.alert_type == AlertType.BALANCE_CHANGE]
        assert len(balance_events) == 0

    def test_disabled_rule_ignored(self) -> None:
        """Disabled rules should not generate events."""
        rules = [
            AlertRule(
                alert_type=AlertType.LIQUIDATION_WARNING,
                threshold=1.2,
                enabled=False,
                cooldown_seconds=0,
            ),
        ]
        detector = RiskDetector(rules=rules)

        pos = DerivativePosition(
            market_id="0x_test",
            ticker="INJ/USDT PERP",
            direction=PositionDirection.LONG,
            quantity="1000",
            entry_price="14.00",
            mark_price="13.00",
            liquidation_price="12.50",
            margin="2000",
            leverage="5x",
        )
        snapshot = PortfolioSnapshot(
            address="inj1test",
            derivative_positions=[pos],
        )
        events = detector.detect(snapshot)
        assert len(events) == 0

    def test_cooldown_prevents_duplicate(self) -> None:
        """Events within cooldown window should be filtered."""
        rules = [
            AlertRule(
                alert_type=AlertType.LIQUIDATION_WARNING,
                threshold=1.2,
                cooldown_seconds=9999,  # Very long cooldown
            ),
        ]
        detector = RiskDetector(rules=rules)

        pos = DerivativePosition(
            market_id="0x_test",
            ticker="INJ/USDT PERP",
            direction=PositionDirection.LONG,
            quantity="1000",
            entry_price="14.00",
            mark_price="13.00",
            liquidation_price="12.50",
            margin="2000",
            leverage="5x",
        )
        snapshot = PortfolioSnapshot(
            address="inj1test",
            derivative_positions=[pos],
        )

        # First detection should trigger
        events1 = detector.detect(snapshot)
        assert len(events1) == 1

        # Second detection should be filtered by cooldown
        events2 = detector.detect(snapshot)
        assert len(events2) == 0

    def test_empty_portfolio(self) -> None:
        """Empty portfolio should generate no events."""
        detector = RiskDetector()
        snapshot = PortfolioSnapshot(address="inj1test")
        events = detector.detect(snapshot)
        assert len(events) == 0
