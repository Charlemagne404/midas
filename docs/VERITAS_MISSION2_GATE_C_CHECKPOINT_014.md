# Gate C checkpoint 014 — finalized-source analyzer catches up

**Captured:** 2026-10-16T04:18:16Z
**Mission status:** active; the source-analysis prefix is current while recording continues.

The scheduled 04:10:41 UTC source-analysis batch completed at 04:13:29 UTC. It processed 81 finalized segments, used 8.398 CPU seconds and peaked at 120.4 MiB with no swap. It did not read an active segment.

| Measure | Result |
| --- | ---: |
| Processed / cataloged finalized segments | 5,206 / 5,206 |
| Pending segments / bytes | 0 / 0 |
| Processed source bytes | 1,346,127,203 |
| Quality-valid campaign-window states | 351,524 |
| Markets | 87 |
| Positive top-ask / full-depth states | 0 / 0 |

The sealed summary reports status current and readiness collecting_frozen_campaign_window. Its top-edge distribution contains 351,524 valid states, with maximum -0.001, median -0.01, and no positive values. This is finalized-source evidence from the frozen Reality window, not realized strategy performance.

The separate gap-detail index remains partial at 2417/5196 cataloged segments, or 2417/5194 replayable segments after excluding 2 empty finalized segments. It has 435 campaign-window resynchronization events across 15 affected market IDs, with 2777 segments / 762,500,134 bytes pending. Receiver-time gaps do not establish exchange quote time or causal censor attribution.

The source summary file SHA-256 is 2fb4afcd19f3a7aa4b8c2879c28e9483f30898cb1eff3839120c3ce7e0037fc9; its embedded summary digest is 7c8a709baea288cae65de769f4469d07482551e15e3eff1cba147634238ffac4. The gap index remains independently versioned and is not complete.
