# MIDAS Frontier — Final Handoff

**Cut:** 2026-10-29 22:58 CET

**Development worktree:** `/home/charlie/midas-frontier`

**Branch:** `codex/frontier-20261026`
**Latest implementation checkpoint:** `b0ed1372ab7c0ce05133808d029393423d99c52f`

## Executive summary

Frontier has delivered a substantial, research-only expansion of MIDAS. It
adds a shared adapter and provenance layer for five public market-data venues,
canonical market and payoff models, an evidence-backed relationship graph,
candidate opportunity analysis with an independent Decimal audit, bounded
storage and replay, Arena/Laboratory hooks, and a native Mission Control
workspace.

This is a usable development implementation, not a production-ready or
economically validated trading system. Polymarket is the only venue with a
bounded saved public market/book observation described in the evidence. The
other venue adapters are implemented and fixture-tested but remain held from
current live collection or research under the documented data-use gates.
There is no verified live cross-venue economic relationship or eligible
opportunity, and no profitability claim.

## What Frontier adds to MIDAS

- A venue-neutral adapter protocol, capability registry, bounded anonymous
  read-only transports, explicit source holds, normalization, health state,
  and source-specific errors.
- Canonical markets, instruments, outcomes, payoff and settlement terms,
  native trading units, fee evidence, book depth, and source provenance.
- A persisted relationship graph that distinguishes hypotheses from reviewed
  or mathematically checked relationships and retains evidence references.
- Candidate research for supported binary, exhaustive-outcome, implication,
  and bounded joint-state combinations. An independent audit recomputes the
  supported arithmetic and pinned evidence.
- Virtual fee, FX, venue-separated capital, carry, and execution-sensitivity
  models. These retain unknown assumptions instead of filling them with
  invented values.
- Hash-pinned storage, deterministic replay, bounded collection and source
  admission, and finite Arena/Laboratory comparisons.
- A native Frontier workspace for source and coverage inspection, graph
  neighborhoods, opportunity review, replay, and readiness.

All functionality remains research-only. There is no authenticated trading,
order submission, wallet, deposit, or withdrawal path.

## Exchange integrations and evidence

| Source | Implemented capability | Evidence and current boundary |
| --- | --- | --- |
| Polymarket | Market/event metadata, public books, bounded historical data, finite market-stream capture, and deterministic stored-frame replay. | Adapter and replay tests pass. A small bounded Gamma listing and CLOB book observation is preserved from 2026-10-28 at `data/frontier-public-probes/polymarket-bounded-20261028T0852-r2Z/`. It is one market, not a live feed or cross-venue proof. Current probing is off; stream continuity and executable economics are unverified. |
| Kalshi | Read-only prediction-market metadata, book/trade mapping, fee modeling, and cursor-aware contracts. | Fixture-tested. Dated public metadata artifacts exist, but the current source gate quarantines them; no current live validation or usable cross-venue comparison is claimed. Written research/retention authorization remains unresolved. |
| Kraken Spot | Read-only spot metadata, books, trades, OHLC, bounded WebSocket v2 books, and replay. | Fixture-tested, including CRC reconstruction and replay constraints. Source-use review keeps new capture and stored-data use held. Spot prices are context, not prediction-contract payoffs. |
| Coinbase Exchange Spot | Read-only spot market-data adapter and normalization. | Fixture-tested only. Source-use hold and data quarantine remain; no live request was made in finalization. |
| Gemini Spot | Bounded symbol metadata and recent-trade parsing with source precision retained. | Fixture-tested only. API-form, applicable agreement, and intended-use review remain open; no live request was made. |

The Polymarket observation is genuine public source evidence, but its limited
scope does not establish venue-wide coverage, a synchronized or complete book,
or an executable trade. Kalshi has dated public metadata artifacts that are
currently quarantined. All cross-venue opportunity demonstrations are
explicitly labeled fixtures. No live cross-venue equivalence was certified.

## Core research systems

The canonical model supports selected binary and multi-outcome event
contracts plus spot context. It preserves native identifiers and source
semantics and rejects unsupported payoff structures. Decimal arithmetic is
used for the supported monetary calculations. A shared schema accepting an
instrument type does not imply complete economic support for that type.

