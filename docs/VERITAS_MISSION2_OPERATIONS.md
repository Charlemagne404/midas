# Veritas Mission 2 Operations

**Runtime checked:** 2026-10-15 13:18:58 UTC
**Services:** `midas-veritas-observatory.service`, `midas-veritas-source-analysis.service`, `midas-veritas-research-director.service`
**Timers:** `midas-veritas-observatory.timer`, `midas-veritas-source-analysis.timer`, `midas-veritas-research-director.timer`

## Current state

- All three Veritas user timers are active. The latest observer run completed at 13:01:20 UTC, the finalized-source replay completed at 13:13:51 UTC, and the Director cycle completed at 13:15:58 UTC. Their next scheduled UTC runs are 13:31:21, 13:40:19, and 13:45:16. The oneshot services are inactive between runs as expected.
- Latest scan: `scan-20261015T130114Z-f5e32eaf445c`, captured at 13:01:14 UTC and finalized under v4. The analyzer has 19 processed snapshots and no pending snapshots. The latest cumulative panel has 760 selected observations, 681 request/receipt-valid pairs, 79 invalid pairs, 326 distinct market IDs, and 160 pairs passing the prior reported-age/skew gate. The paired increase is 521/760 (+68.55 percentage points); all five economic gates remain zero-positive.
- The latest six-frame bounded discovery union contains 298 unique IDs: 138 supported same-condition V1 binary pairs and 160 explicit exclusions (93 augmented NegRisk records and 67 unsupported outcome relationships). The selected panel has 40 markets, 37 rotating and all three available frozen controls. Scan 19 overlaps scan 18 on seven IDs; 33 rotating selections changed. Its liquidity counts are 15 high / 13 medium / 12 low; expiry counts are 19 near / 14 medium / 7 long; spread counts are 18 tight / 16 medium / 6 wide.
- Runtime data uses 17,940,019 bytes under `data/veritas-observatory/`, below the 1 GiB hard cap. Snapshots and derived runtime artifacts are ignored by Git; versioned docs record identities and hashes. Do not prune or raise the cap without a separate retention review.
- The 13:01 v2 scan used seven HTTP attempts (six Gamma frames and one CLOB batch) out of a 14-attempt maximum. Thirty-six selected pairs passed the quality gate; four had empty ask sides (one Yes and three No). The frozen control file hash remains `9578217e20dcc7d1c65fa110f0ed7c689b55483b61191f1aae8d30c9b7300d9a`.
- The finalized Reality source analyzer remains `catching_up_finalized_source`: 1,676 of 3,432 cataloged finalized segments processed, with 1,756 segments / 470,661,304 bytes pending through ordinal 198,650. The 13:10 UTC recurrence processed 128 segments / 31,714,730 bytes in 187 seconds, using 9.34 CPU seconds and 141,037,568 bytes peak memory. Its partial prefix contains 15,469 campaign-window frame records, 11,367 touched market-frame states, and 11,000 quality-valid states, with zero positive top-ask and full-depth states. Summary digest: `03ace2c3d6761fdb92d6ed81df1e731ad3ed5cf3acda04d609b4b40f6fe27c4d`; summary file SHA256: `d5733cfdfd61e2fe702b79f6e4d894c9023761be7bd68168b3bb32725f6a8cb4`. **Correction:** the 12:43 summary's 4,078 `period_frame_records` were campaign-window frames, not zero. See [Gate A checkpoint 017](VERITAS_MISSION2_GATE_A_CHECKPOINT_017.md) and [inventory 020](VERITAS_MISSION2_RESEARCH_INVENTORY_020.json).
- The 13:15 Director cycle admitted `job-a7320b92c7f0453ea32b1b79` for scan 19. Arena completed all 19 events at 13:16:07 UTC; finding `veritas-qualification-v1-6e262fb7c4325c0c` reports zero positive states at all five gates. The job and finding are complete, while the Director manifest still says `QUEUED` and retains scan 18 as last qualified. Its next scheduled cycle at 13:45:16 UTC is the reconciliation point. No manual poll or retry was started. See [Gate F checkpoint 007](VERITAS_MISSION2_GATE_F_CHECKPOINT_007.md).
- The protected Reality user services were active during the last explicit read-only check. The separate Reality worktree was clean. No Reality service was restarted or modified, and no campaign data was changed.

## Research Director history projection

The `/api/arena/research-activity` projection now includes a digest-checked
history of each displayed Director's recent events. It scans at most 128
event files per Director, reads at most 64 KiB per event, and returns up to
eight records. The API verifies each event filename against the canonical
payload digest and confirms the Director identity before projecting selected
fields. It does not alter Director manifests or events. The last read-only projection check at 12:55 UTC returned eight verified
entries from the Director's then-19-file event archive, marked the view
truncated, and reported zero invalid artifacts. The
full append-only event directory remains the durable record; the UI and API
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

## Gate A checkpoint 017 — current evidence

The scheduled 13:01 UTC scan finalized as snapshot 19. The v4 panel contains
760 selected observations, 681 quality-valid pairs, 79 invalid pairs, 160
legacy age/skew-valid pairs, and 326 distinct markets. The paired yield
increase is 521/760 (68.55 percentage points). All five economic gates remain
zero-positive. Scan 19's bounded union has 298 unique records, 138 supported
pairs, and 160 explicit exclusions; its 40-market sample retained 37 rotating
markets and three available frozen controls.

The 13:13 finalized-source summary contains 15,469 campaign-window frame
records, 11,367 touched states, and 11,000 quality-valid states. The prefix
remains incomplete with 1,756 finalized segments / 470,661,304 bytes pending;
positive top-ask and full-depth counts remain zero. The earlier 12:43 summary
also contained 4,078 campaign-window frame records, 2,779 touched states, and
2,739 quality-valid states; checkpoint 016's interpretation of that counter as
zero frames was incorrect and is corrected in checkpoint 017.

The 13:15 Director admission completed all 19 events in Arena, but its
manifest still showed `QUEUED` and scan 18 as last qualified at this check.
The next Director cycle at 13:45:16 UTC is the scheduled reconciliation
point. See [Gate A checkpoint 017](VERITAS_MISSION2_GATE_A_CHECKPOINT_017.md),
[Gate F checkpoint 007](VERITAS_MISSION2_GATE_F_CHECKPOINT_007.md), and
[research inventory 020](VERITAS_MISSION2_RESEARCH_INVENTORY_020.json).

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
