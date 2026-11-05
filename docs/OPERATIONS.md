# MIDAS operations (historical systemd snapshot, 2026-10-29)

**Historical record:** the detailed service, PID, and resource values below
were sampled read-only on 2026-10-29. They are not current service facts. Use
the [maintainer handoff](MIDAS_MAINTAINER_HANDOFF.md) for the 2026-11-05
inventory and [backup and recovery guide](BACKUP_AND_RECOVERY.md) for current
data protection procedures. Recheck live services before any operation.

## Active service ownership

All installed MIDAS units are user services under
`/home/charlie/.config/systemd/user`. The unit templates in
`deploy/systemd/user` still contain legacy worktree paths. Do not infer that the
unified checkout is serving production.

| Unit | Current code path | Data/config path | Limits and notes |
|---|---|---|---|
| `midas-api.service` | Release `/home/charlie/.local/share/midas-api/releases/a152999`; working directory `/home/charlie/midas` | Main checkout `.env` and `data/` | `MemoryHigh=1536 MiB`, `MemoryMax=1792 MiB`, `MemorySwapMax=0`; PID 1218662. |
| `midas-web.service` | Release `/home/charlie/.local/share/midas-api/releases/767f330/apps/web` | Immutable release | Active Vite service; no memory cap. Its release identity differs from the API release. |
| `midas-reality.service` | `/home/charlie/midas-reality` | `/home/charlie/midas-reality/deploy/reality.json` and Reality data | Protected recorder; `MemoryHigh=1152 MiB`, `MemoryMax=1280 MiB`, swap max 0; PID 1235804. |
| `midas-reality-api.service` | Release `/home/charlie/.local/share/midas-capacity/interface-capacity-v3-20261021`; working directory `/home/charlie/midas-reality` | Reality workspace | `MemoryHigh=576 MiB`, `MemoryMax=640 MiB`, swap max 0; PID 610950. |
| `midas-reality-web.service` | `/home/charlie/midas-reality/apps/web` | Reality web worktree | `MemoryMax=512 MiB`; PID 2890819. |

### Effective restart, dependency, and resource policy

These are effective user-manager settings at the 2026-10-29 23:24:58 UTC
census. The long-running API, web, recorder, and Reality interface units use
`Restart=on-failure`. Timer-triggered workers use `Restart=no`. Most units
require `basic.target` and `app.slice`; web units are ordered after their API,
and Reality/Veritas one-shots are ordered after their respective timers.

| Unit | Restart | Effective memory limit | Additional dependency/configuration note |
|---|---|---|---|
| `midas-api.service` | on-failure | High 1536 MiB; max 1792 MiB; swap 0 | Requires `basic.target` and `app.slice`; after network. Four loaded drop-ins. |
| `midas-web.service` | on-failure | No memory cap | After `midas-api.service`; four loaded drop-ins. |
| `midas-reality.service` | on-failure | High 1152 MiB; max 1280 MiB; swap 0 | After `network-online.target`; three runtime `user.control` memory overrides. |
| `midas-reality-api.service` | on-failure | High 576 MiB; max 640 MiB; swap 0 | After network; seven loaded release/quality/resource drop-ins. |
| `midas-reality-web.service` | on-failure | Max 512 MiB | After `midas-reality-api.service`. |
| `midas-arena-scheduler.service` | no | Max 512 MiB | After its timer; runtime CPU quota drop-in. |
| `midas-reality-capacity.service` | no | High 160 MiB; max 192 MiB; swap 0 | After its timer; runtime CPU and memory-limit drop-ins. |
| `midas-reality-research.service` | no | Max 768 MiB | After its timer; up to 12-hour start timeout. |
| `midas-reality-shadow-integrity.service` | no | Max 256 MiB | After its timer. |
| `midas-veritas-observatory.service` | no | Max 256 MiB; swap 0 | Versioned release; after timer and network-online; V6 candidate drop-in. |
| `midas-veritas-research-director.service` | no | Max 512 MiB | After timer; runtime CPU quota drop-in. |
| `midas-veritas-source-analysis.service` | no | Max 256 MiB | After timer; frozen-campaign import and runtime CPU quota drop-ins. |

Several effective values come from multiple service drop-ins, including
runtime files below `/run/user/1000/systemd/user.control`. The unit templates
in the repository do not fully describe the loaded service configuration.
Deployment staging must inventory the drop-ins and compare their semantics;
do not copy the live user-control overrides into new units without review.

