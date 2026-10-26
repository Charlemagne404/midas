# MIDAS Reliability Deployment Verification

**Captured:** 2026-10-20, approximately 00:45–00:50 CEST
**Verdict: NOT READY FOR FRONTIER**

## A. Executive summary

The committed Arena and campaign reliability changes pass the focused suites and disposable process-failure checks. The old `48H-001` campaign remains inactive and its final report hash is valid. The Reality recorder was not restarted; it is collecting fresh observations under its existing memory limits, but commit `b8220e3` is not loaded.

An attempted graceful restart of `midas-api.service` to load current MIDAS source exposed a critical production failure. The new process did not reach health: the kernel globally OOM-killed it at about 9 GB RSS during application startup. systemd automatically retried once and the retry was also globally OOM-killed. The API is now stopped and disabled to prevent another automatic restart. No memory limit was increased. The precise allocation responsible is not established, and the API remains unavailable.

The host also fails the Arena CPU pressure gate, swap is full, and I/O pressure is elevated. A 60-minute endurance run was not started. The separate Veritas gap-detail timer continues to fail on its distinct-reason bound. These findings make the operational infrastructure unsuitable for Frontier handoff at this time. This verdict is separate from the source-level test results.

No campaign, Reality recorder, Reality shadow worker, Veritas worker, or unrelated Continental service was intentionally restarted by this verification. No historical research or recording was deleted, reset, or regenerated. The only production service action was the MIDAS API restart attempt and its subsequent disablement after the OOMs.

## B. Deployment matrix

| Component | Source commit and change | Runtime/deployment state | Restart/reload and rollback |
|---|---|---|---|
| Arena jobs, scheduler, and tournament checkpoints | MIDAS `3b96500` | Source is committed in `/home/charlie/midas`. The one-shot Arena dispatcher ran at 00:43:02 from that checkout and completed an empty schedule scan at 00:43:08. No active Arena worker or held Arena execution lock was found. There is no persistent worker process to restart. | New dispatcher/worker invocations import the checkout. Roll back only with a reviewed `git revert`; do not reset historical artifacts. |
| Campaign controller and status | MIDAS `c8124ef`, plus `62859d6` for legacy finalization inference | Source is committed. The read-only status command reports `48H-001` as `PARTIAL`, finalization `COMPLETED` (inferred from the matching final-report hash), and no active step. The report SHA-256 matches the manifest. The installed service/timer definitions are stale: installed timeout is 300 seconds versus 240 in source, and the installed timer is five-minute calendar-based versus 30-second inactive-based in source. The campaign timer remains inactive and disabled. | Deploying unit-file changes would need `daemon-reload`; it does not require interrupting a protected service. No unit reload or timer activation was done. Existing installed unit files are the rollback copy. The old campaign timer must remain disabled. |
| MIDAS API | Current source tree at `62859d6`; earlier reliability commits `3b96500`, `c8124ef` | The pre-restart process started on Oct 17, before these commits; an exact imported-code hash was not recorded. It was healthy in `demo` mode with live execution disabled. The restart at 00:37:38 attempted to load the current tree but never reached a verified ready state. Two startup processes were globally OOM-killed. Current state: failed, `MainPID=0`, one systemd restart recorded, unit disabled. The unit has no `MemoryHigh` or `MemoryMax`. | A restart is required to activate current API source, but it is unsafe until startup memory use is bounded and validated. No retry is planned here. Keep disabled. A source rollback, if later justified, must use new revert commits and preserve the database; a revert alone does not address the observed memory behavior. |
| Reality recorder | Reality `b8220e3` | Commit is clean in `/home/charlie/midas-reality`, but not deployed. PID 863193 has remained active since Oct 19 00:50:57 and predates the commit. It is recording fresh data under `MemoryHigh=704 MiB`, `MemoryMax=768 MiB`, and `CPUQuota=25%`. | A protected-service restart is required to load the change and needs explicit user approval. Do not restart before approval. Rollback would require restoring the prior source with a new revert commit and, if the new runtime had started, another controlled restart. |
| Veritas gap-detail analysis | Veritas worktree `683dba2`; not part of this reliability change | Its timer is active. The latest run failed at 00:36:42 with `ValueError: Distinct finalized gap reasons exceeded their bound`; the same failure has recurred in recent runs. The service uses the frozen runtime overlay. No Veritas state was altered. | No restart or deployment was attempted. The bound failure needs a separate, evidence-preserving fix before relying on this pipeline. |

