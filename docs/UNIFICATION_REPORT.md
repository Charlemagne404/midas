# MIDAS Project Unification report

**Outcome:** the unified development baseline is implemented and verified for
the bounded subsystem and application workflows listed below. Production
adoption and historical cleanup remain pending. No production service or
historical data was changed.

**Authoritative checkout:** `/home/charlie/midas-unification`

**Branch:** `codex/midas-unification`

**Code baseline commit:** `fd3d16dacdfc726915c48dcbc71321396a6b0cfa`
(`fix(reality): preserve ambiguous archive provenance`)

**Final report/documentation commit:** the final branch tip is included in the
owner handoff after this report is committed.

**Starting source commit:** `f6ac37fffcd97eafab4915492200217fbe8c358a`.

## 1. Initial state and inventory

MIDAS was split across the original `main` checkout, Reality and Veritas runtime
worktrees, Frontier, V6/research branches, readiness branches, recovery
references, temporary staging checkouts, and separate installed releases. The
running API, web frontend, recorder, timers, and Reality interface did not all
use one source path. Durable research data was spread across multiple owners and
must remain separate.

The final Git inventory counted 26 local branches (including the new
unification branch), 7 live remote heads, 29 worktrees, and no stashes. Unique
commits, dirty worktrees, active runtime paths, detached checkouts, and cleanup
candidates are recorded in
[UNIFICATION_BRANCH_INVENTORY.md](UNIFICATION_BRANCH_INVENTORY.md). No old
branch or worktree was removed. No force reset, `git clean`, or history rewrite
was used.

The read-only systemd sample found five active application/recorder units and
seven enabled timers. No MIDAS container or cron job was found. Current unit
paths, data ownership, resource limits, and time-specific resource readings are
in [OPERATIONS.md](OPERATIONS.md) and
[MIDAS_CURRENT_STATE.md](MIDAS_CURRENT_STATE.md).

A later unit census found 121 MIDAS unit-file entries, including 12 static
one-shot services, two disabled Reality shadow services, and 90 transient
service records. Twelve units were loaded active (the five services and seven
timers); seven timer-triggered one-shot services were loaded inactive; no
MIDAS unit was loaded failed. Five timers were disabled. None of the transient
records or disabled units was reset or removed.

## 2. Baseline choice and consolidated systems

The branch starts at `f6ac37fffcd97eafab4915492200217fbe8c358a`, the verified
Frontier handoff based on the integrated Veritas V6 line. It already contained
the newest compatible multi-source research, V6 catalogs and independent
economics, and the latest Frontier application shell. The unification branch
then selectively reconciled Reality/capacity work, Observatory/API integration,
readiness reporting, scheduler behavior, and tests.

The unified source contains the core and paper foundations, Prometheus/scanner,
Laboratory, Arena, Reality, Veritas V6, Frontier, Research Director,
Observatory, Mission Control, and Research Readiness. `App.tsx` owns one React
navigation shell; the API routers expose the domain workspaces. Reality,
Veritas, Frontier, Arena, and Laboratory keep distinct stores where they have
different writers or provenance contracts. Historical databases were not
physically combined.

Important local integration changes are committed as:

- `2d3e69d` — bounded Reality recovery, storage, and capacity controls.
- `17253af` — saved Observatory workspace and API projection.
- `447a4e9` — verified checkpoint acceleration and bounded public HTTP
  transport.
- `455f55f` — Reality transport age, book age, persistence and queue telemetry;
  restored the missing `packages/midas/reality/resources.py` used by full-scale
  validation and added resource-gate tests.
- `115abd7` — bounded round-robin Arena schedule dispatch so later active
  schedules are not starved by the first batch.
- `e6463ab` — Frontier test fixtures now bind raw and normalized provenance;
  production provenance checks remain strict.
- `88581c2` — standardized Python formatting scope while excluding immutable
  `deploy/runtime/**` release snapshots.
- `fd3d16d` — preserve ambiguous Reality archive files; fail closed on partial,
  unpublished, untracked, or symlinked archive entries.

The readiness branch's loading and memory-composition behavior is represented
in the single current `Readiness.tsx` workspace and the readiness API. The
Veritas V6 branch is already in the selected source ancestry. The Reality
archive-provenance and comprehensive engineering branches were inspected by
unique commit and their selected fixes were ported or matched to current code;
their entire branch histories were not merged blindly. The branch inventory
lists the source commit IDs and retained evidence.

## 3. Architecture and application result

The current architecture map assigns subsystem ownership in
[ARCHITECTURE.md](ARCHITECTURE.md). Core domain code remains separate from the
FastAPI and React edges. Research APIs read through subsystem projections.
Historical and synthetic inputs, Reality observations, virtual paper outcomes,
independent audits, and hypothetical economics stay separately labeled.
Frontier remains research-only and its source-policy gates are intact.

The unified backend started in demo mode on `127.0.0.1:18080` with a new
temporary SQLite database and temporary Arena, Laboratory, Frontier, Reality,
recording, and Veritas roots. `/openapi.json` returned 200 with 136 paths.
Health, resources, state, scenarios, paper summary, analytics, Frontier
overview/readiness, Arena overview/observatory, Laboratory catalog, and Reality
overview returned 200. The empty temporary Veritas workspace returned the
existing “Veritas evidence has not been generated” response (404); no synthetic
Veritas evidence was created. The server then shut down cleanly. The temporary
root was isolated from the active workspaces.

Frontend unit tests passed (78), and the production build, lint, and typecheck
passed. The isolated browser suite passed 19 checks with 5 skips. Browser tests
used temporary research roots; their empty Veritas state was handled by the
workspace flow. No live service was used for browser testing.

