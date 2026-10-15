# Veritas Mission 2 Operations

**Latest read-only runtime check:** 2026-10-15 20:20 UTC
**Services:** `midas-veritas-observatory.service`, `midas-veritas-source-analysis.service`, `midas-veritas-research-director.service`
**Timers:** `midas-veritas-observatory.timer`, `midas-veritas-source-analysis.timer`, `midas-veritas-research-director.timer`

## Latest runtime state — 2026-10-15 20:20 UTC

- The observer timer completed scan 33 at 20:00:54 UTC and is next due at
  20:31:39 UTC. The fixed coverage pilot has three scans / 120 selected slots
  / 97 quality-valid pairs / 23 invalid pairs / zero skipped sequences. Its
  fixed stop is 2026-10-16 19:00:55 UTC. The cumulative 33-scan panel has
  1,167/1,320 valid pairs across 616 IDs; all five economic gates remain
  zero-positive and the best top edge is -$0.001/share.
- The finalized-source timer completed at 20:14:36 UTC. It processed 128
  segments / 31,477,866 bytes in 212 seconds, using 10.618 CPU seconds and
  147.7 MiB peak memory with no swap. The current summary is
  `catching_up_finalized_source`: 3,388/4,260 segments / 842,162,936 bytes
  processed, with 872 segments / 269,424,035 bytes pending. Its campaign
  window has 212,048 frame records, 192,293 touched states, and 186,344
  quality-valid states across 47 markets; positive top-ask and full-depth
  counts remain zero. The 912 campaign-window gap markers comprise 911
  `book_resynchronization` and one `connection_failure`; the aggregate provides
  no event timestamps or outage durations. The next timer is due at 20:40:16
  UTC. Summary digest: `c32f8e0796c9c8c814e7fc5eb0538042667a908b0d90ad6b589af551d05608e4`;
  summary-file SHA-256: `f3517dc2950bb5a6436e40d5605ac4ff492ae3e4c70477e982a6be572eee351f`.
- The 20:15:44 UTC Director cycle admitted
  `job-16d651741d304fa098f87cc9` for scan 33. Arena completed all 33 events at
  20:16:26 UTC with exit status 0; finding
  `veritas-qualification-v1-010c9e464077e301` reports zero positives at all
  five economic gates and a complete zero-row candidate replay. The Director
  manifest was last updated before job completion and still projects
  `QUEUED`; the 20:45:05 UTC cycle is the reconciliation point. No manual
  poll or retry was started. See [Gate F checkpoint
  019](VERITAS_MISSION2_GATE_F_CHECKPOINT_019.md).
- At 20:02 UTC, the Reality recorder service was active with zero restarts and
  both configured market-data DNS names resolved. Its last journal warning
  remains `DEGRADED` at 04:57:26 UTC, but a read-only metadata audit found
  1,790 finalized segment files mtime-stamped at or after that warning. The
  first followed within about eight seconds, the largest adjacent mtime gap
  was 36.51 seconds, and the newest was at 20:05:04 UTC. This rules against a
  prolonged recording-output outage in the audited interval. However, the
  20:14 source summary counted 911 `book_resynchronization` markers and one
  `connection_failure` in its campaign window. The analyzer treats gap records
  as reconstruction barriers, but the aggregate does not measure outage
  duration or give event timestamps. This does not prove gap-free frames or
  upstream feed completeness. See [continuity audit
  001](VERITAS_MISSION2_RECORDER_CONTINUITY_001.json). The frozen Reality
  shadow service was observed active after one automatic restart at the prior
  19:57 check; no campaign or service was restarted or changed for this audit.
- A targeted read of the finalized segment covering the connection failure
  verified all 92 records and matched the segment SHA-256 to its catalog
  sidecar. The `connection_failure` at 04:57:26.717847 UTC matches the DNS
  warning; the first later receiver frame was at 04:57:29.162854, 2.445
  seconds later. This does not prove all eight market books recovered or were
  fresh. See [gap-timing artifact
  001](VERITAS_MISSION2_RECORDER_GAP_TIMING_001.json).
- Host memory available was 8.9 GiB; swap use was 3.5/4 GiB, a resource
  pressure indicator in the 20:16 host snapshot. The filesystem
  had 199 GiB free (56% used). Reality recordings occupied about 1.1 GiB at
  the audited count; the Veritas observatory runtime directory was about 38
  MiB at the previous size check. Midas and Reality API health endpoints and
  both local web interfaces returned HTTP 200 at 19:57 UTC; no newer health
  probe was run here.
