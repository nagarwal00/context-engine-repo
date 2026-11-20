import os
import tempfile
import unittest
from datetime import date

from medstock.inventory import expired_batches, receive, stock_level, write_off_expired
from medstock.models import Batch, Medicine
from medstock.storage import JSONStore

TODAY = date(2026, 11, 21)


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = JSONStore(os.path.join(self.tmp.name, "inv.json"))
        self.store.add_medicine(Medicine("ORS", "ORS sachet", "sachet", 30))
        receive(self.store, Batch("S1", "ORS", 20, date(2026, 11, 10), date(2025, 11, 1)))
        receive(self.store, Batch("S2", "ORS", 15, date(2027, 5, 31), date(2026, 10, 1)))

    def tearDown(self):
        self.tmp.cleanup()

    def test_receive_requires_registered_medicine(self):
        with self.assertRaises(KeyError):
            receive(self.store, Batch("X1", "UNKNOWN", 5, date(2027, 1, 1), date(2026, 1, 1)))

    def test_stock_level_ignores_expired(self):
        self.assertEqual(stock_level(self.store, "ORS", TODAY), 15)

    def test_expired_batches(self):
        self.assertEqual([b.batch_no for b in expired_batches(self.store, TODAY)], ["S1"])

    def test_write_off_expired(self):
        written = write_off_expired(self.store, TODAY)
        self.assertEqual([b.batch_no for b in written], ["S1"])
        self.assertEqual(expired_batches(self.store, TODAY), [])


if __name__ == "__main__":
    unittest.main()
