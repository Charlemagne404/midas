# Reality Calibration Laboratory — Mission 2

Mission 2 is active on `project/reality` in `/home/charlie/midas-reality`.
**Gate A is reopened for cached-snapshot timing validation; Gates B–G remain outstanding.
Mission 2 is not ready for handoff.**
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
  --budget-bytes 25769803776 --reserve-bytes 21474836480

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
provide no automatic raw pruning or raw-root rollover. The Gate A candidate
uses a 24 GiB raw budget, 24 GiB archive budget, twenty GiB free-disk reserve
and ninety-day stop horizon; deployment and runtime evidence below determine
whether the candidate is active. Do not mistake a successful archive for
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

Gate A now has bounded capacity and archival/offloading policy, deployment gates,
stratified discovery with selection provenance, verified V1 public metadata,
timing measurements and independent book comparisons. Its accepted engineering
checkpoint and operational limitations appear below.
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


## Gate A implementation and deployment evidence

This section supersedes the initial 2 GiB storage plan. The successful deployment
receipt reports `deployed: true`, and live status confirms the expanded config.
[Verification receipt](REALITY_GATE_A_CHECKS.json),
[preflight](REALITY_GATE_A_PREFLIGHT.json),
[deployment](REALITY_GATE_A_DEPLOYMENT.json) and
[recorded pilot findings](REALITY_GATE_A_PILOT_FINDINGS.json) retain the evidence.

### Panel and protocol contract

`stratified-observation-v1` requests six bounded Gamma pages: high liquidity,
medium liquidity, thin liquidity, unfiltered near-expiry, tagged near-expiry and
a rotating bounded ID page. All responses, request parameters, reception times,
HTTP statuses and raw ordinals are recorded before selection. Each response
candidate gets an eligibility/selection/exclusion decision, including duplicates.
The universe is all responses to those explicit queries, not the entire venue.

Up to eight pilot slots cover high/medium/thin liquidity, fast/stable activity,
near expiry, category diversity and a seeded random eligible control. No apparent
edge or arbitrage filter influences selection. Controls are random within the
bounded recorded universe, not uniform global controls. Activity uses previously
observed update rates when at least two candidates have coverage; otherwise it
uses a labeled daily price-change proxy. Missing measured rates never become zero.
The seed and prior-rate inputs are attached to the decision audit. Unavailable
strata remain unfilled and visible. The pilot is not broad scientific validation;
event identities and correlated market families remain attached to the cohort.

