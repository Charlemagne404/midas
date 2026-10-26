# Reality reliability and Frontier foundation handoff

2026-10-20. Engineering is isolated and committed; **production is unchanged**.

| Verdict | Decision |
|---|---|
| Reality engineering | **MOSTLY READY** |
| Production deployment | **REQUIRES MORE WORK**; a transition at the observed pressure/headroom is unsafe |
| Frontier foundation | **CONDITIONALLY READY**, for isolated development only |

## A. Executive summary

The candidate adds restart acceleration with a checked engine snapshot, an exact catalog prefix and mandatory rehashing of every covered source segment. Only the uncovered tail needs decompression and reconstruction. Corrupt, incompatible or stale checkpoints fall back to full verified replay; changed source bytes fail closed. Raw records, segment format, historical checkpoints, ordinals, source identities and scientific replay remain authoritative.

Recorder memory is more predictable: bounded HTTP streaming replaces eager response buffering, frame metadata no longer retains decoded depth trees across socket awaits, record readers release decoding scratch before yielding, and append avoids copying an entire compressed payload into a second framing buffer. Existing streaming digest, bounded status projection, cohort pruning and stale-error clearing are included through the candidate's ancestry.

Recovery now preserves colliding quarantine artifacts, durably publishes quarantine directory entries before truncating the original, and treats finalization I/O failure as terminal. Resource admission is enforced in both deployment preflight and immediately before mutation. Status adds recovery provenance, resource measurements, queue semantics, resynchronization and timing scopes.

**165 regression tests passed**, covering recorder, operations, deployment, panel, recovery, calibration, dashboard, foundry, shadow and research scheduling. The final exact deployment verifier also passed **106 focused tests**, Ruff and a 40-file Mypy check; an extended 42-file Mypy check includes the capsule/benchmark tools. The complete wildcard run including model training did not finish safely: one hit its 300-second bound; a retry was stopped after pressure rose. No complete wildcard-suite pass is claimed.

The historical OOM allocation remains unknown. No new full-store recovery or 60-minute Reality endurance run was admitted. Current recorder headroom repeatedly failed the 4 MiB gate; host I/O pressure also exceeded the staging threshold during samples. A brief later passing sample does not establish sustained safety. The candidate has **not** been loaded by production.

Final handoff receipt: API **READY**, Veritas v2 **CURRENT** (16,374 segments, zero pending), recorder PID **863193**, 16/16 fresh books at ordinal **2,434,067**, sequencing unverified. The final resource receipt at 2026-10-20T13:14:37.460443+00:00 records **1,150,976 bytes** below MemoryHigh and rejects staging admission. Frozen campaign manifest/status hashes match the prior preserved identities. Candidate is synchronized on its dedicated branch; the live Reality checkout remains untouched.

## B. Root-cause investigation and lifecycle audit

Required prior reports were inspected alongside their linked OOM, full-store replay, pause, deployment and service evidence. Historical measurements are distinguished from fresh observations below.

