# Veritas Mission 2 Operations

**Runtime checked:** 2026-10-15 06:52 UTC
**Services:** `midas-veritas-observatory.service`, `midas-veritas-source-analysis.service`
**Timers:** `midas-veritas-observatory.timer`, `midas-veritas-source-analysis.timer`

## Current state

- The user timer is active and waiting. It is scheduled every 30 minutes in
  UTC, with up to two minutes randomized delay and persistent catch-up behavior.
- The latest scan (`scan-20261015T063103Z-12947c8cef0a`) completed successfully
  at 06:31:03 UTC. The oneshot exited successfully at 06:31:09 after about 16
  seconds and used 617 ms CPU time.
- The next scheduled timer event is 07:00:23 UTC.
- The service is inactive between runs, as expected for a oneshot. The timer
  is the active unit.
- The loaded unit files match the deploy definitions in this checkout.
- The analysis index has seven processed snapshots and zero pending snapshots.
- Runtime data uses 4,959,490 bytes under `data/veritas-observatory/`; the
  configured hard root limit is 1 GiB. Source snapshots are immutable and
  ignored by Git; docs and experiment artifacts record their paths and hashes.
- The finalized Reality source timer is active and offset from the snapshot
  timer. Its first batch processed 128 of 2,681 replayable segments, with 2,553
  remaining. The oneshot completed successfully in 72 seconds, used 3.63
  seconds CPU, and peaked at 110.6 MiB; the active Reality recorder remained
  untouched.
- Source-analysis readiness is `catching_up_finalized_source`. The first 128
  segments end at ordinal 7,048 and contain no campaign-window frames.

## Resource and network bounds

| Control | Configuration |
| --- | --- |
| Cohort size | 40 selected markets; service validates 30–50 |
| Stable controls | Target 8; unavailable frozen IDs are reported, not outcome-replaced |
| Discovery | Six Gamma query frames, at most 50 returned rows per frame |
| Book reads | One public CLOB `/books` batch for the selected pair assets |
| Request pacing | One second between public requests; seven planned requests per scan |
| CPU | `CPUQuota=5%`, `Nice=19` |
| Memory | `MemoryMax=256M`; measured peak not recorded |
| Storage | 1 GiB observatory root cap; scan fails closed when projected bounds are exceeded |
| Runtime | 10-minute systemd start timeout |
| Privileges | `NoNewPrivileges=true`; no credentials or authenticated requests |
| Write access | Only `data/veritas-observatory/` |

The scanner performs public Gamma GET discovery calls and an unauthenticated
public CLOB `/books` read. It has no order, wallet, deposit, or authenticated
trading path. A snapshot records request and receipt times but cannot prove a
batch is atomic or reveal upstream queue age.

## Data lifecycle

1. Discovery and selected books are saved to a content-hashed compressed
   snapshot using exclusive naming.
2. `continuous_analysis.py` verifies the finalized snapshot identity and
   indexes it once into `analysis-events/v2/`.
3. Analysis events are immutable. Cumulative state and `research-summary.json`
   are replaced atomically after each successful indexing pass.
4. The analysis run accepts at most 100 pending snapshots. It refuses unsafe
   symlinks, malformed evidence, digest mismatches, oversized data, and an
   over-bound state. A failed run does not convert partial data into a valid
   candidate.
5. No automatic deletion or pruning is configured. The 1 GiB cap is the stop
   boundary; review retention before changing that cap.

The v1 analyzer artifacts and original Veritas/Reality records remain
preserved. Version 2 keeps its own state and events and recomputes the evidence
summary from finalized snapshots once each.

## Finalized Reality source analysis

The independent `midas-veritas-source-analysis.service` reads the frozen
campaign at the pinned path, verifies campaign ID
`adf91d042ab8f91678834b9258bfde70022a763dfda8c91d1e94be334583aa46` and
campaign file SHA256
`aa8acb2b46823c1a1e3ac5d01a57dde917746c2c7471098ae2a4598875e322f5`, then
scans numeric catalog sidecars and their finalized `.seg` records. It never
opens `.open` files. Empty finalized headers are validated and excluded from
the replay cursor so a later no-record catalog cannot reorder source progress.

Each run is limited to 128 replayable segments or 32 MiB of new segment data;
each segment is capped at 16 MiB. Catalog metadata scans are capped at 32 MiB
and 100,000 entries. State is capped at 24 MiB and the source event/state store
at 256 MiB. Systemd applies 5% CPU, 256 MiB memory, idle IO, low scheduling
priority, a 10-minute timeout, no new privileges, read-only home access, and
write access only to the Veritas observatory data directory. The timer is
scheduled at minutes 10 and 40 UTC, offset from the snapshot timer.

The source analyzer writes `source-analysis-events/v1/`,
`source-analysis-state-v1.json`, and `source-research-summary.json`. The event
is written exclusively before atomic cursor/state replacement. The state pins
the campaign hash, analysis code file hashes, processed ordinal, and a rolling
digest of the processed catalog prefix. A changed prefix or code identity stops
the run. It does not hash old `.seg` payloads every invocation; each new
segment is hash-checked and record/catalog-checked when consumed.

## Inspection

These commands are read-only:

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

The two timers own normal recurrence. Do not launch overlapping manual runs;
if a manual run is needed, use its oneshot service and wait for completion
before evaluating the corresponding summary.

## Preservation audit

The separate `/home/charlie/midas-reality` checkout remained clean at commit
`714f824`. Reality API, recorder, shadow, and web services and their archive,
capacity, research, and integrity timers were still active. No Reality service
was restarted or written by this pilot. Three unrelated Reality test/canary
units reported exit-code results dated 2026-10-14, before this checkpoint:
`midas-reality-final-browser.service`,
`midas-reality-final-regression.service`, and
`midas-reality-shadow-canary.service`. They were left untouched.

No new CPU, memory, or network dependency was added to Arena or Reality. Both
installed recurrences are bounded Veritas user timers.
