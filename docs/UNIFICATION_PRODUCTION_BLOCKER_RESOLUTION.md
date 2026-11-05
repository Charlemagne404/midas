# MIDAS production blocker resolution

**Mission status: ENGINEERING IMPROVED; PRODUCTION CUTOVER NOT READY.**
Read-only investigation and bounded validation were completed on 2026-10-30.
The live API, Arena timer, web app, Reality recorder, Veritas timers, and their
data were not stopped, restarted, edited, or redirected.

## A. Verified starting state

The authoritative checkout is `/home/charlie/midas-unification`, branch
`codex/midas-unification`. At mission start its HEAD was
`5237269821e5a6c3d54a3a92e76a0bc850a1f3b5`, containing application release
source `b13477e86477eadeccac22ebd84595a808dcd1f9` as an ancestor. The release
is staged at
`/home/charlie/.local/share/midas/releases/b13477e86477eadeccac22ebd84595a808dcd1f9`
with its matching Python environment. This mission's tooling, timer template,
and report are local changes on the unification branch; they do not change the
application release source. The separate `/home/charlie/midas` checkout had
pre-existing dirty files and was left untouched.

At the read-only runtime check:

| Owner | Observed runtime | Durable boundary |
|---|---|---|
| API | `midas-api.service`, PID 1218662, old release `a1529991a880965a8ad37a7528e2c4cabfc341d8`, `127.0.0.1:8000`; health `READY`, mode `demo`, `live_execution=false` | `/home/charlie/midas/data`, including SQLite, Arena, Laboratory, paper and research records |
| Web | Existing release `767f330`, `127.0.0.1:5173` | No separate database; uses the API |
| Arena | Existing minutely `midas-arena-scheduler.timer`; its service runs the old checkout script | `/home/charlie/midas/data/arena` |
| Reality recorder | Protected PID 1235804 from `/home/charlie/midas-reality`; no transition attempted | `/home/charlie/midas-reality/data` |
| Reality interface | Separate API on 8010 and web on 5180 | Reality workspace and preview state |
| Veritas | Observatory, Research Director and source-analysis timers; Observatory release `e988cbb0af86fe89e07da9af8036598b65068deb`; source-analysis uses a frozen-runtime overlay | `/home/charlie/midas-veritas/data` |

The active SQLite file is `/home/charlie/midas/data/midas.db`; the API held
open descriptors for the database, WAL, and SHM. At 2026-10-30 21:42:54 UTC
the main file was 12,589,813,760 bytes, WAL 4,482,592 bytes, and SHM 32,768
bytes; the writer continued changing WAL metadata after that sample. The API
health endpoint reported 899,583 paper journal events and revision 899,582 at
the later read-only sample. It does not expose the active Alembic revision.
No SQLite connection was opened against the live database by this mission; no
production backup, checkpoint, integrity scan, or restore was attempted.

The historical file
`/home/charlie/midas/data/backups/midas-before-milestone2-1791742584.db` is
not a current-production backup. The file as actually inspected was 11,259,904
bytes, contained 4,495 records and only the unversioned `records` table. The
older `docs/MILESTONE_2_LOCAL_RUNTIME_EVIDENCE.json` describes that filename
as a 4,892-record schema-002 demo snapshot with 32 paper events. The mismatch
shows why historical backup notes cannot establish current file contents.
The inspected file is synthetic legacy test material only.

## B. Engineering changes

