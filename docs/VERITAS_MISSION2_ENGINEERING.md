# Veritas Mission 2 Engineering Checkpoint

## Latest operational and discovery update — Gate A checkpoint 021 / Gate F checkpoint 011

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
