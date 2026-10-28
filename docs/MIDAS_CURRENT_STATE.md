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

## Frontier development addendum — 2026-10-28

### Recorded health join and timeline freshness control — 2026-10-28 00:18 CET

Frontier branch `codex/frontier-20261026` is at code commit
`8e79bf1f3bc583aa2329096729c6dd9c624c603d`, following
`ea073c4cdb4a00b70fc609e8806f80a40542cd4c`. The timeline API now resolves
recorded source-state events against the finite collector's append-only
checkpoint journal. It checks the full checkpoint chain and run-spec digest,
then requires the event venue, health timestamp, mapped state, reason, and
checkpoint digest to match. Held-source health is rejected. Timeline snapshot
schema 2 pins the validated checkpoint hashes while schema 1 inputs without
recorded health remain readable. Mission Control exposes a pinned book-age
control from 1 to 3,600,000 milliseconds.

The combined Frontier/Arena regression passed **350 tests**; the separate
collector/timeline-API/Arena timeline selection passed **21/21**. The Web suite
passed **40/40**, TypeScript, ESLint, Prettier, and production build passed, and
the isolated Playwright empty/offline scenario passed **1/1**. Legacy integration
and Arena admission regressions passed **63**, with one PostgreSQL test skipped
after unsetting `MIDAS_TEST_POSTGRES_URL`. Strict mypy passed the three changed
backend modules. The existing 544.41 kB Chart chunk advisory remains.

The host sample at `2026-10-27T23:15:35Z` showed 0% memory PSI avg10, 10 GiB
available memory, and 400 MiB free swap; it is a dated point-in-time sample.
No exchange request, collector, Arena worker, production service, or historical
store was accessed. Frontier remains isolated, research-only, undeployed, and
**PARTIALLY VERIFIED**. No live multi-venue relationship or economically
eligible opportunity was established. See the [mission ledger](frontier/FRONTIER_MISSION_LEDGER.md)
and [engineering report](frontier/FRONTIER_ENGINEERING_REPORT.md).

### Event-time Arena replay and finite collector checkpoint — 2026-10-27 22:58 UTC

The isolated Frontier branch contains collector commit
`b6b8a99337b5b08a54b5011eaf72d30949ab0b1b` and event-time Arena integration
commit `5e04c14b47c9b820946259a8ad1e232b4597190a`. The collector is a finite
one-source Python module with restartable append-only checkpoints; it is not an
API, Arena job, timer, or background service. Event-time replay is exposed as
an explicit, local-input-only Arena job with content-addressed snapshots,
hash-verified results, held-source filtering, a readiness gate, and a Frontier
Mission Control view.

Verification at this checkpoint: the Frontier/Arena Python regression command
passed **347 tests**; the web suite passed **40/40**; the isolated browser
scenario passed **1/1** and observed no collector probe or timeline submission
from opening Replay & Readiness. Scoped strict mypy passed four changed backend
modules, TypeScript, ESLint, Ruff and Prettier passed, and the Vite production
build passed. The build retains the existing 544.41 kB Chart chunk advisory.
The repository-wide mypy run still reports 35 errors in unrelated Veritas/Arena
modules. No exchange request or Arena worker was launched; no production
service or historical store was accessed. Recorded source-status events remain
unsupported until a validated evidence-store join exists, and timeline
readiness remains pending a completed bounded job with runtime evidence.

Frontier remains isolated, research-only, undeployed, and **PARTIALLY VERIFIED**.
No positive cross-venue economic result was established. See the
[mission ledger](frontier/FRONTIER_MISSION_LEDGER.md),
[architecture](frontier/FRONTIER_ARCHITECTURE.md),
[operations guide](frontier/FRONTIER_OPERATIONS.md), and
[engineering report](frontier/FRONTIER_ENGINEERING_REPORT.md).

### Coinbase Exchange Spot update — 2026-10-27 21:07 UTC

The isolated Frontier branch `codex/frontier-20261026` now contains Coinbase
Exchange spot adapter commit `cfda4ad1beb00f301affe52752e8815b4862f8b5`, with
validation checkpoint commit `4b20aa9db859842f355c37920505de893732c17a`. The
adapter supports configured public product metadata, aggregated level-2 books,
and one bounded trade page. Spot remains contextual evidence, not an event
contract payoff; account-tier fees, settlement rules, and live cross-venue
relationships are not established.

