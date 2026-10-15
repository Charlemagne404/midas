# Veritas Mission 2 Operations

**Runtime checked:** 2026-10-15 12:31 UTC
**Services:** `midas-veritas-observatory.service`, `midas-veritas-source-analysis.service`, `midas-veritas-research-director.service`
**Timers:** `midas-veritas-observatory.timer`, `midas-veritas-source-analysis.timer`, `midas-veritas-research-director.timer`

## Current state

- All three Veritas user timers are active. The 12:10 source-analysis recurrence and 12:15 Director cycle completed successfully, and a 12:16 no-launch reconciliation verified the Director result. The 12:31 observer scan then completed. The next observer, source-analysis, and Director runs are 13:00:57, 12:40:38, and 12:45:12 UTC. The oneshot services are inactive between runs as expected.
- Latest scan: `scan-20261015T123114Z-ded26b5ea023`, captured at 12:31:14 UTC and finalized under v4. The analyzer has 18 processed snapshots and no pending snapshots. The Director remains `CURRENT` for scan 17; scan 18 has not yet reached its 12:45 qualification cycle.
- Cumulative panel: 720 selected observations, 645 request/receipt-valid pairs, 75 invalid pairs, and 304 distinct market IDs. The previous reported-age/skew gate accepts 153/720. The paired increase is 492 observations (+68.33 percentage points).
- The latest bounded discovery union contains 293 unique IDs: 84 supported same-condition V1 binary pairs and 209 explicit exclusions (146 augmented NegRisk records and 63 unsupported outcome relationships). The selected panel has 40 markets, 37 rotating and three available frozen controls; unavailable frozen IDs were reported without outcome replacement.
- Runtime data uses 16,454,032 bytes under `data/veritas-observatory/`, below the 1 GiB hard cap. Snapshots and derived runtime artifacts are ignored by Git; versioned docs record identities and hashes. Do not prune or raise the cap without a separate retention review.
- The 12:31 v2 scan used seven HTTP attempts (six Gamma frames and one CLOB batch) out of a 14-attempt maximum. Thirty-two selected pairs passed the quality gate; eight had empty ask sides. The frozen control file hash remains `9578217e20dcc7d1c65fa110f0ed7c689b55483b61191f1aae8d30c9b7300d9a`.
- The finalized Reality source analyzer remains `catching_up_finalized_source`: 1,438 of 3,313 cataloged segments processed, 1,875 segments (504,775,332 bytes) pending through ordinal 166,686. The processed prefix has no campaign-window frames. The 12:10 UTC run processed 122 segments / 33,266,456 bytes in 159 seconds, using 7.970 CPU seconds and 136.4 MiB peak memory. Its sealed summary digest is `12ae77298aaca26f5b402ac9548983a6b34e4e0d7414d1d1a1b8ac858800bf0d`. See [research inventory 017](VERITAS_MISSION2_RESEARCH_INVENTORY_017.json).
- The protected Reality user services `midas-reality.service`, `midas-reality-shadow.service`, and `midas-reality-api.service` were active during the read-only check. The separate Reality worktree is clean. No service was restarted or modified by Veritas.

The latest bounded Arena qualification is `job-97c08fcee4f0407b88c06ca1`.
It completed all 17 finalized v4 events and persisted finding
`veritas-qualification-v1-4158e04dd04c8f4f` over 311,541 source bytes. It
found zero positive states at each of five qualification gates. The job's
source hash matched the committed revision. A 12:16 no-launch reconciliation
verified the finding and set the Director state to `CURRENT`; it admitted no
additional job. The earlier 11:15 UTC job for scan 110153 remains failed at
0/1 on source revision drift; it is preserved and was not retried. The live
activity projection reports zero active or queued jobs and zero invalid
artifacts. See [Gate F checkpoint
005](VERITAS_MISSION2_GATE_F_CHECKPOINT_005.md) and prior [checkpoint
004](VERITAS_MISSION2_GATE_F_CHECKPOINT_004.md).

At 11:30 CEST, an observer run failed with `Invalid frozen control cohort`
because the deployed scanner version rejected the file's legacy version tag.
The frozen eight-ID file remains unchanged with the SHA256 above; current code
accepts both the current and legacy tags. The 12:01 and 12:31 CEST scheduled
scans succeeded. No manual scan was run to recover.

## Research Director history projection

The `/api/arena/research-activity` projection now includes a digest-checked
history of each displayed Director's recent events. It scans at most 128
event files per Director, reads at most 64 KiB per event, and returns up to
eight records. The API verifies each event filename against the canonical
payload digest and confirms the Director identity before projecting selected
fields. It does not alter Director manifests or events. The live projection
returned eight verified entries from the Veritas Director's 19-file event
archive, marked the view truncated, and reported zero invalid artifacts. The
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
second seven-market OpenAI IPO group. The latter was enumerated by seven direct
Gamma market reads and checked against the adapter's on-chain question count;
the Gamma group filter returned 20 unrelated rows and no matching members. Its
single 14-token CLOB batch returned all books with depth at 5/20/100 shares,
but timestamps were up to 33.546 seconds old with 20.962 seconds of skew. No
positive qualified edge appears in either study; the OpenAI Yes set is flat
before fees at top of book, while its No set is negative. Both captures fail
freshness qualification. The sealed source and replay artifacts are under
`data/veritas-observatory/structure-studies/`; these studies are separate from
the recurring observer timer. See [Gate A checkpoint
015](VERITAS_MISSION2_GATE_A_CHECKPOINT_015.md).

The first v4 pass reindexed ten already finalized immutable snapshots. The 08:31, 09:00, 10:01, and 10:31 UTC scheduled scans were captured and classified under v4 prospectively. The latest completed 17-snapshot economic qualification remains zero-positive; the 12:31 scan has not yet reached its 12:45 Director cycle. Protocol 002 documents the paired series; it does not alter a Reality campaign or waive the original follow-up design's gates. The latest source-replay progress and sealed digests are recorded in [research inventory 018](VERITAS_MISSION2_RESEARCH_INVENTORY_018.json).

## Gate A checkpoint 015 — current evidence

The 12:31 UTC observer scan is finalized and indexed as snapshot 18. It has 32
quality-valid pairs, eight empty-ask invalid pairs, and no positive economic
states. Cumulative current/legacy freshness counts and all hashes are in
[research inventory 018](VERITAS_MISSION2_RESEARCH_INVENTORY_018.json).

The OpenAI IPO structure study is a separate fixed-group read. Its 14-book
capture has complete displayed depth at 5/20/100 shares but fails the 5-second
age and 250 ms skew rules. Use the replay runner or one bounded public refresh;
the study does not run on the recurring observer timer. See [Gate A checkpoint
015](VERITAS_MISSION2_GATE_A_CHECKPOINT_015.md).

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
