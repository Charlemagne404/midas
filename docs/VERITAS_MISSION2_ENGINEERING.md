# Veritas Mission 2 Engineering Checkpoint

## Current delta: v4 measurement and coverage checkpoint

The incremental snapshot analyzer is now at `veritas-finalized-snapshot-analysis-v4`;
v1–v3 state, summaries, and event histories are retained separately. v4 adds
per-market selected/valid counts, first and last sampled time, sampled book
fingerprint changes, and per-market/cumulative reclassification under the
previous five-second reported-age and 250 ms cross-outcome-skew gate. The
current request/receipt gate remains active. The paired result is a
measurement-yield comparison, with explicit limits around batch atomicity,
sequence freshness, and upstream queue age.

The dashboard exposes cohort strata, paired gate yield, sampled state changes,
and a bounded least-covered-market table. See [Gate A checkpoint
008](VERITAS_MISSION2_GATE_A_CHECKPOINT_008.md), [Gate G checkpoint
002](VERITAS_MISSION2_GATE_G_CHECKPOINT_002.md), and [measurement comparison
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

- Latest scan: `scan-20261015T083153Z-1d45d1808d34`, captured 08:31:53 UTC and indexed by v4 at 08:31:59.
- Latest discovery union: 300 unique IDs, 167 supported pair markets, 133
  explicit exclusions.
- Latest selected panel: 40 markets (six available stable controls, 34
  rotating); 37 quality-valid pairs. Latest liquidity strata are 9/14/17
  high/medium/low, expiry strata 17/22/1 near/medium/long, and spread strata
  9/15/16 tight/medium/wide.
- Indexed panel: eleven snapshots, 440 selected observations, 396
  request/receipt-valid, 44 empty-ask invalids, 156 distinct markets, zero
  pending snapshots. The legacy reported-age/skew gate accepts 98/440; paired
  yield improves by 298 observations (+67.7 percentage points).
- There are 284 sampled consecutive book-state comparisons; 271 fingerprints
  differ. The API bands 54 markets as higher sampled change, eight as lower,
  and 94 unclassified. These remain intermittent comparisons, not venue update
  rates.
- Observation window: about 152 minutes; current API readiness is
  `collecting_repeated_temporal_coverage`.
- Data root: 9,007,858 bytes, below the 1 GiB cap.
- Service configuration: 40 markets, one-second request pacing, seven planned
  network requests per scan, `CPUQuota=5%`, `MemoryMax=256M`, low CPU/IO
  priority, no new privileges, and writes limited to the observatory data root.
- Latest scheduled scan completed successfully at 08:31:59 UTC, using about
  609 ms of CPU. Qualification run
  `VERITAS-M2-ECO-QUAL-001-RUN-95f8752f5291` over eleven snapshots found zero
  positive states at all gates (396 quality-valid pairs, 156 distinct
  markets; top-edge median -0.028, maximum -0.001).

### Finalized source replay extension

The source analyzer's first batch, persistent catch-up, and scheduled
recurrences are recorded in checkpoints 003–007. The latest scheduled run
processed 128 segments / 6,230,348 bytes in 70 seconds, using 3.523 seconds of
CPU and 111.4 MiB peak memory. Cumulative progress is 530 of 2,839 replayable
segments, through ordinal 29,076, with 2,309 segments (604,276,235 bytes)
pending. Readiness remains `catching_up_finalized_source`; the prefix contains
no campaign-window frames. The source timer is active and the Reality checkout
remains clean at `714f824`.

The full scan results and immutable source identities are in
[`VERITAS_MISSION2_GATE_A_CHECKPOINT_001.md`](VERITAS_MISSION2_GATE_A_CHECKPOINT_001.md),
[`VERITAS_MISSION2_GATE_A_CHECKPOINT_002.md`](VERITAS_MISSION2_GATE_A_CHECKPOINT_002.md),
[`VERITAS_MISSION2_GATE_A_CHECKPOINT_003.md`](VERITAS_MISSION2_GATE_A_CHECKPOINT_003.md),
[`VERITAS_MISSION2_GATE_A_CHECKPOINT_004.md`](VERITAS_MISSION2_GATE_A_CHECKPOINT_004.md),
[`VERITAS_MISSION2_GATE_A_CHECKPOINT_005.md`](VERITAS_MISSION2_GATE_A_CHECKPOINT_005.md),
[`VERITAS_MISSION2_GATE_A_CHECKPOINT_006.md`](VERITAS_MISSION2_GATE_A_CHECKPOINT_006.md),
[`VERITAS_MISSION2_GATE_A_CHECKPOINT_007.md`](VERITAS_MISSION2_GATE_A_CHECKPOINT_007.md),
[`VERITAS_MISSION2_RESEARCH_INVENTORY_003.json`](VERITAS_MISSION2_RESEARCH_INVENTORY_003.json),
[`VERITAS_MISSION2_RESEARCH_INVENTORY_004.json`](VERITAS_MISSION2_RESEARCH_INVENTORY_004.json),
[`VERITAS_MISSION2_RESEARCH_INVENTORY_005.json`](VERITAS_MISSION2_RESEARCH_INVENTORY_005.json),
[`VERITAS_MISSION2_RESEARCH_INVENTORY_006.json`](VERITAS_MISSION2_RESEARCH_INVENTORY_006.json),
[`VERITAS_MISSION2_RESEARCH_INVENTORY_007.json`](VERITAS_MISSION2_RESEARCH_INVENTORY_007.json),
and [`VERITAS_MISSION2_RESEARCH_INVENTORY_008.json`](VERITAS_MISSION2_RESEARCH_INVENTORY_008.json).

## Verification

| Check | Result |
| --- | --- |
| Full Veritas backend test selection | 83 passed; one Starlette/httpx deprecation warning |
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
