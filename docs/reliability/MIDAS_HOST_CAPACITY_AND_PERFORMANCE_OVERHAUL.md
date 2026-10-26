# MIDAS host capacity and performance overhaul

Date: 2026-10-20. **Final: substantial improvements deployed and verified; overall acceptance remains conditional.** Stopping condition: external/safety verification limits around protected Reality and its storage budget; further independent high-impact optimizations have diminishing returns at the observed workload. All times below are UTC unless explicitly marked CEST (UTC+2). Historical reports are evidence of earlier incidents, not measurements of this run.

## 1. Executive summary

The largest demonstrated avoidable cost was a SQLite history query repeatedly walking synthetic observations to find rare simulations. During the initial three-minute window the main API read 37.7 MiB/s, the NVMe averaged 9,563 read IOPS and 80.9% utilization, and host I/O full PSI averaged 12.94%. CPU was not saturated: aggregate busy time averaged 18.13%, CPU PSI 3.14%, and memory PSI was zero. High swap occupancy was predominantly inactive data, not sustained thrashing.

Implemented selective history access, cheaper logically identical paper transitions, compressed physical account heads with unchanged logical hashes and synchronous durability, reserve-aware shared research admission, and corrected API-only release selection. Controlled benchmarks show 272x less query CPU, 62.4% less paper transition CPU, and 95.88% fewer durable writes on the specified fixtures. These are component measurements, not whole-host speedup claims.

The protected recorder has never been stopped or restarted by this mission. It retains its original PID and old loaded code, with only a few MiB below MemoryHigh. That prevents the existing 64 MiB-margin full-store staging gate from admitting recovery tests. Low host pressure cannot establish that this recorder transition or future ingestion growth is safe. A completed 61-minute production window includes both APIs, continuous recording, 119 finalized Veritas segments and two automatically scheduled bounded qualification jobs. Average CPU busy time is 14.01%, CPU PSI 2.13%, I/O full PSI 0.79%, and memory PSI zero. Overall acceptance remains conditional: source-quality exceptions occurred, the full-store gate remains refused, and the recorder's existing 24 GiB budget has approximately 22 days remaining at this hour's measured growth despite a configured 90-day retention. No protected restart or budget change was authorized or performed.

## 2. Host inventory

Verified i5-9400F: six physical cores/six logical CPUs, 16,665,567,232 bytes usable physical memory (15.52 GiB), 4 GiB swap. Ubuntu 24.04.5; kernel 7.0.0-38. Samsung MZVLB512HBJQ 512 GB NVMe, ext4 root approximately 468 GiB, approximately 168 GiB user-available space at inspection. Approximately 24 GiB additional ext4 reservation is not treated as staging space. The unrelated cloud mount has separate capacity and was untouched. NVMe scheduler is `none`.

Cgroup v2: user manager has no CPU quota; MIDAS service quotas are local. User hierarchy delegates CPU/memory/pids but not I/O: `io.stat` is unavailable and IOWeight is not evidence of an effective hard I/O reservation. Process `/proc/PID/io` and device diskstats supply physical-I/O observations. Cached file pages count against service memory limits.

| Service/workload | Ownership and purpose | CPU quota | MemoryHigh / Max | Swap cap |
|---|---|---:|---:|---:|
| midas-reality | Protected continuous recorder | 25% of one core | 704 / 768 MiB | 0 |
| midas-api | Production demo API/Laboratory coordinator | one core | 1536 / 1792 MiB | 0 |
| midas-reality-api | Separate interface/demo API | half core | unlimited / 512 MiB | 0 |
| Veritas gap-detail v2 | Periodic validated finalized-segment analysis | one core | 192 / 256 MiB | 0 |
| Arena scheduler | Minute timer, job reconciliation | one core | unlimited / 512 MiB | existing |
| Veritas director | Periodic research orchestration | one core | unlimited / 512 MiB | existing |
| Main Arena qualification | Admitted, isolated read-only job | requested 1–100% | effective 512 MiB max | 0 |
| Main / Veritas ordinary Arena | Admitted research | at most one core | requested / fixed 4 GiB respectively | 0 |

System/user timers include one-minute Arena reconciliation, five-minute Reality capacity and Veritas v2 work, approximately half-hour source analysis/observatory/director work, and daily archive/research/integrity jobs. Existing daily schedules are retained. Paused shadows and inactive 48H-001 remain inactive. Separate interface services are legitimate isolated workloads, not orphan duplicates.

Unrelated Continental/desktop infrastructure includes status, Rustdesk, Netdata, Docker services, GNOME, terminals/Codex, Drop and ChatGPT/WebKit. Their measured costs are included in host totals; none was reconfigured or disabled. See [inventory](evidence/host-capacity-20261020/host-inventory.json).

## 3. Initial resource breakdown

Baseline: 15:09:47–15:12:49, 13 samples at approximately 15-second intervals, before the first API restart. No new research campaign. Both demo APIs, live recorder, ordinary timers, desktop and unrelated services were running. This is class A/B background/production, not a completely idle machine.

| Consumer | CPU % of ONE core | Mean cgroup MiB | Mean swap MiB | Physical reads / writes |
|---|---:|---:|---:|---|
| Main API | 22.44 | 1535.6 | 0 | 37.7 / 1.17 MiB/s |
| Interface API | 8.27 | 191.9 | 0 | 0 / 1.29 MiB/s |
| Reality recorder | 0.69 | 703.0 | 0.7 inherited | approximately 45 B/s / 55 KiB/s |
| Rustdesk | 21.05 | 379.0 | 4.4 | not attributed to MIDAS |
| GNOME shell | 7.09 | 203.2 | 267.3 | unrelated |
| Drop scope | 6.99 | 440.9 | 224.0 | unrelated |
| Netdata | 6.25 | 365.9 | 40.8 | unrelated |
| Large terminal/Codex scope | 6.03 | 4102.1 | 589.6 | includes engineering work |
| status service | 1.95 | 197.8 | 425.5 | unrelated |

Host CPU mean 18.13%, interval peak 26.19%; individual core means 16.48–20.08%. Sampled run queue averaged 2 (maximum 5), blocked tasks 0.62 (maximum 1); approximately 37,594 context switches/s and 28.1 process/thread creations/s. The short post-fix window approximately halved context switching while creation rate remained approximately 27/s, so no claim is made that MIDAS eliminated unrelated short-lived tasks. Mean I/O wait 13.15%. CPU PSI some avg10 mean 3.14%, max 4.56%; I/O full mean 12.94%, max 15%; memory some/full zero. NVMe read bandwidth 37.91 MiB/s, write 3.13 MiB/s; read await mean 0.085 ms, write await 0.646 ms. High small-read IOPS and file-cache churn explain pressure despite low per-request device latency.

Main API cgroup cache was approximately 1.3 GB, anonymous memory approximately 289 MB; initial process RSS/PSS approximately 336/322 MiB. Recorder usage included approximately 631 MB anonymous memory, 85 MB inactive file pages and 19 MB kernel accounting. RSS, PSS and cgroup totals are different quantities and are not added together. Parent process waited-child I/O is not summed with child counters. [Baseline evidence](evidence/host-capacity-20261020/baseline-summary.json).

## 4. Bottleneck investigation

