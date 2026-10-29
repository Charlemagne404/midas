# MIDAS Host Memory Pressure Incident — 2026-10-29 Follow-up

| Field | Value |
| --- | --- |
| Host | Ubuntu, 16.67 GB RAM, 4.29 GB swap |
| Initial sample | 2026-10-29 04:58 CET |
| Latest addendum | 2026-10-29 15:14 CET |
| Frontier worktree | `/home/charlie/midas-frontier` |
| Branch | `codex/frontier-20261026` |
| Pre-incident checkpoint | `checkpoint/frontier-pre-memory-incident-20261029` (`a8fbcd7`) |
| Incident continuation checkpoint | `checkpoint/frontier-pre-followup-20261029-0558` (`0bbb62e`) |

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
04:16 and 04:46 scheduled runs succeeded. Since the final systemd-oomd kill
at 23:43:24 on October 28, no additional systemd-oomd kill has appeared
through 04:58 on October 29; no kernel OOM has appeared since the 20:15:44
capacity kill.

This is **partially contained, not resolved**. At 04:58 the host had 10.80
GiB available RAM, zero current host/user PSI, and about 2 MiB free swap.
`oomctl dump` still lists no monitored cgroups despite the active user-unit
OOM policy and historical kill records. The reason for this current reporting
mismatch is unresolved. Do not treat the quiet period as proof of durable
recovery.

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

The normal capacity timer fired at 04:46:58 and the service completed at
04:47:04 with `Result=success`, exit status 0, 6.257 CPU seconds, and zero
swap peak. systemd reported a 3.2 MiB memory peak, much lower than the prior
137.4 MiB sample; treat the new peak as non-comparable and do not infer that
the inventory path is bounded from it. The report still contains
`INVALID_MANIFEST`, inventory, and provenance alerts; no archive state was
changed. At 04:47 the host had zero PSI and 11.59 GB `MemAvailable`; user
manager `oom=19`/`oom_kill=15` remained unchanged at 04:46. API and Reality
remained active at restart counts 9/14, the gap-detail timer remained
disabled, and no new OOM journal entry appeared. This is one scheduled run,
not endurance validation.

The schema-2, schema-4, and schema-5 storage migration cases passed **3/3** in
a 512 MiB, zero-swap, 20%-CPU scope. The API multihop stale-cursor case
passed **1/1** under the same cap after an appended relationship. Together
with the earlier focused five-case graph/storage run, this verifies eight
storage/migration cases and one API cursor case on fixtures. The API test
emitted the existing Starlette/httpx deprecation warning.

At 04:49, host and user-manager PSI remained zero, `MemAvailable` was 11.53
GB, and free swap was 2.04 MB. User-manager `oom=19` and `oom_kill=15` were
unchanged. API and Reality were active at restart counts 9/14, the gap-detail
timer inactive, and the capacity timer active. No new OOM journal entry
appeared. The most recent `oomctl dump` still listed no monitored groups.
The quiet interval since the last OOMd kill is about five hours and six
minutes; nearly full swap and monitor visibility remain unresolved.

## Bounded economics regression and current host sample — 2026-10-29 04:51 CET

Four fixture-only cross-venue economics modules (FX sensitivity, capital
carry, Kalshi fee sensitivity, and logical-implication economics) passed
**79/79 in 4.79 seconds**. They ran against the Frontier worktree with a
512 MiB maximum, zero swap, and 20% CPU quota. They provide no live-source,
execution, or profitability evidence. Immediately after the run, PSI was
zero, `MemAvailable` was 11.59 GB, free swap was 2.04 MB, user-manager
`oom=19`/`oom_kill=15` were unchanged, API and Reality were active at restarts
9/14, and no new OOM record appeared.

At 04:51:44, `MemAvailable` was 10.82 GiB and free swap about 2 MiB. Host and
user-manager PSI remained zero; the user manager held 9.10 GB memory and
2.86 GB swap, with `oom=19` and `oom_kill=15`. API was active at 814.5 MiB
current memory (1.5 GiB high, 1.7 GiB max); Reality was active at 270.7 MiB
(1.1 GiB high, 1.2 GiB max), with restart counts still 9/14. The gap-detail
timer was inactive and the capacity timer waiting. `oomctl dump` listed no
monitored cgroups. A read-only kernel/systemd-oomd journal query since 04:45
found no OOM record. The observation window is short; swap is still nearly
full and OOMD monitor registration remains unresolved.

## OOMD candidate and workload attribution follow-up — 2026-10-29 04:56 CET

A read-only review of the October 28 23:43 OOMD candidate logs distinguishes
the trigger from the selected victims. At 23:43:09 the parent
`user@1000.service` pressure was 61.64%, exceeding its configured 50% limit.
OOMD selected Reality at 550.7 MiB current memory (that candidate's 10/60-second
PSI values were zero). Fifteen seconds later the parent pressure was 54.45%;
the gap-detail process was 204.8 MiB and recorded 76.50% 10-second / 50.59%
60-second local PSI with 426 pages scanned in the most recent sample. The API
was 1.4 GiB with near-zero local PSI; a Terminal child scope was 457 MiB with
near-zero PSI. The evidence confirms that gap-detail was locally under
reclaim stress and that it was selected during elevated aggregate user
pressure. It does not establish it as the sole source of host pressure, and
the first Reality kill is not itself evidence of high local PSI.

At 04:54:36, systemd-oomd was active, had been running since October 15, and
had zero restarts. The user manager still reported
`ManagedOOMMemoryPressure=kill` with a 50% override. A fresh 04:56 `oomctl`
sample continued to list no monitored groups. The 04:56 host and user-manager
PSI values were zero, `MemAvailable` was 10.803 GiB, and `SwapFree` was
0.002 GiB. The registration discrepancy remains unresolved; no daemon reload
or restart was attempted.

The 04:54 cgroup inventory put `app-org.gnome.Terminal.slice` at 4.06 GiB
current memory and 1.54 GiB swap, the largest user application slice. Its
accounting included 2.69 GiB file cache; the largest child scope held 1.68
GiB, including 1.16 GiB file and 0.50 GiB anonymous memory. API and Reality
were active at 0.80/0.27 GiB current memory. The Frontier process search found
no tests, builds, replay jobs, or source probes. The Terminal slice is the
largest current user workload, but this does not attribute the October 28
events to it. No terminal, service, or protected collector was interrupted.

At 04:57:10, `MemAvailable` was 10.799 GiB and `SwapFree` 0.002 GiB. Host
and user-manager PSI remained zero; user-manager `memory.events` stayed at
`oom=19`/`oom_kill=15`. API and Reality remained active at restart counts
9/14, the gap-detail timer inactive, and the capacity timer active. No OOM
entry appeared in the checked kernel/systemd-oomd journal interval since
04:45. The observation remains short relative to the prior repeated-kill
pattern, and the swap/monitoring issues remain open.

## Bounded joint-state regression and post-test host check — 2026-10-29 04:58 CET

The focused `tests/frontier/test_joint_state.py` module passed **14/14 in
4.28 seconds** in a transient scope capped at `MemoryHigh=384M`,
`MemoryMax=512M`, `MemorySwapMax=0`, and `CPUQuota=20%`. It used deterministic
fixtures, pinned imports to the Frontier worktree, disabled pytest cache
writes, and placed its temporary files under `/dev/shm`. It did not access
external sources, production databases, or historical research stores.

Before the run, host and user-manager PSI were zero, `MemAvailable` was
10.828 GiB, and 0.002 GiB swap was free. At 04:58:45, PSI remained zero,
`MemAvailable` was 10.802 GiB, swap free remained 0.002 GiB, and user-manager
`memory.events` remained at `oom=19`/`oom_kill=15`. No OOM entry appeared in
the checked kernel/systemd-oomd journal interval from 04:58:25 to 04:58:58.
API and Reality remained active at restarts 9/14; the gap-detail timer remained
inactive and the capacity timer active. This bounded test provides no
endurance evidence.

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

## Bounded verification follow-up — 2026-10-29 05:04 CET

Three focused fixture suites passed under separate transient user scopes,
each with `MemoryHigh=384M`, `MemoryMax=512M`, `MemorySwapMax=0`, and
`CPUQuota=20%`:

- `tests/frontier/test_joint_state.py`: **14/14** in 4.28 seconds.
- `tests/frontier/test_logical_implication.py` and
  `tests/frontier/test_relationship_reviews.py`: **27/27** in 10.89 seconds.
- `tests/frontier/test_transport.py`: **20/20** in 4.08 seconds.

Selected strict mypy checks passed for four economics modules and four
adapter modules. Ruff check and format passed on twelve files. The only code
change was a one-line formatter correction in `adapters/transport.py`,
committed as `ef4e77d`; no service configuration was changed in this follow-up.
One existing Starlette/httpx TestClient deprecation warning remains.

At 05:04:25 CET, host and user-manager PSI were zero, `MemAvailable` was
10.802 GiB, `SwapFree` was 0.002 GiB, and user-manager `memory.events`
remained `oom=19`/`oom_kill=15`. API and Reality remained active at restart
counts 9/14; the gap-detail timer remained inactive and the capacity timer
active. `oomctl dump` still listed no monitored groups, and no OOM entry was
found in the checked journal interval since 05:03. This is a brief post-check
sample only. It does not resolve swap exhaustion, current OOMD monitor
visibility, root-cause attribution beyond the demonstrated replay-local
pressure, or endurance stability. Keep broad suites, public probes, and large
replays deferred.

At 05:06 CET, a separate read-only status check showed `MemAvailable` 10.79
GiB, `SwapFree` 0.002 GiB, zero host/user-manager PSI, and unchanged
user-manager `memory.events` (`high=16417339`, `max=730045`, `oom=19`,
`oom_kill=15`). API/Reality were active at about 0.80/0.27 GiB current
cgroup memory, with restart counts 9/14. The gap-detail timer was inactive
and the capacity timer active. No OOM entry was returned by the preceding
ten-minute systemd-oomd journal query. `oomctl dump` continued to list no
monitored groups. This remains a short quiet interval, not proof of stability.

## Readiness telemetry improvement — 2026-10-29 05:10 CET

The read-only Research Readiness resource API now includes `swap_total_bytes`
and `swap_free_bytes` from the same bounded `/proc/meminfo` read used for RAM.
The UI shows free/total swap and utilization only when the data is valid;
missing or malformed values stay unmeasured. Swap occupancy is displayed as
context and does not independently change Arena admission, which continues to
use available memory, pressure, cgroup headroom, and active job evidence.

The API resource tests passed **5/5**, and the focused Readiness UI tests
passed **3/3**. Ruff check/format, ESLint, Prettier, and strict mypy for the
readiness resource module passed. A bounded live resource snapshot confirmed
the new fields are populated from `/proc/meminfo`: total/free swap was
4,294,963,200 / 2,080,768 bytes at 05:10 CET. This is telemetry evidence,
not a stability conclusion. At the post-test host check, PSI remained zero,
available RAM was 11,543,302,144 bytes, free swap was 2,088,960 bytes,
`oom=19`/`oom_kill=15` were unchanged, and API/Reality remained active.
`oomctl` monitor visibility and nearly full swap remain unresolved. No
service configuration or protected data changed.

## Host and service follow-up — 2026-10-29 05:19 CET

This read-only update refreshed the 04:58 assessment. Host memory was
16,274,968 kB total and 11,326,216 kB available (about 10.80 GiB). Host and
user-manager PSI `some` and `full` averages were all zero at the sample.
Swap remained effectively full: 4,194,300 kB total with only 2,052 kB free.
The zero PSI and high available memory indicate no current reclaim stall; the
nearly full swap and past events remain operational risks.

The `user@1000.service` cgroup charged 9,199,026,176 bytes (about 8.57 GiB),
had a recorded peak of 13,992,292,352 bytes (about 13.03 GiB), and used
2,864,476,160 bytes (about 2.67 GiB) of swap. Its ancestors and the user
manager still have no memory or swap ceilings. Its counters remained at
`high=16,417,339`, `max=730,045`, `oom=19`, and `oom_kill=15`. Current
`memory.stat` charged about 5.47 GiB to file cache, 2.04 GiB to anonymous
memory, and 1.03 GiB to kernel memory, including about 0.95 GiB reclaimable
slab. Visible `charlie` process RSS summed to about 4.1 GiB across 157
processes. This confirms that process RSS alone does not explain the current
cgroup charge. The Terminal application slice was the largest sampled user
application slice at 4,389,888,000 bytes current memory and 1,647,280,128
bytes swap; it contains active interactive/development sessions, which were
left untouched. These are current charges, not historic attribution.

`midas-api.service` and `midas-reality.service` were active with restart
counts 9 and 14. Their current cgroup charges were about 0.81 GiB and 0.28
GiB; recorded peaks remained about 1.50 GiB and 1.13 GiB. The API and Reality
live service configurations were not changed. The Reality status file was
updated at 05:19:11 CET and reported `RECORDING_UNSEQUENCED`,
`active_receiving`, 16/16 fresh books, zero failures, and no backpressure;
`sequence_verified` remained false. This confirms current receiving only,
not sequence completeness or archive integrity.

The five-minute gap-detail timer remained `inactive` and `disabled`; its
service remained failed from the previous OOMD kill. The Reality capacity
timer remained active at its existing 30-minute schedule. Its last scheduled
run completed successfully at 05:17:07 with the existing 160 MiB
`MemoryHigh`, 192 MiB `MemoryMax`, and zero swap limit. The reported peak for
this run was only about 4.8 MiB, which is inconsistent with prior retained
peaks and is not used as evidence that the scanner's peak is bounded. Its
report still contained `ARCHIVE_SEGMENT_INVENTORY_INVALID` and
`ARCHIVE_MANIFEST_PROVENANCE_INVALID`; neither was repaired or modified.

`systemd-oomd` remained active, but `oomctl --no-pager` still listed no
monitored cgroups, despite the vendor `user@.service` policy
`ManagedOOMMemoryPressure=kill` at 50%. No OOMD kill appeared after
2026-10-28 23:43:24 CET, and no kernel OOM appeared after the 20:15:44 CET
capacity-checker kill. This is a quiet interval of about 5 hours 36 minutes
for OOMD and 9 hours for the capacity checker, not an endurance result.

No service configuration was changed in this follow-up and no Frontier test,
build, replay, batch job, or source probe was launched. The pre-existing
containment remains in place: the gap-detail timer is stopped/disabled and
the capacity checker has its reversible 160/192 MiB bound. The gap timer can
be restored after an explicit resource-admission review with
`systemctl --user enable --now midas-veritas-gap-detail-v2.timer`; the
capacity bound rollback procedure is recorded above.

**Continuation decision:** the latest sample supports serial, source-independent
code and documentation work, plus only small, separately capped fixture
checks after another admission sample. It does not support broad test suites,
large replays, concurrent research, or live source probes while swap is full
and OOMD monitor visibility remains unresolved. Incident status remains
**PARTIALLY CONTAINED / PARTIALLY VERIFIED**.

## Admission review and bounded regression — 2026-10-29 05:22 CET

The existing Arena host gate was reviewed without code changes. It admits one
worker at a time and checks active job IDs, at least 2 GiB of `MemAvailable`
plus the requested worker budget, disk reserve, CPU load, host and user-manager
memory PSI, and I/O PSI. It fails closed when required pressure readings are
missing. Its thresholds are `some > 10%` or `full > 1%` for host/user memory
PSI and `some > 20%` for I/O PSI. The scheduled-job gate applies the same
host/user PSI and single-active-job constraints. Frontier replay, timeline,
and discovery requests are bounded to a 512 MiB memory limit, 50% CPU quota,
five minutes maximum wall time, and idle I/O priority. Full swap alone does
not force rejection when `MemAvailable` and PSI remain healthy; swap is
retained as context, not misrepresented as current pressure.

Three existing cgroup admission regressions passed (**3/3 in 7.09 seconds**):
user-manager PSI path resolution, denial under user-manager pressure, and
fail-closed behavior when the user pressure reading is unavailable. They ran
serially in a transient scope with `MemoryHigh=384M`, `MemoryMax=512M`,
`MemorySwapMax=0`, and `CPUQuota=20%`; no new tests were added. Before the
run, at 05:22:15, `MemAvailable` was 11,318,100 kB, `SwapFree` was 2,216 kB,
and host memory PSI was zero. At 05:22:35 after the run, `MemAvailable` was
11,291,496 kB, `SwapFree` remained 2,216 kB, and host memory PSI remained
zero. User-manager `memory.events` stayed at `oom=19`/`oom_kill=15`. API and
Reality remained active at restart counts 9/14; the capacity timer remained
active/waiting and the gap-detail timer inactive. No OOM journal event
appeared in the checked interval after 05:22.

This targeted check supports the existing admission implementation and
serial, bounded continuation only. It does not validate the complete scheduler
or host endurance, and it does not resolve full swap, the OOMD monitor-listing
mismatch, uncertain historic workload attribution, or the invalid archive
provenance/inventory evidence.

## Critical service check — 2026-10-29 05:24 CET

After the bounded admission test, Caddy, Continental's tailnet proxy and
identity backend, Echo production and staging, Headscale, Tailscale, RustDesk,
the MIDAS API, MIDAS web, Reality recorder, and the Reality API/web services
were active. `ssh.socket` remained active; `ssh.service` was inactive under
socket activation. No service was stopped, restarted, or reconfigured during
this check. The current service snapshot supports continued infrastructure
availability; it is not a recovery or endurance certification.

## Frontier bounded work and post-run host check — 2026-10-29 05:40 CET

The isolated Frontier branch added a finite Polymarket public market-stream
decoder/capture path. It is disabled by default, makes no request in the
fixture tests, and does not apply unsequenced price changes to a local book.
The `tests/frontier/test_polymarket_stream.py` and existing
`tests/frontier/test_adapters.py` suites passed **179/179 in 8.80 seconds**
under `MemoryHigh=384M`, `MemoryMax=512M`, `MemorySwapMax=0`, and
`CPUQuota=20%`; peak RSS was 66,992 KiB, swaps were zero, and the test emitted
no socket messages. Strict mypy passed for the changed models, adapter,
decoder, and storage modules (**134,492 KiB peak RSS**) under a 768 MiB hard
limit, zero swap, and 20% CPU quota. Ruff and `git diff --check` passed. No
service or persistent system configuration changed.

At 05:40 CET, `MemAvailable` was 11,290,932 kB and `SwapFree` 2,568 kB of
4,194,300 kB. Host memory PSI remained zero. User-manager OOM counters were
unchanged at `oom=19`/`oom_kill=15`. The latest service snapshot, at 05:38:27,
showed MIDAS API/web and Reality recorder/API/web active with API/recorder
restart counts still 9/14; the capacity timer active/waiting and the
gap-detail timer inactive/dead. No systemd-oomd or kernel OOM appeared in the
checked journal interval from 05:20 through 05:38:27 CET.

This short follow-up confirms that the bounded fixture work did not add
measurable swap use or advance OOM counters. It does not resolve near-full
host swap, the user-manager pressure-monitor visibility mismatch, historic
workload attribution, or the separate invalid archive manifest/provenance
warnings. Frontier may continue only with serial, source-independent edits and
small capped fixture checks after a fresh resource sample. Broad regressions,
large replay, live stream probes, and new collectors remain deferred. Incident
status remains **PARTIALLY CONTAINED / PARTIALLY VERIFIED**.

## Polymarket adapter checkpoint and current host sample — 2026-10-29 05:42 CET

The Frontier branch committed a finite, disabled-by-default Polymarket public
market-stream capture as `0e02c93`. The capture validates and retains full-book,
price-change, best-bid/ask, and tick-size events as source evidence. It does not
apply deltas or produce a `BookSnapshot` because the documented feed does not
specify sequence continuity or gap recovery. It has no API/UI route or
persistent worker and was not connected to a live source. No service or
persistent system configuration changed.

The adapter, stream, and transport fixture slice passed **199/199 in 11.11
seconds** under `MemoryHigh=384M`, `MemoryMax=512M`, `MemorySwapMax=0`, and
`CPUQuota=20%`; peak RSS was 66,968 KiB, swap use was zero, and no socket
traffic was emitted. Strict mypy passed for five changed source files in 0.80
seconds with a 53,180 KiB peak RSS under a 768 MiB hard cap, zero swap, and
20% CPU. Ruff and whitespace checks passed.

At 05:41 CET the host had 11,287,011,328 bytes available RAM (10.51 GiB) and
2,641,920 bytes free swap (2.52 MiB of 4.00 GiB); host memory PSI averages were
zero. User-manager `memory.events` remained `oom=19` and `oom_kill=15`. At
05:42 the API and Reality recorder were active at restart counts 9 and 14;
MIDAS web, Reality API/web, Caddy, Echo production/staging, Continental
tailnet/identity, Tailscale, RustDesk, Headscale, and `ssh.socket` were active.
The Reality capacity timer was active/waiting. The gap-detail timer remained
inactive; its service remained failed with its prior `oom-kill` result. No
service was restarted or changed.

`oomctl dump` now lists `user@1000.service` under the 50% pressure policy with
zero current pressure averages and about 8.6 GiB current memory. Earlier
follow-up samples listed no monitored cgroups; the reason for that difference
is still unknown. Kernel and OOMD journal queries found no new entries from
05:38 through 05:42. This is a brief quiet interval only. Near-full swap and
historic attribution limits remain, and the invalid Reality archive inventory
and provenance alerts remain separate and untouched. Continue only serial,
source-independent work and small capped fixture checks after a fresh sample;
do not run broad suites, replay, collectors, or live probes. Status remains
**PARTIALLY CONTAINED / PARTIALLY VERIFIED**.

At the same service sample, API memory was 881,721,344 bytes current and
1,611,026,432 bytes peak, against `MemoryHigh=1,610,612,736`,
`MemoryMax=1,879,048,192`, and `MemorySwapMax=0`. Reality was 310,964,224 bytes
current and 1,208,467,456 bytes peak, against `MemoryHigh=1,207,959,552`,
`MemoryMax=1,342,177,280`, and `MemorySwapMax=0`. Both current charges were
below their high thresholds; the recorded peaks were slightly above
`MemoryHigh` but below each hard maximum. These cgroup peaks are scoped service
measurements, not host-wide workload attribution.

## Readiness resource telemetry and post-test sample — 2026-10-29 05:51 CET

The isolated Frontier branch committed `4595e46`, adding a read-only
`user-manager` cgroup record to the existing Research Readiness resource API and
dashboard. It exposes current memory charge, hierarchical memory PSI, and
cumulative `memory.events` counters for high/max, OOM, process kills, and group
kills. Missing counters remain null and display as not measured. The view does
not alter scheduling or admission decisions, and its cgroup event counters do
not replace kernel or systemd-oomd journal evidence for kill attribution.

The bounded API resource test passed **7/7 in 0.89 seconds**, with 43,852 KiB
peak RSS. The focused dashboard file passed **3/3 in 14.01 seconds**, using a
256 MiB Node heap. Both used 384 MiB `MemoryHigh`, 512 MiB `MemoryMax`, zero
swap, and 20% CPU quota. Strict mypy, Ruff, ESLint, Prettier, and whitespace
checks passed. The single-file UI run did not build the full TypeScript project.
The tests were fixture-only and caused no socket traffic.

A live bounded call to the resource sampler at about 05:49 took 0.09 seconds
and peaked at 12,888 KiB RSS. It measured user-manager charge of 9,317,834,752
bytes, zero memory PSI, and cumulative `oom=19`, `oom_kill=15`, and
`oom_group_kill=0`. In that one sample, user-manager CPU PSI some avg10 was
8.87% and full avg10 was 8.38%; no workload attribution is established. At
05:51 host memory available was 11,573,329,920 bytes (10.78 GiB), free swap was
2,695,168 bytes (2.57 MiB), and host memory PSI remained zero. OOM counters
remained unchanged. `oomctl` listed the user-manager at its 50% policy with
zero current pressure averages. Kernel and OOMD journal queries found no
entries since 05:42.

At 05:51 the API and Reality recorder remained active with restart counts 9/14;
MIDAS and Reality web/API, Echo production/staging, Continental tailnet/auth,
Caddy, Headscale, Tailscale, RustDesk, and `ssh.socket` remained available.
The capacity timer was active/waiting; the gap-detail timer remained inactive
and its failed service retained the earlier OOM result. Nothing was restarted,
reconfigured, or deployed. The host remains only partially contained because
swap is nearly full and the observation window is short. Keep only serial,
source-independent edits and capped fixtures within the admission limits.

## Effective ancestor limits and latest admission check — 2026-10-29 05:54 CET