Source use is disabled by default. The local adapter and API require an exact
acknowledgement of Market Data Terms version `2026-08-07`, with a separate
public-probe setting. This does not validate the applicable organization,
region, retention, or redistribution scope. No Coinbase API request or capture
was made. The focused adapter, terms-gate, held-source, and spot-payoff tests
pass **10/10**; the full Frontier suite, web suite, production build, and
browser regression for this checkpoint remain pending a safe host admission
window. At the latest resource check the external bounded Veritas/Arena batch
held the shared Arena lock and PSI was high; it was left untouched. Frontier
development remains isolated, incomplete, and undeployed. See the [mission
ledger](frontier/FRONTIER_MISSION_LEDGER.md) and [engineering
report](frontier/FRONTIER_ENGINEERING_REPORT.md) for measured evidence and
continuation steps.

### Frontier regression update — 2026-10-27 21:12 UTC

The complete Frontier Python suite now passes **262/262**, the web unit suite
passes **40/40**, TypeScript typecheck passes, and targeted Frontier ESLint
passes. Ruff check/format, Prettier, and `git diff --check` pass. Peak RSS was
353,748 KiB for Frontier Python, 271,600 KiB for web tests, and 439,648 KiB for
typecheck; none of these jobs swapped. The production build and browser E2E
remain unverified for the Coinbase checkpoint. The shared Arena batch had
restarted and PSI was elevated at the latest admission check, so those heavier
jobs were deferred. No exchange request, service action, or historical-store
access occurred.

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

## Frontier virtual capital release-delay scenario — 2026-10-27 20:02 UTC

Code commit `29ab175` adds an optional post-settlement release delay for each
venue in the virtual capital-duration workbench. Delay is a whole-second
scenario input, bounded to one year, defaults to zero, and is included in the
input digest. The independent verifier recomputes release time, duration,
carry, and adjusted P&L from the pinned replay inputs. UTC normalization
handles daylight-saving transitions and timestamps that overflow fail closed.
The interface labels the delay as a scenario assumption, not actual redemption
or capital availability.

Verification passed: the capital-carry module **27/27** (including a post-format
rerun), saved-run API integration **1 passed**, full Frontier Python suite
**246/246**, full web suite **40/40**, and isolated Frontier browser suite
**4/4**. TypeScript, targeted ESLint/Prettier, Ruff check/format, strict mypy
for the capital model and Frontier API, and `git diff --check` passed. The
production build compiled 2,228 modules in 12.28 seconds wall at 700,060 KiB
peak RSS with zero swaps, using `/tmp/midas-frontier-web-build-20261027-2001`;
the repository `dist` was untouched. Existing large index/Chart chunk and
external-output-directory warnings remain. The Frontier Python suite has the
existing Starlette/httpx deprecation warning. At `2026-10-27T20:02:00Z`, memory
PSI avg10 was 0.00% (`some`/`full`), avg60 1.19% / 1.09%, avg300 14.11% /
12.77%; 9.5 GiB was available and 468 MiB swap free. The legacy repository
suite remains unrun. No live-source request, held-capture read, protected
service action, or deployment occurred. Frontier remains isolated,
undeployed, research-only, and PARTIALLY VERIFIED.

## Frontier Arena replay regression — 2026-10-27 20:04 UTC

The focused Arena integration suite `tests/arena/test_frontier_replay.py`
passed **10/10** in 1.94 seconds (2.63 seconds wall) at **193,936 KiB peak
RSS**, with zero swaps and the existing Starlette/httpx TestClient deprecation
warning. It uses temporary paths and covers replay snapshot/job contracts,
artifact integrity, bounded catalog/API reads, and held-source quarantine.
This supplements the full Frontier Python, web, browser, and build results at
20:02 UTC. No Arena production job, exchange request, preserved capture, or
Reality service was accessed. Frontier remains PARTIALLY VERIFIED; the
repository-wide legacy suite and deployment are not verified.

## Legacy API integration compatibility — 2026-10-27 20:05 UTC

The isolated `tests/integration/test_api.py` module passed **5/5** in 3.99
seconds (5.01 seconds wall) at **154,664 KiB peak RSS**, with zero swaps. Its
demo workflow forbids construction of the public client and uses temporary
databases/workspaces; the Arena qualification route is mocked. It verifies
existing demo API, health/readiness, Frontier empty/no-probe responses,
Veritas/Reality configured-workspace routes, and persistence failure gates.
The only warning is the existing Starlette/httpx TestClient deprecation. At
`2026-10-27T20:05:24Z`, admission PSI avg10 was 0.00% (`some`/`full`), avg60
8.15% / 7.33%, avg300 15.84% / 14.31%; 9.6 GiB was available and 468 MiB swap
free. This is a narrow compatibility slice; the repository-wide legacy suite
remains unrun. No public source, historical store, protected service state, or
production deployment was accessed.

