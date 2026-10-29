# MIDAS Host Memory Pressure and OOM Incident

**Incident date:** 2026-10-28 (CET)

**Initial checkpoint:** 2026-10-29 01:54 CET; append-only follow-up observations
through 2026-10-29 03:44 CET are recorded below.

**Scope:** Host reliability interruption during Project Frontier

**Frontier branch:** `codex/frontier-20261026`, implementation checkpoint `35cc132bcdc681ec48b79bb07d5e46f9a3f40e5c`

## Executive summary

Repeated systemd-oomd kills followed sustained memory pressure in the whole
`user@1000.service` hierarchy: the journal says pressure exceeded 50% for more
than 20 seconds while reclaim was active. The hierarchy has no `MemoryHigh`,
`MemoryMax`, or `MemorySwapMax` ceiling. Its observed peak was about 13.0 GiB
on a host with 15.5 GiB physical memory. This establishes hierarchical
reclaim pressure, not global physical-memory exhaustion, and does not identify
one workload as the sole cause.

At 01:51:59 CET, host `MemAvailable` was 10 GiB and PSI avg10/avg60/avg300
was zero, but swap remained 3.1 of 4 GiB used. The 01:50:35–01:51:05 sample
showed substantial file-cache charges: MIDAS API was about 1.535 GiB
(1.414 GiB file cache, 118 MiB anonymous), a GNOME Terminal scope was about
1.214 GiB (778 MiB file, 412 MiB anonymous), and Reality was about 553 MiB.
Process RSS alone therefore understates the cgroup budget in use.

Two narrowly scoped containment changes are in effect:

- The five-minute Veritas gap-detail timer is disabled and stopped. Inspection confirmed
  that it only replays finalized segments, has no reverse dependents, and is
  not part of live Reality collection.
- The Reality capacity monitor has `MemoryHigh=160M`, `MemoryMax=192M`, and
  `MemorySwapMax=0` in a reversible persistent user-unit drop-in. Its previous
  128 MiB hard cap caused seven kernel memcg OOM kills. The 00:46 scheduled
  run completed in 33.3 seconds at a 137.4 MiB peak, but the old 128 MiB soft
  limit caused measurable reclaim PSI. The new 160 MiB soft limit has one
  measured scheduled run at 01:16 (134,225,920-byte peak) and a second
  successful scheduled run at 01:46; the latter's peak was not retained.
  Both capacity reports preserve the invalid archive provenance/inventory
  warnings. The 01:46 report shows a fresh but unsequenced collector status.

Reality was killed by systemd-oomd and automatically restarted. Its restart
path fully replays and verifies the recording before resuming collection. At
01:07 CET it wrote fresh status: `RECORDING_UNSEQUENCED`,
`collection_health=active_receiving`, 16/16 fresh books, zero failures, and
`backpressure_active=false`. Its storage count exceeded the 00:46 capacity
snapshot by 512 KiB at 01:07 and continued to grow through 01:08, confirming
new persisted observations after cold replay. Recovery and current capture
are now demonstrated, with `sequence_verified=false` still explicit. No
operator restart or protected Reality configuration change was made.

**The host supports short, strictly bounded offline tests but not broad suites
or research batches yet.** No new oomd or kernel OOM kill was observed through
01:51, more than two hours after the last kill. Host PSI is zero and 10 GiB is
available, but swap remains 3.1/4 GiB used. API and Reality are active; at
01:51:59 the API was within 512,000 bytes (0.49 MiB) of `MemoryHigh`, and
Reality was within about 598 MiB. Their leaf `max`, `oom`, and `oom_kill`
counters were zero. The original workload mix that crossed the user-manager
pressure threshold is still unknown, so this quiet interval does not establish
incident resolution.

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
   A retrospective journal count from 16:00 through 23:44 CET found 28
   victim events: 16 gap-detail replay, 5 Reality, 4 API, and 3 GNOME
   Terminal scopes. This count describes victims, not initiators.
2. **The user hierarchy was not constrained by a cgroup hard memory ceiling.**
   Its effective memory and swap limits and those of its inspected ancestors
   were unlimited. The observed 3.1/4 GiB host swap use is evidence of prior
   swap activity, but available post-incident RAM and absent contemporaneous
   peak measurements do not establish global exhaustion.
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
Static review found that the size check followed by `Path.read_text()` still
left a file-growth race. Isolated candidate commit
`d8629e4b63c8b8ef68e27294fb3599423a694b76` now opens a regular manifest
without following symlinks, checks the opened descriptor, and reads at most
4 MiB plus one byte. A fixture simulates a stale path-level size. All three
new candidate fixtures later pass in bounded runs below; the rest of the
Reality test file remains unrun. The branch is not deployed. It does not
repair or reclassify the existing archive.

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

## Follow-up observation — 2026-10-29 00:40 CET

Read-only checks found the capacity timer enabled and waiting for its scheduled
00:46:04 CET trigger. The previous run remains a timeout at 00:17:04; the
service retains `TimeoutStartSec=60`, `MemoryHigh=128M`, `MemoryMax=192M`, and
`MemorySwapMax=0`. No manual invocation was made. The gap-detail timer remains
inactive. Its service's displayed `oom-kill` result is the historical result
from before containment, not a new kill.

At 00:40:07 CET, host memory was 5.7 GiB used / 9.9 GiB available, with
3.1/4 GiB swap used. Host PSI was `some avg10=0.00%, avg60=0.00%,
avg300=0.02%` and `full avg10=0.00%, avg60=0.00%, avg300=0.00%`. The user
manager cgroup held 11,160,563,712 bytes and 1,893,208,064 bytes of swap;
its PSI was `some avg300=0.02%`, `full avg300=0.01%`. Parent cgroup counters
remain `high=16,402,853`, `max=728,363`, `oom=19`, `oom_kill=15`; no increase
has been observed since 00:13. No oomd or kernel OOM journal entry appeared
in the post-23:43:24 interval queried at this check.

The API was active at 1,609,175,040 / 1,610,612,736 bytes `MemoryHigh`
(1,437,696 bytes remaining); Reality was active at 1,207,640,064 /
1,207,959,552 bytes (319,488 bytes remaining). Reality's `status.json` still
has its 2026-10-28 23:43:01.187 CET timestamp. Thus the low PSI sample does
not establish recovery: the two protected services remain almost exactly at
their soft limits and post-restart capture is still unverified.

The next action is a passive sample during the already scheduled 00:46
capacity invocation. The service cgroup can disappear after the oneshot exits,
so read `memory.current`, `memory.peak`, `memory.events`, and `memory.pressure`
while it is active. Do not manually start the unit, extend its timeout, alter
the Reality unit, or interpret a short quiet interval as closure. If the run
times out, record the failure and keep Frontier runtime work deferred.

## Scheduled capacity run and follow-up — 2026-10-29 00:47 CET

The timer fired normally at 00:46:04 CET. The capacity job completed at
00:46:37, within its existing 60-second timeout, after 6.520 CPU seconds.
Systemd recorded a 137.4 MiB peak, zero swap peak, and `Result=success`;
`MemoryPeak=144,093,184`, below the 192 MiB hard limit. While active, the
cgroup reported `high=1,731`, `max=0`, `oom=0`, and `oom_kill=0`. It reached
144,093,184 bytes at 00:46:28 under the 128 MiB `MemoryHigh`; cgroup PSI then
showed `some/full avg10=48.01%`, avg60=12.77%, avg300=2.87%. At the same
sample host PSI was `some avg10=32.46%` / `full avg10=15.66%`, and the user
manager was `some avg10=31.12%` / `full avg10=14.42%`. About 20 seconds after
the service ended, host/user avg10 had fallen to about 1–2%, while rolling
avg300 `full` remained 1.53–1.65%. This is direct evidence that the service
crossed its soft bound and experienced reclaim stalls, and a time-correlated
host/user PSI spike; it does not prove it caused all of the historical OOMd
events.

The fresh report at `/home/charlie/midas-reality/data/recordings/capacity.json`
was written at 00:46:37 (4,539 bytes). It records 12,133,299,450 bytes under
the active Reality recording root and retains the alerts
`ARCHIVE_SEGMENT_INVENTORY_INVALID`, `ARCHIVE_MANIFEST_PROVENANCE_INVALID`,
and `COLLECTOR_STATUS_STALE` (as well as pending budget/retention restart and
capacity-window warnings). The archive manifest or history was not changed.
Reality `status.json` remained timestamped 23:43:01.187 CET.

In response to the measured `MemoryHigh` reclaim, the auxiliary capacity
service's persistent drop-in now sets `MemoryHigh=160M`, keeping
`MemoryMax=192M` and `MemorySwapMax=0`. `daemon-reload` applied the properties
for future invocations only; the completed job was not restarted. This adds
32 MiB of soft-threshold room while preserving the existing hard cap. Roll
back this incremental adjustment with:

```sh
sed -i 's/^MemoryHigh=160M$/MemoryHigh=128M/' \
  ~/.config/systemd/user/midas-reality-capacity.service.d/90-frontier-memory-bound.conf
systemctl --user daemon-reload
```