`user@1000.service` has `MemoryHigh=infinity`, `MemoryMax=infinity`, and
`MemorySwapMax=infinity`. Its `user-1000.slice` and `user.slice` ancestors also
have no memory or swap caps. `ManagedOOMMemoryPressure=kill` is active with the
50% pressure threshold; `oomctl` reports a 20-second duration. At 05:53:40 the
manager cgroup had 9,338,646,528 bytes current memory and a 13,992,292,352-byte
lifetime peak. The OOMD policy watches aggregate user-manager pressure, but the
historical evidence still does not identify every contributing child workload.

At 05:53:40, API current/peak memory was 888,283,136 / 1,611,026,432 bytes
(`MemoryHigh=1,610,612,736`, `MemoryMax=1,879,048,192`, swap max zero). Reality
was 336,347,136 / 1,208,467,456 bytes (`MemoryHigh=1,207,959,552`,
`MemoryMax=1,342,177,280`, swap max zero). Their current charges were below
`MemoryHigh`; lifetime peaks were slightly above `MemoryHigh` and below their
hard maxima.

At 05:54, `MemAvailable` was 11,545,051,136 bytes (10.76 GiB), free swap was
2,756,608 bytes (2.63 MiB), and host and user-manager memory PSI averages were
zero. User-manager memory events remained `oom=19`, `oom_kill=15`, and
`oom_group_kill=0`. `oomctl` continued to show the user-manager monitored at
50% with zero pressure averages. No kernel or OOMD journal entry appeared
after 05:42. API, Reality, their web/API services, Echo production/staging,
Continental tailnet/auth, Caddy, Headscale, Tailscale, RustDesk, and
`ssh.socket` were active at the 05:51 service check. The capacity timer was
waiting; the gap-detail timer remained inactive and disabled, and its service
retained the earlier OOM failure. No service, timer, or limit changed.

The user-manager monitor is visible again in current `oomctl` samples, but the
earlier empty listings remain unexplained. Swap remains almost fully occupied,
and this quiet interval is brief. Frontier can continue with serial,
source-independent edits and small capped fixture tests after fresh admission
checks; broad tests, replays, live probes, collectors, and production changes
remain deferred. Incident status remains **PARTIALLY CONTAINED / PARTIALLY
VERIFIED**.

## Follow-up admission and service validation — 2026-10-29 05:58 CET

A fresh sample at 05:58:38 showed 11,565,940,736 bytes (10.77 GiB) of
`MemAvailable` and 2,764,800 bytes (2.64 MiB) of free swap out of
4,294,963,200 bytes. Host and user-manager memory PSI averages remained zero.
The user-manager cgroup charged 9,356,570,624 bytes of memory and
2,864,013,312 bytes of swap; its cumulative `oom=19`, `oom_kill=15`, and
`oom_group_kill=0` counters had not changed. Its app slice charged
8,957,480,960 bytes of memory and 2,236,010,496 bytes of swap. Current app
slice memory statistics included 5,897,342,976 bytes of file cache, of which
4,607,369,216 bytes were inactive, 1,973,886,976 bytes anonymous, and
1,067,966,464 bytes kernel memory. These are current composition measurements,
not retrospective attribution for the October 28 pressure episodes.

`oomctl dump` again showed the active 50% / 20-second user-manager memory
pressure monitor, with zero current pressure. systemd-oomd remained active.
No systemd-oomd or kernel OOM kill appeared after the prior query at 05:54;
the historical last kills remain 23:43:24 October 28 for systemd-oomd and
20:15:44 for the capacity checker's kernel memcg OOM. The earlier empty
`oomctl` listings remain unexplained.

The API and Reality collector remained active at unchanged restart counts 9
and 14. Their cgroup current charges were 891,047,936 and 343,289,856 bytes,
respectively; both remained below their 1,610,612,736 / 1,207,959,552-byte
soft limits. The main API and Reality API health endpoints both returned
HTTP 200 with `READY`. MIDAS/Reality web services, Caddy, Echo production and
staging, Continental tailnet and identity, Headscale, RustDesk, and
`ssh.socket` were active under their respective system or user managers. No
service was restarted or reconfigured.

The gap-detail timer remains inactive and disabled. The capacity timer remains
active/waiting; its 05:47:04–05:47:10 run succeeded with exit status 0 under
effective `MemoryHigh=160M`, `MemoryMax=192M`, and `MemorySwapMax=0`. Its
report still carries `ARCHIVE_SEGMENT_INVENTORY_INVALID` and
`ARCHIVE_MANIFEST_PROVENANCE_INVALID`; those integrity warnings are separate
and untouched. No persistent service setting changed during this follow-up.

**Continuation decision:** current RAM availability, zero memory PSI, stable
critical service health, and unchanged kill counters support resuming Frontier
only in serial, source-independent slices with small capped fixture checks.
The nearly exhausted swap, historical aggregate attribution gap, and short
post-containment observation period do not support broad suites, large replay,
concurrent research, live probes, or deployment. This is safe-to-continue
within those bounds, not a resolution of the host incident. Status remains
**PARTIALLY CONTAINED / PARTIALLY VERIFIED**.

## Post-validation host sample — 2026-10-29 06:11 CET

After the bounded Frontier API, UI, mypy, and TypeScript checks, the 05:11:26
UTC host sample showed 11,522,015,232 bytes (10.73 GiB) `MemAvailable` and
7,892,992 bytes (7.52 MiB) free swap. Host and user-manager memory PSI
averages remained zero. User-manager `memory.events` remained
`oom=19`/`oom_kill=15`/`oom_group_kill=0`; the active `oomctl` monitor still
showed the 50% threshold with zero current pressure. No kernel or systemd-oomd
kill appeared since the 06:09 query. The repeated 13-test stream/API fixture
slice passed after recording the saved-market observation ID inside each
normalized frame; its 512 MiB zero-swap scope did not advance OOM counters.

The MIDAS API and Reality recorder remained active with unchanged restart
counts 9 and 14 and current cgroup charges of 897,986,560 and 349,614,080
bytes, below their respective soft thresholds. Both local API health endpoints
returned HTTP 200 and `READY` at 06:09, and the units remained active at 06:11.
The capacity timer remained active and its last run remained successful under
the 160/192 MiB, zero-swap bound. The
gap-detail timer remained disabled. No service, protected collector, or
persistent system configuration was restarted or changed.

This sample supports the bounded test choices; it does not explain the nearly
full swap, prove long-term stability, or resolve historic child-workload
attribution. The host remains **PARTIALLY CONTAINED / PARTIALLY VERIFIED**.

## Post-UI-validation host sample — 2026-10-29 06:15 CET

The focused Frontier UI test initially timed out at its 15-second test limit
under the 20% CPU quota after 15.79 seconds; it reported a timeout, not an
assertion failure. One retry with a 25-second test limit passed **1/1**, with
eight unrelated tests skipped, in 15.90 seconds of test time (31.61 seconds
total runner time). Its `systemd-run --user --scope` remained bounded at
`MemoryHigh=512 MiB`, `MemoryMax=768 MiB`, `MemorySwapMax=0`, and `CPUQuota=20%`;
a concurrent sample observed about 318 MiB charged and zero swap. Host PSI
remained zero during the run.

At 05:14:45 UTC, `MemAvailable` was 11,122,409,472 bytes (about 10.36 GiB),
free swap was 7,892,992 bytes (7.52 MiB), and host memory PSI averages were
zero. User-manager events remained `oom=19`, `oom_kill=15`, and
`oom_group_kill=0`; `oomctl` still showed the 50% pressure monitor with zero
current pressure. Kernel and systemd-oomd journal queries had no kill entries
since 05:11 UTC. MIDAS API and Reality remained active at restart counts 9 and
14. Their current charges were 899,960,832 and 347,783,168 bytes. The
capacity service remains configured at 160/192 MiB with zero swap, and its
last result remains successful. The gap-detail timer remains inactive and
disabled. The API, Reality interfaces, Caddy, and SSH socket were active in
the post-test unit check. The finite Arena dispatcher completed three
one-minute invocations with no schedules and 35 ms CPU in the latest run; no
long-running research job was active in the sampled user units.

No service, timer, or persistent system setting was changed during this
validation. Nearly all swap remains occupied, the user-manager hierarchy is
uncapped, historical attribution is incomplete, and the observation window is
short. Incident status remains **PARTIALLY CONTAINED / PARTIALLY VERIFIED**;
continue only serial, source-independent work and capped fixture checks after
a fresh admission sample.

## Final short-window recheck — 2026-10-29 06:17 CET

At 05:17:02 UTC, after the bounded UI test, `MemAvailable` was
11,387,441,152 bytes (about 10.61 GiB), `SwapFree` was 7,921,664 bytes
(7.55 MiB), and host memory PSI averages remained zero. User-manager event
counters remained `oom=19`, `oom_kill=15`, and `oom_group_kill=0`. The actual
registered `/api/health` endpoints for the MIDAS API (port 8000) and Reality
API (port 8010) both returned `status=READY`; each reported
`live_execution=false`. Both services and the capacity timer remained active;
the gap-detail timer remained inactive. Kernel and systemd-oomd journal
queries contained no kill entries from 05:11:26 through 05:17 UTC.

This is a short quiet interval, not evidence of durable recovery. Swap remains
almost entirely occupied, historical attribution is incomplete, and the
archive inventory/provenance warnings are unchanged.

## Admission-check implementation sample — 2026-10-29 06:27 CET

At 05:27:21 UTC, `MemAvailable` was 11,116,363,776 bytes (10.36 GiB) and
`SwapFree` was 7,946,240 bytes (7.58 MiB). Host memory PSI averages were zero.
The user-manager cgroup charged 9,474,899,968 bytes of memory and
2,858,856,448 bytes of swap; event counters remained `oom=19`,
`oom_kill=15`, and `oom_group_kill=0`. Kernel and systemd-oomd journals had no
kill entries in the preceding 45-minute query.

The MIDAS API and Reality collector remained active with unchanged restart
counts 9 and 14. Their current cgroup charges were 907,067,392 and 352,432,128
bytes, respectively, below their 1,610,612,736-byte and 1,207,959,552-byte
soft limits. The capacity timer remained active; its service was inactive
after its last successful run at the 160/192 MiB, zero-swap bound. The
gap-detail timer remained disabled and its service retained the previous
OOM-kill result. No service, timer, persistent limit, or protected artifact
was changed for the Frontier source-admission implementation.

The implementation's fixture tests ran in zero-swap resource scopes; during
them host PSI remained zero and user-manager OOM counters remained unchanged.
This observation does not resolve the nearly full swap or historic workload
attribution. Incident status remains **PARTIALLY CONTAINED / PARTIALLY
VERIFIED**.

## Post-verification health sample — 2026-10-29 06:37 CET

The user-facing overload feedback change is committed as 401994f. A fixture test returned the bounded-source-operation 429 and verified that Exchange Explorer reports the venue and retry interval. This was a UI/client change only; no service settings, timers, processes, or protected evidence were changed. Prettier, ESLint, full web tsc --noEmit, the focused Exchange Explorer test, and git diff --check passed. The test and type check ran in bounded systemd scopes with swap disabled; the type check used 640/768 MiB memory-high/max, a 384 MiB Node heap, and 25% CPU.

At 05:37:08 UTC, host MemAvailable was 11,463,749,632 bytes (10.68 GiB), SwapFree was 7,979,008 bytes (7.61 MiB), and host memory PSI averages were zero. User-manager memory/swap charges were 9,485,979,648 / 2,858,835,968 bytes. Its cumulative memory events remained oom=19, oom_kill=15, oom_group_kill=0. Kernel and systemd-oomd journal queries had no matching OOM or kill entries since 05:34 UTC. MIDAS API and Reality health endpoints returned READY, with live_execution=false; systemd restart counts remained 9 and 14 in the adjacent 05:34 service sample. The capacity timer was waiting. The gap-detail timer remained inactive and its service retained its prior oom-kill result.

The sample shows no new kill during this brief bounded-work window, but swap remains nearly full and the user-manager hierarchy remains uncapped. Historic system-wide attribution and durable recovery are not established. Incident status remains **PARTIALLY CONTAINED / PARTIALLY VERIFIED**. Serial, bounded, source-independent Frontier work may continue after fresh admission checks; do not infer readiness for broad test suites, live probes, deployment, or concurrent research.

## Graph-context verification and pressure resample — 2026-10-29 07:03 CET

The bounded graph-context fixture/API checks passed **3/3** and the selected
relationship graph UI fixture passed **1/1**. A strict mypy run was then
started for the new graph projection and the full Frontier API inside a
`MemoryMax=768 MiB`, `MemoryHigh=640 MiB`, `MemorySwapMax=0`, `CPUQuota=20%`
scope. At about 2m20s, its Python process had reached 719,512 KiB RSS and was
in uninterruptible I/O; I terminated that task process. It had reported one
type-inference error, which was corrected. A new-module-only strict mypy run
later passed under a 512 MiB hard, 384 MiB high, zero-swap, 20% CPU scope; the
full API type check was not retried. Exact-tree TypeScript, ESLint, and
Prettier checks passed. An isolated Vite production build completed in 54.88
seconds under a 768 MiB hard, 640 MiB high, zero-swap, 25% CPU scope. This is
a resource-bound development check, not a production process or deployment.

During the run, a host sample showed memory PSI briefly elevated to
`some avg10=18.80%` / `full avg10=17.87%`. At 07:02:42 CET it had fallen to
`some avg10/avg60/avg300=3.11/8.15/2.64%` and
`full=2.95/7.74/2.51%`. Available memory was 11,497,480,192 bytes (10.71
GiB), swap free 8,388,608 bytes (8 MiB), user-manager memory 9,553,338,368
bytes, and user-manager swap 2,858,516,480 bytes. Cumulative memory events
remained `oom=19`, `oom_kill=15`, and `oom_group_kill=0`; hierarchical `high`
was 16,420,097 and `max` 730,045. The user-manager OOMD pressure average was
4.73% over 60 seconds against its 50%/20-second limit. Kernel and OOMD journal
queries for the last 20 minutes had no kill entries. This temporal association
does not establish that the type-check caused all observed PSI or explain the
historic kills.

The gap-detail timer was already inactive and remains so; its service retains
the prior failed status 9 with `MemoryHigh=192 MiB`, `MemoryMax=256 MiB`, and
zero swap. It was not stopped or modified in this checkpoint. Arena's
one-minute dispatcher, the 30-minute Veritas Observatory timer, and the
30-minute Reality capacity timer remained scheduled; their latest observed
finite invocations exited 0. MIDAS API and Reality units remained active. No
service, timer, limit, recorder, archive, or existing research evidence was
changed. Avoid further build/type-check/replay work until fresh PSI readings
and a sustained observation window show that the host can admit it safely.

After those bounded checks, the 07:09:34 CET sample showed
`MemAvailable=11,340,759,040` bytes (10.56 GiB), `SwapFree=8,429,568` bytes
(8.04 MiB), host memory PSI `avg10/avg60=0` and `avg300=0.61/0.58%` for
some/full, user-manager memory/swap `9,580,249,088 / 2,858,450,944` bytes,
and unchanged OOM counters 19/15/0. API and Reality remained active at
restarts 9/14. The last ten-minute kernel/OOMD query had no kill entry. The
interval is short; nearly all swap remains used and no sustained recovery has
been demonstrated.

Incident status remains **PARTIALLY CONTAINED / PARTIALLY VERIFIED**. The
historical pressure contributor is still not identified; this check adds a
bounded development workload as a plausible pressure contributor, not a
historical root cause.

## Focused recovery-window checks — 2026-10-29 07:11 CET

After host PSI returned to zero over its 10- and 60-second windows, the
new-module-only strict mypy check passed under 512/384 MiB, zero swap, 20% CPU.
The exact-tree frontend TypeScript check, ESLint, Prettier, and isolated Vite
build also passed under bounded scopes; the build wrote only to
`/tmp/midas-frontier-build-20261029T0608Z`. A final backend regression selection
passed **4/4**, including the empty-native-label case, under 768/640 MiB, zero
swap, 20% CPU. It emitted one existing Starlette/httpx deprecation warning.

At 07:11:41 CET, host memory PSI avg10/avg60 was zero and avg300 was
some/full `0.38/0.36%`; `MemAvailable=11,485,286,400` bytes (10.69 GiB) and
`SwapFree=8,433,664` bytes (8.04 MiB). User-manager memory/swap charges were
9,596,448,768 / 2,858,450,944 bytes, with unchanged OOM counters 19/15/0.
API and Reality remained active at restart counts 9/14, and the preceding
ten-minute OOM journal query was quiet. This supports further serial bounded
development checks only; it does not resolve the nearly exhausted swap or
identify historic OOM contributors. The whole-API mypy check remains deferred.

## Post-build and admission-telemetry sample — 2026-10-29 06:49 CET

Frontier added process-local source gate counters and a refreshable Exchange Explorer snapshot in commit d712df1. The API reports current admitted operations/venues, cumulative admissions, and busy rejections split by venue and shared capacity with a UTC sample time. Counters reset with the router and are not aggregated across API workers. This improves visibility into Frontier's own bounded source calls; it is not a host-level resource monitor.

The source-gate tests passed 3/3 in 3.80 seconds, including the two rejection categories and counter cleanup; the focused UI test passed 1/1 with eight unrelated cases skipped. Ruff, strict mypy, Prettier, ESLint, and the exact-tree TypeScript check passed. A production Vite build transformed 2,230 modules and passed in 54.80 seconds under a 640/768 MiB, zero-swap, 25% CPU scope with a 384 MiB Node heap. It wrote to a new /tmp directory; the existing ignored dist output was preserved. Vite still reports the 544.51 kB Chart chunk advisory. No live market endpoint was contacted.

At 05:48:15 UTC, MemAvailable was 11,544,653,824 bytes (10.76 GiB), SwapFree was 8,278,016 bytes (7.90 MiB), and host memory PSI averages were zero. User-manager memory/swap charges were 9,513,750,528 / 2,858,569,728 bytes and OOM counters remained 19/15/0. API and Reality were active at restart counts 9 and 14; their health endpoints returned READY with live_execution=false immediately before the final sample. The capacity timer was waiting; gap-detail remained inactive with the prior OOM-kill result. No kernel or systemd-oomd kill appeared in the short query since 05:47 UTC.

No service, timer, resource limit, protected collector, or historical evidence was changed. The host incident remains **PARTIALLY CONTAINED / PARTIALLY VERIFIED**: swap is almost full, the user-manager hierarchy is uncapped, and long-term recovery/attribution is not established. Continue Frontier only through serial, bounded work after fresh admission checks.

## Lazy relationship graph context and post-build sample — 2026-10-29 07:17 CET

Commit `8417971` makes structural context opt-in with
`include_entity_context=true`. The ordinary graph response no longer builds or
serializes entity context; Mission Control requests it only in the
Relationships workspace. Fixture tests confirm default omission and explicit
inclusion. The backend selection passed **4/4** (one existing
Starlette/httpx deprecation warning); the focused graph UI test passed **1/1**
with eight skipped. Prettier, ESLint, exact-tree TypeScript, Ruff, and a fresh
53.40-second Vite production bundle passed under bounded, zero-swap scopes.

At 07:17:31 CET, host PSI avg10/avg60 was zero and avg300 was `some=0.09%`,
`full=0.08%`; `MemAvailable=11,121,684,480` bytes (10.36 GiB),
`SwapFree=8,445,952` bytes (8.06 MiB), user-manager memory/swap
`9,739,001,856 / 2,858,446,848` bytes, and OOM counters 19/15/0. API and
Reality remained active at restart counts 9/14. The last ten-minute kernel and
OOMD journal query was quiet. This sample follows one bounded build; nearly
full swap and historic OOM attribution remain unresolved.

## Historical kill attribution and current host sample — 2026-10-29 07:21 CET

The unfiltered October 28 OOMD snapshots confirm simultaneous large user-session
charges, but do not identify a sole initiating workload. At 23:32:57 the user
manager was at 62.37% pressure against its 50%/20-second policy; the candidate
snapshot listed `midas-api.service` at 1.4 GiB, a GNOME Terminal VTE scope at
1.0 GiB, and `midas-reality.service` at 627.8 MiB. OOMD killed the API. At
23:33:14 pressure remained 52.86%; the 1.0 GiB VTE scope and 627.9 MiB Reality
group were still listed, and OOMD killed that terminal scope. At 23:43:09 the
snapshot listed Reality at 550.7 MiB, the Chromium-named application scope at
337.9 MiB, the MIDAS API at 1.4 GiB, and Reality API at 156.6 MiB; OOMD reported
61.64% parent pressure and killed Reality. The collector restarted at 23:43:19.
At 23:43:24 OOMD killed the gap-detail replay at 54.45% parent pressure while
the API and multiple terminal scopes remained among the candidates. These are
concurrent cgroup charges at the kill instants. A selected kill target is not
proof that the target alone caused parent PSI. The five-minute replay remains
the strongest recurring contributor (106/129 kills and high local PSI), while
the other large user-session workloads and the original trigger cannot be
ranked causally from retained evidence.

The gap-detail service log shows a 23:32:09 start, an OOMD kill at 23:38:29,
an immediate short queued invocation, and another start at 23:42:14 that was
killed at 23:43:24. Its timer was stopped at 23:46:27 and is now inactive and
disabled. Its unit performs bounded replay over finalized Reality data and
writes gap-detail/Arena research state; it is not the live recorder or a
required integrity gate. It remains disabled. Restore only after a separate
resource admission and decision: `systemctl --user enable --now
midas-veritas-gap-detail-v2.timer`.

At 07:20:54 host memory was 5.1 GiB used with 10 GiB available; swap had only
8.1 MiB free. Host memory PSI was 0.00% avg10/avg60 and 0.03/0.02% avg300
(`some`/`full`). The user manager charged 9.61 GB, had a 13.99 GB peak, and
used 2.86 GB swap; its current `memory.stat` was approximately 2.25 GB anon,
6.22 GB file, and 1.12 GB kernel. The user manager and ancestors have no
`MemoryHigh`, `MemoryMax`, or `MemorySwapMax`; `memory.events.local` is zero
there, while aggregate descendant counters remain `high=16,420,097`,
`max=730,045`, `oom=19`, `oom_kill=15`. These inherited counters must not be
attributed to the parent or a single unit. `oomctl` currently lists
`user@1000.service` as monitored at 50%, with pressure avg10/avg60 zero and
avg300 0.04%; the earlier empty monitored-group dump at 04:58 has not been
explained. The current low PSI and large available RAM do not clear the nearly
full swap or the historical reclaim risk.

No systemd-oomd kill appeared after 23:43:24 on October 28; no kernel OOM
appeared after the 20:15:44 capacity-service memcg kill. The Reality capacity
monitor remains on its reversible 160 MiB `MemoryHigh` / 192 MiB `MemoryMax` /
zero-swap drop-in. Its 07:17:27 run completed successfully in about seven
seconds; it still reports `ARCHIVE_SEGMENT_INVENTORY_INVALID` and
`ARCHIVE_MANIFEST_PROVENANCE_INVALID`, plus pending startup-config changes.
These integrity warnings were not repaired or rewritten. The next 30-minute
run is due at 07:47; one successful run is not sustained validation.

MIDAS API, Reality recorder, and Reality API are active. API last started at
23:33:08 and Reality at 23:43:19 after OOMD kills; current restart counts are
9 and 14 respectively. The one-minute Arena dispatcher and Veritas
Observatory completed their sampled runs. Continental production services,
Echo production/staging, Caddy, Headscale, Tailscale, RustDesk, and
`ssh.socket` are active. A separate read-only Continental infrastructure
audit remains failed on its existing `0.0.0.0:8081`, `0.0.0.0:5174`, and
disabled Echo offsite-schedule findings; no unrelated service was changed.
The user-manager failed-unit inventory contains retained historical OOM,
Arena-job, and validation failures; it was not reset, and causes were not
generalized beyond the journal evidence above.

Incident status remains **PARTIALLY CONTAINED / PARTIALLY VERIFIED**. The
five-minute pressure churn and capacity-checker hard-cap failures have
targeted reversible controls in effect, and no new kill was observed through
07:20. The original whole-user pressure trigger, near-exhausted swap, long-run
behavior, and archive integrity remain unresolved. Resume Frontier only in
serial work with fresh admission checks, focused fixture tests capped at
768 MiB, zero swap, and at most 25% CPU. Keep broad suites, whole-API mypy,
replay batches, live probes, and deployment deferred. Stop further work if
host PSI rises, cgroup OOM counters change, or API/Reality approach their
`MemoryHigh` limits.

## Post-continuation pressure sample — 2026-10-29 07:32 CET