Relationship discovery combines exact identifiers, structured event and
outcome metadata, bounded deterministic text matching, and explicit review.
Text similarity alone cannot certify equivalence. The graph supports bounded
neighborhood queries and pinned revisions. Relationship assertions remain
separate from their evidence and from the audit that decides whether a
supported payoff comparison is valid.

The opportunity engine covers a bounded subset of cross-venue discrepancies,
complementary and exhaustive outcome constructions, logical implications, and
joint-state baskets. Independent verification checks supported payoff
coverage, positions, quantity and depth constraints, fees, settlement units,
and terminal outcomes. FX, capital, carry, and fill behavior are scenario
assumptions. Public snapshots do not prove simultaneity, fills, transferability,
or profit after unmodeled costs.

Polymarket event replay is snapshot-anchored and explicitly context-only. It
retains reported standalone best-bid/ask events for cross-checking but does
not treat them as depth changes. It has no sequence or gap-recovery proof.
The Kraken book replay also refuses unsupported reconstruction. Saved evidence
is hash-bound and revalidated at research boundaries.

## Dashboard and research workflows

The native dashboard is integrated into MIDAS Mission Control rather than a
standalone mock. It includes source status and capabilities, coverage, graph
neighborhoods and evidence, opportunity details, saved replay, and readiness.
It can be run from this development branch against its API and local research
store. It has not been deployed to the protected MIDAS service.

The final focused three-frame Mission Control journey passed **1/1** at 22:36
with eight unrelated cases skipped. `tsc -b` passed at 22:36 under a 1 GiB,
zero-swap cap. The final Vite production bundle passed in 1m05s under a 1 GiB,
zero-swap, 20%-CPU scope. Vite still warns that the Chart chunk is 544.51 kB,
above its 500 kB advisory threshold. That size optimization is deferred.

## Verification performed

- `tests/frontier/test_polymarket_stream.py`: **24/24 passed** in 9.60 seconds
  under `MemoryHigh=384M`, `MemoryMax=512M`, zero swap, 15% CPU, and
  `TasksMax=64`. This includes the final parser fix: both documented best-price
  spellings are accepted and conflicting aliases are rejected. The suite emits
  the existing Starlette/httpx `TestClient` deprecation warning.
- Ruff check and Ruff format check passed for the changed adapter and test.
- Vite production bundling passed; the bounded TypeScript project check had
  already passed on the same frontend tree.
- The latest engineering evidence also records selected current-tree checks:
  four economics modules **79/79**, joint-state audit/replay **14/14**,
  logical relationship review **27/27**, transport **20/20**, and storage
  **37/37**. These are scoped fixture results, not a full-suite result.
- The focused graph, source, collection, replay, and readiness UI/API tests in
  the engineering report remain their recorded bounded results. The full
  Frontier suite, full MIDAS regression, full browser suite, and endurance
  campaign were not rerun during finalization.

The first finalization test command used a transient service without an
explicit working directory and collected no tests. It used negligible
resources; the corrected command above ran the full focused module. No test
read the preserved public-probe directory or any protected research store.

## Completion matrix

