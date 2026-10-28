# MIDAS Host Memory Pressure and OOM Incident

**Incident date:** 2026-10-28 (CET)

**Checkpoint captured:** 2026-10-29 00:31 CET

**Scope:** Host reliability interruption during Project Frontier

**Frontier branch:** `codex/frontier-20261026`, implementation checkpoint `35cc132bcdc681ec48b79bb07d5e46f9a3f40e5c`

## Executive summary

Repeated systemd-oomd kills were caused by sustained memory pressure in the
whole `user@1000.service` hierarchy: the journal says pressure exceeded the
configured 50% threshold for more than 20 seconds while reclaim was active.
The hierarchy has no `MemoryHigh`, `MemoryMax`, or `MemorySwapMax` ceiling. Its
observed peak was about 13.0 GiB on a host with 15.5 GiB physical memory. The
evidence supports aggregate host memory/reclaim pressure, but does not identify
one workload as the sole cause.

The host had 9.9 GiB `MemAvailable` and low current PSI by the final sample,
but swap remained 3.1 of 4 GiB used. `memory.current` included large file-cache
charges: at 23:51 CET the Terminal slice was 5.2 GB (3.9 GB file cache), MIDAS
API was 1.6 GB (1.5 GB file cache), and Reality was 1.2 GB (1.0 GB file
cache). Process RSS alone therefore understated the cgroup budget in use.

Two narrowly scoped containment changes are in effect:

- The five-minute Veritas gap-detail timer is disabled and stopped. Inspection confirmed
  that it only replays finalized segments, has no reverse dependents, and is
  not part of live Reality collection.
- The Reality capacity monitor has `MemoryHigh=128M`, `MemoryMax=192M`, and
  `MemorySwapMax=0` in a reversible persistent user-unit drop-in. Its previous
  128 MiB hard cap caused seven kernel memcg OOM kills. The 00:16 scheduled
  run avoided an OOM but hit the existing 60-second timeout, so revised-limit
  validation remains incomplete and `capacity.json` is stale.

Reality was killed by systemd-oomd and automatically restarted. Its restart
path fully replays and verifies the recording before resuming collection. At
23:54 CET it remained active but had not written a fresh status since before
the restart and was within 0.8 MiB of `MemoryHigh`. Thus the service process is
alive, but collector recovery and current-boundary capture are not verified.
No operator restart or protected service configuration change was made.

**The host is not yet safe for Frontier tests or research batches.** Continue
only static/documentation work until Reality has demonstrably resumed capture,
service headroom recovers, and memory pressure remains low across multiple
scheduled-job cycles. No new kill was observed through 00:30, about 47 minutes
after the last kill. Current PSI is low, but Reality status is stale, API and
Reality remain near `MemoryHigh`, and the revised capacity limit is unvalidated.

## Observed impact and timeline

### Post-containment sample — 2026-10-29 00:05 CET

At 00:03:14 CET, `free` reported 15 GiB total, 5.6 GiB used, 9.9 GiB
available, and 3.1/4 GiB swap used. Host PSI was `some` 0.00% avg10 / 0.32%
avg300 and `full` 0.00% avg10 / 0.27% avg300. `oomctl dump` showed the
monitored `user@1000.service` at 10.3 GiB with 0.33% avg300 memory pressure.
No new systemd-oomd kill appeared after 23:43:24 CET through 00:05:31 CET.
This is about 22 minutes of quiet after the last kill, not durable recovery.

The effective user-manager policy is `ManagedOOMMemoryPressure=kill` with a
50% per-user PSI threshold. `oomctl` reports a 20-second pressure duration;
the system oomd defaults are 60% and 20 seconds, with a 90% swap-used limit.
Host swap use is below that swap limit. The ten incident journal entries each
name the user-manager pressure threshold and active reclaim as the kill
trigger. Victims were API (three), Reality (two), gap-detail replay (four),
and one GNOME Terminal scope. This identifies the aggregate trigger and
victims, not the sole initiating workload.

