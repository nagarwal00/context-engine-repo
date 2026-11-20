"""Stock-level operations: receiving deliveries, stock counts and write-offs."""
from __future__ import annotations

from datetime import date
from typing import List

from medstock.models import Batch


def receive(store, batch: Batch) -> None:
    """Record a delivered batch. The medicine must already be registered."""
    if store.get_medicine(batch.sku) is None:
        raise KeyError(f"register medicine {batch.sku} before receiving stock")
    store.add_batch(batch)


def stock_level(store, sku: str, today: date) -> int:
    """Units of ``sku`` that can still be dispensed (expired batches excluded)."""
    return sum(b.quantity for b in store.list_batches(sku) if not b.is_expired(today))


def expired_batches(store, today: date) -> List[Batch]:
    """Batches past expiry that still hold units."""
    return [b for b in store.list_batches() if b.quantity > 0 and b.is_expired(today)]


def write_off_expired(store, today: date) -> List[Batch]:
    """Zero out every expired batch and return what was written off."""
    written_off = expired_batches(store, today)
    for batch in written_off:
        store.update_batch_quantity(batch.batch_no, 0)
    return written_off
