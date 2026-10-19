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

## H. Remaining blockers and Reality approval request

1. **MIDAS API startup memory is a critical unresolved blocker.** The API must remain disabled until a bounded-memory investigation identifies and verifies a safe recovery path. The current evidence proves the OOM, not whether paper event replay, SQLite buffering, demo refresh, or another startup allocation caused it. The previous service's unit lifetime peak was 8.5 GiB with 1.0 GiB swap peak; the two new processes reached about 9.0 GiB RSS. No memory ceiling should be raised blindly.
2. **Reality deployment needs explicit approval.** The live recorder must be restarted to load `b8220e3`. The proposed controlled procedure is:
   - Record the current PID, durable counts above, current open-tail size, latest segment and sidecar checksums, status freshness, cgroup memory events, and service unit properties.
   - After approval, use a single controlled stop/start of `midas-reality.service`. SIGTERM should let the current writer close/finalize its active segment and release its lock; startup then validates/reconstructs durable counts and recovers any incomplete tail.
   - Expect a capture interruption covering shutdown plus startup recovery. Public source events during that interval cannot be recovered, so a continuity gap may remain visible. The full store has 14,668 manifests and about 3.86 GB of finalized data; the full startup duration and peak memory are unknown. A 50-frame sample replay is not a basis for an ETA.
   - Verify new PID and loaded source, fresh observations, monotonic durable counts, latest segment checksum, cgroup memory below limits with no new OOM events, lock ownership, and preserved open-tail recovery. If validation fails, stop and preserve all files; restore the previous source with a new revert commit. Any second restart for rollback should be separately authorized.
   - Postponing leaves the currently healthy recorder running with old code. The counter reconstruction and bounded-recovery change remains undeployed, and its full-store startup behavior remains unproven.
3. **Endurance is outstanding.** Repeat only when sustained host CPU PSI is below the scheduler gate, resource headroom is adequate, and the API/recorder incidents have been resolved. Then run the isolated 60-minute workload and capture 5–10 minute samples.
4. **Veritas gap-detail analysis needs a separate bounded-cardinality fix** before that output can be treated as a reliable Frontier dependency.

**Approval requested:** Do you authorize one controlled restart of the protected Reality recorder to deploy `b8220e3`, using the procedure above? No restart has been performed while awaiting this approval.

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