At 00:03, API cgroup memory was about 1.61 GB, comprising 1.48 GB file cache
and 129 MB anonymous memory; Reality was about 1.21 GB, comprising 1.07 GB
file cache and 129 MB anonymous memory. Their `memory.events` showed repeated
`high` events (11,558 API; 4,232 Reality) and no leaf `oom` or `oom_kill`
events. Thus `MemoryHigh` reclaim is active, but cgroup totals are not
equivalent to resident process RSS. The restarted Reality process had
`/proc/1235804/io` `read_bytes=3,061,915,648` at 00:05:31; the latest known
status sample at 00:01 still showed the pre-restart 23:43:01 timestamp. Full
replay and renewed capture remain unverified.

At 00:05 CET, the gap-detail timer was disabled and read back as
`inactive/dead`; its service was not running. The capacity monitor's
persistent drop-in was loaded by `systemctl --user daemon-reload`; the service
remained inactive and the effective limits read back as 128M/192M/0 swap. No
service was restarted or manually run. Its next scheduled run is about 00:16
CET. API and Reality remain within roughly 2.4 MiB of their `MemoryHigh`
limits. Continue to defer Frontier runtime work.

At 00:12:15 CET, the host remained at 9.9 GiB available and 3.1/4 GiB swap
used. Host PSI was `some` 0.00% avg10 / 0.02% avg300 and `full` 0.00% avg10 /
0.01% avg300. No new OOMd kill appeared after 23:43:24 CET through this
sample (about 29 minutes). API was active at 1,604,202,496 / 1,610,612,736
bytes `MemoryHigh` (about 6.1 MiB headroom); Reality was active at
1,207,795,712 / 1,207,959,552 bytes (about 160 KiB headroom). Reality's
restarted PID had `read_bytes=4,066,516,992`; there is still no verified fresh
status or capture.