## Legacy Polymarket and recording compatibility — 2026-10-27 20:06 UTC

`tests/integration/test_adapters.py` passed **9/9** in 0.71 seconds (1.21
seconds wall) at **88,872 KiB peak RSS**, with zero swaps. It uses checked-in
recorded market fixtures and `httpx.MockTransport`; no public request occurs.
`tests/integration/test_recording_isolation.py` passed **4/4** in 0.49 seconds
(0.93 seconds wall) at **77,800 KiB peak RSS**, with zero swaps. Its writes stay
under `tmp_path`; its production-default case only asserts path compatibility.
Together these preserve the existing Polymarket adapter contract and ensure a
temporary database maps to an isolated recording root. At
`2026-10-27T20:06:31Z`, memory PSI avg10 was 0.00% (`some`/`full`), avg60 2.62%
/ 2.36%, avg300 12.54% / 11.33%; 9.6 GiB was available and 468 MiB swap free.
No protected recorder, historical store, public source, or deployment was
accessed. The repository-wide suite remains unrun.

## Frontier Laboratory compatibility smoke — 2026-10-27 20:09 UTC

The existing Laboratory API contract/reproduction test passed **1 test** (two
other module tests deselected) in 2.50 seconds (3.15 seconds wall) at **124,540
KiB peak RSS**, with zero swaps. It creates and reproduces a four-run virtual
demo campaign under `tmp_path`. `MIDAS_MODE=demo` was explicit; Frontier and
Arena roots were redirected to fresh `/tmp` paths. No live source client,
production job, protected service, or historical store was used. The existing
Starlette/httpx TestClient deprecation remains. At `2026-10-27T20:09:29Z`, PSI
avg10 was 0.12% (`some`) / 0.11% (`full`), avg60 12.97% / 11.97%, avg300
15.92% / 14.55%; 9.6 GiB was available and swap free was 468 MiB. This is a
bounded Laboratory compatibility check, not a full Laboratory or repository
regression.

## Frontier per-venue execution-delay sensitivity — 2026-10-27 20:16 UTC

Code commit `9da08fd` adds optional venue-specific delay additions to the
bounded virtual replay scenario. The shared base delay plus each venue addition
is capped at one hour. Cross-venue binary and same-market multi-outcome pricing
apply quote decay using the relevant venue delay, and independent audit v8
recomputes it. Replay v11 and economic model v11 pin the scenario input. The
Workbench exposes per-source inputs for direct, paired, and Arena replay. Its
quantity control now says usable top-ask depth: it is a size haircut, not a
partial-fill simulation. Delay remains user-supplied and does not model actual
execution order, venue latency, or fills.

Focused Python tests passed **8/8**, with a separate API replay check **1/1**;
the focused Workbench test passed **1/1**. TypeScript, ESLint/Prettier, Ruff,
strict core Frontier mypy, and diff checks passed. Full Frontier tests and the
production build remain pending because at `2026-10-27T20:16:17Z` PSI avg10 was
44.92% (`some`) / 40.76% (`full`), 9.5 GiB was available, and 469 MiB swap was
free. API-inclusive strict mypy is also pending: the unrestricted run reached
pre-existing imported Veritas type errors and the filtered run was interrupted
under host pressure. No live source, protected service, held capture, or
production state was accessed. Frontier remains isolated, undeployed, and
PARTIALLY VERIFIED.

## Fee evidence at modeled execution time — 2026-10-27 20:22 UTC

Code commit `ad811a4` checks each leg's fee evidence at replay time plus the
scenario's shared and venue-specific delay. If a pinned schedule expires
before modeled use, the fee and net result remain unknown. The independent
audit recomputes the projected fee-applicability time. Economic model v12,
audit v9, and replay v12 pin this correction; it does not predict future fee
changes.

The fee-expiry and delay selection passed **6/6**, API replay passed **1/1**,
and the complete Frontier Python suite passed **252/252** with zero swaps.
Ruff and strict core Frontier mypy passed. At `2026-10-27T20:22:35Z` after the
full suite, PSI avg10 was 25.66% (`some`) / 22.83% (`full`); 9.5 GiB was
available and 469 MiB swap was free. The production frontend build remains
pending after the UI change; the focused UI test and TypeScript/lint/format
checks passed at the previous checkpoint. API-inclusive strict mypy remains
unverified. No live source, protected service, or historical capture was
accessed. Frontier remains research-only, isolated, undeployed, and PARTIALLY
VERIFIED.

## Frontier bounded partial-fill sensitivity — 2026-10-27 20:36 UTC

