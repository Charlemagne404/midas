# MIDAS maintainer handoff

**Verified operational snapshot:** 2026-11-05 19:57, Europe/Stockholm.
Memory, swap, pressure, service state, and active database sizes were refreshed
between 19:49 and 19:57. The 19:56 Reality capacity timer run naturally timed
out. The Reality recording count/bytes and wider ignored research inventory
were not rescanned because swap is full and research roots are large. The
source baseline for this release readiness pass is
`7ab2d0d98d71e32c7ce7a62275afdc8f45402f04`. Candidate source commit
`7d06ec163b02ed916a881b913c9263c19aed7d80` passed hosted run `42094481010`
across all five jobs. Verify the exact current ref before acting; source
integration and deployment remain separate states. Recheck current refs and
host state before acting on these dated observations.

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
- Release-readiness backend run `42087516960` passed 2,194 tests (2 skipped,
  0 failed; one warning) and the worker lifecycle checks. On 58,367 synthetic
  catalog entries, the pre-streaming reader used 287.0 MiB RSS and 3.56
  seconds; the sequential reader used 175.6 MiB and 3.25 seconds. Under the
  actual 256-MiB, no-swap cgroup, the candidate measured 175.8 MiB process
  peak RSS and 3.02 seconds; cgroup peak was 135,290,880 bytes, with no OOM
  event. Checkpoint migration, legacy digest/provenance, interruption restart,
  idempotent orphan-event reconciliation, and rejected-migration preservation
  are covered by `tests/test_veritas_finalized_source_analysis.py`. This uses
  disposable data; live checkpoint state remains untouched.
- Hosted run `42094481010` for candidate `7d06ec1` passed all five jobs.
  Backend JUnit reported 2,194 passed, 2 skipped, and 0 failed; the two worker
  lifecycle checks also passed. Progressive Veritas reads at 1,000, 10,000,
  25,000, and 58,367 catalogs measured 167.8/186.6/218.7/289.6 MiB RSS for
  the baseline and 166.9/167.7/172.8/175.9 MiB for the sequential reader.
  At 58,367 catalogs, peak RSS fell by 113.7 MiB (39.3%) and runtime went from
  3.48 to 3.21 seconds. The exact 256-MiB no-swap cgroup run used 175.9 MiB
  process RSS and 129.4 MiB cgroup peak, completed in 2.97 seconds, and had no
  OOM kill. Checkpoint migration, provenance, interruption, restart, and
  event-ledger preservation tests passed; live checkpoint state is untouched.
- `6aa7c7f00d736d02ee7ca5629d1b9f102e0ae9d9` is the original squash
  integration and is an ancestor of `origin/main`.
- `codex/midas-unification` at `c256cd1b0743d0c3ba6229c0115fd200fa0f014f`
  preserves the original development history, including its 1,196 commits
  that are not ancestors of the squash. The corresponding remote branch is
  retained.
- The local `/home/charlie/midas` checkout is on `main` at
  `b723bfda47dc5fae3103725a1dbe341f35487754`, 18 commits behind the starting
  `origin/main`. It is a live service working directory. Do not fast-forward
  or edit it during ordinary development; compare it with `origin/main` only
  from a separate task checkout.
- The tags `midas-preservation-baseline-main-20261104` and
  `midas-preservation-baseline-unification-20261104` remain present. On
  2026-11-05, 26 otherwise unreachable commit objects were found and pinned by
  24 local refs under `refs/preservation/orphaned-20261105/`. Those refs are
  local to this repository and are not an independent backup.
- The latest reference count is 64 local branches, 56 fetched `origin` heads,
  8 local-only branches, and 37 worktrees. The release-readiness work was done
  on `codex/midas-release-readiness-20261105`, originally based on `origin/main`
  at `7ab2d0d`; this task reused `/home/charlie/midas-maintenance` and added no
  worktree. The last full
  status audit found nine dirty worktrees. This pass did not repeat an
  all-worktree status scan while swap was full and services were active. No
  worktrees, branches, or research data were removed. See
  [UNIFICATION_BRANCH_INVENTORY.md](UNIFICATION_BRANCH_INVENTORY.md) for the
  earlier per-ref/per-worktree audit and cleanup gates.