| Change | Purpose and verification |
|---|---|
| `scripts/midas_resource_preflight.py` | Adds fail-closed `check` and serialized `run` profiles. Checks MemAvailable, swap reserve/activity, memory/CPU/I/O PSI, user-manager pressure and OOM counters, API and Reality cgroup headroom, active MIDAS worker services, storage reserve, task cgroup limits, duplicate-run lock, and finite task timeout. Runs tasks in a transient systemd scope with explicit `MemoryHigh`, `MemoryMax`, no swap, CPU and I/O limits; timeout cancels the scope. |
| `scripts/midas_sqlite_snapshot.py` | Adds online SQLite backup through `Connection.backup`, manifest and checksums, source/WAL metadata, quick/full integrity checks, no-replace publication, isolated restore, and conservative stale-partial cleanup. It refuses large snapshots unless the heavy profile and `--allow-large` are both present. It never copies a live main database file while ignoring the WAL. |
| `scripts/midas_candidate_db_smoke.py` | Adds a repeatable two-start API check against a restored database under a finite resource scope. It refuses production DB paths and symlinks, confines candidate state to an isolated root, checks schema/readiness/routes, and hashes the pre-existing record prefix so expected demo writes cannot mask changed history. |
| `scripts/compare_api_contracts.py` | Compares the live loopback API's OpenAPI document with the candidate release, including path/methods, existing request/response/security fields, and component schema changes. Candidate app is imported without starting its lifespan. |
| `deploy/systemd/user/midas-arena-scheduler-release@.service` and `.timer` | Adds a versioned Arena dispatcher unit and timer using the candidate release and Python environment while retaining the existing Arena data root. It keeps the one-minute schedule, single-dispatcher lock behavior, memory ceiling, no-swap policy, and low I/O priority. It is not installed or activated. |
| Focused tests | `tests/test_midas_resource_preflight.py`, `tests/test_midas_sqlite_snapshot.py`, `tests/test_api_contract_diff.py`, `tests/test_midas_candidate_db_smoke.py`; Arena dispatcher regression tests are also part of the final validation list. |

## C. Host stabilization and database safety

### Host measurements and cause

At the 2026-10-30 21:36 UTC sample, physical RAM was 16.27 GB, available RAM
about 9.18 GiB, anonymous pages 4.54 GiB, page cache about 5.91 GiB, and
reclaimable slab about 1.54 GiB. Swap was 4 GiB total with about 5.3 MiB free.
`Committed_AS` was 22.7 GiB against a 11.76 GiB `CommitLimit`; overcommit mode
was `0` with ratio `50`. This is virtual commitment accounting and does not
mean the same amount is resident or that the host is currently thrashing.

Memory PSI some/full were 0% avg10/avg60/avg300 in the same sample. CPU PSI
some was 2.44% avg10 and 5.55% avg300, with no CPU full stall. I/O PSI
some/full were about 1.06%/1.06% avg10. Two-second vmstat samples during most
bounded runs showed no swap-in or swap-out; one sample caught one page-in.
That transient did not coincide with memory PSI. The bounded profile permits
at most eight pages of swap movement per two-second sample; the heavy profile
requires none and at least 256 MiB of free swap.

The user-manager cgroup had no finite `MemoryHigh` or `MemoryMax`, held about
9.8 GiB, and had cumulative `memory.events` counters of 19 OOM events and 15
OOM kills. The active API cgroup held about 561 MB (`MemoryHigh=1536 MiB`,
`MemoryMax=1792 MiB`, swap disabled); process RSS was about 161 MiB, of which
about 139 MiB was anonymous, while the API cgroup charged about 405 MB of
inactive file cache. The Reality cgroup held about 1.21 GB with
`MemoryHigh=1152 MiB`, `MemoryMax=1280 MiB`, swap disabled; the process RSS was
about 584 MiB, with about 570 MiB anonymous and about 588 MB file cache charged
to the cgroup. Its remaining headroom to `MemoryHigh` was under 2 MiB. Python
heap profiling was not performed; RSS and cgroup accounting are not a heap
allocation profile.

The systemd-oomd journal records the Oct 30 isolated frontend-test scope being
killed after user-slice memory pressure reached 58.40%, above its 50% threshold
for more than 20 seconds with reclaim activity. The effective duration default
is 20 seconds. The event was in a transient development/test scope, not a
production API or recorder kill. The same event inventory showed concurrent
desktop, browser, development, API and Reality memory use; this is shared-host
competition, not evidence that the production API caused that test-scope
incident. The prior Oct 28 API/Reality OOMD restart history remains relevant.
No new kernel OOM line appeared in the bounded Oct 29–30 query. Unrelated
services were not stopped or signaled.

### Admission results

