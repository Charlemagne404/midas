# Frontier operations

Frontier is a local, public-data research system. It does not submit orders,
use authenticated exchange accounts, or read account balances. Keep it separate
from Reality and protected MIDAS services.

## Worktree and storage

Continue development in `/home/charlie/midas-frontier` on
`codex/frontier-20261026`. This worktree is based on the verified V6 integration
commit. Keep the Frontier store at `MIDAS_FRONTIER_ROOT` (default
`data/frontier-store`); tests and capture validation should use a temporary
store. Do not point Frontier at Reality recordings, Veritas evidence, frozen
campaigns, or other historical stores.

## Public source captures

Adapters make no startup requests and live probing is disabled by default. A
probe requires the venue's explicit
`MIDAS_FRONTIER_<VENUE>_PUBLIC_PROBE_ENABLED=true` setting and a deliberate
bounded capture action. The probe uses documented unauthenticated GETs, source
rate limits, and configured response/request bounds. It captures a limited
listing/book/trade sample or one separately requested cursor page; it does not
start a collector or crawl history. Do not enable probes in a production service
as part of routine development.

**Source terms are an additional gate.** Kalshi live capture is blocked until
written research and local-retention authorization is recorded. Kraken Spot
capture is blocked until its applicable research-use terms are reviewed and any
required permission is recorded. For these two sources, the probe flag alone is
insufficient: also set `MIDAS_FRONTIER_KALSHI_RESEARCH_AUTHORIZATION_REF` or
`MIDAS_FRONTIER_KRAKEN_MARKET_DATA_PERMISSION_REF` to an internal reference to
the relevant permission/review record. The application does not validate that
record; a string reference is not permission. See the
[source-data terms review](SOURCE_DATA_TERMS_REVIEW_2026-10-27.md). Existing
Kalshi and Kraken capture artifacts remain preserved, but do not treat them as
available inputs for new research until the corresponding use review is closed.
The application gate prevents new source requests; it does not yet hide all
previously stored source records from read, graph, or replay routes, so do not
use those routes with the held sources pending review. Fixture-only development
remains available.

Cross-venue observations have independent clocks and freshness guarantees.
Different receipt times or a shared local timestamp do not prove simultaneous
availability, fills, legal access, or transferability. Preserve source and
receipt timestamps, raw hashes, adapter versions, quality flags, and each
exchange's timestamp semantics when evaluating a candidate.

Keep display currency codes separate from denomination identity. Instruments,
books, fee schedules, trades and candidate capital expose an exact identity only
when the source supports one. A ticker match such as `USD` does not establish
that two values use fiat dollars, the same token, or the same network. Missing
identities in older stored rows are intentionally left unknown; do not fill them
from the ticker or update historical records. Candidate evaluation and
independent audit require the exact quote identity to match the verified payoff
settlement unit, and require a fee identity before including a fee amount. The
virtual-funding UI keeps separate balances by venue and canonical denomination.

The source health `requests_in_window` value counts request starts in the
trailing 60 seconds. Reading health is local and makes no source request.
Cross-venue `timing_verified` is stricter than receipt-time proximity: the
exchange timestamp semantics must agree, the samples cannot be future-dated,
and quantified source clock uncertainty is added to observed skew. Current
adapters do not yet provide clock-uncertainty estimates, so inspect that field
and the timing reasons instead of treating a positive recorded-value
calculation as a simultaneous quote.

## Inspecting failed captures

When a bounded API request returns a diagnostic observation ID, read it through
`GET /api/frontier/observations/{id}`. Transport-response failures are stored as
`source_failure` observations. When a complete raw response had already been
captured before normalization or lineage validation failed, the raw observation
retains its original kind and hash while its normalized `record_kind` is
`source_failure`. A later book/trade failure must not duplicate a successful
listing capture. Use the returned IDs and hashes as the evidence boundary; do not
replace missing values with synthetic observations.

The Polymarket v2 trades route is a single explicit page. Its cursor is bound to
condition and page size, and each request repeats the bounded source filters.
There is no automatic continuation or background history crawl. The same
principle applies to the one-page Kalshi operations: a source cursor is retained
as evidence but is not followed without a separate explicit request.

## Resource and deployment limits

Use short, targeted tests and temporary stores. Before heavier local work,
inspect current host memory pressure and available memory; a dated capacity
sample is not an admission grant. Stop or defer builds and broad suites if host
pressure rises. Do not add persistent workers or run multi-day experiments as
part of ordinary development.

The API, UI, adapter fixtures, and bounded Arena replay are development
artifacts. Production deployment, protected-service changes, Reality restart,
campaign mutation, and changes to historical evidence are outside this routine
workflow and require a separate decision. The current mission ledger and
engineering report distinguish fixture verification, live public observations,
and deployment status.
