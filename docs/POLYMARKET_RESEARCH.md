# Polymarket integration research

Verified **2026-10-11**, against official documentation and unauthenticated public reads. Midas implements public prediction-market observation only. See [actual smoke output](LIVE_SMOKE_RESULT.json).

## Sources and findings

| Official source | Finding and implementation consequence |
| --- | --- |
| [Documentation home](https://docs.polymarket.com/) and [index](https://docs.polymarket.com/llms.txt) | Current docs recommend unified SDKs. Direct public HTTP and the market stream are sufficient for this read-only milestone. |
| [Market data overview](https://docs.polymarket.com/market-data/overview) | Events group markets; outcomes have separate trading identifiers. We store event and condition identity separately. |
| [Discovery](https://docs.polymarket.com/market-data/discover-markets) | Gamma provides filtered market/event listings and keyset routes. Midas uses the documented `/markets` listing, bounded to the most liquid configured active markets; it does not claim exhaustive discovery. |
| [Market details](https://docs.polymarket.com/market-data/market-details) | `version` selects the ID family. Constraints and market-specific fee schedules must be inspected. |
| [Prices and books](https://docs.polymarket.com/market-data/prices-order-books) | Public `GET https://clob.polymarket.com/book?token_id=<asset>` works for the selected outcome ID. The REST parameter remains named `token_id` for either protocol. Book arrays need sorting before walking asks. |
| [Realtime data](https://docs.polymarket.com/market-data/realtime-data) | Public market stream is `wss://ws-subscriptions-clob.polymarket.com/ws/market`. Subscription uses `type: market` and `assets_ids`. Send text `PING` every 10 seconds and expect text `PONG`. Dynamic operations are `subscribe` and `unsubscribe`. |
| [Fees](https://docs.polymarket.com/trading/fees) | Current taker curve is shares × rate × price × (1 − price). Fees use five decimal places. Categories differ; Midas never infers a market's rate from its category. |
| [Order precision](https://docs.polymarket.com/trading/place-orders) | Tick, share precision and amount precision are distinct. Midas models two-decimal virtual order sizes, rejects off-grid prices and bounds collateral rounding conservatively. It does not encode real orders. |
| [Positions](https://docs.polymarket.com/concepts/positions-tokens) | A complementary binary set has one unit of modeled collateral backing. Binary split resolutions exist, so modeling only a winner is not sufficient to describe every resolution. Midas tests a 0.5/0.5 payout vector too. |
| [Resolution](https://docs.polymarket.com/concepts/resolution) | Resolution and redemption are distinct operational dependencies. No immediate settlement, financing, oracle reliability, or collateral redemption guarantee is inferred from book prices. |
| [Negative risk](https://docs.polymarket.com/concepts/negative-risk) | Neg-risk conversions relate an event's full outcome set. Augmented sets can contain changing unnamed slots and Other semantics. Both are excluded from the binary evaluator. |
| [V2 API migration](https://docs.polymarket.com/migrate/polymarket-v2/api-integrations) | Strict `v1` → JSON-encoded `clobTokenIds`; `v2` → array `positionIds`. Both fields can coexist. Missing, malformed and unknown versions fail closed. |
| [Unified SDK migration](https://docs.polymarket.com/migrate/clob-sdk-to-unified-sdk) and [Python](https://docs.polymarket.com/getting-started/python) / [TypeScript](https://docs.polymarket.com/getting-started/typescript) | Supported unified clients include Python `polymarket` public clients and TS `@polymarket/client`. No secure SDK is installed. Using a small explicit GET allowlist avoids shipping live execution methods. |
| [Data API v2 migration](https://docs.polymarket.com/migrate/data-api-v1-to-v2) | v2 uses `/v2`, a `data` envelope, snake_case fields and opaque cursors. SDK support is documented from 0.10.0. v1 retirement is announced for 2026-10-24. Midas reads `/v2/status` only in the optional smoke utility; no wallet positions are fetched. |
| [Rate limits](https://docs.polymarket.com/api-reference/rate-limits) | Documented IP budgets include Gamma `/markets` 300/10s, CLOB `/book` 1,500/10s, and Data v2 general 800/10s. Midas deliberately paces all REST requests at ≤5/s, with three attempts and bounded 429/5xx backoff. |

## Protocol interpretation

CTF (`v1`) and Protocol V2 (`v2`) are different position ledgers with different identifiers. The order-domain protocol version is a separate concept from Gamma's market version. Midas implements neither signatures nor position operations. It recognizes both market versions and can observe both with the shared CLOB book interface. Fixture tests establish V2 ID selection even when token IDs are also present; real smoke reads encountered v1 only.

## Fees and verified opportunities

An explicit Gamma `feesEnabled: false` verifies a zero taker schedule for observation. Otherwise Midas requires `feesEnabled: true`, a nonnegative schedule rate, exponent exactly 1 and `takerOnly: true`. Other schedules are unknown or unsupported. Maker rebates, rewards and speculative rebates are excluded.

The current fee page describes five-decimal rounding but aggregate books do not reveal individual resting orders. Synthetic evaluation uses ceilings per slice plus a conservative reserve for possible 0.01-share match fragmentation. The simulator separately uses nearest five-decimal fees per simulated slice. This is a documented model, not a reproduction of all exchange rounding or fills. Live matching fragmentation remains unverified.

Gamma metadata alone is **not treated as a market-specific onchain payout proof**. Real markets currently receive `UNVERIFIED_PAYOUT` after the earlier data-integrity gates (or another earlier rejection). Payout verification is established for explicit synthetic scenario contracts only. This intentionally prevents unsupported live `VERIFIED_MATHEMATICAL` claims. A future attestation adapter must verify instrument/condition binding, payout backing and eligible resolution vectors before lifting this gate.

## Feed integrity and discrepancies

The documented market book/delta examples provide timestamps and state hashes but no dependable continuous sequence. A hash is not a sequence number and no hash reconstruction algorithm is assumed. Stream deltas reconstruct local levels but invalidate their executable trust; periodic REST snapshots restore observation trust. A stream snapshot retains known constraints and requests REST confirmation. Regression, identity mismatch, malformed data, disconnect, tick change and queue overflow trigger invalidation/resync. Same-timestamp ordering is not assumed recoverable.

REST snapshot reads are not atomic across instruments and websocket deltas can race with reads. No live evaluation is eligible for payout verification during this milestone. Snapshot age uses **both** source timestamp and local receipt age; an old unchanged source timestamp can conservatively exclude a recently retrieved book.

The general API page still lists the legacy live-data RTDS URL, while realtime/migration docs describe PolyBolt for external price feeds. Midas uses the market CLOB feed, which is the appropriate book source, and implements neither external feed. The generic fee prose refers to USDC while position documentation describes pUSD; live financial amounts are labeled **modeled pUSD**, with no assumed fiat conversion or redemption guarantee.

Some requested HTML pages were inaccessible through the browsing tool; their official `.md` equivalents were accessible and used. A urllib Gamma request initially returned 403, while curl and the implemented httpx client returned 200. This discrepancy is recorded; no access restriction workaround is part of the adapter.

## Verified against public data

Unauthenticated Gamma discovery, protocol-selected CLOB book retrieval, `/v2/status` envelope, public websocket book receipt and text PONG were exercised on the verification date. Recorded v1 Gamma and book responses are in `tests/fixtures`, explicitly labeled as real captured data and used without network in CI. No live V2 market, live price-change lifecycle campaign, rate-limit exhaustion or reconnect storm was empirically validated.