Frontier resumed with one serial graph-context display-bound change. The
focused Python entity projection (4/4), centered graph API (1/1), and graph UI
(1/1, eight unrelated tests skipped) passed; strict entity-module mypy,
frontend TypeScript, Ruff, Prettier, and ESLint passed. A temporary-output
production bundle completed in 54.10 seconds with a 383.6 MiB peak under a
768 MiB hard cap, zero swap, and 25% CPU. All transient checks ran one at a
time. No service, timer, limit, recorder, or historical artifact was changed.

At 07:32:06, host PSI avg10/avg60/avg300 was zero, `MemAvailable` was 10 GiB,
and only 8.1 MiB swap remained free. The user-manager had about 9.65 GB memory
and 2.86 GB swap at 07:30; aggregate descendant OOM counters remained
19/15/0. API and Reality remained active at restarts 9/14 and used about 899
MiB/381 MiB against 1.5 GiB/1.125 GiB `MemoryHigh`. The gap-detail timer is
still inactive/disabled. The 30-minute capacity timer is waiting for 07:47:27;
its 07:17 run exited successfully but still reported invalid archive
manifest/inventory provenance, unchanged. No kernel or OOMD kill appeared
between 07:20 and 07:32.

Incident status remains **PARTIALLY CONTAINED / PARTIALLY VERIFIED**. The
bounded feature work did not raise PSI or change OOM counters, so serial
source-independent Frontier work can continue under the stated caps. Near-full
swap, the uncapped user-manager hierarchy, unexplained historical parent
pressure, and archive integrity remain open. The next observation is the
scheduled 07:47 capacity run; do not infer durable recovery from the current
quiet interval.

## Graph API version check and host sample — 2026-10-29 07:38 CET

The centered graph API fixture now asserts its returned `model_version`
matches the shared entity-context v2 constant. The focused test passed **1/1**
in 5.39 seconds under a 768 MiB hard / 640 MiB high, zero-swap, 25% CPU
transient unit; Ruff check and format passed. No runtime configuration or
service state was changed.

At 07:38:08 CET, host memory PSI avg10/avg60/avg300 was zero, `MemAvailable`
was 10 GiB, and `SwapFree` was 8.1 MiB. The user-manager charged 9.68 GB
memory and 2.86 GB swap; its descendant OOM counters remained 19/15/0. API,
Reality, and Reality API were active, with restart counts 9/14/0. API and
Reality used about 902 MiB and 379 MiB, respectively, below `MemoryHigh`. No
kernel or OOMD kill appeared after 07:36:50. Gap-detail remains inactive; the
capacity timer is due at 07:47:27. The host remains **PARTIALLY CONTAINED /
PARTIALLY VERIFIED** with nearly full swap and historical pressure attribution
unresolved.

## Scheduled capacity run and host sample — 2026-10-29 07:48 CET

The 07:47:45 CET `midas-reality-capacity.service` invocation completed with
status 0 at 07:47:52 after 6.651 seconds of CPU. The configured `MemoryHigh`
was 160 MiB, `MemoryMax` 192 MiB, and `MemorySwapMax` zero. systemd did not
retain a completed-oneshot peak value. The report still includes pending
collector budget/retention changes, a capacity warning and critical runway
within fourteen days, invalid archive segment inventory, and invalid manifest
provenance. It reports `RECORDING_UNSEQUENCED`; no collector restart or archive
repair was attempted.

At 07:47:53 host memory PSI avg10/60/300 was zero, `MemAvailable` was 10 GiB,
and only 8.2 MiB swap was free. The user-manager cgroup held 9,668,608,000
bytes of memory and 2,858,422,272 bytes of swap, with inherited event counters
unchanged at `oom=19`, `oom_kill=15`, `oom_group_kill=0`. OOMD showed the
50%-threshold monitored user scope at zero current pressure and about 9.0 GiB
current memory. No OOMD or kernel memory-kill entry appeared since 07:38.
API, Reality, and Reality API remained active at restart counts 9/14/0; API
and Reality used approximately 907/384 MiB. The gap-detail timer remains
inactive; the next capacity run is due at 08:17:45.

The current process snapshot included multiple Codex processes and service
workloads, but it cannot identify the initiator of the prior host pressure.
Continental contact/status, user-level tailnet/auth, Echo production/staging,
Caddy, Headscale, Tailscale, RustDesk, and the SSH socket were active. The
brief quiet period and successful bounded scan do not resolve near-full swap,
historical attribution, long-run stability, or archive provenance. Incident
status remains **PARTIALLY CONTAINED / PARTIALLY VERIFIED**.

## Current cgroup attribution — 2026-10-29 07:51 CET

At 07:49, a one-iteration `systemd-cgtop` read showed about 9.0 GiB in the
user manager, 8.6 GiB in its `app.slice`, and 4.2 GiB in the nested GNOME
Terminal slice. A 07:50:13 systemd query measured that Terminal slice at
4,522,909,696 bytes current and 9,433,034,752 bytes peak. One active VTE
scope, started at 23:39 Oct 28, held 1,969,434,624 bytes current and
2,391,777,280 bytes peak across 103 tasks. Its process tree is a resumed Codex
session with app-server and CUA/MCP children. This is a substantial current
user-session contributor; it does not establish the initiator of the prior
OOM events, and the named VTE scope began after some recorded kills.

Other current user cgroups included `midas-api` at about 908 MiB, Reality at
385 MiB, and Reality API at 299 MiB. `system.slice` was about 3.3 GiB; larger
groups included Netdata (398 MiB), RustDesk (217 MiB), snapd (207 MiB),
Continental status (199 MiB), and Echo production (170 MiB). These services
were active and were left untouched. At 07:50:13 host PSI was zero,
`MemAvailable` 10 GiB, and swap free 8.2 MiB. The evidence supports distributed
concurrent load and uncapped user-manager exposure; it does not justify
terminating terminal sessions or changing unrelated service limits. Incident
status remains **PARTIALLY CONTAINED / PARTIALLY VERIFIED**.

## Post-UI assertion pressure sample — 2026-10-29 07:36 CET

The focused graph UI test now asserts the truncation display. It passed **1/1**
with eight unrelated cases skipped in a 768 MiB hard / 640 MiB high,
zero-swap, 25% CPU transient unit. Prettier and ESLint passed. An initial test
assertion had a selector-label typo and failed; after matching the fixture's
existing question mark before the ellipsis, the test passed. No product or host
configuration change resulted from that correction.

At 07:36:50 CET, host `MemAvailable` was 10 GiB, free swap 8.1 MiB, and
memory PSI avg10/avg60/avg300 zero. The user-manager charged 9.67 GB memory and
2.86 GB swap; aggregate OOM counters remained 19/15/0. API and Reality were
active at restart counts 9/14, using about 901 MiB / 379 MiB against
`MemoryHigh` of 1.5 GiB / 1.125 GiB. The gap-detail timer remained inactive;
capacity monitor next elapses at 07:47:27. No kernel or OOMD kill appeared
between 07:32 and 07:36. This remains short admission evidence, not resolution
of nearly full swap or the historical pressure trigger.

## Bounded replay acceptance and host sample — 2026-10-29 07:53 CET

The exact current worktree passed `tests/frontier/test_replay_comparison.py`
**4/4** in 1.61 seconds. The tests cover identical pinned inputs across paired
scenarios, unique scenario names, rejection of a conflicting state mapping,
bounded double-pass inputs, and comparison-model invariants. Two targeted
timeline checks passed **2/2** in 1.81 seconds: a source outage invalidates
pre-outage books until new snapshots arrive, and timeline hashing is invariant
to input order and tamper-evident. Both transient user services used
`MemoryHigh=384M`, `MemoryMax=512M`, `MemorySwapMax=0`, `CPUQuota=20%`,
`TasksMax=64`, and a 60-second runtime. No public source or captured probe
evidence was read.

At 07:52:52 PSI avg10/60/300 remained zero, `MemAvailable` was 10 GiB, and
`SwapFree` 8.2 MiB. User-manager memory/swap was 9,687,404,544 /
2,858,422,272 bytes, with inherited counters unchanged at 19/15/0. API and
Reality remained active at restart counts 9/14 and about 910/386 MiB. No
OOMD/kernel OOM entry appeared since 07:50. These short fixture checks did
not change incident status; broad suites, replay batches, live probes,
endurance, and deployment remain deferred.

## Replay timing and look-ahead checks — 2026-10-29 07:54 CET

Three targeted current-tree timeline cases passed **3/3** in 1.80 seconds:
source-clock/freshness evidence remains intact, receipt time controls book
availability while exchange time reaches the audit, and future relationship
verification is not applied to earlier frames. They ran in a transient user
service capped at 384 MiB high / 512 MiB hard, zero swap, 20% CPU, 64 tasks,
and a 60-second runtime. No live source or captured probe was accessed.

At 07:54:13, host PSI avg10/60/300 was zero, `MemAvailable` 10 GiB, and
`SwapFree` 8.2 MiB. User-manager memory/swap was 9,688,809,472 /
2,858,422,272 bytes; OOM counters stayed 19/15/0. API and Reality were active
at restart counts 9/14 and about 911/388 MiB. No OOMD or kernel OOM appeared
after 07:50. Incident status remains **PARTIALLY CONTAINED / PARTIALLY
VERIFIED**; nearly full swap and broad acceptance limits are unchanged.

## Cross-market relationship safety checks — 2026-10-29 07:55 CET

Five current-tree cases passed **5/5** in 1.62 seconds from
`test_relationships_economics_replay.py`: text matching proposes hypotheses
only, payoff verification rejects authority/settlement mismatch, spot cannot
be verified as a prediction contract across three venue cases, and payout
currency mismatch fails without an explicit valuation bridge. The transient
user service had 384 MiB high / 512 MiB hard memory, zero swap, 20% CPU, 64
tasks, and 60-second runtime. No live source or captured probe data was read.

At 07:55:22 host PSI was zero, `MemAvailable` 10 GiB, and `SwapFree` 8.2 MiB.
User-manager memory/swap was 9,700,184,064 / 2,858,422,272 bytes; OOM counters
remained 19/15/0. API and Reality were active at restart counts 9/14 and about
912/390 MiB. No OOMD or kernel OOM appeared since 07:50. This fixture result
strengthens relationship rejection behavior but does not establish a live
cross-venue match or change the **PARTIALLY CONTAINED / PARTIALLY VERIFIED**
incident state.

## Logical implication economics checks — 2026-10-29 07:56 CET

Five focused cases in `test_logical_implication_economics.py` passed **5/5**
in 1.60 seconds. They reject reverse implication with a counterexample,
settlement-time bridging, silently treating unknown fees as zero, stale-leg
completion, and post-cutoff relationship evidence. The test ran under a
384 MiB high / 512 MiB hard, zero-swap, 20% CPU, 64-task, 60-second transient
service. No source access occurred.

At 07:56:03 PSI remained zero, `MemAvailable` was 10 GiB, `SwapFree` 8.2 MiB,
user-manager memory/swap was 9,697,857,536 / 2,858,422,272 bytes, and OOM
counters remained 19/15/0. API/Reality were active at restarts 9/14 and about
912/391 MiB; no OOMD or kernel OOM appeared since 07:50. This adds fixture
evidence for conservative economics but does not alter the partial incident
status or support live-profitability claims.

## Offline adapter acceptance and host sample — 2026-10-29 07:57 CET

Five focused cases passed **5/5** in 3.71 seconds: adapter configs/capabilities
fail closed, the default registry remains disabled and network-idle, Coinbase
Spot keeps native book/trade semantics, Gemini Spot normalizes fixture
metadata/books, and Gemini rejects perpetual products and non-string book
decimals. The transient service used 384 MiB high / 512 MiB hard, zero swap,
20% CPU, 64 tasks, and a 60-second runtime. One existing Starlette/httpx
deprecation warning appeared; no exchange endpoint was contacted.

At 07:57:10 host PSI remained zero, `MemAvailable` 10 GiB, and `SwapFree`
8.2 MiB. User-manager memory/swap was 9,703,047,168 / 2,858,422,272 bytes;
OOM counters stayed 19/15/0. API, Reality, and Reality API remained active at
restarts 9/14/0, with API/Reality about 913/393 MiB. No OOMD/kernel OOM
appeared since 07:50. These fixture tests do not change the partial incident
status or authorize live source probes.

## Polymarket, Kalshi, and Kraken fixture checks — 2026-10-29 07:58 CET

Three selected `test_adapters.py` cases passed **3/3** in 2.70 seconds:
Polymarket output remains descriptive without verified-payout claims, Kalshi
multivariate output preserves event/group/market evidence, and Kraken Spot
preserves native units and level timestamps. The transient test service used
384 MiB high / 512 MiB hard memory, zero swap, 20% CPU, 64 tasks, and a
60-second runtime; no public source was queried.

At 07:57:55 host PSI was zero, `MemAvailable` 10 GiB, and `SwapFree` 8.2 MiB.
User-manager memory/swap was 9,709,481,984 / 2,858,422,272 bytes; OOM counters
remained 19/15/0. API, Reality, and Reality API stayed active at restart
counts 9/14/0; API/Reality used about 912/393 MiB. No OOMD/kernel OOM
appeared since 07:50. These fixture tests add no live validation and the
incident remains **PARTIALLY CONTAINED / PARTIALLY VERIFIED**.

## Held-source transport denial — 2026-10-29 07:59 CET

Four focused tests passed **4/4** in 3.29 seconds. They verify that Gemini's
hold blocks before request; flagged, copied, or transport-overridden Coinbase
configurations cannot bypass the terms hold. All use fake transports; no
network request was made. The transient user service used 384 MiB high /
512 MiB hard, zero swap, 20% CPU, 64 tasks, and a 60-second runtime. One
existing Starlette/httpx deprecation warning appeared.

At 07:58:42 PSI was zero, `MemAvailable` 10 GiB, and `SwapFree` 8.2 MiB.
User-manager memory/swap was 9,708,617,728 / 2,858,422,272 bytes; OOM
counters remained 19/15/0. API/Reality were active at restart counts 9/14,
using about 913/394 MiB. No OOMD/kernel OOM appeared since 07:50. This
verifies the hold boundary in fixtures, not source permission or live access.

## Economic Workbench UI test and host sample — 2026-10-29 08:00 CET

The paired baseline/current-assumptions Economic Workbench UI test passed
**1/1**, with eight unrelated tests skipped, in 15.38 seconds. It submitted
execution delay, slippage, partial-fill, and quote-decay assumptions against
mocked saved-evidence responses. The transient user service was capped at
640 MiB high / 768 MiB hard, zero swap, 25% CPU, 96 tasks, and 90 seconds;
Node heap was 384 MiB. No public request was made.

At 08:00:02 host PSI was zero, `MemAvailable` 10 GiB, `SwapFree` 8.2 MiB.
User-manager memory/swap was 9,715,281,920 / 2,858,409,984 bytes; inherited
OOM counters remained 19/15/0. API, Reality, and Reality API were active at
restarts 9/14/0. No OOMD/kernel OOM appeared after 07:55. This short
fixture-based UI check does not establish long-run stability or change the
**PARTIALLY CONTAINED / PARTIALLY VERIFIED** incident state.

## Transient cgroup accounting calibration — 2026-10-29 08:02 CET

A live transient unit confirmed the effective cgroup controls directly:
`memory.high=402,653,184`, `memory.max=536,870,912`,
`memory.swap.max=0`, and `TasksMax=64`. A 32 MiB touched-allocation check
showed 37,662,720 bytes current / 37,744,640 bytes peak with no swap.

A current-tree four-test pytest slice was run with a shell wrapper that kept
its transient cgroup alive after pytest exited. Live systemd/cgroup telemetry
showed a 42,086,400-byte peak (about 40.1 MiB); the tests passed 4/4. In
contrast, fast `systemd-run --collect --wait` pytest jobs, whose cgroups had
already been removed before the final status was sampled, printed 256 KiB.
That exit-summary value underreports pytest peak memory and must not be
treated as a benchmark. The configured caps are enforced; later peak claims
will require a live/retained cgroup sample.

At 08:02:24 PSI was zero, `MemAvailable` 10 GiB, and `SwapFree` 8.3 MiB.
User-manager memory/swap was 9,718,988,800 / 2,858,340,352 bytes; OOM
counters remained 19/15/0. API/Reality/Reality API remained active at
restarts 9/14/0; API/Reality used about 915/397 MiB. No OOMD or kernel OOM
appeared since 07:58. This instrumentation check changed no persistent host
configuration and does not resolve near-full swap or long-run stability.

## Multi-outcome economics checks and host sample — 2026-10-29 08:03 CET

Three selected current-tree tests passed **3/3** in 1.70 seconds: multi-
outcome candidate and audit price-tick enforcement, exact hypothetical
coverage classification, and bounded overlapping three-leg payoff-basket
search. The 384 MiB high / 512 MiB hard transient cgroup was retained for
five seconds after pytest exit; live `memory.peak` was 43,180,032 bytes
(about 41.1 MiB), with zero swap. This is a measured peak for this slice.

At 08:03:24 host PSI was zero, `MemAvailable` 10 GiB, and `SwapFree` 8.4 MiB.
User-manager memory/swap was 9,731,592,192 / 2,858,254,336 bytes; OOM
counters remained 19/15/0. API/Reality were active at restart counts 9/14,
using about 916/397 MiB. No OOMD or kernel OOM appeared since 08:00. The
bounded fixture test did not change the **PARTIALLY CONTAINED / PARTIALLY
VERIFIED** incident status.

## Capital and FX fixtures with post-run host sample — 2026-10-29 08:04 CET

Four selected tests passed **4/4** in 1.61 seconds: venue-separated capital
carry is independently checked; supplied release delays cover every venue;
conversion fees apply to every terminal state; and a same-identity case
cannot add an unverified FX/conversion assumption. The transient service was
configured with 384 MiB high / 512 MiB hard, zero swap, 20% CPU, 64 tasks,
and a 60-second runtime. Its fast collected-unit peak field was 256 KiB and
is not a trustworthy measurement under the calibration above; no peak claim
is made for this test. No external data was accessed.

At 08:04:33 PSI was zero, `MemAvailable` 10 GiB, `SwapFree` 8.4 MiB, and
user-manager memory/swap 9,728,978,944 / 2,858,254,336 bytes. OOM counters
remained 19/15/0; API/Reality were active at restarts 9/14, about 916/398
MiB. No OOMD or kernel OOM appeared since 08:00. The tests do not change the
**PARTIALLY CONTAINED / PARTIALLY VERIFIED** incident assessment.

## Pinned-input replay and provenance checks — 2026-10-29 08:05 CET

Two selected `test_timeline_api.py` cases passed **2/2** in 10.59 seconds.
The replay API staged only pinned local inputs without source requests; the
empty journal remained missing and hash-chain corruption failed closed. The
transient cgroup was retained and measured 69,042,176 bytes peak (about
65.9 MiB), under 384 MiB high / 512 MiB hard, zero swap, 20% CPU, 64 tasks,
and a 60-second runtime. One existing Starlette/httpx deprecation warning
appeared; temporary stores and fixtures only.

At 08:05:36 PSI was zero, `MemAvailable` 10 GiB, and `SwapFree` 8.4 MiB.
User-manager memory/swap was 9,732,186,112 / 2,858,254,336 bytes; OOM
counters remained 19/15/0. API, Reality, and Reality API were active at
restarts 9/14/0; API/Reality used about 917/399 MiB. No OOMD or kernel OOM
appeared since 08:03. Incident status remains **PARTIALLY CONTAINED /
PARTIALLY VERIFIED**.

## User-slice attribution and UI test pressure sample — 2026-10-29 08:12 CET

`oomctl dump` confirms the active memory-pressure monitor is
`/user.slice/user-1000.slice/user@1000.service`: 50% pressure for 20 seconds.
The user manager has no `MemoryHigh`, `MemoryMax`, or `MemorySwapMax` limit.
The Oct 28 OOMD entry recorded 54.45% pressure above the 50% threshold with
reclaim activity, then killed `midas-veritas-gap-detail-v2.service`. This
proves the OOMD trigger, not the workload that created that pressure. The
separate capacity-service kernel OOMs remain attributable to its former
128 MiB `MemoryMax`; the service now reads back as 160 MiB high / 192 MiB max /
zero swap and its 07:47:45 run succeeded. Its next timer point is 08:17:45.

At 08:07, `app.slice` held 9,335,378,816 bytes and 2,230,583,296 bytes swap.
Its memory statistics were about 1.99 GB anonymous, 6.25 GB file cache, and
1.08 GB kernel/slab. The GNOME Terminal slice held 4,539,244,544 bytes and
1,647,251,456 bytes swap; one VTE scope was 1,985,372,160 bytes across 106
tasks. This is a large current contributor, with substantial file-cache and
kernel/slab accounting, but does not establish historical causation. The
largest user-slice pressure event and the earlier terminal kills remain
unattributed to a single workload.

At 08:08, five `vmstat` samples showed brief first-sample swap-in/out (66/70
pages per second) followed by four samples at zero. The one-minute Arena
dispatcher repeatedly reported no scheduled work; its observed CPU use was
small. The Veritas observation, analysis, director, and capacity timers are
bounded but can overlap by schedule; no evidence ties their recent runs to
the past OOMD threshold crossing.

A focused Kalshi fee-sensitivity UI test was attempted twice. The first
transient service exited 1 after about 20 seconds, but its assertion output
was unavailable. A second run was capped at 640 MiB high / 768 MiB max, zero
swap, 25% CPU, 96 tasks, a 90-second runtime, and a 384 MiB Node heap. It hit
the runtime limit at 91.6 seconds after 22.09 CPU seconds; the captured log
contains only the Vitest startup line. It produced no test result. A live
sample showed 667,418,624 current / 672,047,104 peak bytes; the transient
summary separately reported a 661.5 MiB peak. Both observations are below the
hard cap and at/above the 640 MiB high threshold. No source request was made.

At 08:10:59 global memory PSI briefly reached `some` avg10/60/300
5.70/2.27/0.53% and `full` 5.28/2.10/0.49%; by 08:11:50 it had decayed to
0.03/0.95/0.44% and 0.02/0.88/0.40%. `MemAvailable` stayed about 10 GiB,
swap remained nearly full, and recent OOM counters stayed 19/15/0. API,
Reality, and Reality API remained active at restarts 9/14/0; API and Reality
were below their configured `MemoryHigh` thresholds. The transient test likely
contributed to short cgroup reclaim and host PSI, but this does not explain
the earlier OOMD event. No more UI checks or broad suites should run until a
fresh, longer low-pressure admission window is observed.

Incident status remains **PARTIALLY CONTAINED / PARTIALLY VERIFIED**. The
gap-detail timer remains inactive and disabled. Rollback commands for both
the timer and capacity drop-in are in “Actions in effect and rollback” above.

## Low-memory fixture admission after UI stop — 2026-10-29 08:15 CET

With global memory PSI avg10 at zero and oomd's monitored user cgroup near
zero, two bounded storage-security checks passed **2/2** in 2.01 seconds:
oversized base64 rejection before decode and offline evidence-tamper detection.
Three graph-revision checks passed **3/3** in 2.31 seconds: graph revision
changes for rendered market metadata but not books/trades, legacy migration
backfills graph revisions, and relationship-review counters update
atomically. Both runs used 384 MiB high / 512 MiB max, zero swap, 20% CPU,
64 tasks, and a 60-second runtime. A concurrent live cgroup sample of the
graph run measured a 44,711,936-byte peak, zero swap, and no high/max/OOM
events. The fast collected-unit 256 KiB peak from the first test is invalid
after cgroup removal and is excluded.

At 08:15:35 global memory PSI was 0/0.01/0.18% avg10/60/300 and full
0/0.01/0.17%; oomd's user-cgroup pressure was 0/0.01/0.20%. `MemAvailable`
was 10 GiB; swap remained nearly full. API/Reality/Reality API remained active
at restarts 9/14/0, with API/Reality at about 967/423 MiB. OOM counters stayed
19/15/0, and no recent OOMD/kernel OOM entry appeared. The 08:17:45 capacity
timer is the next validation point. Small serial fixture work may continue
after fresh admission; UI retries, broad suites, and endurance work remain
deferred.

## Analytics fixture and host sample — 2026-10-29 08:21 CET

Three selected analytics behaviors were checked: bounded empty-sample output,
recurrence requiring distinct books and replay times, and exclusion of invalid
source lineage. The last two passed first. The empty-sample case first failed
because the expected venue list omitted `gemini_spot`; registry and model code
confirm the Gemini Spot adapter is registered and analytics emits a row for
each `Venue`. The assertion now tracks the declared enum, and the corrected
case passed **1/1** in 1.61 seconds. No adapter implementation was weakened.