The active `midas-arena-scheduler.timer` continues to run short dispatcher scans; the latest scan returned `COMPLETE` with no schedules. The `midas-autonomy-48h-001.timer` is inactive and disabled. Reality recording and its related capacity, archive, research, and shadow timers were left in their existing states. No new research timer was enabled.

## C. Tests and failure verification

| Verification | Result |
|---|---|
| MIDAS focused suites: jobs, scheduling, tournaments, autonomy campaign, artifact usage index | **70 passed** in 94.36 seconds; one existing Starlette/httpx deprecation warning. |
| Reality `tests/test_reality.py` | **25 passed** in 13.29 seconds. |
| Ruff on the final status-inference source/test and `git diff --check` | Passed before commit. |
| Worker killed during evaluation in an isolated process | Three of eight durable rows were reused; five missing rows were recomputed. The recovered eight-row output exactly matched an uninterrupted deterministic reference, with no duplicate rows. |
| Process exit during temporary checkpoint write | The incomplete temporary write was not accepted. Retry recomputed all eight rows and matched the reference. |
| Process exit after artifact completion but before registry registration | Retry reused the completed artifact and registered one finding; it did not rewrite the durable rows. |
| Controller exit after durable admission but before publishing its job ID | Restart reconciliation found the admission key and retained exactly one job. |
| Reality copied-store restart and tail recovery | In disposable copies, counters were reconstructed across processes; an appended frame and partial tail byte were recovered with the partial byte recorded. A separate first-segment replay handled 50 frames/56 records with about 23.8 MiB peak RSS. |

The finalization deadline, shutdown grace, late-admission cutoff, report-publication failure, retry bounds, worker ownership checks, resource gates, artifact reconciliation, corruption rejection, and legacy campaign status inference were exercised in fixtures. They were not all exercised as live systemd process kills. No production worker or recorder was SIGKILLed, and no artificial OOM was created. Full-scale Reality startup replay, full paper-journal startup memory, process-kill at every database commit boundary, and live controller dependency transitions remain unverified.

The API restart attempt was an unintended production failure, not an OOM test. Read-only verification after it showed the paper account head at revision 376642 with the account checksum matching the latest event checksum. The latest event timestamp was 00:37:36, one second before the old process was stopped; no later recovery event was observed. A deeper read-only journal-delta query stalled in disk I/O and was abandoned. No database write or cleanup was performed by that diagnostic.

## D. Endurance results

No 60-minute endurance test was run. At 00:42:55 CEST, the host had about 8.7 GiB available RAM, 4.0/4.0 GiB swap occupied, and 186 GiB free disk. CPU PSI `some` was 65.27% over 10 and 60 seconds and 58.67% over 300 seconds. The Arena scheduler's CPU PSI gate is 20%, so this was unsafe for a representative workload. Memory PSI was low at the 10-second sample (`some=0`, `full=0`); I/O PSI was `some=2.34%`, `full=0.58%` over 10 seconds, with 300-second averages of 4.38% and 1.90%. `vmstat` showed small but nonzero swap movement. The recent global OOMs further precluded a sustained run.

These are host snapshots and pressure averages, not endurance evidence. No autonomous job transitions, checkpoint reuse cycles, dependent scheduling, or recovery under sustained load were observed. The endurance criterion remains **UNVERIFIED**.

