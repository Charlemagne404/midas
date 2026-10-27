# Architecture

Midas is a modular monolith and a separately built React command center. Financial domain code under `packages/midas` imports neither the API, SQLAlchemy nor frontend. Pydantic is the shared validation contract, not an HTTP response dependency.

```mermaid
flowchart LR
  Gamma[Public Gamma GET] --> Adapter[Version-aware adapters]
  REST[Public CLOB GET] --> Adapter
  WS[Public market stream] --> State[Book state and integrity]
  Adapter --> State
  Demo[Labeled synthetic fixtures] --> State
  Adapter --> Journal[Append-only raw + normalized JSONL]
  WS --> Journal
  State --> Math[Decimal binary strategy]
  Math --> Risk[Independent risk gate]
  Risk --> Sim[Internal discrete-event exchange]
  Sim --> Ledger[Virtual ledger]
  Ledger --> Audit[Independent reconciliation]
  Math --> Store[SQLAlchemy research records]
  Sim --> Store
  Store --> API[FastAPI]
  API --> UI[React command center]
  Journal --> Replay[Receipt-ordered replay]
  Replay --> Math
  Sim --> Research[Arena training and evaluation]
  Research --> Artifacts[Versioned local artifacts and replays]
  Artifacts --> API
```

## Responsibilities

- `core/models.py`: validated market, fee, instrument, book, event and evaluation contracts.
- `market_data`: public GET allowlist, normalization, bounded reconnecting stream state, raw recording and receipt-ordered replay.
- `arbitrage`: deterministic complete-binary evaluator and a `Strategy` protocol. It knows no portfolio or database.
- `risk`: independently configurable hard constraints over virtual proposals and portfolio exposure. A strategy verdict cannot override them.
- `simulation`: virtual clock, scheduler, exchange, portfolio ledger, accounting auditor, catalog and executable scenarios.
- `apps/api`: configuration, storage, lifecycle orchestration, HTTP contracts and bounded experiment admission.
- `apps/web`: dashboard, scanner inspection, scenario execution, event cursor and persisted analytics.

## Storage and limits

One indexed relational `records` table stores immutable versioned JSON payloads for market metadata, observations, simulations and system events, with source, entity key and receipt time as separate columns. Models are normalized before insertion. Financial values serialize as decimal strings. This reduces migration surface in the first milestone; hot price-level storage and a richer relational experiment schema are deferred.

PostgreSQL uses an Alembic migration. SQLite is the zero-infrastructure offline default and initializes the same initial tables directly. SQLite auto-created schemas should not receive the initial Alembic migration again; use a fresh database for migration exercises. A future schema change must reconcile the SQLite bootstrap with migration history.

Metadata refreshes periodically; the configured active-market subset is sorted by liquidity. Current observations are reevaluated at read time so a stalled refresh cannot retain a verified label. Database records older than the configured retention window are pruned hourly. Raw JSONL files are not deleted automatically: the recorder stops at a configured total budget, reports an error and blocks new audited simulations until storage is restored. Explicit prune tooling is provided.

The websocket queue is bounded at 2,048 frames; deduplication retains 4,096 hashes. In-memory events retain 300 entries. API history queries are bounded. CPU simulation and scanning use worker threads. Two scenario workers are permitted concurrently; total admitted running/queued requests are capped at eight. The virtual clock itself never sleeps.

## Operating boundary

Demo startup constructs no public network client. Live mode observes public data only. Scenario portfolios are always synthetic independent experiments, including while live observation runs. The optional public Data API v2 smoke does not fetch account positions. There is no wallet, secure SDK, signature, external execution adapter, order submission/cancellation route, or credential field.

HTTP endpoints are intended for a trusted local workstation. Docker publishes ports on loopback. Authentication, multi-user access and production ingress are deferred.

## Milestone 2 extension (supersedes the Milestone 1 storage/payout boundary above)

Public Gamma metadata + CLOB fee/delay metadata feed `CTFVerifier`; fixed-contract
finalized Polygon reads produce `MarketEconomicAttestation`. `BinaryStrategy` consumes
the attested structure, records complete/rejected proof traces and conservative live
fee/terminal-rounding bounds. Public REST remains GET-only; RPC POST permits only chain
reads, never transactions. V2 remains economically unsupported in live mode.

The new domain state machine `midas.paper.broker` uses the original strategy/risk,
virtual `Exchange` and independent auditor. `apps.api.paper.PaperBroker` persists a
shared account and immutable journal with an atomic CAS transition. Cash envelopes,
independent leg actions, books, orders, settlements and stop state survive restart.
All startup paths use Alembic 001/002, including recognized legacy SQLite adoption.
SQLite explicitly uses WAL and FULL synchronous writes. Financial tables are never
pruned with observation records. See `RECOVERY_AND_RECONCILIATION.md` for boundaries.

