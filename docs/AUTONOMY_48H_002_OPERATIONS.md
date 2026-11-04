# MIDAS 48H-002 Operations

48H-002 is a finite, read-only campaign over immutable Veritas snapshots and
Reality recording health. Its controller is a user-systemd oneshot service with a
persistent five-minute timer. User-manager linger supports recovery after logout.
The campaign writes only under `data/autonomy/48H-002/` and does not rewrite
48H-001 or Reality/Veritas source artifacts.

## Research and scheduling

The frozen baseline uses the newest 96 safe, immutable snapshots available at
launch, divided into three 32-scan slices. Each scan is independently replayed
for source integrity, stored versus recomputed pair validity and edge, reported
timestamp age/skew, and fee arithmetic. A malformed scan is quarantined on its
own; it does not invalidate the rest of its slice. Transient task failures use
bounded exponential backoff and become `BLOCKED` after five attempts so other
work can proceed.

New snapshots are discovered by scanning the immutable snapshot directory and
filtering by capture time, independently of the `latest-summary.json` high-water
mark. The prospective ledger is created at campaign start and records
`QUEUED`, `AUDITED`, and `QUARANTINED` events. The initial priority finishes the
frozen baseline; after adaptation, the scheduler alternates eligible baseline
and prospective work. It persists the selected item, reason, and queue sizes
for each admitted tick.

A strict-fresh gross-positive observation or a source/fee mismatch can redirect
the research priority. If strict freshness is below 20%, the controller may add
the preceding 32 scans. If no strict-fresh candidate appears within 12 hours,
the priority shifts to source quality and outcome/fill-label feasibility. No
synthetic training or Arena tournament is queued. These are research screens,
not profitability claims: selected snapshots are repeated observations and do
not contain realized fills or settlements.

## Admission and resource limits

Launch preflight remains strict. During runtime, high Reality recorder memory,
Reality source continuity, and Veritas feed freshness are recorded as warnings
for historical snapshot replay; those live-data conditions do not determine
whether already-saved immutable scans can be audited. Runtime still requires
protected services active, API readiness with live execution false, adequate
host memory and disk reserve, acceptable host pressure, a measured low-swap
interval, and no active conflicting Arena or Veritas research worker. Two
consecutive healthy runtime checks are required after a hard gate clears.

Each controller invocation is limited to 10% of one CPU, 512 MiB memory, no
swap, idle I/O, and a 15-minute wall limit. The 48-hour deadline stops new
research admissions. A 30-minute bounded grace window reconciles an admitted
one-shot before finalization. Unfinished or quarantined required work is
reported as partial.

## Status and recovery

```bash
cd /home/charlie/midas
./.venv/bin/python scripts/autonomy_48h_002.py status
systemctl --user status midas-autonomy-48h-002.timer
systemctl --user status midas-autonomy-48h-002.service
journalctl --user -u midas-autonomy-48h-002.service
```

`STATUS.md`, `manifest.json`, `research-plan.json`, and the prospective scan
ledger are updated as evidence arrives. Resource samples and scheduler decisions
are bounded rolling records; incident counts and per-task attempt/backoff state
remain in the manifest. Completed source audits and scan artifacts are immutable
and are never replaced during recovery. A final report distinguishes
unmeasured outcomes from measured zeroes.

Pause, resume, and cancel operate only on this campaign:

```bash
./.venv/bin/python scripts/autonomy_48h_002.py pause
./.venv/bin/python scripts/autonomy_48h_002.py resume
./.venv/bin/python scripts/autonomy_48h_002.py cancel
```

If the host is powered off or suspended long enough to miss the campaign window,
the controller marks the run partial rather than implying the missing
observations were collected. The campaign never starts, stops, or reconfigures
Reality, Veritas, API, Arena scheduler, paper-account, or live-trading services.
