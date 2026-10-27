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
   resolution, fee, quantity, book, trade, candle, health, and provenance types.
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
   bounded graph-neighborhood queries, and separately configured public captures.
7. `apps/web/src/Frontier.tsx`: native Mission Control research workspace and
   paired-assumption workbench.

The three adapters are registered at API construction, but that action is
local-only. Network access is gated separately for each source. There is no
Frontier API key type, account endpoint, wallet, execution method, or order
submission route.

## 4. Exchange integrations and capability matrix

| Venue | Implemented public research | Preserved distinctions and limits | Live evidence |
| --- | --- | --- | --- |
| Polymarket | Gamma market discovery; CLOB books; legacy public trades; cursor-paginated Data API v2 trade pages; native token/condition/event IDs; strict market normalization and supported fee-shape handling | Event outcomes are not marked payoff-verified; settlement asset and resolution meaning are not independently attested; no incremental book stream or candle normalization; fee schedules expire after five minutes and unsupported exponents remain unknown; v2 condition history is fixed to three years and page capture uses taker-only trades with a 0.01-share floor | Earlier live API evidence persisted one listing, one book, and ten trades through the older trade path. A direct v2 first page and one continuation through the local API route each returned ten rows and were hash-verified via isolated stores; no third page was requested. A separate one-market listing captured a market-specific `zero_fees` schedule at 20:41:18.972060Z, with `feesEnabled=true`, exponent 1, taker-only, rate 0; normalized status was verified only through 20:46:18.972Z. |
| Kalshi | Public market discovery, market metadata, binary YES/NO instruments, public book snapshots/trades, ticker-filtered cursor trade pages, explicit event/series fee metadata, and a standalone one-fill taker-fee sensitivity; retains native rules, status, timestamps and market fields | MVE metadata is classified as conditional; asks derived from complementary YES/NO bids where applicable. Trade pages normalize `yes_price_dollars` as a YES-price reference and preserve `no_price_dollars` and taker fields only in raw evidence; no BUY/SELL aggressor direction is inferred. The fee sensitivity is not converted to candidate/account fee costs; fee applicability, maker path, scheduled changes, account class and multi-fill accumulation remain unresolved. No stream or historical-candle normalization. | Earlier bounded API capture persisted one listing, an empty book, and a valid empty trade response. A later one-market public listing plus event and series fee-metadata captures returned HTTP 200, used three GETs total, and passed raw/row hash-verified temporary-store read-back. One later bounded listing-plus-trade-page request pair returned HTTP 200; the page had zero trades and no next cursor, with raw and row hashes verified. |
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
Unknown fields with economic consequences remain unknown. Raw native metadata is
kept alongside normalized values for inspection.

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

## 6. Relationship graph

`relationships.py` builds a deterministic, bounded index using venue-local native
event IDs and cross-venue title tokens. Cross-venue text results are explicitly
`HYPOTHESIS` edges with evidence terms, source observation IDs, matcher version,
and stable identities. Similar titles cannot certify same payoff.

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
and ID. The opaque continuation cursor binds the center, page size, and append-
only graph revision counts for recorded `market_listing` and
`instrument_metadata` observations, relationships, and reviews. The market
observation count pins the metadata used to render graph nodes; books and trades
do not change that graph revision. The API checks the revision before and after
each page read and returns 409 if it changed, so the client restarts rather than
silently mixing graph states. Each page reads at most 500 source relationship
rows; the UI returns 30 visible edges per page and provides previous/next
controls. Deeper one-to-three-hop traversals
remain a single bounded query and report when their scan may be incomplete.
Without a center the route returns a bounded recent edge window. The UI renders
at most 18 network edges and retains an evidence list capped at 30 per page.
Clustering, layout control, full-universe search, and multi-hop pagination remain
incomplete.

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
indexes and revision-bound cursors, and the visual network caps at 18 edges.
Reviewer authentication, external assertion retrieval, multi-hop
pagination/clustering, and experiment result drill-downs remain incomplete.
The Replay & Readiness section also includes a content-hashed Arena job list and
detail view. It labels the limits and offline worker boundary and shows the
hash-verified completed paired comparison. Job history is a 500-record bounded
scan and can report when it may be incomplete.
Candidate detail shows the independent audit disposition,
recomputed economics, and pinned-input hash. Readiness summarizes audit
dispositions from the most recent three hash-valid runs and explicitly says that
arithmetic agreement does not establish profitability or execution.

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
- The latest replay/API regression passed **29 tests** in 12.08 seconds across `tests/arena/test_frontier_replay.py` and `tests/frontier/test_api.py`, including rejection of malformed and out-of-bound worker measurements. The updated Mission Control Frontier component passed **7 tests**, including CPU/RSS display and the capacity-limit note. The production frontend build passed; the Frontier chunk is 68.90 kB JavaScript and 29.81 kB CSS. The existing 503.86 kB main and 544.41 kB Chart chunks still trigger Vite's bundle-size warning. TypeScript, ESLint, Prettier, and Ruff passed. `jobs.py` passed mypy; checking `apps/api/arena.py` still reports three pre-existing errors in unchanged API code, outside the added projection helper.
- The targeted Frontier browser suite passed **3 tests** in 8.5 seconds with one worker. It verifies workspace responsiveness, that Arena history does not start work on page load, and bounded/mobile graph behavior. An isolated ASGI API read of the persisted worker returned the three allowlisted metrics, and the result route returned HTTP 200 with `integrity_verified=true`; no production API process was started.
- Ruff check and format passed for all changed Python files. Mypy passed in strict mode for the Frontier replay job module, Arena job schema, and Frontier API (3 source files). A broader import-following mypy run reports 37 errors in 8 existing Veritas/Arena/API files, including unrelated legacy errors in `apps/api/arena.py`; it reported no errors in the Frontier replay job or `apps/api/frontier.py`. `git diff --check` passed.
- Two systemd-supervised Frontier fixture jobs completed after the ordinary host-wide Arena gate admitted them. Their paired results verify against the same pinned snapshot. The latest manifest now records process CPU/RSS, and Mission Control exposes the allowlisted measurements with a capacity-limit note. These fixture jobs do not validate a live relationship or economic opportunity; resource sustainability remains `NOT_MEASURED`.
- After the 130-test regression, two targeted API cases passed for snapshot staging and simulated admission denial. The denial returned HTTP 409, preserved the content-addressed snapshot, issued no source request, and created no job.

