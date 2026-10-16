# Gate F checkpoint 017 — scheduled scan 31 qualification

**Captured:** 2026-10-15 19:16 UTC
**Mission status:** active; qualification completed, Director manifest awaiting its next scheduled reconciliation.

## Scheduled Director cycle

The 19:15 UTC Research Director timer completed normally. At 19:15:46 UTC it
admitted one bounded Arena job, pinned to scan
`scan-20261015T190055Z-7799523b9d87`. Job
`job-c2b34af59d624f2ea3081b54` completed all 31 events with exit status 0 in
1.914 seconds. It created finding
`veritas-qualification-v1-b3744235647f846e` at 19:15:59 UTC.

The v3 qualification processed 31 scans / 1,240 selected pairs / 1,102
quality-valid pairs / 138 invalid pairs across 575 distinct market IDs. It
found zero positive states at each of the five gates: top-ask gross, full
displayed depth, per-leg minimums, single-match fees, and
fragmentation-safe fees. Candidate evidence is complete with zero rows, and
the replay status is `NO_POSITIVE_CANDIDATES_TO_REPLAY`. The result keeps
no-trade, marks strategy readiness `NOT_READY_NO_QUALIFIED_GROSS_CANDIDATE`,
and marks model readiness `NOT_READY_NO_PUBLIC_OUTCOME_LABELS`.

The persisted result is `VERITAS-M2-ECO-QUAL-001-V3-RUN-564bd76d67f1`,
dataset digest
`564bd76d67f14671d1b6787e4b7ec24aedd421c50a61bd92b4eebc443c711c9a`, and
experiment digest
`f6c75633d02db413edabd41c0b3597d08ac1365884c12f6c9abf43e5261d6ab7`. The
finding file SHA256 is
`b9311062873e56d6d3464140f2d54f9ac9d9584b1ecc694239742d2cc0d6f1d7`.

## Manifest and operational status

The Arena job record is terminal and successful. At capture, the Director
manifest still projected its `current_job_state` as `QUEUED`, while naming
scan 31 as the current scan and scan 30 as last qualified. This is a delayed
projection; it is not evidence that the Arena job is still running. The next
Director timer is 19:45:26 UTC. No manual poll, retry, or service restart was
run.

The Director one-shot exited normally after about 31 seconds wall time, using
1.55 CPU seconds and peaking at 64.4 MiB. It admitted only this one job. No
orders or authenticated requests were used. The new finding and manifest are
under `data/arena/findings/` and
`data/arena/directors/director-veritas-opportunity-v1/`.

## Interpretation

The scan-pinned qualification confirms the current no-positive result through
the latest 31-scan panel and independently runs the candidate source-replay
path in its complete zero-candidate mode. The positive-candidate branch still
has synthetic fixture coverage only; no genuine candidate has exercised it.
This remains a qualification result, not a PnL or fill experiment. The source
panel is selected and observations are correlated. Keep observation and
finalized-source analysis scheduled, and do not launch strategy or model work
without an eligible gross candidate and suitable labels.
