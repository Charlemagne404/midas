# Veritas operations — research procedures

As of 2026-10-26, the clean Veritas development worktree is
`/home/charlie/midas-veritas` on `project/veritas` at
`3b102928594323e7886859d348f7b2151663debb`. The scheduled V6 observer runs
from the immutable release recorded in the dated V6 handoff below. The
integrated MIDAS readiness work is isolated on
`codex/veritas-v6-integration-20261026`; it has not been merged to `main`.
Reality collection and its frozen prospective worker continue from the
separate `/home/charlie/midas-reality` worktree.

## Read the Reality baseline without taking writer ownership

The bounded forensic command opens the campaign journal with SQLite read-only
mode and does not write to the campaign directory:

```bash
cd /home/charlie/midas-veritas
PYTHONPATH=packages /home/charlie/midas/.venv/bin/python \
  scripts/veritas_forward_audit.py \
  --root /home/charlie/midas-reality/data/research/reality/forward/mission2 \
  --limit 50000
```

The command validates the frozen campaign identity and limits the indexed
decision query to at most 50,000 records. Its output summarizes reasons and
provenance; it never exports raw observations. A live writer may append while
the read transaction is open. Operational status JSON and service health are
separate snapshots and can lag the journal by a few outcomes.

`--check-integrity` adds a full read-only SQLite scan. Use it during a low-load
period because scan time and disk reads grow with the journal archive. The
default forensic query does not scan the full database or event hash chain.

## Reproduce sampled decisions from finalized raw segments

Use the source replay when journal decisions need independent source verification:

```bash
cd /home/charlie/midas-veritas
PYTHONPATH=packages /home/charlie/midas/.venv/bin/python \
  scripts/veritas_reconcile_sources.py \
  --campaign-root /home/charlie/midas-reality/data/research/reality/forward/mission2 \
  --limit 5000
```

The command verifies the frozen campaign code, takes a short read-only journal
snapshot, and replays only cataloged finalized `.seg` files. It does not read an
active `.open` segment, write into Reality, or copy raw observations to its
aggregate report. Decisions at source ordinals beyond the captured finalized
prefix are reported as uncovered. The default source bound is 20 GiB; use a
smaller `--max-source-gib` value when limiting disk reads. Full-prefix replay
reads each finalized segment for both integrity and reconstruction, so use it
when needed rather than as a frequent poll. The committed result is
`docs/VERITAS_GATE_A_SOURCE_REPLAY_001.json`.

The current replay also reports decision-to-frame input lag, paired-book age,
cross-outcome receiver-time skew, per-market and per-outcome book-update
intervals, recorded source gaps, and freshness counts by quality reason and
market. Version 5 adds five-minute family activity groups, normalized issue
labels mapped to campaign market IDs, and unmapped-entry counts. Version 6
maps finalized gap issue entries to campaign market and YES/NO outcome and
records allowlisted fields from process-start configuration records. It omits
outcome asset identifiers and startup storage paths. Version 7 also measures
receiver-time elapsed from preceding same-gap-epoch outcome updates to
resynchronization issues and scheduled decisions. It reports counts against
the frozen decision freshness gate and the source engine's active stale
threshold. Input lag starts at the recorded frame receiver timestamp; zero
skew is not evidence of venue-level simultaneity.
The latest combined snapshot is
[VERITAS_GATE_A_GAP_AGE_001.json](VERITAS_GATE_A_GAP_AGE_001.json),
documented in [Gate A checkpoint 010](VERITAS_GATE_A_CHECKPOINT_010.md).
Intervals spanning source discontinuities are censored. These measurements
are diagnostic and do not modify the frozen campaign or establish fills.

## Count raw market-frame quality and opportunity states

```bash
cd /home/charlie/midas-veritas
PYTHONPATH=packages /home/charlie/midas/.venv/bin/python \
  scripts/veritas_raw_funnel.py \
  --campaign-root /home/charlie/midas-reality/data/research/reality/forward/mission2 \
  --max-source-gib 1 \
  > docs/VERITAS_GATE_A_RAW_FUNNEL_005.json
```