At 00:47:43 CET, 10 GiB was available and no new oomd or kernel OOM record
appeared after 23:43:24. Host/user avg10 PSI had fallen below 0.1%; however,
avg60 `full` was 2.70–2.89% and avg300 `full` 1.53–1.65%. API and Reality
were active at 1,609,244,672 / 1,610,612,736 bytes and 1,207,644,160 /
1,207,959,552 bytes, respectively. These small margins and stale Reality
status keep production recovery unverified. The capacity timer's next run is
01:16:04 CET; observe it passively to validate the 160 MiB threshold.

### Workload and cause attribution update

The measured scheduler inventory shows `midas-arena-scheduler.timer` polling
once per minute with a 512 MiB service hard cap and 60-second timeout; its
last service CPU accounting was 0.034 seconds. The Veritas observatory,
source-analysis, and research-director timers run every 30 minutes, staggered
at approximately :00, :10, and :15 UTC, with 256/512 MiB service hard caps.
Recent runs completed and their CPU accounting was 1.69, 5.75, and 1.34
seconds, respectively. The observed capacity run began 56 seconds after the
director trigger; no overlap was demonstrated in those unit states. These
snapshots do not exclude brief scheduler overlaps in earlier incidents.

The oomd mechanism is established by its journal: it killed candidates after
the `user@1000.service` slice exceeded its 50% pressure threshold for more
than 20 seconds with reclaim activity. The separate kernel memcg OOM mechanism
is established for the old capacity unit: its 128 MiB hard cap killed the
capacity process seven times after recorded RSS of roughly 129–131 MiB plus
file-backed charge. This run validates completion under the new 192 MiB hard
cap. The workload that originally drove repeated user-slice pressure high
enough to trigger oomd remains **unproven**. Earlier Terminal-slice, API, and
Reality charges are time-specific and mostly file-backed; none identifies
the historical trigger by itself. Oomd registration is also not confirmed by
the unprivileged `oomctl` view.

**The broad Frontier runtime gate remains closed.** The capacity run
temporarily raised full PSI, the protected services remained close to their
soft limits, and Reality had not published post-restart capture status. Keep
full suites, replay, probes, and batches deferred until rolling pressure
recovers and the next scheduled capacity check confirms the revised soft
threshold behaves without a comparable reclaim spike.

## Protected-service and scheduler recheck — 2026-10-29 00:50 CET

At 00:50:25, API and Reality remained active with restart counters 9 and 14.
The API cgroup was 1,609,125,888 / 1,610,612,736 bytes `MemoryHigh` and Reality
was 1,207,750,656 / 1,207,959,552 bytes. Both service-level memory PSI
`avg10/avg60/avg300` was 0.00% in this sample. The API cgroup's 1.482 GB
file-backed charge was almost entirely inactive file cache, against 125 MB
anonymous memory; Reality's 1.082 GB file charge was likewise almost entirely
inactive cache, against 124 MB anonymous memory. This explains why cgroup
accounting is near `MemoryHigh` while process RSS is about 143 MB for the API
and 133 MB for Reality. It does not show current stalls in those two leaf
cgroups.

The user-manager cgroup had no `MemoryHigh` or `MemoryMax`. Its `memory.stat`
sample was 1.96 GB anon, 8.00 GB file, 1.15 GB kernel, including 6.22 GB
inactive file. Its `memory.events` now reads `high=16,411,152`,
`max=728,363`, `oom=19`, `oom_kill=15`; `high` rose 8,299 from the 00:40
sample, but `max` and OOM counters did not change. This increment is not
attributed to a particular service. At 00:50:25 its PSI was `some
avg10/avg60/avg300=0.00/0.26/1.30%`, `full=0.00/0.17/0.86%`. The system-scope
`user@1000.service` still has `ManagedOOMMemoryPressure=kill`; the historical
oomd journal specifies the observed 50% for 20 seconds trigger. There is no
user-slice hard memory cap.

The Reality process's `read_bytes` reached 9,715,167,232 at 00:49:28, up
2,846,515,200 bytes from 00:30:58, while `status.json` remained timestamped
23:43:01.187. This confirms continued cold-replay reads without fresh capture
attestation. Do not interrupt it.

Scheduler logs now give exact bounded-run intervals: Arena dispatches lasted
about 34 ms each minute; the 00:46:04.373 dispatcher completed at 00:46:04.408,
before the capacity job started at 00:46:04.556. The 00:45:08.764 Research
Director run completed at 00:45:10.157, before capacity began. The recent
Veritas observation and source-analysis runs lasted 12.2 and 5.9 seconds;
the samples show no actual overlap with the 00:46 capacity run. All observed
Midas/Reality interfaces, Continental services, Echo production/staging,
RustDesk, and `ssh.socket` were active at the checks; none was changed. The
only unit configuration change was the auxiliary capacity monitor drop-in.
These recent successful short runs do not disprove earlier timer overlap or
identify the historical oomd pressure initiator.

The specific OOMd trigger and old capacity hard-limit failure are demonstrated;
the workload that produced the historical 50% user-slice pressure is not.
Disabling the five-minute auxiliary gap-detail timer, bounding the capacity
hard limit, and observing no new OOM for over an hour are favorable evidence,
not proof of a single root cause or durable closure. The 160 MiB capacity
soft threshold has not yet been exercised; next scheduled run remains
01:16:04 CET. Keep Frontier tests and experiments deferred until that run and
the protected Reality recovery/readiness conditions are met.

## Near-bound Reality recheck — 2026-10-29 00:54 CET

At 00:54:24 CET, host memory remained 5.4 GiB used / 10 GiB available, with
3.1/4 GiB swap used. Host PSI was `some` avg10/avg60/avg300
0.00/0.00/0.62%, `full` 0.00/0.00/0.39%; user-manager PSI was
`some` 0.00/0.00/0.55%, `full` 0.00/0.00/0.36%. No new oomd or kernel OOM
record appeared after 23:43:24. Parent cgroup `high` increased another 2,605
to 16,413,757 since 00:50; `max=728,363`, `oom=19`, and `oom_kill=15` stayed
unchanged. This is not attributed to a specific workload.

API was active at 1,609,302,016 / 1,610,612,736 bytes `MemoryHigh` (about
1.25 MiB headroom). Reality was active at 1,207,951,360 / 1,207,959,552
bytes, leaving only 8 KiB. Its leaf PSI was 0.00% avg10/avg60/avg300, but
near-zero headroom plus stale `status.json` means replay/capture recovery is
still not verified. The memory-admission hold remains in place despite the
lower host and parent PSI. Arena's minute dispatcher continued to report
`schedules: []` at 00:50–00:54. Keep Frontier runtime work paused; the next
capacity run under `MemoryHigh=160M` is 01:16:04 CET.

At 00:54:52, a read-only recheck confirmed no new oomd or kernel OOM entries
after 23:43:24 and the same stale Reality status timestamp. Reality remained
active; its cgroup current had fallen to 1,207,762,944 bytes, leaving about
192 KiB below `MemoryHigh`. The observed current therefore fluctuates within
hundreds of KiB of its soft limit rather than maintaining material headroom.

## Bounded candidate fixtures — 2026-10-29 01:01–01:02 CET

After the 01:00 Veritas observation completed, all three isolated Reality
capacity-candidate fixtures passed across two runs from
`/home/charlie/midas-reality-capacity-scan-frontier-20261029`:

- Oversized manifest plus stale path-size case: 1 passed in 1.01 seconds.
- Bounded inventory scan / unknown headroom: 1 passed.
- Skip inventory walk for invalid provenance: 1 passed; the two-case run
  completed in 0.52 seconds.

The cases used temporary fixture files and performed no network or archive
access. Each `systemd-run --user --scope` used `MemoryMax=384M`,
`MemorySwapMax=0`, `CPUQuota=25%`, `TasksMax=16`, and a 20-second subprocess
timeout. The transient scopes were cleaned after exit, so systemd did not
retain their `MemoryPeak` for post-run inspection.

At 01:02:32, host available memory was 9.8 GiB; host/user avg10 PSI remained
0.00% and avg300 `full` PSI was 0.04%. User-manager `max`, `oom`, and
`oom_kill` counters were unchanged, and no new OOM journal entry appeared.
API and Reality remained active; Reality had about 236 KiB `MemoryHigh`
headroom and its status was still stale. The candidate branch is clean at
`d8629e4b63c8b8ef68e27294fb3599423a694b76`; these fixtures do not validate
the full test file, the Reality service, the archive, or production capacity
behavior. Keep broad tests deferred until after the 01:16 capacity run and
fresh Reality recovery evidence.

## Focused capacity regression — 2026-10-29 01:05 CET

At 01:05, the isolated candidate worktree ran the complete focused
`test_reality_operations.py -k archive_capacity` group in a new transient
scope with the same 384 MiB hard cap, no swap, 25% CPU quota, 16-task limit,
and 20-second timeout. Result: **5 passed, 35 deselected in 0.61 seconds**.
This covers the three new candidate fixtures plus two existing capacity
checks; it does not cover the remaining Reality tests or the Frontier suite.

