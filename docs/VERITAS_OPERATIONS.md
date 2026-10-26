# Veritas operations — research procedures

As of 2026-10-26, the clean Veritas development worktree is
`/home/charlie/midas-veritas` on `project/veritas` at
`3b102928594323e7886859d348f7b2151663debb`. The scheduled V6 observer runs
from the immutable release recorded in the dated V6 handoff below. The
integrated MIDAS readiness work is isolated on
`codex/veritas-v6-integration-20261026`; it has not been merged to `main`.
Reality collection and its frozen prospective worker continue from the
separate `/home/charlie/midas-reality` worktree.

For the latest timestamped runtime values, use the final dated handoff at the
bottom of this document and the linked [MIDAS engineering mission report](reliability/MIDAS_ENGINEERING_MISSION_2026-10-26.md).
The older Gate A/B procedures and pilot notes below are versioned evidence and
protocols; their counts are not a substitute for the latest V6 projection.

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

The first V6 runtime checkpoint at `2026-10-26T03:31:11Z` contained 526
snapshots: 20 processed and 506 pending (`CATCHING_UP`). Its continuous-analysis
artifact ID is `continuous-analysis`, SHA-256
`d5cd5de76a7d3e379a5acf53899cd009cf1d66cac056a23995393f75e29982be`. The
independent Decimal reference v3 had 800 repeated pair observations across
349 unique markets; 714 were primary-quality-valid, 167 independently
verified, and zero were positive-gross or net-eligible. The 547 source-quality
and 547 validity disagreement counts are category flags and can overlap; do
not report their sum as unique pairs. The latest scan had 298 unique market IDs
from 300 candidate records, 32 rotating selections, and zero stable-control
markets at that checkpoint. Repeated observations are not independent trials.

The next scheduled update at `2026-10-26T04:32:24Z` processed 40 of 528
snapshots, leaving 488 pending. The independently versioned Decimal reference
audited 1,600 repeated pairs across 741 unique markets: 1,405 passed the
primary quality filter, 310 passed independent snapshot-validity checks, and
zero were economically supported or net-eligible. Source-quality and
validity disagreement flags are 1,095 each; they overlap and must not be
summed as unique affected pairs. The latest scan selected 8 reference-random
and 32 rotating-stratified markets, with zero stable controls. Its summary is
95,169 bytes with SHA-256
`49bc1c678f237b4d7656481218b5101585e0c57fdc6cc80020ca371002ef0bb1`; the API
artifact returned HTTP 200 with the same hash at 04:38Z.

The read-only finalized-source endpoint returned current analysis over
31,977/31,977 catalog segments (zero pending; last processed ordinal
5,148,456). Gap detail returned 32,029/32,031 segments (zero pending; last
processed ordinal 5,155,611). These are indexed finalized-source projections,
not the latest-boundary cold-recovery matrix.

Use the read-only API to inspect the current projection and its artifact
identity:

```bash
curl -fsS http://127.0.0.1:8000/api/veritas/overview | jq \
  '.opportunity_observatory | {analysis_version, analysis_catchup_status, updated_at_utc, processed_snapshot_count, pending_snapshot_count, summary_artifact, discovery, observation_funnel, independent_economic_audit}'
curl -fsS http://127.0.0.1:8000/api/readiness/resources | jq \
  '{captured_at_utc, host_memory, host_pressure, services, observer_last_run, staged_reality_candidate}'
```

At 04:48 UTC the API and web dashboard were deployed from immutable releases
`cf452ec` and `4f4179c`; the Mission Control API reported demo mode and
`live_execution=false`. At 05:03 UTC the web process moved to release
`90c625d`, while the API release remained `cf452ec`.
The dashboard labels the economic total as overlapping flags and keeps live,
historical, staged, and unmeasured evidence distinct. Current research
readiness remains blocked by source-quality/validity disagreements, incomplete
Reality collector observability, missing full cold-recovery evidence, API
`MemoryHigh` pressure, and the stale persisted state of three Arena director
manifests. The read-only production projection joins each to its owner job,
showing two cancellations and one artifact-budget failure, with zero active or
unverified directors; the manifests remain unchanged. Storage runway is
warning-level and staged Reality capacity is not active. The web fix in local
commit `90c625d4e168c64fe3c8d1f93e0c1393734fd009` handles missing Veritas
measurements safely; it was still deployment-pending in the 04:31 browser
receipt and was installed later under the verified 90c625d release below.

