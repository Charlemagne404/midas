# MIDAS current state

**Snapshot date:** 2026-10-17 (historical operational baseline; the details below have not been refreshed for 2026-10-26).

**Current verified status:** Use the [MIDAS engineering mission report for 2026-10-26](reliability/MIDAS_ENGINEERING_MISSION_2026-10-26.md) for the later API, dashboard, Veritas V6, Reality collector, recovery, storage, and archive measurements. Its newest exact-boundary read-only preflight is timestamped `2026-10-26T04:55:04Z`. Do not treat the service health, campaign counts, resource figures, or index boundaries below as current without rechecking their capture times.

## Project status

Prometheus, Reality, and Veritas engineering is consolidated into `main`. Prometheus provides the simulation, Laboratory, Arena, provenance, and bounded research foundations. Reality provides public read-only market recording, replay, and forward shadow campaigns. Veritas provides versioned market observation, independent audits, economic sensitivities, source replay, Arena qualification, and the dashboard/API.

MIDAS has no real-order, wallet, deposit, or trading-credential path. Public observations, shadow campaigns, and Arena/Laboratory simulations do not establish real fills or profitability.

## Repository and worktrees

| Path | Branch | Purpose and dependency |
|---|---|---|
| `/home/charlie/midas` | `main` | Authoritative development checkout. Main API, dashboard, and Arena scheduler run from here. |
| `/home/charlie/midas-reality` | `project/reality` | Retained runtime checkout for the public recorder, frozen Reality campaign, successor campaign, and Reality interface. Systemd units use this path; its `data/` and `.venv/` stay local. |
| `/home/charlie/midas-veritas` | `project/veritas` | Retained data and runtime workspace for Veritas observation, source replay, gap-detail replay, Research Director, and Veritas API artifacts. Timers use this path; its ignored data remains local. |

Both feature branch histories are represented in `main`. The Reality and Veritas worktrees remain because active services and preserved runtime data depend on their paths. Do not remove either worktree until those services and their data have a separately verified migration plan. Temporary consolidation worktrees are not part of the operating layout.

Recovery refs created during consolidation:

- `recovery/preconsolidation-main-20261017`
- `recovery/preconsolidation-reality-20261017`
- `recovery/preconsolidation-veritas-20261017`
- `recovery/veritas-uncommitted-20261017` (preserved interrupted Veritas changes)

Project Atlas remains deferred. Frontier was not yet implemented at this
2026-10-17 historical snapshot; its later isolated development state is recorded
in the dated addendum below and in the Frontier engineering report.

## Frontier development addendum — 2026-10-27

Frontier development is active in the isolated worktree
`/home/charlie/midas-frontier` on branch `codex/frontier-20261026`, based on the
verified Veritas V6 integration. It is not merged or deployed. The current
development checkpoint adds bounded Polymarket and Kalshi event-group capture,
parent-event/outcome metadata, a conservative text-only relationship hypothesis
path, and Market Explorer controls. Kraken explicitly leaves event-group
discovery unsupported.

A preserved two-request public metadata capture identifies Polymarket event
`32225` and Kalshi event `CONTROLH-2026` as a related 2026 House-control topic.
The child contracts use different stated resolution schedules and details; the
relationship remains a hypothesis and the independent same-payoff verifier
rejects equivalence. No order books, synchronized quotes, or economic result
were captured. The live payloads and hashes are in
`data/frontier/live-probes/2026-10-27-public-cross-venue-house-control-r1.json`.

The focused Frontier and Arena replay suite passed 116 tests with a measured
250,324 KiB peak RSS and no swap. The frontend passed 39 tests, a production
build, and 11 isolated browser tests. A whole-repository pytest attempt remains
blocked at collection by legacy Reality/Veritas imports that are unresolved in
the selected checkout. This addendum updates Frontier development only; the
production service and protected Reality recorder state below has not been
remeasured or changed by this work.

The 2026-10-27 replay v6 development checkpoint now carries exact saved market
and book observation record IDs through API-loaded model provenance, replay
manifests, candidate legs, and content-addressed Arena snapshots. The focused
Frontier/Arena regression suite passed 118 tests at 254,696 KiB peak RSS with
zero swap. This is isolated code and fixture/local-store verification; it did
not change the database schema, production services, or protected Reality
state. See the dated Frontier mission ledger for the complete command and
resource measurements.