Synthetic, recorded and live-shadow accounts stay separate. New fault/differential
experiments run the production broker state machine. The API and React Paper Trading
page expose the actual durable account. Existing 43 scenarios and their interfaces
remain intact. Historical replay can consume attested metadata and verified settlement
observations; it does not infer missing future observations.

## Project Prometheus extension

Arena research code lives under `packages/midas/arena` and is exposed through the
`/api/arena` routes in `apps/api/arena.py`. It reuses the Laboratory simulator and
accounting checks while keeping datasets, model weights, jobs, tournaments, and replay
payloads in a separate artifact store rooted at `MIDAS_ARENA_ROOT` (default
`data/arena`). Manifests record source and artifact identities; bounded native jobs
capture their source and write durable job state. `apps/web/src/Arena.tsx` presents
those registries and their evaluation evidence.

Arena policies are research artifacts over synthetic scenarios. They do not enter
the live observation or paper-broker decision path. Preserve the distinction between
public observations, synthetic scenarios, modeled execution, and measured findings.
The [Prometheus final report](PROMETHEUS_FINAL_REPORT.md) describes the current
evaluation design and its exceptions.

## Project Frontier extension

Frontier is an isolated research path under `packages/midas/frontier`; it does not
replace the legacy Polymarket contracts or change Reality's protected collector.
Three public-only adapters normalize Polymarket event tokens, Kalshi event
contracts, and configured Kraken spot pairs into versioned venue-aware models.
Capabilities and unsupported behavior are declared per adapter. A bounded HTTPS
GET transport enforces host allowlists, rate, retry, timeout, and response-byte
limits; all adapters are disabled for network access unless explicitly configured.
Kalshi and Kraken also require a configured source-terms authorization reference
before the main API can enable live capture. Their current terms review blocks
those captures; see the [Frontier source-data terms review](frontier/SOURCE_DATA_TERMS_REVIEW_2026-10-27.md).

The Frontier API writes source responses and normalized batches into its own
append-only SQLite store. Read routes use read-only SQLite connections. Recorded
market and book observations feed a deterministic replay with a hash of the exact
Frontier backend source set, normalized inputs, relationship decisions, and virtual
scenario assumptions. The matcher proposes hypotheses only. Append-only,
self-attributed review revisions record rejected, ambiguous, or strict-verifier
decisions; the verifier requires verified resolution and exhaustive payout
evidence. Reviewer and external assertion references are not authenticated.
Replay uses only the latest decision and preserves the full review history.

When a venue's source-use policy is blocked, Frontier derives a held-source set
from adapter configuration and applies it at the application read boundary.
SQL queries omit held observations and related graph edges; direct evidence,
replay inputs, and derived API results are filtered or rejected. Generic Arena
job and research-activity summaries, details, and logs also check Frontier
replay provenance; generic replay submission rejects held snapshots and
cancellation is blocked before a held job can be changed. Missing replay
provenance fails closed. Raw append-only evidence remains preserved. Direct
database inspection and exports
are outside this route quarantine and remain under the operational hold.
Canonical denomination identities now flow from instrument quote through public
book, fee, trade, candidate leg, and modeled capital fields. Candidate economics
and independent audit require those exact identities to agree with the payoff
settlement unit; a display ticker alone cannot bridge fiat to a token or one
token contract to another. Legacy rows without identity remain readable and
remain economically incomplete. Virtual-funding inputs stay local and are
separated by venue and exact denomination.
Polymarket adapter v3 and Kalshi adapter v5 also normalize source event-group
context through an explicit one-GET `event_market_groups` capability and
`POST /api/frontier/probe/{venue}/event-markets`. The route binds the returned
children to a market already in the recorded window and stores the raw event
response with the normalized group. Parent event titles and native outcome labels
are preserved separately from market questions. Cross-venue parent-title plus
outcome-text matches remain hypotheses; they do not infer YES/NO semantics or
verified payoff equivalence. Kraken explicitly does not support event groups.
The relationship proposal API binds evidence IDs to the immutable observation
records that supplied the normalized markets, so those graph evidence links
resolve to the raw and normalized source captures.
Kalshi adapter v4/v5 normalizes bounded native MVE component market/event IDs
and selected YES/NO sides as source-declared structure; combo payout and
resolution remain unverified and excluded from candidate economics.
List reads validate raw observation hashes, normalized row hashes, relationship
payload/index hashes, latest review-to-revision links, and replay output digests
before graph or replay processing. `GET /api/frontier/graph` offers one-to-three
hop neighborhoods from a recorded market, capped at 200 source markets and 500
scanned effective edges; this remains a bounded recent-window traversal rather
than a large-universe graph index.
Centered one-hop graph reads use relationship keysets; two- and three-hop reads
use deterministic breadth-first result pages. Cursors bind the center, depth,
page size, and append-only graph revision. Each request recomputes the bounded
window, scans at most 500 relationship rows, chunks wide frontiers into queries
of at most 200 markets, and returns 409 if graph inputs changed.