The 03:43Z bounded finalized-source analysis processed through ordinal
5,140,697 and reported zero pending segments for that captured prefix. The
later source/gap indexes above also report no pending catalog work; neither
projection is full cold-recovery proof. The copied latest-boundary checkpoint
still covers only 2,816 of 31,742 segments. At 04:35:56Z the protected
collector API remained degraded and unsequenced with all 16 current books
fresh, but persistence-window, recovery, and queue-depth telemetry were
unavailable. It reported 18,594 durable local gap markers, which are not an
exact lost-exchange-event count. Its current error was null; the last
`ConnectionClosedOK` error was historical and had no source timestamp.

The staged reliability candidate at `4278b5b` contains bounded persistence
latency, transport queue, backpressure, checkpoint, and resource telemetry and
passed 63 isolated candidate tests. It remains a dirty, undeployed worktree;
its isolated first-write receipt covers a separate archive-provenance-only
worktree and does not prove a feed canary or current-boundary recovery. Never
infer exact exchange-event loss from local gap markers.

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

## 2026-10-26 — final V6 and Reality candidate verification (04:55 UTC)

The scheduled Veritas V6 observer remains pinned to the immutable release
`/home/charlie/.local/share/midas-veritas/releases/e988cbb0af86fe89e07da9af8036598b65068deb`;
the integration source and Research Readiness dashboard remain on the
unmerged branch `codex/veritas-v6-integration-20261026`. The latest observed
observer publication is `2026-10-26T04:32:24Z`: analysis processed 40/528
snapshots with 488 pending. Decimal reference v3 covered 1,600 repeated pair
observations across 741 unique markets; 310 passed independent snapshot
validity checks and zero were economically supported or net-eligible. The
1,095 source-quality and 1,095 validity disagreement flags can overlap. The
latest sample had 8 reference-random, 32 rotating-stratified, and 0 stable
control markets. The 95,169-byte `continuous-analysis` summary has SHA-256
`49bc1c678f237b4d7656481218b5101585e0c57fdc6cc80020ca371002ef0bb1`.
Repeated observations are correlated and establish neither executable fills
nor profitability.

At the 04:47 API read, finalized-source analysis covered 32,035/32,035
segments through ordinal 5,156,975. Gap detail covered 32,048 replayable
segments of a 32,050-segment catalog through ordinal 5,158,905. The subsequent
04:55 metadata-only production inventory counted 32,065 finalized raw segment
names through ordinal 5,160,978, so these indexes lag the raw name boundary.
No segment contents were read or hashed by that inventory; none of these
projections proves latest-boundary cold recovery.

The clean Reality candidate is now
`/home/charlie/midas-reality-archive-provenance` at commit
`d298957afe14d6cbbc47038fbb101a96a63fadca`, with source identity
`3e17719404b0b2fd9edd05fa8b6bbc27ae6c2e4fd5a30849f0a2121319a03e9a`. Its
Reality, dashboard, and operations regression suite passed 66 tests; isolated
zero-duration first-write and checkpoint replay passed without network calls.
The candidate is not installed as a runtime release. Production remains on
PID 3007040 with the older collector. Its source is unsequenced; local gap
markers do not count lost exchange events, and persistence-window,
recovery-state, and queue-depth telemetry remain unavailable.

The fresh exact-boundary preflight is
`/home/charlie/midas-engineering-mission-20261026/evidence/reality-read-only-deployment-preflight-2026-10-26T0455Z.json`
(SHA-256
`f2cb8fa8a5947f96c94b69c8e722fe35a8a9260e3ccee730f02eee94de27ca43`). It is
metadata-only and blocked. The archive has 19,833 segment files versus 18,695
manifest entries, including 1,138 unmanifested finalized files and 58
`.copying` files; no content hashes were recomputed and nothing was adopted,
deleted, or republished. The active 24 GiB / 90-day contract projects 16.70
effective runway days; staged 112 GiB / 120-day settings project 108.14 days.
API `MemoryHigh` headroom was 14.74 MiB at the after-sample, so heavy research
admission remains blocked. No protected restart, archive mutation, or new
campaign is authorized by this handoff.

