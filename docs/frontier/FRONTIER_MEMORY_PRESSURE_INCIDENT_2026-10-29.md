# MIDAS Host Memory Pressure Incident — 2026-10-29 Follow-up

| Field | Value |
| --- | --- |
| Host | Ubuntu, 16.67 GB RAM, 4.29 GB swap |
| Sample time | 2026-10-29 04:58 CET |
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
