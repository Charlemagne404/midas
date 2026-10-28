# Project Frontier Engineering Report

**Report date:** 2026-10-28

## Corrected user-service and active-workload recheck — 2026-10-28 17:27 UTC

The prior 17:23–17:25 system-level `systemctl` queries reported the protected
units as inactive. A follow-up query to the **user** systemd manager corrected
that interpretation: at 17:27:46Z, `midas-reality.service` and
`midas-api.service` were both `active/running`, with MainPIDs **553843** and
**374645**. Their `MemoryCurrent` values were 1,130,409,984 / 1,207,959,552
bytes for Reality and 1,126,404,096 / 1,610,612,736 bytes for API. Both
processes were also present with the expected recorder and release-server
command lines. The capacity API PID **610950** was separately present.

The same process sample found Veritas gap-detail worker PID **719471**, age 26
seconds, in uninterruptible `D` state, running from `/home/charlie/midas` with
roots under both `/home/charlie/midas/data/arena` and
`/home/charlie/midas-veritas/data/arena`. This is an active non-Frontier
workload; it was not started or changed here. Memory PSI at 17:27:46Z was
46.94% avg10 `some` / 43.17% avg10 `full` (16.12% / 14.78% avg60), with
10,210,504 KiB available and 2,132 KiB swap free. The PSI rise is host-level;
it is not attributed to a single process. **Do not retry the full Arena suite
while this workload and pressure are present.** No process or service action
was taken. This entry supersedes the earlier system-level inactive reading.

## Saved live-evidence API regression — 2026-10-28 17:25 UTC

Commit `5dcd369` adds
`tests/frontier/test_captured_public_evidence_api.py`, which copies the
committed genuine Polymarket capture database into pytest's temporary
directory and verifies the Mission Control read API against it. The focused
test passes **1/1 in 0.80 seconds**. Follow-up commit `3e8fa17` strengthens the
same case to pin the live markets' payoff as unverified/non-exhaustive and
resolution as unverified; the final test-tree rerun passes **1/1 in 0.79
seconds**. It checks three stored observations, all five native market IDs,
the one captured book, all ten `hypothesis` edges, a four-edge centered
neighborhood, and the event observation's raw and SQLite row hashes. The
overview confirms the read routes made no network request and markets are
labeled `recorded observations only`. Ruff, format, `py_compile`, and diff
checks pass. The existing Starlette/httpx TestClient deprecation warning
remains.

At 17:25:29Z, memory PSI was 0.00% avg10 / 8.70% avg60 / 16.75% avg300
(`full`: 0.00% / 7.75% / 14.81%), with 10,414,440 KiB available and 2,112 KiB
swap free. Both protected systemd units were still `inactive/dead`; no action
was taken. This short run does not clear the admission gate for a broad Arena
regression. The 17:23 service-state discrepancy remains unexplained.

## Live evidence API exposure and host recheck — 2026-10-28 17:23 UTC

A bounded local API smoke used a temporary copy of the committed 270,336-byte
Polymarket evidence store and the normal Frontier read router. No network
probe was enabled or made. The overview reported three observations; the
markets route returned five markets as `recorded observations only`; the books
route returned the one captured book; the relationship route returned ten
`hypothesis` edges; and a centered query returned four neighboring edges. The
exact source observation route returned HTTP 200 for the event-group evidence.
All checks passed. Starlette emitted its existing `httpx` TestClient
deprecation warning. This verifies the saved-evidence API surface, not a new
browser E2E run or live collection through Mission Control.

At 17:23:10Z, read-only systemd inspection reported both
`midas-reality.service` and `midas-api.service` as `inactive/dead` with no main
PID. This differs from the 17:18:23Z sample, when both were active; no cause is
known and no service action was taken. Memory PSI at 17:23:10Z was 48.55%
avg10 / 43.35% full avg10 (32.43% / 28.77% avg60), with 10,200,612 KiB
available and 2,092 KiB swap free. Keep broad regression stopped. Do not infer
production recovery or outage cause from these snapshots.

## Current status and acceptance delta — 2026-10-28 17:18 UTC

This checkpoint supersedes the earlier 16:30 acceptance snapshot. Frontier
remains isolated on `codex/frontier-20261026`, research-only, and undeployed.
The only untracked path is the pre-existing `data/frontier-public-probes/`
directory; it was preserved and not used for this evidence.

Three bounded, unauthenticated requests through the Polymarket public adapters
returned and were retained as raw and normalized evidence: one Gamma listing
at 17:04:45Z (one open binary market, native ID `2589810`), one CLOB book at
17:09:19Z (five asks, no bids, best ask 0.995 in the returned depth), and one
Gamma event lookup at 17:13:05Z (five child markets under native event
`606422`, “Fed Decision in October?”). Requests used 8-second timeouts,
bounded response sizes, and zero retries. The book's exchange timestamp was
about 10.04 seconds before receipt; precision and simultaneity are unknown.
Public API availability is documented in Polymarket's [research data
guide](https://institute.polymarket.com/data) and [CLOB order-book
reference](https://docs.polymarket.com/api-reference/market-data/get-order-book).

The isolated SQLite store is 270,336 bytes under its 4 MiB bound, with three
observations, three deterministic replay results, and ten persisted,
source-pinned `SAME_EVENT` hypotheses. Two repeated event-group replays share
run ID
`68ffa2fee9e70f727395e1d11371b561a4ee51c7baddc82004f0b6a5bcee99ea` and result
hash `aa95c4c6b35c681631e054c4a8a7bd44bb0e420987f8833a58c71b7e8f55debe`; the
reloaded result contains ten membership proposals and zero candidates. An
offline integrity pass verified raw and normalized file hashes, SQLite row
hashes, all three replay records, and all ten hypotheses. Event membership
does not prove mutually exclusive/exhaustive outcomes, settlement or payoff
equivalence, a cross-venue relationship, or executable economics.

The full `tests/arena` regression was interrupted after 105 passes in 2:25
when system memory PSI rose to 36.63% avg10 / 31.86% full at 17:18:23Z. No
assertion failure was reported before interruption; the run is partial, not a
pass. It peaked at 484,168 KiB RSS, used no swap or sockets, and both protected
services remained active and untouched. Broader regression stays deferred
until a fresh resource sample shows that memory pressure has cleared.

| Requirement | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Polymarket public adapter evidence | PARTIALLY VERIFIED | Three bounded public responses cover one market listing, one token book, and one event group. This is selected live evidence, not broad adapter conformance, synchronized execution, or venue-wide coverage. |
| Live same-venue event graph | COMPLETE AND VERIFIED WITHIN TESTED SCOPE | Five source-grouped markets yield ten stored, observation-pinned `SAME_EVENT` hypotheses and an indexed neighborhood. All are hypotheses; no payoff or resolution equivalence is certified. |
| Stored evidence and deterministic replay | COMPLETE AND VERIFIED WITHIN TESTED SCOPE | Three observation/replay records and ten relationships pass offline hash checks; repeated event replays reproduce the same run and result hashes. Cross-source synchronization and endurance remain unmeasured. |
| Opportunity discovery and independent economics | PARTIALLY VERIFIED | Fixture-backed candidate families and independent Decimal audits remain covered. The live event replay emitted zero candidates; no live cross-venue match or eligible opportunity is established. |
| Other venue live research | BLOCKED | Existing Kalshi, Kraken, and Coinbase source-use holds remain in force. No probe was performed for them. |
| Laboratory/Arena integration | PARTIALLY VERIFIED | Frontier slices remain covered; the broader Arena regression stopped after 105 cases under system memory pressure and has no full-suite result. |
| Resource sustainability | PARTIALLY VERIFIED | Bounded components have measured profiles, but this Arena run encountered material memory pressure. Long-running collection and deployment load remain unmeasured. |
| Production deployment | DEFERRED | Frontier remains isolated and undeployed; protected recovery, source policy, operations, and deployment gates remain separate. |
| Project Frontier overall | PARTIALLY VERIFIED | Genuine Polymarket metadata, book, event graph, and replay evidence now extend the fixture-backed platform; multi-venue economic validation, full legacy regression, endurance, protected recovery, and deployment remain incomplete. |

Continue source-independent, low-resource review. Do not retry the broad Arena
suite until a new resource admission sample supports it.

## Historical replay request-bound checkpoint — 2026-10-28 16:45 UTC

The historical price replay request validator now checks each observation ID's
length before hashing IDs for duplicate detection. It rejects non-lowercase or
non-hex SHA-256 values and then checks uniqueness. The API regression sends an
overlength ID, receives HTTP 422, and confirms it did not create another replay.
The focused test passes 1/1 (55 unrelated API cases filtered) using the
MockTransport-backed fixture. Ruff, format, syntax, and diff checks pass.
Commit `e44b23d` contains the implementation and regression.

At 16:45:20Z, CPU PSI avg10 was 34.45%, memory PSI avg10 0%, I/O PSI avg10
0.14%, and about 9.7 GiB was available; swap remained full. Protected Reality
and API services were active and untouched. This focused fixture test made no
public request. The full API and Frontier suites were not run.

## Virtual capital-carry verification — 2026-10-28 16:43 UTC

At code HEAD `b7f2155`, `tests/frontier/test_capital_carry.py` passed 27/27 in
0.46 seconds on tmpfs. Subsequent commits changed API validation/tests and docs,
not capital-carry logic. The tested sensitivity keeps hypothetical balances
separate per venue, requires hash-pinned settlement inputs, holds each venue's
capital until the latest modeled settlement plus the explicit release delay,
and independently recomputes simple-interest carry. It does not establish
actual financing, transfer, custody, redemption, venue fees, or executable
availability; candidate classification remains unchanged. No capital-carry
code changed in this checkpoint.

The 16:43:09Z post-run host sample showed CPU PSI avg10 36.33%, memory and I/O
PSI avg10 0%, and about 9.9 GiB available; swap was full. Both protected
Reality and API services were active. No external source or production service
was accessed.

## Focused regression results — 2026-10-28 16:42 UTC

The full `tests/frontier/test_relationship_reviews.py` module passes 16/16
after adding request-level lowercase SHA-256 validation. The focused new cases
pass 3/3. `test_coinbase.py` and `test_source_data_permissions.py` pass 18/18
after correcting a stale test expectation that still used the prior Coinbase
hold wording. The changed Frontier UI test passes 1/1 with eight unrelated
cases filtered out. Ruff check, Ruff format check, and `git diff --check` pass.

The first Coinbase-focused run reported 17 passes and one stale assertion
failure; this was a test-fixture string mismatch, not a source-policy or
runtime failure. The corrected two-module rerun passed. At 16:42:07Z, CPU PSI
avg10 was 33.24%, memory PSI avg10 0%, I/O PSI avg10 0.01%, and about 9.9 GiB
was available. Swap remained full. The protected Reality and API services were
active; no source endpoint was queried. Broad suites remain deferred under
host CPU pressure.

## Relationship-review evidence validation checkpoint — 2026-10-28 16:39 UTC

Static review found that the review request bounded the number of observation
IDs but did not validate their SHA-256 format until constructing the durable
review record, after the handler had looked them up in storage. The request
model now requires lowercase 64-character SHA-256 IDs before route processing.
An adversarial regression covers overlength, uppercase, and non-hex values.

Same-payoff mappings remain limited to 20 entries of at most 120 characters;
logical-implication mappings remain limited to 1,024 entries of at most 128
characters. The route also pins both markets to stored observations, verifies
the normalized evidence contains those markets, rejects held-source evidence,
and states that reviewer and external-assertion identities are unauthenticated.
Commit `8c898dc` contains the code and regression. `py_compile` and
`git diff --check` pass. The focused test remains pending because CPU PSI was
39.68% avg10 and swap had only 1.2 MiB free at the latest sample.

## Coinbase source-use restriction checkpoint — 2026-10-28 16:36 UTC

The current official [Coinbase Market Data Terms](https://www.coinbase.com/legal/market_data),
updated 2026-08-07, restrict use of Market Data to develop, train, fine-tune,
teach, validate, benchmark, or improve AI/ML models, algorithms, chatbots,
agents, and other automated systems, or for related AI research, development,
or operation, absent prior express written consent. MIDAS has no validated
consent or intended-scope review for that use. Coinbase remains held; no
endpoint was queried.

The adapter and API now use one shared hold reason, and the Exchanges view
lists the specific restricted activities. Adapter/API/UI regression assertions
were updated but not run under the current CPU-pressure admission hold.
`git diff --check` passes. The initial implementation is commit `5ea6921`; this
checkpoint further lists the activities named in the terms. Neither change
enables source use or lifts the existing hold.

## Arena regression stop and current status — 2026-10-28 16:30 UTC

The finite `tests/arena` retry used the absolute Frontier worktree package path
and tmpfs basetemp `/dev/shm/midas-frontier-arena-20261028-1610`. It advanced
beyond the 50% progress marker without a reported assertion failure, then was
stopped after 9:06.59 when CPU PSI remained elevated on the six-core host while
the protected Reality recorder was active. The pytest process peaked at
487,772 KiB RSS, used 549.86 CPU seconds, made zero socket calls, and used zero
swaps. SIGINT and SIGTERM did not stop the CPU-bound process; after confirming
its PID, the Frontier test process alone was terminated with SIGKILL (exit
137). The run produced no pytest summary and is not a pass.

CPU PSI at 16:18:24 UTC was 24.67% some avg10 / 23.78% avg60. After the test
process was absent, CPU PSI measured 38.09% avg10 / 28.68% avg60 at 16:19:41
and 42.63% / 37.65% at 16:21:29. Memory PSI avg10 remained 0.00%, I/O PSI
avg10 was 0.36% some at the first post-stop sample, and about 9.9 GiB remained
available. CPU pressure persisted without a pytest or Arena worker; no cause is
attributed to Frontier alone. A read-only sample at 16:23:12Z still measured
CPU PSI at 41.51% avg10 / 40.14% avg60, with memory and I/O PSI low. The Reality
recorder, MIDAS services, public sources, preserved evidence, and untracked
capture directory were left untouched. A later read-only PSI sample at
16:30:27Z showed CPU `some` at 41.18% avg10 / 40.35% avg60, with memory and I/O
avg10 at 0.00%. At 16:30:43Z, `midas-reality.service` and `midas-api.service`
were both active; service `MemoryCurrent` was 1,207,721,984 and 1,223,196,672
bytes. These are service-accounting snapshots, not headroom. No service was
restarted or reconfigured.

Current acceptance snapshot:

| Requirement | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Isolated exchange-independent adapter foundation | COMPLETE AND VERIFIED | Four read-only adapters, capability declarations, canonical models, fixture contracts, and the shared bounded transport are implemented and covered by the current Python suite. |
| Kalshi, Kraken, and Coinbase live source validation | IMPLEMENTED, LIVE VALIDATION PENDING | Adapters are fixture-verified; terms and intended-use holds keep further collection and held evidence quarantined. |
| Canonical instrument and supported payoff semantics | PARTIALLY VERIFIED | Versioned canonical models and exhaustive supported payoff constructions pass controlled fixtures; cross-venue settlement equivalence is not established. |
| Relationship graph and evidence validation | PARTIALLY VERIFIED | Bounded hypothesis discovery, relationship review history, and verified payoff edges are fixture-tested; no genuine verified cross-venue payoff relationship is established. |
| Candidate generation and independent economic audit | PARTIALLY VERIFIED | Bounded opportunity families and independent Decimal recalculation pass controlled fixtures; no eligible live cross-venue opportunity is established. |
| Cross-venue costs, capital, and execution scenarios | PARTIALLY VERIFIED | Fee evidence, depth, virtual venue balances, timing, partial fills, and stress scenarios are modeled; account-specific fees, jurisdiction, transfer, collateral, and settlement remain unresolved. |
| Provenance, storage, and deterministic replay | COMPLETE AND VERIFIED WITHIN TESTED SCOPE | Hash-checked observations, relationship reviews, deterministic/paired replay, and selected Arena handoffs have fixture and persistence regression coverage; cross-source synchronization and endurance are unmeasured. |
| Bounded collection and source-health handling | IMPLEMENTED, LIVE VALIDATION PENDING | Isolated bounded collection and failure/health evidence paths are fixture-tested; current venue holds prevent live validation for Kalshi, Kraken, and Coinbase. |
| Laboratory/Arena integration | PARTIALLY VERIFIED | Frontier integration slices pass; the 427-case full Arena retry stopped beyond 50% under sustained CPU pressure and did not produce a suite result. |
| Source-aware analytics and readiness | PARTIALLY VERIFIED | Coverage, quality, rejection, and readiness views use bounded stored evidence; the current sample does not support venue-wide prevalence claims. |
| Native Frontier workspace | COMPLETE AND VERIFIED, DEPLOYMENT PENDING | Vitest 47/47, TypeScript, ESLint, and Prettier pass. Production build and 7 regular + 2 seeded fixture browser cases passed at the 13:59 UTC checkpoint; this turn changed only a test assertion. |
| Research-only security boundary | COMPLETE AND VERIFIED | Public transport is anonymous GET-only, host-contained, redirect-disabled, and source-gated; no authenticated trading, wallet, deposit, withdrawal, or order path is present in Frontier. |
| Resource sustainability | PARTIALLY VERIFIED | Bounded Python/web runs have measured RSS and no test swaps; a broader Arena test caused sustained CPU pressure and was stopped. Continuous-source and deployment load are unmeasured. |
| Live cross-venue scientific acceptance | BLOCKED | Current source-use holds prevent new Kalshi/Kraken/Coinbase research; fixture results are not represented as live evidence. |
| Production deployment | DEFERRED | The Frontier worktree remains isolated and undeployed; recovery, source-use, operational, and explicit deployment gates remain outstanding. |
| Project Frontier overall | PARTIALLY VERIFIED | The research platform is substantial and bounded-tested, but live cross-venue science, full Arena regression, endurance, protected recovery, and deployment are incomplete. |

Continue with source-independent implementation review. Reattempt broad regression
only after a fresh CPU PSI sample is stable. Preserve source-use holds and the
current worktree boundary. The detailed 20-section engineering report and
append-only work history follow.

## Spot-versus-event payoff distinction in the native UI — 2026-10-28

The Exchanges view labels Kraken and Coinbase spot feeds as context and states
that a spot price is not a prediction-contract payoff. Added a rendered UI
assertion to the existing Coinbase source-policy/no-auto-probe test. The
focused case passes **1/1**, and the full frontend Vitest suite passes
**47/47 across nine files** in 21.95 seconds (22.51 seconds wall), at 267,328
KiB peak RSS, with zero swaps and socket messages. TypeScript `tsc -b`, targeted
ESLint, and Prettier check pass. The initial Prettier check caught the new
assertion's formatting; after formatting, the check and focused test passed.

No production UI implementation changed. The production build and fixture
browser E2E remain verified by the dated 13:59 UTC checkpoint; they were not
rerun for this test-only edit. At 16:09:21 UTC after verification, memory and
I/O PSI avg10/avg60 were both 0.00%, and approximately 10 GiB was available.
No live exchange source, production service, or capture was accessed. Test
commit: `8d61a62` (`apps/web/src/Frontier.test.tsx`).

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Spot-versus-event UI disclosure | COMPLETE AND VERIFIED | The rendered Exchanges view's spot disclaimer has a regression assertion. |
| Current frontend tests and static checks | COMPLETE AND VERIFIED | Vitest 47/47, `tsc -b`, targeted ESLint, and Prettier check pass. |
| Production build and browser E2E | COMPLETE AND VERIFIED, DATED | Existing 13:59 UTC acceptance remains relevant because production UI code did not change; this checkpoint did not rerun build/E2E. |
| Frontier overall | PARTIALLY VERIFIED | Genuine cross-venue findings, broader legacy regression, endurance, protected recovery, and deployment remain incomplete. |

## Adapter transport host containment — 2026-10-28

`BaseReadOnlyAdapter` now requires every injected transport host to belong to
that adapter's declared host allowlist. A subset remains permitted for
endpoint-specific fixtures; an extra host or another venue's host fails closed
at construction. Regression cases cover both rejection paths, and an existing
single-host Polymarket Gamma fixture still passes. The focused selection passed
**3/3**; strict mypy for `base.py`, Ruff check, and Ruff format check pass.

The first full test attempt used exact equality between injected and declared
host sets. It failed **70** tests because existing fixtures use valid subsets
such as Gamma-only for an adapter that also supports CLOB endpoints. The
implementation was refined to subset containment; 405 tests passed in that
attempt, with all failures localized to the new constructor rejection. No
fixture or test was changed to hide the boundary error. The final current
`tests/frontier` suite passes **475/475** in 30.14 seconds pytest time (31.68
seconds wall), peaking at 381,080 KiB RSS with zero swaps, filesystem inputs,
and socket messages. It used the absolute worktree package path and tmpfs
basetemp `/dev/shm/midas-frontier-host-final-20261028-1604`. One existing
Starlette/httpx TestClient deprecation warning remains.

Before the final run at 16:03:57 UTC, memory PSI avg10 was 0.00% (avg60 0.03%
some / 0.02% full), I/O PSI avg10 was 0.00%, about 9 GiB was available, and
swap had 168 KiB free. At 16:04:42 UTC after validation, memory PSI avg10/avg60
was 0.00%/0.01% some and 0.00%/0.00% full, I/O PSI was 0.00%, and about 9 GiB
remained available. No live endpoint or protected service was accessed.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Adapter host-allowlist containment | COMPLETE AND VERIFIED | Injected allowlists cannot widen beyond the adapter's source declaration; valid host subsets remain supported. |
| Current Frontier Python suite | COMPLETE AND VERIFIED | `tests/frontier` passes 475/475 with one existing deprecation warning. |
| Changed adapter static checks | COMPLETE AND VERIFIED | Targeted strict mypy, Ruff check, and Ruff format check pass. |
| Full Arena/repository regression | PARTIALLY VERIFIED | The earlier Arena run stopped at 67%; broader legacy regression remains open. |
| Frontier overall | PARTIALLY VERIFIED | Live cross-venue findings, broader regression, endurance, protected recovery, and deployment remain incomplete. |

## Transport hardening and current Frontier suite verification — 2026-10-28

The focused fixture-only tests for nonstandard JSON tokens, parser complexity,
environment proxy handling, and injected transport rejection passed **10/10**
(0.69 seconds pytest time, 1.06 seconds wall, 62,656 KiB peak RSS, zero swaps,
and zero socket messages). Ruff check passed; Ruff format confirmed all three
changed Python files were already formatted. Strict mypy reported no issues in
`packages/midas/frontier/adapters/transport.py`.

The full current `tests/frontier` suite passed **473/473** in 30.27 seconds
pytest time (31.83 seconds wall), at 383,136 KiB peak RSS, with zero swaps and
zero socket messages. The test used the absolute Frontier worktree package
path and isolated tmpfs basetemp `/dev/shm/midas-frontier-full-20261028-1600`.
One existing Starlette/httpx TestClient deprecation warning remains. A sample
shortly before the full suite measured memory PSI avg10 0.00% (avg60 2.02%
some / 1.42% full), I/O PSI avg10 0.00%, about 10 GiB available, and full swap
with 112 KiB free. At 16:01:12 UTC after validation, memory PSI avg10/avg60 was
0.00%/0.66% some and 0.00%/0.46% full, I/O PSI avg10 was 0.14% some / 0.00%
full, and about 10 GiB remained available.

No live endpoint or protected service was accessed. This verifies the current
Frontier Python suite after parser and proxy hardening. The full legacy Arena
suite remains partial: the corrected run reached 67% before it was stopped
under host memory pressure. This checkpoint makes no production readiness,
live cross-venue, or endurance claim.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Frontier public transport hardening | COMPLETE AND VERIFIED | Focused fixture regressions pass 10/10; no network request was made. |
| Current Frontier Python suite | COMPLETE AND VERIFIED | `tests/frontier` passes 473/473 with one existing deprecation warning. |
| Transport static checks | COMPLETE AND VERIFIED | Ruff check/format and targeted strict mypy pass. |
| Full Arena/repository regression | PARTIALLY VERIFIED | The interrupted Arena rerun reached 67%; broader regression remains open. |
| Frontier overall | PARTIALLY VERIFIED | Genuine cross-venue science, broad regression, endurance, protected recovery, and deployment remain incomplete. |

## Frontier public egress static audit — 2026-10-28

Read-only code search of `packages/midas/frontier/adapters` and
`apps/api/frontier.py` found one production construction point for
`PublicReadTransport`, in `BaseReadOnlyAdapter`, and no separate direct HTTP
client in that scoped Frontier path. Adapter network calls use the shared
`get_json` method. The transport pins requests to HTTPS and exact source host
allowlists, rejects URL credentials and non-default ports, disables redirects,
uses GET only, revalidates the final request URL, and bounds response reads.
Its owned client disables environment proxy discovery; injected clients are
restricted to isolated `MockTransport` fixtures without custom mounts. The
source API routes use registered adapters and finite collection bounds.

This is static source evidence, not a runtime security assessment. The new
parser and proxy regressions have not run because current memory PSI remains
high and swap is full. At 2026-10-28 15:57:34 UTC, memory PSI avg10 was
33.82% some / 24.54% full, I/O PSI avg10 was 0.01% some / 0.01% full, roughly
10 GiB was available, and swap had 92 KiB free. No Frontier tests or lint
process was started from that sample. The review also found legacy HTTPX
clients in Polymarket market-data, CTF, Reality, and Veritas code; those paths
were outside scope and remain unchanged. No public endpoint, capture, service,
or untracked data was accessed.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Frontier egress-path source review | PARTIALLY VERIFIED | Static callsite and boundary review only; focused regressions and runtime validation remain pending. |
| Frontier parser and proxy changes | IMPLEMENTED, VALIDATION PENDING | Tests are committed in the worktree but not run on current HEAD under the resource hold. |
| Legacy MIDAS HTTP clients | DEFERRED | Identified by repository-wide callsite search, not modified or audited in this Frontier checkpoint. |
| Frontier overall | PARTIALLY VERIFIED | Live cross-venue science, broader regression, endurance, protected recovery, and deployment remain open. |

## Revalidate every Frontier persistence input — 2026-10-28

The write-boundary fix now covers all Frontier persistence methods, not only
source observations. Raw and normalized observations, relationship proposals,
relationship reviews and revisions, deterministic replays, historical replays,
and paired comparisons are reparsed from Python-mode model dumps before the
store is initialized. Replay writes additionally recompute the manifest-derived
run ID and result digest. This closes the copied-model route to persisting
malformed normalized rows or unreadable replay artifacts.

Storage regressions cover copied raw/normalized records, malformed
relationships, and replay/comparison hashes. The storage module passes
**25/25** in 1.31 seconds (1.66 seconds wall), at 68,560 KiB peak RSS, zero
swaps, zero filesystem input, and zero socket messages. Strict mypy passes for
`storage.py`; Ruff check/format and `git diff --check` pass. The exact Frontier
plus Arena replay/discovery/timeline suite passes **468/468** in 31.61 seconds
(33.10 seconds wall), at 380,404 KiB peak RSS, zero swaps, zero filesystem
input, 8 output blocks, and zero socket messages. One existing Starlette/httpx
deprecation warning remains. Output used the isolated tmpfs root
`/dev/shm/midas-frontier-storage-all-writers-full-20261028`.

Before the full suite memory PSI avg10 was 0.00%, I/O PSI was 0.12% some /
0.02% full, and about 10 GiB was available. Afterward memory remained 0.00%,
I/O was 0.01% some / 0.01% full, and about 10 GiB was available. No live
source, protected store, production service, or historical research artifact
was accessed. **Implementation commit:** `e99cf0e`.

## Observation write-boundary revalidation — 2026-10-28

The append-only evidence store serialized already-instantiated raw and
normalized models without re-running model validation. A `model_copy(update=...)`
could bypass Pydantic checks and persist a malformed observation. The store
now round-trips each input through `model_dump(mode="python")` and
`model_validate` before creating the database or writing any rows. The storage
regression verifies that both a copied raw record with a mismatched body hash
and a copied market with invalid payoff structure fail before database creation.

`tests/frontier/test_storage.py` passed **22/22** in 16.83 seconds, at 68,252
KiB peak RSS, with zero swaps, filesystem input, and socket messages. Strict
mypy passes for `storage.py`; Ruff and whitespace checks pass. Output stayed
under `/tmp/midas-frontier-storage-input-validation-20261028`. The exact
Frontier suite plus Arena replay/discovery/timeline regression then passed
**465/465** in 31.56 seconds (33.02 seconds wall), at 380,600 KiB peak RSS,
zero swaps, zero filesystem input, and zero socket messages. It emitted one
existing Starlette/httpx deprecation warning; output used the isolated tmpfs
root `/dev/shm/midas-frontier-storage-exact-full-20261028`. Pre-run memory PSI
avg10 was 0.00%, I/O PSI 0.09% some / 0.06% full; immediately afterward
memory remained 0.00% and I/O was 0.01% some / 0.01% full, with about 10 GiB
available. The write-boundary fix is committed as `6a3e459`.

## Empty payoff-state rejection in relationship verifiers — 2026-10-28

An offline audit found that malformed copied market records with no payoff
states and no instrument payout rows could pass same-payoff or logical
implication checks over empty mappings. Both direct verifiers now require
nonempty exhaustive states and full market structural revalidation. The
same-payoff verifier advanced from v7 to v8, logical implication from v3 to
v4, and independent audit from v21 to v22 so earlier attestations do not count
as current evidence for new candidate research.

New regressions cover the copied empty-state cases and rejection of prior
verifier versions. The three affected relationship/economics modules passed
**97/97** in 1.04 seconds, at 65,304 KiB peak RSS with zero swaps, filesystem
input, or socket messages. Strict mypy passes on `relationships.py`,
`independent_audit.py`, and `models.py`; Ruff check/format and
`git diff --check` pass. The complete Frontier suite plus Arena
replay/discovery/timeline regression passed **463/463** in 111.02 seconds
(112.48 seconds wall), at 380,764 KiB peak RSS, zero swaps, 16 filesystem input
blocks, and zero socket messages. It emitted one existing Starlette/httpx
deprecation warning. Test artifacts stayed under
`/tmp/midas-frontier-v8-v4-full-20261028`. Pre-run memory PSI avg10 was 0.00%,
I/O PSI was 0.03% some / 0.00% full, and about 10 GiB was available. Immediately
afterward memory PSI remained 0.00%, while I/O rose to 5.37% some / 4.16%
full; further tests are held until a fresh sample falls below the 1% gate.
This correction provides no new live cross-venue equivalence evidence. The
implementation is committed as `eb53842`. A read-only follow-up found no
additional empty-state acceptance in the bounded multi-outcome and joint-state
audits or the verified relationship-review API path; no runtime test was run
during the post-suite I/O pressure hold.

## Same-payoff verifier empty-instrument rejection — 2026-10-28

Direct reproduction found that two verified binary markets with no
instruments could receive a `VERIFIED` same-payoff edge: the empty instrument
mapping passed the bijection check without comparing any payout vectors. The
verifier now rejects a supplied market with no instrument payout vectors, and
the version is advanced from 6 to 7. This invalidates old v6 attestations for
new independent candidate audits while leaving their stored evidence
readable; a fresh review against current source records is required.

The regression covers the empty-left, empty-right, and both-empty cases. The
targeted verifier/version slice passed **10/10**; Ruff check/format and
`git diff --check` pass. The complete `tests/frontier` suite plus Arena
replay/discovery/timeline passed **459/459** in 108.32 seconds (109.76 seconds
wall), peaking at 381,136 KiB RSS with zero swaps and socket messages. Test
artifacts stayed under `/tmp/midas-frontier-v7-full-20261028`. Strict mypy is
also passed after I/O PSI avg10 returned below 1%: `relationships.py` and
`independent_audit.py` have no issues. Ruff check/format and `git diff --check`
pass. This is an implementation correction, not evidence of a live cross-venue
equivalence.

## Arena relationship fixture repair — 2026-10-28 12:52 UTC

The Arena discovery fixtures used placeholder source observation IDs. The
independent same-payoff verifier requires both supplied markets' provenance
observation IDs to appear in the assertion evidence, so it correctly marked
the relationship rejected and the snapshot validator refused to accept it.
The fixture now cites those exact pinned IDs; no verifier or production code
changed.

The bounded run of `tests/arena/test_frontier_discovery.py`,
`tests/arena/test_frontier_timeline.py`, and
`tests/frontier/test_discovery_comparison.py` passed **15/15** in 5.88 seconds
(6.59 seconds wall), at 198,600 KiB peak RSS, zero swaps, and zero socket
messages. Generated test artifacts stayed under
`/tmp/midas-frontier-arena-20261028T1252Z`. The run emitted one existing
Starlette/httpx `TestClient` deprecation warning. This verifies deterministic
fixture behavior, not live cross-venue equivalence or production readiness.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Arena Frontier discovery and timeline regressions | COMPLETE AND VERIFIED | 14/14 pass after correcting pinned fixture evidence. |
| Frontier discovery-scope comparison | COMPLETE AND VERIFIED | 1/1 fixture-based deterministic test passes. |
| Frontier overall | PARTIALLY VERIFIED | Genuine cross-venue public evidence, protected recovery, broader source validation, and deployment remain open. |

## Broader isolated browser regression — 2026-10-28 12:48 UTC

The one-worker non-Veritas Playwright suite passes **16 tests**, with two
seeded tests skipped because this run used an empty store. It took 35.8 seconds
of Playwright time (36.36 seconds wall) and reached 222,188 KiB peak RSS, with
zero swaps and socket messages. It covered Frontier, Arena, Laboratory, paper
simulation, Reality's fixture-backed explorer, Readiness, deferred chart
loading, and Mission Control. The two seeded Frontier cases passed separately
**2/2** against their deterministic fixture store. The Laboratory tests
completed one six-run comparison and one adversarial simulation in the
temporary database; no long-running campaign was launched.

The historical Veritas artifact browser test was excluded because its expected
files are in the preserved Veritas workspace. That workspace was neither read
nor redirected; Veritas unit component and offline economics/replay suites
remain verified separately. The browser-run Reality operations were
intercepted, paper state reported `synthetic` mode and zero live orders, and no
exchange probe was enabled. The demo API/Vite processes exited after the run.

At `12:48:15Z`, memory PSI avg10 was **0.00%** and I/O PSI was **0.01% some /
0.00% full**; about **9 GiB** was available. Host swap occupancy remained
3.5/4 GiB, but the test process used no swap.

| Requirement | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Non-Veritas MIDAS browser regression | COMPLETE AND VERIFIED | 16 passed; two seeded Frontier cases pass separately. |
| Veritas historical-artifact browser flow | PARTIALLY VERIFIED | Historical workspace was intentionally not read; fixture-backed components and offline economics/replay pass. |
| Frontier overall | PARTIALLY VERIFIED | Genuine cross-venue evidence, protected recovery, wider source validation, and deployment remain open. |

## Frontier frontend build and browser verification — 2026-10-28 12:46 UTC

The native Frontier frontend type-checks and builds in production mode. `tsc
-b` passes in 8.63 seconds with 471,424 KiB peak RSS. Vite transforms 2,230
modules and builds in 4.78 seconds (5.03 seconds wall), with 684,180 KiB peak
RSS. The output was directed to `/tmp/midas-frontier-web-build-20261028T1234Z`
so the workspace `dist/` was not overwritten. Frontier is a lazy 182.82 kB
JavaScript chunk (44.55 kB gzip). The deferred chart chunk is 544.51 kB
(186.79 kB gzip), above Vite's 500 kB warning threshold; lazy-loading is
verified in the browser.

Frontend Vitest passes **47/47 in 9 files**, 20.32 seconds (20.73 seconds
wall), with 288,496 KiB peak RSS. ESLint and the full Prettier check pass.
Focused browser verification passes **10/10 in 20.5 seconds** (21.14 seconds
wall; 206,744 KiB peak RSS). It covers Frontier empty states, market/source
views, explicit recorded-history actions, hypothetical joint-state replay,
fixture-only Kalshi settlement arithmetic, graph bounds, 390 px responsive
overflow, deferred chart load, and read-only Arena/Laboratory artifact views.
The separate seeded browser suite passes **2/2 in 8.0 seconds** (10.60 seconds
wall; 180,704 KiB peak RSS), including 21 fixture history captures, persisted
deterministic replay, and a hash-verified seeded Arena result loaded into
Laboratory. A further **1/1** readiness browser check passed in 4.5 seconds
(5.02 seconds wall; 166,284 KiB peak RSS) without an explicit
`MIDAS_FRONTIER_E2E_RUN_ID`, confirming that generated owner markers survive
worker config reloads.

The initial browser attempt exposed a harness defect: Playwright did not create
the parent directory for its temporary SQLite database, and API health returned
503 (`unable to open database file`). The config now creates a fresh non-symlink
root directly under the system temp directory and uses a per-run owner marker
to let Playwright worker processes reopen config after test data is created;
non-empty roots from other runs are rejected. Empty-state and seeded browser
runs both pass after this fix. Both local servers exited, and their ports were
clear after testing.

At `12:46:07Z` post-verification, memory PSI avg10 was **0.00%**, I/O PSI
some/full was **0.08%**, and about **9.9 GiB** was available. All timed test
processes reported zero swaps and socket messages. The Vite chunk-size warning
remains a performance follow-up, not a failed production build. Frontier
remains research-only and undeployed.

| Requirement | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Frontend type-check, lint, and format | COMPLETE AND VERIFIED | TypeScript, ESLint, and full Prettier checks pass. |
| Frontier production frontend | COMPLETE AND VERIFIED | Vite build succeeds; chart chunk remains above the 500 kB warning threshold. |
| Frontier browser acceptance | COMPLETE AND VERIFIED | 12 focused empty-state and seeded Playwright tests pass plus a default-token config check; broader unrelated UI E2E remains unrun. |
| Frontier overall | PARTIALLY VERIFIED | Live cross-venue evidence, wider browser regression, protected recovery, and deployment remain open. |

## Bounded source-quality, Veritas, and integration regressions — 2026-10-28 12:33 UTC

The source anomaly audit fixtures initially advertised reconstruction revision
5. The current Reality replay engine and collector explicitly support revisions
1–4, so they correctly rejected the unsupported fixture. The two synthetic
records were corrected to revision 4; production code and recorded evidence
were unchanged.

The corrected source-quality regression group passes **10/10** in 0.17 seconds
with 44,256 KiB peak RSS, zero swaps, and zero socket messages. The two Veritas
fixture suites for independent Decimal economics and V6 offline replay pass
**24/24** in 0.36 seconds with 45,460 KiB peak RSS, zero swaps, and zero socket
messages. Their writes are confined to unique `/tmp` basetemps.

The full `tests/integration` group passes **56 tests**, with the opt-in
PostgreSQL test skipped because `MIDAS_TEST_POSTGRES_URL` was not configured.
It took 28.49 seconds of pytest time (29.77 seconds wall), reached 222,868 KiB
peak RSS, and reported zero swaps and socket messages. It emitted one existing
Starlette/httpx `TestClient` deprecation warning. API databases, recording
paths, and replay state were isolated under
`/tmp/midas-frontier-integration-20261028T1235Z`.

The integration pre-run sample showed memory PSI avg10 **0.00%** and I/O PSI
**0.04%**. At `12:33:34Z` post-run, memory remained **0.00%**, I/O was
**0.56% some / 0.39% full**, and about **10 GiB** was available. Host swap
occupancy was 3.5/4 GiB, but pytest used no swap. No live source, protected
recording, frozen campaign, service control, or operational evidence store was
accessed.

| Requirement | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Reality source-quality replay audits | COMPLETE AND VERIFIED | 10/10 against supported replay revision 4. |
| Veritas V6 offline replay and independent economics | COMPLETE AND VERIFIED | 24/24 fixture-based; does not establish live economics. |
| MIDAS integration regression | PARTIALLY VERIFIED | 56 passed, optional PostgreSQL skipped; browser and production acceptance remain. |
| Frontier overall | PARTIALLY VERIFIED | Genuine cross-venue validation, broader browser regression, production recovery, and deployment remain open. |

## Additional Reality regression evidence — 2026-10-28 12:29 UTC

Source-independent Reality tests now add the following evidence:

- The synthetic foundry suite passes **18/18** (0.83 seconds, 46,988 KiB
  peak RSS).
- Model-training and replay fixtures pass **19/19** (3.87 seconds pytest
  time / 4.99 seconds wall, 400,572 KiB peak RSS).
- Full-scale staging-admission predicates pass **17/17** (0.15 seconds,
  43,812 KiB peak RSS).
- The read-only sandbox check passes **1/1** with a child process confined to
  temporary source/staging roots (0.16 seconds, 43,656 KiB peak RSS).
- The Reality shadow suite passes **20/20** on `/tmp` (2.97 seconds pytest
  time / 3.54 seconds wall, 170,616 KiB peak RSS). Its first `/dev/shm` run
  had three capacity-guard failures because free space on that mount was below
  the fixture's configured reserve; all three cases then passed on `/tmp` and
  the full module passed there.

All listed runs used isolated synthetic or temporary evidence, had zero swaps
and zero socket messages, and did not access the protected recorder, frozen
campaigns, live sources, or service controls. At `12:29:11Z`, I/O PSI some was
**1.08%** avg10 (full **0.90%**); additional tests are paused until the gate
clears. The Frontier suite remains **430/430** from the exact current tree.

## Public transport security and current verification — 2026-10-28 12:26 UTC

Security review found that the optional injected `httpx.AsyncClient` could
carry authorization headers/auth handlers, cookies, request hooks, default
query parameters, or redirect behavior. `PublicReadTransport` now rejects
those defaults, revalidates client state for each call, pins anonymous GETs to
configured timeouts with redirects disabled, and clears response cookies while
serializing requests. The request method remains GET-only.

The current source tree passes `tests/frontier` **430/430** in 28.96 seconds.
Focused tests pass for transport **15/15**, adapters plus Coinbase **84/84**,
collection **27/27**, and the corrected Reality schedule module **4/4**. Peak
RSS for those respective focused runs was 56,888 KiB, 79,156 KiB, 70,400 KiB,
and 163,236 KiB; all reported zero swaps and zero socket messages. Strict mypy
reports no issues in the changed collection and transport modules. Ruff check,
Ruff format, and whitespace checks pass. The Frontier suite emitted one
existing Starlette/httpx `TestClient` deprecation warning.

Full-suite pre/post samples at `12:25:36Z` and `12:26:13Z` showed memory and
I/O PSI avg10 at **0.00%** and about **10 GiB** available. Tests used a tmpfs
basetemp. No external source, production service, or protected store was
accessed. Live cross-venue equivalence remains blocked by source-use holds and
the held-capture boundary. Frontier remains **PARTIALLY VERIFIED** and
undeployed; broader legacy/browser regression and deployment readiness remain
open.

| Requirement | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Exchange-independent read transport security | COMPLETE AND VERIFIED | No-auth/no-redirect/client-state regressions; 15 transport, 84 adapter, and 430 full Frontier tests pass; strict mypy passes. |
| Atomic finite collection startup | COMPLETE AND VERIFIED | One SQLite transaction for run plus sequence-zero checkpoint; rollback regression and collection lifecycle module pass. |
| Frontier Python suite | COMPLETE AND VERIFIED | 430/430 on exact current source tree. |
| Broader MIDAS regression | PARTIALLY VERIFIED | Selected legacy slices pass; other legacy modules and browser acceptance remain. |
| Genuine cross-venue validation | BLOCKED | No authorized genuine multi-venue relationship or eligible economic result established. |
| Production deployment | DEFERRED | Frontier remains isolated; no deployment was performed. |

## Resource admission recheck — 2026-10-28 12:20 UTC

At `12:20:05Z`, memory PSI avg10 was **36.90% some / 27.21% full** while
I/O PSI avg10 was **0.29% some / 0.00% full**. About **10 GiB** was available;
**3.5/4 GiB** swap was in use. No runtime verification started. The pending
collection and research-schedule tests remain queued behind the memory gate.

## Memory-gated validation — 2026-10-28 12:18 UTC

The last sample at `12:18:47Z` showed I/O PSI avg10 **0.01% some / 0.01%
full**, but memory PSI avg10 **36.13% some / 31.37% full**. Available memory
was about **10 GiB**, with **3.5/4 GiB** swap occupied. No tests, build, or
type-check ran. The 420/420 Frontier result is prior-tree evidence; current
collection and schedule fixture changes still need runtime verification after
both PSI avg10 values fall below the 1% gate.

## Atomic collection startup persistence — 2026-10-28 12:16 UTC

Commit `36546cd` fixes a crash window in finite collection startup. The run
specification and initial `created` checkpoint now commit in one SQLite
transaction. A failure to append the checkpoint rolls back the run record, and
no source request starts before that transaction commits. The regression
injects a temporary database trigger failure and checks that neither row
remains; the success-path collection test checks that sequence zero is
`created`.

Ruff check, Ruff format check, and `git diff --check` pass. Runtime tests and
strict typing are pending. At `12:16:41Z`, memory PSI avg10 was **25.94% some /
18.04% full**, I/O PSI was **4.83% some / 3.18% full**, about **10 GiB** was
available, and host swap was **3.5/4 GiB** used. No test, source request,
service action, or protected-store operation ran under this sample. The
untracked public-capture directory remains untouched.

| Requirement | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Atomic collection run/checkpoint creation | IMPLEMENTED, VALIDATION PENDING | `36546cd`; rollback and success-path regressions are added but not yet run. |
| Exact current Frontier suite | PARTIALLY VERIFIED | The 420/420 result at 11:55 UTC predates later collection and fixture changes; rerun after resource admission. |
| Strict mypy on collection startup | DEFERRED | Run on the exact current tree after the host gate clears. |
| Frontier overall | PARTIALLY VERIFIED | Genuine cross-venue research evidence, full legacy/browser acceptance, production recovery, and deployment remain open. |

## Broader MIDAS verification gate — 2026-10-28 11:57 UTC

The exact Frontier suite and strict mypy are verified as recorded below. A
repository-wide MIDAS regression was not started: at `11:57:28Z`, memory PSI
avg10 was **39.00% some / 35.46% full**, I/O PSI was **0.93% some / 0.93%
full**, and about **10 GiB** was available. A read-only test-source scan also
found legacy tests that reference `/home/charlie/midas/data/laboratory-final`
and tests that launch subprocesses or local servers. Review those test roots
before a broad invocation so it cannot touch preserved operational data. No
legacy test, protected service, or research artifact was touched.

| Requirement | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Frontier Python suite | COMPLETE AND VERIFIED | 420/420 on current tree, with measured bounded resource use. |
| Repository-wide MIDAS regression | DEFERRED | Current host memory PSI exceeds 1%; test roots and subprocess cases need a bounded isolation review. |
| Frontier overall | PARTIALLY VERIFIED | Browser/legacy checks, live cross-venue evidence, and deployment remain open. |

## Current status — 2026-10-28 11:55 UTC

Strict mypy passes on the current API guard, base adapter, and Coinbase adapter:
`apps/api/frontier.py`, `packages/midas/frontier/adapters/base.py`, and
`packages/midas/frontier/adapters/coinbase.py` report **no issues in 3 source
files**. The exact current `tests/frontier` tree then passed **420/420** in
**29.02 seconds** (30.50 s wall). Peak RSS was **378,276 KiB**, with zero
swaps, zero filesystem input, 912 filesystem-output blocks, and zero socket
messages. One existing Starlette/httpx `TestClient` deprecation warning
remains.

The pre-run sample at `11:55:04Z` showed memory PSI avg10 **0.00%**, I/O PSI
**0.85% some / 0.70% full**, and about **10 GiB** available. After the run at
`11:55:41Z`, memory PSI remained **0.00%**, I/O was **0.91% some / 0.63%
full**, and about **10 GiB** remained available. The test process used no swap.
This closes the earlier type-narrowing rerun; the API guard’s exact current
tree is both type-checked and fully covered by `tests/frontier`.

| Requirement | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Coinbase source-use hold | COMPLETE AND VERIFIED | Source-specific config, adapter, transport, and API checks pass in the full current suite. |
| API source-use hold | COMPLETE AND VERIFIED | All 11 probe routes reject held config before work; source status reports effective eligibility; strict mypy and 420 tests pass. |
| Full Frontier Python suite | COMPLETE AND VERIFIED | 420/420 on current code; 29.02 s, 378,276 KiB peak RSS, zero swaps and filesystem input. |
| Cross-venue live semantic/economic validation | BLOCKED | Current terms and held-capture restrictions remain; fixtures do not establish live equivalence. |
| Full Frontier project | PARTIALLY VERIFIED | Broader MIDAS/browser gates, genuine cross-venue evidence, and deployment remain separate open criteria. |

## Current status — 2026-10-28 11:53 UTC

Commits `782df89`, `9776427`, and `4b8c9f0` complete the source-use hold path:
all 11 public probe routes reject held source configs before adapter work,
source listings report effective probe eligibility, and the guard returns the
validated config for route use. The Coinbase API regression checks HTTP 409,
the held reason, disabled effective status, and zero transport requests.

The Coinbase module passed **13/13** on the immediately preceding guard
implementation. Four affected Kalshi/Coinbase collection cases passed **4/4**.
The full Frontier suite then passed **420/420** in **28.88 seconds** (30.30 s
wall), with **378,920 KiB** peak RSS, zero swaps, zero filesystem input, 368
filesystem-output blocks, and zero socket messages. Pre-run PSI at
`11:51:24Z` was memory **0.00%**, I/O **0.76% some / 0.73% full**; post-run
at `11:52:02Z`, memory remained **0.00%**, I/O was **0.52%**, and about
**10 GiB** was available. The run emitted one existing Starlette/httpx
deprecation warning.

The full run preceded the final `4b8c9f0` refactor from a boolean guard to a
guard that returns the validated config. That refactor preserves the runtime
condition and addresses strict-mypy union-attribute errors found in the prior
check, but strict mypy and tests have not yet been rerun against that exact
commit. Ruff check/format and `git diff --check` pass on the current tree.

At `11:53:54Z`, memory PSI avg10 rose to **1.16% some / 1.02% full**, I/O PSI
was **0.91% some / 0.83% full**, about **10 GiB** was available, and host swap
was **3.5/4 GiB** used. The memory gate is exceeded; no further tests or mypy
run started under that sample. Frontier remains **PARTIALLY VERIFIED**.

| Requirement | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Coinbase source-use hold | COMPLETE AND VERIFIED | `ca14e37`; direct/copy/type/transport guards pass in the 13-case module on the pre-`4b8c9f0` tree. |
| API source-use hold | IMPLEMENTED, LIVE VALIDATION PENDING | `782df89`, `9776427`, `4b8c9f0`; 420 tests pass before the final type-narrowing refactor; exact-tree checks pending. |
| Strict mypy on API guard | PARTIALLY VERIFIED | The first run exposed 13 union-attribute errors; `4b8c9f0` returns the validated config, but rerun awaits resource admission. |
| Frontier overall | PARTIALLY VERIFIED | Live cross-venue evidence, broader MIDAS/browser checks, and deployment remain open. |

## Current status — 2026-10-28 11:48 UTC

Commit `782df89` adds an API-level source-use hold preflight to all 11 bounded
probe routes, before locks, reads, or adapter calls. The Coinbase API regression
now expects HTTP 409 and zero transport requests while the source remains held.
Ruff check/format and `git diff --check` pass for the API changes.

The first focused Coinbase run was on the tree before this API fix: **12 passed,
1 failed** in 1.28 seconds, with **78,636 KiB** maximum RSS and zero swaps. The
failure was the old success-path API test trying to read quarantined Coinbase
records after a test-only fixture transport had returned success. That run
made no real network request. The pre-run sample at `11:46:30Z` had memory PSI
avg10 **0.00%**, I/O PSI **0.41%**, and about **10 GiB** available. At
`11:46:51Z`, I/O PSI rose to **1.19%**; at `11:47:55Z`, memory PSI avg10 rose
to **52.19% some / 46.63% full** and I/O PSI was **1.10% some / 0.75% full**.
The current regression has not been rerun; the resource gate is exceeded.

| Requirement | Status | Evidence and remaining boundary |
| --- | --- | --- |
| API source-use hold enforcement | IMPLEMENTED, LIVE VALIDATION PENDING | `782df89` checks all 11 probe routes; focused post-fix test awaits a fresh admitted sample. |
| Coinbase source-use hold model | IMPLEMENTED, LIVE VALIDATION PENDING | `ca14e37`; static checks pass, current tests pending. |
| Frontier overall | PARTIALLY VERIFIED | The 418/418 result predates these changes; cross-venue evidence, current regression, broader MIDAS checks, and deployment remain open. |

## Current status — 2026-10-28 11:46 UTC

This entry supersedes the 11:44 UTC status. Follow-up commit `92b5bf0` aligns
the Kraken adapter fixture so its `PublicReadTransport` receives the same
source-specific `KrakenSpotConfig` as the adapter, preserving the newly
enforced config-match invariant. Ruff check/format and `git diff --check` pass
for the changed Python files. Tests remain unrun under the memory PSI gate
recorded below. The report and ledger inventory include both `ca14e37` and
`92b5bf0`; no source, production service, or protected store was touched.

## Current status — 2026-10-28 11:44 UTC

Code commit `ca14e37` closes Coinbase source-use hold bypasses found during
review of the pending copied-config regression. `CoinbaseSpotConfig` can no
longer clear the hold with an exact terms acknowledgement alone. The adapter
requires the exact Coinbase config type, and `BaseReadOnlyAdapter` rejects an
injected transport whose concrete config type or value differs. Offline parser
and API fixture tests now use a test-only in-memory transport while retaining a
held config. Regression coverage includes copied configs with and without the
exact acknowledgement, generic config substitution, and mismatched transport
configuration.

Ruff check, Ruff format check, and `git diff --check` pass. The Coinbase tests
have **not run**. At `11:43:51Z`, memory PSI avg10 was **6.41% some / 5.82%
full**, I/O PSI was **0.59% some / 0.45% full**, about **10 GiB** was available,
and host swap was **3.5/4 GiB** used. The previously observed PID 344473 was no
longer present. The memory PSI admission gate remains exceeded; no tests,
replay, source probe, protected service, or deployment action was attempted.

The **418/418** Frontier result remains evidence for product commit `1dd0987`,
before `ca14e37` and the added regressions. Frontier remains
**PARTIALLY VERIFIED** until the focused test and current full suite pass under
an admitted host sample.

| Requirement | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Coinbase source-use hold enforcement | IMPLEMENTED, LIVE VALIDATION PENDING | `ca14e37`; config, adapter, and transport mismatch guards plus offline regressions; tests await memory PSI below 1%. |
| Adapter resource-bound validation | COMPLETE AND VERIFIED | Product code and 418 existing Frontier tests pass on `1dd0987`. |
| Genuine cross-venue validation | BLOCKED | Held source permission/evidence boundary remains. |
| Frontier overall | PARTIALLY VERIFIED | New regressions, broader MIDAS checks, live evidence, and deployment remain open. |

## Current status — 2026-10-28 11:38 UTC

This entry supersedes the 11:35 UTC checkpoint. Test commit `c6dfff1` adds a
Coinbase-specific source-use hold regression: a copied config that removes the
terms block without the reviewed acknowledgement must be rejected before
adapter or transport setup. Ruff and `git diff --check` pass. The new test has
not run because the host resource gate is currently exceeded.

At `11:38:45Z`, memory PSI avg10 was **35.09% some / 29.50% full**, I/O PSI
was **3.88% some / 3.67% full**, about **10 GiB** was available, and host
swap was 3.4/4 GiB used. Read-only inspection found an existing
`veritas_gap_detail_v2_batch.py` process (PID 344473) in D state; it was not
interrupted or modified. No test, replay, source probe, protected service, or
deployment action was performed under the measured pressure.

The existing **418/418** full Frontier run is for product commit `1dd0987`
before this test-only commit. It remains evidence for the unchanged product
code but does not cover the newly added Coinbase regression or represent a
full run of the latest test tree. Frontier remains **PARTIALLY VERIFIED**.

| Requirement | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Adapter resource-bound validation | COMPLETE AND VERIFIED | Product code rejects copied invalid limits; 418 existing Frontier tests pass on `1dd0987`. |
| Coinbase copied-config terms hold | PARTIALLY VERIFIED | Regression committed and linted, not executed due memory and I/O PSI exceeding the admission gate. |
| Genuine cross-venue validation | BLOCKED | No authorized genuine multi-venue evidence is available. |
| Production recovery and deployment | DEFERRED | Research worktree remains isolated, unmerged, and undeployed. |
| Frontier overall | PARTIALLY VERIFIED | Latest test-tree regression, broader MIDAS tests, live evidence, and deployment remain open. |

## Current status — 2026-10-28 11:35 UTC

This entry supersedes the 11:31 UTC checkpoint. Code commit `1dd0987`
revalidates adapter configurations before use. A copied `AdapterConfig` with
a one-billion-byte response cap previously bypassed its Pydantic bounds and
was accepted by `PublicReadTransport`. The concrete adapter config type is
now reconstructed so subclass allowlists and Coinbase terms validation also
rerun. Both `BaseReadOnlyAdapter` and `PublicReadTransport` reject a malformed
copy before using it or constructing an HTTP client.

The adapter module passed **71/71** and collection plus collection-API modules
passed **34/34**. Full `tests/frontier` passed **418/418** in 30.09 seconds
(31.53 seconds wall time), with **379,004 KiB** peak RSS, zero process swaps,
zero filesystem input, 392 output blocks, and zero socket messages. Ruff
check/format, strict mypy for nine production modules, and `git diff --check`
passed. One existing Starlette/httpx `TestClient` deprecation warning
remains. The full run used tmpfs at
`/dev/shm/midas-frontier-adapter-config-full-20261028T1135Z`.

Before the full run at `11:34:58Z`, memory PSI avg10 was **0.00%**, I/O PSI
was **0.66% some / 0.45% full**, and about **10 GiB** was available. At
`11:35:49Z`, memory PSI avg10 remained **0.00%**, I/O PSI was **0.57% some /
0.47% full**, and about **10 GiB** remained available. Host swap was already
3.4/4 GiB used; the test process used none. No live source, protected
capture, production service, collector, or Arena job was used. Frontier
remains **PARTIALLY VERIFIED**.

| Requirement | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Adapter resource-bound validation | COMPLETE AND VERIFIED | Invalid copied limits are rejected before transport setup; adapter and collection tests pass. |
| Full Frontier Python regression | COMPLETE AND VERIFIED | 418/418 pass on code commit `1dd0987`; one existing deprecation warning remains. |
| Genuine cross-venue equivalence and economics | BLOCKED | No authorized genuine multi-venue evidence is available. |
| Broader MIDAS regression | PARTIALLY VERIFIED | Not run on this branch; Reality recovery dependency and incompatible Reality lineages remain unresolved. |
| Production recovery and deployment | DEFERRED | The research worktree remains isolated, unmerged, and undeployed. |
| Frontier overall | PARTIALLY VERIFIED | Live science, broader regression, and production readiness remain open. |

## Current status — 2026-10-28 11:31 UTC

This entry supersedes the 11:24 UTC checkpoint. Frontier remains isolated at
`/home/charlie/midas-frontier` on `codex/frontier-20261026`. Code commit
`e26efab` closes a virtual-assumption integrity gap: a copied execution
scenario with `fill_fraction=2` previously generated quantity-20 positions
against displayed depth 10 and the independent audit classified both as
verified.

`ExecutionScenario.has_valid_structure` now reparses the complete scenario.
Candidate generators, joint-state generation, replay, paired replay,
event-time replay, and discovery-scope comparison reject malformed scenario
copies. Direct independent audit returns incomplete evidence and clears
practical eligibility. The change is pinned by economic model v21, audit v21,
replay v20, timeline v2, and discovery-comparison v2.

Five affected test modules passed **100/100**. Full `tests/frontier` passed
**417/417** in 30.54 seconds (32.02 seconds wall time), with **380,336 KiB**
peak RSS, zero process swaps, zero filesystem input, 1,872 output blocks, and
zero socket messages. Ruff check/format, strict mypy for seven production
modules, and `git diff --check` passed. One existing Starlette/httpx
`TestClient` deprecation warning remains. Tests used tmpfs at
`/dev/shm/midas-frontier-scenario-integrity-full-20261028T1131Z`.

Before the run, memory PSI avg10 was **0.00%**, I/O PSI was **0.33% some /
0.16% full**, and about **10 GiB** was available. At `11:31:38Z`, memory PSI
avg10 remained **0.00%**, I/O PSI was **0.72% some / 0.71% full**, and about
**10 GiB** remained available. Host swap was already 3.4/4 GiB used; the test
process used none. No public source, protected capture, production service,
worker, or Arena job was used. The untracked public-probe directory remains
untouched.

| Requirement | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Copied execution-assumption integrity | COMPLETE AND VERIFIED | A fill fraction above one cannot scale book depth or pass as verified at audit/replay boundaries. |
| Full Frontier Python regression | COMPLETE AND VERIFIED | 417/417 pass on code commit `e26efab`; one existing deprecation warning remains. |
| Genuine cross-venue equivalence and economics | BLOCKED | No authorized genuine multi-venue evidence is available. |
| Broader MIDAS regression | PARTIALLY VERIFIED | Not run on this branch; Reality recovery dependency and incompatible Reality lineages remain unresolved. |
| Production recovery and deployment | DEFERRED | The research worktree remains isolated, unmerged, and undeployed. |
| Frontier overall | PARTIALLY VERIFIED | Live science, broader regression, and production readiness remain open. |

## Current status — 2026-10-28 11:24 UTC

This entry supersedes the 11:21 UTC checkpoint below. Frontier remains
isolated at `/home/charlie/midas-frontier` on `codex/frontier-20261026`.
Code commit `ac85442` extends copied-input validation to the full order-book
snapshot. A naive copied `received_at_utc` previously passed the level-only
check and raised `TypeError` during replay time arithmetic.

`BookSnapshot.has_valid_structure` now reconstructs the snapshot through
Pydantic validation, including top-level receipt/exchange times and nested
provenance. Candidate generators and independent audit use the same check;
deterministic replay applies it before calculating the default analysis
cutoff. A copied naive timestamp is rejected at intake. Economic model v20,
audit v20, and replay v19 identify the changed rules.

The focused book-integrity slice passed **10/10**. Full `tests/frontier`
passed **415/415** in 30.80 seconds (32.27 seconds wall time), with
**378,208 KiB** peak RSS, zero process swaps, zero filesystem input, 1,856
output blocks, and zero socket messages. Ruff check/format, strict mypy for
five production modules, and `git diff --check` passed. One existing
Starlette/httpx `TestClient` deprecation warning remains. Tests used tmpfs at
`/dev/shm/midas-frontier-book-structure-final-20261028T1124Z`.

At `11:24:07Z`, about 10 GiB was available, memory PSI avg10 was 0%, and I/O
PSI was 0.29% some / 0.05% full. At `11:24:44Z`, about 10 GiB remained
available, memory PSI avg10 was 0%, and I/O PSI was 0.32% some / 0% full. No
live source, protected capture, production service, or Arena job was used; the
saved public capture remains unstaged and untouched. Frontier remains
**PARTIALLY VERIFIED**.

### Latest acceptance delta

| Requirement | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Copied book snapshot structure | COMPLETE AND VERIFIED | Full book and provenance validation runs at generation, audit, and replay boundaries; malformed copied timestamps fail before time arithmetic. |
| Full Frontier Python regression | COMPLETE AND VERIFIED | 415/415 pass on code commit `ac85442`; one existing deprecation warning remains. |
| Live cross-venue equivalence and economics | BLOCKED | No authorized genuine multi-venue evidence is available for this checkpoint. |
| Broader MIDAS regression | PARTIALLY VERIFIED | Not run on this branch; Reality recovery dependency and incompatible Reality lineages remain unresolved. |
| Production recovery and deployment | DEFERRED | The research worktree remains isolated, unmerged, and undeployed. |
| Frontier overall | PARTIALLY VERIFIED | Live science, broader regression, and production readiness remain open. |

## Previous checkpoint — 2026-10-28 11:21 UTC

This entry supersedes the 11:15 UTC checkpoint below. Frontier remains
isolated at `/home/charlie/midas-frontier` on `codex/frontier-20261026`.
Code commit `da347a4` closes a copied nested-market integrity gap found with
a fixture that duplicated an instrument's native ID. The multi-outcome
generator previously reached fill-sensitivity construction and raised
`ValueError` because it treated duplicate contract identities as separate
legs.

`FrontierMarket.has_valid_structure` now rebuilds the complete market payload
through Pydantic validation at candidate generation, independent audit, and
replay boundaries. Malformed copied markets produce incomplete candidate or
audit evidence, or are rejected at replay intake. This includes nested
instrument, payout, payoff, and settlement rules. Economic model v19, audit
v19, and replay v18 pin the change.

The first full run after the implementation had **412 passed and 2 failed**;
both failures asserted narrower diagnostic text than the new structural gate,
and the run also exposed a serializer warning from a copied field. Those
assertions now expect the structural rejection, and the validation-only dump
suppresses serializer warnings. Focused corrections passed **3/3**. The final
full `tests/frontier` run passed **414/414** in 29.94 seconds (31.40 seconds
wall time), with **377,768 KiB** peak RSS, zero process swaps, zero filesystem
input, 376 output blocks, and zero socket messages. Ruff check/format, strict
mypy for five production modules, and `git diff --check` passed. One existing
Starlette/httpx `TestClient` deprecation warning remains. Tests used tmpfs at
`/dev/shm/midas-frontier-market-copy-final2-20261028T1121Z`.

At `11:20:51Z`, about 10 GiB was available, memory PSI avg10 was 0%, and I/O
PSI was 0.34% some / 0% full. At `11:21:37Z`, about 10 GiB remained available,
memory PSI avg10 was 0%, and I/O PSI was 0.64% some / 0.44% full. No live
source, protected capture, production service, or Arena job was used; the
saved public capture remains unstaged and untouched. Frontier remains
**PARTIALLY VERIFIED**.

### Latest acceptance delta

| Requirement | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Copied market contract structure | COMPLETE AND VERIFIED | Nested validators rerun at candidate, audit, and replay boundaries; malformed duplicate instrument identity fails closed. |
| Full Frontier Python regression | COMPLETE AND VERIFIED | 414/414 pass on code commit `da347a4`; one existing deprecation warning remains. |
| Live cross-venue equivalence and economics | BLOCKED | No authorized genuine multi-venue evidence is available for this checkpoint. |
| Broader MIDAS regression | PARTIALLY VERIFIED | Not run on this branch; Reality recovery dependency and incompatible Reality lineages remain unresolved. |
| Production recovery and deployment | DEFERRED | The research worktree remains isolated, unmerged, and undeployed. |
| Frontier overall | PARTIALLY VERIFIED | Live science, broader regression, and production readiness remain open. |

## Previous checkpoint — 2026-10-28 11:15 UTC

This entry supersedes the 11:12 UTC checkpoint below. Frontier remains
isolated at `/home/charlie/midas-frontier` on `codex/frontier-20261026`.
Code commit `1f6bd64` closes a content-identity gap in conditional joint-state
analysis. A copied map could change its external assertion payload while
retaining the prior content hash; a fixture produced three conditional
candidates and an independently `verified` candidate audit before the fix.

`JointStateMap.content_identity_matches` now reconstructs and revalidates the
bounded definition before hashing. Candidate generation refuses stale map
identities, the independent audit classifies them as incomplete evidence, and
replay rejects them at intake. This protects the mapping's content address; a
correct hash still does not authenticate the external assertion or prove that
the listed joint states are exhaustive or attainable. Economic model v18,
audit v18, and replay v17 identify the changed rules.

The new stale-identity regression confirms all three boundaries. The focused
joint-state module passed **11/11**. Full `tests/frontier` passed **413/413**
in 30.79 seconds (32.26 seconds wall time), with **379,304 KiB** peak RSS,
zero process swaps, zero filesystem input, 2,688 output blocks, and zero
socket messages. Ruff check/format, strict mypy for five production modules,
and `git diff --check` passed. One existing Starlette/httpx `TestClient`
deprecation warning remains. The suite used tmpfs at
`/dev/shm/midas-frontier-joint-map-final-20261028T1115Z`.

At `11:14:51Z`, about 10 GiB was available, memory PSI avg10 was 0%, and I/O
PSI avg10 was 0%. At `11:15:29Z`, about 10 GiB remained available, memory PSI
avg10 was 0%, and I/O PSI was 0.03% some / 0% full. No live source, protected
capture, production service, or Arena job was used; the saved public capture
remains unstaged and untouched. Frontier remains **PARTIALLY VERIFIED**.

### Latest acceptance delta

| Requirement | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Joint-state map content identity | COMPLETE AND VERIFIED | Stale copied IDs are rejected at generation and replay, and make existing candidate audits incomplete; semantics remain unauthenticated. |
| Full Frontier Python regression | COMPLETE AND VERIFIED | 413/413 pass on code commit `1f6bd64`; one existing deprecation warning remains. |
| Live cross-venue equivalence and economics | BLOCKED | No authorized genuine multi-venue evidence is available for this checkpoint. |
| Broader MIDAS regression | PARTIALLY VERIFIED | Not run on this branch; Reality recovery dependency and incompatible Reality lineages remain unresolved. |
| Production recovery and deployment | DEFERRED | The research worktree remains isolated, unmerged, and undeployed. |
| Frontier overall | PARTIALLY VERIFIED | Live science, broader regression, and production readiness remain open. |

## Previous checkpoint — 2026-10-28 11:12 UTC

This entry supersedes the 11:04 UTC checkpoint below. Frontier remains
isolated at `/home/charlie/midas-frontier` on `codex/frontier-20261026`.
Code commit `435153d` closes a copied-book integrity gap: direct
`model_copy(update=...)` could bypass the constructor's unique-price-level
validator and make a duplicate best ask appear to provide inflated depth.

`BookSnapshot.has_valid_price_levels` now rechecks level type, unique prices,
finite nonnegative prices, finite positive quantities, and aware optional
level timestamps at each decisive boundary. Cross-venue, single-market,
bounded-payoff, and joint-state generators reject malformed books; the
independent audit classifies a selected malformed book as incomplete; replay
rejects it before candidate generation. Economic model v17, audit v17, and
replay v16 pin these acceptance changes. Existing stored model rows remain
readable.

Focused adversarial regressions passed **8/8**. An initial local run of the
five copied-level cases used a nonexistent fixture instrument ID; the test
setup was corrected to select the normalized fixture instrument and passed on
rerun. The final full `tests/frontier` suite passed **412/412** in 29.83
seconds (31.33 seconds wall time), with **378,608 KiB** peak RSS, zero process
swaps, zero filesystem input, 376 output blocks, and zero socket messages.
Ruff check/format, strict mypy for five production modules, and
`git diff --check` passed. One existing Starlette/httpx `TestClient`
deprecation warning remains. Tests used tmpfs at
`/dev/shm/midas-frontier-book-depth-final-20261028T1112Z`.

At `11:10:34Z`, about 10 GiB was available, memory PSI avg10 was 0%, and I/O
PSI was 0.06% some / 0.01% full. At `11:12:10Z`, about 10 GiB remained
available, memory PSI avg10 was 0%, and I/O PSI was 0.12% some / 0% full.
No live source, protected capture, production service, or Arena job was used;
the existing public capture remains unstaged and untouched. Frontier remains
**PARTIALLY VERIFIED**.

### Latest acceptance delta

| Requirement | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Copied book-level integrity | COMPLETE AND VERIFIED | Candidate generation, independent audit, and replay reject duplicate or otherwise invalid levels; adversarial fixtures cover inflated depth and copied malformed values. |
| Full Frontier Python regression | COMPLETE AND VERIFIED | 412/412 pass on code commit `435153d`; one existing deprecation warning remains. |
| Live cross-venue equivalence and economics | BLOCKED | No authorized genuine multi-venue evidence is available for this checkpoint. |
| Broader MIDAS regression | PARTIALLY VERIFIED | Not run on this branch; Reality recovery dependency and incompatible Reality lineages remain unresolved. |
| Production recovery and deployment | DEFERRED | The research worktree remains isolated, unmerged, and undeployed. |
| Frontier overall | PARTIALLY VERIFIED | Live science, broader regression, and production readiness remain open. |

## Previous checkpoint — 2026-10-28 11:04 UTC

This entry supersedes the 11:02 UTC checkpoint below. Frontier remains
isolated at `/home/charlie/midas-frontier` on `codex/frontier-20261026`. Test
commit `d44bab0` adds an API-to-store regression for duplicate-key responses;
code commit `0dbea9c` supplies the strict parser.

The bounded API regression now exercises the full failure-evidence path: a
response containing duplicate JSON keys returns HTTP 502 with
`DUPLICATE_JSON_KEY`, preserves its exact raw body in an append-only
`source_failure` observation, and serves that observation through the
hash-verified evidence endpoint with the failure stage and code intact. The
duplicate remains excluded from normalized market rows. This closes the gap
between the earlier transport-level test and persisted source provenance.

Full `tests/frontier` passes **404/404** in 29.66 seconds (31.12 seconds wall
time); `/usr/bin/time -v` measured **378,492 KiB** peak RSS, zero process
swaps, zero filesystem input, and 360 output blocks. One existing
Starlette/httpx `TestClient` deprecation warning remains. Ruff check/format,
strict mypy for six changed production modules, and `git diff --check` pass.
The suite used tmpfs at
`/dev/shm/midas-frontier-json-storage-final-20261028T1103Z`.

At `11:03:02Z`, memory and I/O PSI avg10 were 0% and about 10 GiB was
available; host swap remained 3.5/4 GiB used. At `11:03:37Z`, memory PSI was
0%, I/O PSI was 0.03% some / 0% full, about 10 GiB was available, and the test
process reported zero swaps. No live source, protected capture, production
service, or Arena job was used. Frontier remains **PARTIALLY VERIFIED**; live
multi-venue validation, broader MIDAS regression, production recovery, and
deployment remain open.

### Latest acceptance delta

| Requirement | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Duplicate-key source failure provenance | COMPLETE AND VERIFIED | API returns classified error, persists exact bounded raw body, and exposes hash-verified evidence. |
| Full Frontier Python regression | COMPLETE AND VERIFIED | 404/404 pass on the exact test commit; one existing deprecation warning remains. |
| Live cross-venue equivalence and economics | BLOCKED | No authorized genuine multi-venue evidence is available for this checkpoint. |
| Broader MIDAS regression | PARTIALLY VERIFIED | Not run on this branch; Reality recovery dependency and incompatible Reality lineages remain unresolved. |
| Production recovery and deployment | DEFERRED | The research worktree remains isolated, unmerged, and undeployed. |
| Frontier overall | PARTIALLY VERIFIED | Live science, broader regression, and production readiness remain open. |

## Current status — 2026-10-28 11:02 UTC

This entry supersedes the 10:59 UTC checkpoint below. Frontier remains
isolated at `/home/charlie/midas-frontier` on `codex/frontier-20261026`; code
commit `ff522e9` is the latest implementation checkpoint.

The logical-implication version gate now has a matching economic-model
version. Commit `ff522e9` advances the candidate and replay model from v15 to
v16 and adds a regression showing that a stored v2 implication edge remains
readable but yields incomplete evidence until it is re-reviewed under
verifier v3. This makes the changed acceptance rule explicit in candidate and
replay identities.

The focused logical-implication economics suite passes **7/7**. Full
`tests/frontier` passes **404/404** in 29.74 seconds (31.22 seconds wall time);
`/usr/bin/time -v` measured **385,644 KiB** peak RSS, zero process swaps, zero
filesystem input, and 1,176 output blocks. One existing Starlette/httpx
`TestClient` deprecation warning remains. Ruff check/format, strict mypy for
six changed production modules, and `git diff --check` pass. The run used
tmpfs at `/dev/shm/midas-frontier-final-review-20261028T1101Z`.

At the pre-run sample (`11:01:11Z`), memory PSI avg10 was 0%, I/O PSI avg10
was 0%, and about 10 GiB was available; host swap remained 3.5/4 GiB occupied.
At `11:01:46Z`, memory PSI avg10 was 0%, I/O PSI avg10 was 0.01% some / 0%
full, about 10 GiB was available, and the test process reported zero swaps.
No live source, protected capture, production service, or Arena job was used.
The public Polymarket capture remains untouched. Frontier remains
**PARTIALLY VERIFIED**; genuine multi-venue validation, broader MIDAS
regression, production recovery, and deployment remain open.

### Latest acceptance delta

| Requirement | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Logical implication version and replay identity | COMPLETE AND VERIFIED | Economic model v16 pins current implication verifier v3; old v2 evidence remains incomplete until re-reviewed. |
| Full Frontier Python regression | COMPLETE AND VERIFIED | 404/404 pass on the exact code commit; one existing deprecation warning remains. |
| Source parsing and replay input integrity | COMPLETE AND VERIFIED | Duplicate JSON keys and duplicate relationship IDs are rejected with bounded evidence/identity rules. |
| Live cross-venue equivalence and economics | BLOCKED | No authorized genuine multi-venue evidence is available for this checkpoint. |
| Broader MIDAS regression | PARTIALLY VERIFIED | Not run on this branch; Reality recovery dependency and incompatible Reality lineages remain unresolved. |
| Production recovery and deployment | DEFERRED | The research worktree remains isolated, unmerged, and undeployed. |
| Frontier overall | PARTIALLY VERIFIED | Live science, broader regression, and production readiness remain open. |

## Current status — 2026-10-28 10:59 UTC

This entry supersedes the 10:56 UTC checkpoint below. Frontier remains
isolated at `/home/charlie/midas-frontier` on `codex/frontier-20261026`. Code
commit `63c2d74` rejects duplicate replay relationships; `0dbea9c` is the
latest code commit and rejects duplicate JSON object keys in source responses.

A controlled replay that supplied the same relationship twice previously
returned two candidates with one distinct candidate ID. Replay now rejects
duplicate relationship identities before candidate generation. A bounded
`httpx.MockTransport` reproduction showed standard JSON decoding silently
kept the last duplicate field value. `PublicReadTransport` now rejects
duplicate keys at every object depth as `DUPLICATE_JSON_KEY` and preserves the
complete bounded response body in failure evidence, preventing ambiguous data
from reaching normalization.

The focused replay regression passed **1/1** and duplicate-key parser cases
passed **2/2**. Full `tests/frontier` passes **403/403** in 29.47 seconds
(30.92 seconds wall time); `/usr/bin/time -v` measured **376,780 KiB** peak
RSS, zero process swaps, zero filesystem input, and 376 output blocks. The
existing Starlette/httpx `TestClient` deprecation warning remains. Ruff
check/format, strict mypy for the changed production modules, and
`git diff --check` pass. The run used tmpfs at
`/dev/shm/midas-frontier-duplicate-inputs-20261028T1058Z`.

At the pre-run sample (`10:58:31Z`), memory and I/O PSI avg10 were 0%, about
10 GiB was available, and host swap remained 3.5/4 GiB occupied. At
`10:59:07Z`, PSI avg10 remained 0%, about 10 GiB was available, and the test
process reported zero swaps. No live source, protected capture, production
service, or Arena job was used. The preserved public capture remains
unmodified. Frontier remains **PARTIALLY VERIFIED**; live multi-venue evidence,
broader MIDAS regression, production recovery, and deployment remain open.

### Latest acceptance delta

| Requirement | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Duplicate relationship replay inputs | COMPLETE AND VERIFIED | Replay rejects duplicate IDs; controlled reproduction previously emitted duplicate candidate identities. |
| Ambiguous duplicate-key source JSON | COMPLETE AND VERIFIED | Parser rejects top-level and nested duplicate keys and retains raw bounded response evidence. |
| Full Frontier Python regression | COMPLETE AND VERIFIED | 403/403 pass on the exact code tree; one existing deprecation warning remains. |
| Live cross-venue equivalence and economics | BLOCKED | No authorized genuine multi-venue evidence is available for this checkpoint. |
| Broader MIDAS regression | PARTIALLY VERIFIED | Not run on this branch; Reality recovery dependency and incompatible Reality lineages remain unresolved. |
| Production recovery and deployment | DEFERRED | The research worktree remains isolated, unmerged, and undeployed. |
| Frontier overall | PARTIALLY VERIFIED | Live science, broader regression, and production readiness remain open. |

## Current status — 2026-10-28 10:56 UTC

This entry supersedes the 10:52 UTC checkpoint below. Frontier remains
isolated at `/home/charlie/midas-frontier` on `codex/frontier-20261026`; code
commit `3097082` is the latest implementation checkpoint.

A read-only follow-on audit found that `verify_logical_implication` could mark
a copied market VERIFIED when its payoff state list or native instrument IDs
contained duplicates. The independent audit already rejected those malformed
markets, but relationship state itself was too permissive. Logical verifier v3
now rejects duplicate payoff states and native instrument identities, and
explicitly checks outcome identity uniqueness. Independent audit v16 requires
current v3 evidence; older v2 relationships stay readable but cannot support
a newly audited logical-implication candidate without review.

The malformed-market regression passed in the focused relationship and
implication suites (**70/70**). Full `tests/frontier` passes **400/400** in
29.65 seconds (31.11 seconds wall time); `/usr/bin/time -v` measured **378,052
KiB** peak RSS, zero process swaps, zero filesystem input, and 384 output
blocks. One existing Starlette/httpx `TestClient` deprecation warning remains.
Ruff check/format, strict mypy for the three changed production modules, and
`git diff --check` pass. The suite used tmpfs at
`/dev/shm/midas-frontier-logical-bypass-20261028T1055Z`.

At the pre-run sample (`10:55:13Z`), memory PSI avg10 was 0%, I/O PSI avg10 was
0.01%, and about 10 GiB was available; the host already showed 3.5 GiB of 4
GiB swap occupied. At `10:55:57Z`, both PSI avg10 readings were 0%, about 10
GiB remained available, and the test process reported zero swaps. No live
source, protected capture, production service, or Arena job was used. External
semantic assertions remain self-attributed; live multi-venue evidence,
broader MIDAS regression, production recovery, and deployment remain open.
Frontier remains **PARTIALLY VERIFIED**.

### Latest acceptance delta

| Requirement | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Malformed payoff and implication market rejection | COMPLETE AND VERIFIED | Same-payoff v6 and logical implication v3 reject copied duplicate states/identities; independent audit v16 requires current evidence. |
| Full Frontier Python regression | COMPLETE AND VERIFIED | 400/400 pass on the exact implementation commit; one existing deprecation warning remains. |
| Cross-venue semantic assertion | PARTIALLY VERIFIED | Reviewer identity and assertion authenticity remain unresolved. |
| Live cross-venue equivalence and economics | BLOCKED | No authorized genuine multi-venue evidence is available for this checkpoint. |
| Broader MIDAS regression | PARTIALLY VERIFIED | Not run on this branch; Reality recovery dependency and incompatible Reality lineages remain unresolved. |
| Production recovery and deployment | DEFERRED | The research worktree remains isolated, unmerged, and undeployed. |
| Frontier overall | PARTIALLY VERIFIED | Live science, broader regression, and production readiness remain open. |

## Current status — 2026-10-28 10:52 UTC

This entry supersedes the 10:46 UTC checkpoint below. Frontier remains
isolated at `/home/charlie/midas-frontier` on `codex/frontier-20261026`; code
commit `3dc3721` is the latest implementation checkpoint.

An offline audit reproduced that direct Pydantic `model_copy(update=...)` can
construct malformed in-memory market models without running field validators.
Same-payoff verifier v6 rejects duplicate payoff-state identifiers, native
instrument identities, missing or duplicate outcome identities, and duplicate
payout rows. Independent audit v15 checks these payoff and instrument
identities again, including payout rows on instruments not selected by a
candidate. Version-5 relationship evidence remains readable but is incomplete
for new audits until it is reviewed under v6.

Four parametrized verifier regressions and one audit regression cover copied
model corruption, including a duplicate payout on an unselected instrument.
The focused relationship/economics module passes **63/63**. The exact full
`tests/frontier` tree passes **399/399** in 29.59 seconds (31.07 seconds wall
time); `/usr/bin/time -v` measured **379,224 KiB** peak RSS, zero process
swaps, zero filesystem input, and 384 output blocks. One existing
Starlette/httpx `TestClient` deprecation warning remains. Ruff check/format,
strict mypy for the three changed production modules, and `git diff --check`
pass. The suite used tmpfs at
`/dev/shm/midas-frontier-malformed-model-20261028T1052Z`.

At the pre-run sample (`10:51:36Z`), memory and I/O PSI avg10 were 0% and about
10 GiB was available; the host already showed 3.5 GiB of 4 GiB swap occupied.
At `10:52:24Z`, PSI avg10 remained 0%, about 10 GiB was available, and the
test process reported zero swaps. No live source, protected capture, service,
or Arena job was used. External semantic assertions remain self-attributed;
live equivalence, broader MIDAS regression, production recovery, and
deployment are still unresolved. Frontier remains **PARTIALLY VERIFIED**.

### Latest acceptance delta

| Requirement | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Copied malformed payoff rejection | COMPLETE AND VERIFIED | Verifier v6 and audit v15 reject duplicate payoff states, native instruments, outcomes, and payout rows, including an unselected instrument. |
| Full Frontier Python regression | COMPLETE AND VERIFIED | 399/399 pass on the exact implementation commit; one existing deprecation warning remains. |
| Cross-venue semantic assertion | PARTIALLY VERIFIED | Replay inputs are bounded and deterministic; reviewer identity and assertion authenticity remain unresolved. |
| Live cross-venue equivalence and economics | BLOCKED | No authorized genuine multi-venue evidence is available for this checkpoint. |
| Broader MIDAS regression | PARTIALLY VERIFIED | Not run on this branch; Reality recovery dependency and incompatible Reality lineages remain unresolved. |
| Production recovery and deployment | DEFERRED | The research worktree remains isolated, unmerged, and undeployed. |
| Frontier overall | PARTIALLY VERIFIED | Live science, broader regression, and production readiness remain open. |

## Current status — 2026-10-28 10:46 UTC

This entry supersedes the 10:35 UTC status and acceptance matrix below.
Frontier remains isolated at `/home/charlie/midas-frontier` on
`codex/frontier-20261026`; code commit `7ebe56a` is the latest implementation
checkpoint.

An offline relationship audit found that same-payoff reviews were not bound to
their replay cutoff. The verifier now requires both distinct pinned market
observation IDs, bounded unique evidence IDs, and an assertion timestamp no
earlier than either source capture. The independent audit requires a single
current-version attestation citing both records and created by the candidate's
replay cutoff. A later review can no longer validate a historical candidate;
older version-4 edges stay readable but produce incomplete evidence until
re-reviewed. Reviewer identity and the external semantic assertion remain
self-attributed and unauthenticated.

The exact committed tree passes **394/394** Frontier tests in 29.62 seconds
(31.09 seconds process wall time). `/usr/bin/time -v` measured **378,716 KiB**
peak RSS, **zero swaps**, zero filesystem input, and 368 filesystem-output
blocks. The only warning is the existing Starlette/httpx `TestClient`
deprecation. Ruff check/format, strict mypy for `relationships.py`,
`independent_audit.py`, and `models.py`, and `git diff --check` pass. The run
used tmpfs at `/dev/shm/midas-frontier-rel-audit-verified-20261028T1048Z`.
Pre-run memory PSI avg10 was 0%; I/O PSI avg10 was 0.06% some / 0.03% full,
with about 10.8 GiB available. At `10:45:46Z` after the run, memory and I/O
PSI avg10 were 0%, with about 10.9 GiB available.

### Latest acceptance delta

| Requirement | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Same-payoff source evidence and assertion timing | COMPLETE AND VERIFIED | Verifier v5 checks both distinct market IDs and assertion ordering; the independent audit v14 enforces the replay cutoff. Four new regressions cover late, missing, shared, and old-version evidence. |
| Full Frontier Python regression | COMPLETE AND VERIFIED | 394/394 tests pass on the exact implementation commit with zero swaps. |
| Cross-venue semantic assertion | PARTIALLY VERIFIED | Replay evidence is now bounded and deterministic; reviewer identity and semantic assertion authenticity remain unresolved. |
| Live cross-venue equivalence and economic opportunity | BLOCKED | Existing source-use holds still prevent authorized validation with Kalshi, Kraken, and Coinbase observations. |
| Broader MIDAS regression | PARTIALLY VERIFIED | Not run on this branch; the Reality recovery dependency and incompatible Reality lineages remain unresolved. |
| Production recovery and deployment | DEFERRED | The research worktree remains isolated, unmerged, and undeployed; production gates remain separate. |
| Frontier overall | PARTIALLY VERIFIED | The new relationship gate is verified, while live science, broader regression, and production readiness remain open. |

No live source, held capture, protected store, production service, or Arena job
was accessed in this checkpoint. The preserved Polymarket capture remains
single-venue evidence with unverified payoff and resolution; no opportunity or
profitability claim follows from this change.

## Current status — 2026-10-28 10:35 UTC

Frontier is isolated at `/home/charlie/midas-frontier` on
`codex/frontier-20261026`. It descends from verified Veritas V6 integration
commit `11d32a0` and retains merge base `55601b9` with `main`. Feature commits
`c4adac6` and `6c13b47` defer the shared Chart payload until it approaches the
viewport and reuse each mounted ECharts instance when its options refresh;
test commit `c04f699` covers fallback when `IntersectionObserver` is absent.
Recent Python verification commits `006fa38`, `5fd3158`, and `668a243` close
an FX result-integrity gap, pin receipt-time replay evidence, and preserve
venue-specific collector configuration across restart. `7f7cd6d` records
strict-format/type cleanup for those changes.

At `2026-10-28T08:52:24Z` and `08:53:07Z`, one finite, unauthenticated
Polymarket Gamma listing request and one explicit CLOB book GET were captured
to a new isolated local store. The stored responses and normalized records
validate against their raw and row hashes. The one open binary market's payoff
and resolution remain unverified; the sampled Yes book has five asks, no bids,
and a source timestamp 33.403 seconds before local receipt by direct wall-clock
comparison. This is live single-venue adapter evidence, not a cross-venue
relationship, simultaneous quote, or opportunity. The Polymarket Institute's
[public research data guide](https://institute.polymarket.com/data) describes
these public market APIs for research use. The local read-only
`/api/frontier/markets` and `/api/frontier/books` routes returned the saved
market and book with their observation IDs intact; the API disclosed the data
as recorded observations only.

At `09:05:58Z`, the full API was started briefly in demo mode on loopback with
paper, recording, Laboratory, Arena, and Reality roots isolated under
`/tmp/midas-frontier-live-ui-20261028-0905/`; all Frontier public-probe flags
were explicitly disabled. Its Frontier API routes returned the saved market
and book (`530a6f…ec44` and `4bb731…a6b5`) with
`source_state: recorded observations only`. The API process was stopped, and
the market-store, collection-store, and manifest hashes still match the
preserved capture. A bounded Chromium smoke then rendered the captured market
in Frontier's Exchange Explorer, opened its book showing the empty bid side,
and expanded the immutable source-response panel. Its observation endpoint
returned HTTP 200 and the saved raw-response details rendered. The browser
observed no page errors, external requests, or probe/collection POSTs. A
screenshot is at `/dev/shm/frontier-live-capture-ui-20261028.png`. API and Vite
were stopped afterward. This verifies one local captured-data UI path only.

After commit `be31236` added the full observation ID to the evidence panel, a
second bounded Chromium check used a byte-identical temporary copy of the
captured market store under
`/tmp/midas-frontier-live-ui-id-20261028T1026Z/`. It displayed the full book
observation ID, loaded the evidence endpoint with HTTP 200, and made no source
operation or external request. The API reported demo mode and
`live_execution: false`; all public-probe flags were disabled. The original
market store, collection journal, and manifest hashes were rechecked unchanged.
Screenshot: `/dev/shm/frontier-live-capture-ui-observation-id-20261028.png`.

At `10:27Z`, an offline review of `fx.py` and `capital.py` checked rate
orientation, venue-local balances, exact conversion-fee recomputation,
candidate P&L adjustment, and venue-specific capital release after each
market's latest verified settlement plus an explicit delay. The focused
`test_fx_sensitivity.py` and `test_capital_carry.py` suites passed **45/45** in
0.54 seconds using tmpfs. The review found no defect requiring a code change.
These are bounded hypothetical calculations; they do not establish venue
convertibility, settlement truth, shared collateral, or execution.

The related Kalshi fee-model review confirms the candidate schedule remains
explicitly estimated, preserves separate member-precision cases, and is not an
account-specific quote. `test_kalshi_fee_sensitivity.py` passed **21/21** in
0.52 seconds on fixtures, including property-based calculation comparisons.
Live fee applicability, account precision, and venue-specific authorization
remain unverified; no fee-data probe was made.

The payoff-model audit reproduced an ambiguity in verified markets: two payout
rows for the same state passed set-based coverage validation, and downstream
mapping retained only the last amount. Commit `f591185` rejects duplicate payout
state identifiers at both instrument and verified-market validation. Three
focused regressions cover identical duplicates, conflicting amounts, and
prebuilt instruments. The independent binary, multi-outcome, basket, and
implication audit paths also reject duplicate vectors. The genuine captured
market still has an unverified payoff; this fix does not create live payoff
evidence.
Existing implementation includes Polymarket, Kalshi, Kraken Spot, and Coinbase
public read adapters; canonical instrument and payoff models; reviewable
relationship evidence; bounded candidate discovery and independent economics;
isolated collection, storage, and replay; Arena integration; and the native
Mission Control workspace.

Current bounded verification:

- The full `tests/frontier` suite passes **390/390** in one process after the
  payout-row fix. The tmpfs run at
  `/dev/shm/midas-frontier-payoff-regression-20261028T1033Z` took 29.51 seconds.
  Peak RSS, swap, and filesystem input were not measured. One existing
  Starlette/httpx `TestClient` deprecation warning remains.
- The updated frontend passes **47/47** unit tests, TypeScript, full-project
  ESLint and Prettier, production build, **17** default Playwright cases with
  two expected seeded-only skips, and the separate **2/2** seeded Frontier/Arena
  cases using disposable local services and stores; the seeded cases were
  rerun after the chart changes. The full default browser
  suite was rerun after the chart lifecycle and fallback changes against the
  latest code. After the observation-ID UI change, all **47/47** frontend unit
  tests passed again; TypeScript, scoped ESLint/Prettier, and production build
  also passed. The build emitted a 368.81 kB entry, 182.82 kB Frontier chunk,
  and a 544.51 kB Chart/ECharts chunk.
- After an offline review of the separate FX and venue-capital sensitivities,
  `test_fx_sensitivity.py` and `test_capital_carry.py` passed **45/45** in
  0.54 seconds. The arithmetic remains assumption-driven and venue-local.
- `test_kalshi_fee_sensitivity.py` passed **21/21** in 0.52 seconds; its
  property-based cases compare the candidate fee calculation with the separate
  audit and explicit rounding sensitivities.
- `test_payoff_model_invariants.py` passed **3/3**. Strict configured mypy for
  `models.py`, Ruff, and formatting passed after the duplicate-state fix.
- The current Frontier evidence disclosure displays the full immutable
  observation ID alongside timing, row hash, request metadata, and the raw
  response. The ID is covered by a UI test and was visible in the captured-data
  browser check above. The Chart/ECharts chunk still triggers Vite's 500 kB
  advisory; viewport deferral reduces initial transfer but not chunk size.
- The new viewport-loading browser check observes no Chart module request while
  the chart is below the viewport, then one request after scrolling it into
  view. This defers transfer and parsing; it does not reduce the 544.51 kB
  minified Chart chunk (186.79 kB gzip). Option refreshes now update the
  existing chart and do not reinitialize the ECharts instance.
- The separate genuine-capture browser smoke at `10:21Z` rendered market
  `2589810`, its recorded one-sided book, and the raw response evidence panel;
  `GET /api/frontier/observations/4bb731fd70467c6e8f4ebf33c994243ecb2a02f2701d8ba4e493aae729b0a6b5`
  returned HTTP 200. It sent no external or source-probe/collection request.
  The screenshot is transient in `/dev/shm`, not a committed artifact.
- Strict configured mypy passes for the changed `models.py`; Ruff and formatting
  pass for the changed Python files. Earlier scoped strict mypy covered the
  Frontier package/API integration. The tmpfs test command and pressure gate are
  documented in `FRONTIER_OPERATIONS.md`.
- The full suite's sampled PSI stayed below the 1% admission gate through
  `09:01:26Z` (memory avg10 0%; I/O avg10 0.32% some / 0.19% full). At
  `09:02:39Z`, memory PSI rose to **54.19% some / 48.45% full**; the cause is
  unknown and is not attributed to Frontier. At `09:03:33Z`, memory PSI avg10
  was 0.93% some / 0.79% full and I/O PSI avg10 was 0.79% some / 0.75% full.
  At `09:05:51Z`, I/O PSI avg10 was 0.99% some / 0.99% full; at `09:06:50Z` it
  was 1.35% some / 1.35% full while memory PSI avg10 was 0%. The source of the
  change is unknown and is not attributed to Frontier. At `10:13:59Z`, memory
  PSI avg10 was **37.05% some / 31.35% full** and I/O PSI avg10 was 0%. At
  `10:17:35Z`, memory PSI avg10 was **9.69% some / 6.56% full** and I/O PSI
  avg10 was 0%. At `10:22:00Z`, memory and I/O PSI avg10 were both 0%. At
  `10:26:49Z`, memory PSI avg10 was 0% and I/O PSI avg10 was 0.02% some/full.
  At `10:28:32Z`, memory and I/O PSI avg10 were both 0%. At `10:29:58Z`, memory
  PSI avg10 was 0% and I/O PSI avg10 was 0.02% some / 0% full. At `10:34:45Z`,
  memory PSI avg10 was 0% and I/O PSI avg10 was 0.04% some / 0% full.
  The pressure source is unknown and is not attributed to Frontier.

The complete MIDAS repository regression remains unverified. The current tree
has `packages/midas/arena/recovery.py` but lacks
`packages/midas/reality/recovery.py`, which
`tests/test_reality_full_scale_validation.py` imports. Other Reality lineages
have different collector, reconstruction, replay, and storage dependencies;
no module was copied or cherry-picked into this branch. Earlier selected legacy
regressions do not replace the full suite.

Live cross-venue validation remains blocked by source-use holds. Kalshi, Kraken,
and Coinbase stay quarantined from live probes and research routes; a test to
replay an archived held capture was denied by `tests/frontier/conftest.py` and
removed without a workaround. Existing synthetic tests establish only
hypothesis behavior. No verified live cross-venue payoff match, economically
eligible opportunity, or realizable profit is claimed. Continuous source
quality, production resource/recovery, and deployment gates remain open.

Frontier remains **PARTIALLY VERIFIED**, research-only, isolated, unmerged, and
undeployed. No protected service or historical evidence was changed.

## Current mission acceptance matrix — 2026-10-28 10:35 UTC

This matrix assesses the requested Frontier scope against the current isolated
branch and captured evidence. The current code/test tree includes `f591185`,
`be31236`, and test-isolation guard `429f690`; documentation-only checkpoints
include `7651b81`, `2c8038d`, `6da77a1`, `95b00bc`, `e65f763`, `5c5d6f1`,
`275cccf`, and `9dc7509`. The genuine public capture remains untracked and
preserved under
`data/frontier-public-probes/`.

| Requirement | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Isolated Frontier baseline and adapter capability framework | COMPLETE AND VERIFIED | Branch `codex/frontier-20261026` descends from the verified V6 baseline. Adapters declare supported and unsupported capabilities; configuration, transport, parsing, and fixture contracts are covered by the full Frontier suite. |
| Polymarket public adapter and normalized API path | PARTIALLY VERIFIED | One genuine Gamma listing and one CLOB book were captured, hash-validated, returned through the local API, and rendered in the native workspace; the immutable observation endpoint returned HTTP 200. This is not broad adapter conformance or simultaneous/executable evidence. |
| Kalshi, Kraken, and Coinbase live source use | BLOCKED | Adapter and permission-gate fixtures pass, but current research-use/terms gates hold probes and quarantine stored evidence. No live cross-venue use is claimed. |
| Additional venue screen: Deribit | COMPLETE AND VERIFIED | Official API, both current entity-specific terms pages, and jurisdiction documents were reviewed. Derivative data could be contextual evidence, but data-processing permission is unverified and one entity's terms prohibit automated collection; no adapter or probe was added. See `ADDITIONAL_VENUE_SCREEN_2026-10-28.md`. |
| Canonical instruments and supported payoff semantics | PARTIALLY VERIFIED | Versioned models preserve venue IDs, outcomes, constraints, denomination identity, payoff and resolution metadata, and provenance. Payout vectors reject duplicate state rows at model validation; three focused regressions and the full suite pass. The captured binary market's payoff and settlement remain unverified. |
| Relationship graph and evidence persistence | PARTIALLY VERIFIED | Deterministic proposals, explicit hypothesis/verification states, evidence-backed reviews, bounded graph queries, and persistence are tested. No genuine verified cross-venue economic equivalence exists in permitted evidence. |
| Opportunity discovery and independent verification | PARTIALLY VERIFIED | Bounded binary, outcome-coverage, implication, basket, and joint-state paths have independent arithmetic and fixture coverage. No live cross-venue candidate or positive eligible opportunity is demonstrated. |
| Cross-venue costs, capital, and execution uncertainty | PARTIALLY VERIFIED | Fee, FX, carry, partial-fill, timing, and venue-separated virtual-capital models have independent checks; focused FX/carry regressions passed 45/45 and Kalshi fee regressions passed 21/21. Account-specific fees, settlement, legal access, custody, transfers, and executable availability remain unresolved. |
| Collection, provenance, durable storage, and deterministic replay | PARTIALLY VERIFIED | Finite restartable collection, immutable hash-linked observations, bounded storage, replay, and source-quality metadata are fixture-tested; one bounded live Polymarket capture is preserved. Continuous feeds, broad history, and long-horizon source quality remain unmeasured. |
| Laboratory/Arena integration | PARTIALLY VERIFIED | Replay/comparison artifacts and bounded job paths have deterministic fixture coverage and a prior short supervised worker demonstration. Endurance, concurrency, and production-worker readiness are not established. |
| Frontier analytics and coverage | PARTIALLY VERIFIED | Source-aware coverage, quality, timing, candidate, and rejection summaries are implemented. The single live market/book sample cannot support venue-wide coverage or prevalence conclusions. |
| Native Mission Control Frontier workspace | PARTIALLY VERIFIED | All 47 frontend unit tests, TypeScript, lint/format, production build, fixture browser flows, and a bounded genuine-capture browser check pass. The native view renders a saved market/book and exposes its full observation ID and raw evidence. This does not validate every workspace view or production deployment. |
| Full Frontier Python regression | COMPLETE AND VERIFIED | `tests/frontier` passed **390/390** in one process after the capture-path guard and payoff-row fix, in 29.51 seconds. The existing Starlette/httpx deprecation warning remains; this run did not measure peak RSS, swap, or filesystem input. |
| Broader MIDAS regression | PARTIALLY VERIFIED | Not run on this branch. `tests/test_reality_full_scale_validation.py` imports `packages/midas/reality/recovery.py`, which is absent here; other Reality lineages have incompatible dependencies. |
| Research-only and source-use boundary | COMPLETE AND VERIFIED | No authenticated trading, order, wallet, or deposit path was introduced. API health reported `live_execution: false`; probes were disabled in the local API check, and held-source routes remain quarantined. |
| Resource sustainability | PARTIALLY VERIFIED | Earlier bounded tests and workers have measured profiles, but no sustained campaign is authorized. At `10:34:45Z`, memory PSI avg10 was 0% and I/O PSI avg10 was 0.04% some / 0% full; the browser and test runs are not sustained resource evidence. |
| Required architecture, operations, current-state, report, venue-screen, and ledger documentation | COMPLETE AND VERIFIED | The requested architecture, operations, current-state, engineering report, additional-venue screen, and append-only mission ledger exist and include current test, API-capture, permission, and resource evidence. |
| Production deployment | DEFERRED | Deployment remains separate and requires source-policy closure, recovery/resource review, deployment-scope verification, and explicit authorization. |
| Genuine cross-venue relationship and economic validation | BLOCKED | Current source-use gates do not permit the additional venue evidence needed to verify a live cross-venue match. Do not bypass the gates; continue source-independent work. |
| Project Frontier overall | PARTIALLY VERIFIED | The multi-exchange research foundation is implemented, but live cross-venue science, broader MIDAS regression, sustained resource evidence, production recovery, and deployment remain incomplete. |

The zero-opportunity outcome remains valid. Fixture verification proves only
the supported model behavior; the single Polymarket capture does not establish
cross-venue equivalence, simultaneous availability, realizable profit, or that
the market universe has been adequately covered.

## Full Frontier regression after capture isolation — 2026-10-28 09:03 UTC

After commit `429f690` added the Python test I/O guard for the genuine public
capture root, the complete `tests/frontier` suite passed **387/387** in one
process. Pytest time was 29.38 seconds. Temporary test state was placed at
`/dev/shm/midas-frontier-regression-20261028T0901Z`. No live source, protected
store, production service, or Arena job was accessed. The existing
Starlette/httpx `TestClient` deprecation warning remains. Resource measurements
for peak RSS, swaps, and filesystem input were not collected for this run.

Sampled memory and I/O PSI remained below the documented 1% avg10 gate through
`09:01:26Z`. A later `09:02:39Z` sample showed memory PSI avg10 at 54.19% some /
48.45% full; its cause is unknown. At `09:03:33Z`, memory avg10 was 0.93% some /
0.79% full and I/O avg10 was 0.79% some / 0.75% full. The latest sample is
below the gate, but another fresh sample is required before additional broad
work. Frontier remains **PARTIALLY VERIFIED**.

## Live API read of preserved Polymarket evidence — 2026-10-28 09:06 UTC

A short-lived Uvicorn process ran the full MIDAS API in demo mode on loopback.
Its paper database, recording root, Laboratory, Arena, and Reality roots were
under `/tmp/midas-frontier-live-ui-20261028-0905/`; the Frontier read path
pointed to the preserved Polymarket capture and all public-probe flags were
false. `GET /api/frontier/markets?venue=polymarket&limit=5` and
`GET /api/frontier/books?venue=polymarket&limit=5` each returned the saved row
with its original observation ID and recorded-only disclosure. The market
store, collection store, and manifest hashes matched the values in the capture
report after shutdown. The demo API health response reported `live_execution`
false. No source request or production service was used.

Vite was started briefly on loopback against the local API. A browser was not
started because I/O PSI was 0.99% some/full at `09:05:51Z` and 1.35% some/full
at `09:06:50Z`, above the documented resource gate. The cause is unknown; this
does not establish a UI defect. A genuine-capture browser rendering check
remains pending. Frontier remains **PARTIALLY VERIFIED**.

## Bounded live Polymarket adapter validation — 2026-10-28 08:57 UTC

One explicitly enabled finite collection request used the existing read-only
Polymarket adapter with `market_limit=1`, `book_limit=0`, a 5-second request
timeout, a 262,144-byte response cap, zero retries, and a one-request
configuration. It completed in one Gamma GET and persisted one market listing
to the fresh local store
`data/frontier-public-probes/polymarket-bounded-20261028T0852-r2Z/`. A second
explicit adapter call made one unauthenticated CLOB GET for the first outcome
token's book. No account, wallet, order-entry, proxy, or production service was
used. Both source responses were HTTP 200 from allowlisted HTTPS hosts.

The listing reported one open binary market, native market ID `2589810`, event
ID `606422`, and Yes/No outcome instruments. Frontier leaves both payoff and
resolution unverified. The separate Yes-token book (`1701037799…25586`)
contained five ask levels and no bid levels; its best observed ask was `0.995`.
The source-reported book timestamp was `2026-10-28T08:52:33.893Z`; local
receipt was `2026-10-28T08:53:07.296333Z`. The **33,403.333 ms** difference is
only a comparison of the recorded clocks. It does not establish clock
synchronization, source freshness limits, simultaneous availability, fills,
or executability.

The manifest and SQLite evidence are local and untracked. The manifest SHA256
is `2e1574b5a42499ba8efe3ac9033de9e6c4e1a3a1a6d381955ce57e9815938e79`. The
SQLite database and collector-journal hashes at `08:57Z` are
`e9efca9b1658a29cf768222883f9eda0d466e011622b36b0e38efecd846a2052` and
`8b21af2bae0af48a66d52e76aeb228606a530ffc1e83725ab0d7c808cfa0773d`. The
listing observation ID is
`530a6f50dd9826fa200a2dc7fe8a60de3d59b0b465297bd5bb9c7c6f4274ec44` and its
raw/row hashes are `90d3ae42ed62b003a3fc143a79af43251e5aafb0197eaa37c65d38b1cc1c55ca`
and `0f967db5763776a08281013a541f5fc433dd9fbc011ed406357fa5fe722c9b82`.
The book observation ID is
`4bb731fd70467c6e8f4ebf33c994243ecb2a02f2701d8ba4e493aae729b0a6b5` and its
raw/row hashes are `e7dcb616e5a8f6b19c45010b222c36e889244a9f4da254030040f51f5469df91`
and `aa6e39508c70cf5ca995271f39aa3b9aff9f8d77e5a8aaf1a902ae90bc94dd68`.
The one-market collector run is `e8d1373f-7df1-4ac4-8d30-8f4a50b57858`.
Read-only local API requests returned HTTP 200 for one market and one book,
preserved both observation IDs, and made no additional exchange request.

To keep this genuine data separate from synthetic regression inputs,
`tests/frontier/conftest.py` now blocks Python file reads and writes under both
the held legacy capture root and the new `data/frontier-public-probes` root.
Code commit `429f690` expands the runtime and static path guards for both roots.
The static test-source scan and runtime path, symlink, `..`, and `dir_fd`
checks pass **3/3**. Ruff, formatting, and `git diff --check` pass. The capture
is not a fixture and no cross-venue inference was attempted. The project
remains **PARTIALLY VERIFIED**; source-use holds for Kalshi, Kraken, and
Coinbase, the full MIDAS regression gap, production recovery, and deployment
remain open.

## Collector configuration, FX audit, and timeline timestamp integrity — 2026-10-28 08:47 UTC

Three focused research fixes are now checkpointed:

- Commit `668a243` preserves concrete `KrakenSpotConfig` and
  `CoinbaseSpotConfig` fields in the finite collection run spec using an
  explicit allowlisted type tag. Pair/product allowlists and Coinbase terms
  acknowledgment survive journal creation, listing, and restart. Resume rejects
  changed configuration before adapter work. Schema-v1 base-config records
  remain readable; arbitrary persisted class names are rejected.
- Commit `006fa38` binds a verified virtual FX result's reported conversion
  fee to both the independent audit total and the terminal P&L fee deduction.
  Recomputed result hashes can no longer legitimize a forged fee or mismatched
  after-conversion P&L. Unavailable and disagreement states remain explicit.
- Commit `5fd3158` adds a timeline test where exchange time precedes receipt
  time. The quote remains unavailable until local receipt, and its source-time
  skew reaches the existing economic timing audit.

The full Python suite passed **386/386** after these logic and test changes in
29.38 seconds pytest time / 30.82 seconds wall time, with **378,704 KiB** peak
RSS, zero swaps, and zero filesystem input. After a final formatting/type
cleanup commit (`7f7cd6d`), the affected collection/API, FX, and timeline
selection passed **57/57** in 3.44 seconds; strict configured mypy for
`collection.py` and `fx.py`, Ruff check/format, and `git diff --check` passed.
The full run began at `2026-10-28T08:46:01Z` after memory PSI avg10 was 0%, I/O
PSI avg10 was 0.82% some / 0.74% full, and no Arena admission lock holder was
found. After tests, PSI was low; at `08:47:41Z` a later sample showed memory
pressure above 45% full, so no further broad work was started. No live source,
held capture, protected service, or production store was used.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Full Frontier Python suite | COMPLETE AND VERIFIED | 386 tests passed after logic changes; the final post-format affected selection passed 57/57. |
| Collection restart config pinning | COMPLETE AND VERIFIED | Kraken/Coinbase config round-trip, mismatch rejection, no adapter call, and legacy schema-v1 readability pass. |
| FX result integrity | COMPLETE AND VERIFIED | Rehashed tampering of scenario fee, aggregate fee, and audit relationship is rejected. |
| Timeline receipt/source time distinction | COMPLETE AND VERIFIED | Availability follows local receipt; exchange-time skew remains unverified by the economic timing gate. |
| Frontier project overall | PARTIALLY VERIFIED | Live multi-venue evidence, full MIDAS regression, production recovery, and deployment remain open. |

## Chart instance reuse on data refresh — 2026-10-28 08:31 UTC

Code commit `6c13b47` separates ECharts instance lifetime from option updates.
`Chart.tsx` now initializes the chart and resize observer once per mounted
component, applies each new option with `notMerge: true`, and disposes the
instance only on unmount. This prevents refreshed API data from tearing down
and recreating the same chart while ensuring removed series or axes do not
linger after an option change.

`Chart.test.tsx` verifies that an option update calls `setOption` on the same
single instance and that disposal happens on unmount. The complete frontend
unit suite passes **47/47** in nine files, including viewport observer and
no-observer fallback behavior. The production build passes
TypeScript and Vite (2,230 modules; entry 368.81 kB, Frontier 182.75 kB, Chart
544.51 kB / 186.79 kB gzip). The post-change Playwright chart smoke and deferred
loading tests pass **2/2**. A follow-up full Playwright run against the latest
code passes **17 tests with two expected seeded-only skips**. Full-project
ESLint, Prettier, and `git diff --check` pass.

At `2026-10-28T08:31:18Z`, memory PSI avg10 was 0%, I/O PSI avg10 was
0.35% some / 0.02% full, and about 10 GiB was available. Tests use disposable
browser state and loopback demo services. No source probe, protected service,
or protected store was accessed. Frontier remains **PARTIALLY VERIFIED**.

## Viewport-deferred chart loading — 2026-10-28 08:28 UTC

Code commit `c4adac6` centralizes chart rendering in
`apps/web/src/DeferredChart.tsx` for Mission Control, Arena, and Reality. It
reserves chart space, exposes a loading status, and uses `IntersectionObserver`
with a 120 px root margin before importing the ECharts module. Browsers without
`IntersectionObserver` retain immediate loading. The chart's dimensions remain
242 px in the shared dashboard and 280 px in Reality.

The focused browser test places the viewport at 390 by 200 px, confirms the
chart container is below the viewport and no `Chart` module request occurs,
then scrolls to the reserved area and confirms one module request and a
rendered SVG. This verifies request timing only: the production build still
contains the 544.41 kB minified Chart chunk (186.76 kB gzip). Its bytes are
deferred until a chart is likely to be seen; total bundle size is unchanged.

```bash
cd apps/web
./node_modules/.bin/vitest run
# 45 passed in 8 files
./node_modules/.bin/playwright test e2e/deferred-chart.spec.ts
# 1 passed; isolated loopback demo API and Vite server
./node_modules/.bin/playwright test
# 17 passed, 2 seeded-only skips
npm run build
# TypeScript and Vite passed; entry 368.81 kB, Frontier 182.75 kB,
# Chart 544.41 kB minified / 186.76 kB gzip
./node_modules/.bin/eslint src/DeferredChart.tsx src/DeferredChart.test.tsx src/App.tsx src/Reality.tsx src/Arena.tsx e2e/deferred-chart.spec.ts
./node_modules/.bin/prettier --check src/DeferredChart.tsx src/DeferredChart.test.tsx src/App.tsx src/Reality.tsx src/Arena.tsx src/styles.css e2e/deferred-chart.spec.ts
```

At `2026-10-28T08:28:12Z`, memory PSI avg10 was 0%, I/O PSI avg10 was
0.14% some / 0.12% full, and about 10 GiB was available. Tests used only
isolated browser/API state and fixtures; no exchange probe, production service,
or protected store was accessed. Frontier remains **PARTIALLY VERIFIED**.

## Bounded metadata and initial resource checkpoint — 2026-10-28 03:59 UTC

The isolated worktree is `/home/charlie/midas-frontier` on
`codex/frontier-20261026`. The relevant commits are `e4692d1`
(capability-specific single-market metadata capture), `b7638db` (bounded
live-probe evidence), `447ea0f` (web regression and event-identity checkpoint),
`e994654` (current engineering-report checkpoint), and `c2e3db0` (resource-gate
recheck). The Polymarket event-ID code/test correction described below remains
uncommitted. There is no merge, push, production deployment, source credential,
or protected-service change.

One bounded, public, read-only Polymarket Gamma detail request for previously
recorded market `2589810` returned HTTP 200 and was persisted in a separate,
ignored local capture store. Its 4,198-byte response hash is
`d462014349743a6175facab3aef0433a069899c43845c789ca4cdce87bd8cf26`; the
evidence envelope links to the original listing observation and passes
read-only SQLite integrity and raw-hash checks. The detail title and Federal
Reserve authority match the listing, but the response has no event field and
does not prove event membership, outcome completeness, payoff, settlement
asset, or cross-venue equivalence. The persisted detail's `market:2589810`
event value was a local fallback from the legacy MIDAS parser, not a Gamma
event ID. The request succeeded, but the disposable TestClient harness then
exited nonzero while closing an async client on a different event loop; no
request was retried. Exact capture and source-use boundaries are in
[`SOURCE_DATA_TERMS_REVIEW_2026-10-27.md`](SOURCE_DATA_TERMS_REVIEW_2026-10-27.md).

The full Mission Control web unit suite passed **40/40 across seven files**
(360,100 KiB peak RSS, zero swaps or socket messages). The Frontier browser
suite passed **6/6** against temporary loopback services and isolated data
(197,660 KiB peak RSS, zero swaps or socket messages). The browser cases made
no public source request. Earlier typecheck, targeted lint, formatting, and
Frontier backend checks are recorded in the mission ledger. The production
web build remains pending.

An additional working-tree correction removes the legacy Polymarket
`market:<id>` fallback from Frontier's `native_event_id`: the adapter now
retains only an explicit numeric event object or a validated parent-event ID.
Fixture tests cover missing event context and preservation of the saved
listing's event grouping. Ruff and formatting pass, but those Python tests and
strict typing have not been run after this correction. At
`2026-10-28T03:59:17Z`, memory PSI avg10 was **35.49% some / 30.65% full** and
external Veritas PID **4154226** held the shared Arena admission lock in `D`
state. The process and lock were left untouched; no further resource-bearing
checks were started.

The `2026-10-28T04:03:00Z` follow-up remained above the resource gate:
memory PSI avg10 was **42.66% some / 33.52% full**, avg60 **37.19% / 29.70%**,
and avg300 **27.58% / 22.98%**. About **10 GiB** was available, with **333
MiB** swap free. PID **4154226** still held the shared lock in `D` state. The
event-ID correction remains untested and uncommitted pending another fresh
resource admission; no host process was touched.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Public Polymarket single-market metadata route | PARTIALLY VERIFIED | One bounded HTTP 200 capture persisted and hash-checked; no event, payoff, or cross-venue verification. Disposable harness teardown failed after read-back. |
| Frontier web unit suite | COMPLETE AND VERIFIED | 40/40 tests across seven files; 360,100 KiB peak RSS; zero swaps or socket messages. |
| Frontier browser E2E | COMPLETE AND VERIFIED | 6/6 tests on temporary local services/data; no public source probes. |
| Polymarket missing-event identity correction | PARTIALLY VERIFIED | Adapter and API assertions are written and static checks pass; Python tests/typecheck pending a fresh resource admission. |
| Production web build | PARTIALLY VERIFIED | Not run after the latest UI slice; defer until a fresh resource check admits it. |
| Multi-venue economic validation | BLOCKED | Other source-use holds remain in effect; no verified live cross-venue payoff is claimed. Fixture-only economic checks do not establish live equivalence. |
| Production deployment | DEFERRED | Frontier remains isolated on its development branch; no production transition was attempted. |

## Polymarket event identity and consumer regression closeout — 2026-10-28 04:11 UTC

Commit `fb6d800` corrects Frontier's Polymarket normalization. The legacy MIDAS
normalizer still supplies `market:<id>` for older callers, but Frontier now
sets `native_event_id` only from an explicit numeric nested Gamma event or the
validated event-page parent. Missing or ambiguous event context stays `null`.
The listing observation and older normalized detail capture remain immutable;
the latter's `market:2589810` value is retained as historical parser output,
not source event evidence. Changed code/tests:
`packages/midas/frontier/adapters/polymarket.py`,
`tests/frontier/test_adapters.py`, and `tests/frontier/test_api.py`.

The full Frontier suite passes **352/352** in 55.83 seconds (376,888 KiB peak
RSS, zero swaps or socket messages). After the final type-only annotation
change, the targeted explicit-event, absent-event, and bound-API tests pass
**3/3** in 1.02 seconds (81,848 KiB peak RSS, zero swaps or socket messages).
Strict typing passes for the API, shared models, adapter base, Polymarket, and
Kalshi modules:

```bash
/home/charlie/midas/.venv/bin/mypy --strict --follow-imports=silent \
  apps/api/frontier.py packages/midas/frontier/models.py \
  packages/midas/frontier/adapters/base.py \
  packages/midas/frontier/adapters/polymarket.py \
  packages/midas/frontier/adapters/kalshi.py
# Success: no issues found in 5 source files
```

The selected Arena discovery, replay, timeline, and job-supervision regression
then passed **38/38** in 37.70 seconds (200,152 KiB peak RSS, zero swaps or
socket messages). Its fixtures and temporary roots do not exercise a production
Arena store or establish real systemd/cgroup execution.
At the post-run sample `2026-10-28T04:11:18Z`, memory PSI avg10 was **0.00%
some / 0.00% full**, I/O PSI avg10 was **10.31% some / 9.83% full**, about
**9 GiB** was available, and no process held the shared Arena lock. This is a
point sample, not a sustainability claim.

At `2026-10-28T04:12:29Z`, a fresh sample denied additional resource-bearing
work: memory PSI avg10 was **38.86% some / 33.25% full**. External Veritas PID
**4166289**, running `scripts/veritas_gap_detail_v2_batch.py`, held the shared
Arena lock in `D` state. It was not touched. The regression and build results
above remain valid; no follow-up work was launched under this pressure.

TypeScript project build and production Vite bundle also pass. Vite wrote to
`/tmp/midas-frontier-build-20261028T0406Z`, leaving the existing web `dist`
output alone. The output transformed 2,228 modules in 4.83 seconds. Peak RSS
was 685,120 KiB; no swap or socket messages were used. Existing advisories
remain: the Chart chunk is 544.41 kB, and Vite notes that the temporary output
directory is outside the project root and will not be emptied automatically.
Ruff check/format and `git diff --check` pass. The full web suite remains
40/40 and Frontier browser suite 6/6 from the 03:57 checkpoint above.
The generated OpenAPI description for the metadata route now states its
saved-listing binding and evidence limits; the focused API schema regression
passes **1/1**. Commit `1da2b11` records that API description, its assertion,
and the matching operations, development, and current-state documentation. No
public request was made for this documentation update.

At `2026-10-28T04:06:58Z`, memory PSI avg10 was **0.08% some / 0.08% full**,
about **10 GiB** was available, and the shared Arena lock had no listed holder.
The protected Reality API remained untouched. No public source request was
made for this correction, no historical capture was rewritten, and no
deployment occurred.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Frontier Polymarket native event identity | COMPLETE AND VERIFIED | Commit `fb6d800`; 352-test Frontier regression, focused final-code 3/3, selected Arena regression 38/38, and strict mypy pass. Historical captures keep their original normalized value. |
| Arena discovery/replay/timeline/job consumers | COMPLETE AND VERIFIED | Selected 38-test regression passes after the event normalization correction; no real systemd unit or production Arena root was used. |
| Frontier web unit suite and browser E2E | COMPLETE AND VERIFIED | 40/40 and 6/6 respectively; E2E uses temporary local services and no public source probe. |
| Production web build | COMPLETE AND VERIFIED | TypeScript plus Vite pass with output in `/tmp`; known Chart chunk and external outDir advisories remain. |
| Live cross-venue equivalence and eligible economics | BLOCKED | Only one bounded Polymarket detail was fetched; other source-use holds prevent live cross-venue validation. No live opportunity or profitability is claimed. |
| Production deployment | DEFERRED | Isolated branch remains unmerged, unpushed, and undeployed. |

Frontier overall remains **PARTIALLY VERIFIED**, research-only, and
undeployed. The final completion matrix must preserve the held-source, live
cross-venue, source-permission, and production-transition gaps.

## Exact captured-body normalization replay — 2026-10-28 04:14 UTC

The stored public Gamma detail body was re-run through the corrected
Polymarket adapter using an in-memory HTTPX `MockTransport`. The existing raw
SHA-256 remained `d462014349743a6175facab3aef0433a069899c43845c789ca4cdce87bd8cf26`;
the result preserved the native market ID and title but returned
`native_event_id=null` instead of the historical parser fallback
`market:2589810`. The replay made one mocked request and **zero public network
calls**. It did not append a row: SQLite integrity stayed `ok` and the
read-only capture store remained at two observations.

This confirms the event-ID correction against the exact genuine captured body
without rewriting history. It does not establish parent-event membership,
exhaustive outcomes, payoff, settlement, venue equivalence, or an opportunity.
The capture remains in ignored local storage and is not included in version
control. The legacy Polymarket normalizer's local fallback remains compatible.
The complete `tests/integration/test_adapters.py` file passes **10/10**,
including `test_legacy_polymarket_event_id_fallback_remains_compatible`
(91,336 KiB peak RSS, zero swaps or socket messages). These use recorded
fixtures and local transports; no exchange endpoint was contacted.

**Corrected combined Frontier/Arena verification — 2026-10-28 03:12 UTC:**
After synchronizing the stale timeline message expectation and isolating two
launch-command unit tests from the host-wide admission lock, the serial
Frontier plus selected Arena regression passes **383/383**. Pytest took 90.26
seconds; process wall time was 91.74 seconds, maximum RSS **377,372 KiB**, zero
swaps, and zero socket messages. The existing Starlette/httpx TestClient
deprecation warning remains. Ruff check/format and `git diff --check` pass.
This selection is not the full MIDAS Python repository suite.

The scoped strict mypy check for
`packages/midas/frontier/discovery_comparison.py` was not started because the
768-MiB resource gate denied it. At `2026-10-28T03:12:36Z`, memory PSI avg10
was **34.89% some / 32.22% full**; external Veritas batch PID **4117533** held
the shared Arena admission lock. It was not touched. No additional
resource-bearing validation should run until a fresh gate admits it.

**Frontier/Arena regression rerun — 2026-10-28 03:08 UTC:** With an admitted
preflight snapshot, the serial selection
`tests/frontier` plus `test_frontier_discovery.py`, `test_frontier_replay.py`,
`test_frontier_timeline.py`, and `test_jobs.py` completed **380 passed / 3
failed** in 88.11 seconds pytest time / 89.51 seconds process wall. Peak RSS was
**377,184 KiB**, with zero swaps and socket messages; one existing
Starlette/httpx TestClient deprecation warning remains. One failure was a
stale timeline test expectation for the error wording after Frontier discovery
was added to the same resource ceiling. Two command-assembly tests were denied
before mocked launch because external Veritas batch PID **4112565** acquired
the shared `/home/charlie/midas/data/arena/.global-admission.lock` during the
suite. Read-only `fuser` confirmed the holder; it was left untouched. The two
command tests now locally stub admission, and the timeline assertion now
matches the current message. These test-only corrections have not yet been
rerun. Ruff and `git diff --check` pass.

At `2026-10-28T03:08:37Z`, after the suite, memory PSI avg10 was **36.19% some
/ 30.12% full**, I/O PSI avg10 was **3.98% some / 3.70% full**, about **9.6
GiB** was available, and **332 MiB** of swap was free. Wait for the external
lock to release and recheck pressure before further admission-dependent
verification. No source, held capture, external process, protected service,
or production Arena artifact was modified.

**Latest bounded Arena discovery execution — 2026-10-28:** One
synthetic `frontier_discovery` job passed the real host-wide admission gate and
ran through `midas.arena.jobs` in an actual transient user systemd unit. The
run occurred between the `03:00:30Z` clock sample and the `03:03:40Z` post-run
pressure sample; exact worker start time was not separately captured. The
hash-pinned input and output were confined to a temporary directory, the
worker was AF_UNIX-only, and systemd exposed `MemoryMax=536870912`,
`MemorySwapMax=0`, and `CPUQuotaPerSecUSec=500ms`. The bounded supervisor
smoke command took 5.9 seconds wall; the worker's own elapsed field was not
retained. Its content-addressed artifact passed the
result verifier and contained two fixture candidates. Job ID was
`job-16457e8fea8a483d8d10c8df`; result SHA-256 was
`c4c753fd209b0857a522a19054d82793c65b03c31c33890915cf4c0f64982e36`.
Systemd recorded cgroup MemoryPeak
117,252,096 bytes, while the worker process reported peak RSS 170,110,976
bytes; these separate measurements are not reconciled by this run. After
completion, the unit was not found/inactive/dead with `Result=success`, and no
matching worker process remained. This verifies one bounded supervisor/cgroup
execution, not sustained capacity or live exchange evidence.

At `2026-10-28T03:03:40Z`, during the post-run review, host memory PSI avg10
was **49.40% some / 41.21% full**, with about **9.8 GiB** available and **332
MiB** swap free. No cause is assigned to this increase; defer another heavy
check until a fresh admission sample. No
exchange request, held capture, production Arena root write, protected
service, or persistent systemd unit was used.

**Official source terms supplement — 2026-10-28 03:00 UTC:** A fresh read-only
review confirmed that public unauthenticated access is a technical API
property, not permission for Frontier's research and retention. Kalshi's
public market-data endpoints remain subject to the Developer Agreement and
the linked Data Terms; Kraken's API guidance requires prior permission for
certain uses, including non-personal commercial use of public market data;
Coinbase's Market Data Terms prohibit AI/ML development use and specified
benchmark and valuation uses. No endpoint was queried and no hold changed.
See [the detailed terms review](SOURCE_DATA_TERMS_REVIEW_2026-10-27.md).

**Candidate outcome disclosure — 2026-10-28 02:57 UTC:** Code commit
`3af51c0589c9550ff5bbf9333e24a818e75041c0` makes the candidate detail view
label worst-case values as modeled P&L and explicitly states that deterministic
replay outcomes do not establish fills, venue access, or realized profit. The
scoped component test passes **1/1** (the other seven Frontier component tests
were skipped by the filter), the saved-artifact Playwright path passes **1/1**
in 5.4 seconds, and the final production build passes TypeScript and Vite with
2,228 modules transformed. Vite still reports the existing **544.41 kB** Chart
chunk advisory. These UI checks use the explicitly intercepted fixture and
local demo services; no real-source or Arena execution evidence is added.

After the build, the host sample at `2026-10-28T02:57:42Z` measured PSI avg10
**29.83% some / 24.02% full**, avg60 **9.75% / 7.88%**, with about **9.8 GiB**
available and **332 MiB** swap free. This elevated short sample is a reason to
defer further heavy work until resources are rechecked; it does not change the
bounded test results.

**Latest Arena worker isolation checkpoint — 2026-10-28 02:56 UTC:** Code
commit `9b0b28f89832799fdcc8ff66f117e156d133be7c` adds the missing AF_UNIX-only
network restriction to launched `frontier_discovery` jobs and includes
discovery in the consistent 300-second/512-MiB/50%-CPU/nice-15/idle-I/O
validation message. The Frontier discovery tests now create a pinned fixture
job and execute it through a child process running `python -m midas.arena.jobs`;
the durable job completes and its resulting discovery artifact passes the
existing job/result verifier. A separate launch-command test checks the
systemd properties, including `MemorySwapMax=0` and
`RestrictAddressFamilies=AF_UNIX`; it mocks `systemd-run` and the admission
context, so no service or real Arena job was launched.

`tests/arena/test_jobs.py` plus `tests/arena/test_frontier_discovery.py` pass
**21/21** in 36.59 seconds pytest time / 37.28 seconds process wall, at
**193,632 KiB peak RSS**, zero swaps, and zero socket messages. One existing
Starlette/httpx TestClient deprecation warning remains. Ruff and
`git diff --check` pass. This closes fixture verification of worker dispatch
and its containment command, not systemd/cgroup runtime verification. No
source request, shared Arena-root write, protected service action, or
deployment occurred. The normal systemd job launch remains behind the shared
host admission gate.

**Latest Mission Control checkpoint — 2026-10-28 02:52 UTC:** Code commit
`4c40c7f4403d7571ae52849e6c4d10c81fa4d5c1` adds read-only candidate
inspection to saved Arena discovery-scope artifacts. Each scope resolves a
candidate only through its own pinned replay IDs and checks the candidate ID,
family, classification, audit disposition, and worst-case outputs against
that scope's summary before showing details. The panel displays exact decimal
strings for basket costs, fees, leg quotes, terminal payout/P&L, per-leg book
observation IDs, timing evidence, practical eligibility, the independent audit,
assumptions, and evidence hashes. It caps rendered detail at 50 candidates per
scope and identifies the remainder. No API, source, or Arena-worker behavior
changed.

Verification on the UI checkpoint:

- `./node_modules/.bin/vitest run` in `apps/web`: **40/40** tests passed across
  7 files in 7.85 seconds.
- `npm run build` in `apps/web`: TypeScript and Vite passed; 2,228 modules
  transformed and Vite completed in 4.71 seconds. The existing **544.41 kB**
  Chart chunk advisory remains.
- `npm run lint` passed before the E2E addition; scoped ESLint on the final
  changed TSX and E2E files passed. Prettier check and `git diff --check` pass.
- The targeted saved-artifact Playwright case passed **1/1** in 5.2 seconds
  using loopback demo APIs, temporary storage, and an explicitly labeled
  intercepted fixture. It checks expansion of the outcome, leg, and audit
  evidence. It does not execute an Arena worker or validate live exchange data.

No Python tests were rerun because this checkpoint changes only the web UI and
its browser fixture. At `2026-10-28T02:52:22Z`, memory PSI was avg10 **21.85%
some / 20.89% full**, avg60 **4.93% / 4.69%**, with about **9.8 GiB** available
and **332 MiB** swap free. This single host sample is not a capacity admission.
Candidate detail rendering is **COMPLETE AND VERIFIED** for saved fixture
artifacts; the Arena supervisor path, genuine live cross-venue evidence, and
production deployment remain pending. Project Frontier remains **PARTIALLY
VERIFIED**.

**Latest API snapshot correction — 2026-10-28 02:45 UTC:** Code commit
`3f084a99732b0cb610bafe18aacaf13fb54a92c2` fixes discovery-scope staging when
the local store contains repeated snapshots for one instrument. The bounded
store query is newest-first by local receipt time; staging now keeps exactly
one newest book per `(venue, market, instrument)` identity, preserves that
observation ID, and sorts the resulting inputs deterministically. Previously,
repeated books could be passed into a snapshot whose schema correctly rejects
duplicate instrument rows, causing a valid local research request to fail.

The regression test stores two different books for one instrument and verifies
that the latest local receipt and its record ID are pinned. `tests/frontier/test_api.py`
passes **53/53** (26.37 seconds pytest time, 27.35 seconds process wall,
284,280 KiB peak RSS, zero swaps and socket messages). The exact discovery
staging test passes **1/1** (3.17 seconds wall, 202,204 KiB peak RSS), and the
scope/math plus Arena-artifact selection passes **4/4** (2.43 seconds wall,
194,060 KiB peak RSS). Ruff, formatting, Python compilation, and diff checks
pass. No source request or Arena worker ran. This is a focused API correction;
the full suite, strict mypy, supervisor execution, live data, and production
status remain as recorded below.

**Current implementation checkpoint — 2026-10-28 02:40 UTC:** Code commit
`d59c4a8e66af7d525e65b70d90c268d3eaa92cfe` adds bounded discovery-scope
comparison through Arena. The same pinned local evidence and deterministic
replay implementation are evaluated under Polymarket-only, venue-local, and
cross-venue universe scopes. Coverage and candidate deltas are persisted in a
content-addressed snapshot and hash-checked result artifact; Mission Control
can submit, inspect, and compare those results. The endpoint makes no source
request. It compares input coverage under one algorithm, not independent
algorithm versions, and it cannot estimate venue-wide prevalence or certify
unreviewed mappings.

The complete web unit suite passes **40/40**. TypeScript, ESLint, Prettier,
Ruff, Python compilation, and the production Vite build pass; the build keeps
the existing **544.41 kB** chart-chunk advisory. A targeted Playwright history
test passes **1/1** against isolated temporary API, database, and Arena roots;
it verifies the new history view without submitting work or probing a venue.
The full Frontier plus related Arena selection completed **375 passed / 6
failed** in 79.10 seconds. All six failures were in existing general Arena job
supervision tests: a contemporaneous read-only check found the shared host
admission lock held by an active Veritas gap-detail batch (PID 4086834); four
test records remained queued and two submissions reported the lock busy. The
batch was left untouched. A follow-up mypy run was stopped after a fresh host
sample showed memory PSI avg10 at **30.44% some / 27.78% full**, with 331 MiB
swap free; strict typing for this checkpoint is therefore incomplete.

Direct Arena artifact execution, snapshot recovery, hash validation, caps,
scope math, the Frontier API staging boundary, and the UI submission/result
rendering are fixture-tested. An actual Arena supervisor job for the new kind,
resource sustainability, genuine cross-venue mapping, live source validation,
and deployment remain unverified. Project Frontier is **PARTIALLY VERIFIED**.

**Latest implementation checkpoint — 2026-10-28 02:16 UTC:** Feature commit
`4bd3b7f2636d5cd8d069fb2e2b2e97188ad68247` adds bounded conditional
multi-market joint-state basket replay, an independently recomputed payoff
audit, the stored-evidence API, and an explicit Mission Control mapping editor.
Browser test commit `b0f38c2` adds an end-to-end fixture flow for explicit map
submission. Differential test commit `29f1a5b` adds seeded subset-oracle tests
and a bounded 64-state performance harness; optimization commit `bc8d073`
caches exact per-instrument payout vectors and incrementally sums candidate
subsets. The focused randomized differential passed and the full
Frontier Python suite passed **343/343**. The full web unit suite passes
**40/40**, the production build passed, and the Frontier Playwright spec passes
**5/5**, including the fixture-only map flow. The synthetic 12-instrument,
64-state search improved from a **5.122-second** one-candidate median to
**0.102 seconds**, at the cost of about 32 MiB more peak RSS. These are isolated
local/fixture checks only. A shared-state map
is an unauthenticated external assertion, so it cannot establish economic
equivalence; live cross-venue validation and the broader Frontier acceptance
remain incomplete.

**Latest virtual funding / terminal P&L checkpoint:** code commit
`71ee203b033c4bc0f38afce09b5255fe31bcae21` extends the saved-run funding
sensitivity to expose a separate outcome-level P&L result after modeled
conversion costs. It is available only when the candidate and funding audits
verify, candidate fees are complete, and each venue-local balance covers its
recorded requirement. A separate rational audit checks every terminal state;
the candidate's stored P&L, classification, and practical eligibility remain
unchanged. Incomplete or disagreeing evidence returns no adjusted state values.
Full Frontier Python regression passed **325/325** (51.73 seconds wall,
365,976 KiB peak RSS, zero swaps/socket messages). The Web suite passed
**40/40**; the Frontier browser spec passed **4/4** against isolated test
services. TypeScript, targeted ESLint/Prettier, Ruff, strict scoped mypy for
`fx.py`, and the Vite production build passed. The build retains the 544.41 kB
Chart-chunk advisory. One existing Starlette/httpx deprecation warning remains.
No exchange request, protected service, production store, external worker, or
deployment was used. Live FX, cross-venue funding availability, source
permissions, and production readiness remain unresolved.

**Branch:** `codex/frontier-20261026`

**Prior browser baseline (2026-10-28 00:27 UTC):** Commit
`86b79fe10b6aed82dabbe3e40ea01e08923ad744` added fixture-backed funding-currency
browser coverage and passed the configured **12/12** E2E suite. The latest
change reran the full Frontier browser spec (**4/4**) after extending the
response model. Both are isolated fixture evidence, not live FX or executable
cross-venue economics.

**API type checkpoint (2026-10-28 00:35 UTC):** Commit
`480ba629171c855086cd375a34e688bbc72fdbcb` types the Frontier router's
registry parameter as `AdapterRegistry` instead of `Any`, removing the
adapter-lookup `no-any-return` diagnostic. Strict mypy passes for
`apps/api/frontier.py`; Ruff and format checks pass. The isolated API overview
test passes **1/1** in 0.70 seconds at **77,492 KiB peak RSS**, zero swaps, and
zero socket messages. The test has one pre-existing Starlette/httpx
deprecation warning. The 322-test Python suite and 40/12 web/browser suites
passed at the prior checkpoint and were not rerun after this annotation-only
change.

**Worktree:** `/home/charlie/midas-frontier`

**Baseline:** `11d32a0693b25c290fd273f23e40cf7b5950d95d` (`codex/veritas-v6-integration-20261026`)
**Disposition:** substantial isolated research implementation; **Project Frontier is not complete, deployed, or production-ready**.

## 1. Executive summary

Frontier adds an isolated, research-only market-data foundation for Polymarket,
Kalshi, Kraken spot, and a fixture-validated Coinbase Exchange spot adapter. It has versioned venue-aware contracts, a bounded
public-GET adapter protocol, capability declarations, normalizers, an append-only
SQLite evidence store, relationship hypotheses and append-only review revisions,
an explicit payoff-equivalence check, five narrowly bounded Decimal
opportunity families,
deterministic replay, local API routes, and a native Mission Control workspace.

An official source-terms review on 2026-10-27 adds a live-data permission
boundary: Kalshi capture is blocked pending written research/retention
authorization, and Kraken capture is blocked pending review of applicable
market-data terms and any required permission. Their adapters remain available
for offline fixtures. Previously captured source artifacts remain preserved
and are quarantined from Frontier application reads, graphs, candidate/replay
views, and Arena replay result APIs while the hold is active. Direct database
inspection and exports remain within the operational hold.

A later test-source audit found 15 direct references to preserved capture files
in `tests/frontier/test_adapters.py` and `tests/frontier/test_api.py`. The full
Frontier suite recorded at 18:41 UTC executed those cases and therefore read
the referenced files, contrary to the test-fixture boundary then documented.
No test writes to the capture directory were identified, and no capture
mutation is known. All 15 path references have now been replaced with synthetic
inline inputs. A path-text scan over `tests`, `packages`, and `apps` finds no
remaining `live-probes` reference. A static Python-test guard passes, the
changed adapter/API selections pass, and the full Frontier suite passes **219
tests** after conversion. The earlier 18:41 suite remains evidence of code
behavior on held inputs, but must not be cited as fixture-only held-source
validation. See the updated [source-data terms review](SOURCE_DATA_TERMS_REVIEW_2026-10-27.md).
An autouse runtime guard for common file-open calls was added and verified in
the subsequent 219-test run. A temporary-path regression covers path strings,
symlink traversal with `..`, and `dir_fd` access; no preserved capture was
opened.

The Polymarket, Kalshi, and Kraken adapters have fixture/contract coverage and
bounded prior live evidence; Coinbase Exchange is now implemented against the
official public product/book/trade schemas and locally controlled fixtures,
but has no live capture because its reviewed data terms impose scope and
redistribution limits. The exact terms revision is held behind an explicit
operator acknowledgement and a separate network opt-in. Polymarket also
has an explicitly triggered, cursor-paginated Data API v2 trade-page path that
preserves outcome token identity through normalized storage. One genuine v2
first page was captured directly, then one continuation page was captured
through the isolated Frontier API route using its opaque source cursor. Each
made one public GET, returned ten trades, and was hash-verified through a
temporary store. Their trade IDs did not overlap. No third page was requested.
Kalshi now has a separate ticker-filtered, cursor-paginated public trade-page
operation, bounded to one saved market and at most 100 rows. A genuine API round
trip captured an empty Kalshi page with an empty continuation cursor; fixture
tests cover trade-row normalization and cursor errors.
Saved Kalshi event and series metadata drives a bounded standalone fee
sensitivity for one hypothetical taker fill and, on later replay, a separate
provenance-bound candidate fee estimate when complete supported evidence passes
the quote-time, freshness, raw-hash, and identity gates. The standalone
sensitivity supports two documented quadratic fee types and shows direct and
non-direct balance-precision cases. Candidate replay models one fill under a
conservative non-direct precision assumption; it does not establish an account
fee quote. Manual sensitivity price and quantity remain scenario assumptions,
not observed quotes or captured fills.
Kalshi's event fee-change API documentation now informs an explicit override
resolution state. The fee workbench rejects sensitivities when event override
fields are missing or partial, and accepts only a complete pair or a
documented null/null clear. This is fixture-verified; no new source capture or
research over held Kalshi data was performed.
The current replay path can compile a saved, hash-checked event/series pair into
a provenance-bound estimated Kalshi taker fee for supported quadratic schedules.
The estimate is limited to one fill, uses source metadata no later than the
book quote and at most 24 hours old, and applies the documented non-direct
balance precision as a conservative scenario. Replay schema v2 separately pins
the fee metadata observation IDs; Mission Control displays their count. The
candidate remains conditional or incomplete, and an independent audit repeats
the estimate from pinned evidence. This is fixture-verified implementation;
there was no source request or held-data read during this checkpoint.
Current touched versions are FrontierMarket schema v4, Kalshi adapter v17,
economic model v10, independent audit v7, and deterministic replay v10. The
latest Kalshi metadata addition preserves exact `price_ranges` values and
enforces reported ranges in both candidate generation and the independent
audit. The `start`-anchored step grid is an implementation inference from the
public schema shape; inclusive/exclusive boundary semantics remain unspecified
and boundary quotes fail closed.
Kalshi adapter v7 added a separate one-page multivariate-event lookup filtered
by exactly one series or collection ticker. A genuine public response returned
one event and a source cursor, but omitted its nested `markets` field despite
the requested flag. The raw response and the v6 normalization failure are
preserved with hash-verified temporary-store read-back. The API/UI retain that
event as a `MarketGroup` whose member-list state is `omitted`, with zero
normalized child markets; omission is not treated as an empty market group.
Adapter v8 also corrects event-detail normalization for a documented top-level
empty `markets` array. Neither response supplies child contracts or combo
payoff semantics.
Adapter v9 adds a bounded filter for one event ticker using Kalshi's documented
`tickers` parameter and validates the returned event identity. Its saved public
capture also omitted nested markets, this time with no cursor; it verifies the
single-event lookup path, not child-contract coverage or economics.
Adapter v10 adds one public market-detail lookup for a child ticker already
listed in a saved combo's selected-component metadata. It validates the
parent-bound market/event identities and persists the raw and normalized child
record. A one-request capture returned the first child of a saved basketball
combo, with a closed lifecycle and rules that include fair-price fallback
conditions for inactive/non-playing and postponed events. The child has no
captured book or price, and neither its standalone payoff nor the parent combo
payoff is verified.
Relationship matcher v5 adds an explicit `source_component_reference` edge
when the saved parent names that child and a separately captured child record
matches its native ticker and event ID. It stays a hypothesis and cannot support
economic calculations.
Kalshi adapter v11 preserves the optional selected-leg
`yes_settlement_value_dollars` field as a bounded exact Decimal and exposes it
with its source name in Mission Control. The official event schema documents
the field; Frontier does not infer combo payout from it. The live child capture
does not contain the field, so this addition has fixture/schema-shape
verification rather than live-field verification. Commit `d6d4540` also verifies
that a documentation-shaped fixture value survives API serialization and
temporary-store read-back.
Adapter v12 adds a separate saved-record arithmetic comparison of selected-leg
settlement values against the parent market's recorded settlement value. It is
fixture-verified, source-read-free, and excluded from candidate economics; no
live settlement values were present to run it against.
Bounded live round trips through each adapter and
the Frontier probe API persisted one
listing per venue, then one listing plus at most one book per venue, and most
recently one listing, one book, and up to ten public trades per venue, to
separate temporary SQLite stores. The raw responses and normalized read-backs
are hash-verified and committed. The latest sample had 8 asks/10 bids and 10
trades on Polymarket, 10/10 and 10 trades on Kraken, and an empty Kalshi book
and trade array. These books and prints were collected sequentially and do not
establish synchronized or executable states.
The observations do **not** establish a verified cross-venue event equivalence.
No economically eligible opportunity was established. Controlled mathematical
fixtures test the verifier; they are not market findings.

Replay now runs a separately implemented Decimal audit over each generated
candidate. It independently reconstructs positions, payoff states, pinned ask
prices and depth, applicable fees, basket cost, and terminal P&L from the
normalized markets and books. A versioned SHA-256 pins its candidate, input
evidence, relationship mappings, and scenario. The audit found and helped fix a
canonical relationship-mapping order defect that had allowed a replay regression
to pass with an empty candidate list. This is independent arithmetic over shared
normalized evidence; it does not independently validate exchange truth, source
timing, external resolution documents, or real execution.

Replay v5 retains effective relationship mappings and the relationship
proposal limit in each normalized-input digest. A bounded paired-replay path runs
two named scenarios over the same saved markets, books, verified relationships,
effective mappings, code version, and UTC time; its shared evidence digest omits
only the per-arm scenario. It stores both replay arms and the comparison
atomically. The comparison reports matched construction counts and modeled
classification/count deltas without assigning an improvement score. The
workbench exposes the result, but no genuine live cross-venue pair exists in the
captured evidence and paired fixture outputs are not market findings.

Replay v6 overlays the immutable SQLite observation record ID onto market and
book provenance whenever the API loads those models for research. Replay
manifests, candidate legs, and Arena snapshots now point to records that can be
resolved through the observation API. Direct in-memory adapter replay keeps its
deterministic adapter-derived identities. The replay version pins this input
identity change; the schema and previously stored evidence rows are unchanged.
The focused integration tests carry saved public Polymarket and Kalshi event
responses through adapters, API, storage, relationship proposal, deterministic
replay, and paired replay, and verify exact record references. A controlled
book row separately verifies API readback, replay-manifest provenance, and the
content-addressed Arena snapshot. This establishes record lineage in fixture
and local-store research, not live cross-venue equivalence or economics.

Economic model v4 adds an exact one-sided full-or-no-fill terminal sensitivity
for the supported binary and multi-outcome constructions. The candidate and the
separate audit identify the worst adverse leg pattern across all `2^n` patterns
for up to 16 legs. This assumes each leg either fills fully or not at all at its
modeled price; it does not estimate fill probabilities, partial fills, hedging,
or unwind recovery. Unknown applicable fees leave the after-fee sensitivity
unknown. Replay v5 pins this added candidate output. A fixture differential
check exhaustively enumerates all eight patterns for a three-leg case and agrees
with the analytic result; it does not provide live market or execution evidence.

The bounded probe API now preserves a successful HTTP response whose JSON shape
fails adapter normalization as an append-only source-failure observation. Its
error response returns the observation ID, and source health reports the venue
as degraded until a later successful probe. Invalid JSON is rejected inside the
transport before a normalized response is built, but complete response bytes are
still preserved as an append-only source-failure observation. Invalid UTF-8 is
stored losslessly using base64 with the SHA-256 computed over the original bytes.
Oversized responses are rejected without storing a partial body.

The implementation deliberately stops short of full acceptance. It now has a
self-attributed review workflow, but reviewer and external assertion IDs are
references only; MIDAS does not authenticate the reviewer, fetch the assertion,
or verify the source truth of stored market fields. There is no continuous
collector, complete venue universe, multi-hop paginated graph service,
logical-implication or general multi-leg solver, FX model, full
cost/capital-transfer model, or integrated Arena/Laboratory experiment scheduler.
Public book snapshots never set
`practical_eligibility` to true. No Frontier source is enabled for network access
by default, and the worktree has not been merged or deployed.

## 2. Baseline architecture

The isolated starting point was the verified Veritas V6 integration commit
`11d32a0`, not `main`. That baseline contains the Veritas V6 integration and
Research Readiness work. The legacy Polymarket implementation remains the
reference for strict venue-specific behavior: `packages/midas/market_data`,
CTF-specific payoff checks, existing fee handling, and the prior Reality and
Veritas storage paths.

At mission start, `/home/charlie/midas` was on `main` at `55601b9` with unrelated
modified and untracked work. The Reality reliability worktree also held unrelated
operational/evidence changes. Those trees were not changed. The selected baseline
worktree was clean, and Frontier was created as a separate worktree and branch.
The other inspected worktrees included Reality (`4f5cb568`), Veritas
(`3b102928`), Reality reliability (`4278b5b5`), and the V6 integration baseline
(`11d32a0`). The initial ledger’s claim about an active Veritas market-coverage
scope was not used as a current-state fact; it is superseded by this report.

The existing market and recording types encode Polymarket/CTF conventions and
single-source replay. Frontier therefore uses a new package and separate data
root. It does not reinterpret legacy data, connect to Reality’s recorder, or
change frozen evidence.

## 3. Frontier architecture

The primary layers are:

1. `packages/midas/frontier/models.py`: versioned venue, instrument, payoff,
   resolution, fee, quantity, book, trade, candle, health, event-group, and provenance types.
2. `adapters/base.py`, `adapters/transport.py`, and four venue adapters:
   capability-checked, HTTPS GET-only, source-specific parsing and validation.
3. `relationships.py` and `economics.py`: conservative proposals, explicit
   payoff comparison, and bounded outcome-state arithmetic.
4. `independent_audit.py`: a separately coded candidate arithmetic audit over
   pinned normalized contracts, books, relationships, and scenarios.
5. `storage.py` and `replay.py`: isolated bounded evidence persistence and
   deterministic and paired replay over pinned local inputs, including audit
   results and typed diagnostics for captured responses that fail normalization.
6. `apps/api/frontier.py`: bounded local reads, explicit proposal/replay writes,
   bounded graph-neighborhood queries, and separately configured public captures,
   including Kalshi multivariate events.
7. `apps/web/src/Frontier.tsx`: native Mission Control research workspace,
   one-page Kalshi MVE discovery, and paired-assumption workbench.

The four adapters are registered at API construction, but that action is
local-only. Network access is gated separately for each source. There is no
Frontier API key type, account endpoint, wallet, execution method, or order
submission route.

## 4. Exchange integrations and capability matrix

| Venue | Implemented public research | Preserved distinctions and limits | Live evidence |
| --- | --- | --- | --- |
| Polymarket | Gamma v1 CTF-token and v2 position-ID discovery; v1-host public CLOB books; v2 position books routed to the documented `clob-v2` host; legacy public trades and cursor-paginated Data API v2 pages; native token/condition/event IDs; strict normalization, supported fee-shape handling, and bounded parent-event group capture | V1 settlement identity remains absent. V2 position markets map to the documented Polygon pUSD token identity, but market-specific payout and resolution remain unverified. The v2 book route is fixture-tested only because `clob-v2.polymarket.com` did not resolve from this development host. No incremental book stream or candle normalization; fee schedules expire after five minutes and unsupported exponents remain unknown; v2 condition history is fixed to three years and page capture uses taker-only trades with a 0.01-share floor. | Earlier live API evidence persisted one listing, one book, and ten trades through the older trade path. A direct v2 first page and one continuation through the local API route each returned ten rows and were hash-verified via isolated stores; no third page was requested. A one-market listing captured a market-specific `zero_fees` schedule at 20:41:18.972060Z, with `feesEnabled=true`, exponent 1, taker-only, rate 0; normalized status was verified only through 20:46:18.972Z. The 2026-10-27 v1-host book probe returned HTTP 200, 58 bid levels and 8 ask levels, body SHA `cecdb8d4f14fa61a7039e1559a52e02c2e7819a0342566f5d07d829841bc9aef`; this is one current public snapshot, not V2-host or settlement validation. |
| Kalshi | Public market listing and ticker-bound detail; binary YES/NO instruments; public book snapshots/trades; ticker-filtered cursor trade pages; event/series fee metadata; one-fill and one-order taker-fee sensitivities; bounded event groups and MVE event discovery; adapter v16 retains v4 normalization of up to 64 native MVE selected component references | MVE selected legs remain conditional source assertions, not verified component rules, combo payoff, or settlement equivalence. Adapter v10 adds a single-market detail GET only for a child ticker referenced by a saved parent MVE; the API checks market and event identity, persists the raw/normalized row, and includes `market_metadata` in market query and graph revisions. Adapter v8 accepts the documented top-level empty event-market array when the event-level field is omitted; v9 adds the single-event `tickers` filter. Asks are derived from complementary YES/NO bids where applicable. Trade pages normalize `yes_price_dollars` as a YES-price reference and preserve `no_price_dollars` and taker fields only in raw evidence; no BUY/SELL aggressor direction is inferred. Complete saved event/series fee evidence can now inform a separate conditional one-fill candidate estimate in replay. Actual account precision, maker/mixed-order behavior, FCM charges, schedule changes, and exact account applicability remain unresolved. No stream or historical-candle normalization. | Earlier listing/book/trade/event/fee captures remain hash-pinned. The one MVE child capture returned HTTP 200 with raw SHA `0f1c3cd42cac5202ca5a3012d58cb8d9631bf39cce313c738bb0448140271eda` and temporary-store row SHA `a2e7ae0c08436155a0bdc80e07f16d6b882eaf9706617994be135b668ec5897a`. Its source ticker and event matched the saved parent reference; the child was closed and its rules describe fair-price fallbacks. It contains no child book/price, does not establish combo payoff, and does not create cross-venue economics. |
| Kraken Spot | Configured-pair AssetPairs metadata; public depth, trades and OHLC; pair tick/lot/minimum fields retained | Spot is a base/quote instrument, not an event payoff. Fee tier, account eligibility, custody, and event hedge semantics are unknown. Pair discovery is an explicit allowlist. | Bounded live API capture persisted XBT/USD metadata, depth with 10 asks/10 bids and per-level timestamps, and ten trades. No prediction-contract equivalence was found; new capture and research remain held. |
| Coinbase Exchange Spot | Explicit allowlisted product metadata, aggregated L2 snapshots, and one bounded trade page; public source `sequence`, `time`, `auction_mode`, maker-side, increments, and minimums remain raw-evidence linked | Spot context only; no event payout, candles, incremental book, verified fee schedule, settlement rule, or account eligibility. Product catalog is not enumerated. Coinbase Market Data Terms restrict use; an exact reviewed-version acknowledgement and independent probe flag are required. | **No Coinbase request made.** Synthetic fixture contract tests only; live validation is pending because the terms/organization/region/display scope is not independently resolved. |

### Additional venue screen and admission recheck — 2026-10-27 21:42 UTC

Manifold Markets was evaluated as a possible additional public source. Its
documented public API supports unauthenticated reads, but Manifold's official
February 2025 announcement ended its sweepstakes markets; current FAQ says
mana cannot be converted to cash. That makes current market prices useful only
as a possible forecast/sentiment reference, not an economic payoff or
opportunity leg. The site's prize drawings are separate from market
contracts. A forecast-only adapter is not added because it would need a
separate non-economic instrument type and a focused research need.

Betfair Exchange was evaluated as a potential event-market venue. Its official
API requires account application keys; the delayed key is for development and
returns production data delayed by 1–180 seconds, while documented live
read-only access is not permitted. Commercial use requires approval. Frontier
does not create accounts or credentials, so a Betfair integration is deferred
until an independently authorized data-access path exists. No Manifold or
Betfair API request, account action, or historical-data access occurred. The
source screen and references are recorded in
[`ADDITIONAL_VENUE_SCREEN_2026-10-27.md`](ADDITIONAL_VENUE_SCREEN_2026-10-27.md).

At `2026-10-27T21:42:51Z`, the deferred legacy compatibility selection was
still not admitted: external batch PID **3745206** remained in `D` state and
held the shared Arena admission lock. PSI avg10 was 39.31% (`some`) / 34.14%
(`full`), avg60 42.01% / 36.47%, and avg300 33.22% / 28.94%. No test was
started and the external worker remained untouched.

### Legacy integration and Arena replay compatibility closure — 2026-10-27 21:45 UTC

After the batch exited and PSI avg10 settled, the compatibility selection
passed on the current Frontier worktree with the package path explicitly set
to `packages:.`. An import-path check resolved `midas` to
`/home/charlie/midas-frontier/packages/midas/__init__.py`. The exact command
was:

```text
PYTHONPATH=packages:. /usr/bin/time -v /home/charlie/midas/.venv/bin/pytest tests/integration/test_adapters.py tests/integration/test_api.py tests/integration/test_recording_isolation.py tests/arena/test_frontier_replay.py -q
```

All **28 tests passed** in 5.96 seconds pytest time / 7.32 seconds wall, at
**282,584 KiB peak RSS**, with zero test-process swaps. The sole warning is the
existing Starlette/httpx `TestClient` deprecation. The selected tests use
repository fixtures, mock transports, temporary recording/database roots, and
direct deterministic Arena replay; they did not submit any exchange request
or start a supervised research job. Immediately after the run, no shared Arena
lock holder was present, memory PSI avg10 was 0.01% (`some`) / 0.00% (`full`),
9.9 GiB was available, and 455 MiB swap was free. The earlier
`2026-10-27T21:39:36Z` deferral is resolved for these four modules; the broader
repository suite still has separately documented collection and host-gate
limitations.

Each adapter declares every shared capability as supported or unsupported with a
reason. Kalshi documents unauthenticated public market-data access and its
binary order book returns YES/NO bids, with complementary prices used to infer
the other side; Frontier retains that source-specific rule rather than treating
the returned arrays as generic asks ([Kalshi public market-data guide](https://docs.kalshi.com/getting_started/quick_start_market_data),
[Kalshi order-book specification](https://docs.kalshi.com/api-reference/market/get-market-orderbook)).
The public [Get Event](https://docs.kalshi.com/api-reference/events/get-event)
and [Get Series](https://docs.kalshi.com/api-reference/market/get-series)
endpoints now have a separate metadata-only adapter operation. The event request
sets `exclude_markets=true` so the response stays bounded; the adapter retains
event-level override field presence and values, the series `fee_type` and
`fee_multiplier`, request/receipt times, and hashes of both raw responses. An
isolated live route run at `2026-10-26T23:16:17.916305Z`–
`2026-10-26T23:16:18.408650Z` listed one MVE market, then captured its event and
series metadata with exactly three unauthenticated GETs total, zero retries, a
65,536-byte response cap, no book/trade requests, and an 8 MiB temporary store.
The event contained no override fields; the series supplied
`quadratic_with_combo_maker_fees` with multiplier 1. All three raw hashes and
temporary-store row hashes were verified. Artifact:
[`2026-10-27-kalshi-public-fee-metadata.json`](../../data/frontier/live-probes/2026-10-27-kalshi-public-fee-metadata.json),
SHA-256 `4a2e1ac8e2953314e89f26fa825142b551ce0a24512a14e3494df03b936ea53e`.
This is one public metadata sample, not a fee schedule survey or account fee
quote. Kalshi's help page says fees vary for some markets, while its published
rounding model depends on member balance precision and per-order accumulation;
therefore the canonical `FeeSchedule` remains unknown and no fee is calculated
from these parameters ([Kalshi Fees](https://help.kalshi.com/en/articles/13823805-fees),
[Fee Rounding](https://docs.kalshi.com/getting_started/fee_rounding)).
The official July 7, 2026 fee-schedule PDF lists the distinct `KXMVE` row with
maker multiplier 2 and taker multiplier 1. The captured source series is
`KXMVECROSSCATEGORY`, whose event/series API evidence instead reports
`quadratic_with_combo_maker_fees` and multiplier 1, with no event override.
Frontier does not assume these different series identifiers are interchangeable
or apply the `KXMVE` maker multiplier to this evidence. The current sensitivity
remains taker-only; maker-fee mapping to the exact native series is unresolved
([July 7, 2026 Fee Schedule](https://kalshi.com/docs/kalshi-fee-schedule.pdf)).

Kalshi's documented
[`GET /trade-api/v2/events/multivariate`](https://docs.kalshi.com/api-reference/events/get-multivariate-events)
supports `series_ticker` or `collection_ticker`, `with_nested_markets`, and a
source cursor. Adapter v7 adds a capability-gated API operation accepting
exactly one filter, requests `limit=1` with nested markets, and does not follow
the returned cursor. The API persists a v2 `MarketBatch` containing typed
`MarketGroup` context alongside child contracts when present. Event grouping is
not a payoff or event-equivalence claim.

The preserved October 27 response was fetched using collection
`KXMVECROSSCATEGORY-R`, identified from the prior saved public market listing.
It returned HTTP 200, event
`KXMVECROSSCATEGORY-S2026ZZZB25KKPHBN3TFC`, and a nonempty cursor, but the event
had no `markets` field despite `with_nested_markets=true`. Its original adapter
v6 normalization therefore failed closed and the raw capture plus typed
`SourceFailureRecord` were stored and read back with verified hashes. Adapter
v7 now replays the same saved response as one event group with
`member_list_state="omitted"` and zero normalized markets. It does not turn
the missing list into an empty list. The capture artifact is
[`2026-10-27-kalshi-multivariate-page-r1.json`](../../data/frontier/live-probes/2026-10-27-kalshi-multivariate-page-r1.json);
its raw SHA-256 is `f04f5a2a0421a349e338828a9ba219352e841d5a7729247778cfbe47a5fa570d`
and temporary-store row SHA-256 is
`a8fa28b85e0474bab7ba62e7ab2b74785198aedeaba1228fdac7294ca100ebea`. No page
was followed and the response contains no order books, child prices, or payoff
evidence. Two earlier one-request attempts were lost when the temporary probe
harness failed after receiving the source response; they are disclosed but not
used as evidence. The final retained attempt used one GET, zero retries, a
262,144-byte cap, and an isolated 8 MiB store.

The MVE normalizer distinguishes a missing `markets` field from an explicit
empty array; an explicit `null` is rejected as invalid schema. The fixture/API
regressions cover nested members, source omission, malformed member identity,
and explicit-null rejection. The Mission Control result includes the member-list
state so operators can see omission directly and can expand the saved raw
response from immutable storage. A fixture-backed browser scenario
for this control is present in `apps/web/e2e/frontier.spec.ts`; it was enumerated
but not executed at this checkpoint.

A second read was then made against the official event-detail path for the same
saved MVE ticker. It returned HTTP 200 in one unauthenticated GET (zero retries,
262,144-byte cap) with event metadata, no `event.markets` field, and an explicit
empty top-level `markets` array. The raw SHA-256 is
`4dff6f7d770dff3a7564b5cf0558ff0c21862977d52a360a93f5b10f436afa83`; the
initial v7 failure row SHA-256 is
`3cd24ab39df2a766e6118aee59f48e9e8142880ec5d15f77340252981b5f434f`. Adapter
v8 now replays the same raw body to a valid empty `MarketBatch` in a separate
temporary store; that replay row SHA-256 is
`c47a0e7827849c886c2c3e290d16035e1a87c26b602d028217c90f9b58c760aa`. The
original capture and failed-normalization record remain intact. This is an
explicit empty array in one event-detail response, not proof that no related
market exists elsewhere or that the combo has a particular payoff. Artifact:
[`2026-10-27-kalshi-mve-event-detail-r1.json`](../../data/frontier/live-probes/2026-10-27-kalshi-mve-event-detail-r1.json).

Kalshi adapter v4 also parses the documented `mve_selected_legs` field into
typed source-declared components, preserving each selected native event ticker,
market ticker, and YES/NO side. Normalization rejects duplicate, malformed,
self-referential, or over-64 component lists; the raw market fields remain
available for audit. The Mission Control market inspector renders these
components beside an explicit notice that they do not certify component rules,
combo payout, or resolution equivalence. Kalshi's public [Get Multivariate
Events](https://docs.kalshi.com/api-reference/events/get-multivariate-events)
schema exposes selected event/market/side fields. Its [Market
FAQs](https://help.kalshi.com/en/articles/13823821-market-faqs) describe combo
payout as the product of the underlying position values and say combos undergo
their own settlement review. That source-level payout description is not enough
to verify this captured market: its `rules_primary` is empty, its `rules_secondary`
contains only a general disclaimer, and the captured listing does not include
the complete rule and settlement evidence for all selected components.

The preserved listing response in
[`2026-10-26-public-source-probe-r2.json`](../../data/frontier/live-probes/2026-10-26-public-source-probe-r2.json)
has raw SHA-256
`5285d145fed96c70a727e7573b7a7094a69790da18bb1d1eff1fc6b840073f14` and lists
`KXMVECROSSCATEGORY-S2026KCUDJTPZBDVDK2OZ-ISTID3QWK` with 17 selected YES/NO
components. Replaying the preserved bytes through adapter v4 was local and
fixture-driven; no new live probe was made. The observation is dated and its
expected expiration was `2026-10-27T06:15:00Z`; it is source-structure evidence,
not current market status or opportunity evidence. No MVE payoff was promoted
or evaluated by candidate economics.

Kalshi's documented [Get Trades](https://docs.kalshi.com/api-reference/market/get-trades)
endpoint supports ticker filtering, a source cursor, and pages up to 1,000 rows;
Frontier deliberately caps its explicit page at 100. The isolated trade-page
capture ran at `2026-10-26T23:29:53.349697Z`–
`2026-10-26T23:29:54.049333Z` with one listing GET and one ticker-filtered
trade GET, zero retries, 65,536-byte caps, and an 8 MiB temporary store. Both
responses were HTTP 200. The selected ticker
`KXMVECROSSCATEGORY-S2026AI6WGLUADXUYU2PZ-PGLXFSG4I` normalized as a
conditional event; the page contained no trades and no next cursor. Its raw
hashes are `ccd9144ebab67664ef0b724925d97fe597f906b9b26e30be421cf43d269f4d4c`
and `ce91679332b1b83d2574366e4cc72f6d41bf656ccc2fa9cf574ee4f9ac6809e7`; row
hashes are `72e105ad6b96f6d0968fb68822016bb7384fdc5f65956219343e219cf07e389b`
and `cc12462c22bd77a76bb674c8ace8b9b081726e032a4ff981c7ee17980e19c51a`.
The manifest SHA-256 is
`94cb4aeed436c5ac6b7d1175f99532fea57caa2b8d998600bf332451e0bcd06b`; the
serialized artifact SHA-256 is
`7439cdb2ab02d766d174257953d3bf967cbd933df5683c4c799938fedf122b04`. Because
the live page had no rows, only the adapter's empty-page and termination behavior
were validated against the genuine source; trade-row mapping remains fixture
verified. This observation provides no liquidity or cross-market economics.
Kraken’s public spot pair metadata and depth endpoints support the spot adapter,
but do not make spot a prediction-contract payoff ([Kraken AssetPairs](https://docs.kraken.com/api-reference/market-data/get-tradable-asset-pairs),
[Kraken order book](https://docs.kraken.com/api-reference/market-data/get-order-book)).
Polymarket’s data model links events, markets, and outcome token identifiers;
the wrapper preserves that structure while keeping payoff attestation separate
([Polymarket market-data overview](https://docs.polymarket.com/market-data/overview)).
The adapter accepts only Gamma schedules with `feesEnabled=true`, an explicit
rate, `takerOnly=true`, and exponent 1; an explicit `feesEnabled=false` is
represented as zero, while unsupported or incomplete shapes stay unknown. The
captured Gamma `feeSchedule` is hashed into the normalized record, sourced to
Polymarket's [fee formula](https://docs.polymarket.com/trading/fees), and expires
after five minutes. Tests verify both a nonzero fixture schedule and rejection
of an exponent-2 schedule. The October 26 live capture was a single zero-fee
market, not a venue-wide fee survey. Gamma market details expose market-specific
fee fields ([Market Details](https://docs.polymarket.com/market-data/market-details)).

The public [Polymarket Data API v2](https://data-api.polymarket.com/v2/docs)
trade feed uses an opaque cursor-only keyset envelope. A condition query is
limited to a fixed three-year window; its cursor carries the seek anchor and
page size, so Frontier resends the same condition and trade filters on every
page. The implementation makes one explicit GET per requested page, capped at
100 rows, and preserves each row's token ID, outcome label/index, transaction
hash, share quantity, price, and block timestamp. Source wallet/profile fields
are retained only in the bounded raw response, not normalized into Frontier's
trade record. The wrapper cursor binds the source cursor to the condition and
page size; it is not a wallet or account token. Two-page cursor behavior,
filter stability, raw/normalized persistence, malformed-cursor rejection, and
market mismatch handling pass fixtures. One direct ten-row first page and one
ten-row continuation through the local API route were also captured live and
hash-verified. The second page advertised another cursor; no third page or full
history walk was requested. Earlier ten-trade samples used the legacy public
trades path.

Kalshi's event/series fee metadata is captured and linked to raw responses.
Complete supported metadata can inform the replay's explicitly estimated
one-fill taker cost, but account-specific schedule applicability, fee-change
timing, balance precision, maker/mixed-order charges, FCM charges, and
multi-fill rounding/rebates remain unresolved. The estimate is not an executable
account cost. Kraken's public pair data does not establish the account's current
fee tier. Its trade-volume endpoint is authenticated, which Frontier does not
call ([Kraken Get Trade Volume](https://docs.kraken.com/api-reference/account-data/get-trade-volume)).
No fee is guessed for Kraken.

The transport allows only HTTPS GET to an adapter’s host list, rejects redirects,
uses bounded timeouts/retries/rate, and caps response bytes. The default per
source request rate is 1 request/second; the configured maximum is 5. Response
size is capped at 256 KiB. A single API capture accepts at most 20 markets and
may include one book and at most ten public trades for one discovered market.
Kraken requests only configured symbols. This is bounded sampling, not a
universe crawler.

## 5. Canonical data and economic models

The canonical schema retains venue and native market/instrument identity,
instrument type, base/quote/settlement assets, quantity units, payout state
vectors, resolution text/authority/timing, lifecycle, constraints, fee status,
quality flags, source timestamps, raw-response hash, and adapter/schema version.
Parent event titles and source outcome labels are separate optional fields, so
event-group context does not replace the child market question. Unknown fields
with economic consequences remain unknown. Raw native metadata is kept alongside
normalized values for inspection.

The supported structures include binary and multi-outcome event-market records,
conditional-event records, and Kraken spot pairs. This is a schema and parser
coverage statement, not proof of economic support for every category. Payoff
verification remains false for normalized public listings until a separate
review supplies complete states, resolution evidence, and settlement terms.
Derivatives are represented as a future kind but are not currently normalized
or evaluated.

Prices, quantities, payout vectors, fees and scenario inputs use `Decimal`.
Models reject non-finite values and unexpected fields. Venue-native IDs and
source fields remain available so calculations can be checked against the
original response.

The market's settlement asset identity now also anchors price denominations.
`MarketInstrument`, `BookSnapshot`, `FeeSchedule`, `TradeObservation`, candidate
legs, and candidate capital retain exact identities alongside their display
currency codes. Binary, implication, and multi-outcome economics require exact quote identity
agreement from payoff to instrument to observed book, and fee arithmetic
requires the fee unit to match. Candidate capital comparisons use the exact
settlement identity; the UI separates virtual balances by venue and canonical
identity. A token whose code is `USD` cannot be added to, compared with, or
funded from `fiat:USD` without an explicit valuation model. Legacy records that
lack identity remain readable, but the candidate and audit paths classify them
as incomplete. FrontierMarket schema v4, BookSnapshot v2, TradeObservation v3,
OpportunityCandidate v2, economic model v10, independent audit v7, and replay
v10 pin this extension. Schema v4 also carries optional exact-decimal Kalshi
price-increment ranges, with absent and explicitly empty ranges distinguished.

## 6. Relationship graph

`relationships.py` builds a deterministic, bounded index using venue-local native
event IDs, cross-venue title tokens, and similar parent-event titles paired with
market-specific outcome terms. The parent-context path rejects conflicting
explicit four-digit years. Cross-venue text results are explicitly `HYPOTHESIS`
edges with evidence terms, source observation IDs, matcher version, and stable
identities. Similar titles cannot certify same payoff.

Matcher v5 also proposes a `source_component_reference` edge when a recorded
parent's native selected-component list names a child market and the recorded
child has the exact same venue/ticker and, when supplied, event ID. The edge
retains both immutable source observation IDs and the selected side. It remains
a `HYPOTHESIS`: this records the source's asserted component link and a matching
child identity, not equivalent rules, payoffs, logical implications, or
settlement. Missing children, duplicate native identifiers, venue mismatches,
and event-ID mismatches produce no edge. These source edges are prioritized
within the bounded proposal limit. The binary, implication, and multi-outcome
candidate evaluators still require their supported verified constructions; a
component reference alone returns a price-discrepancy-only classification.

`verify_same_payoff` is separate. It requires an external assertion ID, source
observation IDs, verified and exhaustive payout states, a bijection between
outcomes and instruments, matching payout vectors and currency/settlement asset,
matching verified resolution fingerprints and authorities, and matching close
and settlement times. The bounded review API and Mission Control form require
stored hash-checked observations for both source markets. A verification request
must pass the payoff verifier; reject and ambiguous decisions are also recorded
separately. Each decision appends a review record and a linked relationship
revision atomically. Revisions use compare-and-set against the latest review,
and replay consumes only the latest decision, so a later decision can revoke an
earlier verified state without deleting evidence. Reviewer labels and external
assertion IDs are self-attributed and are not authenticated or retrieved; the
review is not a claim that an external document was independently assessed.
Stored relationships and reviews are append-only. `GET /api/frontier/graph`
traverses one to three hops from a recorded center using left/right endpoint
indexes. It returns at most 200 edges, considers at most 500 relationship rows
per request, and loads at most 200 source markets. The response reports the
number of relationship rows scanned and whether a capped scan may be incomplete.
Centered one-hop queries support keyset pages ordered by relationship timestamp
and ID. Centered two- and three-hop queries now also paginate a deterministic
breadth-first result window. The v2 cursor binds the center, depth, page size,
and append-only graph revision, and carries only a bounded edge offset. Each
continuation recomputes the same traversal from the pinned local graph inputs;
there is no persisted traversal session. The API checks graph revision before
loading node metadata and after the page query, returning 409 if market,
relationship, or review rows were appended. Each request scans at most 500
relationship rows and returns at most 200 edges. A BFS layer wider than 200
market IDs is split into deterministic indexed chunks while consuming the same
aggregate scan budget. When that budget truncates a traversal, the response
keeps the incomplete flag even if the researcher reaches the end of its
available result pages. The uncentered recent-edge view is still a bounded
single read without continuation. Mission Control displays 30 edges per page,
with previous/next controls. Its network renders at most 18 edges and the
evidence list is capped at 30 per page. Clustering, layout control, and
full-universe search remain incomplete.

`verify_logical_implication` checks a directed binary YES implication over an
explicit bijection between the two markets' joint payoff state spaces. It
requires verified exhaustive payoffs, complete binary YES/NO vectors that are
exact complements, verified resolutions, the pinned observation for each
market, and a nonempty external assertion ID that does not predate those
observations. It rejects mappings above 1,024 states or 128 characters per
state ID. Direction and the canonical state mapping are recorded in evidence
and included in relationship identity. Per-market settlement denominations
and times are preserved and may differ; the relationship verifier does not
bridge them. Its verified result proves only the payout-vector implication over
the supplied mapping; the assertion that these mapped states describe the same
world remains self-attributed. It is available through the existing
hash-checked review API and append-only store. The economic verifier now
consumes these edges through a bounded two-venue binary family: it buys
NO(source) plus YES(target), independently checks every mapped payout, and
requires identical settlement denomination, close time, and settlement time.
Positive outcomes remain conditional; Mission Control still has no controls
for creating a directed implication.

## 7. Opportunity discovery algorithms

Three bounded candidate families are implemented. Cross-venue complete all-long
binary coverage requires a previously verified same-payoff relationship and
enumerates its mapped states. The new logical-implication family consumes a
verified directed YES edge over a bijective joint-state map. For A implies B it
buys NO(A) and YES(B); the reverse edge selects the corresponding reversed
positions. Its terminal payout must cover at least one settlement unit in every
mapped state. It requires open binary markets on distinct venues, complete
complementary 0/1 YES and NO vectors, exact quote and payout denomination
identity, and matching market close and settlement times. It does not bridge FX,
asset identity, close-time, or settlement-time differences. Candidate replay
adds a separate family dispatch, and the independent audit recomputes the
direction, mapped inequalities, basket payouts, fees, capital and fill-pattern
exposure without calling the generator arithmetic. The external assertion must
cite both pinned market records and predate the replay cutoff; both close and
settlement times must remain in the future. Distinct venue resolution
authorities and rule fingerprints are not reconciled by this bounded evaluator.
Positive classifications remain conditional because the external assertion
tying the joint state spaces to one semantic world is self-attributed and
unauthenticated. Missing fees are not zeroed; stale or insufficiently
synchronized books produce incomplete evidence.

Within-market multi-outcome coverage buys one contract for each of three to
sixteen states in one open event market. It requires a verified, exhaustive
payoff, verified resolution, matching settlement asset, and a strict one-to-one
mapping between states and unit-payout one-hot instruments. The evaluator fails
closed on incomplete or overlapping state vectors, missing books, unsupported
fees, invalid size steps, insufficient depth, or incompatible timing evidence.
All generated candidates remain hypothetical and have
`practical_eligibility=false`.

The implication construction, like within-market multi-outcome coverage, has
controlled fixtures and deterministic replay coverage only. No genuine captured
relationship currently supplies verified semantic equivalence or implication,
so the live sample produced no eligible evaluation. Replay continues to apply
only previously stored verified relationship revisions; text matches remain
hypotheses. Unbounded cycles, partial-payoff combinations, general multi-leg
optimization, and spot/derivative hedge models remain deferred. Every complete
candidate passes to the independent audit. Existing regressions cover non-
identity state mappings, reversed input ordering, unknown fees, stale timing,
settlement mismatch, tampered payout rejection, and deterministic replay.

## 8. Independent economic verification

For supported candidates, the primary Decimal candidate calculator evaluates
terminal payout by state; per-venue gross capital, fee amounts, modeled net cost, and worst-state
gross/net result; quantity step/minimum and displayed top-ask depth; quote
currency and settlement compatibility; receipt and exchange timestamp skew;
book age; and scenario slippage, delay-based quote decay, and fill fraction.
Per-venue capital reports principal and a computed fee when its supported fee
model is current; estimate-based fees remain conditional. When a fee is unknown,
the missing amount is called out and never treated as zero. Unknown fees prevent
a decisive net calculation. A missing/stale book, unsupported
payoff, incomplete equivalence, or currency mismatch fails closed into a
non-positive or incomplete classification.

Candidate detail now exposes the existing `capital_by_venue` estimate through
a client-only virtual balance comparison. Each venue is checked independently
using exact decimal arithmetic; balances are neither pooled nor transferred.
Requirements use modeled buy prices plus computed fees, including a clearly
assumption-labeled fee estimate when present. When an applicable fee is unknown,
the UI reports principal coverage but leaves fee sufficiency unresolved.
Missing or mixed quote currencies disable the comparison. This is a
display-level scenario aid and does not add account, collateral, transfer, FX,
or settlement-duration modeling.

The multi-outcome evaluator proves only the exhaustive sum of accepted one-hot
state payoffs and only for a same-market, all-long construction. It uses an exact
common quantity step and treats an explicit requested quantity as exact; it
rejects a request exceeding the common modeled top-level depth or its fill
fraction. Canonical monetary and quantity Decimals are bounded to 36 digits and
18 decimal places; fee rates are bounded to 12 decimal places and at most one.
Economic evaluation raises local Decimal precision to 128 digits. Verified taker
fees are applied only when their source, currency, supported formula (or explicit
zero rate), and effective/expiry window are applicable to the replay time.
Unknown or expired schedules do not become zero.

`independent_audit.py` does not call candidate-generator arithmetic helpers. It
rechecks the candidate's market/instrument identity, verified relationship or
exhaustive-state mapping, pinned best ask and displayed depth, modeled purchase
price, fee applicability and amount, gross and net basket costs, every terminal
payoff/P&L state, worst-state results, and the generator's reported classification.
The audit records a disposition (`verified`, `disagreement`, `incomplete`, or
`not_evaluated`), checked market/leg counts, recomputed values, and a versioned
input SHA-256. Missing decisive evidence yields `INCOMPLETE`; calculation
disagreement preserves recomputed figures and downgrades the candidate to
`INCOMPLETE_EVIDENCE`. Independent audit version 2 independently reconstructs
each leg's payoff and full-or-no-fill exposure vectors, recomputes the worst
pre-fee and fee-inclusive stress cases, and compares identities, partitions,
and P&L against the candidate. Unknown fees prevent a fee-inclusive result.
Replay version 5 includes this audit and sensitivity in its deterministic
result. Readiness aggregates dispositions only across the latest three
hash-valid runs, and the UI shows the audit state, recomputed cost/fees/net result,
and shortened input hash.

For logical implications, independent audit v7 separately validates the
directed endpoints and external-evidence record, reproduces YES(source) <=
YES(target) for every mapped state, verifies that the candidate selected
NO(source) and YES(target), and recomputes their combined payoff. Positive
modeled results cannot be classified as verified mathematical inconsistencies
because the shared-world semantic assertion is not authenticated. Unknown fees
remain unknown; stale or timing-incomplete implication books are classified as
incomplete.

This is an independent implementation of bounded arithmetic over shared,
normalized and persisted inputs. It is not an independent feed, market-data
oracle, reviewer, resolution-document verifier, fee authority, clock, or execution
venue. A `verified` audit means the candidate arithmetic agrees with its pinned
inputs under the supported model; it is not evidence of independently true
market semantics or of a realizable opportunity.

The primary candidate calculator is a bounded model, not an execution simulator.
It does not model FX, account-specific fees, queue priority, custody, cross-venue
funding or transfers, venue access, partial multi-leg recovery, or settlement
failure probabilities. The full-or-no-fill stress assumes fixed modeled leg
prices, independent per-leg fill/no-fill choices, and terminal settlement under
the verified state model; it does not model probabilities, partial quantities,
or post-fill actions. Scenario outcomes are virtual assumptions. Every candidate has
`hypothetical=true` and `practical_eligibility=false`; a public quote comparison
is never called executable profit.

## 9. Storage, replay, and provenance

Frontier stores data under its own configurable root, default
`data/frontier-store`. SQLite schema v6 defaults to a 64 MiB cap, 50,000
observations, 100,000 relationship records, and 512 KiB per record. An additive
migration upgrades v2/v3/v4/v5 stores with relationship revision, review,
left/right endpoint indexes, and the append-only paired-comparison table without
rewriting existing relationship payloads.
Append-only triggers reject row updates/deletes on observations, indexes,
relationships, review records, runs, and paired comparisons. Relationship review and its derived
state revision are inserted in one bounded transaction. Effective queries and
replay select the last compare-and-set review revision while the earlier record
history remains immutable. Query methods open read-only connections.
Observation and relationship list reads verify content hashes and indexed fields
before returning records. They also validate the current review-to-revision
link; replay and comparison reads recompute their pinned output digests. Offline
tamper tests cover observation, relationship, replay, and comparison list paths.

Captures retain request URL/status/times, local receipt time, raw bytes and
SHA-256, normalized record (or a bounded `SourceFailureRecord` when a decoded
response fails normalization), adapter and source-schema version, and observation
identity. Probe error responses return the diagnostic observation ID, and the
failure remains available through the hash-verified observation read. Invalid
JSON and non-2xx responses are stored as source-failure
observations; invalid UTF-8 bodies use base64 while retaining the original-byte
hash. Oversized or partial response bodies are not stored. Replay consumes only
stored data, fixes source observation IDs,
relationships, assumptions and time, sorts inputs deterministically, and pins a
hash of normalized inputs and the Frontier backend source set. No adapter is
called from replay. Replay version 5 includes each candidate's independent
audit disposition and input hash, one-sided fill sensitivity, plus effective
state/instrument mappings and the relationship proposal limit in normalized-
input identity. Paired replay is
limited to 100 markets, 200 books, 500 verified relationships, and 500 proposed
relationships. It persists two replay records and one comparison in one SQLite
transaction; all three records are hash-validated and protected by append-only
triggers. The store has no compaction/retention worker; once the cap is
reached, writes fail closed and require an explicitly reviewed storage policy.

For store-backed API replay, Frontier now overlays the selected immutable
observation row ID onto the normalized market or book model's provenance before
passing it to replay. The run manifest and candidate legs therefore refer to
the exact source record ID that `/api/frontier/observations/{id}` can resolve.
Replay v6 pins this provenance behavior into normalized-input identity. Direct
in-memory adapter replays keep their deterministic adapter-derived IDs. The
change does not update historical observation rows or require a schema
migration; tests cover API reads, event relationship evidence, single and paired
replay, and Arena snapshot staging.

Polymarket v2 trade pages are each stored as one raw observation plus one
`TradeBatch` schema-v2 record. The record retains the source cursor and next
cursor, condition ID, page limit, and exact `has_more` state; every normalized
trade carries its token ID, outcome label/index, transaction hash, price, share
quantity, and block time. Existing schema-v1 trade batches remain readable and
their new optional instrument fields resolve as unknown. The local continuation
cursor wraps the source cursor with its condition/page-size binding, so the API
can reject a cursor replayed against a different recorded condition or page
size. Read-back returns page metadata together with the trade rows, allowing the
UI to continue from saved evidence without an automatic source crawl.

The committed public captures are
`data/frontier/live-probes/2026-10-26-public-source-probe.json`,
`...-r2.json`, `...-frontier-api-live-validation.json`, and
`...-frontier-api-books.json`, `...-frontier-api-trades.json`,
`...-polymarket-v2-trade-page.json`, and
`...-polymarket-v2-api-continuation.json`. They contain raw public response bodies
and no credentials or mutating requests. The API book run used zero retries, an
8-second timeout, a 65,536-byte response cap, at most two HTTP requests per
venue, and an 8 MiB temporary store. Its envelope SHA-256 is
`101094b56c3dc620f8f66b423c92b5796db0a57852a5f7807aab50b2af956d60`; all six
raw hashes and the envelope hash were recomputed. The application adapter
default response cap remains 262,144 bytes (256 KiB); that is distinct from the
65,536-byte book-capture limit. The later trade run used zero retries, an
8-second timeout, an 8 MiB temporary store, and a 262,144-byte response cap.
It made three requests per venue (listing/metadata, book, and trade), all HTTP
200. Polymarket and Kraken each returned ten trades; Kalshi returned a valid
empty array. All nine raw-body hashes and envelope hash
`ca72a2aa2095ae02660f0ea23c0a6e94019929bd7d1e174b0446673637e04570` were
recomputed, and API read-back counts matched. The largest body was 68,758
bytes. No fee endpoint was called.

The v2 trade page was requested directly through the Polymarket adapter at
`2026-10-26T22:56:38.585296Z`–`2026-10-26T22:56:38.728359Z`, for a condition
already in the saved listing. One public GET (limit 10, zero retries,
65,536-byte cap) returned HTTP 200 and ten rows, all for the same Yes outcome
token, with a continuation cursor. Its raw hash is
`8923bbf6cff2262344ba7b14c923866bace1e46139bd790cedaa758195e6a174`; the
temporary-store row hash is
`65b172aff5ddbfba0c5e43d2952567028ec11a8ce210d44ea11b40732958bbda`; and the
manifest hash is
`d970fce4cb0f4e48995b066ac1114d1c8c519be72eeaca54158cae65db664198`; the
serialized artifact hash is
`e5f400db64aeb000a688889eee4649a8e82ec061638dbe997e5b735dc423dc71`. A bounded
continuation page through the local API route is also preserved below. The two
pages do not establish venue-wide trade coverage, order-book depth, or
cross-venue equivalence.

## 10. Laboratory and Arena integration

Frontier paired replay now has an Arena job kind, registered in the existing job
supervisor. `POST /api/frontier/arena-replay` stages immutable, content-addressed
inputs under the configured Arena root and submits through `jobs.create`, so the
existing host-wide resource-admission lock remains authoritative. The selected
snapshot includes the normalized markets, books, effective verified edges, two
scenario definitions, a pinned UTC observation time, and the Frontier source
version. It is bounded at 100 markets, 200 books, 500 relationships, 8 MiB per
snapshot, 128 MiB / 1,000 snapshots in the store, and 8 MiB per result artifact.

The worker accepts only the snapshot ID and file hash. It verifies both, runs
the existing paired deterministic replay code, and writes a hash-checked result
artifact. Arena caps this job at 300 seconds, 512 MiB, 50% CPU, nice 15, and idle
I/O; the service command restricts address families to AF_UNIX, so the worker
does not use IP networking. The new Arena API lists a bounded recent job catalog
and exposes results only for successful completed Frontier jobs after matching
the manifest's pinned snapshot and result digests. Mission Control now submits
only on explicit click, polls while jobs are active, and displays the job state,
snapshot ID/hash, result hash, and paired comparison. Rejected host admission is
shown as an error; the snapshot remains available for an idempotent retry.
The Research Readiness panel reports `NOT_CONFIGURED` without an Arena root,
`LIVE_VALIDATION_PENDING` until a bounded local scan finds a completed
hash-verified result with a runtime record, `EVIDENCE_RECORDED` after that
check, and `REVIEW_REQUIRED` if completed result/runtime evidence is invalid.
The separate resource sustainability gate remains `NOT_MEASURED`: two short
replays over the same fixture do not characterize sustained workload capacity.

Local testing covers schema and resource caps, content-addressed snapshot
idempotence and tampering, safe path rejection, artifact integrity, result to
job-manifest binding, the API snapshot submission seam, and the UI's submission
and result flow. A controlled cross-venue fixture produced the same paired
comparison and replay-arm hashes through the Arena executor as through direct
deterministic replay.

Two actual systemd-supervised replays completed in the isolated worktree Arena
root after separate read-only host snapshots passed the normal Arena admission
gate. The first run's preflight found no active jobs, 4.59 GiB available
memory, six CPUs, load average 1.37, and 146 GiB free disk. It completed in
0.167 seconds with two candidates in each paired arm. Job
`job-83d1ca93682a4e89b6643024` is preserved alongside the later measurement.
Both used snapshot
`1448349f90cb486b84d945f34f1a2447a297f04a2fd33015627bd6f5f1a8b559`; its file
SHA-256 is
`74f169b18a3b81eade1059a11309c9e3de3535074bc1c1eabd044739685b69ef`. The first
result SHA-256 was
`f147cc55ed467c2af16465f61894affd54d43eb2f31c0c0fa7a84b17f148e929`.

The first run showed that systemd's transient unit counters were unavailable
after exit, so the Arena worker now records process CPU deltas and peak RSS
directly in its terminal job manifest. A second preflight again found no active
jobs (10.07 GiB available memory, six CPUs, load average 1.14, and 144.4 GiB
free disk) and the normal admission lock rechecked at launch. Job
`job-5484db9a63964f43a0e2c5d8` completed successfully in 0.199392 seconds with
two candidates per paired arm. Its process profile reports 0.067554 seconds
user CPU, 0.010943 seconds system CPU, and peak RSS of 167,288,832 bytes
(159.5 MiB) under the configured 512 MiB cgroup limit. The job artifact growth
was 28,766 bytes. Result SHA-256
`2c77cdfc91f7f86da87509f797a39acd8501513c0c30dc987ab85c40e8322db3` and
comparison ID
`1dee0a8c22d97b38619cb244eeb98b6dbb3de5062e1ab593e4308ac9a68fbbe4` verify
against the same pinned input. The local result verifier confirmed the full
job-to-snapshot-to-result binding. Arena history now exposes only these
allowlisted process metrics, and Mission Control renders them with a note that
one worker sample is not a capacity claim. No public source was queried; this
validates supervisor and artifact wiring, not live venue or economic evidence.

`resource_sustainability` remains `NOT_MEASURED`: two short deterministic
replays over the same fixture do not characterize larger inputs, concurrent
system load, or sustained resource behavior. The earlier `resource_admission_lock_busy` result
was not bypassed. No long-running campaign or background collector was started.

## 11. Dashboard implementation

Frontier is integrated into the existing React Mission Control navigation and
visual style. It has overview, exchanges, markets/books/trades, relationship
evidence, candidate, virtual economic workbench, replay and readiness sections. It reads
real local Frontier API responses; the empty-state screenshot used isolated
temporary storage and shows zero captured evidence. The workspace has distinct
offline, empty, unsupported, disabled-probe, stale/error, and degraded states.
Source health is separated from observation age. The source controls do not
probe automatically; a capture is explicit and unavailable unless the specific
source flags are enabled. Responsive browser verification covered the empty
workspace at 1440px/390px and fixture-only graph selection, center-market
keyset page navigation, review submission, and a first/next Polymarket trade-page
flow at desktop/mobile widths. Trade capture is disabled in the interface unless
the selected source advertises the capability and its explicit probe flag is
enabled. The source selector lists only markets in saved listing evidence; each
click requests one venue-specific page and the UI shows its observation/raw
hashes and request bound.
The API
graph query is bounded to 200 source markets, 500 scanned relationship rows per
request, and 1–3 hops; centered one-hop traversal uses left/right endpoint
indexes and keyset cursors, while two-/three-hop traversal uses revision-bound
breadth-first pages. The visual network caps at 18 edges. Reviewer
authentication, external assertion retrieval, clustering, and experiment
result drill-downs remain incomplete. A focused browser test now verifies a
revision-pinned depth-two graph page, venue-separated virtual balances, and
mobile overflow behavior. Earlier dated statements that this browser path was
pending are superseded by this checkpoint.
The Replay & Readiness section also includes a content-hashed Arena job list and
detail view. It labels the limits and offline worker boundary and shows the
hash-verified completed paired comparison. Job history is a 500-record bounded
scan and can report when it may be incomplete.
Candidate detail shows the independent audit disposition,
recomputed economics, and pinned-input hash. Readiness summarizes audit
dispositions from the most recent three hash-valid runs and explicitly says that
arithmetic agreement does not establish profitability or execution. Candidate
detail also compares local virtual balances with per-venue modeled requirements;
this comparison is not persisted and cannot establish that capital is actually
available.

## 12. Testing and reproducibility

Verification on this branch:

- Backend focused suite: **54 passed** in 9.86 seconds. Command: `PYTHONPATH=packages:apps/api /home/charlie/midas/.venv/bin/python -m pytest -q tests/frontier tests/integration/test_adapters.py tests/integration/test_api.py::test_offline_api_workflow_contract_and_persistence`.
- After the schema-v5 graph adjacency change, that focused command passed **56 tests** in 10.65 seconds. `/usr/bin/time -v` measured 11.43 seconds wall, 3.97 seconds user CPU, 145,560 KiB peak RSS, and zero socket messages; one upstream Starlette/httpx deprecation warning remained.
- After adding Polymarket fee-shape assertions and timeout/truncated-stream failure cases, the same focused command passed **59 tests** in 11.11 seconds pytest time / 11.89 seconds wall, 4.03 seconds user CPU, 145,936 KiB peak RSS, and zero socket messages. This confirms bounded timeout retries and ensures incomplete stream bodies do not enter the complete-response evidence path.
- After adding centered keyset pagination, graph-revision invalidation for rendered market metadata, and a 501-edge scan-bound regression, the focused command passed **63 tests** in 15.59 seconds pytest time / 16.38 seconds wall, 4.75 seconds user CPU, 148,684 KiB peak RSS, and zero socket messages. The dense-fixture test took 3.76 seconds (4.35 seconds process wall, 1.12 seconds user CPU, 65,756 KiB RSS) including proposal construction, persistence of 501 rows, and a single 500-row page read; this is fixture setup plus query, not a standalone query-latency benchmark.
- Python static checks: Ruff check and format check passed for the Frontier package/tests; mypy passed for 16 Frontier/API source files. A broader `mypy packages/midas/frontier apps/api` attempt reported 37 errors in eight unchanged Veritas/Arena/API files; no Frontier source error was reported.
- Frontend unit suite: **35 passed across 7 files**.
- Frontend typecheck, ESLint, and Prettier check passed.
- Trade capture/read API regression tests: **2 passed**; they validate Polymarket's condition-ID query, bounded GET count, absent authorization, raw evidence persistence/read-back, plus the stored-batch query.
- Production frontend build passed. Frontier is lazy-loaded as a 49.11 kB JavaScript chunk and 24.74 kB CSS. Vite emitted the existing large-chunk warning for 503.86 kB main and 544.41 kB Chart chunks.
- Frontier browser cases: **2 passed** in 6.5 seconds, including empty state, fixture-only keyset page navigation, center-market graph review, and independent audit details at desktop/mobile sizes. The full 10-case browser suite was attempted earlier; 8 passed and 2 existing Laboratory cases were denied at the host-wide Arena admission lock (`resource_admission_lock_busy`). Neither case started an experiment, and the shared lock was not bypassed. The isolated API tests use a temporary root and never enable source probes.
- Legacy regression evidence: focused integration adapter contracts and the existing offline API workflow/persistence acceptance test passed. The complete repository Python suite was not run.
- Latest `tests/frontier` run after paginated trade and outcome-instrument changes: **59 passed** in 14.52 seconds pytest time; `/usr/bin/time -v` measured 15.00 seconds wall, 3.25 seconds user CPU, 110,952 KiB peak RSS, zero socket messages, and no swaps. One upstream Starlette/httpx TestClient deprecation warning remains.
- Legacy adapter and offline API regression after additive `TradeObservation` fields: **10 passed** in 2.37 seconds pytest time / 3.09 seconds wall, 2.53 seconds user CPU, 121,420 KiB peak RSS, zero socket messages.
- Latest frontend suite: **36 passed across 7 files**; TypeScript typecheck, ESLint, and Prettier checks passed. Frontier's built chunks are 51.60 kB JavaScript and 25.46 kB CSS; the pre-existing main/Chart chunks remain above Vite's 500 kB warning threshold.
- Latest Frontier Playwright run: **2 passed** in 6.3 seconds with one worker. It includes explicit first/next trade-page UI continuation against fixtures; it does not imply a live browser/API source run.
- Current regression after Kalshi fee metadata/UI integration: `tests/frontier` **63 passed** in 17.08 seconds pytest time; `/usr/bin/time -v` measured 17.63 seconds wall, 3.69 seconds user CPU, 110,004 KiB peak RSS, and zero socket messages/swaps. The existing Starlette/httpx TestClient deprecation warning remains.
- Current frontend suite: **37 passed across 7 files**. Typecheck, ESLint, and Prettier checks passed. Production build passed; Frontier chunks are 53.37 kB JavaScript and 26.03 kB CSS. The existing 503.86 kB main and 544.41 kB Chart chunks still trigger Vite's large-chunk warning.
- Current Frontier Playwright run: **2 passed** in 6.4 seconds with one worker. These cases validate existing bounded graph interactions and isolated page behavior; the fee metadata action is covered by the frontend fixture test, not a live-browser probe.
- The Kalshi fee metadata route passed an isolated live API-to-temporary-store read-back for one market and series. It made one listing, one event, and one series GET, all HTTP 200; the three raw-body and stored-row hashes verified. This is endpoint/normalization evidence only, not a fee-cost calculation.
- Live v2 source checks: one unauthenticated direct first-page GET and one continuation GET invoked through `POST /api/frontier/probe/polymarket/trades`; each made one request without retries, returned HTTP 200 and ten trades, and had raw plus normalized temporary-store read-back hashes pinned. Their 20 native trade IDs are distinct. No third page was requested.
- Latest bounded Python regression command: **77 passed** across `tests/frontier`, adapter contract integration, and the offline API persistence workflow in 17.75 seconds pytest time. `/usr/bin/time -v` measured 18.57 seconds wall, 4.99 seconds user CPU, 150,520 KiB peak RSS, zero swaps, and zero socket messages. One upstream Starlette/httpx `TestClient` deprecation warning remains.
- Kalshi cursor-page fixture coverage: normalizes one page, binds continuation cursor to recorded ticker and page size, persists raw/normalized observations, rejects an unrecorded ticker, an unexpected ticker row, and a nonadvancing cursor, and handles an empty terminal page. The genuine live request returned an empty page, so row mapping is fixture verified only.
- Frontend after adding the Kalshi source selector: **37 passed across 7 files**; TypeScript typecheck, ESLint, and Prettier passed. Production build passed; Frontier chunks are 54.10 kB JS and 26.06 kB CSS. The existing 503.86 kB main and 544.41 kB Chart chunks still trigger Vite's large-chunk warning.
- Frontier Playwright file: **2 passed** with one worker, including graph interaction and the Polymarket/Kalshi trade-page controls. The first full 10-case run had one outdated Frontier selector and two Laboratory timeouts; after updating the selector and rerunning, the full suite passed **10/10** in 23.4 seconds with one worker. The browser suite used isolated temporary API/storage roots. No live source probing was enabled.
- Python Ruff check/format, mypy for the 16 Frontier/API source files, and `git diff --check` passed after the Kalshi trade-page change.
- The live Kalshi trade-page capture used two unauthenticated GETs (one saved-market listing and one trade page), zero retries, 65,536-byte response caps, and a temporary 8 MiB store. Both HTTP 200 bodies and both temporary-store row hashes verified. The conditional market's page held zero trades and no cursor; the capture does not validate a live row mapping or establish market availability.
- Latest focused Python regression after the documented-fee-example case: **86 passed** across `tests/frontier`, adapter contract integration, and the offline API persistence workflow. Pytest took 18.05 seconds; `/usr/bin/time -v` measured 18.90 seconds wall, 5.16 seconds user CPU, 151,728 KiB peak RSS, zero swaps, and zero socket messages. After the additional capability-text assertion, the adapter and fee-sensitivity subset passed **25 tests** in 1.40 seconds. One upstream Starlette/httpx deprecation warning remains. The full repository Python suite was not run.
- Fee-sensitivity tests cover formula precision, microdollar rounding, both balance quanta, unsupported fee types, input bounds, saved-evidence validation and mismatched event/series rejection. A new regression matches Kalshi's [documented fee-rounding fill](https://docs.kalshi.com/getting_started/fee_rounding): `$0.00363825` model fee, `$0.003639` microdollar fee, `$0.001361` non-direct rounding adjustment, and `$0.005` total fee for a `$0.055` one-contract buy. The preserved derived artifact replays offline from hash-verified October 27 event/series metadata: manual `$0.50`, quantity 1, `$0.0175` direct-member and `$0.02` non-direct-member modeled fee. No HTTP call supplied that scenario price or size.
- Artifact integrity: derived result SHA-256 `cdc66e6722fe25369317107ca4d94b4749b3f47f938dca0b3924507f5b5922c4`; source metadata capture SHA-256 `4a2e1ac8e2953314e89f26fa825142b551ce0a24512a14e3494df03b936ea53e`; calculation digest `0218bc4415eafbd8d154173fd66b98c8be92ef7255d0cd75b9a61e8b5a385ce0`.
- Python Ruff check/format and mypy passed for the Frontier/API source set checked at this checkpoint. `git diff --check` passed before the documentation checkpoint.
- Frontend after the sensitivity work: **37 passed across 7 files**; TypeScript typecheck, ESLint and Prettier passed. Production build passed; Frontier JS is 56.47 kB and CSS is 26.85 kB. Existing main (503.86 kB) and Chart (544.41 kB) chunks retain the Vite large-chunk warning.
- Targeted Frontier Playwright: **2 passed** in 6.3 seconds, one worker, using isolated temporary API/storage roots and no live probe. A subsequent full 10-case run had two Laboratory failures: Arena admission returned `host_memory_pressure`, then an experiment-report wait timed out after the denied launch. No experiment started and no resource gate was bypassed; full E2E verification remains incomplete.
- Paired-replay checkpoint: the focused command across `tests/frontier`, adapter contracts, and the offline API workflow passed **96 tests**. Pytest took 20.28 seconds; `/usr/bin/time -v` measured 21.07 seconds wall, 5.38 seconds user CPU, 154,656 KiB peak RSS, zero swaps, and zero socket messages. Ruff check/format, mypy across 16 Frontier/API source files, and `git diff --check` passed. One upstream Starlette/httpx deprecation warning remains; the complete repository Python suite was not run.
- Frontend paired-comparison checkpoint: **38 tests passed across 7 files**; typecheck, ESLint, and Prettier checks passed. Production build passed; Frontier's lazy chunk is 60.41 kB JavaScript and 27.64 kB CSS. The pre-existing 503.86 kB main and 544.41 kB Chart chunks still trigger Vite's size warning. Targeted Frontier Playwright passed **2 cases** in 7.1 seconds using one worker, an isolated temporary store, and zero source-probe requests. It verifies paired comparison save/read through the local research API and responsive layout, not live market matching.
- Latest one-sided-fill regression: **97 passed** across `tests/frontier`, adapter contracts, and the offline API workflow in 20.53 seconds pytest time. `/usr/bin/time -v` measured 21.36 seconds wall, 5.69 seconds user CPU, 155,636 KiB peak RSS, zero swaps, and zero socket messages. Ruff check/format, mypy across 16 Frontier/API sources, and `git diff --check` passed. One upstream Starlette/httpx deprecation warning remains.
- Latest frontend regression: **38 passed across 7 files**; TypeScript typecheck, ESLint, and Prettier passed. Production build passed; Frontier's lazy chunk is 62.62 kB JavaScript and 28.46 kB CSS. The existing 503.86 kB main and 544.41 kB Chart chunks still trigger Vite's size warning. Targeted Frontier Playwright passed **2 cases** in 7.3 seconds with one worker, isolated temporary API/store roots, and no source-probe requests.
- A broader single-worker Playwright attempt ran all 10 browser cases: **8 passed and 2 Laboratory launch checks were blocked** by the host-wide Arena admission lock (`resource_admission_lock_busy`). Failure context confirms no experiment was admitted or launched. The lock was not bypassed; Laboratory execution remains unverified under the active host gate. The complete repository Python suite was not run.
- The one-sided-fill differential fixture exhaustively enumerates all eight full/no-fill patterns for three legs and matches the analytic minimum terminal P&L. A 16-leg fixture validates the bounded 65,536-pattern state-space declaration with analytic evaluation; it is not a production throughput benchmark.
- Arena paired-replay checkpoint: **130 passed** across Frontier, the new bounded Arena worker/API tests, Arena job-schema foundations, and offline API persistence. Pytest took 47.97 seconds; `/usr/bin/time -v` measured 49.97 seconds wall, 31.65 seconds user CPU, 535,504 KiB peak RSS (about 523 MiB), zero swaps, and zero socket messages. The 8-test isolated Arena replay module completed in 1.81 seconds. One upstream Starlette/httpx `TestClient` deprecation warning remains.
- Frontend after Arena job submission, history, result verification, and readiness-gate UI: **39 passed across 7 files**. TypeScript typecheck, ESLint, and Prettier passed. Production build passed; Frontier chunks are 67.76 kB JavaScript and 29.81 kB CSS. Existing 503.86 kB main and 544.41 kB Chart chunks still trigger Vite's size warning.
- Targeted Frontier Playwright: **3 passed** in 7.5 seconds with one worker and isolated temporary API/Arena/store roots. The new case opened Arena history and confirmed no replay submission occurs on page load. No source probe or Arena worker was launched.
- After the readiness transition was implemented, the complete Frontier API test module passed **20 tests** in 8.24 seconds. A fixture completed job with a hash-valid result and runtime record produces `EVIDENCE_RECORDED`; a corrupt result produces `REVIEW_REQUIRED`; `resource_sustainability` stays `NOT_MEASURED`. The readiness scan is capped at 100 job entries and 64 KiB per manifest. This unit-test result is separate from the later supervised fixture run documented above.
- The latest replay/API regression passed **29 tests** in 12.08 seconds across `tests/arena/test_frontier_replay.py` and `tests/frontier/test_api.py`, including rejection of malformed and out-of-bound worker measurements. The updated Mission Control Frontier component passed **7 tests**, including CPU/RSS display and the capacity-limit note. The production frontend build passed; the Frontier chunk is 68.90 kB JavaScript and 29.81 kB CSS. The existing 503.86 kB main and 544.41 kB Chart chunks still trigger Vite's bundle-size warning. TypeScript, ESLint, Prettier, and Ruff passed. At this checkpoint, `jobs.py` passed mypy and `apps/api/arena.py` had three existing typing errors; later commit `2628792` fixed the optional unit-ID and sorted-path typing, and focused mypy now passes for those API/job sources.
- The targeted Frontier browser suite passed **3 tests** in 8.5 seconds with one worker. It verifies workspace responsiveness, that Arena history does not start work on page load, and bounded/mobile graph behavior. An isolated ASGI API read of the persisted worker returned the three allowlisted metrics, and the result route returned HTTP 200 with `integrity_verified=true`; no production API process was started.
- Ruff check and format passed for all changed Python files. Mypy passed in strict mode for the Frontier replay job module, Arena job schema, and Frontier API (3 source files). A broader import-following mypy run reports 37 errors in 8 existing Veritas/Arena/API files, including unrelated legacy errors in `apps/api/arena.py`; it reported no errors in the Frontier replay job or `apps/api/frontier.py`. `git diff --check` passed.
- Replay v6 source-record lineage regression: `tests/frontier` plus
  `tests/arena/test_frontier_replay.py` passed **118 tests** in 24.05 seconds;
  `/usr/bin/time -v` measured 24.89 seconds wall, 7.48 seconds user CPU,
  0.76 seconds system CPU, 254,696 KiB peak RSS, zero swaps, and zero socket
  messages. Ruff check/format passed on the four changed Python files, and
  focused mypy passed on four API/replay/Arena source modules. The tests verify
  store-row IDs in API market/book reads, event relationship evidence, replay
  manifests, paired replay, and Arena snapshots. One upstream
  Starlette/httpx `TestClient` deprecation warning remains.
- Centered multi-hop graph pagination: the complete `tests/frontier` plus
  `tests/arena/test_frontier_replay.py` suite passed **121 tests** in 27.54
  seconds; `/usr/bin/time -v` measured 28.35 seconds wall, 8.36 seconds user
  CPU, 0.94 seconds system CPU, 259,044 KiB peak RSS, zero swaps, and zero
  socket messages. Tests verify breadth-first edge order across pages,
  repeat-page determinism, depth/page-size/center binding, stale-revision
  rejection, and 201-market frontier chunking. The frontend passed **39 tests**,
  TypeScript, ESLint, and Prettier. The updated E2E spec was enumerated by
  Playwright but not run in a browser. A production frontend build and E2E run
  were deferred at the measured host-pressure sample recorded below.
- Two systemd-supervised Frontier fixture jobs completed after the ordinary host-wide Arena gate admitted them. Their paired results verify against the same pinned snapshot. The latest manifest now records process CPU/RSS, and Mission Control exposes the allowlisted measurements with a capacity-limit note. These fixture jobs do not validate a live relationship or economic opportunity; resource sustainability remains `NOT_MEASURED`.
- After the 130-test regression, two targeted API cases passed for snapshot staging and simulated admission denial. The denial returned HTTP 409, preserved the content-addressed snapshot, issued no source request, and created no job.

Backend tests emitted one upstream Starlette/httpx TestClient deprecation
warning. No tests modified legacy expectations to make them pass. Fixture network
responses are distinct from the preserved genuine public capture files.

### Kalshi order-fee rounding checkpoint (2026-10-27)

- The new local `/api/frontier/economics/kalshi-fee-order-sensitivity` endpoint
  accepts 1–32 manual fills for a single market, native instrument, and buy/sell
  direction. It requires the event/series metadata pair to be present in the
  append-only store, hash-matched to its raw captures, tied to the requested
  recorded market, and the fill instrument to exist in that market's recorded
  instrument list.
- Decimal arithmetic applies the documented quadratic taker formula to each
  fill, rounds trade fees to `$0.000001`, floors each signed balance change to
  the selected precision grid, accumulates rounding across one order, and emits
  rebates in precision increments capped so no fill fee is negative. Output
  includes per-fill trade/rounding/rebate values, carry balance, order totals,
  both documented precision cases, source observation IDs and raw hashes, and a
  deterministic input digest. Mixed instruments, mixed order sides, unsupported
  fee types, and over-bound order size fail closed.
- The Mission Control market inspector now accepts and displays a bounded
  fill sequence, records the native instrument on each fill, reports both
  precision scenarios and per-fill fee components, and labels all inputs as
  manual hypothetical scenarios. The existing one-fill route remains available
  for compatibility; neither endpoint modifies candidate net economics.
- Tests reproduce the official one-fill rounding example and an order-level
  accumulator/rebate case, including the balance identity for both buys and
  sells. A regression preserves the full supported 12-decimal price/quantity
  precision in both fee sensitivities. The complete Frontier backend suite
  passed **98 tests** in 32.93 seconds pytest time; `/usr/bin/time -v` measured
  33.73 seconds wall, 6.38 seconds user CPU, 248,112 KiB peak RSS, zero swaps,
  and no socket traffic. One upstream Starlette/httpx deprecation warning remains.
- Frontend regression passed **39 tests across 7 files**; TypeScript, ESLint,
  and Prettier passed. Production build passed; the Frontier JavaScript and CSS
  chunks are 71.13 kB and 30.28 kB. Existing main and Chart chunks continue to
  exceed Vite's 500 kB warning threshold. Build time was 5.66 seconds, peak RSS
  577,964 KiB, with zero swaps and no socket traffic.
- Targeted Frontier Playwright passed **3 tests** in 8.0 seconds with one worker,
  isolated temporary API/database/Arena/Frontier roots, no public-source probe,
  and no Arena launch. Component tests cover the new fill editor; E2E covers the
  responsive workspace, replay history, and bounded relationship graph.
- Ruff, focused mypy across the three changed Frontier/API modules, and
  `git diff --check` passed. The complete repository Python suite was not run.
- The saved Kalshi fee and order-book captures do not refer to the same native
  market, and the captured book is empty. Order inputs therefore remain manual;
  these tests and sensitivities do not validate live fills, candidate fee
  integration, or profitability.

### Kalshi selected-leg settlement-value metadata (2026-10-27)

- Commit `7ad28c5` adds adapter v11's optional
  `yes_settlement_value_dollars` to the typed selected-component model. The
  adapter preserves it as an exact bounded Decimal, rejects malformed,
  negative, and excessive-precision values through a typed error, carries the
  source field into relationship evidence, and displays the exact value in the
  component inspector. The UI retains the source's `YES settlement value`
  terminology.
- Kalshi's official [Get Multivariate Events schema](https://docs.kalshi.com/api-reference/events/get-multivariate-events)
  documents this field. The schema evidence reviewed does not establish that it
  is the MVE's combo payout, so Frontier explicitly does not make that
  inference. Omission remains unknown. The hash-pinned October 27 child-market
  capture predates this change and did not include this field; value-specific
  verification is documentation-shaped fixture coverage only.
- The v11-focused adapter regression passed **8 tests**; a prior full
  Frontier/Arena run passed **140 tests** before the excessive-precision case
  was added. Strict mypy passed for the changed four Python modules; Ruff,
  `git diff --check`, TypeScript, ESLint, Prettier, the 40-test frontend suite,
  and production build passed. The built Frontier chunks were 78.48 kB JS and
  33.14 kB CSS; existing 503.86 kB main and 544.41 kB Chart chunks retain the
  Vite warning. `/usr/bin/time -v` measured the prior full Python suite at
  30.97 seconds wall and 266,896 KiB peak RSS. At the latest sample memory PSI
  was 38.49% `some` / 33.50% `full` over 10 seconds with 3.45 GiB swap in use,
  so browser E2E and another full-suite process were not launched.
- A subsequent isolated API regression passed **1 test**: a fixture variant
  carrying `0.3750` round-trips through the public read-only capture route,
  normalized market read, and stored observation. The synthetic field addition
  is identified as a schema-shaped test input; the preserved live response
  remains unchanged and still omits this field.
- No live source request, production service, browser workload, or deployment
  was used for this field. The mission remains incomplete and not production
  ready.

### Kalshi multi-request failure and recovery checkpoint (2026-10-27)

- Added an API-boundary regression for the metadata flow's two-request shape:
  the public event request succeeds, then the series request returns HTTP 503.
  The test confirms that both the successful event bytes and failed series bytes
  are persisted with verified hashes and failure-stage labels.
- The same fixture confirms Kalshi health changes to degraded with the transport
  error, a subsequent successful event/series call clears the error and restores
  healthy state, and previously persisted diagnostic rows remain byte-for-byte
  unchanged after recovery.
- The bounded sequence contains four mock-transport GETs, with no Authorization
  header. This is fixture-only API recovery coverage; no live source was
  intentionally degraded, and live degraded-source recovery remains unverified.
- The complete Frontier backend suite passed **99 tests** in 33.92 seconds
  pytest time. `/usr/bin/time -v` measured 34.73 seconds wall, 6.54 seconds user
  CPU, 248,244 KiB peak RSS, zero swaps, and zero socket messages. Ruff check,
  Ruff format check, `git diff --check`, and a post-format targeted test rerun
  passed. One upstream Starlette/httpx `TestClient` deprecation warning remains.

### Kalshi MVE selected-component checkpoint (2026-10-27)

- Kalshi adapter v4 maps the documented `mve_selected_legs` field into bounded
  canonical component records with native event/market tickers and the selected
  YES/NO side. It rejects malformed objects, invalid sides, duplicate market
  identifiers, self-reference, and lists above 64 components. Raw response
  fields and hashes remain persisted alongside normalized rows.
- Mission Control's market inspector displays saved components and an explicit
  note that component membership does not establish component rules, combo
  payoff, or settlement equivalence. Existing saved MVE markets receive no
  backfilled normalized components until a new listing is captured.
- A fixture API/store round trip replayed the preserved October 26 listing
  bytes with MockTransport, verified the raw SHA-256 and all 17 selected
  components, and confirmed payoff verification remains false. This was an
  offline replay of genuine preserved response bytes, not a new live probe.
  The sample's primary rules were empty; the secondary rules were only a general
  disclaimer. The observation is dated and is not current market-state or
  economic evidence.
- The complete `tests/frontier` suite passed **104 tests** in 20.96 seconds
  pytest time; `/usr/bin/time -v` measured 21.77 seconds wall, 6.60 seconds user
  CPU, 247,084 KiB peak RSS, zero swaps, and zero socket messages. Ruff
  check/format and focused mypy for the Kalshi adapter/models passed. One
  upstream Starlette/httpx `TestClient` deprecation warning remains.
- Frontend tests passed **39 cases across 7 files**; typecheck, ESLint, and
  Prettier passed. The production build passed with a 71.91 kB Frontier
  JavaScript chunk and 31.14 kB CSS. Existing 503.86 kB main and 544.41 kB
  Chart chunks still trigger Vite's size warning. Build measurements were
  12.51 seconds wall, 19.85 seconds user CPU, and 658,824 KiB peak RSS, with
  zero swaps and zero socket messages.
- Targeted Frontier Playwright passed **3 tests** in 7.7 seconds with one
  worker and isolated temporary API/database/Arena/Frontier roots. The browser
  test inspected component identifiers, side, and the unverified-payoff notice.
  No source probe or Arena job was launched.

### Independent-audit malformed-leg checkpoint (2026-10-27)

- The independent verifier previously assumed that a two-leg cross-venue
  candidate contained one leg for each market, then used `next()` to locate
  those legs. A malformed or corrupted candidate repeating one market could
  escape as an uncaught `StopIteration` instead of receiving an evidence
  disposition.
- The verifier now checks that its two candidate legs cover both selected
  market identities before reading the instruments. The invalid shape is
  recorded as `INCOMPLETE` with an `INCOMPLETE EVIDENCE` candidate
  classification. A regression mutates an otherwise valid candidate to repeat
  its first leg and exercises that path.
- The focused regression passed in 0.28 seconds. The complete
  `tests/frontier` suite passed **104 tests** in 20.89 seconds pytest time;
  `/usr/bin/time -v` measured 21.70 seconds wall, 6.52 seconds user CPU,
  247,952 KiB peak RSS, zero swaps, and zero socket messages. Ruff check/format,
  focused mypy for the audit module, and `git diff --check` passed. One upstream
  Starlette/httpx `TestClient` deprecation warning remains.

### Event-group metadata and cross-venue hypothesis checkpoint (2026-10-27)

- Polymarket adapter v3 and Kalshi adapter v5 now advertise the bounded
  `EVENT_MARKET_GROUPS` capability. Each implementation makes one fixed-host
  public GET, validates the returned event identity, bounds and de-duplicates
  child markets, and preserves parent event title and native child fields. The
  API route `POST /api/frontier/probe/{venue}/event-markets` is source-config
  gated, requires a market already in the saved observation window, verifies
  the event response contains that market, and persists one raw response with
  a normalized `MarketBatch`. Kraken explicitly declares this capability
  unsupported. The [Polymarket event documentation](https://docs.polymarket.com/market-data/discover-markets)
  describes public event retrieval and grouped markets; Kalshi's documented
  [Get Event](https://docs.kalshi.com/api-reference/events/get-event) and
  [Get Events](https://docs.kalshi.com/api-reference/events/get-events)
  schemas expose an event and nested markets.
- The saved direct public capture contains two sequential HTTP 200 responses:
  Polymarket event `32225` at
  `2026-10-27T10:40:22.014124Z`–`10:40:22.055629Z` (50,404 bytes, raw SHA-256
  `7a4679841943a27efeeeabb77e44b24805e5c4b6533a9e0093633dd89714560e`) and
  Kalshi event `CONTROLH-2026` at
  `2026-10-27T10:40:22.056340Z`–`10:40:22.394643Z` (4,036 bytes, raw SHA-256
  `cce75fcc4d528401ddbfd576a7fafe6c8aed42ccbd4b7cb3d772a98e2157f189`).
  Envelope SHA-256 is
  `943761832d6b44616d5abeccd934cf0bb6adb88fbc4fedb0524e1e39b1104400`.
  Evidence is preserved in
  [`2026-10-27-public-cross-venue-house-control-r1.json`](../../data/frontier/live-probes/2026-10-27-public-cross-venue-house-control-r1.json).
- Offline adapter replay normalized nine Polymarket children and two Kalshi
  children, preserving their event IDs/titles and raw lineage. The title and
  outcome-context matcher proposed a Democratic House-control
  `TEXT_CANDIDATE` at `HYPOTHESIS` state. It rejected an outcome-mismatched
  fixture and a parent title naming 2028 instead of 2026. Independent
  same-payoff verification rejected the observed pair: Polymarket's child
  `endDate` is November 4, 2026 and its description allows late caucus
  attribution through January 4; Kalshi's Democratic contract closes and
  expires February 1, 2027, with a secondary rule for early media calls or
  the Speaker's party on that date. These source rules, dates, and authorities
  are not established as equivalent by text.
- API fixture tests for both venue routes verify market binding, one-GET bounds,
  normalized latest-record selection, exact raw hash persistence, and
  byte-preserving diagnostic capture when a requested market is absent from the
  event. They do not constitute a live adapter-to-API browser probe. The capture
  contains no prices or order books, was sequential rather than simultaneous,
  and supports no discrepancy, verified equivalence, or economic claim.
- A second integration fixture passed both preserved response bodies through
  their venue adapters, the event-group API routes, SQLite, and the relationship
  proposal route. Its single target pair remains `TEXT_CANDIDATE`/`HYPOTHESIS`
  under matcher v4. It also rejects a child-title year mismatch when the parent
  title omits a year, and rejects a contradiction between a source's parent and
  child years. Relationship evidence names the exact stored observation records
  containing normalized markets; both cross-venue IDs were read back and
  verified. Direct in-memory matcher use retains deterministic normalized
  observation IDs. This changes hypothesis filtering and evidence references,
  not payoff verification, market identity, or economics.
- `tests/frontier` plus `tests/arena/test_frontier_replay.py` passed **118 tests**
  in 22.95 seconds; `/usr/bin/time -v` measured 23.77 seconds wall, 7.38 seconds
  user CPU, 254,240 KiB peak RSS, zero swaps, and zero socket messages. All
  frontend tests passed (**39 tests across 7 files**); the production build
  passed with existing 503.86 kB main and 544.41
  kB chart chunk warnings; **11/11** isolated Playwright tests passed. Ruff
  check/format and focused import-following mypy passed for the seven changed
  backend modules. Normal import-following mypy reports 14 existing errors in
  four unchanged Veritas/Arena files. A repository-wide pytest attempt stopped
  at collection: one Reality test imports a missing `midas.reality.recovery`
  module, and four legacy tests import `test_reality_foundry` without the
  `tests/` directory on the module path. The Frontier/Arena replay suites
  themselves pass.
- Kalshi adapter v10 adds a bounded market-detail request for one MVE child
  ticker already present in a saved parent's selected-component metadata. The
  API rejects unreferenced tickers before network access, makes one
  unauthenticated GET, checks returned market/event identities against saved
  parent evidence, and persists the raw and normalized `market_metadata`
  observation. Market queries and graph revisions include this observation
  kind. Mission Control exposes the capture action and displays source rules
  with an explicit unverified-payoff state.
- A genuine one-request capture returned a referenced child with matching
  ticker and event IDs. Raw SHA-256
  `0f1c3cd42cac5202ca5a3012d58cb8d9631bf39cce313c738bb0448140271eda` and
  isolated temporary-store row SHA-256
  `a2e7ae0c08436155a0bdc80e07f16d6b882eaf9706617994be135b668ec5897a` are
  preserved in [`2026-10-27-kalshi-mve-component-market-r1.json`](../../data/frontier/live-probes/2026-10-27-kalshi-mve-component-market-r1.json).
  The market was closed. Its resolution text contains fair-price fallback
  cases for inactive/non-playing and postponed events; it is not a verified
  simple binary payout. No book or price was captured, and neither the child
  nor parent-combo payoff is verified.
- Current bounded Python regression: **136 passed** across `tests/frontier`
  and `tests/arena/test_frontier_replay.py` in 29.56 seconds; one existing
  Starlette/httpx TestClient deprecation warning remains. The frontend unit
  suite passed **40 tests across 7 files**; TypeScript, targeted
  ESLint/Prettier, and Ruff checks passed. Three isolated Frontier Playwright
  cases passed in 8.9 seconds with one worker. Production Vite build passed;
  Frontier chunks are 78.34 kB JavaScript and 33.14 kB CSS. Existing 503.86 kB
  main and 544.41 kB Chart chunks still trigger the size warning. Mypy for the
  three modified Python modules passed in strict mode with imported-module
  diagnostics suppressed; Ruff check/format and `git diff --check` also pass.
  A follow-on storage regression passed (**1 test**, 0.53 seconds), proving a
  saved component `market_metadata` record advances the graph revision while
  book/trade records do not.
- After matcher v5 added source-component references, the full
  `tests/frontier` plus `tests/arena/test_frontier_replay.py` regression passed
  **137 tests** in 30.04 seconds. `/usr/bin/time -v` measured 30.85 seconds wall,
  8.89 seconds user CPU, 264,844 KiB peak RSS, zero swaps, and zero socket
  messages. The existing Starlette/httpx TestClient deprecation warning remains.
  The relationship/API modules also passed a 49-test focused run. A fixture
  test then replayed the captured MVE parent listing through the current Kalshi
  adapter, joined it to the separately captured child detail, and produced one
  source-component hypothesis with both stored observation IDs; that test
  passed independently. Strict mypy for the changed relationship/API modules
  and Ruff check/format passed. This is deterministic replay of saved public
  responses, not a fresh cross-venue or economic observation.

### Saved Kalshi candidate-fee estimate checkpoint — 2026-10-27 16:41 UTC

Code commit `3e85c8d` adds a replay-only candidate fee estimate from a complete,
hash/path/identity-checked saved event/series pair. It requires supported
quadratic taker metadata, evidence no later than the pinned book quote and at
most 24 hours old at both quote and replay evaluation. It calculates one fill
with the conservative `$0.01` non-direct-member debit-alignment scenario. The
independent audit re-derives this fee, estimated-fee candidates cannot be
classified as verified mathematical inconsistencies, and replay manifest v2
pins the fee metadata observation IDs separately. Mission Control shows that
count in run history. Partial, unreported, mismatched, unsupported, held, stale,
and otherwise missing fee evidence remains unknown.

Follow-up test commit `90bd11e` adds explicit future-at-quote, stale-at-quote,
and stale-at-replay rejection cases for estimated fees.
API test commit `ad1415b` verifies the saved fee status and both observation IDs
are returned from the bounded Markets endpoint.
Storage test commit `f35677d` extends the legacy replay fixture with a
schema-v1 manifest that lacks the new fee-ID field. That test passed
independently and confirms the stored JSON and result hash remain unchanged;
the wider storage/replay comparison selection was not rerun after this test-only
change.
Focused verification after the implementation passed **35** economics/replay
tests, **3** saved-evidence/API fee and quarantine tests, **19** storage and
replay-comparison tests, **2** adapter capability/metadata tests, and **1**
Mission Control fixture test (**60 passed** total). Strict mypy passed for the
six changed Python source modules; Ruff check/format, TypeScript typecheck,
targeted ESLint/Prettier, and `git diff --check` passed. One existing
Starlette/httpx TestClient deprecation warning appeared in the API selection.
The full Frontier suite and production frontend build were not run under the
current host-pressure sample. No public source request, held-data read,
service, production configuration, or historical artifact was used or changed.

### Relationship review history checkpoint — 2026-10-27 17:52 UTC

The append-only review store now has a hash-checked newest-first history query,
and `GET /api/frontier/relationships/{id}/reviews` returns keyset pages of at
most 50 records. Its cursor is bound to the relationship identity, UTC review
timestamp, and review ID. The route rejects held-source relationships before
returning their review history. Mission Control fetches pages only when the
review history panel is opened and provides a load-older control; self-attributed
labels and assertion references remain explicit.

The relationship-review API test module passed **13 tests**, including two-page
history ordering, malformed and oversized cursor rejection, and corrupt-record
hash rejection. The source-quarantine integration test passed **1 test** and
confirms the history route returns 409 for a held-source relationship. The
Frontier component suite passed **8 tests**, including history rendering;
TypeScript typecheck, ESLint, Prettier, Ruff check/format, and `git diff --check`
passed. The targeted strict mypy command reported 14 existing errors in four
imported Veritas/Arena files and none in the two selected source files. The
production build and browser E2E were deferred at a 17:52 UTC memory PSI sample
of 45.66% `some` / 41.31% `full`, with 474 MiB swap free. No source or held-data
read, service change, or deployment occurred.

### Bounded uncentered text-search pagination — 2026-10-27 17:58 UTC

Relationship text search now pages through a deterministic breadth-first
result window. The cursor binds the normalized query, depth, page size, and
append-only graph revision; stale graph revisions and mismatched queries are
rejected. The API still seeds from at most 200 recorded market records and
scans at most 500 relationship rows per request, and the UI states that this is
not a full-universe search. The Frontier API module passed **44 tests**; after
extending the new case to a depth-two chain, that bounded search test passed
again independently. The Frontier component suite passed **8 tests** including
search submission, pagination, and the displayed coverage limit. TypeScript,
ESLint, Prettier, Ruff, and `git diff --check` passed. At 17:58 UTC, memory PSI
`avg10` was 32.30% (`some`) / 25.89% (`full`), with 475 MiB swap free. A fresh
production build and browser E2E remain deferred. No public or held-source data
was accessed.

## 13. Performance and resource measurements

The previous focused backend run (54 tests) completed in 10.65 seconds wall time,
used 3.97 seconds user CPU, and peaked at 145,628 KiB RSS (about 142 MiB). After
the schema-v5 graph adjacency change, 56 tests completed in 11.43 seconds wall
time, used 3.97 seconds user CPU, and peaked at 145,560 KiB RSS; the process
recorded zero socket messages. The latest 59-test focused run completed in 11.89
seconds wall time, used 4.03 seconds user CPU, and peaked at 145,936 KiB RSS;
the latest 63-test graph-pagination run completed in 16.38 seconds wall time,
used 4.75 seconds user CPU, and peaked at 148,684 KiB RSS. Both runs recorded
zero socket messages. The standalone 501-edge fixture took 4.35 seconds wall,
1.12 seconds user CPU, and peaked at 65,756 KiB RSS while constructing and
inserting the graph and reading one 500-row page. These are bounded test
measurements, not a
production service capacity estimate. The two focused
Frontier browser cases ran serially with one worker and completed in 6.5
seconds. No service or persistent Frontier worker was started. The host and
protected service cgroups were not treated as spare Frontier capacity based on
this process-local test measurement.

The latest full `tests/frontier` run with v2 trade pages and preserved
outcome-token fields passed 59 tests in 15.00 seconds wall time, used 3.25
seconds user CPU, and peaked at 110,952 KiB RSS with zero socket messages and no
swaps. The legacy adapter/offline-API regression passed 10 tests in 3.09 seconds
wall time at 121,420 KiB peak RSS. Frontier browser cases ran serially with one
worker and completed in 6.3 seconds. These are isolated verification jobs, not a
production capacity guarantee.

The paired-replay focused regression completed in 21.07 seconds wall time and
peaked at 154,656 KiB RSS (about 151 MiB), with zero swaps and zero socket
messages. The one-sided-fill focused regression completed in 21.36 seconds wall
time and peaked at 155,636 KiB RSS (about 152 MiB), with zero swaps and zero
socket messages. Targeted Frontier Playwright completed in 7.3 seconds with one
worker. These are isolated verification measurements, not host capacity
measurements.
These remain bounded local development measurements and do not establish host
admission headroom or service capacity.

The broader Arena/Frontier regression completed in 49.97 seconds wall time and
31.65 seconds user CPU, with 535,504 KiB (about 523 MiB) process peak RSS, zero
swaps, and zero socket messages. It was run serially before the supervised
fixture replays. The latest actual worker took 0.199392 seconds, used 0.067554
seconds user CPU and 0.010943 seconds system CPU, and reached 167,288,832 bytes
process peak RSS (159.5 MiB). This is one deterministic fixture sample, not a
host capacity measurement.
The follow-up Frontier API module took 8.24 seconds. Frontend unit tests took
4.95 seconds total and the three targeted Frontier browser cases took 7.5
seconds with one worker. The built Frontier chunks are 67.76 kB JavaScript and
29.81 kB CSS with the job-history, result, and readiness state panel.
These local process measurements do not establish that the production API or
host currently has headroom for an Arena worker.

The October 27 Kalshi MVE component checkpoint's complete Frontier suite
peaked at 247,084 KiB RSS over 21.77 seconds wall time. Its production frontend
build peaked at 658,824 KiB RSS over 12.51 seconds wall time. Both had zero swaps
and zero socket messages. These are isolated development-process measurements
and do not qualify production resource sustainability.

The 118-test replay-v6 lineage regression used 24.89 seconds wall time,
8.24 seconds total user-plus-system CPU, and peaked at 254,696 KiB RSS. It
recorded zero swaps and zero socket messages. This is one bounded local test
measurement; it is not a production capacity or deployment qualification.

At `2026-10-27T11:28:57Z`, before considering a browser-server run or production
frontend build, the host reported 9.8 GiB available memory and 3.4 GiB swap in
use; memory PSI `avg10` was 35.78% (`some`) and 32.22% (`full`). The active
`midas-api.service` cgroup used 527,319,040 bytes against a 1,610,612,736-byte
`MemoryHigh`. The 121-test Python run itself stayed at 259,044 KiB RSS and used
no swap. Because browser/build workloads would add processes during elevated
memory pressure, they were not started. This is a dated admission decision, not
a deployment-readiness measurement.

At `2026-10-27T16:41:19Z`, before deciding whether to run the full Frontier
suite or another production frontend build, memory PSI `avg10` was 0% for
`some` and `full`, while `avg300` was 17.36% and 15.70%. Available memory was
9,809,116 KiB (about 9.35 GiB); only 484,228 KiB (about 473 MiB) of the 4 GiB
swap device was free. The targeted selections above were kept short; the full
suite and build were deferred. This is a host admission observation, not an
application service measurement or deployment-readiness result.

At `2026-10-27T16:49:36Z`, memory PSI had risen to `avg10` 40.64% (`some`) /
36.38% (`full`), `avg60` 42.33% / 38.23%, and `avg300` 36.64% / 33.16%.
Available memory was 9,581,096 KiB (about 9.14 GiB); free swap was 484,348 KiB
(about 473 MiB) of 4 GiB. The new legacy-manifest test itself passed in 0.55
seconds; the wider storage suite and all larger jobs remain deferred. This is a
host observation and a targeted test result, not a service capacity estimate.

## 14. Actual scientific findings

The original captures contain five public HTTP 200 responses: Kalshi market
listing (20:01:44Z), Kraken AssetPairs and depth, Polymarket Gamma event listing,
and a later Kalshi orderbook query at 20:07:27Z. The listing-only API round trip
at 20:41:18Z–20:41:19Z adds three HTTP 200 listings, one per venue. A second
round trip at 21:10:40Z–21:10:43Z made two public requests per venue through the
Frontier API and persisted one listing and one book snapshot per source. The
selected Polymarket book had 8 asks and 10 bids; Kraken had 10 asks and 10 bids;
the Kalshi book had no YES or NO levels and its response lacked a unified
exchange snapshot timestamp. Kraken book levels carry independent update times.
The calls were sequential and therefore are not a synchronized cross-venue
snapshot. All six raw response hashes and the capture-envelope hash were
recomputed successfully. The Kalshi listing includes multivariate
event/selected-leg fields and remains a conditional event with unverified
payoff. Kraken evidence is spot-pair data. The captured Polymarket event
“Will the Democratic Party control the House after the 2026 Midterm elections?”
and Kraken XBT/USD do not provide a defensible equivalent payoff relationship.

At `2026-10-26T21:25:20.750899Z`–`21:25:27.005495Z`, the bounded API path
captured one listing/metadata response, one book, and one trade response per
venue. Polymarket and Kraken returned ten normalized trades each; Kalshi
returned a valid empty trade array. The API read-back matched those counts.
Requests were sequential, each response was HTTP 200, and the largest raw body
was 68,758 bytes. The envelope hash is
`ca72a2aa2095ae02660f0ea23c0a6e94019929bd7d1e174b0446673637e04570`; all nine
raw-body hashes were independently recomputed. Trade prints do not establish
available depth, matched timestamps, or executable fills.

At `2026-10-26T22:56:38.585296Z`–`22:56:38.728359Z`, a separate direct adapter
probe requested exactly one Polymarket Data API v2 page for a condition in the
saved listing. The 10-row request used a 65,536-byte response bound and zero
retries; it returned HTTP 200, ten rows, and a continuation cursor. All ten rows
mapped to the same Yes token. The raw body and normalized batch were read back
from an isolated temporary store and hash-verified.

At `2026-10-26T23:02:48.888920Z`–`23:02:49.046817Z`, the isolated local
Frontier API accepted that condition/page-bound cursor and made exactly one
unauthenticated continuation GET with retries disabled. HTTP 200 returned ten
more trades for the same Yes token and another continuation cursor. None of the
ten native trade IDs overlapped the first page. The raw body and normalized
batch were read back from the temporary 8 MiB store. Its raw SHA-256 is
`a2790da7bb4ea1faafe118562818b9de95b400b6f21d55b2bf3cb0697245fa32`, stored
row SHA-256 is
`5197ee99f491e2970d3656ae394a5279a9a135335a7a60f45a377db4d1715e5a`, source
cursor SHA-256 is
`ccf6e9eaf39ba97a889068435cc8cb1283d99b40c1de81f81df9b56a5b320d98`, and
serialized artifact SHA-256 is
`d95c09da91bdf840a7b8fee693a32b14b5d47d8677307773c20ac8c26e7dc405`.
Both live pages contain public trade prints for one outcome token. This bounded
two-page observation verifies the local API continuation path, not a complete
history walk, order-book depth, cross-venue equivalence, synchronization, or
execution.

At `2026-10-26T23:29:53.349697Z`–`23:29:54.049333Z`, the isolated API made one
fresh Kalshi listing GET and one ticker-filtered trade-page GET with zero
retries, 65,536-byte caps, and an 8 MiB temporary store. Both returned HTTP 200.
The saved multivariate ticker
`KXMVECROSSCATEGORY-S2026AI6WGLUADXUYU2PZ-PGLXFSG4I` normalized as a conditional
event. Kalshi returned zero rows and an empty continuation cursor. Raw hashes
`ccd9144ebab67664ef0b724925d97fe597f906b9b26e30be421cf43d269f4d4c` and
`ce91679332b1b83d2574366e4cc72f6d41bf656ccc2fa9cf574ee4f9ac6809e7` and row
hashes `72e105ad6b96f6d0968fb68822016bb7384fdc5f65956219343e219cf07e389b` and
`cc12462c22bd77a76bb674c8ace8b9b081726e032a4ff981c7ee17980e19c51a` verified
on read-back. This tests endpoint reachability, persistence, and empty-page
termination; no genuine Kalshi trade row was returned to validate the live row
normalizer. The fixture path validates row mapping and mismatch rejection.

The earlier one-market Gamma capture at `2026-10-26T20:41:18.972060Z` included
`feesEnabled=true`, `feeType=zero_fees`, and a market fee schedule with exponent
1, taker-only, and rate 0. The raw body hash is
`657c587bd9faeef246ffb6b27f9a2a9a00f8eb90123629b1c10fdffd434130a6`; the
normalized fee record hashes the exact fee fields and expires five minutes after
receipt. This validates the parser against one genuine market observation only.
It does not establish general Polymarket fees, fee stability outside that
window, other fee exponents, or any Kalshi/Kraken fee applicability. The
fixture-driven nonzero rate `0.04` covers the supported taker formula, and a
mutated exponent-2 record is rejected as unknown.

Thus the captures verify endpoint accessibility and preserve heterogeneous
source evidence, but do not establish a verified cross-venue relationship,
simultaneous quote, meaningful depth, or opportunity. No captured event carries
the payoff/resolution evidence needed to enter the multi-outcome evaluator. The
public fixture count is not venue-wide coverage. Controlled positive binary and
multi-outcome arithmetic fixtures only show that bounded constructions are
evaluated as designed; they are not scientific or economic findings.

## 15. Economic limitations

Kalshi fee parameters are recorded, but exact market/account applicability
remains unresolved; Kraken account-tier fees are unknown from the public spot
capture; and Polymarket fee semantics remain constrained to the strict
exponent-1 normalizer and five-minute market metadata expiry. A separate,
non-classifying funding-currency sensitivity accepts explicit user FX
assumptions and venue-local virtual balances. It does not provide sourced FX,
alter candidate P&L, or establish that capital can be transferred or converted.
Cross-venue collateral, transfer/withdrawal costs, account funding allocation,
capital duration, jurisdiction, custody, and settlement access remain
unmodeled. Public depth is a time-stamped displayed snapshot, not a fill
guarantee. In this evidence set, cost-adjusted discrepancies and executable
opportunities remain unestablished.
The saved Kalshi fee-metadata pair supports a standalone one-fill sensitivity
and a bounded manual one-order sensitivity under the July 7, 2026 public
quadratic taker formula and both documented balance-precision cases. Replay now
can compile complete hash-matched event/series evidence into an estimated
candidate fee and the independent audit re-derives it. The candidate estimate
models one fill, checks metadata freshness against quote and replay times, and
uses a conservative `$0.01` non-direct balance-alignment scenario. It is not an
account fee quote or book-priced result. Maker/mixed-order fills, FCM charges,
actual account precision, multi-fill realization and rebates, later schedule
changes, and other execution costs remain unresolved. Candidate estimates are
conditional or incomplete and do not verify economic eligibility.

## 16. Unresolved defects and blockers

No active code/test blocker is known in the implemented subset. Major acceptance
gaps are deferred work, not hidden passed checks:

- Live API-to-store validation covered one listing, one book, and at most ten
  legacy trades per venue. One direct v2 first page and one API-route
  continuation page were hash-verified; no third page, full history walk, or
  live browser-to-source session was run. Fee endpoints,
  live retries/degradation, timeouts, repeated schema variation, and book
  freshness across a time series remain unverified. Deterministic API tests cover
  invalid JSON, JSON parser-complexity limits, invalid UTF-8, HTTP 503 and 2xx
  schema-failure evidence, bounded retry attempts, source isolation, health
  degradation, and recovery.
  Oversized partial bodies are rejected and not persisted.
- No verified genuine cross-venue event relationship exists in the sample.
- Relationship reviews are self-attributed only. Reviewer identities and
  external assertion IDs are not authenticated or retrieved, so the workflow
  cannot establish independent source truth beyond the persisted market fields.
- Centered graph neighborhoods use left/right endpoint indexes, a 200-market
  recorded window, three-hop limit, and 500 scanned relationship rows per
  request. One-hop paging uses a timestamp/ID keyset; two- and three-hop pages
  preserve deterministic breadth-first ordering by recomputing the same
  revision-pinned result window. A 201-market frontier fixture verifies bounded
  query chunking. Relationship review history is now available through bounded
  hash-checked keyset pages and on-demand Mission Control drill-down; held-source
  edges remain rejected. Uncentered text search now pages deterministic BFS
  results with a revision-bound cursor, but still searches only the latest
  200-record market window and scans at most 500 relationship rows. Full-universe
  search/clustering and authenticated review remain unimplemented. A later
  focused browser test verifies a revision-pinned depth-two graph page; the
  earlier memory-pressure deferral is superseded for that focused case.
- The only multi-outcome family is a same-market all-long construction over
  verified one-hot exhaustive states; only controlled fixtures have exercised it.
  The bounded binary implication verifier now feeds a separate long-only
  implication candidate family and independent audit. It is exercised only by
  controlled fixtures; semantic equivalence remains unauthenticated, and no
  genuine captured pair supports an implication result. General multi-leg
  search remains unimplemented.
- The independent economic audit rechecks supported arithmetic from the same
  pinned normalized evidence. It cannot authenticate source semantics, reviewer
  identity, external assertions, fee authority, timestamps, or exchange truth;
  it is not a second independent market-data source.
- No account-specific fee quote, sourced FX rate, cross-venue capital transfer,
  or settlement-risk model exists. The venue-local funding-currency sensitivity
  is a separately labelled user-assumption scenario that does not change
  candidate costs or establish conversion availability. One-sided and partial-
  fill sensitivities model hypothetical exposures, not actual fills, queue
  position, or execution probability. The Kalshi replay estimate is one-fill
  and conditional, and does not resolve account applicability.
- No continuous source worker, incremental book stream, gap reconstruction, or
  source-specific long-horizon quality study exists.
- A bounded Frontier paired-replay job is now registered with Arena and exposed
  through its local API and Mission Control. It reuses the host-wide admission
  gate and has fixture, API, and UI coverage, but no systemd worker was admitted
  or launched. There is still no Laboratory experiment manager or durable
  campaign scheduler. The Frontier-specific Python suite passes **322 tests**,
  and the configured web unit and browser suites pass **40** and **12** tests
  respectively as of 2026-10-28. The complete repository Python suite,
  deployment-scale concurrency, and steady-state resource sustainability remain
  unverified.

## 17. Production deployment prerequisites

No production deployment is authorized or performed. Before a separately
reviewed deployment, require: expanded adapter-through-API validation covering
books, trades, fee endpoints where available, and source degradation; schema
migration and backup/recovery review; real store
growth/CPU/memory admission measurements under isolated limits; source-specific
rate and jurisdiction review; fully specified fee/settlement models for any
economic gate; relationship adjudication audit; monitoring and storage-cap
operations; full relevant regression and browser tests; a deployment rollback
plan; and explicit operator authorization. Do not attach Frontier workers to the
Reality recorder.

## 18. Future research opportunities

Priority order:

1. Broaden v2 source validation only for a concrete unanswered behavior. One
   direct first page and one API-route continuation now have live, hash-pinned
   evidence; do not continue fetching pages just to grow the sample. Broaden
   degraded-source evidence only through a short bounded probe.
2. The centered multi-hop API/UI path is revision-bound and has deterministic
   BFS fixture coverage. The complete configured browser suite now passes,
   including graph neighborhood pagination. Extend beyond the current
   200-market/500-row bounds or add clustering only after representative data
   and resource measurements justify the added scope.
3. The Kalshi saved-evidence replay estimate now covers one supported quadratic
   taker fill. Extend it only when permitted public evidence and an independently
   checked model establish further fee timing, precision, maker/mixed-fill, or
   multi-fill behavior. Keep Kraken account fee tier unknown without
   authenticated data; no candidate may use unknown or expired fees as zero.
4. Seek real public multi-outcome metadata that meets the strict payoff and
   resolution requirements; broaden accepted payoff families only with
   independently checked evidence.
5. Arena supervisor wiring has completed two bounded controlled-fixture jobs,
   with result integrity and process CPU/RSS recorded. Resource sustainability
   remains unmeasured; do not launch another fixture merely to repeat wiring.
   Design the next bounded job only around a scientific comparison with pinned
   multi-source inputs and measurable value. Add durable Laboratory experiment
   definitions only if a concrete use case requires them. Do not launch
   unattended campaigns.
6. Only after representative evidence, consider authenticated reviewer identity
   and independent external assertion ingestion; this needs a separately
   designed security boundary.
7. Venue-local funding-currency sensitivity now accepts explicit user
   assumptions without changing candidate economics. Only after permitted,
   representative rate and settlement evidence is available should Frontier
   consider integrating FX into candidate P&L, cross-venue capital allocation,
   settlement/transfer costs, or instrument hedge models.

## 19. Exact files and commits changed

Implementation and documentation commits on this branch:

- `4bd3b7f2636d5cd8d069fb2e2b2e97188ad68247` — bounded joint-state basket
  candidate generation, replay manifest and canonical map identity, independent
  payoff audit, stored-observation API, and explicit Mission Control editor.
  Files: `apps/api/frontier.py`, `apps/web/src/Frontier.test.tsx`,
  `apps/web/src/Frontier.tsx`, `apps/web/src/frontier.css`,
  `packages/midas/frontier/economics.py`,
  `packages/midas/frontier/independent_audit.py`,
  `packages/midas/frontier/joint_economics.py`,
  `packages/midas/frontier/models.py`, `packages/midas/frontier/replay.py`,
  `tests/frontier/test_api.py`, `tests/frontier/test_capital_carry.py`,
  `tests/frontier/test_fx_sensitivity.py`,
  `tests/frontier/test_joint_state.py`,
  `tests/frontier/test_relationships_economics_replay.py`.
- `b0f38c2` — adds the explicit joint-state editor flow to
  `apps/web/e2e/frontier.spec.ts`; fixture metadata and replay response are
  intercepted, and the test asserts zero venue-probe requests.
- `29f1a5b` — adds a seeded 48-case differential subset-oracle test and
  `tests/frontier/benchmark_joint_state_search.py` for the 12-instrument,
  64-state synthetic search ceiling.
- `bc8d073` — caches per-instrument mapped payout vectors and incrementally
  computes subset payouts, costs, and market coverage in
  `packages/midas/frontier/joint_economics.py`.
- Documentation checkpoint on this branch — this report, mission ledger,
  current-state entry, architecture, operations, and development/API guidance
  for the joint-state implementation. The commit identity is in branch history
  and the final handoff.

- `047298b` — paginated uncentered graph text search through a revision-pinned,
  bounded BFS result window; connected search submission, previous/next pages,
  and explicit coverage limits in Mission Control.
- `d0b7f0f` — added bounded, hash-checked relationship review history with
  relationship-bound keyset cursors, held-source rejection, on-demand
  Mission Control pagination, and API/UI/quarantine regressions.
- `0b293915511aa08f008b5b12241ad1238ab8c96a` — reject blank or non-string
  relationship mapping entries in the browser before submission and cover the
  no-request error path.
- `95372c8feb1129609e3e2ed4f20179432ed4e446` — added fixture coverage for a
  non-identity joint-state mapping with the implication source on the
  canonical right endpoint; checked candidate legs, payout states, independent
  audit, and replay output.
- `ce14e87f4d494d8a0fe5a041d4fb65fd1feab8fb` — added native Mission Control
  relationship-claim and directed YES implication review controls, capability
  gating, frontend unit coverage, and a fixture-backed browser flow.
- `6706fe1d3194224697b5101a2f92fb6ba914c693` — integrated the verified
  directed-implication edge into deterministic replay, a conditional
  NO(source)+YES(target) Decimal opportunity evaluator, and independent audit;
  added fixture-based generator, replay, API persistence, and tamper checks.
- `3e85c8d` — compiled complete saved Kalshi event/series fee observations into
  a provenance-bound conditional candidate estimate; added independently
  recomputed fee auditing, replay manifest fee-evidence IDs, held-source
  quarantine coverage, and a run-history evidence count in Mission Control.
- `90bd11e` — tested that estimated fees reject evidence received after the
  pinned quote, older than 24 hours at quote time, or more than 24 hours old at
  replay evaluation.
- `ad1415b` — extended the saved event/series evidence fixture through the
  `/api/frontier/markets` response and asserted the estimate and both
  provenance IDs are surfaced.
- `f35677d` — extended legacy replay storage coverage to a schema-v1 manifest
  without `fee_metadata_observation_ids` and confirmed hash-preserving reads.
- `0f8e1d6` — exchange-independent contracts, transport, Polymarket/Kalshi/
  Kraken adapters, relationships, Decimal economics, bounded storage/replay,
  tests, and public capture evidence.
- `3a086c3` — Frontier API, source-specific disabled-by-default configuration,
  application registration, and offline API regression assertions.
- `c9f4185` — fixed instrument-metadata market visibility/replay and recorded
  three bounded live adapter/API/store listing round trips with verified hashes.
- `38d43be` — Mission Control Frontier route, UI, styles, unit tests, and
  responsive/end-to-end test.
- `673c49a` — rendered an accessible 18-edge relationship network and added
  selected-edge evidence interaction plus desktop/mobile browser coverage.
- `b94a3fc` — versioned the economic model and made unresolved venue-fee
  exclusions explicit in per-venue capital assumptions.
- `5a2d61f` — added append-only review records and linked relationship
  revisions, compare-and-set re-review, latest-state replay queries, additive
  SQLite migration, Mission Control review UI, and revocation/migration tests.
- `084d860` — added bounded recorded-market graph neighborhoods, center/depth
  controls, live one-book API round trips for three venues, and hash validation
  for observation, relationship, review-revision, and replay list reads.
- `3fe24dd` — added bounded public trade capture/read-back, the native Mission
  Control trade table, adapter route regression tests, and preserved three-
  venue listing/book/trade evidence.
- `5e87d1893d3f20972b32adfe19081a38a6286344` — added exact, bounded same-market
  multi-outcome coverage with
  Decimal precision and quantity constraints, fee-expiry validation,
  deterministic replay, API/UI candidate details, and fixture-only tests.
- `d8d70a4dcb96da3f6eb4d5ca784af1b0500fd743` — added multi-outcome bounds and
  non-vacuous replay regression
  coverage for non-identity state mappings and reversed input order.
- `ae7c3084838a2942fab06017cacfb6657462fa53` — independently recalculated
  bounded replay candidate economics,
  persisted audit dispositions and input hashes, surfaced audit values in the
  UI/readiness view, and fixed the canonical relationship-mapping order defect.
- `53c38d7bf01a356b54c82e359ea64ab2661836f9` — preserved bounded raw evidence
  and typed diagnostics for captured probe responses that fail normalization;
  exposed diagnostic observation IDs and tested source degradation/isolation and
  recovery.
- `e8019d81a70c50446371d29d6e65ebaefba6e8e4` — retained complete bounded
  transport failure bodies, including invalid UTF-8 as base64 with original-byte
  hash verification; tested invalid JSON, encoding, and HTTP 503 diagnostics.
- `294cc6dd8be39eed6a03ebc1fcc4ae5c42bab548` — tested retry caps and confirmed
  the final bounded 503 response remains available as hash-verifiable evidence.
- `d389c24291cb63c63803c77dfdafff751806d5ef` — added schema-v5 left/right
  endpoint indexes, bounded relationship-neighborhood queries, additive v4
  migration, scan accounting, and API/query-plan regression tests.
- `872466e8eaa499ef4af8186c27757323153704e8` — surfaced the bounded graph
  scan count and incomplete-neighborhood state in Mission Control with a UI
  regression assertion.
- `cbd6dedb582c516f78003813b7308a677be72fb2` — documented indexed graph
  traversal, source limits, and updated architecture/development guidance.
- `49ee6a6c3cb172f0631db7c30ca5aebfa5b3119e` — checkpointed indexed graph
  measurements and remaining scale limits in the mission ledger.
- `aa2a001c8ebbb4d7c8e5681c698611d28163238f` — tested supported Polymarket
  fee shapes, bounded retry behavior, and truncated-stream evidence rejection.
- `5a38586988ffb517e3c9f29b6076c6a265e034e6` — documented narrow fee evidence
  and bounded response-failure coverage.
- `89eff8b09dcd82161162b2ff6174f1e840a710d5` — implemented bounded,
  revision-bound graph keyset pages and stale-cursor tests.
- `711a5639ba165d966ac8149625bba7adef7ae569` — added Mission Control graph
  continuation controls and desktop/mobile coverage.
- `58fe77ba8d6030798e8a70629ca863f988c8fabb` — updated graph architecture,
  development notes, and the engineering report.
- `67f79cde6b37ac51c226c4338196a1b2482e37aa` — added Polymarket v2 cursor
  pages, outcome-token-preserving schema v2, bounded API persistence, and
  adversarial cursor/page tests.
- `7c6cc21764d124f61211b79299335d78e8260c69` — added source-config-gated
  Mission Control page controls, outcome identity display, and UI/browser tests.
- `e661e06e22b2d29bd68e13dd6e6b423c698fec27` — preserved the direct first-page
  and live API continuation captures, verified their hashes, and updated the
  architecture, development, README, and engineering-report handoffs.
- `a6bcf60a0eed50e9082e2f7361c5321280b57fba` — added Kalshi cursor-paginated
  public trade capture, the ticker/page-size-bound API route, source-neutral
  trade-page controls, contract/API/UI tests, and one hash-verified empty live
  page capture.
- `225dc8db78b7ac9e60218c7be325ae77f15d8603` — added the local evidence-bound
  Kalshi one-fill taker-fee sensitivity, rounding scenarios, manual-input UI,
  tests, and an offline derived artifact; canonical candidate economics is
  unchanged.
- `127176b708a941f7f22fd643ea0e20addb91bf7a` — checked one-fill precision
  against Kalshi's documented rounding example and updated the capability
  declaration to describe the remaining candidate-fee boundary.
- `1e3d30a13db8588fae5e72a39f56fa7db625479a` — added bounded paired replay
  over identical local evidence, atomic persistence for both arms and the
  comparison, comparison API/workbench, replay-v4 mapping/proposal-limit input
  hashing, and adversarial storage/identity/UI coverage.
- `5af50b9714d571a0c730f15a0e261f2d4ece2b3e` — added exact one-sided
  full-or-no-fill sensitivity, independent audit version 2, economic model
  version 4, replay version 5, responsive candidate stress details, and
  exhaustive small-case differential and unknown-fee coverage.
- `6fa3696e9225d78d1ca3c54ce21cbb885de58aa8` — integrated content-addressed
  Frontier paired-replay snapshots with a bounded offline Arena job, result
  integrity API, explicit Mission Control submission/history, and fixture/API/UI
  coverage. Worker runtime was not validated under host admission.
- `cf6bade452e5cc6fe821c7280adfca97aa563396` — verified that resource-admission
  denial preserves the pinned snapshot and creates no job.
- `f5c7129ef14741b9a5027a9cf22111e13daf6276` — documented the Arena replay
  integration, caps, validation, and outstanding supervisor-runtime limit.
- `886e1300c535339ca614fcbbe04b3e6984dbee93` — made the readiness gate inspect
  bounded completed-job evidence and runtime fields, separated it from resource
  sustainability, and added valid/corrupt fixture transitions.
- `109df84f8bdf70b9601762dc5d53a932330cfe20` — persisted per-worker process CPU
  deltas and peak RSS in Arena job manifests, projected only bounded metrics
  through job history, and displayed them in Mission Control with an explicit
  capacity limitation.
- `fba28dfee450f6d6fb1605f836408bccaada5158` — moved the API's finite,
  nonnegative, range-bounded numeric checks into a typed helper.
- `26287927bdda8c51a47ab4cf3e77321c2d305301` — fixed optional systemd unit-ID
  narrowing and sorted-path typing in the Arena API. Focused import-following
  mypy now passes for the Arena API and job module; 20 Arena API tests pass.
- `c9e3be6990fab75c50df845d355dfac164d179b0` — added hash-matched, persisted-
  evidence Kalshi one-order taker sensitivity with native-instrument binding,
  exact Decimal fee/rounding outputs, bounded API and Mission Control fill
  editor, and order-level accumulator/rebate regressions.
- `c59be55` — documented the Kalshi order-fee model's source, account, precision,
  and candidate-economics limitations.
- `a087cb2` — added API-boundary tests for partial Kalshi event/series failure,
  immutable diagnostic evidence, source-health degradation, and recovery.
- `401ddfa` — recorded the partial-failure recovery evidence and current
  verification boundary.
- `b84dac2` — normalized bounded Kalshi MVE selected-component market/event
  identifiers and YES/NO sides, persisted the response, and surfaced the
  unverified-combo boundary in Mission Control.
- `62617bb` — documented the Kalshi MVE component checkpoint and preserved
  evidence limits.
- `415f3d4` — made the independent audit classify repeated-market two-leg
  candidates as incomplete evidence.
- `928de98` — documented that malformed-leg audit fix and its focused test.
- `b4cfcbe` — added bounded Polymarket/Kalshi public event-group normalization,
  captured direct source evidence, parent-context UI, cross-venue hypothesis
  discovery, and API relationship evidence linked to stored observation IDs.
- `b640bd2` — documented event-group capture provenance, the relationship
  evidence-link behavior, updated source limitations, and current focused
  verification.
- `29cb909` — bumped the relationship matcher to v4 and rejects text candidates
  when explicit years conflict across a parent title and child title or between
  venues, with regression coverage for a generic parent title.
- `38ad1fa` — introduced replay v6 and overlays exact store observation record
  IDs into API-loaded market/book provenance so manifests, candidate evidence,
  paired replay, and Arena snapshots retain resolvable source lineage; added
  end-to-end API/store/replay regressions.
- `5c14049` — added revision-bound breadth-first pagination for centered
  two-/three-hop graph queries, deterministic chunking for wide BFS layers,
  Mission Control continuation controls, cursor/revision/API tests, and a
  multi-hop browser test definition. The browser test was not run at this
  checkpoint because of the dated host-pressure admission decision.

Principal changed paths:

- `packages/midas/frontier/{models.py,registry.py,relationships.py,economics.py,independent_audit.py,storage.py,replay.py}`
- `packages/midas/frontier/adapters/{base.py,normalization.py,transport.py,polymarket.py,kalshi.py,kraken.py}`
- `apps/api/{config.py,main.py,frontier.py,arena.py}`
- `packages/midas/arena/{jobs.py,frontier_replay.py}`
- `apps/web/src/{App.tsx,Frontier.tsx,Frontier.test.tsx,frontier.css}` and
  `apps/web/e2e/frontier.spec.ts`
- `tests/frontier/*`, `tests/arena/test_frontier_replay.py`,
  `tests/integration/test_api.py`
- `data/frontier/live-probes/*`, including
  `2026-10-27-kalshi-public-trade-page.json`
- `.env.example`, `.gitignore`, `README.md`, `docs/ARCHITECTURE.md`, `docs/DEVELOPMENT.md`,
  and `docs/frontier/*`

The Kalshi trade-page implementation and live evidence are committed as
`a6bcf60a0eed50e9082e2f7361c5321280b57fba`. The architecture, development,
README, mission ledger, and report now document its source limits and latest
verification.

The bounded Kalshi MVE implementation and retained public response are commit
`58cb6c7`. Its changed code paths are the Kalshi adapter/model/protocol, local
Frontier API route, Mission Control view/styles, and adapter/API/frontend/browser
tests. The associated development, current-state, README, architecture, ledger,
and report updates preserve the source omission and resource-limited verification
status.

Commit `001b103` fixes the event-detail empty-list parsing case found by the
bounded follow-up GET and adds an exact saved-response replay regression. The
raw observation, original v7 failure record, and separately normalized v8 store
read-back remain in the versioned probe artifact.

Commit `a40d2ee` adds Kalshi adapter v9's single-event MVE `tickers` filter,
response identity validation, Mission Control support, mismatch and exact
saved-response tests, and the preserved public capture. Its exact changed
implementation/evidence paths are `packages/midas/frontier/adapters/base.py`,
`packages/midas/frontier/adapters/kalshi.py`, `apps/api/frontier.py`,
`apps/web/src/Frontier.tsx`, `apps/web/src/Frontier.test.tsx`,
`apps/web/e2e/frontier.spec.ts`, `tests/frontier/test_adapters.py`,
`tests/frontier/test_api.py`, and
`data/frontier/live-probes/2026-10-27-kalshi-mve-ticker-filter-r1.json`.
The report, mission ledger and developer/current-state handoffs record the
capture's digest reconciliation and verification boundary.

Documentation checkpoint `98fbf3a` updates `README.md`,
`data/frontier/live-probes/README.md`, `docs/DEVELOPMENT.md`,
`docs/MIDAS_CURRENT_STATE.md`, `docs/frontier/FRONTIER_ARCHITECTURE.md`, this
report, and `docs/frontier/FRONTIER_MISSION_LEDGER.md` with the v9 interface,
source evidence, hash reconciliation, and measured verification results.

Commit `4193ddb` updates `apps/web/e2e/frontier.spec.ts` so the existing
browser flow submits and displays the single-event ticker filter. Formatting
and lint pass; Playwright enumerates all three Frontier cases, but the browser
itself was not launched under the latest host-pressure sample.

Documentation checkpoint `47664ad` updates `docs/frontier/FRONTIER_ARCHITECTURE.md`,
this report, and the mission ledger with the dated Kalshi fee-schedule versus
native-series mapping gap. No fee logic or candidate economics changed.

Commit `7ad28c5` implements Kalshi adapter v11's optional selected-leg
settlement-value preservation. Exact changed files are
`packages/midas/frontier/models.py`,
`packages/midas/frontier/adapters/kalshi.py`,
`packages/midas/frontier/relationships.py`, `apps/web/src/Frontier.tsx`,
`apps/web/src/Frontier.test.tsx`, `apps/web/e2e/frontier.spec.ts`,
`tests/frontier/test_adapters.py`, `tests/frontier/test_api.py`, and
`tests/frontier/test_relationships_economics_replay.py`. The source field is
preserved/displayed but not used to infer combo payoff. Value-specific live
validation is pending because the existing capture omitted it.
Commit `d6d4540` adds the API/store round-trip regression for a schema-shaped
fixture value; it does not change the preserved live capture.

### Latest MVE verification update (2026-10-27 11:51 UTC)

- `pytest -q tests/frontier/test_adapters.py tests/frontier/test_api.py -k
  multivariate`: **9 passed, 49 deselected** in 1.61 seconds. `/usr/bin/time -v`
  measured 2.06 seconds wall, 1.25 seconds user CPU, 75,004 KiB peak RSS, zero
  swaps, and zero socket messages. One existing Starlette/httpx TestClient
  deprecation warning remains.
- The focused Mission Control MVE unit test passed. Frontend typecheck,
  targeted ESLint/Prettier, Python Ruff/format, strict mypy for the Kalshi
  adapter, base protocol, models and Frontier API, `git diff --check`, and
  Playwright spec enumeration all passed. The spec lists three Frontier browser
  cases; one now drives the MVE filter and asserts `omitted` is surfaced. The
  browser test itself and production build were not run.
- At the resource sample, available RAM was 9.4 GiB, swap use was 3.4 GiB,
  memory PSI `avg10` was 32.86% some / 26.88% full, and a separately owned
  bounded Veritas batch was still active. Browser/build work was deferred; no
  service, protected Reality state, or other job was touched.
- The live finding remains narrow: one saved HTTP 200 returned a single event
  and cursor with nested markets omitted. Adapter/API tests replay the exact
  preserved source bytes. No child instruments or payoff were discovered from
  this response, and the adapter does not follow the cursor.

### Adapter v8 empty event-detail replay (2026-10-27 12:00 UTC)

- A second one-GET Kalshi request for the same MVE event returned HTTP 200 with
  `event.markets` absent and an explicit empty top-level `markets` array. The
  preserved v7 call failed normalization as `INVALID_SCHEMA`; the original raw
  capture and failure row were retained. Adapter v8 now accepts that documented
  top-level empty-list shape. Offline replay of the exact raw body produced zero
  normalized child markets, and a separate 8 MiB temporary store read back the
  normalized row with SHA-256
  `c47a0e7827849c886c2c3e290d16035e1a87c26b602d028217c90f9b58c760aa`.
- The adapter/API multivariate and saved-detail tests passed **10 tests, 49
  deselected** in 1.48 seconds; `/usr/bin/time -v` measured 1.95 seconds wall,
  1.23 seconds user CPU, 75,056 KiB peak RSS, zero swaps, and zero socket
  messages. The focused MVE frontend test passed; frontend typecheck, targeted
  ESLint/Prettier, strict mypy for the Kalshi adapter, Ruff/format, and
  Playwright test enumeration passed. Three Frontier browser cases were listed;
  browser execution and production build remain deferred.
- At 12:00 UTC, available RAM was 9.3 GiB, swap use was 3.4 GiB, and memory
  PSI `avg10` was 33.60% some / 27.12% full while a separately owned bounded
  Veritas batch remained active. This bounded adapter/parser change did not
  start or alter that job, any service, or protected Reality state.
- Together the two preserved endpoint responses show a nested-list omission on
  the filtered MVE listing and an explicit empty top-level list on event detail.
  They provide no child market, price, combo payoff, settlement equivalence,
  synchronized quote, or venue-wide absence result.

### Adapter v9 single-event MVE filter (2026-10-27 12:18 UTC)

- Kalshi adapter v9, API, and Mission Control now accept exactly one
  `event_ticker` in addition to the existing series or collection filter. The
  ticker is sent as the documented `tickers` query parameter, and a response
  that does not contain the requested event is rejected. This remains one
  bounded page; no cursor continuation or multi-event ticker list is allowed.
- One genuine unauthenticated GET through the isolated API returned HTTP 200
  for `KXMVECROSSCATEGORY-S2026ZZZB25KKPHBN3TFC`. The response contained one
  matching event, no cursor, and omitted nested `markets`; Frontier retained
  `member_list_state=omitted` and zero child markets. Raw body SHA-256:
  `3e2372de6143c0c8f37b3e77265a210596bf3c414fa33d19ee4028b1d2d3a7bb`;
  the preserved raw/normalized snapshot replayed into a fresh temporary store
  has row SHA-256
  `e6dcb76b2e18316866c078fd4778c2dff93891132e8b92104e3385c08d1271bd`. The
  capture-time digest `cea5ea38a3ffad129fa2baedf3520b9bae71e8d4919521e140f46467baf57d50`
  is retained but marked unreconciled because it does not match the payload
  included in the artifact. The reproducible hash and request bounds are in
  `data/frontier/live-probes/2026-10-27-kalshi-mve-ticker-filter-r1.json`.
- After capture and verified store read-back, the temporary probe harness
  raised `RuntimeError: Event loop is closed during AsyncClient cleanup after
  TestClient shutdown`. The capture records that cleanup error; the single
  source request was not repeated. The artifact is replayed offline by an API
  regression using the exact saved response bytes.
- The focused adapter/API selection passed **13 tests, 49 deselected** in 2.03
  seconds; `/usr/bin/time -v` measured 2.49 seconds wall, 1.36 seconds user
  CPU, 78,360 KiB peak RSS, and zero swaps. One existing Starlette/httpx
  TestClient deprecation warning remains. The frontend Vitest run passed **40
  tests across 7 files**; TypeScript typecheck, targeted ESLint/Prettier,
  Python Ruff/format, and strict mypy for the three changed Python modules with
  imported-module diagnostics suppressed all passed. The unfiltered strict
  mypy command reports 14 errors in four unchanged Veritas/Arena modules;
  there are no reported errors in the three changed modules. `git diff --check`
  passes. Browser E2E and production build remain deferred under the measured
  host pressure.
- After this checkpoint's focused selection, the complete Python Frontier and
  Arena replay regression passed **133 tests** in 29.11 seconds; `/usr/bin/time
  -v` measured 29.95 seconds wall, 8.83 seconds user CPU, 264,732 KiB peak RSS,
  and zero swaps. One existing Starlette/httpx TestClient deprecation warning
  remains.
- The existing Playwright scenario now selects `event_ticker`, asserts the
  request payload and displays the returned event. `playwright test --list`
  enumerates three Frontier browser cases; none was executed. The E2E spec's
  formatting and ESLint pass.
- At 12:18 UTC the host had 9.3 GiB available RAM and 3.4 GiB swap in use;
  memory PSI `avg10` was 32.67% (`some`) / 28.61% (`full`), with `avg60` at
  35.97% / 31.36%. No browser or build process was started; the complete Python
  regression itself used zero swap.
- Reconciliation found that the artifact's initially reported row digest did
  not match its preserved raw and normalized objects. That earlier digest is
  retained and explicitly labeled unreconciled. The exact included snapshot
  now has a separately computed row hash and a fresh temporary-store read-back;
  the API regression also recomputes its row hash from the returned persisted
  payload. The raw source-body digest itself matched throughout.
- This adds evidence that the public endpoint honors the documented single
  event filter. It does not reveal the child markets, validate combo payoff,
  establish settlement equivalence, or demonstrate any economic opportunity.

### Kalshi fee-schedule applicability review (2026-10-27 12:17 UTC)

- The official Kalshi Help Center fee page links the July 7, 2026 fee-schedule
  PDF. That document lists the generic taker formula and a separate `KXMVE`
  schedule row with maker multiplier 2 and taker multiplier 1. This is a
  dated source document, not proof that every multivariate series inherits
  those terms ([Fees](https://help.kalshi.com/en/articles/13823805-fees),
  [Fee Schedule for July 2026](https://kalshi.com/docs/kalshi-fee-schedule.pdf)).
- The preserved October 27 event/series metadata capture is for
  `KXMVECROSSCATEGORY`, not `KXMVE`. Its series endpoint reports
  `quadratic_with_combo_maker_fees` and multiplier 1, with no event override.
  The ticker difference is unresolved evidence, so Frontier does not transfer
  the `KXMVE` maker multiplier to that series or infer a maker charge from the
  taker-only sensitivity.
- No code, fee schedule, or candidate economics changed. Maker/mixed-order
  applicability, account balance precision, any mapping between these native
  identifiers, and upcoming schedule changes remain open research requirements.

### Kalshi selected-component graph extension (2026-10-27)

Commit `3164d6f` adds Kalshi adapter v10's parent-bound single-child market
detail operation, API validation/persistence, Mission Control rule inspection,
fixture regressions, and one genuine child response capture. Commit `ee28bab`
tests that `market_metadata` advances the bounded graph revision. Documentation
checkpoint `043da75` records the v10 behavior and hash-pinned capture.

Commit `756ff89` bumps the deterministic relationship matcher to v5 and adds
same-venue `source_component_reference` hypotheses when the saved parent and
recorded child IDs align. The edge retains both store observation IDs, stays a
hypothesis, and cannot support payoff arithmetic. It is verified against the
saved public Kalshi parent listing and captured child detail in offline replay.
Commit `74d9a76` clarifies that matching an event ID is conditional on the
selected-component record providing one. The full Frontier/Arena regression
passed 137 tests after matcher v5; the saved-source replay passed separately.

Latest isolated checkpoint commits and exact changed files:

- `51afe86` — `packages/midas/frontier/storage.py`,
  `tests/frontier/test_storage.py`, `tests/frontier/test_coinbase.py`,
  `docs/frontier/FRONTIER_ARCHITECTURE.md`,
  `docs/frontier/FRONTIER_OPERATIONS.md`,
  `docs/frontier/FRONTIER_ENGINEERING_REPORT.md`,
  `docs/frontier/FRONTIER_MISSION_LEDGER.md`,
  `docs/MIDAS_CURRENT_STATE.md`.
- `999561c` — `docs/frontier/FRONTIER_ENGINEERING_REPORT.md`,
  `docs/frontier/FRONTIER_MISSION_LEDGER.md`, `docs/MIDAS_CURRENT_STATE.md`.
- `6bc0351` — `packages/midas/frontier/models.py`,
  `packages/midas/frontier/adapters/transport.py`,
  `packages/midas/frontier/adapters/base.py`,
  `packages/midas/frontier/adapters/normalization.py`,
  `packages/midas/frontier/storage.py`, `apps/api/frontier.py`,
  `apps/web/src/Frontier.tsx`, `apps/web/src/Frontier.test.tsx`,
  `tests/frontier/test_adapters.py`, `tests/frontier/test_api.py`,
  `tests/frontier/test_coinbase.py`, `tests/frontier/test_storage.py`,
  `docs/frontier/FRONTIER_ARCHITECTURE.md`,
  `docs/frontier/FRONTIER_OPERATIONS.md`.
- `3665aec` — `docs/frontier/FRONTIER_ENGINEERING_REPORT.md`,
  `docs/frontier/FRONTIER_MISSION_LEDGER.md`, `docs/MIDAS_CURRENT_STATE.md`.
- `008106b` — `packages/midas/frontier/adapters/coinbase.py`,
  `tests/frontier/test_coinbase.py`.

### Recent 2026-10-28 continuation commits

- `eab4a0b`, `634ee5f` — strict JSON constant parsing and regression coverage;
  `packages/midas/frontier/adapters/transport.py`,
  `tests/frontier/test_adapters.py`, and the report and mission ledger.
- `1938dc4` — disable environment-derived proxy routing for the public
  transport; `packages/midas/frontier/adapters/transport.py`,
  `tests/frontier/test_transport.py`, and the report and mission ledger.
- `eadec5d` — reject injected proxy transports;
  `packages/midas/frontier/adapters/transport.py`,
  `tests/frontier/test_transport.py`, and the report and mission ledger.
- `8ad54d7` — contain injected adapter hosts within the declared venue set;
  `packages/midas/frontier/adapters/base.py` and
  `tests/frontier/test_adapters.py`.
- `8d61a62` — assert the native UI's spot-versus-event payoff disclosure;
  `apps/web/src/Frontier.test.tsx`.
- `9589ced` — anchor the Arena migration-pilot subprocess import to its
  worktree; `tests/arena/test_migration_pilot_verification.py`, the report, and
  the mission ledger.
- `ba03b75` — guard specialized held-source routes;
  `tests/frontier/test_source_data_permissions.py`,
  `docs/MIDAS_CURRENT_STATE.md`, the report, and the mission ledger.
- `02b7cbb`, `319cb1e`, `4bf8379`, `5bab54d`, `c8deaef` — current-state and
  acceptance checkpoints in `docs/MIDAS_CURRENT_STATE.md`, this report, and
  the mission ledger.
- `fbfb08b`, `8513dee`, `df3af66`, `59f0e70`, `d521344`, `bbeb1ef`,
  `55407dd` — report and mission-ledger checkpoints for proxy validation,
  protected-resource admission, public egress, transport verification,
  parser admission, adapter host containment, and spot-disclosure verification.
- `46fe772` — records the Arena CPU-pressure stop in this report, the mission
  ledger, and `docs/MIDAS_CURRENT_STATE.md`.
- `d48a528` — expands this report's current acceptance matrix;
  `docs/frontier/FRONTIER_ENGINEERING_REPORT.md`.
- `8438320` — indexes the acceptance-matrix expansion in this report;
  `docs/frontier/FRONTIER_ENGINEERING_REPORT.md`.

All listed files are verified from the respective commit trees. The 16:21
Arena-stop checkpoint was committed as `46fe772`; the 16:30 protected-service
and resource recheck is recorded at the beginning of this report, ledger, and
current-state handoff.

## 20. Final status and continuation instructions

### Saved fee-evidence replay checkpoint — 2026-10-27

Commits `3e85c8d`, `90bd11e`, `ad1415b`, and `f35677d` implement the source-backed
replay estimate and test its freshness, Markets API output, and legacy manifest
compatibility.
The public event/series pair remains immutable and is used only after raw
response, endpoint, identity, freshness, and source-hold checks. Fixture
verification establishes deterministic arithmetic, evidence lineage, and
independent-audit agreement. It does not establish an account fee, live
applicability, multi-fill cost, or executable net opportunity. At this saved-fee
checkpoint, economic model v8, independent audit v5, replay v8, and Kalshi
adapter v16 were current in the worktree. The implementation is undeployed;
source permission remains blocked.
The full Frontier suite and production build are deferred at the measured
16:41 UTC host-pressure sample recorded in Section 13.

### Venue-separated virtual capital comparison (2026-10-27)

Code commit `9d7b599516ca70895525c701543c507054bcfbe6` adds a candidate-detail
workbench for comparing a manually entered virtual balance against modeled
capital by venue. Inputs stay in browser component state and never reach the
API or persistence. Each venue is compared independently with exact decimal
arithmetic. A missing/mixed quote currency disables comparison, and unknown
applicable fees prevent a sufficiency claim. The current comparison uses
canonical capital denomination identities and keeps virtual balances separate
by venue and exact unit. This does not model actual account balances,
collateral, transfer eligibility, or settlement duration.

The implementation changed `apps/web/src/Frontier.tsx`,
`apps/web/src/Frontier.test.tsx`, `apps/web/src/frontier.css`, and
`apps/web/e2e/frontier.spec.ts`. The Frontier component test file passed **8
tests**; frontend typecheck, ESLint, and Prettier passed. One focused Playwright
case passed and covers depth-two graph pagination, venue-fragmented funding,
and mobile overflow. A production build was attempted after the code change,
then stopped before completion as host memory PSI rose. At the final sample
(`2026-10-27T13:13:42Z`), PSI `avg10` was 38.92% (`some`) / 33.95% (`full`),
available RAM was 9.3 GB, and swap use was 3.5 GiB. The latest change therefore
does not have a verified production build; the earlier v12 build is not evidence
for this UI revision. No source request, service, production configuration, or
historical artifact was changed.

### Quote-currency completeness correction (2026-10-27 13:18 UTC)

Code commit `cca4038` fixes a UI review finding: the funding comparison now
requires every candidate leg at a venue to declare the same quote currency. A
partially missing currency disables the comparison. A regression case was
added to `apps/web/src/Frontier.test.tsx`, but it has not been run. Only
`git diff --check` passed after this follow-up. At `2026-10-27T13:18:58Z`,
memory PSI `avg10` was 37.39% (`some`) / 32.69% (`full`), available RAM was
about 9.2 GiB, and only 553 MiB of swap remained free. The prior 8-test
component and focused browser results predate this correction; they do not
verify it. Run the focused component test and typecheck after host pressure
eases. No source, service, or production action was taken.

### Payout denomination and drained-capture integrity (2026-10-27 13:28 UTC)

The economic review found that equal numeric amounts are not interchangeable
when `PayoffSpec.payout_currency` differs from its settlement asset. The strict
same-payoff verifier now rejects a market whose payout currency and payoff
settlement asset differ, and also rejects a disagreement with the market-level
settlement asset. Binary and same-market multi-outcome candidate generation
repeat the supported denomination checks; the independent arithmetic audit
requires the same evidence. No USD/USDC valuation, stablecoin redemption, or
network bridge is modeled. A six-test focused regression group passed, covering
relationship rejection, a forged verified-edge bypass attempt, binary
candidate rejection, independent re-audit, and multi-outcome rejection.

The API review found that `/probe/{venue}` and `/probe/polymarket/trades`
drained adapter captures before validating normalized-record lineage, so an
identity/hash mismatch could lose the complete raw response. Both paths now
preserve still-unpersisted captures in diagnostic records. The generic route
removes a capture as soon as its successful observation is stored, avoiding a
duplicate failure record if a later book or trade leg fails. Four focused API
tests passed: the Polymarket v2 route and generic market, book, and trade
lineage failures each retain raw bytes with a matching hash, while prior
successful listing evidence remains single-counted. Tests used MockTransport
and isolated temporary stores; no public request was made.

Code checkpoint `f6cf347899da981093140b0ec44f03816c46e0d5` changes
`apps/api/frontier.py`, `packages/midas/frontier/economics.py`,
`packages/midas/frontier/independent_audit.py`,
`packages/midas/frontier/relationships.py`,
`tests/frontier/test_api.py`, and
`tests/frontier/test_relationships_economics_replay.py`.
Follow-up code checkpoint `3f8a5cabfe209d105d0ddde948f9862cf72fb8fb` fixes
`SourceHealth.requests_in_window`, which previously exposed the lifetime
request counter under a window label. It now counts request starts over the
trailing 60 seconds using a bounded monotonic timestamp history; per-operation
deltas still use the lifetime count. Its focused regression command was
`/home/charlie/midas/.venv/bin/pytest -q --tb=short tests/frontier/test_adapters.py -k 'source_health_request_count_is_a_bounded_rolling_window'`;
it reported **1 passed, 41 deselected**. The code changes
`packages/midas/frontier/adapters/base.py`,
`packages/midas/frontier/adapters/transport.py`, and
`tests/frontier/test_adapters.py`.

Cross-venue timing received a separate guard in code checkpoint
`25a9cc711976da49b80bdaacc3b51c2ac6f82bae`. It requires matching known
timestamp semantics, bounds timestamps by replay time, and includes both
provenance clock-uncertainty values in the maximum skew comparison. The
positive control and missing-uncertainty, mismatched-semantics, and future-time
cases, including an explicit unknown-semantics case, passed in one focused
regression (**1 passed, 21 deselected**). Its command was
`/home/charlie/midas/.venv/bin/pytest -q --tb=short tests/frontier/test_relationships_economics_replay.py -k 'cross_venue_timing_requires_comparable_semantics_and_clock_bounds'`.
Current venue adapters do not populate clock-uncertainty estimates, so their
cross-venue `timing_verified` field remains false; arithmetic classification
does not establish simultaneous execution. The change is in
`packages/midas/frontier/economics.py` and
`tests/frontier/test_relationships_economics_replay.py`.
Documentation checkpoint `47254341322d7f2d89ce55147c8ac574be2a4b80` updates
`README.md`, `docs/DEVELOPMENT.md`, `docs/MIDAS_CURRENT_STATE.md`,
`docs/frontier/FRONTIER_ARCHITECTURE.md`, this report, and adds
`docs/frontier/FRONTIER_OPERATIONS.md`. The final ledger identity update is
tracked separately.

The API regression command, from the Frontier worktree, was
`/home/charlie/midas/.venv/bin/pytest -q --tb=short tests/frontier/test_api.py -k 'preserves_drained_capture_on_lineage_mismatch or cursor_pages_are_bound_and_persisted'`;
it reported **4 passed, 31 deselected**. The focused economics selection
reported **6 passed**. Ruff check and formatting passed for all changed Python
files.

Ruff check and formatting passed for the changed Python files. At `13:28:55Z`,
host memory PSI `avg10` was 39.81% (`some`) / 34.86% (`full`), available memory
was about 9.1 GB, and 553 MiB of swap remained free. That older pressure sample
is not the admission state for the later focused run below. No protected
service, production configuration, or historical evidence was changed.

### Focused regression and static-check results (2026-10-27 13:40 UTC)

The following combined engine/API regression run passed **99 tests** with one
Starlette/httpx deprecation warning:

`/home/charlie/midas/.venv/bin/pytest -q --tb=short tests/frontier/test_api.py tests/frontier/test_adapters.py tests/frontier/test_relationships_economics_replay.py`

The Frontier component file passed **8/8** tests after the missing-quote-
currency case was corrected to use Testing Library's scoped `within` query.
Web TypeScript typecheck, targeted ESLint, and Prettier passed. The test-helper
correction is code commit `f206dfedc34cf3fafae0b74afc5e13376c036b4a`. The
focused depth-two/capital-fragmentation/mobile browser case passed earlier but
was not rerun after this correction.

The targeted mypy command was
`/home/charlie/midas/.venv/bin/mypy packages/midas/frontier/adapters/base.py packages/midas/frontier/adapters/transport.py packages/midas/frontier/economics.py packages/midas/frontier/relationships.py packages/midas/frontier/independent_audit.py apps/api/frontier.py`.
It exited 1 after reporting 14 errors in four unmodified imported modules:
`packages/midas/veritas/independent_economics.py`,
`packages/midas/veritas/analysis_catalog.py`,
`packages/midas/veritas/continuous_analysis.py`, and
`packages/midas/arena/director.py`. It emitted no diagnostics in the six
explicit Frontier/API targets. The full repository suite, remaining
Frontier/Arena tests, and production frontend build remain unverified.

At `13:40:25Z`, memory PSI `avg10` was 0% (`some`/`full`), `avg300` was
19.26% / 16.92%, available memory was about 9.3 GB, and 553 MiB of swap remained
free. No live source request was made.

### Kalshi MVE reported settlement arithmetic (2026-10-27 13:01 UTC)

Code commit `8a3e25c` bumps the Kalshi adapter to v12 and adds a local,
saved-evidence-only audit for Kalshi multivariate event settlement values. The
adapter preserves bounded component `yes_settlement_value_dollars`, parent
`settlement_value_dollars`, and the optional strict-boolean `is_provisional`
flag. The API route reads at most 200 recorded Kalshi market rows, makes zero
source requests, and does not invoke candidate generation. The calculation
supports at most 64 selected components and uses Decimal arithmetic: a selected
YES value is the source-reported YES value; a selected NO value is one minus
that value; the selected values are multiplied and compared with the recorded
parent value.

The audit compares only complete inputs for a settled parent with an explicit
`is_provisional=false`; a missing flag is treated as non-final. It reports
incomplete evidence, non-final source values, an
unsupported structure, or source-reported product match/mismatch. Mission
Control displays the per-leg values, product, parent value, missing IDs,
assumptions, observation ID and raw hash. It links to Kalshi's [combo
settlement guidance](https://help.kalshi.com/en/articles/13823820-combos),
[NO scalar settlement guidance](https://help.kalshi.com/en/articles/17515177-protected-nfl-player-markets),
and [MVE API schema](https://docs.kalshi.com/api-reference/events/get-multivariate-events).
The source values are compared with arithmetic derived from that guidance; this
does not independently authenticate the source, review component outcome
rules, verify the actual event outcome, or establish price, timing, fees, fills,
or returns. It does not modify opportunity generation or payoff verification.

The v12 implementation changed `apps/api/frontier.py`,
`apps/web/e2e/frontier.spec.ts`, `apps/web/src/Frontier.test.tsx`,
`apps/web/src/Frontier.tsx`, `packages/midas/frontier/adapters/kalshi.py`,
`packages/midas/frontier/economics.py`, `packages/midas/frontier/models.py`,
`tests/frontier/test_adapters.py`, `tests/frontier/test_api.py`, and
`tests/frontier/test_relationships_economics_replay.py`. This documentation
checkpoint also updates `README.md`, `docs/DEVELOPMENT.md`,
`docs/MIDAS_CURRENT_STATE.md`, `docs/frontier/FRONTIER_ARCHITECTURE.md`,
`docs/frontier/FRONTIER_ENGINEERING_REPORT.md`, and
`docs/frontier/FRONTIER_MISSION_LEDGER.md`.

The API/store, arithmetic, UI and browser examples use documentation-shaped
fixtures. The preserved live child response lacks component settlement values;
there is no live settlement audit result. The pre-link-field full Python
Frontier/Arena run passed **148 tests**. With the final official-source-link
field present, the focused adapter/economics/API selection passed **17 tests**.
The full frontend suite passed **40 tests**, and all **4** isolated Frontier
Playwright cases passed; the new case verifies that the local audit performs no
exchange probe. TypeScript, ESLint, Prettier, Ruff, strict mypy and the
production frontend build passed. The build retained existing large-chunk
warnings. At `2026-10-27T13:01Z`, memory PSI `avg10` was 38.72% (`some`) /
32.96% (`full`), available RAM was 9.93 GB, and 3.46 GiB swap was in use. No
additional full Python run was launched. This dated admission decision is not a
host capacity result. No public request, service, production configuration, or
historical artifact was changed.

Frontier’s isolated engine/API/UI foundation is **implemented and boundedly
verified**. The mission as a whole is **not complete**. It remains unmerged,
undeployed, without ongoing collection, and without genuine verified
cross-venue economics.

| Major component | Status | Evidence and limit |
| --- | --- | --- |
| Isolated baseline/worktree and preserved unrelated changes | COMPLETE AND VERIFIED | Branch starts at verified V6 commit; original dirty worktrees untouched. |
| Adapter protocol, capability registry, bounded GET transport | COMPLETE AND VERIFIED | Contract tests, all capability declarations, host/size/rate/redirect bounds; the transport also preserves request/body elapsed nanoseconds from a monotonic clock in successful and complete-error evidence. Kalshi MVE discovery is explicitly supported while Polymarket/Kraken remain unsupported. Kalshi adapter v17 parses documented `price_ranges` into exact-Decimal instrument intervals, preserves raw native metadata, distinguishes absent from empty, and rejects malformed/oversized ranges. The grid anchor and endpoint treatment remain conservative implementation choices, not live-verified semantics. |
| Kalshi MVE settlement metadata and arithmetic audit | PARTIALLY VERIFIED | Adapter v13 introduced bounded component YES settlement values and optional parent settlement/provisional fields; Kalshi adapter v15 retains that behavior. A saved-evidence-only API/UI audit recomputes the selected component product for up to 64 legs and compares it with the parent value only for complete evidence and explicit finality; audit schema v2 identifies its algorithm and returns the parent lifecycle/provisional flag. Direct official rule/schema links and observation/raw hashes are shown. All settlement arithmetic remains fixture-only; the preserved live child lacks values, no live audit result exists, and the method does not verify outcomes/rules or alter candidate economics. |
| Polymarket, Kalshi, Kraken Spot, and Coinbase Exchange Spot adapters | PARTIALLY VERIFIED | Polymarket/Kalshi/Kraken fixture and prior bounded live evidence remain as described above. Coinbase adapter v1 implements configured product metadata, aggregated L2, and one bounded trade page with explicit maker-side semantics, exact increments, source sequence/time retained in raw evidence, and no account fee assertion. Coinbase behavior is fixture-only; the terms version gate and separate public-probe flag default off. No Coinbase API request or capture has occurred, and no cross-venue Coinbase relationship is validated. Account fees and spot/event payoff equivalence remain unresolved. |
| Canonical market/instrument normalization | PARTIALLY VERIFIED | Binary event, conditional event, multi-outcome event, and spot-pair forms are represented; FrontierMarket schema v4, BookSnapshot v2 and TradeObservation v3 retain exact quote-denomination identities where a source mapping is established. `MarketInstrument.price_increment_ranges` distinguishes missing from explicitly empty Kalshi source data and preserves exact start/end/step values while `native_fields` keeps the original values. Coinbase product fixtures retain exact base/quote units and source constraints but remain contextual spot instruments with no event payoff. Candidate and independent audit checks reject out-of-range, off-step, empty-list, and boundary quotes; range endpoint semantics remain undocumented, so endpoints fail closed. Instrument, book, fee, trade, candidate-leg and capital units are distinguished from display codes. Legacy rows load with identity absent and remain economically incomplete. V2 Polymarket trades retain native outcome-token identity; Kalshi MVE component references remain source assertions; `MarketBatch` schema v2 preserves typed `MarketGroup` membership state. The genuine MVE response records member-list state `omitted` and zero child markets. Payoff/resolution semantics remain unverified. |
| Relationship hypotheses, review revisions, indexed neighborhoods, and payoff/implication verifiers | PARTIALLY VERIFIED | Self-attributed review API/UI, append-only revisions, latest-state replay, tamper/migration checks, left/right endpoint-indexed 1–3 hop scans capped at 500 rows, one-hop keyset pages, and revision-bound multi-hop BFS pages with deterministic recomputation and 201-market chunk coverage. Matcher v5 includes bounded exact-ID MVE selected-component references as HYPOTHESIS edges with both source record IDs; a saved Kalshi parent listing and child detail replay into one such edge. A bounded directed binary implication verifier checks complete complementary payout vectors over a bijective state mapping (maximum 1,024 states), records each side's settlement asset/time, and requires the pinned observation for both source markets. Review history now has a hash-checked API endpoint with bounded keyset pagination and on-demand Mission Control drill-down; held-source rejection and two-page history are fixture tested. Uncentered text search pages a deterministic BFS result window with a query/depth/page-size/graph-revision cursor; search still covers at most 200 recorded markets and 500 relationship rows. Mission Control review controls select the YES direction and left-to-right state mapping, gated on verified exhaustive binary payoff, resolution, YES/NO instruments, and pinned market records. The API verifier remains authoritative, and the semantic state mapping plus reviewer identity are not authenticated. The economic engine consumes verified edges only in its conditional long-only implication family. Matcher v4's explicit year-conflict rejection remains. A genuine House-control topic pair remains text-only HYPOTHESIS and fails strict same-payoff verification. Reviewer authentication and full-universe search remain absent. |
| Opportunity candidate and independent economic checks | PARTIALLY VERIFIED | Two-venue all-long binary, directed YES implication, and same-market 3–16 state one-hot exhaustive coverage; economic model v13 computes exact full/no-fill exposure plus a five-point, quantity-step-filtered partial-fill sensitivity for up to 16 legs, with source-supported fees recalculated per aggregate partial quantity; independent audit v10 rederives both. Controlled replay tests reject off-step Kalshi quotes and quantities in generator/audit. Three-leg differential fixtures enumerate the entire 125-point partial grid; a rounded Kalshi fee fixture checks that partial fees are not linearly scaled; quantity-step grid filtering, unknown fees, audit agreement, and the 16-leg bound are tested. The separable partial grid does not estimate fill probabilities, intermediate continuous fractions, multi-fill rounding, price paths, or hedge/unwind. Per-venue delay and fee expiry are modeled at declared future execution time, not observed latency. Positive implication results remain conditional because semantic mapping evidence is unauthenticated. No genuine implication pair or economically eligible live result is present. The transport now records per-request monotonic elapsed duration, but adapters still omit source-clock uncertainty, so live cross-venue timing remains unverified. Broader funding/settlement costs and operational feasibility remain incomplete. |
| Kalshi taker-fee sensitivity and replay estimate | PARTIALLY VERIFIED | Hash-matched event/series evidence supports one-fill and bounded one-order Decimal sensitivities for two documented quadratic taker fee types, both balance-precision cases, per-fill rounding, order accumulation, and capped rebates. Adapter v17 preserves complete override, explicit series inheritance, partial, and unreported states. Saved-evidence replay compiles only complete, identity- and raw-hash-matched supported quadratic fee metadata into a FeeStatus.ESTIMATE; it enforces no-look-ahead and 24-hour quote/replay freshness, models a single fill, and uses `$0.01` non-direct balance alignment as a conservative scenario. The independent audit re-derives that estimate, and Replay v10 pins fee metadata observation IDs separately. Partial/unreported/mismatched/stale evidence remains unknown; the July schedule's `KXMVE` multiplier is not transferred to differently named MVE series. All candidate-fee coverage is fixture-based. Account-specific precision, exact maker/mixed-order applicability, multi-fill rounding/rebates, FCM charges, later schedule changes, and actual net economics remain unresolved. |
| Append-only evidence store and deterministic replay | COMPLETE AND VERIFIED | Storage schema v6, additive v2/v3/v4/v5 migration, bounds, hash validation, and immutability. Replay v10 carries exact store record IDs, denomination fields, and separate fee metadata observation IDs through API-loaded market/book provenance, manifests, candidate legs, and Arena snapshots; direct in-memory replay retains adapter IDs. Replay-v5 economic output includes full/no-fill sensitivity and pins effective mappings/proposal limit. The separate Arena wrapper uses immutable content-addressed snapshots and hash-verified result artifacts; two controlled fixture workers completed and the latest recorded CPU/RSS. |
| Frontier API and source configuration | PARTIALLY VERIFIED | Kalshi MVE discovery validates exactly one series/collection/event-ticker filter, capability/config gates, one-page bounds, and raw/normalized lineage; it does not follow the source cursor. Component detail is a separate one-GET capability, bound before the request to a ticker in a saved parent's selected legs and after the response to the saved event identity. Saved fee metadata is joined only after hash/path/identity checks, omitted for held venues, and becomes an input only to later replay. Coinbase source registration, exact reviewed-terms acknowledgement gate, explicit product allowlist, and separate public-probe flag are implemented; no Coinbase network request is allowed by default. The complete 269-test Frontier suite passes. Exact source permission and live Coinbase validation remain pending. Production build and the full 12-test browser suite now pass in isolated output/temporary workspaces. Frontier readiness summarizes candidate timing audits over its latest three non-held replays as within bounds, outside bounds, or unrecorded while retaining the existing source-quality gate state. |
| Paired scenario comparison | PARTIALLY VERIFIED | Local deterministic comparison, atomic result persistence, API/UI, and isolated browser tests pass. Two systemd-supervised Arena jobs completed over the same controlled fixture with verified result identities; the latest worker's process CPU and peak RSS are visible in Mission Control. No genuine matched live cross-venue pair or live economic claim exists. |
| Live market/book/trade and fee metadata through adapters/API | PARTIALLY VERIFIED | Earlier listing/book/trade, event-group, fee-metadata, and trade-page captures are hash-pinned. Kalshi MVE captures include filtered pages whose nested markets were omitted and one detail response with explicit top-level `markets: []`. The new one-request child detail capture matches a selected leg's saved ticker/event identities and has raw/store hashes; its rules expose fair-price fallbacks, but it has no book/price and proves neither child nor combo payoff. Fee metadata now has fixture-verified candidate replay integration, but no new public observation, current schedule verification, cross-venue timing, combo economics, venue-wide coverage, or execution was established in this checkpoint. |
| Source workers and broad historical data | DEFERRED | No persistent worker or long-duration collection. |
| Laboratory/Arena research orchestration | PARTIALLY VERIFIED | Arena job kind, content-addressed snapshots, bounded offline execution, API submission/history/result verification, process CPU/RSS capture, and explicit workspace controls are implemented and tested; two fixture jobs passed the host-wide gate and completed under systemd. Laboratory campaign management and resource-sustainability evidence remain incomplete. |
| Native Mission Control workspace | PARTIALLY VERIFIED | Local API, bounded graph/review UI with on-demand revision history and paginated 200-market-capped text search, Polymarket/Kalshi trade-page and event-group controls, explicit filtered one-page Kalshi MVE capture by series, collection, or one event ticker with returned member-list state, parent-event context, instrument-bound fee sensitivity, selected-leg component-rule and recorded-settlement arithmetic inspection, paired replay, candidate fill stress, virtual balances keyed by venue and exact denomination identity, and Arena job history/result display. The Coinbase source/capability, terms gate, and four-venue graph column are present; no real Coinbase data is displayed. The evidence disclosure now shows request start/receipt and monotonic elapsed duration. The full 40-test web suite, TypeScript typecheck, targeted ESLint/Prettier, isolated production build, and full 12-test browser suite pass. The workspace is not deployed. |
| Source data use/retention permission | BLOCKED | Kalshi Developer Agreement and Data Terms restrict the relevant API/data uses; the applicable regional Kraken terms and Frontier authorization remain unverified. Coinbase Market Data Terms dated 2026-08-07 impose additional research/redistribution scope conditions; Frontier's exact organization, region, retention, and display applicability is unvalidated. Coinbase requires exact-version operator acknowledgement plus a separate public-probe flag, both off by default. No Coinbase API request or capture occurred. No new Kalshi/Kraken capture or research use of held data is authorized; existing artifacts are preserved unchanged. The 18:41 full-suite run read files later identified as held captures; no mutation is known. |
| Offline test-source separation from held captures | COMPLETE AND VERIFIED | All 15 discovered references were replaced by synthetic inputs. A scan over `tests`, `packages`, and `apps` returns no `live-probes` references. The runtime guard blocks direct path, symlink, symlink-plus-`..`, and relative `dir_fd` file-open cases through built-in `open`, `io.open`, and `os.open`; its 2 tests pass, and the complete 269-test Frontier suite passes with the guard active. A read-only code review found no ordinary test interference. Existing capture files remain unchanged. |
| Held-source application read quarantine | IMPLEMENTED, LIVE VALIDATION PENDING | Code `d38f517` filters held-venue observation lists/direct reads, source aggregates, relationships/graph edges, review and replay inputs, derived outputs, paired comparisons, and Frontier Arena replays. Code `73e008e` applies pinned-snapshot checks to Arena job summaries, details, logs, submissions, and cancellation; `e7958c1` also filters the research-activity digest; `23f9860` rejects held snapshots before inspect/reconciliation can rewrite a job manifest. Controlled fixtures verify held/missing provenance is hidden or rejected while source/snapshot/result/job-manifest artifacts remain stored. The actual preserved live store was not audited; direct database reads and exports remain outside the API filter. |
| Production readiness/deployment | DEFERRED | Separate review and authorization required; production eligibility is false. |
| Positive economic result | NOT ESTABLISHED | No genuine cross-venue equivalent or economically eligible result in captured evidence. |

To continue safely, use this worktree and branch. Preserve both completed
fixture jobs as supervisor-path evidence; do not infer source or economic
validity from them. Keep resource sustainability unmeasured until the workload
and host conditions are characterized beyond one short fixture. Live
degraded-source behavior remains unverified; do not intentionally degrade a
live source. Continue by searching for public multi-outcome metadata that meets
the strict payoff and resolution evidence requirements, reconciling Kalshi's
public event/series parameters with a defensible candidate fee schedule. The
focused depth-two browser E2E now passes. Scale beyond the graph's current
bounds only if representative data and measured resource
use justify it. Add durable Laboratory experiment management only if needed
beyond the tested Arena job wrapper. Add adversarial audit mutations only for
distinct failure modes. Expand economics only where source evidence supports it.
Re-run the focused suites before each checkpoint. Do not enable probes by
default, deploy, modify Reality, or start a long-running campaign as part of
routine continuation.

## Frontier frontend build resource checkpoint — 2026-10-27 13:42 UTC

The production frontend build was retried with
`corepack pnpm --dir apps/web build`. TypeScript completed and Vite began
transforming modules. About five seconds later, host memory PSI `avg10` had
risen to 10.74% (`some`) / 8.37% (`full`) with about 8.7 GB available RAM.
The build was stopped with Ctrl-C (exit 130) to avoid adding load. At
`2026-10-27T13:42:24Z`, PSI `avg10` was 22.14% / 16.01% and `avg300` was
14.22% / 12.27%; available RAM was 9.1 GB and free swap was about 553 MiB.
This build is **unverified**; the successful TypeScript phase does not establish
a production bundle. No service or data source was contacted or changed.

## Kalshi settlement finality guard — 2026-10-27

Review found the recorded MVE arithmetic audit accepted a settled parent when
`is_provisional` was absent. The public Kalshi MVE schema represents this as a
boolean source field, but the field can be missing in captured data. The audit
now requires the value to be explicitly `false`; both `true` and `null` classify
the source values as non-final. The focused unit selection passed **2 tests**
(`20 deselected`); the API provenance test passed **1 test** (`34 deselected`),
and the focused UI test passed **1 test** (`7 skipped`). Ruff check/format and
Prettier passed. Audit schema v2 returns algorithm version
`kalshi-mve-settlement-audit-2`, parent lifecycle, and the recorded provisional
flag; Mission Control displays them. The audit remains a comparison of
source-reported settlement arithmetic only; it does not validate market rules
or feed candidate economics. Implementation commit:
`364478853908272f5b860758fa0bb18b52b3efc8`.

Reproduction commands:

```text
/home/charlie/midas/.venv/bin/pytest -q --tb=short tests/frontier/test_relationships_economics_replay.py -k 'kalshi_mve_reported_settlement_audit_fails_closed or kalshi_mve_reported_settlement_audit_recomputes_yes_no_component_product'
/home/charlie/midas/.venv/bin/pytest -q --tb=short tests/frontier/test_api.py -k 'kalshi_mve_optional_settlement_value_persists_through_api'
corepack pnpm --dir apps/web exec vitest run src/Frontier.test.tsx -t 'captures Kalshi fee metadata' --maxWorkers=1 --minWorkers=1
corepack pnpm --dir apps/web typecheck
```

Results were 2 passed/20 deselected, 1 passed/34 deselected, 1 passed/7
skipped, and TypeScript passed. Ruff, ESLint, Prettier, and `git diff --check`
also passed. No live source call was made.

## Settlement asset identity implementation

The opaque settlement denomination remains for readable price/payout units,
and schema v2 adds structured identity fields to `FrontierMarket` and
`PayoffSpec`. Fiat identity uses a three-letter code; token/other identity
requires an explicit network ID and asset reference. The payoff and market
identities must agree; relationship verification, candidate generation, and
the independent verifier compare the complete identities. The equivalence
verifier is v3, the economic model is v6, the independent audit is v3, replay
is v7, and adapter versions are Kalshi v14, Polymarket v6, and Kraken Spot v3.
Market schema v3, book schema v2, trade schema v3, and candidate schema v2 carry
the exact denomination fields. Historical records without the optional
identity still load, but fail closed for verified payoff comparison.

Kalshi normalizes supported event settlement as `fiat:USD`. The Polymarket
adapter maps Gamma v2 position-backed markets to the documented pUSD token on
Polygon (`eip155:137`, `0xc011a7e12a19f7b1f670d46f03b03f3342e82dfb`) and routes
their public book GETs to `clob-v2.polymarket.com`. Gamma v1 CTF-token markets
remain without a canonical settlement identity. The v2 mapping comes from the
source protocol contract and is not an independent market-specific payout
attestation; both Polymarket payoff and resolution remain unverified. Official
references are the [Polymarket SDK protocol table](https://github.com/Polymarket/rs-clob-client-v2/blob/main/README.md),
[Polygon V2 deployment addresses](https://github.com/Polymarket/polymarket-v2-external/blob/main/README.md),
and the [V2 collateral adapter](https://github.com/Polymarket/ctf-exchange-v2/blob/main/src/adapters/CtfCollateralAdapter.sol).
Fixtures show identical token tickers rejected when either network or
contract-reference identity differs, across the relationship verifier and
independent audit. Legacy schema-v1 market/payoff records still load, but the
same-payoff verifier rejects them until identity is present. The identity
itself is not an independent source attestation; source, resolution, capital,
and valuation evidence remain separate requirements.

Checkpoint verification: the relationship/economics/replay module passed 25
tests; adapter, storage, and replay-comparison modules passed 60; two targeted
API tests and two targeted Frontier UI tests passed. The UI typecheck, targeted
ESLint, Prettier, Ruff, and `git diff --check` passed. These are regression
checks for this schema change, not a full repository suite, production build,
browser E2E run, live token integration, or performance benchmark. No live
source request or service mutation was made in that checkpoint.

Reproduction commands:

```text
/home/charlie/midas/.venv/bin/pytest -q tests/frontier/test_relationships_economics_replay.py
/home/charlie/midas/.venv/bin/pytest -q tests/frontier/test_adapters.py tests/frontier/test_storage.py tests/frontier/test_replay_comparison.py
/home/charlie/midas/.venv/bin/pytest -q tests/frontier/test_api.py::test_captured_cross_venue_event_context_creates_reviewable_hypothesis tests/frontier/test_api.py::test_replay_api_generates_and_persists_multi_outcome_candidate
corepack pnpm --dir apps/web exec vitest run src/Frontier.test.tsx -t 'captures Kalshi fee metadata|renders a bounded accessible relationship graph' --maxWorkers=1 --minWorkers=1
corepack pnpm --dir apps/web typecheck
```

## Polymarket versioned CLOB route checkpoint

Polymarket adapter v5 uses the Gamma market `version` field to distinguish
legacy CTF-token IDs from position-backed v2 IDs. The official [Polymarket SDK
protocol table](https://github.com/Polymarket/rs-clob-client-v2/blob/main/README.md)
documents the v2 CLOB host and pUSD collateral for position-backed markets;
the [Polygon deployment manifest](https://github.com/Polymarket/polymarket-v2-external/blob/main/README.md)
identifies the pUSD contract, and the [collateral adapter source](https://github.com/Polymarket/ctf-exchange-v2/blob/main/src/adapters/CtfCollateralAdapter.sol)
shows the pUSD/USDC.e conversion around CTF operations. The adapter maps only
Gamma v2 position markets to that pUSD identity. It leaves v1 CTF-token
settlement identity absent because the Gamma identifier schema alone does not
establish a market's collateral route. Neither payoff nor resolution is
verified by this mapping.

An unauthenticated GET to the documented v2 host could not resolve DNS from
this development environment, so the route remains fixture-tested with live
validation pending. A separate one-request GET against the v1 host returned
HTTP 200. The market condition and token matched the saved Gamma v1 observation
(`187d2a3e549953f65838c67e6165a4994e001697cb588a4a121c81647d1a2cef`); the new
book body is 2,514 bytes with SHA-256
`cecdb8d4f14fa61a7039e1559a52e02c2e7819a0342566f5d07d829841bc9aef`, exchange
timestamp `1793110593506`, 58 bid levels, and 8 ask levels. The exact raw
response is preserved in
`data/frontier/live-probes/2026-10-27-polymarket-clob-v1-book-r1.json`.

The Polymarket adapter module passed 44 tests; the full Frontier API module
passed 35 tests with one existing Starlette/httpx deprecation warning. V2
fixtures exercise host selection, exact pUSD identity, unauthenticated GET
behavior, and rejection when source version and provenance disagree. No
authenticated request, order, production service change, or deployment was
made. This does not establish a real v2 market observation or an economic
opportunity. Implementation commit `2c7bacc517e7a273d2a4f6490a01f9174b82fef1`
contains adapter v5, fixture tests, and the raw v1 book capture.

An additional adversarial verifier test holds nominal payout currency at
`USD` while changing one leg's exact settlement identity to Polygon pUSD. The
same-payoff verifier rejects the pair for both denomination and asset
identity mismatch; no pUSD-to-USD bridge is inferred. The
relationship/economics/replay module passes 26 tests with this regression.
Test commit `65a7e8d98f0674cb05d1be025e43e820ed88092c` contains the case.

## Exact quote-denomination identity checkpoint — 2026-10-27

Code commit `03dbc92` closes a remaining unit-aliasing gap. The canonical
identity now travels with instrument quote currency, public book price
currency, fee currency, trade quote currency, candidate legs, and candidate
capital. The binary and multi-outcome evaluators require the quote identity on
the instrument and its observed book to equal the verified payoff settlement
identity. Supported fee arithmetic also requires exact fee-unit identity. The
independent audit separately checks those same fields and reports incomplete
evidence when an identity is missing. Replay v7 pins the updated model fields
and economic model v6 into replay inputs; the independent audit is version 3.

The core adversarial fixture gives a network-qualified token the display code
`USD` while its event payoff declares that token and its instrument/book quote
fields still identify `fiat:USD`. A payoff relationship can be established from
the identical event terms, but candidate generation returns incomplete
evidence before price arithmetic. Additional tests strip candidate leg, capital,
or book identity and confirm independent audit returns incomplete. The UI
disables mixed-unit funding comparison and keys virtual balances by both venue
and canonical denomination, so entering fiat USD cannot satisfy a token-USD
scenario. Kalshi trade pages now emit trade-observation schema v3 with explicit
fiat USD identity; trade-batch schema v2 accepts nested trade schemas v2 and v3.
Legacy rows remain loadable with unknown denomination identity.

The full isolated Python Frontier suite passed **153 tests** in 35.35 seconds
with one pre-existing Starlette/httpx `TestClient` deprecation warning. The
Frontier React component file passed **8/8** tests. The focused Playwright
scenario for bounded graph pagination, venue-separated virtual funding, and
mobile layout passed **1/1** using an isolated temporary database and fixture
routes. TypeScript typecheck, targeted ESLint for the UI and E2E file, Prettier,
Ruff check/format, and `git diff --check` passed. The production web build
completed in 12.95 seconds at 676,320 KiB peak RSS with zero swaps. Vite reports
its existing chunk-size warning for the 503.86 kB main and 544.41 kB chart
chunks. No live source request, production service, database, or historical
artifact was changed.

This closes denomination identity for the currently supported event candidate
families; it does not make the mission complete. Cross-venue clock uncertainty,
verified public equivalence, complete capital/settlement costs, venue access,
source-worker operation, full-universe research, and positive live economics
remain unestablished. The full repository suite and full browser suite were not
run. The Polymarket v2 CLOB host remains live-validation pending. Production
deployment remains deferred.

Implementation commit `03dbc92` changed
`packages/midas/frontier/models.py`,
`packages/midas/frontier/economics.py`,
`packages/midas/frontier/independent_audit.py`,
`packages/midas/frontier/replay.py`,
`packages/midas/frontier/adapters/kalshi.py`,
`packages/midas/frontier/adapters/kraken.py`,
`packages/midas/frontier/adapters/polymarket.py`,
`tests/frontier/builders.py`, `tests/frontier/test_relationships_economics_replay.py`,
`tests/frontier/test_adapters.py`, `tests/frontier/test_api.py`,
`apps/web/src/Frontier.tsx`, `apps/web/src/Frontier.test.tsx`, and
`apps/web/e2e/frontier.spec.ts`.

Reproduction commands:

```text
PYTHONPATH=packages:. /home/charlie/midas/.venv/bin/pytest -q tests/frontier
corepack pnpm --dir apps/web exec vitest run src/Frontier.test.tsx --maxWorkers=1 --minWorkers=1
corepack pnpm --dir apps/web exec playwright test e2e/frontier.spec.ts --grep 'relationship network remains bounded' --workers=1
corepack pnpm --dir apps/web typecheck
corepack pnpm --dir apps/web exec eslint src/Frontier.tsx src/Frontier.test.tsx e2e/frontier.spec.ts
corepack pnpm --dir apps/web exec prettier --check src/Frontier.tsx src/Frontier.test.tsx e2e/frontier.spec.ts
corepack pnpm --dir apps/web build
```

## API denomination read-back regression — 2026-10-27

Follow-up commits `8a1f41e` and `43b5a08` add API-level persistence/read-back
assertions to controlled replay and trade fixtures. They confirm the exact fiat
USD identity is preserved by `/api/frontier/markets`, `/api/frontier/books`,
and `/api/frontier/trades`, then appears on replay candidate capital and every
candidate leg. Both focused tests passed (**2 passed**) with the existing
Starlette/httpx `TestClient` deprecation warning; Ruff check/format and
`git diff --check` passed. This closes the serialization check for these
fixture paths, not live-source validation. No external source, production
service, or historical store was changed.

The current source changes are in `03dbc92` (denomination model and propagation),
`8a1f41e` and `43b5a08` (API read-back regressions). Documentation checkpoints
are `48c75fa` and `2dd6b13`, with this update recorded in the mission ledger.

## Source data use permission review — 2026-10-27

The official [Kalshi Developer Agreement v1.1](https://kalshi-public-docs.s3.amazonaws.com/Kalshi-Developer-Agreement.pdf)
states that API use is limited to facilitating a member's own exchange trading
and restricts non-trading collection, caching, aggregation, and storage absent
authorization. The [Kraken API Center](https://docs-legacy.kraken.com/api/docs/guides/global-intro/)
describes public market-data interfaces, but does not itself settle permission
for Frontier's research and retention use. Kraken terms vary by region. This
project has no recorded written Kalshi research/retention authorization, and
has not classified the applicable Kraken use. This is an operational
restriction, not legal advice or a finding about prior use. See the official
terms refresh recorded below.

The application now defaults both sources off and additionally requires
`MIDAS_FRONTIER_KALSHI_RESEARCH_AUTHORIZATION_REF` or
`MIDAS_FRONTIER_KRAKEN_MARKET_DATA_PERMISSION_REF`, alongside the existing
probe flag, before enabling a live request. The reference is not validated by
the application. Source routes report why a probe is disabled, return HTTP 409
without a network request, and the readiness API reports a blocked source-use
gate. Mission Control displays the restriction. Commits `d38f517`, `73e008e`,
`e7958c1`, and `23f9860` filter held-source observations before
market/book/trade lists, direct evidence reads, relationship and graph queries,
saved-input replay, candidate/run/comparison views, and Frontier Arena replay
endpoints. Generic Arena job summaries/details/logs and research-activity
digests reject held
snapshots; generic replay submission checks the snapshot before enqueue, and
cancellation is rejected before mutation. Overview aggregates omit held-source
coverage while database size continues to account for preserved evidence. The
filter operates at the application API boundary; direct database inspection
and exports remain held.
Fixture development remains available.

The source/storage/Arena/API selection passed **13 tests** in 10.37 seconds;
the Arena replay/API modules passed **30 tests** in 4.66 seconds. The
Frontier component suite passed **8/8**. TypeScript, targeted ESLint, Prettier,
Ruff, and `git diff --check` passed. One existing Starlette/httpx TestClient
deprecation warning remains. The full suite and frontend production build were
not rerun at this checkpoint. These are fixture-based route checks, not a read
audit of the actual preserved data store. No exchange request, account access,
external message, service change, deployment, or evidence mutation was made.

The source terms and operational limits are recorded in
[`SOURCE_DATA_TERMS_REVIEW_2026-10-27.md`](SOURCE_DATA_TERMS_REVIEW_2026-10-27.md).

## Kalshi event-fee override completeness — 2026-10-27

The official [event fee-change API documentation](https://docs.kalshi.com/api-reference/events/get-event-fee-changes)
says an event fee override is layered on its parent series and that a pair of
null override values clears the event override. The current [Kalshi fee page](https://kalshi.com/fee-schedule)
shows a standard combo row (excluding uncorrelated NFL) with multiplier 1 and
maker fees at 50% of taker fees. That page also separates non-standard series;
the visible standard row alone does not establish the applicable maker terms
for a particular native series. The [MVE event schema](https://docs.kalshi.com/api-reference/events/get-multivariate-events)
lists event override fields but does not specify precedence on that endpoint.

Code commit `e950b9c` bumps the adapter to v15 and `KalshiFeeMetadata` to schema
v2. It records
`fee_resolution_state`: `event_override`, `series_inherited`,
`partial_override`, or `override_unreported`. Only the first two states are
eligible for the standalone one-fill and one-order sensitivities. Legacy saved
schema-v1 metadata remains readable, defaults to `override_unreported`, and
cannot produce a sensitivity until recaptured through the authorized path.
Mission Control displays the state beside the native fee values. Both
sensitivity outputs are schema/model v2. Candidate `FeeSchedule` and candidate
economics remain unchanged.

Fixture verification covers complete overrides, explicit null/null clearing,
missing fields, partial values, and both sensitivity rejections. The focused
Python selection passed **28 tests** in 3.49 seconds with one existing
Starlette/httpx deprecation warning. Strict mypy passed for the three changed
engine modules; Ruff check/format passed for six Python files. The focused
Frontier UI test passed (**1 passed, 7 skipped**), and TypeScript typecheck
passed. No live exchange request or read of held Kalshi captures was made.
This resolves the override-completeness behavior in code, not series-specific
maker applicability, account fee precision, fee-schedule currency, or candidate
fee integration. Source permission remains blocked and deployment remains
deferred.

## Independent timing and instrument-constraint verification — 2026-10-27

Commit `b1c1df0` advances the independent economic audit to model v4 and schema
v2. For supported cross-venue and multi-outcome candidates it recomputes local
receipt skew, exchange timestamp skew, freshness, per-source freshness limits,
timestamp semantics, replay-time bounds, book quality flags, and required
best-ask timestamps directly from pinned snapshots. Cross-venue timing also
recomputes the combined source clock-uncertainty bound. The audit records those
recomputed values and treats a mutated candidate timing claim as a disagreement.

Candidate construction and independent audit now check displayed best asks
against declared instrument tick size. A source freshness limit can also make a
cross-venue comparison timing-unverified even when the general scenario age
limit passes. A direct adversarial mutation test confirms the existing quantity
step verifier rejects an off-step leg. Test commit `4fcc628` adds direct
multi-outcome timing agreement and tampering cases as well as the cross-venue
checks. Test commit `34b8b53` verifies that a swapped, still-bijective outcome
mapping is rejected when it conflicts with the verified instrument payoffs.
Commit `5cb5747` advances the candidate economic model to v7 because the
freshness and tick checks affect candidate eligibility and replay identities;
test commit `fcf3b31` pins v7 in the replay manifest.

UI commit `89526f3` carries the independently recomputed timing values into the
Opportunity Explorer audit panel: receipt skew, exchange timestamp skew, and
the independent timing gate. Older audit records with no recomputed fields show
“Not recorded.” Test commit `3e648dd` removes the new fields from a legacy
candidate fixture and verifies all three labels show “Not recorded.” The full
frontend suite passed **40 tests**; TypeScript, targeted ESLint, and Prettier
passed. The frontend production build was not repeated.

The post-commit selection passed **134 tests** across replay/economics,
adapters, API, and Kalshi fee sensitivities in 21.88 seconds. The replay-manifest
assertion also passed in its focused deterministic-replay test. Strict mypy passed
for the three changed engine modules; Ruff check/format and `git diff --check`
passed. One existing Starlette/httpx TestClient deprecation warning remains.
This is controlled fixture validation. Live adapter clock-uncertainty values
remain absent; the full Python suite, frontend production build, performance
profile, and live-source checks were not repeated. No held-source capture,
production service, or exchange endpoint was accessed, and no deployment
occurred. These checks do not establish simultaneous execution or profitability.

Code commit `8195df4` adds bounded timing-audit counts to the Frontier
readiness source-quality detail. Its fixture writes a replay with no quantified
clock uncertainty and another with uncertainty bounds, then confirms the gate
reports both within- and outside-bounds candidates from the same non-held replay
window. The source-quality gate remains review-required or not-established; the
counts do not imply simultaneous execution. The same checkpoint tightens three
adjacent API return annotations so strict mypy passes for `apps/api/frontier.py`.
The API module passed **36 tests**; after test placement cleanup, both readiness
tests passed again (**2 passed**). The relationship/economics module passed
**33 tests**, including multi-outcome tick rejection and independent audit
mutation. Ruff check/format and strict mypy for the API module passed. The full
Python suite, production build, performance profile, and live-source checks were
not repeated. No source capture, service, or external endpoint was accessed.

The legacy-audit and held-source readiness checks proposed above were completed
in the checkpoint below using a temporary synthetic database and fixture-only
observations.

## Legacy replay compatibility and readiness coverage — 2026-10-27

Storage commit `6b08efe` keeps historical replay evidence readable when a
current model adds optional timing fields. The reader validates the stored
digest against the original JSON payload and the normalized current-model
payload, accepting either exact representation while still rejecting changed
payloads. It does not rewrite the historical JSON or hash. A synthetic audit-v3
row regression verifies that compatibility path; the storage module passed
**15 tests**, strict mypy, Ruff, formatting, and `git diff --check`.

Readiness commit `0b341c4` reports replay candidates whose old audit schema has
no recomputed timing verdict as “not recorded”; candidates missing the audit
object are also included in that timing count. Follow-up commit `e9d0ff1` counts
missing audit objects as not evaluated and leaves the independent verification
gate `NOT_ESTABLISHED` when no evaluated audit exists. Test commit `2c7763d`
checks that state for a replay window containing only an unaudited candidate.
The API fixture inserts a hash-validated v3 audit replay into a temporary store
and checks the readiness summary alongside within-bounds and outside-bounds
current records. A separate quarantine regression verifies that held Kalshi
runs are excluded from readiness totals even though their immutable rows
remain preserved.

Commit `163ab79` makes readiness return HTTP 409 with a concise storage
integrity detail when a replay payload no longer matches its pinned result
hash. Follow-up commit `e491f3f` centralizes reads of replay rows and applies
the same 409 response to `/runs`, `/opportunities`, and held-filtered
`/overview`. A synthetic source hold verifies that all four routes, including
`/readiness`, reject the corrupted row consistently. Commit `d75d1ee` applies
the same integrity response to comparison list/detail, held overview, and
relationship reads. Corrupt fixture rows remain in the temporary database;
the route returns an explicit 409 instead of partial evidence. Test commit
`050d798` adds coverage for a comparison whose pinned replay is corrupt and a
relationship whose review record is corrupt. The focused legacy, unaudited,
quarantine, replay/comparison hash, relationship hash, pinned-run, and review
record regressions passed **7 tests** in 3.40 seconds. Strict mypy for the API
route, Ruff, formatting, and `git diff --check` passed. One existing
Starlette/httpx TestClient deprecation warning remains.

These checks establish backward-compatible local replay reading and API-level
source quarantine behavior on synthetic fixtures only. They do not validate
held source records, live source quality, or economic performance. No held
capture, production database, live endpoint, service, or deployment was used.

Commit `a675a3f` adds a shared verified observation reader for direct evidence,
market, book, trade, and overview queries. Its synthetic fixture corrupts
three temporary source rows, checks that each API returns HTTP 409, and
confirms the damaged rows remain unchanged. The eight focused readiness,
quarantine, replay, comparison, review, and observation regressions passed
**8 tests** in 3.96 seconds. Strict mypy for the API route, Ruff, formatting,
and `git diff --check` passed. One Starlette/httpx TestClient deprecation
warning remains. No production or held-source records were read.

## Resource admission checkpoint — 2026-10-27 16:20 UTC

At `2026-10-27T16:20:34Z`, host memory PSI measured `avg10` 49.81% (`some`)
and 45.22% (`full`), with `avg60` at 46.14% / 41.60%. Available host RAM was
9.1 GiB; swap usage was 3.5 GiB of 4.0 GiB. CPU PSI `avg10` was 1.42%, and
I/O PSI `avg10` was 0.17%. The command's cgroup showed 2.05 GB current usage
and no `memory.high` or `memory.max` bound, which does not establish host
headroom. I did not start the full `tests/frontier` suite under this sample.
The eight targeted integrity/readiness tests remain the current verification;
they are not a full Frontier-suite pass. No service or research job was
started.

**Next safe action:** remeasure PSI after host memory pressure subsides and
only then reconsider the full `tests/frontier` suite. Use temporary test data
roots and classify any interrupted run as incomplete.

## End-to-end fee candidate API replay — 2026-10-27 16:54 UTC

Test commit `65a4f4e` first checked saved fee IDs through the returned and
persisted replay manifests. Follow-up commit `dc5ef43` extends that temporary
fixture with a controlled Polymarket/Kalshi binary pair, an asserted
same-payoff relationship, and four saved books. The local replay API produces
the expected fixture candidate: `CONDITIONAL ECONOMIC OPPORTUNITY`, `$0.18`
modeled fees, and `$1.32` worst-case modeled net P&L. The independent audit
recomputes the arithmetic, and `practical_eligibility=false`. Both fee
observation IDs remain in the returned and stored manifests. These are
synthetic observations and a controlled assertion; they are not a genuine
cross-venue event or a live opportunity.

The focused API test passed (**1 passed** in 1.36 seconds); Ruff, formatting,
and `git diff --check` passed. One existing Starlette/httpx TestClient
deprecation warning remains. The fixture uses a temporary database and empty
adapter registry, with no source requests. It validates the saved-evidence to
candidate-to-replay chain while keeping modeled returns hypothetical.

At `2026-10-27T16:54:49Z`, memory PSI was `avg10` 0.00% (`some`) / 0.00%
(`full`), `avg60` 2.94% / 2.64%, and `avg300` 22.70% / 20.48%.
`MemAvailable` was 9,845,932 KiB, with 484,520 KiB of 4 GiB swap free. The
full Frontier suite, production build, and browser E2E remain deferred. No
source, held data, service, or production setting was accessed.

## Official fee-formula cross-check — 2026-10-27 16:56 UTC

I rechecked the implemented estimate against Kalshi's [fee schedule effective
July 7, 2026](https://kalshi.com/docs/kalshi-fee-schedule.pdf) and [fee
rounding documentation](https://docs.kalshi.com/getting_started/fee_rounding).
The published formula is `M × 0.07 × contracts × P × (1-P)`, with the trade
fee rounded upward to a microdollar. Debit alignment uses the member's target
balance precision; the order-level guide also specifies an accumulator and
rebates across fills.

The single-fill sensitivity and candidate calculation implement those
rounding steps for both documented precision classes. Candidate estimates
remain conditional and use a non-direct single-fill scenario. A separate
bounded order sensitivity models the accumulator and rebate instead of
projecting a single fill across an order. The fee-sensitivity module passed
**19 tests** in 0.28 seconds, including Kalshi's documented FCM fill example
and a two-fill accumulator/rebate case. No code changed during this
cross-check; it confirms the bounded fixture model, not an account-specific
charge or present applicability of a fee schedule to an unobserved market.

At `2026-10-27T16:56:38Z`, memory PSI was `avg10` 0.00% (`some`) / 0.00%
(`full`), `avg60` 0.48% / 0.43%, and `avg300` 15.66% / 14.13%.
`MemAvailable` was 9,836,380 KiB, with 484,544 KiB of 4 GiB swap free. Broad
suite, browser E2E, and production build remain deferred.

## Persisted candidate readback check — 2026-10-27 16:57 UTC

Test commit `b01e757` asserts that the saved replay's complete candidate list
matches the response from the replay API, in addition to retaining both fee
evidence IDs. The focused API test passed (**1 passed** in 1.39 seconds);
Ruff and formatting passed, with one existing Starlette/httpx deprecation
warning. This remains controlled fixture evidence only.

After the focused run, at `2026-10-27T16:57:34Z`, memory PSI was `avg10`
39.35% (`some`) / 35.94% (`full`), `avg60` 14.33% / 13.19%, and `avg300`
16.32% / 14.79%. `MemAvailable` was 9,614,412 KiB and swap free was 484,552
KiB of 4 GiB. Broad Python/browser suites and the production build remain
deferred.

## Host-pressure admission recheck — 2026-10-27 16:58 UTC

At `2026-10-27T16:58:07Z`, memory PSI had risen to `avg10` 50.81% (`some`) /
46.34% (`full`), `avg60` 29.18% / 26.77%, and `avg300` 19.83% / 18.02%.
Available memory was 9,620,440 KiB, but only 484,556 KiB of 4 GiB swap was
free. No further test, build, source request, service action, or production
change was made after this sample. Broad verification remains deferred pending
a later low-pressure admission check.

## Property-based fee-order invariants — 2026-10-27 17:00 UTC

Test commit `1144283` adds a bounded Hypothesis check over 24 generated orders
per run: one to 32 fills, buy or sell side, varied prices/quantities, and fee
multipliers 0, 1, or 3. For direct and non-direct precision, it checks
nonnegative fill fees, rebate bounds, exact fee totals, and conservation of
signed revenue through per-fill and order balance changes. The full fee
sensitivity module passed **20 tests** in 0.43 seconds; Ruff, formatting, and
`git diff --check` passed. The property test exercises only the local Decimal
model and generated values.

At `2026-10-27T17:00:21Z`, memory PSI was `avg10` 39.43% (`some`) / 32.43%
(`full`), `avg60` 41.16% / 36.61%, and `avg300` 28.33% / 25.60%.
`MemAvailable` was 9,592,368 KiB; swap free was 484,584 KiB of 4 GiB. Broad
Frontier verification and production build remain deferred.

## Blank permission-reference gate regression — 2026-10-27 17:02 UTC

Test commit `fd5711a` adds a settings-only regression that enables the Kalshi
and Kraken probe flags while supplying whitespace-only permission references;
both `probe_allowed` results remain false. The focused test passed (**1
passed** in 0.95 seconds), and Ruff, formatting, and `git diff --check` passed.
It constructs no adapters and makes no source request. One existing
Starlette/httpx TestClient deprecation warning remains from module import.

At `2026-10-27T17:02:02Z`, memory PSI was `avg10` 45.61% (`some`) / 41.04%
(`full`), `avg60` 45.59% / 41.05%, and `avg300` 33.78% / 30.52%.
`MemAvailable` was 9,632,428 KiB and swap free was 484,596 KiB of 4 GiB.
Broad suites and production build remain deferred.

## Independent fee-calculator differential — 2026-10-27 17:04 UTC

This checkpoint adds a 32-example Hypothesis check that compares the
candidate fee calculator, the independent auditor's fee calculation, and the
non-direct one-fill sensitivity across bounded prices, quantities, and fee
multipliers. All three produced identical modeled fees. The full fee
sensitivity module passed **21 tests** in 0.50 seconds; Ruff, formatting, and
`git diff --check` passed. This is controlled Decimal-fixture evidence; it
does not read a source or establish a live fee schedule's applicability.

At `2026-10-27T17:04:54Z`, memory PSI was `avg10` 45.31% (`some`) / 40.92%
(`full`), `avg60` 44.96% / 40.74%, and `avg300` 39.03% / 35.36%.
`MemAvailable` was 9,664,080 KiB and swap free was 484,612 KiB of 4 GiB.
Broad suites, browser E2E, and production build remain deferred.

## Directed logical-implication review integration — 2026-10-27 17:15 UTC

`packages/midas/frontier/relationships.py` now includes a bounded verifier for
directed binary YES implications over an explicit bijection of joint state
spaces. It requires complete verified binary YES/NO payout vectors that are
exact complements, verified resolutions, source observation identities, and an
external assertion ID; it rejects mappings above 1,024 states. Direction and
per-market settlement assets/times are pinned in the relationship evidence and
identity. Settlement differences are preserved, not bridged. Verification
establishes only the payout-vector implication over the supplied mapping; the
shared-world semantic assertion remains unauthenticated. The verifier now runs
through the existing relationship-review API and append-only store. The route
requires both hash-checked market observations; storage accepts only the two
verified relationship types, preserves the original endpoint pair, and
confirms that the result cites the reviewed evidence. Controlled API tests
confirm persistence of the directed edge and reject a false implication
direction without writing a review. Mission Control has no directed-review
controls, and candidate generation does not consume these edges.

Nine new tests, including an exhaustive comparison of all 64 pairs of
three-state binary YES vectors, plus the relationship/economics and review API
modules passed together (**52 passed** in 4.02 seconds). The TestClient emitted
one existing Starlette/httpx deprecation warning. All three changed Python
modules pass `mypy --strict --follow-imports=silent`; the unrestricted strict
run reports 14 errors in imported Veritas/Arena modules, none in changed files.
Ruff, format check, and `git diff --check` passed. No network or held-source
records were used.

At `2026-10-27T17:16:56Z`, memory PSI was `avg10` 41.71% (`some`) / 38.28%
(`full`), `avg60` 39.03% / 35.22%, and `avg300` 29.23% / 26.23%.
`MemAvailable` was 9,433,944 KiB and swap free was 485,104 KiB of 4 GiB.
Broad suite, browser E2E, and production build remain deferred.

### Logical-implication economics and replay — 2026-10-27 17:33 UTC

Code commit `6706fe1d3194224697b5101a2f92fb6ba914c693` adds a distinct
logical-implication opportunity family. For a verified directed YES edge, it
evaluates long-only `NO(source) + YES(target)` against the recorded joint-state
mapping. It requires pinned source observations, an assertion recorded no
later than the replay cutoff, exact common settlement denomination, matching
future close/settlement times, complementary binary payouts, and fresh books.
Fees remain unknown when source evidence is incomplete. Candidate economics and
the separate audit both cap positive results at conditional because the
external assertion is self-attributed and unauthenticated. Replay v9 persists
the candidates and audits through the existing append-only API/store path.

The bounded fixture selection passed **14 tests** in 1.74 seconds, including
directed-basket arithmetic, independent audit disagreement on tampered payout,
settlement mismatch, unknown fees, stale books, replay determinism, replay-cutoff
evidence, and API persistence/read-back. Ruff check, Ruff format check, and
strict mypy on the four changed production modules passed; `git diff --check`
passed. One existing Starlette/httpx TestClient deprecation warning remains.
No live source request or held-data read was made. There is still no genuine
captured cross-venue logical implication or economically eligible live result.

At `2026-10-27T17:33:19Z`, memory PSI was `avg10` 45.57% (`some`) / 41.61%
(`full`), `avg60` 45.72% / 41.25%, and `avg300` 36.83% / 33.19%.
`MemAvailable` was 9,701,564 KiB and swap free was 485,724 KiB of 4 GiB. The
full Frontier suite, browser E2E, and production build were not run under this
pressure sample. Frontier remains isolated, undeployed, and incomplete.

### Directed implication review controls — 2026-10-27 17:38 UTC

UI commit `ce14e87f4d494d8a0fe5a041d4fb65fd1feab8fb` extends Mission Control's
existing relationship-review form with a claim selector, explicit YES
implication direction, and left-to-right joint-state mapping. It sends the
directional endpoints and omits instrument mapping for this claim. The client
offers the option only when both loaded markets have exhaustive verified
binary payoffs, verified resolution, bounded state IDs, exactly one YES and NO
instrument, and pinned source records. The server verifier remains the
authoritative check. The form labels the external assertion as a reference and
states that neither it nor the reviewer identity is authenticated.

The full frontend unit suite passed **40 tests** across seven files. The
targeted relationship-review browser test passed **1 test** with local API and
web servers, temporary storage, fixture routes, and one worker. TypeScript
typecheck, targeted ESLint, Prettier check, and `git diff --check` passed. The
browser route is fixture-intercepted and makes no external source request; it
verifies UI request construction and responsive layout, not live review
adjudication. Backend API/store persistence is covered separately by the 14
focused Python tests recorded above.

At `2026-10-27T17:38:29Z`, memory PSI `avg10` was 0.00% (`some`) / 0.00%
(`full`), `avg60` 9.89% / 8.42%, and `avg300` 30.21% / 26.89%.
`MemAvailable` was 9,790,148 KiB and swap free was 486,136 KiB of 4 GiB. A
production build and full Frontier Python suite remain unrun. Frontier remains
isolated, undeployed, and incomplete.

### Reversed endpoint and non-identity implication mapping — 2026-10-27 17:40 UTC

Test commit `95372c8feb1129609e3e2ed4f20179432ed4e446` adds a three-state
fixture where the source market sorts after the target and the joint-state map
is non-identity. Candidate generation preserves the directed source-NO and
target-YES legs, maps each target state to the correct source payout, and
matches the independently recomputed audit and deterministic replay result.
The focused implication, relationship API, replay, and audit selection passed
**15 tests** in 1.71 seconds. Ruff check and format check passed; `git
diff --check` passed. No live data or source endpoint was accessed.

At `2026-10-27T17:40:29Z`, memory PSI `avg10` was 0.00% (`some`) / 0.00%
(`full`), `avg60` 1.33% / 1.13%, and `avg300` 20.00% / 17.80%.
`MemAvailable` was 9,866,316 KiB and swap free was 486,152 KiB of 4 GiB.
Broader Frontier Python verification and the production build remain unrun.

### Full Frontier Python regression — 2026-10-27 17:42 UTC

`PYTHONPATH=packages /usr/bin/time -v /home/charlie/midas/.venv/bin/pytest -q
tests/frontier` passed **199 tests** in 37.94 seconds of pytest time and 39.01
seconds wall time. Peak RSS was 329,116 KiB, with zero swaps and zero socket
messages. One existing Starlette/httpx TestClient deprecation warning remains.
The suite includes fixture adapter contracts, API routes, logical-implication
review/replay/audit, persistence, source permission gates, and bounded Arena
resource-denial behavior. The test fixtures use temporary roots and mocked
transport; they do not validate live source availability or evidence.

At `2026-10-27T17:42:45Z`, memory PSI was `avg10` 37.14% (`some`) / 33.70%
(`full`), `avg60` 12.71% / 11.29%, and `avg300` 15.55% / 13.83%.
`MemAvailable` was 9,482,844 KiB and swap free was 486,228 KiB of 4 GiB. The
complete repository suite and production frontend build remain unrun; Frontier
is still undeployed and incomplete.

### Relationship mapping input guard — 2026-10-27 17:44 UTC

UI commit `0b293915511aa08f008b5b12241ad1238ab8c96a` rejects blank keys,
blank values, and non-string JSON values in a state or instrument mapping
before constructing the API request. The focused relationship-review component
test passed after adding a numeric-value rejection assertion; no review request
was sent for the malformed mapping. TypeScript typecheck, targeted ESLint, and
Prettier checks passed. A direct Pydantic request-model check also rejected a
numeric mapping target as `string_type`; the backend schema was unchanged.
The earlier full frontend run passed 40 tests before this narrow guard, and the
targeted test was rerun after it. The full Python suite result above is
unaffected. No source request or held-data read occurred.

At `2026-10-27T17:44:28Z`, memory PSI `avg10` was 45.36% (`some`) / 40.48%
(`full`), `avg60` 37.67% / 33.08%, and `avg300` 23.98% / 21.20%.
`MemAvailable` was 9,631,192 KiB and swap free was 486,248 KiB of 4 GiB. The
production frontend build remains deferred.

### Virtual capital-duration sensitivity — 2026-10-27 18:15 UTC

Code commit `e9da21abcacb397d0962eb8507e46f52f4daa8d5` adds a read-only,
on-demand capital carry sensitivity for saved opportunity candidates.
`GET /api/frontier/opportunities` now returns the
candidate's saved run ID and result hash; the new
`POST /api/frontier/opportunities/capital-carry` requires those exact values,
the candidate ID, and a decimal-string annual carry rate in basis points for
every venue. It reloads the append-only run, applies existing held-source
quarantine, and reads each position leg's exact pinned market observation. It
makes no venue request and writes no new database artifact.

The calculator requires exact common settlement denomination, source-marked
verified future settlement timing, resolution rule/authority and evidence
references, candidate/leg/market identity agreement, bounded rates, and
validated normalized-store-row and raw-body hashes. It computes simple interest
per venue as `capital × rate_bps / 10,000 × elapsed_seconds / 31,536,000`,
starting at the saved candidate observation time and conservatively holding
that venue's total capital through its latest candidate-market settlement.
There is no compounding, currency rounding, shared collateral, funding source,
or transfer assumption. Exact inputs/results receive deterministic SHA-256
identities. A separate calculation checks pinned market identity, source and
store-row hashes, release times, durations, carry, and adjusted gross/net P&L.
The sensitivity is hypothetical, may retain unknown-fee exclusions, and cannot
change the original candidate classification or eligibility. It does not
authenticate the settlement claim or establish executable profitability.

The full Frontier Python suite passed **208 tests** in 40.60 seconds (334,996
KiB peak RSS, zero swaps and socket messages), and the full web unit suite passed
**40 tests** before the final store-row-hash display was added. After that
additive provenance change, the focused capital model/API selection passed
**8 tests**, and the Frontier component suite passed **8 tests**. Strict mypy
for `capital.py` and the Frontier API, Ruff check/format, TypeScript typecheck,
targeted ESLint, and Prettier checks passed. The production frontend build also
passed before that final display adjustment; Vite reported its existing
greater-than-500-kB index/chart chunk warning. The latest resource sample at
`2026-10-27T18:15:31Z` showed memory PSI `avg10` 39.17% (`some`) / 34.05%
(`full`), `MemAvailable` 9,479,384 KiB and 482,448 KiB swap free; the build was
not repeated under that pressure. Browser E2E, a post-provenance full
suite/build, live settlement evidence, and deployment remain outstanding. No
live or held source, protected service, or production deployment was accessed.
Frontier remains incomplete, isolated, and undeployed.

#### Completion-matrix addendum

| Component | Current status | Boundary |
| --- | --- | --- |
| Virtual capital-duration sensitivity | PARTIALLY VERIFIED | Fixture-backed model, store-pinned API, independent arithmetic, Mission Control input/results, deterministic hashes, and targeted tests pass. No live financing terms or genuine verified live settlement inputs were tested; transfers, FX, collateral, jurisdiction, unknown fees, execution risk, and custody remain outside the calculation. |
| Mission Control capital workbench | PARTIALLY VERIFIED | Adds user-entered annual bps by venue, exact source-row/raw/resolution references, adjusted gross/net output, and limitations. Full component/API tests pass; browser E2E for this path and the post-row-hash production build remain pending. |
| Project Frontier overall | PARTIALLY VERIFIED | The mission remains isolated, unmerged, undeployed, and incomplete; source permission gates, live cross-venue semantic/economic verification, and production readiness are unresolved. |

Files changed for this checkpoint: `packages/midas/frontier/capital.py`,
`apps/api/frontier.py`, `apps/web/src/Frontier.tsx`,
`apps/web/src/Frontier.test.tsx`, `apps/web/src/frontier.css`,
`tests/frontier/test_capital_carry.py`, and `tests/frontier/test_api.py` under
code commit `e9da21abcacb397d0962eb8507e46f52f4daa8d5`; this report,
`FRONTIER_ARCHITECTURE.md`, `FRONTIER_OPERATIONS.md`, and the mission ledger
record the documentation update.

### Carry differential and browser scenario checkpoint — 2026-10-27 18:20 UTC

Code commit `b112a6ce28f606c1316916d1725a2512afe980de` adds a bounded
Hypothesis differential test over 32 generated combinations of venue capital,
annual basis-point rates, and separate settlement durations. The production
Decimal result is compared with a separately constructed exact `Fraction`
reference per venue and for the aggregate. All **8 tests** in
`tests/frontier/test_capital_carry.py` pass, including the generated examples.

Code commit `1b5fc82d3e17237e16ac846d7bdac7987edaf12a` adds a local browser
scenario intercepted entirely by explicit test fixtures. It submits the
saved run ID/hash, candidate ID, and per-venue rates; checks the independent
audit display and unchanged candidate classification; and checks the exact
source-row hash is visible in the result. ESLint and Prettier pass, and
Playwright lists all four tests in `apps/web/e2e/frontier.spec.ts`. The browser
was not launched, so this is authored and statically checked E2E coverage, not
a passed browser test.

At `2026-10-27T18:20:14Z`, host memory PSI measured `some avg10=45.75%` and
`full avg10=41.08%`, with `MemAvailable=9,691,132 KiB` and `SwapFree=482,504
KiB`. The focused browser run, full post-row-hash Python/web suites, and
post-row-hash production build remain pending until pressure materially eases.
This checkpoint used no exchange request, held-source read, protected service,
or production deployment.

| Component | Current status | Boundary |
| --- | --- | --- |
| Capital carry exact-reference differential | COMPLETE AND VERIFIED | 32 bounded Hypothesis examples compare Decimal venue/aggregate results with a Fraction reference; this verifies calculator arithmetic over the generated domain, not financing terms or executable economics. |
| Capital carry browser E2E | IMPLEMENTED, LIVE VALIDATION PENDING | Fixture route and UI assertions are authored, linted/formatted, and discovered by Playwright; no browser execution has occurred. |
| Project Frontier overall | PARTIALLY VERIFIED | Still isolated, unmerged, undeployed, and incomplete; live semantic/economic cross-venue validation, source permission review, and production readiness remain unresolved. |

Files changed: `tests/frontier/test_capital_carry.py` and
`apps/web/e2e/frontier.spec.ts` in the code commits above; this report and
`FRONTIER_MISSION_LEDGER.md` record the checkpoint.

### Exact-rational carry audit — 2026-10-27 18:21 UTC

Code commit `6fe0192` makes the capital-carry verifier arithmetically distinct
from the production sensitivity path. The sensitivity computes with bounded
Decimal arithmetic; the verifier independently reconstructs elapsed seconds
from the UTC datetime delta and calculates venue carry as an exact `Fraction`,
converting to Decimal only for comparison and output. The regression test
mutates one venue's carry amount and confirms the audit reports disagreement.

`pytest -q tests/frontier/test_capital_carry.py` passed **9 tests**. Ruff check,
Ruff format check, strict mypy for `capital.py`, and `git diff --check` passed.
This strengthens arithmetic independence; both paths still consume the same
hash-pinned candidate and settlement metadata and therefore do not authenticate
external financing or settlement claims.

At `2026-10-27T18:21:36Z`, memory PSI was `some avg10=41.79%` and `full
avg10=37.24%`, with `MemAvailable=9,661,452 KiB` and `SwapFree=482,512 KiB`.
The fixture browser scenario remains unexecuted, as do post-row-hash full suites
and the production build. No exchange request, held-source read, protected
service, or production deployment was used.

| Component | Current status | Boundary |
| --- | --- | --- |
| Capital carry independent arithmetic | COMPLETE AND VERIFIED | Decimal model and exact-rational verifier are different arithmetic paths; generated differential cases and a tampering rejection test pass. Source settlement authenticity and financing availability remain unverified. |
| Project Frontier overall | PARTIALLY VERIFIED | Isolated and undeployed; browser E2E, broad final regression/build, live relationship evidence, source permission review, and production gates remain incomplete. |

Files changed: `packages/midas/frontier/capital.py` and
`tests/frontier/test_capital_carry.py` in code commit `6fe0192`; this report
and `FRONTIER_MISSION_LEDGER.md` record the verification.

### Subsecond carry differential extension — 2026-10-27 18:22 UTC

Code commit `abb512f` extends the 32 bounded Hypothesis examples so Polymarket
and Kalshi settlement timestamps independently include random microseconds as
well as whole seconds. The separate `Fraction` reference now exercises the
audit's exact conversion of `timedelta` microseconds while still varying venue
capital and annual rates. The focused carry module passes **9 tests**; Ruff
check, formatting check, and `git diff --check` pass.

At `2026-10-27T18:22:13Z`, host memory PSI was `some avg10=45.68%` and `full
avg10=41.43%`, with `MemAvailable=9,823,344 KiB` and `SwapFree=482,520 KiB`.
The fixture browser path, post-row-hash full suites, and production build remain
unexecuted under this pressure. No live source, protected service, or
production deployment was used.

| Component | Current status | Boundary |
| --- | --- | --- |
| Capital carry subsecond differential | COMPLETE AND VERIFIED | Bounded generated cases compare Decimal model outputs to exact rational references with separate venue microsecond settlement offsets. This verifies arithmetic only, not timing truth or financing availability. |
| Project Frontier overall | PARTIALLY VERIFIED | Fixture browser execution, broad final regression/build, live cross-venue semantic evidence, source permission review, and production readiness remain incomplete. |

Files changed: `tests/frontier/test_capital_carry.py` in code commit
`abb512f`; this report and `FRONTIER_MISSION_LEDGER.md` record the update.

### Final bounded regression checkpoint — 2026-10-27 18:26 UTC

The full Frontier Python suite passed **212 tests** in 40.20 seconds. One
existing `StarletteDeprecationWarning` reports that `httpx` with
`starlette.testclient` is deprecated; it did not fail the suite. The full web
unit suite passed **40 tests** across seven files. The complete browser E2E
suite passed **12 tests** in 26.5 seconds using the Playwright configuration's
temporary database and local demo API. It covers the new fixture-only carry
request/result and all other existing UI fixture scenarios. No venue request
was made.

The first complete Frontier E2E run exposed a test-only ambiguous locator: the
capital panel exposes both the venue balance status and an older-candidate
warning. Commit `80162fe` scopes the balance assertions to `.fr-capital-row`;
the full four-test Frontier E2E file then passed. The full E2E suite passed
after that repair.

The production web build passed, including TypeScript project build. `/usr/bin/time
-v` measured **693,052 KiB** maximum RSS, zero swaps, and zero socket messages.
Vite retains its existing chunk warning: `index` is 504.00 kB and `Chart` is
544.41 kB after minification. At `2026-10-27T18:26:20Z`, memory PSI was `some
avg10=0.00%` / `full avg10=0.00%`, `MemAvailable=9,442,548 KiB`, and
`SwapFree=482,576 KiB`.

| Component | Current status | Boundary |
| --- | --- | --- |
| Frontier capital carry model and independent audit | COMPLETE AND VERIFIED | 212 Frontier Python tests include 32 bounded generated Decimal-vs-Fraction cases with independent venue microseconds, tampered carry rejection, unverified-settlement rejection, and naive-time rejection. This does not authenticate real settlement claims, funding availability, or executable economics. |
| Web unit and production build | COMPLETE AND VERIFIED | 40 web tests and TypeScript/Vite production build pass. Existing large index/chart chunk warning remains. |
| Browser E2E suite | COMPLETE AND VERIFIED | All 12 repository browser tests pass, including the four Frontier scenarios and the fixture-intercepted carry path. The carry API response is a controlled fixture. |
| Project Frontier overall | PARTIALLY VERIFIED | Isolated and undeployed. Live relationship equivalence, source permission review, live cross-venue economic validation, deferred collection/FX/collateral/transfer modeling, and production prerequisites remain incomplete. |

Code commits in this checkpoint: `a45a811` independently checks source
settlement prerequisites and rejects invalid candidate timestamps;
`80162fe` repairs the Frontier E2E locator. Full-suite verification also covers
earlier carry commits `6fe0192` and `abb512f`. No protected service, held-source
store, exchange API, or production deployment was used.

### Repository-wide Python regression attempt — 2026-10-27 18:28 UTC

The default repository invocation, `/home/charlie/midas/.venv/bin/pytest -q`,
failed during collection before running tests. Four tests use sibling imports
such as `from test_reality_foundry import ...` while `tests/` is a package and
is not on the configured Python path. A fifth collection error is
`tests/test_reality_full_scale_validation.py` importing
`midas.reality.recovery`, which is absent from the selected Frontier baseline
(whose verified source parent is `11d32a0693b25c290fd273f23e40cf7b5950d95d`) and
from current `main`. I did not copy code from another dirty worktree or change
Reality to satisfy this stale test dependency.

I retried with `PYTHONPATH=tests` and excluded only that uncollectable
full-scale file. **50 tests passed** before the suite reached
`tests/arena/test_admission.py::test_resource_snapshot_detects_workers_across_arena_roots`.
That test expected only its synthetic Arena worker reason, while the actual
host gate correctly reported an additional `host_memory_pressure` reason. At
`2026-10-27T18:28:25Z`, host PSI was `some avg10=34.98%` / `full avg10=30.76%`.
I interrupted the broader run rather than suppressing that live resource
signal. The attempt peaked at **521,880 KiB** RSS and used no swap; tests after
the interruption remain unverified. This does not invalidate the separately
completed 212-test Frontier suite, 40-test web suite, 12 browser tests, or
production build.

| Component | Current status | Boundary |
| --- | --- | --- |
| Frontier, web, and browser regression | COMPLETE AND VERIFIED | 212 Frontier Python tests, 40 web tests, 12 repository browser tests, and the production build pass. |
| Broader legacy Python regression | PARTIALLY VERIFIED | 50 tests passed before a live host-pressure gate assertion; remainder was interrupted. Default collection also has four sibling-import errors and one absent Reality recovery dependency. No test behavior was weakened. |
| Project Frontier overall | PARTIALLY VERIFIED | Development remains isolated and undeployed; source/semantic validation, broader legacy verification, and production transition prerequisites remain unresolved. |

No additional source file changed for this test attempt. This remains an
environment- and baseline-limited verification result, not a code pass.

### Deterministic Arena admission test input — 2026-10-27 18:30 UTC

The pressure failure above exposed a non-deterministic test boundary: the
cross-root worker-discovery test also called the live host-resource gate, even
though its purpose is to verify job catalog traversal. Code commit `adf1b15`
injects stable memory, disk, CPU, and PSI values for that unit test while
retaining the genuine temporary-directory scan and the assertion that a worker
blocks admission. Existing separate tests continue to check explicit pressure
thresholds. The corrected focused test passed (**1 test**); Ruff check and
format checks pass. The broader suite has not been rerun, and the Reality
recovery import remains unresolved.

At `2026-10-27T18:30:09Z`, actual host PSI was `some avg10=46.13%` and `full
avg10=41.43%`; the broader rerun remains deferred. This deterministic fixture
does not change production resource-gate behavior or conceal current host
pressure.

| Component | Current status | Boundary |
| --- | --- | --- |
| Arena cross-root admission unit test | COMPLETE AND VERIFIED | Catalog traversal is tested against a temporary two-root fixture and stable injected resource telemetry; separate tests exercise pressure thresholds. |
| Repository-wide Python regression | PARTIALLY VERIFIED | Previous attempt passed 50 tests, then saw host-pressure-sensitive assertion and was interrupted. Rerun pending lower pressure; the legacy Reality recovery test still cannot collect on this baseline. |

Files changed: `tests/arena/test_admission.py` in code commit `adf1b15`; this
report and `FRONTIER_MISSION_LEDGER.md` record the change.

### Legacy test fixture import correction — 2026-10-27 18:31 UTC

Code commit `ceea335` changes the four direct sibling imports in the
Reality/Veritas test modules from top-level `test_*` names to package-qualified
`tests.*` imports. The tests have not otherwise changed. Ruff passes, and the
four affected modules collect **51 tests**. The complete repository collection
has not been repeated, so only those four modules' collection is verified.

The remaining known collection blocker is
`tests/test_reality_full_scale_validation.py`: the verified Frontier baseline
parent `11d32a0693b25c290fd273f23e40cf7b5950d95d` does not include the imported
`midas.reality.recovery` module. That test also depends on the same missing
module through its script; its expected code is present only in a separate
Reality reliability worktree, which was not mixed into this branch.

At `2026-10-27T18:31:23Z`, memory PSI remained high (`some avg10=44.39%`,
`full avg10=40.01%`); no broad rerun was started. Frontier/web/build/browser
results remain as recorded above.

| Component | Current status | Boundary |
| --- | --- | --- |
| Legacy sibling-fixture imports | COMPLETE AND VERIFIED | Four modules now collect 51 tests through the repository's `tests` package; test behavior is unchanged. |
| Full repository Python suite | PARTIALLY VERIFIED | 50 tests passed in the prior pressure-limited attempt; full collection/runtime remains pending a lower-pressure window and the absent Reality recovery module. |

Files changed: `tests/test_reality_research_schedule.py`,
`tests/test_reality_shadow.py`, `tests/test_reality_training.py`, and
`tests/test_veritas_resumable_shadow_replay.py` in commit `ceea335`.

### Carry E2E request identity correction — 2026-10-27 18:32 UTC

Code commit `9a4ccf4` replaces the carry browser fixture's descriptive candidate
string with a 64-character lowercase hexadecimal ID. `CapitalCarryRequest`
requires that SHA-256-shaped identity, and the saved candidate used by the
API integration test has the same format. This closes a fixture/schema mismatch
without changing the API contract.

Targeted ESLint and Prettier checks pass, and Playwright discovers all four
Frontier browser tests. The full 12-test suite passed before this fixture-only
change; the updated Frontier browser test has not yet been executed. The latest
pressure reading at `2026-10-27T18:32:26Z` was `some avg10=44.47%` and `full
avg10=40.44%`, so browser revalidation remains pending.

| Component | Current status | Boundary |
| --- | --- | --- |
| Capital carry browser request identity | IMPLEMENTED, BROWSER REVALIDATION PENDING | Fixture now sends schema-valid SHA-256 candidate identity; current test discovery/static checks pass, browser execution after the correction is pending. |
| Project Frontier overall | PARTIALLY VERIFIED | Remains isolated and undeployed; broader Python suite, live cross-venue validation, source permission review, and production readiness remain incomplete. |

File changed: `apps/web/e2e/frontier.spec.ts` in commit `9a4ccf4`.

### Bounded JSON parser failure classification — 2026-10-27 18:37 UTC

Code commit `ac5daaf` catches `RecursionError` and integer-token `ValueError`
from the bounded public JSON decoder. The transport returns
`JSON_COMPLEXITY_LIMIT`, retains the complete response within the configured
byte bound as failed-capture evidence, and does not retry the input. The API
diagnostic path stores the raw body and marks the transport-response failure;
subsequent valid source data still recovers source health.

Focused transport and API verification passed **3 tests** in 2.16 seconds with
86,772 KiB peak RSS and zero swaps. Ruff and formatting checks passed; strict
mypy for the transport module passed. A 1,100-level fixture did not exceed
CPython's parser limit, so the tested nesting fixture uses 20,000 levels
(40,001 bytes, below the 65,536-byte test response limit); a 5,000-digit integer
tests the numeric parser limit. The first assertion run exposed this fixture
threshold; the adjusted fixtures pass.

At `2026-10-27T18:37:02Z`, host memory PSI remained `some avg10=41.88%` and
`full avg10=37.24%`. The carry E2E fixture has its API-valid candidate ID but
has not yet been browser-executed after that correction. Broader repository
Python verification remains partial due the absent baseline Reality recovery
module and pressure-sensitive host gate. No exchange request, protected
service, or production store was used.

| Component | Current status | Boundary |
| --- | --- | --- |
| Public JSON parser complexity handling | COMPLETE AND VERIFIED | Deep nesting and oversized integer tokens become non-retryable classified adapter failures with bounded raw evidence; API diagnostic persistence and subsequent source recovery pass. |
| Carry browser E2E after schema-valid ID change | IMPLEMENTED, BROWSER REVALIDATION PENDING | Static checks and test discovery pass; browser execution of the latest fixture remains pending under elevated PSI. |
| Project Frontier overall | PARTIALLY VERIFIED | Isolated and undeployed; live semantic/economic cross-venue validation, source permissions, broader regression, and production prerequisites remain incomplete. |

Files changed: `packages/midas/frontier/adapters/transport.py`,
`tests/frontier/test_adapters.py`, and `tests/frontier/test_api.py` in commit
`ac5daaf`; this report and `FRONTIER_MISSION_LEDGER.md` record the checkpoint.

### Pre-decode JSON nesting bound — 2026-10-27 18:39 UTC

The prior decoder exception handling did not bound nesting at a predictable
depth: CPython accepted deeply nested arrays beyond the original fixture's
1,100 levels, while recursive normalization after parsing could still exceed
downstream limits. The public transport now scans the bounded UTF-8 response
before decoding and rejects more than 64 nested JSON containers as
`JSON_COMPLEXITY_LIMIT`. The scanner tracks string and escape state, so
brackets inside JSON text do not count toward nesting. The parser's existing
`RecursionError` and numeric-token `ValueError` handling remains as a fallback.

Verification passed: the three focused adapter cases cover deep nesting,
oversized integer tokens, and 100 bracket levels inside an escaped JSON string;
the API diagnostic persistence/recovery test passed separately. Ruff,
formatting, strict mypy for the transport, and `git diff --check` pass. The API
test emitted the existing Starlette/httpx deprecation warning. Current live
source validation, broader regression, and production readiness are unrelated
and remain outstanding; Frontier is still isolated and undeployed.

| Component | Current status | Boundary |
| --- | --- | --- |
| Public JSON parser nesting bound | COMPLETE AND VERIFIED | More than 64 containers fail before object construction; string content is ignored; raw diagnostic evidence and API recovery pass. |
| Carry browser E2E after candidate ID fixture change | IMPLEMENTED, BROWSER REVALIDATION PENDING | The separate carry fixture still needs a browser run after its schema correction. |
| Project Frontier overall | PARTIALLY VERIFIED | Cross-venue live semantic/economic validation, broad regression, and production prerequisites remain incomplete. |

Files changed: `packages/midas/frontier/adapters/transport.py`,
`tests/frontier/test_adapters.py`, and the Frontier architecture and operations
documentation. This report records the continuing hardening after commit
`ac5daaf`.

### Frontier browser revalidation — 2026-10-27 18:40 UTC

After the capital-carry browser fixture was corrected to use a schema-valid
candidate hash in commit `9a4ccf4`, the complete Frontier browser spec passed
**4 of 4 tests** in 10.5 seconds with one worker. It used the Playwright
configuration's temporary demo database, local API/UI servers, and bounded
Frontier root; the Kalshi arithmetic test explicitly remained fixture-only.
The UI suite did not probe an exchange or launch research work.

The same checkpoint re-ran the focused transport cases (**3 passed**) and the
API failure-diagnostic persistence/recovery case (**1 passed**), plus Ruff,
format, strict transport mypy, and whitespace checks. The API test emitted the
existing Starlette/httpx deprecation warning. At 18:40:37 UTC, PSI 10-second
averages were 0.00% for both some and full, five-minute averages were 19.56%
and 17.60%, available memory was 9.12 GiB, and swap free was 471 MiB.

| Component | Current status | Boundary |
| --- | --- | --- |
| Frontier browser spec after candidate identity correction | COMPLETE AND VERIFIED | Four isolated local-demo browser tests pass; this does not establish production deployment or live exchange behavior. |
| Public JSON parser nesting bound | COMPLETE AND VERIFIED | Focused parser and API diagnostic tests pass with pre-decode 64-level bound and escaped-string coverage. |
| Project Frontier overall | PARTIALLY VERIFIED | Broader repository regression, live economic validation, and production readiness remain incomplete. |

Files changed in the browser fixture correction: `apps/web/e2e/frontier.spec.ts`
in commit `9a4ccf4`. No browser test files changed in this revalidation.

### Frontier web unit regression — 2026-10-27 18:43 UTC

The full web unit suite passed with `corepack pnpm test`: **40 tests across
7 files** in 5.00 seconds, including all eight Frontier component tests. The
Frontier browser spec also remains green at four of four tests from the
18:40 UTC checkpoint. No frontend source changed during this verification.

The production build was not started. At 18:43:32 UTC, host memory PSI had
risen to 36.01% some / 28.91% full over 10 seconds and 20.59% / 18.43% over
five minutes; available memory was 8.81 GiB but swap free was 473 MiB. The
recent build's measured peak is approximately 676 MiB, so defer it until a
fresh admission sample shows the host has recovered. The prior build result
predates the latest stored-row-hash and carry UI changes.

| Component | Current status | Boundary |
| --- | --- | --- |
| Frontier/full web unit suite | COMPLETE AND VERIFIED | 40 tests in seven files pass on the current branch. |
| Latest production frontend build | COMPLETE AND VERIFIED | `npm run build` passes on the v13 code and current Workbench; Vite transforms 2,228 modules and emits Frontier at 102.13 kB JS / 35.87 kB CSS. Existing Chart chunk is 544.41 kB and triggers Vite's >500 kB advisory. |
| Project Frontier overall | PARTIALLY VERIFIED | Live economic validation, source permissions, broad repository regression, and production readiness remain incomplete. |

No exchange request, protected service, or production store was accessed.

### Collision-free settlement asset keys — 2026-10-27 18:49 UTC

The prior separator-joined token identity could collide when colons appeared
inside both the network and asset-reference fields. For example, two distinct
valid tuples—net:alpha / asset:beta and net:alpha:asset / beta—produced the
same canonical string. `SettlementAssetIdentity.canonical_id` now emits a
versioned, compact JSON tuple prefixed `settlement-asset-v2`; the identity
model accepts only its implemented schema version 1. Same-payoff verifier v4
and logical-implication verifier v2 pin the new key encoding into relationship
identities. Existing persisted relationship evidence is not rewritten.

Four focused synthetic tests pass (**4 passed**): the delimiter-collision
pair produces distinct keys and same-payoff relationship IDs, unsupported
identity schema versions reject, same-ticker cross-network behavior remains
rejected, and logical implication still reports both settlement units.
Ruff, formatting, and `git diff --check` pass. Strict mypy and the complete
Frontier suite have not been rerun after this change; host PSI at 18:49:39 UTC
was 46.81% some / 42.40% full over 10 seconds and 31.84% / 28.83% over five
minutes. Available memory was 9.22 GiB and swap free was 473 MiB. No source
API or protected service was accessed.

| Component | Current status | Boundary |
| --- | --- | --- |
| Backend settlement identity key and verifier versions | PARTIALLY VERIFIED | Collision behavior and focused relationship tests pass; full Frontier regression and strict mypy remain pending. |
| UI identity comparison and balance key | IMPLEMENTED, VERIFICATION PENDING | The UI compares identity fields directly, rejects unsupported/malformed values, and uses a structured balance key; focused frontend tests remain pending. |
| Project Frontier overall | PARTIALLY VERIFIED | Live cross-venue economics, source permission review, production build, and deployment remain incomplete. |

### UI settlement identity comparison hardening — 2026-10-27 18:51 UTC

Code commit `547a37b` hardens Mission Control's virtual-funding comparison.
It validates that an identity has the exact supported v1 field set, compares
schema version, kind, code, network, and asset reference field by field, and
keys stored virtual balances with a JSON tuple of venue plus those identity
fields. Non-fiat display labels percent-encode colons and percent signs. The
component regression covers the distinct delimiter-colliding identity pair,
distinct virtual balances, mismatched capital/leg identities, and unsupported
schema version.

Prettier and `git diff --check` pass. The focused frontend test and production
build have not run after this UI patch. At 18:51:18 UTC, PSI was 42.89% some /
38.45% full over 10 seconds and 35.52% / 32.03% over five minutes; available
memory was 9.22 GiB and swap free was 473 MiB. The frontend test is part of the
Frontier component suite; rerun it and the full Frontier suite when admission
pressure eases. No exchange or protected service was accessed.

| Component | Current status | Boundary |
| --- | --- | --- |
| UI settlement identity gate | IMPLEMENTED, TESTING PENDING | Structured identity comparisons and keys are implemented; the new regression has not executed yet. |
| Collision-free canonical asset key | PARTIALLY VERIFIED | Four focused Python tests pass; complete Frontier suite and strict mypy after the change remain pending. |
| Project Frontier overall | PARTIALLY VERIFIED | Production build, live cross-venue economic verification, source permission review, and deployment remain incomplete. |

Changed files: `apps/web/src/Frontier.tsx` and `apps/web/src/Frontier.test.tsx`,
commit `547a37b`.

### Frontier Python regression and resource measurement — 2026-10-27 18:41 UTC

The complete Frontier Python suite passed: **215 tests in 39.29 seconds**.
The suite included the parser-depth tests, API diagnostic persistence and
recovery, adapters, relationship graph, opportunity economics, persistence,
replay, and API behavior. `/usr/bin/time -v` measured **335,120 KiB peak RSS**
and **zero swaps**. The only reported warning was the existing
Starlette/httpx TestClient deprecation notice. At 18:41:46 UTC, host PSI
10-second averages were 0.00% for both some and full, five-minute averages
were 15.37% and 13.84%, available memory was 9.46 GiB, and swap free was
471 MiB.

This is a full Frontier suite result, not a repository-wide MIDAS regression.
Repository-wide collection previously found the missing baseline
`midas.reality.recovery` dependency; the branch's full Frontier suite remains
independently green. No production services or live source APIs were accessed.

| Component | Current status | Boundary |
| --- | --- | --- |
| Frontier Python suite | COMPLETE AND VERIFIED | 215 Frontier tests pass; repository-wide collection and the absent baseline Reality recovery module remain separate issues. |
| Frontier browser spec | COMPLETE AND VERIFIED | Four local-demo browser tests pass; live exchange validation is not implied. |
| Project Frontier overall | PARTIALLY VERIFIED | Broader repository regression, live economic validation, and production readiness remain incomplete. |

### Test-source boundary and current web verification — 2026-10-27 19:02 UTC

Commit `5e51a88` replaces the 15 direct test reads from the held
`data/frontier/live-probes` directory with synthetic inline adapter/API inputs,
and adds a static test-source guard. The guard passed **1 test**; the modified
adapter/API selection passed **24 tests in 4.17 seconds** at **94,724 KiB peak
RSS**; and the complete Frontier Python suite passed **218 tests in 39.36
seconds** at **333,988 KiB peak RSS**, with zero swaps in all three runs. The
existing Starlette/httpx TestClient deprecation warning remains. A source-text
scan across `tests`, `packages`, and `apps` found no remaining `live-probes`
path. The earlier 18:41 suite did read held capture files via the former test
references; no test writes or capture mutation are known. Current fixture tests
demonstrate implementation behavior only, not live-source validation or
permission.

The UI's exact settlement-identity funding check validates the supported
structure and ASCII asset references consistent with the backend model,
compares identity fields directly, and uses a structured venue/identity key.
This UI change and its regression are committed in `3e7d1b9`.
The non-ASCII rejection case is covered. The Frontier component suite passed
**8/8**, the full web suite **40/40**, web typecheck, targeted ESLint and
Prettier passed, and the Frontier Playwright suite passed **4/4** using its
temporary local API, database, Arena/Frontier roots, and no exchange probes.
The Playwright process peaked at **191,496 KiB RSS** with no swaps. The
post-change production build passed at **714,944 KiB peak RSS**, no swaps, in
12.46 seconds. Vite retains the known large index/chart chunk-size warning.
No production deployment or protected service action occurred. Source
permission, genuine cross-venue economic verification, repository-wide
regression, and deployment remain open.

### Held-source test guard closure — 2026-10-27 19:11 UTC

Commit `5e51a88` replaces held-capture test reads with synthetic inputs;
`2aef789` adds the first runtime guard; and `df30fa7` closes its direct,
symlink, symlink/`..`, and `dir_fd` cases. `test_held_capture_source_boundary.py` passes **2/2**; the
converted adapter/API selection passes **24**; the full Frontier Python suite
passes **219** in **39.83 seconds** with **335,396 KiB peak RSS** and zero
swaps. Ruff and format checks pass for the guard. The existing
Starlette/httpx TestClient deprecation is the only Python-suite warning. A
read-only peer review found no ordinary test interference. Source-text scans
show no `live-probes` path in `tests`, `packages`, or `apps`; preserved source
files were not changed or opened during this remediation. The older 18:41
suite did read held capture files through the references present at that time;
no mutation is known. Source permission, genuine multi-venue economics,
repository-wide regression and production deployment remain unresolved.

## Permission-reference policy regression — 2026-10-27

A read-only configuration audit found that an arbitrary nonblank permission
reference cleared the historical-source quarantine even though the reference
was not validated and live probing remained disabled. This contradicted the
documented source-use boundary. The configuration now fails closed for Kalshi
and Kraken regardless of the probe flag or reference value; API quarantine and
readiness remain active, and the readiness detail states that no validated
permission loader exists. Synthetic API coverage now supplies arbitrary
references while asserting both probe rejection and quarantine of stored
fixture evidence. Documentation was corrected in the source review, operations
guide, and current-state file. Implementation is committed as `52b6a9e`; the
status update is committed as `205dbff`. The permission module passes **4/4**;
the full Frontier suite passes **219/219** in 39.47 seconds at **335,216 KiB
peak RSS**, with zero swaps. Ruff and format checks pass, and strict mypy passes
for the canonical models and relationship modules. The existing
Starlette/httpx TestClient deprecation is the only test warning. The focused
permission module was rerun after the formatter adjustment to the assertion;
the full suite preceded that whitespace-only change. All
test data were synthetic, the held-source runtime guard was active, and no
held capture, source request, protected service, or production state was
accessed. These results verify software quarantine behavior only; they do not
establish permission, live source quality, or economic opportunity.

## Official Kalshi multiplier-column clarification — 2026-10-27 19:28 UTC

The [official July 7, 2026 fee schedule](https://kalshi.com/docs/kalshi-fee-schedule.pdf)
labels the non-standard fee-table columns Maker Multiplier then Taker
Multiplier. Its `KXMVE` row's `2 1` is therefore maker 2 / taker 1. The
[Get Series API schema](https://docs.kalshi.com/api-reference/market/get-series)
exposes the series `fee_type` and `fee_multiplier`, while the [event fee-change
schema](https://docs.kalshi.com/api-reference/events/get-event-fee-changes)
describes overrides on the parent series. This clarifies the public schedule's
column ordering only: it does not establish that the `KXMVE` row applies to
the differently named `KXMVECROSSCATEGORY` series in held evidence. Account
precision and maker/mixed-order applicability remain unresolved. The existing
fixture test covers the taker sensitivity path for
`quadratic_with_combo_maker_fees` at multiplier 1; this is implementation
coverage, not confirmation of a live fee schedule. No code or tests changed,
and no API request, held-capture read, or production action occurred.

At `2026-10-27T19:28:52Z`, memory PSI `avg10` was 46.02% (`some`) / 39.98%
(`full`), `avg60` 35.04% / 31.47%, and `avg300` 22.52% / 20.34%; available
memory was 9.3 GiB and swap free was 468 MiB of 4 GiB. After `avg10` eased, the
focused existing regression
`test_supported_quadratic_maker_variants_keep_taker_formula` passed **2/2**
in 0.30 seconds at **54,520 KiB peak RSS**, with zero swaps. It uses synthetic
metadata and verifies only the local taker sensitivity for the two fee types;
it does not establish live applicability. At `2026-10-27T19:31:50Z`, memory PSI
`avg10` was 0.05% (`some`) / 0.04% (`full`), `avg60` 15.01% / 13.35%, and
`avg300` 24.38% / 21.90%; available memory was 9.4 GiB and swap free was 468
MiB of 4 GiB. `git diff --check` passed. Frontier remains PARTIALLY VERIFIED;
permission, live cross-venue economics, broad repository regression, and
deployment remain open.

### Kalshi price-range constraints — 2026-10-27 19:44 UTC

The [official Kalshi Get Market schema](https://docs.kalshi.com/api-reference/market/get-market)
exposes `price_ranges` entries with `start`, `end`, and `step`. Frontier
schema v4 retains these as bounded exact-decimal `MarketInstrument` constraints;
Kalshi adapter v17 validates at most 32 ranges while preserving the native
response, and the model distinguishes missing range metadata from an explicit
empty list. The shared model limits decimal precision to 18 places, rejecting
extreme scientific-notation exponents before rational arithmetic. Candidate
generation and independent audit each reject empty, out-of-range, off-step,
and boundary quotes when ranges are reported. The implementation uses `start`
as the step-grid anchor, inferred from the schema shape. Endpoint inclusivity
is unspecified and boundary quotes therefore fail closed. This is fixture
verification, not live source validation.

The focused Python selection passed **17 tests, 126 deselected** in 1.17 seconds
at **78,936 KiB peak RSS**, with zero swaps and one existing
Starlette/httpx deprecation warning. It covered adapter parsing/malformed
metadata, candidate and independent-audit quote checks, deterministic replay,
and replay API output. Adversarial fixtures reject an extreme `1e-999999999`
step, non-array or oversized lists, out-of-domain and overlapping ranges,
missing fields, numeric rather than string values, and overlong decimals.
The full Frontier component file passed **8/8** in 3.31 seconds, including the
new constraint display. TypeScript typecheck, targeted ESLint and Prettier,
Ruff, strict mypy on the five changed production modules, and `git diff --check`
passed. At `2026-10-27T19:46:50Z`, host memory PSI `avg10` was 41.09% `some` /
36.23% `full`, with 9.2 GiB available memory and 468 MiB swap free. The broad
Frontier suite and production build remain deferred. No source request, held
data read, protected service action, or deployment occurred.
Code commit `47f399d` implements the typed range model and enforcement;
`52abaad` adds the adversarial parser cases and updates the checkpoint evidence.
The complete adapter test module passed **60 tests** in 2.65 seconds at
**60,504 KiB peak RSS**, with zero swaps. At `2026-10-27T19:45:58Z`, host memory
PSI `avg10` was 47.18% `some` / 41.86% `full`; 9.3 GiB was available and 468
MiB swap was free. At `2026-10-27T19:46:50Z`, the full Frontier UI component
test file passed **8/8** in 3.31 seconds. The broader Frontier suite and
production build remain deferred.
Next safe work is an offline review of incomplete cross-venue capital and
settlement costs. The full Frontier Python, web, and isolated browser suites
have now run; keep FX and transfer costs unknown absent evidence, and retain the
source-use and deployment holds.

### Consolidated Frontier regression and build — 2026-10-27 19:50 UTC

After memory PSI eased, the complete Frontier Python suite passed **230/230**
in 39.45 seconds (40.56 seconds wall) at **335,348 KiB peak RSS**, with zero
swaps and one existing Starlette/httpx deprecation warning. The full web unit
suite passed **40/40 across seven files** (4.85 seconds reported by Vitest,
5.36 seconds wall) at **298,344 KiB peak RSS**, with zero swaps. The complete
Frontier browser spec passed **4/4** with one worker in 9.7 seconds (10.29
seconds wall) at **190,708 KiB peak RSS**, with zero swaps. Playwright used its
temporary SQLite, Arena, and Frontier roots plus a temporary output directory;
the four cases verify the no-probe view, no-launch Arena history, fixture-only
Kalshi settlement review, and bounded mobile graph. The test servers stopped at
completion.

`npm run build -- --outDir /tmp/midas-frontier-web-build-20261027-1949` passed
TypeScript and Vite production compilation (2,228 modules; 4.69 seconds Vite,
12.21 seconds wall) at **706,308 KiB peak RSS**, with zero swaps. The unique
temporary output directory kept the repository's existing `dist` untouched.
Vite emitted its existing warning for the >500 kB main and Chart chunks, plus
the expected warning that an external `outDir` is not emptied automatically.
`npm run typecheck -- --pretty false`, targeted ESLint and Prettier, Ruff,
strict mypy on five changed production modules, and `git diff --check` passed.

At `2026-10-27T19:50:15Z`, memory PSI `avg10` was 0.00% (`some`) / 0.00%
(`full`), `avg60` 2.36% / 2.11%, and `avg300` 22.62% / 20.32%; 9.1 GiB was
available and 468 MiB of 4 GiB swap was free. No external source probes, held
capture reads, Reality actions, or deployments occurred. The repository-wide
legacy test suite remains unrun. Frontier is still PARTIALLY VERIFIED because
source-use permission, live cross-venue equivalence/economics, and broader
funding/settlement costs remain unresolved.

### Virtual post-settlement release delay — 2026-10-27 20:02 UTC

Code commit `29ab175` extends the saved-run-bound virtual capital-duration
sensitivity with an optional whole-second release delay per venue, bounded to
31,536,000 seconds. Omitted values mean zero; a supplied map must cover all
candidate venues. This user-entered scenario is not a source-reported promise
of redemption, withdrawal, or capital availability. The delay is included in
the canonical input digest. The independent Fraction-based audit recomputes
release time, elapsed duration, carry, and adjusted P&L. Settlement instants
are converted to UTC before adding elapsed seconds, including across
daylight-saving transitions; out-of-range timestamps fail closed. The API and
Mission Control expose this assumption without adding source requests, account
paths, or saved artifacts.

Tests cover positive-delay arithmetic, zero defaults, incomplete and malformed
inputs, audit tampering, generated Fraction differentials, a daylight-saving
transition, and datetime overflow. The capital-carry module passed **27/27**
(and was rerun **27/27** after Ruff formatting). The saved-run API integration
passed **1 test** (43 deselected). The complete Frontier Python suite passed
**246/246** in 39.38 seconds (40.49 seconds wall) at **336,116 KiB peak RSS**,
zero swaps; its only warning was the existing Starlette/httpx TestClient
deprecation. The complete web suite passed **40/40 across seven files** in
5.25 seconds wall at **259,924 KiB peak RSS**, zero swaps. The isolated Frontier
Playwright suite passed **4/4** in 10.2 seconds (10.81 seconds wall) at
**190,776 KiB peak RSS**, zero swaps. It used temporary local API/database/
Arena/Frontier roots and made no exchange requests.

TypeScript production compilation passed. Targeted ESLint and Prettier, Ruff
check/format, strict mypy for `capital.py` and the Frontier API, and
`git diff --check` passed. The production build at
`/tmp/midas-frontier-web-build-20261027-2001` transformed 2,228 modules; Vite
took 4.65 seconds and the full build took 12.28 seconds wall at **700,060 KiB
peak RSS**, with zero swaps. The repository `dist` was not modified. Existing
warnings remain for the >500 kB index/Chart chunks and an external output
directory. At `2026-10-27T20:02:00Z`, memory PSI avg10 was 0.00% (`some`/`full`),
avg60 1.19% / 1.09%, avg300 14.11% / 12.77%; 9.5 GiB was available and 468
MiB swap free. No live source, held capture, Reality service, or production
deployment was accessed. The repository-wide legacy suite remains unrun.
This capital scenario is **COMPLETE AND VERIFIED** in fixture/local testing;
Frontier overall remains **PARTIALLY VERIFIED** due source permission, live
cross-venue economic evidence, broader cost assumptions, legacy regression,
and deployment prerequisites.

### Frontier Arena replay integration verification — 2026-10-27 20:04 UTC

The focused `tests/arena/test_frontier_replay.py` suite passed **10/10** in
1.94 seconds (2.63 seconds wall) at **193,936 KiB peak RSS**, zero swaps. The
test module exercises immutable pinned replay snapshots, bounded Arena job
contracts, artifact integrity and recovery, bounded catalog filtering, API
result linkage, and held-source read quarantine. It uses temporary fixture
roots and does not submit or launch a production Arena job. The existing
Starlette/httpx TestClient deprecation is the only warning. At
`2026-10-27T20:04:45Z`, host memory PSI avg10 was 0.22% (`some`) / 0.20%
(`full`), avg60 15.34% / 13.80%, avg300 18.05% / 16.31%; 9.6 GiB was available
and 468 MiB swap free. No exchange request, held capture, Reality action, or
deployment occurred. This improves local Arena integration coverage; broader
legacy regressions and production readiness remain incomplete.

### Legacy API integration compatibility — 2026-10-27 20:05 UTC

The isolated `tests/integration/test_api.py` module passed **5/5** in 3.99
seconds (5.01 seconds wall) at **154,664 KiB peak RSS**, with zero swaps. The
demo workflow forbids construction of the public client and uses temporary
databases/workspaces; the Arena qualification route is mocked. Coverage
includes health/readiness, Frontier empty/no-probe behavior, existing
Veritas/Reality configured-workspace routes, and persistence failure gates.
The only warning is the existing Starlette/httpx TestClient deprecation. At
`2026-10-27T20:05:24Z`, admission PSI avg10 was 0.00% (`some`/`full`), avg60
8.15% / 7.33%, avg300 15.84% / 14.31%; 9.6 GiB was available and 468 MiB swap
free. This is a bounded compatibility slice, not the full repository suite.
No public source, historical store, protected service state, or production
deployment was accessed. The full legacy suite and deployment remain
unverified.

### Legacy Polymarket and recording-path regression — 2026-10-27 20:06 UTC

Existing Polymarket adapter tests in `tests/integration/test_adapters.py`
passed **9/9** in 0.71 seconds (1.21 seconds wall) at **88,872 KiB peak RSS**,
zero swaps. The tests use repository fixture files and `httpx.MockTransport`;
no live request is enabled. `tests/integration/test_recording_isolation.py`
passed **4/4** in 0.49 seconds (0.93 seconds wall) at **77,800 KiB peak RSS**,
zero swaps. Its temporary-database writes stay under `tmp_path`; the production
default case asserts the legacy recording path without writing there. At
`2026-10-27T20:06:31Z`, host memory PSI avg10 was 0.00% (`some`/`full`), avg60
2.62% / 2.36%, avg300 12.54% / 11.33%; 9.6 GiB was available and 468 MiB swap
free. These regressions add confidence in existing Polymarket ingestion and
recording isolation, but do not constitute the repository-wide legacy suite.
No protected recorder, historical store, public source, or production
deployment was accessed.

### Frontier Laboratory compatibility smoke — 2026-10-27 20:09 UTC

The existing Laboratory API contract/reproduction test passed **1 test** (two
module tests deselected) in 2.50 seconds (3.15 seconds wall), at **124,540 KiB
peak RSS**, zero swaps. It creates and reproduces four virtual demo cases. The
run set `MIDAS_MODE=demo` and directed Frontier/Arena roots to fresh `/tmp`
paths; database, Laboratory, and recording artifacts used `tmp_path`. The
existing Starlette/httpx TestClient deprecation is the only warning. At
`2026-10-27T20:09:29Z`, host PSI avg10 was 0.12% (`some`) / 0.11% (`full`),
avg60 12.97% / 11.97%, avg300 15.92% / 14.55%; 9.6 GiB was available and
468 MiB swap free. No exchange source, production Arena job, protected service,
or historical store was accessed. This is one bounded compatibility case,
not the full Laboratory or repository regression suite.

### Per-venue quote-decay replay sensitivity — 2026-10-27 20:16 UTC

Code commit `9da08fd` extends `ExecutionScenario` with a shared base execution
delay plus optional additional delay by supported venue. Per-venue additions
are strict whole milliseconds, each combined venue delay is capped at one
hour, and at most the three currently supported venue keys are accepted. The
binary cross-venue and same-market multi-outcome calculators apply the venue's
effective delay when evaluating user-supplied quote decay. The independent
audit recomputes each leg's modeled price from its market venue. Replay version
11, economic model version 11, and audit version 8 identify the behavior;
scenario serialization is included in candidate and replay input hashes.

The Mission Control workbench exposes an additional-delay input for each
configured source and sends the mapping to direct replay, paired replay, and
Arena replay. Its size control is now labeled as a usable top-ask depth cap.
This corrects the former UI wording: scaling the displayed depth is a size
haircut, not a partial-fill model. Venue delay additions only scale a virtual
quote-decay assumption; they do not establish actual venue latency, action
ordering, simultaneous or sequential execution, fills, or recoveries. The
existing independent full-or-no-fill exposure stress remains distinct.

Verification used fixture and temporary local data only. The focused Python
selection passed **8 tests** (80 deselected) in 1.32 seconds pytest time / 1.77
seconds wall at **86,172 KiB peak RSS**, zero swaps and zero socket messages.
It covers asymmetric per-venue pricing, tampered-price disagreement, invalid
venue/delay inputs, scenario hash pinning, and API persistence/readback. The
isolated API replay test also passed **1/1** after its final assertion update
in 0.94 seconds pytest time / 1.38 seconds wall at **77,348 KiB peak RSS**,
zero swaps, and the existing Starlette/httpx deprecation warning. The focused
workbench test passed **1/1** (seven other cases deselected); TypeScript,
targeted ESLint/Prettier, Ruff check/format, strict mypy for the four core
Frontier model/economics/replay modules with imported diagnostics suppressed,
and `git diff --check` passed.

An unrestricted mypy invocation that included the API reported existing
imported errors in `packages/midas/veritas/independent_economics.py` at lines
46, 296, and 407. A filtered API-inclusive run was interrupted after 15 seconds
without output under host pressure, so API-inclusive strict typing remains
unverified. At `2026-10-27T20:16:17Z`, memory PSI avg10 was 44.92% (`some`) /
40.76% (`full`); 9.5 GiB was available and 469 MiB swap was free. The full
Frontier regression and a production build were not rerun after this revision;
the earlier build does not verify the changed UI. No source request, held
capture read, protected service action, or deployment occurred. This change is
**PARTIALLY VERIFIED**; Frontier remains **PARTIALLY VERIFIED** overall.

### Fee evidence at modeled venue execution time — 2026-10-27 20:22 UTC

Code commit `ad811a4` makes the bounded delay scenario consistent across quote
decay and fee applicability. For each leg, the effective modeled time is the
replay analysis time plus the shared delay and that venue's addition. Fee
effective/expiry bounds and the freshness age for a provenance-bound Kalshi
estimate are checked at this projected time. A schedule that expires before
the modeled use time yields an unknown fee, so net P&L remains unknown and the
candidate stays conditional. The independent audit derives the projected time
separately from the replay timestamp, scenario, and pinned market venue. It
does not infer future fee changes or hold a schedule valid beyond its pinned
evidence window. Economic model v12, audit v9, and replay v12 pin the rule.

The bounded fee-expiry regression passed with the per-venue delay selection:
**6 passed, 39 deselected** in 0.47 seconds pytest time / 0.81 seconds wall at
**60,588 KiB peak RSS**, zero swaps and zero socket messages. The offline API
replay test passed **1/1** (43 deselected) in 0.93 seconds pytest time / 1.36
seconds wall at **77,392 KiB peak RSS**, zero swaps, with the existing
Starlette/httpx deprecation. After this code change, the full Frontier suite
passed **252/252** in 39.63 seconds pytest time / 40.73 seconds wall at
**336,712 KiB peak RSS**, zero swaps and zero socket messages; the same
deprecation warning was the only warning. Ruff check/format, strict mypy on
the four core Frontier modules with imported diagnostics suppressed, and
`git diff --check` passed.

At `2026-10-27T20:22:35Z`, immediately after the full suite, memory PSI avg10
was 25.66% (`some`) / 22.83% (`full`), with 9.5 GiB available and 469 MiB swap
free. The production frontend build remains pending after the prior UI change;
the UI's focused component test, typecheck, ESLint, and Prettier checks had
passed at the 20:16 checkpoint. API-inclusive strict mypy remains unverified
for the reasons recorded above. No live source, held capture, protected
service, or production state was accessed. This fee-horizon correction is
**COMPLETE AND VERIFIED** in controlled tests; Frontier remains
**PARTIALLY VERIFIED** overall.

## Bounded partial-fill sensitivity — 2026-10-27 20:37 UTC

Economic model v13 adds a five-point partial-fill grid to supported candidate
families. Each leg samples 0%, 25%, 50%, 75%, and 100% of its modeled order
quantity, with intermediate points omitted when they violate that contract's
quantity step. For each terminal state the evaluator independently chooses
each leg's adverse fraction, so it computes the grid minimum in
`O(states × legs × grid points)` rather than materializing up to `5^16`
combinations. Fee calculations run again at each nonzero modeled quantity and
the same projected venue execution time; after-fee sensitivity remains unknown
if any applicable fee is unresolved. The independent audit v10 reconstructs
the grid and fee outputs from pinned markets, books, scenario, and fee evidence.
Replay v13 pins the new candidate output.

The result is exact only for these quantity-step-feasible grid points. It
models one aggregate fill per leg at the modeled best-ask price. It does not
estimate fill probabilities, continuous values between points, multiple-fill
rounding, queue position, quote paths, deeper-book execution, hedging, or
unwinding. The Workbench reports both worst sampled gross/net results and the
selected quantity for each leg; an expandable view lists every feasible grid
point per leg.

Verification: `tests/frontier` passed **254/254** in 39.82 seconds pytest time /
40.92 seconds wall at **335,988 KiB peak RSS**. One existing Starlette/httpx
TestClient deprecation remains. Focused fixtures compare the three-leg grid by
enumerating all 125 fraction combinations, verify fee rounding where a quarter
size fee differs from one quarter of the full-size fee, filter a step-1
contract grid to 0%, 50%, and 100%, reject unknown after-fee values, and detect
tampered partial results independently. The 16-leg full/no-fill bound remains
65,536 patterns; the partial grid does not expand its Cartesian product.
The Workbench component tests passed **8/8**, TypeScript, targeted ESLint and
Prettier passed, Ruff and strict mypy for the four core Frontier modules
passed. The overall package browser suite and production frontend build remain
pending until host pressure permits. At `2026-10-27T20:37:47Z`, PSI avg10 was
34.40% (`some`) / 30.73% (`full`), with 9.9 GiB available and 481,040 KiB swap
free. No live data or protected service was touched. This is an isolated local
implementation; Frontier remains undeployed and **PARTIALLY VERIFIED**.

The v13 implementation described here was committed as **`e50ba34`** on
`codex/frontier-20261026`. That commit changed `packages/midas/frontier/economics.py`,
`packages/midas/frontier/independent_audit.py`, `packages/midas/frontier/models.py`,
`packages/midas/frontier/replay.py`, `tests/frontier/test_relationships_economics_replay.py`,
`tests/frontier/test_api.py`, `apps/web/src/Frontier.tsx`,
`apps/web/src/Frontier.test.tsx`, `docs/frontier/FRONTIER_ARCHITECTURE.md`, and
this report. The separately maintained mission ledger and current-state file
record the post-commit handoff.

### Frontier frontend and browser verification — 2026-10-27 20:43 UTC

The full Web unit suite passed **40/40** tests across seven files in 5.25
seconds wall at **322,452 KiB peak RSS**. TypeScript, targeted ESLint, and
Prettier passed. The production build passed `tsc -b` and Vite in 12.50 seconds
wall at **692,056 KiB peak RSS**; Vite transformed 2,228 modules. Frontier's
emitted chunk is 102.13 kB JavaScript / 35.87 kB CSS. Vite retains a chunk-size
advisory for the existing 544.41 kB Chart chunk (threshold 500 kB); the build
exits successfully.

The dedicated Frontier browser spec passed **4/4** in 11.12 seconds wall at
**192,508 KiB peak RSS**, using the temporary demo API/database/Arena/Frontier
roots and a read-only Veritas workspace at this isolated worktree. No source
probes were sent. The full 12-test browser suite completed **10/12** in 57.66
seconds wall at **193,596 KiB peak RSS**: every non-Laboratory case passed,
including all four Frontier cases. Both Laboratory launch cases correctly
received `resource_admission_lock_busy` and could not observe the expected
completed fixture campaign.

Read-only inspection found the guard is deliberately host-wide: `global_lock_path`
uses `/home/charlie/midas/data/arena/.global-admission.lock` even when the test
API uses temporary Arena and database roots. Its active `flock` owner at
`2026-10-27T20:43:15Z` was PID **3681242**, running
`scripts/veritas_gap_detail_v2_batch.py` against the primary and Veritas Arena
roots. This worker was already running before the E2E suite; it and its lock
were left untouched. The two refused POSTs started no Laboratory worker. Do
not bypass or retry these tests until that global admission slot is released.

Verification status update: Python Frontier **254/254**, Web unit **40/40**,
Workbench **8/8**, build, and Frontier E2E **4/4** are verified. The complete
browser suite remains **PARTIALLY VERIFIED** because the global resource guard
prevented two temporary Laboratory launches. Cross-venue live relationship
validation, source permissions, and production deployment gates remain
unresolved. No production or exchange service was contacted.

### Official source terms refresh — 2026-10-27 20:45 UTC

The current Kalshi [Developer Agreement v1.1](https://kalshi-public-docs.s3.amazonaws.com/Kalshi-Developer-Agreement.pdf)
and [Data Terms of Use](https://kalshi-public-docs.s3.amazonaws.com/kalshi-data-terms-of-service.pdf)
were rechecked. They maintain the restrictive use boundaries summarized above;
the public GET interface examples do not establish a research/retention
exception. Keep the Kalshi source gate blocked.

Kraken's current [legal index](https://www.kraken.com/legal) directs users to
region-specific terms. Its [Global Terms](https://www.kraken.com/legal/global-terms)
are marked last updated 19 October 2026; the current [EEA Terms](https://www.kraken.com/legal/eea-terms)
explicitly include pricing data in “Our Content” and require approved purposes
or prior permission for other use. The [API Center](https://docs-legacy.kraken.com/api/docs/guides/global-intro/)
lists public Spot REST/WebSocket market-data interfaces but does not resolve
their application to this research workflow, retention, or the user's
applicable regional agreement. Preserve the hold pending exact-use review.

The [Polymarket Institute research guide](https://institute.polymarket.com/data),
dated 24 July 2026, continues to describe open APIs as research-accessible and
distinguishes the decentralized and US-only platforms as separately managed
data/API systems. It does not grant restricted-location access or establish
interchangeability between those systems.

This was a documentation-only review of official pages. It made no network
request to any exchange API, contacted no exchange, and read no held capture.
No source policy changed. The source-use readiness gate remains blocked for
Kalshi and Kraken, while Frontier remains **PARTIALLY VERIFIED** overall.

### Arena admission recheck — 2026-10-27 20:47 UTC

Before retrying the two Laboratory browser cases, a read-only host check found
that the earlier lock holder had exited but a new
`veritas_gap_detail_v2_batch.py` process (PID **3690476**) had acquired the
same global lock inode **6423106** at
`/home/charlie/midas/data/arena/.global-admission.lock`. Memory PSI at the
recheck was 38.74% (`some`) / 33.82% (`full`) avg10, 11.52% / 10.26% avg60,
and 20.77% / 18.43% avg300. The protected Reality recorder was present and
untouched. No Laboratory browser retry, lock bypass, worker launch, or service
action occurred. Keep the earlier full-browser result at 10/12 (two admission
denials) and the dedicated Frontier result at 4/4 until the shared slot
releases and a safe bounded rerun is possible.

### Coinbase Exchange Spot adapter — 2026-10-27 21:07 UTC

Commit `cfda4ad1beb00f301affe52752e8815b4862f8b5` adds a read-only Coinbase
Exchange spot adapter for an explicit one-to-twenty product allowlist. It
normalizes product metadata, exact increments/minimums, bounded aggregated L2
books, and one public trade page while preserving native response hashes,
timestamps, sequence and auction state. Coinbase maker-side trade fields are
not mislabeled as aggressor side. Spot payoffs, account-tier fees, settlement
rules, and event outcomes remain unsupported; spot prices are contextual and
cannot qualify as event-contract arbitrage.

The API requires the exact reviewed terms version `2026-08-07` and a separate
public-probe setting. `CoinbaseSpotConfig` itself refuses a null generic hold
without the exact version. This local acknowledgement does not independently
establish legal, regional, retention, or redistribution eligibility. The
adapter is fixture-validated only; no Coinbase request or live observation was
made.

The focused Coinbase adapter, API terms gate, held-source quarantine, and spot
payoff rejection selection passed **10/10** in 3.19 seconds (3.90 seconds wall,
**131,064 KiB peak RSS**, zero swaps). It emitted only the existing
Starlette/httpx TestClient deprecation warning. `ruff check`, `ruff format
--check`, Prettier, and `git diff --check` passed. The exact-version gate test
covers a missing acknowledgement, a stale version, whitespace variation, an
exact version with probe disabled, and explicit network enablement without
making a request. A direct adapter-config attempt to clear the hold without
acknowledgement is rejected.

At `2026-10-27T21:07:37Z`, a fresh host check found the external
`veritas_gap_detail_v2_batch.py` worker (PID **3706995**) holding the existing
global Arena lock inode **6423106**, with the process in `D` state. Memory PSI
was 30.67% (`some`) / 27.75% (`full`) avg10, 10.73% / 9.72% avg60, and 19.99%
/ 17.95% avg300; 9 GiB was available and 459 MiB swap was free. That worker and
lock were left untouched. The full Frontier suite, web suite, production build,
and browser regression have not been rerun for this commit. Frontier remains
partially verified, research-only, isolated, and undeployed.

### Python and web regression checkpoint — 2026-10-27 21:12 UTC

After the 21:07 focused Coinbase validation, the complete Frontier Python suite
passed **262/262** in 41.60 seconds (42.81 seconds wall, **353,748 KiB peak RSS**,
zero swaps). It includes the new adapter, exact terms-version checks, source
quarantine, and spot-payoff rejection. Only the existing
Starlette/httpx TestClient deprecation warning remains.

The complete web unit suite passed **40/40** in 14.86 seconds (15.56 seconds
wall, **271,600 KiB peak RSS**, zero swaps) with one worker. TypeScript
typecheck passed in 7.83 seconds at **439,648 KiB peak RSS**, zero swaps, and
targeted ESLint for the changed Frontier component/tests passed. Ruff check and
format, Prettier check, and `git diff --check` passed. The production frontend
build and browser E2E suite remain pending.

At `2026-10-27T21:12:52Z`, the external
`veritas_gap_detail_v2_batch.py` worker PID **3711078** held the shared Arena
lock inode **6423106** in `D` state. PSI avg10 was 35.46% (`some`) / 31.91%
(`full`), avg60 13.64% / 11.93%, avg300 15.10% / 13.55%; about 9 GiB was
available and 459 MiB swap was free. The worker and lock were left untouched;
no production service, exchange, or historical capture was accessed.

### Observation persistence timestamp — 2026-10-27 21:23 UTC

The Frontier observation writer now stamps missing typed
`Provenance.persisted_at_utc` values into a copied normalized model before
serialization and the atomic SQLite insert. The timestamp is the writer's
pre-insert UTC time; it is not a commit/fsync completion time or an estimate of
source clock uncertainty. Adapter models are not mutated. Previously stamped
capture models keep their original timestamp when copied to a content-addressed
snapshot, preserving the exact row hash. Retry comparison clears only the
typed persistence field, validates the stored row hash, and leaves the stored
timestamp untouched. Historical rows with the optional value absent remain
readable and can be retried idempotently.

The focused storage, Coinbase, and snapshot-copy selection passed **25/25** in
9.60 seconds (10.04 seconds wall), at **81,880 KiB peak RSS**, zero swaps. It
covers first-insert stamping, immutability of the caller's model, retry
stability, nested market/group provenance, legacy-row compatibility, and the
Coinbase missing source-time case. The complete Frontier suite passed
**265/265** in 42.04 seconds pytest time / 43.28 seconds wall, at **352,164 KiB
peak RSS**, zero test-process swaps. One initial full run caught a copied-row
hash mismatch; preserving an already stamped timestamp fixed it, and both the
focused snapshot regression and final full run pass. Ruff check/format and
`git diff --check` pass. The suite run began while no Arena lock was held, but
an external batch acquired the shared lock during the run; it completed without
swap and the batch was not touched. No source, production service, Reality
process, or historical store was accessed. Production build and browser E2E
remain pending another safe admission window.

### Monotonic request-duration provenance — 2026-10-27 21:28 UTC

Code commit `6bc0351` records bounded `request_elapsed_monotonic_ns` values in
the read-only HTTP transport, raw observations, typed provenance, complete HTTP
failure captures, and the evidence disclosure. The clock starts after source
rate pacing and stops after the complete body arrives, before JSON decoding.
Only elapsed duration is stored; monotonic clock origins are not compared across
venues or processes. Failures without complete response evidence leave the
field unknown. Storage compares typed raw models on duplicate inserts so older
raw rows that predate this optional property remain idempotent. The row
persistence hash and observation identity rules remain unchanged.

The focused adapters/storage/Coinbase/API selection passed **86/86** in 13.52
seconds pytest time / 14.00 seconds wall at **88,376 KiB peak RSS**, with zero
swaps. It covers success, complete-response failure, raw/provenance propagation,
snapshot hash preservation, and legacy rows missing both the monotonic duration
and persisted timestamp. The targeted Mission Control test passed **1/1**
(seven other cases in that file skipped by selection) in 1.78 seconds at
**208,356 KiB peak RSS**, zero swaps. Ruff check/format and diff checks pass.
The full Python suite, Web suite, typechecks, build, and browser E2E have not
been rerun for `6bc0351`. At `2026-10-27T21:28:03Z`, external Arena batch PID
**3727342** held lock inode **6423106** in `D` state; PSI avg10 was 45.93%
(`some`) / 40.80% (`full`), 9.7 GiB was available and 459 MiB swap was free.
It was left untouched. No exchange source or protected service was accessed.

### Final Python, Web, build, and browser checkpoint — 2026-10-27 21:36 UTC

Code commit `008106b` adds an explicit integer check for the Coinbase Decimal
exponent tuple field, removing its Frontier-local strict-mypy diagnostic while
retaining the existing non-finite and extreme-value rejection. Its parameter
test covers `NaN`, infinity, and out-of-range positive/negative exponents. The
focused Coinbase module passes **11/11** in 1.70 seconds pytest time / 2.15
seconds wall at **74,804 KiB peak RSS**, zero swaps. A strict direct-module
check with `--follow-imports=silent` passes all seven changed Python source
files in 1.99 seconds at **407,748 KiB peak RSS**, zero swaps. An earlier
unfiltered mypy invocation reported 17 diagnostics, including the Coinbase
typing issue fixed here and transitive pre-existing Veritas/Arena diagnostics;
that unfiltered invocation was not rerun after the guard.

The complete `tests/frontier` suite passes **269/269** in 42.33 seconds pytest
time / 43.61 seconds wall at **352,484 KiB peak RSS**, zero swaps. It emits
only the existing Starlette/httpx TestClient deprecation. The Web unit suite
passes **40/40** in 14.98 seconds test time / 15.40 seconds wall at **346,668
KiB peak RSS**, zero swaps. TypeScript typecheck passes in 7.57 seconds at
**441,532 KiB peak RSS**, zero swaps. Targeted ESLint passes in 1.31 seconds
at **269,940 KiB peak RSS**; Prettier check passes in 0.91 seconds at
**174,180 KiB peak RSS**. Ruff check/format and `git diff --check` pass.

The production frontend build completed into
`/tmp/midas-frontier-build-20261027-2132`; Vite transformed 2,228 modules and
built in 4.84 seconds (12.74 seconds total wall) at **701,536 KiB peak RSS**,
zero swaps. The Frontier bundle is 102.97 kB JS / 36.10 kB CSS. The existing
544.41 kB Chart chunk advisory and the external-output-directory notice remain;
the repository `dist` was not used. The full browser suite passed **12/12** in
27.0 seconds Playwright time / 27.49 seconds wall at **209,416 KiB peak RSS**,
zero swaps, with one worker. It includes all four Frontier cases and both
bounded Laboratory browser cases. The API used isolated temporary database,
Arena, and Frontier roots; no exchange probe was issued.

At `2026-10-27T21:36:40Z`, no global Arena lock holder was present. Memory PSI
avg10 was 0.00% (`some`/`full`), avg60 4.24% / 3.72%, avg300 14.30% / 12.58%;
9.5 GiB was available and 455 MiB swap was free. Project Frontier remains
isolated, research-only, undeployed, and **PARTIALLY VERIFIED** because source
permissions, genuine cross-venue payoff validation, and deployment readiness
remain unresolved.

### Legacy integration admission check — 2026-10-27 21:39 UTC

The planned compatibility selection covers `tests/integration/test_adapters.py`,
`tests/integration/test_api.py`, `tests/integration/test_recording_isolation.py`,
and `tests/arena/test_frontier_replay.py`. It was not started. At
`2026-10-27T21:39:36Z`, external batch PID **3745206** was in uninterruptible
I/O wait and held `/home/charlie/midas/data/arena/.global-admission.lock`;
memory PSI was **44.57% some / 39.03% full avg10**, with 40.17% / 35.19%
avg60. The lock probe confirmed the admission slot was occupied. The batch was
left untouched, and the four-module compatibility selection is deferred until
the shared lock releases and host pressure settles. This does not change the
269/269 Frontier, 40/40 Web, or 12/12 browser results above; those results were
collected in their separately documented admission windows. No service,
exchange, or protected evidence store was accessed.

### Legacy integration and Arena admission regression — 2026-10-27 21:46 UTC

The entire `tests/integration` directory passed **55 tests**, with one
PostgreSQL runtime test skipped because `MIDAS_TEST_POSTGRES_URL` was
intentionally unset. It ran with `PYTHONPATH=packages:.:tests`, ensuring local
package and sibling-test imports resolve from this worktree, and took 28.53
seconds pytest time / 29.82 seconds wall at **210,816 KiB peak RSS**, zero
swaps. The existing Starlette/httpx `TestClient` deprecation is the only
warning. The integration tests use temporary SQLite roots, local fixtures,
and mock transports; no exchange API or configured PostgreSQL service was
used.

`tests/arena/test_admission.py` then passed **8/8** in 1.41 seconds pytest
time / 2.04 seconds wall at **178,692 KiB peak RSS**, zero swaps. This
includes `test_resource_snapshot_detects_workers_across_arena_roots`, whose
purpose-specific resource snapshot is now isolated from live host pressure;
the separate threshold tests use controlled snapshots. No worker or systemd
job was started. At `2026-10-27T21:46:43Z`, shared Arena admission was free,
PSI avg10 was 0.00% (`some`/`full`), 9.9 GiB was available, and 455 MiB swap
was free. The earlier repository-wide 50-test interruption is now partially
revalidated across all integrations plus the bounded Arena admission module;
unrelated repository collection/runtime limits remain open.

### Post-test resource recheck — 2026-10-27 21:48 UTC

At `2026-10-27T21:48:09Z`, external Veritas batch PID **3762324** remained in
uninterruptible `D` state at `mem_cgroup_handle_over_high`, running
`scripts/veritas_gap_detail_v2_batch.py` against its existing Veritas and
Arena roots. Memory PSI avg10 had risen to **47.93% some / 41.46% full**.
The process was left untouched. No Frontier tests or builds were started
after it appeared; the passing bounded test results above remain valid. The
shared admission lock should be checked again before further resource-consuming
verification.

### Resource admission released — 2026-10-27 21:49 UTC

At `2026-10-27T21:49:51Z`, PID **3762324** had exited and no holder of the
shared Arena admission lock was listed. Memory PSI avg10 was 0.00% (`some` and
`full`); available memory was 9.9 GiB and 455 MiB swap was free. No test was
repeated: the complete browser suite already passed 12/12 at the latest
unchanged UI checkpoint (`008106b`, 21:36 UTC), while the 21:45 and 21:46
legacy regressions were independently completed afterward. Recheck before any
future worker-admission attempt.

### Bounded coverage analytics — 2026-10-27 22:13 UTC

Code commit **`4c9a8d8`** adds the no-network endpoint
`GET /api/frontier/analytics/coverage` and the native Mission Control
**Coverage & quality** tab. This closes a concrete Frontier intelligence gap:
the workspace can summarize the locally recorded market mix and inventory,
book-source quality, denomination-aware spreads and top depth, replay
classifications/rejection reasons, and independently recomputed timing evidence.
All values remain explicitly scoped to saved inputs. Follow-up commit
**`66e89a5`** adds exact market-observation and quote-denomination identity to
the repeated-construction signature so changes in pinned economic identity
cannot be counted as one recurring construction.

The code commit changes `apps/api/frontier.py`,
`packages/midas/frontier/analytics.py`, `apps/web/src/Frontier.tsx`,
`apps/web/src/Frontier.test.tsx`, `apps/web/e2e/frontier.spec.ts`,
`tests/frontier/test_analytics.py`, and `tests/frontier/test_api.py`. The
follow-up code commit changes `packages/midas/frontier/analytics.py` and
`tests/frontier/test_analytics.py`. The
documentation checkpoint updates the architecture, development guide, mission
ledger, this report, and `docs/MIDAS_CURRENT_STATE.md`.

The API caps the recent sample at 50 normalized markets, 50 book observations,
20 eligible replay runs, and 5,000 candidate records. Full persisted
market/instrument identity counts are read from the existing indexed store.
Held venues are filtered from both inventory and replay/sample views. A book is
eligible for pricing only after receipt/hash/provenance checks, a market and
instrument join, and exact quantity/quote identity checks; the book must be
two-sided, uncrossed, and unflagged. Freshness and exchange-clock availability
are reported separately from structural validity. Quote-identity delimiter
escaping avoids grouping distinct namespaced assets under one label, and
conflicting canonical aliases for one venue-native market prevent book joining.
Spread calculations use `Decimal` and are grouped by venue, market type,
quantity unit, and quote asset. Candidate rejection reasons count once per
distinct reason per rejected record. A repeated gross-positive construction
requires a verified independent audit, recomputed positive worst-case gross
P&L, verified timing, pinned market-observation IDs and quote denominations,
distinct book sets, and distinct replay times; the metric does not imply
net-positive economics, independent opportunity counts, continuous persistence,
or executable profit. The route performs no source network request and returns
`network_called: false`.

Verification for this checkpoint:

- `tests/frontier`: **279 passed**, 70.89 seconds wall, **354,788 KiB peak RSS**,
  zero swaps; only the existing Starlette/httpx deprecation warning.
- Web unit tests: **40 passed**, 16.10 seconds wall, **333,216 KiB peak RSS**,
  zero swaps.
- Coverage browser component behavior is part of those 40 cases. A dedicated
  Playwright E2E case also passes **1/1**, 6.62 seconds wall, **186,788 KiB peak
  RSS**, zero swaps, against its isolated temporary API/store. It checks the
  200 `network_called: false` response and confirms no source-probe request.
- Strict mypy passes for `packages/midas/frontier/analytics.py` and
  `apps/api/frontier.py`; Ruff check/format, targeted ESLint, Prettier,
  TypeScript typecheck, and `git diff --check` pass.
- The Vite production build transformed 2,228 modules in 5.46 seconds at
  **667,976 KiB peak RSS**, zero swaps, using
  `/tmp/midas-frontier-build-20261027-2206`. Frontier emits 112.13 kB JS /
  36.10 kB CSS. The existing 544.41 kB Chart chunk remains above Vite's 500 kB
  advisory threshold.

The Web suite, dedicated browser E2E, and Vite build ran after `4c9a8d8` and
before the backend-only signature follow-up `66e89a5`. The final full Frontier
Python suite and strict mypy check for the changed analytics module ran after
`66e89a5`; that follow-up changed no frontend files.

No live exchange request, protected service, held capture, or production store
was accessed. The changed view's dedicated browser case and all Web unit tests
passed; the full 12-case repository browser suite was not rerun after this
checkpoint. The coverage feature is **COMPLETE AND VERIFIED** in local bounded
tests, while Project Frontier remains **PARTIALLY VERIFIED**, research-only,
isolated, and undeployed. Kalshi/Kraken permissions, genuine live cross-venue
payoff validation, executable synchronization/capital assumptions, and
production eligibility remain unresolved.

### Event-time replay checkpoint — 2026-10-27 22:24 UTC

Code commit **`30576f1`** adds the offline engine in
`packages/midas/frontier/timeline.py` and its four fixture cases in
`tests/frontier/test_timeline.py`. It extends saved-input
replay from one cross-sectional book set to a bounded sequence of observation
times. It orders the input deterministically, pins normalized market/book and
relationship evidence in a manifest, applies only market metadata and verified
relationships available by each UTC cutoff, and selects the latest book per
instrument only while it remains within the configured freshness window.
Degraded/unavailable source events remove that venue's books; a recovery event
does not revive pre-interruption quotes, so each leg needs a later book
observation. Missing or expired legs are passed to the existing replay and
independent arithmetic audit as absent evidence and are reported as incomplete,
never as held-forward prices.

The result includes per-frame source state, per-instrument observation identity,
age and inclusion/exclusion reason, candidate classification and economic
summary, plus the deterministic replay and timeline hashes. Recorded source
events require a SHA-256-shaped observation reference; the engine does not load
or authenticate that referenced store row. Fixture and scenario events remain
explicitly labelled. Inputs are capped at 100 markets, 200 books, 100 verified
relationships, 100 source events, 500 instruments, and 128 frames; normalized
input and result bounds are 32 MiB and 16 MiB.

Four fixture cases cover quote deterioration, exact freshness-boundary behavior,
source outage/recovery invalidation, deterministic input-order independence,
and exclusion of a relationship verified after an earlier frame. The focused
timeline tests pass **4/4** in 0.69 seconds, at **54,864 KiB peak RSS** and zero
swaps. The final complete `tests/frontier` run passes **283/283** in 69.44
seconds pytest time / 70.69 seconds wall, at **355,720 KiB peak RSS** and zero
swaps; only the existing Starlette/httpx `TestClient` deprecation warning
remains. Strict mypy passes for `timeline.py`; Ruff check/format and
`git diff --check` pass.

At this earlier engine-only checkpoint, the timeline was not API-accessible,
persisted through Arena's job/artifact path, or visible in the dashboard.
Cross-sectional paired snapshots were the only Arena replay job. No external
API, source capture, protected service, campaign, Arena worker, or production
store was used. Frontier remained **PARTIALLY VERIFIED**, research-only, and
undeployed. The follow-up integration is documented in the later checkpoint
below.

### Event-time Arena integration and finite collector — 2026-10-27 22:58 UTC

Code commit `5e04c14b47c9b820946259a8ad1e232b4597190a` integrates the event-time
engine with Arena's existing bounded job protocol. The job references an
immutable snapshot whose identity hashes saved markets, joined books, verified
relationships, source scenario events, either explicit cutoffs or a deterministic
derived cutoff policy, freshness limit, scenario, and code version. `JobSpec`
constrains this kind to at most 300 seconds, 512 MiB, 50% CPU, nice 15, and idle
I/O; the worker kind is network restricted. The result artifact contains the
timeline's per-frame replay references and hashes and is independently
revalidated against the durable Arena job record. The snapshot store is bounded
to 128 MiB and 1,000 files; individual normalized inputs are limited to 32 MiB
and the result to 16 MiB.

`POST /api/frontier/arena-timeline-replay` packages only local stored evidence,
reports `network_calls: 0`, and submits through Arena's ordinary admission gate.
The bounded job/result catalog and result routes verify pinned identity and
quarantine held-source inputs. The Frontier readiness gate accepts only a
completed artifact with the matching snapshot and result hashes plus a worker
runtime record. No Arena timeline job was submitted or launched for this
checkpoint, so readiness remains `LIVE_VALIDATION_PENDING`.

The request explicitly rejects `basis=recorded` source-status events. Although
the event-time engine validates a hash-shaped reference, the application does
not yet join it to a validated, hash-checked stored source-health row. Fixture
and scenario events are accepted as such and remain labelled; the UI does not
present these as measured source status.

The new Replay & Readiness panel shows bounded timeline job history and, for a
verified result, each frame's freshness and source-exclusion counts, source
status basis, candidate classifications, and evidence digests. The explicit
submission control is disabled until saved markets exist. It also explains that
the output does not establish simultaneous executable books, fills, venue
access, or profit.

Preceding this, commit `b6b8a99337b5b08a54b5011eaf72d30949ab0b1b` adds
`midas.frontier.collection.BoundedSourceCollector`. It is a sequential finite
per-source lifecycle with append-only restart checkpoints linked by row hashes
in a separate bounded SQLite journal. Limits are 20 markets, 10 book tasks, 20
levels, 16 MiB captured evidence, and 300 seconds per run. Start and resume
revalidate the source's configured adapter version/capabilities; start checks
the live public-probe flag and policy hold. It is not yet registered as an API
operation, Arena job, systemd service, or timer. Its fixtures use a fake adapter;
no collector or source request was launched.

#### Verification and reproducibility

- Combined Frontier/Arena regression command: **347 passed** in 130.66 seconds.
  This includes all `tests/frontier` cases, paired and event-time Arena artifact
  tests, job-schema checks, and Arena API regressions. Only the existing
  Starlette/httpx `TestClient` deprecation warning remains.
- Web unit suite: **40/40**. TypeScript typecheck, ESLint, Prettier, Ruff
  check/format, `git diff --check`, scoped strict mypy for the four changed
  backend modules, and the Vite production build pass.
- Isolated Playwright scenario: **1/1**. It started the demo API using
  temporary database, Frontier, and Arena roots, opened the Replay & Readiness
  view, and observed zero public-probe requests and zero paired/timeline job
  submissions. The saved-market prerequisite leaves timeline submission
  disabled.
- Repository-wide mypy reports **35 existing errors across eight unrelated
  Veritas/Arena/API files**; scoped strict mypy reported no error in the changed
  timeline, job, or API modules.
- The Vite output includes the existing 544.41 kB Chart chunk advisory. No
  representative browser/memory profile or production build deployment was
  attempted.

The changed files in `5e04c14` are `apps/api/arena.py`,
`apps/api/frontier.py`, `apps/web/e2e/frontier.spec.ts`,
`apps/web/src/Frontier.test.tsx`, `apps/web/src/Frontier.tsx`,
`apps/web/src/frontier.css`, `packages/midas/arena/jobs.py`,
`packages/midas/arena/frontier_timeline.py`,
`tests/arena/test_frontier_timeline.py`, and
`tests/frontier/test_timeline_api.py`. Commit `b6b8a99` changes
`packages/midas/frontier/collection.py` and `tests/frontier/test_collection.py`.
The current follow-up docs update `FRONTIER_ARCHITECTURE.md`,
`FRONTIER_OPERATIONS.md`, `FRONTIER_MISSION_LEDGER.md`,
`FRONTIER_ENGINEERING_REPORT.md`, `docs/DEVELOPMENT.md`, and
`docs/MIDAS_CURRENT_STATE.md`.

#### Current checkpoint matrix

| Component | Status | Evidence and boundary |
| --- | --- | --- |
| Event-time replay algorithm and per-frame independent audit | COMPLETE AND VERIFIED | Deterministic fixture suite covers freshness boundaries, outage invalidation, lookahead rejection, and canonical replay hashes; no live cross-venue timeline was observed. |
| Event-time Arena snapshot, worker dispatch, artifact integrity, API result reads | IMPLEMENTED, LIVE VALIDATION PENDING | Job spec, executor, artifact hashes, API input pinning, history/result, held-source filtering, and readiness behavior are tested with temporary fixture roots; no Arena worker was launched for this checkpoint. |
| Event-time Mission Control view | IMPLEMENTED, LIVE VALIDATION PENDING | Web fixture test covers successful frame display; isolated browser test covers empty/offline state and proves opening the view submits no job or source request; no actual worker result was rendered in a browser. |
| Finite source collector module | PARTIALLY VERIFIED | Restart, cancellation, persistence recovery, and source-specific errors use fake adapters. No API/Arena registration, service, real adapter call, or live validation is present. |
| Recorded source-health event join | DEFERRED | Request payloads reject `basis=recorded`; an authenticated-by-hash join to validated local source-health evidence is required before accepting it. |
| Source permissions and live multi-venue validation | BLOCKED | No new live source request occurred; configured source-use restrictions still govern live validation. |
| Production deployment | DEFERRED | Frontier remains isolated and unmerged; deployment is outside this development checkpoint. |

Project Frontier remains **PARTIALLY VERIFIED**, isolated, research-only,
unmerged, and undeployed. No economically eligible live opportunity or positive
profitability result was established. Next safe implementation steps are to
validate a local source-health evidence join, continue fixture-backed
adversarial and resource tests, and determine whether an OS-enforced egress
boundary is available before registering collection as a networked Arena job.

### Recorded source-health join and pinned freshness control — 2026-10-28 00:18 CET

Code commit `ea073c4cdb4a00b70fc609e8806f80a40542cd4c` completes the local
recorded source-health join for event-time replay. `CollectionJournal` now has a
read-only batch resolver for up to 100 checkpoint-row hashes. It does not call
`initialize`, create a missing journal, or modify collection evidence. The
resolver enforces the 64 MiB journal budget and bounded checkpoint/run counts,
checks the collection schema, validates the run-spec hash and model identity,
and walks the entire selected run's sequence/hash chain before returning any
health record. The new hash index helps current journals; correctness does not
depend on that index, so prior collection journals remain queryable within the
same byte/row bounds.

The timeline API admits a `basis=recorded` event only if its evidence digest
resolves to a verified checkpoint and its venue, checked time, status, and
canonical reason match the recorded `SourceHealth`. The API maps only
`HEALTHY`, `DEGRADED`, and explicitly `UNAVAILABLE`; `NOT_PROBED` and
`UNSUPPORTED` are not interpreted as venue availability. A `HEALTHY` record
also needs a nonfuture successful-source timestamp. The event is rejected if
its venue is held. Unknown digests and field substitutions return 422; corrupt
journal identity/timing fails closed with 409. Repeated digests in one request
are rejected. No network activity is part of the join.

The joined value is the collector's adapter-local state at the checkpoint
check time, derived from that adapter's request history. It is not a continuous
venue-health feed, account-eligibility check, or reachability guarantee. The
Mission Control callout states this boundary beside the replay result.

Arena timeline snapshots now use schema version 2, pinning the sorted
`validated_source_status_checkpoint_sha256s` alongside the event. The model
requires exact set equality between recorded event references and those pinned
join identities. Prior schema-1 snapshots without recorded source status remain
loadable; schema 1 cannot carry recorded events. The API remains the trust
boundary that verifies the source journal before creating a content-addressed
snapshot. Arena timeline execution remains network-restricted and consumes the
already pinned local input.

Mission Control's Replay & Readiness panel now includes a maximum book receipt
age field. It accepts integers from 1 through 3,600,000 milliseconds, disables
submission for invalid values, sends the selected value, and displays the
freshness limit from the returned result. Follow-up commit
`8e79bf1f3bc583aa2329096729c6dd9c624c603d` adds a visible explanation that
recorded health reflects adapter-local state at its checkpoint, not continuous
venue availability, reachability, or account eligibility. No other replay
assumption is changed by these controls.

#### Verification and evidence

- Combined command over all `tests/frontier`, paired/event-time Frontier Arena,
  Arena job-schema, and Arena API selections: **350 passed** in 80.52 seconds.
- Focused `tests/frontier/test_collection.py`, `test_timeline_api.py`, and
  `tests/arena/test_frontier_timeline.py`: **21 passed** in 6.25 seconds.
- Web suite after the source-health wording update: **40/40**. TypeScript
  typecheck, ESLint, Prettier, and production
  build passed. The build retains the known 544.41 kB Chart chunk advisory.
- Isolated Playwright case: **1/1** in 5.3 seconds using temporary API, Arena,
  and database roots. Opening Replay & Readiness issued no source probe and no
  replay submission. The complete 12-case browser suite was not rerun here.
- Legacy integration and Arena admission set: **63 passed, 1 skipped** in 29.88
  seconds with `MIDAS_TEST_POSTGRES_URL` unset; the skip is the PostgreSQL case.
- Strict mypy passed for `collection.py`, `frontier_timeline.py`, and
  `apps/api/frontier.py`. Ruff and formatting checks passed. The existing
  TestClient deprecation warning remains.
- Host sample at `2026-10-27T23:15:35Z` measured 0.00% memory PSI avg10,
  10 GiB available memory, and 400 MiB free swap. This is a time-specific sample.

Changed code files are `apps/api/frontier.py`, `apps/web/src/Frontier.tsx`,
`apps/web/src/Frontier.test.tsx`, `apps/web/src/frontier.css`,
`packages/midas/frontier/collection.py`,
`packages/midas/arena/frontier_timeline.py`,
`tests/frontier/test_collection.py`, `tests/frontier/test_timeline_api.py`, and
`tests/arena/test_frontier_timeline.py`. Documentation was then updated in
`docs/DEVELOPMENT.md`, `docs/MIDAS_CURRENT_STATE.md`,
`docs/frontier/FRONTIER_ARCHITECTURE.md`,
`docs/frontier/FRONTIER_OPERATIONS.md`,
`docs/frontier/FRONTIER_MISSION_LEDGER.md`, and this report.
Commit `8e79bf1` changes `apps/web/src/Frontier.tsx` and
`apps/web/src/Frontier.test.tsx` to add and verify the adapter-local health
limitation.

No exchange request, collector, Arena worker, Reality action, production
service, historical-store read, push, merge, or deployment occurred. No
cross-venue opportunity or positive economic result was established.

#### Current checkpoint matrix

| Component | Status | Evidence and boundary |
| --- | --- | --- |
| Collection-journal health lookup | COMPLETE AND VERIFIED | Read-only bounded batch lookup verifies run spec and complete checkpoint chain; tests cover valid joins, tampering, unknown digest without file creation, and held-source rejection. No genuine source health capture was made. |
| Recorded event mapping and timeline schema 2 | COMPLETE AND VERIFIED | API field matching, state mapping, health-time consistency, checkpoint hash pinning, and schema-1 compatibility are covered by fixtures. Snapshot attestation identifies an API-verified join; it is not a digital signature. |
| Timeline freshness control | COMPLETE AND VERIFIED | Unit test sends 5,000 ms, checks 0 disables submission, and checks result rendering; typecheck/build/browser empty-state pass. |
| Timeline Arena worker and full result browser flow | IMPLEMENTED, LIVE VALIDATION PENDING | Job schema, artifact binding, and fixture execution are tested. No worker was launched and no worker result was rendered in a real browser. |
| Finite source collector module | PARTIALLY VERIFIED | Restart, cancellation, persistence recovery, and failure cases use fixture adapters. No live capture or collection job/API lifecycle is registered. |
| Live source permission and multi-venue evidence | BLOCKED | Existing source-use holds remain; there is no live observation or genuine cross-venue relation in this checkpoint. |
| Production deployment | DEFERRED | The Frontier branch remains isolated and unmerged; no production transition was attempted. |

Project Frontier remains **PARTIALLY VERIFIED**, isolated, research-only, and
undeployed. Next safe engineering work is a bounded read-only catalogue and UI
for verified recorded health checkpoints, plus offline adversarial replay cases;
the following checkpoint completes the catalog and UI portion. Do not register
a networked collection job until the allowed egress boundary is explicit and
testable. The source permissions, live multi-venue evidence, and deployment
gates remain separate.

### Verified recorded-health catalog and replay provenance — 2026-10-27 23:31 UTC

Code commits **`31f62db`**, **`1779e89`**, **`9a3eced`**, and **`8f9b9b8`** add
a local read-only catalog of collector health evidence, explicit replay event
selection, visibility of manifest-pinned checkpoint hashes, and early
rejection of same-venue/same-time status duplicates.

`CollectionJournal.latest_source_health_checkpoints` does not call
`initialize`, create a missing journal, or write to collection evidence. It
streams the bounded journal (maximum 20,000 checkpoints and 64 MiB) and selects
at most 20 latest timestamped health observations, one per run. Each selected
run's spec hash and venue are checked, then the existing batch resolver
revalidates the complete checkpoint sequence and hash chain. Held venues are
filtered before the response. Timestamp-less `NOT_PROBED` does not represent a
new replay event and does not shadow the last timestamped health record. A
timestamped state that cannot map to availability shadows older status for that
run.

`GET /api/frontier/collection-health-events?limit=20` returns the recorded
event plus run, adapter version, checkpoint sequence, health state, last-success
time, and row digest. The response reports `network_called: false` and
`source_health_scope: adapter_local_checkpoint`. Before staging a timeline, the
API requires event venue/state/time/reason/digest to match the verified
checkpoint and rejects two events for the same venue at one timestamp. Mission
Control queries the catalog only while Replay & Readiness is open. All events
start unchecked, and selecting one disables another event for the same
venue/check-time. The result detail shows the checkpoint hashes pinned into the
manifest. UI text distinguishes adapter-local checkpoint health from
continuous venue availability and account eligibility.

#### Verification and resource decision

- Combined `tests/frontier` plus paired/timeline Arena replay, job, and API
  selection: **354 passed** in 83.42 seconds; peak RSS **363,776 KiB**, zero
  swaps. The existing Starlette/httpx TestClient deprecation warning remains.
- Collector and timeline API focused set: **18 passed** in 7.37 seconds; the
  follow-up timestamp-less-state and chain-integrity cases passed **2/2** in
  0.56 seconds. Duplicate same-venue/time request rejection passed in its
  focused API case.
- `apps/web/src/Frontier.test.tsx`: **8 passed**. It verifies opt-in selection,
  same-time exclusion, and rendering the result manifest digest.
- Isolated Playwright Replay & Readiness case: **1/1 passed** in 5.0 seconds
  using temporary API/store roots. It observes the empty verified-health state
  with no source probe and no replay submission on page open.
- TypeScript passed in 7.92 seconds at **448,228 KiB** peak RSS. The production
  Vite build passed in 5.10 seconds at **647,020 KiB** peak RSS, zero swaps.
  Frontier output is 124.32 kB JS / 39.65 kB CSS; the existing 544.41 kB Chart
  chunk warning remains. Strict scoped mypy passed for the collection, timeline,
  Arena timeline, and API modules. Ruff, ESLint, Prettier, and `git diff --check`
  passed.
- Initial browser admission check found shared Arena lock inode **6423106** held
  by PID **3885836** with PSI avg10 29.42% `some` / 22.00% `full` and 3.7 GiB
  swap in use. The browser run and build were deferred until the lock released;
  they then ran after avg10 fell to 0% and 10 GiB was available.

No exchange API, collector, Arena worker, protected recorder, held capture, or
production store was accessed. The catalog contains no genuine current source
health sample and this increment established no cross-venue price relation or
economic result.

Code files in `31f62db` are `packages/midas/frontier/collection.py`,
`apps/api/frontier.py`, `tests/frontier/test_collection.py`,
`tests/frontier/test_timeline_api.py`, `apps/web/src/Frontier.tsx`,
`apps/web/src/Frontier.test.tsx`, `apps/web/src/frontier.css`, and
`apps/web/e2e/frontier.spec.ts`. Commit `1779e89` changes timestamp-less health
semantics. Commit `9a3eced` displays manifest-pinned digests. Commit `8f9b9b8`
adds duplicate-time API and UI safeguards. Documentation is in the following
checkpoint commit.

#### Updated completion matrix

| Component | Status | Evidence and boundary |
| --- | --- | --- |
| Local recorded-health catalog | COMPLETE AND VERIFIED | Bounded read-only scan, latest timestamped observation, held filtering, and full-chain verification have fixture coverage; no live source event exists. |
| Replay health event selection and digest display | PARTIALLY VERIFIED | Component suite and empty-state Playwright pass. No journal-backed live health event was available in a browser. |
| Duplicate same-time source events | COMPLETE AND VERIFIED | API rejects same-venue/same-time duplicates before job staging; UI disables a second selection; focused API and UI cases pass. |
| Timeline worker and populated result browser flow | IMPLEMENTED, LIVE VALIDATION PENDING | Job/artifact fixture paths are covered. No new Arena worker was launched. |
| Live source permissions and multi-venue evidence | BLOCKED | Existing source-use holds remain; the catalog is not a capture path. |
| Production deployment | DEFERRED | No merge, push, or deployment occurred. |

Frontier remains **PARTIALLY VERIFIED**, isolated, research-only, and
undeployed. Continue the remaining offline acceptance work. Do not open Arena
network egress or register an unattended collector to populate this catalog.

### Explicit finite source collection API — 2026-10-27 23:38 UTC

Code commit **`cf67b2b`** exposes `BoundedSourceCollector` as
`POST /api/frontier/collect/{venue}` and an explicit Exchanges-view action.
The route checks the configured source enablement and public-probe flag, rejects
held sources, verifies market-discovery and requested book capabilities, and
applies the source's market limit before collection starts. It shares the
per-venue lock with the existing probes. The request calls the collector in the
API request lifecycle and starts no Arena job, worker, timer, or background
loop.

The API caps each request at five markets, two books, depth ten, 4 MiB of
captured evidence, and 60 seconds wall time. The UI sends a fixed smaller
request: three markets, one book, depth five, and 30 seconds. Adapter request
count and a conservative request upper bound are returned with the checkpointed
run result. Mission Control displays the run state and identifier, counts,
failures, and the limitation that this source-health event is adapter-local.
Source adapters remain disabled by default; Kalshi, Kraken, and Coinbase holds
remain effective. The route supports starting a run only; HTTP run-history and
resume routes are still needed for complete operator recovery after a paused
run or page reload.

#### Verification

- `tests/frontier/test_collection_api.py`: **2/2** in 1.10 seconds using the
  fixture adapter. Coverage includes successful persisted market/book capture,
  request bounds, and disabled/held rejection before fake requests or journal
  creation.
- `apps/web/src/Frontier.test.tsx`: **8/8** in 4.19 seconds. The test verifies
  no automatic POST, the fixed finite request body, persisted result summary,
  and adapter-local health caveat.
- TypeScript, strict scoped mypy for `frontier.py` and `collection.py`, Ruff
  check/format, Prettier, and `git diff --check` pass.
- Combined Frontier/Arena Python command: **354 passed, 2 failed** in 81.75
  seconds, **366,436 KiB peak RSS**, zero swaps. Both failures are existing
  supervisor tests (`test_supervised_job_runner_imports_the_submitted_checkout`
  and `test_veritas_qualification_supervisor_has_read_only_resource_bounds`)
  rejected by the shared `resource_admission_lock_busy` check. The observed
  lock holder was existing Veritas batch PID **3913373** in `D` state using
  existing Veritas/Arena roots; it was not interrupted. Post-run memory PSI
  avg10 measured **35.60% some / 29.55% full**, with **9.9 GiB available** and
  **3.7 GiB swap in use**. Do not retry admission-dependent tests until the
  shared lock releases and current pressure is measured again.
- Production build and browser tests were deferred for this revision. The
  previous build and browser results are dated and do not validate `cf67b2b`.

No genuine source call, live collector run, Arena worker, Reality action,
production service change, or historical evidence access occurred. All
integrations here are fixture verified; live collection remains pending.

| Component | Status | Evidence and remaining work |
| --- | --- | --- |
| Finite collection route and UI | IMPLEMENTED, LIVE VALIDATION PENDING | Source gates, request caps, stored result summary, and no-background behavior pass fixtures. Live capture and populated browser verification remain pending. |
| Collection module checkpoint and resume | PARTIALLY VERIFIED | Module restart recovery remains fixture tested; HTTP history and resume routes are not implemented. |
| Disabled/held source guards | COMPLETE AND VERIFIED | API tests reject before collector call or journal creation. |
| Combined Frontier/Arena regressions | PARTIALLY VERIFIED | 354 pass; two shared-lock failures are external resource-admission failures. |
| Browser and production build for latest code | IMPLEMENTED, TESTING PENDING | Deferred under measured host pressure; earlier revision evidence is not transferred. |
| Production deployment | DEFERRED | Branch remains isolated, unmerged, and undeployed. |

Frontier remains research-only and **PARTIALLY VERIFIED**. Next safe work is to
wait for the existing Arena lock and memory pressure to recover, then rerun the
two blocked tests and latest-revision build/browser checks. Continue with
offline collection history/recovery integration or fixture-backed acceptance;
do not start unattended collection or contact a venue merely to populate test
data.

## Finite collection history and resume follow-up — 2026-10-27 23:53 UTC

Code commit `305814b` adds operator recovery for finite collection. The API
lists at most 20 recent run checkpoints from the separate collection journal,
verifies selected run hash chains, filters held venues, and reads without
creating a missing journal or contacting a source. The Exchanges workspace
shows run state, checkpoint digest, counts, health scope, and resume
eligibility.

Resume requires an explicit request. Both the API and collector revalidate
source enablement, public-probe configuration, policy holds, pinned source
configuration, adapter version and capability manifest, required
capabilities, market limits, and request bounds before additional source
work. Terminal runs return their stored result without requests. No automatic
resume, background worker, or retry loop was added. Request accounting
distinguishes total requests over the run from the ceiling for one attempt.

The focused collection module/API tests pass **20/20** (6.15 seconds pytest
time, 87,036 KiB peak RSS, zero swaps); the Frontier component suite passes
**8/8**, the isolated browser smoke passes **1/1**, and TypeScript, strict
scoped mypy, Ruff, ESLint, Prettier, and the production Vite build pass. The
build used `/tmp/midas-frontier-build-20261028-0049`, reached 690,080 KiB peak
RSS with zero swaps, and retains the existing 544.41 kB Chart chunk advisory.
The combined Frontier and selected Arena regression passes **358** cases but
has **two existing Arena supervisor test failures** because a Veritas batch
held the shared resource admission lock; all Frontier tests passed in that
run. PID 3939942 was in `D` state at the 23:53 UTC recheck and was left
untouched. PSI avg10 had risen to 49.25% `some` / 42.91% `full`; no retry was
started.

No exchange API, held source capture, protected Reality service, Arena worker,
or production deployment was used. This fixture and isolated-browser evidence
establishes no genuine multi-venue observation or economic opportunity.

| Component | Status | Boundary |
| --- | --- | --- |
| Finite collection history and explicit resume API | COMPLETE AND VERIFIED | Fixture-backed; live source capture remains pending and disabled by default. |
| Policy, config, and capability revalidation | COMPLETE AND VERIFIED | Invalid/held resumes fail before new source requests or pending-capture recovery. |
| Exchanges history/resume UI | PARTIALLY VERIFIED | Component and isolated browser checks pass; no populated genuine-source history exists. |
| Selected Frontier/Arena regressions | PARTIALLY VERIFIED | All Frontier tests passed in the combined run; the two shared-lock-denied Arena supervisor cases passed separately after release. All 360 selected cases pass across two invocations, with no single clean combined run. |
| Latest production frontend build | COMPLETE AND VERIFIED | Temporary build output only; no deployment. |
| Genuine cross-venue economics and production transition | DEFERRED | No live cross-venue result established; source policy and separate deployment review remain. |

See the [mission ledger](FRONTIER_MISSION_LEDGER.md) for reproducible commands,
resource measurements, and the next safe action. Frontier remains isolated,
research-only, undeployed, and **PARTIALLY VERIFIED**.

### Arena admission-test follow-up — 2026-10-27 23:55 UTC

After the external holder exited, the two supervisor tests denied by the
earlier shared-lock collision passed **2/2** in a targeted 4.34-second run
(179,752 KiB peak RSS, zero swaps). Their `subprocess.run` launch is replaced
by a fixture, so no Arena worker started. The full combined selection was not
repeated: its other 358 cases had already passed. Thus all 360 selected cases
have passed across the two invocations, although there is no single clean
combined-run result. At the retry admission sample the lock was free and PSI
avg10 was 0%; a later sample was 0% avg10 with 10 GiB available. No production
or protected service state was touched.

### Full web regression — 2026-10-27 23:56 UTC

The complete web unit suite passes **40/40 across seven files** in 15.55
seconds reported by Vitest / 15.97 seconds wall at **300,960 KiB peak RSS**,
zero swaps. It includes Frontier, Arena, Readiness, Mission Control, Reality,
Veritas, and Laboratory component suites. This is component-level verification;
browser coverage remains the isolated Frontier case recorded above.

### Full Frontier browser regression — 2026-10-27 23:57 UTC

The complete Frontier Playwright spec passes **4/4** in 11.5 seconds reported
/ 12.05 seconds wall at **192,280 KiB peak RSS**, zero swaps. It validates the
local Exchanges history request without collection/source POSTs, no automatic
Arena job submission, fixture-only settlement inspection, and responsive
bounded graph interaction. The API ran with isolated test roots; no exchange
endpoint was called.

### Collection history policy and checkpoint-chain regressions — 2026-10-28 00:00 UTC

Commit `a7996f9` adds a regression for collection history when a venue's
source-use hold is active. The endpoint returns no eligible runs, reports that
no network was called, and leaves the adapter transport untouched. A second
assertion verifies that `latest_run_checkpoints()` fails closed when a stored
checkpoint digest is tampered with, matching the existing integrity checks on
other journal reads.

The focused collection module/API suite passes **21/21** in 6.06 seconds
reported by pytest / 6.53 seconds wall, at **87,676 KiB peak RSS** and zero
swaps. Ruff and `git diff --check` pass. Tests used fake adapters and temporary
storage. No exchange request, held capture read, Arena worker, Reality action,
or production change occurred. Since only tests changed, broader suites were
not repeated. The latest resource sample, at 00:00:12 UTC, showed the shared
admission lock free, PSI avg10 **0.64% some / 0.58% full**, and **10 GiB
available**; host resources may change after that sample.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Collection source-hold filtering and checkpoint-chain integrity | COMPLETE AND VERIFIED | Fixture regressions are included in the 21-case focused collection suite; no live source capture was performed. |
| Collection history and explicit resume | COMPLETE AND VERIFIED | HTTP and module tests only; live source use remains disabled by default and requires a separate policy review. |
| Cross-venue live relationships/economics and deployment | DEFERRED | No genuine cross-venue observation or production transition was established. |
| Project Frontier overall | PARTIALLY VERIFIED | Source permissions, genuine cross-venue validation, broader clean combined regression, and production prerequisites remain incomplete. |

Frontier remains isolated and research-only. Continue offline acceptance work
without treating this fixture evidence as live-source or deployment evidence.

### Missing-adapter collection responses — 2026-10-28 00:02 UTC

Commit `169bfa2` adds a shared adapter lookup guard for finite collection start
and resume. A venue that is part of the public venue enum but absent from the
registry now returns HTTP 409, `The <venue> source adapter is not registered.`,
before a collection journal is created or queried. The new API regression
covers both routes and confirms that the journal remains absent.

The complete collection API test module passes **6/6** in 1.98 seconds
reported / 2.52 seconds wall at **84,136 KiB peak RSS**, zero swaps. Ruff and
`git diff --check` pass; the existing Starlette/httpx deprecation warning is
unchanged. At 00:02:40 UTC the shared Arena admission lock was held by PID
3950719; memory PSI avg10 was **41.99% some / 37.85% full**, 10 GiB was
available, and 3.7 GiB of swap was in use. The focused test did not stage Arena
work. No source request, held capture access, protected service action, or
production change occurred.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Collection API missing-adapter handling | COMPLETE AND VERIFIED | Both start/resume return a bounded 409 before journal access; fixture API module passes 6/6. |
| Collection API history and resume | COMPLETE AND VERIFIED | Fixture-backed routes only; no live collection or populated genuine-source history. |
| Arena-dependent broad regression | PARTIALLY VERIFIED | Previously passed across separate invocations; do not retry while the shared lock is held and PSI is elevated. |
| Project Frontier overall | PARTIALLY VERIFIED | Genuine cross-venue validation, clean combined broad regression, live source policy review, and deployment prerequisites remain incomplete. |

Continue with read-only audits and isolated changes. Frontier remains isolated,
research-only, and undeployed.

### Unregistered adapter handling across source routes — 2026-10-28 00:04 UTC

Commit `01ffe05` extends the shared adapter lookup guard across Frontier's
source-specific trade, fee, market-detail, event-group, and multivariate
probes, plus generic market discovery. Combined with finite collection start
and resume in `169bfa2`, absent adapters now produce a bounded HTTP 409 rather
than an unhandled registry `KeyError`. The route performs the lookup before
source config, journal, or transport access.

A focused API test calls collection start, collection resume, and generic
market discovery with an empty registry; all three return the expected 409,
and no collection journal is created. It passes **1/1** in 0.65 seconds at
**75,800 KiB peak RSS**, zero swaps. Ruff and `git diff --check` pass. The
existing Starlette/httpx deprecation warning remains. The pre-test host sample
at 00:04:26 UTC had PSI avg10 **11.06% some / 9.93% full**, avg60 **33.28%
some / 29.88% full**, 10 GiB available, and no Arena admission-lock holder.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Missing-adapter source-route degradation | COMPLETE AND VERIFIED | Shared guard covers all nine source-facing lookup sites; representative collection and discovery routes pass with an empty registry. |
| Live multi-venue source validation | BLOCKED | Existing source-use holds and permission gaps remain; no source was probed in this checkpoint. |
| Arena-dependent broad regression | PARTIALLY VERIFIED | Prior results passed across separate invocations; rerun only after fresh pressure and lock admission checks. |
| Project Frontier overall | PARTIALLY VERIFIED | Live cross-venue economic evidence and production prerequisites remain outstanding. |

No exchange, collector, Arena worker, protected service, production store,
or deployment was used. Continue bounded offline acceptance work.

### Collection history with an absent adapter — 2026-10-28 00:05 UTC

Commit `b2e3eed` tests the history endpoint when a saved run outlives its
registered adapter. The API returns the locally pinned run and checkpoint
metadata, sets `network_called: false`, and marks the run non-resumable with an
explicit missing-adapter reason. The focused test passes **1/1** in 0.69
seconds at **72,864 KiB peak RSS**, zero swaps. Ruff and `git diff --check`
pass; the existing Starlette/httpx deprecation warning remains.

At the pre-test 00:05:01 UTC resource sample, PSI avg10 was **0.36% some / 0.33%
full**, avg60 was **18.90% some / 16.97% full**, 10 GiB was available, and no
shared Arena lock holder was visible. This was an offline temporary-store test;
no exchange call, held capture read, or Arena worker occurred.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Missing-adapter history and resume diagnostics | COMPLETE AND VERIFIED | The history remains inspectable while resume eligibility is false; fixture test confirms the reason and no network status. |
| Cross-venue source evidence and economics | BLOCKED | Existing policy restrictions prevent new source requests; no new multi-venue evidence is claimed. |
| Project Frontier overall | PARTIALLY VERIFIED | Deployment, genuine cross-venue validation, and broader clean combined regression remain incomplete. |

Continue bounded offline acceptance; Frontier remains isolated and research-only.

### Official source terms refresh — 2026-10-28

A read-only official-documentation review reconfirmed the Kalshi API's
own-trading and data-retention restrictions and the unresolved Kraken research
permission/retention scope. Kraken's current public Spot REST rate guidance is
one request per second or less, consistent with the Frontier transport's
default. Coinbase's Market Data Terms include a limited research-use license,
while restricting redistribution, certain benchmark/valuation outputs, and
AI/ML research use. Frontier does not enforce those purpose-specific limits;
the exact-version acknowledgement is only a local gate, not a blanket grant
for all analyses. The existing source holds and quarantine remain unchanged.
No exchange API, stored capture, or configuration was accessed or changed.
See the [source-data terms review](SOURCE_DATA_TERMS_REVIEW_2026-10-27.md) for
links and operational detail.

### Virtual funding-currency sensitivity — 2026-10-28 00:22 UTC

Code commit `530c9aa8b3fb2b4ee006c35c2494bccdb0b7cae8` adds the separate
`packages/midas/frontier/fx.py` scenario engine and
`POST /api/frontier/opportunities/funding-currency-sensitivity`. The route
reloads a saved replay by run ID and result hash, applies held-source filtering,
and requires exactly one assumption for every venue in the selected candidate.
It performs no source request, store mutation, account lookup, or Arena
submission. User assumptions include each full settlement-asset identity, a
nonnegative venue-local balance, a positive rate in target settlement units per
funding unit, and a conversion fee below 10,000 bps.

For target capital `S`, rate `r`, fee `f` bps, and balance `B`, required funding
is `S / (r * (1 - f/10000))`; target value available after fees is
`B * r * (1 - f/10000)`; and the modeled fee is `S * f / (10000 - f)` in
target units. Exact identity permits only the canonical rate 1 and fee 0.
Fiat and network-specific token identities remain distinct even when tickers
match. The UI starts rate and fee inputs blank when identities differ. Each
venue stays isolated. The response carries deterministic input/result hashes,
an independent Fraction audit, uncovered virtual funding per venue, and the
count of candidate legs whose fees remain unknown. Candidate classification,
practical eligibility, and P&L are unchanged. The modeled conversion fee is not
subtracted from candidate P&L.

Implementation files in commit `530c9aa8b3fb2b4ee006c35c2494bccdb0b7cae8`:
`packages/midas/frontier/fx.py`, `apps/api/frontier.py`,
`apps/web/src/Frontier.tsx`, `apps/web/src/frontier.css`,
`apps/web/src/Frontier.test.tsx`, `tests/frontier/test_api.py`, and
`tests/frontier/test_fx_sensitivity.py`. Test-only commit
`87c67b23fbda1624a6b36273b63cd94427113b4c` extends the FX unit file with
oversized-input rejection cases. The documentation checkpoint changes
`docs/DEVELOPMENT.md`, `docs/MIDAS_CURRENT_STATE.md`,
`docs/frontier/FRONTIER_ARCHITECTURE.md`,
`docs/frontier/FRONTIER_OPERATIONS.md`,
`docs/frontier/FRONTIER_ENGINEERING_REPORT.md`, and
`docs/frontier/FRONTIER_MISSION_LEDGER.md`.

Two verification defects were found and fixed before the checkpoint. The first
test run caught the independent fee total using Python's default 28-digit
Decimal context; the audit now sums at the model's 96-digit context. Thirty
bounded generated combinations of rates, fees, and balances then exposed a
last-digit shortfall disagreement at a recurring-division boundary. The rational
audit now mirrors the explicit 96-digit rounding point for that derived amount
while deciding coverage from exact rational inputs. Before the size-bound
follow-up, the focused Python selection passed **39 tests** in 1.63 seconds. The
final focused selection passed **40 tests** in 1.26 seconds, including capital
carry regression, saved-run API integration and FX API hash rejection, plus the
new 30-example generated audit property, and oversized balance/candidate amount
rejection. Test follow-up commit `87c67b23fbda1624a6b36273b63cd94427113b4c`
adds the size-bound regression. The existing Starlette/httpx
TestClient deprecation warning remains.

The focused Mission Control test file passed **8/8** in 4.23 seconds. It checks
asset-identity input, requires a user-entered rate and fee for a different
identity, rejects exponent-form balance text before submission, confirms the
saved-run request body, shows unresolved candidate fees, and keeps economics
unchanged. TypeScript and the Vite production build passed. The build reports a
544.41 kB Chart chunk advisory; the new Frontier chunk is 135.35 kB. Targeted
ESLint, Prettier, Ruff, Ruff formatting, `git diff --check`, strict mypy for
`fx.py`, and strict API-module mypy with the existing `no-any-return` check
suppressed all pass. Unsuppressed strict API-module mypy still reports that
pre-existing adapter-lookup return at `apps/api/frontier.py:1052`; the new
funding route has no additional typing error.

No Playwright run, full Frontier suite, CPU/memory profile, public FX source, or
live cross-venue relationship was produced for this checkpoint. At
`2026-10-28T00:20:21Z`, memory PSI avg10 was **45.09% some / 39.20% full**,
available memory was **10,087 MiB**, and swap use was **3,768 MiB** while the
external Veritas gap-detail batch PID **3960724** remained active. That batch
was not interrupted. No Reality process, protected service, source capture,
Arena worker, production store, or deployment was touched.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Virtual funding-currency model and independent audit | COMPLETE AND VERIFIED | Offline API/unit fixtures cover namespaced identities, deterministic hashes, venue isolation, bounds, tampering, exact coverage, and 30 generated Decimal/Fraction cases. No conversion availability or FX observation is established. |
| Saved-run funding API | COMPLETE AND VERIFIED | Run/result hash binding, held-source filter, exact candidate/venue matching, classification/eligibility/P&L invariance, and stale-hash rejection pass a fixture-backed API test. |
| Mission Control funding workbench | PARTIALLY VERIFIED | Component test, typecheck, lint, and production build pass. No Playwright browser check was admitted under the current host pressure. |
| Live FX and cross-venue funding/transfer evidence | DEFERRED | No FX source or account/transfer path is integrated; all rates and balances are user assumptions. |
| Project Frontier overall | PARTIALLY VERIFIED | Live multi-venue validation, full regression, browser acceptance, resource sustainability, and production deployment remain incomplete. |

Continue with bounded offline acceptance. Do not promote user-entered conversion
scenarios to sourced exchange economics or executable capital availability.

### Funding-currency browser acceptance and Frontier regression — 2026-10-28

Commit `86b79fe10b6aed82dabbe3e40ea01e08923ad744` extends
`apps/web/e2e/frontier.spec.ts`. The pinned candidate fixture changes Kalshi's
funding identity from USD to EUR, confirms that the FX rate and conversion-fee
inputs start empty, submits explicit values for Kalshi and a separate USD
balance for Polymarket, and checks the response leaves the saved candidate's
classification and practical eligibility unchanged. The first E2E attempt
found a test-selector ambiguity because both venue rows correctly displayed
the unresolved-fee notice. The assertion was corrected to require both rows;
the targeted test then passed, followed by the full configured browser suite.

Verification on 2026-10-28:

- `env PYTHONPATH=packages:.:tests /usr/bin/time -v /home/charlie/midas/.venv/bin/pytest tests/frontier -q`: **322 passed**, 1 existing Starlette/httpx deprecation warning, 50.72 seconds pytest time / 52.04 seconds wall, **364,312 KiB peak RSS**, zero swaps, zero socket messages.
- `corepack pnpm test` in `apps/web`: **40 passed** across 7 files in 5.32 seconds.
- `corepack pnpm exec playwright test --workers=1` in `apps/web`: **12 passed** in 27.4 seconds. Playwright starts isolated demo API/web services and temporary databases; the FX response is an explicit browser fixture, while the saved-run endpoint is covered separately by the Python API tests.
- Prettier, ESLint for the modified E2E file, `git diff --check`, and the earlier build/typecheck passed. No production frontend build was rerun because this checkpoint changed only E2E code.

At `2026-10-28T00:27:27Z`, after these bounded tests, memory PSI avg10 was
**17.09% some / 11.86% full**, MemAvailable was **9,858,420 KiB**, and
SwapFree was **335,952 KiB**. This single run does not establish resource
sustainability. The E2E suite used no exchange endpoint, production database,
protected Reality process, or deployment. No Arena campaign or long-running
worker was started.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Frontier Python regression | COMPLETE AND VERIFIED | 322 tests pass, including adapter, relationship, replay, API, and funding-currency coverage; full repository tests are outside this result. |
| Mission Control and browser regression | PARTIALLY VERIFIED | All 40 web unit tests and 12 configured E2E tests pass. The funding-currency response is fixture-intercepted in browser; the API is independently fixture-tested. No live FX source is connected. |
| Resource sustainability | PARTIALLY VERIFIED | This test run measured 364,312 KiB peak Python RSS and zero swaps; longer concurrency, steady-state collection, and production admission remain unmeasured. |
| Live cross-venue economics and deployment | DEFERRED | Source permission, synchronized venue evidence, FX availability, transfers, and production transition remain unresolved. |
| Project Frontier overall | PARTIALLY VERIFIED | The offline research implementation has broad passing regressions; genuine live cross-venue validation and deployment gates remain open. |

### Strict API typing retry deferred — 2026-10-28 00:31 UTC

A scoped strict mypy retry for `apps/api/frontier.py` was attempted after
reviewing its existing `registry: Any` parameter and adapter-lookup
`no-any-return` diagnostic. A temporary concrete `AdapterRegistry` annotation
was removed when the check failed to finish. The process ran for 25.34 seconds
at 99% CPU and reached **694,744 KiB peak RSS** without a type result; only that
mypy process was stopped. It used zero swaps and left no source change.

During the check at `2026-10-28T00:31:15Z`, memory PSI avg10 was **24.98% some
/ 19.55% full**, MemAvailable was **9,799,260 KiB**, and the external Veritas
gap-detail batch PID **3975405** was active. It was not touched. The strict API
typing caveat remains unresolved; retry when shared-host pressure subsides.

## Current mission acceptance matrix — 2026-10-28 03:13 UTC

This matrix assesses the user-requested Frontier stages and scientific
acceptance against current branch evidence, not intent or planned work.

| Requirement | Status | Current evidence and remaining gap |
| --- | --- | --- |
| Isolated baseline and exchange-independent adapter foundation | COMPLETE AND VERIFIED | Branch `codex/frontier-20261026` is based on the verified V6 integration commit in a separate worktree. Shared capability contracts, registry, source-specific adapters, bounded transport, and compatibility tests pass in the Frontier suite. |
| Polymarket, Kalshi, Kraken, and Coinbase read-only adapters | PARTIALLY VERIFIED | Adapters are implemented and contract/fixture tested; selected historical Polymarket, Kalshi, and Kraken public responses were captured. Kalshi and Kraken remain held, Coinbase remains held pending exact terms-scope validation, and no fresh live validation is claimed. |
| Canonical instruments, precise denominations, and supported payoff semantics | PARTIALLY VERIFIED | Versioned models preserve native IDs, identities, outcomes, payoff rules, constraints, and provenance; binary, one-hot multi-outcome, and bounded same-market constant-payout basket evaluators reject unsupported or incompatible semantics. Spot remains contextual unless a supported payoff link is proved. Broader instrument families are not supported. |
| Relationship graph, evidence, persistence, and bounded exploration | PARTIALLY VERIFIED | Deterministic proposals, explicit verification states, append-only review evidence, held-source filtering, and revision-pinned neighborhood/search pages have API and UI coverage. No genuine verified cross-venue economic match exists; reviewer identities and external assertions are not authenticated. |
| Opportunity families and independent economic verification | PARTIALLY VERIFIED | Binary coverage, bounded one-hot coverage, directed implication, within-market constant-payout subsets, and multi-market joint-state baskets have independent arithmetic checks. The new joint-state path accepts two to four stored open markets, up to twelve instruments, and a content-hashed external assertion of two to sixty-four shared states; it searches at most 4,095 subsets. Focused replay/API and independent-audit fixtures pass. The audit proves arithmetic only over the asserted map; it cannot authenticate the event composition or establish the map's semantics. No live positive or economically eligible opportunity is established. |
| Venue costs, capital, and currency assumptions | PARTIALLY VERIFIED | Public fee metadata, bounded fee/carry sensitivities, partial-fill stress, venue-separated virtual balances, and a separate conversion-adjusted terminal-P&L scenario exist. The P&L scenario requires verified candidate/funding audits, complete candidate leg fees, and sufficient per-venue balances; it never mutates candidate economics. Account-specific fees, sourced FX, cross-venue transfer/custody, settlement risk, and conversion availability remain unknown. |
| Isolated collection, provenance, durable storage, and deterministic replay | PARTIALLY VERIFIED | Finite restartable collection, append-only hash-chained checkpoints, a read-only keyset-paginated run catalog across the 1,000-run journal bound, bounded storage, event-time replay, source-health evidence, and replay provenance are implemented and tested offline. No continuous market-data stream, full source-history backfill, or long-horizon source-quality study is established. |
| Laboratory/Arena research integration | PARTIALLY VERIFIED | Bounded replay jobs, paired comparisons, content-addressed discovery artifacts, and integrity-checked APIs exist. One synthetic discovery job passed real host-wide admission and completed in an actual transient user systemd unit under `MemoryMax=512M`, `MemorySwapMax=0`, `CPUQuota=50%`, and AF_UNIX-only networking; its artifact passed hash verification. The corrected serial Frontier/selected-Arena regression passes 383/383, including command-assembly checks isolated from host lock state. This is one short supervised fixture run and a bounded regression, not sustained, concurrent, or production service validation. No long-duration campaign or production worker is authorized. |
| Native Frontier Mission Control interface | IMPLEMENTED, DEPLOYMENT PENDING | The full web suite last passed 40/40; the current candidate-detail UI also passes its focused component test, fixture browser flow, TypeScript, and Vite production build. The detail view preserves decimal strings, matches candidates to their scope summaries, caps display at 50 per scope, and labels terminal P&L as hypothetical without fills or realized profit. Browser artifact data is intercepted fixture content on loopback demo services. The build retains the existing 544.41 kB Chart chunk advisory. No live source data or production deployment occurred. |
| Scientific acceptance: normalization, rejection, controlled discrepancy, independent arithmetic, missing/stale/asynchronous evidence, and deterministic replay | PARTIALLY VERIFIED | The corrected serial Frontier/selected-Arena regression passes 383/383, including 48 seeded differential cases against an independent exhaustive oracle. The web suite passes 40/40 on the candidate-inspection checkpoint; the latest disclaimer adjustment passes its focused component and browser tests and production build. Evidence still does not establish a genuine cross-venue relationship, authenticated state composition, synchronized executable quotes, or positive economics. |
| Resource sustainability under bounded development workloads | PARTIALLY VERIFIED | The full Frontier Python suite previously reached 366,360 KiB peak RSS; the Vite build previously reached 713,040 KiB; and the corrected combined regression reached 377,372 KiB peak RSS with zero swaps and socket messages. One real systemd discovery unit recorded MemoryMax 512 MiB, swap max zero, 50% CPU quota, cgroup MemoryPeak 117,252,096 bytes, and worker process peak RSS 170,110,976 bytes; those high-water measurements differ and are not reconciled. The synthetic 12-instrument/64-state search evaluated 4,095 subsets; three one-candidate runs measured 0.101767 seconds median / 0.104521 seconds maximum at 70,576 KiB peak RSS, with an eight-candidate run at 0.174308 seconds / 71,460 KiB. Sustained collection, concurrency, and broad latency/CPU behavior remain unmeasured. At 03:12:36 UTC after the regression, memory PSI avg10 was 34.89% some / 32.22% full; defer further resource-bearing checks until external admission releases and a fresh gate passes. |
| Read-only research boundary and source-use gates | COMPLETE AND VERIFIED | No trading/authenticated exchange path is provided; source-policy tests ensure held venues return 409 without requests and held evidence stays quarantined. This does not grant permission to use a held source. |
| Required architecture, operations, current-state, report, and continuation documentation | COMPLETE AND VERIFIED | The engineering report, architecture, operations guidance, current-state note, source terms review, and append-only mission ledger record implementation, evidence, blockers, and continuation actions. |
| Production deployment | DEFERRED | Requires separate source permission, resource/storage/recovery review, full deployment-scope regression, monitoring/rollback preparation, and explicit authorization. |
| Genuine cross-venue validation using currently held sources | BLOCKED | The current source-use review blocks new Kalshi/Kraken research and keeps Coinbase held pending a resolved terms scope. Polymarket research access alone cannot establish cross-venue equivalence. Continue offline work; do not bypass the holds. |

Across the 14 scientific criteria, deterministic fixtures establish the
supported normalization, rejection, arithmetic, missing/stale-data, persistence,
and replay mechanisms. Cross-venue live matching and fully modeled execution
economics remain unproven. Zero eligible opportunities is an honest outcome;
it is not a claim that the opportunity question has been settled.

The scoped API type check now passes after host pressure subsided. Continue
offline acceptance; live cross-venue work remains gated on a validated
source-use decision, and deployment remains a separately authorized activity.

### Funding-adjusted terminal-state P&L — 2026-10-28 00:47 UTC

Code commit `71ee203b033c4bc0f38afce09b5255fe31bcae21` closes a gap in the
virtual funding sensitivity: it previously reported conversion costs without
applying them to outcome economics. Schema/model version 2 now includes a
separate `pnl_scenario`. The input digest binds the saved run and candidate,
candidate independent-audit identity and terminal P&L, per-leg modeled-fee
completeness, venue capital, and user assumptions. A separate `Fraction`
calculation recomputes the fee and subtracts it from every terminal state.

The scenario is **verified** only if the saved candidate audit and funding
conversion audit verify, every candidate leg has a modeled fee, the candidate
P&L agrees with its independent audit, and all virtual balances cover their
venue-local requirements. Missing prerequisites return **unavailable**;
inconsistent P&L or arithmetic returns **disagreement**. Neither state exposes
adjusted terminal values. The result never modifies the saved candidate's P&L,
classification, or practical eligibility. The API reads only the hash-pinned
saved candidate and makes no exchange request or database write. The UI renders
both verified state values and the unavailable explanation.

Files in `71ee203`: `packages/midas/frontier/fx.py`,
`tests/frontier/test_fx_sensitivity.py`, `tests/frontier/test_api.py`,
`apps/web/src/Frontier.tsx`, `apps/web/src/Frontier.test.tsx`, and
`apps/web/e2e/frontier.spec.ts`.
The documentation checkpoint updates `docs/frontier/FRONTIER_ARCHITECTURE.md`,
`docs/frontier/FRONTIER_OPERATIONS.md`, `docs/frontier/FRONTIER_MISSION_LEDGER.md`,
`docs/DEVELOPMENT.md`, `docs/MIDAS_CURRENT_STATE.md`, and this report.

Verification on the isolated worktree:

- `pytest tests/frontier -q`: **325 passed** in 50.39 seconds; **51.73 seconds
  wall**, **365,976 KiB peak RSS**, zero swaps, and zero socket messages. One
  existing Starlette/httpx deprecation warning remains.
- Focused funding sensitivity and saved-run API selection: **16 passed** in
  1.14 seconds; `/usr/bin/time -v` measured **82,756 KiB peak RSS**, zero swaps,
  and zero socket messages.
- Web unit suite: **40 passed** across seven files. This covers the panel's
  verified and unavailable display states.
- `tsc -b`, scoped ESLint, Prettier, Ruff check/format, and strict scoped mypy
  for `packages/midas/frontier/fx.py` passed.
- `playwright test e2e/frontier.spec.ts --workers=1`: **4 passed** in 11.7
  seconds using the isolated demo API/web services. The funding response is a
  fixture; the saved-run Python API test independently exercises the verified
  P&L scenario.
- Vite production build passed in 4.69 seconds. It still reports the existing
  544.41 kB Chart-chunk size advisory.

The first updated web-unit run caught an old assertion that counted two `red`
labels; the verified P&L panel correctly adds a third state label. The selector
was updated and all **40** web tests passed. No real FX data, source endpoint,
account, wallet, protected Reality process, production database, or deployment
was used. The fixture verifies arithmetic and UI behavior; it does not establish
live convertibility, transfer availability, executable quotes, or profitability.

| Component | Status | Evidence and boundary |
| --- | --- | --- |
| Virtual conversion-adjusted outcome P&L | COMPLETE AND VERIFIED | Saved-run API, rational differential checks, incomplete-fee/balance rejection, tampered candidate-P&L rejection, and UI verified/unavailable states pass. Still entirely assumption-driven. |
| Funding-currency web/API workflow | COMPLETE AND VERIFIED | Version 2 API contract, full web suite, Frontier browser spec, TypeScript, lint, and production build pass. Browser source response is fixture-intercepted. |
| Live FX, conversion and cross-venue capital access | DEFERRED | No FX observation, account balance, transfer, jurisdiction, custody, collateral, or conversion availability is sourced. |
| Project Frontier overall | PARTIALLY VERIFIED | Other scientific and source-use gaps in the current matrix remain open; there is no genuine verified cross-venue match or production deployment. |

Continue offline engineering from the current mission matrix. Do not treat a
positive fixture result as evidence of a live opportunity or as permission to
use held sources.

### Collection API checkpoint integrity and 328-test regression — 2026-10-28 00:55 UTC

Commit `780575c` adds a route-level integrity check for finite collection
history and resume. The test creates a valid paused run in a temporary journal,
simulates a low-level payload-only disk alteration while restoring the SQLite
append-only trigger, and leaves the original checkpoint digest in place. Both
HTTP history and resume surface a bounded 409 integrity error; the fake adapter
records no request. This verifies the API preserves the collection journal's
hash-chain rejection behavior at its external read-only boundary.

Together with code commit `4ba723f`, three API tests now cover reconstructed
process recovery from a pending observation without rediscovery, held-source
history/start/resume quarantine, and tampered checkpoint rejection. The
complete serial Frontier suite includes these cases.

Verification on the isolated worktree:

- `pytest -q tests/frontier`: **328 passed** in 51.45 seconds pytest time and
  **52.82 seconds wall**. `/usr/bin/time -v` measured **367,868 KiB peak RSS**,
  zero swaps, zero socket messages, zero major page faults, and 35% CPU use. One
  existing Starlette/httpx deprecation warning remains.
- The focused collection API selection passed **3/3** in 1.81 seconds.
  Ruff check/format and `git diff --check` passed.
- Post-run host memory PSI was **0.01% avg10** for both `some` and `full`, with
  about **10 GiB available** and **3.7 GiB swap in use**. The result supports
  this bounded serial suite; it does not demonstrate sustained or concurrent
  production capacity.
- No exchange endpoint, held source, Reality process, external worker,
  production store, or deployment was used.

| Component | Status | Evidence and boundary |
| --- | --- | --- |
| Collection API restart, quarantine, and tamper rejection | COMPLETE AND VERIFIED | Three route-level fixture tests fail closed without new adapter calls; low-level corruption exists only in a temporary test database. |
| Current Frontier Python regression | COMPLETE AND VERIFIED | 328 tests pass on this revision. Web/browser acceptance is not part of this Python suite. |
| Project Frontier overall | PARTIALLY VERIFIED | Genuine cross-venue validation, held-source live capture, long-horizon source quality, and deployment remain incomplete. |

Continue offline acceptance from the mission matrix. These fixture results do
not establish a live cross-venue opportunity or authorize use of held sources.

### HTTP collection recovery across reconstructed API instances — 2026-10-28 00:53 UTC

Two route-level tests now cover the durable collection lifecycle across
reconstructed API state. The recovery test starts a fixture-backed finite
Polymarket collection and injects a one-time local persistence interruption,
which leaves a pending market capture in a paused checkpoint. It closes the
original test client and registry, constructs a new API app, registry, adapter,
and `FrontierStore` over the same temporary journal, and resumes by run ID. The
run completes from its persisted pending observation with zero requests from
the reconstructed adapter and zero rediscovery calls. History exposes the
checkpoint digest and correct resumability state; a terminal retry returns the
same result without a request.

The quarantine test seeds a paused Kalshi run in a temporary journal while
`hold_sources=True`. The history API omits the held run, and both start and
resume return 409 before adapter requests or journal mutation. This validates
the API boundary with local synthetic metadata only; it does not access or
authorize the held source.

Verification on the isolated worktree:

- The two focused collection-history/recovery/quarantine tests passed in 1.66
  seconds. Ruff check/format and `git diff --check` passed.
- The broader Frontier suite was not rerun after these tests were added. The
  preceding host sample showed memory PSI avg10 at 43.18% some / 39.51% full,
  9.8 GiB available, and 3.7 GiB swap in use. Broad regression remains pending
  a fresh admission check after pressure subsides.
- No exchange endpoint, protected service, external worker, production store,
  or deployment was used. The repository changes are limited to
  `tests/frontier/test_api.py` and this documentation checkpoint.

| Component | Status | Evidence and boundary |
| --- | --- | --- |
| HTTP collection recovery across reconstructed app/registry/store | COMPLETE AND VERIFIED | Fixture-backed restart resumes the pending observation without rediscovery; terminal retry is idempotent. |
| Held-source collection history/start/resume API gates | COMPLETE AND VERIFIED | A held Kalshi journal entry is hidden, and start/resume reject before fake network calls or journal mutation. |
| Full Frontier suite after these tests | PARTIALLY VERIFIED | The prior 325-test suite predates the two new tests; focused checks pass. Rerun only after resource pressure is remeasured. |

Continue bounded offline acceptance. Keep all held sources quarantined and the
production transition separate.

### Strict Frontier API registry typing — 2026-10-28 00:35 UTC

Commit `480ba629171c855086cd375a34e688bbc72fdbcb` changes the
`apps.api.frontier.router` parameter from `Any` to the concrete
`AdapterRegistry`. Its typed `get` method returns `ExchangeAdapter`, so strict
mypy no longer reports `no-any-return` at the registered-adapter boundary.
This does not change API behavior or initiate network activity.

Verification: `MYPYPATH=packages /home/charlie/midas/.venv/bin/mypy --strict
--follow-imports=silent apps/api/frontier.py` passed with no issues in one
source file. `/usr/bin/time -v` measured 27.22 seconds wall, 717,964 KiB peak
RSS, zero swaps, and zero socket messages. Ruff check and format check passed.
The API overview route regression passed **1/1** in 0.70 seconds; peak RSS was
**77,492 KiB**, with zero swaps/socket messages and one existing
Starlette/httpx deprecation warning. At the 00:34:53 UTC sample, memory PSI
avg10 was 0.11% some / 0.10% full and MemAvailable was 9,913,344 KiB. The
previous full Frontier/web/browser suites were not rerun because this change
only narrows a router parameter type; the focused test confirms startup and
router construction.

The earlier 00:31 deferred attempt was stopped at 694,744 KiB while the external
batch was active. That attempt changed no code; after the batch ended, the
validated type change was committed. No external batch, protected service,
exchange, or production store was modified.

### Cursor-paginated finite collection history — 2026-10-28 01:07 UTC

Code commit `067b2ce` lets operators inspect the retained finite collection
journal beyond its newest 20 entries. The history API accepts an optional
`before_run_id`; when more rows exist it returns `next_before_run_id` as the
last visible run ID. The next request resolves that anchor from the append-only
run table, checks its pinned spec hash and complete checkpoint chain, then reads
older entries. Page selection uses a read-only SQLite transaction for a
consistent view and scans at most the journal's 1,000-run bound in 64-row
batches. Every returned run still gets complete chain verification. The code
never creates a missing journal or calls an adapter. Appending a newer run
between page requests does not shift the older page anchor.

The storage regression inserts one visible Polymarket run, 65 held Kalshi runs,
and another visible Polymarket run. A two-item page scan must cross the 64-row
batch boundary, omit all held entries, and return both visible runs in order.
The API test walks three pages, appends a newer run between page requests, and
confirms no duplicate or missing older entries; malformed and unknown cursors
fail closed. Mission Control exposes shared “Load older runs” and “Newest runs”
controls and resets to the newest page after collection start or resume.

Files changed by `067b2ce`: `packages/midas/frontier/collection.py`,
`apps/api/frontier.py`, `tests/frontier/test_collection.py`,
`tests/frontier/test_api.py`, `apps/web/src/Frontier.tsx`,
`apps/web/src/Frontier.test.tsx`, `apps/web/src/frontier.css`, and
`apps/web/e2e/frontier.spec.ts`.

Verification on the isolated worktree:

- `pytest -q tests/frontier`: **330 passed** in 52.85 seconds pytest time and
  **54.20 seconds wall**. `/usr/bin/time -v` measured **365,832 KiB peak RSS**,
  zero swaps, zero socket messages, zero major page faults, and 35% CPU use. One
  existing Starlette/httpx deprecation warning remains.
- The full web unit suite passed **40/40** in 15.86 seconds. The Frontier
  browser spec passed **4/4** in 12.0 seconds against isolated services.
- `tsc -b`, the Vite production build, scoped ESLint/Prettier, strict mypy for
  `apps/api/frontier.py` and `packages/midas/frontier/collection.py`, Ruff, and
  `git diff --check` passed. Vite retains the existing 544.41 kB chart-chunk
  advisory.
- Tests used fixture stores or isolated local services; no exchange, held
  source, protected Reality process, external worker, production store, or
  deployment was used.

| Component | Status | Evidence and boundary |
| --- | --- | --- |
| Retained finite collection history catalog | COMPLETE AND VERIFIED | Keyset pages cover up to 1,000 retained runs with a consistent read snapshot, chain-verified cursor anchors, bounded 64-row scans, and held-source filtering. No market-data backfill or continuous stream is added. |
| Exchanges collection history UI | COMPLETE AND VERIFIED | Full web unit suite, 4-test Frontier browser spec, TypeScript, and production build pass. Browser services are isolated. |
| Current Frontier Python regression | COMPLETE AND VERIFIED | 330 tests pass on code commit `067b2ce`; the broad scientific and source-use limitations in the current matrix still apply. |
| Project Frontier overall | PARTIALLY VERIFIED | Genuine cross-venue relationship validation, live research behind current holds, broader multi-leg discovery, long-horizon source quality, and production deployment remain incomplete. |

Continue offline acceptance from the current mission matrix. Do not infer live
opportunity economics from fixtures or treat collection pagination as
historical market-data coverage.

## Bounded event payoff-basket search — 2026-10-28 01:20 UTC

Commit `d16259422902bc4acd75cb45e0ced6eb8e186904` adds an additive candidate
family for a verified exhaustive multi-outcome event market whose contract
payoffs overlap or otherwise differ from one-hot outcomes. The candidate
generator enumerates subsets of at most twelve instruments (4,095 non-empty
subsets), across three to sixteen terminal states. A basket qualifies only if
all selected nonnegative payoff vectors add to the same positive payout in
every state, all legs use one quantity unit, and the payout settlement identity
is exact. Candidate search returns eight ranked results by default and enforces
a hard caller cap of 32. It does not infer contract semantics from labels.

The selected long legs use one common quantity from aligned step/depth bounds.
The evaluator then applies the existing exact quote-unit, price-tick, fee,
slippage, freshness, timing, capital, and fill-sensitivity checks. Contract
asks above their maximum verified state payout fail closed. Practical
eligibility remains false. Deterministic replay version 14 preserves the
existing one-hot path and invokes the new family only for other verified
multi-outcome payoff structures. Economic model version 14 pins candidate
identity. Independent audit version 11 separately checks the selected
contracts, common quantity, complete state vectors, constant positive payout,
quotes, fees, costs, terminal P&L, fill exposure, and classification.

A controlled fixture uses three overlapping binary-payoff vectors whose sum is
exactly USD 2 per contract in each of three states. At the fixture depth of ten
contracts, the model recomputes USD 20 payout per state against USD 7.50 quoted
cost, for USD 12.50 gross P&L. This is synthetic test arithmetic only; it is
not an observed market, source-backed opportunity, or economic finding. The
independent audit verifies all three legs and rejects the same candidate after
one leg is removed. A separate fixture with no constant-payout subset returns
no candidate.

After the implementation, `tests/frontier/test_relationships_economics_replay.py`
and both multi-outcome and payoff-basket replay API regressions passed **51
tests** in 2.00 seconds. The complete serial Frontier suite then passed **332
tests** in 52.98 seconds pytest time / **54.32 seconds wall**. Peak RSS was
**369,040 KiB**, with zero swaps, socket messages, or major page faults and 35%
CPU use. One existing Starlette/httpx deprecation warning remains. Strict mypy
passed for `economics.py`, `independent_audit.py`, `models.py`, and `replay.py`;
scoped Ruff check/format and `git diff --check` passed. The focused Mission
Control test passed **1/1** for the new candidate-family label, and the API
fixture verifies persistence/listing without adapter requests. The separate
maximum-bound synthetic subset benchmark is recorded below; its deliberately
uniform payoff vectors do not establish representative market-workload
performance.

Reproduction commands:

```bash
PYTHONPATH=packages /home/charlie/midas/.venv/bin/python -m pytest -q tests/frontier/test_relationships_economics_replay.py tests/frontier/test_api.py::test_replay_api_generates_and_persists_multi_outcome_candidate tests/frontier/test_api.py::test_replay_api_generates_and_persists_bounded_payoff_basket
corepack pnpm --dir apps/web exec vitest run src/Frontier.test.tsx -t 'renders recorded-evidence empty states and never probes a source automatically'
PYTHONPATH=packages /home/charlie/midas/.venv/bin/python -m pytest -q tests/frontier
```

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Bounded within-market payoff-basket candidate generation | COMPLETE AND VERIFIED | Exact 3-leg overlapping payoff fixture, deterministic replay, no-coverage rejection, strict bounds, and independent audit are covered by the focused regression. No public source record currently establishes this verified payoff structure. |
| General multi-market joint-state search | DEFERRED | The new family uses one market's own exhaustive payoff state space; it does not compose arbitrary events or infer joint state spaces across venues. |
| Project Frontier overall | PARTIALLY VERIFIED | Live cross-venue validation, source-use holds, broader source-quality evidence, general multi-market search, and production deployment remain unresolved. |

Continue offline acceptance. Keep held sources unchanged, preserve the
research-only boundary, and treat the synthetic gross result as a unit test
only.

## Bounded payoff-basket ceiling benchmark — 2026-10-28 01:22 UTC

Benchmark harness commit `447c85a` adds
`tests/frontier/benchmark_payoff_basket_search.py`; `c1c58ad` makes the
synthetic all-state labels and verification basis explicit. It creates a
controlled 16-state market with twelve instruments, each paying one unit in
every state, and one displayed ask per leg. Thus all **4,095** non-empty subsets satisfy the
constant-payout property, forcing the enumerator to traverse its maximum subset
count. It asks for the configured maximum of 32 ranked candidates and confirms
32 results on warm-up and on each measured iteration.

Command:

```bash
PYTHONPATH=packages:. /usr/bin/time -v /home/charlie/midas/.venv/bin/python tests/frontier/benchmark_payoff_basket_search.py
```

On this host, the five measured calls after warm-up took **0.344171 seconds
median** and **0.355593 seconds maximum**. The complete process, including
setup, warm-up, and all measured calls, took **2.37 seconds wall** and reached
**49,792 KiB peak RSS**. It used 100% CPU, with zero swaps, socket messages, or
major page faults. The benchmark and Ruff check/format passed. It used only
controlled fixtures: no network, exchange, store, or production data was
accessed.

This is a synthetic enumeration ceiling, not a typical or representative
market distribution: its identical all-state payoff vectors are designed to
make every subset qualify. The measurement is specific to this host and run;
it does not establish latency or memory under a live feed, mixed market sizes,
concurrency, sustained collection, or production limits. Broader multi-market
search remains unsupported.

## Varied payoff-basket and current frontend verification — 2026-10-28 01:27 UTC

Benchmark harness commit `8f2d22fa7bc37ac806d070403d122d941dc226a8` extends
the synthetic search benchmark to four declared shapes. Each run has one warm-up
and five timed iterations. The observed medians and maximums were:

| Fixture | Instruments / states | Enumerated subsets | Qualifying / returned | Median / maximum |
| --- | ---: | ---: | ---: | ---: |
| Single basket | 3 / 3 | 7 | 1 / 1 | 0.000928 / 0.000991 sec |
| Eleven baskets | 12 / 16 | 4,095 | 11 / 11 | 0.091870 / 0.099176 sec |
| No basket | 12 / 16 | 4,095 | 0 / 0 | 0.072525 / 0.074176 sec |
| Dense ceiling | 12 / 16 | 4,095 | 4,095 / 32 | 0.343868 / 0.355242 sec |

The fixtures use explicit synthetic payout vectors. `single-basket` is the
three overlapping-vector construction; `eleven-baskets` uses eleven claims
covering one state plus one complementary claim; `no-basket` repeats one
single-state claim; and `dense-ceiling` uses all-state claims. The complete
four-case process took **3.37 seconds wall**, reached **50,640 KiB peak RSS**,
used 99% CPU, and incurred zero swaps, major faults, or socket messages. This
isolates enumeration and bounded candidate construction; it is not a
representative venue workload. Reproduce with the benchmark command above.

The full web unit suite passed **40/40** in **5.99 seconds wall**, with
**310,652 KiB peak RSS**. The Frontier Playwright spec passed **4/4** in
**12.60 seconds wall**, with **192,060 KiB peak RSS** and zero swaps. Playwright
started only loopback demo services using temporary storage. A pre-run host
sample showed 10,778,132,480 bytes available, memory PSI `avg10=0.00`, and
3,949,416,448 bytes of swap in use; neither measured test process swapped.
The user-slice cgroup had no configured memory high/max value. These short runs
do not establish sustained or concurrent service capacity.

Project Frontier remains **PARTIALLY VERIFIED**. In particular, general
multi-market joint-state composition and corresponding independent audit are
not implemented; current cross-market families remain pairwise, and their
semantic evidence and current source-use holds constrain live validation.

## Production web build after payoff-basket UI change — 2026-10-28 01:29 UTC

`corepack pnpm --dir apps/web build` completed successfully on the current
worktree. It ran `tsc -b` and Vite 7.3.7, transforming **2,228 modules** and
producing the production bundle in **4.65 seconds** (12.93 seconds process wall
time). `/usr/bin/time -v` measured **647,704 KiB peak RSS**, zero swaps, zero
major faults, and zero socket messages. The only build diagnostic was the
existing chart chunk advisory: `Chart-CMyjNNXf.js` is **544.41 kB** minified,
above Vite's 500 kB warning threshold. The build was local and isolated; no
deployment or service transition occurred.

The current web unit suite (**40/40**) and Frontier browser spec (**4/4**) also
pass after the payoff-basket UI update. The browser run used loopback demo
services and temporary database/workspace roots. This verifies current
frontend tests, types, and production compilation; it does not establish
production deployment, operational capacity, live source behavior, or overall
Frontier completion. General multi-market joint-state composition and its
independent arithmetic audit remain unimplemented.

## Conditional multi-market joint-state baskets — 2026-10-28 02:03 UTC

Code commit `4bd3b7f2636d5cd8d069fb2e2b2e97188ad68247` adds an all-long
constant-payout search across two to four stored open event markets. The input
is a bounded, explicit projection from two to sixty-four externally named
shared states to each selected market's local outcomes. A validated model
normalizes the map before computing its canonical SHA-256 ID, and replay pins
both its definition and digest. The calculator considers at most twelve
instruments and 4,095 subsets; it retains candidate legs in each market's
native quantity unit. It requires verified exhaustive payoff and resolution
metadata, identical settlement asset identity and payout currency, and common
future close and settlement timestamps. It does not infer cross-venue unit
conversion or settlement equivalence.

The independent audit is separately implemented and recomputes leg arithmetic
and constant payouts over every mapped state. That verifies the candidate's
calculation relative to the supplied map; it does not verify that the shared
states are semantically correct, exhaustive, or jointly attainable. The map is
an unauthenticated external assertion. Positive results therefore remain
conditional, practical execution eligibility remains false, and no result
establishes a live opportunity.

`POST /api/frontier/replay/joint-state` accepts map definitions but not a
caller-provided identity. It requires stored market observation IDs and saved
public book observations; the assertion timestamp must postdate selected
market metadata. This route performs no network fetch and does not infer
relationships. Held-source filtering remains active. Mission Control's
Replay & Readiness editor requires every projection cell and displays the
conditional classification. The editor request is covered by UI unit tests;
the API is covered by stored-only, malformed, stale-assertion, and persisted
replay tests. Test commit `b0f38c2` adds a Playwright flow using intercepted
fixture observations and response. It verifies the complete request payload
and no-probe behavior; it does not authenticate semantic mapping correctness
or test a live exchange.

Verification on this commit:

| Check | Result | Boundary |
| --- | --- | --- |
| Full Frontier Python suite | **342 passed** in 53.70 seconds pytest time (55.06 seconds process wall), 368,788 KiB peak RSS, zero swaps | One existing Starlette/httpx TestClient deprecation warning. |
| Focused regression | **152 passed** across joint-state, relationship/economics/replay, capital, FX, and API tests | Kept as a direct reproduction of the new integration paths. |
| Full web unit suite | **40 passed** | Includes explicit joint-state form/request assertions. |
| Frontier Playwright | **5 passed** in 13.7 seconds test time (14.52 seconds process wall), 197,060 KiB peak RSS, zero swaps | Includes the explicit joint-state form submission using fixture market metadata and an intercepted research API response; no source request. |
| Production web build | Passed; TypeScript plus Vite 7.3.7 transformed 2,228 modules in 4.76 seconds (13.18 seconds process wall), 713,040 KiB peak RSS, zero swaps | Existing 544.41 kB chart-chunk advisory remains. |
| Static checks | Ruff passed; scoped strict mypy passed for `models.py`, `economics.py`, `joint_economics.py`, `independent_audit.py`, and `replay.py` | A broader mypy invocation surfaced 14 diagnostics in imported pre-existing Veritas/Arena modules and none in the changed Frontier API router. |

No live source, production service, protected recording, or production store
was accessed or changed. No deployment occurred. The full scientific goals
remain partially verified: live cross-venue relationship evidence, semantic
map authentication, cross-venue capital/transfer feasibility, sustained
source quality, and deployment are unresolved.

## Joint-state differential and search performance — 2026-10-28 02:16 UTC

Test commit `29f1a5b` adds a deterministic, seeded 48-case differential test.
Each case builds two binary event-market fixtures, varies exact ask prices, and
uses either identity or flipped local-state projections. A standalone oracle
enumerates all 15 non-empty contract subsets, retains the three constant
positive-payout baskets that span both markets, computes their ranking, and
compares the full ordered identities with the candidate generator. Every
generated candidate is also run through the separate arithmetic audit. The
full Frontier regression then passed **343/343** in 53.88 seconds pytest time
(55.23 seconds process wall), at **366,360 KiB peak RSS**, with zero swaps and
zero socket messages. One existing Starlette/httpx deprecation warning
remains.

The new `tests/frontier/benchmark_joint_state_search.py` measures a synthetic
ceiling case with two markets, twelve instruments, and sixty-four joint states.
Each synthetic instrument pays one unit in every state, and the fixture quotes
each at 0.01. Of 4,095 non-empty subsets, 3,969 span both markets and have a
constant payout. This input intentionally maximizes qualifying baskets; it is
not a source observation, representative book, or economic finding.

On the original implementation before optimization commit `bc8d073`, three
timed one-candidate searches measured a **5.122457 s median** and
**5.147910 s maximum**; the complete process used **38,624 KiB peak RSS**. The
implementation in `bc8d073` now precomputes each instrument's payout vector in
joint-state order, then uses subset dynamic programming to incrementally sum
Decimal payout vectors, ask costs, and market-coverage bits. It adds the
highest-index leg last to keep the prior ascending Decimal addition order.
Ranking, candidate identities, candidate economics, and bounds are unchanged.

After that change, three timed searches returning one candidate measured
**0.101767 seconds median** and **0.104521 seconds maximum**. With
`--max-candidates 8`, one timed search measured **0.174308 seconds**. Process
peak RSS was **70,576 KiB** for the three-repeat run and **71,460 KiB** for the
eight-candidate run; neither swapped. The one-candidate median fell by about
50 times while peak memory rose by about 32 MiB. These measurements cover this
one synthetic host workload only; they do not prove API latency under live
data, concurrency, service memory headroom, or sustained operation.

The initial five-repeat/eight-candidate invocation yielded no captured output
at the 30-second tool boundary, and no benchmark process remained on follow-up.
It is excluded from the measurements. The harness defaults were reduced to
three repeats and one returned candidate; an explicit eight-candidate sample
then completed normally. This preserves a reproducible short default while
still allowing the configured result cap to be measured deliberately.

Verification on this checkpoint: Ruff check and format pass for the changed
Python files; `mypy --strict --follow-imports=silent` passes for
`joint_economics.py`; the 343-test Frontier suite passes. Frontend source did
not change from the preceding **40/40** web, **5/5** Playwright, and production
build checkpoint. No exchange, production service, preserved recording, or
production store was accessed. The project remains **PARTIALLY VERIFIED**;
source permission, genuine cross-venue semantics, long-horizon quality, and
deployment are still open.

## Scoped Frontier type checks closed — 2026-10-28 03:15 UTC

After two fresh Arena admission snapshots each passed the configured 768-MiB
request, strict mypy passed for `packages/midas/frontier/discovery_comparison.py`
and `apps/api/frontier.py`:

```bash
env MYPYPATH=packages /home/charlie/midas/.venv/bin/mypy --strict \
  --follow-imports=silent packages/midas/frontier/discovery_comparison.py
env MYPYPATH=packages /home/charlie/midas/.venv/bin/mypy --strict \
  --follow-imports=silent apps/api/frontier.py
```

The API check took 21.74 seconds. Imported-module diagnostics were suppressed,
so this does not establish repository-wide typing. At `2026-10-28T03:15:11Z`,
memory PSI avg10 was **0.00% some / 0.00% full**, I/O PSI avg10 was **0.62%
some / 0.61% full**, available memory was about **10.1 GiB**, and free swap was
about **333 MiB**. This is a dated point sample only. No code changed during
these checks; no source endpoint, test database, worker, production service,
or protected recording was accessed.

The corrected Frontier plus selected Arena regression remains **383/383** at
**377,372 KiB** peak RSS from its earlier run. The type checks close only the
two scoped modules. Frontier remains **PARTIALLY VERIFIED**, isolated,
research-only, and undeployed; genuine cross-venue equivalence, held-source
live evidence, broader typing, sustained resource evidence, and deployment
remain unresolved.

## Polymarket outcome evidence and bounded rejection diagnostics — 2026-10-28 03:25 UTC

One permitted Polymarket Gamma probe made two public GET requests at one
request per second, with a 7-second timeout, zero retries, and a 256-KiB
response cap. The first `/markets` request returned HTTP 200 with 20 active
markets ordered by liquidity. The immutable local row is stored at
`data/public-captures/frontier-polymarket-20261028T031822Z-pqzzdf1m/frontier.sqlite3`
and its read-back was checked:

| Evidence | SHA-256 / identity |
| --- | --- |
| Raw page | `bee76335963dc0045b0a0be4638afab827dfef9e83cef4eaa3e812d8ba0ba094` |
| Frontier observation | `5e5f63dbc701476347a814a8496f1e88869f27a49e884b2cf27ee8ee238e661a` |
| Persisted row | `75db34b2b7e9848637942dcbb771745774cfc52ec586322b90c278e7e78b65` |

The page had 20 two-instrument markets, four numeric event identifiers, and a
largest event group with 13 listed children. All 20 records included rule
text; one included a resolution authority; zero included a close time; and
zero were marked verified or exhaustive for payoff. This is bounded source
coverage, not an exhaustive market inventory or proof of an outcome set.

The single selected `/events/{id}` request was rejected by the 256-KiB body
bound. At the time, `RESPONSE_TOO_LARGE` retained neither status nor declared
length metadata, and no body was stored or retried. No more source requests
were made. The local database contains the first page only; it is under the
ignored `data/public-captures/` path and is not committed or published. No
Kalshi, Kraken, Coinbase, or protected Reality data was accessed.

This exposed a source-diagnostics gap. `PublicReadTransport` now rejects
declared or streamed bodies before copying beyond the configured limit and
attaches status, timestamps, declared length when available, configured cap,
and bytes yielded at rejection. It never retains an oversized body. API probe
and finite collector failure paths persist a metadata-only `source_failure`
observation with `raw_body_state=not_captured_after_size_limit`; its raw hash
is explicitly the hash of the empty stored body, while the normalized
version-2 `SourceFailureRecord` preserves the rejection metadata. Schema-v1
raw observations and failure records remain readable. The implementation adds
transport, API, collection, and legacy-schema tests.

Ruff check/format and whitespace validation pass. The fresh 768-MiB admission
attempt for focused tests and strict mypy was denied by the shared Arena lock.
At `2026-10-28T03:23:40Z`, memory PSI avg10 was **12.12% some / 10.92% full**,
above configured admission thresholds. Those tests and strict mypy are still
pending; no test pass is claimed for this change. The earlier 383-test
Frontier/selected-Arena regression remains dated evidence from before it.

## Bounded response-rejection verification — 2026-10-28 03:27 UTC

A fresh 768-MiB preflight admitted the focused regression. Nine tests passed
in **3.19 seconds** across the complete Frontier transport test module and
targeted API, finite-collection, and legacy-schema cases. They cover declared
length and streaming rejection, metadata-only persistence without a response
body, source-health degradation, and reading schema-v1 records. One existing
Starlette/httpx TestClient deprecation warning remains.

Strict mypy passed with `--strict --follow-imports=silent` for
`apps/api/frontier.py`, `packages/midas/frontier/collection.py`,
`packages/midas/frontier/models.py`, and the adapter base and transport
modules. Ruff check/format and `git diff --check` passed. This verifies the
focused rejection path and five scoped modules; it does not replace a full
Frontier regression.

A new preflight for all `tests/frontier` was denied with
`resource_admission_lock_busy`; no test started. At `2026-10-28T03:27:25Z`,
memory PSI avg10 was **14.17% some / 12.55% full**, I/O PSI avg10 was **0.93%
some / 0.72% full**, available memory was about **9.8 GiB**, and free swap was
about **333 MiB**. PID **4128967** was confirmed running
`scripts/veritas_gap_detail_v2_batch.py` against the shared Arena root. It was
not interrupted. The full Frontier suite remains pending a fresh passing
preflight. No source request, protected service action, or deployment occurred
during this verification.

The focused response-size diagnostic is **COMPLETE AND VERIFIED** within its
bounded tests. Frontier overall remains **PARTIALLY VERIFIED**, research-only,
isolated, and undeployed.

## Gamma event response bound and documented recovery path — 2026-10-28

The official [Gamma market-discovery reference](https://docs.polymarket.com/market-data/discover-markets)
describes `/events/{id}` as returning one event object containing its `markets`
array. It also documents individual market lookups and a paged
`/markets/keyset` collection. The reviewed reference does not describe
event-ID-keyed pagination for the event's child markets. This means an event
with many children can exceed Frontier's configured response cap even though
the market listing page itself fit. Rejected bodies remain uncaptured; the new
diagnostic record preserves only response metadata. Individual requests for
already-known market IDs are a possible bounded way to hydrate those known
markets, but cannot prove the complete event outcome set. No additional source
requests were made for this documentation review. The observed event's payoff
and exhaustiveness remain unverified.

## Full regression after response-rejection schema change — 2026-10-28 03:32 UTC

Following commit `c91bdf43f125b15279907d4ca53291f377b58387`, a fresh 768-MiB
resource admission check passed and the complete `tests/frontier` suite plus
the selected Arena discovery, replay, timeline, and job tests passed **387/387**
in 90.74 seconds pytest time (92.21 seconds process wall). Maximum RSS was
**379,240 KiB**, with zero swaps and zero socket messages. The existing
Starlette/httpx TestClient deprecation warning remains. This closes the
Frontier and selected Arena regression for the new raw-observation schema v2
and rejection metadata path; it is not a full repository regression.

At `2026-10-28T03:32:45Z`, the post-run 768-MiB gate denied additional work with
`host_memory_pressure`. Memory PSI avg10 was **41.42% some / 36.83% full** and
I/O PSI avg10 was **7.68% some / 7.20% full**; about **10.1 GiB** was available.
Read-only inspection found external Veritas PID **4132908** running
`scripts/veritas_gap_detail_v2_batch.py` against the shared Arena root. It was
left untouched. No further resource-bearing checks were started.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Frontier plus selected Arena regression after schema v2 | COMPLETE AND VERIFIED | 387/387 pass with 379,240 KiB peak RSS, zero swaps, and zero socket messages. |
| Project Frontier overall | PARTIALLY VERIFIED | Cross-venue payoff validation, held-source permission, broad scientific and production acceptance, and deployment remain incomplete. |

## Frontier source-failure evidence in Mission Control — 2026-10-28 03:36 UTC

The exchange workspace's probe error now surfaces saved diagnostic
observations through the existing immutable-evidence disclosure. For an
oversize rejection, the view labels the body as uncaptured, shows the transport
cap and rejection metadata, and clarifies the empty-stored-body hash. The UI
filters diagnostic IDs to lowercase SHA-256 identities before rendering them.
A fixture regression was added for the structured probe error and evidence
record. No network request is involved.

The change is not yet verified. No web test, typecheck, lint, format check, or
production build ran after the edit because the latest host preflight denied
resource work at `2026-10-28T03:32:45Z` during high memory PSI and an external
Veritas batch. The backend regression remains 387/387 at its prior checkpoint;
it does not cover this UI edit.

### Focused UI evidence verification — 2026-10-28 03:37 UTC

The focused Frontier web regression passed **1/1** after formatting. It covers
a structured `RESPONSE_TOO_LARGE` result, the linked diagnostic observation,
and the body-omission and stored-hash disclosure. `corepack pnpm typecheck`,
targeted ESLint, and Prettier check passed. No live source request was made.

The full web unit suite was not started: the fresh resource gate at
`2026-10-28T03:37:23Z` denied work at **31.75% memory PSI some / 25.89% full**.
About **9.8 GiB** remained available, but external Veritas PID **4136998** held
the shared Arena lock. It was left untouched. Browser E2E and production build
remain pending; no deployment occurred.

## Legacy API and research-boundary regression — 2026-10-28 04:16 UTC

The isolated Frontier branch also passed two targeted MIDAS integration
modules. `tests/integration/test_api.py` passed **5/5** in 4.47 seconds pytest
time (5.56 seconds process wall) at **167,956 KiB peak RSS**. It verifies the
offline Frontier API contract and probe denial in demo mode, persistence and
failure gates using temporary databases, and configured workspace routing.
`tests/integration/test_milestone2_journey.py` passed **5/5** in 4.70 seconds
pytest time (5.55 seconds process wall) at **134,632 KiB peak RSS**. It checks
fixture-backed verifier and paper-broker replay, disallowed stale/negative
economics, read-only request guards, and temporary paper-state recovery. Both
runs used zero swap and emitted no socket messages. The existing
Starlette/httpx TestClient deprecation warning remains.

At the post-run sample `2026-10-28T04:16:39Z`, memory PSI avg10 was **0.00%
some / 0.00% full**, I/O PSI avg10 **1.04% / 1.04%**, about **10 GiB** was
available, and the shared Arena lock had no holder. No live source endpoint,
production database, protected service, real Arena worker, or deployment was
used. This increases confidence in compatibility and the research-only API
boundary; it does not establish production behavior, cross-venue economic
equivalence, or full MIDAS regression. Frontier remains **PARTIALLY VERIFIED**,
isolated, research-only, and undeployed.

## Completion matrix snapshot — 2026-10-28 04:18 UTC

This snapshot incorporates the 04:07 code and build verification, the 04:09
API-description check, the 04:16 legacy API regressions, and the host admission
sample captured at 04:18 UTC. Later sections supersede its test and resource
status where they contain newer evidence.

| Requirement | Status | Current evidence and remaining boundary |
| --- | --- | --- |
| Isolated baseline and exchange-independent adapter foundation | COMPLETE AND VERIFIED | Separate worktree and branch; capability registry, bounded transports, source-specific adapters, and compatibility contracts are implemented. |
| Polymarket, Kalshi, Kraken, and Coinbase adapters | PARTIALLY VERIFIED | Read-only adapters have fixture/contract coverage; one bounded Polymarket detail response was captured. Kalshi and Kraken remain held and Coinbase remains held pending terms-scope resolution; no fresh cross-venue request is claimed. |
| Canonical instruments and payoff semantics | PARTIALLY VERIFIED | Versioned identities, native units, and bounded binary, one-hot, and basket semantics are implemented; broader instrument classes and sourced equivalence remain unsupported. |
| Relationship graph and evidence | PARTIALLY VERIFIED | Bounded proposals, explicit verification states, append-only review evidence, persistence, and neighborhood APIs/UI are tested. No genuine verified cross-venue economic match exists; reviewer and external joint-state assertions are not authenticated. |
| Opportunity generation and independent verification | PARTIALLY VERIFIED | Supported binary, implication, payoff-basket, and bounded joint-state arithmetic has independent checks and differential fixtures. No live positive or economically eligible opportunity is established. |
| Venue costs, capital, and currency | PARTIALLY VERIFIED | Fee sensitivities, partial-fill stress, venue-separated virtual balances, and assumption-driven conversion scenarios exist. Sourced FX, custody/transfer access, account-specific costs, jurisdiction, and settlement risks remain unknown. |
| Collection, provenance, storage, and deterministic replay | PARTIALLY VERIFIED | Bounded restartable collection, hash-chained checkpoints, immutable evidence, and replay are implemented and offline tested. Continuous feeds, complete source histories, and long-horizon source quality are unverified. |
| Laboratory/Arena integration | PARTIALLY VERIFIED | Deterministic replay and bounded jobs are integrated; one short synthetic job completed under a real constrained transient unit. Selected Arena tests pass 38/38 after event-ID correction; sustained and production worker behavior is unmeasured. |
| Native Frontier dashboard | IMPLEMENTED, DEPLOYMENT PENDING | Web unit tests 40/40, Frontier Playwright 6/6, and temporary-directory production build pass. Browser/source data is fixture/local; the existing Chart chunk advisory remains. |
| Scientific acceptance | PARTIALLY VERIFIED | Full Frontier Python tests pass 352/352 after event-ID correction; selected Arena tests pass 38/38 separately; recorded-body replay, offline capture integrity, and 10 legacy API/adapter tests pass. No live equivalent cross-venue observation or economic validation exists. |
| Bounded resource sustainability | PARTIALLY VERIFIED | Prior bounded tests/builds recorded their peak RSS and zero swaps. Concurrency, continuous collection, and production admission remain unmeasured. At 04:18 UTC memory PSI avg10 was 48.45% some / 43.86% full, and an external Veritas batch held the shared Arena lock; no further resource-bearing work was started. |
| Research-only boundary and source-use gates | COMPLETE AND VERIFIED | Tests ensure held sources reject before network use and no trading/authenticated order pathway is exposed. This does not grant permission to use a held source. |
| Documentation and continuation evidence | COMPLETE AND VERIFIED | Architecture, operations, source terms, current-state, engineering report, and append-only ledger record the implementation and blockers. |
| Genuine live cross-venue validation | BLOCKED | Existing source-use holds prevent an authorized second-venue observation; the captured Polymarket detail lacks event membership/payoff evidence. No equivalence or profitability claim is made. |
| Production deployment | DEFERRED | Requires separate source permission, production resource/storage/recovery review, full deployment-scope regression, monitoring/rollback preparation, and explicit authorization. |
| Project Frontier overall | PARTIALLY VERIFIED | The isolated research system is substantially implemented and bounded-tested, but live cross-venue scientific acceptance and deployment criteria remain open. |

The optional legacy storage-query and recording-isolation tests were inspected
but not run after the 04:17 preflight found the shared Arena lock held and
memory PSI rising. At `2026-10-28T04:18:00Z`, `fuser` showed external PID
**4170342** using the lock; `ps` identified the process as
`scripts/veritas_gap_detail_v2_batch.py` under
`midas-veritas-gap-detail-v2.service`. It was not interrupted. About **10 GiB**
of available memory does not override that gate. Resume only after a fresh
admission sample passes and the shared lock is free.

### Subsequent bounded compatibility and service-guard checks — 2026-10-28 04:19 UTC

The lock later cleared and a fresh low-avg10 sample admitted three narrowly
scoped checks. Storage-query plus recording-isolation tests passed **7/7** in
2.18 seconds pytest time (2.68 seconds process wall), with **103,244 KiB peak
RSS**. The protected-service materialization guard test passed **1/1** in 0.43
seconds (0.84 seconds process wall), with **72,156 KiB peak RSS**. These tests
use temporary roots or mocked service state. A source-tree search for
`data/frontier/live-probes` and `live-probes/` returned no matches in
`tests`, `packages`, or `apps`; it did not open held capture data.

All test processes used zero swap and emitted zero socket messages. At
`2026-10-28T04:19:47Z`, memory PSI avg10 was **0.01% some / 0.01% full**,
avg60 **9.38% / 8.50%**, avg300 **13.11% / 11.79%**, and I/O PSI avg10
**1.27% / 1.08%**. About **10 GiB** was available and no Arena lock holder was
listed. The selected checks close the previously deferred legacy storage and
recording contracts, not the full MIDAS suite or sustained resource admission.

| Component | Status | Current evidence and remaining boundary |
| --- | --- | --- |
| Storage query and recording isolation compatibility | COMPLETE AND VERIFIED | 7/7 selected tests pass using temporary roots/path assertions. |
| Protected-service paper-state mutation guard | COMPLETE AND VERIFIED | Focused mock-backed test proves the service guard rejects API and Reality materialization; no actual service interaction occurred. |
| Held-capture path references in source/test trees | COMPLETE AND VERIFIED | No direct `live-probes` path references found in tests, packages, or apps; no held data was opened. |
| Project Frontier overall | PARTIALLY VERIFIED | Live cross-venue validation, complete repository acceptance, and deployment remain incomplete. |

### Held-source boundary regression — 2026-10-28 04:20 UTC

`tests/frontier/test_held_capture_source_boundary.py` passed **2/2** in 0.16
seconds pytest time (0.46 seconds process wall), at **43,732 KiB peak RSS**,
with zero swaps and zero socket messages. It scans current Python test files
for held-capture path references and exercises read, write, open, `os.open`,
symlink, traversal, and `dir_fd` protections only under a temporary directory.
No preserved capture was opened. The post-run sample at
`2026-10-28T04:20:34Z` showed memory PSI avg10 **0.00% some / 0.00% full**,
avg60 **4.36% / 3.95%**, avg300 **11.19% / 10.07%**, I/O PSI avg10
**0.87% / 0.69%**, about **10 GiB** available, and no shared Arena lock holder.

| Component | Status | Current evidence and remaining boundary |
| --- | --- | --- |
| Held-source capture guard | COMPLETE AND VERIFIED | Current test-tree scan and temporary-path denial cases pass; no held data was accessed. |

### Combined Frontier/Arena acceptance after current code — 2026-10-28 04:23 UTC

The full Frontier test directory plus selected Arena discovery, replay,
timeline, and job modules passed **390/390 in one pytest invocation** after
the current Frontier code changes. Runtime was **91.63 seconds pytest time**
(**93.00 seconds process wall**) at **380,624 KiB peak RSS**. The run used zero
swaps and emitted zero socket messages. It produced the existing
Starlette/httpx TestClient deprecation warning. Tests use fixtures and
temporary roots; they do not prove a production systemd worker or live source
behavior.

At the post-run sample `2026-10-28T04:23:44Z`, memory PSI avg10 was **39.41%
some / 35.46% full**, avg60 **29.70% / 26.17%**, avg300 **16.08% / 14.23%**,
and I/O PSI avg10 **8.41% / 8.00%**. About **10 GiB** appeared available,
but the shared Arena lock was held by external Veritas PID **4174453**. It was
left untouched. No further resource-bearing check was started.

| Component | Status | Current evidence and remaining boundary |
| --- | --- | --- |
| Combined Frontier and selected Arena regression | COMPLETE AND VERIFIED | 390/390 pass in one invocation after current code; this is not the full MIDAS suite. |
| Resource sustainability under current host load | PARTIALLY VERIFIED | The combined run did not swap, but post-run PSI was high and the external batch held the shared lock; concurrent/sustained capacity remains unverified. |
| Project Frontier overall | PARTIALLY VERIFIED | Live cross-venue equivalence, complete MIDAS regression, and deployment remain incomplete. |

### Supplemental FX source evaluation — 2026-10-28

Official ECB Data Portal documentation provides an HTTPS SDMX API and daily
reference-rate series such as `D.USD.EUR.SP00.A`. ESCB statistics are reusable
with attribution, subject to the published no-modification rule and separate
rights for third-party data. The source's daily reference values are not
executable bid/ask quotes and do not establish same-time conversion, transfer,
or account availability. ECB is therefore recorded as a possible contextual
reference-data provider, not as a trading venue, exchange adapter, or decisive
funding source. No ECB API request or data capture occurred. The [source terms
review](SOURCE_DATA_TERMS_REVIEW_2026-10-27.md) records the primary links and
the exact limitations.

## Legacy integration regression — 2026-10-28 04:32 UTC

The complete `tests/integration` directory passed **56/56 runnable tests**;
one optional PostgreSQL runtime test was skipped because
`MIDAS_TEST_POSTGRES_URL` was absent. The run used a dedicated pytest base
directory at `/tmp/midas-frontier-integration-20261028T0432Z` and completed in
**28.49 seconds pytest time** (**29.73 seconds wall**) at **220,460 KiB peak
RSS**, with zero swaps, major faults, or socket messages. The existing
Starlette/httpx TestClient deprecation warning remains. Temporary-root tests
and the skipped PostgreSQL case do not establish database-backend runtime
behavior.

At `2026-10-28T04:32:51Z`, the post-run host sample showed memory PSI avg10
**38.12% some / 32.63% full**, avg60 **16.02% / 13.44%**, and avg300 **9.56% /
8.34%**; about **10 GiB** was available. Read-only inspection identified
external Veritas PID **4182417** holding the shared Arena admission lock. It
was left untouched. No additional tests, build, source request, protected
service action, or deployment was started after that sample.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Legacy integration regression | COMPLETE AND VERIFIED | `tests/integration`: 56 passed, one optional PostgreSQL test skipped; temporary pytest directory; 220,460 KiB peak RSS; zero swaps or socket messages. |
| Full MIDAS repository regression | PARTIALLY VERIFIED | The Frontier/selected-Arena and complete integration suites pass, but the rest of `tests/` has not run as one repository-wide suite. |
| Further resource-bearing checks at this checkpoint | DEFERRED | Post-run memory PSI rose and an external Veritas job held the shared lock; its process was not disturbed. |

## Full-suite collection baseline mismatch — 2026-10-28 04:36 UTC

A full Python-suite attempt was made in a detached test worktree at commit
`29b09fa`; the Frontier worktree was not used as the test directory. That
detached checkout did contain the tracked `data/frontier/live-probes` capture
directory. Pytest stopped during collection after **10.89 seconds**
with an `ImportError` in `tests/test_reality_full_scale_validation.py:12`:
`from midas.reality import recovery`. The selected source tree does not contain
`packages/midas/reality/recovery.py`, so no test cases executed. The command
used the shared MIDAS virtual environment and a dedicated `/tmp` base directory
and peaked at **453,748 KiB RSS**, with zero swaps and socket messages.

Read-only Git-tree comparison found that `recovery.py` is present in the
separate candidate `fix/reality-foundation-20261020` at `4278b5b`, but absent
from both the selected Veritas V6 baseline and the protected `project/reality`
checkout. The missing candidate implementation depends on companion Reality
changes in reconstruction, replay, and storage. No files were copied or merged
from that candidate, and no protected service was accessed. This is a
cross-worktree baseline/test mismatch; it does not establish that the full
suite passes against either source revision. No test functions executed in
this attempt. File-open tracing was not enabled, so available evidence does
not establish whether collection read any held capture; no capture writes or
copies were intentional.

At `2026-10-28T04:38:33Z`, memory PSI avg10 was **1.17% some / 1.03% full**,
avg60 **13.95% / 12.54%**, and avg300 **10.50% / 9.37%**. About **10 GiB** was
available. The shared Arena lock no longer had a holder in that sample, but
the host remained under material longer-window pressure; no further suite or
build was started.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Full MIDAS Python suite | PARTIALLY VERIFIED | Collection is blocked by the selected checkout lacking `midas.reality.recovery`, imported by a current tracked test. No suite tests ran. |
| Reality candidate integration | DEFERRED | The separate recovery implementation is coupled to newer reconstruction/replay/storage code; no cross-branch merge was attempted. |
| Broader regression after this attempt | DEFERRED AT THIS SAMPLE | Longer-window memory PSI remained elevated; no test process or shared Arena lock holder remained. |

## Sparse-tree regression correction and resource stop — 2026-10-28 04:43 UTC

This entry corrects the 04:36 account: the `29b09fa` detached worktree did
contain the tracked `data/frontier/live-probes` directory. No test functions
ran in that attempt because collection failed first, but file-open tracing was
not enabled. Therefore, the evidence does not establish whether collection
read a held capture. No capture writes or copies were intentional.

The follow-up used a detached sparse worktree at `c8989d5` with `data/`
excluded. The path
`/tmp/midas-frontier-regression-sparse-20261028T0440Z/data/frontier/live-probes`
was absent before and after the run. The source snapshot is documented in the
mission ledger. The diagnostic command excluded the known Reality collection
blocker:

```bash
nice -n 10 /usr/bin/time -v env PYTHONPATH=packages:. \
  /home/charlie/midas/.venv/bin/python -m pytest -q \
  --basetemp=/tmp/midas-frontier-rest-regression-20261028T0440Z \
  --ignore=tests/test_reality_full_scale_validation.py tests
```

Pytest reported **101 passed** before SIGINT at **149.66 seconds**, then exited
2 with `KeyboardInterrupt`. This is an incomplete diagnostic, not a suite pass.
Peak RSS was **539,616 KiB**; swaps and socket messages were zero. At
`2026-10-28T04:42:57Z`, memory PSI was **35.48% some / 28.44% full** over 10
seconds, **15.83% / 13.22%** over 60 seconds, and **8.25% / 7.15%** over 300
seconds. External Veritas batch PID **4190462** held the shared Arena lock and
was left untouched; only the Frontier test process was interrupted. At
`2026-10-28T04:43:58Z`, that PID remained present and memory PSI had risen to
**47.14% some / 42.14% full** over 10 seconds. No further resource-bearing
validation is admitted at this checkpoint.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Full MIDAS suite excluding the known Reality collection blocker | PARTIALLY VERIFIED | 101 tests passed before a resource-driven interrupt; pytest exited 2 and no full-suite result is claimed. |
| Capture exclusion for follow-up diagnostic | COMPLETE AND VERIFIED | Sparse test worktree omitted `data/`; the held capture path was absent before and after. |
| Captures in the initial detached collection worktree | PARTIALLY VERIFIED | Tracked capture directory was present; no test functions ran, but access during collection cannot be ruled out without file-open tracing. |
| Further local regression | DEFERRED AT THIS SAMPLE | Memory PSI was high and external Veritas PID 4190462 remained active; it was not interrupted. |

## Re-admission attempt and second resource stop — 2026-10-28 04:49 UTC

At `2026-10-28T04:45:48Z`, memory PSI had recovered to **0.00% some / 0.00%
full** over 10 seconds and **7.46% / 6.57%** over 60 seconds; about **10.2
GiB** was available. The shared Arena lock had no holder, and the sparse
worktree remained clean with `data/frontier/live-probes` absent. On that fresh
sample, the same bounded repository diagnostic was retried in the sparse tree,
using `/tmp/midas-frontier-rest-regression-20261028T0445Z` for pytest output.

It again reached **101 passed**. At interruption, a test-dispatched Arena
planning child was still active under the pytest temporary root. Static review
identified it as
`tests/arena/test_research_planning.py::test_native_plan_runs_four_fits_and_matched_fresh_studies`:
the test calls `create(..., launch=False)` and then directly starts
`midas.arena.jobs` with a 300-second worker limit and a 330-second subprocess
timeout. The worker and pytest process were CPU-active; the external Veritas
lock was concurrent host activity, not evidence that the test was waiting on
that lock. At `2026-10-28T04:49:37Z`, PSI was **43.29% some / 37.60%
full** over 10 seconds, **33.38% / 28.08%** over 60 seconds, and **19.74% /
16.84%** over 300 seconds. PID **4194119** (`veritas_gap_detail_v2_batch.py`)
was in `DNs` state with about **259 MiB RSS** and held the lock. Only Frontier
pytest PID **4193289** was interrupted; the temporary child job and test
process had exited by the post-stop check. The external process was not
signaled. The run ended before the declared subprocess timeout; it is
incomplete because it was stopped under high shared-host pressure, not because
the test failed or timed out.

Pytest exited **2** with `KeyboardInterrupt` at **204.34 seconds** (205.98
seconds process wall), with **534,664 KiB** peak RSS, zero swaps, zero major
faults, and zero socket messages. The run does not pass the repository suite.
The capture path remained absent after the attempt, and the sparse test
worktree was clean at the post-run check. No code or test files were modified.
Further resource-bearing checks are deferred until a new memory and Arena-lock
admission sample.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Broad MIDAS Python regression excluding known collection blocker | PARTIALLY VERIFIED | Two runs each reached 101 passing tests; both ended with resource-driven interrupts and exit 2. Neither is a suite pass. |
| Sparse capture isolation | COMPLETE AND VERIFIED | Held capture path absent before and after both diagnostic runs. |
| External Arena workload isolation | COMPLETE AND VERIFIED | Only Frontier pytest processes were interrupted; external Veritas PID 4194119 was left untouched. |
| Further repository regression | DEFERRED AT THIS SAMPLE | External job holds the shared lock and memory PSI is high. |

## Isolated planning test admission stop — 2026-10-28 04:52 UTC

At `2026-10-28T04:52:00Z` (approximately), a fresh read-only sample found no
Arena lock holder, memory PSI **0.00% some / 0.00% full** over 10 seconds and
**6.36% / 5.51%** over 60 seconds, I/O PSI **1.08% / 0.96%** over 10 seconds,
and about **10.2 GiB** available. The only test then started was the identified
bounded Arena case:

```bash
nice -n 10 /usr/bin/time -v env PYTHONPATH=packages:. \
  /home/charlie/midas/.venv/bin/python -m pytest -q \
  --basetemp=/tmp/midas-frontier-arena-plan-test-20261028T0452Z \
  tests/arena/test_research_planning.py::test_native_plan_runs_four_fits_and_matched_fresh_studies
```

After roughly 21 seconds, external Veritas batch PID **4437** appeared and held
the shared Arena lock. At that sample, memory PSI rose to **26.81% some /
23.46% full** over 10 seconds. The test and its temporary worker were CPU
active; the worker was not waiting for the global lock. I sent SIGINT only to
the Frontier pytest PID. Pytest exited **2** after **37.95 seconds** with
`KeyboardInterrupt` and reported **no tests ran**. Peak RSS was **441,976 KiB**,
with zero swaps, major faults, and socket messages. The test was stopped before
its own 330-second subprocess timeout; no test result is claimed.

At the post-stop sample `2026-10-28T04:52:53Z`, PID 4437 remained and held the
shared lock; memory PSI was **35.37% some / 31.45% full** over 10 seconds. The
temporary child exited, the sparse worktree stayed clean, and the held capture
path remained absent. No source or test files changed. Defer further tests
until a fresh admission sample.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Isolated Arena planning regression | PARTIALLY VERIFIED | Started under a clear admission sample, then was interrupted after 37.95s when shared-host PSI rose; no test completed. |
| Sparse capture boundary | COMPLETE AND VERIFIED | Held path remained absent; sparse test worktree stayed clean. |
| Further resource-bearing checks | DEFERRED AT THIS SAMPLE | External PID 4437 holds the shared lock and short-window PSI is high. |

## Configured Arena lock isolation — 2026-10-28 04:56 UTC

Code commit `bffa163` fixes a real test-isolation defect: API settings and both
Playwright configurations already supplied a temporary `MIDAS_ARENA_ROOT`,
but the Arena admission helper and Veritas batch independently hard-coded the
primary production lock path. `midas.arena.admission.global_lock_path()` now
uses the configured root, creates it when absent, rejects an empty or symlink
root, and retains the prior primary-root behavior when the environment
variable is unset. `scripts/veritas_gap_detail_v2_batch.py` imports that shared
helper, keeping batch and Arena workers on the same lock path.

The affected tests cover configured-root creation, unchanged default-path
selection, symlink rejection, and Veritas/Arena lock-path identity. Both full
affected modules passed **24/24** in **1.43 seconds pytest time** (**2.04
seconds wall**) at **181,080 KiB peak RSS**, with zero swaps, major faults, or
socket messages. Ruff check and format check passed on all four changed Python
files; `git diff --check` passed. The test invocation used a dedicated
`/tmp/midas-frontier-admission-regression-20261028T0456Z` base directory and
temporary Arena roots. It made no exchange request or protected-service
change. No Playwright run or broad repository suite was started after this
patch; browser/runtime integration remains to be verified.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Configured Arena lock path | COMPLETE AND VERIFIED | Default behavior, configured root, symlink refusal, and shared Veritas/Arena path pass affected tests. |
| API/Playwright runtime integration | PARTIALLY VERIFIED | Configuration supplies the isolated root and helper tests pass; browser E2E after the change is not yet run. |
| Project Frontier overall | PARTIALLY VERIFIED | Full repository regression, genuine cross-venue equivalence, held-source permission, and production readiness remain incomplete. |

## Resource admission remains closed — 2026-10-28 04:57 UTC

At `2026-10-28T04:57:41Z`, external Veritas batch PID **8201** held the shared
Arena lock in `DNs` state at **256,804 KiB RSS**. Memory PSI was **39.38% some
/ 34.80% full** over 10 seconds, **11.08% / 9.83%** over 60 seconds, and
**11.05% / 9.74%** over 300 seconds. About **10.1 GiB** was available; I/O PSI
avg10 was below 1%. No tests, builds, source requests, or service changes
started after the `bffa163` lock-path verification. The external process was
left untouched. Defer further broad or browser verification until a fresh
sample shows acceptable pressure and no shared-lock holder.

## Admission recheck — 2026-10-28 04:58 UTC

At `2026-10-28T04:58:41Z`, PID 8201 was no longer present and no process held
the shared Arena lock. Memory PSI had fallen to **1.57% some / 1.44% full**
over 10 seconds, **14.55% / 13.22%** over 60 seconds, and **13.02% / 11.62%**
over 300 seconds. About **10.3 GiB** was available; I/O PSI avg10 was below
1%. The short-window full PSI still exceeds the Arena admission threshold of
1%, so no broad suite or browser run started. Recheck before resource-bearing
verification.

## Cross-process source collection lease — 2026-10-28 05:05 UTC

Code commit `8fb4c0d` gives each venue a process-shared, nonblocking `flock`
lease in the isolated Frontier collection store. A second API process cannot
start or resume a competing finite collection for that venue while the lease
is held; other venues use separate leases. A rejected start does not create a
run record. Resume re-reads the latest checkpoint after taking the lease, so a
run completed by another process is returned from its terminal checkpoint.
Lease files are opened without following symlinks and must be user-owned
regular files. The lease is released on normal completion, error, timeout, or
cancellation.

The complete `tests/frontier/test_collection.py` module passed **21/21** in
6.04 seconds pytest time (**6.41 seconds wall**) at **67,672 KiB peak RSS**,
zero swaps, and zero socket messages. The added checks cover competing
collector instances, a forked competing process, per-venue independence,
rejection before run creation, and lease release. Ruff check/format and
`git diff --check` passed. Strict `mypy --strict --follow-imports=silent
packages/midas/frontier/collection.py` also passed with no issues (134,940 KiB
peak RSS, zero swaps or socket messages). No exchange request, browser/build,
protected service change, or production lock write was involved. Web/API
typing and the broader suites remain pending.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Per-venue collection lifecycle isolation | COMPLETE AND VERIFIED | Process-shared nonblocking lease, competing-process rejection, other-venue concurrency, no orphan run, and lease release pass in the collection module. |
| Full Frontier and MIDAS regression after this change | PARTIALLY VERIFIED | Only the complete collection module was rerun; the full suites remain outstanding. |
| Strict typing and browser/runtime integration after this change | PARTIALLY VERIFIED | Strict mypy passes for the collection module; web/API typing and browser runtime remain unverified. |
| Live cross-venue economics and deployment | BLOCKED / DEFERRED | Existing source-use restrictions and production readiness boundaries remain unchanged. |

## Collection wall time includes the initial health check — 2026-10-28 05:09 UTC

Code commit `6c5c329` removes the initial source health await from run setup.
The durable `created` checkpoint is now written first, and the first health
probe runs inside the configured finite collection timeout. A stalled health
probe therefore produces a durable `paused` checkpoint with
`COLLECTION_WALL_LIMIT`, before any discovery request. This also ensures a
stalled adapter cannot retain the new per-venue process lease indefinitely.

The expanded `tests/frontier/test_collection.py` module passed **23/23** in
7.28 seconds pytest time (**7.67 seconds wall**) at **68,316 KiB peak RSS**,
zero swaps, and zero socket messages. It includes the health-stall wall-limit
case, forked competing-collector case, symlink rejection, and source-lease
release checks. Ruff check, Ruff format, and `git diff --check` passed before
the test run. Strict mypy passed on `8fb4c0d`; the post-`6c5c329` rerun remains
pending. No exchange request or protected-service operation occurred.

At approximately `2026-10-28T05:09Z`, memory PSI avg10 was **0.09% some / 0.08%
full** and I/O PSI avg10 was **3.50% some / 3.12% full**. No process held the
shared Arena lock. Defer further resource-bearing verification until a fresh
admission sample.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Finite collection wall-time enforcement | COMPLETE AND VERIFIED | An indefinitely stalled initial health call is checkpointed as paused at the configured wall limit, with no discovery request; all 23 collection tests pass. |
| Collection module typecheck after `6c5c329` | PARTIALLY VERIFIED | Strict mypy passed immediately before this small refinement; rerun after the latest commit. |
| Full Frontier/MIDAS and browser regression after latest collector changes | PARTIALLY VERIFIED | Only the 23-test collection module is current; full regression remains outstanding. |
| Live cross-venue economics and deployment | BLOCKED / DEFERRED | Source-use and production readiness boundaries remain unchanged. |

## Collection API lease-conflict regression — 2026-10-28 05:12 UTC

Test commit `be73099` adds an API-level check that holds a venue lease while
posting to `/api/frontier/collect/{venue}`. The endpoint returns **HTTP 409**
before it creates a collection run or calls market discovery. This verifies
that the library's cross-process lease failure is translated to the existing
API conflict response. All eight tests in `tests/frontier/test_collection_api.py`
pass in **2.35 seconds pytest time** (**2.83 seconds wall**) at **88,252 KiB
peak RSS**, with zero swaps or socket messages. The suite emits one existing
Starlette deprecation warning for using `httpx` with `TestClient`; no network
request occurred. Ruff check, Ruff format, and `git diff --check` passed.

At approximately `2026-10-28T05:11Z`, memory PSI avg10 was **0.00% some / 0.00%
full**, I/O PSI avg10 was **2.36% some / 1.92% full**, and no process held the
shared Arena lock. Post-refinement strict typing and broader tests remain
pending until a fresh admission sample.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Collection API lease-conflict behavior | COMPLETE AND VERIFIED | Eight API module tests pass; busy lease returns 409 without a run record or discovery request. |
| Strict mypy after `6c5c329` | PARTIALLY VERIFIED | Previous strict mypy result is from `8fb4c0d`; post-refinement rerun remains. |
| Full Frontier/MIDAS and browser regression | PARTIALLY VERIFIED | Collection and collection API modules pass; broader suites have not been rerun. |

## Timeout releases source ownership — 2026-10-28 05:14 UTC

Test commit `f502977` strengthens the stalled-health regression: after the
first finite collection reaches `COLLECTION_WALL_LIMIT` and persists `paused`,
a second run for the same venue starts and completes. This proves the
per-venue file lease is released on timeout, rather than only on cancellation
or normal completion.

The complete collection module passes **23/23** after this assertion in 7.56
seconds pytest time (**7.92 seconds wall**) at **69,780 KiB peak RSS**, with
zero swaps and socket messages. This includes lease release after timeout,
forked-process exclusion, symlink rejection, and the health-stall no-discovery
check. The collection API module remains **8/8** from the immediately
preceding run. No external network request or protected service action
occurred.

After this test, at approximately `2026-10-28T05:14Z`, I/O PSI avg10 rose to
**6.98% some / 6.73% full**; memory PSI avg10 was **0.05% some / 0.05% full**.
No process held the shared Arena lock. Post-refinement mypy, browser checks,
and broader suites remain deferred pending a fresh resource sample.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Lease release after wall timeout | COMPLETE AND VERIFIED | The stalled-health run pauses at the wall limit and a subsequent same-venue run completes; the 23-test collection module passes. |
| Collection API endpoint integration | COMPLETE AND VERIFIED | The API module passes 8/8, including HTTP 409 on a busy lease. |
| Post-refinement strict typing and broad regression | PARTIALLY VERIFIED | Latest mypy remains pending; full Frontier/MIDAS and browser suites remain outstanding. |

## Combined collection verification and strict typecheck — 2026-10-28 05:15 UTC

After `6c5c329`, strict `mypy --strict --follow-imports=silent
packages/midas/frontier/collection.py` passed with **no issues** at **134,740
KiB peak RSS**, zero swaps, and zero socket messages.

The collector and HTTP API modules then passed together:

```bash
nice -n 10 /usr/bin/time -v env PYTHONPATH=packages:. \
  /home/charlie/midas/.venv/bin/python -m pytest -q \
  --basetemp=/tmp/midas-frontier-collection-combined-20261028T0518Z \
  tests/frontier/test_collection.py tests/frontier/test_collection_api.py
# 31 passed in 9.40s; 91,868 KiB peak RSS; zero swaps or socket messages
```

The run emitted one existing Starlette deprecation warning for `httpx` with
`TestClient`. Both test modules use synthetic in-process adapters and temporary
stores; no external request or held-capture path was involved. After the run,
at approximately `2026-10-28T05:15Z`, memory PSI avg10 was **0.00% some / 0.00%
full**, I/O PSI avg10 was **6.55% some / 6.10% full**, and no process held the
shared Arena lock. Defer broad Python, browser, and build workloads until a
new admission sample clears the I/O gate.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Collector, lease, timeout, and HTTP endpoint regression | COMPLETE AND VERIFIED | Combined collection and API modules pass 31/31 after the latest code; this does not substitute for full Frontier/MIDAS regression. |
| Strict typecheck of the changed collector | COMPLETE AND VERIFIED | Mypy strict passes on `packages/midas/frontier/collection.py` after `6c5c329`. |
| Broad regression and browser verification | PARTIALLY VERIFIED | Deferred after the post-test I/O PSI sample exceeded 1%; remeasure before launch. |

## Full Frontier suite interrupted by shared-host pressure — 2026-10-28 05:17 UTC

The full `tests/frontier` suite was started in an isolated `/tmp` base after
an admission sample showed no shared Arena lock and short-window PSI below the
1% gate. During the run, external Veritas batch PID **24419** appeared and
held `/home/charlie/midas/data/arena/.global-admission.lock`. Memory PSI rose
to **18.13% some / 14.58% full** and I/O PSI to **4.98% some / 4.42% full**.
Only Frontier pytest PID **24413** received SIGINT; the external batch and its
lock were left untouched.

Pytest reported **108 passed** before `KeyboardInterrupt`, then exited **2**
after **19.11 seconds pytest time** (**20.14 seconds process wall**) at
**323,856 KiB peak RSS**, zero swaps, zero major faults, and zero socket
messages. This is an interrupted diagnostic, not a full-suite pass. The
captured pytest output included the existing Starlette/httpx TestClient
deprecation warning. The run used
`/tmp/midas-frontier-full-suite-20261028T0518Z` as its base. A source scan
found no `live-probes` references in `tests/frontier`, the Frontier package,
or its API module. The worktree remained clean.

At the post-stop sample `2026-10-28T05:17Z`, memory PSI avg10 was **44.56%
some / 36.62% full**, I/O PSI avg10 was **2.48% some / 2.34% full**, and PID
24419 still held the Arena lock. No further tests, builds, browser work, or
source requests started. Recheck after the external batch releases the lock
and short-window PSI falls below admission thresholds.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Full Frontier Python suite after collector changes | PARTIALLY VERIFIED | Interrupted after 108 passed under rising host pressure; exit 2, no suite pass. |
| Interruption isolation | COMPLETE AND VERIFIED | Only Frontier pytest was interrupted; external Veritas batch was not signaled and worktree remained clean. |
| Further resource-bearing checks | DEFERRED | External lock held and PSI exceeded admission thresholds at the latest sample. |

## Second full Frontier suite attempt stopped at I/O gate — 2026-10-28 05:20 UTC

A retry of `pytest tests/frontier` began after a fresh sample had memory and
I/O PSI avg10 below 1% and no shared Arena lock. At approximately 20% test
progress, I/O PSI rose to **5.43% some / 5.43% full** while no external lock
holder or batch process was present. This run itself was causing material I/O
pressure, so I sent SIGINT only to Frontier pytest PID **27532**.

Pytest reported **113 passed** before `KeyboardInterrupt`, then exited **2**
after **23.59 seconds pytest time** (**24.69 seconds process wall**) at
**339,596 KiB peak RSS**, zero swaps, zero major faults, and zero socket
messages. It wrote **139,160 KiB** to its isolated test area. This is an
interrupted diagnostic, not a full-suite pass. The worktree remained clean,
and the source scan found no `live-probes` references in the selected test,
package, or API paths. The existing Starlette/httpx TestClient deprecation
warning appeared.

At `2026-10-28T05:20Z`, post-stop memory PSI avg10 was **0.00% some / 0.00%
full**, I/O PSI avg10 was **1.65% some / 1.59% full**, and no process held the
shared Arena lock. Avoid another monolithic run; resume broader coverage as
smaller serial file groups after short-window PSI clears the gate.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Monolithic Frontier Python regression | PARTIALLY VERIFIED | Two attempts stopped at 108 and 113 completed cases; both exited 2 and neither is a suite pass. |
| Changed collection and collection API modules | COMPLETE AND VERIFIED | The focused pair passes 31/31 in one invocation, with strict mypy for the changed collection module. |
| Remaining Frontier regressions | PARTIALLY VERIFIED | Split into smaller serial groups after host admission; no browser/build run yet. |

## Bounded serial Frontier regression slices — 2026-10-28 05:23 UTC

To reduce the I/O footprint after the monolithic attempts, four focused
invocations passed **198 tests** across the changed collector/API, adapter,
analytics/timeline/transport/logical-relation, and economics/capital/fee/spot
modules:

| Module group | Result | Peak RSS | Boundary |
| --- | --- | --- | --- |
| `test_collection.py`, `test_collection_api.py` | 31 passed in 9.40s | 91,868 KiB | Busy lease API conflict, wall-time timeout/release, cross-process leases, and collection persistence. |
| `test_adapters.py` | 62 passed in 2.51s | 59,976 KiB | Adapter contracts and synthetic response fixtures. |
| `test_analytics.py`, `test_discovery_comparison.py`, `test_timeline.py`, `test_logical_implication.py`, `test_transport.py` | 25 passed in 2.31s | 59,444 KiB | Local analytical, timing, relationship, and transport behavior. |
| `test_fx_sensitivity.py`, `test_capital_carry.py`, `test_kalshi_fee_sensitivity.py`, `test_coinbase.py`, `test_logical_implication_economics.py` | 80 passed in 2.26s | 81,928 KiB | Fixture-only economics, fee, currency, and spot-context checks. |

All four test processes used isolated `/tmp` basetemp directories, zero swaps,
and zero socket messages. The API-containing groups emitted the existing
Starlette/httpx TestClient deprecation warning. A scan found no
`live-probes` references in the Frontier tests, package, or API module. Strict
mypy separately passes for `packages/midas/frontier/collection.py` after the
latest collector implementation.

At `2026-10-28T05:23Z`, memory PSI avg10 was **31.74% some / 28.60% full**,
I/O PSI avg10 was **0.39% some / 0.38% full**, and no Arena lock holder was
present. Defer more resource-bearing tests at this sample. Unrun as complete
modules are `test_api.py`, `test_relationships_economics_replay.py`,
`test_relationship_reviews.py`, `test_joint_state.py`, `test_storage.py`,
`test_replay_comparison.py`, `test_timeline_api.py`,
`test_source_data_permissions.py`, and `test_held_capture_source_boundary.py`.
No full Frontier/MIDAS pass or browser/build verification is claimed.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Four serial test slices | COMPLETE AND VERIFIED | 198 passing tests across bounded modules; no external network, swap, or socket traffic. |
| Full Frontier Python regression | PARTIALLY VERIFIED | Two monolithic attempts interrupted; nine test modules remain unrun as complete modules. |
| Resource admission | DEFERRED | Memory PSI remained high at the latest sample despite no active Arena lock holder. |

## Storage module verification — 2026-10-28 05:25 UTC

`tests/frontier/test_storage.py` passes **18/18** in **7.61 seconds pytest
time** (**7.97 seconds wall**) at **69,800 KiB peak RSS**, zero swaps, and zero
socket messages. The module covers append-only observations and relationships,
hash/tamper checks, read-only query behavior, keyset graph pages, budgets, and
additive migrations. It used an isolated `/tmp` basetemp and did not access
the held live-probe directory.

The timed process wrote **98,840 KiB** into its temporary SQLite evidence
stores. At approximately `2026-10-28T05:24Z`, memory PSI avg10 was **0.01% some
/ 0.01% full**, while I/O PSI avg10 rose to **7.74% some / 7.24% full**. At
the later 05:24:49 sample, I/O PSI remained just over admission at **1.05%
some / 1.04% full**; no process held the shared Arena lock. Defer additional
storage/API test modules until a fresh sample clears the I/O gate.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Storage integrity and recovery tests | COMPLETE AND VERIFIED | All 18 storage tests pass in isolation; no full suite claim. |
| Serial Frontier regression slices | PARTIALLY VERIFIED | 216 passing tests across five bounded invocations; eight Frontier modules remain unrun as complete modules. |
| Additional resource-bearing verification | DEFERRED | I/O PSI remains above 1% at the latest measurement. |

## Source-use boundary regression slice — 2026-10-28 05:25 UTC

The source-protection modules `test_held_capture_source_boundary.py` and
`test_source_data_permissions.py` passed **7/7** in **2.57 seconds pytest
time** (**3.34 seconds wall**) at **141,420 KiB peak RSS**, zero swaps, and
zero socket messages. The checks guard against test/runtime access to held
capture paths, confirm unvalidated permission references do not enable source
probes, and verify held source evidence remains quarantined. The run wrote
**3,616 KiB** to its isolated temporary directory; no exchange endpoint was
requested. One existing Starlette/httpx TestClient deprecation warning
remains.

At the post-test sample around `2026-10-28T05:25Z`, memory PSI avg10 was
**0.00% some / 0.00% full** and I/O PSI avg10 was **1.13% some / 0.97% full**;
no Arena lock holder was present. Defer additional test modules until I/O
`some` PSI falls below 1%.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Source-use and held-capture boundary tests | COMPLETE AND VERIFIED | All 7 tests pass; no new source request and only temporary test data were used. |
| Serial Frontier regression coverage | PARTIALLY VERIFIED | 223 tests pass across six bounded invocations; six modules remain unrun as complete modules. |
| Remaining resource-bearing tests | DEFERRED | I/O `some` PSI is slightly above the 1% threshold. |

## Replay comparison and timeline API verification — 2026-10-28 05:27 UTC

The complete `test_replay_comparison.py` and `test_timeline_api.py` modules
passed **8/8** in one bounded invocation (2.90 seconds pytest time, 3.61
seconds wall, 211,468 KiB peak RSS). Pytest used
`/tmp/frontier-replay-timeline-20261028`; the process had zero swaps and socket
messages and wrote 4,840 KiB. The existing Starlette/httpx TestClient
deprecation warning appeared.

The immediate post-run sample showed memory PSI avg10 **0.00% some / 0.00%
full** and I/O PSI avg10 **1.52% some / 1.37% full**. No Frontier test or Arena
research lock holder was active. Further tests are deferred until I/O `some`
PSI falls below 1%. Serial regression coverage now totals **231 passed cases
across seven bounded invocations**. Four complete modules remain:
`test_api.py`, `test_relationships_economics_replay.py`,
`test_relationship_reviews.py`, and `test_joint_state.py`. The full suite is
still unverified; the two interrupted monolithic runs are not full-suite
passes.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Replay comparison and timeline API | COMPLETE AND VERIFIED | Both modules pass 8/8 in an isolated temporary directory. |
| Serial Frontier regression coverage | PARTIALLY VERIFIED | 231 passed across seven invocations; four modules remain. |
| Full Frontier regression | PARTIALLY VERIFIED | Two monolithic attempts were interrupted; no full-suite pass is claimed. |
| Additional resource-bearing checks | DEFERRED | Post-run I/O PSI exceeded the admission threshold. |

## Relationship review module verification — 2026-10-28 05:29 UTC

The complete `test_relationship_reviews.py` module passed **13/13** in 4.72
seconds pytest time (5.22 seconds wall) at 104,492 KiB peak RSS. It ran with
`/tmp/frontier-relationship-reviews-20261028`, zero swaps, and zero socket
messages. The existing Starlette/httpx TestClient deprecation warning
appeared.

The immediate post-run sample showed memory PSI avg10 **0.02% some / 0.01%
full** and I/O PSI **2.85% some / 2.10% full**. No Frontier test or shared
Arena admission lock holder remained active. Further tests are deferred until
I/O `some` PSI falls below 1%. Serial regression coverage now totals **244
passed cases across eight bounded invocations**. Three complete modules
remain: `test_api.py`, `test_relationships_economics_replay.py`, and
`test_joint_state.py`. No full-suite pass is claimed; both monolithic attempts
were interrupted.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Relationship review module | COMPLETE AND VERIFIED | All 13 tests pass in an isolated temporary directory. |
| Serial Frontier regression coverage | PARTIALLY VERIFIED | 244 passed across eight invocations; three modules remain. |
| Full Frontier regression | PARTIALLY VERIFIED | Two monolithic attempts were interrupted; no full-suite pass is claimed. |
| Additional resource-bearing checks | DEFERRED | Post-run I/O PSI exceeded the admission threshold. |

## API regression, collection/overview slice — 2026-10-28 05:31 UTC

The API module collects to **55 test cases**. Its first isolated slice covers
collection start/resume/history, overview, coverage analytics, saved Kalshi
fee-pair joining, and the disabled public-probe guard. All **9/9** selected
cases passed in 3.31 seconds pytest time (3.80 seconds wall) at 97,360 KiB peak
RSS. The run used `/tmp/frontier-api-collection-overview-20261028`, zero
swaps, and zero socket messages. The existing Starlette/httpx TestClient
deprecation warning appeared.

The immediate post-run sample measured memory PSI avg10 **0.00% some / 0.00%
full** and I/O PSI **2.07% some / 1.38% full**. No Frontier test or shared
Arena admission lock holder remained active. Further slices are deferred
until I/O `some` PSI falls below 1%. Total serial regression coverage is now
**312 cases across eleven bounded invocations**. The API module remains
partial, with 46 cases in three slices outstanding; no full Frontier suite
pass is claimed.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| API collection and overview slice | COMPLETE AND VERIFIED | Nine selected cases pass; 46 API cases remain. |
| Serial Frontier regression coverage | PARTIALLY VERIFIED | 312 cases pass across eleven invocations; API coverage is incomplete. |
| Full Frontier regression | PARTIALLY VERIFIED | Both monolithic attempts remain interrupted, not completed passes. |

## API regression, source-probe slice — 2026-10-28 05:32 UTC

The second API slice covers public-source probe parsing/persistence, event and
multivariate metadata, fee metadata, and cross-venue event context. It passed
**12/12** in 6.52 seconds pytest time (7.01 seconds wall) at 103,256 KiB peak
RSS. Pytest used `/tmp/frontier-api-source-probes-20261028`; the process had
zero swaps and socket messages. The existing Starlette/httpx TestClient
deprecation warning appeared.

At the immediate post-run sample, memory PSI avg10 was **0.00% some / 0.00%
full** and I/O PSI was **2.95% some / 2.12% full**. No Frontier tests or Arena
admission lock holder remained active. Defer further slices until I/O `some`
PSI falls below 1%. API coverage is **21/55** cases across two slices, with 34
cases remaining. Serial regression coverage totals **324 cases across twelve
bounded invocations**; no full Frontier suite pass is claimed.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| API collection/overview and source-probe slices | COMPLETE AND VERIFIED | 21 of 55 cases pass across two isolated slices; 34 remain. |
| Serial Frontier regression coverage | PARTIALLY VERIFIED | 324 pass across twelve invocations; the API module is partial. |
| Full Frontier regression | PARTIALLY VERIFIED | The monolithic attempts were interrupted; no full-suite pass is claimed. |

## API regression, replay/readiness slice — 2026-10-28 05:33 UTC

The third API slice covers relationship proposal/replay, paired replay,
resource-gated Arena staging, readiness, corrupt-row handling, raw
observations, and persisted candidate replay. It passed **19/19** in 7.50
seconds pytest time (8.31 seconds wall) at 243,040 KiB peak RSS. Pytest used
`/tmp/frontier-api-replay-readiness-20261028`; the process had zero swaps and
socket messages. The existing Starlette/httpx TestClient deprecation warning
appeared.

The immediate post-run sample showed memory PSI avg10 **0.00% some / 0.00%
full** and I/O PSI **2.58% some / 2.23% full**. No Frontier test or shared
Arena admission lock holder remained active. Defer the last API slice until
I/O `some` PSI falls below 1%. API coverage is **40/55** cases across three
slices, with 15 cases outstanding. Total serial regression coverage is now
**343 passed cases across thirteen bounded invocations**; a full-suite pass
is still not established.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| API regression slices | PARTIALLY VERIFIED | 40 of 55 cases pass across three slices; 15 remain. |
| Serial Frontier regression coverage | PARTIALLY VERIFIED | 343 cases pass across thirteen invocations. |
| Full Frontier regression | PARTIALLY VERIFIED | Both monolithic runs were interrupted; no full-suite pass is claimed. |

## Frontier serial regression completion — 2026-10-28 05:35 UTC

The final API graph/trade-read/capture-lineage slice passed **15/15** in 11.60
seconds pytest time (12.11 seconds wall) at 113,792 KiB peak RSS. It used
`/tmp/frontier-api-graph-trades-20261028`; the process had zero swaps and
socket messages. The existing Starlette/httpx TestClient deprecation warning
appeared.

The API module collected to **55 cases** and all are covered by four
non-overlapping slices:

| Slice | Cases | Pytest time | Peak RSS |
| --- | ---: | ---: | ---: |
| Collection, overview, coverage | 9 | 3.31s | 97,360 KiB |
| Source probes and metadata | 12 | 6.52s | 103,256 KiB |
| Replay, Arena staging, readiness | 19 | 7.50s | 243,040 KiB |
| Graph, trade reads, capture lineage | 15 | 11.60s | 113,792 KiB |

Across bounded runs, **all 22 `tests/frontier/test_*.py` modules completed
successfully**: **358 passing cases across fourteen invocations**. The
recorded runs had zero swaps and zero socket messages. Two monolithic
`pytest tests/frontier` attempts were interrupted after 108 and 113 cases;
this is not represented as a single-process full-suite pass.

The post-run sample measured memory PSI avg10 **0.00% some / 0.00% full** and
I/O PSI **4.09% some / 3.01% full**. No Frontier test or Arena admission lock
holder remained active. Defer the frontend build/browser workload until I/O
`some` PSI falls below 1%.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Python modular regression | COMPLETE AND VERIFIED | All 22 modules pass across bounded invocations: 358 cases in fourteen runs. |
| Single-process full Frontier suite | PARTIALLY VERIFIED | Two monolithic attempts were interrupted; no one-process pass. |
| Frontend build and browser integration | DEFERRED | Earlier UI verification exists; the post-backend rerun is pending admission. |

## Current frontend and integration verification — 2026-10-28 05:38 UTC

The current branch frontend passes the production build, unit suite, targeted
Frontier browser spec, lint, and formatting checks:

- `corepack pnpm build` completed `tsc -b` and Vite in 13.75 seconds wall time
  at 664,720 KiB peak RSS, with zero swaps and socket messages.
- The full web unit suite passed **40/40** tests across seven files in 6.67
  seconds Vitest time (7.70 seconds wall) at 290,488 KiB peak RSS, with zero
  swaps and socket messages.
- The Frontier Playwright spec passed **6/6** in 15.5 seconds (16.35 seconds
  wall) at 199,036 KiB peak RSS. It ran an isolated demo API and Vite server
  using temporary SQLite, Arena, and Frontier roots. Those services exited
  afterward and ports 15173/18000 were free. These local fixture flows made
  no exchange probe and submitted no orders.
- `corepack pnpm lint` and `corepack pnpm format:check` passed. Targeted Ruff
  check and format verification passed for the changed collector and tests;
  strict mypy for the collector passed at the earlier checkpoint.

Vite still emits a chunk-size advisory for the 504.00 kB main bundle and
544.41 kB Chart bundle. The Frontier lazy bundle is 164.53 kB JavaScript and
48.35 kB CSS. This is a follow-up optimization; the production build passed.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Python modular regression | COMPLETE AND VERIFIED | All 22 modules pass: 358 cases across fourteen bounded invocations. |
| Frontier frontend unit/build/lint/format | COMPLETE AND VERIFIED | 40 unit cases, TypeScript/Vite build, lint, and Prettier pass. |
| Frontier browser integration | COMPLETE AND VERIFIED | Six Frontier Playwright tests pass against isolated local demo services. |
| Single-process full Python suite | PARTIALLY VERIFIED | Two monolithic runs were interrupted; modular coverage is complete. |
| Live second-venue relationship/economics | BLOCKED | Existing source-use holds remain; no genuine cross-venue relationship or opportunity is claimed. |
| Production transition | DEFERRED | The branch remains isolated and undeployed pending separate source, resource, recovery, and deployment review. |

## Package-wide Frontier static analysis — 2026-10-28 05:43 UTC

Strict typing now covers the complete Frontier package and its API integration
route:

- `mypy --strict --follow-imports=silent packages/midas/frontier`: **23 source
  files**, no issues, 5.38 seconds wall, 199,892 KiB peak RSS.
- Adding `apps/api/frontier.py` to the same strict check: **24 source files**,
  no issues, 28.84 seconds wall, 723,472 KiB peak RSS.
- Ruff check passes for `packages/midas/frontier`, `apps/api/frontier.py`, and
  `tests/frontier`; Ruff format check reports all **51 files** already
  formatted.

Both mypy caches were under `/tmp`, and both processes used zero swaps. The
post-check PSI sample showed memory avg10 **0.00% some/full** and I/O avg10
**0.00% some/full**. No service, external source, or persistent research store
was accessed or modified.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Frontier package and API strict typing | COMPLETE AND VERIFIED | 24 source files pass strict mypy. |
| Frontier Python lint and formatting | COMPLETE AND VERIFIED | Ruff passes and all 51 relevant files are formatted. |
| Live multi-venue validation | BLOCKED | Current source-use holds prevent a second-venue observation. |
| Production eligibility | DEFERRED | The branch remains isolated; no deployment was attempted. |

## Polymarket public price-history milestone — 2026-10-28 06:15 UTC

Commit `f0a5957` (`feat(frontier): add bounded Polymarket price history`)
adds a separate `PRICE_HISTORY` capability to Polymarket adapter v7. The
official [CLOB price-history reference](https://docs.polymarket.com/api-reference/markets/get-prices-history)
documents the token ID, time bounds, interval, and fidelity parameters. The
adapter currently allows the documented `1d` and `1w` intervals, at most 7 days,
up to 1500 points, and the configured response-byte limit. It validates exact
Decimal prices in `[0,1]`, integral Unix-second timestamps, strict ordering,
the requested window, and token IDs. Polymarket continues to declare
`HISTORICAL_CANDLES` unsupported: the price response does not provide OHLC,
volume, or trade count.

The explicit API operation
`POST /api/frontier/probe/polymarket/price-history` accepts only an outcome token
present in the bounded recorded market listing. It persists the raw response,
normalized series, and the listing observation ID used to authorize that token
lookup. `GET /api/frontier/price-history` reads stored series only. Mission
Control's Market detail view exposes token, CLOB interval, and 1/3/7-day lookback
controls, an accessible sample-dot plot, a bounded sample table, and evidence
inspection. No source request occurs on page load. Historical samples remain
context only and are not executable quotes or simultaneous cross-venue prices.

One explicit unauthenticated public request for token
`98022490269692409998126496127597032490334070080325855126491859374983463996227`
returned HTTP 200 with **79 samples**, **2139 response bytes**, and raw SHA-256
`0b69fa1f31cd9618e922ab681c41c67e4de51d5572e662fa3db1d3267e50afc8`. A repeat
request returned the same content hash. The byte-for-byte source response and
capture sidecar are preserved in:

- `tests/fixtures/polymarket_price_history_live_20261028.json`
- `tests/fixtures/polymarket_price_history_live_20261028.meta.json`

The live request was made directly through a temporary adapter configured for
one GET. It did not run through or change the API service, write to a Frontier
runtime store, access an account, or submit an order. Separate 30-day and
36-day requests returned HTTP 400 with `startTs`/`endTs` “interval is too long”.
The public reference does not publish an accepted maximum range; Frontier uses
seven days as a conservative cap. The sidecar records status and message for
those rejected attempts; they were not persisted as separate `RawObservation`
records. No conclusion about source-wide historical coverage is drawn from one
token and window.

Verification on this branch:

- `tests/frontier/test_adapters.py`: **67 passed** in 2.53 seconds, including
  offline replay of the genuine captured public response.
- `tests/frontier/test_api.py`: **56 passed** in 45.11 seconds, including
  listing-bound lookup, persisted raw/normalized lineage, stored-series read,
  unknown-token rejection before egress, and the 7-day request cap.
- `Frontier.test.tsx`: **8 passed** in 5.39 seconds, including the explicit
  token-history UI capture and no automatic source request.
- `e2e/frontier.spec.ts`: **6 passed** in 15.6 seconds against isolated local
  demo services. The added price-history workflow itself is covered by the
  fixture-backed component test and API integration test.
- Strict mypy: **5 changed Python source files**, no issues. Ruff check/format,
  web lint, Prettier check, `git diff --check`, and the TypeScript/Vite
  production build pass.

The frontend build retains the existing 504.00 kB main and 544.41 kB Chart
chunk advisory. The API test run also reports the existing Starlette
`httpx` deprecation warning. No measured resource profile was taken for this
feature. No live cross-venue relationship, candidate economics, or positive
opportunity was demonstrated.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Polymarket price-history adapter | COMPLETE AND VERIFIED | A genuine 79-point public response is preserved and the normalizer replays it offline; current source-range cap is based on observed 400 responses, not a published maximum. |
| Price-history API, raw persistence, and saved lookup | COMPLETE AND VERIFIED | Full API module passes; request is bound to a recorded instrument and stores the listing observation ID. No production deployment occurred. |
| Market detail price-history interface | COMPLETE AND VERIFIED | Component and browser suites pass using fixtures; the new history control has no dedicated browser E2E scenario yet. |
| Use of history in multi-venue economics | DEFERRED | History is contextual evidence only; no algorithm consumes it as an executable quote. |
| Genuine cross-venue validation | BLOCKED | Kalshi, Kraken, and Coinbase source-use holds remain; no new cross-venue equivalence is claimed. |
| Production transition | DEFERRED | No service configuration, production store, or deployment was changed. |

**Changed files in `f0a5957`:** `apps/api/frontier.py`,
`apps/web/src/Frontier.tsx`, `apps/web/src/Frontier.test.tsx`,
`apps/web/src/frontier.css`, `packages/midas/frontier/models.py`,
`packages/midas/frontier/adapters/{__init__,base,polymarket}.py`,
`tests/frontier/{test_adapters,test_api}.py`, and the two captured fixture files
listed above. Architecture, operations, and development docs plus the mission
ledger were updated in the documentation checkpoint following this code commit.

## Deterministic price-history replay and coverage — 2026-10-28 06:34 UTC

Code commit `2e27f1102d8055f822b41ad40b02421385d7df33` adds a descriptive
historical price-sample replay alongside the existing market/book opportunity
replay. It accepts one to eight persisted `historical_price_points`
observations, revalidates immutable observation and raw hashes, source venue,
receipt time, and any saved market/token binding, then pins sorted input IDs,
normalized data hash, backend code version, and replay version in a separate
manifest. For each series the result records point count, exact Decimal price
bounds, first/last point timestamps, span, largest adjacent returned-sample gap,
and point timestamps later than local receipt. No price quote, candle, fill,
candidate, or opportunity is generated. A returned-point gap does not estimate
missing data because the source has not specified completeness or expected
cadence.

The immutable SQLite `price_history_replays` table is part of schema 7. The
initializer upgrades schema 6 without changing historic evidence. The
`POST /api/frontier/price-history/replay` route reads only existing source rows,
does not make a network call, and writes the exact result; list/detail routes
verify hashes and filter missing or held source IDs. The coverage endpoint scans
at most 20 recent eligible history records and groups capture counts, unique
instrument counts, source point counts, empty/unbound captures, future times,
capture ages, source point time ranges, and largest adjacent observed gaps.
Overlapping records remain separate, and repeated samples may appear in summed
point counts. Mission Control exposes these summaries on the existing Coverage
view and offers a button in Market detail to replay a saved series explicitly.

The E2E fixture suite intercepts the Polymarket capture route and proves the
workflow performs no request until capture is pressed, then issues a separate
local replay only after its own click. This is an interface demonstration with
fixture data, not a live or historical source validation. The genuine Polymarket
response captured in the previous milestone remains preserved only as a test
fixture; it was not inserted into a runtime database.

Verification includes 31 deterministic replay/analytics/storage tests, the
56-test API module, the five-test source-permission module, 40 frontend unit
tests, and seven Frontier browser tests. TypeScript, ESLint, Prettier, Ruff,
strict targeted mypy, `git diff --check`, and the production frontend build pass.
The API test process emitted the existing Starlette/httpx deprecation warning;
Vite retains its 504.00 kB main and 544.41 kB Chart chunk-size advisory. An
unsuppressed strict mypy traversal reported 14 errors in imported Veritas and
Arena files and none in the four changed Frontier Python modules. No
feature-specific RSS/CPU profile was captured.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Deterministic descriptive history replay | COMPLETE AND VERIFIED | Pinned inputs, exact summaries, result hashes, and bounded acceptance. No opportunity candidates. |
| History replay persistence | COMPLETE AND VERIFIED | Schema 7 table, schema 6 migration, immutable writes, hash validation, temporary-store tests. |
| Historical source-quality summary | COMPLETE AND VERIFIED | Newest bounded captures by venue; repeated windows and gaps are explicitly described without inferred completeness. |
| Mission Control replay action | COMPLETE AND VERIFIED | Explicit, fixture-backed capture/replay flow in component and browser tests. |
| History-based cross-venue economics | DEFERRED | Historical prices remain context; no payoff or executable quote model consumes them. |
| Second-venue live validation | BLOCKED | Source-use holds remain for Kalshi, Kraken, and Coinbase. |
| Production migration and deployment | DEFERRED | No production store, service, or deployment was changed. |

Changed files in `2e27f11`: `apps/api/frontier.py`,
`packages/midas/frontier/{historical_replay,analytics,storage}.py`,
`apps/web/src/{Frontier.tsx,Frontier.test.tsx,frontier.css}`,
`apps/web/e2e/frontier.spec.ts`, and
`tests/frontier/{test_historical_replay,test_analytics,test_api,test_source_data_permissions}.py`.
The architecture, operations, development, ledger, and engineering-report
documentation checkpoint is recorded separately from the code commit.

## Research & Replay history lineage inspector — 2026-10-28 06:44 UTC

Code commit `ce8d7dd` adds a native inspector to Mission Control's Replay &
readiness workspace. It reads up to 20 latest saved Polymarket historical-price
captures and up to 20 saved descriptive replay artifacts. Researchers can
select one to eight capture observation IDs and explicitly request a local
replay. The UI does not call a source endpoint from this workflow, and its
result panel labels candidate generation as not performed.

Saved replay artifacts load through the existing hash-validating detail route.
The inspector displays the run, normalized-input, and result hashes; replay and
code versions; latest input receipt time; and, per input, source observation
ID, raw-body hash, venue, native instrument, optional bound market observation,
requested interval and range, returned sample price bounds, timestamp bounds,
largest adjacent returned-point gap, and future-point count. For source records
outside the currently loaded 20-capture page, it makes the missing receipt-time
context explicit. No price sample is treated as a quote or candidate.

The source selector enforces the backend's eight-input limit: once eight
checkboxes are selected, further unchecked rows are disabled. The UI does not
silently truncate a replay payload. Artifact list selection and detail loading
are separate read operations, and held-source artifacts remain filtered by the
existing API response.

Verification:

- `corepack pnpm test`: **41 passed** across seven frontend test files. The
  Frontier component test covers saved list/detail reads, two-series replay,
  receipt/raw lineage, no automatic POST, and the eight-selected/ninth-disabled
  boundary.
- `corepack pnpm exec playwright test e2e/frontier.spec.ts`: **7 passed** on
  isolated local services. Its price-history case uses intercepted fixtures,
  confirms the two-record replay and lineage, checks no extra source probe, and
  verifies no horizontal overflow at a 390 px viewport.
- `corepack pnpm build`: TypeScript and production Vite build pass with 2,228
  modules transformed. The Frontier bundle is 181.57 kB; existing main and
  Chart chunk advisories remain at 504.00 kB and 544.41 kB.
- ESLint, Prettier check, and `git diff --check` pass.

No API or Python implementation changed in this checkpoint. Browser and
component tests use fixture responses; this is not a UI validation against a
populated service store or live source. No service store was migrated, no
deployment or resource profile was performed, and no economic calculation was
run. Kalshi, Kraken, and Coinbase remain held, so only the existing Polymarket
historical-price source is selectable in this inspector.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Multi-series replay selection and eight-input limit | COMPLETE AND VERIFIED | Frontend test selects eight, confirms the ninth is disabled, and checks the exact two-ID request after reducing selection. |
| Saved replay list/detail interface | PARTIALLY VERIFIED | Fixture-backed browser and component runs pass; populated service-store UI validation remains pending. |
| Per-series source lineage display | COMPLETE AND VERIFIED | Source IDs, raw hashes, instrument, binding, request interval, sampled bounds, and receipt context are visible. |
| Cross-venue historical series | BLOCKED | Remaining source-use holds prevent additional venue data from entering the inspector. |
| Production migration and deployment | DEFERRED | No service configuration or production database changed. |

Changed files in `ce8d7dd`: `apps/web/src/Frontier.tsx`,
`apps/web/src/Frontier.test.tsx`, `apps/web/src/frontier.css`, and
`apps/web/e2e/frontier.spec.ts`. Documentation was updated in a separate
checkpoint. **Next safe action:** add bounded offset paging to the two local
saved-evidence lists, retaining held-source filtering and the eight-series
limit.

## Bounded paging for saved price-history evidence — 2026-10-28 06:53 UTC

Code commit `797e00a` adds `has_more` to the two history list APIs using one
extra read row, while returning no more than the caller's requested page. The
source-history response retains a 20-row maximum and a 100,000 maximum offset.
The replay list retains a 100-row maximum and the same offset bound. For replay
artifacts, the API determines whether another stored page exists before source
eligibility filtering; it then filters held or missing evidence on only the
visible page and reports the held count for that page. Offsets still advance
through all stored runs, so a held artifact does not hide eligible later
results.

Mission Control now pages both saved capture and replay lists in 20-row
increments. Page controls show current page and result count. The source
selection applies only to its current page and resets when navigating; no more
than eight IDs can enter a replay. Replay page navigation clears the selected
ID and loads the first visible artifact detail for the new page. All paging is
over local evidence and triggers no venue request.

Verification:

- `tests/frontier/test_api.py`: **56 passed** in 29.57 seconds; added assertions
  verify `has_more` on first and final capture/replay pages using a temporary
  store and MockTransport.
- `tests/frontier/test_source_data_permissions.py`: **5 passed** in 3.51
  seconds; existing Starlette/httpx deprecation warning remains.
- `corepack pnpm test`: **41 passed** across seven files, including selection
  clearing on source-page changes and the 8-item cap.
- `corepack pnpm exec playwright test e2e/frontier.spec.ts`: **7 passed**;
  fixture-backed capture/replay remains explicit, and the inspector fits a
  390 px viewport without horizontal overflow.
- `corepack pnpm build`: TypeScript and production build pass, with 2,228
  modules transformed. Frontier output is 182.67 kB. Existing main and Chart
  chunk warnings remain at 504.00 kB and 544.41 kB.
- ESLint, Prettier, Ruff check/format, and `git diff --check` pass.

Strict mypy on `apps/api/frontier.py` reports 15 `no-any-return` errors on
unchanged lines of that module; none points to the pagination change. There
was no measured resource profile. API tests use temporary stores and mock
transports, and the browser test intercepts history routes with fixtures. This
does not establish a populated service-store UI result or live source
validation. No deployment or production migration was performed.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Bounded lookahead and source-history paging | COMPLETE AND VERIFIED | API tests cover exact next/final-page signals and offsets. |
| Replay paging with held-source filtering | COMPLETE AND VERIFIED | Held omission is page-scoped and eligible later rows remain reachable. |
| Mission Control capture/replay pagination | COMPLETE AND VERIFIED | Component and browser suites pass; source selection clears on page change. |
| Populated-store UI/API browser integration | PARTIALLY VERIFIED | API persistence tests use temporary stores, while browser history calls are fixture-intercepted. |
| Multi-venue price-history sources | BLOCKED | Kalshi, Kraken, and Coinbase remain held; no unsupported series are surfaced. |
| Production migration/deployment | DEFERRED | No service configuration or production store changed. |

Changed files in `797e00a`: `apps/api/frontier.py`,
`apps/web/src/Frontier.tsx`, `apps/web/src/Frontier.test.tsx`,
`apps/web/src/frontier.css`, `apps/web/e2e/frontier.spec.ts`, and
`tests/frontier/test_api.py`. Operations, architecture, development, ledger,
and report docs were updated separately. **Next safe action:** seed a dedicated
temporary Frontier store with explicit fixture captures/replays and drive the
browser inspector against the local API without contacting a venue.

## Populated saved-history browser/API verification — 2026-10-28 06:59 UTC

Code commit `3251941` adds an opt-in browser scenario and fixture seeder for the
persisted price-history inspector. The seeder writes 21 immutable Polymarket-
shaped history observations and their 21 deterministic replay artifacts into a
fresh SQLite store under a temporary browser root. Every fixture uses a
versioned adapter label and an explicit fixture-only limitation. It refuses to
overwrite an existing store; it does not make HTTP requests. The Playwright
configuration shares and validates the temporary root across its config and
worker processes, seeds only under `MIDAS_SEED_FRONTIER_E2E=1`, and otherwise
leaves the existing empty-store E2E behavior intact.

The new test first checks the local API's first and final capture/replay pages
and `has_more` transitions. It then navigates Mission Control, selects two
saved captures, posts an explicit local descriptive replay, reads the saved
artifact by run ID, inspects its per-series lineage, and pages the older saved
records. The test observed no `/probe/` request. This verifies persistence and
the API/UI path against controlled fixture rows; it is not venue validation,
cross-venue evidence, or economic research.

Verification since this checkpoint:

- The opt-in seeded browser integration: **1 passed** against the real local
  FastAPI routes and isolated temporary store.
- Standard `e2e/frontier.spec.ts`: **7 passed** on temporary loopback services.
- Frontend unit tests: **41 passed** across seven files.
- TypeScript project check, ESLint, Prettier, Ruff check/format, and production
  frontend build passed. Vite transformed 2,228 modules; existing 504.00 kB
  main and 544.41 kB Chart chunk advisories remain.
- Direct storage verification confirmed 21 captures and 21 replay artifacts
  with newest-first paging. No production store, protected service, or source
  endpoint was accessed.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Saved-history API/UI over persisted data | COMPLETE AND VERIFIED | Isolated SQLite fixture store, actual local routes, UI replay POST, saved detail and page navigation; zero source probes. |
| Seeded E2E isolation | COMPLETE AND VERIFIED | Explicit opt-in, temporary-root validation, store overwrite refusal, default suite unseeded. |
| Live source response validation | BLOCKED | Existing source-use holds remain; fixture evidence does not change this state. |
| Production integration | DEFERRED | No production database, service, or deployment was changed. |

**Next safe action:** continue the source-independent acceptance matrix and
select the next bounded replay, resource, or supervisor gap. Remeasure host
admission before a broad or resource-intensive run; keep source-use holds and
production isolation unchanged.

## Host admission recheck — 2026-10-28 07:03 UTC

At `2026-10-28T07:02:48Z`, the shared Arena admission lock was held by external
Veritas batch PID **115803** in `midas-veritas-gap-detail-v2.service`. The
process had exited and released the lock by the next sample at
`2026-10-28T07:03:02Z`; no signal was sent and no store was touched. At that
time memory PSI avg10 was **32.56% some / 29.27% full**, while I/O PSI avg10
was **0.70% some / 0.70% full**. Available memory was about **10.7 GiB** and
free swap about **0.52 GiB**. No resource-bearing Frontier test, build, or
Arena job was started after the sample because memory pressure remained high.
This is a dated admission observation, not a capacity guarantee.

**Continuation:** remeasure memory/I/O pressure and the shared lock before any
additional resource-bearing acceptance run. Do not interrupt the separate
Veritas workload or bypass normal admission.

## Complete default browser regression — 2026-10-28 07:05 UTC

With memory PSI avg10 at 0%, I/O PSI avg10 at 0.92%, about 10 GiB available,
and the shared Arena lock unheld, the complete web browser suite ran on
isolated loopback services. `corepack pnpm exec playwright test` completed
**15 passed, 1 skipped** in 33.8 seconds. The skipped test is the explicitly
opt-in populated-store integration; that test separately passed **1/1** with
`MIDAS_SEED_FRONTIER_E2E=1`. The default run covered the Frontier, Arena,
Laboratory, Paper, Readiness, Reality, and Veritas browser paths. No public
source request or order was submitted.

At `2026-10-28T07:05:07Z`, memory PSI avg10 remained **0.00% some / 0.00% full**,
while I/O PSI rose to **1.09% some / 0.88% full**; available memory was about
10 GiB, swap free about 0.52 GiB, and the shared lock had no holder. Because
the I/O `some` value crossed the strict 1% threshold after the run, no further
resource-bearing check followed. This browser evidence remains local-interface
verification; source-use holds, live second-venue validation, and production
eligibility are unchanged.

## Laboratory/Arena integration checkpoint — 2026-10-28 07:13 UTC

The Laboratory now exposes a read-only **Frontier research** tab over the
existing Arena discovery study catalog and saved-result endpoint. It supports
selection among retained jobs and displays scope summaries, pairwise scope
deltas, and pinned reproducibility identities only after the API returns its
integrity-verified artifact. The frontend does not create another campaign or
admit a worker. It does not convert Frontier's multi-market inputs to the
Laboratory's single-market episode schema; that conversion would need an
explicit lossless economic contract. The Frontier workspace remains the entry
point for submitting discovery comparisons through Arena's normal admission.

The initial implementation passed the focused Laboratory component file
**4/4**, the full frontend unit suite **43/43**, and TypeScript project check.
Component tests mocked the Arena API, asserted older-job selection, verified
identity display and integrity-result withholding, and confirmed navigation.
During final review, job selection was moved into a valid nested button so the
card no longer puts block elements inside a button. At this checkpoint the
change and its browser case were not yet rechecked; final results appear below.
Commit `afcc726` adds a fixture-routed Playwright case for retained-job
selection, integrity-gated rendering, and no source or Arena mutation requests.

Commit `a875ee2` adds a stronger opt-in path. The temporary E2E seeder creates
a Polymarket-only Frontier discovery snapshot, result artifact, and completed
Arena job manifest through the content-addressed artifact APIs. The new
Playwright scenario reads the listing and verified result from the real local
Arena API and opens the same artifact in Laboratory. It performs no source
request and starts no Arena worker. This is controlled synthetic evidence,
clearly versioned as an E2E fixture, and the new seeded scenario has not been
executed yet.

At `2026-10-28T07:12:59Z`, memory PSI avg10 was **47.23% some / 42.98% full**,
I/O PSI avg10 **0.75% some / 0.74% full**, with about **10 GiB** available.
The lock check at that time inspected the Frontier worktree's relative
`data/arena` path and did not establish the protected shared lock state. No
resource-bearing checks followed because memory pressure was above the
admission threshold. This is a time-specific sample. The UI test did not read
a persisted Arena store or contact any source.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Laboratory read-only Frontier study history | PARTIALLY VERIFIED AT THIS CHECKPOINT | Initial component/unit/type checks pass; the later markup and persisted-store/API results appear below. |
| Legacy Laboratory campaign execution of Frontier snapshots | DEFERRED | No lossless mapping from multi-market Frontier payoffs to single-market `MarketEvent` episodes is defined. |
| Arena worker/admission path | PARTIALLY VERIFIED | This change only reads existing Arena routes; it adds no worker completion or live resource evidence. |
| Project Frontier overall | PARTIALLY VERIFIED | Live cross-venue semantic evidence, held-source access, broader science/resource gates, and deployment remain incomplete. |

Changed files in this checkpoint include
`apps/web/src/LaboratoryFrontierResearch.tsx`, `Laboratory.tsx`,
`Laboratory.test.tsx`, `App.tsx`, `styles.css`, and
`apps/web/e2e/laboratory.spec.ts`, plus the Laboratory,
Frontier architecture, operations, development, current-state, mission-ledger,
and report documentation. No source endpoint, production service, or protected
data store was accessed.

Commit identities on `codex/frontier-20261026`:

- `d396589` — Laboratory study-history UI, selection, and integrity-gated summary.
- `8227f34` — Laboratory/Frontier architecture and status documentation.
- `afcc726` — Fixture-routed Laboratory browser scenario.
- `87ef08e` — Record that final markup and browser checks were pending.
- `91e61d7` — Expand the reproducibility disclosure before the visible-value assertion.
- `a1e5687` — Pin integration commit identities in the report and ledger.
- `8c5ffbc` — Correct the protected shared-lock path and record the live holder.
- `a875ee2` — Seed a persisted fixture Arena study and add actual API/browser inspection.
- `9d8d98b` — List documentation follow-up commit identities.
- `aa8483b` — Correct the fixture manifest and improve E2E failure diagnostics.
- `5472d15` — Record the persisted Arena browser validation checkpoint.

The working tree was clean at `91e61d7`. The commits remain local to the
isolated Frontier branch; there was no merge, push, or deployment.

## Protected host admission recheck — 2026-10-28 07:17 UTC

At `2026-10-28T07:17:18Z`, the correct shared Arena lock at
`/home/charlie/midas/data/arena/.global-admission.lock` was held by PID
**124298**, the `midas-veritas-gap-detail-v2.service` worker. It was left
untouched. Memory PSI avg10 was **36.43% some / 28.38% full**, and I/O PSI
avg10 **0.02% some / 0.02% full**. Resource-bearing verification remains
deferred until memory pressure clears and the same protected lock is free. The
earlier relative-path check in this worktree did not prove the shared lock was
free. No protected API, source, store, or service was changed.

## Frontier E2E admission recheck — 2026-10-28 07:21 UTC

The source-independent persisted-Arena browser test and temporary seeder were
added in `a875ee2`; neither has been executed. At `2026-10-28T07:21:58Z`,
memory PSI avg10 was **39.28% some / 20.15% full**, I/O PSI was **0.00%**, and
about **10 GiB** was available. PID **124298** still held the protected shared
Arena lock under `midas-veritas-gap-detail-v2.service`. The protected batch was
left untouched. No build, test, browser, source, or production operation was
started after this measurement. Revalidate memory PSI and the exact lock path
before running even the isolated browser suite.

## Laboratory/Arena persisted-study verification — 2026-10-28 07:30 UTC

After the Veritas batch exited, a controlled opt-in browser run exercised the
seeded Frontier history and saved Arena discovery artifact. The seeder stores a
single-market Polymarket fixture, result artifact, and completed manifest under
a validated temporary browser root. The API then verifies the saved result
against its snapshot and manifest; the Laboratory view loads the real local API
routes. No Arena worker, exchange call, or production store is involved. The
fixtures establish storage/API/UI wiring, not live source quality or a genuine
cross-venue relationship.

Two preparation defects were caught and corrected: the discovery snapshot
builder needs an explicit empty verified-relationship tuple, and the completed
job manifest needs `exit_status: 0`. After those fixes, verification passed:

- Focused Laboratory component tests: **4/4**; full frontend unit suite: **43/43**.
- TypeScript, ESLint, Prettier, and Ruff check/format check passed.
- Production frontend build passed with 2,229 modules; existing 511.30 kB main
  and 544.41 kB Chart chunk advisories remain.
- Explicit seeded browser/API run: **2/2 passed**.
- Fixture-routed Laboratory browser case: **1/1 passed**, including no source
  probe and no Arena mutation request assertions.
- Complete default browser suite: **16 passed, 2 skipped**; both seeded cases
  were intentionally opt-in and passed separately.

At the post-run sample `2026-10-28T07:28:12Z`, memory PSI avg10 was **0.00%
some / 0.00% full**, I/O PSI avg10 **0.01% some / 0.01% full**, available
memory about **10 GiB**, and no process held the protected shared Arena lock.
The external Veritas worker remained untouched throughout.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Laboratory saved Frontier study inspector | COMPLETE AND VERIFIED | Component, full frontend, type, lint, format, build, and browser checks pass. |
| Persisted Arena result through API and Laboratory UI | COMPLETE AND VERIFIED | Actual local API validates a content-addressed temporary fixture before UI display. No supervised worker or live source is involved. |
| Live market/cross-venue validation | BLOCKED | Test evidence is synthetic and Polymarket-only; live source-use holds remain. |
| Project Frontier overall | PARTIALLY VERIFIED | Live equivalent exposures, source permission, broader resource/science acceptance, and deployment remain open. |

Commits `a875ee2` and `aa8483b` contain the seeded Arena fixture path and its
contract fixes. These commits are local to `codex/frontier-20261026`; there was
no merge, push, deployment, public source request, or protected-store change.

## Mission Control workspace bundle refinement — 2026-10-28 07:35 UTC

Commit `87a6a3c` makes Laboratory, Arena, and Reality lazy-loaded workspaces in
`apps/web/src/App.tsx`, each with a visible loading state. The production build
emits dedicated chunks for those workspaces. The JavaScript entry chunk fell
from the previously recorded **511.30 kB** to **367.85 kB** (about 28%). The
separate Chart/ECharts chunk remains **544.41 kB** and above Vite's advisory
threshold. Because Mission Control displays a chart on its initial view, this
is an entry-chunk reduction, not a same-sized reduction in full initial page
transfer.

The updated production build passed (2,229 transformed modules), as did all
**43** web unit tests, the default browser suite (**16 passed, 2 opt-in seeded
tests skipped**), ESLint, and Prettier. The two seeded scenarios were then run
explicitly after the App change and passed **2/2**, including the persisted
Frontier artifact API and lazy Laboratory view. TypeScript is included in the
passing production build. At `2026-10-28T07:35:37Z`, host memory PSI avg10 was
0.00% some/full and I/O PSI avg10 was **0.44% some / 0.28% full**; approximately
**10 GiB** was available and no process held the shared Arena lock. Both
browser runs used temporary local API/storage roots; no exchange endpoint or
production service was accessed.

| Component | Status | Current evidence and remaining boundary |
| --- | --- | --- |
| Separate loading of Laboratory, Arena, and Reality | COMPLETE AND VERIFIED | Build output has separate chunks, and the full unit and browser regressions pass. |
| Entry JavaScript bundle | COMPLETE AND VERIFIED | 367.85 kB, down about 28% from the prior 511.30 kB measurement. |
| Chart/ECharts bundle | PARTIALLY VERIFIED | Build passes; its 544.41 kB warning remains, and Mission Control loads it for its initial chart. |
| Frontier overall | PARTIALLY VERIFIED | Genuine live cross-venue equivalence/economics and deployment prerequisites remain open. |

## Candidate observation timestamp contract — 2026-10-28 07:37 UTC

The scientific code review found that `OpportunityCandidate.observed_at_utc`
accepted a naive datetime even though normalized evidence times elsewhere
require timezone information. Independent timing code converts candidate time
to epoch milliseconds; Python interprets a naive value in the host's local
timezone. This could shift the audit's freshness calculation by the host UTC
offset for malformed or legacy candidate data.

Commit `92ab4e8` adds a model validator that rejects a missing timezone and
normalizes aware timestamps to UTC. Its regression test checks both behaviors.
The full affected module `tests/frontier/test_relationships_economics_replay.py`
passes **50/50**. Strict mypy passes for `packages/midas/frontier/economics.py`;
Ruff check and format checks pass for the changed source and test files. At
`2026-10-28T07:37:17Z`, memory PSI avg10 was 0.00%, I/O PSI avg10 was **0.01%
some / 0.00% full**, approximately **10 GiB** was available, and the shared
Arena lock was unheld. No live source, protected store, or production service
was accessed. Broader post-change regression is still pending.

| Component | Status | Current evidence and remaining boundary |
| --- | --- | --- |
| Candidate timestamp validation | COMPLETE AND VERIFIED | Naive values are rejected and aware offsets normalize to UTC; 50 economics/replay tests pass. |
| Full Frontier regression after this fix | PARTIALLY VERIFIED | The affected module passes; the complete suite has not been rerun after this narrow change. |
| Project Frontier overall | PARTIALLY VERIFIED | Live cross-venue equivalence, held-source permissions, broader production gates, and deployment remain incomplete. |

## Fee and raw-observation time validation — 2026-10-28 07:39 UTC

The timestamp audit then found two fee applicability fields and two raw
observation fields that still accepted naive datetimes. Fee evaluation compares
`effective_at_utc` and `expires_at_utc` with aware replay times; naive input
could raise during candidate generation or independent audit. Raw request and
receipt times are part of content-addressed source evidence, so accepting an
implicit host-local timezone would make their temporal meaning ambiguous.

Commit `a7df7e9` validates all three `FeeSchedule` timestamps (evidence,
effective, and expiry) and both `RawObservation` timestamps (request start and
response receipt). Naive timestamps are rejected, and aware offsets normalize
to UTC. The affected economics/replay and storage modules pass **73/73**.
Strict mypy passes for the two changed model/economics modules; Ruff check and
format check pass for the changed source and tests.

At `2026-10-28T07:39:41Z`, memory PSI avg10 was **0.00% some/full**, I/O PSI
avg10 was **2.52% some / 1.96% full**, approximately **10 GiB** was available,
and the shared Arena lock was free. The broader test slice was deferred because
I/O pressure was above the repository's 1% admission threshold. No production
service, protected store, worker, or source was accessed.

| Component | Status | Current evidence and remaining boundary |
| --- | --- | --- |
| Fee schedule applicability timestamps | COMPLETE AND VERIFIED | Naive evidence/effective/expiry times reject; aware times normalize to UTC. |
| Raw response timestamp contract | COMPLETE AND VERIFIED | Request and receipt times reject naive values and normalize aware offsets. |
| Broader regression after model changes | PARTIALLY VERIFIED | 73 affected tests pass; adapter/API and remaining Frontier modules are pending lower I/O pressure. |
| Project Frontier overall | PARTIALLY VERIFIED | Live cross-venue science, source permissions, full resource/recovery evidence, and deployment remain open. |

## Arena snapshot-builder timestamp guard — 2026-10-28 07:42 UTC

The timestamp review extended to three Arena `make_snapshot` functions. The
paired replay and discovery-scope builders serialize `as_of_utc` after calling
`astimezone(UTC)`; the event-time builder does the same for its replay cutoff
sequence. Without an earlier awareness check, a naive datetime is interpreted
using the host local timezone and can be silently shifted before the snapshot
hash is generated.

Commit `6d5e82b` adds an explicit timezone-awareness check before conversion in
all three builders. Aware timestamps still normalize to UTC. The affected
Arena test modules pass **25/25**, including naive input rejection for replay,
discovery, and timeline snapshots. Strict mypy passes for the three changed
Arena modules, and Ruff check/format pass. The existing Starlette/httpx
`TestClient` deprecation warning remains.

At `2026-10-28T07:42:38Z`, memory PSI avg10 was **0.00% some/full**, I/O PSI
avg10 was **1.64% some / 1.08% full**, about **10 GiB** was available, and the
shared Arena lock was free. The broader suite remains deferred until I/O
pressure is below the 1% admission threshold. No source, production service,
protected store, or Arena worker was touched.

| Component | Status | Current evidence and remaining boundary |
| --- | --- | --- |
| Paired replay snapshot time input | COMPLETE AND VERIFIED | Naive values reject before normalization; targeted module passes. |
| Discovery-scope snapshot time input | COMPLETE AND VERIFIED | Naive values reject before normalization; targeted module passes. |
| Event-time snapshot cutoff input | COMPLETE AND VERIFIED | Naive cutoffs reject before normalization; targeted module passes. |
| Broader regression after timestamp audit | PARTIALLY VERIFIED | Targeted economics/storage/Arena modules pass; adapter/API and full suite are deferred by I/O admission. |
| Frontier overall | PARTIALLY VERIFIED | Live multi-venue equivalence, source permissions, complete production readiness, and deployment remain incomplete. |

## Lazy workspace failure containment — 2026-10-28 07:47 UTC

Commit `8f5bf83` wraps the seven lazy Mission Control workspaces in a shared
error boundary outside Suspense. A rejected import or descendant render failure
is now contained to its workspace and displayed as an accessible alert with a
refresh instruction. The error boundary does not claim an in-place retry; it
preserves the surrounding Mission Control shell.

Verification on the isolated Frontier worktree:

- Frontend unit tests: **44/44 passed**, including the error-boundary case.
- TypeScript project build, ESLint, and Prettier check: passed.
- Production frontend build: passed, with **2,229 modules transformed**.
- Default Playwright suite: **16 passed**, **2 expected seeded-only skips**.
- Seeded Frontier/Arena Playwright suite: **2/2 passed** against disposable
  temporary stores, including the saved Arena discovery artifact in
  lazy-loaded Laboratory.
- Generated JS chunks include a **368.13 kB** entry, **182.75 kB** Frontier,
  and the existing **544.41 kB** Chart/ECharts chunk. Vite still warns about
  Chart's minified size; the initial Mission Control view loads that chart, so
  the entry reduction must not be represented as an equivalent initial
  transfer reduction.

The latest admission sample at `2026-10-28T07:47:03Z` reported memory PSI
avg10 **0.00% some/full**, I/O PSI avg10 **0.07% some / 0.04% full**, and
approximately **10 GiB** available. Browser APIs were configured for local
demo mode with temporary SQLite, Frontier, and Arena roots. No external source,
protected database, production service, or worker was accessed.

| Component | Status | Current evidence and remaining boundary |
| --- | --- | --- |
| Lazy workspace load feedback and failure containment | COMPLETE AND VERIFIED | Seven workspace boundaries; unit, full browser, and seeded persisted-artifact cases pass. |
| Frontend build and workspace splitting | PARTIALLY VERIFIED | Build passes; 544.41 kB Chart chunk warning remains and loads for initial Mission Control. |
| Frontier project acceptance | PARTIALLY VERIFIED | This UI reliability checkpoint does not close live equivalent-market, source-policy, broad resource, production-recovery, or deployment requirements. |

## Independent audit timezone guard — 2026-10-28 07:58 UTC

Commit `e1946bc` advances the independent economic verifier from v12 to v13.
The verifier now recursively checks the typed candidate, scenario, selected
markets and pinned books, relationship evidence, and joint-state map for naive
timestamps before it performs any fee, relationship, resolution, or timing
arithmetic. This protects against malformed reconstructed models created with
Pydantic `model_copy(update=...)`, which bypasses field validation. For an
evaluated candidate with legs, invalid timestamps return an `INCOMPLETE` audit
rather than allowing Python to infer a host-local timezone. The epoch conversion
helper also rejects a non-datetime value. The v13 identifier is included in the
audit input hash so it cannot be mistaken for a prior verifier result.

Verification evidence:

- Economics/replay and storage modules: **74/74 passed** after recursive
  timestamp preflight was added. The final `isinstance` hardening in the epoch
  helper followed that run; a post-hardening rerun is pending admission.
- Full Frontier API module after the final code commit: **56/56 passed**. This
  includes paired replay, multi-outcome, payoff-basket, joint-state, readiness,
  and persistence/API paths.
- Strict mypy for `independent_audit.py` and `models.py`, Ruff check, Ruff
  format check, and `git diff --check`: passed on final source.
- The API suite emitted the existing Starlette/httpx `TestClient`
  deprecation warning.

At `2026-10-28T07:57:51Z`, memory PSI avg10 was **0.00% some/full**, I/O PSI
avg10 was **7.28% some / 5.30% full**, approximately **10 GiB** was available,
and no Arena lock holder was present. Additional tests are deferred until I/O
avg10 returns below the 1% admission threshold. The change accessed no public
source, production service, worker, or protected store.

| Component | Status | Current evidence and remaining boundary |
| --- | --- | --- |
| Independent audit timestamp validation | COMPLETE AND VERIFIED | Candidate and pinned-book naive-time regressions return incomplete; final API module and static checks pass. |
| Exact-commit economics/storage module rerun | PARTIALLY VERIFIED | 74 cases passed after recursive preflight; the final runtime type guard still needs that bounded rerun. |
| Frontier project acceptance | PARTIALLY VERIFIED | This integrity fix does not establish live economic equivalence, unrestricted source permission, production recovery, or deployment eligibility. |

## Price-history replay input revalidation — 2026-10-28 08:02 UTC

Commit `dd4882d` makes the descriptive price-history replay validate every
bounded capture again from `model_dump(mode="python")` before it sorts,
compares, hashes, or converts timestamps to epoch seconds. This specifically
closes a nested `model_copy(update=...)` path that could place a naive point in
an otherwise validated `PriceHistoryReplayInput`. The normalized replay
identity advances to `frontier-price-history-replay-2`; persisted store schema
and historical rows remain unchanged.

Verification on the final code:

- `tests/frontier/test_historical_replay.py`: **5/5 passed**, including the
  nested naive-time regression, deterministic ordering, immutable persistence,
  and schema-six migration.
- The fixture-backed Polymarket price-history API probe/replay case: **1/1
  passed** with its transport mocked.
- Ruff, Ruff format, strict mypy for `historical_replay.py`, and
  `git diff --check`: passed.
- The API test emitted the existing Starlette/httpx `TestClient` deprecation
  warning.

At `2026-10-28T08:01:50Z`, memory PSI avg10 was **0.00% some/full** and I/O PSI
avg10 was **1.09% some / 0.68% full**, with approximately **10 GiB** available.
Because I/O `some` was slightly above the 1% gate, no additional suite was
started from this checkpoint. No live source, worker, protected store, or
production service was accessed.

| Component | Status | Current evidence and remaining boundary |
| --- | --- | --- |
| Reconstructed price-history input handling | COMPLETE AND VERIFIED | Nested naive points are rejected by model revalidation before replay arithmetic and hashing. |
| Price-history replay/API integration | COMPLETE AND VERIFIED | Five replay tests and one mocked API replay case pass; new outputs are version 2. |
| Frontier project acceptance | PARTIALLY VERIFIED | Live equivalent-market evidence, held-source approvals, broad resource/recovery, and deployment remain outstanding. |

## Exact-tree timestamp regression checkpoint — 2026-10-28 08:03 UTC

This checkpoint supersedes the preceding note that the final economics/storage
rerun was still pending. On the exact current code, the economics/replay,
storage, and historical-replay test modules pass **79/79** together. This
includes the final runtime type guard in independent audit v13, the
candidate/book `model_copy` naive-time regressions, and the nested historical
price-point rejection in replay v2.

The full `tests/frontier/test_api.py` module passed **56/56** after audit v13.
After the replay v2 change, its fixture-backed price-history probe/replay case
passed **1/1**. Strict mypy passes for `independent_audit.py`, `models.py`, and
`historical_replay.py`; Ruff and Ruff format checks pass for all changed Python
sources and tests. `git diff --check` passes. The API tests emit the existing
Starlette/httpx `TestClient` deprecation warning.

At `2026-10-28T08:02:44Z`, memory PSI avg10 was **0.00% some/full**, I/O PSI
avg10 was **0.15% some / 0.00% full**, approximately **10 GiB** was available,
and the shared Arena lock was free. No live source, worker, protected store, or
production service was accessed. Earlier post-run I/O samples were elevated,
so no extra broad suite was scheduled.

| Component | Status | Current evidence and remaining boundary |
| --- | --- | --- |
| Independent economic audit time safety | COMPLETE AND VERIFIED | Final affected module and full API module pass; naive typed evidence fails closed. |
| Descriptive price-history replay | COMPLETE AND VERIFIED | Final five-case module and route-level API test pass; new replay identity is v2. |
| Timestamp regression slice | COMPLETE AND VERIFIED | 79 relevant tests pass on the exact current code. |
| Frontier overall acceptance | PARTIALLY VERIFIED | Full single-process suite, live equivalent markets, held-source permission, resource endurance, and production deployment remain open. |

## Adapter timestamp parser regression — 2026-10-28 08:04 UTC

Commit `2eff73e` adds a contract test for the existing shared adapter time
parser. The test verifies that timezone-naive ISO strings return no parsed
timestamp, explicit `+02:00` input normalizes to UTC, and `Z` input remains UTC.
This protects source-time evidence from host-local interpretation without
changing adapter behavior or requesting live data.

`tests/frontier/test_adapters.py` passes **68/68**. Ruff, Ruff format, and
`git diff --check` pass. All venue HTTP behavior in the module is driven by
mocked transports; the new test calls only `parse_time`. At
`2026-10-28T08:04:42Z`, memory PSI avg10 was **0.00% some/full**, I/O PSI avg10
was **0.02% some / 0.00% full**, with approximately **10 GiB** available. No
live source, worker, protected store, or production service was accessed.

| Component | Status | Current evidence and remaining boundary |
| --- | --- | --- |
| ISO timestamp parsing contract | COMPLETE AND VERIFIED | Naive source time remains missing; explicit timezones normalize to UTC; adapter fixture module passes. |
| Live timestamp behavior | IMPLEMENTED, LIVE VALIDATION PENDING | No live source probe was performed under the current source-use boundary. |
| Frontier project acceptance | PARTIALLY VERIFIED | This parser test does not close live cross-venue, source-policy, resource/recovery, or deployment gates. |

## Full Frontier suite resource-gated attempt — 2026-10-28 08:07 UTC

The final tree collected **378 tests** under `tests/frontier`. I started one
single-process fixture-backed run after a preflight sample showed memory PSI
avg10 **0.00%**, I/O PSI avg10 **0.19%**, and approximately **10 GiB**
available. After **193 tests passed**, a live host sample showed I/O PSI avg10
had risen to **12.91% some / 10.15% full**. I sent SIGINT to stop the run.
Pytest exited 2 with `KeyboardInterrupt`; no failures were reported in the 193
completed cases, and the remaining 185 cases did not run.

`/usr/bin/time -v` reported **68.97 seconds** wall time and **347,088 KiB**
maximum RSS, with zero process swaps. A post-stop sample showed memory PSI
avg10 **0.00%**, I/O PSI avg10 **4.49% some / 3.33% full**, and approximately
**10 GiB** available. I/O pressure persisted after the test process ended.
No public network source, production service, worker, protected store, or Arena
job was started. The suite uses local fixtures and temporary test state.

| Component | Status | Current evidence and remaining boundary |
| --- | --- | --- |
| Completed portion of full Frontier suite | PARTIALLY VERIFIED | 193 cases passed before resource-gated interruption. |
| Full single-process Frontier suite | PARTIALLY VERIFIED | 185 collected cases remain unrun; retry waits on a fresh low-I/O sample. |
| Frontier overall acceptance | PARTIALLY VERIFIED | This run does not establish full regression, live cross-venue science, resource endurance, or deployment readiness. |

## Nested price-history point revalidation — 2026-10-28 08:09 UTC

Commits `2e73476` and `aa88b03` close and type-check a nested-instance
validation fix in the canonical `PriceHistorySeries` model. Pydantic's default nested-instance behavior could
skip validation for a previously constructed `HistoricalPricePoint`, including
an instance changed with `model_copy(update=...)`. The series validator then
used `.timestamp()` for range checks, so a copied naive timestamp could be
interpreted in the host timezone. The same bypass could admit an invalid price.

A field pre-validator now serializes nested point instances to Python payloads
before normal nested parsing. Existing UTC and `SettlementScalar` bounds are
therefore rerun before the series order/range checks. The historical replay
module passes **6/6**, the adapter module passes **68/68**, and the targeted
history-probe/replay API case passes **1/1**. Strict configured mypy passes for
`models.py`. Ruff check, Ruff format, and `git diff --check` pass. The six-case module completed in **1.81 seconds**,
maximum RSS **57,708 KiB**, with zero process swaps. At
`2026-10-28T08:11:12Z`, memory PSI avg10 was **0.00%**, I/O PSI avg10 was
**0.90% some / 0.74% full**, and approximately **10 GiB** was available. Tests
used temporary or mocked state and accessed no live source, worker, protected
store, or production service. The API test emitted the existing
Starlette/httpx `TestClient` deprecation warning.

| Component | Status | Current evidence and remaining boundary |
| --- | --- | --- |
| Nested historical price-point validation | COMPLETE AND VERIFIED | `PriceHistorySeries` reparses nested model payloads; historical replay, adapter, and targeted API tests pass. |
| Full single-process Frontier suite | PARTIALLY VERIFIED | 193/378 cases passed before a measured I/O-pressure stop; 185 cases remain unrun. |
| Frontier overall acceptance | PARTIALLY VERIFIED | This guard does not close live cross-venue, source-policy, broad resource/recovery, or deployment gates. |

## Held-capture test guard — 2026-10-28 08:13 UTC

I attempted an offline adapter-to-relationship regression using an existing
capture under `data/frontier/live-probes`. The test harness intercepted the
read in `tests/frontier/conftest.py` and raised
`PermissionError: Frontier tests may not access held source captures` before
the artifact was read. The one-case run therefore exited 1; this was a policy
guard, not an adapter or relationship assertion failure. No network request,
service, worker, or protected store was accessed. I removed the temporary test
and did not copy or repackage the capture to work around the guard.

The repository retains synthetic event-group coverage that checks the
relationship proposer emits only a `TEXT_CANDIDATE` hypothesis and leaves both
payoff and resolution unverified. That does not establish a relationship from
the held public capture or a verified cross-venue economic match. Source-use
authorization and the full suite remain separate open gates.

## Full Frontier suite pass on tmpfs — 2026-10-28 08:18 UTC

The three migration-test failures from the first tmpfs run were stale literal
expectations of schema `6`. The current store defines `SCHEMA_VERSION = 7`
and migrates old schemas to that version. I updated the migration assertions to
compare with the single source-of-truth constant; storage behavior was not
changed. The exact final tree then passed **379/379** tests in one process.

The test run took **29.51 seconds** (31.00 seconds process wall time) and
emitted one existing Starlette/httpx `TestClient` deprecation warning. Pytest
temporary files were placed under
`/dev/shm/midas-frontier-pytest-20261028-0817` to reduce disk I/O. Maximum RSS
was **378,216 KiB**, swaps **0**, filesystem input **0**, and filesystem output
544 blocks. Pre-run pressure at `2026-10-28T08:17:18Z` was memory PSI avg10
**0.00%**, I/O PSI avg10 **0.02%**, with about **10 GiB** available. After the
run, at `08:18:01Z`, memory PSI remained **0.00%** and I/O PSI avg10 was
**0.02% some / 0.00% full**. No source, worker, production service, protected
store, or Arena job was accessed or started.

| Component | Status | Current evidence and remaining boundary |
| --- | --- | --- |
| Full Frontier Python suite | COMPLETE AND VERIFIED | 379/379 tests pass against the final Frontier code and tests in one process. |
| Broader MIDAS and browser regression | PARTIALLY VERIFIED | This suite does not replace separate legacy, frontend, or end-to-end evidence. |
| Live cross-venue semantic/economic validation | BLOCKED | Held-capture test guard and unresolved source-use boundary remain. |
| Frontier overall acceptance | PARTIALLY VERIFIED | Deployment, production recovery, and genuine cross-venue evidence remain open. |

### October 28 continuation change inventory

| Commit | Files | Change |
| --- | --- | --- |
| `2eff73e` | `tests/frontier/test_adapters.py` | Pin naive ISO rejection and UTC offset normalization. |
| `2e73476` | `packages/midas/frontier/models.py`; `tests/frontier/test_historical_replay.py` | Revalidate nested historical price points before series timestamp checks; cover naive timestamp and invalid price copies. |
| `aa88b03` | `tests/frontier/test_historical_replay.py` | Add the strict test return annotation. |
| `f5dfb26` | `tests/frontier/test_relationship_reviews.py` | Compare migration results against the current `SCHEMA_VERSION` constant. |
| `3ce0984`, `9e1649c` | `docs/MIDAS_CURRENT_STATE.md`; `docs/frontier/FRONTIER_ARCHITECTURE.md`; `docs/frontier/FRONTIER_ENGINEERING_REPORT.md`; `docs/frontier/FRONTIER_MISSION_LEDGER.md` | Record timestamp and nested-model validation contracts. |
| `300fdcf`, `0ec12f0`, `a3fd358`, `252e5be`, `e4f6c82` | `docs/MIDAS_CURRENT_STATE.md`; `docs/frontier/FRONTIER_ENGINEERING_REPORT.md`; `docs/frontier/FRONTIER_MISSION_LEDGER.md` | Record the resource-gated attempt, test evidence, held-capture boundary, typing, and full-suite result. |
| `5e20c7f` | `docs/frontier/FRONTIER_OPERATIONS.md` | Document the PSI admission gate and tmpfs-backed Frontier test command. |
| `5878235` | `docs/frontier/FRONTIER_ENGINEERING_REPORT.md` | Add this continuation change inventory. |
| `e26efab` | `packages/midas/frontier/discovery_comparison.py`; `economics.py`; `independent_audit.py`; `joint_economics.py`; `models.py`; `replay.py`; `timeline.py`; `tests/frontier/test_api.py`; `test_discovery_comparison.py`; `test_joint_state.py`; `test_logical_implication_economics.py`; `test_relationships_economics_replay.py`; `test_timeline.py` | Revalidate copied virtual execution assumptions at candidate, joint-state, audit, replay, paired replay, timeline, and comparison boundaries; pin economics/audit/replay/timeline/comparison versions. |
| `4ddcd11` | `docs/MIDAS_CURRENT_STATE.md`; `docs/frontier/FRONTIER_ARCHITECTURE.md`; `docs/frontier/FRONTIER_ENGINEERING_REPORT.md`; `docs/frontier/FRONTIER_MISSION_LEDGER.md` | Record the copied execution-scenario integrity gate. |
| `1dd0987` | `packages/midas/frontier/adapters/base.py`; `adapters/transport.py`; `models.py`; `tests/frontier/test_adapters.py` | Revalidate concrete adapter configuration bounds before adapter use or HTTP client creation. |
| `0ac1094` | `docs/MIDAS_CURRENT_STATE.md`; `docs/frontier/FRONTIER_ARCHITECTURE.md`; `docs/frontier/FRONTIER_ENGINEERING_REPORT.md`; `docs/frontier/FRONTIER_MISSION_LEDGER.md`; `docs/frontier/FRONTIER_OPERATIONS.md` | Record adapter resource-bound validation and exact 418-test evidence. |
| `c6dfff1` | `tests/frontier/test_coinbase.py` | Add a pending no-network regression for a copied config that attempts to clear Coinbase's source-use hold without the exact reviewed acknowledgement. |
| `ca14e37` | `packages/midas/frontier/adapters/base.py`; `packages/midas/frontier/adapters/coinbase.py`; `tests/frontier/test_coinbase.py` | Reject Coinbase hold clearing, generic config substitution, and mismatched injected transport config; keep offline adapter/API fixtures on a held config. |
| `92b5bf0` | `tests/frontier/test_adapters.py` | Pass the same bounded `KrakenSpotConfig` into the adapter and fixture transport under the new config-match invariant. |
| `782df89` | `apps/api/frontier.py`; `tests/frontier/test_coinbase.py` | Reject held sources in all 11 probe routes before adapter or transport work; replace the held Coinbase API success-path fixture with an HTTP 409/zero-request regression. |
| `9776427` | `apps/api/frontier.py`; `tests/frontier/test_coinbase.py` | Report `public_probe_enabled` as effective eligibility, including source-policy holds; assert held Coinbase source status. |
| `4b8c9f0` | `apps/api/frontier.py`; `tests/frontier/test_adapters.py`; `tests/frontier/test_collection.py` | Return the validated source config from the API guard for type narrowing; align Kalshi config bounds and preserve held Coinbase collection config in offline journal tests. |
| `98704bb` | `docs/frontier/FRONTIER_ARCHITECTURE.md`; `docs/frontier/FRONTIER_OPERATIONS.md` | Document strict Coinbase source-use hold and fixture-only transport. |
| `2315615` | `docs/MIDAS_CURRENT_STATE.md`; `docs/frontier/FRONTIER_ENGINEERING_REPORT.md`; `docs/frontier/FRONTIER_MISSION_LEDGER.md` | Record the Kraken fixture config alignment. |
| `9577355` | `docs/MIDAS_CURRENT_STATE.md`; `docs/frontier/FRONTIER_ENGINEERING_REPORT.md`; `docs/frontier/FRONTIER_MISSION_LEDGER.md` | Record API source-use hold preflight and its regression evidence. |
| `afde92c` | `docs/frontier/FRONTIER_ENGINEERING_REPORT.md`; `docs/frontier/FRONTIER_MISSION_LEDGER.md`; `docs/MIDAS_CURRENT_STATE.md` | Record resource-gated Coinbase policy regression status. |
| `fbb46e4` | `docs/MIDAS_CURRENT_STATE.md`; `docs/frontier/FRONTIER_ENGINEERING_REPORT.md`; `docs/frontier/FRONTIER_MISSION_LEDGER.md` | Record the 11:53 status, full-suite result before the type-narrowing refactor, and PSI hold. |
| `597d9ff` | `docs/MIDAS_CURRENT_STATE.md`; `docs/frontier/FRONTIER_ENGINEERING_REPORT.md`; `docs/frontier/FRONTIER_MISSION_LEDGER.md` | Record strict-mypy success and exact-tree 420/420 verification. |
| `bf9d933` | `tests/laboratory/test_campaigns.py`; `tests/arena/test_frontier_replay.py` | Align isolated resource-gate inputs with current telemetry and pin replay relationship evidence to actual fixture observations. |

The temporary `tests/frontier/test_recorded_cross_venue_relationship.py` was
removed after the test guard denied held-capture access; it is not part of the
final tree or any commit.

### Legacy regression fixture corrections — 2026-10-28

Test commit bf9d933 records the two fixture-only corrections below.

The resource-aware legacy regression review found two stale test fixtures:

- Laboratory tests omitted available_cpu_count and host_load_avg1 from their
  ready resource snapshot. The current admission gate correctly failed closed.
  One denial test set CPU PSI to 99, although the gate deliberately decides
  host capacity from normalized load per available CPU because CPU PSI can be
  distorted by quota waits. The fixtures now match Arena's existing ready
  snapshot and use host_load_avg1=6 across six CPUs for deterministic denial.
- An Arena cross-venue replay test cited observation IDs that were not present
  in the two pinned fixture markets. The relationship verifier rejected the
  edge as unsupported evidence, so the replay summary correctly contained one
  invalid-edge candidate. The test now cites the exact pinned market
  observation IDs and asserts the relationship is verified before checking
  both payoff directions.

The final affected legacy slices pass: **153/153** unit/simulation/property
tests, **75/75** Laboratory tests, and **30/30** Arena admission plus Frontier
replay/timeline tests. Ruff, Ruff format, and git diff --check pass. Test
basetemps were isolated under /dev/shm; data/datasets inputs were read-only.
No production service, live source, or held capture was used.

At 2026-10-28T12:03:40Z, host memory PSI avg10 was 54.85% some / 49.81%
full; I/O PSI was 1.28% some / 1.22% full. About 10 GiB was available but
3.5/4 GiB of swap was already occupied. The redundant combined rerun and
unreviewed legacy modules were held because I/O PSI exceeded the 1% admission
threshold. The full MIDAS legacy suite therefore remains only partially
verified. Frontier overall remains **PARTIALLY VERIFIED**; this regression
work does not establish live cross-venue equivalence, production readiness, or
deployment eligibility.

### Coinbase hold-message correction — 2026-10-28

Code commit 9552db5 fixes user-facing source-policy text in the Coinbase
adapter. The old default message suggested that acknowledging the reviewed
Market Data Terms version was sufficient to lift the hold, but the source-use
review and validator require a separate validated permission and intended
scope. The updated message makes the active boundary explicit. The focused
offline Coinbase module passes **13/13**; Ruff and Ruff format pass. The run
used a tmpfs basetemp, zero swaps, no filesystem input, and no socket
messages. Memory PSI stayed at 0%; I/O PSI remained below 1% before and after.
Strict mypy passes for the changed adapter module. No live Coinbase request
or held record was accessed.

Changed in commit 9552db5: packages/midas/frontier/adapters/coinbase.py and
tests/frontier/test_coinbase.py. The change corrects the explanation only.
Coinbase probes remain blocked, and Frontier overall remains **PARTIALLY
VERIFIED**.

### Reality regression resource hold — 2026-10-28

A read-only review of the 14-test tests/test_reality.py module found its
recording and replay paths are temporary, its HTTP fixture is mocked, and its
WebSocket tests bind only to localhost. One case signals its own test-runner
process and is excluded from the next bounded run. The module was not run:
at 2026-10-28T12:08:02Z memory PSI avg10 was 50.74% some / 45.23% full and
I/O PSI was 0.84% some / 0.68% full. About 10 GiB was available, with 3.5/4
GiB swap occupied. A process listing showed PID 369790 running the Veritas
gap-detail batch; it was left untouched, and no causal attribution is made.

The Reality model regression remains deferred until memory and I/O PSI both
fall below the 1% admission threshold. This does not change the protection or
state of any Reality recording or Veritas process. Frontier overall remains
**PARTIALLY VERIFIED**.

### Reality model and panel regression slices — 2026-10-28

After the resource hold above, the isolated Reality model regression passed
**13/13** selected tests in 8.48 seconds; one test that signals its own
runner was deselected. It used a tmpfs basetemp, mocked HTTP, and ephemeral
localhost WebSockets, with 53,032 KiB peak RSS and zero swaps.
tests/test_reality_panel.py passed **26/26** in 0.24 seconds, with 46,876
KiB peak RSS and zero swaps; source discovery used MockTransport and an
in-memory recorder callback. No protected recording, live source, or service
was accessed.

The calibration test module was reviewed and found to use synthetic fixtures
without persistent roots, network, or subprocesses, but it was not run. At
2026-10-28T12:10:00Z, I/O PSI avg10 some was 1.04%, just above the 1%
admission threshold. The Reality model slice remains partial because the
self-signaling case was excluded; the calibration slice remains deferred.
Frontier overall remains **PARTIALLY VERIFIED**.

### Reality calibration and dashboard API regression — 2026-10-28

The synthetic Reality calibration module passed **18/18** tests, with 52,396
KiB peak RSS, zero swaps, and no socket messages. The isolated Reality
dashboard API module passed **14/14**, with 65,308 KiB peak RSS, zero swaps,
and no socket messages. Its router used pytest temporary roots; the
systemctl command path was mocked and no service command ran. The existing
Starlette/httpx TestClient deprecation warning remains.

At 2026-10-28T12:10:42Z before the dashboard run, memory PSI avg10 was 0.00%
and I/O was 0.60% some / 0.59% full. At 12:10:49Z afterward, memory remained
0.00% while I/O rose to 1.53% some / 1.35% full. Further tests were held at
that gate. Across the reviewed Reality slices, 71 tests pass and one
self-signaling case remains deselected. No recording, live source, or service
was accessed. Frontier overall remains **PARTIALLY VERIFIED**.

### Research-schedule test fixture correction — 2026-10-28

Test commit cd248ce updates a fixture that targeted the wrong module name.
The schedule test patched the top-level test_reality_foundry module, while
the dataset helper imports tests.test_reality_foundry; a read-only Python
probe confirmed they are distinct objects. The date changes therefore never
reached the generated tape, and the overlapping final-test-period guard
correctly failed closed on the second synthetic evaluation. The test now
patches the exact imported module and asserts distinct dataset identities.

The original isolated invocation lacked tests on PYTHONPATH and failed before
the pruning test body. A corrected import-path run reached the body and
reported three passed / one failed at the intentional overlap guard. No data
outside unique /dev/shm basetemps was changed. Ruff, format, and whitespace
checks pass for cd248ce. Runtime verification of that commit remains pending:
at 2026-10-28T12:12:41Z memory PSI avg10 was 44.70% some / 40.61% full.
The research-schedule module remains unverified on the corrected fixture.

## Collection journal write-boundary revalidation — 2026-10-28 13:21 UTC

Review of the isolated collector journal found three write methods that called
`initialize()` before reparsing typed input: `create_run`,
`create_run_with_initial_checkpoint`, and `append_checkpoint`. A malformed
copied Pydantic model could therefore create or mutate the journal schema
before being rejected. All three methods now revalidate and apply record-size
bounds before initialization. Checkpoint lookup and sequence checks use the
reparsed checkpoint instance.

The regression passes **1/1** in 0.45 seconds and proves invalid run specs and
checkpoints are rejected without creating the root directory. Peak RSS was
**61,960 KiB**, with zero swaps, filesystem input, and socket messages. Ruff
check/format, `git diff --check`, and strict mypy for `collection.py` pass.
At `2026-10-28T13:21:09Z`, memory PSI avg10 was **0.00%**, I/O PSI avg10 was
**0.00%**, and approximately **10.4 GiB** was available. CPU PSI avg10 was
**41.79%**, so module-wide and broader test runs remain deferred pending a
fresh resource sample. No collector, live source, protected store, or
production service was accessed.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Collection journal append input validation | COMPLETE AND VERIFIED | All three append paths reject malformed copied models before SQLite initialization; targeted regression, strict mypy, and lint/format pass. |
| Full collection module after this change | PARTIALLY VERIFIED | Not rerun while host CPU pressure is elevated; the focused regression passes. |
| Frontier project acceptance | PARTIALLY VERIFIED | Genuine live cross-venue equivalence, held-source permissions, production recovery, broad resource qualification, and deployment remain open. |

**Implementation commit:** `3153148` (`fix(frontier): validate collection writes before initialization`).

## Read-only collection journal lookup — 2026-10-28 13:23 UTC

The source-independent read-path review found `run_spec()` and `checkpoints()`
called the schema initializer. A GET-like lookup could therefore create an
empty journal or silently add schema to an incomplete database. Both methods
now use a bounded, schema-checked SQLite `mode=ro` connection. Missing journals
return the existing not-found/empty results without filesystem mutation;
incomplete or unsupported journals fail closed without repair.

The focused regression passes **1/1** in 0.45 seconds; peak RSS was **62,440
KiB**, with zero swaps, filesystem input, or socket messages. Strict mypy on
`collection.py`, Ruff check/format, and `git diff --check` pass. At
`2026-10-28T13:23:32Z`, memory PSI avg10 was **0.00%**, I/O PSI was **0.05%
some / 0.01% full**, and approximately **10.4 GiB** was available. Host CPU PSI
avg10 was **42.26%**, so the whole collection module and broader suites were
deferred. No source, collector, protected store, or production service was
accessed.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Collection run/checkpoint reads | COMPLETE AND VERIFIED | Missing and incomplete journal paths remain unchanged; one targeted regression, mypy, and lint/format pass. |
| Full collection module after journal changes | PARTIALLY VERIFIED | Only focused regressions were rerun while host CPU PSI remained elevated. |
| Frontier project acceptance | PARTIALLY VERIFIED | Genuine cross-venue evidence, held-source permission, broad resource qualification, production recovery, and deployment remain open. |

**Implementation commit:** `f440fa2` (`fix(frontier): keep collection journal reads read-only`).

## Official source-terms refresh — 2026-10-28 13:26 UTC

A read-only review refreshed the operational source-use boundaries against the
official terms and API notices. The current Kalshi Developer Agreement still
limits API use to a member's own trading and limits collection, aggregation,
and storage to that purpose. Kraken's API introduction says prior permission
is required for certain uses, including non-personal commercial use of public
market data. The Coinbase Market Data Terms remain dated 7 August 2026 and
restrict external display/dissemination, end-user apps, and specified AI/ML
uses without written consent. The Polymarket Institute research guide
distinguishes the decentralized and US exchanges and their separate APIs.
These findings support the existing source-use gates; they do not determine
the user's applicable terms or establish permission.

See the dated [source-data terms refresh](SOURCE_DATA_TERMS_REVIEW_2026-10-28.md)
for scope, limitations, and the official links. No source API was called,
no saved capture was opened, and no gate was changed. The existing Polymarket
integration remains distinct from the separate US exchange. Frontier's
cross-venue scientific acceptance remains **PARTIALLY VERIFIED** while
additional source-use permission and genuine equivalent-market evidence are
unavailable.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Current source terms review | COMPLETE AND VERIFIED | Official materials were refreshed read-only on 2026-10-28 and the dated review is linked from architecture and operations docs. |
| Kalshi, Kraken, and Coinbase source use | BLOCKED | Existing code gates and quarantines remain active; no permission was inferred from public endpoints or config values. |
| Genuine cross-venue equivalence | BLOCKED | No permitted live evidence establishes an equivalent multi-venue payoff. |

**Documentation commit:** `c9388b2`.

## Collection module regression after journal fixes — 2026-10-28 13:28 UTC

The complete `tests/frontier/test_collection.py` module now passes **29/29**
against commits `3153148` and `f440fa2`, covering the journal input and
read-only lookup fixes in their surrounding collector tests. Pytest time was
1.94 seconds (2.33 seconds wall); maximum RSS was **69,124 KiB**, with zero
swaps, filesystem input, or socket messages and 576 output blocks. Output and
SQLite test journals stayed under
`/dev/shm/midas-frontier-collection-module-20261028`.

Before the module at `13:28:17Z`, memory PSI avg10 was **0.00%**, I/O PSI was
**0.03% some / 0.03% full**, and approximately **10.5 GiB** was available.
Afterward at `13:28:47Z`, memory remained **0.00%**, I/O was **0.14% some /
0.03% full**, and approximately **10.4 GiB** remained available. CPU PSI was
still **44.54%**, so the full Frontier suite and broader repository regressions
remain deferred. The test uses fake adapters, temporary roots, and a bounded
local lock child; it makes no public-data request and touches no protected
service or evidence.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Collection journal append and read boundaries | COMPLETE AND VERIFIED | The complete 29-case collection module passes after both fixes; strict mypy, Ruff, and format checks also pass. |
| Full Frontier regression after journal fixes | PARTIALLY VERIFIED | The full suite was not rerun under sustained high host CPU pressure. |
| Frontier project acceptance | PARTIALLY VERIFIED | Live cross-venue evidence, held-source permission, broad resource qualification, production recovery, and deployment remain open. |

## Arena snapshot storage and path validation — 2026-10-28

Commit `4788443` hardens the three Frontier snapshot families in Arena:
replay, discovery, and timeline. Each `store_snapshot` now rebuilds and
validates the typed snapshot from JSON-mode `exclude_unset` data before any
size check or filesystem mutation, and takes the stored identity from that
validated object. This closes a `model_copy(update=...)` boundary where nested
objects could skip validation or a copied identifier could influence the
output path. Each loader also reparses its typed job specification before
using its identifier in a path. Timeline's schema-v1 field-set behavior is
retained during round trips.

Six focused tests passed on isolated tmpfs roots: four malformed-copy,
content-address, and timeline-compatibility cases passed in 1.72 seconds
(2.41 seconds wall, 193,700 KiB maximum RSS); two replay/discovery storage and
artifact-reconstruction happy paths passed in 1.60 seconds (2.27 seconds wall,
190,404 KiB maximum RSS). Both invocations recorded zero swaps, filesystem
input, and socket messages. The three Arena modules pass strict mypy; Ruff
check/format and `git diff --check` pass. The only output warning was the
existing Starlette/httpx `TestClient` deprecation warning. These tests used
temporary roots and did not access a collector, external source API, held
capture, protected store, production service, or persistent Arena job.

At `2026-10-28T13:35:05Z`, CPU PSI avg10 was 48.03%, I/O PSI was 0.21% some
and 0.00% full, memory PSI was 0.00%, and approximately 10 GiB was available.
The full Arena modules and full Frontier suite were not rerun under sustained
CPU pressure. The repository's latest previous full Frontier pass remains
379/379 at commit `f5dfb26`; it is not evidence that these later commits have
passed the entire suite.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Arena Frontier snapshot validation and path boundaries | COMPLETE AND VERIFIED | Six focused tests, strict mypy, Ruff check/format, and diff check pass across replay, discovery, and timeline. |
| Full Arena and Frontier regression after this fix | PARTIALLY VERIFIED | Focused cases pass; broad rerun deferred due to sustained host CPU PSI. |
| Frontier overall | PARTIALLY VERIFIED | Live cross-venue equivalence, source-use permissions, held-capture access, production recovery, and deployment gates remain unresolved. |

**Implementation commit:** `4788443` (`fix(arena): validate Frontier snapshot boundaries`).

## FrontierStore preflight before database initialization — 2026-10-28

Commit `c5b8822` moves input-only validation ahead of FrontierStore
initialization and migration for observations, relationship hypotheses,
relationship reviews, replay results, price-history replay results, and paired
comparisons. Encoded row bounds, replay budgets, and paired-run consistency
are checked before database schema creation. Observation writes pre-serialize
and bound the raw body plus normalized payload with its persistence provenance
stamp. Validation that depends on stored state remains transaction-bound.

The full `tests/frontier/test_storage.py` module passes **28/28** in 1.33
seconds (1.68 seconds wall), with **70,916 KiB** maximum RSS, zero swaps,
filesystem input, or socket messages, and 568 output blocks. It used the
isolated tmpfs root `/dev/shm/midas-frontier-storage-preflight-module-20261028`.
Strict mypy on `storage.py`, Ruff check/format, and `git diff --check` pass.
Regressions verify oversized relationship and combined observation rows,
invalid replay budgets, and mismatched paired comparisons leave the new store
path absent.

The combined full Frontier-plus-Arena snapshot regression was not run. At
`2026-10-28T13:39:57Z`, CPU PSI avg10 was 2.06%, I/O PSI was 1.27% some / 1.24%
full, and memory PSI was 0.00%; the I/O sample exceeded the 1% test-admission
gate. No source, held capture, protected store, collector, production service,
or historical evidence was accessed.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| FrontierStore write preflight | COMPLETE AND VERIFIED | Six append paths validate model and encoded-size constraints before initialization; the full 28-case storage module, strict mypy, and Ruff pass. |
| Frontier/Arena full regression after this commit | PARTIALLY VERIFIED | Touched module passes; combined regression deferred by measured I/O pressure. |
| Frontier overall | PARTIALLY VERIFIED | Live cross-venue equivalence, source-use permissions, held-capture access, production recovery, and deployment remain open. |

**Implementation commit:** `c5b8822` (`fix(frontier): preflight storage writes before initialization`).

## Independent audit behavior when position legs are absent — 2026-10-28

Commit `2d8e9fb` closes a stale-result path in
`independently_audit_candidate`. If a copied candidate loses all legs after
carrying a verified audit, positive economics, eligibility, or timing fields,
the no-leg result now clears those derived fields and sets the audit
disposition to `NOT_EVALUATED`. An existing verified, conditional, or
modeled-negative classification is downgraded to `INCOMPLETE_EVIDENCE`.
Clean candidates classified only as `PRICE_DISCREPANCY_ONLY` preserve that
classification because they make no payoff claim.

The focused no-leg regression passed **1/1** in 0.56 seconds (0.91 seconds
wall), with **68,076 KiB** peak RSS, zero swaps, filesystem input, or socket
messages, and 1,496 output blocks under the tmpfs root
`/dev/shm/midas-frontier-no-leg-audit-20261028`. Strict mypy on
`independent_audit.py`, Ruff check/format, and `git diff --check` pass.

The full 82-case `test_relationships_economics_replay.py` module was held. At
`2026-10-28T13:42:40Z`, CPU PSI avg10 was 0.98%, I/O was 0.31% some / 0.26%
full, and memory PSI was 48.10% some / 44.12% full. The memory gate was
exceeded; available host memory alone did not justify a test run. No exchange
source, capture, protected store, collector, production service, or historical
evidence was accessed.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| No-leg independent economic audit output | COMPLETE AND VERIFIED | Focused mutation regression and static checks pass; stale economic outputs are removed. |
| Full economics/replay regression after this change | PARTIALLY VERIFIED | One focused case passes; 81 sibling tests remain pending lower memory PSI. |
| Frontier overall | PARTIALLY VERIFIED | Source-use permissions, held-capture validation, genuine cross-venue equivalence, production recovery, and deployment remain open. |

**Implementation commit:** `2d8e9fb` (`fix(frontier): clear unaudited economics without legs`).

## Missing relationship-review store guard — 2026-10-28 13:46 UTC

Commit `ccc44ce` makes `append_relationship_review` reject a missing target
before creating the SQLite database or its root directory. A focused regression
asserts both paths remain absent. The regression and post-change storage module
have not run, and strict mypy/Ruff have not been rerun: the `13:46:08Z` sample
showed memory PSI avg10 at **35.83% some / 28.31% full**, CPU PSI at **29.19%**,
and I/O PSI at **0.09% some / 0.08% full**, despite about 9 GiB available.
Validation remains pending a fresh resource-admission sample. No source,
capture, collector, protected store, or production service was accessed.
Frontier remains **PARTIALLY VERIFIED**.

## Read-only review-target preflight — 2026-10-28 13:48 UTC

Commit `13377dc` closes the empty-database case left by the earlier missing-path
guard. Before `initialize()`, `append_relationship_review` now checks for the
relationship table and requested parent through `_read_connect()`. An absent
table or row returns the existing target-not-found error without schema
creation or migration. SQLite inspection errors are surfaced as a store error;
the write transaction still rechecks the parent after initialization. A second
regression asserts that an existing empty database remains byte-for-byte
unchanged. Neither focused regression, the storage module, nor strict
mypy/Ruff was run after the change.

At `2026-10-28T13:48:50Z`, memory PSI avg10 was **37.45% some / 28.85% full**,
CPU PSI **29.17%**, and I/O PSI **0.00%**. About 9 GiB was available, with
3.5 GiB swap in use; memory exceeds the documented 1% admission gate. No
source, capture, collector, protected store, or production service was accessed.
Frontier remains **PARTIALLY VERIFIED**.

## Review-store and independent-audit fail-closed verification — 2026-10-28 13:56 UTC

Commits `13377dc` and `76d388b` finish two bounded hardening changes. The
review writer now performs a read-only parent lookup before SQLite
initialization, so a missing target in an absent store or an existing empty
database does not create schema or advance a migration. The write transaction
rechecks the row. The independent audit clears prior candidate-derived payout,
cost, fee, P&L, capital, timing, and fill-sensitivity values when an invalid
scenario or missing pinned evidence prevents recomputation. It also disables
practical eligibility and returns `INCOMPLETE_EVIDENCE`; clean
`PRICE_DISCREPANCY_ONLY` candidates without legs remain unchanged. The audit
algorithm version was bumped to 23.

`tests/frontier/test_storage.py` passes **30/30** in 1.33 seconds (1.67 seconds
wall), at 68,232 KiB peak RSS, zero swaps, zero filesystem input, zero socket
messages, and 608 filesystem output blocks. The 83-case
`test_relationships_economics_replay.py` module passes **83/83** in 0.68
seconds (1.03 seconds wall), at 56,348 KiB peak RSS, zero swaps, input, or
socket messages, and 376 output blocks. Both used separate `/dev/shm` roots.

The complete `tests/frontier` suite passes **452/452** in 29.16 seconds (30.67
seconds wall), at 380,164 KiB peak RSS, with zero swaps, 224 filesystem input
and 376 output blocks, and no socket traffic. One existing Starlette/httpx
`TestClient` deprecation warning remains. Strict mypy passes on the three
changed production modules; Ruff check/format and `git diff --check` pass on
the five changed Python files.

At `13:55:22Z`, memory and I/O PSI avg10 were both **0%**, and approximately
**10 GiB** was available, although 3.5 GiB of swap was in use. Post-run at
`13:55:58Z`, both remained at **0%**; CPU PSI avg10 was 42.66% before and
32.88% after. No live source, capture, collector, protected store, service,
browser, or Arena job was accessed. This completes the Python verification for
these commits, not the Frontier mission. Live source authorization and
cross-venue evidence remain blocked; browser/Arena verification, production
recovery, and deployment remain outstanding. Frontier remains
**PARTIALLY VERIFIED**.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Review-target preflight | COMPLETE AND VERIFIED | Missing-store and existing-empty-database cases pass in the full storage module. |
| Independent audit fail-closed output | COMPLETE AND VERIFIED | Invalid-scenario and missing-evidence regressions pass; prior economics are cleared when no recomputation occurs. |
| Frontier Python suite on `76d388b` | COMPLETE AND VERIFIED | 452/452; one existing TestClient deprecation warning remains. |
| Live cross-venue relationship/economics | BLOCKED | Current source-use holds remain; no second-venue relationship is claimed. |
| Browser/Arena and production transition | DEFERRED | No browser or Arena run was needed for these backend changes; production remains isolated and undeployed. |

**Files and commits:** `packages/midas/frontier/storage.py` (`13377dc`),
`packages/midas/frontier/independent_audit.py`,
`packages/midas/frontier/models.py`, and
`tests/frontier/test_relationships_economics_replay.py` (`76d388b`), plus the
storage regressions in `tests/frontier/test_storage.py` (`13377dc`).

## Frontier dashboard and browser acceptance — 2026-10-28 13:59 UTC

At verified code commit `76d388b`, all frontend unit checks passed: Vitest
**47/47** across nine files, `tsc -b`, ESLint, and Prettier. The production Vite
build completed after transforming 2,230 modules. It reports one advisory:
`Chart` is **544.51 kB** minified (186.79 kB gzip), above the configured 500 kB
warning threshold. No UI code changed during this checkpoint.

The unseeded Frontier Playwright suite passed **7/7** tests in 17.8 seconds
(18.66 seconds wall, 201,120 KiB peak RSS, zero swaps). The separate seeded
suite passed **2/2** in 8.1 seconds (11.03 seconds wall, 183,388 KiB peak RSS,
zero swaps). Its seeder wrote 21 deterministic fixture captures and replay
artifacts plus one fixture-only Arena discovery artifact under
`/tmp/midas-browser-xRjN0g`. This was isolated test state; no collector or Arena
worker ran. The browser checks exercised responsive overview/graph views,
explicit saved-history replay, candidate/relationship details, and the seeded
Laboratory artifact path. The explicit history-probe UI action was fulfilled by
a Playwright route; no request reached a venue or collection endpoint. Uvicorn
and Vite bound only to loopback and stopped after each run; final port
inspection found no listeners on ports 18000 or 15173.

The Vitest run took 9.42 seconds wall and peaked at **323,972 KiB**. At
`13:58:51Z` before the seeded browser test, memory PSI avg10 was **0.00%** and
I/O PSI avg10 was **0.43% some / 0.21% full**, with about **9.8 GiB** available.
At `13:59:19Z`, memory PSI remained **0.00%**, I/O PSI was **0.08% some / 0.04%
full**, and no service listener remained. The build peaked at **686,100 KiB**,
with zero swaps and 5,880 filesystem output blocks. No external source, held
capture, protected store, or production service was accessed. The untracked
`data/frontier-public-probes/` directory remains untouched.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Frontier web unit and component tests | COMPLETE AND VERIFIED | 47/47 Vitest tests pass; nine test files. |
| Web typecheck, lint, format, and production build | COMPLETE AND VERIFIED | `tsc -b`, ESLint, and Prettier pass; Vite build succeeds with one large Chart chunk advisory. |
| Frontier browser flows | COMPLETE AND VERIFIED | Seven regular and two seeded browser tests pass using isolated local state only. |
| Genuine live cross-venue validation | BLOCKED | Source-use holds remain; no browser fixture is treated as a live observation. |
| Production transition | DEFERRED | The isolated branch remains undeployed; production recovery and deployment gates are separate. |

This closes the bounded Frontier dashboard verification, not the whole mission.
Source-use permission, genuine cross-venue evidence, broader Arena/production
readiness, and deployment remain unresolved; Frontier is **PARTIALLY VERIFIED**.

## Frontier Arena replay integration verification — 2026-10-28 14:00 UTC

The Frontier-specific Arena modules passed **28/28** tests in 3.86 seconds
(4.58 seconds wall), with **200,752 KiB** peak RSS, zero swaps, zero filesystem
input, zero socket messages, and 384 filesystem output blocks. They used
`/dev/shm/midas-frontier-arena-snapshots-20261028T1400Z`. One existing
Starlette/httpx `TestClient` deprecation warning remains.

Coverage included replay, event-time timeline, and discovery snapshot
serialization and loading; nested model and path validation; content hashes;
held-source catalog/result filtering; completed-job/artifact binding; and
network-restricted worker command assertions. The discovery test ran one
bounded fixture-only child process that exited within the test. No persistent
Arena job, long campaign, production Arena root, live source, collector, or
service was started or accessed.

At `14:00:17Z` before the test, memory and I/O PSI avg10 were **0.00%**, with
about **10 GiB** available (3.5 GiB swap was occupied). At `14:00:40Z` after
the test, memory and I/O PSI avg10 remained **0.00%**. CPU PSI avg10 was
44.38% before and 38.33% after. The full legacy Arena suite and broader MIDAS
regression were not run.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Frontier Arena replay/timeline/discovery integration | COMPLETE AND VERIFIED | Three targeted modules pass 28/28 against the integrated local APIs and bounded fixture worker. |
| Full legacy Arena/MIDAS regression | DEFERRED | No claim of full Arena or repository-wide regression is made. |
| Production Arena deployment | DEFERRED | Only test-owned temporary roots were used; production remains untouched. |

Frontier remains **PARTIALLY VERIFIED**: source-use authorization, genuine
cross-venue evidence, production recovery, and deployment still need separate
closure.

## Arena job-supervision regression and I/O admission stop — 2026-10-28 14:03 UTC

`tests/arena/test_jobs.py` passed **16/16** in 31.95 seconds (32.55 seconds
wall), with **180,988 KiB** peak RSS, zero swaps, 120 filesystem input blocks,
105,904 output blocks, and no socket traffic. Its isolated root was
`/tmp/midas-frontier-arena-jobs-20261028T1402Z`. Coverage includes cancelled
and stale-source workers, bounded artifact/disk accounting, supervisor state,
retry lineage, worker leases, and launch-command restrictions. A few tests
launch short-lived workers directly against their test-owned temporary roots;
all exited with the suite. No production systemd unit, persistent Arena job,
service, or collector was used.

At `14:02:23Z` before the run, memory and I/O PSI avg10 were **0.00%**, with
about **10 GiB** available. At `14:03:06Z`, memory PSI remained **0.00%** but
I/O PSI reached **4.58% some / 3.59% full**. CPU PSI avg10 was 43.91% before
and 36.68% after. No subsequent test or build was started. Wait for a fresh
I/O PSI avg10 below the 1% admission gate before more resource-bearing work.
The full legacy Arena and repository-wide MIDAS suites remain deferred.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Arena job/supervisor path | COMPLETE AND VERIFIED | `test_jobs.py` passes all 16 cases, including short-lived worker subprocesses. |
| Broader legacy Arena/MIDAS regression | DEFERRED | This targeted module is not evidence for the full suites; I/O admission is currently exceeded. |
| Production transition | DEFERRED | No production root, service, or systemd unit was used. |

Frontier remains **PARTIALLY VERIFIED**; source-use authorization, genuine
cross-venue evidence, full legacy regression, production recovery, and
deployment remain open.

## Current Frontier acceptance matrix — 2026-10-28 14:05 UTC

This matrix supersedes the earlier 10:35 UTC matrix and earlier point-in-time
summaries in this report. The implementation and test checkpoint is
`de0f8a4` (`docs(frontier): record Arena job supervision evidence`) plus the
documentation-only updates in the current change. The working branch remains
`codex/frontier-20261026`. The untracked held path
`data/frontier-public-probes/` was not opened, modified, copied, or staged.

| Requirement | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Isolated Frontier foundation and adapter capabilities | COMPLETE AND VERIFIED | Shared capability declarations, source configuration, validation, normalized models, consistent degraded states, and fixture contract tests are implemented. This does not itself establish live source conformance. |
| Polymarket public adapter | PARTIALLY VERIFIED | A bounded genuine public observation was validated earlier in this mission. The sample does not establish sustained source quality, simultaneous availability, or executable economics. |
| Kalshi, Kraken, and Coinbase adapters | IMPLEMENTED, LIVE VALIDATION PENDING | Read-only adapter code and fixture behavior are implemented; current source-use gates keep live probes and held evidence quarantined. |
| Additional venue research | PARTIALLY VERIFIED | Deribit was screened and deferred; no adapter or probe was added. Current source-specific constraints and decisions are documented in the dated venue review. |
| Canonical instruments and payoff semantics | PARTIALLY VERIFIED | Versioned models preserve native IDs, outcomes, denomination, constraints, payoff/resolution metadata, and provenance. Schema v5 now adds deterministic venue-scoped instrument IDs; fixture payoff checks pass, while real cross-venue settlement equivalence remains unverified. |
| Relationship discovery, graph, and persistence | PARTIALLY VERIFIED | Deterministic proposals, explicit hypothesis/verification states, evidence-backed review, bounded graph access, and persistence have fixture coverage. No permitted genuine cross-venue economic equivalence is verified. |
| Opportunity generation and independent verification | PARTIALLY VERIFIED | Supported binary, outcome-coverage, implication, basket, and joint-state cases have independent arithmetic and adversarial fixture coverage. No live cross-venue candidate or positive eligible opportunity is demonstrated. |
| Cross-venue costs, capital, and execution uncertainty | PARTIALLY VERIFIED | Fee, FX, timing, partial-fill, and venue-separated virtual-capital models are tested with fixtures. Account-specific fees, jurisdiction, settlement, transfer, custody, and executable availability remain unresolved. |
| Multi-source capture, storage, provenance, and replay | PARTIALLY VERIFIED | Bounded restartable collection, immutable hash-linked observations, source-quality metadata, and deterministic replay are tested. Direct library inputs now cap at 200 markets, 400 books, 1,000 relationships, and 1,000 proposals; sustained feeds and broad historical quality are not measured. |
| Frontier Laboratory/Arena integration | PARTIALLY VERIFIED | Frontier replay/timeline/discovery tests pass **28/28**; generic Arena job-supervision tests pass **16/16**; isolated admission tests pass **11/11**. Full legacy Arena regression, endurance, and production-worker readiness remain deferred. |
| Frontier overview and research workspace | COMPLETE AND VERIFIED | Vitest **47/47**, TypeScript, ESLint, Prettier, production build, and isolated browser suites **7/7 + 2/2** pass. The build retains a non-fatal 544.51 kB Chart chunk advisory. UI fixture evidence is labeled as fixture evidence. |
| Analytics and Frontier readiness | PARTIALLY VERIFIED | Source-aware coverage, quality, timing, rejection summaries, and readiness gates are implemented and fixture-tested. Available observations do not support venue-wide prevalence or coverage claims. |
| Research-only security boundary | COMPLETE AND VERIFIED | No authenticated trading, order submission, wallet, deposit, or withdrawal path was introduced; bounded test workers remain isolated and network-restricted where required. |
| Full Frontier Python suite | PARTIALLY VERIFIED | `tests/frontier` passed **452/452** on the storage/audit checkpoint; subsequent Arena and replay-bound changes have focused coverage, but the full suite has not been rerun on current code. |
| Broader MIDAS and full legacy Arena regression | DEFERRED | No repository-wide suite result is claimed. Full legacy Arena and broad MIDAS verification remain outstanding. |
| Resource sustainability and production recovery | PARTIALLY VERIFIED | Bounded RSS, swap, PSI, and I/O observations are recorded for selected tests. No long-running campaign or current-boundary production recovery proof exists. |
| Genuine live cross-venue relationship and economics | BLOCKED | Current source-use gates and held-capture protections prevent the independent additional-venue evidence required for this claim. No synthetic fixture is presented as live. |
| Production deployment | DEFERRED | The isolated branch remains unmerged and undeployed; separate source-policy, recovery/resource, and deployment authorization gates remain open. |
| Project Frontier overall | PARTIALLY VERIFIED | The exchange-independent research foundation, fixture scientific checks, native workspace, and bounded Arena integration are implemented. Live cross-venue science, broader regressions, endurance, production recovery, and deployment remain incomplete. |

### Arena admission regression — 2026-10-28 14:04 UTC

`tests/arena/test_admission.py` passed **11/11** in 1.38 seconds of pytest
time (1.99 seconds process wall), with **180,884 KiB** peak RSS, zero swaps,
zero filesystem input, 376 output blocks, and no socket traffic. The isolated
test root was `/dev/shm/midas-frontier-arena-admission-20261028T1404Z`.
Pre-run memory and I/O PSI avg10 were at or below **0.01%** at `14:04:10Z`;
afterward both were **0.00%** at `14:04:17Z`. CPU PSI avg10 after the run was
**42.02%**. Tests used temporary roots and monkeypatched admission state; no
production job, service, source, collector, or protected store was used.

The immediately preceding generic `tests/arena/test_jobs.py` run had caused
I/O PSI to rise to **4.58% some / 3.59% full**. Work resumed only after a fresh
sample was below the 1% I/O gate. This targeted admission run does not close
the broader legacy Arena regression or demonstrate resource sustainability.

## Direct replay resource bounds — 2026-10-28 14:10 UTC

**Implementation commit:** `f1d04bf` (`fix(frontier): bound direct replay inputs`).

The replay API already restricted its ordinary window, but direct callers of
`deterministic_replay` and `propose_relationships` had no matching core bounds.
The proposer now rejects more than 200 markets before building its indexes.
Replay rejects more than 200 markets, 400 books, or 1,000 verified
relationships before structural validation or sorting, and restricts
relationship proposals to 1..1,000. These limits match the ordinary API
maxima. Results inside those bounds are unchanged; paired replay retains its
stricter 100-market, 200-book, and 500-edge limits.

Five new adversarial tests cover oversized inputs. The full
relationship/economics/replay module passed **88/88** in 1.04 seconds wall
time at 56,248 KiB peak RSS. Replay-comparison, timeline, and discovery-
comparison modules passed **11/11** in 0.84 seconds at 56,064 KiB. API replay
tests passed **12/12** (44 deselected) in 4.80 seconds at 231,308 KiB; one
existing Starlette/httpx TestClient deprecation warning remains. All runs used
isolated `/dev/shm` roots, zero swaps, zero filesystem input, and no socket
traffic. Strict mypy passed on both changed implementation modules; Ruff check,
Ruff format check, and `git diff --check` passed.

The complete `tests/frontier` suite was not rerun after this change. Its latest
suite-wide result remains **452/452** on the earlier storage/audit checkpoint;
the current implementation has **111/111** focused passing tests across the
affected replay and caller modules. At `14:09:48Z`, memory and I/O PSI avg10
were 0.00%; at `14:10:23Z` memory and I/O were each 0.03% some / 0.00% full.
CPU PSI avg10 was 46.38% before and 37.77% after. No live source, held
capture, production service, or protected store was accessed; the held
`data/frontier-public-probes/` directory remains untouched.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Core relationship and replay input bounds | COMPLETE AND VERIFIED | Oversized direct inputs fail before structural validation, indexing, or sorting; affected module and caller slices pass. |
| Full Frontier suite on current code | PARTIALLY VERIFIED | 111 focused tests cover the change and direct consumers; the complete suite has not been rerun on `f1d04bf`. |
| Project Frontier overall | PARTIALLY VERIFIED | Live cross-venue evidence, broad regressions, sustained resource evidence, production recovery, and deployment remain open. |

## Source-scoped instrument identity — 2026-10-28 14:21 UTC

**Implementation commit:** `4305083` (`feat(frontier): add source-scoped instrument identities`).

`FrontierMarket` schema v5 now exposes a stable canonical ID on every
`MarketInstrument`. The ID hashes a version tag plus venue, native market ID,
and native instrument ID, so it is deterministic and source-scoped. Existing
schema v1–v4 payloads without the field derive it at validation time without
rewriting their declared schema version. Mismatched supplied IDs fail
validation. Adapter output and deterministic replay version numbers were
advanced; the Frontier market detail view exposes the ID with an explicit
label that it is not an equivalence claim.

The final targeted identity/adapter/Coinbase run passed **89/89** in 3.44
seconds wall time at **79,108 KiB** peak RSS, with zero swaps, filesystem input,
or socket messages; pytest reported 2.97 seconds and one existing
Starlette/httpx `TestClient` deprecation warning. Strict mypy passed on the
model, replay module, and four adapters (**6 source files**). Ruff check and
format check passed (**11 files**). `tsc -b` exited successfully, and the
focused Frontier UI test passed **1/1** (8 unrelated tests were skipped by the
filter). The adjacent model/replay/storage selection passed **140/140**, and
the API replay selection passed **12/12** earlier in this increment, before a
final type-guard-only adjustment in the migration validator; that final change
was covered by the 89-test rerun and strict typing.

At `14:20:34Z`, CPU PSI avg10 was **41.20%**, memory and I/O PSI avg10 were
**0.00%**, and the protected Reality recorder and MIDAS API were active. At
`14:21:27Z`, CPU PSI avg10 was **42.76%** with memory and I/O PSI avg10 at
**0.00%**. The complete Frontier suite and broader legacy regression were not
rerun under that sustained CPU pressure. No source request, production
service, or protected store was accessed; the untracked
`data/frontier-public-probes/` evidence path remains untouched.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Source-scoped canonical instrument IDs | COMPLETE AND VERIFIED | Schema v5 derivation, legacy v1–v4 migration, tamper rejection, four adapter fixtures, and UI display pass. IDs do not establish cross-venue payoff equivalence. |
| Canonical payoff and cross-venue economic equivalence | PARTIALLY VERIFIED | Existing bounded payoff fixtures remain covered; no permitted genuine cross-venue settlement-equivalence evidence is established. |
| Full Frontier and broad legacy regression on this commit | PARTIALLY VERIFIED | Focused changed-code checks pass; the full Frontier suite and repository-wide regression were not rerun. |
| Frontier project overall | PARTIALLY VERIFIED | Live cross-venue evidence, broader regression, sustained-resource evidence, production recovery, and deployment remain open. |

### Follow-up: legacy schema migration coverage — 2026-10-28 14:24 UTC

**Test commit:** `de57883` (`test(frontier): cover legacy instrument schema migration`).

The legacy identity migration test now covers each declared `FrontierMarket`
schema version from v1 through v4, verifying that a missing instrument ID is
derived and the declared version is retained. The focused identity, adapter,
and Coinbase selection passed **92/92** in 3.46 seconds wall time at **78,988
KiB** peak RSS, with zero swaps, filesystem input, or socket messages. Ruff
check and format pass for the changed test. One pre-existing
Starlette/httpx `TestClient` deprecation warning remains. This is targeted
coverage; the complete Frontier and broader legacy suites were not rerun.

CPU PSI avg10 was **46.66%** before the selection and **43.48%** afterward;
memory PSI stayed at **0.00%**, and I/O PSI was **0.03% some / 0.00% full**
afterward. No source, production service, or protected store was accessed.
Frontier remains research-only and **PARTIALLY VERIFIED**.

## Persisted instrument identity — 2026-10-28 14:27 UTC

**Test commit:** `6ecb7c9` (`test(frontier): verify instrument IDs persist`).

Storage regression coverage now verifies that instrument canonical IDs survive
append and readback for both a single `FrontierMarket` observation and a
`MarketBatch` observation. The selected storage tests passed **2/2** (28
deselected) in 1.75 seconds wall time at **58,636 KiB** peak RSS, with zero
swaps, filesystem input, or socket messages. Ruff check and format passed for
the changed test file.

CPU PSI avg10 was **42.59%** before and **39.61%** after. Memory PSI stayed
**0.00%**; I/O PSI increased from **0.18% some / 0.00% full** to **0.70% some
/ 0.54% full**, still below the 1% gate. No live source or protected service
was accessed. The full Frontier suite was not rerun; overall status remains
**PARTIALLY VERIFIED**.

### Storage module regression — 2026-10-28 14:28 UTC

After the focused persistence cases, the complete `tests/frontier/test_storage.py`
module passed **30/30** in 16.72 seconds wall time at **71,876 KiB** peak RSS,
with zero swaps, filesystem input, or socket messages. Pytest reported 16.36
seconds. The isolated temporary-file run wrote 100,472 filesystem blocks.
Before the run, I/O PSI avg10 was 0.00% some / 0.00% full; afterward it rose to
**9.54% some / 7.20% full**. Memory PSI remained 0.00%. Do not start another
resource-bearing check until a fresh I/O admission sample is below 1%.
No live source or protected store was accessed. This verifies the storage
module only; the complete Frontier suite remains unrun and status is
**PARTIALLY VERIFIED**.

## Current Frontier Python suite — 2026-10-28 14:31 UTC

**Code revision tested:** `d3e30a0` (`docs(frontier): record storage identity regression`); the documentation-only commit does not change tested code.

The full `tests/frontier` suite passed **465/465** in 29.51 seconds pytest
time (30.97 seconds process wall time), at **381,916 KiB** peak RSS. The run
used `--basetemp=/dev/shm/midas-frontier-full-20261028T143105Z`, with zero
swaps, filesystem input, and socket messages, and 432 filesystem output
blocks. One existing Starlette/httpx `TestClient` deprecation warning remains.

Before the run at `14:31:05Z`, CPU PSI avg10 was **44.60%**, memory PSI was
**0.00%**, and I/O PSI was **0.01% some / 0.00% full**. Afterward at
`14:31:45Z`, CPU PSI was **38.39%**, memory PSI **0.00%**, and I/O PSI
**0.06% some / 0.00% full**. The temporary run directory occupies 19 MiB in
tmpfs. Its cleanup command was rejected by the shell safeguard (`rm -f` style
commands are not permitted), so I left the isolated test directory intact.
No source, production service, protected store, or held evidence was accessed.
This closes current-branch Frontier Python suite verification; it
does not establish full MIDAS, browser, Arena, live-source, or deployment
acceptance.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Full Frontier Python suite on current code | COMPLETE AND VERIFIED | 465/465 pass on `d3e30a0`, with tmpfs-backed pytest state and measured resource profile. |
| Broader MIDAS, browser, and Arena regression | PARTIALLY VERIFIED | Separate full suites and current browser/Arena acceptance remain outstanding. |
| Frontier project overall | PARTIALLY VERIFIED | Genuine permitted cross-venue evidence, broader regression, resource sustainability, production recovery, and deployment remain open. |

## Frontier workspace verification — 2026-10-28 14:36 UTC

The complete web unit suite passed **47/47** across 9 files; the focused
Frontier component file also passed **9/9** after formatting. TypeScript
typecheck, ESLint, and the full Prettier check pass. The production build
passed, including `tsc -b`, in 14.07 seconds wall time at **712,284 KiB** peak
RSS, zero swaps, filesystem input, or socket messages. Vite completed in 4.90
seconds. The existing Chart chunk advisory remains (**544.51 kB** minified;
the configured warning threshold is 500 kB).

Frontier-specific Playwright acceptance passed **7/7** with the normal empty
temporary store and **2/2** with the explicit seeded path. The seeded run read
21 labeled fixture captures and replay artifacts plus one fixture-only Arena
discovery artifact. Both runs used isolated local API/UI services on ports
18000/15173, one worker, no public-source requests, and no production service.
The regular Frontier run took 19.46 seconds wall time at 201,688 KiB peak RSS;
the seeded run took 11.62 seconds at 182,712 KiB. Both had zero swaps and
socket messages. The seeded test emitted a harmless `NO_COLOR`/`FORCE_COLOR`
environment warning.

At `14:35:57Z`, CPU PSI avg10 was **44.34%**, memory PSI **0.00%**, and I/O PSI
**0.44% some / 0.23% full**. At `14:36:23Z`, memory remained 0.00% and I/O PSI
was **0.05% some / 0.01% full**. This verifies the current Frontier workspace
and its seeded research path, not unrelated Mission Control E2E, external
source validity, or production deployment.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Web unit tests, typecheck, lint, and formatting | COMPLETE AND VERIFIED | 47/47 unit tests; `tsc -b`, ESLint, Prettier, and post-format Frontier 9/9 pass. |
| Production frontend build | COMPLETE AND VERIFIED | Build succeeds; the existing 544.51 kB Chart chunk advisory remains. |
| Frontier browser and seeded research paths | COMPLETE AND VERIFIED | 7/7 normal and 2/2 seeded Playwright tests on isolated local services; all seeded evidence is fixture-only. |
| Broader MIDAS browser regression | PARTIALLY VERIFIED | Non-Frontier E2E files were not rerun in this checkpoint. |
| Frontier project overall | PARTIALLY VERIFIED | Live cross-venue validation, full broader regression, endurance, production recovery, and deployment remain open. |

### Broader Playwright run stopped at the I/O gate — 2026-10-28 14:38 UTC

The full web E2E command collected **19 tests** with one worker; the two
seeded-only cases were skipped because the seed flag was not enabled. Eight
tests completed successfully and two were reported skipped before the run was
interrupted with SIGINT after host I/O pressure crossed the 1% admission
threshold. No assertion failure was reported; the remaining nine cases did not
complete. This is not a passing full-suite result.

I/O PSI avg10 was **0.33% some / 0.00% full** before the run at `14:37:53Z`;
at `14:38:19Z` it reached **1.12% some / 0.64% full**. After stopping, it fell
to **0.59% some / 0.41% full** at `14:38:29Z` and **0.21% some / 0.15% full**
at `14:38:38Z`. The Playwright interruption left its isolated local API and
Vite test servers running; I verified their exact process arguments and
terminated only those test-owned PIDs. Both were gone at the next process
check. No production service or public source was accessed.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Frontier-specific E2E | COMPLETE AND VERIFIED | Dedicated normal and seeded Frontier files pass 7/7 and 2/2. |
| All Mission Control Playwright E2E | PARTIALLY VERIFIED | The 19-case run was resource-stopped after eight passes and two skips; nine did not complete. |
| Frontier project overall | PARTIALLY VERIFIED | Broader regression, live-source science, endurance, production recovery, and deployment remain open. |

### Browser coverage completed across isolated runs — 2026-10-28 14:42 UTC

The earlier one-shot Mission Control Playwright command remains interrupted at
the I/O gate as recorded above. To complete coverage without rerunning its
already passing Frontier cases, the ten other E2E cases were run as a separate
one-worker group. An initial attempt passed 9/10 because I explicitly pointed
`MIDAS_VERITAS_WORKSPACE` at an empty directory; the Veritas page correctly
reported that its historical evidence was unavailable. No application or
test change was needed. The repeat omitted that override, matching the
Playwright configuration's repository-backed read-only Veritas evidence path,
while keeping the mutable API database, Arena root, and Frontier root in a
fresh temporary directory. All ten cases then passed in 23.3 seconds.

Combined with the previously passing dedicated Frontier runs (7/7 normal and
2/2 seeded), all **19 collected Mission Control E2E cases passed across three
isolated runs**. The seeded cases used fixture data only. This establishes
current per-file browser coverage; it does not turn the interrupted one-shot
into a completed run or close the broader Python, live-source, production, or
deployment gates.

Periodic I/O PSI avg10 samples during the admitted run remained below the 1%
gate; the highest sampled value was 0.85% some / 0.42% full. At `14:42:48Z`
the final sample was 0.08% some / 0.06% full; memory PSI was 0.00%. The test
API and Vite servers were gone at the final process check. No public source,
production service, or protected store was accessed.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Mission Control browser test coverage | COMPLETE AND VERIFIED | All 19 collected cases pass across isolated one-worker runs; the earlier combined run was stopped at the I/O gate. |
| Broader MIDAS Python/Arena regression | PARTIALLY VERIFIED | Current full repository regression remains incomplete. |
| Frontier project overall | PARTIALLY VERIFIED | Live cross-venue science, resource sustainability, production recovery, and deployment remain open. |

### Frontier Arena job and replay integration — 2026-10-28 14:44 UTC

On code revision `4bf8379`, the focused Frontier Arena timeline, replay, and
discovery integration modules pass **28/28**. Pytest completed in 3.91
seconds; process wall time was 4.63 seconds and peak RSS was 201,368 KiB.
The run used a dedicated `/dev/shm` basetemp, zero swaps, no filesystem input,
376 filesystem output blocks, and no socket messages. The only warning is the
existing Starlette/httpx TestClient deprecation. Post-run I/O PSI avg10 at
`14:44:31Z` was 0.30% some / 0.18% full; memory PSI was 0.00%.

These tests exercise bounded Frontier job specs, durable artifacts, replay,
and API reads using temporary fixture state. They do not establish the full
legacy Arena suite, production worker readiness, live source quality, or
resource endurance.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Frontier Arena timeline/replay/discovery integration | COMPLETE AND VERIFIED | Current-code targeted modules pass 28/28 with temporary test roots. |
| Full legacy Arena/repository regression | PARTIALLY VERIFIED | Remaining Arena and broader MIDAS tests are not closed by this focused slice. |
| Frontier project overall | PARTIALLY VERIFIED | Live cross-venue evidence, endurance, production recovery, and deployment remain open. |

## Superseding Frontier acceptance matrix — 2026-10-28 14:49 UTC

This matrix supersedes the 14:05 UTC snapshot above. The active branch is
`codex/frontier-20261026`; documentation HEAD before this checkpoint is
`319cb1e`. The latest non-documentation commit is `ce19a98`, which only formats
the Frontier component test. No Python Frontier source or test files changed
after the **465/465** suite on `d3e30a0`. `data/frontier-public-probes/` remains
untracked and untouched.

| Requirement | Status | Current evidence and boundary |
| --- | --- | --- |
| Exchange-independent adapter protocol and capability registry | COMPLETE AND VERIFIED | All declared capability values are represented; omitted support defaults to unsupported. Adapter contract and source-config tests pass. |
| Polymarket read-only adapter | PARTIALLY VERIFIED | Earlier bounded public observations and fixture contract tests exist; sustained quality, cross-source synchronization, and executable availability are not established. |
| Kalshi, Kraken, and Coinbase read-only adapters | IMPLEMENTED, LIVE VALIDATION PENDING | Adapters and fixture tests exist. Their live collection and held-capture use remain disabled under the current source-use review. |
| Additional venue selection | DEFERRED | Deribit was screened and deferred; no additional adapter or live probe is justified under the reviewed terms and unresolved jurisdiction. |
| Canonical instruments, payoff semantics, and precision | PARTIALLY VERIFIED | Versioned venue-scoped identities, payout/resolution metadata, native constraints, and exact arithmetic have fixture and persistence coverage; real cross-venue settlement equivalence remains unverified. |
| Relationship graph and relationship verification | PARTIALLY VERIFIED | Deterministic proposals, persisted review evidence, bounded queries, and adversarial fixture checks pass; no permitted live cross-venue equivalence is established. |
| Opportunity discovery and independent economic audit | PARTIALLY VERIFIED | Supported binary, outcome coverage, implication, basket, and joint-state cases have fixture verification; no live eligible cross-venue opportunity is demonstrated. |
| Cross-venue fees, capital, FX, timing, and execution uncertainty | PARTIALLY VERIFIED | Explicit assumption models and independent fixture calculations exist; venue-specific permission, account costs, settlement access, and executable availability remain unresolved. |
| Multi-source collection, provenance, storage, and replay | PARTIALLY VERIFIED | Bounded collection, hash-linked evidence, restart/replay paths, and source-quality diagnostics have regression coverage; sustained feeds and cross-source simultaneity are not measured. |
| Frontier Laboratory/Arena integration | PARTIALLY VERIFIED | Frontier timeline/replay/discovery pass 28/28; Arena job supervision passes 16/16; admission passes 11/11. Full legacy Arena and production-worker readiness remain open. |
| Native Frontier workspace and readiness UI | COMPLETE AND VERIFIED | Web unit tests pass 47/47; typecheck, lint, formatting, build, and all 19 browser cases pass across isolated runs. The 544.51 kB Chart advisory remains. |
| Analytics and source-aware readiness | PARTIALLY VERIFIED | Coverage, quality, timing, rejection, and readiness views are implemented and fixture-tested; available evidence does not support venue-wide prevalence claims. |
| Research-only security boundary | COMPLETE AND VERIFIED | Adapter transport is anonymous, bounded HTTPS GET only; no order, wallet, deposit, withdrawal, or private-key path exists in the Frontier adapter layer. Internal POST routes perform research, replay, collection, or local analysis. |
| Full Frontier Python suite | COMPLETE AND VERIFIED | `tests/frontier` passes 465/465 on `d3e30a0`; no Python Frontier source or test files changed afterward. |
| Mission Control browser coverage | COMPLETE AND VERIFIED | All 19 collected cases pass across separate isolated runs: 10 legacy, 7 normal Frontier, and 2 seeded fixture cases. The earlier combined run remains honestly recorded as I/O-stopped. |
| Broader MIDAS and full legacy Arena regression | PARTIALLY VERIFIED | Relevant selected slices pass, but repository-wide and full Arena suites have not been completed. |
| Resource sustainability and protected recovery | PARTIALLY VERIFIED | Short-run RSS, swap, PSI, and I/O samples are recorded. No endurance campaign or current-boundary production recovery proof exists. |
| Genuine live cross-venue relationship and economics | BLOCKED | Current terms review keeps additional-venue collection and held evidence quarantined; no synthetic result is represented as live. |
| Production deployment | DEFERRED | Frontier remains isolated and undeployed. Separate recovery, source-use, and deployment gates remain open. |
| Project Frontier overall | PARTIALLY VERIFIED | The research platform and local evidence paths are implemented; live cross-venue science, broad regression, endurance, protected recovery, and deployment remain incomplete. |

**Continuation:** keep source-use holds and protected services unchanged. Continue
bounded offline regressions or implementation work only where it closes a
specific acceptance gap; remeasure resource admission before broader batches.

### Specialized held-source route regression — 2026-10-28 14:53 UTC

Extended `tests/frontier/test_source_data_permissions.py` to exercise the
Kalshi public trade, fee metadata, market metadata, MVE component, event-market,
multivariate-event, and finite collection routes with the source-use hold
active. Every route returned the configured 409 hold reason and the adapter
request count remained zero. The same integration test continues to verify
that enabled probe flags and arbitrary permission-reference strings do not
lift Kalshi or Kraken holds. This closes route-level API regression coverage;
it does not grant or imply permission to use either source.

The full current `tests/frontier` suite passed **465/465**, including these new
assertions, in 29.51 seconds pytest time (31.00 seconds process wall) at
381,712 KiB peak RSS. It used
`/dev/shm/midas-frontier-python-20261028T1453Z-rzOuVr`, zero swaps, zero
filesystem input, 376 output blocks, and no socket messages. The existing
Starlette/httpx `TestClient` deprecation warning remains. I/O and memory PSI
avg10 were both 0.00% in the pre-run sample at `14:53:02Z` and post-run sample
at `14:53:58Z`.

| Component | Status | Current evidence and remaining boundary |
| --- | --- | --- |
| Held-source API probe/collection routes | COMPLETE AND VERIFIED | All specialized Kalshi routes reject before network access; enabled flags and arbitrary references do not lift Kalshi/Kraken holds. |
| Full Frontier Python suite | COMPLETE AND VERIFIED | 465/465 pass with the expanded route-level source-policy regression. |
| Live Kalshi/Kraken research | BLOCKED | Source-use holds and absent validated authorization remain unchanged. |
| Frontier project overall | PARTIALLY VERIFIED | Live cross-venue science, broader legacy regression, endurance, protected recovery, and deployment remain open. |

### Legacy Arena regression and subprocess import-path correction — 2026-10-28 15:45 UTC

The full Arena suite collects 427 cases across 78 files. A first run launched
with relative PYTHONPATH=packages failed after 216 passing cases because a
test worker changed its working directory to a temporary root and imported
the installed base checkout at /home/charlie/midas/packages. Its older JobSpec
did not accept the three Frontier job fields. The failure was in test-process
checkout selection, not a failure of the Frontier Arena worker contract.

The migration verification test now prepends the active worktree's absolute
packages path to the child environment. The exact worker case passes 1/1 with
the original relative PYTHONPATH invocation (6.84 seconds pytest time, 7.82
seconds wall, 346,064 KiB peak RSS, zero swaps, and no socket messages). Ruff
check, Ruff format check, and git diff --check pass for this change.

A second full-suite run with an absolute Frontier package path reached 67%
without a reported test assertion failure. The process ran 9:47.35, used
590.63 CPU seconds, peaked at 493,008 KiB RSS, and used zero swaps. Host memory
PSI avg10 rose to 34.08% some / 30.80% full during the run; a post-stop sample
reached 47.91% some / 43.67% full. The run was terminated after graceful
signals did not promptly stop the CPU-bound test. A later 15:44:01Z sample
showed memory PSI avg10 at 0.03% some / 0.02% full but avg60 at 6.91% some /
6.34% full, I/O PSI avg10 at 0.63% some / 0.57% full, 9.6 GiB available, and
3.7 GiB of 4 GiB swap in use. No test assertion failure was reported before
the stop. The protected Reality recorder and separate Veritas work were left
untouched.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Arena migration test worker path | COMPLETE AND VERIFIED | The subprocess now imports the active checkout; the exact migration worker case passes under the original relative environment. |
| Full legacy Arena suite | PARTIALLY VERIFIED | The corrected run reached 67%, then ended at the host memory gate; this is not a full-suite pass. |
| Broader MIDAS and Frontier acceptance | PARTIALLY VERIFIED | Existing Frontier, browser, and targeted Arena evidence remains valid; broad regression, live-source science, endurance, production recovery, and deployment remain open. |

**Continuation:** keep source-use holds and protected services unchanged. Use
absolute worktree paths for subprocess verification, and remeasure memory and
I/O pressure before another broad suite. The full legacy Arena suite remains
open.

### Strict handling of nonstandard JSON numeric tokens — 2026-10-28 15:48 UTC

The shared public-read transport now rejects Python's nonstandard JSON
constants NaN, Infinity, and -Infinity at the decoding boundary. It classifies
them as INVALID_JSON and preserves the bounded raw response evidence. Four
mock-response cases cover top-level NaN, each infinity spelling, and a nested
NaN token; an additional parser-limit case uses a 5,000-digit decimal
exponent. Decoder arithmetic exceptions are classified as
JSON_COMPLEXITY_LIMIT. The owned HTTPX client now sets trust_env=False; a
configuration regression sets HTTP_PROXY, HTTPS_PROXY, and ALL_PROXY and
checks the client setting. Injected clients now require an isolated
MockTransport and cannot carry custom transport mounts, blocking explicit
proxy clients as well. No real exchange endpoint is used by these cases.

This change is implemented but not yet validated. At 15:47:55Z memory PSI
avg10 measured 45.32% some / 40.12% full and I/O PSI 0.61% some / 0.60% full;
9.5 GiB was available, with 3.7 GiB of 4 GiB swap in use. The focused
transport test and Ruff checks are deferred until a fresh resource sample
meets the local admission gate. Implementation commits are eab4a0b, 634ee5f,
1938dc4, and eadec5d.

At 15:52:21Z memory PSI avg10 remained 37.47% some / 23.71% full and avg60
was 36.41% some / 24.95% full. I/O PSI avg10 was 0.09% some / 0.06% full,
available memory was 9.7 GiB, and 3.8 GiB of 4 GiB swap was occupied. No
validation process was started under that pressure sample.

At 15:55:14Z, memory PSI avg10 measured 36.40% some / 21.49% full, with
avg60 at 36.05% some / 23.01% full. I/O PSI avg10 was 0.00%, available memory
was 9.9 GiB, and swap was full at 4.0 GiB with 39 MiB free. The transport now
rejects injected network clients and custom proxy mounts (commit eadec5d),
but its focused tests and Ruff checks remain pending.

At 15:55:43Z, memory PSI avg10 was 37.30% some / 22.94% full and avg60 was
36.29% some / 22.83% full. I/O PSI avg10 remained 0.00%; available memory was
9.8 GiB, with 4.0 GiB of 4.0 GiB swap in use and 8 KiB free. A read-only
process snapshot showed the Reality recorder and separate Veritas gap-detail
work active. No Frontier test or Arena worker was running; both services were
left untouched.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Malformed nonstandard JSON numbers | IMPLEMENTED, VALIDATION PENDING | Strict parse-constant handling and fixture regressions are present; focused validation is pending. |
| Default transport proxy policy | IMPLEMENTED, VALIDATION PENDING | Environment proxy discovery is disabled for the owned client; its configuration regression is pending. |
| Injected transport proxy policy | IMPLEMENTED, VALIDATION PENDING | The transport accepts fixture MockTransport clients only and rejects custom mounts; no live transport test has run. |
| Current Frontier Python suite | PARTIALLY VERIFIED | The previous 465/465 result predates this transport change and is not current-tree evidence. |
| Live source policy | COMPLETE AND VERIFIED | No source request was made for this work; held venues remain fail-closed. |
| Frontier overall | PARTIALLY VERIFIED | Broad Arena regression, live cross-venue science, endurance, protected recovery, and deployment remain open. |

## Current validation-boundary hardening — 2026-10-28 16:51 UTC

The latest source-independent review closed two additional hash-before-shape
checks. `5455b6e` validates persisted replay, joint-state, fee-schedule, and
relationship-review evidence IDs before uniqueness operations, and bounds
direct same-payoff and logical-implication verifier inputs. Five focused
modules pass 143/143. `d0d1f41` moves collection-checkpoint digest validation
ahead of duplicate hashing; all five digest fields have adversarial coverage,
and the complete collection module passes 34/34. Ruff and formatting checks
pass for both commits, and the working changes have clean diff checks.

These results are fixture-backed local verification. No public exchange
request, protected service interaction, or production deployment occurred.
The full Frontier suite has not been rerun after the latest edits, so overall
status remains **PARTIALLY VERIFIED**. Live cross-venue validation, resource
sustainability, production recovery, and deployment remain open. The latest
resource sample (16:50:58Z) showed CPU PSI avg10 37.09%, memory and I/O PSI
avg10 0%, 9.9 GiB available, and full swap. Pytest state was contained under
`/dev/shm`; the untracked public-probe capture directory remains untouched.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Evidence identity validation before hashing | COMPLETE AND VERIFIED | Five focused modules pass 143/143; oversized and malformed digests are rejected. |
| Collection checkpoint digest validation | COMPLETE AND VERIFIED | Five field cases and all 34 collection tests pass. |
| Full Python suite after latest edits | PARTIALLY VERIFIED | The latest 143-case and 34-case focused suites pass; full Frontier regression is pending. |
| Live source validation and production readiness | PARTIALLY VERIFIED | No live source request or deployment is claimed; applicable holds and protected-service requirements remain. |

## Current Frontier Python regression — 2026-10-28 16:53 UTC

The full `tests/frontier` suite now passes **497/497** on the current code tree
at `02912e5` (the commit itself contains only the preceding documentation
checkpoint, so tested code is identical to the validated changes). Pytest
completed in 30.28 seconds in `/dev/shm`; one existing Starlette/httpx
deprecation warning remains. The post-run sample at 16:53:09Z showed CPU PSI
avg10 38.47%, memory and I/O PSI avg10 0%, and 9.9 GiB available. No live
source probe or protected-service operation was performed.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Frontier Python suite | COMPLETE AND VERIFIED | 497/497 on the current code tree; one existing deprecation warning. |
| Frontier Arena integration | COMPLETE AND VERIFIED | The timeline/replay/discovery integration slice passes 28/28; full legacy Arena suite remains open. |
| Live cross-venue validation | PARTIALLY VERIFIED | Fixture-based matching and economics are covered; live venue matching remains blocked by source-use gates. |
| Resource sustainability and production readiness | PARTIALLY VERIFIED | Short bounded suites pass; endurance, protected recovery, and deployment have not been established. |
| Frontier overall | PARTIALLY VERIFIED | Cross-venue live science, broad legacy regression, production recovery, and deployment remain open. |

## Raw response capture and full Python regression — 2026-10-28 16:55 UTC

Commit `62e5a61` closes a parsing-boundary gap in `RawObservation`. The model
now rejects excessive UTF-8 or base64 text length before encoding or decoding,
and retains the decoded-byte check for valid base64 at the boundary. A
regression ensures over-limit base64 input never reaches the decoder. The
complete storage module passes 31/31.

The full `tests/frontier` suite passes **498/498** on the current code in
29.75 seconds, with one existing Starlette/httpx deprecation warning. Pytest
state was stored under `/dev/shm`. The 16:55:30Z post-run sample measured CPU
PSI avg10 29.59%, memory PSI avg10 0%, I/O PSI avg10 0.08%, and 9.8 GiB
available. No live source request or protected-service operation occurred.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Frontier raw-response parsing bound | COMPLETE AND VERIFIED | Oversized base64 rejects before decode; full storage module passes. |
| Full Frontier Python regression | COMPLETE AND VERIFIED | 498/498 on current code; one existing deprecation warning. |
| Frontier Arena integration | COMPLETE AND VERIFIED | The timeline/replay/discovery slice passes 28/28; broad legacy Arena remains open. |
| Live cross-venue validation | PARTIALLY VERIFIED | Fixture-backed relationships and economics are covered; live-source evidence remains unavailable under current source-use holds. |
| Resource sustainability and production readiness | PARTIALLY VERIFIED | Short suites pass; endurance, protected recovery, and deployment remain open. |
| Frontier overall | PARTIALLY VERIFIED | Live cross-venue science, broad legacy regression, production recovery, and deployment remain open. |

## Strict repository typing and integrated regression — 2026-10-28 17:03 UTC

The repository CI command `mypy packages/midas apps/api` now succeeds with no
issues across 181 source files. Its initial 34 errors were in five Veritas
modules and two Arena modules. Commit `e3a2bd2` narrows parsed numeric and JSON
shapes, rejects non-object reusable-sweep manifests, and returns a strictly
boolean Arena readiness result. No trading or source-access path changed.

The seven directly affected Veritas/Arena test modules pass **80/80** in 7.83
seconds. After those changes, the full `tests/frontier` suite passes **498/498**
in 30.08 seconds. Each run has one existing Starlette/httpx TestClient
deprecation warning. Ruff and format checks pass. The post-run sample at
17:03:06Z showed CPU PSI avg10 31.12%, memory PSI avg10 0%, I/O PSI avg10
0.18%, and 9.7 GiB available. Both test batches used `/dev/shm`; no live source
request or protected-service action occurred.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Full CI strict type check | COMPLETE AND VERIFIED | `mypy packages/midas apps/api`: no issues in 181 source files. |
| Direct Veritas/Arena regression slice | COMPLETE AND VERIFIED | 80/80 cases pass across seven modules. |
| Full Frontier regression after integration edits | COMPLETE AND VERIFIED | 498/498 pass on the current code tree. |
| Live cross-venue science | PARTIALLY VERIFIED | Fixture-backed matching/economics pass; held-source permission and live equivalence remain unresolved. |
| Frontier overall | PARTIALLY VERIFIED | Broad legacy regression, resource endurance, protected recovery, and deployment remain open. |

## Bounded live Polymarket metadata observation — 2026-10-28 17:04 UTC

The [official Polymarket Institute guide](https://institute.polymarket.com/data)
describes open public APIs for research, identifies Gamma as the market and
event discovery interface, and treats the decentralized and US exchanges as
separate data sources. On code commit `e3a2bd2`, one unauthenticated
`PolymarketAdapter.discover_markets(limit=1)` call to the decentralized
Gamma `/markets` endpoint returned HTTP 200. The temporary read-only config
bounded the call to one market, 256 KiB, eight seconds, and zero retries.

The persisted observation is
`data/frontier-live-evidence-polymarket-20261028T170445Z/`. It contains the
raw `RawObservation`, normalized `MarketBatch`, and a manifest. Local replay
reconstructs both models and verifies the raw-response, raw-record, and
normalized-batch hashes. The response body was 7,757 bytes; the normalized
batch was 14,431 bytes. The one open binary market (`2589810`) includes two
outcome instruments and explicit `PAYOUT_NOT_ATTESTED`,
`SETTLEMENT_ASSET_NOT_ATTESTED`, and `CROSS_VENUE_EQUIVALENCE_NOT_ASSERTED`
flags. No order book, trade, or fee schedule was requested.

This is live single-venue metadata validation, not evidence of a
cross-venue relationship, simultaneous pricing, or an economic opportunity.
Kalshi, Kraken, and Coinbase source-use holds remain in force; all production
and protected-service states remain unchanged.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Polymarket public metadata adapter | COMPLETE AND VERIFIED | One bounded Gamma GET; response and normalized artifacts reconstruct and hash-check. |
| Polymarket payoff/book economics | PARTIALLY VERIFIED | The observation lacks attested payout, settlement asset, and book depth. |
| Genuine live cross-venue relationship | BLOCKED | Other candidate source use remains held; no equivalent live pair is available. |
| Frontier overall | PARTIALLY VERIFIED | Cross-venue evidence, broad legacy regression, resource endurance, protected recovery, and deployment remain open. |

## Durable storage and deterministic replay of a live Polymarket capture — 2026-10-28 17:07 UTC

The preserved 17:04 raw response and normalized one-market batch were appended
to a new, isolated `FrontierStore` under the capture directory. Its SQLite
database is 155,648 bytes with a 4 MiB configured cap and a four-row budget.
The validated read path reconstructed `RawObservation` and `MarketBatch`,
checked the raw SHA-256 and append-only row hash, and retained the canonical
market `polymarket:2589810` with both instruments. The store observation ID is
`90e019e6751d2be81fed5d9eeec1d92eb703b4ee822596d833268f369096e559`; its row
hash is `70d9396eb804982a26191521fc3dd28c73e299587407cf242c823c708f54be78`.

Two deterministic replays over the recovered market used the stored
observation identity, the source receive time as `as_of_utc`, code version
`e3a2bd2`, no books, and a ten-proposal bound. Both returned run ID
`b4b0d76bc912b596ceeb21cfb15a687134a34d9c8f9fe702e31d5f966a2cef6a` and result
hash `89cce280acb0a1e7615965108f15ea5cc2b622df0fc8c56ef6ad35a525f63fab`.
The replay was appended and recovered from the same isolated store with its
hash validation. It yielded zero proposed relationships and zero candidates;
one metadata-only market does not support further economic conclusions. The
machine-readable receipt is in
`data/frontier-live-evidence-polymarket-20261028T170445Z/store_replay_receipt.json`.

This adds genuine single-source durability and replay evidence. It does not
close the live cross-venue, book economics, or opportunity acceptance criteria.
At 17:07:40Z CPU PSI avg10 was 41.15%. The protected Reality service remained
active at 1,207,738,368 of 1,207,959,552 bytes (`MemoryCurrent` of
`MemoryHigh`); the API remained active at 1,186,410,496 of 1,610,612,736
bytes. I deferred the broad legacy regression under this measured pressure.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Live Polymarket observation persisted and recovered | COMPLETE AND VERIFIED | Isolated FrontierStore round-trip validates raw and row hashes and reconstructs the normalized batch. |
| Deterministic replay over recovered genuine input | COMPLETE AND VERIFIED | Two runs share exact run/result hashes; persisted result reloads and verifies. Zero candidates are expected for one market without books. |
| Live multi-venue relationship and economics | BLOCKED | Held-source policy remains active and this capture is single-venue metadata only. |
| Frontier overall | PARTIALLY VERIFIED | Broad regression, cross-venue science, resource endurance, protected recovery, and deployment remain open. |

## Bounded live Polymarket order book — 2026-10-28 17:10 UTC

The official [Polymarket CLOB order-book reference](https://docs.polymarket.com/api-reference/market-data/get-order-book)
documents the public `GET /book` endpoint, including a no-auth request example;
the [Polymarket Institute research guide](https://institute.polymarket.com/data)
describes the CLOB as the source for current spread and book depth. On
`frontier-polymarket-8`, one unauthenticated `fetch_book` request for the YES
instrument of the captured Gamma market returned HTTP 200. The bounded probe
used an 8-second timeout, a 65,536-byte response-body maximum, and no retry.

The 3,164-byte raw response is preserved with a normalized `BookSnapshot` in
`data/frontier-live-evidence-polymarket-20261028T170445Z/`. The response
contained zero bid levels and five ask levels; best ask within that returned
depth was 0.995. The source supplied timestamp 17:09:09.345Z and the local
receipt timestamp was 17:09:19.386225Z. Their difference is about 10.04
seconds, but source timestamp precision and simultaneity are not established.
The capture files have hashes recorded in both the manifest and the book
receipt. The isolated 4 MiB Frontier store now contains two validated source
observations and two persisted replay results; its size is 167,936 bytes.

Two deterministic replays over the recovered market and book produced run ID
`cb7bbcf1fa03d0ad62bb8d60023d2b048168fc04f0aacf64304337ac4d467a9c` and result
SHA-256 `caba4ebffaf4972fa5ba1805b8b2d9b41a5ba3d26323c613f960f50e89c0f0a3`.
The second result is persisted and reloads with hash validation. It contains no
relationship proposals or candidates. This is the expected conservative
result for a single one-sided outcome book with an unattested market payout;
it establishes neither a complete payoff nor an executable trade.

At 17:11:25Z CPU PSI avg10 was 39.52%, memory PSI avg10 was 0%, I/O PSI
avg10 was 0.01%, and 10,209,340 KiB was available. Reality and API remained
active. Reality was at 1,207,590,912 / 1,207,959,552 bytes, 360 KiB below
`MemoryHigh`, with 1,816 KiB free swap. I deferred broader regression under
these conditions.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Polymarket live book retrieval and normalization | COMPLETE AND VERIFIED | One official public GET returned HTTP 200; a bounded raw body and normalized book are preserved and hash-linked. |
| Durable storage and deterministic replay with a book | COMPLETE AND VERIFIED | Two replays share run/result hashes; the stored replay reloads with validation. |
| Live economic opportunity | PARTIALLY VERIFIED | No complete, verified payout and only one outcome's book were observed; no economic claim follows. |
| Frontier overall | PARTIALLY VERIFIED | Live multi-venue evidence, broad legacy regression, resource endurance, protected recovery, and deployment remain open. |

## Live Gamma event-group graph and replay — 2026-10-28 17:14 UTC

The [Polymarket Institute data guide](https://institute.polymarket.com/data)
documents the Gamma lookup route for a known event ID. Frontier used the event
ID `606422` from the 17:04 public market listing in one unauthenticated
`discover_event_markets` request. The request had an 8-second timeout,
256 KiB response-body maximum, 20-market limit, and zero retries. The response
returned HTTP 200, contained 27,059 bytes, and arrived at
2026-10-28T17:13:05.764808Z.

The response yielded five binary submarkets (`2589810`–`2589814`) grouped under
the native event “Fed Decision in October?”. Deterministic relationship
discovery produced ten pairwise `SAME_EVENT` edges. Each is stored in the
isolated Frontier graph store as a `HYPOTHESIS` and cites the event observation
ID `d32fc5d5e8b78e93da9d0b049d6a30aa52eda35c75972a77fbad5785904a951e`. A
bounded indexed neighborhood query returned the four peers of one endpoint.
The raw event response, normalized batch, and a machine-readable edge receipt
are preserved in
`data/frontier-live-evidence-polymarket-20261028T170445Z/`.

Two replay runs over the recovered five-market batch produced run ID
`68ffa2fee9e70f727395e1d11371b561a4ee51c7baddc82004f0b6a5bcee99ea` and
result SHA-256 `aa95c4c6b35c681631e054c4a8a7bd44bb0e420987f8833a58c71b7e8f55debe`.
The saved replay reloads with hash validation. It contains ten event-membership
hypotheses and zero economic candidates. Every child contract retains an
unverified, non-exhaustive payoff and unverified resolution metadata. Shared
event membership does not establish mutually exclusive or exhaustive outcome
semantics, equivalent payoffs, or a cross-venue relationship.

At 17:14:02Z CPU PSI avg10 was 2.70%, avg60 11.76%, and avg300 30.82%; memory
PSI was 0%; I/O PSI avg10 was 0.75% (`full` 0.62%). Available memory was
10,219,060 KiB. Reality and API were active; Reality was at
1,207,046,144 / 1,207,959,552 bytes, with 1,932 KiB free swap. Broad
regression still requires a fresh resource-admission sample.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Live Gamma event-group normalization | COMPLETE AND VERIFIED | One bounded official public route returned five child contracts under one native event ID. |
| Live graph proposal and persistence | COMPLETE AND VERIFIED | Ten source-observation-pinned `SAME_EVENT` hypotheses persist; first endpoint has four indexed peers. |
| Reproducible replay over the event group | COMPLETE AND VERIFIED | Two results match exactly and the saved replay validates on reload; zero candidates. |
| Verified cross-venue relationship | BLOCKED | No second cleared venue is available; these are same-venue source groupings only. |
| Frontier overall | PARTIALLY VERIFIED | Cross-venue science, broad regression, resource endurance, protected recovery, and deployment remain open. |

## Full Arena regression interrupted by host memory PSI — 2026-10-28 17:18 UTC

The full `tests/arena` suite was launched with `MIDAS_ARENA_ROOT` and pytest
`--basetemp` under the private `/dev/shm/midas-frontier-arena-full.W5DIac/`
directory, one process, and BLAS/OpenMP thread limits of one. At 2:25 elapsed,
105 tests had passed without a reported assertion failure. The suite was
interrupted with SIGINT while blocked in Python's selector wait after the
17:17:33Z host sample showed memory PSI avg10 18.53% (`full` 16.16%). Pytest
reported one existing Starlette/httpx deprecation warning. The interruption
is not a test failure, and it does not count as full-suite verification.

The process peaked at 484,168 KiB RSS, used no swap, and sent/received no
sockets. At 17:18:23Z, after the test process exited, memory PSI remained
36.63% avg10 (`full` 31.86%) while `MemAvailable` was 9,910,060 KiB. Reality
and API remained active and unchanged; their `MemoryCurrent` values were
1,115,865,088 and 1,124,130,816 bytes, respectively.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Partial legacy Arena regression | PARTIALLY VERIFIED | 105 cases pass before resource-driven SIGINT; no assertion failure preceded it. |
| Full legacy Arena regression | PARTIALLY VERIFIED | Not completed; remaining tests need a later resource-admission sample. |
| Protected service state | COMPLETE AND VERIFIED | Both services remained active; no service or configuration change occurred. |
| Frontier overall | PARTIALLY VERIFIED | Cross-venue source clearance, broad regression, resource endurance, protected recovery, and deployment remain open. |

## Captured-evidence browser acceptance — 2026-10-28 17:36 UTC

A gated Playwright browser case now renders the preserved public Polymarket
capture through the native Frontier workspace. Its isolated seeder checks the
committed SQLite capture's SHA-256, SQLite integrity, three observations, and
ten relationship rows before copying it under a fresh temporary browser root.
Playwright's repeated worker-side config load reuses this data only when its
run owner and capture markers match.

The one-case run passes in 5.1 seconds. The page displays the captured Fed
market and its one-sided book, the `0.995` ask, the raw CLOB request URL, and a
stored `same_event` edge labeled as a hypothesis. The browser test asserts zero
public source-probe requests and zero API mutations. The API is started in demo
mode against the disposable copy, and the capture itself remains unchanged.
Prettier, ESLint, and `git diff --check` pass for the changed web files. A
Playwright `--list` load discovers 20 configured cases; it is test discovery,
not full browser verification.

At 17:36:56Z post-run memory PSI avg10 was 0.00% (`full` 0.00%), avg60 was
0.61% (`full` 0.55%), and avg300 was 6.08% (`full` 5.48%). The protected
Reality and API services remained active at 1,150,152,704 / 1,207,959,552 and
1,130,233,856 / 1,610,612,736 bytes, respectively. This short bounded browser
run is not endurance or deployment evidence.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Captured public-evidence Frontier browser path | COMPLETE AND VERIFIED | The real saved market, book, raw provenance, and stored relationship hypothesis render from a hash-pinned isolated copy. |
| Browser source and mutation boundary | COMPLETE AND VERIFIED | Zero source probes and zero API mutations were observed in the bounded case. |
| Full browser and legacy regression | PARTIALLY VERIFIED | One captured-evidence case passes; broad regression remains resource-gated. |
| Project Frontier overall | PARTIALLY VERIFIED | Live cross-venue science, broader regression, resource endurance, protected recovery, and deployment remain open. |

## Current official REST contract spot-check — 2026-10-28 17:40 UTC

Read the current official [Kalshi market orderbook](https://docs.kalshi.com/api-reference/market/get-market-orderbook),
[Kalshi trades](https://docs.kalshi.com/api-reference/market/get-trades),
[Kalshi event](https://docs.kalshi.com/api-reference/events/get-event), and
[Kraken spot orderbook](https://docs.kraken.com/api-reference/market-data/get-order-book)
references against the implemented adapters. The documented Kalshi order book
contains YES and NO bids only; the adapter derives complementary asks and keeps
the source's fixed-point dollar prices and quantities. Kalshi's ticker-filtered
trade page supports a cursor and includes block trades by default; Frontier
caps each page at 100 and labels the block-trade limitation. The event endpoint
documents nested child markets and a deprecated top-level child list, both of
which the adapter validates. Kraken's `Depth` endpoint is an aggregated L2 book
with per-level publication times; Frontier preserves those timestamps without
claiming a single synchronized snapshot time.

No endpoint-shape drift requiring a code change was found. This was a
documentation-only review: it made no venue requests and does not establish
current reachability, source permission, or live adapter validation. The
existing source-use holds and disabled-by-default adapter config remain in
force.

## Kalshi trade classification normalization — 2026-10-28 17:43 UTC

The official Kalshi trade response includes `is_block_trade`,
`taker_outcome_side`, and `taker_book_side`. The prior normalizer preserved the
raw response but omitted these values from normalized trade records; its table
therefore could not show whether a print was a block trade. The v4
`TradeObservation` now keeps those fields, the Kalshi adapter uses version
`frontier-kalshi-19`, and the UI labels block status while leaving missing
classification as “Not reported.” The normalized taker labels remain distinct
from the general aggressor-side field.

Tests now cover true, false, and missing block flags, malformed values, API
storage/readback, and the UI display. They are **pending execution**. The
17:43:55Z host sample showed memory PSI avg10 50.51%, avg60 36.98%, avg300
15.94% (`full` 45.14%, 32.70%, 14.12%) with `MemAvailable` 9,887,764 KiB and
Reality at 1,155,682,304 / 1,207,959,552 bytes. No tests were started at that
sample; implementation verification remains partial.

| Component | Status | Evidence and remaining boundary |
| --- | --- | --- |
| Kalshi block/taker metadata preservation | PARTIALLY VERIFIED | Versioned fields and UI are implemented; focused adapter, API, and web tests remain pending due host pressure. |
| Live Kalshi collection | IMPLEMENTED, LIVE VALIDATION PENDING | The documented API shape is mapped; no live request or source-use validation was performed. |

## Kalshi trade metadata focused verification — 2026-10-28 19:30 UTC

The follow-up tests passed after adding versioned `is_block_trade`,
`taker_outcome_side`, and `taker_book_side` fields to normalized Kalshi trades.
Seven mocked adapter cases passed for true, false, missing, and malformed
values. The API pagination and storage test passed, preserving normalized flags
and the raw source page without authorization headers. It emitted one existing
Starlette/httpx deprecation warning. The focused Frontier UI test passed and
rendered both the taker label and block-trade classification; its name filter
selected one case and skipped eight other tests in the same file. Ruff,
Prettier, ESLint, and whitespace checks passed after formatting.
The official response example also includes `taker_side` without defining its
semantics; Frontier preserves it in the raw page and does not infer a normalized
meaning or aggressor direction from it.

The tests used local fixtures and a temporary database. They made no Kalshi
request. Peak RSS was 61,492 KiB for the adapter cases, 87,452 KiB for the API
case, and 258,972 KiB for the web test. The post-run 19:29 UTC resource sample
recorded memory PSI avg10 0.00%, avg60 4.96%, avg300 19.96% (`full` 0.00%,
3.51%, 14.43%), 9,823,408 KiB available memory and 11,420 KiB free swap. Both
protected services remained active. These checks verify bounded normalization
and presentation behavior; they do not verify live source reachability,
permission, endurance, or production deployment.

## Current-tree regression and build checkpoint — 2026-10-28 19:35 UTC

The full `tests/frontier` suite passes **505/505** in 62.92 seconds (64.48
seconds process wall) at 390,176 KiB peak RSS, with zero swaps and no socket
traffic. The only warning is the existing Starlette/httpx `TestClient`
deprecation. The full `apps/web/src/Frontier.test.tsx` file passes **9/9** in
6.20 seconds of test time at 260,884 KiB peak RSS.

Current-tree frontend `typecheck` passes in 9.24 seconds at 471,440 KiB peak
RSS. The production build passes in 14.42 seconds at 671,000 KiB peak RSS and
transforms 2,230 modules. Vite reports the existing Chart chunk at 544.51 kB
(186.79 kB gzip) above its 500 kB advisory threshold; the lazy Frontier chunk
is 183.24 kB (44.69 kB gzip). Ruff, Prettier, and ESLint pass. The isolated
captured-public-evidence browser case passes **1/1** in 5.2 seconds; it reads a
hash-verified temporary copy of three observations and ten relationships,
makes no public-source requests, and records zero API mutations.

At 19:35:02 UTC, post-run memory PSI was avg10 0.00%, avg60 0.00%, avg300
6.02% (`full` 0.00%, 0.00%, 4.34%). I/O PSI was avg10 0.71% some / 0.50%
full, avg60 3.57% / 2.49%, and avg300 2.08% / 1.45%. `MemAvailable` was
9,906,408 KiB and `SwapFree` 19,032 KiB. Reality remained active at
1,207,844,864 / 1,207,959,552 bytes, leaving about 112 KiB below `MemoryHigh`;
the API remained active at 1,531,400,192 / 1,610,612,736 bytes. No further
resource-bearing test was started at this sample. The complete web suite and
broader legacy Arena/MIDAS regression remain unrun on this exact tree.

| Requirement | Status | Current evidence and boundary |
| --- | --- | --- |
| Exchange-independent adapters and capability contracts | COMPLETE AND VERIFIED | Current Frontier suite passes 505 tests, including adapter and API contracts. |
| Polymarket source and captured evidence path | PARTIALLY VERIFIED | A bounded genuine Polymarket capture is hash-pinned, browser-visible, and reproducible; no continuous quality or simultaneous-execution claim follows. |
| Kalshi, Kraken, and Coinbase live source validation | IMPLEMENTED, LIVE VALIDATION PENDING | Fixture tests and official API contract reviews pass; source-use holds prevent live collection absent applicable permission. |
| Canonical instruments, payoff semantics, relationship graph, and independent economic audit | PARTIALLY VERIFIED | Deterministic fixture, persistence, adversarial, and independent calculations pass; live cross-venue equivalence remains unavailable. |
| Multi-source storage, provenance, and replay | PARTIALLY VERIFIED | Bounded replay, saved evidence, and current Frontier tests pass; sustained multi-source synchronization remains unmeasured. |
| Laboratory/Arena integration | PARTIALLY VERIFIED | Frontier-specific Arena and supervision slices pass; full legacy Arena regression and production-worker readiness remain open. |
| Frontier workspace, current changed UI path, typecheck, and production build | COMPLETE AND VERIFIED | Current Frontier UI test file 9/9, typecheck, lint, formatting, build, and captured-evidence browser case pass; the Chart size advisory remains. |
| Full web suite on the exact current tree | PARTIALLY VERIFIED | Prior 47/47 baseline remains; current Frontier component file is 9/9. The 47-case suite was not rerun after this tree's changes because post-run I/O PSI rose and Reality reached its soft memory boundary. |
| Full Frontier Python suite | COMPLETE AND VERIFIED | Current tree `tests/frontier`: 505/505. |
| Broader MIDAS and full legacy Arena regression | PARTIALLY VERIFIED | Earlier broad run stopped at the host resource gate; no full-repository pass is claimed. |
| Resource sustainability and protected recovery | PARTIALLY VERIFIED | Bounded run RSS and current PSI are measured; Reality is at its soft memory boundary, and there is no endurance or current-boundary recovery proof. |
| Genuine live cross-venue relationship and economics | BLOCKED | Current Kalshi/Kraken/Coinbase source-use gates remain; no synthetic output is presented as live. |

## Kraken recent-trades parser audit — 2026-10-28 19:45 UTC

Commit `4093a9a34a8476517cc5f4ead1844bbc3eee81b5` updates the read-only Kraken
Spot adapter to `frontier-kraken-spot-5`. `fetch_trades` now sends the bounded
requested count, validates the bounded pair identifier, and accepts records
only under the exact requested internal pair key. It rejects unexpected
additional pair keys, malformed tuple lengths, invalid prices/quantities or
timestamps, and malformed optional native trade IDs. A present Kraken trade ID
is retained as the native identity and instrument identity is attached to the
trade record. The API example's one-letter tuple value remains in raw evidence;
the adapter leaves `aggressor_side` unset because the official REST response
documentation does not define that field's semantics. The capability URL now
points at Kraken's `Get Recent Trades` endpoint, which the adapter actually
uses.

The full adapter test file passes **103/103** in 2.83 seconds pytest time
(3.22 seconds wall), with 65,136 KiB peak RSS, zero swaps, and zero socket
messages. Ruff check and format plus targeted mypy pass. Tests use mocked
responses; no live Kraken request or held source artifact was read. The current
official API documentation was reviewed at
[Kraken Get Recent Trades](https://docs.kraken.com/api-reference/market-data/get-recent-trades).
The exact tuple-key rule, documented `count` bound, sample layout, and internal
pair key example informed this change. The page shows one-letter field values
without defining their aggressor semantics, so the normalization intentionally
does not assign one.

This closes a fixture-verified parser correctness issue, not source validation.
Kraken's applicable research/retention permission remains unresolved and live
probes remain blocked. The 505-case Frontier suite passed before Kalshi v20
and Kraken v5; it has not been rerun after those changes. At
`2026-10-28T19:45:20Z`, Reality was 720,896 bytes below `MemoryHigh`, API had
about 69 MiB below its high boundary, memory PSI avg10/avg60 was 0%, and I/O
PSI avg10/avg60 was 0%/0.04%. A broader run was not started.

| Requirement | Status | Evidence and boundary |
| --- | --- | --- |
| Kraken public-trade parser contract | COMPLETE AND VERIFIED | Fixture and adapter contract suite passes 103/103; live validation remains held. |
| Full post-hardening Frontier suite | PARTIALLY VERIFIED | The prior 505-case pass predates Kalshi v20 and Kraken v5. |
| Genuine Kraken or cross-venue live research | BLOCKED | Source-use/retention review remains unresolved; no new public request was made. |
| Frontier overall | PARTIALLY VERIFIED | Live cross-venue science, broad regression, endurance, protected recovery, and deployment remain incomplete. |

## Polymarket legacy one-shot trade audit — 2026-10-28 19:52 UTC

Commit `2b638ce047ee91b761681385e1e46a565346cd3b` updates the older
Polymarket Data API `/trades` parser to `frontier-polymarket-9`. It now accepts
only a bounded 32-byte condition identifier, requires each row to carry that
exact condition, and rejects a response exceeding its requested limit. Price
must be in `[0, 1]`; size must be positive; and timestamp must be parseable.
The native outcome token ID is required and retained. An optional transaction
hash is validated and preserved as the trade ID. A per-row index in provenance
keeps two prints with the same transaction hash and token distinct. The legacy
side field stays in the complete raw response and is not mapped to normalized
aggressor direction because the reviewed legacy response reference does not
define that meaning. The explicit Data API v2 cursor method is separate and
unchanged.

The adapter test file passed **115/115** in 3.06 seconds pytest time (3.46
seconds wall), with 66,124 KiB peak RSS, zero swaps, and zero socket messages.
After a final message-only wording edit, the ten focused legacy parser cases
passed again. Ruff check/format and targeted mypy pass. This is mock-fixture
verification; there was no live request, no held evidence access, and no claim
that v1 and v2 source semantics are interchangeable. The official Data API v2
reference separately describes public condition-filtered cursor trades and
the condition/token identifier distinction:
[Polymarket Data API v2 docs](https://data-api.polymarket.com/v2/docs).

The broader 505-case Frontier suite predates Kalshi v20, Kraken v6, and
Polymarket v9. At `2026-10-28T19:52:10Z`, Reality was about 212 KiB over
`MemoryHigh`; memory PSI avg10/avg60 was 0%. No broader test run was started.

| Requirement | Status | Evidence and boundary |
| --- | --- | --- |
| Polymarket legacy one-shot trade parser | COMPLETE AND VERIFIED | Exact condition/token binding, binary price bounds, required timestamp, and distinct same-transaction row identity are covered by fixture tests. |
| Full post-hardening Frontier suite | PARTIALLY VERIFIED | The 505-case pass predates Kalshi v20, Kraken v6, and Polymarket v9. |
| Live validation of this legacy parser revision | IMPLEMENTED, LIVE VALIDATION PENDING | Prior bounded Polymarket data predates v9; this parser change is fixture-only and no new request was made. |
| Frontier overall | PARTIALLY VERIFIED | Broad regression, current cross-venue source validation, endurance, protected recovery, and deployment remain incomplete. |

## Kraken pair binding across read endpoints — 2026-10-28 19:47 UTC

Commit `36554c76a675ebdfcf08e5b0d871fc311c74c0e1` advances the Kraken Spot
adapter to `frontier-kraken-spot-6`. Its order-book reader now requests the
discovered internal pair ID instead of the display alias and requires the
exact returned key. The OHLC reader rejects missing or unexpected pair keys,
while permitting the source's separate `last` marker. Pair IDs are bounded
and validated on discovery and reads. These changes remove two single-result
fallbacks that could have attributed another pair's data to the selected
instrument. The trade parser remains exact-key bound, sends `count`, retains
optional native trade IDs, and leaves the undocumented tuple side code out of
normalized aggressor direction.

The complete adapter test file passes **105/105** in 3.04 seconds pytest time
(3.44 seconds wall), at 65,256 KiB peak RSS, zero swaps, and zero socket
messages. Ruff check/format and targeted mypy pass. These tests use mocked
responses; no live Kraken request or held source artifact was read. The current
official Kraken docs describe internal pair keys as the default response form
for [Get Order Book](https://docs.kraken.com/api-reference/market-data/get-order-book),
[Get Recent Trades](https://docs.kraken.com/api-reference/market-data/get-recent-trades),
and [Get OHLC Data](https://docs.kraken.com/api-reference/market-data/get-ohlc-data).
The Kraken source-use and retention hold still blocks live validation.

The complete 505-case Frontier suite predates Kalshi v20 and Kraken v6 and was
not rerun. At `2026-10-28T19:47:46Z`, Reality was only 28,672 bytes below
`MemoryHigh`, while memory PSI avg10/avg60 remained 0%; no broad suite was
started. I/O PSI avg10/avg60 was 0.02%/0.07%; `MemAvailable` was about 9.5 GiB.

| Requirement | Status | Evidence and boundary |
| --- | --- | --- |
| Kraken books, candles, and trades exact-pair parser contract | COMPLETE AND VERIFIED | Fixture adapter suite passes 105/105; verifies exact pair identity and rejection behavior. Live use remains held. |
| Full post-hardening Frontier suite | PARTIALLY VERIFIED | The prior 505-case pass predates Kalshi v20 and Kraken v6. |
| Genuine Kraken/cross-venue live validation | BLOCKED | Applicable source-use and retention authorization are unresolved. |
| Frontier overall | PARTIALLY VERIFIED | Live cross-venue science, broad regression, endurance, protected recovery, and deployment remain incomplete. |
| Production deployment | DEFERRED | Branch remains isolated and undeployed; production recovery and deployment gates remain separate. |
| Project Frontier overall | PARTIALLY VERIFIED | Core research platform and current bounded acceptance paths work; live cross-venue science, full broad regression, endurance, protected recovery, and deployment remain incomplete. |

The architecture and development guides were then synchronized with
Kalshi `TradeObservation` schema v4: three nullable native trade flags are
normalized, while the example-only `taker_side` value remains raw and
uninterpreted.

## Kalshi one-shot trade validation hardening — 2026-10-28 19:40 UTC

A source-path audit found that Kalshi's older `fetch_trades` collection method
did not validate each returned ticker, unlike the newer cursor-paged method. It
also accepted non-binary prices and absent timestamps/trade IDs. Adapter v20
now validates the requested ticker before the request and rejects mismatched
row tickers, missing or invalid trade IDs, prices outside `[0, 1]`, and missing
timestamps. It keeps the raw response for rejected rows and applies the same v4
trade flags to valid rows. No source request was made.

The full Kalshi-adapter test file passes **90/90** in 2.58 seconds at 60,576
KiB peak RSS. Six cases cover valid one-shot normalization and mismatched or
malformed rows; all use mocked HTTP. Ruff and formatting checks pass. This
adapter file was rerun after the v20 change, but the full 505-case Frontier
suite was run immediately before it and has not been rerun afterward.

At 19:40:36 UTC, memory PSI was avg10/avg60 0.00% and I/O PSI was at most
0.03% avg10 / 0.03% avg60. `MemAvailable` was 9,996,416 KiB. Reality remained
active at 1,207,558,144 / 1,207,959,552 bytes (about 392 KiB below
`MemoryHigh`); API remained active at 1,535,356,928 / 1,610,612,736 bytes.
No further broad test was started at this sample.

| Requirement | Status | Current evidence and boundary |
| --- | --- | --- |
| Kalshi public trade adapter, one-shot and paginated parsing | COMPLETE AND VERIFIED | Current adapter test file passes 90/90; ticker, IDs, binary price, timestamps, block flags, and raw evidence are covered with fixtures. Live collection remains held. |
| Full current-tree Frontier Python suite | PARTIALLY VERIFIED | 505/505 passed before the v20 one-shot parser hardening; after that change the complete adapter file passes 90/90. |
| Genuine Kalshi cross-venue observation | BLOCKED | Source-use policy remains in force; fixtures and documentation are not live-market evidence. |
| Frontier project overall | PARTIALLY VERIFIED | Production recovery, broad legacy regression, live cross-venue science, endurance, and deployment remain open. |

## Coinbase trade-page normalization audit — 2026-10-28 19:53 UTC

Commit `fe37b971848441f81cc5fc5f64d4cd594bf025a3` advances Coinbase Exchange
Spot to adapter v3. The trade reader now rejects booleans for the page limit,
responses larger than the requested page, string/boolean/negative/oversized
trade IDs, missing or unsupported maker-side values, and missing timestamps.
It emits `TradeObservation` schema v2 with the product identity. Coinbase's
official [Get product trades](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-trades)
reference specifies a required int32 trade ID and `buy`/`sell` side; its side
description says this is the maker order side. Frontier keeps that value in raw
evidence and leaves normalized `aggressor_side` unset. Price and size remain
exact Decimal inputs and must be positive.

The complete Coinbase fixture module passes **23/23** in 0.83 seconds pytest
time (1.30 seconds wall), with 77,172 KiB peak RSS, zero swaps, and zero socket
messages. Ruff check/format and targeted mypy pass. The only warning is the
existing Starlette/httpx `TestClient` deprecation. The test transport is local;
there was no live Coinbase request or held source artifact access. Current
terms and intended-scope checks still block Coinbase data use.

The full 505-case Frontier suite predates Kalshi v20, Kraken v6, Polymarket v9,
and Coinbase v3. At `2026-10-28T19:53:53Z`, Reality was 151,552 bytes below
`MemoryHigh`; memory and I/O PSI avg10/avg60 were 0%. No broader suite was
started.

| Requirement | Status | Evidence and boundary |
| --- | --- | --- |
| Coinbase trade-page parser contract | COMPLETE AND VERIFIED | Fixture module passes 23/23 for the official int32 ID, maker-side enum, page limit, required timestamp, and positive amounts. |
| Live Coinbase adapter validation | BLOCKED | Source-use terms and intended scope remain unresolved; no request was made. |
| Full post-hardening Frontier suite | PARTIALLY VERIFIED | The prior 505-case pass predates current adapter versions. |
| Frontier overall | PARTIALLY VERIFIED | Broad regression, genuine live cross-venue science, endurance, protected recovery, and deployment remain open. |

## Kraken OHLC row parser audit — 2026-10-28 19:55 UTC

Commit `adda6fcee9f81d16a71b99e9a5175f176e468f71` advances Kraken Spot to
`frontier-kraken-spot-7`. The REST OHLC parser requires exactly the eight
documented tuple values, parses the timestamp, validates finite nonnegative
prices/VWAP/volume, checks that open and close lie within low/high, and accepts
only a nonnegative JSON integer for trade count. Invalid input is classified
as `INVALID_CANDLES` before constructing the typed series; the bounded raw
response remains captured. The earlier exact native pair key check is also
required.

All Kraken-named adapter tests pass **25/25** in 1.03 seconds pytest time
(1.41 seconds wall), at 65,896 KiB peak RSS, zero swaps, and no socket
messages. Ruff check/format and targeted mypy pass. The tests use local mock
responses; there was no live request or held data access. The official
[Kraken Get OHLC Data](https://docs.kraken.com/api-reference/market-data/get-ohlc-data)
page shows an eight-value candle array and states that the latest candle may
be incomplete; Frontier continues to disclose that condition in the series
limit note.

The complete adapter file's 115-case pass predates this v7 change. The full
505-case Frontier suite predates Kalshi v20, Kraken v7, Polymarket v9, and
Coinbase v3. At `2026-10-28T19:55:46Z`, Reality had only 212,992 bytes below
`MemoryHigh`; memory PSI avg10/avg60 was 0%. No broad suite was started.

| Requirement | Status | Evidence and boundary |
| --- | --- | --- |
| Kraken OHLC parser contract | COMPLETE AND VERIFIED | 25 Kraken-specific fixture tests pass, covering exact eight-field rows, timestamps, nonnegative amounts, OHLC consistency, counts, and native-key binding. |
| Full current-tree adapter/Frontier suites | PARTIALLY VERIFIED | Earlier full passes predate v7 and the latest other adapter versions. |
| Live Kraken OHLC validation | BLOCKED | Source-use/retention scope remains unresolved; no request was made. |
| Frontier overall | PARTIALLY VERIFIED | Broad regression, live cross-venue evidence, endurance, protected recovery, and deployment remain open. |

## Kraken AssetPairs precision metadata audit — 2026-10-28 19:59 UTC

Commit `7c66bc1d5c0e32e14c6894dca9107fdaef69307a` advances Kraken Spot to
`frontier-kraken-spot-8`. Pair discovery now accepts `pair_decimals` and
`lot_decimals` only as exact JSON integers within the adapter's precision
bounds. Missing values, booleans, fractional numbers, numeric strings, and
out-of-range values return `INVALID_INSTRUMENT` before they can generate tick
or lot increments. This prevents permissive `int()` coercion from changing
untrusted metadata. Kraken's official
[API symbols and tickers reference](https://support.kraken.com/articles/360000920306-api-symbols-and-tickers)
shows the precision fields as numeric AssetPairs metadata; the parser's exact
integer rule is a conservative local validation contract.

The focused `tests/frontier/test_adapters.py -k kraken` selection passes
**35/35** with 99 cases deselected (1.04 seconds pytest time, 1.41 seconds
wall), 65,692 KiB peak RSS, zero swaps, and zero socket messages. Ten new
fixture cases reject invalid type and range variants across both precision
fields. Ruff check/format and strict targeted mypy pass. There was no live
Kraken request or held artifact access.

At `2026-10-28T19:59:01Z`, memory PSI avg10/avg60 was 0%. I/O PSI `some`
avg10/avg60 was 0%/0.02%; `full` was 0%. `MemAvailable` was 10,013,876 KiB and
`SwapFree` was 43,896 KiB. Reality was at 1,207,746,560 / 1,207,959,552 bytes,
212,992 bytes below `MemoryHigh`; API was at 1,546,682,368 /
1,610,612,736 bytes. The 115-case full adapter pass predates Kraken v7/v8; the
505-case Frontier suite predates the latest adapter versions. No broader suite
was started.

| Requirement | Status | Evidence and boundary |
| --- | --- | --- |
| Kraken pair precision parser | COMPLETE AND VERIFIED | 35 Kraken-focused fixture cases pass, including invalid boolean, string, fractional, missing, and out-of-range values. |
| Current full adapter/Frontier suites | PARTIALLY VERIFIED | Earlier full passes predate v8 and the latest other adapter versions. |
| Live Kraken data validation | BLOCKED | Research and retention authorization remain unresolved; no public request was made. |
| Frontier overall | PARTIALLY VERIFIED | Broad regression, genuine live cross-venue science, endurance, protected recovery, and deployment remain incomplete. |

## Shared transport response-byte enforcement — 2026-10-28 20:05 UTC

Commit `3ee3739da1b1fb48445c0d9423c9f4f1b3b9ad5a` changes the public GET
transport to request `Accept-Encoding: identity`, reject non-identity encoded
2xx responses before body reading, and measure the configured response cap over
raw streamed bytes with HTTPX `aiter_raw()`. This closes a decompression-bound
gap: the repository lock pins HTTPX 0.28.1, whose `aiter_bytes()` transparently
decodes gzip, deflate, Brotli, and Zstandard before returning data. A highly
compressible response could therefore expand before Frontier evaluated its
response-size cap. The versioned local test now supplies a 229-byte gzip body
that expands to 200,000 bytes under a 1,024-byte cap and verifies that Frontier
rejects it as unsupported encoding without decoding it. Bounded raw error
bodies retain the 429/5xx retry and failure-evidence behavior.

Because adapter-version provenance covers the shared collection behavior, the
four identifiers advanced to Polymarket 10, Kalshi 21, Kraken Spot 9, and
Coinbase Exchange Spot 4. Kalshi's normalized `taker_outcome_side` and
`taker_book_side` are also explicitly narrowed to the model's validated literal
types; accepted wire values and economics are unchanged.

The full transport contract module passes **19/19** in 2.27 seconds pytest
time (2.65 seconds wall), with 58,984 KiB peak RSS, zero swaps, and no socket
messages. The complete adapter fixture module passes **134/134** in 3.13
seconds pytest time (3.51 seconds wall), with 67,164 KiB peak RSS, zero swaps,
and no socket messages. Ruff check/format passes across the five modified
adapter/transport files and both test modules; strict targeted mypy passes for
the five Python source modules. Tests use local fixture transports only.

At `2026-10-28T20:05:40Z`, memory PSI avg10/avg60 was 0%. I/O PSI `some`
avg10/avg60 was 0.01%/0.02%; `full` was 0%. `MemAvailable` was 9,911,416 KiB
and `SwapFree` was 44,056 KiB. Reality was at 1,207,709,696 /
1,207,959,552 bytes, 249,856 bytes below `MemoryHigh`; API was at
1,551,216,640 / 1,610,612,736 bytes. No broad Frontier or legacy suite was
started, and no public source was contacted. The 505-case Frontier suite
predates this change.

| Requirement | Status | Evidence and boundary |
| --- | --- | --- |
| Shared transport byte bound | COMPLETE AND VERIFIED | 19 fixture contract cases pass, including encoded expansion larger than the configured cap. |
| Current adapter fixture modules | COMPLETE AND VERIFIED | The complete 134-case adapter module passes after the transport and version updates. |
| Full current-tree Frontier and legacy suites | PARTIALLY VERIFIED | The 505-case Frontier pass predates current adapter versions and transport; broader legacy regression remains unrun. |
| Live multi-venue validation | BLOCKED | Source-use/retention holds remain; no live collection or cross-venue observation is claimed. |
| Frontier overall | PARTIALLY VERIFIED | Scientific coverage, broad regression, endurance, protected recovery, and deployment remain incomplete. |

## Bounded encoded-response evidence follow-up — 2026-10-28 20:08 UTC

Commit `cdee9cee690b3e3982ffc16aa2abcaeebf8f40c4` improves the unsupported
content-encoding path while preserving the raw-byte limit. For a live,
streaming 2xx response, Frontier reads raw wire chunks only up to the existing
cap, then rejects non-identity encoding without asking HTTPX to decode it. If
the complete body fits the cap, its compressed bytes are stored in
`FailedResponseEvidence`; an oversized body gets bounded rejection diagnostics.
If an isolated `MockTransport` fixture has already buffered the response, the
adapter rejects an encoded 2xx response before accessing the decoded-content
property. HTTPX's official
[async streaming reference](https://www.python-httpx.org/async/) specifies that
`aiter_raw()` yields raw bytes without content decoding; the repository lock
pins HTTPX 0.28.1. The gzip test uses a 229-byte payload that expands to 200,000
bytes against a 1,024-byte cap and verifies exact compressed-byte evidence.

The transport contract module passes **19/19** in 2.28 seconds pytest time
(2.64 seconds wall), with 58,928 KiB peak RSS, zero swaps, and no socket
messages. The full adapter fixture module passes **134/134** against this final
transport in 2.88 seconds pytest time (3.27 seconds wall), with 61,028 KiB peak
RSS, zero swaps, and no socket messages. Ruff and strict targeted mypy pass.
No source requests or held data artifacts were accessed.

The pre-test admission sample at `2026-10-28T20:07:38Z` measured memory PSI
avg10/avg60 0%, I/O PSI `some` avg10/avg60 0%/0.04% and `full` 0%,
`MemAvailable` 9,979,384 KiB, and `SwapFree` 47,968 KiB. Reality was
1,207,795,712 / 1,207,959,552 bytes, 163,840 bytes below `MemoryHigh`; API was
1,552,601,088 / 1,610,612,736 bytes. No broad suite was started.

| Requirement | Status | Evidence and boundary |
| --- | --- | --- |
| Encoded response cap and evidence | COMPLETE AND VERIFIED | Fixture tests validate raw bounded capture and reject an encoded expansion without decompression. |
| Current adapter fixture modules | COMPLETE AND VERIFIED | The 134-case adapter module passes against current adapter identifiers and final transport behavior. |
| Full Frontier and legacy regression | PARTIALLY VERIFIED | The prior 505-case suite predates current versions; broad legacy regression remains unrun. |
| Live multi-venue science | BLOCKED | Source-use and retention gates remain unresolved; no cross-venue live observation is claimed. |
| Frontier overall | PARTIALLY VERIFIED | Broad regression, live market evidence, endurance, protected recovery, and deployment remain open. |

## Encoded-response evidence persistence — 2026-10-28 20:11 UTC

Commit `e8353ff2ee8e6c39fd8eda94e8e926afeb113e4e` adds an API-level
reproducibility check for encoded transport failures. The fixture supplies a
gzip body whose decompressed payload exceeds the configured response limit.
Frontier rejects the response as `UNSUPPORTED_CONTENT_ENCODING`, persists the
bounded raw compressed bytes as base64 in a temporary evidence store, preserves
their SHA-256, and labels the record `transport_response` with the same error
code. The source health is subsequently recovered by the existing valid local
fixture. The test does not contact an exchange.

The focused API integration test passes **1/1** in 3.03 seconds pytest time
(3.53 seconds wall), at 88,748 KiB peak RSS, zero swaps, and zero socket
messages. Ruff passes. The existing Starlette/httpx `TestClient` deprecation
is the only warning. No broader suite was started.

At `2026-10-28T20:11:08Z`, memory PSI avg10/avg60 was 0%; I/O PSI `some`
avg10/avg60 was 0.29%/0.22% and `full` was 0.22%/0.14%. `MemAvailable` was
9,883,468 KiB and `SwapFree` 48,040 KiB. Reality was at 1,207,939,072 /
1,207,959,552 bytes, only 20,480 bytes below `MemoryHigh`; API was at
1,560,555,520 / 1,610,612,736 bytes. No further tests were run after this
sample.

| Requirement | Status | Evidence and boundary |
| --- | --- | --- |
| Durable encoded-failure evidence | COMPLETE AND VERIFIED | The API fixture proves bounded raw bytes, base64 representation, hash, classification, and health recovery. |
| Current adapter and transport fixture suites | COMPLETE AND VERIFIED | The adapter module passes 134/134 and the transport module 19/19 against the final code. |
| Full current Frontier and legacy regressions | PARTIALLY VERIFIED | The prior 505-case Frontier run predates current adapter and transport changes; broad legacy testing remains unrun. |
| Genuine live cross-venue science | BLOCKED | Source authorization/retention gates remain; fixture evidence is not live-market validation. |
| Frontier overall | PARTIALLY VERIFIED | Broad regression, live observations, endurance, protected recovery, and deployment remain incomplete. |

## Frontend build, unit, and browser verification — 2026-10-28 20:18 UTC

The isolated frontend typecheck and production bundle pass. Vite transformed
2,230 modules in 28.29 seconds wall time; measured maximum RSS was 560,236
KiB, with no swaps. The Frontier route is code-split into a 183.24 kB bundle
(44.69 kB gzip). The chart chunk remains 544.51 kB minified (186.79 kB gzip)
and triggers Vite's 500 kB advisory. Chart import already uses a deferred
feature boundary; the advisory was retained rather than hidden by changing the
threshold.

Frontend unit verification passes **47 tests across 9 files** in 29.23 seconds
wall time, with 240,556 KiB maximum RSS and no swaps. ESLint and Prettier checks
pass across the frontend in 16.11 seconds wall time, with 347,084 KiB maximum
RSS.

Playwright ran all seven cases in `apps/web/e2e/frontier.spec.ts`, completing
in 21.9 seconds. It used a temporary SQLite store, `MIDAS_MODE=demo`, an
isolated local API and Vite server, and a 2 GiB cgroup memory cap. The temporary
servers used loopback ports 18000 and 15173 and exited after the run. The
source-probe assertions remained zero; the browser fixtures do not establish
live adapter or cross-venue validity. Output is retained under
`/tmp/midas-frontier-playwright-frontier-20261028` and
`/tmp/midas-browser-frontier-20261028`.

An initial build invocation under `RLIMIT_AS=2 GiB` exited before compilation
because Node could not allocate its WebAssembly runtime. The same build
succeeded under the cgroup memory cap, showing that the earlier failure was a
virtual-address-space restriction in the runner rather than a project build
error.

At `2026-10-28T20:20:04Z`, host `MemAvailable` was 9,950,196 KiB and memory
PSI avg10 was 0%. I/O PSI `some` avg10/avg60 was 0.12%/0.10%, with `full` 0%.
Reality measured 1,207,869,440 / 1,207,959,552 bytes, only 90,112 bytes below
`MemoryHigh`; API measured 1,559,650,304 / 1,610,612,736 bytes. Despite host
headroom and low PSI, that volatile protected-service margin does not justify
a broad backend regression. No public source probe or production service
operation was performed.

| Requirement | Status | Evidence and boundary |
| --- | --- | --- |
| Frontend typecheck and production build | COMPLETE AND VERIFIED | Build passes with the chart size advisory preserved. |
| Frontend unit suite | COMPLETE AND VERIFIED | 47 tests pass in 9 files. |
| Frontier browser acceptance | COMPLETE AND VERIFIED | Seven local demo E2E scenarios pass; they provide no live-market evidence. |
| Frontend lint and formatting | COMPLETE AND VERIFIED | ESLint and Prettier checks pass. |
| Current full backend/legacy regression | PARTIALLY VERIFIED | Latest full 505-case Frontier pass predates current adapter and transport changes; broader tests remain deferred under the recorder resource gate. |
| Live cross-venue scientific validation | BLOCKED | Source-use/retention gates remain unresolved. |
| Frontier overall | PARTIALLY VERIFIED | Live cross-venue evidence, broad regression, endurance, protected recovery, and deployment remain incomplete. |

## Kalshi and Polymarket book request binding — 2026-10-28 20:32 UTC

Commit `dcb522d9538b7782a01db2efccc82e63d737f009` advances the Kalshi and
Polymarket adapters to `frontier-kalshi-23` and `frontier-polymarket-12`.
Kalshi now binds its book request to a revalidated native ticker, canonical
market ID, USD settlement identity, exact YES/NO contract instruments, and
binary payout vectors. Book depth must be an actual integer. Polymarket now
revalidates its market/outcome mapping, protocol-specific quote and settlement
metadata, and the instrument IDs against the native v1 `clobTokenIds` or v2
`positionIds` retained at discovery. Invalid identities fail before CLOB book
transport.

The combined `test_adapters.py -k 'kalshi or polymarket'` selection passes
**105 tests** with 61 deselected in 2.64 seconds pytest time (3.03 seconds
wall). Maximum RSS was 67,372 KiB, with zero swaps and zero socket messages.
The selection includes 8 Kalshi market-corruption cases, 3 invalid-depth
cases, 12 Polymarket market-corruption variants, and a v2 `positionIds`
mismatch rejection. Ruff check/format and strict mypy pass for the changed
modules. The run used fixture-only `MockTransport` responses; it is not live
exchange validation.

No current full backend regression was run. The latest protected-service
sample recorded for this checkpoint is `2026-10-28T20:25:57Z`: Reality was
65,536 bytes below `MemoryHigh`, and API usage was 1,562,820,608 /
1,610,612,736 bytes. The focused tests ran in a transient 1 GiB cgroup with no
swaps. Public source probes remain blocked by the source-use/retention gate,
and the held `data/frontier-public-probes/` path was not read or modified.

| Requirement | Status | Evidence and boundary |
| --- | --- | --- |
| Kalshi and Polymarket book request binding | COMPLETE AND VERIFIED | Native market, instrument, outcome, settlement, and depth checks pass focused adversarial fixtures. |
| Live Kalshi and Polymarket book validation | BLOCKED | No public exchange calls were made; fixture validation does not prove current source behavior. |
| Current broad Frontier/legacy regression | PARTIALLY VERIFIED | Focused adapter tests pass; the broad suite remains deferred under volatile protected-service memory headroom. |
| Frontier overall | PARTIALLY VERIFIED | Live cross-venue science, full regression, endurance, protected recovery, and deployment remain incomplete. |

## Research-only boundary and resource recheck — 2026-10-28 20:35 UTC

A static review of the Frontier adapter, API, and workspace paths found no
exchange order submission/cancellation, deposit/withdrawal, wallet,
private-key, or exchange API-key operation. `PublicReadTransport` issues
anonymous HTTPS `GET` requests through a fixed host allowlist and does not
follow redirects. API POST routes found in this scope are local research
operations such as replay, collection, and public-data probes. This code
review does not certify runtime security against every possible caller.

At `2026-10-28T20:34:48Z`, protected Reality and API services were active and
untouched. Reality measured 1,207,480,320 / 1,207,959,552 bytes, 479,232 bytes
below `MemoryHigh`; API measured 1,567,940,608 / 1,610,612,736 bytes. Host
`MemAvailable` was 9,930,252 KiB and `SwapFree` 48,608 KiB. Memory PSI avg10
was 0%; I/O PSI `some` avg10/avg60/avg300 was 0.62% / 0.32% / 0.08%. This
single reading does not establish sustained admission margin. No public
source request or broad test was run after the sample.

| Requirement | Status | Evidence and boundary |
| --- | --- | --- |
| External trading boundary | COMPLETE AND VERIFIED WITHIN REVIEW SCOPE | External adapters use the anonymous GET-only transport; no exchange execution or account path was found in the reviewed Frontier scope. |
| Broad test admission | BLOCKED | Reality remained 479,232 bytes below `MemoryHigh`; sustained margin is not established. |
| Frontier overall | PARTIALLY VERIFIED | Live cross-venue validation, broad regressions, endurance, protected recovery, and deployment remain incomplete. |

## Current adapter contract regression — 2026-10-28 20:36 UTC

At tree `7971acff50a771630f1b245ce2757e6069696451`, the full
`tests/frontier/test_adapters.py` module passes **166/166** in 2.97 seconds
pytest time (3.37 seconds wall), at 61,132 KiB maximum RSS with zero swaps and
zero socket messages. It ran inside a transient 1 GiB cgroup cap. The full
Coinbase adapter module passes **33/33** with one existing Starlette/httpx
`TestClient` deprecation warning. Strict mypy passes for all four adapters;
Ruff and formatting pass for the adapters and their test modules.

The latest pre-run protected-service sample was `2026-10-28T20:34:48Z`.
Reality used 1,207,480,320 / 1,207,959,552 bytes, 479,232 bytes below
`MemoryHigh`; API used 1,567,940,608 / 1,610,612,736 bytes. I/O PSI `some`
avg10 was 0.62%. The bounded adapter component run completed without swaps or
socket traffic; this does not clear the gate for a full Frontier, Arena, or
legacy MIDAS suite. Both services remained active and untouched.

| Requirement | Status | Evidence and boundary |
| --- | --- | --- |
| Current four-venue adapter contract regression | COMPLETE AND VERIFIED | 166 adapter tests plus 33 Coinbase tests pass on the current tree using fixtures. |
| Four adapter modules typechecked and styled | COMPLETE AND VERIFIED | Strict mypy and Ruff check/format pass. |
| Full Frontier/legacy regressions | PARTIALLY VERIFIED | Not rerun at this tree; protected service headroom is not sustained. |
| Live cross-venue research | BLOCKED | No new venue calls were made; source-use and retention boundaries remain. |
| Frontier overall | PARTIALLY VERIFIED | Cross-venue live science, broad regression, endurance, protected recovery, and deployment remain incomplete. |

## Polymarket condition identifier validation — 2026-10-28 20:38 UTC

Commit `f8be86b6cb57f0eb17e17cfaee832698cb1b58c7` advances Polymarket to
`frontier-polymarket-13`. Before a book request, `fetch_book` now validates
that `conditionId` has the documented 32-byte hex form, in addition to the
native market, protocol, outcome order, and native token/position ID bindings.
Missing and malformed identifiers have distinct fixture cases.

The full `tests/frontier/test_adapters.py` module passes **167/167** in 3.23
seconds pytest time (3.63 seconds wall), with 68,624 KiB maximum RSS, zero
swaps, and zero socket messages, inside a transient 1 GiB cgroup. Strict mypy
passes for all four exchange adapters; Ruff and formatting pass across all
four adapters and their test files. No live exchange endpoint was called.

The format requirement follows the Polymarket Institute research guide's
description of `conditionId` as a blockchain identifier and its 32-byte
hexadecimal example. Current official source-use material for Kalshi, Kraken,
Coinbase, and Polymarket was refreshed in this turn and recorded in the source
terms review. No captured source data was opened. The source holds remain in
force, so there is no new cross-venue live match. The full Frontier, Arena,
and legacy regression suites remain deferred under the protected-service
resource gate.

| Requirement | Status | Evidence and boundary |
| --- | --- | --- |
| Polymarket condition ID validation | COMPLETE AND VERIFIED | Missing and malformed IDs reject before book I/O; adapter fixtures pass. |
| Current adapter regression | COMPLETE AND VERIFIED | 167/167 adapter tests pass with fixture-only transports. |
| Live cross-venue validation | BLOCKED | Kalshi, Kraken, and Coinbase use remains held; no live match is represented. |
| Full Frontier/legacy regression | PARTIALLY VERIFIED | Not run at this checkpoint; Reality remains close to `MemoryHigh`. |
| Frontier overall | PARTIALLY VERIFIED | Live cross-venue science, broad regression, endurance, recovery, and deployment remain open. |

## Official source-use terms refresh — 2026-10-28 20:37 UTC

Read-only review of the current linked official materials reconfirmed the
source-use boundaries documented in
`SOURCE_DATA_TERMS_REVIEW_2026-10-27.md`. Kalshi's Developer Agreement still
limits API use to facilitating the member's own trading, while its Data Terms
restrict software development, collection/retention, and AI-related uses
without written authorization. Kraken's API guide requires prior permission
for certain uses, including non-personal commercial use of public market data;
the reviewed EEA terms also restrict extraction and automated applications,
but the applicable regional terms remain unresolved. Coinbase's terms provide
a limited personal/entity research license but restrict outside-organization
display or redistribution, end-user applications, and AI/ML development or
validation absent written consent. Polymarket's research guide continues to
describe open research APIs and distinguishes the global and US-only services.

No exchange API was queried, no exchange was contacted, and no retained source
capture was opened. This is an operational gate, not legal advice or an
individual eligibility decision. Keep Kalshi, Kraken, and Coinbase held until
research, retention, automation, and display scope is covered by validated
permission. Polymarket's research guide does not establish user-specific
regional eligibility or permission to use unrelated service data.

| Requirement | Status | Evidence and boundary |
| --- | --- | --- |
| Current official source-use review | COMPLETE AND VERIFIED WITHIN REVIEW SCOPE | Official terms/API guide and researcher guide refreshed without using venue endpoints or stored captures. |
| Live Kalshi/Kraken/Coinbase collection | BLOCKED | Current review does not establish scope-specific permission for the Frontier research and retention plan. |
| Polymarket research integration | IMPLEMENTED, LIVE VALIDATION PENDING | Public research guide supports the documented global API use; individual eligibility remains unverified. |
| Frontier overall | PARTIALLY VERIFIED | Cross-venue live science, broad regressions, endurance, protected recovery, and deployment remain incomplete. |

## Coinbase book depth type validation — 2026-10-28 20:33 UTC

Commit `46cd7ad` advances Coinbase Spot to
`frontier-coinbase-exchange-spot-6` and rejects boolean, floating-point, and
string book-depth values before transport. Valid depth remains an integer
from 1 through 20.

The focused Coinbase fixture module passes **33/33** in 0.85 seconds pytest
time (1.33 seconds wall), with 76,904 KiB maximum RSS, zero swaps, and zero
socket messages. Three invalid-depth cases verify that no book request is
issued. Ruff check/format and strict mypy pass. The one warning is the
existing Starlette/httpx `TestClient` deprecation. No Coinbase network request
was made.

This is bounded adapter-contract evidence, not source validation. The latest
protected-service memory sample recorded for this mission remains
`2026-10-28T20:25:57Z`, when Reality was 65,536 bytes below `MemoryHigh`.
Broader regressions remain deferred; the focused suite ran under a transient
1 GiB cgroup cap with no swaps.

| Requirement | Status | Evidence and boundary |
| --- | --- | --- |
| Coinbase book-depth input validation | COMPLETE AND VERIFIED | Invalid depth types reject before I/O; all 33 focused fixture tests pass. |
| Coinbase live behavior | BLOCKED | No public source request was made; source-use/retention review remains unresolved. |
| Current full Frontier regression | PARTIALLY VERIFIED | Focused adapter tests pass; full regression remains deferred by the resource gate. |
| Frontier overall | PARTIALLY VERIFIED | Live cross-venue science, broad regression, endurance, protected recovery, and deployment remain incomplete. |

## Coinbase book input binding — 2026-10-28 20:23 UTC

Commit `c3bcb131ca57e2ca610dcda720b58cd293846039` advances the Coinbase Spot
adapter to `frontier-coinbase-exchange-spot-5`. `fetch_book` now revalidates
the supplied market and rejects it before transport unless the canonical
market identity, base/quote assets, sole instrument, native instrument ID,
quantity unit, and quote-currency identity match the configured product.

Seven fixture mutations exercise missing/duplicate instruments and changed
market or instrument identities. The full Coinbase fixture module passes
**30/30** in 0.78 seconds pytest time (1.26 seconds wall), at 78,176 KiB
maximum RSS, with no swaps or socket messages. Ruff and strict mypy pass. The
only warning is the existing Starlette/httpx `TestClient` deprecation. The
Coinbase source-use hold remains active; these local fixtures do not validate
live source behavior.

At `2026-10-28T20:23:33Z`, `MemAvailable` was 9,943,808 KiB and memory PSI
avg10 was 0%; I/O PSI `some` avg10/avg60 was 0%/0%, with `full` 0%. Reality
was 1,207,795,712 / 1,207,959,552 bytes, 163,840 bytes below `MemoryHigh`; API
was 1,563,070,464 / 1,610,612,736 bytes. The focused module ran inside a
transient 1 GiB cgroup cap. Broad regression remains deferred because recent
samples show volatile protected-service memory headroom.

| Requirement | Status | Evidence and boundary |
| --- | --- | --- |
| Coinbase book input binding | COMPLETE AND VERIFIED | Invalid or mismatched market metadata is rejected before book transport. |
| Coinbase live validation | BLOCKED | Source-use/retention hold remains; fixtures are not live evidence. |
| Current full Frontier/legacy regression | PARTIALLY VERIFIED | Latest full Frontier run predates current adapter changes. |
| Frontier overall | PARTIALLY VERIFIED | Cross-venue live science, broad regression, endurance, protected recovery, and deployment remain incomplete. |

## Kraken book input binding — 2026-10-28 20:25 UTC

Commit `616e5cfa83b236802369d2c8d348d6baff731b92` advances Kraken Spot to
`frontier-kraken-spot-10`. Before a depth request, `fetch_book` now
revalidates the market, canonical pair identity, raw pair asset metadata,
base/quote fields, sole instrument, quantity unit, and quote identity. Invalid
or cross-bound objects return `INVALID_INSTRUMENT` without requesting `/Depth`.

Eight fixture corruptions exercise those bindings. The Kraken-focused
`test_adapters.py` selection passes **43 tests** (99 deselected) in 1.06 seconds
pytest time (1.45 seconds wall), at 65,764 KiB maximum RSS, with no swaps or
socket messages. Ruff and strict mypy pass. An initial run failed only because
the test expected `/AssetPairs` instead of `/0/public/AssetPairs`; after
correcting the test's expected path, all 43 cases passed. No live Kraken
request was made.

At `2026-10-28T20:25:57Z`, `MemAvailable` was 9,899,784 KiB and memory PSI
avg10 was 0%; I/O PSI `some` avg10/avg60 was 0%/0.01%, with `full` 0%. Reality
was 1,207,894,016 / 1,207,959,552 bytes, 65,536 bytes below `MemoryHigh`; API
was 1,562,820,608 / 1,610,612,736 bytes. The focused tests ran inside a
transient 1 GiB cgroup cap. Broad regression remains deferred under the
volatile protected-service memory gate.

| Requirement | Status | Evidence and boundary |
| --- | --- | --- |
| Kraken book input binding | COMPLETE AND VERIFIED | Eight malformed-market variants reject before depth I/O; 43 Kraken-focused fixture cases pass. |
| Kraken live validation | BLOCKED | Source-use/retention scope remains unresolved; fixture evidence is not live data. |
| Current full Frontier/legacy regression | PARTIALLY VERIFIED | Current focused adapter contracts pass; the full suite predates the recent adapter changes. |
| Frontier overall | PARTIALLY VERIFIED | Live cross-venue science, broad regression, endurance, protected recovery, and deployment remain incomplete. |

## Current Frontier completion matrix — 2026-10-28 20:40 UTC

This is the current handoff snapshot for branch `codex/frontier-20261026`,
code commit `f8be86b`, and documentation head `9f415a8`. The only remaining
untracked path is the preserved `data/frontier-public-probes/`; it was not
read, modified, staged, or deleted.

| Deliverable | Current status | Evidence and remaining boundary |
| --- | --- | --- |
| Exchange-independent adapter protocol, capability registry, and normalization | COMPLETE AND VERIFIED WITHIN FIXTURE SCOPE | Polymarket, Kalshi, Kraken, and Coinbase adapters are implemented; the 167-case adapter module, 33-case Coinbase module, strict typing, and style checks pass. Live validation varies by source and remains pending or held. |
| Canonical instruments, payoff semantics, and source provenance | PARTIALLY VERIFIED | Exact identities and bounded source metadata are implemented; source-specific and economic assertions remain unverified where evidence is absent. |
| Relationship graph and cross-market candidate generation | PARTIALLY VERIFIED | Persistence, deterministic fixture construction, and candidate families are tested; genuine cross-venue equivalence is not established. |
| Independent mathematical and multi-venue economics | PARTIALLY VERIFIED | Decimal-based verification, cost sensitivity, and virtual capital/carry models are implemented and fixture-tested; no live eligible opportunity or executable-profit claim exists. |
| Collection, durable evidence, replay, and reproducibility | PARTIALLY VERIFIED | Bounded records, hashes, and deterministic replay are implemented; sustained multi-source synchronization and endurance remain unmeasured. |
| Laboratory/Arena integration | PARTIALLY VERIFIED | Frontier-specific bounded paths pass; full legacy Arena regression and production-worker readiness remain unverified. |
| Frontier Mission Control workspace | COMPLETE AND VERIFIED WITHIN TESTED SCOPE | Prior frontend tests, typecheck, production build, and seven local E2E scenarios pass; no UI changes occurred in the latest adapter checkpoints. |
| Current Frontier Python suite | PARTIALLY VERIFIED | The 167-case adapter module and 33-case Coinbase module pass; the 505-case full Frontier run predates the latest adapter changes. |
| Full web and broader MIDAS/Arena regressions | PARTIALLY VERIFIED | Prior bounded UI checks pass; no exact-tree full-web or broader legacy suite was run in this checkpoint. |
| Live Kalshi/Kraken/Coinbase research | BLOCKED | Current official terms do not establish permission for Frontier's intended research, retention, automation, and display scope. |
| Live cross-venue relationship and economic result | BLOCKED | No authorized genuine cross-venue observation or economic match is available; fixtures remain explicitly synthetic. |
| Resource sustainability and protected recovery | PARTIALLY VERIFIED | Short bounded runs are measured; Reality remains close to `MemoryHigh`, and no endurance or current-boundary recovery proof exists. |
| Production deployment | DEFERRED | Frontier remains isolated and undeployed; the user's protected-service and deployment exclusions remain in force. |
| Project Frontier overall | PARTIALLY VERIFIED | Core implementation is substantial, but live cross-venue science, broad exact-tree regressions, endurance, protected recovery, and deployment prerequisites remain open. |

No exchange endpoint was queried in this checkpoint. No service was restarted,
reconfigured, or deployed. The last resource sample at `2026-10-28T20:34:48Z`
showed Reality only 479,232 bytes below `MemoryHigh`, so the broad Frontier,
Arena, and legacy suites remain deferred. Continue with source-independent,
bounded work and update this matrix when evidence changes.

## Polymarket geographic access boundary — 2026-10-28 20:42 UTC

The official Polymarket restriction page lists restricted countries and
regions and does not list Sweden. It also makes restrictions location-dependent
and prohibits VPN/proxy circumvention. Because the user is traveling, the
physical location of the host for any future request is not established by the
configured Europe/Stockholm timezone. No API request was made. Polymarket
research-source validation therefore remains pending verified physical
eligibility; this does not alter the other venues' terms holds.

| Requirement | Status | Evidence and boundary |
| --- | --- | --- |
| Polymarket research use | IMPLEMENTED, LIVE VALIDATION PENDING | Official research guide is available; physical eligibility at request time remains unknown. |
| Geographic restriction compliance | PARTIALLY VERIFIED | Official list reviewed; no endpoint request or circumvention occurred. |
| Frontier overall | PARTIALLY VERIFIED | Cross-venue live evidence, exact-tree broad regression, endurance, protected recovery, and deployment remain open. |

## Latest implementation checkpoint — 2026-10-28 20:45 UTC

Commit `bc00a34b966e` hardens pair-based cross-venue candidate generation.
Each book must identify the exact selected venue, native market, native
instrument, and quantity unit before displayed prices enter the economics.
Candidate/replay economic model identity is now
`frontier-economic-verifiers-22`. The directly affected economics/replay and
logical implication modules pass **104/104** fixture tests; Ruff check/format
and whitespace checks pass. The bounded run peaked at **69,148 KiB RSS** in a
1 GiB transient scope with zero swaps or socket messages. No source endpoint
was queried.

| Component | Current status | Evidence and remaining boundary |
| --- | --- | --- |
| Pair-based candidate book identity | COMPLETE AND VERIFIED | Wrong market, instrument, or quantity-unit snapshots are rejected before quote arithmetic. |
| Focused economic and replay regression | COMPLETE AND VERIFIED | 104/104 tests pass on this checkpoint. |
| Full current Frontier and legacy regressions | PARTIALLY VERIFIED | Broad suites remain unrun while Reality is close to `MemoryHigh`. |
| Live cross-venue market relationship | BLOCKED | Source-use scope and location authorization remain unresolved; no live cross-venue result is claimed. |
| Frontier overall | PARTIALLY VERIFIED | Live science, broad regressions, endurance, protected recovery, and deployment prerequisites remain open. |

## Latest implementation checkpoint — 2026-10-28 20:48 UTC

Commit `68bc6f2` advances the candidate/replay economic identity to
`frontier-economic-verifiers-23` and validates a source timing invariant:
`BookSnapshot.received_at_utc` must equal the response receipt time in its
provenance. The check also runs during structural revalidation of unvalidated
model copies, so candidate generation fails closed on a tampered or
misassociated timestamp. A fixture update keeps the existing asynchronous-book
scenario valid while still testing two seconds of receipt skew.

Four focused modules covering all four adapters, pair and multi-outcome
economics, and replay pass **305/305**. Strict mypy passes for the four core
economic/model modules. Ruff check/format and whitespace checks pass. The test
run used a 1 GiB transient scope, peaked at **95,148 KiB RSS**, and produced no
swaps or socket messages. One initial run exposed the old inconsistent fixture;
the corrected rerun passed completely. No public endpoint was queried.

| Component | Current status | Evidence and remaining boundary |
| --- | --- | --- |
| Book receipt/provenance timing integrity | COMPLETE AND VERIFIED | Constructor and structural revalidation reject divergent receipt timestamps. |
| Focused adapter, economics, and replay regression | COMPLETE AND VERIFIED | 305/305 cases pass on commit `68bc6f2`. |
| Exact-tree full Frontier and legacy regression | PARTIALLY VERIFIED | Broad suites remain unrun under the protected service resource gate. |
| Live cross-venue relationship and economics | BLOCKED | Source-use terms and current location remain unresolved; fixture results are not live claims. |
| Frontier overall | PARTIALLY VERIFIED | Live science, broad regressions, endurance, protected recovery, and deployment prerequisites remain open. |

## Latest implementation checkpoint — 2026-10-28 20:49 UTC

Commit `f13bb2212c98` advances the replay economic identity to
`frontier-economic-verifiers-24`. The `BookSnapshot` integrity rule now binds
both local receipt time and parsed exchange time to their copies in
provenance. This protects freshness and cross-venue timestamp comparisons
against an internally altered snapshot. Venues that do not supply a unified
book timestamp retain `None` in both fields, while per-level timestamps remain
independent.

The four focused adapter, economics, and replay modules pass **306/306** after
one existing future-time fixture was corrected to move its provenance copy
along with the book timestamp. The run took 4.26 seconds of pytest time, peaked
at **94,148 KiB RSS** under a 1 GiB transient scope, and produced no swaps or
socket messages. Strict mypy passed for the core model, economics, replay, and
independent-audit modules; Ruff and whitespace checks pass. No source API was
queried.

| Component | Current status | Evidence and remaining boundary |
| --- | --- | --- |
| Book receipt/exchange time provenance | COMPLETE AND VERIFIED | Construction and structural revalidation reject either timestamp mismatch. |
| Focused adapter/economics/replay regression | COMPLETE AND VERIFIED | 306/306 fixture cases pass on commit `f13bb2212c98`. |
| Full Frontier and legacy regression | PARTIALLY VERIFIED | Exact-tree broad suites remain unrun under the protected resource gate. |
| Live cross-venue economics | BLOCKED | Exchange data-use scope and current location remain unresolved; no live opportunity is claimed. |
| Frontier overall | PARTIALLY VERIFIED | Live evidence, broad regressions, endurance, protected recovery, and deployment remain open. |

## Latest implementation checkpoint — 2026-10-28 20:52 UTC

Commit `ea04e319c219` converts normalized stored-book validation failures in
`/books` and replay loading into explicit HTTP 409 responses. Coverage
analytics continues counting invalid book records as excluded evidence. An
integration fixture recomputes a stored row hash after introducing a
provenance-inconsistent timestamp and verifies that `/books` and `/replay`
reject it without contacting an adapter or changing the stored row. A valid
synthetic cross-venue book/replay flow also passes.

The two focused API tests pass; the scoped process peaked at **86,560 KiB RSS**
with zero swaps or socket messages. Ruff and whitespace checks pass. Strict
mypy on the API module still has 15 unrelated `no-any-return` diagnostics; the
new validator and loader have no diagnostic. Memory PSI was elevated at the
latest sample, so broader tests remain deferred. No source endpoint was
queried, and no protected service was changed.

| Component | Current status | Evidence and remaining boundary |
| --- | --- | --- |
| Stored book validation error handling | COMPLETE AND VERIFIED | Invalid normalized books return explicit 409 from the public book read and replay paths. |
| Valid stored book/replay API | COMPLETE AND VERIFIED WITHIN FIXTURE SCOPE | Existing synthetic cross-venue replay flow passes. |
| API module strict typing | PARTIALLY VERIFIED | 15 unrelated existing `no-any-return` issues remain in the module. |
| Full current Frontier and MIDAS regressions | PARTIALLY VERIFIED | Deferred under elevated system memory pressure. |
| Frontier overall | PARTIALLY VERIFIED | Live science, broad regressions, endurance, protected recovery, and deployment remain open. |

## Latest implementation checkpoint — 2026-10-28 20:55 UTC

Commit `2205227e0b0d` extends the timestamp/provenance integrity rule to
`TradeObservation`. Local receipt and parsed exchange timestamps must match
their provenance copies, with both source-time fields absent when no unified
exchange timestamp is available. The `/trades` route already reports model
validation failures as HTTP 409; its regression now confirms that a hash-valid
stored row with an altered exchange timestamp is rejected without source
access.

The four-adapter contract module, Coinbase module, and focused stored-trade API
case pass **201/201**. The process peaked at **87,776 KiB RSS** under a 1 GiB
transient scope with zero swaps or socket messages. Strict mypy passes for the
core model, economics, replay, and independent-audit modules. Ruff and
whitespace checks pass. At `2026-10-28T20:55:32Z`, memory PSI remained elevated
and the API was **114,688 bytes below** its `MemoryHigh` boundary, so the full
suites remain unrun. No public endpoint or protected service was touched.

| Component | Current status | Evidence and remaining boundary |
| --- | --- | --- |
| Book and trade timestamp provenance | COMPLETE AND VERIFIED | Both receipt and exchange timestamps are checked against source provenance. |
| Focused adapter and trade API regression | COMPLETE AND VERIFIED | 201/201 fixture cases pass on commit `2205227e0b0d`. |
| Full exact-tree Frontier/MIDAS regression | PARTIALLY VERIFIED | Deferred under elevated PSI and the near-boundary API resource sample. |
| Live cross-venue research | BLOCKED | Data-use and physical-location authorization remain unresolved. |
| Frontier overall | PARTIALLY VERIFIED | Live evidence, broad regression, endurance, protected recovery, and deployment remain open. |

## Exact collection-capture provenance — 2026-10-28 21:01 UTC

Implementation and collector tests are committed as `49d7827` on
`codex/frontier-20261026`.

Collector version `frontier-finite-collection-3` binds normalized market and
book evidence to the captured request URL, adapter version, request start,
response receipt, monotonic request duration, and raw-body SHA-256. A matching
body hash alone no longer suffices. The discovery path checks every normalized
market against an exact capture; the book path checks its one pinned response
and the adapter version recorded by the run. The pending checkpoint validator
reapplies these bindings before a newly captured observation can be persisted.
Lineage failures preserve the original raw response as a diagnostic record.

The complete collector module passes **36/36** tests in 9.19 seconds within a
transient scope capped at 1 GiB RAM, zero swap, and 50% CPU. Focused coverage
also confirms a valid resumable collection and invalid URL provenance rejection
for both market and book captures. Strict mypy passes on
`packages/midas/frontier/collection.py`; Ruff check, Ruff format check, and
`git diff --check` pass. No external endpoint was contacted.

At `2026-10-28T21:01:22Z`, Reality remained active at 1,207,685,120 bytes of
1,207,959,552-byte `MemoryHigh`; API remained active at 1,608,720,384 bytes of
1,610,612,736-byte `MemoryHigh`. Memory PSI avg10 was 0%, avg300 `some` was
11.79%; host available memory was 10.30 GB and swap had 49.98 MB free. The
services were not modified. Broad Frontier/MIDAS regression remains deferred
while the protected services have little soft-limit margin.

| Requirement | Status | Evidence and boundary |
| --- | --- | --- |
| Collector request/capture provenance | COMPLETE AND VERIFIED | Normalized market/book lineage binds URL, adapter version, request and receipt times, monotonic duration, and raw hash. |
| Exact-tree collector tests | COMPLETE AND VERIFIED | 36/36 tests pass on the current code. |
| Full Frontier and MIDAS regression | PARTIALLY VERIFIED | Broad suites remain unrun under the protected-service resource gate. |
| Genuine live cross-venue science | BLOCKED | Source-use/location authorization remains unresolved; fixture results are not live claims. |
| Frontier overall | PARTIALLY VERIFIED | Live evidence, broad regressions, endurance, protected recovery, and deployment remain open. |

## Bounded public-trade collection — 2026-10-28 21:13 UTC

The trade collection implementation, API, UI, and fixture tests are committed
as `4d38b69` on `codex/frontier-20261026`. Collector version
`frontier-finite-collection-4` adds a restart-safe optional stage after market
and book collection. Each finite run can select zero to two discovered markets
and request one source page of up to ten prints per selected market. The run
pins these limits and records dedicated trade tasks, batch observation IDs,
print count, and per-task failures. Empty successful responses persist as
empty `TradeBatch` records, so zero prints are distinguished from a failed or
missing observation. Unsupported public-trade capability is rejected before
discovery; the default trade-market limit is zero.

For nonempty batches, each trade must match the requested venue and native
market and bind to the exact response capture by raw SHA-256, source URL,
adapter version, request start, response receipt, and monotonic request
duration. The raw response is retained with a normalized batch. Failure
diagnostics retain the captured response and mark the trade task failed. The
append-only checkpoint stores separate in-progress, completed, and failed
trade states, and resume skips completed work. The API includes opted-in trade
calls in its request upper bound; Mission Control exposes a per-venue checkbox
that is off by default and displays trade prints and failed batches.

Verification on this checkpoint:

- Backend collector and finite API modules: **51/51 passed** in 14.51 seconds,
  1 GiB memory cap, zero swap, 50% CPU. The only warning is the existing
  Starlette/httpx TestClient deprecation.
- After the final input-normalization guard, four focused trade cases pass:
  stored and resumable batches, exact provenance rejection, and empty successful
  batches. Strict mypy passes for `collection.py`.
- Frontier UI test file: **9/9 passed**. TypeScript project check, ESLint, and
  Prettier pass.
- Production frontend build: **2,230 modules transformed**. Frontier outputs
  184.05 kB JS and 54.22 kB CSS. The existing Chart chunk is 544.51 kB and
  continues to trigger Vite's over-500-kB advisory.
- A whole-web Vitest invocation accidentally ran under a 50% CPU quota and
  ended **43 passed, 4 timed out of 47**. All four failures were 5-second test
  timeouts; the dedicated Frontier file passed without the CPU cap. This is
  recorded as an unsuccessful broad-suite attempt, not a pass.
- Strict mypy on `apps/api/frontier.py` still reports the same 15 unrelated
  `no-any-return` sites; the changed request and resume branches produced no
  diagnostic. No exchange endpoint was queried.

At `2026-10-28T21:13:16Z`, Reality was active and **65,536 bytes below** its
1,207,959,552-byte `MemoryHigh`; API was active and **3,088,288 bytes below**
its 1,610,612,736-byte boundary. Memory PSI avg10 was 0%; avg300 `some` was
0.98% and `full` 0.71%. Host available memory was 10.04 GB and swap free was
50.25 MB. No protected service was modified. Broad Frontier/MIDAS regression
remains deferred under this resource sample.

| Requirement | Status | Evidence and boundary |
| --- | --- | --- |
| Durable public-trade collection | COMPLETE AND VERIFIED WITH FIXTURES | Bounded opt-in tasks, exact capture provenance, checkpoint/resume, empty results, and per-task failures pass fixture tests. |
| API capability and request bounds | COMPLETE AND VERIFIED | Unsupported capability is rejected before collection; extra requests are included in the retry-aware upper bound. |
| Mission Control trade option | COMPLETE AND VERIFIED WITHIN TESTED SCOPE | The explicit disabled-by-default checkbox, results, typecheck, lint, focused test, and production build pass. |
| Full frontend suite | PARTIALLY VERIFIED | The throttled run had four 5-second timeout failures; the exact Frontier test passes 9/9. |
| Current broad Frontier and MIDAS regressions | PARTIALLY VERIFIED | Not run under the protected-service memory boundary. |
| Live multi-venue trade research | BLOCKED | Source-use and location authorization remain unresolved; this work has no live collection evidence. |
| Production deployment | DEFERRED | No deployment or protected service transition occurred. |
| Project Frontier overall | PARTIALLY VERIFIED | Live scientific evidence, broad regressions, endurance, recovery, and deployment prerequisites remain open. |

## Source-aware public-trade coverage — 2026-10-28 21:22 UTC

Coverage analytics now includes response schema version 2 and reads at most 50
newest stored `public_trades` observations across eligible venues. The storage
reader hash-checks each row; the API then validates `TradeBatch`, checks its
venue, and binds each print's raw-body digest and receipt timestamp to the
captured observation. Invalid normalized batches and lineage mismatches are
counted separately from valid captures. The summary reports capture and
returned-print counts, valid empty responses, distinct requested/trade market
and instrument counts, source-timestamp coverage, capture age, and future
exchange timestamps. It does not deduplicate prints across overlapping pages.
Collection failures remain in the separate verified collection checkpoints.

Mission Control adds a **Public trade capture coverage** card with an explicit
empty state and the sample interpretation limits. Held venues are omitted by
the same SQL exclusion used for the other coverage inputs. This read performs no
source requests and does not infer venue-wide volume, a complete trade history,
or zero activity from an empty response.

Verification on implementation commit `e371861`:

- Analytics and three coverage API cases: **13/13 passed** in 4.69 seconds,
  under a transient 1 GiB memory and 50% CPU cap. One existing
  Starlette/httpx TestClient deprecation warning remains.
- Strict mypy passes for `packages/midas/frontier/analytics.py`; Ruff check and
  format pass. Strict mypy on `apps/api/frontier.py` reports the same 15
  existing `no-any-return` diagnostics recorded at the prior checkpoint.
- Mission Control typecheck passes. `Frontier.test.tsx` passes **9/9** in 21.11
  seconds under a 2 GiB memory and 50% CPU cap; ESLint and Prettier pass.
- Production build passes after transforming **2,230 modules**. Frontier emits
  185.97 kB JS and 54.22 kB CSS. The existing 544.51 kB Chart chunk still
  triggers Vite's over-500-kB advisory.
- Tests used temporary fixture stores; no exchange market-data endpoint was
  queried. No source terms or location holds were changed.

At `2026-10-28T21:24:10Z`, both protected services were active. Reality used
1,117,011,968 of 1,207,959,552 bytes at `MemoryHigh` (90,947,584 bytes below);
API used 1,609,633,792 of 1,610,612,736 bytes (978,944 bytes below). Memory
PSI avg10 was 0%; avg300 was 0.07% `some` and 0.04% `full`. Host available
memory was 10.01 GB and swap free was 51.82 MB. No service configuration or
process was changed. Broad Frontier/MIDAS regression remains deferred at the
near-boundary API limit.

| Requirement | Status | Evidence and boundary |
| --- | --- | --- |
| Stored public-trade coverage | COMPLETE AND VERIFIED WITH FIXTURES | Bounded hash-checked capture summaries distinguish prints, empty responses, invalid normalization, timestamps, and venue. |
| Held-source filtering | COMPLETE AND VERIFIED WITH FIXTURES | API fixture confirms held Kalshi trade records are omitted. |
| Coverage & quality UI | COMPLETE AND VERIFIED WITHIN TESTED SCOPE | 9/9 Frontier UI cases, typecheck, lint, format, and production build pass. |
| Live public-trade coverage | BLOCKED | Source-use and physical-location authorization remain unresolved. |
| Full exact-tree regression and endurance | PARTIALLY VERIFIED | Not run under the protected API's approximately 1 MiB `MemoryHigh` margin. |
| Project Frontier overall | PARTIALLY VERIFIED | Live cross-venue science, broad regression, endurance, protected recovery, and deployment remain open. |

## Four-adapter trade fixtures and timestamp quality — 2026-10-28 21:36 UTC

Commits `91c127f`, `df5ea00`, `6a3687b`, and `d19bef3` complete a bounded
fixture contract for Polymarket, Kalshi, Kraken spot, and Coinbase spot public
trades. The shared test preserves native market and instrument identifiers,
raw-response hashes, request and receipt timing, monotonic duration, adapter
version, and source timestamp semantics. It checks each adapter's declared
`PAGINATED_PUBLIC_TRADES` capability and whether it exposes event outcome
definitions. Equal fixture prices and quantities are not treated as evidence of
equivalent exposures.

Fixture responses use injected `httpx.MockTransport` and are persisted and
re-read through a temporary `FrontierStore`, including stored observation IDs
and nested trade hashes. The test verifies that no Authorization header is
sent. Coinbase remains under its source-use hold; the fixture-only override
asserts that the hold is still configured. No exchange endpoint was queried,
and this is not live adapter validation or evidence of source permission.

Coverage response schema version 3 reports source timestamp presence, clock
uncertainty availability, receipt age, receipt timestamps after the summary
cutoff, and exchange timestamps later than response receipt. It continues to
read only the newest bounded stored sample and does not infer trade volume,
complete history, synchronized executable quotes, or zero activity from empty
responses.

Verification on `d19bef3`:

- Ruff and strict mypy pass for `tests/frontier/test_trade_adapter_contract.py`.
- After adding timestamp-semantics and pagination-capability assertions, the
  four-adapter contract test passes **1/1** in 0.95 seconds. It ran with a 1 GiB
  address-space limit, a 60-second CPU-time limit, and reduced process priority.
- The preceding bounded analytics/API/adapter slice passed **14/14**; the
  updated adapter contract was then rerun independently as above. One existing
  Starlette/httpx TestClient deprecation warning was present in the slice.
- The Frontier UI test file passed **9/9**, and the frontend typecheck passed
  after schema version 3 was reflected in the client type. ESLint and Prettier
  passed after the UI timing columns were added. The production frontend build
  passed after those UI changes; its later schema-version-only type update does
  not change emitted application code. The known 544.51 kB Chart chunk advisory
  remains.
- `git diff --check` passes. No broad Python, web, browser, or legacy regression
  suite was run at this checkpoint.

At `2026-10-28T21:36:16Z`, Reality and API were active. Reality used
1,207,574,528 / 1,207,959,552 bytes at `MemoryHigh` (385,024 bytes below); API
used 1,607,020,544 / 1,610,612,736 bytes (3,592,192 bytes below). Memory PSI
avg10/avg60/avg300 remained 0%. Host `MemAvailable` was 9,742,044 kB and
`SwapFree` was 50,884 kB. No protected process or configuration was changed.
The small fixture test does not justify broader suite admission at these
service margins.

| Requirement | Status | Evidence and boundary |
| --- | --- | --- |
| Four-adapter trade normalization contract | COMPLETE AND VERIFIED WITH FIXTURES | Native IDs, source timestamp semantics, pagination capability, raw response lineage, and outcome-definition capabilities are asserted for four adapter fixtures. |
| Fixture persistence and source-hold guard | COMPLETE AND VERIFIED WITH FIXTURES | Trade captures round-trip through a temporary store; Coinbase's configured hold remains asserted. |
| Stored trade timing-quality summary | COMPLETE AND VERIFIED WITH FIXTURES | Schema-v3 bounded read exposes timestamp and clock-uncertainty quality fields without source requests. |
| Live multi-venue trade validation | BLOCKED | Source-use and location authorization remain unresolved; no live observation is claimed. |
| Broad regression and resource endurance | PARTIALLY VERIFIED | Deferred under current protected-service `MemoryHigh` margins. |
| Production deployment | DEFERRED | No deployment or protected service transition occurred. |
| Project Frontier overall | PARTIALLY VERIFIED | Live scientific findings, broad regressions, endurance, protected recovery, and deployment prerequisites remain open. |

Next safe action: continue isolated fixture review of each adapter's
pagination and reconnect boundaries, then re-measure protected-service headroom
before any larger regression. Keep live collection disabled while the source
and location holds remain.

## Trade pagination and checkpoint replay review — 2026-10-28 21:39 UTC

Review of the existing trade-page paths found explicit source cursor handling
for Polymarket and Kalshi. API cursors bind the opaque venue cursor to the
recorded market and page size. The bounded API fixtures exercise a two-page
request, persisted page evidence, cursor replay, and rejection of page-size
changes. Adapter fixtures reject inconsistent or non-advancing cursors. The
adapter implementations had an over-limit response guard, but no direct trade
page test for that guard existed at this checkpoint. The collector checkpoint
fixture verifies resume without repeating market discovery. This REST design
is page-oriented; it is not a continuous streaming or full-history claim.

The focused regression passes **8/8** in 3.68 seconds under a 1 GiB
address-space limit, 60-second CPU-time limit, and reduced priority. It includes
Polymarket and Kalshi API page/replay cases, adapter cursor rejection cases, and
collector resume. One existing Starlette/httpx TestClient deprecation warning
was emitted. All source responses were provided by fixtures; no venue request
was made. No duplicate pagination test or adapter code change was warranted.

At `2026-10-28T21:39:17Z`, both services were active. Reality used
1,154,699,264 / 1,207,959,552 bytes at `MemoryHigh` (53,260,288 bytes below);
API used 1,606,209,536 / 1,610,612,736 bytes (4,403,200 bytes below). Memory
PSI avg10/avg60/avg300 was 0%. `MemAvailable` was 9,721,020 kB and `SwapFree`
was 51,132 kB. No protected process or configuration was changed.

| Requirement | Status | Evidence and boundary |
| --- | --- | --- |
| Polymarket/Kalshi public trade pagination | PARTIALLY VERIFIED | Opaque source cursor, market binding, fixed page size, and persisted replay are covered; the direct over-limit response assertion is added in the later 21:43 checkpoint. |
| Collector checkpoint resume | COMPLETE AND VERIFIED WITH FIXTURES | Resume avoids repeating market discovery and preserves completed work. |
| Continuous feed reconnect behavior | DEFERRED | These integrations expose bounded REST pages; no streaming/reconnect claim is made. |
| Project Frontier overall | PARTIALLY VERIFIED | Live data, broad regressions, endurance, recovery, and deployment remain open. |

Next safe action: audit source fee evidence applicability and independent
rounding assumptions with bounded fixtures.

## Fee evidence applicability audit — 2026-10-28 21:39 UTC

The read-only audit found that the adapter layer preserves venue fee evidence
without promoting missing account details to zero. Polymarket exposes a verified
schedule only for supported, unexpired source formulas and retains a digest of
the native schedule evidence; unsupported exponents and expired schedules stay
unknown. Kalshi's bounded event/series metadata lookup validates both native
identities and distinguishes complete event overrides, series inheritance,
partial overrides, and unreported overrides. That public metadata remains
`economics_state=unresolved`; it is not an account fee quote. Kraken and
Coinbase spot metadata continue to leave account-tier fee schedules unknown.

No code change was justified by this audit. The focused fixture suite passes
**8/8** in 1.78 seconds under a 1 GiB address-space limit, 60-second CPU-time
limit, and reduced process priority. It covers unsupported Polymarket fee
exponents; Kalshi event overrides and inherited series parameters; incomplete
override states; wrong event/series identities; and rejection of an unsafe
series ticker before the second request. All responses are injected fixtures;
no venue endpoint was queried and no fee schedule was changed.

At `2026-10-28T21:40:01Z`, the user-manager services were active. Reality used
1,207,705,600 / 1,207,959,552 bytes at `MemoryHigh` (253,952 bytes below);
API used 1,606,520,832 / 1,610,612,736 bytes (4,091,904 bytes below). Memory
PSI avg10/avg60/avg300 was 0%. Host `MemAvailable` was 9,726,956 kB and
`SwapFree` was 51,144 kB. No protected service was modified. Broader tests stay
deferred at this sample.

| Requirement | Status | Evidence and boundary |
| --- | --- | --- |
| Polymarket source fee parsing | COMPLETE AND VERIFIED WITH FIXTURES | Unsupported formula versions and expired evidence remain unknown; supported schedules carry source and hash provenance. |
| Kalshi public fee metadata | COMPLETE AND VERIFIED WITH FIXTURES | Event/series identity and override states are checked; metadata stays non-economic until account applicability is established. |
| Kraken/Coinbase spot fee applicability | PARTIALLY VERIFIED | Models explicitly preserve unknown account-tier schedules; no user account or live fee endpoint is involved. |
| Cross-venue account fee eligibility | PARTIALLY VERIFIED | Existing candidate economics fail closed when decisive fee evidence is absent; account-specific applicability remains unresolved. |
| Project Frontier overall | PARTIALLY VERIFIED | Live multi-venue evidence, broad regression, resource endurance, protected recovery, and deployment remain open. |

Next safe action: review the existing independent economic fee differential
cases and their rounding/currency assumptions, using focused fixtures only;
take a fresh protected-resource sample before running them.

## Independent fee differential checks — 2026-10-28 21:40 UTC

After a fresh resource sample, three focused economic tests pass **3/3** in
0.34 seconds under a 1 GiB address-space limit, 60-second CPU-time limit, and
reduced process priority. They cover a source-backed Kalshi one-fill fee
estimate through candidate generation and independent audit, binary candidate
classification when one fee is unknown, and logical-implication economics that
must leave the net result unresolved rather than treating unknown fees as zero.
All evidence is fixture-based; no fee endpoint or account was accessed. The
broader economics and Frontier suites were not run.

At `2026-10-28T21:40:36Z`, both protected services were active. Reality used
1,110,278,144 / 1,207,959,552 bytes at `MemoryHigh` (97,681,408 bytes below);
API used 1,606,807,552 / 1,610,612,736 bytes (3,805,184 bytes below). Memory
PSI avg10/avg60/avg300 was 0%. Host `MemAvailable` was 9,532,680 kB and
`SwapFree` was 51,148 kB. No service was modified. Broad regression remains
deferred at the protected API limit.

| Requirement | Status | Evidence and boundary |
| --- | --- | --- |
| Source-backed fee candidate calculation | COMPLETE AND VERIFIED WITH FIXTURES | Kalshi fee estimate is reproduced through candidate generation and independent audit; account precision and other costs remain limitations. |
| Unknown-fee handling | COMPLETE AND VERIFIED WITH FIXTURES | Positive gross constructions remain conditional with no net result when a decisive fee is unknown. |
| Broad economic regression | PARTIALLY VERIFIED | Three targeted tests pass; the wider economics and Frontier suites remain deferred. |
| Project Frontier overall | PARTIALLY VERIFIED | No live market evidence, broad acceptance run, endurance, protected recovery, or deployment is claimed. |

Next safe action: continue fixture-level adapter and verifier review only. Do
not start a broad suite while protected-service headroom remains near `MemoryHigh`.

## Trade page-size guard fixtures — 2026-10-28 21:43 UTC

Test commit `3f07f81` adds `tests/frontier/test_trade_page_bounds.py` with
direct oversized-response checks for Polymarket v2 and Kalshi public trade
pages. Each fixture returns two rows for a requested page size of one. The test
requires rejection while retaining the exact raw response capture and verifies
that the request is a public GET without an Authorization header. No adapter
implementation change was needed.

The new module passes Ruff, format check, and strict mypy. Its two new cases plus
the existing Polymarket and Kalshi invalid/non-advancing cursor cases pass
**7/7** in 0.37 seconds under a 1 GiB address-space limit, 60-second CPU-time
limit, and reduced priority. The first run had one fixture-only failure because
the exact Kalshi path in the helper omitted `/trade-api/v2`; after correcting
that fixture path, the final focused run passed. No venue endpoint was queried.

Strict mypy was also attempted on the established, broadly untyped
`tests/frontier/test_adapters.py` module; it is not a clean strict-typing gate
because that file contains many unannotated test definitions and generic types.
The new isolated bounds module passes strict mypy independently.

At `2026-10-28T21:43:49Z`, Reality and API were active. Reality used
1,156,440,064 / 1,207,959,552 bytes at `MemoryHigh` (51,519,488 bytes below);
API used 1,606,242,304 / 1,610,612,736 bytes (4,370,432 bytes below). Memory
PSI avg10/avg60/avg300 was 0%. Host `MemAvailable` was 9,666,780 kB and
`SwapFree` was 51,200 kB. No service or configuration changed.

| Requirement | Status | Evidence and boundary |
| --- | --- | --- |
| Oversized trade-page response rejection | COMPLETE AND VERIFIED WITH FIXTURES | Polymarket v2 and Kalshi retain raw evidence and reject rows beyond the requested page size. |
| Trade cursor and page replay | COMPLETE AND VERIFIED WITH FIXTURES | Polymarket/Kalshi identity-bound pages, invalid cursor rejection, and collector checkpoint resume pass focused tests. |
| Broad regression | PARTIALLY VERIFIED | Only focused fixture and economic slices ran; broad suites remain deferred. |
| Project Frontier overall | PARTIALLY VERIFIED | Live evidence, full scientific acceptance, endurance, recovery, and deployment remain open. |

Next safe action: continue review of source-independent relationship and
opportunity verification; reserve broad suites for adequate protected-service
headroom or an isolated host.

## Payoff-equivalence fail-closed review — 2026-10-28 21:46 UTC

The existing `verify_same_payoff` path requires distinct venues and supported
event-contract structures, exhaustive verified state sets, a bijective state
and instrument mapping, equal payout vectors, matching settlement asset
identity, and matching resolution fingerprint, authority, close time, and
settlement time. It also binds the assertion to each market's pinned source
observation and rejects an assertion timestamp that predates either source
record. The verifier requires an external assertion; it does not claim that
string similarity or matching titles prove resolution semantics.

Candidate generation independently reruns structural checks. The focused
tests include a forged `VERIFIED` relationship over mismatched settlement
semantics and confirm the candidate remains incomplete. The fail-closed
relationship slice passes **5/5** in 0.33 seconds under a 1 GiB address-space
limit, 60-second CPU-time limit, and reduced process priority. It covers
spot-versus-event rejection, same-ticker assets on different networks, pinned
evidence identity and timing, payout currency/settlement mismatch, and the
candidate guard against a forged relationship. No venue request was made; no
code change was warranted.

At `2026-10-28T21:46:10Z`, both protected services were active. Reality used
1,200,824,320 / 1,207,959,552 bytes at `MemoryHigh` (7,135,232 bytes below);
API used 1,606,815,744 / 1,610,612,736 bytes (3,796,992 bytes below). Memory
PSI avg10/avg60/avg300 was 0%. `MemAvailable` was 9,656,552 kB and `SwapFree`
was 51,228 kB. No protected service was changed. Broad regressions remain
deferred under the API memory boundary.

| Requirement | Status | Evidence and boundary |
| --- | --- | --- |
| Exact payoff-equivalence structure | COMPLETE AND VERIFIED WITH FIXTURES | Mapping bijections, exhaustive payoff vectors, settlement identity, and timing/authority fields are checked. |
| Pinned source evidence and assertion order | COMPLETE AND VERIFIED WITH FIXTURES | Both market observations are required; predating and shared evidence are rejected. |
| Semantic resolution equivalence | PARTIALLY VERIFIED | The system requires an external assertion and matching fingerprint; public text similarity does not certify semantics. |
| Spot and asset-identity safeguards | COMPLETE AND VERIFIED WITH FIXTURES | Spot/event structures and same-ticker cross-network settlement identities do not pass as equivalent. |
| Project Frontier overall | PARTIALLY VERIFIED | Live relationship evidence, broad regression, endurance, recovery, and deployment remain open. |

Next safe action: inspect logical-implication verification and candidate
classification boundaries with focused fixtures; keep broad suites deferred.

## Logical-implication direction and state bounds — 2026-10-28 21:47 UTC

The implication verifier treats direction as material. New tests exercise the
valid source-YES-to-target-YES basket and reject its reverse when one joint
state is a counterexample. They also reject a non-bijective state mapping and a
1,025-state mapping before payout-vector traversal; the configured cap is
1,024 states. The tests use pinned fixture markets and an explicit external
assertion, so they verify bounded arithmetic and mapping behavior rather than
semantic event equivalence.

Test commit `cd8d95c` adds the three new verifier cases. Ruff and format checks
pass for the changed test module. The three new verifier cases plus the
existing directed basket and independent audit pass **4/4** in
0.35 seconds under a 1 GiB address-space limit, 60-second CPU-time limit, and
reduced process priority. No source endpoint was queried and no production
logic changed.

At `2026-10-28T21:47:46Z`, Reality and API were active. Reality used
1,207,885,824 / 1,207,959,552 bytes at `MemoryHigh` (73,728 bytes below); API
used 1,607,192,576 / 1,610,612,736 bytes (3,420,160 bytes below). Memory PSI
avg10/avg60/avg300 was 0%. `MemAvailable` was 9,640,972 kB and `SwapFree` was
51,260 kB. No protected service changed. No further tests are justified at
this near-boundary sample.

| Requirement | Status | Evidence and boundary |
| --- | --- | --- |
| Directed implication arithmetic | COMPLETE AND VERIFIED WITH FIXTURES | Forward basket verifies; reverse direction with a counterexample is rejected. |
| State mapping validation | COMPLETE AND VERIFIED WITH FIXTURES | Non-bijective mapping and state count above 1,024 are rejected. |
| Independent implication candidate audit | COMPLETE AND VERIFIED WITH FIXTURES | Existing directed basket audit still verifies and remains conditional economically. |
| Semantic event relationship | PARTIALLY VERIFIED | External assertion and pinned evidence remain required; fixtures do not establish live event equivalence. |
| Project Frontier overall | PARTIALLY VERIFIED | Live research, broad regression, endurance, recovery, and deployment remain open. |

Next safe action: continue read-only review of candidate classification and
adversarial relationship evidence. Defer further tests until a fresh sample
shows materially more protected-service headroom.

## Candidate-side implication edge revalidation — 2026-10-28 21:49 UTC

Test commit `a737e11` adds a forged-edge case for the candidate generator. The
fixture starts with a valid directed relationship, changes its stored direction
to the reverse while retaining the `VERIFIED` state, then confirms candidate
generation reevaluates the payout implication and classifies the edge as
`INVALID_RELATIONSHIP`. This verifies that a persisted verification label alone
cannot authorize a basket. Ruff and format checks pass; the focused case passes
**1/1** in 0.33 seconds under a 1 GiB address-space limit, 60-second CPU-time
limit, and reduced priority. No source endpoint was queried; no production
logic changed.

At `2026-10-28T21:49:16Z`, Reality and API were active. Reality used
1,158,930,432 / 1,207,959,552 bytes at `MemoryHigh` (49,029,120 bytes below);
API used 1,607,307,264 / 1,610,612,736 bytes (3,305,472 bytes below). Memory
PSI avg10/avg60/avg300 was 0%. `MemAvailable` was 9,658,460 kB and `SwapFree`
was 51,276 kB. No protected service changed.

| Requirement | Status | Evidence and boundary |
| --- | --- | --- |
| Candidate-side implication revalidation | COMPLETE AND VERIFIED WITH FIXTURES | A forged reverse edge is rejected despite retaining `VERIFIED` state. |
| Independent candidate audit | COMPLETE AND VERIFIED WITH FIXTURES | The existing directed basket's independent verifier remains covered. |
| Live logical relationship evidence | BLOCKED | Fixture assertions do not establish semantic event equivalence at live venues. |
| Project Frontier overall | PARTIALLY VERIFIED | Live evidence, broad regression, endurance, recovery, and deployment remain open. |

Next safe action: continue static review of cross-venue candidate
classification and evidence reuse; only run another bounded fixture after a
fresh protected-resource sample.
