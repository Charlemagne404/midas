# MIDAS Reliability and Efficiency Pass

**Scope:** reliability engineering only. No Atlas or Frontier work, new research campaign, strategy development, trading capability, or protected production service action was started.

**Verdict: MOSTLY READY**

## A. Executive summary

The code now has durable row-level tournament checkpoints, bounded worker queue waits, stale-worker reconciliation, idempotent job admission, linked retry attempts, pressure-correlated resource cancellation, periodic artifact-accounting reconciliation, and explicit execution, shutdown, and report deadlines. Reality status now separates process-local counters from durable lifetime record counts; restart recovery validates manifests and retains incomplete tails. These changes are implemented and tested in isolated fixtures.

The measured Arena artifact-usage index reduced a warm observation from a 0.166247-second full tree scan to 0.000206 seconds at the median over 20 observations (about 806× for that operation). A representative tournament recovery fixture reused seven of eight completed evaluation rows and recomputed one. These are narrow measurements; they do not prove whole-job or campaign speedups.

The changes are **not deployed**. Reality changes are in the `midas-reality` worktree and require an approved recorder restart to take effect. The OOM cause remains unproven, no 60-minute endurance run was safe on the observed host, and the failure suite does not yet exercise every requested crash boundary with real process kills. Those limits keep this pass at MOSTLY READY.

## B. Architecture findings and priorities

The assessment at `data/autonomy/48H-001/48H_001_COMPREHENSIVE_ASSESSMENT.md` and its source artifacts show that the 48-hour run ended PARTIAL, produced 15 completed jobs alongside 20 cancelled attempts, two failed attempts and one interrupted attempt, and published its report after the grace period while a Director worker was still running. It recorded about 11.917 worker CPU-hours, about 7.113 CPU-hours on attempts not classified as complete, and only 0.146 optimizer CPU-hours. One artifact-accounting path spent about 4,319 of a 5,400-second job in fallback scanning. The recorder restarted after a cgroup OOM; its process counter reset even though the durable record stream survived. Those observations guided the order below.

| Priority | Finding and root cause | Impact and response |
|---|---|---|
| Highest | Tournament output was only reusable at coarse stage boundaries; incomplete evaluation work could be repeated. | Added stable evaluation identities, integrity-checked row checkpoints, and recovery of missing rows. |
| Highest | Worker queue time counted against execution limits; queued workers repeatedly published progress and could run accounting; a dead supervisor could leave stale in-memory state. | Bound queue waits, start execution time after acquiring the Arena lease, avoid queued scans, and persist interruption after checking the execution lock. |
| Highest | Campaign admission could be lost between creating a job and publishing its ID; retries and resource cancellations could repeat without clear lineage or a terminal stop. | Reconcile durable admission keys after controller restart, link attempts, cap retry paths, and expose explicit resource/deadline blocks. |
| High | Campaign ticks repeatedly traversed Arena history; the old scheduler also rejected work based on total Arena size rather than available headroom. | Use a durable byte baseline plus conservative per-job allowances, periodic/pressure-triggered reconciliation, explicit global and per-job caps, and disk reserve checks. |
| High | Swap activity could be treated as danger even when memory PSI and available memory showed no pressure; worker swap growth was not pressure-correlated. | Admission now checks available memory, disk reserve and host CPU, memory and I/O PSI. Cancellation requires corroborating host or worker pressure for swap growth. |
| High | Report publication was not bounded independently from execution and shutdown. | Add an absolute execution cutoff, admission cutoff based on job and queue budgets, bounded shutdown grace, and bounded report-publication deadline with emergency terminal reporting. |
| High | Recorder process counters restarted at zero, and one status value could conceal whether recording was stale or merely slow. | Rebuild lifetime record totals from durable segment manifests and report receiving, no-event, reconnecting, stale, backpressured, recovering and failed states. |
| Unresolved | The kernel recorded a Reality cgroup OOM, but available evidence does not identify the allocation or demonstrate a leak. | Do not infer a leak or claim an OOM fix. Changes bound known queues and replay scratch, but production memory behavior still needs staged observation. |

Other audited safeguards retained: Arena heavy jobs serialize behind a worker lease; queued and executing worker states are distinct; completed tournament registration can be reconciled from its durable artifact; synthetic work can bypass only source-continuity gates, not host resource gates; and Veritas/model dependencies remain local to dependent work. The existing audited source-transition mechanism remains in place. This pass does not define a new separation between operational and methodology hashes; a changed source fingerprint may still prevent reuse, which is conservative for scientific integrity.

## C. Implemented improvements

### Durable jobs, scheduling and tournament recovery

**Problem addressed:** queued jobs consumed runtime and emitted excessive updates; stale supervisor state was not durably reconciled; duplicate submissions and retries could be ambiguous; interrupted tournament rows were recomputed.

