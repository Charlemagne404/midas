# Project Frontier Engineering Report

**Report date:** 2026-10-28

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

## Current mission acceptance matrix — 2026-10-28 02:16 UTC

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
| Laboratory/Arena research integration | PARTIALLY VERIFIED | Bounded replay jobs, paired comparisons, integrity-checked results, and fixture/UI paths exist. No durable Laboratory experiment manager, long-duration campaign, or production worker is authorized or verified. |
| Native Frontier Mission Control interface | IMPLEMENTED, DEPLOYMENT PENDING | The current web unit suite passes 40/40, Frontier browser spec 5/5, TypeScript, and Vite production build after the joint-state editor change. A new fixture-only browser case submits every mapping cell, verifies the server-derived ID response and conditional status, and confirms no venue probe. Browser checks use isolated demo services and temporary roots. The build transformed 2,228 modules at 713,040 KiB peak RSS and retains the existing 544.41 kB chart-chunk advisory. No live source data was used; no production deployment occurred. |
| Scientific acceptance: normalization, rejection, controlled discrepancy, independent arithmetic, missing/stale/asynchronous evidence, and deterministic replay | PARTIALLY VERIFIED | The full Frontier regression passes 343 tests in 53.88 seconds (55.23 seconds process wall) at 366,360 KiB peak RSS, with zero swaps. It includes 48 seeded differential cases comparing joint-state generation with an independent exhaustive oracle, plus API persistence, separate arithmetic auditing, native-unit preservation, and adversarial rejection. The web suite passes 40/40, Frontier browser spec 5/5, and current production build. Evidence does not establish a genuine cross-venue relationship, authenticated state composition, synchronized executable quotes, or positive economics. |
| Resource sustainability under bounded development workloads | PARTIALLY VERIFIED | The current Frontier Python suite reached 366,360 KiB peak RSS; the Vite build transformed 2,228 modules at 713,040 KiB peak RSS; the Frontier Playwright spec used 197,060 KiB peak RSS. None swapped. The synthetic 12-instrument/64-state search evaluated 4,095 subsets and 3,969 qualifying baskets: three one-candidate runs measured 0.101767 seconds median / 0.104521 seconds maximum at 70,576 KiB peak RSS; one eight-candidate run took 0.174308 seconds at 71,460 KiB. Representative public workloads, sustained collection, concurrency, production admission, and broad latency/CPU behavior remain unmeasured. |
| Read-only research boundary and source-use gates | COMPLETE AND VERIFIED | No trading/authenticated exchange path is provided; source-policy tests ensure held venues return 409 without requests and held evidence stays quarantined. This does not grant permission to use a held source. |
| Required architecture, operations, current-state, report, and continuation documentation | COMPLETE AND VERIFIED | The engineering report, architecture, operations guidance, current-state note, and append-only mission ledger record implementation, evidence, blockers, and continuation actions. |
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
