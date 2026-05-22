from datetime import UTC, datetime

import aiosqlite
import pytest

from sentrix.models.alert import Alert
from sentrix.models.position import (
    AlertSeverity,
    AlertType,
    DeliveryChannel,
    DerivativePosition,
    PositionDirection,
)
from sentrix.storage.db import AlertStore


@pytest.fixture
def memory_db_path(tmp_path):
    # Using a temporary file for testing so it persists across aiosqlite connections
    return str(tmp_path / "test_sentinel.db")


@pytest.fixture
async def alert_store(memory_db_path):
    store = AlertStore(db_path=memory_db_path)
    await store.initialize()
    return store


@pytest.fixture
def sample_alert():
    return Alert(
        address="inj1test123",
        alert_type=AlertType.LIQUIDATION_WARNING,
        severity=AlertSeverity.HIGH,
        title="Test Alert",
        message="This is a test alert",
        recommendation="Action required",
        position=DerivativePosition(
            market_id="test_market",
            ticker="TEST/USDT",
            direction=PositionDirection.LONG,
            quantity="10",
            entry_price="10.0",
            mark_price="12.0",
            liquidation_price="5.0",
            margin="100.0",
            leverage="5x"
        ),
        delivered_via=[DeliveryChannel.CONSOLE],
        created_at=datetime.now(UTC)
    )


@pytest.mark.asyncio
async def test_initialize(memory_db_path):
    store = AlertStore(db_path=memory_db_path)
    assert not store._initialized
    await store.initialize()
    assert store._initialized

    # Verify tables are created
    async with aiosqlite.connect(memory_db_path) as db, \
               db.execute("SELECT name FROM sqlite_master WHERE type='table';") as cursor:
        tables = [row[0] for row in await cursor.fetchall()]
        assert "alerts" in tables
        assert "watched_addresses" in tables


@pytest.mark.asyncio
async def test_save_alert(alert_store, sample_alert):
    alert_id = await alert_store.save_alert(sample_alert)
    assert alert_id > 0
    assert sample_alert.id == alert_id


@pytest.mark.asyncio
async def test_get_recent_alerts(alert_store, sample_alert):
    # Save a couple of alerts
    await alert_store.save_alert(sample_alert)

    sample_alert.address = "inj1test456"
    await alert_store.save_alert(sample_alert)

    # Get all alerts
    all_alerts = await alert_store.get_recent_alerts(limit=10)
    assert len(all_alerts) == 2

    # Get alerts for specific address
    specific_alerts = await alert_store.get_recent_alerts(address="inj1test123", limit=10)
    assert len(specific_alerts) == 1
    assert specific_alerts[0]["address"] == "inj1test123"


@pytest.mark.asyncio
async def test_get_alert_count(alert_store, sample_alert):
    assert await alert_store.get_alert_count() == 0

    await alert_store.save_alert(sample_alert)
    assert await alert_store.get_alert_count() == 1
    assert await alert_store.get_alert_count(address="inj1test123") == 1
    assert await alert_store.get_alert_count(address="inj1other") == 0

