# 2. Dispense batches in FIFO (first-in, first-out) order

## Status

Rejected (in favour of ADR-0003, FEFO dispensing)

## Context

When a medicine is stocked from several batches, the dispensing code has to
choose which batch to take units from. FIFO by `received_on` date is the
default most inventory tools use and the simplest to explain to counter staff.

## Decision

Pick batches in FIFO order: the batch with the oldest `received_on` date is
dispensed first.

Rejected. Distributors do not deliver in expiry order: a delivery received
later can carry a shorter shelf life than stock already on the shelf (short-
dated lots are often sold at a discount). Under FIFO that newer, shorter-dated
batch waits behind the older one and expires unsold. The rule optimises for
arrival order, but the cost we are trying to avoid is expiry.

## Consequences

- FIFO must not be reintroduced in `medstock/dispensing.py`.
- Batch ordering is defined by ADR-0003 instead.
