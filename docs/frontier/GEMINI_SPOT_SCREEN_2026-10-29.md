# Additional venue screen — Gemini Spot — 2026-10-29

This review used Gemini's official REST API documentation, API Agreement, and
Market Data Agreement as published at review time. It made no network API
request, did not submit the API Use Form, did not create or access an account,
and did not inspect or copy a market-data capture. The review is not legal
advice and does not determine which Gemini entity or User Agreement applies to
the user or MIDAS.

| Criterion | Finding |
| --- | --- |
| Public interface | Gemini documents unauthenticated public market-data endpoints for symbol details (`GET /v1/symbols/details/{symbol}`) and current aggregated books (`GET /v1/book/{symbol}`). The API Agreement states that public market-data requests do not require an API key and lists a 120 requests/minute public limit. The API Agreement also asks API users to complete an API Use Form. No form was submitted. |
| Instrument and research value | Symbol details declare base/quote currencies, `product_type`, `contract_type`, tick/quote increments, minimum size, and status. Spot pairs can provide a second venue's contextual BTC/ETH price and liquidity evidence. They are not event-contract payoffs or direct arbitrage legs. The adapter rejects swaps and preserves unknown user-specific fees. |
| Timing and precision | The book API returns price and quantity as exact decimal strings. Its per-level `timestamp` fields are explicitly documented as dummy compatibility values and must not be used. The adapter preserves raw bytes and local receipt time, leaves exchange time absent, and flags timestamp-unavailable. Public docs describe an aggregated book but do not establish simultaneous executability across venues. |
| Data-use terms | Gemini's Market Data Agreement dated 12 October 2025 permits personal/internal, informational, and price/market analysis uses subject to its prohibited-use terms. It prohibits redistribution, specified financial-product uses, and creation or use of financial benchmarks/reference rates/indexes; commercial-purpose use is directed to Gemini business development. The applicable residency-specific User Agreement, intended organization/research scope, internal distribution, and any separate approval remain unreviewed. The API Use Form has not been completed. |
| Operational and economic limitations | No live freshness, depth, rate behavior, fees, jurisdiction, or venue availability was measured. Per-symbol metadata is queried only for a configured allowlist; the venue-wide symbol list is deliberately not crawled. No authenticated endpoint, order-entry path, or credential support is implemented. |
| Decision | **Implement a read-only adapter behind a non-clearable source-use hold; live validation and use of retained Gemini data remain pending.** Reconsider the hold only after the applicable agreement and intended scope are reviewed and any required API-use or data-use approval is recorded through an authorized process. |

## Official references

- [Gemini Market Data API](https://developer.gemini.com/trading/rest-api/market-data)
- [Get Symbol Details](https://developer.gemini.com/trading/rest-api/market-data/get-symbol-details)
- [Get Current Order Book](https://developer.gemini.com/trading/rest-api/market-data/get-current-order-book)
- [Gemini API Agreement](https://www.gemini.com/legal/api-agreement)
- [Gemini Market Data Agreement](https://www.gemini.com/legal/market-data-agreement)

No source observation was acquired. Fixture tests use documented response
shapes and establish parser behavior only, not live-source functionality,
permission, current liquidity, or economics.