The isolated worktree now contains an uncommitted five-point partial-fill grid
for supported research candidates. It filters intermediate ratios by venue
quantity step, recomputes supported fees at each aggregate partial quantity,
and independently verifies the worst grid result. Replay is v13, the economic
model is v13, and the independent audit is v10. The Workbench displays the
sampled gross/net result and per-leg quantities. These are bounded sensitivities
only; no fill probability, continuous quantity range, multiple-fill rounding,
price path, hedge, or unwind is modeled.

Focused economics tests passed **6/6**, including exhaustive three-leg grid
enumeration, fee rounding, quantity-step filtering, and unknown-fee behavior;
the audit-tampering test passed **1/1**. Workbench component tests passed **8/8**;
TypeScript, targeted ESLint/Prettier, Ruff, and strict mypy on the four core
Frontier modules passed. A first full run had 252 passing tests and one failing
quantity-mutation diagnostic; the audit was corrected and its focused test now
passes. The complete post-fix regression and full frontend build/browser suite
remain pending. At `2026-10-27T20:36:01Z`, memory PSI avg10 was 50.50% (`some`)
and 46.53% (`full`), with 9.9 GiB available and 469 MiB swap free. No build or
full-suite run was started at that pressure sample. The code and updated
architecture/report matrix are uncommitted in `codex/frontier-20261026`.
Production services, source data, protected recordings, and deployment remain
untouched. Frontier remains **PARTIALLY VERIFIED**.

## Frontier v13 post-fix regression — 2026-10-27 20:37 UTC

The full Frontier Python suite passed **254/254** in 39.82 seconds pytest time
/ 40.92 seconds wall at **335,988 KiB peak RSS**; the only warning was the
existing Starlette/httpx TestClient deprecation. This covers the new bounded
partial-fill grid, a nonlinearly rounded Kalshi fee fixture, quantity-step
filtering, unknown-fee handling, independent audit tampering, and API replay
version 13. The API model exposes the exact feasible fill fractions per leg,
and the Workbench can expand those per-leg grids. The grid still has no fill
probabilities, continuous intermediate points, multiple-fill rounding, quote
paths, or hedge/unwind model.

The eight-case Workbench component suite, TypeScript, targeted ESLint/Prettier,
Ruff, strict mypy on four core Frontier modules, and `git diff --check` passed.
At `2026-10-27T20:37:47Z`, PSI avg10 was 34.40% (`some`) / 30.73% (`full`),
avg60 22.93% / 20.56%, avg300 27.50% / 24.76%; 9.9 GiB was available and swap
free was 481,040 KiB. The full web suite, production frontend build, and
post-change browser E2E remain pending after the next host admission check.
No live source, protected service, recording, or deployment was used. Code and
docs remain uncommitted in the isolated Frontier worktree; overall status is
**PARTIALLY VERIFIED**.

## Frontier v13 code commit — 2026-10-27 20:38 UTC

The implementation is committed on `codex/frontier-20261026` as **`e50ba34`**
(`Add independently audited partial-fill grid sensitivity`). It includes the
economic model, independent audit, replay/model version bumps, Python/API tests,
Workbench rendering and tests, and Frontier architecture/report updates. The
latest full Frontier regression remains **254/254**. The focused component
suite and static checks pass. The ledger, engineering report, and this
current-state file have documentation-only changes after that commit. Full
web tests, production build, and browser E2E
remain pending because PSI was 38.72% full at avg10 at `20:38:38Z`, despite
9.9 GiB available. No live source, protected service, or production deployment
was used; Frontier remains **PARTIALLY VERIFIED**.

## Frontier frontend and browser verification — 2026-10-27 20:43 UTC

The complete Web unit suite passed **40/40**. The production build passed
`tsc -b` and Vite in 12.50 seconds wall at **692,056 KiB peak RSS**. Frontier's
bundle is 102.13 kB JS / 35.87 kB CSS; Vite keeps an advisory warning for the
existing 544.41 kB Chart chunk. Dedicated Frontier browser E2E passed **4/4**.

The full 12-test browser suite passed **10** and failed **2** Laboratory launch
cases: the API correctly denied both with `resource_admission_lock_busy` before
launching workers. At `2026-10-27T20:43:15Z`, the active global-lock holder was
PID 3681242, `scripts/veritas_gap_detail_v2_batch.py`, using the primary and
Veritas Arena roots. The lock path is the primary `/home/charlie/midas/data/arena/.global-admission.lock`;
temporary browser roots do not override it. That pre-existing worker and lock
were left untouched. The other ten browser cases passed, including all Frontier
cases. Do not bypass/retry until the shared slot releases.

