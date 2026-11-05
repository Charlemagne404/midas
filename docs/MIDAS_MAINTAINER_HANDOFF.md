# MIDAS maintainer handoff

**Verified snapshot:** 2026-11-05, Europe/Stockholm. **Source base before this
maintenance pass:** `origin/main` at
`c00bd128605c85b5c34220efbee54f0993e9b560`. The work was prepared on
`codex/midas-maintenance-20261105`; source integration and deployment are
separate states. Recheck current refs and the host before acting on these dated
observations.

## What MIDAS contains

MIDAS is a Python modular monolith with a FastAPI application, a React Mission
Control interface, deterministic simulations, and research services. It
observes public market data and can maintain a virtual paper account. It has
no real order submission, wallet, private key, or deposit path. A simulation,
recorded observation, virtual paper result, and independent economic audit are
different evidence classes; none establishes real fills or profitability.

| Area | Main responsibility and boundary |
|---|---|
| `packages/midas/core`, `arbitrage`, `economics`, `risk`, `paper`, `simulation` | Contracts, exact arithmetic, risk gates, virtual accounting, deterministic exchange simulation. |
| Market Data and Reality | Read-only public acquisition, raw recording, source quality, reconstruction, replay, and recovery. Reality owns its recordings and research state. |
| Frontier | Separately stored multi-source observations, relationship hypotheses and reviews, bounded replay, and source-use gates. |
| Veritas | Versioned scan and analysis catalogs, independent economics, qualification, and research coordination. It does not rewrite source observations. |
| Laboratory | Deterministic synthetic campaigns and adversarial experiments. |
| Arena | Resource-admitted research jobs, datasets, model evaluation, schedule dispatch, and artifact verification. |
| API and Mission Control | `apps/api` owns application lifecycle, settings, persistence projections, and routes. `apps/web` presents those APIs in one React shell. |
| Readiness and Autonomy | Readiness projects measured state; timers and workers schedule bounded tasks. Neither implies production approval. |

The normal evidence path is public observations into Market Data and Reality;
synthetic inputs into Laboratory and Arena; and separately versioned evidence
into Frontier and Veritas. The API projects these stores to Mission Control.
The detailed subsystem map is in [ARCHITECTURE.md](ARCHITECTURE.md).

## Source history and repository state

- `origin/main` was refreshed to `c00bd128`. The successful hosted run on this
  SHA was GitHub Actions run `42017520116` (four jobs: Python, web, browser,
  and PostgreSQL).
- The maintenance implementation at `2bb3ffa` passed GitHub Actions run
  `42030063692` across all five jobs: Python, web, browser, PostgreSQL, and the
  required systemd unit parser. The isolated backend suite reported 2,185
  passed, 2 skipped, and 0 failed. This handoff records that completed result;
  check current CI for any later branch tip.
- `6aa7c7f00d736d02ee7ca5629d1b9f102e0ae9d9` is the original squash
  integration and is an ancestor of `origin/main`.
- `codex/midas-unification` at `c256cd1b0743d0c3ba6229c0115fd200fa0f014f`
  preserves the original development history, including its 1,196 commits
  that are not ancestors of the squash. The corresponding remote branch is
  retained.
- The local `/home/charlie/midas` checkout is on `main` at
  `b723bfda47dc5fae3103725a1dbe341f35487754`. It is used by live services and
  Vite processes. Do not fast-forward or edit it during ordinary development;
  compare it with current `origin/main` only from a separate task checkout.
- The tags `midas-preservation-baseline-main-20261104` and
  `midas-preservation-baseline-unification-20261104` remain present. On
  2026-11-05, 26 otherwise unreachable commit objects were found and pinned by
  24 local refs under `refs/preservation/orphaned-20261105/`. Those refs are
  local to this repository and are not an independent backup.
- The refreshed inventory contained 62 local branches, 53 `origin` heads, and
  37 worktrees. Nine worktrees had uncommitted source or evidence changes.
  No stale worktree entries were reported by `git worktree prune --dry-run`;
  neither worktrees nor branches were removed. See
  [UNIFICATION_BRANCH_INVENTORY.md](UNIFICATION_BRANCH_INVENTORY.md) for
  per-ref and per-worktree dispositions.

The [unification report](UNIFICATION_REPORT.md) and
[2026-10-29 current-state report](MIDAS_CURRENT_STATE.md) are historical
records. The latter's old “authoritative checkout” language describes its
original snapshot, not today's development baseline.

## Current runtime and data ownership

These services were active when checked. Their working directories and data
are not interchangeable with the maintenance worktree.

| Unit/process | Active source or working directory | Data and observation |
|---|---|---|
| `midas-api.service`, PID 1218662 | API release `a152999`; working directory `/home/charlie/midas` | Open `/home/charlie/midas/data/midas.db`, WAL mode, 16,362,156,032 bytes. The Arena scheduler also uses this checkout and its `data/arena`. |
| `midas-reality-api.service`, PID 610950 | Versioned Reality interface release; working directory `/home/charlie/midas-reality` | Open `data/research/reality/interface/preview.db`, WAL mode, 12,456,755,200 bytes. |
| `midas-reality.service`, PID 2366325 | `/home/charlie/midas-reality` | Owns `data/recordings/reality`; the writer lock and an `.open` segment were active. Recording data was about 23 GiB across 132,311 files. |
| Reality and main Vite processes | `/home/charlie/midas-reality/apps/web` and `/home/charlie/midas` | Both source worktrees are in use; leave their dependencies and files in place. |
| Veritas timers | Versioned observatory release and `/home/charlie/midas-veritas` | Write/read Veritas state under `/home/charlie/midas-veritas/data`. |

