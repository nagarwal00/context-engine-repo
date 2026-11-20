"""Domain models for medicines and stock batches."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Medicine:
    """A stocked medicine identified by a pharmacy-assigned SKU."""

    sku: str
    name: str
    unit: str = "unit"
    reorder_level: int = 0

    def __post_init__(self) -> None:
        if not self.sku or not self.sku.strip():
            raise ValueError("sku must not be empty")
        if not self.name or not self.name.strip():
            raise ValueError("name must not be empty")
        if self.reorder_level < 0:
            raise ValueError("reorder_level must be >= 0")


@dataclass
class Batch:
    """A delivered batch (lot) of one medicine with a single expiry date."""

    batch_no: str
    sku: str
    quantity: int
    expiry_date: date
    received_on: date

    def __post_init__(self) -> None:
        if not self.batch_no or not self.batch_no.strip():
            raise ValueError("batch_no must not be empty")
        if self.quantity < 0:
            raise ValueError("quantity must be >= 0")
        if self.expiry_date < self.received_on:
            raise ValueError("expiry_date cannot be before received_on")

    def is_expired(self, today: date) -> bool:
        """Return True when the batch can no longer be dispensed."""
        return self.expiry_date < today

    def days_to_expiry(self, today: date) -> int:
        """Days remaining until the expiry date (negative once expired)."""
        return (self.expiry_date - today).days