Backend tests emitted one upstream Starlette/httpx TestClient deprecation
warning. No tests modified legacy expectations to make them pass. Fixture network
responses are distinct from the preserved genuine public capture files.

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
The saved Kalshi fee-metadata pair supports only a standalone one-fill
sensitivity under the July 7, 2026 public quadratic taker formula and displayed
balance-precision cases. It is not an account fee quote, does not model
multi-fill accumulation, rebates, FCM charges, or later schedule changes, and
does not enter the candidate's canonical `FeeSchedule`; unknown cost treatment
in candidate economics is preserved.

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
- Centered graph neighborhoods now use left/right endpoint indexes, bounded to
  500 relationship rows per request and a 200-market recorded window. Centered
  one-hop browsing has keyset continuation tied to append-only graph counts and
  rejects stale cursors. Uncentered and multi-hop queries remain bounded single
  reads; full-universe search, multi-hop pagination/clustering, relationship
  revision-history drill-down, and authenticated review remain unimplemented.
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
2. Extend revision-bound pagination to multi-hop graph traversal only if a
   bounded cursor can preserve breadth-first ordering; add full-universe search
   and clustering only after representative data and measurements exist.
3. Extend Kalshi fee evidence only when public metadata establishes the market's
   applicable formula and precision model beyond the current bounded taker
   sensitivity. Keep Kraken account fee tier unknown without authenticated
   data; no candidate may use unknown or expired fees as zero.
4. Seek real public multi-outcome metadata that meets the strict payoff and
   resolution requirements; broaden accepted payoff families only with
   independently checked evidence.
5. When normal host admission permits, run one bounded paired-replay Arena job
   and measure its supervised runtime. The job type, snapshot, API, and UI are
   implemented; systemd execution remains unvalidated. Add durable Laboratory
   experiment definitions only if a concrete use case requires them. Do not
   launch unattended campaigns.
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
  nonnegative, range-bounded numeric checks into a typed helper; the same three
  existing unrelated API typing errors remain.

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

## 20. Final status and continuation instructions

Frontier’s isolated engine/API/UI foundation is **implemented and boundedly
verified**. The mission as a whole is **not complete**. It remains unmerged,
undeployed, without ongoing collection, and without genuine verified
cross-venue economics.

