# Gate C checkpoint 007 — staggered 15-minute gap-detail cadence

**Captured:** 2026-10-16 01:36 UTC

**Branch:** `project/veritas`

**Mission status:** active; campaign-window gap attribution remains incomplete.

## Change

The bounded gap-detail timer previously ran at :20 and :50 UTC, twice hourly.
The declarative timer now runs at :05, :20, :35, and :50 UTC, every 15 minutes.
The added :05 and :35 slots are offset from the observer (:00/:30), source
analysis (:10/:40), and Research Director (:15/:45) starts. The gap analyzer's
existing limits remain 128 segments / 32 MiB per invocation, `CPUQuota=5%`,
`MemoryMax=256M`, `Nice=19`, and idle I/O scheduling. Its nonblocking output
lock remains in place.

The installed user timer was synchronized with
`deploy/systemd/user/midas-veritas-gap-detail-analysis.timer`. The user manager
was reloaded and only the timer unit was restarted to apply the schedule. The
gap-analysis service was not manually launched, interrupted, or restarted;
neither the Reality recorder/shadow nor any campaign was changed.

## First added scheduled batch

The timer fired at 01:35:00 UTC. Its one-shot completed at 01:36:13 UTC with
exit status 0, without restart or overlap. It processed 116 finalized segments
and 33,071,280 source bytes; the 32-MiB byte bound stopped the batch before its
128-segment limit. Systemd recorded 3.674 CPU seconds, 52.2 MiB peak memory,
and no memory swap peak. The service remained under the configured 5% CPU and
256-MiB memory limits. The active `.open` segment was not read.

| Measure | Before, 01:21 UTC | After, 01:36 UTC |
| --- | ---: | ---: |
| Cataloged finalized segments | 4,871 | 4,901 |
| Processed replayable segments | 1,072 | 1,188 |
| Processed source bytes | 224,233,275 | 257,304,555 |
| Pending segments | 3,797 | 3,711 |
| Pending source bytes | 1,037,173,118 | 1,011,014,530 |
| All-period gap events | 1,855 | 1,911 |
| Campaign-window gap events in processed prefix | 0 | 0 |

Pending source bytes fell by 26,158,588 across the interval despite new
finalized segments arriving. This is one observation after the schedule
change, not evidence of stable throughput or a completion-time forecast.

The processed prefix ends at ordinal 139,550, before the frozen campaign
window begins at 21:07:58 UTC on October 14. Therefore the empty campaign-window
gap count is still incomplete and is not evidence that the campaign had no
feed gaps. All 1,911 gap events remain all-period source diagnostics; they do
not establish quote age, outage duration, or complete recovery.

## Verification and next step

- `systemd-analyze calendar` normalized the four UTC slots to the expected
  15-minute cadence and predicted 01:35, 01:50, 02:05, and 02:20 UTC.
- `systemd-analyze verify` passed for the gap timer and unchanged service unit.
- `tests/test_veritas_gap_detail_analysis.py`: **3 passed**.
- The live one-shot exited successfully with no restart. The timer is active
  and next due at 01:50 UTC.
- No full regression suite or manual gap-analysis run was started.

Keep this cadence and existing per-run bounds for now. Recheck subsequent
scheduled batches for overlap, exit status, resource use, and net cursor
advance; keep the campaign-window gap count marked incomplete until the
finalized prefix actually crosses campaign start. See [inventory
054](VERITAS_MISSION2_RESEARCH_INVENTORY_054.json) and the [operations
checkpoint](VERITAS_MISSION2_OPERATIONS.md).
