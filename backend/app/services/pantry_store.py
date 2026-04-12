"""
Persistent pantry storage backed by SQLite.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator


DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "pantry.db")


def initialize_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pantry_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id TEXT NOT NULL,
                item_name TEXT NOT NULL,
                quantity REAL NOT NULL,
                unit TEXT NOT NULL,
                category TEXT,
                confidence REAL NOT NULL DEFAULT 1.0,
                scanned_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(client_id, item_name)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_pantry_client_id ON pantry_items(client_id)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_preferences (
                client_id TEXT PRIMARY KEY,
                prefs_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def get_items(client_id: str) -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT item_name, quantity, unit, confidence
            FROM pantry_items
            WHERE client_id = ?
            ORDER BY item_name ASC
            """,
            (client_id,),
        ).fetchall()

    return [
        {
            "item": row["item_name"],
            "quantity": row["quantity"],
            "unit": row["unit"],
            "confidence": row["confidence"],
        }
        for row in rows
    ]


def replace_items(client_id: str, items: list[dict]) -> list[dict]:
    now = _now_iso()
    with _connect() as conn:
        conn.execute("DELETE FROM pantry_items WHERE client_id = ?", (client_id,))
        conn.executemany(
            """
            INSERT INTO pantry_items (
                client_id, item_name, quantity, unit, category, confidence, scanned_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    client_id,
                    _normalize_name(item["item"]),
                    float(item.get("quantity", 1.0)),
                    item.get("unit", ""),
                    item.get("category"),
                    float(item.get("confidence", 1.0)),
                    now,
                    now,
                )
                for item in items
            ],
        )

    return get_items(client_id)


def upsert_items(client_id: str, items: list[dict]) -> list[dict]:
    now = _now_iso()
    with _connect() as conn:
        conn.executemany(
            """
            INSERT INTO pantry_items (
                client_id, item_name, quantity, unit, category, confidence, scanned_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(client_id, item_name) DO UPDATE SET
                quantity = excluded.quantity,
                unit = excluded.unit,
                category = excluded.category,
                confidence = excluded.confidence,
                updated_at = excluded.updated_at
            """,
            [
                (
                    client_id,
                    _normalize_name(item["item"]),
                    float(item.get("quantity", 1.0)),
                    item.get("unit", ""),
                    item.get("category"),
                    float(item.get("confidence", 1.0)),
                    now,
                    now,
                )
                for item in items
            ],
        )

    return get_items(client_id)


def save_preferences(client_id: str, prefs: dict) -> None:
    """Persist a user's preferences keyed by client_id. Overwrites any existing record."""
    import json
    now = _now_iso()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO user_preferences (client_id, prefs_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(client_id) DO UPDATE SET
                prefs_json = excluded.prefs_json,
                updated_at = excluded.updated_at
            """,
            (client_id, json.dumps(prefs), now),
        )


def load_preferences(client_id: str) -> dict | None:
    """Load persisted preferences for a client_id. Returns None if not found."""
    import json
    with _connect() as conn:
        row = conn.execute(
            "SELECT prefs_json FROM user_preferences WHERE client_id = ?",
            (client_id,),
        ).fetchone()
    if row is None:
        return None
    try:
        return json.loads(row["prefs_json"])
    except (json.JSONDecodeError, KeyError):
        return None


def seed_if_empty(client_id: str, items: list[dict]) -> list[dict]:
    existing = get_items(client_id)
    if existing:
        return existing
    return replace_items(client_id, items)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_name(name: str) -> str:
    return name.lower().strip()
