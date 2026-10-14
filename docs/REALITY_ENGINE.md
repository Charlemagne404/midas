# Reality engine — Mission 1 (in progress)

Isolated branch `project/reality`, baseline `8acab22`. Runtime data stays in this
worktree's `data/recordings`; the production API, financial simulation and
protected research stores are not modified.

Implementation order: validate public contracts; start bounded durable capture;
add reconstruction/replay and failure tests; deploy user supervision; verify
restart, protected archive and regressions. Mission 2 UI is outside scope.

Official contracts consulted 2026-10-14:
- https://docs.polymarket.com/market-data/discover-markets
- https://docs.polymarket.com/market-data/realtime-data
- https://docs.polymarket.com/api-reference/wss/market

Gamma returns explicit v1 CTF token IDs and v2 position IDs. This initial engine
selects only explicit v1 active accepting-order markets with validated distinct
binary tokens; V2 is excluded with a reason. Discovery is a bounded liquidity
page, sorted deterministically by reported 24-hour volume then market ID.
Public WS uses `assets_ids`, market subscription and text PING every ten seconds.
No documented reliable per-book sequence exists in this contract. Receive order
is an observation order, not exchange causality or execution latency.

## Recording and reconstruction contract

The official [AsyncAPI schema](https://docs.polymarket.com/asyncapi.json) confirms
that updates assign the new aggregate level size; zero removes a level. Snapshot
levels are aggregated, and source timestamps are Unix milliseconds. The field
is not a matching-engine sequence or proof of latency. Initial subscription
requests explicitly ask for `initial_dump`; reconnections get fresh snapshots.
The official [rate limits](https://docs.polymarket.com/api-reference/rate-limits)
list Gamma `/markets` at 300 requests/10 seconds and CLOB `/book` at 1,500/10
seconds. Normal operation uses one discovery request per five minutes and one
WS with six assets. No market-channel subscription ceiling was found in these
contracts; the local ten-market maximum is an engineering bound, not a venue
limit. No authenticated PolyBolt, wallet or account interface is used.

Storage v1 is `MIDASR1\n`, followed by independently compressed zlib records:
4-byte big-endian compressed length, 32-byte SHA256, then compressed canonical
JSON. Records retain original WS text (or base64 for unexpected binary frames),
normalized event type/asset/condition/source timestamp summaries, UTC Unix
reception nanoseconds, monotonic nanoseconds, connection/subscription UUIDs and
a durable global ordinal. Full discovery response text and the selected cohort
are retained. Unknown frames are retained and counted; uncertain books are
invalidated. Snapshot constraint records point back to their raw frame ordinal.

Every append is flushed and fsynced before reconstruction. Each completed `.seg`
has an atomically published catalog manifest with whole-file SHA256, bytes,
ordinal range, record counts and kinds. Catalog files are the durable segment
index. Exports copy finalized segments and a versioned input manifest. The live
`.open` segment is deliberately excluded from exports; `SIGUSR1` finalizes it.
Restart recovery checks existing segments and salvages only complete checksummed
records from an open segment. A partial tail is preserved as `.tail` and its byte
count is recorded in a process-start gap. Checksum corruption fails closed.
One advisory writer lock prevents concurrent writers. Nothing writes to MIDAS
production SQLite, Arena or Laboratory storage.

Replay orders records by durable ordinal and events within a frame by array
index. It never sorts by exchange timestamp or looks ahead for a later snapshot.
`--through` ends the state at an observed ordinal. Repeated level assignments
remain observations; duplicate counts use bounded recent hashes. Regressing
source timestamps, crossed/locked books, malformed events, unexpected assets,
unknown events, reported top divergence and staleness invalidate affected books.
Reconnections and process boundaries invalidate all existing books until fresh
snapshots arrive. Snapshots replace depth and establish a new lineage. Snapshot
differences are counted even across a gap; that count does not prove venue drift
or a lost message. Source hashes remain opaque; the documented update hash is
not guaranteed to equal a reconstructed full-book content hash.

Book levels, top prices and spreads use Decimal. Quote lifetime statistics
measure changes observed at the receiver, with a fresh interval on each snapshot;
they are not exchange queue lifetimes. `internally_consistent` refers to the
observed snapshot/update lineage. `sequence_verified` is always false. Quiet books
older than 60 seconds are explicitly stale, even when other assets are active.
Every 30 seconds and on rotation/shutdown, a checkpoint stores the deterministic
pre-checkpoint state hash. Replay must match every stored online checkpoint.
Observed values are raw messages; depth/top/spreads are reconstructed; continuity,
freshness and quote lifetimes are local assessments with these stated limits.

## Supervision and commands

Run from `/home/charlie/midas-reality`:

```bash
systemctl --user status midas-reality.service
.venv/bin/python -m midas.reality status
journalctl --user -u midas-reality.service -n 50 --no-pager
systemctl --user stop midas-reality.service
systemctl --user start midas-reality.service
systemctl --user restart midas-reality.service
systemctl --user kill -s SIGUSR1 midas-reality.service
.venv/bin/python -m midas.reality export --output data/recordings/my-export
.venv/bin/python -m midas.reality replay --manifest data/recordings/my-export/manifest.json
.venv/bin/python -m midas.reality replay --through 100 --output /tmp/reality-state.json
```

`deploy/reality.json` is the persisted production configuration. Changes apply
on restart. Other isolated roots can be selected only under this worktree's
`data/recordings`. Export destinations must be new directories. Exports omit the
actively written segment, so rotate first when a recent interval is required.
All status output is local; no public port or API route is introduced. Status
older than ten seconds is flagged `STATUS_STALE`; assess expected/fresh book
counts along with service state and receive time. Restart failures are bounded
at five starts per five minutes; restore storage/connectivity, then use
`systemctl --user reset-failed midas-reality.service` and start explicitly.

The user unit is enabled, with user lingering already enabled on this host.
It has a 512 MiB memory maximum, 25% of one CPU quota, 32 tasks, low scheduling
priority, read-only home/system access except this worktree's recordings,
restart-on-failure with ten-second delay and 45-second graceful-stop timeout.
The receiver queue is bounded at 32 frames of at most 1 MiB. Library transport
backpressure pauses reads; no application drop policy silently discards frames.
A transport close or overflow produces a gap and fresh subscription. Remote
silent drops cannot be proved absent without a sequence contract.

The initial store budget is 2 GiB, segment maximum 8 MiB (plus a bounded record)
and 300 seconds, with 5 GiB free-space reserve and 30-day retention horizon.
Checkpoints also rotate segments every 30 seconds. Budget, reserve or retention
exhaustion stops recording; no research data or raw segments are automatically
deleted. Export/archive the recording root and configure a fresh isolated root
before the horizon or budget expires. The service intentionally fails closed
when durable storage cannot proceed. Keep exported copies outside the active
root's budget accounting and budget them separately. This is bounded unattended
recording, not an unlimited archival retention service.

## Verification

`tests/test_reality.py` uses small genuinely captured payloads whose original
segment SHA256 and ordinal references are in `tests/fixtures/reality/observed.json`.
Tests modifying those payloads are labeled fault tests; the localhost reconnect
test sends those fixtures and is not presented as a live venue capture.
Tests cover exact assignments/removal, duplicates, snapshots and drift, malformed
and unknown events, stale/crossed books, tick changes, timestamp regressions,
writer exclusion, rotation, budget stop, corruption, partial-tail recovery,
checkpoint mismatch, no future state, real socket close/reconnect, heartbeat and
safe shutdown. Production smoke and operational evidence are recorded separately.

Mission 2 UI, analytics, shadow fills, economic calibration and profitability
claims remain outside this engine. V2 reconstruction is explicitly unsupported.

Early supervised captures retain two corrected implementation defects: the
heartbeat classifier caused extra explicitly recorded reconnect gaps, and five
snapshot-constraint records (ordinals 621–625) pointed to preceding constraint
records rather than snapshot frame 619. Append-only `metadata_correction` records
supply the correct provenance without changing original recordings. The original
book snapshot lineage was correct, values were unchanged, and checkpoint hashes
remain reproducible. Both recorder defects are fixed; no continuous coverage is
claimed for those reconnect intervals. Metadata corrections are provenance
annotations, not future market observations used in earlier reconstructed states.

At the first audit (16.2-minute capture span), 1,197 genuine frames contained
80 book events, 1,104 price-change events, 75 venue-wide new-market events,
two best-bid/ask events and one last-trade event. Twenty-seven online checkpoints
matched repeat replay. The finalized segments occupied 1.48 MB; the observed
initial growth rate, including development reconnect metadata, projected about
132 MB/day. That projects roughly sixteen days to the 2 GiB budget; actual rates
vary. Plan export/archive before the budget threshold. Peak recorder memory was
about 31 MB, well below its 512 MiB cap. The protected archive remained intact
with its owner lock held, and the existing services kept their original PIDs.
These are measured early-production checks, not proof of multi-day operation.

The final regression suite is running in the isolated worktree with the pinned
CPU Arena dependencies and one BLAS/OpenMP thread. Focused Reality tests, Ruff
and strict typing pass. Mission acceptance remains pending until the broader
regression and the final runtime audit finish. Read-only evidence generation:

```bash
systemctl --user kill -s SIGUSR1 midas-reality.service
.venv/bin/python scripts/audit_reality.py
```
