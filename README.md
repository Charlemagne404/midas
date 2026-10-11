# MIDAS

**A read-only Polymarket research command center and deterministic virtual exchange laboratory.**

Midas evaluates complementary binary positions using exact ask-depth arithmetic, independently gates virtual risk, and tests sequential execution against an auditable simulated venue. The research system remains useful when every observed real opportunity is rejected.

**Midas never submits real orders. No wallet, private key, deposited balance or trading credentials are required.** Demo mode is entirely offline after dependencies are installed. Live mode observes unauthenticated public market data and maintains a separate virtual paper account. Lab experiments use labeled synthetic portfolios; historical replay preserves recorded data provenance.

![Midas command center](docs/mission-control.png)

## Install and run

Requirements: Python 3.12+, Node 22+, Corepack, and uv. Dependencies are locked. If uv is unavailable, bootstrap it locally:

```bash
python3 -m venv .venv
.venv/bin/pip install uv
.venv/bin/uv sync --frozen
```

If uv is already installed, `uv sync --frozen` creates the environment. Frontend dependencies:

```bash
corepack pnpm install --frozen-lockfile
```

Start the API from the repository root:

```bash
.venv/bin/uv run uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
```

Start the dashboard in a second terminal:

```bash
corepack pnpm dev
```

Open **http://127.0.0.1:5173**. API documentation: **http://127.0.0.1:8000/docs**. Default mode is `demo`; Alembic migrates SQLite and automatically initializes `data/midas.db`. The frontend uses only local assets and its `/api` proxy. Copy `.env.example` to `.env` to customize settings.

Optional container startup uses PostgreSQL and versioned migrations:

```bash
docker compose up --build
```

The dashboard/API ports are the same; PostgreSQL is bound to localhost:54329. Default database credentials are only for this local container setup. Local Docker execution was unavailable in the development environment because socket access was denied; the Compose configuration was validated and PostgreSQL execution is covered by a configured CI job, not a claimed local pass.

## Public observation mode

```bash
MIDAS_MODE=live .venv/bin/uv run uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
```

This discovers up to 100 liquid markets, prioritizes supported top-level CTF binary
markets, monitors up to 20, and records public books and streaming observations. A
finalized Polygon read verifies condition and complementary position identities. Live
mathematical labels are conditional complete-position proofs with explicit collateral,
fee and operational-cost assumptions; fills remain unverified. Unknown versions,
negative risk, absent evidence and stale observations fail closed. Protocol V2 routing
is fixture-tested and live economics remain unsupported. No exchange mutation path exists.

Live books and demo fixtures never share a book state. Scenario results remain labeled SYNTHETIC even when live observations are enabled.

## Demonstration

1. In **Scanner**, open **Synthetic binary • profitable**. Ten YES shares at 0.42 plus ten NO shares at 0.53 cost **9.50 virtual USD**, with **10.00 modeled payout** and **0.50 modeled net profit**. Inspect books, identifiers, fees and the separate risk decision.
2. In **Simulation Lab**, select `profitable`, seed `7`, and run it. Independently arriving virtual legs consume liquidity; settlement credits **0.50 realized virtual USD P&L**. Move the event cursor to inspect reserved/locked cash and unmatched inventory before settlement. Run again: the artifact hash is identical.
3. Select `unprofitable`. The strategy returns `NEGATIVE_EDGE`, the risk gate rejects it, and no virtual fills occur.
4. Select `first_leg_only`. The model initially verifies the complete position, but the venue rejects the second order. The unhedged YES leg loses **4.20 virtual USD** under the supplied NO settlement. The accounting invariants pass because the loss is real within the simulation and reconciles.
5. Select `partial_fills`. After liquidity shrinks, three complete sets and one unmatched share remain before settlement. The timeline shows both quantities explicitly.

These demonstrate model and simulator behavior, **not actual trading profitability**. Persisted history records independent experiments; it does not combine them into a fictional cumulative account return.

The same workflows are available through HTTP:

```bash
curl http://127.0.0.1:8000/api/opportunities
curl -X POST http://127.0.0.1:8000/api/scenarios/profitable/run \
  -H 'Content-Type: application/json' -d '{"seed":7}'
curl -X POST http://127.0.0.1:8000/api/scenarios/first_leg_only/run \
  -H 'Content-Type: application/json' -d '{"seed":7}'
```

Those POSTs modify internal virtual simulation state only.

## Commands

Use `uv` in place of `.venv/bin/uv` when it is on PATH.

```bash
.venv/bin/uv run pytest -q
.venv/bin/uv run ruff check packages apps/api tests infra scripts
.venv/bin/uv run ruff format --check packages apps/api tests infra scripts
.venv/bin/uv run mypy packages/midas apps/api
corepack pnpm format:check
corepack pnpm lint
corepack pnpm typecheck
corepack pnpm test
corepack pnpm build
corepack pnpm --dir apps/web exec playwright install chromium
corepack pnpm test:e2e
.venv/bin/uv run python scripts/replay.py
.venv/bin/uv run python scripts/benchmark.py
```

