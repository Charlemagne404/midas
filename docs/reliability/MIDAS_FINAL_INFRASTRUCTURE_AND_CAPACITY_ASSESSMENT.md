# MIDAS final infrastructure, storage and capacity assessment

**Assessment date:** 2026-10-20 (UTC; host local time CEST)  
**Scope:** existing MIDAS host, protected Reality recorder, main API/Arena, Veritas, and isolated Reality recovery candidate.  
**Production safety:** the Reality recorder was not stopped, signalled, or restarted. No source observations, frozen campaign outputs, model evidence, or Veritas history were deleted or rewritten. Frontier, new live collectors, and a new 48-hour campaign were not started.

## A. Executive summary

The host is no longer suffering the severe API read-amplification problem measured earlier on October 20. The verified 61-minute post-optimization observation recorded 14.01% mean host CPU busy, 2.13% mean CPU PSI, 0.79% mean I/O full PSI, and zero memory PSI. The production API remained ready, Reality continued recording, and two scheduled Veritas qualification jobs completed. API writes per observation fell 89.6% with comparable observation throughput. These improvements are documented in [the host capacity report](MIDAS_HOST_CAPACITY_AND_PERFORMANCE_OVERHAUL.md) and its [evidence index](evidence/host-capacity-20261020/README.md).

That operating result does not clear the four Frontier blockers. The Reality application budget is 24 GiB with a 20 GiB disk reserve; its latest receipt estimates 0.973 GB/day of growth and 21.83 days to the application limit. The root filesystem has about 179 GB free, so the immediate limit is the application budget rather than physical exhaustion. The source is currently fresh but unsequenced, has accumulated gap and comparison exceptions, and the live status retains a stale disconnect error. The recovery candidate has strong fixture and fault-injection coverage, but full-archive replay did not finish. A bounded historical Arena tournament completed beside Reality, but that single workload does not establish continuous heavy-training capacity.

Safe work completed in this pass: the capacity monitor now warns at 30 days and marks 14 days critical; its timer runs every 30 minutes instead of every five minutes while retaining the same 120-segment measurement window. An isolated recovery runner now reads immutable finalized files through a tested Landlock read-only boundary, with independent staging writes and separate host/recorder admission checks. Arena source now has an atomic-publisher mode that avoids repeatedly polling thousands of newly published artifacts in a large historical tree. Tests pass for these changes. None of this authorizes or performs a protected recorder restart.

## B. Current host and runtime baseline

The latest point snapshot was collected at approximately 2026-10-20 19:35 UTC. It supplements, but does not replace, the 61-minute controlled production observation.

| Measure | Current point snapshot | Comparable sustained observation / interpretation |
|---|---:|---|
| CPU | CPU PSI some avg10 1.13%, avg60 1.84% | 14.01% mean host busy; 2.13% mean CPU PSI in the 61-minute window |
| Memory | 9.11 GB MemAvailable; memory PSI zero | 15.52 GiB usable RAM; no sustained memory pressure in the 61-minute window |
| Swap | 3.17 GB occupied of 4.29 GB | `vmstat` showed no sustained `si`/`so`; occupied swap is mostly idle, not evidence of thrashing by itself |
| Reality cgroup | 736.7 MB charged; 738.2 MB MemoryHigh; 805.3 MB MemoryMax; 68.7 MB below max | 10698 `high` events, zero `max`, `oom`, or `oom_kill`; anonymous 653.7 MB, file cache 62.8 MB, kernel 20.2 MB |
| Reality process | PID 863193, RSS 647.9 MB, VmSwap 668 KB, two threads | NRestarts 1, unchanged since the historical OOM; no restart during this assessment |
| Storage | NVMe root 178.95 GB free; separate HDD 641.23 GB free | HDD is not part of the recorder root or its application budget; staging copies previously caused I/O PSI and were stopped |
| I/O | `io.stat` is unavailable in the delegated user cgroup | 61-minute mean I/O full PSI 0.79%, peak 2.49%; device and process I/O are recorded separately in the host report |

The Reality service has CPUQuota 25% of one CPU, MemoryHigh 704 MiB, MemoryMax 768 MiB, MemorySwapMax 0, and TasksMax 32. The main API is PID 3717987 and ready, with one CPU quota, 1.5 GiB MemoryHigh and 1.75 GiB MemoryMax. The separate Reality interface API is PID 3725032 and active. Both API health and the current Reality endpoint were checked directly. No new service restart or OOM was observed.

