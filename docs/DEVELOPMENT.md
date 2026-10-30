# MIDAS development

**Authoritative checkout:** /home/charlie/midas-unification

**Branch:** codex/midas-unification

Start future development here. The original /home/charlie/midas checkout
remains on protected main because the API working directory and Arena timer
still use it. Reality and Veritas worktrees also remain as runtime dependencies.
See [OPERATIONS.md](OPERATIONS.md) before accessing installed services or
preserved stores. Older checkpoint-specific commands and results are archived
in [the previous development guide](history/DEVELOPMENT_HISTORY_2026-10-30.md).

## Requirements and install

Python 3.12 or newer, uv, Node 22 or newer, Corepack, and pnpm 10.18.0 are
expected. Python dependencies are pinned by uv.lock; web dependencies are
pinned by the repository-root pnpm-lock.yaml. The full Arena RL dependency set
is the optional `arena-rl` group, including the CPU-only Torch wheel source.

From the repository root:

    uv sync --locked --group dev --group arena-rl
    corepack pnpm install --frozen-lockfile

This creates the checkout-local Python environment and frontend packages. The
production migration used an isolated uv bootstrap and a per-release Python
environment; dependency installation and lockfile verification are recorded
in [UNIFICATION_PRODUCTION_MIGRATION_REPORT.md](UNIFICATION_PRODUCTION_MIGRATION_REPORT.md).
Do not point a development process at a service-owned data path.

Copy .env.example to .env only for local overrides. Use demo mode, temporary
database/artifact roots, and explicit false values for public probe flags. Never
point a development process at a service-owned data path.

## Run an isolated application

Start the API from the repository root. Every mutable store goes under one new
temporary directory. The non-default port avoids the installed API on port 8000.

    midas_dev_root=$(mktemp -d /tmp/midas-dev-XXXXXX)
    export MIDAS_MODE=demo
    export MIDAS_DATABASE_URL=sqlite+aiosqlite:///$midas_dev_root/midas.db
    export MIDAS_ARENA_ROOT=$midas_dev_root/arena
    export MIDAS_LABORATORY_ROOT=$midas_dev_root/laboratory
    export MIDAS_FRONTIER_ROOT=$midas_dev_root/frontier
    export MIDAS_REALITY_WORKSPACE=$midas_dev_root/reality
    export MIDAS_RECORDING_ROOT=$midas_dev_root/recordings
    export MIDAS_VERITAS_WORKSPACE=$midas_dev_root/veritas
    export MIDAS_FRONTIER_POLYMARKET_PUBLIC_PROBE_ENABLED=false
    export MIDAS_FRONTIER_KALSHI_PUBLIC_PROBE_ENABLED=false
    export MIDAS_FRONTIER_KRAKEN_PUBLIC_PROBE_ENABLED=false
    export MIDAS_FRONTIER_COINBASE_PUBLIC_PROBE_ENABLED=false
    .venv/bin/python -m uvicorn apps.api.main:app --host 127.0.0.1 --port 18080

In a second terminal from the repository root:

    MIDAS_API_TARGET=http://127.0.0.1:18080 corepack pnpm dev

The dashboard listens on http://127.0.0.1:5173. The API health route is
http://127.0.0.1:18080/api/health. Stop both development processes before
removing the exact temporary directory created for that run. Do not launch
systemd timers, collectors, campaigns, or production workers during ordinary
development.

## Verification commands

Run focused tests for changed code, then the standard checks:

    .venv/bin/python -m pytest -q tests/frontier
    .venv/bin/ruff check .
    .venv/bin/ruff format --check .
    .venv/bin/mypy packages/midas apps/api
    corepack pnpm lint
    corepack pnpm typecheck
    corepack pnpm test
    corepack pnpm build
    corepack pnpm format:check

The isolated browser suite is:

    corepack pnpm test:e2e

Playwright starts temporary local API/web servers and temporary research roots.
It does not need a live source probe or service data. Install its browser
runtime using the Playwright command documented by the web package when
necessary.

At unification closeout, 748 Frontier tests passed. The latest focused
Reality/recovery/resource and Arena schedule set passed 122 tests. Mypy passed
for 192 source files; Ruff check and formatting passed. Web tests passed 78;
lint, typecheck, build, and 19 browser checks passed with 5 skips. The backend
suite collected 2,119 tests but was stopped after 119 passed in 319.91 seconds
while a synthetic serialization case was still running. The full suite is
therefore partial, not verified. Exact details are in
[UNIFICATION_REPORT.md](UNIFICATION_REPORT.md).

## Branch and integration workflow

Check the starting state before edits:

    git status --short --branch
    git rev-parse HEAD

Create a task branch from the unified branch:

    git switch codex/midas-unification
    git switch -c codex/<short-task-name>

For isolated parallel work, add a named worktree for that branch and record the
path. Do not reuse main, a runtime worktree, or a historical branch as the
development baseline. Before integrating subsystem work, compare unique
commits, working-tree changes, and runtime dependencies. Cherry-pick or port
only reviewed changes; preserve source commit IDs in the integration report.
Do not delete ambiguous evidence, stash unrelated work, or use blanket cleanup.

Run affected tests before committing. Keep integration commits small enough to
review, report any failed or partial checks accurately, then verify a clean
branch status. Use the branch disposition manifest for the current history.

## Research data and operational boundaries

- Store local test databases, campaigns, journals, models, and captures under
  the exact temporary root supplied to the process.
- Keep Reality, Veritas, Frontier, Arena, Laboratory, and paper artifacts in
  their own stores when their ownership or provenance differs.
- Treat ignored and untracked data as preserved until its owner, integrity, and
  dependencies are understood. Never rewrite source observations or prior
  economic results to fit a new schema.
- The browser, API, tests, and read-only catalog routes must not start public
  collection or a long research run implicitly.
- Use the plan in [UNIFICATION_DEPLOYMENT_PLAN.md](UNIFICATION_DEPLOYMENT_PLAN.md)
  for release staging, rollback, and production authorization.
- Check timestamped host/cgroup headroom before bounded replay or research;
  high host memory alone does not prove that a protected worker has headroom.