The null-safe web release `90c625d4e168c64fe3c8d1f93e0c1393734fd009` was
built from a verified Git archive, passed a fresh production build, and was
installed through
`midas-web.service.d/99-research-readiness-90c625d.conf` (SHA-256
`c5a3c87843c5499f9e8af916f793b57799d90ad78966ebc50a932c3c67116d84`). The
service changed from PID 864756 to PID 1012462; root and Veritas module
requests returned HTTP 200, including the `Not measured` label. The old
`4f4179c` release/drop-in remains available for rollback. The exact web
release manifest, post-deployment smoke receipt, and after-build integrity
receipt are listed in the mission report. The latter reverified all 1,844
tracked source blobs and eight generated assets.

At `2026-10-26T05:06:26Z`, a bounded direct resource sample showed API
`MemoryHigh` headroom of 8.72 MiB, Reality headroom of 109.8 MiB, and host
available memory of 7.95 GB. The API `high` event counter remained 10,977 with
zero OOM events. This point sample keeps heavy-research admission blocked; see
the hashed resource receipt in the mission report.

## Reality checkpoint recovery follow-up (2026-10-26 05:17 UTC)

The clean candidate at
`/home/charlie/midas-reality-archive-provenance`, branch
`codex/reality-archive-provenance-20261026`, now includes the checkpoint
prefix recovery fix in commit
`c2e73eb92173ab8dc06da460e37ee15931edf154` and the isolated startup identity
test in `a1f2fe99624ca0184835dff452a319fc2d7dcf30`. The recovery loader accepts
new catalog entries before or between saved checkpoint entries only when
those entries contain zero records; they are verified in tail replay. Prefix
source hashes and state digest checks remain mandatory, and an inserted
nonempty entry rejects the checkpoint. The only compatible prior identity is
the independently recomputed pre-fix candidate identity
`2f09ba251a65b2cac00f9e94d5c00f2e7600a5f528fb28c39d46735306ba5860`.

The full bounded Reality, recovery, dashboard, and operations regression
passed 109 tests. After the recovery documentation wording change, all 42
recovery tests passed; after adding the source-identity assertion, the
isolated startup identity test passed. Ruff and formatting passed. One
20%-CPU-quota run made the existing 50 ms heartbeat fixture exceed its
timeout; the final full run kept
the memory and task bounds but removed that artificial CPU throttle. No test
threshold changed. Detailed results and limitations are in
`/home/charlie/midas-engineering-mission-20261026/docs/reliability/MIDAS_ENGINEERING_MISSION_2026-10-26.md`.

The final fixture receipt is
`/home/charlie/midas-engineering-mission-20261026/evidence/reality-checkpoint-prefix-fix-first-write-2026-10-26.json`
(SHA-256
`982691cd267b0758997601ce2410d59005859d834371654a3ff882ac4f746075`). It
records a first durable write in 0.023 seconds, five finalized records, no
public network requests, a loopback subscription, and matching checkpoint
recovery/replay state. It is not a feed canary or current-archive recovery
proof; source sequencing remains unverified.

The 05:16:57Z read-only runtime sample reports the protected recorder still
active on PID 3007040 with its original start time. Production health remains
degraded/unsequenced and its persistence, recovery, and transport queue
telemetry remain unavailable. The API `MemoryHigh` headroom was 3,571,712
bytes; heavy research admission remains blocked. The candidate remains
undeployed. Do not restart the protected recorder or alter the ambiguous
archive based on these tests; the full current-boundary recovery, feed canary,
storage/archive clearance, and separate restart authorization remain open.

## Fresh Reality candidate preflight (2026-10-26 05:21 UTC)

The read-only preflight was refreshed for candidate `a1f2fe99624ca0184835dff452a319fc2d7dcf30`,
source identity
`53731b128faa335940acccad878294a72740cfeb49e3454c2b364fce5587f254`. The
receipt is
`/home/charlie/midas-engineering-mission-20261026/evidence/reality-read-only-deployment-preflight-2026-10-26T0521Z.json`
(SHA-256
`1c7298bec73744334e3f37be3527433a7837e4900d6fb8441ca55204055a0934`). It
remains `READ_ONLY_EXACT_BOUNDARY_PREFLIGHT_BLOCKED`; the official restart
gate was not run because current-boundary full recovery and a candidate feed
canary are absent.

