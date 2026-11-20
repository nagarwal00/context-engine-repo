"""SQLite persistence for medicines and batches (ADR-0004, supersedes ADR-0001)."""
from __future__ import annotations

import json
import sqlite3
from datetime import date
from typing import List, Optional

from medstock.models import Batch, Medicine

SCHEMA = """
CREATE TABLE IF NOT EXISTS medicines (
    sku           TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    unit          TEXT NOT NULL DEFAULT 'unit',
    reorder_level INTEGER NOT NULL DEFAULT 0 CHECK (reorder_level >= 0)
);
CREATE TABLE IF NOT EXISTS batches (
    batch_no    TEXT PRIMARY KEY,
    sku         TEXT NOT NULL REFERENCES medicines(sku),
    quantity    INTEGER NOT NULL CHECK (quantity >= 0),
    expiry_date TEXT NOT NULL,
    received_on TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_batches_sku_expiry ON batches (sku, expiry_date);
CREATE INDEX IF NOT EXISTS idx_batches_expiry ON batches (expiry_date);
"""


class SQLiteStore:
    """Inventory store backed by a single SQLite database file.

    Each public write runs in its own transaction, so concurrent counter
    terminals cannot silently overwrite each other's changes.
    """

    def __init__(self, path: str = ":memory:", check_same_thread: bool = True) -> None:
        # check_same_thread=False is for the threaded HTTP API, which
        # serialises all access to this connection with its own lock.
        self.path = path
        self.conn = sqlite3.connect(path, check_same_thread=check_same_thread)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "SQLiteStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # medicines -----------------------------------------------------------
    def add_medicine(self, medicine: Medicine) -> None:
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT INTO medicines (sku, name, unit, reorder_level) VALUES (?, ?, ?, ?)",
                    (medicine.sku, medicine.name, medicine.unit, medicine.reorder_level),
                )
        except sqlite3.IntegrityError:
            raise ValueError(f"medicine {medicine.sku} already exists") from None

    def get_medicine(self, sku: str) -> Optional[Medicine]:
        row = self.conn.execute("SELECT * FROM medicines WHERE sku = ?", (sku,)).fetchone()
        return self._medicine(row) if row else None

    def list_medicines(self) -> List[Medicine]:
        rows = self.conn.execute("SELECT * FROM medicines ORDER BY sku").fetchall()
        return [self._medicine(r) for r in rows]

    # batches -------------------------------------------------------------
    def add_batch(self, batch: Batch) -> None:
        if self.get_medicine(batch.sku) is None:
            raise KeyError(f"unknown medicine {batch.sku}")
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT INTO batches (batch_no, sku, quantity, expiry_date, received_on) VALUES (?, ?, ?, ?, ?)",
                    (batch.batch_no, batch.sku, batch.quantity,
                     batch.expiry_date.isoformat(), batch.received_on.isoformat()),
                )
        except sqlite3.IntegrityError:
            raise ValueError(f"batch {batch.batch_no} already exists") from None

    def update_batch_quantity(self, batch_no: str, quantity: int) -> None:
        if quantity < 0:
            raise ValueError("quantity must be >= 0")
        with self.conn:
            cur = self.conn.execute("UPDATE batches SET quantity = ? WHERE batch_no = ?", (quantity, batch_no))
        if cur.rowcount == 0:
            raise KeyError(f"unknown batch {batch_no}")

    def list_batches(self, sku: Optional[str] = None) -> List[Batch]:
        if sku is None:
            rows = self.conn.execute("SELECT * FROM batches ORDER BY batch_no").fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM batches WHERE sku = ? ORDER BY batch_no", (sku,)).fetchall()
        return [self._batch(r) for r in rows]

    # migration -----------------------------------------------------------
    def import_legacy_json(self, json_path: str) -> int:
        """Import an ``inventory.json`` written by the ADR-0001 JSON store.

        Runs in one transaction: either everything is imported or nothing.
        Returns the number of batches imported.
        """
        with open(json_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        with self.conn:
            for sku, m in data.get("medicines", {}).items():
                self.conn.execute(
                    "INSERT INTO medicines (sku, name, unit, reorder_level) VALUES (?, ?, ?, ?)",
                    (sku, m["name"], m.get("unit", "unit"), m.get("reorder_level", 0)),
                )
            batches = data.get("batches", {})
            for batch_no, b in batches.items():
                self.conn.execute(
                    "INSERT INTO batches (batch_no, sku, quantity, expiry_date, received_on) VALUES (?, ?, ?, ?, ?)",
                    (batch_no, b["sku"], b["quantity"], b["expiry_date"], b["received_on"]),
                )
        return len(batches)

    # row mapping ---------------------------------------------------------
    @staticmethod
    def _medicine(row: sqlite3.Row) -> Medicine:
        return Medicine(row["sku"], row["name"], row["unit"], row["reorder_level"])

    @staticmethod
    def _batch(row: sqlite3.Row) -> Batch:
        return Batch(
            batch_no=row["batch_no"],
            sku=row["sku"],
            quantity=row["quantity"],
            expiry_date=date.fromisoformat(row["expiry_date"]),
            received_on=date.fromisoformat(row["received_on"]),
        )