Full Frontier Python regression remains **254/254**, full Web units **40/40**,
Workbench tests **8/8**, TypeScript, targeted lint/format, Ruff, core strict
mypy, build, and Frontier E2E are verified. Full package E2E is partially
verified due only to the two admission-denied Laboratory tests. At the same
timestamp, PSI avg10 was 45.75% (`some`) / 41.58% (`full`), avg60 43.43% /
38.30%, avg300 37.69% / 33.23%; 9.9 GiB was available and 481,192 KiB swap
free. No external exchange source or production service was touched. Frontier
remains isolated, undeployed, and **PARTIALLY VERIFIED**.

## Frontier source terms recheck — 2026-10-27 20:45 UTC

An official-documents-only review reconfirmed the Kalshi data-use restrictions
and current Kraken regional content terms. Kraken's API Center documents public
Spot market-data endpoints, but the reviewed terms do not resolve this
research/retention use or the applicable regional agreement. Polymarket
Institute's current research guide distinguishes its global and US-only data
systems. The source gates did not change: Kalshi/Kraken live probes and stored
research remain blocked or quarantined. No API request, exchange contact, held
capture read, production action, or permission inference was made. See
[`SOURCE_DATA_TERMS_REVIEW_2026-10-27.md`](frontier/SOURCE_DATA_TERMS_REVIEW_2026-10-27.md).

## Frontier Arena admission recheck — 2026-10-27 20:47 UTC

The host-wide Arena lock was reacquired by a new
`veritas_gap_detail_v2_batch.py` worker, PID 3690476, on lock inode 6423106.
PSI avg10 was 38.74% `some` / 33.82% `full`; the protected Reality recorder
was present and left untouched. No rerun of the two Laboratory browser cases
was started and no lock was bypassed. Full browser evidence remains 10/12 with
those two cases admission-denied; Frontier's dedicated browser suite remains
4/4. Wait for shared admission and lower host pressure before retry.

## Frontier observation persistence checkpoint (`51afe86`) — 2026-10-27 21:23 UTC

The isolated writer now records missing `Provenance.persisted_at_utc` values
on new Frontier observations, without mutating adapter models. It preserves an
existing stamp when copying saved evidence into a content-addressed snapshot;
legacy rows without the optional field remain readable. Focused storage,
Coinbase, and snapshot-copy tests pass **25/25**. The full Frontier Python suite
passes **265/265** at **352,164 KiB peak RSS**, zero swaps. The test process
overlapped with a newly started external Arena batch after the admission
precheck; that worker and its lock were left untouched. Production build and
browser E2E for the Coinbase/storage checkpoint remain pending a safe host
window. Frontier remains research-only, isolated, undeployed, and
**PARTIALLY VERIFIED**.

## Frontier monotonic request provenance checkpoint (`6bc0351`) — 2026-10-27 21:28 UTC

Frontier records read-only HTTP request/body elapsed duration from a local
monotonic clock, carries it into raw observations and normalized provenance,
and shows it in the source-evidence disclosure. The focused Python selection
passes **86/86** and the targeted UI test passes **1/1**. The full Frontier
suite result **265/265** is from predecessor `51afe86`; it has not been rerun
for this change. Web suite, typecheck, build, and browser E2E are also pending
for the new UI field. At the latest resource sample, external bounded Arena
batch PID **3727342** held the shared lock and PSI was elevated. The worker was
left untouched; no source or production service was accessed.

## Frontier full verification checkpoint (`008106b`) — 2026-10-27 21:36 UTC

The latest code adds monotonic per-request timing provenance and a defensive
Coinbase Decimal exponent guard. The complete Frontier Python suite passes
**269/269**, Web unit suite **40/40**, TypeScript, targeted ESLint/Prettier,
Ruff, and strict direct mypy for the changed Python modules. The production
frontend build passes into `/tmp` and the full browser suite passes **12/12**,
including both bounded Laboratory cases. Peak RSS was 352,484 KiB for Frontier
Python, 346,668 KiB for web tests, 441,532 KiB for TypeScript, 701,536 KiB for
the build, and 209,416 KiB for browser E2E; all reported zero swaps. No
exchange API was called. Frontier remains research-only, isolated, undeployed, and
**PARTIALLY VERIFIED** because source permissions, genuine cross-venue payoff
validation, and production readiness remain unresolved.

## Frontier legacy compatibility selection deferred — 2026-10-27 21:39 UTC

