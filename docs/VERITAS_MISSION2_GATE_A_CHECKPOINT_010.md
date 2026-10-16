# Veritas Mission 2 Gate A Checkpoint 010 — Fifth Scheduled Source Replay

- **Captured:** 2026-10-15 09:16 UTC
- **Branch:** `project/veritas`
- **Protected Reality commit:** `714f824`
- **Status:** The fifth scheduled source-analysis recurrence advanced within its bounds. The finalized-source catch-up and public observation study remain open.

## Scheduled source-analysis recurrence

The source timer fired at 09:10:54 UTC. Its oneshot completed successfully at
09:13:32 UTC (exit status 0), in 158 seconds. Systemd recorded 7.937 seconds
of CPU time, a 113.4 MiB memory peak, and no swap. The bounded batch processed
128 finalized segments / 26,555,999 source bytes.

The analyzer advanced from 658 to 786 of 2,959 replayable finalized segments.
It skipped two validated empty finalized headers. The processed prefix reaches
ordinal 55,101 and contains 127,645,268 bytes. There are 2,173 segments /
602,349,214 bytes pending. Readiness remains
`catching_up_finalized_source`.

The prefix contains 43,999 frame records overall, but zero fall inside the
frozen campaign window. It therefore has zero campaign-window frame records
and zero quality-valid campaign states. This recurrence adds no campaign
economic evidence and remains separate from the public snapshot panel.

## Integrity and preservation

All 786 immutable event files were folded into a rolling chain; the result
matches the analyzer state. The latest event's `analysis_event_sha256` is
`177eef647887a4d4a91ffc04d9b5d428d7c8049dd4607b4dcf786e32d2207c54`, and its
file SHA256 is
`22ca828295b927d9747ba2add6e411d86d49f249248339a5387466c3279b7b9a`. The
rolling event-chain digest is
`29b7a68aed1eb7890c6cb23ea927801ec86903b421a3acb60f3dca19b9d0c0b5`; the
sealed state digest is
`b7ef8decd2c7ec6443ea30117332f9bc04f9f69184df0229f0ed46416681a999`, with
state-file SHA256
`ef0e90c69377732eeab1ac7538a13fc1d9aa40480c0cd58e1e917350c2c4e5e7`. The
prefix catalog digest is
`ec7ae9b6ff983f517c5e2d62ecb15831b4bd6fa6b9141aa251b4210a5f6aa3d9`.

The sealed summary digest is
`3918ddc107a782e1f3a7148190e4b8bb7ac03ba39e79cc0601a45419452f0e48`; its
file SHA256 is
`b03b0f91f1e9e356343391f10857ec5c0e07313904eeefd58d712587f0910611`. The
analyzer reports that it did not read an active segment. It reads only
cataloged finalized segments and never opens `.open` files.

The observer and source-analysis timers are active; their next events are
09:30:26 UTC and 09:40:48 UTC. The Veritas data root uses 10,145,758 bytes of
its 1 GiB bound. The protected Reality checkout remains clean at `714f824`,
and the Reality API, collector, and shadow services are active. No Reality
writer or source record was changed or restarted.

The public panel is unchanged: the latest scan remains the 09:00:47 UTC scan,
and its twelve-snapshot qualification still has zero positive states. The
24-hour pilot review, original 48-hour follow-up and dependence requirements,
independent freshness/coverage evidence, and controlled Director workflow
remain open.

The current lineage and runtime state are recorded in [research inventory
011](VERITAS_MISSION2_RESEARCH_INVENTORY_011.json). Inventory 010 and Gate A
checkpoint 009 remain preserved.