- The frozen-campaign v1.4 audit found public markouts but no suitable
  strategy target or execution/P&L labels. The 20:16 Director manifest now
  reports `NOT_READY_NO_CANDIDATE_RELEVANT_TARGET`; this remains readiness for
  its separate snapshot dataset and does not ingest the frozen-campaign
  report. See [Gate C checkpoint
  003](VERITAS_MISSION2_GATE_C_CHECKPOINT_003.md).

The one-shot Veritas services are inactive between scheduled runs by design.
The recurring timers remain active; do not manually invoke overlapping runs.

## Historical runtime snapshot — 2026-10-15 15:16 UTC

- All three Veritas user timers are active. Scan 23 finalized at 15:00:26 UTC, the finalized-source replay exited at 15:14:31 UTC, and the Director cycle exited at 15:15:37 UTC. Arena completed its qualification at 15:15:47 UTC. The next scheduled UTC runs are 15:30:10, 15:40:45, and 15:45:00. The oneshot services are inactive between runs as expected.
- Latest scan: `scan-20261015T150026Z-56e1e44d7837`, captured at 15:00:26 UTC and finalized under v4. The analyzer has 23 processed snapshots and no pending snapshots. The cumulative panel has 920 selected observations, 825 request/receipt-valid pairs, 95 invalid pairs, 418 distinct market IDs, and 189 pairs passing the prior reported-age/skew gate. The paired increase is 636/920 (+69.13 percentage points); all five economic gates remain zero-positive.
- The latest six-frame bounded discovery union contains 300 unique IDs: 190 supported same-condition V1 binary pairs and 110 explicit exclusions (84 augmented NegRisk records and 26 unsupported outcome relationships). The selected panel has 40 markets, 36 rotating and four available frozen controls. Scan 23 overlaps scan 22 on five IDs, one rotating and four controls, so 35 rotating selections changed. Liquidity counts are 15 high / 11 medium / 14 low; expiry counts are 19 near / 14 medium / 7 long; spread counts are 21 tight / 14 medium / 5 wide.
- Runtime data uses 21,785,641 bytes under `data/veritas-observatory/`, below the 1 GiB hard cap. Snapshots and derived runtime artifacts are ignored by Git; versioned docs record identities and hashes. Do not prune or raise the cap without a separate retention review.
- The 15:00 v2 scan used seven HTTP attempts (six Gamma frames and one CLOB batch) out of a 14-attempt maximum. Thirty-six selected pairs passed the quality gate; four had empty No ask sides. The frozen control file hash remains `9578217e20dcc7d1c65fa110f0ed7c689b55483b61191f1aae8d30c9b7300d9a`.
- The finalized Reality source analyzer remains `catching_up_finalized_source`: 2,161 of 3,668 cataloged finalized segments processed, with 1,507 segments / 396,434,833 bytes pending through ordinal 269,843. The 15:10 UTC recurrence processed 124 segments / 33,163,975 bytes in 227 seconds, using 11.36 CPU seconds and 155,504,640 bytes peak memory. Its partial prefix contains 70,950 campaign-window frame records, 59,343 touched market-frame states, and 57,798 quality-valid states, with zero positive top-ask and full-depth states. Summary digest: `37715a41a176feb08db23867b5f2c7b9e39647a3f9df43a770df049c497dd6e3`; summary file SHA256: `08bd70741083b0d689c8df5d3bdf9b3fbee7683670261fea5932dbaccba6199a`. The 12:43 source-window interpretation correction is recorded in [Gate A checkpoint 017](VERITAS_MISSION2_GATE_A_CHECKPOINT_017.md).
- The 15:15 Director cycle reconciled scan 22, then admitted `job-bf0dbe4c773f4cfe9832fd8d` for scan 23 using the 15:14 source summary. Arena completed all 23 events at 15:15:47 UTC; finding `veritas-qualification-v1-a695104c7dcbb82a` reports zero positive states at all five gates. The Director manifest last updated at 15:15:32 UTC projects `QUEUED` for scan 23 and retains scan 22's finding, while its event archive records scan 22 completion and scan 23 admission. The next scheduled cycle at 15:45:00 UTC is the reconciliation point. No manual poll or retry was started. See [Gate F checkpoint 011](VERITAS_MISSION2_GATE_F_CHECKPOINT_011.md).
- At 11:30 CEST an observer run failed with `Invalid frozen control cohort` because the deployed scanner rejected the file's legacy version tag. The frozen file remained unchanged, current code accepts both tags, and scheduled scans through 17:00 CEST succeeded. No manual recovery scan was run.
- The protected Reality user services were active during the last explicit read-only check. The separate Reality worktree was clean. No Reality service was restarted or modified, and no campaign data was changed.

