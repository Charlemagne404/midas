# Development and verification

MIDAS is a Python modular monolith with a separately built React dashboard.
Python dependencies are pinned by `uv.lock`; frontend dependencies are pinned by
`pnpm-lock.yaml`. Use Python 3.12 or newer, Node 22 or newer, Corepack, and uv.

## Install

From the repository root:

```bash
uv sync --frozen
corepack pnpm install --frozen-lockfile
```

If uv is not installed, the root README shows how to bootstrap it in the local
`.venv`. Copy `.env.example` to `.env` only when local overrides are needed. The
template uses demo mode and workspace-relative storage paths; it contains no
credentials.

## Run the application

Start the API and dashboard in separate terminals from the repository root:

```bash
.venv/bin/uv run uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
corepack pnpm dev
```

The dashboard is at `http://127.0.0.1:5173`; the API health endpoint is
`http://127.0.0.1:8000/api/health`. The default mode is demo and uses a local
SQLite database. `docker compose up --build` is an optional PostgreSQL-backed
setup; see the root README for its local port and migration command.

## Verify changes

Run the checks from the repository root. These commands use the lockfiles and
match the continuous-integration workflow:

```bash
.venv/bin/uv run --frozen pytest -q
.venv/bin/uv run --frozen ruff check packages apps/api tests infra scripts
.venv/bin/uv run --frozen ruff format --check packages apps/api tests infra scripts
.venv/bin/uv run --frozen mypy packages/midas apps/api
corepack pnpm lint
corepack pnpm typecheck
corepack pnpm test
corepack pnpm build
```

For browser tests, install Chromium once and then run the isolated Playwright
suite:

```bash
corepack pnpm --dir apps/web exec playwright install chromium
corepack pnpm test:e2e
```

Playwright starts its own API and web servers on ports 18000 and 15173 and uses a
temporary database and Arena root. Per-test screenshots stay in the ignored
`apps/web/test-results` directory. The suite does not reuse the application's
default database or overwrite curated documentation images. If those ports are
occupied, stop only the conflicting test process or run the suite in an isolated
environment.

Use the verifier documented beside a research artifact when checking historical
evidence. Verification commands should read saved artifacts. Commands named
`run_*`, campaign commands, and API actions that admit jobs can create durable
research output; use a separate local data root for intentional experiments.

## Package boundaries

- `packages/midas/core` defines validated domain contracts. Market-data adapters,
  arbitrage, risk, paper accounting, simulation, Laboratory, and Arena logic live
  in their respective `packages/midas` modules.
- Domain and simulation code is independent of FastAPI, SQLAlchemy, and the web
  application. `apps/api` owns configuration, persistence, lifecycle, and HTTP
  orchestration.
- `apps/web` is the React command center and calls the API through its configured
  `/api` proxy.
- Alembic migrations are under `infra/migrations`; Python and frontend checks
  are configured in `pyproject.toml` and `apps/web`.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the data flow and storage details.

## Project Frontier (isolated branch)

Frontier's public adapters are disabled by default and do not probe on API
startup. Its local store is selected with `MIDAS_FRONTIER_ROOT` (default
`data/frontier-store`), with an independent byte cap set by
`MIDAS_FRONTIER_STORE_MAX_BYTES`. If a public sample is explicitly needed, enable
only the intended venue with one of:

```text
MIDAS_FRONTIER_POLYMARKET_PUBLIC_PROBE_ENABLED=true
MIDAS_FRONTIER_KALSHI_PUBLIC_PROBE_ENABLED=true
MIDAS_FRONTIER_KRAKEN_PUBLIC_PROBE_ENABLED=true
MIDAS_FRONTIER_COINBASE_PUBLIC_PROBE_ENABLED=true
```

