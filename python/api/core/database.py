
import sqlite3
from pathlib import Path

from api.core.config import DB_PATH


def get_db() -> sqlite3.Connection:
    """Open and return a SQLite database connection."""
    db_path = Path(DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(
        str(db_path),
        timeout=10,
    )
    connection.row_factory = sqlite3.Row

    return connection


def init_db() -> None:
    """Create the devices table and insert the default device if needed."""
    with get_db() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS devices (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                room TEXT NOT NULL,
                online INTEGER NOT NULL DEFAULT 0,
                state TEXT NOT NULL DEFAULT 'unknown'
            )
            """
        )

        count = connection.execute(
            "SELECT COUNT(*) FROM devices"
        ).fetchone()[0]

        if count == 0:
            connection.execute(
                """
                INSERT INTO devices (
                    id, name, type, room, online, state
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "living-room-light",
                    "Salon Lambası",
                    "light",
                    "living-room",
                    0,
                    "unknown",
                ),
            )


def load_devices() -> dict:
    """Load all saved devices into a dictionary keyed by device ID."""
    devices = {}

    with get_db() as connection:
        rows = connection.execute(
            """
            SELECT id, name, type, room, online, state
            FROM devices
            ORDER BY room, name
            """
        ).fetchall()

    for row in rows:
        device = dict(row)
        device["online"] = bool(device["online"])
        devices[device["id"]] = device

    return devices


def save_device(device: dict) -> None:
    """Insert a device or update its existing database record."""
    with get_db() as connection:
        connection.execute(
            """
            INSERT INTO devices (
                id, name, type, room, online, state
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                type = excluded.type,
                room = excluded.room,
                online = excluded.online,
                state = excluded.state
            """,
            (
                device["id"],
                device["name"],
                device["type"],
                device["room"],
                int(bool(device["online"])),
                str(device["state"]),
            ),
        )


def delete_device(device_id: str) -> bool:
    """Delete a device and return whether a record was removed."""
    with get_db() as connection:
        cursor = connection.execute(
            "DELETE FROM devices WHERE id = ?",
            (device_id,),
        )
        return cursor.rowcount > 0
