# Frontier source-data terms refresh — 2026-10-28

This is a read-only operational refresh of the official source materials linked
in Frontier's source-use review. No source API was queried, no exchange was
contacted, and no saved capture was opened. This is not legal advice and does
not determine which entity, regional terms, or prior permissions apply to the
user or MIDAS.

## Findings

### Kalshi

The official [Developer Agreement v1.1](https://kalshi-public-docs.s3.amazonaws.com/Kalshi-Developer-Agreement.pdf)
still limits API use to facilitating a member's own trading, and restricts
collecting, caching, aggregating, and storing API data for other purposes. It
also requires membership and acceptance of the agreement for API use. The
separate [Data Terms of Use](https://kalshi-public-docs.s3.amazonaws.com/kalshi-data-terms-of-service.pdf)
sets restrictive conditions for Kalshi Data, including written authorization
for certain software-development and archived-data uses. Public unauthenticated
API examples do not remove these use restrictions.

Frontier's retained, aggregated, cross-venue research is outside the stated
own-trading purpose. No written authorization is recorded here. Kalshi live
probes and use of preserved Kalshi evidence remain held; the existing API and
data quarantine stays enabled.

### Kraken Spot

Kraken's [API introduction](https://docs-legacy.kraken.com/api/docs/guides/global-intro/)
says API use is subject to Kraken's terms and that prior permission is required
for certain uses, including non-personal commercial use of data from public
endpoints such as market data. The current [Global Terms of Service](https://www.kraken.com/legal/global-terms)
show a last-updated date of 19 October 2026; Kraken also publishes separate
[EEA Terms of Service](https://www.kraken.com/legal/eea-terms). The terms differ
by region, and their applicability to the intended MIDAS use has not been
established. The API guide's permission notice is sufficient to keep public
Kraken capture and retained research on hold while the user's/organization's
scope and any required permission remain unresolved.

### Coinbase Exchange Spot

Coinbase's [Market Data Terms of Use](https://www.coinbase.com/legal/market_data)
remain dated 7 August 2026. They provide a limited personal/research-use
license subject to restrictions. Without prior written consent, the terms
restrict building an application intended for users outside the individual or
their organization's officers and employees, external display or dissemination
of Market Data and Derived Works, and specified AI or machine-learning uses.
The applicable entity, organization, region, internal distribution, and exact
research scope are not established. The Coinbase source-use hold therefore
remains; a version acknowledgement alone is not permission.

### Polymarket

The [Polymarket Institute research data guide](https://institute.polymarket.com/data)
continues to describe research access to the decentralized Polymarket exchange
and separately identifies the US exchange, with distinct APIs and separately
managed data. Frontier's existing Polymarket adapter and saved evidence must
not be generalized to the separate US exchange. The research guide does not
establish jurisdictional trading eligibility, redistribution rights, or live
economic equivalence.

## Operational outcome

No source-use hold was lifted. Kalshi, Kraken, and Coinbase adapters remain
offline-fixture-only under the current permission gate. Polymarket's existing
research adapter remains scoped to its documented source. No API call, test
against held captures, capture copy, or change to `data/frontier-public-probes/`
occurred during this refresh. Re-review source terms and intended use before
any change to a hold.
