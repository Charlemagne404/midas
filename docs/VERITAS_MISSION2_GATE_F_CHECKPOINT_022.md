# Gate F checkpoint 022 — scan 37 qualification and scheduled replay progress

**Captured:** 2026-10-15T22:26:02Z  
**Mission status:** active; scheduled analysis and the fixed coverage pilot continue.

## Scheduled Research Director and Arena qualification

At 22:15:26 UTC, the scheduled Director admitted one scan-pinned qualification
for `scan-20261015T220039Z-1bcb8753082e`. Arena completed job
`job-91acafbffec74604be3eacf5` with exit status 0, no error, and all 37/37
source events processed in 2.316 seconds. The finding is
`veritas-qualification-v1-0c90e8c4bf939671`; its experiment run is
`VERITAS-M2-ECO-QUAL-001-V3-RUN-a711bc835c73`.

The v3 result compares the unchanged top-ask gross-sign baseline with the
implemented depth- and per-leg-minimum-aware qualification on the same
37-snapshot dataset. Both report zero positive states. The subsequent funnel
also reports zero at full displayed depth, both per-leg minimums,
single-match fees, and fragmentation-safe fees, for all five quantities. The
dataset contains 1,307 valid pairs over 689 selected market IDs, with maximum
edge -$0.001 and median -$0.020 per share. Candidate evidence is complete
with zero rows, and the independently replayed empty candidate set reports
`NO_POSITIVE_CANDIDATES_TO_REPLAY`. No authenticated request or order was
submitted. This is an end-to-end economic qualification result, not a
strategy-P&L or execution result.

The Arena job record is authoritative and terminal, but the Director manifest
still projects `current_job_state=QUEUED` and scan 36 as the last qualified
scan. Its next scheduled cycle at 22:45 UTC is the reconciliation point. No
manual polling or retry was used.

## Finalized-source analysis

The source analyzer completed its 22:10:44–22:14:25 UTC scheduled run. The
batch processed 89 finalized segments / 33,008,963 bytes using 11.037 CPU
seconds and 144.9 MiB peak memory, with no swap and zero restarts. The sealed
prefix covers 3,852/4,496 cataloged finalized segments; 644 segments /
198,051,788 bytes remain pending through ordinal 516,893. It contains 263,679
campaign-window frame records, 230,666 touched states, and 221,768
quality-valid states across 63 markets. Positive top-ask, requested-depth,
full-depth, and minimum-notional states remain zero. The run declared
`active_segment_read=false`.

## Incremental gap-detail analysis

The independent gap-detail service completed its 22:20 UTC scheduled batch
at 22:21:12 UTC, processing 128 segments / 25,719,771 bytes. It used 3.479
CPU seconds and 114.3 MiB peak memory, used no swap, and exited successfully
without restart. Its sealed prefix now covers 402/4,514 replayable finalized
segments, with 4,112 segments / 1,088,795,757 bytes pending. It contains
1,614 all-period gap events: 1,557 resynchronizations, five malformed
constraints, 12 process starts, 10 process stops, and 30 scheduled refreshes.

No indexed gap falls in the frozen campaign window yet. The latest indexed
gap event is at 2026-10-14T11:27:49Z, before campaign start at
2026-10-14T21:07:58Z, so the current zero in-window count remains partial and
uninformative. The extractor reads finalized segments only, declares
`active_segment_read=false`, and does not mutate the primary analyzer cursor
or frozen campaign.

## Runtime and limitations

The latest one-shot units completed successfully with zero restarts and zero
swap. The latest Veritas finding and research artifacts remain read-only; no
production service, Reality recorder, frozen campaign, source segment, or
coverage-pilot protocol was changed. The gap-detail replay is still catching
up, the Director projection awaits its scheduled reconciliation, and
independent sequence/freshness evidence remains unavailable. Gate F remains
in progress.
