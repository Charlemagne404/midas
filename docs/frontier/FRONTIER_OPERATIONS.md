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

Cross-venue observations have independent clocks and freshness guarantees.
Different receipt times or a shared local timestamp do not prove simultaneous
availability, fills, legal access, or transferability. Preserve source and
receipt timestamps, raw hashes, adapter versions, quality flags, and each
exchange's timestamp semantics when evaluating a candidate.

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