| Lifecycle | Finding and disposition |
|---|---|
| Discovery/subscription | Polymarket discovery, exact condition/token mapping, public metadata and fee checks precede WS subscription. Cohorts are limited to 10 markets / 20 outcome tokens. Failed discovery is journaled as a connection gap. This remains venue-specific. |
| Reception/validation | WS messages are limited to 1 MiB. Raw receipt precedes engine reconstruction. Collector metadata and constraint extraction formerly parsed separately and left decoded objects in loop locals across awaits; one scoped helper now performs both and releases depth trees. Engine independently validates durable raw payloads. |
| State | Decimal books have a 10,000-level limit per side, current-cohort pruning, a 4,096-entry recent digest window and bounded coverage tracking. Duplicate diagnostics do not establish event identity or exactly-once delivery. |
| Backpressure | Synchronous append/fsync/reconstruction blocks the source loop; transport high-water marks pause reads. There is no unbounded application event queue. Slow append and queue configuration are reported; queue saturation is not falsely reported as measured queue occupancy. |
| Durability | Length + compressed-record SHA256 + zlib records, fsync before counter advancement, immutable finalized segments and atomic sidecars are retained. Header and compressed payload are now written separately without changing bytes. |
| Finalization | Segment bytes are fsynced and renamed, directory synced, then manifest atomically installed. Missing sidecars are rebuilt from complete source bytes. Finalization errors poison the writer. |
| Restart | Writer lock is acquired, open tails recovered, manifest counters validated, then recovery verified before writer activation. The old path replayed the complete history on every restart. Checkpoint acceleration removes prefix decoding while still hashing its bytes. |
| Reconstruction | Full replay continues to verify ordinals, segment metadata/digests and online engine digests. Prefix-only scientific replay still verifies the unconsumed tail. Accelerated recovery restores all internal state, including timing floors, counters, token mapping and duplicate window. |
| Consumers | Dashboard reads bounded status; replay/foundry/calibration/shadow consumers retain the framed-v1 format. New operational record kinds are ignored by the engine except for receipt time, as other diagnostic records already are. Frozen Veritas and campaign code is untouched. |

**Confirmed unnecessary retention/allocation:** complete HTTP bodies before limit checks; repeated decoded WS trees; compressed-payload framing copy; compressed and raw JSON scratch retained in suspended record generators; historical full-state digest materialization. The latter was already corrected in the candidate ancestry and is measured against the loaded historical implementation here.

**Confirmed historical failure mechanism:** the Oct 19 kernel evidence records `CONSTRAINT_MEMCG`, a 768 MiB limit, about 749 MB anonymous memory and heavy swap/reclaim churn. The triggering path was swap-in charging. It does not identify a Python allocation or establish whether the victim was replaying or recording. Neither a leak nor a definitive OOM fix can be claimed.

Single points of failure remain: one writer, filesystem and synchronous persistence path per root; one specialized connection lifecycle per collector. They fail visibly and preserve evidence. Host/storage pressure can still affect separate processes. This mission adds no multi-venue adapter or speculative orchestration framework.

## C. Memory analysis

### Fresh production observations

In the final 50-second passive receipt (15:03:08–15:03:58 CEST), PID **863193** remained unchanged with **one** historical restart. Its margin below `MemoryHigh=738,197,504` was **876,544–1,490,944 bytes** (0.84–1.42 MiB). `high` increased from **10,210 to 10,212**; max/OOM/OOM-kill remained zero. All six samples had 16 fresh books and advancing ordinals (2,432,917 → 2,433,011). Memory PSI avg10 was zero during this receipt; I/O full PSI ranged 1.16–9.85%.

An earlier mission receipt also captured a normal refresh entering `AWAITING_DATA`; that is not evidence of a process restart. Process RSS/anonymous/private-dirty, cgroup breakdown, process I/O and full status samples are retained in the receipts. A later spot sample had 593,813,504 anonymous bytes and 120,233,984 file bytes. Anonymous memory rose during the overall session while file cache was reclaimed. These observations do not locate the retained objects or prove a leak. No production heap tracing, signal, cache clearing or limit change was performed.

### Controlled memory model

Separate processes build explicitly synthetic two-outcome books. Heap figures are tracemalloc retained bytes; RSS includes Python, allocator and imports. All models use the same source semantics and deterministic levels; they are not venue observations.

| Markets | Depth per side | Candidate retained book heap | Candidate digest extra peak | Loaded `2b83818` digest extra peak |
|---:|---:|---:|---:|---:|
| 1 | 100 | 105,715 B | 13,417 B | 92,664 B |
| 10 | 100 | 1,042,441 B | 38,831 B | 860,372 B |
| 1 | 1,000 | 983,635 B | 71,045 B | 884,008 B |
| 10 | 1,000 | 9,821,065 B | 96,459 B | 8,320,212 B |
| 1 | 10,000 | 9,503,795 B | 647,045 B | 8,337,176 B |