The major `data` trees measured about 24.2 GB in `/home/charlie/midas`,
40.6 GB in `/home/charlie/midas-reality`, 2.0 GB in `/home/charlie/midas-veritas`,
1.3 GB in the old engineering-mission worktree, and 4.1 GB in a Reality staging
worktree. These are point-in-time directory sizes, not backup sizes. Other
research artifacts are distributed across the remaining worktrees.

Configuration belongs in `.env.example` for documented local settings,
deployment JSON for service-specific configuration, and systemd templates
under `deploy/systemd/user`. Never copy service secrets into Git. Environment
variables select separate API, Reality, Frontier, Veritas, Arena, Laboratory,
and recording roots; retain those ownership boundaries.

The current host's principal evidence roots are `/home/charlie/midas/data`
(API, paper, Arena, and Laboratory), `/home/charlie/midas-reality/data`
(recordings and Reality research), `/home/charlie/midas-veritas/data`
(Veritas catalogs and analysis), and `/home/charlie/midas-frontier/data`
(Frontier captures and research). Historical experiments also remain under
the engineering-mission and reliability worktrees and in Reality staging
trees. The branch/worktree inventory records their exact locations and Git
status. A clean Git status says nothing about ignored datasets. No complete
machine-readable inventory or independent copy of all these research roots
exists yet.

## Validation status and live blockers

The maintenance implementation passed all five hosted jobs in run
`42030063692`; the backend results were **2,185 passed, 2 skipped, 0 failed**.
The dedicated systemd job required `systemd-analyze` and parsed the generated
user service and timer units, so that check did not silently skip. The focused
backup, recording, Veritas source-analysis, and systemd parser tests passed
locally: **23 passed**. Ruff checks and formatting passed for the changed
Python files. No full backend, browser, or PostgreSQL suite was run locally.

The Veritas source-analysis timer is enabled and is failing repeatedly. The
2026-11-05 journal contains **27 OOM kills since midnight**; the latest run
used 7.551 CPU seconds and ended after 12 seconds with exit status 9 under
`MemoryMax=256 MiB`. The Reality raw root had 58,181 finalized segment
sidecars (23,465,741 bytes total); the last durable analysis state, last
updated 2026-11-04 11:41, records 53,340 processed segments and about 370 KiB
of state. The catalog reader retains path objects and all decoded catalog
dictionaries while it scans the complete source root. At this catalog size
that is a plausible cause of the cap failure, but the worker's peak RSS was
not captured, so it is not proven. A streaming refactor passed fixture tests
but was removed: the existing recovery state includes this source file's
digest, so deploying that refactor unchanged would reject the durable state.
The fix needs a reviewed, versioned state-identity migration and
bounded-memory validation. Keep the 256 MiB service cap; do not launch another
live run or change the timer/limits without a separate resource review.

Some Veritas Mission 2 readers and API lineage checks deliberately pin the
Reality campaign digest and absolute recording/campaign paths under
`/home/charlie/midas-reality`. They preserve source provenance and explain why
the Veritas service is not yet relocatable by changing workspace settings
alone. Relocating those inputs requires a reviewed evidence migration and
matching tests; do not replace the pins with generic defaults casually.

The main API database, Reality interface database, Reality recordings, and
additional research stores have no verified independent backup. A separate
physical disk is mounted at `/mnt/continental-cloud`, but the resource gate
denied even a no-op heavy admission probe: only 24 KiB of swap was free and a
swap-in page occurred during sampling. Capacity passed; swap reserve and swap
activity failed. No live backup or service operation was attempted. The
[backup and recovery guide](BACKUP_AND_RECOVERY.md) records the procedures,
tested disposable formats, and remaining protection gaps.

## Resume development safely

Start from a clean task checkout based on the current `origin/main`, not from
the running `/home/charlie/midas` checkout. Reuse a suitable checkout for a
small change. Add a worktree for actual parallelism or isolation. Before
editing, inspect status, branches, worktrees, and current CI. Group code,
tests, and docs into completed logical commits; avoid progress-only commits
and routine progress reports. Run focused checks, then use hosted isolated CI
for the comprehensive suite.

```bash
git fetch origin
git status --short --branch
git worktree list --porcelain
uv sync --locked --group dev
corepack pnpm install --frozen-lockfile
```

Run a changed backend test with `uv run pytest -q <test-path>`, then relevant
`uv run ruff check`, `uv run mypy`, and frontend checks from
[DEVELOPMENT.md](DEVELOPMENT.md). Tests and frontend runs must use fresh
temporary data roots and local ports. Public probes, timers, campaigns, and
long-running workers do not belong to ordinary development startup.

For systems with `systemd-analyze`, run the user-unit parser test in
`tests/arena/test_schedule_timer_install.py`. Hosted CI has a dedicated job
that first requires the parser, so this test cannot silently skip there.

Source integration, release staging, and deployment are separate states. Use
the [deployment plan](UNIFICATION_DEPLOYMENT_PLAN.md) and a current reviewed
release procedure before touching live services. Green CI is not a
production-readiness claim.

## Actions that need specific review

- Do not casually stop/restart protected API or Reality services, enable
  disabled timers, launch workers, or raise their resource ceilings.
- Do not delete a worktree, branch, recovery ref, ignored dataset, database,
  recording, or staging directory based only on age or a clean Git status.
- Do not run `git clean`, broad pruning, or garbage collection while historical
  refs and data ownership are unresolved. The current old and dirty worktrees
  remain preserved.
- Never copy an active SQLite main file without its WAL. Use the transactional
  snapshot tool and restore to a new location.
- Never treat a current checkout SHA as the loaded release identity, a source
  merge as deployment, or synthetic and paper results as realized outcomes.
