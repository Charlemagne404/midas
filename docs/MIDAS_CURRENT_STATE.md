# MIDAS current state

**Snapshot date:** 2026-10-17 (historical operational baseline; the details below have not been refreshed for 2026-10-26).

**Current verified status:** Use the [MIDAS engineering mission report for 2026-10-26](reliability/MIDAS_ENGINEERING_MISSION_2026-10-26.md) for the later API, dashboard, Veritas V6, Reality collector, recovery, storage, and archive measurements. Its newest exact-boundary read-only preflight is timestamped `2026-10-26T04:55:04Z`. Do not treat the service health, campaign counts, resource figures, or index boundaries below as current without rechecking their capture times.

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

Project Atlas remains deferred. Frontier was not yet implemented at this
2026-10-17 historical snapshot; its later isolated development state is recorded
in the dated addendum below and in the Frontier engineering report.

## Frontier development addendum — 2026-10-28

### Latest isolated Frontier checkpoint — 2026-10-28 17:23 UTC

A local read-only API smoke against a temporary copy of the captured Polymarket
store returned all five event markets, the one saved book, ten `hypothesis`
relationships, a four-edge centered neighborhood, and HTTP 200 for the
hash-pinned event observation. The routes reported recorded-only evidence and
made no network request. This did not rerun browser E2E. The smoke emitted the
existing Starlette/httpx TestClient deprecation warning.

At 17:23:10Z, systemd reported `midas-reality.service` and `midas-api.service`
as `inactive/dead` with no main PID. No cause is known and no service action
was taken; a prior 17:18:23Z sample had shown both active. Memory PSI was
48.55% avg10 / 43.35% full avg10 (32.43% / 28.77% avg60), with about 9.7 GiB
available and 2,092 KiB swap free. Broad regression remains paused. Read the
report and mission ledger for evidence and timing limits.

### Prior isolated Frontier checkpoint — 2026-10-28 17:18 UTC

Three bounded unauthenticated requests through the Polymarket public adapters
produced a Gamma market listing, a CLOB order book, and a Gamma event group.
The event lookup returned five child markets for event `606422`; Frontier
persisted ten source-pinned `SAME_EVENT` hypotheses, all still unverified for
payoff or settlement equivalence. Two replays reproduced the same run and
result hashes, returned zero opportunity candidates, and passed persisted
hash validation. The isolated store contains three observations, three replay
records, and ten relationships in 270,336 bytes. The book had five asks, no
bids, and a best ask of 0.995 in the requested depth; its exchange timestamp
was about 10.04 seconds before receipt, with precision and simultaneity
unknown. No cross-venue equivalence or executable economics is established.

The full Arena regression was paused after 105 passing cases when memory PSI
rose to 36.63% avg10 / 31.86% full. No assertion failure preceded
interruption; this is not a full-suite pass. Both protected services remained
active and untouched. Keep broad regression paused until a fresh resource
sample clears the memory-pressure gate. Raw capture, replay, and integrity
details are in the [Frontier mission ledger](frontier/FRONTIER_MISSION_LEDGER.md)
and [engineering report](frontier/FRONTIER_ENGINEERING_REPORT.md).

### Prior isolated Frontier checkpoint — 2026-10-28 16:45 UTC

Price-history replay now checks observation-ID length before duplicate-set
hashing, then validates lowercase SHA-256 format and uniqueness. The API
regression returns 422 for an overlength ID and confirms no extra replay is
persisted. Its focused test passes 1/1; Ruff, format, syntax, and diff checks
pass. The earlier relationship-review and Coinbase source-policy regressions
also pass as recorded below. At 16:45Z, CPU PSI avg10 was 34.45%, memory PSI
0%, I/O PSI 0.14%, and about 9.7 GiB was available; swap remained full. Reality
and API services were active. No public endpoint was queried. Code commit:
`e44b23d`.

The virtual cross-venue capital-carry module passed 27/27 at 16:43 on code HEAD
`b7f2155`, in 0.46 seconds using a tmpfs test directory. Subsequent commits
changed API validation/tests and documentation, not capital-carry logic. Static
review confirms per-venue capital isolation and an independent arithmetic
audit. It remains a sensitivity over user-entered rates; it does not establish
venue fees, transfers, collateral, custody, or executable capital availability.

The relationship-review module passes 16/16 after request-level digest
validation. Coinbase adapter/source-permission modules pass 18/18 after
updating a stale assertion to the shared hold reason. The changed Frontier UI
test passes 1/1 (eight other cases were filtered out). Ruff, formatting, and
`git diff --check` pass. The first Coinbase run exposed only that stale test
expectation; the corrected rerun passes. At 16:42Z, CPU PSI avg10 was 33.24%,
memory PSI 0%, I/O PSI 0.01%, and about 9.9 GiB was available; swap remained
full. Reality and API services were active. No source endpoint was queried.

At the 16:39 checkpoint, relationship-review requests had been changed to
reject evidence identifiers unless each is a lowercase 64-character SHA-256
digest, before observation lookups. The same-payoff and logical-implication
mappings remain bounded by their request model. The focused tests were pending
at that timestamp; the later 16:42 run passed the full 16-case review module.
Implementation commit: `8c898dc`.

The Coinbase source-status reason now lists the specific activities in the
2026-08-07 Market Data Terms restriction: developing, training, fine-tuning,
teaching, validating, benchmarking, or improving AI/ML systems, plus related AI
research, development, or operation, absent prior express written consent. No
permission, entity, region, or intended-scope review is validated, so the
deny-by-default source hold remains. Tests were pending at the 16:36 checkpoint;
the later 16:42 run passed the adapter/source-permission modules and changed UI
case. No Coinbase endpoint was queried.