The new runner admitted formatter/lint and focused tests with `MemoryHigh=256
MiB`, `MemoryMax=384 MiB`, `MemorySwapMax=0`, and 25% CPU quota. The restored
candidate check used `MemoryHigh=768 MiB`, `MemoryMax=1024 MiB`, no swap, and
25% CPU quota. Memory PSI remained zero and task cgroup OOM counters remained
zero after those runs. A timeout simulation returned 124, and its `sleep 30`
child and transient scope were gone after cancellation.

A heavy admission simulation for the live database, with estimated 12,500 MiB
of output and 5,120 MiB reserve, was denied before the child command started.
Blocking reasons were less than 64 MiB of protected Reality `MemoryHigh`
headroom and less than 256 MiB of free swap. Therefore no production-scale
backup was attempted. Free RAM and storage alone do not override those gates.

### Backup and restore evidence

The online backup tool was exercised on the inspected 11.26 MB legacy fixture.
It created a standalone `DELETE`-journal snapshot of 11,259,904 bytes with
SHA-256
`b5fd5f1281a081238a353efa78dfaa496977edccd32717d23529d4a00ddd696f`.
Full `PRAGMA integrity_check` returned `ok`; manifest and database hashes
verified; an isolated restored copy had the same checksum and passed full
integrity check. The source fixture had no WAL, so the WAL-safe live-writer
path was separately exercised by unit tests using an active WAL fixture; those
tests verified committed state in the backup and that the source WAL was not
shrunk/checkpointed by the backup routine.

This validates procedure mechanics on small representative formats, not
12.58 GB throughput, production RTO, current WAL state, or current production
restore. The exact remaining data blocker is a heavy-profile online snapshot
of the live database followed by verified isolated restore and full candidate
startup against that restored copy. Do not substitute the stale synthetic
fixture for that work.

## D. Unified API, Arena, and web compatibility

The old API currently serves 76 OpenAPI paths / 81 path-method pairs. The
candidate exposes 136 paths / 141 path-method pairs. The structural diff
found 60 added path-method pairs and 35 added schemas, with no removed route,
no changed existing request/response/security/server field, and no changed or
removed existing schema or shared component. This is additive contract evidence; it is not an
end-to-end browser proof against the live API. The new web build requires the
additional candidate routes, so a web-only switch remains invalid. Pair the
candidate web with its candidate API. Because the old operations remain in the
candidate OpenAPI contract, the existing web can remain until the candidate
web is ready, subject to live smoke and service ordering.

The installed API and candidate have identical `apps/api/paper.py` and
identical Alembic revision files 001–003. The candidate adds schema-version
logging in `storage.py` and relocates runtime scratch files through
`MIDAS_RUNTIME_ROOT`. Those source comparisons reduce the rollback surface,
but do not replace a production-sized restore rehearsal. The active old API
health endpoint does not publish its current Alembic revision.

The active dispatcher and unified dispatcher are not identical. The unified
version adds a persisted cursor and pass sequence, caps each pass at 100
schedules, skips terminal work without importing the Arena model stack, and
handles malformed or symlinked manifests as errors instead of silently
trusting them. It uses the same `scheduler.lock` lease path to prevent two
dispatchers from running concurrently. The candidate dispatcher modifies the
shared Arena schedule root, so no Arena migration or rollback is declared
verified until it is tested on a consistent isolated copy of current schedule
state. The new release timer template is staged only.

The clean legacy database rehearsal used two candidate API starts. Each
reached `READY`, reported schema `003`, `live_execution=false`, and returned
HTTP 200 from 15 core read-only GET routes. The release exposed 136 OpenAPI
paths. All 4,495 pre-existing record rows were preserved exactly by a prefix
hash. Demo startup appended 50 new rows, each explicitly labeled
`SYNTHETIC`; the second start reported `CHECKPOINT_VERIFIED` paper recovery.
Those writes are visible and expected for demo mode. The rehearsal used a
synthetic 11 MB database, not production-sized history.

The previous release validation also passed the isolated frontend build,
lint/typecheck, browser smoke (19 passed, 5 skipped; 2 seeded checks passed),
and 128 backend integration checks. These are candidate-release results from
the prior migration report, not a new complete regression run in this mission.
The requested full backend suite previously collected 2,130 tests and did not
complete; no full-suite pass is claimed.

