# Reality engine — Mission 1

Read-only Polymarket recording, durable storage and deterministic reconstruction
on `project/reality`, isolated in `/home/charlie/midas-reality` from the protected
Prometheus checkout and runtime stores. The baseline remains `8acab22`, tagged
`prometheus-final-2026-10-14`. No wallet, credential, order submission, public
listener, UI, profitability estimate or financial simulation change is introduced.

## Public contracts and cohort

Official contracts consulted and checked against genuine responses:
- https://docs.polymarket.com/market-data/discover-markets
- https://docs.polymarket.com/market-data/realtime-data
- https://docs.polymarket.com/api-reference/wss/market
- https://docs.polymarket.com/asyncapi.json
- https://docs.polymarket.com/api-reference/rate-limits

Gamma supports event/market lookup and filtered listings, including keyset
pagination. This recorder requests a bounded page of active, open markets ordered
by liquidity, then selects deterministically by reported 24-hour volume and ID.
It validates explicit v1, accepting-order/order-book flags, condition IDs, distinct
CTF token IDs and Yes/No outcome relationships. V2 position IDs are distinguished
from CTF tokens and explicitly excluded. Full responses, selection settings,
selected mappings and rejection reasons are retained. Refresh replaces retired
assets; resolution invalidates affected books and requests resynchronization.

The initial cohort is three markets (six outcome tokens); configuration permits
one to ten markets. One public WS uses `assets_ids`, `type: market`,
`custom_feature_enabled` and `initial_dump`. Text PING is sent every ten seconds.
The observed legacy wire format uses full book snapshots and price changes whose
size is the **new aggregate level quantity**; zero removes a level. Source
messages use Unix millisecond timestamps. They are not matching-engine sequences
or exchange execution latency measurements. The update hash is not guaranteed to
be a reconstructed full-book content hash and remains opaque.

Official limits include Gamma `/markets` at 300 requests/10 seconds and CLOB
`/book` at 1,500/10 seconds. Normal discovery uses one request per five minutes.
No market-channel subscription ceiling was found in these contracts; ten markets
is our engineering bound. No authenticated PolyBolt or account interface is used.

## Durable recording and replay

Storage v1 starts with `MIDASR1\n`. Each record has a 4-byte big-endian compressed
length, 32-byte SHA256 and independently zlib-compressed canonical JSON. Records
retain original WS text (base64 for unexpected binary frames), normalized
asset/condition/type/source-timestamp summaries, UTC Unix reception nanoseconds,
monotonic nanoseconds, connection/subscription UUIDs and a durable global ordinal.
Process-start records preserve configuration and implementation identity.

Every append is flushed and fsynced before reconstruction. Completed `.seg`
files have atomic catalog manifests containing whole-file SHA256, byte count,
ordinal range and record-kind counts. These catalogs index the recordings.
A writer lock prevents competing writers. Raw stores are ignored by Git and stay
separate from the production API, Arena and Laboratory databases.

Recovery verifies finalized segments and salvages only complete checksummed
records from an open segment. Partial headers/tails are preserved as `.tail`
with explicit recovery metadata. Corruption fails closed. Exports copy finalized
segments, fsync and verify them, then publish a versioned manifest. The active
`.open` segment is excluded; rotate first to include a recent interval.

Replay orders records by durable ordinal, then frame array index. It never sorts
by source timestamps or looks ahead for a later snapshot. `--through` limits
state to an observed ordinal. Every 30 seconds, and on rotation/shutdown, an
online checkpoint stores the deterministic pre-checkpoint state hash. Replay
must match every checkpoint. Raw ordinals identify snapshot/update lineage.

## Reconstruction and uncertainty

Per-outcome books retain exact Decimal prices and quantities, full received
depth, top prices, exact spreads, tick changes, receive freshness and observed
quote-lifetime statistics. Price changes assign quantities rather than adding
them. Snapshots replace depth. Lifetime statistics measure receiver-observed
changes, restart their current interval at snapshots and do not measure exchange
queue lifetimes. Observed values are raw messages; depth/top/spread are
reconstructed; continuity, freshness and lifetime assessments are local inference.

Duplicates remain in raw storage and are counted with bounded recent hashes.
Unknown/binary/malformed frames remain recorded and invalidate uncertain state.
Unexpected identifiers, regressing source timestamps, crossed/locked books,
reported top divergence and stale observations are detected. Snapshot differences
are counted even across gaps, so that counter alone does not establish drift or
message loss. Books are capped at 10,000 levels per side to bound memory.

`internally_consistent` describes the observed snapshot/update lineage.
`sequence_verified` is always false: this contract supplies no reliable per-book
sequence proof. Quiet books older than sixty seconds are stale even if other
assets are active. Gaps invalidate previous books until fresh snapshots arrive.
Each new connection waits for its initial snapshots before checking old stale
state; a bounded deadline detects incomplete snapshots even when updates arrive.
Resynchronization records a gap, reconnects and requests new snapshots.

## Operations and resource bounds