Both transient cgroups were under 384 MiB high / 512 MiB max, zero swap, 20%
CPU, and 64 tasks. Live peaks were 41,836,544 and 41,730,048 bytes; no high,
max, OOM, or swap events occurred. At 08:21:35 global memory PSI and oomd
user-cgroup pressure were zero at avg10/60 and 0.03% at avg300. `MemAvailable`
was 10 GiB, swap nearly full, OOM counters 19/15/0, and API/Reality remained
active at restart counts 9/14. The small fixture run did not change the
**PARTIALLY CONTAINED / PARTIALLY VERIFIED** incident status.

## Scheduled capacity monitor follow-up — 2026-10-29 08:18 CET

The existing timer launched `midas-reality-capacity.service` at 08:17:52;
it exited successfully at 08:17:59 after 6.544 CPU seconds. The effective
limits remained 160 MiB high / 192 MiB max / zero swap. No live cgroup peak
was captured. The systemd final summary's 256 KiB peak is invalid after the
oneshot cgroup had been removed and is not used as a measurement.

The generated report still contains pending budget/retention restart notices,
capacity horizon warnings, `ARCHIVE_SEGMENT_INVENTORY_INVALID`, and
`ARCHIVE_MANIFEST_PROVENANCE_INVALID`. These are separate data-integrity and
configuration issues; no archive repair, deletion, or Reality collector
restart was performed. At 08:17:52 memory PSI and monitored user-cgroup
pressure were zero, `MemAvailable` was 10 GiB, swap remained nearly full, and
OOM counters remained 19/15/0. The API, Reality, and Reality API services
remained active at restarts 9/14/0. This is another successful bounded run,
not proof of sustained memory headroom or full incident recovery.

## Collection API safety fixtures and host sample — 2026-10-29 08:19 CET

Three collection API tests passed **3/3** in 4.99 seconds: held/disabled
sources fail before journal creation or network request; a capability-manifest
change blocks checkpoint resume; and an unregistered adapter is reported
before journal access. They ran under 384 MiB high / 512 MiB max, zero swap,
20% CPU, 64 tasks, and a 60-second timeout. Live cgroup peak was 64,749,568
bytes with no swap or high/max/OOM events. One existing Starlette/httpx
deprecation warning appeared. Local fake adapters only; no external source
request.

At 08:19:30 global memory PSI was 0/0/0.06% avg10/60/300, and oomd's
user-cgroup pressure was 0/0/0.07%; `MemAvailable` was 10 GiB while swap was
still nearly full. OOM counters remained 19/15/0; API and Reality remained
active at restart counts 9/14, around 969/426 MiB. No OOMD or kernel OOM
appeared in the recent window. This supports continuing small serial fixture
work only; the 640 MiB UI retry, broad suites, and endurance runs stay
deferred.

## Cross-venue discovery fixture admission — 2026-10-29 08:24 CET

The deterministic three-scope discovery fixture passed **1/1** in 1.69
seconds. Its transient cgroup peaked at 42,405,888 bytes under 384 MiB high /
512 MiB max, zero swap, 20% CPU, and 64 tasks; no high/max/OOM event occurred.
The cgroup was isolated from live sources. At 08:24:26 memory PSI and oomd's
monitored user-cgroup pressure were zero, with about 10 GiB available; swap
remained nearly full and OOM counters stayed 19/15/0. API and Reality remained
active at restarts 9/14. The latest bounded fixture check did not create
measurable host memory pressure. Incident status remains **PARTIALLY
CONTAINED / PARTIALLY VERIFIED**.

## Host recheck — 2026-10-29 08:27 CET

At 08:26:15, the host had 11,036,332 kB `MemAvailable` and 8,600 kB
`SwapFree`. Global memory PSI avg10/60/300 was zero. The user manager held
9,785,925,632 bytes memory and 2,858,250,240 bytes swap; aggregate descendant
counters remained `oom=19`, `oom_kill=15`, `oom_group_kill=0`. API and Reality
were active at restart counts 9 and 14, using 973,557,760 and 430,526,464
bytes respectively. The capacity timer remained active between scheduled
runs; the gap-detail timer remained inactive and disabled.

No systemd-oomd entry or kernel OOM appeared after the 08:24:26 sample. This
is only a three-minute quiet interval with almost no free swap; it is not
evidence of durable recovery. The historical initiating workload remains
unknown. No production service or archive data was changed during this check.

## OOMD monitor-tree recheck — 2026-10-29 08:30 CET

The earlier `oomctl dump` output that listed no monitored cgroups is not
reproducible in the latest sample: at 08:30:35, `oomctl` listed
`/user.slice/user-1000.slice/user@1000.service` under memory-pressure
monitoring at 50% for the configured 20-second duration. Its reported current
pressure was zero, matching the cgroup's zero avg10/60/300 PSI. The `oomctl`
`System Context` totals still displayed 0B for RAM and swap even while the
monitored user cgroup reported 9.1G current memory; this display inconsistency
remains unexplained. The swap-monitor list was empty.

At 08:30:31, host `MemAvailable` was 11,072,948 kB and `SwapFree` 8,612 kB.
The user-manager cgroup held 9,794,785,280 bytes memory and 2,858,242,048
bytes swap. Aggregate events remained `oom=19`, `oom_kill=15`, and
`oom_group_kill=0`. API and Reality were active at restart counts 9/14 with
974,974,976 / 432,996,352 bytes current. No systemd-oomd or kernel OOM log
appeared after 08:24:26. This five-minute observation remains too short to
establish recovery; nearly full swap and the historical initiating workload
remain unresolved.

## Source-use hold regression — 2026-10-29 08:32 CET

`tests/frontier/test_source_data_permissions.py::test_probe_flags_and_references_do_not_enable_unvalidated_sources`
passed **1/1 in 7.21 seconds**. The fixture deliberately requested Kalshi and
Kraken probes with enabled flags and arbitrary permission-reference strings;
both remained disabled, all relevant routes returned HTTP 409 with the
policy reason, and each adapter transport retained `request_count=0`. Gemini
also remained held. This used no exchange endpoint or saved probe data.

The test ran serially with the existing repository Python environment inside a
transient user scope bounded at 384 MiB high / 512 MiB max, zero swap, 20% CPU,
and 64 tasks. One existing Starlette/httpx deprecation warning appeared. No
direct cgroup peak was retained. At 08:32:39, global and user-cgroup memory
PSI was zero; `MemAvailable` was 11,058,496 kB and `SwapFree` 8,612 kB.
User-manager `memory.events` remained unchanged (`high=16,422,194`,
`max=730,045`, `oom=19`, `oom_kill=15`); API and Reality remained active at
restart counts 9/14. No systemd-oomd or kernel OOM entry appeared since
08:24:26. This supports the offline permission gate only; the incident is
still **PARTIALLY CONTAINED / PARTIALLY VERIFIED**, with almost no free swap
and the historical initiating workload unknown.

Two configuration-only cases in
`tests/frontier/test_source_data_permissions.py` also passed **2/2 in 5.70
seconds**: arbitrary Kalshi/Kraken permission-reference values do not enable
sources, and whitespace-only references do not enable probes. These use local
settings validation only. The same 384/512 MiB high/max, zero-swap, 20% CPU,
64-task scope was used; a Starlette/httpx deprecation warning appeared. No
direct cgroup peak was retained.

At 08:33:36, global PSI and the user-manager `high`, `max`, `oom`, and
`oom_kill` counters were unchanged from the 08:32 sample; `MemAvailable` was
11,044,580 kB and `SwapFree` 8,612 kB. API and Reality remained active at
restart counts 9/14. OOMD and kernel OOM journals remained empty since
08:24:26. This adds source-permission fixture evidence only and does not
change the incident assessment.

## 2026-10-29 08:45 CET — latest pressure attribution and bounded continuation

- At 08:41:56, the host had 11,306,045,440 bytes (`10.53 GiB`) available and
  8,835,072 bytes of swap free (4,286,128,128 of 4,294,963,200 bytes used).
  Global memory PSI avg10/60/300 and full PSI avg10/60/300 were zero. The
  `user@1000` cgroup held 9,821,118,464 bytes memory and 2,858,233,856 bytes
  swap. Its cumulative events were unchanged at `high=16,422,194`,
  `max=730,045`, `oom=19`, `oom_kill=15`, `oom_group_kill=0`.
- `oomctl dump` now lists the user-manager cgroup at the configured 50%
  pressure threshold, with current pressure zero and reported usage 9.1 GiB.
  Its separate System Context totals still show 0 B. The mismatch is
  unresolved. `user.slice`, `user-1000.slice`, and `user@1000.service` have no
  `MemoryHigh`, `MemoryMax`, or `MemorySwapMax` ceiling; the OOMD pressure
  policy, rather than a user-slice hard limit, caused the documented
  historical OOMD kills.
- A leaf-cgroup sample at 08:41:07 showed the largest current entries as an
  active GNOME Terminal `vte-spawn` scope at 1,915 MiB, API at 935.5 MiB,
  Reality at 421.7 MiB, and Reality API at 324.4 MiB. The Veritas source
  analysis timer then ran from 08:40:58 to 08:41:09 at about 218 MiB and
  exited successfully. This describes current occupancy and a scheduled job;
  it does not establish which process caused the historical parent-cgroup
  pressure. No interactive scope was altered.
- At 08:41, API, Reality, and Reality API were active with restart counts
  9/14/0. Current usage was about 935/422/324 MiB against limits of
  1,536/1,152/512 MiB respectively (API and Reality also have hard limits of
  1,792 and 1,280 MiB). The Reality status written at 08:40:05 reported
  `RECORDING_UNSEQUENCED`, `active_receiving`, 16/16 fresh books, one recorded
  failure, no process backpressure, and `sequence_verified=false`. No Reality
  restart, configuration change, or data repair was performed.
- Continental Cloud tailnet and ID auth remained active. Echo production and
  staging, RustDesk, `ssh.socket`, and systemd-oomd were active; SSH is
  socket-activated. The unrelated Continental read-only infrastructure audit
  failed at 08:34:58 with three policy findings: listeners on `0.0.0.0:8081`
  and `0.0.0.0:5174`, plus a disabled Echo offsite schedule. It exited with
  status 1 after 1.529 CPU seconds; this was not an OOM. No listeners,
  schedules, or unrelated services were changed. The owning service/operator
  should review those audit findings separately.
- The gap-detail timer remains `inactive` and `disabled`; its five-minute
  replay remains the strongest identified recurring OOMD contributor: 106 of
  129 October 28 kills targeted it, and a captured service cgroup had
  75% memory PSI while using about 205 MiB under `MemoryHigh=192M` and
  `MemoryMax=256M`. It was auxiliary finalized-segment analysis, not live
  capture or an integrity check. The capacity timer remains active every 30
  minutes; its current effective limit is `MemoryHigh=160M`,
  `MemoryMax=192M`, `MemorySwapMax=0`. The 08:17:52 run exited successfully at
  08:17:59. Its post-cleanup 256 KiB peak field is not a valid process peak.
- The pre-fix `project/reality` code parsed an unbounded archive manifest and,
  when its provenance was invalid, materialized every directory entry before
  checking files. The killed runs did not retain a memory peak or entry count,
  so this was a code-supported risk, not a demonstrated per-run cause. The
  08:50 addendum below records the bounded fix and scheduled-run evidence.
- After the scheduled source-analysis job completed, the final formatted
  Kraken WebSocket reconstructor suite passed **12/12 tests in 1.88 seconds**.
  It ran in a transient 384 MiB high / 512 MiB max, zero-swap, 20% CPU,
  64-task scope; targeted `ruff check` also passed. No endpoint or saved probe
  data was accessed. At 08:44:18, MemAvailable was 11,263,049,728 bytes,
  SwapFree was 8,839,168 bytes, global PSI remained zero, and the user-manager
  counters were unchanged. No kernel OOM/systemd-oomd entries appeared after
  08:44:11. This validates the offline parser only; the adapter continues to
  declare `BOOK_UPDATES` unsupported pending transport, durable provenance,
  and service integration.
- No kernel OOM or systemd-oomd record appeared after the 08:24:26 journal
  checkpoint; the last known OOMD kill remains 23:43:24 October 28 and the
  last kernel capacity OOM 20:15:44. This quiet interval is not proof of
  recovery. Almost all swap remains occupied, current terminal memory is
  substantial, and the historical workload mix is not fully attributed.

**Continuation gate:** Frontier may continue with short, serial, offline
fixture work inside transient resource scopes after a fresh PSI/cgroup check.
Keep broad suites, UI builds, profiling, large replay, new campaigns, live
source probes, and deployment deferred. The incident stays **PARTIALLY
CONTAINED / PARTIALLY VERIFIED**; do not infer that the machine is cleared for
heavy work from available RAM or a brief zero-PSI sample.

## 2026-10-29 08:50 CET — capacity-scan mitigation and scheduled validation

- Inspected the isolated `/home/charlie/midas-reality-capacity-scan-frontier-20261029`
  branch. It was based exactly on the clean service worktree commit
  `4f5cb5689548987bf30a33f050284ea8cb2f3c28` and had four local commits:
  `8b2131f`, `9868dac`, `7e637a9`, and `d8629e4`. The focused
  `tests/test_reality_operations.py -k archive_capacity` run passed **5/5**
  (35 deselected) in 0.80 seconds under a 384 MiB high / 512 MiB max,
  zero-swap, 20% CPU, 64-task transient scope. It used temporary fixtures and
  did not scan the real archive.
- Fast-forwarded only the local `/home/charlie/midas-reality` branch
  `project/reality` from `4f5cb56` to `d8629e4`. The worktree was clean before
  and after. No service configuration changed, no manual capacity invocation
  occurred, and the protected Reality recorder was not restarted. The next
  existing timer invocation therefore exercised the fix without an explicit
  restart.
- The change streams the inventory directory walk with a hard 65,536-entry
  bound, returns unknown bytes/headroom if that bound is exceeded, reads the
  archive manifest with a 4 MiB byte cap plus a growth-race check and no-follow
  regular-file open, and skips an inventory walk when manifest provenance is
  invalid or size-limited. It leaves all archive bytes and manifest contents
  untouched. The report deliberately shows unknown archive capacity when its
  inventory cannot be trusted.
- The scheduled capacity service ran at 08:48:00 and finished successfully at
  08:48:07 (6.572 CPU seconds), under its existing
  `MemoryHigh=160M` / `MemoryMax=192M` / `MemorySwapMax=0` bounds. The new
  report carries `ARCHIVE_MANIFEST_SIZE_LIMIT`,
  `ARCHIVE_INVENTORY_UNVERIFIED`, and `ARCHIVE_CAPACITY_UNKNOWN`; archive
  `raw_archive_bytes`, headroom, and runway are null. This confirms the
  over-4-MiB manifest is rejected before inventory traversal and that the
  scheduled checker completed. Its process memory peak was not retained, so
  this does not quantify the memory reduction.
- Reality status briefly changed at 08:48:34 to `DEGRADED_BOOKS`, 15/16 fresh,
  stale. By 08:48:55 it had returned to `RECORDING_UNSEQUENCED`,
  `active_receiving`, 16/16 fresh, one recorded failure, no backpressure, and
  `sequence_verified=false`. The recorder PID stayed 1235804, restart count
  14; no matching error or OOM record appeared. This transient source-quality
  change is recorded as an observation, not attributed to the capacity code.
- At 08:49:13, MemAvailable was 11,267,211,264 bytes, SwapFree was 9,240,576
  bytes, global PSI remained zero, user-manager memory/swap were
  9,849,122,816 / 2,858,233,856 bytes, and OOM counters remained 19/15/0. No
  kernel or systemd-oomd record appeared since 08:47:30. API and Reality
  remained active at restart counts 9/14. The host remains partially
  contained; nearly full swap and uncertain historical workload attribution
  are unresolved.

Rollback for the code-only fast-forward, if needed, is a revert commit (no
reset or forced branch movement):

```sh
git -C /home/charlie/midas-reality revert --no-edit 4f5cb5689548987bf30a33f050284ea8cb2f3c28..d8629e4b63c8b8ef68e27294fb3599423a694b76
```

Keep the five-minute gap-detail timer disabled. Frontier may continue with
short serial fixture work after fresh admission; do not use the quiet interval
or successful capacity run as evidence for heavy tests, full recovery, archive
integrity, or production readiness.

## 2026-10-29 08:54 CET — interruption revalidation

- Before recording this update, the Frontier branch was at
  `75e6f2602a33ca7d04ffb507279dd61fd33d7bac`, with no tracked changes and the
  existing untracked `data/frontier-public-probes/` preserved. A fresh local
  checkpoint branch, `checkpoint/frontier-memory-interruption-20261029-0854`,
  now points to that commit. No untracked data was staged or changed.
- At 08:54:26 the host showed about 10 GiB `MemAvailable`, zero current global
  PSI, and 4.0 GiB of 4.0 GiB swap occupied. User-slice `memory.pressure` also
  had zero current averages. This is presently quiet, but swap remains an
  unresolved risk; `swapoff` or a global sysctl/OOM-policy change would be
  unsafe without better evidence.
- At 08:52, `app.slice` charged 9.48 GB memory and 2.23 GB swap, with no local
  `MemoryHigh`, `MemoryMax`, or `MemorySwapMax`. Its `memory.stat` attributed
  about 6.36 GB to file cache (5.04 GB inactive), 2.02 GB to anonymous memory,
  and 1.09 GB to kernel memory, including 0.93 GB reclaimable slab. The parent
  `user@1000.service` was at about 9.88 GB memory and 2.86 GB swap. Its
  accumulated descendant counters were `high=16,422,194`, `max=730,045`,
  `oom=19`, `oom_kill=15`; these counters cannot identify one contributing
  service. The top process RSS sample was below 400 MiB per process. Current
  occupancy is therefore not a reliable reconstruction of the event-time
  workload.
- `systemd-oomd` remains active. The effective user-manager policy is
  `ManagedOOMMemoryPressure=kill` at 50%; the October 28 logs show 129 kills
  when user-manager pressure exceeded that threshold for over 20 seconds with
  reclaim activity. The final such kill remains 23:43:24 on October 28. A
  separate `sar` sample around 23:30–23:50 showed 10.0–10.4 GB available RAM
  and about 77% swap use, so these observations do not demonstrate global RAM
  exhaustion at those sample instants. They do establish severe user-cgroup
  reclaim pressure and the policy that selected victims. The exact workload
  mix that caused the pressure remains unattributed. Gap-detail's repeated
  local pressure and 106/129 kill share make it the strongest known recurring
  contributor, not a proven sole cause.
- Kernel logs still show seven separate `CONSTRAINT_MEMCG` kills of
  `midas-reality-capacity.service` at its former 128 MiB ceiling, the latest
  at 20:15:44 October 28. Its source previously parsed an unbounded manifest
  and could walk every archive entry when provenance was invalid; the killed
  executions did not retain manifest sizes or allocation traces, so this is a
  supported failure mechanism, not proof of the exact allocation on each run.
  The local Reality branch now has a 4 MiB manifest read bound, a 65,536-entry
  walk bound, and skips untrusted inventory. The next existing scheduled run
  at 08:48 succeeded within effective `MemoryHigh=160M`, `MemoryMax=192M`,
  `MemorySwapMax=0`, reporting `ARCHIVE_MANIFEST_SIZE_LIMIT`,
  `ARCHIVE_INVENTORY_UNVERIFIED`, and `ARCHIVE_CAPACITY_UNKNOWN`. The archive
  capacity remains unknown; no archive evidence or manifest was repaired.
- At 08:54, `midas-api` and `midas-reality` were active with unchanged restart
  counts 9 and 14. Their current memory was about 0.99 GB and 0.45 GB against
  their 1.75 GB and 1.25 GB maxima. No new OOMD kill or kernel OOM appeared
  after the previously recorded events. The gap-detail timer remains
  inactive/disabled. No matching pytest, gap-detail, Arena job, capacity
  process, or recovery-validation worker was active. No critical collector or
  unrelated service was restarted or reconfigured during this revalidation.
- No additional host configuration was changed in this interruption. The
  existing containment and rollback commands are recorded above. The initial
  `daymark-db.service` failure and the separate Continental audit findings
  remain unrelated and untouched.

**Current continuation decision:** resume Frontier only with serial source
work, fresh admission checks, and focused offline fixture checks under a
transient resource scope (384 MiB `MemoryHigh`, 512 MiB `MemoryMax`, zero swap,
20% CPU, 64 tasks). Keep full test suites, builds, profiling, large replay,
live probes, and background experiments deferred. Current zero PSI and the
quiet interval support this narrow continuation; nearly exhausted swap,
unknown historical workload attribution, and the unresolved
`oomctl`/monitor-registration discrepancy mean host recovery is not proven.

## 2026-10-29 09:05 CET — bounded Frontier resumption and host recheck

- Frontier resumed with one offline, fixture-driven Kraken Spot WebSocket v2
  capture path. It accepts one explicitly configured spot symbol, one finite
  connection, bounded frames and captured records, and validates the book
  checksum before accepting reconstructed state. It stores raw-frame hashes
  and source timestamps with the normalized update. The feature is contextual
  market research only; it does not imply payoff equivalence with prediction
  contracts or execution capability. No public network probe was made.
- The new capture tests and existing Kraken book-stream tests passed 15/15;
  three focused adapter/capability regressions passed 3/3; Ruff and staged
  whitespace checks passed. These ran serially in the transient scope
  documented above. No broad suite, build, profiling run, or background job
  was started. Commit `588ff1c556648f85c27111357488f9a31295e8a1` contains this
  Frontier implementation and its tests. The pre-resumption checkpoint at
  `75e6f2602a33ca7d04ffb507279dd61fd33d7bac` remains available on branch
  `checkpoint/frontier-memory-interruption-20261029-0854`; the probe-data
  directory remains untracked and untouched.
- At 09:05:39, host `MemAvailable` was about 10 GiB and global PSI averages
  were zero. Swap was still fully occupied (4.0/4.0 GiB; about 8.9 MiB free).
  The app slice used about 9.65 GB memory and 2.23 GB swap, with no local
  `MemoryHigh`, `MemoryMax`, or `MemorySwapMax`. Its memory accounting showed
  6.52 GB file cache (5.07 GB inactive), 2.02 GB anonymous memory, and 1.08 GB
  kernel memory (0.93 GB reclaimable slab). These are current cgroup charges,
  not an attribution of the October 28 pressure event. The app-slice
  `oom=19` and `oom_kill=15` counters were unchanged; cgroup high/max and reclaim
  counters are cumulative and likewise do not identify the responsible job.
- A one-shot cgroup/process sample showed `midas-api` near 949 MiB,
  `midas-reality-api` near 337 MiB, `midas-reality` near 441 MiB, and several
  Codex processes between about 333 and 396 MiB RSS. No one sampled process
  accounts for the whole app-slice charge. The exact workload mix, cache
  ownership, and event-time process attribution remain unknown. This supports
  the prior conclusion that user-cgroup pressure and oomd policy are
  demonstrated, while a unique system-wide cause is not.
- `midas-api` and `midas-reality` remained active with restart counts 9 and 14.
  The capacity unit's latest result remained successful; its existing timer was
  active with its next run scheduled for 09:18. The gap-detail unit remained
  failed from its earlier OOM, and its timer was absent from the active timer
  listing. No new oomd or kernel OOM entries appeared after the 08:54 check.
  No protected service was restarted or reconfigured.

**Continuation decision:** Frontier can continue only with short, serial,
offline work under fresh admission checks and the documented transient resource
scope. Full suites, builds, live probes, large replay, profiling, and persistent
workers remain deferred. The quiet interval and successful bounded tests do not
prove host recovery; full swap, 9.65 GB current app-slice charge, unresolved
workload attribution, and archive provenance warnings remain open risks.

## 2026-10-29 09:18 CET — scheduled bounded capacity check

- The existing capacity timer launched `midas-reality-capacity.service` at
  09:18:07. It exited successfully at 09:18:14 (`ExecMainStatus=0`) with a
  recorded 128.9 MiB peak and zero swap, below `MemoryHigh=160M`,
  `MemoryMax=192M`, and `MemorySwapMax=0`. Its 30-minute timer remained active
  with the next run at 09:48:07. The gap-detail timer remained absent from the
  active timer listing.
- The report continues to emit `ARCHIVE_MANIFEST_SIZE_LIMIT`,
  `ARCHIVE_INVENTORY_UNVERIFIED`, and `ARCHIVE_CAPACITY_UNKNOWN`, along with
  budget, retention, and capacity-horizon alerts. This run did not repair,
  rewrite, prune, or otherwise alter archive evidence; archive capacity remains
  unknown.
