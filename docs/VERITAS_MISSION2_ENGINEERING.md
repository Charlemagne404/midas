# Veritas Mission 2 Engineering Checkpoint

## Latest checkpoint — Gate A scan 33 and recorder continuity audit

At 20:05 UTC, scan 33 completed with 31/40 selected pairs quality-valid. The
cumulative panel has 1,167/1,320 valid pairs across 616 selected market IDs,
153 invalid pairs, and zero positive top-gross pairs; the best edge remains
-$0.001/share. The 24-hour rotating-coverage pilot has three scans, 97/120
valid pairs, and no skipped scan sequences. Its comparison remains descriptive
because only three of nine selected control slots were available. See [Gate A
checkpoint 029](VERITAS_MISSION2_GATE_A_CHECKPOINT_029.md).

A read-only segment metadata audit found 1,790 finalized Reality `.seg` files
with mtimes at or after the 04:57:26 UTC DNS warning. The first followed the
warning by about eight seconds; the largest adjacent mtime gap was 36.51
seconds, and the latest file was written at 20:05:04 UTC. At 20:02 UTC the
recorder was active with zero restarts and DNS resolved. This argues against
a prolonged recording-output outage. The 20:14 source summary counted 911
`book_resynchronization` markers and one `connection_failure`; these are
reconstruction barriers, but their aggregate contains no event times or
outage durations. Feed continuity is therefore not established. See
[continuity artifact 001](VERITAS_MISSION2_RECORDER_CONTINUITY_001.json) and
[research ledger H072](VERITAS_RESEARCH_LEDGER.json).

The scheduled 20:14:36 UTC source-analysis run processed 128 segments / 31.48
MB in 212 seconds, using 10.618 CPU seconds and 147.7 MiB peak memory with no
swap. It is catching up at 3,388/4,260 segments, with 872 / 269,424,035 bytes
pending. The partial campaign window has 186,344 quality-valid states across
47 markets, with zero positive top-ask/full-depth states. The next source
timer is 20:40:16 UTC.

Scan 33's Arena qualification completed all 33 events successfully at
20:16:26 UTC and found zero positives at all five gates. The authoritative
job is complete, while the Director manifest still projects it as queued; the
20:45:05 UTC cycle is the reconciliation point. The manifest now reports the
corrected `NOT_READY_NO_CANDIDATE_RELEVANT_TARGET` model readiness. See [Gate
F checkpoint 019](VERITAS_MISSION2_GATE_F_CHECKPOINT_019.md). No manual poll or
restart was used.

The frozen-campaign v1.4 audit found 937 public markouts across 41,012
follow-up slots, with 40,075 censored. At five seconds, 473/3,503 valid initial
decisions have an observed markout, but all report no initial discrepancy,
null opportunity persistence, and unknown-counterfactual execution ground
truth. These are not strategy or P&L labels. The v1.4 code passed 9 focused
tests, Ruff, formatting, and strict Mypy; the artifact remains separate from
the dashboard's pinned v1.3 schema. See [Gate C checkpoint
003](VERITAS_MISSION2_GATE_C_CHECKPOINT_003.md) and [label artifact
001](VERITAS_MISSION2_LABEL_FEASIBILITY_001.json). Mission 2 remains active.

## Gate G checkpoint 005 — coverage dashboard and scan 32

Commit `a03a10c` adds a read-only coverage-pilot panel backed by a
digest- and lineage-verified API projection. Focused verification passed 12
API tests, one targeted UI test, Ruff, formatting, strict Mypy, TypeScript,
ESLint, Prettier, and the production build; the existing Vite large-chunk
advisory remains. No host deployment or service restart occurred.

The live pilot has two scans / 80 selected slots / 66 quality-valid / 14
invalid / zero missed sequences. Scan 32 selected 40 pairs from a 300-ID
bounded discovery union; 34 were quality-valid and none had positive gross.
The 32-snapshot panel contains 1,136/1,280 quality-valid pairs across 598
distinct selected IDs, zero positives at all five economic gates, and a
maximum top edge of -$0.001/share. Finalized-source analysis remains partial.
See [Gate G checkpoint 005](VERITAS_MISSION2_GATE_G_CHECKPOINT_005.md).


## Earlier operational and discovery update — Gate A checkpoint 021 / Gate F checkpoint 011

The 15:00 scheduled scan is snapshot 23. The cumulative panel has 920
selected observations, 825 request/receipt-valid pairs, 95 invalid pairs, and
418 distinct markets. The legacy reported-age/skew gate accepts 189 pairs,
for a paired recovery of 636/920 (+69.13 percentage points). All five
economic qualification gates remain zero-positive.

The 15:10 finalized-source replay processed 124 segments / 33,163,975 bytes.
Its partial prefix now covers 2,161/3,668 finalized segments and contains
70,950 campaign-window frame records, 59,343 touched states, and 57,798
quality-valid states. There are 1,507 segments / 396,434,833 bytes pending;
positive top-ask and full-depth states remain zero. The earlier source-window
interpretation correction remains documented in checkpoint 017.

The 15:15 Director cycle recorded scan 22 completion, admitted scan 23, and
Arena completed the 23-event qualification at 15:15:47 UTC. The finding
remains zero-positive. The manifest last updated at 15:15:32 UTC projects
`QUEUED` for scan 23 and retains scan 22's finding; the next scheduled poll at
15:45:00 UTC is the reconciliation point. No manual poll or retry was started.
See [Gate A checkpoint 021](VERITAS_MISSION2_GATE_A_CHECKPOINT_021.md), [Gate F
checkpoint 011](VERITAS_MISSION2_GATE_F_CHECKPOINT_011.md), [operations](VERITAS_MISSION2_OPERATIONS.md),
and [research inventory 024](VERITAS_MISSION2_RESEARCH_INVENTORY_024.json).

