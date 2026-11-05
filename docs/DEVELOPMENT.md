# MIDAS development

**Baseline:** the current, reviewed `origin/main` branch. This guide was
refreshed on 2026-11-05; the exact checkout, runtime, and backup state is in the
[maintainer handoff](MIDAS_MAINTAINER_HANDOFF.md).

The original `/home/charlie/midas` checkout may be behind `origin/main` and is
still used by running services and Vite processes. Do not update or use it for
ordinary code changes. `/home/charlie/midas-unification` preserves the source
history that was squash-integrated into `main`; it is no longer the default
development baseline. Reality and Veritas worktrees still own live services or
data. Read [OPERATIONS.md](OPERATIONS.md) before accessing them. Older
checkpoint-specific commands and results are archived in
[the previous development guide](history/DEVELOPMENT_HISTORY_2026-10-30.md).

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

## Reproducible production release verification — 2026-10-30

The migration resolved the earlier missing-uv evidence. A pinned uv 0.13.6
binary is installed at
/home/charlie/.local/share/midas/toolchains/uv-0.13.6/bin/uv. Python 3.12.3
and the dev plus arena-rl groups were synced against the Python lockfile; the
locked resync resolved 78 records and checked 77 installed packages. The
Python environment lives outside the release at
/home/charlie/.local/share/midas/venvs/b13477e86477eadeccac22ebd84595a808dcd1f9.
The source archive, frontend lock, dist hash, and release manifest identities
are in
[UNIFICATION_PRODUCTION_MIGRATION_REPORT.md](UNIFICATION_PRODUCTION_MIGRATION_REPORT.md).

From the exact release directory, the locked environment can be recreated
without changing another checkout's environment:

    cd /home/charlie/.local/share/midas/releases/b13477e86477eadeccac22ebd84595a808dcd1f9
    UV_PROJECT_ENVIRONMENT=/home/charlie/.local/share/midas/venvs/b13477e86477eadeccac22ebd84595a808dcd1f9 /home/charlie/.local/share/midas/toolchains/uv-0.13.6/bin/uv sync --locked --group dev --group arena-rl
    corepack pnpm install --frozen-lockfile

The release used Node v22.23.4 and Corepack pnpm 10.18.0. Build, lint and
typecheck passed; 78 frontend tests passed in the final serial run. An earlier
frontend test scope was killed by systemd-oomd during memory reclaim; the
bounded rerun passed and the event is documented in the migration report.
The final backend suite collected 2,130 cases but did not complete. The prior
unification closeout counts above remain a separate historical snapshot.

## Branch and integration workflow

First inspect the repository and existing worktrees. Reuse a clean, suitable
development checkout for a small change. Create a separate worktree when
parallel work or isolation actually needs one; do not create branches or
worktrees for trivial edits. Keep running service checkouts and worktrees with
unclassified changes untouched.

For a new task, fetch the current remote refs without pruning preserved refs,
then branch from `origin/main`:

```bash
git fetch origin
git status --short --branch
git worktree list --porcelain
git worktree add -b codex/<task>-YYYYMMDD /home/charlie/midas-<task> origin/main
```

Run focused tests for the changed subsystem and the relevant local lint or
type checks. Group related source, tests, and documentation into commits that
represent completed logical changes. Avoid progress-only commits and routine
progress Markdown. Stage exact paths, inspect the staged diff, and preserve
published history. Use the standard hosted CI for the isolated full suite;
do not run service operations or data-heavy tests against live roots.

Before integration, compare the candidate with the current `origin/main`,
inspect its CI results, and review any concurrent branch or worktree changes.
Source integration, release staging, and deployment are separate states. Use
[UNIFICATION_DEPLOYMENT_PLAN.md](UNIFICATION_DEPLOYMENT_PLAN.md) and the
release owner’s current authorization for service transitions. Do not remove
ambiguous branches, worktrees, or research files during integration.

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
