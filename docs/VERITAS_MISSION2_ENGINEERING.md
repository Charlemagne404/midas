# Veritas Mission 2 Engineering Checkpoint

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
run. Version 2 re-audits saved books with the repaired gate and preserves v1
state, events, and summary. Its current backlog is zero.

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
counts, readiness, and immutable snapshot links. Zero candidates are displayed
directly. The page shows finalized Reality replay progress in its own panel,
separate from intermittent public snapshots and realized execution.

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

- Latest scan: `scan-20261015T063103Z-12947c8cef0a`, captured 06:31:03 UTC.
- Latest discovery union: 300 unique IDs, 167 supported pair markets, 133
  explicit exclusions.
- Latest selected panel: 40 markets (six available stable controls, 34
  rotating); 37 quality-valid pairs.
- Indexed panel: seven snapshots, 280 selected observations, 248 quality-valid,
  32 empty-ask invalids, 133 distinct markets, zero pending snapshots.
- Observation window: 31 minutes 35 seconds; current API readiness is
  `collecting_repeated_temporal_coverage`.
- Data root: 4,745,634 bytes, below the 1 GiB cap.
- Service configuration: 40 markets, one-second request pacing, seven planned
  network requests per scan, `CPUQuota=5%`, `MemoryMax=256M`, low CPU/IO
  priority, no new privileges, and writes limited to the observatory data root.
- Latest scheduled service process: success, 617 ms CPU time and about 16 seconds elapsed.
  Peak memory was not recorded by systemd for this completed oneshot.

### Finalized source replay extension

The separate source analyzer's first live batch is recorded in
[`VERITAS_MISSION2_GATE_A_CHECKPOINT_003.md`](VERITAS_MISSION2_GATE_A_CHECKPOINT_003.md).
It processed 128 of 2,681 replayable segments through ordinal 7,048, with
2,553 segments (648,266,578 bytes) pending. The run used 3.63 seconds of CPU
and peaked at 110.6 MiB; readiness is `catching_up_finalized_source`. This
initial prefix contains no campaign-window frames, so it provides no economic
result yet. The read-only source timer is active and the Reality checkout
remains clean.

The full scan results and immutable source identities are in
[`VERITAS_MISSION2_GATE_A_CHECKPOINT_001.md`](VERITAS_MISSION2_GATE_A_CHECKPOINT_001.md),
[`VERITAS_MISSION2_GATE_A_CHECKPOINT_002.md`](VERITAS_MISSION2_GATE_A_CHECKPOINT_002.md),
[`VERITAS_MISSION2_GATE_A_CHECKPOINT_003.md`](VERITAS_MISSION2_GATE_A_CHECKPOINT_003.md),
and [`VERITAS_MISSION2_RESEARCH_INVENTORY_003.json`](VERITAS_MISSION2_RESEARCH_INVENTORY_003.json).

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
