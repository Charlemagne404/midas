# MIDAS engineering mission closeout — 2026-10-26

## Executive readout

Veritas V6 is integrated into a dedicated MIDAS branch and its observer is
running from the pinned V6 release. Its latest scheduled update remains
`2026-10-26T04:32:24Z`: the independent Decimal reference audited 1,600
repeated pairs across 741 unique markets and found zero economically supported
or net-eligible observations. These are correlated observations, not 1,600
independent trials. The snapshot catalog is still catching up, and the latest
scan included no stable-control markets.

The Research Readiness view is implemented and deployed through the existing
local Mission Control Vite service. At 04:48:57Z `/api/health` reported API
release `cf452ec`, `READY`, `mode=demo`, and `live_execution=false`; Laboratory
was `READY` and paper recovery was `CHECKPOINT_VERIFIED` at 673,222 events.
The view reads live API projections, labels demo mode prominently, separates
staged and deployed versions, classifies missing evidence conservatively, and
shows storage and cgroup measurements. Browser verification at 1440 px and
390 px completed without page errors or horizontal overflow. The follow-up
fix for unmeasured Veritas fields is now deployed in immutable web release
`90c625d`; its targeted Veritas browser test passed against isolated evidence
fixtures, and post-deploy checks served the `Not measured` state successfully.

Reality production remains on its older collector and active 24 GiB / 90-day
configuration. At the 04:47Z read, the collector was receiving with 16/16
books fresh but remained degraded and unsequenced; its 18,607 local gap
markers are not a count of lost exchange events. Persistence-window,
recovery-state, and transport-queue telemetry were unavailable. Latest-boundary
cold recovery remains incomplete. Archive staging still has invalid
manifest/provenance state.

The 04:55:04Z metadata-only exact-boundary preflight counted 32,065 finalized
raw segment names through ordinal 5,160,978, while source and gap indexes
ended 30 and 15 segment names behind that boundary. It did not read segment
contents or compute content hashes. The archive still has 1,138 finalized
segments outside its manifest and 58 `.copying` files. The clean candidate
rejects unmanifested files, but no archive or production mutation was made.
The protected recorder remained on PID 3007040; the preflight is blocked.

The original Reliability worktree remains dirty and preserved. A clean local
candidate at `d298957afe14d6cbbc47038fbb101a96a63fadca` integrates its bounded
collector telemetry with archive fail-closed handling. Its focused Reality,
dashboard, and operations suite passes 66 tests, and its isolated zero-duration
first-write/recovery receipt matches the candidate source identity. It remains
undeployed.

Readiness is **not established**. At 04:47:40Z, API cgroup use was
1,593,131,008 bytes against `MemoryHigh=1,610,612,736`, leaving about 16.7 MiB;
host available memory was about 8.10 GB. After the web release, the 05:06:26Z
point sample showed 8.72 MiB of API `MemoryHigh` headroom and 7.95 GB available
on the host; heavy-research admission remains blocked. The current measured
storage projection is about 16.7 days at the effective growth rate and 20.2
days on the short-window estimate. Independent correctness, collector,
recovery, resource, and storage gates remain blocked or conditional; economic
evidence sufficiency remains conditional with zero eligible candidates. Arena
has no active or queued jobs; three persisted `RUNNING` director manifests
project to two cancellations and one failure without rewriting them. Its only
open alert is an expired one-minute operational demonstration schedule with
no child job.

No Frontier, Atlas, replacement long-duration campaign, real-money operation,
wallet action, or exchange order was started.

## 1. Starting state and safety boundaries

Repository and service state was checked before deployment. Historical reports
were treated as leads and rechecked against current APIs, service units, and
artifacts.

| Worktree | Branch and HEAD at inspection | State preserved |
| --- | --- | --- |
| `/home/charlie/midas` | `main`, `55601b9a090945cb498806e4878b6ddc33562043` | 41 dirty entries; untouched |
| `/home/charlie/midas-reality` | `project/reality`, `4f5cb5689548987bf30a33f050284ea8cb2f3c28` | clean; active recorder source |
| `/home/charlie/midas-veritas` | `project/veritas`, `3b102928594323e7886859d348f7b2151663debb` | clean |
| `/home/charlie/midas-reality-reliability` | `fix/reality-foundation-20261020`, `4278b5b5e66823e41a5d949b7b7c2e007c5b4ed0` | 26 dirty entries; preserved |
| `/home/charlie/midas-veritas-research-overhaul` | `codex/real-market-research-overhaul`, `3b102928594323e7886859d348f7b2151663debb` | 25 dirty entries; preserved |
| `/home/charlie/midas-reality-archive-provenance` | `codex/reality-archive-provenance-20261026`, `d298957afe14d6cbbc47038fbb101a96a63fadca` | clean; isolated collector candidate |
| `/home/charlie/midas-engineering-mission-20261025` | `codex/midas-comprehensive-engineering-mission-20261025`, `005f6fa50eca9cf4fa332ab59bb335607a78cc84` | six untracked evidence/data entries; preserved |
| `/home/charlie/midas-veritas-v6-integration-20261026` | `codex/veritas-v6-integration-20261026`, final runtime source `4f4179c72eeb6deab59c4fc5959315cf62284c85` | dedicated integration branch |

The main checkout's dirty files, the dirty Reality reliability and Veritas
research-overhaul worktrees, and the existing 522-snapshot replay evidence
were not staged, reset, deleted, or rewritten. The only protected service left
untouched was `midas-reality.service` (PID 3007040, source
`/home/charlie/midas-reality`, production commit `4f5cb568...`). The active
Reality process ID and start time were unchanged after this mission's API and
web deployments.

## 2. Veritas V6 integration and independent economics

The integration branch includes the V6 implementation commits `0082b1e`
(`feat(veritas): integrate v6 independent research path`) and `e988cbb`
(`merge: integrate Veritas v6 with active platform baseline`). The audit
covered the independent reference, observer, versioned SQLite catalogs,
summary publication, scheduling records, and offline replay/recovery tests.
The deployed observer release is pinned at
`/home/charlie/.local/share/midas-veritas/releases/e988cbb0af86fe89e07da9af8036598b65068deb`;
its timer remains active and its one-shot service is inactive between runs by
design.