The [unification report](UNIFICATION_REPORT.md) and
[2026-10-29 current-state report](MIDAS_CURRENT_STATE.md) are historical
records. The latter's old “authoritative checkout” language describes its
original snapshot, not today's development baseline.

## Current runtime and data ownership

These services were active when checked. Their working directories and data
are not interchangeable with the maintenance worktree.

| Unit/process | Active source or working directory | Data and observation |
|---|---|---|
| `midas-api.service`, PID 1218662 | API release `a152999`; working directory `/home/charlie/midas` | Open `/home/charlie/midas/data/midas.db`, WAL mode, 16,559,865,856 bytes plus a 4,482,592-byte WAL at 19:49. The Arena scheduler also uses this checkout and its `data/arena`. |
| `midas-web.service`, PID 1095134 | Vite release `767f330`; working directory under `/home/charlie/.local/share/midas-api/releases` | Running development UI process; left untouched. |
| `midas-reality-api.service`, PID 610950 | Reality interface release `interface-capacity-v3-20261021`; working directory `/home/charlie/midas-reality` | Open `data/research/reality/interface/preview.db`, WAL mode, 12,645,478,400 bytes plus a 4,317,792-byte WAL at 19:49. |
| `midas-reality-web.service`, PID 2890819 | Vite under `/home/charlie/midas-reality/apps/web` | Running Reality development UI; left untouched. |
| `midas-reality.service`, PID 2366325 | `/home/charlie/midas-reality` | Owns `data/recordings/reality`; recorder process is active. The last measured inventory found 58,367 finalized segment/sidecar pairs totaling 19,739,677,482 segment bytes; it was not rescanned during this pass. |
| Veritas source-analysis timer | Script in `/home/charlie/midas-veritas`, Python environment from `/home/charlie/midas/.venv` | Reads `/home/charlie/midas-veritas/data/veritas-observatory`, with 128-segment and 32-MiB batch bounds. Its latest timer run OOM-killed. |
| Reality capacity timer | `midas.reality.operations` from `/home/charlie/midas-reality` | Reads the active recording tree and archive policy; its latest timer run timed out. |

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

At 19:49, RAM was 15 GiB with 7.1 GiB available and 621 MiB immediately free.
All 4 GiB of swap remained occupied, with 236 KiB free. Three `vmstat` samples
showed swap-in/out only in the first sample (49/53 pages), followed by no swap
traffic; CPU idle was 80–86% and I/O wait about 1%. Memory PSI 5-minute
`some`/`full` was 0.02%/0.01%; I/O PSI was 0.72%/0.55%. `/` was 82% full with
82 GiB free. `/mnt/continental-cloud` had 592 GiB free on `/dev/sda4`, a
separate internal disk on the same host. It can hold a local recovery copy but
cannot protect against host failure.

The top process sample included the active Reality recorder at about 723 MiB,
the MIDAS API at about 160 MiB, and an unrelated long-lived headless browser
process at about 1.49 GiB. Its owning task was not established; it was not
stopped or modified. Five MIDAS user services were running (API, main web,
Reality API, Reality web, recorder); these services and their processes were
left untouched.

The latest Veritas source-analysis run failed at 19:40:56 with
`Result=oom-kill`, exit status 9, 7.393 seconds CPU time, and a 256-MiB
`MemoryMax`; the unit has `Restart=no`, while its timer remains active. The
journal contains 64 OOM-kill entries since Nov 4 00:00. The v1 state still
records 53,340 processed of 58,367 catalogs (about 5,027 pending), last
observed in the earlier state check. The campaign and event ledger were not
modified by this maintenance pass. The confirmed root cause is that the
loaded v1 `_read_catalogs` materializes all sidecar paths and decoded metadata
before applying the batch limit. The consolidated reader in `origin/main`
scans sidecars sequentially and retains only the next bounded batch. It
preserves the legacy digest
mapping, writes v2 state atomically, keeps the original v1 file and event
ledger, and reconciles an orphan event idempotently. It remains undeployed and
has not touched live research state.