Kraken Spot discovery uses the comma-separated configured pair allowlist
`MIDAS_FRONTIER_KRAKEN_PAIRS` (default `XBTUSD`). The Polymarket switch enables
only its bounded unauthenticated public GET. Kalshi and Kraken additionally
require `MIDAS_FRONTIER_KALSHI_RESEARCH_AUTHORIZATION_REF` and
`MIDAS_FRONTIER_KRAKEN_MARKET_DATA_PERMISSION_REF`, respectively, before the
main API can enable a live probe. The reference must point to a separately
reviewed source permission/terms record; Frontier does not validate the record.
The current review leaves both Kalshi and Kraken live probes blocked. See the
[source-data terms review](frontier/SOURCE_DATA_TERMS_REVIEW_2026-10-27.md).
Coinbase Exchange uses an explicit product allowlist in
`MIDAS_FRONTIER_COINBASE_PRODUCTS` (default `BTC-USD`). Its Market Data Terms
must be acknowledged by setting
`MIDAS_FRONTIER_COINBASE_MARKET_DATA_TERMS_VERSION_ACKNOWLEDGED=2026-08-07`;
that exact-version acknowledgement and the probe flag are separate controls.
The version gate does not validate organization, regional, retention, or
redistribution scope. Coinbase spot remains contextual evidence, never an
event-contract payoff, and no Coinbase source request was made during the
current implementation checkpoint. The source-specific adapter config also
rejects clearing the terms hold without the exact version. Re-review the terms
before enabling the network switch.
These controls do not enable account access, order entry, or credential
handling. While the reference is absent, the API also filters held venues from
stored market, graph, replay, candidate, and comparison reads. Arena replay
snapshots are checked through the dedicated routes, generic job summary/detail
and log routes, and research-activity digests. Generic job submission rejects
held snapshots and cancel actions are rejected before mutating held jobs.
Held reads are rejected before Arena job reconciliation, so the held job
manifest is not rewritten. Missing provenance is rejected.
This route filter does not cover direct database reads or exports, which remain
held. A deliberate probe is initiated from Frontier's Exchanges view. One
probe can capture one bounded listing, optionally one book, and at most ten
recent public trades for the first discovered market. `GET
/api/frontier/trades` returns stored, hash-verified normalized prints with their
source-observation IDs and raw hashes. A valid empty response remains an empty
capture. Polymarket also has an explicit `POST
/api/frontier/probe/polymarket/trades` route that reads one v2 cursor page (up to
100 rows) for a condition already present in the saved listing. The UI exposes a
first-page and continuation action only when the Polymarket source and the
paginated-trade capability are enabled. It reuses the same condition, page size,
taker-only, and 0.01-share filters per page; condition queries expose a fixed
three-year history window. No page walk or data fetch starts automatically.
Normalized v2 rows retain token ID and outcome identity, while wallet profile
fields remain only in the bounded raw source response. Trade prints are not
order-book depth. Kalshi exposes a separate explicit
`POST /api/frontier/probe/kalshi/trades` route with `market_id` (the recorded
native ticker), `limit` (at most 100), and an optional returned cursor. Each
cursor is bound to its ticker and page size; one request captures one page and
Kalshi's block trades remain included by default. The normalization treats
`yes_price_dollars` as a YES-price reference and does not infer a BUY/SELL side
from `taker_outcome_side`. The UI lets a researcher select either Polymarket or
Kalshi and then choose a market already present in saved listing evidence. Kraken
does not currently claim cursor-paginated public trades. The protected Reality
recording and its evidence remain on separate roots.