The V6 reference version is
`veritas-independent-economic-reference-v3` and uses Decimal calculations
separate from the scanner's decisive pair-auditor path. Differential and
adversarial coverage exercises binary/complement identities, protocol and
book validity, crossed books, tick/price bounds, ask depth, quantity and
minimum-order constraints, collateral/notional, fees and rounding, and
complete-position gross/net calculations. Calculation disagreements and
source-lineage flags are persisted as separate categories. Category counts
can overlap and must not be added as unique affected pairs.

At the final API snapshot (`2026-10-26T03:43:03Z` browser evidence):

- V6 analysis version: `veritas-finalized-snapshot-analysis-v6`.
- Persisted snapshots: 526 total; 20 processed; 506 pending; status
  `CATCHING_UP`.
- Independent reference: 800 repeated pair observations across 349 unique
  markets; 714 primary-quality-valid; 167 independently verified; zero
  positive-gross and zero net-eligible observations.
- Economic support: zero supported; all 800 are unsupported for economic
  eligibility under the recorded reference assumptions.
- Disagreement flags: 547 source-quality and 547 validity flags. These are
  category flags, not 1,094 unique pairs.
- Sampling: 5,986 bounded market-frame visits, 6,000 query-candidate record
  visits, 800 selected pair observations. The latest scan selected 40 markets
  from 300 candidate records, including 32 rotating selections and zero
  stable-control markets. Repeated observations are correlated; the cohort is
  not 800 independent trials.
- Latest analysis summary artifact ID `continuous-analysis`, SHA-256
  `d5cd5de76a7d3e379a5acf53899cd009cf1d66cac056a23995393f75e29982be`.

The previously oversized 2,097,481-byte V4 published summary was preserved
under its versioned V4 name. At the first migration checkpoint, the bounded V6
summary was 89,839 bytes, SHA-256
`0cf03b22f5ec6026dbb02cf9da94bfde84e4c70582eb737a1e2a56c2026e730e`. The
scheduled V6 update at `2026-10-26T03:31:11Z` published the current
`/home/charlie/midas-veritas/data/veritas-observatory/research-summary.json`
at 91,075 bytes, SHA-256
`d5cd5de76a7d3e379a5acf53899cd009cf1d66cac056a23995393f75e29982be` (the
`continuous-analysis` artifact hash above). The preserved V4 file's SHA-256 is
`aca960615863ab4a8df3ab673b78e70dcbef56583146275e023e907def7f18c5`. The API
exposes the versioned summary/artifact identity; publication is bounded and
does not truncate at the former 2 MiB reader limit. V6 catalog rebuild, identity/hash
checks, interrupted publication, and corruption-preservation tests passed.
The 522-snapshot offline replay completed from an isolated copy in about 696
seconds, used about 127 CPU seconds, and peaked at about 537 MiB under its 768
MiB cap; it was not repeated. Its receipt and verification hashes are recorded
in the mission evidence tree referenced below.

The next scheduled update at `2026-10-26T04:32:24Z` published a 95,169-byte
summary at the same path with SHA-256
`49bc1c678f237b4d7656481218b5101585e0c57fdc6cc80020ca371002ef0bb1`. A
read-only API artifact fetch returned HTTP 200 with the same artifact hash.
The current post-observer receipt in Section 6 also verifies the matching
source-analysis and gap-detail artifact identities.

The scheduled V6 update at `2026-10-26T04:32:24Z` has processed 40 of 528
snapshots, leaving 488 pending. The versioned Decimal reference audited 1,600
repeated pair observations across 741 unique markets: 1,405 passed the primary
quality filter, 310 passed the independent snapshot-validity check, and zero
were economically supported or net-eligible. All 1,600 were unsupported for
economic eligibility under the recorded assumptions. Source-quality and
validity disagreement categories each contain 1,095 flags; they can overlap
and are not unique-pair totals. The latest scan selected 8 reference-random
markets and 32 rotating-stratified markets, with zero stable-control markets.
The full snapshot identity, role counts, artifact hashes, and funnel are in the
04:38 UTC receipt in Section 6. These repeated observations do not establish
independent trial counts, profitability, executable fills, queue position,
acknowledgements, or realized P&L.

The 04:55:04Z raw-root metadata inventory found 32,065 finalized `.seg`
names through ordinal 5,160,978, one active `.open` file of 422,130 bytes,
and 32,065 matching numeric sidecars with no name mismatch. It did not hash
raw segment contents. Relative to this boundary, the latest source-analysis
index is 30 segment names behind and the gap-detail catalog is 15 names
behind; these are incremental indexes, not full recovery.

The latest API read reports finalized-source analysis at 32,035/32,035
segments, zero pending, last ordinal 5,156,975, artifact SHA-256
`075303799f9f02a556bcf550628d3ff12d58b83a7b8fce7e0d626526538b2d47`. Gap
detail generated at `2026-10-26T04:47:24Z` covers 32,048 replayable segments
of a 32,050-segment catalog, has zero pending work, ends at ordinal 5,158,905,
and has artifact SHA-256
`a6c466494b0818a8c7c8a39100d428e41f86a867cd27848296622ad7ea7cff62`. Two
catalog entries are empty finalized segments. The live Reality API was already
at ordinal 5,159,119 during the same read window. These distinct incremental
indexes do not close the active raw tail or establish a full cold-recovery
proof.

## 3. Reality collector, storage, and recovery

The production recorder is still the older deployed collector at
`/home/charlie/midas-reality`, commit
`4f5cb5689548987bf30a33f050284ea8cb2f3c28`, configured for a 24 GiB budget and
90-day retention. The API reports `RECORDING_UNSEQUENCED`, current error null,
and a historical `ConnectionClosedOK ... server shutting down` last error
without a source timestamp. Public-feed sequence continuity is not verified;
no local gap count is described as an exact number of lost exchange events.
The current API still reports missing persistence-window, recovery-state, and
transport-queue-depth telemetry.

At 04:35:56Z the recorder API reported `degraded` and
`incomplete_observability`, with all 16 expected books fresh but
`recent_persistence_window_incomplete`, `recovery_state_unreported`, and
`transport_queue_depth_unreported`. It reported 18,594 durable local gap
markers, explicitly not a lost-event count, 213 current-process stable-lineage
divergences, and 1852 source-time regressions after gaps. The current error was
null; the last `ConnectionClosedOK` error remains historical and has no
source timestamp. Raw fields and interpretations are preserved in Section 6.

