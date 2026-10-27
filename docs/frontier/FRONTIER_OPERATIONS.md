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
While the permission reference is absent, Frontier application routes also
quarantine previously stored Kalshi/Kraken observations and derived research
artifacts: market/book/trade lists, direct observation lookup, relationship
lists, graph traversal, candidate/run/comparison views, replay inputs, and
Arena replay catalog/results, plus generic Arena job overview/detail/log and
research-activity routes for Frontier replay jobs. Generic submissions reject
held snapshots, and cancellation cannot expose a result or mutate a held job.
The snapshot check runs before job reconciliation so a blocked read does not
rewrite the job manifest. Held rows are not deleted or rewritten. The overview's
database-size measurement includes preserved held evidence while its research
counts exclude it. Direct database inspection, exports, and other paths outside
these APIs remain held. Controlled fixtures verify the application filters;
they do not validate the terms. A test-source audit found direct references to
preserved captures in two Frontier test modules, and the 18:41 UTC full suite
read those files. The 15 references have been replaced by synthetic inputs,
and a source-text scan now finds no held-directory references. The static
guard passes; the modified API/adapter selection passes 24 tests, and the full
Frontier suite passes 218 tests. These synthetic tests do not establish source
permission or live-source validation. See the
[source-data terms review](SOURCE_DATA_TERMS_REVIEW_2026-10-27.md) for details.
An autouse runtime guard for common file-open calls was added after those test
runs; it has not been validated yet and requires a safe rerun of its regression
and the full Frontier suite.

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

## Virtual settlement-duration sensitivity

Candidate cards can submit a user-entered annual carry rate (basis points) for
each venue to `POST /api/frontier/opportunities/capital-carry`. The request must
name the candidate's saved run and exact result hash. The API loads that run and
the market observations pinned on its candidate legs, verifies store integrity
and source/market/venue identity, then requires verified, hash-identified future
settlement metadata and a single exact settlement denomination. It uses no
network request, account, balance, wallet, or saved-source permission expansion.
Held Kalshi/Kraken candidates remain unavailable through the existing
quarantine.

The calculation uses simple interest at the supplied rate, actual duration in
seconds divided by a 365-day year, and no compounding or currency rounding. It
starts at the saved candidate observation time and holds all capital for a
venue until the latest settlement among that venue's candidate markets. This
conservative duration may overstate individual-leg holding time. It is not an
exchange fee or a financing offer. Unknown fees can remain excluded from the
candidate's capital amount. The response retains exact decimal values, both
run/candidate hashes, per-market observation IDs, validated normalized-store-row
and raw-body hashes, resolution evidence references, and the independent
arithmetic disposition. The result is
computed on demand and is not written to the Frontier database. It cannot change
candidate classification or practical eligibility; it does not establish
settlement truth, financing availability, legal access, transferability,
collateral eligibility, or executable returns.

## Saved Kalshi fee evidence

The event/series fee-metadata probe is a source capture, not an immediate fee
calculation. After capture, a saved-evidence replay can derive a conditional
one-fill taker estimate only when the event override is complete or explicitly
cleared to inherit the series, the event and series rows match their raw
responses and recorded market, and the fee type is supported. The metadata must
predate the pinned book quote and be no more than 24 hours old at quote and
replay time. Replay manifests pin the event and series observation IDs, and the
run history displays their count.

The estimate applies the public quadratic formula and a conservative `$0.01`
non-direct-member balance-alignment scenario for one fill. It does not identify
the user's account class or establish maker/multi-fill/FCM costs. Such candidates
remain conditional or incomplete. Missing, partial, stale, mismatched, or
unsupported fee evidence stays unknown. The source-terms permission gate still
applies: no probe or new use of held Kalshi evidence is enabled by this feature,
and held rows remain filtered from Frontier API research reads.

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

`JSON_COMPLEXITY_LIMIT` means the bounded JSON decoder rejected more than 64
container levels or an oversized integer token. The transport makes no retry
for this response, retains its complete bounded raw bytes as a
`source_failure` record, and reports the diagnostic observation ID. Inspect
the error code and raw-body hash; do not treat the failure as an empty market
response.

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
