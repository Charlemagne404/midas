# Reality Calibration Laboratory — Mission 2

Mission 2 is active on `project/reality` in `/home/charlie/midas-reality`.
**Gate A is in progress; Mission 2 is not ready for handoff.**
Prometheus remains at `8acab2298632eb04fbe5183fbe54f8e6f97a8fdb` in the separate
`/home/charlie/midas` checkout. Atlas is deferred. No trading capability is authorized.

## Architecture and scientific boundary

The existing standalone collector owns immutable framed/zlib raw observations,
checksummed segment catalogs and deterministic reconstruction. It runs without
the API, dashboard or research workers. See [Mission 1 operations](REALITY_ENGINE.md)
for verified feed contracts, V1 pair validation, resynchronization and timing
limitations. The new operations worker only reads finalized segments and atomic
status snapshots; it never opens a writer, modifies catalogs, or reads the
active segment. Capacity output lives outside the recording root.

Observed market data, derived measurements, estimated execution, simulator
assumptions and unknown counterfactuals must stay distinct. Displayed liquidity
and quote persistence do not prove hypothetical fills. Exchange sequencing,
private queue position, submission latency and hypothetical market impact remain
unobserved. There are no Mission 2 prediction or profitability findings yet.

## Storage operations implemented

From the Reality worktree:

```bash
.venv/bin/python -m midas.reality.operations capacity \
  --config deploy/reality.json --output data/recordings/capacity.json

.venv/bin/python -m midas.reality.operations archive \
  --config deploy/reality.json \
  --output data/recordings/reality-archive-mission2 \
  --budget-bytes 2147483648 --reserve-bytes 21474836480

systemctl --user status midas-reality-capacity.timer
journalctl --user -u midas-reality-capacity.service -n 50 --no-pager
```

The enabled timer measures every five minutes with 128 MiB memory maximum,
10% of one CPU, idle I/O priority and a sixty-second runtime limit. Research
must continue to receive less priority than ingestion. The monitor reports
recent raw payload rate inputs, compressed plus catalog growth, source manifest
hash, filesystem free space, budget headroom, retention deadline and alerts.
Forecasts require at least sixty seconds of observations without regressing
reception timestamps. The last 120 completed segments bound its sample. The
forecast includes gaps and metadata, so it measures storage consumption rather
than claiming uninterrupted market coverage. Growth rates can change abruptly.

Warnings enter the service journal for low budget, disk reserve, projected
exhaustion within seven days, retention exhaustion, stale status and insufficient
rate evidence. No external notification delivery is configured. A failed monitor
job remains visible in systemd; stale capacity reports must not imply health.

Archives use an exclusive archive-job lock, source-root identity, per-record and
whole-file verification, fsynced temporary copies, and atomic publication.
Full ordinal and replay-checkpoint validation precedes manifest publication.
Interrupted copies resume; existing corrupt archives fail closed. Source bytes
and catalogs are never changed. The active segment is deliberately excluded.
Use SIGUSR1 only when an intentional rotation is needed before archival.

Archive destinations have explicit budgets and free-disk reserves. A local copy
consumes additional host disk and is not off-host redundancy. Current operations
provide no automatic raw pruning, raw-root rollover, or removal of the recorder's
2 GiB budget or thirty-day stop horizon. Do not mistake a successful archive for
reclaimed collector headroom. Disposable derived data will have separate roots
and reproducible source manifests; no derivative retention job is implemented yet.

## Initial storage checkpoint — 14 October 2026

Authoritative snapshot: [storage checkpoint](REALITY_MISSION2_STORAGE_CHECKPOINT.json).
Focused validation: [test output](REALITY_MISSION2_STORAGE_TESTS.log).

- Recorder PID 2033047 remained running without restart; three V1 markets and
  six fresh books, 19,696 frames in the current process, zero current-process
  connection failures. Historical gaps remain in the source archive.
- Root roughly 99.8 MB. Recent 120-segment sample spans 3,645 seconds and 9,342
  frames; compressed and catalog growth roughly 189 MB/day. At that measured
  rate the 2 GiB recorder budget has about 10.9 days remaining. This estimate
  replaces the initial Mission 1 sample's lower rate; it is not a guarantee.
- About 218 GB free disk at measurement, five GiB current recorder reserve,
  about 73 MB recorder cgroup memory. A separate archive uses a twenty GiB
  free-disk reserve and two GiB maximum budget.
- 627 finalized segments, 99,072,439 bytes, were copied and validated against
  source checksums, ordinal continuity and replay checkpoints. No originals
  were deleted. The manifest retains provenance and its verification timestamp.
- 24 recorder/operations tests pass; Ruff and strict typing pass for the new
  worker; systemd unit verification passes. Tests use artificial storage fixtures
  and existing provenance-labeled captured feed fixtures, not synthetic fills.
- Runtime inspection caught a monitor timing race: a report sampled its clock
  before scanning but read newer collector status afterward. The clock is now
  sampled after reading status; an independent slow-sampling regression covers
  this error. The deployed monitor completed successfully with no alerts.
- The Prometheus checkout has no working-tree changes. This checkpoint does not
  repeat the comprehensive protected-archive audit required at final handoff.

## Remaining stages and acceptance evidence

Gate A still needs sustainable bounded capacity/rollover and offloading policy,
collector deployment gates, representative discovery with selection provenance,
verified protocol metadata, timing quality and independent book comparisons.
Changes to the running collector require intentional documented deployment;
frontend work must not restart it. Original observations must remain recoverable.

Gate B will define immutable datasets, decision-time features, measurable labels,
censoring, chronological partitions, grouped identities, embargoes and leakage
checks. Raw hash/ordinal lineage must remain attached to every example.

Gate C will compare real distributions with preserved synthetic baselines and
publish optimistic, intermediate, conservative and stress assumptions. Unsupported
private execution quantities remain assumptions or unknowns.

Gate D will train lightweight controls and supported observation targets, preserving
train-only preprocessing, held-out evaluation, dependence-aware uncertainty and
eligibility checks. Insufficient coverage must block scientific claims without
blocking implementation of the pipeline.

Gate E will freeze policies, thresholds, feature versions, controls, market rules,
analysis plans and future periods before starting durable shadow decisions and
outcome follow-up. No order submission is permitted; economic results are hypothetical.

Gate F will build the native Reality overview, market explorer, historical and
opportunity observatories, calibration, model research, shadow, forward-validation
and collector-operations views using bounded backend queries and real evidence.

Gate G will verify backend/frontend/browser behavior, storage, research integrity,
protected archives and operational jobs, then commit coherent work on the Reality
branch. Comprehensive architecture, labels, calibration, training, economics,
scientific findings, dashboard instructions and future coverage requirements will
be documented here as implemented and verified. None of those later gates is
claimed complete by this initial storage checkpoint.