A follow-up at 00:49:48 showed CPU PSI still high (`some`: 58.49% over 10 seconds, 61.85% over 60 seconds, 61.51% over 300 seconds), I/O PSI `some=2.16%` and `full=1.13%` over 10 seconds, 8.8 GiB available RAM, and 3.9/4.0 GiB swap occupied. Endurance remained unsafe.

## E. Performance comparison

| Measure | Evidence | Limit |
|---|---|---|
| Warm artifact usage lookup | Earlier 20-sample median: full scan 0.166247 s; indexed lookup 0.000206 s, about 806× faster for that operation. | Microbenchmark only; not an overall Arena speedup. |
| Tournament resume | An isolated process kill reused three completed rows and computed five missing rows; result matched reference. Earlier fixtures reused seven of eight rows. | No uninterrupted-versus-resumed end-to-end wall-clock comparison. |
| Arena dispatch overhead | Latest empty scheduler invocation used about 1.4 seconds CPU and peaked at 43 MiB. | Empty scan only; says nothing about worker runtime or progress. |
| API and Reality startup | API startup failed before health at about 9 GB RSS. Reality full-store startup time and peak memory were not measured. | No valid production improvement claim. |

Checkpoint writes add durable I/O, but the process-failure fixture demonstrates avoided recomputation of valid rows. No production cost or net time saving has been measured. The indexed-operation result is not extrapolated to full campaign speed.

## F. Reality health, memory, and data integrity

At the final read-only check the recorder was active as PID 863193, with status `RECORDING_UNSEQUENCED`; the latest observation was only seconds old. Its process-local counters were about 210,967 frames and 8,616 gaps. The persisted status also reports an orderly WebSocket close (`ConnectionClosedOK`) and one connection failure, while fresh observations continued. Sequence verification remains false; no stronger continuity claim is made.

A low-priority manifest scan found 14,668 finalized segment manifests describing 2,128,830 records and 3,864,578,744 bytes: 1,663,679 frame records and 8,618 gap records. It found no missing segment files or manifest/file-size mismatches. One active `.open` segment was present. The SHA-256 of the latest finalized segment matched its sidecar (`3e5b4d805bb9a0a41fa9508944157aef252d4a85e854deb9b46949b9afc6b453`). The scan did not hash every historical segment.

At 00:42:55, Reality used about 355 MiB of cgroup memory, mostly anonymous memory (about 355 MB; file cache about 7 MB). Its current cgroup reported `high=10069`, `max=0`, `oom=0`, and `oom_kill=0`; the running process peak was about 704.5 MiB, at the 704 MiB `MemoryHigh` threshold and below the 768 MiB `MemoryMax`. The historical Reality OOM at 2026-10-19 00:50:47 killed a process with about 732 MB anonymous RSS; systemd restarted the recorder ten seconds later. Historical service logs also show a 768 MiB memory peak and about 641 MiB swap peak.

This evidence shows real pressure and a prior cgroup OOM, but does not establish a leak. Current code inspection found bounded sample history and queue settings; the observed anonymous-memory peaks could still reflect retained book state, temporary allocations, runtime behavior, or another allocation path. No invasive profiling was run. The original Reality OOM cause and production memory trend remain unresolved.

The Reality recovery changes passed isolated tests, but production still runs pre-`b8220e3` code. The small copied-store tests do not establish startup time or peak memory when reopening the full 3.86 GB recording store. No production restart or continuity gap was introduced.

## G. Resource safety and operational state

- At 00:42:55 the host had 15 GiB RAM, about 8.7 GiB available, full swap, and 186 GiB disk headroom. CPU PSI remained far above the Arena gate; I/O PSI was below the scheduler's 20% `some` threshold but remained nonzero.
- The Arena tree contained 108 terminal jobs: 81 completed, 22 cancelled, four failed, and one interrupted. No queued/running job or held Arena execution lock was found. Ninety-one empty `execution.lock` files remain on disk; none was held, and none was removed.
- Arena worker resource unit definitions were not changed. No active worker existed for a live cgroup limit measurement.
- Reality remains under its configured user-control cgroup limits. The API unit has no memory cap; the failed restart demonstrated that it can consume host memory and trigger a global OOM. No limit was raised or added without evidence.
- The independent Veritas gap-detail failure remains active and recurring. The unrelated failed `daymark-db.service` was left untouched.