The later 04:47Z API read still reported `degraded` and
`incomplete_observability`, while the collector was `RECORDING_UNSEQUENCED`
and `active_receiving`. It had 16/16 fresh books, ordinal 5,159,119, 4,063,802
frames, and 18,607 durable local gap markers. `sequence_verified` remains
false. The current error was null; the old `ConnectionClosedOK` last error
still had no source timestamp. Persistence samples, recovery state, and
transport queue depth remained unreported. The incrementing local gap count
does not quantify lost upstream events.

The preserved source candidate in `/home/charlie/midas-reality-reliability`
remains dirty at `4278b5b5e66823e41a5d949b7b7c2e007c5b4ed0`, with its two
tracked operational edits and untracked evidence untouched. Its previously
verified candidate suite passed 63 tests. The committed collector code
provides bounded 60-second persistence/append latency samples with coverage
and completeness, process maximums and backpressure counters, WebSocket queue
depth/high-water samples that remain unknown when transport introspection is
unavailable, recovery checkpoint ordinal/duration/error, and resource-headroom
status. These fields are exposed by candidate read-only APIs and dashboard.

A clean integration candidate is now available at
`/home/charlie/midas-reality-archive-provenance`, branch
`codex/reality-archive-provenance-20261026`, commit
`d298957afe14d6cbbc47038fbb101a96a63fadca` (parent `987481fd6ae611d062155063c19f24b5ea51bb18`, which is based on `4278b5b`). It adds fail-closed
archive validation: unmanifested finalized segments, `.copying` files, invalid
manifests, symlinks, and interrupted manifest publication are preserved and
block publication. A prior published manifest is matched as an ordered
subsequence so new empty finalized segments cannot make a valid incremental
archive look like a different source. The candidate never adopts extra
unmanifested `.seg` files. Its final Reality, dashboard, and operations suite
passed 66 tests; the focused archive operations suite passed 17 tests, and
Ruff passed.

An isolated zero-duration startup at this exact candidate identity wrote the
`process_start` gap durably, finalized three contiguous records through
ordinal 3, made zero guarded network calls, stopped with zero failures, and
replayed its checkpoint to the same state. Source identity is
`3e17719404b0b2fd9edd05fa8b6bbc27ae6c2e4fd5a30849f0a2121319a03e9a`. This is
not a public-feed canary or a current-boundary recovery proof. The clean
candidate is not deployed, and the protected recorder was not changed.

The latest capacity projection, measured around 04:40:49Z and re-read at
04:47Z, uses active 24 GiB / 90-day settings. Effective runway is 16.7 days and
the short-window estimate is 20.2 days. The staged 112 GiB / 120-day settings
remain pending restart and estimate 108.1 days at the configured rate, below
the 120-day retention target. At the 04:47:40Z resource sample the raw
recording filesystem had 159,354,204,160 bytes available. Warnings remain;
the proposed budget has not been activated.

Archive staging at
`/mnt/continental-cloud/data/midas-reality-staging/archive-mission3` remains
`INVALID_MANIFEST` with invalid provenance. The rechecked tree was about 5.39
GB and contained 19,833 segment files against 18,695 manifest entries; 1,138
finalized segment names were outside the manifest (their names exist in the
current raw root), and 58 `.copying` files occupied about 16.5 MB. The
published subset has not had a full content-integrity pass. At the 04:40Z API
capacity projection, the archive remained `INVALID_MANIFEST`; 18,521 of the
18,695 manifest entries had a previous full content verification, which does
not verify the out-of-manifest names. The archive writer is inactive and its
timer disabled. The new candidate guard is tested only on synthetic fixtures;
it did not inspect, adopt, or rewrite the production archive. No ambiguous
file was removed, adopted, or re-published.

Historical full recovery R10 ended at 19,546 segments. R14 covered a verified
prefix plus suffix through 20,110. R15 stopped at 2,304 of 20,148. The newer
copied cold-recovery boundary pinned 31,742 segments / 9,007,651,890 bytes;
its checkpoint covered 2,816 of 31,742 segments and remained incomplete. The
recording root has since advanced beyond that boundary. No full latest-boundary
cold-recovery claim is made. The dashboard keeps finalized-source indexing
separate from cold-recovery verification.

## 4. Readiness API, dashboard, and integration boundaries

Commit `cf452ec618a06897774547addd214c3906b534e2` adds
`GET /api/readiness/resources`, release/source identities in `/api/health`,
bounded procfs, cgroup-v2, pressure, filesystem, systemd last-run, and staged
Reality-worktree projections, plus the dashboard and its tests. Commit
`0753beda1ebaed6332241917aba204b5eb26c744` makes API `MemoryHigh` headroom a
research-admission input. Commit
`4f4179c72eeb6deab59c4fc5959315cf62284c85` labels economic category totals as
overlapping disagreement flags.

The initial 04:39 web release and API packages under
`/home/charlie/.local/share/midas-api/releases/` were created from committed
Git archives and checked against all 1,843 tracked blobs. API release identity
is `cf452ec`; web source revision was `4f4179c...`. User drop-ins were
`midas-api.service.d/95-research-readiness-cf452ec.conf` and
`midas-web.service.d/99-research-readiness-4f4179c.conf`. Existing API demo
mode, paper store, recording-budget environment, cgroup limits, and API port
were retained. Web remains the existing local Vite service bound to
`127.0.0.1:5173`; a separate unrelated Vite service on port 5174 was not
touched. Drop-in removal restores the previous immutable source release; no
Reality unit was edited.

