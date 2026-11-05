# MIDAS maintainer handoff

**Verified operational snapshot:** 2026-11-05 18:40, Europe/Stockholm.
Memory, swap, pressure, service results, and active database file sizes were
refreshed at 18:40–18:43. The Reality recording count/bytes and wider ignored
research inventory were not re-scanned because the host had active swap and
elevated I/O pressure. The source baseline at the start of this release
readiness pass was `7ab2d0d98d71e32c7ce7a62275afdc8f45402f04`, with all five
hosted CI jobs passing. Source integration and deployment remain separate
states. Recheck current refs and the host before acting on these dated
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

- The Veritas source-analysis implementation is at
  `dcefed29b3d1cbed3baf15ecc1b25cde4c27882e`; it is integrated in `origin/main`
  by normal fast-forward. The handoff and retention clarification are
  documentation-only updates. Check `git rev-parse origin/main` and its latest
  Actions run for the current exact integration SHA and CI result.
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
- The refreshed inventory contains 63 local branches, 55 `origin` heads, 8
  local-only branches, and 37 worktrees. This pass reused the existing
  `/home/charlie/midas-maintenance` worktree and added no worktree. Nine
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

At 18:40, RAM was 15 GiB with 7.3 GiB available and 478 MiB immediately free.
All 4 GiB of swap was occupied, with 52 KiB free. Memory PSI 5-minute
`some`/`full` was 0.27%/0.23%; I/O PSI was 0.60%/0.48%. The first `vmstat`
sample showed 49/53 pages of swap-in/out, followed by two samples with no
swap traffic; those later samples had 7% I/O wait. `/` remained 82% full with
82 GiB free. `/mnt/continental-cloud` had 592 GiB free on `/dev/sda4`, a
separate internal disk on the same host. It is a local recovery copy only,
not protection against host failure.

The latest Veritas source-analysis run failed at 18:40:56 with
`Result=oom-kill`, exit status 9, `MemoryPeak=268435456` (exactly 256 MiB),
and 7.213 seconds CPU time. Its timer is active; the service has no automatic
restart count. The v1 state file still records 53,340 processed of 58,367
catalogs (about 5,027 pending) and was last modified Nov 4 at 11:41. The
campaign and event ledger were not changed by this maintenance pass. The
runtime root cause is confirmed: the loaded v1 `_read_catalogs` materializes
all sidecar paths and decoded metadata before applying the batch limit. The
source fix in main scans sidecars sequentially and retains only the next
bounded batch. It preserves the legacy digest mapping, writes v2 state
atomically, keeps the original v1 file and event ledger, and reconciles an
orphan event idempotently. It remains undeployed and has not touched live
research state.

`midas-reality.service` was active at the prior service check and had 19
historical restarts; 18 `systemd-oomd` kills from Oct 22–Nov 4 were followed
by automatic restarts. The active `midas-reality-capacity.timer` is scheduled
every 30 minutes. Its last recorded service run started at 18:25:44 and timed
out at 18:26:44 (exit signal 15, 3.360 CPU seconds) under `MemoryHigh=160 MiB`,
`MemoryMax=192 MiB`, no swap, and a 60-second deadline. The timer remains
active. The saved capacity report is still builder v5, measured Nov 3 at
14:15; it reports archive inventory/size limits and unknown archive capacity,
and is stale by more than two timer intervals. The loaded v5 path materializes
all sidecars with `manifest()`, then separately stats each segment/catalog for
growth and scans the directory again for total bytes. Low CPU use during the
timeout plus current I/O pressure make metadata/storage contention a likely
runtime contributor; isolated full-store measurements are pending. The release
candidate built on v6 keeps sidecar parsing bounded, caches metadata observed
during inventory, and counts root bytes in that same directory pass. It still
performs a bounded full catalog walk. No live limit, timer, service, report, or
recording was changed. The old
`midas-veritas-gap-detail-v2.timer` is inactive and its service is failed after
134 historical oomd kills; this is not a currently scheduled loop. The 104
failed user units observed at 17:10 were a mixture of historical one-shot,
validation, and completed Arena job units; this is not 104 active restart
loops. The Arena scheduler's empty schedule result is intentional idle
behavior.

The API had nine historical `systemd-oomd` kills during whole-user-slice
pressure; its own cgroup OOM counter was zero and its `MemoryMax` was not the
trigger. The user-slice kills are distinct from per-unit `MemoryMax` events.

Some Veritas Mission 2 readers and API lineage checks deliberately pin the
Reality campaign digest and absolute recording/campaign paths under
`/home/charlie/midas-reality`. They preserve source provenance and explain why
the Veritas service is not yet relocatable by changing workspace settings
alone. Relocating those inputs requires a reviewed evidence migration and
matching tests; do not replace the pins with generic defaults casually.