At 01:05:55, available host memory was 9.8 GiB. Host/user avg10 PSI was
0.00%, avg300 `full` PSI was 0.00%, and user-manager `max`, `oom`, and
`oom_kill` counts were unchanged; no newer OOM journal entry appeared. API
and Reality were still active; Reality remained only about 220 KiB below
`MemoryHigh` with stale status. Its isolated candidate branch is clean and
undeployed. Keep the broader runtime gate closed pending the 01:16 capacity
run and fresh Reality recovery evidence.

## Reality recovery and bounded Frontier tests — 2026-10-29 01:08 CET

Reality status began advancing again at 01:06:42.862 CET, when the new
recording state started. By 01:07:24 it reported
`RECORDING_UNSEQUENCED`, `active_receiving`, 16/16 fresh books, zero failures,
and no backpressure. It reported 5,746,669 lifetime frames and
12,133,811,197 storage bytes, 511,747 bytes above the 00:46 capacity report.
At 01:08:52 it still reported `active_receiving`, 16/16 fresh books and zero
failures, with 5,746,762 frames and 12,134,229,021 storage bytes. The storage
grew another 417,824 bytes between those snapshots. This demonstrates resumed
observation and persistent growth after cold replay; sequencing remains
unverified (`sequence_verified=false`). No collector action was taken.

With fresh capture and low pressure established, bounded Frontier tests
resumed in separate transient user scopes:

- `tests/arena/test_admission.py`: 15 passed in 5.90 seconds.
- `tests/arena/test_scheduling.py`: 12 passed in 17.89 seconds; one existing
  Starlette/httpx deprecation warning.

Each scope used `MemoryMax=512M`, `MemorySwapMax=0`, `CPUQuota=25%`,
`TasksMax=16`, and a 30-second subprocess timeout. After both, at 01:08:52,
host available memory was 9.9 GiB; host and user PSI avg10/avg300 were near
zero. User-manager `high` was 16,416,798, only one more than at 01:07:51;
`max=728,363`, `oom=19`, and `oom_kill=15` were unchanged. No new OOM journal
entry appeared. API and Reality remained active with about 1.30 MiB and
0.82 MiB `MemoryHigh` headroom, respectively; their leaf PSI remained zero.

Continue with bounded tests only. Full test suites, replay, live probes, and
research batches remain gated pending the 01:16 capacity run under the new
160 MiB soft bound. Keep the gap-detail timer disabled and preserve the now
active Reality collector.

## Admission-test harness correction — 2026-10-29 01:11 CET

The Laboratory resource-denial case was first run with a 512 MiB transient
`MemoryMax`. It failed before reaching the intended admission denial because
the test's pool-capacity precondition correctly requires 722,894,848 bytes.
That failure identifies an undersized test harness limit, not a product
regression. No test code or test data was changed. The same test passed on a
bounded rerun with a 1 GiB cap, zero swap, 25% CPU quota, 16 tasks, and a
30-second timeout: **1 passed in 1.41 seconds**.

At 01:11:44, after the rerun, host available memory was 9.8 GiB, host and user
memory PSI avg10/avg60/avg300 were zero, and user-manager `high`, `max`, `oom`,
and `oom_kill` counts had not changed from the pre-run sample. Kernel and
systemd-oomd journals had no new kill. API and Reality were active. API and
Reality remain near their service `MemoryHigh` boundaries; their current
charges were 1,609,359,360 / 1,610,612,736 bytes and 1,192,218,624 /
1,207,959,552 bytes, respectively. These near-boundary values justify keeping
all broad runtime work gated.

The revised capacity-monitor `MemoryHigh=160M` is still not validated. Its
scheduled 01:16 run is the next evidence gate. No claims are made that the
incident is resolved based on this brief quiet period.

## Revised capacity-bound validation — 2026-10-29 01:17 CET

The scheduled 01:16:04 capacity timer completed successfully at 01:16:11.
Systemd retained `MemoryPeak=134,225,920` bytes (about 128 MiB), below the
revised `MemoryHigh=160 MiB`; `MemoryMax=192 MiB` and `MemorySwapMax=0` were
effective. The service used 6.56 CPU seconds and returned status 0. Its peak
was 8 KiB above the former 128 MiB threshold and about 32 MiB below the revised
threshold, consistent with avoiding repeated soft-limit reclaim in this run.
This validates one scheduled run under the new bound, not long-term behavior.

The generated capacity report measured at 01:16:09 CET reports fresh collector
status age 3.36 seconds, state `RECORDING_UNSEQUENCED`, and raw recording root
size 12,137,375,646 bytes. Archive state remains `INVALID_MANIFEST`; the
inventory and provenance alerts remain in the report. No archive or manifest
was modified.

At 01:16:56, host `MemAvailable` was 9.8 GiB, swap use 3.1/4 GiB, and host
memory PSI avg10/avg60/avg300 was 0.00%. The user-manager event counts were
`max=728,363`, `oom=19`, and `oom_kill=15` unchanged; its `high` count rose by
three since 01:14:26. Neither the kernel nor systemd-oomd journal has a new
kill since 23:43:24 CET on 2026-10-28. Reality/API restart counts remain 14/9;
both services are active but close to their `MemoryHigh` limits. Echo
production/staging, Continental, Caddy, RustDesk, and SSH were active at the
same check. The five-minute gap-detail timer remains disabled.

The historical systemd-oomd mechanism is confirmed, and the recurring capacity
service's old 128 MiB local cap was exceeded. The original workload mix that
drove the user hierarchy above oomd's pressure threshold is still unknown.
Current evidence supports resuming only bounded offline Frontier tests with
explicit memory, swap, CPU, task, and wall-time limits. Keep broad suites,
replay, live probes, and research batches gated; do not treat this single run
or quiet observation window as incident closure.

## Bounded Frontier resumption — 2026-10-29 01:30 CET

After the scheduled capacity run passed, Frontier fixture work resumed
sequentially in transient user scopes. Typical Python scopes used a 768 MiB
hard cap, zero swap, 25% CPU quota, 64-task cap, and explicit wall timeout.
The frontend scopes also used a 768 MiB cap, zero swap, 25% CPU quota,
64-task cap, and `GOMAXPROCS=2`. These bounded workloads did not produce a
host/user PSI spike or a max/OOM event.

At 01:30:17, `MemAvailable` was 10 GiB, host PSI avg10/avg60/avg300 was 0%,
and the user-manager counters were `high=16,416,835`, `max=728,363`,
`oom=19`, `oom_kill=15`. The high count had risen 14 since 01:16:56, but max,
OOM, and OOM-kill counts were unchanged. The kernel and oomd journals still
had no new kill after 23:43:24 CET. Reality and API remained active with
unchanged restart counts 14/9; Reality usage was about 627 MiB after reclaim,
while API stayed near its service `MemoryHigh`. No critical service was
restarted or reconfigured during the tests.

The verified capacity run, continued fresh Reality status, zero current PSI,
and stable OOM counters support continued **bounded offline development and
fixture tests only**. The root workload mix that triggered the historic
user-slice pressure remains undetermined, swap remains 3.1/4 GiB used, the
API remains near its soft bound, and only one capacity run has validated the
160 MiB threshold. Do not treat the incident as solved or resume broad suites,
live probes, replay campaigns, endurance, or production changes on this basis.

At 01:34:53, after additional offline UI and browser verification, host
`MemAvailable` was 9.6 GiB, PSI remained zero, and user-manager
`max=728,363`, `oom=19`, and `oom_kill=15` were unchanged. Reality and API
were active with restart counts 14/9; the kernel/oomd journals had no new
kill. The one-core isolated Playwright smoke passed 1/1, and two seeded
replay/Arena browser tests passed 2/2 against loopback services and temporary
fixture stores. No live source calls were made. The earlier Chromium
SIGTRAP did not repeat with the larger bounded browser scope; it is not
attributed to memory pressure. This adds bounded verification but does not
identify the historical pressure initiator or constitute endurance evidence.

At 01:36:35, after the finite collection/API, Coinbase, and analytics fixture
slices (102 tests total), host available memory was 9.7 GiB, PSI remained
zero, and user-manager `max`, `oom`, and `oom_kill` were unchanged. Reality
and API were active with restart counts 14/9. The next scheduled source
analysis is at 01:40 and the next capacity report is due at 01:46; observe
those existing jobs without starting competing work.

The 01:40 source-analysis run finished at 01:40:13 with exit status 0 after
processing 58 new segments; pending count was zero and status was `current`.
Its measured peak was 226.3 MiB under `MemoryMax=256 MiB`, with zero swap and
8.382 CPU seconds. At 01:40:19, host `MemAvailable` was 9.7 GiB, host PSI was
zero, and the user-manager's max/OOM/OOM-kill counters were unchanged.

## Scheduled service and replay regression checkpoint — 2026-10-29 01:48 CET

The 01:45:04 research-director job exited successfully at 01:45:05 after 1.325
CPU seconds. It reported `WAITING_FOR_FINALIZATION`; the latest scan had not
reached finalized v4 analysis and no qualified gross candidate existed. The
01:46:11 capacity job exited successfully at 01:46:17 after 6.168 CPU seconds.
The capacity report still carries
`ARCHIVE_SEGMENT_INVENTORY_INVALID` and
`ARCHIVE_MANIFEST_PROVENANCE_INVALID`, and reports
`RECORDING_UNSEQUENCED`. Raw recording-root usage increased by 11,641,577
bytes between the 01:16 and 01:46 reports. No manifest or archive was changed.