| Component | Status | Qualification |
| --- | --- | --- |
| Adapter protocol, capability registry, anonymous read-only transport | COMPLETE AND VERIFIED | Contract, bounds, and transport-safety fixtures pass. |
| Polymarket adapter and stored replay | IMPLEMENTED, VERIFICATION PENDING | One bounded public listing/book artifact exists; current live capture, stream continuity, and economic eligibility are unverified. |
| Kalshi adapter | IMPLEMENTED, VERIFICATION PENDING | Fixture contracts pass; current source-use gate quarantines saved records and blocks live validation. |
| Kraken Spot adapter and replay | IMPLEMENTED, VERIFICATION PENDING | Fixture tests pass; source-use gate blocks current capture and research use. |
| Coinbase and Gemini Spot adapters | PARTIALLY IMPLEMENTED | Parser and normalization fixtures exist; source-use/API-form requirements remain unresolved. |
| Canonical instruments and payoff semantics | PARTIALLY IMPLEMENTED | Supported categories are modeled; unsupported and venue-specific economics fail closed or remain unknown. |
| Relationship graph and review | PARTIALLY IMPLEMENTED | Deterministic hypotheses, provenance, review, and supported mathematical checks work on fixtures; no live cross-venue equivalence is verified. |
| Candidate generation and independent economic audit | PARTIALLY IMPLEMENTED | Supported fixture opportunities are independently recomputed; no live eligible opportunity is demonstrated. |
| Storage, provenance, replay, and bounded source admission | PARTIALLY IMPLEMENTED | Selected storage/replay contracts pass; multi-venue live capture and archive provenance are open. |
| Arena/Laboratory comparisons | PARTIALLY IMPLEMENTED | Bounded orchestration and selected comparisons work; endurance and broad comparative acceptance remain pending. |
| Native Frontier dashboard | IMPLEMENTED, VERIFICATION PENDING | Production bundle, typecheck, and focused journeys pass; broad integration and production API validation are pending. |
| Read-only and no-trading boundary | COMPLETE AND VERIFIED | No account/order/wallet path is implemented in the reviewed Frontier code. |
| Live multi-venue economic research | BLOCKED | Source-use and permission gates prevent safe current collection and validation. |
| Production deployment | BLOCKED | Not deployed or authorized; host recovery, source permissions, and broader release validation are incomplete. |

## Operational and scientific limits

The [separate 2026-10-29 host incident report](FRONTIER_MEMORY_PRESSURE_INCIDENT_2026-10-29.md)
remains **PARTIALLY CONTAINED / PARTIALLY VERIFIED**, not resolved. At 22:58,
host memory PSI was zero and
about 10 GiB was available, but all 4 GiB of swap remained occupied. The
scheduled capacity monitor succeeded under its 160/192 MiB, zero-swap limits;
the gap-detail timer remains disabled. API, Reality, and Reality API were
active at restart counts 9/14/0, with no OOMD or kernel kill observed since
22:41. This short quiet interval does not establish durable recovery or
historical workload attribution. The separate archive-manifest and provenance
warnings remain untouched.

Do not interpret fixture arbitrage, public quote differences, price
correlation, spot context, or a successful independent calculation as
realizable profit. Jurisdiction, venue access, custody, account-specific fees,
capital transfer, settlement timing, cross-source clock quality, complete
books, and one-sided execution risk remain unresolved. No result in this
handoff demonstrates positive economic returns.

## Repository state and next steps

The branch is isolated and local; no merge, push, deployment, protected
service change, or production-store write occurred. The incident checkpoint
tag `checkpoint/frontier-pre-host-memory-incident-20261029-2054` remains
available. The pre-existing untracked
`data/frontier-public-probes/` directory was left untouched and is not part of
the commits.

Primary implementation locations are `packages/midas/frontier/` (canonical
models, adapters, economics, relationships, provenance, storage, replay, and
analytics), `apps/api/frontier.py` (research API), `apps/web/src/Frontier.tsx`
and `frontier.css` (native workspace), `tests/frontier/`, and
`apps/web/e2e/frontier*.spec.ts`. The detailed architecture and chronological
evidence remain in `FRONTIER_ARCHITECTURE.md`,
`FRONTIER_ENGINEERING_REPORT.md`, and `FRONTIER_MISSION_LEDGER.md`.

Recent implementation checkpoints include `c1ad426` (standalone Polymarket
BBO replay and dashboard evidence) and `b0ed137` (conflicting best-price alias
rejection). The final documentation commit records this handoff and the final
incident/ledger snapshots.

Before any future deployment or live multi-venue research, prioritize:

1. Resolve sustained host memory/swap risk and verify OOMD monitoring and
   workload attribution over a longer, safe observation window.
2. Complete source-specific jurisdiction, intended-use, and permission review
   and add a validated authorization mechanism before releasing held sources.
3. Run a bounded release-level integration and browser regression only after
   the host gate permits it; then review a separate deployment change.

No further Frontier feature work or campaign is part of this handoff.
