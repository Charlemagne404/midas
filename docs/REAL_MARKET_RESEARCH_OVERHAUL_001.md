# MIDAS Real-Market Research Overhaul 001

**Assessment date:** 2026-10-25
**Implementation branch:** `codex/real-market-research-overhaul`
**Deployment state:** prepared in an isolated worktree; not deployed

## Executive result

This work makes the public-market observation path more resilient and makes its conclusions easier to qualify. It adds per-asset CLOB validation and targeted recovery, an explicit bounded reference cohort, v6 source and independent-economic re-auditing, crash-recoverable SQLite indexes, freshness and measurement status fields, and round-robin schedule dispatch with durable decisions.

The strongest finding is operational and scientific: the active Veritas store has 513 snapshots and 513 v4 analysis events, but the published `research-summary.json` and `latest-summary.json` stop at scan 423 from 2026-10-23. The v4 analysis state contains all 513 scans, so the evidence exists; the summaries did not advance with it. The summary file is 2,097,481 bytes, 329 bytes beyond the old 2 MiB reader bound. The new v6 analyzer discovers snapshots from the immutable directory and publishes a bounded summary from a durable SQLite ledger.

On the complete stored v4 event set, 20,514 selected observations cover 3,902 distinct markets. The source replay marks 18,312 quality-valid, of which 3,855 pass the legacy strict-freshness rule. No positive top-book gross edge appears. These are selected, repeated public snapshots, not independent market trials or evidence of venue-wide prevalence, fills, or exploitable profit.

## Runtime and protected boundaries

- The active checkout inspected was `/home/charlie/midas-veritas`, branch `project/veritas`, commit `3b102928`; it was clean during inspection. Its observer reports protocol `veritas-public-observatory-v2`, and its current full analysis is v4.
- User timers for the Veritas observer and research director were loaded and waiting. No observer or research-director process was running at the process check.
- Changes in this report are in the separate `midas-veritas-research-overhaul` worktree. No code was copied into the active checkout, no timer or service was restarted, and no Reality recorder or campaign was touched.
- No authenticated request, wallet operation, order, or real-money action was made. No new 48-hour campaign was started.

## Existing observation lifecycle

The active v2 path makes six bounded Gamma queries, normalizes and deduplicates market records, selects a rotating cohort and frozen controls, retrieves complementary CLOB books, applies pair quality and economic checks, and writes a compressed immutable scan snapshot. The v4 analyzer replays those snapshots into per-scan events, a cumulative state file, and a JSON research summary. Research Director and Arena qualification consume the newest summary/event and may create bounded offline research work.

The frozen v4 summary currently covers 423 scans, while the v4 state and event directory cover 513. The last state scan is `scan-20261025T210108Z-fb8d059e438f`; the latest summary names `scan-20261023T233202Z-dc4f690bd80f`. That leaves 90 committed scans absent from the published summaries. This reproduces the summary/index split implicated by 48H-002 at larger scale: immutable evidence and derived events can exist while a size-bounded summary reader prevents publication.

### Archived v4 evidence

Read-only aggregation of all 513 v4 event files produced:

| Measure | Observed |
|---|---:|
| Scans / selected market observations | 513 / 20,514 |
| Distinct selected markets | 3,902 |
| Repeated visits beyond the first visit per market | 16,612 |
| Markets observed at least five times / maximum visits | 1,650 / 72 |
| Quality-valid pairs in v4 replay | 18,312 |
| Legacy strict-fresh pairs | 3,855 (21.05% of quality-valid) |
| Positive top-book gross pairs | 0 |

The selected observation set is dependent: most observations are revisits, and the scan cadence is about 30 minutes (median 30.0008 minutes). The roles in this history are 20,173 `rotating_stratified` visits and 341 `stable_random_control` visits. There is no reference-random cohort in the archived events, so this history cannot estimate an unbiased opportunity prevalence even within a stable venue-wide frame.

Across 18,312 valid v4 edge observations, the reported edge per share ranges from `-0.998` to `-0.001`; the median is `-0.021`, the 90th percentile is `-0.003`, and 6,175 (33.72%) are within one cent of zero. All remain negative. These are repeated snapshot observations, not 18,312 independent opportunities.

The selected category labels are overlapping and conditional on the bounded Gamma query frames. Politics appears most often (9,620 category assignments), followed by Recurring (5,169), Trump (4,472), and Crypto (3,769). Those assignments are not a category prevalence estimate.

### Freshness diagnosis

The v4 state attributes 14,456 of 18,312 quality-valid pairs to reported update age above five seconds; only one pair exceeds the 250 ms reported YES/NO timestamp-skew gate. The two leg age counts are equal (14,456 each). The measured failure is therefore dominated by old source-reported timestamps, not cross-outcome skew.

