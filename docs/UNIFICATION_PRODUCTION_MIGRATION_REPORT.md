# MIDAS unified production migration report

**Snapshot:** host measurements 2026-10-30 00:56–01:06 UTC, database stat
01:05 UTC; related systemd-oomd event 2026-10-30 00:58 CET
(2026-10-29 23:58 UTC)
**Outcome:** unified release built and validated in isolation; no production
service migrated. Current host pressure and shared writer dependencies block a
safe application cutover. The protected Reality transition is staged and still
requires separate authorization.

## 1. Authoritative source and release identity

The reported starting identities were verified locally:

- Consolidation commit: e524be501dac4cbcc29b1177987688aad723adaa
- Application baseline: fd3d16dacdfc726915c48dcbc71321396a6b0cfa
- Authoritative checkout and branch: /home/charlie/midas-unification,
  codex/midas-unification
- Validated release source commit: b13477e86477eadeccac22ebd84595a808dcd1f9
- Application version: 0.2.0
- Preserved original main checkout: commit 55601b9 with its pre-existing 69
  dirty status entries; no reset, stage, or edit was made there.

The release commit is a descendant of the consolidation commit. Seven
post-consolidation commits complete the operational contract, optional CPU
Arena dependency group, API typing/readiness test fixtures, Frontier seeded
fixtures, and evidence-aware Veritas browser expectations. The authoritative
checkout was clean before this report was written. The separate
/home/charlie/midas checkout remains on protected main at 55601b9 with its
existing dirty work; this mission did not modify or stage it.

The seven release-source commits after consolidation are:

- 294d5f623b8ea2edba2ca2cf8cbeb1a1b1b998d9 — versioned release runtime
  contract and service templates.
- f70181db640095bf16852d03a2b04e1f9bb56a60 — locked optional CPU Arena
  dependencies.
- 127d677b3482d74957d56f377efc912d08a634ee — API deployment-schema typing.
- fbd355e0d48fafa181fc4d9bfd702cfcf7742d81 — API readiness test fixture.
- 90a4b1a80c9a3f74c55ec640b07c79b58b759548 — Frontier seeded history URLs.
- 478b16a7e4c0fd10872d8a0e2d5f38205796b690 — Frontier seeded source schema.
- b13477e86477eadeccac22ebd84595a808dcd1f9 — evidence-aware Veritas
  end-to-end labels; validated release source.

The reproducible source archive is
/tmp/midas-unification-b13477e86477eadeccac22ebd84595a808dcd1f9.tar.gz,
SHA256 7634e27236f848e3a16e68a1956ff23bf10d5b998b1e2ae4e56195823427f71d.
The extracted release is
/home/charlie/.local/share/midas/releases/b13477e86477eadeccac22ebd84595a808dcd1f9.
Its separate Python environment is
/home/charlie/.local/share/midas/venvs/b13477e86477eadeccac22ebd84595a808dcd1f9.

The machine-readable release manifest is in the release directory. Its SHA256
is 0569450c05e72238295b026ec2f369ae1eaba586366e2ee897220df76b6759b7.
The manifest records source, lockfiles, frontend output, environment, tests,
route smoke, configuration identities, and the explicit fact that production
activation did not occur. The deployment timestamp remains unset because this
release has not been activated.

## 2. Initial live environment

All installed MIDAS units are user services under
/home/charlie/.config/systemd/user. Their unit files, runtime drop-ins,
environment sources, and timers remain in place. The user manager also has
runtime user.control overrides, so repository templates alone do not describe
the effective live resource policy.

