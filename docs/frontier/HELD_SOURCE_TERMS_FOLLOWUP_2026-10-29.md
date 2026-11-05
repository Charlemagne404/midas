# Frontier held-source terms follow-up — 2026-10-29

This supplement reviews official API and data-use materials for the held
cross-venue sources. It uses official documentation and terms pages only. No
exchange market-data endpoint was called, no API-use form was submitted, and
no saved exchange evidence was used for this terms review. This is not legal
advice and does not determine the user's jurisdiction, contracting entity,
organization status, or existing permissions. The detailed Gemini review is
preserved in [SOURCE_DATA_TERMS_REVIEW_2026-10-29.md](SOURCE_DATA_TERMS_REVIEW_2026-10-29.md).

## Kalshi

Kalshi's API help page describes public market data as available through its
REST API. Its regulatory agreements page lists a Member Agreement dated
October 1, 2026. Public endpoint availability does not itself grant rights to
collect, retain, aggregate, or use data for external research. The previous
terms review records restrictions in the Developer Agreement and separate
Data Terms beyond a member's own trading, including written authorization
requirements for some software-development and archive uses. Frontier has no
recorded written research/retention authorization. Keep Kalshi probes and
saved-data quarantine held.

References: [Kalshi API help](https://help.kalshi.com/en/articles/13823854-kalshi-api);
[Kalshi regulatory agreements](https://kalshi.com/regulatory/agreement);
[Developer Agreement](https://kalshi-public-docs.s3.amazonaws.com/Kalshi-Developer-Agreement.pdf);
[Data Terms of Use](https://kalshi-public-docs.s3.amazonaws.com/kalshi-data-terms-of-service.pdf).

## Kraken Spot

Kraken's API introduction says public market-data endpoints are available
without account authentication, while API use remains subject to applicable
terms. It explicitly says prior permission is required for certain uses,
including non-personal commercial use of public endpoint data. Kraken's
global terms were updated October 28, 2026, and separate EEA terms exist.
Frontier has not established which regional terms apply or whether its
research, storage, and display scope falls within a permitted personal use.
Keep Kraken probes and saved-data quarantine held until that scope and any
required permission are established.

References: [Kraken API introduction](https://docs-legacy.kraken.com/api/docs/guides/global-intro/);
[Kraken public endpoint examples](https://support.kraken.com/articles/360000919986-public-endpoint-examples-you-can-try-them-directly-in-a-web-browser-);
[Kraken global terms](https://www.kraken.com/legal/global-terms);
[Kraken EEA terms](https://www.kraken.com/legal/eea-terms).

## Coinbase Exchange Spot

Coinbase's Market Data Terms of Use, dated August 7, 2026, grant a limited
personal/research-use license subject to restrictions. Without prior express
written consent, the terms restrict external display or dissemination and use
of market data to develop, validate, benchmark, or improve AI/ML models,
algorithms, agents, or other automated systems. Frontier's applicable entity,
distribution, retention, automation, and research scope have not been
validated. A terms-version acknowledgement and a public-probe flag do not
provide that consent. Keep the Coinbase source-use hold and quarantine.

Reference: [Coinbase Market Data Terms of Use](https://www.coinbase.com/legal/market_data).

## Operational outcome

No source-use hold was lifted. Kalshi, Kraken, and Coinbase remain fixture-only
under the current source gate; Gemini's detailed use and API-form conditions
remain documented separately. The existing Polymarket integration remains
separately scoped, with its worktree probe flag off. Future live use requires
the applicable terms and jurisdiction review, any required written permission
or form, a validated source-authorization mechanism, and a fresh host
admission check.