## Latest dashboard update — Gate G checkpoint 004

The read-only Arena activity API now returns a bounded, filename-digest-
verified history of recent Research Director events. The Veritas page exposes
scan/job/finding and experiment/dataset lineage, gate counts, and preserved
failure/recovery notes beside current strategy/model readiness. The last
read-only projection check at 12:55 UTC returned eight verified events from
the Director's then-19-file archive and zero invalid artifacts; the
source-drift failure and subsequent stable-revision qualification were both
visible. Backend, frontend, type, lint, format, build, and browser checks
passed. See [Gate G checkpoint 004](VERITAS_MISSION2_GATE_G_CHECKPOINT_004.md).

## Previous operational update — Gate F checkpoint 005

The 12:15 Director cycle completed a new 17-event qualification for the 12:01
scan on committed source revision `e78a95e2`. Its five opportunity gates
remain zero-positive. A 12:16 no-launch poll verified the finding and admitted
no second job. The 12:10 finalized-source replay advanced to 1,438/3,313
cataloged segments, with no campaign-window frames. See [Gate F checkpoint
005](VERITAS_MISSION2_GATE_F_CHECKPOINT_005.md), [operations](VERITAS_MISSION2_OPERATIONS.md),
and [research inventory 017](VERITAS_MISSION2_RESEARCH_INVENTORY_017.json).

## Previous discovery status — Gate A checkpoint 014

The 12:01 observer scan found 200 supported binary markets among 300 bounded
IDs, with 100 explicit exclusions. Thirty-five of 40 selected pairs were
quality-valid. The 17-snapshot panel has 613 valid pairs across 284 market IDs
and no positive top, depth, minimum-size, or fee-qualified states. The
Director qualification and source-replay recurrences have both completed for
this scan. See [Gate A checkpoint
014](VERITAS_MISSION2_GATE_A_CHECKPOINT_014.md), [research inventory
017](VERITAS_MISSION2_RESEARCH_INVENTORY_017.json), and
[operations](VERITAS_MISSION2_OPERATIONS.md).

## Previous operational update — Gate F checkpoint 003

The 11:15 job for the 11:01 scan failed before event processing because its
source revision changed while queued. It remains preserved at 0/1 and was not
retried. The next scheduled cycle has since completed successfully against
the stable committed revision; see [Gate F checkpoint
003](VERITAS_MISSION2_GATE_F_CHECKPOINT_003.md) and [checkpoint
004](VERITAS_MISSION2_GATE_F_CHECKPOINT_004.md).

## Previous discovery status — Gate A checkpoint 012

The bounded 11:01 observer scan found 207 eligible binary markets in 300
unique IDs. A pinned, read-only event audit verified one complete nine-outcome
NegRisk event and added replayable economics for both complete Yes and No
baskets. Both have negative gross edge and fail source timestamp age and skew
gates; neither qualifies an opportunity. The audit preserves the protocol
limitation that at-most-one Yes does not ensure at least one Yes.
See [Gate A checkpoint 012](VERITAS_MISSION2_GATE_A_CHECKPOINT_012.md),
[research inventory 015](VERITAS_MISSION2_RESEARCH_INVENTORY_015.json), and
[operations](VERITAS_MISSION2_OPERATIONS.md).

## Earlier status — Gate F checkpoint 002

The Research Director now validates and stores the separately maintained
finalized-source summary on each cycle, including its sealed digest, campaign
identity, replay counters, and economic counters. The API and Veritas activity
panel expose source readiness alongside public-snapshot qualification. A
10:56 UTC no-launch poll reused the existing completed finding, created no job,
and reported 1,072/3,136 source segments processed with no campaign-window
frames yet. See [Gate F checkpoint 002](VERITAS_MISSION2_GATE_F_CHECKPOINT_002.md),
[operations](VERITAS_MISSION2_OPERATIONS.md), and [research inventory
014](VERITAS_MISSION2_RESEARCH_INVENTORY_014.json).

## Earlier status — Gate F checkpoint 001

The recurring Veritas Research Director is enabled at :15 and :45 UTC. It
verifies a current v2 scan and finalized v4 event, admits one scan-pinned
Arena qualification job, and publishes durable readiness and finding lineage.
The first recurring cycle qualified
`scan-20261015T103110Z-b077f9c3d7be` through
`job-1bb0f47d56374e1385503362`, producing
`veritas-qualification-v1-115a375a2bd16454` over 14 events. The cumulative
panel has 507 valid pairs across 210 markets and zero positive states at all
qualification gates. The API and Veritas dashboard expose the current scan,
readiness, sample counts, and no-trade recommendation. See [Gate F checkpoint
001](VERITAS_MISSION2_GATE_F_CHECKPOINT_001.md), [operations](VERITAS_MISSION2_OPERATIONS.md),
and [research inventory 013](VERITAS_MISSION2_RESEARCH_INVENTORY_013.json).

The 10:40 UTC Reality source-analysis recurrence processed 128 finalized
segments / 30,283,274 bytes in 155 seconds (7.737 CPU seconds, 132.1 MiB peak).
The prefix now covers 1,072 of 3,136 replayable segments, with 2,064 pending
(557,814,406 bytes) through ordinal 122,759 and no campaign-window frames. The
observer, source-analysis, and Research Director timers are active. Reality
services and protected evidence were not restarted or changed. Current source
and state hashes are in [research inventory 013](VERITAS_MISSION2_RESEARCH_INVENTORY_013.json).

## Earlier status — Gate A checkpoint 011