At 01:48:23, host available memory was 10 GiB, PSI avg10/avg60/avg300 was zero,
and swap use was 3.1/4 GiB. The API cgroup used 1,609,134,080 bytes against a
1,610,612,736-byte `MemoryHigh` (1.41 MiB headroom); its `memory.events` showed
11,655 `high` events and zero `max`, `oom`, or `oom_kill`. Reality used
577,245,184 bytes against a 1,207,959,552-byte high bound and also had zero
leaf max/OOM events. The user-manager high count was 16,416,854; its max/OOM/
OOM-kill counts were unchanged at 728,363/19/15. No kernel or systemd-oomd kill
was logged after 23:43:24 CET.

The corrected four-file relationship/history/replay/source-permission test
slice passed 127/127 in 13.19 seconds in a transient service with a 768 MiB
memory cap, zero swap, 25% CPU, 64-task limit, and 180-second runtime bound.
No live source calls occurred. The service emitted an implausible 256 KiB
memory peak; that value is not accepted as a measured process peak. After this
run, PSI remained zero, the user-manager `max`, `oom`, and `oom_kill` counts
were unchanged, and Reality/API remained active with restart counts 14/9.
Because the API remains within about 1.4 MiB of `MemoryHigh`, broader test
execution is deferred. This is a quiet observation window and bounded test
evidence, not proof that the historic pressure initiator is fixed.

## Short host and cgroup sample — 2026-10-29 01:50–01:52 CET

The existing read-only `host_capacity_sample.py` ran for 30 seconds, taking
seven samples from 01:50:35 to 01:51:05 CET. It ran in a transient systemd
service bounded to 256 MiB, zero swap, 25% CPU, 32 tasks, and 45 seconds. The
temporary JSONL was 3.23 MB at
`/tmp/frontier-host-pressure-20261029-0150.jsonl`; it was not added to the
repository. The service's printed 256 KiB peak is implausible and is not used
as a process-memory measurement.

Across the sample, host `MemAvailable` was 10,262–10,284 MiB, `SwapFree` was
stable at 938.2 MiB, and `pswpin`/`pswpout` did not change. Host, API, and
Reality memory PSI averages were zero. API cgroup `memory.current` varied from
1,534.7 to 1,535.2 MiB under a 1,536 MiB `MemoryHigh`; `memory.stat` showed
about 1,413.9 MiB file cache and 117.9 MiB anonymous memory. Its `high` event
count rose from 11,657 to 11,658, while its `memory.pressure` total barely
changed and `max`, `oom`, and `oom_kill` stayed zero. Reality was about 553 MiB
with unchanged high/OOM events. One active GNOME Terminal scope held about
1,214 MiB (778 MiB file, 412 MiB anonymous); another held about 316 MiB.

At 01:51:59, API usage was 1,610,100,736 bytes against a 1,610,612,736-byte
`MemoryHigh`, leaving 512,000 bytes. Its `high` count was 11,659. The
user-manager `high` count was 16,416,858, four above the 01:48:23 checkpoint;
`max`, `oom`, and `oom_kill` remained 728,363/19/15. Reality/API were still
active with restart counts 14/9, host PSI remained zero, 10 GiB was available,
and no kernel or systemd-oomd kill was logged since 23:43:24. The sample
identifies current cgroup contributors but cannot attribute the historical
OOM window. API `MemoryHigh` margin is now less than half a MiB, so further
tests and runtime work are deferred pending material recovery.

At 01:53:55, the MIDAS API, Reality collector/API, MIDAS web, Continental
tailnet/auth, Echo production/staging, Caddy, RustDesk, and `ssh.socket` were
active. The capacity, source-analysis, and research-director oneshots were
inactive after their successful completions; the gap-detail timer remained
disabled/inactive and its last OOM-killed oneshot remained failed. At 01:54:08,
API usage had eased to 1,609,490,432 bytes, 1.07 MiB below `MemoryHigh`;
Reality/API restart counts remained 14/9. Host PSI remained zero. User-manager
`high=16,416,860` had increased by two since 01:51:59; `max=728,363`, `oom=19`,
and `oom_kill=15` were unchanged. No kernel or systemd-oomd kill was logged
after 23:43:24. The API remains very near its soft bound, so no further tests
or runtime work are scheduled in this checkpoint.

## OOM victim evidence and bounded follow-up — 2026-10-29 02:02 CET

A narrow journal extraction around the two final systemd-oomd decisions on
2026-10-28 establishes the immediate kill mechanism and the memory present in
the candidate cgroups:

| Time CET | Selected cgroup | Candidate memory / local pressure | Parent trigger |
| --- | --- | --- | --- |
| 23:43:09 | `midas-reality.service` | 550.7 MiB; local PSI Avg10/60/300 all 0.00% | `user@1000.service` PSI 61.64%, above 50% for over 20 seconds with reclaim |
| 23:43:24 | `midas-veritas-gap-detail-v2.service` | 204.8 MiB; local PSI Avg10 76.50%, Avg60 50.59%, Avg300 15.12% | `user@1000.service` PSI 54.45%, above 50% for over 20 seconds with reclaim |

At the first decision, other listed candidates included the MIDAS API at
about 1.4 GiB, Chromium at 337.9 MiB, Reality API at 156.6 MiB, a GNOME
ChatGPT scope at 131.1 MiB, and GNOME terminal scopes. At the second, the API
remained about 1.4 GiB, one terminal VTE scope was 457.0 MiB, Chromium was
338.3 MiB, and another terminal scope was 318.4 MiB. These are oomd candidate
snapshots, not a complete process inventory or proof that any one service
initiated system-wide reclaim. They do show that the gap-detail process was
above its effective 192 MiB `MemoryHigh` and experiencing substantial local
reclaim pressure when selected; that makes it a demonstrated contributor at
that instant, not a demonstrated sole cause of the user-slice pressure.

The five-minute unit is explicitly the bounded finalized-Reality gap-detail
replay. It runs `veritas_gap_detail_v2_batch.py` over saved segment and Arena
paths, with per-run bounds of 128 segments, 32 MiB of source, and a 4 GiB
artifact limit; it has a ten-minute timeout and no declared dependency on the
Reality collector. It is auxiliary research replay, not live capture or
integrity monitoring. The timer remains disabled/inactive, and the service's
last result remains `oom-kill`. It can be restored with:

```sh
systemctl --user reset-failed midas-veritas-gap-detail-v2.service
systemctl --user enable --now midas-veritas-gap-detail-v2.timer
```

Recent scheduled work was staggered in the observed window: source analysis
processed 58 segments in about nine seconds (226.3 MiB peak, 256 MiB max,
zero swap); research director completed in about one second; the capacity
report completed in about six seconds; and Veritas observatory completed in
about twelve seconds. Arena's minute timer returned an empty schedule in
about one second. These observations show no overlap in that sample, but do
not establish that historical jobs never overlapped. No timer schedule other
than the auxiliary gap-detail timer was changed.

The revised capacity monitor has effective `MemoryHigh=160M`,
`MemoryMax=192M`, and `MemorySwapMax=0` in the persistent drop-in
`~/.config/systemd/user/midas-reality-capacity.service.d/90-frontier-memory-bound.conf`.
Its 01:16 run recorded a 134,225,920-byte peak under the new bound and
completed successfully. This is one validated run; later 01:46 completion
did not retain a peak, so long-term headroom is not established. The exact
rollback is to remove only that drop-in and reload the user manager:

```sh
rm ~/.config/systemd/user/midas-reality-capacity.service.d/90-frontier-memory-bound.conf
systemctl --user daemon-reload
```

At 02:02 CET on 2026-10-29, host memory was 15 GiB total, 5.8 GiB used,
9.8 GiB available; swap use was 3.1/4 GiB; host PSI Avg10/60/300 was zero.
The user-manager cgroup was charged 11,100,119,040 bytes; its event counters
were `high=16,416,870`, `max=728,363`, `oom=19`, `oom_kill=15`, unchanged for
max/OOM/OOM-kill since the prior checkpoints. Its current memory PSI averages
were zero. The short 01:50 sample had no change in swap-in or swap-out
counters, but elevated swap occupancy remains a risk indicator and does not
rule out earlier reclaim or swap activity.

At that same check, the API was active at 1,609,719,808 bytes against a
1,610,612,736-byte `MemoryHigh` (892,928 bytes, about 0.85 MiB, of headroom),
with `MemoryMax=1,879,048,192`; Reality was active at 587,796,480 bytes
against a 1,207,959,552-byte `MemoryHigh`. API and Reality restart counts
remained 9 and 14. Reality API, MIDAS web, Continental tailnet/auth, Echo
production/staging, Caddy, RustDesk, and `ssh.socket` were active. No kernel
OOM or systemd-oomd kill was found after 23:43:24 CET. The gap-detail timer
was disabled; its failed oneshot remains visible for diagnosis.