| Major component | Status | Evidence and limit |
| --- | --- | --- |
| Isolated baseline/worktree and preserved unrelated changes | COMPLETE AND VERIFIED | Branch starts at verified V6 commit; original dirty worktrees untouched. |
| Adapter protocol, capability registry, bounded GET transport | COMPLETE AND VERIFIED | Contract tests, all capability declarations, host/size/rate/redirect bounds. |
| Polymarket, Kalshi and Kraken Spot adapters | PARTIALLY VERIFIED | Fixture/contract tests and bounded live listing/book/legacy-trade captures are preserved. Polymarket v2 first and continuation pages returned ten rows each. Kalshi has a ticker-filtered cursor-page implementation, fixture-verified row mapping, and a live empty terminal page; live row normalization remains unvalidated. Kalshi event/series parameters and Kraken spot data are captured, while exact Kalshi account fees and Kraken account fee applicability remain unknown. Live degraded-source behavior remains unverified. |
| Canonical market/instrument normalization | PARTIALLY VERIFIED | Three distinct instrument classes are represented; v2 Polymarket trades retain native outcome-token identity. Live lineage and several payoff/settlement semantics remain unverified. |
| Relationship hypotheses, review revisions, indexed neighborhoods, and explicit same-payoff verifier | PARTIALLY VERIFIED | Self-attributed review API/UI, append-only revisions, latest-state replay, tamper/migration checks, left/right endpoint-indexed 1–3 hop scans capped at 500 rows, revision-bound centered one-hop keyset pages, stale-cursor rejection, and a 501-edge scan-bound test; no genuine equivalent pair, reviewer authentication, or multi-hop pagination. |
| Opportunity candidate and independent economic checks | PARTIALLY VERIFIED | Two-venue all-long binary and same-market 3–16 state one-hot exhaustive coverage; economic model v4 computes an exact full/no-fill adverse exposure pattern over up to 16 legs, and independent audit v2 recomputes it from pinned inputs. Differential three-leg enumeration and unknown-fee cases pass. Controlled fixtures only; source semantics, account costs, broader funding/settlement costs, and operational feasibility remain incomplete. |
| Kalshi taker-fee sensitivity | PARTIALLY VERIFIED | Saved, hash-matched public event/series fee evidence supports a local one-fill calculation for two documented quadratic fee types, with Decimal and rounding tests. Manual inputs are not live quotes; account-specific, multi-fill and full candidate fee integration remain unresolved. |
| Append-only evidence store and deterministic replay | COMPLETE AND VERIFIED | Schema v6, additive v2/v3/v4/v5 migration, bounds, hash validation, immutability, replay-v5 output includes full/no-fill sensitivity and identity pins effective mappings and proposal limit. The separate Arena wrapper uses immutable content-addressed snapshots and hash-verified result artifacts; two controlled fixture workers completed and the latest recorded CPU/RSS. |
| Paired scenario comparison | PARTIALLY VERIFIED | Local deterministic comparison, atomic result persistence, API/UI, and isolated browser tests pass. Two systemd-supervised Arena jobs completed over the same controlled fixture with verified result identities; the latest worker's process CPU and peak RSS are visible in Mission Control. No genuine matched live cross-venue pair or live economic claim exists. |
| Live market/book/trade and fee metadata through adapters/API | PARTIALLY VERIFIED | One bounded listing, book, and legacy trade response per venue is hash-pinned; Polymarket v2 pages have distinct IDs; a Kalshi event/series fee-metadata read-back and a new cursor-page response are hash-pinned. The cursor page was empty and terminal, so its live row mapping is not established. Samples are not synchronized and do not prove venue-wide coverage, fees, or execution. |
| Source workers and broad historical data | DEFERRED | No persistent worker or long-duration collection. |
| Laboratory/Arena research orchestration | PARTIALLY VERIFIED | Arena job kind, content-addressed snapshots, bounded offline execution, API submission/history/result verification, process CPU/RSS capture, and explicit workspace controls are implemented and tested; two fixture jobs passed the host-wide gate and completed under systemd. Laboratory campaign management and resource-sustainability evidence remain incomplete. |
| Native Mission Control workspace | PARTIALLY VERIFIED | Local API, bounded graph/review UI, Polymarket/Kalshi trade-page controls, Kalshi fee inspection, paired-replay workbench, candidate one-sided-fill detail, and Arena job history/result display; unit tests and isolated Frontier E2E cover local fixture paths. No job was submitted by E2E, and production deployment/live browser-to-source validation are not done. |
| Production readiness/deployment | DEFERRED | Separate review and authorization required; production eligibility is false. |
| Positive economic result | NOT ESTABLISHED | No genuine cross-venue equivalent or economically eligible result in captured evidence. |

To continue safely, use this worktree and branch. Preserve both completed
fixture jobs as supervisor-path evidence; do not infer source or economic
validity from them. Keep resource sustainability unmeasured until the workload
and host conditions are characterized beyond one short fixture. Then broaden
API-boundary degraded-source behavior;
determine whether public
Kalshi market metadata is sufficient to extend fee sensitivity into a defensible
candidate fee schedule; search for public multi-outcome metadata that meets the
strict payoff and resolution evidence requirements without loosening
attestation; extend bounded graph paging to multi-hop only if traversal order can
remain reproducible. Add durable Laboratory experiment management only if
needed beyond the tested Arena job wrapper. Add
adversarial mutations and differential audit fixtures only where they test a
distinct failure mode. Expand economics only where source evidence supports it.
Re-run the focused suites before each checkpoint. Do not enable probes by default,
deploy, modify Reality, or start a long-running campaign as part of routine
continuation.