## Research Director history projection

The `/api/arena/research-activity` projection now includes a digest-checked
history of each displayed Director's recent events. It scans at most 128
event files per Director, reads at most 64 KiB per event, and returns up to
eight records. The API verifies each event filename against the canonical
payload digest and confirms the Director identity before projecting selected
fields. It does not alter Director manifests or events. The last read-only
projection check at 12:55 UTC returned eight verified entries from the
Director's then-19-file event archive, marked the view truncated, and reported
zero invalid artifacts. The full append-only event directory remains the durable record; the UI and API
history are bounded views. See [Gate G checkpoint
004](VERITAS_MISSION2_GATE_G_CHECKPOINT_004.md).

## Resource and network bounds

| Control | Configuration |
| --- | --- |
| Cohort size | 40 selected markets; service validates 30–50 |
| Stable controls | Target 8; unavailable frozen IDs are reported, not outcome-replaced |
| Discovery | Six Gamma query frames, at most 50 returned rows per frame; rotating 30-minute page offsets |
| Book reads | One public CLOB `/books` batch for selected pair assets |
| Request pacing | One second between public requests; seven logical reads planned, 14 HTTP attempts maximum |
| CPU | `CPUQuota=5%`, `Nice=19` |
| Memory | `MemoryMax=256M` |
| Storage | 1 GiB observatory root cap; scanner fails closed at projected bound |
| Runtime | 10-minute systemd start timeout |
| Privileges | `NoNewPrivileges=true`; no credentials or authenticated requests |
| Director cycle | Timer at :15 and :45 UTC; skips evidence older than two hours; one scan-pinned Arena admission |
| Director service | CPU 5%, memory 512 MiB, private temp, `AF_UNIX` socket family only |
| Qualification job | CPU quota 10%, memory 512 MiB, wall 300 seconds, source cap 64 MiB / 512 events, `AF_UNIX` only |
| Write access | Veritas observatory and this checkout's isolated `data/arena` roots only |

The observer uses public Gamma GET discovery and unauthenticated public CLOB reads. It makes no orders and has no wallet, deposit, or authenticated trading path. Request/receipt timing does not prove response-batch atomicity, venue sequence, upstream queue age, or executable quote lifetime.

## Data lifecycle and versioning

The scanner writes exclusive, content-hashed compressed snapshots. `continuous_analysis.py` verifies finalized snapshot identities and immutable event digests, then atomically updates analyzer state and summary. It accepts at most 100 pending snapshots per run and rejects malformed, oversized, digest-mismatched, or unsafe inputs. v4 records paired legacy/current gate outcomes and per-market sample coverage. Snapshot fingerprint changes are sampled inter-scan changes, not true venue update rates.

The one-shot NegRisk studies cover the complete nine-outcome Strava set and a
second seven-market OpenAI IPO group. The OpenAI group was enumerated by seven
direct Gamma market reads and checked against the adapter's on-chain question
count; the Gamma group filter returned 20 unrelated rows and no matching
members. A second CLOB refresh and a public WebSocket cross-check each returned
all 14 books. Both source captures failed the 5-second age and 250 ms skew
rules. The WebSocket top prices and last-trade prices matched the REST response
for all tokens, while full displayed depth changed and the stream supplied no
sequence field. The new stream replay runner verifies the saved frame and its
REST reference. These fixed-group reads remain separate from the recurring
observer timer. See [Gate A checkpoint
016](VERITAS_MISSION2_GATE_A_CHECKPOINT_016.md).

## Previous Gate A checkpoint 019 — evidence at 14:21 UTC

The 14:01 UTC scan finalized as snapshot 21. The v4 panel contains 840
selected observations, 751 quality-valid pairs, 89 invalid pairs, 176 legacy
age/skew-valid pairs, and 367 distinct markets. The paired yield increase is
575/840 (68.45 percentage points). All five economic gates remain
zero-positive. Scan 21's bounded union has 300 unique IDs, 198 supported
pairs, and 102 explicit exclusions; its 40-market sample retained 37 rotating
markets and three available frozen controls.

The 14:13 finalized-source summary contains 40,459 campaign-window frame
records, 30,809 touched states, and 29,749 quality-valid states. The prefix
remains incomplete with 1,630 finalized segments / 430,839,649 bytes pending;
positive top-ask and full-depth counts remain zero. The earlier 12:43 summary
contained 4,078 campaign-window frames; checkpoint 016's interpretation of
that counter as zero frames was incorrect and was corrected in checkpoint 017.

