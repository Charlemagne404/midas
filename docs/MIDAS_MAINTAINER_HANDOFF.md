# MIDAS maintainer handoff

**Verified snapshot:** 2026-11-05 16:31, Europe/Stockholm. **Source base before
this operational resilience pass:** `origin/main` at
`3e700b9b2bba7a9da1564e3ab8b2e18be2eba6ea`, whose five hosted CI jobs passed.
This work is on `codex/midas-operational-resilience-20261105`; source
integration and deployment are separate states. Recheck current refs and the
host before acting on these dated observations.

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

- `origin/main` is `3e700b9b2bba7a9da1564e3ab8b2e18be2eba6ea`; its five hosted CI
  jobs passed before this operational resilience work began.
- The prior maintenance implementation at `2bb3ffa` passed GitHub Actions run
  `42030063692` across all five jobs: Python, web, browser, PostgreSQL, and the
  required systemd unit parser. The isolated backend suite reported 2,185
  passed, 2 skipped, and 0 failed.
- The Veritas streaming, migration, and summary fixes are at
  `dcefed29b3d1cbed3baf15ecc1b25cde4c27882e`. Hosted run `42054636224` passed
  all five jobs: Python, web, browser, PostgreSQL, and the required systemd
  parser. Backend JUnit reported 2,189 passed, 2 skipped, and 0 failed; the two
  worker lifecycle checks also passed. On 58,367 synthetic catalog entries,
  isolated peak RSS fell from 287.4 MiB on the pre-fix reader to 175.9 MiB on
  the streaming reader, a 111.5 MiB reduction. The new reader retained 128
  entries and stayed below the existing 256 MiB service limit. This validates
  the source code only; no live state was migrated.
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
- The refreshed inventory now contains 63 local branches, 54 `origin` heads,
  and 37 worktrees (one maintenance branch added; no new worktree). Nine
  worktrees had uncommitted source or evidence changes.
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
| `midas-api.service`, PID 1218662 | API release `a152999`; working directory `/home/charlie/midas` | Open `/home/charlie/midas/data/midas.db`, WAL mode, 16,422,002,688 bytes plus a 4,482,592-byte WAL. The Arena scheduler also uses this checkout and its `data/arena`. |
| `midas-reality-api.service`, PID 610950 | Versioned Reality interface release; working directory `/home/charlie/midas-reality` | Open `data/research/reality/interface/preview.db`, WAL mode, 12,513,951,744 bytes plus a 4,317,792-byte WAL. |
| `midas-reality.service`, PID 2366325 | `/home/charlie/midas-reality` | Owns `data/recordings/reality`; the writer lock and one `.open` segment were active. There were 58,367 finalized segment/sidecar pairs totaling 19,739,677,482 segment bytes. |
| Reality and main Vite processes | `/home/charlie/midas-reality/apps/web` and `/home/charlie/midas` | Both source worktrees are in use; leave their dependencies and files in place. |
| Veritas timers | Versioned observatory release and `/home/charlie/midas-veritas` | Write/read Veritas state under `/home/charlie/midas-veritas/data`. |

The latest measured `data` trees were about 23 GB in `/home/charlie/midas`,
38 GB in `/home/charlie/midas-reality`, 1.9 GB in `/home/charlie/midas-veritas`,
17 MB in `/home/charlie/midas-frontier`, 1.3 GB in the old
engineering-mission worktree, and 4.1 GB in a Reality staging worktree. These
point-in-time sizes total about 68.3 GB and exclude research data not included
in that scan; they are not a complete backup inventory.

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

## Current operational assessment and blockers

At the 16:31 host sample, RAM was 15 GiB with 7.4 GiB available; all 4 GiB of
swap remained used, with 208 KiB free. Five-minute memory PSI was 2.04%/1.78%
for `some`/`full`; I/O PSI was about 0.7%. The first `vmstat` sample showed
swap-in/out, while the next two had none; CPU idle was 80–81% with 1% I/O wait.
`/` was 82% full with 82 GiB free; `/mnt/continental-cloud` had 592 GiB free
on a separate internal SATA disk. It is a same-host copy, not off-host
protection. An unrelated Echo Archives headless browser (PID 2574398) was
using about 1.50 GiB RSS and 63% CPU after running for over a day; it was left
alone.