## E. Reality, Veritas, Frontier, and research services

Reality recorder identity remains PID 1235804 on its original source and
configuration. At the latest memory sample its cgroup had less than 2 MiB of
headroom to `MemoryHigh`; this alone blocks heavy concurrent recovery work.
The previous staged release/configuration remains an accepted static
candidate, but this mission did not run a recorder canary, inspect or repair
the live recording root, certify archive provenance, or test full-store
recovery. Source sequencing and gap evidence remain separate from freshness.
The service is **BLOCKED BY AUTHORIZATION** for any stop, restart, signal,
replacement, or reconfiguration, even if technical gates later pass.

Veritas remains on its existing scheduled services and worktree roots. The
source-analysis unit includes a frozen-runtime package overlay; a source
analysis one-shot was active during final host inventory. No candidate was
started against Veritas catalogs or immutable campaigns, and no overlay was
removed or replaced. The unified code has Veritas and Research Readiness
interfaces, but historical-worktree data compatibility remains
**IMPLEMENTED, VERIFICATION PENDING**. Existing timers and frozen evidence
remain unchanged.

All Frontier public probes remain disabled in the staged release. No new
Frontier source, collector, campaign, or trading activity was started. The
candidate routes for Frontier, Observatory, Laboratory, Arena, Reality,
Veritas, Research Director, telemetry/incidents, and readiness are available
in the candidate API; the remaining items requiring live or historical state
are conditions in the deployment matrix below.

## F. Verification record

| Command or operation | Result |
|---|---|
| `ruff check` on the four operational scripts and their focused tests | Passed: “All checks passed!” |
| `pytest -q tests/test_midas_resource_preflight.py tests/test_midas_sqlite_snapshot.py tests/test_api_contract_diff.py tests/test_midas_candidate_db_smoke.py tests/arena/test_dispatch_schedules.py` | Passed: 26 tests in 2.39 s; run in 512/768 MiB bounded scope, no task OOM events |
| WAL snapshot unit fixture | Passed; snapshot included committed WAL-backed state, source WAL was not checkpointed/shrunk |
| Legacy snapshot `backup`, `verify`, `restore` with `--integrity full` | Passed; full integrity `ok`, source/restore SHA-256 matched |
| `midas_candidate_db_smoke.py ... --cycles 2` on the restored 4,495-record fixture | Passed; 2 ready starts, 15/15 GET routes returned 200 on each, schema remained 003, old record prefix hash preserved, only synthetic additions |
| `compare_api_contracts.py` against `http://127.0.0.1:8000/openapi.json` | Completed; additive 60 path-method pairs and 35 schemas, no existing operation, schema, security, server, or shared-component changes; result `COORDINATED_CUTOVER_REQUIRED` |
| `systemd-analyze --user verify /tmp/midas-arena-unit-verify-b13477e86477eadeccac22ebd84595a808dcd1f9/midas-arena-scheduler-release@b13477e86477eadeccac22ebd84595a808dcd1f9.service /tmp/midas-arena-unit-verify-b13477e86477eadeccac22ebd84595a808dcd1f9/midas-arena-scheduler-release@b13477e86477eadeccac22ebd84595a808dcd1f9.timer` | Passed; instantiated copies were under `/tmp`, not installed |
| Bounded cancellation simulation (`sleep 30`, 2-second timeout) | Returned 124; child and scope absent after cancellation |
| Heavy admission simulation for the live DB | Correctly denied before command start due Reality headroom and swap-reserve gates |
| Full backend suite | Not run in this mission; prior run collected 2,130 and did not complete |
| Live production database backup, restore, candidate startup, or write test | Not run; the heavy gate denied it |
| Reality/Veritas production data canary | Not run; protected recorder boundary and active Veritas worker preserved |

The machine-readable candidate contract diff and restored database evidence
were kept under `/tmp/midas-contract-validation-20261030/`; they are temporary
validation artifacts, not release inputs. The snapshot tool's committed tests
are the durable repeatable WAL/restore checks.

### Reproduction commands