The additional compatibility run across existing adapter, API,
recording-isolation, and Frontier Arena replay tests was deferred. At
2026-10-27T21:39:36Z, external batch PID 3745206 held the shared Arena
admission lock in D state; memory PSI avg10 was 44.57% some / 39.03% full.
No tests were started, and the worker was left untouched. Recheck lock and
host pressure before resuming. This does not invalidate the already completed
Frontier, Web, typecheck, build, or browser results.

## Frontier additional venue screen — 2026-10-27 21:42 UTC

Official Manifold and Betfair documentation was evaluated for a useful
additional source. Manifold's current core market currency is non-redeemable
mana and its sweepstakes markets ended in 2025, so it was not added as an
economic venue. Betfair requires an account application key; delayed data is
1–180 seconds, live read-only access is not permitted, and commercial use
requires approval. Neither API was queried and no credentials were requested.
The sourced decision is in
`docs/frontier/ADDITIONAL_VENUE_SCREEN_2026-10-27.md`.

At 2026-10-27T21:42:51Z, the deferred legacy tests remained unstarted because
PID 3745206 held the shared Arena lock in D state and PSI avg10 remained
39.31% some / 34.14% full. Recheck admission before running them.

## Frontier legacy compatibility tests complete — 2026-10-27 21:45 UTC

After the external batch exited and memory PSI settled, the selected legacy
adapter/API/recording-isolation and Frontier Arena replay modules passed
**28/28**. The run explicitly used `PYTHONPATH=packages:.`; the resolved
`midas` import was the Frontier worktree at
`/home/charlie/midas-frontier/packages/midas/__init__.py`. It took 7.32
seconds wall, peak RSS 282,584 KiB, zero swaps; only the existing
Starlette/httpx TestClient deprecation warning remains. Immediately after the
run, the shared lock was free and PSI avg10 was 0.01% some / 0.00% full.
This closes that bounded compatibility check. The separate repository-wide
Python run remains partial due the previously recorded collection/runtime
issues.

## Frontier integration and admission regression checkpoint — 2026-10-27 21:46 UTC

The complete `tests/integration` directory passed **55 tests**, with the
PostgreSQL runtime test skipped because its URL was explicitly unset. The
local package and test paths were supplied via `PYTHONPATH=packages:.:tests`.
The run took 29.82 seconds wall, peak RSS 210,816 KiB, zero swaps. The
Starlette/httpx TestClient deprecation is the only warning. Arena admission
regressions then passed **8/8** in 2.04 seconds wall, peak RSS 178,692 KiB,
zero swaps. The post-run lock was free and PSI avg10 was 0.00% some / 0.00%
full. These are bounded legacy integration/admission results, not a clean
repository-wide suite; unrelated collection/runtime gaps remain documented.

## Frontier resource gate — 2026-10-27 21:48 UTC

At `2026-10-27T21:48:09Z`, external Veritas batch PID **3762324** was still
blocked in `D` state at `mem_cgroup_handle_over_high`; memory PSI avg10 was
47.93% `some` / 41.46% `full`. It was left untouched. No Frontier tests or
builds were started after it appeared. Wait for pressure to settle and verify
the shared Arena admission lock before further resource-consuming checks.

## Frontier resource gate cleared — 2026-10-27 21:49 UTC

At `2026-10-27T21:49:51Z`, external Veritas batch PID 3762324 had exited and
no shared Arena lock holder was listed. Memory PSI avg10 was 0.00% `some` /
`full`; available memory was 9.9 GiB and 455 MiB swap was free. The browser
suite already passed 12/12 at the latest unchanged UI checkpoint, and later
legacy integration/admission checks passed. Recheck resource admission before
any future worker launch.

## Frontier coverage analytics checkpoint — 2026-10-27 22:13 UTC

Isolated branch `codex/frontier-20261026` adds source-aware recorded coverage
and quality analytics in code commit `4c9a8d8`. Follow-up `66e89a5` pins
market-observation IDs and canonical quote denominations in the repeated
construction signature. The no-network API endpoint
uses bounded market/book/replay samples, filters held venues, verifies joins
and observation lineage, and exposes freshness, denomination-aware spread and
depth, timing, and candidate classification summaries. A new native Frontier
Coverage & quality tab loads the view on demand. The endpoint does not query an
exchange or start a collector.

Current bounded results: Frontier Python **279/279**, Web unit suite **40/40**,
dedicated Coverage-tab browser E2E **1/1**, strict mypy, Ruff, ESLint, Prettier,
TypeScript, and Vite production build all pass. Peak RSS was 354,788 KiB for
Frontier Python, 333,216 KiB for Web tests, 186,788 KiB for the browser case,
and 667,976 KiB for Vite; each job reported zero swaps. No protected service,
exchange endpoint, held capture, or production store was accessed.