Intermediate measurements cover 4 and 8 markets at depths 100 and 1,000. The ten-market/depth-1,000 digest temporary allocation falls about **86×**; retained book heap is essentially unchanged, as expected. Maximum candidate RSS in these scenarios was about **59.3 MiB**. This is not production RSS or a reproduction of the OOM.

Within these fixtures, retained storage is about 238–264 bytes per level, including the scenario's metadata. For this binary-market collector there are four sides per market. A hypothetical fully populated 10-market/10,000-depth state therefore suggests roughly 95–106 MB of traced book storage. **That combination was not measured**, and Python dictionary resize, decimal shapes, payloads and allocator high-water marks make it an estimate rather than a deployment budget.

Other terms must be budgeted separately:

- Subscriptions: 2 tokens per current binary market; this relationship cannot be generalized to other venues.
- Transport: configured `max_queue=32` is a WS frame high-water mark, not a strict count of complete decoded messages or measured occupancy. Fragmentation, an in-flight message, socket buffers and text representation add overhead. `max_size=1 MiB` remains enforced.
- Event frequency raises CPU/fsync demand. If arrival outpaces persistence, transport reads pause; eventual disconnects retain continuity uncertainty. The real localhost 100-frame slow-writer regression verifies bounded transport configuration and preservation of that finite burst, not arbitrary overload losslessness.
- Timing samples remain capped at 1,024; recent event digests at 4,096. Cohort tracking is pruned. HTTP wire bodies are capped at 2 MiB, requested without compression, and total request lifetime is bounded (20 seconds normally, up to 30; comparison uses its shorter timeout). Oversize responses preserve the observed prefix in an explicit `http_response_limit` record. Independent comparison limits do not falsely invalidate the WS book stream.
- Replay retains current engine state plus a record; scientific incremental readers spool at most 8 MiB before temporary disk spill. The fast path hashes using bounded file-digest buffers.
- Recovery checkpoint files are capped at **32 MiB**. Decode temporarily holds JSON structures plus restored Decimal books; full-archive peak restore/save memory is still unmeasured. Save reserves space for the entire temporary bound alongside the previous checkpoint. This is a file bound, not a claim of 32 MiB heap use.

Multiple collectors should initially have separate processes, roots, locks and cgroup budgets. Summing the measured book term is useful capacity arithmetic; it is not evidence that total source RSS or cgroup cache charging scales linearly. Measure each source's event format, depth and recovery workload before deployment.

## D. Startup and recovery performance

### Architecture and trust

`recovery-v1.checkpoint` is an optional accelerator, never the archive's authority. It contains a checksummed exact engine snapshot, catalog prefix, engine digest and implementation fingerprint. It is atomically written/fsynced at finalized boundaries, every five minutes during recording and at clean shutdown; startup bootstraps it after verified full replay when absent. Checkpoint failures are explicit status diagnostics and do not justify continuing after raw persistence failure.

On restart:

1. Acquire the existing exclusive writer lock and recover complete open-tail records.
2. Validate all manifest identities, sizes, counters and contiguous ordinal ranges.
3. Check checkpoint framing, checksum, size, implementation and exact catalog prefix.
4. Restore internal engine state and compare its digest/cursor.
5. **Hash every prefix segment** against its pinned digest. Source mismatch is fatal.
6. Replay only uncovered finalized segments, verifying their metadata, ordinals and online checkpoints.
7. Compare engine and durable store ordinal, enforce retention horizon, activate writer, durably record `process_start`, restore subscriptions and wait for fresh initial snapshots.

Missing/stale/corrupt acceleration metadata causes full verified replay. Its fallback reason is reported. It cannot silently turn unverified state into healthy collection. A new process always records an interruption gap and requires fresh initial snapshots; restored books never imply continuous source sequencing.