The tested null-safe Veritas rendering was then deployed separately as web
release `90c625d4e168c64fe3c8d1f93e0c1393734fd009` at
`/home/charlie/.local/share/midas-api/releases/90c625d`. It was packaged from
the committed Git archive and all 1,844 tracked blobs matched the source
commit. The pnpm lockfile is unchanged from `4f4179c`; the release uses the
same existing `apps/web/node_modules` symlink. A fresh bounded production
build passed under `MemoryHigh=768M`, `MemoryMax=1G`, `CPUQuota=20%`, and
`TasksMax=64`; the existing 502.91 kB main and 544.41 kB Chart advisories
remain. The new deployment drop-in is
`midas-web.service.d/99-research-readiness-90c625d.conf` (SHA-256
`c5a3c87843c5499f9e8af916f793b57799d90ad78966ebc50a932c3c67116d84`); the
previous `4f4179c` release and drop-in remain intact for rollback. At
`2026-10-26T05:03:22Z` (06:03:22 CET) the web service moved from PID 864756 to
PID 1012462. Its root and transformed
Veritas module both returned HTTP 200, and the served module contained the
null-safe `Not measured` label. API remained `READY` on `cf452ec`, demo mode,
`live_execution=false`; Reality remained active on PID 3007040.

The dashboard covers API, Reality, Veritas, Laboratory, Arena, version
provenance, observation funnel, independent economic categories, data and
recovery integrity, resource/storage sustainability, and six evidence gates.
Missing evidence never passes. It distinguishes live API projections,
persisted/historical analysis, staged Reality source, demo mode, and unmeasured
execution assumptions. A zero-candidate result is shown with its denominator.
Current collector errors are distinct from the older error projection.

The deployed API restart revalidated the 670,756-event paper journal and
reported `CHECKPOINT_VERIFIED`. It took 4 minutes 7 seconds from service start
to application startup completion. At the 03:44Z postflight, cumulative API
cgroup CPU use was 221 seconds (startup-only CPU was not isolated). Cgroup
current memory was 1,594,609,664 bytes against `MemoryHigh=1,610,612,736` and
`MemoryMax=1,879,048,192`; the peak was 1,611,124,736 bytes. Process RSS was
about 177 MiB; `memory.stat` attributed 164 MB to anonymous memory and 1.414
GB decimal (1.32 GiB) to file cache. `memory.events` showed 10,902 `high`
events and zero `max`, OOM, or OOM-kill events. Host available memory was
about 8.1 GB (7.5 GiB). This is a measured startup/reclaim cost, not evidence
of a Python heap leak. The resource gate therefore blocks additional heavy
research while API cgroup headroom remains below the admission threshold.

The postflight cross-component snapshot reported no active or queued Arena
jobs, six terminal Laboratory campaigns, and three stale Arena directors whose
persisted state still said `RUNNING` while owning jobs were cancelled/failed.
The gate remains blocked; their manifests were not rewritten. A fresh
read-only production API check at 04:32:50Z again found zero active/queued
Arena jobs, zero active/unverified directors, and three persisted `RUNNING`
manifests with terminal owner jobs: two `CANCELLED`, one `FAILED` after the
1 GiB artifact budget was exceeded. Each owner linkage matched the manifest's
configuration and source hash; manifest and job-record hashes are preserved
in Section 6. The deployed API already projects these terminal states without
rewriting those persisted records, so no cleanup mutation was justified. The
scheduled bounded Reality source-analysis service completed its 59-segment
batch at ordinal 5,140,697 with zero pending segments for that captured
prefix. This is not the separate 31,742-segment cold-recovery matrix.

A live health/resource sample at 04:33:53Z reported API `READY` on release
`cf452ec`, `CHECKPOINT_VERIFIED` for the paper journal at 672,718 events, and
host available memory of 8,190,214,144 bytes. API cgroup current was
1,608,658,944 bytes against `MemoryHigh=1,610,612,736`, leaving 1,953,792 bytes
(1.86 MiB); the earlier 04:33:30 point was only 1,024,000 bytes below the
same threshold. Reality cgroup current was 1,070,161,920 of 1,207,959,552
bytes `MemoryHigh`. The latest bounded Veritas observer run exited successfully
at 04:32:24Z under its 256 MiB limit, but its memory peak was unavailable and
the separate per-run resource status remains `NOT_MEASURED`. These point
samples keep heavy-research admission blocked; they do not identify a heap
leak or establish sustained capacity.

The later bounded resource endpoint sample at `2026-10-26T04:47:40Z` measured
API cgroup use at 1,593,131,008 bytes against `MemoryHigh=1,610,612,736`, with
17,481,728 bytes (16.7 MiB) headroom. It recorded 16 `high` events during its
4.368-second sample and no OOM events. Reality cgroup use was 1,078,980,608 of
1,207,959,552 bytes `MemoryHigh`; host available memory was 8,096,669,696
bytes. The current readiness API therefore continues to block heavy research
admission even though host-wide available memory is substantial.

At 04:48:57Z `/api/health` reported main API `READY` on `cf452ec`, demo mode,
`live_execution=false`, Laboratory `READY`, and paper recovery
`CHECKPOINT_VERIFIED` at 673,222 events. A fresh read-only Arena projection
showed zero active or queued jobs and zero active directors, three stale
persisted director manifests, zero unverified directors, and zero invalid
artifacts. Their owner jobs remain two `CANCELLED` and one `FAILED` after the
artifact budget was exceeded. One open alert refers to an already `EXPIRED`
60-second operational demonstration schedule titled “real admission expiry
after pause, no child admitted”; the schedule has no job ID. No manifest or
schedule was changed.

At `2026-10-26T05:06:26Z`, a bounded direct cgroup/procfs snapshot taken after
the web update measured API memory at 1,601,470,464 of 1,610,612,736 bytes
`MemoryHigh`, leaving 9,142,272 bytes (8.72 MiB). Its cumulative `high` event
counter remained 10,977 and OOM counters remained zero. Reality memory was
1,092,866,048 of 1,207,959,552 bytes `MemoryHigh`, leaving 109.8 MiB; host
available memory was 7,947,862,016 bytes. This is a point sample, not sustained
capacity evidence; heavy research admission remains blocked. The receipt is
listed in Section 6.

## 5. Verification and retained failures