[Gamma market query documentation](https://docs.polymarket.com/api-reference/markets/list-markets)
provides liquidity, expiry and tag filters. The Politics tag (`2`) was independently
queried by slug on 14 October; it supplements the unfiltered expiry page because
that page was dominated by Up/Down markets outside the current Yes/No contract.
Tagged expiry coverage is therefore biased and explicitly recorded. The selection
system permits a different configured tag; expanding category coverage requires
continued measurement, not a claim that eight slots represent the whole venue.

[Official outcome identifier documentation](https://docs.polymarket.com/market-data/prices-order-books)
distinguishes CTF token IDs from V2 position IDs. V2 reconstruction remains excluded:
the public migration-guide route could not be retrieved, and full V2 lifecycle,
payoff and wire behavior have not been independently verified. V1 candidates with
mixed identifiers, ambiguous pairs, missing negative-risk semantics, augmented
other outcomes, invalid ticks/minimum sizes or unknown fee schedules are excluded.

Each selected V1 condition is verified against the unauthenticated CLOB market
response's protocol, tokens, outcome names, condition, lifecycle and negative-risk
flag. Both outcome fee-rate responses are retained. Negative-risk and event-group
identities remain explicit; no cross-condition pairing is introduced. Gamma and
CLOB constraints and lifecycle fields stay separately sourced. Payoff is one
combined collateral-unit claim for the same-condition Yes/No pair before fees,
redemption, settlement and conversion assumptions, not a confirmed dollar profit.

[Published fee guidance](https://docs.polymarket.com/trading/fees) and genuine
responses contain fee-schedule parameters alongside legacy base-fee fields.
These quantities are not blindly interchangeable basis-point rates. The recorder
retains both with provenance; economic research must name the applicable fee
formula/version and exclusions. No fill or private fee execution is observed.

### Timing, reconstruction and independent comparisons

Raw records preserve venue milliseconds, local UTC and monotonic receipt times.
Receipt is application WebSocket dequeue, not hardware network arrival; transport
queue delay cannot be precisely inferred. Immutable timing measurements retain
up to 1,024 recent frame ordinals with persistence begin/completion and reconstruction
completion monotonic times. Clock health is preserved at process start and in those
measurements using Linux kernel synchronization status and reported error bounds;
it is not independent proof of absolute venue clock alignment.

Status exposes bounded live depth (first fifty levels per side, explicit truncation),
source hashes, freshness, both-leg skew, gap counts, per-outcome observed update
coverage, kernel clock health and the latest independent comparison. The full raw
books remain available for reproducible reconstruction; bounded status depth is
not the full archive. HTTP comparisons use one asynchronous public GET every
fifteen seconds, round-robin over the cohort, with a five-second timeout. They do
not pause WebSocket ingestion or submit orders.

A separately implemented REST level parser validates exact decimal prices and
quantities, identities and duplicates. Comparisons distinguish stable local
lineage agreement, divergence, concurrent-update ambiguity, stale/ineligible
state and unavailable/invalid responses. Native hashes and independent depth
hashes are retained. Agreement cannot establish absence of missed messages.
HTTP round trips are not one-way or order-submission latency.

Pilot 1 found empty-side boundary advertisements: zero for no bids, one for no
asks. Independent REST reads confirm empty depth, and the official
[market-channel example](https://docs.polymarket.com/api-reference/wss/market)
shows the ask boundary value. Reconstruction revision 2 accepts those advertisements
without creating any price or liquidity. Revision 1 keeps its historical behavior
and original checkpoint hashes. Genuine captured fixtures retain ordinal/segment
hash provenance for the regression, with artificial controls separately labeled.

Pilot 2 failed deployment: fast markets advertised a new top before matching
public depth changes. Revision 3 marks that interval `advertised_top_pending`;
it is uncertain and ineligible for fully consistent observations. A matching
advertisement alone cannot repair depth. Confirming depth clears uncertainty;
a two-second deadline requests an explicit resynchronization if it remains
unconfirmed. True depth/advertised disagreement still invalidates reconstruction.
The reconstruction revision is recorded at each process start; old revisions
remain replayable rather than rewriting original observations.

A device-write failure now leaves the uncertain segment in `.open` format for
checksummed tail recovery. Further writes fail closed; a partially persisted frame
is never finalized as an immutable segment. The injected partial-write regression
verifies preservation of the preceding complete record and explicit tail evidence.

### Sustainable bounded operations and deployment

[Storage policy](../deploy/reality-storage-policy.json) specifies 24 GiB raw,
24 GiB archive, twenty GiB free-space reserve, ninety-day stop horizon, a daily
verified archival timer and the existing five-minute capacity monitor. Preflight
requires the full remaining raw allocation plus full archive allocation to fit
without consuming the protected disk reserve. At the measured host capacity this
is roughly a 48 GiB commitment, not allocation of all available disk.

There is no automatic raw pruning. Local replication adds a recoverable verified
copy, not off-host redundancy. Before a seven-day capacity alert deadline, use the
archive CLI with an explicitly chosen mounted/off-host destination and verify its
manifest. A new recorder root requires intentional stop, verified finalized history,
retained old-root identity/manifest and reviewed host commitments. Root/ordinal
identities must not be conflated. No off-host destination is configured here.
Finite capacity/retention exhaustion stops safely and requires operator action.

The daily archive service is limited to 256 MiB, ten percent of one CPU, idle I/O
and lower scheduling priority; timeout is thirty minutes. Jobs are exclusive and
resumable. Full integrity/replay verification scales with archive size: a timeout
must be investigated, never presented as a successful archive. The raw collector
runs independently under its existing 512 MiB and 25% CPU limits. Dashboard,
training and archival failures do not own its writer lock.

`scripts/reality_deployment.py verify` freezes the tested recorder source hash.
`preflight` requires an isolated completed canary with exact network settings,
full fresh outcome coverage, matching replay checkpoints, independent agreements,
no repeated consistency loss, sufficient projected storage runway and healthy
production. `apply` rejects changed/expired gates and changed production PIDs,
records restart intent, backs up config, and requires fresh books after restart.
It restores the previous configuration under the tested implementation on failure.

The first deployment rolled back because a forty-five-second health window was
too short for cold replay of the genuine archive under the service's CPU limit.
That failed attempt is retained in
[failed deployment receipt](REALITY_GATE_A_DEPLOYMENT_FAILED.json). Recovery took
roughly sixty seconds before collector initialization; no raw observations were
removed. The corrected deployment window is bounded at 180 seconds (permitted
range sixty to three hundred), with all mutations still guarded. This is a real
operational limitation: cold-start replay time grows with retained history and
must be measured before future large-archive deployments. Recorder restart gaps
are preserved, not claimed as continuous coverage.

### Next gate

After live expanded collection, scheduled archival and mixed-revision historical
replay are verified, Gate B will build decision-time datasets and observable
labels with explicit gap, stale-state, pending-advertisement and ordering censoring.
No Mission 2 prediction model, shadow decision engine or Reality UI is delivered
by Gate A alone. The remaining stages above remain authoritative.


## Gate A checkpoint — accepted engineering scope

[Authoritative runtime and coverage snapshot](REALITY_GATE_A_CHECKPOINT.json)
was produced by `scripts/reality_checkpoint.py` after rollout. The snapshot
contains 39,408 genuine finalized raw frames across twelve historically selected
markets over a 6.09-hour observation span. The active panel has eight V1 markets
and sixteen outcome books. This span includes recorded interruptions and must
not be called continuous coverage. The current process has zero connection
failures; books may be temporarily degraded by stale or pending advertisements.
At the snapshot fourteen of sixteen books were eligible/fresh, with all sixteen
tracked; subsequent healthy snapshots restore sixteen. Reliability here means
preserved ingestion and visible uncertainty, not uninterrupted eligibility.

There are 22 independent stable-local-lineage book agreements and two concurrent
update ambiguities in production's finalized evidence. All remain unsequenced.
The local timing evidence covers 5,890 sampled frames, with maximum measured
persistence 13.75 ms and reconstruction 6.44 ms in that subset. These are local
processing measurements, not submission or venue latency. The successful rollout
needed 66.6 seconds from recorded restart intent to fresh-book acceptance under
the CPU limit. The failed short-window attempt and rollback remain documented.

The five-minute capacity monitor completed successfully with no alerts. Its recent
mixed-panel sample estimates about 283 MB/day and about ninety days storage
runway, capped sooner by the ninety-day retention horizon. This includes pre-rollout
traffic and is not the steady expanded-panel rate. The stricter startup-heavy
pilot projected only 22.5 days; operators must follow changing five-minute forecasts.
Root storage is about 109 MB at measurement, with roughly 218 GB filesystem free.
The live recorder uses about 55 MiB of cgroup memory at the later service check,
well below 512 MiB. Other MIDAS API and frontend services remain running.

The first daily archive job completed successfully: 686 finalized segments,
101,941,399 bytes, verified without deleting originals. Capacity and archival
timers are enabled; no training, dataset or shadow job has been started yet.
The archive intentionally trails the still-growing raw root until its next run.

[Final focused checks](REALITY_GATE_A_FINAL_CHECKS.json) report 53 passes, with
Ruff and strict typing passing. The final broad backend/frontend/browser and
protected-artifact checks belong to Gate G and have not been claimed here.
[Legacy replay](REALITY_GATE_A_LEGACY_REPLAY.log) and
[mixed-revision replay](REALITY_GATE_A_MIXED_REPLAY.log) pass, the latter verifying
691 online checkpoints at that captured interval. Earlier producer records include
six process-start epochs without a complete implementation identity. Their bytes
remain preserved; research must qualify or exclude those epochs rather than
invent source provenance.

[Protected code identities](REALITY_GATE_A_BASELINE_IDENTITIES.json) match the
Prometheus baseline for both Laboratory and Arena. The separate Prometheus
checkout is clean. [Read-only protected audit](REALITY_GATE_A_PROTECTED_AUDIT.json)
confirms Laboratory integrity, its protected 162,000 results over 18,000 groups,
and its active owner lock. The comprehensive protected research-artifact hash audit
is still required at final handoff.

The capacity forecast initially treated deferred HTTP reception timestamps as
clock regressions. The corrected worker separates general receipt reordering from
regressions in synchronously persisted WebSocket frames and measures time bounds
across the whole sample. True sequential frame clock regressions still make the
forecast unavailable. The receipt-order fixture independently covers this behavior.
A transient monitor run failed during that correction; it recovered successfully,
while the recorder PID stayed unchanged. Builder version/hash are now included
in the capacity artifact. Recorder implementation `3b00e8fe…` is reproducible from
commit `74b1dea`; this separate operations-worker correction required no restart.

Gate B is next: reproducible decision-time datasets, observable labels, censoring,
chronological partitions and independent leakage checks. There are no Mission 2
trained-model scores, execution-ground-truth claims or shadow P&L findings yet.


## Extended live validation — Gate A reopened

After the initial checkpoint, the live collector reported four initial-snapshot
timeouts. Inspection of exact source intervals found cached snapshots for the
quiet Bitcoin-reserve market with source timestamps older than preceding observed
updates. Revision 3 rejected those snapshots, so initialization could not complete,
even though the responses were genuine public observations. The original collector
continued recording and repeatedly recovered fresh books; the failures and gaps
are retained. Initial short-canary acceptance was therefore insufficient for this
longer-run condition.

Revision 4 allows a new received snapshot after an explicit gap to establish an
observed lineage, while retaining `timing_uncertainty` and the prior source-time
floor. It does not claim that a regressing source timestamp proves venue freshness.
The qualifier survives further older snapshots and clears only on sufficiently
new, matching depth evidence. Snapshots regressing within uninterrupted lineage
remain invalid. Status reports `DEGRADED_SOURCE_TIMING` while such qualifiers exist;
datasets must exclude or explicitly qualify these decisions. Initialization also
accepts confirmation of a current-connection snapshot on a later frame, never
reusing a prior connection's snapshot.

Genuine captured regression fixtures preserve raw ordinals, segment hashes and
the explicitly derived prior book. An isolated six-minute canary now exercises
scheduled refresh and quiet-market behavior before a further gated deployment.
The running recorder remains on the committed revision 3 implementation until
that canary finishes and the gate passes. Gate B has not started.