Checkpoint checksums protect accidental corruption, not an adversary able to rewrite both archive and all checksums. Changing reconstruction/storage/replay/recovery source invalidates the accelerator. No existing raw format migration is required. Existing archives without it still boot correctly, with the old full-replay cost.

### Measured disposable startup

Final code's controlled archives use captured fixture payloads repeated as explicitly synthetic workload. Each row includes deferred `Store` setup, verified recovery, writer activation and the **first new fsynced gap**. It is a minimal durable-resumption probe, not the complete collector entry point: it omits the collector's initial accelerator republish, DNS, venue subscription and first live frame. Those costs must be included in full-scale collector acceptance.

| Finalized segments | Bytes | Full replay to first durable record | Checkpoint path to first durable record | Checkpoint path CPU | Peak startup RSS |
|---:|---:|---:|---:|---:|---:|
| 9 | 455,415 | 0.2470 s | 0.0174 s | 0.0070 s | 22,884 KiB |
| 33 | 1,684,516 | 0.9383 s | 0.0240 s | 0.0145 s | 23,340 KiB |
| 129 | 6,604,343 | 3.7092 s | 0.0451 s | 0.0400 s | 23,624 KiB |

The fast path hashed **all** segments/bytes in each row and reconstructed zero prefix segments. Separate tests add a verified tail and compare every engine field with complete replay. Read/write syscall bytes, physical I/O counters and CPU are in `benchmark.json`; warm cache can make physical reads zero. These measurements are **too small to establish full-store boot time**.

### Real archive evidence and uncertainty

The prior 16,110-segment / **4,294,762,665-byte**, 2,414,595-ordinal snapshot completed the older candidate's full replay in **428.431 CPU / 432 wall seconds**, without a CPU quota, under 768 MiB hard memory and no swap. Peak cgroup usage was **704.48 MiB**, with 5,405 high events and no OOM. The reporter then failed; the final state digest was not retained. This is prior replay-return evidence, not a clean run of this candidate.

At production's unchanged 25% CPU quota, those CPU seconds imply about **28.6 minutes plus setup/reconnect**, superseding the earlier low-confidence 66-minute estimate. The exact new candidate's cold bootstrap and checkpoint path have not been measured at full size.

A defensible model is:

`T_resume = catalog setup(N) + checkpoint decode/current-state validation + hash(B) + verified tail replay + checkpoint save + writer activation + discovery/subscription/snapshot time`.

Full replay instead pays historical decompression, event reconstruction and every online checkpoint digest. The fast path's byte hashing still scales with archive bytes and catalog setup with segment count. Disk throughput/cache state, thousands of file opens, quota, tail composition and checkpoint restore dominate the uncertainty; extrapolating the 6.6 MB result into a production ETA would be misleading.

A prebuilt capsule from an immutable full-size snapshot can avoid cold bootstrap during the authorized transition. `scripts/reality_recovery_snapshot.py` prepares this **without production writes**, rechecking headroom/host pressure every five seconds and terminating only its own staging process if admission fails. It has not been run against the full archive under this mission's unsafe conditions.

Time to subscription, first newly durable record/frame and startup duration are now explicit status fields. Full-health and live first-frame latency still require admitted full-scale staging and production confirmation.

## E. Collection and durability

- Raw WS observations remain recorded before reconstruction. Raw repeated events remain raw repeated events; no sequence or uniqueness guarantee is invented.
- Heartbeats, bounded exponential reconnect backoff (1–60 seconds), successful-cohort backoff reset, snapshot deadlines and subscription restoration remain intact. Old errors clear after successful non-heartbeat recovery; cumulative failure and durable gap history remain.
- Health distinguishes recovering, reconnecting, resynchronizing, no events, stale, backpressured, receiving, stopped and failed. Resource constraint is an independent flag with cgroup/host measurements. Process counters and durable lifetime record-kind totals have explicit scopes.
- All meaningful persistence errors are terminal. A write/finalization failure can leave a record durable before local reconstruction; restart replay consumes the durable truth rather than inventing an acknowledgement.
- Complete crash-tail records are recovered. Incomplete bytes are retained as `.tail`; collision names preserve earlier artifacts. Their directory entry is synced **before** truncation. Checksum-corrupt complete records remain a hard failure with original bytes preserved; they are not silently skipped or repaired.
- Partially written manifest temporary files are not authoritative; finalized segment bytes allow missing-sidecar reconstruction. Checkpoint temporary files are disposable and ignored on recovery; prior atomic checkpoints survive failed replacement.
- Storage budgets, 20 GiB production reserve, retention horizon and source continuity limits remain enabled. No historical artifact is deleted to create capacity.