| Live unit or process | Identity and binding | State and dependency |
|---|---|---|
| midas-api.service | PID 1218662; API release a1529991a880965a8ad37a7528e2c4cabfc341d8 at /home/charlie/.local/share/midas-api/releases/a152999; working directory /home/charlie/midas; 127.0.0.1:8000 | Demo mode; active shared MIDAS SQLite database, Arena, paper, Laboratory and integrated research APIs; 9 restarts. |
| midas-web.service | PID 1095134; release 767f330 under /home/charlie/.local/share/midas-api/releases/767f330/apps/web; 127.0.0.1:5173 | Vite dashboard, ordered after the API; no effective memory cap; 0 restarts. Its release differs from the API. |
| midas-arena-scheduler.timer/service | Every minute; script from /home/charlie/midas; root /home/charlie/midas/data/arena | Active scheduled dispatcher against the same durable MIDAS data owner; one-shots use Restart=no and a 512 MiB maximum. |
| midas-reality.service | PID 1235804; source /home/charlie/midas-reality, branch commit d8629e4; config /home/charlie/midas-reality/deploy/reality.json | Protected public-observation recorder; 14 restarts; writes /home/charlie/midas-reality/data/recordings/reality. |
| midas-reality-api.service | PID 610950; release /home/charlie/.local/share/midas-capacity/interface-capacity-v3-20261021; 127.0.0.1:8010 | Separate Reality interface API and preview database; not the unified API. |
| midas-reality-web.service | PID 2890819; /home/charlie/midas-reality/apps/web; 127.0.0.1:5180 | Separate Reality interface; depends on its Reality API. |
| Terminal-owned Vite | PID 3930859; dirty /home/charlie/midas/apps/web; 0.0.0.0:5174 | Development process, not systemd and not the 5173 dashboard; left untouched. |
| Veritas timers | Observatory release e988cbb0af86fe89e07da9af8036598b65068deb; Director and source analysis use /home/charlie/midas-veritas with the existing MIDAS Python environment | Three enabled timers; separate Veritas data owner at /home/charlie/midas-veritas/data. No dedicated always-on Veritas daemon. |
| Reality timers | Capacity every 30 minutes; research and shadow-integrity daily | Enabled one-shots use the Reality workspace; not changed. |

The Reality recorder is explicitly protected. The shared API and Arena timer,
the separate Reality interface state, and Veritas scheduled research are
stateful operational dependencies and were also left unchanged. Other active
user applications included Aegis, Continental Cloud tailnet, Continental ID
auth, Cordyceps, RoadReach and Vanguard AI. They remain outside this migration;
no unrelated service was stopped or reconfigured. The recent OOMD event
targeted only the isolated frontend-test scope.

The API unit starts uvicorn from /home/charlie/midas/.venv and uses
--app-dir /home/charlie/.local/share/midas-api/releases/a152999 while its
working directory remains /home/charlie/midas. Do not infer that the entire
running application is represented by the dirty main checkout's Git head.
Loaded drop-ins at the snapshot were:

- API: 90-midas-immutable-release.conf,
  95-research-readiness-cf452ec.conf, recording-budget.conf, and
  zz-readiness-memory-composition.conf.
- Web: 95-research-readiness-cf452ec.conf,
  99-research-readiness-4f4179c.conf, 99-research-readiness-90c625d.conf,
  and zz-readiness-memory-composition.conf.
- Reality recorder: runtime user.control MemoryHigh, MemoryMax and
  MemorySwapMax overrides.
- Reality API: capacity release, recording budget, two quality drop-ins,
  Frontier memory bound, and runtime MemoryHigh/MemoryMax overrides.
- Reality web: no loaded drop-ins.

The long-running units use Restart=on-failure; timer-triggered workers use
Restart=no. The API requires the user manager's basic/app slices and network;
the web is ordered after the API; Reality recorder is after network-online;
Reality web is after its API. Reality and Veritas one-shots are ordered after
their timers. The active API unit directly sets demo mode, Laboratory and
Reality/Veritas roots, and unbuffered Python output; the dashboard targets the
API at 127.0.0.1:8000.

| Unit | Memory current / peak | MemoryHigh / MemoryMax / swap max | Cumulative cgroup events |
|---|---:|---|---|
| midas-api.service | 339 MiB / 1,536 MiB | 1,536 MiB / 1,792 MiB / 0 | high 11,692; max/OOM 0 |
| midas-web.service | 90 MiB / 472 MiB | unlimited / unlimited / unlimited | no high/max/OOM |
| midas-reality.service | 695 MiB / 1,152 MiB | 1,152 MiB / 1,280 MiB / 0 | high 33,176; max/OOM 0 |
| midas-reality-api.service | 123 MiB / 522 MiB | 576 MiB / 640 MiB / 0 | max 5,199; high/OOM 0 |
| midas-reality-web.service | 25 MiB / 128 MiB | unlimited / 512 MiB / unlimited | no high/max/OOM |

The API health endpoint reported application version 0.2.0, old release
identity a152999, demo mode, live_execution=false, paper recovery
CHECKPOINT_VERIFIED at journal revision 857708 with 857709 events, and
Laboratory READY with no recovery errors. This is a read-only observation of the
old service, not validation of its persistent stores by the new release.

