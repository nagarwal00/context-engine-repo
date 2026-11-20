# 2. Dispense batches in FIFO (first-in, first-out) order

## Status

Proposed

## Context

When a medicine is stocked from several batches, the dispensing code has to
choose which batch to take units from. FIFO by `received_on` date is the
default most inventory tools use and the simplest to explain to counter staff.

## Decision

Pick batches in FIFO order: the batch with the oldest `received_on` date is
dispensed first.

## Consequences

- Simple rule, easy to verify by hand on the shelf.
- Assumes deliveries arrive in expiry order. To be checked against real
  delivery data before acceptance.
