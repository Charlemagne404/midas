# Veritas Mission 2 Gate A Checkpoint 005 — Scheduled Source Replay

- **Captured:** 2026-10-15 07:15 UTC
- **Branch:** `project/veritas`
- **Protected Reality commit:** `714f824`
- **Status:** The first scheduled source-analysis recurrence after timer catch-up completed successfully; source catch-up and public observation remain in progress.

## Scheduled source-analysis recurrence

The source timer fired at 07:10:59 UTC. Its oneshot exited successfully at
07:13:05 UTC (exit status 0), after 126 seconds. Systemd recorded 6.318 seconds
of CPU use, a 111.2 MiB peak, and no swap. The bounded batch processed 18
segments / 31,822,927 source bytes before the next segment would have exceeded
the 32 MiB per-run byte limit.

The analyzer restored the prior serialized context and advanced the immutable
prefix from 256 to 274 of 2,722 replayable segments. It skipped two validated
empty finalized headers. The latest processed ordinal is 15,189 and cumulative
processed source bytes are 60,554,062. There are 2,448 segments / 604,079,176
bytes pending. Readiness remains `catching_up_finalized_source`.

No campaign-window frames, quality-valid states, or positive states have
appeared in the processed prefix. These bootstrap records provide no economic
observation. The public snapshot analyzer is a separate stream.

## Source and event lineage

- Pinned campaign ID: `adf91d042ab8f91678834b9258bfde70022a763dfda8c91d1e94be334583aa46`
- Campaign file SHA256: `aa8acb2b46823c1a1e3ac5d01a57dde917746c2c7471098ae2a4598875e322f5`
- Analysis code SHA256: `9f9e2249b49dd1cb10c11713aa2683567aa9cf0914c3ed2b08cf8e3fea25ebf8`
- Recomputed source-code manifest: all 11 files match the saved manifest and aggregate digest.
- Processed prefix catalog SHA256: `223d5ec840ed376a0eba9bd769c9553b247cfddd42bb60c2980ee87e2d524bcc`
- Latest event digest: `e96f68019f96de3f62a6500e00699b1761b40882621fe61dd6df63cf9b6c8079`
- Cumulative event-chain SHA256: `3da2c0c3940a9846dcb38dd7262ffa0db0b462be568eab3c256a2a15c34cd773`
- Latest event file SHA256: `3e8b7509c3948e11202a57a0e0a019df0e45549b2d0e7238f7ad0a45268cb227`
- State digest: `2bb042f4443133c3ca44323a405315d7b64cbc1d522b72cef1df04455bdd6e54`
- State file SHA256: `cfde8b2fa3369112527fc0790a1d127b1262bd4a02b122829de8be481dd8751f`
- Summary digest: `b17186545f8d071533371d786ff89846feac5e6bc378f7c5bc0c460074c9e9b6`
- Summary file SHA256: `0b960be432d4bb59d96e6669aacfd666706d3ffa7de210d54e73769d38c3f17a`
- Observatory data root: 5,859,151 bytes, below its 1 GiB limit.

## Independent public observation

The 07:00:35 UTC public scan is
`scan-20261015T070035Z-12f2eac522c9`, with evidence SHA256
`12f2eac522c954839d6a9f6b8c85d012e73fafb5af580aa274c15c3e1d89afe1`. Its
analysis v2 event was indexed by 07:00:41 UTC; the index now contains eight
snapshots and has no pending work. The eight-snapshot panel spans about 61
minutes, with 320 selected observations, 286 quality-valid pairs, 34 invalid
pairs, and 142 distinct markets.

The deterministic economic qualification run
`VERITAS-M2-ECO-QUAL-001-RUN-94406141f63a` found zero positive states at top
ask, 20-share full depth, per-leg minimum notional, and either fee sensitivity.
The top-edge median is -0.029 and the maximum is -0.001 per share. This is a
short, selected, correlated panel and a candidate-qualification result; it does
not imply fills or profitability.

## Operations and preservation

The source timer is active and the oneshot is inactive after success. The next
source calendar event is 07:40:01 UTC. The snapshot timer is active; its next
event is 07:30:58 UTC. Both services remain bounded and write only under the
Veritas observatory root.

The separate Reality checkout remains clean at `714f824`, and
`midas-reality.service` remains active. The analyzer read finalized cataloged
`.seg` inputs only; it did not open `.open`, write Reality, restart a Reality
unit, or take a writer lock.

## Evidence and limitation

This is the first ordinary calendar recurrence observed after the persistent
timer catch-up, so it confirms one scheduled execution in addition to the
catch-up run. It does not establish long-term recurrence reliability. Most of
the finalized-source catalog remains pending, and the processed prefix has no
campaign-window coverage. Continue bounded replay and recheck source identity,
progress, and resource use on later runs.