## F. Architecture and scalability

Reusable infrastructure now has stronger bounded HTTP transport, source-independent framed durability, separate root ownership, checked recovery and Linux resource admission. Simulated independent roots demonstrate that one exhausted storage budget does not stop the other root's appends.

The collector/engine still encode Polymarket binary outcomes, bounded prices, condition IDs and unsequenced lineage. Those semantics must remain in that adapter. Future sources need their own timestamp/sequence contracts and faithful event formats, roots, health and resource budgets. Separate processes/cgroups are the supported containment boundary today; there is no demonstrated fair multi-source loop in one process. Shared disk and host pressure remain common failure domains.

**No additional venue, market cohort, strategy, Frontier implementation or research campaign was introduced.**

## G. Implemented changes and identities

Candidate branch: `fix/reality-foundation-20261020` in `/home/charlie/midas-reality-reliability`.

| Commit | Content |
|---|---|
| `b06eff8` | Verified checkpoint recovery, bounded transport/parse lifetimes, framing scratch reduction, tail durability, resource preflight and fault tests |
| `3b332d0` | Reproducible synthetic benchmark and passive observer |
| `92e9648` | Additional guard confining benchmark writes to disposable synthetic `/tmp` roots |
| `f2dc9c7` | Fail closed on any staging monitor exception; subprocess test proves only the disposable builder terminates |

Deployment target: **`f2dc9c7`** (full identity in `verification.json`). Its ancestor `b0610c1` includes stale-error clearing; `c833200` and `b8220e3` are ancestors. No defect was bypassed by stacking onto an unvalidated storage path: replay/count/tail cases were rerun, ordinal validation was strengthened, and finalization failure behavior corrected.

Core files: `collector.py`, `observation.py`, `storage.py`, `replay.py`, new `recovery.py`, `transport.py`, `resources.py`; deployment/snapshot tools and `tests/test_reality_recovery.py`, `tests/test_reality_deployment.py`. Benchmark/observer tools are separate from runtime imports.

Production checkout remains `c833200`; the recorder began before that checkout revision and still runs the historical `2b83818` code identified in the incident evidence. The Reality interface API is also older than the candidate. Veritas runtime remains its immutable installed release. None of those checkouts/runtime paths was updated.

## H. Failure and compatibility testing

Final pinned core regression: **165 passed**, one existing Starlette/httpx deprecation warning. Scope excludes `tests/test_reality_training.py`; broad attempts including it were not completed, as documented below. Ruff passes on changed source/tools/tests; Mypy passes **42** runtime/tool files; `git diff --check` passes.

Cases include clean startup, lifetime counters, source interruption/reconnection, stale-book initial resync, finite burst under slow writes, immutable replay, prefix-tail corruption, discovery mapping, existing dashboard/foundry/calibration/shadow consumption and clean shutdown. New cases exercise:

