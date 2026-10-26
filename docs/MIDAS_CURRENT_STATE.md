# MIDAS current state

**Base snapshot:** 2026-10-17 (local operational state). The dated 2026-10-26 addendum below is the latest checked runtime snapshot and supersedes earlier live-service statements where they differ. Mission reports, checkpoints, ledgers, and experiment artifacts remain historical records and should be read with their own version and capture time.

**Latest full-system recheck:** At 2026-10-26 02:33:58 CET, the API returned HTTP 200 `READY` in demo mode with `live_execution=false`, Laboratory `READY`, and paper recovery `CHECKPOINT_VERIFIED` at 666,807 events. Reality remained active on PID `3007040` with cgroup use 1,122,304,000 bytes against `MemoryHigh=1,207,959,552` (85,655,552 bytes below); cumulative `high` events were 14,379 and `max`/OOM/kill counters were zero. The active Veritas v4 observer failed at 02:31:07 CET on its 2,097,481-byte summary, and `/api/veritas/overview` returned HTTP 503. The staged 112 GiB / 120-day storage commitments exceed current NVMe free space by 6.51 GB. This is a time-specific read-only sample; no production service was changed.

## Project status

Prometheus, Reality, and Veritas engineering is consolidated into `main`. Prometheus provides the simulation, Laboratory, Arena, provenance, and bounded research foundations. Reality provides public read-only market recording, replay, and forward shadow campaigns. Veritas provides versioned market observation, independent audits, economic sensitivities, source replay, Arena qualification, and the dashboard/API.

MIDAS has no real-order, wallet, deposit, or trading-credential path. Public observations, shadow campaigns, and Arena/Laboratory simulations do not establish real fills or profitability.

## Repository and worktrees

| Path | Branch | Purpose and dependency |
|---|---|---|
| `/home/charlie/midas` | `main` | Authoritative development checkout. Main API, dashboard, and Arena scheduler run from here. |
| `/home/charlie/midas-reality` | `project/reality` | Retained runtime checkout for the public recorder, frozen Reality campaign, successor campaign, and Reality interface. Systemd units use this path; its `data/` and `.venv/` stay local. |
| `/home/charlie/midas-veritas` | `project/veritas` | Retained data and runtime workspace for Veritas observation, source replay, gap-detail replay, Research Director, and Veritas API artifacts. Timers use this path; its ignored data remains local. |

Both feature branch histories are represented in `main`. The Reality and Veritas worktrees remain because active services and preserved runtime data depend on their paths. Do not remove either worktree until those services and their data have a separately verified migration plan. Temporary consolidation worktrees are not part of the operating layout.

Recovery refs created during consolidation:

- `recovery/preconsolidation-main-20261017`
- `recovery/preconsolidation-reality-20261017`
- `recovery/preconsolidation-veritas-20261017`
- `recovery/veritas-uncommitted-20261017` (preserved interrupted Veritas changes)

Project Atlas and Frontier are not implemented and are deferred.

## Architecture and source layout

MIDAS is a Python modular monolith with a separate React dashboard:

- `packages/midas/core`, `market_data`, `simulation`, `risk`, and `paper` contain the domain, read-only adapters, deterministic exchange, and virtual accounting.
- `packages/midas/laboratory` and `packages/midas/arena` contain durable simulated experiments and bounded research jobs.
- `packages/midas/reality` contains public recording, finalized-segment replay, and shadow-campaign code.
- `packages/midas/veritas` contains observation, source replay, measurement, audit, and economic analysis.
- `apps/api` registers the FastAPI routes and configures persistence and storage paths.
- `apps/web` contains the React command center, including Arena, Reality, and Veritas pages.
- `docs/` contains current operations guidance plus preserved historical research, checkpoint, provenance, and verification records.

The Veritas API uses source code from `main` and reads its versioned documents and runtime artifacts from `MIDAS_VERITAS_WORKSPACE` (currently `/home/charlie/midas-veritas`). This keeps the 122 MB observatory and 133 MB Arena runtime stores in place. The main Arena store remains `/home/charlie/midas/data/arena` unless `MIDAS_ARENA_ROOT` is changed.

