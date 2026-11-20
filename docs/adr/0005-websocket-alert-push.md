# 5. Push alerts to the dashboard over a WebSocket

## Status

Proposed

## Context

The alerts dashboard currently refreshes by polling `GET /alerts` every 30
seconds (`medstock/api.py`). Polling is simple, but a stock-out caused by a
dispense at one counter can take up to 30 seconds to show on the dashboard at
another, and every open dashboard issues 120 requests per hour even when
nothing changed.

## Decision

Proposed: add a WebSocket endpoint (`/ws/alerts`) that pushes the alert list
whenever a dispense, receipt or write-off changes it, and keep `GET /alerts`
for clients that cannot open a WebSocket.

## Consequences

- Alerts appear immediately instead of after up to one poll interval.
- Python's standard library has no WebSocket server, so this either adds the
  project's first third-party dependency or a hand-written RFC 6455
  handshake and framing layer.
- Conflicts with the current polling design in `medstock/api.py`; one of the
  two approaches needs to be chosen before implementation.