At another point during this work, I/O full PSI temporarily reached 6.17% avg10 and 3.87% avg60 while tests and scheduled work overlapped. It later fell to 0.75% avg10 and 1.00% avg60. This transient is not presented as a normal-load average. No archive workload was started during the elevated sample.

## C. Storage sustainability

### Actual limit and measured growth

The reported “about 22 days” is the Reality store's **application budget**, not the physical filesystem limit. `deploy/reality.json` sets a 24 GiB budget (`25,769,803,776` bytes), a 20 GiB free-disk reserve (`21,474,836,480` bytes), 90-day retention, eight configured markets, and 8 MiB/300-second segments. The receipt-aware capacity calculation limits usable headroom to the lower of application headroom and physical free space after the reserve.

At 2026-10-20 19:36 UTC, the current status endpoint reported:

| Capacity item | Measured value |
|---|---:|
| Reality recording root | 4,525,525,538 bytes |
| Application budget | 25,769,803,776 bytes (24 GiB) |
| Budget-limited headroom | 21,244,278,238 bytes |
| Physical filesystem free | 179,362,594,816 bytes |
| Reserved physical free space | 21,474,836,480 bytes (20 GiB) |
| Recent finalized-segment/catalog growth | 11,263.45 bytes/s; 973,161,695 bytes/day |
| Estimated application-budget runway | 1,886,126 seconds, about 21.83 days |
| Current alert | `CAPACITY_WARNING_WITHIN_THIRTY_DAYS` |

The rate came from the latest 120 finalized segments over 3,647.7 seconds: 34,506,704 raw frame-payload bytes and 41,085,738 compressed/catalog bytes. It is a short-window estimate; the receipt explicitly excludes the active segment from its rate, includes current root usage, and states that future rates vary. Earlier 61-minute evidence measured 40,595,398 bytes of additional store growth and independently estimated 22.18–22.35 days. The two recent measurements support the same approximate runway, but do not establish a seasonal forecast.

### Storage categories and safe reclamation

The current Reality root byte count includes raw observations, finalized segment files, sidecars/manifests, and the active/incomplete recording state. The recent receipt reports no separately accounted recovery checkpoint. A metadata inventory at 2026-10-20 19:04 UTC covered 17,068 finalized segments, two empty segments, and 4,516,957,497 segment bytes; it excluded a small open tail. That inventory is historical to its timestamp and is not a full byte-checksum audit.

The existing subsystem inventory found approximately 3.9 GiB of a local Reality archive copy, 3.5 GiB in Reality research outputs, 3.4 GiB in Arena, and 0.9 GiB in Veritas. Arena's job subdirectory was about 110 MB. Ninety-four retained Arena source snapshots accounted for 91.8 MB of logical files, but only about 3.05 MB of distinct source bytes; the roughly 88.7 MB repeated portion is provenance evidence and saves less than 2.2 hours of current Reality growth. These categories are logical/worktree views and are not additive physical-device totals because of overlap and hard links. The whole root filesystem also contains operating-system, user, and unrelated Continental data; those files were not treated as MIDAS cleanup targets.

| Storage class | Available measurement | Treatment |
|---|---|---|
| Raw Reality observations and finalized segments | 4.5255 GB current recording-root total; 4.5170 GB finalized segment bytes in the 19:04 UTC inventory | Retained; the receipt's growth estimate includes compressed/catalog bytes and gaps |
| Open tail, manifests, and checkpoints | The inventory recorded a small open tail (about 75.5 KB) and no recovery checkpoint at that boundary; sidecars are included in the root total | Not changed; the old-tail size is not presented as current |
| Local Reality archive copy | Approximately 3.9 GiB in the prior subsystem inventory | Kept as a recovery/provenance copy; not removed or moved during this run |
| Reality research, Veritas, and Arena | Approximately 3.5 GiB, 0.9 GiB, and 3.4 GiB respectively; Arena jobs about 110 MB | Preserved; no retention policy or ownership evidence justified deletion |
| Models and training datasets | Included in the Reality research/Arena totals above; not separately reconciled by model or dataset in this assessment | Preserved; no immutable evidence was compacted or purged |
| API journal, Laboratory outputs, logs, and existing temporary files | No fresh ownership-resolved byte split was available without another broad tree walk | No age-based cleanup; this remains an accounting gap, not assumed to be zero |
| Arena duplicate source snapshots | 91.8 MB logical, about 3.05 MB distinct source content across 94 snapshots | Preserved for reproducibility; estimated duplicate portion is too small to change runway materially |
| Filesystem metadata and non-MIDAS data | Included in the filesystem's used/free blocks, not in the Reality application budget | Not assigned to MIDAS without ownership evidence |

