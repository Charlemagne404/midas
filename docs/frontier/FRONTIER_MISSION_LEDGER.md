# Project Frontier Mission Ledger

**Latest checkpoint (2026-10-27 17:58 UTC):** Code commit `047298b` adds
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
| Adapter protocol, capability inventory, bounded GET transport | COMPLETE AND VERIFIED | Contract tests; all capabilities explicitly declared; Polymarket/Kalshi event groups supported, Kalshi MVE discovery explicitly supported, and Kraken MVE discovery explicitly unsupported; no startup request. |
| Kalshi MVE settlement metadata and arithmetic audit | PARTIALLY VERIFIED | Adapter v12 introduced bounded component YES settlement values and optional parent settlement/provisional fields; current Kalshi adapter v16 retains the behavior. A saved-evidence-only API/UI audit recomputes the selected component product for up to 64 legs and compares it with the parent value only for complete, final evidence; official rule/schema links and observation/raw hashes are shown. The full 148-test suite predates only the output source-link tuple; the final focused 17 tests and four browser cases include it. All positive and negative settlement arithmetic remains fixture-only; the preserved live child lacks values, no live audit result exists, and this method does not verify outcomes/rules or alter candidate economics. |
| Polymarket, Kalshi and Kraken Spot implementations | PARTIALLY VERIFIED | Fixture tests and bounded live listing/book/trade-to-store evidence exist. Current adapter versions are Polymarket v6, Kalshi v16, and Kraken Spot v3. Polymarket v2 first and continuation pages returned ten rows each. Kalshi cursor pages are implemented and row mapping is fixture-tested; a live page returned zero trades and no cursor, so live row normalization remains pending. Two genuine public event-group responses are hash-pinned and replayed through Polymarket/Kalshi adapters. Kalshi MVE listing responses omitted nested members; v10 captured a saved-parent-selected child and preserved its rules. The sole captured child is closed and includes fair-price fallback language, so child and combo payoffs remain unverified. Account fees and Kraken account fee applicability remain unknown. API fixtures cover source degradation and recovery; live degraded-source behavior remains unverified. |
| Canonical normalization and native evidence | PARTIALLY VERIFIED | Distinct event, conditional event and spot forms; FrontierMarket v3, BookSnapshot v2 and TradeObservation v3 preserve canonical denomination identities where supported; Kalshi paginated batches retain schema v2 with nested trade schema v3. Quote, fee, trade, capital, and display codes are separate fields. Legacy v1/v2 rows without identity still load but remain unknown and economically incomplete. V2 Polymarket trades preserve token and outcome identity. October 27 event-group capture preserves parent-event title and child outcome text. Kalshi `MarketBatch` v2 stores typed MVE groups with `included`, `empty`, or `omitted` member state; detail responses with a documented top-level empty list replay to zero child markets. Other settlement/payoff semantics remain intentionally unverified. |
| Relationship matching, immutable review, indexed neighborhoods, and strict payoff verifier | PARTIALLY VERIFIED | Self-attributed review API/UI with stored source refs, append-only revisions, compare-and-set, latest-state replay, query-plan/migration tests, and 1–3 hop left/right indexed scans capped at 500 rows. Centered one-hop keyset and two-/three-hop breadth-first pages bind graph inputs and reject stale cursors; deterministic recomputation and 201-market frontier chunking are tested. Matcher v5 emits exact-ID MVE `source_component_reference` hypotheses only with a matching saved child ticker/event and preserves both observation IDs; the recorded parent/child pair replays offline through the current adapter and matcher. Matcher v4 year-conflict checks remain. The genuine House-control pair is text-only and strict payoff verification rejects same-payoff equivalence. Per-market payout currency must match its settlement asset, and the market-level settlement asset must match the payoff record; the USD/USDC regression passes. A focused depth-two browser test now passes; authenticated review and revision-history drill-down remain pending. |
| Economic candidate verifier and independent audit | PARTIALLY VERIFIED | Exact two-venue binary all-long coverage and same-market 3–16-state exhaustive one-hot coverage. Economic model v8 derives the exact adverse full-or-no-fill terminal pattern for up to 16 legs; independent audit v5 rederives payoff/cost, pinned-book timing and source-quality claims, and the Kalshi one-fill estimate independently. Fixture cases verify the `$0.01` scenario, 24-hour freshness, no-look-ahead, conditional classification, and replay fee-evidence IDs. Three-leg brute-force and maximum 16-outcome replay/audit fixtures agree over a 65,536-pattern bound. Unknown fees suppress net stress; mismatches and unsupported fees fail closed. Current adapter clock-uncertainty estimates are absent, no genuine eligible event is established, and there is no independently authenticated market truth or practical execution proof. |
| Kalshi candidate-fee estimate | PARTIALLY VERIFIED | Commit `3e85c8d` joins only complete raw/hash/path/identity-checked event/series metadata and requires metadata no later than quote time and at most 24 hours old at quote/replay. A supported one-fill formula uses conservative non-direct `$0.01` debit alignment; estimates cannot yield a verified mathematical inconsistency. Independent arithmetic and manifest fee-observation IDs pass fixture/API/replay checks. Account applicability, balance class, maker/mixed/multi-fill and FCM charges, later changes, live validation and source permission remain unresolved. |
| Bounded store and deterministic replay | COMPLETE AND VERIFIED | Storage schema v6 with additive v2/v3/v4/v5 migrations, immutable replay/comparison records, replay-v8 source lineage, denomination identities, and separate fee metadata observation IDs through manifests/candidate legs/Arena snapshots; direct replay retains adapter IDs. Test commit `f35677d` verifies a saved schema-v1 manifest lacking the new field remains readable and its JSON/hash is preserved. The 19-test storage/replay-comparison selection passed before that follow-up, and the changed legacy case passed separately. Replay-v5 output includes fill sensitivity and identity includes effective mappings/proposal limit; prior replay results and observations remain unchanged. |
| Paired scenario comparison | PARTIALLY VERIFIED | Direct local comparison and API/UI/browser tests pass. Two actual systemd-supervised fixture replays completed over the same pinned inputs and their result hashes verify. The latest run measured worker process CPU/RSS and exposes it in Mission Control. No genuine equivalent live market pair exists. |
| Frontier API and source configuration | COMPLETE AND VERIFIED | Local reads include hash-verified legacy and cursor-page batches. Polymarket and Kalshi page routes are capability/config/recorded-market gated, bounded to one page and retries, and bind cursors to market and size. Kalshi MVE discovery validates exactly one series/collection/event-ticker filter and does not follow its cursor. Component-detail fetches are bound pre-request to saved selected-leg metadata and post-response to saved market/event identity. Saved Kalshi fee metadata is joined to replay markets only after raw/hash/path/identity checks and remains excluded for held sources. Four focused API regressions verify raw market/book/trade capture retention after post-drain lineage failures, preserve a drained Polymarket v2 page, and ensure earlier successful listings are not duplicated. The Frontier readiness source-quality gate summarizes candidate timing audits from its latest three non-held replays; it does not change the review-required state or imply execution. |
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
3. Reconcile Kalshi's captured event/series parameters with the effective
   published maker/taker schedule and account rounding model. The July 7, 2026
   schedule lists `KXMVE` maker/taker multipliers 2/1, while the captured
   `KXMVECROSSCATEGORY` event/series endpoint reports
   `quadratic_with_combo_maker_fees` with multiplier 1. These identifiers are
   not treated as equivalent; exact maker-fee applicability remains open. Keep
   Kraken account fee tier unknown without authenticated account data, and keep
   fee expiry enforced before any decisive net classification.
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