Kalshi multivariate-event discovery is a separate explicit
`POST /api/frontier/probe/kalshi/multivariate-events` operation. Supply exactly
one of `series_ticker`, `collection_ticker`, or `event_ticker`; an event ticker
maps to Kalshi's documented `tickers` query parameter. The adapter requests one
page with `limit=1` and `with_nested_markets=true`, honors the existing
public-probe configuration and capability gate, and retains but does not follow
a source cursor. `MarketBatch` schema v2 stores typed event groups beside normalized
markets. Each group records whether its member list was included, explicitly
empty, or omitted by the source. A live HTTP 200 response currently proves the
event lookup path but omitted `markets`; see
`data/frontier/live-probes/2026-10-27-kalshi-multivariate-page-r1.json` for its
raw hash, diagnostic row, and bounded store read-back. No nested contract or
combo payout was established by that response. A missing member field is kept
as omitted, a present empty array is kept as empty, and explicit `null` is
rejected. Mission Control displays that state and can open the saved raw response.
One bounded event-detail follow-up for the same ticker returned HTTP 200 with no
`event.markets` field and an explicit empty top-level `markets` array. Adapter
v8 now normalizes this documented response shape as an empty event-detail batch;
its offline replay and separate temporary-store row hash are recorded in
`data/frontier/live-probes/2026-10-27-kalshi-mve-event-detail-r1.json`.
Adapter v9 adds the one-event ticker filter and validates that the returned
event matches the requested ticker. Its preserved HTTP 200 response again
omitted nested markets and had no cursor; offline API replay stores the event
with membership `omitted`. The capture's raw SHA-256 is
`3e2372de6143c0c8f37b3e77265a210596bf3c414fa33d19ee4028b1d2d3a7bb`, and its
offline snapshot replay row SHA-256 is
`e6dcb76b2e18316866c078fd4778c2dff93891132e8b92104e3385c08d1271bd`, verified
from the preserved raw/normalized payload and a fresh temporary-store read.
The original capture-time digest
`cea5ea38a3ffad129fa2baedf3520b9bae71e8d4919521e140f46467baf57d50` is retained
but marked unreconciled because it does not match the artifact payload. The
probe harness reported an event-loop cleanup error after capture and read-back;
it did not repeat the request. See
`data/frontier/live-probes/2026-10-27-kalshi-mve-ticker-filter-r1.json`.

Adapter v10 adds an explicit `POST
/api/frontier/probe/kalshi/mve-component-market` operation. It accepts a parent
canonical market ID and one selected child ticker, and requires that exact
child/event reference to exist in a saved MVE market before making a request.
It issues one public GET to Kalshi's [Get Market](https://docs.kalshi.com/api-reference/market/get-market)
endpoint, checks the returned ticker and event, stores the complete raw response
and normalized market, and includes new `market_metadata` records in market
queries and graph revisions. The Mission Control MVE inspector provides the
explicit capture control. It exposes the child market's current rules and
lifecycle, but never treats them as proof of the parent combo's payout or
settlement.

One capture followed the first child reference from the saved October 26 combo.
The child was closed at capture time and its public rules include fair-price
fallbacks for inactive/non-playing and postponed games. Raw hash
`0f1c3cd42cac5202ca5a3012d58cb8d9631bf39cce313c738bb0448140271eda` and
isolated-store row hash
`a2e7ae0c08436155a0bdc80e07f16d6b882eaf9706617994be135b668ec5897a` are
preserved in `data/frontier/live-probes/2026-10-27-kalshi-mve-component-market-r1.json`.
The capture has no book or price. Its detailed rules strengthen the reason the
combo cannot be reduced to a verified one-hot payoff; no candidate economics
were enabled.

Adapter v11 retains Kalshi's optional `yes_settlement_value_dollars` selected-leg
field as a bounded exact Decimal and shows it in Mission Control. The official
schema documents the field, but Frontier does not infer a parent MVE payout
from it. Omission remains unknown, and the saved live child response did not
contain the field; the value parser and UI are fixture-verified only. Refer to
Kalshi's [Get Multivariate Events](https://docs.kalshi.com/api-reference/events/get-multivariate-events)
schema for the source definition.

