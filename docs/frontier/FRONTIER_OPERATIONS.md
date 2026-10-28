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

## Same-payoff review and replay cutoff

New same-payoff reviews use verifier version
`frontier-equivalence-verifier-8`. The review must cite the two distinct
stored market observation IDs loaded for the reviewed pair; its assertion time
cannot predate either market record. Candidate replay also requires the
versioned assertion to exist by that replay's cutoff. A review entered later
cannot validate a historical candidate.

Previously saved pre-v8 same-payoff relationships remain readable and
append-only, but the current independent audit
(`frontier-independent-economic-audit-22`) classifies a candidate using one as
`INCOMPLETE_EVIDENCE`. Re-review the original hypothesis against the current
stored market records to produce a version-8 relationship before using it in a
new audited replay. The verifier also requires nonempty exhaustive payoff
states and structurally valid instrument payout vectors on each market, so
empty state or instrument mappings cannot pass as vacuous bijections.
The verifier and audit recheck uniqueness of payoff states, native instrument
identities, outcome identities, and payout rows; the audit checks every
instrument, including unselected legs. This guards
against in-memory `model_copy(update=...)` objects that bypass ordinary model
validation. The reviewer label and assertion ID remain self-attributed; this
workflow does not authenticate them or establish legal or semantic equivalence.
The audit does not rewrite or delete stored relationships or reviews.

Logical-implication reviews use
`frontier-logical-implication-verifier-4` and the independent audit is now
`frontier-independent-economic-audit-22`. The verifier rejects empty or
duplicate payoff states and native instrument identities even when they arrive
inside a prebuilt model object. Earlier logical-implication records remain
readable, but they do not validate a new candidate until the relationship is
reviewed under v4.

Book snapshots also expose a runtime price-level integrity check because
`model_copy(update=...)` bypasses Pydantic validation. Candidate generators and
the independent audit reject copied books with duplicate prices, non-finite or
out-of-domain prices, non-positive quantities, malformed levels, or naive
level timestamps. Deterministic replay rejects such input before candidate
generation. A malformed book cannot contribute inflated top-of-book depth.

Joint-state maps also recompute their content digest and rerun the bounded
definition validation when used for candidate generation, audit, or replay.
A copied mapping whose assertion or projection changes while retaining its
old ID cannot support a conditional candidate or a verified audit. Replay
rejects the malformed mapping before search. A correctly hashed map remains an
unauthenticated semantic assertion and does not prove that joint states are
exhaustive or attainable.

Markets are also reconstructed through Pydantic validation at candidate,
independent-audit, and replay boundaries. This rechecks nested instrument,
payout, payoff, and settlement invariants after in-memory `model_copy` calls.
Malformed markets produce incomplete candidate/audit evidence or are rejected
at replay intake; they do not reach payout arithmetic.

Order-book snapshots are reconstructed through Pydantic validation at the
candidate, independent-audit, and replay boundaries. This includes top-level
receipt/exchange timestamps and nested provenance as well as level prices,
quantities, and timestamps. Replay performs the check before deriving a
default cutoff, so a copied naive timestamp is rejected instead of reaching
date arithmetic.

## Public source captures

Adapters make no startup requests and live probing is disabled by default. A
probe requires the venue's explicit
`MIDAS_FRONTIER_<VENUE>_PUBLIC_PROBE_ENABLED=true` setting and a deliberate
bounded capture action. The probe uses documented unauthenticated GETs, source
rate limits, and configured response/request bounds. It captures a limited
listing/book/trade sample or one separately requested cursor page; it does not
start a collector or crawl history. Do not enable probes in a production service
as part of routine development.

Adapter and transport construction revalidates the concrete source config
before use. A copied config that bypassed its response, timeout, request-rate,
market-count, or retry bounds is rejected before an HTTP client is created.

The transport rejects duplicate JSON object keys at every nesting depth with a
non-retryable `DUPLICATE_JSON_KEY` error. The bounded raw response is retained
as failure evidence and is not normalized into market, book, or trade rows.

For one saved Polymarket or Kalshi market, Mission Control's **Capture market
detail** action calls `POST /api/frontier/probe/{venue}/market-metadata`. The
route requires an exact native-ID lookup extension, derives the native ID from
the bounded saved market window, and verifies that the capture used the
adapter-declared HTTPS URL for that ID. The saved `market_metadata_evidence`
envelope links the detail response to the original listing observation; it does
not replace the catalogue row or imply event membership, exhaustive outcomes,
or verified payoff. Kraken and Coinbase have no single-ID detail lookup and the
route rejects them before network access. This is still a deliberate public
source request and remains subject to the source's use gate and operator
configuration.

