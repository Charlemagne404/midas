# Gate C checkpoint 004 — exact source audit for gap censors

**Captured:** 2026-10-15 21:54 UTC
**Mission status:** active. The frozen campaign remains unchanged, the bounded
gap-detail timer is catching up, and the six-scan 24-hour snapshot coverage
pilot is still running to its fixed stop.

## Current frozen-campaign censoring

The versioned v1.4 forensic report was rerun against one read-only SQLite
snapshot with a 50,000-decision limit, no truncation, and no full database
integrity scan. It reports 10,253 decisions across 43 markets and 37 connected
families: 3,503 valid initial states and 6,750 invalid. Across 41,012 scheduled
horizon slots, 937 public markouts were observed, 40,075 were censored, and
none were pending.

| Horizon | Public markouts | Censored slots | Pending | Markouts / valid starts |
| ---: | ---: | ---: | ---: | ---: |
| 100 ms | 29 | 10,224 | 0 | 0.83% |
| 300 ms | 94 | 10,159 | 0 | 2.68% |
| 1,000 ms | 341 | 9,912 | 0 | 9.73% |
| 5,000 ms | 473 | 9,780 | 0 | 13.50% |

The 40,075 censored slots separate into 27,000 invalid-at-decision slots and
13,075 censors after a valid initial state. Initial invalidity is mainly
`stale_book` (6,059 of 6,750 invalid decisions) and an empty ask side (495);
the remaining causes are recorded separately in the machine-readable report.
Among all censor rows, `future_observation_unavailable` accounts for 10,233,
stale follow-up books 1,461, source-availability timeouts 970, and recorded or
reconstruction gap labels 339. The unavailable-future category still mixes
venue inactivity, cohort selection, and source coverage; it is not evidence
that those outcomes were economically null.

Coverage is concentrated. The two markets with the most five-second markouts
account for 411/473 (86.9%) of those measurements and 1,608/3,503 (45.9%) of
valid starts. Five-second hourly yield ranges from 6/200 (3.0%) to 44/228
(19.3%) across the observed UTC-hour groups. Those are descriptive repeated
measurements, not independent market-wide rates.

At five seconds, every observed row still has no initial discrepancy,
`opportunity_persistence=null`, and `execution_ground_truth=unknown_counterfactual`.
The public marks therefore do not provide a strategy target or fill/P&L
labels. Keep no-trade and defer model training.

The scheduled 21:40 source-analysis batch completed at 21:43:27 UTC. It
processed 122 finalized segments / 33.46 MB and now covers 3,763/4,436
cataloged segments, with 673 / 217.58 MB pending. The campaign-window replay
counts 210,181 quality-valid states across 63 markets, 1,089 resynchronizations
and one connection failure, and zero positive top-ask or full-depth states.
This aggregate has no per-gap timestamps; the supplemental gap-detail prefix
is still required for timing and affected-market attribution.

Observer scan 36 completed at 21:31:46 UTC with 35/40 pairs passing quality
and zero positive top-gross pairs. The cumulative 36-snapshot panel has
1,272/1,440 quality-valid pairs across 665 selected market IDs; its maximum
top-pair edge remains -0.001/share. The scan-pinned Arena qualification job
completed all 36 events with zero positives at all five gates and a complete
empty candidate replay. The finding is
`veritas-qualification-v1-42a676c47fba96b8`. The Director manifest has admitted
this scan but has not yet reconciled the completed Arena result.

The coverage pilot now has six scans and 202/240 valid pairs across 177
distinct selected markets. Its rotating cohort has 194/220 valid pairs and
the frozen stable controls have 8/20; this nonrandomized comparison remains
descriptive. It has recorded no skipped scans and remains active to its fixed
stop at 2026-10-16 19:00:55 UTC.

The scheduled 21:50 gap-detail batch completed successfully at 21:51:20 UTC
with zero service restarts. Under its 32 MiB source-byte bound it processed
18 segments / 31,822,927 bytes, advancing the verified prefix to 274/4,455
nonempty segments with 4,181 pending. Its sealed summary reports 1,152
all-period gap records (1,108 resynchronizations, five malformed-constraint
markers, 11 process starts, nine stops, and 19 scheduled refreshes). These are
not campaign-window counts. I independently decoded and checksum-verified
the terminal finalized segment: its last record is ordinal 15,189 at
2026-10-14 10:24:24.977 UTC, before campaign start at 21:07:58 UTC. The zero
campaign-window count remains uninformative. See [gap-detail prefix
002](VERITAS_MISSION2_GAP_DETAIL_PREFIX_002.json).

## Exact gap-reference audit

The new bounded audit scanned all 40,075 censored outcomes read-only. It found
339 gap-related censor rows:

- 179 `recorded_gap:book_resynchronization` outcomes reference 97 distinct raw
  gap records. All 97 matched the finalized source record's ordinal, receiver
  time, reason, offset, compressed-record hash, and canonical-record hash.
- 160 `book_issue:gap:book_resynchronization` outcomes reference 60 distinct
  termination records: 53 discovery-page records, two fee-metadata records,
  and five market-metadata records. Their source references verify, but those
  records are not the gap events themselves; this audit does not attribute
  them to a particular preceding gap.

The audit verified 157 unique termination records in 133 finalized segments.
It streamed 31,324,375 compressed event bytes under its 64 MiB cap, hashed
58,443,329 source-segment bytes under its 128 MiB cap, and read 3,020,478 bytes
of exact record frames. It did not reverify the SQLite hash chain or run an
integrity scan. The sealed result is
[`CENSOR_GAP_AUDIT_001`](VERITAS_MISSION2_CENSOR_GAP_AUDIT_001.json).

The independent gap-detail stream now indexes 274/4,455 nonempty segments.
Its highest-ordinal record is at 2026-10-14 10:24:24.977 UTC, before campaign
start. The report's zero in-window gap count is partial while the remaining
4,181 segments are pending. Preserve its pinned code and cursor while it
catches up; use the future timestamp-and-market index to investigate the 160
indirect book-issue labels and reconcile campaign-window gap totals. The
earlier 256-segment verification remains in
[gap-detail prefix 001](VERITAS_MISSION2_GAP_DETAIL_PREFIX_001.json).

## Verification and next work

- The full current censoring summary is in
  [`Gate A censoring report 004`](VERITAS_GATE_A_CENSORING_004.json).
- The paired request-to-receipt freshness comparison remains a separate
  snapshot measurement, not a change to frozen follow-up labels. The coverage
  pilot remains fixed and read-only; see the
  [measurement comparison](VERITAS_MISSION2_MEASUREMENT_COMPARISON_002.md)
  and [pilot protocol](VERITAS_MISSION2_MEASUREMENT_PILOT_001.md).
- Focused audit tests: **4 passed**. Ruff, formatting, and strict Mypy passed,
  including the audit test module.
- No services or campaigns were restarted or changed; no active `.open`
  segment was read; no network requests or orders were made.

This improves source attribution for explicit gap censors. It does not explain
the full `future_observation_unavailable` category, establish continuous feed
coverage, or turn public marks into executable outcomes.
