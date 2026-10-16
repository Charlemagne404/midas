# Veritas Gate A checkpoint 004 — worker decision timing

Captured at `2026-10-14T23:19:56.595651Z`. The machine-readable result is
[VERITAS_GATE_A_DECISION_TIMING_001.json](VERITAS_GATE_A_DECISION_TIMING_001.json).
This checkpoint extends the finalized-source decision replay in
[checkpoint 002](VERITAS_GATE_A_CHECKPOINT_002.md) and the raw-frame funnel in
[checkpoint 003](VERITAS_GATE_A_CHECKPOINT_003.md). It does not accept Gate A or
any later development gate.

## Protected-state check

- The frozen Reality campaign remains
  `adf91d042ab8f91678834b9258bfde70022a763dfda8c91d1e94be334583aa46`; its plan
  SHA256 remains
  `aa8acb2b46823c1a1e3ac5d01a57dde917746c2c7471098ae2a4598875e322f5`.
- The Reality recorder and shadow worker were active before and after the scan,
  each with zero service restarts.
- The campaign plan, journal, raw recordings, and service state were not
  changed. No orders were submitted.

## Reproduction coverage

The bounded read-only query selected all 2,008 available decision rows under its
5,000-row limit at journal event sequence 23,697. Every selected row referenced
the captured finalized prefix, so all 2,008 reproduced without mismatch. The
replay verified 1,792 finalized segments (416,779,433 bytes), 216,095 source
records, 1,788 online reconstruction checkpoints, and all 11,850 distinct cited
source references. No decision inside the prefix was missing. The source
manifest SHA256 is
`cafdee622901ee882f7bd7f351f0fb5ac51583acd6d3a588d2f87139d22a6971`.

The worker's stored rolling history-reference windows differed from a
continuous offline replay for 1,491 decisions. This is the same runtime snapshot
timing variance described in checkpoint 002; it did not produce a feature,
baseline, source-state, or core-lineage mismatch, and all cited references
resolved.

## Timing result

The frozen input-lag limit is 250 ms and the frozen maximum book freshness is
5,000 ms. In the 2,008 covered decisions:

- Decision time minus the cited raw frame's receiver timestamp had a
  41.991 ms median, 220.232 ms p95, and 248.866 ms maximum. No sampled decision
  exceeded the frozen input-lag limit.
- Both outcome books were present in every row. The maximum age of the two books
  had a 10.460 s median, 52.350 s p95, and 62.407 s maximum.
- 1,337 decisions (66.6%) had at least one book older than the frozen 5 s
  freshness limit. The frozen quality reason was `stale_book` for 1,294 rows;
  another 22 were `book_issue:stale`. Freshness violations also occurred in 20
  of 22 `source_timing_uncertainty` rows and one `book_issue:advertised_top_pending`
  row.
- The recorded cross-outcome receiver-time skew was zero for all 2,008 rows.
  Books inherit the enclosing raw frame's receiver timestamp. A zero difference
  can therefore mean both outcomes were carried in one frame; it does not prove
  the underlying venue quotes were simultaneous.

| Quality reason | Decisions | Median maximum leg age | Over 5 s |
| --- | ---: | ---: | ---: |
| `eligible` | 555 | 0.399 s | 0 |
| `stale_book` | 1,294 | 22.373 s | 1,294 |
| `book_issue:stale` | 22 | 62.015 s | 22 |
| `source_timing_uncertainty` | 22 | 28.541 s | 20 |
| `empty_ask_side` | 100 | 0.755 s | 0 |
| `book_issue:advertised_top_pending` | 11 | 3.110 s | 1 |
| `independent_book_divergence` | 4 | 0.041 s | 0 |

The freshness mix varied materially by market. The per-market report contains
full lag, age, skew, and reason distributions. For example, the 562828 slice had
6 of 137 decisions above 5 s (4.4%) and a 0.139 s median maximum leg age; the
5674902 slice had 33 of 45 above 5 s (73.3%) and a 29.467 s median. Repeated
rows from the same market are correlated, so these are descriptive slices of
this selected campaign cohort.

## Interpretation and limits

Worker processing lag does not explain the observed freshness failures in this
sample: the cited frame was processed within the frozen 250 ms bound, while the
reconstructed books were often much older. The leading measured constraint is
the age of each market's latest recorded outcome books. Market differences
suggest source activity or update cadence may matter, but this scan does not
separate low market activity from recording gaps or worker scheduling. That is
the next investigation; no pipeline defect is established here.

Input lag starts at the recorder's raw-frame receipt timestamp. It does not
measure delay before that receipt, and the frame-level clock does not provide
independent exchange timestamps for the two outcomes. This is not a fill,
execution, or profitability result. The eight rows beyond the earlier finalized
prefix had finalized before this capture and are now reproduced; no selected
row was beyond the finalized prefix in this snapshot. The active `.open` segment
was excluded.

## Verification

- Veritas focused suite: 26 passed.
- Ruff check and formatting check passed for the changed source and replay test.
- Strict mypy passed for `packages/midas/veritas`.
- Source replay passed with analysis version v2, no mismatches, and no
  uncovered selected decisions.

## Next work

1. Measure per-market paired-book update intervals and source gaps, then compare
   them with scheduled-decision timing and raw touched-frame quality.
2. Use the activity and freshness evidence to draft a separate, predeclared
   sampling-cadence experiment; leave the frozen Reality campaign unchanged.
3. Continue independent fee, full-depth, capital, settlement, and unmatched
   position validation before using the Veritas economics engine downstream.