The protected process remains PID 3007040 on the old deployed worktree. The
live API reports ordinal 5,169,781, 16/16 fresh books, and degraded,
unsequenced collection with three required telemetry fields unavailable. The
raw metadata inventory found 32,117 finalized segments, 32,117 sidecars, and
one 17,998-byte active `.open` file. No raw segment bytes or hashes were read.

The archive still has 19,833 finalized segment files against 18,695 manifest
entries, including 1,138 names outside the published manifest and 58
`.copying` files totaling 16,471,242 bytes. The manifest's own list hash and
recording-root reference match, but the live integrity projection still
reports invalid provenance. Nothing was adopted, removed, or republished.
The latest capacity projection estimates about 18.4 storage-only days for the
active contract at its observed rate; the staged 112 GiB / 120-day candidate
projects 108.12 days. API `MemoryHigh` headroom is now 1,060,864 bytes, so
heavy research admission remains blocked. The candidate is undeployed, and
this metadata preflight does not change that deployment decision.

## Candidate bounded public feed canary (2026-10-26 05:24 UTC)

The exact candidate then ran a 100-second unauthenticated public feed canary
with isolated temporary storage and bounded resources. It stopped cleanly,
persisted 322 frames, verified four periodic checkpoints, and received 37/37
HTTP 200 responses. Six book comparisons matched local unsequenced state; one
reported stale local state; there were no invalid/divergent comparisons or
collector failures. Full replay matched checkpoint recovery. The canary's
resource cgroup peaked at 35,618,816 bytes with no memory or OOM events.

Only 8/16 outcome books were fresh at the final checkpoint, so the full
coverage condition failed. Keep this as a blocker and preserve the existing
60-second freshness threshold. The receipt is
`/home/charlie/midas-engineering-mission-20261026/evidence/reality-candidate-live-feed-canary-2026-10-26T0524Z.json`
(SHA-256
`b6a7d5798edee24562259f439f43b8adcc574b039f45d13bd4ff093bd9fa79e2`). The
first harness attempt failed before discovery because its synchronous HTTP
event hook was awaited; the failure receipt is retained separately. The
temporary canary root was removed after verification. This canary is not a
current-boundary recovery proof and does not establish execution or
profitability. The protected recorder remains on PID 3007040 and the official
deployment gate remains blocked.

A 05:28:11Z direct cgroup read confirmed the Reality, API, and web PIDs were
unchanged. API `MemoryHigh` headroom was 1,593,344 bytes (1.52 MiB), with zero
OOM events; Reality headroom was 102,039,552 bytes, also with zero OOM events.
No temporary canary root remained. Receipt:
`/home/charlie/midas-engineering-mission-20261026/evidence/live-service-post-canary-2026-10-26T0528Z.json`
(SHA-256
`30771c1c33406515c2824192307d17ce62ad013c094893974a25db33f331b089`).

## Readiness memory composition candidate — 2026-10-26

The candidate readiness API adds `services.<service>.memory_composition_bytes`
to `/api/readiness/resources`. It reads a fixed allowlist of byte counters from
cgroup `memory.stat`: `anon`, `file`, `shmem`, `active_file`, and
`inactive_file`. `shmem`, `active_file`, and `inactive_file` overlap the broad
`file` counter and must not be added to it. File-backed pages may be reclaimed,
but they remain part of `memory.current` and count against `MemoryHigh`.
Missing or oversized input returns a not-measured composition while the
charged-memory and admission fields remain unchanged.

The dashboard presents anonymous and file-backed values beside the charged
cgroup total, with a note that prevents double counting. This is an
observability addition only; it neither diagnoses a leak nor changes the
95-percent research admission hold. **Historical 05:37Z status:** the tested
candidate was local commit `d56cdcf42293de76649feb7df181ff783b30c4b9` on
`codex/veritas-v6-integration-20261026`, before deployment. The services now
run API release `a152999` and web release `767f330`, as documented in the
following 05:59Z deployment section. The measured snapshot and verification receipt is
`/home/charlie/midas-engineering-mission-20261026/evidence/readiness-memory-composition-2026-10-26T0537Z.json`
(SHA-256
`a8ceb73b06e0dc04d9c06182bf43bf1dccae646083628b7224eb80d3aff5e972`).