### Causal assessment and operating gate

- **Confirmed:** systemd-oomd killed processes after sustained PSI/reclaim in
  the shared user-manager hierarchy. The kernel memcg OOMs on the old capacity
  monitor were separate local-limit failures. The capacity monitor exceeded
  its old 128 MiB bound; one run passed under the revised 160/192 MiB bounds.
- **Demonstrated contributor:** the gap-detail process was at 204.8 MiB with
  high local PSI when it was killed. Disabling its five-minute auxiliary timer
  removes this repeated replay workload while keeping live collection
  untouched.
- **Not established:** which workload or combination first drove the whole
  user manager into sustained pressure. API, Reality, GUI/browser and terminal
  cgroups were all sizable in the candidate snapshots. Current cgroup samples
  taken after the incident cannot reconstruct that trigger.
- **Not established:** absence of historical timer overlap, long-term success
  of the capacity-monitor bound, or closure of the archive provenance issues.
  `ARCHIVE_SEGMENT_INVENTORY_INVALID`,
  `ARCHIVE_MANIFEST_PROVENANCE_INVALID`, and `RECORDING_UNSEQUENCED` remain
  separate integrity findings; no archive or manifest was modified.

The measured quiet window supports static/offline Frontier work and only
sequential, explicitly bounded fixture checks. At 02:02 the API had less than
1 MiB of `MemoryHigh` headroom, so further test processes, broad suites, live
probes, profiling, and batch replay remain deferred. This is containment and
partial validation, not incident resolution. Continue to monitor PSI, service
restart counts, cgroup `memory.events`, and scheduled jobs before increasing
runtime activity.

## Cgroup summary instrumentation — 2026-10-29 02:07 CET

Frontier's read-only host sampler now captures `memory.swap.max` alongside
its existing cgroup observations. `host_capacity_summary.py` now retains the
per-cgroup `memory.high`, `memory.max`, and swap limit; summarizes PSI
`avg10`/`avg60`/`avg300`; and reports first/last/delta values for
`memory.events` and PSI `total` counters. Counter decreases are emitted as a
reset with a null delta, rather than as negative activity. This closes an
observability gap found during the incident: the sampler held these raw
fields, but its summary discarded the per-cgroup PSI and OOM-event changes.
The change is only in the Frontier development worktree; no service was
reconfigured and no historical sample was rewritten.

`tests/test_host_capacity_summary.py` passed **2/2** in 1.739 seconds in a
transient scope with `MemoryHigh=448M`, `MemoryMax=512M`, no swap, 25% CPU,
16 tasks, and a 30-second timeout. The fixtures cover normal event/PSI deltas
and counter resets. Ruff lint and formatting checks passed. The first test
invocation used Python `-S`, which hid the installed pytest module and exited
before test collection; the installed `pytest` entrypoint corrected the
harness. The first reset-case fixture also omitted the sampler's required host
memory fields; correcting the fixture yielded the final 2/2 pass. Systemd
reported a 256 KiB memory peak for the test scope, which is implausible and is
not used as process-memory evidence.

At 02:06:32 CET after the bounded checks, host available memory was
10,799,087,616 bytes and swap use was 3,311,185,920 / 4,294,963,200 bytes.
Host, user-manager, and API PSI averages were zero. The user-manager event
counters were `high=16,416,873`, `max=728,363`, `oom=19`, `oom_kill=15`; the
API had `high=11,674` and zero max/OOM/OOM-kill events. The user-manager and
API high counters each increased by one relative to the preceding sample;
the timing does not establish causation. The API was active at 1,609,396,224
bytes versus `MemoryHigh=1,610,612,736` (1,216,512 bytes of headroom), with
restart count 9; Reality was active with restart count 14. No new OOM was
observed; this remains a bounded check, not an endurance validation.

The sampler and summary implementation with its two focused fixtures is
commit `b7eab3c114adddd79ef156ec2585c851e0b71dd6` on
`codex/frontier-20261026`.

## Scheduled Veritas analysis observation — 2026-10-29 02:11 CET

The existing source-analysis timer ran from 02:11:04 to 02:11:13 and exited
successfully. Its report recorded 61 newly processed segments, 38,189 total
processed segments, zero pending segments or source bytes, status `current`,
and readiness `awaiting_finalized_campaign_window_end`. The summary digest was
`29502af5ffbbba860985513fb572978deceb22e7ece82e69052a8e9d07bccc6d`. The
service peaked at 229,371,904 bytes (218.7 MiB) under `MemoryMax=256 MiB`,
used 8.494 CPU seconds and 0 bytes of swap, then exited with status 0. This is
the scheduled bounded analysis of local finalized Reality segments; no
collector restart or service configuration change occurred.

At 02:11:39, host available memory was 10,784,276,480 bytes, swap use was
3,311,181,824 bytes, and host PSI averages were zero. User-manager counters
were `high=16,416,878`, `max=728,363`, `oom=19`, `oom_kill=15`. The API was
active at 1,609,617,408 bytes against a 1,610,612,736-byte `MemoryHigh`
(995,328 bytes of headroom); Reality was active at 597,573,632 bytes.
Restart counts remained 9/14. The post-run journal scan found no kernel OOM
or systemd-oomd kill after 23:43:24 on Oct 28. This successful scheduled run
supports continuing bounded offline work but does not establish sustained
headroom or identify the earlier pressure initiator.

## Full Frontier Python suite under the resource gate — 2026-10-29 02:19 CET

The current `tests/frontier` suite passed **648/648** in 120.52 seconds. It
ran once in a transient user scope with `MemoryHigh=640M`,
`MemoryMax=768M`, `MemorySwapMax=0`, 25% CPU, 64 tasks, and a 180-second wall
limit. The unit completed successfully in 2 minutes 6.432 seconds, with
25.157 CPU seconds, a 254.8 MiB cgroup peak, and zero swap. The suite's
autouse guard denied reads from both captured live-source paths. The only
warning was the existing Starlette/httpx TestClient deprecation.

At 02:18:59, host `MemAvailable` was 10,622,218,240 bytes and swap use was
3,311,120,384 bytes. Memory PSI remained zero on host and API; user-manager
`max=728,363`, `oom=19`, `oom_kill=15` and API leaf max/OOM counters remained
unchanged. API and Reality stayed active with restart counts 9/14; API had
962,560 bytes below `MemoryHigh`. No kernel OOM or systemd-oomd kill was found
after 23:43:24 on Oct 28. I/O PSI after the run was `some avg10=2.29%`,
`avg60=4.74%`, `avg300=2.45%`; `full` was `2.14%`, `4.42%`, and `2.26%`.
The cause of that short I/O-pressure increase is not assigned. Defer further
disk-heavy suites and persistence tests until I/O PSI eases. This is bounded
validation, not endurance or incident closure.

## Bounded web regression and browser observation — 2026-10-29 02:26 CET

The first complete Vitest invocation used a 25% CPU quota and the configured
five-second per-test timeout. It ended with 34 passed and 13 timed out; all
reported failures were timeout errors, with no assertion, import, or process
failure. A single-worker retry used a 50% CPU quota, a 15-second invocation
timeout, `MemoryHigh=768M`, `MemoryMax=896M`, zero swap, 64 tasks, and a
180-second wall limit. It passed **47/47 across nine files** in 56.916 seconds
with a 286.7 MiB cgroup peak, 27.508 CPU seconds, and zero swap. The timeout
override was command-line only; test code and repository configuration were
not changed.

The default Playwright suite then ran one worker against loopback-only Vite and
API servers, with isolated database, Frontier, and Arena roots under
`/tmp/midas-browser-frontier-20261029-0226` and artifacts under
`/tmp/midas-frontier-e2e-artifacts-20261029-0226`. It reported **17 passed and
3 skipped** out of 20. The skips were the two explicitly seeded Frontier tests
and the captured-evidence test, none of which were enabled in this run. No
public exchange probes were enabled. The transient service used
`MemoryHigh=1G`, `MemoryMax=1280M`, zero swap, 50% CPU, 192 tasks, and a
180-second wall limit. It completed in 1:32.623 with a 744.5 MiB peak, 44.398
CPU seconds, and zero swap. Temporary fixture databases and synthetic
recordings remain in the dedicated `/tmp` roots; no project data was touched.

At 02:26 CET, host `MemAvailable` was 10,371,465,216 bytes and host memory PSI
averages were zero. Swap use was 3,313,573,888 bytes. User-manager PSI was
`some=0.20%/0.55%/0.98%` and `full=0.04%/0.16%/0.69%` for avg10/avg60/avg300.
Its counters remained `high=16,416,891`, `max=728,363`, `oom=19`, and
`oom_kill=15`; no new oomd or kernel OOM event appeared after the 23:43:24
Oct 28 kill. API and Reality remained active with restart counts 9 and 14.
API was at 1,525,174,272 / 1,610,612,736 bytes `MemoryHigh` (about 81.4 MiB
headroom); Reality was at 222,257,152 bytes. The gap-detail timer remains
disabled. The scheduled capacity monitor's effective limits remain 160 MiB
`MemoryHigh`, 192 MiB `MemoryMax`, and zero swap.