| Rank | Evidence/root cause | Frequency/value | Risk and decision |
|---|---|---|---|
| 1 | Rare-kind history query chose source index and scanned newer observations | repeated UI analytics; tens of MiB/s | Low complexity; pin existing kind index only for simulation/experiment; preserve selective source path for observations |
| 2 | Paper transition deep-copied and repeatedly summarized retained histories | every observation; approximately 79 ms CPU fixture | Moderate correctness sensitivity; exact output hashes, financial/crash/idempotency tests |
| 3 | Approximately 941 KiB complete account head rewritten per event | every durable command; persistent WAL/checkpoint traffic | Higher compatibility risk; bounded versioned physical codec, unchanged logical checksums, FULL-sync and tested old-code materialization |
| 4 | Admission reserved 2 GiB regardless of worker cap; interface/Lab bypass paths | launch-time OOM/overlap risk | Reserve cap plus 2 GiB; shared lease and actual ancestor memory checks; refusal retains legitimate queued work |
| 5 | Hidden qualification 10% quota | one CPU-second takes approximately ten wall seconds | Honor declared quota; retain one global worker and low priority |
| 6 | Recorder historical state, full manifests/checkpoints/recovery | near local MemoryHigh; full-scale test gated | Candidate synthetic validation only; do not touch live PID or weaken gate |
| 7 | Veritas prefix/lineage work | approximately 5.3 CPU seconds/300 seconds at approximately 16.9k segments | Current host cost approximately 0.3% of six cores; retain checks rather than introduce unvalidated incremental identity rules |

Other investigations: WebSocket parsing/order-book depth materially affects isolated replay CPU; no live-process profiler was attached. Laboratory feature/tournament semantics are unchanged. Shared archive discovery over the small current research catalog did not justify an index/cache with invalidation complexity. Logging/health checks/timers cost less than the demonstrated API hot paths. Immutable Veritas analysis and source lineage were hash-compared, not rewritten. API startup still verifies the complete event chain using existing streaming batches; removing that check would trade integrity for speed and was rejected.

Historical CPU PSI approximately 80% cannot be recreated or assigned to today's processes from current samples. Readable kernel logs independently confirm global API OOMs at 00:38/00:40 CEST on October 20, with approximately 9,000,944/8,983,968 KiB anonymous RSS, and a separate interface API cgroup OOM at 05:51 CEST with 517,264 KiB anonymous RSS. None occurred during this mission's measurement/deployment window. These are API incidents, not evidence establishing the recorder's historical OOM cause. The journal startup streaming fix predates this work and remains effective; no new credit is claimed for it. Recorder's historical OOM root cause remains unproven.

## 5. Implemented optimizations

- `d06ea41`, refined `cabd0ea`: bound SQLite rare-kind queries using existing index and parameter binding. Reverse-skew observation regression prevents moving the scan to a rare LIVE source.
- `3647c03`: detached JSON state cloning and compact internal totals, with complete public/durable histories retained. No version, scientific model or reconciliation change.
- `1f47c2f`: transparent PaperAccount JSON codec only. Small/incompressible/>64 MiB states retain plain JSON. Decoder bounds expansion and rejects unknown versions, wrong sizes, concatenated streams and malformed data. Journal/record JSON remain plain. `scripts/verify_paper_journal.py` streams events and verifies snapshot checksum as well as all transitions.
- `58d6213`, `c2d1c5f`, `ddb1679`: effective memory-cap reserve; explicit CPU budget; interface root catalog; shared Laboratory lease through pool shutdown; requested worker budgets checked against coordinator/ancestor cgroup limits. Failed launch releases lease and records recoverable status.
- `3dfd113`: research CPUWeight 10 and Laboratory children Nice 19. These prioritize availability rather than reduce scientific work.
- `fc67cd6`: bounded 4 GiB synthetic recording allowance per API, supported by free-space reserve. This allocates space; it is not an efficiency saving or permanent retention solution.
- `b64ebca`, `a9d3772`: low-frequency, read-only time-series collection and streaming summaries, including device IOPS/latency and explicitly per-process physical I/O.
- `e06f7c6`: independent immutable Veritas wrapper release; analysis and identity files unchanged. Veritas branch commits `b687c88`, `a31b82f`, `a970885`, `10c88a2`, `44178fb` provide equivalent operational guards.

Relevant validation completed in bounded disposable cgroups: 82 paper/simulation/property tests; 62 Arena/admission/scheduling/autonomy tests; 19 Veritas admission/director tests; 15 Laboratory tests plus targeted lease/start-failure cases; 12 batch/control cases; 37 exact interface/native worker cases; codec/paper/query regression suite (30 before final oversize compatibility case), targeted eight codec cases; 11 API/demo/import tests. Ruff and relevant Mypy checks passed. Counts describe separate runs with overlap, not unique tests. No expensive full repository suite was run concurrently with production recovery.

## 6. Before-and-after benchmarks

| Equivalent workload | Before | After | Comparison |
|---|---:|---:|---|
| 20,024-row history fixture, seven runs, 24 identical rows | median 7.063 ms CPU / 8.285 ms wall | 0.02594 / 0.02597 ms | 272x CPU / 319x wall |
| Actual captured six-scenario head, ten equivalent transitions | median 79.467 ms CPU | 29.850 ms | 62.4% less CPU |
| Captured interface head, seven transitions | 80.314 ms CPU | 29.307 ms | 63.5% less CPU |
| 64 durable observations, two runs/version, FULL commits + checkpoint | 170,172,416 write bytes/run | 7,008,256 | 95.88% fewer / 24.28x |
| Same durable fixture | mean 6.844 CPU / 7.086 wall seconds | 6.679 / 6.801 seconds | no CPU penalty observed |
| Same fixture high-water RSS | maximum 94.42 MiB | 90.22 MiB | measured /proc VmHWM; not production memory claim |
| Same SHA work, CPUQuota 10% vs requested 100% | 10.792 wall / 1.071 CPU seconds | 1.072 wall / 1.072 CPU seconds | work unchanged, quota waiting removed |

All state-storage repetitions produce the same logical SHA256; all transition variants produce identical canonical result hashes. Physical encoding differs by design. Quota test digest is identical, throttled time 9.709 seconds versus zero; local CPU PSI approximately 50% under the 10% quota demonstrates quota waiting independently of physical saturation. It does not by itself explain historical host PSI.

Live old-query probe was intentionally aborted above 100,000 VM instructions after 26 ms; fixed query returned all 24 rows in 0.383 ms below 1,000 instructions. This is an aborted lower bound, not a completed old-query benchmark. Post-fix pidstat showed zero main physical reads during a comparable short routine interval. Final sustained host metrics are recorded separately below; transient startup and different process ages are excluded from steady-state savings claims.

Evidence: [query](evidence/host-capacity-20261020/query-benchmark.json), [paper](evidence/host-capacity-20261020/paper-benchmark.json), [physical writes](evidence/host-capacity-20261020/state-storage-benchmark.json). Production six-scenario state compresses less than the synthetic single-market fixture: isolated compact raw 875,584 bytes compressed to 57,709 before base64; do not promise a 24x whole-host I/O reduction.

### Sustained production comparison

Same workload class: both demo APIs, recording, routine timers and external host services. Initial baseline is 3.03 minutes; intermediate is 38.80 minutes with query/broker fixes but plain account heads (16:55–17:34); final is 61 minutes of health observation (17:42:24–18:43:24), with 242 host samples covering 60.72 minutes inside that window. Durations, source event mix, external activity and process ages differ, so whole-host differences are observational; the fixed-work benchmarks above supply causal comparisons.