## H. Remaining blockers and Reality deployment plan — original snapshot, superseded by K

1. **MIDAS API startup memory is a critical unresolved blocker.** The API must remain disabled until a bounded-memory investigation identifies and verifies a safe recovery path. The current evidence proves the OOM, not whether paper event replay, SQLite buffering, demo refresh, or another startup allocation caused it. The previous service's unit lifetime peak was 8.5 GiB with 1.0 GiB swap peak; the two new processes reached about 9.0 GiB RSS. No memory ceiling should be raised blindly.
2. **Reality deployment needs explicit approval.** The live recorder must be restarted to load `b8220e3`. The proposed controlled procedure is:
   - Record the current PID, durable counts above, current open-tail size, latest segment and sidecar checksums, status freshness, cgroup memory events, and service unit properties.
   - After approval, use a single controlled stop/start of `midas-reality.service`. SIGTERM should let the current writer close/finalize its active segment and release its lock; startup then validates/reconstructs durable counts and recovers any incomplete tail.
   - Expect a capture interruption covering shutdown plus startup recovery. Public source events during that interval cannot be recovered, so a continuity gap may remain visible. The full store has 14,668 manifests and about 3.86 GB of finalized data; the full startup duration and peak memory are unknown. A 50-frame sample replay is not a basis for an ETA.
   - Verify new PID and loaded source, fresh observations, monotonic durable counts, latest segment checksum, cgroup memory below limits with no new OOM events, lock ownership, and preserved open-tail recovery. If validation fails, stop and preserve all files; restore the previous source with a new revert commit. Any second restart for rollback should be separately authorized.
   - Postponing leaves the currently healthy recorder running with old code. The counter reconstruction and bounded-recovery change remains undeployed, and its full-store startup behavior remains unproven.
3. **Endurance is outstanding.** Repeat only when sustained host CPU PSI is below the scheduler gate, resource headroom is adequate, and the API/recorder incidents have been resolved. Then run the isolated 60-minute workload and capture 5–10 minute samples.
4. **Veritas gap-detail analysis needs a separate bounded-cardinality fix** before that output can be treated as a reliable Frontier dependency.

**Current authorization:** The operator has explicitly withheld approval for a Reality recorder restart. Do not restart. The later diagnostic findings and updated plan in section K supersede the estimates and outstanding items in this original snapshot.

## I. Frontier readiness

| Gate | Assessment |
|---|---|
| Restart-safe Arena work and deterministic checkpoint reuse | **Validated in isolated process tests**, not yet demonstrated over sustained production cycles. |
| Bounded retries, deadlines, idempotent admission, and terminal campaign state | **Source tests pass**; campaign timer remains inactive. |
| Artifact accounting and resource monitoring | **Focused tests pass**; production endurance not measured. Existing host pressure safely blocks new work. |
| Reality durability and restart recovery | **Isolated copies/tests pass**; new code is undeployed and full-store startup is unmeasured. |
| Protected services healthy | Reality recorder remains active/fresh; API is unavailable; Veritas gap-detail job is failing. |
| Ready to launch another unattended 48-hour run | **No.** It would be unsafe and is expressly outside this phase. |

**NOT READY FOR FRONTIER.** The API's repeat global OOM during deployment is a known critical operational risk. Frontier should wait until API startup is bounded and health-verified, Reality deployment/recovery is approved and checked, and the Veritas failure is resolved or shown not to be a Frontier dependency. The endurance run must pass before a new unattended campaign. Frontier work and the next campaign were not started here.

## J. Repository and deployment status