The 14:15 Director cycle recorded completion of scan 20 and admitted scan 21.
Arena completed all 21 events at 14:16:20 UTC, but the manifest still showed
`QUEUED` for scan 21 and scan 20 as last qualified at this check. The next
Director cycle at 14:45:16 UTC is the scheduled reconciliation point. See
[Gate A checkpoint 019](VERITAS_MISSION2_GATE_A_CHECKPOINT_019.md), [Gate F checkpoint
009](VERITAS_MISSION2_GATE_F_CHECKPOINT_009.md), and [research inventory
022](VERITAS_MISSION2_RESEARCH_INVENTORY_022.json).

## Previous Gate A checkpoint 018 — scan 20 evidence

The 13:31 UTC scan finalized as snapshot 20. The v4 panel contains 800
selected observations, 714 quality-valid pairs, 86 invalid pairs, 167 legacy
age/skew-valid pairs, and 349 distinct markets. The paired yield increase is
547/800 (68.38 percentage points). All five economic gates remain
zero-positive. Scan 20's bounded union has 297 unique IDs, 153 supported
pairs, and 144 explicit exclusions; its 40-market sample retained 37 rotating
markets and three available frozen controls.

The 13:43 finalized-source summary contains 29,198 campaign-window frame
records, 21,747 touched states, and 21,041 quality-valid states. The prefix
remains incomplete with 1,699 finalized segments / 450,044,085 bytes pending;
positive top-ask and full-depth counts remain zero. The earlier 12:43 summary
contained 4,078 campaign-window frames; checkpoint 016's interpretation of
that counter as zero frames was incorrect and was corrected in checkpoint 017.

The 13:45 Director admission completed all 20 events in Arena, but its
manifest still showed `QUEUED` and scan 19 as last qualified at this check.
The next Director cycle at 14:15:29 UTC is the scheduled reconciliation
point. See [Gate A checkpoint 018](VERITAS_MISSION2_GATE_A_CHECKPOINT_018.md),
[Gate F checkpoint 008](VERITAS_MISSION2_GATE_F_CHECKPOINT_008.md), and
[research inventory 021](VERITAS_MISSION2_RESEARCH_INVENTORY_021.json).

## Gate A checkpoint 016 — historical evidence


The 12:31 UTC observer scan remains finalized as snapshot 18. It has 32
quality-valid pairs and eight empty-ask invalid pairs; the cumulative panel has
645/720 quality-valid pairs across 304 distinct markets. All five economic
qualification gates remain zero-positive. The 12:45 Arena qualification
completed all 18 analysis events and found no positive gross state.

The OpenAI IPO stream capture returned a complete 14-token book set in 84 ms,
but its source age reached 17.781 seconds and source timestamp skew was 11.977
seconds. Best bid, best ask, and last-trade prices matched the REST refresh for
14/14 tokens. The current stream schema provides no sequence field, so the
capture does not establish independent sequence freshness. See [Gate A
checkpoint 016](VERITAS_MISSION2_GATE_A_CHECKPOINT_016.md), [Gate F checkpoint
006](VERITAS_MISSION2_GATE_F_CHECKPOINT_006.md), and [inventory
019](VERITAS_MISSION2_RESEARCH_INVENTORY_019.json).

The finalized-source summary referenced by checkpoint 016 contains 4,078
campaign-window frame records, 2,779 touched market-frame states, and 2,739
quality-valid states. Top-ask and full-depth positive counts remain zero, and
the source prefix remains incomplete with finalized segments pending.

The independent Reality source analyzer validates the frozen campaign identity and reads only cataloged finalized `.seg` inputs. It never opens `.open` files. Per run it is limited to 128 segments or 32 MiB of new segment data; each segment is capped at 16 MiB. Catalog scans are bounded. Source state and events retain campaign/code/prefix digests and stop on identity drift. Resource bounds remain CPU 5%, memory 256 MiB, low priority, ten-minute timeout, and Veritas-only writes.

Arena's existing job worker supports a pinned, bounded Veritas qualification task. The recurring Director detects each new finalized v4 scan, checks readiness, admits one idempotent job, verifies the finding digest and source lineage, and reports an evidence-based recommendation. It also validates and records the separate finalized-source summary; it does not coordinate or launch source replay, start strategy/model experiments, or promote a model. See [Gate F checkpoints 001](VERITAS_MISSION2_GATE_F_CHECKPOINT_001.md) and [002](VERITAS_MISSION2_GATE_F_CHECKPOINT_002.md).

