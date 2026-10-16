# Gate C checkpoint 009 — campaign-window gap attribution begins

**Captured:** 2026-10-16 02:48 UTC

**Mission status:** active; the gap index remains incomplete.

## Scheduled gap-detail run

The 02:35 UTC timer invocation started at 02:35:00 and exited successfully at
02:36:15. It processed 128 finalized segments / 31,714,730 source bytes, used
3.780 CPU seconds, had zero service restarts, and did not open an active
`.open` segment. The service and timer retain their existing 128-segment /
32-MiB per-run bounds and resource controls.

The prefix now covers 1,676/5,020 cataloged replayable segments and
383,377,554 bytes. It has 3,342 segments / 914,571,657 bytes pending. The
summary is `catching_up`; it must not be interpreted as a complete campaign
gap census.

## Newly attributed campaign-window gaps

The processed prefix now includes **73 campaign-window gap events**, all
`book_resynchronization`, with no missing reported asset IDs and no unmapped
affected assets. The observed counts by market ID are:

| Market ID | Gap events |
| --- | ---: |
| 559687 | 32 |
| 561251 | 30 |
| 5674900 | 40 |
| 5674902 | 15 |
| 5674915 | 33 |
| 5675021 | 10 |
| 665205 | 55 |

These per-market counts overlap the 73 gap events because one event can name
multiple affected markets. The full-period log contains 2,154 gap-detail
events across book resynchronizations, connection failures, malformed
constraints, process starts/stops, and scheduled refreshes. These records
identify reported feed events; they do not establish quote age, outage
duration, economic loss, or a causal explanation for frozen follow-up
censoring.

The count changed from zero campaign-window events to 73 because the indexed
prefix advanced into campaign time. Earlier zero counts were incomplete, not
evidence that the campaign had no gaps. Keep the staggered 15-minute cadence,
allow further scheduled runs to finish, and join exact asset/time evidence to
the frozen censor labels only after the prefix is complete. See the current
[gap-detail summary](../data/veritas-observatory/gap-detail-summary-v1.json),
[operations checkpoint](VERITAS_MISSION2_OPERATIONS.md), and [inventory
054](VERITAS_MISSION2_RESEARCH_INVENTORY_054.json).
