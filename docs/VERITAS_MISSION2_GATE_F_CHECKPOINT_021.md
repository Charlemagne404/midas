# Gate F checkpoint 021 — scan 35 qualification and bounded gap-detail replay

**Captured:** 2026-10-15T21:22:40Z  
**Mission status:** active; Arena completed scan 35 and the Director manifest awaits scheduled reconciliation.

## Scheduled Director and Arena result

The 21:15:31 UTC Research Director cycle admitted one bounded qualification
for scan `scan-20261015T210215Z-1f43257737f1`. The Arena job completed at
21:16:12 UTC:

- Job: `job-b8352727baca4803824a6b95`
- State: `COMPLETED`, exit status 0, no error; 35/35 events processed
- Finding: `veritas-qualification-v1-c92a948f88c300e1`
- Run: `VERITAS-M2-ECO-QUAL-001-V3-RUN-c835a985c45f`
- Dataset SHA-256: `c835a985c45fe938589c9a67aecc385d75fb28b469aab46cf0e2d794581c8b2b`
- Experiment SHA-256: `7c34933b8c5f54b0dc3c490bc1b224c1e6277a8aa8b8b8d2ea0ea0304f78f7aa`
- Job-file SHA-256: `b2e49956b0630b18cbd223e63c7e5e44f31e712faa41616c1515ccc463f73839`
- Finding-manifest SHA-256: `3bbc5a71ed9633eea379fd9eb04582cb75d06fb366e3c07627491c154b516151`

The finding contains 35 snapshots / 1,400 selected pairs / 1,237
quality-valid pairs / 163 invalid pairs / 648 distinct market IDs. The maximum
top-pair edge is -$0.001 per share; positive count is zero. Top-ask gross,
full displayed depth, both per-leg minimums, single-match fees, and the
fragmentation-safe fee gate all return zero positive states. Candidate
evidence is complete with zero rows; independent replay is complete with zero
candidates. The result is `no_positive_gross_candidate_observed` and supports
the current hypothetical no-trade baseline. It says nothing about fills or
realized P&L.

No authenticated request was used and no order was submitted. The Arena job
completed through the existing scheduler; no manual poll, retry, service
restart, or overlapping job was started.

## Manifest projection timing

The Director manifest currently names scan 35 and job
`job-b8352727baca4803824a6b95`, but reports `current_job_state=QUEUED` and scan
34 as the latest qualified scan. The authoritative Arena job and finding are
terminal and successful. The scheduled 21:45 UTC Director cycle should
reconcile this projection. Model readiness remains
`NOT_READY_NO_CANDIDATE_RELEVANT_TARGET`; independent confirmation remains
`NOT_READY_LESS_THAN_48_HOURS_OR_NO_INDEPENDENT_SEQUENCE`.

## Finalized-source and gap-detail progress

The 21:10:14 UTC source-analysis recurrence completed at 21:14:02, processing
125 segments / 33,387,810 bytes. The cumulative source prefix is 3,641/4,377
cataloged segments, with 736 / 237,913,078 bytes pending. It includes 204,052
quality-valid campaign-window states over 57 markets and zero positive states
at every tracked gross or economic gate. The campaign-window aggregate has
1,031 `book_resynchronization` markers and one `connection_failure`.

The new independent gap-detail timer completed its 21:20 UTC batch at
21:21:07. Its cursor now covers 256/4,396 replayable segments, ending at
ordinal 13,113 / 2026-10-14T10:15:11Z—well before the frozen campaign starts.
It has detailed 466 all-period gaps, verified against the raw finalized
records, but has not yet reached campaign-window records. Its event chain,
state, and code are independently pinned in
[Gate A checkpoint 032](VERITAS_MISSION2_GATE_A_CHECKPOINT_032.md) and [gap-detail
prefix artifact 001](VERITAS_MISSION2_GAP_DETAIL_PREFIX_001.json).

The relevant one-shot units exited successfully with zero restarts or swap.
Source analysis peaked at 134.6 MiB and used 11.574 CPU seconds; gap detail
peaked at 131.5 MiB and used 3.307 CPU seconds. The Reality recorder and frozen
shadow remain active, with zero recorder restarts and one prior shadow restart.
Midas API/web and Reality API/web remain active with zero restarts. No HTTP
probe was run at this capture; no service or campaign was changed.

The current Veritas Arena job is complete. A prior queued Veritas job remains
failed because its pinned research source changed before it was scheduled;
the current scan 35 job was submitted against the current revision and
completed successfully. This older failure does not change scan 35 evidence.