The latest isolated Frontier checkpoint adds revision-bound pagination for
centered two- and three-hop graph traversals. Pages preserve deterministic
breadth-first order, and wide layers are split into indexed queries while the
500-row request scan cap remains in force. The full Frontier/Arena regression
suite passed 121 tests (259,044 KiB peak RSS); the frontend passed 39 tests,
typecheck, lint, and formatting. Playwright enumerated 11 tests, but browser E2E
and a fresh production build were deferred at the 2026-10-27 11:28:57 UTC
resource sample: memory PSI `avg10` was 35.78% (`some`) and 32.22% (`full`),
swap use was 3.4 GiB, and the active API cgroup was at 527,319,040 of
1,610,612,736 bytes `MemoryHigh`. No server, production service, or protected
Reality state was changed.

The latest isolated Frontier checkpoint adds a capability-gated, operator-triggered
Kalshi multivariate-event lookup. It accepts exactly one series or collection
ticker, requests one page with nested markets, retains but does not follow the
source cursor, and persists typed event-group metadata. The genuine October 27
capture returned one event and a cursor but omitted nested markets despite the
requested flag. Its saved replay now represents membership as `omitted`, not as
an empty list; explicit `null` member data is rejected. This is event discovery
only and establishes no combo payoff or component equivalence.

The focused adapter/API regression passed 9 tests at 75,004 KiB peak RSS with
zero swaps; the focused Mission Control test passed. Frontend typecheck, targeted
ESLint/Prettier, Frontier Python Ruff/format, and strict mypy passed. Playwright
enumerated the three Frontier browser cases, including the new omitted-member
capture flow, but browser execution and a new production build remain deferred:
at 11:51 UTC memory PSI was 32.86% some / 26.88% full over 10 seconds, swap use
was 3.4 GiB, and a separate bounded Veritas batch was active. Available RAM was
9.4 GiB. Frontier did not start or change that job, any service, or protected
Reality state. The exact live artifact and source limitations are in the
Frontier engineering report and mission ledger.

## Architecture and source layout

MIDAS is a Python modular monolith with a separate React dashboard:

- `packages/midas/core`, `market_data`, `simulation`, `risk`, and `paper` contain the domain, read-only adapters, deterministic exchange, and virtual accounting.
- `packages/midas/laboratory` and `packages/midas/arena` contain durable simulated experiments and bounded research jobs.
- `packages/midas/reality` contains public recording, finalized-segment replay, and shadow-campaign code.
- `packages/midas/veritas` contains observation, source replay, measurement, audit, and economic analysis.
- `apps/api` registers the FastAPI routes and configures persistence and storage paths.
- `apps/web` contains the React command center, including Arena, Reality, and Veritas pages.
- `docs/` contains current operations guidance plus preserved historical research, checkpoint, provenance, and verification records.

The Veritas API uses source code from `main` and reads its versioned documents and runtime artifacts from `MIDAS_VERITAS_WORKSPACE` (currently `/home/charlie/midas-veritas`). This keeps the 122 MB observatory and 133 MB Arena runtime stores in place. The main Arena store remains `/home/charlie/midas/data/arena` unless `MIDAS_ARENA_ROOT` is changed.

The deployed `midas-api.service` now sets `MIDAS_VERITAS_WORKSPACE=%h/midas-veritas`; its existing recording-budget drop-in is preserved. After this deployment, `/api/health` reported `READY`, Laboratory `READY`, paper journal recovery `CHECKPOINT_VERIFIED` across 236,471 events, and `live_execution=false`. Veritas overview and artifact endpoints returned HTTP 200. API startup verified the durable paper journal for about 74 seconds; the service cgroup peaked at 8.54 GiB. At 00:53 local, cgroup use was 3.23 GiB, including 1.61 GiB `inactive_file` cache, while process RSS was 1.61 GiB. The host reported 8.0 GiB available RAM and 3.6 GiB swap in use. Allow for that startup cost when planning any future API restart.

## Services and dashboard access

The active local dashboard and API use loopback addresses:

- Main command center: <http://127.0.0.1:5173>
- Main API health: <http://127.0.0.1:8000/api/health>
- Veritas overview: <http://127.0.0.1:8000/api/veritas/overview>
- Reality API: <http://127.0.0.1:8010/api/health>
- Reality interface: <http://127.0.0.1:5180>

The main API and web development server use `/home/charlie/midas`. Reality recorder, shadow workers, API, and web services use `/home/charlie/midas-reality`. Veritas timer units use `/home/charlie/midas-veritas`; Veritas observation, source replay, gap-detail replay, and Research Director services are one-shot jobs and are normally inactive between timer runs. `midas-arena-scheduler.timer` also runs bounded dispatch checks; its service is normally inactive after each check.

The managed main dashboard is on `127.0.0.1:5173`; a separate shell-owned Vite development server also remains on `0.0.0.0:5174` in an active GNOME Terminal session. The latter has no systemd dependency and was left running with its terminal intact.