## Frozen campaign censoring snapshot

At 08:44 UTC the Gate C analyzer captured 10,165 decisions from one read-only
SQLite transaction. It used `mode=ro` and `PRAGMA query_only=on`; it did not copy
raw observations. The artifact contains 40,660 horizon slots, 930 observed
public measurements, 39,730 censors, and zero pending outcomes in that snapshot.
The campaign writer remains active, so this is an interim view.
`future_observation_unavailable` remains unresolved between quiet venue
activity and feed/cohort coverage. The full event hash chain and a full database
integrity check were not run. See [Gate C checkpoint
001](VERITAS_MISSION2_GATE_C_CHECKPOINT_001.md).

## Read-only inspection

```bash
systemctl --user is-active midas-veritas-observatory.timer
systemctl --user is-active midas-veritas-source-analysis.timer
systemctl --user is-active midas-veritas-research-director.timer
systemctl --user list-timers midas-veritas-observatory.timer --no-pager
systemctl --user list-timers midas-veritas-source-analysis.timer --no-pager
systemctl --user list-timers midas-veritas-research-director.timer --no-pager
systemctl --user status midas-veritas-observatory.service --no-pager
systemctl --user status midas-veritas-source-analysis.service --no-pager
journalctl --user -u midas-veritas-observatory.service -n 30 --no-pager
journalctl --user -u midas-veritas-source-analysis.service -n 30 --no-pager
journalctl --user -u midas-veritas-research-director.service -n 30 --no-pager
du -sb /home/charlie/midas-veritas/data/veritas-observatory
```

Do not launch overlapping manual runs. If a manual run is needed, invoke its oneshot service and wait for completion before reading the relevant summary.

## Preservation

The separate `/home/charlie/midas-reality` checkout remains the protected source of the frozen campaign. Veritas analysis reads finalized source segments only and writes to its own observatory root. Do not restart or alter Reality services for this workflow. No Arena, Laboratory, Prometheus, or historical campaign records are rewritten. No real-money action is permitted.

## 2026-10-15 15:45 UTC scheduled cycle

The 15:30 observer scan completed in 16 seconds using seven public HTTP attempts and 0.622 CPU seconds; the saved store measured 22,696,673 bytes. The 15:40:45 source replay processed 128 finalized segments / 32,016,580 bytes in 225 seconds and 11.290 CPU seconds. It remains within its 128-segment / 32 MiB batch bounds and leaves 1,438 finalized segments pending. The 15:45:04 Director cycle reconciled scan 23 and admitted scan 24. Arena completed the bounded 24-event job in 1.418 seconds; the Director manifest is due for reconciliation at 16:15:11 UTC. The observer, source-analysis, and Director timers remain active. No manual poll or retry occurred.

See [Gate A checkpoint 022](VERITAS_MISSION2_GATE_A_CHECKPOINT_022.md) and [Gate F checkpoint 012](VERITAS_MISSION2_GATE_F_CHECKPOINT_012.md) for artifact hashes, counters, and the current manifest projection.

## 2026-10-15 16:15 UTC scheduled cycle

The 16:00 observer scan completed in 17 seconds after seven public HTTP attempts and used 0.659 CPU seconds. The 16:10:39 source replay processed 128 finalized segments / 32,329,769 bytes in 227 seconds and 11.347 CPU seconds, within its segment and byte bounds. The 16:15:14 Director cycle reconciled scan 24 and admitted scan 25; Arena completed the bounded 25-event qualification in 1.514 seconds. The Director manifest is due for reconciliation at 16:45:03 UTC. The three timers remain active; no manual poll or retry occurred.

See [Gate A checkpoint 023](VERITAS_MISSION2_GATE_A_CHECKPOINT_023.md) and [Gate F checkpoint 013](VERITAS_MISSION2_GATE_F_CHECKPOINT_013.md) for artifact hashes, counters, and the current manifest projection.

## 2026-10-15 16:45 UTC scheduled cycle

The 16:30 observer scan completed in 16 seconds after seven public HTTP attempts and used 0.632 CPU seconds. The 16:40:08 source replay processed 128 finalized segments / 33,042,875 bytes in 221 seconds and 11.037 CPU seconds, within its segment and byte bounds. The 16:45:04 Director cycle reconciled scan 25 and admitted scan 26; Arena completed the bounded 26-event qualification in 1.525 seconds. The Director manifest is due for reconciliation at 17:15:09 UTC. The three timers remain active; no manual poll or retry occurred.

