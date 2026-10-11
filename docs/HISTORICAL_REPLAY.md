# Historical replay

Two retained public captures are packaged in `data/datasets`: `ctf-4024677` and
`ctf-4024680`. Each contains original attested market metadata plus two normalized
instrument snapshots with original raw responses. These are real-data captures, but
only three events each, not long continuous market histories. They contain no
observed hypothetical fills or redemption. Both captures reject the apparent trade
because the modeled edge is negative.

Each manifest contains source, capture clocks, instrument IDs, protocol types, version,
SHA-256 of exact JSONL bytes, count, exchange timestamp coverage, missing intervals,
known interruptions, metadata, completeness limits and economic assumptions. Empty
missing-interval/interruptions lists mean no interval was recorded in this bounded
capture, not that a continuous feed was complete. Campaigns additionally pin a hash
of the entire manifest. New datasets can use the existing Recorder's MarketEvent JSONL
schema and `create_manifest`; published datasets must include applicable metadata.

```bash
.venv/bin/python scripts/laboratory.py validate ctf-4024677
.venv/bin/python scripts/laboratory.py campaign --dataset ctf-4024677 --runs 1 --compare --root data/my-recorded-replay
```

Validation rejects changed hashes/counts/coverage, invalid lines, mixed synthetic
provenance, conflicting duplicate IDs, unknown instruments, condition mismatches and
inconsistent event/book clocks. Catalog validation labels failed datasets quarantined
and execution rejects them; it does not silently move or repair the source file.
Exact duplicates are suppressed. Receipt-disordered captures are replayed by stable
receipt order, retaining equal-time capture order. Exchange time never determines
when an observation becomes available. Older late exchange snapshots are counted and
cannot overwrite newer state. Raw unsequenced deltas invalidate their affected books;
the system does not invent full depth from incomplete deltas.

`replay_scenario` accepts a receipt-time window, instrument pair/market selection and
additional observation latency. Windows start with invalid books and require observed
snapshots; they do not warm-start from future data or assume preceding feed continuity.
One episode currently runs one binary market with its related instruments. Multi-market
joint episodes are deferred. The dataset manifest can catalog multiple markets, but
the current campaign builder selects the first supported pair.

The strategy sees only already received books, frozen before processing delay. Tests
delay the second book, send older exchange snapshots late, vary receipt latency and
verify that unchanged instruments keep their original receipt clock. A recorded dataset
ends at its declared receipt horizon: orders beyond that horizon remain pending;
there is no fabricated fill or payout. The UI labels recorded provenance separately
from synthetic scenarios and uses actual persisted/reconstructed event histories.

Execution is always hypothetical and uncalibrated. Public order books do not reveal
queue priority, hypothetical competing orders or exact match fragmentation. Comparing
execution models is an uncertainty analysis, not evidence of realized trading profit.
Repeating these captures with many seeds does not create new independent observations
of reality.
