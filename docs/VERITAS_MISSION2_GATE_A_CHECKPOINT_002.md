# Veritas Mission 2 Gate A Checkpoint 002

**Captured:** 2026-10-15 06:31:03 UTC
**Branch:** `project/veritas`
**Source commit before this continuation:** `0e4a195e497e960ca995e8c6c8b8f276b56f2366`
**Status:** Scheduled post-commit scan and analysis verified; pilot continues

## Recurring operation verified

The active user timer ran the first scheduled scan after checkpoint commit
`0e4a195`. The service began at 06:30:53 UTC, finalized the scan at 06:31:03,
and exited successfully at 06:31:09. It used about 617 ms of CPU time and ran
for about 16 seconds. The latest capture was indexed once by analysis v2; the
processed snapshot count advanced from six to seven with no backlog.

The next scheduled timer event was 07:00:23 UTC. The service and timer remain
bounded to the deployment settings documented in
[`VERITAS_MISSION2_OPERATIONS.md`](VERITAS_MISSION2_OPERATIONS.md).

## New snapshot lineage

- Scan: `scan-20261015T063103Z-12947c8cef0a`
- Snapshot: `data/veritas-observatory/snapshots/scan-20261015T063103Z-12947c8cef0a.json.gz`
- Snapshot evidence SHA-256: `12947c8cef0a838589bb74461250020597a1ca153701802ae2f3af4581be7bd0`
- Analysis event SHA-256: `700f29876c216f28fb1dc9f6a061a7f200488b587b0859cd8153d7e97480a538`
- Scanner source SHA-256: `712d65a8698e3b6a3d9ec5362c12322559cf7359d874ea281eab0740569f08e1`
- Latest scan: 40 selected markets, 37 quality-valid pairs, three empty-ask
  exclusions, zero positive gross candidates.
- Latest selection: six stable controls, 34 rotating; high/medium/low liquidity
  counts 8/17/15; near-seven-day/medium/long expiry counts 15/24/1; tight,
  medium, and wide spreads 9/16/15.

## Cumulative evidence

Across seven snapshots from 05:59:28 through 06:31:03 UTC:

- 280 selected market-pair observations; 248 quality-valid and 32 invalid.
- Invalid reasons: 30 `no_empty_ask_side`, two `yes_empty_ask_side`.
- 133 unique market IDs observed; current bounded eligible union remains 167.
- Quality yield is 88.6% descriptively; the selected repeated observations are
  dependent and are not an independent event-rate estimate.
- Positive top-ask gross, depth, minimum-notional, single-match fee, and
  fragmentation-safe fee counts remain zero at every measured quantity.
- Top edge among valid states ranges from -0.984 to -0.001 per share, with
  median nearest-rank -0.028.
- Runtime data root is 4,745,634 bytes. No data cap or analysis backlog was
  reached.

On the newest scan, 23 of 37 valid pairs had reported update age above five
seconds on each leg, while all 37 had reported cross-outcome skew at or below
250 ms. Request-to-receipt freshness remains a batch-level measurement; it does
not verify venue sequence or upstream queue age.

## Refreshed economic comparison

The first economic artifact remains immutable. A second run of the same frozen
qualification rules now has a deterministic run ID derived from its ordered
snapshot and analysis-event identities:

- Experiment: `VERITAS-M2-ECO-QUAL-001`
- Run ID: `VERITAS-M2-ECO-QUAL-001-RUN-7878566d1ffb`
- Artifact: `data/veritas-observatory/experiments/VERITAS-M2-ECO-QUAL-001-RUN-002.json`
- Artifact file SHA-256: `291badcaee3e012cbabeaf2323b70fff95d792d94bc22b1aab2fce42020ef91e`
- Result SHA-256: `bec0435a125240372dd0c3200003f6e35e827548f5450c35b1873be7e6992fb5`
- Dataset SHA-256: `7878566d1ffb8261caca50ec09036715ec2c5f765b4c57a152744e86cf6d8737`

The unchanged top-ask baseline and the 20-share full-depth/minimum/fee funnel
each remain at zero positives across 248 valid states. This is evidence for
continued abstention in this panel, not proof that opportunities are absent
venue-wide and not a strategy PnL result.

The deterministic run identity change passed its targeted tests. The complete
Veritas backend test selection also passed: 77 tests, with only the existing
Starlette/httpx deprecation warning.

## Remaining evidence gates

The observation window is 31 minutes 35 seconds. It remains below both the
24-hour descriptive dependence-review readiness threshold and the separate
follow-up design's 48-hour coverage gate. Continue the timer. Do not infer
independence, continuous quote coverage, source queue freshness, fills, or
profitability from this checkpoint.
