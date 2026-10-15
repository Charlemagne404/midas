# Veritas Gate A checkpoint 010 — event-aligned source age and freshness thresholds

Captured 2026-10-15 00:21:58 UTC. This checkpoint measures elapsed receiver
time from the preceding per-outcome book update to resynchronization issue
records and scheduled decisions. It does not change the Reality campaign.

## Protected-state check

- The protected campaign remains
  adf91d042ab8f91678834b9258bfde70022a763dfda8c91d1e94be334583aa46, with
  campaign.json SHA256
  aa8acb2b46823c1a1e3ac5d01a57dde917746c2c7471098ae2a4598875e322f5.
- The Reality recorder and shadow worker remained active after the replay,
  each with NRestarts=0.
- The replay used finalized cataloged segments only. It did not read the
  active segment or write to the Reality worktree. No order was submitted.

## Finalized-source replay

The aggregate result is
[VERITAS_GATE_A_GAP_AGE_001.json](VERITAS_GATE_A_GAP_AGE_001.json), analysis
version `veritas-source-replay-v7`. It covers 1,914 finalized segments
(448,390,042 bytes) through ordinal 231,059 and verified 1,910 reconstruction
checkpoints. The source manifest SHA256 is
`2d437b886055d05022d95bd61818d7f15b91e7a548b61607ffe6cb0da832bed6`.
All 2,945 sampled decisions reproduced, with zero mismatches, zero decisions
outside the finalized prefix, and no active-segment reads.

## Resynchronization issue age

The replay recorded 191 book-resynchronization gaps and 1,108 mapped issue
entries across eight markets: 1,062 stale, 39 top-divergence, six
advertised-top-pending, and one timestamp-regression entry. No entries were
unmapped or censored for a missing prior update, a prior recorded gap, or
negative receiver-time elapsed.

All 1,062 stale entries had a preceding same-gap-epoch outcome update and an
active source stale threshold of 60,000 ms. Their elapsed receiver time ranged
from 60,008.304 ms to 64,341.912 ms; all 1,062 were above the threshold and
none were at or below it. The recorded stale issue therefore agrees with the
reconstructed source engine's 60-second stale rule in this snapshot.

## Scheduled decision age by outcome

The frozen decision freshness gate is 5,000 ms. All 2,945 sampled decisions
had both outcome books available. YES and NO age distributions had identical
bucket counts and p50/p95 values in all 14 decision markets. The per-decision
leg counts show no one-sided freshness failures:

- 1,050 decisions had zero legs older than 5 seconds.
- 1,895 decisions (64.35%) had both legs older than 5 seconds; none had only
  one failing leg.
- Of those 1,895 decisions, 1,866 had both legs older than 5 seconds but no
  older than the source's 60-second threshold. The remaining 29 had both legs
  older than 60 seconds.

In total, 3,732 leg ages were over 5 seconds and at or below 60 seconds; 58
leg ages were over 60 seconds. These counts separate the earlier frozen
campaign abstention gate from the collector's later stale classification.
Per-market age distributions and interval buckets are in the JSON artifact.

The source gap and scheduled decision measures use recorded receiver
timestamps. They do not measure upstream venue quote age or guarantee that an
update could have been received sooner. The 60-second source label and
5-second decision quality gate serve different purposes; this result does not
justify weakening the frozen gate or changing the collector.

## Verification and decision

- Focused source replay tests: **5 passed**.
- Ruff check and format: passed.
- Strict mypy for `packages/midas/veritas`: passed.
- The replay reads finalized cataloged `.seg` files only. It does not read
  the active `.open` segment or export outcome asset identifiers.
- No campaign or collector setting was changed, and no orders were submitted.

Current classification remains **insufficient independent evidence**. The
source gap label matches the reconstructed 60-second timeout, while most
scheduled freshness failures fall between the 5-second campaign gate and the
60-second source threshold. Market activity and per-outcome freshness remain
descriptive observations, not evidence of fills or profitability.

## Next work

1. Design a separate, predeclared activity-aware sampling and future-horizon
   study that retains the existing quality gate and no-trade control.
2. Expand the finalized raw opportunity panel and continue to require a
   positive, quality-valid gross candidate before extending economic scenarios.
3. Inspect existing Research Director interfaces before adding any new job
   control or dashboard surface.