The official [Coinbase Market Data Terms](https://www.coinbase.com/legal/market_data)
and full source-use review are recorded in the linked Frontier engineering
report and [terms review](frontier/SOURCE_DATA_TERMS_REVIEW_2026-10-28.md).

The public-read transport follow-up contains injected adapter hosts within
each adapter's declared host set. The focused regression passes **3/3**;
strict mypy for the adapter base, Ruff, and Ruff format pass. The full current
`tests/frontier` suite passes **475/475** (16:04 UTC), with one existing
Starlette/httpx deprecation warning. The frontend suite passes **47/47**;
TypeScript, targeted ESLint, and Prettier pass. A test-only UI assertion keeps
the spot-price versus event-payoff distinction visible. Production build and
fixture-browser evidence remain at the separately dated 13:59 UTC checkpoint.

A finite retry of all **427 `tests/arena` cases** advanced beyond 50% without a
reported assertion failure, but was stopped after 9:06.59 under sustained host
CPU pressure. It produced no test summary and is not a pass. The verified
Frontier pytest worker used 549.86 CPU seconds, peaked at 487,772 KiB RSS, and
used zero swaps or sockets. After it exited, CPU PSI remained elevated: 42.63%
avg10 / 37.65% avg60 at 16:21:29Z and 41.51% / 40.14% at 16:23:12Z. Memory and
I/O PSI were low. This is host-level evidence; no cause is assigned to Frontier
alone. Broader regression remains deferred until fresh samples show stable CPU
pressure.

At 16:30:27Z, CPU PSI remained 41.18% avg10 / 40.35% avg60 while memory and
I/O PSI avg10 were 0.00%. At 16:30:43Z, read-only systemd inspection confirmed
the protected `midas-reality.service` and `midas-api.service` were active; the
Reality process was in its service cgroup. Their accounted memory was
1,207,721,984 and 1,223,196,672 bytes. These readings do not represent
available headroom. No service was restarted or reconfigured.

Kalshi, Kraken, and Coinbase source-use holds remain in force. No live endpoint,
protected Reality service, or historical source evidence was accessed or
changed. Frontier stays isolated, research-only, and undeployed. See the
[Frontier engineering report](frontier/FRONTIER_ENGINEERING_REPORT.md) and
[mission ledger](frontier/FRONTIER_MISSION_LEDGER.md) for exact run details and
the current acceptance matrix.

### Latest isolated Frontier checkpoint — 2026-10-28 13:09 UTC

The relationship audit found that copied models with empty payout-state sets
could make both same-payoff and logical-implication proofs pass over empty
mappings. Both direct verifiers now require nonempty exhaustive states and
structurally valid market records. Verifier versions advanced to same-payoff
v8 and logical-implication v4; independent audit v22 makes earlier evidence
incomplete for new audited candidates. The three affected regression modules
pass **97/97**, strict mypy passes on all three changed core modules, and Ruff
plus whitespace checks pass. The full Frontier suite plus Arena
replay/discovery/timeline regression passes **463/463** in 111.02 seconds
(112.48 seconds wall), at 380,764 KiB peak RSS with zero swaps and socket
messages. One existing Starlette/httpx deprecation warning remains. Post-run
memory PSI avg10 was 0.00%, I/O PSI was 5.37% some / 4.16% full, and about
10 GiB was available; further tests are held until I/O pressure falls below the
1% gate. Frontier remains **PARTIALLY VERIFIED**, isolated, research-only, and
undeployed. The verifier correction is committed as `eb53842`. A read-only
follow-up found no further empty-state acceptance in the bounded multi-outcome
and joint-state audits or the verified relationship-review API path; no new
runtime test was run during the post-suite I/O pressure hold.

### Latest isolated Frontier checkpoint — 2026-10-28 13:17 UTC

The Frontier store now revalidates typed observation, relationship, review,
replay, historical replay, and paired-comparison inputs before persistence.
Replay writes also recheck manifest identity and content hash. The storage
suite passes **25/25** and strict mypy passes for the store module. The full
Frontier/Arena suite passes **468/468** on the exact updated tree in 31.61
seconds (33.10 seconds wall), at 380,404 KiB peak RSS with zero swaps,
filesystem input, and socket messages. One existing Starlette/httpx warning
remains. Output used the isolated tmpfs root
`midas-frontier-storage-all-writers-full-20261028`. Post-run memory PSI avg10
was 0.00%, I/O PSI was 0.01% some / 0.01% full, and about 10 GiB was available.
The change is committed as `e99cf0e`. Frontier remains **PARTIALLY VERIFIED**,
research-only, isolated, and undeployed.

### Latest isolated Frontier checkpoint — 2026-10-28 13:00 UTC

An offline verifier audit reproduced a vacuous proof: two binary markets with
empty instrument sets could be marked as same-payoff equivalent because the
empty instrument mapping is a bijection. The verifier now requires actual
instrument payout vectors and has advanced to version 7, which causes the
independent audit to reject prior v6 attestations as current verification.
The empty-left/right/both regression and prior-verifier v5/v6 checks pass; the
full Frontier and related Arena regression passes **459/459**. Ruff, format,
and strict mypy for the changed verifier and independent audit pass. Tests and
mypy used isolated `/tmp` roots with zero swap and socket traffic. Frontier
remains **PARTIALLY VERIFIED**, research-only, isolated, and undeployed.

### Latest isolated Frontier checkpoint — 2026-10-28 12:52 UTC

The Arena discovery fixture now cites the exact source observation IDs pinned
to both market records. The strict same-payoff verifier had correctly rejected
the former placeholder IDs; no production verifier behavior changed. Arena
discovery, Arena timeline, and Frontier discovery-scope comparison regressions
pass **15/15**. The bounded run took 5.88 seconds, peaked at 198,600 KiB RSS,
and used no swap or socket traffic. Frontier remains **PARTIALLY VERIFIED**,
research-only, isolated, and undeployed; live cross-venue evidence and
production readiness remain open.

### Latest isolated Frontier checkpoint — 2026-10-28 12:48 UTC

The broader one-worker non-Veritas browser suite passes **16 tests**; the two
seeded Frontier cases were skipped in its empty-store run and pass separately
**2/2**. This included Frontier, Arena, Laboratory, paper simulation,
fixture-backed Reality explorer, Readiness, deferred charts, and Mission
Control. Laboratory's bounded 6-run comparison and 1-run adversarial test
completed in the temporary database. The historic Veritas artifact browser
case remains unrun because it requires preserved workspace files; no such
workspace was accessed.

At 12:48:15Z memory PSI avg10 was 0.00%, I/O PSI some/full was 0.01%/0.00%,
about 9 GiB was available, and no browser test process swapped. The local API
and Vite servers exited. Frontier remains **PARTIALLY VERIFIED**,
research-only, isolated, and undeployed.

### Latest isolated Frontier checkpoint — 2026-10-28 12:46 UTC

Frontier frontend checks pass: TypeScript, ESLint, Prettier, production Vite
build, **47/47 Vitest**, and **12 focused Playwright cases** across empty and
seeded data. Browser checks cover the Frontier workspace, mobile graph
overflow, chart lazy-loading, explicit history replay, fixture-only Kalshi
settlement, and hash-verified Arena evidence in Laboratory. All local servers,
database files, replay artifacts, screenshots, and build output were isolated
under `/tmp`; no exchange probe or production service was used.

An additional readiness browser case passed **1/1** without an explicit E2E
run ID, verifying that generated temp-root ownership markers survive worker
config reloads.

The first E2E run exposed a missing parent directory for the temporary SQLite
database. The Playwright config now creates a fresh real temporary root and
checks a per-run owner marker so workers can reload configuration without
accepting stale state. The Vite build warns that its deferred chart chunk is
544.51 kB (186.79 kB gzip); the chart remains lazy-loaded.

At 12:46:07Z memory PSI avg10 was 0.00% and I/O PSI some/full was 0.08%, with
about 9.9 GiB available and no timed test process swapping. Frontier remains **PARTIALLY VERIFIED**,
research-only, isolated, and undeployed; genuine cross-venue evidence and
production readiness remain open.

### Latest isolated Frontier checkpoint — 2026-10-28 12:33 UTC

Three bounded regression groups now pass: Reality source-quality reconciliation
**10/10**, Veritas independent-economics plus offline V6 replay **24/24**, and
the MIDAS integration suite **56 passed, 1 optional PostgreSQL test skipped**.
The integration run used temporary databases and replay files, took 28.49
seconds (29.77 seconds wall), peaked at 223 MiB RSS, and used no swap or socket
traffic. One existing Starlette/httpx deprecation warning remains.

The source anomaly fixture was corrected from unsupported reconstruction
revision 5 to the current supported revision 4. At 12:33:34Z memory PSI avg10
was 0.00%, I/O PSI was 0.56% some / 0.39% full, and about 10 GiB was
available. No public source, protected recording, frozen campaign, production
service control, or persistent operational store was accessed. Frontier
remains **PARTIALLY VERIFIED**, research-only, isolated, and undeployed.

### Latest isolated Frontier checkpoint — 2026-10-28 12:29 UTC

Additional Reality regression slices pass: synthetic foundry **18/18**,
training/replay **19/19**, staging admission **17/17**, read-only sandbox
**1/1**, and shadow replay **20/20**. All tests used synthetic or temporary
roots; shadow needs `/tmp` because `/dev/shm` free space fell below its
configured reserve. The initial three reserve-guard failures all passed on
`/tmp` before the complete 20-test run. No protected recording, frozen
campaign, live source, or service was accessed.

At 12:29:11Z memory PSI avg10 was 0.00%; I/O PSI some was 1.08% and full was
0.90%, so additional runs are deferred until a fresh sample clears the 1%
gate. Frontier remains **PARTIALLY VERIFIED**, research-only, isolated, and
undeployed.

### Latest isolated Frontier checkpoint — 2026-10-28 12:26 UTC

The public transport now rejects injected HTTP clients carrying auth, sensitive
headers, cookies, request hooks, default query parameters, base URLs, or
redirect settings. Requests enforce anonymous GETs, configured timeouts, no
redirects, and cookie cleanup. Strict mypy and Ruff pass.

The exact current Frontier Python suite passes **430/430**. Focused transport,
adapter/Coinbase, and collection slices pass **15/15**, **84/84**, and
**27/27**; the corrected Reality schedule module passes **4/4**. Those bounded
runs report zero swaps and socket messages. Pre/post full-suite samples show
memory and I/O PSI avg10 at 0.00%. No live source, protected store, or service
was accessed. Frontier remains **PARTIALLY VERIFIED**, research-only, isolated,
and undeployed; source authorization and broader repository acceptance remain
open.

### Latest isolated Frontier checkpoint — 2026-10-28 12:20 UTC

At 12:20:05Z memory PSI avg10 remained 36.90% some / 27.21% full; I/O PSI
was 0.29% some / 0.00% full. About 10 GiB was available, with 3.5/4 GiB
swap in use. No tests, build, or type check started. The new collection
transaction and schedule fixture changes remain pending runtime validation.
Frontier remains **PARTIALLY VERIFIED**, research-only, and undeployed.

### Latest isolated Frontier checkpoint — 2026-10-28 12:18 UTC

At 12:18:47Z I/O PSI avg10 recovered to 0.01% some / 0.01% full, while
memory PSI remained 36.13% some / 31.37% full. About 10 GiB was available
and 3.5/4 GiB swap was occupied. No tests, build, or mypy run started. Runtime
verification of commits `36546cd` and `cd248ce` remains pending until both PSI
avg10 values fall below 1%. Frontier remains **PARTIALLY VERIFIED**,
research-only, isolated, and undeployed.

### Latest isolated Frontier checkpoint — 2026-10-28 12:16 UTC

Commit `36546cd` makes creation of a finite collection run and its initial
checkpoint atomic. A failed checkpoint insert rolls back the run record, and
source requests begin only after both rows commit. The trigger-based rollback
regression and successful initial-state assertion are implemented. Ruff and
format checks pass; runtime tests and strict typing are pending.

At 12:16:41Z memory PSI avg10 was 25.94% some / 18.04% full and I/O PSI was
4.83% some / 3.18% full. About 10 GiB was available, with 3.5/4 GiB swap in
use. No tests were launched under that pressure. The 420/420 Frontier result
predates the latest code and fixture changes. The untracked public-capture
directory remains untouched. Frontier remains **PARTIALLY VERIFIED**,
research-only, and undeployed.

### Latest isolated Frontier checkpoint — 2026-10-28 12:12 UTC

Test commit cd248ce corrects the research-schedule fixture to patch the same
source module used by dataset_fixture. The prior date shift targeted a
separately imported top-level module, so it produced duplicate synthetic
dataset periods and the overlap guard correctly rejected the second
evaluation. Ruff and format checks pass; runtime verification is pending.

At 12:12:41Z memory PSI avg10 was 44.70% some / 40.61% full, above the 1%
test gate. All attempted writes were confined to /dev/shm. No protected data
or service was accessed. Frontier remains **PARTIALLY VERIFIED**,
research-only, and undeployed.

### Latest isolated Frontier checkpoint — 2026-10-28 12:10 UTC

Additional bounded Reality regression passed: calibration **18/18** and
dashboard API **14/14**, bringing the reviewed Reality slices to **71 passing
tests** plus one intentionally deselected self-signaling case. Dashboard
operations were rooted in tmp_path and its systemctl subprocess was mocked.
The existing Starlette/httpx deprecation warning remains.

After the dashboard run, I/O PSI avg10 rose to 1.53% some / 1.35% full, so
additional test runs are deferred until a fresh sample falls below 1%. No
recording, live source, or service was touched. Frontier remains
**PARTIALLY VERIFIED**, research-only, and undeployed.

### Latest isolated Frontier checkpoint — 2026-10-28 12:09 UTC

The isolated Reality model slice passed **13/13** selected tests; one
self-signaling test was deselected. The Reality panel and observation slice
passed **26/26**. Both used tmpfs or in-memory evidence, mocked HTTP, and
localhost-only WebSockets. No protected recording, source, or service was
accessed.

The calibration test module was reviewed as synthetic and source-independent,
but not run after the 12:10:00Z I/O PSI sample reached 1.04% some. Frontier
remains **PARTIALLY VERIFIED**, research-only, and undeployed.

### Latest isolated Frontier checkpoint — 2026-10-28 12:08 UTC

A review of the isolated Reality model tests found all file writes use pytest
temporary roots and their network fixtures are mocked HTTP plus ephemeral
localhost WebSockets. One case signals its own test process and will be
excluded from a bounded run. No test was started because at 12:08:02Z memory
PSI avg10 was 50.74% some / 45.23% full; I/O PSI was 0.84% some / 0.68% full.
About 10 GiB was available, with 3.5/4 GiB swap occupied. A read-only process
listing showed the existing Veritas batch process; it was left untouched.
Frontier remains **PARTIALLY VERIFIED**, research-only, and undeployed.

### Latest isolated Frontier checkpoint — 2026-10-28 12:05 UTC

Code commit 9552db5 corrects the Coinbase source hold message: a reviewed
terms-version acknowledgement alone does not lift the hold; a validated
permission and intended-scope review are still required. The hold and all
probe guards remain active. The focused offline Coinbase module passes
**13/13**; Ruff and format checks pass. No request or held record was accessed.
Strict mypy also passes for the changed adapter module.

At 12:05:41Z before the test, memory PSI avg10 was 0.00%, I/O was 0.61%
some / 0.49% full, and about 10 GiB was available. At 12:06:00Z afterward,
memory remained 0.00%, I/O was 0.72% some / 0.40% full, and about 10 GiB
remained available. Frontier remains **PARTIALLY VERIFIED**, research-only,
and undeployed.

### Latest isolated Frontier checkpoint — 2026-10-28 12:03 UTC

Code/test commit bf9d933 updates the two regression fixtures summarized here.

Two legacy test fixtures were brought into line with existing production
contracts. The Laboratory admission fixture now supplies CPU count and host
load telemetry, and its pressure test sets the normalized host-load metric
that the current fail-closed gate evaluates. The Arena replay fixture now
binds a verified cross-venue relationship to the actual observation IDs pinned
by both synthetic markets.

The scoped legacy slices pass: unit/simulation/property **153/153**,
Laboratory **75/75**, and Arena admission plus Frontier replay/timeline
**30/30**. The latter two were rerun after fixture corrections. Ruff, format,
and whitespace checks pass. Tests used isolated /dev/shm basetemps; no live
source, held capture, production store, or service was accessed.

At 12:03:40Z, host memory PSI avg10 was **54.85% some / 49.81% full** and
I/O PSI was **1.28% some / 1.22% full**. About 10 GiB was available, with
3.5/4 GiB swap already occupied. The combined and broader repository reruns
remain deferred until a fresh sample falls below the 1% I/O admission gate.
Frontier remains **PARTIALLY VERIFIED**, research-only, and undeployed.

### Latest isolated Frontier checkpoint — 2026-10-28 11:38 UTC

Test commit `c6dfff1` adds a Coinbase terms-hold regression against a copied
`CoinbaseSpotConfig`. It checks both adapter and transport constructors refuse
a copy that clears the hold without the exact reviewed terms acknowledgement.
Ruff and `git diff --check` pass; the test has not run.

At `11:38:45Z`, memory PSI avg10 was 35.09% some / 29.50% full and I/O PSI
was 3.88% some / 3.67% full. About 10 GiB was available; host swap was
3.4/4 GiB used. A read-only process inspection found the existing
`veritas_gap_detail_v2_batch.py` process (PID 344473) in D state; it was left
untouched. No test or replay was started under this pressure. The previously
verified 418/418 suite covers product commit `1dd0987`, before this test-only
commit; the full current test tree remains pending. Frontier remains
**PARTIALLY VERIFIED**, research-only, and undeployed.

### Latest isolated Frontier checkpoint — 2026-10-28 11:35 UTC

Code commit `1dd0987` makes adapter resource bounds fail closed after copied
model updates. `AdapterConfig` revalidates against its concrete type, and both
adapter and transport constructors reject malformed configs before use or
HTTP client creation. The adapter module passes **71/71**, collection and
collection-API modules pass **34/34**, and full `tests/frontier` passes
**418/418** in 31.53 seconds wall time. Peak RSS was **379,004 KiB**, with
zero process swaps, filesystem inputs, and socket messages. Ruff, formatting,
strict mypy for nine production modules, and `git diff --check` pass. One
existing Starlette/httpx deprecation warning remains. Tests used tmpfs at
`/dev/shm/midas-frontier-adapter-config-full-20261028T1135Z`.

At the pre-run sample `11:34:58Z`, memory PSI avg10 was 0%, I/O PSI was 0.66%
some / 0.45% full, and about 10 GiB was available. At `11:35:49Z`, memory
PSI remained 0%, I/O PSI was 0.57% some / 0.47% full, and about 10 GiB
remained available. Host swap was 3.4/4 GiB used; the test process used no
swap. No live source, protected capture, or production service was accessed.
Frontier remains **PARTIALLY VERIFIED**, research-only, and undeployed.

### Latest isolated Frontier checkpoint — 2026-10-28 11:31 UTC

Code commit `e26efab` closes a copied execution-assumption gap. A
`model_copy(update=...)` scenario with `fill_fraction=2` previously produced
positions twice the displayed best-ask depth, and both independent audits
marked the result verified. Scenario objects are now reconstructed through
validation at candidate, joint-state, replay, timeline, comparison, and direct
audit boundaries. Invalid assumptions fail closed; direct audit records
incomplete evidence and disables practical eligibility. Economic model v21,
audit v21, replay v20, timeline v2, and discovery comparison v2 pin the
behavior.

The focused affected slices passed **100/100** and full `tests/frontier`
passed **417/417** in 32.02 seconds wall time, with **380,336 KiB** peak RSS,
zero process swaps, zero filesystem input, and zero socket messages. Ruff
check/format, strict mypy for seven production modules, and `git diff --check`
pass. One existing Starlette/httpx deprecation warning remains. Tests used
tmpfs at `/dev/shm/midas-frontier-scenario-integrity-full-20261028T1131Z`.

At the pre-run sample, memory PSI avg10 was 0%, I/O PSI was 0.33% some / 0.16%
full, and about 10 GiB was available. At `11:31:38Z`, memory PSI remained 0%,
I/O PSI was 0.72% some / 0.71% full, and about 10 GiB remained available.
Host swap was already 3.4/4 GiB used; this test process used no swap. No live
source, protected capture, or production service was accessed. Frontier
remains **PARTIALLY VERIFIED**, research-only, and undeployed.

### Latest isolated Frontier checkpoint — 2026-10-28 11:24 UTC

Code commit `ac85442` closes a copied snapshot-timestamp gap. Full book
snapshots, including receipt/exchange times and provenance, are revalidated at
candidate generation, independent audit, and replay intake. Replay validates
before deriving its default cutoff, so a naive copied `received_at_utc` is
rejected rather than reaching date arithmetic. Economic model v20, audit v20,
and replay v19 pin the changed rules.

The focused book-integrity slice passes **10/10**. Full `tests/frontier`
passes **415/415** in 32.27 seconds wall time, with **378,208 KiB** peak RSS,
zero test-process swaps, zero filesystem input, and zero socket messages. Ruff
check/format, strict mypy for five production modules, and `git diff --check`
pass. One existing Starlette/httpx deprecation warning remains. Tests used
isolated tmpfs storage at
`/dev/shm/midas-frontier-book-structure-final-20261028T1124Z`.

At `11:24:07Z`, about 10 GiB was available, memory PSI avg10 was 0%, and I/O
PSI was 0.29% some / 0.05% full. At `11:24:44Z`, about 10 GiB remained
available, memory PSI avg10 was 0%, and I/O PSI was 0.32% some / 0% full. No
live source, protected capture, or production service was accessed. Live
cross-venue validation, broader MIDAS regression, production recovery, and
deployment remain open. Frontier remains **PARTIALLY VERIFIED**, research-only,
and undeployed.

### Latest isolated Frontier checkpoint — 2026-10-28 11:21 UTC

Code commit `da347a4` closes a copied nested-market integrity gap. A duplicate
instrument ID bypassed `FrontierMarket` constructor validation and caused the
multi-outcome candidate generator to raise during sensitivity construction.
Markets are now reconstructed and validated at candidate generation,
independent audit, and replay boundaries. Malformed copies fail closed as
incomplete evidence or rejected replay input. Economic model v19, audit v19,
and replay v18 pin the behavior.

The final full `tests/frontier` suite passes **414/414** in 31.40 seconds wall
time, with **377,768 KiB** peak RSS, zero test-process swaps, zero filesystem
input, and zero socket messages. Ruff check/format, strict mypy for five
production modules, and `git diff --check` pass. One existing Starlette/httpx
deprecation warning remains. Tests used isolated tmpfs storage at
`/dev/shm/midas-frontier-market-copy-final2-20261028T1121Z`.

At `11:20:51Z`, about 10 GiB was available, memory PSI avg10 was 0%, and I/O
PSI was 0.34% some / 0% full. At `11:21:37Z`, about 10 GiB remained available,
memory PSI avg10 was 0%, and I/O PSI was 0.64% some / 0.44% full. No live
source, protected capture, or production service was accessed. Live
cross-venue validation, broader MIDAS regression, production recovery, and
deployment remain open. Frontier remains **PARTIALLY VERIFIED**, research-only,
and undeployed.

### Latest isolated Frontier checkpoint — 2026-10-28 11:15 UTC

Code commit `1f6bd64` closes a copied joint-state mapping identity gap. Runtime
use now reconstructs and revalidates the bounded mapping definition and checks
its canonical content digest during candidate generation, independent audit,
and replay. The fixture regression confirms stale content with the old ID
produces no candidate, makes an existing candidate audit incomplete, and is
rejected by replay. Economic model v18, audit v18, and replay v17 pin the
changed rules. A valid mapping remains an unauthenticated semantic assertion.

The focused joint-state suite passes **11/11**. Full `tests/frontier` passes
**413/413** in 32.26 seconds wall time, with **379,304 KiB** peak RSS, zero
test-process swaps, zero filesystem input, and zero socket messages. Ruff
check/format, strict mypy for five production modules, and `git diff --check`
pass. One existing Starlette/httpx deprecation warning remains. Tests used
isolated tmpfs storage at
`/dev/shm/midas-frontier-joint-map-final-20261028T1115Z`.

At `11:14:51Z`, about 10 GiB was available, memory PSI avg10 was 0%, and I/O
PSI avg10 was 0%. At `11:15:29Z`, about 10 GiB remained available, memory PSI
avg10 was 0%, and I/O PSI was 0.03% some / 0% full. No live source, protected
capture, or production service was accessed. Live cross-venue validation,
broader MIDAS regression, production recovery, and deployment remain open.
Frontier remains **PARTIALLY VERIFIED**, research-only, and undeployed.

### Latest isolated Frontier checkpoint — 2026-10-28 11:12 UTC

Code commit `435153d` closes a copied-book depth-integrity gap. Runtime book
checks now reject duplicate prices, non-finite or negative prices,
non-finite/non-positive quantities, malformed levels, and naive level
timestamps in candidate generation, independent audit, and deterministic
replay. Economic model v17, audit v17, and replay v16 pin the changed rules.

Focused adversarial tests passed **8/8**. The full `tests/frontier` suite
passes **412/412** in 31.33 seconds wall time, with **378,608 KiB** peak RSS,
zero test-process swaps, zero filesystem input, and zero socket messages.
Ruff check/format, strict mypy for five production modules, and
`git diff --check` pass. One existing Starlette/httpx deprecation warning
remains. Tests used isolated tmpfs storage at
`/dev/shm/midas-frontier-book-depth-final-20261028T1112Z`.

At `11:10:34Z`, about 10 GiB was available, memory PSI avg10 was 0%, and I/O
PSI was 0.06% some / 0.01% full. At `11:12:10Z`, about 10 GiB remained
available, memory PSI avg10 was 0%, and I/O PSI was 0.12% some / 0% full.
No live source, protected capture, or production service was accessed. Live
cross-venue validation, broader MIDAS regression, production recovery, and
deployment remain open. Frontier remains **PARTIALLY VERIFIED**, research-only,
and undeployed.

### Latest isolated Frontier checkpoint — 2026-10-28 11:04 UTC

Test commit `d44bab0` adds end-to-end evidence for duplicate JSON-key source
failures. The API returns `DUPLICATE_JSON_KEY`, persists the exact bounded
response in a `source_failure` observation, and serves the raw body, failure
stage, and code from the evidence endpoint without adding a normalized market.
Full `tests/frontier` passes **404/404** in 31.12 seconds wall time, with
**378,492 KiB** peak RSS and zero test-process swaps. Ruff, formatting, strict
mypy for six changed production modules, and `git diff --check` pass. One
existing Starlette/httpx deprecation warning remains.

At `11:03:02Z`, memory and I/O PSI avg10 were 0% and about 10 GiB was
available; host swap was already 3.5/4 GiB used. At `11:03:37Z`, memory PSI
was 0%, I/O PSI was 0.03% some / 0% full, about 10 GiB was available, and the
test process had used no swaps. No live source or protected capture was
accessed. Live multi-venue validation, broader MIDAS regression, production
recovery, and deployment remain open. Frontier remains **PARTIALLY VERIFIED**,
research-only, and undeployed.

### Latest isolated Frontier checkpoint — 2026-10-28 11:02 UTC

Commit `ff522e9` advances the economic model to v16 so candidate and replay
identities pin logical-implication verifier v3 acceptance. A regression
confirms prior v2 implication evidence remains readable but yields incomplete
evidence with no position until re-reviewed. The focused economics suite
passes **7/7**; full `tests/frontier` passes **404/404** in 31.22 seconds wall
time, with **385,644 KiB** peak RSS and zero test-process swaps. Ruff,
formatting, strict mypy across six changed production modules, and
`git diff --check` pass. One existing Starlette/httpx deprecation warning
remains.

At `11:01:11Z`, memory and I/O PSI avg10 were 0%, about 10 GiB was available,
and host swap was already 3.5/4 GiB occupied. At `11:01:46Z`, memory PSI was
0%, I/O PSI was 0.01% some / 0% full, about 10 GiB was available, and the test
process used no swaps. No live source or protected capture was accessed. Live
multi-venue validation, broader MIDAS regression, production recovery, and
deployment remain open. Frontier remains **PARTIALLY VERIFIED**, research-only,
and undeployed.

### Latest isolated Frontier checkpoint — 2026-10-28 10:59 UTC

Commit `63c2d74` rejects duplicate relationship IDs before deterministic
replay candidate generation; a fixture had previously produced two rows with
one candidate identity. Commit `0dbea9c` rejects duplicate JSON object keys at
any depth as `DUPLICATE_JSON_KEY`, retaining bounded raw-response evidence and
preventing ambiguous fields from reaching normalization. Focused regressions
passed **1/1** and **2/2**; full `tests/frontier` passes **403/403** in 30.92
seconds wall time, with **376,780 KiB** peak RSS and zero test-process swaps.
Ruff, formatting, strict mypy, and `git diff --check` pass. One existing
Starlette/httpx deprecation warning remains.

At `10:58:31Z`, memory and I/O PSI avg10 were 0%, about 10 GiB was available,
and host swap was already 3.5/4 GiB occupied. At `10:59:07Z`, PSI remained
0%, about 10 GiB was available, and the test process used no swaps. No live
source or protected capture was accessed; the saved public capture remains
untouched. Live multi-venue evidence, broader MIDAS regression, production
recovery, and deployment remain open. Frontier remains **PARTIALLY VERIFIED**,
research-only, and undeployed.

### Latest isolated Frontier checkpoint — 2026-10-28 10:56 UTC

Commit `3097082` closes a logical-implication verifier gap reproduced with
direct Pydantic `model_copy(update=...)`: duplicate payoff states or native
instrument IDs could produce a VERIFIED relationship. Logical verifier v3
rejects those markets and requires unique outcome identities; independent
audit v16 requires current v3 evidence. Old v2 relationships remain readable
but do not validate new audited candidates. The focused implication and
relationship suites pass **70/70**; full `tests/frontier` passes **400/400** in
31.11 seconds wall time, with **378,052 KiB** peak RSS and zero test-process
swaps. Ruff, formatting, strict mypy, and `git diff --check` pass. One existing
Starlette/httpx deprecation warning remains.

At `10:55:13Z`, memory PSI avg10 was 0%, I/O PSI avg10 was 0.01%, and about 10
GiB was available; the host already had 3.5/4 GiB swap occupied. At
`10:55:57Z`, both PSI readings were 0%, about 10 GiB was available, and the
test process had used no swaps. No live source, protected capture, service, or
Arena job was used. Semantic assertions remain self-attributed; live
cross-venue evidence, broader MIDAS regression, production recovery, and
deployment remain open. Frontier remains **PARTIALLY VERIFIED**, research-only,
and undeployed.

### Latest isolated Frontier checkpoint — 2026-10-28 10:52 UTC

Commit `3dc3721` closes malformed in-memory market-object cases where direct
`model_copy(update=...)` bypassed field validators. Same-payoff verifier v6
and independent audit v15 reject duplicate payoff states, native instruments,
outcomes, and payout rows; the independent audit checks even unselected
instruments. Four verifier cases and one audit case cover copied corruption.
The focused module passes **63/63** and full `tests/frontier` passes **399/399**
in 31.07 seconds wall time, with **379,224 KiB** peak RSS and zero test-process
swaps. Ruff, formatting, strict mypy, and `git diff --check` pass. One existing
Starlette/httpx deprecation warning remains.

At `10:51:36Z`, memory and I/O PSI avg10 were 0% and about 10 GiB was
available; the host already had 3.5/4 GiB swap occupied. At `10:52:24Z`, PSI
remained 0%, about 10 GiB was available, and the test process had used no
swaps. No live source, protected capture, service, or Arena job was used.
Semantic assertions remain self-attributed, the captured Polymarket payoff and
resolution remain unverified, and live cross-venue matching, broader MIDAS
regression, production recovery, and deployment remain open. Frontier remains
**PARTIALLY VERIFIED**, research-only, and undeployed.

### Latest isolated Frontier checkpoint — 2026-10-28 10:46 UTC

Commit `7ebe56a` binds same-payoff relationship review evidence to the two
distinct pinned market observations and the replay cutoff. Verifier v5 rejects
missing/shared evidence and assertions predating either source; independent
audit v14 rejects late attestations and older verifier versions. Four new
regressions cover these boundaries. The full `tests/frontier` suite passes
**394/394** in 29.62 seconds, with **378,716 KiB** peak RSS and zero swaps.
Ruff, formatting, strict mypy for the three changed production modules, and
`git diff --check` pass. One existing Starlette/httpx deprecation warning
remains.

External semantic assertions and reviewer labels remain self-attributed; live
cross-venue equivalence is not established. The captured Polymarket payoff and
resolution remain unverified. Source-use, broader MIDAS regression,
production-recovery, and deployment gates remain open. Frontier is still
**PARTIALLY VERIFIED**, research-only, and undeployed.

### Latest isolated Frontier checkpoint — 2026-10-28 10:35 UTC

Commit `f591185` fixes verified-payoff ambiguity from duplicate payout rows:
the same state can no longer appear twice in an instrument vector, and verified
markets require every state exactly once. The focused regression passed **3/3**;
the full Frontier suite passed **390/390** in 29.51 seconds. Strict mypy for
`models.py`, Ruff, and formatting passed. Memory PSI avg10 was 0% and I/O PSI
avg10 was 0.04% some / 0% full at `10:34:45Z`. The captured market's own payoff
remains unverified; no live cross-venue evidence or production transition was
created. Frontier remains **PARTIALLY VERIFIED**.

### Latest isolated Frontier checkpoint — 2026-10-28 10:30 UTC

The fixture-backed Kalshi fee-sensitivity module passed **21/21**, including
property-based fee and independent-audit comparisons. The model continues to
classify the public-derived schedule as an estimate and separates account
precision cases. No live fee request or code change was made; account-specific
applicability remains unknown. Memory PSI avg10 was 0% and I/O PSI avg10 was
0.02% some / 0% full at `10:29:58Z`. Source authorization, genuine cross-venue
economics, and production gates remain open; Frontier is **PARTIALLY VERIFIED**.

### Latest isolated Frontier checkpoint — 2026-10-28 10:28 UTC

The offline FX and venue-capital review found no code defect. The focused
conversion/carry suites passed **45/45** in 0.54 seconds; memory and I/O PSI
avg10 were 0% at `10:28:32Z`. FX rates retain explicit orientation and
venue-local balances, while carry uses verified per-market settlement times
and an explicit release delay. These remain hypothetical assumptions, not
conversion, collateral, or execution evidence. Source-use, full MIDAS regression,
production recovery, and deployment gates remain open. Frontier is still
isolated, research-only, undeployed, and **PARTIALLY VERIFIED**.

### Latest isolated Frontier checkpoint — 2026-10-28 10:26 UTC

Functional commit `be31236` adds the immutable observation ID to Frontier's
evidence panel. Afterward, all 47 frontend unit tests, TypeScript, scoped
ESLint/Prettier, and the production build passed. A bounded Chromium check
against a temporary copy of the genuine Polymarket capture displayed market
`2589810`, its one-sided book, and the full book observation ID; its saved
evidence endpoint returned HTTP 200. No source operation or external request
was made. Both local listeners were stopped and the original capture hashes
still match. Memory PSI avg10 was 0%; I/O PSI avg10 was 0.02% some/full at
`10:26:49Z`. The Vite build still reports a 544.51 kB Chart/ECharts chunk.
Frontier remains isolated, research-only, undeployed, and **PARTIALLY VERIFIED**.

### Latest isolated Frontier checkpoint — 2026-10-28 10:22 UTC

The code/test tree remains at `429f690` with documentation-only commits after
it. A bounded browser smoke rendered the genuine captured Polymarket market,
one-sided book, and immutable response panel through the isolated local API;
the saved observation endpoint returned HTTP 200. No external request or
source-probe/collection POST was made. API/Vite listeners are stopped. Hashes
for the two SQLite stores and capture manifest still match. At `10:22:00Z`,
memory and I/O PSI avg10 were both 0%; no broad suite, build, or long experiment
was started. The untracked public capture remains preserved; the separate
Deribit screen is now documented. Frontier remains research-only, isolated,
undeployed, and **PARTIALLY VERIFIED**.

### Latest isolated Frontier checkpoint — 2026-10-28 10:17 UTC

The code/test tree includes `429f690`; later commits update documentation only.
The hash-validated Polymarket capture remains the only untracked data, and the
local API/Vite listeners are stopped. Deribit was screened from
official API and terms sources and deferred pending written data-use approval;
no request or adapter was added. At `10:17:35Z`, memory PSI avg10 was 9.69% some
/ 6.56% full and I/O PSI avg10 was 0%. Defer tests, builds, and browser work
until both avg10 values are below 1%. See the current acceptance matrix in the
[Frontier engineering report](frontier/FRONTIER_ENGINEERING_REPORT.md).
Frontier remains research-only, isolated, undeployed, and
**PARTIALLY VERIFIED**.

### Latest isolated Frontier checkpoint — 2026-10-28 09:06 UTC

A short-lived local Uvicorn API ran in demo mode with its writable roots
isolated under `/tmp/midas-frontier-live-ui-20261028-0905/`; all source probes
were explicitly disabled. Its real Frontier market and book GET routes
returned the preserved Polymarket records and observation IDs with a
recorded-only disclosure. Hashes of both SQLite stores and the capture manifest
were unchanged after shutdown. Health reported `live_execution: false`. Vite
was started and stopped against this API, but no browser was launched.

At `09:05:51Z`, I/O PSI avg10 was 0.99% some/full; at `09:06:50Z`, it was 1.35%
some/full while memory PSI avg10 was 0%. No cause is attributed. Defer browser
rendering until a fresh sample clears the resource gate. Frontier remains
research-only and **PARTIALLY VERIFIED**.

### Full Frontier regression checkpoint — 2026-10-28 09:03 UTC

After capture-root isolation commit `429f690`, the complete `tests/frontier`
suite passed **387/387** in one process in 29.38 seconds pytest time. The run
used `/dev/shm/midas-frontier-regression-20261028T0901Z`; peak RSS, swaps, and
filesystem input were not measured. The existing Starlette/httpx deprecation
warning remains. It used fixtures and temporary state only and accessed no
live source, production service, protected store, or Arena job.

PSI samples through `09:01:26Z` were below the 1% avg10 gate. Memory PSI rose
to 54.19% some / 48.45% full at `09:02:39Z`, with cause unknown. At `09:03:33Z`,
memory PSI avg10 was 0.93% some / 0.79% full and I/O PSI avg10 was 0.79% some /
0.75% full. Recheck before the next broad test/build. Live cross-venue
validation, full MIDAS regression, production recovery, and deployment remain
open. Frontier remains research-only, isolated, and **PARTIALLY VERIFIED**.

### Isolated Frontier live capture — 2026-10-28 08:57 UTC

One explicitly bounded, unauthenticated Polymarket Gamma listing request and
one CLOB book GET completed against allowlisted public HTTPS hosts. The single
open binary market is preserved with its raw response, normalized record,
collection journal, row hashes, and a hash-bearing manifest under the isolated
Frontier worktree's `data/frontier-public-probes/` directory. Its payoff and
resolution remain unverified. The Yes book has five asks, no bids, and a source
timestamp 33.4 seconds before local receipt by direct clock comparison; this
does not establish synchronized clocks or executability. No other venue was
accessed, and no cross-venue relationship or opportunity is claimed. The
local read-only Frontier markets/books API returned the two saved rows with
observation IDs intact and labeled them as recorded evidence only.

Commit `429f690` extends the Frontier Python test guard so automated tests
cannot read or write either live-capture root; its focused suite passes **3/3**.
Live source holds for Kalshi/Kraken/Coinbase, broader MIDAS regression,
production recovery, and deployment remain open. Frontier remains isolated,
research-only, and **PARTIALLY VERIFIED**. At `08:57:53Z`, memory PSI avg10 was
50.11% some / 43.78% full and I/O PSI avg10 was 1.09% some / 0.80% full. No
cause is attributed; further resource-bearing checks wait for a fresh sample
under the documented gate.

### Latest isolated Frontier checkpoint — 2026-10-28 08:47 UTC

The full Frontier Python suite now passes **386/386** after the collection,
FX-integrity, and timeline-timestamp changes. It ran on tmpfs in 29.38 seconds
of pytest time (30.82 seconds wall), peaked at 378,704 KiB RSS, used no swap,
and recorded zero filesystem input. After final formatting/type cleanup, the
affected collection/API, FX, and timeline selection passed **57/57**; strict
mypy, Ruff check/format, and `git diff --check` pass.

Collection run specs now preserve allowlisted Kraken pair and Coinbase product
and terms-ack config across restart. Verified FX sensitivities bind the total
conversion fee to terminal P&L deductions. Timeline coverage verifies that a
quote cannot be used before local receipt and that exchange-time skew remains
visible to the timing audit. At `08:47:41Z`, host memory PSI avg10 rose to
49.58% some / 45.01% full; no further broad test or build was started. No live
source, protected service, or historical evidence was touched. Frontier remains
**PARTIALLY VERIFIED**.

### Latest isolated Frontier checkpoint — 2026-10-28 08:37 UTC

The seeded browser integration was rerun after the latest chart changes and
passes **2/2**: saved Frontier history/replay through the local API, and a
fixture Arena discovery artifact through storage into Laboratory. The runner
created 21 labeled fixture captures and one fixture-only Arena job in an
isolated temporary root. The full default suite remains **17 passed, 2
expected seeded-only skips**; web unit tests pass **47/47**, with full-project
lint, formatting, TypeScript, and build already passing. No live source,
production service, or protected store was accessed.

The Frontier Python suite remains **379/379**. Cross-venue source permission,
full MIDAS regression, production recovery, and deployment remain open. Frontier
is **PARTIALLY VERIFIED**, research-only, isolated, unmerged, and undeployed.

### Latest isolated Frontier checkpoint — 2026-10-28 08:34 UTC

The complete default browser suite was rerun against the latest chart
implementation and observer-fallback test: **17 passed, 2 expected seeded-only
skips**. The complete web unit suite passes **47/47**; full-project ESLint,
Prettier, TypeScript, and production build pass. Playwright used only isolated
loopback demo services and temporary state; it left no test server listening.
The existing seeded Frontier/Arena browser run remains **2/2**.

The latest production Chart chunk is **544.51 kB** minified (**186.79 kB gzip**)
and remains deferred until its viewport region approaches view. This changes
load timing and reuses mounted chart instances; it does not reduce total bundle
size. Frontier's Python suite remains **379/379**. Live source validation,
full MIDAS regression, production recovery, and deployment remain open.
Frontier is **PARTIALLY VERIFIED** and remains isolated, research-only,
unmerged, and undeployed.

### Latest isolated Frontier checkpoint — 2026-10-28 08:32 UTC

Test commit `c04f699` adds the missing-browser-capability check for deferred
charts. `DeferredChart` now has passing coverage for both delayed loading with
`IntersectionObserver` and immediate loading when the API is unavailable. The
full web unit suite passes **47/47** across nine files. The production build
and chart-specific browser checks remain passing from the latest code change;
the full default browser run at the prior viewport-loading checkpoint passed
17 cases with two expected seeded-only skips.

Frontier Python remains 379/379. Cross-venue live validation, held-source
permissions, full MIDAS regression, production recovery, and deployment remain
open. Project status is **PARTIALLY VERIFIED**; no source, protected service,
or historical evidence was changed.

### Latest isolated Frontier checkpoint — 2026-10-28 08:31 UTC

Code commit `6c13b47` updates ECharts options on the mounted chart instance
instead of disposing and reinitializing the chart after every option refresh.
The chart lifecycle unit test verifies one initialization, updated options, and
disposal on unmount. The web unit suite passes **46/46**, the production build
and scoped lint/format pass, and post-change browser smoke plus deferred-load
checks pass **2/2**. The preceding complete default browser suite passed 17
cases with two expected seeded-only skips.

The prior `c4adac6` change defers the Chart payload until the viewport observer
nears it. The latest 544.51 kB minified chart chunk (186.79 kB gzip) is unchanged
in size, but now loads only when needed; mounted charts reuse their instance.
The Frontier Python suite remains 379/379. Full MIDAS regression, live
multi-venue validation, held-source permissions, and production readiness
remain open. Frontier is **PARTIALLY VERIFIED**, isolated, research-only,
unmerged, and undeployed. No protected service or historical evidence changed.

### Latest isolated Frontier checkpoint — 2026-10-28 08:28 UTC

Code commit `c4adac6` defers the shared ECharts Chart module in Mission
Control, Arena, and Reality until its reserved viewport area approaches view.
The focused Playwright network assertion verifies zero Chart module requests
while the chart is below the viewport, followed by one request and a rendered
chart after scrolling. The overall 544.41 kB Chart chunk is unchanged; this
defers loading rather than reducing bundle size. The frontend suite passes
45/45 unit tests, 17 default Playwright tests with two seeded-only skips, build,
TypeScript, lint, and formatting. The separately seeded Frontier/Arena browser
checks remain 2/2.

The isolated Frontier Python suite remains 379/379. The complete MIDAS
regression, live multi-venue validation, held-source permissions, and production
readiness remain open. No live cross-venue equivalence or economically
eligible opportunity is claimed. Frontier remains **PARTIALLY VERIFIED**,
research-only, unmerged, and undeployed; no protected service or historical
evidence was changed. See the [engineering report](frontier/FRONTIER_ENGINEERING_REPORT.md)
and [mission ledger](frontier/FRONTIER_MISSION_LEDGER.md) for measurements.

### Latest isolated Frontier checkpoint — 2026-10-28 08:23 UTC

The exact `tests/frontier` suite passes **379/379** in a single process using
the documented tmpfs workflow (29.51 seconds pytest time, 378,216 KiB peak RSS,
zero swaps and zero filesystem input). Latest bounded web evidence is 44/44
unit tests, TypeScript, ESLint, Prettier, production build, 16 default browser
cases with two expected seeded-only skips, and 2/2 seeded Frontier/Arena cases
on disposable services and stores. The full MIDAS regression remains
unverified because this selected tree lacks `midas.reality.recovery`, imported
by `tests/test_reality_full_scale_validation.py`; other Reality lineages have
incompatible dependencies and were not copied into this branch.

Kalshi, Kraken, and Coinbase remain quarantined from live probes and
research/replay routes. The test harness rejected an attempted held-capture
read, and no workaround was used. Synthetic relationship tests do not establish
live cross-venue equivalence. Frontier is **PARTIALLY VERIFIED**, research-only,
isolated, unmerged, and undeployed. No protected service or historical
evidence was changed. See the [Frontier engineering report](frontier/FRONTIER_ENGINEERING_REPORT.md)
and [mission ledger](frontier/FRONTIER_MISSION_LEDGER.md) for dated evidence
and remaining gates.

### Latest isolated Frontier checkpoint — 2026-10-28 04:07 UTC

Frontier remains on `/home/charlie/midas-frontier`, branch
`codex/frontier-20261026`, separate from the `main` services and protected
Reality worktree. Code commit `fb6d800` now leaves Polymarket event identity
unknown when Gamma detail omits an explicit event; the original legacy
normalizer remains unchanged for other MIDAS callers, and historical capture
rows are not rewritten.

The full Frontier Python regression passes **352/352**, the full Mission
Control web unit suite **40/40**, and Frontier browser E2E **6/6** against
temporary local services and data. Selected Arena discovery/replay/timeline
and job tests pass **38/38** with temporary roots. Strict typing for the API
and affected adapter models passes, and TypeScript plus the production Vite
build completes to a temporary directory. The existing Chart chunk advisory
remains. The bounded detail route's generated OpenAPI description now records
its listing binding and evidence limits. One bounded Polymarket Gamma detail
request was captured and hash-checked, but it
does not establish event membership, exhaustive outcomes, payoff, settlement,
or an opportunity. No Kalshi, Kraken, or Coinbase live request was made under
their current source-use holds.
The focused legacy integration regression confirms other MIDAS callers retain
their existing local `market:<id>` fallback behavior. The complete legacy
adapter integration file passes **10/10** with fixtures and local transports.

At the post-build sample `2026-10-28T04:06:58Z`, memory PSI avg10 was 0.08%
some/full with about 10 GiB available and no shared Arena lock holder. No
protected service, production configuration, historical evidence, or Reality
recording was changed. The post-Arena sample at `2026-10-28T04:11:18Z` still
had memory PSI avg10 0.00% some/full, I/O PSI avg10 10.31% some / 9.83% full,
about 9 GiB available, and no shared lock holder. At the later
`2026-10-28T04:12:29Z` check, memory PSI avg10 was 38.86% some / 33.25% full
and external Veritas PID 4166289 held the shared lock; it was left untouched.
The exact captured Gamma detail body later replayed offline through the
corrected adapter with no public network call: it retained the market title
and raw hash and now yields no native event ID; the two-row capture store was
unchanged. Frontier is **PARTIALLY VERIFIED**, research-only,
isolated, unmerged, and undeployed. See the [Frontier mission ledger](frontier/FRONTIER_MISSION_LEDGER.md),
[engineering report](frontier/FRONTIER_ENGINEERING_REPORT.md), and
[source terms review](frontier/SOURCE_DATA_TERMS_REVIEW_2026-10-27.md) for the
exact measurements and blocker ledger.

### Hypothetical replay P&L disclosure — 2026-10-28 02:57 UTC

Frontier code commit `3af51c0589c9550ff5bbf9333e24a818e75041c0` labels the
candidate's worst-case values as modeled P&L and states that replay outcomes do
not establish fills, venue access, or realized profit. The focused component
test, saved-artifact Playwright fixture, and TypeScript/Vite build pass. The
browser test uses intercepted fixture data, and the build retains the existing
544.41 kB Chart chunk advisory. After the build, PSI avg10 reached **29.83%
some / 24.02% full**; further heavy work is deferred pending a fresh sample.
Frontier remains **PARTIALLY VERIFIED**.

### Arena discovery worker dispatch containment — 2026-10-28 02:56 UTC

Frontier code commit `9b0b28f89832799fdcc8ff66f117e156d133be7c` restricts
launched `frontier_discovery` Arena jobs to AF_UNIX socket families and keeps
the 300-second, 512-MiB, half-CPU, nice-15, idle-I/O bounds. A child-process
fixture completed through the durable Arena job dispatcher and its result
passed artifact verification. The related Arena supervision regression passes
**21/21** at **193,632 KiB peak RSS**, zero swaps, and zero socket messages.
The command test mocks `systemd-run` and admission, and the worker fixture uses
a temporary root; actual systemd/cgroup execution and host-gated admission
remain unverified. No production or protected service was changed. Frontier
remains undeployed and **PARTIALLY VERIFIED**.

### Saved Arena candidate evidence UI — 2026-10-28 02:52 UTC

Frontier code commit `4c40c7f4403d7571ae52849e6c4d10c81fa4d5c1` adds
read-only detail inspection for candidates in saved Arena discovery-scope
artifacts. The UI matches details to the selected scope's replay runs and
summary identity/classification/audit/worst-case fields, preserves exact
decimal strings, shows legs, observation IDs, terminal outcomes, timing,
independent audit, assumptions, and hashes, and caps rendering at 50 per
scope. The web unit suite passes **40/40**, TypeScript and the production build
pass, and a fixture-backed browser path passes **1/1**. Vite retains its
existing **544.41 kB** Chart chunk advisory. The browser artifact is intercepted
fixture data; no Arena worker or live exchange data was used. Project Frontier
remains **PARTIALLY VERIFIED**, with supervisor execution, live cross-venue
matching, source-use gates, and deployment still unresolved.

### Joint-state search differential and bounded performance — 2026-10-28 02:16 UTC

Performance commit `bc8d073` changes joint-state subset evaluation to cache
each instrument's asserted-state payoff vector and incrementally sum subset
vectors in ascending instrument order. This preserves Decimal summation order
while avoiding repeated payoff dictionary construction. Test commit `29f1a5b`
adds a seeded 48-case differential test against an independent exhaustive
subset oracle and a reproducible 12-instrument/64-state benchmark. The oracle
checks all three constant-payout baskets for each two-market fixture and
independently audits every generated candidate.

The full Frontier Python suite passes **343/343** in 53.88 seconds pytest time
(55.23 seconds process wall) at **366,360 KiB peak RSS**, with zero swaps. One
existing Starlette/httpx TestClient deprecation warning remains. Ruff and strict
scoped mypy for `joint_economics.py` pass. The synthetic max-bound benchmark
examined **4,095 subsets**, of which **3,969** covered both markets and had the
fixture's constant payout. Three timed runs with one returned candidate had a
**0.101767-second median** and **0.104521-second maximum**, at **70,576 KiB
peak RSS** for the complete process, with zero swaps. A separate run returning
eight candidates took **0.174308 seconds**; peak RSS was **71,460 KiB**.
Before the optimization, the one-candidate run measured a **5.122457-second
median** at **38,624 KiB peak RSS**. The optimized one-candidate median is about
50 times lower with about 32 MiB more peak RSS. These are synthetic code-path
measurements, not market latency or economic evidence.

At the post-suite sample, PSI `avg10` was **0.00%**, `avg60` **4.36%**, and
about **10 GiB** was available; swap remained **3.7 GiB used**. No source,
protected service, or production store was accessed. Project Frontier remains
**PARTIALLY VERIFIED**: live semantic matching, source permission, economic
feasibility, sustained collection, and deployment gates remain open.

### Conditional multi-market joint-state basket and browser flow — 2026-10-28 02:03 UTC

Code commit `4bd3b7f2636d5cd8d069fb2e2b2e97188ad68247` adds a bounded
all-long constant-payout basket over an explicit shared-state map for two to
four stored event markets. The replay and map are versioned and content-hashed;
the independent audit recomputes the arithmetic while preserving each leg's
native quantity unit. The map remains an unauthenticated external assertion,
so any positive result stays conditional and practical eligibility is false.
The API reads saved observations only, requires the assertion timestamp to
postdate selected metadata, and makes no source request. Mission Control
contains an explicit mapping editor.

Follow-up test commit `b0f38c2` adds the explicit joint-state submission flow
to `apps/web/e2e/frontier.spec.ts` using intercepted, labeled fixture data.

The focused Frontier regression passed **152 tests**; the full Frontier Python
suite then passed **342/342** in 53.70 seconds (55.06 seconds process wall) at
**368,788 KiB peak RSS**, with zero swaps. The full web unit suite passed
**40/40**, TypeScript passed, and the production build transformed
**2,228 modules** in **4.76 seconds** (13.18 seconds process wall time) at
**713,040 KiB peak RSS**, with zero swaps. The existing **544.41 kB** chart
chunk advisory remains. The full Frontier Playwright spec passes **5/5** in
13.7 seconds (14.52 seconds process wall) at **197,060 KiB peak RSS**, with
zero swaps. A new fixture-only browser flow checks explicit projection
submission, a server-derived mapping ID, the conditional result, and no venue
probe. All browser runs use loopback demo services and temporary storage. Ruff
and scoped strict mypy for the changed
Frontier core modules pass. A broader mypy invocation still reports 14
diagnostics in imported pre-existing Veritas/Arena modules, with none in the
changed Frontier API router.

Immediately after the full Frontier Python suite and before the browser run,
memory PSI `avg10` was **0.00%** and `avg60` **0.64%**, with about **10 GiB
available**. After the browser run PSI rose to `avg10=45.36%` and
`avg60=26.91%`, with **9.7 GiB available**; swap remained **3.7 GiB used** and
the browser process itself did not swap. Defer further heavy checks until host
pressure subsides. These short checks establish neither sustained capacity nor
production readiness. No live venue validation, service modification, or
deployment was performed. General multi-market solving, semantic
authentication of state maps, live cross-venue validation, and production
gates remain open; Project Frontier is **PARTIALLY VERIFIED**.

### Production web build and complete current frontend checks — 2026-10-28 01:29 UTC

The current web revision passes the full unit suite (**40/40**), isolated
Frontier browser spec (**4/4**), and `corepack pnpm --dir apps/web build`
(TypeScript plus Vite). The build transformed 2,228 modules and used **647,704
KiB peak RSS** in 12.93 seconds wall time, with zero swaps. Vite retains the
existing **544.41 kB** chart-chunk advisory. Playwright used only loopback demo
services and temporary research storage. No production deployment occurred.
Project Frontier remains **PARTIALLY VERIFIED**; multi-market joint-state
composition, live cross-venue validation, long-horizon source-quality evidence,
and deployment gates remain open.

### Varied subset shapes and frontend regression — 2026-10-28 01:27 UTC

Benchmark commit `8f2d22fa7bc37ac806d070403d122d941dc226a8` measures four
synthetic workload shapes. A 3-instrument/3-state case returned its one valid
basket in a **0.000928 second median**. At the 12-instrument/16-state ceiling,
the 11-basket case took **0.091870 seconds median**, the zero-basket case
**0.072525 seconds**, and the dense 4,095-basket case returned the 32-result
cap in **0.343868 seconds**. All cases and the reproduction command are in the
latest mission-ledger checkpoint; they do not represent exchange workloads.

After the payoff-basket UI change, the complete web unit suite passed **40/40**
and the isolated Frontier Playwright spec passed **4/4**. Peak RSS was 310,652
KiB and 192,060 KiB respectively; neither run swapped. Mission Control is
verified on the current frontend revision, but Frontier remains undeployed and
overall status is **PARTIALLY VERIFIED**. General multi-market joint-state
composition and its independent audit remain open.

### Bounded payoff-basket ceiling benchmark — 2026-10-28 01:22 UTC

Harness commits `447c85a` and `c1c58ad` add and clarify a reproducible
synthetic benchmark for the configured search ceiling: twelve instruments,
sixteen states, all 4,095 non-empty subsets qualifying, and 32 returned
candidates. Five measured calls after a warm-up had **0.344171 seconds
median** and **0.355593 seconds maximum**; the whole process used **49,792 KiB
peak RSS** and 2.37 seconds wall time. Inputs explicitly identify synthetic
all-state claims that pay one unit in every state to maximize the number of
qualifying subsets. This bounds the implemented search cost on one host; it is
not a representative market workload or an economic finding.
The script is [benchmark_payoff_basket_search.py](/home/charlie/midas-frontier/tests/frontier/benchmark_payoff_basket_search.py).

### Bounded event payoff-basket research — 2026-10-28 01:20 UTC

Commit `d16259422902bc4acd75cb45e0ced6eb8e186904` adds bounded search for
constant-payout long baskets over non-one-hot contracts in one verified
exhaustive event market. The search handles at most twelve instruments,
3–16 terminal states, and 4,095 non-empty subsets, returning eight ranked
candidates by default. Replay preserves the existing one-hot family, and the
new candidate family reaches the independent audit, which rechecks the
constant positive terminal payout from pinned contracts. This does not compose
multiple event state spaces, infer semantic relationships, or establish
execution.

After the change, 49 relationship/economics/replay tests and two replay API
tests passed (51 total), as did the focused Mission Control family-label test;
strict mypy passed for the four changed core modules, and Ruff plus diff checks
passed. The full serial Frontier suite then passed 332 tests in 54.32 seconds
wall time at 369,040 KiB peak RSS, with zero swaps, socket messages, or major
page faults. Full web and browser suites were not rerun after this change. The
synthetic three-leg arithmetic is a fixture, not an observed market finding.
Mission status remains **PARTIALLY VERIFIED**; live cross-venue validation,
general multi-market research, source-quality evidence, and production
deployment remain incomplete.

### Conversion-adjusted terminal-state sensitivity — 2026-10-28 00:47 UTC

Code commit `71ee203b033c4bc0f38afce09b5255fe31bcae21` on the isolated Frontier
branch applies user-entered virtual conversion fees to a separate terminal-state
P&L sensitivity. The calculation is available only when the saved candidate's
economic audit and funding conversion audit verify, all modeled candidate leg
fees are known, and every venue-local virtual balance covers the recorded
capital requirement. An independent rational pass checks the per-state result.
Incomplete or disagreeing inputs produce no adjusted P&L map. The candidate's
saved P&L, classification, and practical eligibility stay unchanged. This adds
no FX source, transfer, account, wallet, execution, or production path.

The full Frontier regression passed **325/325** in 51.73 seconds wall time, with
**365,976 KiB peak RSS**, zero swaps, and zero socket messages. Focused
currency/P&L plus saved-run API coverage passed **16/16**; that measured run used
**82,756 KiB peak RSS**, zero swaps, and zero socket messages. The web suite
passed **40/40**, TypeScript passed, the Frontier browser spec passed **4/4**,
and the Vite production build passed with the existing 544.41 kB Chart chunk
advisory. Ruff, scoped mypy, ESLint, Prettier, and `git diff --check` passed.
One existing Starlette/httpx deprecation warning remains. The build and browser
tests used the isolated worktree. No source endpoint or protected MIDAS service
was accessed. Current mission status remains **PARTIALLY VERIFIED**; genuine
live cross-venue matching and production deployment remain open.

### Virtual funding-currency sensitivity — 2026-10-28 00:22 UTC

Frontier branch `codex/frontier-20261026` is at test-hardening commit
`87c67b23fbda1624a6b36273b63cd94427113b4c`, following implementation commit
`530c9aa8b3fb2b4ee006c35c2494bccdb0b7cae8`. The implementation adds a hash-pinned,
on-demand virtual funding-currency sensitivity to candidate details. Each venue
requires an explicit namespaced funding identity, balance, target-units per
funding-unit rate, and conversion fee. Different identities do not inherit
parity; their rate and fee inputs start blank. The separate Fraction audit and
the route leave candidate P&L, classification, and practical eligibility
unchanged. This is not a live FX source or transfer model.

The focused Python selection passed **40/40** and the Frontier Web test file
passed **8/8**. TypeScript, production build, targeted lint/formatting, and strict
mypy for the new FX module passed. The API file's broader strict-mypy run still
has its existing `no-any-return` adapter lookup finding; suppressing that code
produces no other API-module error. The production build reports a 544.41 kB
Chart chunk advisory. The full Frontier suite and Playwright browser test remain
unrun under elevated shared host pressure while an external Veritas batch was
active. No exchange request, Reality process, Arena worker, production store,
or deployment was used. Frontier remains isolated, research-only, undeployed,
and **PARTIALLY VERIFIED**. There is no new evidence of live FX availability,
cross-venue economic relationships, or profitable opportunities. See the
[mission ledger](frontier/FRONTIER_MISSION_LEDGER.md) and
[engineering report](frontier/FRONTIER_ENGINEERING_REPORT.md).

### Recorded health join and timeline freshness control — 2026-10-28 00:18 CET

Frontier branch `codex/frontier-20261026` is at code commit
`8e79bf1f3bc583aa2329096729c6dd9c624c603d`, following
`ea073c4cdb4a00b70fc609e8806f80a40542cd4c`. The timeline API now resolves
recorded source-state events against the finite collector's append-only
checkpoint journal. It checks the full checkpoint chain and run-spec digest,
then requires the event venue, health timestamp, mapped state, reason, and
checkpoint digest to match. Held-source health is rejected. Timeline snapshot
schema 2 pins the validated checkpoint hashes while schema 1 inputs without
recorded health remain readable. Mission Control exposes a pinned book-age
control from 1 to 3,600,000 milliseconds.

The combined Frontier/Arena regression passed **350 tests**; the separate
collector/timeline-API/Arena timeline selection passed **21/21**. The Web suite
passed **40/40**, TypeScript, ESLint, Prettier, and production build passed, and
the isolated Playwright empty/offline scenario passed **1/1**. Legacy integration
and Arena admission regressions passed **63**, with one PostgreSQL test skipped
after unsetting `MIDAS_TEST_POSTGRES_URL`. Strict mypy passed the three changed
backend modules. The existing 544.41 kB Chart chunk advisory remains.

The host sample at `2026-10-27T23:15:35Z` showed 0% memory PSI avg10, 10 GiB
available memory, and 400 MiB free swap; it is a dated point-in-time sample.
No exchange request, collector, Arena worker, production service, or historical
store was accessed. Frontier remains isolated, research-only, undeployed, and
**PARTIALLY VERIFIED**. No live multi-venue relationship or economically
eligible opportunity was established. See the [mission ledger](frontier/FRONTIER_MISSION_LEDGER.md)
and [engineering report](frontier/FRONTIER_ENGINEERING_REPORT.md).

### Event-time Arena replay and finite collector checkpoint — 2026-10-27 22:58 UTC

The isolated Frontier branch contains collector commit
`b6b8a99337b5b08a54b5011eaf72d30949ab0b1b` and event-time Arena integration
commit `5e04c14b47c9b820946259a8ad1e232b4597190a`. The collector is a finite
one-source Python module with restartable append-only checkpoints; it is not an
API, Arena job, timer, or background service. Event-time replay is exposed as
an explicit, local-input-only Arena job with content-addressed snapshots,
hash-verified results, held-source filtering, a readiness gate, and a Frontier
Mission Control view.

Verification at this checkpoint: the Frontier/Arena Python regression command
passed **347 tests**; the web suite passed **40/40**; the isolated browser
scenario passed **1/1** and observed no collector probe or timeline submission
from opening Replay & Readiness. Scoped strict mypy passed four changed backend
modules, TypeScript, ESLint, Ruff and Prettier passed, and the Vite production
build passed. The build retains the existing 544.41 kB Chart chunk advisory.
The repository-wide mypy run still reports 35 errors in unrelated Veritas/Arena
modules. No exchange request or Arena worker was launched; no production
service or historical store was accessed. Recorded source-status events remain
unsupported until a validated evidence-store join exists, and timeline
readiness remains pending a completed bounded job with runtime evidence.

Frontier remains isolated, research-only, undeployed, and **PARTIALLY VERIFIED**.
No positive cross-venue economic result was established. See the
[mission ledger](frontier/FRONTIER_MISSION_LEDGER.md),
[architecture](frontier/FRONTIER_ARCHITECTURE.md),
[operations guide](frontier/FRONTIER_OPERATIONS.md), and
[engineering report](frontier/FRONTIER_ENGINEERING_REPORT.md).

### Coinbase Exchange Spot update — 2026-10-27 21:07 UTC

The isolated Frontier branch `codex/frontier-20261026` now contains Coinbase
Exchange spot adapter commit `cfda4ad1beb00f301affe52752e8815b4862f8b5`, with
validation checkpoint commit `4b20aa9db859842f355c37920505de893732c17a`. The
adapter supports configured public product metadata, aggregated level-2 books,
and one bounded trade page. Spot remains contextual evidence, not an event
contract payoff; account-tier fees, settlement rules, and live cross-venue
relationships are not established.

Source use is disabled by default. The local adapter and API require an exact
acknowledgement of Market Data Terms version `2026-08-07`, with a separate
public-probe setting. This does not validate the applicable organization,
region, retention, or redistribution scope. No Coinbase API request or capture
was made. The focused adapter, terms-gate, held-source, and spot-payoff tests
pass **10/10**; the full Frontier suite, web suite, production build, and
browser regression for this checkpoint remain pending a safe host admission
window. At the latest resource check the external bounded Veritas/Arena batch
held the shared Arena lock and PSI was high; it was left untouched. Frontier
development remains isolated, incomplete, and undeployed. See the [mission
ledger](frontier/FRONTIER_MISSION_LEDGER.md) and [engineering
report](frontier/FRONTIER_ENGINEERING_REPORT.md) for measured evidence and
continuation steps.

### Frontier regression update — 2026-10-27 21:12 UTC

The complete Frontier Python suite now passes **262/262**, the web unit suite
passes **40/40**, TypeScript typecheck passes, and targeted Frontier ESLint
passes. Ruff check/format, Prettier, and `git diff --check` pass. Peak RSS was
353,748 KiB for Frontier Python, 271,600 KiB for web tests, and 439,648 KiB for
typecheck; none of these jobs swapped. The production build and browser E2E
remain unverified for the Coinbase checkpoint. The shared Arena batch had
restarted and PSI was elevated at the latest admission check, so those heavier
jobs were deferred. No exchange request, service action, or historical-store
access occurred.

Frontier development is active in the isolated worktree
`/home/charlie/midas-frontier` on branch `codex/frontier-20261026`, based on the
verified Veritas V6 integration. It is not merged or deployed. The current
development checkpoint adds bounded Polymarket and Kalshi event-group capture,
parent-event/outcome metadata, a conservative text-only relationship hypothesis
path, and Market Explorer controls. Kraken explicitly leaves event-group
discovery unsupported.

A preserved two-request public metadata capture identifies Polymarket event
`32225` and Kalshi event `CONTROLH-2026` as a related 2026 House-control topic.
The child contracts use different stated resolution schedules and details; the
relationship remains a hypothesis and the independent same-payoff verifier
rejects equivalence. No order books, synchronized quotes, or economic result
were captured. The live payloads and hashes are in
`data/frontier/live-probes/2026-10-27-public-cross-venue-house-control-r1.json`.

The focused Frontier and Arena replay suite passed 116 tests with a measured
250,324 KiB peak RSS and no swap. The frontend passed 39 tests, a production
build, and 11 isolated browser tests. A whole-repository pytest attempt remains
blocked at collection by legacy Reality/Veritas imports that are unresolved in
the selected checkout. This addendum updates Frontier development only; the
production service and protected Reality recorder state below has not been
remeasured or changed by this work.

The 2026-10-27 replay v6 development checkpoint now carries exact saved market
and book observation record IDs through API-loaded model provenance, replay
manifests, candidate legs, and content-addressed Arena snapshots. The focused
Frontier/Arena regression suite passed 118 tests at 254,696 KiB peak RSS with
zero swap. This is isolated code and fixture/local-store verification; it did
not change the database schema, production services, or protected Reality
state. See the dated Frontier mission ledger for the complete command and
resource measurements.

The latest isolated Frontier checkpoint adds revision-bound pagination for
centered two- and three-hop graph traversals. Pages preserve deterministic
breadth-first order, and wide layers are split into indexed queries while the
500-row request scan cap remains in force. The full Frontier/Arena regression
suite passed 121 tests (259,044 KiB peak RSS); the frontend passed 39 tests,
typecheck, lint, and formatting. Playwright enumerated 11 tests, but browser E2E
and a fresh production build were deferred at the 2026-10-27 11:28:57 UTC
resource sample: memory PSI `avg10` was 35.78% (`some`) and 32.22% (`full`),
swap use was 3.4 GiB, and the active API cgroup was at 527,319,040 of
1,610,612,736 bytes `MemoryHigh`. No server, production service, or protected
Reality state was changed.

The latest isolated Frontier checkpoint adds a capability-gated, operator-triggered
Kalshi multivariate-event lookup. It accepts exactly one series or collection
ticker, requests one page with nested markets, retains but does not follow the
source cursor, and persists typed event-group metadata. The genuine October 27
capture returned one event and a cursor but omitted nested markets despite the
requested flag. Its saved replay now represents membership as `omitted`, not as
an empty list; explicit `null` member data is rejected. This is event discovery
only and establishes no combo payoff or component equivalence.

A separate one-GET follow-up to Kalshi's public event-detail endpoint returned
HTTP 200 for the same ticker. The `event` object omitted its nested `markets`
field while the documented top-level `markets` array was explicitly empty.
Adapter v7 rejected that shape; adapter v8 now replays it as a valid empty
event-detail batch. The preserved raw response and separate hash-verified replay
row are in `data/frontier/live-probes/2026-10-27-kalshi-mve-event-detail-r1.json`.
This confirms no child markets in those two bounded responses, not venue-wide
absence or payoff semantics.

Adapter v9 extends the explicit MVE probe filter to one event ticker, mapped to
the documented `tickers` query parameter and checked against the returned event
ID. A preserved single-request capture returned one event, no cursor, and no
nested-market field. Exact raw-response replay through the local API stores the
event with membership state `omitted`; the raw body and isolated store-row hash
are recorded in
`data/frontier/live-probes/2026-10-27-kalshi-mve-ticker-filter-r1.json`. The
harness cleanup raised an event-loop error only after response capture and
store read-back completed; the request was not repeated. This is event lookup,
not evidence of child contracts, combo payoff, or venue-wide inventory.

The isolated Frontier branch now has adapter v10's one-market Kalshi metadata
lookup, exposed only for a selected component ticker already referenced by a
saved MVE market. It validates parent market/event identity and persists
`market_metadata` rows into market queries and graph revisions. One public
capture returned the referenced Brandon Miller 2+ assists contract as closed;
its rules include fair-price fallback cases. Raw and row hashes are preserved
in `data/frontier/live-probes/2026-10-27-kalshi-mve-component-market-r1.json`.
This child-level source observation does not verify combo payout or economics,
and the Frontier branch remains undeployed.

The current isolated branch is Kalshi adapter v13, Polymarket adapter v5, and
Kraken Spot adapter v2. It retains Kalshi's optional
`yes_settlement_value_dollars` component field and adds a local-only arithmetic
audit comparing the recorded selected-component product with the parent MVE's
recorded settlement value. The audit requires complete component values and a
settled parent with `is_provisional=false`; an absent flag remains non-final
evidence. Otherwise it reports incomplete, non-final, or unsupported evidence.
Audit schema v2 pins algorithm `kalshi-mve-settlement-audit-2` and returns the
parent lifecycle and recorded provisional flag with source observation and
raw-body hashes. The dashboard displays these values. The audit
does not make a source request or generate a candidate. Kalshi's public
[combo guidance](https://help.kalshi.com/en/articles/13823820-combos),
[NO scalar rule](https://help.kalshi.com/en/articles/17515177-protected-nfl-player-markets),
and [MVE API schema](https://docs.kalshi.com/api-reference/events/get-multivariate-events)
are included in the inspector. Only documentation-shaped fixtures currently
contain the required parent and component values; no live settlement finding
is available. Initial adapter/audit commit: `8a3e25c`.
Commit `364478853908272f5b860758fa0bb18b52b3efc8` tightens finality handling:
the local audit now requires explicit `is_provisional=false` and returns the
versioned algorithm/finality fields in schema v2. Focused unit, API, and UI
checks pass; live settlement values remain unavailable.

### Polymarket versioned book and settlement mapping

Polymarket adapter v5 routes Gamma `version=v1` CTF-token books to
`clob.polymarket.com` and `version=v2` position-ID books to the documented
`clob-v2.polymarket.com` host. For v2 positions, it maps settlement to pUSD on
Polygon (`eip155:137`, token address
`0xc011a7e12a19f7b1f670d46f03b03f3342e82dfb`); market payoff and resolution
remain unverified. V1 market settlement identity remains absent because the
Gamma asset-ID schema alone does not attest a market's collateral route.

A bounded v1-host live book probe at `2026-10-27T14:16:33.559710Z` returned
HTTP 200 and is preserved in
`data/frontier/live-probes/2026-10-27-polymarket-clob-v1-book-r1.json`. The
earlier direct request to the documented v2 host failed DNS resolution from
this development environment. The v2 route is therefore fixture-tested and
live validation remains pending. No order, authenticated call, or service
change was made.

Verification for this checkpoint: the full Python Frontier/Arena suite passed
148 tests before only the output's official-source-link field was added; the
latest focused Python selection passed 17 tests with that field. The 40-test
frontend suite, all four Frontier browser cases, production frontend build,
typecheck, lint, format, Ruff, and strict mypy passed. At 13:01 UTC, memory PSI
`avg10` was 38.72% (`some`) / 32.96% (`full`), available RAM was 9.93 GB, and
3.46 GiB of swap was in use. No additional full Python run was started under
that pressure. No deployment, new public capture, protected-service change, or
Reality action was made. See the Frontier report and mission ledger for the
test boundary and remaining acceptance work.

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

The frozen worker's lag and recorder memory growth need a separately versioned operational decision. Preserve the current campaigns, records, and source segments while making that decision. Do not change the frozen campaign configuration or journal. As of the 2026-10-17 operational snapshot, Atlas/Frontier, new market discovery, strategy expansion, training, exploratory experiments, and economic optimization were outside the maintenance scope; Frontier's later isolated development has not changed this production boundary.


## Research Readiness live state — 2026-10-26 06:38 UTC

Mission Control API release `a152999` and web release `767f330` remain active. The dashboard distinguishes measured, missing, loading, stale, and blocked evidence; live browser verification covered the V6 summary, delayed-request loading, demo labeling, and a 390 px viewport.

The latest V6 summary (06:30:54Z) is `CATCHING_UP` at 80/532 snapshots, with 452 pending. Reference v3 covers 3,200 repeated observations across 1,342 markets; 585 are independently snapshot-valid and there are zero positive-gross, supported, or net-eligible. The latest scan (`scan-20261026T063043Z-496db0ece99f`) selected 40 from a bounded population of 94 in a 299-market response union: 8 reference-random, 31 rotating-stratified, and 1 stable control. It had 33 quality-valid, 7 strict-fresh, and zero positive top-gross pairs. Seven frozen controls were missing. This scan has no v3 analysis event yet, so it is not part of the cumulative independent counts. Repeated observations are not independent trials.

Reality's atomic status receipt at 06:36:18Z reports `RECORDING_UNSEQUENCED`, ordinal 5,189,775, 16/16 fresh books, sequence verification false, 18,720 local gap markers, and no `current_error`. Its generic `ConnectionClosedOK` field has no timestamp. The active collector still uses 24 GiB / 90-day settings and reports 9,186,445,262 bytes stored. Finalized-source analysis last covered 32,213/32,213 catalog segments through ordinal 5,183,587 at 06:10:53Z; the current ordinal is 6,188 records beyond it. The latest archive provenance inventory remains invalid, with 1,138 extra names and 58 `.copying` files.

At 06:35:10Z, API memory charge was 1,609,183,232/1,610,612,736 bytes (1.36 MiB headroom), with 8 new `MemoryHigh` events over 565.771 seconds and no `max` or OOM event. Reality had 272,220,160 bytes below `MemoryHigh`; host available memory was 8.64 GB. Research admission remains blocked. The latest capacity forecast is still from 06:11Z; the staged 112 GiB / 120-day plan remains pending restart. A fresh 519-snapshot offline replay output has a complete receipt but its old verifier omitted copy-checkpoint reconciliation; this output was preserved. The reconciliation defect is fixed on the isolated Veritas integration branch and tested, but that fix has not been deployed. See [engineering mission Section 19](reliability/MIDAS_ENGINEERING_MISSION_2026-10-26.md) and `docs/VERITAS_OPERATIONS.md` for receipt hashes and remaining gates.

## Frontier development checkpoint — 2026-10-27

On isolated branch `codex/frontier-20261026`, commit
`9d7b599516ca70895525c701543c507054bcfbe6` adds a candidate-detail virtual
funding comparison. Manually entered balances stay in browser state, are
compared with exact decimal arithmetic separately per venue, and are never
pooled or sent to an API. Unknown venue fees remain unresolved. The Frontier
component tests passed 8/8, the focused depth-two/capital-fragmentation/mobile
Playwright case passed, and frontend typecheck, ESLint, and Prettier passed.
The production build after this UI change was stopped before completion as
memory PSI rose; it remains unverified. The latest sampled PSI (`13:13:42Z`)
was 38.92% (`some`) / 33.95% (`full`), with 9.3 GB available RAM and 3.5 GiB
swap used. No source, service, production configuration, or Reality evidence was
changed. This development checkpoint does not update or measure the operational
Reality/Veritas state above. See the [Frontier mission ledger](frontier/FRONTIER_MISSION_LEDGER.md)
and [engineering report](frontier/FRONTIER_ENGINEERING_REPORT.md).

Review follow-up commit `cca4038` disables virtual-funding comparison if any
leg is missing a quote currency. The Frontier component file now passes 8/8
tests after this correction, and the web TypeScript typecheck passes. The
focused depth-two/capital-fragmentation/mobile browser case predates the fix
and was not rerun. The production build remains unverified because it was
stopped under rising PSI.

## Frontier economics and API provenance checkpoint — 2026-10-27 13:28 UTC

The isolated Frontier branch adds a fail-closed USD/USDC denomination guard to
same-payoff verification, binary and multi-outcome candidate generation, and
the independent economic audit. A focused six-test regression group passed.
The Polymarket v2 trade-page and generic market/book/trade probe now preserve
raw response captures drained before lineage checks; already persisted earlier
captures are removed from the pending failure set to avoid duplicates. Four
focused API tests passed, including byte/hash readback from temporary stores.
Ruff check and formatting passed for the changed code. These checks used
fixtures and mock HTTP responses, not live exchange calls.

The source health `requests_in_window` field now counts the trailing 60 seconds
of bounded monotonic-time request history instead of the transport lifetime
counter. Commit `3f8a5cabfe209d105d0ddde948f9862cf72fb8fb` adds the metric and a
focused adapter regression; one test passed. This does not change probe rate
limits or make health reads call a venue.

Cross-venue candidate timing now also requires equal known timestamp semantics,
timestamps no later than the replay time, and observed timestamp skew plus
declared source clock uncertainty within the scenario limit. Commit
`25a9cc711976da49b80bdaacc3b51c2ac6f82bae` adds the guard; its focused test
passed. Existing public adapters leave clock uncertainty unspecified, so live
cross-venue timing remains unverified.

At the latest resource sample (`13:28:55Z`), host memory PSI was 39.81%
(`some`) / 34.86% (`full`) over `avg10`, with 9.1 GB available RAM and about
553 MiB swap free. Broader test suites, the Frontier production build, and the
UI typecheck were not run. The earlier interrupted production build remains
unverified; no production service or historical evidence changed. See the
[Frontier ledger](frontier/FRONTIER_MISSION_LEDGER.md),
[engineering report](frontier/FRONTIER_ENGINEERING_REPORT.md), and
[operations guide](frontier/FRONTIER_OPERATIONS.md).

## Frontier focused regression checkpoint — 2026-10-27 13:40 UTC

The core API, adapter, and economics test files passed 99 tests with one
Starlette/httpx deprecation warning. The web component file passed 8/8 tests,
including the per-leg missing-currency case, after test commit
`f206dfedc34cf3fafae0b74afc5e13376c036b4a`; TypeScript typecheck, targeted
ESLint, and Prettier passed. No live source or browser E2E run occurred in this
checkpoint.

Targeted mypy exited 1 on 14 diagnostics in four unmodified imported
Veritas/Arena modules and reported none in its six explicit Frontier/API
targets. The complete repository test suite, remaining Frontier/Arena tests,
and production build remain unverified. The separate Frontier engineering
report records the exact commands and mypy module names.

### Frontend build retry — 2026-10-27 13:42 UTC

`corepack pnpm --dir apps/web build` completed TypeScript and started Vite
transformation, then was stopped with Ctrl-C (exit 130) after a follow-up
sample about five seconds later showed PSI `avg10` at 10.74% (`some`) / 8.37%
(`full`). At `13:42:24Z`, PSI `avg10` was 22.14% / 16.01%, `avg300` was
14.22% / 12.27%, available RAM was 9.1 GB, and free swap was about 553 MiB.
The production bundle remains unverified; no service or source was contacted.

### Settlement asset identity checkpoint

`FrontierMarket` and `PayoffSpec` schema v2 now carry a structured
`settlement_asset_identity`. Non-fiat identities require a network ID and asset
reference, and relationship verification, opportunity generation, and the
independent audit require the market and payoff identities to agree exactly.
The token-ticker fixture verifies for the same identity and is rejected when
the network differs. Kalshi event contracts normalize to `fiat:USD`.
Polymarket Gamma v2 position markets now map to pUSD on Polygon; v1 markets
remain without a canonical settlement identity. Both Polymarket payoff paths
remain unverified, so the mapping creates no live cross-venue economic claim.
The identity is normalized protocol evidence, not an independent market
payout attestation. V2 book routing is fixture-verified; live host validation
is pending, while a separate current v1-host book capture is recorded.

Focused regression verification on this checkpoint passed: 25 relationship,
economics, and replay tests; 60 adapter, storage, and replay-comparison tests;
two API tests; two Frontier UI tests; TypeScript typecheck; Ruff; ESLint; and
Prettier. No full repository suite, production frontend bundle, live token
integration, or browser E2E was run for the schema checkpoint. The subsequent
v1-host public snapshot and unresolved v2 hostname attempt are documented in
the Polymarket route subsection and live-probe manifest. The exact test
commands and interpretation are recorded in the Frontier engineering report.

## Frontier exact-denomination checkpoint — 2026-10-27

Commit `03dbc92` extends canonical denomination identity from market settlement
to instrument quote, public book, fee schedule, trade, candidate leg, and modeled
capital. The binary and multi-outcome evaluators require the instrument and
book quote units to match the exact settlement identity; the independent audit
rechecks quote, book, fee, and capital identities. A token whose display code is
`USD` cannot match `fiat:USD`. Older records still load with identity unknown
and remain ineligible for supported candidate arithmetic. Mission Control keeps
virtual balances separate by venue and canonical denomination.

The full Python Frontier suite passed **153 tests** with one existing
Starlette/httpx deprecation warning. The Frontier component file passed **8/8**;
TypeScript, targeted ESLint, Prettier, Ruff, and `git diff --check` passed. The
isolated depth-two graph and venue-fragmented-funding Playwright case passed.
The production frontend build completed in **13 seconds** at **676,320 KiB peak
RSS**, with no swaps; Vite retains a chunk-size warning for the main and chart
bundles. No live exchange request, deployment, production service change, or
Reality/evidence mutation occurred. The full repository suite, full browser
suite, and live Polymarket v2 host/settlement validation remain outstanding.
See the [Frontier ledger](frontier/FRONTIER_MISSION_LEDGER.md) for reproduction
commands and the [engineering report](frontier/FRONTIER_ENGINEERING_REPORT.md)
for the current component matrix.

## Frontier source-data terms hold — 2026-10-27

An official-source terms review found that the Kalshi Developer Agreement and
[Data Terms](https://kalshi-public-docs.s3.amazonaws.com/kalshi-data-terms-of-service.pdf)
restrict the relevant API/data use outside the stated member-trading purposes.
Kraken's [EEA Terms effective 26 February 2026](https://assets-cms.kraken.com/files/51n36hrp/facade/e7cb2e6758f56b3eaa044d4b0b8097f2d1252a63.pdf)
restrict use and extraction of pricing data; the applicable regional terms and
MIDAS authorization have not been established. New Kalshi and Kraken live
captures remain held. Existing capture files remain preserved unchanged, with
new research/replay use treated as restricted pending review.

The API has no validated permission loader for Kalshi or Kraken. Both source
probe properties therefore remain false even when a probe flag and arbitrary
reference string are configured. Source routes surface the unconditional
policy hold, existing stored rows remain quarantined, and readiness keeps the
source-data-permissions gate `BLOCKED`. A reference string alone is not
permission. The regression and its verification are tracked in the
[Frontier ledger](frontier/FRONTIER_MISSION_LEDGER.md); implementation is
committed in `52b6a9e`. The focused API module passes **4/4** and the full
Frontier suite passes **219/219** with the runtime guard active; strict mypy,
Ruff, formatting, and diff checks pass. The fixture results do not establish
source permission or live validation. No source request, external message,
production change, or historical-data mutation was made for this review.

Code commits `d38f517`, `73e008e`, `e7958c1`, and `23f9860` extend the hold to
Frontier application reads: old Kalshi/Kraken market, book, trade, and
observation routes are filtered; relationships and graph edges touching held
venues are excluded; stored runs/comparisons and Arena replay artifacts with
held-source provenance are quarantined; new replay inputs omit held
observations; and generic Arena job views, research-activity digests, replay
submission, and cancellation enforce the same snapshot check.
Controlled fixtures verify those filters while confirming old records remain
stored. Arena checks held snapshots before its reconciliation path, preserving
the job manifest during blocked reads.
Direct database inspection, exports, and other paths outside those APIs remain
held pending the source review. A later test-source audit found 15 direct
capture-path references in two Frontier test modules; the 18:41 UTC full
Frontier suite executed those cases and read the referenced preserved files.
No test writes to those files were identified, and no mutation is known. All
15 references are now replaced by synthetic inputs; a `rg` scan over
`tests`, `packages`, and `apps` finds no `live-probes` path. The static source
guard passes, the converted adapter/API selection passes 24 tests, and the
full Frontier suite passes 219 tests in 39.83 seconds at 335,396 KiB peak RSS
with zero swaps. The existing Starlette/httpx deprecation warning remains.
These fixtures establish code behavior only; source permission and live
validation remain blocked. See the
[source-data terms review](frontier/SOURCE_DATA_TERMS_REVIEW_2026-10-27.md)
and [Frontier ledger](frontier/FRONTIER_MISSION_LEDGER.md).

## Frontier source-boundary and UI regression checkpoint — 2026-10-27

Commit `5e51a88` replaces the 15 direct test reads of preserved
`data/frontier/live-probes` artifacts with synthetic local response data and
adds a static test-source guard. The historical 18:41 full suite did read the
then-referenced files; no test write or capture mutation is known. Since the
cleanup, the guard passes and the full Frontier suite passes **218 tests**
(39.36 seconds, **333,988 KiB peak RSS**, zero swaps). The 24-case changed
adapter/API selection also passes. No held capture is used by the new fixture
tests.

The settlement-identity UI hardening now compares typed fields and uses a
structured balance key. Frontier's component suite passes **8/8**, the full web
suite **40/40**, and the isolated Frontier browser spec **4/4**. Typecheck,
targeted ESLint, and Prettier pass. The post-change production build passes at
**714,944 KiB peak RSS** with zero swaps; the existing Vite large-chunk warning
remains. Browser tests used temporary local services/databases and no exchange
probes. No production deployment, protected-service change, live source request,
or historical capture modification occurred. The code/docs verification
checkpoint is in progress on the Frontier branch; source permission, live
cross-venue economics, deployment, and repository-wide tests remain open.

After the earlier 218-test run, an autouse runtime file-open guard was added,
reviewed, and hardened against symlink/`..` traversal and relative `dir_fd`
opens in commit `df30fa7`. Its temporary-path cases pass **2/2**. The full
Frontier suite now passes **219 tests in 39.83 seconds**, with **335,396 KiB
peak RSS** and zero swaps; Ruff and format checks pass for the guard. The only
warning is the existing Starlette/httpx TestClient deprecation. No held source
file was opened by the new tests or changed in this work. The source permission
hold and live economic validation remain unresolved.

## Frontier Kalshi fee-override checkpoint — 2026-10-27

Kalshi's documented event-fee rule is now represented explicitly. Adapter v15
records a complete event override, an explicitly cleared override that inherits
series terms, a partial override, or unreported override fields. The local
one-fill and one-order fee sensitivities now reject partial and unreported
states. Mission Control displays the fee-resolution state next to the native
parameters. This uses official documentation and bounded fixtures only; no new
exchange request or read of held Kalshi capture data was made. Schema-v1 fee
metadata remains readable and is treated as unresolved for sensitivity work.
The canonical candidate fee schedule remains unknown, and source
permission/deployment gates remain blocked/deferred. See the [Frontier engineering report](frontier/FRONTIER_ENGINEERING_REPORT.md)
and [mission ledger](frontier/FRONTIER_MISSION_LEDGER.md) for exact tests and
limitations.

## Frontier relationship-review history checkpoint — 2026-10-27

The isolated Frontier branch now exposes immutable relationship review history
through hash-checked keyset pages, with a bounded on-demand review panel in
Mission Control. The endpoint rejects relationships involving held sources,
and controlled fixtures cover pagination, corrupt-record rejection, and the
quarantine boundary. Reviewer labels and assertion IDs remain self-attributed;
they are not authenticated. The 13-test review API module, held-source
quarantine integration test, and 8-test Frontier UI component suite pass;
frontend typecheck, ESLint, Prettier, and Python Ruff checks also pass. No
public source request, held-data read, production service change, or deployment
occurred. A fresh production build and browser E2E were deferred at the host
memory-pressure sample. Frontier remains isolated, incomplete, and undeployed;
see the [Frontier mission ledger](frontier/FRONTIER_MISSION_LEDGER.md) and
[engineering report](frontier/FRONTIER_ENGINEERING_REPORT.md).

## Frontier bounded graph text search — 2026-10-27

The relationship explorer now submits text searches to the local API and pages
through a deterministic breadth-first result window. Its cursor pins the query,
depth, page size, and graph revision; stale cursors are rejected. Search remains
limited to at most 200 recorded market records and 500 relationship rows, and
Mission Control labels that scope. The Frontier API module passed **44 tests**;
the final depth-two search pagination regression also passed independently.
The Frontier UI component passed **8 tests**, including search and page
navigation; TypeScript typecheck, ESLint, Prettier, and Ruff checks passed.
The production build and browser E2E were deferred at the host PSI sample.
Frontier remains a research-only development branch, incomplete and
undeployed; this does not provide full-universe coverage or a genuine economic
result. See the [mission ledger](frontier/FRONTIER_MISSION_LEDGER.md) and
[engineering report](frontier/FRONTIER_ENGINEERING_REPORT.md).

## Frontier Kalshi schedule clarification — 2026-10-27

Commit `410860a` records an official-document check: the July 7, 2026 Kalshi
fee schedule labels its non-standard columns Maker Multiplier then Taker
Multiplier, so the `KXMVE` row means maker 2 / taker 1. This resolves the
column-order reading only. It does not establish that the row applies to the
different `KXMVECROSSCATEGORY` series in preserved evidence or settle account
precision, maker fees, or mixed-order economics. No source request or held-data
read occurred and no code or test files changed. The existing two-case
synthetic fee-type regression passed **2/2** in 0.30 seconds at **54,520 KiB
peak RSS** with zero swaps; this verifies local taker arithmetic only. Frontier
remains isolated and PARTIALLY VERIFIED; Kalshi/Kraken source permission, live
cross-venue economics, broader regression, and production deployment remain
unresolved.
See the [Frontier ledger](frontier/FRONTIER_MISSION_LEDGER.md) and
[engineering report](frontier/FRONTIER_ENGINEERING_REPORT.md).

## Frontier Kalshi price-range checkpoint — 2026-10-27 19:44 UTC

The isolated Frontier branch now normalizes Kalshi `price_ranges` as exact
decimals in FrontierMarket schema v4 and Kalshi adapter v17. The new instrument
field distinguishes absent metadata from an explicitly empty range list, and
both candidate generation and independent audit enforce reported intervals.
The shared model caps decimal precision at 18 places to reject enormous
scientific-notation exponents before rational arithmetic.
The implementation uses `start` as the step-grid anchor by inference from the
official schema's `start`/`end`/`step` shape. Because endpoint inclusivity is
undocumented, prices at range boundaries fail closed. This is fixture-verified
behavior only; no live request or held-data read occurred.

The focused Python adapter/economics/replay/API selection passed **17 tests**
with one existing deprecation warning at **78,936 KiB peak RSS** and zero swaps.
The full Frontier UI component file passed **8/8** in 3.31 seconds, including
the new constraint display. TypeScript, targeted ESLint, Prettier, Ruff, strict
mypy on five production modules, and `git diff --check` passed. Parser
regressions reject non-arrays, oversized and overlapping
ranges, out-of-domain values, missing/numeric fields, overlong decimals, and an
extreme exponent. At `2026-10-27T19:46:50Z`, memory PSI `avg10` was 41.09% `some` /
36.23% `full`, with 9.2 GiB available and 468 MiB swap free. The broad suite and
production build were deferred. Frontier remains isolated, research-only,
PARTIALLY VERIFIED, and undeployed; live source permission, price-range
semantics, multi-venue economic validation, and deployment remain open.
The implementation is in commit `47f399d`; commit `52abaad` adds adversarial
parser fixtures and the expanded verification checkpoint.
The complete Kalshi/Polymarket/Kraken adapter test module passed **60 tests**
in 2.65 seconds at **60,504 KiB peak RSS** with zero swaps; this is not a full
Frontier regression. At `2026-10-27T19:45:58Z`, memory PSI `avg10` was 47.18%
`some` / 41.86% `full`, with 9.3 GiB available and 468 MiB swap free.
The full Frontier UI component file also passed **8/8** in 3.31 seconds.
Next safe work is an offline review of incomplete cross-venue capital and
settlement costs, leaving unsupported FX/transfer costs unknown. Recheck host
pressure before the broader suite; keep source permission and deployment gates
unchanged.

## Frontier regression and build checkpoint — 2026-10-27 19:50 UTC

After PSI eased, the complete Frontier Python suite passed **230/230** in
39.45 seconds at **335,348 KiB peak RSS**; the full web suite passed **40/40**
across seven files at **298,344 KiB peak RSS**. Both completed with zero swaps.
The isolated Frontier browser spec passed **4/4** in 9.7 seconds, one worker,
at **190,708 KiB peak RSS** with zero swaps. Playwright used temporary API,
SQLite, Arena, Frontier, and test-output paths; all local test servers stopped.

The production build passed to
`/tmp/midas-frontier-web-build-20261027-1949`, compiling 2,228 modules in 4.69
seconds Vite time (12.21 seconds wall) at **706,308 KiB peak RSS** with zero
swaps. The existing Vite main/Chart chunk-size warning remains. TypeScript,
targeted ESLint and Prettier, Ruff, strict mypy for five changed production
modules, and `git diff --check` passed. At `2026-10-27T19:50:15Z`, PSI `avg10`
was 0.00% `some` / 0.00% `full`; available memory was 9.1 GiB and swap free
468 MiB. The repository-wide MIDAS suite remains unrun. No external source
probe, held-capture read, Reality action, or deployment occurred. Frontier stays
isolated, research-only, PARTIALLY VERIFIED, and undeployed.

## Frontier virtual capital release-delay scenario — 2026-10-27 20:02 UTC

Code commit `29ab175` adds an optional post-settlement release delay for each
venue in the virtual capital-duration workbench. Delay is a whole-second
scenario input, bounded to one year, defaults to zero, and is included in the
input digest. The independent verifier recomputes release time, duration,
carry, and adjusted P&L from the pinned replay inputs. UTC normalization
handles daylight-saving transitions and timestamps that overflow fail closed.
The interface labels the delay as a scenario assumption, not actual redemption
or capital availability.

Verification passed: the capital-carry module **27/27** (including a post-format
rerun), saved-run API integration **1 passed**, full Frontier Python suite
**246/246**, full web suite **40/40**, and isolated Frontier browser suite
**4/4**. TypeScript, targeted ESLint/Prettier, Ruff check/format, strict mypy
for the capital model and Frontier API, and `git diff --check` passed. The
production build compiled 2,228 modules in 12.28 seconds wall at 700,060 KiB
peak RSS with zero swaps, using `/tmp/midas-frontier-web-build-20261027-2001`;
the repository `dist` was untouched. Existing large index/Chart chunk and
external-output-directory warnings remain. The Frontier Python suite has the
existing Starlette/httpx deprecation warning. At `2026-10-27T20:02:00Z`, memory
PSI avg10 was 0.00% (`some`/`full`), avg60 1.19% / 1.09%, avg300 14.11% /
12.77%; 9.5 GiB was available and 468 MiB swap free. The legacy repository
suite remains unrun. No live-source request, held-capture read, protected
service action, or deployment occurred. Frontier remains isolated,
undeployed, research-only, and PARTIALLY VERIFIED.

## Frontier Arena replay regression — 2026-10-27 20:04 UTC

The focused Arena integration suite `tests/arena/test_frontier_replay.py`
passed **10/10** in 1.94 seconds (2.63 seconds wall) at **193,936 KiB peak
RSS**, with zero swaps and the existing Starlette/httpx TestClient deprecation
warning. It uses temporary paths and covers replay snapshot/job contracts,
artifact integrity, bounded catalog/API reads, and held-source quarantine.
This supplements the full Frontier Python, web, browser, and build results at
20:02 UTC. No Arena production job, exchange request, preserved capture, or
Reality service was accessed. Frontier remains PARTIALLY VERIFIED; the
repository-wide legacy suite and deployment are not verified.

## Legacy API integration compatibility — 2026-10-27 20:05 UTC

The isolated `tests/integration/test_api.py` module passed **5/5** in 3.99
seconds (5.01 seconds wall) at **154,664 KiB peak RSS**, with zero swaps. Its
demo workflow forbids construction of the public client and uses temporary
databases/workspaces; the Arena qualification route is mocked. It verifies
existing demo API, health/readiness, Frontier empty/no-probe responses,
Veritas/Reality configured-workspace routes, and persistence failure gates.
The only warning is the existing Starlette/httpx TestClient deprecation. At
`2026-10-27T20:05:24Z`, admission PSI avg10 was 0.00% (`some`/`full`), avg60
8.15% / 7.33%, avg300 15.84% / 14.31%; 9.6 GiB was available and 468 MiB swap
free. This is a narrow compatibility slice; the repository-wide legacy suite
remains unrun. No public source, historical store, protected service state, or
production deployment was accessed.

## Legacy Polymarket and recording compatibility — 2026-10-27 20:06 UTC

`tests/integration/test_adapters.py` passed **9/9** in 0.71 seconds (1.21
seconds wall) at **88,872 KiB peak RSS**, with zero swaps. It uses checked-in
recorded market fixtures and `httpx.MockTransport`; no public request occurs.
`tests/integration/test_recording_isolation.py` passed **4/4** in 0.49 seconds
(0.93 seconds wall) at **77,800 KiB peak RSS**, with zero swaps. Its writes stay
under `tmp_path`; its production-default case only asserts path compatibility.
Together these preserve the existing Polymarket adapter contract and ensure a
temporary database maps to an isolated recording root. At
`2026-10-27T20:06:31Z`, memory PSI avg10 was 0.00% (`some`/`full`), avg60 2.62%
/ 2.36%, avg300 12.54% / 11.33%; 9.6 GiB was available and 468 MiB swap free.
No protected recorder, historical store, public source, or deployment was
accessed. The repository-wide suite remains unrun.

## Frontier Laboratory compatibility smoke — 2026-10-27 20:09 UTC

The existing Laboratory API contract/reproduction test passed **1 test** (two
other module tests deselected) in 2.50 seconds (3.15 seconds wall) at **124,540
KiB peak RSS**, with zero swaps. It creates and reproduces a four-run virtual
demo campaign under `tmp_path`. `MIDAS_MODE=demo` was explicit; Frontier and
Arena roots were redirected to fresh `/tmp` paths. No live source client,
production job, protected service, or historical store was used. The existing
Starlette/httpx TestClient deprecation remains. At `2026-10-27T20:09:29Z`, PSI
avg10 was 0.12% (`some`) / 0.11% (`full`), avg60 12.97% / 11.97%, avg300
15.92% / 14.55%; 9.6 GiB was available and swap free was 468 MiB. This is a
bounded Laboratory compatibility check, not a full Laboratory or repository
regression.

## Frontier per-venue execution-delay sensitivity — 2026-10-27 20:16 UTC

Code commit `9da08fd` adds optional venue-specific delay additions to the
bounded virtual replay scenario. The shared base delay plus each venue addition
is capped at one hour. Cross-venue binary and same-market multi-outcome pricing
apply quote decay using the relevant venue delay, and independent audit v8
recomputes it. Replay v11 and economic model v11 pin the scenario input. The
Workbench exposes per-source inputs for direct, paired, and Arena replay. Its
quantity control now says usable top-ask depth: it is a size haircut, not a
partial-fill simulation. Delay remains user-supplied and does not model actual
execution order, venue latency, or fills.

Focused Python tests passed **8/8**, with a separate API replay check **1/1**;
the focused Workbench test passed **1/1**. TypeScript, ESLint/Prettier, Ruff,
strict core Frontier mypy, and diff checks passed. Full Frontier tests and the
production build remain pending because at `2026-10-27T20:16:17Z` PSI avg10 was
44.92% (`some`) / 40.76% (`full`), 9.5 GiB was available, and 469 MiB swap was
free. API-inclusive strict mypy is also pending: the unrestricted run reached
pre-existing imported Veritas type errors and the filtered run was interrupted
under host pressure. No live source, protected service, held capture, or
production state was accessed. Frontier remains isolated, undeployed, and
PARTIALLY VERIFIED.

## Fee evidence at modeled execution time — 2026-10-27 20:22 UTC

Code commit `ad811a4` checks each leg's fee evidence at replay time plus the
scenario's shared and venue-specific delay. If a pinned schedule expires
before modeled use, the fee and net result remain unknown. The independent
audit recomputes the projected fee-applicability time. Economic model v12,
audit v9, and replay v12 pin this correction; it does not predict future fee
changes.

The fee-expiry and delay selection passed **6/6**, API replay passed **1/1**,
and the complete Frontier Python suite passed **252/252** with zero swaps.
Ruff and strict core Frontier mypy passed. At `2026-10-27T20:22:35Z` after the
full suite, PSI avg10 was 25.66% (`some`) / 22.83% (`full`); 9.5 GiB was
available and 469 MiB swap was free. The production frontend build remains
pending after the UI change; the focused UI test and TypeScript/lint/format
checks passed at the previous checkpoint. API-inclusive strict mypy remains
unverified. No live source, protected service, or historical capture was
accessed. Frontier remains research-only, isolated, undeployed, and PARTIALLY
VERIFIED.

## Frontier bounded partial-fill sensitivity — 2026-10-27 20:36 UTC

The isolated worktree now contains an uncommitted five-point partial-fill grid
for supported research candidates. It filters intermediate ratios by venue
quantity step, recomputes supported fees at each aggregate partial quantity,
and independently verifies the worst grid result. Replay is v13, the economic
model is v13, and the independent audit is v10. The Workbench displays the
sampled gross/net result and per-leg quantities. These are bounded sensitivities
only; no fill probability, continuous quantity range, multiple-fill rounding,
price path, hedge, or unwind is modeled.

Focused economics tests passed **6/6**, including exhaustive three-leg grid
enumeration, fee rounding, quantity-step filtering, and unknown-fee behavior;
the audit-tampering test passed **1/1**. Workbench component tests passed **8/8**;
TypeScript, targeted ESLint/Prettier, Ruff, and strict mypy on the four core
Frontier modules passed. A first full run had 252 passing tests and one failing
quantity-mutation diagnostic; the audit was corrected and its focused test now
passes. The complete post-fix regression and full frontend build/browser suite
remain pending. At `2026-10-27T20:36:01Z`, memory PSI avg10 was 50.50% (`some`)
and 46.53% (`full`), with 9.9 GiB available and 469 MiB swap free. No build or
full-suite run was started at that pressure sample. The code and updated
architecture/report matrix are uncommitted in `codex/frontier-20261026`.
Production services, source data, protected recordings, and deployment remain
untouched. Frontier remains **PARTIALLY VERIFIED**.

## Frontier v13 post-fix regression — 2026-10-27 20:37 UTC

The full Frontier Python suite passed **254/254** in 39.82 seconds pytest time
/ 40.92 seconds wall at **335,988 KiB peak RSS**; the only warning was the
existing Starlette/httpx TestClient deprecation. This covers the new bounded
partial-fill grid, a nonlinearly rounded Kalshi fee fixture, quantity-step
filtering, unknown-fee handling, independent audit tampering, and API replay
version 13. The API model exposes the exact feasible fill fractions per leg,
and the Workbench can expand those per-leg grids. The grid still has no fill
probabilities, continuous intermediate points, multiple-fill rounding, quote
paths, or hedge/unwind model.

The eight-case Workbench component suite, TypeScript, targeted ESLint/Prettier,
Ruff, strict mypy on four core Frontier modules, and `git diff --check` passed.
At `2026-10-27T20:37:47Z`, PSI avg10 was 34.40% (`some`) / 30.73% (`full`),
avg60 22.93% / 20.56%, avg300 27.50% / 24.76%; 9.9 GiB was available and swap
free was 481,040 KiB. The full web suite, production frontend build, and
post-change browser E2E remain pending after the next host admission check.
No live source, protected service, recording, or deployment was used. Code and
docs remain uncommitted in the isolated Frontier worktree; overall status is
**PARTIALLY VERIFIED**.

## Frontier v13 code commit — 2026-10-27 20:38 UTC

The implementation is committed on `codex/frontier-20261026` as **`e50ba34`**
(`Add independently audited partial-fill grid sensitivity`). It includes the
economic model, independent audit, replay/model version bumps, Python/API tests,
Workbench rendering and tests, and Frontier architecture/report updates. The
latest full Frontier regression remains **254/254**. The focused component
suite and static checks pass. The ledger, engineering report, and this
current-state file have documentation-only changes after that commit. Full
web tests, production build, and browser E2E
remain pending because PSI was 38.72% full at avg10 at `20:38:38Z`, despite
9.9 GiB available. No live source, protected service, or production deployment
was used; Frontier remains **PARTIALLY VERIFIED**.

## Frontier frontend and browser verification — 2026-10-27 20:43 UTC

The complete Web unit suite passed **40/40**. The production build passed
`tsc -b` and Vite in 12.50 seconds wall at **692,056 KiB peak RSS**. Frontier's
bundle is 102.13 kB JS / 35.87 kB CSS; Vite keeps an advisory warning for the
existing 544.41 kB Chart chunk. Dedicated Frontier browser E2E passed **4/4**.

The full 12-test browser suite passed **10** and failed **2** Laboratory launch
cases: the API correctly denied both with `resource_admission_lock_busy` before
launching workers. At `2026-10-27T20:43:15Z`, the active global-lock holder was
PID 3681242, `scripts/veritas_gap_detail_v2_batch.py`, using the primary and
Veritas Arena roots. The lock path is the primary `/home/charlie/midas/data/arena/.global-admission.lock`;
temporary browser roots do not override it. That pre-existing worker and lock
were left untouched. The other ten browser cases passed, including all Frontier
cases. Do not bypass/retry until the shared slot releases.

Full Frontier Python regression remains **254/254**, full Web units **40/40**,
Workbench tests **8/8**, TypeScript, targeted lint/format, Ruff, core strict
mypy, build, and Frontier E2E are verified. Full package E2E is partially
verified due only to the two admission-denied Laboratory tests. At the same
timestamp, PSI avg10 was 45.75% (`some`) / 41.58% (`full`), avg60 43.43% /
38.30%, avg300 37.69% / 33.23%; 9.9 GiB was available and 481,192 KiB swap
free. No external exchange source or production service was touched. Frontier
remains isolated, undeployed, and **PARTIALLY VERIFIED**.

## Frontier source terms recheck — 2026-10-27 20:45 UTC

An official-documents-only review reconfirmed the Kalshi data-use restrictions
and current Kraken regional content terms. Kraken's API Center documents public
Spot market-data endpoints, but the reviewed terms do not resolve this
research/retention use or the applicable regional agreement. Polymarket
Institute's current research guide distinguishes its global and US-only data
systems. The source gates did not change: Kalshi/Kraken live probes and stored
research remain blocked or quarantined. No API request, exchange contact, held
capture read, production action, or permission inference was made. See
[`SOURCE_DATA_TERMS_REVIEW_2026-10-27.md`](frontier/SOURCE_DATA_TERMS_REVIEW_2026-10-27.md).

## Frontier Arena admission recheck — 2026-10-27 20:47 UTC

The host-wide Arena lock was reacquired by a new
`veritas_gap_detail_v2_batch.py` worker, PID 3690476, on lock inode 6423106.
PSI avg10 was 38.74% `some` / 33.82% `full`; the protected Reality recorder
was present and left untouched. No rerun of the two Laboratory browser cases
was started and no lock was bypassed. Full browser evidence remains 10/12 with
those two cases admission-denied; Frontier's dedicated browser suite remains
4/4. Wait for shared admission and lower host pressure before retry.

## Frontier observation persistence checkpoint (`51afe86`) — 2026-10-27 21:23 UTC

The isolated writer now records missing `Provenance.persisted_at_utc` values
on new Frontier observations, without mutating adapter models. It preserves an
existing stamp when copying saved evidence into a content-addressed snapshot;
legacy rows without the optional field remain readable. Focused storage,
Coinbase, and snapshot-copy tests pass **25/25**. The full Frontier Python suite
passes **265/265** at **352,164 KiB peak RSS**, zero swaps. The test process
overlapped with a newly started external Arena batch after the admission
precheck; that worker and its lock were left untouched. Production build and
browser E2E for the Coinbase/storage checkpoint remain pending a safe host
window. Frontier remains research-only, isolated, undeployed, and
**PARTIALLY VERIFIED**.

## Frontier monotonic request provenance checkpoint (`6bc0351`) — 2026-10-27 21:28 UTC

Frontier records read-only HTTP request/body elapsed duration from a local
monotonic clock, carries it into raw observations and normalized provenance,
and shows it in the source-evidence disclosure. The focused Python selection
passes **86/86** and the targeted UI test passes **1/1**. The full Frontier
suite result **265/265** is from predecessor `51afe86`; it has not been rerun
for this change. Web suite, typecheck, build, and browser E2E are also pending
for the new UI field. At the latest resource sample, external bounded Arena
batch PID **3727342** held the shared lock and PSI was elevated. The worker was
left untouched; no source or production service was accessed.

## Frontier full verification checkpoint (`008106b`) — 2026-10-27 21:36 UTC

The latest code adds monotonic per-request timing provenance and a defensive
Coinbase Decimal exponent guard. The complete Frontier Python suite passes
**269/269**, Web unit suite **40/40**, TypeScript, targeted ESLint/Prettier,
Ruff, and strict direct mypy for the changed Python modules. The production
frontend build passes into `/tmp` and the full browser suite passes **12/12**,
including both bounded Laboratory cases. Peak RSS was 352,484 KiB for Frontier
Python, 346,668 KiB for web tests, 441,532 KiB for TypeScript, 701,536 KiB for
the build, and 209,416 KiB for browser E2E; all reported zero swaps. No
exchange API was called. Frontier remains research-only, isolated, undeployed, and
**PARTIALLY VERIFIED** because source permissions, genuine cross-venue payoff
validation, and production readiness remain unresolved.

## Frontier legacy compatibility selection deferred — 2026-10-27 21:39 UTC

The additional compatibility run across existing adapter, API,
recording-isolation, and Frontier Arena replay tests was deferred. At
2026-10-27T21:39:36Z, external batch PID 3745206 held the shared Arena
admission lock in D state; memory PSI avg10 was 44.57% some / 39.03% full.
No tests were started, and the worker was left untouched. Recheck lock and
host pressure before resuming. This does not invalidate the already completed
Frontier, Web, typecheck, build, or browser results.

## Frontier additional venue screen — 2026-10-27 21:42 UTC

Official Manifold and Betfair documentation was evaluated for a useful
additional source. Manifold's current core market currency is non-redeemable
mana and its sweepstakes markets ended in 2025, so it was not added as an
economic venue. Betfair requires an account application key; delayed data is
1–180 seconds, live read-only access is not permitted, and commercial use
requires approval. Neither API was queried and no credentials were requested.
The sourced decision is in
`docs/frontier/ADDITIONAL_VENUE_SCREEN_2026-10-27.md`.

At 2026-10-27T21:42:51Z, the deferred legacy tests remained unstarted because
PID 3745206 held the shared Arena lock in D state and PSI avg10 remained
39.31% some / 34.14% full. Recheck admission before running them.

## Frontier legacy compatibility tests complete — 2026-10-27 21:45 UTC

After the external batch exited and memory PSI settled, the selected legacy
adapter/API/recording-isolation and Frontier Arena replay modules passed
**28/28**. The run explicitly used `PYTHONPATH=packages:.`; the resolved
`midas` import was the Frontier worktree at
`/home/charlie/midas-frontier/packages/midas/__init__.py`. It took 7.32
seconds wall, peak RSS 282,584 KiB, zero swaps; only the existing
Starlette/httpx TestClient deprecation warning remains. Immediately after the
run, the shared lock was free and PSI avg10 was 0.01% some / 0.00% full.
This closes that bounded compatibility check. The separate repository-wide
Python run remains partial due the previously recorded collection/runtime
issues.

## Frontier integration and admission regression checkpoint — 2026-10-27 21:46 UTC

The complete `tests/integration` directory passed **55 tests**, with the
PostgreSQL runtime test skipped because its URL was explicitly unset. The
local package and test paths were supplied via `PYTHONPATH=packages:.:tests`.
The run took 29.82 seconds wall, peak RSS 210,816 KiB, zero swaps. The
Starlette/httpx TestClient deprecation is the only warning. Arena admission
regressions then passed **8/8** in 2.04 seconds wall, peak RSS 178,692 KiB,
zero swaps. The post-run lock was free and PSI avg10 was 0.00% some / 0.00%
full. These are bounded legacy integration/admission results, not a clean
repository-wide suite; unrelated collection/runtime gaps remain documented.

## Frontier resource gate — 2026-10-27 21:48 UTC

At `2026-10-27T21:48:09Z`, external Veritas batch PID **3762324** was still
blocked in `D` state at `mem_cgroup_handle_over_high`; memory PSI avg10 was
47.93% `some` / 41.46% `full`. It was left untouched. No Frontier tests or
builds were started after it appeared. Wait for pressure to settle and verify
the shared Arena admission lock before further resource-consuming checks.

## Frontier resource gate cleared — 2026-10-27 21:49 UTC

At `2026-10-27T21:49:51Z`, external Veritas batch PID 3762324 had exited and
no shared Arena lock holder was listed. Memory PSI avg10 was 0.00% `some` /
`full`; available memory was 9.9 GiB and 455 MiB swap was free. The browser
suite already passed 12/12 at the latest unchanged UI checkpoint, and later
legacy integration/admission checks passed. Recheck resource admission before
any future worker launch.

## Frontier coverage analytics checkpoint — 2026-10-27 22:13 UTC

Isolated branch `codex/frontier-20261026` adds source-aware recorded coverage
and quality analytics in code commit `4c9a8d8`. Follow-up `66e89a5` pins
market-observation IDs and canonical quote denominations in the repeated
construction signature. The no-network API endpoint
uses bounded market/book/replay samples, filters held venues, verifies joins
and observation lineage, and exposes freshness, denomination-aware spread and
depth, timing, and candidate classification summaries. A new native Frontier
Coverage & quality tab loads the view on demand. The endpoint does not query an
exchange or start a collector.

Current bounded results: Frontier Python **279/279**, Web unit suite **40/40**,
dedicated Coverage-tab browser E2E **1/1**, strict mypy, Ruff, ESLint, Prettier,
TypeScript, and Vite production build all pass. Peak RSS was 354,788 KiB for
Frontier Python, 333,216 KiB for Web tests, 186,788 KiB for the browser case,
and 667,976 KiB for Vite; each job reported zero swaps. No protected service,
exchange endpoint, held capture, or production store was accessed.

Frontier is still **PARTIALLY VERIFIED**, not deployed, and research-only.
Coverage results describe bounded stored evidence and do not establish
venue-wide measurement, synchronized executable quotes, positive net economics,
or live multi-venue validation. See the [mission ledger](frontier/FRONTIER_MISSION_LEDGER.md)
and [engineering report](frontier/FRONTIER_ENGINEERING_REPORT.md) for the full
checkpoint, remaining acceptance gaps, and continuation work.

## Frontier event-time replay checkpoint — 2026-10-27 22:24 UTC

Code commit `30576f1` adds an offline engine in
`packages/midas/frontier/timeline.py` that replays
repeated books at bounded UTC cutoffs, records stale/missing/source-interrupted
legs, prevents use of pre-interruption quotes until a new snapshot is observed,
and excludes relationship verifications that postdate a frame. Four fixture
tests cover deterioration, expiry boundaries, source interruption/recovery,
input-order reproducibility, and future-verification lookahead. The full
`tests/frontier` suite passes **283/283** in 70.69 seconds wall at **355,720 KiB
peak RSS**, zero swaps; strict mypy, Ruff, and `git diff --check` pass. The
focused timeline suite passes **4/4** in 0.69 seconds at **54,864 KiB peak RSS**.
This is engine-level verification only: the timeline is not yet exposed in the
API, persisted through Arena, or surfaced in Mission Control. Frontier remains
research-only, isolated, undeployed, and **PARTIALLY VERIFIED**.

## Frontier recorded-health catalog — 2026-10-27 23:31 UTC

Commits `31f62db`, `1779e89`, `9a3eced`, and `8f9b9b8` add a local read-only
catalog of verified collector health checkpoints, explicit replay selection,
artifact digest display, and rejection of ambiguous same-time source events.
The catalog is bounded to 20 events, filters held sources, validates each
selected journal chain, and does not create a missing journal or contact a
venue. Timestamp-less `not_probed` does not become a replay event. The UI
leaves all events unchecked and disables a second selected event for the same
venue/check time. It identifies the adapter-local health scope.

The combined Frontier/Arena regression passes **354/354** in 83.42 seconds at
**363,776 KiB peak RSS**, zero swaps. Frontier UI component tests pass **8/8**;
the isolated Replay & Readiness Playwright check passes **1/1** and verifies
the empty catalog with no source probe or job submission. TypeScript, strict
scoped mypy, Ruff, ESLint, and Prettier pass. The Vite production build passes
in 5.10 seconds at **647,020 KiB** peak RSS, zero swaps; the existing 544.41 kB
Chart chunk warning remains. No public source observation or cross-venue
economic result was established. Frontier remains isolated, research-only,
undeployed, and **PARTIALLY VERIFIED**. See the [mission ledger](frontier/FRONTIER_MISSION_LEDGER.md)
and [engineering report](frontier/FRONTIER_ENGINEERING_REPORT.md) for the
remaining offline gaps and source/deployment boundaries.

## Frontier finite source-capture API — 2026-10-27 23:38 UTC

Code commit `cf67b2b` exposes `BoundedSourceCollector` as an explicit
`POST /api/frontier/collect/{venue}` operation and an Exchanges-view button.
It shares the source lock with existing probes, rechecks the configured public
probe flag, source-use hold, capabilities, and source request limits, and caps
one run at five markets, two books, depth ten, 4 MiB of evidence, and 60
seconds. Mission Control sends a smaller 3-market/1-book/depth-5, 30-second
request. The call uses the API request lifecycle and starts no Arena job,
worker, timer, or background service. The endpoint supports starting a run;
the module's resume capability does not yet have an HTTP route or UI.

The two finite-collection API tests pass **2/2** in 1.10 seconds with fixture
adapters. `Frontier.test.tsx` passes **8/8** in 4.19 seconds, including the
explicit request body, saved run summary, and adapter-local health caveat.
TypeScript, strict scoped mypy, Ruff, Prettier, and `git diff --check` pass.
The combined Frontier/Arena regression produced **354 passed and two host
admission failures** in 81.75 seconds, at **366,436 KiB peak RSS** and zero
swaps. The two failures are existing Arena job-supervisor tests that could not
acquire the shared admission lock; process **3913373**, the existing Veritas
gap-detail batch, held that lock. It remains untouched. The production build
and browser suite were deferred after memory PSI rose to 35.60% `some` / 29.55%
`full`; 9.9 GiB was available and 3.7 GiB of swap was in use.

No real adapter, external API, collector against a live source, Arena worker,
Reality action, production service, or historical store was accessed. Source
configuration remains disabled by default and existing source-use holds remain
in force. The endpoint/UI integration is fixture-verified; live collection and
the populated browser flow remain pending. Frontier is isolated,
research-only, **PARTIALLY VERIFIED**, and undeployed.

## Frontier collection recovery — 2026-10-27 23:53 UTC

Commit `305814b` adds a bounded read-only history endpoint and explicit
resume action for finite source-collection checkpoints. API and collector
revalidate source-use policy, enabled/public-probe configuration, adapter and
capability manifests, current source limits, and request bounds before
resuming. The Exchanges workspace exposes recent verified checkpoints and a
resume button only for eligible nonterminal runs; no automatic retries or
background collection were added.

The focused collection tests pass **20/20**, Frontier UI tests **8/8**, and an
isolated browser smoke **1/1**. TypeScript, scoped strict mypy, Ruff,
ESLint/Prettier, and the Vite production build pass. All `tests/frontier`
cases passed in a broader selected regression (**358 passed, 2 failed**); the
two failures are Arena supervisor tests denied by a new external Veritas
batch holding the shared resource lock. At the 23:53 UTC sample that batch
(PID 3939942, `D` state) remained the lock holder; PSI avg10 was 49.25% `some`
and 42.91% `full`, with 9.7 GiB available and 3.7 GiB swap in use. No retry
was attempted.

No source API, held capture, Reality service, Arena worker, or production
deployment was accessed. Current Frontier status remains isolated,
research-only, undeployed, and **PARTIALLY VERIFIED**. See the [mission
ledger](frontier/FRONTIER_MISSION_LEDGER.md) for exact measurements and
continuation guidance.

### Arena admission-test follow-up — 2026-10-27 23:55 UTC

After the external Veritas holder exited, the two admission-denied Arena
supervisor tests passed **2/2** in 4.34 seconds wall at **179,752 KiB peak RSS**
and zero swaps. Their process launch is fixture-replaced, so no Arena worker
started. Alongside the earlier combined run, all **360 selected Frontier/Arena
cases** pass across two invocations; the combined run itself still records two
environmental denials. The retry began with the global lock free, PSI avg10 at
0%, and 10 GiB available. The isolated Frontier build and browser check also
pass for commit `305814b`; no production deployment or source request occurred.

### Full web regression — 2026-10-27 23:56 UTC

The full web unit suite passes **40/40 across seven files** in 15.55 seconds
reported / 15.97 seconds wall at **300,960 KiB peak RSS**, zero swaps. This
includes the Frontier component suite and the other Mission Control views.

### Full Frontier browser regression — 2026-10-27 23:57 UTC

The Frontier Playwright spec passes **4/4** in 11.5 seconds reported / 12.05
seconds wall at **192,280 KiB peak RSS**, zero swaps. It verifies Exchanges
history loads without collection/source POSTs, replay history submits no job,
fixture-only settlement review, and responsive bounded graph exploration.
The run used temporary API/data roots and did not call an exchange endpoint.

### Frontier collection acceptance follow-up — 2026-10-28 00:00 UTC

Commit `a7996f9` adds held-source history filtering and corrupted checkpoint
chain regressions. The focused collection module/API tests pass **21/21** in
6.53 seconds wall at **87,676 KiB peak RSS**, zero swaps; Ruff and
`git diff --check` pass. Verification used fake adapters and temporary storage
and made no source request. At 00:00:12 UTC, the shared admission lock was
free, PSI avg10 was 0.64% `some` / 0.58% `full`, and 10 GiB was available.
Frontier remains research-only, undeployed, and **PARTIALLY VERIFIED**. See the
[mission ledger](frontier/FRONTIER_MISSION_LEDGER.md) for the current evidence
and continuation notes.

### Frontier missing-adapter API guard — 2026-10-28 00:02 UTC

Commit `169bfa2` gives finite collection start and resume a clear HTTP 409 when
a venue adapter is unavailable, before the collection journal is touched. The
collection API tests pass **6/6** in 2.52 seconds wall at **84,136 KiB peak
RSS**, zero swaps; Ruff and `git diff --check` pass. No source request or Arena
worker ran. At 00:02:40 UTC the shared Arena lock was held by PID 3950719 and
memory PSI avg10 was 41.99% some / 37.85% full, so Arena-dependent verification
is deferred pending a fresh admission check. Frontier remains research-only,
undeployed, and **PARTIALLY VERIFIED**; see the [mission ledger](frontier/FRONTIER_MISSION_LEDGER.md).

### Frontier adapter-unavailable responses — 2026-10-28 00:04 UTC

Commit `01ffe05` extends the HTTP 409 missing-adapter response across source
probe routes. A focused regression covers collection start/resume and generic
discovery against an empty registry (**1/1**, 0.65 seconds, 75,800 KiB peak
RSS, zero swaps). Ruff and `git diff --check` pass. At the 00:04:26 UTC
pre-test sample, PSI avg10 was 11.06% some / 9.93% full, avg60 was 33.28%
some / 29.88% full, 10 GiB was available, and the shared Arena lock was free.
No source request or Arena worker ran. Frontier remains research-only,
undeployed, and **PARTIALLY VERIFIED**; see the [mission ledger](frontier/FRONTIER_MISSION_LEDGER.md).

### Frontier collection history when an adapter is absent — 2026-10-28 00:05 UTC

Commit `b2e3eed` confirms that saved paused-run metadata remains inspectable
without a registered adapter, while history reports `network_called: false` and
resume remains disabled with a clear reason. The focused test passes **1/1**
in 0.69 seconds at **72,864 KiB peak RSS**, zero swaps. Ruff and
`git diff --check` pass. The pre-test resource sample recorded PSI avg10 below
1%, 10 GiB available, and no Arena lock holder. No source request or worker
ran. Frontier remains research-only, undeployed, and **PARTIALLY VERIFIED**;
see the [mission ledger](frontier/FRONTIER_MISSION_LEDGER.md).

### Frontier source terms refresh — 2026-10-28

Official terms were reviewed read-only. Kalshi's own-trading/data-storage
restriction remains incompatible with unapproved Frontier research use. Kraken
research retention and applicable regional terms remain unresolved; its public
Spot REST guidance is one request per second or less, matching the adapter
default. Coinbase allows limited personal or organizational research but also
restricts some derived-data, valuation, and AI/ML uses; the existing exact-term
version gate remains unchanged and is not a general permission grant. No API
or capture was accessed and no source config changed. See the [source-data
terms review](frontier/SOURCE_DATA_TERMS_REVIEW_2026-10-27.md). Frontier remains
research-only, undeployed, and **PARTIALLY VERIFIED**.

### Frontier funding-currency browser acceptance — 2026-10-28 00:27 UTC

Commit `86b79fe10b6aed82dabbe3e40ea01e08923ad744` adds a fixture-backed browser regression for explicit venue-local FX assumptions. The full Frontier Python suite passes **322/322**, the web unit suite **40/40**, and the configured browser suite **12/12**. Python peak RSS was **364,312 KiB** with zero swaps. Browser tests used isolated demo services; they do not establish a live FX source, cross-venue executable funding, source permission, or production readiness. Frontier remains research-only, undeployed, and **PARTIALLY VERIFIED**. See the [engineering report](frontier/FRONTIER_ENGINEERING_REPORT.md) and [mission ledger](frontier/FRONTIER_MISSION_LEDGER.md).

### Frontier API registry typing — 2026-10-28 00:35 UTC

Commit `480ba629171c855086cd375a34e688bbc72fdbcb` types the Frontier API router against `AdapterRegistry`, removing its `Any` return diagnostic. Strict mypy passes for the API module; a no-network API overview test passes **1/1**. Ruff and formatting pass. The earlier 322/40/12 suite results are unchanged; they were not rerun after this annotation-only change. Frontier remains research-only, undeployed, and **PARTIALLY VERIFIED**.

### Frontier discovery-scope Arena comparison — 2026-10-28 02:40 UTC

Code commit `d59c4a8e66af7d525e65b70d90c268d3eaa92cfe` adds a saved-evidence
comparison of Polymarket-only, per-venue, and cross-venue discovery scopes,
including a hash-pinned Arena artifact API and a native Mission Control view.
The same deterministic calculators run in every arm; this measures coverage
differences in one bounded evidence window, not independent algorithm
performance or exchange-wide opportunity prevalence. Source probes remain
explicit and are not triggered by this flow.

The web unit suite passes **40/40**, TypeScript, ESLint, Prettier, Ruff,
Python compilation, and the Vite production build pass, and one isolated
Playwright history test passes **1/1**. The broader Frontier/related-Arena
selection has **375 passes and six existing Arena job-supervision failures**:
the shared admission lock was held by an active Veritas batch, so worker cases
remained queued or were rejected before launch. That batch was left untouched.
The follow-up mypy check was stopped during memory PSI at 30.44% `some` / 27.78%
`full` avg10 and 331 MiB swap free. The new comparison module's two initial
local mypy findings were fixed, but full strict typing for this checkpoint is
unverified. No exchange request or supervised discovery worker was run.

Frontier remains **PARTIALLY VERIFIED**, isolated, research-only, undeployed,
and not production-ready. See the [engineering report](frontier/FRONTIER_ENGINEERING_REPORT.md)
and [mission ledger](frontier/FRONTIER_MISSION_LEDGER.md) for exact evidence and
continuation steps.

### Discovery-snapshot latest-book correction — 2026-10-28 02:45 UTC

Commit `3f084a99732b0cb610bafe18aacaf13fb54a92c2` ensures the discovery-scope
Arena snapshot contains one latest locally received book per instrument when
the observation store holds repeated snapshots. The pinned book retains its
immutable observation ID. The Frontier API module passes **53/53**; focused
scope/Arena tests pass **4/4**; no source probe or worker was run. Peak RSS was
284,280 KiB for the API module and 194,060 KiB for the focused comparison set,
with zero swaps. This fixes snapshot construction but does not establish quote
freshness, cross-venue synchronization, supervisor execution, or profitability.
Project Frontier remains **PARTIALLY VERIFIED**.

### Frontier terms and supervised worker checkpoint — 2026-10-28 03:03 UTC

A read-only refresh of official Kalshi, Kraken, and Coinbase materials confirms
that unauthenticated endpoints and published rate limits do not establish
permission for Frontier research, retention, or distribution. Kalshi and
Kraken probes and new use of held captures remain blocked; Coinbase's exact
terms-version acknowledgement is not blanket permission. No API request or
capture read occurred. Details are in the
[source-data terms review](frontier/SOURCE_DATA_TERMS_REVIEW_2026-10-27.md).

One synthetic `frontier_discovery` job completed through the actual Arena host
admission gate and transient systemd worker. Its hash-pinned input and artifact
were confined to a temporary directory; the output passed integrity
verification, and the unit exited successfully. Systemd exposed 512 MiB
memory, no swap, 50% CPU, and AF_UNIX-only networking. One process peak-RSS
measurement differed from the cgroup memory peak; both figures are preserved
separately without treating them as equivalent. This one fixture run closes
supervisor execution for a bounded case, not sustained capacity, live source
validity, or production readiness. At 03:03:40 UTC during post-run review,
memory PSI avg10 was 49.40% some / 41.21% full; wait for a fresh admission
check before another heavy workload.
Frontier remains isolated, research-only, undeployed, and **PARTIALLY
VERIFIED**.

### Frontier/Arena regression checkpoint — 2026-10-28 03:08 UTC

The serial Frontier plus selected Arena suite passed **380/383** in 89.51
seconds wall at **377,184 KiB peak RSS**, with zero swaps or socket messages.
One failure was a stale assertion for an expanded resource-limit message; two
command-assembly tests were denied by the shared admission lock, which was held
by external Veritas batch PID 4112565. That batch was left untouched. The test
expectation is updated and the two command tests now isolate launch-command
checks from host admission, but the corrections are not yet tested. The
03:08:37 UTC sample measured memory PSI avg10 36.19% some / 30.12% full; wait
for that process to release the lock and remeasure before more admission-bound
tests. Current evidence and exact commands are in the
[engineering report](frontier/FRONTIER_ENGINEERING_REPORT.md) and
[mission ledger](frontier/FRONTIER_MISSION_LEDGER.md).

### Combined Frontier/Arena regression verified — 2026-10-28 03:12 UTC

The corrected serial Frontier plus selected Arena regression now passes
**383/383** in 91.74 seconds wall at **377,372 KiB peak RSS**, with zero swaps
or socket messages. The stale resource-limit message assertion and two
host-lock-dependent command tests were corrected; Ruff and formatting also
pass. This is not a full MIDAS repository run. A scoped strict mypy check for
the discovery comparison module was deferred when a fresh resource gate denied
it for `host_memory_pressure`. At 03:12:36 UTC memory PSI avg10 was 34.89% some
/ 32.22% full and external Veritas batch PID 4117533 held the shared Arena
lock. It was left untouched. Frontier remains isolated, research-only,
undeployed, and **PARTIALLY VERIFIED**.

### Scoped Frontier type checks completed — 2026-10-28 03:15 UTC

After two separate 768-MiB Arena admission checks passed, strict mypy passed
for `packages/midas/frontier/discovery_comparison.py` and `apps/api/frontier.py`
with imported-module diagnostics suppressed. The API check took 21.74 seconds;
this is not a repository-wide typing result. At 03:15:11 UTC memory PSI avg10
was 0.00% some / full and I/O PSI avg10 was 0.62% some / 0.61% full, with
about 10.1 GiB available memory and 333 MiB free swap. This dated sample is
not a sustained-capacity measurement. No exchange source, test database,
worker, protected service, or recording was accessed. The overall mission
remains **PARTIALLY VERIFIED**, research-only, isolated, and undeployed; see
the [mission ledger](frontier/FRONTIER_MISSION_LEDGER.md) and
[engineering report](frontier/FRONTIER_ENGINEERING_REPORT.md).

### Polymarket metadata and response-size checkpoint — 2026-10-28 03:25 UTC

A read-only, 2-request Polymarket Gamma probe stored one hash-verified
20-market page in the ignored local database
`data/public-captures/frontier-polymarket-20261028T031822Z-pqzzdf1m/frontier.sqlite3`.
Every returned market had two instruments and rule text; one had a resolution
authority, none had a close time, and none had verified/exhaustive payoff
metadata. The event-detail follow-up was rejected at the 256-KiB response cap;
the pre-change path did not preserve response size/status metadata. No held
venue data or protected service was accessed.

Transport, API, and finite-collector paths now persist bounded rejection
metadata without storing the rejected body, with v1 record compatibility
covered in new tests. This source and implementation checkpoint remains
bounded; the verification follow-up below records focused test results and the
full-suite blocker.

### Response-rejection verification and full-suite admission — 2026-10-28 03:27 UTC

The focused transport/API/collection/schema selection passed **9/9** in 3.19
seconds after a fresh 768-MiB admission check. Strict mypy passed for five
changed production modules; Ruff check/format and whitespace checks pass. The
full `tests/frontier` suite was not started: a later preflight found
`resource_admission_lock_busy`. At 03:27:25 UTC memory PSI avg10 was 14.17%
some / 12.55% full and external Veritas PID 4128967 held the shared Arena
lock. That batch was left untouched. Full Frontier regression after the raw
observation schema change remains pending. No additional source request,
protected service action, or deployment occurred. Frontier remains isolated,
research-only, **PARTIALLY VERIFIED**, and undeployed.

The official [Polymarket Gamma discovery reference](https://docs.polymarket.com/market-data/discover-markets)
documents event fetch as one object with an embedded `markets` array, plus
separate market-ID reads and paged market-keyset listing. It does not document
child-market pagination keyed by Gamma event ID. The event response-size limit
therefore remains an adapter constraint; hydrating known market IDs separately
cannot establish an exhaustive outcome set. This documentation check made no
additional market-data requests.

### Frontier regression after response-size diagnostics — 2026-10-28 03:32 UTC

After commit `c91bdf43f125b15279907d4ca53291f377b58387`, the complete Frontier
and selected Arena regression passed **387/387** in 90.74 seconds pytest time
(92.21 seconds process wall), with **379,240 KiB** peak RSS, zero swaps, and
zero socket messages. A fresh 768-MiB preflight admitted the run. At the
post-run sample, memory PSI avg10 had risen to **41.42% some / 36.83% full**;
the gate denied further work while external Veritas PID **4132908** held the
shared lock. It was not interrupted. This supersedes the earlier dated note
that the full Frontier suite had not yet been rerun after schema v2. The full
MIDAS repository suite remains outside this checkpoint; Frontier remains
isolated, research-only, **PARTIALLY VERIFIED**, and undeployed.

The Frontier workspace also now renders saved response-rejection evidence
from structured probe errors, including body-omission state and bounded
response metadata. A fixture regression was added, but it has not yet run.
Frontend typecheck, lint, formatting and build are also pending a fresh safe
resource check; the post-run host gate at 03:32 UTC denied further work under
high memory PSI with external Veritas PID 4132908 holding the shared lock.

The focused source-failure evidence fixture then passed **1/1** after Prettier;
web typecheck, targeted ESLint, and Prettier check passed. The wider web suite
was not started after a fresh 03:37 UTC gate found memory PSI at 31.75% some /
25.89% full and external Veritas PID 4136998 holding the shared lock. Browser
E2E and production build remain unverified for this change. No source probe or
deployment occurred.

### Legacy integration regression addendum — 2026-10-28 04:16 UTC

From `/home/charlie/midas-frontier`, `tests/integration/test_api.py` passed
**5/5** and `tests/integration/test_milestone2_journey.py` passed **5/5**.
Peak RSS was **167,956 KiB** and **134,632 KiB**, respectively; both runs had
zero swaps and zero socket messages. The tests use temporary databases and
fixture/mock transports. They cover offline Frontier API/probe-denial
contracts, legacy read-only transport and paper-research behavior, and do not
validate deployed services. At 04:16:39 UTC, memory PSI avg10 was 0.00% some /
0.00% full, I/O PSI avg10 1.04% / 1.04%, approximately 10 GiB was available,
and no process held the shared Arena lock. The full MIDAS suite and production
deployment remain unverified; Frontier is still research-only and
**PARTIALLY VERIFIED**.

### Frontier status checkpoint — 2026-10-28 04:18 UTC

The 04:16 offline legacy API and paper-research regressions pass **10/10** in
temporary roots. The Frontier code checkpoint also has the **352/352** Python
suite, **40/40** web tests, **6/6** Frontier browser scenarios, the temporary
production build, and **38/38** selected Arena consumers documented. No live
cross-venue equivalence is established; current source-use holds remain in
force. Frontier is isolated, research-only, **PARTIALLY VERIFIED**, and
undeployed.

At 04:17 UTC, the optional storage/recording regression was deferred after a
shared Arena lock holder was found. Read-only inspection identified PID
4170342 as `scripts/veritas_gap_detail_v2_batch.py` under
`midas-veritas-gap-detail-v2.service`. At 04:18:00 UTC memory PSI avg10 was
48.45% some / 43.86% full, I/O PSI avg10 0.79% / 0.79%, approximately 10 GiB
was available, and 333 MiB of swap was free. The external process was left
untouched; no additional tests or resource-bearing checks were started.

### Follow-up after shared Arena lock cleared — 2026-10-28 04:19 UTC

The previously deferred temporary-root storage-query and recording-isolation
tests passed **7/7**; the focused API/Reality protected-service
materialization guard passed **1/1**. Peak RSS was 103,244 KiB and 72,156 KiB,
respectively, with zero swaps and zero socket messages. A source-tree audit
found no `data/frontier/live-probes` path references under tests, packages, or
apps, without opening held data. At 04:19:47 UTC memory PSI avg10 was
0.01% some/full, avg60 9.38%/8.50%, avg300 13.11%/11.79%; I/O PSI avg10 was
1.27%/1.08%; about 10 GiB was available and the shared Arena lock was free.
This closes those specific checks. Broader suite work remains subject to a
fresh resource gate; Frontier remains research-only, undeployed, and
**PARTIALLY VERIFIED**.

### Held-source boundary regression — 2026-10-28 04:20 UTC

`tests/frontier/test_held_capture_source_boundary.py` passed **2/2**. It
confirmed no current Python test references the held capture directory and
that direct, symlink, traversal, and `dir_fd` access attempts are denied under
a temporary directory. Peak RSS was 43,732 KiB; there were zero swaps or
socket messages. No preserved capture was opened. At 04:20:34 UTC memory PSI
avg10 was 0.00% some/full, avg60 4.36%/3.95%, avg300 11.19%/10.07%, I/O PSI
avg10 0.87%/0.69%, and the shared Arena lock was free. This strengthens the
offline source boundary evidence but does not release any source-use hold.

### Combined Frontier/Arena regression — 2026-10-28 04:23 UTC

The current `tests/frontier` suite and selected Arena discovery, replay,
timeline, and job modules passed **390/390 in one invocation** in 91.63 seconds
pytest time (93.00 seconds process wall), at **380,624 KiB peak RSS** with zero
swaps and socket messages. This is not a full MIDAS repository regression or
production worker check. The post-run sample at 04:23:44 UTC showed memory PSI
avg10 39.41% some / 35.46% full, avg60 29.70% / 26.17%, avg300 16.08% / 14.23%,
and I/O PSI avg10 8.41% / 8.00%. External Veritas PID 4174453 held the shared
Arena lock; it was left untouched, and no further resource-bearing checks were
started. Frontier remains research-only, undeployed, and **PARTIALLY VERIFIED**.

### Frontier saved-history persistence and complete browser regression — 2026-10-28 07:06 UTC

Code commit `3251941` adds an opt-in seeded browser integration for the saved
price-history inspector. Its deterministic seeder writes 21 fixture captures
and 21 replay artifacts to a fresh temporary Frontier store; the browser then
reads both pages through the real local API, submits one two-series replay,
checks the saved result and source lineage, and pages older records. It asserts
zero source-probe requests. The separate integration passes **1/1**. The full
default browser suite reports **15 passed, 1 skipped**; the seeded test is the
intentional skip. It covers Frontier, Arena, Laboratory, Paper, Readiness,
Reality, and Veritas.
The frontend unit suite also passes **41/41**, and typecheck, lint, formatting,
and production build pass. No public endpoint, order, protected service, or
production database was accessed.

At `2026-10-28T07:05:07Z`, post-browser memory PSI avg10 was **0.00% some/full**
and I/O PSI avg10 was **1.09% some / 0.88% full**; about **10 GiB** memory was
available, and no process held the shared Arena lock. Further
resource-bearing tests were deferred because I/O `some` exceeded the 1%
threshold. Frontier remains isolated, research-only, undeployed, and
**PARTIALLY VERIFIED**; current source-use holds and cross-venue evidence gaps
remain unchanged. See the [Frontier mission ledger](frontier/FRONTIER_MISSION_LEDGER.md)
for continuation and admission details.

### Frontier Laboratory/Arena study-history view — 2026-10-28 07:13 UTC

The isolated Frontier branch adds a **Frontier research** tab to the existing
Laboratory. It reads Arena's bounded discovery-job catalog, lets the user
select a retained job, and displays a completed study only after the existing
API verifies its artifact hashes. It reuses the Arena job and snapshot rather
than converting multi-market inputs into the legacy single-market Laboratory
campaign schema. The tab does not request source data or submit work.

The focused Laboratory tests (4/4), full frontend unit suite (43/43), and
TypeScript check passed before a final semantic markup refinement. The modified
card markup has not yet been rechecked. At `2026-10-28T07:12:59Z`, memory PSI
avg10 was **47.23% some / 42.98% full**; no additional resource-bearing
verification was started. Commit `afcc726` also adds a fixture-routed
Playwright case for this view, but it has not been run; `91e61d7` makes its
reproducibility assertion open the disclosure first. This UI-level
integration does not verify Arena
supervisor completion, a populated live-store browser flow, or source quality.
Frontier remains isolated, research-only, **PARTIALLY VERIFIED**, and
undeployed. Continue with a fresh host admission sample before rerunning the
focused test, frontend lint/format checks, and typecheck.

### Protected Arena lock recheck — 2026-10-28 07:17 UTC

At `2026-10-28T07:17:18Z`, PID **124298** (`midas-veritas-gap-detail-v2.service`)
held `/home/charlie/midas/data/arena/.global-admission.lock`. The worker was
left untouched. Memory PSI avg10 was **36.43% some / 28.38% full** and I/O PSI
avg10 **0.02% some / 0.02% full**. The earlier check used a relative path in
the Frontier worktree, not the protected shared lock, and is superseded. No
resource-bearing checks were started; rerun only after memory pressure clears
and the exact protected lock is free.

### Persisted Laboratory/Arena browser case queued — 2026-10-28 07:22 UTC

Commit `a875ee2` extends the explicit seeded browser setup with a
content-addressed, fixture-only Arena discovery artifact and a Playwright case
that reads it through the actual local API and Laboratory UI. The seeder writes
only into a validated temporary browser root and starts no worker. This new
path remains unrun. At `2026-10-28T07:21:58Z`, memory PSI avg10 was
**39.28% some / 20.15% full**; PID **124298** still held the protected Arena
admission lock. I left it untouched and deferred browser/test/build work until
the lock clears and memory pressure drops.

### Laboratory/Arena saved-study verification complete — 2026-10-28 07:30 UTC

After PID 124298 exited, the fixture-backed API/browser path passed. The
opt-in seeded suite passed **2/2** against temporary Frontier and Arena stores;
the Laboratory-specific browser case passed **1/1**. The full default browser
suite passed **16** with **2** expected opt-in skips. Frontend unit tests passed
**43/43**; TypeScript, lint, formatting, Ruff, and production build passed. The
build retains the existing 511.30 kB main and 544.41 kB Chart advisories. At
`2026-10-28T07:28:12Z`, post-run memory PSI avg10 was 0%, I/O PSI avg10 was
0.01%, about 10 GiB was available, and the protected Arena lock was unheld.
The saved job is a synthetic Polymarket-only fixture; this proves the local
storage/API/UI path, not live-source or cross-venue matching. Frontier remains
isolated, research-only, **PARTIALLY VERIFIED**, and undeployed.

### Frontier workspace bundle split — 2026-10-28 07:33 UTC

Commit `87a6a3c` moves Laboratory, Arena, and Reality behind lazy navigation
boundaries with visible loading states. The production web build passes and
the entry JavaScript chunk is **367.85 kB**, down from the previously recorded
**511.30 kB** (about 28%). Those three workspaces are emitted as separate
chunks. The **544.41 kB** Chart/ECharts chunk advisory remains; Mission Control
uses charts on its initial view, so the entry-chunk change is not a 28% claim
about total initial transfer. The complete web unit suite passes **43/43** and
the default browser suite passes **16** with **2** opt-in seeded-store skips.
The seeded cases were run separately after the code split and passed **2/2**,
including the populated Arena-to-Laboratory path. TypeScript build, ESLint, and
Prettier checks pass. No source, protected store, or production service was
accessed. At 07:35:37 UTC memory PSI avg10 was **0.00% some/full**, I/O PSI
avg10 was **0.44% some / 0.28% full**, about **10 GiB** was available, and the
shared Arena lock was free. Frontier remains isolated,
research-only, **PARTIALLY VERIFIED**, and undeployed.

### Frontier verification follow-up — 2026-10-28 07:37 UTC

After commit `87a6a3c`, both opt-in seeded browser scenarios passed **2/2**,
including the populated Arena discovery artifact rendered through lazy-loaded
Laboratory. Commit `92ab4e8` then tightened the candidate time contract: naive
observation timestamps now fail validation and aware offsets normalize to UTC.
The affected economics/replay module passed **50/50**; strict mypy and Ruff
checks passed for the changed Python code and tests. At 07:37:17 UTC, memory
PSI avg10 was 0.00%, I/O PSI avg10 was **0.01% some / 0.00% full**, about
**10 GiB** was available, and the shared Arena lock was unheld. No exchange
source or protected store was accessed. Full Frontier regression after the
timestamp change remains pending; overall Frontier is still research-only and
**PARTIALLY VERIFIED**.

### Fee and raw observation time validation — 2026-10-28 07:39 UTC

Commit `a7df7e9` extends timezone validation to fee evidence/effective/expiry
times and raw observation request/receipt times. Naive values are rejected and
aware offsets normalize to UTC. The affected economics/replay and storage
modules pass **73/73**; strict mypy and Ruff checks pass. At 07:39:41 UTC memory
PSI avg10 was 0%, while I/O PSI was **2.52% some / 1.96% full**, so the
remaining Frontier regression was deferred. The shared Arena lock was free;
no production service, source, or protected store was touched. Overall Frontier
remains isolated, research-only, and **PARTIALLY VERIFIED**.

### Arena snapshot time guard — 2026-10-28 07:42 UTC

Commit `6d5e82b` closes a related issue in Arena snapshot builders: replay,
discovery-scope, and event-time functions now reject naive time inputs before
converting them to UTC and hashing the snapshot. The three affected Arena test
modules pass **25/25**; strict mypy and Ruff pass. At 07:42:38 UTC memory PSI
avg10 was 0%, but I/O PSI was **1.64% some / 1.08% full**, so remaining broad
regression was deferred under the 1% admission gate. The shared Arena lock was
free and no worker, source, production service, or protected store was touched.
Frontier remains isolated, research-only, and **PARTIALLY VERIFIED**.

### Workspace load-failure containment — 2026-10-28 07:47 UTC

Commit `8f5bf83` wraps lazy Mission Control workspaces in accessible error
boundaries. A failed workspace chunk now displays a contained alert with a
refresh instruction instead of taking down the workspace view. The complete
web unit suite passes **44/44**, TypeScript, ESLint, and Prettier pass, and the
production build succeeds. Default browser E2E passes **16** with **2**
expected opt-in skips; seeded Frontier/Arena browser E2E passes **2/2** using
disposable `/tmp` fixtures. Vite still reports the **544.41 kB** Chart chunk
advisory. At 07:47:03 UTC, memory PSI avg10 was 0%, I/O PSI avg10 was **0.07%
some / 0.04% full**, and about **10 GiB** was available. No exchange source,
protected store, production service, or worker was accessed. Overall Frontier
remains isolated, research-only, and **PARTIALLY VERIFIED**.

### Independent audit timestamp hardening — 2026-10-28 07:58 UTC

Commit `e1946bc` advances the independent economic verifier to v13 and checks
typed candidate, scenario, market, book, relationship, and joint-state inputs
for timezone-aware timestamps before any arithmetic or temporal comparison.
This closes the path where `model_copy(update=...)` could bypass ordinary
Pydantic timestamp validators and make Python interpret a naive value in the
host's local timezone. The verifier now returns incomplete evidence for those
inputs when a candidate has a constructed position. The full Frontier API
module passes **56/56** after the commit; the affected economics/storage slice
passed **74/74** after the recursive preflight but before the final runtime
type guard in the epoch converter. Ruff, Ruff format, strict mypy for the
changed source modules, and `git diff --check` pass.
The API run emitted the existing Starlette/httpx TestClient deprecation warning.
Afterward, at 07:57:51 UTC, memory PSI avg10 was 0%, I/O PSI was **7.28% some /
5.30% full**, and about **10 GiB** remained available. The broader post-commit
economics/storage rerun is deferred. No source, production service, worker, or
protected store was accessed. Frontier remains **PARTIALLY VERIFIED**.

### Price-history replay timestamp revalidation — 2026-10-28 08:02 UTC

Commit `dd4882d` revalidates each serialized bounded price-history capture
before deterministic replay. That closes a nested-model-copy path where a
naive historical point could reach `.timestamp()` and be interpreted in the
host timezone. New outputs identify the behavior as replay v2. The history
replay module passes **5/5**, including the new nested timestamp rejection,
append-only storage, and schema migration cases; its API probe/replay test
passes **1/1**. Ruff, Ruff format, strict mypy for `historical_replay.py`, and
`git diff --check` pass. At 08:01:50 UTC, memory PSI avg10 was 0%, I/O PSI
avg10 was **1.09% some / 0.68% full**, and about **10 GiB** was available. The
route test used a mocked source transport. No source, protected store, worker,
or production service was accessed. Frontier remains research-only and
**PARTIALLY VERIFIED**.

### Frontier independent audit with no position legs — 2026-10-28 13:42 UTC

Commit `2d8e9fb` clears prior P&L, capital, sensitivity, and timing fields when
no position legs remain. Previously economic classifications now become
`INCOMPLETE EVIDENCE`; a clean discrepancy-only label is preserved. The
focused regression, strict mypy, and Ruff pass. The 82-case economics/replay
module was deferred after memory PSI avg10 reached **48.10% some / 44.12%
full**. No exchange source, capture, protected store, collector, or production
service was accessed. Frontier remains research-only and **PARTIALLY VERIFIED**.

### Exact-tree timestamp regression checkpoint — 2026-10-28 08:03 UTC

The pending verifier rerun is now complete. On the final code tree, the
independent economics/replay, storage, and historical-replay modules passed
**79/79**. The full Frontier API module had passed **56/56** after audit v13;
the price-history API case passed **1/1** after replay v2. Ruff, Ruff format,
strict mypy for the changed sources, and whitespace checks pass. The earlier
74-case status is superseded. At 08:02:44 UTC, memory PSI avg10 was **0%**,
I/O PSI avg10 was **0.15% some / 0.00% full**, about **10 GiB** was available,
and no shared Arena lock holder was present. No source, worker, protected store,
or production service was accessed. Overall Frontier remains **PARTIALLY
VERIFIED**: the broader single-process suite and scientific/deployment gates
remain open.

### Adapter timestamp parser contract — 2026-10-28 08:04 UTC

Commit `2eff73e` adds a fixture-only contract test for `parse_time`: a naive
ISO timestamp string yields no timestamp, while `+02:00` and `Z` inputs
normalize to the expected UTC instants. The full adapter test module passes
**68/68**; Ruff, Ruff format, and `git diff --check` pass. At 08:04:42 UTC,
memory PSI avg10 was 0%, I/O PSI avg10 was **0.02% some / 0.00% full**, and
about **10 GiB** was available. The change exercised no network transport,
production service, worker, or protected store. Frontier remains **PARTIALLY
VERIFIED**.

### Full Frontier suite resource-gated attempt — 2026-10-28 08:07 UTC

The final tree collected 378 `tests/frontier` tests. A single fixture-backed
run passed 193 before live I/O PSI rose to **12.91% some / 10.15% full**; the
process was stopped with SIGINT. The remaining 185 cases did not run, so the
single-process suite remains **PARTIALLY VERIFIED**. `/usr/bin/time -v`
reported 68.97 seconds wall time, 347,088 KiB peak RSS, and zero process
swaps. After stopping, I/O PSI remained **4.49% some / 3.33% full**, while
memory PSI stayed at 0% and about 10 GiB remained available. No network source,
Arena job, worker, protected store, or production service was started. More
test or replay work waits for a fresh admitted sample.

### Nested price-history point revalidation — 2026-10-28 08:09 UTC

Commits `2e73476` and `aa88b03` close and type-check a nested-instance
validation gap in `PriceHistorySeries`: copied point models are reparsed before timestamp range checks, so a naive
timestamp or invalid price cannot bypass `HistoricalPricePoint` validators.
The historical-replay module passes **6/6**, the adapter module passes **68/68**,
and the targeted history-probe/replay API case passes **1/1**. Strict configured
mypy passes for `models.py`; Ruff check, Ruff format, and `git diff --check`
pass. At 08:11:12 UTC, memory PSI avg10 was 0%,
I/O PSI avg10 was **0.90% some / 0.74% full**, and about 10 GiB was available.
The history module took 1.81 seconds, peaked at 57,708 KiB RSS, and used no
swap. The tests used temporary or mocked state. The API case emitted the
existing Starlette/httpx deprecation warning. The full suite remains partial
after 193/378 cases passed before I/O pressure forced a stop. Frontier remains
**PARTIALLY VERIFIED**.

### Held-capture test guard — 2026-10-28 08:13 UTC

An attempted offline adapter-to-relationship test was denied by
`tests/frontier/conftest.py` with `PermissionError: Frontier tests may not
access held source captures` before reading the protected file. The test was
removed; no copy or fixture conversion was made. Existing synthetic event
group tests remain valid, but live cross-venue relationship evidence and
economic equivalence remain open. No network, service, worker, or protected
store was accessed. Frontier remains **PARTIALLY VERIFIED**.

### Full Frontier Python suite — 2026-10-28 08:18 UTC

After replacing three stale schema-6 test literals with `str(SCHEMA_VERSION)`,
the exact final `tests/frontier` tree passes **379/379** in one process (29.51s
pytest time; 31.00s wall). The tmpfs run peaked at 378,216 KiB RSS, used no
swap, and recorded zero filesystem input. It emitted the existing
Starlette/httpx TestClient deprecation warning. Pre/post memory PSI avg10 was
0%; I/O PSI was **0.02%** pre-run and **0.02% some / 0.00% full** post-run,
with about 10 GiB available. No public source, worker, protected store,
production service, or Arena job was accessed. Frontier remains **PARTIALLY
VERIFIED** because held-source validation, broader MIDAS/browser gates, and
production readiness remain open.

### Coinbase source-use hold integrity — 2026-10-28 11:44 UTC

Code commit `ca14e37` prevents Coinbase's source-use hold from being cleared
through terms acknowledgement alone, copied config values, generic config
substitution, or an injected transport with a different configuration. Offline
parser/API fixtures use an in-memory test transport while retaining a held
config. Ruff check, Ruff formatting, and `git diff --check` pass; tests remain
unrun. At `11:43:51Z`, memory PSI avg10 was **6.41% some / 5.82% full**, I/O
PSI was **0.59% some / 0.45% full**, about **10 GiB** was available, and swap
was **3.5/4 GiB** used. The prior `418/418` result is for `1dd0987`, before
this change. No live source, protected service, or deployment was used.
Frontier remains research-only and **PARTIALLY VERIFIED**.

Commit `782df89` closes the API-side hold gap across all 11 public probe
routes. The pre-fix focused Coinbase run passed 12/13 tests; its one failure
showed the route let a test-only transport through before the source's read
quarantine hid the resulting fixture record. The route now rejects held
sources before transport work. The updated test remains unrun: after the first
run, memory PSI avg10 reached **52.19% some / 46.63% full** and I/O PSI reached
**1.10% some / 0.75% full**. No real source was contacted; Frontier remains
**PARTIALLY VERIFIED**.

Commit `92b5bf0` also aligns the Kraken fixture transport with the exact
`KrakenSpotConfig` supplied to its adapter. Ruff check/format pass for the
fixture; no tests were run under the current memory PSI gate.

### Frontier probe-source hold continuation — 2026-10-28 11:53 UTC

Commits `782df89`, `9776427`, and `4b8c9f0` gate held-source use in all 11
public probe routes and report effective probe eligibility. The Coinbase API
route now returns HTTP 409 before transport access while the source is held.
The corrected Frontier suite passed **420/420** before the final type-narrowing
refactor, with **378,920 KiB** peak RSS and zero swaps or filesystem input.
That run emitted the existing Starlette/httpx deprecation warning. Strict
mypy found 13 optional-config narrowing errors in the prior API guard; the
current helper returns the validated config, but exact-tree mypy and tests
remain pending. At `11:53:54Z`, memory PSI avg10 was **1.16% some / 1.02%
full**, I/O PSI **0.91% some / 0.83% full**, and about **10 GiB** was
available. No live source, protected service, or deployment was used.
Frontier remains research-only and **PARTIALLY VERIFIED**.

### Exact Frontier source-hold verification — 2026-10-28 11:55 UTC

Strict mypy passes for the API hold guard, base adapter, and Coinbase adapter.
The exact current `tests/frontier` tree passes **420/420** in 29.02 seconds
(30.50 seconds wall), with **378,276 KiB** peak RSS, zero swaps, zero
filesystem input, and zero socket messages. One existing Starlette/httpx test
client deprecation warning remains. Pre-run memory PSI avg10 was 0.00% and
I/O PSI was **0.85% some / 0.70% full**; post-run memory remained 0.00% and
I/O was **0.91% some / 0.63% full**, with about 10 GiB available. All 11
probe routes reject a held source before transport work, and the source
listing reports effective probe status. Live cross-venue evidence, broader
MIDAS/browser acceptance, and deployment remain open; Frontier is **PARTIALLY
VERIFIED** overall.

### Broad MIDAS test admission — 2026-10-28 11:57 UTC

No repository-wide test run was started. At `11:57:28Z`, memory PSI avg10
was **39.00% some / 35.46% full**, I/O PSI **0.93% some / 0.93% full**, and
about 10 GiB was available. A read-only scan found legacy tests that reference
`/home/charlie/midas/data/laboratory-final` and launch subprocesses or local
servers. Review their data roots before a broad invocation. The exact Frontier
suite remains **420/420** and strict mypy passes as recorded above; broader
MIDAS/browser checks and production eligibility remain **PARTIALLY VERIFIED**.

### Frontier collection journal boundaries — 2026-10-28 13:24 UTC

On isolated branch `codex/frontier-20261026`, commits `3153148` and `f440fa2`
move collection-run/checkpoint validation ahead of SQLite initialization and
make run/checkpoint lookups use bounded read-only SQLite connections. Focused
invalid-write and missing/incomplete-read regressions pass **1/1 each**; strict
mypy for `packages/midas/frontier/collection.py`, Ruff check/format, and
`git diff --check` pass. Each targeted process peaked near **62 MiB RSS**, with
zero swaps, filesystem input, or socket traffic.

The full collection module and broader suites were not rerun after these narrow
changes. At `2026-10-28T13:24:39Z`, memory PSI avg10 was **0.00%**, I/O PSI was
**0.00%**, about **10.4 GiB** was available, and host CPU PSI avg10 was
**47.65%**. The untracked `data/frontier-public-probes/` directory remains
untouched. No collector, source, protected store, or production service was
accessed. Frontier remains research-only and **PARTIALLY VERIFIED**.

### Frontier source-terms refresh — 2026-10-28 13:26 UTC

The official Kalshi, Kraken, Coinbase, and Polymarket materials were refreshed
read-only. The findings support the current Kalshi/Kraken/Coinbase use holds and
confirm that Polymarket's decentralized and US exchanges have separate APIs.
The dated details are recorded in
`docs/frontier/SOURCE_DATA_TERMS_REVIEW_2026-10-28.md`; current architecture
and operations pages now link to it. No source API was called, no capture was
opened, and no permission or hold state changed. Frontier remains
research-only and **PARTIALLY VERIFIED**.

### Frontier collection journal regression — 2026-10-28 13:28 UTC

The exact `tests/frontier/test_collection.py` module passed **29/29** after
commits `3153148` and `f440fa2` in 1.94 seconds (2.33 seconds wall), with
69,124 KiB peak RSS, zero swaps, filesystem input, or socket messages. It used
temporary SQLite roots and a bounded local file-lease child process. The full
Frontier suite remains deferred: after the run at `13:28:47Z`, host CPU PSI
avg10 was **44.54%**; memory PSI was 0.00%, I/O PSI was **0.14% some / 0.03%
full**, and about **10.4 GiB** was available. No source, held capture,
protected store, collector, or production service was accessed. Frontier
remains research-only and **PARTIALLY VERIFIED**.

### Frontier Arena snapshot integrity — 2026-10-28 13:35 UTC

Commit `4788443` now revalidates replay, discovery, and timeline snapshots
before writing and revalidates job specs before constructing snapshot paths.
Six targeted corruption and happy-path tests pass; strict mypy, Ruff, and
format checks pass. Tests ran under `/dev/shm` with zero swaps, filesystem
input, or socket messages. Broader Arena/Frontier suites remain deferred while
host CPU PSI avg10 is about **48%**. No source, capture, collector, protected
store, service, or persistent job was accessed. Frontier remains research-only
and **PARTIALLY VERIFIED**.

### FrontierStore preflight boundary — 2026-10-28 13:39 UTC

Commit `c5b8822` moves encoded-size, budget, and paired-input validation ahead
of SQLite initialization for six append paths. The complete storage test module
passes **28/28** in 1.33 seconds with 70,916 KiB peak RSS and zero swaps,
filesystem input, or socket messages; strict mypy and Ruff pass. The combined
Frontier/Arena suite was held after a fresh sample showed I/O PSI avg10 at
**1.27% some / 1.24% full**. No source, capture, protected store, collector,
or production service was accessed. Frontier remains research-only and
**PARTIALLY VERIFIED**.

### Frontier missing-review-store guard — 2026-10-28 13:46 UTC

Commit `ccc44ce` prevents a relationship review for an absent target from
initializing a Frontier SQLite store. Its no-root-creation regression is added
but not run; strict mypy/Ruff and the updated storage module are pending a fresh
resource sample. At `13:46:08Z`, memory PSI avg10 was **35.83% some / 28.31%
full**, CPU PSI **29.19%**, and I/O PSI **0.09% some / 0.08% full**. No source,
capture, protected store, collector, or production service was accessed.
Frontier remains research-only and **PARTIALLY VERIFIED**.

### Frontier read-only review-target preflight — 2026-10-28 13:48 UTC

Commit `13377dc` checks a review parent through a read-only SQLite connection
before database initialization. This also covers an existing empty database;
a byte-preservation regression is committed, but neither focused case nor
post-change storage/static validation has run. At `13:48:50Z`, memory PSI avg10
was **37.45% some / 28.85% full**, CPU PSI **29.17%**, and I/O PSI **0.00%**;
about 9 GiB was available while swap usage was 3.5 GiB. The memory gate remains
exceeded. Frontier remains research-only and **PARTIALLY VERIFIED**.

### Frontier audit fail-closed verification — 2026-10-28 13:56 UTC

Commits `13377dc` and `76d388b` make missing review targets fail before SQLite
initialization and clear candidate economics when the independent audit cannot
recompute them due to an invalid scenario or missing pinned evidence. The
complete Frontier Python suite passes **452/452** in 29.16 seconds; strict
mypy, Ruff, and formatting checks pass. Peak RSS was 380,164 KiB with zero
swaps or socket traffic under `/dev/shm`. An existing Starlette/httpx
deprecation warning remains. No source, capture, production service, browser,
or Arena job was accessed. Live cross-venue evidence and source-use
authorization remain blocked; production recovery and deployment remain
deferred. Frontier remains research-only and **PARTIALLY VERIFIED**.

### Frontier dashboard browser verification — 2026-10-28 13:59 UTC

Frontend checks pass: **47/47** Vitest tests, TypeScript, ESLint, Prettier, and
the production build. The build has one advisory for a 544.51 kB minified
Chart chunk. Frontier browser E2E passes **7/7**, and seeded local fixture E2E
passes **2/2**. Both used loopback services and temporary roots; the explicit
history-probe POST was intercepted in Playwright, no request reached a venue,
and ports 18000/15173 are closed. The seeded
run wrote fixture-only history and one Arena artifact in `/tmp`. Memory PSI
avg10 remained at 0%; I/O PSI post-run was 0.08% some / 0.04% full. Live source
authorization, cross-venue evidence, production recovery, and deployment remain
open. Frontier remains research-only and **PARTIALLY VERIFIED**.

### Frontier Arena integration verification — 2026-10-28 14:00 UTC

The Frontier-specific Arena replay, timeline, and discovery tests pass
**28/28** in 3.86 seconds (4.58 seconds wall), at 200,752 KiB peak RSS and
zero swaps or socket traffic. They cover hash-pinned snapshots, held-source
filtering, result binding, and one bounded fixture worker subprocess. No
persistent Arena job or production root was used. Memory and I/O PSI avg10
were 0% before and after. The broad legacy Arena suite remains deferred; live
cross-venue permission/evidence and production recovery/deployment remain open.
Frontier remains research-only and **PARTIALLY VERIFIED**.

### Arena job supervision tests — 2026-10-28 14:03 UTC

`tests/arena/test_jobs.py` passes **16/16** in 32.55 seconds wall time, at
180,988 KiB peak RSS with zero swaps. Tests used a temporary root and their
worker processes exited. Memory PSI remained 0%, but post-run I/O PSI rose to
4.58% some / 3.59% full, so further resource-bearing checks are deferred until
a fresh sample is below 1%. No production Arena job or service was used.
Frontier remains research-only and **PARTIALLY VERIFIED**.

### Arena admission regression and current Frontier status — 2026-10-28 14:05 UTC

`tests/arena/test_admission.py` passes **11/11** in 1.99 seconds wall time,
at 180,884 KiB peak RSS, zero swaps, zero filesystem input, and no socket
traffic. The suite used a temporary `/dev/shm` root and monkeypatched
admission state. Pre-run memory and I/O PSI avg10 were at or below 0.01%;
post-run both were 0.00%. No production job or service was used. This adds to
the Frontier Arena 28/28 integration and generic Arena job 16/16 evidence; it
does not establish full legacy Arena regression or endurance readiness.

The current engineering report matrix supersedes its earlier 10:35 UTC
snapshot. Frontier remains **PARTIALLY VERIFIED**, research-only, isolated,
unmerged, and undeployed. Current source-use gates and held-capture protections
leave genuine live cross-venue validation blocked. Broader MIDAS regression,
resource sustainability, production recovery, and deployment remain open. The
held `data/frontier-public-probes/` path remains untouched.

### Direct replay bounds — 2026-10-28 14:10 UTC

Commit `f1d04bf` adds library-level limits matching the bounded replay API:
200 markets, 400 books, 1,000 verified relationships, and at most 1,000
relationship proposals. Relationship proposal itself rejects more than 200
markets before indexing. Targeted coverage passes **111/111** across the
relationship/economics/replay module, replay consumers, and API replay tests;
strict mypy and Ruff checks pass. The complete Frontier suite is not rerun on
this code, so its 452/452 result remains tied to the earlier storage/audit
checkpoint. Memory and I/O PSI stayed below 0.03% avg10; CPU PSI remained high
but fell during the short checks. Frontier remains research-only and
**PARTIALLY VERIFIED**.

### Frontier instrument identity — 2026-10-28 14:21 UTC

Commit `4305083` adds schema-v5 venue-scoped canonical IDs for Frontier
instruments, with deterministic legacy v1–v4 migration and rejection of IDs
that disagree with native identifiers. Adapter outputs and replay versions
were advanced. The 89-test identity/adapter/Coinbase slice passes, strict
mypy and Ruff pass, TypeScript build succeeds, and the focused UI test passes.
The IDs do not establish cross-venue payoff equivalence. The full Frontier and
legacy suites were not rerun while CPU PSI avg10 remained about 41–43%. No live
source, protected service, or held evidence path was accessed. Frontier stays
research-only, isolated, undeployed, and **PARTIALLY VERIFIED**.

Commit `de57883` expands legacy instrument-ID migration coverage across market
schemas v1–v4. The focused identity/adapter/Coinbase slice passes 92/92; Ruff
passes. The full Frontier suite was not rerun. CPU PSI avg10 remained above
43%, so broad verification stays deferred; overall Frontier status remains
**PARTIALLY VERIFIED**.

Commit `6ecb7c9` adds storage checks confirming instrument IDs survive durable
readback for single-market and batch observations (2/2 focused tests pass).
The full Frontier suite remains unrerun; no live source or protected service
was accessed. Overall Frontier status remains **PARTIALLY VERIFIED**.

The full storage module passes 30/30, including canonical-ID persistence for
single-market and batch observations. Its temporary-file run raised I/O PSI
avg10 to 9.54% some / 7.20% full; further tests are deferred until a fresh
sample is below 1%. No protected store was accessed.

The full current Frontier Python suite passes 465/465 on `d3e30a0` using a
tmpfs test root, at 381,916 KiB peak RSS and zero swaps or sockets. Post-run
I/O PSI avg10 remained 0.06% some / 0.00% full. This does not close broader
MIDAS/browser/Arena, live-source, production-recovery, or deployment gates.

The web suite passes 47/47; `tsc -b`, ESLint, Prettier, and production build
pass. Frontier Playwright passes 7/7 on the empty path and 2/2 on seeded
fixture data using isolated local services. The Chart bundle advisory remains
544.51 kB. Frontier stays **PARTIALLY VERIFIED** pending broader regression,
live-source, recovery, and deployment gates.

## Broader browser regression stopped — 2026-10-28 14:38 UTC

The full one-worker Mission Control Playwright command collected 19 tests;
eight passed, two seeded-only cases were skipped, and nine did not complete.
I stopped it with SIGINT after I/O PSI crossed the 1% admission gate
(1.12% some / 0.64% full at 14:38:19Z). No assertion failure was reported.
The interrupted process left its isolated test API and Vite servers running;
I verified and terminated only those test-owned processes. Both were gone on
the next process check. No production service or public source was accessed.

Frontier-specific browser tests still pass 7/7 normal and 2/2 seeded. The
broader Mission Control browser suite and overall Frontier status remain
**PARTIALLY VERIFIED**.

**Next safe action:** take a fresh resource sample before any additional
browser run; continue bounded, source-independent review until I/O admission
is clear.

## Mission Control E2E coverage — 2026-10-28 14:42 UTC

All 19 collected Mission Control browser cases pass across isolated one-worker
runs: 10 existing MIDAS cases, 7 normal Frontier cases, and 2 seeded Frontier
fixture cases. The earlier combined run remains recorded as interrupted at
the I/O gate. A first 10-case run had one Veritas failure because I overrode
its historical artifact workspace with an empty directory; the successful
repeat used the configured repository-backed read path and required no code
or test edits. Mutable API, Arena, and Frontier data stayed in a fresh temp
root. I/O PSI stayed below 1% in sampled checks; final I/O PSI at 14:42:48Z
was 0.08% some / 0.06% full and memory PSI was 0.00%. No test server remained.

Browser case coverage is **COMPLETE AND VERIFIED**. Broader repository
regression and Frontier overall remain **PARTIALLY VERIFIED**.

## Frontier Arena integration — 2026-10-28 14:44 UTC

Current-code Frontier Arena timeline, replay, and discovery tests pass 28/28.
The run took 4.63 seconds wall time at 201,368 KiB peak RSS, with a tmpfs
basetemp, zero swaps, and no socket traffic. The existing Starlette/httpx
deprecation warning remains. Post-run I/O PSI was 0.30% some / 0.18% full;
memory PSI was 0.00%. This closes the focused Frontier Arena slice only;
broader Arena and MIDAS regression remain **PARTIALLY VERIFIED**.

## Superseding acceptance snapshot — 2026-10-28 14:49 UTC

Exact-current web unit tests pass 47/47. `tests/arena/test_jobs.py` passes
16/16 after its test-only admission determinism update (15.42 seconds wall,
180,992 KiB peak RSS, tmpfs root, zero swaps or sockets). The Frontier Python
suite remains 465/465 on code with no later Python changes; Frontier Arena
integration is 28/28, admission is 11/11, and all 19 Mission Control browser
cases pass across isolated runs. Typecheck, lint, formatting, and production
build pass; the existing Chart bundle advisory is 544.51 kB.

The adapter protocol and research-only boundary are implemented and tested.
Live cross-venue data use remains held under the current source review; full
legacy MIDAS/Arena regression, endurance, production recovery, and deployment
remain open. Frontier overall is **PARTIALLY VERIFIED**. The report's new
14:49 UTC matrix supersedes the earlier 14:05 snapshot.

## Held-source API regression — 2026-10-28 14:53 UTC

The source-permission integration test now exercises seven specialized
Kalshi probe/collection routes with enabled flags and arbitrary permission
references. Every route returns the source hold before network access; the
adapter request count stays zero. The complete Frontier Python suite passes
465/465 with these assertions (31.00 seconds wall, 381,712 KiB peak RSS,
tmpfs root, zero swaps or sockets). Live source permission remains unresolved;
no source request was made.

## Frontier bounded evidence validation — 2026-10-28 16:51 UTC

After that full-suite run, additional source-independent changes were made in
`5455b6e` and `d0d1f41`. Five focused model, replay, and verifier modules pass
143/143; `tests/frontier/test_collection.py` passes 34/34. The newly covered
validators reject malformed evidence IDs before set-based duplicate checks.
Ruff, format, syntax, and diff checks pass. The full Frontier suite has not
been rerun on this latest tree, so the 465/465 result is historical rather
than current-tree evidence. No exchange endpoint or protected service was
accessed. At 16:50:58Z CPU PSI avg10 was 37.09%, memory and I/O PSI avg10 were
0%, available memory was 9.9 GiB, and swap was full. Frontier overall remains
**PARTIALLY VERIFIED**; live cross-venue science, full regression, protected
recovery, and deployment remain open.

## Frontier CI typing and integrated regression — 2026-10-28 17:03 UTC

The strict repository type check now succeeds across 181 source files after
`e3a2bd2` fixed 34 Veritas/Arena typing errors. Seven directly affected test
modules pass 80/80; the full `tests/frontier` suite passes 498/498 on the
integrated tree. Each run reports one existing Starlette/httpx warning. Ruff
and format checks pass. At 17:03:06Z CPU PSI avg10 was 31.12%, memory PSI
avg10 0%, I/O PSI avg10 0.18%, and 9.7 GiB was available. Runs used `/dev/shm`;
no source API request or protected-service action occurred. Live cross-venue
validation, broad legacy Arena regression, endurance, protected recovery, and
deployment remain open.

## Current Frontier Python suite — 2026-10-28 16:53 UTC

The complete `tests/frontier` suite passes **497/497** on the current code
tree in 30.28 seconds; one existing Starlette/httpx deprecation warning
remains. Pytest used `/dev/shm`. At 16:53:09Z CPU PSI avg10 was 38.47%,
memory and I/O PSI avg10 were 0%, and 9.9 GiB was available. This updates the
16:51 focused-only snapshot. No public source probe or protected-service
action occurred. Full legacy Arena regression, live cross-venue science,
resource endurance, protected recovery, and deployment remain open.

## Current Frontier raw-capture and Python regression — 2026-10-28 16:55 UTC

Commit `62e5a61` bounds `RawObservation` body text before encoding/decoding.
The focused storage module passes 31/31, and the full `tests/frontier` suite
passes 498/498 in 29.75 seconds with one existing Starlette/httpx deprecation
warning. Pytest state was under `/dev/shm`. At 16:55:30Z memory PSI avg10 was
0%, I/O PSI avg10 was 0.08%, CPU PSI avg10 was 29.59%, and 9.8 GiB was
available. No live source request or protected-service operation occurred.
Broad legacy Arena regression, live cross-venue science, endurance, protected
recovery, and deployment remain open.
## Frontier live Polymarket adapter observation — 2026-10-28 17:04 UTC

One unauthenticated, one-market Gamma listing request through the Frontier
Polymarket adapter returned HTTP 200. The raw observation and normalized
market batch are preserved in
`data/frontier-live-evidence-polymarket-20261028T170445Z/`; local model
reconstruction and SHA-256 checks pass. The result is one open binary market
with two instruments and explicit unverified-payout, settlement-asset, and
cross-venue-equivalence quality flags. No book, trade, or economic conclusion
was derived. Kalshi, Kraken, and Coinbase source-use holds remain active;
Reality and API services were not modified or restarted.

## Frontier live observation storage and replay — 2026-10-28 17:07 UTC

The same one-market capture now round-trips through a new isolated
`FrontierStore` database (155,648 bytes; 4 MiB budget). Its raw and row hashes
validate, and typed market and raw models reconstruct. Two deterministic
replays over the recovered stored row produce the same run ID and result hash;
the replay itself reloads through the hash-validating store path. It has zero
relationship proposals and candidates because the input has one metadata-only
market and no book. No cross-venue conclusion is claimed. At 17:07:40Z CPU PSI
avg10 was 41.15%; protected Reality was within about 216 KiB of its soft memory
boundary, so broad legacy regression remains deferred. Both protected
services were active and unchanged.

## Frontier live Polymarket book and replay — 2026-10-28 17:10 UTC

One unauthenticated, bounded CLOB book GET for the previously captured YES
instrument returned HTTP 200. The raw response and normalized book are now
preserved both as portable files and in the isolated Frontier store. It had
zero bid levels and five asks (best ask 0.995); its exchange timestamp was
about 10.04 seconds before receipt, with timestamp semantics still uncertain.
Two deterministic replays over the stored market and book had identical run
and result hashes, and the saved replay reloaded with hash verification. It
reported zero relationships or candidates; no completed payoff or economic
opportunity is claimed. The store holds two observations and two replays and
uses 167,936 bytes. Source-use holds and protected services are unchanged.
At 17:11:25Z CPU PSI avg10 was 39.52%; Reality was 360 KiB below `MemoryHigh`,
and swap had 1,816 KiB free. Broad regression remains deferred.

## Frontier live Gamma event-group graph — 2026-10-28 17:14 UTC

One bounded public Gamma event lookup returned five binary submarkets under
native event `606422`. Frontier persisted ten pairwise `SAME_EVENT`
hypotheses, all tied to the raw event observation; the first market has four
neighbors. The child payoffs remain unverified and non-exhaustive, so these
edges do not establish payoff equivalence. Two deterministic event replays
matched and reloaded with hash validation, producing zero candidates. This is
same-venue graph evidence, not cross-venue validation. At 17:14:02Z CPU PSI
avg10 was 2.70%, I/O PSI avg10 was 0.75%, and Reality had about 892 KiB below
`MemoryHigh`; broad regression still requires a new admission check.

## Full Arena regression paused — 2026-10-28 17:18 UTC

The one-worker full `tests/arena` run passed 105 cases before a host memory PSI
spike; it was interrupted with SIGINT and no assertion failure had been
reported. Peak RSS was 484 MiB. At 17:18:23Z memory PSI avg10 was 36.63%
(`full` 31.86%) despite 9.9 GiB available. Reality and API remained active.
The run is partial; wait for a fresh admission sample before retrying the
remaining legacy regression.
