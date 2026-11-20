# 3. Dispense batches in FEFO (first-expiry, first-out) order

## Status

Accepted

## Context

ADR-0002 proposed FIFO dispensing and was rejected because deliveries do not
arrive in expiry order. The pharmacy loses money when a batch expires on the
shelf, so the ordering rule should follow expiry, not arrival. WHO guidance
on good storage and distribution practices recommends FEFO stock rotation for
the same reason.

## Decision

`medstock/dispensing.py` orders dispensable batches by `expiry_date`
ascending, with `batch_no` as a deterministic tie-breaker. Expired and empty
batches are never dispensed. A request that non-expired stock cannot fully
cover fails without changing any batch.

We considered FIFO by received date, but it lets short-dated later deliveries
expire unsold.

Rejected alternatives: FIFO ordering by received_on date (ADR-0002).

## Consequences

- Shortest-dated stock leaves the shelf first, minimising expiry write-offs.
- Staff must pick by the expiry date printed on the strip, not by shelf
  position; the CLI prints the batch numbers to pick.
- Any code that sorts batches by `received_on` for dispensing is a regression.