For Polymarket, `native_event_id` is populated only from one explicit numeric
Gamma `events` entry or from a validated parent-event response. A detail object
without event metadata has no native event ID in Frontier; the legacy MIDAS
`market:<id>` placeholder is not event evidence. Existing stored observations
retain their original normalized representation and must not be silently
rewritten during this correction.

The 2026-10-28 bounded Polymarket validation is preserved separately at
`data/frontier-public-probes/polymarket-bounded-20261028T0852-r2Z/`. It contains
one completed one-market Gamma run, one explicit CLOB book observation, the
append-only store, and a hash-bearing `capture-manifest.json`. This is genuine
source evidence, not synthetic test data. Python Frontier tests now deny file
access beneath this root as well as beneath the legacy held-capture root; do
not add the capture to test fixtures or copy it into a synthetic dataset. The
manifest records that the market payoff/resolution remain unverified and that
the book had no bids and a 33.4-second source-timestamp-to-receipt difference
by direct comparison of unsynchronized clocks. This bounded observation does
not establish venue-wide coverage, cross-venue equivalence, or executability.

**Source terms are an additional gate.** Kalshi live capture is blocked until
written research and local-retention authorization is recorded. Kraken Spot
capture is blocked until its applicable research-use terms are reviewed and any
required permission is recorded. For these two sources, no configuration
currently enables collection. The application has no validated authorization
loader, so both probes and all stored Kalshi/Kraken research reads remain
blocked even when a probe flag and reference are set.
`MIDAS_FRONTIER_KALSHI_RESEARCH_AUTHORIZATION_REF` and
`MIDAS_FRONTIER_KRAKEN_MARKET_DATA_PERMISSION_REF` are descriptive only; a
string reference is not permission. See the
[current source-data terms review](SOURCE_DATA_TERMS_REVIEW_2026-10-28.md).
Existing Kalshi and Kraken capture artifacts remain preserved; do not treat them as
available inputs for new research until the corresponding use review is closed.
While the validated permission mechanism is unavailable, Frontier application
routes also quarantine previously stored Kalshi/Kraken observations and derived
research artifacts: market/book/trade lists, direct observation lookup, relationship
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
and a source-text scan now finds no held-directory references. The modified
adapter/API selection passes 24 tests; the complete Frontier suite passes
**219 tests** with the runtime guard active. The guard's temporary-path tests
pass **2/2**, covering direct paths, symlink traversal including `..`, and
relative `dir_fd` opens through common Python file-open APIs. These synthetic
tests do not establish source permission or live-source validation. Preserved
source files were not used or changed. See the
[current source-data terms review](SOURCE_DATA_TERMS_REVIEW_2026-10-28.md) for details.

Coinbase Exchange Spot has a separate explicit product allowlist
(`MIDAS_FRONTIER_COINBASE_PRODUCTS`, default `BTC-USD`). Its source-use gate
remains held even when the operator acknowledges the reviewed Market Data Terms
version exactly with
`MIDAS_FRONTIER_COINBASE_MARKET_DATA_TERMS_VERSION_ACKNOWLEDGED=2026-08-07` and
sets `MIDAS_FRONTIER_COINBASE_PUBLIC_PROBE_ENABLED=true`. Frontier has no
validated permission and intended-scope review loader; the exact-version value
records acknowledgement only. Coinbase probes return HTTP 409 before network
access, and Coinbase source records remain quarantined from application
research/replay routes. Coinbase fixture tests do not establish live validation
or permission.
The `CoinbaseSpotConfig` model rejects clearing its source-use hold even when
the exact terms version is acknowledged, because no validated permission and
intended-scope loader exists. Structural revalidation also rejects copied
configurations that attempt to clear the hold before adapter or transport
setup, and adapters reject injected transports with a different config model
or value. The adapter also requires the exact source-specific config type.
Parser/API fixture tests use a test-only in-memory transport and make no source
requests.
The 2026-10-28 terms refresh also records restrictions on third-party derived
data, benchmark/valuation uses, and AI/ML research use. The exact-version
acknowledgement and probe flag do not grant permission for Frontier analytics;
the runtime source-use hold remains until intended scope and any required
permission have been validated. See the
[current source-data terms review](SOURCE_DATA_TERMS_REVIEW_2026-10-28.md).