This replays the finalized prefix to rebuild books and verify online
reconstruction checkpoints, but aggregates only campaign-period frames that
touch a paired market. It uses recorded receiver time, not shadow-worker
processing time. Counts are repeated correlated observations, distinct from
the scheduled decision denominator. It reports public ask-depth support before
fees and never claims a fill. Version 2 compares each leg's depth-weighted USDC
notional with the reported per-order USDC minimum. The latest bounded, raw-free
snapshot is `docs/VERITAS_GATE_A_RAW_FUNNEL_004.json`, documented in
[Gate A checkpoint 012](VERITAS_GATE_A_CHECKPOINT_012.md). Each invocation
captures a changing finalized prefix; use a new unused versioned output name
instead of overwriting a prior snapshot. The one GiB cap currently leaves
headroom above the latest 484 MB prefix.

## Reproduce the controlled capacity sensitivity

```bash
cd /home/charlie/midas-veritas
PYTHONPATH=packages /home/charlie/midas/.venv/bin/python \
  scripts/veritas_economic_scenario_study.py \
  > docs/VERITAS_GATE_B_CAPACITY_001.json
```

This deterministic exercise uses a hand-authored synthetic V1 order book, a
discrete quantity grid, USDC capital budgets, explicit fee and carry assumptions,
and full/half displayed-depth sensitivities. It makes no observed-opportunity,
fill, or strategy-performance claim. Its implementation is in
`packages/midas/veritas/scenario_study.py` and its assumptions are embedded in
the output artifact.

## Solve synthetic execution break-even thresholds

```bash
cd /home/charlie/midas-veritas
PYTHONPATH=packages /home/charlie/midas/.venv/bin/python \
  scripts/veritas_execution_break_even.py \
  > docs/VERITAS_GATE_B_EXECUTION_BREAK_EVEN_001.json
```

This extends the same synthetic size grid with a per-attempt equation for a
completed pair, one unmatched leg, and no fill. It reports the matched
completion rate needed to offset explicitly assumed unmatched-leg loss under
single-match and fragmentation-safe fee cases. The rate grids are sensitivity
inputs, not estimates; public quote observations cannot identify our
hypothetical fill rates. No recovery value is assumed for the unmatched leg.
The math is in `packages/midas/veritas/execution_break_even.py`, and the
controlled scenario assembly is in `packages/midas/veritas/scenario_study.py`.
The output is documented in
[Gate B checkpoint 001](VERITAS_GATE_B_CHECKPOINT_001.md).

Read-only service evidence is available from:

```bash
curl --fail --silent http://127.0.0.1:8010/api/health
curl --fail --silent http://127.0.0.1:8010/api/reality/overview
curl --fail --silent http://127.0.0.1:8010/api/reality/operations
curl --fail --silent 'http://127.0.0.1:8010/api/reality/forward?limit=5000'
```

The `overview` and `operations` endpoints include bounded status and resource
summaries. Do not use dashboard requests to modify campaign state.

## Read-only Veritas dashboard

The native **Veritas** page reads `GET /api/veritas/overview`. It summarizes
committed Gate A/B evidence, the current hypothesis ledger, and the research
inventory. Individual provenance links use
`GET /api/veritas/artifacts/{identity}` and return the JSON object plus its
SHA256 digest. Supported identities are `baseline`, `raw-funnel`, `capacity`,
`break-even`, `ledger`, and `inventory`.

The interface reads only those six repository artifacts. It rejects unknown
identities, symlinked files, invalid JSON objects, and files larger than 512
KiB. The overview omits raw market records and repository paths. These routes
are read-only; they cannot change campaign state or submit orders. The page
refreshes its overview every 60 seconds.

The current decision and evidence limits are summarized in the [final
report](VERITAS_FINAL_REPORT.md), [engineering report](VERITAS_ENGINEERING_REPORT.md),
and [economic verdict](VERITAS_ECONOMIC_VERDICT.md). The closeout checkpoint is
[Gate J checkpoint 001](VERITAS_GATE_J_CHECKPOINT_001.md).

Run focused verification from `/home/charlie/midas-veritas`:

```bash
/home/charlie/midas/.venv/bin/pytest -q tests/test_veritas_dashboard_api.py
/home/charlie/midas/.venv/bin/ruff check \
  apps/api/veritas.py apps/api/main.py tests/test_veritas_dashboard_api.py
corepack pnpm --dir apps/web test
corepack pnpm --dir apps/web lint
corepack pnpm --dir apps/web format:check
corepack pnpm --dir apps/web build
```

