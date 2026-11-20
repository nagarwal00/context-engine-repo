import unittest
from datetime import date

from medstock.alerts import collect_alerts
from medstock.models import Batch, Medicine
from medstock.storage import SQLiteStore

TODAY = date(2026, 11, 21)


class AlertTests(unittest.TestCase):
    def setUp(self):
        self.store = SQLiteStore(":memory:")
        self.store.add_medicine(Medicine("CTZ10", "Cetirizine 10 mg", "tablet", reorder_level=20))
        self.store.add_medicine(Medicine("MET500", "Metformin 500 mg", "tablet", reorder_level=50))

    def tearDown(self):
        self.store.close()

    def kinds(self, **kwargs):
        return [(a.kind, a.sku, a.batch_no) for a in collect_alerts(self.store, TODAY, **kwargs)]

    def test_no_alerts_when_stock_healthy(self):
        self.store.add_batch(Batch("C1", "CTZ10", 100, date(2027, 6, 1), date(2026, 6, 1)))
        self.store.add_batch(Batch("M1", "MET500", 200, date(2027, 6, 1), date(2026, 6, 1)))
        self.assertEqual(self.kinds(), [])

    def test_low_stock_alert(self):
        self.store.add_batch(Batch("C1", "CTZ10", 100, date(2027, 6, 1), date(2026, 6, 1)))
        self.store.add_batch(Batch("M1", "MET500", 40, date(2027, 6, 1), date(2026, 6, 1)))
        self.assertEqual(self.kinds(), [("low_stock", "MET500", None)])

    def test_near_expiry_and_expired_ordering(self):
        self.store.add_batch(Batch("C1", "CTZ10", 100, date(2026, 12, 5), date(2026, 6, 1)))
        self.store.add_batch(Batch("M0", "MET500", 10, date(2026, 11, 1), date(2025, 11, 1)))
        self.store.add_batch(Batch("M1", "MET500", 200, date(2027, 6, 1), date(2026, 6, 1)))
        self.assertEqual(self.kinds(), [
            ("expired", "MET500", "M0"),
            ("near_expiry", "CTZ10", "C1"),
        ])

    def test_window_is_configurable(self):
        self.store.add_batch(Batch("C1", "CTZ10", 100, date(2026, 12, 5), date(2026, 6, 1)))
        self.store.add_batch(Batch("M1", "MET500", 200, date(2027, 6, 1), date(2026, 6, 1)))
        self.assertEqual(self.kinds(expiry_window_days=7), [])

    def test_alert_serialises(self):
        self.store.add_batch(Batch("M1", "MET500", 1, date(2027, 6, 1), date(2026, 6, 1)))
        self.store.add_batch(Batch("C1", "CTZ10", 100, date(2027, 6, 1), date(2026, 6, 1)))
        [alert] = collect_alerts(self.store, TODAY)
        self.assertEqual(alert.to_dict()["kind"], "low_stock")


if __name__ == "__main__":
    unittest.main()
