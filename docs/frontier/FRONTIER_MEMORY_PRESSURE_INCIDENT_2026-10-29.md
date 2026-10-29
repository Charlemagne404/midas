# MIDAS Host Memory Pressure Incident — 2026-10-29 Follow-up

| Field | Value |
| --- | --- |
| Host | Ubuntu, 16.67 GB RAM, 4.29 GB swap |
| Sample time | 2026-10-29 04:32 CET |
| Frontier worktree | `/home/charlie/midas-frontier` |
| Branch | `codex/frontier-20261026` |
| Preservation checkpoint | `ac4222f` (`feat(frontier): add held Gemini spot research adapter`) |

This is the current incident report. It supplements the chronological record in
[`FRONTIER_MEMORY_PRESSURE_INCIDENT_2026-10-28.md`](FRONTIER_MEMORY_PRESSURE_INCIDENT_2026-10-28.md).
The full-day journal query below expands that earlier report's final-ten-event
sample to all October 28 systemd-oomd kills.

## Executive finding

Two separate mechanisms caused process termination:

1. **systemd-oomd pressure kills:** On October 28 it killed 129 cgroups after
   the `user@1000.service` memory-pressure value exceeded its configured 50%
   threshold for more than 20 seconds with reclaim activity. The most frequent
   target was the five-minute Veritas gap-detail replay: 106 kills. The replay
   also showed high memory PSI in its own cgroup. It is the strongest
   identified recurring contributor, but the aggregate cgroup evidence does
   not prove it was the sole source of pressure.
2. **Kernel memcg OOM:** Seven Reality capacity-checker processes were killed
   against that service's local `MemoryMax=128M`; each reached about 129–131
   MiB anonymous RSS plus roughly 11 MiB file RSS. This was a separate leaf
   cgroup limit failure, not a host-wide kernel OOM.

The gap-detail timer is stopped and disabled. The capacity service now has a
reversible 160 MiB soft / 192 MiB hard limit with swap disabled, and its
04:16 scheduled run succeeded. Since the final systemd-oomd kill at 23:43:24
on October 28, no additional systemd-oomd kill has appeared through 04:32 on
October 29; no kernel OOM has appeared since the 20:15:44 capacity kill.

This is **partially contained, not resolved**. At 04:32 the host had 11.63 GB
available RAM and zero current host/user PSI, but only 1.94 MB of swap remained
free. `oomctl dump` currently lists no monitored cgroups despite the active
user-unit OOM policy and the historical kill records. The reason for this
current reporting mismatch is unresolved. Do not treat the quiet period as
proof of durable recovery.

## Full-day kill evidence

The journal contains 129 systemd-oomd kills between 00:28 and 23:43 CET on
October 28. Each kill record names user-manager memory pressure above 50% for
more than 20 seconds with reclaim activity.

| Target | Kills | Interpretation |
| --- | ---: | --- |
| `midas-veritas-gap-detail-v2.service` | 106 | Five-minute finalized-segment replay; strongest recurrent contributor |
| `midas-reality.service` | 10 | Critical recorder was killed and systemd restarted it |
| `midas-api.service` | 8 | API was killed and systemd restarted it |
| GNOME Terminal `vte-spawn` scopes | 4 | Interactive sessions were terminated |
| Firefox scope | 1 | Desktop process terminated |
| **Total** | **129** | All cited memory-pressure actions, not swap-limit actions |

At 23:38:28 the gap-detail cgroup had about 206.9 MiB current memory and
memory PSI of 75.70% avg10 / 73.20% avg60 / 51.25% avg300. At 23:43:24 it had
about 204.8 MiB and 76.50% avg10 / 50.59% avg60 memory PSI. It remained below
its 256 MiB `MemoryMax`; the logged reason was pressure in the parent
user-manager cgroup. The timer was stopped at 23:46:27 and is currently
`inactive` and `disabled`.