See [dashboard checkpoint 001](VERITAS_DASHBOARD_CHECKPOINT_001.md) for the
displayed evidence and latest verification result.

## Prospective measurement pilot v2

Mission 2 adds `VERITAS-M2-COVERAGE-PILOT-002` as an isolated 24-hour / 48-scan
measurement study. Its [frozen protocol](VERITAS_MISSION2_COVERAGE_PILOT_002.json)
enrolls from the next ordinary immutable observer scan after deployment; it
does not backfill earlier snapshots or change pilot 001. State, events, and the
summary live under
`data/veritas-observatory/measurement-pilots/VERITAS-M2-COVERAGE-PILOT-002/`.

The v2 implementation pin covers only `coverage_pilot_v2.py` and the shared
`coverage_pilot.py` event/summary helpers. Keep those files unchanged until the
study reaches its fixed stop or cap. Each event links the saved snapshot and
finalized v4 analysis by digest and records the observer/analysis code hashes,
reported timestamp-age and cross-outcome-skew diagnostics, plus separate
atomicity and sequence-verification counts. Reported timestamp recency is not
venue freshness; zero verification counts remain unknown or unverified, not
proof of failure. The overview exposes a read-only `measurement_pilot_v2`
projection and the `coverage-pilot-v2` artifact. Do not manually trigger a scan
to enroll or accelerate this study.
The dashboard continues to verify pilot 001 against its stored event-chain pin
and labels current-source drift explicitly; this preserves the historical
record without treating its source as current.

## Follow-up power sensitivity

The activity-aware sampling proposal has a reproducible planning-only power
calculation. It reads the committed Gate A baseline artifact and writes a
derived sensitivity JSON; it does not read Reality runtime stores or change a
campaign.

```bash
cd /home/charlie/midas-veritas
PYTHONPATH=packages /home/charlie/midas/.venv/bin/python \
  scripts/veritas_followup_power.py \
  > docs/VERITAS_GATE_A_FOLLOWUP_POWER_001.json
PYTHONPATH=packages /home/charlie/midas/.venv/bin/pytest -q \
  tests/test_veritas_followup_power.py
```

The design and its launch-readiness decision are in
[follow-up design draft 002](VERITAS_GATE_A_FOLLOWUP_DESIGN_002.md). The
cluster grid is a sensitivity, not an empirical correlation estimate or a
campaign power claim.

## Existing Arena jobs and finite schedules

Arena is the existing owner for durable simulator jobs and bounded research
schedules. The Arena UI's **Durable research jobs** and **Bounded research
director** areas show persisted progress and controls. Read-only API routes
include `GET /api/arena`, `GET /api/arena/jobs/{job_id}`,
`GET /api/arena/jobs/{job_id}/logs`, `GET /api/arena/directors/{director_id}`,
and `GET /api/arena/schedules/{schedule_id}`. Schedule control routes are
`POST /api/arena/schedules/{schedule_id}/pause`, `/resume`, and `/cancel`.

Job specifications are validated before admission. Workers are launched by
the Arena supervisor with one CPU core, 4 GiB memory, a maximum two-hour wall
budget, and a 1 GiB artifact budget. The finite scheduler admits at most eight
active or queued jobs, requires at least 2 GiB available memory and free disk,
and stops admitting when its artifact bound is reached. A schedule has at most
32 ordered steps and a maximum seven-day admission window. The dispatcher
polls at most 100 schedules per pass and records local alerts on failures.

The optional installer at `scripts/install_schedule_timer.py` writes user
systemd unit files and enables a minutely scheduler timer. Do not run it merely
to make Veritas appear autonomous; it changes user-service state. The
`scripts/research_followup.py` workflow is a synthetic Arena latency study,
not a public-market measurement job. Its `plan` command preregisters against a
qualified baseline; `run` or `tick` may launch supervised Arena children, and
`stop` cancels its children. Use it only for a bounded, predeclared study with
an unused seed range.