- Exact restoration of **every internal Engine field**, mandatory prefix hashes without prefix decode, uncovered-tail equivalence and repeated restart.
- Truncated/checksum-corrupt/oversized/incompatible/wrong-prefix checkpoint fallback; source corruption still fatal.
- Failed checkpoint replacement preserving the prior snapshot; **actual subprocess SIGKILL** before replacement.
- **Actual subprocess SIGKILL** after a fsynced record plus partial tail; durable counter recovery, preserved partial bytes, and a second restart without duplication.
- Missing sidecar after finalization, manifest overlap rejection, quarantine collision preservation and directory-sync-before-truncate ordering.
- Terminal writer after auto-finalization failure; wire bytes unchanged by split framing writes.
- Bounded HTTP response closing after its observed prefix, unsupported compression rejection and total trickle deadline.
- Explicit resynchronization status, per-root failure containment, strict 4 MiB admission boundary and deployment rejection **before** configuration/service mutation.
- Tracemalloc regression bounding retained memory while a large-record iterator is paused.

An actual OS OOM was not injected; SIGKILL covers abrupt process loss without inducing host pressure. Real ENOSPC/EIO at every filesystem syscall and a full-volume interruption during checkpoint restore remain untested. OSError injection covers selected boundaries, not every storage failure mode. Stale but internally valid sidecar metadata remains subject to full record validation on cold replay or exact prefix binding + rehash on accelerated replay.

Broad wildcard verification first hit its 300-second bound; a single-threaded retry was stopped after elevated host pressure. Logs retain the incomplete progress and unit outcomes. This is a resource/test-scope limitation, not a passing model-training regression or proof of a new model defect. The later 165-test run avoids model fitting and completed in 25.13 seconds. Changes after its collection affect only the benchmark root guard and staging monitor failure handling. A direct negative check confirms protected benchmark roots are rejected before I/O; a subprocess fault test confirms a failed monitor terminates only its own builder and leaves source bytes unchanged. The exact release verifier was rerun after these changes.

## I. Endurance verification and resource limits

**No new 60-minute Reality endurance pass.** Six final recorder samples all fail the 4 MiB gate. I/O full PSI reached 9.85%, above the new 2% admission limit. Earlier broad-test pressure prompted stopping only the owned test unit. The older 63m45s Arena/32-transition result remains valid historical Arena evidence, not Reality endurance evidence.

Synthetic benchmark ran under a 128 MiB hard cgroup cap, 96 MiB high, zero swap, one-CPU cap, low priority and 120-second bound; Python workers also had 256 MiB address-space and 90 CPU-second limits. Final tests had 256 MiB hard / 224 MiB high, zero swap, one CPU, 32 tasks and 90 seconds. These are disposable-unit settings; **production safeguards were not raised**. The final benchmark used 28.408 CPU seconds. Long-run queue growth, reconnection frequency, memory slope, quiet-market behavior and full-depth checkpoint allocation still need sustained admitted measurement.

Evidence: [benchmark](evidence/reality-foundation-20261020/benchmark.json), [operations](evidence/reality-foundation-20261020/operations.json), [regression](evidence/reality-foundation-20261020/regression.log), [unit history](evidence/reality-foundation-20261020/staging-units.log), [verification identities](evidence/reality-foundation-20261020/verification.json).

## J. Production deployment procedure — NOT executed

### Preconditions before asking for a protected transition

1. Preserve the candidate branch at `f2dc9c7`; resolve its full commit and package fingerprint from `verification.json`. Require clean candidate, Reality, main and Veritas worktrees. No installation into the live import path until the approved stop window.
2. Require sustained recorder margin **at least 4 MiB**, host available memory >=2 GiB, CPU PSI some avg10 <20%, memory PSI some avg10 <0.5%, I/O PSI full avg10 <2%, no new max/OOM events, and >=20 GiB free disk reserve **after** budget commitments. Nearly full swap is a monitoring signal, not by itself proof of active pressure.
3. **4 MiB is an admission floor, not a measured adequate startup reserve.** Prior full replay crossed MemoryHigh, current natural margin varies by several MiB, and snapshot restore adds allocations. Prefer at least 64 MiB sustained recorder margin before heavy staging, plus its own cgroup cap; validate a workload-derived startup reserve from the full-size test. Do not weaken the 4 MiB floor or raise production memory limits.
4. Once these conditions are safe, run one bounded full-size capsule build against the existing immutable 4.29 GB snapshot (or a newly pinned finalized-only snapshot), then a disposable full-size fast-start/first-durable-write probe with an uncovered tail. Require complete digest/counter equality, all source hashes, peak memory and I/O readings, and successful first durable record. Cold fallback remains a separate measured requirement.
5. Run a >=60-minute isolated localhost-feed endurance scenario, cycling segment finalization, disconnect/reconnect, incomplete snapshots, backpressure and restart. Use only clearly labelled simulation/copied observations. Preserve counters/digests, queue diagnostics, cgroup anon/file/PSI and source freshness at 5–10 minute intervals. Stop the owned test on pressure or recorder gate failure. No production signal.
6. Run the exact local deployment `verify` command against the final candidate and validate a freshly built canary. The old canary's implementation fingerprint cannot satisfy a new candidate. Refresh receipts rather than changing their expected hashes. The automated active-production `preflight/apply` pair is not the execution mode for the manual source replacement below.