The kernel journal contains seven separate `CONSTRAINT_MEMCG` OOM records for
`midas-reality-capacity.service` from 17:15:21 through 20:15:44, spaced about
30 minutes apart. Every record identifies that service as `oom_memcg` and a
128 MiB hard cap. Later scheduled runs also succeeded while the old cap was in
place, so demand varied; the cap explains those seven kills but not every
successful or failed run. Source inspection previously found a plausible
high-memory archive-inventory fallback when provenance is invalid. The killed
runs did not retain inventory size or peak allocation, so that code path is a
hypothesis, not a proven cause. No archive manifest or historical evidence was
changed.

## Cgroup, pressure, and workload findings

The effective `user@1000.service` and its `user.slice` ancestors have no
`MemoryHigh`, `MemoryMax`, or `MemorySwapMax` ceiling. At 04:25, the user
manager charged about 9.02 GB memory, had a 13.99 GB recorded peak, and used
2.86 GB swap. Current counters were `high=16,417,339`, `max=730,045`,
`oom=19`, and `oom_kill=15`; these aggregate descendant counters are not
counts for one service. Current user-manager PSI was zero. Its current
`memory.stat` showed roughly 2.16 GB anonymous memory, 5.73 GB file memory,
and 1.10 GB kernel memory. The host had 11.64 GB `MemAvailable`, while
4,293,038,080 of 4,294,963,200 swap bytes were used.

