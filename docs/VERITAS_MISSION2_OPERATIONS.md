# Veritas Mission 2 Operations

**Runtime checked:** 2026-10-15 09:02 UTC
**Services:** `midas-veritas-observatory.service`, `midas-veritas-source-analysis.service`
**Timers:** `midas-veritas-observatory.timer`, `midas-veritas-source-analysis.timer`

## Current state

- Both Veritas user timers are active. The observer's 09:00 UTC run succeeded; the next event is 09:30:26 UTC. The source replay's 08:40 UTC run succeeded; the next event is 09:10:54 UTC. The oneshot services are inactive between runs as expected.
- Latest scan: `scan-20261015T090047Z-6f98ffeaecab`, captured at 09:00:47 UTC and indexed by v4 at 09:00:52. The v4 analyzer has 12 processed snapshots and no pending snapshots.
- Cumulative panel: 480 selected observations, 431 request/receipt-valid pairs, 49 empty-ask invalids, and 161 distinct market IDs. The previous reported-age/skew gate accepts 107/480. The paired increase is 324 observations (+67.5 percentage points).
- The latest bounded discovery union contains 300 IDs: 167 supported same-condition V1 binary pairs and 133 explicit exclusions. The selected panel has 40 markets, 34 rotating and six available frozen controls.
- Runtime data uses 9,865,838 bytes under `data/veritas-observatory/`, below the 1 GiB hard cap. Snapshots and derived runtime artifacts are ignored by Git; versioned docs record identities and hashes. Do not prune or raise the cap without a separate retention review.
- The finalized Reality source analyzer remains `catching_up_finalized_source`: 658 of 2,899 replayable segments processed, 2,241 segments (610,777,450 bytes) pending through ordinal 39,776. Its processed prefix contains no campaign-window frames. The latest 08:40 UTC run processed 128 segments / 8,585,088 bytes in 87 seconds, using 4.347 CPU seconds.
- The protected Reality user services `midas-reality.service`, `midas-reality-shadow.service`, and `midas-reality-api.service` were active during the read-only check. The separate Reality worktree is clean. No service was restarted or modified by Veritas.

## Resource and network bounds

| Control | Configuration |
| --- | --- |
| Cohort size | 40 selected markets; service validates 30–50 |
| Stable controls | Target 8; unavailable frozen IDs are reported, not outcome-replaced |
| Discovery | Six Gamma query frames, at most 50 returned rows per frame |
| Book reads | One public CLOB `/books` batch for selected pair assets |
| Request pacing | One second between public requests; seven planned requests per scan |
| CPU | `CPUQuota=5%`, `Nice=19` |
| Memory | `MemoryMax=256M` |
| Storage | 1 GiB observatory root cap; scanner fails closed at projected bound |
| Runtime | 10-minute systemd start timeout |
| Privileges | `NoNewPrivileges=true`; no credentials or authenticated requests |
| Write access | Veritas observatory data root only |

The observer uses public Gamma GET discovery and unauthenticated public CLOB reads. It makes no orders and has no wallet, deposit, or authenticated trading path. Request/receipt timing does not prove response-batch atomicity, venue sequence, upstream queue age, or executable quote lifetime.

## Data lifecycle and versioning

The scanner writes exclusive, content-hashed compressed snapshots. `continuous_analysis.py` verifies finalized snapshot identities and immutable event digests, then atomically updates analyzer state and summary. It accepts at most 100 pending snapshots per run and rejects malformed, oversized, digest-mismatched, or unsafe inputs. v4 records paired legacy/current gate outcomes and per-market sample coverage. Snapshot fingerprint changes are sampled inter-scan changes, not true venue update rates.

The first v4 pass reindexed ten already finalized immutable snapshots. The 08:31 and 09:00 UTC scheduled scans were captured and classified under v4 prospectively. Protocol 002 documents the paired series; it does not alter a Reality campaign or waive the original follow-up design's gates. The 12-snapshot economic qualification run remains zero-positive; see [Gate A checkpoint 009](VERITAS_MISSION2_GATE_A_CHECKPOINT_009.md).

The independent Reality source analyzer validates the frozen campaign identity and reads only cataloged finalized `.seg` inputs. It never opens `.open` files. Per run it is limited to 128 segments or 32 MiB of new segment data; each segment is capped at 16 MiB. Catalog scans are bounded. Source state and events retain campaign/code/prefix digests and stop on identity drift. Resource bounds remain CPU 5%, memory 256 MiB, low priority, ten-minute timeout, and Veritas-only writes.

Arena's existing scheduler remains active for its supported typed job families. It has no Veritas finalized-source input type; routing every recurring scan through it would add source-copy/artifact handling and a second scheduler path beside the existing bounded timers. Current Veritas collection and analysis therefore remain direct oneshot timer jobs. Gate F still requires a controlled Director workflow and is open; the timers do not constitute that workflow.

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