These bounded runs did not raise memory PSI, use test-unit swap, change OOM
counters, or restart the protected services. They support continued bounded
offline work. They do not explain the historical system-wide pressure source,
clear the host's high swap occupancy, validate endurance, or resolve the
invalid Reality archive manifest/inventory. Keep the gap-detail timer stopped
until its workload and resource budget are reviewed; keep public probes,
profiling, and batch research disabled.

At 02:28 CET, the sampled user and system managers also showed the MIDAS API
and Reality collector/API, Continental tailnet/auth and website services,
Echo production and staging, Caddy, RustDesk, and `ssh.socket` active. This
confirms those services were available after the bounded checks; it is a
point-in-time service-state check, not an uptime guarantee.

## Scheduled-job and seeded-browser follow-up — 2026-10-29 02:33 CET

The pre-existing Veritas observatory completed at 02:32:16, recording a
bounded 40-market Polymarket sample after 7 public GET attempts. Its service
used 35.6 MiB peak memory, 1.654 CPU seconds, and zero swap. It recorded no
positive gross candidates. The run was not a Frontier cross-venue result.

The two isolated synthetic Frontier seeded browser journeys then passed
**2/2** in 25.6 seconds. The unit used a fresh `/tmp` store, peaked at 498.7
MiB, used 14.751 CPU seconds and zero swap, and had a 120-second limit. No
captured-evidence store or exchange probe was enabled. At 02:33, host
`MemAvailable` was 10,383,945,728 bytes, host memory PSI was zero, and swap
use was 3,313,475,584 bytes. User-manager `oom=19` and `oom_kill=15` remained
unchanged; API/Reality remained active at restart counts 9/14, with about
78.3 MiB below the API `MemoryHigh`. This is another bounded quiet sample, not
endurance or resolution of the unknown original trigger.

## Ancestor-cgroup sampler follow-up — 2026-10-29 02:45 CET

Review of `scripts/host_capacity_sample.py` found that it sampled only the
direct cgroup path attached to each process. That omitted aggregate ancestors
such as `user@1000.service`, where systemd-oomd's pressure and memory event
counters are relevant. The sampler now records each observed cgroup from leaf
through `/`, deduplicating shared ancestors and rejecting non-absolute,
double-root, NUL-containing, and parent-traversal paths before filesystem
mapping. This changes only the isolated Frontier diagnostic script; no host
service configuration or protected data was changed.
The sampler change is committed as `2493c2d`; its rollback is
`git revert 2493c2d`.

The focused host-capacity test file passed **6/6** under a transient 256 MiB,
zero-swap, 25% CPU unit. A separate one-shot snapshot completed in 0.63 seconds
under a 256 MiB, zero-swap, 20% CPU unit: 385 processes and 149 distinct cgroup
paths were sampled, including `/user.slice/user-1000.slice/user@1000.service`
and `/`. The observed user-manager counters remained `max=729589`, `oom=19`,
and `oom_kill=15`.

At 02:45:22 CET, host `MemAvailable` was 11,441,176 kB, `SwapFree` was 204 kB,
and host memory PSI `avg10` was zero. The user-manager event counters matched
the preceding observation. MIDAS API and Reality were active; the gap-detail
timer was inactive; the capacity and source-analysis timers were active. The
next capacity run was due at 02:46:21 and had not yet been observed in this
check. `whoopsie` remained active with `_usr_bin_node.1000.upload` present and
no `.uploaded` marker; the 58,222,586-byte crash report was left untouched.

This improves visibility into ancestor limits and pressure counters. It does
not identify the historical pressure initiator, explain the full swap, or
establish a sustained quiet period. The capacity report's `INVALID_MANIFEST`
and archive provenance findings remain a separate integrity issue and were
not modified.

## Capacity run and post-run observation — 2026-10-29 02:48 CET

The scheduled `midas-reality-capacity.service` run started at 02:46:28 and
finished at 02:46:38 with `Result=success`, exit status 0, and 6.810 CPU
seconds. Its effective limits were `MemoryHigh=160M`, `MemoryMax=192M`, and
`MemorySwapMax=0`; the 30-minute capacity timer remains active. systemd
reported `MemoryPeak=[not set]`, so the run proves bounded completion at the
revised limit but supplies no peak-memory measurement. The report still
returned `INVALID_MANIFEST`, invalid archive segment inventory, and invalid
manifest provenance; it was read only.

A six-snapshot sampler window ran from 02:47 through 02:48 CET for 24.91
seconds under a 192 MiB, zero-swap, 20% CPU limit. It observed 383–386
processes and 148 cgroups per sample, including the user-manager ancestor.
`MemAvailable` ranged from 11,458,116 to 11,474,644 kB; only 208 kB of swap
remained free. Host and user-manager memory PSI `some` and `full` averages
were zero in every sample. The user-manager `memory.events` counters did not
change (`high=16417194`, `max=729589`, `oom=19`, `oom_kill=15`). The kernel
journal had no OOM record after the Oct 28 23:43:24 CET event, and the
systemd-oomd journal ended at that same kill. This is a roughly three-hour
quiet interval with a short post-run sample, not proof of durable resolution.

At 02:48 CET, the MIDAS API and Reality, Continental tailnet and auth, Echo
production and staging, Continental contact/status sites, Caddy, RustDesk,
and `ssh.socket` were active. The gap-detail timer was inactive; the capacity
timer was active. The failed-unit inventory also contained 37
`midas-arena-job-*` one-shot records and one `continental-infrastructure-audit`
unit. These were not reset or restarted, and their relationship to the Oct 28
OOM events is not established. The Node crash report and Whoopsie `.upload`
state remained preserved without an `.uploaded` marker at the last check.

The demonstrated historical trigger remains hierarchical reclaim pressure in
`user@1000.service`; no single initiating workload has been proven. The
unusually high swap occupancy, failed one-shot records, separate archive
integrity findings, and current process mix remain open review items. Continue
Frontier only with isolated, bounded, zero-swap work while preserving the
existing timer and capacity-monitor rollback commands above.

## Node crash-report submission side effect — 2026-10-29 02:50 CET

The earlier bounded TypeScript check aborted at the Node/V8 heap limit (about
300.6 MiB cgroup peak); this was not a host or service-cgroup OOM. It caused
Ubuntu Apport to create `/var/crash/_usr_bin_node.1000.crash` (58,222,586
bytes) and Whoopsie to attempt a submission. The Whoopsie journal records an
upload attempt beginning at 02:36:52 and, at 02:45:34, an HTTP 504 Gateway
Timeout. The `.uploaded` marker is absent; the `.upload` marker and report
remain. At 02:49:43, `whoopsie.service` was inactive. A 504 does not establish
whether any part of the report reached the remote endpoint, so receipt is
unknown. The report contents were not read, and neither the report nor the
system service was altered. Do not repeat Node tests that may crash until a
safe diagnostic path is established.

## Sampler input resilience and final point check — 2026-10-29 02:51 CET

While resuming bounded Frontier work, a further low-cost failure mode was
closed: undecodable `/proc` text now yields an explicit unavailable (`null`)
field instead of aborting the whole sampler. The fixture writes invalid UTF-8
bytes and verifies this fail-closed behavior. Commit `e4d12ac` contains only
this script and focused test; rollback with `git revert e4d12ac`. The focused
test file passed **7/7 in 0.60 seconds** under a 256 MiB, zero-swap, 25% CPU
limit; Ruff passed under a 192 MiB, zero-swap, 20% CPU limit.

At 02:51:34 CET, `MemAvailable` was 11,455,120 kB and only 216 kB of swap was
free. Host memory PSI remained zero; user-manager counters remained
`max=729589`, `oom=19`, `oom_kill=15`. API and Reality were active with restart
counts still 9 and 14. The capacity timer was active and gap-detail timer
inactive. Caddy, RustDesk, and `ssh.socket` were active. Whoopsie was inactive;
the 58,222,586-byte crash report and `.upload` marker remained, with no
`.uploaded` marker. No host configuration or data was changed by this follow-up.

Safe continuation remains limited to small isolated, zero-swap work. Do not
run Node checks that could create another crash report, broad suites, or
competing research batches until the resource and upload conditions are
reviewed. This point sample does not resolve the high swap occupancy or the
historical workload attribution.

## OOM policy confirmation and 03:14 incident checkpoint

The system journal contains **12 systemd-oomd kills** from 20:18:23 through
23:43:24 CET on Oct 28: four `midas-api` kills, three Reality collector kills,
four gap-detail replay kills, and one GNOME Terminal scope. Each kill entry
states that `user@1000.service` memory pressure exceeded its 50% threshold for
more than 20 seconds with reclaim activity. The effective policy comes from
`/usr/lib/systemd/system/user@.service.d/10-oomd-user-service-defaults.conf`:
`ManagedOOMMemoryPressure=kill`, `ManagedOOMMemoryPressureLimit=50%`. The user
slice and manager have no `MemoryHigh`, `MemoryMax`, or `MemorySwapMax` bound.
This confirms the aggregate trigger and leaf victims; it still does not prove
which workload initiated pressure.

