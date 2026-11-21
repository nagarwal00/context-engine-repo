"""Prepare a CIF database after ingesting this repository.

CIF ingestion does not create guard rules and does not run conflict or
supersession detection. This script does both for nagarwal00/context-engine-repo:

1. Loads the rules from cif_rules.json into the CIF database. By default they
   are added as "proposed" so a maintainer approves them in the Review Queue;
   pass --activate to make them active immediately.
2. Runs CIF's ReconciliationEngine (conflict and supersession detection).

Run it after ingesting the repository in the CIF dashboard, with the CIF
server stopped or idle:

    python tools/cif_setup.py --engine C:\\path\\to\\SE_project
"""
from __future__ import annotations

import argparse
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_NAME = "nagarwal00/context-engine-repo"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--engine", required=True, help="path to the CIF checkout")
    parser.add_argument("--db", help="CIF database (default: <engine>/context_intelligence.db)")
    parser.add_argument("--rules", default=os.path.join(REPO_ROOT, "cif_rules.json"))
    parser.add_argument("--activate", action="store_true", help="make the rules active instead of proposed")
    args = parser.parse_args(argv)

    engine = os.path.abspath(args.engine)
    db_path = os.path.abspath(args.db or os.path.join(engine, "context_intelligence.db"))
    if not os.path.isfile(os.path.join(engine, "backend", "db.py")):
        print(f"[cif-setup] not a CIF checkout: {engine}", file=sys.stderr)
        return 2
    if not os.path.isfile(db_path):
        print(f"[cif-setup] database not found: {db_path}", file=sys.stderr)
        return 2
    sys.path.insert(0, engine)

    from backend.db import Database
    from backend.engine.reconciliation import ReconciliationEngine
    from backend.models import GuardRule

    db = Database(db_path)
    with db.get_connection() as conn:
        ingested = conn.execute("SELECT COUNT(*) FROM decisions WHERE repo = ?", (REPO_NAME,)).fetchone()[0]
    if ingested == 0:
        print(f"[cif-setup] {REPO_NAME} has not been ingested into {db_path}; ingest it in the dashboard first.",
              file=sys.stderr)
        return 1
    print(f"[cif-setup] {ingested} decisions found for {REPO_NAME}")
    with db.get_connection() as conn:
        registered = conn.execute("SELECT COUNT(*) FROM repos WHERE repo_full_name = ?", (REPO_NAME,)).fetchone()[0]
    if not registered:
        print(f"[cif-setup] WARNING: {REPO_NAME} is not registered in the repos table, so the dashboard "
              "cannot select it. Update CIF to a version that registers repos on ingest and ingest again.")

    with open(args.rules, encoding="utf-8") as fh:
        rules = json.load(fh)
    status = "active" if args.activate else "proposed"
    for r in rules:
        with db.get_connection() as conn:
            cited = conn.execute("SELECT COUNT(*) FROM decisions WHERE decision_id = ?", (r["decision_id"],)).fetchone()[0]
        if not cited:
            print(f"[cif-setup] WARNING {r['rule_id']}: decision {r['decision_id']} not in the database "
                  "(were the ADRs ingested? a GitHub token avoids rate-limited partial ingests)")
        db.upsert_guard_rule(GuardRule(
            rule_id=r["rule_id"], decision_id=r["decision_id"], rule_type=r["rule_type"],
            params=r["params"], status=status, polarity=r.get("polarity", "must_not"),
            applies_to=r["params"].get("paths", []), source="human",
            approved_by="cif_setup" if args.activate else None,
        ))
        print(f"[cif-setup] rule {r['rule_id']} -> {status}")

    recon = ReconciliationEngine(db)
    conflicts = recon.check_for_conflicts(REPO_NAME)
    supersessions = recon.detect_supersessions(REPO_NAME)
    for c in conflicts:
        print(f"[cif-setup] conflict ({c['contradiction_topic']}): "
              f"{c['decision_1']['title']}  <->  {c['decision_2']['title']}")
    print(f"[cif-setup] {len(conflicts)} conflict(s), {len(supersessions)} supersession candidate(s) recorded")
    print("[cif-setup] done; restart or refresh the CIF dashboard")
    return 0


if __name__ == "__main__":
    sys.exit(main())