`midas-reality.service` was active and had 19 historical restarts, including
18 `systemd-oomd` kills through Nov 4. The active capacity timer is scheduled
every 30 minutes. Its latest attempt started at 19:56:04 and timed out at
19:57:04 (exit signal 15, 3.593 CPU seconds, 176.8 MiB peak) under
`MemoryHigh=160 MiB`, `MemoryMax=192 MiB`, no swap, and a 60-second deadline.
The timer remains active. The service journal contains 81 timeout entries
since Nov 4 00:00. The saved capacity report is still builder v5, measured Nov
3 at 14:15; it reports archive inventory/size limits and unknown archive
capacity, and is stale by more than two timer intervals. The loaded v5 path
materializes all sidecars with `manifest()`, then separately stats each
segment/catalog for growth and scans the directory again for total bytes. The
timeouts consume only about 3.4–3.6 CPU seconds per minute, suggesting most
elapsed time is spent waiting on metadata or storage I/O. The current host
sample had low CPU wait, so live storage behavior still requires observation.
Hosted run `42094481010` compared active v5, the exact v6 source at
`origin/main`, and the candidate under the existing 160-MiB `MemoryHigh`,
192-MiB `MemoryMax`, no-swap, one-CPU, 60-second service envelope. All three
produced the same source sample, growth metrics, raw-root bytes, and alert
semantics at each scale; only container-local free space and its derived
headroom/time estimate varied. The benchmark excludes only those three
environment-dependent fields from semantic equality:

| Catalogs | v5 runtime / RSS | main v6 runtime / RSS | candidate runtime / RSS / cgroup peak |
|---:|---:|---:|---:|
| 1,000 | 0.61 s / 28.5 MiB | 0.61 s / 27.9 MiB | 0.60 s / 27.5 MiB / 18.5 MiB |
| 10,000 | 1.20 s / 46.9 MiB | 1.17 s / 37.3 MiB | 1.01 s / 42.2 MiB / 33.1 MiB |
| 58,367 | 4.49 s / 140.3 MiB | 4.19 s / 87.8 MiB | 3.37 s / 121.5 MiB / 112.4 MiB |

At full catalog count the candidate was 25% faster than v5 and 20% faster than
main v6. It used 18.8 MiB less process RSS than v5, but 33.7 MiB more than
main v6 because it retains inventory metadata to avoid repeat stats. That
tradeoff stayed below `MemoryHigh`; there were no OOM events, and the
candidate completed well inside 60 seconds. The fixture has 58,367 sidecars
but only about 64 MB of root data; it does not reproduce the production
recording payload or storage-device latency. A one-shot measurement on the
production tree under existing limits remains a required post-deployment gate.
The release candidate built on v6 keeps sidecar parsing bounded, caches
metadata observed during inventory, and counts root bytes in that same
directory pass. It still performs a bounded full catalog walk. No live limit,
timer, service, report, or recording was changed. The old
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

The main API database and its WAL were 16,559,865,856 and 4,482,592 bytes at
19:49; the Reality interface database and WAL were 12,645,478,400 and
4,317,792 bytes at 19:49. Both are actively written. The main Reality
recordings and ignored research stores have no independently verified backup.
The snapshot/restore tools use SQLite's online backup API and finalized
recording checks, and their disposable tests passed in the previous
maintenance run. No live snapshot was taken: swap remained effectively full
and the previous heavy resource admission denied work. `restic 0.16.4` is
installed, but there is no MIDAS
repository, off-host endpoint, credential, schedule, retention policy, or
external failure alert. The full ignored-data inventory is incomplete. See
[BACKUP_AND_RECOVERY.md](BACKUP_AND_RECOVERY.md) for destination sizing,
verification cadence, and the remaining requirements.

## Monitoring added in the release candidate

The Reality API now projects capacity-report age as `fresh`, `stale`,
`unavailable`, or `clock_uncertain` without rewriting the saved report. The
Reality and Readiness screens label stale measurements with their last
measurement time. The read-only Operations view includes current service and
timer state, last result/exit, restart count, memory/CPU fields, and last/next
trigger times for Reality and Veritas source analysis. A timeout or OOM result
is visible in the latest unit status and regression-tested. This is not a
persistent failure-streak counter or an external alert channel; the counts
above were recovered from the service journal. Backup expiry/failure
monitoring remains unconfigured because no MIDAS backup repository exists.
The future backup schedule must report last-success age and failures outside
the source host.

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