Cross-venue observations have independent clocks and freshness guarantees.
Different receipt times or a shared local timestamp do not prove simultaneous
availability, fills, legal access, or transferability. Preserve source and
receipt timestamps, raw hashes, adapter versions, quality flags, and each
exchange's timestamp semantics when evaluating a candidate.

On first persistence, the store fills a missing typed
`provenance.persisted_at_utc` in the normalized observation copy. It records
the Frontier writer's UTC time immediately before serialization and the
atomic SQLite insert; it is not a commit/fsync completion timestamp and does
not certify source-clock accuracy. The store does not mutate the adapter's
in-memory model. Already-stamped captures retain their timestamp when copied
to an isolated snapshot, keeping the immutable row hash stable. Re-appending an
identical capture keeps its first timestamp and row hash. Legacy observations
with this optional value absent remain readable and are not rewritten.

For new transport responses, `request_elapsed_monotonic_ns` measures from the
request start after source pacing until the full response body is received.
Inspect it as a per-request duration in the evidence disclosure; it is not a
cross-source timestamp or a clock-synchronization estimate. Complete HTTP
error responses retain this duration. Timeouts or connection failures without
a response body leave it unavailable.

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

Candidate cards can submit a user-entered annual carry rate (basis points) and
an optional post-settlement release delay (whole seconds) for each venue to
`POST /api/frontier/opportunities/capital-carry`. The request must
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
venue until the latest settlement among that venue's candidate markets plus the
entered delay. Delay defaults to zero, must cover every venue if supplied, and
is bounded to 31,536,000 seconds. It is hashed and independently checked, but
is only a virtual scenario input; it does not predict redemption, withdrawal,
or reuse timing. This conservative duration may overstate individual-leg holding time. It is not an
exchange fee or a financing offer. Unknown fees can remain excluded from the
candidate's capital amount. The response retains exact decimal values, both
run/candidate hashes, per-market observation IDs, validated normalized-store-row
and raw-body hashes, resolution evidence references, and the independent
arithmetic disposition. The result is
computed on demand and is not written to the Frontier database. It cannot change
candidate classification or practical eligibility; it does not establish
settlement truth, financing availability, legal access, transferability,
collateral eligibility, or executable returns.

## Virtual funding-currency sensitivity

Candidate cards can call
`POST /api/frontier/opportunities/funding-currency-sensitivity` with the exact
saved run ID/result hash, candidate ID, and one virtual funding assumption per
candidate venue. Each assumption specifies a full namespaced funding-asset
identity, nonnegative balance, an explicit rate oriented as candidate target
asset units per one funding-asset unit, and a conversion fee in basis points.
The API reads the hash-pinned replay candidate, applies the existing held-source
filter, and makes no market request or database write.

For target capital `S`, rate `r`, and fee `f` basis points, it calculates
required funding as `S / (r * (1 - f/10000))`, balance value after fees as
`B * r * (1 - f/10000)`, and the fee in target units as
`S * f / (10000 - f)`. The same-identity case requires rate 1 and fee 0.
Distinct assets, including same-ticker tokens on different networks, receive no
parity assumption. The UI leaves different-identity rate and fee fields blank;
both must be entered before submission. Values are not rounded. Decimal
results are checked by an independent Fraction calculation and bound to input
and result hashes.

Venue-local balances remain isolated and are never pooled. Schema version 2 adds
a separate outcome-level P&L sensitivity: it subtracts the modeled conversion
fee from every terminal state only when the candidate's independent economic
audit verifies, every leg fee is known, the funding audit verifies, and every
venue balance covers its recorded capital requirement. The Fraction audit
recomputes both the modeled conversion fee and each adjusted state value. When
one of those checks is unavailable or disagrees, the response includes a
reason and no adjusted P&L values. This does not mutate the candidate's saved
P&L or classification.

No conversion is performed or confirmed. The response counts candidate legs
with unresolved modeled fees and does not establish a conversion market,
transfer path, legal access, custody, collateral, FX timing, or executable
availability. Do not describe a covered virtual balance or positive modeled
terminal-state sensitivity as funded, tradable, or realized profit.