The applicable policy is the vendor `user@.service` drop-in:
`ManagedOOMMemoryPressure=kill`, `ManagedOOMMemoryPressureLimit=50%`. `oomctl`
reports a 60% global default, a 20-second duration, and a 90% swap-used limit;
the per-user 50% override is what the incident logs show. The October 28 kill
records explicitly cite memory pressure, so the nearly full swap is an
important current risk but is not the recorded trigger for those kills. The
systemd documentation describes PSI-based monitoring and selecting eligible
descendant cgroups with reclaim activity; see the [systemd-oomd service
documentation](https://www.freedesktop.org/software/systemd/man/255/systemd-oomd.service.html),
[oomd configuration](https://www.freedesktop.org/software/systemd/man/255/oomd.conf.html),
and [resource-control settings](https://www.freedesktop.org/software/systemd/man/255/systemd.resource-control.html).

Current cgroup occupancy identifies contributors, not historic causes. At
04:25 the app slice used about 8.63 GB memory and 2.24 GB swap. The GNOME
Terminal slice used about 4.33 GB memory and 1.65 GB swap; one `vte-spawn`
scope accounted for about 1.77 GB. It contains several interactive Codex and
development processes. These scopes are left untouched because they include
active sessions and remote work. API and Reality were below their local soft
limits at the latest sample, but their observed peaks approached those limits:

| Service | State at 04:28 | Current / recorded peak | Effective limits | Restart count |
| --- | --- | ---: | --- | ---: |
| `midas-api.service` | active | 0.84 / 1.61 GB | High 1.50 GB, Max 1.75 GB, swap 0 | 9; last started 23:33:08 |
| `midas-reality.service` | active | 0.27 / 1.21 GB | High 1.125 GB, Max 1.25 GB, swap 0 | 14; last started 23:43:19 |

The API's memory-composition drop-in has an October 26 modification time;
the API base unit is from October 20. Reality's base unit is from October 21
and its live resource-control drop-ins are from October 20–21. The gap-detail
unit is from October 21 and its five-minute timer is from October 20. The
capacity service and its 30-minute timer are from October 21. These timestamps
show that the relevant schedules predated the October 28 kills; the API
drop-in was updated two days before them. They do not establish a causal
change. No service limit, OOM policy, or protected collector configuration
was changed during this follow-up.

Other scheduled work is staggered in the current schedule. In the sampled
04:00–04:17 period the observation pilot completed in about 12 seconds,
source analysis in 9 seconds, research director in 2 seconds, and capacity in
about 6 seconds; the minute Arena dispatcher completed immediately. No overlap
was observed in that interval. The old five-minute replay was the only
frequent heavy job implicated by the full-day kill pattern. This does not
prove that other workloads never overlap or contribute.

## Actions in effect and rollback

| Change | Reason and evidence | Current state | Rollback |
| --- | --- | --- | --- |
| Stop/disable `midas-veritas-gap-detail-v2.timer` | Auxiliary replay only; 106 of 129 October 28 OOMd kills targeted its service. It is not live capture or an integrity check. | `inactive`, `disabled`; service remains failed after its last OOMd kill. | After resource admission and an explicit decision to resume replay: `systemctl --user enable --now midas-veritas-gap-detail-v2.timer` |
| Bound Reality capacity monitor at High 160M / Max 192M / SwapMax 0 | Original 128M cap had seven kernel memcg kills. Latest scheduled run at 04:16:51 succeeded; the 00:46 run previously recorded a 137.4 MiB peak. This does not repair the possible unbounded archive scan. | Persistent drop-in `/home/charlie/.config/systemd/user/midas-reality-capacity.service.d/90-frontier-memory-bound.conf`; timer remains active at 30-minute intervals. | To restore the prior 128M hard cap, replace that file with `[Service]`, `MemoryMax=128M`, `MemorySwapMax=0`, then run `systemctl --user daemon-reload` and verify `systemctl --user show midas-reality-capacity.service -p MemoryHigh -p MemoryMax -p MemorySwapMax`. The existing runtime High setting is 128M. |
| Checkpoint Frontier worktree | Preserve current implementation before incident edits. | Local commit `ac4222f`; branch `codex/frontier-20261026`. Probe evidence directory remains untracked and untouched. | No rollback needed; normal Git history is the recovery point. |

The exact capacity rollback can be applied with:

```sh
cat > /home/charlie/.config/systemd/user/midas-reality-capacity.service.d/90-frontier-memory-bound.conf <<'EOF'
[Service]
MemoryMax=128M
MemorySwapMax=0
EOF
systemctl --user daemon-reload
systemctl --user show midas-reality-capacity.service -p MemoryHigh -p MemoryMax -p MemorySwapMax
```

The higher capacity bound is currently retained because it gives the checker
room for the measured 137.4 MiB peak. No process was manually started or
stopped by this follow-up. The gap-detail timer should remain disabled until
its replay memory behavior is bounded and the host admission gate is reviewed.

## Validation and service health

At 04:28 the host and user-manager memory PSI files reported zero avg10,
avg60, and avg300 pressure. `midas-api`, `midas-reality`, the Reality API and
web, the MIDAS web, the Arena scheduler, and the other bounded research timers
were active or waiting as expected. The Reality capacity timer was active; the
gap-detail timer was inactive. Continental tailnet and identity user units,
Echo archive and staging services, RustDesk, and systemd-oomd were active.
None was changed or restarted.

The Reality status file changes frequently. A 04:29:40 sample briefly read
`AWAITING_DATA` / `stale` with 0/16 fresh books. At 04:30:01 it reported
`RECORDING_UNSEQUENCED`, `active_receiving`, 16/16 fresh books, zero failures,
and no backpressure. `sequence_verified` remains false. This supports current
receiving at that timestamp, not sequenced completeness or archive integrity.
The capacity report's `INVALID_MANIFEST` and archive inventory/provenance
warnings remain a separate integrity issue. No archive data or manifest was
modified.

At 04:32 the Reality status file again reported `RECORDING_UNSEQUENCED`,
`active_receiving`, 16/16 fresh books, zero failures, and no backpressure; its
latest observation was only seconds old. The host still had zero PSI and
user-manager `oom=19` / `oom_kill=15` counters were unchanged. `systemd-oomd`
is active. Its current `oomctl dump` reports no monitored
cgroups and zero system-context memory/swap, even though `user@1000.service`
still reports the vendor `ManagedOOMMemoryPressure=kill` property and the
October 28 journal proves that monitoring acted then. This discrepancy needs
read-only follow-up; no global OOM policy was relaxed, disabled, or reloaded.
No OOMd kill has appeared since October 28 23:43:24, no kernel OOM since
20:15:44, and the API/Reality restart counts have remained 9/14. This is a
4-hour-49-minute quiet window after the last OOMd action, not endurance
validation.

At 04:36 the host still had zero PSI and 11.61 GB `MemAvailable`, but only
1.94 MB of swap remained free. The gap-detail timer remained inactive and
disabled; the capacity timer and API/Reality services were active. The
capacity service's most recent scheduled result remained successful at
04:16:51. Journal review still showed no OOM kill newer than 23:43:24 on
October 28. This adds four minutes to the bounded quiet observation only;
swap exhaustion risk and the OOMD registration discrepancy remain unresolved.

At 04:39 the host still had zero PSI and 11.62 GB `MemAvailable`; swap had
2.03 MB free. API and Reality remained active at restart counts 9 and 14,
respectively. The capacity monitor timer remained active and the gap-detail
timer remained disabled. No new OOM event was present since the prior sample.
Two small Frontier validation scopes (each limited to 256 MiB, zero swap, and
20% CPU) produced no visible PSI increase. Python syntax compilation and a
SQLite-only graph-counter smoke check passed. The actual pytest cases could
not run: host Python has neither pytest nor Pydantic installed. No packages
were installed. This was bounded development validation, not a host stability
or application integration test.

At 04:42, an existing virtual environment at
`/home/charlie/midas/.venv/bin/python` was found. The five focused graph
revision and schema-migration cases then passed **5/5 in 2.20 seconds** in a
scope capped at 384 MiB `MemoryHigh`, 512 MiB `MemoryMax`, zero swap, and 20%
CPU. An explicit `PYTHONPATH` check confirmed imports resolve to
`/home/charlie/midas-frontier/packages/midas/frontier/storage.py` at schema
version 8. The post-test sample still showed zero PSI, 11.52 GB
`MemAvailable`, 2.03 MB free swap, active API/Reality, and unchanged restart
counts 9/14. No OOM record appeared. The transient scope's peak was not
retained by systemd. These fixture tests verify the storage migration and
counter behavior; they do not verify the full suite, production storage, or
host endurance.

At 04:44, a fresh host and user-manager sample still showed zero PSI and no
new OOM record. `MemAvailable` was 11.60 GB, free swap 2.04 MB, and the user
manager charged 9.09 GB memory plus 2.86 GB swap with a 13.99 GB peak. Its
`memory.events` remained `oom=19`, `oom_kill=15`. API and Reality were active
at unchanged restart counts 9/14; the gap-detail timer was inactive and the
capacity timer active. `oomctl dump` still listed no monitored groups while
the user-manager 50% memory-pressure policy property remained present. The
current quiet interval does not resolve the swap or monitoring risks.

## Frontier continuation gate

Frontier is **safe to continue with serial code/documentation work and small,
targeted fixture checks under resource limits**. There is no active Frontier
test, build, replay, or source probe in the process list. The latest API is a
released non-Frontier build; Frontier is not deployed. The preceding bounded
frontend build completed without changing PSI or the OOM counters.

Do not resume broad suites, large replay batches, simultaneous analyses, or
public source probes while swap remains effectively full and current OOMD
monitor registration is unclear. Recheck PSI, free swap, API/Reality
headroom, timer state, and the current Reality status before any heavier
work. Preserve the unsequenced label and invalid archive provenance; do not
use them as a reason to modify the protected recorder or historical evidence.

**Incident status: PARTIALLY CONTAINED / PARTIALLY VERIFIED.** The identified
replay churn has been removed from the schedule and the capacity checker's
hard limit has safe headroom for its measured peak. Root-cause attribution
outside the replay workload, full-swap risk, current OOMD monitor visibility,
and long-duration host stability remain unresolved.
