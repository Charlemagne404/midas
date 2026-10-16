# Gate F checkpoint 027 — scan 44 qualification and source replay

**Captured:** 2026-10-16 01:46 UTC

**Mission status:** active; no strategy or model is promoted.

## Scan 44 Arena qualification

The scheduled Research Director ran at 01:45:02 UTC and exited successfully at
01:45:33 UTC. It admitted one scan-pinned Arena child,
`job-c8a59c778af54704895630a9`. The child completed at 01:45:45 UTC with exit
status 0, all 44/44 source events processed, and 2.895 seconds elapsed. Its
finding is `veritas-qualification-v1-262313565b399a77`, with experiment run
`VERITAS-M2-ECO-QUAL-001-V3-RUN-ebdbd02b5c91`.

| Evidence artifact | SHA-256 |
| --- | --- |
| Arena job record | `193990a5669bc5d06886223b3265025f9ce00e06df08db2db83e1bdaa8b8b740` |
| Arena source manifest | `379c619fdd2d5e5386974985e58a2ab66a5a6f5b224a5a610c8bef1f5f7f5124` |
| Submitted Arena source revision | `7ea33c451b69fc5ab3429c0808a13279fd3d8ffc816a37a76207fc205cf0b163` |
| Qualification finding manifest | `2004cc133a7bc4030b2ccddb392a8589f486135d2713a87b1528f5c274821da1` |
| Experiment digest | `5b8d4de3eeb3956862624ba9b84236f68508b05fbbbfc16e672af491ca0380e9` |
| Qualification dataset digest | `ebdbd02b5c9184856aa8905ddc20f2cfb0c36f64d0acf314a96ad4cee85d97dd` |

The submitted source revision matches the source hash in the Arena manifest.
The read-only `_finding_summary` validator accepted the finding identity,
experiment digest, admitted scan identity, complete candidate evidence,
complete empty source replay, and read-only flags.

| Qualification measure | Result |
| --- | ---: |
| Repeated snapshots | 44 |
| Selected pair states | 1,760 |
| Quality-valid pair states | 1,534 |
| Distinct selected market IDs | 798 |
| Positive states at each of the five economic gates | 0 |
| Candidate evidence | Complete, 0 rows |
| Candidate replay | `NO_POSITIVE_CANDIDATES_TO_REPLAY`, complete |

The unchanged top-ask gross baseline and full-depth, minimum-notional,
single-match-fee, and fragmentation-safe-fee gates all remain zero. Keep
no-trade. This is a reproducible comparison over selected repeated
observations, not a fill or profitability result.

## Scheduled Director state

The manifest was updated during admission and still reports the scan-44 child
as `QUEUED`, with scan 43 as the last qualified scan. The child is durably
`COMPLETED`; no manual poll, retry, or duplicate admission was made. The next
scheduled Director cycle is at 02:15 UTC.

## Finalized-source replay and operations

The scheduled source analyzer started at 01:40:39 UTC and exited 0 at
01:44:13 UTC. It processed 128 segments / 30,224,014 bytes under the existing
128-segment / 32-MiB bound. Its cumulative prefix covers 4,613/4,910 finalized
segments and 1,198,270,103 bytes, with 297 segments / 72,605,628 bytes
pending. It reports 296,396 quality-valid campaign-window states across 72
markets and zero positive top-ask, quantity-depth, full-depth, or minimum-
notional states. The `.open` segment was not read.

The staggered gap-detail timer is active at :05, :20, :35, and :50 UTC; the
01:35 batch completed successfully and the next is due at 01:50 UTC. Its
separate prefix has not reached campaign time, so its zero campaign-window
gap count remains incomplete. The observer and qualification pipelines remain
read-only, and no orders or authenticated requests were used.