The 10:01 UTC scheduled v2 discovery scan (`scan-20261015T100116Z-7d135306c470`)
indexed as the 13th finalized snapshot. The 300-ID bounded union contained 132
eligible binary pairs; 38 of 40 selected pairs were quality-valid, with zero
positive gross candidates. A bounded Arena qualification job consumed the 13
finalized v4 events and persisted an idempotent zero-positive finding. The
dashboard browser workflow passed. Full evidence and current limits are in
[Gate A checkpoint 011](VERITAS_MISSION2_GATE_A_CHECKPOINT_011.md).

The 10:10 UTC source-analysis recurrence also completed within its limits.
The finalized prefix is now 944/3,077 segments, with 2,133 pending and no
campaign-window frames. Reverification of all 944 sealed events matched the
rolling chain in state.

## Earlier checkpoint: paired measurement, censoring, and dashboard

The details below describe the 12-snapshot state at 09:16 UTC. The 13-snapshot
discovery and source-replay continuation is recorded at the top of this report
and in Gate A checkpoint 011.

The incremental snapshot analyzer is now at `veritas-finalized-snapshot-analysis-v4`;
v1–v3 state, summaries, and event histories are retained separately. v4 adds
per-market selected/valid counts, first and last sampled time, sampled book
fingerprint changes, and per-market/cumulative reclassification under the
previous five-second reported-age and 250 ms cross-outcome-skew gate. The
current request/receipt gate remains active. The paired result is a
measurement-yield comparison, with explicit limits around batch atomicity,
sequence freshness, and upstream queue age.

The dashboard exposes cohort strata, paired gate yield, sampled state changes,
a bounded least-covered-market table, and the frozen-campaign censoring view.
See [Gate A checkpoint 008](VERITAS_MISSION2_GATE_A_CHECKPOINT_008.md),
[Gate C checkpoint 001](VERITAS_MISSION2_GATE_C_CHECKPOINT_001.md), [Gate G
checkpoint 002](VERITAS_MISSION2_GATE_G_CHECKPOINT_002.md), [Gate G checkpoint
003](VERITAS_MISSION2_GATE_G_CHECKPOINT_003.md), and [measurement comparison
protocol 002](VERITAS_MISSION2_MEASUREMENT_COMPARISON_002.md).

**Date:** 2026-10-15
**Branch:** `project/veritas`
**Starting commit:** `9a857cc56804bec6b7129171ba090d338e263aa3`

## Architecture delivered

### Public discovery and observation

[`observatory.py`](../packages/midas/veritas/observatory.py) builds a six-frame
Gamma discovery union, retains exclusions and query lineage, selects up to 40
price-blind markets, and retrieves YES/NO books through one bounded public
CLOB `/books` call. It records immutable compressed snapshots, response hashes,
source code hashes, and a compact latest summary. The stable cohort and each
rotation are explicit; selection probabilities apply only within the bounded
query union and conditional frozen controls.

Only same-condition V1 binary pairs pass to economic arithmetic. Multi-outcome,
augmented negative-risk, ambiguous identity, and unsupported payoff semantics
are excluded with reasons. This prevents related event text from being treated
as a payoff identity.

### Independent arithmetic and quality gate

[`opportunity_audit.py`](../packages/midas/veritas/opportunity_audit.py) checks
condition/token identity, exact outcomes, market status, tick/minimum metadata,
book sides, sequence-independent pair matching, top asks, sorted depth walks,
and quantity-specific minimums. It reports independent audit arithmetic and
cross-checks fee behavior. Adversarial fixtures cover positive and negative
edges, invalid pair identities, empty sides, insufficient depth, minimums, and
fee cases.

The measurement comparison changes the freshness basis from last-reported book
update age to request-to-receipt duration for the exact response batch. Reported
book age and cross-outcome skew remain diagnostics. The analyzer labels batch
atomicity and sequence ordering unverified rather than assuming them.

### Incremental research and experiment

[`continuous_analysis.py`](../packages/midas/veritas/continuous_analysis.py)
indexes only completed immutable snapshots. It verifies snapshot identity and
analysis-event digests, uses exclusive event creation and atomic state writes,
resumes after partial work, and processes at most 100 pending snapshots per
run. Version 4 preserves v1–v3 artifacts, re-audits saved books with the
repaired gate, and adds paired legacy-gate plus per-market sampled coverage
metrics. Snapshot transitions do not estimate true venue update rates.

[`finalized_source_analysis.py`](../packages/midas/veritas/finalized_source_analysis.py)
is a separate incremental reader for the frozen Mission 2 Reality campaign. It
checks the campaign file hash and identity on each run, reads only numeric
finalized-segment catalogs and their `.seg` files, and never opens `.open`
files. It validates each new segment hash and record catalog, skips verified
empty finalized headers, and detects catalog-prefix changes behind progress
without hashing old segment payloads on every run. A restored `Context`
reconstructs source state across bounded batches. Each segment gets an
exclusive digest-sealed event before the atomic cursor/state update, so an
interrupted segment can be replayed and compared without duplicate application.
The user service limits each run to 128 segments or 32 MiB, state to 24 MiB,
and source-analysis artifacts to 256 MiB.

[`economic_experiment.py`](../packages/midas/veritas/economic_experiment.py)
compares the unchanged top-ask gross-sign baseline to full displayed depth and
both per-leg minimum checks at 20 shares. It separately counts single-match
and fragmentation-safe fee sensitivities. Event digests, snapshot evidence
hashes, scanner hashes, source event hashes, experiment source hash, and a
result digest are retained. Each input dataset gets a deterministic run ID, so
a later cumulative window creates a new immutable artifact while preserving
prior results. The artifact reports candidate qualification, not PnL.

### API and dashboard

