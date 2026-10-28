# MIDAS Host Memory Pressure and OOM Incident

**Incident date:** 2026-10-28 (CET)

**Checkpoint captured:** 2026-10-28 23:54 CET

**Scope:** Host reliability interruption during Project Frontier

**Frontier branch:** `codex/frontier-20261026`, checkpoint `53c21a316cfc2fea0a15a1cfa5c7ae03f34a76cb`

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

- The five-minute Veritas gap-detail timer is stopped. Inspection confirmed
  that it only replays finalized segments, has no reverse dependents, and is
  not part of live Reality collection.
- The Reality capacity monitor has runtime-only `MemoryHigh=128M`,
  `MemoryMax=192M`, and `MemorySwapMax=0`. Its previous 128 MiB hard cap caused
  seven kernel memcg OOM kills. The adjustment is bounded and reversible; its
  next scheduled run has not yet validated the new limit.

Reality was killed by systemd-oomd and automatically restarted. Its restart
path fully replays and verifies the recording before resuming collection. At
23:54 CET it remained active but had not written a fresh status since before
the restart and was within 0.8 MiB of `MemoryHigh`. Thus the service process is
alive, but collector recovery and current-boundary capture are not verified.
No operator restart or protected service configuration change was made.

**The host is not yet safe for Frontier tests or research batches.** Continue
only static/documentation work until Reality has demonstrably resumed capture,
service headroom recovers, and memory pressure remains low across multiple
scheduled-job cycles. The eight-minute quiet interval after the last OOMd kill
is too short to claim recovery.

## Observed impact and timeline

### systemd-oomd kills

All eight entries explicitly cite user-session memory pressure greater than
50% for over 20 seconds with reclaim activity:

| CET | Killed unit/scope | User-session pressure |
| --- | --- | ---: |
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
- The state after the 23:43 Reality restart is not proven to meet the latest
  collection boundary. The report does not claim recovery or data continuity.

## Changes made and rollback

### Stopped auxiliary gap-detail timer

Inspection confirmed the timer was scheduled every five minutes
(`OnCalendar=*-*-* *:02/5:00 UTC`), `Persistent=false`, and launched a oneshot
that replays finalized Reality segments into Veritas gap-detail/Arena outputs.
The unit did not collect live market data. Reverse dependency inspection found
no other units requiring the timer. The timer was stopped through the user
systemd manager and was inactive by 23:49 CET. It remains enabled, so the
temporary stop ends if the user manager is restarted or the timer is explicitly
started.

Rollback / resume:

```sh
systemctl --user start midas-veritas-gap-detail-v2.timer
```

No replay service was manually started and no Arena or Veritas evidence was
modified.

### Bounded the Reality capacity monitor at runtime

The unit runs about every 30 minutes, is a `Type=oneshot`, has a 60-second
timeout, and writes only the capacity report. Before this incident change it
had `MemoryMax=128M`, no explicit `MemoryHigh`, and unlimited swap. A runtime
override now sets `MemoryHigh=128M`, `MemoryMax=192M`, and `MemorySwapMax=0`.
The effective properties were read back successfully; the service was
inactive, so no running job or live collector was restarted. The underlying
unit file under `~/.config/systemd/user/` was not edited. systemd stored the
override under `/run/user/1000/systemd/user.control/`, so it is runtime-only.

Rollback the effective memory properties:

```sh
systemctl --user set-property --runtime midas-reality-capacity.service \
  MemoryHigh=infinity MemoryMax=128M MemorySwapMax=infinity
```

The override is scoped to this short monitor. It does not relax limits on
Reality, API, or any other unit. Its next timer run at approximately 00:16 CET
is still required to validate runtime behavior under the new bound.

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
- `midas-reality-capacity.service`: last completed successfully at 23:46:11,
  before the runtime limit adjustment; next scheduled run is the validation
  point.
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

- The gap-detail timer was `inactive/dead` and still `enabled`; its last
  trigger remained 23:42:14 CET.
- Capacity monitor effective properties read back as `128M` high, `192M` max,
  and swap max `0`; no follow-up execution has occurred yet.
- At 23:51:44 host PSI avg10 was 0%, avg300 was 3.82%; there were no new oomd
  kill entries after 23:43:24 through that sample. The quiet interval was only
  about eight minutes total and about five minutes after stopping the timer.
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
4. The capacity timer completes its next bounded run under the runtime cap.
5. The gap-detail timer remains stopped until replay scheduling and aggregate
   memory admission are reviewed; restarting it is available through the
   rollback command above.

Until then, Frontier may continue static/documentation work only. Do not run
tests, replays, live probes, or batch research. Continue to preserve the
untracked `data/frontier-public-probes/` and all Reality/Veritas/Arena data.
