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

A separate one-GET follow-up to Kalshi's public event-detail endpoint returned
HTTP 200 for the same ticker. The `event` object omitted its nested `markets`
field while the documented top-level `markets` array was explicitly empty.
Adapter v7 rejected that shape; adapter v8 now replays it as a valid empty
event-detail batch. The preserved raw response and separate hash-verified replay
row are in `data/frontier/live-probes/2026-10-27-kalshi-mve-event-detail-r1.json`.
This confirms no child markets in those two bounded responses, not venue-wide
absence or payoff semantics.

Adapter v9 extends the explicit MVE probe filter to one event ticker, mapped to
the documented `tickers` query parameter and checked against the returned event
ID. A preserved single-request capture returned one event, no cursor, and no
nested-market field. Exact raw-response replay through the local API stores the
event with membership state `omitted`; the raw body and isolated store-row hash
are recorded in
`data/frontier/live-probes/2026-10-27-kalshi-mve-ticker-filter-r1.json`. The
harness cleanup raised an event-loop error only after response capture and
store read-back completed; the request was not repeated. This is event lookup,
not evidence of child contracts, combo payoff, or venue-wide inventory.

The isolated Frontier branch now has adapter v10's one-market Kalshi metadata
lookup, exposed only for a selected component ticker already referenced by a
saved MVE market. It validates parent market/event identity and persists
`market_metadata` rows into market queries and graph revisions. One public
capture returned the referenced Brandon Miller 2+ assists contract as closed;
its rules include fair-price fallback cases. Raw and row hashes are preserved
in `data/frontier/live-probes/2026-10-27-kalshi-mve-component-market-r1.json`.
This child-level source observation does not verify combo payout or economics,
and the Frontier branch remains undeployed.

