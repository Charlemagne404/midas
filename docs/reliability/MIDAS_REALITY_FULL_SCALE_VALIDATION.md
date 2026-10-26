# Reality full-scale validation and deployment handoff

2026-10-20 UTC. **Production was not stopped, restarted, upgraded, or reconfigured.**

## A. Executive summary

| Question | Verdict | Evidence |
|---|---|---|
| Full-scale recovery | **PARTIALLY VERIFIED** | Complete metadata inventory: 16,422 finalized segments / 4,354,241,444 bytes / 2,436,055 records. Three real segments (120,505 bytes) verified. Exact candidate full-store cold/checkpoint/crash matrix **not admitted**. |
| Production deployment | **REQUIRES MORE WORK** | First passive window had only 4.02–4.43 MiB below MemoryHigh; the attempted heavy run subsequently failed even the existing 4 MiB floor. Startup peak, downtime, and 60-minute endurance remain unmeasured. **Restart not recommended.** |
| Project Frontier foundation | **NOT READY** | Multiple independent collectors are not justified by catalog accounting and fixtures. Current recorder full-scale recovery, sustained memory budget, and endurance are still acceptance blockers. No Frontier work was started. |

The main objective is **not complete**. Stopping here follows the mission's explicit resource-gate fallback, not a passing full-store claim. There is a tested, executable recovery procedure for a later admitted window. No production memory limit was increased and no safety gate was weakened.

New evidence is in [evidence/reality-full-scale-20261020](evidence/reality-full-scale-20261020/). Historical candidate evidence remains in [the preceding handoff](MIDAS_REALITY_RELIABILITY_AND_FRONTIER_READINESS.md); its results are not relabeled as this run.

## B. Full-store recovery

### Verified current baseline

- Protected recorder PID **863193**, systemd start **2026-10-18 22:50:57 UTC** (October 19 00:50:57 CEST), one historical automatic restart. Same PID throughout this work.
- Loaded implementation is **`2b83818`**. Its reconstructed package fingerprint, `768868ad81265168305e1b7ed1e17d884a9b68ab03b96da63ed91a80680381a9`, matches the durable `process_start` record at ordinal **1,827,244**, and the checkout reflog at process start. This establishes loaded identity independently of today's checkout.
- Live checkout **`c83320000a085bf30490b4b76b425527fe8574f7`**, clean. Candidate **`f2dc9c7ece0656aa75d1fefc7a01f511a94079c5`**, clean, in `/home/charlie/midas-reality-reliability`, branch `fix/reality-foundation-20261020`. Veritas checkout was clean. None was changed.
- Effective limits: **MemoryHigh 704 MiB; MemoryMax 768 MiB; MemorySwapMax 0; CPUQuota 25% of one CPU; TasksMax 32; TimeoutStopSec 45**. Installed MemoryHigh/Max drop-ins override the old checked-in base unit's 384/512 MiB values. Use effective settings, not the repository base unit, when budgeting.
- MIDAS API `/api/health`: **READY**, Laboratory **READY**, paper checkpoint verified at 401,317 journal events. Veritas finalized-source v2 was **current**, zero pending segments; its later receipt accounts for 16,425 catalog entries, including two empty segments, through ordinal 2,436,217. Its independently running analysis is not candidate startup verification.

Receipts: [runtime identity](evidence/reality-full-scale-20261020/runtime-identity.json), [baseline](evidence/reality-full-scale-20261020/baseline.json), [later observation](evidence/reality-full-scale-20261020/final-observation.json).

### Precisely scoped archive boundary

[Inventory](evidence/reality-full-scale-20261020/inventory.json), 13:35:46.805–13:35:48.344 UTC:

| Item | Accounted value |
|---|---:|
| Finalized segments | 16,422 (two empty) |
| Finalized source bytes | 4,354,241,444 |
| Durable records / last ordinal | 2,436,055 |
| Frame records | 1,911,936 |
| Gap records | 9,523 |
| Online checkpoint records | 16,411 |
| Optional recovery accelerator | Absent |

All listed sidecars passed identity, size, kind-total and contiguous ordinal-range validation. No unmatched finalized segment was observed. The last pinned segment is `00000000000002436036-27a2b3fc718442f2b5f9893b0785da37.seg`, ending at ordinal 2,436,055; segment SHA256 is recorded in the inventory. Catalog SHA256 is `d239325352bb296807f440bb621cf28c8263e037358540aa32f8b1a3f006f831`.