**Implementation:**

- Arena jobs cap lease wait at 300 seconds, publish queue state at most every 30 seconds, and apply the configured execution timeout only after owning the worker lock. The systemd runtime bound includes queue time plus execution time.
- Worker inspection checks the execution lock before recording `INTERRUPTED`; locks remain kernel-managed and are released when a process exits. Retries must reference a terminal failed, cancelled or interrupted parent and carry an attempt number.
- Per-job and global artifact caps, a 2 GiB free-space reserve, and remaining per-job artifact allowance are enforced inside the worker as well as at admission.
- Scheduling uses active job IDs, `MemAvailable`, free disk and host PSI rather than a total-history-size threshold. Its diagnostic retains the specific gate reasons.
- Tournament identity includes evaluation inputs, dataset and source lineage. Each deterministic row records its model, episode, execution model and challenge-seed identity. Recovery validates the fingerprint and result, journal and scenario digests, quarantines invalid partial rows, detects duplicates or gaps, and computes only missing rows. Registration can be reconciled after a crash between artifact completion and registry update.

**Files:** `packages/midas/arena/jobs.py`, `packages/midas/arena/scheduling.py`, `packages/midas/arena/tournaments.py` and their three `tests/arena/` suites.

**Risks:** stricter global and disk budgets can block work as the artifact tree grows; the limits are explicit and failures preserve evidence. Tournament reuse remains bound to source identity and therefore may be invalidated by code changes.

### Campaign retries, accounting and finalization

**Problem addressed:** the campaign could repeat health cancellations, miss a worker created just before a controller crash, start work too late to finish, or remain open while finalization ran.

**Implementation:**

- Health backpressure cancellations stop after three attempts and become `BLOCKED_RESOURCE`. Normal retry attempts link to their prior job and retain attempt history.
- Host swap activity cancels only when available memory or PSI corroborates pressure. A worker swap delta also requires worker memory PSI, a memory-limit/OOM event, or critical host pressure.
- Controller restart reconciliation binds an `ADMITTING` step to its durable admission key before deciding to retry or stop it. Failed admission reconciliation becomes explicit blocked state.
- Campaign artifact accounting persists a scan baseline and counts new or active jobs against their full artifact allowance until reconciliation. Stable trees rescan after six hours; near-headroom rescans are at least five minutes apart. The controller no longer needs a full Arena walk on every tick.
- Last admission time is derived from the campaign execution deadline minus the declared worker wall limit and queue allowance. Deadline handling stops admission, requests cancellation, waits through bounded grace, then finalizes. A separate 300-second report-publication budget produces `FINALIZATION_FAILED` emergency records if finalization cannot complete.
- Controller timer source is set to a 30-second check interval, and the service timeout is 240 seconds. The timer and service files were not installed, reloaded or activated.
- Final validation reuses a durable recorded activation or bounded regression evidence rather than launching a long test suite at campaign end.

**Files:** `scripts/autonomy_48h.py`, `deploy/systemd/user/midas-autonomy-48h-001.service`, `deploy/systemd/user/midas-autonomy-48h-001.timer`, and `tests/test_autonomy_campaign.py`.

**Risks:** controller timing uses persistent absolute timestamps for restart recovery; system clock changes can affect those deadlines. Elapsed worker limits use monotonic time. The installed autonomy timer is currently inactive and disabled, so these service-file changes are source-only.

### Reality recorder durability and health reporting

**Problem addressed:** counters were process-local, so a restarted recorder could report zero despite durable history; replay could read a segment repeatedly; status did not distinguish a stale feed from an active but slow writer.

**Implementation:**

- Store startup reconstructs per-kind counts and ordinals from validated segment manifests. Counters increase only after writes are flushed and synced. Existing open-tail recovery preserves the incomplete bytes as a `.tail` artifact and recovers complete records.
- Segment description hashes while parsing rather than performing a separate file hash pass. Manifest replay verifies the immutable segment in one source pass, spooling at most 8 MiB in memory before spilling to temporary storage, then yields validated records. Prefix replay still verifies the unconsumed tail.
- Recorder status reports durable lifetime frame, gap and total-record counts separately from explicitly process-local frame and append/backpressure counters.
- Time spent in the durable append and reconstruction path over one second marks process-local backpressure. Collection health prioritizes stale/no-source state over a prior slow append, while retaining the backpressure flag and counter.

**Files:** `/home/charlie/midas-reality/packages/midas/reality/{collector.py,replay.py,storage.py}` and `tests/test_reality.py`.

**Risks:** counters reconstruct from sidecars, whose checksum and metadata are checked against segment content at startup. A missing or corrupt segment remains a hard integrity error. A one-second append threshold is a diagnostic threshold, not proof of sustained source health. No production memory ceiling or recorder settings were changed.

