# MIDAS Frontier architecture

Frontier adds a separate, read-only market-research path to MIDAS. Its contracts
live under `packages/midas/frontier`; the legacy Polymarket strategy, Reality
recorder, Veritas evidence, Arena artifacts, and Laboratory roots are not reused
as mutable Frontier storage.

## Components

| Component | Location | Responsibility |
| --- | --- | --- |
| Canonical contracts | `models.py` | Venue, instrument kind, payoff, resolution, fee, quantity, provenance, and book models. |
| Adapter protocol and lifecycle | `adapters/base.py` | Capability declarations, local health, response capture, and common read-only adapter contract. |
| Bounded HTTP transport | `adapters/transport.py` | HTTPS GET only, fixed host allowlist, bounded timeout/retry/rate/response sizes, no redirects or credentials. |
| Public venue adapters | `adapters/polymarket.py`, `kalshi.py`, `kraken.py` | Source-specific normalization and native metadata preservation. |
| Registry | `registry.py` | Explicit capability inventory; default instances do not probe. |
| Relationship intelligence | `relationships.py` | Deterministic indexed hypotheses, strict payoff checks, and immutable review contracts. |
| Candidate calculators | `economics.py` | Decimal cross-venue binary and same-market exhaustive multi-outcome all-long checks with fee, depth, freshness, timing, and scenario bounds; exact bounded one-sided fill sensitivity; separate Kalshi one-fill fee sensitivity. |
| Independent arithmetic audit | `independent_audit.py` | Separately recomputes supported candidate identities, payoff vectors, pinned quotes/depth, fees, costs, terminal P&L, fill-pattern sensitivity, and classification from replay inputs. |
| Durable evidence | `storage.py` | Append-only, size- and row-bounded SQLite observations, markets, relationship reviews/revisions, runs, and paired comparisons. |
| Replay | `replay.py` | Stable input ordering, scenario/mapping/proposal-limit-aware replay identities, deterministic results, and paired assumption comparisons. |
| HTTP API | `apps/api/frontier.py` | Bounded local queries and graph neighborhoods, relationship proposals/reviews, deterministic and paired replay, config-gated public capture, and evidence-bound Kalshi fee sensitivity. |
| Mission Control workspace | `apps/web/src/Frontier.tsx` | Sources, markets/books, relationship hypotheses, candidates, workbench, replay comparisons, and readiness. |

## Adapter capability contract

Every venue declares support or an explicit unsupported reason for every
capability. An adapter may support public metadata, snapshots, trades, or candles
while rejecting incremental books, verified fee schedules, or settlement
semantics. The shared model retains native market and instrument identifiers,
native metadata, source URL, adapter/schema versions, raw-body hash, request and
receipt times, and source-time semantics. Source quality flags are carried forward
instead of being replaced with guessed values.

Kalshi separately advertises `fee_metadata`: a deliberate one-event plus one-series
read captures the event override fields and series fee type/multiplier. The event
request excludes child markets to keep this metadata call bounded. This capability
does not populate `FeeSchedule`; native parameters remain stored with both raw
response hashes while candidate net economics remains unresolved.

The local `POST /api/frontier/economics/kalshi-fee-sensitivity` workbench calculation
uses only saved event/series evidence and manual price/quantity scenario inputs. It
supports the documented quadratic taker formula for `quadratic` and the captured
`quadratic_with_combo_maker_fees` type, and fails closed for other fee types. It
calculates a one-fill model fee rounded to a microdollar, then displays total debit
and fee under both documented balance quanta: `$0.0001` for a direct member and
`$0.01` for a non-direct member. Metadata IDs, raw hashes, received times, model
version, assumptions and a calculation digest accompany the result. This is a
standalone sensitivity, not an account quote and not an input to candidate net
economics; it omits multi-fill accumulation, rebates, FCM charges and later schedule
changes. The manually entered price is not represented as a public quote.