### Timers and one-shot jobs

The timer census found seven enabled timers and five disabled timers. Trigger
definitions and randomized delays below were read from the installed timer
units; all enabled timers are persistent.

| Timer | State and trigger | Delay and owner |
|---|---|---|
| `midas-arena-scheduler.timer` | enabled; minutely | 5 s randomized delay; `/home/charlie/midas` Arena root. |
| `midas-reality-capacity.timer` | enabled; 1 min after boot, then every 30 min | no randomized delay; Reality workspace. |
| `midas-reality-research.timer` | enabled; daily at 02:30 UTC | up to 10 min randomized delay; Reality workspace. |
| `midas-reality-shadow-integrity.timer` | enabled; daily at 03:00 UTC | up to 5 min randomized delay; Reality workspace. |
| `midas-veritas-observatory.timer` | enabled; every 30 min | up to 2 min randomized delay; Veritas workspace and release `e988cbb0af86fe89e07da9af8036598b65068deb`. |
| `midas-veritas-research-director.timer` | enabled; minutes 15 and 45 each hour UTC | up to 30 s randomized delay; Veritas workspace. |
| `midas-veritas-source-analysis.timer` | enabled; minutes 10 and 40 each hour UTC | up to 60 s randomized delay; Veritas workspace. |
| `midas-reality-archive.timer` | disabled; daily at 04:00 UTC | up to 5 min randomized delay; Reality archive root. |
| `midas-autonomy-48h-001.timer` | disabled; every 5 min after 2 min boot delay | up to 15 s randomized delay; historical autonomy data. |
| `midas-autonomy-48h-002.timer` | disabled; every 5 min after 2 min boot delay | up to 5 s randomized delay; historical autonomy data. |
| `midas-veritas-gap-detail-analysis.timer` | disabled; minutes 05, 20, 35, and 50 UTC | not persistent; Veritas research data. |
| `midas-veritas-gap-detail-v2.timer` | disabled; every 5 min beginning at minute 02 UTC | not persistent; up to 20 s randomized delay. |

The unit census found 121 MIDAS unit-file entries: five enabled service units,
12 static one-shot service units, two disabled Reality shadow services, 90
transient service records, seven enabled timers, and five disabled timers. The
transient records include 37 Arena, 17 validation, 15 Reality, six Veritas,
three each for current/evidence/reliability, two capacity, and one each for
guard, PPO, Prometheus, and public-series work. They were not loaded units in
the final census. Their logs and linked job/evidence roots were not cleared.

The five long-running services and seven timers were active. Seven
timer-triggered one-shot services were loaded inactive; no MIDAS unit was
loaded in a failed state in the final census. `midas-reality-archive.timer`,
both `midas-autonomy-48h-00*.timer` units, and both Veritas gap-detail timers
are disabled. The static
`midas-veritas-gap-detail-analysis.service` and
`midas-veritas-gap-detail-v2.service` remain installed for historical review.
No unit was reset or removed during unification; use per-job manifests and
service logs to reconcile them before any cleanup.

Installed static one-shot service units are `midas-arena-scheduler.service`,
`midas-autonomy-48h-001.service`, `midas-autonomy-48h-002.service`,
`midas-reality-archive.service`, `midas-reality-capacity.service`,
`midas-reality-research.service`, `midas-reality-shadow-integrity.service`,
`midas-veritas-gap-detail-analysis.service`,
`midas-veritas-gap-detail-v2.service`, `midas-veritas-observatory.service`,
`midas-veritas-research-director.service`, and
`midas-veritas-source-analysis.service`. `midas-reality-shadow.service` and
`midas-reality-shadow-successor.service` are disabled service units.

The disabled timers are `midas-autonomy-48h-001.timer`,
`midas-autonomy-48h-002.timer`, `midas-reality-archive.timer`,
`midas-veritas-gap-detail-analysis.timer`, and
`midas-veritas-gap-detail-v2.timer`. Keep the historical 48-hour unit files
and their data references until their owner confirms retirement.

No MIDAS Docker/Podman container or cron entry was found in the inventory.

## Read-only inspection

These commands inspect user units and logs without changing them:

```bash
systemctl --user status midas-api.service midas-web.service midas-reality.service
systemctl --user list-timers --all
systemctl --user show midas-reality.service -p MainPID -p ControlGroup -p MemoryHigh -p MemoryMax
journalctl --user -u midas-reality.service --since '30 minutes ago' --no-pager
free -h
cat /proc/pressure/memory /proc/pressure/io
df -h /home /mnt/continental-cloud/data
```

Capture timestamp with every resource reading. At the unification sample,
`MemAvailable` was about 10 GiB, swap had only 436 KiB free, memory PSI was 0%,
and I/O PSI was about 1.4% avg10. The Reality cgroup used 977,072,128 bytes;
its `memory.events` showed 33,176 `high`, 0 `max`, and 0 OOM events. These
counters are cumulative and the reading is not a sustained recovery result.

## Durable data and recovery

The active Reality recorder writes under `/home/charlie/midas-reality/data`.
Veritas catalogs and schedules use `/home/charlie/midas-veritas/data`. Arena,
Laboratory, paper-trading, historical experiments, and reliability evidence
remain under their existing roots in `/home/charlie/midas/data`. Frontier
captures and its SQLite store remain separate. Staging and recovery material
under `/mnt/continental-cloud/data/midas-reality-staging` is preserved; its
presence alone does not certify current recovery provenance.

Before a separately authorized recovery or deployment transition:

1. Record the exact unit, source commit, source-tree hash, unit-file hash,
   configuration identity, PID, cgroup limits/events, and persistent root.
2. Stop admission of new work only through the approved deployment procedure;
   do not edit or move active recorder data.
3. Produce a verified backup or immutable recovery snapshot on the intended
   target filesystem. Check the full manifest, segment set, byte counts, and
   hashes against the recorded boundary.
4. Run candidate verification in an isolated staging root with bounded
   resources. Bind receipts to the candidate source hash and exact inputs. The
   archive tool now preserves unresolved `.copying` files, orphan segments,
   pending manifests, and unsafe links for explicit provenance review; do not
   remove them to make a retry pass.
5. Review rollback target, data ownership, unit dependencies, and service
   health before any production transition.

`scripts/reality_full_scale_validation.py` includes read-only inventory and a
guarded recovery workflow. Its `run`, `resume`, and `worker` modes are not
ordinary health checks. Do not use them against the protected production store
without a separately authorized run plan and verified staging admission.

## Release and rollback shape

The preferred runtime design is a versioned, immutable release directory plus
service-specific durable data roots. The currently installed API and web
releases are already separate, while Reality and Veritas still rely on retained
worktrees or paths under their workspaces. The canonical release layout,
unit-file changes, validation steps, and rollback sequence are prepared in
[UNIFICATION_DEPLOYMENT_PLAN.md](UNIFICATION_DEPLOYMENT_PLAN.md); none has been
applied.

For a future release, stage backend and frontend artifacts from the same
unified commit and lockfiles, verify their manifest hashes, install new unit
templates beside the current ones, and exercise startup with temporary data
roots. Keep old releases and all persistent stores until the new unit and
rollback path have been reviewed. Do not change `main`, move a database, switch
service source paths, reload systemd, or restart a live unit as part of a local
development run.

## Current operational boundary

The protected Reality recorder and all production services were left running
on their original sources. No service was restarted, stopped, replaced,
reconfigured, reloaded, or pointed at the unified branch. Production adoption
is **DEPLOYMENT PENDING**; the exact approvals and transition checklist are in
the deployment plan.

## Migration remeasurement — 2026-10-30

The active PIDs and source paths in the service table remained the same at the
00:56–00:57 UTC remeasurement. The main API still reported old release a152999
on port 8000; the dashboard remained on 5173, the protected recorder on its
original PID and config, and the two Reality interface services on 8010 and
5180. The terminal-owned dashboard on port 5174 remained a separate
development process.

The host had 9.9 GiB MemAvailable and 134 GiB free on the root filesystem, but
the 4 GiB swap file was 99.99% occupied. A one-second vmstat interval showed
no swap-in or swap-out. Latest CPU PSI some was 2.40% avg10 and 9.67% avg300;
I/O PSI some/full was 0.91%/0.79% avg10. The user slice used about 9.9 GiB and
its cumulative memory.events showed 19 OOM events and 15 OOM kills. The API
and Reality service cgroups had 11,692 and 33,176 high events, respectively,
with zero max/OOM events in those service cgroups.