- At 09:18:54, about 10 GiB RAM was available and global PSI averages were
  zero, but swap remained full at 4/4 GiB. `app.slice` charged about 9.81 GB
  memory and 2.23 GB swap. API and Reality remained active at restart counts
  9/14. No new systemd-oomd entry appeared after the 09:18:17 check. This
  scheduled success verifies the bounded capacity invocation for this run; it
  does not establish host recovery or identify the earlier pressure source.

**Continuation decision:** retain the current 160/192 MiB capacity bound and
30-minute schedule. Frontier may continue with focused serial offline work
after fresh admission. Full suites, builds, live probes, and long replays remain
deferred while swap is exhausted and workload attribution is unresolved.

## 2026-10-29 09:30 CET — high-priority incident revalidation

This pass re-read host PSI, `/proc/meminfo`, `vmstat`, `oomctl`, cgroup files,
user timers, service properties and journals. It made no service, timer, OOM
policy, collector, or data change. Frontier was at `eb929fc` before this
documentation checkpoint; the pre-existing untracked
`data/frontier-public-probes/` remains untouched.

### Root cause boundaries

The evidence separates three mechanisms and scopes:

1. **Confirmed systemd-oomd trigger.** The effective vendor policy for
   `user@1000.service` is `ManagedOOMMemoryPressure=kill` with a 50% limit.
   Current `oomctl` lists `/user.slice/user-1000.slice/user@1000.service` as
   monitored at 50%; it reports a 20-second default duration. October 28 kill
   records explicitly say user-manager pressure exceeded 50% for over 20
   seconds **with reclaim activity**. At 23:43:09 it was 61.64% when Reality
   was killed; at 23:43:24 it was 54.45% when gap-detail was killed. This is
   pressure in the monitored user-manager cgroup, not the same metric as
   global PSI. The lower global PSI sample reported for the incident window
   does not contradict the user cgroup crossing its threshold.
2. **Confirmed recurrent association; initiating workload unknown.** The full
   October 28 OOMD journal contains 129 kills: 106 gap-detail replay, 10
   Reality, 8 API, 4 terminal scopes, and 1 Firefox scope. Gap-detail was an
   auxiliary five-minute finalized-data replay. At its last kill it used
   about 204.8 MiB, below its 256 MiB hard cap, and its local PSI was
   avg10/avg60 76.50%/50.59%. It is the strongest recurring contributor but
   the evidence does not prove it initiated all parent pressure. Candidate
   snapshots also show API, Reality, terminal and other workloads co-resident.
   Their exact causal shares, any leak, and the initial trigger remain
   unproven.
3. **Separate confirmed leaf-cgroup OOM.** Seven kernel
   `CONSTRAINT_MEMCG` OOM events targeted `midas-reality-capacity.service`
   at its old 128 MiB hard limit. Killed Python processes had about 129–131
   MiB anonymous RSS and roughly 11 MiB file RSS. This was a local service
   limit failure, not a host-wide kernel OOM and not an OOMD pressure kill.
   Invalid-manifest archive traversal was a plausible source of high memory,
   not directly measured in the killed runs. The bounded inventory code and
   archive provenance findings remain separate; no manifest or archive data
   was repaired.

Thus the incident does not show that **global** PSI crossed 50%. OOMD acted
on the `user@1000.service` pressure policy. The user-manager and `app.slice`
ancestors remain without `MemoryHigh`, `MemoryMax`, or `MemorySwapMax`. An
aggregate cap there could affect desktop and remote-administration sessions,
so none was introduced. Current OOMD monitor registration is visible; the
earlier `oomctl` samples showing no monitored group remain unexplained.
`oomctl` currently lists no swap-monitored cgroups, and October 28 kill
reasons cite reclaim/pressure rather than a swap-limit action.

### Current host, workloads, and schedules

At 09:27:51 CET, `/proc/meminfo` reported `MemAvailable=10,935,308 kB`
(10.43 GiB), 4,194,300 kB total swap, and 9,188 kB free (about 9 MiB).
Global and user-manager memory PSI avg10/avg60/avg300 were all zero. A
three-interval `vmstat 1 3` sample showed 65/70 kB/s swap-in/out in its first
interval, then zero in the following two. This short sample cannot establish
that swap churn is durably absent. No OOMD or kernel kill appeared after
23:43:24 October 28 and 20:15:44 October 28 respectively.

The user-manager cgroup charged 10.10 GB memory and 2.86 GB swap; its
`memory.stat` was about 2.14 GiB anonymous, 6.19 GiB file, and 1.06 GiB
kernel. `app.slice` charged 9.71 GB memory and 2.23 GB swap, with about 1.90
GiB anonymous, 6.11 GiB file, and 1.02 GiB kernel. These are cgroup charges
including file cache, not process RSS or a direct estimate of unreclaimable
memory. Both aggregate cgroups remain uncapped. Descendant counters stayed
at `oom=19`, `oom_kill=15`, `oom_group_kill=0`.

The largest current app leaf was one GNOME Terminal VTE scope at 2,092 MiB
current: about 565 MiB anonymous, 1,495 MiB file, and 31 MiB kernel. It was
left running. Other notable leaf charges were API 961 MiB (118 MiB anonymous,
835 MiB file), Reality 459 MiB (247 MiB anonymous, 202 MiB file), and Reality
API 349 MiB (96 MiB anonymous, 242 MiB file). These point-in-time charges do
not identify the October 28 pressure initiator. The process sample showed
Codex processes below 400 MiB RSS each; no terminal, browser, desktop, or
remote-session process was signalled or limited.

At 09:29, MIDAS API, Reality recorder, and Reality API were active with
restart counts 9/14/0 and effective limits of 1536/1792 MiB, 1152/1280 MiB,
and 512 MiB respectively, all with zero swap allowance. The API health route
returned `READY`, release `a152999`, and `live_execution=false`. Reality's
status file, modified at 09:29:07, reported `RECORDING_UNSEQUENCED`,
`active_receiving`, 16/16 fresh books, zero process backpressure, one recorded
failure, and `sequence_verified=false`; it also retains a timeout/staleness
error. This confirms active receiving at that time, not sequenced completeness
or archive integrity. Continental tailnet/identity and production web units,
Echo production/staging, RustDesk, Tailscale/Headscale, and `ssh.socket` were
active; none was changed. An unrelated Daymark database unit has been failed
and disabled since October 9; the read-only Continental infrastructure audit
also has a failed result. Neither appears in the OOMD/kernel kill records.

The gap-detail timer remains `inactive` and `disabled`, with its service's
last result `oom-kill`; it is absent from the active timer list. The capacity
timer is active on its 30-minute schedule. Its 09:18 run exited 0 at 128.9
MiB peak and zero swap under `MemoryHigh=160M`, `MemoryMax=192M`, and
`MemorySwapMax=0`; archive inventory/provenance warnings and unknown capacity
remain. The one-minute Arena schedule dispatcher completed in about 33 ms
CPU. Other scheduled Veritas work has 256 MiB observation/source-analysis
caps and a 512 MiB director cap. Runs were staggered in the sampled window:
observation 09:02, source analysis 09:11, director 09:15, and capacity 09:18.
No overlapping heavy scheduled job was observed in this window; this does not
guarantee non-overlap at all times.

### Changes, rollback, and safe continuation

No new host configuration change was warranted by this revalidation. The two
targeted reversible actions remain in effect, with exact rollback commands in
“Actions in effect and rollback” above:

- Keep the auxiliary gap-detail timer disabled; only re-enable after explicit
  resource admission and a bounded replay implementation.
- Keep the capacity monitor at 160 MiB High / 192 MiB Max / zero swap. Its
  rollback restores the former 128 MiB hard cap and is not recommended without
  a replacement bound because that setting produced seven leaf OOM kills.

Do not change global OOMD policy, swap configuration, user-manager limits, or
protected collector settings based on this evidence. Do not clear swap or stop
active terminal/session processes. Current measurements support **careful
resumption** of Frontier source-independent work only: one job at a time, with
fresh admission and a transient 384 MiB High / 512 MiB Max, zero-swap, 20% CPU,
64-task, short-timeout scope. Defer full suites, UI builds, live probes, large
replay, profiling, and persistent workers while swap is effectively full.
Stop on rising PSI, changed OOM counters, any new OOM entry, low API/Reality
headroom, or a scheduled workload overlap.

**Incident disposition:** **PARTIALLY CONTAINED / PARTIALLY VERIFIED, not
resolved.** The recurring auxiliary replay and the capacity checker's proven
128 MiB cap mismatch have targeted containment. Services and PSI are stable
in this short sample, but swap remains full, the parent user cgroup is uncapped,
the historic pressure initiator is not proven, and long-duration no-kill
validation remains outstanding.

## 2026-10-29 09:49 CET — Frontier validation admission follow-up

The two focused Kraken stored-frame replay API tests passed **2/2 in 4.91 s**
under a transient `MemoryHigh=384M`, `MemoryMax=512M`, zero-swap, 20%-CPU,
64-task, 60-second scope. The existing Starlette/httpx deprecation warning
appeared. The replay UI test passed **7/7 in 7.10 s** under the same bounds
after correcting an assertion for the added acknowledgement frame. Ruff lint
passed; Ruff formatting and Prettier were applied to the changed files.

TypeScript verification did not complete. The full-app check first exited on
Node's default heap limit after about 65 seconds inside a 512 MiB max scope.
A retry with a 320 MiB Node heap reached its 90-second runtime bound (scope
peak 364.9 MiB, zero swap). A narrower check of `Frontier.tsx` and the replay
panel was then configured with `MemoryHigh=256M` / `MemoryMax=384M`; it reached
272.1 MiB and was stopped at 49.7 seconds when host PSI rose to
`some=26.48%` / `full=24.51%` avg10. User-manager `memory.events.high` increased
from 16,422,194 to 16,424,562 across that interval. This likely contributed to
the transient reclaim pressure because the check exceeded its own soft bound,
but does not establish it as the sole cause of that host PSI sample or explain
the October 28 incident. Aggregate `oom=19`, `oom_kill=15`, and
`oom_group_kill=0` counters did not change. No further compiler, build, or test
job was started.

The scheduled Reality capacity monitor then completed at 09:48:30 with
`Result=success`, `MemoryPeak=148,496,384` bytes, `MemoryHigh=160M`,
`MemoryMax=192M`, and zero swap. At 09:49:49, `MemAvailable` was
11,442,974,720 bytes (10.66 GiB), `SwapFree` 9,572,352 bytes (9.13 MiB), and
host PSI avg10 was zero; avg60/avg300 `some` were 1.22%/1.25% and `full`
1.10%/1.12%, declining from the compiler interval. Aggregate user-manager
counters were `high=16,424,562`, `max=730,045`, `oom=19`, and `oom_kill=15`.
The API, Reality recorder, and Reality API were active with restart counts
9/14/0; no systemd-oomd or kernel OOM journal entry appeared after 09:30.
These measurements do not establish sustained recovery. Swap remains nearly
full, and the compiler attempt demonstrates that even source-independent work
can cause reclaim if its soft cgroup bound is set below its actual working
set.

The current Frontier implementation checkpoint is commit `00efbf1`
(`feat(frontier): replay stored Kraken book captures`). It adds bounded,
offline reconstruction from hash-bound persisted Kraken frames and a UI replay
control; it does not open a source connection. The focused Python and UI tests
passed, while TypeScript checking remains **unverified**. No production service
or historical evidence was changed. Keep the incident **PARTIALLY CONTAINED /
PARTIALLY VERIFIED** and limit further work to a single offline job only after
fresh admission, using a soft limit above the measured working set; stop if PSI
rises or counters change.

## 2026-10-29 10:06 CET — bounded-work validation follow-up

The Frontier Gemini adapter work resumed only after a fresh host/timer check.
Its offline Gemini plus shared-trade-contract slice passed **8/8 in 2.51 s**
under a transient 384 MiB `MemoryHigh`, 512 MiB `MemoryMax`, zero-swap,
20%-CPU, 64-task, 60-second service. A concurrent cgroup sample during the
successful run measured 47,181,824 bytes current/peak and zero swap. No live
exchange request, broad test suite, build, or persistent job ran. No system
configuration or protected service was changed.

At 10:06:35, `MemAvailable` was 11,346,505,728 bytes (10.57 GiB), while only
9,625,600 bytes (9.18 MiB) of the 4 GiB swap device was free. Global memory
PSI `some` and `full` avg10/avg60/avg300 were zero. The user manager still
charged 10,189,189,120 bytes memory, had a 13,992,292,352-byte lifetime peak,
and held 2,858,139,648 bytes in swap. Its `high=16,424,562`, `max=730,045`,
`oom=19`, `oom_kill=15`, and `oom_group_kill=0` counters were unchanged. No
kernel or systemd-oomd kill entry appeared in the preceding 20 minutes.
`midas-api`, Reality, and Reality API remained active at restart counts 9/14/0;
Echo archive/staging, RustDesk, `ssh.socket`, and systemd-oomd were active.

This small, quiet observation window supports continuing one bounded offline
Frontier task after fresh admission. It does not establish lasting host
recovery or identify the original aggregate pressure source. Swap remains
nearly exhausted and the user-manager cgroup remains large. The auxiliary
gap-detail replay timer remains disabled, Reality capacity remains bounded at
160/192 MiB with zero swap, and archive provenance/inventory warnings remain
untouched. **Incident status remains PARTIALLY CONTAINED / PARTIALLY VERIFIED.**

## 2026-10-29 10:10 CET — final bounded-work and scheduled-job follow-up

After clarifying Gemini's fail-closed handling of a page containing any
broken print, the focused Gemini and shared five-venue trade tests passed
**8/8 in 2.51 s** under the same zero-swap 384/512 MiB cgroup caps, 20% CPU,
64 tasks, and 60-second timeout. The transient unit reported a 45.2 MiB peak
and zero swap. Ruff check and format checks passed. Tests used synthetic
fixtures only; the source-use hold remains in force. No host setting, timer,
or protected service was changed.

The 10:10:37 Veritas source-analysis timer ran and the service was inactive by
10:10:54; PSI remained zero and user-manager OOM counters were unchanged.
At 10:10:57, `MemAvailable` was 11,317,956,608 bytes (10.54 GiB), while only
9,629,696 bytes (9.19 MiB) of swap was free. The user manager charged
10,198,982,656 bytes memory and 2,858,139,648 bytes swap, with a
13,992,292,352-byte lifetime peak. Event counters remained
`high=16,424,562`, `max=730,045`, `oom=19`, and `oom_kill=15`; no kernel or
systemd-oomd kill entry appeared in the previous 25 minutes. API/Reality/
Reality API stayed active at restart counts 9/14/0.

This confirms only a short bounded validation interval. Near-full swap,
substantial user-manager charge, unresolved historic aggregate pressure
attribution, and the lack of long-duration observation continue to block a
resolved disposition. The incident remains **PARTIALLY CONTAINED / PARTIALLY
VERIFIED**; Frontier may continue only serial, offline, resource-capped work
after a fresh admission check.

## 2026-10-29 10:13 CET — API and collector boundary regression

Four focused regressions covering Gemini's non-clearable probe hold, held
collector config persistence, pre-journal/pre-request rejection, and
capability-manifest resume rejection passed **4/4 in 9.00 s**. The transient
service peaked at 57.5 MiB, used zero swap, and remained within 384 MiB high /
512 MiB max, 20% CPU, 64 tasks, and 60 seconds. The only warning was the
existing Starlette/httpx deprecation notice. At 10:13:28, host PSI was zero,
`MemAvailable` was 11,310,669,824 bytes, and 9,633,792 bytes of swap was free.
OOM counters stayed at 19/15/0; no kernel or systemd-oomd kill appeared in
the prior 30 minutes. API, Reality, and Reality API remained active at
restart counts 9/14/0. The test used temporary local state and made no
external request or configuration change. The next scheduled Continental
audit was due at 10:13:54; wait for it to complete before further work.

The scheduled Continental audit completed at 10:14:05 with `Result=exit-code`
and reported 72 pass, 19 warnings, 3 failures, and 3 unknowns. Its failures
were the previously recorded unexpected non-loopback listeners on
`0.0.0.0:8081` and `0.0.0.0:5174`, plus the disabled Echo offsite schedule.
It consumed 1.526 CPU seconds; memory PSI was zero and the user-manager OOM
counters did not change. This read-only audit result is separate from the
memory incident. Continental, Echo, remote-access, and protected MIDAS
services were not changed.

## 2026-10-29 10:19 CET — capacity run and offline fixture follow-up

The scheduled Reality capacity monitor completed at 10:18:29 with
`Result=success`, 135,696,384 bytes (129.4 MiB) peak under
`MemoryHigh=160M`, `MemoryMax=192M`, and zero swap. It still reports
`ARCHIVE_CAPACITY_UNKNOWN` and archive inventory/provenance limitations; no
historical evidence or recorder state was altered.

After the capacity run, the Gemini parser suite passed **8/8 in 2.10 s**,
including malformed duplicate/order/limit cases, in a separate zero-swap
384/512 MiB transient unit with a 42.2 MiB peak. The default-registry idle
test passed **1/1 in 3.70 s** at 49.3 MiB peak. A stale expectation that only
Polymarket declares `BOOK_UPDATES` was corrected to also include Kraken's
existing declared implementation. Tests caused no observed PSI or OOM-event
change and made no external request.

At 10:19:35, `MemAvailable` was 11,306,885,120 bytes (10.54 GiB), but only
9,637,888 bytes (9.19 MiB) of swap was free. Global PSI remained zero. The
user manager charged 10,237,464,576 bytes current memory and 2,858,139,648
bytes swap, with a 13,992,292,352-byte peak. `oom=19`, `oom_kill=15`, and
`oom_group_kill=0` remained unchanged; no kernel/systemd-oomd kill appeared
in the previous 40 minutes. API/Reality/Reality API stayed active at restart
counts 9/14/0. This bounded interval permits only continued serial work; it
does not resolve the incident or validate archive provenance.

## 2026-10-29 10:25 CET — host recheck and Frontier timestamp correction

The Gemini List Trades parser was corrected after the official documentation
example showed a whole-second `timestamp` alongside subsecond
`timestampms`. Mixed-unit fields now have to agree at whole-second precision,
same-unit fields must match exactly, and `timestampms` is preferred. Its
focused parser plus shared adapter contract tests passed 9/9 in 2.51 seconds;
the run was fixture-only, peaked at 42.1 MiB, used zero swap, and made no
external request. Gemini remains under the non-clearable source-use hold.

At 10:25:09, host `MemAvailable` was 11,197,222,912 bytes (10.43 GiB), while
only 9,641,984 bytes (9.20 MiB) of swap was free. Host memory PSI was zero.
The user manager charged 10,253,131,776 bytes memory and 2,858,139,648 bytes
swap, with lifetime peak 13,992,292,352 bytes. Its counters remained
`high=16,424,562`, `max=730,045`, `oom=19`, `oom_kill=15`, and
`oom_group_kill=0`. Read-only journal queries found no matching kernel,
systemd-oomd, API, Reality, or gap-detail kill entries since 10:00. API,
Reality, and Reality API were active/running with restart counts 9/14/0. The
gap-detail service still reports its prior `oom-kill` result, but its timer is
inactive and no restart was requested. No service configuration changed.

This recheck is another short quiet interval, not a resolution. Swap remains
near exhaustion, the user-manager charge remains substantial, historical
pressure initiation is not fully attributed, and archive inventory/provenance
remains unresolved. Continue only serial, offline, resource-capped Frontier
work after fresh admission; do not run broad suites or live source probes.

## 2026-10-29 10:33 CET — bounded persistence regression and host recheck

The five-venue trade adapter contract test was extended to carry Gemini's
documented mixed-precision timestamp through normalization and
hash-pinned `FrontierStore` append/readback. It passed **1/1 in 2.31 seconds**
in a transient scope capped at 384 MiB high, 512 MiB max, zero swap, 20% CPU,
64 tasks, and 60 seconds. After commit `cd20960`, the test was rerun and
passed **1/1 in 2.30 seconds**. Its wrapper sampled the live cgroup before it
exited: peak `memory.peak` was 52,412,416 bytes, with zero high/max/OOM events
and zero swap. Targeted Ruff check and format check also passed in a separate
bounded unit at an 8,695,808-byte peak. systemd's post-cleanup `MemoryPeak`
summary reported only 256 KiB for the pytest unit and is not used as the peak;
the in-unit cgroup sample is the recorded measurement. Fixture transports
only; no endpoint, source-use hold, captured probe, or protected service was
accessed or changed.

At 10:33:26, `MemAvailable` was 11,243,335,680 bytes (10.47 GiB),
`SwapFree` was 9,666,560 bytes (9.22 MiB), and global memory PSI averages
were zero. User-manager counters remained `high=16,424,562`, `max=730,045`,
`oom=19`, and `oom_kill=15`; API, Reality, and Reality API remained active
with restart counts 9/14/0. The gap-detail timer remained inactive.

The scheduled 10:29:08 Continental audit separately exited 1 after 1.443
CPU seconds with the same 72 pass / 19 warn / 3 fail / 3 unknown result. Its
failures were non-loopback listeners on `0.0.0.0:8081` and `0.0.0.0:5174`
and the disabled Echo offsite schedule. No related services/configuration were
changed; this is separate from memory-pressure evidence.

The short test did not change cgroup OOM counters or PSI, but swap remains
near exhaustion and no long-duration stability evidence exists. Host status
remains **PARTIALLY CONTAINED / PARTIALLY VERIFIED**; continue only serial,
offline, resource-capped Frontier work after a fresh admission check.

## 2026-10-29 10:51 CET — priority incident recheck

### Current trigger and attribution limits

The active systemd-oomd policy is confirmed in the vendor drop-in
`/usr/lib/systemd/system/user@.service.d/10-oomd-user-service-defaults.conf`:
`ManagedOOMMemoryPressure=kill` and a 50% user-manager memory-pressure limit.
The applicable pressure duration is 20 seconds. `user.slice`,
`user-1000.slice`, and `user@1000.service` have no `MemoryHigh`, `MemoryMax`,
or `MemorySwapMax` ceiling. This explains the recorded systemd-oomd action:
the parent user manager crossed its PSI threshold with reclaim activity, and
oomd selected eligible descendant cgroups. The kernel journal has seven
separate `CONSTRAINT_MEMCG` capacity-checker kills and no system-wide kernel
OOM record in the searched interval.

At 10:51, `oomctl dump` showed `/user.slice/user-1000.slice/user@1000.service`
as the memory-pressure-monitored cgroup at 50%; its current pressure averages
were zero. The same output showed a 90% swap-used limit but no swap-monitored
cgroups. This differs from the 10:33 capture that showed no monitored cgroup.
Neither `systemd-oomd` nor `user@1000.service` had restarted, and no policy
change was observed between samples; the reporting discrepancy remains
unexplained. The October 28 kill records themselves cite memory PSI, not a
swap-used threshold.

The evidence does not identify one primary host-wide workload. October 28's
129 oomd victims comprised 106 gap-detail replay kills, 10 Reality recorder
kills, 8 MIDAS API kills, 4 GNOME Terminal scopes, and 1 Firefox scope. The
gap-detail job is a strong recurring load contributor: its own cgroup had
about 205 MiB current use and 50–77% PSI around the final kills. The frequency
and victim counts do not prove it was the sole or initiating cause. The 10:44
occupancy sample identifies additional candidates, not historic causation:
the GNOME Terminal slice was at about 4.5 GiB memory / 1.53 GiB swap with an
8.79 GiB lifetime peak; the API cgroup was at 0.98 / 1.50 GiB (High 1.50,
Max 1.75), and Reality at 0.50 / 1.13 GiB (High 1.125, Max 1.25). The largest
terminal scope was 2.14 GiB, mostly charged file cache, with zero current PSI.
The user manager's 10:44 memory.stat was file/cache-heavy (about 6.4 GB file,
4.9 GB inactive file, 2.2 GB anonymous, and 1.1 GB kernel); host
`MemAvailable` remained high. These facts do not establish that the terminal
scope or any one MIDAS service initiated the historical pressure.

The current service cgroups also show different local-limit signals: API had
11,692 `memory.events high` increments and no `max` events; Reality had
33,176 `high` and no `max`; Reality API was at 0.38 / 0.50 GiB against its
512 MiB hard cap, with 5,030 `max` events but no OOM events. These counters
are cumulative cgroup events, not kill counts. They warrant continued
monitoring; no critical service limit was changed in response.

### Fresh state and workload review

