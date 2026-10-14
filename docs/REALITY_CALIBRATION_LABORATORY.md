# Reality Calibration Laboratory — Mission 2

Mission 2 is active on `project/reality` in `/home/charlie/midas-reality`.
**Gates A and B are accepted engineering checkpoints; Gates C–G remain outstanding.
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


## Extended live validation — initial Gate A acceptance reopened

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


## Revised Gate A acceptance — reconstruction revision 4

The longer pilot and gated production repair are complete. See
[revision 4 checks](REALITY_GATE_A_R4_CHECKS.json),
[preflight](REALITY_GATE_A_R4_PREFLIGHT.json),
[deployment](REALITY_GATE_A_R4_DEPLOYMENT.json), and
[current checkpoint](REALITY_GATE_A_R4_CHECKPOINT.json).
This supersedes the earlier acceptance for startup timing behavior; earlier
snapshots and failed attempts remain preserved.

The 362-second canary captured 796 genuine frames, verified twelve replay
checkpoints, observed two cross-gap snapshot source-time regressions, and finished
with sixteen fresh books and zero connection failures. It recorded 23 independent
book agreements, one stale-local comparison and five book resynchronizations.
Resynchronization limits use the original engineering intensity bound of 1.5 per
minute, scaled to the longer duration; the earlier nine-in-two-minutes pilot still
fails that bound. These are bounded operational tests, not scientific performance
validation or sequencing proof.

A snapshot timestamp earlier than a preceding update is directly observed;
"cached snapshot" is operational shorthand. Caching or publisher timing differences
could explain it, but exact venue ordering is not verified. The four-millisecond
captured example is sufficient to break an overly strict initialization rule;
it does not identify one-way latency or private execution behavior.

The deployment gate supports an explicitly requested cached-snapshot repair
only when the isolated canary actually observed the regression case, production
has the same reviewed config, and its only inconsistent books are stale or
source-timestamp regressed with the matching initialization error. Other degraded
conditions remain blocked. The final attempt happened during a healthy production
snapshot and required no exception to the healthy-state gate. All restart intent,
source hashes and prior config are retained. Fresh-book acceptance took 77.3 seconds.

Production now runs the sealed recorder implementation `9231e11c…` from commit
`82e9fa4`. At the revision 4 checkpoint, it has zero connection failures, sixteen
fresh books, and seventy current-process independent book agreements. It has also
encountered and correctly qualified a cross-gap source-time regression in real
operation. Timing-uncertain intervals remain visible and require dataset exclusion
or explicit qualification; this does not remove uncertainty to improve model scores.

The revised finalized catalog contains 44,244 genuine frames across fifteen
historically selected market IDs over 6.80 hours, including gaps and related market
families. The current cohort remains eight markets. Mixed-revision replay verified
772 checkpoints at its captured cutoff. Final focused verification reports 55
passes; strict typing and lint pass. The revised checkpoint command supports explicit
deployment/check receipt paths so it cannot silently associate a new PID with an
old rollout receipt.

Storage is roughly 128 MB at measurement. The monitor's recent mixed sample now
estimates about 586 MB/day, up from the earlier sample, with no capacity alerts;
its changing forecast must be monitored. Raw and archival budgets remain 24 GiB
each with twenty GiB disk reserve and ninety-day retention stop. The six-minute
startup/refresh-heavy pilot offers a stricter estimated runway of about forty days.
Daily archival is still a bounded, non-destructive local replication job; off-host
redundancy and indefinite local retention are not claimed.

Gate A's scoped engineering requirements are now verified. Gate B starts next,
with source-time qualifiers, missing historical producer identity, gaps, stale
states, partial complementary observations and future-observation missingness
explicitly incorporated into data acceptance and labels. No Mission 2 real-data
model, shadow campaign, economic conclusion or native Reality dashboard is claimed
to be delivered by this collection checkpoint.

## Gate B — foundry implementation in progress

