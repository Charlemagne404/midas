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
   deterministic replay over pinned local inputs, including audit results and
   typed diagnostics for captured responses that fail normalization.
6. `apps/api/frontier.py`: bounded local reads, explicit proposal/replay writes,
   bounded graph-neighborhood queries, and separately configured public captures.
7. `apps/web/src/Frontier.tsx`: native Mission Control research workspace.

The three adapters are registered at API construction, but that action is
local-only. Network access is gated separately for each source. There is no
Frontier API key type, account endpoint, wallet, execution method, or order
submission route.

## 4. Exchange integrations and capability matrix

| Venue | Implemented public research | Preserved distinctions and limits | Live evidence |
| --- | --- | --- | --- |
| Polymarket | Gamma market discovery; CLOB books; legacy public trades; cursor-paginated Data API v2 trade pages; native token/condition/event IDs; strict market normalization and supported fee-shape handling | Event outcomes are not marked payoff-verified; settlement asset and resolution meaning are not independently attested; no incremental book stream or candle normalization; fee schedules expire after five minutes and unsupported exponents remain unknown; v2 condition history is fixed to three years and page capture uses taker-only trades with a 0.01-share floor | Earlier live API evidence persisted one listing, one book, and ten trades through the older trade path. A direct v2 first page and one continuation through the local API route each returned ten rows and were hash-verified via isolated stores; no third page was requested. A separate one-market listing captured a market-specific `zero_fees` schedule at 20:41:18.972060Z, with `feesEnabled=true`, exponent 1, taker-only, rate 0; normalized status was verified only through 20:46:18.972Z. |
| Kalshi | Public market discovery, market metadata, binary YES/NO instruments, public book snapshots and trades; retains native rules, status, timestamps and market fields | MVE metadata is classified as conditional; asks derived from complementary YES/NO bids where applicable. Fee applicability is unknown in adapter v1. No stream or historical-candle normalization. | Bounded live API capture persisted one listing, an empty book, and a valid empty trade response. The book had no unified exchange snapshot timestamp. |
| Kraken Spot | Configured-pair AssetPairs metadata; public depth, trades and OHLC; pair tick/lot/minimum fields retained | Spot is a base/quote instrument, not an event payoff. Fee tier, account eligibility, custody, and event hedge semantics are unknown. Pair discovery is an explicit allowlist. | Bounded live API capture persisted XBT/USD metadata, depth with 10 asks/10 bids and per-level timestamps, and ten trades. No prediction-contract equivalence was found. |