| Metric | Initial | Pre-codec stable | Final |
|---|---:|---:|---:|
| Host busy CPU mean / interval peak | 18.13 / 26.19% | 15.31 / 34.95% | 14.01 / 21.99% |
| CPU PSI some avg10 mean / peak | 3.14 / 4.56% | 2.00 / 7.59% | 2.13 / 9.09% |
| I/O full PSI mean / peak | 12.94 / 15.00% | 0.75 / 2.76% | 0.79 / 2.49% |
| Host memory PSI some mean / peak | 0 / 0% | 0.0008 / 0.10% | 0 / 0% |
| NVMe reads MiB/s mean | 37.91 | 0.138 | 0.240 |
| NVMe read IOPS mean | 9563 | see evidence | 29.5 |
| NVMe writes MiB/s mean | 3.13 | 3.81 | 0.783 |
| NVMe utilization mean | 80.87% | 4.60% | 4.77% |
| Main CPU % one core | 22.44% | 8.58% | 8.69% |
| Interface CPU % one core | 8.27% | 5.79% | 5.82% |
| Main kernel-accounted writes MB/s | 1.224 | 1.542 | 0.160 |
| Interface accounted writes MB/s | 1.357 | 1.460 | 0.152 |
| Main physical reads B/s | 39,526,555 | 14 | 2 |
| Interface physical reads B/s | 0 | 4 | 9 |

Main API reads fell by more than 99.99% against the initial baseline. Host I/O full PSI fell approximately 93.9%; this is a sampled time-series observation, not a universal host speedup. Codec-only mean API write reductions are 89.64% main / 89.56% interface. CPU did not move into saturation: cap/priority and scientific work remain unchanged.

The index-bounded production command comparison explicitly normalizes useful work:

| Metric | Main before / after codec | Interface before / after codec |
|---|---:|---:|
| Observations/s | 0.5593 / 0.5583 | 0.5335 / 0.5336 |
| CPU seconds/observation, including API reads | 0.15344 / 0.15561 | 0.10856 / 0.10899 |
| Kernel write bytes/observation | 2,756,837 / 286,049 | 2,736,264 / 285,561 |

Thus reduced I/O preserved throughput; small observed CPU-per-unit increases (1.4% / 0.4%) accompany approximately 89.6% fewer writes, with substantial CPU reserve. Counts are 1302/2034 main and 1242/1944 interface, all `observe` commands within the corresponding host sample timestamps. These observations include external UI traffic and are not controlled CPU microbenchmarks. [Normalized evidence](evidence/host-capacity-20261020/normalized-production-work.json).

Device read/write await changed from 0.085/0.646 ms initially to mean interval averages 2.145/2.239 ms (final maxima 8.0/4.73 ms). Latency improvement is **not** claimed: request mix and counts changed sharply, and interval means are not request-weighted tail distributions. Utilization, pressure, useful throughput and API availability improved/remained healthy; process-lifetime recorder max append stayed 0.208 seconds. Per-process write_bytes is kernel accounting, not NAND wear; device diskstats independently supplies host writes. No cache/swap flush was used.

[Final host evidence](evidence/host-capacity-20261020/final-summary.json), [intermediate](evidence/host-capacity-20261020/pre-codec-summary.json).

## 7. Scheduler and resource management

Retain one global research job, conservative cross-root catalog checks and nonblocking admission. Ordinary work requires requested/effective MemoryMax plus the existing 2 GiB available-memory reserve. Main default 3 GiB needs 5 GiB available; Veritas/legacy 4 GiB needs 6 GiB; qualification 512 MiB needs 2.5 GiB. v2 batch reserves its 256 MiB plus 2 GiB. Actual pressure and disk checks still apply. CPU PSI some avg10 <=20%, memory some <=10% and full <=1%, I/O some <=20% are existing Arena admission limits, not newly relaxed targets. For this mission's controlled tests the stricter memory some <=0.5% abort gate was used.

Laboratory additionally requires coordinator RSS + 128 MiB reserve + requested worker count times declared per-worker memory within every finite ancestor memory.high/max. It rejects impossible pools rather than secretly reducing specifications. Lease remains held until pool shutdown, including paused draining, so periodic v2/research can defer. This is deferred legitimate work/reduced overlap, not eliminated work or increased throughput. No paused shadow lifecycle is changed. One small native legacy worker completed 30 generated episodes in 6.66 seconds wall (5.86 CPU); this bounds one fixture, not arbitrary model-training throughput.

One core at low priority is the present research ceiling, not proof that all jobs fit. Main Lab budgets must fit the API's own cgroup; preview generally needs a smaller explicit worker budget. Job admission reevaluates actual MemAvailable/pressure/catalog state at launch. It is a conservative adaptive yes/no gate, not a learned predictor of peaks. Final main/interface/recorder throttled times were 0.118 / 178.08 / 6.05 seconds over 3643 seconds. Interface local CPU PSI mean 2.83% coexisted with host CPU PSI 2.13% and 14.01% busy CPU; its half-core burst budget causes local waiting without physical saturation. Recorder local CPU PSI mean 0.07% (peak 6.16%) does not support blaming all timing degradation on host CPU. Repeated expensive trials were not launched to fill a benchmark table.

Acceptance targets retain the actual gates rather than redefining them after observing results:

| Criterion | Target / evidence required |
|---|---|
| Normal CPU | Sustained PSI some avg10 below existing 20% gate; no persistent core saturation; reserve for one low-priority core |
| Memory | No new OOM/max events, no sustained memory PSI/reclaim; worker cap plus 2 GiB available; essential working sets bounded |
| Heavy Reality staging | Existing require_safe floor **4 MiB** recorder margin, then stricter full-store **64 MiB sustained** margin; memory some <0.5%, I/O full <2%, CPU some <20% |
| Swap | No sustained in/out/reclaim with memory PSI; occupancy alone is not a failure |
| Storage | Existing disk reserve, continued durable ordinal/segment progress, no repeated whole-history reads or unbounded routine I/O |
| Availability | Both APIs continuously READY, no restart loop; sampled read-only endpoint latency <250 ms is an empirical review target, not a pre-existing contractual SLA |
| Useful work | Journal revisions and finalized Veritas segments advance, pending queue drains, recording progresses; sustained research still requires separate admitted endurance |

The ordinary Arena limits and stricter Reality staging limits serve different workloads; they are not interchangeable. At 17:41:40 UTC the actual full-store gate rejected the recorder even at the 4 MiB floor, before reaching its additional 64 MiB requirement. No gate was weakened.

## 8. Memory and swap

Host memory pressure was zero in the baseline and remained a monitoring/abort condition. Approximately 8–9 GiB MemAvailable coexisted with nearly full swap. Significant swapped sets belonged to inactive unrelated apps; no swapoff/cache clearing was performed. Swap occupancy is not an acceptance failure by itself. Baseline averaged 1.54 swap-in pages/s (about 6.2 KiB/s), zero swap-out, 2.27 major faults/s and zero direct/kswapd scan rates. Rates and major faults, rather than occupancy alone, determine active paging; final distributions are in the sustained summary.

