# MIDAS current state

**Freshness note:** this remains the 2026-10-29 point-in-time snapshot. The later 2026-10-30 release, resource remeasurement, and migration outcome are in [UNIFICATION_PRODUCTION_MIGRATION_REPORT.md](UNIFICATION_PRODUCTION_MIGRATION_REPORT.md).

**Snapshot:** read-only service and host sample at `2026-10-29 23:09:12 UTC` (2026-10-30 00:09 CET). Repository code baseline: `fd3d16dacdfc726915c48dcbc71321396a6b0cfa`; documentation closeout is committed on the same branch. Historical observations are preserved in [the archived current-state ledger](history/MIDAS_CURRENT_STATE_HISTORY_2026-10-29.md) and dated engineering reports.

## Authoritative development baseline

- **Path:** `/home/charlie/midas-unification`
- **Branch:** `codex/midas-unification`
- **Starting implementation:** `f6ac37fffcd97eafab4915492200217fbe8c358a`, the verified Frontier handoff based on the Veritas V6 integration.
- **Working state:** code and documentation are committed locally; the branch is not pushed or merged into protected `main`.
- **Next development session:** open this checkout and branch. Check `git status --short` and `git rev-parse HEAD` before changing files.

The old `/home/charlie/midas` checkout remains on `main` because the live API and Arena scheduler use it. It is a runtime dependency, not the development baseline. The Reality and Veritas worktrees also remain in place for active services and data ownership.

## Integrated capabilities

| Area | Current implementation and boundary |
|---|---|
| Core and paper foundations | Exact arithmetic, separate risk gates, deterministic simulation, and virtual paper accounting. MIDAS has no real order submission, wallet, deposit, or credential path. |
| Market Data | Public, read-only acquisition and normalized observations. Frontier adapters remain capability and source-policy gated. |
| Reality | Recording, source-quality observations, reconstruction, replay, and recovery. The unified code reports WebSocket transport activity separately from per-market book freshness, bounded queue pressure, and recent persistence latency. Ambiguous partial or unpublished archive files are preserved for provenance review. No protected recorder transition was performed. |
| Veritas V6 | Versioned scan/analysis catalogs, independent economic audit, and evidence qualification remain separate from source observations. Conditional assumptions and incomplete evidence remain explicit. |
| Frontier | Bounded multi-venue evidence store, hypothesis and review history, deterministic replay, and separate arithmetic audit. Stored observations remain immutable and venue-specific. |
| Laboratory and Arena | Deterministic synthetic experiments, bounded job admission, artifact verification, and a fair rotating schedule dispatcher. No campaign or long-running worker was started for this mission. |
| Research Director and Observatory | Research coordination and read-only catalog projections are integrated through the shared API. |
| Mission Control and Research Readiness | One React shell contains the scanner, paper, Reality, Veritas, Frontier, Laboratory, Arena, Observatory, readiness, analytics, settings, and operations views. The existing `Readiness.tsx` is the single readiness workspace. |

A saved result, a recorded observation, a synthetic simulation, a virtual paper outcome, and an independently checked calculation are different evidence classes. None establishes realized trading profit or real fills.

## Live service architecture

This is a point-in-time user-systemd inventory. Installed units live under `/home/charlie/.config/systemd/user`; repository templates are under `deploy/systemd/user`. The running services still reference legacy worktrees or separately versioned releases.

| Unit | Active source/runtime path | Persistent owner or boundary |
|---|---|---|
| `midas-api.service` | API release `/home/charlie/.local/share/midas-api/releases/a152999`; `WorkingDirectory=/home/charlie/midas`; PID 1218662 | Main checkout configuration and data; `MemoryHigh=1536 MiB`, `MemoryMax=1792 MiB`, swap max 0. |
| `midas-web.service` | Web release `/home/charlie/.local/share/midas-api/releases/767f330/apps/web` | Versioned web release; no memory limit is set. |
| `midas-reality.service` | `/home/charlie/midas-reality`; `deploy/reality.json`; PID 1235804 | Protected recorder and Reality data; `MemoryHigh=1152 MiB`, `MemoryMax=1280 MiB`, swap max 0. |
| `midas-reality-api.service` | API release `/home/charlie/.local/share/midas-capacity/interface-capacity-v3-20261021`; working directory `/home/charlie/midas-reality`; PID 610950 | Reality workspace; `MemoryHigh=576 MiB`, `MemoryMax=640 MiB`, swap max 0. |
| `midas-reality-web.service` | Vite source `/home/charlie/midas-reality/apps/web`; PID 2890819 | Legacy Reality web checkout; `MemoryMax=512 MiB`. |