## Development test execution

The older 219- and 379-test Frontier counts elsewhere in this document are
earlier checkpoints. On 2026-10-28 at 09:01 UTC, the full `tests/frontier` suite
passed **387/387** in one process after the test I/O guard was extended to the
separate genuine Polymarket capture root. Pytest time was 29.38 seconds. The
prior 08:46 run took 29.38 seconds of pytest time and 30.82 seconds wall time,
peaked at 378,704 KiB RSS, used no swap, and recorded zero filesystem input;
those measurements were not collected for the 09:01 run. The 09:01 run emitted
the existing Starlette/httpx
`TestClient` deprecation warning. After a formatting/type-only cleanup, the
57 affected collection/API, FX, and timeline cases passed again; strict mypy,
Ruff check/format, and `git diff --check` passed. The tests are fixture-backed
and the source-use guard continues to deny held captures.

A later host sample at `2026-10-28T08:47:41Z` showed memory PSI avg10 **49.58%
some / 45.01% full**, while I/O PSI was below 1%. No cause was attributed and
no further broad test was started at that checkpoint. On 2026-10-28 at
`09:06:50Z`, memory PSI avg10 was 0% and I/O PSI avg10 was **1.35% some / 1.35%
full**. A local API/Vite smoke was stopped before starting a browser; no cause
is attributed. Recheck pressure before the next browser, broad test, or build.
At `10:13:59Z`, memory PSI avg10 was **37.05% some / 31.35% full** and I/O PSI
avg10 was 0%. Wait for both avg10 values to fall below the 1% admission gate
before starting tests, builds, or a browser. The current worktree completion
matrix and continuation state are recorded in the engineering report and
mission ledger.
At `10:17:35Z`, memory PSI avg10 remained above the gate at **9.69% some /
6.56% full** and I/O PSI avg10 was 0%. The Deribit venue screen is documented
separately; its public market data remains held pending written data-use
approval. No live probe was made.

At `10:22:00Z`, memory and I/O PSI avg10 were both 0%. A bounded captured-data
browser smoke then used only the isolated local API/Vite pair and the preserved
Polymarket store; it rendered the market, one-sided book, and saved raw-response
details. The observation GET returned HTTP 200, with no external requests or
source-probe/collection POSTs. Both listeners were stopped and capture hashes
were rechecked. This verifies that single read path only; continue to gate broad
tests, builds, or other resource-bearing work on a fresh PSI sample.

At `10:26:49Z`, memory PSI avg10 was 0% and I/O PSI avg10 was 0.02% some/full.
The follow-up UI verification used a temporary byte-identical copy of the
captured Frontier store under
`/tmp/midas-frontier-live-ui-id-20261028T1026Z/`; all write-capable roots were
also under that temporary directory and all source probes were disabled. It
verified the displayed observation ID and immutable evidence GET, then stopped
both servers. The original capture hashes were unchanged.

At `10:28:32Z`, memory and I/O PSI avg10 were both 0%. The focused offline
FX/capital-carry verification passed `test_fx_sensitivity.py` and
`test_capital_carry.py` (45 tests, 0.54 seconds) with `--basetemp` at
`/dev/shm/midas-frontier-fx-capital-20261028T1027Z`. It used fixtures and did
not read the preserved public capture or any protected service state.

The bounded fixture-backed fee review then passed
`tests/frontier/test_kalshi_fee_sensitivity.py` (21 tests, 0.52 seconds) with
temporary state at `/dev/shm/midas-frontier-fees-20261028T1030Z`. It made no
network request. At `10:29:58Z`, memory PSI avg10 was 0%; I/O PSI avg10 was
0.02% some / 0% full. Keep account-specific fee authority and live source use
classified as unverified.

After a fresh admission sample below 1%, the full Frontier suite passed
**390/390** after the verified-payoff duplicate-row fix. Pytest temporary state
was placed at `/dev/shm/midas-frontier-payoff-regression-20261028T1033Z`; run
time was 29.51 seconds. The three new model-invariant tests passed separately;
strict mypy, Ruff, and formatting checks for the changed Python files also
passed. At `10:34:45Z`, memory PSI avg10 was 0% and I/O PSI avg10 was 0.04% some
/ 0% full. Peak RSS, swap, filesystem I/O, and sustained capacity were not
measured in this regression.

