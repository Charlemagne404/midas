# Gate F checkpoint 036 — scheduled scan 71 qualification

At 15:15 UTC on 2026-10-16 the existing Research Director timer admitted one
bounded Arena qualification for finalized scan 71. No manual admission, retry,
or campaign change was made.

Arena completed job `job-4fcf2252f1d84e53a54e0966` in 5.32 seconds, processing
all 71 scan events (1,303,680 source bytes) under its existing 10% CPU, 512
MiB memory, and 300-second wall bounds. Finding
`veritas-qualification-v1-a68c91de3c2245a9` is pinned to scan
`scan-20261016T150117Z-366ac2e7f8ea` and experiment run
`VERITAS-M2-ECO-QUAL-001-V4-RUN-1eee813f5361`.

The unchanged top-ask baseline, complete displayed-depth gross check, both
per-leg minimum checks, and both fee sensitivities each reported zero positive
states. Candidate evidence is complete with zero rows; independent gross
candidate replay is complete with zero candidates. The v4 research improvement
uses a finalized-event USD-notional prefilter followed by independent share-
minimum and fee replay. It adds qualification rigor but did not change the
economic result. This is not evidence of strategy P&L or fills.

The Arena child is complete. The Director's 15:15 UTC snapshot still reports
scan 70 as last qualified and scan 71 as the latest scan with the child
admitted; the next normal Director cycle should reconcile the completed
finding. Model readiness remains `NOT_READY_NO_CANDIDATE_RELEVANT_TARGET`, and
strategy readiness remains `NOT_READY_NO_QUALIFIED_GROSS_CANDIDATE`.

Evidence: Arena job file `data/arena/jobs/job-4fcf2252f1d84e53a54e0966/job.json`
and finding manifest `data/arena/findings/veritas-qualification-v1-a68c91de3c2245a9/manifest.json`.