Focused offline tooling and Arena dispatcher validation (the exact test list
is the one shown above) was run through the bounded runner:

```bash
/home/charlie/midas/.venv/bin/python scripts/midas_resource_preflight.py run \
  --label final-contract-expanded-validation --profile bounded-test \
  --memory-budget-mib 384 --storage-path /tmp --storage-reserve-mib 0 \
  --memory-high-mib 512 --memory-max-mib 768 --cpu-quota-percent 25 \
  --timeout-seconds 180 -- /bin/bash -c '
  /home/charlie/midas/.venv/bin/ruff check scripts/midas_resource_preflight.py scripts/midas_sqlite_snapshot.py scripts/compare_api_contracts.py scripts/midas_candidate_db_smoke.py tests/test_midas_resource_preflight.py tests/test_midas_sqlite_snapshot.py tests/test_api_contract_diff.py tests/test_midas_candidate_db_smoke.py tests/arena/test_dispatch_schedules.py &&
  /home/charlie/midas/.venv/bin/ruff format --check scripts/midas_resource_preflight.py scripts/midas_sqlite_snapshot.py scripts/compare_api_contracts.py scripts/midas_candidate_db_smoke.py tests/test_midas_resource_preflight.py tests/test_midas_sqlite_snapshot.py tests/test_api_contract_diff.py tests/test_midas_candidate_db_smoke.py &&
  /home/charlie/midas/.venv/bin/pytest -q tests/test_midas_resource_preflight.py tests/test_midas_sqlite_snapshot.py tests/test_api_contract_diff.py tests/test_midas_candidate_db_smoke.py tests/arena/test_dispatch_schedules.py &&
  /usr/bin/systemd-analyze --user verify /tmp/midas-arena-unit-verify-b13477e86477eadeccac22ebd84595a808dcd1f9/midas-arena-scheduler-release@b13477e86477eadeccac22ebd84595a808dcd1f9.service /tmp/midas-arena-unit-verify-b13477e86477eadeccac22ebd84595a808dcd1f9/midas-arena-scheduler-release@b13477e86477eadeccac22ebd84595a808dcd1f9.timer &&
  /home/charlie/midas/.venv/bin/python scripts/compare_api_contracts.py --candidate-root /home/charlie/.local/share/midas/releases/b13477e86477eadeccac22ebd84595a808dcd1f9 --isolated-root /tmp/midas-contract-validation-20261030/route-diff-root --existing-url http://127.0.0.1:8000/openapi.json > /tmp/midas-contract-validation-20261030/api-contract-diff-v3.json'
```

The restored legacy-fixture API rehearsal used:

```bash
/home/charlie/midas/.venv/bin/python scripts/midas_resource_preflight.py run \
  --label candidate-restored-db-smoke --profile bounded-test \
  --memory-budget-mib 640 --storage-path /tmp --storage-reserve-mib 0 \
  --memory-high-mib 768 --memory-max-mib 1024 --cpu-quota-percent 25 \
  --timeout-seconds 240 -- \
  /home/charlie/.local/share/midas/venvs/b13477e86477eadeccac22ebd84595a808dcd1f9/bin/python \
  scripts/midas_candidate_db_smoke.py \
  --candidate-root /home/charlie/.local/share/midas/releases/b13477e86477eadeccac22ebd84595a808dcd1f9 \
  --candidate-python /home/charlie/.local/share/midas/venvs/b13477e86477eadeccac22ebd84595a808dcd1f9/bin/python \
  --isolated-root /tmp/midas-contract-validation-20261030 \
  --database /tmp/midas-contract-validation-20261030/restored-clean.db --cycles 2
```

The actual fixture snapshot operations were:

```bash
/home/charlie/midas/.venv/bin/python scripts/midas_sqlite_snapshot.py backup \
  --source /home/charlie/midas/data/backups/midas-before-milestone2-1791742584.db \
  --destination /tmp/midas-contract-validation-20261030/snapshot \
  --integrity full --reserve-mib 0
/home/charlie/midas/.venv/bin/python scripts/midas_sqlite_snapshot.py verify \
  --snapshot /tmp/midas-contract-validation-20261030/snapshot --integrity full
/home/charlie/midas/.venv/bin/python scripts/midas_sqlite_snapshot.py restore \
  --snapshot /tmp/midas-contract-validation-20261030/snapshot \
  --destination /tmp/midas-contract-validation-20261030/restored-clean.db \
  --integrity full
```