Example full-size capsule build **only after admission** (not a deployment command):

```bash
cd /home/charlie/midas-reality-reliability
systemd-run --user --unit=midas-reality-foundation-full-capsule \
  --property=MemoryHigh=704M --property=MemoryMax=768M \
  --property=MemorySwapMax=0 --property=CPUQuota=100% \
  --property=Nice=19 --property=IOSchedulingClass=idle \
  --property=TasksMax=8 --property=RuntimeMaxSec=1200 --property=Restart=no \
  --working-directory=/home/charlie/midas-reality-reliability \
  --setenv=PYTHONPATH=/home/charlie/midas-reality-reliability/packages:/home/charlie/midas-reality-reliability \
  /home/charlie/midas/.venv/bin/python scripts/reality_recovery_snapshot.py \
  --snapshot /tmp/midas-reality-fullstore-candidate-c833200/replay \
  --output /tmp/midas-reality-foundation-full-capsule
```

Output must be new/empty. A capsule alone is **not** the full startup/endurance acceptance. The builder's five-second watchdog rechecks the protected PID and resource gates; it signals only itself on failure. Its package fingerprint must match the final candidate.

### Controlled transition after all gates pass and explicit approval

1. Record then-current PID, service/config/drop-in hashes, source and candidate hashes, latest finalized checksum, catalog/counts, open-tail identity, cgroup events and source freshness. Recheck frozen campaign identities from the evidence receipt. Preserve current unit/config and `c833200` as rollback source. The shared `project/reality` branch can fast-forward to `f2dc9c7`, but **do not do so while the protected process is running**.
2. Obtain explicit approval for **one graceful stop/start**, expected interruption derived from the full-size test, and its observation-gap implications. Approval to pause shadows does not authorize this action.
3. Install the existing one-shot `Restart=no` guard, reload systemd and verify all original production limits remain: 704 MiB high, 768 MiB maximum, zero swap, 25% CPU, 32 tasks, 128 FDs and 45-second stop timeout. Stop once with SIGTERM. Preserve any incomplete tail after timeout; no automatic retries.
4. After the process exits, fast-forward `project/reality` to the reviewed target. Preserve the explicit production JSON configuration unchanged. Install the reviewed unit (SHA256 `0afb3154bd51f5e016768f583ea792e27b882f0e5ddc6651be3bcbb890a8dd94`) while preserving existing reviewed resource drop-ins. The installed base file still says 384/512 MiB but effective user-control overrides are already 704/768 MiB; matching the template must not change effective limits. Copy the validated accelerator to the recording root using an fsynced temporary file and atomic rename; existing raw/manifests are not migrated. If a capsule is absent/incompatible, expect full replay and use the separately measured cold-start window. Do not remove raw evidence to make an index match.
5. Verify imports resolve to `/home/charlie/midas-reality/packages/midas/reality` and hashes match `verification.json` (including recovery/transport/resources). Reuse only a fresh, matching local `verify` receipt. **This source-changing rollout uses the manual one-stop/one-start mode described here. Do not run `preflight` or `apply` after stopping:** the existing automation requires an active recorder and matching production source before its own restart; it cannot perform this source replacement while keeping the live checkout untouched. Its guards must not be bypassed. Pre-stop checks for this manual packet are the pinned candidate/canary/capsule receipts, recorded existing source/unit identities, `require_safe` admission, preserved counters/checksums and explicit approval. The operator performs the exact subsequent health checks below; there is no second start hidden in a tool invocation.
6. Before the one start, recheck disk commitments, host PSI and preserved source catalog. Start once with automatic restart disabled. Record the first new fsynced record, restored subscription, first non-heartbeat frame and full fresh-book status. Require status <=10 seconds old, 16/16 fresh expected books for the existing eight-market configuration, advancing ordinals/lifetime counts, correct recovery mode, zero sequence-verification claim, no source checksum errors and no new max/OOM events.
7. Keep the existing **60-minute maximum readiness ceiling** until full-size measurements establish a smaller justified bound, followed by five continuous minutes of advancing healthy collection. This ceiling is an abort bound, **not** an expected fast-start duration. Current measured evidence cannot supply a safe exact new-candidate interruption ETA. Cold planning remains ~28.6 minutes plus overhead from the older full replay. Do not approve a claimed seconds-long interruption from microbenchmarks.
8. Abort on changed identities/configuration, inadequate reserve/pressure, failed checksums/ordinals, writer-lock conflict, failed persistence, new max/OOM events, stale nonadvancing status, repeated process ownership changes, or readiness timeout. Preserve all raw/tail/manifests, unit journal and last verified ordinal. Leave restart disabled; no automatic rollback/retry.
9. After the stable health window, remove only the temporary one-shot drop-in and restore the prior bounded restart policy. Monitor at 5, 15, 30 and 60 minutes, then 6 and 24 hours: anon/file split, high/max/OOM deltas, host/worker PSI, swap movement, append/checkpoint latency, freshness, gap frequency and durable throughput. Verify newly finalized checksums and replay across the transition with the source gap visible.

