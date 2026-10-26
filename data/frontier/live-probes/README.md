# Bounded public-source probe captures

These files contain genuine public HTTP responses captured by MIDAS Frontier on
2026-10-26. Requests were unauthenticated `GET` requests with a short timeout
and per-response byte cap. No orders, accounts, credentials, wallet calls, or
mutating methods were used. Raw response bodies are retained so normalization
can be replayed; each capture contains a SHA-256 over its pre-hash manifest.

| Capture | Evidence |
| --- | --- |
| `2026-10-26-public-source-probe.json` | Kalshi market listing, Kraken pair metadata and depth, and Polymarket Gamma event listing; all returned HTTP 200. |
| `2026-10-26-public-source-probe-r2.json` | The same bounded source responses plus the sampled Kalshi market's public order book. The book was empty (`yes_dollars=[]`, `no_dollars=[]`). |
| `2026-10-26-frontier-api-live-validation.json` | One live listing request through each Frontier adapter and `/api/frontier/probe/{venue}`, persisted to a temporary SQLite store and read back through the evidence API. All three returned HTTP 200 and one normalized market. |
| `2026-10-26-frontier-api-books.json` | One listing plus at most one book through each Frontier adapter/API route; all three returned HTTP 200 and persisted their normalized snapshots to a temporary store. |
| `2026-10-26-frontier-api-trades.json` | One listing, at most one book, and up to ten public trades through the Frontier API for each venue; all three returned HTTP 200 and were read back from a temporary store. |
| `2026-10-26-polymarket-v2-trade-page.json` | One direct, unauthenticated Data API v2 first page for a condition already present in the saved public listing; one GET, ten normalized trades, and hash-verified temporary-store read-back. |
| `2026-10-26-polymarket-v2-api-continuation.json` | One continuation page for that condition through the isolated Frontier API route; one unauthenticated GET, ten normalized trades, and hash-verified temporary-store read-back. Its ten transaction IDs do not overlap the first page. |

The earliest direct source-probe files contain five HTTP 200 responses:
Kalshi market listing and later book, Kraken pair metadata and depth, and a
Polymarket Gamma event listing. Later API round trips and the two v2 pages are
enumerated separately below.

The Kalshi market returned as `market_type=binary` also carried
`mve_collection_ticker` and multiple `mve_selected_legs`. Frontier therefore
preserves it as a conditional event and leaves its payoff unverified. The
Polymarket event titled “Kraken IPO by ___ ?” and Kraken's XBT/USD spot pair
share the word “Kraken” but do not share an economic payoff. Neither capture
establishes a verified cross-venue equivalent event or an executable
opportunity.

These captures are small, time-specific fixtures, not continuous source
coverage or evidence of venue-wide market conditions.

The Frontier API listing-only round trip ran at `2026-10-26T20:41:18.904543Z` to
`20:41:19.624016Z`. It used one listing request per venue with retries disabled
and 65,536-byte response caps. Its capture envelope SHA-256 is
`3aaacd7b5d6f66d5cbc4178f8ff14768bc3622378ada1a2ba7961cb705d58ab6a`.

A second Frontier API round trip ran at approximately
`2026-10-26T21:10:40.775Z`–`21:10:43.974Z`. It made one discovery request and
at most one book request per source, sequentially, with retries disabled,
8-second timeouts, 65,536-byte response caps, and a temporary 8 MiB SQLite
store. Each venue reported two bounded network requests and returned HTTP 200.
Raw bodies and normalized observations were read back through the evidence API.
The envelope SHA-256 is
`101094b56c3dc620f8f66b423c92b5796db0a57852a5f7807aab50b2af956d60`, and the
envelope and all six raw-body hashes were recomputed successfully. Polymarket's
book contained 8 asks and 10 bids; Kraken's contained 10 asks and 10 bids;
Kalshi returned an empty book and explicitly lacked a unified exchange snapshot
timestamp. Kraken timestamps are per-level, while Polymarket's response does
not establish matching-engine simultaneity. Calls were sequential across
venues, so these books are not a synchronized cross-market state. No trades or
fee endpoints were called during that run. Each SQLite store was temporary and
isolated; the committed JSON files preserve the returned public evidence.