Those snapshot commands were themselves run inside a bounded-test systemd scope.
The full live-database invocation must use the heavy profile, a measured
destination filesystem, a database-size-derived required capacity plus reserve,
`--integrity full`, and `--allow-large`; it was intentionally not run here.

## G. Deployment readiness matrix

| Component | Status | Gate |
|---|---|---|
| Unified API release | **BLOCKED BY DATA COMPATIBILITY** | Candidate passes legacy synthetic fixture; no production-scale consistent backup/restore or startup check against the active 12.58 GB database. |
| Arena scheduler | **BLOCKED BY DATA COMPATIBILITY** | Versioned candidate unit/timer are staged, but current schedule root and rollback compatibility have not been rehearsed on an isolated snapshot. |
| Mission Control web | **READY WITH CONDITIONS** | Candidate build/browser checks passed previously; it must be paired with the candidate API routes and follows API/Arena data gates. |
| SQLite backup/restore tooling | **READY WITH CONDITIONS** | Online backup mechanics, WAL fixture, manifest, integrity and isolated restore pass on small data. Full production-scale run requires fresh heavy admission. |
| Reality recorder | **BLOCKED BY AUTHORIZATION** | Protected current recorder unchanged; explicit owner authorization is required, and resource/archive/recovery gates still need fresh evidence. |
| Reality API/web | **IMPLEMENTED, VERIFICATION PENDING** | Staged candidate interfaces exist; current recorder/data-root integration and candidate canary not verified. |
| Veritas scheduled services | **IMPLEMENTED, VERIFICATION PENDING** | Existing timers, frozen work, and frozen-runtime overlay retained; candidate compatibility with active catalogs and campaigns has not been run. |
| Frontier, Observatory, Research Readiness | **READY WITH CONDITIONS** | Unified interfaces and tests exist; external probes remain disabled and current persistent research roots were not migrated or rewritten. |
| Full regression suite | **IMPLEMENTED, VERIFICATION PENDING** | 2,130 tests were previously collected but not completed. |
| Overall production migration | **NOT READY** | Production-sized database and Arena-state recovery evidence are still required; Reality cutover separately requires authorization. |

## H. Cutover and rollback procedure

No production cutover is included in this mission. After the data gate passes
and the owner explicitly authorizes the API/Arena/web operation, use this
sequence as the reviewable change plan:

1. Re-measure host and service state with
   `scripts/midas_resource_preflight.py check --profile heavy`, the real
   destination path, measured database size, and at least 5 GiB reserve. Do
   not proceed if a gate fails or a MIDAS worker owns the heavy-work lock.
2. While the old API is still live, make a consistent online SQLite snapshot
   to a verified backup destination with
   `scripts/midas_sqlite_snapshot.py backup --source /home/charlie/midas/data/midas.db
   --destination <new-versioned-backup-directory> --integrity full
   --reserve-mib 5120 --allow-large`, through the heavy resource runner. Run
   `verify --integrity full`, restore to a new isolated file, run integrity
   checks, and execute `midas_candidate_db_smoke.py --cycles 2` against that
   restored copy. Preserve the source, snapshot, manifests and logs.
3. Confirm exact current API, web, Arena timer/service, database, scheduler
   lock, data roots, environment hashes, and candidate identities. Pause
   incoming state-changing UI/API work. Stop the old Arena timer, wait for its
   service to become inactive, and verify the lock is released. Stop the old
   web and then old API; verify their PIDs and database descriptors are gone.
4. Start candidate API instance
   `midas-api-release@b13477e86477eadeccac22ebd84595a808dcd1f9.service` and
   require `READY`, release identity b13477e…, expected schema, paper journal
   recovery, disabled public probes, and `live_execution=false`. Run the
   selected GET route smoke. Start the paired candidate web instance only
   after API readiness, then start
   `midas-arena-scheduler-release@b13477e86477eadeccac22ebd84595a808dcd1f9.timer`
   after schedule-root owner and lock checks pass.