[`apps/api/veritas.py`](../apps/api/veritas.py) adds bounded reads for the
continuous-analysis summary and latest scan, a continuous-analysis artifact,
validated snapshot route, and a separate finalized-source summary and artifact.
It validates summary digests and scan IDs, applies compressed and decompressed
byte bounds, and remains read-only.

[`Veritas.tsx`](../apps/web/src/Veritas.tsx) and
[`veritas.css`](../apps/web/src/veritas.css) add market-discovery and cohort
strata, scan/coverage counts, data quality, concentration, edge and candidate
counts, readiness, paired old/new measurement yield, sampled market-state
transitions, least-covered markets, and immutable snapshot links. Zero
candidates are displayed directly. The page shows finalized Reality replay
progress in its own panel, separate from intermittent public snapshots and
realized execution.

### Gate C censoring analysis and Gate G dashboard

The v1.3 forward-forensics report reads one SQLite transaction from the active
frozen campaign using `mode=ro` and `PRAGMA query_only=on`. It groups outcomes
by market, decision UTC hour, frozen horizon, initial observation-quality
regime, and censor mechanism. An absent outcome row remains pending; it is not
counted as a censor. The 08:44 UTC snapshot covers 10,165 decisions and 40,660
horizon slots: 930 public measurements, 39,730 censors, and zero pending rows.
It includes 168 market/horizon groups, 48 hour/horizon groups, and 32
initial-quality/horizon groups. The full artifact is
[`VERITAS_GATE_A_CENSORING_003.json`](VERITAS_GATE_A_CENSORING_003.json),
SHA256 `4e7d8d2bde0cda1afdc5876de2fbc31c3a54219b95d9baba0bfbfeed454b9b72`.

The API validates campaign identity and count reconciliation before using the
report for follow-up yield. The dashboard shows horizon yields, up to 20
markets and 24 UTC-hour rows at the longest horizon, mechanism totals, and a
link to the full bounded artifact. `future_observation_unavailable` remains
ambiguous: the frozen worker records it after the horizon deadline passes
without a qualifying synchronized future book, without proving venue
inactivity or identifying every feed-selection gap. This audit did not replay
the complete event hash chain or run a full SQLite integrity scan.

Verification already recorded for this code set: 88 Veritas backend tests, 29
frontend tests, Ruff, strict Mypy, frontend lint/typecheck/format/build, and the
Veritas Playwright workflow passed. The production build retains its existing
large-chunk advisory. See [Gate C checkpoint
001](VERITAS_MISSION2_GATE_C_CHECKPOINT_001.md) and [Gate G checkpoint
003](VERITAS_MISSION2_GATE_G_CHECKPOINT_003.md).

### Recurring operation

The observer and snapshot analyzer run every 30 minutes on the existing user
timer. A separate offset timer advances finalized Reality source replay every
30 minutes under its own CPU, memory, byte, and segment limits. Neither
pipeline duplicates Reality's recorder or alters the frozen campaign. Both
timers and services are active and checked in under
[`deploy/systemd/user`](../deploy/systemd/user).

The two read-only analysis cycles advance independently: the snapshot cycle
indexes each newly finalized public scan, while the source cycle replays a
bounded finalized Reality prefix and resumes from its saved context. The API
exposes distinct readiness and source evidence for each. Neither launches an
Arena job or trains a model. With zero gross candidate labels, a strategy
tournament or predictor comparison would not be an evidence-supported
experiment.

## Runtime and evidence at checkpoint

- Latest scan: `scan-20261015T090047Z-6f98ffeaecab`, captured 09:00:47 UTC and indexed by v4 at 09:00:52.
- Latest discovery union: 300 unique IDs, 167 supported pair markets, 133
  explicit exclusions.
- Latest selected panel: 40 markets (six available stable controls, 34
  rotating); 35 quality-valid pairs. Latest liquidity strata are 9/16/15
  high/medium/low, expiry strata 18/21/1 near/medium/long, and spread strata
  16/12/12 tight/medium/wide.
- Indexed panel: twelve snapshots, 480 selected observations, 431
  request/receipt-valid, 49 empty-ask invalids, 161 distinct markets, zero
  pending snapshots. The legacy reported-age/skew gate accepts 107/480; paired
  yield improves by 324 observations (+67.5 percentage points).
- There are 319 sampled consecutive book-state comparisons; 304 fingerprints
  differ. The API bands 54 markets as higher sampled change, 15 as lower, and
  92 unclassified. These remain intermittent comparisons, not venue update
  rates.
- Observation window: about 181 minutes; current API readiness is
  `collecting_repeated_temporal_coverage`.
- Data root: 9,865,838 bytes, below the 1 GiB cap.
- Service configuration: 40 markets, one-second request pacing, seven planned
  network requests per scan, `CPUQuota=5%`, `MemoryMax=256M`, low CPU/IO
  priority, no new privileges, and writes limited to the observatory data root.
- Latest scheduled scan completed successfully at 09:00:52 UTC, using about
  605 ms of CPU. Qualification run
  `VERITAS-M2-ECO-QUAL-001-RUN-b401cd384481` over twelve snapshots found zero
  positive states at all gates (431 quality-valid pairs, 161 distinct
  markets; top-edge median -0.028, maximum -0.001).

### Finalized source replay extension

The source analyzer's first batch, persistent catch-up, and scheduled
recurrences are recorded in checkpoints 003–010. The latest scheduled run
processed 128 segments / 26,555,999 bytes in 158 seconds, using 7.937 seconds
of CPU and 113.4 MiB peak memory. Cumulative progress is 786 of 2,959
replayable segments, through ordinal 55,101, with 2,173 segments
(602,349,214 bytes) pending. Readiness remains
`catching_up_finalized_source`; the processed prefix has no campaign-window
frames. The source timer is active and the Reality checkout remains clean at
`714f824`.

