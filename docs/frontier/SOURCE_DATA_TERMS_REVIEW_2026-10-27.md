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
