# Project Midas — Directive 001 delivery report

Date: 2026-10-11. Delivery: a functioning read-only research foundation and offline simulation command center. This report describes implemented and exercised behavior; the documented limitations are not presented as completed capabilities.

## Completed systems

- Installable Python monorepo package, FastAPI backend, React/TypeScript application, locked dependencies, environment configuration, local SQLite and PostgreSQL Compose/Alembic definitions.
- Real public Gamma discovery and strict protocol-selected instrument normalization, public CLOB snapshots, heartbeat-managed market streaming, deduplication, bounded buffering, reconnect/backoff, invalidation and periodic REST resynchronization.
- Validated normalized contracts and append-only JSONL records retaining raw parsed inputs, exact wire JSON, source/exchange clocks and interpretation versions. Indexed SQL persistence for markets, observations, incidents and complete experiment artifacts.
- Exact binary depth evaluation with tick/minimum/capital/quantity rules, supported market-specific fee schedules, conservative rounding, outcome payouts, reasons and provenance. A separate risk component gates virtual positions.
- Deterministic event scheduler, virtual venue, independent order legs, reservations, consuming/partial fills, IOC/GTC behavior, rejection, acknowledgment/cancellation delays, stop and settlement, portfolio marks and drawdown, journal and independent accounting reconstruction.
- 43 executable scenarios, randomized property invariants, checkpoint restoration, receipt-ordered historical observation replay and synthetic replay samples.
- Connected dark command center, scanner sorting/filtering/details, executable simulation controls and replay cursor, persisted results, recorded analytics, incidents, telemetry, settings and an honest strategy/Arena foundation.

## Architecture

The backend is a modular monolith. Financial modules do not depend on HTTP, storage or frontend formats. A strategy receives domain market/book contracts and returns an evaluation; risk separately admits or rejects the complete virtual proposal. The exchange computes actual virtual fills independently and an auditor reconstructs the ledger.

Two-mode operation prevents real/demo book mixing. Scenario portfolios always use synthetic inputs and independent starting capital. There is no cumulative return calculation across unrelated experiment portfolios. Timestamp/freshness gates are evaluated again when observations are read.

The official unified SDKs were researched; a small public GET allowlist avoids bringing secure trading capabilities into this repository. PostgreSQL is the container default, with SQLite for offline workstation operation. Custom accessible components/CSS provide the terminal design without a second styling framework. [Decisions](DECISIONS.md) explain the deviations.

## Verification executed

Commands below were executed locally, using `.venv/bin/uv` or the equivalent installed executable:

| Command / workflow | Result |
| --- | --- |
| `.venv/bin/uv sync --frozen` | Passed; installs locked backend environment |
| `corepack pnpm install --frozen-lockfile` (initial locked installation and subsequent normal update for formatting tooling) | Dependency installation passed; current lock retained |
| `.venv/bin/pytest -q` | **103 passed**; latest measured full run approximately 2.2–2.4 s |
| `.venv/bin/ruff check packages apps/api tests infra scripts` | Passed |
| `.venv/bin/ruff format --check packages apps/api tests infra scripts` | Passed; 35 Python files formatted |
| `.venv/bin/mypy packages/midas apps/api` | Passed; strict checking of 22 source files |
| `corepack pnpm format:check`, `lint`, `typecheck` | Passed |
| `corepack pnpm test` | **2 frontend tests passed** |
| `corepack pnpm build` | Passed; substantial lazy chart chunk warning remains |
| `corepack pnpm --dir apps/web exec playwright install chromium` | Browser installed successfully |
| `corepack pnpm test:e2e` | **1 integrated browser test passed**, covering scanner evidence, positive/rejected/loss scenarios, replay, all eight pages, stop enforcement and mobile rendering |
| `.venv/bin/uv build` and wheel inspection | Source distribution and wheel built; API/domain packages present, frontend/node_modules excluded from wheel |
| `.venv/bin/python scripts/replay.py` | Passed; first incomplete snapshots rejected, later positive and negative synthetic observations evaluated deterministically |
| `.venv/bin/python scripts/benchmark.py` | Passed; measured CPU baseline recorded below |
| `docker compose config -q` | Passed |
| Alembic upgrade against fresh temporary SQLite, then `scripts/storage_smoke.py` | Migration and insert/read passed |
| `docker info` | Blocked by local `/var/run/docker.sock` permissions; container/PostgreSQL execution **not tested locally** |
| `.venv/bin/python scripts/live_smoke.py` | Real public Gamma, CLOB, Data API v2 and websocket book/PONG verified |
| Integrated live `Service.start`/refresh/stream/shutdown with temporary SQLite | Passed; three real markets, six instruments/books, connected stream, recorded wire JSON, no verified opportunity |

