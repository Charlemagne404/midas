# Veritas Mission 2 Operations

**Runtime checked:** 2026-10-15 10:46 UTC
**Services:** `midas-veritas-observatory.service`, `midas-veritas-source-analysis.service`, `midas-veritas-research-director.service`
**Timers:** `midas-veritas-observatory.timer`, `midas-veritas-source-analysis.timer`, `midas-veritas-research-director.timer`

## Current state

- All three Veritas user timers are active. The observer's 10:31 UTC run succeeded; its next event is 11:01 UTC. Source replay last succeeded at 10:40 UTC; its next run is about 11:10 UTC. The Director timer is active and continues at :15 and :45 UTC. The oneshot services are inactive between runs as expected.
- Latest scan: `scan-20261015T103110Z-b077f9c3d7be`, captured at 10:31:10 UTC and finalized under v4. The analyzer has 14 processed snapshots and no pending snapshots.
- Cumulative panel: 560 selected observations, 507 request/receipt-valid pairs, 53 invalid pairs, and 210 distinct market IDs. The previous reported-age/skew gate accepts 128/560. The paired increase is 379 observations (+67.68 percentage points).
- The latest bounded discovery union contains 300 IDs: 184 supported same-condition V1 binary pairs and 116 explicit exclusions. The selected panel has 40 markets, 36 rotating and four available frozen controls; unavailable frozen IDs were reported without outcome replacement.
- Runtime data uses 12,179,395 bytes under `data/veritas-observatory/`, below the 1 GiB hard cap. Snapshots and derived runtime artifacts are ignored by Git; versioned docs record identities and hashes. Do not prune or raise the cap without a separate retention review.
- The v2 scan used seven HTTP attempts (six Gamma frames and one CLOB batch) out of a 14-attempt maximum. Its observer service used 629 ms CPU and completed in 16 seconds. The frozen control file hash remains `9578217e20dcc7d1c65fa110f0ed7c689b55483b61191f1aae8d30c9b7300d9a`.
- The finalized Reality source analyzer remains `catching_up_finalized_source`: 1,072 of 3,136 replayable segments processed, 2,064 segments (557,814,406 bytes) pending through ordinal 122,759. The processed prefix has no campaign-window frames. The 10:40 UTC run processed 128 segments / 30,283,274 bytes in 155 seconds, using 7.737 CPU seconds, 132.1 MiB peak memory, and no swap. The current state and summary digests are recorded in [research inventory 013](VERITAS_MISSION2_RESEARCH_INVENTORY_013.json).
- The protected Reality user services `midas-reality.service`, `midas-reality-shadow.service`, and `midas-reality-api.service` were active during the read-only check. The separate Reality worktree is clean. No service was restarted or modified by Veritas.

The bounded Arena qualification `job-1bb0f47d56374e1385503362` completed
14/14 finalized v4 events and persisted finding
`veritas-qualification-v1-115a375a2bd16454`. It read 256,411 source bytes and
found zero positive states at each of five qualification gates. The checkout's
isolated `data/arena` root contains the Director manifest, append-only events,
job, and finding. No jobs are active, and the activity projection reports zero
invalid artifacts. A repeat Director poll reused the same job and finding.

At 11:30 CEST, an observer run failed with `Invalid frozen control cohort`
because the deployed scanner version rejected the file's legacy version tag.
The frozen eight-ID file remains unchanged with the SHA256 above; current code
accepts both the current and legacy tags. The 12:01 and 12:31 CEST scheduled
scans succeeded. No manual scan was run to recover.

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

The first v4 pass reindexed ten already finalized immutable snapshots. The 08:31, 09:00, 10:01, and 10:31 UTC scheduled scans were captured and classified under v4 prospectively. The 14-snapshot economic qualification remains zero-positive. Protocol 002 documents the paired series; it does not alter a Reality campaign or waive the original follow-up design's gates. The latest source-replay progress and sealed digests are recorded in [research inventory 013](VERITAS_MISSION2_RESEARCH_INVENTORY_013.json).

The independent Reality source analyzer validates the frozen campaign identity and reads only cataloged finalized `.seg` inputs. It never opens `.open` files. Per run it is limited to 128 segments or 32 MiB of new segment data; each segment is capped at 16 MiB. Catalog scans are bounded. Source state and events retain campaign/code/prefix digests and stop on identity drift. Resource bounds remain CPU 5%, memory 256 MiB, low priority, ten-minute timeout, and Veritas-only writes.

Arena's existing job worker supports a pinned, bounded Veritas qualification task. The recurring Director detects each new finalized v4 scan, checks readiness, admits one idempotent job, verifies the finding digest and source lineage, and reports an evidence-based recommendation. It does not coordinate source replay, start strategy/model experiments, or promote a model. See [Gate F checkpoint 001](VERITAS_MISSION2_GATE_F_CHECKPOINT_001.md).

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
