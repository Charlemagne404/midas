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

## Gate C — observational calibration and execution uncertainty

The calibration layer is separate from the Prometheus simulator and protected
experiments. `midas.reality.calibration` accepts a checksum-verified Foundry
artifact and uses only the intersection of chronological training and
market-generalization training. Validation, final-test and held-out families
cannot contribute to its empirical kernel or economic sensitivity calculations.
Its identity includes the dataset/row hashes, critical decoder and measurement
code, the preserved synthetic generator code, fixed resampling seed and explicit
execution assumption manifests. A 32 MiB report limit, 256 MiB derivative-root
budget and 20 GiB host reserve bound publication.

Run a bounded worker, separately from collection:

```bash
systemd-run --user --unit=midas-reality-calibration-example \
  --property=WorkingDirectory=/home/charlie/midas-reality \
  --property=CPUQuota=20% --property=MemoryMax=768M \
  --property=Nice=15 --property=IOSchedulingClass=idle \
  /home/charlie/midas-reality/.venv/bin/python -m midas.reality.calibration \
  --dataset data/research/reality/datasets/23201960592577e4cb280c5f3dc1fb64d75e3b12bacb45d347cc2ae32472242c \
  --output data/research/reality/calibration
```

The report includes horizon and selection-role distributions, receiver quote
age, spread, displayed depth, update intensity, skew, causal lookback changes,
public future measurements, grouped sample coverage and missingness. Initial
metrics count each decision anchor once, rather than once per horizon variant.
Persistence means original-price presence at a later observation point. A price
can disappear and reappear; these measurements are not continuous survival.

An additional checksum-verified raw-prefix pass measures best-ask spells and
spread/depth changes inside valid receiver-observed lineages. Gaps, stale limits,
independent divergences, snapshot/tick resets, clock regressions and uncertain
books right-censor spells. Empty-ask intervals are not quote lifetimes. All
within-frame changes remain unresolved, and the unsequenced stream may omit
venue events. Completed and censored durations are reported separately; a
completed-only distribution must not be interpreted as the population lifetime
law. Deferred HTTP timestamps are separate from sequential WebSocket clock
checks. Raw online checkpoints are verified during this pass.

Each horizon reports measured persistence, unknown counts, and worst-case
missing-outcome identification bounds. Exploratory bootstrap intervals resample
families then time blocks, preserving variants in each block. These intervals
cannot correct informative missingness, selection bias, unobserved events or
single-day coverage. Degenerate measured intervals such as [1,1] therefore do
not imply certainty. The joint observational kernel retains matched public
labels and their dependence groups. `calibrated_kernel.load` requires an
externally pinned artifact hash. `sample` keeps censored draws unknown and
rejects unsupported horizons; it cannot interpolate a private execution process.

### Explicit scenario contract

All scenarios use original observed ask limits and a causal initial filter.
Future evidence changes only follow-up measurements, never the initial decision.
No scenario estimates actual fill probability, order queue position, submitted
order latency or private acknowledgment behavior.

| Family | Requested delay | Displayed-depth fraction imposed | Friction per acquired share | Initial age / skew limits | Follow-up and stress assumptions |
| --- | ---: | ---: | ---: | ---: | --- |
| Optimistic | 100 ms | 1 | 0 | 5,000 / 250 ms | Initial liquidity assumed available; future evidence not required |
| Intermediate | 300 ms | 0.8 | 0.001 collateral unit | 1,000 / 100 ms | Qualifying public future required; original-price retained aggregate depth bounds support |
| Conservative | 1,000 ms | 0.5 | 0.005 collateral unit | 300 / 25 ms | Stronger timing and liquidity haircut; unknown follow-up remains unknown |
| Stress | 5,000 ms | 0.25 | 0.02 collateral unit | 5,000 / 250 ms | Qualifying future required; impose disappearance of the cheaper leg and recovery failure |