Seven enabled timers were present: Arena scheduler; Reality capacity, research, and shadow integrity; Veritas observatory, research director, and source analysis. The Arena timer's one-shot service uses `/home/charlie/midas`; Reality timers use `/home/charlie/midas-reality`; Veritas research services use `/home/charlie/midas-veritas`. The Veritas observatory runs from release `e988cbb0af86fe89e07da9af8036598b65068deb` and writes to the Veritas workspace. A later unit census found 121 MIDAS unit-file entries, including 90 transient service records from past Arena, validation, Reality, Veritas, and reliability work; these were not loaded units, and no unit state was cleared. Five timers were disabled, including archive, two 48-hour autonomy, and two Veritas gap-detail timers. The static gap-detail services remain installed. No unit was restarted, reloaded, disabled, or rewritten. No MIDAS container or cron job was found.

At the sample time, host memory available was about 10 GiB and swap was effectively full (436 KiB free of 4 GiB). Memory PSI was 0% over the sampled windows; I/O PSI was about 1.4% avg10. Reality cgroup memory was 977,072,128 bytes against 1,207,959,552-byte `MemoryHigh` and 1,342,177,280-byte `MemoryMax`; its counters showed 33,176 high events and zero max/OOM events. These are time-specific measurements, not a sustained capacity guarantee.

## Preserved data and ownership

No research database, recording, model, journal, campaign, archive, snapshot, or runtime release was merged, migrated, or rewritten during Project Unification.

| Path | Measured inventory | Ownership and handling |
|---|---:|---|
| `/home/charlie/midas/data` | 18 GiB | Shared historical scanner, paper, Arena, Laboratory, research, reliability, and campaign data. Multiple active writers; preserve in place. |
| `/home/charlie/midas-reality/data` | 27 GiB | Reality recordings, datasets, journals, research, and canary/export data. Recorder-owned; preserve and do not migrate while active. |
| `/home/charlie/midas-veritas/data` | 1.6 GiB | Veritas V6 catalogs, scans, experiments, Arena records, and scheduled analysis outputs. Keep physically separate. |
| `/home/charlie/midas-frontier/data` | 17 MiB | Public captures, evidence receipts, and Frontier research store. Preserve raw and normalized evidence. |
| `/home/charlie/midas-engineering-mission-20261025/data` | 1.3 GiB | 522-file offline Veritas replay evidence. The worktree also contains more than 3,000 untracked data files; preserve it intact. |
| `/mnt/continental-cloud/data/midas-reality-staging` | 6.2 GiB | Recovery/staging material, including the 5.1 GiB `archive-mission3`. Its historical provenance is not a current-boundary recovery certification. |
| `/home/charlie/.local/share/midas-api/releases` | 601 MiB | Immutable API and web release directories, including the active `a152999` and `767f330` releases. |
| `/home/charlie/.local/share/midas-capacity` | 29 MiB | Versioned Reality interface releases. |
| `/home/charlie/.local/share/midas-veritas/releases` | 85 MiB | Versioned Veritas observer release. |

Sizes are the read-only inventory captured on 2026-10-29. Do not infer that ignored files, copied archives, or staging trees are disposable. No database consolidation is planned merely to normalize layout.

## Verification status

- Full Frontier backend suite: **748 passed**, one upstream Starlette/httpx deprecation warning.
- Focused Reality, recovery/resource, and Arena schedule tests: **122 passed** after the archive safeguard; one upstream deprecation warning.
- Full-project typing: **mypy packages/midas apps/api — 192 source files, no issues**.
- Python lint and formatting: **`ruff check .` and `ruff format --check .` passed**. Immutable `deploy/runtime/**` snapshots and archived docs are excluded from Ruff so their contents remain unchanged.
- Frontend unit tests: **78 passed**; lint, typecheck, and production build passed.
- Isolated browser suite: **19 passed, 5 skipped**. The test used temporary Lab/Reality/Arena/Frontier roots and the unified checkout as the empty Veritas workspace.
- Unified API smoke: startup completed in demo mode with temporary data roots. OpenAPI exposed 136 paths; representative core, Reality, Frontier, Arena, Laboratory, and readiness GET routes returned 200. The empty Veritas workspace returned its no-evidence 404 without generating synthetic evidence.
- Broad backend suite: **2,119 tests collected**. The serial run was stopped after **119 passed in 319.91 seconds** while a synthetic JSON serialization test was still running. It had no assertion failure before interruption; the complete suite is **not verified**.
- `uv sync` was not run because `uv` was unavailable in this shell. Verification used the existing Python 3.12 environment at `/home/charlie/midas/.venv`; Node was 22.23.4 and pnpm was 10.18.0.

## Remaining state

The unified development baseline is implemented and checked through the focused subsystem, frontend, and browser suites. **Production adoption is pending.** The API, web, Reality recorder, Reality API/web, Arena timer, and Veritas timers still use the paths and releases listed above. See [OPERATIONS.md](OPERATIONS.md) and [UNIFICATION_DEPLOYMENT_PLAN.md](UNIFICATION_DEPLOYMENT_PLAN.md) before any transition.

The repository inventory contains 26 local branches, 7 remote heads, and 29 worktrees. No old branch or worktree was deleted. Several of them contain active-runtime dependencies, uncommitted source, or unique research data. The complete disposition is in [UNIFICATION_BRANCH_INVENTORY.md](UNIFICATION_BRANCH_INVENTORY.md).
