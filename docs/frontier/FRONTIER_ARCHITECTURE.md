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
| Candidate calculators | `economics.py` | Decimal cross-venue binary and same-market exhaustive multi-outcome all-long checks with fee, depth, freshness, timing, and scenario bounds. |
| Independent arithmetic audit | `independent_audit.py` | Separately recomputes supported candidate identities, payoff vectors, pinned quotes/depth, fees, costs, terminal P&L, and classification from replay inputs. |
| Durable evidence | `storage.py` | Append-only, size- and row-bounded SQLite observations, markets, relationship reviews/revisions, and runs. |
| Replay | `replay.py` | Stable input ordering, manifest and implementation digest, deterministic result identity. |
| HTTP API | `apps/api/frontier.py` | Bounded local queries and graph neighborhoods, relationship proposals/reviews, deterministic replay, and config-gated public capture. |
| Mission Control workspace | `apps/web/src/Frontier.tsx` | Sources, markets/books, relationship hypotheses, candidates, workbench, replay, readiness. |

## Adapter capability contract

Every venue declares support or an explicit unsupported reason for every
capability. An adapter may support public metadata, snapshots, trades, or candles
while rejecting incremental books, verified fee schedules, or settlement
semantics. The shared model retains native market and instrument identifiers,
native metadata, source URL, adapter/schema versions, raw-body hash, request and
receipt times, and source-time semantics. Source quality flags are carried forward
instead of being replaced with guessed values.

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
records, relationship decisions/reviews, and replay results are append-only.
SQLite schema v4 migrates older v2/v3 stores additively and enforces update/delete
triggers on evidence tables. Review records link to their derived relationship
revision, and effective queries resolve the latest decision. Query methods use
SQLite read-only mode; they do not initialize or mutate the store. Listing reads
recheck raw body and normalized row hashes, relationship/review hashes and
revision linkage, and replay result digests. Write routes
enforce row and database byte budgets before committing. Repeated captures remain
distinct because their request and receipt timestamps form part of the evidence
identity.

When an HTTP 2xx JSON body is captured but cannot be normalized or the bounded
probe batch fails, the API stores the raw response with a versioned
`SourceFailureRecord` and returns its observation ID in the error details. The
normal market/book readers ignore that diagnostic record, while the normal
hash-verified observation route can retrieve it. Invalid JSON fails inside the
transport before the adapter builds a raw observation, so its body is not yet
stored. A later successful probe clears the adapter's degraded health state.

Replay reads only stored inputs, sorts records by canonical IDs, pins the source
observation IDs and relationship IDs, hashes normalized input, persists scenario
assumptions, and records a SHA-256 over the backend Frontier source set. Re-running
the same recorded inputs, implementation, and assumptions yields the same result
identity. Replay version 3 includes the independent per-candidate arithmetic
audit and its pinned-input hash. Replay time defaults to the latest selected
source receipt time; empty input uses a fixed epoch. No network adapter is called
from replay.

## API and UI behavior

`GET /api/frontier/overview`, `/sources`, `/markets`, `/books`, `/trades`,
`/observations/{id}`, `/relationships`, `/graph`, `/opportunities`, `/runs`, and `/readiness`
are local evidence reads. `POST /relationships/propose` writes deterministic
hypotheses; `POST /relationships/{id}/review` records an immutable explicit
decision; `POST /replay` writes a deterministic replay result; `POST /probe/{venue}`
is rejected unless that source is enabled. An explicit bounded probe may capture
one discovered listing page, one book, and up to ten public trades for the first
market. `GET /trades` returns hash-verified normalized trades with their source
observation and raw-body hash. The UI displays recorded trades as public prints,
not as available depth or executable prices. Probe errors include diagnostic
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
assertion verification, indexed large-universe graph neighborhood search, or
production deployment. `/graph` limits source markets to 200, scans at most 500
effective relationships, and returns at most 200 edges over 1–3 hops. The current
replay/candidate set is small and bounded. See the [engineering report](FRONTIER_ENGINEERING_REPORT.md) and
[mission ledger](FRONTIER_MISSION_LEDGER.md) for acceptance status and continuation
steps.
