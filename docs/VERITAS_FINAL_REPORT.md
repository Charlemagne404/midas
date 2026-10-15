# Project Veritas — final research and engineering report

**As of:** 2026-10-15

**Worktree:** `/home/charlie/midas-veritas`, branch `project/veritas`

**Decision:** No observed candidate supports a strategy or a separate prospective campaign. Keep the existing Reality campaign and its services untouched; continue passive evidence collection and revisit only after the stated evidence gates are met.

## Executive finding

The latest finalized-source replay covers about 4 hours 16 minutes, 16 selected
market IDs, and 44,981 quality-valid paired-book states. It found zero positive
best-ask pair edges, zero positive quantity-specific top edges, zero positive
full-depth pre-fee edges, and zero positive full-depth edges meeting both
per-leg minimum notionals. This supports a no-candidate conclusion for this
captured panel and interval. It does not estimate venue-wide opportunity
prevalence.

The controlled economic study is synthetic. At 100 shares per leg and full
displayed depth, its favorable single-match fee-rounding case yields +1.4178
USDC at the worse resolution, while the fragmentation-safe fee bound yields
-0.7822 USDC. The same assumed book gives a 50.1959 USDC adverse unmatched-leg
loss. None of these values are observed fills, actual money, or probabilities.
There is no empirical fill, completion, queue, recovery, or market-impact rate
with which to turn the sensitivity into expected strategy performance.

The result does not justify a new campaign. The activity-aware follow-up
protocol remains a planning draft because the two-day coverage rule and crossed
market/time dependence are unvalidated. The frozen Mission 2 campaign remains
the protected reference and continues to report insufficient forward evidence
in its captured checkpoint.

## Evidence and interpretation

| Evidence class | Result | What it supports |
| --- | --- | --- |
| **Observed public source** | 2,040 finalized segments, 483,718,250 bytes, through ordinal 251,887; 56,912 frame records; 46,298 touched states; 44,981 quality-valid states; 1,317 invalid states. | A bounded description of the selected recorded panel in the captured interval. |
| **Derived from observed source** | Complete five-share depth and fee metadata for all 44,981 valid states. No positive top, quantity-depth, full-depth pre-fee, or full-depth/minimum-notional candidate. Maximum top edge -0.001 per share; median -0.01. | No quality-valid positive gross complement was found in this snapshot. Repeated states are correlated; they are not independent opportunities. |
| **Synthetic scenario** | 100 shares per leg, full displayed depth: +1.4178 USDC worst-resolution P&L under single-match rounding; -0.7822 USDC under the fragmentation-safe fee bound; 50.1959 USDC loss in the assumed unrecovered adverse unmatched leg. | Sensitivity to declared book, fee, settlement, rounding, and position assumptions only. |
| **Planning calculation** | One-second public-measurement baseline 27/1,408 = 1.92% per scheduled slot; 27/381 = 7.09% among valid initial states. A 50% relative lift gives a simple two-proportion estimate of 3,994 independent slots per arm. | Study sizing illustration only. Dependence is not estimated, and the eligible-market/coverage rules remain unverified. |
| **Unknown** | Actual fills, queue position, order acknowledgements, fill/completion probability, private matching, own market impact, recovery value, and profitability. | These values must remain unknown; quote depth and public follow-ups do not identify them. |

The machine-readable funnel is [raw funnel 004](VERITAS_GATE_A_RAW_FUNNEL_004.json),
with method and limits in [Gate A checkpoint 012](VERITAS_GATE_A_CHECKPOINT_012.md).
Synthetic assumptions and fee cases are documented in [Gate B checkpoint
001](VERITAS_GATE_B_CHECKPOINT_001.md). The power calculation and launch
readiness conditions are in [follow-up design draft
002](VERITAS_GATE_A_FOLLOWUP_DESIGN_002.md).

## Work completed

### Gate scope

The lettered checkpoints span two related workstreams. Reality Mission 2's
Gates A–G are the protected engineering and public-observation baseline, whose
acceptance is recorded in the [Mission 2 audit](REALITY_MISSION2_ACCEPTANCE.md).
That acceptance does not mean a model or strategy passed: the captured Gate D
checkpoint has no scientific champion, and the captured Gate F forward state
is `insufficient_forward_evidence`. Veritas adds its own source/economic
analysis in Gates A/B, broad verification in Gates G/H, the read-only dashboard
in Gate I, and this synthesis in Gate J. The matching letters do not merge the
two acceptance criteria.