The Veritas source-analysis timer remains enabled and failing. The kernel
recorded **33 cgroup OOM kills on 2026-11-05**, the latest at 16:10, under its
256 MiB service limit.
Each run reaches roughly 260 MiB anonymous RSS plus about 19–51 MiB file RSS
before the kernel kills it. The catalog contains 58,367 finalized sidecars;
the last durable state still records 53,340 processed segments, leaving about
5,027 pending. Root cause is confirmed: `_read_catalogs` builds a path object
and decoded metadata dictionary for every catalog before the batch-size limit
is applied. The source-only fix in this branch scans one JSON catalog at a
time, keeps only names plus the next bounded batch, and migrates the known v1
checkpoint into a v2 state file while retaining the v1 file and event ledger.
It has not been deployed or run on live research data. Keep the memory cap and
the live state untouched until review and an approved deployment.

`midas-reality.service` is active now but has 19 historical restarts; 18
`systemd-oomd` kills from Oct 22–Nov 4 were followed by automatic restarts.
Its current cgroup used about 733 MiB, with a 1.13 GiB peak and a 1.25 GiB
limit. The active `midas-reality-capacity.timer` also fires every 30 minutes;
the capacity service hit its 60-second timeout on six consecutive runs from
13:54 through 16:25 on Nov 5, consuming only about 3.4 CPU seconds in the
latest run. Those failures leave the capacity report stale. The monitor
traverses the full 58k finalized catalog and needs isolated profiling; no
timer, unit, or resource ceiling was changed. The old
`midas-veritas-gap-detail-v2.timer` is inactive and its service is failed after
134 historical oomd kills; this is not a currently scheduled loop. The 98
failed user services observed were historical one-shot or validation units,
not 104 active restart loops. The Arena scheduler's empty schedule result is
intentional idle behavior.

The API had nine historical `systemd-oomd` kills during whole-user-slice
pressure; its own cgroup OOM counter was zero and its `MemoryMax` was not the
trigger. The user-slice kills are distinct from per-unit `MemoryMax` events.

Some Veritas Mission 2 readers and API lineage checks deliberately pin the
Reality campaign digest and absolute recording/campaign paths under
`/home/charlie/midas-reality`. They preserve source provenance and explain why
the Veritas service is not yet relocatable by changing workspace settings
alone. Relocating those inputs requires a reviewed evidence migration and
matching tests; do not replace the pins with generic defaults casually.

The main API database, Reality interface database, Reality recordings, and
additional research stores have no verified independent backup. The backup
and restore tools support consistent SQLite snapshots and finalized recording
stores, and their disposable tests passed in the previous maintenance run. No
live snapshot has been taken: the heavy resource gate previously denied work
for the full swap and observed swap activity. `restic` is installed, but no
MIDAS repository, off-host endpoint, credential, schedule, retention policy, or
alert is configured. The `/mnt/continental-cloud` partition is an extra local
disk only. See [BACKUP_AND_RECOVERY.md](BACKUP_AND_RECOVERY.md) for exact
commands, known data sizes, and the off-host prerequisites.

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
that first requires the parser, so this test cannot silently skip there. The
offline backend suite also skips its PostgreSQL paper recovery test when no
PostgreSQL URL is set; the separate PostgreSQL job runs that recovery check.

Source integration, release staging, and deployment are separate states. Use
the [deployment plan](UNIFICATION_DEPLOYMENT_PLAN.md) and a current reviewed
release procedure before touching live services. Green CI is not a
production-readiness claim.

## Non-blocking CI maintenance signals

Hosted runs pass, but GitHub currently reports that several action tags target
Node 20 and are being forced to run on Node 24. Upgrade those action majors
after checking compatibility. The backend run also reports a
Starlette/httpx `TestClient` deprecation warning; review it with the next
dependency refresh rather than suppressing it.

## Veritas source-analysis rollout gate

The source-only fix does not change the active observatory release or timer.
Before any rollout, identify the service's exact loaded release and verify its
analysis code digest against the v1 compatibility manifest. Require a
resource-admission pass and an independently verified backup of the v1 state,
event ledger, campaign inputs, and source evidence. Exercise the migration on
a disposable copy of that exact checkpoint. During an explicitly approved
cutover, serialize timer invocations, install the new immutable release, and
run one controlled analysis;
verify the v2 state seal and migration provenance, unchanged v1 file, event
chain, processed cursor, summary, and peak memory below the existing limit
before allowing scheduled retries to resume. If any prerequisite is missing,
leave the timer and state untouched.

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
