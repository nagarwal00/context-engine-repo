# MedStock

[![Tests](https://github.com/nagarwal00/context-engine-repo/actions/workflows/tests.yml/badge.svg)](https://github.com/nagarwal00/context-engine-repo/actions/workflows/tests.yml)

Medicine stock and expiry tracker for small pharmacies and clinics.

## The problem

Small pharmacies and rural clinics often track stock in notebooks or
spreadsheets. Two problems follow:

1. **Expiry losses.** One medicine is usually on the shelf in several batches
   with different expiry dates. If staff take whichever strip is in front,
   short-dated batches expire unsold and are written off.
2. **Stock-outs.** Fast-moving items (paracetamol, ORS, metformin) run out
   before anyone notices they need reordering.

MedStock records every batch with its expiry date, dispenses in
**first-expiry, first-out (FEFO)** order, and raises alerts for expired,
near-expiry and low-stock items before either problem happens.

## Features

| Feature | Module | Notes |
|---|---|---|
| Medicines and batches with expiry validation | `medstock/models.py` | A batch cannot expire before it is received |
| SQLite storage, one file, no server | `medstock/storage.py` | Transactions, CHECK constraints, expiry indexes ([ADR-0004](docs/adr/0004-sqlite-storage.md)) |
| FEFO dispensing | `medstock/dispensing.py` | Shortest-dated batch first, expired stock never dispensed ([ADR-0003](docs/adr/0003-fefo-dispensing.md)) |
| Atomic multi-batch dispense | `medstock/storage.py` | Conditional decrements in one transaction; stale plans roll back |
| Receiving, stock levels, expiry write-offs | `medstock/inventory.py` | Stock counts exclude expired units |
| Expired / near-expiry / low-stock alerts | `medstock/alerts.py` | 30-day window by default, configurable |
| JSON HTTP API | `medstock/api.py` | Dashboard polls `GET /alerts` every 30 s |
| Command-line interface | `medstock/cli.py` | Counter-staff workflow, CSV import, legacy JSON import |

Standard library only. Python 3.11 or newer.

## Quick start

```bash
git clone https://github.com/nagarwal00/context-engine-repo.git
cd context-engine-repo

# Load the sample inventory and look at the alerts
python -m medstock.cli --db medstock.db --today 2026-11-21 import-csv data/sample_inventory.csv
python -m medstock.cli --db medstock.db --today 2026-11-21 alerts

# Dispense 320 tablets: the CLI tells staff which batches to pick
python -m medstock.cli --db medstock.db --today 2026-11-21 dispense PCM500 320
```

`data/sample_inventory.csv` is an illustrative dataset (six batches) chosen so
that every alert type appears.

### CLI commands

| Command | What it does |
|---|---|
| `add-medicine SKU NAME [--unit U] [--reorder-level N]` | Register a medicine |
| `receive SKU BATCH QTY EXPIRY [--received-on DATE]` | Record a delivered batch |
| `dispense SKU QTY` | Dispense in FEFO order and print the batches to pick |
| `stock` | Dispensable units per medicine |
| `alerts [--window DAYS]` | Expired, near-expiry and low-stock alerts |
| `write-off` | Zero out expired batches |
| `import-csv PATH` | Import medicines and batches from CSV |
| `import-json PATH` | Import a legacy `inventory.json` (ADR-0001 format) |
| `serve [--host H] [--port P]` | Run the HTTP API |

Global options: `--db PATH` (default `medstock.db`), `--today YYYY-MM-DD`.

### HTTP API

Start it with `python -m medstock.cli --db medstock.db serve --port 8000`.

| Method | Path | Body | Result |
|---|---|---|---|
| GET | `/health` | | `{"status": "ok"}` |
| GET | `/medicines` | | Medicines with current dispensable stock |
| GET | `/alerts` | | `{"alerts": [...], "poll_interval_seconds": 30}` |
| POST | `/dispense` | `{"sku": "PCM500", "quantity": 12}` | Batches picked; `409` if stock is insufficient or changed meanwhile |
| POST | `/receive` | `{"batch_no", "sku", "quantity", "expiry_date", "received_on"?}` | `201` |

The alerts dashboard refreshes by polling `GET /alerts`; every response
carries `X-Poll-Interval: 30` and `Cache-Control: no-store`. A push-based
alternative is under discussion in [ADR-0005](docs/adr/0005-websocket-alert-push.md).

## Architecture decisions

Decisions are recorded as ADRs in [`docs/adr/`](docs/adr/) using the Nygard
template (Status / Context / Decision / Consequences).

| ADR | Decision | Status |
|---|---|---|
| [0001](docs/adr/0001-json-file-storage.md) | Store inventory in a single JSON file | Superseded by 0004 |
| [0002](docs/adr/0002-fifo-dispensing.md) | Dispense batches FIFO (by received date) | Rejected |
| [0003](docs/adr/0003-fefo-dispensing.md) | Dispense batches FEFO (by expiry date) | Accepted |
| [0004](docs/adr/0004-sqlite-storage.md) | Move storage to SQLite | Accepted |
| [0005](docs/adr/0005-websocket-alert-push.md) | Push alerts over a WebSocket | Proposed |

## Testing the Context Intelligence Framework

This repository doubles as a real-world test bed for the
[Context Intelligence Framework](https://github.com/nagarwal00/context-engine-prototype-).
[docs/TESTING_WITH_CIF.md](docs/TESTING_WITH_CIF.md) maps every CIF feature
to the commits, ADRs and code here and records what CIF produced on them.
Pull requests into `main` are checked against the ADRs by the
**CIF Decision Guard** workflow using the rules in `cif_rules.json`.

## Development

```bash
python -m unittest discover -s tests -t . -v
```

CI runs the same suite on Python 3.11 and 3.12 for every push and pull
request (`.github/workflows/tests.yml`).

## Licence

MIT, see [LICENSE](LICENSE).
