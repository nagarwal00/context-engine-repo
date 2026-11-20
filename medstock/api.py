"""JSON HTTP API for counter terminals and the alerts dashboard (stdlib only).

The dashboard refreshes alerts by polling ``GET /alerts``; the response tells
the client how often to poll via ``poll_interval_seconds`` and the
``X-Poll-Interval`` header.
"""
from __future__ import annotations

import json
import threading
from datetime import date
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Optional, Tuple

from medstock.alerts import collect_alerts
from medstock.dispensing import InsufficientStock, dispense
from medstock.inventory import receive, stock_level
from medstock.models import Batch
from medstock.storage import StaleStock

POLL_INTERVAL_SECONDS = 30
MAX_BODY_BYTES = 64 * 1024


class ApiError(Exception):
    def __init__(self, status: HTTPStatus, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


class MedStockApp:
    """Request routing and business logic, independent of the HTTP server."""

    def __init__(self, store, today: Callable[[], date] = date.today) -> None:
        self.store = store
        self.today = today
        # One SQLite connection is shared by all handler threads; serialise access.
        self.lock = threading.Lock()

    def handle(self, method: str, path: str, body: Optional[dict]) -> Tuple[HTTPStatus, dict]:
        path = path.split("?", 1)[0].rstrip("/") or "/"
        with self.lock:
            if method == "GET" and path == "/health":
                return HTTPStatus.OK, {"status": "ok"}
            if method == "GET" and path == "/medicines":
                return HTTPStatus.OK, {"medicines": self._medicines()}
            if method == "GET" and path == "/alerts":
                alerts = collect_alerts(self.store, self.today())
                return HTTPStatus.OK, {
                    "alerts": [a.to_dict() for a in alerts],
                    "poll_interval_seconds": POLL_INTERVAL_SECONDS,
                }
            if method == "POST" and path == "/dispense":
                return self._dispense(body or {})
            if method == "POST" and path == "/receive":
                return self._receive(body or {})
        raise ApiError(HTTPStatus.NOT_FOUND, f"no route for {method} {path}")

    def _medicines(self) -> list:
        today = self.today()
        return [
            {"sku": m.sku, "name": m.name, "unit": m.unit, "reorder_level": m.reorder_level,
             "stock": stock_level(self.store, m.sku, today)}
            for m in self.store.list_medicines()
        ]

    def _dispense(self, body: dict) -> Tuple[HTTPStatus, dict]:
        sku = body.get("sku")
        quantity = body.get("quantity")
        if not isinstance(sku, str) or not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
            raise ApiError(HTTPStatus.BAD_REQUEST, "body must be {\"sku\": str, \"quantity\": positive int}")
        if self.store.get_medicine(sku) is None:
            raise ApiError(HTTPStatus.NOT_FOUND, f"unknown medicine {sku}")
        try:
            plan = dispense(self.store, sku, quantity, self.today())
        except (InsufficientStock, StaleStock) as exc:
            raise ApiError(HTTPStatus.CONFLICT, str(exc)) from None
        return HTTPStatus.OK, {"sku": sku, "picked": [{"batch_no": b, "units": u} for b, u in plan]}

    def _receive(self, body: dict) -> Tuple[HTTPStatus, dict]:
        try:
            batch = Batch(
                batch_no=str(body["batch_no"]),
                sku=str(body["sku"]),
                quantity=int(body["quantity"]),
                expiry_date=date.fromisoformat(body["expiry_date"]),
                received_on=date.fromisoformat(body.get("received_on") or self.today().isoformat()),
            )
            receive(self.store, batch)
        except KeyError as exc:
            raise ApiError(HTTPStatus.BAD_REQUEST, f"missing or unknown field: {exc}") from None
        except (TypeError, ValueError) as exc:
            raise ApiError(HTTPStatus.BAD_REQUEST, str(exc)) from None
        return HTTPStatus.CREATED, {"batch_no": batch.batch_no}


def _make_handler(app: MedStockApp):
    class Handler(BaseHTTPRequestHandler):
        server_version = "MedStock/0.1"

        def _send(self, status: HTTPStatus, payload: dict) -> None:
            raw = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Poll-Interval", str(POLL_INTERVAL_SECONDS))
            self.end_headers()
            self.wfile.write(raw)

        def _dispatch(self, method: str) -> None:
            try:
                body = None
                if method == "POST":
                    length = int(self.headers.get("Content-Length") or 0)
                    if length > MAX_BODY_BYTES:
                        raise ApiError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "request body too large")
                    try:
                        body = json.loads(self.rfile.read(length) or b"{}")
                    except json.JSONDecodeError:
                        raise ApiError(HTTPStatus.BAD_REQUEST, "body is not valid JSON") from None
                    if not isinstance(body, dict):
                        raise ApiError(HTTPStatus.BAD_REQUEST, "body must be a JSON object")
                status, payload = app.handle(method, self.path, body)
            except ApiError as exc:
                status, payload = exc.status, {"error": exc.message}
            self._send(status, payload)

        def do_GET(self) -> None:  # noqa: N802 (http.server naming)
            self._dispatch("GET")

        def do_POST(self) -> None:  # noqa: N802
            self._dispatch("POST")

        def log_message(self, fmt: str, *args) -> None:
            pass

    return Handler


def make_server(store, host: str = "127.0.0.1", port: int = 8000,
                today: Callable[[], date] = date.today) -> ThreadingHTTPServer:
    """Create (but do not start) the HTTP server."""
    return ThreadingHTTPServer((host, port), _make_handler(MedStockApp(store, today)))