For a broad suite run, first sample `/proc/pressure/memory` and
`/proc/pressure/io`; defer when memory or I/O PSI avg10 is at or above 1%.
The successful run placed pytest temporary files on tmpfs, reducing block I/O:

```sh
frontier_run_id=$(date -u +%Y%m%dT%H%M%SZ)
frontier_basetemp="/dev/shm/midas-frontier-pytest-$frontier_run_id"
test ! -e "$frontier_basetemp" || exit 2
PYTHONPATH=packages \
  /home/charlie/midas/.venv/bin/python -m pytest -q tests/frontier \
  --basetemp="$frontier_basetemp"
```

Use a new path for every run because pytest resets its `--basetemp` directory.
Check that the path does not already exist and that `/dev/shm` has enough free
space before starting. Tmpfs reduces disk writes but consumes RAM; stop the run
if host pressure exceeds the gate. This command uses fixture/local state only;
it does not authorize live source requests, workers, service changes, or
production deployment.

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

## Conditional joint-state basket replay

`POST /api/frontier/replay/joint-state` evaluates a bounded all-long basket
across **two to four** stored open event markets. The caller must supply an
explicit shared-state map with **two to sixty-four** rows. Each row projects
every local outcome into that joint state; the API validates complete coverage
and derives a canonical map ID from the normalized definition. It never
discovers or certifies the shared states. The map is an unauthenticated
research assertion and remains unverified semantic evidence.

The request references saved market and book observations. The map's assertion
timestamp must postdate the selected market metadata. Replay uses those stored
records only; it makes no exchange request and does not load newer market or
book data. Selected markets must provide exhaustive verified event payoffs and
resolution metadata, share settlement asset identity and payout currency, and
have the same future close and settlement timestamps. Search is bounded to
twelve total instruments and 4,095 subsets. Position legs retain venue-native
quantity units; Frontier does not assume that a share on one venue converts to
a contract on another.

The independent audit recomputes the constant-payout arithmetic over the
pinned map and stored quotes, but it cannot establish that the map is complete,
semantically correct, or jointly attainable. A positive result is therefore
classified as conditional. No practical execution eligibility is emitted;
capital transfer, simultaneous access, execution, settlement, and venue
restrictions remain outside this calculation. Mission Control exposes the
same definition fields in Replay & Readiness and requires each projection cell
to be entered explicitly.

## Joint-state search resource check

Run the reproducible synthetic ceiling benchmark from the repository root:

```bash
PYTHONPATH=packages:. /usr/bin/time -v /home/charlie/midas/.venv/bin/python tests/frontier/benchmark_joint_state_search.py
```

It measures two fixture markets, twelve instruments, sixty-four asserted
states, and 4,095 subsets without reading a store or contacting a source. The
current three-run, one-candidate measurement had a 0.101767-second median and
0.104521-second maximum at 70,576 KiB process peak RSS. A one-run eight-result
sample took 0.174308 seconds at 71,460 KiB. The fixture deliberately makes
3,969 subsets satisfy a constant payout; these are not venue results or
opportunity evidence. The figures bound this local code path only and do not
establish request latency under load or sustained resource capacity.

## Event-time Arena replay

`POST /api/frontier/arena-timeline-replay` uses only the bounded local Frontier
market, book, and effective verified-relationship records. It stages a
content-addressed immutable snapshot, then requests a `frontier_timeline` job
under Arena's normal global admission gate. Each worker is capped at 300
seconds, 512 MiB, 50% CPU, nice 15, and idle I/O; this job kind is network
restricted. The API response reports `network_calls: 0`. It does not start a
collector or query a source.

The saved timeline UI remains read-only until the researcher explicitly submits
the job. Replay is disabled until at least one saved market is available. The
result page shows per-frame book freshness/exclusion counts, source-state
labels, candidate classifications, and hash identities. These are hypothetical
research outputs and do not demonstrate simultaneous quotes, fills, venue
access, or profit. A frame with no explicit source-state event must not be read
as evidence that the venue was healthy; receipt-time book freshness is reported
separately.