## 4. Verification

| Check | Result |
|---|---|
| Frontier backend suite | **748 passed**, one Starlette/httpx deprecation warning. |
| Reality/recovery/resource and Arena scheduler focused set after archive safeguard | **122 passed**. |
| Reality archive operations suite | **47 passed** before the final extra lock-path case; included in the later 122-test run. |
| `mypy packages/midas apps/api` | **192 source files, no issues**. |
| `ruff check .` | Passed. |
| `ruff format --check .` | Passed; 832 Python/Markdown files were formatted, with immutable runtime snapshots and archived docs excluded. |
| Web unit tests | **78 passed**. |
| Web lint, typecheck, and build | Passed. |
| Isolated browser journey | **19 passed, 5 skipped**. |
| Unified backend smoke | Started; representative core and workspace GET routes returned 200. Empty Veritas returned the documented no-evidence 404. |
| Full backend suite | **2,119 collected; partial.** The serial run was stopped after 119 passed in 319.91 seconds while still in a synthetic JSON-serialization case. No assertion failure had occurred; the full suite is not verified. |
| Locked environment install | `uv sync` was not run because `uv` was unavailable in this shell. Tests used the existing Python 3.12 environment under `/home/charlie/midas/.venv`; web tooling used the existing Node 22.23.4 / pnpm 10.18.0 installation. |

The smoke server initially failed to import the workspace package because this
checkout did not have a local virtual environment installed. It started after
setting `PYTHONPATH` to the unified `packages` directory while using the
existing test environment. The normal fresh-checkout setup remains the locked
install in [DEVELOPMENT.md](DEVELOPMENT.md); this particular checkout does not
contain its own `.venv` or frontend `node_modules` after closeout.

## 5. Runtime, research, and deployment

The active API and web still use separate immutable releases. The API working
directory and Arena timer remain tied to `/home/charlie/midas`; Reality services
remain tied to `/home/charlie/midas-reality` and one separate release; Veritas
timers remain tied to `/home/charlie/midas-veritas`. They were not redirected to
the unified branch.

Measured research roots remain in place: approximately 18 GiB under
`/home/charlie/midas/data`, 27 GiB under `/home/charlie/midas-reality/data`,
1.6 GiB under `/home/charlie/midas-veritas/data`, 17 MiB under the Frontier
data root, and separate staging, replay, release, and recovery trees. No
catalog, recording, campaign, journal, model, experiment result, snapshot, or
archive was moved, merged, rewritten, or deleted.

The production transition is **INTEGRATED, DEPLOYMENT PENDING**. Exact source
and service paths, isolation, backup, verification, activation, and rollback
steps are in [UNIFICATION_DEPLOYMENT_PLAN.md](UNIFICATION_DEPLOYMENT_PLAN.md).
Protected Reality deployment, active mutable-data migration, systemd changes,
and `main` integration are **BLOCKED BY AUTHORIZATION** until the owner
separately authorizes the specific operational transition.

## 6. Remaining known limitations

- The full backend regression run is partial, not a pass. A focused broad set
  passed; a normal bounded full run still needs an environment with appropriate
  runtime budget.
- The unified checkout has no locally installed locked Python or frontend
  dependencies. Install with the documented lockfile commands before the next
  development task; do not use the historical production checkout's data root.
- Several services and timers still depend on retained source worktrees or
  older release directories; no deployment was attempted.
- The protected Reality recorder remains source-unsequenced. The dated archive
  and resource snapshot is not current recovery or endurance certification.
- Static Veritas gap-detail units, disabled archive/autonomy timers, and
  transient test/research unit records remain unresolved; their logs, ownership,
  and attached data need review before retirement.
- Some branches contain dirty source, dated evidence, or detached commits.
  The inventory makes no destructive cleanup recommendation for ambiguous
  material.

## 7. Completion matrix

| Status | Items |
|---|---|
| **COMPLETE AND VERIFIED** | One local authoritative branch and checkout; compatible code integrated; focused Reality/Arena and Frontier suites passed; static checks and frontend build passed; temporary-root backend smoke succeeded; branch, worktree, runtime, and data inventories written. |
| **INTEGRATED, DEPLOYMENT PENDING** | Unified API and workspaces are available in source; existing installed releases and timers remain on their old paths pending staged, authorized deployment. |
| **PARTIALLY VERIFIED** | Full backend suite; real production service migration; complete live Veritas route with populated preserved data; endurance, full-store Reality recovery, and production readiness. |
| **BLOCKED BY AUTHORIZATION** | Replacing or restarting protected production services; reloading or changing production units; migrating active mutable data; pushing/merging into protected `main`; deleting historical branches or ambiguous worktrees. |
| **DEFERRED** | Physical data consolidation, optional refactors beyond required integration, historical cleanup, and standalone candidate-transition or measurement tooling that has no active runtime dependency. |

## 8. Exact next-session starting point

```bash
cd /home/charlie/midas-unification
git switch codex/midas-unification
git status --short --branch
git rev-parse HEAD
```

Install from `uv.lock` and `apps/web/pnpm-lock.yaml` using the commands in
[DEVELOPMENT.md](DEVELOPMENT.md). Read [MIDAS_CURRENT_STATE.md](MIDAS_CURRENT_STATE.md)
for capabilities and limits, [ARCHITECTURE.md](ARCHITECTURE.md) for ownership,
and [OPERATIONS.md](OPERATIONS.md) before touching runtime services or data.
The final branch tip and clean worktree are recorded after the report commit.