## Research Readiness deployment — 2026-10-26 05:59 UTC

The live Mission Control API and web service now run immutable releases `a152999` and `767f330`. API source revision is `a1529991a880965a8ad37a7528e2c4cabfc341d8`; web source revision is `767f33006db115d66ec22eaa8dc8c3f6a3675e30`. The API exposes bounded cgroup `memory.stat` composition at `/api/readiness/resources`; the dashboard shows anonymous/file-backed charge while retaining `memory.current` for resource gates. During first fetch, it announces pending evidence sources and keeps gates unpassed until the response arrives.

The live V6 projection at the 05:59Z receipt is `CATCHING_UP` at 60/530 snapshots, with 470 pending. Its Decimal reference contains 2,400 repeated observations across 1,032 unique markets: 2,047 quality-valid, 428 independently verified, zero positive-gross and zero net-eligible. The source-quality and validity flag counts are separate overlapping categories. None of these repeated observations are independent trials. Finalized-source analysis is current at 32,153/32,153 indexed segments, but no full latest-boundary cold-recovery receipt is reported. The collector remains unsequenced and its local gap markers are not an exchange event-loss count.

The live dashboard run classifies the API resource gate as blocked: API cgroup charge is near its `MemoryHigh` boundary. The API release startup verified its 675k-event paper journal in 4m32s and read approximately 7.47 GB; no OOM occurred, but point samples showed elevated host I/O pressure during verification. Avoid overlapping the next API restart with a heavy research job. Existing rollback releases are `cf452ec` (API) and `90c625d` (web). Full receipt and browser screenshot are recorded in the engineering report's Section 15.


## V6 persisted state and catalog verification — 2026-10-26 06:08 UTC

The latest successful bounded observer run completed at `2026-10-26T06:01:54.492061Z`. V6 remains `CATCHING_UP` at 70/531 snapshots, with 461 pending. Independent reference v3 audited 2,800 repeated observations across 1,173 unique markets: 2,333 primary-quality-valid, 497 independently snapshot-valid, 1,836 source-quality disagreement flags, 1,836 validity disagreement flags, and zero positive-gross, economically supported, or net-eligible observations. The disagreement categories overlap; repeated pairs are not independent trials.

The latest public scan (`scan-20261026T060143Z-c4756dc31eb7`) selected 40 markets from a bounded eligible population of 165: 8 reference-random and 32 rotating-stratified, with no stable controls available. It recorded 34 quality-valid pairs and zero positive-gross candidates. Its compressed snapshot SHA-256 matches the catalog's compressed-file identity; the recomputed semantic evidence digest matches the scan ID and snapshot metadata. The distinction matters: the semantic digest is not the compressed file hash.

Both current SQLite catalogs passed read-only `PRAGMA integrity_check` at `06:08:17Z` in 0.297 seconds (`snapshot-catalog-v4.sqlite3`, 6,094,848 bytes) and 0.194 seconds (`analysis-catalog-v6-independent-v3.sqlite3`, 3,248,128 bytes). Their files were unchanged during the checks. This verifies page integrity at capture time; it does not establish a full source replay or economic profitability. Full receipt identities and limitations are in [engineering mission Section 16](reliability/MIDAS_ENGINEERING_MISSION_2026-10-26.md).


## Finalized-source catch-up refresh — 2026-10-26 06:12 UTC

The scheduled finalized-source analyzer completed successfully at
`2026-10-26T06:10:53Z` under its existing 128-segment / 32 MiB per-run limits.
It processed 60 segments (15,808,351 bytes) in the batch. The digest-checked
summary now reports 32,213/32,213 finalized catalog segments, zero pending,
and last processed ordinal 5,183,587. At the separate 06:11:53Z collector
status read, the live ordinal had advanced to 5,183,903. This closes the
incremental catalog backlog at the analysis boundary but leaves the newer
collector tail and full cold-recovery proof unresolved. Receipt identity and
limitations are documented in [engineering mission Section 17](reliability/MIDAS_ENGINEERING_MISSION_2026-10-26.md).


