# Gate A checkpoint 045 — 48-snapshot coverage replay

**Captured:** 2026-10-16 04:02 UTC
**Mission status:** active; the bounded discovery panel and 24-hour pilot remain in progress.

## Offline market-universe coverage

The A1 replay completed at 03:47:39 UTC using saved snapshots only. It verified all snapshot evidence hashes and retained Gamma and CLOB response hashes across 48 scans and 31,353,007 compressed bytes. It issued no live HTTP requests.

| Measure | Result |
| --- | ---: |
| Distinct Gamma market IDs in the bounded query unions | 5,903 |
| IDs eligible for the supported V1 pair rule at least once | 2,135 |
| Distinct selected market IDs | 849 |
| Selected pair observations | 1,920 |
| Current-replay quality-valid observations | 1,660 / 86.46% |
| Invalid observations | 260 |
| Positive top-gross pairs | 0 |

All 48 classifier replays match the stored eligible-market counts. The six query frames each add eligible IDs conditionally on the other five frames. Their mean marginal eligible-ID contribution is 10.83 high-liquidity, 38.10 low-liquidity, 30.75 medium-liquidity, 5.15 near-expiry, 23.54 rotating-control, and 49.92 tagged-near-expiry IDs per scan. The mean bounded union is 298.79 Gamma IDs and 158.81 eligible IDs per scan.

The latest saved scan is scan-20261016T033156Z-fda52aa72c22. Its bounded union had 296 Gamma IDs: 129 eligible and 167 excluded. Forty markets were selected, 32 pairs passed quality checks, and eight had an empty ask side. Reported update age exceeded five seconds on both legs in 27 pairs; no pair exceeded 250 ms reported timestamp skew. These timestamp fields do not establish venue sequence or atomicity.

The 48-scan union contains 5,903 market IDs, 5,903 condition IDs, and 11,806 outcome asset IDs. The selection panel spans 849 IDs. The latest eligible metadata contains 48 high-, 63 low-, and 18 medium-liquidity IDs; expiry bands contain 26 long-duration, 48 medium-90-day, and 55 near-seven-day IDs; spread bands contain 36 medium, 67 tight, and 26 wide IDs.

One legacy capture-versus-current-replay validity counter discrepancy remains on scan 1: the stored count is 5 and current replay is 32. The 27-observation difference is disclosed in the artifact rather than rewritten into history.

## Latest scan beyond the A1 artifact

The observer finalized scan-20261016T040030Z-56b893816f32 at 04:00:30 UTC, after the offline coverage artifact was captured. Its bounded union contains 298 Gamma IDs: 127 eligible and 171 excluded (114 unverified augmented negative-risk semantics and 57 unsupported outcome relationships). It selected 40 markets; 31 pairs passed quality checks and nine did not. All top-gross, full-depth, minimum, and fee gates are zero. Reported update age exceeded five seconds on both legs in 25 pairs; no pair exceeded 250 ms reported timestamp skew. Scan 49 is reported separately and is not included in artifact 003.

## Fixed measurement pilot

The separate v1 pilot remains running at 18/48 completed scans: 588/720 selected slots pass quality checks (81.67%), across 434 distinct selected market IDs. It has 132 invalid slots and one skipped scan sequence after the scan-45 code-hash mismatch. Rotating stratified selections yield 567/666 valid slots (85.14%); frozen stable controls yield 21/54 (38.89%). This comparison is descriptive and nonrandomized. The fixed stop remains 2026-10-16 19:00:55 UTC. No pilot plan, state, or campaign was changed.

## Evidence and limitations

The artifact is docs/VERITAS_MISSION2_MARKET_UNIVERSE_COVERAGE_003.json with SHA-256 aa9e59a360324d6480a27b63447868ccc5519c905eb02002b37277485a249634. Its snapshot-manifest digest is 56f38792b3c25ab352e5c1fe9ac0e76f15c73e58d599522d421ca531804f3f79.

The six-page discovery union is bounded by upstream query filters; it is not a venue-wide denominator. Repeated snapshots are selected and temporally dependent. This report does not establish continuous quotes, venue update frequency, order arrival, fills, or profitability. The active Reality recorder remains configured for eight markets; the broad panel is an intermittent snapshot screen.

The focused dashboard API and coverage tests passed 26 tests together, including two market-universe coverage tests. Ruff, formatting, strict Mypy for the changed API module, and git diff whitespace checks passed. No service, collector, pilot, or frozen campaign was changed.