The deployed `midas-api.service` now sets `MIDAS_VERITAS_WORKSPACE=%h/midas-veritas`; its existing recording-budget drop-in is preserved. After this deployment, `/api/health` reported `READY`, Laboratory `READY`, paper journal recovery `CHECKPOINT_VERIFIED` across 236,471 events, and `live_execution=false`. Veritas overview and artifact endpoints returned HTTP 200. API startup verified the durable paper journal for about 74 seconds; the service cgroup peaked at 8.54 GiB. At 00:53 local, cgroup use was 3.23 GiB, including 1.61 GiB `inactive_file` cache, while process RSS was 1.61 GiB. The host reported 8.0 GiB available RAM and 3.6 GiB swap in use. Allow for that startup cost when planning any future API restart.

## Services and dashboard access

The active local dashboard and API use loopback addresses:

- Main command center: <http://127.0.0.1:5173>
- Main API health: <http://127.0.0.1:8000/api/health>
- Veritas overview: <http://127.0.0.1:8000/api/veritas/overview>
- Reality API: <http://127.0.0.1:8010/api/health>
- Reality interface: <http://127.0.0.1:5180>

The main API and web development server use `/home/charlie/midas`. Reality recorder, shadow workers, API, and web services use `/home/charlie/midas-reality`. Veritas timer units use `/home/charlie/midas-veritas`; Veritas observation, source replay, gap-detail replay, and Research Director services are one-shot jobs and are normally inactive between timer runs. `midas-arena-scheduler.timer` also runs bounded dispatch checks; its service is normally inactive after each check.

The managed main dashboard is on `127.0.0.1:5173`; a separate shell-owned Vite development server also remains on `0.0.0.0:5174` in an active GNOME Terminal session. The latter has no systemd dependency and was left running with its terminal intact.

The Reality interface API on `127.0.0.1:8010` is the isolated demo preview. It returns HTTP 200 and `startup_status=READY`, but its health status is `DEGRADED`: the synthetic demo recorder exhausted its default 100,000,000-byte budget under `data/research/reality/interface/recordings`, and the service logs repeated recording-budget errors. This preview database/recording path is separate from the public collector's `data/recordings`; the collector and campaigns are unaffected. The preview API was left running without resetting its data or raising the cap. A rotation or disabled-demo-recording policy needs a separate operational decision if this preview remains in use.

At 00:53 local, the Reality recorder was running at about 704 MiB against `MemoryHigh=704 MiB` and `MemoryMax=768 MiB`; its recorded cgroup peak was about 704.3 MiB. It is near the high threshold but below the hard cap. Do not raise the limit to hide growth. The frozen Reality worker is still running but is severely behind source input; its campaign is preserved and unchanged. The successor worker is active on its own versioned campaign. Both report zero actual orders.

The frozen worker's last status showed `WARMING_OR_LAGGED_SOURCE`, 10,253 decisions, and 215,099 lagged frames skipped. Its last decision was at 2026-10-15 08:58 UTC while the status was updated at 2026-10-16 22:40 UTC. The successor status was `FORWARD_EVALUATING_EXPERIMENTAL`, with its last decision and source receipt near 2026-10-16 22:40 UTC. Do not restart, reset, reconfigure, or rewrite either campaign as part of routine deployment.

The latest gap-detail run completed at 00:51 local time with 7,383 segments processed, `status=current`, and zero pending segments. An earlier run processed 7,354 replayable finalized segments from a 7,356-segment catalog; the remaining two were recorded as empty finalized segments. Source analysis completed at 00:42 local time with 7,364 segments processed, `status=current`, and no pending source bytes. The latest public observation scan completed at 00:30 local time. The scheduled Research Director run completed at 00:45:50 local time; its next timer is scheduled for 01:15.

Historical failed one-shot Arena jobs, test suites, capture attempts, and the Reality canary remain visible in systemd's failed-unit list. They are not active processes or recurring timers. Do not clear or rerun them just to make the unit list look clean; consult their saved records and logs first.

## Data and archive locations

Mutable databases, model files, recordings, campaign state, and research runtime outputs are ignored by Git and must remain in place:

- Prometheus and main application state: `/home/charlie/midas/data/` (about 5.3 GB), including Arena and Laboratory stores.
- Reality recordings: `/home/charlie/midas-reality/data/recordings/` (about 3.4 GB); Reality research and campaigns: `/home/charlie/midas-reality/data/research/` (about 1.7 GB).
- Frozen Reality campaign: `/home/charlie/midas-reality/data/research/reality/forward/mission2/`.
- Successor campaign: `/home/charlie/midas-reality/data/research/reality/forward/mission2-successor-20261016/`.
- Veritas finalized-source observations and summaries: `/home/charlie/midas-veritas/data/veritas-observatory/` (about 122 MB); Veritas Arena store: `/home/charlie/midas-veritas/data/arena/` (about 133 MB).
- Recovery snapshots: `/home/charlie/midas-recovery-20261011T2355/` and `/home/charlie/midas-recovery-post-campaign-20261012/` (about 480 MB and 504 MB). Each snapshot manifest listed 47 files; all recorded sizes and SHA-256 values verified.
- Prometheus bundles: `/home/charlie/midas-prometheus-bundles/` (about 555 MB). All 24 `.tar.gz` archives passed a read-only archive listing/integrity check. Related bundle verification records remain in `docs/`.