The recorder continues on its sealed revision 4 code, independently of the new
research modules. No recorder restart was performed for dataset development.
Raw inputs are finalized, immutable segment prefixes; the active `.open` file is
excluded. Research owns a separate derivative root and builder lock.

`midas.reality.foundry` builds content-addressed datasets from a frozen source
manifest, versioned specification and builder/reconstruction code hashes. Each
example contains segment SHA256, raw compressed-record SHA256, canonical-record
SHA256, byte offsets, ordinal, source producer identity, parser revision, decision
UTC/monotonic times, feature references, label references and actual future delays.
Builder source is copied into the artifact for later reproduction. Complete
source ordering, record/file/catalog integrity and all online checkpoints are
verified before publication; partial derivatives are not research datasets.

Features include both-leg best prices, spread, bounded displayed depth, total depth,
quantity-dependent full-book acquisition cost, imbalance, freshness, quote age,
recent observed updates, price/depth changes, public trades, categories/event IDs,
reported expiry, tick/minimum-size/fee metadata and cross-outcome reception skew.
Hypothetical quantity and capital are separately labeled assumptions. Displayed
cost excludes fees and conversion; the fee parameters are not silently applied
as verified private execution charges.

Labels are versioned public measurements: pointwise original-price presence,
aggregate depth at original quotes, adverse ask movement, discrepancy persistence,
displayed acquisition cost, data/rule disruption and quoted exit-value change.
They never represent an actual or hypothetical confirmed fill. Constituent orders
and our hypothetical queue position remain unidentified. If there was no initial
discrepancy, opportunity persistence is not applicable, not a negative example.

A later label requires both outcome depth observations at/after the requested
horizon, within the smaller of configured tolerance and 25% of that horizon, with
bounded skew and valid freshness. Actual delays are attached to each leg. There
is no interpolation between events or carrying an old quiet leg forward as proof
of a new observation. Missing future data, gaps, stale/inconsistent books,
source-time qualifiers, independent-comparison divergence, tick changes and
reported expiry cause explicit censoring. A known empty future ask side instead
supports an observed negative quote-presence label and zero aggregate depth;
undefined movement/acquisition targets stay unavailable.

Partitions are chronological train/validation/test, with embargoes covering label
horizons and tolerance. Their windows include dynamic book/snapshot and rolling
feature inputs. Related event/condition/negative-risk aliases are merged into
connected families; horizon variants and family/time dependence groups cannot
straddle partitions. Conflicting boundary groups become embargoed. A separate
held-out-family view excludes entire held-out families from training/validation.
Cross-day generalization is explicitly unavailable when only one day is present.
Static, already-known protocol metadata can be shared across temporal partitions;
it does not stand for independent market observations.

The final-test ledger requires a frozen validation-selected candidate/weight list
and baseline controls before opening a period. Exact interrupted evaluations may
resume; altered plans, overlapping opened periods and repeated consumed-period
promotion are rejected. Structural/source integrity audits do not fit models or
select hyperparameters on test outcomes. Model-training integration follows in
Gate D; no fitted real-data model is claimed at this stage.

The independent verifier checks chronology, references, versions, censoring,
market-pair semantics, effective timing, unknown execution truth and grouped
partition separation. A second implementation reconstructs the raw prefix and
checks quote/depth/cost/movement labels using independent arithmetic, including
rehashed label corruption and skipped/selectively censored future observations.

### Initial real-data development results

A six-minute genuine recording produced 1,712 examples, with 108 observed public
measurements and 1,604 censored. The independent raw-source audit passed all 108
observed labels and 964 unique record references. This small development artifact
has no performance or economic validation claim.