## 2026-10-15 17:15 UTC scheduled cycle

The 17:01 observer scan completed with 40 selected markets, 33 quality-valid pairs, two identical duplicate discovery records, zero identity conflicts, and zero positive economic gates. It used seven public HTTP attempts. The 17:10:17 source replay processed 116 finalized segments / 33,217,726 bytes in 242 seconds, using 12.138 CPU seconds and 122.3 MiB peak memory. Progress is 2,661/3,903 finalized segments; 1,242 / 344,457,128 bytes remain pending. The 17:15:09 Director cycle admitted scan 27. Arena completed all 27 events in 1.619 seconds with zero-positive gates. The Director manifest projection remains queued pending its scheduled 17:45:25 UTC reconciliation. The three timers remain active; no manual poll or retry occurred.

See [Gate A checkpoint 024](VERITAS_MISSION2_GATE_A_CHECKPOINT_024.md) and [Gate F checkpoint 014](VERITAS_MISSION2_GATE_F_CHECKPOINT_014.md) for artifact hashes, counters, and the current manifest projection.

## 2026-10-15 17:33 UTC observer scan 28

The 17:32:11 observer scan finalized with 40 selected markets, 35 quality-valid pairs, five empty No ask sides, and zero positive top, depth, minimum, or fee gates. Its six-frame union contained 300 unique IDs; 190 passed same-condition V1 eligibility and 110 were explicitly excluded. The cumulative v4 panel now has 28 snapshots, 1,120 selected pairs, 996 quality-valid pairs, 513 distinct market IDs, and no positive top-ask state. The read-only economic-comparison v2 function accepted all 28 event files and returned complete candidate evidence with zero candidate rows; it did not write a finding or replace the next scheduled Arena run.

At 17:33 UTC the observer service had completed; its timer, the source-analysis timer, and the Research Director timer were active. The next scheduled runs were 18:00:31, 17:40:03, and 17:45:25 UTC respectively. The Director manifest still reflects its 17:15 admission of scan 27; Arena completed that job at 17:15:51. The next Director cycle is the reconciliation point. No manual poll, retry, or service restart was run. Gate D implementation and tests are recorded in [checkpoint 001](VERITAS_MISSION2_GATE_D_CHECKPOINT_001.md).

## 2026-10-15 17:59 UTC checkpoint — v3 replay ready

The 17:44:13 finalized-source summary processed 119 segments / 32 MiB in its
bounded batch. Cumulative progress is 2,780/3,962 replayable finalized
segments, with 1,182 segments / 327,830,232 bytes pending through ordinal
360,067. The source prefix remains incomplete and reports zero positive
top-ask and full-depth pre-fee states.

The 17:45:31 Director cycle reconciled scan 27 and admitted scan 28. Arena
completed the scan-pinned v2 qualification at 17:46:13 with all 28 events;
the persisted finding has zero positive states across all five gates. A
read-only v3 comparison of those same 28 events produced the same zero-positive
result and a complete empty replay, but did not write a finding. The next
observer, source-analysis, and Director timer runs were scheduled for
18:00:31, 18:10:37, and 18:15:12 UTC. All three timers were active and their
one-shot services idle at inspection. No service was restarted and no manual
run was launched.

See [Gate D checkpoint 002](VERITAS_MISSION2_GATE_D_CHECKPOINT_002.md) for
implementation, exact hashes, synthetic-path coverage, and verification.

## 2026-10-15 18:02 UTC observer scan 29

The scheduled observer completed scan 29 at 18:00:52 UTC with 40 selected
markets, 38 quality-valid pairs, seven public HTTP attempts, and zero positive
gross, full-depth, minimum, or fee states. The read-only v3 comparison now spans
29 snapshots / 1,160 selected pairs / 1,034 quality-valid pairs / 536 unique
markets. Its maximum top-pair edge remains -0.001 per share, with zero positive
states at every economic gate. The observer timer's next run is scheduled for
18:30:45 UTC. The 18:10:37 source-analysis and 18:15:12 Director runs remain
scheduled; the latter will reconcile scan 28 and can admit scan 29. No manual
run, retry, or service restart was used.

Scan 29 source and selection evidence is indexed in [Gate A checkpoint
026](VERITAS_MISSION2_GATE_A_CHECKPOINT_026.md) and the current machine-readable
[inventory 030](VERITAS_MISSION2_RESEARCH_INVENTORY_030.json).

## 2026-10-15 18:20 UTC source replay and Director recovery note

