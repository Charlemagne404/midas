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
```

Kraken Spot discovery uses the comma-separated configured pair allowlist
`MIDAS_FRONTIER_KRAKEN_PAIRS` (default `XBTUSD`). These flags permit only bounded
unauthenticated public GETs. They do not enable account access, order entry, or
credential handling. A deliberate probe is initiated from Frontier's Exchanges
view. One probe can capture one bounded listing, optionally one book, and at most
ten recent public trades for the first discovered market. `GET
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

For a recorded Kalshi market, the Exchange Explorer can explicitly capture
public fee metadata with `POST /api/frontier/probe/kalshi/fee-metadata` and its
canonical `market_id`. The route requires the source's public-probe setting and
the market must be in the bounded saved listing window. It makes one event GET
with `exclude_markets=true` and one series GET, then stores both raw responses
with the normalized event overrides and series fee type/multiplier. This
evidence-only capture does not set the market's `FeeSchedule` or change candidate
economics. A separate local
`POST /api/frontier/economics/kalshi-fee-sensitivity` accepts the recorded
`market_id`, paired event and series `observation_id`s, and manual
`price_usd`/`quantity_contracts`. It makes no source request; it checks the
stored source kind, host, market identity, timestamps, normalized metadata and
raw hashes before computing a one-fill taker sensitivity. Supported quadratic
fee types use the dated July 7, 2026 public formula, with direct and non-direct
balance-precision scenarios. The response is hashed and hypothetical, not an
account quotation, not a quote from a saved public book, and not applied to
candidate net economics. Unsupported fee types, malformed inputs and mismatched
evidence fail closed. Multi-fill rounding accumulation, rebates, FCM charges and
later fee schedule changes remain outside this model.
The Kalshi trade-page route follows the same saved-market and source-configuration
gates, persists one raw and normalized page per click, and returns no next cursor
when Kalshi's response cursor is empty. It does not start a history crawl.

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
500 relationship rows per request; the response includes the row count and marks
when the scan may be incomplete. The uncentered view remains a bounded recent-edge
query. List reads recheck stored observation, relationship, review-lineage,
replay, and comparison hashes before research use.

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

For focused Frontier verification, use isolated test databases and run:

This linked worktree does not contain a local `.venv`. The current host's
existing dependency environment is used below, while `PYTHONPATH` points imports
at this Frontier checkout. Replace that interpreter path with the interpreter
for your own locked environment when working elsewhere.

```bash
PYTHONPATH=packages:apps/api /home/charlie/midas/.venv/bin/python -m pytest tests/frontier tests/integration/test_adapters.py tests/integration/test_api.py::test_offline_api_workflow_contract_and_persistence -q
/home/charlie/midas/.venv/bin/ruff check apps/api/frontier.py apps/api/config.py apps/api/main.py packages/midas/frontier tests/frontier tests/integration/test_api.py
/home/charlie/midas/.venv/bin/ruff format --check apps/api/frontier.py packages/midas/frontier tests/frontier tests/integration/test_api.py
PYTHONPATH=packages:apps/api /home/charlie/midas/.venv/bin/mypy packages/midas/frontier apps/api/frontier.py
corepack pnpm --dir apps/web test
corepack pnpm --dir apps/web typecheck
corepack pnpm --dir apps/web build
```

The Frontier Playwright case sets `MIDAS_FRONTIER_ROOT` under a temporary
directory. It never enables a source probe. See the
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
