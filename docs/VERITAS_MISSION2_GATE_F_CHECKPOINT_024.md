# Gate F checkpoint 024 — scan 40 qualified

**Captured:** 2026-10-16 00:00 UTC

## Scan-pinned qualification

The scheduled Research Director admitted scan
`scan-20261015T233205Z-a2240a38b48f` as Arena child
`job-2bab2b48ad934f99bf187a8a`. The child completed all 40 source events
with exit status 0 at 23:46:25 UTC. Its durable finding reports
`no_positive_gross_candidate_observed`, complete empty candidate evidence,
and zero states at the top-ask, full-depth, per-leg-minimum,
single-match-fee, and fragmentation-safe-fee gates.

The v4 panel covers 40 finalized snapshots and 1,600 selected pair slots.
It contains 1,405 request/receipt-quality-valid pairs across 741 selected
market IDs. Among valid states, the maximum top-pair edge is -$0.001 per
share and the median is -$0.020 per share. Invalid states and the scan-1
capture counter version difference are detailed in the [A1 coverage
artifact](VERITAS_MISSION2_MARKET_UNIVERSE_COVERAGE_001.json).

The Arena job is complete. The Director manifest still projects the child as
`QUEUED` pending its scheduled 00:15:04 UTC reconciliation; this is a delayed
projection, not a failed qualification. No manual poll, retry, or duplicate
job was started. The next observer timer is 00:01:47 UTC, and the fixed
measurement pilot remains on its existing protocol.

## Interpretation and limits

The 40 snapshots are repeated intermittent observations from bounded six-frame
discovery unions. They are not independent opportunity trials and do not
establish venue-wide prevalence, quote duration, order arrival, fills, or
profitability. The result keeps no-trade as the hypothetical policy and does
not justify model or execution-policy comparison. No authenticated requests
or orders occurred.

The persisted Arena finding is linked from [inventory
046](VERITAS_MISSION2_RESEARCH_INVENTORY_046.json). The independent A1
discovery audit and its focused tests are in [Gate A checkpoint
038](VERITAS_MISSION2_GATE_A_CHECKPOINT_038.md). Mission 2 remains active.