The old snapshots do not retain monotonic request timing for the full pipeline. They cannot determine whether the old reported timestamps reflect upstream quote age, provider timestamp semantics, queueing before MIDAS queried, or source clock offset. They also do not establish a venue sequence or atomic book snapshot. The 48H-002 supplemental audit remains a separate selected campaign sample: 3,304 of 3,840 observations passed its quality checks and 640 of those passed strict freshness (19.37%).

## 48H campaign findings

The 48H-002 postmortem and supplemental audit were reviewed as incident evidence, not as a venue-wide sample. The key engineering failures were an 80-asset request returning 78 books and invalidating a 32-scan slice; 128 repeats of that deterministic batch; 448 resource deferrals in 577 ticks; 38 post-save observer failures; a 2 MiB summary-reader failure; stale summary discovery; 58 queued scans left behind; missing scheduler decisions; unmeasured results rendered as zero; and incorrect boolean aggregation.

The supplemental 96-snapshot / 3,840-observation audit found 3,304 quality-valid and 640 strict-fresh observations, no positive gross candidates at tested quantities, and no stored-v4 versus independent-v3 validity or edge disagreements in that selected sample. It also found no fee disagreement across 5,153 checks. Correlated selection limits the inferential scope.

48H-001 remained partial: it did not establish real execution labels or a demonstrated real-economic advantage. Its repeated observations and 48H-002 do not justify a claim that no opportunity exists outside the observed frame or sampling windows.

## Implemented changes in the isolated worktree

### Observation selection and retrieval

- The observer uses six explicit Gamma query frames with rotating stratified selection and a separately recorded `reference_random` cohort. The random cohort is drawn before adaptive rotation and reports its probability and bounded-frame denominator. Selection does not use price edge. Frozen controls, reference observations, and adaptive selections remain distinguishable.
- The protocol remains conditional on the successful, eligible union of those bounded Gamma frames. It does not claim known inclusion probability over all venue markets. The 30-minute interval remains; the archived data does not justify a faster recurring campaign by itself.
- The public read budget is explicit: at most eight logical reads per scan, one retry per read, and at most 16 HTTP attempts. A scan normally uses six Gamma reads and one CLOB batch; the eighth logical read is reserved for a targeted retry.
- CLOB responses are checked per requested asset for missing, duplicate, unexpected, and malformed rows. Incomplete batches retain usable unrelated pairs. Only affected pairs are retried, with both legs requested together; retry books are not mixed with the initial batch for that pair. A remaining partial pair stays ineligible. The exact 80-request / 78-response regression verifies a two-asset targeted retry and unaffected-pair handling.
- Bounded failed-scan evidence is retained. Each request records local wall and monotonic start/receive/parse timing; the snapshot separately records persistence timing. Source-reported book time is never presented as a local request time or an exchange sequence.

### Economic and temporal verification

- The v6 source replay verifies Gamma and CLOB payload hashes, request-body identity when the original receipt contains it, pair membership in one hashed batch, saved-book correspondence, and snapshot identity before re-auditing. V4 and v5 event protocols remain readable; the new analyzer writes a separate v6 stream and catalog.
- Legacy single-batch snapshots without stored request-body hashes are supported as a lower-assurance compatibility path. Their request identity is explicitly marked inferred/unverified; the code does not invent a request hash.
- The first v5 replay checked source lineage but reused the scanner's pair auditor. Review found this was not independent enough for the stated audit goal. V6 adds [independent_economics.py](/home/charlie/midas-veritas-research-overhaul/packages/midas/veritas/independent_economics.py), a separate Decimal implementation for pair identity, tick validation, crossed-book rejection, top ask, depth, minimum constraints, and fee references. V6 excludes a pair when the reference path vetoes it or when exact calculations disagree; both results and disagreement reasons are retained.
- The v6 event reports `batch_atomicity_verified=false` and `sequence_verified=false`. Two individually fresh books are not called simultaneous. It remains a public-snapshot calculation, not a measured fill or execution result.

### Storage, indexing, and reporting

- `snapshot-catalog-v3.sqlite3` indexes immutable snapshots and market metadata with WAL and full synchronous durability. Reconciliation is bounded to 50 files per pass, independent of summary high-water marks, and quarantines bad content by file hash. A duplicate-observation transaction test verifies all-or-nothing insertion.
- `analysis-catalog-v6.sqlite3` is the exact-once event ledger. Per-scan event files are atomically published before the database transaction; the analyzer can recover a durable event that was written before a crash interrupted catalog application. The SQLite transaction updates the event, observation rows, independent-audit fields, and cumulative state together.
- The analyzer enumerates saved snapshots independently of the old summary. It caps per-run work at 100 snapshots, writes versioned v6 events, preserves old summaries byte-for-byte via streaming before rollover, and keeps the published per-market detail bounded. Historical snapshots and v4/v5 results are not rewritten.
- Catalog output distinguishes snapshot-captured counters from the independent v6 source and economic replay. Missing metrics are `null`, with partial totals and scan coverage; an empty catalog is `NOT_MEASURED`. The v6 independent view stays unavailable or partial until its ledger covers the indexed scans.
- The API summary reader bound is raised from 2 MiB to 10 MiB for compatibility. The v6 summary itself is bounded and compact; the larger reader limit is not the long-term storage mechanism.
- The Veritas API now reports absent measurements as `null` with an explicit `NOT_MEASURED` status. Empty policy collections no longer become a false `all_abstained=true` through Python's empty-`all()` behavior.

