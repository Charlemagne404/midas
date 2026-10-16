# Veritas Gate A checkpoint 012 — later finalized raw opportunity funnel

Captured 2026-10-15 01:26:02 UTC. This snapshot extends the version 2 raw
opportunity funnel on a larger finalized source prefix. It does not change the
Reality campaign.

## Protected-state check

- The protected campaign remains
  `adf91d042ab8f91678834b9258bfde70022a763dfda8c91d1e94be334583aa46`. Its
  `campaign.json` SHA256 remains
  `aa8acb2b46823c1a1e3ac5d01a57dde917746c2c7471098ae2a4598875e322f5`.
- The replay used the static catalog of finalized `.seg` files captured at
  startup. The report records `active_segment_read: false`; it did not read an
  `.open` payload, write to the Reality worktree, or submit an order.

## Finalized-source snapshot

The aggregate result is
[VERITAS_GATE_A_RAW_FUNNEL_004.json](VERITAS_GATE_A_RAW_FUNNEL_004.json). It
covers 2,040 finalized segments (483,718,250 bytes) through ordinal 251,887
and verifies 2,036 reconstruction checkpoints. Its source manifest SHA256 is
`67673b47d41166894f97c5ef8ec694705d83230c52d53156084156452ab8d756`. The
recorded receiver-time window ran from 2026-10-14 21:07:59 UTC through
2026-10-15 01:24:15 UTC, about 4 hours 16 minutes.

## Raw opportunity funnel

The campaign window contained 56,912 frame records and 46,298 touched
market-frame states across 16 campaign market IDs. Of these states, 44,981
passed paired-book quality checks and 1,317 were invalid:

- 1,040 empty ask-side states.
- 202 independent book-divergence states.
- 50 source-timing-uncertain states.
- 20 top-divergence states.
- 5 states after reported expiry.

At the frozen five-share quantity, every quality-valid state had complete
displayed depth and fee-regime metadata. No state had a positive best-ask pair
edge, a positive quantity-specific top edge, a positive full-depth pre-fee
edge, or a positive full-depth edge meeting both per-leg USDC minimums. The
maximum top-pair edge remained -0.001 per share and the median remained -0.01.

Compared with checkpoint 011, this snapshot adds 116 finalized segments,
33,115,478 bytes, 19,968 source records, 16,261 frame records, 15,291 touched
states, and 15,049 quality-valid states. The panel adds one campaign market ID.
The added frame states are correlated observations and do not represent
independent opportunities. This remains a selected monitored panel, not a
venue-wide sample.

## Decision

The larger prefix does not change the gross opportunity conclusion. The
captured panel still has no quality-valid positive complementary opportunity
before fees or execution assumptions. Keep the no-trade decision and existing
quality gates. Displayed depth is not a fill, and this analysis does not
establish profitability.

No campaign or collector setting changed, and no separate prospective
campaign was created or started. The next raw-funnel replay should wait for a
materially larger finalized interval; the activity-aware follow-up design
still needs finalized multi-day evidence before a campaign can be frozen.
