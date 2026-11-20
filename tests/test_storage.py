import json
import os
import tempfile
import unittest
from datetime import date

from medstock.models import Batch, Medicine
from medstock.storage import SQLiteStore, StaleStock


class SQLiteStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = SQLiteStore(":memory:")
        self.store.add_medicine(Medicine("AMX250", "Amoxicillin 250 mg", "capsule", 40))

    def tearDown(self):
        self.store.close()

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

    def test_duplicate_batch_rejected(self):
        self.store.add_batch(Batch("L1", "AMX250", 30, date(2027, 1, 31), date(2026, 11, 2)))
        with self.assertRaises(ValueError):
            self.store.add_batch(Batch("L1", "AMX250", 5, date(2027, 1, 31), date(2026, 11, 2)))

    def test_update_unknown_batch_rejected(self):
        with self.assertRaises(KeyError):
            self.store.update_batch_quantity("NOPE", 1)

    def test_batch_for_unknown_medicine_rejected(self):
        with self.assertRaises(KeyError):
            self.store.add_batch(Batch("L9", "NOPE", 1, date(2027, 1, 1), date(2026, 1, 1)))

    def test_apply_dispense_decrements(self):
        self.store.add_batch(Batch("L1", "AMX250", 30, date(2027, 1, 31), date(2026, 11, 2)))
        self.store.add_batch(Batch("L2", "AMX250", 30, date(2027, 2, 28), date(2026, 11, 2)))
        self.store.apply_dispense([("L1", 30), ("L2", 5)])
        self.assertEqual({b.batch_no: b.quantity for b in self.store.list_batches()}, {"L1": 0, "L2": 25})

    def test_stale_plan_is_rolled_back(self):
        # Another terminal took 25 of L2 after this plan was computed.
        self.store.add_batch(Batch("L1", "AMX250", 30, date(2027, 1, 31), date(2026, 11, 2)))
        self.store.add_batch(Batch("L2", "AMX250", 5, date(2027, 2, 28), date(2026, 11, 2)))
        with self.assertRaises(StaleStock):
            self.store.apply_dispense([("L1", 30), ("L2", 10)])
        self.assertEqual({b.batch_no: b.quantity for b in self.store.list_batches()}, {"L1": 30, "L2": 5})

    def test_expiry_indexes_exist(self):
        names = {r[0] for r in self.store.conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'batches'")}
        self.assertIn("idx_batches_sku_expiry", names)
        self.assertIn("idx_batches_expiry", names)

    def test_data_persists_across_connections(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "medstock.db")
            with SQLiteStore(path) as first:
                first.add_medicine(Medicine("ORS", "ORS sachet", "sachet", 30))
            with SQLiteStore(path) as second:
                self.assertEqual(second.get_medicine("ORS").unit, "sachet")


class LegacyImportTests(unittest.TestCase):
    def test_imports_adr_0001_json_file(self):
        legacy = {
            "medicines": {"PCM500": {"name": "Paracetamol 500 mg", "unit": "tablet", "reorder_level": 100}},
            "batches": {"P1": {"sku": "PCM500", "quantity": 60,
                               "expiry_date": "2027-03-31", "received_on": "2026-10-01"}},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "inventory.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(legacy, fh)
            with SQLiteStore(":memory:") as store:
                self.assertEqual(store.import_legacy_json(path), 1)
                [batch] = store.list_batches("PCM500")
                self.assertEqual(batch.quantity, 60)

    def test_failed_import_is_rolled_back(self):
        legacy = {
            "medicines": {"PCM500": {"name": "Paracetamol 500 mg"}},
            "batches": {"P1": {"sku": "UNKNOWN", "quantity": 1,
                               "expiry_date": "2027-03-31", "received_on": "2026-10-01"}},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "inventory.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(legacy, fh)
            with SQLiteStore(":memory:") as store:
                with self.assertRaises(Exception):
                    store.import_legacy_json(path)
                self.assertEqual(store.list_medicines(), [])


if __name__ == "__main__":
    unittest.main()