The protected recorder has a *local charged-footprint/peak* risk: approximately 730–738 MB charged against 738,197,504-byte MemoryHigh, even when host memory is available. Reclaim/high counters exist; zero current cgroup max/OOM/oom_kill counters and zero memory PSI do not establish full-recovery headroom. SwapMax=0 does not erase previously charged inactive swap. Inactive file cache is reclaimable; a high total charge alone does not prove anonymous-memory exhaustion. During final observation recorder charge ranged 690.18–703.89 MiB, anonymous mean 616.16 MiB, file mean 65.89 MiB and kernel mean 18.87 MiB. Total MemoryHigh margin ranged 0.113–13.82 MiB, never the required 64 MiB. Its 82 high events reclaimed approximately 9856 pages; no max/OOM event, major fault or sampled memory PSI occurred. The gate is conservative and cache-sensitive, but no measured full-recovery peak exists to justify weakening it.

Final main/API RSS means were 146.09 / 114.59 MiB; cgroup means 1474.67 / 420.72 MiB were predominantly file cache. Their new high-event counts were two/zero, OOM/max zero, major faults zero, sampled memory PSI zero. Recorder RSS mean 625.12 MiB was bounded over this hour. This is not a proof against multi-day growth. [Cgroup evidence](evidence/host-capacity-20261020/cgroup-details.json).

Host available memory final minimum/mean 8.48/8.68 GiB; swap-in/out averaged 0.102/0.487 pages/s (about 0.4/1.9 KiB/s). Small transient page-scan bursts occurred (direct max 240 pages/s, kswapd max 6730), with memory PSI zero; do not describe reclaim as entirely absent. Final swap free was approximately 1.03 GiB. The large occupancy change since the initial baseline is unattributed and is not credited as an optimization. No global memory policy, swappiness (60), overcommit (0), reserved space or unrelated cgroup was altered.

API cgroup cache growth during full event-chain startup is expected; streaming avoids materializing hundreds of thousands of events. Restart-dependent RSS changes are not treated as controlled optimization gains. Compressed account-head and broker fixture memory is bounded, but long-horizon state growth still needs explicit retention/architecture work.

## 9. Storage and I/O

Every accepted paper command retains the journal append, logical checksum and atomic account/event transaction with SQLite FULL synchronous behavior. Codec changes only physical head representation, so a bad envelope fails closed. Both APIs have bounded raw synthetic recording allowances; historical research/model artifacts were not deleted. Device/counter observations are cache-sensitive; no cold-cache claim or cache-flush experiment was made.

Recurring archive traversal was separated from the live recording path in analysis. Existing protected code still retains its historical behavior. Veritas v2 processes finalized segments, approximately 9–10 new segments per five-minute batch, with zero pending segments in observed successful runs. The independent Reality capacity monitor also consumed 4.277 CPU seconds at 18:46, approximately every five minutes, reading archive metadata for capacity/rate estimates. Together with v2, this is roughly 10 CPU seconds/300 seconds (about 0.6% of six-core capacity). Sharing a persistent metadata index might remove duplicated work, but is not justified now against integrity/invalidation complexity. Current whole-prefix/lineage validation remains a small residual cost; no historical provenance was rewritten. Heavy archive recovery/compaction was not run against the protected host when the established staging gate denied it.

Verified protected configuration: budget **24 GiB**, filesystem reserve **20 GiB**, retention **90 days**, 8 MiB/300-second segments, 600-second selection refresh and 300-second resync. Final stored bytes were 4,512,410,845. This hour added 40,595,398 bytes: a linear model gives 0.893 GiB/day and **22.18 days** until the configured budget, not 90 days of effective runway. A 90-day archive at this hour's mix would require approximately 80.32 GiB, before other MIDAS/unrelated growth. These are single-hour estimates, not a long-term forecast. No raw/model/history was removed and no protected limit was changed. The existing receipt-aware capacity timer independently estimated 950.9 MB/day and 22.35 days remaining at 18:46, corroborating this window model; it reported no clock regressions, while keeping 172 deferred-record receipt-order regressions distinct. [Capacity receipt](evidence/host-capacity-20261020/capacity-monitor-final.json). The capacity timer remains the mechanism for observing the runway; an approved budget/retention/archival plan is needed before exhaustion. Existing archival compatibility must be validated before moving any finalized source.

Current root free space is 167.36 GiB. The capacity model reserves the protected 20 GiB first, plus outstanding API/research/storage commitments and unrelated growth. The existing generic Arena disk gate remains its inherited 2 GiB floor plus a 1 GiB next-artifact allowance; it does **not** encode the recorder's full 20 GiB reservation across independent writers. This is a residual coordination hardening item for long unattended operation, not a present I/O bottleneck at 167 GiB free. Do not claim that all disk reserves are already enforced by the generic gate or use reserved root blocks as staging capacity.

## 10. Endurance verification

Final uninterrupted post-codec observation completed: **3660.000 seconds, 62 health samples**, 242 host samples over 60.72 minutes. Both API processes stayed READY with zero sampled HTTP failures, zero restarts and live execution false. Recorder PID 863193 remained unchanged, with zero new OOM/max events; frozen hashes stayed identical in all samples. Earlier windows span several hours of ordinary recording and scheduling, but contain deliberate authorized API-only maintenance restarts and cannot be relabeled as one clean deployment pass. Recorder PID remained 863193 and frozen campaign hashes remained identical. No destructive recorder test or simultaneous heavy workload was used.

One earlier approximately 57-minute sample window had 59 health samples: recorder RECORDING_UNSEQUENCED 41, AWAITING_DATA 3, DEGRADED_SOURCE_TIMING 14, DEGRADED_BOOKS 1. Fresh books were 16 in 55 samples, zero in three and ten in one. These are observed provider/timing states, not all-good source assertions. Process-lifetime max append duration was approximately 0.208 seconds; it is not a newly measured p95. Source timing degradation can coexist with fresh books and low host pressure; the audit does not prove host contention is its sole cause.

Final useful work: main/interface journals advanced **2046 / 1956** events, recorder **22,112 durable ordinals / 18,273 frames / 40,595,398 stored bytes**, Veritas **119 finalized segments**, pending segments maximum zero. A second scheduled qualification (`job-a41ec9c5faca48d4a43ab3ee`) validated 269 events in 4.08 recorded elapsed / 3.696 CPU seconds, exit 0. Both jobs retained ordinary negative findings without promoting a model.

Main/interface health mean 3.14/4.33 ms, p95 16.85/22.71 ms, maxima 39.09/84.32 ms. State mean/p95/max 12.24/43.43/93.84 ms. Analytics mean/p95/max 119.60/256.43/335.05 ms: it slightly misses the empirical 250 ms review target; no contractual SLA or baseline latency improvement is asserted. Refresh-processing latency mean/p95/max 707.55/798.64/808.29 ms; queue, pending simulations and broker delay were zero in every sample.