The two failed staging attempts created small disposable copies on NVMe/HDD. Their exact run-owned paths are cleaned after preserving the stop reasons and worker receipts below; they are not source evidence.

No raw Reality observations, archived source, API journal, Veritas history, models, datasets, frozen campaign, or old logs were deleted. No expired temporary directory was removed on age alone. The identified duplicate source snapshots are too small to solve the runway and are intentionally retained for reproducibility. The recent API account-head compression reduced durable writes without changing logical state; that is a useful I/O optimization, not a reduction in Reality capture growth.

### Runway target and storage decision

At the measured rate, 90 more days require about 87.6 GB of new Reality data, or about 92.1 GB including the current 4.53 GB root. A 96 GiB Reality allocation would cover that single-source linear estimate with modest budget margin, subject to reserving space for other MIDAS data, recovery, checkpoints, and unrelated disk growth. The current root has enough physical space for that 1x estimate after the existing 20 GiB reserve, but the configured 24 GiB application budget does not.

For a simple linear Frontier scenario, one comparable additional collector would bring total growth to about 1.95 GB/day. Ninety days would require about 175.2 GB of new writes. Current physical free space after the 20 GiB reserve is about 157.5 GB, so the 2x scenario is short by at least 17.7 GB before other MIDAS growth or recovery headroom. Four times the current total rate would require about 350.3 GB over 90 days and is not supportable on the present unallocated root capacity. These are storage-only extrapolations; no extra collector was launched and no scaling behavior was measured.

The warning threshold is now 30 days, critical is 14 days, and the existing action threshold remains seven days. The capacity timer was safely changed from five to thirty minutes to avoid repeatedly sampling the same 120-segment window; it remains active. Raw retention remains 90 days and the writer still stops at its configured budget/reserve. No budget expansion was applied because the live recorder has its configuration loaded in memory; changing the file alone would make the timer's displayed limit disagree with the writer's actual limit until a protected transition. A coordinated budget/retention/archive decision and recorder transition are still required.

**Storage verdict: NOT READY.** The physical root is not about to fill, but the active Reality budget still has roughly 22 days of runway, far below the 90-day target.

## D. Reality source quality

At 19:36 UTC the recorder endpoint was 0.63 seconds old, the last observation was 0.64 seconds old, all 16 expected books were fresh, and `timing_uncertain_books` was zero. The process state was `RECORDING_UNSEQUENCED`; `sequence_verified` was explicitly false. The same live status contained 9,864 cumulative gap records and lifetime comparisons of 239 concurrent-update ambiguities, three ineligible local states, one unavailable public comparison, 118 stable local-lineage divergences, 9,744 stable local-lineage matches that remain unsequenced, and 41 stale comparisons. These are lifetime counters, not current outage counts. A REST snapshot can differ because the source changes during the round trip; a divergence is a quality exception, not proof of a dropped WebSocket event.

The current status also retains `ConnectionClosedOK: received 1001 ... server shutting down` even though frames and observations have advanced after reconnect. This is a stale diagnostic in the old live implementation. The reliability candidate clears the current error after a successfully received non-heartbeat frame while preserving gap history. That correction is covered in the candidate source/tests, but the protected process still has the older loaded code.

Historical monitoring observed timing-degraded and book-degraded states during an otherwise running process. The current process-lifetime maximum append time is 0.208 seconds; it is not a p95/p99 latency distribution. One independent REST comparison had a 47.2 ms round trip, which is not one-way source-to-host latency. The earlier source timestamp versus local receive comparison varied widely and does not establish network delay because the source timestamp semantics are not a guaranteed transit timestamp.