Each configuration has a separate SHA-256 identity. These delays and fractions
are imposed research choices, not calibrated submission or fill distributions.
Fractional partial inventory is permitted after a request satisfying the reported
minimum. One leg can have more imposed inventory than its complement; matched
payout and unmatched terminal-payoff ranges are accounted separately. The stress
case deliberately retains the more expensive leg. Recovery failure is explicit,
not an inferred real liquidation. Preserved Prometheus broker/recovery machinery
continues to exist unchanged alongside this bounded observational contract.

Economic sensitivity compares identical initial candidates across the four
families at quantities 5, 10 and 25, and capital budgets 10, 100 and 1,000
collateral units. Same-anchor horizon variants must have identical feature hashes.
Unknown fees/minimums, unsupported protocols, insufficient initial depth, timing
violations and capital failures abstain. Future book absence remains unknown.
Fees are applied once, and empty imposed inventory incurs no redemption charge.
No order is submitted and no hypothetical outcome is reported as realized money.

The declared fee curve version uses the recorded market schedule only when its
exponent is 1, taker-only flag is true and rate is bounded. Disabled fees are
explicitly zero. The separately recorded legacy `base_fee` field is never
reinterpreted as basis points. The public curve is shares × rate × price ×
(1 − price), with a conservative 0.00001 reserve per nonzero leg. This is a
hypothetical cost convention, not an invoice or proof of protocol interoperability.
Source checked 2026-10-14: [official Polymarket fees](https://docs.polymarket.com/trading/fees).
No maker rebate is assumed. Common sensitivity defaults impose seven settlement
days, 10% annual financing, 0.01 redemption cost and a collateral-value factor
of one. These are editable assumption fields; neither settlement delay nor
collateral conversion value is established by the feed.

### Preserved simulator comparison

The comparison regenerates all 19 original Laboratory families at seeds 0–15
(304 synthetic controls) without reading or writing historical experiment files.
The report pins their complete scenario-bundle hash and unchanged original
execution presets. Equal family weighting is disclosed; this is not the weighted
historical distribution of every Prometheus run. It compares original-price
persistence, discrepancy presence, disappearance, initial spread and top depth.
Original simultaneous leg updates, exact synthetic future states, imposed
settlement, private matching and acknowledgments are described as non-equivalent
to qualified real receiver observations. Real-source and synthetic evidence are
separate fields throughout.

### Gate C findings and evidence limits

Accepted calibration `8e29bed2af533d3e2ee1640c5c9e876d3323480d8b2d579b454b6c9768aa2500`
uses 7,970 training horizon rows at 1,993 anchors, eight markets, seven connected
families, 725 family/time blocks and one UTC day. Five families and 224 blocks
have measured futures: 500 measurements and 7,470 unknown outcomes. Every
measured original-price persistence target is true. The measured subset rate
of 100% has an all-outcome identification range of **6.27%–100%**. Horizon-specific
ranges are 4.11%–100% at 100 ms (82 measured), 4.52%–100% at 300 ms (90),
7.33%–100% at 1,000 ms (146), and 9.14%–100% at 5,000 ms (182). These are
missing-outcome bounds, not confidence in an execution probability.

The accepted training cohort contains no initially supported positive theoretical
pair discrepancy, even before fee deductions. All 1,993 matched candidate
anchors abstain in each of the four scenario families at quantity five/capital
100; the larger sensitivity grid also exposes reasons and coverage. There are
no real-data hypothetical positive-position outcomes to report. Fixture arithmetic
proves partial positions, fee accounting, stress loss and unknown follow-up;
fixtures are explicitly artificial and never counted as market evidence.

The receiver-prefix pass processed 63,916 raw records and verified 841 online
checkpoints. It found 4,339 right-censored spells and zero trustworthy completed
best-ask spells. Therefore the available prefix does not identify a completed
quote-lifetime distribution. There are 38,571 valid aggregate-depth transitions;
retained original-price depth has mean ratio 0.9838 across 1,000 leg measurements,
with minimum 0.002836 and median one. Observed quality barriers and missingness
prevent extrapolating this to continuous order survival or fill rates.

In the 304 regenerated synthetic controls, apparent discrepancy prevalence is
83.55% at 100 ms and 69.41% at 1,000 ms, versus no initial discrepancy in accepted
real training anchors. Median initial top-ask depth is 16 synthetic shares versus
1,691 observed shares. Both median spreads are approximately 0.01, but observed
spread support ranges from 0.001 to 0.09; synthetic initial spreads are concentrated
at 0.01 (with the rounding family at 0.0001). These expose generator/cohort
mismatches. They do not establish venue-wide prevalence or causal execution
advantage; the real panel and equal-weighted synthetic families are selected
populations.

`docs/REALITY_GATE_C_CALIBRATION.json` contains the published report summary,
artifact hash, exact assumptions and economic grid. The full derivative report
retains 500 joint observable kernel rows with source example IDs. A pinned-hash
smoke run sampled 100 draws at 300 ms: 97 censored and three observational,
with approximately 7.0 ms mean Python inference time including report hashing.
That is an engineering check, not a new experiment or probability validation.
Modified artifact bytes were rejected. Recorder operation was unaffected.

The first research run was intentionally stopped before publication after review
caught that deferred HTTP timestamps must not trigger sequential WebSocket clock
regression. A fixture now checks this distinction. The second completed artifact
was superseded after zero-inventory redemption accounting was tightened; that
version remains an explicitly superseded derivative. The accepted build took
167.50 seconds, 33.75 CPU seconds and 183.5 MiB peak memory under a 20% CPU quota
and 768 MiB memory cap. No raw observations were deleted or rewritten.

Focused Reality verification passes **91 tests**. Ruff passes and strict mypy
passes across 21 Reality sources. Independent fixture assertions cover receiver
spells, empty asks, gap censoring, missingness bounds, grouped coverage, fee
rounding, no double charging, partial terminal-payoff bounds, zero-inventory
accounting, capital/minimum checks, stress recovery failure, causal decision
isolation, matched horizons, deterministic kernels and unsupported interpolation.
The full backend/frontend/browser checks remain for Gate G.

The final-test access ledger remains unopened. Gate C does not validate a model,
a population execution law, any private fill mechanism or profitability. Gate D
is next: train supported observation targets with training-only preprocessing,
chronological evaluation and simple controls, while explicitly rejecting
scientifically unsupported promotion. Prospective shadow campaigns and the
native Reality dashboard remain outstanding.

A separate bounded regeneration completed in 167.70 seconds (33.80 CPU seconds,
184.5 MiB peak memory). Calibration identity, all measurements, assumptions,
bootstrap results, synthetic comparison, joint kernel and economic sensitivity
are identical. Only the measured build duration differs; file hashes and the
stable semantic report hash are recorded separately in
`docs/REALITY_GATE_C_REPRODUCIBILITY.json`.

At the Gate C operations checkpoint, the recorder remained PID 2288376 with no
Gate C restart and zero automatic restarts, eight markets, 16/16 fresh books,
zero timing-uncertain books and zero connection failures in its active epoch.
Its 56,663 frames are active-epoch frames, not the entire preserved archive.
Raw ordinal was 119,245 and storage approximately 207 MiB. Five independently
observed divergences remain in the evidence alongside 532 qualified agreements;
agreement does not prove sequencing or full continuity. A brief cohort-refresh
`AWAITING_DATA` state recovered to 16 fresh books without restarting collection.

Capacity monitoring and daily verified archive timers remain active. Recent
capacity forecasts are variable (about 1.3 GB/day at the checkpoint, approximately
19 days to the 24 GiB raw allocation); alerts and explicit stops remain in force,
with a separate 24 GiB archive allocation and 20 GiB host reserve. The filesystem
has approximately 200 GiB free and the host approximately 10 GiB available RAM.
Both accepted calibration jobs are terminal successful; no training or shadow
worker is running yet. The protected main worktree is clean at the Prometheus
baseline, and Laboratory/Arena code identities remain unchanged. Full protected
archive verification remains part of Gate G, not a claim newly made by Gate C.
Current service, raw-prefix, capacity and protection evidence is recorded in
`docs/REALITY_GATE_C_CHECKPOINT.json`.

## Gate D — genuine observation-target training

Reality now has a separate Arena adapter for genuine Foundry datasets. It reuses
Arena's two-hidden-layer PyTorch architecture with a 25-input Reality schema;
it does not reinterpret historical synthetic completion labels or reuse their
weights as observation-trained models. Protected Arena/Laboratory code and
archives are unchanged. Inputs include prices, logarithmic displayed quantities,
spread/missingness, receiver age/skew, quote age, update intensity, imbalance,
causal lookback changes, tick, reported expiry/liquidity, quantity and horizon.
Market/family identities and future measurements are excluded from inputs.
Categories, selection roles, families, markets, horizons and days are evaluation
slices. Day coverage must match the actual decision timestamp.

The model target version is `reality-model-targets-v1`:

- `quote_persistence`: original-price presence at the declared future horizon.
- `depth_retention`: minimum across legs of retained original-price quantity
  divided by initial top-ask quantity, bounded to [0,1].
- `adverse_ask_movement`: measured adverse change in the paired best asks.
- `opportunity_persistence`: applies only to an initially supported theoretical
  discrepancy; other decisions are not applicable, not unknown or negative.
- `market_disruption`: known public-data freshness/connectivity/reconstruction
  deterioration within the horizon. This is a data-quality target, not a private
  execution, monetary-loss or fill target. Known deterioration can be measured
  even when price futures are censored; otherwise missing targets remain unknown.

Preprocessing uses the intersection of chronological and family-held-out
training partitions only. Standardization and support envelopes use training
inputs; fitting assigns equal total weight to each training family/time block.
Validation alone selects fixed candidate families and MLP checkpoints. Constant
controls use a declared smoothed training base rate for classifications or a
weighted training mean for regression. Fixed heuristics are explicitly unfitted.
Learned classifiers/regressors require target variation. Logistic regression,
Ridge and a shallow tree precede any MLP. An MLP is considered only after a
lightweight learner improves the validation control by at least 2%, with at
least 100 known training and 50 validation targets. The fixed small network has
16 hidden units per layer, a fixed seed, at most 40 epochs and early stopping.
No larger architecture or hyperparameter sweep was added.

Portable JSON parameters preserve preprocessing, supported ranges, native
estimator coefficients/tree/MLP weights, curves, seeds, configuration, input and
target versions, numeric-library versions and source/dataset identities. Native
and portable estimator predictions are independently compared before publication.
Weight and metadata hashes bind each model ID. Loading detects weight, registry,
metadata, version and support corruption; inference rejects incompatible
protocol/horizon/quantity or inputs outside the training envelope. Experimental
predictions explicitly condition on measurable public targets, expose no actual
fill probability and do not activate a decision policy.

### Frozen development and final-test evidence

Accepted genuine run:
`9f593b0e68c61c5a8eabf3b01b7ad38c9e1df27436bd041a55a505c995a0a9f9`.
It uses the independently audited Gate B dataset at the 1,000 ms horizon,
with 1,993 accepted training anchors, 476 validation anchors and 786 final-test
anchors. All are from one UTC day. Price/depth targets have 146 known training,
30 validation and 45 test observations. Disruption has 335 known training
(146 negative/189 positive), 95 validation (30/65) and 226 test (45/181) targets.
The remaining eligible outcomes are unknown. Quote persistence is one-class;
adverse movement is constant zero; opportunity persistence has no applicable
examples. Those targets cannot support discriminative learned models here.

The run publishes **13 artifacts: eight controls and five learned models**.
The learned models are logistic/tree/MLP for disruption and Ridge/tree for depth
retention. The MLP passed the pre-test validation trigger but did not win
validation. No additional network was fitted for model-count purposes.

| Supported target | Validation-selected development candidate | Frozen-test metric | Relevant controls/learners |
| --- | --- | ---: | --- |
| Disruption | Shallow tree | Brier 0.30910 | Constant 0.19821; logistic 0.41306; MLP 0.25121 |
| Depth retention | Fixed unchanged-depth heuristic | MAE 0.00490 | Constant 0.01905; Ridge 0.05657; tree 0.03071 |
| Quote persistence | Smoothed constant control | Brier 0.0000457 on 45 positive-only targets | No evidence of discrimination or population calibration |
| Adverse movement | Zero constant control | MAE 0 on 45 zero-only targets | No learned variation or generalization claim |
| Opportunity persistence | None | Not applicable | No supported initial discrepancy |

The disruption tree's validation Brier was 0.08373, but its frozen-test Brier
is worse than the constant control. Learned depth models also lose to the fixed
heuristic. These are negative development findings, not grounds to select a
new candidate using the opened test. Full Brier/log loss/calibration, regression
residual/tail errors, matched baseline skill, training-support coverage and
market/family/category/role/day slices are in `docs/REALITY_GATE_D_TRAINING.json`.
Intervals resample family/time blocks and are explicitly exploratory and
conditional; shared feed/venue dependence, one-day coverage and informative
missingness prevent independent population claims. Regression prediction
intervals remain unsupported. Prediction accuracy is not economic usefulness.

All candidate weights, controls, validation selections, target definitions,
threshold 0.5 and the analysis plan were frozen before test access. Evaluation
`fc18c7493b427fba2856cd33c3149ce26694ca62ddb83a8e4ec53dd34a4e2415`
is consumed in the shared `data/research/reality/evaluation-ledger`. No test
threshold retuning or subsequent promotion against that period is allowed.
Known test observations from entirely held-out families are separately reported.
Cross-day generalization is unavailable. There is **no scientific champion and
no eligible decision-policy model**.

Eligibility requires seven UTC days, sufficient measured family/time blocks and
families, both classes when applicable, at most 30% unknown targets, meaningful
validation/control improvement, positive frozen-test improvement with grouped
paired uncertainty, acceptable conditional calibration, compatible reproducible
inference and matched hypothetical decision usefulness. Current candidates fail
several gates, including missingness and temporal coverage. Technically usable
experimental probes are distinct from policy eligibility; forward assessment
must retain that distinction.

The genuine run took 58.90 seconds overall, 13.27 CPU seconds and 297.7 MiB peak
memory with CPU capped at 20% and numerical libraries restricted to one thread.
Its v1 scaler emitted floating-roundoff warnings on constant columns. Published
scales/parameters remain finite and were verified. Future training uses adapter
v2, detecting constant columns using training only before standardization. This
versioned correction does not rewrite v1 weights, curves or test results.

### Reproduction and interrupted work

The run retains an exact frozen source bundle, including the imported Arena
network/input sources, under `training/runs/<run-id>/code`. Reproduction explicitly
uses that bundle and the pinned numeric toolchain. A bounded independent refit
used train/validation only and reproduced all 13 weight checksums and curves.
It published zero new models and did not reopen the consumed final test.
Measured refitting took 9.30 seconds after development loading; total CPU use
was 6.55 seconds. Proof: `docs/REALITY_GATE_D_REPRODUCIBILITY.json`.

```bash
# Use the accepted run's v1 source, not the future v2 fitting implementation.
PYTHONPATH=data/research/reality/training/runs/9f593b0e68c61c5a8eabf3b01b7ad38c9e1df27436bd041a55a505c995a0a9f9/code:packages \
  .venv/bin/python -m midas.reality.model_reproduce \
  --dataset data/research/reality/datasets/23201960592577e4cb280c5f3dc1fb64d75e3b12bacb45d347cc2ae32472242c \
  --root data/research/reality/training \
  --run-id 9f593b0e68c61c5a8eabf3b01b7ad38c9e1df27436bd041a55a505c995a0a9f9 \
  --output data/research/reality/reproduction-check.json
```

Training owns a derivative-root lock, publishes immutable models incrementally,
and records actual verification/loading/fitting/freeze/test/finalization phases.
Interrupted identical work reuses verified artifacts and an exact opened plan;
result-publication/ledger-consumption recovery does not create a new promotion.
A different code/specification against a consumed period is rejected. Failure,
corruption, budget or reserve breaches have visible terminal states and leave
raw recordings intact. The accepted run's frozen implementation can resume its
exact result even after future-version development.

### Durable future research

`deploy/reality-research.json` configures a daily coverage check and at most one
frozen offline plan per UTC week. `midas-reality-research.timer` is enabled, using
02:30 UTC plus up to ten minutes of jitter. Its oneshot service has a 20% CPU
quota, 768 MiB memory cap, low scheduling/idle I/O priority, no network, isolated
temporary storage and a twelve-hour ceiling. It does not modify collection or
active forward campaigns, activate models, retune their thresholds or promote
new candidates automatically.

After seven days of raw span, the job freezes a seven-day input window, builds a
versioned 1,000 ms dataset at two-minute sampling stride, independently audits
public labels, then runs the fixed training/validation/final-test protocol.
Actual measured coverage still determines eligibility. Failed explicit jobs do
not self-trigger new experiments; interrupted identical work has at most one
bounded recovery attempt. The new scheduled dataset tier is capped at 2 GiB;
the model/job tier is capped at 512 MiB, with a 20 GiB host reserve. Cold replay
and independent auditing still scale with the preserved source prefix; timeout,
capacity and interruption states require inspection rather than assuming success.

Only this new schedule's explicitly marked completed JSONL example caches are
prunable, retaining the latest complete cache. Earlier cache pruning verifies
completed model/report provenance and row checksums, preserves immutable
manifests/code/source references and writes an availability notice. Original raw
records and the accepted Gate B/C/D evidence are outside that retention class.
Unpublished `.building-*` scratch is disposable only in the scheduled namespace
while its builder lock proves no live writer owns it. Regenerate pruned rows
with retained frozen Foundry source/spec/manifest in a separate root. This is
reversible derivative-cache management, not removal of original observations.

The first real scheduled check succeeded with `WAITING_FOR_COVERAGE` at roughly
0.41 recorded days. It fitted nothing and left the timer enabled. Models trained
above are retrospective development evidence; prospective decisions have not
started yet. Gate E is next: freeze a shadow campaign before future observations,
start recording genuine decisions/follow-ups without orders, and verify durable
prospective accumulation. The native dashboard and final broad verification remain
outstanding.

### Gate D verification and operations checkpoint

Focused verification passes **114 tests**; additional registry-metadata and UTC
day-corruption assertions were rechecked in the 19-test training suite. Ruff
passes and strict mypy passes across 28 Reality sources. Tests include native/
portable classifier and regressor agreement, deterministic MLP/linear/tree fits,
train-only scaling, one-class refusal, independently computed metric arithmetic,
unknown-target exclusion, feature/future isolation, model and metadata corruption,
chronological frozen-test access/resume, period-overlap rejection, budget safety,
coverage waiting, bounded weekly triggering and explicit disposable-cache/scratch
retention with raw/code/manifest preservation. No fixture performance is counted
as genuine market evidence. Full backend/frontend/browser and protected archive
checks remain for Gate G.

At the checkpoint, collection remains PID 2288376 with zero automatic restarts
and no Gate D restart. Its active epoch has 69,822 frames, eight monitored markets,
16/16 fresh books, no timing-uncertain books and zero connection failures. The
finalized raw catalog has 1,182 segments and 136,690 records; the live ordinal
is 136,776. Storage is approximately 241 MiB, with roughly 232 MiB cgroup memory,
within the 512 MiB cap. Capacity has no alerts: recent growth is about 0.70 GB/day,
with an estimated 36.5 days to the 24 GiB raw budget and approximately 202 GiB
filesystem free. Forecast variation remains material; capacity/archival monitors
must stay enabled. The daily research timer is active; its check and both
Gate D jobs have successful terminal states. No prospective shadow service or
eligible policy is running yet.

The main checkout is clean at `8acab2298632eb04fbe5183fbe54f8e6f97a8fdb`.
Laboratory identity remains `c14738f8468a8103a98c2704dc5454e85e867a5e3d5b7174cc7383342aa5ebd8`;
Arena identity remains `bac445c2bb79877e6484cc395820a36dba69b7b03712e8ed1caf1a7ac160a681`.
`docs/REALITY_GATE_D_CHECKPOINT.json` pins model/report hashes, consumed test,
reproduction, coverage, eligibility failures, current services, raw catalog,
capacity and protection evidence. These are timestamped checkpoint facts rather
than continuously guaranteed frontend values.

## Gate E — prospective shadow engineering (in verification)

The shadow reader, frozen campaign, append-only evidence journal and live worker
are implemented in separate Reality modules. The first genuine canary failed
before any decisions because the reader rejected a legal empty rotated segment.
That evidence is retained. The corrected reader verifies empty catalogs without
resetting global ordinal continuity; a fixture regression now covers the case.
A second frozen canary has started accumulating genuine decisions and follow-ups.
The main fourteen-day campaign is frozen separately, with its start after the
canary period. Acceptance and measured evidence will be recorded after audit.

The raw reader opens source files read-only, validates framing/record checksums,
tracks exact offsets and ordinals, and verifies finalized segment hashes and
online reconstruction checkpoints. Partial open-file writes are retried; no raw
writer or collector restart is required. Warm-up never creates retrospective
decisions. Sampling requires actual current decision time, a compatible frozen
producer/reconstructor and a source-frame lag no greater than 250 ms.

The compressed SQLite journal uses full-synchronous WAL transactions and an
append-only SHA-256 event chain. Decision bodies, follow-ups, source seals and
worker transitions remain immutable. Query indexes and recoverable runtime state
are separate derived tables. A durable decision-commit marker precedes any
qualifying future receipt. Cursor, engine books/counters/recent hashes, metadata,
rolling history, pending decisions and sampling state support recovery without
reinterpreting decisions under a changed implementation.

Policies include no trade, a mathematical discrepancy filter, original Prometheus
recorded-source mathematics, conservative risk, an eligibility-gated prediction
policy and a recovery guard. Experimental prediction probes do not activate an
ineligible policy. Original attestation/negative-risk restrictions are retained;
the adapter never fabricates live execution attestations. Proposed capital is
explicitly hypothetical, bounded by position/market/family/overall limits and
not recycled during the campaign without evidence of execution or settlement.
No wallet, authenticated trading API, order router or actual order submission is
implemented.

Each qualified decision retains exact public features/full baseline books,
source lineage, actual decision/computation/commit times, processing lag, model
IDs/weight hashes, policy reasons, proposed size/limits and declared assumptions.
All-market sampling is thirty seconds; an additional qualified discrepancy can
trigger a five-second sample. This extra sampling bias is explicit in the plan.
An observatory captures five-second public book points with quality flags.
Invalid/stale states record abstentions rather than fabricated features.

Follow-ups use 100/300/1,000/5,000 ms receiver horizons and declared tolerances,
requiring new sufficiently synchronized depth observations for both legs.
Unavailable futures, gaps, timing ambiguity and source/market/tick changes are
censored. A two-second availability grace completes quiet-source unknowns;
absence is never converted into a negative price/fill outcome. Four frozen
execution families produce per-trial hypothetical bounds. Unmatched inventory
and quoted-bid unwind assumptions are explicit; a below-minimum or unsupported
recovery cannot be reported as successful. None of these quantities are actual
fills, realized money or private queue/latency measurements.

The main `midas-reality-shadow.service` uses immutable campaign code, pinned
model/report hashes, one worker lock, a 4 GiB evidence budget, 20 GiB host reserve,
512 MiB memory cap, low scheduling/idle-I/O priority and bounded failure restarts.
Its configured steady CPU cap is 10% of one core. Temporary warm-up quotas are
operational changes, not changes to frozen decision/measurement thresholds.
`PrivateNetwork=true` was requested, but this host's user service manager reports
network namespaces unavailable; that OS isolation is not enforced. The worker
itself only reads local raw data/models and has no networking or order-submission
path. This limitation must not be described as proven network isolation.
