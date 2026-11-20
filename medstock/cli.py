"""Command-line interface: ``python -m medstock.cli --db medstock.db <command>``."""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import date
from typing import List, Optional

from medstock.alerts import DEFAULT_EXPIRY_WINDOW_DAYS, collect_alerts
from medstock.dispensing import InsufficientStock, dispense
from medstock.inventory import receive, stock_level, write_off_expired
from medstock.models import Batch, Medicine
from medstock.storage import SQLiteStore, StaleStock


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {value!r}") from None


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="medstock", description="Medicine stock and expiry tracker")
    p.add_argument("--db", default="medstock.db", help="SQLite database file (default: medstock.db)")
    p.add_argument("--today", type=_date, default=None, help="override today's date (YYYY-MM-DD)")
    sub = p.add_subparsers(dest="command", required=True)

    m = sub.add_parser("add-medicine", help="register a medicine")
    m.add_argument("sku")
    m.add_argument("name")
    m.add_argument("--unit", default="unit")
    m.add_argument("--reorder-level", type=int, default=0)

    r = sub.add_parser("receive", help="record a delivered batch")
    r.add_argument("sku")
    r.add_argument("batch_no")
    r.add_argument("quantity", type=int)
    r.add_argument("expiry_date", type=_date)
    r.add_argument("--received-on", type=_date, default=None)

    d = sub.add_parser("dispense", help="dispense units in FEFO order")
    d.add_argument("sku")
    d.add_argument("quantity", type=int)

    sub.add_parser("stock", help="show dispensable stock per medicine")

    a = sub.add_parser("alerts", help="show expiry and low-stock alerts")
    a.add_argument("--window", type=int, default=DEFAULT_EXPIRY_WINDOW_DAYS, help="near-expiry window in days")

    sub.add_parser("write-off", help="zero out expired batches")

    i = sub.add_parser("import-csv", help="import medicines and batches from a CSV file")
    i.add_argument("path")

    j = sub.add_parser("import-json", help="import a legacy inventory.json (ADR-0001 format)")
    j.add_argument("path")

    s = sub.add_parser("serve", help="run the JSON HTTP API")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    return p


def import_csv(store, path: str) -> int:
    """Import rows of sku,name,unit,reorder_level,batch_no,quantity,expiry_date,received_on."""
    count = 0
    with open(path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if store.get_medicine(row["sku"]) is None:
                store.add_medicine(Medicine(row["sku"], row["name"], row["unit"], int(row["reorder_level"])))
            receive(store, Batch(row["batch_no"], row["sku"], int(row["quantity"]),
                                 date.fromisoformat(row["expiry_date"]), date.fromisoformat(row["received_on"])))
            count += 1
    return count


def main(argv: Optional[List[str]] = None, out=sys.stdout) -> int:
    args = build_parser().parse_args(argv)
    today = args.today or date.today()

    if args.command == "serve":
        from medstock.api import make_server
        store = SQLiteStore(args.db, check_same_thread=False)
        server = make_server(store, args.host, args.port)
        print(f"MedStock API on http://{args.host}:{server.server_address[1]}", file=out)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
            store.close()
        return 0

    with SQLiteStore(args.db) as store:
        try:
            if args.command == "add-medicine":
                store.add_medicine(Medicine(args.sku, args.name, args.unit, args.reorder_level))
                print(f"registered {args.sku}", file=out)
            elif args.command == "receive":
                receive(store, Batch(args.batch_no, args.sku, args.quantity, args.expiry_date,
                                     args.received_on or today))
                print(f"received {args.quantity} x {args.sku} (batch {args.batch_no})", file=out)
            elif args.command == "dispense":
                for batch_no, units in dispense(store, args.sku, args.quantity, today):
                    print(f"pick {units} from batch {batch_no}", file=out)
            elif args.command == "stock":
                for med in store.list_medicines():
                    print(f"{med.sku}\t{stock_level(store, med.sku, today)}\t{med.name}", file=out)
            elif args.command == "alerts":
                alerts = collect_alerts(store, today, args.window)
                for alert in alerts:
                    print(f"[{alert.kind}] {alert.message}", file=out)
                if not alerts:
                    print("no alerts", file=out)
            elif args.command == "write-off":
                for batch in write_off_expired(store, today):
                    print(f"wrote off {batch.quantity} x {batch.sku} (batch {batch.batch_no})", file=out)
            elif args.command == "import-csv":
                print(f"imported {import_csv(store, args.path)} batches", file=out)
            elif args.command == "import-json":
                print(f"imported {store.import_legacy_json(args.path)} batches", file=out)
        except (InsufficientStock, StaleStock, KeyError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