A later bounded API round trip ran at
`2026-10-26T21:25:20.750899Z`–`2026-10-26T21:25:27.005495Z`. It requested one
listing page, at most one book, and at most ten recent trades per venue, one
source at a time. The temporary SQLite store was capped at 8 MiB; adapters used
zero retries, 8-second timeouts, and 262,144-byte response caps. Each venue made
exactly three GET requests, all returning HTTP 200. The Polymarket sample
contained 8 asks, 10 bids, and 10 trades; Kraken had 10 asks, 10 bids, and 10
trades; Kalshi returned an empty book and zero trades. The Kalshi trade endpoint
returned a valid empty array. The API read-back reported the same trade counts.
All nine raw-body hashes and the envelope SHA-256
`ca72a2aa2095ae02660f0ea23c0a6e94019929bd7d1e174b0446673637e04570` were
recomputed successfully. The largest body was Kraken Trades at 68,758 bytes,
within the configured bound. Requests were sequential across venues and
timestamp semantics differ; these records do not imply synchronized quotes or
fills. No fee endpoint was called. Trade captures and books are public
observations, not profitability evidence.

The Data API v2 first-page probe ran at
`2026-10-26T22:56:38.585296Z`–`22:56:38.728359Z`. It used the previously
recorded condition `0xd5d9fc47718bd553592d126b1fa5e87183d27f3936975b0c04cc0f2dec1f1bb4`,
a 10-row page limit, a 65,536-byte response cap, and zero retries. Exactly one
GET returned HTTP 200 with ten normalized trades and `has_more=true`; all ten
rows referred to one Yes outcome token. The adapter persisted one raw and
normalized observation in an isolated temporary 8 MiB Frontier store and its
hash-verified read-back was preserved. The response raw-body SHA-256 is
`8923bbf6cff2262344ba7b14c923866bace1e46139bd790cedaa758195e6a174`; the
temporary-store row SHA-256 is
`65b172aff5ddbfba0c5e43d2952567028ec11a8ce210d44ea11b40732958bbda`; and the
pre-hash manifest SHA-256 is
`d970fce4cb0f4e48995b066ac1114d1c8c519be72eeaca54158cae65db664198`; the
serialized artifact SHA-256 is
`e5f400db64aeb000a688889eee4649a8e82ec061638dbe997e5b735dc423dc71`. The
manifest digest covers all fields except `envelope_sha256`, encoded as UTF-8
JSON with sorted keys and compact separators. The first page is a single-source
trade-print observation, not an order-book snapshot, cross-venue comparison, or
execution result. One live continuation page through the API is recorded below.

The bounded continuation probe ran at
`2026-10-26T23:02:48.888920Z`–`23:02:49.046817Z`. It supplied the opaque
cursor from the preceding captured page to the local
`POST /api/frontier/probe/polymarket/trades` route. The route bound the cursor to
the same condition and page size and made exactly one HTTPS GET, with zero
retries and a 65,536-byte response cap. HTTP 200 returned ten more trades for
the same Yes outcome token and another continuation cursor. Their ten native
transaction IDs were disjoint from page one. The raw-body hash is
`a2790da7bb4ea1faafe118562818b9de95b400b6f21d55b2bf3cb0697245fa32`, temporary
store row hash is
`5197ee99f491e2970d3656ae394a5279a9a135335a7a60f45a377db4d1715e5a`, cursor
hash is
`ccf6e9eaf39ba97a889068435cc8cb1283d99b40c1de81f81df9b56a5b320d98`, envelope
manifest hash is
`0d94b9c33555550cb2f72e895d6103bec1bf528561c7b9de246c27f0f81bb5ac`, and
serialized artifact hash is
`d95c09da91bdf840a7b8fee693a32b14b5d47d8677307773c20ac8c26e7dc405`. A further
page was available, but the probe stopped after this one continuation request.
The two pages demonstrate bounded cursor continuation and persistence; they do
not constitute full history, market depth, synchronized quotes, or execution
evidence.
