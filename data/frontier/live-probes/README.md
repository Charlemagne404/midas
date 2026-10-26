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

The Kalshi market returned as `market_type=binary` also carried
`mve_collection_ticker` and multiple `mve_selected_legs`. Frontier therefore
preserves it as a conditional event and leaves its payoff unverified. The
Polymarket event titled “Kraken IPO by ___ ?” and Kraken's XBT/USD spot pair
share the word “Kraken” but do not share an economic payoff. Neither capture
establishes a verified cross-venue equivalent event or an executable
opportunity.

These captures are small, time-specific fixtures, not continuous source
coverage or evidence of venue-wide market conditions.