- **Source and opportunity analysis:** bounded finalized-segment replay,
  decision/source reconciliation, timing and gap diagnostics, and the updated
  raw opportunity funnel. The latest replay did not read an active `.open`
  payload.
- **Economic analysis:** repaired fee and USDC minimum-notional arithmetic;
  added controlled capacity and execution break-even sensitivities. The
  sensitivities do not contain observed quotes or execution rates.
- **Follow-up design:** fixed the primary estimand to qualifying one-second
  public measurements per all scheduled slots, and added a reproducible power
  sensitivity. No campaign was frozen or started.
- **Read-only dashboard:** added a native Veritas page with a bounded overview
  and an allowlisted artifact endpoint. It exposes versioned summaries and
  hashes, not raw market records or campaign controls. See [dashboard
  checkpoint 001](VERITAS_DASHBOARD_CHECKPOINT_001.md).
- **Engineering verification:** completed backend, frontend, type, lint,
  formatting, build, and isolated browser checks. Evidence and qualifications
  are in [Gate G checkpoint 001](VERITAS_GATE_G_CHECKPOINT_001.md) and [Gate H
  checkpoint 001](VERITAS_GATE_H_CHECKPOINT_001.md).
- **Research catalog and handoff:** updated the [research
  inventory](VERITAS_RESEARCH_INVENTORY.json), [hypothesis
  ledger](VERITAS_RESEARCH_LEDGER.json), [backlog](VERITAS_RESEARCH_BACKLOG.md),
  and [operations procedures](VERITAS_OPERATIONS.md).

## Evidence limits

The source panel is selected and short, not a representative venue-wide sample.
Frames and market states overlap in time and are correlated. The feed has no
venue sequencing guarantee. Recorded receiver-time freshness does not reveal
upstream quote age. Public displayed depth does not establish persistence at
the same constituent orders or any hypothetical fill. The Mission 2 forward
checkpoint is sparse and reports `insufficient_forward_evidence`; its
hypothetical economics are not actual portfolio returns. See the [Reality
Mission 2 acceptance audit](REALITY_MISSION2_ACCEPTANCE.md) and captured [Gate
F checkpoint](REALITY_GATE_F_CHECKPOINT.json).

Engineering checks are strong but bounded. The full backend run passed 785
tests with one optional PostgreSQL integration test skipped because no test
database URL was supplied. Two later guards in `scripts/research_followup.py`
were covered by 10 focused tests and the final full Mypy run. The Reality
browser test used intercepted operation and raw-record routes; it verified the
read-only interface view, while API source-record behavior was exercised
against temporary segment fixtures. The original browser error response was
not captured, so the release-fixed segment-rotation issue remains the likely
cause rather than a confirmed diagnosis. The production build also retains the
existing bundle-size advisory. See [Gate H checkpoint
001](VERITAS_GATE_H_CHECKPOINT_001.md).

## Next evidence gates

1. Wait for a materially longer finalized interval before another raw-funnel
   replay, or use a separately approved observation cohort.
2. Establish at least 48 hours of pre-period subscription and finalized-source
   coverage, with the draft's coverage threshold and at least nine eligible
   markets; do not infer coverage from update counts.
3. Estimate or bound crossed market/family and time-block dependence from
   finalized multi-day evidence, then simulate the exact slot assignment and
   primary analysis before freezing any separate study.
4. If a positive gross candidate appears, independently recheck its source,
   payoff mapping, per-leg minimums, full-depth costs, fees, and quantity.
   Only then compare explicitly hypothetical execution policies, keeping fill
   and recovery assumptions unknown unless separately identified.

Until then, retain the no-trade control and do not select a strategy, create a
new prospective campaign, or promote synthetic thresholds as empirical
performance. The current campaign identity and plan hash remain documented in
the [ledger](VERITAS_RESEARCH_LEDGER.json); Reality operations remain in their
separate worktree.