The full scan results and immutable source identities are in
[`VERITAS_MISSION2_GATE_A_CHECKPOINT_001.md`](VERITAS_MISSION2_GATE_A_CHECKPOINT_001.md),
[`VERITAS_MISSION2_GATE_A_CHECKPOINT_002.md`](VERITAS_MISSION2_GATE_A_CHECKPOINT_002.md),
[`VERITAS_MISSION2_GATE_A_CHECKPOINT_003.md`](VERITAS_MISSION2_GATE_A_CHECKPOINT_003.md),
[`VERITAS_MISSION2_GATE_A_CHECKPOINT_004.md`](VERITAS_MISSION2_GATE_A_CHECKPOINT_004.md),
[`VERITAS_MISSION2_GATE_A_CHECKPOINT_005.md`](VERITAS_MISSION2_GATE_A_CHECKPOINT_005.md),
[`VERITAS_MISSION2_GATE_A_CHECKPOINT_006.md`](VERITAS_MISSION2_GATE_A_CHECKPOINT_006.md),
[`VERITAS_MISSION2_GATE_A_CHECKPOINT_007.md`](VERITAS_MISSION2_GATE_A_CHECKPOINT_007.md),
[`VERITAS_MISSION2_GATE_A_CHECKPOINT_008.md`](VERITAS_MISSION2_GATE_A_CHECKPOINT_008.md),
[`VERITAS_MISSION2_GATE_A_CHECKPOINT_009.md`](VERITAS_MISSION2_GATE_A_CHECKPOINT_009.md),
and [`VERITAS_MISSION2_GATE_A_CHECKPOINT_010.md`](VERITAS_MISSION2_GATE_A_CHECKPOINT_010.md). Historical and current evidence inventories are
[`VERITAS_MISSION2_RESEARCH_INVENTORY_003.json`](VERITAS_MISSION2_RESEARCH_INVENTORY_003.json),
[`VERITAS_MISSION2_RESEARCH_INVENTORY_004.json`](VERITAS_MISSION2_RESEARCH_INVENTORY_004.json),
[`VERITAS_MISSION2_RESEARCH_INVENTORY_005.json`](VERITAS_MISSION2_RESEARCH_INVENTORY_005.json),
[`VERITAS_MISSION2_RESEARCH_INVENTORY_006.json`](VERITAS_MISSION2_RESEARCH_INVENTORY_006.json),
[`VERITAS_MISSION2_RESEARCH_INVENTORY_007.json`](VERITAS_MISSION2_RESEARCH_INVENTORY_007.json),
[`VERITAS_MISSION2_RESEARCH_INVENTORY_008.json`](VERITAS_MISSION2_RESEARCH_INVENTORY_008.json),
[`VERITAS_MISSION2_RESEARCH_INVENTORY_009.json`](VERITAS_MISSION2_RESEARCH_INVENTORY_009.json),
[`VERITAS_MISSION2_RESEARCH_INVENTORY_010.json`](VERITAS_MISSION2_RESEARCH_INVENTORY_010.json), and
[`VERITAS_MISSION2_RESEARCH_INVENTORY_011.json`](VERITAS_MISSION2_RESEARCH_INVENTORY_011.json), and
[`VERITAS_MISSION2_RESEARCH_INVENTORY_012.json`](VERITAS_MISSION2_RESEARCH_INVENTORY_012.json).

## Verification

| Check | Result |
| --- | --- |
| Full Veritas backend test selection | 88 passed; one Starlette/httpx deprecation warning |
| Ruff on source analysis, API, script, tests, and existing implementation | Passed |
| Mypy on source analysis, API, and CLI script | Passed |
| Frontend unit suite | 29 passed |
| Frontend typecheck, lint, production build | Passed; build reports a large-chunk advisory |
| Veritas Playwright workflow | Passed; discovery, no-candidate state, source link, and API artifact were verified |
| Broader seven-test browser run | Six passed; one Reality workflow failed because the expected exact `Yes` heading was absent |
| `git diff --check` before mission docs | Passed; rerun at checkpoint commit |
| Systemd service and timer deployment definitions | Loaded user units match checkout; latest scan succeeded and timer is active |

The broader browser failure was in `e2e/reality.spec.ts`; no Reality source or
campaign file was changed. A separate Reality regression/browser unit reports
an exit code from 2026-10-14, before this checkpoint. It was not restarted or
modified.

## Explicitly not done

- No Reality collector, source segment, campaign identity, or policy was
  changed. No Arena, Laboratory, Prometheus, or historical Veritas records
  were rewritten.
- No full venue census, WebSocket update-rate study, source sequence proof,
  queue-age proof, fill model, or profitability result exists.
- The original prospective follow-up study's 48-hour, nine-market, and
  dependence-analysis requirements remain unmet. The active snapshot pilot is
  a separate bounded alternative, not a silent waiver.
- No model was trained and no strategy policy promoted. The observed gross
  candidate count is zero.

## Gate A continuation: rotating discovery and Arena qualification

Checkpoint 011 introduces `veritas-public-observatory-v2` with deterministic
half-hour Gamma page offsets, preserved frozen controls, source-aware category
labels, explicit per-market conditional selection probabilities, response
size limits, and actual HTTP attempt counts. The scheduled 10:01 UTC scan
successfully processed six discovery frames and one CLOB batch, indexed a
13th snapshot, and left zero pending v4 analysis events.

