import os
import tempfile
import unittest
from datetime import date

from medstock.models import Batch, Medicine
from medstock.storage import JSONStore


class JSONStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = JSONStore(os.path.join(self.tmp.name, "inventory.json"))
        self.store.add_medicine(Medicine("AMX250", "Amoxicillin 250 mg", "capsule", 40))

    def tearDown(self):
        self.tmp.cleanup()

    def test_medicine_round_trip(self):
        med = self.store.get_medicine("AMX250")
        self.assertEqual(med.name, "Amoxicillin 250 mg")
        self.assertIsNone(self.store.get_medicine("NOPE"))

    def test_duplicate_medicine_rejected(self):
        with self.assertRaises(ValueError):
            self.store.add_medicine(Medicine("AMX250", "Duplicate"))

    def test_batch_round_trip_and_update(self):
        self.store.add_batch(Batch("L1", "AMX250", 30, date(2027, 1, 31), date(2026, 11, 2)))
        self.store.update_batch_quantity("L1", 12)
        [batch] = self.store.list_batches("AMX250")
        self.assertEqual(batch.quantity, 12)
        self.assertEqual(batch.expiry_date, date(2027, 1, 31))

    def test_batch_for_unknown_medicine_rejected(self):
        with self.assertRaises(KeyError):
            self.store.add_batch(Batch("L9", "NOPE", 1, date(2027, 1, 1), date(2026, 1, 1)))


if __name__ == "__main__":
    unittest.main()