## V3 fee-bound verification and resource refresh — 2026-10-26 06:23 UTC

The independent V3 fee calculation was checked against [Polymarket's published fee formula and precision](https://help.polymarket.com/en/articles/13364478-trading-fees).
For per-match raw fee `f` and `q = 0.00001`, floor rounding is at most `f`;
half-up rounding is zero below `q/2` and at most `f + q/2 <= 2f` otherwise.
The resulting `ceil(2 × raw fee)` bound remains conservative across unknown
fill counts when summed by price level. It is a hypothetical cost bound on
displayed depth, not evidence of fills or realized economics. A new unequal
fragmentation fixture checks both floor and half-up modes across three prices
per outcome leg. The independent economics, fee-envelope, and V2 scanner suites
passed 63 tests. The V3 reference/catalog remain in place; no runtime or
historical data changed.

The current API resource receipt at `2026-10-26T06:22:56.752894Z` shows
1,606,393,856 / 1,610,612,736 bytes charged below `MemoryHigh`, leaving 4.02
MiB. Reality had 272,154,624 bytes below its `MemoryHigh`. No new high or OOM
event was measured for either service. Host I/O full PSI was 0.99% avg10 while
both service cgroups reported zero at avg10. The resource gate remains blocked
by the API's greater-than-95% charge. The receipt is
`/home/charlie/midas-engineering-mission-20261026/evidence/readiness-resource-sample-2026-10-26T0623Z.json`
(SHA-256 `dfda3ec6d3e48b4d837229f17f87e2c6e53b1a16acf8109948663333abe32a9b`).
Full test identities and the persisted-summary boundary are in [engineering mission Section 18](reliability/MIDAS_ENGINEERING_MISSION_2026-10-26.md).


## V6 checkpoint reconciliation and current boundary — 2026-10-26 06:38 UTC

The bounded observer completed successfully at 06:30:54Z. Its V6 summary is `CATCHING_UP` at 80/532 snapshots, with 452 pending. Reference v3 covers 3,200 repeated observations across 1,342 markets, with 585 independently snapshot-valid and zero positive-gross, supported, or net-eligible. The newest scan is `scan-20261026T063043Z-496db0ece99f`: 40 selected from a bounded eligible population of 94 in a 299-market response union, with 8 reference-random, 31 rotating, and 1 stable random control; 7 frozen controls were unavailable. It has 33 quality-valid and 7 strict-fresh pairs, with no positive top-gross pairs. There is no v3 analysis event for this scan yet. Do not combine it with the processed-prefix totals. Summary and scan hashes are in engineering mission Section 19.

The 06:35:10Z resource receipt shows the API at 1,609,183,232 / 1,610,612,736 bytes `MemoryHigh` (1.36 MiB headroom), with 8 high events over 565.771 seconds and no OOM. Heavy research and full replay admission remain blocked. The Reality collector status at 06:36:18Z is `RECORDING_UNSEQUENCED`, 16/16 fresh, ordinal 5,189,775; the source-analysis receipt remains through ordinal 5,183,587. The intervening 6,188 record ordinals and current tail do not have cold-recovery proof. The recorder remains on its 24 GiB / 90-day configuration. The invalid archive and its extra files remain untouched.

An existing isolated output at `/home/charlie/midas-engineering-mission-20261025/data/veritas-v6-offline-replay-v3-20261026` contains a 519-snapshot complete receipt and a canonical self-consistent post-run verification. The old verifier reports `copy_checkpoint_reconciliation=null`; the artifact was not rewritten. On `codex/veritas-v6-integration-20261026`, commit `6702a9a610a280181547dcd71fd5a6d599a45132` fixes completed-resume attestation with bounded append-only reconciliation history and backward-compatible legacy-record migration. Twenty-one tests across the replay and continuous-analysis files pass under a 256/384 MiB memory scope and 10% CPU. This code has not been deployed and must not be used to rewrite the preserved output. Exact hashes and status details are in engineering mission Section 19.

Arena lifecycle reconciliation at 06:38Z found 37 failed job-unit records, each matched to a durable terminal `job.json`; no active Arena worker, missing record, or nonterminal mismatch was found. The scheduler completed successfully. Failure history remains intact.