Tests include independent accounting corruption detection, overspending rejection, duplicate-fill immunity, real SQL write failure, API restart persistence, profitable execution, partial/unhedged inventory, stale/invalid data, tick/fee/precision cases and Hypothesis-generated prices/sizes/fees/delays/stops/duplicates/settlement outcomes. Demo API tests explicitly forbid constructing a public network client.

Early verification found packaging/import configuration and an omitted SQLAlchemy asyncio extra; both were fixed. Fixed-quantity math tests initially requested optimizer defaults and browser tests used ambiguous selectors; explicit quantities and scoped/accessibly labeled controls corrected those issues. No failing test was removed or weakened to hide an implementation failure.

Remaining non-failing warnings: installed Starlette's TestClient warns that its httpx integration is deprecated in favor of httpx2; pnpm reports upstream deprecations and skipped esbuild lifecycle scripts (the actual build passes); Playwright's environment has competing NO_COLOR/FORCE_COLOR flags; Vite warns about a >500 kB lazy graphing chunk. The automated CI definitions have been created but not run on GitHub.

### Measured results

[Benchmark artifact](BENCHMARK_RESULT.json): 1,000 complete-binary evaluations with two one-level synthetic books on Python 3.12.3 / Linux x86_64 had approximately **0.206 ms median**, **0.220 ms p95**. The 43-scenario CPU suite took approximately **0.044 s**, with no failed invariants. These numbers exclude HTTP, storage, websocket load and frontend work; they are not sustained production throughput claims.

Frontend production build: approximately **351 kB main JS / 106 kB gzip**, **544 kB lazy chart JS / 187 kB gzip**, **20.5 kB CSS / 5.3 kB gzip**. Charts load separately; further chart bundle reduction is deferred. The integrated live scan/persist timing is recorded in [service output](LIVE_SERVICE_RESULT.json), for a three-market sample only.

## Polymarket integration

[Research](POLYMARKET_RESEARCH.md) links the current official sources and records the v1/v2 identifier distinction, fee schedule, precision, stream heartbeat, sequence uncertainty, negative/augmented risk exclusions, Data API v2 migration and rate limits.

Actual public checks retrieved v1 market metadata and both identifier fields, used the correct CTF asset for a CLOB book, read `/v2/status` and received a websocket book plus text PONG. [Public smoke output](LIVE_SMOKE_RESULT.json) and [integrated service output](LIVE_SERVICE_RESULT.json) preserve the evidence.

Live V2 markets were not encountered; ID routing and synthetic V2 payout contracts are fixture-tested. Sustained delta/reconnect fault campaigns are not claimed. All three liquidity-sorted markets in the integrated sample were neg-risk and correctly excluded; the service visibly reported degraded freshness rather than pretending old source timestamps were current.

Market-specific onchain payout attestation is **not implemented**. General official complete-set economics are researched, but Gamma alone is not accepted as proof for a particular live instrument pair. Eligible live binary markets remain unverified. This is the main limitation before economically meaningful live scanner classification, and no actual real-market profit is claimed.

## Simulation

