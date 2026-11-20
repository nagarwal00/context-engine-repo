import unittest
from datetime import date

from medstock.models import Batch, Medicine


class MedicineTests(unittest.TestCase):
    def test_valid_medicine(self):
        med = Medicine("PCM500", "Paracetamol 500 mg", "tablet", reorder_level=100)
        self.assertEqual(med.reorder_level, 100)

    def test_empty_sku_rejected(self):
        with self.assertRaises(ValueError):
            Medicine("  ", "Paracetamol 500 mg")

    def test_negative_reorder_level_rejected(self):
        with self.assertRaises(ValueError):
            Medicine("PCM500", "Paracetamol 500 mg", reorder_level=-1)


class BatchTests(unittest.TestCase):
    def make(self, **overrides):
        values = dict(
            batch_no="B1",
            sku="PCM500",
            quantity=50,
            expiry_date=date(2027, 3, 31),
            received_on=date(2026, 11, 1),
        )
        values.update(overrides)
        return Batch(**values)

    def test_negative_quantity_rejected(self):
        with self.assertRaises(ValueError):
            self.make(quantity=-5)

    def test_expiry_before_receipt_rejected(self):
        with self.assertRaises(ValueError):
            self.make(expiry_date=date(2026, 10, 1))

    def test_days_to_expiry(self):
        batch = self.make(expiry_date=date(2026, 12, 1))
        self.assertEqual(batch.days_to_expiry(date(2026, 11, 21)), 10)

    def test_not_expired_before_expiry_date(self):
        batch = self.make(expiry_date=date(2026, 12, 1))
        self.assertFalse(batch.is_expired(date(2026, 11, 30)))

    def test_expired_after_expiry_date(self):
        batch = self.make(expiry_date=date(2026, 12, 1))
        self.assertTrue(batch.is_expired(date(2026, 12, 2)))


if __name__ == "__main__":
    unittest.main()