| Area | Verification result |
| --- | --- |
| Veritas V6 core and persistence regression | 44 focused V6 tests passed; 186 post-merge backend regression tests passed; 26 API/Arena integration tests passed in the prior integration checkpoint |
| Current API/Veritas integration | 59 focused tests passed, including resource API, API integration, independent economics, observatory, and catalog tests; one upstream Starlette/httpx deprecation warning |
| V6 interrupted offline replay | 4 tests passed for resume after interruption, source/copy corruption, path/symlink overlap, and admission checkpoint |
| Reality integrated candidate | 66 tests passed on clean commit `d298957`; archive operations passed 17/17; Ruff passed; zero-duration isolated first-write and recovery replay passed with no network calls |
| Python quality | Ruff passed for changed API/tests; four Python files already format-clean |
| Frontend full unit suite | 32 tests passed across 6 files; final changed Readiness tests also passed 3/3 |
| Frontend checks | TypeScript, ESLint, Prettier, and production build passed; existing Chart (544.41 kB) and main (502.91 kB) chunks still trigger Vite's 500 kB advisory |
| Readiness browser test | Isolated Playwright Readiness test passed; deployed browser capture showed expected release IDs and live values at desktop/mobile widths, no page errors, and no 390 px horizontal overflow |
| Veritas missing-evidence rendering | Fixed three runtime crashes when an unmeasured observatory returned null counts/maps; null now renders as “Not measured,” while measured zero remains zero |
| Browser regression suite | Full suite 8/8 passed with one worker; after the final partial-measurement fix, targeted Veritas E2E passed 1/1 |

The prior 5/8 broad browser run exposed three test and UI defects, which are now
addressed rather than excluded. Arena's test asserted a generated-data
workflow against an isolated empty store, Reality's test depended on
machine-local archive data, and Veritas assumed opportunity counts and maps
were non-null even when the observer had no finalized snapshot. The browser
fixtures now model Arena and Reality state explicitly; the Veritas test checks
that an unavailable current analysis remains visibly unmeasured while frozen
historical evidence remains identified as historical. The full suite passed
8/8 with one worker. The Playwright API uses a temporary SQLite and Arena
root, and its Veritas workspace defaults to this worktree. That isolated
workspace reports `measurement_status=NOT_MEASURED`; it has no latest
snapshot, and `/api/veritas/artifacts/continuous-analysis` returns 404 because
no public observatory analysis has been generated there. This is not a probe
of the deployed production API; its persisted V6 state is covered by the
separate live evidence in Section 6. Current finalized-source gap detail is
unavailable in the isolated workspace; frozen campaign gap attribution
remains historical and is not presented as current-boundary verification.

During an earlier attempt to exercise the old Arena browser workflow, its
isolated temporary store trained one synthetic unmatched-risk classifier
(30 base episodes, 5 epochs). The follow-on diagnostics/evaluation job was
rejected with `resource_admission_lock_busy`; no frozen evaluation,
tournament, or research finding resulted, and the artifact is not evidence.
The replacement Arena E2E is a fixture-only view test that explicitly asserts
no `/api/arena/jobs` submission. This bounded test artifact remains outside
the research evidence set.

No new full-store recovery, collector restart, long-duration test, stress
campaign, or trading-strategy training was performed. The isolated synthetic
Arena classifier from the earlier E2E attempt is disclosed above and was not
used as a research result. No before/after optimization is claimed. The
bounded API cgroup sampling and runtime browser capture are measurement
evidence, not a synthetic performance benchmark.

## 6. Evidence artifacts and identities

Mission evidence files are under
`/home/charlie/midas-engineering-mission-20261026/evidence/`:

- `system-postflight-2026-10-26T0343Z.json` — whitelisted live API, V6,
  Reality, Arena/Laboratory, resource, and unit snapshot; SHA-256
  `2e0e99ce1248bda6fc223f22f4817e8f539f730e5d95cbddbdb462445aac3e91`.
- `api-startup-recovery-2026-10-26.json` — API startup timestamps, paper
  journal recovery count, cgroup peak and postflight breakdown; SHA-256
  `95b3e6dbb90c2eefc05668cc05ca631f49e097f98e2e0089135daf7687428513`.
- `research-readiness-live-2026-10-26.json` and
  `research-readiness-live-2026-10-26.png` — final live browser receipt and
  screenshot, captured at `2026-10-26T03:43:03Z`; SHA-256 values are
  `069f739231df41d6748aed780710d86fab16b6e7dae11161b55503ebd619e22f` and
  `b2cbebd5ee158dace650dba92208cf1101d235022894557fa904fd8f38a48229`.
- `research-readiness-transient-2026-10-26T034209Z.json` and `.png` — the
  incomplete projection during a scheduled refresh, retained with its
  `NOT_MEASURED` display rather than treated as final evidence.
- `web-null-evidence-regression-2026-10-26T0426Z.json` and
  `web-null-evidence-playwright-2026-10-26T0426Z.log` — bounded frontend and
  browser regression receipt plus the raw 8/8 Playwright log. The receipt
  records the changed-file hashes, cgroup bounds, current Reality process
  identity, and the isolated synthetic Arena E2E attempt described above;
  SHA-256 values are `c3abbf3968ec626c4dfbb6a591a77ae2fb2e7eb3f736667d9e3baf032cd4a347`
  and `b23667a865281939972a5ee6a0742e72c11375ee28f8630b2f8654a981958ed4`,
  respectively.
- `web-null-measurement-followup-2026-10-26T0431Z.json` and
  `web-veritas-targeted-2026-10-26T0431Z.log` — final partial-measurement UI
  check, 32/32 serial Vitest suite, typecheck, lint, Prettier, production
  build, and bounded targeted Veritas browser result. SHA-256 values are
  `930d2ea1877b6535afef7b06fb66eb77db2b580cef465c1ffd99a0d069f6eaa2` and
  `1514ee18decf58811d62d07cea4ed56540b754ff5086a219409133d31a0a471f`.
- `arena-director-owner-projection-2026-10-26T0433Z.json` — fresh production
  read-only research-activity projection, verified owner configuration/source
  linkage, and hashes for the three unchanged persisted manifests and job
  records; SHA-256 `c145a7ea5680108b15fddbea2fa1ab6a84b480874068a3fff0734d81bcb1be07`.
- `web-release-90c625d-predeploy-2026-10-26T0503Z.json` — immutable web
  release preflight, verified source tree, bounded build, prior service/API
  identities, and rollback inputs; SHA-256
  `3922125700f44d9bc7f02673b759d4f304a4c7364bb0e37580722662e67e093b`.
- `web-release-90c625d-postdeploy-2026-10-26T0503Z.json` — web/API health,
  active web PID, HTTP 200 loopback responses, served null-safe label, and
  unchanged Reality PID; SHA-256
  `230a4c6bd1f53aa99de4fb3d230e7a4298e5f8f1a580456fa6167ea98fa71871`.
