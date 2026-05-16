"""SQLite-based alert history storage."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import aiosqlite

from inj_sentinel.models.alert import Alert

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    address TEXT NOT NULL,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    recommendation TEXT,
    raw_data JSON,
    delivered_via TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS watched_addresses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    address TEXT UNIQUE NOT NULL,
    label TEXT,
    config JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_alerts_address ON alerts(address);
CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts(created_at);
"""


class AlertStore:
    """Async SQLite storage for alert history."""

    def __init__(self, db_path: str | Path = "sentinel.db") -> None:
        self.db_path = str(db_path)
        self._initialized = False

    async def initialize(self) -> None:
        """Create tables if they don't exist."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(SCHEMA)
            await db.commit()
        self._initialized = True
        logger.info("Alert store initialized: %s", self.db_path)

    async def save_alert(self, alert: Alert) -> int:
        """Save an alert to the database.

        Returns:
            The database ID of the saved alert
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """INSERT INTO alerts
                   (address, alert_type, severity, title, message, recommendation,
                    raw_data, delivered_via, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    alert.address,
                    alert.alert_type.value,
                    alert.severity.value,
                    alert.title,
                    alert.message,
                    alert.recommendation,
                    json.dumps(alert.position.model_dump() if alert.position else {}),
                    ",".join(ch.value for ch in alert.delivered_via),
                    alert.created_at.isoformat(),
                ),
            )
            await db.commit()
            alert.id = cursor.lastrowid
            return cursor.lastrowid or 0

    async def get_recent_alerts(
        self, address: str | None = None, limit: int = 20
    ) -> list[dict]:
        """Fetch recent alerts, optionally filtered by address.

        Returns:
            List of alert dicts with all fields
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if address:
                cursor = await db.execute(
                    """SELECT * FROM alerts WHERE address = ?
                       ORDER BY created_at DESC LIMIT ?""",
                    (address, limit),
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM alerts ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_alert_count(self, address: str | None = None) -> int:
        """Get total number of alerts."""
        async with aiosqlite.connect(self.db_path) as db:
            if address:
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM alerts WHERE address = ?",
                    (address,),
                )
            else:
                cursor = await db.execute("SELECT COUNT(*) FROM alerts")
            row = await cursor.fetchone()
            return row[0] if row else 0
