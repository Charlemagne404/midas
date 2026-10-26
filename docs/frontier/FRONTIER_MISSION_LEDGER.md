# Project Frontier Mission Ledger

**Current stage:** isolated engine/API/UI, immutable relationship review, schema-v5
indexed bounded graph neighborhoods with UI scan-quality status, hash-verified
public book/trade capture, exact fixture-verified multi-outcome coverage, and a
separate candidate arithmetic audit; plus captured-response failure diagnostics
and degraded-source recovery. The supported Polymarket fee shape now has
nonzero-fixture and live zero-fee evidence coverage; timeout and truncated-stream
failure tests pass. Centered one-hop graph neighborhoods now support append-only
revision-bound keyset pagination with stale-cursor rejection. Polymarket v2
cursor trade pages now preserve token/outcome identifiers, have a bounded
operator-triggered API/UI continuation flow, and one live first page has been
hash-verified through an isolated temporary store. One live continuation page
also passed through the isolated API route, adding ten disjoint trades with
hash-verified temporary-store read-back. A further page was available but not
requested.
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

## Public source investigation

Official API documentation reviewed:

- [Kalshi public market-data quick start](https://docs.kalshi.com/getting_started/quick_start_market_data)
- [Kalshi Get Markets](https://docs.kalshi.com/api-reference/market/get-markets)
- [Kalshi Get Market Orderbook](https://docs.kalshi.com/api-reference/market/get-market-orderbook)
- [Kalshi fee information](https://help.kalshi.com/en/articles/13823805-fees)
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
- A direct Polymarket Data API v2 first-page capture and one continuation page through the local API each returned 10 rows/HTTP 200 in exactly one request, without retries, and verified raw plus normalized temporary-store read-back. The 20 native trade IDs are disjoint. The second page still advertised a next cursor; no third page was requested.
- Ruff check and format check: passed for the Frontier package and test files.
- Mypy: passed for 16 Frontier/API source files. A broader `mypy packages/midas/frontier apps/api` attempt reported 37 errors in eight unchanged Veritas/Arena/API files; none was in Frontier source.
- Frontend tests: **35 passed across 7 files** after adding incomplete-scan messaging coverage; typecheck, lint and Prettier check passed.
- Frontend production build: passed. Existing main and Chart chunks trigger Vite’s >500 kB warning. Frontier’s lazy chunks are 49.11 kB JS and 24.74 kB CSS.
- Frontier browser cases: **2 passed** in 6.5 seconds, including centered graph pagination, fixture-only review submission, multi-outcome candidate state, and audit details at desktop/mobile sizes using one worker and isolated roots; source probes remained disabled. In the broader 10-case E2E run, 8 passed and 2 existing Laboratory cases were denied at the shared Arena resource-admission lock (`resource_admission_lock_busy`); no experiments started and the lock was not bypassed.
- The complete Python repository suite was not run. No continuous worker, campaign, or service was started.

Reproduction commands and environment boundaries are in
[`docs/DEVELOPMENT.md`](../DEVELOPMENT.md) and
[`FRONTIER_ARCHITECTURE.md`](FRONTIER_ARCHITECTURE.md).

## Completion matrix

| Component | Status | Current evidence / remaining requirement |
| --- | --- | --- |
| Verified isolated baseline and worktree | COMPLETE AND VERIFIED | Separate branch from `11d32a0`; unrelated dirty trees preserved. |
| Adapter protocol, capability inventory, bounded GET transport | COMPLETE AND VERIFIED | Contract tests; all capabilities explicitly declared; no startup request. |
| Polymarket, Kalshi and Kraken Spot implementations | PARTIALLY VERIFIED | Fixture tests and one bounded live listing/book/trade-to-store round trip per venue pass. One direct Polymarket v2 first page and one API-route continuation returned ten rows each and were hash-verified through isolated stores, with distinct trade IDs. Polymarket fee parsing accepts only the supported taker exponent-1 schedule; one genuine Gamma listing recorded a five-minute verified zero-fee sample. Kalshi series and Kraken account fee applicability remain unknown; live degraded-source behavior remains unverified. |
| Canonical normalization and native evidence | PARTIALLY VERIFIED | Distinct event, conditional event and spot forms; v2 Polymarket trades preserve token and outcome identity, while earlier v1 batches still load with those new fields unknown. Other settlement/payoff semantics remain intentionally unverified. |
| Relationship matching, immutable review, indexed neighborhoods, and strict payoff verifier | PARTIALLY VERIFIED | Self-attributed review API/UI with stored source refs, append-only revisions, compare-and-set, latest-state replay, query-plan/migration tests, and 1–3 hop left/right indexed scans capped at 500 rows. Centered one-hop keyset pages bind listing/instrument-metadata observation, relationship, and review counts; changed inputs reject stale cursors. A 501-edge fixture verifies the scan cap. No authenticated reviewer/assertion, genuine equivalent pair, or multi-hop pagination. |
| Economic candidate verifier and independent audit | PARTIALLY VERIFIED | Exact two-venue binary all-long coverage and same-market 3–16-state exhaustive one-hot coverage. A separate Decimal implementation recomputes supported candidate arithmetic from hash-pinned normalized inputs; controlled fixtures only, no genuine eligible event, independently authenticated market truth, or practical execution proof. |
| Bounded store and deterministic replay | COMPLETE AND VERIFIED | Schema v5, additive v2/v3/v4 migration with preserved relationship payloads, append-only review/revision history, content integrity checks, persisted replay-v3 audit results, and tests that later review revokes earlier verified replay input. |
| Frontier API and source configuration | COMPLETE AND VERIFIED | Local reads include hash-verified v1/v2 trades and page metadata. A v2 POST is capability/config/recorded-market gated, bounded to one cursor page and retries, and rejects condition/page-size cursor mismatch. Two-page API persistence/read-back and no-egress mismatch rejection pass fixtures; one live continuation page also passed through the API route. |
| Live adapter-to-API listing, book, and trade persistence | PARTIALLY VERIFIED | Three genuine listings, books, and legacy trade responses are hash-preserved; one direct v2 first page and one API-route continuation page were hash-read from isolated temporary stores with distinct trade IDs. The samples are sequential and no third page or time-series collection was attempted. Kalshi book/trade arrays were empty. |
| Mission Control Frontier workspace | IMPLEMENTED, LIVE VALIDATION PENDING | Native view now gates manual first/next Data API v2 pages on the source flag and capability, shows raw/normalized evidence hashes, and retains token/outcome identity. Unit and desktop/mobile E2E cover fixture pages; the workspace is not deployed. |
| Laboratory/Arena research orchestration | DEFERRED | Navigation links only; no Frontier experiment job type/scheduler. |
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

1. Expand API-boundary degraded-source and recovery validation if a distinct
   useful failure condition can be established safely. The direct adapter first
   page and one live API-route continuation are captured; do not request more
   pages merely to increase counts. Live degraded-source recovery remains
   unverified. Mock tests cover bounded timeout retries, oversized-response
   rejection, truncated-stream evidence rejection, and retry-after/HTTP failure
   capture; no live source is intentionally degraded.
2. Extend revision-bound pagination to multi-hop traversal only if a bounded
   cursor can preserve breadth-first semantics; full-universe search and
   clustering need representative data and a resource measurement first.
3. Resolve Kalshi market/series fee applicability against its effective
   schedule. Keep Kraken account fee tier unknown without authenticated account
   data, and keep fee expiry enforced before any decisive net classification.
4. Seek genuine public multi-outcome metadata that satisfies the strict verified
   payoff and resolution requirements; do not relax the evaluator to fit current
   captures.
5. Extend audit mutation/differential fixtures for distinct failure modes, and
   design authenticated review and independent assertion ingestion only after a
   separately reviewed security boundary exists.
6. Integrate only short, resource-admitted deterministic replay jobs with
   Laboratory/Arena; do not start an unattended campaign.

Do not connect Frontier to Reality’s recorder, enable probes as a default,
deploy, or alter protected evidence as part of ordinary continuation. The next
safe work is genuine public multi-outcome term investigation, Kalshi series fee
resolution, stronger API-boundary degraded-source tests, and short
resource-admitted Arena/Laboratory replay integration.

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
`e661e06e22b2d29bd68e13dd6e6b423c698fec27`. This ledger amendment is the
current branch checkpoint; no deployment or production change was made.