The systemd-oomd daemon is active, and `user@1000.service` remains active with
`ManagedOOMMemoryPressure=kill` and its configured 50% threshold. The user
cgroup's `memory.pressure` file is readable and near zero. However, `oomctl
dump` listed no monitored cgroups at 00:12, although its 00:03 sample listed
`user@1000.service`. The reason is unresolved; the report does not treat the
unit property alone as proof that oomd is currently monitoring that cgroup.
No oomd configuration or service action was taken.

The capacity timer is still active/waiting for 00:16:04 CET; the service has
not been run manually and the new persistent limit has not yet been tested.
The gap-detail timer remains inactive and disabled.

At 00:13:25 CET, a bounded read-only sample still showed 9.9 GiB available,
3.1/4 GiB host swap used, and host PSI at 0.00% avg10 for both `some` and
`full` (avg300 also rounded to 0.00%). The active `user@1000.service` has no
memory or swap cap and currently charges 11.17 GB memory and 1.89 GB swap;
its systemd properties still select `ManagedOOMMemoryPressure=kill`, while
the prior kill journal records the 50%/20s trigger. The unprivileged `oomctl
dump` still lists no monitored groups and reports a zero-byte system context,
so current monitor registration is not independently verified by that query.

The largest current user child slice was `app-org.gnome.Terminal.slice` at
about 5.0 GiB. Its cgroup reported about 3.8 GiB file cache, 0.72 GiB anon,
and 0.47 GiB kernel memory (with shmem reported as a file subcategory). No
single process RSS in the sampled process list approached the slice total.
This is a current charge snapshot, not proof that the Terminal slice caused
the earlier pressure episodes. API and Reality remain active but within
about 1.6 MiB and 0.2 MiB of their respective `MemoryHigh` limits. No new
OOM kill appeared through 00:13:25 CET, about 30 minutes after the last one.

The next Veritas research-director timer is at 00:15:04, the capacity timer at
00:16:04, the observation pilot at 00:30, and source analysis at 00:40:40.
The inspection found no queued user-manager jobs. The 30-minute research
timers remain enabled because no evidence ties their bounded successful runs
to the previous kills; avoid launching any additional research work during
this observation window.

The scheduled capacity service did start at 00:16:04 but failed at 00:17:04
with `Result=timeout`: the existing `TimeoutStartSec=60` sent SIGTERM. It used
6.39 seconds of CPU over the minute. The effective `MemoryHigh=128M`,
`MemoryMax=192M`, and `MemorySwapMax=0` were in force. No kernel OOM or OOMd
kill was logged; user-manager `oom`/`oom_kill` counters remained 19/15 from
the 00:13 sample. systemd did not retain a service `MemoryPeak` after failure,
so the revised memory bound is not yet validated. `capacity.json` remains
unchanged with mtime 23:46:11 CET. The 60-second timeout itself is configured
in the existing service unit and was not changed.

At about 00:18 CET, host PSI was `some` 0.01% avg10 / 6.09% avg60 / 4.74%
avg300 and `full` 0.01% / 5.06% / 3.86%; available memory remained 9.9 GiB.
User-manager PSI was similarly 0.01% avg10, with avg60 near 6% and avg300
near 4%. These averages reflect a recent interval and do not identify the
capacity process as their cause. The archive mount is currently local ext4
(`/dev/sda4`); the process's low CPU time and timeout establish a long wait,
but the specific I/O or memory wait remains unknown.

Source inspection found a plausible memory-scalability defect in the
capacity path: when archive provenance is invalid, it discarded the catalog
and built an in-memory dictionary of every archive directory entry before
statting them. The inventory size and killed-run peak were not captured, so
this is a demonstrated unbounded code path and a plausible contributor, not
a proven attribution for the historical OOMs. An isolated candidate at
`/home/charlie/midas-reality-capacity-scan-frontier-20261029`, commit
`8b2131faf40ddd06c8dff155169bddec7048c807`, streams inventory entries and
stops after 65,536 entries. Follow-up commit
`9868dac2bdc762a5f6c29cbeeda88a13fed8075e` skips the directory walk entirely
when manifest provenance is invalid, reporting unknown archive bytes and
headroom. The saved 23:46 report records `INVALID_MANIFEST`, 18,695 catalog
segments, and 5,393,427,930 archive bytes; the manifest itself is 7,406,466
bytes. Commit `7e637a9b78155e8b0bc16361cefb18f0b2f34935` caps archive-manifest
input at 4 MiB and reports larger manifests as unverified without parsing or
scanning. All three fixtures were added but not run. The candidate is not deployed into
`/home/charlie/midas-reality`; no archive or Reality service was modified.

At 00:22 CET, host PSI had fallen to 0.00% avg10 / 2.16% avg300 `some` and
0.00% / 1.75% `full`; `MemAvailable` was about 10 GiB and swap remained
3.1/4 GiB. API was active at 1,607,528,448 / 1,610,612,736 bytes `MemoryHigh`
(about 2.9 MiB headroom); Reality was active at 1,207,767,040 /
1,207,959,552 bytes (about 0.18 MiB headroom). The actual collector root is
`/home/charlie/midas-reality/data/recordings/reality`; its `status.json` still
has mtime 23:43:01 CET and state `DEGRADED_SOURCE_TIMING`. Manifest/capture
freshness and recovery therefore remain unverified. No new OOM kill appeared
through this sample.

At 00:25 CET, `MemAvailable` was about 10 GiB, swap remained 3.1/4 GiB, and
host PSI was 0.00% avg10 / 1.04% avg300 `some` and 0.00% / 0.84% `full`. No
OOMd or kernel OOM entry appeared after 23:43:24. API and Reality remained
active; their last measured cgroup usage at 00:22 was still within 2.9 MiB
and 0.18 MiB of `MemoryHigh`. Reality `status.json` remained stale at 23:43:01
with `DEGRADED_SOURCE_TIMING`. The capacity timer remains active, next due
00:46; no manual run was started.

At 00:30:19 CET, host `MemAvailable` was 9.9 GiB and swap remained 3.1/4 GiB.
Host PSI was 0.00% avg10 / 0.37% avg300 `some` and 0.00% / 0.29% `full`;
user-manager PSI avg300 was 0.35% / 0.31%. The scheduled Veritas observation
pilot ran from 00:30:01 to 00:30:13 and exited successfully; no OOM entry
appeared in this window. This one bounded run does not establish sustained
recovery or prove the pilot cannot contribute under different conditions.
API was active at 1,609,224,192 / 1,610,612,736 bytes `MemoryHigh` (1.32 MiB
headroom); Reality was active at 1,204,600,832 / 1,207,959,552 bytes
(3.20 MiB headroom). Their restart counters remained at 9 and 14. Reality
`status.json` was rechecked and remained at 23:43:01 CET with
`DEGRADED_SOURCE_TIMING`. The research-director run at 00:15:04 completed at
00:15:05, so it did not overlap the 00:16 capacity run.

At 00:30:58, Reality PID 1235804 was still running in state `R` with
`VmRSS=135,148 kB`; `/proc/1235804/io` showed 6,868,652,032 `read_bytes` and
4,096 `write_bytes`. The same PID had read 4,066,516,992 bytes at 00:12:15,
so another 2.80 GB had been read in 18 minutes 43 seconds. Its cgroup was
1,207,947,264 / 1,207,959,552 bytes at `MemoryHigh`, leaving about 12 KiB.
`status.json` remained at 23:43:01 with `DEGRADED_SOURCE_TIMING`. This is
evidence that the automatic restart is still replaying/reading the recording;
it has not demonstrated return to live capture. Do not restart or reconfigure
the collector, and do not resume Frontier runtime work.

At 00:31:49, the user-manager cgroup charged 11,157,987,328 bytes of memory
and 1,893,208,064 bytes of swap; user PSI avg300 was 0.26% `some` / 0.22%
`full`. The Terminal app slice was 5,474,066,432 bytes (4,123,885,568 file,
841,838,592 anon, and 506,671,104 kernel); API was 1,608,781,824 bytes
(1,481,334,784 file / 125,706,240 anon), and Reality was 1,204,981,760
(1,080,209,408 file / 122,904,576 anon). This is a current charge snapshot,
not attribution of the earlier pressure. Host `MemAvailable` remained about
10 GiB.

### systemd-oomd kills

The journal contains ten kills from 21:51 through 23:43 CET. All explicitly
cite user-session memory pressure greater than 50% for over 20 seconds with
reclaim activity:

| CET | Killed unit/scope | User-session pressure |
| --- | --- | ---: |
| 21:51:21 | `midas-reality.service` | 54.27% |
| 21:51:37 | `midas-api.service` | 50.01% |
| 23:23:00 | `midas-api.service` | 57.60% |
| 23:23:16 | `midas-veritas-gap-detail-v2.service` | 52.03% |
| 23:28:28 | `midas-veritas-gap-detail-v2.service` | 63.62% |
| 23:32:57 | `midas-api.service` | 62.37% |
| 23:33:14 | GNOME Terminal `vte-spawn` scope | 52.86% |
| 23:38:28 | `midas-veritas-gap-detail-v2.service` | 59.80% |
| 23:43:09 | `midas-reality.service` | 61.64% |
| 23:43:24 | `midas-veritas-gap-detail-v2.service` | 54.45% |

API was automatically restarted at 23:33:08 CET. Reality was automatically
restarted at 23:43:19 CET. These service restart counters (`NRestarts=9` for
API and `14` for Reality) are lifetime values, not counts attributable solely
to this incident. The gap-detail oneshot repeatedly failed with
`Result=oom-kill`; its last run reached 204.8 MiB and local memory PSI of
76.50% avg10 / 50.59% avg60. At that time it was below its 256 MiB hard cap,
so the logged kill was the ancestor pressure action, not its `MemoryMax`.

Separately, kernel memcg OOM repeatedly killed the Reality capacity process
inside `midas-reality-capacity.service` at 17:15:21, 17:45:22, 18:15:40,
18:45:40, 19:15:40, 19:45:40, and 20:15:44. Each kernel record names the
service cgroup as `oom_memcg` and shows approximately 129–131 MiB anonymous
RSS plus about 11 MiB file RSS against `MemoryMax=128M`. Later scheduled runs
succeeded; the 23:46:11 run used 77.2 MiB peak and no swap. The hard cap is the
demonstrated local OOM trigger. Why the workload crossed it in those seven
runs but not later remains unproven.

### Resource snapshots

At 23:49 CET, `free` reported 15 GiB total, 5.6 GiB used, 360 MiB free,
10 GiB buff/cache, 9.9 GiB available, and 3.1/4 GiB swap used. At 23:51:44,
host memory PSI was `some` 0.00% avg10 / 3.82% avg300 and `full` 0.00% avg10 /
3.28% avg300. User-session PSI was `some` 0.00% avg10 / 4.48% avg300 and
`full` 0.00% avg10 / 4.17% avg300. These are recovery-period measurements;
they do not contradict the earlier sustained pressure recorded by oomd.

The user hierarchy’s 23:49 sample was 11.18 GB current and 13.99 GB peak. Its
`memory.high`, `memory.max`, and `memory.swap.max` were all `max`. The hierarchy
had 1.89 GB swap current; total host swap use was larger. Descendant counters
were cumulative: `high=16,377,206`, `max=728,363`, `oom=19`, `oom_kill=15`.
These counters cannot be assigned to one child workload.

At 23:51 the largest identified application cgroups included:

| Cgroup | `memory.current` | File cache | Anonymous |
| --- | ---: | ---: | ---: |
| `app-org.gnome.Terminal.slice` | 5.19 GB | 3.91 GB | 0.78 GB |
| `midas-api.service` | 1.60 GB | 1.48 GB | 0.13 GB |
| `midas-reality.service` | 1.19 GB | 1.05 GB | 0.14 GB |

The file figures are cgroup accounting, not attribution to a specific file or
command. Terminal’s slice includes several live scopes and accumulated parent
cache; the snapshot does not identify which historical command populated it.
The API’s and Reality’s page-cache origin also remains unknown. At the OOMd
decision points for API and Reality, oomd candidate output showed zero local
PSI for those leaves while the parent user hierarchy was over threshold. This
supports an ancestor-pressure diagnosis rather than a service-specific hard
limit for those kills.

## Root-cause assessment

### Demonstrated

1. **The immediate systemd-oomd trigger was user-session memory pressure with
   reclaim.** The journal gives the measured parent PSI, 50% limit, 20-second
   duration, and reclaim condition for each victim.
2. **The user hierarchy was not constrained by a cgroup hard memory ceiling.**
   Its effective memory and swap limits and those of its inspected ancestors
   were unlimited. The peak and swap measurements indicate the host’s physical
   memory/reclaim budget was tight at incident peaks.
3. **The capacity monitor’s 128 MiB hard cap caused its repeated local OOMs.**
   Kernel records show the service cgroup as the memcg OOM domain and process
   RSS at or over the cap.
4. **The gap-detail timer created avoidable workload churn.** It fired every
   five minutes, ran replay/analysis over finalized Reality data, and was not
   required for live capture or integrity. It also suffered local replay
   pressure while the parent user hierarchy was under pressure.
5. **Reality’s automatic restart is performing full cold replay before live
   collection resumes.** On the `project/reality` source at `4f5cb56`,
   `packages/midas/reality/collector.py` calls `manifest(root)` and
   `replay(root, source_manifest)` before `store.activate()`. At the 23:51
   sample the restarted PID had read about 1.08 GB from storage, used about
   1.00 GB cgroup file cache, and had not advanced `status.json` since
   23:43:01. The latest segment finalization was 23:43:31. At 23:54 the
   service cgroup was 1,207,193,600 / 1,207,959,552 bytes at `MemoryHigh`.
   No established TCP connection was listed for that PID in the 23:51 sample.
   These facts show that the collector had not yet demonstrated resumed live
   capture; they do not prove why the prior system-wide pressure began.

### Plausible capacity-monitor contributors (causal link unverified)

The 23:46 saved capacity report showed the archive as `INVALID_MANIFEST`, with
18,695 catalog segments and 5,393,427,930 reported archive bytes; its
manifest file was 7,406,466 bytes. In the protected source, the capacity path
loads all raw segment sidecars through `manifest(root)`. When archive
provenance is invalid, the older `archive_capacity` path also materialized
every directory entry in a dictionary and statted the inventory. These are
workloads whose memory and I/O grow with recording/archive size. The 00:16
run consumed 6.39 CPU seconds before waiting until the existing 60-second
timeout, consistent with an I/O-bound scan but not proof of it. The old OOM
records do not contain a per-run peak or allocation trace, so the precise
reason the process exceeded 128 MiB remains unproven.

The isolated source candidate bounds valid inventory walks and skips the
directory walk when provenance is invalid, returning unknown bytes/headroom.
Its fixtures remain unrun, and it is not deployed. It does not repair or
reclassify the existing archive.

### Not established

- No individual workload was proven to be the sole or dominant source of the
  23:23–23:43 system-wide pressure. The large Terminal, API, and Reality file
  cache charges are substantial, but page-cache attribution is incomplete and
  a current snapshot cannot reconstruct the incident peak.
- Frontier tests were not running during the OOMd kill cluster. The last
  bounded Frontier checks occurred earlier; no evidence ties them to the
  incident. No new Frontier test or research process was started during this
  incident response.
- The Arena scheduler continued to run its one-second dispatcher and reported
  `schedules: []`; the evidence does not show it as a material load source.
- The archive’s `INVALID_MANIFEST`, segment inventory, and provenance warnings
  are separate integrity findings. No manifest or recording data was edited.
- The timing of the original 128 MiB capacity cap, user-manager oomd policy,
  and research timer installations relative to the first incidents has not
  been reconstructed; no configuration-change correlation is claimed.
- The state after the 23:43 Reality restart is not proven to meet the latest
  collection boundary. The report does not claim recovery or data continuity.

## Changes made and rollback

### Stopped auxiliary gap-detail timer

Inspection confirmed the timer was scheduled every five minutes
(`OnCalendar=*-*-* *:02/5:00 UTC`), `Persistent=false`, and launched a oneshot
that replays finalized Reality segments into Veritas gap-detail/Arena outputs.
The unit did not collect live market data. Reverse dependency inspection found
no other units requiring the timer. The timer was stopped through the user
systemd manager and inactive by 23:49 CET, then disabled at 00:05 CET so it
stays stopped across a user-manager restart. It remains a reversible user-level
unit change.

Rollback / resume:

```sh
systemctl --user enable --now midas-veritas-gap-detail-v2.timer
```

No replay service was manually started and no Arena or Veritas evidence was
modified.

### Bounded the Reality capacity monitor with a reversible override

The unit runs about every 30 minutes, is a `Type=oneshot`, has a 60-second
timeout, and writes only the capacity report. Before this incident change it
had `MemoryMax=128M`, no explicit `MemoryHigh`, and unlimited swap. A runtime
override set `MemoryHigh=128M`, `MemoryMax=192M`, and `MemorySwapMax=0`.
At 00:05 CET, the same values were made persistent in
`~/.config/systemd/user/midas-reality-capacity.service.d/90-frontier-memory-bound.conf`.
The effective properties read back successfully after user-manager reload;
the service was inactive, so no running job or live collector was restarted.
The scheduled 00:16 run was terminated at 00:17 by the existing 60-second
start timeout. No kernel OOM was logged, but systemd did not retain its peak
memory, so the revised limit is not validated.

Rollback the effective memory properties:

```sh
rm ~/.config/systemd/user/midas-reality-capacity.service.d/90-frontier-memory-bound.conf
systemctl --user daemon-reload
systemctl --user set-property --runtime midas-reality-capacity.service \
  MemoryHigh=infinity MemoryMax=128M MemorySwapMax=infinity