The API and Arena scheduler share the original main checkout and durable
research roots. The API starts paper and Laboratory recovery; the scheduler
admits Arena work against its shared root. The new frontend expects routes that
the old API does not expose. These are coordinated owners, not independent
release switches. Frontier, Observatory, Veritas, Research Director and
Readiness are not separate always-on services in this deployment; much of the
consolidated UI is currently absent from the active API release.

## 3. Host resource gate

At 2026-10-30 00:56:45 UTC the host had 15 GiB RAM, 9.9 GiB MemAvailable,
5.6 GiB used, and the 4 GiB swap file was 99.99% occupied. At 01:06:33 UTC
only about 1 MiB of swap remained free. CommitLimit was 11.76 GiB while
Committed_AS was 21.9 GiB (about 1.86 times the limit). Committed_AS is virtual
memory commitment accounting, not resident use or proof of immediate
exhaustion, but it shows that reservations exceed the host's commit limit.
A one-second vmstat interval showed 0 KiB/s swap-in, swap-out and block I/O;
this does not demonstrate ongoing swap thrashing or sustained disk idleness.
Swap was not cleared.

At the subsequent cgroup sample, the user slice used about 9.9 GiB. Its
cumulative memory.events counters included 19 OOM events and 15 OOM kills.
The API cgroup used about 339 MiB, peaked at 1.50 GiB, and had 11,692 high
events but zero max/OOM events. Reality used about 691 MiB, peaked at 1.13 GiB,
and had 33,176 high events but zero max/OOM events. API limits are
MemoryHigh=1536 MiB, MemoryMax=1792 MiB, MemorySwapMax=0; Reality limits are
MemoryHigh=1152 MiB, MemoryMax=1280 MiB, MemorySwapMax=0.

The latest sampled memory PSI was 0.0%. CPU PSI some was 2.40% avg10 and 9.67%
avg300, with no CPU full stall. I/O PSI some was 0.91% avg10 and 1.23% avg300;
I/O full was 0.79% avg10 and 1.09% avg300. The root filesystem had 134 GiB
available of 468 GiB, 70% used. These figures show free RAM and disk at the
instant, alongside sustained CPU/I/O delay and historical reclaim events.

At 2026-10-30 00:58 local time, systemd-oomd killed nine processes in the
transient scope run-u139765.scope, named “MIDAS unified release frontend unit
tests,” after user-slice memory pressure exceeded 58.40% for more than 20
seconds with reclaim activity. This was a mission test scope, not a production
service. A later serial frontend test run passed. The service cgroups showed no
new max/OOM events in the snapshot. Earlier OOMD events on Oct 28 had killed
the API and protected Reality recorder before automatic recovery; the current
restart counts are 9 and 14 respectively. No new kernel OOM line appeared in
the bounded Oct 29–30 kernel-log query.

Conclusion: the machine supported capped, isolated verification, but is not
qualified for additional production-equivalent parallel services. Recent OOMD
reclaim action, full swap, cumulative user-slice OOM history, and I/O pressure
make an overlapping rollout unsafe. There is no measured sustained stability
window. Do not infer that the large MemAvailable reading removes these risks.

## 4. Release and dependency reproducibility

The Python release uses Python 3.12.3, uv 0.13.6, locked groups dev and
arena-rl, and CPU Torch 2.8.0+cpu. The pinned uv executable is
/home/charlie/.local/share/midas/toolchains/uv-0.13.6/bin/uv. A controlled
toolchain was installed outside the active application environments. The final
uv sync --locked check resolved 78 records and checked 77 installed packages.
An earlier construction pass used uv 0.13.0; the final locked resync passed
with uv 0.13.6. CUDA was unavailable and not required.
The pinned uv executable SHA256 is
23803452c0fbe125033054cd9ff245f1d649fb65b4b73f68429f4abda432436d.

The backend lockfile SHA256 is
15f2e950cf679d203f130ac553918f8f75af5d121bdc66bcb3c8c98161888bb6.
The frontend uses Node v22.23.4 and Corepack pnpm 10.18.0. The repository-root
pnpm-lock.yaml SHA256 is
dc968fcb0457b4337a92e26095834e075200dd2115e5380d9479d0072c0d8c4c.
pnpm install --frozen-lockfile passed. Its existing esbuild postinstall script
was skipped by pnpm's build-script policy; the build and tests still passed.

The frontend build and TypeScript project build passed. The dist tree hash is
23d20d9a93a7f84e914f0ade86410e6495d9f145309316063ecaa5097d151935.
Vite warned that the Chart chunk is 544.51 kB; this was non-fatal. Ruff check
passed for packages/midas, apps/api, scripts and tests; 528 files passed Ruff
format checking. Mypy passed for 193 source files.

