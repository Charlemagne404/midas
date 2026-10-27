# Project Frontier Engineering Report

**Report date:** 2026-10-27

**Branch:** `codex/frontier-20261026`

**Worktree:** `/home/charlie/midas-frontier`

**Baseline:** `11d32a0693b25c290fd273f23e40cf7b5950d95d` (`codex/veritas-v6-integration-20261026`)
**Disposition:** substantial isolated research implementation; **Project Frontier is not complete, deployed, or production-ready**.

## 1. Executive summary

Frontier adds an isolated, research-only market-data foundation for Polymarket,
Kalshi, and Kraken spot. It has versioned venue-aware contracts, a bounded
public-GET adapter protocol, capability declarations, normalizers, an append-only
SQLite evidence store, relationship hypotheses and append-only review revisions,
an explicit payoff-equivalence check, two narrow Decimal opportunity evaluators,
deterministic replay, local API routes, and a native Mission Control workspace.

An official source-terms review on 2026-10-27 adds a live-data permission
boundary: Kalshi capture is blocked pending written research/retention
authorization, and Kraken capture is blocked pending review of applicable
market-data terms and any required permission. Their adapters remain available
for offline fixtures. Previously captured source artifacts remain preserved
and are quarantined from Frontier application reads, graphs, candidate/replay
views, and Arena replay result APIs while the hold is active. Direct database
inspection and exports remain within the operational hold.

The three adapters are implemented and fixture/contract tested. Polymarket also
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
Saved Kalshi event and series metadata can also drive a bounded, local fee
sensitivity for one hypothetical taker fill. It supports two documented
quadratic fee types, shows direct and non-direct balance-precision cases, and
does not modify candidate economics. The input price and quantity are manual
scenario assumptions, not observed quotes or account-specific costs.
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
2. `adapters/base.py`, `adapters/transport.py`, and three venue adapters:
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

The three adapters are registered at API construction, but that action is
local-only. Network access is gated separately for each source. There is no
Frontier API key type, account endpoint, wallet, execution method, or order
submission route.

## 4. Exchange integrations and capability matrix

| Venue | Implemented public research | Preserved distinctions and limits | Live evidence |
| --- | --- | --- | --- |
| Polymarket | Gamma v1 CTF-token and v2 position-ID discovery; v1-host public CLOB books; v2 position books routed to the documented `clob-v2` host; legacy public trades and cursor-paginated Data API v2 pages; native token/condition/event IDs; strict normalization, supported fee-shape handling, and bounded parent-event group capture | V1 settlement identity remains absent. V2 position markets map to the documented Polygon pUSD token identity, but market-specific payout and resolution remain unverified. The v2 book route is fixture-tested only because `clob-v2.polymarket.com` did not resolve from this development host. No incremental book stream or candle normalization; fee schedules expire after five minutes and unsupported exponents remain unknown; v2 condition history is fixed to three years and page capture uses taker-only trades with a 0.01-share floor. | Earlier live API evidence persisted one listing, one book, and ten trades through the older trade path. A direct v2 first page and one continuation through the local API route each returned ten rows and were hash-verified via isolated stores; no third page was requested. A one-market listing captured a market-specific `zero_fees` schedule at 20:41:18.972060Z, with `feesEnabled=true`, exponent 1, taker-only, rate 0; normalized status was verified only through 20:46:18.972Z. The 2026-10-27 v1-host book probe returned HTTP 200, 58 bid levels and 8 ask levels, body SHA `cecdb8d4f14fa61a7039e1559a52e02c2e7819a0342566f5d07d829841bc9aef`; this is one current public snapshot, not V2-host or settlement validation. |
| Kalshi | Public market listing and ticker-bound detail; binary YES/NO instruments; public book snapshots/trades; ticker-filtered cursor trade pages; event/series fee metadata; one-fill and one-order taker-fee sensitivities; bounded event groups and MVE event discovery; adapter v10 retains v4 normalization of up to 64 native MVE selected component references | MVE selected legs remain conditional source assertions, not verified component rules, combo payoff, or settlement equivalence. Adapter v10 adds a single-market detail GET only for a child ticker referenced by a saved parent MVE; the API checks market and event identity, persists the raw/normalized row, and includes `market_metadata` in market query and graph revisions. Adapter v8 accepts the documented top-level empty event-market array when the event-level field is omitted; v9 adds the single-event `tickers` filter. Asks are derived from complementary YES/NO bids where applicable. Trade pages normalize `yes_price_dollars` as a YES-price reference and preserve `no_price_dollars` and taker fields only in raw evidence; no BUY/SELL aggressor direction is inferred. Fee sensitivity remains manual, not a candidate/account fee schedule; actual account precision, maker/mixed-order behavior, FCM charges, scheduled changes, and full candidate fee applicability remain unresolved. No stream or historical-candle normalization. | Earlier listing/book/trade/event/fee captures remain hash-pinned. The one MVE child capture returned HTTP 200 with raw SHA `0f1c3cd42cac5202ca5a3012d58cb8d9631bf39cce313c738bb0448140271eda` and temporary-store row SHA `a2e7ae0c08436155a0bdc80e07f16d6b882eaf9706617994be135b668ec5897a`. Its source ticker and event matched the saved parent reference; the child was closed and its rules describe fair-price fallbacks. It contains no child book/price, does not establish combo payoff, and does not create cross-venue economics. |
| Kraken Spot | Configured-pair AssetPairs metadata; public depth, trades and OHLC; pair tick/lot/minimum fields retained | Spot is a base/quote instrument, not an event payoff. Fee tier, account eligibility, custody, and event hedge semantics are unknown. Pair discovery is an explicit allowlist. | Bounded live API capture persisted XBT/USD metadata, depth with 10 asks/10 bids and per-level timestamps, and ten trades. No prediction-contract equivalence was found. |

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