The 18:10 source-analysis service completed at 18:14:33 UTC with 127 finalized
segments / 33,535,604 bytes processed. Cumulative progress is 2,907/4,023
segments and 714,067,245 processed source bytes; 1,116 segments / 316,707,896
bytes remain. It used 11.65 CPU seconds and 160.1 MiB peak memory, below its
5% CPU and 256 MiB memory bounds, and did not open the active segment.

The 18:15:21 Director service exited successfully at the process level but
marked its manifest `UNVERIFIED`: it rejected the completed scan-28 v2 finding
because it predates the v3 replay object. It did not admit scan 29. The
completed job artifact remains unchanged; its manifest projection is stale and
shows `QUEUED`. Commit `9379985` fixes the version compatibility and adds
regression coverage. A read-only validation of the persisted v2 finding now
passes and labels replay unavailable for legacy v2. No manual reconciliation,
retry, or service restart was run.

At inspection, the observer, source-analysis, and Director timers were active;
their next runs were scheduled for 18:30:45, 18:40:08, and 18:45:20 UTC. The
source and Director one-shot services were inactive after completion. See [Gate
F checkpoint 016](VERITAS_MISSION2_GATE_F_CHECKPOINT_016.md) and [inventory
031](VERITAS_MISSION2_RESEARCH_INVENTORY_031.json).

A post-fix targeted regression completed at 18:22 UTC: 43 backend tests passed
across six affected Veritas/Arena modules. Strict Mypy, Ruff, formatting, and
the targeted Veritas browser flow passed. The failure and recovery chronology
remains in [Gate F checkpoint 016](VERITAS_MISSION2_GATE_F_CHECKPOINT_016.md);
the updated evidence is in [inventory
032](VERITAS_MISSION2_RESEARCH_INVENTORY_032.json).

The v4 paired measurement comparison was recomputed over the same 29 finalized
events: 240/1,160 passed the legacy age/skew rule and 1,034/1,160 passed the
request-to-receipt quality rule, a paired recovery of 794 (+68.45 percentage
points). This is a yield comparison only; sequence, atomicity, and upstream
queue age remain unverified. See the [current inventory
033](VERITAS_MISSION2_RESEARCH_INVENTORY_033.json).

## 2026-10-15 19:07 UTC — coverage pilot scan 1

The scheduled 19:00:44 observer run completed scan
`scan-20261015T190055Z-7799523b9d87` at 19:00:55 UTC, with 40 selected pairs,
32 quality-valid pairs, eight empty-ask invalid pairs, and seven public HTTP
attempts. It used the already scheduled discovery and books reads; the new
pilot added no network calls. The v4 panel advanced to 31 snapshots / 1,240
selected pairs / 1,102 quality-valid pairs / 138 invalid pairs / 575 distinct
selected market IDs. No positive top-gross state was found.

Pilot `VERITAS-M2-COVERAGE-PILOT-001` is running with one scan, 40 slots, 32
valid pairs, zero missed scan sequences, and its fixed end at 2026-10-16
19:00:55 UTC. The source/plan hashes and limitations are recorded in [Gate C
checkpoint 002](VERITAS_MISSION2_GATE_C_CHECKPOINT_002.md).

At this checkpoint the finalized-source analyzer remained at 3,019/4,081
segments with 1,062 segments / 312,431,120 bytes pending. Its next timer was
19:10:05 UTC. The Director's scan-30 qualification job had completed, while
the manifest still showed it queued; its next cycle was 19:15:13 UTC. The
observer's next timer was 19:30:19 UTC. There were no active Arena jobs and the
three Veritas one-shot services were inactive between timers. No manual poll,
retry, or service restart was run.

The Reality recorder and frozen shadow were active. The recorder log retained
a prior DNS resolution failure and degraded-state warning; the shadow service
had one automatic restart after an integrity/continuity mismatch and was
running at inspection. No protected campaign or recording was changed.
Available RAM was 8.9 GiB, swap use 3.5/4 GiB, disk use 56% with 199 GiB free,
and the Veritas observatory root was about 29.3 MB. Main Midas and Reality API
and web services were active. See [inventory 036](VERITAS_MISSION2_RESEARCH_INVENTORY_036.json).

## 2026-10-15 19:16 UTC — scheduled source and Director recurrences

The 19:10:05 source-analysis timer ran to completion at 19:14:38 UTC with
exit status 0 and zero restarts. It processed 113 finalized segments /
33,445,857 bytes; cumulative progress is 3,132/4,140 segments and
780,800,513 source bytes, with 1,008 segments / 298,406,538 bytes pending.
The source summary now reports 192,072 campaign-window frame records,
169,253 quality-valid states, 43 markets, and zero positive top-ask or
full-depth states. The batch used 13.619 CPU seconds, peaked at 146.7 MiB,
and used no swap. It reads finalized `.seg` inputs only.