The Reality interface API on `127.0.0.1:8010` is the isolated demo preview. It returns HTTP 200 and `startup_status=READY`, but its health status is `DEGRADED`: the synthetic demo recorder exhausted its default 100,000,000-byte budget under `data/research/reality/interface/recordings`, and the service logs repeated recording-budget errors. This preview database/recording path is separate from the public collector's `data/recordings`; the collector and campaigns are unaffected. The preview API was left running without resetting its data or raising the cap. A rotation or disabled-demo-recording policy needs a separate operational decision if this preview remains in use.

At 00:53 local, the Reality recorder was running at about 704 MiB against `MemoryHigh=704 MiB` and `MemoryMax=768 MiB`; its recorded cgroup peak was about 704.3 MiB. It is near the high threshold but below the hard cap. Do not raise the limit to hide growth. The frozen Reality worker is still running but is severely behind source input; its campaign is preserved and unchanged. The successor worker is active on its own versioned campaign. Both report zero actual orders.

The frozen worker's last status showed `WARMING_OR_LAGGED_SOURCE`, 10,253 decisions, and 215,099 lagged frames skipped. Its last decision was at 2026-10-15 08:58 UTC while the status was updated at 2026-10-16 22:40 UTC. The successor status was `FORWARD_EVALUATING_EXPERIMENTAL`, with its last decision and source receipt near 2026-10-16 22:40 UTC. Do not restart, reset, reconfigure, or rewrite either campaign as part of routine deployment.

The latest gap-detail run completed at 00:51 local time with 7,383 segments processed, `status=current`, and zero pending segments. An earlier run processed 7,354 replayable finalized segments from a 7,356-segment catalog; the remaining two were recorded as empty finalized segments. Source analysis completed at 00:42 local time with 7,364 segments processed, `status=current`, and no pending source bytes. The latest public observation scan completed at 00:30 local time. The scheduled Research Director run completed at 00:45:50 local time; its next timer is scheduled for 01:15.

Historical failed one-shot Arena jobs, test suites, capture attempts, and the Reality canary remain visible in systemd's failed-unit list. They are not active processes or recurring timers. Do not clear or rerun them just to make the unit list look clean; consult their saved records and logs first.

## Data and archive locations

Mutable databases, model files, recordings, campaign state, and research runtime outputs are ignored by Git and must remain in place:

- Prometheus and main application state: `/home/charlie/midas/data/` (about 5.3 GB), including Arena and Laboratory stores.
- Reality recordings: `/home/charlie/midas-reality/data/recordings/` (about 3.4 GB); Reality research and campaigns: `/home/charlie/midas-reality/data/research/` (about 1.7 GB).
- Frozen Reality campaign: `/home/charlie/midas-reality/data/research/reality/forward/mission2/`.
- Successor campaign: `/home/charlie/midas-reality/data/research/reality/forward/mission2-successor-20261016/`.
- Veritas finalized-source observations and summaries: `/home/charlie/midas-veritas/data/veritas-observatory/` (about 122 MB); Veritas Arena store: `/home/charlie/midas-veritas/data/arena/` (about 133 MB).
- Recovery snapshots: `/home/charlie/midas-recovery-20261011T2355/` and `/home/charlie/midas-recovery-post-campaign-20261012/` (about 480 MB and 504 MB). Each snapshot manifest listed 47 files; all recorded sizes and SHA-256 values verified.
- Prometheus bundles: `/home/charlie/midas-prometheus-bundles/` (about 555 MB). All 24 `.tar.gz` archives passed a read-only archive listing/integrity check. Related bundle verification records remain in `docs/`.

The frozen Reality campaign configuration SHA-256 is `aa8acb2b46823c1a1e3ac5d01a57dde917746c2c7471098ae2a4598875e322f5`; the successor configuration SHA-256 is `c5eb8b98cbfd657372fc620192c5a0c0bb46f41d760800e680181fa7f3ee95a3`. A read-only integrity check verified both campaign identities, 20 pinned code files, four models, SQLite integrity, and event chains. The frozen journal had 113,419 events and tail SHA-256 `0d4757d1bb9d9145c90ce1ce004943dcb1c733da18617ec2a844444591a279e`; the successor had 23,657 events and tail SHA-256 `59475db679ae4c2ce8e3fe464d76046d1dde337ae07861110662c97d373f9921`. These checks did not write to the campaign directories.

## Research conclusions and evidence limits

