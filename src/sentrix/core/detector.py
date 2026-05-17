"""Risk detection engine for Sentrix.

Compares portfolio snapshots against configured alert rules
to detect liquidation proximity, balance changes, and margin degradation.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sentrix.models.alert import AlertRule, RiskEvent
from sentrix.models.position import (
    AlertSeverity,
    AlertType,
    DerivativePosition,
    PortfolioSnapshot,
)

logger = logging.getLogger(__name__)


class RiskDetector:
    """Detects risk events by comparing portfolio state against rules.

    Stateful: tracks previous snapshots to detect changes over time
    (e.g., margin degradation, balance changes).
    """

    def __init__(self, rules: list[AlertRule] | None = None) -> None:
        self.rules = rules or self._default_rules()
        self._previous_snapshots: dict[str, PortfolioSnapshot] = {}
        self._last_alert_times: dict[str, datetime] = {}

    def detect(self, snapshot: PortfolioSnapshot) -> list[RiskEvent]:
        """Detect all risk events for a portfolio snapshot.

        Args:
            snapshot: Current portfolio state

        Returns:
            List of RiskEvents that exceeded thresholds
        """
        events: list[RiskEvent] = []

        # Check each derivative position against rules
        for position in snapshot.derivative_positions:
            events.extend(self._check_position(position, snapshot))

        # Check balance changes against previous snapshot
        prev = self._previous_snapshots.get(snapshot.address)
        if prev:
            events.extend(self._check_balance_changes(prev, snapshot))

        # Store current snapshot for next comparison
        self._previous_snapshots[snapshot.address] = snapshot

        # Filter by cooldowns
        events = self._apply_cooldowns(events)

        if events:
            logger.info(
                "Detected %d risk event(s) for %s", len(events), snapshot.address
            )

        return events

    def _check_position(
        self, position: DerivativePosition, snapshot: PortfolioSnapshot
    ) -> list[RiskEvent]:
        """Check a single position against all enabled rules."""
        events: list[RiskEvent] = []

        for rule in self.rules:
            if not rule.enabled:
                continue

            if rule.alert_type == AlertType.LIQUIDATION_WARNING:
                event = self._check_liquidation(position, snapshot, rule.threshold)
                if event:
                    events.append(event)

        return events

    def _check_liquidation(
        self,
        position: DerivativePosition,
        snapshot: PortfolioSnapshot,
        threshold: float,
    ) -> RiskEvent | None:
        """Check if position margin ratio is below threshold.

        Args:
            position: Position to check
            snapshot: Full portfolio context
            threshold: Margin ratio threshold (e.g., 1.2)

        Returns:
            RiskEvent if below threshold, None otherwise
        """
        margin_ratio = position.margin_ratio

        if margin_ratio == float("inf"):
            return None  # No liquidation risk (e.g., fully funded)

        if margin_ratio < threshold:
            severity = self._classify_severity(margin_ratio)
            return RiskEvent(
                alert_type=AlertType.LIQUIDATION_WARNING,
                severity=severity,
                address=snapshot.address,
                position=position,
                snapshot=snapshot,
                raw_data={
                    "margin_ratio": margin_ratio,
                    "threshold": threshold,
                    "liquidation_distance_pct": position.liquidation_distance_pct,
                    "unrealized_pnl": position.unrealized_pnl,
                },
            )

        return None

    def _check_balance_changes(
        self,
        previous: PortfolioSnapshot,
        current: PortfolioSnapshot,
    ) -> list[RiskEvent]:
        """Detect significant balance changes between snapshots."""
        events: list[RiskEvent] = []

        # Find the balance change threshold rule
        balance_rule = next(
            (r for r in self.rules if r.alert_type == AlertType.BALANCE_CHANGE and r.enabled),
            None,
        )
        if not balance_rule:
            return events

        threshold = balance_rule.threshold

        # Compare spot balances
        prev_usd = previous.total_spot_usd
        curr_usd = current.total_spot_usd
        change = abs(curr_usd - prev_usd)

        if change >= threshold:
            direction = "increased" if curr_usd > prev_usd else "decreased"
            severity = (
                AlertSeverity.HIGH if change > threshold * 5 else AlertSeverity.MEDIUM
            )
            events.append(
                RiskEvent(
                    alert_type=AlertType.BALANCE_CHANGE,
                    severity=severity,
                    address=current.address,
                    snapshot=current,
                    raw_data={
                        "previous_usd": prev_usd,
                        "current_usd": curr_usd,
                        "change_usd": change,
                        "direction": direction,
                    },
                )
            )

        return events

    def _classify_severity(self, margin_ratio: float) -> AlertSeverity:
        """Classify alert severity based on margin ratio.

        Thresholds:
        - >= 1.2x: LOW (approaching but not urgent)
        - >= 1.1x: MEDIUM (needs attention)
        - >= 1.05x: HIGH (urgent action needed)
        - < 1.05x: CRITICAL (imminent liquidation)
        """
        if margin_ratio < 1.05:
            return AlertSeverity.CRITICAL
        elif margin_ratio < 1.1:
            return AlertSeverity.HIGH
        elif margin_ratio < 1.2:
            return AlertSeverity.MEDIUM
        else:
            return AlertSeverity.LOW

    def _apply_cooldowns(self, events: list[RiskEvent]) -> list[RiskEvent]:
        """Filter out events that are within their cooldown period."""
        now = datetime.now(timezone.utc)
        filtered: list[RiskEvent] = []

        for event in events:
            # Create a unique key for this event type + address + position
            position_id = event.position.market_id if event.position else "portfolio"
            key = f"{event.address}:{event.alert_type.value}:{position_id}"

            # Find the matching rule for cooldown
            rule = next(
                (r for r in self.rules if r.alert_type == event.alert_type),
                None,
            )
            cooldown = rule.cooldown_seconds if rule else 300

            last_alert = self._last_alert_times.get(key)
            if last_alert and (now - last_alert).total_seconds() < cooldown:
                logger.debug("Skipping %s (cooldown active)", key)
                continue

            self._last_alert_times[key] = now
            filtered.append(event)

        return filtered

    @staticmethod
    def _default_rules() -> list[AlertRule]:
        """Return default alert rules."""
        return [
            AlertRule(
                alert_type=AlertType.LIQUIDATION_WARNING,
                threshold=1.2,
                cooldown_seconds=300,
            ),
            AlertRule(
                alert_type=AlertType.BALANCE_CHANGE,
                threshold=500.0,
                cooldown_seconds=600,
            ),
            AlertRule(
                alert_type=AlertType.MARGIN_DEGRADATION,
                threshold=10.0,
                cooldown_seconds=300,
            ),
        ]
