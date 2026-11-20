"""Low-stock and expiry alerts."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import List, Optional

from medstock.inventory import stock_level

DEFAULT_EXPIRY_WINDOW_DAYS = 30


@dataclass(frozen=True)
class Alert:
    kind: str  # "expired" | "near_expiry" | "low_stock"
    sku: str
    message: str
    batch_no: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


def collect_alerts(store, today: date, expiry_window_days: int = DEFAULT_EXPIRY_WINDOW_DAYS) -> List[Alert]:
    """Build the current alert list, most urgent kinds first."""
    if expiry_window_days < 0:
        raise ValueError("expiry_window_days must be >= 0")

    expired: List[Alert] = []
    near: List[Alert] = []
    low: List[Alert] = []

    for batch in store.list_batches():
        if batch.quantity == 0:
            continue
        if batch.is_expired(today):
            expired.append(Alert(
                "expired", batch.sku,
                f"Batch {batch.batch_no} of {batch.sku} expired on {batch.expiry_date.isoformat()}; "
                f"{batch.quantity} units must be written off",
                batch.batch_no,
            ))
        elif batch.days_to_expiry(today) <= expiry_window_days:
            near.append(Alert(
                "near_expiry", batch.sku,
                f"Batch {batch.batch_no} of {batch.sku} expires in {batch.days_to_expiry(today)} days "
                f"({batch.quantity} units)",
                batch.batch_no,
            ))

    for med in store.list_medicines():
        level = stock_level(store, med.sku, today)
        if level <= med.reorder_level:
            low.append(Alert(
                "low_stock", med.sku,
                f"{med.name}: {level} {med.unit}(s) left, reorder level is {med.reorder_level}",
            ))

    return expired + near + low