- Prometheus demonstrated model and policy behavior in synthetic simulation. It did not establish real-market profitability.
- Reality's frozen forward state remains `insufficient_forward_evidence`; no scientific champion or real fill is established.
- The latest ledger-receipted Veritas independent audit covers 84 saved scans and 3,360 selected observations. It reports zero quality-valid positive gross candidates, zero stored-versus-independent validity/top-edge mismatches, and zero disagreements across 3,768 fee checks. The sample is finite, selected, and correlated; it is not venue-wide or evidence of fills.
- The market-quality experiment predicts the same-snapshot book-quality gate only. It reports zero positive gross candidates in its held-out panel and is explicitly not deployed as an economic strategy.
- `VERITAS_MISSION2_INDEPENDENT_OPPORTUNITY_AUDIT_021.json` contains an 85-scan result but has no matching ledger receipt. It is preserved as unreceipted evidence and is not the artifact returned by the dashboard. The API intentionally serves the newest ledger-receipted audit (scan 84).

No historical observation, campaign journal, or economic result should be rewritten to make versions agree. Synthetic execution sensitivities, public quote observations, and shadow decisions must remain distinct.

## Development and verification

From `/home/charlie/midas`, use Python 3.12+, Node 22+, Corepack, and the lockfiles. See [Development and verification](DEVELOPMENT.md) for full install instructions.

```bash
uv sync --frozen
corepack pnpm install --frozen-lockfile
.venv/bin/uv run uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
corepack pnpm dev
```

The main backend tests are run with `.venv/bin/uv run --frozen pytest -q`; frontend checks use `corepack pnpm lint`, `typecheck`, `test`, and `build`. Browser tests use `corepack pnpm test:e2e`. Tests that admit Arena jobs or start campaigns can write durable state; use a temporary data root for intentional tests and inspect the command before running it.

For focused Veritas regression tests:

```bash
PYTHONPATH=packages .venv/bin/python -m pytest -q tests/test_veritas_*.py
```

## Deferred work and operating limits

The frozen worker's lag and recorder memory growth need a separately versioned operational decision. Preserve the current campaigns, records, and source segments while making that decision. Do not change the frozen campaign configuration or journal. As of the 2026-10-17 operational snapshot, Atlas/Frontier, new market discovery, strategy expansion, training, exploratory experiments, and economic optimization were outside the maintenance scope; Frontier's later isolated development has not changed this production boundary.


## Research Readiness live state — 2026-10-26 06:38 UTC

Mission Control API release `a152999` and web release `767f330` remain active. The dashboard distinguishes measured, missing, loading, stale, and blocked evidence; live browser verification covered the V6 summary, delayed-request loading, demo labeling, and a 390 px viewport.

The latest V6 summary (06:30:54Z) is `CATCHING_UP` at 80/532 snapshots, with 452 pending. Reference v3 covers 3,200 repeated observations across 1,342 markets; 585 are independently snapshot-valid and there are zero positive-gross, supported, or net-eligible. The latest scan (`scan-20261026T063043Z-496db0ece99f`) selected 40 from a bounded population of 94 in a 299-market response union: 8 reference-random, 31 rotating-stratified, and 1 stable control. It had 33 quality-valid, 7 strict-fresh, and zero positive top-gross pairs. Seven frozen controls were missing. This scan has no v3 analysis event yet, so it is not part of the cumulative independent counts. Repeated observations are not independent trials.

Reality's atomic status receipt at 06:36:18Z reports `RECORDING_UNSEQUENCED`, ordinal 5,189,775, 16/16 fresh books, sequence verification false, 18,720 local gap markers, and no `current_error`. Its generic `ConnectionClosedOK` field has no timestamp. The active collector still uses 24 GiB / 90-day settings and reports 9,186,445,262 bytes stored. Finalized-source analysis last covered 32,213/32,213 catalog segments through ordinal 5,183,587 at 06:10:53Z; the current ordinal is 6,188 records beyond it. The latest archive provenance inventory remains invalid, with 1,138 extra names and 58 `.copying` files.

At 06:35:10Z, API memory charge was 1,609,183,232/1,610,612,736 bytes (1.36 MiB headroom), with 8 new `MemoryHigh` events over 565.771 seconds and no `max` or OOM event. Reality had 272,220,160 bytes below `MemoryHigh`; host available memory was 8.64 GB. Research admission remains blocked. The latest capacity forecast is still from 06:11Z; the staged 112 GiB / 120-day plan remains pending restart. A fresh 519-snapshot offline replay output has a complete receipt but its old verifier omitted copy-checkpoint reconciliation; this output was preserved. The reconciliation defect is fixed on the isolated Veritas integration branch and tested, but that fix has not been deployed. See [engineering mission Section 19](reliability/MIDAS_ENGINEERING_MISSION_2026-10-26.md) and `docs/VERITAS_OPERATIONS.md` for receipt hashes and remaining gates.