Final recorder state samples: RECORDING_UNSEQUENCED 56, DEGRADED_BOOKS one, DEGRADED_SOURCE_TIMING three, AWAITING_DATA two; fresh books 16 in 59, 12 in one, zero in two. All-source-good acceptance therefore did **not** pass. Recording progress and preserved diagnostics demonstrate resource continuity, not perfect source validity. Start/end single finalized segments matched sidecar byte counts and SHA256, not a full archive audit. [Endurance evidence](evidence/host-capacity-20261020/endurance-summary.json). A scheduled Veritas director cycle admitted `job-8c0b2f8ef4a14e5d8558041c` at 17:45:33. It completed qualification of 268 scan-pinned events: 3.97 seconds recorded elapsed, 3.72 CPU seconds from systemd, exit 0, 512 MiB cap, one core, CPUWeight 10. Result was correctly `no_positive_gross_candidate_observed`; no scientific threshold or frozen campaign changed. Source copy/import/preflight added approximately two seconds before the worker start timestamp. This is actual ordinary autonomous analysis during observation, not a newly activated campaign. [Receipt](evidence/host-capacity-20261020/observed-research-job.json).

Sustained *heavy* research and isolated termination/recovery at full size were deferred due protected working-set risk; full-store Reality recovery is explicitly refused by its separate recorder margin gate. Ordinary Arena admission was ready with approximately 8.7 GiB available, low pressure and no active research jobs at a later instantaneous check. Do not conflate these gates or claim all research is blocked. Existing isolated crash/recovery tests and short native workers do not substitute for that integrated test.

## 11. Production deployment

Only APIs and MIDAS-owned research/admission configuration are deployed. Main API loads main source; interface uses independent physical release `~/.local/share/midas-capacity/interface-capacity-v1-20261020`, based on exact `c833200` with explicit overrides and file-hash manifest. Explicit Uvicorn `--app-dir` is essential: prior interface stages could load old apps from WorkingDirectory despite PYTHONPATH pinning core packages. The protected worktree/source/PID never changed.

Veritas immutable runtime: `~/.local/share/midas-veritas/gap-detail-v2-efficient-20261020/runtime`. Wrapper admission changed; scientific source hashes match the original release. The timer's next invocation selects it without restarting the recorder. Reality candidate `f2dc9c7` remains staged/undeployed; loaded recorder commit remains `2b83818`.

Rollback: API-only stop, verify PID=0/inactive, materialize *current* compressed heads with `scripts/paper_state_storage.py --materialize --service <API> --database <db>`, then select prior code using explicit app-dir and start once. This preserves revisions/checksums/journal heads; never restore a stale financial head backup. Materializer checks every head and atomically rolls back if any checksum fails. Actual previous main release recovered the disposable materialized fixture: 268 journal events, 264 observations. [Receipt](evidence/host-capacity-20261020/rollback-old-code.json). Prepared complete previous source at `~/.local/share/midas-capacity/main-pre-codec-aee2005`. Normal bounded API on-failure policies were restored at 17:46:36 with both API PIDs unchanged. Only the temporary runtime single-start overrides were removed; recorder policy was untouched. [Receipt](evidence/host-capacity-20261020/restart-policy-restored.json).

## 12. Current capacity

Ordinary services have substantial aggregate CPU/RAM headroom once needless reads and serialization are removed. Current evidence supports continuous recording plus both APIs and bounded periodic finalized-segment analysis, subject to persistent recorder local-memory/source-quality conditions. It does not demonstrate arbitrary autonomous training coexistence. The integrated window does demonstrate two normal automatically scheduled qualification jobs coexisting with collection and APIs. Capacity is bounded in time by the current capture budget: approximately 22 days at the measured mix until an approved preservation/retention/budget transition. It is not an unconditional 90-day operating certification.

Reserve at least 2 GiB host available memory *after* a worker's full cap, retain existing disk reserve and actual cgroup limits, and admit at most one low-priority research job. Because workload memory is specified as a cap, not a measured statistical peak, this model deliberately favors production safety. Bounded fixtures have completed without changing evaluation semantics; sustained production research capacity remains a conditional claim until protected headroom and full-scale validation are resolved. An idle host with research indefinitely deferred is not full acceptance.

## 13. Frontier capacity planning

Synthetic replay uses no new subscriptions or providers: 8/16/32 in-memory markets (2x/4x), 100/1000 levels, 2000 identical delta frames, three runs per case/version; all input and final-state hashes match. Candidate and old recorder sources were imported into disposable one-core/192 MiB units. [36 samples](evidence/host-capacity-20261020/synthetic-growth.json).

| Candidate component | 8 markets | 16 markets (2x) | 32 markets (4x) |
|---|---:|---:|---:|
| 100 levels: frames/CPU-second approximately | 17,942 | 17,573 | 16,398 |
| 100 levels: digest CPU ms | 4.10 | 8.26 | 16.23 |
| 100 levels: VmHWM MiB | 21.16 | 22.09 | 23.86 |
| 1000 levels: frames/CPU-second approximately | 3,284 | 3,255 | 3,231 |
| 1000 levels: digest CPU ms | 27.92 | 56.12 | 112.57 |
| 1000 levels: VmHWM MiB | 28.51 | 36.70 | 52.93 |

At 32 markets/1000 levels, candidate RSS is approximately 36% below old 83.18 MiB; deep-book update throughput is essentially unchanged. This credits existing candidate data structures, not a newly deployed recorder optimization. Digest work and retained state scale with total depth/markets; doubling both source event rate and depth can consume substantially more than twice CPU. Frame rate here excludes WebSockets, network parsing, fsync, archive history and recovery, so it is not end-to-end live capacity. The present live MemoryHigh margin rules out approving even 2x ingestion from this fixture alone. Candidate shallow-book digest is also slower (8-market/100-level median 2.73 ms old versus 4.10 ms candidate); deep 32-market digest is 131.04 versus 112.57 ms. This is not a uniform CPU improvement. Incremental candidate deep-book memory is approximately 1.02 MiB per extra synthetic market between 8 and 32, excluding live transport/history overhead. Multi-source Frontier is NOT authorized or capacity-verified. No 10x claim is made.

A second growth axis is history and storage, separate from per-book replay:

| Assumed scenario | Existing recording-budget runway from current bytes | Hypothetical prefix CPU at 2x/4x historical segment count |
|---|---:|---:|
| Current event/byte mix | 22.18 days | measured approximately 5.3–6 CPU s per five-minute v2 batch |
| Twice aggregate stored bytes/s | 11.09 days | approximately 11 CPU s/batch if all prefix costs scale linearly with 2x segment count |
| Four times stored bytes/s | 5.55 days | approximately 22 CPU s/batch if all prefix costs scale linearly with 4x segment count |

Runways assume no budget change/deletion and constant payload mix/compression. Prefix figures are conservative unvalidated models, not replay benchmarks; event rate does not necessarily increase segment count while time-based rotation dominates. Doubling providers with similar pipelines would add their independent retained state, bytes and validation work; different sources can have very different payload/lineage costs. Current batches use roughly 2 MiB for 9–10 new segments against 128-segment/32 MiB limits, but this does not prove safety of larger/multiple-source batches under 256 MiB memory. Full-store working sets and I/O mix must be measured first. [Storage model](evidence/host-capacity-20261020/storage-growth-model.json).

## 14. Remaining inefficiencies

