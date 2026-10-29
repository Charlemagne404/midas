# Exchange adapter documentation contract review — 2026-10-29

**Implementation status refreshed:** 2026-10-29 10:10 CET, after the bounded
Gemini recent-trade parser fixtures. The contract review remains
documentation-derived; the status refresh inspected local implementation and
fixture evidence only.

## Scope and method

This is a bounded review of current official API documentation against the
Frontier adapter declarations and selected normalization paths. It used
documentation pages and local source code only: no exchange endpoint was
queried, no retained probe was opened, and no source-use hold was changed.
Technical API documentation does not establish data-use permission, account
eligibility, regional access, or executable economics.

## Findings

| Source | Officially documented market-data contract | Frontier handling | Remaining boundary |
| --- | --- | --- | --- |
| Kalshi | The public market-orderbook endpoint returns binary YES and NO bids; the response example uses fixed-point decimal strings. The documentation describes an opposite-outcome bid at `1 - price` as the corresponding ask. | The adapter preserves exact decimal inputs, derives the opposite-side ask at `1 - price`, retains local receipt provenance, and explicitly marks the absence of one unified exchange book timestamp. | No incremental book reconstruction is implemented. Binary complement logic does not certify contract-resolution equivalence across markets. |
| Coinbase Exchange | The product-book endpoint's level 2 mode is the full aggregated book and includes `sequence` and `time`. During auction mode, quotes are indicative and can change before trading resumes. | Frontier requests level 2, preserves the raw response including sequence/time and auction fields, validates sequence/time presence, and adds `AUCTION_MODE_INDICATIVE` when the source reports an auction. Candidate evaluation records any book quality flag as a source-quality reason, and the independent audit will not validate a flagged book. | REST response time is not treated as cross-venue simultaneity. The adapter does not reconstruct the Coinbase WebSocket book. |
| Kraken Spot | REST order-book data is distinct from the documented WebSocket v2 `book` channel. The latter provides aggregated level 2 snapshots and updates, configurable depth, per-symbol acknowledgements, and a checksum; the documentation says updates must be processed in sequence. | Frontier uses bounded public REST depth, retains individual level timestamps, and does not claim a single snapshot timestamp. The finite stream adapter gates on an explicit acknowledgement and full snapshot, applies in-connection updates in arrival order, verifies CRC32, invalidates state on malformed or mismatched input, and retains raw protocol and book frames with provenance. Schema-v2 frames preserve the requested subscription depth. The bounded offline replayer rebuilds from persisted raw frames, verifies hashes and normalized state, and emits deterministic context-only results. The `BOOK_UPDATES` capability and config-gated capture API are implemented. | The replayer rejects legacy frames without an explicit recorded depth. Reconnecting must not silently bridge missing updates; no cross-connection continuity or exchange sequence guarantee is claimed. Capture and replay have fixture evidence only, not live-source validation. The existing source-use hold remains in force. |
| Gemini Spot | The public book reference specifies aggregated price levels and exact decimal-string prices and quantities; its per-level timestamp is a dummy compatibility field. The public trade endpoint returns a bounded recent page with native trade ID, exact decimal price/amount, execution timestamp, exchange, side, and optional broken-trade flag. | Frontier preserves exact book fields, ignores dummy timestamps, and flags source book time as unavailable. Adapter v2 supports one page of at most 100 trades after source-verified symbol details establish quote currency. It requires coherent timestamps, newest-first ordering, and valid native IDs/side/exchange; a page containing any broken print is rejected. Cursor pagination remains unsupported. Fixture contract tests pass 8/8. | Gemini remains under its non-clearable source-use hold. No live request or source-derived trade retention was performed; adapter capability and fixture evidence do not authorize data use. |
| Polymarket | The current public market-stream reference describes distinct `book`, `price_change`, `last_trade_price`, and `tick_size_change` events; book events may carry a hash and timestamp. Outcome identifiers differ by protocol, including CTF token IDs and Protocol V2 position IDs. | Frontier's finite legacy market-stream path binds capture to saved asset IDs, preserves raw frames and normalized observations, and does not apply deltas or claim sequence continuity. The worktree probe flag remains off. | Before any future capture, revalidate the legacy wire format against the exact supported protocol and market version. No capture or live compatibility claim is made by this review. |

## Engineering decisions

- The original documentation-only pass made no adapter code change. The later
  replay checkpoint adds an offline consumer of the persisted Kraken evidence;
  it does not change source-use policy or the live-adapter boundary.
- Keep REST snapshots, event-driven updates, and historical observations as
  separate declared capabilities; do not infer stream support from REST docs.
- Keep source time, local receipt time, sequence, and book validity distinct.
  A timestamp or sequence field alone does not prove cross-venue simultaneity.
- Kraken `BOOK_UPDATES` is now advertised because bounded transport, durable
  raw-frame provenance, and failure reporting are integrated. This capability
  declaration does not authorize requests or establish live validation.
- A live stream capture still requires a source-use decision and a fresh host
  admission check. A checksum-valid fixture is not live evidence.
- Stored-frame replay opens no source connection and refuses to infer missing
  subscription depth for legacy rows. Its deterministic reconstruction does
  not prove cross-connection continuity or event-contract economics.
- Keep Gemini live requests and source-derived trade retention blocked until
  the residency-specific agreement and intended use are reviewed and the API
  Use Form requirement is resolved. The parser was exercised only with
  isolated synthetic fixtures; it does not make Gemini observations eligible
  for research.

## Official references

- Kalshi: [Get Market Orderbook](https://docs.kalshi.com/api-reference/market/get-market-orderbook)
- Coinbase Exchange: [Get Product Book](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-book)
- Kraken Spot: [WebSocket v2 Book (Level 2)](https://docs.kraken.com/exchange/api-reference/spot-websocket-v2/book)
- Gemini: [Get Current Order Book](https://developer.gemini.com/trading/rest-api/market-data/get-current-order-book), [List Trades](https://developer.gemini.com/trading/rest-api/market-data/list-trades), [Market Data reference](https://developer.gemini.com/rest/market-data)
- Polymarket: [Real-Time Data](https://docs.polymarket.com/market-data/realtime-data)