### Scheduling and compatibility

- The Arena dispatcher now rotates its cursor across schedule IDs rather than inspecting the same first 100 on every pass. It writes per-pass decisions and preserves a cursor across runs; malformed schedule records do not prevent other records from being considered.
- Schedule state transitions and controls append durable decision records with sequence numbers. The research director and qualification entry points can resolve a scan in v6, v5, or v4, without mixing versions in one qualification run. Frozen v4 reporting endpoints remain pinned to v4.
- Existing Reality admission and protected-service policy were not altered. This work does not claim that ordinary Veritas deployment or long-run operational behavior has been verified.

## Verification and benchmark results

### Automated tests

The final compatible Veritas and Arena API/scheduler set passed **288 tests** in 37.79 seconds. It includes independent-calculation, crossed-book, fee-curve, crash-recovery, and v6 catalog-join checks. Ruff lint and formatting passed on all 23 changed Python files, and `git diff --check` passed.

Two existing checkout issues prevented a clean all-Veritas collection: `tests/test_veritas_gap_detail_v2_batch.py` imports `midas.veritas.gap_detail_control`, which is absent from the active `project/veritas` branch; and `tests/test_veritas_gap_detail_v2_release.py::test_frontier_admission_overlay_pins_analyzer_and_systemd_runtime` compares a pinned release manifest expecting 73 package files with 61 files present in this checkout. Neither file is part of the changed implementation. The pinned release artifact was left untouched.

The full `tests/arena` suite was also attempted but stopped after more than five minutes of sustained CPU work at about 19% progress. It is **incomplete**, not passed. No such test process remains running. The regressions that did complete include missing/duplicate/unexpected/malformed CLOB assets, the 80-versus-78 case, persistent partial pairs, legacy request receipts, stale summary recovery, >2 MiB summary rollover, poison snapshot quarantine, idempotent reprocessing, crash-window recovery after event publication and after SQLite commit, unknown-versus-zero metrics, the independent crossed-book veto, Decimal depth and fee-curve agreement, 105-schedule rotation, and durable decision logs.

### Archived-data replay

An isolated v6 replay of one archived scan (`scan-20261022T190153Z-e8f434348254`) processed 40 selected pairs, 36 quality-valid pairs, 7 strict-fresh pairs, and zero positive top-book gross pairs. It agrees with that scan's v4 event and the campaign's per-scan audit. The v6 valid-edge range for this scan is `-0.194` to `-0.001`; the separate economic reference reported no disagreements.

An isolated v6 eight-snapshot replay sampled across the full stored interval processed 320 selected observations with no quarantines. It progressed through catalog batches of 4 and analysis batches of 3, 3, and 2; pending counts fell 5, 2, 0. V6 and the existing v4 source replay agree on each scan: 286 quality-valid, 68 strict-fresh, and zero positive top-book gross observations. The separate economic reference audited all 320 pairs, accepted the same 286, and recorded zero disagreements. The snapshot catalog's capture-time counters on that subset were 259 quality-valid and 63 strict-fresh; source replay recovers 27 more valid pairs and five more strict-fresh pairs. This discrepancy is why capture-reported validity is no longer conflated with independent replay validity. The separate catalog summary joins the two SQLite ledgers and reports `MEASURED` only after all eight replay events match indexed snapshots by identity and content hash.

### Single-snapshot microbenchmark

The v4 analyzer and v6 analyzer were run once each on the same archived scan in separate isolated roots. V6 performs payload and pair-lineage checks, an independent economic calculation, and transactional SQLite indexing. It was slower on this single run; this is a tradeoff, not a broad performance claim.

| Path | Wall time | CPU time | Process peak RSS | Event / summary bytes |
|---|---:|---:|---:|---:|
| Active v4 analyzer | 0.1058 s | 0.0874 s | 47,164 KiB | 18,225 / 26,944 |
| v6 analyzer only | 0.2020 s | 0.1337 s | 48,980 KiB | 131,662 / 30,412 |
| v6 scan catalog + analyzer + summary | 0.3136 s | 0.1954 s | 49,932 KiB | 131,662 event; 127 KiB scan DB; 84 KiB analysis DB; 30 KiB summary |