## D. Before-and-after performance evidence

| Measurement | Previous behavior | New behavior / evidence | Limit |
|---|---|---|---|
| Arena usage observation | Full `os.walk` across 55,879 historical files: median 0.166247 s. A campaign worker was documented spending 4,319 s in fallback accounting during a 5,400 s run. | Existing `UsageIndex` benchmark: median warm indexed observation 0.000206 s over 20 samples, about 806× for that operation; 2 index reconciliations, 0 fallback scans. Campaign controller now caches a durable baseline and conservatively budgets active/new jobs. | Warm-cache, host-specific microbenchmark. Not a whole-job speedup. Controller scan-frequency reduction is structural, not separately timed end-to-end. Benchmark: `docs/PROMETHEUS_USAGE_INDEX_BENCHMARK.json`. |
| Interrupted tournament | In-flight evaluation rows could be lost at the Director stage boundary and recomputed. | Fixture interrupted at 7/8 completed rows; recovery reused seven and computed one, with the same final result as the uninterrupted deterministic fixture. | Injected at a row boundary in a disposable fixture; not an OS-level SIGKILL during a row write. |
| Reality manifest replay | Separate hash, metadata/parse and yield passes could reread segment bytes multiple times. | One source pass validates digest and record metadata, then validated content is replayed from bounded spool storage. Structural regression asserts no standalone `file_hash` or `describe` pass. | No wall-clock benchmark over protected Reality archives was run. Replay decompression still occurs twice; large spools can use temporary disk. |
| CPU / optimizer use | 48H-001 recorded 11.917 worker CPU-hours, 7.113 on non-completed attempts and 0.146 optimizer CPU-hours. | No honest campaign-wide after figure exists because no research campaign was run. Row recovery and queue accounting are directly tested; deployment and long-run resource collection remain. | Do not infer research throughput or total CPU savings from fixture tests. |

## E. Recovery and fault tolerance verification

The tests use disposable `tmp_path` artifacts and isolated worker calls. Relevant cases include:

- Worker cancellation preserves terminal state and source snapshot; a missing/dead supervisor persists `INTERRUPTED`; duplicate runner ownership is rejected by the worker lease.
- Duplicate admission keys return the same durable job or reject changed configuration/retry-parent identity. A controller restart reconciles a job created before its step ID was published.
- Retry lineage rejects a nonterminal parent, increments attempt number and preserves prior attempts. Repeated resource cancellations enter a terminal block.
- Tournament recovery reuses seven of eight valid rows, quarantines a corrupt checkpoint, rejects mismatched digests, and reconciles a complete artifact whose registry update was interrupted.
- Artifact budget, global cap and disk-reserve exhaustion fail explicitly without deleting historical evidence. Usage-index tests cover overflow/watch failure reconciliation and exact fallback behavior.
- Campaign fixtures reach the execution deadline, request worker shutdown, finalize after grace, leave too-late steps unadmitted, and publish a terminal emergency report when report generation fails.
- Resource tests distinguish swap occupancy/activity from memory pressure and verify a worker swap increase alone continues, while worker PSI corroboration cancels.
- Reality fixtures reopen a store and reconstruct lifetime counts, recover incomplete tails, verify segment integrity including a prefix replay's tail, and distinguish stale, reconnecting, no-event and backpressured states.

**Not yet fault-tested with a real kill:** process death during the checkpoint file's atomic replacement; actual controller SIGKILL in the admission/report-write windows; real inotify kernel queue overflow/watch exhaustion on the production tree; upstream socket outage against a staging recorder; and OS-level OOM. Unit fixtures cover related recovery logic but are not substitutes for these process-level tests.

## F. Recorder reliability

The historical assessment supports a cgroup OOM and a ten-second systemd restart, but not a proven heap leak or a complete record of the OOM allocation sequence. The recorder keeps bounded sample history (`deque(maxlen=1024)`), bounded WebSocket queue configuration and current book state; no unbounded in-memory frame queue was identified in the inspected path. Startup reconstructs record totals from durable sidecars. Source sequence verification remains explicitly false for unsequenced data, and segment integrity failures remain fatal.

The storage code and tests changed in the separate Reality worktree, not the production checkout. The production recorder, shadow services and raw records were left running and untouched. Memory boundedness under a day-scale live workload and the original OOM cause remain unverified.

## G. Resource protection and host state

At **2026-10-20 00:12 CEST**, after the targeted tests, the host had about 16.67 GB RAM, about 7.67 GB available, and 4.295 GB of 4.295 GB swap occupied. Memory PSI was zero (`some` and `full`); CPU PSI `some avg10` was about 64.58%, and I/O PSI was `some avg10` 2.10% / `full avg10` 0.46%. Root filesystem had about 198.94 GB available. Reality recorder and shadow services were active; Reality successor and autonomy service/timer were inactive.