The scan union contained 300 IDs and 132 supported binary pairs. The selected
40-market panel had 38 valid pairs, zero positive gross candidates, and no
orders. The bounded Arena qualification job replayed the immutable 13-event
v4 prefix and persisted its idempotent result as an Arena finding. It found no
positive state at the unchanged top-ask, full-depth, minimum-notional, or fee
gates. The Veritas dashboard exposes the collector limits and persisted Arena
activity; the browser workflow passed against the new finalized evidence.

The expanded checkpoint validation passed 132 related backend tests and 29
frontend tests, strict Mypy, Ruff, Python formatting, frontend lint/typecheck/
formatting, production build, and the Veritas discovery Playwright workflow.
See [Gate A checkpoint 011](VERITAS_MISSION2_GATE_A_CHECKPOINT_011.md) and
[research inventory 012](VERITAS_MISSION2_RESEARCH_INVENTORY_012.json).

The probabilities remain conditional on a bounded query-response union and
frozen controls; half-hour offsets do not make the frame representative of the
venue. Quote sequence freshness, a 24-hour pilot review, the 48-hour
follow-up/dependence gates, a complete Research Director workflow, and
independent economic confirmation remain open. The full source replay is still
catching up and contains no campaign-window frames in its processed prefix.

## Gate A checkpoint 015 addendum — scan 18 and second complete group

The scheduled 12:31 UTC scan brought the v4 panel to 18 snapshots, 720 selected
observations, 645 quality-valid pairs, and 304 distinct markets. The prior
reported-age/skew gate accepts 153 pairs; the paired recovery is 492 pairs
(68.33 percentage points). No positive top, depth, minimum-size, or fee state
appeared. The 40-market sample remains conditional on the bounded Gamma frame.

The new pinned study runner verifies the seven-market OpenAI IPO NegRisk group
from direct Gamma market responses, sequential question indices, and the
Polygon adapter question count. Its rules form six contiguous ranges and one
No-IPO outcome. The Gamma group-filter query returned 20 unrelated markets,
which makes the direct member reads and on-chain count the useful completeness
evidence for this case.

One 14-token CLOB batch returned full displayed depth for 5, 20, and 100
shares per outcome. Source data failed freshness qualification at 33,546 ms
maximum age and 20,962 ms cross-book skew. The Yes basket top cost equals its
conditional $1 payout; the No basket costs $6.035 against a $6 protocol
minimum. Both are non-positive before fees at all tested sizes. The captured
artifact replays from its embedded evidence with a matching result digest. The
runner compiles and replay validation passes; no broader suite was run for this
documentation and artifact checkpoint. See [Gate A checkpoint
015](VERITAS_MISSION2_GATE_A_CHECKPOINT_015.md) and [inventory
018](VERITAS_MISSION2_RESEARCH_INVENTORY_018.json).

## Gate A checkpoint 016 addendum — public stream replay

The second REST capture and the official public market WebSocket cross-check
both returned the complete 14-token group, but failed source age and timestamp
skew limits. Their best bid, best ask, and last-trade prices matched exactly
for all 14 tokens; full bid and ask depth matched for six tokens each. The
WebSocket frame contains no sequence field. Its complete-set Yes top gross
edge is $0, while the No set is -$0.035; all tested full-depth and fee-safe
edges are non-positive.

The replay runner now accepts `--replay-market-stream`. It verifies the
WebSocket artifact digest, referenced REST study, complete token set, frame
bytes, timestamps, tick sizes, and basket calculations. The stream schema omits
NegRisk and minimum-size fields, so replay binds those two constraints from
the digest-verified REST/Gamma metadata. The bounded saved capture replayed
successfully; no test suite was run for this documentation and artifact update.
See [Gate A checkpoint 016](VERITAS_MISSION2_GATE_A_CHECKPOINT_016.md), [Gate
F checkpoint 006](VERITAS_MISSION2_GATE_F_CHECKPOINT_006.md), and [research
inventory 019](VERITAS_MISSION2_RESEARCH_INVENTORY_019.json).

The 12:45 Arena qualification completed 18/18 finalized events and returned
zero-positive results at all five gates. Its finding is complete in Arena,
while the Director manifest retains a queued state pending the next scheduled
poll. The 12:43 finalized-source summary contained 4,078 campaign-window frame
records, 2,779 touched market-frame states, and 2,739 quality-valid states;
positive top-ask and full-depth states remained zero.

## Previous Gate A checkpoint 017 addendum — scan 19 and source-window replay

Scan 19 adds 36 quality-valid pairs and four empty-ask invalid pairs. The 19-scan
panel has 681/760 quality-valid observations, 160/760 legacy age/skew-valid
observations, and no positive top, depth, per-leg minimum, or fee state. The
bounded scan union has 298 unique IDs, 138 supported same-condition V1 pairs,
and 160 explicit exclusions. The 40-market selection retains 37 rotating
markets and three available frozen controls.

The finalized-source analyzer counts `period_frame_records` inside the frozen
campaign window. This changes the interpretation of checkpoint 016: its
12:43 prefix had 4,078 campaign-window frames, 2,779 touched states, and 2,739
quality-valid states. The 13:13 summary advances that count to 15,469 frames,
11,367 touched states, and 11,000 quality-valid states, with zero positive
top-ask or full-depth states. Replay remains partial and reads finalized
segments only.

The 13:15 Arena job completed all 19 events at 13:16:07 UTC with zero positive
states at each qualification gate. Its manifest still projects `QUEUED` and
scan 18 as last qualified until the scheduled 13:45:16 UTC cycle. Mission 2
remains active. See [Gate A checkpoint 017](VERITAS_MISSION2_GATE_A_CHECKPOINT_017.md),
[Gate F checkpoint 007](VERITAS_MISSION2_GATE_F_CHECKPOINT_007.md), and
[research inventory 020](VERITAS_MISSION2_RESEARCH_INVENTORY_020.json).
## Previous Gate A checkpoint 018 addendum — scan 20 and source replay