**Rollback:** preserve any records produced by the candidate. Do not reset counters, truncate history, delete recovery evidence or restore an old data directory. Code rollback to `c833200` ignores the optional accelerator and performs full replay. A rollback start requires separately approved interruption and its own measured memory/time budget. If storage integrity fails, stop and investigate rather than overwriting source bytes.

This is an execution handoff with unmet prerequisites, not a request to restart under current conditions. No production unit/configuration was installed, reloaded or changed.

## K. Outstanding blockers

- Sustained recorder resource headroom; observed repeated MemoryHigh proximity and reclaim remain unresolved in the loaded old process.
- Exact candidate full-size capsule creation/restore/tail replay, peak startup/save memory, CPU/I/O and first-durable-record/subscription/full-health measurements.
- New Reality endurance and subsequent production health window; the Arena endurance result cannot substitute.
- Complete training-inclusive wildcard regression under an appropriately admitted environment; the recorded 165-test compatibility scope is narrower.
- Historical OOM allocation attribution remains unknown. The implemented reductions mitigate credible paths without proving that original incident fixed.
- Explicit protected-recorder authorization and approved execution mode/window, after the preceding gates. An undeployed candidate is not production verification.

## L. Frontier readiness

| Decision | Verdict and evidence needed |
|---|---|
| Begin isolated Frontier development | **CONDITIONALLY READY**: separately authorized work can use independent roots/processes and honest source semantics. This mission does not begin it. |
| Deploy additional market collectors | **NOT READY**: deploy/verify current Reality first; measure new source formats, depth, rate and resource budgets independently. |
| Another unattended 48-hour campaign | **NOT READY**: requires Reality production recovery, full-scale/endurance evidence, resource stability and campaign-specific admission. |

The candidate is a materially stronger foundation. It is not evidence that week-long operation, arbitrary market depth, or several additional collectors will fit the existing host.
