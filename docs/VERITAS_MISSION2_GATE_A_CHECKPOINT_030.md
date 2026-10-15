# Gate A checkpoint 030 — scan 34 and source-gap index audit

**Updated through:** 2026-10-15T20:34:55Z  
**Mission status:** active; scan 34 awaits the next scheduled Research Director cycle.

## Scan 34: bounded discovery and observation

The scheduled scan `scan-20261015T203154Z-c77f2bb45c60` completed at
20:31:54.972592 UTC. Six bounded query frames returned 300 rows and 298
unique IDs. One hundred thirty met the supported same-condition V1 binary
relationship gate; 168 were excluded (106 unverified augmented NegRisk
semantics and 62 unsupported outcome relationships). The scan selected 40
markets: 37 rotating selections and three of eight available stable controls.
Thirty-five pairs passed request/receipt checks; five were invalid for an
empty ask side. There were zero positive top-gross pairs.

Across 34 finalized snapshots, the panel now has 1,360 selected pairs, 1,202
quality-valid pairs, 158 invalid pairs, and 632 distinct selected market IDs.
The legacy reported-age gate accepts 275/1,360; the request/receipt gate
accepts 1,202/1,360, a paired increase of 927 observations or 68.2 percentage
points. This is a measurement-gate yield change; it does not establish venue
timestamp freshness. The best cumulative top edge remains -$0.001/share, and
all five quantity/depth/minimum/fee gates remain zero-positive.

The fixed 24-hour coverage pilot has completed four of up to 48 scans / 160
selected pair slots / 132 quality-valid pairs / 28 invalid pairs / zero
missed scan sequences. Rotating selections account for 128/148 valid slots;
available stable controls account for 4/12. There are 123 distinct selected
market IDs. The role comparison remains descriptive because the control
cohort is small and not randomized. The fixed stop remains
2026-10-16T19:00:55Z.

The snapshot records seven public HTTP attempts, zero pilot-only extra
requests, no authenticated requests, and no orders submitted. Intermittent
snapshots do not establish continuous coverage or executable prices.

## Source-gap index audit

A read-only verification checked all 3,388 sealed v1 source-analysis events,
their contiguous segment indices, the event hash chain, the processed catalog
prefix, and the cumulative summary. The current campaign-window aggregate
contains 911 `book_resynchronization` markers and one `connection_failure`.
Across all periods represented in the processed prefix, the per-segment
`record_kinds` fields count 2,993 gap records in 1,440 segments, with at most
46 in one segment. These all-period counts are not a campaign-window total.

The v1 event index has no per-gap timestamp or reason, so it cannot cluster
the current 911 campaign markers by time or market or estimate recovery
duration. The earlier source replay provides detailed five-minute buckets
for only the first 1,914 segments / ordinal 231,059; those 191 early
campaign-window resynchronizations cannot be extrapolated to the newer
prefix. See [gap-index audit 001](VERITAS_MISSION2_GAP_INDEX_AUDIT_001.json)
and [H074](VERITAS_RESEARCH_LEDGER.json).

## Scheduled research and host state

The authoritative scan-33 Arena job completed at 20:16:26 UTC with zero
positives, but the Director manifest last updated at 20:16:09 UTC still shows
that job as queued. Scan 34 has not yet been qualified. The next Director
cycle is due at 20:45:05 UTC; no manual poll, retry, or overlapping job was
started.

The finalized-source analyzer remains at 3,388/4,260 segments, with 872
segments / 269,424,035 bytes pending. Its 20:14 summary reports 186,344
quality-valid states across 47 markets and zero positive top-ask or
full-depth states. The next source timer is due at 20:40:16 UTC.

At 20:34:55 UTC, the Reality recorder and frozen shadow service were active;
the recorder had zero restarts and the shadow had one prior restart. Veritas
one-shot services were inactive between scheduled runs, and all three Veritas
timers were active. Midas API/web and Reality API/web units were active with
zero restarts. The host had 8.9 GiB available memory, 3.6/4 GiB swap in use,
199 GiB free disk (56% used), and a 39 MiB observatory directory. These are
read-only unit and host observations; no HTTP health probe was run at this
capture.

## Evidence

- Snapshot evidence SHA-256: `c77f2bb45c60d2eec390dc2c56d89ef87e270ecda8417d271dd11bdaebabfb2f`
- Compressed snapshot SHA-256: `c7a0da6b4502c46c0005d0717f14df1913619183cb79e7d61bb756c815aef64c`
- v4 analysis-event SHA-256: `f30d82eceb24654b9f5712899612bff43ed03095995669e36c02af46f19571f2`
- v4 analysis-event file SHA-256: `a5e309410de926c742781372f509d9bbafa603e1a06b56bc07fdf5d94df96e4d`
- Pilot event SHA-256: `106a2c442a1206a65248fc124739245c0b177bdc2c529166881daacc0f898f2a`
- Pilot event file SHA-256: `87d24866006a442d8f78100cd8e791c8b99c43a06a8c40933315fa7ee968dda4`
- Pilot cumulative summary SHA-256: `3482d9a541c2663b07c4507a5859a518e101d544bf718434280d736a0f2eff30`
- Cumulative observer summary file SHA-256: `1e88aad06e1481854e83dd7c5e1ec0315b75fdb0ce61d617b0115b0a24d9ddc4`
- Finalized-source summary SHA-256: `c32f8e0796c9c8c814e7fc5eb0538042667a908b0d90ad6b589af551d05608e4`
- Gap-index audit SHA-256: `0718dd6480b8486dc31028a996c2b1fd9322fb47a15de05f2e3c036f2780915b`

No collector, service, campaign, or active research job was restarted or
changed for this checkpoint. Keep no-trade; allow the scheduled source replay,
Director qualification, and fixed coverage pilot to proceed. A separate
bounded finalized-segment gap-detail extractor is now the next source-quality
task.