The current isolated branch is Kalshi adapter v13, Polymarket adapter v5, and
Kraken Spot adapter v2. It retains Kalshi's optional
`yes_settlement_value_dollars` component field and adds a local-only arithmetic
audit comparing the recorded selected-component product with the parent MVE's
recorded settlement value. The audit requires complete component values and a
settled parent with `is_provisional=false`; an absent flag remains non-final
evidence. Otherwise it reports incomplete, non-final, or unsupported evidence.
Audit schema v2 pins algorithm `kalshi-mve-settlement-audit-2` and returns the
parent lifecycle and recorded provisional flag with source observation and
raw-body hashes. The dashboard displays these values. The audit
does not make a source request or generate a candidate. Kalshi's public
[combo guidance](https://help.kalshi.com/en/articles/13823820-combos),
[NO scalar rule](https://help.kalshi.com/en/articles/17515177-protected-nfl-player-markets),
and [MVE API schema](https://docs.kalshi.com/api-reference/events/get-multivariate-events)
are included in the inspector. Only documentation-shaped fixtures currently
contain the required parent and component values; no live settlement finding
is available. Initial adapter/audit commit: `8a3e25c`.
Commit `364478853908272f5b860758fa0bb18b52b3efc8` tightens finality handling:
the local audit now requires explicit `is_provisional=false` and returns the
versioned algorithm/finality fields in schema v2. Focused unit, API, and UI
checks pass; live settlement values remain unavailable.

### Polymarket versioned book and settlement mapping

Polymarket adapter v5 routes Gamma `version=v1` CTF-token books to
`clob.polymarket.com` and `version=v2` position-ID books to the documented
`clob-v2.polymarket.com` host. For v2 positions, it maps settlement to pUSD on
Polygon (`eip155:137`, token address
`0xc011a7e12a19f7b1f670d46f03b03f3342e82dfb`); market payoff and resolution
remain unverified. V1 market settlement identity remains absent because the
Gamma asset-ID schema alone does not attest a market's collateral route.

A bounded v1-host live book probe at `2026-10-27T14:16:33.559710Z` returned
HTTP 200 and is preserved in
`data/frontier/live-probes/2026-10-27-polymarket-clob-v1-book-r1.json`. The
earlier direct request to the documented v2 host failed DNS resolution from
this development environment. The v2 route is therefore fixture-tested and
live validation remains pending. No order, authenticated call, or service
change was made.

Verification for this checkpoint: the full Python Frontier/Arena suite passed
148 tests before only the output's official-source-link field was added; the
latest focused Python selection passed 17 tests with that field. The 40-test
frontend suite, all four Frontier browser cases, production frontend build,
typecheck, lint, format, Ruff, and strict mypy passed. At 13:01 UTC, memory PSI
`avg10` was 38.72% (`some`) / 32.96% (`full`), available RAM was 9.93 GB, and
3.46 GiB of swap was in use. No additional full Python run was started under
that pressure. No deployment, new public capture, protected-service change, or
Reality action was made. See the Frontier report and mission ledger for the
test boundary and remaining acceptance work.

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

## Frontier development checkpoint — 2026-10-27

On isolated branch `codex/frontier-20261026`, commit
`9d7b599516ca70895525c701543c507054bcfbe6` adds a candidate-detail virtual
funding comparison. Manually entered balances stay in browser state, are
compared with exact decimal arithmetic separately per venue, and are never
pooled or sent to an API. Unknown venue fees remain unresolved. The Frontier
component tests passed 8/8, the focused depth-two/capital-fragmentation/mobile
Playwright case passed, and frontend typecheck, ESLint, and Prettier passed.
The production build after this UI change was stopped before completion as
memory PSI rose; it remains unverified. The latest sampled PSI (`13:13:42Z`)
was 38.92% (`some`) / 33.95% (`full`), with 9.3 GB available RAM and 3.5 GiB
swap used. No source, service, production configuration, or Reality evidence was
changed. This development checkpoint does not update or measure the operational
Reality/Veritas state above. See the [Frontier mission ledger](frontier/FRONTIER_MISSION_LEDGER.md)
and [engineering report](frontier/FRONTIER_ENGINEERING_REPORT.md).

Review follow-up commit `cca4038` disables virtual-funding comparison if any
leg is missing a quote currency. The Frontier component file now passes 8/8
tests after this correction, and the web TypeScript typecheck passes. The
focused depth-two/capital-fragmentation/mobile browser case predates the fix
and was not rerun. The production build remains unverified because it was
stopped under rising PSI.

## Frontier economics and API provenance checkpoint — 2026-10-27 13:28 UTC

The isolated Frontier branch adds a fail-closed USD/USDC denomination guard to
same-payoff verification, binary and multi-outcome candidate generation, and
the independent economic audit. A focused six-test regression group passed.
The Polymarket v2 trade-page and generic market/book/trade probe now preserve
raw response captures drained before lineage checks; already persisted earlier
captures are removed from the pending failure set to avoid duplicates. Four
focused API tests passed, including byte/hash readback from temporary stores.
Ruff check and formatting passed for the changed code. These checks used
fixtures and mock HTTP responses, not live exchange calls.

The source health `requests_in_window` field now counts the trailing 60 seconds
of bounded monotonic-time request history instead of the transport lifetime
counter. Commit `3f8a5cabfe209d105d0ddde948f9862cf72fb8fb` adds the metric and a
focused adapter regression; one test passed. This does not change probe rate
limits or make health reads call a venue.

Cross-venue candidate timing now also requires equal known timestamp semantics,
timestamps no later than the replay time, and observed timestamp skew plus
declared source clock uncertainty within the scenario limit. Commit
`25a9cc711976da49b80bdaacc3b51c2ac6f82bae` adds the guard; its focused test
passed. Existing public adapters leave clock uncertainty unspecified, so live
cross-venue timing remains unverified.

At the latest resource sample (`13:28:55Z`), host memory PSI was 39.81%
(`some`) / 34.86% (`full`) over `avg10`, with 9.1 GB available RAM and about
553 MiB swap free. Broader test suites, the Frontier production build, and the
UI typecheck were not run. The earlier interrupted production build remains
unverified; no production service or historical evidence changed. See the
[Frontier ledger](frontier/FRONTIER_MISSION_LEDGER.md),
[engineering report](frontier/FRONTIER_ENGINEERING_REPORT.md), and
[operations guide](frontier/FRONTIER_OPERATIONS.md).

## Frontier focused regression checkpoint — 2026-10-27 13:40 UTC

The core API, adapter, and economics test files passed 99 tests with one
Starlette/httpx deprecation warning. The web component file passed 8/8 tests,
including the per-leg missing-currency case, after test commit
`f206dfedc34cf3fafae0b74afc5e13376c036b4a`; TypeScript typecheck, targeted
ESLint, and Prettier passed. No live source or browser E2E run occurred in this
checkpoint.

Targeted mypy exited 1 on 14 diagnostics in four unmodified imported
Veritas/Arena modules and reported none in its six explicit Frontier/API
targets. The complete repository test suite, remaining Frontier/Arena tests,
and production build remain unverified. The separate Frontier engineering
report records the exact commands and mypy module names.

### Frontend build retry — 2026-10-27 13:42 UTC

`corepack pnpm --dir apps/web build` completed TypeScript and started Vite
transformation, then was stopped with Ctrl-C (exit 130) after a follow-up
sample about five seconds later showed PSI `avg10` at 10.74% (`some`) / 8.37%
(`full`). At `13:42:24Z`, PSI `avg10` was 22.14% / 16.01%, `avg300` was
14.22% / 12.27%, available RAM was 9.1 GB, and free swap was about 553 MiB.
The production bundle remains unverified; no service or source was contacted.

### Settlement asset identity checkpoint

`FrontierMarket` and `PayoffSpec` schema v2 now carry a structured
`settlement_asset_identity`. Non-fiat identities require a network ID and asset
reference, and relationship verification, opportunity generation, and the
independent audit require the market and payoff identities to agree exactly.
The token-ticker fixture verifies for the same identity and is rejected when
the network differs. Kalshi event contracts normalize to `fiat:USD`.
Polymarket Gamma v2 position markets now map to pUSD on Polygon; v1 markets
remain without a canonical settlement identity. Both Polymarket payoff paths
remain unverified, so the mapping creates no live cross-venue economic claim.
The identity is normalized protocol evidence, not an independent market
payout attestation. V2 book routing is fixture-verified; live host validation
is pending, while a separate current v1-host book capture is recorded.

Focused regression verification on this checkpoint passed: 25 relationship,
economics, and replay tests; 60 adapter, storage, and replay-comparison tests;
two API tests; two Frontier UI tests; TypeScript typecheck; Ruff; ESLint; and
Prettier. No full repository suite, production frontend bundle, live token
integration, or browser E2E was run for the schema checkpoint. The subsequent
v1-host public snapshot and unresolved v2 hostname attempt are documented in
the Polymarket route subsection and live-probe manifest. The exact test
commands and interpretation are recorded in the Frontier engineering report.

## Frontier exact-denomination checkpoint — 2026-10-27

Commit `03dbc92` extends canonical denomination identity from market settlement
to instrument quote, public book, fee schedule, trade, candidate leg, and modeled
capital. The binary and multi-outcome evaluators require the instrument and
book quote units to match the exact settlement identity; the independent audit
rechecks quote, book, fee, and capital identities. A token whose display code is
`USD` cannot match `fiat:USD`. Older records still load with identity unknown
and remain ineligible for supported candidate arithmetic. Mission Control keeps
virtual balances separate by venue and canonical denomination.

The full Python Frontier suite passed **153 tests** with one existing
Starlette/httpx deprecation warning. The Frontier component file passed **8/8**;
TypeScript, targeted ESLint, Prettier, Ruff, and `git diff --check` passed. The
isolated depth-two graph and venue-fragmented-funding Playwright case passed.
The production frontend build completed in **13 seconds** at **676,320 KiB peak
RSS**, with no swaps; Vite retains a chunk-size warning for the main and chart
bundles. No live exchange request, deployment, production service change, or
Reality/evidence mutation occurred. The full repository suite, full browser
suite, and live Polymarket v2 host/settlement validation remain outstanding.
See the [Frontier ledger](frontier/FRONTIER_MISSION_LEDGER.md) for reproduction
commands and the [engineering report](frontier/FRONTIER_ENGINEERING_REPORT.md)
for the current component matrix.

## Frontier source-data terms hold — 2026-10-27

An official-source terms review found that the Kalshi Developer Agreement and
[Data Terms](https://kalshi-public-docs.s3.amazonaws.com/kalshi-data-terms-of-service.pdf)
restrict the relevant API/data use outside the stated member-trading purposes.
Kraken's [EEA Terms effective 26 February 2026](https://assets-cms.kraken.com/files/51n36hrp/facade/e7cb2e6758f56b3eaa044d4b0b8097f2d1252a63.pdf)
restrict use and extraction of pricing data; the applicable regional terms and
MIDAS authorization have not been established. New Kalshi and Kraken live
captures remain held. Existing capture files remain preserved unchanged, with
new research/replay use treated as restricted pending review.

The API has no validated permission loader for Kalshi or Kraken. Both source
probe properties therefore remain false even when a probe flag and arbitrary
reference string are configured. Source routes surface the unconditional
policy hold, existing stored rows remain quarantined, and readiness keeps the
source-data-permissions gate `BLOCKED`. A reference string alone is not
permission. The regression and its verification are tracked in the
[Frontier ledger](frontier/FRONTIER_MISSION_LEDGER.md); implementation is
committed in `52b6a9e`. The focused API module passes **4/4** and the full
Frontier suite passes **219/219** with the runtime guard active; strict mypy,
Ruff, formatting, and diff checks pass. The fixture results do not establish
source permission or live validation. No source request, external message,
production change, or historical-data mutation was made for this review.

Code commits `d38f517`, `73e008e`, `e7958c1`, and `23f9860` extend the hold to
Frontier application reads: old Kalshi/Kraken market, book, trade, and
observation routes are filtered; relationships and graph edges touching held
venues are excluded; stored runs/comparisons and Arena replay artifacts with
held-source provenance are quarantined; new replay inputs omit held
observations; and generic Arena job views, research-activity digests, replay
submission, and cancellation enforce the same snapshot check.
Controlled fixtures verify those filters while confirming old records remain
stored. Arena checks held snapshots before its reconciliation path, preserving
the job manifest during blocked reads.
Direct database inspection, exports, and other paths outside those APIs remain
held pending the source review. A later test-source audit found 15 direct
capture-path references in two Frontier test modules; the 18:41 UTC full
Frontier suite executed those cases and read the referenced preserved files.
No test writes to those files were identified, and no mutation is known. All
15 references are now replaced by synthetic inputs; a `rg` scan over
`tests`, `packages`, and `apps` finds no `live-probes` path. The static source
guard passes, the converted adapter/API selection passes 24 tests, and the
full Frontier suite passes 219 tests in 39.83 seconds at 335,396 KiB peak RSS
with zero swaps. The existing Starlette/httpx deprecation warning remains.
These fixtures establish code behavior only; source permission and live
validation remain blocked. See the
[source-data terms review](frontier/SOURCE_DATA_TERMS_REVIEW_2026-10-27.md)
and [Frontier ledger](frontier/FRONTIER_MISSION_LEDGER.md).

## Frontier source-boundary and UI regression checkpoint — 2026-10-27

Commit `5e51a88` replaces the 15 direct test reads of preserved
`data/frontier/live-probes` artifacts with synthetic local response data and
adds a static test-source guard. The historical 18:41 full suite did read the
then-referenced files; no test write or capture mutation is known. Since the
cleanup, the guard passes and the full Frontier suite passes **218 tests**
(39.36 seconds, **333,988 KiB peak RSS**, zero swaps). The 24-case changed
adapter/API selection also passes. No held capture is used by the new fixture
tests.

The settlement-identity UI hardening now compares typed fields and uses a
structured balance key. Frontier's component suite passes **8/8**, the full web
suite **40/40**, and the isolated Frontier browser spec **4/4**. Typecheck,
targeted ESLint, and Prettier pass. The post-change production build passes at
**714,944 KiB peak RSS** with zero swaps; the existing Vite large-chunk warning
remains. Browser tests used temporary local services/databases and no exchange
probes. No production deployment, protected-service change, live source request,
or historical capture modification occurred. The code/docs verification
checkpoint is in progress on the Frontier branch; source permission, live
cross-venue economics, deployment, and repository-wide tests remain open.

After the earlier 218-test run, an autouse runtime file-open guard was added,
reviewed, and hardened against symlink/`..` traversal and relative `dir_fd`
opens in commit `df30fa7`. Its temporary-path cases pass **2/2**. The full
Frontier suite now passes **219 tests in 39.83 seconds**, with **335,396 KiB
peak RSS** and zero swaps; Ruff and format checks pass for the guard. The only
warning is the existing Starlette/httpx TestClient deprecation. No held source
file was opened by the new tests or changed in this work. The source permission
hold and live economic validation remain unresolved.

## Frontier Kalshi fee-override checkpoint — 2026-10-27

Kalshi's documented event-fee rule is now represented explicitly. Adapter v15
records a complete event override, an explicitly cleared override that inherits
series terms, a partial override, or unreported override fields. The local
one-fill and one-order fee sensitivities now reject partial and unreported
states. Mission Control displays the fee-resolution state next to the native
parameters. This uses official documentation and bounded fixtures only; no new
exchange request or read of held Kalshi capture data was made. Schema-v1 fee
metadata remains readable and is treated as unresolved for sensitivity work.
The canonical candidate fee schedule remains unknown, and source
permission/deployment gates remain blocked/deferred. See the [Frontier engineering report](frontier/FRONTIER_ENGINEERING_REPORT.md)
and [mission ledger](frontier/FRONTIER_MISSION_LEDGER.md) for exact tests and
limitations.

## Frontier relationship-review history checkpoint — 2026-10-27

The isolated Frontier branch now exposes immutable relationship review history
through hash-checked keyset pages, with a bounded on-demand review panel in
Mission Control. The endpoint rejects relationships involving held sources,
and controlled fixtures cover pagination, corrupt-record rejection, and the
quarantine boundary. Reviewer labels and assertion IDs remain self-attributed;
they are not authenticated. The 13-test review API module, held-source
quarantine integration test, and 8-test Frontier UI component suite pass;
frontend typecheck, ESLint, Prettier, and Python Ruff checks also pass. No
public source request, held-data read, production service change, or deployment
occurred. A fresh production build and browser E2E were deferred at the host
memory-pressure sample. Frontier remains isolated, incomplete, and undeployed;
see the [Frontier mission ledger](frontier/FRONTIER_MISSION_LEDGER.md) and
[engineering report](frontier/FRONTIER_ENGINEERING_REPORT.md).

## Frontier bounded graph text search — 2026-10-27

The relationship explorer now submits text searches to the local API and pages
through a deterministic breadth-first result window. Its cursor pins the query,
depth, page size, and graph revision; stale cursors are rejected. Search remains
limited to at most 200 recorded market records and 500 relationship rows, and
Mission Control labels that scope. The Frontier API module passed **44 tests**;
the final depth-two search pagination regression also passed independently.
The Frontier UI component passed **8 tests**, including search and page
navigation; TypeScript typecheck, ESLint, Prettier, and Ruff checks passed.
The production build and browser E2E were deferred at the host PSI sample.
Frontier remains a research-only development branch, incomplete and
undeployed; this does not provide full-universe coverage or a genuine economic
result. See the [mission ledger](frontier/FRONTIER_MISSION_LEDGER.md) and
[engineering report](frontier/FRONTIER_ENGINEERING_REPORT.md).

## Frontier Kalshi schedule clarification — 2026-10-27

Commit `410860a` records an official-document check: the July 7, 2026 Kalshi
fee schedule labels its non-standard columns Maker Multiplier then Taker
Multiplier, so the `KXMVE` row means maker 2 / taker 1. This resolves the
column-order reading only. It does not establish that the row applies to the
different `KXMVECROSSCATEGORY` series in preserved evidence or settle account
precision, maker fees, or mixed-order economics. No source request or held-data
read occurred and no code or test files changed. The existing two-case
synthetic fee-type regression passed **2/2** in 0.30 seconds at **54,520 KiB
peak RSS** with zero swaps; this verifies local taker arithmetic only. Frontier
remains isolated and PARTIALLY VERIFIED; Kalshi/Kraken source permission, live
cross-venue economics, broader regression, and production deployment remain
unresolved.
See the [Frontier ledger](frontier/FRONTIER_MISSION_LEDGER.md) and
[engineering report](frontier/FRONTIER_ENGINEERING_REPORT.md).

## Frontier Kalshi price-range checkpoint — 2026-10-27 19:44 UTC

The isolated Frontier branch now normalizes Kalshi `price_ranges` as exact
decimals in FrontierMarket schema v4 and Kalshi adapter v17. The new instrument
field distinguishes absent metadata from an explicitly empty range list, and
both candidate generation and independent audit enforce reported intervals.
The shared model caps decimal precision at 18 places to reject enormous
scientific-notation exponents before rational arithmetic.
The implementation uses `start` as the step-grid anchor by inference from the
official schema's `start`/`end`/`step` shape. Because endpoint inclusivity is
undocumented, prices at range boundaries fail closed. This is fixture-verified
behavior only; no live request or held-data read occurred.

The focused Python adapter/economics/replay/API selection passed **17 tests**
with one existing deprecation warning at **78,936 KiB peak RSS** and zero swaps.
The full Frontier UI component file passed **8/8** in 3.31 seconds, including
the new constraint display. TypeScript, targeted ESLint, Prettier, Ruff, strict
mypy on five production modules, and `git diff --check` passed. Parser
regressions reject non-arrays, oversized and overlapping
ranges, out-of-domain values, missing/numeric fields, overlong decimals, and an
extreme exponent. At `2026-10-27T19:46:50Z`, memory PSI `avg10` was 41.09% `some` /
36.23% `full`, with 9.2 GiB available and 468 MiB swap free. The broad suite and
production build were deferred. Frontier remains isolated, research-only,
PARTIALLY VERIFIED, and undeployed; live source permission, price-range
semantics, multi-venue economic validation, and deployment remain open.
The implementation is in commit `47f399d`; commit `52abaad` adds adversarial
parser fixtures and the expanded verification checkpoint.
The complete Kalshi/Polymarket/Kraken adapter test module passed **60 tests**
in 2.65 seconds at **60,504 KiB peak RSS** with zero swaps; this is not a full
Frontier regression. At `2026-10-27T19:45:58Z`, memory PSI `avg10` was 47.18%
`some` / 41.86% `full`, with 9.3 GiB available and 468 MiB swap free.
The full Frontier UI component file also passed **8/8** in 3.31 seconds.
Next safe work is an offline review of incomplete cross-venue capital and
settlement costs, leaving unsupported FX/transfer costs unknown. Recheck host
pressure before the broader suite; keep source permission and deployment gates
unchanged.

## Frontier regression and build checkpoint — 2026-10-27 19:50 UTC

After PSI eased, the complete Frontier Python suite passed **230/230** in
39.45 seconds at **335,348 KiB peak RSS**; the full web suite passed **40/40**
across seven files at **298,344 KiB peak RSS**. Both completed with zero swaps.
The isolated Frontier browser spec passed **4/4** in 9.7 seconds, one worker,
at **190,708 KiB peak RSS** with zero swaps. Playwright used temporary API,
SQLite, Arena, Frontier, and test-output paths; all local test servers stopped.

The production build passed to
`/tmp/midas-frontier-web-build-20261027-1949`, compiling 2,228 modules in 4.69
seconds Vite time (12.21 seconds wall) at **706,308 KiB peak RSS** with zero
swaps. The existing Vite main/Chart chunk-size warning remains. TypeScript,
targeted ESLint and Prettier, Ruff, strict mypy for five changed production
modules, and `git diff --check` passed. At `2026-10-27T19:50:15Z`, PSI `avg10`
was 0.00% `some` / 0.00% `full`; available memory was 9.1 GiB and swap free
468 MiB. The repository-wide MIDAS suite remains unrun. No external source
probe, held-capture read, Reality action, or deployment occurred. Frontier stays
isolated, research-only, PARTIALLY VERIFIED, and undeployed.
