# Gate C checkpoint 010 — second campaign-window gap batch

**Captured:** 2026-10-16 02:55 UTC

**Mission status:** active; finalized-source gap indexing remains incomplete.

## Scheduled 02:50 UTC run

The 15-minute timer started the bounded gap-detail service at 02:50:00 UTC.
It exited successfully at 02:51:13 after processing 115 finalized segments /
33,465,203 source bytes. The run used 3.656 CPU seconds, had zero restarts,
and did not read an active `.open` segment.

The index now covers 1,791/5,049 cataloged segments and 416,842,757 processed
bytes, leaving 3,256 segments / 888,351,418 bytes pending. Its status remains
`catching_up`.

## Campaign-window attribution

The campaign-window total increased from 73 to **131** gap events, all
`book_resynchronization`. No campaign-window gap event lacked reported asset
IDs, and none of the affected assets were unmapped. The per-market counts are
overlapping event attributions, not event totals:

| Market ID | Gap attributions |
| --- | ---: |
| 559687 | 59 |
| 561251 | 58 |
| 5674900 | 74 |
| 5674902 | 15 |
| 5674915 | 73 |
| 5675021 | 21 |
| 665205 | 96 |

The increase is evidence that the earlier zero count was a pre-campaign
prefix artifact, not evidence of no campaign-time gaps. It still does not
establish quote age, outage duration, economic impact, or causal relation to
the frozen follow-up censors. Keep the timer cadence and wait for the index to
complete before making those joins.

The full summary is
[gap-detail-summary-v1.json](../data/veritas-observatory/gap-detail-summary-v1.json)
with digest `d262daba8359134789d1ade5a12cac02c7f6c3116c73d872b4f514c4ccce5012`.
See [checkpoint 009](VERITAS_MISSION2_GATE_C_CHECKPOINT_009.md), [operations
state](VERITAS_MISSION2_OPERATIONS.md), and [inventory
055](VERITAS_MISSION2_RESEARCH_INVENTORY_055.json).
