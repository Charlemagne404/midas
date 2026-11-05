# Additional venue screen — Deribit — 2026-10-28

This source-selection review used Deribit's official API documentation,
membership terms, and restricted-jurisdiction notice as available on
2026-10-28. It made no API request, opened no account, accepted no terms, and
created no market-data fixture. Documentation availability does not grant
permission to collect or process market data.

| Criterion | Finding |
| --- | --- |
| Public data interface | Deribit documents JSON-RPC v2 market-data methods including `public/get_instruments` and `public/get_order_book`, with GET examples against its test API. The book response includes instrument identity, source timestamp, lifecycle state, price levels, and other venue-specific fields. No live call or unauthenticated production request was made. |
| Instrument and economic relevance | The instrument catalog exposes spot, futures, options, and perpetuals with instrument type, tick/lot constraints, contract size, settlement currency, quote currency, index, expiry, and state. Crypto spot/derivatives could contextualize relevant BTC/ETH event markets, but do not share their payoff. Options surfaces or mark/index prices must not be treated as a prediction-contract arbitrage leg without an independently validated model and hedge. |
| Data quality and operation | The public instrument list is documented as cached for about one minute and rate-limited to one request per second. The order-book endpoint accepts bounded depth values through 10,000 levels and returns exchange timestamps. Live freshness, completeness, observed liquidity, service reliability, and production rate behavior were not measured. |
| Data-use terms | Deribit FZE's Exchange Membership Terms, effective 2026-08-13, restrict market and derived data to personal use and require prior written approval for non-personal processing. DRB Panama's separate Terms of Service, version 2026-02-02, has a similar market/derived-data restriction and also prohibits systematic or automated data collection on its systems. Which entity and terms apply is not established. Frontier's platform research, storage, and analytical processing therefore remain held pending authoritative written scope approval. |
| Jurisdiction | Deribit's restricted-jurisdiction page was updated 2026-10-06 and lists multiple excluded jurisdictions, including the United States, Canada, and United Kingdom retail clients. The user's applicable entity and jurisdiction are not established by this review; no eligibility is inferred. |
| Cost and maintenance | The documented JSON-RPC v2 interface is technically plausible for a read-only adapter, but fee applicability, market-data rights, permitted retention/display, and current source quality have not been validated for Frontier. A new adapter would add instrument-specific settlement and currency complexity. |
| Decision | **Defer adapter and all live capture.** Reconsider only after written data-use approval (or an authoritative scope review) and a separately documented jurisdiction decision. If cleared, begin with a contextual derivative adapter whose instruments cannot enter event-contract economics without an explicit payoff/hedge proof. |

## Official references

- [Deribit `public/get_instruments` API documentation](https://docs.deribit.com/api-reference/market-data/public-get_instruments)
- [Deribit `public/get_order_book` API documentation](https://docs.deribit.com/api-reference/market-data/public-get_order_book)
- [Deribit Exchange Membership Terms — Deribit FZE](https://support.deribit.com/hc/en-us/articles/25944532191645-Deribit-Exchange-Membership-Terms-Deribit-FZE)
- [Terms of Service — DRB Panama Inc.](https://support.deribit.com/hc/en-us/articles/25944471089437-Terms-of-Service-DRB-Panama-Inc)
- [Deribit restricted jurisdictions](https://support.deribit.com/hc/en-us/articles/25944487427741-Restricted-Jurisdictions)

This is a source-selection record, not a legal conclusion or permission to use
the source. No Deribit adapter, capture, fixture, or research result was added.