- `web-release-90c625d-postdeploy-integrity-2026-10-26T0505Z.json` — rechecks
  all 1,844 source blobs and eight built assets after deployment, plus API and
  web identities; SHA-256
  `2d5e2fbb9db87d5049416e8e17b201720870a5bacc88c1121c8f2808c4e15216`.
- `midas-post-web-deployment-resource-2026-10-26T0506Z.json` — direct
  post-deploy cgroup/procfs and unit-state snapshot; it classifies the sample
  as point-in-time, not sustained capacity. SHA-256
  `23951cf13245bfc826afd247708cc3399a44adeb769be8417e8ad22b0b81fdb6`.
- `resource-api-post-browser-2026-10-26T0433Z.json` — live API health and
  bounded cgroup/host/observer sample at 04:33:53Z; SHA-256
  `f59e50f0a919ea16c94c6601963b00ece37b07d3449e03e9975b75c7fbcf283b`.
- `reality-live-observability-2026-10-26T0435Z.json` — live Reality overview
  and operations projection, preserving unsequenced-source and unavailable
  current telemetry states at collector ordinal 5,155,334; SHA-256
  `3ce86d583777ff3ba339a5f424358d936dfef27351c5b0178e594571e9991d02`.
- `veritas-live-v6-postobserver-2026-10-26T0438Z.json` — post-observer V6
  funnel and Decimal reference counts, latest discovery cohort, direct API
  artifact checks, source/gap index boundaries, and verified summary-file
  identity; SHA-256
  `470ce82775558e7c3b3982076a51e0e13b115b07ac4650567db24d4aa777c86b`.
- `reality-final-candidate-first-write-2026-10-26T0447Z.json` — final clean
  Reality candidate `d298957` startup, zero-duration network-guarded first
  durable write, three-record finalization, checkpoint replay, source identity,
  and unchanged protected PID; SHA-256
  `ab6ca1486a826a877ad42caca15912afcadb02e2f330715df58193f32a520a4f`.
- `reality-archive-state-regression-2026-10-26T0450Z.json` and `.log` — final
  archive-state tests (17/17) and Ruff result on `d298957`; receipt SHA-256
  `33eb9d4e59f1158a22cf599046b4b9d2a3ca89e13dcb514054dd9bf2e07d9907`, log
  SHA-256 `7e9a963e308436ba6964ba05776a59ac06cda8a6128d3d175325485d71cc04b0`.
- `reality-candidate-regression-2026-10-26T0451Z.json` and `.log` — final
  Reality, dashboard, and operations suite (66 passed, one upstream
  deprecation warning) and Ruff result on `d298957`; receipt SHA-256
  `f302f552a6fa438892c6c43484b2f7c970381772dc13d41dd35caaa7d625159b`, log
  SHA-256 `bc6676df1cd295628829152b837f1fc3a89b3f48d26afa0f65192e4cefd9b9fb`.
- `reality-read-only-deployment-preflight-2026-10-26T0455Z.json` — bounded
  metadata-only exact-boundary preflight, candidate/config identities,
  archive manifest state, cgroup deltas, and explicit blockers; it did not
  read source contents or invoke the official deployment gate. SHA-256
  `f2cb8fa8a5947f96c94b69c8e722fe35a8a9260e3ccee730f02eee94de27ca43`.
- `data/veritas-v6-offline-replay-522-20261026/` in the preserved
  `midas-engineering-mission-20261025` worktree — isolated 522-snapshot replay
  receipt SHA-256
  `1ddfe7a27bb7a85b499aaa71f41ac551924649d9c994cee5c870db0b619dc7e6` and
  post-run verification SHA-256
  `5d5cb78d9940882d4e3c1b06456c522db84679ccbb242b49e7395664fe94feca`.

The active UI package manifest is at
`/home/charlie/.local/share/midas-api/releases/90c625d/RELEASE-MANIFEST.json`,
SHA-256 `cd3a76adc08c44451550dbb5476a8f5c4d55f5cadbf5fda5a5085507e1392590`;
the previous `4f4179c` UI release remains available for rollback. The API
manifest is at
`/home/charlie/.local/share/midas-api/releases/cf452ec/RELEASE-MANIFEST.json`.
Each records the full source commit and tree identity. Existing older release
directories remain available for rollback.

## 7. Final classification and next actions

| Component | Classification | Current verdict |
| --- | --- | --- |
| Veritas V6 code, independent Decimal reference, catalog migration and bounded publication | **COMPLETE AND VERIFIED** | Integrated and scheduled; latest update has 40/528 snapshots processed, 488 pending, and 1,095 source-quality plus 1,095 validity flags (categories may overlap) |
| Economic evidence | **PARTIALLY VERIFIED** | Latest reference covers 1,600 repeated pairs across 741 markets; 310 independently snapshot-valid, zero economic support/net eligibility, and execution outcomes remain unmeasured |
| Readiness resource API and dashboard | **COMPLETE AND VERIFIED** | Deployed at API `cf452ec` / web `90c625d`; browser receipt and screenshot available |
| Veritas missing-evidence rendering and deterministic browser fixtures | **COMPLETE AND VERIFIED** | Null renders as `Not measured`, distinct from measured zero; targeted browser test passed, and immutable web release `90c625d` serves the fix with HTTP 200 smoke verification |
| Reality candidate hardening | **IMPLEMENTED, DEPLOYMENT PENDING** | Clean candidate `d298957` integrates the 4278 telemetry base and archive fail-closed fixes; 66 Reality/dashboard/operations tests pass. First-write and checkpoint replay are verified. A feed canary, complete latest-boundary recovery, storage clearance, and protected-restart authorization remain |
| Reality candidate bounded telemetry | **IMPLEMENTED, DEPLOYMENT PENDING** | Candidate exposes bounded persistence, transport-queue, backpressure, checkpoint, and resource fields; production API still lacks these observations |
| Production Reality telemetry/integrity | **PARTIALLY VERIFIED** | At the 04:47Z API read, all 16 books were fresh and the collector was receiving, but health remained degraded/unsequenced with persistence-window, queue-depth, and recovery-state telemetry missing |
| Cold recovery/reproducibility | **PARTIALLY VERIFIED** | Source analysis covered 32,035/32,035 of its captured index and gap detail 32,048/32,050 replayable segments; live ordinal 5,159,119 is ahead. The latest boundary is not fully verified |
| Storage/archive provenance | **BLOCKED** | Effective capacity runway is 16.7 days, staged capacity is inactive, and archive manifest/provenance remain invalid; the new guard preserves and blocks ambiguous files |
| Cross-component research admission | **PARTIALLY VERIFIED** | Dashboard blocks at low API `MemoryHigh` headroom; Arena has 0 active/queued jobs, 3 stale owner-linked directors (2 cancelled, 1 failed), and an expired no-child demonstration schedule alert |
| Trading, Frontier, Atlas, 48-hour campaign | **DEFERRED BY SCOPE** | Not started |

