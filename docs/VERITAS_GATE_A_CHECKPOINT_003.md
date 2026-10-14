# Veritas Gate A checkpoint 003 — raw frame opportunity funnel

Captured at `2026-10-14T23:08:03.112457Z`. The aggregate machine report is
[VERITAS_GATE_A_RAW_FUNNEL_001.json](VERITAS_GATE_A_RAW_FUNNEL_001.json). It is
the next source snapshot after the decision replay in
[checkpoint 002](VERITAS_GATE_A_CHECKPOINT_002.md); the campaign remains active.

## Read-only source scope

The scanner verified the frozen campaign plan and pinned Reality code, replayed
the cataloged finalized source prefix, verified all segment hashes, ordinal
continuity, and online reconstruction checkpoints, then counted only market
states touched by a raw frame during the campaign window. The active `.open`
segment was excluded. The result contains aggregate counts and price-edge
summary statistics, not raw event payloads.

The captured prefix contained 1,768 finalized segments, 411,096,328 bytes, and
records through ordinal 213,679. It replayed 213,679 records and verified 1,764
online checkpoints. The campaign window began at `2026-10-14T21:07:58Z`; the
last included source receipt was `2026-10-14T23:06:23Z`, about 1 hour 58 minutes
of the frozen fourteen-day period so far. The source manifest SHA256 is
`df23dedd8a27d08aaf5b25925a12d32007a8266068d8f7048ac47c00abfa3d4d`.

## Funnel result

- 27,489 raw frame records fell inside the campaign window. A pair state was
  counted when at least one of that market's outcome books changed in the frame.
- The scanner observed 20,125 touched market-frame states across ten markets,
  grouped into 139 five-minute family blocks. There were no unsupported
  producer or reconstruction frames and no receiver-clock regression frames.
- 19,501 states passed the frozen pair-quality rules. The other 624 were
  `empty_ask_side` (479), `independent_book_divergence` (94),
  `source_timing_uncertainty` (34), or `book_issue:top_divergence` (17).
- At all 19,501 quality-valid states, displayed asks supported the campaign
  quantity of five shares on both legs. The pre-fee best-ask edge distribution
  ranged from `-0.58` to `-0.001` collateral units per set; its nearest-rank
  median was `-0.06`. There were zero positive top-ask states and zero positive
  full-depth pre-fee states.
- A public fee regime was available for all 19,501 quality-valid states. The
  scanner did not apply fees or settlement assumptions because the displayed
  gross edge was already negative throughout this snapshot.
- The source recorded 119 `book_resynchronization` gaps inside the window. Their
  presence is retained as a separate source count, not treated as a market
  outcome.

## Interpretation and limits

This source-receipt-time scan supports the current abstention decision for the
observed selected cohort: no positive complementary quote appeared in these
quality-valid touched states, even before fees. The result is stronger source
coverage than the scheduled decision sample but does not represent independent
opportunities: repeated market-frame states are correlated. It is not
venue-wide prevalence, and it does not reconstruct the shadow worker's
processing lag at every non-decision frame.

The 20,125 market-frame states are not comparable as a denominator to the
campaign decision rows in checkpoints 001–002. This scan uses source receipt
time and counts each frame that touches a pair; the worker applies its frozen
schedule at processing time. Displayed depth is not a fill. No strategy,
economic assumption, model, threshold, or campaign rule was changed.

## Verification

- Focused Veritas suite: 25 passed.
- Ruff lint: passed for Veritas modules, audit commands, and focused tests.
- Ruff format check: passed for the new source replay and raw funnel files.
- Strict mypy: passed for `packages/midas/veritas`.
- The synthetic funnel test confirmed exact top-ask versus full-depth
  classification and ignored a malformed `.open` file.

## Next work

1. Join each stored decision to its verified source frame and measure worker
   input lag, pair age, cross-outcome skew, and recent per-market update rate.
2. Explain the difference between the raw touched-frame quality mix and the
   scheduled decision quality mix before designing any new cadence.
3. Test larger quantity, fee-fragmentation, capital, settlement, and
   unmatched-position bounds only after selecting states that pass independent
   payoff and metadata checks.
4. Keep the frozen Reality campaign unchanged and capture later source
   snapshots with their own manifest hashes and journal sequence.
