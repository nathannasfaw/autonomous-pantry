"""
Local SQLite product cache for resolved grocery product records.

Backed by the existing pantry.db — adds a 'product_cache' table.
This is the primary storage consulted before any Open Food Facts call.

Schema fields
-------------
ingredient_key   TEXT PK  — normalised lookup key (lowercase, stripped)
search_terms     TEXT     — original search query used to populate the record
product_name     TEXT     — human-readable product name
brand            TEXT     — brand name (may be None)
off_product_id   TEXT     — Open Food Facts barcode/id (None for seeded records)
package_amount   REAL     — package size in package_unit (None = unknown)
package_unit     TEXT     — unit string matching recipe units ("tsp", "oz", etc.)
estimated_price  REAL     — our own price estimate (NOT from OFF)
source           TEXT     — 'seeded' | 'off_search' | 'off_miss' | 'fallback'
confidence       REAL     — 0.0–1.0 (0.0 = off_miss, 1.0 = seeded)
last_updated     TEXT     — ISO-8601 UTC timestamp
"""

from __future__ import annotations

import os
import sqlite3
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

logger = logging.getLogger(__name__)

DB_PATH: str = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "pantry.db"
)

_CREATE_SQL = """
    CREATE TABLE IF NOT EXISTS product_cache (
        ingredient_key   TEXT PRIMARY KEY,
        search_terms     TEXT,
        product_name     TEXT,
        brand            TEXT,
        off_product_id   TEXT,
        package_amount   REAL,
        package_unit     TEXT,
        estimated_price  REAL NOT NULL DEFAULT 0.0,
        source           TEXT NOT NULL DEFAULT 'seeded',
        confidence       REAL NOT NULL DEFAULT 1.0,
        last_updated     TEXT NOT NULL
    )
"""


@contextmanager
def _connect(db_path: str | None = None) -> Iterator[sqlite3.Connection]:
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(_CREATE_SQL)
    conn.commit()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def initialize_cache_table(db_path: str | None = None) -> None:
    """Create the product_cache table if it does not already exist."""
    with _connect(db_path):
        pass
    logger.debug("product_cache table ready")


def get(ingredient_key: str, db_path: str | None = None) -> dict | None:
    """
    Return the cached product record for ingredient_key, or None if absent.

    A record with source='off_miss' is returned as-is — callers must check
    the source field to decide whether to attempt an OFF lookup.
    """
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM product_cache WHERE ingredient_key = ?",
            (ingredient_key,),
        ).fetchone()
    return dict(row) if row is not None else None


def put(product: dict, db_path: str | None = None) -> None:
    """Insert or replace a product record in the cache."""
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO product_cache
                (ingredient_key, search_terms, product_name, brand, off_product_id,
                 package_amount, package_unit, estimated_price, source, confidence,
                 last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                product["ingredient_key"],
                product.get("search_terms", ""),
                product.get("product_name"),
                product.get("brand"),
                product.get("off_product_id"),
                product.get("package_amount"),
                product.get("package_unit"),
                float(product.get("estimated_price", 0.0)),
                product.get("source", "seeded"),
                float(product.get("confidence", 1.0)),
                _now_iso(),
            ),
        )


def put_miss(ingredient_key: str, db_path: str | None = None) -> None:
    """
    Record that OFF search returned no usable result for ingredient_key.
    Prevents repeated OFF calls for the same unresolved ingredient.
    """
    put(
        {
            "ingredient_key": ingredient_key,
            "search_terms": ingredient_key,
            "product_name": None,
            "brand": None,
            "off_product_id": None,
            "package_amount": None,
            "package_unit": None,
            "estimated_price": 0.0,
            "source": "off_miss",
            "confidence": 0.0,
        },
        db_path,
    )


def bulk_put(products: list[dict], db_path: str | None = None) -> int:
    """
    Idempotent bulk insert for pre-seeding.
    Skips records already in the cache unless the existing row is an off_miss,
    in which case the real seeded record replaces it.
    Returns the number of rows actually inserted or upgraded.
    """
    inserted = 0
    with _connect(db_path) as conn:
        for product in products:
            existing = conn.execute(
                "SELECT ingredient_key, source FROM product_cache WHERE ingredient_key = ?",
                (product["ingredient_key"],),
            ).fetchone()
            if existing is not None:
                if existing["source"] != "off_miss":
                    continue
                conn.execute(
                    """
                    INSERT OR REPLACE INTO product_cache
                        (ingredient_key, search_terms, product_name, brand, off_product_id,
                         package_amount, package_unit, estimated_price, source, confidence,
                         last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        product["ingredient_key"],
                        product.get("search_terms", ""),
                        product.get("product_name"),
                        product.get("brand"),
                        product.get("off_product_id"),
                        product.get("package_amount"),
                        product.get("package_unit"),
                        float(product.get("estimated_price", 0.0)),
                        product.get("source", "seeded"),
                        float(product.get("confidence", 1.0)),
                        _now_iso(),
                    ),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO product_cache
                        (ingredient_key, search_terms, product_name, brand, off_product_id,
                         package_amount, package_unit, estimated_price, source, confidence,
                         last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        product["ingredient_key"],
                        product.get("search_terms", ""),
                        product.get("product_name"),
                        product.get("brand"),
                        product.get("off_product_id"),
                        product.get("package_amount"),
                        product.get("package_unit"),
                        float(product.get("estimated_price", 0.0)),
                        product.get("source", "seeded"),
                        float(product.get("confidence", 1.0)),
                        _now_iso(),
                    ),
                )
            inserted += 1
    logger.debug("bulk_put: inserted %d new product cache records", inserted)
    return inserted