At 10:51:03 CET the host had 16,665,567,232 bytes RAM, 11,416,158,208 bytes
available (10.63 GiB), and zero memory PSI. Swap had only 9,805,824 bytes
free (9.35 MiB). `vmstat` showed no continuing swap-in or swap-out after its
first sample. User-manager event counters remained `oom=19`, `oom_kill=15`,
and `oom_group_kill=0`. No systemd-oomd or kernel kill had appeared since
23:43:24 on October 28, about 11 hours earlier. This is a quiet interval, not
durable recovery evidence.

Reality, MIDAS API, and Reality API were active with restart counts 14/9/0;
RustDesk, Caddy, Echo production and staging, and the Continental services
observed here remained active. No user-systemd jobs were running at the
sample. Scheduled work observed during this recheck was staggered and short:
the Veritas observatory took about 12 seconds (1.73 CPU seconds), source
analysis 10 seconds (8.90 CPU seconds), and the research director 2 seconds
(1.33 CPU seconds). Arena's minute dispatcher returned an empty schedule in
about 0.03 CPU seconds. The capacity monitor completed its 10:48:30 run with
exit status 0 in 7 seconds (6.40 CPU seconds). This establishes no overlap in
the observed window; it does not rule out overlap at other times.

The capacity monitor's already-installed drop-in remains
`/home/charlie/.config/systemd/user/midas-reality-capacity.service.d/90-frontier-memory-bound.conf`
with `MemoryHigh=160M`, `MemoryMax=192M`, and `MemorySwapMax=0`. Its 10:18
run peaked at 135,696,384 bytes (129.4 MiB) and succeeded; the 10:48 run also
exited successfully. The latest output still reports
`ARCHIVE_MANIFEST_SIZE_LIMIT`, `ARCHIVE_INVENTORY_UNVERIFIED`, and
`ARCHIVE_CAPACITY_UNKNOWN`, alongside existing capacity warnings. No archive
manifest, inventory, or historical evidence was modified. These integrity
warnings remain a separate unresolved issue.

The Frontier UI integration test had two bounded timeouts at 10:37 and 10:42.
Their cgroup peaks were 382,668,800 and 362,721,280 bytes, with zero cgroup
high/max/OOM events and zero swap. They were not evidence of a memory kill,
but the repeated slow test is deferred. Both test units were complete and no
Frontier test or service job was active at the 10:51 sample; active interactive
sessions were left intact and not attributed to a project. The separate 08:20
analytics test failure peaked at 41,836,544 bytes. No new test, batch, or live
source request was started for this incident review. The scheduled Veritas
public-observation pilot ran before this interruption at 10:31; it was not
started by this review.

The 10:45 Continental read-only audit exited 1 with 72 pass, 19 warn, 3 fail,
and 3 unknown. Its three existing findings concern listeners on
`0.0.0.0:8081` and `0.0.0.0:5174` and the disabled Echo offsite schedule. No
Continental, Echo, SSH, RustDesk, Reality, or MIDAS service configuration was
changed here.

### Actions, rollback, and continuation

No additional host configuration was changed during this recheck. The
five-minute gap-detail timer was already stopped at 23:46:27 on October 28
and remains `inactive`/`disabled`; its unit performs finalized replay, not
live capture or archive-integrity repair. When a separately reviewed
resource-safe replay is desired, its previous schedule can be restored with
`systemctl --user enable --now midas-veritas-gap-detail-v2.timer`. Do not
restore it while its batch admission and five-minute cadence remain
unreviewed. The capacity drop-in is also pre-existing and remains in force;
removing it would restore the known-failing 128 MiB base limit, so no rollback
is recommended during this incident. No oomd policy, swap setting, protected
service limit, service state, or access path was changed.

Before investigation edits, the isolated Frontier tree was checkpointed at
HEAD `e1a82c620221578822c0b90ea5c270e87aefc8a9`. The tracked UI diff is
recoverable from
`/home/charlie/frontier-checkpoints/frontier-before-memory-incident-20261029T104431+0100.patch`
(SHA-256 `923cf479e583fbd2d5ca8a8a2b85ed8201bce7779e6bd1d9de4361335f3e64f1`).
The existing `data/frontier-public-probes/` directory was left untouched.

**Disposition:** partially contained and partially verified. No new instance
of either previously observed failure pattern was recorded through this
sample while the timer pause and capacity bound were in effect; this is not
long-run proof of recovery. Continue only serial, offline, bounded Frontier
work after a fresh admission check (zero-swap transient scope, finite
memory/CPU/task/time limits). Defer broad
frontend tests, builds, parallel analysis, and any new live-source polling.
Do not change the user-manager oomd policy, protected service limits, swap, or
archive provenance without a separately justified and reviewed change.

## 2026-10-29 10:57 CET — bounded Frontier continuation

After a fresh admission sample at 10:56:35 (10.52 GiB available, zero memory
PSI, 9.35 MiB free swap, no active systemd job), Frontier resumed with one
small, offline UI utility check. The trade-time formatting function was
isolated in `apps/web/src/frontierTime.ts`; its focused Vitest file now covers
microsecond-preserving UTC output, offset-to-UTC conversion, and missing or
invalid timestamps. The test passed **3/3** in 3.90 seconds. Prettier check
passed for the four touched UI/test files. Code commit: `46a09f9`.

An initial filter attempt used `.test.ts`, which the repository's Vitest
configuration excludes (`src/**/*.test.tsx` only); it discovered no tests and
is not counted as validation. That attempt peaked at 117,239,808 bytes with
zero cgroup events and zero swap. After renaming to `.test.tsx`, the successful
run used a transient scope with `MemoryHigh=384M`, `MemoryMax=512M`,
`MemorySwapMax=0`, `CPUQuota=25%`, `TasksMax=64`, and a 60-second runtime cap.
The in-unit peak was 120,201,216 bytes; cgroup high/max/OOM counters and swap
were all zero; CPU time was 5.022 seconds. The earlier full component render
still timed out twice and remains deferred; the added rendered-table
assertions are not represented as integration-tested.

At 10:57:18 after the run, `MemAvailable` was 11,172,644 kB (10.65 GiB),
memory PSI remained zero, `SwapFree` remained 9,576 kB (9.35 MiB), user
manager `oom/oom_kill/oom_group_kill` stayed 19/15/0, and no oomd or kernel
kill appeared since 23:43:24 on October 28. API, Reality, and Reality API
remained active at restart counts 9/14/0. This is evidence the bounded check
fit within the host envelope; it does not clear the underlying incident.

**Continuation gate:** Frontier may continue only serial, offline, fixture-
based work after a fresh admission sample, within zero-swap cgroup limits and
finite CPU, memory, tasks, and runtime. Full frontend tests/builds, parallel
analysis, and new live-source polling remain deferred. Incident status stays
**PARTIALLY CONTAINED / PARTIALLY VERIFIED**.

## 2026-10-29 11:13 CET — bounded Frontier resumption

A fresh 11:05:26 admission sample showed 10.57 GiB MemAvailable, zero PSI, about
9.4 MiB free swap, no active systemd jobs, and unchanged user-manager OOM
counters 19/15/0. Frontier resumed only with isolated offline UI verification.
Commit f874cf0 extracts the Kalshi fee/sensitivity panel into its own component.
No public request, service operation, data-directory read, or host configuration
change accompanied it.

The focused UI suite passed 3/3 after explicit test cleanup was added. Its
transient cgroup was bounded to 384 MiB high / 512 MiB max, zero swap, 20% CPU,
64 tasks, and 60 seconds; the in-unit peak was 138,158,080 bytes with no
high/max/OOM event. Targeted ESLint and Prettier passed. The first test attempt
had two failures caused by retained DOM between cases and was corrected before
the successful rerun.

Two TypeScript build attempts did not produce diagnostics. The first reached its
60-second runtime cap at a 315,731,968-byte cgroup peak. The second exited with
Node's V8 heap exhausted near 251 MiB old-space after 50.1 seconds; cgroup peak
was 315,351,040 bytes. Both runs used zero swap and recorded no cgroup
high/max/OOM event. This was a Node process heap limit, not a host memcg OOM.
The exact-tree typecheck therefore remains unverified; no further TypeScript
retry or broad UI build was run.

At 11:11:53, MemAvailable was 10.54 GiB, SwapFree 10.1 MiB, and global memory
PSI was zero; user-manager OOM counters remained 19/15/0. API, Reality, Reality
API, Continental contact/status sites, Echo production/staging services, and
RustDesk were active. The scheduled Veritas source-analysis unit completed
successfully. No kernel or systemd-oomd kill was found in the journal interval
checked after 11:05. The quiet interval is short and swap remains nearly full.

The existing mitigations remain unchanged: the auxiliary gap-detail timer is
inactive/disabled, and the Reality capacity service is bounded at 160 MiB high /
192 MiB max / zero swap with its timer enabled. No protected service, timer,
archive, historical record, or service configuration was changed. Host status
remains **PARTIALLY CONTAINED / PARTIALLY VERIFIED**. Safe continuation is
limited to serial, offline, fixture-based tasks under fresh admission and finite
zero-swap cgroup bounds; historical pressure attribution and durable recovery
remain unresolved.


## 2026-10-29 11:16 CET — post-commit observation

At 11:16:11, MemAvailable was 10.53 GiB, SwapFree 10.1 MiB, global memory PSI
was zero, and user-manager OOM counters remained 19/15/0. API, Reality, and
Reality API were active at restart counts 9/14/0. Continental contact/status,
Echo production/staging, and RustDesk were active. The 11:15 Veritas research-
director unit exited successfully. No systemd-oomd or kernel kill appeared in
the checked interval after 11:05. There were no active systemd jobs at 11:16:25.
This quiet interval includes the bounded offline test and compiler attempts but
does not establish sustained recovery; swap remains nearly full and historical
pressure attribution is unresolved.


## 2026-10-29 11:22 CET — bounded typecheck and production build

At 11:21:15, a fresh admission sample showed 10.62 GiB MemAvailable, zero PSI,
about 10.1 MiB free swap, no active systemd jobs, and unchanged user-manager OOM
counters 19/15/0. The current Frontier tree then passed tsc -b with an explicit
384 MiB Node heap. Its transient cgroup was limited to 512 MiB high / 640 MiB
max, zero swap, 25% CPU, 64 tasks, and 120 seconds; the run took 76.833 seconds,
peaked at 402,681,856 bytes, and recorded no cgroup events or swap.

A Vite production build transformed 2,233 modules and succeeded in 55.28
seconds, writing 16 files totaling 1.5 MiB to this temporary output directory:

`/tmp/midas-frontier-build-20261029T1121Z`

Its cgroup was limited to 640 MiB high / 768 MiB max, zero swap, 25% CPU, 64
tasks, and 120 seconds. The in-unit peak was 609,099,776 bytes with zero
cgroup events and swap. Vite retained its 544.51 kB Chart chunk advisory and
noted that the new external output directory would not be automatically
emptied.

At 11:22:29, MemAvailable was 10.66 GiB, SwapFree 10.2 MiB, PSI was zero, and
OOM counters remained 19/15/0. API/Reality/Reality API remained active at
restart counts 9/14/0; no kernel or systemd-oomd kill appeared after 11:19. The
build and compiler did not contact an exchange, change a service, or write into
the repository's dist directory. The short quiet window does not resolve nearly
full swap or historical workload attribution.


## 2026-10-29 11:30 CET — bounded browser validation and task-limit diagnosis

The first fixture-only overview browser attempt failed before the test body
when headless Chromium crashed; its unit peaked at 527,007,744 bytes, used zero
swap, and recorded no memory cgroup OOM event. The kernel recorded a Chromium
`int3` trap. A minimal diagnostic then exited successfully after Chromium
launched, created a page, and closed it.

A bounded E2E retry with `TasksMax=96` failed at browser launch with
`pthread_create: Resource temporarily unavailable`. The kernel explicitly
recorded `fork rejected by pids controller` against that temporary E2E unit.
Host-wide task headroom was ample: the user slice had 899 tasks against a
37,082 limit, with a per-user process limit of 56,186. This was the test unit's
own task ceiling, not evidence of host PID exhaustion. With only that unit's
limit raised to 256, Chromium reached the page; the test then exposed a
five-second assertion timeout while React was still loading the lazy Frontier
workspace. The E2E now grants 20 seconds for that route and 60 seconds for the
single journey.

The targeted overview E2E passed 1/1 in 15.3 seconds (38.9 seconds total unit
runtime). Its temporary unit used MemoryHigh=768 MiB, MemoryMax=1 GiB,
MemorySwapMax=0, CPUQuota=25%, TasksMax=256, and RuntimeMaxSec=180s. The unit's
memory peak was 723,308,544 bytes; swap and memory cgroup events were zero.
Peak tasks were 113 and the pids controller recorded no limit event. The
browser verified that this fixture-only flow made no source-probe or collection
request.

At 11:30:05, MemAvailable was 11,235,135,488 bytes (10.47 GiB), memory PSI was
zero, SwapFree was 12,263,424 bytes (11.7 MiB), and the user slice had 899 of
37,082 tasks. API, Reality, and Reality API remained active at restart counts
9/14/0. User-manager OOM counters remained 19/15/0; no kernel or systemd-oomd
kill appeared in the checked journal after 11:18. This brief quiet interval
does not establish durable recovery. Swap remains nearly full and historical
pressure attribution remains unresolved.

At 11:31:43, the scheduled Veritas observatory unit exited successfully and no
user jobs remained. MemAvailable was 11,431,862,272 bytes (10.65 GiB), memory
PSI was zero, and SwapFree was 12,595,200 bytes (12.0 MiB). At 11:31:53, the
user-manager counters remained 19/15/0, API/Reality/Reality API remained active
at restarts 9/14/0, and no kernel or systemd-oomd kill appeared in the checked
journal after 11:18. This is a short post-run observation, not evidence of
durable recovery.


## 2026-10-29 11:34 CET — saved-sample replay and post-run host check

The fixture-backed saved Polymarket sample replay browser case passed **1/1 in
18.9 seconds** (37.1 seconds total unit runtime). Its intercepted test
responses and isolated demo API did not contact a live exchange. It verifies
that saved sample capture and replay occur only after explicit user actions.
The transient unit used MemoryHigh=768 MiB, MemoryMax=1 GiB, MemorySwapMax=0,
CPUQuota=25%, TasksMax=256, and RuntimeMaxSec=180s. Its memory peak was
701,476,864 bytes; swap and memory high/max/OOM events were zero. Peak tasks
were 111 with no pids limit event.

At 11:34:46, MemAvailable was 11,109,826,560 bytes (10.35 GiB), memory PSI
was zero, SwapFree was 12,607,488 bytes (12.0 MiB), and user-manager OOM
counters remained 19/15/0. API/Reality/Reality API remained active at restart
counts 9/14/0. The gap-detail timer remained inactive and the Reality capacity
timer active; no user jobs remained. No kernel or systemd-oomd kill appeared
in the checked journal after 11:18. This short interval supports only
continued bounded work and does not establish durable recovery.

## Frontier captured-store migration follow-up — 2026-10-29 11:42–11:47 CET

A bounded captured-data browser run exposed an API startup compatibility gap:
the isolated captured Frontier database used schema 7 while the current code
expects schema 8. The first run reached the UI but emitted repeated API errors
when readiness queried the old schema. The original captured database was
copied to a temporary test root; its source evidence was not migrated or
modified.

Commit `a05f025` adds startup migration for an existing Frontier store before
the API starts serving its Frontier router. Missing databases are not created
as a side effect. A migration error is logged, visible in `/api/health` as a
degraded Frontier store, and does not prevent the broader API from starting.
The migration runs in a worker thread. This is a code change in the isolated
Frontier branch only; no production process was restarted and the fix has not
been deployed.

After the change, the captured browser case passed **1/1 in 14.6 seconds**
(32.3 seconds total unit runtime). Its scope used MemoryHigh=768 MiB,
MemoryMax=1 GiB, MemorySwapMax=0, CPUQuota=25%, TasksMax=256, and
RuntimeMaxSec=180s. Peak memory was 693,190,656 bytes; swap, memory events,
and pids-limit events were zero, with 111 peak tasks. The copied temporary
database was schema 8 with 3 observations, 10 relationships, and graph
revision `(2, 10, 0)`. This is fixture/captured-data evidence, not a live
exchange validation.

Two startup migration cases and the existing graph revision migration case
passed **3/3 in 11.41 seconds** under a 640 MiB max, zero-swap, 20%-CPU,
64-task, 90-second scope. The added failure-path case verifies a symlinked
database is rejected without changing its target, the Frontier readiness
surface returns 503, and `/api/health` remains available with degraded status.
Ruff check and format checks passed for the changed Python files. The tests
emitted one existing Starlette/httpx TestClient deprecation warning.

At 11:47:14, host `MemAvailable` was 11.48 GB (10.69 GiB), memory PSI was
zero, and `SwapFree` was 12.75 MB (12.2 MiB). User-manager counters remained
`oom=19` and `oom_kill=15`; the checked kernel and systemd-oomd journals had
no matching kill entries after 11:18. API, Reality, and Reality API remained
active at restart counts 9/14/0. Continental contact/status, Continental
tailnet/auth, Echo production/staging, and RustDesk were active. The
gap-detail timer remained inactive and the capacity timer waiting. No jobs
were active. This quiet sample does not resolve the nearly full swap or
historical pressure attribution.

The Reality API cgroup remained near its 512 MiB hard limit at the 11:46
sample: 438,611,968 bytes current, 536,870,912 bytes peak, `max=5030`, and
`oom=0`/`oom_kill=0`, with zero current local PSI. About 324 MB was accounted
as file cache and 99 MB as anonymous memory. The cumulative `max` count means
allocation attempts reached this cgroup's hard limit; `oom=0` records no
memcg OOM at this sample. Neither value establishes a host-pressure cause.
No limit change was made. Incident status remains **PARTIALLY CONTAINED /
PARTIALLY VERIFIED**; Frontier may continue only as serial, bounded, offline
work with a fresh resource admission check.

## Current workload attribution sample — 2026-10-29 11:49 CET

A fresh read-only sample showed 11.44 GB (10.66 GiB) `MemAvailable`, zero
host PSI, and 12.78 MB (12.2 MiB) `SwapFree`. The uncapped user-manager
cgroup charged 10,118,754,304 bytes (9.42 GiB) of memory and
2,857,951,232 bytes (2.66 GiB) of swap. Its `memory.stat` attributed about
2.33 GB to anonymous pages, 6.63 GB to file cache, and 1.14 GB to kernel
memory. OOM counters remained 19/15/0; no jobs were active.

The largest current leaf under that user manager was a GNOME Terminal VTE
scope charged 2,354,704,384 bytes (2.19 GiB): 598 MB anonymous memory and
1.72 GB file cache, no swap, zero current PSI, and zero local high/max/OOM
events. Its processes included the active Codex CLI (about 403 MiB RSS), the
Codex app server (about 330 MiB), and MCP/CUA processes. This identifies a
substantial current development-session charge; its quiet local PSI and
current host headroom do not establish that this scope caused the October 28
OOM events.

`systemd-cgtop` charged `system.slice` about 3.0 GiB, spread across services;
large listed entries included Netdata (~421 MiB), RustDesk (~217 MiB), snapd
(~207 MiB), Continental status (~199 MiB), Echo production (~162 MiB), and
journald (~150 MiB). These services were not altered. The current Reality
recorder, MIDAS API, Reality API, and their separate cgroups remain active.
The 11:49 sample is an attribution snapshot, not a causal reconstruction. It
reinforces that pressure is aggregate and file-cache-heavy at this time, but
does not resolve what crossed the user-slice pressure threshold on October 28.
No process was killed or stopped to reduce the current charge.

## Post-checkpoint pressure signal — 2026-10-29 12:15 CET

The Frontier Polymarket replay slice used only serialized, fixture-backed
checks under explicit per-task memory, swap, CPU, task, and runtime bounds. The
focused API replay test and one UI component journey passed; `tsc -b` exited 0.
A combined strict-mypy invocation covering the new replay module and the large
API router reached its 60-second runtime cap and exited 143. An isolated strict
check of the new replay module then passed with imported modules silenced. No
public-data request or production action occurred.

At 12:14:01, `MemAvailable` was 11,351,244,800 bytes (10.57 GiB), `SwapFree`
was 14,327,808 bytes (13.66 MiB), and memory PSI had risen to `some`
avg10/avg60 **0.68% / 9.64%** and `full` **0.63% / 8.96%**. The uncapped
user-manager cgroup held 10,124,951,552 bytes memory and 2,856,464,384 bytes
swap. `memory.events.high` was 16,428,144, up 3,582 from the 12:10 sample;
`max=730,409`, `oom=19`, `oom_kill=15`, and `oom_group_kill=0` were unchanged.
Current top RSS included several Codex/terminal processes, protected Reality
at about 293 MB, journald at about 242 MB, MIDAS API at about 143 MB, and
Reality API at about 112 MB (the `ps` RSS values are KiB, shown here as rounded
decimal MB). This is a current process snapshot, not proof of
which workload caused pressure.

After 58 seconds without another compute-heavy check, the 12:14:59 sample had
`MemAvailable=11,431,800,832` bytes (10.65 GiB), unchanged swap and user-manager
`memory.events`, PSI avg10 back to zero, and avg60 declining to `some=3.67%` /
`full=3.41%`. At 12:15:35 the MIDAS API, Reality recorder/API, Continental
contact/status, Echo production/staging, RustDesk, SSH socket, and systemd-oomd
were active; API/Reality/Reality API restart counts remained 9/14/0. The gap-
detail timer remained inactive and the capacity timer was waiting. No matching
systemd-oomd or kernel kill appeared in the checked journal since 11:18 CET.

The timing leaves Frontier's bounded compiler/type-check activity as a
possible contributor to the transient PSI rise, but concurrent user workloads
and the aggregate user-manager scope prevent attribution. No service limit,
timer, OOMD policy, protected collector, store, or archive was changed in this
checkpoint. Do not run another compiler/build/browser suite or broad research
job until a fresh admission sample shows PSI back near baseline. Current status
remains **PARTIALLY CONTAINED / PARTIALLY VERIFIED**; safe continuation is
limited to small serialized offline edits and checks after admission.

## Bounded Frontier continuation and current admission sample — 2026-10-29 12:31 CET

No persistent service, timer, production store, protected recorder, or OOM
policy was changed during this Frontier continuation. A focused frontend test
was first started in a disposable scope capped at 64 tasks. At 12:24:13 the
kernel logged `fork rejected by pids controller` for that exact transient
scope, and Vitest stopped before collecting tests. This is attributed to the
scope's deliberately low `TasksMax=64`, not a host or user-slice task ceiling:
the enclosing `user-1000.slice` later measured 889 tasks against a 37,082-task
maximum. The same focused test was rerun with `TasksMax=128`, `GOMAXPROCS=2`,
and one Vitest worker; it passed **1/1** (7.39 seconds of test time, 17.90
seconds total). The transient PID-limit failure is separate from the October
28 memory-pressure kills and did not change OOM counters.

The saved-frame listing API cases passed **2/2 in 5.21 seconds** under a
512 MiB high / 640 MiB max, zero-swap, 20%-CPU, 128-task, 60-second bound.
The frontend `tsc -b` check exited 0 under the same memory and task bounds with
a 384 MiB Node heap; its transient peaked at 411,545,600 bytes and 20 tasks.
ESLint and Prettier checks passed after formatting the two edited frontend
files. Ruff check/format passed for the Python files. One existing
Starlette/httpx TestClient deprecation warning appeared.
The checks exercised fixture-backed UI/API behavior only; no exchange
connection or live capture occurred.

At 12:31 CET, `MemAvailable` was about 10 GiB, `SwapFree` about 14 MiB, and
host PSI was zero over avg10/avg60 (`some` avg300 0.08%, `full` avg300 0.07%).
`user-1000.slice` charged 10.26 GB memory and 3.41 GB swap; its task count was
889/37,082. User-manager `memory.events` remained `high=16,428,175`,
`max=730,409`, `oom=19`, `oom_kill=15`, and `oom_group_kill=0`. The active
`user@1000.service` had 10.18 GB memory and 2.86 GB swap and retained
`ManagedOOMMemoryPressure=kill` with its 50% threshold. Unlike the earlier
04:xx `oomctl` snapshot, `oomctl dump` now lists this user manager among
memory-pressure monitored cgroups at 50%; the earlier reporting mismatch is
not present in this sample, but continuity between samples is unverified.