The 19:15:13 Director timer completed normally at 19:15:50 UTC and admitted
scan `scan-20261015T190055Z-7799523b9d87`. Arena job
`job-c2b34af59d624f2ea3081b54` completed 31/31 with exit status 0 in 1.914
seconds. Finding `veritas-qualification-v1-b3744235647f846e` reports 1,102
quality-valid pairs across 575 markets, zero positives at all five gates, and
complete zero-candidate replay evidence. The job record is complete, while
the Director manifest still projects `QUEUED`; its next scheduled cycle is
19:45:26 UTC. No manual poll, retry, or restart occurred. See [Gate F
checkpoint 017](VERITAS_MISSION2_GATE_F_CHECKPOINT_017.md).

At 19:16 UTC the Veritas one-shot services were idle between timers; no Arena
job was running. The next timers were the observer at 19:30:19 UTC, source
analysis at 19:40:45 UTC, and Director at 19:45:26 UTC. Host load average was
1.52 on six CPUs, RAM available 8.9 GiB, swap used 3.5/4 GiB, disk 56% used
with 199 GiB free, and the observatory root was 29,467,543 bytes. The Reality
recorder and shadow remained active; their previously recorded DNS/degraded
warning and one shadow restart remain unresolved operational cautions. No
protected campaign state was changed. See [inventory 036](VERITAS_MISSION2_RESEARCH_INVENTORY_036.json).


## 2026-10-15 19:41 UTC — scan 32 and Gate G dashboard code checkpoint

The scheduled observer completed scan
`scan-20261015T193035Z-7597bbb981fa` at 19:30:35 UTC. Six bounded public
discovery pages returned 300 unique market IDs; 188 met same-condition V1
eligibility. Forty pairs were selected (37 rotating, three available stable
controls); 34 passed the request/receipt quality gate and six had an empty ask
side. The 112 explicit exclusions comprised 46 markets with unverified
augmented NegRisk semantics and 66 unsupported outcome relationships. All
gross, depth, minimum-notional, and fee gates remained zero-positive.

The cumulative v4 panel has 32 snapshots, 1,280 selected pairs, 1,136
quality-valid pairs, 144 invalid pairs, and 598 distinct selected IDs. The
legacy reported-age rule accepts 262 pairs versus 1,136 under request/receipt
completeness (+874, +68.28 percentage points). The maximum top-pair edge
remains -$0.001 per share. These are repeated selected observations, not
independent opportunities or venue-wide coverage.

The 24-hour pilot has completed two scans: 66/80 slots valid, 14 invalid, and
zero missed sequences. Rotating markets yielded 64/74 valid; available
controls yielded 2/6. This is descriptive and nonrandomized. The pilot adds
no requests and remains fixed through 2026-10-16 19:00:55 UTC.

At capture (19:41 UTC), the Reality recorder and frozen shadow were active.
The shadow has one historical automatic restart after a final-source integrity
or continuity mismatch; the recorder retains a prior temporary DNS/degraded
warning. The scheduled source-analysis run started at 19:40:47 UTC and was
still active at capture (PID 528516, 1.0 min elapsed, 3.2 CPU seconds, 171 MiB
RSS); its last completed summary remained at 3,132/4,140 segments (780,800,513
bytes processed; 298,406,538 pending). It is bounded to 128 segments and 32
MiB per run. The Director timer is next at 19:45:26 UTC; the observer timer is
next at 20:00:38 UTC. No Arena job was active.

Host load average was 0.87 / 1.39 / 1.45 across six CPUs, RAM available was
8.9 GiB of 15 GiB, swap used was 3.5/4 GiB, and disk use was 56% with 199 GiB
free. The observatory root measured 30,246,059 bytes. Main Midas and Reality
APIs and web services were active. Gate G checkpoint 005 is committed code on
`project/veritas` but was not deployed; no services, collectors, or campaigns
were restarted or modified for this checkpoint.

See [Gate G checkpoint 005](VERITAS_MISSION2_GATE_G_CHECKPOINT_005.md),
[research inventory 037](VERITAS_MISSION2_RESEARCH_INVENTORY_037.json), and
[the live pilot summary](../data/veritas-observatory/measurement-pilots/VERITAS-M2-COVERAGE-PILOT-001/summary.json).
