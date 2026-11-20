import json
import threading
import unittest
import urllib.error
import urllib.request
from datetime import date

from medstock.api import POLL_INTERVAL_SECONDS, make_server
from medstock.models import Batch, Medicine
from medstock.storage import SQLiteStore

TODAY = date(2026, 11, 21)


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = SQLiteStore(":memory:", check_same_thread=False)
        cls.store.add_medicine(Medicine("PCM500", "Paracetamol 500 mg", "tablet", 20))
        cls.store.add_batch(Batch("P1", "PCM500", 10, date(2026, 12, 1), date(2026, 6, 1)))
        cls.store.add_batch(Batch("P2", "PCM500", 30, date(2027, 6, 1), date(2026, 6, 1)))
        cls.server = make_server(cls.store, port=0, today=lambda: TODAY)
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.store.close()

    def request(self, method, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status, json.loads(resp.read()), resp.headers
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read()), err.headers

    def test_health(self):
        status, body, _ = self.request("GET", "/health")
        self.assertEqual((status, body), (200, {"status": "ok"}))

    def test_alerts_include_poll_interval(self):
        status, body, headers = self.request("GET", "/alerts")
        self.assertEqual(status, 200)
        self.assertEqual(body["poll_interval_seconds"], POLL_INTERVAL_SECONDS)
        self.assertEqual(headers["X-Poll-Interval"], str(POLL_INTERVAL_SECONDS))
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn("near_expiry", [a["kind"] for a in body["alerts"]])

    def test_dispense_uses_fefo_then_reports_conflict(self):
        status, body, _ = self.request("POST", "/dispense", {"sku": "PCM500", "quantity": 12})
        self.assertEqual(status, 200)
        self.assertEqual(body["picked"], [{"batch_no": "P1", "units": 10}, {"batch_no": "P2", "units": 2}])
        status, body, _ = self.request("POST", "/dispense", {"sku": "PCM500", "quantity": 500})
        self.assertEqual(status, 409)

    def test_dispense_validation(self):
        self.assertEqual(self.request("POST", "/dispense", {"sku": "PCM500", "quantity": "3"})[0], 400)
        self.assertEqual(self.request("POST", "/dispense", {"sku": "NOPE", "quantity": 1})[0], 404)

    def test_receive_and_list(self):
        status, _, _ = self.request("POST", "/receive", {
            "batch_no": "R1", "sku": "PCM500", "quantity": 5, "expiry_date": "2027-09-30"})
        self.assertEqual(status, 201)
        status, body, _ = self.request("GET", "/medicines")
        self.assertEqual(status, 200)
        self.assertEqual(body["medicines"][0]["sku"], "PCM500")
        self.assertEqual(self.request("POST", "/receive", {"sku": "PCM500"})[0], 400)

    def test_unknown_route(self):
        self.assertEqual(self.request("GET", "/nope")[0], 404)


if __name__ == "__main__":
    unittest.main()
