import unittest
from datetime import date

from medstock.dispensing import InsufficientStock, dispense, fefo_order, pick_batches
from medstock.models import Batch, Medicine
from medstock.storage import SQLiteStore

TODAY = date(2026, 11, 21)


def batch(no, qty, expiry, received=date(2026, 6, 1)):
    return Batch(no, "PCM500", qty, expiry, received)


class FefoOrderTests(unittest.TestCase):
    def test_earliest_expiry_first_even_if_received_later(self):
        # The later delivery expires sooner: this is the case FIFO gets wrong.
        older_delivery = batch("A", 10, date(2027, 6, 30), received=date(2026, 7, 1))
        newer_delivery = batch("B", 10, date(2027, 1, 31), received=date(2026, 9, 1))
        ordered = fefo_order([older_delivery, newer_delivery], TODAY)
        self.assertEqual([b.batch_no for b in ordered], ["B", "A"])

    def test_expired_and_empty_batches_excluded(self):
        ordered = fefo_order([
            batch("OLD", 5, date(2026, 11, 1)),
            batch("EMPTY", 0, date(2027, 1, 1)),
            batch("OK", 5, date(2027, 2, 1)),
        ], TODAY)
        self.assertEqual([b.batch_no for b in ordered], ["OK"])

    def test_ties_broken_by_batch_number(self):
        ordered = fefo_order([batch("Z", 1, date(2027, 1, 1)), batch("M", 1, date(2027, 1, 1))], TODAY)
        self.assertEqual([b.batch_no for b in ordered], ["M", "Z"])


class PickBatchesTests(unittest.TestCase):
    def test_spans_batches(self):
        plan = pick_batches([batch("A", 4, date(2027, 1, 1)), batch("B", 10, date(2027, 2, 1))], 7, TODAY)
        self.assertEqual(plan, [("A", 4), ("B", 3)])

    def test_insufficient_stock(self):
        with self.assertRaises(InsufficientStock) as ctx:
            pick_batches([batch("A", 4, date(2027, 1, 1))], 5, TODAY)
        self.assertEqual(ctx.exception.available, 4)

    def test_rejects_non_positive_quantity(self):
        with self.assertRaises(ValueError):
            pick_batches([], 0, TODAY)


class DispenseTests(unittest.TestCase):
    def test_dispense_updates_store(self):
        with SQLiteStore(":memory:") as store:
            store.add_medicine(Medicine("PCM500", "Paracetamol 500 mg", "tablet", 50))
            store.add_batch(batch("A", 4, date(2027, 1, 1)))
            store.add_batch(batch("B", 10, date(2027, 2, 1)))
            dispense(store, "PCM500", 7, TODAY)
            remaining = {b.batch_no: b.quantity for b in store.list_batches("PCM500")}
            self.assertEqual(remaining, {"A": 0, "B": 7})


if __name__ == "__main__":
    unittest.main()
