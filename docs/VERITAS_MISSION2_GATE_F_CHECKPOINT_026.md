# Gate F checkpoint 026 — scan 43 qualification and source catch-up

Captured 2026-10-16 01:18 UTC. This records the scheduled scan-43
qualification, its read-only finding validation, the latest finalized-source
analysis, and a current operations snapshot.

## Scan 43 Arena qualification

The scheduled Research Director ran at 01:15:33 UTC and exited successfully
at 01:16:04 UTC. It admitted one scan-pinned Arena child,
**job-4653ecaf1d5d457f8530c8bc**. The child completed at 01:16:15 UTC with
exit status 0, all 43/43 source events processed, and 2.725 seconds elapsed.
Its finding is **veritas-qualification-v1-8a9f2a1a489aeb3c** and its run
identity is **VERITAS-M2-ECO-QUAL-001-V3-RUN-c1a50c704723**.

| Evidence artifact | SHA-256 |
| --- | --- |
| Arena job record | `faac8a1926cf25cd13c3c0ec8ac7b5c312173787b2368ac2f5a722d7ad0fbfca` |
| Arena source manifest | `379c619fdd2d5e5386974985e58a2ab66a5a6f5b224a5a610c8bef1f5f7f5124` |
| Qualification finding manifest | `08afbe0154fd8dd79c16cc4dfee33306d154273b939875c9c50839e319253a1a` |
| Submitted Arena source revision | `7ea33c451b69fc5ab3429c0808a13279fd3d8ffc816a37a76207fc205cf0b163` |
| Experiment digest | `b33be2ab08cf41cb91c7cca014f63fc8b57b561d808093a4b065a51524676521` |
| Qualification dataset digest | `c1a50c704723d6af4a749eb7622d1ddb772713afb6631e2658cbec34e75df42e` |

The job source-manifest hash matches the submitted source revision. The
read-only `_finding_summary` validator accepted the finding identity,
experiment digest, expected scan identity, complete candidate evidence,
complete empty source replay, and read-only flags.

| Qualification measure | Result |
| --- | ---: |
| Repeated snapshots | 43 |
| Selected pair states | 1,720 |
| Quality-valid pair states | 1,499 |
| Distinct selected market IDs | 784 |
| Maximum / median top edge | -$0.001 / -$0.020 per share |
| Positive states at each of the five economic gates | 0 |
| Candidate evidence | Complete, 0 rows |
| Candidate replay | `NO_POSITIVE_CANDIDATES_TO_REPLAY`, complete |

The five gates are unchanged top-ask gross sign, full displayed-depth gross,
full depth plus both per-leg minimums, single-match fee sensitivity, and
fragmentation-safe fee sensitivity. Keep no-trade. This qualification is a
reproducible comparison over selected repeated observations; it is not a
profitability, fill, or venue-wide prevalence result.

The Director manifest was updated at 01:15:57 UTC, before the child finished.
It still shows state `RUNNING`, the scan-43 child as `QUEUED`, and scan 42 as
the last qualified scan. The next scheduled Director cycle is 01:45:26 UTC.
No manual poll, retry, or duplicate admission was made.

## Finalized-source analysis

The one-shot that began at 01:10:31 UTC exited successfully at 01:13:55 UTC.
Its summary covers 4,485/4,851 finalized segments and 1,168,046,089 processed
source bytes, with 366 segments / 89,139,824 bytes pending. It reports
286,617 quality-valid campaign-window states across 72 markets and zero
positive top-ask, quantity-depth, full-depth, or per-leg-minimum states. The
analysis remains `catching_up`; it did not read the active `.open` segment.

The gap-detail summary has not refreshed in this checkpoint. Its last
completed prefix remains the partial 00:51 UTC result documented in [checkpoint
025](VERITAS_MISSION2_GATE_F_CHECKPOINT_025.md); it ends before the frozen
campaign window, so its zero campaign-window gap count is not a result.

## Current system health and next steps

At 01:18 UTC the local API reported `READY` with live execution disabled. The
Reality recorder and shadow, Midas API and web, and Reality API and web were
active. The collector continues to report `RECORDING_UNSEQUENCED`; its current
raw root is 1,261,164,701 bytes and capacity reported no alerts, with about
33.7 days remaining at the measured recent growth rate. Filesystem usage was
56% with about 212.35 GB available. Available memory was about 10.47 GB and
swap use about 3.76 GB; CPU usage was not sampled.

The shadow worker has one historical restart after a finalized-source
integrity/continuity mismatch on 2026-10-15. It is active now, and its restart
count did not increase today. No collector, shadow, timer, pilot, or frozen
campaign was restarted or changed for this checkpoint.

Let the scheduled 01:20 UTC gap-detail batch run, then wait for the 01:45:26
UTC Director reconciliation. Keep the fixed measurement pilot and its
19:00:55 UTC stop unchanged; keep the discovery successor gated and no-trade.