Active file `00000000000002436056-b59ad614223c4915829c0f93e3163990.open`, observed at 1,996 bytes, was **excluded**, not copied while growing. Finalizations after the entry listing belong to a later boundary. The historical data was not modified, hardlinked, or bulk copied during this mission. This is a metadata boundary receipt, **not a retained byte snapshot or full checksum audit**.

### Required matrix status

| Test | Exact candidate, real full store | New disposable fixture evidence |
|---|---|---|
| A. Cold recovery | **DEFERRED: resource gate** | Verified cold reconstruction and checkpoint publication |
| B. Verified checkpoint | **DEFERRED** | All prefix bytes hashed; zero prefix segments reconstructed; full internal-state identity matches cold |
| C. Clean process restart | **DEFERRED** | Independent worker exit/start restores identical state |
| D. Corrupt/stale checkpoint | **DEFERRED** | Bad framing and valid-checksum incompatible identity fall back to verified cold replay |
| E. Interrupted reconstruction/save | **DEFERRED** | Actual SIGKILL during reconstruction and before atomic checkpoint publication; subsequent state matches; prior durable checkpoint survives |

The systemd fixture contains **two gap records / 374 bytes**. It validates the runner's orchestration and failure checks; it says nothing about realistic state size, full-store time or production memory. [Fixture receipts](evidence/reality-full-scale-20261020/procedure-fixture/scope.json).

## C. Memory assessment

The first 50-second passive window (13:32:27–13:33:17 UTC) had cgroup usage **733,552,640–733,982,720 bytes**: only **4,214,784–4,644,864 bytes** below MemoryHigh. The later 50-second window (13:37:50–13:38:41) had only **1,662,976–2,392,064 bytes** margin. `memory.events.high` remained 10,244 across these windows, and max/OOM/OOM-kill remained zero. Historical cgroup peak was **738,721,792 bytes (704.50 MiB)**, already above MemoryHigh.

Across the 373.985-second span between receipt endpoints:

- Process RSS: **597,248 → 597,628 KiB**; anonymous RSS: **587,584 → 587,964 KiB**, a 380 KiB increase. This short observation cannot establish a leak or a stable long-run slope.
- Total cgroup memory moved by much more than process anonymous RSS. At the subsequent host sample it was **700,121,088 bytes**, with **602,255,360 anonymous**, **79,765,504 file**, and **18,046,976 kernel** bytes. File-cache reclaim explains much of the apparent headroom recovery; it does not establish reduced retained Python state.
- `/proc` still reported 668 KiB of process swap. A later 10-second host interval saw **3 swap-in pages, zero swap-out pages**. Nearly full swap is distinguished from active swap churn.

Host baseline: 16,665,567,232 bytes RAM; approximately **8.0 GiB available**, approximately **3.96 GiB of 4 GiB swap occupied**; root filesystem **169 GiB available**. Baseline/later sampled host memory PSI avg10 was zero, CPU some avg10 **2.58–15.16%**, I/O full avg10 **0.30–3.19%**. The latter exceeded the 2% gate. Subsequent host CPU some avg10 reached **52.81–80.26%**. The tiny fixture and compatibility work was bounded separately; no full recovery was launched into that pressure. [Host counters](evidence/reality-full-scale-20261020/host-final.json), [disk I/O](evidence/reality-full-scale-20261020/disk-io.log).

**Operating budget remains unproven.** There is no defensible new-candidate full-store peak for cold replay, checkpoint load/save, retained market state, or sustained ingestion. No production heap tracing, GC forcing, cache dropping, swap manipulation, or memory-limit change was performed. Historical OOM allocation attribution remains unknown; **the OOM is not proven solved**.

The 4 MiB check remains an admission floor only. This runner adds a conservative **64 MiB sustained protected-recorder margin for heavy staging**, plus its separate 640/768 MiB staging cgroup. That is a staging precaution, **not a measured startup budget**. Final production budgeting must use repeated measured startup/save peaks, anonymous/file/kernel decomposition, ingestion high-water behavior and shared-host pressure. If those do not fit 704/768 MiB with operating reserve, deployment stays blocked; do not increase limits merely to pass.

The final 30-test integration unit used only **5% of one CPU**, consumed **3.717 CPU seconds**, and reported **139.7 MiB peak cgroup memory**, zero swap, inside its 256 MiB hard cap. This bounds that fixture workload only.

## D. Integrity verification