## 5. Integration and regression verification

| Check | Result |
|---|---|
| Isolated API | Demo startup READY, fresh SQLite and runtime roots, schema 003, 136 OpenAPI paths, candidate source/release identity reported. |
| Read-only API route smoke | 18 selected GET routes returned HTTP 200, including core, paper, analytics, Arena, Laboratory, Frontier, Reality, readiness and Observatory paths. No public source probes were enabled. |
| Frontend/API preview | Frontend root, built asset and API proxy returned HTTP 200. Candidate preview and API ports 18081 and 18080 are now closed. |
| Backend focused integration | 128 passed; one upstream Starlette TestClient deprecation warning. |
| Full backend suite | 2,130 collected; not completed. The previous broad run stopped after 119 passed in 319.91 seconds while in synthetic JSON serialization. The isolated bounded Arena director case passed separately in 172.61 seconds total. No full-suite pass is claimed. |
| Frontend unit tests | 78 passed in 15 files in the final serial run. An earlier systemd-oomd-killed attempt is recorded in section 3. |
| Browser checks | 19 passed, 5 skipped; a separately seeded Frontier Replay-to-Laboratory journey passed 2/2. Three skips require captured evidence and two are the separately seeded cases. |
| Frontend lint and typecheck | Passed. |

The browser suite covered the Mission Control overview; a scanner observation
and synthetic simulation; persistent paper state; Laboratory configure/run/
compare/replay flows; saved Arena evidence; Reality exploration/replay;
Veritas evidence labels; Observatory views; Frontier captured and seeded
replay; and Research Readiness. It also navigated to Analytics, Incidents,
Telemetry and Settings. Those last areas received shell/navigation checks, not
a full production-data workflow. The seeded Frontier journey covered Replay
into Laboratory. The smoke used fresh candidate databases and temporary
mutable roots. The live API was queried only with GET for the existing Reality
and Veritas projections. Tests did not start collection, workers, campaigns or
orders.

The slow bounded Arena director/evolution case
tests/arena/test_evolution.py::test_bounded_director_runs_real_selection_and_two_matched_challenges
passed individually in an isolated capped scope in 172.61 seconds. The broad
run had no assertion failure before it was stopped in synthetic serialization.
This confirms an expensive case can pass, but no before/after performance
baseline was available to rule out a regression.

This is bounded integration evidence, not an exhaustive backend regression or
production endurance result. The production-equivalent database was not opened
by the candidate.

## 6. Scientific and operational controls

The candidate stayed in demo/research-only mode with live execution false.
The four staged Frontier probe switches for Polymarket, Kalshi, Kraken and
Coinbase are false. There is no Gemini activation in the staged environment.
No public source probe, authenticated exchange path, wallet, live order or
campaign was activated. Paper trading remains virtual.

Reality continues to report market observations separately from sequencing,
freshness and execution truth. The read-only Reality API snapshot changed
between stale and active_receiving over the observation window; the latest
snapshot had 16 fresh books, sequence_verified=false, 25,395 lifetime gap
records, and a retained stale-observation timeout diagnostic. Collection
receiving does not establish complete or sequenced source data.

The read-only Veritas overview reported insufficient_independent_evidence.
Its finalized Reality projection covered 40,967 of 40,967 catalog segments,
with no pending bytes and readiness awaiting_finalized_campaign_window_end.
The independent audit covered 712 snapshots, with zero positive gross pairs
and zero candidate events. These results remain research evidence only; they
do not establish profitability or order execution.

## 7. Persistent state and compatibility

The installed API's database is /home/charlie/midas/data/midas.db. A
read-only stat at 2026-10-30 01:05:25 UTC measured 12,008,026,112 bytes
(12.008 GB), with a 4,482,592-byte active WAL and a 32,768-byte SHM file. The
API had reported schema 003 in the earlier health snapshot. Its paper journal
and Laboratory state are live. The Arena timer shares
/home/charlie/midas/data/arena. The Reality recorder writes under
/home/charlie/midas-reality/data; Veritas catalogs and jobs remain under
/home/charlie/midas-veritas/data; Frontier data stays in its separate existing
store. No research database, WAL, recording, campaign, model, artifact or
historical evidence was copied, rewritten, migrated or deleted.

