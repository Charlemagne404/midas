# Project Frontier Mission Ledger

**Branch:** `codex/frontier-20261026`  
**Worktree:** `/home/charlie/midas-frontier`  
**Baseline:** `11d32a0693b25c290fd273f23e40cf7b5950d95d` (`codex/veritas-v6-integration-20261026`)  
**Started:** 2026-10-26  
**Mode:** read-only exchange research; no trading, credentials, wallet, deployment, or protected-service changes.

## Current stage

Stage A — baseline and isolation: **complete**.  
Stage B — adapter foundation and public integrations: **in progress**.

## Verified starting point

- The primary checkout `/home/charlie/midas` is on `main` at `55601b9` and contains unrelated modified and untracked work. It was not changed.
- The clean integration worktree `/home/charlie/midas-veritas-v6-integration-20261026` is on `codex/veritas-v6-integration-20261026` at `11d32a0`; that commit descends from the current `main` commit. It includes Veritas V6 and Research Readiness and is the isolated Frontier baseline.
- The supplied Reality, Veritas, V6 integration, and Reality reliability worktrees were checked. The Reality reliability worktree contains unrelated dirty operational/evidence state and was not changed.
- Running user services at inspection included `midas-api.service`, `midas-reality.service`, `midas-web.service`, `midas-reality-api.service`, `midas-reality-web.service`, and a transient Veritas market-coverage scope. No service was restarted or modified.
- At the bounded resource snapshot, `midas-api.service` used 1,480,568,832 / 1,610,612,736 bytes at `MemoryHigh` (about 124 MiB headroom). `midas-reality.service` used 1,202,798,592 / 1,207,959,552 bytes (about 4.9 MiB headroom). These are time-specific observations. Frontier will not start a service or sustained collector; test work will be isolated and serialized.

## Baseline architecture findings

- The existing core `Market`, `Instrument`, `Book`, and `Fee` contracts encode Polymarket CTF assumptions and lack general venue, settlement-asset, currency, and instrument-type fields.
- `packages/midas/market_data/polymarket.py` is the only current market-data adapter. It already has bounded public GET handling, Decimal wire parsing, and source-specific identity/fee checks.
- `packages/midas/market_data/ctf.py`, `packages/midas/economics/attestation.py`, and `packages/midas/arbitrage/engine.py` provide useful fail-closed Polymarket-specific checks. They will remain compatible; Frontier economics will be separate.
- `packages/midas/market_data/recording.py` is append-only but single-source and its replay path is tied to `BinaryStrategy`.
- The frontend is a React SPA in `apps/web/src/App.tsx`; `apps/api/main.py` includes routers; current CSS and React Query conventions support a native workspace. Frontier must not use the generic Polymarket/demo banner for multi-source state.
- The Veritas V6 reference, Readiness dashboard, Arena jobs, and Laboratory datasets are reusable research and provenance infrastructure. They do not establish cross-venue validation by themselves.

## Source investigation and live probe

Official references reviewed:

- [Kalshi market-data quick start](https://docs.kalshi.com/getting_started/quick_start_market_data)
- [Kalshi Get Markets](https://docs.kalshi.com/api-reference/market/get-markets)
- [Kalshi Get Market Orderbook](https://docs.kalshi.com/api-reference/market/get-market-orderbook)
- [Kalshi fee information](https://help.kalshi.com/en/articles/13823805-fees)
- [Kraken Get Order Book](https://docs.kraken.com/api-reference/market-data/get-order-book)
- [Kraken public trade data](https://docs.kraken.com/api/docs/rest-api/get-post-trade)
- [Polymarket market-data research guide](https://institute.polymarket.com/data)

At `2026-10-26T20:00:02Z`, bounded unauthenticated public-data probes returned HTTP 200 from Kalshi `GET /markets?limit=1&status=open` and one market's `/orderbook`, Kraken `AssetPairs` and `Depth`, and Polymarket Gamma `GET /events?limit=1&active=true&closed=false`. The first Kalshi order book response was only 51 bytes and contained no useful depth; this is endpoint-access evidence, not liquidity evidence. The Polymarket result titled “Kraken IPO by ___ ?” is not economically equivalent to Kraken spot. No credentials were sent. Full response bodies were not retained by that initial probe.

## Implementation plan

1. Define Frontier-specific versioned contracts, explicit capability declarations, source health, bounded public HTTP client, and adapter registry without weakening legacy Polymarket contracts.
2. Wrap Polymarket's existing public APIs; implement current Kalshi public event/market/order-book/trade support; implement Kraken spot public market metadata/books/trades as contextual non-event instruments. Preserve unsupported capabilities and unknown fees as unknown.
3. Add instrument/payoff models and fail-closed economic equivalence checks; add deterministic relationship proposals, reviewed/verified edges, and bounded persistence.
4. Add supported candidate families, independent Decimal outcome evaluation, multi-venue capital/cost assumptions, and explicit uncertainty classifications.
5. Add bounded multi-source observation capture and deterministic replay; integrate short fixture-based experiments with Laboratory/Arena without starting persistent workers.
6. Add isolated Frontier API and native Mission Control views for sources, instruments, relationships, candidates, replay, and readiness.
7. Add adversarial unit/contract/API/UI verification, measure bounded CPU/memory, preserve legacy regression behavior, write the final report, and create coherent local commits.

## Completion matrix

| Component | Status | Evidence / blocker |
| --- | --- | --- |
| Baseline audit and isolated worktree | COMPLETE AND VERIFIED | Clean baseline at `11d32a0`; dirty unrelated work preserved. |
| Adapter contracts and capability registry | DEFERRED | Not implemented yet. |
| Polymarket adapter | DEFERRED | Existing adapter audited; Frontier wrapper not implemented. |
| Kalshi adapter | PARTIALLY VERIFIED | Unauthenticated market/order-book probe returned 200; sampled book empty; normalization and contract tests pending. |
| Kraken spot adapter | PARTIALLY VERIFIED | Public AssetPairs/Depth probes returned 200; implementation and fee model pending. |
| Instrument/payoff and relationship graph | DEFERRED | Not implemented yet. |
| Opportunity verification/economic model | DEFERRED | Not implemented yet. |
| Provenance, storage, replay, Laboratory/Arena | DEFERRED | Not implemented yet. |
| Native Frontier interface/readiness | DEFERRED | Not implemented yet. |
| Regression, resource, scientific acceptance | DEFERRED | No tests run yet; production service/resource boundary is active. |

## Blockers and safety boundaries

- Reality is near its `MemoryHigh`; do not restart or attach Frontier collection to it.
- The API remains close enough to its soft memory boundary that full-suite, browser, or benchmark runs require care and must be serialized. Avoid changing any active service or shared data root.
- Exchange availability is not user eligibility. Jurisdiction and account access remain unresolved research metadata; no restriction will be bypassed.
- A public order book is a snapshot, not proof of simultaneous executable fills. The initial Kalshi book had no depth.
- Kraken spot cannot be matched to an event contract without a defensible payoff/hedge model. Kraken fees are not presumed verified by its public spot feed.

## Next safe action

Implement the isolated `packages/midas/frontier` core models, public adapter protocol, registry, and bounded HTTP transport; then add fixture-driven contract tests before any more network probes.