There is no Veritas-specific raw-funnel worker type yet. Source replay remains
an explicit bounded command using finalized source segments. The current work
did not start a Veritas job or install a scheduler timer. See [Gate E
scheduling review 001](VERITAS_GATE_E_SCHEDULING_REVIEW_001.md) for the
integration decision and required bounds for a future adapter.

`scripts/benchmark_shadow_consume.py` also has an isolated resumable mode for
measuring shadow-consume catch-up. Pass `--work-dir` below
`data/veritas-canaries`, `--repetitions 1`, and an `--output` path inside that
work directory. The runner checks the frozen campaign and runtime snapshot,
pins their hashes and the implementation hashes in a write-once manifest,
locks the private work directory, and refuses campaign, raw-source, training,
symlink, or output-path overlap. It writes only to that isolated journal and
artifacts. Resume requires the same inputs and implementation. Cursor, replay
clock, source-seal events, and research state are checkpointed transactionally
at segment seals, the segment bound, or the configured wall-clock interval.
SIGINT and SIGTERM stop after the current source record and preserve the last
safe checkpoint. The result is a bounded replay measurement; its synthetic
clock does not establish live recovery, new market evidence, or strategy
performance. Avoid running it alongside resource-constrained production
research jobs.

## Verify Veritas code

Focused economic and forensic checks:

```bash
cd /home/charlie/midas-veritas
PYTHONPATH=packages /home/charlie/midas/.venv/bin/pytest -q \
  tests/test_veritas_economics.py tests/test_veritas_forensics.py \
  tests/test_veritas_source_replay.py tests/test_veritas_raw_funnel.py \
  tests/test_veritas_economic_scenario_study.py tests/test_veritas_execution_break_even.py \
  tests/test_veritas_followup_power.py
/home/charlie/midas/.venv/bin/ruff check \
  packages/midas/veritas scripts/veritas_forward_audit.py \
  scripts/veritas_reconcile_sources.py scripts/veritas_raw_funnel.py \
  scripts/veritas_economic_scenario_study.py \
  scripts/veritas_execution_break_even.py scripts/veritas_followup_power.py \
  tests/test_veritas_economics.py tests/test_veritas_forensics.py \
  tests/test_veritas_source_replay.py tests/test_veritas_raw_funnel.py \
  tests/test_veritas_economic_scenario_study.py tests/test_veritas_execution_break_even.py \
  tests/test_veritas_followup_power.py
MYPYPATH=packages /home/charlie/midas/.venv/bin/mypy packages/midas/veritas
```

The focused Veritas suite passes 43 tests, including synthetic execution
break-even thresholds. The full bounded Gate H verification is recorded in
[Gate H checkpoint 001](VERITAS_GATE_H_CHECKPOINT_001.md); it includes the
backend suite, strict Mypy, full Ruff and format checks, frontend tests, lint,
typecheck, build, and isolated browser runs. The browser Reality test
intercepts service operations and raw-record requests. The follow-up power
calculation is planning-only and does not submit an Arena job.

## Preserve service and evidence ownership

- Never edit `campaign.json`, frozen models, pinned source, labels, plan,
  `shadow.sqlite`, collector status, raw recording segments, or integrity files
  in `/home/charlie/midas-reality`.
- Do not restart, stop, pause, or launch a second process against the Reality
  campaign. Inspect user-service status and bounded API evidence first.
- Do not claim a fill from displayed depth or public quote persistence. All
  Veritas economics are hypothetical, all orders remain disabled, and no wallet
  or trading credentials are used.
- Keep experiments bounded and checkpointed. Use no paid services or external
  compute. Preserve raw, model, Laboratory, Arena, Prometheus, and campaign
  artifacts.
- Keep source-specific research on `project/veritas`; place platform
  integration on a dedicated branch with its own verification record. Do not
  merge either branch into `main` without a separate integration request.

## 2026-10-26 — V6 runtime and readiness handoff

The V6 implementation is integrated on the dedicated branch
`codex/veritas-v6-integration-20261026` at runtime source commit
`4f4179c72eeb6deab59c4fc5959315cf62284c85`. The production observer is pinned
separately to
`/home/charlie/.local/share/midas-veritas/releases/e988cbb0af86fe89e07da9af8036598b65068deb`.
`midas-veritas-observatory.timer` is active; the one-shot service being
inactive between runs is expected. Do not launch a manual observer in parallel
with its timer.