The high CPU PSI, full swap occupancy and nonzero I/O full pressure made an additional 60-minute compute endurance workload an inconsiderate and unsafe server use. No such workload was started. The memory PSI and available-memory figure show that swap occupancy alone did not indicate active memory pressure at the sampled moment. New-job admission is gated on host pressure and explicit disk/memory headroom; active workers retain cgroup bounds, with cancellation based on corroborated pressure and bounded retry count.

This is a host snapshot, not proof of sustained protection. No CPU, memory or swap settings were raised, and no memory-management operation was run.

## H. Operational verification

All times are **2026-10-20 CEST**. Tests ran with disposable fixtures; no campaign or production research job was admitted.

| Verification | Result |
|---|---|
| `tests/arena/test_jobs.py tests/arena/test_scheduling.py tests/arena/test_tournaments.py tests/test_autonomy_campaign.py` | **60 passed**, one existing Starlette/httpx deprecation warning; final run completed in 94.20 s. |
| `tests/arena/test_usage_index.py` | **9 passed** in 1.69 s. |
| Reality `tests/test_reality.py` in `/home/charlie/midas-reality` | **25 passed** in 13.43 s. |
| Ruff on all changed source and tests in both worktrees | Passed. |
| `git diff --check` in both worktrees | Passed before commit. |
| Cross-subsystem campaign fixture | Verified Director-to-tournament admission and next-round scheduling; this is a mocked staging fixture, not a live Arena endurance run. |
| 60-minute / multi-cycle endurance | Not run: host pressure and protected active services made it unsafe; no production campaign was started. |

## I. Remaining limitations

- The Reality OOM cause is unknown; no production memory profiling or restart has been performed.
- None of these commits is deployed. The Reality commit needs explicit approval before restarting the protected recorder service.
- No 60-minute endurance observation, real OS-level kill matrix, or multiday test was run.
- Campaign CPU totals can be reconstructed for retained attempts where systemd usage was sampled, but a process killed before its final cgroup sample may still lack exact final CPU accounting.
- Campaign artifact baseline reconciliation is conservative and periodic; external artifact writers can cause temporary overestimation or delayed discovery, bounded by per-job/global limits and reconciliation intervals.
- Tournament row recovery is coupled to dataset/configuration/source fingerprints. This preserves scientific correctness, but operational code changes can prevent reuse of prior rows.
- Existing controller code remains tied to the 48H-001 campaign identity and its report naming. The installed timer is disabled; future campaign identity generalization was not attempted in this pass.
- The one-second recorder append threshold is an operational indicator; it has not been calibrated against a representative production latency distribution.

## J. Readiness for the next phase

**MOSTLY READY.** The top reliability changes are implemented, focused tests pass, and no code-level critical blocker surfaced in these fixtures. Before starting the separately planned Frontier phase, deploy/review the campaign controller change as appropriate, obtain approval for a bounded Reality service restart to deploy `b8220e3`, then verify recorder counts and continuity after restart. Once the host has sustained low CPU/I/O pressure, run a minimum 60-minute isolated end-to-end cycle test covering admission, reusable training, checkpointed evaluation, finalization, dependent tournament, worker release and automatic next admission. Capture CPU, memory, swap activity, PSI, disk and forward progress throughout.

That readiness statement does **not** authorize Frontier development or a research campaign. Neither was started here.

## K. Git and deployment state

| Repository / commit | Changes | State |
|---|---|---|
| `/home/charlie/midas`, `3b96500` — `fix(arena): recover workers and checkpoint tournament rows` | `packages/midas/arena/jobs.py`, `scheduling.py`, `tournaments.py`; tests in `tests/arena/`. | Committed; tested in isolation; not deployed. |
| `/home/charlie/midas`, `c8124ef` — `fix(autonomy): bound retries and campaign finalization` | `scripts/autonomy_48h.py`, source systemd service/timer, `tests/test_autonomy_campaign.py`. | Committed; tested in isolation; systemd files not installed/reloaded; host timer remains inactive/disabled. |
| `/home/charlie/midas-reality`, `b8220e3` — `fix(reality): preserve recorder counters and bounded recovery` | Reality collector, storage and replay; `tests/test_reality.py`. | Committed; isolated tests pass; not deployed. A live Reality restart requires explicit approval. |
| Report commit | This report. | Added after code commits; no production effect. |

No historical campaign files, Reality source records, trained model artifacts, Arena or Laboratory history, Veritas records, Prometheus experiments or unrelated Continental services were changed. No production worker, timer or recorder was restarted. No deployment or production verification has been claimed.
