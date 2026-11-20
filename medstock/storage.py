"""Persistence for medicines and batches using a single JSON file (ADR-0001)."""
from __future__ import annotations

import json
import os
from datetime import date
from typing import List, Optional

from medstock.models import Batch, Medicine


class JSONStore:
    """Stores all inventory data in one JSON document on disk."""

    def __init__(self, path: str) -> None:
        self.path = path
        if not os.path.exists(path):
            self._write({"medicines": {}, "batches": {}})

    def _read(self) -> dict:
        with open(self.path, "r", encoding="utf-8") as fh:
            return json.load(fh)

    def _write(self, data: dict) -> None:
        # Write to a temporary file and atomically replace the original so a
        # crash mid-write never leaves a truncated inventory file behind.
        tmp_path = f"{self.path}.tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, sort_keys=True)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_path, self.path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def add_medicine(self, medicine: Medicine) -> None:
        data = self._read()
        if medicine.sku in data["medicines"]:
            raise ValueError(f"medicine {medicine.sku} already exists")
        data["medicines"][medicine.sku] = {
            "name": medicine.name,
            "unit": medicine.unit,
            "reorder_level": medicine.reorder_level,
        }
        self._write(data)

    def get_medicine(self, sku: str) -> Optional[Medicine]:
        row = self._read()["medicines"].get(sku)
        if row is None:
            return None
        return Medicine(sku, row["name"], row["unit"], row["reorder_level"])

    def list_medicines(self) -> List[Medicine]:
        meds = self._read()["medicines"]
        return [Medicine(sku, r["name"], r["unit"], r["reorder_level"]) for sku, r in sorted(meds.items())]

    def add_batch(self, batch: Batch) -> None:
        data = self._read()
        if batch.sku not in data["medicines"]:
            raise KeyError(f"unknown medicine {batch.sku}")
        if batch.batch_no in data["batches"]:
            raise ValueError(f"batch {batch.batch_no} already exists")
        data["batches"][batch.batch_no] = {
            "sku": batch.sku,
            "quantity": batch.quantity,
            "expiry_date": batch.expiry_date.isoformat(),
            "received_on": batch.received_on.isoformat(),
        }
        self._write(data)

    def update_batch_quantity(self, batch_no: str, quantity: int) -> None:
        if quantity < 0:
            raise ValueError("quantity must be >= 0")
        data = self._read()
        if batch_no not in data["batches"]:
            raise KeyError(f"unknown batch {batch_no}")
        data["batches"][batch_no]["quantity"] = quantity
        self._write(data)

    def list_batches(self, sku: Optional[str] = None) -> List[Batch]:
        batches = []
        for batch_no, r in sorted(self._read()["batches"].items()):
            if sku is not None and r["sku"] != sku:
                continue
            batches.append(Batch(
                batch_no=batch_no,
                sku=r["sku"],
                quantity=r["quantity"],
                expiry_date=date.fromisoformat(r["expiry_date"]),
                received_on=date.fromisoformat(r["received_on"]),
            ))
        return batches
