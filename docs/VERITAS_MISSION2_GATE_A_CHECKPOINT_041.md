# Gate A checkpoint 041 — scan 43 and interim pilot yield

Captured 2026-10-16 01:03 UTC. Scan 43 was captured at 01:01:47 UTC; its
observer one-shot exited successfully at 01:01:54 UTC. The compact snapshot
and derived summary were read after that exit.

## Scan 43 public observation

The unauthenticated bounded scan selected 40 paired markets from six Gamma
pages. Its bounded page union contained 300 unique IDs, of which 202 met the
supported paired-market rule at this scan; 98 were excluded. This is a
query-bounded union, not a venue census. Of 40 selected pairs, 32 passed the
current quality gate and eight failed because the NO ask side was empty.

No positive top-ask gross pair appeared. At each tested quantity (5, 10, 20,
50, and 100 shares per leg), positive full-depth gross, per-leg minimum
notional, single-match-fee, and fragmentation-safe-fee counts were all zero.
The scan reports zero fee-unavailable pairs and zero recorded timestamp-skew
pairs above 250 ms. No authenticated request or order was used.

The saved v4 summary now covers 43 repeated snapshots: 1,499 of 1,720
selected pair states passed quality checks, with 221 invalid states and zero
candidate events. It records 784 distinct selected market IDs across the
panel and a maximum observed top edge of -$0.001/share. These are correlated,
intermittent observations; they do not establish opportunity prevalence,
quote lifetime, fills, or strategy performance.

## Fixed measurement pilot

The unchanged v1 pilot is at 13 of 48 planned scans, with 429 of 520 selected
slots quality-valid (82.5%), 326 distinct selected IDs, and zero skipped scan
sequences. The role yields remain descriptive and non-randomized: the rotating
stratum is 414/479 valid, and the stable control is 15/41 valid. The pilot
continues to its fixed stop at 2026-10-16 19:00:55 UTC. Its results do not
support a causal or venue-wide comparison.

## Operations and next evidence

The observer service exited with status 0 and is inactive between timer runs;
its timer remains enabled. Scan 43 has not yet been qualified by the Research
Director. The next scheduled source analysis is 01:10:29 UTC, Director cycle
01:15:26 UTC, and gap-detail batch 01:20 UTC. No service, timer, pilot, or
frozen campaign was manually changed or restarted for this capture.

The successor scanner remains gated until the fixed pilot stop. Continue
no-trade and wait for the scheduled Director cycle before recording a scan 43
Arena qualification.