Candidate snapshots support a mixed-workload explanation. At 23:23, oomd
listed the API at 1.4 GiB, Reality at 1.0 GiB, one terminal scope at 1.0 GiB,
and gap-detail at 204.7 MiB. At 23:43, API was 1.4 GiB while Reality was
550.7 MiB. These are cgroup charges, including file cache, and show concurrent
large consumers rather than a unique source. API, Reality, the terminal,
Chromium, and scheduled replay all resided inside the same user manager.

The separate kernel memcg OOM chain for `midas-reality-capacity.service` is
confirmed seven times between 17:15 and 20:15 CET on Oct 28. The killed
Python processes had approximately 129–131 MiB anonymous RSS plus 11 MiB file
RSS under the original 128 MiB hard limit. The effective reversible override
is currently `MemoryHigh=160M`, `MemoryMax=192M`, `MemorySwapMax=0`; scheduled
runs at 00:46 and 01:16 completed with retained peaks of 137.4 MiB and 128.0
MiB, and the 02:46 run also completed successfully (6.810 CPU seconds; no
peak was retained). This supports the revised monitor cap, not a claim about
the historical host-wide pressure source.

At 03:14:18 CET, host `MemAvailable` was 11,159,352 kB, memory PSI was zero,
and only 1,272 kB of 4,194,300 kB swap was free. `user@1000.service` charged
7,519,457,280 bytes of memory and 2,864,898,048 bytes of swap; its recorded
peak was 13,992,292,352 bytes. Its `memory.events` were `high=16,417,194`,
`max=730,045`, `oom=19`, and `oom_kill=15`. Those counters did not change
during this read-only check. The last systemd-oomd kill remains 23:43:24 Oct
28; the last capacity memcg OOM remains 20:15:44 Oct 28. API and Reality are
active (`NRestarts=9` and `14`); `ssh.socket`, RustDesk, Caddy, Continental
tailnet/auth, and Echo production/staging were active. No collector restart,
configuration change, OOM policy change, or historical-data operation was
made in this follow-up.

The gap-detail timer remains disabled and its failed service remains stopped;
rollback is documented above. The capacity override and rollback remain as
documented above. Do not raise the user-wide oomd threshold or exempt Reality
without a separate design review: doing so could trade service kills for a
kernel OOM, and changing the critical collector's containment is outside this
checkpoint. The host remains suitable only for sequential, isolated,
resource-bounded offline Frontier work with zero-swap transient scopes. This
quiet interval and current zero PSI do not clear the full-swap condition or
identify the original initiating workload.

### Scheduled capacity run and service check — 2026-10-29 03:16 CET

The active capacity timer started `midas-reality-capacity.service` at 03:16:36
and it completed successfully at 03:16:44 (exit 0, 6.575 CPU seconds). The
effective limits remained 160 MiB `MemoryHigh`, 192 MiB `MemoryMax`, and zero
swap. systemd retained no memory peak. At 03:16:52, host memory PSI remained
zero, `MemAvailable` was 11,428,380 kB, and only 1,272 kB of swap was free.
User-manager `oom=19` and `oom_kill=15` were unchanged; its `high` counter
increased by 145 during the interval. MIDAS API and Reality were active at
restart counts 9 and 14. No systemd-oomd or kernel OOM entry appeared after
the check began. This validates a bounded scheduled execution and service
continuity for this sample; it does not establish sustained stability, remove
the full-swap condition, or identify the historical initiating workload.

### Post-frontend-test resource check — 2026-10-29 03:23 CET

After the focused, single-worker Frontier Vitest run, host PSI was still zero,
MemAvailable was 11,422,164 kB, and only 1,316 kB of swap was free. The user
manager remained at `oom=19`/`oom_kill=15`; API and Reality remained active at
restarts 9/14. No new systemd-oomd or kernel OOM records appeared after 03:20.
This observation window is only a few minutes and does not establish
endurance; retain the zero-swap test gate and defer broad or Node build work.

### Host and bounded-work checkpoint — 2026-10-29 03:33 CET

The Frontier worktree remained on `codex/frontier-20261026` at commit
`9b35b50`. Its only untracked path was the preserved public-probe evidence
directory `data/frontier-public-probes/`; it was not staged or modified. The
worktree had already been checkpointed before this incident review. This
follow-up changed documentation only and did not alter service configuration,
recordings, archive evidence, or other research data.

At 03:32:25, host memory was 15 GiB total, 4.6 GiB used, and about 10 GiB
available. Swap remained 4,192,968 kB of 4,194,300 kB used (1,332 kB free).
Host and user-manager memory PSI averages were all zero. `vmstat` showed zero
swap-in and swap-out in both one-second interval rows; swap use did not change.
This indicates cold pages remain in swap without measurable active swap churn
in that brief sample. It does not establish that swap is healthy or that future
pressure is impossible.

The user manager charged 7,909,601,280 bytes of memory and 2,864,865,280 bytes
of swap; its effective `MemoryHigh`, `MemoryMax`, and `MemorySwapMax` are all
unbounded. `user.slice` and `user-1000.slice` are also unbounded. The manager's
`memory.stat` sample was about 2.10 GB anonymous, 4.52 GB file cache, and
1.10 GB kernel memory. Its current event counts were `high=16,417,339`,
`max=730,045`, `oom=19`, and `oom_kill=15`; the OOM counters did not change.
The largest current user child was `app-org.gnome.Terminal.slice` at about
3.73 GB memory and 1.65 GB swap. One Codex/terminal scope accounted for
about 1.18 GB memory and no swap. These are current workload observations,
not attribution for the Oct 28 OOMs. At the historical 23:23 candidate sample,
oomd recorded concurrent API, Reality, Terminal, and gap-detail charges; no
single initiating workload is proven.

At 03:32:25, API was active at 809.9 MB against 1,610.6 MB `MemoryHigh` and
1,879.0 MB `MemoryMax`, with zero swap; its peak was 1,611.0 MB. Reality was
active at 229.9 MB against 1,208.0 MB `MemoryHigh` and 1,342.2 MB
`MemoryMax`, with zero swap; its peak was 1,208.5 MB. Restart counters remain
9 and 14, respectively. The current Reality `status.json` mtime was 03:33:15;
it reports `RECORDING_UNSEQUENCED`, `active_receiving`, 16 fresh books,
`sequence_verified=false`, and no active backpressure. The `.open` segment
also advanced at 03:33:31. No collector restart or archive operation was
performed.

The gap-detail timer remains `disabled/inactive`; its replay-only service is
not live collection or integrity monitoring. The capacity timer remains
active, and the 03:16:44 run exited successfully in 8 seconds (6.575 CPU
seconds) at `MemoryHigh=160M`, `MemoryMax=192M`, `MemorySwapMax=0`; systemd
retained no peak. The 03:31 Veritas observation completed in 12 seconds, the
03:32 daily Reality research check returned `ALREADY_ATTEMPTED_THIS_WEEK` in
16 seconds, and recent source-analysis/research-director runs were staggered
and completed in seconds. The Arena dispatcher continued returning an empty
schedule. There are no queued user-manager jobs. No timer change beyond the
documented gap-detail containment is justified by these observations.

The full swap occupancy persists, but no new OOMd or kernel OOM record appears
after Oct 28 23:43:24, through 03:33. The current evidence supports only
sequential, bounded, offline Frontier work in transient scopes with explicit
memory limits, zero swap, CPU limits, and timeouts. Do not run broad suites,
concurrent jobs, or long experiments. A manager-wide memory ceiling or change
to oomd policy could affect Reality, API, interactive sessions, and remote
administration; no such policy change is made here. Further design work must
reserve those critical workloads and retain a rollback path before changing
that boundary.

After the 03:23 Vitest sample, a bounded TypeScript project check passed with
exit 0 under a transient 1 GiB `MemoryHigh`, 1,280 MiB `MemoryMax`, zero-swap,
25% CPU scope. The production Vite build also passed (2,230 modules, 46.58 s)
under a 768/896 MiB, zero-swap, 25% CPU scope. It emitted the existing
544.51 kB Chart chunk warning. The 03:27 host sample remained at zero PSI with
11,426,460 kB available and 1,332 kB swap free; OOM counters remained 19/15.
These checks were serialized and did not produce a new OOM event. Continue
only with similarly bounded work; production readiness and the historical
pressure source remain unresolved.

### Fixture-backed timeline browser check and collector point check — 03:38 CET

The focused Playwright case for the saved timeline timing table passed 1/1 in
12.3 seconds (32.8 seconds including isolated server startup and shutdown).
It used a new `/tmp/midas-browser-*` fixture root and a transient systemd scope
with 1 GiB `MemoryHigh`, 1,280 MiB `MemoryMax`, zero swap, 25% CPU, 192 tasks,
and a 180-second timeout. The first attempt showed that the UI correctly
collapses frame details by default; the test now opens the frame before
checking receipt age, exchange time and meaning, clock uncertainty, and the
freshness limit. It asserted zero source-probe requests and zero Arena POSTs.
No production API, public source, or saved MIDAS/Reality data was used.

