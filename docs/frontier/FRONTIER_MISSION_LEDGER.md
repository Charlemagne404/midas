# Project Frontier Mission Ledger

## Strict parsing and proxy boundaries; tests held for resource admission — 2026-10-28 15:48 UTC

The public read transport now supplies a strict JSON parse-constant handler.
Python's standard decoder otherwise accepts NaN and positive/negative
Infinity, although those tokens are not valid JSON. Frontier classifies them
as INVALID_JSON and retains the bounded raw response evidence. Decimal parser
arithmetic errors now share the existing JSON_COMPLEXITY_LIMIT path. Added
four fixture cases for nonstandard constants and a 5,000-digit decimal
exponent case for the parser-limit path. The owned HTTPX client now uses
trust_env=False so HTTP_PROXY, HTTPS_PROXY, and ALL_PROXY cannot reroute its
public reads. Injected clients are limited to isolated MockTransport fixtures
without mounted custom transports, rejecting both network clients and explicit
proxy mounts. Local tests cover the default configuration and rejection paths.

The new transport tests and Ruff checks have not run. At 15:47:55Z host memory
PSI avg10 was 45.32% some / 40.12% full, I/O PSI was 0.61% some / 0.60% full,
9.5 GiB was available, and 3.7 GiB of 4 GiB swap was occupied. A separate
Veritas gap-detail batch was visible; no source, capture, or service was
changed. Implementation commits are eab4a0b, 634ee5f, 1938dc4, and eadec5d.

The repeat sample at 15:52:21Z still exceeded the memory gate: avg10 was
37.47% some / 23.71% full and avg60 was 36.41% some / 24.95% full. I/O avg10
was 0.09% some / 0.06% full, 9.7 GiB was available, and 3.8 GiB of 4 GiB swap
was occupied. No test or Ruff process was started. The parser and proxy
changes remain implemented with validation pending.

At 15:55:14Z, memory PSI remained elevated at 36.40% some / 21.49% full
avg10, with avg60 at 36.05% some / 23.01% full. I/O PSI avg10 was 0.00%;
9.9 GiB was available while swap was full at 4.0 GiB, with 39 MiB free. The
injected-client restriction was committed as eadec5d. No transport test or
Ruff check has run after the parser and proxy changes.

At 15:55:43Z, memory PSI was 37.30% some / 22.94% full avg10 and 36.29% some
/ 22.83% full avg60. I/O PSI avg10 remained 0.00%; 9.8 GiB was available and
swap was full at 4.0 GiB with 8 KiB free. A read-only process snapshot showed
the Reality recorder and a separate Veritas gap-detail batch active; neither
was touched. No Frontier test or Arena worker was running, so new transport
validation remains deferred.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Nonstandard JSON numeric-token rejection | IMPLEMENTED, VALIDATION PENDING | Transport and four mock-response cases are changed; run the focused adapter test after resource admission. |
| Default transport environment-proxy handling | IMPLEMENTED, VALIDATION PENDING | The owned client disables environment proxy discovery; a local configuration regression is added. |
| Injected transport proxy boundary | IMPLEMENTED, VALIDATION PENDING | Network clients and custom mounted transports are rejected; fixture-only validation is pending. |
| Current Frontier Python suite | PARTIALLY VERIFIED | The prior 465/465 result predates this transport change and does not verify current HEAD. |
| Live source and protected data | UNCHANGED | No adapter request or source capture was made; existing source-use holds remain active. |
| Frontier project acceptance | PARTIALLY VERIFIED | Live cross-venue science, broad regression, endurance, protected recovery, and deployment remain open. |

**Next safe action:** take a fresh memory and I/O PSI sample before running
the focused transport test; rerun the full Frontier Python suite only after
focused validation and a separate resource admission check. Keep this parser
boundary fail-closed and do not use live venue endpoints for fixture validation.

## Legacy Arena suite interrupted under host memory pressure — 2026-10-28 15:45 UTC

Collected the full legacy Arena suite as 427 cases across 78 files. The first
run used relative PYTHONPATH=packages; after the migration test changed into a
temporary directory, its worker imported the installed base checkout at
/home/charlie/midas/packages and rejected Frontier-only JobSpec fields. That
run reached 216 passed before this environment-path failure.

The focused migration worker case passed with an absolute Frontier package
path. I then fixed its test helper to prepend the active worktree's absolute
packages directory to the child PYTHONPATH. The same case passed again with
the original relative PYTHONPATH=packages invocation: 1/1 in 6.84 seconds
(7.82 seconds process wall), 346,064 KiB peak RSS, zero swaps, 2,536 input
blocks, 16 output blocks, and no socket messages. Ruff check, Ruff format
check, and git diff --check pass for the helper change.

A corrected full-suite run used the absolute Frontier package path and reached
67% without a reported assertion failure. It ran for 9:47.35, used 590.63 CPU
seconds, peaked at 493,008 KiB RSS, and used zero swaps. During the run, host
memory PSI avg10 rose above the admission gate; the sample before interruption
was 34.08% some / 30.80% full. A post-stop sample briefly reached 47.91% some /
43.67% full, so the pressure cannot be attributed to the Frontier test process
alone. The pytest PID was terminated after SIGINT and SIGTERM did not promptly
stop the CPU-bound test. No Arena test child remained. A read-only process
snapshot showed separate active Veritas work and the protected Reality
recorder; neither was touched.

At 15:44:01Z after the pressure subsided, memory PSI avg10 was 0.03% some /
0.02% full and avg60 was 6.91% some / 6.34% full. I/O PSI avg10 was 0.63% some
/ 0.57% full, available memory was 9.6 GiB, and 3.7 GiB of 4 GiB swap was in
use. The current evidence supports the focused migration case, not a completed
full Arena suite.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Migration worker subprocess import path | COMPLETE AND VERIFIED | Test helper pins the active worktree package path; the exact case passes under relative PYTHONPATH. |
| Full legacy Arena suite | PARTIALLY VERIFIED | Corrected run reached 67% with no reported assertion failures, then was stopped at severe host memory PSI. |
| Further resource-bearing regression | DEFERRED | Remeasure host pressure before another batch; prefer bounded focused slices while memory avg60 and swap remain elevated. |
| Frontier project acceptance | PARTIALLY VERIFIED | Live cross-venue evidence, broad regression, endurance, protected recovery, and deployment remain open. |

**Next safe action:** keep the source-use holds and protected services
unchanged. Use an absolute worktree package path for subprocess test runs and
wait for a fresh resource sample before starting another resource-bearing
test batch. Do not call the interrupted suite a pass.

## Arena job-supervision regression and I/O admission stop — 2026-10-28 14:03 UTC

The generic Arena job/supervisor module passed **16/16** in 31.95 seconds
(32.55 seconds wall), at 180,988 KiB peak RSS, zero swaps, 120 filesystem input
blocks, 105,904 output blocks, and no socket traffic. The test root was
`/tmp/midas-frontier-arena-jobs-20261028T1402Z`. Tests cover cancelled and
stale-source workers, artifact and disk budgets, supervisor failure state,
durable retries, worker leases, and restricted launch commands. Child workers
were test-scoped and exited with the suite; no production systemd unit, service,
or Arena root was used.

At `14:02:23Z` before the run, memory and I/O PSI avg10 were **0.00%**, with
about **10 GiB** available. At `14:03:06Z` after the run, memory PSI remained
**0.00%**, but I/O PSI had risen to **4.58% some / 3.59% full**. CPU PSI avg10
was 43.91% before and 36.68% after. No further test or build was started; wait
for a fresh I/O PSI avg10 below the 1% admission threshold. The worker test
processes exited; no collector or persistent Arena job is running.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Arena generic job and supervisor regression | COMPLETE AND VERIFIED | `tests/arena/test_jobs.py` passes 16/16, including bounded worker-process cases. |
| Further resource-bearing verification | DEFERRED | Post-run I/O PSI exceeded the admission gate; re-sample before continuing. |
| Frontier project acceptance | PARTIALLY VERIFIED | Live source permission/evidence, broader MIDAS regression, production recovery, and deployment remain open. |

**Next safe action:** continue read-only acceptance review while I/O pressure
settles, then remeasure before another bounded test slice. Preserve the
source-use holds and `data/frontier-public-probes/`.

## Frontier Arena replay integration verification — 2026-10-28 14:00 UTC

At code commit `76d388b`, the targeted Arena integration modules passed
**28/28** in 3.86 seconds (4.58 seconds wall), at 200,752 KiB peak RSS, zero
swaps, filesystem input, or socket messages, and 384 filesystem output blocks.
The run used `/dev/shm/midas-frontier-arena-snapshots-20261028T1400Z`; one
existing Starlette/httpx `TestClient` deprecation warning remains. Coverage
included Frontier replay, event-time timeline, and discovery snapshots,
content-addressed integrity, held-source filtering, completed-job result
binding, and the discovery worker-process boundary. One test launched a
bounded fixture-only child process, which exited within the test; no
persistent Arena job, service, source request, or collector was started.

At `14:00:17Z` before the run, memory and I/O PSI avg10 were **0.00%**, about
**10 GiB** was available, and 3.5 GiB of swap was occupied. At `14:00:40Z`
afterward, memory and I/O PSI avg10 remained **0.00%**. CPU PSI avg10 was
44.38% before and 38.33% after. No production Arena root or service was used.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Frontier Arena replay, timeline, and discovery integration | COMPLETE AND VERIFIED | Three targeted modules pass 28/28, including snapshot tamper/path checks, result binding, held-source filtering, and a bounded fixture subprocess. |
| Full legacy Arena suite | DEFERRED | The full Arena suite was not run; Frontier-scoped tests cover the changed integration paths. |
| Frontier project acceptance | PARTIALLY VERIFIED | Source-use permission, genuine cross-venue evidence, broader MIDAS regression, production recovery, and deployment remain open. |

**Next safe action:** record this Arena evidence and continue the acceptance
matrix without running long campaigns or a broad resource-intensive Arena
suite. Keep all tests fixture/local and preserve the source-use holds.

## Frontier dashboard and browser acceptance — 2026-10-28 13:59 UTC

**Verified source commit:** `76d388b`; documentation checkpoint follows at
`3dd6cd2`.

Frontend checks passed: Vitest **47/47** across nine files; TypeScript
`tsc -b`; ESLint; Prettier format check; and the production build. The build
transformed 2,230 modules. Vite emitted one size warning: `Chart` is 544.51 kB
minified / 186.79 kB gzip, above its 500 kB advisory threshold. The build
completed successfully.

Frontier browser E2E passed **7/7**; the separate seeded local integration
passed **2/2**. The regular run covered responsive views, explicit replay,
relationship selection, and local Arena evidence. The seeded run used 21
deterministic fixture captures/replays and one fixture-only Arena artifact at
`/tmp/midas-browser-xRjN0g`; it verified local pagination, replay lineage, and
Laboratory inspection. The explicit price-history probe action was fulfilled
by a Playwright route; no request reached a venue, and no collection POST was
observed. Both runs used one worker, local API/Vite listeners, and isolated
temporary roots; the listeners were stopped after each run. The final port
check found no listeners on 18000 or 15173.

Representative resource evidence: Vitest ran in 9.42 seconds wall time with
323,972 KiB peak RSS and zero swaps. The normal Frontier browser run took
18.66 seconds wall and peaked at 201,120 KiB; the seeded run took 11.03 seconds
wall and peaked at 183,388 KiB. Both used zero swaps. Before the seeded browser
run at `13:58:51Z`, memory PSI avg10 was **0.00%**, I/O PSI was **0.43% some /
0.21% full**, and about **9.8 GiB** was available. After both E2E runs at
`13:59:19Z`, memory PSI remained **0.00%** and I/O PSI was **0.08% some / 0.04%
full**. No live source, held capture, production service, or protected store
was accessed. `data/frontier-public-probes/` remains untouched and unstaged.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Frontier frontend unit/component tests | COMPLETE AND VERIFIED | 47/47 pass across nine files. |
| TypeScript, ESLint, Prettier, production build | COMPLETE AND VERIFIED | All pass; one non-fatal 544.51 kB Chart chunk advisory remains. |
| Frontier browser E2E | COMPLETE AND VERIFIED | 7/7 regular and 2/2 seeded fixture-only tests; loopback services shut down. |
| Live cross-venue validation | BLOCKED | Current source-use holds remain; fixture/browser evidence is not live source validation. |
| Frontier mission and deployment | PARTIALLY VERIFIED | Production recovery, source-use authorization, and deployment gates remain open. |

**Next safe action:** continue the remaining source-independent acceptance
review; do not start production services or live source probes.

## Review-store and independent-audit fail-closed verification — 2026-10-28 13:56 UTC

**Implementation commits:** `13377dc` (`fix(frontier): preflight review targets read only`)
and `76d388b` (`fix(frontier): clear unverified audit outputs`).

`append_relationship_review` now checks the requested parent using a read-only
SQLite connection before initialization, including when the path is an existing
empty database. The independent audit now clears candidate-derived payout,
cost, fee, P&L, capital, timing, and fill-sensitivity outputs when it cannot
recompute them because the execution scenario is invalid or pinned evidence is
missing. It also forces practical eligibility off and records
`INCOMPLETE_EVIDENCE`. The clean no-leg price-discrepancy-only classification
remains preserved. The audit algorithm version is now 23.

Verification passed:

- `tests/frontier/test_storage.py`: **30/30** in 1.33 seconds (1.67 seconds
  wall), 68,232 KiB peak RSS, zero swaps, filesystem input, or socket traffic;
  608 filesystem output blocks, isolated under
  `/dev/shm/midas-frontier-storage-review-preflight-20261028T1354Z`.
- `tests/frontier/test_relationships_economics_replay.py`: **83/83** in 0.68
  seconds (1.03 seconds wall), 56,348 KiB peak RSS, zero swaps, filesystem
  input, or socket traffic; 376 output blocks under
  `/dev/shm/midas-frontier-economics-replay-fail-closed-20261028T1354Z`.
- Full `tests/frontier`: **452/452** in 29.16 seconds (30.67 seconds wall),
  380,164 KiB peak RSS, zero swaps, 224 filesystem input and 376 output blocks,
  and no socket traffic. One existing Starlette/httpx deprecation warning
  remains. The run used
  `/dev/shm/midas-frontier-review-audit-full-20261028T1355Z`.
- Strict mypy passed on `storage.py`, `independent_audit.py`, and `models.py`;
  Ruff check/format and `git diff --check` passed on all five changed Python
  files.

Before the full run at `13:55:22Z`, memory and I/O PSI avg10 were both 0%,
about 10 GiB was available, and 3.5 GiB of swap was occupied. After the run at
`13:55:58Z`, memory and I/O PSI avg10 remained 0%. CPU PSI avg10 was 42.66%
before and 32.88% after. The full suite was serial, bounded, fixture-backed,
and isolated; no live API, protected capture/store, collector, production
service, browser, or Arena job was accessed.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Review target preflight before SQLite initialization | COMPLETE AND VERIFIED | Missing path and existing empty-file regressions pass; complete storage module passes. |
| Independent audit on invalid scenario or missing pinned evidence | COMPLETE AND VERIFIED | Regressions prove stale economic outputs are cleared; full Frontier suite and static checks pass. |
| Frontier Python test suite on `76d388b` | COMPLETE AND VERIFIED | 452/452 pass; one existing TestClient deprecation warning. |
| Frontier project acceptance | PARTIALLY VERIFIED | Source-use holds, genuine live cross-venue evidence, Arena/browser revalidation, production recovery, and deployment remain open. |

**Next safe action:** continue the isolated browser/API acceptance work after a
fresh resource sample. Preserve the source-use holds and keep
`data/frontier-public-probes/` untouched.

## Read-only review-target preflight — 2026-10-28 13:48 UTC

**Implementation commit:** `13377dc` (`fix(frontier): preflight review targets read only`).

The prior absent-path guard did not cover an existing empty SQLite file:
`initialize()` could still create schema before the review target lookup failed.
`append_relationship_review` now checks the relationship table and target using
the store's read-only connection before initialization. The existing missing
store regression uses a shared review fixture, and a second regression checks
that an empty database remains byte-for-byte unchanged. Neither regression,
the storage module, nor mypy/Ruff has run after this commit.

At `2026-10-28T13:48:50Z`, memory PSI avg10 was **37.45% some / 28.85% full**,
CPU PSI **29.17%**, and I/O PSI **0.00%**; about 9 GiB was available and swap
usage was 3.5 GiB. The memory admission gate remains exceeded. No source,
capture, collector, protected store, or production service was accessed.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Review-target preflight before SQLite initialization | IMPLEMENTED, VALIDATION PENDING | Missing-path and empty-file regressions are committed; both await test/static validation. |
| FrontierStore module after `13377dc` | PARTIALLY VERIFIED | The prior 28/28 module result predates both review-guard commits. |
| Frontier project acceptance | PARTIALLY VERIFIED | Live source-use holds, cross-venue evidence, broad regression, production recovery, and deployment remain open. |

**Next safe action:** when a fresh sample shows memory and I/O PSI avg10
below 1%, run both focused review-target cases, strict mypy/Ruff, then the
complete storage module. Keep `data/frontier-public-probes/` untouched.

## Missing relationship-review store no longer initializes — 2026-10-28 13:46 UTC

**Implementation commit:** `ccc44ce` (`fix(frontier): avoid initializing for missing review targets`).

`FrontierStore.append_relationship_review` requires an existing hypothesis.
When the database path does not exist, it now returns the same target-not-found
error before initializing SQLite or creating the store root. A regression
constructs a valid review and adjudicated relationship and asserts that both
the database and root remain absent.

The regression and post-change storage module were **not run**, and strict
mypy/Ruff were not rerun, because at `2026-10-28T13:46:08Z` host memory PSI
avg10 was **35.83% some / 28.31% full**. CPU PSI was 29.19%, I/O PSI 0.09%
some / 0.08% full, and about 9 GiB was available. No source, capture,
collector, protected store, or production service was accessed. This commit
has a pending focused regression and static check.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Absent-store relationship-review guard | IMPLEMENTED, VALIDATION PENDING | Code and a no-root-creation regression are committed; neither test nor static checks ran under high memory PSI. |
| FrontierStore module after this change | PARTIALLY VERIFIED | Prior 28/28 result predates `ccc44ce`; rerun the exact storage module after resource admission. |
| Frontier project acceptance | PARTIALLY VERIFIED | Source-use permissions, held-capture validation, live cross-venue evidence, broad regression, production recovery, and deployment remain open. |

**Next safe action:** wait for fresh memory PSI below the test-admission gate,
then run the focused missing-store case, strict mypy, and storage module. Keep
the public-probe directory untouched.

## Independent audit clears economics without position legs — 2026-10-28 13:42 UTC

**Implementation commit:** `2d8e9fb` (`fix(frontier): clear unaudited economics without legs`).

The independent-audit review found that a copied candidate could retain a
verified classification and positive P&L after all position legs were
removed. The audit correctly said `NOT_EVALUATED` but previously returned the
stale result fields. The no-leg path now always clears practical eligibility,
payoff/P&L/capital totals, sensitivities, and timing claims. It changes a
previously audited or otherwise economically classified candidate to
`INCOMPLETE_EVIDENCE`; a clean `PRICE_DISCREPANCY_ONLY` candidate remains a
discrepancy.

The focused regression passed **1/1** (0.56 seconds pytest, 0.91 seconds wall,
**68,076 KiB** maximum RSS, zero swaps, filesystem input, or socket messages,
and 1,496 output blocks). It used
`/dev/shm/midas-frontier-no-leg-audit-20261028`. Strict mypy for
`independent_audit.py`, Ruff check/format, and `git diff --check` pass.

The surrounding 82-case economics/replay module was not run. At
`2026-10-28T13:42:40Z`, CPU PSI avg10 was **0.98%**, I/O PSI **0.31% some /
0.26% full**, and memory PSI **48.10% some / 44.12% full**; memory pressure
exceeded admission by a wide margin, despite about 9 GiB being available. No
source, capture, protected store, collector, or production service was used.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| No-leg independent-audit output | COMPLETE AND VERIFIED | Targeted regression proves stale positive economics are cleared and discrepancy-only status remains; strict mypy and Ruff pass. |
| Full economics/replay module after this change | PARTIALLY VERIFIED | One focused regression passes; 81 sibling tests were not rerun under high memory PSI. |
| Frontier project acceptance | PARTIALLY VERIFIED | Live cross-venue evidence, source-use permissions, held-capture access, production recovery, broad regression, and deployment remain open. |

**Next safe action:** continue read-only review or wait for a fresh low-memory-
pressure sample before running the economics module. Keep the public-probe
directory and held captures untouched.

## FrontierStore write preflight — 2026-10-28 13:39 UTC

**Implementation commit:** `c5b8822` (`fix(frontier): preflight storage writes before initialization`).

The source-independent persistence audit found that bounded FrontierStore
writers initialized or migrated SQLite before validating encoded row size,
replay budgets, or paired-input consistency. Observation, relationship,
relationship-review, replay, price-history replay, and paired-comparison
writers now complete those input-only checks before initialization. Observation
preflight includes both the raw-plus-normalized payload and its final persisted
provenance representation. Checks that require existing database evidence
(for example, whether a reviewed hypothesis exists) still run inside the
transaction.

New regressions confirm that oversized observation and relationship rows,
invalid replay budgets, and mismatched paired comparisons are rejected without
creating the database file. The full `tests/frontier/test_storage.py` module
passes **28/28** in **1.33 seconds** (1.68 seconds wall), at **70,916 KiB**
maximum RSS, with zero swaps, filesystem input, or socket messages and 568
filesystem-output blocks. It used
`/dev/shm/midas-frontier-storage-preflight-module-20261028`. Strict mypy for
`storage.py`, Ruff check/format, and `git diff --check` pass.

The combined Frontier-plus-Arena snapshot suite was not started. A fresh sample
at `2026-10-28T13:39:57Z` showed CPU PSI avg10 **2.06%**, I/O PSI **1.27% some
/ 1.24% full**, and memory PSI **0.00%**; I/O exceeded the 1% admission gate.
About 10 GiB remained available. No source, capture, protected store, collector,
production service, or historical research evidence was accessed.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| FrontierStore bounded write preflight | COMPLETE AND VERIFIED | Six persistence paths preflight model consistency, encoded limits, and budgets before database initialization; the complete 28-case storage module passes. |
| Full Frontier/Arena regression after this commit | PARTIALLY VERIFIED | Touched storage module passes; combined suite deferred after I/O PSI exceeded admission. |
| Frontier project acceptance | PARTIALLY VERIFIED | Source-use holds, held-capture restrictions, genuine cross-venue evidence, production recovery, and deployment remain open. |

**Next safe action:** continue bounded source-independent review; sample I/O
pressure before a broader test invocation. Preserve
`data/frontier-public-probes/` untouched.

## Collection journal module verification — 2026-10-28 13:28 UTC

After the append-input and read-only-query fixes (`3153148`, `f440fa2`), the
full `tests/frontier/test_collection.py` module passes **29/29** in 1.94 seconds
(2.33 seconds wall). The run used
`/dev/shm/midas-frontier-collection-module-20261028`, peaked at **69,124 KiB**
RSS, and recorded zero swaps, filesystem input, or socket messages (576 output
blocks). It includes a short local file-lease child process and temporary
journal roots; no external source or protected store was used.

Before the run at `13:28:17Z`, memory PSI avg10 was 0.00%, I/O PSI was 0.03%
some / 0.03% full, and 10.5 GiB was available. Afterward at `13:28:47Z`,
memory remained 0.00%, I/O was 0.14% some / 0.03% full, and 10.4 GiB was
available. CPU PSI remained elevated at 44.54%, so the full Frontier suite and
broader repository suites remain deferred. **Code commits:** `3153148`,
`f440fa2`.

**Next safe action:** continue bounded source-independent audit; rerun broader
tests only after a fresh resource sample supports admission.

## Official source-terms refresh — 2026-10-28 13:26 UTC

Read-only review of the official Kalshi, Kraken, Coinbase, and Polymarket
materials confirmed the existing source-use holds. Kalshi's API agreement
limits use to a member's own trading; Kraken's API notice says prior permission
is required for certain uses including non-personal commercial use of public
market data; Coinbase's current market-data terms restrict external display,
end-user apps, and AI/ML uses absent written consent. Polymarket's research
guide distinguishes its .com and US exchanges and APIs. The new dated review
is `docs/frontier/SOURCE_DATA_TERMS_REVIEW_2026-10-28.md`, linked from current
architecture and operations docs. No permission was inferred and no hold was
lifted.

No API request, exchange contact, or capture read occurred. The untracked
`data/frontier-public-probes/` directory remains untouched. This work was
documentation-only; focused collector tests and module verification are
recorded below. **Documentation commit:** `c9388b2`.

**Next safe action:** continue source-independent implementation review; do not
enable a held source without a validated permission and scope review.

## Collector journal reads remain read-only — 2026-10-28 13:23 UTC

Follow-up review found `run_spec()` and `checkpoints()` routed reads through
`initialize()`. That created a new SQLite journal for missing-run reads and
could add schema objects to an incomplete database. They now use a size-bounded,
schema-checked SQLite `mode=ro` connection; missing run/checkpoint lookups keep
their prior not-found semantics without creating a root or repairing a file.

The targeted absent/incomplete-journal regression passes **1/1** in 0.45
seconds, with **62,440 KiB** peak RSS, zero swaps, filesystem input, or socket
messages. Strict mypy for `collection.py`, Ruff check/format, and
`git diff --check` pass. At `2026-10-28T13:23:32Z`, memory PSI avg10 was 0.00%,
I/O PSI was 0.05% some / 0.01% full, and 10.4 GiB was available. CPU PSI
avg10 was 42.26%; broader tests remain deferred. No source, collector,
protected store, or production service was accessed.

**Implementation commit:** `f440fa2` (`fix(frontier): keep collection journal reads read-only`).

**Next safe action:** continue source-independent review; wait for a fresh
resource sample before broader regression workloads.

## Collection journal input checks before initialization — 2026-10-28 13:21 UTC

The source-independent persistence review found that `CollectionJournal`'s run,
initial-checkpoint, and checkpoint append methods initialized SQLite before
revalidating caller-supplied models. They now validate and enforce encoded-size
bounds before initialization. Checkpoint database lookups use the reparsed
record. A regression submits malformed `model_copy(update=...)` values to all
three methods and confirms rejection without creating the journal root.

The targeted case passes **1/1** in 0.45 seconds; peak RSS was **61,960 KiB**,
with zero swaps, filesystem input, or socket messages. Ruff check/format,
`git diff --check`, and strict mypy for `collection.py` pass. At
`2026-10-28T13:21:09Z`, memory PSI avg10 was 0.00%, I/O PSI avg10 was 0.00%,
and 10.4 GiB was available. Host CPU PSI avg10 remained elevated at 41.79%,
so the collection module and broader suites were not run. No live source,
collector, protected store, or production service was accessed.

**Implementation commit:** `3153148` (`fix(frontier): validate collection writes before initialization`).

**Next safe action:** continue source-independent provenance/replay review;
admit a broader regression slice only after a fresh resource sample supports it.

## Revalidate every Frontier persistence input — 2026-10-28

The persistence review extended the `append_observation` guard across the
remaining evidence writers. A shared boundary reparses relationship hypotheses,
relationship reviews and revisions, replay manifests, price-history replay
results, and paired comparisons before database initialization. Deterministic
replay inputs also have their manifest-derived run ID and content digest
recomputed before a write, preventing a malformed copied replay from becoming
an unreadable stored row.

Regression coverage now includes copied observations, invalid relationship
models, replay result hashes, and paired comparison hashes. The storage module
passes **25/25** in 1.31 seconds (1.66 seconds wall), at 68,560 KiB peak RSS,
with zero swaps, filesystem input, or socket messages. Strict mypy passes for
`storage.py`; Ruff check/format and `git diff --check` pass. The exact Frontier
suite plus Arena replay/discovery/timeline suite passes **468/468** in 31.61
seconds (33.10 seconds wall), with one existing Starlette/httpx deprecation
warning. It peaked at 380,404 KiB RSS, used zero swaps and filesystem input
(8 output blocks), and emitted no socket messages. Tests ran in
`/dev/shm/midas-frontier-storage-all-writers-full-20261028`.

Before the full run, memory PSI avg10 was 0.00%, I/O PSI was 0.12% some /
0.02% full, and about 10 GiB was available. Afterward memory remained 0.00%,
I/O was 0.01% some / 0.01% full, and about 10 GiB remained available. No live
source, protected store, production service, or historical research artifact
was accessed. **Implementation commit:** `e99cf0e`.

**Next safe action:** continue source-independent provenance/replay review;
keep broader tests behind a fresh resource sample below the 1% I/O threshold.

## Observation write-boundary revalidation — 2026-10-28

The provenance-write audit found that `FrontierStore.append_observation`
serialized typed models as-is. A previously constructed `RawObservation` or
normalized model changed through `model_copy(update=...)` could therefore be
stored without re-running its validators. The store now reparses both inputs
from their Python-mode payloads before it initializes the database or inserts
anything, and converts validation failures into `FrontierStoreError`.

The storage regression covers a copied raw record with a mismatched body hash
and a copied market with an invalid verified payoff; both fail before the
database path is created. `tests/frontier/test_storage.py` passes **22/22** in
16.83 seconds, at 68,252 KiB peak RSS with zero swaps, filesystem input, and
socket messages. Strict mypy passes for `storage.py`; Ruff check/format and
`git diff --check` pass. The focused output used
`/tmp/midas-frontier-storage-input-validation-20261028`.

The exact post-change Frontier suite plus Arena replay/discovery/timeline
regression passed **465/465** in 31.56 seconds (33.02 seconds wall), with one
existing Starlette/httpx `TestClient` deprecation warning. It peaked at
380,600 KiB RSS, used zero swaps and filesystem input (8 output blocks), and
emitted no socket messages. The run used the unique tmpfs basetemp
`/dev/shm/midas-frontier-storage-exact-full-20261028`. Pre-run memory PSI avg10
was 0.00%, I/O PSI was 0.09% some / 0.06% full, and about 10 GiB was available.
Post-run memory PSI remained 0.00%, I/O was 0.01% some / 0.01% full, and about
10 GiB was available. No live source, protected store, production service, or
historical research artifact was accessed.

**Implementation commit:** `6a3e459` (`fix(frontier): validate observations before persistence`).

**Next safe action:** continue source-independent provenance and replay review;
admit more tests only when a fresh resource sample remains below the 1% I/O
threshold.

## Empty payoff-state rejection in relationship verifiers — 2026-10-28

The verifier audit found a second vacuous-proof path. A malformed in-memory
copy could erase the payoff state set and every instrument payout row; the
empty state mapping then satisfied the logical-implication bijection and
state-by-state implication checks. Same-payoff verification had the related
empty-state risk when instruments remained present. Both direct verifiers now
require nonempty exhaustive states and revalidate each market's full structure.
Same-payoff verification advanced from v7 to v8, logical implication from v3
to v4, and the independent audit from v21 to v22. Prior attestations remain
inspectable but no longer count as current verification for new candidate
audits.

The new model-copy regressions and stale-version checks pass. All three
affected relationship/economics modules pass **97/97** in 1.04 seconds; strict
mypy passes for `relationships.py`, `independent_audit.py`, and `models.py`.
Ruff check/format and `git diff --check` pass. Tests used
`/tmp/midas-frontier-relationship-v8-v4-20261028`; the run peaked at 65,304
KiB RSS with zero swaps, filesystem input, or socket messages. The full
Frontier suite plus Arena replay/discovery/timeline regression passed
**463/463** in 111.02 seconds (112.48 seconds wall), with one existing
Starlette/httpx `TestClient` deprecation warning. It peaked at 380,764 KiB RSS,
used zero swaps and 16 filesystem input blocks, and emitted no socket messages.
Output was isolated under `/tmp/midas-frontier-v8-v4-full-20261028`. Pre-run
memory PSI avg10 was 0.00%, I/O PSI was 0.03% some / 0.00% full, and about
10 GiB was available. Immediately afterward memory PSI remained 0.00%; I/O PSI
was 5.37% some / 4.16% full with about 10 GiB available, so additional tests
are held until a fresh sample falls below the 1% admission threshold.

**Implementation commit:** `eb53842` (`fix(frontier): reject vacuous payoff state proofs`).

The read-only follow-up checked the remaining bounded economic verifier
families, the independent logical-implication and same-payoff candidate audits,
and the stored relationship-review route. Multi-outcome and joint-state audits
already require nonempty bounded state sets; the API review route validates
hash-checked stored market observations and calls the versioned direct verifier
before it can persist a verified revision. It is the only production caller of
`append_relationship_review`. No additional empty-state acceptance path was
found in these inspected code paths. This was source inspection, not a new
runtime test.

**Next safe action:** continue source-independent review of replay and
provenance write boundaries while I/O pressure settles; run more tests only
after a fresh sample falls below the admission gate. Source-use holds,
held-capture preservation, and production boundaries remain unchanged.

## Same-payoff verifier empty-instrument rejection — 2026-10-28

A targeted review found that `verify_same_payoff` accepted two binary event
markets with no instruments when given an empty instrument mapping. Because
the empty mapping is technically a bijection over two empty sets, the verifier
incorrectly produced a `VERIFIED` edge without comparing any payout vectors.
This was reproduced directly against the current branch. The verifier now
rejects either market when it has no instrument payout vectors, and its version
has advanced from 6 to 7 so the independent audit will not treat prior edges
as current verification. Existing v6 evidence remains readable but requires
re-review for new audited candidates.

The regression covers an empty left market, empty right market, and both empty.
The targeted verifier/version slice passed **10/10** in 0.57 seconds; Ruff
check, Ruff format, and `git diff --check` pass. The full `tests/frontier`
suite plus Arena replay/discovery/timeline passed **459/459** in 108.32 seconds
(109.76 seconds wall), at 381,136 KiB peak RSS with zero swaps and socket
messages. All test output was isolated under
`/tmp/midas-frontier-v7-full-20261028`.

Before the full run memory PSI avg10 was 0.00%, I/O PSI avg10 was 0.04% some /
0.04% full, and 10.2 GiB was available. Afterward memory PSI remained 0.00%,
while I/O PSI rose to 4.38% some / 2.65% full. Strict mypy is held until a
fresh I/O sample is below the 1% admission threshold. After I/O avg10 returned
below 1%, strict mypy passed with no issues in `relationships.py` and
`independent_audit.py` (2.49 seconds). The exact command was:

```text
PYTHONPATH=packages:. /home/charlie/midas/.venv/bin/mypy --cache-dir=/tmp/midas-frontier-mypy-v7-20261028 packages/midas/frontier/relationships.py packages/midas/frontier/independent_audit.py
```

At 13:00:52 UTC, memory PSI avg10 was 0.00%, I/O PSI avg10 was 0.01% some /
0.01% full, and 10.2 GiB was available. No capture, exchange endpoint,
production service, or historical research artifact was used or modified.

Next safe action: audit the remaining independent candidate-verification and
relationship-review paths for similarly vacuous evidence acceptance, then
continue source-independent Frontier acceptance. Keep source-use holds,
held-capture preservation, and production boundaries unchanged.

## Arena relationship fixture repair — 2026-10-28 12:52 UTC

Four Arena discovery regressions rejected their synthetic cross-venue
relationship because the fixture supplied placeholder observation IDs instead
of the exact observation IDs pinned in its Polymarket and Kalshi market
provenance. The independent payoff verifier correctly rejected that evidence.
The fixture now cites the pinned IDs; no verifier or production behavior was
changed.

The Arena discovery and timeline modules plus the Frontier discovery-scope
comparison passed **15/15** in 5.88 seconds (6.59 seconds wall), with 198,600
KiB peak RSS, zero swaps, and zero socket messages. All generated artifacts
were rooted under `/tmp/midas-frontier-arena-20261028T1252Z`. The pre-run
memory PSI avg10 was 0.00%, and about 10.3 GiB was available. One existing
Starlette/httpx `TestClient` deprecation warning remains.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Arena Frontier discovery and timeline regressions | COMPLETE AND VERIFIED | 14/14 pass with pinned fixture evidence. |
| Frontier discovery-scope comparison | COMPLETE AND VERIFIED | 1/1 deterministic comparison test passes. |
| Frontier overall | PARTIALLY VERIFIED | Genuine cross-venue public evidence, protected recovery, broader source validation, and deployment remain open. |

Next safe action: continue with an isolated acceptance gap. Keep public-source
use, held-capture, and production boundaries unchanged.

## Broader isolated browser regression — 2026-10-28 12:48 UTC

The one-worker Playwright run across the non-Veritas browser suite completed
**16 passed, 2 skipped** in 35.8 seconds (36.36 seconds wall), with 222,188
KiB peak RSS, zero swaps, and zero socket messages. It exercised Frontier,
Arena, Laboratory, paper simulation, Reality's isolated explorer, readiness,
deferred charts, and Mission Control. The two seeded Frontier tests were
skipped because this run intentionally used an empty store; they pass **2/2**
in the separate seeded run recorded below. Laboratory completed the bounded
6-run comparison and 1-run adversarial simulation against the test database.
Reality service operations were intercepted by fixtures, and the paper API
reported synthetic mode with zero live orders.

The Veritas browser case that asserts historical research artifacts was
excluded because its expected artifacts are in the preserved Veritas
workspace; it was not redirected to or read from that workspace. The Veritas
unit component tests and offline independent-economics/replay regressions remain
verified separately. The demo API and Vite test servers exited, and ports
18000/15173 were clear afterward. No public source, service control, or
operational evidence store was used.

At `12:48:15Z`, memory PSI avg10 was **0.00%**, I/O PSI was **0.01% some /
0.00% full**, about **9 GiB** was available, and host swap remained at 3.5/4
GiB. Pytest used no swap.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Non-Veritas MIDAS browser regression | COMPLETE AND VERIFIED | 16 passed; seeded tests separately pass 2/2. |
| Veritas historical-artifact browser flow | PARTIALLY VERIFIED | Not run against preserved artifact storage; fixture-backed component tests and offline economics pass. |
| Frontier overall | PARTIALLY VERIFIED | Genuine cross-venue public evidence, broader live/browser validation, protected recovery, and deployment remain open. |

Next safe action: continue implementation or use additional isolated
regressions. Do not read the held Veritas workspace or cross the production
boundary without explicit scope changes.

## Frontier frontend build and browser verification — 2026-10-28 12:46 UTC

The Frontier workspace passes its current frontend checks:

- `tsc -b`: passed in 8.63 seconds, 471,424 KiB peak RSS, zero swaps and
  socket messages.
- Vite production build: **2,230 modules transformed**, built in 4.78 seconds
  (5.03 seconds wall), 684,180 KiB peak RSS, zero swaps and socket messages.
  Output is isolated at `/tmp/midas-frontier-web-build-20261028T1234Z`.
  Frontier's lazy JavaScript chunk is 182.82 kB (44.55 kB gzip). The deferred
  chart chunk is 544.51 kB (186.79 kB gzip), which triggers Vite's existing
  500 kB chunk warning; the browser lazy-loading check passes.
- Vitest: **47/47 across 9 files** in 20.32 seconds (20.73 seconds wall),
  288,496 KiB peak RSS, zero swaps and socket messages.
- ESLint and the full frontend Prettier check both pass.
- Frontier-focused Playwright: **10/10** in 20.5 seconds (21.14 seconds wall),
  206,744 KiB peak RSS, zero swaps and socket messages. Coverage includes
  overview, source/market empty states, explicit history actions, joint-state
  replay, fixture-only Kalshi settlement, bounded relationship graph, mobile
  390 px overflow, deferred chart loading, Arena evidence, and Laboratory
  artifact review.
- Seeded Playwright: **2/2** in 8.0 seconds (10.60 seconds wall), 180,704 KiB
  peak RSS, zero swaps and socket messages. It paginates 21 synthetic history
  captures, persists and replays a deterministic result, then loads a
  hash-verified fixture Arena artifact in Laboratory. All seeded data and
  screenshots are under `/tmp`.
- Default-token Playwright: **1/1** readiness browser check in 4.5 seconds
  (5.02 seconds wall), 166,284 KiB peak RSS, zero swaps and socket messages.
  This run omitted `MIDAS_FRONTIER_E2E_RUN_ID`, confirming generated owner
  markers survive worker config reloads.

The first browser startup attempt timed out because the configured temporary
database parent did not exist; the API's `/api/health` returned SQLite
`unable to open database file`. The Playwright config now creates only a fresh
real directory directly under the system temp root, records a per-run owner
marker, and rejects symlinked or stale roots. The marker lets workers reload
configuration only for that run after the API creates its database. Both the
empty-state and seeded browser runs now pass. The local demo API and Vite test
servers exited; ports 18000 and 15173 were clear after the runs.

At `12:46:07Z`, memory PSI avg10 was **0.00%**, I/O PSI some/full was
**0.08%**, about **9.9 GiB** was available, and host swap was at 3.5/4 GiB.
None of the timed frontend commands used swap.
No public exchange probe, protected service, persistent source store, or
production deployment was involved.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Frontend type-check, lint, and format | COMPLETE AND VERIFIED | `tsc -b`, ESLint, and full Prettier check pass. |
| Frontier production bundle | COMPLETE AND VERIFIED | 2,230 modules; isolated build succeeds. Deferred chart chunk remains above Vite's 500 kB warning threshold. |
| Frontier browser workspace | COMPLETE AND VERIFIED | 12 focused Playwright cases pass across empty and seeded roots; one extra check verifies generated run IDs. Wider unrelated UI E2E remains unrun. |
| Frontier overall | PARTIALLY VERIFIED | Cross-venue source evidence, broad legacy/browser acceptance, production recovery, and deployment remain open. |

Next safe action: continue with a bounded, source-independent acceptance gap
or implementation defect. Keep Frontier isolated and preserve source-use and
production boundaries.

## Bounded source-quality, Veritas, and integration regressions — 2026-10-28 12:33 UTC

The source anomaly audit fixtures advertised reconstruction revision 5, while
the current Reality replay engine and collector support revisions 1–4. The
engine correctly rejected the unsupported fixture. Both synthetic records now
use revision 4; no production code or captured evidence changed.

Verification on isolated inputs:

- `tests/test_reality_source_anomaly_audit.py`,
  `tests/test_reality_source_quality_reaudit.py`, and
  `tests/test_reconcile_reality_source_quality.py`: **10/10** in 0.17 seconds,
  44,256 KiB peak RSS, zero swaps and socket messages. All outputs were under
  `/tmp/midas-frontier-source-quality-20261028T1231Z`.
- `tests/test_veritas_independent_economics.py` and
  `tests/test_veritas_v6_offline_replay.py`: **24/24** in 0.36 seconds,
  45,460 KiB peak RSS, zero swaps and socket messages. Economics were fixture
  based; replay artifacts were under
  `/tmp/midas-frontier-veritas-fixtures-20261028T1232Z`.
- `tests/integration`: **56 passed, 1 skipped** in 28.49 seconds (29.77 seconds
  wall), 222,868 KiB peak RSS, zero swaps and socket messages. The PostgreSQL
  case skipped because no explicit `MIDAS_TEST_POSTGRES_URL` was set. The run
  emitted the existing Starlette/httpx `TestClient` deprecation warning. API
  and persistence data stayed under
  `/tmp/midas-frontier-integration-20261028T1235Z`.

The integration pre-run sample had memory PSI avg10 **0.00%**, I/O PSI
**0.04%**, and about **10 GiB** available. At `12:33:34Z` after the run,
memory PSI remained **0.00%**, I/O PSI was **0.56% some / 0.39% full**, and
about **10 GiB** remained available; host swap use remained 3.5/4 GiB, with
zero swap attributed to pytest. No public source, protected recording, frozen
campaign, production service control, or persistent operational store was
used.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Reality source-quality replay audits | COMPLETE AND VERIFIED | 10/10 after correcting fixture revision to the supported revision 4. |
| Veritas independent economics and V6 offline replay | COMPLETE AND VERIFIED | 24/24 fixture-based checks; no live-source claim. |
| MIDAS integration regression | PARTIALLY VERIFIED | 56 passed and optional PostgreSQL skipped; browser/production acceptance remains separate. |
| Frontier overall | PARTIALLY VERIFIED | Genuine cross-venue validation, broader browser regression, production recovery, and deployment remain open. |

Next safe action: continue with source-independent regressions only after a
fresh PSI admission sample. Keep the source-use holds and deployment boundary
intact.

## Additional bounded Reality regression slices — 2026-10-28 12:29 UTC

After the 430/430 Frontier run, more source-independent legacy tests passed:

- `tests/test_reality_foundry.py`: **18/18**, 0.83 seconds, 46,988 KiB peak
  RSS, zero swaps and socket messages; all evidence is generated in `tmp_path`.
- `tests/test_reality_training.py`: **19/19**, 3.87 seconds pytest time / 4.99
  seconds wall, 400,572 KiB peak RSS, zero swaps and socket messages; model
  training and dataset writes use synthetic temporary inputs.
- `tests/test_reality_full_scale_validation_admission.py`: **17/17**, 0.15
  seconds, 43,812 KiB peak RSS, zero swaps and socket messages; only synthetic
  admission telemetry is evaluated.
- `tests/test_reality_readonly_sandbox.py`: **1/1**, 0.16 seconds, 43,656 KiB
  peak RSS, zero swaps and socket messages. Its child process operates only on
  the test's temporary source/staging directories.
- `tests/test_reality_shadow.py`: the first run on `/dev/shm` had **17 pass,
  3 fail** because its configured filesystem reserve exceeded available space
  on that mount. The three failed cases passed when rerun on `/tmp` (**3/3**),
  and the complete module then passed **20/20** in 2.97 seconds pytest time /
  3.54 seconds wall, 170,616 KiB peak RSS, zero swaps and socket messages.
  All campaign and source paths were inside each run's unique pytest
  temporary directory; no frozen campaign or recorder data was accessed.

At `12:29:11Z`, memory PSI avg10 was **0.00%**, while I/O PSI some was
**1.08%** (full **0.90%**); further tests are held until both avg10 values are
below 1%. No protected service, live exchange source, or protected evidence
was used.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Reality synthetic foundry and training regressions | COMPLETE AND VERIFIED | 18/18 and 19/19 passed on tmpfs; no source access or model deployment. |
| Reality full-scale admission and sandbox regressions | COMPLETE AND VERIFIED | 17/17 and 1/1 passed with fixture telemetry and temporary source/staging roots. |
| Reality shadow replay | COMPLETE AND VERIFIED | 20/20 pass on `/tmp`; the 3 `/dev/shm` failures were the configured reserve guard, not shadow assertions. |
| Further test admission | DEFERRED | I/O PSI some briefly exceeded the 1% avg10 gate. |
| Frontier overall | PARTIALLY VERIFIED | Remaining legacy modules, live cross-venue permission/evidence, production recovery, and deployment remain open. |

Next safe action: remeasure PSI before the isolated Reality deployment-guard
module or another legacy test slice. Do not run deployment operations.

## Anonymous public transport hardening and current regression — 2026-10-28 12:26 UTC

Static security review found that `PublicReadTransport` accepted arbitrary
injected `httpx.AsyncClient` state. A client configured with credentials,
default query parameters, cookies, request hooks, a base URL, or redirects could
widen requests beyond the transport's stated public-read contract. The
transport now rejects those client configurations, rechecks before each
request, forces anonymous GET/no-redirect/configured-timeout behavior, and
clears source cookies under a per-transport request lock. Added regressions
cover client authentication, sensitive headers, cookies, query defaults,
hooks, redirects, base URLs, and server-set cookie cleanup.

Verification on the exact current source tree:

- `tests/frontier/test_transport.py`: **15/15** in 2.15 seconds, 56,888 KiB
  peak RSS, zero swaps, zero socket messages.
- `tests/frontier/test_adapters.py tests/frontier/test_coinbase.py`: **84/84**
  in 2.95 seconds, 79,156 KiB peak RSS, zero swaps and socket messages.
- `tests/frontier/test_collection.py`: **27/27** in 1.95 seconds,
  70,400 KiB peak RSS, zero swaps and socket messages. This includes the
  atomic initial-checkpoint rollback regression.
- `tests/test_reality_research_schedule.py`: **4/4** in 1.56 seconds,
  163,236 KiB peak RSS, zero swaps and socket messages; the corrected module
  alias now produces distinct dataset periods.
- Full `tests/frontier`: **430/430** in 28.96 seconds with the existing
  Starlette/httpx deprecation warning. Pre/post PSI avg10 was 0.00% for memory
  and I/O; about 10 GiB was available. Test state was isolated under
  `/dev/shm`.
- Strict mypy: **no issues in 2 source files** (`collection.py` and
  `adapters/transport.py`). Ruff check/format and `git diff --check` pass.

No live exchange source, protected store, production service, or account was
used. The preserved untracked public-capture directory remains untouched.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Public HTTP transport anonymous-client boundary | COMPLETE AND VERIFIED | Injected credential/default-state rejection, redirect override, configured timeout, and cookie cleanup; 15 transport tests plus 84 adapter/API-adjacent tests and strict typing pass. |
| Atomic collection run/checkpoint creation | COMPLETE AND VERIFIED | Rollback trigger regression and 27/27 collection lifecycle tests pass. |
| Corrected Reality schedule fixture | COMPLETE AND VERIFIED | 4/4 schedule tests pass with distinct generated dataset IDs. |
| Full Frontier Python regression | COMPLETE AND VERIFIED | 430/430 pass on the exact current source tree. |
| Genuine cross-venue equivalence and economics | BLOCKED | Source-use holds and held-capture boundary remain; no live match is claimed. |
| Frontier overall | PARTIALLY VERIFIED | Broader MIDAS/browser regression, production recovery, and deployment remain open. |

Next safe action: continue bounded, source-independent MIDAS regressions;
re-measure host PSI before each workload. Keep source-use holds and the
production/deployment boundary intact.

## Memory pressure persists — 2026-10-28 12:20 UTC

At `12:20:05Z`, memory PSI avg10 remained **36.90% some / 27.21% full**;
I/O PSI had settled to **0.29% some / 0.00% full**. About **10 GiB** was
available, with **3.5/4 GiB** swap in use. No runtime test, build, or type
check was launched. The collection atomicity fix and research-schedule fixture
remain implemented but await runtime validation.

Next safe action: do not admit test work until a fresh sample shows both
memory and I/O PSI avg10 below 1%.

## Memory admission remains closed — 2026-10-28 12:18 UTC

At `12:18:47Z`, I/O PSI avg10 had fallen to **0.01% some / 0.01% full**, but
memory PSI avg10 remained **36.13% some / 31.37% full**. About **10 GiB** was
available and **3.5/4 GiB** swap was in use. No tests, build, or mypy job was
started. Both memory and I/O must be below the 1% admission threshold before
runtime verification resumes.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Atomic collection run/checkpoint creation | IMPLEMENTED, VALIDATION PENDING | Commit `36546cd`; runtime tests and strict typing await memory admission. |
| Research-schedule module | IMPLEMENTED, VALIDATION PENDING | Commit `cd248ce`; corrected fixture is not yet runtime-verified. |
| Frontier overall | PARTIALLY VERIFIED | Latest full Frontier suite predates current edits; live cross-venue evidence, broader regressions, and deployment remain open. |

Next safe action: sample host pressure again; run targeted tmpfs tests only when
both PSI avg10 values fall below 1%.

## Atomic initial collection checkpoint — 2026-10-28 12:16 UTC

Source-only review found that finite collection startup wrote a run record and
its first checkpoint in separate SQLite transactions. A process failure between
those writes could leave a run without the durable checkpoint required by
history and resume. `BoundedSourceCollector.start()` now writes both records in
one transaction through `create_run_with_initial_checkpoint()`. A failed
checkpoint insert rolls back the run row as well; source requests happen only
after this transaction commits.

A fixture regression installs a temporary SQLite trigger that rejects the
initial checkpoint insert and verifies that both tables remain empty and no
adapter request starts. The existing successful finite-capture test also checks
that the first durable state is `created`. Ruff and format checks pass, and
`git diff --check` is clean. Runtime tests and strict typing have not run yet.

At 12:16:02 UTC memory PSI avg10 was **26.58% some / 17.06% full**, I/O PSI
avg10 was **3.67% some / 2.54% full**, about **10 GiB** was available, and
**3.5/4 GiB** swap was in use. No test was launched against this sample. No
service, live source, capture, or protected store was used. The pre-existing
untracked public-capture directory remains untouched.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Initial collection persistence atomicity | IMPLEMENTED, VALIDATION PENDING | Run and initial checkpoint now share a transaction; rollback and success-state tests are committed after runtime admission. |
| Frontier overall | PARTIALLY VERIFIED | Broad MIDAS regression, authorized cross-venue evidence, production recovery, and deployment remain open. |

Next safe action: after fresh memory and I/O PSI avg10 both fall below 1%, run
the focused collection module with a unique tmpfs pytest basetemp and then
strictly type-check the changed module.

## Reality research-schedule fixture correction — 2026-10-28 12:12 UTC

Test commit cd248ce fixes a synthetic fixture that patched the wrong Python
module identity. The schedule test changed top-level test_reality_foundry.START,
while dataset_fixture uses tests.test_reality_foundry.START. A read-only
identity probe confirmed those are distinct modules, so the intended time
shift never reached the synthetic tape. The second dataset therefore reused
the same final-test period and the research-access guard correctly rejected
the overlap. The fixture now patches the imported module object and asserts
the generated dataset IDs differ.

The first isolated invocation omitted the tests directory from PYTHONPATH and
failed while resolving the monkeypatch target. Rerunning with
PYTHONPATH=packages:.:tests reached the test body: three tests passed, while
the overlapping-period guard rejected the stale duplicate fixture. All data
and the one opened temporary evaluation record remained under unique /dev/shm
basetemps; no tracked or protected store was accessed. Ruff, format, and
git diff --check pass.

No runtime test has been run against cd248ce yet. At 12:12:41Z memory PSI
avg10 was **44.70% some / 40.61% full**, I/O PSI was **0.57% some / 0.57%
full**, and about **10 GiB** was available. The relevant test remains deferred
until a fresh memory sample falls below the 1% admission threshold.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Research-schedule fixture alias correction | IMPLEMENTED, VALIDATION PENDING | cd248ce patches the module used by dataset_fixture and checks IDs differ; runtime test awaits resource admission. |
| Research-schedule tests | PARTIALLY VERIFIED | Three of four pass on the pre-fix fixture; the fourth stopped safely on the intentional overlap guard. |
| Frontier overall | PARTIALLY VERIFIED | Broad regression, source permission/evidence, and deployment remain open. |

Next safe action: after memory PSI avg10 falls below 1%, run the exact
research-schedule module with PYTHONPATH=packages:.:tests and a fresh tmpfs
basetemp; preserve the overlap guard.

## Reality calibration and dashboard slices — 2026-10-28 12:10 UTC

The isolated calibration module passed **18/18** tests in 0.46 seconds
(0.79 seconds wall time), peak RSS 52,396 KiB, zero swaps, and no socket
messages. It used deterministic synthetic arithmetic fixtures. At 12:10:33Z
before the run, memory PSI avg10 was 0.00%, I/O was 0.74% some / 0.72% full,
and about 10 GiB was available; at 12:10:38Z afterward, memory remained 0.00%
and I/O was 0.40% some / 0.39% full.

The isolated Reality dashboard API module passed **14/14** in 0.70 seconds,
peak RSS 65,308 KiB, zero swaps, and no socket messages. Its router was bound
to tmp_path, and the operation endpoint's systemctl runner was mocked; no
service command ran. The existing Starlette/httpx deprecation warning
remains. At 12:10:42Z before this run, memory PSI was 0.00%, I/O was 0.60%
some / 0.59% full; at 12:10:49Z afterward, memory remained 0.00% but I/O
rose to **1.53% some / 1.35% full**. About 10 GiB remained available.

The bounded Reality coverage now stands at **71 passing tests**, plus one
self-signaling test intentionally deselected. No protected recording, public
source, or production service was accessed. I/O PSI exceeded the 1% gate after
the dashboard run, so no subsequent tests were started.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Reality model, panel, and calibration slices | PARTIALLY VERIFIED | 13 model tests, 26 panel tests, and 18 calibration tests pass; one self-signaling case remains excluded. |
| Reality dashboard API slice | COMPLETE AND VERIFIED | 14/14 pass against temporary roots with mocked service command. |
| Further test admission | DEFERRED | Post-dashboard I/O PSI was above 1%. |
| Frontier overall | PARTIALLY VERIFIED | Full MIDAS regression, held-source access, genuine cross-venue science, and deployment remain open. |

Next safe action: re-sample both PSI values and review the next candidate test
roots before starting further legacy checks.

## Reality model and panel regression slices — 2026-10-28 12:09 UTC

After the 12:08 admission hold, the 12:09:15Z sample fell below the 1% gate
(memory PSI avg10 0.04% some / 0.04% full; I/O 0.73% some / 0.67% full; about 10
GiB available). The bounded Reality model run passed **13/13** selected tests
in 8.48 seconds; one test that signals its own runner was deselected. Peak
RSS was 53,032 KiB, with zero swaps and no socket messages. Its HTTP fixture
was mocked, its WebSocket fixtures bound to localhost, and writes used a
unique /dev/shm basetemp.

The full tests/test_reality_panel.py module then passed **26/26** in 0.24
seconds, with 46,876 KiB peak RSS, zero swaps, and no socket messages. Its
source-discovery case used MockTransport and an in-memory recorder callback.
The 12:09:47Z pre-run sample had memory PSI avg10 0.00%, I/O 0.77% some /
0.71% full, and about 10 GiB available; at 12:09:52Z afterward, memory
remained 0.00% and I/O was 0.87% some / 0.69% full. No protected recording,
public source, or service was accessed.

The next read-only review found tests/test_reality_calibration.py contains
synthetic arithmetic fixtures and no persistent-root, network, or subprocess
operations. It was not run: at 12:10:00Z I/O PSI avg10 some had risen to
**1.04%**, just above the admission threshold.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Reality model slice | PARTIALLY VERIFIED | 13 selected tests pass; the self-signaling test remains unrun. |
| Reality panel/observation slice | COMPLETE AND VERIFIED | 26/26 synthetic tests pass. |
| Reality calibration slice | DEFERRED | Effects reviewed; no run at I/O PSI 1.04%. |
| Full MIDAS legacy suite | PARTIALLY VERIFIED | Other Reality, Veritas, Arena, integration, and broader modules remain unrun. |
| Frontier overall | PARTIALLY VERIFIED | Live cross-venue permissions/evidence, broad regression/browser acceptance, and deployment remain open. |

Next safe action: rerun a fresh PSI sample before admitting calibration or
other tests. Keep the self-signaling Reality case excluded unless its signal
handling can be safely isolated.

## Reality regression admission hold — 2026-10-28 12:08 UTC

A source-only review of tests/test_reality.py found 14 tests. Their recording
and replay writes use tmp_path; REST discovery uses httpx.MockTransport, and
the WebSocket cases bind only to ephemeral 127.0.0.1 servers. The config
isolation test passes the historical Laboratory path only to a constructor
that is expected to reject it. One test sends SIGTERM to its own test-runner
process; exclude that case from the next bounded run.

No Reality test was started. At 12:08:02Z, host memory PSI avg10 was **50.74%
some / 45.23% full**, I/O PSI was **0.84% some / 0.68% full**, available
memory was about **10 GiB**, and swap was **3.5/4 GiB** used. A read-only
process listing showed PID 369790 running
scripts/veritas_gap_detail_v2_batch.py; it was left untouched. This sample
does not establish what caused the pressure.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Reality model regression | DEFERRED | Test effects reviewed; no run under elevated memory PSI. |
| Full MIDAS legacy suite | PARTIALLY VERIFIED | Unit, simulation, property, Laboratory, and selected Arena slices pass; most legacy modules remain unrun. |
| Frontier overall | PARTIALLY VERIFIED | Live multi-venue permission/evidence, broad legacy/browser acceptance, and deployment remain open. |

Next safe action: after a fresh memory and I/O sample meets the 1% gate, run
tests/test_reality.py excluding bounded_transport_burst_is_preserved_under_slow_writes
with a tmpfs basetemp. Do not interact with the observed Veritas process.

## Coinbase hold-message accuracy — 2026-10-28 12:05 UTC

Code commit 9552db5 corrects the Coinbase source hold message. The prior
wording implied that acknowledging the reviewed Market Data Terms version
would lift the hold; the implemented policy requires a separately validated
permission and intended-scope review, and a version acknowledgement alone is
insufficient. The revised message states that distinction while preserving
the unconditional hold.

The focused offline Coinbase module passes **13/13** in 0.77 seconds (1.22
seconds wall time), with 77,756 KiB peak RSS, zero swaps, zero filesystem
input, and zero socket messages. Ruff, format, and git diff --check pass. The
test asserts both the permission/scope requirement and that acknowledgement
alone cannot lift the hold. Strict mypy passes for the changed Coinbase
adapter (one source file). No Coinbase request or held record was accessed.

At 12:05:41Z before the run, memory PSI avg10 was **0.00%**, I/O was **0.61%
some / 0.49% full**, and about **10 GiB** was available. At 12:06:00Z
afterward, memory PSI remained **0.00%**, I/O was **0.72% some / 0.40% full**,
and about **10 GiB** remained available.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Coinbase source-policy explanation | COMPLETE AND VERIFIED | Accurate hold reason is pinned by a 13-test offline module; policy remains held. |
| Coinbase live validation | BLOCKED | Terms, jurisdiction, intended use, and validated permission remain unresolved; no probe was made. |
| Frontier overall | PARTIALLY VERIFIED | Cross-venue evidence, broad legacy/browser acceptance, and deployment remain open. |

Next safe action: keep the source held and continue source-independent work;
do not interpret a terms-version acknowledgement as permission.

## Legacy Laboratory and Arena fixture refresh — 2026-10-28 12:03 UTC

Code commit bf9d933 updates the two test fixtures described below.

The first tmpfs-backed Laboratory slice exposed an outdated test-only resource
snapshot: it omitted available_cpu_count and host_load_avg1, so the current
fail-closed admission gate correctly returned resource_pressure_unavailable.
Its denial test also changed CPU PSI, whose magnitude is intentionally not a
host-saturation signal under the current quota-aware gate. The fixture now
supplies the same bounded CPU fields as Arena's ready_snapshot; the denial
case uses a normalized host load at the configured limit.

The first Arena replay slice exposed a mismatched synthetic evidence identity.
The cross-venue relationship fixture cited source-left and source-right,
which were not the pinned markets' observation IDs. The verifier correctly
rejected that relationship, and replay produced one invalid-edge candidate.
The fixture now cites each market's actual provenance observation and asserts
the relationship reaches VERIFIED before expecting both payoff directions.

Final bounded verification on the changed tree:

- tests/unit tests/simulation tests/property: **153 passed** in 5.37 seconds;
  peak RSS 73,472 KiB, zero swaps, no sockets.
- tests/laboratory: **75 passed** in 26.67 seconds; peak RSS 165,892 KiB,
  zero swaps and filesystem input. An existing Starlette/httpx deprecation
  warning remains.
- tests/arena/test_admission.py tests/arena/test_frontier_replay.py
  tests/arena/test_frontier_timeline.py: **30 passed** in 2.10 seconds; peak
  RSS 198,056 KiB, zero swaps, filesystem input, and sockets.
- Ruff check, Ruff format check, and git diff --check pass for both changed
  test modules.

All pytest basetemps were unique directories under /dev/shm; Laboratory's
existing data/datasets inputs were read-only. No production store, service,
public source, or held capture was accessed. At 12:03:40Z, host memory PSI
avg10 was **54.85% some / 49.81% full**, I/O PSI was **1.28% some / 1.22%
full**, and about **10 GiB** was available. The I/O reading exceeded the 1%
admission threshold, so the redundant combined rerun and broader suite were
not started. This sample is not a causal attribution to these test processes.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Legacy unit, simulation, and property slice | COMPLETE AND VERIFIED | 153/153 pass on the current tree. |
| Laboratory regression slice | COMPLETE AND VERIFIED | 75/75 pass after aligning the synthetic gate inputs with the current contract. |
| Arena admission and Frontier replay | COMPLETE AND VERIFIED | 30/30 pass; replay fixture now cites pinned observation provenance. |
| Full MIDAS legacy suite | PARTIALLY VERIFIED | Only the bounded slices above were admitted; other modules remain unrun. |
| Frontier overall | PARTIALLY VERIFIED | Live multi-venue evidence, full legacy/browser acceptance, and deployment remain open. |

Next safe action: re-sample host PSI before the next test workload. Continue
with source-independent audit while holding broader runs whenever I/O avg10 is
at or above 1%; preserve the current source-use and deployment gates.

## Broader MIDAS regression admission — 2026-10-28 11:57 UTC

The exact Frontier suite and strict-mypy slice are complete as recorded in the
11:55 entry. I did not start the full repository suite. At `11:57:28Z`, memory
PSI avg10 was **39.00% some / 35.46% full**, I/O PSI **0.93% some / 0.93%
full**, and about **10 GiB** was available. This exceeds the memory admission
gate.

A read-only scan found legacy tests that reference the hard-coded
`/home/charlie/midas/data/laboratory-final` path and tests that start
subprocesses or local servers. Before any broad legacy run, review those tests
for operational data writes and redirect their roots to an isolated temporary
directory where supported. No tests, source probes, or service operations were
performed for this check.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Frontier suite and source-use guards | COMPLETE AND VERIFIED | Exact 420/420 suite and strict-mypy evidence in the preceding entry. |
| Full MIDAS legacy suite | DEFERRED | Host memory PSI exceeds 1%; test data-root isolation is not yet verified. |
| Frontier overall | PARTIALLY VERIFIED | Browser/legacy acceptance, genuine cross-venue evidence, and deployment remain open. |

**Next safe action:** after a fresh memory and I/O PSI sample below 1%, review
the identified legacy test roots, then run only the isolated broad tests that
cannot alter preserved Reality, Veritas, Arena, or Laboratory data.

## Exact-tree probe hold and suite verification — 2026-10-28 11:55 UTC

Strict mypy passes for the final source-hold path in `apps/api/frontier.py`,
`packages/midas/frontier/adapters/base.py`, and
`packages/midas/frontier/adapters/coinbase.py` (**3 source files**, no issues).
The exact current Frontier tree then passed **420/420** tests in **29.02 s**
pytest time (**30.50 s** wall), with **378,276 KiB** peak RSS, zero swaps,
filesystem input, and socket messages, and 912 filesystem-output blocks. One
existing Starlette/httpx deprecation warning remains.

At `11:55:04Z` before the run, memory PSI avg10 was **0.00%**, I/O was
**0.85% some / 0.70% full**, and about **10 GiB** was available. At
`11:55:41Z` afterward, memory PSI remained **0.00%**, I/O was **0.91% some /
0.63% full**, and about **10 GiB** remained available. This run is exact-tree
verification after `4b8c9f0`'s type-narrowing refactor.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Coinbase source-use hold | COMPLETE AND VERIFIED | Coinbase config, adapter, transport, and API regressions pass in the exact 420-test suite. |
| API source-use hold | COMPLETE AND VERIFIED | All 11 probe routes enforce policy; effective availability is surfaced; strict mypy passes. |
| Frontier Python regression | COMPLETE AND VERIFIED | 420/420 current-tree tests pass; one existing deprecation warning. |
| Frontier overall | PARTIALLY VERIFIED | Cross-venue permissions/evidence, broader repository/browser acceptance, and deployment remain open. |

**Next safe action:** continue with source-independent full-repository and
frontend acceptance checks after a fresh resource sample. Keep live cross-venue
data use and production transition behind their existing permission and
deployment gates.

## Probe source-use hold closeout and exact-tree checks — 2026-10-28 11:53 UTC

Commits `782df89`, `9776427`, and `4b8c9f0` enforce source-use holds across
all 11 public probe routes, report effective probe eligibility, and preserve
the validated config in route scope. The Coinbase API regression requires HTTP
409 before any transport request. Tests were corrected to pass the same config
to adapter and transport and to persist Coinbase config while its source stays
held.

The Coinbase module passed **13/13** and the four affected Kalshi/Coinbase
collection cases passed **4/4**. The full Frontier suite then passed
**420/420** in **28.88 s** (30.30 s wall), peak RSS **378,920 KiB**, zero swaps,
zero filesystem input, 368 filesystem-output blocks, and zero socket messages.
Pre-run PSI at `11:51:24Z` was memory **0.00%**, I/O **0.76% some / 0.73%
full**. Post-run at `11:52:02Z`, memory remained **0.00%**, I/O was **0.52%**,
and about **10 GiB** was available. One existing Starlette/httpx deprecation
warning was emitted.

The full run preceded the final `4b8c9f0` API helper refactor. A strict-mypy
run on the prior boolean helper reported 13 union-attribute errors where the
optional config was used after a separate boolean check. The current helper
returns the validated config after enforcing flags and policy hold, preserving
type narrowing. Ruff check/format pass; strict mypy and tests have not been
rerun against that exact commit.

The latest host sample at `11:53:54Z` showed memory PSI avg10 **1.16% some /
1.02% full**, I/O PSI **0.91% some / 0.83% full**, about **10 GiB** available,
and swap **3.5/4 GiB** used. The memory gate is exceeded; no further test or
mypy workload was started.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Coinbase source-use hold | COMPLETE AND VERIFIED | Config/adapter/transport/API guards; focused module 13/13 on pre-refactor code. |
| API source-use hold | PARTIALLY VERIFIED | Full suite 420/420 before type-narrowing refactor; exact-tree rerun and strict mypy pending. |
| Frontier overall | PARTIALLY VERIFIED | Live cross-venue evidence, broader MIDAS/browser checks, and deployment remain open. |

**Next safe action:** wait for a fresh memory and I/O PSI avg10 below 1%, run
strict mypy on `apps/api/frontier.py` and the three modified adapter modules,
then rerun the Frontier suite once on tmpfs if the gate remains admitted.

## API source-use hold preflight — 2026-10-28 11:48 UTC

Code commit `782df89` makes every public probe route reject a source whose
`probe_policy_block_reason` is set, in addition to requiring enabled probe
flags. The check runs before route locks and adapter calls. The Coinbase API
regression asserts HTTP 409 and zero transport requests for a held source.

The first focused run before this change completed **12/13** Coinbase tests;
one existing API success-path case failed because a test-only transport
returned fixture data while the application correctly hid the held venue's
stored records. This exposed the missing API preflight: the route reached the
fixture transport rather than rejecting the held source first. It made no
external request. The run took **1.28 s**, peaked at **78,636 KiB**, and used
zero swaps. Ruff check/format and `git diff --check` pass for the fix, but the
updated Coinbase module has not run.

Before the attempt at `11:46:30Z`, memory PSI avg10 was **0.00%**, I/O PSI was
**0.41%**, and about **10 GiB** was available. At `11:46:51Z`, I/O PSI rose to
**1.19%**. The latest sample at `11:47:55Z` showed memory PSI **52.19% some /
46.63% full** and I/O PSI **1.10% some / 0.75% full**; further tests remain
gated. No live source or protected service was used.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| API source-use hold preflight | IMPLEMENTED, LIVE VALIDATION PENDING | `782df89`; all 11 probe routes guard source holds; updated module awaits resource admission. |
| Coinbase focused module | PARTIALLY VERIFIED | Pre-fix attempt 12/13; failure led to this API guard and test change; rerun pending. |
| Frontier overall | PARTIALLY VERIFIED | The existing full suite predates the latest code; broader regression, cross-venue evidence, and deployment remain open. |

**Next safe action:** require a fresh memory and I/O PSI avg10 below 1%, rerun
`tests/frontier/test_coinbase.py` on tmpfs, then run the Frontier suite once if
the gate remains admitted.

## Kraken fixture config alignment — 2026-10-28 11:45 UTC

Test commit `92b5bf0` updates the Kraken adapter fixture to construct one
`KrakenSpotConfig` and pass it to both `KrakenSpotAdapter` and its
`PublicReadTransport`. This keeps the test aligned with `BaseReadOnlyAdapter`'s
new invariant that an injected transport's concrete config type and value must
match the adapter's. Ruff check, Ruff format check, and `git diff --check` pass
for this file. The Frontier tests remain unrun because memory PSI is above the
1% admission threshold; the latest recorded sample is in the 11:44 entry.

## Coinbase source-use hold integrity fix — 2026-10-28 11:44 UTC

Code commit `ca14e37` tightens the Coinbase public-source policy boundary.
Review found that the terms-version acknowledgement could be paired with
`probe_policy_block_reason=None`, even though the current source-use review
requires a validated permission and intended-scope loader that does not exist.
The config validator now rejects any cleared hold, including an exact-version
acknowledgement. The adapter requires the exact `CoinbaseSpotConfig` type, and
the base adapter rejects an injected transport unless its concrete config type
and value match the adapter config. This closes generic-config and mismatched-
transport paths around the source-specific hold.

Offline Coinbase parser/API fixtures now use a test-only in-memory transport
with the source-use hold still present. Regressions cover direct and copied
hold clearing, the copied-config exact-ack case, generic config substitution,
and mismatched transport config. Ruff check, Ruff format check, and
`git diff --check` pass. The tests have **not run**.

At `2026-10-28T11:43:51Z`, memory PSI avg10 was **6.41% some / 5.82% full**,
I/O PSI was **0.59% some / 0.45% full**, about **10 GiB** was available, and
swap was **3.5/4 GiB** used. PID 344473 was no longer present in the sample.
Test execution remains gated on memory PSI falling below 1%; no test or replay
was started under the current sample. The `418/418` result is still for
`1dd0987`, before `ca14e37`.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Coinbase source-use hold integrity | IMPLEMENTED, LIVE VALIDATION PENDING | `ca14e37`; static checks pass; targeted and full tests await resource admission. |
| Frontier overall | PARTIALLY VERIFIED | Cross-venue permission/evidence, broad regressions, and deployment remain open. |

**Next safe action:** when a fresh sample shows memory and I/O PSI below 1%,
run `tests/frontier/test_coinbase.py` on tmpfs, then run the Frontier suite once
if the gate remains admitted. Preserve `data/frontier-public-probes/` as
untracked research data.

## Coinbase copied-config hold regression pending resource admission — 2026-10-28 11:38 UTC

Test commit `c6dfff1` adds a regression for clearing Coinbase's source-use
hold on a `CoinbaseSpotConfig` copied with `model_copy(update=...)`. It checks
that concrete-subclass revalidation rejects the copied config at both the
adapter and transport constructors, before any HTTP client can be created.
Ruff and `git diff --check` pass, but the new test has **not run**.

At `11:38:45Z`, memory PSI avg10 was **35.09% some / 29.50% full**, I/O PSI
was **3.88% some / 3.67% full**, and about **10 GiB** was available. Host swap
was 3.4/4 GiB used. A read-only process sample showed an existing
`veritas_gap_detail_v2_batch.py` process (PID 344473) in D state; it was left
untouched. No test, replay, source probe, protected-service operation, or
deployment was attempted under this pressure.

The prior **418/418** full-suite result remains valid for the product code at
`1dd0987`; `c6dfff1` adds one unrun regression, so it does not establish the
current test tree's full-suite result.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Adapter resource-bound implementation | COMPLETE AND VERIFIED | Concrete config revalidation and 418 existing Frontier tests pass on product commit `1dd0987`. |
| Coinbase copied-config terms-hold regression | PARTIALLY VERIFIED | Test is committed and linted; execution waits for a fresh PSI sample below the 1% admission limit. |
| Frontier project overall | PARTIALLY VERIFIED | Full current test tree, live cross-venue science, broader MIDAS regression, and production deployment remain open. |

**Next safe action:** once a fresh host sample is below the 1% PSI gate, run
`PYTHONPATH=packages:. /home/charlie/midas/.venv/bin/python -m pytest -q tests/frontier/test_coinbase.py --basetemp=/dev/shm/midas-frontier-coinbase-copy-gate-<UTC-ID>`.
If it passes, run the full Frontier suite once on the same tree and update the
report from the measured results.

## Revalidate public-source resource configuration — 2026-10-28 11:35 UTC

Code commit `1dd0987` closes a bounded-transport configuration gap. A copied
`AdapterConfig` could bypass field validators and set `max_response_bytes` to
one billion; `PublicReadTransport` used the value when constructing its
bounded client and streaming responses. Configurations now revalidate against
their concrete model type. `BaseReadOnlyAdapter` and `PublicReadTransport`
reject invalid copies before adapter use or HTTP client creation. The
concrete-type check retains Kraken/Coinbase subclass validators.

The adapter module passed **71/71** and collection plus collection-API modules
passed **34/34**. Full `tests/frontier` on the exact current tree passed
**418/418** in 30.09 seconds (31.53 seconds wall time), with **379,004 KiB**
peak RSS, zero process swaps, zero filesystem input, 392 output blocks, and
zero socket messages. Ruff check/format, strict mypy for nine production
modules, and `git diff --check` passed. One existing Starlette/httpx
deprecation warning remains. The full run used tmpfs at
`/dev/shm/midas-frontier-adapter-config-full-20261028T1135Z`.

Before the full run at `11:34:58Z`, memory PSI avg10 was **0.00%**, I/O PSI
was **0.66% some / 0.45% full**, and about **10 GiB** was available. At
`11:35:49Z`, memory PSI avg10 was **0.00%**, I/O PSI was **0.57% some / 0.47%
full**, and about **10 GiB** remained available. Host swap was 3.4/4 GiB used;
the full test process used none. No live source, protected capture, production
service, collector, or Arena job was used. The public-probe directory remains
untracked and untouched. Frontier remains **PARTIALLY VERIFIED**.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Copied adapter resource configuration | COMPLETE AND VERIFIED | Out-of-bound response size is rejected before transport/client setup; adapter and collection regressions pass. |
| Full Frontier Python suite | COMPLETE AND VERIFIED | 418/418 pass on code commit `1dd0987`; one existing deprecation warning remains. |
| Live cross-venue validation | BLOCKED | No authorized genuine source evidence was used to establish a cross-venue match. |
| Frontier project overall | PARTIALLY VERIFIED | Broader MIDAS regression, live science, production recovery, and deployment remain open. |

**Next safe action:** continue source-independent acceptance review. Recheck
host PSI before any further broad test or replay workload.

## Revalidate copied virtual execution assumptions — 2026-10-28 11:31 UTC

Code commit `e26efab` fixes an over-depth candidate path reproduced with a
copied `ExecutionScenario`. A model with `fill_fraction=2` bypassed Pydantic
validation through `model_copy(update=...)`; replay generated two candidate
positions of quantity 20 against displayed depth 10, and both independent
audits reported `verified`.

`ExecutionScenario.has_valid_structure` now reconstructs scenario payloads
through Pydantic validation. Cross-venue, implication, single-market, bounded
basket, and joint-state candidate entry points reject malformed assumptions.
Replay, paired replay, event-time replay, and discovery-scope comparison reject
them before use. Direct independent audit returns `INCOMPLETE` and clears
practical eligibility. Economic model v21, audit v21, replay v20, timeline v2,
and discovery comparison v2 identify these contracts.

The focused affected-module slices passed **100/100**. Full `tests/frontier`
passed **417/417** in 30.54 seconds (32.02 seconds wall time); peak RSS was
**380,336 KiB**, process swaps **0**, filesystem input **0**, output 1,872
blocks, and socket messages sent/received **0**. Ruff check/format, strict
mypy for seven production modules, and `git diff --check` passed. One existing
Starlette/httpx deprecation warning remains. The suite used tmpfs at
`/dev/shm/midas-frontier-scenario-integrity-full-20261028T1131Z`.

Before the run, memory PSI avg10 was **0.00%**, I/O PSI was **0.33% some /
0.16% full**, and about **10 GiB** was available. At `11:31:38Z`, memory PSI
avg10 remained **0.00%**, I/O PSI was **0.72% some / 0.71% full**, and about
**10 GiB** remained available. Host swap was already 3.4/4 GiB used; this
process used none. No public source, protected capture, production service,
worker, or Arena job was accessed. The public-probe directory remains
untracked and untouched. Frontier remains **PARTIALLY VERIFIED**.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Copied execution-scenario validation | COMPLETE AND VERIFIED | Invalid fill fraction cannot scale displayed depth or pass audit/replay; all decisive scenario entry points revalidate. |
| Full Frontier Python suite | COMPLETE AND VERIFIED | 417/417 pass on code commit `e26efab`; one existing deprecation warning remains. |
| Genuine cross-venue science | BLOCKED | No authorized, accessible evidence was used to establish a genuine cross-venue match. |
| Frontier project overall | PARTIALLY VERIFIED | Broader MIDAS regression, live evidence, production recovery, and deployment remain open. |

**Next safe action:** continue source-independent acceptance review. Take a
fresh host PSI sample before any further test or replay workload.

## Validate full book snapshots before replay time arithmetic — 2026-10-28 11:24 UTC

Code commit `ac85442` extends runtime book validation from individual price
levels to the complete `BookSnapshot`. A controlled fixture copied a naive
`received_at_utc`; replay previously reached time subtraction and raised
`TypeError` instead of returning an evidence classification. Book snapshots
are now reconstructed through Pydantic validation at candidate generation,
independent audit, and replay boundaries. Replay validates before deriving
its default cutoff. This covers snapshot and provenance timestamps as well as
price levels, quantities, and their timestamps.

The new regression confirms naive copied receipt time is rejected before
cutoff calculation. The focused book-integrity slice passed **10/10**. Full
`tests/frontier` passed **415/415** in 30.80 seconds (32.27 seconds wall time)
using `/dev/shm/midas-frontier-book-structure-final-20261028T1124Z`. Peak RSS
was **378,208 KiB**, process swaps **0**, filesystem input **0**, output 1,856
blocks, and socket messages sent/received **0**. Ruff check/format, strict
mypy for five production modules, and `git diff --check` passed. One existing
Starlette/httpx deprecation warning remains.

At `11:24:07Z`, about 10 GiB was available, memory PSI avg10 was 0%, and I/O
PSI was 0.29% some / 0.05% full. At `11:24:44Z`, about 10 GiB remained
available, memory PSI avg10 was 0%, and I/O PSI was 0.32% some / 0% full. No
live source, protected capture, production service, or Arena job was used.
The preserved public capture remains unstaged and untouched. Frontier remains
**PARTIALLY VERIFIED**.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Copied book timestamp and level integrity | COMPLETE AND VERIFIED | Full snapshots are revalidated at generation, audit, and replay; naive replay timestamps fail before cutoff calculation. |
| Full Frontier Python suite | COMPLETE AND VERIFIED | 415/415 pass on code commit `ac85442`; one existing deprecation warning remains. |
| Live cross-venue matching and economics | BLOCKED | Authorized genuine multi-venue evidence remains unavailable. |
| Frontier project overall | PARTIALLY VERIFIED | Broader MIDAS regression, live science, production recovery, and deployment remain open. |

**Next safe action:** continue source-independent acceptance review. Recheck
host PSI before another test workload; shared I/O pressure remains below the
1% gate.

## Revalidate copied market contracts — 2026-10-28 11:21 UTC

Code commit `da347a4` addresses a copied-market failure reproduced with a
three-outcome fixture. Duplicating one `native_instrument_id` through
`model_copy(update=...)` bypassed `FrontierMarket` validation, then the public
multi-outcome generator raised `ValueError` while constructing fill-pattern
sensitivity. `FrontierMarket.has_valid_structure` now reconstructs the
complete nested market payload with Pydantic validation. Binary, implication,
single-market, bounded-basket, and joint-state generators fail closed;
independent audit marks a selected invalid market incomplete; deterministic
replay rejects invalid markets before candidate generation.

The regression confirms the copied duplicate ID no longer throws and cannot
reach a verified candidate, audit, or replay result. Economic model v19,
independent audit v19, and replay v18 identify the new acceptance rules.
The first full run after the implementation had **412 passed and 2 failed**:
both failures asserted narrower diagnostic text that the new structural gate
now supersedes; a Pydantic serializer warning also appeared while inspecting a
deliberately copied field. The tests now assert the earlier structural
rejection, and validation-only reconstruction suppresses serializer warnings.
The focused cases passed **3/3** after correction.

The final full `tests/frontier` run passed **414/414** in 29.94 seconds
(31.40 seconds wall time) using
`/dev/shm/midas-frontier-market-copy-final2-20261028T1121Z`. Peak RSS was
**377,768 KiB**, process swaps **0**, filesystem input **0**, filesystem
output 376 blocks, and socket messages sent/received **0**. Ruff check/format,
strict mypy for five production modules, and `git diff --check` passed. One
existing Starlette/httpx deprecation warning remains.

At `11:20:51Z`, about 10 GiB was available, memory PSI avg10 was 0%, and I/O
PSI was 0.34% some / 0% full. At `11:21:37Z`, about 10 GiB remained available,
memory PSI avg10 was 0%, and I/O PSI was 0.64% some / 0.44% full. No live
source, protected capture, production service, or Arena job was used. The
saved public capture remains unstaged and untouched. Frontier remains
**PARTIALLY VERIFIED**.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Copied market contract integrity | COMPLETE AND VERIFIED | Nested market validators rerun at generation, audit, and replay boundaries; duplicate-instrument fixture no longer throws. |
| Full Frontier Python suite | COMPLETE AND VERIFIED | 414/414 pass on code commit `da347a4`; one existing deprecation warning remains. |
| Live cross-venue matching and economics | BLOCKED | Authorized genuine multi-venue evidence remains unavailable. |
| Frontier project overall | PARTIALLY VERIFIED | Broader MIDAS regression, live science, production recovery, and deployment remain open. |

**Next safe action:** continue source-independent acceptance review. Recheck
host PSI before another test workload; I/O pressure was below the 1% gate but
had risen to 0.64% some / 0.44% full after this run.

## Revalidate joint-state content identities — 2026-10-28 11:15 UTC

Code commit `1f6bd64` closes a copied joint-state map identity gap. A bounded
fixture changed `external_assertion_id` through `model_copy(update=...)` while
retaining the original `mapping_id`; before the fix, candidate generation
returned three conditional candidates and the independent audit marked one
verified. `JointStateMap.content_identity_matches` now reconstructs the bounded
definition, reruns its validation, and hashes the canonical payload at the
candidate-generation, independent-audit, and replay boundaries.

The regression confirms a stale-ID copy produces no candidates, makes an
existing candidate audit incomplete, and is rejected by replay. The focused
joint-state test module passed **11/11**. Full `tests/frontier` passed
**413/413** in 30.79 seconds (32.26 seconds wall time) using
`/dev/shm/midas-frontier-joint-map-final-20261028T1115Z`. Peak RSS was
**379,304 KiB**, process swaps **0**, filesystem input **0**, output 2,688
blocks, and socket messages sent/received **0**. Ruff check/format, strict
mypy for five production modules, and `git diff --check` passed. One existing
Starlette/httpx deprecation warning remains.

At `11:14:51Z`, about 10 GiB was available, memory PSI avg10 was 0%, and I/O
PSI avg10 was 0%. At `11:15:29Z`, about 10 GiB remained available, memory PSI
avg10 was 0%, and I/O PSI was 0.03% some / 0% full. No live source, protected
capture, production service, or Arena job was used. The saved public capture
remains unstaged and untouched. Frontier remains **PARTIALLY VERIFIED**.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Joint-state map content integrity | COMPLETE AND VERIFIED | Stale copied IDs fail closed at candidate generation, independent audit, and replay. External semantics remain unverified by design. |
| Full Frontier Python suite | COMPLETE AND VERIFIED | 413/413 pass on code commit `1f6bd64`; one existing deprecation warning remains. |
| Live cross-venue matching and economics | BLOCKED | Authorized genuine multi-venue evidence remains unavailable. |
| Frontier project overall | PARTIALLY VERIFIED | Broader MIDAS regression, live science, production recovery, and deployment remain open. |

## Reject malformed copied book depth — 2026-10-28 11:12 UTC

Code commit `435153d` adds a runtime integrity check for order-book levels,
because Pydantic `model_copy(update=...)` bypasses the model's duplicate-price
validator. Cross-venue, multi-outcome, bounded-basket, and joint-state
candidate generation now refuse duplicate or otherwise invalid price levels;
the independent audit returns incomplete evidence for such a selected book,
and deterministic replay rejects it before candidate generation. Economic
model v17, independent audit v17, and replay v16 identify these semantics.

Fixture regressions cover inflated duplicate top-ask depth at candidate, audit,
and replay boundaries plus copied non-finite/negative prices, non-finite/zero
quantities, and naive level timestamps. The focused checks passed **8/8**. An
initial local run of the five copied-level cases used a nonexistent fixture
instrument ID; the test setup was corrected to select the normalized fixture
instrument and then passed.

The final full `tests/frontier` run passed **412/412** in 29.83 seconds
(31.33 seconds wall time) using
`/dev/shm/midas-frontier-book-depth-final-20261028T1112Z`. Peak RSS was
**378,608 KiB**, process swaps **0**, filesystem input **0**, filesystem
output 376 blocks, and socket messages sent/received **0**. Ruff check/format,
strict mypy for five production modules, and `git diff --check` passed. One
existing Starlette/httpx deprecation warning remains.

Before the test at `11:10:34Z`, roughly 10 GiB was available, memory PSI avg10
was 0%, and I/O PSI was 0.06% some / 0.01% full. At `11:12:10Z`, roughly 10
GiB remained available, memory PSI avg10 was 0%, and I/O PSI was 0.12% some /
0% full. No live source, protected capture, production service, or Arena job
was used. The pre-existing untracked public capture remains unstaged and
untouched. Frontier remains **PARTIALLY VERIFIED**.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Copied book-level integrity | COMPLETE AND VERIFIED | Generator, independent-audit, and replay guards reject duplicate or invalid levels; the bounded adversarial regressions pass. |
| Full Frontier Python suite | COMPLETE AND VERIFIED | 412/412 pass on code commit `435153d`; one existing deprecation warning remains. |
| Live cross-venue matching and economics | BLOCKED | Authorized genuine multi-venue evidence remains unavailable. |
| Frontier project overall | PARTIALLY VERIFIED | Broader MIDAS regression, live science, production recovery, and deployment remain open. |

## Persist duplicate-key source failures — 2026-10-28 11:04 UTC

Test commit `d44bab0` extends the duplicate-key regression through the API,
append-only store, and evidence endpoint. A mock source response with repeated
`id` fields returns HTTP 502 and `DUPLICATE_JSON_KEY`; its exact raw body and
error code are retrievable through the hash-verified `source_failure`
observation, and no normalized market row is created. No live source was used.

The focused API regression passed **1/1**. Full `tests/frontier` passed
**404/404** in 29.66 seconds (31.12 seconds wall time) using
`/dev/shm/midas-frontier-json-storage-final-20261028T1103Z`. Peak RSS was
**378,492 KiB**, process swaps **0**, filesystem input **0**, output 360
blocks. Ruff, format, strict mypy for six changed production modules, and
`git diff --check` passed. One existing Starlette/httpx deprecation warning
remains.

At `11:03:02Z`, memory and I/O PSI avg10 were 0%, about 10 GiB was available,
and host swap was already 3.5/4 GiB used. At `11:03:37Z`, memory PSI was 0%,
I/O PSI was 0.03% some / 0% full, about 10 GiB remained available, and the
test process used no swaps. No live source, protected capture, production
service, or Arena job was used. Frontier remains **PARTIALLY VERIFIED**.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Duplicate-key source failure provenance | COMPLETE AND VERIFIED | Classified raw response persists and is available by hash-verified observation ID. |
| Full Frontier Python suite | COMPLETE AND VERIFIED | 404/404 pass on the exact test commit; one existing deprecation warning remains. |
| Live cross-venue matching and economics | BLOCKED | Authorized genuine multi-venue evidence remains unavailable. |
| Frontier project overall | PARTIALLY VERIFIED | Broader MIDAS regression, live science, production recovery, and deployment remain open. |

## Pin implication acceptance in economic model identity — 2026-10-28 11:02 UTC

Code commit `ff522e9` advances `ECONOMIC_MODEL_VERSION` from
`frontier-economic-verifiers-15` to `frontier-economic-verifiers-16` to bind
logical-implication verifier v3 acceptance into candidate and replay
identities. Its new regression supplies a prior v2 implication edge and
confirms replay leaves it `INCOMPLETE_EVIDENCE` with no position until it is
re-reviewed. The stored edge remains readable and unchanged.

`tests/frontier/test_logical_implication_economics.py` passed **7/7**. Full
`tests/frontier` passed **404/404** in 29.74 seconds (31.22 seconds wall time)
using `/dev/shm/midas-frontier-final-review-20261028T1101Z`. Peak RSS was
**385,644 KiB**, process swaps **0**, filesystem input **0**, and output 1,176
blocks. Ruff, format, strict mypy across six changed production modules, and
`git diff --check` passed. One existing Starlette/httpx deprecation warning
remains.

At `11:01:11Z`, memory and I/O PSI avg10 were 0%, about 10 GiB was available,
and host swap was already 3.5/4 GiB used. At `11:01:46Z`, memory PSI remained
0%, I/O PSI was 0.01% some / 0% full, about 10 GiB was available, and the test
process reported no swaps. No live source, protected capture, production
service, or Arena job was used. Frontier remains **PARTIALLY VERIFIED**.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Logical implication evidence migration | COMPLETE AND VERIFIED | Economic model v16 requires verifier v3; v2 evidence cannot generate a new eligible position. |
| Full Frontier Python suite | COMPLETE AND VERIFIED | 404/404 pass on the exact code commit; one existing deprecation warning remains. |
| Live cross-venue matching and economics | BLOCKED | Authorized genuine multi-venue evidence remains unavailable. |
| Frontier project overall | PARTIALLY VERIFIED | Broader MIDAS regression, live science, production recovery, and deployment remain open. |

## Replay identity and source JSON ambiguity — 2026-10-28 10:59 UTC

Code commit `63c2d74` rejects repeated relationship IDs in deterministic
replay. A controlled fixture had previously produced two candidate rows with
the same candidate ID when the same relationship was supplied twice. The
replay boundary now fails before generating or auditing candidates.

Code commit `0dbea9c` makes the bounded HTTP JSON parser reject duplicate
object keys at any nesting depth with `DUPLICATE_JSON_KEY`. The error retains
the bounded raw response bytes and is not retried. A `MockTransport` fixture
confirmed Python's prior decoder silently kept the last duplicate field value;
no public source was queried. Focused replay and JSON regressions passed
**1/1** and **2/2**. Full `tests/frontier` passed **403/403** in 29.47 seconds
(30.92 seconds wall time), using
`/dev/shm/midas-frontier-duplicate-inputs-20261028T1058Z`. Peak RSS was
**376,780 KiB**, process swaps **0**, filesystem input **0**, and output 376
blocks. Ruff, format, strict mypy for changed production modules, and
`git diff --check` passed. One existing Starlette/httpx deprecation warning
remains.

At `10:58:31Z`, memory and I/O PSI avg10 were 0%, about 10 GiB was available,
and host swap was already 3.5/4 GiB used. At `10:59:07Z`, PSI remained 0%,
about 10 GiB was available, and the test process reported zero swaps. No live
source, protected capture, production service, or Arena job was used. Frontier
remains **PARTIALLY VERIFIED**.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Replay relationship identity | COMPLETE AND VERIFIED | Duplicate relationship IDs now fail before candidate generation. |
| Public JSON parsing | COMPLETE AND VERIFIED | Duplicate object keys at any depth are rejected with raw bounded evidence retained. |
| Full Frontier Python suite | COMPLETE AND VERIFIED | 403/403 pass on the exact code tree; one existing deprecation warning remains. |
| Live cross-venue matching and economics | BLOCKED | Authorized genuine multi-venue evidence remains unavailable. |
| Frontier project overall | PARTIALLY VERIFIED | Broader MIDAS regression, live science, production recovery, and deployment remain open. |

## Logical implication rejects copied malformed markets — 2026-10-28 10:56 UTC

Code commit `3097082` closes a remaining model-copy validation gap. A
controlled read-only reproduction showed `verify_logical_implication` could
return VERIFIED for a market whose copied payoff state list or native
instrument IDs contained duplicates. Independent audit v15 already returned
incomplete for such candidate inputs, but the relationship graph should not
have assigned verified status. Logical implication verifier v3 checks unique
payoff states, native instrument identities, and outcome identities. The
independent audit is v16 and only accepts current v3 evidence. Old v2 records
remain readable but need re-review to support a new audited candidate.

The focused implication and relationship suites passed **70/70**. Full
`tests/frontier` passed **400/400** in 29.65 seconds (31.11 seconds wall time)
using `/dev/shm/midas-frontier-logical-bypass-20261028T1055Z`. Peak RSS was
**378,052 KiB**, process swaps **0**, filesystem input **0**, output 384
blocks. Ruff, format, strict mypy for three production modules, and
`git diff --check` passed. One existing Starlette/httpx deprecation warning
remains.

At `10:55:13Z`, memory PSI avg10 was 0%, I/O PSI avg10 was 0.01%, about 10 GiB
was available, and host swap was already 3.5/4 GiB used. At `10:55:57Z`, both
PSI readings were 0%, about 10 GiB was available, and the test process used no
swaps. No live source, protected capture, production service, or Arena job was
used. Frontier remains **PARTIALLY VERIFIED**.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Malformed relationship input rejection | COMPLETE AND VERIFIED | Same-payoff v6 and logical implication v3 reject duplicate payoff states and instrument identities; independent audit v16 requires current logical evidence. |
| Full Frontier Python suite | COMPLETE AND VERIFIED | 400/400 pass on the exact code commit; one existing deprecation warning remains. |
| Semantic assertion authenticity | PARTIALLY VERIFIED | Reviewer and assertion remain self-attributed. |
| Live cross-venue matching and economics | BLOCKED | Authorized genuine multi-venue evidence remains unavailable. |
| Frontier project overall | PARTIALLY VERIFIED | Broader MIDAS regression, live science, production recovery, and deployment remain open. |

## Reject copied malformed payoff models — 2026-10-28 10:52 UTC

Code commit `3dc3721` closes a fail-open path found with direct Pydantic
`model_copy(update=...)`: in-memory objects could carry duplicate payoff rows
or identities past model field validation. Same-payoff verifier v6 rejects
duplicate state IDs, native instrument IDs, missing/duplicate outcome IDs,
and duplicate payout rows. Independent audit v15 independently checks payoff
state and native instrument uniqueness and scans every instrument for
duplicate payout rows, including legs not selected in the candidate. Its
cross-venue path also requires unique outcome identities. Existing v5 evidence
is retained but no longer validates new audits without a current review.

Four verifier cases and one independent-audit case reproduce the issue. The
focused relationship/economics module passed **63/63**; full
`tests/frontier` passed **399/399** in 29.59 seconds (31.07 seconds wall time)
using `/dev/shm/midas-frontier-malformed-model-20261028T1052Z`. Peak RSS was
**379,224 KiB**, process swaps **0**, filesystem input **0**, and output 384
blocks. Ruff, format, strict mypy for three production modules, and
`git diff --check` passed. One existing Starlette/httpx deprecation warning
remains.

At `10:51:36Z`, memory and I/O PSI avg10 were 0% and about 10 GiB was
available; host swap was already 3.5/4 GiB used. At `10:52:24Z`, PSI remained
0%, availability was about 10 GiB, and the test process reported zero swaps.
No live source, protected capture, production service, or Arena job was used.
Frontier remains **PARTIALLY VERIFIED**. Continue with bounded offline audits
and preserve the separate live-source, broader-regression, and deployment
gates.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Copied malformed payoff rejection | COMPLETE AND VERIFIED | Verifier v6 and audit v15 reject duplicate identities and payout rows, including an unselected instrument. |
| Full Frontier Python suite | COMPLETE AND VERIFIED | 399/399 pass on the exact code commit; one existing deprecation warning remains. |
| Semantic assertion authenticity | PARTIALLY VERIFIED | Reviewer and assertion remain self-attributed; no assertion truth proof is added. |
| Live cross-venue matching and economics | BLOCKED | Genuine authorized multi-venue evidence remains unavailable. |
| Frontier project overall | PARTIALLY VERIFIED | Broader MIDAS regression, live science, production recovery, and deployment remain open. |

## Same-payoff evidence and replay cutoff — 2026-10-28 10:46 UTC

Code commit `7ebe56a` closes a replay-provenance gap. `verify_same_payoff` now
requires distinct pinned market observation IDs for both inputs, between two
and ten unique nonempty evidence IDs, and an assertion time no earlier than
either source record. Verifier version advances to
`frontier-equivalence-verifier-5`.

The independent audit now advances to
`frontier-independent-economic-audit-14` and accepts exactly one current
same-payoff attestation only when it cites both pinned markets and was created
by the candidate replay cutoff. Reproductions showed that a review created one
second after the historical replay cutoff had previously been accepted by the
cross-venue audit. It is now classified `INCOMPLETE_EVIDENCE`. Missing market
evidence, shared observation identity, and a prior verifier version also fail
closed. Older v4 records remain readable and append-only; they need a new
review before they can validate a new audited replay. Reviewer identity and
external assertion truth remain unauthenticated.

Four new verifier/audit regressions accompany the change. The full
`tests/frontier` suite passes **394/394** in 29.62 seconds (31.09 seconds
process wall time) using `/dev/shm/midas-frontier-rel-audit-verified-20261028T1048Z`.
Peak RSS was **378,716 KiB**, swaps **0**, filesystem input **0**, and output
368 blocks. One existing Starlette/httpx `TestClient` deprecation warning
remains. Ruff check/format, strict mypy for the three changed production
modules, and `git diff --check` pass.

The pre-run sample had memory PSI avg10 **0%**, I/O PSI avg10 **0.06% some /
0.03% full**, and about **10.8 GiB** available. After the run, at
`10:45:46Z`, memory and I/O PSI avg10 were **0%**, about **10.9 GiB** remained
available, and no process swaps were reported. No live source, held capture,
production service, protected store, or Arena job was used. Frontier remains
**PARTIALLY VERIFIED**; no live cross-venue equivalence or economic opportunity
is claimed.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Same-payoff evidence binding | COMPLETE AND VERIFIED | Verifier v5 pins both market observations and rejects predating assertions; audit v14 rejects attestations after replay cutoff and older evidence versions. |
| Full Frontier Python suite | COMPLETE AND VERIFIED | 394/394 tests pass on the exact committed implementation; one existing deprecation warning remains. |
| Semantic assertion authenticity | PARTIALLY VERIFIED | Assertion and reviewer remain self-attributed; no source authenticity or truth proof is added. |
| Live cross-venue matching and economics | BLOCKED | Source-use holds and unavailable authorized evidence remain. |
| Frontier project overall | PARTIALLY VERIFIED | Broader MIDAS regression, live science, production recovery, endurance, and deployment remain open. |

## Verified payoff row uniqueness — 2026-10-28 10:35 UTC

Reproduced a canonical-model defect using a controlled verified binary fixture.
The Yes instrument contained payout rows `yes=1`, `yes=0`, `no=0`; validation
accepted it because the state-ID set still covered `{yes, no}`. A downstream
state map kept the last `yes` amount, so row order could change the payoff used
by later calculations.

Commit `f591185` rejects duplicate payout state IDs in `MarketInstrument` and
requires each state exactly once for every outcome in `FrontierMarket` with a
verified payoff. New tests cover identical duplicates, contradictory amounts,
and a prebuilt model instance. The focused test passed **3/3**; the full
`tests/frontier` suite passed **390/390** in 29.51 seconds with temporary state
at `/dev/shm/midas-frontier-payoff-regression-20261028T1033Z`. Strict mypy for
`models.py`, Ruff check/format, and `git diff --check` passed. Independent binary,
multi-outcome, payoff-basket, and implication audit paths also check payout-row
uniqueness. The real captured Polymarket market still lacks verified payoff
evidence; this model fix does not create live payoff evidence.

At `10:34:45Z`, memory PSI avg10 was 0% and I/O PSI avg10 was 0.04% some / 0%
full. No source request or production service was used. Frontier remains
**PARTIALLY VERIFIED**.

## Fee rounding and provenance review — 2026-10-28 10:30 UTC

Reviewed the bounded Kalshi fee estimate and its independent calculation. The
candidate schedule remains `ESTIMATE`, binds event and series evidence, and
keeps direct-member and non-direct-member precision cases separate because
account balance precision is not available from public metadata. The fee
rounding test uses source-rule fixtures; it does not establish that the rule
applies to a particular account or that current live source use is permitted.

`tests/frontier/test_kalshi_fee_sensitivity.py` passed **21/21** in 0.52
seconds using `/dev/shm/midas-frontier-fees-20261028T1030Z`; property-based
cases compare candidate fees to the independent audit and rounding scenarios.
No source request or code change was made. At `10:29:58Z`, memory PSI avg10
was 0% and I/O PSI avg10 was 0.02% some / 0% full. Account-specific fees,
source authorization, and verified payoff evidence remain unresolved.
Frontier remains **PARTIALLY VERIFIED**.

## Offline FX and venue-capital invariant review — 2026-10-28 10:28 UTC

Reviewed `packages/midas/frontier/fx.py` and `capital.py` without changing
source or captured data. FX assumptions pin the orientation as target
settlement-asset units per one funding unit; balances stay isolated by venue;
conversion fees and adjusted terminal-state P&L are independently recomputed
with exact rational inputs. Capital carry uses the maximum verified settlement
time among a venue's candidate markets, then adds an explicit user-entered
post-settlement delay. It does not pool collateral or assert settlement or
conversion availability.

Focused tests `tests/frontier/test_fx_sensitivity.py` and
`tests/frontier/test_capital_carry.py` passed **45/45** in 0.54 seconds, with
temporary files at `/dev/shm/midas-frontier-fx-capital-20261028T1027Z`. No
defect requiring a patch was found. At `10:28:32Z`, memory and I/O PSI avg10
were both 0%. No live venue rates or balances were used. Frontier remains
**PARTIALLY VERIFIED**. Continue with offline model review and targeted
adversarial tests; recheck PSI before broad tests, builds, or profiling.

## Observation ID provenance and current frontend verification — 2026-10-28 10:26 UTC

Commit `be31236` adds the full `observation_id` to the immutable-response panel;
its UI regression test asserts the value is displayed. After that change, the
entire frontend suite passed **47/47**, `pnpm typecheck` passed, scoped ESLint
and Prettier passed, and `pnpm build` passed. The production build retains the
existing Vite warning for the **544.51 kB** Chart/ECharts chunk; the Frontier
chunk is 182.82 kB. The one-line provenance change does not address that size.

A bounded Chromium check ran against a byte-identical copy of the captured
Polymarket market store at
`/tmp/midas-frontier-live-ui-id-20261028T1026Z/`. It rendered market `2589810`,
its one-sided book, and the full observation ID
`4bb731fd70467c6e8f4ebf33c994243ecb2a02f2701d8ba4e493aae729b0a6b5`; the saved
evidence GET returned HTTP 200. It made no external request or source operation.
The demo API reported `live_execution: false`, all source probes were disabled,
and both local listeners were stopped. The original capture's market database,
collection journal, and manifest SHA-256 values remain
`e9efca9b1658a29cf768222883f9eda0d466e011622b36b0e38efecd846a2052`,
`8b21af2bae0af48a66d52e76aeb228606a530ffc1e83725ab0d7c808cfa0773d`, and
`2e1574b5a42499ba8efe3ac9033de9e6c4e1a3a1a6d381955ce57e9815938e79`.
Screenshot: `/dev/shm/frontier-live-capture-ui-observation-id-20261028.png`.

At `10:26:49Z`, memory PSI avg10 was 0% and I/O PSI avg10 was 0.02% some/full.
No broad MIDAS suite, long-duration collection, production transition, or
cross-venue probe was started. Live cross-venue equivalence remains blocked by
source-use review; the full MIDAS suite still has an incompatible/missing
Reality recovery dependency. Frontier remains **PARTIALLY VERIFIED**. Next
safe work is offline review of payoff, fee, FX, and venue-separated capital
invariants, with a fresh resource admission sample before broader tests.

## Bounded captured-data UI verification — 2026-10-28 10:22 UTC

At `10:21Z`, a headless Chromium smoke opened the Frontier workspace through
the isolated local Vite and demo API processes. The Exchange Explorer showed
the genuine captured Polymarket market `2589810`; the book view showed the
recorded empty bid side. Expanding “Inspect immutable source response” caused
the saved observation route for book observation
`4bb731fd70467c6e8f4ebf33c994243ecb2a02f2701d8ba4e493aae729b0a6b5` to return
HTTP 200, and the evidence panel rendered its timing and row-hash details. The
browser recorded no page errors, external requests, or source-probe/collection
POSTs. Screenshot: `/dev/shm/frontier-live-capture-ui-20261028.png`.

The temporary API and Vite servers were stopped; no listeners remained on
ports 18017 or 15174. The captured market store, collection journal, and
`capture-manifest.json` hashes still match the preserved evidence. At
`10:22:00Z`, memory and I/O PSI avg10 were both 0%. This short browser smoke
does not establish deployment readiness or sustained resource behavior.
Frontier remains **PARTIALLY VERIFIED**.

## Current resource admission and additional venue screen — 2026-10-28 10:17 UTC

The current code/test tree includes `429f690`; `7651b81`, `2c8038d`, `6da77a1`,
and `95b00bc` are documentation-only commits. Official Deribit API,
membership-terms, and restricted-jurisdiction documents were screened; the
public derivatives could provide context but data use remains held pending
written approval. No Deribit request, adapter, or fixture was created. Details
are in `ADDITIONAL_VENUE_SCREEN_2026-10-28.md`.

The market-store, collector-journal, and manifest hashes still match the
preserved Polymarket capture. At `10:17:35Z`, memory PSI avg10 was 9.69% some /
6.56% full and I/O PSI avg10 was 0%. The subsequent brief browser smoke was
admitted after a fresh sample below 1%; see the newer checkpoint above. The
latest requirement-by-requirement matrix is at the top of
`FRONTIER_ENGINEERING_REPORT.md`. Frontier remains
**PARTIALLY VERIFIED**.

## Full Frontier regression after capture isolation — 2026-10-28 09:02 UTC

After commit `429f690` added the test I/O guard for the separate public
Polymarket capture root, the complete `tests/frontier` suite passed **387/387**
in one process (29.38 seconds pytest time). Its tmpfs directory was
`/dev/shm/midas-frontier-regression-20261028T0901Z`. Peak RSS, swaps, and
filesystem input were not measured on this run. The existing
Starlette/httpx `TestClient` deprecation warning remains. Tests used fixtures
and temporary state; no source, production service, protected store, or Arena
job was accessed.

PSI samples stayed below the documented 1% avg10 gate through `09:01:26Z`.
Memory PSI later reached 54.19% some / 48.45% full at `09:02:39Z` for an unknown
host cause. At `09:03:33Z`, memory avg10 was 0.93% some / 0.79% full and I/O
avg10 was 0.79% some / 0.75% full. No follow-up resource-bearing operation has
started. Frontier remains **PARTIALLY VERIFIED**.

## Live API read of preserved Polymarket evidence — 2026-10-28 09:06 UTC

Started and stopped the full API on loopback in demo mode, with writable paper,
recording, Laboratory, Arena, and Reality roots isolated beneath
`/tmp/midas-frontier-live-ui-20261028-0905/`. The Frontier store was the
preserved live Polymarket capture; every venue probe flag was explicitly false.
The API's `/api/frontier/markets` and `/api/frontier/books` GETs each returned
one saved record with observation IDs
`530a6f50dd9826fa200a2dc7fe8a60de3d59b0b465297bd5bb9c7c6f4274ec44` and
`4bb731fd70467c6e8f4ebf33c994243ecb2a02f2701d8ba4e493aae729b0a6b5`, and the
recorded-only disclosure. Post-run hashes of the market database, collection
journal, and manifest match the capture report. API health identified demo mode
and `live_execution: false`. No source request or production service was used.

Vite was started and stopped against this local API, but the browser was not
launched. I/O PSI avg10 was 0.99% some/full at `09:05:51Z`, then 1.35%
some/full at `09:06:50Z`; no cause is attributed. A browser rendering check is
pending a fresh resource sample below the 1% gate. Frontier remains
**PARTIALLY VERIFIED**.

## Bounded live Polymarket adapter evidence and fixture isolation — 2026-10-28 08:57 UTC

The Polymarket adapter was exercised against the public Gamma and CLOB APIs
under the source-use review recorded in
[`SOURCE_DATA_TERMS_REVIEW_2026-10-27.md`](SOURCE_DATA_TERMS_REVIEW_2026-10-27.md).
The official [Polymarket Institute research data guide](https://institute.polymarket.com/data)
describes the public APIs for research. One finite collector run used a limit
of one market, no book in that run, 5-second timeout, 262,144-byte response
bound, and zero retries. It made exactly one Gamma HTTPS GET and completed.
A second explicit read-only adapter call made exactly one CLOB HTTPS GET for
the Yes outcome's public book. No account or order functionality was used.

The isolated evidence root is
`data/frontier-public-probes/polymarket-bounded-20261028T0852-r2Z/`; it contains
the run journal, append-only SQLite evidence store, and `capture-manifest.json`
(SHA256 `2e1574b5a42499ba8efe3ac9033de9e6c4e1a3a1a6d381955ce57e9815938e79`).
At `08:57Z`, the `frontier.sqlite3` and `frontier-collection.sqlite3` files
hashed to `e9efca9b1658a29cf768222883f9eda0d466e011622b36b0e38efecd846a2052`
and `8b21af2bae0af48a66d52e76aeb228606a530ffc1e83725ab0d7c808cfa0773d`.
The completed collector run ID is
`e8d1373f-7df1-4ac4-8d30-8f4a50b57858`. The raw and normalized listing row
and separate book row were re-read through `FrontierStore`, their stored
identities and row hashes were validated, and `MarketBatch`, `FrontierMarket`,
`BookSnapshot`, and `RawObservation` were reparsed. The listing contains one
open binary market (`2589810`, event `606422`) with Yes/No instruments. Its
payoff and resolution remain unverified. The sampled Yes book has five asks,
no bids, and a best ask of `0.995`. The source timestamp
`08:52:33.893Z` precedes local receipt `08:53:07.296333Z` by 33,403.333 ms by
recorded wall clocks; clock synchronization, source freshness, simultaneity,
and executability are not established. This is single-venue observation
evidence only, with no candidate or cross-venue relationship claim.

The read-only Frontier API was then pointed at this capture store in-process.
`GET /api/frontier/markets?venue=polymarket&limit=5` and
`GET /api/frontier/books?venue=polymarket&limit=5` each returned HTTP 200 with
one item, the matching native market ID, exact observation IDs, and the
recorded-only source-state disclosure. Probe flags were disabled in that API
registry; these reads made no source request or store mutation.

To preserve strict separation of source observations and synthetic fixtures,
the Python test I/O guard now protects both `data/frontier/live-probes` and
`data/frontier-public-probes` (code commit `429f690`). The static test-source scan and runtime tests
for both roots, including symlink, `..`, and `dir_fd` cases, pass **3/3**.
Ruff, Ruff formatting, and `git diff --check` pass. The full Frontier suite
was not rerun after this isolated guard change; the previous exact-tree result
was 386/386. At `2026-10-28T08:55:21Z`, memory PSI avg10 was 0%; I/O PSI avg10
was 0.71% some / 0.58% full during the focused check. At `08:57:53Z`, memory
PSI avg10 was **50.11% some / 43.78% full** and I/O PSI avg10 was **1.09% some
/ 0.80% full**. No cause is attributed; further resource-bearing checks wait
for a new sample below the documented gate. No production service, protected
store, or other venue was touched. Overall Frontier remains **PARTIALLY
VERIFIED**.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Polymarket Gamma listing adapter | PARTIALLY VERIFIED | One bounded public GET produced a normalized, persisted market and a validated raw/row lineage; a local API read returned it with its observation ID. This is a single response, not broad live conformance. |
| Polymarket CLOB book adapter | PARTIALLY VERIFIED | One genuine book response was captured and returned through the local API; the only displayed side was five asks and clock synchronization remains unverified. |
| Live cross-venue relationship/economics | BLOCKED | Other venue source-use holds remain; no equivalence or candidate is claimed. |
| Test/source-data separation | COMPLETE AND VERIFIED | The test path guard protects both capture roots; 3/3 focused tests pass. |
| Frontier project overall | PARTIALLY VERIFIED | Full MIDAS regression, source permissions for other venues, production recovery, and deployment remain open. |

## Collection config, FX integrity, and timeline time evidence — 2026-10-28 08:47 UTC

Commits `668a243`, `006fa38`, and `5fd3158` close three bounded research gaps.
`668a243` adds allowlisted config tags to the finite collection run spec so
Kraken pair configuration and Coinbase product/terms acknowledgment survive
journal JSON round-trips. Resume fails before adapter work when any pinned
setting differs. Legacy schema-v1 base configs remain readable and unknown tags
are rejected. `006fa38` enforces agreement among a verified funding conversion
fee, its independent audit total, and each post-fee terminal P&L state—even if
the result hash is recomputed. `5fd3158` adds a timeline fixture with exchange
time before local receipt; the quote becomes available only upon receipt, and
the skew remains visible to timing audit state.

The full Python suite passed **386/386** after these changes. To reduce I/O, it
used `/dev/shm/midas-frontier-pytest-20261028-0846`: **29.38s** pytest time,
**30.82s** wall, **378,704 KiB** maximum RSS, zero swaps, and zero filesystem
input. The known Starlette/httpx TestClient deprecation warning remains. After
`7f7cd6d` formatting/type cleanup, focused verification was rerun:

```bash
PYTHONPATH=packages:. /home/charlie/midas/.venv/bin/python -m pytest -q \
  tests/frontier/test_collection.py tests/frontier/test_collection_api.py \
  tests/frontier/test_fx_sensitivity.py tests/frontier/test_timeline.py \
  --basetemp=/dev/shm/midas-frontier-focused-20261028-0847
# 57 passed in 3.44s; 97,480 KiB maximum RSS; zero swaps and filesystem input
```

Strict mypy passes for `collection.py` and `fx.py`; Ruff check and format pass
for the five changed Python files. At the full-run preflight
`2026-10-28T08:46:01Z`, memory PSI avg10 was 0%, I/O PSI was 0.82% some /
0.74% full, and no shared Arena admission lock holder was present. After the
full run, PSI remained below 1%; a later host sample at
`2026-10-28T08:47:41Z` showed memory PSI avg10 **49.58% some / 45.01% full**.
No cause is attributed and no more broad workload was started. No source,
held capture, production service, or protected store was used.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Collection config survives restart | COMPLETE AND VERIFIED | 34 collection/API tests plus full 386-test suite; mismatched source settings reject before adapter calls. |
| FX result integrity | COMPLETE AND VERIFIED | 18 FX tests plus full suite; rehashed arithmetic contradictions fail model validation. |
| Timeline receipt-time gating | COMPLETE AND VERIFIED | Focused timing case and full suite; source-time skew remains unverified in economic timing state. |
| Frontier Python regression | COMPLETE AND VERIFIED | 386/386 after logic changes; 57 affected cases passed on final formatted tree. |
| Frontier project overall | PARTIALLY VERIFIED | Live source permission, broader MIDAS regression, production recovery, and deployment remain open. |

## Seeded Frontier/Arena browser integration after chart changes — 2026-10-28 08:37 UTC

After commits `6c13b47` and `c04f699`, the opt-in seeded browser suite passes
**2/2**. It traverses saved Frontier history pages and deterministic replay
through the local API, then loads a fixture-only Arena discovery artifact from
Arena storage into Laboratory. The seeder created 21 fixture captures and one
fixture job under the isolated `/tmp/midas-browser-*` root. No exchange
request, production service, or protected store was used.

```bash
cd apps/web
MIDAS_SEED_FRONTIER_E2E=1 ./node_modules/.bin/playwright test e2e/frontier.seeded.spec.ts
# 2 passed in 8.0s using local demo services and disposable state
```

After the run, at `2026-10-28T08:36:51Z`, memory PSI avg10 was 0%, I/O PSI
avg10 was 0.62% some / 0.54% full, and about 10 GiB was available. The
temporary test servers had stopped. This complements the default 17-pass,
2-seeded-skip browser run; it is fixture integration evidence, not live-market
validation.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Seeded Frontier history/replay and Arena-to-Laboratory flow | COMPLETE AND VERIFIED | Two browser cases pass through disposable local API/storage; all market records are explicit fixtures. |
| Live cross-venue validation | BLOCKED | Existing source-use holds remain; fixture integration is not live-source evidence. |
| Frontier project overall | PARTIALLY VERIFIED | Full MIDAS regression, production recovery, source permission, and deployment remain open. |

## Full browser regression after chart lifecycle update — 2026-10-28 08:34 UTC

After commits `6c13b47` and `c04f699`, the default Playwright browser suite
passes **17/17 executed tests**, with its two seeded-only cases skipped as
expected. It was run with one worker against the configured temporary root,
disposable local demo API, and Vite server. The tests covered deferred-load
network timing, Mission Control chart rendering, Arena, Reality, Frontier,
Laboratory, Readiness, Paper, and Veritas flows. No source probe, production
service, or protected store was used; no test server remained listening.

The complete web unit suite is **47/47**; full-project ESLint and Prettier,
TypeScript, and the production build pass. The latest build retains the 544.51
kB minified Chart chunk (186.79 kB gzip); this work defers its request until
needed and reuses the mounted instance without reducing total bundle size.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Full default browser suite at latest chart code | COMPLETE AND VERIFIED | 17 tests pass; two opt-in seeded cases skip as expected. |
| Full frontend unit suite | COMPLETE AND VERIFIED | 47 tests pass across nine files. |
| Frontier project overall | PARTIALLY VERIFIED | Live source, full MIDAS regression, production recovery, and deployment remain open. |

## Deferred chart observer fallback — 2026-10-28 08:32 UTC

Test commit `c04f699` covers `DeferredChart` in both environments: the module
load waits for the reserved area to approach the viewport when
`IntersectionObserver` exists, and starts immediately when that browser API is
unavailable. The focused test passes **2/2**; the complete web unit suite passes
**47/47** across nine files. This verifies the existing fallback contract and
adds no runtime behavior.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Deferred chart browser-capability fallback | COMPLETE AND VERIFIED | Focused test and full 47-test web suite pass. |
| Frontier project overall | PARTIALLY VERIFIED | Live source, full MIDAS regression, production recovery, and deployment gates remain open. |

## Chart instance reuse on data refresh — 2026-10-28 08:31 UTC

Code commit `6c13b47` makes the ECharts instance in `Chart.tsx` live for the
mounted component instead of recreating it whenever an option object changes.
Each new option is applied with `notMerge: true`, so removed series and axes do
not remain from the previous option. The resize observer and chart are
disconnected/disposed on unmount.

```bash
cd apps/web
./node_modules/.bin/vitest run
# 46 passed in 9 files
./node_modules/.bin/vitest run src/Chart.test.tsx
# 1 passed after the final lint correction
./node_modules/.bin/playwright test e2e/smoke.spec.ts e2e/deferred-chart.spec.ts
# 2 passed after the chart lifecycle update
npm run build
# TypeScript and Vite passed; 2,230 modules; 368.81 kB entry,
# 182.75 kB Frontier, 544.51 kB Chart / 186.79 kB gzip
./node_modules/.bin/eslint src/Chart.tsx src/Chart.test.tsx
./node_modules/.bin/prettier --check src/Chart.tsx src/Chart.test.tsx
```

The unit test verifies one `init`, successive option updates on the same chart,
and one disposal on unmount. The browser checks exercise real ECharts rendering
through the local demo API and recheck that loading remains deferred. The full
default browser suite at the preceding code checkpoint passed 17 cases with
two seeded-only skips; only the two chart-specific cases were rerun after this
change. At `08:31:18Z`, memory PSI avg10 was 0%, I/O PSI avg10 was 0.35% some /
0.02% full, and about 10 GiB was available. No exchange request or protected
service/store was used.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| ECharts option refresh lifecycle | COMPLETE AND VERIFIED | Unit test proves one instance is reused and disposed only on unmount; real-browser chart smoke passes. |
| Deferred chart payload | COMPLETE AND VERIFIED | Viewport request-timing browser assertion passes; chunk remains 544.51 kB minified and 186.79 kB gzip. |
| Frontier project overall | PARTIALLY VERIFIED | Shared UI improvements do not close live source, full MIDAS regression, production recovery, or deployment gates. |

## Viewport-deferred chart loading — 2026-10-28 08:28 UTC

Code commit `c4adac6` adds a shared `DeferredChart` boundary to Mission
Control, Arena, and Reality. It preserves chart space and text status while
using a 120 px `IntersectionObserver` root margin to wait before importing the
Chart/ECharts module. Browsers without the observer API load immediately.

The browser test uses a 390 by 200 px viewport, checks that the first chart is
below it with no Chart module request, then scrolls into view and requires one
module request plus a rendered SVG. It proves that payload loading is deferred;
the minified Chart chunk remains **544.41 kB** (**186.76 kB gzip**) and total
bundle size is not reduced.

```bash
cd apps/web
./node_modules/.bin/vitest run
# 45 passed in 8 files
./node_modules/.bin/playwright test e2e/deferred-chart.spec.ts
# 1 passed
./node_modules/.bin/playwright test
# 17 passed, 2 expected seeded-only skips
npm run build
# TypeScript and Vite passed; 368.81 kB entry, 182.75 kB Frontier,
# 544.41 kB Chart chunk
```

The scoped ESLint and Prettier checks passed. At `08:28:12Z`, memory PSI avg10
was 0%, I/O PSI avg10 was 0.14% some / 0.12% full, and about 10 GiB was
available. Playwright started only isolated loopback demo services and
temporary stores. No live source, production service, or protected store was
used.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Shared deferred chart loading | COMPLETE AND VERIFIED | Unit test, full web suite, production build, and browser network assertion; chunk bytes are unchanged and are transferred only after an observed chart approaches view. |
| Browser regression | COMPLETE AND VERIFIED | 17 default E2E cases pass; two seeded-only cases skip as expected, and their separate seeded run remains previously verified. |
| Frontier project overall | PARTIALLY VERIFIED | This loading improvement does not close live source, full MIDAS regression, production recovery, or deployment gates. |

## Acceptance checkpoint — 2026-10-28 08:23 UTC

The exact current Frontier Python suite passes **379/379** in one process via
the documented tmpfs workflow. It took 29.51 seconds pytest time, peaked at
378,216 KiB RSS, used no swap, and recorded zero filesystem input. The latest
separate frontend checkpoint passed 44/44 unit tests, TypeScript, ESLint,
Prettier, the production build, 16 default browser cases with two expected
seeded-only skips, and two seeded Frontier/Arena cases against disposable local
services and stores.

The full MIDAS repository regression is unverified because this selected tree
does not contain `midas.reality.recovery`, required by
`tests/test_reality_full_scale_validation.py`; another Reality lineage has
different dependencies and no copy or cherry-pick was made. Kalshi, Kraken,
and Coinbase remain held from live probes and research/replay routes. The
attempted held-capture test was denied by the test guard and removed without
accessing or repackaging the capture. No live cross-venue match, economically
eligible opportunity, or realizable profit is claimed. Frontier remains
**PARTIALLY VERIFIED**, research-only, isolated, unmerged, and undeployed.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Full Frontier Python regression | COMPLETE AND VERIFIED | 379/379 in one process on the exact tested code tree; resource details are recorded in the engineering report. |
| Frontier web and browser acceptance | PARTIALLY VERIFIED | Latest unit/build/browser evidence is fixture-backed; no live cross-venue data is displayed as evidence. |
| Full MIDAS repository regression | BLOCKED | Selected checkout lacks `midas.reality.recovery`; a compatibility port needs separate dependency and scope work. |
| Live multi-venue scientific validation | BLOCKED | Source holds and the held-capture test guard remain in force. |
| Frontier project overall | PARTIALLY VERIFIED | Continue source-independent acceptance review; production transition and deployment remain out of scope. |

## Explicit hypothetical replay-outcome disclosure — 2026-10-28 02:57 UTC

Code commit `3af51c0589c9550ff5bbf9333e24a818e75041c0` changes the candidate
detail metrics to “worst modeled gross/net P&L” and places a disclosure beside
terminal outcomes: these hypothetical replay values do not establish fills,
venue access, or realized profit.

```bash
cd apps/web
./node_modules/.bin/vitest run src/Frontier.test.tsx -t "submits bounded Arena replay and discovery comparisons with verified results"
# 1 passed; 7 skipped
./node_modules/.bin/playwright test e2e/frontier.spec.ts -g "saved Arena discovery artifact exposes scoped candidate evidence"
# 1 passed in 5.4s on loopback demo services with an intercepted fixture
npm run build
# TypeScript and Vite passed; 2,228 modules; existing 544.41 kB Chart chunk advisory
```

The browser fixture checks the disclosure in the rendered candidate view. It
does not represent observed market data or an executed opportunity. After the
build, PSI avg10 was **29.83% some / 24.02% full** at `2026-10-28T02:57:42Z`,
with about **9.8 GiB** available and **332 MiB** swap free; defer heavier local
work until another admission sample.

## Discovery worker dispatch and network isolation — 2026-10-28 02:56 UTC

Code commit `9b0b28f89832799fdcc8ff66f117e156d133be7c` adds
`frontier_discovery` to the Arena systemd launcher's network-restricted job
set, so the command allows only AF_UNIX sockets. Its bounded resource error
message now includes discovery alongside replay and timeline. Two fixture
checks exercise the configuration: one stubs only the host admission context
and `systemd-run` to inspect the launch command; the other stages an immutable
input in `tmp_path`, starts a child process with
`python -m midas.arena.jobs`, waits for the actual discovery dispatch, and
verifies the durable result artifact.

```bash
/usr/bin/time -v env PYTHONPATH=packages /home/charlie/midas/.venv/bin/python -m pytest -q tests/arena/test_jobs.py tests/arena/test_frontier_discovery.py
# 21 passed in 36.59s; 193,632 KiB peak RSS; zero swaps or socket messages
```

Ruff and `git diff --check` pass. One existing Starlette/httpx deprecation
warning remains. The launch-command test does not invoke systemd or the host
admission gate; the actual subprocess uses a temporary Arena root and is not
under a production cgroup. The normal systemd launch remains resource-gated.
No live endpoint, shared Arena artifact root, source, protected service, or
production deployment was touched. Project Frontier remains **PARTIALLY
VERIFIED**.

## Saved discovery-candidate evidence in Mission Control — 2026-10-28 02:52 UTC

Code commit `4c40c7f4403d7571ae52849e6c4d10c81fa4d5c1` completes the current
read-only UI step for Arena discovery artifacts. The scope comparison now
opens candidate details from the artifact's replay runs associated with that
scope. Before rendering, the UI matches candidate ID, family, classification,
audit disposition, and worst-case gross/net values to the discovery summary.
The expanded view exposes per-leg venue, native market/instrument/outcome,
native quantity, exact decimal ask/model price/fee, displayed depth, and book
observation ID; settlement identity; terminal payout and gross/net results;
receipt/exchange timing skew; practical eligibility; independent audit checks;
assumptions; and evidence hashes. It renders at most 50 candidates per scope
and reports additional rows. This is inspection of the existing hash-verified
artifact, not a new research calculation or execution path.

Changed files: `apps/web/src/Frontier.tsx`,
`apps/web/src/Frontier.test.tsx`, `apps/web/src/frontier.css`, and
`apps/web/e2e/frontier.spec.ts`.

Reproducible checks on the final UI code:

```bash
cd apps/web
./node_modules/.bin/vitest run src/Frontier.test.tsx -t "submits bounded Arena replay and discovery comparisons with verified results"
# 1 passed; 7 skipped
./node_modules/.bin/vitest run
# 40 passed in 7 files
npm run build
# TypeScript and Vite passed; 2,228 modules; existing 544.41 kB Chart chunk warning
./node_modules/.bin/playwright test e2e/frontier.spec.ts -g "saved Arena discovery artifact exposes scoped candidate evidence"
# 1 passed in 5.2s; isolated loopback demo services and temporary storage
./node_modules/.bin/eslint src/Frontier.tsx src/Frontier.test.tsx e2e/frontier.spec.ts
./node_modules/.bin/prettier --check src/Frontier.tsx src/Frontier.test.tsx src/frontier.css e2e/frontier.spec.ts
```

No Python files changed. No source probe, Arena job submission, protected
service action, deployment, or historical evidence write occurred. The E2E
artifact is a labeled fixture; no supervisor-produced `frontier_discovery`
result has yet been inspected in this browser path. After the bounded E2E, the
`2026-10-28T02:52:22Z` host sample was avg10 PSI **21.85% some / 20.89% full**,
avg60 **4.93% / 4.69%**, about **9.8 GiB** available, and **332 MiB** swap
free. Recheck before any resource-heavy work.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Saved Arena candidate evidence UI | COMPLETE AND VERIFIED | Web unit, TypeScript/build, scoped lint/format, and fixture browser path pass; this does not exercise an Arena supervisor result or live source. |
| Arena discovery job execution | PARTIALLY VERIFIED | Artifact code, API staging, and result inspection are fixture-tested; supervisor completion and resource sustainability remain open. |
| Genuine cross-venue relationship and economic result | DEFERRED | No verified live equivalent relationship or executable synchronized opportunity is established. |
| Project Frontier overall | PARTIALLY VERIFIED | Production, source-use permissions, live matching, and broader operational acceptance remain unresolved. |

**Next safe action:** continue source-independent implementation or documentation;
before any broad suite or benchmark, take a fresh resource/admission sample and
preserve the existing source and production gates.

## Joint-state differential verification and search optimization — 2026-10-28 02:16 UTC

Test commit `29f1a5b` adds a seeded 48-case differential test for candidate
generation and a reproducible max-state benchmark. The differential test
compares the generator against a separate exhaustive oracle over all 15
non-empty subsets of two binary event markets; each case varies exact ask
prices and uses identity or flipped local-state projections. The oracle checks
all three valid constant-payout baskets, candidate ordering, and independent
audit disposition.

Code commit `bc8d073` replaces repeated per-subset payout dictionary creation
with cached per-instrument joint-state vectors, incremental subset payout/cost
vectors, and a market-coverage bit mask. It adds the highest-index entry last
to preserve the prior ascending Decimal accumulation order.

Reproduction and verification:

```bash
env PYTHONPATH=packages /home/charlie/midas/.venv/bin/python -m pytest -q tests/frontier/test_joint_state.py::test_joint_state_search_matches_independent_seeded_subset_oracle
# 1 passed in 0.56s

/usr/bin/time -v env PYTHONPATH=packages /home/charlie/midas/.venv/bin/python -m pytest -q tests/frontier
# 343 passed in 53.88s pytest time / 55.23s process wall; 366,360 KiB peak RSS;
# zero swaps, major faults, or socket messages; one existing deprecation warning

PYTHONPATH=packages:. /usr/bin/time -v /home/charlie/midas/.venv/bin/python tests/frontier/benchmark_joint_state_search.py
# 3 timed runs, 12 instruments, 64 joint states, 4,095 enumerated subsets,
# 3,969 qualifying subsets; one returned candidate; median 0.101767s,
# maximum 0.104521s; 70,576 KiB peak RSS; zero swaps

PYTHONPATH=packages:. /usr/bin/time -v /home/charlie/midas/.venv/bin/python tests/frontier/benchmark_joint_state_search.py --repeats 1 --max-candidates 8
# one sample 0.174308s; 8 candidates; 71,460 KiB peak RSS; zero swaps

MYPYPATH=packages /home/charlie/midas/.venv/bin/mypy --strict --follow-imports=silent packages/midas/frontier/joint_economics.py
# Success: no issues found in 1 source file
```

Before optimization, the same three-run one-candidate benchmark measured a
**5.122457-second median**, **5.147910-second maximum**, and **38,624 KiB peak
RSS**, with no swaps. The optimized median is about **50x lower**, at roughly
**32 MiB additional peak RSS**. A first attempt using five repeats and eight
returned candidates produced no captured measurement at the 30-second tool
boundary; no process remained on follow-up, so that attempt is excluded. Bounded
reruns with fewer output candidates produced the measurements above.

All benchmark payoffs are explicit synthetic fixtures engineered to make
subsets qualify. These results show bounded local computation only; they are
not market workload, source latency, opportunity, or profitability evidence.
At the post-suite sample PSI was `avg10=0.00%`, `avg60=4.36%`, with about 10 GiB
available; swap remained about 3.7 GiB used. The full suite did not swap.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Joint-state candidate generation and independent differential | COMPLETE AND VERIFIED | Full Frontier suite 343/343, 48 seeded exhaustive-oracle cases, and independent candidate audit pass. Randomized fixtures cover two binary markets; they do not establish real event semantics. |
| Bounded 12-instrument / 64-state search cost | COMPLETE AND VERIFIED | Synthetic ceiling benchmark examines 4,095 subsets and returns the requested cap with sub-0.2-second measured latency after vector caching. Peak RSS rises by about 32 MiB; representative source workload and sustained service behavior remain unmeasured. |
| Project Frontier overall | PARTIALLY VERIFIED | Live semantic relationship evidence, source permission, cross-venue funding/settlement feasibility, long-horizon quality, and deployment remain open. |

**Next safe action:** keep the public/source gates unchanged. Continue only with
offline source-independent acceptance unless an allowed source and defensible
cross-venue relationship become available. Recheck host PSI before any larger
test or profiling run.

## Multi-market joint-state replay and browser verification — 2026-10-28 02:03 UTC

Code checkpoint `4bd3b7f2636d5cd8d069fb2e2b2e97188ad68247` adds the bounded
joint-state basket family, canonical asserted-map identity, independent
arithmetic audit, stored-observation API route, and explicit Mission Control
map editor. The path supports two to four selected event markets, two to
sixty-four shared-state rows, twelve total instruments, and 4,095 subsets.
The map is an unauthenticated assertion: arithmetic is independently checked
conditional on it, but its semantics and attainability are not certified.
Native leg quantity units remain distinct; practical eligibility stays false.
Follow-up test commit `b0f38c2` adds a fixture-only Playwright flow for the
explicit mapping editor.

Verification commands and results on the code checkpoint:

```bash
PYTHONPATH=packages /home/charlie/midas/.venv/bin/python -m pytest -q tests/frontier/test_joint_state.py tests/frontier/test_relationships_economics_replay.py tests/frontier/test_capital_carry.py tests/frontier/test_fx_sensitivity.py tests/frontier/test_api.py
# 152 passed; 1 existing Starlette/httpx deprecation warning

/usr/bin/time -v env PYTHONPATH=packages /home/charlie/midas/.venv/bin/python -m pytest -q tests/frontier
# 342 passed in 53.70s pytest time / 55.06s process wall; 368,788 KiB peak RSS;
# zero swaps, major faults, or socket messages; same existing deprecation warning

corepack pnpm --dir apps/web test
# 40 passed

/usr/bin/time -v corepack pnpm --dir apps/web build
# TypeScript + Vite 7.3.7; 2,228 modules; 4.76s Vite / 13.18s process wall;
# 713,040 KiB peak RSS; zero swaps; existing 544.41 kB chart chunk advisory

/usr/bin/time -v corepack pnpm --dir apps/web exec playwright test e2e/frontier.spec.ts --workers=1
# 5 passed in 13.7s test time / 14.52s process wall; 197,060 KiB peak RSS;
# zero swaps; includes explicit mapping submit with fixture-only intercepted data
# loopback demo services and temporary storage only
```

The added browser case selects two fixture event markets, fills every mapping
cell, submits the map, checks that the response supplies the mapping ID, and
asserts that no source probe occurs. The route response is intercepted and is
not evidence of live adapter behavior.

Ruff passed for changed Python files. Scoped strict mypy passed for
`models.py`, `economics.py`, `joint_economics.py`, `independent_audit.py`, and
`replay.py`. A broader mypy invocation produced 14 errors only in imported
pre-existing Veritas/Arena modules; none were reported in the changed Frontier
API router. No live source, protected service, Reality recording, production
store, or deployment was involved. Memory PSI before the final regression was
`avg10=0.00%`, `avg60=1.70%`, with about 9 GiB available; after the suite it was
`avg10=0.00%`, `avg60=0.64%`, with about 10 GiB available. Swap remained
approximately 3.7 GiB used. Following Playwright, PSI rose to
`avg10=45.36%`, `avg60=26.91%`, with about 9.7 GiB available; the run itself
did not swap. Further heavier checks should wait for host pressure to subside.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Conditional joint-state search and independent arithmetic | COMPLETE AND VERIFIED | Bounded fixture/API/replay suite and full Frontier regression pass. Semantic truth of the supplied shared-state map is not verified. |
| Current Mission Control build and regression | COMPLETE AND VERIFIED | Web 40/40, production TypeScript/Vite build, and Frontier Playwright 5/5 pass. The browser suite includes explicit mapping submission and no-probe behavior using fixture data; it does not establish semantic map correctness. |
| Genuine live cross-venue relationship and source validation | BLOCKED | Current terms holds and lack of a verified common event remain. Do not bypass source restrictions; offline work remains possible. |
| Production deployment and long-duration reliability | DEFERRED | Requires separate readiness/resource/recovery review and authorization; no deployment or long-duration run was performed. |
| Project Frontier overall | PARTIALLY VERIFIED | Multiple sources, bounded relationship research, costs, replay, and UI exist, but live semantic matching, source quality, economic feasibility, and production gates remain open. |

The same documentation checkpoint updates the Frontier architecture and
operations guides, development/API guidance, this ledger, the current-state
addendum, and the engineering report. After committing these docs, record the
documentation commit identity in the handoff output.

**Next safe action:** continue work on source-independent acceptance and
relationship validation. Recheck the source-terms gates before considering any
public observation; this checkpoint made no source request. Recheck host PSI
before further resource-bearing validation.

## Production web build verification — 2026-10-28 01:29 UTC

The current Mission Control frontend passes the full web unit suite
(**40/40**), Frontier browser spec (**4/4**), and production build:

```bash
corepack pnpm --dir apps/web test
corepack pnpm --dir apps/web exec playwright test e2e/frontier.spec.ts --workers=1
corepack pnpm --dir apps/web build
```

The build ran TypeScript and Vite 7.3.7, transformed **2,228 modules**, and
completed in 4.65 seconds (**12.93 seconds wall**). Peak RSS was **647,704
KiB**, with zero swaps, major faults, or socket messages. Vite reports the
existing **544.41 kB** chart-chunk advisory above its 500 kB threshold. The
browser spec uses loopback demo services and a temporary database/workspace.
No live sources or production services were involved.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Current Mission Control frontend verification | COMPLETE AND VERIFIED | Web 40/40, Frontier Playwright 4/4, TypeScript check, and Vite production build pass. The bundle advisory remains. |
| Production deployment | DEFERRED | This is a local build only; separate authorization and production readiness gates remain. |
| Project Frontier overall | PARTIALLY VERIFIED | General multi-market composition, live cross-venue evidence, long-horizon source quality, and deployment remain open. |

**Next safe action:** implement and independently audit a separately versioned,
bounded joint-state representation for multi-market portfolios; preserve
asserted state maps as conditional evidence and pin them into replay records.

## Varied payoff-basket workloads and frontend regression — 2026-10-28 01:27 UTC

Benchmark commit `8f2d22fa7bc37ac806d070403d122d941dc226a8` measures four
controlled payout shapes. Each measurement uses one warm-up and five timed
calls; the harness checks that the generator returns the expected count.

| Fixture | Instruments / states | Enumerated subsets | Qualifying / returned | Median / maximum |
| --- | ---: | ---: | ---: | ---: |
| Single basket | 3 / 3 | 7 | 1 / 1 | 0.000928 / 0.000991 sec |
| Eleven baskets | 12 / 16 | 4,095 | 11 / 11 | 0.091870 / 0.099176 sec |
| No basket | 12 / 16 | 4,095 | 0 / 0 | 0.072525 / 0.074176 sec |
| Dense ceiling | 12 / 16 | 4,095 | 4,095 / 32 | 0.343868 / 0.355242 sec |

The four-case process took **3.37 seconds wall** at **50,640 KiB peak RSS**,
with 99% CPU, zero swaps, zero major faults, and zero socket messages. The
payout vectors are explicitly synthetic. These measurements show this code
path's short local cost, not public-market latency or representative workload
performance.

Current frontend regression after commit `d162594`: the full web unit suite
passed **40/40** in 5.99 seconds wall (**310,652 KiB peak RSS**); isolated
Frontier Playwright passed **4/4** in 12.60 seconds wall (**192,060 KiB peak
RSS**, zero swaps). Playwright used loopback demo services and temporary
SQLite/Arena/Frontier directories. Before the run, memory PSI `avg10` was
0.00%, 10,778,132,480 bytes were available, and swap use was 3,949,416,448
bytes. The user-slice cgroup had no memory high/max setting; the short test
runs did not swap. This does not establish sustained or concurrent capacity.

Reproduction commands:

```bash
PYTHONPATH=packages:. /usr/bin/time -v /home/charlie/midas/.venv/bin/python tests/frontier/benchmark_payoff_basket_search.py
corepack pnpm --dir apps/web test
corepack pnpm --dir apps/web exec playwright test e2e/frontier.spec.ts --workers=1
```

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Varied bounded basket benchmark | COMPLETE AND VERIFIED | Four fixture shapes, expected result counts, five iterations after warm-up, and host resource measurements are reproducible. This is synthetic code-path evidence only. |
| Mission Control unit and browser regression | COMPLETE AND VERIFIED | Full web unit suite 40/40 and Frontier Playwright spec 4/4 pass on the current frontend. The services are local demo instances, not deployed services. |
| General multi-market joint-state composition | DEFERRED | Current cross-market candidates use pairwise mappings. A bounded shared joint-state representation and independent multi-market payoff audit are still required. |
| Project Frontier overall | PARTIALLY VERIFIED | Live source-use holds, genuine cross-venue relationship validation, general multi-market composition, long-horizon source-quality evidence, and deployment remain open. |

**Next safe action:** design and implement a separately versioned, bounded
joint-state input and independent payoff audit for multi-market portfolios.
Keep asserted semantic maps conditional, pin their evidence in replay, and do
not claim cross-market proof from local labels.

## Bounded payoff-basket ceiling benchmark — 2026-10-28 01:22 UTC

Harness commit `447c85a` adds
`tests/frontier/benchmark_payoff_basket_search.py`; follow-up `c1c58ad` makes
its synthetic all-state labels and verification basis explicit. The controlled
16-state, 12-instrument fixture makes all **4,095** non-empty subsets qualify
for a constant positive payout, then requests the maximum of 32 ranked
results. The fixture deliberately maximizes subset enumeration; it is not a
market-like payoff distribution or economic evidence.

Five measured calls after a warm-up returned 32 candidates each, with a
**0.344171 second median** and **0.355593 second maximum**. Including import,
setup, warm-up, and five measured calls, `/usr/bin/time -v` reported **2.37
seconds wall**, **49,792 KiB peak RSS**, 100% CPU, zero swaps, zero socket
messages, and zero major page faults. The standalone harness and Ruff
check/format passed. No exchange, network, store, or production data was used.

Reproduce from the repository root:

```bash
PYTHONPATH=packages:. /usr/bin/time -v /home/charlie/midas/.venv/bin/python tests/frontier/benchmark_payoff_basket_search.py
```

This establishes one short synthetic upper-bound measurement on this host. It
does not establish representative workload behavior, concurrency, sustained
resource use, or production admission.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Maximum-bound payoff-basket enumeration | PARTIALLY VERIFIED | 4,095 qualifying subsets and 32 returned results completed in a 0.344171 second median call; the uniform synthetic payoff fixture is not representative. |
| Project Frontier overall | PARTIALLY VERIFIED | This improves bounded performance evidence but does not close live cross-venue, general multi-market, source-quality, or deployment gaps. |

**Next safe action:** continue offline acceptance against more varied synthetic
market sizes and payoff shapes, keeping these measurements separate from
public-source performance claims.

## Bounded event payoff baskets — 2026-10-28 01:20 UTC

Code commit `d16259422902bc4acd75cb45e0ced6eb8e186904` adds a bounded
same-market candidate family for verified exhaustive multi-outcome contracts
with overlapping or non-one-hot payoffs. It enumerates no more than 4,095
subsets from twelve instruments and accepts only baskets whose nonnegative
verified payout vectors produce the same positive total across all three to
sixteen states. Replay defaults to eight candidate results and caps explicit
requests at 32. It uses common trading units, one venue and settlement
identity, exact displayed asks, quantity-step/depth checks, fees, timing,
slippage, and existing fill sensitivities. Economic/replay versions moved to
14 and the independent audit to 11.

The independent audit reconstructs the selected contract vectors and requires
a constant positive terminal payout before doing separate quote, fee, cost,
and P&L calculations. A controlled three-leg fixture passes deterministic
replay and audit; removing one leg fails the audit, and a market with no
constant-payout subset yields no candidate. The fixture's USD 12.50 gross result
is synthetic test arithmetic only, not an observed or economically meaningful
opportunity. The new search has not been benchmarked on a representative
market set.

### Verification

- Focused relationship/economics/replay tests plus both the one-hot and
  payoff-basket replay API regressions: **51 passed** in 2.00 seconds; one
  existing Starlette/httpx deprecation warning remains.
- Focused Mission Control test passed **1/1**, confirming the new candidate
  family is visible in the candidate detail card. The new API fixture verifies
  replay persistence and candidate listing with no adapter requests.
- Strict mypy passed for `economics.py`, `independent_audit.py`, `models.py`,
  and `replay.py`. Scoped Ruff check/format and `git diff --check` passed.
- The full serial Frontier suite passed **332 tests** in 52.98 seconds pytest
  time / **54.32 seconds wall**; peak RSS was **369,040 KiB**, with zero swaps,
  zero socket messages, zero major faults, and 35% CPU. One existing
  Starlette/httpx deprecation warning remains. The full web/browser suites were
  not rerun. No exchange, held source, protected Reality process, production
  store, or deployment was used.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Bounded within-market payoff-basket discovery and audit | COMPLETE AND VERIFIED | Exact three-leg fixture, deterministic replay, truncated-basket audit rejection, and no-coverage rejection pass. Live source semantics and candidate economics are not established. |
| General multi-market joint-state search | DEFERRED | This family only composes payoff vectors in one verified event state space. Cross-market joint-state inference remains unsupported. |
| Project Frontier overall | PARTIALLY VERIFIED | Live cross-venue validation, source-use holds, broader source-quality evidence, general multi-market search, and deployment remain incomplete. |

**Next safe action:** measure the bounded subset search on representative
synthetic market sets, then continue other offline acceptance work. Keep
current source holds and production boundaries in force.

## Cursor-paginated finite collection history — 2026-10-28 01:07 UTC

Code commit `067b2ce` adds keyset pagination to the read-only finite collection
run catalog. `GET /api/frontier/collection-runs?limit=20` returns a bounded page
and `next_before_run_id`; passing that visible run ID as `before_run_id` fetches
older entries. The journal validates the anchor specification and complete
checkpoint chain, and verifies every returned checkpoint chain before
responding. Page selection uses a read-only SQLite transaction for a consistent
view, scans in 64-row batches, and observes the existing 1,000-run ceiling. Held
venues remain excluded, including while the scan passes over their entries.
Newly appended runs do not shift older pages.

Mission Control's Exchanges view adds shared “Load older runs” and “Newest
runs” controls. It resets to the newest page after a finite capture or resume.
The page stays read-only and makes no source request; it only inspects local
hash-chained checkpoints. A unit fixture exercises an older page after a newer
run is inserted, while a storage regression crosses the 64-row scan boundary
with held Kalshi entries excluded.

### Verification and resource evidence

- API/storage pagination regressions: **2 passed**; four adjacent collection
  lifecycle/integrity route tests also passed. The Frontier Python suite passed
  **330 tests** in 52.85 seconds pytest time / **54.20 seconds wall**. Peak RSS
  was **365,832 KiB**, with zero swaps, zero socket messages, zero major page
  faults, and 35% CPU use. One existing Starlette/httpx deprecation warning
  remains.
- The full web unit suite passed **40/40**; the Frontier Playwright spec passed
  **4/4** against isolated services. TypeScript build, production Vite build,
  scoped ESLint/Prettier, strict mypy for the API and collection journal, Ruff,
  and `git diff --check` passed. Vite continues to report the existing 544.41
  kB chart-chunk advisory.
- No exchange endpoint, held source, protected Reality process, external
  worker, production store, or deployment was used.

Documentation follow-up records the architecture, operations, evidence, and
remaining deployment boundary. Production deployment remains deferred.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Finite collection history pagination | COMPLETE AND VERIFIED | Stable run-ID pages, chain-verified anchors and results, malformed/missing cursor rejection, and held-source skip across bounded batches pass API/storage tests. |
| Exchanges history controls | COMPLETE AND VERIFIED | Older/newest navigation, collection/resume reset, full web unit suite, browser spec, and production build pass. Browser test services use isolated local state. |
| Frontier source-history collection | PARTIALLY VERIFIED | The UI can inspect the retained finite-run catalog, capped at 1,000 runs. It does not add a continuous feed or historical market-data backfill. |
| Project Frontier overall | PARTIALLY VERIFIED | Genuine cross-venue live matching, broader multi-leg search, long-horizon source-quality evidence, and deployment remain incomplete. |

**Next safe action:** continue offline acceptance against the remaining matrix.
Prioritize bounded economic families with independently recomputed payoffs;
retain current source-use holds and deployment boundary.

## Collection API integrity boundary and complete Frontier regression — 2026-10-28 00:55 UTC

Code commit `780575c` adds an API-level corruption test for the collection
journal. The fixture simulates offline disk corruption in a temporary SQLite
file by removing and restoring the append-only update trigger around one
payload-only edit, leaving the recorded checkpoint digest unchanged. Both
collection history and resume return HTTP 409 with the chain-integrity failure;
the adapter receives no requests. The append-only trigger itself remains
present when the API reads the journal.

Together with `4ba723f`, this covers three finite collection API cases:
reconstruction and resume without rediscovery, held-source quarantine before
mutation, and tampered checkpoint rejection before source access.

### Verification and resource evidence

- Focused API collection lifecycle/integrity selection: **3 passed** in 1.81
  seconds. Ruff check/format and `git diff --check` passed.
- Full serial Frontier suite: **328 passed**, one existing Starlette/httpx
  deprecation warning, in 51.45 seconds pytest time / **52.82 seconds wall**.
  `/usr/bin/time -v` measured **367,868 KiB peak RSS**, zero swaps, and zero
  socket messages. CPU use was 35%; major page faults were zero.
- Post-run host sample: memory PSI avg10 **0.01% some / 0.01% full**, about
  **10 GiB available**, and **3.7 GiB swap in use**. This supports the bounded
  serial run only; it does not establish sustained or concurrent production
  capacity.
- All evidence is fixture-backed and local. No exchange, held source,
  protected service, production store, external worker, or deployment was used.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Collection API restart, history, held-source, and corruption handling | COMPLETE AND VERIFIED | Three route-level tests verify durable resume, source quarantine, and hash-chain failure closed with no adapter calls. |
| Full Frontier Python regression | COMPLETE AND VERIFIED | 328 tests pass on the current code revision; sustained, concurrent, UI, browser, and deployment checks are separate evidence. |
| Project Frontier overall | PARTIALLY VERIFIED | Genuine cross-venue relationship validation, live sources behind current holds, broad long-horizon data quality, and deployment remain incomplete. |

**Next safe action:** continue offline acceptance from the mission matrix. Do not
use held sources or infer live opportunity economics from these fixtures.

## HTTP collection recovery across reconstructed API instances — 2026-10-28 00:53 UTC

The collection API regressions now exercise recovery after reconstructing the
API app, adapter registry, adapter instance, and store from the same local
collection journal. A fixture-induced persistence interruption leaves a paused
checkpoint with one pending market capture. The reconstructed API resumes it
from the persisted observation, completes the run, and issues no rediscovery
request. Terminal retries remain idempotent. A separate route-level fixture
confirms a held Kalshi run is hidden from history and that both start and resume
are rejected before adapter calls or journal mutation.

### Verification and resource boundary

- Focused HTTP collection recovery/quarantine tests: **2 passed** in 1.66
  seconds. Ruff check/format and `git diff --check` passed.
- The run uses only fixture adapters and a temporary local store. It does not
  contact an exchange or access protected service data.
- The full Frontier suite was not rerun after adding these tests. At the
  pre-run host sample, memory PSI avg10 was **43.18% some / 39.51% full**, with
  **9.8 GiB available** and **3.7 GiB swap in use**. Defer the broad suite until
  pressure subsides and remeasure admission first.

Code commit `4ba723f` adds the route-level recovery and quarantine tests in
`tests/frontier/test_api.py`. The ledger and engineering-report updates are
documentation-only follow-up changes.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| HTTP collection history, restart recovery, and held-source quarantine | COMPLETE AND VERIFIED | Route-level temporary-store tests cover reconstructed-instance resume without rediscovery, terminal retry, and held-source rejection before mutation. No live capture was performed. |
| Full Frontier regression after these additions | PARTIALLY VERIFIED | The prior 325-test suite predates these two tests; the focused additions pass. Broad rerun is deferred while host memory PSI is high. |
| Live source collection and deployment | DEFERRED | All source collection remains disabled by default; no production deployment or Reality action occurred. |

**Next safe action:** remeasure host pressure before considering the full
Frontier suite; meanwhile continue offline acceptance work and keep held-source
quarantine intact.

## Funding-adjusted terminal-state P&L — 2026-10-28 00:47 UTC

Code commit **`71ee203b033c4bc0f38afce09b5255fe31bcae21`** upgrades the saved-run
virtual funding sensitivity to schema/model version 2. It returns a separate
outcome-level P&L scenario after subtracting the user-assumed conversion fee
from each independently audited terminal state. The input digest binds the
candidate independent-audit identity and P&L, modeled-fee completeness, venue
capital, and user assumptions. A second `Fraction` pass independently
recomputes each conversion charge and adjusted state.

The scenario is verified only if the saved candidate audit and funding audit
verify, candidate P&L matches its audit, every candidate leg has a modeled fee,
and each venue-local virtual balance covers its capital requirement. Incomplete
evidence returns `unavailable`; disagreement returns no adjusted state values.
The candidate's saved P&L, classification, and practical eligibility remain
unchanged. The API reads the exact hash-pinned saved run; it makes no source
request, database write, or execution action. Mission Control displays verified
state values or the specific unavailable/disagreement explanation.

### Verification

- Full Frontier Python suite: **325 passed** in 50.39 seconds pytest time / 51.73
  seconds wall. `/usr/bin/time -v` measured **365,976 KiB peak RSS**, zero
  swaps, and zero socket messages. One existing Starlette/httpx deprecation
  warning remains.
- Focused funding model plus saved-run API tests: **16 passed** in 1.14 seconds.
  The measured command used **82,756 KiB peak RSS**, zero swaps, and zero socket
  messages.
- Web unit suite: **40 passed** across seven files, covering both verified and
  unavailable P&L panel states.
- TypeScript, targeted ESLint and Prettier, Ruff check and format, and strict
  scoped mypy for `packages/midas/frontier/fx.py` passed.
- `playwright test e2e/frontier.spec.ts --workers=1`: **4 passed** in 11.7
  seconds using isolated demo services. Browser funding responses are fixtures;
  the saved-run API is independently fixture-tested.
- Vite production build passed in 4.69 seconds. It emitted the existing
  544.41 kB Chart-chunk advisory.

The first expanded UI unit run found a stale count assertion for `red`; the
verified outcome panel adds one state label. The assertion was updated and all
40 Web tests passed. No exchange endpoint, FX source, account, wallet, protected
Reality process, production store, external worker, or deployment was used.
Fixture economics demonstrate the calculation and do not establish live
convertibility, transfers, executable quotes, or profitability.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Conversion-adjusted terminal-state P&L scenario | COMPLETE AND VERIFIED | Saved-run API, rational recomputation, verified/unavailable UI states, incomplete-fee/balance rejection, candidate-audit mismatch rejection, and invariance checks pass. Assumptions remain hypothetical. |
| Funding-currency workflow and Mission Control | COMPLETE AND VERIFIED | Python/Web regressions, Frontier browser spec, TypeScript, lint, scoped mypy, and production build pass. The browser response is fixture-intercepted. |
| Live FX, conversion, and cross-venue capital access | DEFERRED | No FX observation, account balance, transfer, jurisdiction, custody, collateral, or availability evidence is sourced. |
| Project Frontier overall | PARTIALLY VERIFIED | Other science/source gaps remain. There is no genuine verified cross-venue match and no production deployment. |

**Next safe action:** continue offline work from the full acceptance matrix and
mission report. Keep held sources quarantined and the production transition
separate. A positive fixture result is not an observed opportunity.

## Explicit finite collection API — 2026-10-28 01:38 CET

Code commit **`cf67b2b`** adds an explicit `POST
/api/frontier/collect/{venue}` route and an Exchanges-view capture action for
`BoundedSourceCollector`. The route shares the per-source lock used by probes,
rechecks the source's enabled/public-probe flags and policy hold, validates
market-discovery/book capabilities and the source market limit, and returns
the durable run result. The request is synchronous and starts no Arena job,
worker, timer, or background collector. API hard caps are five markets, two
books, depth ten, 4 MiB of evidence, and 60 seconds; the UI sends three markets,
one book, depth five, and 30 seconds. Default source settings remain disabled.

The UI displays the result state, market/book/failure counts, adapter request
count and bound, run ID, and adapter-local health limitation. The route starts
new runs only; collection-run history and HTTP resume controls remain open.
The collector's module-level resume path remains independently tested.

### Verification and resource boundary

- New collection API fixture integration: **2 passed** in 1.10 seconds. It
  covers bounded success/persistence plus limit, disabled-source, and held-
  source rejection before any fake adapter call or journal creation.
- `apps/web/src/Frontier.test.tsx`: **8/8** in 4.19 seconds, including the
  explicit payload and rendering of the saved run summary and health boundary.
- TypeScript, strict scoped mypy for `apps/api/frontier.py` and
  `collection.py`, Ruff check/format, Prettier, and `git diff --check` passed.
- Combined Frontier/Arena regression: **354 passed, 2 failed** in 81.75
  seconds. Peak RSS was **366,436 KiB**, with zero swaps. Both failures are
  existing Arena supervisor tests rejected by the shared
  `resource_admission_lock_busy` gate. At the post-run inspection, existing
  Veritas batch PID **3913373** held `/home/charlie/midas/data/arena/.global-admission.lock`
  while in `D` state; it was left untouched. Host memory PSI avg10 then
  measured **35.60% some / 29.55% full**, with **9.9 GiB available** and
  **3.7 GiB swap in use**. Do not repeat admission-dependent tests until that
  lock releases and pressure is remeasured.
- Production build and browser tests were not rerun for this code commit after
  pressure rose. Earlier build/browser results belong to earlier revisions.

No real adapter, external API, collector against a live source, Arena worker,
Reality action, production service, or historical store was accessed. Tests
used the fixture adapter only. The endpoint has not been deployed; live
collection remains unverified.

| Component | Status | Evidence and remaining work |
| --- | --- | --- |
| Explicit bounded collector API and UI | IMPLEMENTED, LIVE VALIDATION PENDING | Fixture API and component tests pass; live source capture, populated browser response, HTTP resume/history, production build, and deployment are pending. |
| Disabled/held/capability request gates | COMPLETE AND VERIFIED | API fixtures prove rejection before collector request or journal creation; no source config was enabled. |
| Broader Frontier/Arena regression | PARTIALLY VERIFIED | 354 passed; two existing supervisor tests failed because a foreign process held Arena's shared admission lock. Rerun only after safe admission is confirmed. |
| Production deployment | DEFERRED | Frontier remains isolated and undeployed. |

**Next safe work:** after resource admission recovers, rerun the two blocked
supervisor tests and build/browser verification for `cf67b2b`. Continue offline
collection-history/recovery integration or other fixture-backed acceptance
work. Do not contact a source merely to populate the catalog or start a
background collector. Frontier remains **PARTIALLY VERIFIED**, research-only,
isolated, and undeployed.

## Verified recorded-health catalog and replay provenance — 2026-10-28 00:31 CET

Code commits `31f62db`, `1779e89`, `9a3eced`, and `8f9b9b8` add a bounded
local catalog for recent collector-health evidence, explicit replay selection,
artifact digest display, and early rejection of ambiguous same-time source
events. `CollectionJournal.latest_source_health_checkpoints` reads the journal
without mutation, leaves a missing journal missing, filters held venues, selects
at most 20 latest timestamped health observations, and revalidates each selected
run's complete checkpoint chain. Its scan is bounded by the journal's 20,000
checkpoint and 64 MiB limits. Timestamp-less `not_probed` does not create an
event or hide the latest timestamped record; a timestamped unsupported state
suppresses an older availability claim.

`GET /api/frontier/collection-health-events` returns adapter-local status,
timestamps, adapter version, checkpoint sequence, last-success time, and the
verified row digest with `network_called: false`. The UI loads the catalog only
in Replay & Readiness. Items start unchecked; selected events enter the next
explicit replay request, and completed timeline details render the digests
pinned in the result manifest. The API rejects duplicate source-status times
for one venue before it creates an Arena job, and the UI disables a second
selection with the same venue/time. The copy explains that checkpoint health is
not continuous venue availability or account eligibility.

### Verification and limits

- Combined Frontier/Arena regression: **354 passed** in 83.42 seconds; peak RSS
  **363,776 KiB**, zero swaps. One existing Starlette/httpx `TestClient`
  deprecation warning.
- Focused journal and timeline API suite: **18 passed** in 7.37 seconds; the
  timestamp-less-state and chain-corruption follow-up cases passed **2/2** in
  0.56 seconds. The API duplicate-time guard passed its targeted test.
- Frontier UI component file: **8/8 passed** after same-time selection guard;
  the replay artifact case asserts the recorded checkpoint digest is visible.
- Isolated Playwright replay-history case: **1/1 passed** in 5.0 seconds after
  the shared lock released. It uses temporary API/store roots and confirmed the
  empty local state, no source probe, and no replay submission on page open.
- TypeScript passed in 7.92 seconds at **448,228 KiB** peak RSS. The production
  Vite build passed in 5.10 seconds at **647,020 KiB**, zero swaps. Frontier
  output is 124.32 kB JS / 39.65 kB CSS; the existing 544.41 kB Chart chunk
  warning remains. Scoped strict mypy passed for four Frontier/Arena source
  files; Ruff check/format, ESLint, Prettier, and `git diff --check` passed.
- At the first browser admission check, shared Arena lock inode **6423106** was
  held by PID **3885836**, PSI avg10 was 29.42% `some` / 22.00% `full`, and
  3.7 GiB swap was in use. The browser/build were deferred then, and run after
  the lock released, avg10 fell to 0%, and 10 GiB was available.

No adapter was probed, no collector or Arena worker was launched, no held-source
record was exposed, and no protected service or production store was touched.
No genuine public health sample or cross-venue economic result was established.

| Component | Status | Evidence and boundary |
| --- | --- | --- |
| Local recorded-health catalog | COMPLETE AND VERIFIED | Bounded read-only scan, latest timestamped observation, held filtering, and full-chain verification have fixture coverage; no genuine live capture was made. |
| Replay health selection and pinned-digest display | PARTIALLY VERIFIED | Explicit selection and manifest digest rendering pass component tests; the empty/offline browser case passes, but no journal-backed live health event was available in the browser. |
| Duplicate same-time source events | COMPLETE AND VERIFIED | API rejects same-venue/same-time duplicates before job staging; UI disables the second selected option; API and component tests pass. |
| Timeline Arena worker and populated result browser flow | IMPLEMENTED, LIVE VALIDATION PENDING | Job, artifact, and populated result are fixture tested; no new Arena worker was launched. |
| Live source permission and multi-venue evidence | BLOCKED | Existing source-use holds remain; this catalog is not a capture path. |
| Production deployment | DEFERRED | Branch remains isolated and unmerged. |

Frontier remains **PARTIALLY VERIFIED**, research-only, isolated, and
undeployed. Continue the remaining offline acceptance work. Do not add network
egress to the Arena worker or register an unattended collector to populate this
list.

## Recorded source-health join and timeline controls — 2026-10-28 00:18 CET

Code commit `ea073c4cdb4a00b70fc609e8806f80a40542cd4c` joins recorded
source-health events to finite collector checkpoints. The API opens the existing
collection journal read-only, validates each selected run-spec digest and its
complete checkpoint chain, and matches the submitted venue, check timestamp,
health state, canonical reason, and checkpoint row digest. A batched request can
join up to 100 checkpoint hashes in one bounded journal scan. Held-source health
is rejected. Unknown health state, bad timestamps, digest substitution, and
corrupt chains fail closed. No missing journal is created by a lookup.

Timeline snapshot schema 2 pins the verified checkpoint digests; schema 1
snapshots without recorded health remain readable. Healthy, degraded, and
explicit unavailable collector states map to replay status. `not_probed` and
`unsupported` do not imply venue availability. Mission Control now allows an
explicit maximum book receipt age from 1 to 3,600,000 milliseconds, validates
the value, and sends it into the pinned replay input.

Follow-up commit `8e79bf1f3bc583aa2329096729c6dd9c624c603d` adds a Mission
Control callout clarifying that recorded source status is adapter-local
checkpoint health, not continuous venue availability or account eligibility.
The associated Web regression asserts the limitation is visible.

### Verification evidence

- Combined Frontier/Arena regression: **350 passed** in 80.52 seconds across
  `tests/frontier`, paired and event-time Arena replay, job schemas, and Arena
  API tests. One existing Starlette/httpx `TestClient` deprecation warning.
- Focused collector/API/Arena timeline set: **21/21** in 6.25 seconds.
- Web after the source-status callout commit: **40/40**; TypeScript, ESLint,
  Prettier, and production build passed.
  The Vite build reports the existing 544.41 kB Chart chunk advisory.
- Browser: **1/1** isolated Playwright empty/offline case passed in 5.3 seconds
  against temporary API/store roots; it observed zero source probes and zero
  replay submissions on page open.
- Legacy integration/admission regression: **63 passed, 1 skipped** in 29.88
  seconds after unsetting `MIDAS_TEST_POSTGRES_URL`; the skipped case requires
  PostgreSQL.
- Strict mypy passed for `collection.py`, `frontier_timeline.py`, and
  `apps/api/frontier.py`; Ruff check/format and `git diff --check` passed.
- Resource sample at `2026-10-27T23:15:35Z`: memory PSI avg10 was 0.00%,
  10 GiB was available, and 400 MiB swap was free. This point-in-time sample
  does not establish future Arena admission.

No exchange call, collector, Arena worker, Reality action, production service,
or historical store was accessed. Files in `ea073c4` are:
`apps/api/frontier.py`, `apps/web/src/Frontier.tsx`,
`apps/web/src/Frontier.test.tsx`, `apps/web/src/frontier.css`,
`packages/midas/frontier/collection.py`,
`packages/midas/arena/frontier_timeline.py`,
`tests/frontier/test_collection.py`, `tests/frontier/test_timeline_api.py`, and
`tests/arena/test_frontier_timeline.py`.

**Next safe work:** provide a bounded read-only catalogue of verified recorded
health checkpoints to the Frontier research UI, and keep collection out of
Arena until its network egress restrictions can be made explicit and testable.
Continue offline adversarial replay and compatibility work. Frontier remains
**PARTIALLY VERIFIED**, isolated, research-only, unmerged, and undeployed.

---

## Event-time Arena integration checkpoint — 2026-10-27 22:58 UTC

Code commit `5e04c14b47c9b820946259a8ad1e232b4597190a` wires deterministic
event-time replay into Arena's existing bounded, offline job path. A
content-addressed snapshot pins saved markets/books/verified relationships,
scenario, cutoff policy, freshness bound, and implementation version. The
worker writes a hash-checked per-frame artifact. API catalog/result routes and
Frontier readiness verify job binding, artifact hashes, runtime metadata, and
held-source quarantine. Mission Control lists event-time jobs and renders frame
freshness/exclusion counts, candidate classifications, source-state labels,
and evidence hashes. No worker was launched; readiness therefore stays
`LIVE_VALIDATION_PENDING`.

The prior code commit `b6b8a99337b5b08a54b5011eaf72d30949ab0b1b` adds a finite
per-source collection module with append-only restart checkpoints. It is not
registered as an API operation, Arena job, or service; tests use fixture
adapters only. Both checkpoints reject held-source use and maintain explicit
limits. Timeline request data cannot claim `basis=recorded` source health yet:
a validated store join is still required.

### Verification evidence

- Python: **347 passed** across `tests/frontier`, Frontier paired/timeline Arena
  artifacts, Arena job-schema tests, and Arena API regressions. Runtime was
  130.66 seconds. The only warning was the existing Starlette/httpx
  `TestClient` deprecation.
- Web: **40/40** unit tests; TypeScript typecheck, ESLint, and production Vite
  build passed. The existing 544.41 kB Chart chunk advisory remains.
- Browser: **1/1** isolated Playwright scenario passed against a temporary demo
  API/database. Opening Replay & Readiness issued zero source probes and zero
  timeline job submissions; the timeline replay action remained disabled with
  no saved markets.
- Scoped strict mypy passed for `frontier_timeline.py`, `jobs.py`,
  `apps/api/frontier.py`, and `apps/api/arena.py`. Repository-wide mypy still
  reports **35 errors in 8 unrelated legacy Veritas/Arena/API files**; it
  reports none in these changed Frontier integration files.
- Ruff check/format, Prettier, and `git diff --check` passed.
- Post-run host sample (`2026-10-27T22:58:15Z`): PSI avg10 was 0.00% `some`
  and `full`; 10 GiB available memory and 429 MiB free swap. This is a dated
  host observation, not a future admission grant.

No live exchange request, collector, Arena worker, Reality action, production
service change, historical-store read, push, merge, or deployment occurred.
The local Playwright API server used temporary test roots and shut down at test
completion.

Files in `5e04c14`:
`apps/api/arena.py`, `apps/api/frontier.py`,
`apps/web/e2e/frontier.spec.ts`, `apps/web/src/Frontier.test.tsx`,
`apps/web/src/Frontier.tsx`, `apps/web/src/frontier.css`,
`packages/midas/arena/jobs.py`,
`packages/midas/arena/frontier_timeline.py`,
`tests/arena/test_frontier_timeline.py`, and
`tests/frontier/test_timeline_api.py`.

**Next safe work:** add an explicit bounded source-collection Arena job around
`BoundedSourceCollector`, with no live worker launch, and add a validated local
store join for recorded source-health events. Keep source permission checks at
the final request boundary, preserve per-source isolation, and continue other
fixture-backed research work if these integrations uncover a permission or
infrastructure blocker. Frontier remains **PARTIALLY VERIFIED**, isolated,
research-only, and undeployed.

---

**Current resource gate (`2026-10-27T21:48:09Z`):** External Veritas batch PID
**3762324** remains in `D` state at `mem_cgroup_handle_over_high`; PSI avg10 is
**47.93% some / 41.46% full**. It is using the existing Veritas and Arena
roots and was left untouched. No Frontier tests or builds ran after this
process appeared. Recheck pressure and the shared Arena admission lock before
starting additional resource-consuming verification.

**Resource admission released (`2026-10-27T21:49:51Z`):** PID 3762324 had
exited; no shared Arena admission lock holder was listed. Memory PSI avg10 was
0.00% `some` / `full`, with 9.9 GiB available and 455 MiB swap free. No
browser rerun was needed: the full 12/12 suite had already passed at the latest
unchanged UI checkpoint (`008106b`, 21:36 UTC). The subsequent 21:45 and 21:46
legacy regression selections also passed. Admission is a point-in-time signal;
recheck before any worker launch.

**Legacy integration and admission-gate regressions (`2026-10-27T21:46:43Z`):**
All `tests/integration` pass **55/55**, with one PostgreSQL test skipped after
explicitly unsetting `MIDAS_TEST_POSTGRES_URL`; the run used
`PYTHONPATH=packages:.:tests`, 29.82 seconds wall, **210,816 KiB peak RSS**,
zero swaps. `tests/arena/test_admission.py` passes **8/8** in 2.04 seconds wall,
**178,692 KiB peak RSS**, zero swaps. The former cross-root resource-snapshot
assertion now passes with its resource inputs isolated; no supervised job was
started. Only the existing TestClient deprecation warning was emitted. The
post-run lock was free, PSI avg10 0.00% `some`/`full`, and 9.9 GiB was
available. Repository-wide collection/runtime limitations outside these
bounded selections remain.

**Legacy compatibility closure (`2026-10-27T21:45:17Z`):** The deferred
four-module selection passed **28/28** against this worktree. The test process
used `PYTHONPATH=packages:.`; an explicit import check resolved
`midas` to `/home/charlie/midas-frontier/packages/midas/__init__.py`. The
adapter, API, recording-isolation, and Frontier Arena replay tests took 5.96
seconds pytest time / 7.32 seconds wall, peak RSS **282,584 KiB**, zero swaps;
only the existing Starlette/httpx `TestClient` deprecation warning remains.
Immediately afterward the Arena lock was free and PSI avg10 was 0.01% `some`
/ 0.00% `full`, with 9.9 GiB available. This closes the four-module test
deferral recorded at 21:39; it does not close the separately documented
repository-wide Python collection/runtime limitations.

**Additional venue screen (`2026-10-27T21:42:51Z`):** Official documentation was reviewed
for Manifold Markets and Betfair. Manifold's current market currency is mana,
which its FAQ describes as non-redeemable, and its 2025 announcement ended the
cash sweepstakes markets. It remains a possible forecast-only reference, not
an economic opportunity leg. Betfair requires a per-account application key;
its delayed data is 1–180 seconds and live read-only access is not permitted,
while commercial usage requires approval. Neither source was queried and no
credentials or account access were requested. Decision and references:
`docs/frontier/ADDITIONAL_VENUE_SCREEN_2026-10-27.md`.
At the same sample, external batch PID **3745206** remained in `D` state with
the shared Arena admission lock held; PSI avg10 was 39.31% `some` / 34.14%
`full`. The compatibility tests remain deferred; no worker or lock was
interfered with.

**Latest verified checkpoint (`008106b`, 2026-10-27 21:36 UTC):** The
Coinbase Decimal exponent guard removes its Frontier-local strict-mypy error;
its focused module passes **11/11**. The full Frontier suite passes
**269/269** (43.61 seconds wall, **352,484 KiB peak RSS**, zero swaps), and
strict direct mypy with `--follow-imports=silent` passes the seven changed
Python source files. The Web unit suite passes **40/40**; TypeScript,
targeted ESLint/Prettier, Ruff, and diff checks pass. The isolated production
build transforms 2,228 modules and passes in 12.74 seconds wall at **701,536
KiB peak RSS**, zero swaps. The complete browser suite passes **12/12** in
27.49 seconds wall at **209,416 KiB peak RSS**, zero swaps, including Frontier
and both bounded Laboratory cases. Build output is under `/tmp`, and browser
API/arena/frontier data are temporary. No exchange request or production
deployment occurred. The prior unfiltered mypy pass attempt reported a
Coinbase diagnostic fixed in `008106b` plus transitive legacy Veritas/Arena
diagnostics; that unfiltered invocation was not rerun. Frontier remains
**PARTIALLY VERIFIED** because exact source permissions, genuine verified
cross-venue economics, and production readiness are unresolved.

**Admission/deferred check (`2026-10-27T21:39:36Z`):** The planned legacy
compatibility selection (`tests/integration/test_adapters.py`,
`tests/integration/test_api.py`, `tests/integration/test_recording_isolation.py`,
and `tests/arena/test_frontier_replay.py`) was not run. External batch PID
**3745206** remained in `D` state while holding the shared
`/home/charlie/midas/data/arena/.global-admission.lock`; PSI avg10 was 44.57%
`some` / 39.03% `full`. The worker and lock were left untouched. Recheck the
host-wide admission lock and memory pressure before running this selection.
Previously completed 269/269 Frontier, 40/40 Web, and 12/12 browser results
remain valid as recorded; this deferred legacy selection is not covered by
those totals.

At `2026-10-27T21:36:40Z`, no shared Arena lock was held. PSI avg10 was 0.00%
(`some`/`full`), avg60 4.24% / 3.72%, avg300 14.30% / 12.58%; 9.5 GiB was
available and 455 MiB swap was free. No protected service or historic store
was accessed.

**Monotonic timing implementation checkpoint (`6bc0351`, 2026-10-27 21:28 UTC):** Read-only
transport now records request elapsed duration using `time.monotonic_ns()`
after source pacing through complete response-body receipt. The duration is
preserved in `RawObservation`, normalized `Provenance`, complete HTTP error
captures, and the stored-evidence disclosure. It is explicitly a per-request
duration, not a clock value comparable across venues/processes; failures without
complete response evidence leave it unknown. The focused adapters/storage/
Coinbase/API selection passes **86/86** (14.00 seconds wall, **88,376 KiB peak
RSS**, zero swaps); targeted UI test passes **1/1** (1.78 seconds, **208,356 KiB
peak RSS**, zero swaps). Ruff check/format and diff checks pass. The full
Frontier suite passed **265/265** on `51afe86`, not yet rerun on `6bc0351`; Web
suite/typecheck, production build, and browser E2E for the new UI disclosure
remain pending. At `2026-10-27T21:28:03Z`, external Arena batch PID **3727342**
held lock inode **6423106** in `D` state and memory PSI avg10 was 45.93%
(`some`) / 40.80% (`full`). It was left untouched. Frontier remains isolated,
research-only, and undeployed.

**Observation persistence code checkpoint (`51afe86`, 2026-10-27
21:23 UTC):** The bounded append-only observation writer now stamps a missing typed
`Provenance.persisted_at_utc` before serializing a new normalized row. It leaves
the caller's model untouched, preserves a prior timestamp when copying an
already persisted capture into a content-addressed snapshot, and compares
idempotent retries with only the typed persistence time cleared. Legacy rows
without the optional field remain readable and idempotent. An initial broad
run exposed a snapshot row-hash regression; the copy-preservation behavior was
corrected, then focused storage/Coinbase/snapshot tests passed **25/25** and the
complete Frontier suite passed **265/265** in 42.04 seconds pytest time / 43.28
seconds wall at **352,164 KiB peak RSS**, zero swaps. The existing
Starlette/httpx TestClient deprecation is the only warning. The suite's broad
run overlapped with a newly started external Arena batch after the admission
precheck; it still completed with no test-process swap. Do not start another
broad or frontend build/browser job while that batch holds the shared lock.
Ruff check/format and `git diff --check` pass. The Coinbase missing-book-time
regression is included; no exchange was queried. Production build and browser
E2E remain pending, and Frontier remains isolated, research-only, and
undeployed.

At `2026-10-27T21:23:04Z`, the external bounded
`veritas_gap_detail_v2_batch.py` PID **3719559** held shared Arena lock inode
**6423106** in `D` state. PSI avg10 was 40.12% (`some`) / 35.81% (`full`),
avg60 18.55% / 16.35%, avg300 16.59% / 14.89%; 9 GiB was available and 459 MiB
swap was free. The process and lock were left untouched. No Reality service,
source API, production service, or historical evidence was changed.

**Admission recheck (2026-10-27 21:14:30 UTC):** The same external
`veritas_gap_detail_v2_batch.py` worker PID **3711078** still held lock inode
**6423106** in `D` state after 2:11 elapsed. PSI had risen to 47.63% (`some`) /
40.92% (`full`) avg10, 40.75% / 36.55% avg60, and 24.14% / 21.74% avg300.
About 10 GiB remained available and 459 MiB swap was free. No build or browser
test was launched; the worker and lock remain untouched.

**Latest regression checkpoint (2026-10-27 21:12 UTC):** The full Frontier
Python suite passes **262/262** in 41.60 seconds (42.81 seconds wall,
**353,748 KiB peak RSS**, zero swaps). The full web unit suite passes **40/40**
in 14.86 seconds (15.56 seconds wall, **271,600 KiB peak RSS**, zero swaps,
one worker). TypeScript typecheck passes in 7.83 seconds at **439,648 KiB peak
RSS**, zero swaps; targeted ESLint, Ruff check/format, Prettier, and
`git diff --check` pass. The only warning in the Python suite is the existing
Starlette/httpx TestClient deprecation. The production build and browser E2E
suite remain pending.

At `2026-10-27T21:12:52Z`, external `veritas_gap_detail_v2_batch.py` PID
**3711078** held the shared Arena lock inode **6423106** in `D` state. PSI
avg10 was 35.46% (`some`) / 31.91% (`full`), avg60 13.64% / 11.93%, avg300
15.10% / 13.55%; 9 GiB was available and 459 MiB swap was free. It remains
untouched. Next safe action: wait for resource admission, then run the isolated
Frontier browser cases and production build before broader repository checks.
No live source, production service, or historical capture was accessed.

**Latest implementation checkpoint (2026-10-27 21:07 UTC):** Commit `cfda4ad`
adds the Coinbase Exchange spot adapter, exact terms-version enforcement in
both API settings and `CoinbaseSpotConfig`, source quarantine integration, and
Mission Control presentation. The adapter is limited to configured public
product metadata, aggregated L2 snapshots, and one bounded public trade page;
spot remains contextual evidence with no event payoff, account fee, or
settlement claim. Coinbase live access remains unused because organization,
regional, retention, and redistribution scope are unresolved. No exchange
request or held historical capture was made.

The focused adapter, API terms gate, held-source quarantine, and spot-payoff
selection passed **10/10** in 3.19 seconds (3.90 seconds wall), at **131,064 KiB
peak RSS** and zero swaps. The existing Starlette/httpx TestClient deprecation
warning remains. Ruff check/format, Prettier, and `git diff --check` pass. These
tests use local mock transports and temporary stores; they do not establish
live Coinbase validation or permission. The full Frontier suite, full web
suite, production build, and browser regression remain pending for this code
checkpoint.

At `2026-10-27T21:07:37Z`, the external
`veritas_gap_detail_v2_batch.py` worker PID **3706995** held global Arena lock
inode **6423106** in `D` state. PSI avg10 was 30.67% (`some`) / 27.75% (`full`),
avg60 10.73% / 9.72%, avg300 19.99% / 17.95%; 9 GiB was available and 459
MiB swap was free. It was left untouched. Next safe action: wait for the shared
admission lock to release and PSI to settle, then run bounded Frontier and web
regressions for `cfda4ad` before continuing broader mission work. Frontier
remains incomplete, research-only, isolated, and undeployed.

**Latest Laboratory compatibility check (2026-10-27 20:09 UTC):** The existing
`test_laboratory_api_contract_and_reproduction` passed **1 test** (two module
tests deselected) in 2.50 seconds (3.15 seconds wall), at **124,540 KiB peak
RSS**, zero swaps. It runs/reproduces four virtual demo cases. The process used
`MIDAS_MODE=demo` and fresh `/tmp` Frontier/Arena roots; database, Laboratory,
and recording data used the test's `tmp_path`. The only warning is the existing
Starlette/httpx deprecation. At `2026-10-27T20:09:29Z`, host PSI avg10 was
0.12% (`some`) / 0.11% (`full`), avg60 12.97% / 11.97%, avg300 15.92% / 14.55%;
9.6 GiB was available and 468 MiB swap free. No exchange source, production
Arena job, Reality service, or historical store was accessed. This is one
bounded Laboratory smoke, not the Laboratory suite or repository regression.

**Latest legacy regressions (2026-10-27 20:06 UTC):** Existing Polymarket
adapter tests `tests/integration/test_adapters.py` pass **9/9** in 0.71 seconds
(1.21 seconds wall), at **88,872 KiB peak RSS**, zero swaps. They use recorded
repository fixtures and `httpx.MockTransport`; no live request is possible in
these cases. Recording-path regressions `tests/integration/test_recording_isolation.py`
pass **4/4** in 0.49 seconds (0.93 seconds wall), at **77,800 KiB peak RSS**,
zero swaps. All writes are under `tmp_path`; the production-default test only
asserts the established path. At `2026-10-27T20:06:31Z`, PSI avg10 was 0.00%
(`some`/`full`), avg60 2.62% / 2.36%, avg300 12.54% / 11.33%; 9.6 GiB was
available and swap free was 468 MiB. No protected recorder, historical store,
public source, or deployment was accessed. These narrow suites strengthen
legacy coverage; the repository-wide suite remains unrun.

**Latest legacy compatibility check (2026-10-27 20:05 UTC):** The safe
`tests/integration/test_api.py` slice passes **5/5** in 3.99 seconds (5.01
seconds wall) at **154,664 KiB peak RSS**, zero swaps. The demo workflow
forbids constructing a public client and uses temporary databases/workspaces;
the Arena qualification route is mocked. It covers legacy API health,
readiness, persistence gates, configured Veritas/Reality workspace routes,
plus Frontier's no-probe view. Only the existing Starlette/httpx TestClient
deprecation warning remains. At `2026-10-27T20:05:24Z`, admission PSI avg10 was
0.00% (`some`/`full`), avg60 8.15% / 7.33%, avg300 15.84% / 14.31%; 9.6 GiB
was available and 468 MiB swap free. No live source, protected service state,
or historical store was accessed. The full repository suite remains unrun.

**Latest verification (2026-10-27 20:04 UTC):** Frontier's Arena replay
integration suite `tests/arena/test_frontier_replay.py` passes **10/10** in
1.94 seconds (2.63 seconds wall), at **193,936 KiB peak RSS** with zero swaps.
The fixture-only cases exercise bounded job snapshots and catalogs, immutable
artifact hashes/recovery, API result reads, and held-source quarantine under
temporary roots. The only warning is the existing Starlette/httpx TestClient
deprecation. At `2026-10-27T20:04:45Z`, host PSI avg10 was 0.22% (`some`) /
0.20% (`full`), avg60 15.34% / 13.80%, avg300 18.05% / 16.31%; 9.6 GiB was
available and 468 MiB swap free. No persistent Arena job, source request,
held-capture read, protected service action, or deployment occurred. This
adds integration-test evidence only; Frontier remains PARTIALLY VERIFIED.

**Latest checkpoint (2026-10-27 20:02 UTC):** Code commit `29ab175` adds
per-venue virtual post-settlement release delays to the saved-run-bound capital
duration sensitivity. Delay accepts bounded whole seconds up to one year,
defaults to zero, must cover every venue when supplied, and is included in the
input digest. The independent Fraction audit recomputes release time, elapsed
duration, carry, and adjusted P&L. Settlement instants are normalized to UTC
before delay arithmetic; unrepresentable timestamps fail closed. The API
forwards the input and Mission Control renders it as a scenario assumption.
The model/API/UI changes are covered by **27/27** capital-carry tests, the
saved-run API integration (**1 passed, 43 deselected**), the full Frontier
Python suite (**246/246**), the full web suite (**40/40 across seven files**),
and the isolated Frontier Playwright suite (**4/4**). The post-format capital
module rerun also passed **27/27**. TypeScript build/typecheck, targeted ESLint,
Prettier, Ruff check/format, strict mypy for `capital.py` and the Frontier API,
and `git diff --check` pass. The production build in
`/tmp/midas-frontier-web-build-20261027-2001` compiled 2,228 modules in 4.65
seconds Vite time (12.28 seconds wall) at 700,060 KiB peak RSS with zero swaps;
the repository `dist` was untouched. The existing large index/Chart chunk
warning and external-output-directory warning remain. At
`2026-10-27T20:02:00Z`, host memory PSI avg10 was 0.00% (`some`/`full`), avg60
1.19% / 1.09%, avg300 14.11% / 12.77%; 9.5 GiB was available and 468 MiB swap
free. The Frontier suite emitted its existing Starlette/httpx deprecation
warning. The repository-wide legacy suite remains unrun. No live source
request, held-capture read, Reality action, or deployment occurred. Frontier
remains isolated, research-only, PARTIALLY VERIFIED, and undeployed. Next safe
work: review remaining economic cost/settlement limits; continue only with
fresh resource admission before broad regressions or new builds.

**Latest checkpoint (2026-10-27 19:11 UTC):** The runtime held-source guard
is now hardened and verified. Commit `df30fa7` resolves symlink paths before
checking, handles relative `dir_fd` paths through `/proc/self/fd`, removes the
raw opener escape hatch, and tests read/write blocking against `tmp_path`
including symlink traversal with `..`. The guard tests pass **2/2**; Ruff and
format checks pass. A read-only reviewer confirmed the two path bypasses were
closed and found no ordinary Frontier-test interference. Commit `2aef789`
introduced the initial autouse wrappers. The full Frontier
suite passes **219 tests in 39.83 seconds**, **335,396 KiB peak RSS**, zero
swaps, with only the existing Starlette/httpx deprecation warning. Source-text
scans over `tests`, `packages`, and `apps` find no `live-probes` references.
No preserved capture was opened or changed during this cleanup; the historical
18:41 run did read the former test inputs, with no mutation known. At
19:11:39 UTC, host PSI avg10 was 0.00% (`some`/`full`), avg300 20.47%/18.55%;
9.1 GiB was available and 467 MiB swap free. Kalshi/Kraken permission, live
cross-venue economics, repository-wide regression, and production deployment
remain open.

**Latest checkpoint (2026-10-27 19:05 UTC):** After the 19:02 validation,
added `tests/frontier/conftest.py` with an autouse guard for built-in, `io`,
and `os.open` access to the held source path, plus a regression that attempts
read and write only beneath `tmp_path`. No preserved data path was accessed.
The new runtime guard/test has not been run; the previous 218-test pass
predates it. A source-text scan still finds no explicit `live-probes` path
references. At 19:05:42 UTC, PSI was avg10 46.45% (`some`) / 42.53% (`full`),
avg300 31.13%/28.15%, with 9.2 GiB available and 467 MiB swap free. No further
test was admitted. Next safe action: remeasure, run the boundary guard first,
then the full Frontier suite only if short-window PSI permits. Keep overall
source permission and live-source validation blocked.

**Latest checkpoint (2026-10-27 19:02 UTC):** Commit `5e51a88` removes all
15 test-source reads from held `data/frontier/live-probes` captures, replaces
them with synthetic responses/records, and adds a source-path guard. The guard
passed **1/1**; the changed adapter/API selection passed **24 tests** (4.17s,
94,724 KiB peak RSS, zero swaps); the full Frontier Python suite passed
**218 tests** (39.36s, 333,988 KiB peak RSS, zero swaps). The one existing
Starlette/httpx TestClient deprecation warning remains. A scan over `tests`,
`packages`, and `apps` finds no `live-probes` path. The earlier 18:41 suite did
read held capture files through the then-existing test references; no test
writes or capture mutation are known. Current tests use synthetic inputs and
do not validate live source behavior or permission.

After the UI settlement identity hardening, the Frontier web component suite
passed **8/8**, the full web unit suite passed **40/40**, typecheck passed,
targeted ESLint and Prettier passed, the isolated Frontier Playwright suite
passed **4/4** (191,496 KiB peak RSS, zero swaps), and the production build
passed (714,944 KiB peak RSS, zero swaps). Vite retains the known large index
and chart chunk warning. The test/browser services used temporary local
databases and roots; no exchange probe was made. Frontier remains isolated and
undeployed, with source permission and live cross-venue economics unresolved.
Commit `3e7d1b9` contains the UI source/test hardening and verification handoff.

**Latest checkpoint (2026-10-27 18:57 UTC):** A source-use boundary audit
found 15 direct `data/frontier/live-probes` path references in
`tests/frontier/test_adapters.py` and `tests/frontier/test_api.py`. The
18:41 UTC full Frontier suite executed those cases and read the preserved
artifacts; this corrects the earlier statement that these tests used only
controlled fixtures. No test writes to those files were found, and no capture
mutation is known. All 15 references have now been converted to synthetic
local inputs. A `rg` scan over `tests`, `packages`, and `apps` finds no
`live-probes` path; a permanent static Python-test guard is added. Neither
capture data nor bytes were opened by this audit, and the existing capture
files remain untouched. Source terms review, engineering report, operations,
and current-state docs record the correction and current official terms. The
static guard and changed functional tests remain unrun because PSI and swap use
are elevated. Do not rerun until a fresh resource check admits bounded tests.

At 2026-10-27T18:57:27Z, host memory PSI was some/full avg10 17.36%/15.65%,
avg60 38.95%/34.76%, avg300 41.14%/36.90%; 9.4 GiB was available but swap
free remained 472 MiB. No test/build was started. Frontier remains
isolated and undeployed; Kalshi and Kraken live probes and held-data reads stay
blocked. Next safe action: remeasure pressure and run the static boundary test
plus affected adapter/API cases only after the host is admitted.

**Latest checkpoint (2026-10-27 18:51 UTC):** Commit `547a37b` hardens the
virtual-funding UI: identity objects are validated against supported schema v1,
matching compares all five identity fields directly, balance state is keyed by
a JSON tuple, and non-fiat display labels escape delimiters. Regression
coverage was added for the colliding identity pair, separate balances,
mismatched capital/leg units, and unsupported identity version. Prettier and
`git diff --check` pass; the focused component test and production build have
not run after this patch. At 2026-10-27T18:51:18Z, PSI was 42.89% some /
38.45% full over 10 seconds and 35.52% / 32.03% over five minutes; available
memory was 9.22 GiB and swap free was 473 MiB.

Next safe action: remeasure pressure before the focused UI regression, complete
Frontier Python suite, or frontend build. Keep live source and production gates
closed.

**Previous checkpoint (2026-10-27 18:49 UTC):** The backend asset identity key
now uses a versioned compact JSON tuple, and the same-payoff/logical implication
verifier versions advance to v4/v2. The schema rejects unsupported identity
versions. Four focused synthetic tests pass; Ruff, format, and whitespace checks
pass. The complete Frontier suite and strict mypy were not rerun after this
change. At 2026-10-27T18:49:39Z, host PSI was 46.81% some / 42.40% full over
10 seconds and 31.84% / 28.83% over five minutes; available memory was 9.22 GiB
and swap free was 473 MiB. No source request or protected service was used.

The UI field-comparison/key hardening is implemented and Prettier-checked;
its focused component test and the full Frontier suite remain pending.
Remeasure host headroom before running them; defer the production build while
short-window PSI remains high.

**Previous checkpoint (2026-10-27 18:43 UTC):** The full web unit suite passes
**40 tests across 7 files** in 5.00 seconds, including all eight Frontier
component tests. The four Frontier browser tests passed at the preceding
18:40 UTC checkpoint. No frontend files changed during these checks. At
2026-10-27T18:43:32Z, host PSI rose to 36.01% some / 28.91% full over 10
seconds and 20.59% / 18.43% over five minutes; available memory was 8.81 GiB
and swap free 473 MiB. The production build was deferred because its prior
peak was about 676 MiB and current pressure is elevated. The latest build
after row-hash and carry UI changes remains unverified. No exchange request or
protected service was used.

Next safe action: wait for and remeasure resource headroom before attempting the
latest production build, then continue remaining implementation and scientific
acceptance gaps.

**Previous checkpoint (2026-10-27 18:41 UTC):** The complete Frontier Python
suite passes **215 tests in 39.29 seconds**. `/usr/bin/time -v` measured
335,120 KiB peak RSS and zero swaps. The only warning was the existing
Starlette/httpx TestClient deprecation. At 2026-10-27T18:41:46Z, PSI 10-second
averages were 0.00% (some and full) and five-minute averages were 15.37%
(some) and 13.84% (full); available memory was 9.46 GiB and swap free was
471 MiB. The full suite covers Frontier only; repository-wide collection and
the baseline missing Reality recovery dependency remain separate. Frontier
remains isolated and undeployed.

Next safe action: continue investigating and implementing remaining Frontier
coverage, then run the bounded isolated regressions that match each change.
Do not infer production readiness or live cross-venue validation from this
local suite.

**Previous checkpoint (2026-10-27 18:40 UTC):** The four Frontier browser tests
pass after the candidate SHA-256 fixture correction, using temporary local
demo services and no exchange probes. The focused parser selection passes
three cases, and the API source-failure persistence/recovery test passes.
Ruff, format, strict transport mypy, and whitespace checks pass. The API test
emitted the existing Starlette/httpx deprecation warning. At
2026-10-27T18:40:37Z, PSI 10-second averages were 0.00% (some and full) and
five-minute averages were 19.56% (some) and 17.60% (full); available memory was
9.12 GiB and swap free was 471 MiB. Frontier remains isolated and undeployed.

Next safe action: continue the broader Python regression and remaining
economics/research gaps. Recheck resource admission before any broad or
browser-heavy run; do not access restricted sources or protected services.

**Previous checkpoint (2026-10-27 18:39 UTC):** The public transport now checks
JSON nesting before decoding and classifies more than 64 nested containers as
`JSON_COMPLEXITY_LIMIT`. Delimiters inside escaped JSON strings are ignored,
and oversized integer tokens remain covered by the parser fallback. Three
focused adapter cases and the API diagnostic persistence/recovery test pass.
Ruff, format, strict mypy for the transport module, and `git diff --check`
pass. The API test emitted the existing Starlette/httpx deprecation warning.
At `2026-10-27T18:39:43Z`, PSI was `some avg10=0.00%` and
`full avg10=0.00%`, with elevated five-minute averages (some 23.54%,
full 21.19%); available memory was 9.47 GiB and swap free was 471 MiB.
No broad suite had been started in this checkpoint. Frontier remained isolated
and undeployed.

The four Frontier browser tests were run at the following checkpoint after
short-window host PSI had fallen to zero.

**Previous checkpoint (2026-10-27 18:37 UTC):** Code commit `ac5daaf`
classified JSON parser complexity failures (deep nesting and oversized
integer tokens) as `JSON_COMPLEXITY_LIMIT`, preserving bounded raw-response
evidence without retry. The focused transport/API selection passed **3 tests**,
including source-failure persistence and recovery. Ruff, format, strict mypy
for the transport module, and `git diff --check` passed. The focused test
process peaked at 86,772 KiB RSS with zero swaps. At
`2026-10-27T18:37:02Z`, host PSI was elevated (some avg10=41.88%,
full avg10=37.24%); broad suites and browser revalidation were deferred.
Frontier remains isolated and undeployed.

**Previous checkpoint (2026-10-27 18:32 UTC):** Code commit `9a4ccf4` corrects the
capital-carry browser fixture to use a 64-character candidate SHA-256 ID, as
required by `CapitalCarryRequest`. Ruff, Prettier, and Playwright's four-test
discovery pass. The browser suite passed before this fixture correction, so
the Frontier E2E file must be rerun before claiming its latest version passes.
At the latest resource sample (`2026-10-27T18:32:26Z`), PSI was `some
avg10=44.47%` / `full avg10=40.44%`; browser execution remains deferred.

Next safe actions: after measured pressure eases, rerun all four Frontier E2E
tests, then continue the incomplete broader Python regression and remaining
engineering gaps.

**Previous checkpoint (2026-10-27 18:31 UTC):** Code commit `ceea335` changes
four legacy sibling-fixture imports to package-qualified `tests.*` paths. This
preserves test behavior while fixing collection in those files; Ruff passes and
the four files collect **51 tests**. The whole repository collection has not
been repeated since this change. The full-scale Reality test still imports a
`midas.reality.recovery` module absent from the verified baseline. At
`2026-10-27T18:31:23Z`, PSI remained elevated (`some avg10=44.39%`,
`full avg10=40.01%`), so broad runtime verification remains deferred.

Next safe actions: recheck pressure before rerunning repository-wide collection
and tests. Keep the absent Reality recovery dependency explicit; do not copy
from a different dirty worktree or rewrite its substantive test.

**Previous checkpoint (2026-10-27 18:30 UTC):** Code commit `adf1b15` makes the
Arena cross-root catalog test independent of actual machine headroom and PSI.
It still tests real directory/job traversal and asserts the worker-admission
reason; only host telemetry inputs are fixed, while separate tests cover those
thresholds. The isolated test passed, and Ruff/format checks passed. The
repository-wide suite has not been rerun since this repair. At
`2026-10-27T18:30:09Z`, PSI was `some avg10=46.13%` / `full avg10=41.43%`, so
broader testing remains deferred.

Next safe actions: when host pressure eases, rerun the repository suite with
`PYTHONPATH=tests`, excluding only the full-scale Reality test whose required
`midas.reality.recovery` module is absent from the selected baseline. Preserve
all other results and report any remaining host-sensitive failures directly.

**Previous checkpoint (2026-10-27 18:28 UTC):** The repository-wide Python suite
remains incomplete. Plain `pytest -q` stopped in collection with five errors:
four sibling test imports need `tests/` on `PYTHONPATH`, and
`tests/test_reality_full_scale_validation.py` imports
`midas.reality.recovery`, which is absent from this Frontier/V6 baseline and
from current `main`. With `PYTHONPATH=tests` and only that incompatible file
excluded, 50 tests passed before the live resource-gate test correctly found
`host_memory_pressure` in addition to its fixture worker blocker. I interrupted
the run at that point. At `2026-10-27T18:28:25Z`, PSI was `some avg10=34.98%` /
`full avg10=30.76%`, with `MemAvailable` 9,528,840 KiB and swap free 482,740
KiB. No tests were changed to suppress the result; the already completed
Frontier/web/build/browser verification remains green.

Next safe actions: wait for host pressure to materially ease, then rerun the
suite with `PYTHONPATH=tests` while reporting the unavailable Reality recovery
module separately. Preserve the verified V6 baseline, protected Reality code,
and unrelated dirty worktrees.

**Previous checkpoint (2026-10-27 18:26 UTC):** Code commit `80162fe` scopes the
funding E2E balance assertion to its venue row after the full Frontier spec
revealed two `status` elements in the panel. The isolated rerun passes, and the
full browser suite passes **12 tests**. The full Frontier Python suite passes
**212 tests** in 40.20s with one existing Starlette/httpx TestClient
deprecation warning; the full web unit suite passes **40 tests**. The
production frontend build passes with **693,052 KiB** peak RSS, zero swaps, and
the existing Vite warning for the 504 kB index and 544 kB chart chunks. At
`2026-10-27T18:26:20Z`, PSI was `some avg10=0.00%` / `full avg10=0.00%`, with
`MemAvailable` 9,442,548 KiB and swap free 482,576 KiB. Frontier remains
isolated, incomplete, and undeployed.

Next safe actions: continue the remaining economics and research-infrastructure
gaps from the report. Preserve the source permission gate; live cross-venue
semantic/economic validation, transfer/FX/collateral/settlement risks, full
production readiness, and separate deployment authorization remain unresolved.

**Previous checkpoint (2026-10-27 18:22 UTC):** Code commit `abb512f` extends the
32-example Decimal-vs-Fraction property test with independent random
microsecond offsets for each venue settlement. This exercises the exact
subsecond conversion in the audit while retaining separately varying capital,
rate, and venue duration inputs. The focused capital-carry module passed **9
tests**; Ruff and formatting checks pass. At `2026-10-27T18:22:13Z`, PSI rose
to `some avg10=45.68%` / `full avg10=41.43%`, with `MemAvailable` 9,823,344
KiB and swap free 482,520 KiB. Browser execution, post-row-hash full suites,
and the production build remain deferred. Frontier remains isolated,
incomplete, and undeployed.

Next safe actions: after pressure improved, the full browser, Python, and web
verification completed in the later checkpoint. Continue remaining Frontier
work while preserving venue permission gates and protected services.

**Previous checkpoint (2026-10-27 18:21 UTC):** Code commit `6fe0192` changes the
decisive capital-carry audit to reconstruct elapsed seconds and carry as exact
`Fraction` values, then round only when exposing the Decimal result. The
production sensitivity remains Decimal-based; the verifier no longer shares
its arithmetic path. A tampered per-venue carry test confirms the audit reports
disagreement. The focused capital-carry module passed **9 tests**; Ruff check,
Ruff format check, strict mypy for `capital.py`, and `git diff --check` passed.
At `2026-10-27T18:21:36Z`, memory PSI was `some avg10=41.79%` /
`full avg10=37.24%`, with `MemAvailable` 9,661,452 KiB and swap free 482,512
KiB. Browser execution, post-row-hash full suites, and the production build
remain pending. Frontier remains isolated, incomplete, and undeployed.

Next safe actions: after measured pressure materially eases, run the targeted
fixture browser test, post-row-hash full Python/web suites, and production
build; record resource usage. Continue the deferred capital/settlement and
research-infrastructure gaps without using restricted venue data or touching
protected services.

**Previous checkpoint (2026-10-27 18:20 UTC):** Code commit `b112a6c` adds a
bounded Hypothesis differential check for venue-separated virtual carry. Across
32 generated inputs, the Decimal calculator agrees with a separate exact
`Fraction` reference for each venue and total, while the independent audit
remains verified. `pytest -q tests/frontier/test_capital_carry.py` passed **8
tests**. Commit `1b5fc82` adds a fixture-intercepted browser scenario that pins
the saved-run request, venue rates, classification, independent-audit text,
and source-row hash shown in the carry result. ESLint and Prettier pass, and
Playwright discovers all **4** Frontier E2E tests. The browser was not launched:
at `2026-10-27T18:20:14Z`, memory PSI was `avg10=45.75%` (`some`) /
`41.08%` (`full`), `MemAvailable` 9,691,132 KiB, and swap free 482,504 KiB.
Browser execution and a post-row-hash full suite/build remain pending under
this pressure. No venue request, held-source read, protected service, or
production deployment occurred. Frontier remains isolated, incomplete, and
undeployed.

Next safe actions: wait for a materially lower pressure sample before running
the focused Frontier browser E2E; then run post-row-hash Python/web suites and
the production build, recording each resource measurement. Continue remaining
economics/research work independently of venue permission review. Keep source
terms, Reality, production services, and existing research evidence unchanged.

**Previous checkpoint (2026-10-27 18:15 UTC):** Code commit `e9da21a` adds a
saved-run-bound virtual capital-duration sensitivity. Candidates expose their
run ID/hash; the on-demand API validates held-source state and each leg's pinned
market/store-row/raw hashes, then requires source-marked verified future
settlement metadata and exact common denomination. User-entered annual bps rates
feed an unrounded, venue-separated actual-seconds/365 simple-interest scenario
with independent arithmetic and no candidate classification change. Result is
transient, uses no source request, and creates no database record. The full
Frontier Python suite passed **208 tests** (334,996 KiB peak RSS, zero swaps or
socket activity) and the full web suite passed **40 tests** before the final
store-row-hash output adjustment. After that narrow change, the focused Python
model/API selection passed **8 tests** and the Frontier component suite passed
**8 tests**. TypeScript, targeted ESLint/Prettier, strict mypy on the two changed
Python modules, Ruff check/format, and `git diff --check` passed. The production
build passed before the final display adjustment; it reports the existing
index/chart chunk-size warning. At 18:15 UTC, PSI `avg10` was 39.17% (`some`) /
34.05% (`full`), with 482,448 KiB swap free. Browser E2E and a final
post-provenance full suite/build are deferred under that pressure sample. No
live/held source, protected service, or production deployment was used. Frontier
remains isolated, incomplete, and undeployed.

Next safe actions: after current PSI settles, rerun the full Frontier and web
suites plus production build against the final row-hash response; browser
coverage and the Hypothesis differential check are tracked in the later
checkpoint. Keep source terms, Reality, production services, and existing
research evidence unchanged.

**Previous checkpoint (2026-10-27 17:58 UTC):** Code commit `047298b` adds
deterministic pagination for uncentered relationship text search. Its keyset
cursor binds the normalized query, depth, page size, and append-only graph
revision; the UI now searches recorded market titles/IDs, loads more matches,
and states the coverage limit. The implementation still searches at most the
200-record market window and scans at most 500 relationship rows. The Frontier
API module passed **44 tests**; the depth-two search pagination case passed
again after its fixture was extended to include a second-hop edge. The Frontier
component suite passed **8 tests**, including query submission, pagination, and
coverage text. TypeScript typecheck, targeted ESLint/Prettier, Ruff check/format,
and `git diff --check` passed. At 17:58 UTC, PSI `avg10` was 32.30% (`some`) /
25.89% (`full`), and 475 MiB swap was free. Production build and browser E2E
remain deferred. No source or held data was accessed. Full-universe search and
clustering remain open; Frontier is incomplete and undeployed.

**Latest checkpoint (2026-10-27 17:52 UTC):** Code commit `d0b7f0f` adds
bounded, hash-checked relationship review-history storage/API pages and an
on-demand Mission Control history panel. Keyset cursors are relationship-bound;
held-source relationships return 409. The review API module passed **13 tests**,
the held-source quarantine integration test passed **1 test**, and the Frontier
component suite passed **8 tests**. TypeScript typecheck, targeted ESLint,
Prettier, Ruff check/format, and `git diff --check` passed. Strict mypy reported
14 existing errors in four imported Veritas/Arena files and none in the two
selected source files. A production build and browser E2E were deferred at the
17:52 UTC resource sample: memory PSI `avg10` was 45.66% (`some`) / 41.31%
(`full`), with 474 MiB swap free. No source or held-data read, service change,
or deployment occurred. Frontier remains incomplete and undeployed; full
universe graph search, authenticated review, a fresh production build, and
browser validation remain open.

**Latest checkpoint (2026-10-27 17:44 UTC):** UI commit
`0b293915511aa08f008b5b12241ad1238ab8c96a` validates mapping JSON before
submission, rejecting blank keys/values and non-string values. The focused
review component test passes with an assertion that malformed input sends no
request; TypeScript, ESLint, and Prettier checks pass. Direct request-model
validation also rejects numeric mapping targets. The full frontend 40-test run
predates this small guard; the focused test was rerun after it. At 17:44:28 UTC,
PSI `avg10` was 45.36% (`some`) / 40.48% (`full`), with 486,248 KiB swap free of
4 GiB. No source or held data was accessed.

**Previous checkpoint (2026-10-27 17:42 UTC):** The bounded Frontier Python suite
passed **199 tests** in 37.94 seconds (39.01 seconds wall), at 329,116 KiB
peak RSS, zero swaps, and zero socket messages. It includes the implication
relationship review, deterministic candidate replay, independent audit, and
reverse-endpoint non-identity mapping regression. Only the existing
Starlette/httpx TestClient deprecation warning remains. Tests used fixture
transport and temporary roots; no live source was accessed. At 17:42:45 UTC,
memory PSI `avg10` was 37.14% (`some`) / 33.70% (`full`), `avg60` 12.71% /
11.29%, and `avg300` 15.55% / 13.83%; 486,228 KiB swap remained free of 4 GiB.
The complete repository suite and production frontend build remain unrun.

**Previous checkpoint (2026-10-27 17:40 UTC):** Test commit
`95372c8feb1129609e3e2ed4f20179432ed4e446` covers the reversed-endpoint case
for a non-identity three-state implication mapping. It verifies canonical
mapping inversion, correct source-NO/target-YES legs, mapped terminal payouts,
independent audit, and deterministic replay. The focused implication/API/
audit selection passed **15 tests**; Ruff check and formatting passed. No live
source request or held-data read was made. At 17:40:29 UTC, PSI `avg10` was
0.00% (`some`) / 0.00% (`full`), with `avg300` 20.00% / 17.80%; the full
Frontier Python suite and production build remain unrun.

**Previous checkpoint (2026-10-27 17:38 UTC):** UI commit
`ce14e87f4d494d8a0fe5a041d4fb65fd1feab8fb` adds a native Mission Control
review form for directed YES implications, including direction selection and
left-to-right joint-state mapping. The form only enables this claim when the
loaded markets have verified exhaustive binary payoffs, verified resolution,
one YES/NO instrument each, bounded state IDs, and both pinned source records;
the API verifier remains authoritative. The assertion ID is labeled as a
reference and reviewer identity remains self-attributed. The frontend unit
suite passed **40 tests**; the targeted browser test passed **1** with local
fixture routes and temporary storage. TypeScript, ESLint, Prettier, and
`git diff --check` passed. No source requests were made. At 17:38:29 UTC, PSI
`avg10` was 0.00% (`some`) / 0.00% (`full`), while `avg300` remained 30.21% /
26.89%; the production build and full Frontier Python suite remain deferred.
Frontier is still undeployed and incomplete.

**Previous checkpoint (2026-10-27 17:33 UTC):** Code commit
`6706fe1d3194224697b5101a2f92fb6ba914c693` connects verified directed
logical-implication relationships to a bounded `NO(source) + YES(target)`
opportunity family, deterministic replay, and independent audit. It requires
both pinned market observations, assertion evidence no later than the replay
cutoff, matching denomination/close/settlement terms, complementary binary
payouts, and fresh books. Positive results remain conditional because the
semantic assertion is unauthenticated. Fourteen focused fixture/API tests,
Ruff check/format, and strict mypy on the four changed source modules passed.
No live source request or held-data read was made, and no genuine cross-venue
implication opportunity was established. At 17:33:19 UTC, memory PSI `avg10`
was 45.57% (`some`) / 41.61% (`full`), with 485,724 KiB swap free of 4 GiB;
the full suite, browser E2E, and production build remain deferred. Frontier is
still incomplete and undeployed.

**Previous checkpoint (2026-10-27):** Code commit `3e85c8d` integrates a
provenance-bound, conditional Kalshi one-fill fee estimate into saved-evidence
replay. Only complete raw/hash/path/identity-matched supported event/series
metadata no later than the pinned quote and at most 24 hours old at quote and
replay time can contribute. The model uses the documented non-direct `$0.01`
balance-alignment scenario; candidates remain conditional or incomplete, and
the independent audit re-derives the estimate. Replay manifest v2 separately
pins fee observation IDs, and Mission Control displays their count.

Focused verification passed **60 tests**: 35 economics/replay, 3 API fee and
quarantine, 19 storage/replay comparison, 2 adapter capability/metadata, and 1
Mission Control fixture test. API test commit `ad1415b` also verifies the
estimate and both fee evidence IDs in `/api/frontier/markets`. This includes
fee-evidence future-quote, quote-age, and replay-age rejection. Strict mypy
passed for six changed Python source modules; Ruff check/format, TypeScript
typecheck, targeted ESLint/Prettier, and `git diff --check` passed. The full
Frontier suite and production build remain deferred. At the later 16:49 UTC
sample, memory PSI `avg10` was 40.64% `some` / 36.38% `full`, and only about
473 MiB swap remained free. No source request, held-data read, service,
production setting, or historical artifact was accessed or changed.

Storage test commit `f35677d` extends the legacy replay regression to cover a
schema-v1 manifest without the new fee-ID field. The focused test passed in
0.55 seconds and preserved the stored JSON/hash; the wider storage/replay
comparison selection was not rerun after this test-only change.

Current touched versions are Kalshi adapter v16, economic model v8,
independent audit v5, and replay v8. The Frontier mission remains incomplete,
undeployed, and without a genuine verified cross-venue economic result. The
previous checkpoint `e950b9c` made Kalshi fee sensitivities fail closed when
event override fields are partial or unreported; the adapter records complete,
inherited, partial, and unreported states. The previous
checkpoint commits `79eefef`, `82d7e47`, and
`287da15` add independent-audit mutation checks for fee totals, per-leg fees,
and venue capital, plus independent replay verification at the 16-outcome
bound. The audit/replay module passes 28 tests. Code commit `23f9860` also moves
held snapshot checks ahead of Arena's job inspection/reconciliation, preventing
a blocked read from rewriting the held job manifest. It extends activity digest
filtering (`e7958c1`), generic job quarantine (`73e008e`), and source-read
filtering (`d38f517`). The focused quarantine fixtures pass and verify source,
snapshot, and job manifest bytes remain unchanged.
The source permission gate from `9d52b23` remains
BLOCKED; the read quarantine does not resolve source terms. Code commit
`03dbc92` propagates exact denomination identity through quotes, books, fees,
trades, candidate legs and capital, independent audit, replay, and
venue-separated virtual funding. The full Python Frontier suite passed 153
tests and the local production build completed before this policy change.
At the `03dbc92` checkpoint, versions were FrontierMarket v3,
BookSnapshot v2, TradeObservation v3, OpportunityCandidate v2, economic model
v7, independent audit v4, replay v7, Polymarket adapter v6, Kalshi adapter v15,
Kalshi fee metadata schema v2, Kalshi fee-sensitivity schemas v2, and Kraken
Spot adapter v3. The Frontier mission remains incomplete: verified
public equivalence, broader capital and settlement costs, source workers,
full-universe research, live source permissions, and deployment gates remain
open.

**Prior checkpoint summary:** isolated engine/API/UI, immutable relationship
review, schema-v6 indexed bounded graph neighborhoods with UI scan-quality
status, hash-verified public book/trade capture, exact fixture-verified
multi-outcome coverage, a separate candidate arithmetic audit, and a separate
source-reported Kalshi MVE settlement arithmetic audit. The newest economic-model
v4 checkpoint added exact bounded full-or-no-fill stress across up to 16 legs;
independent audit v2 recomputed the sensitivity, and replay v5 pinned it into run
output. Replay v6 overlaid exact immutable store record IDs into store-backed
market/book provenance, manifests, candidate legs, and Arena snapshots; direct
in-memory replay retains adapter-derived IDs. This lineage change needs no
schema migration. Centered graph pagination now covers one-hop keysets and
two-/three-hop deterministic breadth-first pages over a revision-pinned,
500-row result window; wide layers are split into bounded 200-market queries.
The supported Polymarket fee shape now has
nonzero-fixture and live zero-fee evidence coverage; timeout and truncated-stream
failure tests pass. Centered one-hop graph neighborhoods now support append-only
revision-bound keyset pagination with stale-cursor rejection. Polymarket v2
cursor trade pages now preserve token/outcome identifiers, have a bounded
operator-triggered API/UI continuation flow, and one live first page has been
hash-verified through an isolated temporary store. One live continuation page
also passed through the isolated API route, adding ten disjoint trades with
hash-verified temporary-store read-back. A further page was available but not
requested. Kalshi now has a bounded event/series fee-metadata capability and
dashboard capture. One fresh public market plus its event/series parameters
returned HTTP 200 and passed temporary-store raw and row hash verification; the
canonical fee cost remains unknown and unused by economics.
Kalshi also now has a one-page ticker-filtered public trade operation with a
cursor bound to the saved ticker and page size. Its live API page was HTTP 200,
empty, and terminal; trade-row normalization remains fixture-verified only.
The saved Kalshi event/series fee evidence drives local one-fill and bounded
one-order quadratic taker-fee sensitivities for two documented fee types and
both balance-precision cases. The order calculation accepts up to 32 manual fills
for one recorded native instrument and one buy/sell side, and models the
documented per-fill fee rounding, order accumulator, and capped rebates. Manual
price/size inputs are not quotes; the calculator does not change the unknown
canonical fee schedule or candidate economics. An offline derived one-fill
example is hash-pinned. Replay v5 includes the one-sided-fill sensitivity
and retains effective state/instrument mappings and proposal limits in each
replay identity. A bounded paired replay compares two named scenarios over
identical saved inputs, with an evidence digest and atomic persistence of two
run records plus the comparison. The Mission Control workbench can inspect the
paired comparisons and candidate fill stress. Validation is fixture/local-store
only; captured markets do not form a verified cross-venue pair or establish fill
behavior.
Kalshi adapter v4 now preserves typed, bounded MVE selected components
(native event/market identifiers and YES/NO side) from the source response; the
market inspector displays these identifiers with the explicit unresolved
payoff/rules boundary. A preserved 17-component MVE listing was replayed
offline through the API and store. Its primary rules were empty and secondary
text was only a general disclaimer, so its combo economics remain unsupported.
The independent cross-venue audit now classifies malformed two-leg candidates
that repeat one market as incomplete evidence instead of raising an uncaught
exception. The newest 2026-10-27 checkpoint adds a bounded event-group
capability for Polymarket and Kalshi, parent-event/outcome metadata, and a
conservative event-context relationship hypothesis path. A preserved pair of
genuine public event responses produces one Democratic House-control text
hypothesis in offline adapter replay; the independent same-payoff verifier
rejects it because payoff, timing, and resolution equivalence remain
unestablished. A follow-up API fixture now passes both saved public event bodies
through adapters, routes, store, and matcher; relationship evidence IDs resolve
to the exact stored captures. Matcher v4 also blocks explicit parent/child year
conflicts and cross-venue title-year mismatches. The capture contains metadata
only and no prices or books.
Frontier paired replay is also registered as a bounded Arena job over
content-addressed local snapshots, with API submission, history/result reads,
and an explicit Mission Control action. Two controlled fixture jobs passed the
normal host-wide gate and completed under the systemd supervisor. The latest
job also persisted bounded process CPU/RSS measurements and exposes them in
Mission Control. No live market relation was in either job.
The newest Kalshi adapter capability adds an explicitly requested, single-page
multivariate-event lookup, typed `MarketGroup` persistence, and a Mission
Control filter control. The October 27 public response returned one event and a
cursor but omitted nested markets; the evidence is replayed as an omitted member
list, not an empty set. Explicit `null` nested data fails closed. This adds no
component payout or economic-equivalence claim. Adapter v8 also handles the
documented event-detail response shape with a top-level empty market array; the
preserved same-event response replays as zero children without implying
venue-wide absence. Adapter v10 adds a one-market detail request bound to a
selected child in saved MVE metadata, checks parent ticker/event identity, and
persists source rules. A captured closed child includes fair-price fallback
conditions, so its simple binary payoff and the parent combo payoff remain
unverified. Adapter v11 also preserves the optional Kalshi
`yes_settlement_value_dollars` field as a bounded exact Decimal, carries it as
source evidence, and displays it in Mission Control. The documented field is
not interpreted as combo payout. The preserved live child capture omitted it,
so the value path is fixture-only.
The latest UI checkpoint (`9d7b599516ca70895525c701543c507054bcfbe6`) adds a
client-only, exact-decimal virtual balance comparison in candidate detail. It
keeps balances separate per venue and leaves unknown fees unresolved. Eight
Frontier component tests and one focused browser test pass, along with frontend
typecheck, ESLint, and Prettier. A production build after this UI change was
stopped under rising memory PSI and remains unverified. Comprehensive capital
transfer, collateral, FX, and settlement-duration modeling remains incomplete.
Follow-up review commit `cca4038` closes a partial-currency metadata gap by
requiring every leg in a venue to declare the same quote currency. Its
currency-completeness regression is now covered by the rerun eight-test
Frontier component suite and web TypeScript typecheck. The focused browser case
predates this correction and was not rerun. The production build remains
unverified after it was stopped under rising memory PSI.

The latest economics review closed a unit-valuation gap: a verified payoff is
now rejected when payout currency and settlement asset differ, or when the
market-level settlement asset disagrees with its payoff. Binary and
multi-outcome candidate generation and the independent audit each fail closed
without a valuation bridge. The USD/USDC regression exercises a rejected
relationship, a forged-verified-edge attempt, candidate generation, independent
re-audit, and same-market multi-outcome coverage.

The latest API review also found that the generic source probe and the
Polymarket v2 page route drained raw captures before lineage checks, then lost
those captures on mismatch. Both routes now preserve unpersisted captures as
diagnostics and remove already persisted captures from the pending set, avoiding
duplicate failure records after a later book/trade error.
The focused USD/USDC economics selection passed 6 tests; the API capture
selection passed 4 tests with 31 unrelated API tests deselected. Ruff check and
formatting passed. A combined API/adapter/economics run later passed 99 tests.
The full Frontier/Arena and repository suites remain unrun. Targeted mypy
reported errors in four unmodified dependency modules and none in its six
explicit Frontier/API targets. The production build remains unverified.
Remaining acceptance work is substantial.
**Branch:** `codex/frontier-20261026`
**Worktree:** `/home/charlie/midas-frontier`
**Baseline:** `11d32a0693b25c290fd273f23e40cf7b5950d95d` (`codex/veritas-v6-integration-20261026`)
**Mode:** public read-only market research and virtual analysis. No trading credentials, wallet, deposits, withdrawals, order submission, production deployment, Reality restart, campaign mutation, or Atlas work.

## Baseline and preservation

- `/home/charlie/midas` was on `main` at `55601b9` with unrelated dirty work. It was not changed.
- `/home/charlie/midas-veritas-v6-integration-20261026` was clean at `11d32a0` and provided the integration baseline with Veritas V6 and Research Readiness.
- Inspected worktree heads included Reality `4f5cb568`, Veritas `3b102928`, Reality reliability `4278b5b5`, and the V6 integration baseline. The Reality reliability tree had unrelated dirty operational/evidence work and was not changed.
- `/home/charlie/midas-frontier` is a separate linked worktree on `codex/frontier-20261026`. Frontier uses its own store root and test roots.
- The mission-start handoff contained a dated low-headroom Reality/API sample. It was treated as a safety constraint, not as a capacity allowance. No Frontier process was attached to a protected service, and no production services or service configuration were changed.
- The initial ledger’s “active transient Veritas scope” statement was an unverified current-state claim. This ledger supersedes it; no campaign or scope status is inferred from it.

## Baseline architecture findings

- Legacy `Market`, `Instrument`, `Book`, and `Fee` models are Polymarket/CTF-oriented.
- `packages/midas/market_data/polymarket.py`, CTF checks, existing economics, Reality recording and Veritas V6 are reusable references, but do not themselves define exchange-neutral semantics.
- Existing recording/replay is single-source and strategy-specific. Frontier therefore uses separate models, SQLite evidence and deterministic replay.
- The React SPA and existing Mission Control styles support a native lazy-loaded Frontier page.

## Implemented checkpoints

| Commit | Scope |
| --- | --- |
| `c17e187` | Started isolated mission ledger on the verified baseline. |
| `0f8e1d6` | Canonical contracts, capability registry, bounded GET transport, Polymarket/Kalshi/Kraken Spot adapters, relationship proposals/verifier, bounded Decimal economics, append-only store, deterministic replay, fixtures and tests. |
| `3a086c3` | Read-only Frontier API routes, separately gated source probes, app registration and offline API regression assertions. |
| `38d43be` | Native Mission Control workspace, responsive styles, unit test and isolated browser test. |
| `c9f4185` | Pair-metadata market query/replay fix, regression test, and bounded live adapter/API/store validation with preserved, hash-checked raw and normalized records. |
| `673c49a` | Bounded accessible node-link graph and selected-edge evidence interaction with mobile and desktop browser coverage. |
| `b94a3fc` | Explicit unknown-fee capital assumptions and bumped economic model version. |
| `5a2d61f` | Append-only relationship review/revision records, strict review API/UI, latest-state replay, additive SQLite schema migration, and revocation tests. |
| `084d860` | Bounded 1–3 hop graph query and center/depth UI, live listing-plus-book capture for all three sources, and tamper detection on observation, relationship, review-lineage and replay reads. |
| `3fe24dd` | Bounded API trade capture/read-back, hash-preserving dashboard table, one-trade Polymarket route contract, and live listing/book/trade captures for all three venues. |
| `99269f3` | Engineering report, Frontier architecture, Mission Control and development documentation, root README/configuration, and updated trade-capture evidence references. |
| `5e87d18` | Exact bounded same-market multi-outcome all-long coverage, fee-expiry validation, Decimal bounds, deterministic replay and API/UI details, with adversarial controlled fixtures. |
| `7243f84` | Updated engineering report, Frontier architecture, MIDAS architecture/development docs and README for the new bounded family and its fixture-only status. |
| `d8d70a4` | Added multi-outcome bounds and non-vacuous replay regression coverage for non-identity outcome mappings and reversed input order. |
| `ae7c308` | Added independent replay arithmetic audit, candidate audit hashes and dispositions, UI/readiness details, and fixed canonical relationship-mapping order exposed by the regression. |
| `480a322` | Updated engineering report, Frontier architecture, MIDAS architecture/development docs and README for the independent candidate audit. |
| `53c38d7` | Persisted raw responses and typed diagnostics when a decoded probe response fails normalization; included observation IDs in API errors and tested degradation, source isolation, and recovery. |
| `64dc167` | Documented the independent arithmetic audit, source-failure evidence path, latest focused verification, and the current host's test interpreter path. |
| `e8019d8` | Preserved complete bounded invalid-JSON, non-2xx, and invalid-UTF8 response bytes with verified hashes; added API evidence IDs and tests. |
| `59bf640` | Updated the engineering report, architecture, and development documentation for complete bounded transport-failure evidence and latest measurements. |
| `294cc6d` | Added a deterministic test for the two-retry cap, final HTTP 503 evidence, and request accounting. |
| `dbdd7c7` | Refreshed the engineering report for capped retry tests and the latest focused test/resource measurements. |
| `d389c24` | Added schema-v5 left/right relationship endpoint indexes, bounded adjacency queries, scan accounting, a v4 additive migration, and query-plan/API/storage regression tests. |
| `872466e` | Surfaced relationship scan counts and incomplete-neighborhood status in Mission Control; added UI regression coverage and refreshed the isolated Frontier browser fixture. |
| `cbd6ded` | Updated Frontier architecture, development guidance, and engineering report for indexed adjacency, schema v5, latest tests, and remaining graph-scale limits. |
| `aa2a001` | Added supported Polymarket fee-shape assertions and fail-closed exponent coverage; added bounded timeout retry and truncated-stream transport tests. |
| `89eff8b` | Added bounded relationship keyset pages, graph revision checks over market metadata observations, relationships and reviews, plus stale-cursor and 501-edge regressions. |
| `711a563` | Added Mission Control centered-neighborhood page controls, cursor restart state, and desktop/mobile UI coverage. |
| `67f79cd` | Added Polymarket v2 cursor pages, schema-v2 outcome-token preservation, condition/page-size-bound local cursors, bounded persistence/read-back, and adversarial page/cursor tests. |
| `7c6cc21` | Added capability/config-gated Mission Control first/next trade-page controls, outcome-token display, and unit plus desktop/mobile continuation coverage. |
| `e661e06` | Preserved direct first-page and API-route continuation captures, verified their hashes, and refreshed architecture, development, README, and engineering-report handoffs. |
| `a6bcf60` | Added Kalshi cursor-paginated public trade pages, a ticker/page-size-bound API cursor, raw/normalized persistence, a source-neutral Polymarket/Kalshi trade panel, contract/API/UI tests, and one live hash-verified empty-page capture. |
| `225dc8d` | Added a saved-evidence-bound Kalshi one-fill fee sensitivity API and UI, Decimal calculation tests, an offline derived artifact, and API/UI regressions. Candidate economics remains unchanged. |
| `127176b` | Added a regression against Kalshi's documented one-fill rounding example and clarified why the adapter still does not advertise a candidate fee schedule. |
| `1e3d30a` | Added paired deterministic replay, schema-v6 comparison storage, mapping/proposal-limit-aware replay-v4 identities, bounded API/UI, and atomicity, integrity, adversarial, and browser coverage. |
| `5af50b9` | Added analytic full-or-no-fill stress for supported candidates, an independent audit recomputation, replay-v5 result pinning, Mission Control leg-pattern details, and exhaustive three-leg differential/unknown-fee tests. |
| `6fa3696` | Integrated content-addressed Frontier paired-replay snapshots with a bounded offline Arena job, result-integrity API, explicit Mission Control submission/history, and fixture/API/UI coverage. At this implementation checkpoint no worker had yet been admitted. |
| `cf6bade` | Added the resource-admission-denial regression proving snapshot retention and no job creation. |
| `886e130` | Made Arena replay readiness evidence-driven, validated completed artifact/runtime linkage with a bounded scan, and tested valid and corrupt result states. |
| `109df84` | Added bounded worker CPU/RSS capture, safe API projection, and Mission Control display; verified with two supervised fixture replays. |
| `fba28df` | Made the API measurement projection type-safe without exposing malformed, non-finite, or out-of-range values. |
| `2628792` | Fixed optional systemd unit-ID and sorted-path type narrowing in the Arena API; focused API/job mypy now passes. |
| `c9e3be6` | Added saved-evidence-bound, native-instrument-bound Kalshi one-order taker fee sensitivity with order-level rounding/rebates, exact Decimal outputs, API validation, and a Mission Control fill editor. |
| `a087cb2` | Added API-boundary coverage for partial Kalshi event/series failure, raw evidence immutability, degraded health, and subsequent recovery. |
| `b84dac2` | Normalized bounded Kalshi MVE selected component identifiers and sides, persisted the captured response through the API/store path, displayed components in Mission Control, and added malformed-input, persistence, component, and browser regressions. |
| `415f3d4` | Made the independent cross-venue audit fail closed when a two-leg candidate does not contain one leg per selected market; added a malformed-candidate regression. |
| `b4cfcbe` | Added bounded public event-group normalization for Polymarket/Kalshi, preserved a direct cross-venue event capture, exposed group context in Mission Control, and linked API relationship evidence to exact stored observation records. |
| `b640bd2` | Updated architecture, development, current-state, and engineering handoffs for the captured event-group evidence, API traceability, and current verification. |
| `29cb909` | Bumped the deterministic relationship matcher to v4 and blocked title/parent-context hypotheses with contradictory within-market or cross-market explicit years. |
| `38ad1fa` | Introduced replay v6 and preserves exact store observation record IDs in API-loaded models, replay manifests, candidate evidence, paired replay, and Arena snapshots; added lineage integration regressions. |
| `5c14049` | Added revision-bound centered two-/three-hop BFS pagination, deterministic 200-ID frontier chunking within the 500-row scan budget, Mission Control continuation controls, cursor/revision tests, and a browser test definition. Browser execution remains pending at the measured host-pressure checkpoint. |
| `58cb6c7` | Added capability-gated one-page Kalshi multivariate-event discovery, typed group membership state, fail-closed nested metadata validation, API/store persistence, Mission Control capture and raw-evidence inspection, a real omitted-nested-market capture, and adapter/API/UI/browser regressions. |
| `001b103` | Corrected Kalshi event-detail normalization for a documented top-level empty market array; preserved the one-request source response, original v7 normalization failure, v8 offline replay, and hash-verified replay-store row. |
| `a40d2ee` | Added adapter v9 single-event `tickers` filtering with returned-event identity checks, Mission Control support, exact saved-response API replay, mismatch rejection, and an offline snapshot-row hash reconciliation. |
| `98fbf3a` | Updated README, development/current-state, architecture, evidence README, engineering report and mission ledger for the v9 event filter, genuine response, digest reconciliation and current verification. |
| `4193ddb` | Updated the existing Frontier Playwright scenario to use the single-event `event_ticker` filter, assert its request payload, and inspect the returned event. Formatting/lint and test enumeration pass; the browser was not run at host pressure. |
| `47664ad` | Documented the unresolved distinction between Kalshi's dated `KXMVE` fee-schedule row and the captured `KXMVECROSSCATEGORY` event/series metadata; no economics changed. |
| `3164d6f` | Added Kalshi adapter v10 market detail for a saved-parent-selected MVE child, persisted raw/normalized evidence, and exposed component-rule inspection in Mission Control. A one-request capture, API mismatch/unreferenced-ticker tests, and UI coverage are included. |
| `ee28bab` | Added a storage regression proving captured `market_metadata` changes the graph revision while book/trade observations do not. |
| `043da75` | Documented the Kalshi adapter v10 capture operation, hash-pinned public evidence, limitations, and focused verification. |
| `756ff89` | Added matcher v5 source-component reference hypotheses, exact child ticker/event validation, two-source-record provenance, deterministic prioritization, API/UI-graph response coverage, economic non-equivalence rejection, and an offline replay using the preserved Kalshi parent and child captures. |
| `74d9a76` | Clarified that exact event-ID matching is required only when the selected-component source metadata supplies an event ID. |
| `8a3e25c` | Bumped the Kalshi adapter to v12; added bounded parent and selected-leg settlement values, a saved-evidence-only arithmetic audit, API/Mission Control inspection with official rule/schema links, and fixture/API/UI/browser regressions. The result checks source-reported arithmetic only and does not alter candidate economics. |
| `e950b9c` | Bumped the Kalshi adapter to v15; added fee-override resolution states, blocked sensitivities for partial/unreported overrides, kept schema-v1 metadata readable but unresolved, surfaced state in Mission Control, and added adapter/API/economics/UI regressions. No candidate economics changed. |

## Kalshi single-event MVE ticker filter checkpoint (2026-10-27)

- Adapter v9, API and Mission Control now support exactly one event ticker in
  addition to the existing series or collection filter. The request uses the
  documented `tickers` query parameter and validates that the response includes
  the requested event. This is one bounded page with no cursor follow or
  multi-event ticker list.
- A genuine public unauthenticated GET through the isolated API returned HTTP
  200, one matching event, no cursor, and no nested market list. The normalized
  group is marked `omitted`, with zero child markets. Raw body SHA-256 is
  `3e2372de6143c0c8f37b3e77265a210596bf3c414fa33d19ee4028b1d2d3a7bb`; replay
  of the preserved raw/normalized snapshot into a fresh temporary store
  verifies row SHA-256
  `e6dcb76b2e18316866c078fd4778c2dff93891132e8b92104e3385c08d1271bd`. The
  original capture-time digest
  `cea5ea38a3ffad129fa2baedf3520b9bae71e8d4919521e140f46467baf57d50` remains
  preserved but is unreconciled because it does not match the artifact payload.
  The request envelope, replay hash and quality limits are preserved in
  `data/frontier/live-probes/2026-10-27-kalshi-mve-ticker-filter-r1.json`.
- The harness raised `RuntimeError: Event loop is closed during AsyncClient
  cleanup after TestClient shutdown` after capture and store read-back. The
  artifact records that condition and no source request was repeated. A
  deterministic API regression replays the saved raw bytes.
- Adapter/API MVE selections passed **13 tests, 49 deselected** in 2.03 seconds;
  `/usr/bin/time -v` measured 2.49 seconds wall, 1.36 seconds user CPU, 78,360
  KiB peak RSS, and zero swaps. One existing Starlette/httpx TestClient
  deprecation warning remains. The frontend Vitest run passed **40 tests across
  7 files**, and TypeScript typecheck, targeted ESLint/Prettier, Python
  Ruff/format, and strict mypy for the three changed Python modules with
  imported-module diagnostics suppressed passed. Unfiltered strict mypy reports
  14 errors in four unchanged Veritas/Arena modules, with none reported in the
  changed Frontier modules. `git diff --check` passes. Browser execution and
  production build remain deferred under measured host pressure.
- During this checkpoint the host had 9.6 GiB available RAM and 3.4 GiB swap in
  use; memory PSI `avg60` was 25.85% (`some`) and 22.72% (`full`), although
  `avg10` had eased. No browser/build workload or persistent service was
  started.
- The response confirms the one-event filter is wired to the public endpoint.
  It yields no child-market, combo-payoff, settlement-equivalence, synchronized
  price, venue-wide coverage or profitability evidence.

## Kalshi multivariate event discovery checkpoint (2026-10-27)

- Kalshi adapter v7 declares a separately gated `MULTIVARIATE_EVENT_DISCOVERY`
  capability. One request accepts exactly one series or collection ticker,
  requests `limit=1` with nested markets, validates event and child IDs, caps
  nested members, and retains but does not follow the source cursor. A
  `MarketGroup` records event metadata and distinguishes included, explicit
  empty, and source-omitted member lists. An explicit `null` is rejected as
  malformed. The API binds the captured URL/filter and all normalized records
  to one raw response before append-only persistence.
- Genuine source outcome: three single-GET probe attempts occurred; two were
  not preserved because the temporary probe harness failed after response
  receipt and are excluded from evidence. The retained attempt returned HTTP
  200, one event plus a nonempty cursor, but no nested `markets` field despite
  the requested flag. Its original v6 normalization failure is preserved as a
  typed source-failure record. The same raw body now replays through v7 as one
  event group with `member_list_state=omitted`, zero child markets, and no
  payoff/equivalence result. Artifact hashes and the exact limits are listed in
  the engineering report.
- The focused Python adapter/API suite passed **9 tests** in 1.61 seconds;
  `/usr/bin/time -v` measured 2.06 seconds wall, 1.25 seconds user CPU, 75,004
  KiB peak RSS, zero swaps, and zero socket messages. One existing
  Starlette/httpx TestClient deprecation warning remains. The focused MVE
  Mission Control test passed; frontend typecheck, targeted ESLint/Prettier,
  Ruff/format, strict mypy for four backend modules, `git diff --check`, and
  Playwright test enumeration passed. The three-case Frontier Playwright file
  includes the new MVE UI path, but the browser suite and production build were
  not run: at 11:51 UTC memory PSI was 32.86% some / 26.88% full (`avg10`), swap
  use was 3.4 GiB, and a separate bounded Veritas process remained active. No
  Frontier job or server was started.

## Kalshi event-detail empty-list parser correction (2026-10-27)

- A separate one-request public GET to the documented event-detail path for
  `KXMVECROSSCATEGORY-S2026ZZZB25KKPHBN3TFC` returned HTTP 200. The event object
  omitted its `markets` field while the response's top-level `markets` field
  was an explicit empty array. The v7 adapter rejected this shape as
  `INVALID_SCHEMA` and preserved the raw response plus typed failure in an
  isolated 8 MiB store.
- Adapter v8 now selects a top-level empty list when the event-level list is
  absent, while rejecting explicit `null` and non-list values. The exact saved
  body replays offline to an empty market tuple and a `MarketBatch`; a separate
  temporary-store row verifies under raw SHA-256
  `4dff6f7d770dff3a7564b5cf0558ff0c21862977d52a360a93f5b10f436afa83` and replay
  row SHA-256
  `c47a0e7827849c886c2c3e290d16035e1a87c26b602d028217c90f9b58c760aa`. The
  first capture's failure row remains preserved with SHA-256
  `3cd24ab39df2a766e6118aee59f48e9e8142880ec5d15f77340252981b5f434f`.
- Adapter/API multivariate cases plus the saved-detail replay passed **10
  tests**; the focused command measured 1.95 seconds wall and 75,056 KiB peak
  RSS with zero swaps. Strict mypy and Ruff passed for the changed adapter; the
  existing Starlette/httpx test-client deprecation warning remains. This source
  response is one empty event-detail list, not venue-wide market absence or
  payoff evidence. Full browser E2E and production build remain deferred under
  the existing host-pressure boundary.

## Latest checkpoint verification (2026-10-27)

- Centered multi-hop graph pagination: the complete `tests/frontier` plus
  `tests/arena/test_frontier_replay.py` suite passed **121 tests** in 27.54
  seconds; `/usr/bin/time -v` measured 28.35 seconds wall, 8.36 seconds user
  CPU, 0.94 seconds system CPU, 259,044 KiB peak RSS, zero swaps, and zero
  socket messages. The suite verifies deterministic BFS result/page ordering,
  cursor binding to center/depth/page size, stale graph rejection, and a
  201-market frontier split into bounded storage queries. The frontend passed
  **39 tests**, typecheck, lint, and format; Playwright lists all 11 browser
  cases including the updated depth-two interaction. A browser run and fresh
  production build were deferred: at `2026-10-27T11:28:57Z`, memory PSI `avg10`
  was 35.78% (`some`) and 32.22% (`full`), swap use was 3.4 GiB, and the active
  API cgroup used 527,319,040 of 1,610,612,736 bytes at `MemoryHigh`. This is a
  measured resource decision; no browser server or build process was started.
- Store-record lineage and replay-v6 integration: `tests/frontier` plus
  `tests/arena/test_frontier_replay.py` passed **118 tests** in 24.05 seconds;
  `/usr/bin/time -v` measured 24.89 seconds wall, 7.48 seconds user CPU,
  0.76 seconds system CPU, 254,696 KiB peak RSS, zero swaps, and zero socket
  messages. API-loaded Polymarket/Kalshi event rows retain exact store IDs
  through relationship evidence, manifests, direct and paired replay; a
  controlled saved book is also traceable through `/books`, replay, and its
  content-addressed Arena snapshot. Repeated replay output is deterministic.
  Existing schema and saved observations are unchanged. Ruff check/format and
  focused mypy passed. One upstream Starlette/httpx deprecation warning remains.
- Cross-venue event-group and evidence-link integration: `tests/frontier` plus
  `tests/arena/test_frontier_replay.py` passed **118 tests** in 34.97 seconds;
  `/usr/bin/time -v` measured 35.79 seconds wall, 7.40 seconds user CPU,
  252,996 KiB peak RSS, zero swaps, and zero socket messages. The combined
  Polymarket/Kalshi fixture test passes each preserved public event body through
  its adapter, config-gated API route, append-only store, and matcher-v4
  proposal route. A child market year mismatch is rejected even when the
  parent title omits a year; a parent/child year contradiction is also rejected.
  The resulting Democratic-market edge is still a
  `TEXT_CANDIDATE`/`HYPOTHESIS`; both relationship evidence IDs open the exact
  stored observation records. This is fixture replay of public captures, not a
  simultaneous live pair or economic validation. The suite passed **118 tests**
  in 22.95 seconds; `/usr/bin/time -v` measured 23.77 seconds wall, 7.38
  seconds user CPU, 254,240 KiB peak RSS, zero swaps, and zero socket messages.
  Ruff check/format and focused mypy for seven backend/API modules passed. One
  upstream Starlette/httpx
  `TestClient` deprecation warning remains.
- Independent-audit malformed-leg regression: the complete `tests/frontier`
  suite passed **104 tests** in 20.89 seconds pytest time; `/usr/bin/time -v`
  measured 21.70 seconds wall, 6.52 seconds user CPU, 247,952 KiB peak RSS,
  zero swaps, and zero socket messages. A duplicate-market-leg candidate now
  returns an `INCOMPLETE` audit and `INCOMPLETE EVIDENCE` classification rather
  than escaping as `StopIteration`. The focused regression passed after Ruff
  formatting in 0.28 seconds. Ruff check/format, focused mypy for the audit
  module, and `git diff --check` passed. One upstream Starlette/httpx
  deprecation warning remains.
- Kalshi MVE component normalization: the full `tests/frontier` suite passed
  **104 tests** in 20.96 seconds pytest time; `/usr/bin/time -v` measured 21.77
  seconds wall, 6.60 seconds user CPU, 247,084 KiB peak RSS, zero swaps, and
  zero socket messages. Fixture cases reject malformed sides, duplicate
  components, and over-bound lists. An isolated local API/store replay of the
  preserved October 26 public response verified the raw body/hash and all 17
  normalized component records. This used MockTransport over the saved bytes;
  no live request was made. One upstream Starlette/httpx deprecation warning
  remains.
- Frontend: **39 passed across 7 files**; TypeScript, ESLint, and Prettier
  passed. The production build passed with a 71.91 kB Frontier JavaScript chunk
  and 31.14 kB Frontier CSS; the existing 503.86 kB main and 544.41 kB Chart
  chunks still trigger Vite's warning. `/usr/bin/time -v` measured 12.51 seconds
  wall, 19.85 seconds user CPU, and 658,824 KiB peak RSS, with zero swaps and
  zero socket messages.
- Targeted Frontier Playwright: **3 passed** in 7.7 seconds with one worker and
  isolated temporary API/database/Arena/Frontier roots. The MVE market-detail
  fixture displays component IDs, side, and the unverified-payoff notice. No
  source probe or Arena job was launched.
- Ruff check/format, focused mypy for the Kalshi adapter and Frontier models,
  and `git diff --check` passed. No live MVE observation or payoff validation
  was performed; the preserved capture is dated structure evidence only.
- Kalshi metadata partial-failure regression: **99 passed** across the complete `tests/frontier` suite in 33.92 seconds pytest time; `/usr/bin/time -v` measured 34.73 seconds wall, 6.54 seconds user CPU, 248,244 KiB peak RSS, zero swaps, and zero socket messages. The API fixture returns an event response followed by HTTP 503 for its series response, verifies both hash-preserved diagnostic records and their immutability after recovery, observes Kalshi health degrade and recover, and checks the four bounded requests are unauthenticated GETs. A post-format targeted rerun passed in 1.79 seconds. Ruff check/format and `git diff --check` passed. One upstream Starlette/httpx deprecation warning remains. This is fixture evidence; live degraded-source behavior is still unverified.
- Frontend: **39 passed across 7 files**. TypeScript, ESLint, and Prettier passed. The production build passed with a 71.13 kB Frontier JavaScript chunk and 30.28 kB Frontier CSS; the existing 503.86 kB main and 544.41 kB Chart chunks still trigger Vite's warning. `/usr/bin/time -v` measured 5.66 seconds wall and 577,964 KiB peak RSS, with zero swaps and zero socket messages.
- Targeted Frontier Playwright: **3 passed** in 8.0 seconds with one worker and isolated temporary API/database/Arena/Frontier roots. The suite made no source-probe request and launched no Arena work. The new multi-fill fee form is covered by the component test; Playwright exercised the existing responsive workspace, replay history, and bounded relationship graph.
- Ruff check/format, focused import-following mypy for `apps/api/frontier.py`, `packages/midas/frontier/economics.py`, and `packages/midas/frontier/models.py`, and `git diff --check` passed. The full repository Python suite was not run.
- The October 26 Kalshi book capture is empty and names a different market from the October 27 fee-metadata capture. Therefore the multi-fill calculation is intentionally manual and was not represented as a book-priced or live fee result; account balance precision, maker/mixed-fill charges, FCM charges, later schedule changes, and candidate fee integration remain unresolved.
- One-sided fill stress and replay-v5 backend regression: **97 passed** across
  `tests/frontier`, adapter contract integration, and the offline API workflow.
  Pytest took 20.53 seconds; `/usr/bin/time -v` measured 21.36 seconds wall,
  5.69 seconds user CPU, 155,636 KiB peak RSS, zero swaps, and zero socket
  messages. Ruff check/format, mypy for 16 Frontier/API sources, and
  `git diff --check` passed. One upstream Starlette/httpx deprecation warning
  remains.
- Frontend regression: **38 passed across 7 files**; typecheck, ESLint,
  Prettier, and production build passed. Frontier's lazy chunk is 62.62 kB JS
  and 28.46 kB CSS; the existing main and Chart chunks still trigger Vite's
  size warning.
- Targeted Frontier Playwright: **2 passed** in 7.3 seconds with one worker,
  isolated temporary API/store roots, and no source-probe requests. It covers
  the responsive graph and saved-evidence workspace; it does not validate a live
  market pair or fill behavior.
- A broader single-worker E2E attempt ran ten cases: **8 passed and 2
  Laboratory launch checks were denied** by the host-wide Arena admission lock
  (`resource_admission_lock_busy`). The error context confirms no experiment was
  admitted or launched. The shared lock was not bypassed; Laboratory execution
  remains unverified under this host gate.
- A three-leg fixture independently exhaustively enumerates all eight
  full-or-no-fill patterns and matches the analytic minimum terminal P&L. The
  16-leg fixture validates the bounded pattern-space declaration of 65,536
  without enumerating all pattern/state pairs. This is not live execution
  evidence or a production throughput benchmark.
- No source probe, Reality service, Frontier background worker, or production
  service was started for this checkpoint. The complete repository Python suite
  was not run.

- Focused Python regression: **86 passed**, 18.05 seconds pytest time; 18.90
  seconds wall, 5.16 seconds user CPU, 151,728 KiB peak RSS, zero swaps and
  zero socket messages. The adapter and fee-sensitivity subset then passed 25
  tests in 1.40 seconds after a capability diagnostic assertion. One upstream
  Starlette/httpx deprecation warning.
- Frontend suite: **37 passed across 7 files**; typecheck, ESLint, Prettier and
  production build passed. Existing main and Chart bundles continue to emit the
  Vite size warning.
- Targeted Frontier browser cases: **2 passed**, 6.3 seconds, one worker, with
  isolated temporary API/store roots. The separate full-suite attempt had
  Laboratory failures under `host_memory_pressure`; no experiment launched.
- Candidate net economics remains unchanged. Derived Kalshi fee-sensitivity
  scenario inputs were manual, and no live book or quote was used.
- Next safe work: continue source-quality and fee-applicability review, then
  improve a distinct bounded scientific gap without running Laboratory jobs
  while host admission is under memory pressure. Keep deployment and Reality
  integration out of scope.

## Public source investigation

Official API documentation reviewed:

- [Kalshi public market-data quick start](https://docs.kalshi.com/getting_started/quick_start_market_data)
- [Kalshi Get Markets](https://docs.kalshi.com/api-reference/market/get-markets)
- [Kalshi Get Market Orderbook](https://docs.kalshi.com/api-reference/market/get-market-orderbook)
- [Kalshi Get Trades](https://docs.kalshi.com/api-reference/market/get-trades)
- [Kalshi Get Event](https://docs.kalshi.com/api-reference/events/get-event)
- [Kalshi Get Series](https://docs.kalshi.com/api-reference/market/get-series)
- [Kalshi fee information](https://help.kalshi.com/en/articles/13823805-fees)
- [Kalshi fee rounding](https://docs.kalshi.com/getting_started/fee_rounding)
- [Kraken Get Tradable Asset Pairs](https://docs.kraken.com/api-reference/market-data/get-tradable-asset-pairs)
- [Kraken Get Order Book](https://docs.kraken.com/api-reference/market-data/get-order-book)
- [Kraken Get OHLC Data](https://docs.kraken.com/api-reference/market-data/get-ohlc-data)
- [Polymarket market-data overview](https://docs.polymarket.com/market-data/overview)
- [Polymarket Data API v2 OpenAPI](https://data-api.polymarket.com/v2/docs)
- [Polymarket fees](https://docs.polymarket.com/trading/fees)

Genuine, unauthenticated GET response bodies are preserved under
`data/frontier/live-probes/`. The bounded captures contain five HTTP 200
responses: Kalshi market listing and a later book, Kraken AssetPairs and depth,
and Polymarket Gamma events. The sampled Kalshi order book was empty. The Kalshi
market carried MVE collection/selected-leg fields and is conservatively
classified as conditional with payoff unverified. The Polymarket “Kraken IPO”
event and Kraken XBT/USD spot are not equivalent payoffs. No verified
cross-venue pair, simultaneous market state, or economic opportunity was
established.

At `2026-10-26T20:41:18.904543Z`–`20:41:19.624016Z`, one actual public market
listing was requested through each Frontier API probe route using a temporary
8 MiB SQLite store, one request per venue, retries disabled, 65,536-byte response
caps, and no order-book calls. All three returned HTTP 200, normalized as
Polymarket `binary_event`, Kalshi `conditional_event`, and Kraken `spot_pair`,
were persisted, hash-verified on read-back, and returned by the market query.
The preserved capture envelope SHA-256 is
`3aaacd7b5d6f66d5cbc417f8ff14768bc3622378ada1a2ba7961cb705d58ab6a`. This check
also exposed and fixed the API’s omission of Kraken’s `instrument_metadata`
observations from market query and replay inputs.

At approximately `2026-10-26T21:10:40.775Z`–`21:10:43.974Z`, a second isolated
Frontier API validation made one public listing request and at most one public
book request for each venue, sequentially. It used an 8 MiB temporary store,
zero retries, an 8-second timeout, a 65,536-byte response cap, and a maximum of
two requests per source. All three API calls returned HTTP 200; each stored a
listing and one book. Polymarket's sampled book had 8 asks and 10 bids, Kraken
had 10 asks and 10 bids, and Kalshi's book was empty with no unified exchange
snapshot timestamp. Kraken reports per-level update times; Polymarket does not
establish matching-engine simultaneity. The captures were sequential, not a
synchronized multi-venue state. All six raw-body hashes and envelope hash
`101094b56c3dc620f8f66b423c92b5796db0a57852a5f7807aab50b2af956d60` were
recomputed successfully. No trades or fee endpoints were called.

At `2026-10-26T21:25:20.750899Z`–`21:25:27.005495Z`, a third isolated API
round trip requested one listing/metadata page, one book, and up to ten recent
trades per venue. Each adapter made three sequential HTTPS GET requests, all
HTTP 200. Polymarket and Kraken returned ten normalized trades; Kalshi returned
a valid empty public trade response. The API read-back matched those counts.
The 8 MiB temporary store was discarded after capture. All nine raw-body hashes
and envelope hash
`ca72a2aa2095ae02660f0ea23c0a6e94019929bd7d1e174b0446673637e04570` were
recomputed; largest body 68,758 bytes. These prints and sequential books do not
show synchronized quotes, executable fills, or fees. No fee endpoint was called.

At `2026-10-26T22:56:38.585296Z`–`22:56:38.728359Z`, the Frontier Polymarket
adapter made one unauthenticated `GET /v2/trades` against a condition already
present in recorded public metadata. It used a 10-row page, 65,536-byte response
cap, zero retries, and exactly one network request. HTTP 200 returned ten
normalized rows for one Yes outcome token with `has_more=true`. A temporary
8 MiB Frontier store read-back verified the raw and normalized observation
before the store was discarded. The raw SHA-256 is
`8923bbf6cff2262344ba7b14c923866bace1e46139bd790cedaa758195e6a174`, the
store row SHA-256 is
`65b172aff5ddbfba0c5e43d2952567028ec11a8ce210d44ea11b40732958bbda`, and the
pre-hash manifest SHA-256 is
`d970fce4cb0f4e48995b066ac1114d1c8c519be72eeaca54158cae65db664198`; the
serialized artifact SHA-256 is
`e5f400db64aeb000a688889eee4649a8e82ec061638dbe997e5b735dc423dc71`. This is
one public trade-print page, not depth or a cross-venue opportunity. Fixture
API tests also cover two-page persistence and read-back.

At `2026-10-26T23:02:48.888920Z`–`23:02:49.046817Z`, the isolated local API
accepted the first page's opaque cursor bound to the same condition and page
size, then made exactly one unauthenticated v2 GET with retries disabled and a
65,536-byte cap. It returned HTTP 200 and ten more trades on the same Yes token;
all ten transaction IDs were distinct from page one. The page and normalized
v2 batch were read back from a temporary 8 MiB store. Raw SHA-256:
`a2790da7bb4ea1faafe118562818b9de95b400b6f21d55b2bf3cb0697245fa32`; store-row
SHA-256:
`5197ee99f491e2970d3656ae394a5279a9a135335a7a60f45a377db4d1715e5a`; cursor
SHA-256:
`ccf6e9eaf39ba97a889068435cc8cb1283d99b40c1de81f81df9b56a5b320d98`; manifest
SHA-256:
`0d94b9c33555550cb2f72e895d6103bec1bf528561c7b9de246c27f0f81bb5ac`; artifact
SHA-256:
`d95c09da91bdf840a7b8fee693a32b14b5d47d8677307773c20ac8c26e7dc405`. The
source returned another continuation cursor, but no third page was requested.

At `2026-10-26T23:16:17.916305Z`–`23:16:18.408650Z` UTC (October 27 local
time), the isolated API made one fresh Kalshi listing GET and, for the saved
market, one event plus one series fee-metadata GET. It used zero retries,
65,536-byte response caps, an 8-second timeout, no book/trade requests, and a
temporary 8 MiB store. Each response returned HTTP 200; raw body and stored row
hashes passed read-back verification. The event had no fee override fields; the
series reported `quadratic_with_combo_maker_fees`, multiplier 1. Artifact:
`data/frontier/live-probes/2026-10-27-kalshi-public-fee-metadata.json`. Capture
manifest SHA-256:
`945610033e34816f057f054a58fa3672e7f9300d04791b0f76e7b48411fdd607`; serialized
artifact SHA-256:
`4a2e1ac8e2953314e89f26fa825142b551ce0a24512a14e3494df03b936ea53e`. The fee
metadata remains inspection evidence. Market fee costs remain unknown because
maker/taker applicability, fee changes, and account-specific rounding/rebates
are unresolved; no fee was calculated or treated as zero.

Capture records and source-specific limitations are in
[`data/frontier/live-probes/README.md`](../../data/frontier/live-probes/README.md).

## Verification checkpoint

- Backend focused regression after indexed adjacency: **56 passed** in 10.65 seconds pytest time; one upstream Starlette/httpx TestClient deprecation warning. `/usr/bin/time -v` measured 11.43 seconds wall, 3.97 seconds user CPU, 145,560 KiB peak RSS, and zero socket messages.
- Latest focused backend regression: **59 passed** in 11.11 seconds pytest time; one upstream Starlette/httpx TestClient deprecation warning. `/usr/bin/time -v` measured 11.89 seconds wall, 4.03 seconds user CPU, 145,936 KiB peak RSS, and zero socket messages. Added timeout retry and truncated-stream no-partial-evidence tests. Ruff and format checks passed for both changed test files.
- Current focused backend regression: **63 passed** in 15.59 seconds pytest time; one upstream Starlette/httpx TestClient deprecation warning. `/usr/bin/time -v` measured 16.38 seconds wall, 4.75 seconds user CPU, 148,684 KiB peak RSS, and zero socket messages. The 501-edge fixture test took 3.76 seconds (4.35 seconds total process wall, 1.12 seconds user CPU, 65,756 KiB RSS), including candidate construction, row insertion, and a 500-row page read; this is not an isolated query-latency benchmark.
- Latest v2 cursor/trade-schema verification: full `tests/frontier` passed **59 tests** in 14.52 seconds pytest time. `/usr/bin/time -v` measured 15.00 seconds wall, 3.25 seconds user CPU, 110,952 KiB peak RSS, zero socket messages, and no swaps; one existing Starlette/httpx deprecation warning remained. Ruff check/format passed, and mypy passed for 16 Frontier/API source files.
- Legacy adapter/API regression after additive trade fields: **10 passed** in 2.37 seconds pytest time / 3.09 seconds wall, 2.53 seconds user CPU, 121,420 KiB peak RSS, zero socket messages.
- Latest frontend regression: **36 passed across 7 files**; typecheck, lint and Prettier passed. The production build passed; Frontier lazy chunks are 51.60 kB JS and 25.46 kB CSS. Vite retains the existing >500 kB warning on the 503.86 kB main and 544.41 kB Chart chunks.
- Latest Frontier browser run: **2 passed** in 6.3 seconds with one worker, including explicit first/next v2 trade-page UI flow and desktop/mobile relationship graph interactions. UI source requests are fixture-backed; this was not a browser-to-live-source test.
- Current `tests/frontier` after Kalshi fee metadata integration: **63 passed** in 17.08 seconds pytest time; `/usr/bin/time -v` measured 17.63 seconds wall, 3.69 seconds user CPU, 110,004 KiB peak RSS, zero socket messages and zero swaps. One upstream Starlette/httpx TestClient deprecation warning remains.
- Latest bounded regression command: **77 passed** across `tests/frontier`, adapter contract integration, and the offline API persistence workflow in 17.75 seconds pytest time. `/usr/bin/time -v` measured 18.57 seconds wall, 4.99 seconds user CPU, 150,520 KiB peak RSS, zero socket messages, and zero swaps. One upstream Starlette/httpx deprecation warning remains.
- Current frontend suite: **37 passed across 7 files**; typecheck, ESLint and Prettier passed. Production build passed; Frontier chunks are 54.10 kB JS and 26.06 kB CSS. Existing 503.86 kB main and 544.41 kB Chart chunks still trigger Vite's size warning.
- Current Frontier browser file: **2 passed** with one worker after updating the source-neutral trade-market selector. The Polymarket and Kalshi page paths are fixture-backed; no live browser-to-source request was made.
- The first full 10-case Playwright attempt had one outdated Frontier selector and two Laboratory timeouts. After fixing the selector, a full single-worker browser run passed **10/10** in 23.4 seconds. It used isolated temporary API/storage roots and left no source probes enabled.
- Python Ruff check/format, mypy for 16 Frontier/API source files, and `git diff --check` passed after the Kalshi trade-page change.
- The live Kalshi trade-page capture used two unauthenticated GETs (one saved-market listing and one trade page), zero retries, 65,536-byte caps, and a temporary 8 MiB store. Both responses were HTTP 200 and raw/row hashes verified. The conditional market's page had zero trades and no cursor; this does not validate live row mapping or establish market availability.
- Ruff check/format, mypy for 16 Frontier/API files, and `git diff --check` passed.
- A direct Polymarket Data API v2 first-page capture and one continuation page through the local API each returned 10 rows/HTTP 200 in exactly one request, without retries, and verified raw plus normalized temporary-store read-back. The 20 native trade IDs are disjoint. The second page still advertised a next cursor; no third page was requested.
- Ruff check and format check: passed for the Frontier package and test files.
- Mypy: passed for 16 Frontier/API source files. A broader `mypy packages/midas/frontier apps/api` attempt reported 37 errors in eight unchanged Veritas/Arena/API files; none was in Frontier source.
- Frontend tests: **35 passed across 7 files** after adding incomplete-scan messaging coverage; typecheck, lint and Prettier check passed.
- Frontend production build: passed. Existing main and Chart chunks trigger Vite’s >500 kB warning. Frontier’s lazy chunks are 49.11 kB JS and 24.74 kB CSS.
- Frontier browser cases: **2 passed** in 6.5 seconds, including centered graph pagination, fixture-only review submission, multi-outcome candidate state, and audit details at desktop/mobile sizes using one worker and isolated roots; source probes remained disabled. In the broader 10-case E2E run, 8 passed and 2 existing Laboratory cases were denied at the shared Arena resource-admission lock (`resource_admission_lock_busy`); no experiments started and the lock was not bypassed.
- The complete Python repository suite was not run. After an initial browser run exposed a stale Frontier selector and two Laboratory timeouts, the selector was fixed and the full single-worker 10-case suite passed. No persistent service or long-running campaign was started.

Reproduction commands and environment boundaries are in
[`docs/DEVELOPMENT.md`](../DEVELOPMENT.md) and
[`FRONTIER_ARCHITECTURE.md`](FRONTIER_ARCHITECTURE.md).

## Arena replay integration checkpoint (2026-10-27)

- Added the `frontier_replay` Arena job kind using the existing mandatory host-
  wide admission lock. Snapshots pin normalized inputs, scenarios, timestamps,
  and code version by content identity. Bounds are 100 markets, 200 books, 500
  relationships, 8 MiB per snapshot/result, and 128 MiB / 1,000 snapshots.
- The worker reads only the pinned local snapshot, is restricted to 300 seconds,
  512 MiB, 50% CPU, nice 15, and idle I/O, and runs with IP address families
  disabled. The result API requires successful completion and validates the
  job record, snapshot digest, result digest, and comparison identity.
- Mission Control exposes explicit submit, bounded history, progress, hashes,
  and result inspection. Page load does not submit a job. Readiness is
  `LIVE_VALIDATION_PENDING` until a bounded scan finds a completed, hash-verified
  result and runtime record; it then reports `EVIDENCE_RECORDED`, or
  `REVIEW_REQUIRED` for invalid completion evidence. Resource sustainability
  remains `NOT_MEASURED` after two short identical fixture runs.
- The broad Arena/Frontier/API regression passed **130 tests** in 49.97 seconds
  wall, 31.65 seconds user CPU, and 535,504 KiB peak RSS, with zero swaps and
  zero socket messages. The eight-test Arena replay module passed in 1.81
  seconds. Afterward, snapshot submission and simulated resource denial passed
  **2 targeted tests**; denial returns 409, retains the pinned snapshot, makes
  no source request, and creates no job. One upstream Starlette/httpx test-client
  deprecation warning remains.
- The subsequent Frontier API module passed **20 tests** in 8.24 seconds. A
  completed fixture job with valid result/runtime evidence moves readiness to
  `EVIDENCE_RECORDED`; a corrupt result produces `REVIEW_REQUIRED`. The scan is
  capped at 100 job entries and 64 KiB per manifest; resource sustainability
  remains `NOT_MEASURED`.
- The first actual systemd-supervised job ran after normal host preflight passed. The
  preflight observed zero active Arena jobs, 4.59 GiB available memory, six
  available CPUs, load average 1.37, memory PSI 0.07% some / 0.06% full, I/O
  PSI 1.07% some / 0.81% full, and 146 GiB free disk. The controlled fixture
  completed with exit status 0 in 0.167 seconds and produced two candidates per
  arm. The Arena result API returned a hash-verified result and the Frontier
  readiness API reported `EVIDENCE_RECORDED`. No public-source call was made.
- Job evidence remains under
  `data/frontier-arena-validation-20261027-886e130/`. Snapshot ID
  `1448349f90cb486b84d945f34f1a2447a297f04a2fd33015627bd6f5f1a8b559`, snapshot
  file SHA-256
  `74f169b18a3b81eade1059a11309c9e3de3535074bc1c1eabd044739685b69ef`, result
  SHA-256
  `f147cc55ed467c2af16465f61894affd54d43eb2f31c0c0fa7a84b17f148e929`, and
  comparison ID
  `1dee0a8c22d97b38619cb244eeb98b6dbb3de5062e1ab593e4308ac9a68fbbe4` bind
  the first fixture output. It reported 2,431,645 bytes of Arena artifacts and
  28,764 bytes attributable to that job. Its manifest had no CPU/RSS counters;
  systemd's transient unit exposed neither `MemoryPeak` nor `CPUUsageNSec` after
  exit.
- The worker now records process CPU deltas and process peak RSS in its durable
  terminal manifest. A second read-only preflight passed the normal gate with
  no active jobs, 10.07 GiB available memory, six CPUs, load average 1.14, zero
  memory PSI, 0.2% I/O PSI some / 0.14% full, and 144.4 GiB free disk. Job
  `job-5484db9a63964f43a0e2c5d8` completed with exit 0 in 0.199392 seconds and
  again produced two candidates per arm. Its measured user CPU was 0.067554
  seconds, system CPU 0.010943 seconds, peak RSS 167,288,832 bytes (159.5 MiB),
  and job artifact growth 28,766 bytes, under a 512 MiB memory cap. The result
  artifact hash is
  `2c77cdfc91f7f86da87509f797a39acd8501513c0c30dc987ab85c40e8322db3`; the
  shared snapshot and comparison identities remain unchanged. Its manifest
  verified against the pinned snapshot and Arena result reference.
- Arena history exposes only the allowlisted CPU/RSS metrics; Mission Control
  displays elapsed time, user/system CPU, and process peak RSS, with a note that
  one sample is not a capacity claim. Resource sustainability remains
  `NOT_MEASURED`; the 512 MiB cap is not an observed peak or sustainability result.
- Frontend tests passed **39 across 7 files**; TypeScript, ESLint, Prettier, and
  production build passed. Frontier chunks are 67.76 kB JavaScript and 29.81
  kB CSS; existing main and Chart chunks still trigger Vite's bundle-size
  warning. Targeted Frontier Playwright passed **3 cases** in 7.5 seconds with
  one worker and isolated temporary roots; one confirms no automatic submission.
- After adding worker CPU/RSS projection to Arena history, the focused replay/API
  regression passed **29 tests** in 12.10 seconds and the Frontier component
  passed **7 tests**. TypeScript, ESLint, Prettier, and Ruff passed. The production
  build passed with a 68.90 kB Frontier JavaScript chunk and a 29.81 kB CSS
  chunk; existing main and Chart bundle-size warnings remain. The targeted
  Frontier browser suite passed **3 tests** in 8.5 seconds using one worker.
- Worker-profile regression coverage confirms Linux/macOS RSS unit conversion,
  nonnegative CPU deltas, safe filtering of malformed/out-of-range API values,
  and rendering with an explicit sustainability limit. `jobs.py` passed mypy at
  this checkpoint; the API typing follow-up is recorded below.
- At that earlier worker-profile checkpoint, checking `apps/api/arena.py`
  reported three pre-existing type errors. Commit `2628792` subsequently fixed
  the optional unit-ID and sorted-path typing; focused mypy now passes for the
  API and Arena job modules. The broader import-following run still reports 37
  issues across eight existing Veritas/Arena/API files. The full repository
  suite was not run.
- A previous broader E2E run recorded `resource_admission_lock_busy`; that lock
  was not bypassed. The later worker was admitted only after a read-only
  preflight and normal gate check. Its controlled fixture validates supervisor
  and artifact wiring, not live economics. No source probe, Reality service,
  Laboratory campaign, or production service was started.

The Arena job integration is `6fa3696`, the admission-denial regression is
`cf6bade`, and the readiness-state update is `886e130`. The integration report
and architecture handoff were documented in `f5c7129`.
The completed fixtures validate supervisor wiring. Preserve both records and
continue independent source-quality and economic-verification work. Two tiny
same-input runs do not change the resource sustainability gate.

## Kalshi selected-component market detail checkpoint (2026-10-27)

- Kalshi adapter v10 adds one public market-detail GET for a child ticker that
  must already be named by `selected_components` in the saved parent MVE
  record. The API rejects an unreferenced ticker before making a request,
  validates the returned ticker and event identity, and stores raw and
  normalized `market_metadata`. Market-list reads include the new observation
  kind and graph revisions change when component metadata arrives.
- Mission Control now offers “Capture component rules” from a saved selected
  leg and displays title, primary/secondary source rules, raw/observation
  hashes, and explicit payoff-unverified status. The action does not request a
  book or price.
- One genuine unauthenticated GET returned the first selected child of the
  saved combo. The response matched the selected ticker and event. Raw
  SHA-256 `0f1c3cd42cac5202ca5a3012d58cb8d9631bf39cce313c738bb0448140271eda`
  and temporary-store row SHA-256
  `a2e7ae0c08436155a0bdc80e07f16d6b882eaf9706617994be135b668ec5897a` are in
  `data/frontier/live-probes/2026-10-27-kalshi-mve-component-market-r1.json`.
  This child was closed; its rules mention fair-price fallbacks for
  inactive/non-playing and postponed games. No child book/price or verified
  binary payout is present, and parent combo payoff remains unknown.
- Regression state at checkpoint: `tests/frontier` plus
  `tests/arena/test_frontier_replay.py` **136 passed**; frontend **40 passed**
  across seven files; three isolated Frontier Playwright cases passed. TypeScript,
  targeted ESLint/Prettier, Ruff, and production build passed. The full Python
  repository suite has not been run. After the full regression, the focused
  graph-revision storage test passed **1 test** in 0.53 seconds. Strict mypy
  passed for the three modified Python modules and `git diff --check` passed.
  The full engineering report holds prior dated history and current build
  sizes/warnings.
- No persistent service, source worker, Reality process, or long-running
  campaign was started. This remains development-branch work, not deployed.

## Recorded MVE component relationship checkpoint (2026-10-27)

- Relationship matcher v5 adds `source_component_reference`. It emits only when
  a same-venue child is in the bounded recorded market window, its native market
  ticker exactly matches a parent's selected-component reference, and the
  referenced event ID matches when present. The edge preserves both source
  observation IDs and selected side, remains `HYPOTHESIS`, and says explicitly
  that payoff and settlement equivalence are not established. Source edges are
  prioritized within the bounded proposal limit.
- The Polymarket/Kalshi economic generators still accept only supported
  verified payoff constructions; a source-component edge produces
  `PRICE DISCREPANCY ONLY` if passed to binary candidate evaluation.
- An offline replay of the saved Kalshi MVE parent listing and the separately
  captured first child detail passed through the current adapter/matcher and
  produced one exact source-component hypothesis carrying both preserved
  observation IDs. This is a same-venue source linkage, not an equivalent
  cross-venue contract or arbitrage finding.
- Verification after matcher v5: full Frontier/Arena replay suite **137
  passed** in 30.04 seconds; relationship/API modules **49 passed**; the
  saved-source replay test **1 passed**. Strict mypy for the changed matcher/API
  modules, Ruff check/format, and `git diff --check` passed. No source GET or
  browser workload was repeated for this offline graph change.

## Kalshi selected-leg settlement-value metadata checkpoint (2026-10-27)

- Commit `7ad28c5` bumps the Kalshi adapter to v11 and adds optional
  `yes_settlement_value_dollars` to each typed MVE selected component. It is
  parsed as a finite, nonnegative Decimal within model precision bounds, remains
  unknown when omitted, is included in relationship evidence, and is shown
  under the source field's label in the component inspector. Invalid, negative,
  and over-precision values produce a typed adapter failure.
- The official [Get Multivariate Events schema](https://docs.kalshi.com/api-reference/events/get-multivariate-events)
  documents the field but the reviewed schema does not establish that it is the
  containing MVE's payout. No payout inference was added. The saved child
  capture does not have this field; current value-specific verification is
  documentation-shaped fixture coverage only.
- The focused MVE adapter cases passed **8 tests**. Before adding the
  excessive-precision regression, the full Frontier/Arena suite passed **140
  tests**. Strict mypy passed for the four changed Python modules; Ruff,
  `git diff --check`, TypeScript, ESLint, Prettier, the 40-test frontend suite,
  and production build passed. Browser E2E and another full Python run were not
  started under memory PSI of 38.49% `some` / 33.50% `full` (`avg10`) and 3.45
  GiB swap use. The earlier full run measured 266,896 KiB peak RSS.
- Follow-up commit `d6d4540` adds a schema-shaped fixture variant with value
  `0.3750` and proves API serialization plus normalized market and observation
  store read-back (**1 targeted test passed**). The original live artifact was
  not modified; this still is not live-field verification.
- No source request, production service, or deployment was involved. This is a
  bounded research change; overall Frontier remains incomplete.

## Kalshi MVE reported settlement arithmetic checkpoint (2026-10-27 13:01 UTC)

- Code commit `8a3e25c` bumps the Kalshi adapter to v12. It preserves the
  optional component `yes_settlement_value_dollars` as a bounded scalar and
  adds optional parent `settlement_value_dollars` and strict `is_provisional`
  normalization.
- The local-only
  `POST /api/frontier/economics/kalshi-mve-settlement-audit` endpoint loads only
  the bounded recorded Kalshi market window. It makes zero network calls and
  does not run candidate generation. For up to 64 selected legs it computes
  the source-reported position value (YES value for YES; one minus YES for NO),
  then their exact Decimal product. It compares that with the recorded parent
  value only when every input is present and the parent is settled and not
  marked provisional. Missing, non-final, mismatching, matching, and
  unsupported structures have distinct output states.
- This method follows Kalshi's public [combo settlement guidance](https://help.kalshi.com/en/articles/13823820-combos),
  [NO scalar rule](https://help.kalshi.com/en/articles/17515177-protected-nfl-player-markets),
  and [MVE field schema](https://docs.kalshi.com/api-reference/events/get-multivariate-events).
  A result is a source-reported arithmetic comparison. It does not verify child
  rules, outcome correctness, settlement authority, prices, timing, fills, or
  returns; it does not enter candidate economics. The response displays the
  stored observation ID and raw hash with explicit assumptions and direct
  source links.
- Positive and negative arithmetic paths are fixture-only. The preserved live
  child response lacks the necessary component values; there is no live parent
  or component settlement audit result. No public request or store rewrite was
  made.
- The full Frontier/Arena run passed **148 tests** before addition of the
  result's `rule_source_urls` field. With that field present, the focused
  adapter/economics/API selection passed **17 tests**. The full frontend suite
  passed **40 tests**; all **4** Frontier Playwright cases passed, including a
  fixture route that asserts no probe call. Production build, TypeScript,
  ESLint, Prettier, Ruff, and strict mypy passed. The full Python suite was not
  repeated: at 13:01 UTC host memory PSI `avg10` was 38.72% (`some`) / 32.96%
  (`full`), available RAM was 9.93 GB, and 3.46 GiB swap was in use. This is an
  admission decision for the final run, not a service-capacity conclusion.
  Reality, production services, and historical captures were left unchanged.

## Completion matrix

| Component | Status | Current evidence / remaining requirement |
| --- | --- | --- |
| Verified isolated baseline and worktree | COMPLETE AND VERIFIED | Separate branch from `11d32a0`; unrelated dirty trees preserved. |
| Adapter protocol, capability inventory, bounded GET transport | COMPLETE AND VERIFIED | Contract tests; all capabilities explicitly declared; Polymarket/Kalshi event groups supported, Kalshi MVE discovery explicitly supported, and Kraken MVE discovery explicitly unsupported; Kalshi price ranges are now normalized to exact-Decimal instrument constraints and are enforced conservatively by both candidate generation and audit; no startup request. |
| Kalshi MVE settlement metadata and arithmetic audit | PARTIALLY VERIFIED | Adapter v12 introduced bounded component YES settlement values and optional parent settlement/provisional fields; current Kalshi adapter v16 retains the behavior. A saved-evidence-only API/UI audit recomputes the selected component product for up to 64 legs and compares it with the parent value only for complete, final evidence; official rule/schema links and observation/raw hashes are shown. The full 148-test suite predates only the output source-link tuple; the final focused 17 tests and four browser cases include it. All positive and negative settlement arithmetic remains fixture-only; the preserved live child lacks values, no live audit result exists, and this method does not verify outcomes/rules or alter candidate economics. |
| Polymarket, Kalshi and Kraken Spot implementations | PARTIALLY VERIFIED | Fixture tests and bounded live listing/book/trade-to-store evidence exist. Current adapter versions are Polymarket v6, Kalshi v17, and Kraken Spot v3. Polymarket v2 first and continuation pages returned ten rows each. Kalshi cursor pages are implemented and row mapping is fixture-tested; a live page returned zero trades and no cursor, so live row normalization remains pending. Two genuine public event-group responses are hash-pinned and replayed through Polymarket/Kalshi adapters. Kalshi MVE listing responses omitted nested members; v10 captured a saved-parent-selected child and preserved its rules. The sole captured child is closed and includes fair-price fallback language, so child and combo payoffs remain unverified. Account fees and Kraken account fee applicability remain unknown. API fixtures cover source degradation and recovery; live degraded-source behavior remains unverified. |
| Canonical normalization and native evidence | PARTIALLY VERIFIED | Distinct event, conditional event and spot forms; FrontierMarket v4, BookSnapshot v2 and TradeObservation v3 preserve canonical denomination identities where supported; Kalshi `price_ranges` are normalized as bounded exact-Decimal intervals while raw native values remain auditable. Candidate generation and independent audit reject out-of-range, off-step, empty-declaration, and boundary quotes; endpoints are conservative because the official schema does not specify inclusion. Kalshi paginated batches retain schema v2 with nested trade schema v3. Quote, fee, trade, capital, and display codes are separate fields. Legacy v1/v2 rows without identity still load but remain unknown and economically incomplete. V2 Polymarket trades preserve token and outcome identity. October 27 event-group capture preserves parent-event title and child outcome text. Kalshi `MarketBatch` v2 stores typed MVE groups with `included`, `empty`, or `omitted` member state; detail responses with a documented top-level empty list replay to zero child markets. Other settlement/payoff semantics remain intentionally unverified. |
| Relationship matching, immutable review, indexed neighborhoods, and strict payoff verifier | PARTIALLY VERIFIED | Self-attributed review API/UI with stored source refs, append-only revisions, compare-and-set, latest-state replay, query-plan/migration tests, and 1–3 hop left/right indexed scans capped at 500 rows. Centered one-hop keyset and two-/three-hop breadth-first pages bind graph inputs and reject stale cursors; deterministic recomputation and 201-market frontier chunking are tested. Matcher v5 emits exact-ID MVE `source_component_reference` hypotheses only with a matching saved child ticker/event and preserves both observation IDs; the recorded parent/child pair replays offline through the current adapter and matcher. Matcher v4 year-conflict checks remain. The genuine House-control pair is text-only and strict payoff verification rejects same-payoff equivalence. Per-market payout currency must match its settlement asset, and the market-level settlement asset must match the payoff record; the USD/USDC regression passes. A focused depth-two browser test now passes; authenticated review and revision-history drill-down remain pending. |
| Economic candidate verifier and independent audit | PARTIALLY VERIFIED | Exact two-venue binary all-long coverage and same-market 3–16-state exhaustive one-hot coverage. Economic model v13 derives exact full/no-fill stress and bounded 0/25/50/75/100% per-leg partial-fill-grid stress for up to 16 legs, omitting intermediate quantities that violate instrument steps and recalculating supported fees at each modeled aggregate quantity. Independent audit v10 rederives both sensitivities, payout/cost, quote constraints, per-venue delay, fee expiry, pinned-book timing, source quality, and the Kalshi fee estimate. Fixture differentials enumerate all 125 combinations for three legs; a rounded Kalshi fee fixture confirms fees are recalculated rather than linearly scaled. The 16-leg full/no-fill bound remains 65,536 patterns; the partial-fill grid uses separable per-state minimization instead of expanding the Cartesian product. Unknown fees suppress net sensitivity; invalid quantities and audit tampering fail closed. Grid results do not estimate fill probabilities, continuous intermediate quantities, multiple-fill rounding, price paths, or hedge/unwind behavior. Timing and delay remain virtual sensitivity assumptions, not measured execution. Current adapter clock-uncertainty estimates are absent, no genuine eligible event is established, and there is no practical execution proof. |
| Kalshi candidate-fee estimate | PARTIALLY VERIFIED | Commit `3e85c8d` joins only complete raw/hash/path/identity-checked event/series metadata and requires metadata no later than quote time and at most 24 hours old at quote/replay. A supported one-fill formula uses conservative non-direct `$0.01` debit alignment; estimates cannot yield a verified mathematical inconsistency. Independent arithmetic and manifest fee-observation IDs pass fixture/API/replay checks. Account applicability, balance class, maker/mixed/multi-fill and FCM charges, later changes, live validation and source permission remain unresolved. |
| Bounded store and deterministic replay | COMPLETE AND VERIFIED | Storage schema v6 with additive v2/v3/v4/v5 migrations, immutable replay/comparison records, replay-v8 source lineage, denomination identities, and separate fee metadata observation IDs through manifests/candidate legs/Arena snapshots; direct replay retains adapter IDs. Test commit `f35677d` verifies a saved schema-v1 manifest lacking the new field remains readable and its JSON/hash is preserved. The 19-test storage/replay-comparison selection passed before that follow-up, and the changed legacy case passed separately. Replay-v5 output includes fill sensitivity and identity includes effective mappings/proposal limit; prior replay results and observations remain unchanged. |
| Paired scenario comparison | PARTIALLY VERIFIED | Direct local comparison and API/UI/browser tests pass. Two actual systemd-supervised fixture replays completed over the same pinned inputs and their result hashes verify. The latest run measured worker process CPU/RSS and exposes it in Mission Control. No genuine equivalent live market pair exists. |
| Frontier API and source configuration | COMPLETE AND VERIFIED | Local reads include hash-verified legacy and cursor-page batches. Polymarket and Kalshi page routes are capability/config/recorded-market gated, bounded to one page and retries, and bind cursors to market and size. Kalshi MVE discovery validates exactly one series/collection/event-ticker filter and does not follow its cursor. Component-detail fetches are bound pre-request to saved selected-leg metadata and post-response to saved market/event identity. Saved Kalshi fee metadata is joined to replay markets only after raw/hash/path/identity checks and remains excluded for held sources. Four focused API regressions verify raw market/book/trade capture retention after post-drain lineage failures, preserve a drained Polymarket v2 page, and ensure earlier successful listings are not duplicated. The Frontier readiness source-quality gate summarizes candidate timing audits from its latest three non-held replays; it does not change the review-required state or imply execution. The October 27 fail-closed regression verifies probe rejection and held-store quarantine even when arbitrary source-reference strings and probe flags are configured. |
| Kalshi/Kraken source-use controls and stored-evidence quarantine | COMPLETE AND VERIFIED | No validated permission loader exists; probe flags and arbitrary reference strings cannot enable either source. The source registry always carries a block reason, the readiness gate remains `BLOCKED`, probe routes return 409 without requests, and held observations and derived research stay filtered. The synthetic regression passes 4/4 and the full 219-test Frontier suite passes with the held-source runtime guard. This verifies local policy behavior only. |
| Kalshi/Kraken source permission and authorized live research | BLOCKED | The source terms review found the relevant permission/research-use status unresolved. No permission was requested or validated. Do not use preserved held captures for new research or enable live probes until a validated source-use decision and corresponding implementation are available. |
| Live adapter, API and store evidence | PARTIALLY VERIFIED | Three venue listing/book/trade captures, Polymarket v2 first/continuation pages with distinct IDs, a Kalshi empty cursor page, event-group responses and MVE endpoint responses have hash-pinned evidence. A single selected-child market-detail response is also hash/store verified and has matching saved-parent ticker/event IDs; it contains close lifecycle and native fair-price rule text but no price/book. Kalshi trade-row mapping remains fixture-only. Samples are asynchronous and establish no synchronized prices, complete history, child payout, combo payout, or execution. |
| Mission Control Frontier workspace | PARTIALLY VERIFIED | Native view includes Polymarket/Kalshi trade-page, event-group and one-page MVE controls; MVE can filter by series, collection or event ticker; saved selected-leg rules, recorded settlement arithmetic, official source links and provenance hashes can be inspected. Graph/review, depth-paged traversal, paired replay, one-sided fill stress, instrument-bound Kalshi order-fee sensitivity, Arena history/results, and virtual balances keyed by venue and canonical denomination are integrated. Replay run history now displays its separately pinned fee-metadata observation count; a focused fixture passes. The candidate audit panel exposes independently recomputed receipt skew, exchange timestamp skew, and the timing gate while marking older missing fields as not recorded. The prior Frontier/web/browser results remain dated evidence; current focused UI test, typecheck, targeted ESLint, and Prettier pass. No production build was run for this change. It is not deployed. |
| Laboratory/Arena research orchestration | PARTIALLY VERIFIED | Bounded Frontier Arena job type, snapshot, offline executor, API, worker CPU/RSS capture, and workspace history/result view are implemented and tested; two fixture jobs passed the host gate and completed under systemd. Resource sustainability and Laboratory campaign management remain incomplete. |
| Persistent source collection, streaming and broad historical replay | DEFERRED | No background worker or long-duration campaign. |
| Cross-venue FX, comprehensive capital and settlement costs | DEFERRED | Unknown costs remain unknown and block decisive net economics. |
| Production eligibility/deployment | DEFERRED | Separate safety, resource, schema, operations review and authorization required. |
| Positive economic result | NOT ESTABLISHED | No verified live equivalent exposure or economically eligible candidate. |

For the detailed architecture, limitations and complete 20-section acceptance
report, see [`FRONTIER_ENGINEERING_REPORT.md`](FRONTIER_ENGINEERING_REPORT.md).

## Blockers, risks, and next safe work

No defect blocks the implemented subset. The larger acceptance criteria remain
unfinished. The new audit is independent in calculation code only: it consumes
the same normalized evidence and cannot authenticate source truth. Review labels
and external assertion IDs are self-attributed and not authenticated or fetched.
The highest-value next steps are:

1. Live degraded-source behavior remains unverified. API fixtures now cover
   single-response failures and a partial two-request Kalshi metadata failure;
   no live source is intentionally degraded. Polymarket first and continuation
   pages and one Kalshi empty terminal page are captured; do not request more
   pages merely to increase counts. A live Kalshi trade row is not yet available
   in captured evidence. Mock tests cover bounded timeout retries,
   oversized-response rejection, truncated-stream evidence rejection, and
   retry-after/HTTP failure capture.
2. Keep centered multi-hop traversal within its current 500-row scan and
   revision-bound deterministic window. The focused depth-two browser E2E now
   passes; broaden to full-universe search or clustering only after
   representative data and resource measurements justify it.
3. Keep Kalshi fee applicability unresolved until source use is authorized and
   supported evidence is available. The July 7, 2026 schedule labels its
   columns Maker Multiplier then Taker Multiplier, so its `KXMVE` row is maker
   2 / taker 1. This clarifies the row reading only: the captured
   `KXMVECROSSCATEGORY` series is a different identifier, and the published
   row does not establish its maker fee. The API schema documents series
   `fee_type`/`fee_multiplier` and event fee overrides, but current market
   applicability, account rounding class, and maker/mixed-order costs remain
   unresolved. Keep Kraken's account fee tier unknown without authenticated
   account data, and keep fee expiry enforced before any decisive net
   classification.
4. Seek genuine public multi-outcome metadata that satisfies the strict verified
   payoff and resolution requirements; do not relax the evaluator to fit current
   captures.
5. Continue audit mutation/differential fixtures across quantity constraints,
   timing, and state-mapping edge cases. Fee-total, per-leg-fee, venue-capital,
   and maximum 16-outcome audit mutations are now covered. Design authenticated
   review and external assertion ingestion only after a separately reviewed
   security boundary exists.
6. Preserve both controlled-fixture Arena results as supervisor-path evidence.
   The worker now captures and displays process CPU/RSS, but do not make a
   capacity claim from two tiny same-input runs. Add Laboratory campaign
   management only if a concrete need remains.
7. Exact quote and capital denomination checks now cover the missing-currency
   case and the same-code token/fiat collision. The complete
   `Frontier.test.tsx` file, web typecheck, focused depth-two/capital/mobile
   browser case, and local production build pass. The build used 676,320 KiB
   peak RSS and emitted the existing main/chart chunk-size warning. The full
   browser suite and repository-wide test suite remain unrun.

Do not connect Frontier to Reality’s recorder, enable probes as a default,
deploy, or alter protected evidence as part of ordinary continuation. The next
safe work is genuine public multi-outcome term investigation, reconciling
Kalshi's native fee metadata to a supported fee calculation, and finding
distinct source-quality gaps that can be verified without intentionally
disrupting live sources. Exact-denomination aliasing is closed for the currently
supported candidate families.

## Latest checkpoint identity

The multi-outcome implementation is `5e87d1893d3f20972b32adfe19081a38a6286344`;
its non-vacuous replay regression is `d8d70a4dcb96da3f6eb4d5ca784af1b0500fd743`;
and the independent arithmetic audit is
`ae7c3084838a2942fab06017cacfb6657462fa53`. The source-failure diagnostic fix is
`53c38d7bf01a356b54c82e359ea64ab2661836f9`. Documentation checkpoint
`480a3224090f913d832578b581eab428b8b83cc3` documents the arithmetic audit.
Checkpoint `64dc16737e2e35edb02b2556600c8596e85f4a3f` records source-failure
evidence behavior and current test commands. Transport failure evidence is
`e8019d81a70c50446371d29d6e65ebaefba6e8e4`. Documentation checkpoint
`59bf64029e56ca6bad35298a8567c6a8d6c2982e` records byte-preserving failure
capture behavior. The retry-limit regression is
`294cc6dd8be39eed6a03ebc1fcc4ae5c42bab548`. Documentation checkpoint
`dbdd7c76654f6958a821be2897062212708bf884` records the 54-test verification and
updated measurements. The revision-bound relationship paging backend is
`89eff8b5b3594ca45c4f90be016a2066d5a5c688`; the Mission Control page controls
and browser coverage are `711a563f3b99665e2f635d4c66e286bee93f4d38`. Polymarket
v2 page support is `67f79cde6b37ac51c226c4338196a1b2482e37aa`; the Mission
Control continuation is `7c6cc21764d124f61211b79299335d78e8260c69`. The
capture and documentation checkpoint is
`e661e06e22b2d29bd68e13dd6e6b423c698fec27`; the paired replay implementation
and tests are `1e3d30a13db8588fae5e72a39f56fa7db625479a`. The full-or-no-fill exposure
implementation and test checkpoint is
`5af50b9714d571a0c730f15a0e261f2d4ece2b3e`; this report/ledger amendment records
economic model v4, independent audit v2, replay v5, and verification. The
bounded Arena paired-replay integration is `6fa3696`, and the admission-denial
regression is `cf6bade`. The readiness state is evidence-driven in `886e130`;
worker CPU/RSS capture and display are in `109df84`, with typed bounds in
`fba28df`. The first Arena report/docs
checkpoint is `f5c7129`; this ledger/report update records follow-up readiness,
resource measurement, and verification. No deployment or production change was
made.

The current MVE ticker-filter implementation and exact saved-response replay
are `a40d2ee`; the associated README, architecture, report and ledger
documentation checkpoint is `98fbf3a`. The Playwright ticker-filter update is
`4193ddb`; the fee-schedule mapping note is in `47664ad`. This latest
ledger/report amendment records v9 digest reconciliation, the 13-test focused
adapter/API selection, the **133-test** Python Frontier/Arena regression, the
40-test frontend run, current resource measurements, and the remaining
browser/build boundary. At 12:18 UTC, memory PSI `avg10` was 32.67% (`some`) /
28.61% (`full`), so the browser and build remain unrun. No live request was
repeated after the capture; no production deployment occurred.

The 2026-10-27 12:17 UTC fee-source review checked the official July 7 schedule
against the saved `KXMVECROSSCATEGORY` event/series metadata. It found that the
document's `KXMVE` maker/taker multipliers are not directly attributable to the
different captured series ticker. No fee model or candidate economics was
changed; this unresolved mapping is now explicit in the engineering report and
architecture handoff.

The Kalshi MVE reported-settlement arithmetic implementation is
`8a3e25cc1866644a49369e6797f8833aed36cb24`; the README, development,
current-state, architecture, report, and ledger documentation checkpoint is
`021399060de04589f1db49c4cb3cbbed4a55cb8e`. The audit remains fixture-verified
only. The full 148-test Frontier/Arena run predates the output source-link field;
the final focused 17-test Python selection and four Frontier browser cases
include it. See the 13:01 UTC checkpoint above for resource and validation
boundaries. No live settlement observation or production action occurred.

The venue-separated virtual balance comparison is implementation commit
`9d7b599516ca70895525c701543c507054bcfbe6`; the corresponding README,
development, current-state, architecture, report, and ledger documentation
checkpoint is `e3d974d`. The feature remains browser-local and research-only.
Its focused UI/browser verification passed; a production build after the UI
change remains unverified because it was stopped under rising memory PSI.
Commit `cca4038` tightens the per-venue currency guard and adds an unrun
regression test for incomplete currency metadata. Its focused test and
typecheck remain the next safe verification action after memory pressure eases.
The full implementation commit is `cca403886c5dd9f026baf97a8337fa68752e57cc`;
the report, ledger, and current-state follow-up is
`528aac29f233dcb364ba00849d4eed240bb500d5`.

## 2026-10-27 13:28 UTC — denomination and capture integrity

Code commit `f6cf347899da981093140b0ec44f03816c46e0d5` rejects verified payoff
currency/settlement mismatches in relationship verification, binary and
multi-outcome generation, and the independent audit. The focused USD/USDC
regression passed within a six-test economics selection. The same commit keeps
drained Polymarket v2 and generic market/book/trade captures available to failure
diagnostics after lineage rejection; four focused API tests passed and verify
raw-body hashes plus no duplicate previously stored listing.

Documentation commit `47254341322d7f2d89ce55147c8ac574be2a4b80` updates the
README, development guide, current-state handoff, Frontier architecture and
engineering report, and adds the Frontier operations guide. Ruff and
`git diff --check` passed. No live request, service, or historical store was
changed. At the latest `13:28:55Z` resource sample, PSI `avg10` was 39.81%
(`some`) / 34.86% (`full`); no broad suite or build was attempted.

## 2026-10-27 13:33 UTC — bounded source health count

API review found `SourceHealth.requests_in_window` was populated with the
transport's lifetime request counter. Code commit
`3f8a5cabfe209d105d0ddde948f9862cf72fb8fb` now reports a trailing 60-second
count from a bounded monotonic-time history; per-operation deltas continue to
use the lifetime counter. The focused adapter regression passed **1 test**
(`41 deselected`), and Ruff check/format passed. The test uses a patched local
clock and makes no network request. Documentation checkpoint
`a69d81c8fadb4d7833ff912ad169211afa767f10` records the request-window metric in
the architecture, operations, development, current-state, and report notes.

## 2026-10-27 13:35 UTC — cross-venue timestamp gate

Code commit `25a9cc711976da49b80bdaacc3b51c2ac6f82bae` now marks cross-venue
timing verified only when exchange timestamp semantics match and are known,
timestamps are not after replay time, and observed exchange skew plus both
provenance clock uncertainties is within the configured bound. Missing clock
uncertainty remains an explicit timing reason. The focused positive and
adversarial regression, including unknown timestamp semantics, passed **1 test**
(`21 deselected`); Ruff and formatting passed. Existing venue adapters do not
supply clock uncertainty, so recorded cross-venue candidate timing remains
unverified. No live data, service, or historical evidence was changed.
Architecture, operations, current-state, and report notes record the boundary
in documentation checkpoint `a69d81c8fadb4d7833ff912ad169211afa767f10`.

## 2026-10-27 13:40 UTC — focused regression closeout

After a fresh low-`avg10` PSI sample, the API, adapter, and economics files
passed **99 tests** with one existing Starlette/httpx deprecation warning. The
Frontier component file passed **8/8** tests after fixing its `within` query;
web TypeScript typecheck, targeted ESLint, and Prettier passed. Code commit
`f206dfedc34cf3fafae0b74afc5e13376c036b4a` contains the test-helper correction.

Targeted mypy was run on six changed engine/API modules and exited 1 after
finding 14 errors in four unmodified imported Veritas/Arena modules; it emitted
no diagnostics in the six explicit Frontier/API targets. The full repository
suite, remaining Frontier/Arena tests, production build, and browser E2E were
not run. At `13:40:25Z`, memory PSI `avg10` was 0% (`some`/`full`), `avg300`
was 19.26% / 16.92%, available RAM was 9.3 GB, and 553 MiB swap remained free.
No live source request, production service, or historical evidence was changed.
Documentation checkpoint `dc53a8d8fc199e7cc29288e6670d96b0b89f7e2a` records the
99-test run, UI regression correction, TypeScript verification, and static-check
boundary in the current-state handoff and engineering report.

## 2026-10-27 13:42 UTC — frontend build retry stopped under rising PSI

Retried `corepack pnpm --dir apps/web build`. TypeScript passed and Vite began
transforming modules. A sample about five seconds later showed host memory PSI
`avg10` at 10.74% (`some`) / 8.37% (`full`) and about 8.7 GB available RAM;
the process was stopped with Ctrl-C (exit 130). At `13:42:24Z`, PSI `avg10`
was 22.14% / 16.01%, `avg300` 14.22% / 12.27%, available RAM 9.1 GB, and free
swap about 553 MiB. The production bundle remains unverified. No service,
source, or historical evidence was changed. The detailed report and current-
state handoff record these measurements.
Documentation commit `2972eb92a4db0d53727b0d1eccc62b7a519392e7` records this
resource checkpoint in the engineering report and current-state handoff.

## 2026-10-27 — explicit Kalshi settlement finality

Code review found that the local MVE arithmetic audit treated a missing
`is_provisional` value as non-provisional when the parent lifecycle was settled.
The audit now requires an explicit `false`; `true` or absent is classified as
non-final. The focused unit selection passed **2 tests** (`20 deselected`),
and Ruff check/format passed. This prevents unknown finality from being
presented as a source-reported product match/mismatch. Audit response schema v2
pins algorithm `kalshi-mve-settlement-audit-2` and returns the
lifecycle/provisional evidence; Mission Control displays it. The focused API
test passed **1 test** (`34 deselected`), the focused UI test passed **1 test**
(`7 skipped`), TypeScript passed, and
Ruff, ESLint, Prettier, and `git diff --check` passed. Implementation commit
`364478853908272f5b860758fa0bb18b52b3efc8` contains the fix and focused tests.
This remains a local arithmetic check and does not validate rules, outcomes, or
candidate economics. Architecture, current-state, and report text record the
guard.
Documentation commit `3b7defba8c953d7eae7b7c2e9eb9ffa2ec49adc5` updates the
architecture and current handoff for this code checkpoint.

## 2026-10-27 — settlement asset identity review

The canonical `settlement_asset` field is an opaque string with no separate
network or token-contract identity. The Polymarket adapter leaves it absent and
does not verify its payout. Cross-venue payoff verification and opportunity
generation fail closed on missing/unverified payoffs and denomination mismatch,
so current adapters cannot create a candidate from a shared token ticker. Any
future token-settled adapter needs a network/contract-qualified identity or must
remain unsupported. This is a documented model limitation; no code or live
source data changed. Extend the asset identity model before enabling token-
settled cross-venue equivalence.
Documentation commit `b5fa650368d3f77422bc45025bdee9988b1906a8` records this
limitation in the architecture and handoff.

## 2026-10-27 — typed settlement asset identity implementation

Implemented schema-v2 `SettlementAssetIdentity` for markets and payoff specs.
Fiat identities use a three-letter code; non-fiat identities require both a
network ID and an asset reference. EVM addresses normalize to lowercase and
validate as 20-byte addresses; other reference formats retain their source
case. Kalshi event markets map to `fiat:USD`. Polymarket still does not attest
its settlement asset, and Kraken spot remains contextual rather than an event
payoff source.

Same-payoff verification, binary and multi-outcome candidate generation, and
the independent audit now require market/payoff identity agreement. Exact
identity participates in relationship evidence and stable identity inputs.
Schema-v1 records remain readable but cannot pass verified payoff comparison
without an identity. The UI shows the market and payoff identities and
relationship evidence exposes matcher/verifier versions and evidence details.

Verification: 25 relationship/economics/replay tests, 60 adapter/storage/
replay-comparison tests, two targeted API tests, and two targeted UI tests
passed. UI typecheck, Ruff, ESLint, Prettier, and `git diff --check` passed.
No full repository suite, production build, browser E2E, live token-settlement
integration, service change, or source request occurred in this checkpoint.
Token/network fixtures are controlled examples, not live market evidence.
Implementation commit: `e0529c5` (`Add canonical Frontier settlement asset
identities`). Architecture, current-state, and engineering-report updates are
in the documentation checkpoint accompanying this ledger entry.

## 2026-10-27 — Polymarket position-backed book route

Official Polymarket SDK and deployed-contract references distinguish the
legacy CTF-token route from its position-backed route. Adapter v5 now sends
Gamma v2 position IDs to `clob-v2.polymarket.com`, normalizes the documented
Polygon pUSD settlement identity (`eip155:137`, token
`0xc011a7e12a19f7b1f670d46f03b03f3342e82dfb`), and labels its book unit PUSD.
It preserves Gamma v1 CTF-token books on the legacy public CLOB host, while
leaving their canonical settlement identity absent. Both payoff paths remain
unverified, so these changes do not enable cross-venue candidate verification.

The v2 route is fixture-tested and live validation is pending: one direct
unauthenticated GET attempt to the official v2 host could not resolve DNS from
this development environment. A separate one-request v1-host probe on
2026-10-27 returned HTTP 200 at `14:16:33.559710Z`, with the saved Gamma
condition and asset IDs matching. Its 2,514-byte body SHA-256 is
`cecdb8d4f14fa61a7039e1559a52e02c2e7819a0342566f5d07d829841bc9aef`; the raw
body and parent listing observation reference are preserved in
`data/frontier/live-probes/2026-10-27-polymarket-clob-v1-book-r1.json`.

The full adapter module passed 44 tests and the full Frontier API module passed
35 tests with one existing Starlette/httpx deprecation warning. The new v2
fixtures cover host routing, PUSD identity, unauthenticated GET behavior, and
market-version/provenance mismatch rejection. No authenticated request,
service change, or deployment occurred. Official mapping references are the
[Polymarket SDK protocol table](https://github.com/Polymarket/rs-clob-client-v2/blob/main/README.md),
[Polygon V2 deployment manifest](https://github.com/Polymarket/polymarket-v2-external/blob/main/README.md),
and [collateral adapter source](https://github.com/Polymarket/ctf-exchange-v2/blob/main/src/adapters/CtfCollateralAdapter.sol).

The relationship/economics/replay module now passes 26 tests, including an
adversarial construction with equal nominal `USD` payout strings but a
Polygon pUSD settlement identity. Same-payoff verification rejects it on
both settlement denomination and exact asset identity, so the one-to-one
backing assumption does not become an implicit valuation bridge. Regression
test commit `65a7e8d98f0674cb05d1be025e43e820ed88092c` pins this boundary.
Implementation commit `2c7bacc517e7a273d2a4f6490a01f9174b82fef1`
(`Route Polymarket position markets through v2 CLOB`) includes adapter v5,
fixture tests, and the raw v1 book capture.

## 2026-10-27 — canonical quote and capital denomination identity

Implementation commit `03dbc92` carries exact denomination identity through
market instruments, public book snapshots, fee schedules, trade observations,
candidate legs, and candidate capital. The supported event evaluators require
quote identity to agree from payoff through instrument and observed book;
modeled fee arithmetic requires exact fee-unit identity. The independent audit
rechecks quote, book, fee, and capital units. Missing identities in historical
records remain unknown and fail closed. Replay v7 pins the new identity fields.

Controlled adversarial evidence includes a network-qualified token whose
display code is `USD` alongside fiat USD quote fields. A same-payoff relationship
on event terms does not establish quote-unit equality; candidate generation
returns incomplete evidence without legs. Independent audit rejects missing
leg, book, and capital identities. The dashboard disables mixed-unit funding
and keys virtual balances by venue and exact denomination. Kalshi paginated
trades now use trade schema v3 while retaining the TradeBatch v2 envelope.

Verification: the full Python Frontier suite passed **153 tests** in 35.35
seconds with one existing Starlette/httpx deprecation warning. The Frontier
component file passed **8/8**. The bounded depth-two graph, virtual-funding, and
mobile Playwright scenario passed **1/1** using temporary local services and
fixture routes. TypeScript, ESLint for the changed UI/E2E files, Prettier, Ruff
check/format, and `git diff --check` passed. The production bundle passed in
12.95 seconds with **676,320 KiB peak RSS** and zero swaps; the existing Vite
chunk-size warning remains for the main/chart bundles. No live source, service,
deployment, or protected data was touched. The full repository suite, full
browser suite, live Polymarket v2 host, and market-specific token payout remain
unverified. Project Frontier remains incomplete and undeployed.

## 2026-10-27 — API denomination serialization regression

Commits `8a1f41e` and `43b5a08` add focused end-to-end API assertions to
controlled multi-outcome replay and trade fixtures. Exact fiat USD identity
survives `/markets`, `/books`, and `/trades` read-back, then appears on replay
candidate legs and capital. Both focused tests passed (**2/2**) in 1.46 seconds,
with the existing Starlette/httpx `TestClient` deprecation warning. Ruff
check/format and `git diff --check` passed. This verifies serialization and
local persistence for these controlled fixtures; it adds no live-source
evidence. No service, external source, or historical data was changed.

## 2026-10-27 — source terms review and live-probe gate

The official Kalshi Developer Agreement v1.1 restricts API use to a member's
own trading and restricts other collection/storage; Kraken's official API
introduction requires prior permission for certain non-personal commercial
public market-data use. Frontier has no recorded written Kalshi
research/retention authorization and has not classified its Kraken data-use
scope. No exchange was contacted and no source request was made for this
review. See [`SOURCE_DATA_TERMS_REVIEW_2026-10-27.md`](SOURCE_DATA_TERMS_REVIEW_2026-10-27.md)
for the source links and operational decision.

Code commit `9d52b23` adds `MIDAS_FRONTIER_KALSHI_RESEARCH_AUTHORIZATION_REF` and
`MIDAS_FRONTIER_KRAKEN_MARKET_DATA_PERMISSION_REF` gates in the main API,
requires a reference in addition to the existing probe flag, returns the
policy reason in source inventory and disabled-probe errors, adds a readiness
gate, and shows the restriction in Mission Control. A reference is not
independently verified by the application. At this initial gate checkpoint,
stored-source reads were not yet quarantined; that gap is superseded by the
following `d38f517` checkpoint. Existing data remains preserved.

Verification: the Frontier API module plus source-policy tests passed **37
tests** in 20.13 seconds, and the updated source-configuration/API contract
passed **2/2** separately. The Frontier component tests passed **8/8**; TypeScript,
ESLint, Prettier, Ruff and `git diff --check` passed. The full suite and browser
E2E were deferred with memory PSI `avg10` at 39.10% (`some`) and 35.99%
(`full`). No live source call, production service, external message, or
historical evidence mutation occurred.

## 2026-10-27 — held-source read quarantine

Code commit `d38f517` applies the active Kalshi/Kraken source-use hold to stored
research reads. SQL-level source exclusions cover market, book, and trade
observations, summary aggregates, relationship lists, and indexed graph
neighborhoods. Direct observation and relationship-review reads reject held
records. Replay generation uses only non-held observations and relationships;
old candidate/run/comparison outputs are omitted when provenance or legs trace
to a held venue, with missing provenance failing closed. Main wires the same
venue hold into Arena; its Frontier replay catalog hides held snapshots and the
result route returns HTTP 409. The raw append-only evidence and pinned Arena
files remain unchanged. Direct database inspection and exports remain outside
the application route filter and are still operationally held.

Verification: the focused source/storage/Arena/API selection passed **13
tests** in 9.71 seconds with the existing Starlette/httpx TestClient warning.
The Frontier component suite passed **8/8**; TypeScript, targeted ESLint,
Prettier, Ruff and `git diff --check` passed. The full suite and production
build were not rerun. The integration evidence is fixture-only; it does not
audit the preserved live store or settle data-use terms. No live request,
external service, production configuration, or historical evidence was
modified. Source permission remains BLOCKED, deployment remains DEFERRED, and
Project Frontier remains incomplete.

## 2026-10-27 — generic Arena quarantine coverage

Code commit `73e008e` extends the `d38f517` read quarantine to generic Arena
surfaces that could otherwise disclose or reuse Frontier replay results. The
Arena overview omits held or unproven replay jobs; generic detail and log routes
reject them; generic replay submission validates the pinned snapshot before
enqueue; and cancellation is rejected before the job can be mutated or its
record returned. The dedicated replay catalog/result routes share the same
snapshot check. Commit `e7958c1` applies the check to the research-activity
digest as well. Commit `23f9860` runs the check before Arena's inspection and
reconciliation helper; the regression verifies the held manifest is unchanged.
A result artifact marks a job as a Frontier replay, so a
missing or altered job configuration fails closed. These decisions use
fixture snapshots and do not inspect the preserved live source database.

Verification: the focused source/storage/Arena/API selection passed **13 tests**
in 10.37 seconds with the existing Starlette/httpx TestClient deprecation
warning. Both Arena replay and API modules passed **30 tests** in 4.66 seconds;
the held-source regression also passed separately (**1 passed**). Ruff
format/check and `git diff --check` passed. The source artifacts and Arena
snapshot/result fixtures remained unchanged; no service, exchange, or live
database was accessed. Source terms remain BLOCKED, direct database reads and
exports remain held, production deployment remains DEFERRED, and the mission
is incomplete.

## 2026-10-27 — independent audit mutation coverage

Commits `79eefef` and `287da15` add negative mutations that alter the aggregate
modeled fee, a single leg's modeled fee, and per-venue capital allocation. The
independent audit marks each as a disagreement and downgrades classification
to incomplete evidence. Commit `82d7e47` carries the 16-outcome market through
deterministic replay and the independent audit, which agrees on the exact
65,536 full/no-fill pattern space at the supported bound. These are controlled
fixtures with the zero-fee test schedule; they do not validate any live venue
fee or profitability.

Verification: `tests/frontier/test_relationships_economics_replay.py` passed
**28 tests** in 0.47 seconds. Ruff check/format and `git diff --check` passed.
No source request, database, service, or protected research artifact was used.
Additional quantity, timing, and state-mapping mutations remain useful follow-up
work; the economic verifier remains fixture-validated and the mission remains
incomplete.

## 2026-10-27 — Kalshi event-fee override completeness

Official [Kalshi event-fee documentation](https://docs.kalshi.com/api-reference/events/get-event-fee-changes)
states that event fees override the parent series and that a null/null event
override clears that override. The current [fee schedule](https://kalshi.com/fee-schedule)
shows standard combo terms but also distinguishes non-standard series; it does
not establish series-specific maker applicability from the standard row alone.
The MVE schema lists event override fields without documenting precedence there.
No stored Kalshi capture was read for this review, because those source records
remain under the terms hold.

Code commit `e950b9c` bumps the Kalshi adapter to v15 and `KalshiFeeMetadata` to
schema v2. The metadata distinguishes complete event override, explicit
null/null series inheritance, partial override, and unreported override fields.
The one-fill and one-order Decimal sensitivities now require either the complete
override pair or explicit clearing; legacy schema-v1 metadata remains readable,
defaults to `override_unreported`, and is rejected as unresolved. Output schemas
and calculation model versions are v2, and Mission Control displays the
fee-resolution state. Candidate `FeeSchedule` and
candidate economics remain unchanged.

Verification: the focused Python selection passed **28 tests** in 3.49 seconds
with one existing Starlette/httpx deprecation warning. Strict mypy passed for
the three changed engine modules; Ruff check/format passed for six Python files.
The focused Frontier component test passed (**1 passed, 7 skipped**), TypeScript
typecheck passed, and targeted ESLint/Prettier passed. `git diff --check` passed.
These are fixture and local-code results, not a live fee validation. Series maker
applicability, account precision, FCM charges, future schedules, candidate fee
integration, source permission, and deployment remain unresolved or blocked.

## 2026-10-27 — independent timing and instrument-constraint verification

Code commit `b1c1df0` bumps the independent audit model to v4 and persists its
recomputed receipt skew, exchange timestamp skew, and timing verdict. The audit
independently checks pinned-book freshness, source freshness limits, timestamp
semantics, replay-time bounds, source-quality flags, best-ask timestamps, and
cross-venue clock uncertainty. Cross-venue generation now honors each book's
source freshness limit. Both cross-venue and multi-outcome candidate generation
reject a best ask that conflicts with declared instrument tick size; the
independent audit detects tick-metadata mutations. Quantity-step mutation also
has a direct adversarial audit regression. Test commit `4fcc628` adds direct
multi-outcome timing agreement and tampering coverage alongside the cross-venue
timing cases. Test commit `34b8b53` confirms that a swapped, still-bijective
outcome mapping is rejected as incomplete evidence when it conflicts with
verified instrument payoffs. Commit `5cb5747` advances the candidate economic
model to v7 because the freshness and tick checks affect candidate eligibility
and replay identities; test commit `fcf3b31` pins v7 in the replay manifest.

Code commit `89526f3` exposes the recomputed audit timing values and gate in the
Opportunity Explorer, with a distinct not-recorded state for older records.
Test commit `3e648dd` removes the new fields from a legacy candidate fixture and
verifies all three labels show “Not recorded.” The full frontend suite passed
**40 tests**; TypeScript, targeted ESLint, and Prettier passed. The production
build was not repeated.

Post-commit verification passed **134 tests** across the replay/economics,
adapter, API, and Kalshi fee-sensitivity selections in 21.88 seconds. The
replay-manifest assertion also passed in its focused deterministic-replay test.
Strict mypy passed for `models.py`, `economics.py`, and `independent_audit.py`;
Ruff check/format and `git diff --check` passed. One existing Starlette/httpx
TestClient deprecation warning remains. Verification is fixture-based: live
adapter clock-uncertainty values are still absent, held-source captures were
not read, and no production request or deployment was made. The full Python
suite, frontend production build, performance, and live-source checks were not
repeated. Quantity, timing, source-quality, and tick validation improve
verifier coverage but do not establish synchronized execution or
profitability; the mission remains incomplete.

Code commit `8195df4` adds timing-audit counts to the readiness source-quality
gate. The fixture persists a replay with missing clock uncertainty and another
with explicit clock bounds, then verifies the response distinguishes candidates
within and outside the configured timing limits. The existing gate state still
requires per-observation review and the counts do not assert execution. Strict
mypy, Ruff, and the API test file pass; after moving the fixture into its own
test, the two readiness tests passed (**2 passed**). The relationship/economics
module passed **33 tests**, including the new multi-outcome off-tick regression.

The suggested legacy-audit and held-replay readiness checks were completed in
the checkpoint below using synthetic rows and preserved fixture-only
observations.

## 2026-10-27 — legacy replay hashes and readiness coverage

Storage commit `6b08efe` preserves hash validation for pre-v4 audit replay rows:
the reader accepts a matching digest over either the original serialized
payload or its normalized current-model representation. This handles newly
defaulted optional timing fields without rewriting the stored row, while
retaining tamper rejection. Its synthetic v3 replay regression confirms the
stored JSON and digest remain unchanged. All **15 storage tests** passed;
strict mypy, Ruff, formatting, and `git diff --check` passed.

Readiness commit `0b341c4` counts legacy audits without recomputed timing fields
as “not recorded,” and also counts a candidate with no audit object in that
timing bucket. Follow-up commit `e9d0ff1` also counts missing audit objects as
not-evaluated, and leaves the gate `NOT_ESTABLISHED` when there are no evaluated
audits. Test commit `2c7763d` covers a replay window containing only an
unaudited candidate. A v3 audit replay inserted into a temporary test database
is reported through readiness without losing its original hash. The
held-source fixture checks readiness as well as the replay list: three
quarantined Kalshi runs contribute zero non-held replay outputs and zero timing
counts.

Commit `163ab79` makes readiness return HTTP 409 with a storage-integrity
diagnostic if a replay payload no longer matches its pinned result hash. The
follow-up `e491f3f` centralizes replay reads and applies the same 409 response
to `/runs`, `/opportunities`, and held-filtered `/overview`. A synthetic held
source configuration verifies all four read routes including `/readiness`.
Commit `d75d1ee` extends the same integrity response to comparison list/detail,
overview, and relationship reads, including the readiness relationship gate.
Corrupt comparison and relationship rows remain in the temporary database and
all affected routes fail closed. Test commit `050d798` also confirms that a
comparison with a corrupt pinned replay and a relationship with a corrupt
review record fail closed through their read APIs. The focused legacy,
unaudited, quarantine, replay/comparison hash, relationship hash, pinned-run,
and review-record regressions passed **7 tests** in 3.40 seconds. Strict mypy
passed for `apps/api/frontier.py`; Ruff check/format and `git diff --check`
passed. One existing Starlette/httpx TestClient deprecation warning remains.
No held capture, live endpoint, production database, or service was accessed.

Commit `a675a3f` adds one fail-closed observation reader for direct evidence,
market, book, trade, and overview queries. Its test corrupts three temporary
source rows, checks each API returns HTTP 409, and confirms the stored damaged
payloads remain untouched. The eight focused readiness, quarantine, replay,
comparison, review, and observation regressions passed **8 tests** in 3.96
seconds. Strict mypy passed for the API route; Ruff check/format and
`git diff --check` passed. One upstream Starlette/httpx deprecation warning
remains. No production or held-source records were read.

## 2026-10-27 16:20 UTC — full Frontier suite deferred under host pressure

At `2026-10-27T16:20:34Z`, host memory PSI was `avg10` 49.81% (`some`) and
45.22% (`full`), with `avg60` 46.14% / 41.60%. Host RAM showed 9.1 GiB
available and swap showed 3.5 GiB of 4.0 GiB in use. CPU PSI `avg10` was 1.42%
and I/O PSI `avg10` was 0.17%. The current shell cgroup reported 2.05 GB usage
with no `memory.high` or `memory.max` bound; that does not override the host
pressure signal. The broad `tests/frontier` suite was not started. The eight
targeted integrity/readiness tests above remain the current verification for
this change set; this is not a full Frontier-suite pass.

**Next safe action:** remeasure PSI after host memory pressure subsides and
only then reconsider the full `tests/frontier` suite. Keep test roots
temporary; classify any interrupted run as incomplete.

## Saved Kalshi candidate-fee estimate — 2026-10-27 16:41 UTC

Implementation commit `3e85c8d` adds a saved-evidence candidate fee path. The
API joins Kalshi event/series metadata to replay markets only after normalized
identity, event/series agreement, raw body digest, HTTPS host/path, exact source
fields, and receive-time validation. The economics compiler accepts complete
event overrides or explicit null/null series inheritance for supported
quadratic taker fee types. Partial/unreported/unsupported or mismatched rows
stay unknown. Held Kalshi rows remain filtered. Metadata must predate the
pinned book quote and remain within the 24-hour limit at both quote and replay
time.

The estimate uses the July 7, 2026 public quadratic formula, one fill, and
non-direct `$0.01` balance-alignment as a conservative scenario. It is
`FeeStatus.ESTIMATE`, is independently recomputed by audit v5, and cannot
produce `VERIFIED MATHEMATICAL INCONSISTENCY`. Replay v8 manifest schema v2
pins fee metadata observation IDs. Mission Control's run summary displays the
observation count. Account fee class, multi-fill, maker/mixed-order and FCM
charges, later schedule changes, and realizable net costs remain unresolved.

Verification after implementation, freshness test commit `90bd11e`, and API
test commit `ad1415b`: 35
economics/replay tests, 3 saved-fee/API and held-quarantine tests, 19
storage/replay-comparison tests, 2 adapter capability/metadata tests, and 1 UI
fixture (**60 total**); strict mypy for six changed Python modules; Ruff
check/format; web typecheck; targeted ESLint and Prettier; `git diff --check`.
One Starlette/httpx deprecation warning remains.
The complete Frontier suite and production build were deferred at host PSI
`avg300` 17.36% (`some`) / 15.70% (`full`) with only 473 MiB swap free. These
are bounded fixture results, not live fee validation. No source request, held
data read, service, or production setting changed.

Architecture, development, operations, engineering report, and this ledger
record this checkpoint. The mission continues; next work should remain isolated
and bounded, favoring research or validation that does not depend on currently
blocked Kalshi/Kraken source use.

## Replay manifest v1 fee-field compatibility — 2026-10-27 16:49 UTC

Test commit `f35677d` extends the legacy replay-storage regression with a
schema-v1 manifest that has no `fee_metadata_observation_ids` field. The
temporary row is read through the current manifest-v2 model with an empty
default while its original JSON and digest remain byte-for-byte preserved. The
focused test passed (**1 passed** in 0.55 seconds); Ruff and formatting passed.
The broader storage/replay-comparison suite was not rerun after this test-only
change.

At `2026-10-27T16:49:36Z`, host memory PSI measured `avg10` 40.64% (`some`) /
36.38% (`full`), `avg60` 42.33% / 38.23%, and `avg300` 36.64% / 33.16%.
Available memory was 9,581,096 KiB, with 484,348 KiB of 4 GiB swap free. The
full Frontier suite and production build remain deferred. No source request,
held data read, service, production setting, or historical store was accessed.

## 2026-10-27 16:54 UTC — end-to-end fee candidate API replay

Test commit `65a4f4e` checked fee observation IDs in both the returned and
persisted replay manifests. Follow-up test commit `dc5ef43` extends the same
temporary-store fixture with a controlled cross-venue binary pair, explicit
same-payoff assertion, and four stored books. The local replay API returns a
conditional candidate with `$0.18` modeled fees and `$1.32` worst-case modeled
net P&L. The independent audit reproduces the calculation and practical
eligibility remains false. The response and persisted replay both pin the fee
observation IDs. The focused test passed (**1 passed** in 1.36 seconds);
Ruff, format check, and `git diff --check` passed. One existing
Starlette/httpx deprecation warning remains. Data and the assertion are
controlled fixtures, not live venue evidence. The empty adapter registry
caused no source request.

At `2026-10-27T16:54:49Z`, memory PSI was `avg10` 0.00% (`some`) / 0.00%
(`full`), `avg60` 2.94% / 2.64%, and `avg300` 22.70% / 20.48%.
`MemAvailable` was 9,845,932 KiB; swap free was 484,520 KiB of 4 GiB. The full
Frontier suite, production build, and browser E2E remain deferred. No source,
held data, service, or production setting was accessed.

## 2026-10-27 16:56 UTC — official Kalshi fee-rounding cross-check

The [official fee schedule effective July 7, 2026](https://kalshi.com/docs/kalshi-fee-schedule.pdf)
sets the quadratic trade formula; [Kalshi's fee-rounding guide](https://docs.kalshi.com/getting_started/fee_rounding)
specifies microdollar trade-fee rounding, balance-precision alignment, and an
order-level accumulator/rebate. The existing one-fill sensitivity/candidate
math applies the published single-fill operations for both precision classes;
the separate order sensitivity models the multi-fill accumulator. The targeted
fee-sensitivity module passed **19 tests** in 0.28 seconds, including the
documented FCM fill example and two-fill accumulator/rebate fixture. No code
changed. This validates the bounded calculations against public documentation,
not a specific account's charged fee or a live market's applicable schedule.

At `2026-10-27T16:56:38Z`, memory PSI was `avg10` 0.00% (`some`) / 0.00%
(`full`), `avg60` 0.48% / 0.43%, and `avg300` 15.66% / 14.13%.
`MemAvailable` was 9,836,380 KiB; swap free was 484,544 KiB of 4 GiB. The
broad Frontier suite, browser E2E, and production build remain deferred.

## 2026-10-27 16:57 UTC — persisted candidate readback

Test commit `b01e757` verifies that the stored replay's candidate list matches
the local API response, preserving its conditional classification and
independent audit alongside the fee-evidence manifest IDs. The focused API
test passed (**1 passed** in 1.39 seconds); Ruff and format check passed. One
existing Starlette/httpx warning remains. The fixture is controlled and made
no source requests.

After the test, at `2026-10-27T16:57:34Z`, memory PSI measured `avg10` 39.35%
(`some`) / 35.94% (`full`), `avg60` 14.33% / 13.19%, and `avg300` 16.32% /
14.79%. Available memory was 9,614,412 KiB and swap free was 484,552 KiB of
4 GiB. Broad suites and production build remain deferred.

## 2026-10-27 16:58 UTC — host-pressure recheck

At `2026-10-27T16:58:07Z`, memory PSI rose to `avg10` 50.81% (`some`) /
46.34% (`full`), `avg60` 29.18% / 26.77%, and `avg300` 19.83% / 18.02%.
`MemAvailable` was 9,620,440 KiB and swap free was 484,556 KiB of 4 GiB. No
large tests or build were started. Reconsider broad validation only after a
later low-pressure admission measurement. No source, service, or production
state was accessed.

## 2026-10-27 17:00 UTC — property-based fee-order invariants

Test commit `1144283` checks 24 generated order cases per run across one-to-32
fills, buy/sell sides, varied contract prices/quantities, and multipliers 0/1/3.
For each documented balance precision it verifies nonnegative fill fees, rebate
bounds, exact aggregation, and that signed revenue minus net fee equals the
recorded balance change at fill and order levels. The complete fee-sensitivity
module passed **20 tests** in 0.43 seconds. Ruff, format check, and
`git diff --check` passed. Generated fixtures exercise only the Decimal model.

At `2026-10-27T17:00:21Z`, memory PSI was `avg10` 39.43% (`some`) / 32.43%
(`full`), `avg60` 41.16% / 36.61%, and `avg300` 28.33% / 25.60%.
Available memory was 9,592,368 KiB and swap free was 484,584 KiB of 4 GiB.
Broad Frontier verification and production build remain deferred.

## 2026-10-27 17:15 UTC — directed logical-implication review integration

Added `verify_logical_implication` and four controlled tests. It requires an
explicit bijection of joint state IDs, verified exhaustive binary payoffs,
complete complementary 0/1 YES and NO vectors, verified resolutions, source
observation IDs, and an external assertion. It bounds the state space at 1,024
entries and includes direction plus per-market settlement units/times in the
relationship identity and evidence. A verified result establishes payout-vector
implication only; it neither authenticates the semantic mapping nor bridges
settlement differences. The existing relationship-review API now accepts this
review type using hash-checked stored source evidence, and the append-only store
accepts the directed edge only when it preserves the reviewed endpoint pair
and evidence. Mission Control has no directed-review controls and the
opportunity engine does not yet consume these edges.

Nine new tests, including all 64 pairs of three-state YES payout vectors, and
the relationship/economics and review API modules passed **52 tests** in 4.02
seconds. One existing Starlette/httpx deprecation warning remains. All three
changed Python modules pass `mypy --strict --follow-imports=silent`; an
unrestricted strict run reports 14 errors in imported Veritas/Arena modules,
none in changed files. Ruff, format check, and `git diff --check` passed. No
external source or held data was read. Inputs require distinct source IDs,
bounded assertion/evidence identifiers, and an assertion time no earlier than
the source observations.

At `2026-10-27T17:16:56Z`, memory PSI was `avg10` 41.71% (`some`) / 38.28%
(`full`), `avg60` 39.03% / 35.22%, and `avg300` 29.23% / 26.23%.
`MemAvailable` was 9,433,944 KiB; swap free was 485,104 KiB of 4 GiB.
Broad Frontier verification and production build remain deferred.

## 2026-10-27 17:02 UTC — whitespace permission-reference regression

Test commit `fd5711a` verifies that probe flags plus whitespace-only Kalshi
and Kraken permission references leave both live probes disallowed. The
settings-only test passed (**1 passed** in 0.95 seconds); Ruff, format check,
and `git diff --check` passed. It creates no adapter and sends no request. One
existing Starlette/httpx deprecation warning remains.

At `2026-10-27T17:02:02Z`, memory PSI was `avg10` 45.61% (`some`) / 41.04%
(`full`), `avg60` 45.59% / 41.05%, and `avg300` 33.78% / 30.52%.
Available memory was 9,632,428 KiB and swap free was 484,596 KiB of 4 GiB.
Broad suites and production build remain deferred.

## 2026-10-27 17:04 UTC — independent fee-calculator differential

This checkpoint adds a 32-example Hypothesis check across bounded
prices, quantities, and fee multipliers. The candidate fee calculator, the
independent auditor, and the non-direct one-fill sensitivity agreed exactly
for every generated case. The full fee-sensitivity module passed **21 tests**
in 0.50 seconds. Ruff, format check, and `git diff --check` passed. The test
uses controlled fixture metadata and makes no source requests.

At `2026-10-27T17:04:54Z`, memory PSI was `avg10` 45.31% (`some`) / 40.92%
(`full`), `avg60` 44.96% / 40.74%, and `avg300` 39.03% / 35.36%.
`MemAvailable` was 9,664,080 KiB and swap free was 484,612 KiB of 4 GiB.
Broad Frontier verification and production build remain deferred.

## 2026-10-27 19:17 UTC — permission-reference fail-closed regression

A read-only audit found that a nonblank Kalshi or Kraken permission-reference
string could clear the API's held-source reason even though Frontier has no
authorization validator and probing remained disabled. That could expose
previously stored evidence through research routes. The settings now keep both
`frontier_*_probe_allowed` properties false independent of probe flags and
references; the API always supplies a source-use hold, and readiness explains
that no validated loader exists. The source-terms review, operations guide,
current-state note, and regression now state the same rule. The test configures
arbitrary references while checking probe rejection and synthetic stored-data
quarantine. Implementation and regression are committed as `52b6a9e`;
behavioral verification is complete. After formatting the test file, the
source-permission module passed **4 tests in 1.77 seconds** at **116,980 KiB
peak RSS**. The complete Frontier
Python suite passed **219 tests in 39.47 seconds** at **335,216 KiB peak RSS**,
with zero swaps. The existing Starlette/httpx TestClient deprecation warning
remains. Ruff check and format check passed for the changed Python modules;
`git diff --check` passed. Strict mypy passed for `models.py` and
`relationships.py` in 2.38 seconds at 133,268 KiB peak RSS. The test file was
formatter-normalized after the full suite; that was a whitespace-only change.

At `2026-10-27T19:23:46Z`, post-suite memory PSI `avg10` was 0.00% (`some` and
`full`), `avg60` was 8.43% / 7.58%, and `avg300` was 30.50% / 27.57%; available
memory was 9,526 MiB and swap free was 468 MiB. No held capture or external
source was read; all source-policy cases used synthetic temporary records, and
the runtime held-source guard was active. No protected service or production
state was accessed. The tests establish route/probe behavior, not legal source
permission or live multi-venue validation.

## 2026-10-27 19:28 UTC — official Kalshi multiplier-column clarification

Read the current official July 7, 2026 fee schedule and API documentation. The
schedule labels the table columns Maker Multiplier and Taker Multiplier, in
that order; the `KXMVE` row's `2 1` therefore means maker 2 / taker 1. The
series API schema exposes `fee_type` and `fee_multiplier`, and the event fee
changes API describes event overrides layered on the parent series. This
resolves a table-reading ambiguity only. It does not show that the `KXMVE` row
applies to the differently named captured `KXMVECROSSCATEGORY` series, nor
does it establish account-specific precision or maker/mixed-order costs. The
current estimator remains a taker sensitivity; its existing controlled test
covers the `quadratic_with_combo_maker_fees` type with multiplier 1. No code or
tests changed. No API request, held-capture read, source-probe enablement, or
production action occurred.

Sources: [official July 2026 fee schedule](https://kalshi.com/docs/kalshi-fee-schedule.pdf),
[Get Series schema](https://docs.kalshi.com/api-reference/market/get-series),
[Get Event Fee Changes](https://docs.kalshi.com/api-reference/events/get-event-fee-changes),
and [fee-rounding guide](https://docs.kalshi.com/getting_started/fee_rounding).

At `2026-10-27T19:28:52Z`, memory PSI `avg10` was 46.02% (`some`) / 39.98%
(`full`), `avg60` 35.04% / 31.47%, and `avg300` 22.52% / 20.34%. Available
memory was 9.3 GiB and swap free was 468 MiB of 4 GiB. After `avg10` eased, the
focused existing regression
`test_supported_quadratic_maker_variants_keep_taker_formula` passed **2/2**
in 0.30 seconds at **54,520 KiB peak RSS**, with zero swaps. The test exercises
synthetic metadata for `quadratic` and `quadratic_with_combo_maker_fees` at
multiplier 1; it does not establish that the schedule applies to any live
market. At `2026-10-27T19:31:50Z`, memory PSI `avg10` was 0.05% (`some`) /
0.04% (`full`), `avg60` 15.01% / 13.35%, and `avg300` 24.38% / 21.90%; available
memory was 9.4 GiB and swap free was 468 MiB. `git diff --check` passed for the
documentation. Source permission, specific market fee applicability, genuine
cross-venue economics, broader regression, and production deployment remain
unresolved.

## 2026-10-27 19:44 UTC — Kalshi price-range constraints

The [official Kalshi Get Market schema](https://docs.kalshi.com/api-reference/market/get-market)
exposes `price_ranges` entries with `start`, `end`, and `step`. Frontier now
preserves these fields as exact-decimal `MarketInstrument.price_increment_ranges`
in FrontierMarket schema v4. Kalshi adapter v17 bounds and validates the list,
keeps the source-native fields, and distinguishes an absent range list from an
explicit empty list. The shared model caps decimal precision at 18 places so
extreme scientific-notation exponents are rejected before rational arithmetic.
The candidate generator and independent audit separately enforce reported
ranges. The validator treats `start` as the step-grid anchor; that is an
inference from the field shape, not an explicit source guarantee. Because the
schema does not define whether range endpoints are inclusive, boundary prices
fail closed. No source request or held-capture read occurred.

Economic model v10, independent audit v7, and deterministic replay v10 pin the
new constraint behavior. The selected adapter/economics/replay/API tests passed
**17 passed, 126 deselected** in 1.17 seconds at **78,936 KiB peak RSS** with
zero swaps (one existing Starlette/httpx deprecation warning). Adversarial
fixtures reject an extreme `1e-999999999` step before rational conversion,
non-array and oversized range lists, out-of-domain and overlapping ranges,
missing fields, non-string numeric fields, and overlong decimal strings. The
full Frontier component test file passed **8/8** in 3.31 seconds, including
range and quantity-constraint display. TypeScript typecheck, targeted
ESLint/Prettier, Ruff, strict mypy on five changed production modules, and
`git diff --check` passed. At `2026-10-27T19:46:50Z`, host memory PSI `avg10`
was 41.09% (`some`) / 36.23% (`full`), with 9.2 GiB available and 468 MiB swap
free. No broad suite or production build was run. Live range semantics, source
permission, cross-venue economics, and deployment remain unresolved; Frontier
remains isolated and PARTIALLY VERIFIED.
Code commit `47f399d` implements the typed range model and checks; test/documentation
commit `52abaad` adds the malformed-input matrix and records the expanded run.
The full adapter module then passed **60 tests** in 2.65 seconds at **60,504
KiB peak RSS**, with zero swaps. At `2026-10-27T19:45:58Z`, host memory PSI
`avg10` was 47.18% (`some`) / 41.86% (`full`), with 9.3 GiB available and 468
MiB swap free. This adapter-module pass is not a full Frontier regression.
Next safe action: continue offline work on unresolved cross-venue capital and
settlement costs, keeping unsupported transfer/FX costs unknown. The full
Frontier Python, web, and isolated browser suites have now run; keep the
source-use hold, protected services, and production deployment boundary unchanged.
At `2026-10-27T19:46:50Z`, the full Frontier UI component file also passed
**8/8** in 3.31 seconds under the same bounded resource sample.

## 2026-10-27 19:50 UTC — consolidated Frontier regression and build

After PSI eased, `pytest tests/frontier -q` passed **230/230** in 39.45 seconds
(40.56 seconds wall) at **335,348 KiB peak RSS**, with zero swaps and one
existing Starlette/httpx deprecation warning. The full web unit suite passed
**40/40 across seven files** (4.85 seconds Vitest, 5.36 seconds wall) at
**298,344 KiB peak RSS**, with zero swaps. The isolated Frontier browser spec
passed **4/4** with one worker in 9.7 seconds (10.29 seconds wall) at **190,708
KiB peak RSS**, with zero swaps. Its four cases checked no source probes,
read-only Arena history, fixture-only Kalshi settlement arithmetic, and a
bounded mobile graph. Playwright used temporary API databases, Arena/Frontier
roots, and a temporary test-output directory; its local servers stopped at
completion.

The production build passed via
`npm run build -- --outDir /tmp/midas-frontier-web-build-20261027-1949`:
TypeScript succeeded and Vite built 2,228 modules in 4.69 seconds (12.21
seconds wall) at **706,308 KiB peak RSS**, with zero swaps. The repository's
existing `dist` was not written. Vite retains its >500 kB main/Chart chunk
warning and noted that external output directories are not emptied by default.
The web typecheck, targeted ESLint/Prettier, Ruff, strict mypy on five changed
production modules, and `git diff --check` passed.

At `2026-10-27T19:50:15Z`, memory PSI `avg10` was 0.00% `some` / 0.00% `full`,
`avg60` 2.36% / 2.11%, and `avg300` 22.62% / 20.32%; 9.1 GiB was available and
468 MiB of 4 GiB swap was free. No external source probe, held-capture read,
Reality action, or deployment occurred. The repository-wide legacy suite was
not run. Source-use permission, live cross-venue equivalence/economics, and
broader funding/settlement costs remain open; Frontier is still PARTIALLY
VERIFIED.

## Per-venue quote-decay replay sensitivity — 2026-10-27 20:16 UTC

Code commit `9da08fd` extends `ExecutionScenario` with a shared base execution
delay and optional additional delay by supported venue. Each value is a strict
whole number of milliseconds; no more than the three supported venue keys are
accepted; base plus venue addition cannot exceed one hour. Cross-venue binary
and same-market multi-outcome candidates apply the venue-specific effective
delay when evaluating the user-supplied quote-decay assumption. Independent
audit v8 rederives the leg price from the pinned market venue. Scenario payloads
remain included in candidate identity and replay input hashes; replay v11 and
economic model v11 pin the behavior.

The Workbench now exposes a delay addition for each configured source and
sends it to direct, paired, and Arena replays. The displayed-depth setting is
now correctly described as a top-ask size haircut. It does not model partial
leg fills. Per-venue delay is only a virtual quote-decay sensitivity; no actual
latency, execution ordering, or fill response is claimed. Full-or-no-fill
stress remains the separately modeled adverse leg test.

Verification: a focused Python selection passed **8/8** (80 deselected) in
1.32 seconds pytest time / 1.77 seconds wall at **86,172 KiB peak RSS**, zero
swaps and zero socket messages. It covers the venue-specific price math,
independent audit agreement and tamper rejection, invalid inputs, replay hash
pinning, and API scenario persistence. The isolated API replay test passed
**1/1** in 0.94 seconds pytest time / 1.38 seconds wall at **77,348 KiB peak
RSS**, zero swaps, with the existing Starlette/httpx deprecation. The focused
Workbench test passed **1/1** (seven deselected). TypeScript, targeted
ESLint/Prettier, Ruff check/format, strict mypy on the four Frontier domain
modules with imported diagnostics suppressed, and `git diff --check` passed.

An unrestricted API-inclusive mypy attempt reported imported, pre-existing
type errors in `packages/midas/veritas/independent_economics.py` at lines 46,
296, and 407. A second filtered API-inclusive invocation was interrupted after
15 seconds without output under elevated memory pressure; API-inclusive strict
typing remains unverified. At `2026-10-27T20:16:17Z`, PSI avg10 was 44.92%
(`some`) / 40.76% (`full`), 9.5 GiB was available, and 469 MiB swap remained
free. The full Frontier regression and production frontend build were not
rerun; the prior build predates this UI revision. No live source, held capture,
Reality service, or production state was accessed. Commit `9da08fd` contains
the code and tests. Frontier remains **PARTIALLY VERIFIED** and undeployed.

## Fee evidence at modeled execution time — 2026-10-27 20:22 UTC

Code commit `ad811a4` now evaluates each leg's pinned fee schedule at the
scenario's projected venue time: replay analysis time plus shared base delay
and that venue's additional delay. Effective/expiry limits and the age bound
for provenance-bound Kalshi fee estimates are checked at that time. If fee
evidence has expired, the fee and after-fee result remain unknown; no net
opportunity claim is produced from an outdated schedule. The independent audit
reconstructs the projected time separately. Economic model v12, audit v9, and
replay v12 pin the behavior. This does not predict future fee changes or
establish that a public schedule remains in force.

Verification: the delay and fee-expiry selection passed **6/6** (39 deselected)
in 0.47 seconds pytest time / 0.81 seconds wall at **60,588 KiB peak RSS**,
zero swaps and zero socket messages. The saved-evidence API replay case passed
**1/1** in 0.93 seconds pytest time / 1.36 seconds wall at **77,392 KiB peak
RSS**, zero swaps, with the existing Starlette/httpx deprecation. The complete
Frontier suite passed **252/252** in 39.63 seconds pytest time / 40.73 seconds
wall at **336,712 KiB peak RSS**, zero swaps and zero socket messages. Ruff
check/format, strict mypy for the four core Frontier modules with imported
diagnostics suppressed, and `git diff --check` passed.

At `2026-10-27T20:22:35Z` after the full suite, memory PSI avg10 was 25.66%
(`some`) / 22.83% (`full`); 9.5 GiB was available and 469 MiB swap free. The
production web build remains pending after the UI change; the UI test,
TypeScript, ESLint, and Prettier had already passed at the prior checkpoint.
API-inclusive strict mypy remains unverified, with its imported Veritas errors
and interrupted filtered attempt recorded above. No live source, held capture,
Reality service, or production action occurred. `ad811a4` contains the code and
tests; Frontier remains isolated, undeployed, and **PARTIALLY VERIFIED**.

## Frontend build admission recheck — 2026-10-27 20:24 UTC

No new test or build was started. At `2026-10-27T20:24:20Z`, memory PSI avg10
was 51.94% (`some`) / 47.60% (`full`), avg60 43.30% / 39.55%, and avg300
31.50% / 28.41%; 9.6 GiB was available and 469 MiB swap remained free. The
production frontend build and post-UI-change browser suite remain pending until
host PSI eases. The worktree is clean at `ed92557` atop `ad811a4`.

## Bounded partial-fill grid implementation — 2026-10-27 20:34 UTC

Uncommitted code now adds a five-point per-leg partial-fill sensitivity to every
supported opportunity candidate. Quantity-step-invalid interior points are
omitted. The worst combination per terminal state is computed separably, so a
16-leg candidate does not expand a `5^16` Cartesian product. Supported fees are
recalculated for each modeled aggregate quantity at each venue's projected
execution time; any unresolved fee suppresses after-fee sensitivity. The
independent audit separately derives feasible fractions, fee amounts, and worst
results. Replay v13, economic model v13, and audit v10 pin the candidate change.
Mission Control displays the sampled grid, worst gross/net outcomes, and fill
quantities while identifying the output as a bounded sensitivity.

The focused economics selection passed **6/6** (41 deselected), including
exhaustive three-leg grid differentials, quantity-step filtering, unknown-fee
handling, a fee-rounding case where partial fees are not a linear share of the
full-order fee, and independent audit validation. A partial-result tampering
case also passed **1/1**. The Workbench component suite passed **8/8**;
TypeScript, ESLint, Prettier, Ruff, core Frontier strict mypy, and diff checks
passed. The first full Frontier run after adding the model reported 252 passed
and one failed: a mutated off-step candidate caused the independent audit to
return incomplete rather than the expected disagreement. The audit diagnostic
path is corrected and its focused test now passes, but a complete post-fix
Frontier run remains pending.

At `2026-10-27T20:34:20Z`, memory PSI avg10 was 42.59% (`some`) / 38.56%
(`full`), avg60 39.05% / 35.13%, and avg300 27.72% / 24.95%; 9.9 GiB was
available and 469 MiB swap remained free. No full regression, frontend build,
or browser suite was started during that pressure sample. The worktree has
uncommitted changes in the Frontier economic model, independent audit, replay
version, focused API/economics tests, Workbench, and the architecture/report
matrix. Next safe action: remeasure PSI, run the complete Frontier suite when
admission permits, then run the full web suite/build and document actual results.
No live source, held capture, protected service, or production state was
accessed.

## Post-fix partial-fill regression — 2026-10-27 20:37 UTC

The full `tests/frontier` regression now passes **254/254** in 39.82 seconds
pytest time / 40.92 seconds wall at **335,988 KiB peak RSS**, with zero exit
status and only the existing Starlette/httpx TestClient deprecation. This
includes the corrected invalid-quantity diagnostic, API replay v13, exhaustive
three-leg fee-grid comparisons, audit tampering, and 16-leg bound. After the
run, memory PSI avg10 was 34.40% (`some`) / 30.73% (`full`), avg60 22.93% /
20.56%, avg300 27.50% / 24.76%; 9.9 GiB was available and swap free increased
from 481,020 KiB to 481,040 KiB. Full web unit suite, production frontend build,
and browser E2E remain pending; remeasure host admission before starting those
jobs. The partial-fill grid exposes the actual feasible fractions per leg in
its API object and an expandable Workbench detail. Core Frontier Ruff, format,
strict mypy, Web TypeScript, Prettier, and the focused eight-test Frontier
component suite pass. No deployment or live data was used.

## v13 partial-fill code commit — 2026-10-27 20:38 UTC

The bounded partial-fill implementation, independent audit, replay/model
version updates, focused API/economics tests, Workbench presentation, and
architecture/report changes are committed as **`e50ba34`** (`Add independently
audited partial-fill grid sensitivity`). The code commit contains ten files;
the ledger and current-state checkpoint are being updated separately. The
full Frontier test result remains **254/254** (40.92 seconds wall, 335,988 KiB
peak RSS). Core Ruff/format/strict mypy, the eight-case Workbench component
suite, TypeScript, targeted ESLint/Prettier, and diff checks are green.

At `2026-10-27T20:38:38Z`, memory PSI avg10 was 43.32% (`some`) / 38.72%
(`full`), avg60 35.73% / 31.92%, avg300 30.48% / 27.39%; 9.9 GiB was
available and 481,060 KiB swap remained free. This is not adequate evidence to
admit the larger frontend build or browser process pair yet. Full web tests,
production build, and Frontier E2E are still pending. Worktree modifications
are limited to this ledger, `docs/MIDAS_CURRENT_STATE.md`, and the engineering
report's commit-identity note. No source request, Reality service action, or
production transition occurred.

## Web and browser verification; Arena admission blocker — 2026-10-27 20:43 UTC

The full Web unit suite passed **40/40** across seven files in 5.25 seconds
wall at **322,452 KiB peak RSS**. `npm run build` passed TypeScript project
build and Vite in 12.50 seconds wall at **692,056 KiB peak RSS** (2,228 modules).
The Frontier bundle is 102.13 kB JS / 35.87 kB CSS. Vite reports the existing
544.41 kB Chart chunk above its 500 kB advisory threshold; the build succeeds.

The dedicated Frontier Playwright spec passed **4/4** in 11.12 seconds wall
at **192,508 KiB peak RSS**. The full 12-case browser run completed **10/12**
in 57.66 seconds wall at **193,596 KiB peak RSS**: all Frontier and other
non-Laboratory cases passed. The two Laboratory browser cases were denied by
`resource_admission_lock_busy` before any worker was launched. The temporary
API used isolated demo database, Arena, and Frontier roots; Veritas was
read-only from the isolated worktree.

The host-wide lock is `/home/charlie/midas/data/arena/.global-admission.lock`;
its active `flock` was held at `2026-10-27T20:43:15Z` by PID **3681242**,
running `scripts/veritas_gap_detail_v2_batch.py` with the primary and Veritas
Arena roots. The worker was already active before the browser run. It and its
lock were left untouched. Do not bypass the lock or retry Laboratory launches
until the global slot is released. `ps` after Playwright showed the managed API
and browser processes had stopped; only the pre-existing batch holder remained.

The v13 code and report changes are committed in `e50ba34`; v13 test-handoff
documentation is in `05433d2`. This browser/build checkpoint is documentation
only and remains to be committed. At `2026-10-27T20:43:15Z`, system memory PSI
avg10 was 45.75% (`some`) / 41.58% (`full`), avg60 43.43% / 38.30%, avg300
37.69% / 33.23%; 9.9 GiB was available, swap free was 481,192 KiB. No source
API, protected service, evidence store, or production deployment was accessed.
Frontier overall remains **PARTIALLY VERIFIED** due to live cross-venue
validation, permission/deployment gates, and the two lock-blocked Laboratory
browser cases.

## Official source terms refresh — 2026-10-27 20:45 UTC

Read-only official documentation review confirmed the existing source boundary.
Kalshi's Developer Agreement v1.1 still limits API use to a member's own
trading; its separate Data Terms restrict collection, systematic extraction,
and software development use without prior written authorization. Kraken's
current regional terms still require approved purposes or prior permission for
other uses of content, and the EEA terms explicitly identify pricing data as
content. The API Center lists public data endpoints but the reviewed material
does not settle Frontier's exact research/retention rights or the user's
applicable regional agreement. Polymarket Institute's July 24 research guide
still describes open APIs for researchers and separates the decentralized and
US-only systems and their data.

Kalshi/Kraken probes and stored research remain blocked/quarantined; no source
policy changed. No exchange API was queried, exchange contacted, or held capture
opened. The full source rationale and official references are in
[`SOURCE_DATA_TERMS_REVIEW_2026-10-27.md`](SOURCE_DATA_TERMS_REVIEW_2026-10-27.md).
This documentation-only checkpoint remains **PARTIALLY VERIFIED**; live
cross-venue economics and production gates are unresolved.

## Arena admission recheck — 2026-10-27 20:47 UTC

The earlier holder PID 3681242 had exited, but a new bounded
`veritas_gap_detail_v2_batch.py` process (PID **3690476**) acquired the same
host-wide lock inode **6423106** at
`/home/charlie/midas/data/arena/.global-admission.lock`. Memory PSI at the
recheck was 38.74% (`some`) / 33.82% (`full`) avg10, 11.52% / 10.26% avg60,
and 20.77% / 18.43% avg300. The protected Reality recorder was also present in
the process listing. No full-suite browser retry was started; no lock was
bypassed and no worker or service was touched. The prior browser result remains
10/12, with both Laboratory tests denied before work launched; dedicated
Frontier E2E remains 4/4. Resume the two Laboratory cases only after the
shared admission slot releases and host pressure is acceptable.

## Bounded coverage analytics checkpoint — 2026-10-27 22:13 UTC

Code commit **`4c9a8d8`** adds the local `GET /api/frontier/analytics/coverage`
endpoint and a native **Coverage & quality** workspace. Commit **`66e89a5`**
then tightens repeated-candidate identity to include pinned market-observation
IDs and canonical quote denominations, preventing candidates with changed
economic identity from being grouped as recurring. The API summarizes at
most 50 market records, 50 hash-checked book observations, 20 eligible replay
runs, and 5,000 candidate records. It also reports eligible persisted
market/instrument identity counts by venue from the store indexes. Held venues
are filtered. Pricing groups preserve venue, instrument type, quantity unit,
and exact quote denomination; bad joins, conflicting native-market aliases,
stale/future timestamps, and delimiter-colliding asset identities fail closed
or remain explicitly qualified. The UI reports source freshness separately
from structural book quality, bounded candidate classifications, rejection
reasons, timing summaries, and gross-only repeated constructions.

Files in `4c9a8d8`: `apps/api/frontier.py`,
`packages/midas/frontier/analytics.py`, `apps/web/src/Frontier.tsx`,
`apps/web/src/Frontier.test.tsx`, `apps/web/e2e/frontier.spec.ts`,
`tests/frontier/test_analytics.py`, and `tests/frontier/test_api.py`.
Commit `66e89a5` updates `packages/midas/frontier/analytics.py` and adds a
regression to `tests/frontier/test_analytics.py`.

The final `tests/frontier` suite passes **279/279** in 70.89 seconds wall at
**354,788 KiB peak RSS**, zero swaps; one existing Starlette/httpx TestClient
deprecation warning remains. The full Web suite passes **40/40** in 16.10
seconds wall at **333,216 KiB peak RSS**, zero swaps. Strict mypy passes for the
analytics module and Frontier API; Ruff check/format, targeted ESLint,
Prettier, TypeScript typecheck, and `git diff --check` pass. The production
Vite build transforms 2,228 modules in 5.46 seconds at **667,976 KiB peak RSS**
and zero swaps, writing to `/tmp/midas-frontier-build-20261027-2206`; the
Frontier chunk is 112.13 kB JS / 36.10 kB CSS. The pre-existing 544.41 kB Chart
chunk advisory remains. A dedicated isolated browser E2E passes **1/1** in
6.62 seconds wall at **186,788 KiB peak RSS**, confirming a 200 no-network API
response and no source-probe request. The implementation uses only local
evidence and fixtures; no exchange API, protected recorder, held capture, or
production service was accessed.

The Web suite, dedicated E2E, and Vite build preceded the backend-only
signature follow-up `66e89a5`. The final full Frontier suite and strict mypy
check of the changed analytics module were rerun after that follow-up; no
frontend source changed in `66e89a5`.

Frontier remains **PARTIALLY VERIFIED** and undeployed. This checkpoint does
not validate current public market coverage, terms/permission for blocked
Kalshi or Kraken research, live cross-venue equivalence, synchronized
execution, positive net economics, or production deployment. The full browser
suite is not rerun at this checkpoint; the changed Coverage & quality view is
covered by the 40-case Web suite and isolated 1-case E2E above. Next safe work:
extend populated-analytics browser coverage if useful, then continue the
remaining offline acceptance gaps without accessing held sources.

Reproduction commands from `/home/charlie/midas-frontier`:

```bash
env PYTHONPATH=packages:.:tests /home/charlie/midas/.venv/bin/pytest tests/frontier -q
corepack pnpm --dir apps/web exec vitest run --maxWorkers=1 --minWorkers=1
corepack pnpm --dir apps/web run typecheck
corepack pnpm --dir apps/web exec eslint src/Frontier.tsx src/Frontier.test.tsx
corepack pnpm --dir apps/web exec prettier --check src/Frontier.tsx src/Frontier.test.tsx
MYPYPATH=packages /home/charlie/midas/.venv/bin/mypy --strict --follow-imports=silent packages/midas/frontier/analytics.py apps/api/frontier.py
corepack pnpm --dir apps/web exec vite build --outDir /tmp/midas-frontier-build-20261027-2206
corepack pnpm --dir apps/web exec playwright test e2e/frontier.spec.ts --grep 'Frontier workspace uses isolated research state and remains responsive' --workers=1
```

### Full web regression — 2026-10-27 23:56 UTC

The full web unit suite passes **40/40 across seven files** in 15.55 seconds
reported / 15.97 seconds wall at **300,960 KiB peak RSS**, with zero swaps.
This includes all Frontier components and checks unrelated Mission Control
views for UI regressions. No API server or exchange source was contacted by
this unit-test invocation.

### Full Frontier browser regression — 2026-10-27 23:57 UTC

The full `e2e/frontier.spec.ts` passes **4/4** with one worker in 11.5 seconds
reported / 12.05 seconds wall, **192,280 KiB peak RSS**, zero swaps. It covers
responsive isolated workspace behavior, read-only/no-launch replay history,
fixture-only Kalshi settlement arithmetic, and bounded responsive graph
exploration. The first case also confirms that loading Exchanges history
submits no collection or source-probe POST. Playwright used its isolated test
API/database/Arena roots; no live exchange endpoint was called.

## Arena admission-test follow-up — 2026-10-27 23:55 UTC

After the external batch exited, the two supervisor tests denied during the
combined run were rerun alone and passed **2/2** in 3.73 seconds pytest time /
4.34 seconds wall, **179,752 KiB peak RSS**, zero swaps. The command was:

```bash
env PYTHONPATH=packages:.:tests /home/charlie/midas/.venv/bin/pytest tests/arena/test_jobs.py::test_supervised_job_runner_imports_the_submitted_checkout tests/arena/test_jobs.py::test_veritas_qualification_supervisor_has_read_only_resource_bounds -q
```

These tests replace process launch with a fixture, so no Arena worker was
started. Before the rerun the global lock was free, PSI avg10 was 0%, and 10
GiB was available. The earlier combined invocation still ended with two
environmental denials; across the combined run and this targeted rerun, all
360 selected cases passed. The full combined command was not repeated to avoid
re-running the already-passed 358 cases. No service or external process was
modified.

## Bounded event-time replay checkpoint — 2026-10-27 22:24 UTC

Code commit **`30576f1`** adds `packages/midas/frontier/timeline.py` and
`tests/frontier/test_timeline.py`. The offline event-time engine handles
repeated book observations per instrument, explicit cutoffs, freshness expiry,
source degradation/outage/recovery, and relationship evidence timing. It
reuses existing deterministic replay and independent economic auditing per
frame. It pins the normalized inputs and each replay frame, reports selected
observation IDs and exclusion reasons, and rejects pre-interruption books until
a new post-interruption snapshot arrives. It does not assume executable fills.

The four new tests cover quote deterioration, exact freshness-boundary and
stale-leg behavior, source interruption and revalidation, reproducibility under
input reordering, and prevention of future relationship/source-state lookahead.
Final verification: `tests/frontier` **283/283**, 69.44 seconds pytest time /
70.69 seconds wall, **355,720 KiB peak RSS**, zero swaps; timeline-only tests
**4/4**, 0.69 seconds, **54,864 KiB peak RSS**, zero swaps; strict mypy for the
new module, Ruff check/format, and `git diff --check` pass. The only suite
warning is the existing Starlette/httpx TestClient deprecation.

Documentation updates are in `docs/frontier/FRONTIER_ARCHITECTURE.md`,
`docs/frontier/FRONTIER_ENGINEERING_REPORT.md`,
`docs/DEVELOPMENT.md`, and `docs/MIDAS_CURRENT_STATE.md`. No API, source,
protected service, held capture, production store, or Arena job was used. The
engine remains unavailable through the HTTP API, Arena artifact flow, and
Mission Control; those are outstanding integration tasks. Overall Frontier
remains **PARTIALLY VERIFIED**, isolated, research-only, and undeployed. Next
safe engineering work is bounded restart-safe collection and local Arena
timeline integration, with no persistent worker launch.

## Finite collection history and explicit resume — 2026-10-27 23:53 UTC

Code commit **`305814b`** closes the HTTP recovery gap for the finite capture
path. `GET /api/frontier/collection-runs?limit=20` performs a bounded,
read-only scan, returns recent local checkpoints only after validating each
selected run's complete hash chain, filters held venues, and does not create a
missing journal or contact a source. The Exchanges view shows checkpoint
identity, state, counts, source-local health, and the reason a run cannot be
resumed.

`POST /api/frontier/collect/{venue}/{run_id}/resume` is an explicit operator
action for a single nonterminal run. The route and collector recheck source
enablement, policy holds, pinned source config, adapter version and capability
manifest, required capabilities, source market limit, and the API's smaller
resume bounds before source requests or pending-capture recovery. Terminal
runs return their existing result without another request. There is no retry
loop, worker, timer, or automatic resume. Request counts are labeled as total
over the run, while the returned request ceiling is explicitly per attempt.

#### Verification

- `tests/frontier/test_collection.py` and
  `tests/frontier/test_collection_api.py`: **20/20 passed** in 6.15 seconds
  pytest time / 6.71 seconds wall, **87,036 KiB peak RSS**, zero swaps. This
  includes pause/resume, empty non-mutating history, terminal idempotence,
  held/disabled resume rejection before requests, and changed capability
  manifest rejection.
- `apps/web/src/Frontier.test.tsx`: **8/8 passed** in 4.08 seconds wall,
  **217,316 KiB peak RSS**, zero swaps. The fixture flow shows a paused run,
  invokes resume only after a click, and removes the resume action when the
  run is terminal.
- Isolated Frontier Playwright case: **1/1 passed** in 6.29 seconds wall,
  **186,140 KiB peak RSS**, zero swaps. Exchanges history made a local GET
  reporting `network_called=false`; no collection or source-probe POST was
  submitted automatically.
- TypeScript, strict scoped mypy for `collection.py` and `frontier.py`, Ruff
  check/format, ESLint, Prettier, and `git diff --check` pass. Production Vite
  build passes in 4.93 seconds at **690,080 KiB peak RSS**, zero swaps, with
  build output written to `/tmp/midas-frontier-build-20261028-0049`. The
  pre-existing 544.41 kB Chart chunk advisory remains.
- Combined Frontier and selected Arena replay/timeline/job/API regressions:
  **358 passed, 2 failed** in 84.16 seconds, **369,092 KiB peak RSS**, zero
  swaps. All `tests/frontier` tests passed. The two failures are existing
  Arena supervisor tests rejected by `resource_admission_lock_busy`; the
  shared lock was acquired during the run by existing Veritas batch PID
  **3939942** in `D` state. It was not touched. At the 23:53 UTC recheck it
  still held `/home/charlie/midas/data/arena/.global-admission.lock`; memory
  PSI avg10 was **49.25% some / 42.91% full**, with **9.7 GiB available** and
  **3.7 GiB swap in use**. Do not retry the admission-dependent cases while
  this state persists.

No live source request, protected recorder action, held capture read, Arena
worker launch, or production change occurred. Collection remains disabled by
default; this is fixture-backed development verification only.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Finite capture start, local run history, and explicit resume | COMPLETE AND VERIFIED | Fixture API/module tests; live source use remains pending and disabled by default. |
| Adapter-policy and manifest revalidation | COMPLETE AND VERIFIED | Collector and API reject changed/held configurations before additional source requests. |
| Exchanges-view history and resume | PARTIALLY VERIFIED | Component and isolated browser tests pass; no live capture or populated real-source history was available. |
| Frontier and selected Arena regressions | PARTIALLY VERIFIED | All Frontier tests passed in the combined run; the two shared-lock-denied Arena supervisor cases passed separately after release. All 360 selected cases pass across two invocations, with no single clean combined run. |
| Production build and browser smoke | COMPLETE AND VERIFIED | Build and isolated browser case pass for `305814b`; no production deployment. |
| Cross-venue live relationships/economics and deployment | DEFERRED | No genuine cross-venue observation was established; protected source policy and separate deployment review remain. |

Frontier remains isolated, research-only, undeployed, and **PARTIALLY VERIFIED**.
Next safe work is offline acceptance and documentation; avoid further
admission-dependent jobs until the Veritas batch releases the shared lock and
fresh resource measurements support another bounded run.

#### Reproduction commands

Run the focused, low-resource collection checks first:

```bash
env PYTHONPATH=packages:.:tests /home/charlie/midas/.venv/bin/pytest tests/frontier/test_collection.py tests/frontier/test_collection_api.py -q
corepack pnpm --dir apps/web exec vitest run src/Frontier.test.tsx --maxWorkers=1 --minWorkers=1
corepack pnpm --dir apps/web exec vitest run --maxWorkers=1 --minWorkers=1
```

The broader regression selection used for this checkpoint was:

```bash
env PYTHONPATH=packages:.:tests /home/charlie/midas/.venv/bin/pytest tests/frontier tests/arena/test_frontier_replay.py tests/arena/test_frontier_timeline.py tests/arena/test_jobs.py tests/arena/test_arena_api.py -q
```

Before repeating any test that stages Arena work, remeasure memory pressure
and verify the host-wide `/home/charlie/midas/data/arena/.global-admission.lock`
is free. The build and isolated browser commands were:

```bash
corepack pnpm --dir apps/web exec vite build --outDir /tmp/midas-frontier-build-20261028-0049
corepack pnpm --dir apps/web exec playwright test e2e/frontier.spec.ts --grep 'Frontier workspace uses isolated research state and remains responsive' --workers=1
corepack pnpm --dir apps/web exec playwright test e2e/frontier.spec.ts --workers=1
```

### Collection history policy and checkpoint-chain regressions — 2026-10-28 00:00 UTC

Commit `a7996f9` adds two focused collection regressions: a source that is
currently held is omitted from collection history without a network request,
and `latest_run_checkpoints()` rejects a checkpoint chain whose stored digest
has been tampered with. The focused collection module/API suite passes **21/21**
in 6.06 seconds reported by pytest / 6.53 seconds wall, with **87,676 KiB peak
RSS** and zero swaps. Ruff and `git diff --check` pass.

The test run used fake adapters and temporary storage; it made no source
request, read no held capture, and started no Arena worker. At 00:00:12 UTC the
shared admission lock was free, PSI avg10 was 0.64% `some` / 0.58% `full`, and
10 GiB was available; this is a dated host sample, not a standing resource
guarantee. The broader suites were not repeated because implementation code
did not change. Frontier remains isolated, research-only, undeployed, and
**PARTIALLY VERIFIED**. Continue with offline acceptance gaps; preserve the
source-use and production boundaries.

### Missing-adapter collection responses — 2026-10-28 00:02 UTC

Commit `169bfa2` makes finite collection start and resume return HTTP 409 with a
clear unavailable-adapter detail when a supported venue has no registered
adapter. Both routes reject before collection-journal creation or lookup. The
collection API module passes **6/6** in 1.98 seconds reported by pytest / 2.52
seconds wall, at **84,136 KiB peak RSS** and zero swaps; Ruff and
`git diff --check` pass. The existing Starlette/httpx deprecation warning
remains.

At 00:02:40 UTC, the unrelated shared Arena admission lock was held by PID
3950719, PSI avg10 was **41.99% some / 37.85% full**, and 10 GiB was available
with 3.7 GiB swap in use. The API test did not acquire that lock or start an
Arena worker. Avoid Arena-dependent tests while the lock and pressure remain;
continue with read-only review or small isolated checks. Frontier remains
research-only, undeployed, and **PARTIALLY VERIFIED**.

### Unregistered adapter handling across source routes — 2026-10-28 00:04 UTC

Commit `01ffe05` applies the unavailable-adapter guard to the source-specific
trade, fee, market-detail, event-group and multivariate probes, as well as the
generic discovery probe. Together with `169bfa2`, every source-facing request
now reports HTTP 409 when the requested adapter is missing. The focused
regression exercises collection start, collection resume, and generic
market discovery against an empty registry; it passes **1/1** in 0.65 seconds,
at **75,800 KiB peak RSS**, with zero swaps. Ruff and `git diff --check` pass.
The existing Starlette/httpx deprecation warning remains.

The resource sample just before this test (00:04:26 UTC) showed PSI avg10
**11.06% some / 9.93% full**, avg60 **33.28% some / 29.88% full**, 10 GiB
available, and no process holding the shared Arena lock at that instant. Keep
Arena-dependent work deferred until another fresh admission check. No source
request or Arena worker ran. Frontier remains isolated, research-only,
undeployed, and **PARTIALLY VERIFIED**.

### Collection history with an absent adapter — 2026-10-28 00:05 UTC

Commit `b2e3eed` adds a regression proving that a hash-verified paused run
remains visible in the local history after its adapter is unregistered. The API
keeps the run non-resumable with the reason “The pinned source adapter is not
registered.” and reports `network_called: false`. The test passes **1/1** in
0.69 seconds at **72,864 KiB peak RSS**, zero swaps. Ruff and
`git diff --check` pass; the existing Starlette/httpx deprecation warning
remains.

The pre-test host sample at 00:05:01 UTC had PSI avg10 **0.36% some / 0.33%
full**, avg60 **18.90% some / 16.97% full**, 10 GiB available, and no visible
Arena admission-lock holder. No source adapter, network request, or Arena
worker was used. Frontier remains isolated, research-only, undeployed, and
**PARTIALLY VERIFIED**.

### Official source terms refresh — 2026-10-28

A read-only review of official public terms confirmed that the Kalshi API hold
still applies to Frontier's research and retention use. The current Kraken
Global/EEA terms preserve uncertainty around automated extraction and the
permitted scope for research storage; its public Spot REST limit guidance says
one request per second or less remains within published limits, matching the
adapter's generic default. Coinbase's Market Data Terms permit limited
personal or organizational research but add restrictions on third-party
redistribution, specified benchmarks/valuations, and AI/ML research. The exact
fit for Frontier's stored spot-context analytics remains unresolved, so the
existing terms-version gate stays in force. No configuration or code changed,
and no exchange endpoint or stored capture was accessed. Full sources and
scope notes are in
[the source-data terms review](SOURCE_DATA_TERMS_REVIEW_2026-10-27.md).

### Virtual funding-currency sensitivity — 2026-10-28 00:22 UTC

Code commit `530c9aa8b3fb2b4ee006c35c2494bccdb0b7cae8` adds a non-classifying
virtual funding-currency sensitivity for saved candidates. The new pure model,
saved-run API route, and Mission Control workbench accept a distinct full asset
identity, virtual balance, explicit target-units-per-funding-unit rate, and
conversion fee for each candidate venue. No rate is retrieved or inferred; UI
rate/fee fields are blank for different identities. Venue balances remain
separate. An independent Fraction pass checks Decimal calculations, with
input/result hashes bound to the saved candidate. Candidate classification,
practical eligibility, and P&L stay unchanged; unresolved candidate fee legs
remain labelled.

Before the size-bound follow-up, the focused Python selection passed **39/39**
in 1.63 seconds: FX sensitivity,
capital-carry regression, and the saved-run API integration. It includes 30
bounded generated rate/fee/balance cases, different namespaced asset identities,
invalid assumptions, tamper detection, no implicit same-identity conversion,
and stale saved-run hash rejection. The `Frontier.test.tsx` selection passed
**8/8** in 4.23 seconds. TypeScript and the Vite production build passed;
ESLint, Prettier, Ruff, formatting, `git diff --check`, and strict mypy for the
new FX module passed. The Vite build emitted the 544.41 kB Chart-chunk advisory.
Unsuppressed strict mypy on the API module still reports its existing
`no-any-return` at the adapter lookup (`apps/api/frontier.py:1052`); suppressing
that existing code while checking the module finds no other errors.

The first arithmetic test found a 28-digit default-context sum in the
independent fee audit, which was corrected. The 30-example generated test then
found a last-digit shortfall disagreement at 96-digit division; the independent
audit now reproduces that rounding point while checking coverage exactly. No
Playwright run, full Frontier suite, performance profile, FX source, genuine
cross-venue relationship, or live conversion was established.

At `2026-10-28T00:20:21Z`, memory PSI avg10 was **45.09% some / 39.20% full**,
MemAvailable was **10,087 MiB**, and swap use was **3,768 MiB**. An external
Veritas gap-detail batch, PID **3960724**, remained active; it was left
untouched. No exchange request, source capture, Reality process, protected
service, Arena worker, production store, or deployment was used.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Virtual funding-currency model and API | COMPLETE AND VERIFIED | Offline exact-identity, hashing, bounds, venue isolation, generated arithmetic, tamper, and stale-run checks pass. This does not establish an available conversion market. |
| Mission Control funding workbench | PARTIALLY VERIFIED | Component, type, lint, and production build pass; browser automation remains pending resource admission. |
| Live FX and capital transfer | DEFERRED | No source rates, custody, jurisdiction, transfer, collateral, or executable funding evidence is connected. |
| Project Frontier overall | PARTIALLY VERIFIED | Live cross-venue validation, broad regression, browser acceptance, resource sustainability, and deployment remain incomplete. |

Test follow-up commit `87c67b23fbda1624a6b36273b63cd94427113b4c` adds fail-closed
checks for oversized external balance strings and candidate capital magnitude.
The focused Python selection now passes **40/40** in 1.26 seconds. The initial
implementation commit is `530c9aa8b3fb2b4ee006c35c2494bccdb0b7cae8`.

Continue with bounded offline acceptance; do not treat the explicit FX scenario
as sourced or executable economics.

### Funding-currency browser acceptance and full Frontier regression — 2026-10-28 00:27 UTC

Commit `86b79fe10b6aed82dabbe3e40ea01e08923ad744` adds a browser regression for the saved-candidate funding-currency workbench. The fixture changes Kalshi funding from USD to EUR; the UI requires a user-entered rate and fee, keeps Kalshi and Polymarket balances separate, and displays the saved candidate classification as unchanged. The first browser run exposed an assertion expecting one unresolved-fee notice although both venue rows correctly showed one. The selector was fixed to assert both rows; the targeted test and then the full suite passed.

Verification:

- `pytest tests/frontier -q`: **322 passed** in 50.72 seconds; 52.04 seconds wall, **364,312 KiB peak RSS**, zero swaps, zero socket messages. One existing Starlette/httpx deprecation warning remains.
- `corepack pnpm test` in `apps/web`: **40 passed** across seven files in 5.32 seconds.
- `corepack pnpm exec playwright test --workers=1`: **12 passed** in 27.4 seconds using isolated demo API/web services and temporary databases. The funding-currency browser response is intercepted fixture data; the saved-run API is covered independently by Python tests.
- Prettier, ESLint for the changed browser file, and `git diff --check` passed. This test-only commit did not rerun the production web build; typecheck and Vite build passed at the prior implementation checkpoint.

At the post-test sample `2026-10-28T00:27:27Z`, memory PSI avg10 was **17.09% some / 11.86% full**, MemAvailable was **9,858,420 KiB**, and SwapFree was **335,952 KiB**. These short tests do not establish long-run resource sustainability. No exchange endpoint, protected Reality process, production store, deployment, Arena campaign, or long-running worker was used.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Frontier Python suite | COMPLETE AND VERIFIED | 322 Frontier tests pass, including adapters, relationships, replay, saved-run API, and FX arithmetic. This is not the full repository suite. |
| Mission Control browser workflow | PARTIALLY VERIFIED | All 40 unit and 12 E2E tests pass; the FX browser response is fixture-intercepted and its API is separately fixture-tested. No live rate or conversion is established. |
| Test resource profile | PARTIALLY VERIFIED | One run measured 364,312 KiB peak RSS and zero swaps; concurrent operation, sustained collection, and production admission are unmeasured. |
| Genuine cross-venue economics / production | DEFERRED | Source-use permission, synchronized market evidence, FX availability, transfer constraints, and deployment remain unresolved. |
| Project Frontier overall | PARTIALLY VERIFIED | Offline functionality has broad passing regressions; live multi-venue evidence and production gates remain open. |

### Strict API typing check deferred under shared-host pressure — 2026-10-28 00:31 UTC

A targeted strict mypy retry for `apps/api/frontier.py` was started after a read-only review found that the router accepts `registry: Any`, causing the existing `no-any-return` diagnostic on the adapter lookup despite the concrete `AdapterRegistry.get` contract. The temporary annotation change to `AdapterRegistry` was discarded because the check did not complete. After 25.34 seconds at 99% CPU, mypy had reached **694,744 KiB peak RSS** without a result; I sent SIGTERM only to that mypy process. It used zero swaps and changed no files. At `2026-10-28T00:31:15Z`, PSI avg10 was **24.98% some / 19.55% full**, MemAvailable was **9,799,260 KiB**, and the separate Veritas gap-detail batch PID **3975405** remained active. It was left untouched.

The scoped API typing issue remains open and is not treated as a pass or code failure. Retry after shared-host pressure subsides with a smaller type-check scope or controlled cache; do not reconfigure or interrupt the external batch. Frontier remains at the previously verified **PARTIALLY VERIFIED** checkpoint.

### Strict API registry typing completed — 2026-10-28 00:35 UTC

The external Veritas batch was no longer present and a fresh resource sample showed memory PSI avg10 below 1% with about 10 GiB available. Commit `480ba629171c855086cd375a34e688bbc72fdbcb` replaces the Frontier router's `registry: Any` with the concrete `AdapterRegistry` contract. This removes the `no-any-return` issue at adapter lookup without changing runtime behavior.

Strict mypy passed for `apps/api/frontier.py` with no issues in 27.22 seconds, **717,964 KiB peak RSS**, zero swaps and zero socket messages. Ruff and format checks passed. The isolated API overview test passed **1/1** in 0.70 seconds, **77,492 KiB peak RSS**, zero swaps/socket messages; one existing Starlette/httpx deprecation warning remains. The full 322-test Frontier, 40-test web, and 12-test browser suites are from the prior code checkpoint and were not rerun after this type-only change. The earlier 00:31 mypy attempt was stopped during high pressure and yielded no result; this successful retry supersedes it. No external batch or protected service was touched.

Frontier remains **PARTIALLY VERIFIED**. Continue offline implementation and acceptance; do not access currently held source data or deploy.

### Discovery-scope comparison and Arena artifact path — 2026-10-28 02:40 UTC

Code commit `d59c4a8e66af7d525e65b70d90c268d3eaa92cfe` adds a deterministic
comparison across Polymarket-only, venue-local, and cross-venue discovery
scopes. It uses the same saved markets/books, replay implementation, scenario,
and pinned UTC time. It reports instrument/book coverage, verified relationship
counts, candidates, classifications, audit dispositions, and pairwise deltas.
It does not compare independent algorithm versions, infer venue-wide prevalence,
or certify a relationship beyond the existing strict evidence checks.

The `frontier_discovery` Arena job persists an 8 MiB-bounded content-addressed
input, applies the normal host resource gate and 300-second/512-MiB/50%-CPU
limits, writes a result capped at 32 MiB, and binds the result to its durable
job record. The Frontier API stages only locally saved evidence and reports
`network_calls: 0`; the UI exposes bounded history and integrity-verified
results. Held-source filtering is applied to input staging, job history, and
result access.

Verification at this checkpoint:

- `tests/frontier/test_discovery_comparison.py`, `tests/arena/test_frontier_discovery.py`, and the new staging API test passed in the full selection.
- The full web unit suite passed **40/40**; TypeScript, ESLint, Prettier, Ruff, Python compilation, and `git diff --check` passed.
- The production build succeeded; the existing **544.41 kB** chart chunk advisory remains.
- The isolated Replay & Readiness history browser test passed **1/1**. It verified empty history and no automatic job submission or source probe.
- `tests/frontier` plus the related Arena discovery/replay/timeline/job selection completed **375 passed / 6 failed** in **79.10 seconds**. The six failures were in generic existing job-supervision cases, not the new discovery tests. A contemporaneous lock inspection found PID **4086834** (`scripts/veritas_gap_detail_v2_batch.py`) holding the shared Arena admission lock. Four temporary test jobs remained queued; two create attempts reported `resource_admission_lock_busy`. No Arena worker launched from those tests; the active batch was not interrupted.
- Strict mypy initially found two local typing issues in `discovery_comparison.py`; both were corrected. The same invocation also reported 15 diagnostics in existing Veritas/Arena dependencies. A post-fix scoped rerun was stopped without a result after PSI avg10 measured **30.44% some / 27.78% full**, with **331 MiB** swap free. Strict typing for this checkpoint remains unverified.

No source endpoint, protected Reality service, preserved capture, production database, or deployment was accessed. A direct fixture call validates discovery artifact generation, hashing, snapshot reconstruction, and tamper detection, but no `frontier_discovery` job has completed through the Arena supervisor. Resource sustainability, live source validation, verified public cross-venue equivalence, and production remain open. Continue only after a fresh host admission check; do not bypass the global lock or resource gate.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Discovery-scope deterministic comparison | COMPLETE AND VERIFIED | Fixture tests verify same-engine scope comparison, coverage counts, candidate summaries, deltas, and deterministic hashes. This is not independent-algorithm evaluation or venue-wide prevalence. |
| Snapshot and result integrity | COMPLETE AND VERIFIED | Direct worker-function fixture verifies content addressing, hash-checked readback, job binding, limits, and tamper rejection. Supervisor execution is pending. |
| API staging and held-source boundary | COMPLETE AND VERIFIED | Isolated API test proves local saved inputs are bounded and no probe is called; existing held-source checks are reused for history/result access. |
| Mission Control discovery comparison | PARTIALLY VERIFIED | 40/40 unit tests, TypeScript, lint, production build, and 1/1 isolated history E2E pass; full submission flow is fixture-tested in the unit test. |
| General Arena job-supervision regression | PARTIALLY VERIFIED | Six tests could not acquire the shared host lock during an active external Veritas batch; no worker was launched. |
| Strict typing / resource sustainability | PARTIALLY VERIFIED | Local mypy findings were fixed, but the scoped retry stopped during high PSI; no sustained worker profile exists. |
| Genuine cross-venue public finding / deployment | DEFERRED | Source-use restrictions, external semantic evidence, synchronized pricing, supervisor admission, and production gates remain unresolved. |
| Project Frontier overall | PARTIALLY VERIFIED | This offline discovery comparison extends the existing system but does not close the mission's live evidence or deployment criteria. |

### Latest-book selection for discovery snapshots — 2026-10-28 02:45 UTC

Code commit `3f084a99732b0cb610bafe18aacaf13fb54a92c2` fixes a duplicate-book
staging defect. `_load_book_records` returns the bounded observations in
newest-first local-receipt order; the discovery-scope route now selects one
book per `(venue, native_market_id, native_instrument_id)`, retaining the most
recent record and its immutable observation ID. Result ordering is deterministic.

The expanded staging API test stores two book observations for the same
instrument and proves that the newer quote and observation ID enter the pinned
snapshot. `tests/frontier/test_api.py` passes **53/53** in 26.37 seconds pytest
time / 27.35 seconds process wall, **284,280 KiB peak RSS**, zero swaps, and zero
socket messages. The focused scope comparison and Arena-artifact tests pass
**4/4** in 2.43 seconds at **194,060 KiB peak RSS**. Ruff check/format, Python
compilation, and `git diff --check` pass. The test uses only a temporary SQLite
store and monkeypatched job creation; no source request or Arena worker runs.

At `2026-10-28T02:45:28Z`, host memory PSI was avg10 **0.00% some / 0.00% full**
and avg60 **3.64% some / 3.30% full**, with about **10 GiB** available and
**332 MiB** swap free. No Arena lock holder was present at that sample. This is
a dated local observation, not a sustained resource admission. Strict mypy was
not rerun, the new discovery job has not completed through the Arena supervisor,
and live or production validation remains out of scope for this checkpoint.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Discovery snapshot book selection | COMPLETE AND VERIFIED | Repeated observations collapse to the most recently received local snapshot per instrument with its exact observation ID; API, full API module, and direct scope/Arena tests pass. This does not establish exchange-time synchronization or freshness. |
| Arena discovery supervisor and sustained resources | PARTIALLY VERIFIED | Artifact execution and job schema are fixture-tested; actual supervisor admission and representative runtime are pending. |
| Project Frontier overall | PARTIALLY VERIFIED | The snapshot correction improves local replay integrity; source permission, cross-venue validation, broad science acceptance, and deployment remain open. |

### Official source terms supplement — 2026-10-28 03:00 UTC

Read current official Kalshi Data Terms and API quick start, Kraken API
guidance and current EEA Terms, and Coinbase Market Data Terms. The review
confirmed that unauthenticated public endpoints do not by themselves permit
Frontier's systematic collection, software development, retention, or research
use. Kraken's API guidance calls for prior permission for certain uses,
including non-personal commercial use of public market data; Coinbase's terms
prohibit AI/ML development use and specified benchmark/valuation uses. No API
call, contact, capture read, setting change, or policy change occurred. Keep
all existing source holds. Detailed sources are recorded in
`docs/frontier/SOURCE_DATA_TERMS_REVIEW_2026-10-27.md`.

### Bounded Frontier discovery through the real Arena supervisor — 2026-10-28

One synthetic `frontier_discovery` job completed through `midas.arena.jobs`
and the user's actual transient systemd service, using the real host-wide
admission lock and resource snapshot. It ran after the `03:00:30Z` clock
sample and completed before the `03:03:40Z` post-run sample; the exact worker
start time was not separately captured. Admission passed. The pinned input and
all job artifacts lived under a temporary directory; the job used the
AF_UNIX-only network restriction and the configured 300-second, 512-MiB,
zero-swap, 50%-CPU limits. It returned two fixture candidates and its saved
result passed the independent artifact/hash verifier. The job ID was
`job-16457e8fea8a483d8d10c8df` and result hash
`c4c753fd209b0857a522a19054d82793c65b03c31c33890915cf4c0f64982e36`.

While active, systemd reported `MemoryMax=536870912`, `MemorySwapMax=0`,
`CPUQuotaPerSecUSec=500ms`, and cgroup `MemoryPeak=117252096` bytes. The worker
process reported peak RSS **170,110,976 bytes**, user CPU **0.066162 seconds**,
and system CPU **0.010004 seconds**. Process and cgroup memory high-water
figures differ and are retained as separate measurements; this single sample
does not reconcile their accounting scopes or establish a sustained capacity
limit. The bounded supervisor smoke command took **5.9 seconds wall**; the
worker's own elapsed field was not retained. After the worker exited,
systemd reported the transient unit as not found/inactive/dead with
`Result=success`, and no matching worker process remained.

The after-run host sample at `2026-10-28T03:03:40Z` showed memory PSI avg10
**49.40% some / 41.21% full**, about **9.8 GiB** available, and about **332
MiB** swap free. The pressure is not attributed to the short worker; it is a
reason to defer any additional heavy run until a fresh admission check. A
Starlette/httpx TestClient deprecation warning arose from importing the
fixture builder module. No exchange request, held capture, production Arena
root write, protected service, or persistent unit was used.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Synthetic discovery through actual systemd and host admission | COMPLETE AND VERIFIED | One temporary-root job completed under real host admission and systemd limits; its content-addressed artifact passed verification. It used fixtures only and one short run. |
| Worker resource sustainability | PARTIALLY VERIFIED | Systemd resource properties and one process/cgroup usage sample were captured. The high-water figures differ, and sustained, concurrent, and production behavior remain unmeasured. |
| Genuine cross-venue public finding and deployment | DEFERRED | Source-use holds, semantic equivalence, synchronized pricing, venue funding/settlement, and production readiness remain unresolved. |
| Project Frontier overall | PARTIALLY VERIFIED | One supervisor/cgroup gap is closed for bounded fixture execution; source permission, live evidence, broad scientific acceptance, and deployment remain incomplete. |

### Frontier and Arena regression rerun — 2026-10-28 03:08 UTC

With a fresh preflight admission snapshot reporting no active Arena jobs and a
ready gate, the serial regression was rerun:

```bash
/usr/bin/time -v env PYTHONPATH=packages:. /home/charlie/midas/.venv/bin/python -m pytest -q \
  tests/frontier \
  tests/arena/test_frontier_discovery.py \
  tests/arena/test_frontier_replay.py \
  tests/arena/test_frontier_timeline.py \
  tests/arena/test_jobs.py
```

Result: **380 passed, 3 failed** in 88.11 seconds pytest time / 89.51 seconds
process wall, **377,184 KiB maximum RSS**, zero swaps, zero socket messages,
and one existing Starlette/httpx `TestClient` deprecation warning. The failures
were:

- `test_timeline_job_budget_is_small_offline_and_network_restricted_by_kind`
  expected the old resource-limit message, while `JobSpec` now correctly names
  the added discovery job type.
- `test_supervised_job_runner_imports_the_submitted_checkout` and
  `test_veritas_qualification_supervisor_has_read_only_resource_bounds` were
  denied by `resource_admission_lock_busy` before their mocked supervisor
  launch could run. Read-only `fuser` confirmed external Veritas batch PID
  **4112565** held `/home/charlie/midas/data/arena/.global-admission.lock`.
  The batch was left untouched.

The test-only correction updates the stale message expectation and gives those
two command-assembly tests a local no-op admission context; the host-wide
admission behavior remains covered by its separate tests and the real bounded
systemd discovery run above. Targeted rerun remains pending because the
external lock holder is active and the after-suite host sample at
`2026-10-28T03:08:37Z` measured memory PSI avg10 **36.19% some / 30.12% full**,
about **9.6 GiB** available, **332 MiB** swap free, and I/O PSI avg10 **3.98%
some / 3.70% full**. Ruff and `git diff --check` pass for the current test edit;
no test has run after that edit. No source endpoint, held capture, external
batch, protected service, or production Arena artifact was touched.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Frontier plus selected Arena regression | PARTIALLY VERIFIED | 380/383 passed on the pre-correction test source. One stale error-message assertion is updated; two command tests now isolate admission from host state. Rerun is pending external lock release and a fresh pressure check. |
| External Arena admission lock | BLOCKED FOR TEST ADMISSION | Veritas batch PID 4112565 holds the shared lock; do not interrupt it or run more admission-dependent tests until it releases. |
| Project Frontier overall | PARTIALLY VERIFIED | Source permissions, live cross-venue evidence, broad mission criteria, and deployment remain unresolved. |

### Combined Frontier and Arena regression closed — 2026-10-28 03:12 UTC

After PID 4112565 exited and a fresh resource snapshot reported an empty Arena
job list and a ready gate, the corrected combined selection passed:

```bash
/usr/bin/time -v env PYTHONPATH=packages:. /home/charlie/midas/.venv/bin/python -m pytest -q \
  tests/frontier \
  tests/arena/test_frontier_discovery.py \
  tests/arena/test_frontier_replay.py \
  tests/arena/test_frontier_timeline.py \
  tests/arena/test_jobs.py
```

Result: **383 passed** in 90.26 seconds pytest time / 91.74 seconds process
wall, **377,372 KiB maximum RSS**, zero swaps, and zero socket messages. The
existing Starlette/httpx `TestClient` deprecation warning remains. This covers
Frontier and the selected Arena modules, not the full MIDAS Python repository.
Ruff check/format and `git diff --check` pass for the two corrected test
modules. No source access, capture read, production Arena-root write, or
protected service action occurred.

The scoped strict mypy check for
`packages/midas/frontier/discovery_comparison.py` was not launched. The fresh
768-MiB resource gate denied it with `host_memory_pressure`. At
`2026-10-28T03:12:36Z`, memory PSI avg10 was **34.89% some / 32.22% full**,
with about **9.9 GiB** available and **332 MiB** swap free. Read-only `fuser`
identified a new external Veritas gap-detail batch, PID **4117533**, holding
the shared Arena admission lock. It was left untouched. Defer further
resource-bearing work until that lock releases and the pressure gate admits it.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Frontier plus selected Arena regression | COMPLETE AND VERIFIED | The corrected serial selection passes 383/383 at 377,372 KiB peak RSS with zero swaps or socket messages. It is not the full repository suite. |
| Discovery-comparison strict typing | PARTIALLY VERIFIED | Local issues were corrected earlier; final scoped mypy is still pending because the actual resource gate denied work. |
| Current host admission | BLOCKED FOR MORE RESOURCE WORK | Memory PSI is high and external Veritas PID 4117533 owns the shared lock. Preserve it and wait for fresh admission. |
| Project Frontier overall | PARTIALLY VERIFIED | Source permission, live cross-venue evidence, wider repository verification, sustained operations, and deployment remain unresolved. |

### Scoped Frontier type checks closed — 2026-10-28 03:15 UTC

After two fresh Arena resource-admission snapshots each admitted a 768-MiB
request, strict mypy passed for both changed targets:

```bash
env MYPYPATH=packages /home/charlie/midas/.venv/bin/mypy --strict \
  --follow-imports=silent packages/midas/frontier/discovery_comparison.py
env MYPYPATH=packages /home/charlie/midas/.venv/bin/mypy --strict \
  --follow-imports=silent apps/api/frontier.py
```

The API check completed in 21.74 seconds. These are scoped target checks with
diagnostics from imported modules suppressed; they are not a repository-wide
typing result. The checks were read-only and used no source endpoints, test
databases, workers, production services, or protected recordings. At
`2026-10-28T03:15:11Z`, memory PSI avg10 was **0.00% some / 0.00% full**, I/O
PSI avg10 was **0.62% some / 0.61% full**, available memory was about **10.1
GiB**, and free swap was about **333 MiB**. This is one time-bounded host
sample, not a sustained-capacity statement.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Discovery-comparison and Frontier API strict typing | COMPLETE AND VERIFIED | Both scoped mypy invocations pass after separate 768-MiB admission checks. Imported-module diagnostics are intentionally suppressed. |
| Broader Python type safety | PARTIALLY VERIFIED | This closes two scoped targets only; no repository-wide typing pass is claimed. |
| Current host sample | MEASURED | At 03:15:11 UTC, memory PSI avg10 was 0.00% and I/O PSI avg10 was 0.62% some / 0.61% full; this point sample does not establish sustained capacity. |
| Project Frontier overall | PARTIALLY VERIFIED | Genuine cross-venue semantic evidence, held-source live validation, broad operational acceptance, and deployment remain open. |

### Polymarket outcome evidence and response-size diagnostics — 2026-10-28 03:25 UTC

A bounded read-only Polymarket Gamma session made two GET requests at 1 request
per second with a 7-second timeout, no retries, and a 256-KiB body limit. The
first request returned an HTTP 200 page of 20 liquidity-ordered active
markets. The immutable first-page record is in the ignored worktree-local
database
`data/public-captures/frontier-polymarket-20261028T031822Z-pqzzdf1m/frontier.sqlite3`:

- Raw SHA-256: `bee76335963dc0045b0a0be4638afab827dfef9e83cef4eaa3e812d8ba0ba094`
- Observation ID: `5e5f63dbc701476347a814a8496f1e88869f27a49e884b2cf27ee8ee238e661a`
- Stored row SHA-256: `75db34b2b7e9848637942dcbb771745774cfc52ec586322b90c278e7e78b65`

This bounded page contained four numeric event IDs and at most 13 listed
markets for one event. All 20 markets had two instruments and rule text; one
had a resolution authority, none had a close time, and none had verified or
exhaustive payoff metadata. The `/events/{id}` follow-up for the largest group
was rejected by the existing response cap. Its HTTP status and declared size
were not retained by the old failure path; no retry was made. The record is
therefore useful evidence of incomplete metadata and a response-size
limitation, not a validated multi-outcome payout or cross-venue relationship.
No held Kalshi, Kraken, or Coinbase data was accessed.

The transport now attaches bounded response-rejection metadata without
retaining a rejected body. API probes and finite collection runs persist that
metadata in version-2 failure records and label the omitted raw body
explicitly. Raw observations remain readable from schema v1. Ruff check,
format, and `git diff --check` pass for the implementation. Focused transport,
API, collection, compatibility tests, and strict mypy have not run: the fresh
768-MiB Arena admission attempt was denied by the shared lock; a follow-up host
sample at `2026-10-28T03:23:40Z` measured memory PSI avg10 **12.12% some /
10.92% full**, above the admission thresholds. Do not bypass the lock; these
checks remain pending.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Polymarket public listing normalization and durable local read-back | COMPLETE AND VERIFIED | One HTTP 200 page, raw/normalized hash-verified in an ignored worktree-local store; 20 rows only and no venue-wide claim. |
| Event outcome/payoff and resolution evidence | PARTIALLY VERIFIED | The selected detail response exceeded the configured cap; listing metadata had no verified/exhaustive payout or close times. No event-detail body was retained. |
| Bounded response-rejection diagnostics | IMPLEMENTED, LIVE VALIDATION PENDING | Versioned metadata is wired through API and finite collection failure persistence; fixture tests and strict mypy are pending host admission. |
| Project Frontier overall | PARTIALLY VERIFIED | Genuine cross-venue equivalence, source permission for held venues, sustained quality, broader acceptance, and deployment remain open. |

### Bounded rejection diagnostics verified; full suite deferred — 2026-10-28 03:27 UTC

After a fresh 768-MiB preflight admitted focused work, the following selected
tests passed **9/9** in 3.19 seconds:

```bash
pytest -q \
  tests/frontier/test_transport.py \
  tests/frontier/test_collection.py::test_oversized_response_rejection_is_checkpointed_without_body_capture \
  tests/frontier/test_api.py::test_oversized_response_persists_body_omission_and_bounded_transport_metadata \
  tests/frontier/test_storage.py::test_raw_and_source_failure_schema_v1_records_remain_readable
```

This covers both `Content-Length` rejection and bounded streaming rejection,
API and collector persistence of body-omission metadata, and schema-v1
compatibility. The existing Starlette/httpx TestClient deprecation warning is
unchanged. Strict mypy then passed for the Frontier API, collection module,
models, adapter base, and transport with imported-module diagnostics
suppressed. Ruff check/format and `git diff --check` also pass.

A fresh preflight for all `tests/frontier` was denied with
`resource_admission_lock_busy`, and the suite did not start. At
`2026-10-28T03:27:25Z`, memory PSI avg10 was **14.17% some / 12.55% full**,
I/O PSI avg10 was **0.93% some / 0.72% full**, about **9.8 GiB** was available,
and about **333 MiB** of swap was free. Read-only `fuser`/`ps` identified PID
**4128967**, running `scripts/veritas_gap_detail_v2_batch.py` against the
shared Arena root. It was left untouched. Do not rerun the full suite until a
new preflight passes. The prior 383-test combined regression predates this
schema change and is not a substitute for the pending full Frontier run.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Oversized-response bounds and metadata persistence | COMPLETE AND VERIFIED | 9 focused tests pass; response bodies are not stored, v1 records remain readable, and strict mypy passes for five changed production modules. |
| Full Frontier regression after raw observation schema v2 | PARTIALLY VERIFIED | The full suite was not started because the fresh preflight found the shared lock busy and high memory PSI. |
| Project Frontier overall | PARTIALLY VERIFIED | Genuine cross-venue payoff equivalence, held-source permission, broad source quality, deployment, and remaining full-suite acceptance stay open. |

### Official Gamma endpoint shape review — 2026-10-28

The current [Polymarket Gamma discovery reference](https://docs.polymarket.com/market-data/discover-markets)
documents `GET /events/{id}` as returning an event with an embedded markets
array. It separately documents individual market lookup and paged
`/markets/keyset` listing, but does not document a paginated child-market
query keyed by the Gamma event ID. The previously observed 13-child event
therefore remains subject to Frontier's 256-KiB response cap. Known market
IDs can be fetched individually, but that cannot establish event outcome-set
exhaustiveness. No additional public requests were made during this review.

### Combined post-diagnostic regression — 2026-10-28 03:32 UTC

After commit `c91bdf43f125b15279907d4ca53291f377b58387`, a fresh 768-MiB
resource preflight passed with no active Arena jobs, low memory pressure, and
about 10.1 GiB available. The full Frontier suite plus the selected Arena
discovery/replay/timeline/jobs modules then passed **387/387**:

```bash
/usr/bin/time -v env PYTHONPATH=packages:. \
  /home/charlie/midas/.venv/bin/python -m pytest -q \
  tests/frontier \
  tests/arena/test_frontier_discovery.py \
  tests/arena/test_frontier_replay.py \
  tests/arena/test_frontier_timeline.py \
  tests/arena/test_jobs.py
```

The run took **90.74 seconds** in pytest (**92.21 seconds** process wall),
peaked at **379,240 KiB RSS**, used zero swap, and sent or received zero socket
messages. The existing Starlette/httpx TestClient deprecation warning remains.
This closes the full Frontier regression and selected Arena regression for
the response-rejection schema change; it does not represent the full MIDAS
repository suite.

At `2026-10-28T03:32:45Z`, the post-run 768-MiB gate denied further resource
work with `host_memory_pressure`: memory PSI avg10 was **41.42% some / 36.83%
full**, I/O PSI avg10 was **7.68% some / 7.20% full**, and about **10.1 GiB**
was available. Read-only process inspection identified PID **4132908** running
the external `scripts/veritas_gap_detail_v2_batch.py` against the shared Arena
root. It was left untouched. No more resource-bearing checks were started.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Full Frontier plus selected Arena regression after schema v2 | COMPLETE AND VERIFIED | 387/387 pass; 379,240 KiB peak RSS, zero swaps, zero socket messages. The complete repository suite is outside this run. |
| Post-run resource admission | BLOCKED FOR MORE RESOURCE WORK | Fresh post-run gate denied high memory PSI while external Veritas PID 4132908 held the shared lock; preserve the batch and remeasure later. |
| Project Frontier overall | PARTIALLY VERIFIED | Genuine cross-venue payoff equivalence, held-source permission, broad production readiness, and deployment remain open. |

### Frontier probe rejection evidence UI — 2026-10-28 03:36 UTC

The exchange workspace now parses structured probe-failure details, exposes
valid saved diagnostic observation IDs as expandable evidence, and displays
the failure code/message, response cap, declared length, streamed bytes, and
explicit body-omission state. The raw-hash disclosure says that a size-rejected
response hashes the empty stored body rather than the unavailable source body.
Fixture coverage was added to the existing Frontier web test for a
`RESPONSE_TOO_LARGE` failure and its saved record. No live request was made.

The post-run host gate recorded at `2026-10-28T03:32:45Z` denied further work
with high memory PSI while external Veritas PID 4132908 held the shared lock.
No UI test, typecheck, linter, formatter, or build was started after this edit.
Run the focused Frontier web test plus web typecheck, ESLint and Prettier after
a fresh safe host check. This UI change remains **PARTIALLY VERIFIED**; the
earlier 387-test backend regression does not cover it.

### Probe failure evidence UI checks — 2026-10-28 03:37 UTC

After formatting, the focused fixture regression passed **1/1**:

```bash
corepack pnpm exec vitest run src/Frontier.test.tsx \
  -t 'captures one explicit bounded Kalshi multivariate event page'
```

The test covers a structured response-size failure, its saved observation ID,
the rejection metadata disclosure, and the omitted-body/hash explanation.
`corepack pnpm typecheck`, ESLint on `Frontier.tsx` and `Frontier.test.tsx`, and
Prettier check on the two components and stylesheet also passed. The test is
fixture-only and made no source request. No production build or browser E2E ran.

A fresh post-check gate at `2026-10-28T03:37:23Z` denied the full web test suite
with `host_memory_pressure`: memory PSI avg10 was **31.75% some / 25.89% full**
with about **9.8 GiB** available. Read-only `fuser`/`ps` identified external
Veritas PID **4136998** on the shared Arena admission lock; it was left
untouched. The full web unit suite, browser suite, and production build remain
pending a later fresh admission check.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Probe failure evidence UI | COMPLETE AND VERIFIED | Focused fixture passes 1/1; web typecheck, targeted ESLint, and Prettier check pass. |
| Full web regression, browser E2E, and production build after this change | PARTIALLY VERIFIED | Not started because a fresh resource gate denied the full web suite under high memory PSI and an external Veritas lock. |

### Capability-specific single-market metadata capture — 2026-10-28 03:51 UTC

Polymarket now implements direct Gamma detail lookup for one previously
recorded native market ID. The shared adapter package exposes an optional
`SingleMarketMetadataAdapter` extension that returns its exact request URL and
normalizes one response; Polymarket and Kalshi implement it. The API route
`POST /api/frontier/probe/{venue}/market-metadata` requires the extension, a
source-configured public probe, and a canonical market in the bounded saved
market window. It binds the request to that market's immutable listing
observation before egress, enforces an HTTPS URL declared by the adapter, and
checks response venue, canonical/native identities, raw capture count, and raw
hash lineage.

The detail result is stored as a versioned `MarketMetadataEvidence` envelope
under `market_metadata_evidence`. It links the new response to the original
listing record and is intentionally excluded from the catalogue index, so a
single detail response cannot silently replace saved listing or event-group
context. Kraken and Coinbase do not implement the exact-ID extension and are
rejected before network access. Mission Control exposes the capture for
Polymarket and Kalshi when their source configuration and capability permit;
the inspector shows the saved link, detail rules, raw hash, and evidence
disclosure. Event membership, outcome-set exhaustiveness, payoff verification,
and current price are not inferred.

No live source request was made for this change. The adapter/API/UI tests use
existing recorded fixtures and isolated MockTransport responses. One initial
focused test run exposed a test-edit boundary error that had moved pre-existing
Polymarket book assertions into a new test; the assertions were restored to
their original test and the focused rerun passed.

Verification:

```bash
/usr/bin/time -v env PYTHONPATH=packages:. \
  /home/charlie/midas/.venv/bin/python -m pytest -q tests/frontier
# 352 passed in 55.97s; 376,672 KiB peak RSS; zero swaps and socket messages

cd apps/web
corepack pnpm exec vitest run src/Frontier.test.tsx
# 8 passed in 5.20s test time / 5.89s process wall; 238,112 KiB peak RSS
corepack pnpm typecheck
corepack pnpm exec eslint src/Frontier.tsx src/Frontier.test.tsx
corepack pnpm exec prettier --check src/Frontier.tsx src/Frontier.test.tsx

cd /home/charlie/midas-frontier
/usr/bin/time -v env PYTHONPATH=packages:. \
  /home/charlie/midas/.venv/bin/python -m mypy apps/api/frontier.py \
  packages/midas/frontier/models.py packages/midas/frontier/adapters/base.py \
  packages/midas/frontier/adapters/polymarket.py \
  packages/midas/frontier/adapters/kalshi.py
# Success: no issues found in 5 source files
/home/charlie/midas/.venv/bin/ruff check apps/api/frontier.py \
  packages/midas/frontier/models.py packages/midas/frontier/adapters/base.py \
  packages/midas/frontier/adapters/polymarket.py \
  packages/midas/frontier/adapters/kalshi.py tests/frontier/test_api.py \
  tests/frontier/test_adapters.py
/home/charlie/midas/.venv/bin/ruff format --check apps/api/frontier.py \
  packages/midas/frontier/models.py packages/midas/frontier/adapters/base.py \
  packages/midas/frontier/adapters/polymarket.py \
  packages/midas/frontier/adapters/kalshi.py tests/frontier/test_api.py \
  tests/frontier/test_adapters.py
```

The full Frontier suite emitted the existing Starlette/httpx TestClient
deprecation warning. Web typecheck, targeted lint, formatting, and the full
Frontier component test file passed; the production web build and browser E2E
were not run after this slice. The host sample after tests at
`2026-10-28T03:51:06Z` showed memory PSI avg10 `0.00%` some / `0.00%` full,
I/O PSI `2.51%` some / `2.35%` full, about `10.2 GiB` available memory, and
about `333 MiB` free swap. The shared Arena admission lock had no listed
holder. This point sample is not a resource-sustainability claim.

After the full Frontier run, the evidence envelope schema was narrowed to the
single supported version, Gamma ID validation was made robust to non-string
runtime inputs, and adapter-declared metadata URLs were also checked for URL
user-info. The focused adapter/API regression was rerun after those final guards:
**4 passed** in 1.78 seconds, 87,136 KiB peak RSS, zero swaps, and zero socket
messages. Strict mypy for the same five production modules again reported no
issues; Ruff check/format and `git diff --check` passed.

At `2026-10-28T03:52:14Z`, the fresh resource sample remained low (memory PSI
avg10 `0.00%` some/full, I/O PSI `0.72%` some / `0.61%` full, about `9.8 GiB`
available). Read-only `fuser`/`ps` showed external Veritas batch PID `4149818`
in `D` state holding the shared Arena admission lock. It was left untouched;
the full web suite and production web build were deferred while that job holds
the lock.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Polymarket single-ID adapter extension | COMPLETE AND VERIFIED | Exact numeric ID validation, one public GET contract, response binding, and normalizer coverage pass with fixture tests. |
| Polymarket/Kalshi shared API metadata capture | COMPLETE AND VERIFIED | 352-test Frontier suite; both venue routes are exercised with mocked public responses, exact URL and immutable listing linkage. No live request in this slice. |
| Mission Control market detail control | COMPLETE AND VERIFIED | Frontier component suite passes 8/8; capability/config gates and evidence disclosure are fixture-backed. |
| Full web suite, browser E2E, and production build after this slice | PARTIALLY VERIFIED | Typecheck, targeted ESLint/Prettier, and all Frontier component tests pass; broad web suite, browser E2E, and build remain pending. |

### Bounded live metadata capture and harness cleanup finding — 2026-10-28 03:54 UTC

One authorized public read-only request exercised the new Polymarket
single-market metadata route for the already captured native market ID
`2589810`. The route made one GET to the adapter-declared HTTPS URL with the
configured 7-second timeout, zero retries, one-market bound, one-request-per-
second rate limit, and 256-KiB response cap. It returned HTTP 200 with a
4,198-byte body. No credentials, trading interface, account access, held
exchange, or protected service was involved.

The response body hash
`d462014349743a6175facab3aef0433a069899c43845c789ca4cdce87bd8cf26` matches
the hash persisted in observation
`d51864858856a0a8e8faff66fd75c5e590ee4b2f47642147b24c73e8581d74b9`. Its
append-only row hash is
`b2215f17912c3f4e9558d2b314b22d96ceb08fdd0fd439b2429db3ad259a2027`; the
store's read-only SQLite integrity check passed. The observation is bound to
listing `5e5f63dbc701476347a814a8496f1e88869f27a49e884b2cf27ee8ee238e661a`
and remains outside the catalogue index. The capture is worktree-local and
ignored by Git; no prior database or source evidence was modified.

The detail title and resolution authority match the linked listing. Its
normalized event ID is the placeholder `market:2589810`, while the listing
event ID is `606422`. This is not evidence of event membership or equivalence;
the listing context remains authoritative for that captured event grouping.
The response does not verify the resolution rule, exhaustive outcome set,
payoff, settlement asset, or cross-venue equivalence, and it produces no
opportunity claim.

The request and database read-back succeeded, but the short-lived TestClient
harness exited nonzero while closing its async adapter from a different event
loop (`RuntimeError: Event loop is closed`). No retry occurred. This cleanup
issue should be fixed in the probe harness by closing the adapter within the
request's ASGI loop; it does not invalidate the recorded HTTP response but
does mean the process-level probe is not fully clean. The source terms review
records this limitation and preserves the existing Kalshi, Kraken, and
Coinbase holds. No jurisdictional permission is inferred.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Polymarket single-market adapter live lookup | PARTIALLY VERIFIED | One bounded HTTP 200 response is persisted and hash-checked; event membership, payoff semantics, cross-venue matching, and clean harness teardown remain unverified. |
| Isolated capture-store integrity | COMPLETE AND VERIFIED | SQLite integrity check passed; raw-body SHA-256 matches persisted metadata; original capture store stayed read-only. |
| Full web suite, browser E2E, and production build | PARTIALLY VERIFIED | The previous targeted UI checks passed; broad web verification remains pending a fresh resource and shared-lock admission check. |

### Full Frontier web suite and browser E2E — 2026-10-28 03:57 UTC

At `2026-10-28T03:56:26Z`, memory PSI avg10 was 0%, about 10 GiB was
available, and the shared Arena lock had no listed holder. The complete web
unit suite passed **40/40 across seven files**:

```bash
/usr/bin/time -v corepack pnpm test
# 40 passed; 360,100 KiB peak RSS; zero swaps and socket messages
```

The six Frontier browser scenarios then passed **6/6** against the Playwright
configuration's temporary loopback API/database/Arena root and Vite server:

```bash
/usr/bin/time -v corepack pnpm exec playwright test e2e/frontier.spec.ts
# 6 passed in 15.5s; 197,660 KiB peak RSS; zero swaps or socket messages
```

The scenarios covered the research-only overview and responsive layout, no
automatic source probes, replay history without job submission, scoped saved
discovery evidence, fixture-only joint-state replay and Kalshi fee arithmetic,
and bounded relationship-graph interaction. No exchange source request,
protected service, shared Arena artifact root, or production configuration was
touched. The production web build was not run because resource pressure rose
after E2E.

At `2026-10-28T03:59:17Z`, memory PSI had risen to **35.49% some / 30.65% full**
avg10, with about **10 GiB** available. External Veritas PID **4154226** held
the shared Arena admission lock in `D` state. It was left untouched. No further
resource-bearing checks were started.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Complete web unit suite | COMPLETE AND VERIFIED | 40/40 across seven files; 360,100 KiB peak RSS; zero swaps or socket messages. |
| Frontier browser E2E | COMPLETE AND VERIFIED | 6/6 against temporary local services and data; 197,660 KiB peak RSS; no public source requests. |
| Production web build | PARTIALLY VERIFIED | Typecheck passed earlier; final build remains pending a fresh resource admission check. |

### Gamma missing-event identity correction — 2026-10-28 03:59 UTC

The bounded Gamma detail response has no `events`, `eventId`, or `event_id`
field. Its previously stored normalized `market:2589810` value came from the
legacy MIDAS Polymarket normalizer's local fallback, not from Gamma. The
immutable capture remains unchanged and its placeholder is not treated as
evidence of event membership.

The Frontier adapter is being corrected to set `native_event_id` only from an
explicit nested Gamma event or the parent event lookup that supplied the
market. Missing event context now normalizes as `null`; an existing listing
event ID remains on the original listing observation. Adapter and API fixtures
were adjusted to exercise this absent-event case, and the architecture contract
now explains the distinction. Ruff check/format and `git diff --check` passed.
No Python tests or build were started after the edit: at the fresh
`2026-10-28T03:59:17Z` sample, memory PSI avg10 was **35.49% some / 30.65% full**
and external Veritas PID **4154226** held the shared Arena lock. The test change
is therefore unverified and must be run after a new resource admission check.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Frontier event ID normalization correction | PARTIALLY VERIFIED | Conservative mapping and absent-event assertions are implemented; static lint/format pass; targeted adapter/API tests remain pending. Historical captures are immutable. |

### Resource gate recheck — 2026-10-28 04:03 UTC

The follow-up host sample at `2026-10-28T04:03:00Z` continued to deny
resource-bearing verification: memory PSI avg10 was **42.66% some / 33.52%
full**, avg60 **37.19% / 29.70%**, and avg300 **27.58% / 22.98%**. About **10
GiB** was available, but only **333 MiB** of swap remained free. External
Veritas PID **4154226** still held the shared Arena admission lock in `D` state
with elapsed time 4:49. It was not signaled or modified. No tests, typecheck,
browser run, or production build were started after the event-ID edit; those
changes remain in the worktree awaiting a fresh passing resource gate.

### Event-ID correction and production build verification — 2026-10-28 04:07 UTC

Commit `fb6d800` completes the event-identity correction. Frontier now emits
`native_event_id` only from one explicit numeric Gamma event object or a
validated parent-event lookup. The legacy MIDAS Polymarket normalizer is
unchanged for existing callers. Missing or ambiguous Gamma event context is
`null`, and no stored observation was rewritten. The original listing keeps
its explicit event ID; the one older detail capture retains the local
`market:2589810` parser fallback as historical normalized data and is not used
as evidence of event membership.

After the final code change, the full Frontier regression passed **352/352**
in 55.83 seconds, at **376,888 KiB peak RSS**, with zero swaps and socket
messages. The three focused event-ID/API tests were rerun after the type-only
annotation fix and passed **3/3** in 1.02 seconds, at **81,848 KiB peak RSS**,
also with zero swaps or socket messages. Strict mypy passed for five production
modules (API, models, adapter base, Polymarket, and Kalshi). Ruff check/format
and `git diff --check` passed.

The production frontend build completed with TypeScript and Vite. To preserve
the pre-existing ignored `apps/web/dist`, the bundle was written to
`/tmp/midas-frontier-build-20261028T0406Z`; 2,228 modules transformed, Vite
reported **4.83 seconds** build time and **685,120 KiB peak RSS**, with zero
swaps and socket messages. Existing warnings remain for the **544.41 kB** Chart
chunk and the temporary output directory being outside the project root. The
full web test suite remains **40/40** and Frontier E2E **6/6** from the 03:57
checkpoint; those browser cases use temporary loopback services and make no
public source request.

At `2026-10-28T04:06:58Z`, memory PSI avg10 was **0.08% some / 0.08% full**,
about **10 GiB** was available, and no process held the shared Arena lock. The
protected Reality API was left untouched. No live source request, historic
evidence mutation, merge, push, or deployment occurred.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Polymarket event identity normalization | COMPLETE AND VERIFIED | Commit `fb6d800`; 352 full Frontier tests, focused final-code 3/3, strict mypy, and static lint/format pass. Historical captures remain immutable. |
| Web unit suite and Frontier browser E2E | COMPLETE AND VERIFIED | 40/40 unit tests and 6/6 browser tests against isolated local services. |
| Production web build | COMPLETE AND VERIFIED | TypeScript and Vite succeed to a temporary output directory; the existing Chart chunk advisory remains. |
| Live cross-venue payoff equivalence | BLOCKED | Source-use holds prevent a genuine second-venue probe; no live opportunity or profitability is claimed. |
| Production deployment | DEFERRED | Branch remains isolated and undeployed. |

### Metadata API description — 2026-10-28 04:09 UTC

The market-metadata endpoint's FastAPI description now states that the native
ID is bound to the saved listing before egress, the detail is stored
separately, and event membership, exhaustive outcomes, payoff, settlement,
current quotes, and opportunities are not inferred. `FRONTIER_OPERATIONS.md`
and `docs/DEVELOPMENT.md` describe the same boundary. The focused OpenAPI
contract assertion passes **1/1** in
`tests/frontier/test_api.py::test_polymarket_market_metadata_probe_is_bound_and_does_not_replace_listing`.
Commit `1da2b11` records the API description and companion documentation. This
is API documentation only; it makes no source request and changes no runtime
decision path.

### Arena consumer regression after event identity correction — 2026-10-28 04:11 UTC

The selected Arena discovery, replay, timeline, and job-supervision modules
passed **38/38** after commit `fb6d800`:

```bash
/usr/bin/time -v env PYTHONPATH=packages:. \
  /home/charlie/midas/.venv/bin/python -m pytest -q \
  tests/arena/test_frontier_discovery.py \
  tests/arena/test_frontier_replay.py \
  tests/arena/test_frontier_timeline.py \
  tests/arena/test_jobs.py
# 38 passed in 37.70s; 200,152 KiB peak RSS; zero swaps and socket messages
```

The selection covers fixture-backed saved-input discovery/replay and
temporary-root job dispatch. It does not launch a production Arena worker,
write the shared Arena root, or validate actual systemd/cgroup execution.
At `2026-10-28T04:11:18Z`, memory PSI avg10 was **0.00% some / 0.00% full**,
I/O PSI avg10 **10.31% some / 9.83% full**, about **9 GiB** was available, and
no process held the shared Arena lock. No protected service or external batch
was touched.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Arena discovery/replay/timeline/job consumers | COMPLETE AND VERIFIED | Selected 38-test regression passes after event normalization correction; no real systemd unit or production Arena root was used. |

### Offline replay of the captured Gamma detail — 2026-10-28 04:14 UTC

The exact body from stored observation
`d51864858856a0a8e8faff66fd75c5e590ee4b2f47642147b24c73e8581d74b9` was
replayed in memory through the corrected Polymarket adapter using HTTPX
`MockTransport`. It was loaded read-only from the ignored local capture store;
the stored body hash
`d462014349743a6175facab3aef0433a069899c43845c789ca4cdce87bd8cf26` matched
before replay. The prior normalized value was `market:2589810`; the corrected
normalizer returned `native_event_id=null`, while native market ID `2589810`,
title, and raw hash matched. The adapter made one mocked request and no public
network request.

SQLite `integrity_check` remained `ok`, and the store had **2 rows both before
and after** the replay. No observation was appended or rewritten. This verifies
the new parser against the exact captured response; it still provides no event
membership, outcome exhaustiveness, verified payoff, settlement equivalence,
or opportunity evidence. At `2026-10-28T04:14:07Z`, memory PSI avg10 was
**0.42% some / 0.39% full**, I/O PSI avg10 **0.53% / 0.48%**, about **10 GiB**
was available, and no Arena lock holder was listed.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Corrected adapter replay of live captured body | COMPLETE AND VERIFIED | Exact stored response hash and title reproduced; event ID now remains unknown; read-only DB integrity and row count unchanged; no public network access. |

### Legacy Polymarket adapter compatibility — 2026-10-28 04:14 UTC

The shared `midas.market_data.polymarket.normalize_market` function remains
unchanged, including its local `market:<id>` fallback used by existing
callers. A focused regression removes the optional Gamma `events` field from
the recorded fixture and confirms this legacy `Market.event_id` still equals
`market:<native-market-id>`:

```bash
/usr/bin/time -v env PYTHONPATH=packages:. \
  /home/charlie/midas/.venv/bin/python -m pytest -q \
  tests/integration/test_adapters.py::test_legacy_polymarket_event_id_fallback_remains_compatible
# 1 passed in 0.26s; 53,712 KiB peak RSS; zero swaps and socket messages
```

This isolates the Frontier change from the shared legacy normalizer; it does
not constitute a full Reality/Veritas repository regression. Ruff check and
format pass for the changed integration test. No live request or protected
service was used.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Legacy Polymarket event-ID fallback | COMPLETE AND VERIFIED | Shared normalizer remains unchanged and focused integration regression passes; broader repository tests remain outside this check. |

### Full legacy adapter integration file — 2026-10-28 04:15 UTC

The complete `tests/integration/test_adapters.py` module passed **10/10** in
0.75 seconds pytest time (1.24 seconds process wall), at **91,336 KiB peak RSS**,
with zero swaps and socket messages. This includes the new explicit fallback
contract check, recorded Gamma/CLOB fixture normalization, GET-only transport,
record/replay, storage-budget, and degraded-storage cases. The tests use local
transports and fixtures; no exchange endpoint was contacted.

At the post-run sample `2026-10-28T04:15:16Z`, memory PSI avg10 was **0.00%
some / 0.00% full**, I/O PSI avg10 **0.91% some / 0.87% full**, about **10 GiB**
was available, and no process held the shared Arena lock.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Legacy market-data adapter integration | COMPLETE AND VERIFIED | Full 10-test integration adapter module passes with no network or protected data; this is not the full MIDAS repository suite. |

### Resource gate recheck — 2026-10-28 04:12 UTC

At `2026-10-28T04:12:29Z`, memory PSI had risen again: avg10 **38.86% some /
33.25% full**, avg60 **10.55% / 9.26%**, avg300 **12.13% / 10.61%**. I/O PSI
avg10 was **0.44% / 0.34%**. About **9 GiB** was available and **333 MiB** of
swap was free. Read-only `fuser` and `ps` identified external Veritas PID
**4166289** (`scripts/veritas_gap_detail_v2_batch.py`) in `D` state holding the
shared Arena lock. It was left untouched. No tests, builds, probes, or other
resource-bearing jobs were started after the 04:11 Arena regression.

### Legacy API and paper-research safety regression — 2026-10-28 04:16 UTC

Two additional bounded legacy integration modules passed using the isolated
Frontier worktree and temporary test roots:

- `tests/integration/test_api.py`: **5/5** in 4.47 seconds pytest time
  (5.56 seconds process wall), **167,956 KiB peak RSS**. It checks the offline
  Frontier API overview, demo-mode source-probe denial, temporary persistence,
  database failure handling, and configured Reality/Veritas workspace routing.
- `tests/integration/test_milestone2_journey.py`: **5/5** in 4.70 seconds
  pytest time (5.55 seconds process wall), **134,632 KiB peak RSS**. It checks
  fixture replay through the legacy verifier and paper broker, stale/negative
  economics remaining disallowed, read-only transport restrictions, and
  temporary paper-state recovery.

Both runs reported zero swaps and zero socket messages. External public data,
production databases, protected services, and the shared Arena root were not
used. The existing Starlette/httpx TestClient deprecation warning remains.
At `2026-10-28T04:16:39Z`, memory PSI avg10 was **0.00% some / 0.00% full**,
I/O PSI avg10 **1.04% / 1.04%**, about **10 GiB** was available, and the shared
Arena lock had no holder.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Legacy offline API and paper-research compatibility | COMPLETE AND VERIFIED | Ten selected integration tests pass in temporary roots; this is not deployed API or full-repository validation. |
| Project Frontier overall | PARTIALLY VERIFIED | Cross-venue payoff validation, held-source permission, broad scientific acceptance, full-repository regression, and deployment remain incomplete. |

### Shared-host admission deferment — 2026-10-28 04:18 UTC

A read-only preflight for the optional legacy storage-query and recording-
isolation regression found memory PSI avg10 at **48.45% some / 43.86% full**
at `2026-10-28T04:18:00Z`. I/O PSI avg10 was **0.79% / 0.79%**; about
**10 GiB** appeared available and **333 MiB** of swap was free. Those capacity
figures do not override the shared admission gate. `fuser` identified PID
**4170342** holding `/home/charlie/midas/data/arena/.global-admission.lock`;
read-only process inspection identified it as the external
`scripts/veritas_gap_detail_v2_batch.py` under
`midas-veritas-gap-detail-v2.service`. It was left untouched. The optional
tests were not started. No Frontier process, protected service, database, or
evidence store was modified. Resume only after a fresh low-pressure sample and
an unheld shared lock.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Optional legacy storage-query/recording-isolation tests | DEFERRED | Isolated test code was inspected; no test ran because current shared-host admission failed. |
| Project Frontier overall | PARTIALLY VERIFIED | The implementation and bounded regression evidence remain valid; source permission, genuine cross-venue equivalence, full-repository acceptance, and deployment remain open. |

### Storage, recording, and protected-service guard regressions — 2026-10-28 04:19 UTC

After the shared Arena lock cleared, the bounded tests deferred above were
rerun in isolation:

- `tests/integration/test_storage_queries.py` and
  `tests/integration/test_recording_isolation.py`: **7/7** in 2.18 seconds
  pytest time (2.68 seconds process wall), **103,244 KiB peak RSS**. The
  storage cases use temporary SQLite databases; recording cases use temporary
  roots or assert the configured path without writing it.
- `tests/integration/test_state_codec.py::test_materialization_refuses_a_running_or_protected_service`:
  **1/1** in 0.43 seconds pytest time (0.84 seconds process wall), **72,156
  KiB peak RSS**. `systemctl` output is mocked and the test confirms the API
  and Reality service materializations are refused.
- A source-tree reference audit, `rg -n "data/frontier/live-probes|live-probes/" tests packages apps`,
  returned no matches. It read source paths only; no held capture was opened.

Both pytest invocations had zero swaps and zero socket messages. At
`2026-10-28T04:19:47Z`, memory PSI avg10 was **0.01% some / 0.01% full**,
avg60 **9.38% / 8.50%**, avg300 **13.11% / 11.79%**; I/O PSI avg10 was
**1.27% / 1.08%**. About **10 GiB** was available, **333 MiB** of swap was
free, and no process held the shared Arena lock. This supersedes the
04:18 deferment for these selected checks only; it does not justify a broad
suite during elevated longer-window pressure.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Bounded legacy storage and recording compatibility | COMPLETE AND VERIFIED | Seven temporary-root/path-contract tests pass with low peak RSS and no swap or network traffic. |
| Guard against paper-state materialization on protected services | COMPLETE AND VERIFIED | Focused test confirms API and Reality service guards fail closed; actual services were not contacted or modified. |
| Current source-tree held-capture path references | COMPLETE AND VERIFIED | Static audit found no references under tests/packages/apps; this does not authorize direct database access or held-source use. |

### Held-source boundary regression — 2026-10-28 04:20 UTC

`tests/frontier/test_held_capture_source_boundary.py` passed **2/2** in 0.16
seconds pytest time (0.46 seconds process wall), with **43,732 KiB peak RSS**,
zero swaps, and zero socket messages. The source audit test scans Python test
files for held-capture path references; the runtime test exercises reads,
writes, `open`, `os.open`, file/directory symlinks, traversal, and `dir_fd`
against an absent path under `tmp_path`. It opens no preserved source capture.

At `2026-10-28T04:20:34Z`, memory PSI avg10 was **0.00% some / 0.00% full**,
avg60 **4.36% / 3.95%**, avg300 **11.19% / 10.07%**; I/O PSI avg10 was
**0.87% / 0.69%**. About **10 GiB** was available and the shared Arena lock
was free. This verifies the held-capture guard against the current test tree;
it does not authorize use of held records or paths outside these guard rails.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Held-source path guard and test-source isolation | COMPLETE AND VERIFIED | Current Python tests contain no held-capture path reference; direct and symlink path operations are denied on a temporary fixture. |

### Combined Frontier and Arena regression — 2026-10-28 04:23 UTC

The complete `tests/frontier` suite and selected Arena discovery, replay,
timeline, and job modules passed together in one invocation:

```bash
/usr/bin/time -v env PYTHONPATH=packages:. \
  /home/charlie/midas/.venv/bin/python -m pytest -q \
  tests/frontier \
  tests/arena/test_frontier_discovery.py \
  tests/arena/test_frontier_replay.py \
  tests/arena/test_frontier_timeline.py \
  tests/arena/test_jobs.py
# 390 passed in 91.63s pytest time (93.00s wall); 380,624 KiB peak RSS
# zero swaps; zero socket messages
```

This is the first clean combined run after the Gamma event-ID correction and
the later source-rejection diagnostics changes; it covers current Frontier
tests plus the selected Arena consumers in one process. The existing
Starlette/httpx TestClient deprecation warning remains. It does not cover all
MIDAS tests, production Arena/systemd execution, live exchange calls, or
deployment.

At `2026-10-28T04:23:44Z`, post-run memory PSI avg10 was **39.41% some /
35.46% full**, avg60 **29.70% / 26.17%**, avg300 **16.08% / 14.23%**; I/O PSI
avg10 was **8.41% / 8.00%**. About **10 GiB** appeared available and **333
MiB** of swap was free. External Veritas PID **4174453** held the shared Arena
lock and was left untouched. No more resource-bearing checks were started.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Combined current Frontier and selected Arena regression | COMPLETE AND VERIFIED | 390/390 in one invocation at 380,624 KiB peak RSS with zero swaps and socket messages. |
| Full MIDAS repository regression | PARTIALLY VERIFIED | Broad repository suite remains unrun; the selected suite is scoped to Frontier and Arena consumers. |

### Supplementary FX reference source reviewed — 2026-10-28

Reviewed official ECB Data Portal API documentation and the ESCB statistics
reuse policy. The API documents the HTTPS SDMX `EXR` dataflow and daily
reference-rate series; the policy allows free reuse of released statistics
with attribution and a no-modification condition. These are daily reference
statistics rather than tradable FX quotes, so they cannot establish
simultaneous conversion, funding, or transfer availability. ECB is documented
as a possible contextual source, not added to the exchange registry or used
to populate candidate economics. No ECB request or capture was made. See the
[source-data terms review](SOURCE_DATA_TERMS_REVIEW_2026-10-27.md).

### Current mission reconciliation — 2026-10-28 04:30 UTC

The isolated worktree is clean on `codex/frontier-20261026` at
`2064671` (`docs(frontier): evaluate official ECB FX reference data`). The
current code includes read-only adapters for Polymarket, Kalshi, Kraken, and
Coinbase; canonical market/payoff models; relationship review and provenance;
supported candidate families; bounded multi-market joint-state baskets;
independent arithmetic checks; source-aware storage/replay; selected Arena
integration; and the native Frontier Mission Control interface.

The complete `tests/frontier` suite plus selected Arena discovery, replay,
timeline, and job modules passed **390/390** together at **380,624 KiB peak
RSS**, with zero swaps and socket messages. Web unit tests passed **40/40**,
Frontier browser E2E passed **6/6**, and the temporary-output production build
passed. Targeted legacy API, paper-research, storage, recording, service-guard,
and held-source-boundary checks also passed; earlier ledger entries retain the
exact commands and per-run measurements. The full MIDAS repository suite was
not run.

This reconciliation supersedes earlier entries that described general
multi-market search as deferred: commit `4bd3b7f` added a bounded conditional
joint-state basket across two to four markets, and the current combined
regression covers it. The map requires explicit shared-state projections and
is not semantically authenticated; positive outputs remain conditional and
practically ineligible.

| Component | Status | Remaining boundary |
| --- | --- | --- |
| Frontier engine, supported candidate families, independent audit, replay, and UI | COMPLETE AND VERIFIED | Verified on bounded fixtures and selected consumers; the full repository suite and sustained service behavior remain unmeasured. |
| Multi-market joint-state basket | COMPLETE AND VERIFIED | Arithmetic and replay are verified conditional on an external map; semantic truth and attainability are not certified. |
| Four source adapters | PARTIALLY VERIFIED | Fixture/contract checks pass; Kalshi and Kraken use remains held, Coinbase remains held pending exact scope review, and no live cross-venue sample is claimed. |
| Genuine cross-venue equivalence and economic opportunity | BLOCKED | Current source-use holds and missing synchronized, payoff-equivalent evidence prevent live scientific validation. |
| Production transition | DEFERRED | Frontier remains isolated; full deployment-scope readiness, monitoring/rollback preparation, and separate authorization are outstanding. |
| Project Frontier overall | PARTIALLY VERIFIED | Do not infer live equivalence, executable profitability, production readiness, or deployment from fixture results. |

At `2026-10-28T04:29:44Z`, memory PSI was `avg10=0.00%` some/full,
`avg60=3.83% / 3.49%`, and `avg300=10.54% / 9.46%`; I/O PSI avg10 was
`0.91% / 0.63%`, with about 10.3 GiB available and 333 MiB swap free. This is a
time-specific host observation, not a production capacity result. No test,
build, source request, service action, or deployment was started for this
documentation reconciliation.

**Next safe action:** continue source-independent acceptance and code review.
Rerun broader repository validation only after a fresh host and shared-Arena
admission check. Keep held-source requests and use disabled until the relevant
permission is independently validated; preserve the research-only boundary.

### Full legacy integration directory — 2026-10-28 04:33 UTC

The full `tests/integration` directory passed **56 tests**, with one optional
PostgreSQL runtime test skipped because `MIDAS_TEST_POSTGRES_URL` was absent:

```bash
/usr/bin/time -v env PYTHONPATH=packages:. \
  /home/charlie/midas/.venv/bin/python -m pytest -q \
  --basetemp=/tmp/midas-frontier-integration-20261028T0432Z \
  tests/integration
# 56 passed, 1 skipped in 28.49s pytest time / 29.73s wall
# 220,460 KiB peak RSS; zero swaps, major faults, or socket messages
```

The integration cases used fixtures and temporary roots; the test that
asserts the legacy default recording path performed no write. The run emitted
the existing Starlette/httpx TestClient deprecation warning. This closes the
complete local integration directory, not the entire MIDAS Python repository
suite or an enabled PostgreSQL backend.

At the post-run sample `2026-10-28T04:32:51Z`, memory PSI avg10 was **38.12%
some / 32.63% full**, avg60 **16.02% / 13.44%**, and avg300 **9.56% / 8.34%**.
About **10 GiB** was available and **333 MiB** of swap was free. Read-only
`fuser`/`ps` identified external Veritas PID **4182417** holding the shared
Arena admission lock in `D` state. It was left untouched. No further
resource-bearing checks, source requests, protected-service actions, or
deployment were started.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Legacy `tests/integration` directory | COMPLETE AND VERIFIED | 56 tests passed; optional PostgreSQL runtime skipped; temp pytest root; 220,460 KiB peak RSS with zero swaps or sockets. |
| Full MIDAS repository regression | PARTIALLY VERIFIED | Frontier plus selected Arena and the complete integration directory pass; remaining repository suites have not run together. |
| Further resource-bearing verification | DEFERRED AT THIS SAMPLE | Memory PSI rose after the run and external PID 4182417 held the shared Arena lock; the process was not interrupted. |

### Full-suite collection audit — 2026-10-28 04:36 UTC

A full Python test attempt used a detached worktree at Frontier commit `29b09fa`
and an external pytest temporary directory. That worktree did contain the
tracked `data/frontier/live-probes` directory; the Frontier main worktree was
not the pytest source tree:

```bash
nice -n 10 /usr/bin/time -v env PYTHONPATH=packages:. \
  /home/charlie/midas/.venv/bin/python -m pytest -q \
  --basetemp=/tmp/midas-frontier-full-regression-pytest-20261028T0435Z tests
# collection stopped after 10.89s; process wall 12.30s; peak RSS 453,748 KiB
# zero swaps and zero socket messages; no tests ran
```

Collection failed at `tests/test_reality_full_scale_validation.py:12`, which
imports `midas.reality.recovery`. The selected Frontier/V6 source tree lacks
`packages/midas/reality/recovery.py`. Read-only tree comparison confirmed the
module is present in the separate `fix/reality-foundation-20261020` candidate
at `4278b5b` but absent from both the selected V6 baseline and protected
`project/reality` checkout. The candidate module also relies on newer
Reality `reconstruction.py`, `replay.py`, and `storage.py`; no partial copy or
merge was attempted. The mismatch is not evidence that either complete source
revision passes the entire test suite. No test functions executed in this
attempt. File-open tracing was not enabled, so it cannot establish whether
collection read a held capture; no capture writes or copies were intentional.

At `2026-10-28T04:38:33Z`, memory PSI avg10 was **1.17% some / 1.03% full**,
avg60 **13.95% / 12.54%**, avg300 **10.50% / 9.37%**, and I/O PSI avg10
**1.03% / 1.03%**. About **10 GiB** was available. The shared Arena lock had no
holder at that sample, but elevated longer-window memory pressure remained.
No further resource-bearing validation was started.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Full MIDAS Python regression | PARTIALLY VERIFIED | Pytest collection is blocked by the missing Reality recovery module in the selected baseline; no full suite tests executed. |
| Reality candidate cross-branch integration | DEFERRED | Recovery support depends on newer Reality core modules; no files were merged into Frontier. |
| Further broad test runs | DEFERRED AT THIS SAMPLE | Elevated memory PSI remained; the external job was no longer live and the shared lock was free. |

## Sparse-tree regression correction and resource stop — 2026-10-28 04:43 UTC

The `29b09fa` detached worktree used for the 04:36 collection attempt did
contain the tracked `data/frontier/live-probes` directory. No test functions
ran because collection failed on the missing `midas.reality.recovery` module.
File-open tracing was not enabled, so we cannot establish whether collection
read a held capture. No capture writes or copies were intentional. This
corrects the earlier statement that the detached tree did not contain the
capture directory or that capture access could be ruled out.

The follow-up used a detached sparse worktree at `c8989d5` with the `data/`
tree excluded. The held path
`/tmp/midas-frontier-regression-sparse-20261028T0440Z/data/frontier/live-probes`
was absent before and after the run. The command was:

```bash
nice -n 10 /usr/bin/time -v env PYTHONPATH=packages:. \
  /home/charlie/midas/.venv/bin/python -m pytest -q \
  --basetemp=/tmp/midas-frontier-rest-regression-20261028T0440Z \
  --ignore=tests/test_reality_full_scale_validation.py tests
```

The run reached **101 passed** at 149.66 seconds. A memory-PSI and shared-lock
admission check then showed **35.48% some / 28.44% full** over 10 seconds,
**15.83% / 13.22%** over 60 seconds, and **8.25% / 7.15%** over 300 seconds.
External Veritas batch PID **4190462** held the shared Arena admission lock.
Only the Frontier pytest PID was sent SIGINT; the Veritas process was left
untouched. Pytest exited 2 with `KeyboardInterrupt`, so this did not complete
the suite. Peak RSS was **539,616 KiB**, with zero swaps and socket messages.
At `2026-10-28T04:43:58Z`, PID 4190462 remained present and memory PSI was
**47.14% some / 42.14% full** over 10 seconds. Further resource-bearing checks
were deferred.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Full MIDAS Python suite excluding known collection blocker | PARTIALLY VERIFIED | 101 tests passed before resource-driven interrupt; exit 2, no suite pass claimed. |
| Follow-up test isolation | COMPLETE AND VERIFIED | Sparse checkout excluded `data/`; the held capture path stayed absent before and after. |
| Initial detached collection capture boundary | PARTIALLY VERIFIED | Tracked captures were present; reads during collection cannot be ruled out, though no test functions ran and no writes/copies were intentional. |
| Further broad verification | DEFERRED AT THIS SAMPLE | High memory PSI and active external Veritas batch; no action was taken on that process. |

## Re-admission attempt and second resource stop — 2026-10-28 04:49 UTC

At `2026-10-28T04:45:48Z`, memory PSI had recovered to **0.00% some / 0.00%
full** over 10 seconds and **7.46% / 6.57%** over 60 seconds, with about
**10.2 GiB** available. A read-only lock check found no shared Arena holder;
the detached sparse worktree at `c8989d5` was clean and its held capture path
was absent. The repository diagnostic was retried in that sparse tree:

```bash
nice -n 10 /usr/bin/time -v env PYTHONPATH=packages:. \
  /home/charlie/midas/.venv/bin/python -m pytest -q \
  --basetemp=/tmp/midas-frontier-rest-regression-20261028T0445Z \
  --ignore=tests/test_reality_full_scale_validation.py tests
```

The run again reached **101 passed**. At interruption, a test-dispatched Arena
planning child remained active under the pytest temporary root. Static review
identified it as
`tests/arena/test_research_planning.py::test_native_plan_runs_four_fits_and_matched_fresh_studies`.
It calls `create(..., launch=False)` and starts `midas.arena.jobs` directly
with a 300-second worker limit and a 330-second subprocess timeout. The worker
and pytest were CPU-active, so the external lock holder is concurrent host
activity, not evidence that the test waited on the global lock. At
`2026-10-28T04:49:37Z`, an external Veritas batch PID **4194119** held the
shared Arena lock in `DNs` state (about **259 MiB RSS**) and host PSI had risen
to **43.29% some / 37.60% full** over 10 seconds, **33.38% / 28.08%** over 60
seconds, and **19.74% /
16.84%** over 300 seconds. Only Frontier pytest PID **4193289** was sent
SIGINT; the external Veritas process was not signaled. The temporary child job
and pytest process were gone at the post-stop check.

Pytest exited **2** with `KeyboardInterrupt` after **204.34 seconds**; process
wall time was **205.98 seconds**, peak RSS **534,664 KiB**, zero swaps, zero
major faults, and zero socket messages. The run is incomplete and is not a
full-suite pass. The held capture path remained absent after the run; the
sparse test worktree was clean at the post-run check, and no code or test file
was modified. This run ended before the worker's declared subprocess timeout;
it was stopped under high shared-host pressure, not due to a test failure or
timeout. Defer further resource-bearing work until memory PSI and the shared
lock are sampled again.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Broad MIDAS Python regression excluding known Reality collection blocker | PARTIALLY VERIFIED | Two attempts each reached 101 tests, then were interrupted under resource pressure; neither completed. |
| Sparse test data boundary | COMPLETE AND VERIFIED | Held `data/frontier/live-probes` path remained absent before and after both attempts. |
| Protected external Veritas workload | COMPLETE AND VERIFIED | External PID 4194119 and its shared-lock job were left untouched. |
| Further full repository test | DEFERRED AT THIS SAMPLE | High memory PSI and external shared-lock holder remain. |

## Isolated planning test admission stop — 2026-10-28 04:52 UTC

At about `2026-10-28T04:52:00Z`, a fresh admission sample showed no holder of
the shared Arena lock, memory PSI avg10 **0.00% some / 0.00% full**, avg60
**6.36% / 5.51%**, I/O PSI avg10 **1.08% / 0.96%**, and about **10.2 GiB**
available. I launched only the following test, identified by static review as
the active child seen in the two interrupted broad diagnostics:

```bash
nice -n 10 /usr/bin/time -v env PYTHONPATH=packages:. \
  /home/charlie/midas/.venv/bin/python -m pytest -q \
  --basetemp=/tmp/midas-frontier-arena-plan-test-20261028T0452Z \
  tests/arena/test_research_planning.py::test_native_plan_runs_four_fits_and_matched_fresh_studies
```

After roughly 21 seconds, external Veritas batch PID **4437** appeared and held
the global Arena lock. Memory PSI at that sample was **26.81% some / 23.46%
full** over 10 seconds, while the isolated test and its temporary worker were
CPU-active. The worker's test path uses `create(..., launch=False)` and direct
subprocess execution, so the external lock is concurrent activity, not an
established wait dependency. SIGINT was sent only to the Frontier pytest PID.
Pytest exited **2** after **37.95 seconds**, `KeyboardInterrupt`, **no tests
ran**, **441,976 KiB** peak RSS, zero swaps, zero major faults, and zero socket
messages. It was stopped before its 330-second subprocess timeout; no test
result is claimed.

At `2026-10-28T04:52:53Z`, PID 4437 remained and held the shared lock; memory
PSI was **35.37% some / 31.45% full** over 10 seconds. The temporary child
exited, the sparse worktree remained clean, and the held capture path remained
absent. No source or test files changed. Defer further tests until a fresh
admission sample.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Isolated Arena planning test | PARTIALLY VERIFIED | Interrupted after 37.95s under rising PSI; pytest reported no test completed. |
| Held-data isolation | COMPLETE AND VERIFIED | The sparse path remained absent and its worktree remained clean. |
| Further regression | DEFERRED AT THIS SAMPLE | External PID 4437 held the shared lock and short-window PSI was high. |

## Configured Arena lock isolation — 2026-10-28 04:56 UTC

Code commit `bffa163` removes an isolation mismatch: the API and Playwright
configurations already accept a temporary `MIDAS_ARENA_ROOT`, but the shared
Arena/Veritas admission lock still pointed at `~/midas/data/arena`. The Arena
helper now uses the configured root, creates it when absent, rejects an empty
or symlink root, and preserves the previous default when the variable is
unset. The Veritas gap-detail batch now imports the same helper, preventing
the two consumers from diverging.

Verification:

```bash
/home/charlie/midas/.venv/bin/ruff check \
  packages/midas/arena/admission.py scripts/veritas_gap_detail_v2_batch.py \
  tests/arena/test_admission.py tests/test_veritas_gap_detail_v2_batch.py
# All checks passed
/home/charlie/midas/.venv/bin/ruff format --check \
  packages/midas/arena/admission.py scripts/veritas_gap_detail_v2_batch.py \
  tests/arena/test_admission.py tests/test_veritas_gap_detail_v2_batch.py
# 4 files already formatted
nice -n 10 /usr/bin/time -v env PYTHONPATH=packages:. \
  /home/charlie/midas/.venv/bin/python -m pytest -q \
  --basetemp=/tmp/midas-frontier-admission-regression-20261028T0456Z \
  tests/arena/test_admission.py tests/test_veritas_gap_detail_v2_batch.py
# 24 passed in 1.43s; 181,080 KiB peak RSS; zero swaps, major faults, or sockets
```

`git diff --check` passed. The test cases use temporary roots; no exchange
requests, protected service changes, or production lock writes were made. The
focused helper and batch tests prove configured/default path behavior, symlink
rejection, and cross-consumer path equality. Browser end-to-end behavior after
this change remains unverified; no broad test or build was run afterward.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Arena/Veritas configured lock path | COMPLETE AND VERIFIED | Configured root creation, default behavior, symlink refusal, and shared helper are covered by 24 passing tests. |
| Playwright/API runtime integration | PARTIALLY VERIFIED | Playwright already sets the environment variable; end-to-end runtime was not rerun after this change. |
| Project Frontier overall | PARTIALLY VERIFIED | The full repository suite, live cross-venue matching, source authorization, and deployment readiness remain incomplete. |

## Resource admission remains closed — 2026-10-28 04:57 UTC

At `2026-10-28T04:57:41Z`, external Veritas batch PID **8201** had reacquired
the shared Arena lock (`DNs`, **256,804 KiB RSS**). Memory PSI was **39.38%
some / 34.80% full** over 10 seconds, **11.08% / 9.83%** over 60 seconds, and
**11.05% / 9.74%** over 300 seconds; about **10.1 GiB** was available. I/O PSI
avg10 remained below 1%. No further tests or builds were started after the
configured-lock change's 24-test verification. The batch was not signaled.
Next safe action: remeasure; when admitted, run isolated browser verification
and resume repository tests with the Reality import mismatch and bounded
Arena planning case handled separately.

## Admission recheck — 2026-10-28 04:58 UTC

At `2026-10-28T04:58:41Z`, the previously observed Veritas PID 8201 was absent
and no process held the shared Arena lock. Memory PSI was **1.57% some / 1.44%
full** over 10 seconds, **14.55% / 13.22%** over 60 seconds, and **13.02% /
11.62%** over 300 seconds. About **10.3 GiB** was available and I/O PSI avg10
remained below 1%. Although short-window `some` PSI is low, `full` PSI exceeds
the Arena gate's 1% threshold; no test, build, or browser run was started.
Next safe action: remeasure, then run isolated browser verification and resume
the repository suite only when the full-PSI gate and shared lock both admit it.

## Cross-process source collection lease — 2026-10-28 05:05 UTC

Code commit `8fb4c0d` adds a nonblocking `flock` lease per venue to the finite
Frontier collector. The lock is shared across API processes, keeps venues
independent, and is acquired before a new run is recorded. Resume reloads the
latest checkpoint after lease acquisition, avoiding stale sequence writes when
another process finishes the run first. Unsafe/symlink lock paths are rejected;
the OS releases the lease on exceptions, timeout, cancellation, or process exit.

Verification:

```bash
/home/charlie/midas/.venv/bin/ruff check \
  packages/midas/frontier/collection.py tests/frontier/test_collection.py
# All checks passed
/home/charlie/midas/.venv/bin/ruff format --check \
  packages/midas/frontier/collection.py tests/frontier/test_collection.py
# 2 files already formatted
nice -n 10 /usr/bin/time -v env PYTHONPATH=packages:. \
  /home/charlie/midas/.venv/bin/python -m pytest -q \
  --basetemp=/tmp/midas-frontier-collection-regression-20261028T0501Z \
  tests/frontier/test_collection.py
# 21 passed in 6.04s; 67,672 KiB peak RSS; zero swaps or socket messages
```

The focused module tests cross-instance and forked-process exclusion, separate
venue leases, rejection before a competing run is inserted, and release after
cancellation. `git diff --check` passed. No source request, protected service,
production lock, browser, or build was touched. Strict typing and broad
regression after this change remain pending. Strict mypy on
`packages/midas/frontier/collection.py` then passed:

```bash
/home/charlie/midas/.venv/bin/mypy --strict --follow-imports=silent \
  packages/midas/frontier/collection.py
# Success: no issues found in 1 source file
# 134,940 KiB peak RSS; zero swaps or socket messages
```

At approximately `2026-10-28T05:06Z`, no process held the shared Arena lock.
Memory PSI avg10 was **0.01% some / 0.01% full**; I/O PSI avg10 was **0.99% some
/ 0.96% full**. No broad test or browser check started at this marginally
admitted sample. Recheck before broader regression or browser tests.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Per-venue collection lifecycle isolation | COMPLETE AND VERIFIED | Cross-process lock behavior, independent venue leases, no orphan run, and cancellation release are covered by 21 passing collection tests. |
| Full Frontier/MIDAS regression after `8fb4c0d` | PARTIALLY VERIFIED | Collection module passes 21/21; broader suites were not rerun. |
| Strict typing and web runtime after `8fb4c0d` | PARTIALLY VERIFIED | Strict mypy passes for the collection module; web/API typing and browser runtime remain outstanding. |
| Project Frontier overall | PARTIALLY VERIFIED | Live cross-venue economic evidence, broad regression, source authorization, and deployment gates remain open. |

## Initial health probe bounded by collection wall time — 2026-10-28 05:09 UTC

Code commit `6c5c329` moves the first adapter health probe inside the finite
collection timeout. Setup now persists a `created` checkpoint without awaiting
health; the first health observation occurs under the run timeout. A stalled
health call becomes a durable paused run with `COLLECTION_WALL_LIMIT`, and
discovery is not requested. This closes the gap where a health coroutine could
hold the per-venue collector lease beyond `max_wall_seconds`.

The updated collection module passes **23/23** in 7.28 seconds pytest time
(7.67 seconds wall, 68,316 KiB peak RSS, zero swaps and socket messages). Ruff
check/format and `git diff --check` passed. A stalled-health adapter test
confirms the request count remains zero and the run can be loaded from its
durable paused checkpoint. Existing process-lease, venue-independence,
symlink, and cancellation coverage also passes.

Strict mypy passed on `8fb4c0d` before this small refinement. A post-`6c5c329`
rerun and API/browser/full-suite verification remain pending. At approximately
`2026-10-28T05:09Z`, memory PSI avg10 was **0.09% some / 0.08% full**, I/O PSI
avg10 was **3.50% some / 3.12% full**, and no process held the shared Arena
lock. Defer additional resource-bearing checks until a fresh admission sample.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Collection wall-time enforcement | COMPLETE AND VERIFIED | The initial health probe is bounded; the 23-test collection module passes. |
| Strict mypy after `6c5c329` | PARTIALLY VERIFIED | Last strict result was on preceding collector commit `8fb4c0d`; post-refinement check remains. |
| Broader Frontier/MIDAS and browser regression | PARTIALLY VERIFIED | Full suites have not been rerun after latest collector commits. |

## Collection API lease-conflict regression — 2026-10-28 05:12 UTC

Test commit `be73099` adds an API-level busy-lease check. With the
process-shared Polymarket lease held, `POST /api/frontier/collect/polymarket`
returns **409**, makes no adapter discovery request, and leaves the run catalog
empty. The route already maps `FrontierStoreError` to 409; this fixture proves
the behavior end to end through FastAPI/TestClient.

```bash
/home/charlie/midas/.venv/bin/ruff check tests/frontier/test_collection_api.py
# All checks passed
/home/charlie/midas/.venv/bin/ruff format --check tests/frontier/test_collection_api.py
# 1 file already formatted
nice -n 10 /usr/bin/time -v env PYTHONPATH=packages:. \
  /home/charlie/midas/.venv/bin/python -m pytest -q \
  --basetemp=/tmp/midas-frontier-collection-api-regression-20261028T0512Z \
  tests/frontier/test_collection_api.py
# 8 passed in 2.35s; 88,252 KiB peak RSS; zero swaps or socket messages
```

One existing Starlette deprecation warning notes that `httpx` with
`TestClient` is deprecated. This did not fail the tests and no external
network request occurred. At approximately `2026-10-28T05:11Z`, memory PSI
avg10 was **0.00% some / 0.00% full**, I/O PSI avg10 was **2.36% some / 1.92%
full**, and no process held the shared Arena lock. Strict mypy after the
health-timeout refinement and broader tests remain pending.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Collection API conflict handling | COMPLETE AND VERIFIED | Busy cross-process lease maps to 409 with no run insertion or source request; all 8 collection API tests pass. |
| Post-refinement strict typing | PARTIALLY VERIFIED | The previous strict mypy run was on `8fb4c0d`; rerun after `6c5c329`. |
| Full Frontier/MIDAS and browser regression | PARTIALLY VERIFIED | The collection (23/23) and collection API (8/8) modules pass; broad regression remains. |

## Lease release after timeout — 2026-10-28 05:14 UTC

Test commit `f502977` extends the stalled-health test to start a second
same-venue collection after the first run is paused at `COLLECTION_WALL_LIMIT`.
The second run completes, confirming the process-shared lease is released on
timeout.

```bash
nice -n 10 /usr/bin/time -v env PYTHONPATH=packages:. \
  /home/charlie/midas/.venv/bin/python -m pytest -q \
  --basetemp=/tmp/midas-frontier-collection-release-regression-20261028T0515Z \
  tests/frontier/test_collection.py
# 23 passed in 7.56s; 69,780 KiB peak RSS; zero swaps or socket messages
```

The same test module checks forked-process lease exclusion, per-venue
independence, symlink rejection, and no discovery on a health timeout. The
collection API module passes 8/8, including 409 on a busy lease; one existing
Starlette/httpx TestClient deprecation warning remains. No source request or
protected-service operation occurred.

At approximately `2026-10-28T05:14Z`, memory PSI avg10 was **0.05% some / 0.05%
full**, I/O PSI avg10 was **6.98% some / 6.73% full**, and no process held the
shared Arena lock. Defer post-refinement mypy, browser checks, and broader
regression until the I/O gate clears.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Lease release after wall timeout | COMPLETE AND VERIFIED | A second same-venue run completes after the first health probe times out; all 23 collection tests pass. |
| Collection API conflict handling | COMPLETE AND VERIFIED | All 8 API tests pass, including HTTP 409 without a run or discovery request. |
| Post-refinement typing and broader regression | PARTIALLY VERIFIED | Mypy after `6c5c329` and the full Frontier/MIDAS/browser suites remain pending. |

## Combined collector/API regression and post-refinement mypy — 2026-10-28 05:15 UTC

After `6c5c329`, strict mypy passed for the changed collection module. The
complete collection and collection API test modules then passed together:

```bash
/home/charlie/midas/.venv/bin/mypy --strict --follow-imports=silent \
  packages/midas/frontier/collection.py
# Success: no issues found in 1 source file
# 134,740 KiB peak RSS; zero swaps or socket messages

nice -n 10 /usr/bin/time -v env PYTHONPATH=packages:. \
  /home/charlie/midas/.venv/bin/python -m pytest -q \
  --basetemp=/tmp/midas-frontier-collection-combined-20261028T0518Z \
  tests/frontier/test_collection.py tests/frontier/test_collection_api.py
# 31 passed in 9.40s; 91,868 KiB peak RSS; zero swaps or socket messages
```

The suite emitted one existing Starlette deprecation warning for
`httpx`/`TestClient`. It used synthetic adapters, temporary stores, and no
external network or held-capture paths. At approximately `2026-10-28T05:15Z`,
memory PSI avg10 was **0.00% some / 0.00% full**, I/O PSI avg10 was **6.55%
some / 6.10% full**, and no process held the shared Arena lock. Defer broad
Python, browser, and build checks until a fresh sample clears the I/O gate.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Collection and collection API regression | COMPLETE AND VERIFIED | Both modules pass 31/31 together after the latest collector implementation. |
| Strict mypy for the changed collection module | COMPLETE AND VERIFIED | `mypy --strict` passes after `6c5c329`. |
| Full Frontier/MIDAS and browser regression | PARTIALLY VERIFIED | Broader suites remain pending host admission and have not been rerun after the latest collector changes. |

## Full Frontier suite stopped after resource gate closed — 2026-10-28 05:17 UTC

I started `pytest tests/frontier` in `/tmp/midas-frontier-full-suite-20261028T0518Z`
after a clean admission sample. During the test, external Veritas PID **24419**
appeared and held the shared Arena lock; memory PSI reached **18.13% some /
14.58% full**, and I/O PSI reached **4.98% some / 4.42% full**. I sent SIGINT
only to Frontier pytest PID **24413**. I did not signal or modify the external
batch.

Pytest exited **2** with `KeyboardInterrupt` after **19.11 seconds** (**20.14
seconds process wall**), reporting **108 passed** before interruption. Peak
RSS was **323,856 KiB**, with zero swaps, major faults, or socket messages.
The run is not a full-suite pass. The run used only its `/tmp` basetemp; a
source scan found no `live-probes` references in the Frontier tests/package/API,
and the git worktree remained clean.

At the post-stop sample `2026-10-28T05:17Z`, memory PSI avg10 was **44.56% some
/ 36.62% full**, I/O PSI avg10 was **2.48% some / 2.34% full**, and PID 24419
still held the shared Arena lock. No further test, build, browser, or source
request started.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Full Frontier Python regression | PARTIALLY VERIFIED | 108 tests completed before the suite was interrupted; no full pass. |
| Shared-host isolation | COMPLETE AND VERIFIED | Only Frontier pytest was stopped; the external Veritas process and lock were left untouched. |
| Broad regression/browser continuation | DEFERRED | Recheck the Arena lock and short-window PSI after the external job finishes. |

## Monolithic retry stopped by its own I/O pressure — 2026-10-28 05:20 UTC

I retried the monolithic `pytest tests/frontier` run in
`/tmp/midas-frontier-full-suite-retry-20261028T0522Z`. It began under a clean
admission sample with no Arena lock holder. Near 20% progress, I/O PSI reached
**5.43% some / 5.43% full** and no external Veritas process was present. I
stopped only Frontier pytest PID **27532** with SIGINT.

Pytest reported **113 passed** before interruption and exited **2** after
**23.59 seconds** (**24.69 seconds process wall**). Peak RSS was **339,596
KiB**, swaps, major faults, and socket messages were zero, and test output
recorded **139,160 KiB** filesystem output. This is not a full-suite pass.
The test worktree remained clean; static source review found no
`live-probes` path references in the selected Frontier tests/package/API.

At `2026-10-28T05:20Z`, memory PSI avg10 was **0.00% some / 0.00% full**, I/O
PSI avg10 was **1.65% some / 1.59% full**, and no Arena lock holder remained.
Use smaller serial file groups after a fresh admitted sample instead of
another monolithic attempt.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Full Frontier suite | PARTIALLY VERIFIED | Two monolithic attempts stopped after 108 and 113 passing cases; neither completed. |
| Focused collector/API regressions | COMPLETE AND VERIFIED | 31/31 combined; strict mypy passes on the collector. |
| Remaining Python/browser regression | PARTIALLY VERIFIED | Split into resource-aware serial groups after the PSI gate clears. |

## Bounded serial Frontier regression slices — 2026-10-28 05:23 UTC

Four bounded pytest invocations passed **198 tests** total after the collector
change:

| Modules | Tests | Runtime | Peak RSS |
| --- | --- | --- | --- |
| Collection + collection API | 31 | 9.40s | 91,868 KiB |
| Adapters | 62 | 2.51s | 59,976 KiB |
| Analytics, discovery comparison, timeline, logical implication, transport | 25 | 2.31s | 59,444 KiB |
| FX, capital, Kalshi fee, Coinbase, logical-implication economics | 80 | 2.26s | 81,928 KiB |

Each used a separate `/tmp` basetemp, zero swaps, and zero socket messages.
The API-containing runs showed the existing Starlette/httpx TestClient
deprecation warning. A source scan found no `live-probes` path references in
the Frontier tests/package/API. Strict mypy passes for the changed collection
module.

At `2026-10-28T05:23Z`, memory PSI avg10 was **31.74% some / 28.60% full**,
I/O PSI avg10 was **0.39% some / 0.38% full**, and the shared Arena lock was
not held. Defer further tests due to memory pressure. The full suite remains
incomplete; complete module runs still outstanding are `test_api.py`,
`test_relationships_economics_replay.py`, `test_relationship_reviews.py`,
`test_joint_state.py`, `test_storage.py`, `test_replay_comparison.py`,
`test_timeline_api.py`, `test_source_data_permissions.py`, and
`test_held_capture_source_boundary.py`.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Bounded serial regression slices | COMPLETE AND VERIFIED | 198 tests pass across four invocations after the collector changes. |
| Full Frontier/MIDAS suite | PARTIALLY VERIFIED | Two monolithic attempts interrupted; nine modules remain for serial coverage. |
| Browser/build and production deployment | PARTIALLY VERIFIED / DEFERRED | Earlier UI checks pass; no rerun after latest backend work; deployment remains separate. |

## Storage module verification — 2026-10-28 05:25 UTC

The `tests/frontier/test_storage.py` module passes **18/18** in 7.61 seconds
pytest time (7.97 seconds wall) at 69,800 KiB peak RSS, zero swaps, and zero
socket messages. It covers append-only persistence, hash integrity/tampering,
read-only queries, bounded relationship pages, budgets, and additive schema
migrations. It used an isolated `/tmp` basetemp and did not access
`data/frontier/live-probes`.

The test process wrote **98,840 KiB** into temporary SQLite stores. The
post-test sample near 05:24 showed memory PSI avg10 **0.01% some / 0.01% full**
and I/O PSI **7.74% some / 7.24% full**. At 05:24:49, I/O PSI was still just
over the gate at **1.05% some / 1.04% full**, memory PSI was near zero, and no
Arena lock holder was present. Further storage/API tests are deferred until a
fresh sample clears the gate.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Storage integrity and recovery | COMPLETE AND VERIFIED | All 18 storage tests pass in the isolated module. |
| Bounded Frontier regression after collector changes | PARTIALLY VERIFIED | 216 tests pass across five invocations; eight modules remain unrun as complete modules. |
| Further resource-bearing checks | DEFERRED | I/O PSI remains above the 1% threshold at the latest sample. |

## Source-use boundary regression slice — 2026-10-28 05:25 UTC

`tests/frontier/test_held_capture_source_boundary.py` and
`tests/frontier/test_source_data_permissions.py` pass **7/7** in 2.57 seconds
pytest time (3.34 seconds wall) at 141,420 KiB peak RSS, with zero swaps or
socket messages. They verify path guards, fail-closed source permission gates,
and application quarantine behavior. The test process wrote 3,616 KiB into an
isolated `/tmp` directory; no exchange endpoint was queried. One existing
Starlette/httpx TestClient deprecation warning appeared.

At the post-test sample around `2026-10-28T05:25Z`, memory PSI avg10 was
**0.00% some / 0.00% full**, I/O PSI avg10 was **1.13% some / 0.97% full**, and
no Arena lock holder was present. Defer further tests until I/O `some` PSI is
below 1%.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Source-use and held-capture guard tests | COMPLETE AND VERIFIED | All 7 tests pass with no live request or access to historical capture content. |
| Bounded Frontier regression | PARTIALLY VERIFIED | 223 tests pass across six invocations; six modules remain unrun as complete modules. |
| Additional test workloads | DEFERRED | I/O `some` PSI was above the admission threshold at the last sample. |

## Replay comparison and timeline API verification — 2026-10-28 05:27 UTC

`tests/frontier/test_replay_comparison.py` and
`tests/frontier/test_timeline_api.py` passed **8/8** in one bounded invocation:
2.90 seconds pytest time, 3.61 seconds wall, and 211,468 KiB peak RSS. The run
used `/tmp/frontier-replay-timeline-20261028`, had zero swaps and socket
messages, and wrote 4,840 KiB. The existing Starlette/httpx TestClient
deprecation warning appeared.

The immediate post-run sample measured memory PSI avg10 **0.00% some / 0.00%
full** and I/O PSI avg10 **1.52% some / 1.37% full**; no Frontier pytest or
Arena research lock holder was active. Hold further tests until I/O `some`
PSI is below 1%.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Replay comparison and timeline API modules | COMPLETE AND VERIFIED | Both complete modules pass 8/8 in an isolated temporary directory. |
| Serial Frontier regression coverage | PARTIALLY VERIFIED | 231 tests pass across seven bounded invocations; four modules remain unrun as complete modules. |
| Additional resource-bearing tests | DEFERRED | Post-run I/O PSI exceeded the admission threshold. |

## Relationship review module verification — 2026-10-28 05:29 UTC

`tests/frontier/test_relationship_reviews.py` passed **13/13** in 4.72 seconds
pytest time (5.22 seconds wall) at 104,492 KiB peak RSS. It used
`/tmp/frontier-relationship-reviews-20261028`, with zero swaps and socket
messages; the existing Starlette/httpx TestClient deprecation warning appeared.

The post-run sample measured memory PSI avg10 **0.02% some / 0.01% full** and
I/O PSI **2.85% some / 2.10% full**. No Frontier test or shared Arena
admission lock holder was active. Defer further tests until I/O `some` PSI is
below 1%.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Relationship review module | COMPLETE AND VERIFIED | All 13 tests pass in isolation. |
| Serial Frontier regression coverage | PARTIALLY VERIFIED | 244 tests pass across eight bounded invocations; three modules remain unrun as complete modules. |
| Additional resource-bearing tests | DEFERRED | Post-run I/O PSI exceeded the admission threshold. |

## API regression, collection/overview slice — 2026-10-28 05:31 UTC

The API module collects to **55 test cases**. The first bounded slice,
`collection_api`, `collection_history`, overview, coverage analytics, saved
Kalshi fee-pair joining, and the disabled public-probe guard, passed **9/9**
in 3.31 seconds pytest time (3.80 seconds wall) at 97,360 KiB peak RSS. It
used `/tmp/frontier-api-collection-overview-20261028`, with zero swaps and
socket messages. The existing Starlette/httpx TestClient deprecation warning
appeared.

At the immediate post-run sample, memory PSI avg10 was **0.00% some / 0.00%
full** and I/O PSI was **2.07% some / 1.38% full**. No Frontier tests or Arena
admission lock holder remained active. Defer the other API slices until I/O
`some` PSI drops below 1%.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| API collection and overview slice | COMPLETE AND VERIFIED | 9 selected cases pass; 46 API cases remain in three bounded slices. |
| Serial Frontier regression coverage | PARTIALLY VERIFIED | 312 cases pass across eleven bounded invocations; the API module is still partial. |
| Full Frontier regression | PARTIALLY VERIFIED | No full-suite pass is claimed. |

## API regression, source-probe slice — 2026-10-28 05:32 UTC

The source-probe and metadata slice passed **12/12** in 6.52 seconds pytest
time (7.01 seconds wall) at 103,256 KiB peak RSS. It used
`/tmp/frontier-api-source-probes-20261028`, with zero swaps and socket
messages. The existing Starlette/httpx TestClient deprecation warning
appeared.

The post-run sample measured memory PSI avg10 **0.00% some / 0.00% full** and
I/O PSI **2.95% some / 2.12% full**. No Frontier test or shared Arena
admission lock holder was active. Hold further test work until I/O `some`
PSI falls below 1%.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| API collection/overview and source-probe slices | COMPLETE AND VERIFIED | 21 of 55 API cases pass across two isolated slices; 34 remain. |
| Serial Frontier regression coverage | PARTIALLY VERIFIED | 324 cases pass across twelve bounded invocations; the API module is partial. |
| Remaining API slices | DEFERRED | I/O PSI rose above the admission threshold after the second slice. |

## API regression, replay/readiness slice — 2026-10-28 05:33 UTC

The replay, Arena staging, readiness, corruption-handling, and candidate replay
slice passed **19/19** in 7.50 seconds pytest time (8.31 seconds wall) at
243,040 KiB peak RSS. It used `/tmp/frontier-api-replay-readiness-20261028`,
with zero swaps and socket messages. The existing Starlette/httpx TestClient
deprecation warning appeared.

The immediate post-run sample measured memory PSI avg10 **0.00% some / 0.00%
full** and I/O PSI **2.58% some / 2.23% full**. No Frontier test or Arena
admission lock holder was active. Defer the final API slice until I/O `some`
PSI is below 1%.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| API regression slices | PARTIALLY VERIFIED | 40/55 API cases pass across three isolated slices; the final 15 remain. |
| Serial Frontier regression coverage | PARTIALLY VERIFIED | 343 cases pass across thirteen bounded invocations. |
| Remaining API tests | DEFERRED | Post-run I/O PSI exceeded the admission threshold. |

## Frontier serial regression completion — 2026-10-28 05:35 UTC

The final API graph/trade-read/capture-lineage slice passed **15/15** in 11.60
seconds pytest time (12.11 seconds wall) at 113,792 KiB peak RSS. It used
`/tmp/frontier-api-graph-trades-20261028`, with zero swaps and socket messages.
The existing Starlette/httpx TestClient deprecation warning appeared.

The API test module collected to **55 cases** and is now fully covered by four
non-overlapping slices:

| Slice | Cases | Pytest time | Peak RSS |
| --- | ---: | ---: | ---: |
| Collection, overview, coverage | 9 | 3.31s | 97,360 KiB |
| Source probes and metadata | 12 | 6.52s | 103,256 KiB |
| Replay, Arena staging, readiness | 19 | 7.50s | 243,040 KiB |
| Graph, trade reads, capture lineage | 15 | 11.60s | 113,792 KiB |

Together with the earlier bounded slices, **all 22 `tests/frontier/test_*.py`
modules completed successfully**, totaling **358 passing cases across 14
bounded invocations**. There were zero swaps and zero socket messages in the
recorded invocations. The two monolithic `pytest tests/frontier` attempts
remain interrupted after 108 and 113 cases; no single-process full-suite pass
is claimed.

After the final API slice, memory PSI avg10 was **0.00% some / 0.00% full**;
I/O PSI was **4.09% some / 3.01% full**. No Frontier test or Arena admission
lock holder remained active. Defer the frontend build/browser workload until
I/O `some` PSI falls below 1%.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Python modular regression | COMPLETE AND VERIFIED | All 22 Frontier test modules pass across bounded slices: 358 cases in 14 invocations. |
| Single-process full Frontier suite | PARTIALLY VERIFIED | Two monolithic attempts were interrupted; no complete one-process run. |
| Frontend build and browser integration | DEFERRED | Prior UI results exist, but current post-backend rerun is pending an admission sample. |

## Current frontend and integration verification — 2026-10-28 05:38 UTC

The current branch frontend now passes:

- Production build: `corepack pnpm build` completed `tsc -b` and Vite in
  13.75 seconds wall time at 664,720 KiB peak RSS, with zero swaps or socket
  messages.
- Unit suite: **40/40** across seven files in 6.67 seconds Vitest time (7.70
  seconds wall) at 290,488 KiB peak RSS; zero swaps or socket messages.
- Frontier browser integration: **6/6** in 15.5 seconds Playwright time
  (16.35 seconds wall) at 199,036 KiB peak RSS. Playwright used an isolated
  demo API, temporary SQLite/Arena/Frontier roots, and local Vite; its services
  exited and ports 15173/18000 were free afterward. These fixture/local flows
  made no exchange probe and did not submit orders.
- `corepack pnpm lint` and `corepack pnpm format:check` passed. Targeted Ruff
  check and format verification pass for the changed collector and its tests;
  strict mypy for the collector passes from the earlier checkpoint.

Vite retains its chunk-size warning: the main bundle is 504.00 kB and the
Chart bundle is 544.41 kB. Frontier's lazy bundle is 164.53 kB JavaScript and
48.35 kB CSS. The build is successful; the advisory remains a performance
follow-up.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Python modular regression | COMPLETE AND VERIFIED | All 22 Frontier modules pass: 358 cases in 14 bounded invocations. |
| Frontier frontend unit/build/lint/format | COMPLETE AND VERIFIED | 40 unit cases, TypeScript/Vite build, lint, and Prettier pass. |
| Frontier browser integration | COMPLETE AND VERIFIED | Six Frontier Playwright cases pass against isolated local demo services. |
| Single-process full Python suite | PARTIALLY VERIFIED | Two large invocations were interrupted; module-by-module coverage is complete. |
| Live second-venue relationship/economics | BLOCKED | Existing source-use holds remain; no genuine cross-venue equivalence or opportunity is claimed. |
| Production transition | DEFERRED | Branch remains isolated and undeployed; separate source, resource, recovery, and deployment review is required. |

## Package-wide Frontier static analysis — 2026-10-28 05:43 UTC

Strict typing now covers the complete Frontier Python package and its API
integration route:

- `mypy --strict --follow-imports=silent packages/midas/frontier`: **23 source
  files**, no issues, 5.38 seconds wall, 199,892 KiB peak RSS.
- The same check with `apps/api/frontier.py`: **24 source files**, no issues,
  28.84 seconds wall, 723,472 KiB peak RSS.
- Ruff check passed across `packages/midas/frontier`,
  `apps/api/frontier.py`, and `tests/frontier`; Ruff format check reports all
  **51 files** already formatted.

Both mypy caches were isolated under `/tmp`; both processes used zero swaps.
The post-check PSI sample was memory avg10 **0.00% some/full** and I/O avg10
**0.00% some / 0.00% full**. No services, source data, or persistent research
stores were accessed or modified.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Frontier Python package and API strict typing | COMPLETE AND VERIFIED | 24 source files pass strict mypy. |
| Frontier Python lint and formatting | COMPLETE AND VERIFIED | Ruff check passes and all 51 relevant files are formatted. |
| Live multi-venue validation | BLOCKED | Existing source-use restrictions prevent a second-venue observation. |
| Production eligibility | DEFERRED | No deployment or protected-service transition was attempted. |

## Legacy-suite baseline audit — 2026-10-28 05:46 UTC

The current Frontier branch descends from the V6 integration commit
`11d32a0`; its merge base with `main` is `55601b9`. The repository-wide test
collection blocker is specific: the tracked
`tests/test_reality_full_scale_validation.py` imports
`midas.reality.recovery`, which the selected Frontier/V6 tree does not contain.

The recovery module exists on a separate Reality lineage. Comparing that
lineage's corrected recovery commit `c2e73eb` with the Frontier V6 baseline
shows **761 insertions and 233 deletions** across `collector.py`,
`reconstruction.py`, `replay.py`, and `storage.py`. The candidate source
worktrees also contain unrelated dirty or untracked files. No source file was
transplanted and no other worktree was changed. Resolving this regression
requires a deliberate Reality compatibility port or a verified integrated
baseline; copying only `recovery.py` would not test compatible source.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Frontier/V6 baseline identity | COMPLETE AND VERIFIED | Ancestry and merge-base were checked from the current Git graph. |
| Full MIDAS repository regression | PARTIALLY VERIFIED | Collection is blocked by the missing Reality recovery module; full-suite execution is not claimed. |
| Cross-lineage Reality recovery integration | DEFERRED | Dependency code differs materially and was not merged into the isolated Frontier branch. |

## Coinbase scope gate correction — 2026-10-28 05:54 UTC

The terms review already documented that an exact Coinbase Market Data Terms
version acknowledgment does not resolve the applicable organization, region,
retention, derived-data, display, or automated-system scope. The API
configuration nevertheless combined that acknowledgment and the public-probe
flag as sufficient to enable a source request. Commit `8748a53`
(`fix(frontier): keep Coinbase behind scope permission gate`) removes that
inconsistency: the API keeps Coinbase disabled and held until a validated
permission and intended-scope review loader exists. The exact-version field is
retained as an acknowledgment record, not authorization. Held Coinbase
observations remain quarantined even when both settings are supplied.

Verification used only synthetic local fixtures:

- `pytest -q tests/frontier/test_source_data_permissions.py`: **5 passed** in
  2.65 seconds; 141,712 KiB peak RSS; zero swaps or socket messages. The
  matched-version-plus-probe case returns HTTP 409 with zero transport requests
  and confirms held stored evidence remains hidden.
- `corepack pnpm exec vitest run src/Frontier.test.tsx`: **8 passed**; the
  source warning text and existing Frontier research interactions render.
- Strict mypy passed for **26 source files** across the Frontier package and
  API config/startup/routes. Ruff, Python format check, full web Prettier check,
  and `git diff --check` pass.

No Coinbase request, source artifact access, service action, or deployment
occurred. Kalshi and Kraken remain held by the same lack of validated
permission. Live cross-venue equivalence and economics therefore remain
unverified.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Coinbase API source-use gate | COMPLETE AND VERIFIED | Exact terms acknowledgment plus probe flag still returns HTTP 409 before transport; source records remain quarantined. |
| Coinbase intended-scope permission | BLOCKED | Applicable organization, jurisdiction, retention, derived-data, and display scope has no validated permission record or loader. |
| Live multi-venue relationship | BLOCKED | Other venues remain held; no genuine equivalent cross-venue exposure is established. |

## Polymarket price-history checkpoint — 2026-10-28 06:15 UTC

**Stage:** B (Multi-Source Integration), with Market detail UI integration.
**Code commit:** `f0a5957` on `codex/frontier-20261026`.

Added a distinct `PRICE_HISTORY` capability and `PriceHistorySeries` model for
Polymarket CLOB source-reported price points. The Polymarket adapter is now v7;
it deliberately leaves `HISTORICAL_CANDLES` unsupported. Adapter and API bounds
are 1d/1w source intervals, a 7-day request window, at most 1500 points, and the
configured HTTP response limit. Price values are exact decimals in `[0,1]`;
timestamps must be integral Unix seconds, ordered, unique, and within the
requested window. The API refuses tokens absent from the bounded recorded
market listing and stores the listing observation ID with the normalized series.
The GET route is local persisted evidence only. Mission Control now offers an
explicit 1/3/7-day capture and displays the returned samples with evidence
inspection. Price samples are not executable quotes, OHLC, or volume.

Live source result: one documented public token returned HTTP 200 for a
2026-07-29 to 2026-08-05 request at `interval=1d`, `fidelity=60`. The response
contained 79 points and 2139 bytes, SHA-256
`0b69fa1f31cd9618e922ab681c41c67e4de51d5572e662fa3db1d3267e50afc8`. The exact
body and capture metadata are preserved in
`tests/fixtures/polymarket_price_history_live_20261028.json` and its `.meta.json`
sidecar. A repeat GET had the same body hash. Thirty-day and 36-day requests
returned HTTP 400 (`startTs`/`endTs` interval too long); because the official
reference publishes no maximum accepted range, Frontier now caps requests at
seven days. The rejection status/message are recorded in the sidecar; the
failed bodies were not stored as independent `RawObservation` records.

Verification:

- `tests/frontier/test_adapters.py`: **67 passed** in 2.53 seconds, including
  fixture replay of the genuine public response.
- `tests/frontier/test_api.py`: **56 passed** in 45.11 seconds.
- `apps/web/src/Frontier.test.tsx`: **8 passed** in 5.39 seconds, including a
  fixture-backed explicit history capture and confirmation that no request
  starts automatically.
- `apps/web/e2e/frontier.spec.ts`: **6 passed** in 15.6 seconds with isolated
  local demo services.
- Strict mypy passed for the five changed Python source modules; Ruff check and
  formatting, web lint, Prettier, TypeScript, Vite production build, and
  `git diff --check` passed. The build retains its existing 504/544 kB bundle
  advisory; API tests retain the Starlette/httpx deprecation warning.

No production service or runtime Frontier store was used for the live read. No
authenticated call, credential, account access, order, deployment, or
cross-venue economics was involved. Kalshi, Kraken, and Coinbase remain held.

| Component | Status | Next boundary |
| --- | --- | --- |
| Polymarket historical price adapter | COMPLETE AND VERIFIED | Current 7-day bound is conservative, based on observed errors rather than a published maximum. |
| Price-history API persistence and saved read | COMPLETE AND VERIFIED | In-process API integration passes; no production deployment. |
| Market detail history UI | COMPLETE AND VERIFIED | Fixture component flow passes; no dedicated browser E2E action for history yet. |
| Multi-venue use of historical prices | DEFERRED | No history-based relationship or economic candidate is generated. |
| Live second-venue validation | BLOCKED | Kalshi, Kraken, and Coinbase source-use holds remain in effect. |

**Next safe action:** continue isolated single-source research tooling by adding
price-history series to deterministic local replay and source-quality summaries;
keep the series contextual unless a validated payoff or executable quote model
can use it. Do not probe held venues or deploy.

## Deterministic price-history replay and coverage — 2026-10-28 06:34 UTC

**Stage:** E (Scientific replay and source-quality summaries), integrated into
the existing Mission Control Frontier workspace.
**Code commit:** `2e27f1102d8055f822b41ad40b02421385d7df33` on
`codex/frontier-20261026`.

Added `packages/midas/frontier/historical_replay.py`, a separate deterministic
description path for one to eight saved historical-price captures. It validates
the stored observation/raw-row hashes, normalized venue/raw-body/receipt
provenance, and any market-observation binding and native instrument. Its
versioned manifest pins sorted observation IDs, normalized input hash, code
version, and replay time. The result records each series' exact sampled price
minimum/maximum, first and last point, observed span, largest adjacent returned
point gap, and point timestamps later than local receipt. It explicitly sets
`candidate_generation` to `not_performed`; these are point-sample summaries,
not quotes, candles, fills, missing-data estimates, or opportunities.

The append-only Frontier store advances from schema 6 to 7 and adds a separate
`price_history_replays` table with row validation and update/delete triggers.
Existing evidence rows are unchanged. The API accepts stored observation IDs
only, makes no network call, checks any saved market binding, persists a
reproducible result, and exposes bounded list/detail reads. Held and missing
source evidence is rejected for a new run and omitted from saved reads. A
focused policy fixture confirms held Kalshi replay artifacts and history
captures remain in the temporary evidence store but do not enter replay reads
or coverage summaries.

Coverage analytics now read at most the newest 20 eligible stored history
captures and report capture/instrument/point counts, empty and unbound series,
future timestamps, capture age, point timestamp bounds, and largest observed
adjacent gap by venue. Overlapping captures remain separately counted, so a
point total can contain repeated samples. The existing Mission Control Coverage
view shows this evidence with explicit completeness limits. The Market detail
history panel adds a user-triggered “Replay saved series” action and displays
the run/input hashes, sample price range, and largest observed gap; it never
replays automatically after a capture or page load.

Verification on the committed implementation:

- `pytest -q tests/frontier/test_historical_replay.py tests/frontier/test_analytics.py tests/frontier/test_storage.py`:
  **31 passed** in 18.60 seconds, covering deterministic ordering, exact
  summaries, bounded inputs, schema-6 migration, append-only persistence, and
  corrupted-result rejection.
- `pytest -q tests/frontier/test_api.py`: **56 passed** in 48.39 seconds.
  A final focused API and held-source run passed **2 tests** in 2.97 seconds
  after the saved-list response added explicit held-row and incomplete-scan
  counts.
- `pytest -q tests/frontier/test_source_data_permissions.py`: **5 passed** in
  3.23 seconds; the existing Starlette/httpx deprecation warning remains.
- `corepack pnpm --dir apps/web test`: **40 passed** across 7 files; the
  Frontier suite includes explicit capture and saved replay rendering.
- `corepack pnpm --dir apps/web exec playwright test e2e/frontier.spec.ts`:
  **7 passed** in 15.5 seconds on isolated local services. The added browser
  scenario intercepts the historical source request with a fixture, asserts
  there is no request before the click, verifies the request is capped to 7
  days, and checks the separate replay click and output. No live source was
  contacted by this E2E scenario.
- TypeScript, ESLint, Prettier, Ruff check/format, `git diff --check`, and the
  production frontend build pass. Vite transformed 2,228 modules; its existing
  504.00 kB main and 544.41 kB Chart chunk advisory remains.
- Strict mypy with `--follow-imports=silent` passes for the four changed Python
  source modules. The unsuppressed import traversal reports **14 errors in
  imported Veritas and Arena files** (`independent_economics.py`,
  `analysis_catalog.py`, `continuous_analysis.py`, and `arena/director.py`);
  it reports no errors in the four changed modules.

No feature-specific RSS/CPU profile was captured. The replay computation is
bounded to eight series of at most 1500 points each, and all persistence and API
verification used temporary test databases. No service store was migrated, no
source probe, authenticated request, order, deployment, or cross-venue
economic calculation occurred.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Deterministic historical sample replay | COMPLETE AND VERIFIED | Hash-pinned, order-independent result; API and storage tests pass; generates no candidate. |
| Schema-7 persistence and schema-6 migration | COMPLETE AND VERIFIED | Temporary-database tests cover migration, immutable rows, idempotency, and tamper detection. |
| Held-source replay and coverage quarantine | COMPLETE AND VERIFIED | Kalshi capture/replay fixture is not visible through research reads or analytics. |
| Coverage and Market detail replay interface | COMPLETE AND VERIFIED | Component suite and seven browser tests pass with fixture-backed replay. |
| Historical sample use in economic analysis | DEFERRED | No history-based payoff, quote, hedge, or opportunity is modeled. |
| Live second-venue relationship/economics | BLOCKED | Kalshi, Kraken, and Coinbase remain held; no genuine cross-venue match is claimed. |
| Production migration/deployment | DEFERRED | Only isolated code and temporary test stores were used. |

**Next safe action:** connect the bounded replay artifact to the existing
Research & Replay inspection view, allowing selection of multiple saved IDs up
to the eight-series cap and detailed lineage inspection. Keep every series
classified as source-reported historical context. Do not probe held venues or
migrate a service database.

## Research & Replay history lineage inspector — 2026-10-28 06:44 UTC

**Stage:** E/F (saved replay inspection in Mission Control).
**Code commit:** `ce8d7dd` on `codex/frontier-20261026`.

The Replay & readiness workspace now lists the newest 20 saved Polymarket
historical-price captures and the newest 20 descriptive price-history replay
artifacts. A researcher may select one through eight stored capture IDs and
explicitly submit a local replay. The view reads saved list/detail routes only;
it does not start a source request and it states that candidate generation was
not performed. A component test fills eight selections, verifies the ninth is
disabled, reduces the selection, then checks that only the selected two IDs are
submitted.

Saved replay rows can be selected for hash-verified detail reads. The inspector
shows run, input, and result identities; replay and code versions; maximum
input receipt time; and per-series source observation ID, raw response hash,
venue, native instrument, optional bound market observation, request interval,
capture receipt when it is still in the source page, returned price bounds,
point-time bounds, adjacent returned-point gap, and future-point count. If a
capture is older than the bounded source page, the UI says the per-series
receipt time is outside that page. It retains the source-sample limits: no
missing-data estimate, synchronized-availability claim, quote, fill, or
opportunity is presented.

Verification on this checkpoint:

- `corepack pnpm test`: **41 passed** across seven frontend test files,
  including the eight-series selection cap and multi-series lineage render.
- `corepack pnpm exec playwright test e2e/frontier.spec.ts`: **7 passed** on
  isolated local services. The updated price-history scenario intercepts the
  capture and replay APIs, selects two saved samples, checks lineage, and
  confirms the page stays within 390 px without horizontal overflow.
- `corepack pnpm build`: TypeScript project build and production Vite build
  pass (2,228 modules transformed). Existing bundle advisories remain for the
  504.00 kB main chunk and 544.41 kB Chart chunk; the Frontier chunk is
  181.57 kB.
- ESLint, Prettier check, and `git diff --check` pass. No Python or API code
  changed in this checkpoint.

The API contract and page behavior were exercised with local fixture responses;
the inspector was not validated against a populated service store. There was
no live source request, authenticated request, service-store migration,
deployment, resource profile, or economic evaluation. Source-use holds for
Kalshi, Kraken, and Coinbase remain; the UI currently offers the usable
Polymarket historical-price source only.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Bounded multi-series selection | COMPLETE AND VERIFIED | Component test proves the 1..8 UI bound and exact submitted IDs. |
| Saved replay list and detail inspector | PARTIALLY VERIFIED | Fixture-backed list/detail integration and display pass; no populated service-store UI run. |
| Source and input lineage display | COMPLETE AND VERIFIED | IDs, raw hashes, instrument, binding, requested range, sample bounds, and receipt context are exposed. |
| Additional venue price-history selection | BLOCKED | Other candidate venues remain under source-use holds; no unsupported data is exposed. |
| Production migration/deployment | DEFERRED | No service configuration or data store was touched. |

**Next safe action:** add bounded offset paging for saved capture and replay
lists, preserving the eight-input cap and showing page/truncation state. Keep
the reads local and held-source aware. Do not probe held venues or migrate a
service database.

## Bounded paging for saved price-history evidence — 2026-10-28 06:53 UTC

**Stage:** E/F (local replay evidence access).
**Code commit:** `797e00a` on `codex/frontier-20261026`.

Both saved history APIs now return exact `has_more` state using a one-row
lookahead while keeping their response page bounded. `GET /price-history`
continues to return at most 20 rows, accepts offsets up to 100,000, and reports
the 20-row response bound separately from the lookahead. `GET
/price-history/replays` pages stored artifacts similarly, with its API limit
still capped at 100. The replay route applies the offset to stored rows before
held-source filtering; it counts omitted held rows only in the displayed page.
Thus held records cannot be returned, and they do not make `has_more` falsely
stop before later eligible records.

The Mission Control inspector now has Previous/Next navigation for both
capture and replay lists, 20 records per page. It clears selected capture IDs
when moving source pages and preserves the backend eight-series replay cap.
Moving replay pages resets artifact selection to the first available row on the
new page. Page counts and held-row omission counts remain visible.

Verification:

- `/home/charlie/midas/.venv/bin/python -m pytest -q tests/frontier/test_api.py`:
  **56 passed** in 29.57 seconds. The price-history API test now covers first
and final capture/replay pages with `limit=1`, including both `has_more`
transitions.
- `/home/charlie/midas/.venv/bin/python -m pytest -q tests/frontier/test_source_data_permissions.py`:
  **5 passed** in 3.51 seconds; the existing Starlette/httpx deprecation
  warning remains.
- `corepack pnpm test`: **41 passed** across seven frontend test files. The
  Frontier test verifies 20-row navigation, clearing selection, and the
  eight-selected/ninth-disabled limit.
- `corepack pnpm exec playwright test e2e/frontier.spec.ts`: **7 passed** on
  isolated local services; the captured-series flow and 390 px responsive
  check remain green.
- `corepack pnpm build`: TypeScript and production build pass; Vite transforms
  2,228 modules. Frontier bundle is 182.67 kB; existing main/Chart advisories
  are 504.00 kB and 544.41 kB.
- ESLint, Prettier check, Ruff check/format, and `git diff --check` pass.

A strict mypy run of `apps/api/frontier.py` reported 15 `no-any-return`
diagnostics on unchanged lines elsewhere in the route module; none point to
the new paging code. No resource profile was captured. API tests use mock
transports and temporary stores; browser history routes use explicit fixture
intercepts. No live venue request, service-store migration, deployment, or
economic evaluation occurred.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| `has_more` lookahead for source history | COMPLETE AND VERIFIED | API test covers nonfinal and final pages at a one-row page size. |
| `has_more` with held replay filtering | COMPLETE AND VERIFIED | Page slicing precedes held filtering; omitted count is page-scoped. Source permission suite passes. |
| Mission Control paging controls | COMPLETE AND VERIFIED | Component test pages source captures and clears page-local selections; browser suite is responsive. |
| Populated-store UI/API end-to-end | PARTIALLY VERIFIED | API persistence and page behavior use temporary stores; browser UI uses fixture-intercepted history responses. |
| Multi-venue saved price-history paging | BLOCKED | Other source-use holds remain in force; only Polymarket history is selectable. |
| Production migration/deployment | DEFERRED | No service database or configuration was changed. |

**Next safe action:** add a bounded browser integration that seeds a dedicated
temporary Frontier store with fixture-backed saved captures and replay rows,
then drives the inspector against the actual local API routes. Keep all data in
the isolated test store and do not probe or migrate any protected service.

## Persisted history browser/API integration — 2026-10-28 06:59 UTC

**Code commit:** `3251941` on `codex/frontier-20261026`.

Added an explicit opt-in Playwright scenario backed by a disposable Frontier
SQLite store. The Python seeder writes 21 versioned fixture captures and 21
deterministic replay artifacts using the same immutable storage APIs as normal
research data; it refuses to overwrite an existing store. It does not contact
Polymarket or any other venue. The browser configuration creates one isolated
temporary root and seeds only when `MIDAS_SEED_FRONTIER_E2E=1` is set. The
default unseeded suite remains unchanged.

The browser scenario reads first and final capture/replay pages through the
real local FastAPI routes, checks `has_more`, submits a two-series descriptive
replay through the UI, re-reads the saved run by its identity, inspects source
lineage, then navigates both older pages. It asserts zero `/probe/` requests.
The fixture values remain synthetic test inputs; a passing API-backed UI flow
is not a live source validation or an economic result.

Verification:

- `MIDAS_SEED_FRONTIER_E2E=1 corepack pnpm exec playwright test e2e/frontier.seeded.spec.ts`:
  **1 passed** against the real local API and temporary seeded store.
- `corepack pnpm exec playwright test e2e/frontier.spec.ts`: **7 passed** on
  isolated local services with no venue request.
- `corepack pnpm test`: **41 passed** across seven frontend files.
- TypeScript project check, ESLint, Prettier, Ruff check/format, and
  `git diff --check` pass. The production build passes after 2,228 modules;
  its existing main/Chart chunk-size advisory remains.
- Direct seeder verification confirmed 21 persisted captures and 21 replay
  artifacts, with correct newest-first page boundaries.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Saved-history API and UI over persisted data | COMPLETE AND VERIFIED | Isolated temporary store, real local routes, UI replay POST and lineage detail; no source probe. |
| Seed fixture safety | COMPLETE AND VERIFIED | Explicit opt-in, temporary-root check, overwrite refusal, deterministic versioned rows. |
| Live source response validation | BLOCKED | Current venue-use holds remain; fixtures do not satisfy live validation. |
| Production store or service integration | DEFERRED | No protected database, service, or deployment was touched. |

Changed files in `3251941`: `apps/web/playwright.config.ts`,
`apps/web/e2e/frontier.seeded.spec.ts`, and
`apps/web/e2e/seed_frontier_store.py`. Operations and architecture docs were
updated in this documentation checkpoint. **Next safe action:** continue the
remaining source-independent acceptance matrix, prioritizing bounded replay,
resource, and supervisor gaps; remeasure host admission before any broad or
resource-intensive run. Preserve all source-use holds and production state.

## Host admission recheck after the browser integration — 2026-10-28 07:03 UTC

At `2026-10-28T07:02:48Z`, `/home/charlie/midas/data/arena/.global-admission.lock`
was held by PID **115803**, running
`/home/charlie/midas/.venv/bin/python -S scripts/veritas_gap_detail_v2_batch.py`
inside `midas-veritas-gap-detail-v2.service`. It exited before the next sample;
the lock had no holder at `2026-10-28T07:03:02Z`. No signal or other action was
taken against the worker or its stores.

At `2026-10-28T07:03:02Z`, memory PSI avg10 was **32.56% some / 29.27% full**;
I/O PSI avg10 was **0.70% some / 0.70% full**. Available host memory was about
10.7 GiB, with about 0.52 GiB swap free. No resource-bearing Frontier test,
build, or Arena launch followed this sample because the memory-pressure gate
was not clear. These are time-specific host measurements, not a capacity
claim.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Additional resource-bearing acceptance runs | DEFERRED | Memory PSI remained high despite I/O PSI falling below 1%; no admission or sustained-resource claim. |
| Protected Veritas worker | COMPLETE FOR THIS SAMPLE | PID 115803 exited and released the shared lock; its run and artifacts were left untouched. |

**Next safe action:** remeasure memory/I/O PSI and the shared Arena lock before
the next resource-bearing test. Continue independent code review and
documentation while the host gate is closed; do not stop another workload or
bypass shared admission.

## Complete default browser regression — 2026-10-28 07:05 UTC

At the pre-run sample, memory PSI avg10 was **0.00% some / 0.00% full**, I/O
PSI avg10 was **0.92% some / 0.84% full**, about **10 GiB** memory was
available, and no process held the shared Arena lock. The default full web
browser command completed:

```bash
cd apps/web
corepack pnpm exec playwright test
# 15 passed, 1 skipped in 33.8s
```

The one skipped test is `frontier.seeded.spec.ts`, which requires the explicit
`MIDAS_SEED_FRONTIER_E2E=1` flag and had separately passed **1/1** against the
isolated populated-store path. The default suite covered Frontier, Arena,
Laboratory, Paper, Readiness, Reality, and Veritas. It used temporary roots and
loopback services; no public source request or order was submitted.

At the post-run sample `2026-10-28T07:05:07Z`, memory PSI avg10 stayed at
**0.00% some / 0.00% full**, while I/O PSI avg10 rose to **1.09% some / 0.88%
full**. About **10 GiB** was available, swap free was about **0.52 GiB**, and
the shared lock remained unheld. No additional resource-bearing test followed
because I/O `some` was above the strict 1% threshold.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Complete default web browser regression | COMPLETE AND VERIFIED | 15 pass, 1 intentionally opt-in skip across all seven user workspaces. |
| Populated saved-history browser/API path | COMPLETE AND VERIFIED | Separate opt-in test passes against temporary seeded storage and actual local API. |
| Further resource-bearing runs | DEFERRED | Post-run I/O PSI `some` exceeded 1%; remeasure before another run. |

**Next safe action:** remeasure I/O PSI and the shared Arena lock before another
resource-bearing run. Continue only source-independent implementation or code
review while that admission gate is closed; preserve all held-source and
production boundaries.

## Laboratory read-only Frontier study history — 2026-10-28 07:13 UTC

The existing Laboratory now has a **Frontier research** tab backed by Arena's
existing bounded discovery-job catalog and completed-result endpoints. Users
can select any listed job; only completed artifacts whose hashes were verified
by the Arena API are summarized. The detail includes the three scope summaries,
paired deltas, snapshot/result hashes, and discovery/replay versions. The view
does not submit a job, contact a venue, or copy multi-market evidence into the
legacy single-market Laboratory campaign model. Job creation remains in the
Frontier workspace and uses existing Arena admission.

The initial implementation and test run passed the focused Laboratory file
**4/4**, the complete frontend unit suite **43/43**, and `pnpm typecheck`.
Tests covered selection of a retained older job, route identity, result
integrity gating, reproducibility fields, and navigation; API responses were
mocked in component tests. A final accessibility review then moved job-card
selection to a proper nested button, avoiding block content inside a `<button>`.
At this checkpoint, the final markup and fixture-routed browser case had not yet
been rechecked. Later verification is recorded below. Commit `afcc726` adds the
route-fixture Playwright case; `91e61d7` opens the disclosure before asserting
visible reproducibility values.

Commit `a875ee2` strengthens the explicit opt-in seeded browser test. Its
temporary-root seeder now stores one Polymarket-only discovery snapshot,
completed result, and Arena job manifest using Frontier's content-addressed
artifact writer. A new browser case reads the saved job and hash-verified
result through the real local Arena API, then inspects it in Laboratory. The
fixture is synthetic, makes no source call, and writes directly into a fresh
temporary Arena root; it does not start a supervised Arena worker. This new
seeded API/browser path has not yet run.

At `2026-10-28T07:12:59Z`, memory PSI avg10 was **47.23% some / 42.98% full**,
I/O PSI avg10 **0.75% some / 0.74% full**, and about **10 GiB** was available;
the check at that time inspected the relative `data/arena` under the Frontier
worktree and did not establish the protected shared-lock state. No further
resource-bearing work was run after that sample. No protected API, source, or
production store was accessed.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Laboratory read-only view of saved Frontier studies | PARTIALLY VERIFIED AT THIS CHECKPOINT | Initial component tests used mocked API results. The later persisted API/browser verification is recorded below. |
| Legacy Laboratory campaign execution of Frontier snapshots | DEFERRED | The single-market `MarketEvent` schema is not a lossless representation of Frontier's multi-market payoff snapshots. No lossy conversion was added. |
| Arena discovery job completion and host resource sustainability | PARTIALLY VERIFIED | This UI reuses existing routes; it does not verify the separate worker supervisor or current resource gate. |
| Populated-store browser integration for this Laboratory tab | IMPLEMENTED, VALIDATION PENDING AT THIS CHECKPOINT | `a875ee2` seeds a verified fixture artifact into the isolated Arena root; the later API/UI test result is recorded below. |

**Next action at this checkpoint:** remeasure host admission and verify the
new markup and persisted API/UI path. The subsequent check below resolved these
items without changing the overall Frontier status.

Checkpoint commits for this integration are `d396589` (Laboratory UI),
`8227f34` (architecture and initial status documentation), `afcc726`
(fixture-routed browser case), `87ef08e` (pending-verification handoff), and
`91e61d7` (make reproducibility disclosure visible in test assertions), and
`a875ee2` (persisted fixture-backed Arena API/browser flow). The
working tree is clean at this checkpoint. No production branch was changed.
Documentation follow-ups are `a1e5687` (commit identities) and `8c5ffbc`
(correct shared-lock path and external holder); the latter is followed by this
current admission note.

## Correct shared Arena admission check — 2026-10-28 07:17 UTC

The correct protected lock path,
`/home/charlie/midas/data/arena/.global-admission.lock`, was held at
`2026-10-28T07:17:18Z` by PID **124298**, running the Veritas gap-detail batch
under `midas-veritas-gap-detail-v2.service`. The worker was left untouched.
Memory PSI avg10 was **36.43% some / 28.38% full** and I/O PSI avg10
**0.02% some / 0.02% full**. No test, build, or browser process was started
after this sample. The prior relative-path check was not evidence that the
shared lock was free. Recheck both PSI and this exact lock path before
resource-bearing verification.

## Seeded Arena browser verification pending — 2026-10-28 07:22 UTC

Commit `a875ee2` extends the explicit `MIDAS_SEED_FRONTIER_E2E=1` setup to
create one fixture-only Polymarket discovery snapshot, completed artifact, and
Arena manifest in the same disposable browser root as the existing history
fixtures. Its new Playwright case checks the actual local Arena catalog and
hash-verifying result API, then opens the saved result in Laboratory. The API
and browser calls are read-only; the seeder writes only after validating a
fresh `/tmp/midas-browser-*` root. No source data or Arena worker is involved.

This test and the final Laboratory markup refinement remain unverified. At
`2026-10-28T07:21:58Z`, memory PSI avg10 was **39.28% some / 20.15% full**,
I/O PSI was **0.00%**, and PID **124298** still held
`/home/charlie/midas/data/arena/.global-admission.lock` inside
`midas-veritas-gap-detail-v2.service`. The worker and its stores were left
untouched. No verification process was started. Once both admission conditions
clear, run the explicit seeded browser test and focused UI checks, then record
the result without promoting fixture evidence to live-source validation.

## Laboratory/Arena saved-study verification — 2026-10-28 07:30 UTC

The protected Veritas batch exited. At the pre-run samples, memory and I/O PSI
avg10 were below 1%, available memory was about 10 GiB, and the protected shared
Arena lock had no holder. After the full browser suite, at `2026-10-28T07:28:12Z`,
memory PSI avg10 was **0.00% some / 0.00% full**, I/O PSI avg10 **0.01% some /
0.01% full**, about **10 GiB** was available, and the shared lock remained
unheld.

The E2E fixture initially exposed two seed-contract defects before success:
`make_snapshot` requires explicit `verified_relationships=()`, and the completed
Arena manifest must include `exit_status: 0`. Both were corrected. The API then
returned HTTP 409 for the incomplete manifest; the final run exercised the
actual completed-result verifier. All attempts used a fresh `/tmp` browser root.
No source, protected database, or production service was accessed.

Verification of the current committed UI and fixture path:

- `corepack pnpm exec vitest run src/Laboratory.test.tsx`: **4 passed**.
- `corepack pnpm test`: **43 passed** across seven frontend files.
- `corepack pnpm typecheck`: passed.
- `corepack pnpm lint`: passed.
- `corepack pnpm format:check`: passed after formatting the new E2E case.
- Ruff check and `ruff format --check` for `apps/web/e2e/seed_frontier_store.py`: passed.
- `corepack pnpm build`: passed with 2,229 modules. Existing main and Chart
  bundle advisories remain at **511.30 kB** and **544.41 kB**.
- `MIDAS_SEED_FRONTIER_E2E=1 corepack pnpm exec playwright test e2e/frontier.seeded.spec.ts`:
  **2 passed**. One test reads the saved-history pages; the other reads the
  content-addressed Arena job through the real local catalog/result routes and
  inspects it through Laboratory. The job is a synthetic, Polymarket-only
  fixture; the seeder starts no Arena worker.
- The fixture-routed Laboratory case passed **1/1**, confirming the UI does not
  issue source probes or Arena mutation requests.
- Full default `corepack pnpm exec playwright test`: **16 passed, 2 skipped**;
  both skips are the explicitly opt-in seeded cases, which passed separately.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Laboratory inspection of saved Frontier studies | COMPLETE AND VERIFIED | Component coverage, full frontend suite, typecheck, and browser flows pass. Populated API/browser evidence is fixture-backed. |
| Persisted Arena discovery API to Laboratory UI | COMPLETE AND VERIFIED | Temporary content-addressed snapshot, result, and manifest are hash-verified by the real local API, then displayed by the browser. No supervisor job ran. |
| Live-source or genuine cross-venue match through Laboratory | BLOCKED | This seed is a synthetic Polymarket-only fixture; current source-use holds and live semantic acceptance remain. |
| Arena supervisor completion/resource sustainability | PARTIALLY VERIFIED | The read-only UI is verified; this does not establish the worker supervisor or sustained host capacity. |
| Project Frontier overall | PARTIALLY VERIFIED | Genuine live cross-venue matching, held-source access, broader scientific/resource gates, and production deployment remain incomplete. |

Commits `a875ee2` (persisted Arena fixture E2E) and `aa8483b` (manifest
contract fixes and formatted assertions) contain this test path. The working
tree was clean after `aa8483b`; changes remain local to the isolated Frontier
branch, with no merge, push, deployment, source probe, or protected-store write.

## Mission Control lazy research workspaces — 2026-10-28 07:35 UTC

**Stage:** F (native dashboard), performance and workspace-loading refinement.
**Code commit:** `87a6a3c` on `codex/frontier-20261026`.

`apps/web/src/App.tsx` now lazy-loads the Laboratory, Arena, and Reality page
modules when a user opens each workspace. Each has a visible Suspense loading
state. This brings those modules in line with the existing Frontier, Veritas,
Readiness, and Chart split. No workspace was removed or redesigned.

The production build passed and emits separate Laboratory (**33.13 kB**),
Reality (**44.05 kB**), and Arena (**66.43 kB**) chunks. The JavaScript entry
chunk is **367.85 kB**, compared with the previously recorded **511.30 kB**
(about 28% lower). The Chart/ECharts chunk remains **544.41 kB** and continues
to trigger Vite's size advisory. Since Mission Control uses a chart in its
initial view, the entry-chunk reduction does not equal a total initial-transfer
reduction of the same size.

Verification on `87a6a3c`:

- `corepack pnpm build`: passed; TypeScript project build passed; 2,229 modules
  transformed.
- `corepack pnpm test`: **43 passed** across seven files.
- `corepack pnpm exec playwright test`: **16 passed, 2 skipped**. The skips are
  the explicitly opt-in seeded Frontier store scenarios. After this code
  change, `MIDAS_SEED_FRONTIER_E2E=1 corepack pnpm exec playwright test
  e2e/frontier.seeded.spec.ts` separately passed **2/2**, including a populated
  Arena artifact opened in lazy-loaded Laboratory. E2E navigation into
  Frontier, Laboratory, Arena, Reality, and other workspaces remained green.
- `corepack pnpm lint` and `corepack pnpm format:check`: passed.
- `git diff --check`: passed before commit.

The final host sample at `2026-10-28T07:35:37Z` measured memory PSI avg10
**0.00% some / 0.00% full**, I/O PSI avg10 **0.44% some / 0.28% full**, about
**10 GiB** available, and no holder on
`/home/charlie/midas/data/arena/.global-admission.lock`. Tests used isolated
local web/API services. No venue request, protected service, production store,
deployment, or order was involved.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Lazy loading for standalone research workspaces | COMPLETE AND VERIFIED | Build output confirms separate page chunks; full unit/browser suites pass. |
| Mission Control entry bundle reduction | COMPLETE AND VERIFIED | Entry chunk is 367.85 kB vs. prior 511.30 kB; initial chart loading still includes the separate large Chart chunk. |
| Chart chunk size | PARTIALLY VERIFIED | Build passes; 544.41 kB advisory remains for future measured optimization. |
| Project Frontier overall | PARTIALLY VERIFIED | Live cross-venue scientific validation, source permissions, broad production resource/recovery checks, and deployment remain incomplete. |

**Next safe action:** continue the source-independent scientific acceptance
matrix, including economic and replay verifier review; retain the existing
source-use holds and production isolation.

## Candidate observation timestamp validation — 2026-10-28 07:37 UTC

**Stage:** D (independent economics), source-independent timing integrity.
**Code commit:** `92ab4e8` on `codex/frontier-20261026`.

Review found `OpportunityCandidate.observed_at_utc` lacked the aware-time
validation used by Frontier's other evidence timestamps. A naive value can
reach timing verification, where Python's `datetime.timestamp()` interprets it
in the host local timezone. Candidate timestamps now reject naive datetimes
and normalize aware offsets to UTC before storage or audit.

Regression coverage verifies both rejection and offset normalization. The
complete `tests/frontier/test_relationships_economics_replay.py` module passed
**50/50**. Strict mypy passed for `packages/midas/frontier/economics.py`; Ruff
check and Ruff format check pass for both changed Python files. No production,
service, source, or protected data store was accessed.

At `2026-10-28T07:37:17Z`, memory PSI avg10 was **0.00% some/full**, I/O PSI
avg10 was **0.01% some / 0.00% full**, about **10 GiB** was available, and the
shared Arena lock was free. This bounded module test does not re-establish the
full Frontier suite after the change.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Candidate observation timestamp contract | COMPLETE AND VERIFIED | Naive candidate time is rejected; an aware +02:00 timestamp normalizes to UTC; 50 module tests pass. |
| Full Frontier scientific regression after timestamp change | PARTIALLY VERIFIED | The affected economics/replay module passes; remaining modules were not rerun at this checkpoint. |
| Project Frontier overall | PARTIALLY VERIFIED | Live cross-venue match, held-source access, broad resource/recovery, and deployment gates remain open. |

**Next safe action:** continue source-independent audit of timestamp and
provenance contracts across replay inputs, then update this ledger with targeted
verification. Preserve source-use holds and production isolation.

## Fee and raw observation timestamps — 2026-10-28 07:39 UTC

**Stage:** D/E (economic input validation and evidence provenance).
**Code commit:** `a7df7e9` on `codex/frontier-20261026`.

The follow-up review found that `FeeSchedule.effective_at_utc` and
`expires_at_utc` could be naive, even though candidate economics compares them
with aware replay times. `RawObservation.request_started_at_utc` and
`received_at_utc` also lacked timezone validation. These fields now reject
naive values and normalize aware offsets to UTC, matching the existing fee
evidence and normalized provenance contracts. Tests cover both timestamps on
raw records and all three fee-schedule timestamps.

Verification: the economics/replay and storage modules passed **73/73**.
Strict mypy passed for `packages/midas/frontier/models.py` and
`packages/midas/frontier/economics.py`. Ruff check and format check passed for
the changed source modules and tests.

The post-run sample at `2026-10-28T07:39:41Z` measured memory PSI avg10
**0.00% some/full** and I/O PSI avg10 **2.52% some / 1.96% full**; about
**10 GiB** was available and no process held the shared Arena lock. The rest of
the Frontier suite was deferred because I/O pressure exceeded the recorded 1%
admission threshold. No worker or protected store was touched.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Fee schedule time validation | COMPLETE AND VERIFIED | Evidence, effective, and expiry times require timezone-aware input and normalize to UTC. |
| Raw observation request/receipt time validation | COMPLETE AND VERIFIED | Naive times are rejected; aware offsets normalize to UTC; storage tests pass. |
| Broader Frontier regression after provenance changes | PARTIALLY VERIFIED | 73 affected module tests pass; remaining modules wait for lower I/O pressure. |
| Project Frontier overall | PARTIALLY VERIFIED | Genuine second-venue evidence, broad science/resource gates, and deployment remain outstanding. |

**Next safe action:** after I/O pressure falls, run the remaining adapter/API
and Frontier regression slices affected by the shared model change. Continue
source-independent code review while resource admission is closed.

## Arena snapshot-builder timestamp guard — 2026-10-28 07:42 UTC

**Stage:** E (deterministic replay and Arena artifacts).
**Code commit:** `6d5e82b` on `codex/frontier-20261026`.

Review found that the paired replay, discovery-scope, and event-time Arena
`make_snapshot` functions converted their datetime inputs with
`astimezone(UTC)` before checking that the values were aware. Python interprets
naive datetimes in the host local timezone, so those public builders could
silently shift `as_of_utc` or replay cutoffs before pinning the content hash.
The builders now reject naive timestamps first; aware offsets continue to be
normalized to UTC for snapshot identity.

The three affected modules passed **25/25** tests, including one naive-time
rejection case per builder. Strict mypy passed for the three Arena modules;
Ruff check and format check passed for the changed modules and tests. The
existing Starlette/httpx `TestClient` deprecation warning remains.

At `2026-10-28T07:42:38Z`, memory PSI avg10 was **0.00% some/full**, I/O PSI
avg10 was **1.64% some / 1.08% full**, about **10 GiB** was available, and the
shared Arena lock was free. Further broad regression remains deferred until
the I/O gate falls below 1%. No worker, source, protected store, or production
service was accessed.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Arena replay snapshot time guard | COMPLETE AND VERIFIED | Naive analysis time is rejected before UTC normalization; test passes. |
| Arena discovery snapshot time guard | COMPLETE AND VERIFIED | Naive analysis time is rejected before content addressing; test passes. |
| Arena event-time snapshot guard | COMPLETE AND VERIFIED | Naive replay cutoffs are rejected before content addressing; test passes. |
| Full Frontier regression after time-contract changes | PARTIALLY VERIFIED | Affected economics/storage and Arena modules pass; remaining adapter/API/full suite wait for lower I/O pressure. |
| Project Frontier overall | PARTIALLY VERIFIED | Genuine cross-venue evidence, broad resource/recovery checks, and deployment remain open. |

**Next safe action:** continue source-independent review without launching
resource-bearing jobs while the shared-host I/O gate is high. Rerun the
remaining affected regressions only after a fresh admitted sample.

## Lazy workspace failure containment — 2026-10-28 07:47 UTC

**Stage:** F/G (native interface reliability and verification).
**Code commit:** `8f5bf83` on `codex/frontier-20261026`.

The chunk-splitting change left lazy workspaces with loading feedback but no
local error UI. A rejected import could therefore escape the workspace view.
Mission Control now wraps Chart, Readiness, Laboratory, Arena, Reality, Veritas,
and Frontier in error boundaries outside their Suspense loaders. A failure
shows an accessible alert scoped to the affected workspace, with an instruction
to refresh. The boundary intentionally does not claim to retry a rejected
module in place.

Verification: the complete frontend unit suite passed **44/44**; TypeScript,
ESLint, and Prettier passed; and `pnpm build` succeeded. The default browser
suite passed **16** with **2** expected seeded-only skips. The separately
enabled seeded Frontier/Arena suite passed **2/2**, reading the persisted
fixture artifact into lazy-loaded Laboratory. It used only temporary `/tmp`
stores. The production build emitted a **368.13 kB** entry JS chunk and the
existing **544.41 kB** Chart/ECharts advisory; Mission Control still loads the
chart on its initial view. At `2026-10-28T07:47:03Z`, memory PSI avg10 was
**0.00% some/full**, I/O PSI avg10 was **0.07% some / 0.04% full**, and about
**10 GiB** was available. No source, protected store, worker, or production
service was accessed.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Lazy workspace loading and failure UI | COMPLETE AND VERIFIED | Seven lazy workspace boundaries; focused error-boundary test and full frontend unit/browser suites pass. |
| Frontend production bundle | PARTIALLY VERIFIED | Build succeeds; initial chart still loads a 544.41 kB ECharts chunk and Vite keeps the size advisory. |
| Project Frontier overall | PARTIALLY VERIFIED | Live cross-venue economic equivalence, held-source permissions, broad production readiness, and deployment remain open. |

**Next safe action:** continue with source-independent scientific correctness
and API/persistence review; use fresh host admission before broader replay or
regression runs. Keep all held-source, production, and long-running research
boundaries in place.

## Independent audit timezone guard — 2026-10-28 07:58 UTC

**Stage:** D/G (independent economic verification and regression).
**Code commit:** `e1946bc` on `codex/frontier-20261026`.

The audit previously converted typed `datetime` values to epoch milliseconds
with `datetime.timestamp()`. Pydantic field validators reject naive input in
normal construction, but reconstructed models can use `model_copy(update=...)`
without revalidation. That left a path for candidate, book, or nested evidence
times to be interpreted using the host's local timezone. Audit v13 now walks
the candidate, execution scenario, pinned markets and books, relationship
evidence, and joint-state map before performing temporal comparisons. Any naive
timestamp in a candidate with a constructed position makes the audit
`INCOMPLETE`; the epoch helper also rejects malformed non-datetime values. The
verifier version is included in the audit input hash.

The affected economics/replay and storage modules passed **74/74** after the
recursive preflight was implemented. A final runtime type guard was added to
the epoch helper afterward; Ruff and Ruff format pass, and strict mypy passes
for `independent_audit.py` and `models.py` on the final code. After commit, the
full API module passed **56/56**, exercising paired, multi-outcome,
payoff-basket, joint-state, readiness, and persisted replay paths. One existing
Starlette/httpx `TestClient` deprecation warning remains. The smaller explicit
API subset also passed **4/4** before the full API module, so it is superseded
by the latter result.

At `2026-10-28T07:57:51Z`, memory PSI avg10 was **0.00% some/full**, I/O PSI
avg10 was **7.28% some / 5.30% full**, about **10 GiB** was available, and no
shared Arena lock holder was present. Further test runs remain deferred until
I/O avg10 is below the 1% admission threshold. No live source, worker, protected
store, or production service was accessed.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Naive timestamp handling in independent audit | COMPLETE AND VERIFIED | Candidate and book model-copy regressions return `INCOMPLETE`; affected module tests and final API module pass. |
| Full post-commit economics/storage regression | PARTIALLY VERIFIED | 74 cases passed after recursive preflight but before final `isinstance` guard; rerun waits for low I/O pressure. |
| Project Frontier overall | PARTIALLY VERIFIED | Live equivalent cross-venue evidence, held-source approvals, full resource/recovery, and deployment remain open. |

**Next safe action:** when a fresh host sample admits work, rerun the economics
and storage modules against the exact final commit; continue source-independent
review without source requests or production changes while admission is closed.

## Descriptive history replay revalidation — 2026-10-28 08:02 UTC

**Stage:** E (bounded historical replay and deterministic evidence).
**Code commit:** `dd4882d` on `codex/frontier-20261026`.

The historical price-point model rejects naive timestamps during ordinary
validation, but `model_copy(update=...)` could bypass that validation for a
nested point. `deterministic_price_history_replay` now reconstructs each bounded
`PriceHistoryReplayInput` from its serialized model payload before sorting,
hashing, comparing point times, or calling `.timestamp()`. This revalidates the
outer capture, series, provenance, and every point. The replay identity version
advances from v1 to v2; store schema and historical rows are unchanged.

The price-history replay module passed **5/5**, covering deterministic ordering,
capture and size bounds, the new nested naive-time regression, append-only
storage, and schema-6 migration. The fixture-backed price-history API probe and
replay test passed **1/1** after the change. Ruff, Ruff format, strict mypy for
`historical_replay.py`, and `git diff --check` passed. The API test emitted the
existing Starlette/httpx `TestClient` deprecation warning; its source transport
was mocked.

At `2026-10-28T08:01:50Z`, memory PSI avg10 was **0.00% some/full**, I/O PSI
avg10 was **1.09% some / 0.68% full**, and about **10 GiB** was available. The
shared-host I/O some average was slightly above the 1% test gate, so additional
tests remain deferred pending a fresh admitted sample. No public source,
protected store, worker, or production service was accessed.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Historical point-time validation before replay | COMPLETE AND VERIFIED | Nested naive points reject through model revalidation; 5 replay tests and the API route test pass. |
| Historical replay versioning | COMPLETE AND VERIFIED | New inputs carry replay v2; immutable store schema and old records were not changed. |
| Frontier overall | PARTIALLY VERIFIED | This descriptive replay guard does not close live cross-venue, source-policy, production-recovery, or deployment gates. |

**Next safe action:** after a fresh low-I/O sample, rerun the exact-commit
economics/storage slices left pending above; keep source requests and protected
production changes held.

## Exact-tree timestamp regression checkpoint — 2026-10-28 08:03 UTC

**Code commits:** `e1946bc` (independent audit v13) and `dd4882d`
(price-history replay v2).

The previously pending exact-commit regression has now run. The economics /
replay, storage, and historical-replay modules passed **79/79** together,
including the model-copy naive timestamp cases. This includes the full 74-case
economics/storage slice after the final runtime `isinstance` check. The full
Frontier API module passed **56/56** after audit v13. After price-history replay
v2, its route-level mocked probe/replay case passed **1/1**. Ruff, Ruff format,
strict mypy for both changed source areas, and `git diff --check` pass. The
existing Starlette/httpx TestClient deprecation warning remains.

At `2026-10-28T08:02:44Z`, memory PSI avg10 was **0.00% some/full**, I/O PSI
avg10 was **0.15% some / 0.00% full**, about **10 GiB** was available, and the
shared Arena lock was free. Earlier post-run samples briefly exceeded the I/O
gate; no further broad suite was started. No live source, protected store,
worker, or production service was accessed.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Independent audit naive-time rejection | COMPLETE AND VERIFIED | The final economics/replay and storage modules pass; full API module passes. |
| Historical replay nested-model validation | COMPLETE AND VERIFIED | Five replay module cases and the route-level API case pass; new output version is v2. |
| Exact-tree timestamp regression slice | COMPLETE AND VERIFIED | 79 relevant tests pass together on the final code. |
| Frontier project acceptance | PARTIALLY VERIFIED | This does not close full single-process regression, live cross-venue science, held-source access, production recovery, or deployment gates. |

**Next safe action:** return to source-independent acceptance gaps. Only start
another test or replay workload after a fresh host admission sample; preserve
all source-use and production holds.

## Adapter timestamp parser regression — 2026-10-28 08:04 UTC

**Stage:** B/G (adapter normalization contract and tests).
**Test commit:** `2eff73e` on `codex/frontier-20261026`.

The common `parse_time` helper already returned `None` for naive ISO strings
and normalized explicitly offset values to UTC, but the adapter contract suite
did not pin that behavior. A focused regression now verifies naive input is
left unavailable, `+02:00` maps to the equivalent UTC instant, and `Z` remains
UTC. This preserves missing source-time evidence instead of inventing a local
timezone.

The complete fixture-driven `tests/frontier/test_adapters.py` module passed
**68/68** in 2.70 seconds. Ruff, Ruff format, and `git diff --check` passed.
The module's venue calls use injected/mock transport; no public
network source was accessed. At `2026-10-28T08:04:42Z`, memory PSI avg10 was
**0.00% some/full**, I/O PSI avg10 was **0.02% some / 0.00% full**, and about
**10 GiB** was available. No production service, worker, or protected store
was touched.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Shared ISO timestamp normalization contract | COMPLETE AND VERIFIED | Naive ISO input stays unavailable; explicit offsets normalize to UTC; all 68 adapter module tests pass. |
| Live adapter timestamp validation | IMPLEMENTED, LIVE VALIDATION PENDING | This is fixture-backed parser evidence; no live source probe was performed. |
| Project Frontier overall | PARTIALLY VERIFIED | Live multi-venue science, source policy, broad resource/recovery, and production gates remain open. |

## Full Frontier suite resource-gated attempt — 2026-10-28 08:07 UTC

**Stage:** G (single-process regression and resource admission).

The current tree collected **378** tests from `tests/frontier`. A single
fixture-backed run was started after a fresh preflight sample showed memory
PSI avg10 **0.00%**, I/O PSI avg10 **0.19%**, and about **10 GiB** available.
After **193 tests passed**, live I/O PSI rose to **12.91% some / 10.15% full**.
The process was sent SIGINT to stop additional shared-host I/O. Pytest exited
2 with `KeyboardInterrupt`; no test failure was reported among the completed
tests. The complete suite therefore remains **unverified in one process**.

`/usr/bin/time -v` reported 68.97 seconds wall time, 347,088 KiB maximum RSS,
and zero process swaps. A post-stop sample showed memory PSI avg10 **0.00%**,
I/O PSI avg10 **4.49% some / 3.33% full**, and about **10 GiB** available.
The I/O pressure persisted after the Frontier test process stopped. No public
network source, production service, worker, protected store, or Arena job was
started by this run. The test suite uses local fixtures and temporary test
state.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| First 193 collected Frontier tests | PARTIALLY VERIFIED | All 193 completed tests passed; the other 185 did not run. |
| Full single-process Frontier suite | PARTIALLY VERIFIED | Stopped at the resource gate after I/O PSI exceeded the 1% threshold. |
| Frontier project overall | PARTIALLY VERIFIED | Continue source-independent work; retry only after a fresh admitted host sample. |

**Next safe action:** keep reviewing and documenting without launching more
test or replay workloads while shared I/O remains above the admission gate.

## Nested price-history point revalidation — 2026-10-28 08:09 UTC

**Stage:** E/G (canonical model validation and timestamp integrity).
**Code commits:** `2e73476` (validator and regression) and `aa88b03` (test
return annotation) on `codex/frontier-20261026`.

Source review found that Pydantic does not revalidate an already-instantiated
nested model by default. A `HistoricalPricePoint.model_copy(update=...)` with a
naive timestamp or an out-of-range price could therefore be accepted inside a
new `PriceHistorySeries`; its range validator then called `.timestamp()` on the
naive value. `PriceHistorySeries` now converts nested point instances to Python
payloads before nested model parsing, so timestamp and exact price constraints
run again before series checks.

The historical-replay module passes **6/6**, including regressions for both a
naive copied timestamp and a copied out-of-range price. The adapter module
passes **68/68**, and the targeted history-probe/replay API case passes **1/1**.
Ruff check, Ruff format, and `git diff --check` pass. Configured strict mypy
passes for `packages/midas/frontier/models.py`. The six-case history module
completed in 1.81 seconds with **57,708 KiB** maximum RSS and zero swaps.
At `2026-10-28T08:11:12Z`, memory PSI avg10 was **0.00%**, I/O PSI avg10 was
**0.90% some / 0.74% full**, and about **10 GiB** was available. All tests used
temporary or mocked state and accessed no live source, worker, protected store,
or production service. The targeted API case emitted the existing
Starlette/httpx `TestClient` deprecation warning.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| `PriceHistorySeries` nested-point validation | COMPLETE AND VERIFIED | Naive timestamps and invalid prices from copied model instances are rejected; historical replay, adapter, and targeted API tests pass. |
| Full Frontier single-process suite | PARTIALLY VERIFIED | 193 of 378 tests passed before the documented I/O-pressure stop; 185 remain unrun. |
| Frontier project overall | PARTIALLY VERIFIED | Live/source-policy, broad regression, endurance, and deployment gates remain open. |

**Next safe action:** continue source-independent review; run further test
slices only after a fresh low-I/O sample.

## Held-capture test guard — 2026-10-28 08:13 UTC

An offline regression was attempted to replay an existing public-source capture
through Polymarket and Kalshi adapters and feed the normalized markets to the
relationship proposer. `tests/frontier/conftest.py` denied the test's read of
`data/frontier/live-probes` with `PermissionError: Frontier tests may not access
held source captures`. The single test exited 1 before reading the artifact or
making any request. Its temporary test file was removed; the held capture was
not copied or repackaged to bypass the guard.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Recorded live-capture relationship regression | BLOCKED | The test harness protects held source captures from test access. |
| Synthetic cross-venue hypothesis coverage | COMPLETE AND VERIFIED | Existing fixture test verifies event-context text proposals remain HYPOTHESIS and unverified payoffs stay unverified. |
| Genuine cross-venue economic equivalence | BLOCKED | No new source-use permission or held-capture exception was available in this workstream. |
| Frontier project overall | PARTIALLY VERIFIED | Continue independent work; do not route around the capture guard. |

## Full Frontier suite pass on tmpfs — 2026-10-28 08:18 UTC

**Test commit:** `f5dfb26` on `codex/frontier-20261026`.

The three migration tests that failed in the first tmpfs run asserted literal
schema `6`, while `storage.SCHEMA_VERSION` and the migration code correctly use
current schema `7`. Their assertions now compare against `SCHEMA_VERSION`; no
production storage behavior changed. The exact final Frontier tree then passed
all **379/379** tests in **29.51 seconds** (31.00 seconds process wall time),
with one existing Starlette/httpx `TestClient` deprecation warning.

The command used `--basetemp=/dev/shm/midas-frontier-pytest-20261028-0817`.
`/usr/bin/time -v` reported **378,216 KiB** maximum RSS, **zero swaps**, zero
filesystem input, and 544 filesystem-output blocks. At `2026-10-28T08:17:18Z`
before the run, memory PSI avg10 was **0.00%**, I/O PSI avg10 was **0.02%**,
and about **10 GiB** was available. At `08:18:01Z` after the run, memory PSI
avg10 remained **0.00%**, I/O PSI avg10 was **0.02% some / 0.00% full**, and
about **10 GiB** remained available. No live source, worker, protected store,
production service, or Arena job was accessed or started.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Full Frontier Python suite | COMPLETE AND VERIFIED | 379 tests pass on the exact current tree in one process. |
| Full repository and browser acceptance | PARTIALLY VERIFIED | This run covers `tests/frontier`; broader legacy, frontend, and browser checks remain separately evidenced. |
| Genuine live cross-venue equivalence | BLOCKED | The test harness denies held capture access and live source permission remains unresolved. |
| Frontier project overall | PARTIALLY VERIFIED | Deployment, held-source validation, and production resource/recovery gates remain open. |

**Next safe action:** continue source-independent acceptance review and use a
fresh host sample before any additional broad verification workload. The
resource-gated tmpfs command is documented in `docs/frontier/FRONTIER_OPERATIONS.md`
(commit `5e20c7f`).

## Arena snapshot write and load boundaries — 2026-10-28 13:35 UTC

**Implementation commit:** `4788443` (`fix(arena): validate Frontier snapshot boundaries`).

Review of Frontier's Arena replay, discovery, and timeline snapshot stores
found that copied Pydantic instances could bypass nested validation and that
copied job-spec identifiers reached path construction without reparsing. All
three writers now serialize and revalidate the snapshot before size checks or
filesystem changes, then use the validated identifier. All three loaders
revalidate job specs before constructing paths. Timeline schema-v1
`exclude_unset` behavior is preserved so old field-presence semantics remain
round-trippable.

Six focused tests passed: four corruption and timeline-preservation cases
(1.72 seconds pytest, 2.41 seconds wall, 193,700 KiB peak RSS) and two
replay/discovery happy paths (1.60 seconds pytest, 2.27 seconds wall,
190,404 KiB peak RSS). Both runs used isolated `/dev/shm` roots, recorded zero
swaps, filesystem input, and socket messages, and had one existing
Starlette/httpx `TestClient` deprecation warning each. Strict mypy reported no
issues in the three Arena modules; Ruff check/format and `git diff --check`
passed. No source API, collector, held capture, protected store, production
service, or persistent Arena job was accessed.

At `2026-10-28T13:35:05Z`, CPU PSI avg10 was **48.03%**, I/O PSI avg10 was
**0.21% some / 0.00% full**, memory PSI avg10 was **0.00%**, and approximately
**10 GiB** was available. With sustained CPU pressure, the full Arena modules
and broader Frontier suite were not rerun.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Arena Frontier snapshot path and nested-data validation | COMPLETE AND VERIFIED | Focused corruption and round-trip tests pass for replay, discovery, and timeline stores/loaders; strict mypy and Ruff checks pass. |
| Full Arena and Frontier regression after this change | PARTIALLY VERIFIED | Six focused tests pass; full suites were deferred under sustained CPU pressure. |
| Frontier project acceptance | PARTIALLY VERIFIED | Source-use holds, held-capture restrictions, cross-venue equivalence evidence, production recovery, and deployment remain open. |

**Next safe action:** continue bounded source-independent code review; sample
host pressure again before any broader test run. Keep
`data/frontier-public-probes/` untouched.

## Arena admission regression and current completion matrix — 2026-10-28 14:05 UTC

`tests/arena/test_admission.py` passed **11/11** in 1.38 seconds of pytest
time (1.99 seconds process wall), with **180,884 KiB** peak RSS, zero swaps,
zero filesystem input, 376 filesystem-output blocks, and no socket traffic.
The test root was `/dev/shm/midas-frontier-arena-admission-20261028T1404Z`.
The tests use isolated temporary roots and monkeypatched admission conditions;
they do not create a production Arena job or bypass the shared admission gate.

At `14:04:10Z` before the run, memory and I/O PSI avg10 were at or below
**0.01%**, with about **10 GiB** available. At `14:04:17Z` after the run,
memory and I/O PSI avg10 were **0.00%**. CPU PSI avg10 was **42.02%** after
the run. The prior generic `tests/arena/test_jobs.py` run had raised I/O PSI to
4.58% some / 3.59% full; this admission test was run only after fresh samples
showed the I/O avg10 below the documented 1% gate. No follow-on broad suite
was started. No live source, held capture, protected store, production Arena
root, service, collector, or persistent job was accessed.

The report matrix dated 10:35 UTC below is historical. The updated matrix in
`FRONTIER_ENGINEERING_REPORT.md` at this checkpoint is the current acceptance
summary.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Adapter framework and offline contracts | COMPLETE AND VERIFIED | Shared capability declarations, source configuration, parsers, and fixture contract tests pass. Secondary-venue live use remains separately gated. |
| Polymarket public adapter | PARTIALLY VERIFIED | A bounded genuine public observation was previously validated; it does not prove broad feed quality, simultaneous availability, or executable economics. |
| Kalshi, Kraken, and Coinbase adapters | IMPLEMENTED, LIVE VALIDATION PENDING | Read-only adapter behavior is fixture-tested; current source-use permission gates keep live probes and held evidence quarantined. |
| Canonical instruments and payoff semantics | PARTIALLY VERIFIED | Versioned models and bounded payoff checks pass; live cross-venue settlement equivalence is not established. |
| Relationship graph and economic equivalence | PARTIALLY VERIFIED | Deterministic hypothesis, evidence review, and verification paths are fixture-tested; no permitted genuine cross-venue equivalence is verified. |
| Opportunity discovery and independent audit | PARTIALLY VERIFIED | Supported fixture cases independently recompute outcomes and costs; no live cross-venue candidate or positive eligibility is demonstrated. |
| Cross-venue economics and capital constraints | PARTIALLY VERIFIED | Fees, FX assumptions, timing, partial fills, and venue-specific virtual capital are modeled in fixtures; account-specific costs, access, settlement, and execution remain unresolved. |
| Provenance, storage, and replay | PARTIALLY VERIFIED | Bounded immutable observations and deterministic replay have regression coverage; direct proposal/replay inputs now cap at 200 markets, 400 books, 1,000 relationships, and 1,000 proposals. Sustained multi-source quality and history are unmeasured. |
| Frontier Laboratory/Arena integration | PARTIALLY VERIFIED | Frontier replay/timeline/discovery modules pass 28/28; generic Arena job-supervision tests pass 16/16 and admission tests pass 11/11. Full legacy Arena regression, endurance, and production-worker readiness remain deferred. |
| Native Frontier workspace | COMPLETE AND VERIFIED | Frontend tests, typecheck, lint/format, production build, and 9 isolated browser cases pass; no browser fixture is represented as live cross-venue evidence. |
| Source-aware analytics and readiness | PARTIALLY VERIFIED | Summaries and gates are implemented and fixture-tested; the captured sample cannot support venue-wide coverage or opportunity-prevalence conclusions. |
| Research-only boundary | COMPLETE AND VERIFIED | No authenticated trading, wallet, funding, or order-submission path was introduced; bounded tests and API checks remain isolated. |
| Full Frontier Python suite | PARTIALLY VERIFIED | The full suite passed 452/452 on the storage/audit checkpoint; subsequent Arena and replay-bound changes have focused coverage, but the full suite has not been rerun on the current code. |
| Broader MIDAS regression | DEFERRED | The complete legacy repository suite was not run; do not infer broad compatibility from targeted checks. |
| Genuine live cross-venue relationship/economics | BLOCKED | Current source-use gates and held-capture protections prevent the required independent second-venue evidence. |
| Resource sustainability and production recovery | PARTIALLY VERIFIED | Bounded process profiles are recorded. No endurance campaign or current-boundary production recovery proof exists. |
| Production deployment | DEFERRED | Frontier remains isolated, unmerged, and undeployed; separate recovery, source-policy, and deployment gates remain open. |
| Project Frontier overall | PARTIALLY VERIFIED | The research foundation and fixture acceptance are substantial; live cross-venue science, broad legacy regression, endurance, production recovery, and deployment remain outstanding. |

**Next safe action:** continue source-independent review and implementation;
obtain a fresh pressure sample before another resource-bearing verification
slice. Keep the held `data/frontier-public-probes/` path untouched.

## Direct replay resource bounds — 2026-10-28 14:10 UTC

**Implementation commit:** `f1d04bf` (`fix(frontier): bound direct replay inputs`).

The replay API already restricted its ordinary window, but the public
`deterministic_replay` and `propose_relationships` functions did not enforce
those limits for direct callers. The relationship proposer now rejects more
than 200 markets before building its indexes. Deterministic replay rejects
more than 200 markets, 400 books, or 1,000 verified relationships before
structural validation or sorting, and restricts its proposal limit to
1..1,000. These are the existing API maxima; results inside those bounds are
unchanged. Paired replay retains its stricter existing 100-market/200-book/
500-edge limit.

Five new adversarial tests cover the oversized boundaries. The complete
relationship/economics/replay module passed **88/88** in 1.04 seconds wall
time at 56,248 KiB peak RSS. Replay-comparison, timeline, and discovery-
comparison modules passed **11/11** in 0.84 seconds at 56,064 KiB. The API
replay selection passed **12/12** (44 deselected) in 4.80 seconds at 231,308
KiB; one existing Starlette/httpx TestClient deprecation warning remains. All
three runs used isolated `/dev/shm` roots, zero swaps, zero filesystem input,
and no socket traffic. Strict mypy passed on both changed implementation
modules; Ruff check, Ruff format check, and `git diff --check` passed.

The full `tests/frontier` suite was not rerun after this change. The most
recent suite-wide result remains **452/452** on the earlier storage/audit
checkpoint; the current code has **111/111** focused passing tests across the
affected replay and caller modules. At `14:09:48Z`, memory and I/O PSI avg10
were 0.00%; at `14:10:23Z` they were 0.03% some / 0.00% full for memory and
0.03% some / 0.00% full for I/O. CPU PSI avg10 was 46.38% before and 37.77%
after the checks. No live source, held capture, production service, or
protected store was accessed; `data/frontier-public-probes/` remains untouched.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Core relationship and replay input bounds | COMPLETE AND VERIFIED | Oversized direct inputs fail before structural validation, indexing, or sorting; fixture module and all direct caller slices pass. |
| Full Frontier suite on current code | PARTIALLY VERIFIED | 111 focused tests cover the changed code and callers; the complete suite has not been rerun on `f1d04bf`. |
| Frontier project overall | PARTIALLY VERIFIED | Live cross-venue evidence, broad regressions, sustained resource evidence, production recovery, and deployment remain open. |

**Next safe action:** retain the resource gate and continue with a separate
bounded source-independent acceptance item; do not present this targeted
regression as a full-suite rerun.

## Source-scoped canonical instrument IDs — 2026-10-28 14:21 UTC

**Implementation commit:** `4305083` (`feat(frontier): add source-scoped instrument identities`).

`FrontierMarket` schema v5 adds deterministic `MarketInstrument.canonical_id`
values derived from a version tag, venue, native market ID, and native
instrument ID. Schema v1–v4 payloads without the field derive the same value
without changing their declared version; incorrect supplied values are
rejected. Polymarket, Kalshi, Kraken spot, and Coinbase Exchange spot adapter
versions advanced, as did deterministic replay. The UI labels this as a
venue-scoped ID and explicitly says it is not an equivalence claim.

The final identity/adapter/Coinbase selection passed **89/89** in 3.44 seconds
wall time (79,108 KiB peak RSS, zero swaps, filesystem input, or socket
messages). Strict mypy passed for six implementation modules; Ruff check and
format passed for 11 Python files. TypeScript build succeeded and the focused
UI test passed **1/1** with eight tests skipped by name filter. The related
model/replay/storage set passed **140/140**, and API replay passed **12/12**
earlier in this increment, before a final type-guard-only adjustment; the
current guard is covered by the 89-test rerun and mypy.

CPU PSI avg10 remained about **41–43%** around the checks while memory and I/O
PSI avg10 were **0.00%**. The full Frontier and broader legacy suites were not
rerun. No live source, production service, or protected store was accessed.
The held `data/frontier-public-probes/` directory remains untouched. The new
source-scoped IDs do not verify payoff, settlement, or cross-venue equivalence.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Source-scoped canonical instrument ID | COMPLETE AND VERIFIED | Schema migration, stable namespace derivation, mismatch rejection, adapter fixtures, and UI display have focused verification. |
| Cross-venue payoff and settlement equivalence | PARTIALLY VERIFIED | No genuine permitted equivalence evidence is established; source-scoped IDs do not imply equivalence. |
| Full Frontier suite on `4305083` | PARTIALLY VERIFIED | 89 focused identity/adapter tests plus adjacent earlier slices pass; the full suite was not rerun under CPU PSI pressure. |
| Project Frontier overall | PARTIALLY VERIFIED | Live multi-venue evidence, broad regression, sustained-resource evidence, production recovery, and deployment remain open. |

**Next safe action:** continue with independent bounded source work after a
fresh resource admission sample; keep the held capture quarantined and do not
infer cross-venue equivalence from canonical IDs.

## Legacy schema migration coverage — 2026-10-28 14:24 UTC

**Test commit:** `de57883` (`test(frontier): cover legacy instrument schema migration`).

Expanded the migration test from v4-only to all supported legacy market
schema versions v1–v4. Each case verifies deterministic instrument-ID
derivation while retaining its declared version. The focused identity, adapter,
and Coinbase tests pass **92/92** in 3.46 seconds wall time at 78,988 KiB peak
RSS, zero swaps, filesystem input, and socket messages. Ruff check and format
pass for the modified test; the existing Starlette/httpx warning remains.

CPU PSI avg10 was 46.66% before and 43.48% after; memory PSI stayed 0.00% and
post-run I/O PSI was 0.03% some / 0.00% full. No live source or protected
service was accessed. The complete Frontier and broader legacy suites remain
unrun on the current branch; project status stays **PARTIALLY VERIFIED**.

**Next safe action:** take a fresh resource sample before another test slice;
continue with bounded source-independent review while CPU PSI remains elevated.

## Persisted instrument identity — 2026-10-28 14:27 UTC

**Test commit:** `6ecb7c9` (`test(frontier): verify instrument IDs persist`).

Added storage assertions for canonical instrument IDs in both single-market
and market-batch observations after durable append/readback. The focused
storage selection passed **2/2** (28 deselected), in 1.75 seconds wall time
at 58,636 KiB peak RSS, zero swaps, filesystem input, and socket messages.
Ruff check and format passed for the changed test file.

CPU PSI avg10 moved from 42.59% to 39.61%; memory PSI stayed at 0.00%. I/O PSI
rose from 0.18% some / 0.00% full to 0.70% some / 0.54% full, below the 1%
admission boundary. No source or protected service was accessed. The full
Frontier suite remains unrun on current code; status remains **PARTIALLY
VERIFIED**.

**Next safe action:** take a fresh resource sample before further tests; keep
working on bounded source-independent acceptance gaps while live source and
production validation remain gated.

### Storage module regression — 2026-10-28 14:28 UTC

The complete `tests/frontier/test_storage.py` module passes **30/30** in
16.72 seconds wall time at 71,876 KiB peak RSS, zero swaps, filesystem input,
and socket messages. The isolated temporary-file run wrote 100,472 filesystem
blocks. I/O PSI avg10 rose from 0.00% some / 0.00% full before the run to
9.54% some / 7.20% full afterward; memory PSI remained 0.00%.

No live source or protected store was accessed. This is storage-module evidence,
not a complete Frontier regression. Stop resource-bearing checks until a fresh
I/O sample is below 1%; continue static, source-independent review. Frontier
remains **PARTIALLY VERIFIED**.

## Current Frontier Python suite — 2026-10-28 14:31 UTC

**Code revision tested:** `d3e30a0`.

The full `tests/frontier` suite passed **465/465** in 29.51 seconds pytest
time (30.97 seconds process wall time), at 381,916 KiB peak RSS. It ran with
`--basetemp=/dev/shm/midas-frontier-full-20261028T143105Z`, zero swaps,
filesystem input, or socket messages, and 432 filesystem output blocks. One
existing Starlette/httpx warning remains.

At `14:31:05Z`, CPU PSI avg10 was 44.60%, memory PSI 0.00%, and I/O PSI 0.01%
some / 0.00% full. At `14:31:45Z`, CPU PSI was 38.39%, memory PSI 0.00%, and
I/O PSI 0.06% some / 0.00% full. The tmpfs run directory occupies 19 MiB;
its cleanup command was rejected by the shell safeguard (`rm -f` style
commands are not permitted), so it remains intact.
No live source, protected service, or protected store was used. This closes
the Frontier Python suite on current code, not the full MIDAS/browser/Arena
regression or overall project acceptance.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Full Frontier Python suite | COMPLETE AND VERIFIED | 465/465 pass on `d3e30a0`; one existing deprecation warning. |
| Broader MIDAS/browser/Arena regression | PARTIALLY VERIFIED | Separate current-code suites remain outstanding. |
| Project Frontier overall | PARTIALLY VERIFIED | Live cross-venue validation, broad regression, resource sustainability, production recovery, and deployment remain open. |

**Next safe action:** take a fresh resource sample before any additional test
run; continue independent source-policy and UI review in the meantime.

## Frontier workspace verification — 2026-10-28 14:36 UTC

The full web unit suite passes **47/47** across 9 files; post-format
`Frontier.test.tsx` passes **9/9**. TypeScript typecheck, ESLint, and full
Prettier check pass. The production build passes, including `tsc -b`, in 14.07
seconds wall time at 712,284 KiB peak RSS, zero swaps, filesystem input, or
socket messages. Vite completed in 4.90 seconds; the existing Chart chunk
advisory is 544.51 kB against the 500 kB warning threshold.

Frontier-specific Playwright passes **7/7** against an empty temporary store
and **2/2** on the explicitly seeded path. The seeded test reads 21 labeled
fixture captures/replay artifacts and one fixture-only Arena discovery
artifact. Both runs use isolated local services at ports 18000/15173, one
worker, and no public-source requests. Regular/seeded process wall times were
19.46/11.62 seconds; peak RSS was 201,688/182,712 KiB. Both used zero swaps or
socket messages.

At `14:35:57Z`, CPU PSI avg10 was 44.34%, memory PSI 0.00%, and I/O PSI
0.44% some / 0.23% full. At `14:36:23Z`, memory PSI remained 0.00%, and I/O
PSI was 0.05% some / 0.01% full. No public source or production service was
accessed. The non-Frontier browser files, live-source science, endurance,
production recovery, and deployment remain open. Project status remains
**PARTIALLY VERIFIED**.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Web unit/type/lint/format/build | COMPLETE AND VERIFIED | 47 unit tests pass; typecheck, lint, format, and build pass with the known Chart advisory. |
| Frontier browser acceptance | COMPLETE AND VERIFIED | 7 normal plus 2 seeded Playwright cases pass on isolated local state. |
| Broader MIDAS/browser regression | PARTIALLY VERIFIED | Non-Frontier E2E files not rerun in this checkpoint. |
| Project Frontier overall | PARTIALLY VERIFIED | Cross-venue live evidence, broad regression, resource sustainability, production recovery, and deployment remain outstanding. |

**Next safe action:** continue with source-independent acceptance work and take
a fresh resource admission sample before the next broad test batch.

## Broader Mission Control E2E stopped at I/O gate — 2026-10-28 14:38 UTC

The one-worker Playwright run collected 19 tests. Eight passed and two
seeded-only tests were skipped because `MIDAS_SEED_FRONTIER_E2E` was unset;
the remaining nine did not complete. I stopped the run with SIGINT after I/O
PSI crossed the 1% admission threshold. No assertion failure was reported,
and this is not a passing full-suite result.

I/O PSI avg10 was 0.33% some / 0.00% full at 14:37:53Z, reached 1.12% some /
0.64% full at 14:38:19Z, then fell to 0.59% / 0.41% at 14:38:29Z and
0.21% / 0.15% at 14:38:38Z. The interrupted run left only its isolated local
API and Vite servers alive. After verifying exact arguments, I terminated
those test-owned PIDs and verified both were gone. No production service,
protected store, or public source was accessed.

Frontier-specific E2E remains **COMPLETE AND VERIFIED** at 7/7 normal and 2/2
seeded tests. All Mission Control Playwright E2E remains **PARTIALLY
VERIFIED**: eight completed, two skipped, and nine incomplete in this run.
Frontier overall remains **PARTIALLY VERIFIED**.

**Next safe action:** take a fresh I/O and resource sample before another
resource-bearing run. Do not resume the broad E2E batch until the admission
gate clears; continue source-independent static review meanwhile.

## Mission Control browser coverage completed — 2026-10-28 14:42 UTC

The ten non-Frontier browser cases passed **10/10** in a one-worker Playwright
run (23.3 seconds). The first attempt passed 9/10 because I set
`MIDAS_VERITAS_WORKSPACE` to an empty temporary directory; this hid the
checked-in historical artifacts that the Veritas browser spec intentionally
reads. I made no code or test change. The successful rerun left that setting
unset, preserving the configured read-only repository evidence path, and
isolated the mutable API database, Arena, and Frontier roots in a fresh temp
directory.

Together with the earlier isolated Frontier runs (7/7 normal and 2/2 seeded),
all **19 collected Mission Control E2E cases pass across three runs**. Seeded
data is fixture-only. The earlier combined run remains recorded as stopped
after eight passes and two skips when I/O crossed the gate; this subsequent
per-group evidence completes browser-case coverage without changing that
historical result.

I/O PSI avg10 stayed below 1% in periodic samples during the successful run;
the maximum observed sample was 0.85% some / 0.42% full. At 14:42:48Z the
final sample was 0.08% / 0.06%, and memory PSI was 0.00%. The test-owned API
and Vite servers were gone. No public source, production service, or protected
store was accessed.

Mission Control browser test coverage is **COMPLETE AND VERIFIED**. Broader
repository regression and overall Frontier remain **PARTIALLY VERIFIED**;
live cross-venue evidence, resource sustainability, production recovery, and
deployment are still open.

**Next safe action:** continue source-independent acceptance review; take a
fresh resource sample before any further broad test batch.

## Frontier Arena integration regression — 2026-10-28 14:44 UTC

On `4bf8379`, `tests/arena/test_frontier_timeline.py`,
`test_frontier_replay.py`, and `test_frontier_discovery.py` pass **28/28**.
Pytest took 3.91 seconds; process wall time was 4.63 seconds at 201,368 KiB
peak RSS. The run used a dedicated `/dev/shm` basetemp, zero swaps, no
filesystem input, 376 output blocks, and no socket messages. One existing
Starlette/httpx TestClient deprecation warning remains. At `14:44:31Z`,
post-run I/O PSI avg10 was 0.30% some / 0.18% full and memory PSI was 0.00%.

The slice covers Frontier Arena timeline/replay/discovery against temporary
fixture state. It is **COMPLETE AND VERIFIED** for those modules; full legacy
Arena/repository regression and production worker readiness remain
**PARTIALLY VERIFIED**. Frontier overall remains **PARTIALLY VERIFIED**.

**Next safe action:** continue with bounded source-independent acceptance
review; get a new resource sample before additional test batches.

## Exact-tree web and Arena supervision verification — 2026-10-28 14:49 UTC

On the current tree, the complete web unit suite passes **47/47** across nine
files after the formatting-only `Frontier.test.tsx` edit. The run took 8.64
seconds in Vitest; I/O PSI avg10 stayed at 0.00% in sampled checks and memory
PSI stayed at 0.00%.

The exact-current `tests/arena/test_jobs.py` passes **16/16** after the
deterministic admission-test update. Pytest took 14.81 seconds and process wall
time was 15.42 seconds at 180,992 KiB peak RSS. It used
`/dev/shm/midas-frontier-arena-jobs-20261028T1448Z-kqDcZK`, zero swaps, zero
filesystem inputs, 408 output blocks, and no socket traffic. I/O PSI avg10 was
0.09% some / 0.00% full before the run and 0.00% some / 0.00% full in the
post-run sample; memory PSI remained 0.00%.

Together with the current 465/465 Frontier Python suite, 28/28 Frontier Arena
integration cases, 11/11 admission cases, 47/47 web tests, and 19/19 browser
cases across isolated runs, this closes the listed focused suites. It does
not close the full legacy MIDAS/Arena regression, live cross-venue science,
endurance, protected recovery, or deployment. Overall Frontier remains
**PARTIALLY VERIFIED**.

The superseding acceptance matrix is at the end of
`FRONTIER_ENGINEERING_REPORT.md`. Keep `data/frontier-public-probes/`
untouched; take a fresh admission sample before any broader resource-bearing
run.

## Held-source API route coverage and full Python regression — 2026-10-28 14:53 UTC

Expanded `test_probe_flags_and_references_do_not_enable_unvalidated_sources`
to call seven specialized Kalshi public-data routes with source probing flags
set and arbitrary permission references configured. All returned the active
409 hold reason, and the Kalshi adapter request count remained zero. The
existing assertions also verify the generic probe route and the corresponding
Kalshi/Kraken hold state. This is API-level regression coverage; it does not
authorize live collection.

The full current `tests/frontier` suite passes **465/465**, including the new
route cases, in 29.51 seconds (31.00 seconds wall) at 381,712 KiB peak RSS.
The run used a dedicated tmpfs basetemp, zero swaps, no filesystem input, 376
output blocks, and no socket traffic. I/O and memory PSI avg10 were 0.00% in
the pre-run and post-run samples. One existing Starlette/httpx deprecation
warning remains.

**Next safe action:** continue local source-independent code review. Keep all
source-use holds and protected evidence untouched; take a fresh admission
sample before another broad run.