Recommended next actions:

1. Keep heavy replay and training work out of admission until the API cgroup
   has fresh `MemoryHigh` headroom; measure the charged file-cache decay and
   pressure before changing service limits.
2. Optimize or checkpoint paper-journal verification only with an integrity-
   preserving design and corruption/interruption regression tests. Do not
   infer a leak from the page-cache charge or skip rolling-hash validation.
3. Let the scheduled bounded V6 observer continue its existing cadence; do
   not manually accelerate it. Review the 488-snapshot backlog and the
   latest scan's 8 reference-random / 32 rotating / 0 stable-control split on
   the next scheduled result.
4. Keep Arena director lifecycle state derived from the matching owner job;
   preserve the three persisted manifests, and investigate any future
   `UNVERIFIED` projection before considering a mutation. The expired
   one-minute operational demonstration schedule has no child job and should
   remain an evidence record, not be re-dispatched.
5. Keep the Reality recorder on its current service. The archive-provenance
   and unmanifested-segment fixes are integrated on
   `codex/reality-archive-provenance-20261026` at `d298957`; the bounded
   first-write and 66-test candidate checks pass. The exact-boundary preflight
   remains blocked. Before any transition, reconcile NVMe headroom and archive
   provenance, install and verify an immutable candidate release, complete a
   bounded feed canary and recovery at the current raw boundary, and prepare
   rollback plus the expected recording-interruption statement. Then request
   separate approval for the protected stop/restart.
6. Resolve archive ownership and provenance for the 1,138 out-of-manifest
   names and 58 `.copying` files before adoption; do not delete them or enable
   archive writers until ownership and integrity are established.
7. Resume latest-boundary recovery only from a checksummed copy with a bounded
   checkpoint and safe resource admission. Report partial coverage until the
   complete boundary is reconciled.
8. Keep browser verification fixture-based for Arena and Reality, retain the
   explicit no-job assertion in Arena, and keep the large-chunk advisory
   visible in the deployed UI build record.

This closeout does not authorize a Reality service restart, archive mutation,
or a new research campaign.

## 8. Final Reality candidate follow-up — 2026-10-26 03:54 UTC

The archive validator and regression tests were copied from the preserved,
dirty reliability checkout into a clean worktree at
`/home/charlie/midas-reality-archive-provenance`. Commit
`987481fd6ae611d062155063c19f24b5ea51bb18` on
`codex/reality-archive-provenance-20261026` contains only the archive-state
fail-closed change and its tests. Its Reality module source identity is
`c2a5696668828dce79b54ce202715262f4d86f06256525f84f880a76a4f5c1b3`; the
original `/home/charlie/midas-reality-reliability` worktree remains untouched,
including its unrelated untracked evidence. `tests/test_reality_operations.py`
passes 14 tests in 1.73 seconds on the clean candidate worktree.

The isolated startup receipt is
`/home/charlie/midas-engineering-mission-20261026/evidence/reality-candidate-isolated-first-write-2026-10-26.json`
(SHA-256
`21f71e585211318116ea0f0fa2a4db4767eacb6a70308ef85e7c1e872d6edb67`). It ran the
collector for zero feed duration against a temporary root, made no network
requests, wrote the `process_start` gap durably, finalized three contiguous
records, and replayed the recovery checkpoint through ordinal 3. This proves
startup/recovery/first-write mechanics only; it is not a source-feed canary or
production recovery proof.

The read-only exact-boundary deployment-preflight record is
`/home/charlie/midas-engineering-mission-20261026/evidence/reality-deployment-preflight-2026-10-26T0354Z.json`
(SHA-256
`53f1d11909238d91c0e73ff81fcf3351e018b4b60c219a67550a5dfc81e6c7f8`). It is
explicitly blocked, not a green deployment gate. At 03:54:13 UTC the protected
process was still PID 3007040 on production commit
`4f5cb5689548987bf30a33f050284ea8cb2f3c28`, with the 24 GiB / 90-day
configuration, at collector ordinal 5,143,954. The raw root had 31,946
finalized segment names, 204 beyond the copied 31,742-segment recovery
boundary. The old checkpoint still covers only 2,816 of 31,742 segments.

Current archive inventory remains 19,833 `.seg` files versus 18,695 manifest
entries, 1,138 names outside the manifest, and 58 preserved `.copying` files
(16,471,242 bytes). All archived segment names were present in the raw source
directory, but their contents were not fully hash-verified. The writer timer
remains disabled. The archive filesystem has 634,806,595,584 bytes free, but
provenance and inventory validation block use.

The capacity receipt measured 15-minute-old input at 03:40 UTC: the live budget
is 25,769,803,776 bytes / 90 days with 16.53 effective days and 15.17 days in
the short window. The staged 120,259,084,288-byte / 120-day configuration
shows 108.18 configured runway days. At preflight time NVMe free space was
160,133,648,384 bytes. Direct file-size deltas since the 2026-10-21 storage
policy sample showed net growth of about 674 MB/day for the MIDAS database and
644 MB/day for the Reality preview database over 4.73 days. A transparent
straight-line 30-day database scenario, combined with the staged policy's
90-day raw-growth scenario, 20 GiB reserve, and 4 GiB Veritas budget, exceeds
current NVMe free space by 10,286,571,682 bytes. This short sample is a
scenario, not a long-term forecast; it is sufficient to keep storage clearance
blocked until the shared-service plan is recalculated and supported.

