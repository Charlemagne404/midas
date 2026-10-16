# Gate A checkpoint 042 — scan 44 and the 24-hour measurement pilot

**Captured:** 2026-10-16 01:46 UTC

**Scan:** `scan-20261016T013014Z-f4312bef6258`

**Mission status:** active; no strategy or opportunity is promoted.

## Public observation

The scheduled observer completed scan 44 at 01:30:14 UTC and exited 0. Six
bounded Gamma queries returned 300 unique market IDs. Of those, 204 passed the
current supported same-condition V1 pair rule and 96 were excluded: 31 because
augmented negative-risk semantics were unverified and 65 for unsupported
outcome relationships. This is the bounded query union, not a venue census.

The scanner selected 40 pairs; 35 passed the request/receipt quality gate and
five did not. No positive top-ask gross pair appeared. At each tested quantity
(5, 10, 20, 50, and 100 shares per leg), positive full-depth gross,
per-leg-minimum, single-match-fee, and fragmentation-safe-fee counts were all
zero. No authenticated request or order was used.

The current v4 panel covers 44 snapshots: 1,534/1,760 selected pair states
passed quality checks, with 226 invalid states, 798 distinct selected market
IDs, and zero candidate events. Its maximum top edge remains -$0.001/share.
These repeated intermittent observations are correlated and selected; they do
not establish opportunity prevalence, quote persistence, fills, or performance.

## Fixed measurement pilot

The unchanged v1 pilot is at 14/48 planned scans, with 464/560 selected slots
quality-valid (82.9%), 348 distinct selected IDs, and zero skipped scan
sequences. The rotating/stable-control yields remain descriptive and
nonrandomized. The fixed stop is 2026-10-16 19:00:55 UTC. The separate
eight-read discovery successor remains unrun until the pilot reaches its stop.

## Qualification and next evidence

The scheduled Research Director cycle at 01:45 UTC admitted a scan-pinned
Arena child for scan 44. The child completed 44/44 source events and passed
read-only finding validation; see [Gate F checkpoint
027](VERITAS_MISSION2_GATE_F_CHECKPOINT_027.md). The Director manifest still
projects the child as `QUEUED` and scan 43 as last qualified until its next
scheduled reconciliation at 02:15 UTC. No manual poll or retry was made.

Keep no-trade, preserve all six discovery frames and pilot rules, and wait for
the scheduled reconciliation. The observation system remains intermittent;
reported source times and request/receipt duration do not prove venue sequence
freshness or batch atomicity.
