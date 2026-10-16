# Gate B checkpoint 013 — independent replay through the 09:30 snapshot

**Captured:** 2026-10-16T09:30:52Z

**Mission status:** active; no gross or economically qualified candidate
observed.

## Independent replay

The normal 09:30 UTC observer run completed successfully and added
`scan-20261016T093021Z-b20cf6a3b852`. Its saved analysis event reports 32/40
quality-valid pairs and zero positive top-gross pairs. Independent audit 012
then replayed all 60 saved snapshots (2,400 selected market observations;
38,901,902 compressed source bytes) using fee model v3.

| Check | Result |
| --- | ---: |
| Independent / stored quality-valid observations | 2,047 / 2,047 |
| Quality-validity / top-edge mismatches | 0 / 0 |
| Strict reported-freshness observations | 428 |
| Pairs with reported age over 5 seconds | 1,619 |
| Pair timestamp skew over 250 ms | 0 |
| Independent fee arithmetic checks / disagreements | 2,548 / 0 |
| Positive top-pair gross states | 0 |
| Positive full-depth gross states at quantities 5, 10, 20, 50, 100 | 0 at each quantity |
| Positive states after both minimums, single-match fees, or fragmentation-safe fees | 0 at each quantity |

The new 09:30 snapshot contributes 40 selected pairs and 32 quality-valid
pairs. Its stored and independently recomputed results match. These are
intermittent, selected, repeated observations, not independent opportunity
trials or a venue-wide denominator. Timestamp age is based on returned public
timestamps and is not proof of venue sequence freshness, atomicity, persistence,
queue position, order arrival, or fillability.

## Fee model and interpretation

This replay uses `veritas-economic-feasibility-v3`, with buy fees treated as
collateral costs at entry on both legs. The independent Decimal fee arithmetic
agreed for all 2,548 checked quantities. No authenticated request or order was
made. The scan and replay do not identify a hypothetical fill or a realized
return.

## Evidence

- Audit: [independent opportunity audit 012](VERITAS_MISSION2_INDEPENDENT_OPPORTUNITY_AUDIT_012.json)
- Audit file SHA-256: `98d447ecfc965682392292b9834a75dcdbcbb91c659e755c0f2989435546af76`
- Result SHA-256: `1ebc7a3665ae48e37661e522d0d81ef03bd1cf63b838ea9286b5e80cb959e092`
- Source-manifest SHA-256: `c940246d3dcb5622455801dbec676786ec8f7efa7b7e92906c24c0eccb064f5f`
- Audit source-code SHA-256: `ff0d89ef437a051b27002ca9a5f6deb5b1f7dca52e87883894a48ccc726f98e2`
- Latest observer snapshot code SHA-256: `72ab0452c03ecf0d67694e45901870ab3226fd08c5f0772a4118fe790325a5e9`
- Ledger receipt: H133

## Decision and next work

Keep the no-trade decision. The additional saved snapshot does not change the
economic result, and the v3 model continues to find no positive gross or
post-cost state in this selected panel. Preserve audit 012 and advance the next
default output to audit 013 so another replay cannot overwrite it.

The next operational checks are the scheduled 09:40 UTC finalized-source
analysis and 09:45 UTC Research Director cycle. Their outcomes remain
unverified at this checkpoint. The source-analysis cursor was current at
5,815/5,815 segments as of its 09:23 UTC recovery run. The hosted API and
dashboard remain on `/home/charlie/midas`; the branch update is not deployed.