The MIDAS API, Reality collector/API, and systemd-oomd were active. API and
Reality restart counts remained 9 and 14; Reality API remained at zero. The
capacity timer was waiting after its 12:18:53 trigger and retained its 160 MiB
high / 192 MiB max / zero-swap bound. The gap-detail timer remained inactive
and disabled. Continental contact/status/Cloud, Echo production/staging,
Headscale, and RustDesk were active; `ssh.socket` was listening on port 22.
No systemd-oomd kill was recorded since 12:18, and the only new kernel record
in the checked interval was the bounded test-scope fork rejection. These
observations establish a quiet bounded validation window, not durable incident
resolution. Swap is nearly exhausted and the October 28 global pressure
initiator remains unproven.

**Disposition:** Frontier can continue as serial, bounded, offline work after
a fresh admission sample. Broad suites, builds, public probes, source capture,
and production deployment remain deferred while swap and long-term pressure
behavior are unresolved.

## Post-fixture admission sample — 2026-10-29 12:36 CET

The focused malformed-frame listing regression passed **1/1 in 4.50 seconds**
inside its 512 MiB high / 640 MiB max, zero-swap, 20%-CPU, 128-task scope.
It changed only the temporary fixture database and made no network request.
At 12:36, the host had about 10 GiB `MemAvailable`, 14 MiB `SwapFree`, and
zero PSI through avg300. User-manager counters remained
`high=16,428,175`, `max=730,409`, `oom=19`, `oom_kill=15`, and
`oom_group_kill=0`; the enclosing user slice had 896 tasks. The checked
systemd-oomd and kernel journals had no new kill records since 12:31.

This adds a short quiet point after the prior bounded run, not durable recovery
evidence. The systemd-oomd user-manager monitor remains enabled at the 50%
pressure threshold, and near-total swap occupancy continues to constrain
admission. No host service or schedule was changed.

## Post-binding-check admission sample — 2026-10-29 12:38 CET

The saved-frame binding checks passed **2/2 in 5.39 seconds** in a bounded
zero-swap scope; the test used a temporary store and no exchange connection.
At 12:38, host PSI was zero through avg300 and `MemAvailable` remained about
10 GiB, but swap free was still about 14 MiB. User-manager memory events
remained `high=16,428,175`, `max=730,409`, `oom=19`, `oom_kill=15`, and
`oom_group_kill=0`; the user-slice task count was 890. No OOMD or kernel kill
appeared since 12:36. This is another short quiet interval only; no persistent
service or schedule changed, and the incident remains partially contained.

## Post cross-market binding fixture — 2026-10-29 12:40 CET

The final focused API run passed **2/2 in 4.81 seconds** under a zero-swap,
640 MiB maximum scope. The extra fixture rejected a rehashed frame bound to a
valid but unrelated Polymarket market; both listing and replay failed closed.
An earlier attempt hit the temporary SQLite append-only trigger after a new
fixture row recreated it. The test setup now drops the trigger again before
tampering, and the rerun passed. This was a test-fixture failure, not a host
PID or memory event.

At 12:40, `MemAvailable` was about 10 GiB, `SwapFree` about 14 MiB, and PSI
was zero through avg300. User-manager OOM counters remained unchanged, the
user slice had 889 tasks, and no OOMD/kernel kill appeared since 12:38. These
samples cover only short bounded offline tests. Near-total swap occupancy and
historical pressure attribution remain unresolved; no persistent service or
schedule changed.

## Missing-binding test observation — 2026-10-29 12:42 CET

The focused API run passed **2/2 in 5.11 seconds** in a 640 MiB maximum,
zero-swap test scope. A valid-format nonexistent parent ID was rejected by
both listing and replay. At 12:42, PSI was zero through avg300, available RAM
was about 10 GiB, and free swap remained about 14 MiB. User-manager OOM
counters were unchanged, the user slice had 890 tasks, and no OOMD/kernel
kill appeared since 12:40. No service or schedule changed. This short sample
does not establish durable incident recovery.

## Kraken replay provenance check and 12:45 admission sample

The Kraken offline replay route had a separate provenance gap: capture frames
had to share a saved-market observation ID, but replay did not resolve that ID
or verify that it described their Kraken pair. The route now resolves every
frame's parent and requires a stored Kraken `instrument_metadata` record for
the same `SPOT_PAIR` native market with exactly one matching instrument. Its
fixture regression rehashed frames to point at a missing parent, a persisted
stream-frame row, and valid but unrelated ETH/USD metadata; every request was
rejected with HTTP 409. The normal recorded BTC/USD fixture still replays with
the same deterministic result. The focused API test passed **1/1 in 4.61 s**
inside a transient scope capped at 512 MiB high / 640 MiB max, zero swap, 20%
CPU, and 128 tasks. Ruff check and formatting passed. The test used only a
temporary database and fixture frames; it made no exchange connection and did
not read production research stores.

At 12:45 CET, host `MemAvailable` was about 10 GiB while swap remained full
with about 14 MiB free. Host PSI was zero through avg300. User-slice
`memory.events` remained `high=16,428,175`, `max=730,409`, `oom=19`,
`oom_kill=15`, and `oom_group_kill=0`. The MIDAS API, Reality collector, and
Reality API were active with restart counts 9, 14, and 0; their current memory
was about 1.11 GB, 0.62 GB, and 0.47 GB respectively. The capacity unit was
inactive between runs with the reversible 160 MiB high / 192 MiB max / zero
swap override; its 30-minute timer remained active and was due at 12:48:53.
The gap-detail timer remained disabled; its unit's last state remains failed
after the October 28 OOM kill. No service or timer was changed during this
sample. No new OOM record was returned by the checked journal query.

This is a short bounded quiet period, not proof of recovery. The previously
identified 129 OOMd terminations on October 28 and seven 128 MiB capacity
memcg kills remain the established incident evidence. The gap-detail replay
was a demonstrated recurring target and likely contributor, but the initiating
global workload mix remains unproven. Full swap, unknown long-window pressure,
and the separate invalid archive-manifest/provenance warnings remain open.
Frontier may continue only as serial, offline work after fresh admission
samples; public probes, broad suites, and production deployment remain
deferred.

## Scheduled capacity run — 2026-10-29 12:49 CET

The existing 30-minute `midas-reality-capacity.timer` fired at 12:49:00 and
the service exited successfully at 12:49:07. systemd recorded a **130.5 MiB
memory peak**, **zero swap peak**, and 6.556 CPU seconds. The peak was below
the configured 160 MiB `MemoryHigh` and 192 MiB `MemoryMax`; the timer returned
to `active (waiting)` for its 13:19 run. This is one successful bounded run
under the revised limit, not endurance evidence. No service or timer was
manually started, stopped, or reconfigured for this validation.

After completion, the host still had about 10 GiB `MemAvailable`, 14 MiB free
swap, and zero memory PSI through avg300. User-slice OOM counters remained
unchanged at `oom=19` / `oom_kill=15`; the checked OOMd and kernel journals
returned no new kill records since 12:45. MIDAS API, Reality, Reality API,
Continental contact/status/cloud services, Continental's tailnet and ID-auth
user services, Echo production/staging, Headscale, RustDesk, and the SSH
socket were active. API and Reality restart counters remained at 9 and 14.
The same capacity artifact reports `collector_state=RECORDING_UNSEQUENCED`
with a 0.187-second-old collector status; this is a fresh status observation,
not evidence of sequence completeness or archival integrity.

The capacity report written by the scheduled run still reports
`UNVERIFIED_MANIFEST_SIZE_LIMIT`, `archive_manifest_provenance_valid=null`,
and `ARCHIVE_MANIFEST_SIZE_LIMIT`, `ARCHIVE_INVENTORY_UNVERIFIED`, and
`ARCHIVE_CAPACITY_UNKNOWN`. No archive manifest, recording, or historical
research evidence was changed. This remains a separate data-integrity and
capacity uncertainty; the successful memory-bound run does not validate the
archive or establish off-host redundancy.

**Current disposition:** Partially contained and partially verified. The
observed capacity workload fits the revised bound in this scheduled run, and
critical services were active in the checked scopes. Full swap and the
unidentified initiating global workload mix remain open. Continue Frontier
only with serial offline work and fresh admission samples; broad suites, live
probes, and production deployment remain deferred.

## Post-replay bounded validation sample — 2026-10-29 12:55 CET

The focused Polymarket price-history API test passed **1/1 in 6.91 s** under a
512 MiB high / 640 MiB max, zero-swap, 20%-CPU, 128-task transient scope. It
replayed the valid fixture, then verified that a rehashed price-history row
whose normalized Decimal differs from the stored raw response is rejected, and
that a rehashed market batch with mismatched declared/member venues is
rejected. Ruff check and formatting passed. The test used a temporary SQLite
store and mock transport; no exchange or production data was accessed.

At 12:55, the host still had about 10 GiB `MemAvailable`, 14 MiB free swap,
and zero PSI through avg300. User-slice event counters remained
`high=16,428,175`, `max=730,409`, `oom=19`, `oom_kill=15`, and
`oom_group_kill=0`. MIDAS API, Reality, and Reality API were active at restart
counts 9, 14, and 0. The gap-detail timer remained disabled and the capacity
timer active. The checked OOMd/kernel journals had no new kill records since
12:49. This short post-test sample adds no endurance or global-cause evidence;
full swap and the initiating workload remain unresolved.

## Numeric-bound follow-up — 2026-10-29 12:58 CET

The historical-price replay implementation and Polymarket adapter now compare
integral Decimal timestamps with the bounded request interval before converting
them to Python integers. The extreme fixture value `1e1000000000` fails in
both capture parsing and offline replay without oversized integer
materialization. The combined focused group passed **3/3 in 8.69 s** under a
512 MiB high / 640 MiB max, zero-swap, 20%-CPU, 128-task scope. Ruff check and
format passed. No source or production evidence was accessed.

At 12:58, available RAM remained about 10 GiB, swap free 14 MiB, and PSI zero
through avg300. User-slice OOM counters remained 19/15/0, API/Reality/Reality
API remained active at restart counts 9/14/0, and the checked OOMd/kernel
journals showed no new kill since 12:55. Full swap and the historical
initiating workload remain unresolved; the host stays **PARTIALLY CONTAINED /
PARTIALLY VERIFIED**.

## Malformed-envelope validation sample — 2026-10-29 13:00 CET

After adding duplicate-key, `NaN`, and instrument-query mismatch cases, the
focused price-history capture/replay group passed **6/6 in 7.11 s** under a
512 MiB high / 640 MiB max, zero-swap, 20%-CPU, 128-task scope. Existing
TestClient deprecation warning remains. The cases use mock transports and
in-memory rows only.

At 13:00, `MemAvailable` remained about 10 GiB, free swap about 14 MiB, and
PSI was zero through avg300. User-slice OOM counters remained 19/15/0; API,
Reality, and Reality API remained active at restart counts 9/14/0. No new
OOMd/kernel kill appeared in the checked interval since 12:58. This is another
short sample; full swap, global workload attribution, and long-window recovery
remain unresolved.

## Current host and admission sample — 2026-10-29 13:03 CET

At 13:03, the host reported 11,403,976,704 bytes `MemAvailable` (10.62 GiB),
15,368,192 bytes free swap (14.65 MiB), and zero `some`/`full` memory PSI for
avg10, avg60, and avg300. `user@1000.service` held 10,544,066,560 bytes
(9.82 GiB): approximately 2.21 GiB anonymous, 6.51 GiB file-backed, and 1.07
GiB kernel memory. Its cumulative counters remained `high=16,428,175`,
`max=730,409`, `oom=19`, and `oom_kill=15`. Cumulative `memory.stat` counts
include about 394.6 million pages scanned and 28.5 million / 29.9 million
pages swapped in / out. Current PSI is quiet, but these totals confirm
substantial historical reclaim and swap churn without attributing them to one
process.

`oomctl` currently lists `user@1000.service` as a pressure-monitored cgroup
with zero current PSI. The earlier 04:32 dump that listed no monitored cgroups
was therefore not reproduced in this sample; its cause remains unknown. No
systemd-oomd kill appeared after the last recorded October 28 23:43:24 kill,
and the kernel query found no memcg OOM after the last October 28 20:15:44
capacity-checker kill. This is a quiet interval, not endurance validation.

MIDAS API, Reality, and Reality API were active at restart counts 9, 14, and 0
with current memory 1.05 GiB, 603 MiB, and 457 MiB. Their existing bounds
remain API 1.5/1.75 GiB high/max, Reality 1.125/1.25 GiB, and Reality API 512
MiB max; no service was restarted or reconfigured. The capacity timer remains
active and waiting, with its last observed run at 12:49:07 successful at a
130.5 MiB peak under the 160/192 MiB high/max bound. The gap-detail timer
remains inactive and disabled; its service remains failed from the prior OOM
kill. No new capacity run or live collector intervention was started for this
sample.

**Admission decision:** Continue Frontier only as serial, offline work in
transient scopes with explicit memory, swap, CPU, task, and runtime bounds. Do
not run broad suites, public probes, high-memory profiling, or production
deployment while swap is nearly exhausted and historical user-slice reclaim
is unexplained. The observed short test scopes and current quiet PSI support
bounded development only; they do not establish that the host-wide incident is
resolved. Archive-manifest provenance and inventory warnings remain a
separate unresolved integrity concern.

## Bounded storage venue validation — 2026-10-29 13:08 CET

Commit `fbf8fe9` makes `MarketBatch` reject members whose venue differs from
the batch, makes observation writes reject a normalized top-level venue that
differs from the captured raw venue, and repeats both checks when stored rows
are read. A row with a recomputed local digest cannot silently relabel a
normalized market while its raw source row remains intact. The `/markets` API
returns HTTP 409 for these tampered fixtures; no network calls occur.

The focused source/model/storage/API regressions passed **6/6 in 8.70 s**. The
entire storage module then passed **37/37 in 12.19 s**. Both ran serially in
transient scopes with `MemoryHigh=512M`, `MemoryMax=640M`,
`MemorySwapMax=0`, `CPUQuota=20%`, and `TasksMax=128`; the storage module also
had a 45-second runtime bound. Ruff check, formatting, and `git diff --check`
passed. Pytest emitted its existing Starlette/httpx deprecation warning. All
fixtures used temporary SQLite stores; no production database or exchange
source was accessed.

At 13:08, `MemAvailable` was 11,389,616,128 bytes (10.61 GiB), free swap was
15,970,304 bytes (15.23 MiB), and host memory PSI remained zero through avg300.
User-manager `memory.events` were unchanged at `high=16,428,175`,
`max=730,409`, `oom=19`, and `oom_kill=15`. API, Reality, and Reality API
remained active at restart counts 9/14/0. The capacity timer remained active;
the gap-detail timer remained disabled. No new OOMD or kernel kill appeared
in the checked interval. This short bounded run does not resolve the full-swap
risk, global workload attribution, or archive integrity uncertainty.

**Status:** Incident remains **PARTIALLY CONTAINED / PARTIALLY VERIFIED**.
Frontier can continue only through serial offline work with explicit resource
bounds. Broad suites, probes, and deployment remain deferred.

## Rollback-path readback — 2026-10-29 13:09 CET

Read-only inspection confirmed that the persistent
`90-frontier-memory-bound.conf` overrides the user manager's runtime
`50-MemoryHigh.conf`: the persistent values are 160/192 MiB high/max, while the
runtime fallback is 128 MiB high, 192 MiB max, and zero swap. Replacing the
persistent file with the documented `MemoryMax=128M` and `MemorySwapMax=0`
content, then reloading, restores the previous effective 128 MiB high/max
limit. No service configuration or runtime limit was changed during this
cross-check.

## Captured-evidence browser admission — 2026-10-29 13:14 CET

One Playwright browser journey rendered the committed public Polymarket
capture in an isolated `/tmp` root. It passed **1/1 in 44.7 seconds** under
`MemoryHigh=768M`, `MemoryMax=1G`, zero swap, 20% CPU, 128 tasks, and a
120-second runtime limit. Its fixture copied a 270,336-byte hash-pinned store
and used only loopback API/Vite servers; assertions observed no source probes
or API mutations.

At 13:14 the host had 10.58 GiB `MemAvailable`, 15.24 MiB free swap, and zero
memory PSI through avg300. User-manager OOM counters were unchanged at 19/15;
API, Reality, and Reality API remained active at restart counts 9/14/0. No new
OOMD or kernel kill appeared in the checked interval. This bounded browser
journey did not change the partially contained disposition: nearly full swap,
historical workload attribution, and archive integrity remain unresolved.

## Cross-adapter regression and current resource sample — 2026-10-29 13:17 CET

Four fixture-driven market normalization regressions passed **4/4 in 3.71 s**
for Polymarket event groups, Kalshi multivariate event batches, Coinbase spot
discovery, and Gemini spot discovery. They ran without source requests in a
transient scope limited to 512 MiB high / 640 MiB max, zero swap, 20% CPU,
128 tasks, and 90 seconds. The tests establish parser/normalizer behavior for
these fixture cases only; no live cross-venue validation is claimed.

At 13:17:26 CET, host `MemAvailable` was 11,411,402,752 bytes (10.63 GiB) and
`SwapFree` was 15,986,688 bytes (15.25 MiB) out of 4 GiB. Global PSI and
`user@1000.service` PSI were zero through avg300. User-manager `memory.events`
remained high=16,428,175, max=730,409, oom=19, oom_kill=15, and
oom_group_kill=0. Its cgroup currently accounted for 10,554,929,152 bytes of
memory and 2,855,981,056 bytes of swap, with `memory.high=max` and
`memory.max=max`. `memory.stat` split current memory into 7.02 GB file,
2.36 GB anonymous, and 1.15 GB kernel categories. Cumulative `pgscan_direct`,
`pswpin`, and `pswpout` counters were 272,492,783, 28,498,730, and 29,863,773
pages. These are lifetime counters without an interval delta; they evidence
reclaim/swap activity but do not identify when it occurred or which process
initiated the pressure. OOMD/kernel journals had no entries since 13:14.

API, Reality, and Reality API remained active at restart counts 9/14/0. API
current/peak memory was 1.05/1.50 GiB; Reality was 610 MiB/1.125 GiB, each
currently below its configured high threshold. The Reality-capacity timer was
active while its service was inactive. The gap-detail timer remained inactive;
its service remained failed from the prior incident. No service configuration,
production data, or archive manifest changed in this continuation. This short
quiet observation does not resolve nearly full swap, historical workload
attribution, or archive provenance concerns.

**Admission:** Continue Frontier only as serial, offline work in a transient
scope with an explicit memory cap and zero swap. Keep live source probes,
production changes, broad suites, and persistent workers deferred. Reassess
swap and cgroup PSI before each bounded step; do not treat this sample as
proof the host has recovered.

## Captured-store replay validation — 2026-10-29 13:21 CET

One offline Playwright journey passed **1/1 in 40.7 s** (17.4 s test runtime)
against the committed hash-pinned Polymarket store copied into a fresh `/tmp`
root. It clicked the Mission Control Economic workbench replay action and
asserted the successful response referenced nonempty market and book
observation IDs, a version-pinned Frontier code digest, and a well-formed
result hash. It also asserted exactly one mutation (`POST /api/frontier/replay`)
and zero source-probe requests. The replay persisted only in the disposable
test store. This validates captured historical evidence through the UI; it
does not establish current data or simultaneous cross-venue availability.

The Playwright/API/Vite scope used 768 MiB high / 1 GiB max, zero swap, 20% CPU,
128 tasks, a 120-second runtime cap, and a 384 MiB Node heap. At 13:21:41 CET,
host `MemAvailable` was 11,311,423,488 bytes (10.54 GiB), `SwapFree` was
15,994,880 bytes (15.25 MiB), global PSI remained zero, and user-manager OOM
counters stayed at high=16,428,175, max=730,409, oom=19, oom_kill=15,
oom_group_kill=0. API, Reality, and Reality API remained active at restart
counts 9/14/0. The local test ports 18000 and 15173 had no listeners, and no
OOMD/kernel journal entries appeared since the 13:19:51 pre-run sample.

Host admission remains **partially contained**: one short run did not consume
swap, but only 15.25 MiB remained free before and after. Continue only bounded
serial offline development. Historical initiating workload and archive
provenance remain unresolved.

## Narrow-viewport browser check — 2026-10-29 13:26 CET

The pinned capture was copied to a fresh `/tmp` root and used by local
loopback-only API/Vite servers. One Playwright journey passed **1/1 in 46.5 s**
(22.3 s in the test) at 390 × 844 CSS pixels. It visited the eight primary
Frontier sections and checked that the document had no horizontal overflow.
The run made zero source probes and zero API mutations.

The scope was limited to 768 MiB high / 1 GiB max, zero swap, 20% CPU,
128 tasks, and 120 seconds; Node's heap was capped at 384 MiB. Post-run at
13:26:47 CET, host `MemAvailable` was 10.21 GiB, `SwapFree` was 15.28 MiB, PSI
was zero, and user-manager OOM counters remained 19/15. API, Reality, and
Reality API were active at restart counts 9/14/0. Test ports were closed and
there were no OOMD/kernel journal entries since the pre-run sample. This
bounded quiet period does not establish host recovery; swap is still nearly
full and workload attribution remains open.

## Replay determinism check — 2026-10-29 13:32 CET

The captured-store browser journey submitted the same deterministic replay
twice. Both responses referenced nonempty market and book observation IDs and
returned the same `run_id` and `result_sha256`; the browser observed exactly
two replay POSTs and zero source-probe requests. The test used only the
hash-pinned capture copied to a fresh `/tmp` store.

It passed **1/1 in 42.5 s** (18.5 s in the test) under a transient scope with
768 MiB high / 1 GiB max, zero swap, 20% CPU, 128 tasks, a 120-second runtime
limit, and a 384 MiB Node heap. At 13:32:19 CET, `MemAvailable` was 10.16 GiB,
`SwapFree` was 15.36 MiB, PSI remained zero, user-manager OOM counters remained
19/15, and API/Reality/Reality API were active at restart counts 9/14/0. Test
ports were closed; no OOMD/kernel journal entries appeared since 13:29:23.

The sample remains too short to establish host recovery. Continue only
resource-capped serial offline work; historical workload attribution and
archive provenance remain unresolved.

## 320-pixel responsive extension — 2026-10-29 13:29 CET

The same captured-store Playwright journey now checks all eight primary
Frontier sections at both 320 × 844 and 390 × 844 CSS pixels. It passed **1/1
in 49.4 s** (25.2 s in the test), with no document-level horizontal overflow,
source-probe requests, or API mutations. It ran with a 768 MiB high / 1 GiB
max, zero-swap, 20%-CPU, 128-task, 120-second cgroup and a 384 MiB Node heap.

Post-run at 13:29:23 CET: `MemAvailable` was 10.60 GiB, swap free was 15.36
MiB, PSI was zero, user-manager OOM counters remained 19/15, and API/Reality/
Reality API remained active at restart counts 9/14/0. Test ports were closed;
the OOMD/kernel query had no new entries since 13:26:47. This expands narrow
screen evidence while leaving host recovery, cross-browser rendering, and
accessibility evaluation unresolved.

## Contract comparison browser check and post-run host sample — 2026-10-29 13:47 CET

The isolated captured-data responsive test first reached its 30-second
Playwright test timeout while navigating between sections; the saved failure
contains no horizontal-overflow assertion. The test was given a 60-second
test-level bound and rerun once. It passed **1/1 in 37.0 seconds** (runner
duration 1.0 minute) while opening the relationship contract comparison at
both 320 px and 390 px widths. The expanded panels remained within the
document width, with zero source probes and zero API mutations. The single
browser/API/Vite scope was bounded to 768 MiB high / 1 GiB max, zero swap, 20%
CPU, 128 tasks, 120 seconds, and a 384 MiB Node heap; its database was a fresh
temporary copy of the committed public Polymarket capture.

At 13:47:27 CET, `MemAvailable` was 11,169,927,168 bytes (10.40 GiB),
`SwapFree` was 16,117,760 bytes (15.37 MiB), and global memory PSI was zero.
The user-manager memory event counters were unchanged at high=16,428,175,
max=730,409, oom=19, oom_kill=15, oom_group_kill=0. API and Reality remained
active at restart counts 9 and 14; Reality API remained active at 0 restarts.
The capacity service was inactive and its timer remained active; the
gap-detail timer remained disabled and its unit was failed from the earlier
run. Ports 18000 and 15173 were closed, and the checked OOMD/kernel journals
had no entries since 13:46:10. The capacity timer's next scheduled run was
13:49:04 and had not yet been observed at this sample.

This brief interval shows no new kill during the bounded test; it does not
establish recovery or identify the historical pressure initiator. Swap
remains nearly full, the user-manager hierarchy remains uncapped, and archive
provenance remains unresolved. Continue Frontier only as serial, offline,
resource-capped work after fresh admission checks. Do not start broad suites,
live probes, or concurrent research on the basis of this sample.