The frozen Reality campaign configuration SHA-256 is `aa8acb2b46823c1a1e3ac5d01a57dde917746c2c7471098ae2a4598875e322f5`; the successor configuration SHA-256 is `c5eb8b98cbfd657372fc620192c5a0c0bb46f41d760800e680181fa7f3ee95a3`. A read-only integrity check verified both campaign identities, 20 pinned code files, four models, SQLite integrity, and event chains. The frozen journal had 113,419 events and tail SHA-256 `0d4757d1bb9d9145c90ce1ce004943dcb1c733da18617ec2a844444591a279e`; the successor had 23,657 events and tail SHA-256 `59475db679ae4c2ce8e3fe464d76046d1dde337ae07861110662c97d373f9921`. These checks did not write to the campaign directories.

## Research conclusions and evidence limits

- Prometheus demonstrated model and policy behavior in synthetic simulation. It did not establish real-market profitability.
- Reality's frozen forward state remains `insufficient_forward_evidence`; no scientific champion or real fill is established.
- The latest ledger-receipted Veritas independent audit covers 84 saved scans and 3,360 selected observations. It reports zero quality-valid positive gross candidates, zero stored-versus-independent validity/top-edge mismatches, and zero disagreements across 3,768 fee checks. The sample is finite, selected, and correlated; it is not venue-wide or evidence of fills.
- The market-quality experiment predicts the same-snapshot book-quality gate only. It reports zero positive gross candidates in its held-out panel and is explicitly not deployed as an economic strategy.
- `VERITAS_MISSION2_INDEPENDENT_OPPORTUNITY_AUDIT_021.json` contains an 85-scan result but has no matching ledger receipt. It is preserved as unreceipted evidence and is not the artifact returned by the dashboard. The API intentionally serves the newest ledger-receipted audit (scan 84).

No historical observation, campaign journal, or economic result should be rewritten to make versions agree. Synthetic execution sensitivities, public quote observations, and shadow decisions must remain distinct.

## Development and verification

From `/home/charlie/midas`, use Python 3.12+, Node 22+, Corepack, and the lockfiles. See [Development and verification](DEVELOPMENT.md) for full install instructions.

```bash
uv sync --frozen
corepack pnpm install --frozen-lockfile
.venv/bin/uv run uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
corepack pnpm dev
```

The main backend tests are run with `.venv/bin/uv run --frozen pytest -q`; frontend checks use `corepack pnpm lint`, `typecheck`, `test`, and `build`. Browser tests use `corepack pnpm test:e2e`. Tests that admit Arena jobs or start campaigns can write durable state; use a temporary data root for intentional tests and inspect the command before running it.

For focused Veritas regression tests:

```bash
PYTHONPATH=packages .venv/bin/python -m pytest -q tests/test_veritas_*.py
```

## Deferred work and operating limits

The frozen worker's lag and recorder memory growth need a separately versioned operational decision. Preserve the current campaigns, records, and source segments while making that decision. Do not change the frozen campaign configuration or journal. Atlas/Frontier, new market discovery, strategy expansion, training, exploratory experiments, and economic optimization are outside the current maintenance scope.

## Earlier runtime snapshot — 2026-10-26, 02:03 CET

This section records a fresh check; it does not rewrite the 2026-10-17 snapshot above. The complete evidence, limitations and implementation branch are in [the comprehensive engineering mission report](reliability/MIDAS_COMPREHENSIVE_ENGINEERING_MISSION_20261025.md) and [the mission ledger](reliability/MIDAS_COMPREHENSIVE_ENGINEERING_MISSION_LEDGER_20261025.md).

