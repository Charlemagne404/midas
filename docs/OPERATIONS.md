# MIDAS operations

**Resource sample:** 2026-10-29 23:09:12 UTC. **Final unit census:**
2026-10-29 23:24:58 UTC, read-only. This document describes the existing
runtime, not a deployment of `codex/midas-unification`.

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
