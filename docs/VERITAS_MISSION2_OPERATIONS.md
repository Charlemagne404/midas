# Veritas Mission 2 Operations

**Runtime checked:** 2026-10-15 06:32 UTC
**Service:** `midas-veritas-observatory.service`
**Timer:** `midas-veritas-observatory.timer`

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
- Runtime data uses 4,745,634 bytes under `data/veritas-observatory/`; the
  configured hard root limit is 1 GiB. Source snapshots are immutable and
  ignored by Git; docs and experiment artifacts record their paths and hashes.

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

## Inspection

These commands are read-only:

```bash
systemctl --user is-active midas-veritas-observatory.timer
systemctl --user list-timers midas-veritas-observatory.timer --no-pager
systemctl --user status midas-veritas-observatory.service --no-pager
journalctl --user -u midas-veritas-observatory.service -n 30 --no-pager
du -sb /home/charlie/midas-veritas/data/veritas-observatory
```

The periodic timer already owns normal recurrence. Do not launch overlapping
manual scans; if a manual scan is needed, use the oneshot service and wait for
its completion before evaluating the latest summary.

## Preservation audit

The separate `/home/charlie/midas-reality` checkout remained clean at commit
`714f824`. Reality API, recorder, shadow, and web services and their archive,
capacity, research, and integrity timers were still active. No Reality service
was restarted or written by this pilot. Three unrelated Reality test/canary
units reported exit-code results dated 2026-10-14, before this checkpoint:
`midas-reality-final-browser.service`,
`midas-reality-final-regression.service`, and
`midas-reality-shadow-canary.service`. They were left untouched.

No new CPU, memory, or network dependency was added to Arena or Reality. The
only installed recurrence is the bounded Veritas user timer.
