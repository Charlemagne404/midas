# Gate F checkpoint 020 — scan 34 qualification admitted and completed

**Captured:** 2026-10-15T20:46:29Z  
**Mission status:** active; Arena completed scan 34, while the Director manifest awaits its scheduled reconciliation.

## Scheduled Director and Arena result

The 20:45:05 UTC Research Director cycle reconciled scan 33 and admitted one
bounded qualification for scan
`scan-20261015T203154Z-c77f2bb45c60`. The Arena job completed at 20:45:47 UTC:

- Job: `job-e47f6ced4e8f4900965b7179`
- State: `COMPLETED`, exit status 0, no error; 34/34 events processed
- Finding: `veritas-qualification-v1-ef893dbea8f4dfa4`
- Run: `VERITAS-M2-ECO-QUAL-001-V3-RUN-908a516db21c`
- Dataset SHA-256: `908a516db21c122f69c327d0187355c5b004bb72fa188693f48b7467b72b3411`
- Experiment SHA-256: `d9e609db6df6f5aa0222766d2e8a70cbaccf0eb75ac2cf120df3e942f17214c0`
- Submitted-source SHA-256: `4ba1520664464185673cc66a747278805b35f8bfbf3f51ffbff1c2bd3fc2fbcb`
- Job-file SHA-256: `5a691ef188a9bc0fa6ac210eb45111f33324c4221e5d757155c0f2c61068c1ae`
- Finding-manifest SHA-256: `f22cca18093a3e82d3412ada6e6d02d003f243ab5b7459a854a968ebe485cbf4`

The finding's sample contains 34 snapshots / 1,360 selected pairs / 1,202
quality-valid pairs / 158 invalid pairs / 632 distinct market IDs. The maximum
top-pair edge is -$0.001 per share; median is -$0.020; positive count is zero.
Top-ask gross, full displayed depth, both per-leg minimums, single-match fee,
and fragmentation-safe fee gates all return zero positive states. Candidate
evidence is complete with zero rows; replay is complete with zero candidates.
The result is `no_positive_gross_candidate_observed`. It supports the current
hypothetical no-trade baseline but says nothing about fills or realized P&L.

No authenticated request was used and no order was submitted. The Arena job
was completed by the existing scheduler; no manual poll, retry, service
restart, or overlapping job was started.

## Manifest projection timing

At capture the Director manifest was last updated at 20:45:30 UTC. It names
scan 34 and the correct job, but still reports `current_job_state=QUEUED` and
scan 33 as the latest qualified scan. The authoritative Arena job and finding
are terminal and successful. The next scheduled Director cycle at 21:15 UTC
should reconcile this projection. The Director keeps model readiness at
`NOT_READY_NO_CANDIDATE_RELEVANT_TARGET` and independent confirmation readiness
at `NOT_READY_LESS_THAN_48_HOURS_OR_NO_INDEPENDENT_SEQUENCE`.

## Source and operations

The finalized-source replay completed at 20:43:30 UTC, processed 128 segments
/ 30,416,223 bytes, and used 9.376 CPU seconds / 133.5 MiB peak memory / no
swap. The prefix is 3,516/4,318 cataloged segments with 802 / 254,804,640
bytes pending. It contains 192,716 quality-valid campaign-window states over
57 markets, with zero positive top-ask or full-depth states. The campaign
summary counts 972 `book_resynchronization` markers and one
`connection_failure`; individual marker timing is still not present in the
sealed event index. See [Gate A checkpoint 031](VERITAS_MISSION2_GATE_A_CHECKPOINT_031.md).

At 20:46:29 UTC the Reality recorder and frozen shadow were active. Recorder
restart count was zero; the shadow had one prior restart. Midas API/web and
Reality API/web units were active with zero restarts. The one-shot Veritas
services were idle and all three recurring timers were active. Host load was
1.38 / 1.32 / 1.31 on six logical CPUs; memory available was 8.9 GiB, swap
use 3.6/4 GiB, disk free 199 GiB (56% used), and observatory data occupied
40 MiB. These are systemd/process and filesystem checks; no HTTP health probe
was run at this capture. No service or campaign was changed.