At 13:49:04 the scheduled `midas-reality-capacity.service` invocation started
without intervention and exited successfully at 13:49:11 (`ExecMainStatus=0`,
6.514 CPU seconds). The service's measured unit configuration is
`MemoryHigh=160 MiB`, `MemoryMax=192 MiB`, `MemorySwapMax=0`; its timer remains
active and next scheduled for 14:19. API, Reality, and Reality API remained
active at restart counts 9/14/0. No new OOMD or kernel kill appeared after
13:47:27, and user-manager OOM counters remained unchanged. This is one
successful run within the revised budget, not evidence that the process peak
or sustained headroom is safe.

The monitor continues to report `UNVERIFIED_MANIFEST_SIZE_LIMIT`,
`ARCHIVE_INVENTORY_UNVERIFIED`, `ARCHIVE_CAPACITY_UNKNOWN`,
`COLLECTOR_STATUS_STALE`, pending budget/retention changes, and capacity
warnings. These remain integrity and operations findings. No manifest or
historical evidence was modified. Incident status remains **PARTIALLY
CONTAINED / PARTIALLY VERIFIED**.

## Current cgroup and OOMD attribution sample — 2026-10-29 13:50 CET

At 13:50:56 CET, host `MemAvailable` was 11,377,102,848 bytes (10.60 GiB),
while only 16,134,144 bytes (15.39 MiB) of swap remained free. Global memory
PSI avg10/avg60/avg300 was zero. The one-second follow-up `vmstat` interval
showed no swap-in or swap-out; this is a short instantaneous sample, not a
trend. User-manager OOM counters remained high=16,428,175, max=730,409, oom=19,
oom_kill=15, oom_group_kill=0, and no OOMD/kernel kill appeared since 13:47:27.

`systemd-oomd` is active and not in dry-run mode. Its current policy reports a
90% swap-used limit, default 60% memory-pressure limit for 20 seconds, and a
monitored `/user.slice/user-1000.slice/user@1000.service` pressure limit of
50%. That user-manager cgroup currently has no `memory.high`, `memory.max`, or
`memory.swap.max` bound. Its current charge was 10,534,014,976 bytes (9.81
GiB), including 2,855,960,576 bytes (2.66 GiB) of swap; `memory.stat` showed
2.20 GiB anonymous, 6.51 GiB file cache, and 1.08 GiB kernel memory, of which
about 0.99 GiB was slab. The containing `user-1000.slice` was at 10.64 GiB
memory and 3.18 GiB swap, also without those limits.

The process RSS snapshot showed three Codex processes at approximately 404,
352, and 328 MiB and the Reality Python process at approximately 305 MiB.
These current resident sizes do not identify which workload caused the past
pressure: RSS omits page cache and kernel memory, and this sample was taken
after the historical kills. The data demonstrates an uncapped shared user
hierarchy with substantial file-cache, kernel/slab, anonymous, and swap
charges, but does not establish the initiating workload or prove that Frontier
caused the incident. No cap was applied to the shared user hierarchy because
it contains protected collection, API, desktop, and administrative sessions;
choosing a parent budget without a verified aggregate service budget could
jeopardize those services.

The API, Reality, and Reality API remained active at restart counts 9/14/0.
The scheduled capacity monitor had completed successfully at 13:49:11 under
its 160/192 MiB high/max limits and zero swap, while continuing to report
archive manifest/inventory uncertainty and stale collector status. The
gap-detail timer remains disabled. Incident status is still **PARTIALLY
CONTAINED / PARTIALLY VERIFIED**: the service-specific cap mismatch and
auxiliary timer churn are contained, but system-wide historical workload
attribution and sustained recovery are not established.

## Cross-venue fixture and post-test pressure observation — 2026-10-29 13:57 CET

The fixture-only graph browser journey now opens the saved cross-venue
Polymarket/Kalshi relationship and displays deliberately different
resolution authorities, primary rules, close/settlement times, payoff state
IDs, rule fingerprints, and native instrument IDs. The view retains the
hypothesis status and warns that the comparison does not establish equivalent
payoffs. The targeted test passed **1/1** (32.9 seconds for the test; 59.6
seconds total runner time) with Prettier and ESLint passing. It uses synthetic
browser fixtures only and provides no evidence of live multi-venue matching.

The transient Playwright/API/Vite scope was limited to 768 MiB high / 1 GiB
max, zero swap, 20% CPU, 128 tasks, 120 seconds, and a 384 MiB Node heap. The
pre-run sample at 13:55:07 showed zero global PSI and user-manager
`memory.events high=16,428,175`. At 13:56:22, after the run, PSI had risen to
some avg10/avg60/avg300 = 1.09/0.53/0.13% and full = 0.96/0.45/0.11%; the
hierarchical `high` counter was 16,430,236 (+2,061). `max`, `oom`, and
`oom_kill` remained 730,409/19/15. Available RAM was 10.58 GiB, swap free
15.42 MiB, test ports 18000/15173 were closed, and API/Reality/Reality API
remained active at restart counts 9/14/0. The aggregate counter and timing do
not establish that this test alone caused the increase.

After a 30-second quiet interval, at 13:57:05, PSI had fallen to some
avg10/avg60/avg300 = 0.01/0.25/0.10% and full = 0.01/0.21/0.08%; the `high`
counter and OOM counts were unchanged. The one-second follow-up showed no
swap I/O. This reduces the immediate concern but does not establish sustained
recovery. Further compute is paused pending a fresh admission sample; no
critical service was restarted or changed.

## Payoff-detail browser check and post-run sample — 2026-10-29 14:06 CET

The relationship comparison panel now displays instrument payout vectors by
state, quantity units, price currencies, tick and quantity increments, minimum
quantity/notional, fee applicability and schedule provenance, native market
IDs, payoff verification basis, and resolution fingerprints. Missing source
fields remain explicitly unreported. The cross-venue fixture test passed
**1/1 in 34.7 seconds** (1.1 minutes total runner time). Frontend TypeScript
passed in 89 seconds; targeted ESLint and formatting passed. A combined
Prettier invocation exceeded its 45-second transient scope after formatting
the main component and confirming CSS unchanged; formatting was then finished
with a separate bounded run on the E2E file. No production bundle or broad
suite was run.

The test scope used 768 MiB high / 1 GiB max, zero swap, 20% CPU, 128 tasks,
120 seconds, and a 384 MiB Node heap. At 14:06:26, host `MemAvailable` was
10.24 GiB and `SwapFree` was 15.45 MiB. Global memory PSI avg10/60/300 was
zero; `memory.events high` increased by 267 to 16,430,503 while `max`, `oom`,
and `oom_kill` remained 730,409/19/15. The one-second `vmstat` follow-up had
zero swap-in/out. The event counter is hierarchical; attribution is not
assigned to this test. API, Reality, and Reality API remained active at
restart counts 9/14/0, ports 18000/15173 were closed, and no OOMD or kernel
kill appeared since 14:05.

This is a successful bounded fixture verification with no observed host PSI
or OOM event. Swap remains almost full and the shared user manager remains
uncapped; do not infer sustained recovery. No further browser work was started
in this checkpoint.

## Leaf-cgroup workload snapshot — 2026-10-29 14:08 CET

A read-only scan of 79 leaf cgroups at 14:08:02 showed the largest current
charge in a long-lived GNOME Terminal `vte-spawn` scope: 2,567.9 MiB memory,
no swap, 599.9 MiB anonymous, 1,927.9 MiB file cache, and 39.3 MiB kernel
memory. The process inventory from the same inspection showed sleeping Codex
and Node processes in that scope. The snapshot command itself ran inside the
scope and contributes a small amount; it was not stopped or altered. This is
a significant current shared-user workload candidate, not proof that it
triggered the October 28 kills.

Other large leaf charges were MIDAS API at 1,106.8 MiB (978.4 MiB file,
116.5 MiB anonymous), Reality at 649.3 MiB (341.7 MiB file, 292.6 MiB
anonymous), and Reality API at 471.6 MiB (361.4 MiB file, 95.9 MiB anonymous).
The latter's measured charge is close to its 512 MiB `MemoryMax`, though it
remained active and did not hit the limit in this sample. Chromium and GNOME
Shell also had 133.7 MiB and 300.8 MiB of swap charged respectively. These
leaf values explain why process RSS and service kill frequency alone do not
describe the memory hierarchy, but still do not assign the historical OOMD
trigger to one workload.

At 14:08:02, host `MemAvailable` was 10.60 GiB, free swap 15.45 MiB, and
global PSI avg10/60/300 was zero. No service was stopped, signaled, or
reconfigured. This is current-state attribution evidence only; root cause
remains **PARTIALLY IDENTIFIED** at the shared uncapped user-manager and
high-swap-pressure level, with the initiating workload unconfirmed.

## Reality API hard-limit readback — 2026-10-29 14:09 CET

The Reality API cgroup read back `MemoryCurrent=495,714,304` bytes
(472.7 MiB), `MemoryPeak=536,870,912` bytes (512 MiB),
`MemoryMax=536,870,912` bytes, no `MemoryHigh`, and `MemorySwapMax=0`.
Its `memory.events` showed `max=5,030` but `oom=0` and `oom_kill=0`; its
current `memory.stat` was approximately 95.9 MiB anonymous, 362.4 MiB file,
and 14.4 MiB kernel memory. The service remained active with zero restarts.
Thus the hard boundary has been reached historically and allocations have
hit it, but this sample shows no OOM termination or service restart.

At 14:09:50, host memory PSI avg10/60/300 remained zero, approximately 10.60
GiB was available, and only 15.45 MiB of swap was free. API and Reality were
also active at restarts 9/14; test ports were closed and no OOMD or kernel kill
appeared since 14:06:26. No limit was changed: the service's file-backed
charge is large and the aggregate user-manager budget is unresolved, so
increasing its cap would raise potential host commitment without evidence that
the added memory is necessary. Track this as a near-limit service risk, not a
demonstrated OOM cause.

## Scheduled-workload boundary and bounded Frontier continuation — 2026-10-29 14:23 CET

Read-only inspection of scheduled one-shot units found differing containment:
the Arena scheduler and Veritas research director each have a 512 MiB hard
limit but no `MemoryHigh` or swap cap; Veritas source analysis has a 256 MiB
hard limit but no high or swap cap; the observatory has a 256 MiB hard limit
and zero swap; and the Continental infrastructure audit has no memory or swap
limit. The Arena dispatcher runs once per minute, while research and audit
timers can run near one another. This exposes possible aggregate concurrency
and some noncritical units without reclaim/swap bounds, but does not prove
these jobs caused the October 28 pressure. At the 14:16–14:23 observation,
host PSI remained zero, user-manager OOM counters did not change, and no new
OOMD or kernel kill was logged. No timer or unit was modified because there
was no new evidence to justify changing unrelated scheduled operations or a
host-wide budget.

The gap-detail timer is confirmed **disabled and inactive**. Its restoration
command is `systemctl --user enable --now midas-veritas-gap-detail-v2.timer`;
re-enabling it is not recommended until the finalized-replay cadence and
resource admission are reviewed. The capacity monitor ran 14:19:04–14:19:11
and exited 0 with its runtime configuration at `MemoryHigh=160 MiB`,
`MemoryMax=192 MiB`, and `MemorySwapMax=0`. No cap or persistent unit file was
changed in this checkpoint.

Frontier resumed only with serialized fixture work. Prettier and targeted
ESLint passed; the pure relationship-term comparator tests passed 3/3; full
frontend TypeScript passed, followed by a strict isolated type check of the
final helper adjustment. All scopes had explicit memory, zero-swap, CPU, task,
and runtime bounds. The browser E2E assertion was added but not run. There
were no live source requests or production-store writes.

At 14:23:22 CET, host `MemAvailable` was 11,382,661,120 bytes (10.60 GiB),
`SwapFree` was 16,211,968 bytes (15.46 MiB), and global PSI avg10/60/300 was
zero. The user-manager counters were high/max/oom/oom_kill =
16,430,503/730,447/19/15, unchanged from the 14:11–14:13 sample. API, Reality,
and Reality API remained active at restart counts 9/14/0. No OOMD or kernel
kill was logged after 14:19:11. This short, quiet observation does not
establish recovery: swap remains effectively full, the user manager remains
uncapped, historical workload attribution remains incomplete, and the
Reality API is still close to its hard memory limit. Continue only serial,
offline, resource-capped Frontier work after another fresh admission check.

## User-hierarchy composition after bounded validation — 2026-10-29 14:24 CET

At 14:24:54, the uncapped `user@1000.service` cgroup charged
10,612,408,320 bytes (9.88 GiB) memory and 2,855,936,000 bytes (2.66 GiB)
swap. `memory.stat` reported 2,396,262,400 bytes anonymous, 7,035,355,136
bytes file-backed, and 1,157,074,944 bytes kernel memory; slab was
1,061,658,896 bytes (0.99 GiB). The containing `user-1000.slice` charged
10,687,549,440 bytes (9.95 GiB) memory and 3,412,992,000 bytes (3.18 GiB)
swap. At the same readback, host `MemAvailable` was 11,371,073,536 bytes
(10.59 GiB), free swap was 16,216,064 bytes (15.46 MiB), and global PSI was
zero. User-manager event counters remained high/max/oom/oom_kill =
16,430,503/730,447/19/15. This shows that substantial aggregate user-session
charges coexist with currently quiet PSI and available host RAM. It does not
identify the initiating workload for the historical OOMD or kernel events.

## Browser verification and transient reclaim-pressure follow-up — 2026-10-29 14:29 CET

The captured-store cross-venue relationship test was subsequently run and
passed **1/1**; it executed for 53.7 seconds (1.4 minutes total) and asserted
the new visible comparison of literal contract-field differences. The
Playwright scope was bounded at 768 MiB `MemoryHigh`, 1 GiB `MemoryMax`, zero
swap, 20% CPU, 128 tasks, and 120 seconds, with a 384 MiB Node heap. All data
was fixture-backed; no live exchange, production API, or production store was
used. The local test listeners were closed after the run.

At 14:27:31, the post-run sample recorded host some/full memory PSI
avg10/avg60/avg300 = 6.32/7.88/2.25% and 5.51/6.96/1.99%; host available RAM
was about 10.45 GiB and free swap 15.46 MiB. The shared user-manager
`memory.events high` count increased by 7,047 to 16,437,550; `max`, `oom`, and
`oom_kill` stayed at 730,447/19/15. API/Reality/Reality API restart counts
remained 9/14/0, and no OOMD or kernel kill appeared. This timing is
consistent with the capped browser workload or concurrent user-session work
contributing to reclaim pressure, but the hierarchical counter cannot
attribute the event to the test alone.

During quiet follow-up, avg10 PSI returned to zero by 14:28:45. At 14:29:41,
avg60 had declined to some/full 0.90/0.79% and avg300 to 1.42/1.26%; available
RAM was 10.60 GiB and swap free was 15.47 MiB. The `high` and OOM counters did
not increase after the immediate post-run sample. This is a brief declining
pressure interval, not proof of sustained recovery. No additional test,
build, or batch was started. Continue only read-only/source-independent work
after a fresh admission check; defer browser and build verification until a
longer quiet period is demonstrated.

The scheduled Veritas observatory ran at 14:31:04–14:31:16 and exited 0 under
its 256 MiB hard cap / zero-swap setting. At 14:31:35, host some/full PSI
avg10/60/300 was 0/0.13/0.96% and 0/0.11/0.85%; available memory was 10.62
GiB and swap free 15.47 MiB. User-manager `memory.events` stayed at
high/max/oom/oom_kill = 16,437,550/730,447/19/15. API, Reality, and Reality API
remained active at restart counts 9/14/0, with current charges about 1.09 GiB,
662.6 MiB, and 483.3 MiB respectively. No OOMD or kernel kill was logged
since 14:27:31. PSI averages continued to decline; the average window is
short and swap remains nearly full, so this is not incident closure. Stop
additional Frontier compute and retain the current resource caps and service
state pending a longer quiet period.

At 14:32:41, about five minutes after the browser test, PSI had declined
further: some/full avg10/60/300 = 0/0.03/0.75% and 0/0.03/0.66%. Host
`MemAvailable` was 10.60 GiB, swap free 15.47 MiB, and the shared user-manager
`memory.events high` counter remained 16,437,550; `oom`/`oom_kill` remained
19/15. API, Reality, and Reality API were active at restart counts 9/14/0.
No OOMD or kernel kill was logged since 14:27:31. This short follow-up shows
the browser-associated pressure episode receding without an observed kill,
while swap occupancy, the uncapped parent cgroup, near-cap Reality API, and
unknown historical trigger continue to block an incident-resolved verdict.

## Bounded relationship-terms UI follow-up — 2026-10-29 14:42 CET

After a fresh admission sample, Frontier made a source-independent UI change:
the relationship comparison now exposes canonical market/payoff settlement
asset identities and more fee-schedule provenance (fixed fee, multiplier,
evidence hash and observation IDs, observation/effective/expiry timestamps).
Comparison content is computed only for the expanded relationship row. The
instrument detail also names the captured quote-currency identity and keeps
unreported constraints explicit. No live source, production API, or evidence
store was read or written.

Formatting, targeted lint, the pure comparator suite (4/4), and full frontend
TypeScript checking passed under the previously documented bounded scopes.
A targeted component test was then launched in a 512 MiB high / 768 MiB max,
zero-swap, 20%-CPU, 64-task scope. Its terminal session handle disappeared
before Vitest's result could be retained. At 14:42:48, systemd no longer
listed the transient scope and its journal recorded ordinary scope
completion, but it did not retain the test process exit code or assertion
summary. Therefore that component check is **inconclusive**, not a pass. It
was not rerun.

At 14:42:29–14:42:48, host `MemAvailable` was about 10 GiB, swap free about
15 MiB, PSI avg10/60/300 some/full was 0/0.01/0.06%, and user-manager
`memory.events` remained high/max/oom/oom_kill =
16,437,550/730,447/19/15. API, Reality, and Reality API remained active at
restart counts 9/14/0; the auxiliary gap-detail timer remained inactive and
the capacity timer remained waiting. No kernel OOM or systemd-oomd kill was
logged since the test started. This short quiet window does not resolve the
incident: swap remains almost full, the shared user hierarchy is uncapped,
Reality API was previously near its hard limit, and historical pressure
initiation is still unattributed. Keep browser/build and broad-suite work
deferred; continue only serial, offline work after a fresh admission sample.

## Static UI state-race correction — 2026-10-29 14:45 CET

A final static review found that a delayed `toggle` close event from a
previously expanded relationship row could clear the ID of a newer expanded
row. The handler now clears state only when that row still owns the selected
ID. The component fixture also asserts that closing the comparison removes its
deferred term panels. This change is local frontend state only.

Targeted Prettier and ESLint passed for the component and its fixture under
256 MiB high / 384 MiB max, zero swap, 15% CPU and 48 tasks. No TypeScript or
browser test was rerun. The earlier bounded component run remains
**inconclusive** because its Vitest summary and process exit code were not
retained; the new close assertion is therefore pending browser verification.

At 14:45:39, host available memory was about 10 GiB, free swap about 15 MiB,
and global PSI avg10 was zero (avg300 some/full 0.02/0.01%). The shared
user-manager `memory.events high` count had risen by 32 to 16,437,582 since
14:44:30; the hierarchical counter cannot attribute this to the static checks.
OOM/oom_kill remained 19/15, API/Reality/Reality API remained active at
restart counts 9/14/0, and no kernel or systemd-oomd kill was logged in the
interval. This short sample does not resolve the host incident. Keep browser
and build workloads deferred and continue only serial, offline work after a
fresh admission sample.

## Focused relationship UI verification — 2026-10-29 14:51 CET

The previously inconclusive graph contract-terms component check was rerun
under a bounded transient scope: 512 MiB `MemoryHigh`, 768 MiB `MemoryMax`, no
swap, 20% CPU, 64 tasks, 90-second runtime. After correcting fixture text to
assert the comparison panel's actual combined label and raising only that
long fixture's timeout from five to 15 seconds, the selected test passed
**1/1** (6.0 seconds test time; 22.9 seconds total runner time). It exercises
recorded settlement identity, fee details/evidence, lazy expansion, and
collapse. The earlier attempts failed on fixture text matching and the
default timeout; no OOM or assertion failure remained in the passing run.
No live source, production API, or production store was used.

At 14:51:25, host available RAM was about 10 GiB, free swap about 15 MiB,
global PSI avg10/60/300 some/full was 0/0/0%, and shared-user counters were
high/max/oom/oom_kill = 16,437,686/730,447/19/15, unchanged from the pre-run
sample. API, Reality, and Reality API remained active at restart counts
9/14/0. No kernel OOM or systemd-oomd kill was logged since 14:50:45. This is
a short post-run quiet sample, not incident closure; nearly all swap remains
occupied and the historical pressure initiator is still unattributed.

## Bounded instrument-term comparison work — 2026-10-29 14:59 CET

Frontier's graph contract comparison now also compares recorded instrument
count/outcome identifiers and labels, quote currency and canonical identity,
tick size and increment ranges, quantity unit/step/minimum quantity/minimum
notional, and payout vectors by state. Venue-native instrument IDs remain
visible in the contract detail but are not used as cross-venue match keys.
Input size is bounded at 32 instruments, 64 increments or payouts per
instrument, and 4 KiB per serialized comparison field. Missing or over-limit
detail increments the unavailable count instead of being treated as equal.
The comparison remains literal metadata review, not an equivalence verdict.

The focused pure comparator suite passed **7/7**. Targeted ESLint and
Prettier passed, and the full frontend TypeScript check passed under a
640 MiB high / 768 MiB max, zero-swap, 25%-CPU, 64-task, 120-second scope.
No live source or production store was used. At 14:59:27, host available RAM
was about 10 GiB, free swap 15 MiB, and global PSI avg10/60/300 was zero.
Shared-user high/max/oom/oom_kill counters remained
16,437,686/730,447/19/15; API/Reality/Reality API remained active at restart
counts 9/14/0, and no OOMD or kernel kill was logged since 14:57:45. This is
bounded verification and a brief quiet sample only; swap remains nearly full
and the incident stays partially contained.

## Bounded UI verification — 2026-10-29 15:11 CET

The graph UI fixture starts with only the Polymarket market loaded and
asserts the explicit missing-market state, then refetches a two-market
Polymarket/Kalshi fixture and checks recorded instrument differences in
quote-asset identity, quantity step, and payout vector. The selected
component journey passed **1/1** in a 512 MiB `MemoryHigh` / 768 MiB
`MemoryMax`, zero-swap, 20%-CPU, 64-task scope. Prettier and file-scoped
ESLint passed. No network source, production API, or production store was
used.

At 15:11:30, `MemAvailable` was about 10 GiB, free swap about 15 MiB, and
global PSI some/full avg10/60/300 was zero. API, Reality, and Reality API
remained active at restart counts 9/14/0. The gap-detail timer remained
inactive; the capacity timer was waiting. User-manager `memory.events`
high/max/oom/oom_kill was 16,437,686/730,632/19/15: `max` had increased by
185 from the 14:59 sample while `high`, `oom`, and `oom_kill` were unchanged.
The hierarchical counter cannot attribute that increase to a particular
scope. No kernel or systemd-oomd kill was logged during the short test
interval. This check is bounded UI evidence, not incident closure. Swap is
still nearly exhausted, the user-manager hierarchy remains uncapped, and
pressure initiation is not fully attributed. Continue only serial,
source-independent work after fresh admission checks.

## UI assertion refinement and post-run sample — 2026-10-29 15:14 CET

The graph journey was strengthened to assert the left/right values for all
three instrument differences: fiat USD versus token USD on `eip155:137`,
quantity step 1 versus 0.5, and payout 1 versus 0.99. One intermediate run
failed because the test regex expected unescaped JSON quotes; the rendered
comparison values were present. After correcting the regex to match the
rendered payout-state values, the selected test passed **1/1** (6.6 seconds
test time, 23.1 seconds total) under the same 512/768 MiB, zero-swap, 20%-CPU,
64-task scope. This is a fixture assertion correction, not an application
failure.

At 15:14:15, about 10 GiB RAM was available, swap free was about 15 MiB, and
global PSI was zero. Shared user-manager counters remained
high/max/oom/oom_kill = 16,437,686/730,632/19/15 across the last bounded test;
the prior `max` increase is not attributed. API, Reality, and Reality API
were active at restart counts 9/14/0; the capacity timer was waiting and the
gap-detail timer inactive. No kernel or systemd-oomd kill was logged in the
15:13:40–15:14:15 interval. This remains a brief observation only. Nearly all
swap is occupied, the user-manager hierarchy has no aggregate ceiling, and
the incident remains partially contained.