An offline derivation from the saved October 27 metadata capture produced a `$0.0175`
direct-member and `$0.02` non-direct-member fee scenario for one contract at a
manually supplied `$0.50`. Its input and output hashes are preserved in
`data/frontier/live-probes/2026-10-27-kalshi-fee-sensitivity.json`; it is not live
price evidence. The formula uses Kalshi's [July 7, 2026 event fee schedule](https://kalshi.com/docs/kalshi-fee-schedule.pdf)
and [fee rounding documentation](https://docs.kalshi.com/getting_started/fee_rounding).

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
payoff constraints. In particular, Kraken spot is contextual asset evidence; it
cannot become an event-contract payoff through matching text.

## Source configurations and bounds

The API creates all three adapter manifests, but the source transport is disabled
unless its specific `MIDAS_FRONTIER_*_PUBLIC_PROBE_ENABLED` setting is true. No
startup health request is made. A user-triggered capture makes one bounded market
page, plus at most one selected book snapshot. Kraken currently uses a configured pair allowlist,
not venue-wide enumeration. The transport caps each response at 256 KiB, retries
at most twice, has a 15-second maximum timeout, limits each adapter to 5 requests
per second, rejects redirects, and rejects hosts outside its venue allowlist.
The API serializes probes per venue and the store defaults to 64 MiB, 50,000 raw
observations, 100,000 relationship records, and 512 KiB per stored record.

## Relationship and economics boundaries

The matcher indexes exact venue-local event IDs and title terms. Cross-venue title
matches remain hypotheses and preserve evidence terms and source observation IDs.
They are never promoted automatically. The review API requires stored,
hash-verified source records for both markets. A verified decision must pass
`verify_same_payoff`, which requires verified/exhaustive state sets, a bijection
over outcomes and instruments, matching payout vectors, settlement currency/asset,
resolution fingerprint/authority, close and settlement times. The reviewer label
and external assertion ID are self-attributed references: the system does not
authenticate the identity or fetch/verify the assertion. The verifier evaluates
stored fields; it does not prove those fields are true beyond their source
provenance.

Every review appends an immutable review record and a relationship revision in
one transaction. A compare-and-set against the latest review prevents stale
updates. API listings show only effective revisions, while the original and all
prior decisions remain stored. Replay uses only the latest decision, so a later
reject or ambiguous review removes an old verified revision from candidate
inputs without deleting history.

Centered graph reads use separate left- and right-endpoint indexes, so a market
neighborhood is selected by its incident edges instead of scanning the global
recent-relationship window. The API still bounds each traversal to 200 recorded
markets, three hops, and 500 candidate relationship rows per request; it returns
the number scanned and indicates when the scan window may be incomplete. A
centered one-hop neighborhood supports keyset continuation ordered by
relationship time and identity. The cursor carries append-only market-observation,
relationship, and review counts; its market count covers recorded
`market_listing` and `instrument_metadata` observations used to render graph
nodes. The API returns 409 if those graph inputs change between pages. Mission
Control displays 30 edges per page, with a continuation control. Multi-hop
traversals and the uncentered overview remain single bounded reads; dense or
broad queries can still be incomplete.

The economic verifier supports two narrow families. Cross-venue binary coverage
requires a previously verified same-payoff relationship. Same-market
multi-outcome coverage requires three to sixteen verified exhaustive states,
verified resolution and settlement, and exactly one unit-payout one-hot
instrument per state; it buys all states long in one venue and one quantity
unit. Both check top-ask depth, quantity minimums and steps, quote currency,
applicable exact Decimal fee formulas, scenario slippage/decay, local receipt
skew, exchange-time skew, and book age. The exact arithmetic uses bounded inputs
(36 digits, 18 decimal places) and a 128-digit local Decimal context. Explicit
quantities are rejected if the common displayed depth or modeled fill fraction
cannot support them. Unknown or expired fees leave net P&L unknown and are
excluded, rather than zeroed. Other payoffs, implication constraints, and
general multi-leg constructions are unsupported. The multi-outcome family has
fixture verification only; current public observations do not satisfy its
attestation requirements. Candidates always retain `practical_eligibility=false`:
public snapshots do not prove fills, queue priority, venue access, simultaneous
execution, capital transfer, or settlement. Opportunity classifications describe
the mathematical and modeled evidence only.

Economic model version 4 adds a full-or-no-fill exposure sensitivity to each
supported candidate with one to sixteen legs. For each terminal state it
calculates each leg's payoff less its modeled acquisition cost and selects the
negative contributions; this gives the exact worst P&L across every one of the
`2^n` full/no-fill leg patterns without materializing the pattern set. It reports
pre-fee P&L and reports an after-fee result only when every leg has a modeled fee.
The saved pattern identifies filled and unfilled legs, with stable identities.
This is a terminal stress bound, not a probability, partial-fill model,
post-fill hedge, unwind, quote-recovery estimate, or prediction of execution.
Independent audit version 2 derives the leg payoff vectors and adverse patterns
again from the pinned market and book inputs using separate calculation code.

Fee evidence is source-specific and time-bounded. Polymarket schedules are
accepted only for an explicit enabled schedule with rate, taker-only scope, and
exponent 1; explicit disabled fees map to zero, while other shapes remain
unknown. The normalized fee fields are hashed and expire five minutes after
receipt. One October 26 public market listing verified a zero-rate schedule;
that observation is not generalized to other markets. Kalshi fee applicability
has an explicit public metadata resolver. A separate, evidence-bound one-fill
quadratic taker sensitivity exists for two documented fee types, but it does not
convert to an account fee or feed candidate economics. Kraken's public pair feed
does not expose an account's applied tier; Frontier does not call the authenticated
account-volume API. Unknown venue costs remain unknown.

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
response bodies are retained as source-failure observations. Invalid UTF-8 is
stored losslessly as base64 with the hash computed over original bytes. Oversized
or partial bodies are rejected without persistence. A later successful probe
clears the adapter's degraded health state.

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

## API and UI behavior

`GET /api/frontier/overview`, `/sources`, `/markets`, `/books`, `/trades`,
`/observations/{id}`, `/relationships`, `/graph`, `/opportunities`, `/runs`, and `/readiness`
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
observation IDs when a captured response can be preserved. The Frontier page does not inherit the
single-venue synthetic/demo banner. It shows source health separately from
captured evidence age, renders an interactive three-column SVG network for at
most 18 effective edges and a searchable evidence list capped at 30, supports
self-attributed reject/ambiguous/strict-verification reviews, exposes native
rules/fees/books, and keeps offline, unsupported, empty, and degraded states
visible. Candidate details show the separate audit disposition, recomputed cost,
fees, worst-state net result, and shortened evidence hash. Readiness summarizes
audit dispositions over at most the most recent three hash-validated replay runs;
it does not represent source truth or profitability.

## Known scope limits

There are no persistent source workers, incremental order-book streams, full
venue-wide universe scans, FX conversion, derivatives, capital transfer model,
multi-leg solver, automatic semantic certification, authenticated reviewer or
assertion verification, full-universe graph search, multi-hop graph pagination,
or production deployment. `/graph` limits source markets to 200, scans at most
500 relationship rows through endpoint indexes for centered neighborhoods, and
returns at most 200 edges over 1–3 hops. Centered one-hop queries can continue
by cursor while the append-only graph revision stays fixed; the uncentered view
remains a bounded recent-edge window. The current replay/candidate set is small
and bounded. See
the [engineering report](FRONTIER_ENGINEERING_REPORT.md) and
[mission ledger](FRONTIER_MISSION_LEDGER.md) for acceptance status and continuation
steps.
