# Frontier additional venue screen — 2026-10-27

This screen evaluated public-data access and economic fit for two additional
venues. It did not make network requests, create accounts, accept terms, or
retrieve historical data. The result is a source-selection decision, not legal
advice or permission to use either service.

| Candidate | Public interface and cost/access | Economic fit | Decision |
| --- | --- | --- | --- |
| Manifold Markets | Official API docs describe unauthenticated market reads and a 500 requests/minute per-IP limit, while warning that the API is alpha and subject to its Terms of Service. Its February 13, 2025 announcement ended sweepstakes markets: no new sweepstakes markets, later markets were resolved at then-current probability, and the cashout period ended March 28, 2025. Current FAQ says mana cannot be converted to cash. | A possible forecast/sentiment reference. Mana prices and liquidity do not denote cash-settled trading payoffs, so they cannot be an economic leg or arbitrage quote. Current USDC prize drawings are separate from market contracts. | Do not add to the opportunity adapter set. A later forecast-only adapter would need an explicit non-economic source type and a separate review of API data-use, retention, and display scope. |
| Betfair Exchange | Official API docs require an account application key on requests. The delayed key is for development/practice and returns delayed production snapshots (1–180 seconds) with reduced book fields. The live key is described for betting applications; live read-only access is not permitted, activation requires a verified account and a £499 funded-account fee, and commercial data/API use requires Betfair approval. | Exchange odds and runner ladders could be economically relevant to event contracts, but the documented no-bet route is account-keyed delayed data with substantial timing and book limitations. Full live data would cross the current public-only, no-account boundary. | Defer adapter work. Reconsider only after a separately authorized data-use/access path is documented; do not create or request credentials as part of Frontier. |

## Evidence and boundary

- Manifold API and endpoint capabilities: [official API documentation](https://docs.manifold.markets/api).
- Manifold current mana and market framing: [official FAQ](https://docs.manifold.markets/faq).
- Manifold sweepstakes-market shutdown and dates: [official announcement](https://news.manifold.markets/p/focusing-on-mana-bringing-sweepstakes-to-an-end).
- Betfair account-key, delayed-data, live read-only, and commercial-use conditions: [official Application Keys documentation](https://betfair-developer-docs.atlassian.net/wiki/spaces/1smk3cen4v3lu3yomq5qye0ni/pages/2687105/Application%20Keys).

The APIs, accounts, and historical-data services above were not queried. The
public docs do not establish the user's jurisdictional eligibility, commercial
status, or any additional contract. No data or access permission is inferred
from documentation availability. The existing Polymarket/Kalshi/Kraken/Coinbase
source gates remain unchanged.