Browser tests start isolated services on ports 18000/15173 with a temporary database. They cover scanner inspection, profitable simulation, rejected positions, execution loss, event replay, persistent paper controls and model comparisons. Playwright writes screenshots under `docs`. Ordinary checks never require Polymarket availability. The optional real public smoke is separate:

```bash
.venv/bin/uv run python scripts/live_smoke.py
```

For a fresh PostgreSQL or SQLite migration-managed database:

```bash
MIDAS_DATABASE_URL=postgresql+asyncpg://midas:midas_local@localhost:54329/midas \
  .venv/bin/uv run alembic upgrade head
```

Startup adopts a recognized legacy SQLite records-only schema at revision 001 and upgrades it. Back up existing databases before migration. Financial journals are excluded from observation retention.

## API and dashboard

| Interface | Behavior |
| --- | --- |
| `GET /api/state`, `/api/health` | Current mode, observation counts, freshness, integrity, real telemetry and latest independent experiment P&L |
| `GET /api/markets`, `/api/opportunities`, `/api/opportunities/{id}` | Normalized market metadata and exact calculation evidence with independent risk decision |
| `GET /api/paper`, `/api/paper/decisions`, `/api/paper/journal` | Durable shared virtual portfolio, decisions, and event journal |
| `PATCH /api/paper` | Pause/resume paper decisions and select future execution assumptions |
| `GET/POST /api/experiments` | Versioned fault experiments and three-model comparisons; downloadable artifacts |
| `GET /api/scenarios` | 43 reproducible mathematical, execution, infrastructure and risk scenarios |
| `POST /api/scenarios/{id}/run` | Internal scenario execution; bounded two-worker/eight-request admission; seed validation |
| `GET /api/simulations`, `/api/analytics` | Persisted experiment artifacts and provenance-separated observation summaries |
| `GET /api/incidents` | Persisted actual system messages and failures |
| `GET /api/strategies` | Implemented deterministic strategy manifest |
| `GET /api/settings`, `PATCH /api/settings` | Current configuration; toggle persistent paper emergency stop |

Mission Control, Scanner, Simulation Lab, Analytics, Incidents, Telemetry and Settings operate on backend data. Arena exposes the implemented baseline and an honest empty state for future learning systems. No neural training or invented metrics exist.

## Storage and shutdown

Default structured retention is 30 days. Raw recording stops at 100 MB total and visibly reports degraded auditability. Inspect files before explicitly pruning closed segments:

```bash
.venv/bin/uv run python scripts/prune_recordings.py --days 30
.venv/bin/uv run python scripts/prune_recordings.py --days 30 --apply
```

Use Ctrl+C for clean local shutdown. `docker compose down` preserves named volumes; no automatic database wipe occurs. Ports are intended for local trusted access.

## Milestone 2 workflows

The **Paper Trading** page shows durable simulated balances, orders, risk decisions,
ledger events and execution assumptions. The default shared account has 100 virtual
USD/pUSD and a 20-unit trade allocation limit; no SEK conversion is asserted.
`MIDAS_PAPER_CAPITAL` and `MIDAS_PAPER_LIMITS` configure new accounts. Existing accounts
retain their financial configuration across restart. Emergency stop is persistent.

```bash
.venv/bin/python scripts/verify_economics.py
.venv/bin/python scripts/live_paper_smoke.py
.venv/bin/python scripts/paper_lab.py --seed 7 --compare
.venv/bin/pytest tests/integration/test_paper.py -q
.venv/bin/python scripts/paper_benchmark.py
```

The public probes produce traceable economic evaluations and a running paper broker;
zero qualifying trades are a valid outcome. The differential lab uses a labeled synthetic
fixture when real opportunities do not qualify. See the recovery document for a physical
partial-position process-termination demonstration and exact restart commands.

- [Milestone 2 engineering report](docs/MILESTONE_2_ENGINEERING_REPORT.md)
- [Milestone 2 baseline](docs/MILESTONE_2_BASELINE.md)
- [Economic attestation](docs/ECONOMIC_ATTESTATION.md)
- [Paper broker](docs/PAPER_BROKER.md)
- [Execution models](docs/EXECUTION_MODELS.md)
- [Recovery and reconciliation](docs/RECOVERY_AND_RECONCILIATION.md)
- [Milestone 2 test report](docs/MILESTONE_2_TEST_REPORT.md)

## Engineering documentation

- [Engineering report](docs/ENGINEERING_REPORT.md)
- [Architecture and data flow](docs/ARCHITECTURE.md)
- [Current Polymarket research](docs/POLYMARKET_RESEARCH.md)
- [Arbitrage mathematics](docs/ARBITRAGE_MATH.md)
- [Simulation design and approximations](docs/SIMULATION_DESIGN.md)
- [Independent risk model](docs/RISK_MODEL.md)
- [Provenance, replay and retention](docs/DATA_PROVENANCE.md)
- [Architectural decisions](docs/DECISIONS.md)
- [Known limitations](docs/KNOWN_LIMITATIONS.md)
- [Next milestones](docs/ROADMAP.md)