5. Confirm one API writer, one Arena dispatcher, timer identity and next
   elapse, web workspace loading, API and paper readiness, database/WAL
   ownership, service cgroup/OOM deltas, and no unexpected source/route
   behavior. Keep Reality and Veritas unchanged during this cutover.

Rollback begins by stopping candidate web, candidate Arena timer/service, and
candidate API; verify every process and writer lock is gone before restoring
the old API/web/Arena units. Keep all data and snapshots. The old and
candidate paper broker files and migrations 001–003 match, and the candidate
API contract preserves all old API operations. That is code-level rollback
evidence, not proof that a production journal or Arena schedule root can be
restored within an acceptable RTO. A candidate migration beyond 003, any
unexpected journal/hash failure, changed historical record prefix, non-synthetic
demo output, or incompatible Arena manifest is a stop condition. Do not run an
Alembic downgrade or overwrite a live database. Restore a verified snapshot
only after all writers are stopped and the owner has reviewed the exact
restore target.

The candidate Arena dispatcher also creates `dispatcher-state.json` and
changes active schedule manifests as it ticks. Until a copy of current Arena
state has been tested through candidate execution and old-release rollback,
that unit is not production-ready despite its local dispatcher tests.

## I. Remaining actions

**Engineering and evidence still required:**

- Wait for a fresh heavy-resource admission that clears Reality headroom,
  swap reserve, PSI, worker ownership, and destination capacity; then capture
  and restore the current production SQLite state with the online backup tool.
- Verify production Alembic identity, all tables and indexes, paper journal
  head/hash and event count, legacy records, Arena state, and historical
  research access on that restore. Run candidate API twice and test Arena
  schedules plus rollback on an isolated copy.
- Reconcile the difference between the inspected synthetic backup and its
  older evidence record; do not use that file as production provenance.
- Complete a resource-bounded, non-production browser/API workflow check for
  all listed Mission Control areas after the candidate API/data test. The
  prior frontend smoke is not full coverage of every workflow.
- Verify candidate Veritas readers against a frozen catalog/campaign copy,
  including the required frozen-runtime overlay, without changing historical
  artifacts. Validate any versioned service definitions before installing.
- Reassess Reality source sequencing, archive provenance, full-store restore,
  and recording-root integrity with bounded read-only evidence before asking
  for a transition window.

**Owner authorization required:**

- The coordinated production API/Arena/web downtime and shared database
  writer transition.
- Any Reality recorder stop, restart, signal, replacement, reconfiguration,
  or active data-root change.
- Any change to existing Veritas timer activation, frozen campaign ownership,
  or external source collection.

## J. Final handoff

- Working directory: `/home/charlie/midas-unification`
- Branch: `codex/midas-unification`
- Starting HEAD: `5237269821e5a6c3d54a3a92e76a0bc850a1f3b5`
- Mission engineering commit: `ade994576a8614ce5f7376d877371e1704f0ff5b`
- Application release identity: `b13477e86477eadeccac22ebd84595a808dcd1f9`
- Release directory: `/home/charlie/.local/share/midas/releases/b13477e86477eadeccac22ebd84595a808dcd1f9`
- Repeatable backup/restore: `scripts/midas_sqlite_snapshot.py backup|verify|restore`
- Repeatable admission: `scripts/midas_resource_preflight.py check|run`
- Repeatable candidate data test: `scripts/midas_candidate_db_smoke.py`
- Contract comparison: `scripts/compare_api_contracts.py`
- Versioned Arena unit files: `deploy/systemd/user/midas-arena-scheduler-release@.service` and `.timer`
- Coordinated release decision: `deploy/releases/midas-unified-b13477e86477eadeccac22ebd84595a808dcd1f9-resolution.json`
- Production cutover: not executed; no live service or persistent production data changed.

The active app remains old release `a152999`; the candidate is substantially
better prepared but is not safe to activate until the current production
database and Arena state pass the isolated recovery and rollback checks above.