Adapter v12 adds a saved-evidence-only Kalshi MVE settlement arithmetic audit
at `POST /api/frontier/economics/kalshi-mve-settlement-audit`. It reads the
bounded local Kalshi observation window and makes zero public requests. If all
selected component YES settlement values, the parent settlement value, and a
final settled state are present, the endpoint recomputes the product (mapping a
selected NO value to one minus the reported YES value) and returns either
`SOURCE REPORTED PRODUCT MATCH` or `SOURCE REPORTED PRODUCT MISMATCH`.
Missing inputs remain `INCOMPLETE EVIDENCE`; a provisional or unsettled parent
is `SOURCE VALUES NOT FINAL`; unsupported market structure is returned as
`UNSUPPORTED SETTLEMENT STRUCTURE`. A result checks captured values against
Kalshi's stated combo method; it does not authenticate source truth, verify component rules,
infer outcome correctness, or evaluate prices/returns. Method references are
Kalshi's [combo guidance](https://help.kalshi.com/en/articles/13823820-combos),
[NO scalar settlement guidance](https://help.kalshi.com/en/articles/17515177-protected-nfl-player-markets),
and [MVE API schema](https://docs.kalshi.com/api-reference/events/get-multivariate-events).
The response includes the saved observation ID and raw-body hash. Current
value coverage is documentation-shaped fixtures only; the preserved live child
response lacks those values.

For Kalshi multivariate event markets, adapter v4 normalizes up to 64 native
selected component references (event ticker, market ticker, selected YES/NO
side) and Mission Control displays them from the saved market observation. This
is source-declared composition metadata, not verified component rules or payoff
semantics. Kalshi's documentation describes combo payout as the product of
component position values and says combos settle as their own reviewed markets;
Frontier keeps these markets conditional and excludes their unverified payout
from candidate economics. Older saved MVE rows retain their raw native fields
but do not gain normalized component entries until a new bounded listing is
captured.

For a recorded Kalshi market, the Exchange Explorer can explicitly capture
public fee metadata with `POST /api/frontier/probe/kalshi/fee-metadata` and its
canonical `market_id`. The route requires the source's public-probe setting and
the market must be in the bounded saved listing window. It makes one event GET
with `exclude_markets=true` and one series GET, then stores both raw responses
with the normalized event overrides and series fee type/multiplier. This
capture makes no immediate fee calculation. On a later saved-evidence replay,
the API may join a complete event/series pair into a provenance-bound
`FeeStatus.ESTIMATE` for a supported quadratic taker schedule. It verifies
native market/event/series identity, parsed source fields, endpoint paths, raw
hashes, and timestamps. The metadata must be no later than the pinned book quote
and no more than 24 hours old at quote and replay time. Partial, unreported,
mismatched, stale, unsupported, and held-source evidence remains unknown. The
candidate uses one fill at its modeled buy price, derived from the pinned ask
and any selected scenario, plus conservative `$0.01` non-direct-member balance
alignment; the classification remains conditional or incomplete. Replay
manifest v2 separately pins fee-metadata observation IDs and run history
displays their count. This does not establish the account's fee
class, maker or multi-fill costs, FCM charges, or executable net economics.

A separate local
`POST /api/frontier/economics/kalshi-fee-sensitivity` accepts the recorded
`market_id`, paired event and series `observation_id`s, and manual
`price_usd`/`quantity_contracts`. It makes no source request; it checks the
stored source kind, host, market identity, timestamps, normalized metadata and
raw hashes before computing a one-fill taker sensitivity. Supported quadratic
fee types use the dated July 7, 2026 public formula, with direct and non-direct
balance-precision scenarios. The response is hashed and hypothetical, not an
account quotation, not a quote from a saved public book, and not the candidate
fee calculation. Unsupported fee types, malformed inputs and mismatched
evidence fail closed. Fee sensitivity also requires an explicitly complete
event override pair or an explicitly null/null pair that clears the override;
missing or partial event fields make the sensitivity unresolved. This follows
Kalshi's documented rule that event fees override the parent series and that a
null/null pair clears that override
([event fee-change API](https://docs.kalshi.com/api-reference/events/get-event-fee-changes)).
Multi-fill rounding accumulation, rebates, FCM charges and
later fee schedule changes remain outside the one-fill model. The separate
`POST /api/frontier/economics/kalshi-fee-order-sensitivity` route accepts 1–32
manual fills, each carrying its native instrument ID, and requires all fills to
use the same instrument and buy/sell side. It verifies that instrument against
the recorded market and then models per-fill microdollar rounding, order-level
rounding accumulation, and capped rebates under both balance-precision cases.
The order response includes per-fill and aggregate totals with a deterministic
digest. Inputs remain manual, hypothetical, and outside candidate economics;
account precision, maker/mixed orders, FCM charges, and later schedule changes
remain unknown. Neither fee sensitivity binds manual prices to an empty or
different-market public book.
The Kalshi trade-page route follows the same saved-market and source-configuration
gates, persists one raw and normalized page per click, and returns no next cursor
when Kalshi's response cursor is empty. It does not start a history crawl.

Polymarket and Kalshi also advertise the capability `event_market_groups`.
Mission Control's market inspector can call `POST
/api/frontier/probe/{venue}/event-markets` with a saved canonical `market_id`;
Polymarket may supply a numeric `native_event_id` when the saved child record
has no parent identity, while Kalshi uses the recorded event ticker by default.
The route makes one bounded GET, confirms the response contains the selected
market, validates and stores the complete raw event response beside a normalized
`MarketBatch`, and exposes the parent event title and any native outcome label
in the Market Explorer. This only adds context for hypothesis discovery. The
matcher requires similar parent titles and a market-specific outcome text
overlap. It checks explicit years in both parent and child titles; within-source
contradictions and cross-source mismatches block both title and parent-context
paths. It does not infer YES/NO semantics or verify payoff and settlement
equivalence. Kraken does not advertise event-group discovery. Source probing
remains explicit and disabled by default.
The relationship proposal route cites each loaded market's append-only store
record in edge evidence; this lets the graph evidence IDs resolve through the
observation API. For store-backed reads, the API also overlays the selected
market and book record IDs onto model provenance. Replay manifests, candidate
legs, and Arena snapshots then retain those resolvable IDs. Direct adapter or
matcher calls without a store preserve deterministic adapter-derived
observation identities. Replay v6 pins this lineage behavior in its versioned
input identity; the storage schema and existing observation rows are unchanged.

The Economic Workbench can compare two named virtual scenarios through
`POST /api/frontier/replay/compare`. Both arms use the same stored evidence and
pinned replay time, with an explicit shared-input digest. The API bounds each
comparison to 100 saved markets, 200 saved books, 500 verified relationships,
and 500 proposed relationships; it makes no public-source requests. Both replay
arms and the comparison record are appended atomically. Saved results are
available from `GET /api/frontier/comparisons` and
`GET /api/frontier/comparisons/{comparison_id}`. The comparison reports matched
candidate identities and modeled classification/count changes. It does not
score the scenarios or establish fills, simultaneous availability, or profit.
The UI's baseline is the quoted-input assumption and the second arm uses the
current workbench assumptions; both remain hypothetical.

Candidate detail also provides a local virtual-funding comparison. A researcher
may enter a nonnegative decimal balance separately for each venue. The UI
compares it exactly with that venue's modeled principal plus known modeled fees;
balances are never pooled, transferred, sent to an API, or persisted. Comparison
is keyed by venue and canonical denomination identity, not a currency code.
Missing or mixed quote identity disables comparison; a token marked `USD` does
not share a balance with `fiat:USD`. Unknown fees leave the fee amount unresolved
rather than allowing a sufficient-funds claim. These inputs do not inspect real
accounts, collateral, transfers, or settlement duration. Focused coverage checks
exact decimal shortfalls, unresolved fees, venue fragmentation, responsive
layout, and same-code/different-asset isolation. Older normalized records with
no denomination identity remain readable but cannot be upgraded by inference
from their display ticker; candidate generation and independent audit keep them
incomplete. The backend also rejects verified payout denominations that differ
from the recorded settlement asset unless a valuation bridge is implemented;
candidate and independent-audit paths repeat the guard.

Keep Frontier experiments in a temporary store and use the bounded probe gates
described by the [Frontier operations guide](frontier/FRONTIER_OPERATIONS.md).
When a probe returns diagnostic observation IDs, inspect the stored raw hash and
normalized failure record before changing an adapter.
The displayed source request count is a bounded trailing 60-second local
counter; the lifetime count is reserved for per-operation request deltas.

`POST /api/frontier/arena-replay` packages the latest bounded local market,
book, and effective verified-relationship records into a content-addressed
snapshot under `MIDAS_ARENA_ROOT`, then submits the paired replay as an Arena
`frontier_replay` job. Arena's normal host-wide admission gate remains in force.
The worker is capped at 300 seconds, 512 MiB, 50% CPU and idle I/O, and has IP
network families disabled. Snapshots are capped at 8 MiB each, 128 MiB total,
and 1,000 entries. The result route is available only for a successful completed
job and checks both snapshot and artifact hashes. Mission Control lists the
latest bounded job records and polls only while a job is queued or running.
Two controlled fixture workers completed under systemd after passing the normal
host-wide admission gate. The latest durable profile records process CPU deltas
and peak RSS; Mission Control displays these measurements for inspection.
The Frontier readiness panel reports `LIVE_VALIDATION_PENDING` until it finds
a completed, hash-verified Arena result with a worker runtime record in its
bounded local scan. It reports `EVIDENCE_RECORDED` after that check and
`REVIEW_REQUIRED` for a completed record with invalid result/runtime evidence.
`resource_sustainability` remains `NOT_MEASURED`; two short, identical fixture
runs do not establish sustainable capacity or replace a representative workload
profile.

For offline event-time replay over repeated instrument books, use
`midas.frontier.timeline.deterministic_timeline_replay`. The engine accepts
explicit fixture/recorded source-state events and bounded UTC evaluation times;
it expires stale books and invalidates pre-outage quotes until new book evidence
arrives. It calls the existing deterministic replay and independent audit for
each frame and hashes the complete input and result. Verify it with:

```bash
env PYTHONPATH=packages:.:tests /home/charlie/midas/.venv/bin/pytest tests/frontier/test_timeline.py -q
MYPYPATH=packages /home/charlie/midas/.venv/bin/mypy --strict --follow-imports=silent packages/midas/frontier/timeline.py
```

This Python API is offline and bounded, but is not yet wired into the Frontier
HTTP API, persisted Arena jobs, or the Mission Control timeline view.

Relationship decisions use `POST /api/frontier/relationships/{id}/review`. The
review form records source market observation IDs and appends a linked revision;
it cannot bypass the same-payoff verifier. Reviewer labels and external assertion
IDs are self-attributed references, not authenticated identities or fetched
documents. The Frontier SQLite schema upgrades v2/v3/v4/v5 stores additively to
v6; the v5 migration adds separate indexes for each relationship endpoint, and
v6 adds an append-only paired-comparison table without rewriting earlier records.
The relationship graph route accepts an optional `center_market_id`, a `depth`
from 1 to 3, and an edge `limit` up to 200. It loads at most 200 recorded
markets. Centered traversal uses indexed left/right adjacency and scans at most
500 relationship rows per request; a wide breadth-first layer is split into
queries of at most 200 market IDs. The response includes scanned-row counts and
marks when the result may be incomplete. Centered one-hop cursors use stable
timestamp/relationship-ID keyset pages. Centered two- and three-hop cursors pin
the center, depth, page size, and append-only graph revision, then deterministically
recompute the same bounded breadth-first window for each page. Cursor use after
any market-metadata, relationship, or review append returns HTTP 409. The
multi-hop continuation only pages through the same 500-row result window; if a
scan cap truncated the traversal, the incomplete flag remains visible after the
last available page. The uncentered view remains a bounded recent-edge query
without cursor pagination. List reads recheck stored observation, relationship,
review-lineage, replay, and comparison hashes before research use.

Deterministic replay currently evaluates verified cross-venue binary coverage
and an all-long, same-market construction for three to sixteen verified
exhaustive one-hot outcomes. The multi-outcome path is controlled-fixture
verified; it does not evaluate captured listings without verified payoff and
resolution evidence. Both paths are hypothetical research only and always leave
practical execution eligibility false.

Replay version 5 attaches a separately coded arithmetic audit and a full-or-no-fill
exposure sensitivity to each supported candidate. The sensitivity analytically
finds the exact adverse pattern across up to 16 legs; it does not model partial
fills, pattern probabilities, hedging, or unwind recovery. The fee-inclusive
stress result remains unknown when any candidate leg lacks an applicable fee.
Economic model version 4 and independent audit version 2 record this behavior.
It re-derives the supported payoff, pinned quote/depth, applicable fee, modeled
cost, and terminal result from stored inputs. Its normalized-input digest also
includes effective relationship mappings and the proposal limit, so those
assumptions cannot change under the same run identity. An audit disposition of `verified`
means these calculations agree over those pinned inputs; it does not validate
external market truth, reviewer assertions, source synchronization, or execution.
The audit's input SHA-256 is shown in candidate details.

If a bounded probe receives valid JSON but the adapter rejects its shape, the
API stores the raw response with a `SourceFailureRecord` and returns the
observation ID in the error details. The hash-verified observation endpoint can
read it, and a later successful probe restores healthy source state. Invalid JSON
is retained when the complete body is within the configured response cap; invalid
UTF-8 is base64-encoded while the raw hash remains over the original bytes.
Oversized or partial response bodies are not stored.

### Coverage and quality analytics

`GET /api/frontier/analytics/coverage` reads saved local evidence and returns
`network_called: false`. It uses bounded windows of 50 market records, 50 book
observations, 20 eligible replay runs, and 5,000 candidate records; full stored
market/instrument identity counts use the store's indexed records. Held source
venues are excluded. Pricing summaries require verified observation hashes and
timestamps, a joined market/instrument identity, two-sided uncrossed unflagged
books, and an exact quote-asset identity. Missing freshness limits and exchange
timestamps remain explicitly unknown. Candidate rejections count each distinct
reason once per rejected candidate. Repeated construction metrics require
independently recomputed positive gross P&L, verified timing, distinct book
sets, distinct replay times, pinned market-observation IDs, and exact quote
denominations. These are recorded-sample summaries, not venue-wide prevalence,
net economics, or executable opportunities. Mission Control loads the Coverage
& quality tab on demand and displays the sample and interpretation limits
alongside the metrics.

For focused Frontier verification, use isolated test databases and run:

This linked worktree does not contain a local `.venv`. The current host's
existing dependency environment is used below, while `PYTHONPATH` points imports
at this Frontier checkout. Replace that interpreter path with the interpreter
for your own locked environment when working elsewhere.

```bash
PYTHONPATH=packages:apps/api /home/charlie/midas/.venv/bin/python -m pytest tests/arena/test_frontier_replay.py tests/arena/test_foundations.py tests/arena/test_arena_api.py tests/frontier tests/integration/test_api.py -q
/home/charlie/midas/.venv/bin/python -m ruff check apps/api/arena.py apps/api/frontier.py apps/api/main.py packages/midas/arena/frontier_replay.py packages/midas/arena/jobs.py packages/midas/frontier tests/arena/test_frontier_replay.py tests/frontier tests/integration/test_api.py
/home/charlie/midas/.venv/bin/python -m mypy --follow-imports=silent packages/midas/arena/frontier_replay.py packages/midas/arena/jobs.py apps/api/frontier.py
corepack pnpm --dir apps/web test
corepack pnpm --dir apps/web typecheck
corepack pnpm --dir apps/web lint
corepack pnpm --dir apps/web format:check
corepack pnpm --dir apps/web build
corepack pnpm --dir apps/web exec playwright test e2e/frontier.spec.ts --workers=1
```

The Frontier Playwright case sets `MIDAS_FRONTIER_ROOT` under a temporary
directory and `MIDAS_ARENA_ROOT` under a sibling temporary root. It never
enables a source probe and the test does not submit an Arena job. The live Arena
worker path has completed over a controlled fixture after normal admission.
The job ran in an isolated worktree Arena root; its measured process CPU and
peak RSS are a single small-job sample, so resource sustainability remains
unmeasured. See the
[Frontier mission ledger](frontier/FRONTIER_MISSION_LEDGER.md) before extending
the scope or changing its deployment status.

## Keep worktrees and runtime data separate

Read [MIDAS_CURRENT_STATE.md](MIDAS_CURRENT_STATE.md) before changing an
operational checkout. `main` is the authoritative development branch. The Reality
and Veritas worktrees are retained because active services use their paths and
their mutable data belongs to those workspaces. Do not remove, repoint, or share
their database, model, campaign, or recording paths during ordinary development.

For an explicitly approved isolated test checkout, use separate temporary
databases and artifact roots. Keep mutable stores local to that checkout, and do
not symlink them to active campaign or recorder directories.

## Data and research constraints

`data/` is the default location for local databases, journals, models, campaign
outputs, recordings, and exports. Git ignores mutable stores and generated
captures. Small curated fixtures and manifests that are already tracked remain
versioned. Do not add a full runtime database, model directory, or research
archive to a source change. Preserve the protected Laboratory campaign and
historical Prometheus evidence; verify them read-only.

MIDAS remains paper-only. Public observation and synthetic evaluation do not
establish executable fills or real-market profitability. Reality operations must
respect the constraints in [ROADMAP.md](ROADMAP.md).