Replay v5 added effective outcome/instrument mappings, the proposal limit, and
full-or-no-fill exposure sensitivity to the replay input identity and supported
candidate output. Replay v6 overlays the exact immutable store record ID onto
market and book model provenance when API routes load evidence from SQLite.
Replay manifests and candidate legs therefore cite records that resolve through
the observation API; direct adapter/in-memory replay continues to use its
deterministic adapter-derived IDs. This is a replay-version change, not a schema
migration or rewrite of prior evidence. A local paired-replay route evaluates two
named scenarios over one pinned set of stored markets, books, verified
relationships, mappings, code version, and replay time. Its API bound is 100
markets, 200 books, 500 verified relationships, and 500 proposals; it makes no
network requests and atomically appends both arm runs plus a comparison record.
The Mission Control workbench exposes the paired result. It reports matched
candidate and classification/count changes without scoring an assumption as
better or suggesting an executable fill. SQLite schema v6 stores comparisons
append-only and retains additive upgrade paths from earlier schemas.

The optional `POST /api/frontier/arena-replay` route stages the same bounded
evidence as a content-addressed snapshot under the configured Arena root, then
submits an offline `frontier_replay` job through Arena's existing host-wide
admission lock and resource gate. The worker is limited to 300 seconds, 512 MiB,
50% CPU, and idle I/O; IP address families are disabled. Snapshots and completed
artifacts are size-bounded and checked against their content hashes. The Arena
API lists recent Frontier replay jobs and exposes a completed result only after
checking its job configuration, snapshot reference, and result digest. The native
Frontier replay panel can submit a job explicitly, track it, and inspect its
comparison. This is a short replay job, not a Laboratory campaign or collector.
The development checkpoint did not pass the live host admission gate to launch
an Arena worker.

Polymarket additionally exposes an explicit, one-page-at-a-time v2 public trade
capture route. Schema-v2 trade records retain condition, token, outcome, and
transaction identities; an opaque source cursor is wrapped with the requested
condition and page size before the API accepts a continuation. The page repeats
the source filters, and no walk starts automatically. One direct first page and
one continuation through the local API route have bounded, hash-pinned public
evidence; this does not establish full history, depth, synchronized pricing,
or execution. Kalshi and Kraken do not advertise this page capability.
Kalshi exposes a separate fee-metadata capture for one already-recorded market.
It makes one public event request with child markets excluded and one public
series request, then stores both raw responses against the native event override
and series fee parameters. This is inspection evidence only: Frontier leaves the
canonical market fee schedule unknown because account precision, maker/mixed-order
behavior, FCM charges, scheduled changes, and full candidate fee applicability
remain unresolved. Local manual one-fill and bounded one-order sensitivities now
apply the documented quadratic taker formula, per-fill rounding, and order-level
rounding/rebate rules for both published balance-precision cases. They remain
separate from candidate economics and require a recorded native instrument; manual
prices are not represented as public quotes or captured fills.
When a bounded probe receives a decoded 2xx response that fails normalization,
the raw body and typed source-failure diagnostic are stored and the API returns
the observation ID. Complete within-cap invalid JSON and non-2xx bodies are also
stored; invalid UTF-8 uses lossless base64 with the original-byte hash. Oversized
or partial response bodies are rejected without persistence.
The current economic verifier handles two bounded families: all-long complete
binary coverage across two venues after verified payoff equivalence, and all-long
coverage of three to sixteen exhaustive one-hot outcomes within one verified
market. The latter is tested with controlled fixtures only; captured public
markets have not met its payoff and resolution evidence requirements. Other payoff
structures and general multi-leg searches remain unsupported. It does not produce
execution instructions, and public quotes never establish practical execution
eligibility.

Replay applies a separately coded arithmetic audit to generated candidates. It
recomputes candidate identities, payoff states, pinned book prices and depth,
supported fees, basket costs, terminal P&L, and classification from the same
normalized replay inputs, and records a versioned input hash. This checks
calculation agreement; it does not independently authenticate market semantics,
source timing, fee authority, or execution. A verified audit is not a profitability
or fill claim.

```mermaid
flowchart LR
  P[Polymarket public REST] --> A[Read-only adapters]
  K[Kalshi public REST] --> A
  S[Kraken Spot public REST] --> A
  A --> N[Versioned normalized markets and books]
  A --> R[Raw response evidence]
  N --> G[Hypothesis relationship matcher]
  R --> D[Bounded append-only Frontier SQLite]
  N --> D
  G --> D
  UI --> H[Strict review verifier and immutable revision]
  H --> D
  D --> X[Deterministic replay]
  X --> E[Decimal candidate calculators]
  E --> IA[Independent arithmetic audit]
  IA --> API
  X --> API[Frontier research API]
  D --> API
  API --> UI[Mission Control Frontier workspace]
```

Source capture is an explicit bounded request, not a background collector. Current
live probe fixtures and their limitations are documented in
`data/frontier/live-probes/README.md`. The [Frontier engineering report](frontier/FRONTIER_ENGINEERING_REPORT.md)
states the verified integration scope, test evidence, and deferred work.