Kalshi's event/series fee metadata is captured and linked to raw responses, but
the exact fee schedule, fee-change timing, maker/taker applicability, and
account-specific rounding/rebates are not reconciled into an executable cost;
its fee therefore remains unknown. Kraken's public pair data does not establish
the account's current fee tier. Its trade-volume
endpoint is authenticated, which Frontier does not call ([Kraken Get Trade
Volume](https://docs.kraken.com/api-reference/account-data/get-trade-volume)).
No fee is guessed for either source.

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
currency codes. Binary and multi-outcome economics require exact quote identity
agreement from payoff to instrument to observed book, and fee arithmetic
requires the fee unit to match. Candidate capital comparisons use the exact
settlement identity; the UI separates virtual balances by venue and canonical
identity. A token whose code is `USD` cannot be added to, compared with, or
funded from `fiat:USD` without an explicit valuation model. Legacy records that
lack identity remain readable, but the candidate and audit paths classify them
as incomplete. FrontierMarket schema v3, BookSnapshot v2, TradeObservation v3,
OpportunityCandidate v2, economic model v6, independent audit v3, and replay v7
pin this extension.

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
within the bounded proposal limit. The binary and multi-outcome candidate
evaluators still require their supported verified constructions; a component
reference alone returns a price-discrepancy-only classification.

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

## 7. Opportunity discovery algorithms

Two bounded candidate families are implemented. Cross-venue complete all-long
binary coverage still requires a previously verified same-payoff relationship.
It checks both directions through binary outcome/instrument mappings and
enumerates the verified states. Within-market multi-outcome coverage buys one
contract for each of three to sixteen states in one open event market. It
requires a verified, exhaustive payoff, verified resolution, matching settlement
asset, and a strict one-to-one mapping between states and unit-payout one-hot
instruments. All legs use one venue and quantity unit. The evaluator fails closed
on incomplete or overlapping state vectors, missing books, unsupported fees,
invalid size steps, insufficient depth, or incompatible timing evidence.

The within-market construction has controlled fixtures and deterministic replay
coverage; no captured public listing had verified payoff and resolution evidence,
so it has not run against a genuine eligible event. It does not use title
similarity as a trade relation and does not search unbounded cycles,
partial-payoff combinations, logical implications, or arbitrary multi-leg
portfolios.

Replay also returns the bounded set of deterministic relationship proposals, but
only previously stored verified relationships are applied to payoff arithmetic.
No public source capture supplied a verified relationship or a verified
exhaustive multi-outcome event, so the live sample produced no eligible
opportunity evaluation. Implication bounds, exhaustive multi-leg optimization,
and spot/derivative hedge models remain deferred. Each generated candidate is
passed to the separate independent arithmetic audit described below. A regression
also verifies that non-identity outcome mappings and reversed input ordering
still produce actual candidates rather than a vacuous empty result.

## 8. Independent economic verification

For supported candidates, the primary Decimal candidate calculator evaluates
terminal payout by state; per-venue gross capital, fee amounts, modeled net cost, and worst-state
gross/net result; quantity step/minimum and displayed top-ask depth; quote
currency and settlement compatibility; receipt and exchange timestamp skew;
book age; and scenario slippage, delay-based quote decay, and fill fraction.
Per-venue capital reports principal and any verified fee; when a fee is unknown,
the missing amount is called out and never treated as zero. Unknown fees prevent
a decisive net calculation. A missing/stale book, unsupported
payoff, incomplete equivalence, or currency mismatch fails closed into a
non-positive or incomplete classification.

Candidate detail now exposes the existing `capital_by_venue` estimate through
a client-only virtual balance comparison. Each venue is checked independently
using exact decimal arithmetic; balances are neither pooled nor transferred.
Requirements use modeled buy prices plus known fees. When an applicable fee is
unknown, the UI reports principal coverage but leaves fee sufficiency
unresolved. Missing or mixed quote currencies disable the comparison. This is a
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

Kalshi fee parameters are now recorded, while exact market/account fee costs
remain unresolved; Kraken account-tier fees are not known from the public spot capture;
and Polymarket fee semantics remain constrained to the strict exponent-1
normalizer and five-minute market metadata expiry. Cross-venue FX, collateral denomination,
transfer/withdrawal cost, account funding allocation, capital duration,
jurisdiction, custody, and settlement access are unmodeled. Public depth is a
time-stamped displayed snapshot, not a fill guarantee. In this evidence set,
cost-adjusted discrepancies and executable opportunities are therefore
unestablished.
The saved Kalshi fee-metadata pair supports a standalone one-fill sensitivity
and a bounded manual one-order sensitivity under the July 7, 2026 public
quadratic taker formula and both documented balance-precision cases. The order
model handles per-fill rounding, accumulated order rounding, and capped rebates
for up to 32 fills of one recorded instrument and side. It is not an account fee
quote or book-priced result; maker/mixed-order fills, FCM charges, actual account
precision, later schedule changes, and candidate fee integration remain
unresolved. It does not enter the candidate's canonical `FeeSchedule`, and
unknown cost treatment in candidate economics is preserved.

## 16. Unresolved defects and blockers

No active code/test blocker is known in the implemented subset. Major acceptance
gaps are deferred work, not hidden passed checks:

- Live API-to-store validation covered one listing, one book, and at most ten
  legacy trades per venue. One direct v2 first page and one API-route
  continuation page were hash-verified; no third page, full history walk, or
  live browser-to-source session was run. Fee endpoints,
  live retries/degradation, timeouts, repeated schema variation, and book
  freshness across a time series remain unverified. Deterministic API tests cover
  complete invalid-JSON, invalid-UTF8, HTTP 503 and 2xx schema-failure evidence,
  bounded retry attempts, source isolation, health degradation, and recovery.
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
  query chunking. Uncentered search remains a single bounded read; full-universe
  search/clustering, relationship revision-history drill-down, and authenticated
  review remain unimplemented. A later focused browser test now verifies a
  revision-pinned depth-two page; the earlier memory-pressure deferral is
  superseded for that focused case.
- The only multi-outcome family is a same-market all-long construction over
  verified one-hot exhaustive states; only controlled fixtures have exercised it.
  Logical implication bounds and general multi-leg search are not implemented.
- The independent economic audit rechecks supported arithmetic from the same
  pinned normalized evidence. It cannot authenticate source semantics, reviewer
  identity, external assertions, fee authority, timestamps, or exchange truth;
  it is not a second independent market-data source.
- No account-independent fee resolution, FX, cross-venue capital transfer,
  settlement risk, or partial-leg exposure model exists.
- No continuous source worker, incremental book stream, gap reconstruction, or
  source-specific long-horizon quality study exists.
- A bounded Frontier paired-replay job is now registered with Arena and exposed
  through its local API and Mission Control. It reuses the host-wide admission
  gate and has fixture, API, and UI coverage, but no systemd worker was admitted
  or launched. There is still no Laboratory experiment manager or durable
  campaign scheduler. The complete repository Python suite and browser suite
  beyond the targeted Frontier cases were not run.

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
   BFS fixture coverage. Run its targeted browser E2E when measured host memory
   pressure permits. Extend beyond the current 200-market/500-row bounds or add
   clustering only after representative data and resource measurements justify
   the added scope.
3. Extend Kalshi fee evidence only when public metadata establishes the market's
   applicable formula and precision model beyond the current bounded taker
   sensitivity. Keep Kraken account fee tier unknown without authenticated
   data; no candidate may use unknown or expired fees as zero.
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
7. Only after representative evidence, consider FX, capital allocation,
   settlement/transfer, and instrument hedge models.

## 19. Exact files and commits changed

Implementation and documentation commits on this branch:

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

## 20. Final status and continuation instructions

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
| Adapter protocol, capability registry, bounded GET transport | COMPLETE AND VERIFIED | Contract tests, all capability declarations, host/size/rate/redirect bounds; Kalshi MVE discovery is explicitly supported while Polymarket/Kraken remain unsupported. |
| Kalshi MVE settlement metadata and arithmetic audit | PARTIALLY VERIFIED | Adapter v13 introduced bounded component YES settlement values and optional parent settlement/provisional fields; Kalshi adapter v14 retains that behavior. A saved-evidence-only API/UI audit recomputes the selected component product for up to 64 legs and compares it with the parent value only for complete evidence and explicit finality; audit schema v2 identifies its algorithm and returns the parent lifecycle/provisional flag. Direct official rule/schema links and observation/raw hashes are shown. All settlement arithmetic remains fixture-only; the preserved live child lacks values, no live audit result exists, and the method does not verify outcomes/rules or alter candidate economics. |
| Polymarket, Kalshi and Kraken Spot adapters | PARTIALLY VERIFIED | Fixture/contract tests and bounded live listing/book/legacy-trade captures are preserved. Polymarket v2 first and continuation pages returned ten rows each. Kalshi has a ticker-filtered cursor-page implementation, fixture-verified row mapping, and a live empty terminal page; live trade-row normalization remains unvalidated. Adapter v4 preserves native MVE selected component IDs/sides; v7 added one-page MVE discovery whose live response omitted nested markets; v8 fixes event-detail parsing of an explicit empty top-level market array; v10 captures a saved-parent-referenced child contract and preserves its native rules. The one captured child is closed and includes fair-price fallback conditions; neither its simple binary payoff nor the parent-combo payout is verified. Account fees and Kraken account fee applicability remain unresolved. API fixtures cover source degradation and recovery; live degraded-source behavior remains unverified. |
| Canonical market/instrument normalization | PARTIALLY VERIFIED | Three distinct instrument classes are represented; FrontierMarket schema v3, BookSnapshot v2 and TradeObservation v3 retain exact quote-denomination identities where a source mapping is established. Instrument, book, fee, trade, candidate-leg and capital units are distinguished from display codes. Legacy rows load with identity absent and remain economically incomplete. V2 Polymarket trades retain native outcome-token identity; Kalshi MVE component references remain source assertions; `MarketBatch` schema v2 preserves typed `MarketGroup` membership state. The genuine MVE response records member-list state `omitted` and zero child markets. Payoff/resolution semantics remain unverified. |
| Relationship hypotheses, review revisions, indexed neighborhoods, and explicit same-payoff verifier | PARTIALLY VERIFIED | Self-attributed review API/UI, append-only revisions, latest-state replay, tamper/migration checks, left/right endpoint-indexed 1–3 hop scans capped at 500 rows, one-hop keyset pages, and revision-bound multi-hop BFS pages with deterministic recomputation and 201-market chunk coverage. Matcher v5 includes bounded exact-ID MVE selected-component references as HYPOTHESIS edges with both source record IDs; a saved Kalshi parent listing and child detail replay into one such edge. Matcher v4's explicit year-conflict rejection remains. A genuine House-control topic pair remains text-only HYPOTHESIS and fails strict same-payoff verification. Payout currency must match each payoff settlement asset, and the market-level settlement asset must agree; the focused USD/USDC test passes. The focused depth-two browser E2E now passes; reviewer authentication, revision-history drill-down, and full-universe search remain absent. |
| Opportunity candidate and independent economic checks | PARTIALLY VERIFIED | Two-venue all-long binary and same-market 3–16 state one-hot exhaustive coverage; economic model v6 computes an exact full/no-fill adverse exposure pattern over up to 16 legs, and independent audit v3 recomputes it from pinned inputs and exact quote, fee and capital denomination identities. Differential three-leg enumeration and maximum 16-outcome replay/audit agree; fee-total, per-leg-fee, and venue-capital mutations are rejected. Unknown-fee cases, malformed cross-venue leg handling, no-bridge payout/settlement denomination rejection, same-ticker/different-network asset rejection, and a token with ticker `USD` versus fiat USD mismatch all fail closed as expected. Cross-venue timing requires matching known timestamp semantics, nonfuture timestamps, and observed skew plus quantified source clock uncertainty within the scenario bound; controlled adversarial cases pass. Current venue adapters omit clock uncertainty, leaving live cross-venue timing unverified. Broader funding/settlement costs and operational feasibility remain incomplete. |
| Kalshi taker-fee sensitivity | PARTIALLY VERIFIED | Hash-matched public event/series evidence supports one-fill and bounded one-order Decimal sensitivities for two documented quadratic taker fee types, both precision cases, per-fill rounding, order accumulation, and capped rebates. Tests match the official one-fill example and exercise buy/sell arithmetic. The dated official schedule's `KXMVE` multiplier pair is not assumed to apply to captured `KXMVECROSSCATEGORY` metadata. Manual inputs are not live quotes or book-priced; account-specific fees and precision, exact maker/mixed-order applicability, FCM charges, later schedules, and full candidate fee integration remain unresolved. |
| Append-only evidence store and deterministic replay | COMPLETE AND VERIFIED | Storage schema v6, additive v2/v3/v4/v5 migration, bounds, hash validation, and immutability. Replay v7 carries exact store record IDs and the new denomination fields through API-loaded market/book provenance, manifests, candidate legs, and Arena snapshots; direct in-memory replay retains adapter IDs. Replay-v5 economic output includes full/no-fill sensitivity and pins effective mappings/proposal limit. The separate Arena wrapper uses immutable content-addressed snapshots and hash-verified result artifacts; two controlled fixture workers completed and the latest recorded CPU/RSS. |
| Frontier API and source configuration | COMPLETE AND VERIFIED | Kalshi MVE discovery validates exactly one series/collection/event-ticker filter, capability/config gates, one-page bounds, and raw/normalized lineage; it does not follow the source cursor. Component detail is a separate one-GET capability, bound before the request to a ticker in a saved parent's selected legs and after the response to the saved event identity. Four focused tests now cover raw capture retention after drained Polymarket trade-page and generic market/book/trade lineage mismatches, with no duplicate of an earlier successful listing. |
| Paired scenario comparison | PARTIALLY VERIFIED | Local deterministic comparison, atomic result persistence, API/UI, and isolated browser tests pass. Two systemd-supervised Arena jobs completed over the same controlled fixture with verified result identities; the latest worker's process CPU and peak RSS are visible in Mission Control. No genuine matched live cross-venue pair or live economic claim exists. |
| Live market/book/trade and fee metadata through adapters/API | PARTIALLY VERIFIED | Earlier listing/book/trade, event-group, fee-metadata, and trade-page captures are hash-pinned. Kalshi MVE captures include filtered pages whose nested markets were omitted and one detail response with explicit top-level `markets: []`. The new one-request child detail capture matches a selected leg's saved ticker/event identities and has raw/store hashes; its rules expose fair-price fallbacks, but it has no book/price and proves neither child nor combo payoff. No cross-venue timing, combo economics, venue-wide coverage, or execution is established. |
| Source workers and broad historical data | DEFERRED | No persistent worker or long-duration collection. |
| Laboratory/Arena research orchestration | PARTIALLY VERIFIED | Arena job kind, content-addressed snapshots, bounded offline execution, API submission/history/result verification, process CPU/RSS capture, and explicit workspace controls are implemented and tested; two fixture jobs passed the host-wide gate and completed under systemd. Laboratory campaign management and resource-sustainability evidence remain incomplete. |
| Native Mission Control workspace | PARTIALLY VERIFIED | Local API, bounded graph/review UI, Polymarket/Kalshi trade-page and event-group controls, explicit filtered one-page Kalshi MVE capture by series, collection, or one event ticker with returned member-list state, parent-event context, instrument-bound fee sensitivity, selected-leg component-rule and recorded-settlement arithmetic inspection, paired replay, candidate fill stress, virtual balances keyed by venue and exact denomination identity, and Arena job history/result display. The Frontier component file passes all 8 tests, including token `USD` versus fiat `USD` separation; web typecheck, targeted frontend and browser-test ESLint, and Prettier pass. The focused depth-two/capital-fragmentation/mobile browser case passes with the exact-identity fixture contract. The production build now passes with 676,320 KiB peak RSS and no swap; Vite reports the existing 500 kB chunk-size warning for the index/chart chunks. The workspace is not deployed. |
| Source data use/retention permission | BLOCKED | Official Kalshi terms restrict API collection/storage to facilitating a member's own exchange trading absent authorization. Kraken terms require prior permission for some non-personal commercial public market-data uses; Frontier has not classified that use. The main API now requires permission/review references in addition to probe flags. References are not independently verified; no new Kalshi/Kraken live captures or new research use of their stored data pending review. Existing artifacts are preserved unchanged. |
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
authorization. The official [Kraken API introduction](https://docs-legacy.kraken.com/api/docs/guides/global-intro/)
requires prior permission for certain uses, including non-personal commercial
use of public market data; Kraken's terms vary by region. This project has no
recorded written Kalshi research/retention authorization, and has not classified
the applicable Kraken use. This is an operational restriction, not legal advice
or a finding about prior use.

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