Frontier is still **PARTIALLY VERIFIED**, not deployed, and research-only.
Coverage results describe bounded stored evidence and do not establish
venue-wide measurement, synchronized executable quotes, positive net economics,
or live multi-venue validation. See the [mission ledger](frontier/FRONTIER_MISSION_LEDGER.md)
and [engineering report](frontier/FRONTIER_ENGINEERING_REPORT.md) for the full
checkpoint, remaining acceptance gaps, and continuation work.

## Frontier event-time replay checkpoint — 2026-10-27 22:24 UTC

Code commit `30576f1` adds an offline engine in
`packages/midas/frontier/timeline.py` that replays
repeated books at bounded UTC cutoffs, records stale/missing/source-interrupted
legs, prevents use of pre-interruption quotes until a new snapshot is observed,
and excludes relationship verifications that postdate a frame. Four fixture
tests cover deterioration, expiry boundaries, source interruption/recovery,
input-order reproducibility, and future-verification lookahead. The full
`tests/frontier` suite passes **283/283** in 70.69 seconds wall at **355,720 KiB
peak RSS**, zero swaps; strict mypy, Ruff, and `git diff --check` pass. The
focused timeline suite passes **4/4** in 0.69 seconds at **54,864 KiB peak RSS**.
This is engine-level verification only: the timeline is not yet exposed in the
API, persisted through Arena, or surfaced in Mission Control. Frontier remains
research-only, isolated, undeployed, and **PARTIALLY VERIFIED**.

## Frontier recorded-health catalog — 2026-10-27 23:31 UTC

Commits `31f62db`, `1779e89`, `9a3eced`, and `8f9b9b8` add a local read-only
catalog of verified collector health checkpoints, explicit replay selection,
artifact digest display, and rejection of ambiguous same-time source events.
The catalog is bounded to 20 events, filters held sources, validates each
selected journal chain, and does not create a missing journal or contact a
venue. Timestamp-less `not_probed` does not become a replay event. The UI
leaves all events unchecked and disables a second selected event for the same
venue/check time. It identifies the adapter-local health scope.

The combined Frontier/Arena regression passes **354/354** in 83.42 seconds at
**363,776 KiB peak RSS**, zero swaps. Frontier UI component tests pass **8/8**;
the isolated Replay & Readiness Playwright check passes **1/1** and verifies
the empty catalog with no source probe or job submission. TypeScript, strict
scoped mypy, Ruff, ESLint, and Prettier pass. The Vite production build passes
in 5.10 seconds at **647,020 KiB** peak RSS, zero swaps; the existing 544.41 kB
Chart chunk warning remains. No public source observation or cross-venue
economic result was established. Frontier remains isolated, research-only,
undeployed, and **PARTIALLY VERIFIED**. See the [mission ledger](frontier/FRONTIER_MISSION_LEDGER.md)
and [engineering report](frontier/FRONTIER_ENGINEERING_REPORT.md) for the
remaining offline gaps and source/deployment boundaries.

## Frontier finite source-capture API — 2026-10-27 23:38 UTC

Code commit `cf67b2b` exposes `BoundedSourceCollector` as an explicit
`POST /api/frontier/collect/{venue}` operation and an Exchanges-view button.
It shares the source lock with existing probes, rechecks the configured public
probe flag, source-use hold, capabilities, and source request limits, and caps
one run at five markets, two books, depth ten, 4 MiB of evidence, and 60
seconds. Mission Control sends a smaller 3-market/1-book/depth-5, 30-second
request. The call uses the API request lifecycle and starts no Arena job,
worker, timer, or background service. The endpoint supports starting a run;
the module's resume capability does not yet have an HTTP route or UI.

The two finite-collection API tests pass **2/2** in 1.10 seconds with fixture
adapters. `Frontier.test.tsx` passes **8/8** in 4.19 seconds, including the
explicit request body, saved run summary, and adapter-local health caveat.
TypeScript, strict scoped mypy, Ruff, Prettier, and `git diff --check` pass.
The combined Frontier/Arena regression produced **354 passed and two host
admission failures** in 81.75 seconds, at **366,436 KiB peak RSS** and zero
swaps. The two failures are existing Arena job-supervisor tests that could not
acquire the shared admission lock; process **3913373**, the existing Veritas
gap-detail batch, held that lock. It remains untouched. The production build
and browser suite were deferred after memory PSI rose to 35.60% `some` / 29.55%
`full`; 9.9 GiB was available and 3.7 GiB of swap was in use.