| Worktree | Branch/HEAD | Working tree and remote state |
|---|---|---|
| `/home/charlie/midas` | `main` at `62859d6`; reliability commits `3b96500`, `c8124ef`, `50fd4f1`, plus status fix `62859d6` | Code is committed; branch is four commits ahead of `origin/main`, not pushed. This report will be committed separately; no changes will be pushed. |
| `/home/charlie/midas-reality` | `project/reality` at `b8220e3` | Clean, local commit; not deployed to the active recorder. |
| `/home/charlie/midas-veritas` | `project/veritas` at `683dba2` | Clean; no change made in this phase. |

The campaign timer remains inactive/disabled; Reality remains running on its prior loaded code; the API remains failed/disabled. No historical research, model registry, provenance, Reality journal, frozen campaign, or Veritas history was intentionally modified. No commit was pushed.

## K. Follow-on diagnosis and disposition — 2026-10-20 01:15 CEST

This follow-on supersedes the earlier API diagnosis in sections B, E, G, H, I, and J where the earlier snapshot said the API root cause was unknown. It also supersedes the earlier Reality approval request: the operator has explicitly withheld approval. **Do not restart Reality.** No service was manually restarted, no production API startup or deployment was attempted, and no timer change, database write, or historical-record modification was made during this follow-on. The already-active Veritas timer did launch its scheduled one-shot at 01:05; that attempt failed at the code-identity guard before batch processing or output publication.

### API startup OOM: cause isolated and source fix validated

The startup path is `API lifespan -> Service.start -> PaperBroker.start -> replay paper_events`. The production SQLite database is 5,298,958,336 bytes and the paper journal contains 376,643 events; the `paper-demo` account head is only 938,775 characters. The replay used SQLAlchemy `AsyncSession.stream`, but did not set ORM `yield_per`. In the SQLite/aiosqlite path, ORM loading therefore called DBAPI `fetchall()` and materialized the complete event journal during startup. This is the demonstrated cause of the multi-gigabyte startup allocation. The exact replay under a 2 GiB address-space cap failed inside `aiosqlite.cursor.fetchall` after 35.79 seconds at 2,071,884 KiB maximum RSS, without a database write. It reproduces the allocation mechanism; the earlier production OOM records of approximately 9 GiB RSS are consistent with it. This evidence identifies the dominant startup stage and cause; it does not imply that the kernel's exact allocation trace from the old process was captured.

The smallest correct fix is committed locally as MIDAS `9cc92d0`: set `yield_per=256` on the journal stream. The exact full-journal replay then completed in 89.62 seconds at 82,180 KiB maximum RSS, with no swap and no database modification. A separate isolated FastAPI lifespan with disposable database and data roots reached `READY` under a 1.5 GiB address-space limit at 88,872 KiB maximum RSS. Regression coverage asserts the streaming batch size. The paper integration suite passed 10/10; API integration passed 4/4; Ruff passed. These bounded results validate the fix and startup stage in isolation, not production activation.

**Runtime state remains failed and disabled:** `midas-api.service` has `MainPID=0`, `ActiveState=failed`, `NRestarts=1`, and `UnitFileState=disabled`. No API startup was attempted after the fix. Commit `9cc92d0` is local and unpushed. Keep the service stopped and disabled until a separately reviewed activation plan is accepted. That plan should first verify the unit's executable, working directory, environment and imported file path; retain the production DB read-only for a preflight; then use a one-shot, explicitly bounded service invocation with a conservative cgroup ceiling and no campaign timers. Validate health, journal head/checksum, and memory before any ordinary service enablement. If the bound is reached, allow the invocation to fail closed; do not raise it automatically or retry-loop. Restore the prior source with a reviewed revert commit if compatibility problems appear. No timer or campaign should be activated as part of this recovery.

### Veritas gap-detail failure: independent bound defect; deployment blocked by pinned state