Three real finalized segments (first, middle, then latest at sample time), totaling **120,505 bytes**, passed complete framed-record decoding, compressed checksums, file SHA256, exact manifest equality and within-segment ordinal checks. [Sample receipts](evidence/reality-full-scale-20261020/sample-integrity.json). This sample is far too small to certify the archive.

Full-store frame/gap totals above come from validated metadata; they have **not** been reconciled against all decoded records or a newly recovered full-store Engine. No full-store cold/fast state comparison, duplicate audit, or active-tail recovery was performed. Existing raw duplicates must remain observations; no deduplication or exactly-once delivery claim is introduced.

The deferred runner compares state digest, canonical serialization of **all checkpointed internal Engine fields**, ordinal and gap count across cold, fast, restart and fallback runs. It requires the accelerated path to hash exactly the pinned source byte total and reconstruct zero prefix segments. Cold replay validates record ordinals, kinds, segment digests and online state checkpoints. Saved implementation/catalog identities remain checked. `sequence_verified=False` is explicit throughout.

The 59-test candidate run includes actual incomplete-tail SIGKILL recovery, quarantine preservation, source corruption rejection, checkpoint faults, source isolation and retention bounds. These are fixtures, not a live tail interruption. No original tail or historical record was rewritten to obtain a passing comparison.

## E. Performance and bottlenecks

No new full-store startup time, CPU time, physical I/O, temporary-space peak or time-to-ingestion is available. The primary attempt was rejected **before staging output creation**, with `recorder below 4 MiB MemoryHigh headroom`. [Admission failure](evidence/reality-full-scale-20261020/admission.log).

The earlier **432 wall / 428 CPU-second** replay of a 4.29 GB snapshot belongs to an older candidate, lacked its final digest receipt, and ran without the production CPU quota. Its approximately 28.6-minute quota projection is **not an exact-candidate measurement or downtime promise**. Likewise, the preceding small synthetic 3.7092 → 0.0451-second acceleration result is not full-store evidence. The 66-minute estimate remains superseded but is not replaced by a measured current production ETA.

Code inspection confirms the accelerator hashes covered source bytes and avoids covered record decompression/reconstruction. There was no admitted profile proving the dominant current full-store stage, so no speculative runtime optimization was made. This work changes validation tooling only.

The runner records recovery and checkpoint-save time separately, CPU time, peak RSS, base/final smaps, GC counters, process I/O, cgroup anonymous/file/kernel memory, PSI and throttling. Missing cgroup `io.stat` is explicit, not represented as zero; process I/O is still captured. Warm-cache hashing must not be described as physical disk throughput. No cache eviction is authorized by the procedure.

Its readiness scope is **reconstruction plus checkpoint publication**, not subscription, first live frame, full-health readiness, or first new fsynced recorder write. The optional endurance phase measures isolated durable appends; complete collector startup still requires its own acceptance measurement before approving deployment.

## F. Failure recovery and staging isolation

The new procedure is [scripts/reality_full_scale_validation.py](../../scripts/reality_full_scale_validation.py), tested by [four procedure tests](../../tests/test_reality_full_scale_validation.py) and a real systemd fixture matrix.

Important discovered host limitations:

1. `PrivateNetwork=yes` silently degraded under user-systemd; bubblewrap failed to establish its UID map. A probe also showed that requested read-only systemd mount protection was **not enforced**. Unit-file settings alone are therefore insufficient evidence of isolation on this host.
2. ext4 rejected reflinks (`Operation not supported`). No usable unprivileged COW/read-only mount mechanism was found.
3. Initial worker metric collection assumed `io.stat` existed. The small sandbox test caught this; collection now explicitly tolerates unavailable counters. The integration test also caught a subprocess import path selecting main's older Reality module; the test now pins child imports to the tested candidate.

The final runner prefers FICLONE but otherwise makes **one independent finalized-only copy** in disposable staging, verifies every copied file checksum, fsyncs it and marks it read-only. Recovery views point only to that independent snapshot, **never to production inodes**. A nontruncating open probe confirms source write denial before each recovery worker. No hardlinks or chmod operations touch production. Copying approximately 4.35 GB is justified here because the safer zero-copy mechanisms failed. Actual full-size copying is still deferred by admission.