The bounded eight-snapshot replay took 1.8534 seconds wall time, 1.5102 seconds CPU, and peaked at 79,484 KiB RSS. Its isolated output root was 7,236,638 bytes. The one-snapshot outputs included the 567,662-byte copied snapshot; the v4, v6 analyzer-only, and v6 catalog-plus-analysis roots totaled 638,821, 815,752, and 1,008,264 bytes. These figures cover small copied samples; they do not demonstrate full-store performance or long-duration endurance. The v6 work costs more than v4 in this one-scan comparison, with independent arithmetic and durable indexes as the measured tradeoff.

The exact sample IDs, measurements, test boundary, and source-file digests are recorded in [the benchmark artifact](REAL_MARKET_RESEARCH_OVERHAUL_001_BENCHMARK.json).

### Bounded fresh public observation

One read-only scan was run against the public Gamma and CLOB endpoints into a temporary root, using the smallest supported pilot cohort: 30 selected markets, 4 frozen controls, and 4 reference-random selections. The six Gamma calls returned 300 records with two duplicate records and 298 unique IDs; 107 were eligible same-condition pairs in the bounded union. The one CLOB batch requested and received all 60 assets, passed missing/duplicate/unexpected/malformed checks, and needed no retry. The scan made seven HTTP attempts in total.

The scan selected 22 rotating-stratified observations, 4 controls, and 4 reference observations. Independent v6 replay matched the immutable snapshot and catalog by hash, then classified 23 of 30 pairs as quality-valid, 9 as strict-fresh under the existing reported-age/skew gates, and none as positive top-book gross. The separate economic reference agreed on all 30 audited pairs. Fourteen pairs failed the reported-age limit on each leg; none failed the cross-outcome skew gate. Seven were invalid because one ask side was empty. The valid edge distribution had 12 observations in `-0.01..0`, 7 in `-0.05..-0.01`, and 4 below `-0.05`. These are one bounded scan, not a prevalence estimate.

Locally measured Gamma request durations ranged from 74.6 to 261.1 ms; the CLOB request took 75.95 ms. The snapshot persisted 151.59 ms after the final public response. Source-reported quote ages remain distinct from these local timings, and the upstream clock offset and exchange-side ordering remain unknown. The snapshot catalog indexed one scan, the v6 analysis ledger processed one scan with zero backlog, and the temporary capture retained the original hashed source payloads. No authentication or orders were used.

## Conclusions and limits

The current observed frame shows negative gross edges near zero at its upper end and no positive gross top-book pair. The most defensible conclusion is: **this selected intermittent observation set has not produced a gross-positive complementary-pair candidate under the tested conditions.** It cannot establish venue-wide absence, quote persistence between 30-minute scans, competition at the venue, fee-adjusted execution, settlement correctness, or real fills.

The large freshness loss is measurable as reported book age, but source clock offset, upstream timestamp semantics, and venue event order are unknown. Public snapshots cannot substitute for a synchronized exchange stream. The absence of fills is a data limitation, not a result that can be imputed from book depth.

## Prioritized next work

1. Review and deploy this worktree into the ordinary Veritas runtime only after the source diff and operator bounds are accepted. No deployment has occurred here.
2. Run a bounded v6 replay over the stored 513-snapshot set in a dedicated isolated root, compare every per-scan v4/v6 result and independent-economics disagreement, and record resource and mismatch causes before any wider indexing change.
3. After safe deployment, confirm v6 indexing catches up to the immutable snapshot directory, and verify summary discovery, API output, scheduler decisions, and rollback on the live ordinary Veritas path. Do not restart Reality.
4. Collect a bounded public timing study with the new monotonic request instrumentation to separate local request and persistence delay from reported quote age. Keep the 5-second and 250-ms criteria until evidence justifies a versioned change.
5. Build a versioned point-in-time settlement-label collector using independently checked public resolution data. Treat Gamma close/display fields as candidate metadata until their semantics and timing are verified. Real execution labels remain unavailable.
6. Keep a probability-based reference cohort in every new sampling protocol and report conditional rates with market-cluster and time-block uncertainty only when the design supports it. The existing history is not a substitute for that cohort.
7. Extend research scheduling to prioritize expected information gain and explicit hypotheses while preserving queue fairness, bounded retries, and a durable explanation for every deferral.

## Artifact and deployment status

Implemented and tested changes are prepared in the isolated worktree. The 513-snapshot historical data, v4 summaries, 48H campaign records, and protected Reality evidence are unchanged. No code is deployed, no fresh public campaign was launched, and no real-market conclusion here is presented as execution validation. The full Arena suite and long-duration endurance remain unverified.
