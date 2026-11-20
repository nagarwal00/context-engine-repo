import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr

from medstock.cli import main

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLE = os.path.join(HERE, os.pardir, "data", "sample_inventory.csv")


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "medstock.db")

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, *argv):
        out = io.StringIO()
        err = io.StringIO()
        with redirect_stderr(err):
            code = main(["--db", self.db, "--today", "2026-11-21", *argv], out=out)
        return code, out.getvalue(), err.getvalue()

    def test_import_sample_and_alerts(self):
        code, out, _ = self.run_cli("import-csv", SAMPLE)
        self.assertEqual((code, out.strip()), (0, "imported 6 batches"))
        code, out, _ = self.run_cli("alerts")
        self.assertEqual(code, 0)
        self.assertIn("[expired] Batch CTZ-2311A", out)
        self.assertIn("[near_expiry] Batch AMX-2405B", out)
        self.assertIn("[low_stock] Metformin 500 mg", out)

    def test_dispense_picks_shortest_dated_batch(self):
        self.run_cli("import-csv", SAMPLE)
        code, out, _ = self.run_cli("dispense", "PCM500", "320")
        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines(), ["pick 300 from batch PCM-2406A", "pick 20 from batch PCM-2409C"])

    def test_dispense_more_than_stock_fails(self):
        self.run_cli("import-csv", SAMPLE)
        code, _, err = self.run_cli("dispense", "AMX250", "1000")
        self.assertEqual(code, 1)
        self.assertIn("error:", err)

    def test_manual_flow_and_write_off(self):
        self.assertEqual(self.run_cli("add-medicine", "ZNC20", "Zinc 20 mg", "--unit", "tablet")[0], 0)
        self.assertEqual(self.run_cli("receive", "ZNC20", "Z1", "10", "2026-11-01",
                                      "--received-on", "2026-01-01")[0], 0)
        code, out, _ = self.run_cli("write-off")
        self.assertEqual((code, out.strip()), (0, "wrote off 10 x ZNC20 (batch Z1)"))
        code, out, _ = self.run_cli("stock")
        self.assertEqual(out.strip(), "ZNC20\t0\tZinc 20 mg")


if __name__ == "__main__":
    unittest.main()