Scan 20 adds 33 quality-valid pairs and seven empty-ask invalid pairs. The
20-scan panel has 714/800 quality-valid observations, 167/800 legacy
age/skew-valid observations, and no positive top, depth, per-leg minimum, or
fee state. The bounded scan union has 297 unique IDs, 153 supported
same-condition V1 pairs, and 144 explicit exclusions. The 40-market selection
retains 37 rotating markets and three available frozen controls.

The 13:43 finalized-source summary counts 29,198 campaign-window frames,
21,747 touched market-frame states, and 21,041 quality-valid states. The
prefix remains partial with 1,699 finalized segments pending and zero positive
top-ask or full-depth states. Checkpoint 016's 12:43 counter interpretation
was corrected in checkpoint 017.

The 13:45 Arena job completed all 20 events at 13:46:06 UTC with zero positive
states at each qualification gate. Its manifest still projects `QUEUED` and
scan 19 as last qualified until the scheduled 14:15:29 UTC cycle. Mission 2
remains active. See [Gate A checkpoint 018](VERITAS_MISSION2_GATE_A_CHECKPOINT_018.md),
[Gate F checkpoint 008](VERITAS_MISSION2_GATE_F_CHECKPOINT_008.md), and
[research inventory 021](VERITAS_MISSION2_RESEARCH_INVENTORY_021.json).

## Gate A checkpoint 019 addendum — scan 21 and source replay

Scan 21 adds 37 quality-valid pairs and three empty-No-ask invalid pairs. The
21-scan panel has 751/840 quality-valid observations, 176/840 legacy
age/skew-valid observations, and no positive top, depth, per-leg minimum, or
fee state. The bounded scan union has 300 unique IDs, 198 supported
same-condition V1 pairs, and 102 explicit exclusions. The 40-market selection
retains 37 rotating markets and three available frozen controls.

The 14:13 finalized-source summary counts 40,459 campaign-window frames,
30,809 touched market-frame states, and 29,749 quality-valid states. The
prefix remains partial with 1,630 finalized segments pending and zero positive
top-ask or full-depth states. Checkpoint 016's 12:43 counter interpretation
was corrected in checkpoint 017.

The 14:15 Director cycle recorded scan 20 completion, then admitted scan 21.
The Arena job completed all 21 events at 14:16:20 UTC with zero positive
states at each qualification gate. Its manifest still projects `QUEUED` for scan 21 and
scan 20 as last qualified until the scheduled 14:45:16 UTC cycle. Mission 2
remains active. See [Gate A checkpoint 019](VERITAS_MISSION2_GATE_A_CHECKPOINT_019.md),
[Gate F checkpoint 009](VERITAS_MISSION2_GATE_F_CHECKPOINT_009.md), and
[research inventory 022](VERITAS_MISSION2_RESEARCH_INVENTORY_022.json).

## Latest operating checkpoint — scan 24

The scheduled observer, finalized-source replay, and Director qualification cycle completed on 2026-10-15. Scan 24 extended the bounded 40-market sample to 24 snapshots and 441 distinct markets; 859/960 pairs pass the current quality gate, while all gross, depth, minimum, and fee qualification gates remain zero-positive. The source prefix reached 2,289/3,727 finalized segments; the Director and Arena completed the scan-pinned qualification without orders or authenticated requests. The Director manifest projection awaits its 16:15:11 UTC scheduled reconciliation. See [Gate A checkpoint 022](VERITAS_MISSION2_GATE_A_CHECKPOINT_022.md), [Gate F checkpoint 012](VERITAS_MISSION2_GATE_F_CHECKPOINT_012.md), and [inventory 025](VERITAS_MISSION2_RESEARCH_INVENTORY_025.json). Mission 2 remains active.

## Latest operating checkpoint — scan 25

The scheduled discovery and qualification pipeline completed scan 25. The bounded six-frame query returned 297 unique IDs after three duplicates were removed; 121 passed same-condition V1 eligibility. The 40-market sample has 35 quality-valid pairs and no positive gross, depth, minimum, or fee state. The source prefix advanced to 2,417/3,786 finalized segments. Arena completed the scan-pinned 25-event qualification; the Director manifest awaits its scheduled reconciliation. See [Gate A checkpoint 023](VERITAS_MISSION2_GATE_A_CHECKPOINT_023.md), [Gate F checkpoint 013](VERITAS_MISSION2_GATE_F_CHECKPOINT_013.md), and [inventory 026](VERITAS_MISSION2_RESEARCH_INVENTORY_026.json). Mission 2 remains active.

## Latest operating checkpoint — scan 26

The scheduled discovery and qualification pipeline completed scan 26. Its deduplicated six-frame union retained 289 unique IDs after removing 11 identical duplicate records; 169 passed same-condition V1 eligibility. The 40-market sample has 34 quality-valid pairs and no positive gross, depth, minimum, or fee state. The source prefix reached 2,545/3,844 finalized segments. Arena completed the 26-event qualification; the Director manifest awaits its scheduled reconciliation. See [Gate A checkpoint 024](VERITAS_MISSION2_GATE_A_CHECKPOINT_024.md), [Gate F checkpoint 014](VERITAS_MISSION2_GATE_F_CHECKPOINT_014.md), and [inventory 027](VERITAS_MISSION2_RESEARCH_INVENTORY_027.json). Mission 2 remains active.

## Latest operating checkpoint — scan 27