Recorded source-health events must name the SHA-256 row digest of a collector
checkpoint. Before staging, the API opens the existing collection journal in
read-only mode, validates the run-spec hash and complete per-run checkpoint
chain, and compares the event's venue, check time, mapped state, and reason with
the checkpoint. The request cannot choose a different health claim while
reusing a valid digest. `healthy`, `degraded`, and explicit `unavailable` states
are mapped; `not_probed` and `unsupported` do not imply availability. Held
venues are rejected before the journal join. A missing or unknown digest does
not create a journal and returns an input error; a corrupt journal fails closed.
The stored state is the collector's adapter-local state at its check time,
derived from that adapter's request history. It is not a continuous venue
health feed, a reachability guarantee, or evidence of account eligibility.

Up to 100 digest references are joined in one bounded journal scan; each
selected run's complete checkpoint chain is then revalidated. The checkpoint
hashes are pinned in the content-addressed schema-2 timeline snapshot. Existing
schema-1 snapshots without recorded health remain readable. `fixture` and
`scenario` events remain explicitly labelled. Arena history, result, and
Frontier readiness checks filter snapshots that use currently held venues. A
completed artifact counts as readiness evidence only after its job binding,
snapshot/result hashes, and worker runtime record verify. No timeline worker
was launched for the current implementation checkpoint; readiness therefore
remains pending.

The Replay & Readiness panel exposes a maximum book receipt age from 1 to
3,600,000 milliseconds. Invalid values disable submission. The selected limit
is sent to the local-input API and pinned into the replay snapshot.

The panel also reads `GET /api/frontier/collection-health-events?limit=20` when
opened. This is a local, read-only journal lookup: a missing journal stays
missing, held venues are omitted, and each returned checkpoint's full run chain
is verified. Only the latest timestamped health observation per collection run
is listed. Timestamp-less `not_probed` health has no replay event and leaves the
last timestamped observation visible; timestamped unsupported states do not
revive an older availability claim. Each item shows its venue, state, check
time, adapter version, checkpoint sequence, last success, and digest. All items
start unchecked. Selecting one includes its hash-bound `basis=recorded` event
in the next explicit timeline submission. The API reports `network_called: false`;
no collector is started and no exchange is contacted.

Only one source-status event per venue and check timestamp can be submitted.
The API rejects duplicates before staging a job because the event-time engine
cannot resolve two status claims at the same instant. In the UI, selecting one
of two same-time checkpoints disables the other until the first is deselected.

## Finite source collection module

`midas.frontier.collection.BoundedSourceCollector` implements one finite,
sequential source run with append-only checkpoints. Frontier exposes one
operator-triggered `POST /api/frontier/collect/{venue}` request from the
Exchanges view. It calls the collector directly in the API request lifecycle,
shares the per-source lock with other probe routes, and starts no Arena job,
systemd unit, timer, or background service. Nothing is collected on page load.
The endpoint can make public GET requests only after the source's enabled and
live-probe flags are set and its source-use hold is absent. Tests inject fixture
adapters and make no exchange requests.

`start` verifies adapter enablement, the source public-probe flag, policy hold,
declared discovery/book capabilities, and request limits. Its standalone
module bounds are 20 markets, 10 book tasks, depth 20, 16 MiB of captured
evidence, and five minutes wall time. The API applies smaller hard caps of five
markets, two books, depth ten, 4 MiB, and 60 seconds. Mission Control submits
three markets, one book, depth five, and 30 seconds. The per-source loop is
sequential and records failures independently. A restart through the module
resumes from the last append-only checkpoint and revalidates its sequence/hash
chain and pinned adapter version/config; it does not silently relaunch a
terminal run. `GET /api/frontier/collection-runs?limit=20` lists one bounded
page of recent runs and verifies each selected checkpoint's complete hash
chain. If `next_before_run_id` is present, pass it as `before_run_id` to read
the next older page. The API validates the cursor run's stored specification
and full checkpoint chain before using it as a keyset anchor; pages scan the
1,000-run journal ceiling in bounded batches, and newer appended runs do not
shift older pages. Held-source entries remain excluded. The read does not
initialize a missing journal or contact a source. Mission Control exposes
explicit “Load older runs” and “Newest runs” controls and resets to the newest
page after a collection start or resume. The Exchanges view offers an explicit
`POST /api/frontier/collect/{venue}/{run_id}/resume` action for a nonterminal run
only when current source flags, source-use policy, adapter version, capability
manifest, and the API's smaller request bounds still match the pinned spec.
Completed, partial, and failed runs are terminal. A resume is one request-bound
attempt; it does not start an automatic retry loop.

