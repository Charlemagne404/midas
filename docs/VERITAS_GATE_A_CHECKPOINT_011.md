# Veritas Gate A checkpoint 011 — extended finalized raw opportunity funnel

Captured 2026-10-15 00:27:16 UTC. This is a larger finalized-source snapshot
of the version 2 raw opportunity funnel. It does not change the Reality
campaign.

## Protected-state check

- The protected campaign remains
  adf91d042ab8f91678834b9258bfde70022a763dfda8c91d1e94be334583aa46. Its
  campaign.json SHA256 remains
  aa8acb2b46823c1a1e3ac5d01a57dde917746c2c7471098ae2a4598875e322f5.
- The Reality recorder and shadow worker remained active after the replay,
  each with NRestarts=0.
- The analysis read finalized cataloged segments only and did not read the
  active segment or write to the Reality worktree. No order was submitted.

## Finalized-source snapshot

The aggregate result is
[VERITAS_GATE_A_RAW_FUNNEL_003.json](VERITAS_GATE_A_RAW_FUNNEL_003.json).
The replay covered 1,924 finalized segments (450,602,772 bytes) through
ordinal 231,919 and verified 1,920 reconstruction checkpoints. Its source
manifest SHA256 is
2c2b10a584e737702579ffe79d2d8144f182fe8834b964707e47b72ad270df6d. The
recorded receipt window ran from 2026-10-14 21:07:59 UTC through 2026-10-15
00:25:35 UTC, about 3 hours 18 minutes.

## Raw opportunity funnel

The extended panel contained 40,651 frame records and 31,007 touched
market-frame states across 15 campaign market IDs. Of these states, 29,932
passed the paired-book quality checks and 1,075 were invalid:

- 860 empty ask-side states.
- 145 independent book-divergence states.
- 45 source-timing-uncertain states.
- 20 top-divergence states.
- 5 states after reported expiry.

At the frozen five-share quantity, all 29,932 quality-valid states had complete
displayed depth and fee-regime metadata. None had a positive best-ask pair
edge, a positive quantity-specific top edge, or a positive full-depth pre-fee
edge. The best top-pair edge was -0.001; the median was -0.01. All positive
state counts, including those satisfying the corrected per-leg USDC minimum,
were zero.

Compared with the prior v2 snapshot, this replay added 4,759 frame records,
4,483 touched states, and 4,312 quality-valid states. The added observations
are correlated market-time states, not independent opportunities. This remains
a selected monitored panel, not a venue-wide sample.

## Decision

The larger window does not change the gross opportunity conclusion. The
captured panel still has no quality-valid positive complementary opportunity
before fees or execution assumptions. Keep the no-trade decision and existing
quality gates. Displayed depth is not a fill, and this analysis does not
establish profitability.

No campaign or collector setting changed. No training job, future campaign,
or long-running Veritas process was started.

## Next work

1. Design a separate, predeclared activity-aware sampling and future-horizon
   study that retains the existing quality gate and no-trade control.
2. Continue collecting broader finalized evidence and rerun this versioned
   funnel only when the additional source interval is material.
3. Extend economics only if a positive, quality-valid gross candidate appears.