Heavy workers run **sequentially**: snapshot, cold, fast, restart, corrupt, stale, interrupted reconstruction, full replay after interruption, interrupted save, accelerated restore after interrupted save; optionally 60-minute replay. Each has MemoryHigh 640 MiB, MemoryMax 768 MiB, zero swap, CPUQuota 25%, Nice 19, idle I/O priority, 16 tasks, 70-minute runtime bound, no core dumps and 64 MiB per-file size bound. Parent monitoring every five seconds enforces protected PID identity, existing host PSI gates, 64 MiB recorder headroom and a staging-size abort threshold of snapshot bytes plus 256 MiB. Disk admission reserves snapshot bytes plus 1 GiB in addition to 20 GiB free reserve. The aggregate threshold is monitored, not a filesystem hard quota; per-file and worker bounds limit overshoot. No unbounded spool is introduced.

Any monitor failure stops only the randomly named owned staging unit. It never signals the recorder. Partial staging files/logs remain for diagnosis. A failed run is not automatically retried. Initial failed fixture logs are retained, followed by the corrected passing fixture receipts. The optional hour-long ingestion path has **not** been executed and must not be described as verified endurance.

## G. Endurance and live continuity

**60-minute isolated endurance: DEFERRED.** Full-store recovery has not passed, and headroom/host PSI did not support heavy admission. Production remaining alive is not an endurance pass for the candidate.

Passive endpoints 13:32:27–13:38:41 UTC showed **166 additional frame records / 373.985 seconds = 0.444 frames/s**, and **562 ordinals = 1.503 records/s**. Lifetime frame accounting is separate from this process's `frames` counter. Gaps advanced **9,520 → 9,526**. One later sample had only **8/16 fresh books**; subsequent samples returned to **16/16** without a PID change. Endpoint book ages ranged 8.15–47.74 seconds initially and 0–34.50 seconds later. Sequence continuity remains explicitly unverified. Historical maximum append latency remained 0.207824 seconds; it is a process high-water mark, not the latency of every append in this window.

The [final handoff receipt](evidence/reality-full-scale-20261020/handoff.json) records the unchanged PID and advancing ordinal **2,437,470**, but **`DEGRADED_SOURCE_TIMING` despite 16/16 fresh books**. A follow-up at ordinal **2,437,504** still had two timing-uncertain books; kernel clock health was synchronized, with 44 ms maximum error, which does not independently validate venue time. Current recorder margin was **31,326,208 bytes**, still below the 64 MiB heavy-staging requirement. No timing repair or full-health claim is inferred from freshness. This live source-health limitation must remain visible in campaign gating and deployment acceptance.

The optional runner replay uses captured finalized payloads at a target two frames/s, synchronous durability, periodic finalized segments/checkpoints, five-minute memory/GC/throughput samples, clean stop and exact internal-state restart comparison. Its rate is controlled and source-like, not a new venue subscription. It does not exercise real networking, transport queue occupancy or real reconnection behavior; those require the existing isolated collector fault fixtures and a separate admitted collector startup/endurance acceptance. Storage/backpressure failure must fail visibly rather than be counted as an endurance pass.

## H. MIDAS integration and scientific identity

- **59 candidate tests passed**, 17.39 seconds, including recovery, Foundry, shadow campaigns and two model-metrics checks. No model fitting campaign was launched. [Candidate tests](evidence/reality-full-scale-20261020/compatibility.log).
- **30 additional integration/procedure tests passed**, 61.10 seconds, loading **candidate Reality storage** with current main's Veritas/Arena consumers. The receipt prints the exact imported storage path. Tests cover finalized-source replay (including exclusion of active segments), source divergence, resource-gated v2 batches, research-director recovery and Arena director lifecycle, plus the four procedure tests. [Final integration receipt](evidence/reality-full-scale-20261020/integration-r3.log). Initial failures are retained: the procedure test's child import path in `integration.log`, and a test that assumed actual host PSI was quiet in `integration-r2.log`. The latter now uses the existing quiet-resource fixture for its admission assertion; actual pressure parsing/rejection remains independently tested. No runtime resource gate was changed.
- API and Laboratory health were read-only checks; existing service processes were not restarted. Full training-inclusive regression and an end-to-end candidate live API/collector deployment remain unverified. The prior 165 compatibility / 106 focused passes are historical candidate evidence, not additional passes newly executed here.
- All seven protected campaign/manifest/status hashes matched the previous handoff and remained identical between the new passive receipts. Both Reality campaign identities verify under their **own frozen code**. Candidate code correctly rejects execution under mismatched frozen research code. Old manifests/hashes were not rewritten.
- Campaign source-health gating pins allowed producer hashes. Both inspected forward campaigns are `STOPPED_WITH_RECOVERABLE_PENDING`, with no pending horizons. Deploying a new operational producer must not make it eligible under those frozen hashes. Keep their pinned code/data and rejection/censoring semantics. Reading newly collected framed-v1 data is compatible; accepting it as evidence for an old frozen campaign is a separate scientific eligibility decision, not a storage migration.

