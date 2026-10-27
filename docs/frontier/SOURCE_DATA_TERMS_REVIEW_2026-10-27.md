# Frontier source-data use review — 2026-10-27

## Scope and status

This is an operational source-terms review for the local, research-only
Frontier development branch. It is not legal advice or a conclusion about any
person's prior conduct. The scope is public market-data API access, local
retention, and research use. No exchange was contacted, no permission was
requested, and no source request was made for this review.

## Kalshi

The official [Kalshi Developer Agreement v1.1](https://kalshi-public-docs.s3.amazonaws.com/Kalshi-Developer-Agreement.pdf)
defines itself as applying to any user of Kalshi's API. It says API use is
limited to facilitating a member's own trading and that other uses are
disallowed. Section 3.1 prohibits collecting, caching, aggregating, or storing
API data except to facilitate the user's own Kalshi trading; it also restricts
sharing, and section 4.1 requires exchange membership. The official public API
docs expose unauthenticated GET endpoints, but they do not state that those
endpoints are exempt from the agreement.

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

Commits `d38f517`, `73e008e`, and `e7958c1` add application read quarantine
while the source-use gate is active. Kalshi observations are excluded from
market, book, and trade lists; direct observation retrieval returns HTTP 409.
Relationships that touch a Kalshi endpoint are excluded from lists and graph
traversal. Reviews, stored
candidate/run/comparison outputs, and Frontier Arena replay snapshots/results
that trace to Kalshi are held from the corresponding research APIs. Missing
replay provenance fails closed. Source-level evidence remains append-only and
unchanged. Generic Arena overview, research-activity, job detail, and log routes
also check Frontier replay snapshots before exposing job data. Generic replay
submission rejects held snapshots and cancel requests are blocked before any
mutation. The overview exposes eligible counts; its database-size value still
includes preserved held evidence.

This is application-route quarantine. The project still treats direct database
inspection, exports, and other paths outside those read APIs as held pending
permission review. The integration tests use controlled local fixtures; they
do not inspect or alter the preserved live captures.

## Kraken Spot

Kraken's official [API introduction](https://docs-legacy.kraken.com/api/docs/guides/global-intro/)
says API use is subject to Kraken's terms and that prior permission is required
for certain uses, including non-personal commercial use of data from public
endpoints. Kraken's [Terms of Service index](https://www.kraken.com/legal) says
regional terms differ. This review does not determine whether Frontier's
internal MIDAS use is personal, commercial, or covered by a permission already
held by the user.

Accordingly, new Kraken Spot probes and new research use of captured Kraken
market data remain held until the applicable terms are reviewed and any
required permission is recorded. Commits `d38f517`, `73e008e`, and `e7958c1`
apply the same read filters to Kraken observations and derived artifacts as to
Kalshi. Direct database inspection, exports, and other paths outside the
covered read APIs remain held. Offline fixture development may continue. No
authenticated API key, account access, or trading capability is used.

## Polymarket

Polymarket Institute's official [research data guide](https://institute.polymarket.com/data)
describes open exchange APIs and datasets for research use. This supports the
research purpose of the bounded public API integration. It does not authorize
trading from restricted jurisdictions, redistribution, or use of a separate
Polymarket service's data. Frontier remains read-only and does not bypass
geographic or account restrictions.

## Runtime controls

The main API defaults all live probes off. Kalshi live probing now requires
both the explicit probe switch and a non-empty
`MIDAS_FRONTIER_KALSHI_RESEARCH_AUTHORIZATION_REF`. Kraken live probing
requires both its probe switch and a non-empty
`MIDAS_FRONTIER_KRAKEN_MARKET_DATA_PERMISSION_REF`. These values are pointers
to a locally reviewed written authorization or terms-review record; the code
does not inspect or validate the referenced document. A reference by itself is
not proof that the source permits this use.

When a required reference is absent, `/api/frontier/sources` reports the
policy block, probe routes return HTTP 409 without making a request, and
readiness reports `source_data_use_permissions` as `BLOCKED`. The same active
policy holds historical records from the Frontier application read and replay
routes described above. Existing source records are not deleted or rewritten.
The code does not verify the referenced permission document; a future
authorized use requires a separately recorded review and deliberate operator
configuration change. Direct database access remains outside the route filter.

## Read-quarantine verification — 2026-10-27

Controlled fixtures verified source filtering for overview counts, markets,
books, trades, direct observation access, relationship lists, depth-one and
depth-two graph traversal, replay creation, historical run lists, paired
comparisons, and Arena replay catalog/result routes. The test also verified the
held observations and Arena artifacts remained present and unchanged. The
Arena test also covers generic job overview/detail/log routes, research-activity
digests, generic replay submission, cancellation rejection, and damaged
provenance. The focused source/storage/Arena/API selection passed **13 tests**;
the Frontier Mission Control component passed **8/8**, with TypeScript, targeted
ESLint, Prettier, Ruff, and `git diff --check` passing. The full suite and production
build were not rerun at this checkpoint. No live request, database mutation,
service action, or deployment occurred.
