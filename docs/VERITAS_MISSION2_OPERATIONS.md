# Veritas Mission 2 Operations

**Runtime checked:** 2026-10-15 10:14 UTC
**Services:** `midas-veritas-observatory.service`, `midas-veritas-source-analysis.service`
**Timers:** `midas-veritas-observatory.timer`, `midas-veritas-source-analysis.timer`

## Current state

- Both Veritas user timers are active. The observer's 10:01 UTC run succeeded and the next event is 12:31 CEST. The source replay's 10:10 UTC run succeeded and its next event is 12:40 CEST. The oneshot services are inactive between runs as expected.
- Latest scan: `scan-20261015T100116Z-7d135306c470`, captured at 10:01:16 UTC and indexed by v4 at 10:01:21. The analyzer has 13 processed snapshots and no pending snapshots.
- Cumulative panel: 520 selected observations, 469 request/receipt-valid pairs, 51 empty-ask invalids, and 186 distinct market IDs. The previous reported-age/skew gate accepts 122/520. The paired increase is 347 observations (+66.73 percentage points).
- Across 334 sampled consecutive book-state comparisons, 319 fingerprints differ. The dashboard currently bands 53 markets higher, 17 lower, and 116 unclassified; these are intermittent comparisons, not venue update rates.
- The latest bounded discovery union contains 300 IDs: 132 supported same-condition V1 binary pairs and 168 explicit exclusions. The selected panel has 40 markets, 37 rotating and three available frozen controls; the other five frozen IDs were reported missing without replacement.
- Runtime data uses 11,257,293 bytes under `data/veritas-observatory/`, below the 1 GiB hard cap. Snapshots and derived runtime artifacts are ignored by Git; versioned docs record identities and hashes. Do not prune or raise the cap without a separate retention review.
- The v2 scan used seven HTTP attempts (six Gamma frames and one CLOB batch) out of a 14-attempt maximum. The scheduled service used 624 ms CPU and peaked at 28.4 MiB RAM. The frozen control file hash remains `9578217e20dcc7d1c65fa110f0ed7c689b55483b61191f1aae8d30c9b7300d9a`.
- The finalized Reality source analyzer remains `catching_up_finalized_source`: 944 of 3,077 replayable segments processed, 2,133 segments (571,624,064 bytes) pending through ordinal 108,963. The processed prefix has no campaign-window frames. The latest 10:10 UTC run processed 36 segments / 33,314,216 bytes in 179 seconds, using 8.962 CPU seconds, 149.7 MiB peak memory, and no swap. All 944 event hashes and the rolling chain were reverified against sealed state.
- The protected Reality user services `midas-reality.service`, `midas-reality-shadow.service`, and `midas-reality-api.service` were active during the read-only check. The separate Reality worktree is clean. No service was restarted or modified by Veritas.

The bounded Arena qualification `job-13280ea8cb2d427c938f0a3e` completed
13/13 finalized v4 events in about 2.11 seconds and persisted finding
`veritas-qualification-v1-f56acbc2267455d2`. It processed 237,821 source
bytes and found zero positive states at every gate. The checkout's isolated
`data/arena` root contains the job and finding; the job is completed, no jobs
are active, and the read-only activity projection reports zero invalid
artifacts. The repeat admission check returned the same job ID.

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
| Write access | Veritas observatory data root only |

The observer uses public Gamma GET discovery and unauthenticated public CLOB reads. It makes no orders and has no wallet, deposit, or authenticated trading path. Request/receipt timing does not prove response-batch atomicity, venue sequence, upstream queue age, or executable quote lifetime.

## Data lifecycle and versioning

The scanner writes exclusive, content-hashed compressed snapshots. `continuous_analysis.py` verifies finalized snapshot identities and immutable event digests, then atomically updates analyzer state and summary. It accepts at most 100 pending snapshots per run and rejects malformed, oversized, digest-mismatched, or unsafe inputs. v4 records paired legacy/current gate outcomes and per-market sample coverage. Snapshot fingerprint changes are sampled inter-scan changes, not true venue update rates.

The first v4 pass reindexed ten already finalized immutable snapshots. The 08:31, 09:00, and 10:01 UTC scheduled scans were captured and classified under v4 prospectively. The 13-snapshot economic qualification remains zero-positive; the latest Arena finding is linked in [Gate A checkpoint 011](VERITAS_MISSION2_GATE_A_CHECKPOINT_011.md). Protocol 002 documents the paired series; it does not alter a Reality campaign or waive the original follow-up design's gates. The latest source replay is recorded in [Gate A checkpoint 011](VERITAS_MISSION2_GATE_A_CHECKPOINT_011.md).

The independent Reality source analyzer validates the frozen campaign identity and reads only cataloged finalized `.seg` inputs. It never opens `.open` files. Per run it is limited to 128 segments or 32 MiB of new segment data; each segment is capped at 16 MiB. Catalog scans are bounded. Source state and events retain campaign/code/prefix digests and stop on identity drift. Resource bounds remain CPU 5%, memory 256 MiB, low priority, ten-minute timeout, and Veritas-only writes.

Arena's existing job worker now supports a pinned, bounded Veritas qualification task. The one-shot job reads finalized v4 events only and writes a deterministic finding under the existing Arena artifact model. Continuous collection and indexing remain on their bounded timers; Gate F still requires a controlled Director workflow and is open. The completed one-off qualification does not itself constitute that workflow.

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
systemctl --user list-timers midas-veritas-observatory.timer --no-pager
systemctl --user list-timers midas-veritas-source-analysis.timer --no-pager
systemctl --user status midas-veritas-observatory.service --no-pager
systemctl --user status midas-veritas-source-analysis.service --no-pager
journalctl --user -u midas-veritas-observatory.service -n 30 --no-pager
journalctl --user -u midas-veritas-source-analysis.service -n 30 --no-pager
du -sb /home/charlie/midas-veritas/data/veritas-observatory
```

Do not launch overlapping manual runs. If a manual run is needed, invoke its oneshot service and wait for completion before reading the relevant summary.

## Preservation

The separate `/home/charlie/midas-reality` checkout remains the protected source of the frozen campaign. Veritas analysis reads finalized source segments only and writes to its own observatory root. Do not restart or alter Reality services for this workflow. No Arena, Laboratory, Prometheus, or historical campaign records are rewritten. No real-money action is permitted.
