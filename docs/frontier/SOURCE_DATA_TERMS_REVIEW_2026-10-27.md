# Frontier source-data use review — 2026-10-27

## Scope and status

This is an operational source-terms review for the local, research-only
Frontier development branch. It is not legal advice or a conclusion about any
person's prior conduct. The scope is public market-data API access, local
retention, and research use. No exchange was contacted, no permission was
requested, and no source request was made for this review. The official
materials below were reviewed as of 2026-10-27; regional applicability and any
permission held outside this worktree remain unverified.

## Kalshi

The official [Kalshi Developer Agreement v1.1](https://kalshi-public-docs.s3.amazonaws.com/Kalshi-Developer-Agreement.pdf)
defines itself as applying to API users and limits API use to facilitating a
member's own trading. It restricts collecting, caching, aggregating, storing,
and sharing API data outside that purpose. The separate [Kalshi Data Terms of
Use](https://kalshi-public-docs.s3.amazonaws.com/kalshi-data-terms-of-service.pdf)
also governs access to and use of Kalshi market data. The API documentation's
unauthenticated GET examples do not state that public endpoints are exempt
from these terms.

Frontier's independent research, aggregation, append-only evidence store, and
cross-venue analysis do not match that stated own-trading purpose. No written
research/data-retention authorization is recorded in this worktree. Therefore:

- New Kalshi live captures are blocked.
- Existing Kalshi captures remain preserved unchanged under the project
  evidence-preservation requirement. Treat them as use-restricted for new
  research, replay, and publication pending source permission/terms review.
- Fixture-driven adapter, parser, API, and economic tests may continue offline.
- Do not enable Kalshi probes using only
  `MIDAS_FRONTIER_KALSHI_PUBLIC_PROBE_ENABLED`.

This operational hold does not determine whether the prior captures were
authorized or require any change to their preservation state.

Commits `d38f517`, `73e008e`, `e7958c1`, and `23f9860` add application read
quarantine while the source-use gate is active. Kalshi observations are
excluded from market, book, and trade lists; direct observation retrieval
returns HTTP 409.
Relationships that touch a Kalshi endpoint are excluded from lists and graph
traversal. Review routes, stored candidate/run/comparison outputs, and Frontier
Arena replay snapshots/results
that trace to Kalshi are held from the corresponding research APIs. Missing
replay provenance fails closed. Source-level evidence remains append-only and
unchanged. Generic Arena overview, research-activity, job detail, and log routes
also check Frontier replay snapshots before exposing job data. Generic replay
submission rejects held snapshots and cancel requests are blocked before any
mutation. Held-job checks run before Arena's reconciliation helper so a
blocked read cannot rewrite a job manifest. The overview exposes eligible
counts; its database-size value still includes preserved held evidence.

This is application-route quarantine. The project still treats direct database
inspection, exports, and other paths outside those read APIs as held pending
permission review.

**Correction — offline test fixture boundary:** the earlier statement that
integration tests used only controlled fixtures was inaccurate. A path-text-only
audit of test source on 2026-10-27 found 15 direct references across
`tests/frontier/test_adapters.py` and `tests/frontier/test_api.py` to files in
`data/frontier/live-probes/`. Several cases parsed Kalshi artifacts; some
referenced mixed-source captures. The full Frontier test run recorded at 18:41
UTC executed these test cases and therefore read the referenced files. This
audit did not open any capture. No test writes to the capture directory were
identified, and no capture mutation is known. These offline reads violated the
intended held-source boundary even though they made no new source request.

The affected tests are being converted to explicitly synthetic local fixtures.
Keep every existing file under `data/frontier/live-probes/` unchanged. Until
conversion and a no-reference check are recorded, do not run tests that open
held-source captures. Future fixture-only tests must not read that directory.
Passing a synthetic parser test demonstrates behavior on its fixture only; it
does not establish live-source validation.

## Kraken Spot

Kraken's official [API introduction](https://docs-legacy.kraken.com/api/docs/guides/global-intro/)
says API use is subject to Kraken's terms. Kraken's [EEA Terms of Service,
effective 26 February 2026](https://assets-cms.kraken.com/files/51n36hrp/facade/e7cb2e6758f56b3eaa044d4b0b8097f2d1252a63.pdf),
classify pricing data as Kraken content, limit use to approved purposes, and
restrict automated extraction and third-party applications without written
consent. Kraken's [terms index](https://www.kraken.com/legal) notes regional
differences. The applicable regional terms and whether Frontier's internal
MIDAS use is authorized have not been established.

Accordingly, new Kraken Spot probes and new research use of captured Kraken
market data remain held until the applicable terms are reviewed and any
required permission is recorded. Commits `d38f517`, `73e008e`, `e7958c1`, and
`23f9860` apply the same read filters to Kraken observations and derived
artifacts as to Kalshi. Direct database inspection, exports, and other paths
outside the covered read APIs remain held. Offline fixture development may
continue. No authenticated API key, account access, or trading capability is used.

## Coinbase Exchange Spot

Coinbase's official [Exchange API overview](https://docs.cdp.coinbase.com/exchange/introduction/welcome)
documents public Market Data endpoints separately from authenticated account
and trading operations. The [product](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-single-product),
[level-2 order book](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-book),
and [trade](https://docs.cdp.coinbase.com/api-reference/exchange-api/rest-api/products/get-product-trades)
references describe the read paths used by the offline-fixture adapter. The
documented REST IP limit is 10 requests/second with a burst allowance of 15;
Frontier's adapter transport is configured to a lower local maximum and does
not paginate automatically.

The separate official [Market Data Terms](https://www.coinbase.com/legal/market_data)
were marked last updated 7 August 2026 when reviewed on 27 October 2026. They
provide a limited research-use license but also impose organization,
redistribution, derived-data, and other use restrictions. Their application to
this user's organization, jurisdiction, dashboard display, retained records,
and planned research distribution has not been independently resolved. The
technical fact that an endpoint is public does not waive those terms.

The Coinbase adapter is implemented against synthetic local responses and has
not queried Coinbase. It remains held from Frontier research, replay, and
capture. Frontier has no validated permission and intended-scope review loader;
an exact acknowledged terms version and a separate public-probe flag do not
lift the hold. The exact-version field records an operator's configuration
acknowledgement only. No data has been acquired or stored by this integration.
Spot observations, if separately authorized, remain contextual evidence and
cannot be treated as prediction contract payoff or direct arbitrage.

## Polymarket

Polymarket Institute's official [research data guide](https://institute.polymarket.com/data)
describes open exchange APIs and datasets for research use. This supports the
research purpose of the bounded public API integration. It does not authorize
trading from restricted jurisdictions, redistribution, or use of a separate
Polymarket service's data. Frontier remains read-only and does not bypass
geographic or account restrictions.

## Runtime controls

The main API defaults all live probes off. More importantly, there is no
validated authorization loader for Kalshi or Kraken: both
`frontier_kalshi_probe_allowed` and `frontier_kraken_probe_allowed` remain
false regardless of the public-probe flags or configured reference strings.
The `MIDAS_FRONTIER_KALSHI_RESEARCH_AUTHORIZATION_REF` and
`MIDAS_FRONTIER_KRAKEN_MARKET_DATA_PERMISSION_REF` settings are descriptive
only. A reference string is not inspected, authenticated, or treated as proof
of permission.

Consequently `/api/frontier/sources` always reports the Kalshi/Kraken policy
hold, probe routes return HTTP 409 without making a request, and readiness
reports `source_data_use_permissions` as `BLOCKED`, whether or not a reference
string is configured. The same unconditional hold quarantines stored records
from the Frontier application read and replay routes described above. Existing
source records are not deleted or rewritten. Any future unhold requires a
validated permission mechanism and an explicit source-use review; setting the
existing flags or adding a reference is insufficient. Direct database access
remains outside the route filter.

Coinbase's source-specific gate remains held even when the operator sets
`MIDAS_FRONTIER_COINBASE_MARKET_DATA_TERMS_VERSION_ACKNOWLEDGED` to exactly
`2026-08-07` and enables `MIDAS_FRONTIER_COINBASE_PUBLIC_PROBE_ENABLED`. The
version value records acknowledgement only; it does not validate that the
terms permit this organization, region, retention, derived-data, display, or
automated-system use. Without a validated permission and intended-scope review
loader, the source remains quarantined and probes return HTTP 409 before any
request. Re-review the linked terms and intended use before considering a
future permission mechanism. No Coinbase request or live capture was made.

## Read-quarantine verification — 2026-10-27

Controlled fixtures verified source filtering for overview counts, markets,
books, trades, direct observation access, relationship lists, depth-one and
depth-two graph traversal, replay creation, historical run lists, paired
comparisons, and Arena replay catalog/result routes. The test also verified the
held observations, Arena snapshots/results, and job manifest remain unchanged
during blocked reads. The Arena test also covers generic job overview/detail/log
routes, research-activity digests, generic replay submission, cancellation
rejection, and damaged provenance. The focused source/storage/Arena/API
selection passed **13 tests**; the Arena replay/API modules passed **30 tests**
in 4.66 seconds with the existing Starlette/httpx deprecation warning. The
Frontier Mission Control component passed **8/8**, with TypeScript, targeted
ESLint, Prettier, Ruff, and `git diff --check` passing. The full suite and
production build were not rerun at this checkpoint. No live request, database mutation,
service action, or deployment occurred.

## Controlled test-fixture remediation — 2026-10-27

All 15 discovered test-source path references have been replaced with
explicitly synthetic inline response bodies or normalized fixture records in
the two affected modules. A source-text scan over `tests`, `packages`, and
`apps` now finds no `data/frontier/live-probes` or `live-probes` references.
A new static test guards Python test sources against reintroducing that path.
The static test passed, the changed adapter/API selection passed 24 tests, and
the complete Frontier Python suite passed 218 tests in 39.36 seconds at
333,988 KiB peak RSS with zero swaps. The existing Starlette/httpx test-client
deprecation warning remains. `git diff --check` passes. Preserved capture
files were not edited by this cleanup. This suite validates implementation on
synthetic inputs only; it does not establish live-source behavior or permission.

After the 19:02 validation, an autouse runtime guard was added for Python's
built-in, `io`, and `os` file-open calls. A read-only review found and closed
symlink-plus-`..` traversal and relative-`dir_fd` bypasses; the raw opener is
kept inside the fixture closure. Commit `df30fa7` adds those corrections and
temporary-path regressions. The guard passes **2/2** cases, covering Path,
built-in `open`, `os.open`, file and directory symlinks, symlink-plus-`..`, and
relative `dir_fd` access. Ruff and formatting pass. The complete Frontier suite
passes **219 tests in 39.83 seconds** at **335,396 KiB peak RSS**, with zero
swaps and the existing Starlette/httpx TestClient deprecation warning. A scan
over `tests`, `packages`, and `apps` finds no `live-probes` path. The guard is
test-only defense for common Python file-open APIs; the source-use restriction
remains the governing boundary. Existing captures remain untouched, and
synthetic tests do not establish live-source validation or permission.

## Official documentation refresh — 2026-10-27 20:45 UTC

This was a read-only review of official web documentation; no exchange API was
queried, no exchange was contacted, and no historical capture was opened. It is
an operational hold decision, not legal advice or an interpretation of any
person's contractual status.

- **Kalshi:** The current linked [Developer Agreement v1.1](https://kalshi-public-docs.s3.amazonaws.com/Kalshi-Developer-Agreement.pdf)
  continues to limit API use to facilitating a member's own trading, and
  restricts collection, caching, aggregation, and storage for other purposes
  absent authorization. The [Data Terms of Use](https://kalshi-public-docs.s3.amazonaws.com/kalshi-data-terms-of-service.pdf)
  separately limit website data to personal, non-commercial use, expressly
  exclude software development and archived/cached datasets from that allowance,
  and require prior written authorization for listed extraction and derivative
  uses. The public GET examples in API documentation do not resolve those
  conditions for Frontier's systematic research and retention. The Kalshi hold
  remains in force.
- **Kraken:** The current [legal index](https://www.kraken.com/legal) lists
  different terms by residence. The [Global Terms](https://www.kraken.com/legal/global-terms)
  are marked last updated 19 October 2026; they limit use of “Our Content” to
  the user's own benefit, require prior permission for other purposes, and
  restrict extraction, automation, and third-party applications interacting
  with that content without written consent. The current [EEA Terms](https://www.kraken.com/legal/eea-terms)
  expressly include pricing data in “Our Content,” limit it to approved
  purposes, and include similar restrictions. Kraken's [API Center](https://docs-legacy.kraken.com/api/docs/guides/global-intro/)
  describes public Spot REST/WebSocket market-data interfaces, but the material
  reviewed does not settle the exact permission, retention, and research scope
  for Frontier's public-API use or identify the user's applicable regional
  terms. Keep probes and stored Kraken research held until that scope and any
  required permission are validated.
- **Polymarket:** The [Polymarket Institute research guide](https://institute.polymarket.com/data),
  dated 24 July 2026, continues to describe open exchange APIs as accessible
  to students, researchers, and learners. It distinguishes the decentralized
  platform from the US-only platform and says they have separate APIs and
  separately managed data. This supports the existing global-platform research
  source classification only; it does not authorize restricted-location access
  or make the two platforms interchangeable.

This refresh changes no probe flags or source policy. Existing Kalshi and
Kraken captures remain unchanged and quarantined; synthetic offline fixtures
remain the only permitted adapter-validation input in this worktree. A future
change requires a validated source-use decision for the exact data, activity,
retention, region, and intended distribution, not a configuration reference
string alone.

## Official terms refresh — 2026-10-28

This was a read-only review of official public documentation. No exchange was
contacted, no API endpoint was queried, no source setting changed, and no
preserved capture was opened. This is an operational policy record, not legal
advice or a conclusion about any person's eligibility or prior use.

- **Kalshi:** The currently linked [Developer Agreement v1.1](https://kalshi-public-docs.s3.amazonaws.com/Kalshi-Developer-Agreement.pdf)
  still limits API use to a member's own exchange trading and restricts
  collecting, caching, aggregating, storing, and sharing API data outside that
  purpose absent written authorization. It also requires membership, agreement
  acceptance, and contact information. The public nature of GET endpoints does
  not remove those terms. Keep live probes and new research use of preserved
  captures blocked; do not treat a reference string or public endpoint as
  permission.
- **Kraken Spot:** The current [Global Terms](https://www.kraken.com/legal/global-terms)
  state that EEA residents are subject to separate terms; the official
  [EEA Terms](https://www.kraken.com/legal/eea-terms), if applicable, include
  pricing data as “Our Content,” limit its use to approved purposes and the
  user's own benefit, require prior permission for other purposes, and restrict
  data extraction, automation, and third-party applications. The applicable
  residence/account terms and permission for Frontier's storage and research
  remain unverified. The official [Spot API rate-limit guidance](https://support.kraken.com/gb/articles/206548367-what-are-the-api-rate-limits-)
  (updated 1 October 2026) says public REST requests at one per second or less
  would remain within the published limits; Frontier's generic transport
  default is one request per second. This operational limit does not resolve
  the use restriction. Keep Kraken live probes and new stored-data research
  held.
- **Coinbase Exchange Spot:** The official [Market Data Terms](https://www.coinbase.com/legal/market_data)
  remain marked last updated 7 August 2026. They grant a limited personal or
  organizational research-use license, limited to the user or the entity's
  officers and employees, and do not permit an app for other end users. Without
  express written consent, the terms restrict third-party redistribution of
  data and derived works; they also restrict creating specified benchmarks and
  financial-product valuations and prohibit use of Market Data for AI/ML
  research, development, validation, or operation. Frontier does not enforce
  these output/use restrictions. Whether a particular private spot-context
  analysis, its raw retention, and this research interface fit the permitted
  scope is unresolved. Keep the existing hold: the exact-version environment
  acknowledgement is a local configuration gate, not a blanket permission to
  enable every Frontier use. Do not set it solely to enable cross-market
  analysis.

The source-policy conclusion is unchanged: fixtures and code review may
continue offline; live requests, new research over held captures, and
production use remain gated by a specific, validated source-use decision.

### Official terms supplement — 2026-10-28 03:00 UTC

This read-only supplement checked current official terms and API guidance to
resolve whether unauthenticated public endpoints change the source-use
decision. No exchange was contacted, no API endpoint was queried, and no held
capture or production setting was accessed.

- **Kalshi:** The current [Market Data API quick start](https://docs.kalshi.com/getting_started/quick_start_market_data)
  documents unauthenticated GET access for public market data, including
  market and order-book endpoints. That describes technical access. The
  currently linked [Data Terms of Use](https://kalshi-public-docs.s3.amazonaws.com/kalshi-data-terms-of-service.pdf)
  apply to website data and expressly exclude software development and
  archived/cached datasets from the personal, non-commercial permission; they
  also reserve systematic extraction, collection, analysis, and derivative use
  absent prior written authorization. The separate [Developer Agreement v1.1](https://kalshi-public-docs.s3.amazonaws.com/Kalshi-Developer-Agreement.pdf)
  remains the governing API document and limits API use to facilitating a
  member's own trading. The fact that GET calls need no key does not establish
  a research or retention license. Keep the Kalshi API and captured-data hold.
- **Kraken Spot:** Kraken's [API Center introduction](https://docs-legacy.kraken.com/api/docs/guides/global-intro/)
  states that API use is subject to its terms and that prior permission is
  required for certain uses, including non-personal commercial use of data
  from public endpoints such as market data and exchange status. The current
  [EEA Terms](https://www.kraken.com/legal/eea-terms), effective 14 October
  2026, apply to EEA clients and classify pricing data as “Our Content”; they
  reserve uses outside approved purposes and specifically restrict automated
  extraction and scripts interacting with that content. Neither the user's
  residence nor the exact permission scope for Frontier is established here.
  The [public API examples](https://support.kraken.com/articles/360000919986-public-endpoint-examples-you-can-try-them-directly-in-a-web-browser-)
  confirm technical access without an account; the published
  [rate-limit guidance](https://support.kraken.com/gb/articles/206548367-what-are-the-api-rate-limits-)
  recommends public REST requests at one per second or less to remain within
  limits. Rate compliance does not grant research or storage permission. Keep
  Kraken probes and new research over held data blocked.
- **Coinbase Exchange Spot:** The [Market Data Terms](https://www.coinbase.com/legal/market_data)
  remain marked last updated 7 August 2026. In addition to the restrictions
  already recorded above, they explicitly prohibit using Market Data or
  derived works to develop, train, fine-tune, validate, benchmark, or otherwise
  improve AI/ML or other automated systems. They also restrict creation of
  fair-value prices, benchmarks, and financial-product valuations. Frontier
  does not encode a validated exception or permission for those activities.
  The exact-version local acknowledgement is therefore not proof that a
  planned use, data retention, or presentation is permitted; retain the
  existing default hold and do not enable Coinbase probes on that setting
  alone.

No source flag, adapter policy, stored observation, or permission status
changed during this review. Public endpoint accessibility and compliance with
published rate limits do not lift the established holds. Continue fixture-only
adapter validation until a source-specific use review establishes the relevant
terms, region, purpose, retention, and any required written permission.

### Bounded Polymarket event-metadata probe — 2026-10-28 03:18 UTC

The existing research-use boundary was applied to one read-only Polymarket
Gamma session. It made exactly two GET requests at one request per second,
with a 7-second timeout, zero retries, and a 256 KiB response cap. No
credentials, account access, order route, geographic workaround, held source,
or protected service was used.

The `/markets` response was HTTP 200 and returned one liquidity-ordered page
of 20 active markets. Its SHA-256 is
`bee76335963dc0045b0a0be4638afab827dfef9e83cef4eaa3e812d8ba0ba094`; its
Frontier observation ID is
`5e5f63dbc701476347a814a8496f1e88869f27a49e884b2cf27ee8ee238e661a`; and its
append-only store row SHA-256 is
`75db34b2b7e9848637942dcbb771745774cfc52ec586322b90c278e7e78b65`.
The 20 returned markets had two instruments each. The bounded page contained
four numeric event identifiers, with at most 13 listed markets under one
event. All 20 included rule text, one included a resolution authority, none
included a close time, and none had a verified or exhaustive payoff in the
Frontier model. This was a top-liquidity page, not a venue inventory or
multi-outcome validation.

One follow-up `/events/{id}` request for the largest event group was rejected
by Frontier's response-size guard. The pre-change failure path retained no
response body, HTTP status, or declared-length diagnostic, so those details
remain unknown. No retry or follow-up was made. The first-page capture is
stored in the ignored, worktree-local database
`data/public-captures/frontier-polymarket-20261028T031822Z-pqzzdf1m/frontier.sqlite3`;
its raw and normalized read-back hashes were verified. The rejected event
response was not stored. This probe establishes source normalization and
resolution-metadata gaps only; it does not establish an exhaustive outcome
set, a verified payoff, a cross-venue relationship, or an opportunity.

This capture does not change the Kalshi, Kraken, or Coinbase holds or broaden
the Polymarket source-use purpose. It remains a local research record and is
not published or copied into version control.

## Supplemental FX reference-data evaluation — 2026-10-28

The [ECB Data Portal SDMX API documentation](https://data.ecb.europa.eu/help/api/data)
documents HTTPS programmatic access to the `EXR` exchange-rate dataflow and the
daily series key `D.USD.EUR.SP00.A`. This is a daily ECB reference-rate
statistic, not an exchange order book or an executable conversion quote. The
[ESCB reuse policy](https://www.ecb.europa.eu/stats/ecb_statistics/governance_and_quality_framework/html/usage_policy.ga.html)
permits free reuse of public statistics subject to source attribution and its
condition that the statistics and metadata are not modified; third-party data
may have separate rights. The ECB [site copyright terms](https://www.ecb.europa.eu/services/using-our-site/disclaimer/html/index.en.html)
also require accurate reproduction and source citation.

This is a useful possible source for contextual historical FX, but it does not
establish contemporaneous bid/ask availability, account eligibility, funding,
conversion execution, transfer cost, custody, or venue settlement. ECB
reference data therefore is not added as an exchange adapter and is not
automatically fed into Frontier's virtual funding or candidate-P&L scenarios.
No ECB API request or data capture was made. Any future integration must retain
the exact released statistic and required attribution, keep every model
transformation explicit, and preserve the non-executable reference-rate label.
This evaluation does not affect the current Kalshi, Kraken, or Coinbase
source-use holds.

### Bounded Polymarket single-market metadata probe — 2026-10-28 03:54 UTC

After implementing and fixture-testing the capability-specific metadata
route, one public read-only Gamma request fetched the already observed native
market ID `2589810` from `/markets/2589810`. The request was bound before
egress to listing observation
`5e5f63dbc701476347a814a8496f1e88869f27a49e884b2cf27ee8ee238e661a`. The
configured limits were one market, one request, one request per second,
7-second timeout, zero retries, and a 256-KiB response cap. No credentials,
account access, order route, geographic workaround, held source, or protected
service was used.

The HTTP 200 body was 4,198 bytes. Its raw SHA-256 is
`d462014349743a6175facab3aef0433a069899c43845c789ca4cdce87bd8cf26`; the
Frontier observation ID is
`d51864858856a0a8e8faff66fd75c5e590ee4b2f47642147b24c73e8581d74b9`; and
the append-only row SHA-256 is
`b2215f17912c3f4e9558d2b314b22d96ceb08fdd0fd439b2429db3ad259a2027`. A
read-only database check returned `integrity_check=ok`, and recomputing the
stored response-body digest matched the recorded raw hash. The isolated local
store is at
`data/public-captures/frontier-polymarket-market-metadata-20261028Ta05wfo2d/frontier.sqlite3/frontier.sqlite3`;
the prior capture database was read-only and was not modified.

The returned title and Federal Reserve resolution-source URL agree with the
listed market. The detail normalizer assigns `market:2589810` as its native
event ID, while the linked listing records event `606422`; this endpoint
response therefore does not establish event membership and must not replace
the listing's event context. Resolution verification, exhaustive outcome
coverage, payoff verification, settlement-asset attestation, and cross-venue
equivalence all remain false or unsupported. This is one metadata lookup, not
a multi-venue match or opportunity finding.

The capture and store read-back completed, but the one-off TestClient process
then exited with status 1 during `asyncio.run(registry.aclose())`: httpx
reported `RuntimeError: Event loop is closed`. This is a post-request harness
cleanup defect; no request was repeated. A future harness should close the
adapter on the request's ASGI event loop before this probe is considered a
clean end-to-end process run. This record makes no legal or jurisdictional
determination and does not change any source-use hold.