The primary frozen recording prefix produced 13,216 examples in 333.5 seconds
under a 20% CPU limit: 767 observed public measurements and 12,449 censored.
Partitions contain 8,086 training, 1,902 validation, 3,144 test and 84 embargoed
rows. They cover one UTC day. Test coverage includes ten market IDs, seven related
families and 236 family/time groups; these counts do not establish independent
multi-day validation. Most censorship reflects unavailable qualifying future
observations, followed by freshness failures and recorded resynchronizations.

The primary-source independent audit and a second generation using the artifact's
frozen code bundle are running as bounded user services:
`midas-reality-gate-b-audit.service` and
`midas-reality-gate-b-regeneration.service`. Gate B acceptance remains open until
those finish and their evidence is inspected. Dataset generation itself completed
successfully. Current recorder PID remains 2288376; ingestion was not stopped.

Example commands:

```bash
.venv/bin/python -m midas.reality.foundry build \
  --root data/recordings/reality --output data/research/reality/datasets \
  --spec data/research/reality/gate-b-spec.json \
  --source-manifest data/research/reality/gate-b-source-manifest.json
.venv/bin/python -m midas.reality.foundry verify --root <dataset-directory>
```

`verify` performs the structural/contract audit. `audit_public_labels` additionally
reads the frozen raw prefix and independently checks observed measurements.
Raw originals are never pruned or changed by either operation. Budget/reserve
failure removes only the builder's unpublished disposable temporary directory;
interrupted published artifacts remain immutable and checksum-verifiable.


## Gate B acceptance — source audit and frozen-code regeneration

Gate B is accepted. [Dataset evidence](REALITY_GATE_B_DATASET.json),
[independent source audit](REALITY_GATE_B_SOURCE_AUDIT.json),
[reproducibility proof](REALITY_GATE_B_REPRODUCIBILITY.json),
[operational checkpoint](REALITY_GATE_B_CHECKPOINT.json) and
[test output](REALITY_GATE_B_TESTS.log) record the current evidence.

The independent implementation checked all 767 observed public measurements
and 46,638 distinct raw references. It verifies exact decision-time prices,
quantities, cost and exit-value arithmetic, producer provenance, uncertainty
intervals and first qualifying future observations. It completed in 570.1 seconds
under a 20% CPU quota, with about 366 MiB peak memory. This is a research worker,
not part of the ingestion path.

A second build used the artifact's own frozen source bundle, identical raw prefix
and spec. It reproduced dataset ID, example-file SHA256, chronological partitions
and effective coverage exactly. Generation took 334.5 seconds, compared with
333.5 seconds for the original run. Generated timestamps and elapsed times are
operational metadata, not mutable scientific inputs to the dataset identity.

The full focused suite reports 73 passes; lint and strict typing pass. Raw
observations and catalogs were not changed. Collector PID 2288376 remained active
through construction, audit and regeneration. The dataset, audit and regeneration
services have terminal successful states. Continuous capture, capacity monitoring
and daily raw archival remain enabled. No training or prospective shadow campaign
is active yet.

The 13,216 rows are not 13,216 independent successful observations. Only 767 have
qualifying measured futures; 12,449 are censored. Observed test measurements by
requested horizon are 44 at 100 ms, 37 at 300 ms, 45 at 1,000 ms and 48 at 5,000 ms.
This is small, dependent, single-day evidence. Model eligibility and confidence
must reflect these counts; Gate B does not establish prediction skill or economic
usefulness.

The final-test access ledger is implemented but no model-evaluation period has
been opened. Frozen validation-selected weights and controls are required before
Gate D opens a final test; consumed or overlapping periods cannot be reused for
new promotion. The structural and source-integrity audits above do not select
models or tune thresholds on held-out outcomes.

Known limits remain: unsequenced public feed, qualified source timestamps,
unsupported V2/Up-Down/augmented Other contracts, incomplete early producer
identity, no private execution evidence and no cross-day generalization. Code
bundles and raw-record references make later scientific review reproducible.
Gate C is next: observed distribution calibration, multiple explicit execution
assumptions, uncertainty bounds and preserved-simulator comparisons.
