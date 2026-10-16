# Gate A checkpoint 037 — scan 40 and coverage-pilot progress

**Captured:** 2026-10-15 23:34 UTC  
**Mission status:** active; the fixed coverage pilot and protected Reality
campaign continue unchanged.

## Scan 40

The scheduled public observer completed scan
`scan-20261015T233205Z-a2240a38b48f` at 23:32:05 UTC. Its six bounded Gamma
queries returned 291 unique IDs. Seventy-seven passed the supported V1
same-condition pair eligibility check; 214 were excluded. The observer
selected 40 pairs, of which 30 passed request/receipt quality checks. The
remaining ten had an empty ask side. The scan reported zero positive top-gross
pairs and no gross-candidate rows. The batch covered all unique requested
assets and took 198 ms; source sequence and batch atomicity remain unverified.

The result is an intermittent public snapshot. It does not provide continuous
coverage or a venue-wide market census. No authenticated requests or orders
were used.

## Fixed coverage pilot

The 24-hour measurement-only pilot now has 10 of 48 scheduled scans, 400
selected pair slots, 335 quality-valid pairs (83.75%), 65 invalid pairs, 271
distinct selected market IDs, and zero missed scan sequences. Its fixed stop
remains 2026-10-16 19:00:55 UTC. The cohort roles are nonrandomized; the yield
comparison is descriptive and does not show a causal benefit or profitability.

## Scan 39 qualification

Arena completed the scan-pinned qualification for scan 39 with exit status 0
and all 39 source events processed. The 39-snapshot panel contains 1,375
quality-valid pairs from 1,560 selected pairs, 185 invalid pairs, and 732
distinct selected markets. Its maximum top-pair edge is -$0.001/share and its
median is -$0.020/share. Gross, full-depth, per-leg-minimum, single-match-fee,
and fragmentation-safe positive counts are all zero; the complete candidate
replay contains no candidate rows.

The job record is complete, while the Research Director manifest still shows
the previous queued projection and scan 38 as last qualified. Its scheduled
23:45 UTC cycle is the reconciliation point. Scan 40 is newer and remains
unqualified at this checkpoint. No manual Director run, job retry, or service
restart was made.

## Limitations

The 39 qualified snapshots and scan 40 are repeated observations from bounded
selection frames. Their selected markets are not independent samples. The
fixed pilot remains underway, and its control comparison is descriptive.
These data provide no positive arbitrage or execution result. See [inventory
045](VERITAS_MISSION2_RESEARCH_INVENTORY_045.json) and [operations
checkpoint](VERITAS_MISSION2_OPERATIONS.md).