The upstream [Polymarket real-time data documentation](https://docs.polymarket.com/market-data/realtime-data) describes book/price-change data and optional timestamps but does not provide a documented monotonic per-event sequence field. MIDAS therefore cannot prove that every upstream event was delivered. It correctly avoids claiming sequence verification; reconnect gaps and uncertain lineage must remain visible. There is no confirmed MIDAS-caused silent loss in the evidence reviewed, but unsequenced source continuity is inherently unprovable.

Candidate source changes at `fix/reality-foundation-20261020` (`f2dc9c7`) bound transport/parse lifetimes, keep status states distinct during resynchronization, preserve durable tails, use checked recovery checkpoints, and clear stale connection errors after recovery. The candidate passed its documented 165-test core regression and isolated synthetic benchmark. It has not been deployed to the recorder or tested in a 60-minute realistic source interruption/reconnect endurance run.

**Reality data-quality verdict: DEGRADED.** The recorder is live and currently fresh, but source continuity is unsequenced, quality exceptions exist, and the active implementation reports one recovered disconnect as a current error.

## E. Full-store recovery and deployment readiness

The current metadata boundary at 19:04 UTC was 17,068 finalized segments and 4,516,957,497 segment bytes. The live ordinal later advanced to 2,521,304. Metadata accounting is not a complete integrity check: only three real segments had complete checksum and record verification in the previous validation attempt.

The original full-store gate incorrectly treated a few MiB below the recorder's `MemoryHigh` as a reason to prohibit any independent test. The staging runner now distinguishes the recorder's local reclaim threshold from host headroom and its hard `MemoryMax`. It retains conservative admission: at least 32 MiB below recorder `MemoryMax`, at least 3 GiB host MemAvailable, CPU PSI some avg10 below 20%, memory PSI below 0.5%, and I/O full PSI below 4% avg10 and 2% avg60. It rechecks recorder identity and memory event counters. Each worker receives MemoryHigh 640 MiB, MemoryMax 768 MiB, zero swap, 15% CPU quota, low CPU/I/O priority, 16 tasks, a 70-minute unit timeout, a 64 MiB per-file limit, and a 256 MiB staging-output bound.

Copying the 17,000-file archive is not viable on the shared host: the NVMe copy attempt was stopped after I/O full PSI exceeded its limit, and a second attempt on the separate HDD was stopped when small-file copying again drove I/O full PSI above the sustained threshold. Those workers were terminated by their own runner; their partial copies never replaced or changed source files. The runner now symlinks only finalized segment files and applies a Landlock policy in the worker: source paths remain readable, all filesystem mutation is denied except under that run's independent staging root. A direct probe verified that write-open and unlink through an archive symlink are denied while a staging checkpoint can be written.

Two zero-copy full-archive attempts passed the read-only probe and entered cold recovery. The first ran about 10 seconds, used 2.52 CPU seconds, and peaked near 52.5 MiB. The second used the reduced 15% CPU quota, ran about 10 seconds, used 1.53 CPU seconds, and peaked near 35.7 MiB. In the second attempt, host CPU PSI some avg10 rose from 6.35% to 19.49% within the two recorded samples; the worker was then stopped by the runner's 20% pressure gate. Neither worker used swap or increased recorder `MemoryMax`, `max`, or OOM events. The recurring Veritas/Arena scheduled workload would overlap the estimated full replay duration, so I did not repeatedly launch the same multi-hour recovery matrix. The full archive remains intact.

The candidate's earlier full replay took about 428 CPU seconds on a prior implementation, but that run did not produce a final verified receipt. At the new 15% CPU quota that cost would correspond to roughly 48 minutes for one replay; this is only a linear estimate, not a candidate startup measurement. The new candidate full cold recovery, checkpointed recovery, deterministic full-archive digest, full-scale checkpoint rejection, and full-scale recovery memory peak are therefore **not verified**. Isolated fixture tests cover clean recovery, checkpoint fallback, stale/corrupt checkpoint rejection, SIGKILL during checkpoint replacement, incomplete-tail preservation, and counter reconstruction; they do not replace full-store evidence.

The run-owned partial copies and symlink staging directories from these attempts were removed after preserving the stop reasons and bounded worker measurements here; no source files were followed or deleted. Failed systemd test units are inactive and have no remaining process; their failure state was not reset. The 60-minute synthetic Reality recovery benchmark in the prior report was bounded to a disposable synthetic source, not the complete production archive or a real network feed. No 60-minute realistic ingestion/reconnect endurance was completed in this mission. No precise startup interruption estimate is defensible. The final production procedure must pin candidate `f2dc9c7`, record the current PID/counts/tail and source hashes, require a full-size cold and checkpointed receipt plus a measured peak and first-durable-write time, confirm at least 64 MiB sustained recorder headroom as a conservative preflight target, verify host reserve and post-start 16/16 book freshness, and include one-step rollback to the old source. Abort on identity change, new OOM/max event, failed checksum, missing durable progress, stale source status, or insufficient capacity. The actual expected observation gap must be based on the completed measurement, not guessed from the earlier implementation.

No production transition is proposed for approval now: recovery measurements and sustainable storage allocation are still incomplete. The restart prohibition remains in force.

**Reality full-scale recovery verdict: PARTIALLY VERIFIED.** Fixture recovery and the read-only sandbox are verified; full archive recovery is not.

## F. Heavy-research capacity

The strongest completed heavy-work evidence is a 160-episode tournament with five models and 2,880 evaluation rows. It ran for 348.63 seconds, used 277.57 CPU seconds, peaked at 649.7 MiB, and produced about 36.36 MB of job artifacts. It achieved 8.26 evaluation rows per wall second and 0.0964 CPU seconds per row. Reality was already recording during this job. The worker ran under an 80% CPU quota and its result was a completed evaluation, not a model-training or profitability claim.

The 48H-001 campaign report records 11.917 worker CPU-hours across its attempts and a partial result; it is historical evidence, not a new campaign or a 48-hour sustainable-throughput test under the current optimized host. The post-optimization 61-minute window also included two scheduled Veritas qualifications, but those were light finalized-segment checks, not substantial training. No additional campaign was started.

Research scheduling currently serializes heavy Arena work to one worker. New jobs are subject to requested-memory-plus-2-GiB admission, available-memory and host-pressure checks, per-job CPU/memory/wall limits, zero swap, low CPU weight, and artifact/disk budgets. Work that does not fit is queued or rejected without deleting evidence.

There is a demonstrated research accounting inefficiency. A completed tournament recorded 2,882 artifact observations, 73.62 seconds in artifact accounting and 18.65 seconds in progress publication over 348.63 seconds, about 26.5% of elapsed time. A completed Director took 947.7 seconds, with approximately 262.7 seconds in artifact accounting and 34.9 seconds publishing progress. A cancelled long Director had 10,768 observations and approximately 1,042 seconds in artifact accounting over 2,402.6 seconds. These costs do not represent useful model/simulation work.

Arena's artifact writers use fsync plus atomic replacement at progress boundaries. `UsageIndex` retains its default in-place polling for generic callers and tests, but the Arena worker now explicitly selects atomic-publisher mode. In large directory-event mode this removes repeated `stat` calls across new completed artifacts while directory rename/create events keep byte counts exact. A regression creates and atomically replaces artifacts in a forced large-tree mode, confirms exact totals and zero poll paths, and leaves the in-place-write tests enabled for the generic mode. This fixes a specific source-level cost; no new heavy job was launched to claim an end-to-end production speedup. The expected reduction is from the observed thousands of repeated path checks per progress callback to none for those atomic paths; actual next-job timing remains to be measured.

If the measured tournament were repeated continuously with identical hardware load, a purely linear 48-hour extrapolation would be approximately 1.43 million evaluation rows and 38.3 CPU-hours. This is not a capacity promise: it assumes continuous 80%-of-one-core work, no admission deferrals, no scheduled competitor, and no change in the workload. It does not apply to full model training or future collector analysis.

**Heavy-research capacity verdict: CONDITIONALLY SUFFICIENT.** One bounded useful tournament and routine Veritas jobs have coexisted with recording, and concurrency/resource gates are in place. Sustained training throughput and a long autonomous run remain unverified; only one heavy worker at a time is justified.

## G. Cross-system integration and endurance

In the 61-minute production observation, Reality's durable ordinals and frames advanced, both APIs remained ready, 119 Veritas segments finalized, two scheduled qualifications completed, and no sampled API failure, new OOM, or service restart occurred. The two completed jobs processed 268 and 269 events in approximately four seconds each and correctly produced no positive gross candidate. This is routine integration evidence, not heavy-research endurance.

This assessment did not run archive recovery concurrently with Veritas analysis or a new research campaign. The isolated validation worker uses a separate cgroup and filesystem policy; its first cold attempt stopped on host CPU PSI, before it could establish combined recovery behavior. I/O contention from archive copies was observed directly and is why copy-based staging was removed. Storage growth remains visible through the receipt-aware capacity monitor. Main Arena temporary/test outputs are bounded by admission and per-job artifacts, and validation output is capped. No process is currently running from the failed validation attempts.

The recent production API write reduction and lower I/O PSI are preserved. No global CPU/memory/swap policy was changed. Scheduled services and unrelated Continental services were not disabled. No retry loop was added to the recorder or test runner.

## H. Implemented changes, revisions, deployment, rollback

| Change | Revision / test | Deployment state and rollback |
|---|---|---|
| Reality capacity warning at 30 days and critical at 14; capacity sampling timer every 30 minutes | `project/reality` commit `af3d92e`; 14 Reality operations tests pass; Ruff passes | Pushed to `origin/project/reality`. Timer installed, reloaded, and active. Recorder untouched. Revert timer to five minutes and restore prior thresholds if sampling cadence needs rollback. |
| Independent full-store staging admission and zero-copy Landlock read-only source access | Main checkout tool/test edits; 14 focused runner/sandbox tests pass; Ruff and py_compile pass | Engineering tooling only; no production unit or recorder change. Revert runner files to restore prior copy-based approach, though copy-based execution is not recommended under observed I/O pressure. |
| Arena atomic-publisher artifact accounting | Main checkout `usage.py`/`jobs.py`; 25 combined usage/job tests passed, then the refined usage-index test passed 10/10; Ruff and py_compile pass | Source in the production checkout and ready for a future worker launch, but not exercised by a production research job. Roll back by removing `watch_in_place=False`; generic polling remains the default. |
| Reality bounded recovery/transport candidate | Candidate worktree `f2dc9c7`; existing report records 165 core tests passed and bounded synthetic benchmark | Not deployed. Production process PID 863193 still has loaded implementation `2b83818`; production checkout is `c833200`. Restart requires separate explicit approval after full-size measurements. |
| Main API and Veritas reliability/performance improvements | main `87edab0`; Veritas `44178fb` | Earlier changes were deployed and pushed. Current main API is ready; Veritas scheduled work remained active. No forced push or remote overwrite occurred. |

There are three Reality-related code identities and they are not interchangeable: the production checkout is `c833200`, the protected recorder process loaded old `2b83818`, and the isolated candidate is `f2dc9c7`. The candidate was not copied into the live import path. The active capacity timer imports the production Reality checkout on its next run; it is a reporting/configuration change and does not touch the recorder lifecycle.

## I. Current sustainable operating envelope

The present evidence supports continuous recording plus both APIs, routine periodic Veritas analysis, and at most one bounded research worker when admission passes. Normal host CPU and memory have headroom; the recorder's own MemoryHigh margin is consistently tight and its storage budget has only about 22 days remaining. In-place research accounting had an avoidable cost now fixed in source, but that fix has not yet had a production job measurement.

The evidence does not support continuous multi-worker research, an unattended new 48-hour campaign, a full-store candidate deployment, or additional live market collectors. Low average host utilization cannot erase the recorder-local memory margin, source-sequence uncertainty, or budget horizon.

## J. Frontier expansion headroom

On a linear storage model, each collector matching the current eight-market Reality workload adds about 0.97 GB/day. Current configured headroom lasts about 21.8 days for one collector and about 10.9 days if a second comparable collector doubled total growth without a budget change. Ninety days at 1x fits current physical free space after the existing reserve, but requires an application budget of roughly 96 GiB. Ninety days at 2x requires at least 17.7 GB beyond current free capacity after the 20 GiB reserve; that excludes other MIDAS growth and checkpoint/restore working space. A four-times scenario is physically unsupported on the currently free root allocation.

Storage is not the only constraint. Current host utilization supports routine analysis, but no event-rate scaling benchmark exists for additional sources. The Reality protocol adapter is Polymarket-specific, source ordering is unverified, and a full candidate recovery is unmeasured. Each future source would need its own faithful timestamp/sequence semantics, durable format, cgroup and disk budget. Isolated development can continue; production expansion cannot be called ready.

## K. Remaining blockers and exact decisions

1. **Storage allocation/preservation:** choose a coordinated Reality budget, retention, and archival/off-host policy. At current growth, at least a 96 GiB app allocation supports the single-source 90-day estimate with some margin; a second comparable collector needs at least 17.7 GB of additional physical free space after today's 20 GiB reserve for 90 days, plus other service and recovery reserves. Do not change the active writer's budget through a file-only edit.
2. **Protected Reality transition:** after a full-size cold and checkpointed recovery measurement, decide whether to authorize one controlled recorder stop/start to load `f2dc9c7`, with a measured expected observation interruption and explicit rollback. No approval was requested or assumed in this pass.
3. **Source-quality acceptance:** upstream sequence semantics are undocumented in the inspected provider contract. Until another authoritative source contract or independently verifiable sequence becomes available, MIDAS must retain `UNSEQUENCED` status. The stale diagnostic correction is implemented in candidate source but waits for that approved transition.
4. **Full-scale test window:** a full replay is estimated to need about 48 minutes at the current 15% test quota based on older CPU cost, while recurring jobs caused admission/pressure failures. A quiet, admitted window or off-host verification host is needed; the current run did not prove cold startup or checkpoint speed.
5. **Research:** no decision is needed to keep routine, resource-gated research operating. A new unattended 48-hour campaign was explicitly not authorized and is not recommended until storage, recovery, and source-quality conditions improve.

## L. Production state and required verdicts

| Subsystem | Implemented in source | Tested in isolation | Tested in integration | Deployed | Verified in production |
|---|---|---|---|---|---|
| Host/API write and read optimizations | Yes, main `87edab0` | Yes, equivalent workload tests | Yes, 61-minute window | Yes | Yes; 89.6% fewer API write bytes/observation with throughput preserved |
| Veritas resource priority and admission | Yes, `44178fb` | Yes | Yes, scheduled work with Reality | Yes | Yes, scheduled qualifications completed |
| Reality capacity alert/cadence | Yes, current `project/reality` worktree | Yes, 14 tests | Current report/timer path | Timer installed; recorder unchanged | 30-day warning visible; runway still ~21.8 days |
| Reality data-quality/recovery candidate | Yes, `f2dc9c7` | Yes, documented 165 core tests and synthetic benchmark | Full-store cold recovery stopped; no realistic 60-minute feed endurance | No | No; recorder still runs old loaded code |
| Full archive staging boundary | Yes, main checkout | Yes, 14 focused tests; read-only source probe passed | One cold phase entered then stopped by CPU PSI | Tooling only | No full archive checksum/recovery receipt |
| Arena artifact-accounting optimization | Yes, main checkout | Yes, 25 usage/job tests; refined usage test 10/10 | No new heavy job by design | Source is available for future worker process | Not yet timed in a production job |

### Required verdicts

| Area | Verdict | Basis |
|---|---|---|
| Storage sustainability | **NOT READY** | The application budget has about 21.8 days remaining, below the 90-day objective. |
| Reality data quality | **DEGRADED** | Current books are fresh, but sequence is unverified, gaps/divergence exceptions exist, and the live error field is stale. |
| Reality full-scale recovery | **PARTIALLY VERIFIED** | Fixtures and isolation are verified; full archive cold/checkpointed recovery did not complete. |
| Heavy-research capacity | **CONDITIONALLY SUFFICIENT** | One bounded useful tournament and routine jobs coexist with recording; sustained training capacity is not certified. |
| Current MIDAS operations | **CONDITIONALLY READY** | Core services are healthy under measured normal load; storage runway and source quality remain operational constraints. |
| Project Frontier foundation | **NOT READY** | Storage allocation, full recovery, and source-quality limits remain unresolved; no additional live source has been measured. |
| New unattended 48-hour research campaign | **NOT READY** | It is not authorized in this mission; storage/recovery constraints and sustainable heavy throughput are not cleared. |