- Full event-chain startup is still expensive in CPU/read I/O, but streaming and full validation are retained; trusted checkpoint architecture needs a separate integrity design and benchmark.
- Recorder's current historical state/manifest/checkpoint behavior needs full-store isolated verification before transition. No safe live hot patch or restart is authorized.
- Veritas prefix validation approximately 5.3 CPU seconds per five minutes is measurable but small. Incremental identity/index redesign has correctness cost disproportionate to current host benefit.
- Durable journal history still grows; compression targets frequently rewritten heads, not an excuse to prune scientific/account evidence. Protected 24 GiB capture budget versus 90-day retention and cross-writer reserve coordination need an approved preservation plan. Current free space is ample, so no risky automatic archival, budget expansion or protected restart was performed.
- Analytics p95 256 ms slightly exceeds the empirical 250 ms review target. Physical history reads are eliminated; bounded aggregation/serialization remains. No cache/invalidation redesign was justified for this minor residual at 14% host CPU and no API failures.
- Pinned scientific Veritas modules remain byte-identical, including older shared algorithms where applicable. Its measured ordinary qualification cost is dominated by index setup/progress publishing; porting unrelated math changes into frozen runtimes for hypothetical future training would require separate identity/validation evidence.
- Small scheduling catalogs do not justify persistent indexing/cache invalidation. The real qualification worker indexed 34,988 artifact files (456 MB), installed 39,245 watches and spent 1.94 seconds on event-index setup plus 1.70 seconds publishing 270 progress observations. Only one reconciliation/scan (0.049 seconds) and zero fallbacks were recorded. This cost is material within a four-second tiny job, but at ordinary roughly half-hour director cadence its host duty is negligible. Narrowing watches without preserving hard-link/move/update accounting or removing artifact caps was rejected; high-frequency future qualification should benchmark a persistent shared index separately.
- Larger Lab/learning jobs can be refused by explicit cgroup budgets; this is real constrained capacity, not a code speedup. More concurrency is not justified by short fixtures.

## 15. Remaining hardware constraints

No demonstrated host-wide physical CPU/RAM exhaustion under today's ordinary workload remains established after fixes. Nearly full swap is not proof that RAM must be upgraded. The current unmovable protected-recorder local limit and missing safe full-store verification are the primary operational blockers. Do not prescribe hardware as a substitute for fixing those.

Smallest next step is safe isolated full-store verification with a valid sustained recorder margin or separate staging capacity, followed by explicit recorder transition approval. Any proposal to alter its limits/working-set layout must quantify reserve, peaks, rollback and source durability separately. Extra hardware/separation would make staging and concurrent large training safer, but the amount needed cannot honestly be inferred from a 2000-frame in-memory benchmark. Existing hardware can support serialized bounded work; unconstrained multi-source growth and multiple large workers remain unsupported. Four 2 GiB Laboratory budgets cannot fit within the 1792 MiB API cgroup; two simultaneous 4 GiB jobs plus 2 GiB reserve need 10 GiB available, exceeding the measured approximately 8.7 GiB. These are cap/reserve calculations, not measured peaks. Main default one 512 MiB Lab worker fits; small explicit preview budgets can fit while its default 512 MiB worker budget cannot leave coordinator reserve under its own 512 MiB cap. Use lower explicit operational budgets/serialization or a separately validated external-worker architecture; never change evaluation semantics.

The 24 GiB recorder budget, not current root free space, imposes the approximately 22-day recording horizon. The smallest practical next change is an approved, validated storage-budget/retention/archival plan with coordinated disk reserves, plus protected full-store verification and transition approval. This need not imply new hardware, but automatic expansion to a 90-day archive would ignore API/journal/unrelated growth and recovery working sets. No such expansion is approved here.

## 16. Final readiness and verdicts

Final verdicts after sustained observation:

| Question | Verdict | Evidence and remaining condition |
|---|---|---|
| Host efficiency | SUBSTANTIALLY IMPROVED | Comparable exact-work wins plus deployed 61-minute evidence; no new OOM/restart, preserved useful throughput and 93.9% lower observed I/O full PSI |
| Current MIDAS capacity | CONDITIONALLY SUFFICIENT | Routine services, a completed scheduled qualification and bounded serialized work; recorder margin, timing quality and sustained heavy-research verification unresolved |
| Reality production transition | REQUIRES MORE VERIFICATION | No restart authorization; 64 MiB full-store gate unmet; synthetic replay is insufficient |
| Frontier infrastructure | NOT READY | No multi-source/full-recovery/end-to-end growth evidence; current protected working set has no accepted expansion margin |

Normal operation is conditional; Reality deployment is not approved by this report; Frontier development must preserve current isolation and cannot start ingestion expansion; another unattended campaign is not certified. No live execution or campaign was enabled. This mission stops at an **EXTERNAL/SAFETY VERIFICATION BLOCKER**, with meaningful deployed improvements and a completed resource endurance window, rather than full operational acceptance. Full-store Reality verification remains denied by the unchanged protected-recorder gate; its restart and resource/budget transition are not authorized. Remaining low-duty optimization candidates and larger integrity-sensitive redesigns do not justify additional runtime changes at this measured load. All independent meaningful work is complete. Own collectors exited normally; required services and timers remain running with normal API restart policies.

## Measurement and reproduction

Raw private operational artifacts: `/home/charlie/midas/data/host-capacity-20261020/` (gitignored). Curated non-state evidence is in [evidence/host-capacity-20261020](evidence/host-capacity-20261020/). No account-state fixture or full raw process trace is committed.

`host_capacity_sample.py --output <new.jsonl> --seconds 3660 --interval 15` and `host_capacity_observe.py --output <new-health.jsonl> --seconds 3660` are read-only collectors. `host_capacity_summary.py <jsonl> --since <epoch> --until <epoch> --output <summary.json>` streams exact windows. Device await is mean interval service latency, not tail append latency; PSI avg10 is sampled, not averaged cumulative stall time; CPU percentages identify one-core versus six-core denominator. Missing io.stat is unavailable, not zero. Some collected transient units printed 256 KiB MemoryPeak after cgroup disposal; these stale post-exit values are not used as benchmark peaks. In-process `/proc/self/status` VmHWM and live sampled cgroup values are used instead. One-shot jobs may occur between process samples; journals supply their completed CPU/status evidence.

`benchmark_paper_state_storage.py --database <NEW disposable path> --commands 64` and `benchmark_reality_capacity.py` are reproducible isolated workloads; keep one-core/memory/swap/runtime caps, no competing heavy test, and pressure abort checks. Benchmark scripts reject existing/production output paths. Financial state hashes and generated episode/scientific semantics must remain equal. Do not weaken admission or clear caches to reproduce attractive numbers.

## Checkpoint journal (historical steps, superseded by final sections)

## Operational journal

- Initial checkout: main `3784dd9`, clean; origin configured. Read historical reliability reports and inspected current user/system services. Protected recorder remains PID 863193; paused shadow workers and frozen campaigns remain untouched.
- Verified six physical i5-9400F cores, 16,665,567,232 bytes RAM, 4 GiB swap, ext4 NVMe root (468 GiB, approximately 168 GiB available). CPU pressure currently lower than historical incidents; significant I/O pressure. Initial MemAvailable about 7.6 GiB, memory PSI zero, little active swapping; full swap alone is not evidence of thrashing.
- Current main API PID 2737736: approximately 336 MiB RSS, 1.50 GiB cgroup (mostly cache); initial interval reads reached 42 MiB/s. Separate Reality interface demo API PID 2688994 writes roughly 3 MiB/s during refresh. These are investigation targets, not yet proven causes. Recorder remains near MemoryHigh; no heavy archive replay is admitted.
- Started low-frequency host/process/cgroup time series (15-second sampling), preserving unavailable counters as null. No invasive recorder profiler, cache eviction, swap clearing, service restart or global tuning.