The old API exposes 76 OpenAPI paths; the candidate exposes 136. Both report
schema 003 in their respective health checks, but that matching revision alone
does not prove behavioral or data compatibility. The candidate was not pointed
at the active database. No production backup/restore rehearsal, writer
exclusion proof, or full database compatibility check was completed. API and
Arena scheduler therefore cannot be split across releases yet. The required
data roots are explicit in the staged config; no directory relocation is
needed for the first release.

## 8. Staged configuration and systemd architecture

The versioned release separates code, Python environment, configuration, and
persistent state:

- Code and built frontend:
  /home/charlie/.local/share/midas/releases/b13477e86477eadeccac22ebd84595a808dcd1f9
- Python environment:
  /home/charlie/.local/share/midas/venvs/b13477e86477eadeccac22ebd84595a808dcd1f9
- API environment:
  /home/charlie/.config/midas/releases/b13477e86477eadeccac22ebd84595a808dcd1f9.env
- API effective settings identity:
  sha256:6af74b70eb746662d5b7a58ca9494dce81e17f14678ef847a90c7daf557f4dea
- Staged Reality JSON:
  /home/charlie/.config/midas/reality/releases/b13477e86477eadeccac22ebd84595a808dcd1f9.json
- Staged Reality JSON identity:
  sha256:a863f96c58e73bcf10ccf3848c04eb1b0738ef0450b8095b7d9a5afbb55551a8
- Staged Reality environment identity:
  sha256:61bff26e354691f7232d2415091859a89136f8180e676cd4512bb8aa3231c5f2

The staged Reality JSON preserves the existing recorder settings and adds an
explicit allowed_storage_root for the existing recordings owner. Config.load
accepted it read-only. Its environment file is mode 0600. The active Reality
JSON remains unchanged at SHA256
9d1aeeb5a496ad6971dc461ce87f327266ff25240391897f7bb6091a8307119a.
The staged API environment, Reality JSON and Reality environment are all mode
0600.

API, web and Reality service templates are in
deploy/systemd/user/midas-api-release@.service,
deploy/systemd/user/midas-web-release@.service and
deploy/systemd/user/midas-reality-release@.service. Instantiated copies under
/tmp/midas-unification-staged-units-b13477e passed systemd-analyze --user
verify. No unit was installed, enabled, daemon-reloaded or activated. The
template SHA256 values are d5f67a65547c2f51a819c193aca0c7e3780f9c5292a4fc6444f3ce1fd3abd5de
(API), fba3f19df0e76ad73d5a4844f979e747333c16e3931f587f255d6cada16457b9
(web), and 2aca38048900330a09e74b84574aa5aa706e83f20d096da6776f8093949b62b1
(Reality). Runtime hardening makes release code read-only to the services;
the API writes only its state directory and configured MIDAS data roots, the
web only reads its versioned release, and Reality writes only the existing
recordings root. The
templates bound resource limits; the API, web and Reality services use
MemoryMax values of 1792 MiB, 512 MiB and 1280 MiB respectively, with swap
disabled. The web unit adds a 384 MiB MemoryHigh. The Reality candidate keeps
the recorder's current 25% CPU quota and existing data write boundary.

Candidate API logs and temporary test outputs remain under
/tmp/midas-unification-api-smoke-b13477e-gjbk8ziz and the recorded
/tmp/midas-browser-* roots. The smoke services were stopped and ports 18080
and 18081 were confirmed closed. No service points into these temporary roots.

## 9. Service migration outcomes

| Service or integrated area | Outcome | Reason |
|---|---|---|
| Unified release package | RELEASE READY, AUTHORIZATION PENDING | Built from exact commit and locked dependencies; isolated routes, frontend and systemd templates validated. It is not deployed. |
| API: Core, Prometheus/scanner, paper, Laboratory, Arena, Frontier, Veritas, Observatory, Research Director and Readiness | BLOCKED BY COMPATIBILITY; BLOCKED BY RESOURCE CONDITIONS | Old API is live on port 8000 with the 12.008 GB active database and shared writers; route contracts differ, and host admission is not clear. |
| Mission Control web | NOT MIGRATED | The web service binds the current API contract; switching it alone is a user-facing incompatible cutover. |
| Arena scheduler | NOT MIGRATED | Minute timer and shared Arena writer remain on /home/charlie/midas and its durable root. |
| Protected Reality recorder | RELEASE READY, AUTHORIZATION PENDING; BLOCKED BY RESOURCE CONDITIONS | Candidate config, release and unit are staged. Current host gate is not clear, source status is unsequenced, and recording-root integrity/rollback preflight remains required. The exact transition also requires owner approval. |
| Reality interface API and web | NOT MIGRATED | Separate preview database and service contract; they are not interchangeable with the unified API. |
| Veritas Observatory, Research Director and source-analysis timers | NOT MIGRATED | Existing scheduled jobs use separate releases/worktrees and Veritas-owned state; their writer/read contracts were not migrated. |
| Dedicated Frontier worker | NOT MIGRATED | None is installed; Frontier is currently served as an API module. No worker was started. |