## I. Executable validation and production transition

### Later admitted full-store procedure — no recorder action

Run from main using the unchanged candidate packages. Choose a **new** output path each attempt; retain failed results. This command performs no production service action and never starts a collector:

```bash
cd /home/charlie/midas
PYTHONPATH=/home/charlie/midas-reality-reliability/packages:/home/charlie/midas \
  /home/charlie/midas-reality/.venv/bin/python scripts/reality_full_scale_validation.py run \
  --source /home/charlie/midas-reality/data/recordings/reality \
  --output /tmp/midas-reality-full-scale-maintenance-001 --with-endurance
```

It requires 60 seconds of continuous admission before creating staging output. Continue only on unchanged `f2dc9c7`, correct candidate imports, complete boundary/source receipts, every required worker success and exact cold/fast/fallback identity equality. A two-record fixture pass does not satisfy this step. Export receipts before deleting disposable output. Aborting intentionally injected workers is expected; other failures remain blockers. Do not indefinitely retry while gates reject.

Then measure the complete isolated collector lifecycle using controlled local replay, including deferred Store setup, recovered tail, initial checkpoint republish, first fsynced new record, subscription and first fresh snapshot. Preserve the real snapshot; write to its separate staging view. Complete transport/backpressure/reconnect/interrupted-write checks and a stable resource window. The prepared runner does not replace this acceptance step.

### Protected deployment — conditional procedure, **not authorized or executed**

The target is `f2dc9c7`; current loaded code is `2b83818`, checkout/rollback target is `c833200`. **Expected downtime and candidate peak memory are UNKNOWN** until the preceding measurements complete. This is a stop condition for requesting restart approval, not permission to use an estimate.

1. Require clean/pinned source identities, complete full-store matrix, complete collector readiness and endurance evidence, enough disk for staging/capsules plus 20 GiB reserve, and a workload-derived memory reserve within unchanged 704/768 MiB limits. Require host CPU some PSI <20%, memory some <0.5%, I/O full <2%, at least 2 GiB available RAM, sustained recorder headroom and no new OOM/max events. No competing heavy job. Record effective unit/drop-in identities.
2. Resolve the target into a dedicated detached release checkout before the approved window (for example `/home/charlie/midas-reality-releases/f2dc9c7`). Verify its package fingerprint against the validated candidate using the existing source-hash function, and verify imports using the production virtualenv with an explicit release `PYTHONPATH`. Do not mutate the live checkout while the old process is running.
3. Stage this reviewed service override **outside systemd's loaded configuration** until approval:

   ```ini
   [Service]
   WorkingDirectory=/home/charlie/midas-reality-releases/f2dc9c7
   Environment=PYTHONPATH=/home/charlie/midas-reality-releases/f2dc9c7/packages:/home/charlie/midas-reality-releases/f2dc9c7
   Restart=no
   ```

   Existing ExecStart continues to use the production virtualenv and production config/root; explicit `PYTHONPATH` selects the release code. Check that no existing override supersedes these values. Retain the complete old unit/drop-ins/config and their hashes. This release-path mechanism requires its own reviewed identity receipt; the existing `reality_deployment.py apply` expects the old working-directory/source layout and **must not be invoked blindly with this override**.