The scenario library executes the real strategy/risk functions and venue/accounting checks. Complete synthetic positions can fill and profit; the system does not succeed by rejecting everything. Repeated identical scenario/seed/version/configuration results have byte-equivalent canonical content and identical hashes.

Execution uses explicit price-priority IOC/GTC assumptions, 0.01-share synthetic match precision, conservative collateral reservation, independently calculated fees and non-atomic legs. The timeline preserves portfolio state after each event. Checkpoint cases serialize and restore the exchange inside the process. Infrastructure cases inject deterministic untrusted states/fault events; they are not a full process/container/network chaos reproduction.

Queue position, empirical fill probability, passive matching, sell orders, competing participants, endogenous impact, financing, real oracle/redemption timing and persistent scheduler recovery remain unresolved realism limits. Historical replay currently produces opportunity observations, not historical fill claims.

## Dashboard

- **Mission Control:** actual application health, provenance, monitored counts, current classifications, theoretical gross/net amounts, observation counts, actual events and latest independent virtual P&L.
- **Scanner:** searchable/sortable classifications, actual normalized book levels, selected slices, conditions/instrument IDs, fees/rounding assumptions, modeled payouts and independent risk reasons.
- **Simulation Lab:** 43-scenario catalog, validated seed, backend execution, pass/fail, historical portfolios, event cursor, artifact download, ledger details and persisted history.
- **Analytics:** bounded recorded observation activity/distribution and separately labeled per-experiment realized virtual P&L.
- **Arena:** implemented deterministic baseline manifest and explicit future model-training empty state.
- **Incidents:** persisted actual messages with inspectable data/timestamps.
- **Telemetry:** measured process/scan timing, connection, queue, reconnect, integrity and storage health.
- **Settings:** current configuration/risk constraints and working emergency stop. A stop banner is visible globally.

The interface was exercised in Chromium at desktop and mobile widths. [Desktop](mission-control.png), [mobile](mission-control-mobile.png) and [scenario screenshot](dashboard-smoke.png) are actual application captures, not design mockups.

## End-to-end demonstration

| Synthetic case | Calculation / execution | Verified behavior |
| --- | --- | --- |
| `profitable`, seed 7 | 10 sets cost 9.50, payout 10, modeled net +0.50 virtual USD | Scanner evidence inspected; both virtual legs fill; ledger-derived realized +0.50; identical repeat hash |
| `unprofitable`, seed 7 | Combined asks 1.03/share; nonpositive net edge | Strategy rejects, independent risk rejects, no fills or simulated loss manufactured |
| `first_leg_only`, seed 7 | Complete-position model positive, second virtual order rejected | First leg remains unmatched; supplied NO settlement produces −4.20 virtual USD; journal reconciles and invariants pass |
| `partial_fills`, seed 7 | Liquidity shrinks before independent arrivals | Timeline reports three matched sets and one unmatched share before settlement |

The browser smoke performed the first three cases, inspected the supporting observation and moved the replay cursor. Python tests separately verify the partial-fill state.

## Safety

No live submission, cancellation, wallet authentication, private-key handling, deposits, withdrawals or funded position management exists. No trading credentials are required. REST transport rejects paths outside a public GET allowlist. The only websocket outbound operations are public market subscriptions and heartbeats. POST scenario runs and PATCH settings operate solely on internal virtual research state.

## Known limitations and next directive

[Known limitations](KNOWN_LIMITATIONS.md) lists the scope explicitly. Highest priorities are verified live payout/cost attestations; a persistent multi-market paper broker that enforces risk from actual portfolio state; unified migration/recovery management; recorded replay into an honestly modeled virtual venue; longer real-stream validation and PostgreSQL/container execution in an available environment.

Recommended Directive 002: **Audited live observations and persistent paper execution**, before advanced neg-risk strategies or neural training. [Roadmap](ROADMAP.md) sets the order and keeps live execution outside the current boundary.
