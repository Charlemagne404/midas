# MIDAS Frontier architecture

Frontier adds a separate, read-only market-research path to MIDAS. Its contracts
live under `packages/midas/frontier`; the legacy Polymarket strategy, Reality
recorder, Veritas evidence, Arena artifacts, and Laboratory roots are not reused
as mutable Frontier storage.

## Components

| Component | Location | Responsibility |
| --- | --- | --- |
| Canonical contracts | `models.py` | Venue, instrument kind, payoff, resolution, fee, quantity, provenance, book, and venue-declared event-group models. |
| Recorded-sample analytics | `analytics.py` | Bounded market/book/replay coverage, source-quality, pricing, timing, and candidate summaries over hash-checked local evidence. |
| Adapter protocol and lifecycle | `adapters/base.py` | Capability declarations, local health, response capture, and common read-only adapter contract. |
| Bounded HTTP transport | `adapters/transport.py` | HTTPS GET only, fixed host allowlist, bounded timeout/retry/rate/response sizes, no redirects or credentials. |
| Public venue adapters | `adapters/polymarket.py`, `kalshi.py`, `kraken.py`, `coinbase.py` | Source-specific normalization and native metadata preservation. Coinbase Exchange adds a bounded explicit-product spot source; its exact-version acknowledgement does not lift the unresolved permission hold. |
| Registry | `registry.py` | Explicit capability inventory; default instances do not probe. |
| Relationship intelligence | `relationships.py` | Deterministic indexed title and parent-event/outcome hypotheses, source-selected component references, strict payoff checks, and immutable review contracts. |
| Candidate calculators | `economics.py`, `joint_economics.py` | Decimal cross-venue binary, same-market exhaustive one-hot coverage, bounded constant-payout event baskets, and a separately bounded multi-market basket over an explicit shared-state assertion. Joint-state search caches exact mapped payout vectors, then incrementally accumulates subset payouts, costs, and market coverage; venue fees, native quantity units, depth, freshness, timing, and scenario bounds remain attached. |
| Independent arithmetic audit | `independent_audit.py` | Separately recomputes supported candidate identities, payoff coverage or constant-payout basket proofs, pinned quotes/depth, native-unit leg identities, fees, costs, terminal P&L, fill-pattern sensitivity, and classification from replay inputs. Joint-state arithmetic is verified only conditional on the pinned unauthenticated state map. |
| Virtual capital-duration sensitivity | `capital.py` | Recomputes unrounded simple-interest carry from explicit per-venue user assumptions, candidate capital, hash-checked future settlement metadata, and a bounded scenario-only post-settlement release delay; an independent arithmetic pass cannot change candidate classification. |
| Virtual funding-currency sensitivity | `fx.py` | Compares venue-isolated hypothetical balances with candidate capital under explicit namespaced asset identities and user-entered rates/fees; a separate Fraction-audited terminal-state P&L scenario is available only for an independently audited candidate with complete leg fees and sufficient virtual balance. It does not source rates or mutate candidate economics. |
| Durable evidence | `storage.py` | Append-only, size- and row-bounded SQLite observations, markets, relationship reviews/revisions, runs, and paired comparisons. |
| Replay | `replay.py` | Stable input ordering, scenario/mapping/proposal-limit-aware replay identities, exact store-record provenance for API-loaded models, deterministic results, and paired assumption comparisons. Joint-state maps are content-hashed and pinned in replay manifests. |
| Event-time replay | `timeline.py` | Offline bounded replay over repeated book updates, source-state events, and explicit cutoffs; freshness, outage invalidation, candidate summaries, and timeline hashes. |
| Finite source collection | `collection.py`, `apps/api/frontier.py` | One-source sequential bounded capture with durable restart checkpoints and an append-only hash-chained journal; explicit start/resume routes and a read-only keyset-paginated run catalog, with source policy/capability gates, per-source lock, and no job or background service. |
| Arena replay jobs | `packages/midas/arena/frontier_replay.py`, `frontier_timeline.py`, `frontier_discovery.py`, `arena/jobs.py` | Immutable content-addressed inputs, bounded offline paired, event-time, and discovery-scope comparison workers, hash-verified artifacts, AF_UNIX-only networking, and held-source filtering under Arena's existing admission gate. |
| HTTP API | `apps/api/frontier.py`, `apps/api/arena.py` | Bounded local queries and graph neighborhoods, relationship proposals/reviews, deterministic, joint-state, paired, and discovery-scope replay, config-gated captures, fee/capital/funding-currency sensitivities, coverage analytics, a verified local collection-health catalog and checkpoint joins, and local-input Arena staging/result routes. |
| Mission Control workspace | `apps/web/src/Frontier.tsx` | Sources, explicit finite checkpointed capture, markets/books/event context, coverage and source-quality analytics, relationship hypotheses, candidates, venue-separated capital assumptions and funding-currency sensitivity, local comparisons, an explicit conditional joint-state projection editor, paired/event-time/discovery-scope Arena history and evidence, pinned freshness, explicit recorded-health selection, per-scope candidate detail inspection, and readiness. |

## Additional venue selection

The current adapter set is limited to the four sources in the capability
matrix. The dated [additional venue screen](ADDITIONAL_VENUE_SCREEN_2026-10-27.md)
declines a Manifold economic adapter because the current market currency is
non-redeemable mana and its sweepstakes markets ended in 2025. It may be
revisited only as a clearly non-economic forecast source. Betfair is deferred
because documented data access requires an account application key, live
read-only access is not permitted, and commercial usage requires approval.
This avoids treating play-money probabilities or delayed account-keyed data
as directly comparable live quotes.

## Virtual capital-duration sensitivity

`POST /api/frontier/opportunities/capital-carry` accepts a saved run ID and
result hash, one candidate ID, and a decimal-string annual carry rate in basis
points for every venue represented by the candidate. It reloads that exact
append-only replay and each candidate leg's pinned market observation; it does
not query a latest-market window or call a source adapter. A missing/held market,
mixed settlement denomination, incomplete capital mapping, unverified or
hash-missing resolution, settlement at/before the candidate observation time,
or invalid input is rejected.

For each venue it applies simple interest to the candidate's recorded venue
capital from the candidate observation time through the latest settlement among
that venue's candidate markets plus the user-entered additional release delay.
Delay defaults to zero, must be a whole number of seconds, and is bounded to one
year per venue. It is included in the hashed input and independently checked.
This is a scenario assumption, not a source claim or a prediction of redemption,
withdrawal, or reuse timing. The basis is actual seconds divided by 365 days,
without compounding or currency rounding. That full-venue-through-latest rule
is conservative when legs have different release times. It is a user-assumption
sensitivity, not a sourced financing rate, fee schedule, capital-access claim,
or execution model. Unknown fees can remain excluded from candidate capital;
the result labels that and keeps the original candidate classification and
practical-eligibility state unchanged.

The response pins candidate/replay hashes, observation IDs and validated
normalized-store-row hashes, raw observation hashes,
resolution evidence hashes/fingerprints, per-venue rate/capital/delay/time inputs,
and exact decimal outputs. A separate arithmetic pass checks source-record
identity and recomputes duration, carry, and adjusted gross/net result. This
arithmetic check does not authenticate source truth or settlement, and the
transient result is reproducible from the same saved run and rate inputs rather
than persisted as a new artifact. Held-source quarantine is applied before the
market inputs are loaded.

## Virtual funding-currency sensitivity

`POST /api/frontier/opportunities/funding-currency-sensitivity` accepts a saved
run ID/result hash, candidate ID, and one explicit virtual funding assumption
for each candidate venue. Each assumption contains a full settlement-asset
identity, balance amount, target-asset units per funding-asset unit, and a
conversion fee in basis points. The route reloads only the hash-pinned saved
candidate, applies the existing held-source filter, and makes no exchange
request or database write. It needs no wallet, account, or balance connection.

For venue requirement `S`, explicit rate `r`, fee `f` basis points, and funding
balance `B`, the scenario computes required funding as
`S / (r * (1 - f/10000))`, target value available after the fee as
`B * r * (1 - f/10000)`, and conversion fee in target units as
`S * f / (10000 - f)`. Rates must be positive, fees below 10000 bps, and
balances nonnegative. When full asset identities are identical, only rate 1
and fee 0 are accepted. Similar display codes or network-specific token
tickers do not establish identity or parity. Different identities require an
explicit user conversion assumption; in Mission Control, rate and fee fields
remain blank until supplied.

Venue capital remains isolated, and the response reports per-venue funding
requirements, converted value, conversion fees, and shortfalls. A separate
Fraction-based audit checks the Decimal results; input and result digests bind
the candidate, saved run, identities, and assumptions. It is a non-classifying
funding view: conversion fees are not subtracted from candidate P&L, and
candidate classification and practical eligibility are unchanged. Unresolved
candidate fee legs are counted and remain unresolved. The feature does not
verify convertibility, access, legality, custody, transfer timing, collateral,
FX price availability, or execution. No sourced or live FX conversion is
implemented.