4. After explicit protected-service approval, install the override as `~/.config/systemd/user/midas-reality.service.d/99-midas-validated-release.conf`, run `systemctl --user daemon-reload`, verify `Restart=no` and unchanged limits, then `systemctl --user stop midas-reality.service` **once**. Record the old PID exit, elapsed stop time and final durable boundary. Do not automatically escalate a slow graceful stop into SIGKILL. Investigate before continuing if it does not stop within the measured 45-second allowance.
5. Before the new start, preserve/check any `.open` and `.tail` evidence. Require successful graceful finalization or a separately reviewed incomplete-tail recovery path; never truncate manually. Validate all new finalized sidecars, contiguous ordinals/kind totals and segment checksums since the prebuilt capsule boundary. Use the candidate read-only replay path with the verified prefix Engine to reconstruct only that tail, then verify/save a capsule matching the final catalog in **staging state**. Covered prefix bytes still need hashing. Log CPU/RSS/I/O and enforce the admitted validation budget.
6. Only after that receipt succeeds, atomically install the verified optional checkpoint into the production root with file and directory fsync; preserve any previous checkpoint separately. Verify checksum/framing, implementation identity and exact catalog prefix. Do not change raw records, old online checkpoints, sidecars, campaign files or lifetime counters. A staging checkpoint copied to a different catalog without this check is unacceptable.
7. Start exactly once with `systemctl --user start midas-reality.service`. The one-shot `Restart=no` prevents a startup failure loop. Capture PID, actual release imports/producer fingerprint, recovery mode, prefix hash byte/segment counts, tail reconstruction and durable ordinal before calling it healthy.
8. Set readiness timeout from the **measured slowest complete collector startup**, with documented reserve; include shutdown, final tail validation/checkpoint publication, source subscription and first fresh snapshots in interruption estimates. The existing deployment tool's 2,400–3,600-second window is only a configured bound, not measured sufficiency. If measured readiness plus reserve exceeds the supported bound, fix/review that constraint before approval. Type=simple's immediate systemd start success is not readiness.
9. Abort acceptance on timeout, crash, source/checkpoint mismatch, ordinal regression, unexpected limits/imports, new max/OOM events, sustained memory/PSI outside the measured budget, or failure to receive all 16 expected initial fresh books. Preserve evidence, leave automatic retries disabled and request the next protected action. Do not automatically restart or roll back.
10. Require at least five minutes of continuously fresh expected books, advancing frame/ordinal counters, current status timestamps, no PID/restart change, correct candidate producer identity, no new corruption/persistence errors and stable memory/pressure. Verify newly finalized checksums and replay across the visible `process_stop`/`process_start` gap. Recheck API, Veritas lag and campaign eligibility; no unrelated service restart. Continue resource/health observation for at least 60 minutes, with five-minute receipts. Only then restore the recorded `Restart=on-failure` policy through a separately checked policy-only override update and daemon-reload.

**Source-gap implications:** every transition interrupts observation. Restored books do not establish sequence continuity; `sequence_verified` must remain false, and fresh initial snapshots are required. No downtime gap may be hidden by reusing old healthy status or research hashes.

**Rollback:** a code rollback requires another protected interruption and separately approved resource/time budget. Keep `Restart=no`; stop only the candidate when authorized; preserve all newly written segments/tails/checkpoints. Remove the release override to restore the unchanged production checkout `c833200`, recheck the old effective unit/config, then start once when approved. That older code ignores the accelerator and may replay the entire enlarged archive. Its current full-store memory/downtime budget is also unmeasured; do not call rollback immediate or guaranteed safe. Never restore an old archive directory, reset ordinals, discard candidate data, or rewrite frozen research identities. Restore automatic restart policy only after the rollback passes its own health acceptance.

No deployment step above has been executed. The mechanism intentionally avoids updating the live import path before an approved stop. There is no half-installed unit, checkpoint or release change to undo.

## J. Frontier readiness

**NOT READY for multiple independent production market collectors.** The engineering foundation is stronger, and isolated fixture consumers remain compatible. Full-scale cold/checkpoint recovery, shared-host memory reserve, actual collector resumption and hour-long ingestion evidence remain missing. No additional market venue, subscription, Frontier implementation or research campaign was introduced.

## K. Genuine remaining blockers

1. A resource-admitted window or suitable isolated host for the exact-candidate full-store matrix. This host also requires the independent staging-copy allowance because unprivileged read-only isolation and reflinks failed.
2. Measured full-size startup/checkpoint memory, CPU/I/O, durable first write and complete collector readiness interval. The 4 MiB floor cannot supply these answers.
3. Successful 60-minute isolated ingestion and complete collector failure/reconnect/queue acceptance; the supplied optional replay path remains unexecuted.
4. A reviewed deployment identity/resource receipt and measured downtime/rollback plan based on those results. Current procedure is conditional, not approval-ready.
5. Explicit protected-recorder authorization **after** those gates. No approval is requested now because the candidate has not earned a restart recommendation.
6. Final live source timing was degraded with two uncertain books. Preserve that eligibility limitation and require the applicable complete health prerequisites before declaring deployment successful.

Historical OOM attribution remains an unresolved diagnostic limitation; these measurements do not establish its triggering allocation or prove its elimination. Protected authorization and unsafe host conditions now prevent the remaining scale/endurance/deployment work. No automatic retries or continuation into another campaign are scheduled.