At 03:37:53, host PSI remained zero, MemAvailable was about 10 GiB, and swap
was still 4,192,968/4,194,300 kB used. User-manager OOM counters remained
`oom=19`/`oom_kill=15`; its charge was 8,136,388,608 bytes memory and
2,864,861,184 bytes swap. The scope completed without OOM; no oomd or kernel
OOM record appeared. API and Reality remained active at restart counts 9/14,
with zero swap. No queued user-manager job was present after the test.

One status read around 03:37 reported `AWAITING_DATA`, `collection_health=stale`,
and zero fresh books. A subsequent read at 03:38:08 reported
`RECORDING_UNSEQUENCED`, `active_receiving`, 16 fresh books,
`sequence_verified=false`, no failures, and no backpressure; an `.open`
recording segment had mtime 03:38:09. The collector sets `AWAITING_DATA` after
subscribing while it awaits initial snapshots, so this sequence is consistent
with a short resubscription/data gap. Its trigger is unknown. The process PID,
service state, and restart count did not change, and no OOM event coincided
with it. Do not restart or reconfigure Reality; keep source freshness and
sequence verification as separate open quality checks.

### Short sampler around the existing source-analysis timer — 03:41 CET

Ran the existing read-only `scripts/host_capacity_sample.py` for 35 seconds
with five-second intervals under a transient 256 MiB `MemoryHigh`, 384 MiB
`MemoryMax`, zero-swap, 25%-CPU, 64-task scope. It recorded eight snapshots
from 03:40:08 through 03:40:43 in
`/tmp/frontier-host-pressure-20261029-0340.jsonl` (3,979,630 bytes). The
Veritas source-analysis timer was later than the predicted next-elapse value:
it started at 03:40:42 and finished at 03:40:51, after most of the sample
window. Only one sample captured the service (44,097,536 bytes, zero swap), so
this run does not measure its peak memory.

Across all eight snapshots host and user-manager memory PSI remained zero,
`MemAvailable` stayed above 11.3 million kB, swap free stayed at 1,356 kB,
`pswpin`/`pswpout` counters did not move, user-manager swap remained
2,864,861,184 bytes, and `oom=19`/`oom_kill=15` were unchanged. The source
analysis then completed successfully at 03:40:51, processed 60 segments with
zero pending segments/bytes, used 8.371 CPU seconds, and reported
`awaiting_finalized_campaign_window_end`. No OOMd or kernel OOM record
appeared through 03:41. This establishes no pressure during this short window;
it does not identify the October 28 workload mix or validate a full peak for
this service. Timer overlap was not observed in this interval.

### Post-browser-check resource state — 2026-10-29 03:44 CET

The E2E TypeScript file now passes a targeted strict `tsc --noEmit` check
under a transient 512 MiB `MemoryHigh`, 640 MiB `MemoryMax`, zero-swap,
25%-CPU scope. That check exposed a pre-existing control-flow narrowing issue
in the price-history E2E capture variable; converting it to a mutable holder
preserved the assertions and made the existing case type-check. Prettier
passes for the file. The price-history user-action case and the new timeline
timing-table case then passed **2/2 in 47.0 seconds** with one Playwright
worker under a 1 GiB `MemoryHigh`, 1,280 MiB `MemoryMax`, zero-swap, 25%-CPU
scope and 180-second timeout. Venue data was served by test fixtures; no live
exchange source was called. The timeline case asserted zero source probes and
zero Arena submissions.

At 03:43:49, host `MemAvailable` was about 10 GiB and PSI remained zero; swap
was still effectively full, with `free` showing about 1.4 MiB free. The user
manager charged 8,166,600,704 bytes memory and 2,864,803,840 bytes swap. Its event counts
remained `high=16,417,339`, `max=730,045`, `oom=19`, and `oom_kill=15`. No new
oomd or kernel OOM appeared after Oct 28 23:43:24. API and Reality were active
at restart counts 9 and 14 with zero swap. Reality's 03:43:43 status reported
`RECORDING_UNSEQUENCED`, `active_receiving`, 16 fresh books, zero failures,
and no backpressure; `sequence_verified` remains false. The same collector
PID persisted and a fresh `.open` segment was updated at 03:43:41.

This supports resuming serial, bounded, offline Frontier implementation and
verification. It does not close the host incident: swap is almost exhausted,
the user manager remains unbounded, the initiating workload remains unknown,
and brief pressure-free samples do not establish endurance. Broad suites,
concurrent research, long experiments, and any production change remain
deferred.

At 03:44:14, `/proc/swaps` read 4,192,872 kB used of 4,194,300 kB with
1,428 kB free; `MemAvailable` was 11,387,008 kB and PSI remained zero. User
manager OOM counters were unchanged, and no OOMd or kernel OOM appeared since
the 03:43:49 check.

### Post-resumption bounded UI verification — 2026-10-29 03:55 CET

Frontier resumed with a serial offline browser check. The TypeScript build
passed under a transient 768 MiB `MemoryHigh`, 1 GiB `MemoryMax`, zero-swap,
25%-CPU scope. One fixture-backed Playwright test passed in 33.8 seconds under
1 GiB high / 1,280 MiB max, zero swap, 25% CPU, one worker, and a 180-second
timeout. It paged through 26 instrument timing rows and 10 saved candidate
summaries for 12 recorded candidates, exposing the two unsaved summaries; the
test made zero public-probe requests and zero Arena submissions. No live venue
data was used.

At 03:56:57, after the final type check, host PSI was zero and `MemAvailable`
was 11,111,380 kB. Swap remained effectively full at 4,192,748/4,194,300 kB
(1,552 kB free).
User-manager counters remained `high=16,417,339`, `max=730,045`, `oom=19`, and
`oom_kill=15`. No kernel OOM or systemd-oomd kill appeared since Oct 28
23:43:24. The API and Reality remained active at restart counts 9 and 14 with
zero service swap; system `ssh.socket` was listening, and RustDesk and Caddy
were active. No production service or resource configuration was changed.
This is a bounded quiet sample; the host incident remains open because swap is
nearly full, user-manager limits remain unbounded, and the historical
initiating workload is still unidentified.

### Saved replay paging resource check — 2026-10-29 04:02 CET

The follow-up saved replay UI check was fixture-backed and ran alone under a
transient 1 GiB `MemoryHigh`, 1,280 MiB `MemoryMax`, zero-swap, 25%-CPU scope.
It passed one Playwright test in 38.9 seconds with one worker. No live source
request or Arena submission was made. At 04:02:10, PSI remained zero and
user-manager OOM counters were unchanged at 19/15. `MemAvailable` was
11,378,708 kB; swap remained 4,192,684/4,194,300 kB used (1,616 kB free).
API/Reality remained active at restart counts 9/14 with zero service swap. No
kernel OOM or oomd kill appeared after 03:56:57; the last previously recorded
OOM event remains Oct 28 23:43:24. This remains a quiet bounded interval, not
evidence of sustained host stability.

### Current cgroup attribution snapshot — 2026-10-29 04:04 CET

At 04:04:14, PSI remained zero, `MemAvailable` was 11,384,972 kB, and swap
was 4,192,504/4,194,300 kB used (1,796 kB free). The user app slice was
7,846,883,328 bytes memory and 2,236,157,952 bytes swap, with its historical
`oom=19` / `oom_kill=15` counters unchanged. Its GNOME Terminal slice alone
was 3,773,067,264 bytes memory and 1,647,288,320 bytes swap. That slice's
`memory.stat` included 2,336,428,032 bytes file cache (1,987,100,672 bytes
inactive file), 490,041,344 bytes kernel memory, and 941,285,376 bytes anon.
Its own cgroup OOM counters were zero. These are current mixed cache, kernel,
anonymous-memory, and swap charges; they do not identify which workload caused
the earlier pressure window.

The largest individual `VmSwap` process sample was the active Continental
`status.service`: 447,082,496 bytes swap, 207,802,368 bytes current cgroup
memory, and 831,500,288 bytes recorded peak since Oct 9. It has no configured
MemoryHigh, MemoryMax, or MemorySwapMax and its cgroup OOM counters are zero.
GNOME Shell and Nautilus were additional current process-level swap holders.
The Continental status service was not changed or restarted; its contribution
to present swap occupancy is not evidence that it triggered an OOM kill.

No kernel OOM or systemd-oomd kill appeared after the 04:02:10 sample. The
host remains suitable only for sequential, bounded, offline Frontier work.
Historical initiating-workload attribution and durable swap recovery remain
unresolved; no safe service change is supported by this sample alone.

### Diagnostic sampler review — 2026-10-29 04:05 CET

Review of `scripts/host_capacity_sample.py` confirmed it already records each
active process cgroup and its ancestors, including current/peak/high/max memory,
swap current/max, `memory.stat`, `memory.events`, memory PSI, CPU, I/O, and PID
counts. `host_capacity_summary.py` streams bounded time windows. The 35-second
sample around Veritas source analysis missed most of the randomized timer
start, so it cannot establish that job's peak; no sampler code change or
persistent monitor is needed. A future attribution sample should be short and
scheduled around a known task, and must not be interpreted as historical OOM
causality.
