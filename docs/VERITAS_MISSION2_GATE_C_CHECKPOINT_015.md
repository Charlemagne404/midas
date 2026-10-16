# Gate C checkpoint 015 — gap index and censor attribution refresh

**Captured:** 2026-10-16T04:27:21Z
**Mission status:** active; the finalized gap prefix remains partial.

## Scheduled gap-detail progress

The 04:20:00 UTC gap-detail batch exited successfully at 04:21:18 UTC with
status 0 and zero restarts. It processed 128 finalized segments / 33,042,875
bytes, used 3.939 CPU seconds, and peaked at 62.5 MiB. It read no active
segment.

| Measure | Result |
| --- | ---: |
| Processed / replayable segments | 2,545 / 5,224 |
| Cataloged / empty finalized segments | 5,226 / 2 |
| Pending segments / bytes | 2,679 / 736,206,152 |
| Processed source bytes | 613,809,470 |
| Campaign-window gap events / affected markets | 500 / 20 |
| Gaps without reported assets / unmapped affected assets | 1 / 0 |

The prior checkpoint covered 2,417/5,194 replayable segments and 435 campaign
gaps across 15 markets. This new prefix adds 128 processed segments and 65
campaign-window gap events across five additional affected markets. The index
remains incomplete; the latest timer is scheduled for 04:35 UTC.

## Versioned censor attribution

The read-only attribution audit consumed the sealed prefix and a SQLite
read-only transaction. It scanned 40,075 censored outcomes; 339 had
gap-related labels, with no truncation. It verified exact source references
in 133 finalized segments / 58,443,329 bytes and 157 unique records. No open
source segment was read. The SQLite event hash chain and full database
integrity were not reverified.

| Link status | Outcomes |
| --- | ---: |
| Candidate preceding same-market gap | 63 |
| Exact recorded gap verified and indexed | 100 |
| Exact recorded gap verified, not yet in gap index | 79 |
| No prior same-market gap in indexed prefix | 72 |
| Termination after indexed prefix | 25 |

The 63 temporal candidate links refer to nine unique gap events; 41 are over
one hour old at the termination receiver time. There are 61 unique exact
recorded gap events now indexed. The count of terminations after the indexed
prefix fell from 86 in attribution 001 to 25, while exact recorded references
not yet indexed remain at 79. A same-market preceding gap is still temporal
association, not proof of causality or venue unavailability.

Artifact 002 is
`VERITAS_MISSION2_CENSOR_GAP_ATTRIBUTION_002.json`, file SHA-256
`ccb2ab5c40c4ab7eeaa22e1e3b5e2d209e09db1807de1f76cb0dba24e1ae035f`, result
digest `cd8ee8b73c5923bd58dc4042b5220465452ed0a86f75885141a109d99bb051d2`.
Artifact 001 is preserved unchanged.

## Limits

The gap index covers a partial finalized prefix. Receiver-time gaps do not
establish exchange quote time, continuous book impairment, or direct cause of
a censored outcome. This audit did not rewrite campaign labels, run SQLite
integrity checks, or claim fills or profitability. The frozen campaign,
recorder, shadow worker, and scheduled services were not modified or
restarted.
