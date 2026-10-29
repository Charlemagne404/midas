# MIDAS Host Memory Pressure Incident — 2026-10-29 Follow-up

| Field | Value |
| --- | --- |
| Host | Ubuntu, 16.67 GB RAM, 4.29 GB swap |
| Initial sample | 2026-10-29 04:58 CET |
| Latest addendum | 2026-10-29 06:49 CET |
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