At `2026-10-26T03:31:11Z`, the published V6 analysis summary contained 526
snapshots: 20 processed and 506 pending (`CATCHING_UP`). Its continuous-analysis
artifact ID is `continuous-analysis`, SHA-256
`d5cd5de76a7d3e379a5acf53899cd009cf1d66cac056a23995393f75e29982be`. The
independent Decimal reference v3 had 800 repeated pair observations across
349 unique markets; 714 were primary-quality-valid, 167 independently
verified, and zero were positive-gross or net-eligible. The 547 source-quality
and 547 validity disagreement counts are category flags and can overlap; do
not report their sum as unique pairs. The latest scan had 298 unique market IDs
from 300 candidate records, 32 rotating selections, and zero stable-control
markets. Repeated observations are not independent trials.

Use the read-only API to inspect the current projection and its artifact
identity:

```bash
curl -fsS http://127.0.0.1:8000/api/veritas/overview | jq \
  '.opportunity_observatory | {analysis_version, analysis_catchup_status, updated_at_utc, processed_snapshot_count, pending_snapshot_count, summary_artifact, discovery, observation_funnel, independent_economic_audit}'
curl -fsS http://127.0.0.1:8000/api/readiness/resources | jq \
  '{captured_at_utc, host_memory, host_pressure, services, observer_last_run, staged_reality_candidate}'
```

The API and web dashboard are deployed from immutable releases `cf452ec` and
`4f4179c`; the Mission Control API reports demo mode and `live_execution=false`.
The dashboard labels the economic total as overlapping flags and keeps live,
historical, staged, and unmeasured evidence distinct. Current research
readiness remains blocked by source-quality/validity disagreements, incomplete
Reality collector observability, missing full cold-recovery evidence, API
`MemoryHigh` pressure, and three stale Arena director projections. Storage
runway is warning-level and staged Reality capacity is not active.

The latest bounded finalized-source analysis processed through ordinal
5,140,697 and reported zero pending segments for that captured prefix. That
projection is not full cold-recovery proof: the copied latest-boundary
checkpoint still covers only 2,816 of 31,742 segments. The collector continues
to report unsequenced continuity and missing persistence-window, recovery,
and queue telemetry. Never infer exact exchange-event loss from local gap
markers.

The active Reality recorder remains on its prior release and its 24 GiB / 90
day configuration. The staged 112 GiB / 120 day values still require a
guarded transition. Archive staging remains invalid for manifest and
provenance, with 1,138 finalized names outside the manifest and 58 `.copying`
files in the last verified inventory. Do not delete, adopt, or republish those
files, and do not re-enable the archive writer until ownership and integrity
are established. This document does not authorize a Reality restart or archive
mutation.

## Reality candidate follow-up (2026-10-26 03:54 UTC)

The isolated archive-provenance fix is committed as
`987481fd6ae611d062155063c19f24b5ea51bb18` on
`codex/reality-archive-provenance-20261026`; its focused operations tests pass
14/14. An isolated startup/first-durable-write receipt is recorded at
`/home/charlie/midas-engineering-mission-20261026/evidence/reality-candidate-isolated-first-write-2026-10-26.json`
(SHA-256
`21f71e585211318116ea0f0fa2a4db4767eacb6a70308ef85e7c1e872d6edb67`). It used a
temporary root and made no network requests; it is not a feed canary.

The fresh read-only deployment preflight is
`/home/charlie/midas-engineering-mission-20261026/evidence/reality-deployment-preflight-2026-10-26T0354Z.json`
(SHA-256
`53f1d11909238d91c0e73ff81fcf3351e018b4b60c219a67550a5dfc81e6c7f8`) and
is blocked. It measured the active production recorder at ordinal 5,143,954
with 31,946 finalized segments. The latest copied recovery boundary remains
incomplete (2,816/31,742 checkpoint coverage); archive inventory still has
1,138 out-of-manifest names and 58 `.copying` files. At the recorded
30-day shared-database growth scenario, the staged 90-day storage plan is
short by about 10.3 GB of current NVMe free space. Do not restart Reality or
enable archive publication on this evidence. The recorder remains on its
24 GiB / 90-day production configuration pending recovery, storage, archive,
resource, canary, and explicit-authorization gates.