No real adapter, external API, collector against a live source, Arena worker,
Reality action, production service, or historical store was accessed. Source
configuration remains disabled by default and existing source-use holds remain
in force. The endpoint/UI integration is fixture-verified; live collection and
the populated browser flow remain pending. Frontier is isolated,
research-only, **PARTIALLY VERIFIED**, and undeployed.

## Frontier collection recovery — 2026-10-27 23:53 UTC

Commit `305814b` adds a bounded read-only history endpoint and explicit
resume action for finite source-collection checkpoints. API and collector
revalidate source-use policy, enabled/public-probe configuration, adapter and
capability manifests, current source limits, and request bounds before
resuming. The Exchanges workspace exposes recent verified checkpoints and a
resume button only for eligible nonterminal runs; no automatic retries or
background collection were added.

The focused collection tests pass **20/20**, Frontier UI tests **8/8**, and an
isolated browser smoke **1/1**. TypeScript, scoped strict mypy, Ruff,
ESLint/Prettier, and the Vite production build pass. All `tests/frontier`
cases passed in a broader selected regression (**358 passed, 2 failed**); the
two failures are Arena supervisor tests denied by a new external Veritas
batch holding the shared resource lock. At the 23:53 UTC sample that batch
(PID 3939942, `D` state) remained the lock holder; PSI avg10 was 49.25% `some`
and 42.91% `full`, with 9.7 GiB available and 3.7 GiB swap in use. No retry
was attempted.

No source API, held capture, Reality service, Arena worker, or production
deployment was accessed. Current Frontier status remains isolated,
research-only, undeployed, and **PARTIALLY VERIFIED**. See the [mission
ledger](frontier/FRONTIER_MISSION_LEDGER.md) for exact measurements and
continuation guidance.

### Arena admission-test follow-up — 2026-10-27 23:55 UTC

After the external Veritas holder exited, the two admission-denied Arena
supervisor tests passed **2/2** in 4.34 seconds wall at **179,752 KiB peak RSS**
and zero swaps. Their process launch is fixture-replaced, so no Arena worker
started. Alongside the earlier combined run, all **360 selected Frontier/Arena
cases** pass across two invocations; the combined run itself still records two
environmental denials. The retry began with the global lock free, PSI avg10 at
0%, and 10 GiB available. The isolated Frontier build and browser check also
pass for commit `305814b`; no production deployment or source request occurred.

### Full web regression — 2026-10-27 23:56 UTC

The full web unit suite passes **40/40 across seven files** in 15.55 seconds
reported / 15.97 seconds wall at **300,960 KiB peak RSS**, zero swaps. This
includes the Frontier component suite and the other Mission Control views.

### Full Frontier browser regression — 2026-10-27 23:57 UTC

The Frontier Playwright spec passes **4/4** in 11.5 seconds reported / 12.05
seconds wall at **192,280 KiB peak RSS**, zero swaps. It verifies Exchanges
history loads without collection/source POSTs, replay history submits no job,
fixture-only settlement review, and responsive bounded graph exploration.
The run used temporary API/data roots and did not call an exchange endpoint.

### Frontier collection acceptance follow-up — 2026-10-28 00:00 UTC

Commit `a7996f9` adds held-source history filtering and corrupted checkpoint
chain regressions. The focused collection module/API tests pass **21/21** in
6.53 seconds wall at **87,676 KiB peak RSS**, zero swaps; Ruff and
`git diff --check` pass. Verification used fake adapters and temporary storage
and made no source request. At 00:00:12 UTC, the shared admission lock was
free, PSI avg10 was 0.64% `some` / 0.58% `full`, and 10 GiB was available.
Frontier remains research-only, undeployed, and **PARTIALLY VERIFIED**. See the
[mission ledger](frontier/FRONTIER_MISSION_LEDGER.md) for the current evidence
and continuation notes.

### Frontier missing-adapter API guard — 2026-10-28 00:02 UTC

Commit `169bfa2` gives finite collection start and resume a clear HTTP 409 when
a venue adapter is unavailable, before the collection journal is touched. The
collection API tests pass **6/6** in 2.52 seconds wall at **84,136 KiB peak
RSS**, zero swaps; Ruff and `git diff --check` pass. No source request or Arena
worker ran. At 00:02:40 UTC the shared Arena lock was held by PID 3950719 and
memory PSI avg10 was 41.99% some / 37.85% full, so Arena-dependent verification
is deferred pending a fresh admission check. Frontier remains research-only,
undeployed, and **PARTIALLY VERIFIED**; see the [mission ledger](frontier/FRONTIER_MISSION_LEDGER.md).
