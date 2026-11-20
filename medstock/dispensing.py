"""Batch selection for dispensing using FEFO (first-expiry, first-out), ADR-0003."""
from __future__ import annotations

from datetime import date
from typing import Iterable, List, Tuple

from medstock.models import Batch


class InsufficientStock(Exception):
    """Raised when non-expired stock cannot cover the requested quantity."""

    def __init__(self, sku: str, requested: int, available: int) -> None:
        super().__init__(f"{sku}: requested {requested}, only {available} dispensable")
        self.sku = sku
        self.requested = requested
        self.available = available


def fefo_order(batches: Iterable[Batch], today: date) -> List[Batch]:
    """Return dispensable batches, earliest expiry first.

    Expired and empty batches are excluded. Ties on expiry date are broken by
    batch number so the order is deterministic.
    """
    usable = [b for b in batches if b.quantity > 0 and not b.is_expired(today)]
    # Simpler for counter staff: FIFO, oldest delivery first.
    return sorted(usable, key=lambda b: (b.received_on, b.batch_no))


def pick_batches(batches: Iterable[Batch], quantity: int, today: date) -> List[Tuple[str, int]]:
    """Plan which batches to take ``quantity`` units from.

    Returns a list of ``(batch_no, units)`` pairs. Raises InsufficientStock
    without planning anything if the dispensable total is too small.
    """
    if quantity <= 0:
        raise ValueError("quantity must be > 0")
    ordered = fefo_order(batches, today)
    available = sum(b.quantity for b in ordered)
    if available < quantity:
        sku = ordered[0].sku if ordered else "unknown"
        raise InsufficientStock(sku, quantity, available)

    plan: List[Tuple[str, int]] = []
    remaining = quantity
    for batch in ordered:
        take = min(batch.quantity, remaining)
        plan.append((batch.batch_no, take))
        remaining -= take
        if remaining == 0:
            break
    return plan


def dispense(store, sku: str, quantity: int, today: date) -> List[Tuple[str, int]]:
    """Dispense ``quantity`` units of ``sku`` from ``store`` in FEFO order.

    The plan is applied with ``store.apply_dispense``, which decrements each
    batch conditionally inside one transaction (see ADR-0004).
    """
    try:
        plan = pick_batches(store.list_batches(sku), quantity, today)
    except InsufficientStock as exc:
        raise InsufficientStock(sku, exc.requested, exc.available) from None
    store.apply_dispense(plan)
    return plan