At 00:58 CET, systemd-oomd killed nine processes in the isolated
“MIDAS unified release frontend unit tests” scope after reclaim pressure. A
later serial run passed. This was not a production service. Earlier Oct 28
OOMD events had killed the API and Reality recorder before automatic recovery;
their current restart counters are 9 and 14. The resource sample permits
capped isolated work, but does not establish enough sustained headroom for an
overlapping production deployment.

The new release, matching per-release Python environment, configuration, and
three systemd templates are staged under versioned paths. Unit verification
passed, but none of the templates was installed or activated. The candidate
uses explicit persistent data roots and keeps Frontier public-source probes
disabled. API and web remain a coordinated cutover because the API database
and Arena timer have active shared state and the route contracts differ.

The current Reality read-only projection varied between stale and
active_receiving during the snapshot. At the last sample it showed 16 fresh
books, sequence verification false, 25,395 lifetime gap records, and a
retained stale-timeout diagnostic. Veritas returned
insufficient_independent_evidence; its finalized-source projection covered
40,967 of 40,967 segments, with zero positive gross pairs and zero candidate
events. These are source and research-quality limitations, not deployment
health claims.

No service migrated. The protected recorder transition still requires
separate authorization after fresh resource admission and data-root rollback
preflight. The exact staged unit, configuration identities, continuity
estimate, and executable stop/start/rollback procedure are in the
[migration report](UNIFICATION_PRODUCTION_MIGRATION_REPORT.md).

## Blocker-resolution remeasurement — 2026-10-30 21:36–21:40 UTC

The follow-up engineering report is
[UNIFICATION_PRODUCTION_BLOCKER_RESOLUTION.md](UNIFICATION_PRODUCTION_BLOCKER_RESOLUTION.md).
It supersedes the older point-in-time memory and swap figures above for
admission decisions; those earlier records remain historical evidence.

At the 21:36 UTC `/proc` sample, the host had 16.27 GB RAM, 9.18 GiB
MemAvailable, 4 GiB swap with about 5.3 MiB free, 4.54 GiB anonymous pages,
and 5.91 GiB page cache. Memory PSI some/full was 0%; CPU PSI some was 2.44%
avg10 and 5.55% avg300; I/O PSI some/full was about 1.06% avg10. A two-second
swap sample during subsequent scoped checks was normally 0/0; one sample
observed one page-in without memory PSI. Heavy jobs require no sampled swap
movement and at least 256 MiB free swap. Short bounded checks permit at most
eight pages per sample, retain PSI/cgroup gates, and run with swap disabled.

`Committed_AS` measured 22.7 GiB against a 11.76 GiB `CommitLimit` with
`vm.overcommit_memory=0` and ratio 50. This virtual commitment is not resident
memory use. The user-manager cgroup had no finite `MemoryHigh`/`MemoryMax`,
used about 9.8 GiB, and retained 19 OOM / 15 OOM-kill events. The API cgroup
used about 561 MB and had about 1.05 GiB headroom to `MemoryHigh`; the Reality
recorder used about 1.21 GB with less than 2 MiB headroom. Their current
service cgroups showed zero OOM kills. API cgroup usage included about 405 MB
inactive file cache; Reality included about 588 MB. This sample does not
establish sustained stability or a Python heap profile.

The Oct 30 systemd-oomd event killed the isolated frontend-test scope after
user-slice pressure reached 58.40%, above the 50% threshold for more than 20
seconds with reclaim activity. It was not a production API or Reality kill.
No new kernel OOM line appeared in the bounded Oct 29–30 kernel journal query.
An active Veritas source-analysis one-shot was observed during final inventory;
it was preserved and no competing test or research job was started.

The new admission and SQLite snapshot tools passed focused unit tests and
small fixture rehearsal. A heavy check for a 12,500 MiB snapshot plus 5,120
MiB reserve was denied before workload start because the Reality cgroup lacked
64 MiB headroom and free swap was below 256 MiB. The live 12.58 GB SQLite
database therefore has no new backup or restore evidence. The historic
11.26 MB fixture passed full snapshot/restore integrity and the unified API
two-start compatibility check; it is synthetic legacy data and cannot
substitute for production.

The contract diff found 60 candidate route-method additions and 35 added
schemas, with no removed old operation or changed existing request/response
contract fields. The unified web still requires the candidate API for those
new routes. A versioned Arena dispatcher service and timer are staged under
`deploy/systemd/user`; neither is installed, enabled, or started. The
complete verified gates and remaining conditions are in the blocker-resolution
report.
