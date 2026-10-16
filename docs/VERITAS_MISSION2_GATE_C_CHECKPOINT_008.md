# Gate C checkpoint 008 — second staggered gap-detail batch

**Captured:** 2026-10-16 01:51 UTC

**Mission status:** active; the indexed prefix still has not reached campaign time.

## Scheduled cadence and bounds

The gap-detail timer remains at :05, :20, :35, and :50 UTC (every 15
minutes). Its service contract is unchanged: at most 128 finalized segments or
32 MiB per run, a nonblocking output lock, 5% CPU quota, 256-MiB memory cap,
nice 19, idle I/O, and a 10-minute start timeout. The two runs since the
change were staggered away from the observer, source-analysis, and Director
start slots.

| Scheduled start (UTC) | Segments / source bytes | Elapsed | CPU | Peak memory | Exit |
| --- | ---: | ---: | ---: | ---: | ---: |
| 01:35 | 116 / 33,071,280 | 73 sec | 3.674 sec | 52.2 MiB | 0 |
| 01:50 | 128 / 27,931,474 | 71 sec | 3.542 sec | 56.1 MiB | 0 |

Both invocations were timer-started, did not overlap, and had zero service
restarts or memory swap peaks. Neither read the active `.open` segment.

## Prefix progress

| Measure | At 01:21 UTC | At 01:51 UTC |
| --- | ---: | ---: |
| Cataloged finalized segments | 4,871 | 4,931 |
| Processed replayable segments | 1,072 | 1,316 |
| Processed source bytes | 224,233,275 | 285,236,029 |
| Pending segments | 3,797 | 3,613 |
| Pending source bytes | 1,037,173,118 | 990,355,252 |
| All-period gap events | 1,855 | 1,973 |
| Campaign-window gap events in processed prefix | 0 | 0 |

Pending bytes fell by 46,817,866 across this 30-minute interval while 60 new
cataloged segments arrived. The measured change is encouraging but is only one
half-hour interval and is not a catch-up forecast; input sizes vary and new
segments continue to arrive.

The analyzer remains `catching_up` at ordinal 151,428. Its indexed source is
still before the frozen campaign window, which starts at 21:07:58 UTC on
October 14. The zero campaign-window gap count remains incomplete. The 1,973
all-period records are receiver-time source diagnostics and do not prove quote
age, outage duration, or complete book recovery.

## Verification and next action

- Both scheduled one-shots exited successfully; the service is inactive after
  success and the timer remains active, next due at 02:05 UTC.
- The installed timer matches the committed unit. Its calendar and unit
  definition validation passed; the focused gap-detail suite passed **3 tests**.
- No manual gap run, service retry, recorder/shadow restart, collector change,
  pilot change, or campaign modification occurred.

Keep the 15-minute schedule and current batch limits while the next scheduled
runs continue. Continue marking campaign-window gap attribution incomplete
until finalized records from the campaign window are indexed. See [checkpoint
007](VERITAS_MISSION2_GATE_C_CHECKPOINT_007.md), [inventory
054](VERITAS_MISSION2_RESEARCH_INVENTORY_054.json), and the [operations
checkpoint](VERITAS_MISSION2_OPERATIONS.md).