At the same sample the MIDAS API cgroup was at about 99% of `MemoryHigh`
(1,594,994,688 / 1,610,612,736 bytes; 1,414,471,680 bytes charged as file
cache, 165,072,896 bytes anonymous; no `max` or OOM events). Reality was at
1,065,025,536 / 1,207,959,552 bytes `MemoryHigh`, with no `max` or OOM events.
These measurements support holding restart admission; they do not establish a
Python heap leak.

The candidate runtime release is not installed. The official deployment gate
was not invoked because its fresh verification receipt, bounded candidate feed
canary, and complete latest-boundary recovery prerequisites are absent. No
protected service, source recording, archive contents, or runtime
configuration was changed during this follow-up.

## 9. Browser reliability follow-up — 2026-10-26 04:31 UTC

The prior 5/8 browser result is closed by fixes and deterministic test data,
not by skipping the three failures. The Veritas page had three null-handling
crashes on the isolated workspace's valid not-measured response: a missing
minimum-notional count, a missing opportunity-count formatting value, and a
missing per-leg source-quality map. The page now preserves the distinction
between an unmeasured value and a measured zero. It also labels missing
current analysis and finalized-source gap detail as unavailable, while
retaining the frozen campaign attribution as historical evidence.
The Playwright API uses temporary SQLite and Arena roots, and the Veritas
workspace defaults to this worktree; the test does not query the deployed
production API.

Arena and Reality browser verification now use explicit synthetic response
fixtures and state their fixture scope. The Arena test checks the model
registry, diagnostics link, limitations, and absence of a job submission.
Reality's test exercises its explorer and replay surfaces using fixture-only
market and decision records, without relying on local archive data. The full
Playwright suite passed all eight tests with one worker. After a final
adjustment ensuring a missing candidate-event count stays “Not measured” even
when some other opportunity fields are measured, the targeted Veritas browser
test passed 1/1. The raw logs and reproducibility receipts are listed in
Section 6. Vitest's complete frontend suite passed serially (32 tests across
six files); its first parallel run had one timeout under concurrent resource
pressure, and no timeout threshold was raised. Typecheck, lint, formatting,
and production build also passed. The existing Vite bundle-size advisory
remains.

One earlier run of the old Arena E2E trained a single synthetic unmatched-risk
classifier (30 base episodes, five epochs) in a temporary test store before
the shared admission lock rejected its diagnostics/evaluation follow-up. It
produced no frozen test, tournament, or research finding, and is not included
in evidence. The replacement E2E does not submit Arena jobs. At this 04:31
capture, the UI/test follow-up had not been deployed. After the bounded
Playwright scope ended, no Playwright or fixture worker remained; the
protected Reality unit remained active at MainPID 3007040 with its original
2026-10-22 16:40:02 CEST start time. The web reliability changes are committed
as `90c625d4e168c64fe3c8d1f93e0c1393734fd009`; they were later deployed at
05:03 UTC as recorded in Section 4.

## 10. Final exact-boundary read-only preflight — 2026-10-26 04:55 UTC

The final preflight was deliberately limited to filesystem metadata, the
published manifest, service state, bounded API projections, and cgroup/host
counters. It ran under a 128 MiB `MemoryHigh`, 192 MiB `MemoryMax`, 10% CPU,
32-task scope with a 45-second bound. It did not read raw or archived segment
contents, calculate content hashes, call the official deployment gate, or
change the running system.

At `2026-10-26T04:55:04Z`, the protected Reality service was active on PID
3007040 with the same production source and start time. The raw root contained
32,065 finalized segment names (9,119,618,318 bytes), one `.open` file of
422,130 bytes, and matching numeric sidecars. The live ordinal was 5,160,978;
sequence verification remained false. The source-analysis artifact covered
32,035 segments through ordinal 5,156,975; gap detail covered 32,048 replayable
segments from a 32,050-entry catalog through ordinal 5,158,905. All three
indexes describe different incremental boundaries, and none verifies the
current complete store.

Production still used source SHA-256
`26b9bc331a1a47b020116668dec720764e4253b8200c69cce75271ee3c2db182` from
commit `4f5cb5689548987bf30a33f050284ea8cb2f3c28`; its loaded config
`/home/charlie/midas-reality/deploy/reality.json` had SHA-256
`9d1aeeb5a496ad6971dc461ce87f327266ff25240391897f7bb6091a8307119a`. The
clean candidate `d298957` source identity is recorded above; its candidate
collector configuration SHA-256 is
`8c1f8d445e2546d058065ada027d652886523e333930532fff5a044389df137c`.

The archive contained 19,833 segment files totaling 5,369,550,131 bytes
against 18,695 manifest entries. The 1,138 out-of-manifest finalized files
matched current raw names; 58 `.copying` files occupied 16,471,242 bytes. The
manifest's internal hash and root fields matched their own metadata, but the
read-only API still classified provenance as `INVALID_MANIFEST`. No segment
content hashes were recomputed. The archive remained untouched; its writer
and timer remained disabled. The new candidate's fail-closed guard is verified
on isolated fixtures only.

At the after-sample, API cgroup use was 1,595,154,432 of 1,610,612,736 bytes
`MemoryHigh`, leaving 15,458,304 bytes (14.74 MiB); no new `high` or OOM events
occurred during the bounded scan. Reality cgroup use was 1,084,534,784 of
1,207,959,552 bytes `MemoryHigh`, with no new high or OOM events. Host available
memory was 8,098,099,200 bytes. CPU PSI's 10-second `some` value was 37.01% at
the after-sample versus 2.87% before it; this point change is not attributed
to the metadata scan. Heavy research admission remains blocked.

The active 24 GiB / 90-day contract projected 16.70 effective runway days and
20.20 short-window days. Staged 112 GiB / 120-day settings projected 108.14
days, below the retention target. The clean candidate commit
`d298957afe14d6cbbc47038fbb101a96a63fadca` passed its final 66-test Reality,
dashboard, and operations suite and isolated zero-duration first-write check,
but has no immutable runtime release and no public-feed canary. The preflight
is **BLOCKED**, not deployment-ready: full current-boundary cold recovery,
feed canary, telemetry completeness, resource headroom, storage runway,
archive provenance, Reality candidate runtime release installation, and
separate protected-restart authorization remain unresolved. The complete
bounded receipt and hash are listed in Section 6.