From `/home/charlie/midas-reality`:

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
.venv/bin/python scripts/audit_reality.py
```

Persisted settings are in `deploy/reality.json`; changes apply on restart.
Recording roots must be inside this worktree's `data/recordings`. Exports require
a new directory. Status older than ten seconds is flagged `STATUS_STALE`, including
while a large archive is being verified during startup. Check expected/fresh
books, receive time and service state together. The recorder operates independently
of the dashboard and opens no public port.

The enabled user service uses existing user lingering, restart-on-failure with
ten-second delay, at most five starts/five minutes, 45-second graceful stop,
512 MiB memory maximum, 25% of one CPU, 32 tasks and low scheduling priority.
Home/system access is read-only except the recording directory. To recover from
a terminal start limit, restore the cause, then `systemctl --user reset-failed
midas-reality.service` and start explicitly. Network backoff is bounded exponential
and resets after complete initial snapshots. The transport queue is bounded at
32 frames of at most 1 MiB and applies read backpressure without an application
frame-drop policy. Remote silent losses cannot be ruled out without sequencing.

The initial storage budget is 2 GiB, with 5 GiB free-space reserve, 8 MiB segment
limit plus a bounded record, 300-second configured rotation limit and 30-day
retention horizon. Checkpoints also rotate every thirty seconds. Budget, reserve
or retention exhaustion stops recording. Raw recordings are never automatically
deleted: export/archive the root and configure a fresh isolated root before the
limit. Exported copies have a separate storage cost. Audits stream the archive
rather than holding its raw payloads in memory. This is bounded unattended
recording, not unlimited archival retention.

## Verification and retained limitations

`REALITY_FINAL_REGRESSION.log`: 621 passed, one PostgreSQL runtime test skipped.
The final collector fix is separately covered by 15 focused checks in
`REALITY_FOCUSED_TESTS.log`; unrelated regression source and baseline simulation
identities remain unchanged. Ruff and strict typing pass for the engine.

`tests/test_reality.py` uses genuine captured payload strings with source segment
hash/ordinal provenance in `tests/fixtures/reality/observed.json`. Modified fault
payloads and localhost replay servers are labeled fixtures, not venue captures.
Tests cover discovery, exact updates/removal, duplicates, malformed/unknown
messages, stale/crossed books, tick changes, timestamp regressions, snapshots,
writer exclusion, rotation, budget stop, corruption, incomplete-header/tail
recovery, checkpoint mismatch, no future state, socket close/reconnect, heartbeat,
safe stop, 100-frame slow-writer backpressure, closure/turnover, stale-book restart
and missing initial snapshots. Genuine supervised restart and SIGKILL recovery
were exercised against the production recorder, preserving earlier segments.

`REALITY_ARENA_PRESERVATION.json` verifies all 52,323 retained replay result and
journal hashes and matches the baseline's seven datasets, 45 models and 27
completed tournaments. Laboratory's protected 162,000 results over 18,000 groups
remain intact, its integrity check passes and its production owner lock is held.
The independent recorder is excluded from Laboratory's simulation hash alongside
Arena; the Laboratory and Arena hashes exactly match the Prometheus baseline.
Financial-domain changes still invalidate simulation identity.

`REALITY_LIVE_RESYNC.json` traces a genuine top divergence at ordinal 3618,
explicit gap at 3619 and restoration of six books by fresh snapshots at 3622.
`REALITY_VERIFICATION.json` contains the current finalized-segment manifest,
repeat-replay/checkpoint results, measured counts/growth and service/archive checks.

Early capture defects remain visible in the immutable history: a heartbeat bug
caused extra reconnect gaps; five constraint records (621–625) referenced preceding
constraint records instead of snapshot 619 and have append-only provenance
corrections; a stale-book reconnect loop caused an observation outage and many
metadata/gap records before the final fix. Original bytes are preserved, corrected
provenance is audited and checkpoint hashes remain reproducible. No continuous
coverage is claimed across these outages or planned resynchronizations. Overall
historical growth includes the reconnect storm and must be distinguished from
measured steady growth after the fix.

V2 reconstruction, exchange sequencing guarantees, execution latency, historical
shadow fills, economic calibration, profitability, full UI and analytics research
remain outside Mission 1. Mission 2 may present the observed/reconstructed data
with these explicit uncertainty and coverage limits.

## Mission 1 acceptance

Mission 1 is accepted. `REALITY_COMPLETION_AUDIT.json` maps all twelve mission
sections to inspected implementation, tests and runtime evidence. The final
collector is running with three markets and six fresh outcome books. Its source
identity matches the running process-start record. A scheduled refresh at ordinal
16942 was followed by six genuine snapshots at 16945, with no reconnect storm.

The finalized audit covers 11,031 raw frames and 11,221 feed events over a
2-hour-34-minute observation span, with 296 matching online/replay checkpoints.
The span includes gaps: 1,604 explicit gap records, mostly the corrected reconnect
storm, and a 23-minute historical observation outage. It is not continuous coverage.
Finalized segments occupy 81.69 MB and the whole active root about 81.87 MB against
2 GiB. The healthy post-fix sample preserved 325 new frames over 287.5 seconds,
with 303.5 KB compressed growth: about 91.2 MB/day at that measured rate. Archive
before roughly twenty-two days at this rate; rates vary and the hard limits stop
recording. The recorder uses about 27 MB of memory against its 512 MiB cap.
Protected Laboratory/Arena checks and existing service health pass.

Mission 2 presentation work can begin from this foundation with the documented
coverage and sequence limits. It has not been started. Mission 1 stops here.
