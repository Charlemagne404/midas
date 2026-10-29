# MIDAS deployment migration plan

**Status: DEPLOYMENT PENDING.** This is a guarded plan for migrating the
installed user services from retained worktrees and mixed releases to the
unified code baseline. It is not a record of a deployment. No service was
stopped, restarted, reloaded, replaced, or reconfigured during Project
Unification.

## Destination layout

Build immutable release artifacts from one exact unified commit and its pinned
lockfiles. A future release should have a manifest that records the full Git
commit, source tree hash, Python and frontend lockfile hashes, build command,
artifact hashes, and verification results. Keep the release directory separate
from every writable store.

Suggested release layout:

```text
/home/charlie/.local/share/midas/releases/<full-commit>/
  api/
  web/
  workers/
  release-manifest.json
```

Keep service configuration under the existing protected configuration root and
keep each data owner at its current path during the first release:

- Shared API, Arena, Laboratory, paper, and historical MIDAS records:
  `/home/charlie/midas/data`
- Reality recorder and journals: `/home/charlie/midas-reality/data`
- Veritas catalogs and research state: `/home/charlie/midas-veritas/data`
- Frontier store and captures: retain their current separate Frontier-owned
  paths.

These paths are an ownership map, not approval to move or rewrite them. The
first release should change code paths only after owners have verified all
configured data paths and writer identities.

## Installed runtime at the read-only sample

The units are user services under `/home/charlie/.config/systemd/user`. Their
exact sampled paths, PIDs, limits, and seven enabled timers are in
[OPERATIONS.md](OPERATIONS.md). The transition must account for:

- API and web running from separate installed releases while the API working
  directory remains `/home/charlie/midas`.
- The Arena scheduler timer running a script from `/home/charlie/midas`.
- The protected Reality recorder, Reality API, and Reality web still depending
  on `/home/charlie/midas-reality`, including a separately installed Reality
  API release.
- Three Veritas timers using `/home/charlie/midas-veritas`; Observatory uses a
  separate versioned release.
- Five disabled timers (Reality archive, two 48-hour autonomy timers, and two
  Veritas gap-detail timers), plus the two installed static Veritas gap-detail
  one-shot units. Keep their state and logs until an owner verifies whether
  they are still needed.
- Ninety transient service records from past Arena, validation, Reality,
  Veritas, and reliability work. They were not loaded in the final read-only
  census. Reconcile their job manifests, logs, and data before historical
  cleanup.

No Docker/Podman container or cron job was found in the inventory. This does
not replace a future recheck immediately before deployment.

## Required transition sequence

1. **Admit the change.** Re-read `git status`, branch, and full commit. Confirm
   the release manifest matches the artifacts and that the pinned backend and
   frontend dependency files are unchanged from the verified build.
2. **Re-measure the host.** Capture timestamped memory availability, swap,
   memory and I/O PSI, free space, each service cgroup's `memory.current`,
   `memory.high`, `memory.max`, and event counters. Check recorder source status,
   queue pressure, storage headroom, and service PIDs. Do not use the historical
   sample as current admission evidence.
3. **Verify durable state.** Record every service's data roots, active writers,
   database/catalog identity, and source boundary. For Reality, use a finalized
   manifest and exact file hashes; explicitly classify active tails, `.copying`
   files, out-of-manifest segments, and any invalid archive provenance. Do not
   adopt or delete ambiguous material.
4. **Build and test in isolation.** Start candidate API and frontend with fresh
   temporary databases, Arena/Laboratory roots, Reality/Veritas roots, and
   Frontier store. Keep network acquisition disabled. Run the focused test
   suites, route smoke checks, frontend build, and browser checks from
   [DEVELOPMENT.md](DEVELOPMENT.md). Verify the candidate source and test inputs
   by hash.
5. **Stage units without activating them.** Render candidate unit files from
   the unified templates, substitute full release paths and explicit data
   roots, and run `systemd-analyze --user verify` on the staged definitions.
   Compare dependencies, environments, limits, restart policy, readiness, and
   timer schedules with the installed units. Resolve duplicate writers before
   activation.
6. **Prepare rollback.** Keep the current release directories and unit files
   intact. Write down the exact prior release, unit-file hash, environment,
   persistent roots, and command to restore the old mapping. Require new
   schemas to be backward compatible or have a separately verified backup and
   restore procedure. Do not use a data migration to make a code deployment
   appear complete.
7. **Obtain separate production authorization.** Before any production unit
   file is installed, reloaded, switched, stopped, or restarted, obtain explicit
   approval for the named services and exact transition window. Reality recorder
   adoption and any mutation of its active data boundary require a separate
   guarded authorization. The project-level instruction prohibits these
   actions without it.
8. **Transition one owner at a time.** During an approved change, preserve the
   service's single-writer boundary, record pre/post identities and cgroup
   counters, verify readiness and data paths, and stop immediately on failed
   provenance or unexpected resource pressure. Do not alter multiple subsystem
   owners as one opaque rollout.
9. **Close or roll back.** Compare API health, route results, frontend
   workspace loading, timer execution identity, logs, and resource events with
   the pre-change baseline. If a gate fails, restore the recorded prior code
   mapping without deleting or rewriting persistent data. Keep the candidate
   release and evidence for diagnosis.

## Protected Reality gate

The Reality recorder was running from `/home/charlie/midas-reality` at the
sample. Its cgroup had `MemoryHigh=1152 MiB`, `MemoryMax=1280 MiB`, no swap
allowance, and 33,176 cumulative `high` events with no `max` or OOM events. This
is a dated reading, not proof that a new recorder release has adequate headroom.
The host also had only 436 KiB free in 4 GiB of swap at that sample. Re-measure
the recorder-specific gate and storage reserve before any heavy validation or
deployment.

The transition is **BLOCKED BY AUTHORIZATION** until the owner separately
authorizes the exact production action. A code release, passing synthetic
tests, copied archive, or checkpoint prefix does not certify production
recovery or authorize a recorder restart.

## Not performed

- No service unit or timer was edited, disabled, enabled, or reloaded.
- No running service was stopped, restarted, or pointed at this checkout.
- No Reality, Veritas, Arena, Frontier, Laboratory, paper, or campaign data was
  moved, merged, rewritten, or deleted.
- No branch or historical worktree was deleted.
- No push or merge to protected `main` was made.

Use [OPERATIONS.md](OPERATIONS.md) for the sampled service/data map and
[UNIFICATION_REPORT.md](UNIFICATION_REPORT.md) for verified code and test
status.