The recurring source defect is a bound mismatch. Gap-reason cardinality is correctly limited to 128, but the same increment helper was also used for `campaign_window_affected_market_counts`. That market map already has its own 20,000-market limit; applying the 128-reason limit again makes valid journals with 129 distinct affected markets fail. In a disposable 129-market fixture, the old logic fails and the isolated fix passes. The fix is commit `49275d9` on local branch `fix/veritas-gap-market-bound` in `/tmp/midas-veritas-fix`; its focused tests passed 4/4 and Ruff passed. It is not pushed or deployed.

The output in `data/veritas-observatory` pins its campaign and code identity. State currently records 11,555 processed segments through ordinal 1,778,964; the summary records 11,549, six segments behind. A read-only identity check at 01:15 confirmed the restored runtime code hash equals the state hash (`d58bed78…`). The 01:05 scheduled gap-detail attempt failed at the pinned code-identity guard before batch processing or output publication, because the temporary test edit changed a package file imported through the frozen-runtime-overlay symlink. The edit was promptly restored. No state, summary, event file, or Reality record was changed by that attempt. The gap-detail timer remains active with its next scheduled run at 01:20; its one-shot service is failed with exit status 1. The separate source-analysis service was observed active and was left alone.

Do not copy `49275d9` over the linked runtime package or bypass its hash check. Safest recovery is to leave the current v1 state/events/summary immutable, build a separate v2 output root in an isolated copy using the corrected bound, replay the pinned source in bounded batches, and compare campaign identity, source catalog prefix, aggregate totals, and event counts. Only after those checks should a consumer be explicitly moved to v2. A reviewed migration could be considered instead if it preserves and verifies every prior output, but no in-place hash edit or state reset is acceptable. The deployed gap-detail timer will continue to fail on the original market bound until a versioned recovery is approved and deployed.

### Reality status, memory evidence, and deferred deployment

At the 01:15 CEST read-only sample, `midas-reality.service` was active as PID 863193, started 2026-10-19 00:50:57 CEST, with `NRestarts=1`. Its status file was fresh (about 0.1 seconds old): `RECORDING_UNSEQUENCED`, 16/16 fresh books, eight markets, 3,881,356,265 durable storage bytes, and `sequence_verified=false`. Process-local counters were 213,966 frames and 8,643 gaps; they are not lifetime totals. The cgroup had 426,160,128 bytes current memory (~406 MiB), 738,721,792 bytes peak (~704.5 MiB), `MemoryHigh=704 MiB`, `MemoryMax=768 MiB`; `memory.events` showed 10,069 high events and zero max, OOM, or OOM-kill events. Current memory was below the peak, but the small peak-to-max margin and repeated high events remain relevant. This does not establish an active leak or explain the historical global OOM.

A representative copied 2.61 MB finalized segment completed manifest verification and replay in about 0.47 seconds at 24.4 MiB peak RSS. That is a sample-path measurement, not a whole-store boot measurement. The store now has roughly 14,703 finalized manifests and 3.88 GB of durable records. Linear scaling of the sample's two-pass work to the store's startup validation/replay passes suggests roughly 16.5 CPU-minutes, or about 66 wall-minutes at the configured 25% CPU quota, before stop/reconnect overhead. This is a low-confidence planning estimate, not a measured recovery duration; reserve at least a 90-minute window and expect longer if archive composition or contention differs. The earlier estimate should not be read as a guarantee. The process has a 45-second stop timeout; graceful SIGTERM should finalize the open segment and append its stop checkpoint. A forced timeout relies on tested incomplete-tail recovery. Because source sequencing is unverified, any restart creates an irrecoverable public-source observation gap for the interruption.

The host remains unsuitable for endurance or full-store replay measurement: CPU PSI `some` was 68.17% over 10 seconds, 68.01% over 60 seconds, and 64.09% over 300 seconds; available RAM was about 8.56 GiB; swap was 4,146,827,264 of 4,294,963,200 bytes occupied (about 96.6%); I/O PSI was 1.93% `some` and 0.67% `full` over 10 seconds. The CPU pressure exceeds the 20% scheduler gate. No full archive startup measurement or endurance run was attempted.