## Resume checkpoint

Investigate API reads/WAL traffic, duplicate state serialization and synthetic demo overhead first; measure controlled disposable workloads before edits. Verify current scheduler and Veritas costs and protected recorder anonymous/file split. Report all measured classes, limitations, production identities and rollback before final verdicts. Required 16 report sections and four verdicts remain to be completed.

### Cycle 1 — selective API history reads

- Root cause proven by `EXPLAIN QUERY PLAN`: source-filtered recent simulations chose `ix_records_source` and walked newer synthetic observations. Main API physically read ~42 MiB/s, NVMe ~10,600 read IOPS / 88% utilization; host I/O full PSI ~13–14% while CPU remained ~70% idle.
- Bounded read-only live probe: original exceeded 100,000 VM instructions and was aborted after 26 ms; existing kind index returned all 24 simulation rows in 0.383 ms, under 1,000 VM instructions. This is a lower-bound comparison, not an old-query completion benchmark.
- Equivalent disposable 20,024-row / ~20 MiB workload, seven repetitions, exact row equality: original median CPU 7.063 ms, new 0.02594 ms (~272x); median wall 8.285 ms versus 0.02597 ms (~319x). No schema change, journal change, durability change, cache eviction or source-integrity change.
- Implementation pins SQLite source-filtered history to the existing migration-001 kind index. PostgreSQL keeps its existing query. Tests verify mixed sources, row-id ordering, limits, parameter binding and a VM-step budget preventing unrelated-history scans. Two regression tests passed; ten existing API/demo/recording-isolation tests passed. Mypy passed for storage module; Ruff and formatting corrected.
- Deployment plan: only restart the authorized main API, retaining existing cgroup bounds and a temporary one-attempt policy; preserve old module/unit copies and head receipt. Do not touch protected recorder, interface API or frozen services. Abort on startup/health failure or recorder identity/OOM changes. Query code rollback is restoring the saved module followed by a separately bounded main-API restart. No database migration or data rollback is needed.

### Cycle 2 — paper transition CPU

- Captured a read-only 940,863-byte durable account head and latest command into local benchmark artifacts. Profile: three transitions spent 0.323/0.489 profiled seconds in recursive deepcopy and 0.117 seconds in summaries. Internal summaries unnecessarily included all 200 retained decisions.
- Ten equivalent transitions, identical final canonical result hash: original median CPU 79.467 ms; omit decision histories from internal totals 39.630 ms; implemented detached JSON clone plus compact internal summaries 29.850 ms (62.4% less CPU, 2.66x throughput for this operation). No history is dropped from durable state or public full-summary responses. Reconciliation still runs; journal and strategy versions stay identical.
- 82 paper/simulation/property tests passed, including crash boundaries, recovery, financial invariants, and new nested-output isolation/no-op isolation assertions. Mypy and Ruff pass. Scientific evaluation semantics and existing journal streaming are retained.
- Main API query-fix startup completed with CHECKPOINT_VERIFIED around 15:16 UTC after replaying >404k journal events; exact duration/resource deltas will be derived from receipts. No automatic retry, OOM or recorder restart occurred. The broker change is not yet loaded by this process.

### Cycle 3 — research admission reserve

Code audit found launch admission checks only 2 GiB MemAvailable regardless of the requested worker cap (default 3 GiB). It could admit a 3 GiB worker with only 2.1 GiB available, violating the intended production reserve. Global cross-root serialization already restricts active research to one worker. Preserve that measured conservative concurrency; improve admission to require the worker's effective cap *plus* the existing 2 GiB reserve, without reducing any existing pressure gate. This is prevention of over-admission, not a measured CPU speedup or a claim of greater research throughput.

### Interface rollout preparation

The separate Reality interface API is a legitimate isolated demo service, not an orphan. Its old broker performs more full-history serialization. Seven equivalent captured-head transitions: 80.314 ms CPU before, 29.307 ms after (63.5% reduction), identical canonical results. Prepared an independent physical release under `~/.local/share/midas-capacity/interface-3647c03`, based on exact Reality `c833200` API/package source with only storage and broker overrides. The protected recorder checkout is unchanged. Release imports resolve to that independent directory. First test command omitted pytest's asyncio auto setting (9 configuration failures); corrected invocation passed all 14 paper/query tests under a 384 MiB, one-core disposable unit. No interface restart yet.

Admission implementation now requires requested MemoryMax plus the existing 2 GiB reserve before artifacts/systemd launch, using the 512 MiB effective cap for read-only qualification. New budget receipts expose that full minimum. At 4 GiB available a 3 GiB worker is rejected, while a 512 MiB worker can fit; 5 GiB permits the former. 62 Arena/admission/scheduler/campaign tests passed in the one-core/768 MiB disposable unit (256.3 MiB observed unit peak, zero swap). No existing threshold is weakened; extra waiting is explicitly deferred work rather than a throughput improvement.

### Cycle 4 — quota-induced waiting

- Bounded identical SHA256 workload, sequential disposable 64 MiB / zero-swap cgroups: 10% CPU cap completed in 10.792 s wall / 1.071 s CPU, accruing 9.709 s throttling and local CPU PSI avg10 50.22%; 100% cap completed in 1.072 s wall / 1.072 s CPU, zero throttling, same digest. This demonstrates quota waiting without physical six-core saturation. It is a scheduler mechanism benchmark, not a qualification-job throughput benchmark.
- Removed main's hidden qualification override to 10%. New jobs honor their explicit 1–100% requested CPU budget; default is one core, with global one-worker admission, retained 512 MiB memory, low priority, idle I/O and network restriction. Explicit smaller budgets are honored. Relevant 11 admission/qualification/budget tests passed after this change; complete preceding 62-test run and Mypy/Ruff passed. No active job was retuned.
- Main commit `58d6213` includes reserve and quota changes. Main API single-attempt restart at 15:24:10 UTC loads `3647c03` broker and `58d6213` admission; full streaming journal verification is in progress under unchanged 1536/1792 MiB limits and zero swap.
- Veritas audit found its separate launch path already uses one CPU, but ordinary workers have a fixed 4 GiB cap. Applied the same reserve-aware admission there, using that actual cap (6 GiB available required; qualification 2.5 GiB). No Veritas analysis code, release identity, lineage, source campaign or output was rewritten. 19 admission/qualification/director tests passed; Veritas checkout change committed independently. Subsequent timer imports load this gate; the immutable gap-detail runtime remains untouched.

### Later architecture checkpoint — 15:52 UTC

