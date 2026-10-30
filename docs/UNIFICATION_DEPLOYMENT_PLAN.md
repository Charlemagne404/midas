# MIDAS deployment migration plan

**Status: RELEASE CANDIDATE BUILT; PRODUCTION MIGRATION PENDING.** This is the
guarded plan for migrating installed user services from retained worktrees and
mixed releases to the unified code baseline. The 2026-10-30 migration snapshot
and service decisions are in
[UNIFICATION_PRODUCTION_MIGRATION_REPORT.md](UNIFICATION_PRODUCTION_MIGRATION_REPORT.md).

## Destination layout

Build immutable release artifacts from one exact unified commit and its pinned
lockfiles. A future release should have a manifest that records the full Git
commit, source tree hash, Python and frontend lockfile hashes, build command,
artifact hashes, and verification results. Keep the release directory separate
from every writable store.

Use `uv sync --locked --group dev --group arena-rl` for the complete CPU Arena
runtime; `arena-rl` and the explicit CPU Torch index are resolved into
`uv.lock`. A core-only environment is suitable only for workflows that do not
load Arena modeling/training or NumPy/scikit-learn research paths.

The candidate release layout separates application code, its locked Python
environment, per-release configuration, runtime state, and research stores:

```text
/home/charlie/.local/share/midas/releases/<full-commit>/
  apps/
  packages/
  apps/web/dist/
  release-manifest.json
/home/charlie/.local/share/midas/venvs/<full-commit>/
/home/charlie/.config/midas/releases/<full-commit>.env
/home/charlie/.local/state/midas/                 # disposable runtime state
/home/charlie/midas/data/                         # persistent shared research
/home/charlie/midas-reality/data/                 # Reality owner
/home/charlie/midas-veritas/data/                 # Veritas owner
```

Release directories are built from one full commit and become read-only after
their source, dependency lockfiles, frontend build, and manifest are verified.
The Python environment and systemd environment file use the same full commit
identity but live outside the code directory. The environment file contains
absolute data paths and no implicit source activation. The API reports its
release ID, source commit, effective settings fingerprint, Alembic schema
revision, deployment timestamp when supplied, and runtime state from
`/api/health`. The web build embeds its source commit in Research Readiness.
Systemd logs remain in the journal; ephemeral API files live below
`~/.local/state/midas`.

The staged per-release unit templates are
`deploy/systemd/user/midas-api-release@.service`,
`deploy/systemd/user/midas-web-release@.service`, and
`deploy/systemd/user/midas-reality-release@.service`. The API environment
example is `deploy/config/midas-release.env.example`. They are not installed
or activated by this plan. The sample keeps `MIDAS_MODE=demo` and all explicit
Frontier collection switches false. Reality config must set
`allowed_storage_root` explicitly when its immutable release writes to the
existing external recording root. Installing the API and web templates still
requires a coordinated cutover because both bind active production ports and
the API and Arena scheduler share durable state.

Keep each data owner at its current path during the first release:

- Shared API, Arena, Laboratory, paper, and historical MIDAS records:
  `/home/charlie/midas/data`
- Reality recorder and journals: `/home/charlie/midas-reality/data`
- Veritas catalogs and research state: `/home/charlie/midas-veritas/data`
- Frontier store and captures: retain their current separate Frontier-owned
  paths.

These paths are an ownership map, not approval to move or rewrite them. The
first release changes only code paths after owners verify all configured data
paths and writer identities. Do not place mutable data beneath a release.

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
5. **Stage units without activating them.** Verify the release template
   instances against the exact full commit, substitute explicit data roots in
   a per-release environment file, and run `systemd-analyze --user verify` on
   the staged definitions.
   Compare dependencies, environments, limits, restart policy, readiness, and
   timer schedules with the installed units. Resolve duplicate writers before
   activation.
6. **Prepare rollback.** Keep the current release directories and unit files
   intact. Write down the exact prior release, unit-file hash, environment,
   persistent roots, and command to restore the old mapping. Require new
   schemas to be backward compatible or have a separately verified backup and
   restore procedure. Do not use a data migration to make a code deployment
   appear complete.
7. **Respect the protected boundary.** This migration directive authorizes
   reversible transitions for eligible, non-protected services when all gates
   pass. The protected Reality recorder and any change to its active data
   boundary still require separate explicit authorization. Do not introduce
   user-facing downtime without a reviewed traffic switch and rollback path.
   The API/web cutover is a coordinated writer and user-facing transition; the
   current frontend contract is not compatible with the old API.
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

## Not performed at the original unification handoff

- No service unit or timer was edited, disabled, enabled, or reloaded.
- No running service was stopped, restarted, or pointed at this checkout.
- No Reality, Veritas, Arena, Frontier, Laboratory, paper, or campaign data was
  moved, merged, rewritten, or deleted.
- No branch or historical worktree was deleted.
- No push or merge to protected `main` was made.

The production migration follow-up is recorded in
[UNIFICATION_PRODUCTION_MIGRATION_REPORT.md](UNIFICATION_PRODUCTION_MIGRATION_REPORT.md).

Use [OPERATIONS.md](OPERATIONS.md) for the sampled service/data map and
[UNIFICATION_REPORT.md](UNIFICATION_REPORT.md) for verified code and test
status.