- The isolated mission checkout is `/home/charlie/midas-engineering-mission-20261025`, branch `codex/midas-comprehensive-engineering-mission-20261025`, based on `55601b9a090945cb498806e4878b6ddc33562043`. The authoritative `/home/charlie/midas` checkout still has 41 pre-existing dirty paths; they were preserved. Mission code and the Research Readiness dashboard are not deployed.
- Reality still runs from `/home/charlie/midas-reality`, PID `3007040`, using the 24 GiB / 90-day configuration. The 112 GiB / 120-day policy remains a staged candidate. At the 2026-10-25 23:30:01 UTC [read-only assessment](reliability/evidence/MIDAS_MISSION_20261026_DEPLOYMENT_PREFLIGHT_BLOCKED_V2.json), its cgroup had 1,662,976 bytes below `MemoryHigh`, below the 4 MiB admission floor; hard-limit/OOM counters remained zero. Host pressure was low, but host headroom does not satisfy the service-specific guard. Do not raise limits or restart as a substitute for diagnosis.
- Reality's captured public state was `RECORDING_UNSEQUENCED` with 16/16 fresh books and one open segment outside the finalized catalog. Status and manifest were read separately, so the boundary is not atomic. Gap markers are local observations and do not count lost exchange events. The old `ConnectionClosedOK` remains an untimestamped historical value, not a current incident.
- The archive-mission3 staging tree has 19,833 finalized segments, 58 `.copying` files and 1,138 finalized files absent from its manifest. Its source/provenance identities do not establish a safe writer transition. Archive writer/timer remain disabled; no staging files were changed.
- Veritas still runs from `/home/charlie/midas-veritas` on its older v4 implementation. The active store has 521 snapshots; the v4 summary covers 423 through `scan-20261023T233202Z-dc4f690bd80f.json.gz`. The latest scan wrote `scan-20261026T010053Z-ed1b5cd8b6a2.json.gz`, then the observer failed at 02:00:55 CET while reading the 2,097,481-byte summary; `/api/veritas/overview` returned HTTP 503. The isolated v6 replay covers 519 earlier immutable snapshots through `scan-20261026T000113Z-72ddb4303c0b.json.gz`; the latest two snapshots are not included. V6 remains undeployed and has not rewritten the active store.
- At 00:31:26 CET the active API was in demo mode with `live_execution=false`, paper recovery `CHECKPOINT_VERIFIED` at 662,697 events, and Laboratory `READY`. The Arena scheduler's 00:30:04 CET invocation exited successfully. The user systemd manager reported 91 failed historical one-shot units; none were cleared.
- Latest-boundary recovery remains incomplete: the historical R15 result stopped at 2,304 of 20,148 segments. No cold replay of the current Reality boundary was attempted. No long-duration validation or new campaign was started.
- Keep the Veritas v6 rollout and dashboard deployment pending a deliberate local integration/deployment decision. Keep Reality's protected service transition pending a clean exact-boundary recovery, archive provenance and resource preflight plus explicit operator approval.

## Latest runtime addendum — 2026-10-26, 02:33:58 CET

The complete read-only capture is [MIDAS_MISSION_20261026_LIVE_STATE_RECHECK.json](reliability/evidence/MIDAS_MISSION_20261026_LIVE_STATE_RECHECK.json), SHA-256 `f89c3be4866ac10a488d50cca777fac78036a52e3a52d78e38dbb7c1a3dc86be`. It supersedes the 02:03 CET live-status bullets above while preserving that earlier snapshot as history.

- Main API: HTTP 200 `READY`, demo mode, `live_execution=false`, Laboratory `READY`; paper recovery is `CHECKPOINT_VERIFIED` at 666,807 events. The deployed release is `/home/charlie/.local/share/midas-api/releases/24c7504`; its health response does not expose build identity. The Research Readiness page remains undeployed.
- Reality: service PID `3007040` remains on `/home/charlie/midas-reality` and the old 24 GiB / 90-day config. It is `RECORDING_UNSEQUENCED`; 8 markets and 16/16 fresh books are reported, but API health is degraded by missing recent persistence metrics, recovery state and transport queue depth. Its current response has no collector error. The cgroup sample is 1,122,304,000 / 1,207,959,552 bytes (`MemoryCurrent` / `MemoryHigh`); the historical `high` counter is 14,379 and `max`/OOM/kill are zero. The current raw inventory is 31,669 finalized files / 8,985,876,498 bytes plus one open file, based on names and sizes only.
- Veritas: 522 snapshots are present; the v4 summary still covers 423. The latest scan at 02:31:05 CET was `scan-20261026T013105Z-74db14ad03a0.json.gz`; the observer failed at 02:31:07 and the overview API is HTTP 503. The 519-snapshot v6 replay leaves the latest three snapshots outside its pinned boundary. No active runtime migration occurred.
- Arena: zero active jobs, directors or schedules; zero invalid artifacts; one retained expired-admission alert. No new research job was admitted.
- Storage and archive: NVMe free space is 161,950,273,536 bytes. The staged raw, database, Veritas and reserve commitments require 168,457,185,055 bytes (6,506,911,519 bytes above current free space). The 120-day historical-growth case is short by 12,013,107,129 bytes. The archive tree still has 1,138 unmanifested finalized files and 58 `.copying` files; no contents or provenance were established and no files were changed.
- Latest-boundary recovery remains incomplete. R15 stopped at 2,304/20,148 segments; the later copy was interrupted at 697/31,468 with no pinned source boundary or complete snapshot receipt. Do not use or resume that copy as a snapshot.