The collector journal (`frontier-collection.sqlite3`) is separate from the
Frontier observation database but stored under the selected Frontier root. It
is capped at 64 MiB, 1,000 runs, 100 checkpoints per run, and 20,000 total
checkpoints. Keep its store away from Reality, Veritas, frozen campaigns, and
other historical evidence. The current endpoint and UI path are fixture
verified only; no live collection was started and no service was changed.

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

`RESPONSE_TOO_LARGE` means the declared content length or bytes yielded by the
response stream crossed the configured cap. The adapter rejects the response
without retaining its body and makes no retry. The diagnostic observation has
an empty raw body marked `not_captured_after_size_limit`; its normalized
`response_rejection` records the configured limit, rejection stage, declared
length when available, and bytes yielded. The raw SHA-256 is for the empty
stored body, not the rejected source response. Partial transport interruptions
without a complete body remain unpersisted.

For Polymarket event groups, the current official
[Gamma discovery reference](https://docs.polymarket.com/market-data/discover-markets)
documents an event response with an embedded market array, plus individual
market-ID reads and a paged market-keyset listing. It does not document
child-market pagination keyed by Gamma event ID. If the event response exceeds
the cap, retain it as incomplete. Hydrating known market IDs separately cannot
establish an exhaustive outcome set.

The Polymarket v2 trades route is a single explicit page. Its cursor is bound to
condition and page size, and each request repeats the bounded source filters.
There is no automatic continuation or background history crawl. The same
principle applies to the one-page Kalshi operations: a source cursor is retained
as evidence but is not followed without a separate explicit request.

Polymarket's `price_history` capability is another explicit action. The Market
detail view requires an outcome token from saved market evidence and requests a
single `1d` or `1w` source interval over at most seven days. A 30-day and a
36-day range were rejected by the source with HTTP 400; the official reference
does not publish the maximum accepted range, so seven days is the current
conservative cap. The adapter retains the native response and rejects more than
1500 points or any response above its configured byte limit.
`GET /api/frontier/price-history` returns persisted evidence only. The point
model has no OHLC or volume fields;
do not treat the samples as executable quotes or synchronized cross-venue
observations. The source documents token IDs and the endpoint parameters in the
official [CLOB price-history reference](https://docs.polymarket.com/api-reference/markets/get-prices-history).

To reproduce stored samples locally, submit 1..8 history observation IDs to
`POST /api/frontier/price-history/replay`. The operation is network-free and
accepts only immutable saved `historical_price_points` records with consistent
raw hashes, receipt metadata, and any saved market binding. It records a
separate append-only replay artifact; this is a descriptive sample audit and
does not generate quotes or opportunity candidates. Read list/detail artifacts
with `GET /api/frontier/price-history/replays` and
`GET /api/frontier/price-history/replays/{run_id}`. Missing or held-source
evidence is rejected for new runs and omitted from saved reads. The capture
coverage summary scans at most 20 newest stored series, labels repeated
overlapping points, and reports adjacent returned-point gaps without inferring
completeness or expected cadence. The SQLite schema advances to version 7 and
adds a dedicated replay table; an existing schema 6 store is migrated in place
when the normal Frontier store initializer runs. Development tests use
temporary databases; no service store was migrated for this milestone.
The Market detail interface offers replay only after the researcher presses
“Replay saved series” for an identified stored capture. Replay & readiness uses
20-row local pages for both source captures and saved artifacts, with
Previous/Next controls. The API looks ahead by one row to return `has_more`;
its `offset` remains bounded to 100,000. Source selection is limited to eight
rows on the current page and is cleared on page changes. Saved replay pages
omit held-source rows and report the omitted count for the visible page; the
offset traverses stored rows, including held ones, so later eligible artifacts
remain reachable. Selecting a saved artifact reads its hash-verified detail
and displays its per-series observation ID, raw hash, instrument, optional
market binding, request interval, receipt context when available in the source
page, and sampled-point bounds. These reads are local and make no source
request.

To verify the populated-store browser path, run the explicit seeded E2E from
`apps/web`:

```bash
MIDAS_SEED_FRONTIER_E2E=1 corepack pnpm exec playwright test e2e/frontier.seeded.spec.ts
```

Playwright creates a fresh `midas-browser-*` directory under the system temp
directory. `e2e/seed_frontier_store.py` writes 21 clearly labeled deterministic
captures and their 21 replay artifacts there; the test then reads both real
local API pages, submits one local replay, and inspects its stored lineage.
The seeder refuses to overwrite an existing Frontier database. Without the
explicit environment flag, the seeded test is skipped and the normal browser
suite retains its empty temporary store. The fixture URLs identify the source
shape only; the seeder performs no HTTP request and does not validate a live
venue response.

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

## Discovery-scope Arena comparison

The Replay & Readiness view can submit
`POST /api/frontier/arena-discovery-comparison`. It reads only the selected
Frontier store's latest bounded records, includes only joined books and
effective verified relationships, writes a content-addressed snapshot under the
configured Arena root, and submits a `frontier_discovery` job through normal
host-wide Arena admission. It makes no exchange request and does not start a
collector. Held-source rows are filtered before the snapshot is created.

The worker compares Polymarket-only discovery, venue-local discovery (one
replay per observed venue), and cross-venue discovery over the same evidence,
scenario, UTC time, and deterministic replay version. Venue-local counts pool
the per-venue outputs. This is a discovery-coverage comparison under one
implementation; it is not an algorithm-version comparison or an estimate of
exchange-wide opportunity prevalence. Cross-venue candidates require saved
verified relationships. The output does not authenticate their external
assertions or establish simultaneous quotes, fills, legal access, or profit.

Bounds are 100 markets, 200 books, 500 verified relationships, an 8 MiB
snapshot, 128 MiB/1,000 snapshots in the snapshot store, 32 MiB per result, six
unique replay artifacts, and 20,000 candidate summaries per scope. Arena also
applies the existing 300-second, 512-MiB, half-CPU, nice-15, idle-I/O and
host-resource gate. Inspect recent jobs at
`GET /api/arena/frontier-discovery-comparisons?limit=20`; fetch a completed,
hash-verified result at
`GET /api/arena/jobs/{identity}/frontier-discovery`. A denied admission leaves
the saved snapshot available for a later explicit retry; do not bypass the
shared lock or resource gate. The systemd launch also restricts this job to
AF_UNIX socket families; the discovery worker has no HTTP client or exchange
request path. Fixture tests have now exercised the durable `midas.arena.jobs`
dispatch in a child process and checked the generated systemd restriction
command. The launch command was inspected with a mocked `systemd-run`; no
systemd service ran, so cgroup enforcement and shared-lock admission remain
unverified for this job kind.

The staging query examines at most 200 recent saved book observations and keeps
the newest locally received book for each pinned instrument. The resulting
snapshot retains that record's observation ID. This is a deterministic store
selection rule; use each book's receipt/exchange timestamps and quality fields
when interpreting age, and do not describe separate venue observations as
simultaneous quotes.

For a completed, integrity-verified artifact, Mission Control groups candidate
detail by the arm's pinned replay IDs and checks its identity, family,
classification, audit disposition, and worst-case outputs against the summary.
The expanded read-only view is capped at the first 50 candidates per scope. It
shows exact decimal costs and prices, native leg units, quote denomination,
displayed depth and book IDs, terminal-state results, timing uncertainty,
practical-eligibility state, the independent arithmetic audit, assumptions,
and hashes. Additional rows are counted instead of expanded. If a summary has
no matching detail, the panel reports the artifact mismatch. The browser check
uses a clearly labeled intercepted fixture; it does not establish that an
Arena supervisor job completed or that a candidate is live or executable.
Terminal values are labeled hypothetical modeled P&L; the detail view states
that they do not establish fills, venue access, or realized profit.

The Laboratory's **Frontier research** tab is another read-only client for the
same `GET /api/arena/frontier-discovery-comparisons?limit=20` and
`GET /api/arena/jobs/{identity}/frontier-discovery` routes. It can select any
retained completed discovery job and displays an artifact only when the API's
content-integrity verification succeeds. It does not submit or retry Arena
jobs; use Frontier's discovery workspace for that action, where normal resource
admission applies. The Laboratory tab neither copies data into Laboratory's
single-market dataset schema nor starts a source request. A failed integrity
check withholds summary details and should be treated as an artifact error, not
as an empty or zero-result study.

Lazy Mission Control workspaces show a loading message while their code chunk
loads. If a workspace chunk or render fails, the workspace shows an accessible
error alert instructing the operator to refresh Mission Control; other mounted
workspace shell content remains available. The current boundary does not offer
an in-place retry for a rejected chunk.
