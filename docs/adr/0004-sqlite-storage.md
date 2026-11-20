# 4. Move inventory storage to SQLite

## Status

Accepted (supersedes ADR-0001)

## Context

ADR-0001 stored everything in one JSON file and accepted two risks: every
write rewrites the whole file, and concurrent writers can lose updates. The
atomic-write fix stopped truncated files but not lost updates. Once a second
counter terminal and the HTTP API both write stock, two dispenses at the same
moment can each read the old file and one decrement is lost, so the recorded
stock drifts away from the shelf.

## Decision

Migrate `medstock/storage.py` to SQLite through Python's built-in `sqlite3`
module. Each write is its own transaction; `CHECK` constraints keep
quantities non-negative and foreign keys tie batches to medicines.
`SQLiteStore.import_legacy_json()` imports an existing ADR-0001
`inventory.json` in a single transaction.

We considered PostgreSQL, but a database server is too much to install and
administer on a single pharmacy PC.

Rejected alternatives: PostgreSQL server; keeping the JSON file with a lock
file.

## Consequences

- Still zero external dependencies and a single file to back up.
- Writers no longer overwrite each other's changes.
- Existing users run `medstock import-json inventory.json` once.
- ADR-0001 is superseded.
