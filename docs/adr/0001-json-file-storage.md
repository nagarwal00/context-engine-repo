# 1. Store inventory in a single JSON file

## Status

Accepted

## Context

MedStock must run on the one shared computer found in most small pharmacies,
often without an administrator. Early on the data set is small: a few hundred
medicines and their batches. We want zero installation steps and a file the
pharmacist can back up by copying it.

## Decision

Persist medicines and batches in one JSON document (`inventory.json`) through
`medstock/storage.py`. Every write rewrites the whole file.

## Consequences

- No database server or driver to install; backups are a file copy.
- Every write rewrites the entire file, so cost grows with inventory size.
- Two processes writing at the same time can lose an update. Acceptable while
  only one counter terminal uses the tool; revisit if that changes.