- Further audit found the isolated interface's legacy Arena launcher had no host-wide admission and its spawned workers could resolve the editable recorder tree. Added a reproducible pinned API-only release builder: preserves exact Reality/API baseline, overrides only measured broker/query paths plus operational admission/Laboratory guards, checks before artifact creation, adds zero-swap and correct explicit worker import paths. A real disposable legacy worker completed 30 generated episodes; denied admission created no job; duplicate admission remained idempotent. This test passed in 6.66 s under a 512 MiB / one-core unit.
- Added the interface Arena root to primary/Veritas cross-root catalogs and v2 batch defaults. Fifteen admission/batch regression cases passed. No protected recorder source file was modified.
- Laboratory allowed four 2 GiB address-space worker budgets inside an API cgroup capped at 1792 MiB (interface 512 MiB). Added admission against actual cgroup/ancestor MemoryHigh/Max, coordinator RSS and 128 MiB reserve. Laboratory holds the existing host admission lease through pool shutdown, so Arena/Veritas defer rather than overlap research. No evaluation rule, seed, CampaignSpec, plan or run_group calculation changed. This is explicit serialization/admission, not eliminated CPU work. Valid requests remain READY on pressure denial; launch-thread failure becomes recoverable INTERRUPTED and releases the lease.
- Fifteen original/new Laboratory cases passed under a 1536/1792 MiB one-core cgroup, 141.7 MiB observed peak; four targeted reserve/lease/thread-failure cases subsequently passed. Scientific output equality across one/two worker fixtures still passes. Mypy now passes for all six modified runtime modules; Ruff passes.
- Raw demo recording budgets were 829,256,334/1,000,000,000 bytes (main) and 42,435,008/100,000,000 bytes (interface), leaving short runways. Allocated bounded 4 GiB per API based on >168 GiB free disk, preserving >20 GiB recorder reserve plus staging/research commitments. This allocates capacity, does not save CPU or delete anything. Existing explicit retention remains necessary; no financial journal/model/raw evidence was pruned.
- Multiple API-only rollout stages are intentionally retained in local receipts. They are maintenance windows, not endurance passes. The final 60-minute stable observation was planned to begin only after final admission/Laboratory imports and recording budgets were loaded. The recorder remains PID 863193, still old code and near MemoryHigh; sustained research/full-store Reality testing is unadmitted.

Latest prepared interface release: `~/.local/share/midas-capacity/interface-final-20261020`; exact release regression is running before deployment. Primary/Veritas catalog and Laboratory changes are awaiting final commit/restart. Immutable Veritas release must be rebuilt from the original with only the admission wrapper changed; scientific file hashes and v1/v2 identities stay unchanged. Final source/remote synchronization and report sections remain outstanding.

### Cycle 5 — durable account write amplification (17:33 UTC checkpoint)

- After read scans were removed, ordinary API I/O still rewrote an approximately 941 KiB account head for each observation. Added a versioned physical account-only JSON codec: complete logical state is retained, every head/journal transaction remains FULL-sync, event journal JSON and logical hashes are unchanged. Compression is used only when beneficial (4 KiB–64 MiB); larger/incompressible states preserve plain JSON. Decoder rejects bad versions, expansion bounds, wrong lengths, truncation and extra streams.
- Comparable disposable SQLite benchmark, two repetitions per version, 64 identical durable observations plus final FULL checkpoint: plain 170,172,416 written bytes versus encoded 7,008,256 (95.88% reduction; 24.28x). Logical state SHA256 identical in all four runs. Mean CPU 6.8444 versus 6.6794 s; mean wall 7.0860 versus 6.8014 s. Worker VmHWM maxima 94.42 versus 90.22 MiB. These fixture ratios are not claimed as whole-host gains; production snapshots contain six different scenarios and compress less than the single-market fixture.
- Read-only production head inspection verifies both existing logical checksums (main approximately 941 KiB, interface 934 KiB); no compressed production head has been written yet. Prepared complete pre-codec main release `main-pre-codec-aee2005` and a disposable encoded-journal database for an actual old-code rollback probe during the planned API stop.
- Codec/crash/rollback tests pass, including before/after-commit recovery of compressed heads, idempotent commands, invalid encodings, rollback of all head updates if any checksum fails, journal JSON remaining plain, and current-head materialization preserving revisions/hashes. Existing paper tests pass. The explicit full replay helper now consumes an iterator, avoiding a whole-journal list while preserving every transition/hash check and adding snapshot checksum validation.
- Exact interface release regression passed 30 tests in the real working-directory context with explicit app-directory precedence. Initial collection exposed missing baseline scripts; the release builder now includes the complete baseline script closure and new inspection/audit tools. Earlier interface stages pinned core packages but cwd could select old API code: this was reproduced and is corrected by explicit Uvicorn `--app-dir`; startup logs now identify the loaded storage source and codec.
- Background research units now request CPUWeight=10 (critical units retain default 100); Laboratory pool children use Nice=19 within the API cgroup. This prioritizes availability; it does not remove work or claim lower CPU cost. No protected unit property changed.

Remaining immediate steps: commit/activate codec only after old-code disposable rollback probe, load the verified interface app directory, restore normal bounded API restart policies after stable readiness, collect a fresh >=60-minute post-codec window, export compact receipts, complete all 16 report sections and push. Full-store Reality staging and sustained heavy research remain blocked by the unchanged protected-recorder margin gate; do not weaken it or restart the recorder.

### Active verification checkpoint — 17:56 UTC

- Main API PID 3717987, interface API PID 3725032; both READY with codec and unchanged logical validation. Protected recorder still PID 863193, no new OOM/max events. Both normal on-failure policies restored without changing PIDs.
- Final sampler PID 3726902: `host-post-codec.jsonl`, 15-second samples, expected completion about 18:43:50 UTC (20:43:50 CEST). Final observer: `post-codec-final.jsonl`, 61 minutes from about 17:42:24 UTC; expected completion about 18:43:24 UTC. Earlier `post-codec-endurance.jsonl` is superseded after fixing nested telemetry capture; do not combine windows and claim a clean run.
- Actual scheduled Veritas qualification completed in this window (268 events / 3.72 CPU seconds); full-store Reality remains refused. Latest short summary: approximately 14.2% host CPU, 2.05% CPU PSI, 0.77% I/O full PSI, zero memory PSI. Final numbers must replace these interim values only after full observation.
- Main/source branches pushed through checkpoint 97543e0; subsequent offline summarizer/diagnostic documentation updates are safe and await final synchronization. No remaining runtime code rollout is planned. Curated evidence committed; raw operational files remain local/gitignored.
- Finish: collect final summaries for exact observer window; normalize journal progress and I/O; assess source-health failures honestly; validate protected PID/counters/frozen hashes/latest finalized segment; confirm timer jobs and no orphan test work; replace provisional report, commit/push, clean only own monitors if still running. Do not restart recorder or bypass gates.

### Final closure — 18:49 UTC

The 61-minute final observer and 62-minute sampler exited normally. Production PIDs remain main 3717987, interface 3725032, recorder 863193; API Restart=on-failure restored, NRestarts=0/0, recorder historical NRestarts=1 unchanged. Frozen hashes match, two independent finalized-segment receipts match manifests, no unrelated service was changed, no shadow/campaign was activated. A pre-existing failed shadow-canary unit remains failed/inactive with PID zero; it was not reset to disguise historical failure.

Final metrics, normalized observations, cgroup events, source-state exceptions and storage runway are exported in the evidence directory. Final report supersedes all provisional checkpoints above. Overall acceptance remains conditional for the documented protected full-store and long-term storage constraints; no hardware insufficiency or Frontier readiness is fabricated. Further safe high-impact work on the present measured hot paths is exhausted; remaining architectural changes require new full-scale evidence or protection/retention decisions. This report/evidence is finalized for ordinary commit/push synchronization. Do not repeat expensive diagnostics or leave own collectors running.
