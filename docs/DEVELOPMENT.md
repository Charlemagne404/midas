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
capture. The protected Reality recording and its evidence remain on separate
roots.

Relationship decisions use `POST /api/frontier/relationships/{id}/review`. The
review form records source market observation IDs and appends a linked revision;
it cannot bypass the same-payoff verifier. Reviewer labels and external assertion
IDs are self-attributed references, not authenticated identities or fetched
documents. The Frontier SQLite schema upgrades v2/v3 stores additively to v4.
The relationship graph route accepts an optional `center_market_id`, a `depth`
from 1 to 3, and an edge `limit` up to 200. It loads at most 200 recorded
markets and scans at most 500 effective relationships per request; the response
marks capped scan windows explicitly. List reads recheck stored observation,
relationship, review-lineage, and replay hashes before research use.

For focused Frontier verification, use isolated test databases and run:

```bash
.venv/bin/uv run --frozen pytest tests/frontier tests/integration/test_adapters.py tests/integration/test_api.py::test_offline_api_workflow_contract_and_persistence -q
.venv/bin/uv run --frozen ruff check apps/api/frontier.py apps/api/config.py apps/api/main.py packages/midas/frontier tests/frontier tests/integration/test_api.py
.venv/bin/uv run --frozen mypy packages/midas/frontier apps/api/frontier.py
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