Keep Reality deployment, Veritas v6 rollout, archive writing, storage policy changes and dashboard publication pending their separate readiness steps. The protected Reality transition still requires explicit approval after a fresh exact-boundary preflight.

### Isolated Veritas v6 replay — 2026-10-26 02:56 CET

After the 02:33:58 runtime check, an isolated, bounded offline replay pinned
the 522 finalized snapshots present at that time. It processed the boundary
through `scan-20261026T013105Z-74db14ad03a0.json.gz` (324,615,273 source
bytes), indexed 522 snapshots and independently analyzed 522 events, with zero
quarantines and zero catalog integrity issues. A separate `--resume` pass
reverified the copied inputs, SQLite catalogs, event files and bounded summary.
Its source, receipt, verifier, economic and resource identities are in
[`MIDAS_VERITAS_V6_REPLAY_522_20261026.json`](reliability/evidence/MIDAS_VERITAS_V6_REPLAY_522_20261026.json).

The independent reference audited 20,873 of 20,874 selected pair observations
across 3,932 unique markets. It found 3,937 reference snapshot-valid pairs,
14,750 validity disagreements, 14,750 source-quality disagreements, and zero
positive gross, economically supported or net-eligible pairs. These are
correlated selected observations, not independent trials. Active Veritas
remains on v4 and its public API remains HTTP 503 at the last runtime check;
the replay did not change the active service or store. The receipt's process
RSS value conflicts with its scope cgroup peak and is not used for capacity
claims.

### Latest Veritas service check — 2026-10-26 03:02 CET

The scheduled v4 observer started at 03:01:24 CET, wrote a new finalized
snapshot, then failed at 03:01:35 CET on the oversized legacy summary. The
active store now has 523 snapshots; the newest is
`scan-20261026T020133Z-f1469881bdbc.json.gz` (641,953 bytes; SHA-256
`7625c0aa702594d2f6e022f9c7e5ad462c905046681c2ad8ea0d697a526f17a3`). The v4
summary remains 2,097,481 bytes, the API returns HTTP 503, and the v6 replay
boundary remains the previously verified 522 files, leaving this one new file
outside it. Capture:
[`MIDAS_VERITAS_20261026_POST_TIMER_RECHECK.json`](reliability/evidence/MIDAS_VERITAS_20261026_POST_TIMER_RECHECK.json),
SHA-256 `342ff41ca6a32a41340c0fec3ae798a21e1258c353df28efa2564540d2c54913`.
The read-only capture made no additional service or store changes; the scheduled observer wrote the snapshot before the capture.

### Reality admission sample — 2026-10-26 03:05 CET

Read-only admission sample: protected PID `3007040` remains on the old
24 GiB / 90-day config (SHA-256
`9d1aeeb5a496ad6971dc461ce87f327266ff25240391897f7bb6091a8307119a`). The
cgroup held 1,131,302,912 bytes, 76,656,640 bytes below `MemoryHigh` and
210,874,368 below `MemoryMax`; `high=14,379` and max/OOM/kill counters were
zero. Host memory available was 8,000,172,032 bytes; I/O-full PSI was 0.86% over
60 seconds. One admission point sample passed, but no sustained 60-second
window or staging worker was started. Raw and staging filesystems had
161,060,818,944 / 635,101,380,608 bytes free. Carrying forward the prior
capacity requirements, current-commitment and 120-day deficits are
7,396,366,111 and 12,902,561,721 bytes; the historical growth rate was
not re-estimated. This does not verify the current archive boundary or cold
recovery. Evidence:
[`MIDAS_REALITY_ADMISSION_RECHECK_20261026T0204Z.json`](reliability/evidence/MIDAS_REALITY_ADMISSION_RECHECK_20261026T0204Z.json),
SHA-256 `527ca3ac3d08811863f8458b5418d6ba165450d34990289c589379a6d0cd8ea1`.
