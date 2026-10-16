# Gate F checkpoint 025 — scan 42 qualification and source catch-up

Captured 2026-10-16 00:52:13 UTC. This checkpoint records the scheduled
scan-42 qualification, its current Director projection state, and the latest
completed Gate C summaries.

## Scan 42 Arena qualification

The scheduled Research Director admitted
`scan-20261016T003208Z-f65962fb4420` to Arena at 00:45:31 UTC. Child job
`job-aa54e348ab8347b3b1771479` completed at 00:45:46 UTC with all 42 events
processed, exit status 0, no error, and 2.715 seconds elapsed. Its finding is
`veritas-qualification-v1-d6329d3c4c93c779`; the run identity is
`VERITAS-M2-ECO-QUAL-001-V3-RUN-d449697ba6fe`.

The read-only `_finding_summary` validator accepted the finding identity,
experiment digest, expected scan, complete gross-candidate evidence, empty
source replay, and read-only flags. The Arena source manifest's `source_hash`
matches the job's submitted source revision hash.

| Evidence artifact | SHA-256 |
| --- | --- |
| Arena job record | `e397b8bea171756ccd9fd20ea567f176abe8980a52b500b82b477060fa585d43` |
| Arena source manifest | `379c619fdd2d5e5386974985e58a2ab66a5a6f5b224a5a610c8bef1f5f7f5124` |
| Qualification finding manifest | `d36b902567e436c39f8d33935db12d378d271902cf403dfdd0409c44067d35bb` |
| Submitted Arena source revision | `7ea33c451b69fc5ab3429c0808a13279fd3d8ffc816a37a76207fc205cf0b163` |

The v4 panel covers 42 repeated snapshots, 1,680 attempted pairs, 1,467
quality-valid pairs, and 760 selected market IDs. Its maximum top-pair edge is
-$0.001/share and median edge is -$0.020/share. Positive-state counts are zero
for the unchanged top-ask gross baseline, full displayed-depth gross,
full-depth plus both per-leg minimums, single-match fee sensitivity, and
fragmentation-safe fee sensitivity. Candidate evidence is complete with zero
rows; replay status is `NO_POSITIVE_CANDIDATES_TO_REPLAY` and complete.

This is an end-to-end qualification comparison between the unchanged top-ask
baseline and a depth/minimum-aware research rule. It demonstrates that the
pipeline reproduces the empty funnel over this panel. It does not establish
strategy P&L, fills, persistence, or independent confirmation.

## Director projection and scheduling

The child finished after the scheduled Director admission returned. At the
00:52 UTC capture, Arena's job record was `COMPLETED`, but the Director
manifest still showed `RUNNING` with the current job `QUEUED`; its last
qualified scan remained scan 41. The manifest had not yet reconciled the
completed child. Its next scheduled cycle is 01:15:26 UTC. No manual poll,
retry, or duplicate admission was issued.

The same older failed systemd unit visible in the unit inventory is
`job-8cf39368af21426ea3127501`, created on 2026-10-15 for scan
`scan-20261015T110153Z-93de340dd5ce`. It failed because the research source
changed while queued. It is not scan 42's child. Scan 42's child completed
successfully. Two other failed Arena units point to `/home/charlie/midas/data/arena`,
outside this Veritas checkout; they were not modified.

## Gate C source progress

The finalized-source summary generated at 00:43:45 UTC covers 4,357/4,791
segments. It reports 278,820 quality-valid campaign-window states across 68
markets and zero positive top-ask, quantity-depth, full-depth, or
minimum-notional states. There are 434 segments / 102,705,853 bytes pending.
The active `.open` segment was not read.

The gap-detail summary generated at 00:51:10 UTC covers 944/4,812 catalog
segments, with 3,866 / 1,052,399,662 bytes pending and 1,793 all-period gap
events. Its last retained gap is at 16:08:17 UTC on 2026-10-14; the frozen
campaign window begins at 21:07:58 UTC that day. There are still zero
campaign-window gaps in the processed prefix, so this is not a campaign
finding. The active `.open` segment was not read.

Both analyzers' 00:40 and 00:50 one-shots exited successfully. The v1
observer, source analyzer, gap-detail analyzer, and Director services were
inactive at capture; their timers remained active. Reality recorder and
shadow, Midas API, Reality API, and web services reported active. Available
memory was 10,419,458,048 bytes, swap use was 3,737,452,544 bytes, and disk
usage was 56% with 212,392,939,520 bytes available. The observatory root was
41,564,082 bytes. CPU usage was not sampled.

No service, timer, campaign, pilot, or artifact was restarted or manually
changed. The next scheduled runs at capture were observer 01:01:30 UTC, source
analysis 01:10:29 UTC, Director 01:15:26 UTC, and gap-detail analysis
01:20:00 UTC.

Mission 2 remains active. Keep no-trade, continue the scheduled read-only
research, and wait for the Director's scheduled reconciliation before
reporting scan 42 as reconciled by the Director.