The main API database and its WAL were 16,528,715,776 and 4,482,592 bytes at
18:42; the Reality interface database and WAL were 12,615,774,208 and
4,317,792 bytes at 18:43. Both are actively written. The main Reality
recordings and ignored research stores have no independently verified backup.
The snapshot/restore tools use SQLite's online backup API and finalized
recording checks, and their disposable tests passed in the previous
maintenance run. No live snapshot was taken: swap remained effectively full,
the host showed swap traffic and I/O pressure, and the previous heavy resource
admission denied work. `restic 0.16.4` is installed, but there is no MIDAS
repository, off-host endpoint, credential, schedule, retention policy, or
external failure alert. The full ignored-data inventory is incomplete. See
[BACKUP_AND_RECOVERY.md](BACKUP_AND_RECOVERY.md) for destination sizing,
verification cadence, and the remaining requirements.

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

## Approval-gated Reality and Veritas release

The following release is prepared but not authorized or executed. CI and
disposable-data checks may be automated; production service control, live
checkpoint migration, database/recording snapshots, timer changes, and release
switches require the owner's explicit approval and a fresh maintenance window.

1. **Pass the preservation and resource gates.** Complete a read-only inventory
   of ignored research roots. Establish and verify an off-host recovery point
   for the main and Reality SQLite databases, Reality recordings, Veritas
   campaign/source inputs, checkpoint and event ledger, and all other required
   research evidence. Verify a restore. Re-run the heavy resource preflight;
   require adequate free swap, no active swap churn, acceptable PSI, disk
   reserve, and protected-service headroom. Current host measurements fail
   these gates and there is no off-host backup.
2. **Record exact release and service ownership.** Capture the loaded
   `ExecStart`, `WorkingDirectory`, environment/root paths, cgroup limits,
   active timer state, current process identity, source release SHA, Veritas
   campaign digest, Reality recorder release, and current capacity report
   digest. Confirm the service is the expected v1 Veritas / v5 Reality
   implementation; checkout HEAD alone is not runtime identity.
3. **Verify the exact live Veritas checkpoint.** After the analysis service is
   inactive and before a timer can start another run, record hashes and sizes
   for `source-analysis-state-v1.json`, the complete
   `source-analysis-events/v1` ledger, `source-research-summary.json`, the
   pinned campaign, and source catalog boundary. Compare them with the
   independent recovery point. Copy that exact checkpoint to a disposable
   isolated root and rerun the v1-to-v2 migration, interruption, restart,
   digest-compatibility, and event-chain checks. A rejected migration must
   leave the v1 checkpoint and ledger unchanged.
4. **Roll Veritas once under approval.** Only after the service has drained,
   pause its timer and install the immutable validated source release. Keep the
   original v1 checkpoint and ledger in place. Run one admitted batch with the
   existing 128-segment / 32-MiB bounds and existing 256-MiB limit. Verify the
   v2 state seal, migration provenance, unchanged v1 hash, event-chain
   continuity, processed cursor, summary digest, and cgroup peak below 256 MiB.
   Do not resume the timer if any value differs or the run fails.
5. **Roll Reality capacity once under approval.** Keep the Reality recorder
   and its schedule unchanged. Install the immutable validated v6 monitor
   release and run one admitted capacity measurement under the existing
   160-MiB high / 192-MiB maximum, no-swap, 60-second policy. Verify completion
   before the deadline, the v6 builder identity, non-stale `measured_ns`,
   `raw_root_bytes`, sample digest, growth windows, archive validation state,
   and capacity alerts against the pre-release evidence. Publish the new report
   atomically only after review.
6. **Verify and resume.** Confirm the services' loaded source paths and hashes,
   `Result=success`, bounded memory, execution duration, and intended timer
   schedule through `systemctl show` and the application API. Check that the
   Veritas processed count advanced exactly by the completed batch and that
   the event ledger has no duplicate or missing event. Check the Reality report
   timestamp and source identity. Resume only the approved timers after these
   checks.
7. **Rollback on any mismatch.** Pause the affected timer after the current
   one-shot has finished; do not kill a writer. Restore the prior immutable
   code release and service definition. Preserve both v1 and v2 checkpoint
   files, all event files, and the pre-release report. If the candidate wrote
   an event or changed a checkpoint, do not start the old analysis against a
   mixed ledger; restore the complete matching checkpoint-plus-ledger recovery
   point or reconcile it offline first. Restore the prior capacity report only
   if its recorded digest matches the saved copy. Verify loaded release and
   service result before any timer resumes.

The rollout is blocked today by full swap, repeated Veritas OOM, the stale v5
capacity report and timeouts, missing independently verified off-host backups,
and an incomplete ignored-data inventory. A green source CI run does not clear
these production gates.

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