```

The override is scoped to this short monitor. It does not relax limits on
Reality, API, or any other unit. The next scheduled run is 00:46 CET; it must
complete before runtime behavior under the new bound can be validated.

## Services and other infrastructure

- `midas-api.service`: active at 23:54 CET, PID 1218662; 1,604,112,384 bytes
  current against 1,610,612,736 `MemoryHigh` and 1,879,048,192 `MemoryMax`;
  `MemorySwapMax=0`. Its cgroup had about 1.48 GB file cache and 128 MB
  anonymous memory. It had been automatically restarted after the 23:32:57
  oomd kill. API health was not probed, so active state is not an end-to-end
  readiness claim.
- `midas-reality.service`: active at 23:54 CET, PID 1235804, automatically
  restarted after the 23:43:09 oomd kill; its full-replay recovery and live
  capture remain unverified. Its `MemoryHigh` headroom was under 1 MiB.
- `midas-reality-capacity.service`: its 00:16 scheduled run was terminated by
  the pre-existing 60-second timeout at 00:17:04. No kernel OOM was logged;
  `capacity.json` remains at its 23:46:11 mtime and the next timer is 00:46.
- `midas-veritas-gap-detail-v2.service`: most recent oneshot ended with
  `oom-kill`; its timer is now stopped.
- Continental user services `continental-cloud-tailnet.service` and
  `continental-id-auth.service` were active. Echo production and staging
  system services were active. RustDesk was active and `ssh.socket` was
  listening. No action was taken on these services.
- A separate scheduled, read-only Continental infrastructure audit ran at
  23:52:23 and exited 1 at 23:52:24. Its output cited TCP listeners on
  `0.0.0.0:8081` and `0.0.0.0:5174`, plus `echo-offsite-schedule: disabled`.
  This is a separate audit finding, with no demonstrated relation to memory
  pressure; it was not changed in this response.

## Validation and continuation gate

Read-only validation after the containment actions confirmed:

- The gap-detail timer is `inactive/dead` and `disabled`; its last trigger
  remains 23:42:14 CET. Restore with `systemctl --user enable --now
  midas-veritas-gap-detail-v2.timer` after admission review.
- Capacity monitor effective properties read back as `128M` high, `192M` max,
  and swap max `0`, backed by the persistent `90-frontier-memory-bound.conf`.
  Its 00:16 run timed out after 60 seconds without a kernel OOM; peak memory
  was unavailable and the updated limits are not validated.
- At 23:51:44 host PSI avg10 was 0%, avg300 was 3.82%; there were no new oomd
  kill entries after 23:43:24 through that sample. The quiet interval was only
  about eight minutes total and about five minutes after stopping the timer.
- At 23:55:33 host PSI remained 0% avg10 and had fallen to 1.71% `some` /
  1.47% `full` avg300; user-session PSI avg300 was 2.01% / 1.87%. No new oomd
  kill entries appeared after 23:43:24. Host swap remained 3.1/4 GiB used.
- At 23:55 Reality remained active at 1,207,398,400 / 1,207,959,552 bytes
  `MemoryHigh` (about 0.5 MiB headroom), while API was active at
  1,605,521,408 / 1,610,612,736 bytes (about 4.9 MiB headroom). Reality's
  status timestamp remained 23:43:01 CET. The quiet period was about 12
  minutes after the last kill and at least six minutes after the gap timer
  stop, still too short to establish durable recovery.
- A 23:57:49 recheck showed no new oomd kills, host PSI `some` 0.00% avg10 /
  1.06% avg300 and `full` 0.00% avg10 / 0.91% avg300; user-session PSI
  avg300 was 1.59% / 1.47%. Host swap remained 3.1/4 GiB used. API was
  1,604,886,528 / 1,610,612,736 bytes at `MemoryHigh`; Reality was
  1,207,611,392 / 1,207,959,552 bytes. Reality status was still unchanged
  since 23:43:01. Its restarted PID had read 2.08 GB from storage by this
  sample while `storage_bytes` in the pre-kill status was 12.13 GB. This
  confirms replay work continues, but does not establish its completion time
  or resumed capture.
- API, Reality, Continental, Echo, RustDesk, and the SSH socket were observed
  active as described above. Reality’s fresh capture was not verified.
- No stress test, service restart, cache drop, broad test suite, public source
  probe, campaign, or data repair was performed.

**Status: containment applied; incident unresolved.** Current low PSI does not
establish durable host recovery. A safe Frontier testing gate requires all of:

1. A fresh Reality status timestamp and newly persisted observations after the
   automatic restart, showing that startup replay has completed and capture is
   again active. Do not restart the service to obtain this evidence.
2. API and Reality `MemoryHigh` headroom materially above the current
   near-zero margins, with host and user-session PSI remaining low across
   multiple scheduled job cycles.
3. No new systemd-oomd or kernel memcg OOM events during that observation
   window.
4. The capacity timer completes its next bounded run under the persistent cap.
5. The gap-detail timer remains disabled until replay scheduling and aggregate
   memory admission are reviewed; restarting it is available through the
   rollback command above.

Frontier's isolated source commit `35cc132` adds the user-manager cgroup PSI
to Arena, schedule, Laboratory, and gap-replay admission. Fixture
coverage was added but not run, and the change is not deployed. It is not
counted as current host protection; no worker or service was started for this
change.

Until then, Frontier may continue static/documentation work only. Do not run
tests, replays, live probes, or batch research. Continue to preserve the
untracked `data/frontier-public-probes/` and all Reality/Veritas/Arena data.
