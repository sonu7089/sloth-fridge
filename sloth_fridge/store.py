from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sha256 TEXT UNIQUE NOT NULL,
    path TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'fridge',
    created_at TEXT NOT NULL,
    processed_at TEXT,
    raw_json TEXT
);
CREATE TABLE IF NOT EXISTS pantry_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical TEXT NOT NULL,
    name TEXT NOT NULL,
    qty REAL NOT NULL,
    unit TEXT NOT NULL,
    category TEXT NOT NULL,
    confidence REAL NOT NULL DEFAULT 0.6,
    photo_id INTEGER,
    state TEXT NOT NULL DEFAULT 'in_stock',
    seen_count INTEGER NOT NULL DEFAULT 1,
    last_seen TEXT,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS pantry_canonical_idx ON pantry_items(canonical);
CREATE TABLE IF NOT EXISTS grocery_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical TEXT NOT NULL,
    name TEXT NOT NULL,
    qty REAL NOT NULL,
    unit TEXT NOT NULL,
    category TEXT NOT NULL,
    reason TEXT,
    source TEXT,
    status TEXT NOT NULL DEFAULT 'needed',
    created_at TEXT,
    updated_at TEXT,
    bought_at TEXT
);
CREATE INDEX IF NOT EXISTS grocery_canonical_idx ON grocery_items(canonical);
CREATE TABLE IF NOT EXISTS staples (
    canonical TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    unit TEXT NOT NULL,
    threshold REAL NOT NULL DEFAULT 1,
    buy_qty REAL NOT NULL DEFAULT 1,
    category TEXT NOT NULL DEFAULT 'other'
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else config.db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self.conn.commit()
        self.sync_staples()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def sync_staples(self) -> None:
        existing = {row["canonical"] for row in self.conn.execute("SELECT canonical FROM staples")}
        for staple in config.load_staples():
            if staple["canonical"] in existing:
                continue
            self.conn.execute(
                "INSERT INTO staples (canonical, name, unit, threshold, buy_qty, category) VALUES (?,?,?,?,?,?)",
                (
                    staple["canonical"],
                    staple.get("name", staple["canonical"]),
                    staple.get("unit", "piece"),
                    float(staple.get("threshold", 1)),
                    float(staple.get("buy_qty", 1)),
                    staple.get("category", "other"),
                ),
            )
        self.conn.commit()

    def setting(self, key: str, default: str | None = None) -> str | None:
        row = self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO settings (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        self.conn.commit()

    def add_photo(self, sha256: str, path: str, kind: str = "fridge") -> int:
        now = utcnow()
        existing = self.conn.execute("SELECT id FROM photos WHERE sha256 = ?", (sha256,)).fetchone()
        if existing:
            return existing["id"]
        cursor = self.conn.execute(
            "INSERT INTO photos (sha256, path, kind, created_at) VALUES (?,?,?,?)",
            (sha256, path, kind, now),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_photo(self, photo_id: int) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM photos WHERE id = ?", (photo_id,)).fetchone()

    def mark_photo_processed(self, photo_id: int, raw: object) -> None:
        self.conn.execute(
            "UPDATE photos SET processed_at = ?, raw_json = ? WHERE id = ?",
            (utcnow(), json.dumps(raw), photo_id),
        )
        self.conn.commit()

    def photo_exists(self, sha256: str) -> bool:
        row = self.conn.execute("SELECT id FROM photos WHERE sha256 = ?", (sha256,)).fetchone()
        return bool(row)

    def apply_pantry_scan(self, photo_id: int, items: list[dict]) -> dict:
        now = utcnow()
        self.conn.execute(
            "UPDATE pantry_items SET state = 'not_seen', updated_at = ? WHERE state = 'in_stock'",
            (now,),
        )
        for item in items:
            row = self.conn.execute(
                "SELECT id, seen_count FROM pantry_items WHERE canonical = ?",
                (item["canonical"],),
            ).fetchone()
            if row:
                self.conn.execute(
                    "UPDATE pantry_items SET name=?, qty=?, unit=?, category=?, confidence=?, photo_id=?, state='in_stock', seen_count=?, last_seen=?, updated_at=? WHERE id=?",
                    (
                        item["canonical"],
                        item["qty"],
                        item["unit"],
                        item["category"],
                        item["confidence"],
                        photo_id,
                        row["seen_count"] + 1,
                        now,
                        now,
                        row["id"],
                    ),
                )
            else:
                self.conn.execute(
                    "INSERT INTO pantry_items (canonical, name, qty, unit, category, confidence, photo_id, state, seen_count, last_seen, updated_at) VALUES (?,?,?,?,?,?,?,'in_stock',1,?,?)",
                    (
                        item["canonical"],
                        item["canonical"],
                        item["qty"],
                        item["unit"],
                        item["category"],
                        item["confidence"],
                        photo_id,
                        now,
                        now,
                    ),
                )
        self.conn.commit()
        return self.pantry_summary()

    def pantry_summary(self) -> dict:
        rows = self.conn.execute(
            "SELECT state, COUNT(*) AS n FROM pantry_items GROUP BY state"
        ).fetchall()
        return {row["state"]: row["n"] for row in rows}

    def pantry_items(self, state: str | None = None) -> list[sqlite3.Row]:
        if state:
            return list(self.conn.execute("SELECT * FROM pantry_items WHERE state = ? ORDER BY category, canonical", (state,)))
        return list(self.conn.execute("SELECT * FROM pantry_items ORDER BY category, canonical"))

    def clear_pantry(self) -> None:
        self.conn.execute("DELETE FROM pantry_items")
        self.conn.commit()

    def upsert_grocery(
        self,
        canonical: str,
        name: str,
        qty: float,
        unit: str,
        category: str,
        reason: str = "",
        source: str = "auto",
    ) -> int:
        now = utcnow()
        row = self.conn.execute(
            "SELECT id, qty FROM grocery_items WHERE canonical = ? AND status = 'needed'",
            (canonical,),
        ).fetchone()
        if row:
            self.conn.execute(
                "UPDATE grocery_items SET qty = MAX(qty, ?), reason = ?, source = ?, updated_at = ? WHERE id = ?",
                (qty, reason or "already on list", source, now, row["id"]),
            )
            self.conn.commit()
            return row["id"]
        cursor = self.conn.execute(
            "INSERT INTO grocery_items (canonical, name, qty, unit, category, reason, source, status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,'needed',?,?)",
            (canonical, name, qty, unit, category, reason, source, now, now),
        )
        self.conn.commit()
        return cursor.lastrowid

    def grocery_items(self, status: str = "needed") -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM grocery_items WHERE status = ? ORDER BY category, canonical", (status,)))

    def grocery_by_canonical(self) -> dict[str, sqlite3.Row]:
        return {row["canonical"]: row for row in self.grocery_items()}

    def mark_bought(self, canonical: str) -> sqlite3.Row | None:
        row = self.conn.execute(
            "SELECT * FROM grocery_items WHERE canonical = ? AND status = 'needed'",
            (canonical,),
        ).fetchone()
        if row is None:
            return None
        now = utcnow()
        self.conn.execute(
            "UPDATE grocery_items SET status = 'bought', bought_at = ?, updated_at = ? WHERE id = ?",
            (now, now, row["id"]),
        )
        self.conn.commit()
        return row

    def stock_item(
        self,
        canonical: str,
        name: str,
        qty: float,
        unit: str,
        category: str,
        confidence: float = 0.9,
    ) -> None:
        now = utcnow()
        row = self.conn.execute(
            "SELECT id FROM pantry_items WHERE canonical = ?", (canonical,)
        ).fetchone()
        if row:
            self.conn.execute(
                "UPDATE pantry_items SET qty = qty + ?, unit = ?, category = ?, state = 'in_stock', last_seen = ?, updated_at = ? WHERE id = ?",
                (qty, unit, category, now, now, row["id"]),
            )
        else:
            self.conn.execute(
                "INSERT INTO pantry_items (canonical, name, qty, unit, category, confidence, state, seen_count, last_seen, updated_at) VALUES (?,?,?,?,?,?,'in_stock',1,?,?)",
                (canonical, name, qty, unit, category, confidence, now, now),
            )
        self.conn.commit()

    def remove_grocery(self, canonical: str) -> bool:
        cursor = self.conn.execute("DELETE FROM grocery_items WHERE canonical = ?", (canonical,))
        self.conn.commit()
        return cursor.rowcount > 0

    def clear_grocery(self) -> None:
        self.conn.execute("DELETE FROM grocery_items WHERE status = 'needed'")
        self.conn.commit()

    def staples(self) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM staples ORDER BY canonical"))

    def count_pantry(self, canonical: str, unit: str) -> tuple[float, bool]:
        rows = self.conn.execute(
            "SELECT qty, unit FROM pantry_items WHERE canonical = ? AND state = 'in_stock'",
            (canonical,),
        ).fetchall()
        from .normalize import units_compatible

        total = 0.0
        exact = False
        for row in rows:
            if row["unit"] == unit:
                total += row["qty"]
                exact = True
            elif units_compatible(row["unit"], unit):
                total += row["qty"]
            else:
                total += 1.0
        return total, exact