No service met every gate for a low-risk, independent production migration.
There were no production cutovers, post-cutover health checks, or rollbacks.

## 10. Protected Reality transition handoff

No protected process was stopped, signalled, restarted or reconfigured. The
active PID 1235804, source commit d8629e4, active config hash, recorder root and
cgroup were observed read-only. The candidate does not rewrite or copy Reality
data. Its current source stream can move between stale and receiving states;
sequence verification remains false.

A clean stop can consume up to the current 45-second TimeoutStopSec. Allow
roughly 1–2 minutes for a normal stop/start and source reconnect, and reserve a
five-minute maintenance window. Candidate connection time was not measured
against production and no hard recovery bound is established. A nonzero
recording discontinuity is expected; a longer gap is possible if source
reconnection is delayed. This is an estimate, not a continuity guarantee.

After the owner separately approves this exact recorder cutover, and only after
a fresh resource admission and recording-root integrity/rollback preflight,
the procedure is:

    install -m 0644 /home/charlie/.local/share/midas/releases/b13477e86477eadeccac22ebd84595a808dcd1f9/deploy/systemd/user/midas-reality-release@.service /home/charlie/.config/systemd/user/midas-reality-release@.service
    systemctl --user daemon-reload
    systemctl --user disable --now midas-reality.service
    systemctl --user enable --now midas-reality-release@b13477e86477eadeccac22ebd84595a808dcd1f9.service
    systemctl --user status midas-reality-release@b13477e86477eadecc22ebd84595a808dcd1f9.service

Then check the new service PID and release/config identities, recorder status,
fresh books, queue and persistence health, data path, restart count, logs and
cgroup events. Stop on any failure or duplicate writer.

Rollback keeps the same data path. If the new recorder fails its health gate:

    systemctl --user disable --now midas-reality-release@b13477e86477eadeccac22ebd84595a808dcd1f9.service
    systemctl --user enable --now midas-reality.service
    systemctl --user status midas-reality.service

The old unit/config and code remain intact. The rollback also creates a
recording interruption. Authorization for this procedure does not authorize
the separate API/database, web, Arena, Veritas, collector, or research-worker
cutovers.
The rollback command was prepared against the unchanged installed unit but was
not executed or rehearsed; doing so would require stopping and restarting the
protected recorder.

## 11. Incidents and recovery

The only OOMD action during this mission was the isolated frontend-test scope
described in section 3; a later serial run passed. No production service
required rollback. Existing API and Reality restart histories include
pre-mission OOMD kills and are not presented as newly caused by the candidate.

An automatic approval review rejected an attempted recursive removal of the
unused .venv under interim release
/home/charlie/.local/share/midas/releases/294d5f623b8ea2edba2ca2cf8cbeb1a1b1b998d9.
No files were removed. That unactivated environment remains present; it is
retained for later review rather than bypassing the rejection.

## 12. Final readiness and remaining work

The unified release works in an isolated environment. It is not the production
MIDAS system: no live unit runs commit b13477e86477eadeccac22ebd84595a808dcd1f9.
The host had RAM and disk available during the sample, but full swap, measured
CPU/I/O pressure, cumulative OOM history and the recent oomd-killed test mean
it is not yet demonstrated stable for a consolidated production deployment.

Before a future API/web/Arena cutover, remeasure sustained host and service
headroom, establish database backup and restore, validate candidate access to
a consistent copy, resolve the API/web route switch, and prove one writer per
store. Before Reality cutover, complete a current recording-root integrity and
rollback check, remeasure recorder-specific headroom, and obtain explicit
owner authorization for the expected discontinuity. Veritas timers and the
separate Reality interface require their own identity and data-contract review.

Historical branch/worktree cleanup is NOT READY. The original API and Arena
timer still use /home/charlie/midas; Reality and Veritas runtimes still depend
on their respective worktrees. All 29 inventoried worktrees, branches,
recovery references, research stores and historical workspaces remain
preserved. No cleanup command was run.

No service unit, timer, production database, active recorder config, data root,
branch, worktree, or unrelated service was changed by this mission.