Each adapter declares every shared capability as supported or unsupported with a
reason. Kalshi documents unauthenticated public market-data access and its
binary order book returns YES/NO bids, with complementary prices used to infer
the other side; Frontier retains that source-specific rule rather than treating
the returned arrays as generic asks ([Kalshi public market-data guide](https://docs.kalshi.com/getting_started/quick_start_market_data),
[Kalshi order-book specification](https://docs.kalshi.com/api-reference/market/get-market-orderbook)).
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

Kalshi's public series metadata exposes `fee_type` and `fee_multiplier`, but the
adapter does not yet resolve those fields through the effective market/series
fee schedule; its fee remains unknown ([Get Series](https://docs.kalshi.com/api-reference/market/get-series),
[published fee schedule](https://kalshi.com/fee-schedule)). Kraken's public
pair data does not establish the account's current fee tier. Its trade-volume
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
`INCOMPLETE_EVIDENCE`. Replay version 3 includes this audit in its deterministic
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
failure probabilities. Scenario outcomes are virtual assumptions. Every candidate has
`hypothetical=true` and `practical_eligibility=false`; a public quote comparison
is never called executable profit.

## 9. Storage, replay, and provenance

Frontier stores data under its own configurable root, default
`data/frontier-store`. SQLite schema v5 defaults to a 64 MiB cap, 50,000
observations, 100,000 relationship records, and 512 KiB per record. An additive
migration upgrades v2/v3/v4 stores with relationship revision, review, and
left/right endpoint indexes without rewriting existing relationship payloads.
Append-only triggers reject row updates/deletes on observations, indexes,
relationships, review records, and runs. Relationship review and its derived
state revision are inserted in one bounded transaction. Effective queries and
replay select the last compare-and-set review revision while the earlier record
history remains immutable. Query methods open read-only connections.
Observation and relationship list reads verify content hashes and indexed fields
before returning records. They also validate the current review-to-revision
link; replay reads recompute the pinned output digest. Offline tamper tests cover
observation, relationship, and replay list paths.

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
called from replay. Replay version 3 includes each candidate's independent audit
disposition and its input hash. The store has no compaction/retention worker; once the cap is
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

No new long-running campaign or background worker was launched. The Frontier
workspace links into the existing Laboratory and Arena pages, but Frontier
replay is not registered as an Arena/Laboratory experiment type and there is no
new resource-aware research scheduler, paired-comparison runner, or durable
campaign manager. This acceptance establishes deterministic local replay through
Frontier’s own API and test fixtures only.

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
the source advertises the capability and its explicit probe flag is enabled. The
condition selector uses only markets in saved listing evidence; each click
requests one page and the UI shows its observation/raw hashes and request bound.
The API
graph query is bounded to 200 source markets, 500 scanned relationship rows per
request, and 1–3 hops; centered one-hop traversal uses left/right endpoint
indexes and revision-bound cursors, and the visual network caps at 18 edges.
Reviewer authentication, external assertion retrieval, multi-hop
pagination/clustering, and experiment result drill-downs remain incomplete.
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
- Live v2 source checks: one unauthenticated direct first-page GET and one continuation GET invoked through `POST /api/frontier/probe/polymarket/trades`; each made one request without retries, returned HTTP 200 and ten trades, and had raw plus normalized temporary-store read-back hashes pinned. Their 20 native trade IDs are distinct. No third page was requested.

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

Kalshi fee schedules are not resolved to a verified market-specific formula in
adapter v1; Kraken account-tier fees are not known from the public spot capture;
and Polymarket fee semantics remain constrained to the strict exponent-1
normalizer and five-minute market metadata expiry. Cross-venue FX, collateral denomination,
transfer/withdrawal cost, account funding allocation, capital duration,
jurisdiction, custody, and settlement access are unmodeled. Public depth is a
time-stamped displayed snapshot, not a fill guarantee. In this evidence set,
cost-adjusted discrepancies and executable opportunities are therefore
unestablished.

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
- No Laboratory/Arena scheduling integration, paired experiments, full
  repository Python suite, or browser suite outside the existing 10 E2E cases
  was run.

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
3. Resolve Kalshi series-specific fees against the effective schedule. Keep
   Kraken account fee tier unknown without authenticated data; no candidate may
   use unknown or expired fees as zero.
4. Seek real public multi-outcome metadata that meets the strict payoff and
   resolution requirements; broaden accepted payoff families only with
   independently checked evidence.
5. Add deterministic multi-source replay datasets and paired resource-aware
   Laboratory/Arena jobs with explicit caps and no unattended campaigns.
6. Only after representative evidence, consider authenticated reviewer identity
   and independent external assertion ingestion; this needs a separately
   designed security boundary.
7. Only after representative evidence, consider FX, capital allocation,
   settlement/transfer, and instrument hedge models.

## 19. Exact files and commits changed

Code commits on this branch:

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

Principal changed paths:

- `packages/midas/frontier/{models.py,registry.py,relationships.py,economics.py,independent_audit.py,storage.py,replay.py}`
- `packages/midas/frontier/adapters/{base.py,normalization.py,transport.py,polymarket.py,kalshi.py,kraken.py}`
- `apps/api/{config.py,main.py,frontier.py}`
- `apps/web/src/{App.tsx,Frontier.tsx,Frontier.test.tsx,frontier.css}` and
  `apps/web/e2e/frontier.spec.ts`
- `tests/frontier/*`, `tests/integration/test_api.py`
- `data/frontier/live-probes/*`
- `.env.example`, `README.md`, `docs/ARCHITECTURE.md`, `docs/DEVELOPMENT.md`,
  and `docs/frontier/*`

The documentation commit identity is recorded by the final mission-ledger
checkpoint that commits this report.

## 20. Final status and continuation instructions

Frontier’s isolated engine/API/UI foundation is **implemented and boundedly
verified**. The mission as a whole is **not complete**. It remains unmerged,
undeployed, without ongoing collection, and without genuine verified
cross-venue economics.

| Major component | Status | Evidence and limit |
| --- | --- | --- |
| Isolated baseline/worktree and preserved unrelated changes | COMPLETE AND VERIFIED | Branch starts at verified V6 commit; original dirty worktrees untouched. |
| Adapter protocol, capability registry, bounded GET transport | COMPLETE AND VERIFIED | Contract tests, all capability declarations, host/size/rate/redirect bounds. |
| Polymarket, Kalshi and Kraken Spot adapters | PARTIALLY VERIFIED | Fixture/contract tests and one live listing/book/legacy-trade API round trip per venue pass. A direct Polymarket v2 first page and one continuation page through the local API route each returned ten rows and were hash-verified via temporary storage; no third page was requested. Polymarket fee evidence is narrow; Kalshi series and Kraken account fee applicability remain unknown. Mock tests cover invalid JSON/UTF-8, HTTP 503, timeout, truncated streams, schema-failure evidence, capped retries, source isolation, and recovery; live degraded-source behavior remains unverified. |
| Canonical market/instrument normalization | PARTIALLY VERIFIED | Three distinct instrument classes are represented; v2 Polymarket trades retain native outcome-token identity. Live lineage and several payoff/settlement semantics remain unverified. |
| Relationship hypotheses, review revisions, indexed neighborhoods, and explicit same-payoff verifier | PARTIALLY VERIFIED | Self-attributed review API/UI, append-only revisions, latest-state replay, tamper/migration checks, left/right endpoint-indexed 1–3 hop scans capped at 500 rows, revision-bound centered one-hop keyset pages, stale-cursor rejection, and a 501-edge scan-bound test; no genuine equivalent pair, reviewer authentication, or multi-hop pagination. |
| Opportunity candidate and independent economic checks | PARTIALLY VERIFIED | Two-venue all-long binary and same-market 3–16 state one-hot exhaustive coverage, with a separate pinned-input arithmetic audit; controlled fixtures only, with source semantics, fees, broader costs and operational feasibility incomplete. |
| Append-only evidence store and deterministic replay | COMPLETE AND VERIFIED | Schema v5, v2/v3/v4 additive migration, bounds, hash validation, immutability, replay tests; not integrated as an Arena campaign. |
| Live market/book/trade observations through adapters and API | PARTIALLY VERIFIED | One bounded listing, book, and legacy trade response per venue is hash-pinned; a v2 Polymarket first page and API-route continuation page were hash-pinned via isolated-store read-back, with distinct trade IDs. Samples are not synchronized and do not establish continuous feed coverage or a third page. Kalshi's legacy trade array was valid but empty. |
| Source workers and broad historical data | DEFERRED | No persistent worker or long-duration collection. |
| Laboratory/Arena research orchestration | DEFERRED | Workspace navigation and deterministic Frontier replay only. |
| Native Mission Control workspace | PARTIALLY VERIFIED | Local API, bounded graph/review UI, and source/capability-gated explicit Polymarket first/next trade-page controls; unit and desktop/mobile E2E use fixtures. Production deployment and live browser-to-source validation are not done. |
| Production readiness/deployment | DEFERRED | Separate review and authorization required; production eligibility is false. |
| Positive economic result | NOT ESTABLISHED | No genuine cross-venue equivalent or economically eligible result in captured evidence. |

To continue safely, use this worktree and branch. Next broaden API-boundary
degraded-source behavior; resolve Kalshi series fee applicability without
guessing; search for public multi-outcome metadata that
meets the strict payoff and resolution evidence requirements without loosening
attestation; extend bounded graph paging to multi-hop only if traversal order can
remain reproducible; then connect short, resource-admitted deterministic jobs
to Laboratory/Arena. Add
adversarial mutations and differential audit fixtures only where they test a
distinct failure mode. Expand economics only where source evidence supports it.
Re-run the focused suites before each checkpoint. Do not enable probes by default,
deploy, modify Reality, or start a long-running campaign as part of routine
continuation.