Reality remains on the pre-`b8220e3` process, and **restart is expressly unauthorized**. For later consideration only: capture the then-current PID, fresh status, open-tail size, latest finalized checksum, durable counters, and cgroup events; ensure the host has sustained safe CPU/I/O headroom and materially lower swap occupancy; arrange a 90-minute minimum maintenance window; request explicit approval; gracefully stop once; deploy only the reviewed Reality commit; then verify recovered counters, tail handling, fresh collection, checksums, memory and cgroup events. If startup or continuity checks fail, preserve all output and stop the service. Rollback would restore the pre-`b8220e3` source with a reviewed revert; any second restart would need separate authorization. Deferring keeps the live recorder on old code and avoids a known unsequenced collection gap. No restart or deployment occurred.

### Updated tests, performance, and readiness

| Item | Follow-on evidence | Production interpretation |
|---|---|---|
| API journal recovery | Full 376,643-row journal failed at 2 GiB cap without batching; completed at 82,180 KiB peak RSS with `yield_per=256`. | Strong isolated proof of the allocation fix; production API remains stopped and unverified. |
| API lifespan | Disposable FastAPI lifespan reached `READY` at 88,872 KiB peak RSS under 1.5 GiB address-space cap. | No production DB, socket, or service was started. |
| Veritas cardinality | 129-market fixture fails old implementation and passes isolated fix; 4 tests pass. | Fix is not deployed; pinned v1 state blocks in-place source replacement. |
| Reality startup | 2.61 MB copied-segment sample at 24.4 MiB peak RSS; rough 66-minute full-store projection at 25% quota. | Full startup peak/time remain unmeasured; no production restart. |
| Endurance | Not run; CPU PSI exceeded gate and swap was 96.6% occupied. | Remains **UNVERIFIED**. |

The API replay measurement is a major reduction in replay-stage memory, not evidence that all API routes or workloads fit a particular production cgroup limit. The earlier 806x indexed artifact-accounting microbenchmark remains limited to that operation and is not an overall Arena speedup. Correctness and bounded recovery are demonstrated in isolated tests; production API runtime behavior, full Reality archive startup, deployed Veritas recovery, and sustained multi-job progress remain unverified.

**Updated verdict: CONDITIONALLY READY FOR FRONTIER DEVELOPMENT ONLY.** The API's OOM cause is now identified and a small fix is committed and resource-bounded-tested; the source-level defect is no longer unexplained. However, API deployment is intentionally held, the Veritas fix needs versioned output recovery, Reality deployment is expressly unauthorized, and endurance remains unverified under unsafe host conditions. This is not readiness for production deployment, another 48-hour unattended campaign, or Frontier experiments that depend on these services. Frontier work and all new campaigns remain unstarted. Before production research: review an explicitly bounded API recovery, validate a versioned Veritas output, obtain separate Reality restart approval and perform post-deploy verification, then rerun endurance only under sustained safe host conditions.

### Updated repository and runtime state

| Component | Source state | Runtime/deployment state |
|---|---|---|
| MIDAS | `main`; API fix `9cc92d0` is followed by this separate local documentation commit. Branch is seven commits ahead of `origin/main`, not pushed. | API failed, disabled, no PID; fix not loaded by production service. |
| Reality | `/home/charlie/midas-reality` clean at `b8220e3`. | Existing PID 863193 remains active on older loaded code; no restart or source deployment. |
| Veritas main worktree | `/home/charlie/midas-veritas` clean at `683dba2`. | Gap-detail timer active; one-shot failed at 01:05 before processing; source-analysis service was active at the 01:15 sample. |
| Veritas fix | `/tmp/midas-veritas-fix`, branch `fix/veritas-gap-market-bound`, commit `49275d9`, clean and unpushed. | Isolated only; not copied into linked runtime overlay. |

No changes were pushed, historical artifacts were preserved, and the `48H-001` timer remains inactive. The prior temporary Veritas source edit was restored before handoff; the current frozen-runtime code identity again matches its persisted v1 state.