## Adapter capability contract

Every venue declares support or an explicit unsupported reason for every
capability. An adapter may support public metadata, snapshots, trades, or candles
while rejecting incremental books, verified fee schedules, or settlement
semantics. The shared model retains native market and instrument identifiers,
native metadata, source URL, adapter/schema versions, raw-body hash, request and
receipt times, and source-time semantics. Source quality flags are carried forward
instead of being replaced with guessed values.

### Polymarket historical price samples

Polymarket adapter v7 exposes a separate `price_history` capability for the
public CLOB `GET /prices-history` endpoint. The source requires an outcome token
ID and documents `startTs`, `endTs`, `interval`, and `fidelity` query values;
Frontier currently allows `1d` or `1w` source intervals and at most seven days
per request. A request must be explicit and its token ID must appear in a
recorded market listing. The adapter rejects responses above 1500 points or the
configured response byte limit, and validates source timestamps and
probability-range prices before normalization. The source returned HTTP 400 for
30-day and 36-day windows during one read-only probe; its published reference
does not specify the maximum accepted range, so seven days is a conservative
current cap. See the official [CLOB price-history reference](https://docs.polymarket.com/api-reference/markets/get-prices-history).

The normalized `PriceHistorySeries` preserves the native token ID, requested
window, interval, fidelity, ordered UTC timestamps, exact decimal samples, and
raw-response provenance. It is not a `CandleSeries`: the API returns price
points, so Frontier does not derive OHLC, volume, or trade count. Samples are
historical source-reported values, not executable quotes, and do not establish
cross-venue simultaneity. `POST /api/frontier/probe/polymarket/price-history`
stores one response; `GET /api/frontier/price-history` reads persisted series
from the local evidence store only. The Market detail view exposes an explicit
token, interval, and lookback control. One seven-day live response with 79
points (2139 bytes) is preserved byte-for-byte with capture metadata under
`tests/fixtures`; its content hash matched a repeat capture. It was not inserted
into a Frontier runtime database, and no cross-venue relationship was produced.

### Saved price-history replay

Price history uses a dedicated descriptive replay path rather than the market,
book, and candidate replay contract. A caller selects one to eight stored
`historical_price_points` observation IDs. Before computation, the API validates
the stored raw/normalized row hashes, venue, raw-body hash, receipt timestamp,
and (when present) the bound market observation and its native instrument.
`deterministic_price_history_replay` sorts the exact source records, hashes the
normalized inputs with its replay and backend-code versions, and produces one
append-only result keyed by that pinned input manifest. It reports returned
point count, sampled Decimal minimum and maximum, first/last point timestamps,
span, maximum adjacent returned-point gap, and point timestamps later than
local receipt. It does not create order quotes, fill assumptions, opportunity
candidates, or economic claims. A large adjacent gap is descriptive; it does
not estimate missing points because the source has not established a complete
sampling cadence.

These artifacts use a separate `price_history_replays` table with immutable
update/delete triggers. Store schema 7 creates it and upgrades a schema 6 store
without changing existing observation, relationship, or replay rows. Saved
replay reads verify the manifest, run identity, result digest, and source
eligibility; held or missing observation IDs are omitted. Coverage analytics
scan at most the newest 20 history captures, group them by venue, and show
capture counts, distinct instruments, returned points, empty/unbound records,
future timestamps, capture age, point-time range, and largest observed adjacent
gap. Overlapping captures are counted independently and can repeat points. The
Mission Control quality view labels the gap as observed and explains that these
metrics do not establish source completeness or cross-venue simultaneity. The
Market detail panel offers an explicit replay action for the selected saved
series and displays the resulting run/input hashes and sample summary. The
Replay & readiness workspace pages through saved Polymarket history captures
and replay artifacts in 20-row increments, starting at the newest page. The
source selector admits up to eight inputs from the current page and clears its
selection when the page changes. The API uses a bounded one-row lookahead to
return an exact `has_more` flag; replay pagination counts held-source
omissions only in the displayed page while preserving offset order. Selected
artifacts load through the hash-validating detail route and show source
observation and raw hashes, native instrument, bound market observation,
request range, and returned-point summaries. Both views use local evidence only
and start no source request automatically.

`FrontierMarket.native_event_id` is populated only from an explicit source event
record or a parent-event response. The legacy Polymarket parser's local
`market:<market-id>` fallback is not a venue event identifier; Frontier leaves
event membership unknown when Gamma omits the event record, while retaining the
original payload in raw evidence.

Observation persistence copies the normalized model and stamps each missing
typed `Provenance.persisted_at_utc` with the Frontier writer's UTC time
immediately before serialization and the atomic SQLite insert. This records
the writer's pre-insert timestamp; it is not a commit/fsync completion time and
does not reduce source-clock uncertainty. The caller's model is not mutated.
Already-stamped normalized captures keep their original timestamp when copied
into an isolated content-addressed snapshot. On an idempotent retry, storage
validates the original raw and normalized row hashes, compares normalized
content with only the typed persistence timestamp cleared, and returns the
original observation without changing its timestamp or row hash. Older rows
whose optional persistence field is absent or null remain readable as
historical evidence.

The bounded HTTP transport also records `request_elapsed_monotonic_ns` from
after per-source pacing until the complete response body has arrived. It is
copied into raw response evidence and normalized provenance and shown in the
stored-evidence disclosure. This monotonic duration can measure one request's
transport/body time; it has no shared clock origin and cannot synchronize
separate venues or processes. HTTP failures with a complete response body keep
the duration, while failures without response evidence leave it unknown.

Adapter health is local state and does not probe the venue. Its
`requests_in_window` value counts paced HTTP request starts in the trailing 60
seconds using monotonic time. The transport keeps a bounded history sized for
its configured maximum request rate; the separate lifetime `request_count` is
used only for per-operation request deltas.

## Coinbase Exchange Spot adapter

`CoinbaseSpotAdapter` supports configured product metadata, one aggregated
level-2 book, and one public trade page. It accepts one to twenty validated
`BASE-QUOTE` product IDs; it never enumerates the product catalog or follows
trade cursors. REST calls are HTTPS GET only, use the fixed
`api.exchange.coinbase.com` host, and inherit Frontier's bounded response,
retry, timeout, and pacing limits. The level-2 endpoint returns the full
aggregated book; the adapter parses only the requested top 1–20 levels after
the transport's 256 KiB response bound. Coinbase's response `sequence`,
`auction_mode`, and native trade `side` remain in the pinned raw response.
Because the documented trade `side` describes the maker order, normalized
`aggressor_side` stays unknown. Auction books are marked indicative. Product
increments and minimums use exact Decimal; account-tier fees stay unknown.

Products normalize to `spot_pair` with base-asset quantities and a quote-currency
identity when the quote is a known fiat code. They have no event outcomes,
verified payout, or settlement rule. Coinbase spot prices cannot qualify as
event arbitrage through the payoff verifiers.

Coinbase's official [Market Data Terms](https://www.coinbase.com/legal/market_data)
were reviewed as updated 2026-08-07. The terms limit use and redistribution;
the applicable user/organization, region, and intended research/distribution
scope are not machine-validated by Frontier. Coinbase use remains held because
Frontier has no validated permission and intended-scope review loader. The
`MIDAS_FRONTIER_COINBASE_MARKET_DATA_TERMS_VERSION_ACKNOWLEDGED` value records
an exact-version acknowledgement only, and
`MIDAS_FRONTIER_COINBASE_PUBLIC_PROBE_ENABLED=true` cannot lift the runtime
hold. Coinbase probes are rejected before network access, and stored Coinbase
records remain quarantined from application research/replay routes. Re-review
current terms before any future use. The adapter is registered but does not
probe at application startup.
The 2026-10-28 review records additional terms that restrict derived works,
benchmark/valuation uses, and AI/ML research use. The local version
acknowledgement is not a blanket permission for every Frontier analysis;
source use remains gated until the intended scope is reviewed and any required
permission is validated. See the
[source-data terms review](SOURCE_DATA_TERMS_REVIEW_2026-10-27.md).

Polymarket adapter v3 and Kalshi adapter v8 declare
`EVENT_MARKET_GROUPS`. Their `discover_event_markets` operations issue one bounded
public GET, validate the requested native event identity, bound and de-duplicate
the child list, retain the source parent title, and keep native outcome wording
where the source provides it. Kraken explicitly leaves this capability
unsupported. `POST /api/frontier/probe/{venue}/event-markets` is gated by the
source's public-probe configuration and capability, requires a previously
recorded market, binds the returned group to that market's native ID, and stores
the complete raw response beside the normalized `MarketBatch` as
`event_market_listing`. This response-level completeness says nothing about
venue-wide coverage.

`FrontierMarket.native_event_title` and `outcome_label` preserve event-group
context separately from the market question. The relationship matcher may use
similar parent-event text plus an overlapping market-specific outcome token to
propose a cross-venue `TEXT_CANDIDATE`. It checks explicit years in both the
parent title and child market title; a contradiction within a venue or mismatch
across venues blocks both title and parent-context matching. When the parent
omits the year, the child title can supply it. Such edges remain `HYPOTHESIS`;
the text procedure does not infer a YES/NO mapping or certify settlement
equivalence. The independent same-payoff verifier still requires verified
exhaustive payoffs, resolution identity, authority, settlement asset, and
matching timing. It also requires each verified payout currency to equal its
payoff settlement asset, and the market-level settlement asset to agree with
that payoff. Binary and multi-outcome candidate generation plus the
independent audit repeat the denomination guard, so a forged verified
relationship cannot bypass it. No USD-to-USDC conversion or stablecoin/network
valuation bridge is assumed. `FrontierMarket` and `PayoffSpec` schema v2 added a
structured `settlement_asset_identity` beside the display denomination string;
FrontierMarket schema v3 added quote-unit fields, and schema v4 adds bounded
price-increment ranges.
Fiat identities use a three-letter code; token and other non-fiat identities
require a network ID and asset reference. Market and payoff identities must
agree, and cross-venue verification compares the complete identity, so the
same ticker on different networks is not equivalent. This normalized identity
is not independent source proof. Kalshi currently identifies its event
settlement as `fiat:USD`. Polymarket Gamma v2 position-backed markets map to the
documented pUSD contract on Polygon; the adapter routes their books to the
official SDK's v2 CLOB host. Gamma v1 CTF-token markets retain no canonical
settlement identity. The pUSD mapping is protocol-level evidence, not a
market-specific payout attestation, and Polymarket payoff and resolution
remain unverified. The v2 host path is fixture-tested but live validation is
pending. The current [Polymarket SDK protocol table](https://github.com/Polymarket/rs-clob-client-v2/blob/main/README.md),
[Polygon deployment manifest](https://github.com/Polymarket/polymarket-v2-external/blob/main/README.md),
and [collateral adapter source](https://github.com/Polymarket/ctf-exchange-v2/blob/main/src/adapters/CtfCollateralAdapter.sol)
are the mapping references. Cross-venue opportunity verification still fails
closed; no USD-to-pUSD valuation bridge is enabled.

The official [Gamma market-discovery documentation](https://docs.polymarket.com/market-data/discover-markets)
describes `GET /events/{id}` as returning an event with an embedded `markets`
array, and separately documents individual market lookups and paged
`/markets/keyset` listing. It does not document pagination of a child-market
list keyed by the Gamma event ID. Therefore one event-details request remains
subject to Frontier's 256 KiB response cap; a rejected oversized response is
represented by bounded metadata only. Individual lookups can hydrate known
market IDs, but they do not prove the event's outcome set is exhaustive. The
2026-10-28 bounded public probe encountered this limit for a group with 13
listed children, so its payoff and exhaustiveness remain unverified.
Event-group observations participate in
latest-record selection and graph revision identity, so replay and paged reads
cannot silently retain older child-only metadata.

`FrontierMarket` schema v4 adds typed `MarketInstrument.price_increment_ranges`
for the Kalshi `price_ranges` fields exposed by the [public market schema](https://docs.kalshi.com/api-reference/market/get-market).
Each start, end, and step is parsed as a bounded exact Decimal while the raw
native object remains available for audit; the documented response represents
each value as a string. The shared Decimal contract limits
these values to 18 decimal places, rejecting extreme scientific-notation
exponents before rational price checks. Missing ranges remain `null`, and an
explicitly empty array remains empty; neither is replaced with a guessed tick.
Candidate generation and the independent audit enforce any reported
constant tick and, when price ranges are present, require a quote strictly
inside a range and aligned to its step. The validator uses `start` as the step
grid anchor; this is an inference from the documented `start`/`end`/`step`
shape, not an explicit API guarantee. The schema does not state whether range
boundaries are inclusive, so boundary quotes fail closed. This validates the
bounded structure against the documented response shape; fixture tests do not
establish live price-range semantics.

Settlement identity also applies to the unit used to quote a contract. The
instrument, observed book, fee schedule, public trade, candidate leg, and
candidate capital field retain a canonical denomination beside the display
code. Supported event arithmetic requires the instrument and book quote
identities to equal the exact payoff settlement identity; a modeled fee must
identify that same fee unit. A code such as `USD` is insufficient by itself:
`fiat:USD` and a network-qualified token whose display code is `USD` remain
different units. Older rows without these optional identities continue to
load, but candidate generation and the independent audit treat the missing
unit evidence as incomplete. Replay v7 pins these identities into its inputs.
The identity schema currently accepts version 1 only. Deterministic asset keys
use the versioned `settlement-asset-v2` prefix plus a compact JSON tuple of
schema version, kind, code, network, and reference; the fields cannot collide
when a component contains punctuation such as a colon. Funding comparisons use
the structured identity fields, not the display label; non-fiat labels escape
colons and percent signs. Same-payoff and logical-implication verifier versions
advance when the key encoding changes, while stored historical relationship
rows remain untouched.

Kalshi adapter v7 introduced the separate `MULTIVARIATE_EVENT_DISCOVERY`
capability, retained by adapters v8 through v11. Its local
`POST /api/frontier/probe/kalshi/multivariate-events` route requires exactly one
series ticker, collection ticker, or event ticker, a source-enabled
public-probe configuration, and the adapter capability. A single event ticker
maps to Kalshi's documented `tickers` query parameter, and the response is
checked against that requested event ID. Each operation requests one source
page (`limit=1`)
with nested markets, validates event/child identities, caps nested markets at
the configured source bound, and retains but does not follow Kalshi's cursor.
The stored `MarketBatch` schema v2 carries typed `MarketGroup` context alongside
normalized child markets, while the raw response preserves the full source
payload. A non-empty source cursor marks the request incomplete. Even when no
cursor remains, completeness applies only to the requested filter;
it is not venue-wide inventory. Empty responses are stored as bounded empty
batches. `MarketGroup.member_list_state` distinguishes an included member list,
an explicitly empty list, and a field omitted by the source. The live response
captured on October 27 returned one event but omitted nested markets despite
the request flag; Frontier stores its group with zero normalized markets and
marks membership as omitted. It does not reinterpret omission as an empty
event; an explicit `null` member field fails closed as malformed. The adapter,
API persistence, and Mission Control operation are also
verified with documentation-shaped fixtures. The public endpoint documents
series/collection filters, single-event tickers, nested-market inclusion, and
cursor pagination
([Get Multivariate Events](https://docs.kalshi.com/api-reference/events/get-multivariate-events)).

`MarketGroup` records the native group identifier, title, series/collection
identity when returned, member-list state, parent source fields, adapter version, and
capture provenance. Group membership is a source assertion; it does not
certify logical exhaustiveness, component rules, combo payoff, or resolution
equivalence. Child MVE contracts remain conditional-event records with
unverified payout semantics. The Exchanges view lets an operator request one
filtered page, displays returned groups and member counts, and exposes the
raw/normalized observation ID and hash. It sends no request on page load.
The capture result can expand the immutable response through the local evidence
API without making another source request.

Adapter v8 also accepts Kalshi's event-detail response when the `event` object
omits `markets` but the documented top-level `markets` array is explicitly
empty. A one-GET follow-up for the saved MVE ticker returned HTTP 200 in that
shape. The saved response replays to zero child markets with its raw and
normalized store row verified. It does not establish venue-wide absence or a
child-contract payoff.

Adapter v9 adds a single-event ticker filter to the local route. A preserved
public request to `/events/multivariate?tickers=...&limit=1&with_nested_markets=true`
returned one matching event with no cursor and again omitted nested markets.
The raw response SHA-256 is
`3e2372de6143c0c8f37b3e77265a210596bf3c414fa33d19ee4028b1d2d3a7bb`; replaying
the preserved raw/normalized snapshot into a fresh temporary store verifies row
SHA-256
`e6dcb76b2e18316866c078fd4778c2dff93891132e8b92104e3385c08d1271bd`. The
original capture-time digest
`cea5ea38a3ffad129fa2baedf3520b9bae71e8d4919521e140f46467baf57d50` is kept in
the artifact but is unreconciled: it does not match the payload now preserved
there. The temporary harness raised an event-loop cleanup error after the live
response; no second live request was made. The capture still has zero child
markets and says nothing about combo payoff or broader event inventory.

Adapter v10 adds `fetch_market_metadata` for exactly one Kalshi market ticker,
using the documented public Get Market endpoint. The local
`POST /api/frontier/probe/kalshi/mve-component-market` route accepts a saved
parent combo ID and one component ticker. Before network access it requires the
parent to appear in the bounded recorded market window and the exact ticker to
be among that market's normalized `selected_components`. It then performs one
GET, validates the returned market ticker and (when the MVE reference includes
one) event ticker, and appends the full raw response plus normalized child
market. A mismatched response is retained as a diagnostic source failure; an
unreferenced ticker causes no request. The new `market_metadata` observation
kind is included in market queries and in the graph revision, so later graph
pages detect the new record without a schema migration.

Mission Control exposes this request beside each selected MVE component, gated
by the Kalshi public-probe setting and metadata capability. It shows the
captured child's current lifecycle, resolution rules, and evidence identities.
The operation does not fetch books or prices, authenticate the source rules,
verify parent combo payoff, or produce a candidate. One live capture for the
first component of a saved basketball combo returned a closed market with
primary and secondary rules that contain fair-price fallbacks for inactive or
postponed games. That conditional resolution language makes a simple one-hot
binary payoff inference unjustified. The exact raw and temporary-store row
hashes are in the engineering report and
`data/frontier/live-probes/2026-10-27-kalshi-mve-component-market-r1.json`.

Polymarket and Kalshi implement the optional `SingleMarketMetadataAdapter`
extension: each validates a native identifier, constructs its exact public
detail URL, and normalizes one returned market. The shared
`POST /api/frontier/probe/{venue}/market-metadata` route requires that
extension, a source-configured public probe, and a canonical market already
present in the bounded recorded window. It binds to the market's saved
observation ID before egress, then requires one raw response, the same venue
and canonical/native market IDs, and an exact match to the adapter-provided
HTTPS request URL. The adapter supplies venue URL semantics; the route remains
venue-neutral.

The route stores a versioned `MarketMetadataEvidence` envelope under the
`market_metadata_evidence` observation kind. The envelope links the returned
detail to its original listing observation, and its raw body/hash remain
available through the normal observation API. This envelope is deliberately
not a catalogue row: a detail lookup cannot silently replace the market's
listing or event-group context. A direct market detail also does not establish
event membership, outcome-set exhaustiveness, payoff validity, current book
state, or economic equivalence. Kraken and Coinbase expose market metadata
fields within supported discovery paths but do not currently implement this
single-ID lookup extension, so the generic route returns unsupported before
network access for those venues.

Kalshi adapter v11 adds optional `yes_settlement_value_dollars` to each typed
selected component. It parses finite, nonnegative values within the canonical
Decimal bounds, preserves the value through normalized storage and relationship
evidence, and displays it under that source field's label. Missing values remain
unknown. The official [Get Multivariate Events schema](https://docs.kalshi.com/api-reference/events/get-multivariate-events)
documents the field but does not, by itself, specify the containing MVE's
payoff calculation. Frontier therefore does not use the value as combo payout
or establish a component payoff from it. Current value-specific verification
uses documentation-shaped fixtures; the saved live child capture omitted the
field.

Adapter v12 adds a source-reported arithmetic audit for a saved Kalshi MVE.
`POST /api/frontier/economics/kalshi-mve-settlement-audit` reads only the latest
bounded local Kalshi market rows and makes no source request or candidate. It
multiplies each selected leg's reported value (YES value for YES; one minus
YES value for NO) and compares the product to the parent's recorded
`settlement_value_dollars` only when all values exist and the parent lifecycle
is settled and `is_provisional` is false or absent. Missing, non-final, and
unsupported structures receive explicit non-match states. The calculation is
bounded to 64 components and preserves Decimal values; it does not reuse or
change candidate payoff verification. Method references are Kalshi's [combo
settlement guidance](https://help.kalshi.com/en/articles/13823820-combos),
[NO scalar settlement rule](https://help.kalshi.com/en/articles/17515177-protected-nfl-player-markets),
and [MVE API field schema](https://docs.kalshi.com/api-reference/events/get-multivariate-events).
The positive example is fixture-only: the live saved child capture lacks the
required values, so no source-backed arithmetic result has been recorded.

One preserved public capture demonstrates the boundary. The Polymarket and
Kalshi event titles and party-outcome wording generated a deterministic
Democratic-market text hypothesis after adapter normalization. Their market
descriptions, resolution processes, and stated end times differ; both normalized
payoff and resolution attestations remain false. The independent verifier
rejects same-payoff equivalence, and the capture has no order books or prices.
See the evidence and exact hashes in the [engineering report](FRONTIER_ENGINEERING_REPORT.md).

Kalshi `fee_metadata` remains a deliberate bounded event-plus-series capture: the
event request excludes child markets, and both native responses are stored as
separate immutable observations. The metadata schema records whether the event
override is complete, explicitly inherits from a null/null pair, partial, or
unreported. Kalshi's [event fee-change API](https://docs.kalshi.com/api-reference/events/get-event-fee-changes)
documents event-over-series precedence and the null/null clear behavior.

On a later saved-evidence replay, the API may compile complete event/series
observations into a provenance-bound `FeeStatus.ESTIMATE` for a supported
quadratic taker fee. The join checks native market/event/series identity, raw
body hashes, official endpoint paths, parsed source fields, and observation
times. Partial/unreported overrides, unsupported fee types, mismatches, held
sources, and absent evidence remain unknown. This replay path uses Kalshi's
[July 7, 2026 public fee schedule](https://kalshi.com/docs/kalshi-fee-schedule.pdf)
formula `ceil_to_microdollar(0.07 * M * C * P * (1-P))` and its
[fee-rounding documentation](https://docs.kalshi.com/getting_started/fee_rounding).
Fee evidence must be no later than the book quote and no more than 24 hours old
at both quote and replay evaluation; no later evidence is backdated into a
candidate. For one candidate fill, the estimate then applies `$0.01` non-direct
balance-debit alignment, the larger of the two documented balance quanta. It is
a declared conservative scenario, not proof of account class or a final fee.

An estimated fee can produce a conditional or incomplete candidate, never a
verified mathematical inconsistency. Maker or mixed fills, multi-fill order
rounding/rebates, FCM charges, account-specific precision, fee-schedule changes,
and other execution costs remain unresolved. Replay manifest schema v2 pins the
event and series fee observation IDs separately from market and book IDs. The
Mission Control run summary displays their count. The independent audit
recomputes the estimate from the pinned fee model and evidence, but this only
establishes internal arithmetic agreement, not account applicability or an
executable opportunity.

The local `POST /api/frontier/economics/kalshi-fee-sensitivity` endpoint retains
the saved-evidence-bound one-fill calculation. The
`POST /api/frontier/economics/kalshi-fee-order-sensitivity` endpoint accepts one
to 32 manual fills for one recorded native instrument and one buy/sell direction.
Both use only stored event/series evidence, support documented quadratic taker
fee types, and fail closed for unsupported types or incomplete event override
evidence. The order calculation applies
per-fill microdollar trade-fee rounding, signed balance-grid alignment, an
order-level rounding accumulator, and capped precision-aligned rebates. Both
return scenarios for the documented balance quanta: `$0.0001` for a direct member
and `$0.01` for a non-direct member. Metadata IDs, raw hashes, received times,
model version, assumptions, per-fill outputs, and a calculation digest accompany
the order result. Inputs are manual and are not public quotes or captured fills.
These remain standalone sensitivities, not account quotes. Candidate replay now
uses a separate one-fill estimate when its stricter evidence rules pass; the
manual one-order calculation does not become the candidate fee calculation.
Actual account precision, maker/mixed-order behavior, FCM charges, multi-fill
rounding and rebates, and later schedule changes remain unresolved.

An offline one-fill derivation from the saved October 27 metadata capture produced a `$0.0175`
direct-member and `$0.02` non-direct-member fee scenario for one contract at a
manually supplied `$0.50`. Its input and output hashes are preserved in
`data/frontier/live-probes/2026-10-27-kalshi-fee-sensitivity.json`; it is not live
price evidence. The formula uses Kalshi's [July 7, 2026 event fee schedule](https://kalshi.com/docs/kalshi-fee-schedule.pdf)
and [fee rounding documentation](https://docs.kalshi.com/getting_started/fee_rounding).
That schedule's `KXMVE` row lists maker multiplier 2 and taker multiplier 1.
The separately captured `KXMVECROSSCATEGORY` series is not that ticker: its
event/series endpoint evidence reports `quadratic_with_combo_maker_fees` and
multiplier 1, with no event override. Frontier does not transfer the `KXMVE`
maker multiplier to a differently named series. The calculator remains
taker-only, and exact maker-fee applicability for this captured MVE series is
unresolved.

Kalshi also advertises cursor-paginated public trades. Frontier exposes one
operator-triggered ticker-filtered page at a time, caps it at 100 rows even though
the venue documents a larger limit, binds the local cursor to the recorded ticker
and page size, and stops when the source returns an empty cursor. Native
`yes_price_dollars` is represented as a YES-price reference; raw
`no_price_dollars` and taker fields remain in the auditable response. The adapter
does not infer a normalized BUY/SELL aggressor direction from
`taker_outcome_side`.

The common model is not the lowest common denominator. A binary event contract,
a multivariate event leg, and a spot pair retain separate instrument kinds and
payoff constraints. Kraken and Coinbase spot are contextual asset evidence;
neither can become an event-contract payoff through matching text.

Kalshi adapter v4 normalized the venue's `mve_selected_legs` list into bounded
`selected_components` records carrying the selected event ticker, native market
ticker, and YES/NO side. It rejects malformed, duplicate, self-referential, and
over-64 component lists, while retaining the original native fields and response
hash. Mission Control shows those source-declared components with an explicit
unverified-payoff notice. Component membership does not certify the individual
rules, combo settlement, or economic equivalence. Kalshi's public MVE schema
documents these selected market/side fields
([Get Multivariate Events](https://docs.kalshi.com/api-reference/events/get-multivariate-events));
its help center says combo payouts are the product of component position values
and that each combo settles through its own review
([Market FAQs](https://help.kalshi.com/en/articles/13823821-market-faqs)).
Frontier therefore keeps these instruments conditional and does not feed their
unverified payout into candidate economics.
The recorded settlement arithmetic audit reports a match or mismatch only
when the parent is settled and explicitly has `is_provisional=false`; a missing
provisional flag is treated as non-final evidence.
Audit response schema v2 returns `audit_algorithm_version`, parent lifecycle,
and the recorded provisional flag for result provenance.
Kalshi adapter v5 added the separate bounded event-group operation described
above; adapter v7 adds filtered MVE discovery without changing the earlier
component normalization or its payoff limitation.

## Source configurations and bounds

The API creates all four adapter manifests, but the source transport is disabled
unless its specific `MIDAS_FRONTIER_*_PUBLIC_PROBE_ENABLED` setting is true. In
addition, Kalshi requires a non-empty
`MIDAS_FRONTIER_KALSHI_RESEARCH_AUTHORIZATION_REF`, and Kraken requires a
non-empty `MIDAS_FRONTIER_KRAKEN_MARKET_DATA_PERMISSION_REF`. These references
record a separately reviewed source permission; Frontier does not validate the
referenced evidence. The current terms review blocks both live sources while
fixture development remains enabled. No startup health request is made. A
user-triggered discovery capture makes one bounded market page and may include
one selected book snapshot. An event-group capture is a separate one-GET action
linked to a previously recorded child market. Kalshi MVE discovery makes one
filtered GET for one event and requests nested markets; source retries remain
bounded by the adapter configuration.
Kraken currently uses a configured pair allowlist, not venue-wide enumeration.
Coinbase uses a configured product allowlist, not venue-wide enumeration; its
source-use gate additionally requires exact-version operator acknowledgement,
and the public-probe flag is separate. The transport caps each response at 256 KiB, retries
at most twice, has a 15-second maximum timeout, limits each adapter to 5 requests
per second, rejects redirects, and rejects hosts outside its venue allowlist.
The API serializes probes per venue and the store defaults to 64 MiB, 50,000 raw
observations, 100,000 relationship records, and 512 KiB per stored record.

When the terms gate blocks a venue, read APIs also quarantine that venue's
stored observations and derived research. SQL-level exclusions cover source
aggregates, market/book/trade rows, relationships, and bounded graph neighbors.
Direct evidence and review routes reject held records; replay inputs exclude
them, while historical Frontier results and paired comparisons are hidden when
their provenance is held or incomplete. Arena's Frontier-specific replay view,
generic job overview/detail/log routes, and research-activity digest apply the
same snapshot check.
Generic replay submission rejects held or unproven snapshots; cancellation of
a held replay is blocked before mutation. Checks run before job reconciliation
so blocked reads do not rewrite held job manifests. Missing or invalid
snapshot provenance is hidden. This does not remove or rewrite records and
does not cover direct database access or exports; those remain under the
operational hold.

## Relationship and economics boundaries

The matcher indexes exact venue-local event IDs, market title terms, and parent
event titles paired with market-specific outcome terms. Cross-venue text matches
remain hypotheses and preserve evidence terms and source observation IDs. An
explicit disagreement in four-digit event years blocks the parent-context path.
Text never supplies a YES/NO outcome mapping and is never promoted automatically.
Matcher v5 also proposes a `source_component_reference` edge when a recorded
parent's native selected-component list names a child market and the recorded
child has the exact same venue/ticker and, when supplied, event ID. The edge
retains both immutable source observation IDs and the selected side. It remains
a `HYPOTHESIS`: this records what parent metadata asserts and the matching child
identity, not that their rules, payoffs, logical implications, or settlement are
equivalent. Economic candidate generators accept only separately verified
`same_payoff` or `logical_implication` edges, so source-component references
cannot support opportunity arithmetic. Missing children, duplicate native
identifiers, venue mismatches, and event-ID mismatches produce no component
edge. These source-reference edges are prioritized within the bounded proposal
limit so they remain visible when text candidates are numerous.
The API proposal path binds each market to the actual append-only observation
record from which its selected normalized value was loaded. Persisted graph
evidence therefore opens the raw and normalized source record directly. Store-
backed API reads also overlay exact immutable record IDs onto market and book
model provenance before replay. Replay v6 pins these IDs into manifests, input
hashes, and candidate-leg evidence, so each source reference opens the saved
record through the observation API. Offline matcher or replay calls without a
store mapping continue to use deterministic adapter-derived identities. No
stored row is rewritten and no schema migration is needed.
The review API requires stored,
hash-verified source records for both markets. A verified decision must pass
`verify_same_payoff`, which requires verified/exhaustive state sets, a bijection
over outcomes and instruments, matching payout vectors, settlement currency/asset,
resolution fingerprint/authority, close and settlement times. The reviewer label
and external assertion ID are self-attributed references: the system does not
authenticate the identity or fetch/verify the assertion. The verifier evaluates
stored fields; it does not prove those fields are true beyond their source
provenance.

`verify_logical_implication` separately checks a directed binary YES implication
over an explicit bijection between two joint state spaces. It requires complete
verified payout vectors, binary complementary YES/NO settlements, verified
resolutions, two distinct source observation IDs, and a nonempty external
assertion ID that does not predate the source observations. Work is capped at
1,024 states and 128 characters per state ID; direction is included in the
relationship identity and recorded in evidence. Per-market settlement
denominations and times are preserved in the evidence and may differ; the
verifier does not bridge them. A `VERIFIED` result means the source YES payout
never exceeds the target YES payout over the provided mapping. The semantic
claim that both mappings describe the same world remains an unauthenticated
external assertion. It is available through the existing hash-checked
relationship-review API and append-only store. The bounded logical-implication
candidate family consumes these edges for two-venue binary markets by buying
NO(source) and YES(target). Candidate generation and the independent audit
require complete complementary Boolean payout vectors, a bijection over pinned
joint states, exact settlement asset identity, and matching market close and
settlement times that remain in the future at the replay cutoff. The external
assertion must also be present by that cutoff and cite both pinned market
observations. The worst mapped payout must cover at least one settlement unit
in every state. Positive results remain conditional because the semantic state
assertion is unauthenticated; distinct venue resolution authorities are not
independently reconciled. Unknown fees remain unknown, and stale or
insufficiently synchronized books make the candidate incomplete. Mission
Control now offers a self-attributed review form for this claim, with an explicit
YES direction and left-to-right state mapping. The form exposes the option only
when both stored markets advertise exhaustive verified binary payoffs,
verified resolution, and one YES/NO instrument each; the API verifier remains
authoritative and checks the submitted records. The assertion remains a
reference only, and reviewer identity is not authenticated.

Every review appends an immutable review record and a relationship revision in
one transaction. A compare-and-set against the latest review prevents stale
updates. API listings show only effective revisions, while the original and all
prior decisions remain stored. Replay uses only the latest decision, so a later
reject or ambiguous review removes an old verified revision from candidate
inputs without deleting history.

`GET /api/frontier/relationships/{id}/reviews` exposes the append-only review
lineage in newest-first pages of at most 50 records. A bounded keyset cursor is
bound to the relationship, timestamp, and review identity, so newly appended
reviews do not shift older pages. Each page rechecks record hashes and indexed
fields. The route rejects relationships that touch a source held from research
use before returning review evidence. Mission Control fetches this history only
when the user opens it, and labels reviewer names and assertion IDs as
self-attributed references.

Centered graph reads use separate left- and right-endpoint indexes, so a market
neighborhood is selected by its incident edges instead of scanning the global
recent-relationship window. The API bounds each traversal to 200 recorded
markets, three hops, 500 candidate relationship rows, and 200 returned edges per
page. It returns the number scanned and indicates when the result may be
incomplete. A centered one-hop neighborhood uses keyset continuation ordered by
relationship time and identity. Centered two- and three-hop neighborhoods now
also page in deterministic breadth-first order. Their small cursor pins the
center, depth, page size, and graph revision; each request recomputes the same
bounded result window, so no traversal state or database snapshot is persisted.
Wide BFS layers are split into indexed queries of at most 200 market IDs while
sharing the 500-row per-request scan budget. The graph revision includes recorded
`market_listing`, `instrument_metadata`, `market_metadata`, and
`event_market_listing` observations,
relationships, and reviews. The API checks it around each centered page and
returns 409 when any of those inputs change. Mission Control displays 30 edges
per page with previous/next controls. Uncentered text search can page through a
deterministic breadth-first result window. Its cursor binds the normalized
query, depth, page size, and graph revision; each continuation recomputes the
same bounded search and rejects a changed graph. Search seeds are drawn from at
most 200 recorded market records, and traversal reads at most 500 relationship
rows. Mission Control reports these bounds. This is not a full-universe search;
the unfiltered recent-edge view remains a single bounded read, and broad or
dense traversals can still be incomplete.

The economic verifier supports five narrowly bounded families. Cross-venue binary
coverage requires a previously verified same-payoff relationship. The
logical-implication family evaluates the long-only NO(source) plus YES(target)
construction over the pinned joint-state mapping and requires its worst
terminal payout to cover at least one unit. It is limited to two distinct
venues, verified binary terms, a shared settlement asset and quote currency,
matching close and settlement times, and complete timestamp evidence; it never
bridges denomination or timing differences. Any positive result is capped at
conditional because the external assertion that ties the state spaces to one
world is self-attributed and unauthenticated. Same-market multi-outcome
coverage requires three to sixteen verified exhaustive states, verified
resolution and settlement, and exactly one unit-payout one-hot instrument per
state; it buys all states long in one venue and one quantity unit. All families
check top-ask depth, quantity minimums and steps, exact quote denomination
identity on the instrument and book, fee-unit identity, applicable exact
Decimal fee formulas, scenario slippage/decay, local receipt skew, exchange-time
skew, and book age. The exact arithmetic uses bounded inputs (36 digits, 18
decimal places) and a 128-digit local Decimal context. Explicit quantities are
rejected if the common displayed depth or modeled fill fraction cannot support
them. A valid verified schedule or supported provenance-bound Kalshi estimate
can produce modeled net P&L; estimate-based results remain conditional. Unknown
or expired fees leave net P&L unknown and are excluded, rather than zeroed.
The within-market payoff-basket family searches at most 4,095 subsets from a
market with up to twelve instruments and three to sixteen exhaustive states. It
selects up to eight candidates by default (at most 32 for an explicit caller)
by quoted gross margin per common quantity. It accepts only nonnegative
verified payout vectors that sum to the same positive amount in every state.
Its independent audit recomputes each selected leg and the constant terminal
payout. The multi-market joint-state family accepts two to four open event
markets, at most twelve total instruments, and a content-hashed external map of
two to sixty-four asserted shared states. It searches at most 4,095 subsets and
retains only long baskets spanning every selected market with a constant
positive payout over each mapped state. Markets must share exact settlement
asset identity, payout currency, close time, and settlement time. Each leg keeps
its native quantity unit; no share-to-contract conversion is inferred. The
search caches exact mapped payout vectors and incrementally sums subsets in
ascending leg order. The independent audit verifies the basket arithmetic over
the pinned map but cannot prove the map's completeness, semantics, or
attainability, so positive results remain conditional. This is not a general
multi-market solver. Payoff-basket,
joint-state, and logical-implication results have controlled-fixture
verification only; current public observations do not satisfy their required
semantic evidence.
Cross-venue `timing_verified` additionally requires
matching known exchange timestamp semantics, no source/receipt/book timestamp
after the replay time, and observed exchange skew plus both declared clock
uncertainties within the configured limit. Missing clock uncertainty keeps
timing unverified. Current adapters do not populate clock-uncertainty estimates,
so current cross-venue observations cannot pass this timing gate. Candidates
always retain `practical_eligibility=false`:
public snapshots do not prove fills, queue priority, venue access, simultaneous
execution, capital transfer, or settlement. Opportunity classifications describe
the mathematical and modeled evidence only.

Economic model version 14 emits both a full-or-no-fill exposure sensitivity
and a bounded partial-fill grid for supported candidates with one to sixteen
legs. The full/no-fill calculation finds the exact adverse result across all
`2^n` patterns without materializing them. The partial-fill calculation samples
each leg independently at 0%, 25%, 50%, 75%, and 100% of modeled size, omitting
intermediate points that violate that instrument's quantity step. For each
terminal state, separability lets it select each leg's worst grid point in
`O(states × legs × grid points)` work rather than enumerating the Cartesian
product. It recalculates a source-supported fee at each nonzero aggregate
quantity. After-fee results stay unknown when any required fee is unknown.
Independent audit version 11 derives the quantity grid and fee amounts again
from pinned market, book, scenario, and fee evidence using separate code.

The partial-fill output is exact only over the declared grid. Each leg's
quantity is treated as one aggregate fill at its modeled best-ask purchase
price; the model does not estimate fill likelihood, queue position, continuous
fractions between grid points, multiple-fill rounding, price paths, deeper
book execution, post-fill hedge, or unwind recovery. Neither sensitivity is
an execution claim.

Replay version 13 pins the candidate sensitivities alongside an optional
per-venue delay addition and the shared base execution delay. Quote decay uses
the venue-specific delay to reprice each leg, and the independent audit derives
that price again from the candidate leg's venue. Delay values are bounded whole
milliseconds, the venue keys must be supported, and base plus venue addition is
capped at one hour. These are user-entered sensitivity inputs; they do not
assert an actual venue latency, order sequence, or fill response.
`fill_fraction` only caps usable displayed top-ask depth; partial-fill behavior
is handled only by the bounded grid described above.
Fee effective/expiry bounds and the age of provenance-bound fee estimates are
also checked at each leg's modeled venue execution time. If the pinned fee
evidence expires before that time, its fee remains unknown. This does not
predict future fee changes or certify a future venue schedule.

Fee evidence is source-specific and time-bounded. Polymarket schedules are
accepted only for an explicit enabled schedule with rate, taker-only scope, and
exponent 1; explicit disabled fees map to zero, while other shapes remain
unknown. The normalized fee fields are hashed and expire five minutes after
receipt. One October 26 public market listing verified a zero-rate schedule;
that observation is not generalized to other markets. Kalshi fee applicability
has an explicit public metadata resolver. Separate evidence-bound one-fill and
one-order quadratic taker sensitivities cover two documented fee types, with
order-level rounding accumulation and capped rebates. A later replay may derive
a conditional one-fill estimate from complete, hash-linked event/series rows;
account precision and non-taker costs remain unknown. Kraken's public pair feed
does not expose an account's applied tier; Frontier does not call the
authenticated account-volume API. Unknown venue costs remain unknown.

Replay then runs a separate arithmetic implementation that does not call the
candidate calculator's arithmetic helpers. It records `verified`, `disagreement`,
`incomplete`, or `not_evaluated`, the recomputed figures and a versioned SHA-256
over the candidate, normalized market/book inputs, relationships/mappings, and
scenario. Missing evidence or disagreement cannot retain a decisive candidate
classification. This independence is limited to calculation logic: the audit
shares the same normalized evidence and does not authenticate exchange truth,
resolution assertions, fee authority, source timing, or execution.

## Persistence and deterministic replay

The API uses a separate `MIDAS_FRONTIER_ROOT`. Raw source observations, normalized
records, relationship decisions/reviews, replay results, and paired comparisons
are append-only. SQLite schema v6 migrates older v2/v3/v4/v5 stores additively
and enforces update/delete triggers on evidence tables. The v5 migration adds
endpoint indexes without rewriting stored relationship rows; v6 adds an indexed
comparison table without changing earlier evidence. Review records link to their
derived relationship revision, and effective queries resolve the latest decision. Query methods use
SQLite read-only mode; they do not initialize or mutate the store. Listing reads
recheck raw body and normalized row hashes, relationship/review hashes and
revision linkage, and replay/comparison result digests. Write routes
enforce row and database byte budgets before committing. Repeated captures remain
distinct because their request and receipt timestamps form part of the evidence
identity.

When an HTTP 2xx JSON body is captured but cannot be normalized or the bounded
probe batch fails, the API stores the raw response with a versioned
`SourceFailureRecord` and returns its observation ID in the error details. The
normal market/book readers ignore that diagnostic record, while the normal
hash-verified observation route can retrieve it. Invalid JSON fails inside the
transport before normalization, but complete bounded invalid-JSON and non-2xx
response bodies are retained as source-failure observations. JSON nesting is
bounded to 64 container levels before decoding; excessive nesting or
integer-token length returns the non-retryable `JSON_COMPLEXITY_LIMIT` error
and retains the bounded response body as the same kind of diagnostic.
Delimiters inside JSON strings do not count toward this depth. Invalid UTF-8 is
stored losslessly as base64 with the hash computed over original bytes.
For a response rejected by the 256 KiB size bound, the API and finite
collector persist a metadata-only `source_failure` record: schema-v2 raw
observations mark `raw_body_state=not_captured_after_size_limit`, store an
empty raw body, and hash that empty stored body. The normalized schema-v2
`SourceFailureRecord` includes the response status through the raw observation
plus the configured limit, declared `Content-Length` when available, rejection
stage, and bytes yielded before rejection. The external response body is not
retained. Schema-v1 raw observations and source-failure records remain
readable. Other partial transport interruptions still have no complete source
body to persist. A later successful probe clears the adapter's degraded health
state.

Replay reads only stored inputs, sorts records by canonical IDs, pins source
observation IDs, effective state/instrument mappings, relationship IDs, proposal
limit, scenario assumptions, and a SHA-256 over the backend Frontier source set.
Re-running the same recorded inputs, implementation, and assumptions yields the
same result identity. Replay version 5 includes the independent per-candidate
arithmetic audit, exact full-or-no-fill candidate sensitivity, and hashes
effective mappings and the relationship-proposal limit into its normalized-input
digest. Replay time defaults to the latest
selected source receipt time; empty input uses a fixed epoch. No network adapter
is called from replay.

Paired replay compares exactly two named scenarios over the same selected and
hash-pinned local inputs. Its shared-evidence digest includes normalized markets,
books, relationships, effective mappings, code/replay versions, proposal limit,
and the pinned UTC replay time, while each arm separately hashes its scenario.
The API bounds paired runs to 100 markets, 200 books, 500 verified relationships,
and at most 500 proposed relationships. Both run records and the comparison are
committed atomically under the existing 512 KiB per-record and store byte caps.
The comparison summarizes matched constructions and classification/count
changes; it is not a score, fills report, or profit estimate. `POST
/api/frontier/replay/compare` performs no network calls, while `GET
/api/frontier/comparisons` and `GET /api/frontier/comparisons/{id}` return
hash-validated saved comparison records.

`POST /api/frontier/arena-replay` stages an immutable snapshot of at most 100
markets, 200 books, and 500 effective verified relationships under the configured
Arena root, pins the two scenarios and current Frontier source version, and then
submits a `frontier_replay` job through Arena's existing host-wide resource
admission path. A snapshot is limited to 8 MiB, the snapshot store to 128 MiB and
1,000 entries, and the result artifact to 8 MiB. The worker is capped at 300
seconds, 512 MiB, 50% CPU, nice 15, and idle I/O; IP address families are
disabled and the worker uses only local files. Submission does not probe an
exchange. `GET /api/arena/frontier-replays` returns a bounded history, and
`GET /api/arena/jobs/{id}/frontier-replay` exposes only a completed result after
checking the job's snapshot reference, artifact digest, comparison identity, and
success state. Mission Control displays progress, input snapshot ID/hash, result
hash, and the completed comparison. Job admission can be denied by the host
resource gate; snapshots remain pinned for a safe retry. Two controlled fixture
jobs have completed through systemd after ordinary host admission; this validates
supervisor and artifact wiring but not live market data. Frontier readiness
reports `NOT_CONFIGURED` without an Arena root,
`LIVE_VALIDATION_PENDING` until its bounded local scan finds a completed
hash-verified job plus runtime record, `EVIDENCE_RECORDED` after that check, and
`REVIEW_REQUIRED` if a completed record has invalid result/runtime evidence.
Mission Control exposes bounded worker elapsed time, process CPU deltas, and
process peak RSS when present. Resource sustainability remains `NOT_MEASURED`
because two bounded executions over the same fixture do not establish
sustainable capacity.

`timeline.py` adds an offline event-time engine for evidence containing multiple
observations of one instrument. It accepts at most 100 markets, 200 books, 100
verified relationships, 100 source-state events, 500 instrument identities, 128
evaluation frames, 32 MiB of normalized inputs, and a 16 MiB result. Each frame
uses only market and relationship evidence available by its UTC cutoff and the
latest book for each instrument that is still within the configured age. A
degraded or unavailable source excludes its books; after an interruption, a
newer successful book is required before that venue's quotes can re-enter a
frame. The engine records `unreported`, `fixture`, `scenario`, or `recorded`
source-state provenance, book selection/exclusion reasons, candidate
classification summaries, and deterministic replay/result hashes. It reuses
`deterministic_replay` and its independent economic audit for every frame. It
performs no adapter calls and writes no evidence itself.

`POST /api/frontier/arena-timeline-replay` snapshots at most 100 locally saved
markets, 200 joined books, 100 effective verified relationships, and 100
fixture/scenario or recorded source-state events. Recorded status must identify
a collector-checkpoint row hash. Before staging, the API reads the bounded
collection journal in read-only mode, validates the run-spec digest and the
complete per-run checkpoint chain, then requires the requested venue, checked
time, status, and canonical reason to match the checkpoint health record. Only
healthy, degraded, and explicitly unavailable states map to replay status;
not-probed and unsupported states do not imply venue availability. Held-source
events are rejected. The snapshot pins the joined checkpoint hashes in schema
version 2; existing schema-1 snapshots without recorded status remain readable.

`GET /api/frontier/collection-health-events` lists at most 20 recent,
timestamped source-health observations from the local collector journal. The
lookup is read-only, does not create a missing journal, filters held venues,
and validates each returned run's complete checkpoint chain. A timestamp-less
`not_probed` state is not an event and does not replace the latest timestamped
observation; a timestamped state that cannot map to availability does suppress
an older availability claim for that run. The response labels health as
adapter-local and reports `network_called: false`. Replay & Readiness fetches
this catalog only when opened. Every event starts unchecked; only an explicit
selection is submitted as recorded source-state evidence.

The request model rejects duplicate source-status timestamps for the same
venue before creating an Arena job, matching the deterministic timeline
engine's ambiguity rule. The UI disables another event with a venue/check-time
pair already selected; researchers can choose either checkpoint when separate
runs recorded the same timestamp.

`GET /api/frontier/collection-runs?limit=20` returns one read-only page of
hash-chain-verified collection checkpoints. `next_before_run_id` is the last
visible run ID only when another page exists; passing it as `before_run_id`
reads older rows by the journal's append order. Each page verifies its
cursor run's specification and full checkpoint chain before using the anchor,
then scans at most the journal's 1,000-run bound in 64-row batches while
filtering held venues. Newer appended runs do not shift an older page. The
Exchanges view exposes explicit older/newest page controls and returns to the
newest page after a collection start or resume.

The request also pins either ordered UTC evaluation times or the engine's
deterministic input-time/freshness-boundary schedule, maximum book age, scenario,
and code version. It makes no adapter request. The immutable snapshot is limited
to 32 MiB; its store is limited to 128 MiB and 1,000 files. The Arena worker runs
the existing deterministic replay and independent audit at each frame, under
the existing five-minute/512-MiB/half-CPU idle-I/O bounds. Its result is capped
at 16 MiB and bound to the job's snapshot and result hashes.
`GET /api/arena/frontier-timelines` lists bounded history, and
`GET /api/arena/jobs/{id}/frontier-timeline` validates a completed artifact.
Held-source filtering applies to the catalog, result route, and the Frontier
timeline readiness gate.

Mission Control's Replay & Readiness section can explicitly stage this job from
saved local evidence and inspect per-frame freshness counts, source-state
labels, candidate summaries, and input/result digests. Researchers can set the
maximum receipt age from 1 to 3,600,000 milliseconds; the control is disabled
for invalid values or until recorded markets exist. Scenario and fixture source
events remain distinct from measured source health. The integration and UI are
fixture-tested; no event-time Arena worker has been launched in this checkpoint,
so readiness remains `LIVE_VALIDATION_PENDING` until a future permitted bounded
local run has a verified artifact and runtime record. The UI callout explains
that recorded source states are adapter-local checkpoint health, not continuous
venue availability or account eligibility.

`discovery_comparison.py` compares three discovery-universe scopes over the
same pinned saved evidence: Polymarket-only, each venue independently, and all
venues together. Every arm calls the same deterministic replay and independent
economic audit; this measures coverage under the current engine, not a
comparison between independent algorithms. Candidate identity, classifications,
family counts, audit dispositions, source observation IDs, and pairwise deltas
are included in the versioned result. Cross-venue candidates require existing
verified relationships and mappings; text similarity or a user assertion alone
does not certify equivalence.

`POST /api/frontier/arena-discovery-comparison` stages up to 100 stored markets,
200 joined books, and 500 verified relationships into a content-addressed Arena
snapshot. The snapshot is capped at 8 MiB; its store is capped at 128 MiB and
1,000 files. Results are capped at 32 MiB and six unique replay artifacts, with
at most 20,000 candidate summaries per scope. The new `frontier_discovery` job
uses Arena's existing 300-second, 512-MiB, 50%-CPU, nice-15, idle-I/O and
host-admission limits. It performs no network requests. The history and result
routes verify the durable job configuration and artifact hashes and apply the
existing held-source quarantine. Fixture tests execute the artifact code
directly and exercise the API/UI path; no worker of this job kind has completed
through the Arena supervisor yet.

Before staging, the API scans at most the latest 200 saved book observations
and joins them to the selected market/instrument set. Since this is an
observation log rather than a one-row-per-instrument table, repeated snapshots
are collapsed by `(venue, native_market_id, native_instrument_id)` in the
store's newest-first local receipt order. The chosen book's immutable
observation ID remains in the content-addressed input. This avoids duplicate
instrument rows and makes the selection reproducible; it does not claim
exchange-time synchronization or prove the selected book is fresh.

The completed artifact exposes candidate detail from the replay IDs listed on
each scope arm. Mission Control resolves within those IDs and requires the
candidate identity, family, classification, audit disposition, and worst-case
gross/net values to agree with the arm summary before displaying a construction.
The browser shows at most 50 details per scope, retains exact decimal strings,
and includes leg-level observation IDs and independently audited terminal
outcomes. Missing or mismatched detail is surfaced as an artifact mismatch.
This inspection is read-only; it neither recalculates the opportunity nor
turns a fixture into live market evidence. The detail view explicitly labels
terminal values as hypothetical modeled P&L and says they do not establish
fills, venue access, or realized profit. The component and a fixture-backed
browser flow pass; supervisor execution of this job kind and a genuine public
cross-venue mapping remain unverified.

The finite collector is deliberately not exposed as a request handler or
background service. A caller must provide one configured adapter and one
Frontier store to `BoundedSourceCollector`; start rechecks source capability,
probe flags, and policy holds. One run is limited to 20 markets, 10 books, 20
book levels, 16 MiB of evidence, and 300 seconds. Checkpoints are append-only,
sequence- and previous-hash-linked, and capped separately from observation data.
The adapter is sequential within a source run, while per-source failures leave
other tasks eligible to complete. The journal supports a bounded read-only
lookup of up to 100 health-checkpoint digests per timeline request; it validates
each selected run's full chain and never initializes or creates a missing
journal. The journal's existence does not constitute a collector scheduler,
production worker, multi-source campaign, or live validation. The collector
code is fixture-tested and no source request was made.

## API and UI behavior

`GET /api/frontier/overview`, `/sources`, `/markets`, `/books`, `/trades`,
`/analytics/coverage`,
`/observations/{id}`, `/relationships`, `/relationships/{id}/reviews`, `/graph`, `/opportunities`, `/runs`, and `/readiness`
are local evidence reads. `POST /relationships/propose` writes deterministic
hypotheses; `POST /relationships/{id}/review` records an immutable explicit
decision; `POST /replay` writes a deterministic replay result; `POST /probe/{venue}`
is rejected unless that source is enabled. An explicit bounded probe may capture
one discovered listing page, one book, and up to ten public trades for the first
market. A separate explicit `POST /probe/polymarket/trades` captures exactly one
Data API v2 keyset page (at most 100 rows) for a condition already in the bounded
recorded listing window. Its local cursor binds that condition and page size;
each request repeats the same taker-only and 0.01-share filter, and no cursor
walk runs automatically. The [Polymarket Data API v2 docs](https://data-api.polymarket.com/v2/docs)
define condition-filtered history as a fixed three-year window, so this is not
full history. `GET /trades` returns
hash-verified normalized trades with their source observation and raw-body hash;
the v2 trade record preserves the native token ID and outcome fields alongside
the condition and transaction hash. Wallet profile fields from source rows are
not copied into normalized trades, while complete bounded raw responses remain
available as auditable source evidence. Kalshi uses a separate
`POST /probe/kalshi/trades` operation bound to a recorded ticker; block trades
remain included under the source default. Kraken does not advertise cursor-page
trades. The UI displays recorded trades as public
prints, not as available depth or executable prices. Probe errors include diagnostic
observation IDs when a captured response can be preserved. The generic market,
book and trade probe and the Polymarket v2 page route keep drained captures
pending until their normalized records are stored; lineage failures persist the
raw response with a failure record instead of discarding it. Earlier successful
captures are removed from the pending set so a later leg failure does not
duplicate them. The Frontier page does not inherit the single-venue
synthetic/demo banner. It shows source health separately from
captured evidence age, renders an interactive three-column SVG network for at
most 18 effective edges and a searchable evidence list capped at 30, supports
self-attributed reject/ambiguous/strict-verification reviews, exposes native
rules/fees/books, and keeps offline, unsupported, empty, and degraded states
visible. Candidate details show the separate audit disposition, recomputed cost,
fees, worst-state net result, and shortened evidence hash. Readiness summarizes
audit dispositions over at most the most recent three hash-validated replay runs;
it does not represent source truth or profitability.
Candidate details also offer a client-only virtual balance comparison for each
venue's modeled capital requirement. Each nonnegative decimal input remains in
browser component state and is compared exactly against the requirement in that
venue's exact canonical capital denomination. Missing or mixed identity
disables comparison; balances are keyed separately by venue and denomination,
so a token with ticker `USD` cannot reuse a fiat `USD` balance. An unknown
applicable fee prevents a claim that the modeled requirement is fully covered.
Inputs are not sent to the API or persisted. The view does not
model real account balances, collateral eligibility, transfer availability,
settlement duration, or capital at risk between settlements.

The separate virtual funding-currency sensitivity is an on-demand saved-run
API calculation. It accepts one explicit namespaced funding identity, balance,
target-per-funding-unit rate, and fee for each venue at
`POST /api/frontier/opportunities/funding-currency-sensitivity`. It reports
venue-local conversion fee, available target value, and shortfall under those
assumptions. Unlike the client-only same-denomination balance comparison, the
request is sent to the local Frontier API; it is still not persisted or sent to
an exchange. The independent Fraction audit and exact behavioral limits are
specified under [Virtual funding-currency sensitivity](#virtual-funding-currency-sensitivity).

Schema version 2 also returns `pnl_scenario`, a separate outcome-level
sensitivity. It is calculated only when the saved candidate's independent
economic audit is verified, every candidate leg has a modeled fee, the funding
conversion audit verifies, and each venue-local virtual balance covers that
venue's recorded capital requirement. The engine subtracts the modeled target
currency conversion fee from each independently audited terminal-state net P&L
and independently recomputes the results with rational arithmetic. An
unavailable or disagreeing scenario exposes no adjusted state values. This
scenario does not mutate the saved candidate, its P&L, classification, or
practical eligibility. It remains conditional on user assumptions and does not
establish a real conversion, transfer, or executable quote.

`GET /api/frontier/analytics/coverage` is a read-only no-network summary of
stored research. It considers at most 50 recent market records, 50 book
observations, 20 eligible replay runs, and 5,000 candidate records; separate
stored market/instrument identity counts come from indexed inventory. Held
source venues are filtered before both inventory and samples are summarized.
Book pricing requires hash-checked receipt lineage, a matching
market/instrument join, a two-sided uncrossed and unflagged book, and exact
quote-asset identity. Missing freshness limits stay unknown. Spread and top
depth are grouped by venue, market type, quantity unit, and denomination.
Repeated candidate constructions require a verified independent gross result,
verified timing, pinned market-evidence IDs and quote denominations, distinct
book sets, and distinct replay times. These counts describe the bounded saved
sample; they are not venue-wide coverage, independent opportunities, positive
net economics, or executable profit. The Coverage & quality tab loads on demand
and shows these interpretation limits.

## Known scope limits

There are no persistent source workers, incremental order-book streams,
venue-wide universe scans, sourced/live FX conversion, derivatives,
capital transfer model, a general cross-market solver beyond the bounded
explicit joint-state family, broad multi-leg search, automatic semantic
certification, authenticated reviewer or assertion verification, full-universe
graph search, Laboratory campaign integration, or production deployment. The
bounded replay and timeline Arena integrations have completed under the
supervisor after normal host admission. The new discovery-scope job's artifact
and API paths are fixture-tested, but its supervisor path and resource
sustainability remain unverified.
`/graph` limits source markets to 200, scans at most
500 relationship rows through endpoint indexes for centered neighborhoods, and
returns at most 200 edges per page over 1–3 hops. Centered one-hop queries use
keyset cursors; two- and three-hop queries page through deterministic
breadth-first result windows. All cursors bind the append-only graph revision.
The uncentered view remains a bounded recent-edge window. The current
replay/candidate set is small and bounded. See
the [engineering report](FRONTIER_ENGINEERING_REPORT.md) and
[mission ledger](FRONTIER_MISSION_LEDGER.md) for acceptance status and continuation
steps.

The saved price-history inspector also has an opt-in browser integration over a
temporary Frontier database seeded with deterministic, explicitly fixture-only
captures and replay artifacts. It drives the local API and Mission Control
views, including replay submission and page navigation; this verifies the
persisted UI/API contract without contacting a venue or changing the status of
live source validation.
