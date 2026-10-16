# Gate A checkpoint 034 — scan 38 and frozen-control availability

**Captured:** 2026-10-15 22:52 UTC
**Mission status:** active; the observer, fixed measurement pilot, and bounded analysis schedules remain enabled.

## Scan 38

Scan `scan-20261015T223101Z-62913d43b3c1` was captured at 22:31:01 UTC. Its six bounded discovery queries returned 300 candidate records, one duplicate, and 299 unique market IDs. Of these, 111 met the supported same-condition V1 pair rule and 188 were excluded. The observer selected 40 pairs; 34 passed the request/receipt quality gate and six failed due to an empty ask side. No positive top-gross state appeared.

The persisted v3 Arena qualification subsequently processed all 38 finalized snapshot events in job `job-25b10231cab34b16bfbc5b25`, which exited 0 after 2.323 seconds. Across the 38-snapshot panel it found 1,341 quality-valid pairs over 710 selected market IDs. The top-pair edge distribution ranges from -$0.996 to -$0.001 per share, with a -$0.020 nearest-rank median. Positive counts are zero at the unchanged top-ask gate, full displayed depth, both per-leg minimums, single-match fees, and fragmentation-safe fees. Candidate evidence is complete with zero rows; the empty replay reports `NO_POSITIVE_CANDIDATES_TO_REPLAY`. No authenticated request or order was submitted. This is a qualification result, not a fill or strategy-P&L result.

## Frozen-control availability

The 24-hour coverage pilot has completed eight of at most 48 scans: 271 of 320 selected pair slots passed its quality checks, covering 232 distinct market IDs, with zero skipped scan sequences. The rotating cohort has 261/294 quality-valid selections; stable controls have 10/26. These role yields are descriptive because selection roles and availability differ.

The read-only dashboard API now checks the control-cohort digest, pilot event chain, linked compressed snapshot digest, scan identity, selection counts, and the snapshot's bounded discovery universe before projecting availability. For scan 38 it verifies that three of eight frozen controls were selected. The other five do not appear in that scan's six-query union. The API returns counts and a source-snapshot link without exposing the control IDs. Absence from the bounded query responses does not establish that a market is closed or absent from the venue.

The pilot's pinned analyzer, plan, selected controls, and fixed stop were left unchanged. Any retrieval or cohort redesign belongs in a later versioned study.

## Verification and operations

- `tests/test_veritas_dashboard_api.py`: **18 passed**.
- `apps/web/src/Veritas.test.tsx`: **1 passed**.
- Ruff lint and format, Prettier, ESLint, TypeScript, and `git diff --check`: passed.
- A read-only call against the current repository artifacts returned `verified`, 3/8 controls selected, and five controls absent from the bounded query union.
- The scheduled Director projection still showed the completed scan 38 Arena job as `QUEUED` and scan 37 as last qualified. Reconciliation remains scheduled for a later Director cycle; no manual poll or retry was used.
- The running Reality recorder reported `DEGRADED_SOURCE_TIMING` after a DNS resolution error while its segment ordinal and last-observation time were advancing. The shadow campaign worker remained active but reported `WARMING_OR_LAGGED_SOURCE` and 160,039 lagged frames skipped. This is recorded as an operational risk; no service, campaign, or source segment was restarted, changed, or read from an active `.open` file.

See [Gate G checkpoint 010](VERITAS_MISSION2_GATE_G_CHECKPOINT_010.md) for the API and dashboard change. Gate A remains in progress.