The scheduled discovery and qualification pipeline completed scan 27. Its six-frame union contained 298 unique IDs after two identical duplicate records were removed; 123 passed same-condition V1 eligibility. The 40-market sample has 33 quality-valid pairs and no positive gross, depth, minimum, or fee state. The source prefix reached 2,661/3,903 finalized segments, with 1,242 pending. Arena completed the 27-event qualification with zero-positive gates. The Director manifest awaits its scheduled reconciliation. See [Gate A checkpoint 025](VERITAS_MISSION2_GATE_A_CHECKPOINT_025.md), [Gate F checkpoint 015](VERITAS_MISSION2_GATE_F_CHECKPOINT_015.md), and [inventory 028](VERITAS_MISSION2_RESEARCH_INVENTORY_028.json). Mission 2 remains active.

## Gate D improvement — version 2 candidate provenance

The economic qualification now records bounded, hash-linked source pointers
for every quality-valid positive top-ask row. It cross-checks those rows
against each event's positive counter, requires the exact immutable snapshot
path, marks the evidence as not independently replayed, and fails closed at
1,024 evidence rows instead of truncating. The experiment and run identity
are versioned as v2. The read-only v2 comparison over the current 28 finalized
snapshots found 996 valid pairs and no candidate; no research finding was
written by that comparison. Twenty-one targeted backend tests passed, with
Ruff, strict Mypy, and formatting checks. The positive evidence branch is
covered by a synthetic fixture and awaits a genuine candidate. Details are
in [Gate D checkpoint 001](VERITAS_MISSION2_GATE_D_CHECKPOINT_001.md).

## Gate D improvement — version 3 bounded candidate replay

Gate D now independently reopens the immutable source snapshot for each
positive gross candidate, checks source and event lineage, re-derives the
same-condition market and books from the embedded Gamma/CLOB payloads, and
recomputes best asks, quantity depth, minimums, and fee sensitivities under
explicit read bounds. The Director validates the replay summary; Arena exposes
the digest-checked finding through a read-only API, and the dashboard links to
the evidence. Replay is capped and fails closed. It records that request/receipt
timing does not establish venue sequence, atomicity, order arrival, or fills.

The current 29-snapshot read-only v3 comparison remains negative: 1,034 valid
pairs across 536 markets, maximum top-pair edge -0.001 per share, and zero
positive states at every gross or economic gate. The persisted scan-28 finding
is still v2; v3 was exercised with synthetic positive and tampered-source
fixtures and is awaiting the next scheduled persisted qualification. See
[Gate D checkpoint 002](VERITAS_MISSION2_GATE_D_CHECKPOINT_002.md) and
[inventory 030](VERITAS_MISSION2_RESEARCH_INVENTORY_030.json).

## Gate F compatibility correction — legacy v2 finding

The 18:15 Director cycle surfaced a version-compatibility defect: it treated
the completed scan-28 v2 finding as invalid because only v3 results contain the
source-replay object. Commit `9379985` accepts v2 candidate-pointer results as
unreplayed legacy evidence while keeping strict replay validation for v3. It
also makes dashboard projections tolerant of historical ledger entries that
lack status fields. The actual v2 finding now passes read-only validation; no
artifact was rewritten. The next scheduled Director cycle will retry
reconciliation and consider the newest scan. Details and the test evidence are
in [Gate F checkpoint 016](VERITAS_MISSION2_GATE_F_CHECKPOINT_016.md) and
[inventory 031](VERITAS_MISSION2_RESEARCH_INVENTORY_031.json).

## Gate C implementation in operation — coverage pilot scan 1

Commit `de3f764` added a prospective, read-only coverage pilot to the
scheduled observer. At 19:00:55 UTC, scan
`scan-20261015T190055Z-7799523b9d87` enrolled 40 selected pair slots; 32
passed the existing v4 quality checks and eight were invalid because of empty
ask sides. The scan used the existing seven public HTTP attempts. No manual
service invocation was used. The 24-hour window ends at 19:00:55 UTC on
2026-10-16, with a maximum of 48 scans and no early stopping or backfill.

The first descriptive split was 31/37 valid rotating pairs and 1/3 available
stable controls. This is not randomized and supports no causal inference. The
same scan had zero-positive top-gross, full-depth, minimum-notional, and both
fee sensitivity gates. The pilot implementation and plan digests are pinned;
the source files covered by the pilot hash should remain stable while it is
running. The fixed protocol, event lineage, limitations, and next work are in
[Gate C checkpoint 002](VERITAS_MISSION2_GATE_C_CHECKPOINT_002.md) and
[inventory 036](VERITAS_MISSION2_RESEARCH_INVENTORY_036.json).

## Gate F scheduled cycle — scan 31 and finalized-source progress

The scheduled 19:10 UTC source recurrence processed 113 finalized segments /
33,445,857 bytes and advanced the prefix to 3,132/4,140 segments. The
remaining suffix is 1,008 segments / 298,406,538 bytes. The campaign window
now contains 192,072 frame records and 169,253 quality-valid states across 43
markets, with zero positive top-ask or full-depth states. The bounded batch
used 13.619 CPU seconds, 146.7 MiB peak memory, and no swap.

The 19:15 Director cycle admitted scan 31 and Arena completed all 31 events in
1.914 seconds. Its v3 finding has 1,102 quality-valid pairs across 575
markets and zero positive states at all five economic gates. Candidate
provenance/replay is complete for the empty candidate set; the positive
candidate path remains synthetically tested only. The Arena job is complete,
but the Director manifest still projects it as queued until the next scheduled
cycle. See [Gate F checkpoint 017](VERITAS_MISSION2_GATE_F_CHECKPOINT_017.md)
and [inventory 036](VERITAS_MISSION2_RESEARCH_INVENTORY_036.json).
