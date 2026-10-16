# Veritas Mission 2 Operations

## Isolated browser verification — 2026-10-16T08:23:32Z

- The focused Veritas Playwright workflow passed 1 test in 5.6 seconds. It
  verified the coverage-design audit card, its stale 25-versus-26 scan label,
  displayed support and yield values, direct artifact endpoint, and
  no-venue-wide-inference limitation. See [Gate H checkpoint
  002](VERITAS_MISSION2_GATE_H_CHECKPOINT_002.md).
- The workflow used the configured temporary API on port 18000 and Vite on
  port 15173 with a temporary SQLite database and Arena root. Both ports were
  free after Playwright exited. No hosted service, campaign, or scheduled
  research job was restarted or modified; no public request, authenticated
  request, or order was made.
- This targeted browser check does not replace the full browser suite,
  Mission 2 regression, hosted deployment check, or preservation audit.
- The verified run is recorded in [Gate H checkpoint
  002](VERITAS_MISSION2_GATE_H_CHECKPOINT_002.md) and ledger H127.

- **Latest runtime/resource snapshot:** 2026-10-16T08:17:07Z
- **Latest source summary:** 2026-10-16T08:12:56Z
- **Latest gap-detail summary:** 2026-10-16T08:06:29Z
- **Latest Midas/Reality API health probes:** 2026-10-16T08:17:07Z

## Runtime checkpoint — 2026-10-16T08:17:07Z

- The Reality recorder is active with zero restarts, 8 markets / 16 books,
  ordinal 781,791, and 1,464,973,417 recorded bytes. Its state remains
  RECORDING_UNSEQUENCED and sequence_verified is false. The frozen shadow is
  active with one historical restart and remains WARMING_OR_LAGGED_SOURCE;
  its source receipt is from 2026-10-15T16:14:53Z and its last decision from
  2026-10-15T08:58:06Z. It has 43 markets, 47,911 observations, 40,075
  censored follow-ups, 937 measured follow-ups, and zero pending horizons.
- Midas and Reality APIs both returned HTTP 200 in demo mode with live
  execution disabled. Midas reported READY; Reality reported DEGRADED with
  startup READY. Their API/web services remain active. The Reality archive
  service remains failed after timeout with exit status 15 and zero restarts.
- Observer scan 57 (scan-20261016T080056Z-49ba7ada7fab) was captured at
  08:00:56 UTC. The observer panel has 1,945/2,280 quality-valid pairs and
  zero positive top-gross states. The measurement pilot remains at 26/48 scans
  and 842/1,040 valid slots across 608 selected IDs; audit 002 covers 25 scans.
- The 08:12:56 UTC finalized-source summary is current through 5,677/5,677
  segments / 1,460,522,573 bytes. It reports 386,158 quality-valid states
  across 101 markets and zero positive top-ask, full-depth, or
  minimum-notional states; it read no active segment.
- The 08:06:29 UTC gap-detail summary is partial at 4,242/5,665 replayable
  segments / 1,105,386,857 bytes processed. It has 1,423 segments /
  351,838,232 bytes pending and 1,327 campaign-window gaps indexed.
- The scheduled 08:15:58 UTC Director cycle reconciled scan 55 and admitted
  scan 57 as job job-df156882038246b497d9788a. The Arena job completed at
  08:16:17 UTC with no positive gross candidate. The manifest still shows
  QUEUED at its 08:15:58 update, pending the next scheduled reconciliation
  around 08:45 UTC. No manual poll or retry was made.
- Load average was 0.55 / 0.71 / 0.86; 9.6 GiB RAM was available and swap
  use was 3.8/4 GiB. Root disk use was 56%, with about 197 GB available.
  The Reality recording directory was 1.5 GB; the archive directory 922 MB;
  Veritas observatory data 84 MB; Arena data 76 MB.
- At capture, the next scheduled gap-detail, observer, source-analysis, and
  Director cycles were due around 08:20, 08:31, 08:40, and 08:45 UTC. No
  service, campaign, or running research job was restarted or changed for
  this checkpoint.

- **Latest runtime/resource snapshot:** 2026-10-16T06:47:38Z
- **Latest source summary:** 2026-10-16T06:41:47Z
- **Latest gap-detail summary:** 2026-10-16T06:51:25Z
- **Latest Midas/Reality API health probes:** 2026-10-16T06:47:38Z

## Runtime checkpoint — 2026-10-16T06:47:38Z

- The Reality recorder, frozen shadow, Midas and Reality APIs, and both web
  services were active. The recorder has zero restarts; the shadow retains one
  historical restart. Both health probes returned HTTP 200 / `READY` in demo
  mode with live execution disabled. The archive service remains failed after
  its 30-minute timeout at 04:33:35 UTC, with zero restarts.
- Observer scan 54 (`scan-20261016T063125Z-a83f9f475d62`) completed at
  06:31:25 UTC with 35/40 quality-valid pairs and zero positive top-gross
  pairs. The fixed pilot is 23/48 scans, 750/920 valid slots across 562
  distinct markets, with one skipped sequence. Its rotating/control
  comparison remains descriptive and nonrandomized.
- The 06:45:08 UTC Director cycle exited 0 and reconciled scan 53. It admitted
  scan 54. Arena child `job-f8035f4c4d534e7082246684` completed 54/54 events
  with exit 0 in 3.91 seconds; all five gates are zero and candidate
  evidence/replay are complete and empty. The Director manifest still
  projects the child as `QUEUED` until the scheduled 07:15:14 UTC cycle. No
  manual poll or retry occurred.
- The 06:40 UTC finalized-source analysis exited 0 with zero restarts. Its
  sealed prefix covers 5,498/5,498 segments / 1,416,952,599 bytes and 375,120
  quality-valid states across 95 markets. Positive top-ask, full-depth, and
  minimum-notional states remain zero. It read no active segment; readiness
  remains `collecting_frozen_campaign_window`.
- The 06:35 UTC gap-detail batch exited 0 with zero restarts. Its finalized-only
  prefix covers 3,641/5,488 replayable catalog segments / 905,966,969 bytes,
  leaving 1,847 segments / 508,817,892 bytes pending. It indexes 1,032
  campaign-window gap events and read no active segment.
- Load averages were 1.18 / 0.97 / 0.97. Available RAM was 9.7 GiB of 15 GiB;
  swap use was 3.8/4 GiB. Root storage was 56% used with 197 GiB free. The
  Reality research recording directory measured 1,509,797,538 bytes and the
  observatory directory 59,343,927 bytes. Relative to the 06:18 UTC sample,
  these grew 11,274,302 and 1,246,666 bytes over about 29 minutes; this is a
  short two-point sample, not a stable growth-rate forecast.
- At capture, the observer, Director, source-analysis, and gap-detail one-shot
  services were inactive between scheduled runs. Next scheduled timers were
  gap detail 06:50 UTC, Reality capacity 06:50:53, observer 07:01:12, source
  analysis 07:10:15, and Director 07:15:14 UTC. No service, collector, pilot,
  Arena child, or frozen campaign was manually restarted or changed.

See [Gate A checkpoint 050](VERITAS_MISSION2_GATE_A_CHECKPOINT_050.md),
[Gate B checkpoint 009](VERITAS_MISSION2_GATE_B_CHECKPOINT_009.md), [Gate F
checkpoint 033](VERITAS_MISSION2_GATE_F_CHECKPOINT_033.md), [Gate G
checkpoint 017](VERITAS_MISSION2_GATE_G_CHECKPOINT_017.md), and [inventory
073](VERITAS_MISSION2_RESEARCH_INVENTORY_073.json).

## Scheduled gap-detail completion — 2026-10-16T06:51:28Z

The scheduled 06:50 UTC finalized-only batch started at 06:50:04 and exited 0
at 06:51:28 with zero restarts. It processed 122 segments / 33,462,900 bytes.
The sealed index now covers 3,763/5,518 replayable catalog segments / 939,429,869
bytes, leaving 1,755 segments / 482,445,348 bytes pending. It records 1,090
campaign-window gap events and read no active segment. The batch used 4.194 CPU
seconds, peaked at 63.6 MiB, and used no swap.

Summary file SHA-256: `1223768dea9b8b9e221bcf83bcdbca263abe0fdceba481618aa5aa6bfc75232d`;
summary SHA-256: `0e1f37bbad1578c6022dd1ef76746b4699d97d2ed0fb588696293bd955999677`.
The next scheduled observer and source-analysis runs remain 07:01:12 and
07:10:15 UTC, followed by Director reconciliation at 07:15:14 UTC. No service
or campaign was manually changed.

See [inventory 073](VERITAS_MISSION2_RESEARCH_INVENTORY_073.json) for the
post-run evidence record.

## Previous runtime checkpoint — 2026-10-16T06:18:36Z

- The Reality recorder, frozen shadow, Midas and Reality APIs, and both web
  services were active. The recorder has zero restarts; the shadow retains one
  historical restart. Both read-only API health probes returned HTTP 200 /
  `READY` in demo mode with live execution disabled. The archive service is
  still failed after its 30-minute timeout at 04:33:35 UTC, with zero
  restarts. No recovery attempt was made.
- Observer scan 53 (`scan-20261016T060051Z-340d33b97461`) completed at
  06:00:57 UTC with 30/40 quality-valid pairs and zero positive top-gross
  pairs. The fixed pilot is 22/48 scans, 715/880 valid slots across 541
  distinct markets, with one skipped sequence. Its rotating/control
  comparison remains descriptive and nonrandomized.
- The 06:15:10 UTC Director cycle exited 0 at 06:15:35 and reconciled scan 52.
  It admitted scan 53. Arena child `job-6be536ab59a143ec964f46b1` completed
  53/53 events with exit 0 in 3.91 seconds; all five gates are zero and
  candidate evidence/replay are complete and empty. The Director manifest
  still projects the completed child as `QUEUED`, with scan 52 last qualified,
  until its scheduled 06:45:08 UTC cycle. No manual poll or retry occurred.
- The 06:10 UTC finalized-source analysis exited 0 at 06:11:48 with zero
  restarts. Its sealed prefix covers 5,439/5,439 segments / 1,404,163,458
  bytes and 372,088 quality-valid states across 95 markets. Positive top-ask,
  full-depth, and minimum-notional states remain zero. It read no active
  segment; readiness remains `collecting_frozen_campaign_window`.
- The 06:05 UTC gap-detail batch exited 0 at 06:06:21 with zero restarts. Its
  finalized-only prefix covers 3,388/5,431 catalog segments / 842,162,936
  bytes, leaving 2,041 segments / 559,812,218 bytes pending. It indexes 912
  campaign-window gap events and read no active segment.
- The Reality archive unit remains the known operational failure. The system
  user-unit list also contains historical failed research and test units; the
  system-level Daymark database unit is failed and unrelated to the Veritas
  collector and APIs.
- Load averages were 1.18 / 0.94 / 0.98. Available RAM was 9.7 GiB of 15 GiB;
  swap use was 3.7/4 GiB. Root storage was 56% used with 197 GiB free. The
  Reality research recording directory measured 1,498,523,236 bytes and the
  observatory directory 58,097,261 bytes. Relative to the 05:47 UTC sample,
  these grew 12,055,540 and 1,183,078 bytes over about 31 minutes; this is a
  short two-point sample, not a stable growth-rate forecast.
- At capture, the observer, Director, source-analysis, and gap-detail one-shot
  services were inactive between scheduled runs. No model-training process
  appeared in the sampled top CPU process list. Next scheduled timers were
  gap detail 06:20 UTC, Reality capacity 06:20:48, observer 06:31:12, source
  analysis 06:40, and Director 06:45:08 UTC. No service, collector, pilot,
  Arena child, or frozen campaign was manually restarted or changed.

See [Gate A checkpoint 049](VERITAS_MISSION2_GATE_A_CHECKPOINT_049.md),
[Gate B checkpoint 008](VERITAS_MISSION2_GATE_B_CHECKPOINT_008.md), [Gate G
checkpoint 016](VERITAS_MISSION2_GATE_G_CHECKPOINT_016.md), and [inventory
071](VERITAS_MISSION2_RESEARCH_INVENTORY_071.json).

## Scheduled gap-detail completion — 2026-10-16T06:21:25Z

The scheduled 06:20 UTC finalized-only batch exited 0 at 06:21:25 with zero
restarts. It processed 128 segments / 30,416,223 bytes. The sealed index now
covers 3,516/5,459 replayable catalog segments / 872,579,159 bytes, leaving
1,943 segments / 535,462,034 bytes pending. It records 973 campaign-window
gap events and did not read an active segment. The previously completed
06:18 runtime snapshot above is unchanged; this is a later sealed analysis
result. The next bounded batch remains scheduled by the existing timer.

**Previous runtime/resource snapshot:** 2026-10-16T05:22:16Z
**Previous source summary:** 2026-10-16T05:12:45+00:00
**Previous gap-detail summary:** 2026-10-16T05:21:20+00:00
**Previous Midas/Reality API health probes:** 2026-10-16T05:22:16Z

## Previous runtime checkpoint — 2026-10-16T05:22:16Z

- The Reality recorder and frozen shadow are active with zero and one
  historical restarts. Midas and Reality APIs are active; both local health
  probes returned HTTP 200 / `READY` in demo mode with live execution
  disabled. Shadow ordinal lag was not refreshed. Its 10% CPU ceiling remains
  in place; the prior cgroup sample showed throttling in about 97% of quota
  periods, and was not repeated here.
- Scan 51 (`scan-20261016T050020Z-5729ddc65f43`) remains the latest observer
  result: 28/40 quality-valid pairs, 299 discovery IDs, 191 eligible IDs, and
  zero positive top-gross pairs. The fixed pilot is 20/48 scans, 652/800
  valid slots across 492 IDs, with one missed sequence. Rotating selections
  yield 629/742; frozen controls yield 23/58. This comparison is descriptive
  and nonrandomized.
- The scheduled Director cycle reconciled scan 50 and admitted scan 51.
  Scan-51's Arena child completed 51/51 events with zero positives at all five
  gates and complete empty candidate evidence/replay. The manifest still
  projects the completed child as `QUEUED` until the next scheduled cycle at
  05:45:02 UTC. No manual poll or retry was used.
- The independent raw replay now covers 51 snapshots / 2,040 observations.
  It matches all 1,755 v4 quality and top-edge decisions with zero
  mismatches; all gross, depth, minimum, and fee gates remain zero. The
  reported-age sensitivity admits 379 states. This does not establish
  sequence freshness or executable liquidity.
- The 05:10:39 UTC finalized-source run exited 0 at 05:12:48, advancing the
  sealed prefix to 5,324/5,324 segments / 1,375,911,587 bytes, 361,068 valid
  states over 91 markets, and zero positive top-ask, full-depth, or
  minimum-notional states. It used 6.478 CPU seconds, peaked at 122.2 MiB,
  and read no active segment.
- The 05:20:04 UTC gap-detail batch exited 0 at 05:21:23 with zero restarts.
  Its prefix covers 3,019/5,344 replayable segments / 747,354,656 bytes,
  leaving 2,323 segments / 633,802,218 bytes pending. It contains 735
  campaign-window gap events and reports no active-segment read. The next
  batch is 05:35 UTC.
- The Reality archive service remains failed after its 30-minute timeout at
  04:33:35 UTC, with zero restarts. Archive completeness and data loss remain
  unverified.
- Load averages were 0.77 / 0.85 / 0.91. RAM available was 9.7 GiB of 15 GiB;
  swap used was 3.7/4 GiB. Root storage was 56% used with 197 GiB free. The
  Reality recordings directory measured 2,356,218,774 bytes and the
  observatory directory 55,893,662 bytes.
- No Arena, training, source-analysis, Director, or gap-detail worker was
  active at capture. The next timers are observer 05:30:53 UTC, gap detail
  05:35 UTC, source analysis 05:40:08 UTC, and Director 05:45:02 UTC. No
  service, collector, pilot, or frozen campaign was restarted or changed.

See [Gate B checkpoint 006](VERITAS_MISSION2_GATE_B_CHECKPOINT_006.md),
[Gate C checkpoint 017](VERITAS_MISSION2_GATE_C_CHECKPOINT_017.md),
[Gate F checkpoint 032](VERITAS_MISSION2_GATE_F_CHECKPOINT_032.md), and
[inventory 068](VERITAS_MISSION2_RESEARCH_INVENTORY_068.json).

## Runtime checkpoint — 2026-10-16T05:17:20Z

- The Reality recorder and frozen shadow are active with zero and one
  historical systemd restarts. Midas and Reality APIs are active; both
  `/api/health` probes returned HTTP 200 / `READY` in demo mode with live
  execution disabled. Shadow ordinal lag was not refreshed. Its configured
  CPU ceiling remains 10%; a prior cgroup sample showed throttling in about
  97% of quota periods. That resource limit may contribute to catch-up lag and
  was left unchanged.
- Observer scan 51 (`scan-20261016T050020Z-5729ddc65f43`) completed at
  05:00:26 UTC with 28/40 quality-valid pairs, 299 discovery IDs, 191 eligible
  IDs, and zero positive top-gross pairs. The fixed pilot is 20/48 scans,
  652/800 valid slots across 492 IDs, with one skipped sequence. Rotating
  selections yield 629/742; frozen controls yield 23/58. This comparison is
  descriptive and nonrandomized; the pilot's fixed stop is 19:00:55 UTC.
- The 05:15:04 UTC Director cycle exited 0 at 05:15:35 and reconciled scan 50
  as last qualified. It admitted scan 51's child, which completed 51/51 events
  at 05:15:47 with exit 0, no candidate at any of five economic gates, and
  complete empty candidate evidence/replay. The manifest still projects that
  child as `QUEUED`; next scheduled reconciliation is 05:45:02 UTC. No manual
  poll or retry occurred.
- The 05:10:39 UTC source-analysis run exited 0 at 05:12:48, processing 60
  finalized segments / 17,149,551 bytes. The sealed prefix covers
  5,324/5,324 segments / 1,375,911,587 bytes, with 361,068 valid states over
  91 markets and zero positive top-ask, full-depth, or minimum-notional
  states. It used 6.478 CPU seconds, peaked at 122.2 MiB, and read no active
  segment. Campaign-window readiness remains collecting.
- The 05:05:04 UTC gap-detail run exited 0 at 05:06:25 with no restarts. Its
  prefix covers 2,907/5,315 replayable segments / 714,067,245 bytes, with
  2,406 segments / 658,840,424 bytes pending and 680 campaign-window gap
  events. It read no active segment. The next gap batch is 05:20 UTC.
- The Reality archive unit remains failed after its 30-minute timeout at
  04:33:35 UTC, with zero restarts. Archive completeness and data loss remain
  unverified; no source loss was established.
- Load averages were 0.82 / 1.01 / 0.97. RAM available was 9.7 GiB of 15 GiB;
  swap used was 3.6/4 GiB. Root storage was 56% used with 197 GiB free. The
  Reality recordings directory measured 2,352,868,550 bytes and the
  observatory directory 55,685,075 bytes. These single-point sizes do not
  establish a long-term growth rate.
- No Arena, training, source-analysis, Director, or gap-detail process was
  active at capture. The next scheduled timers are observer 05:30:53 UTC,
  source analysis 05:40:08 UTC, and Director 05:45:02 UTC. No collector,
  service, pilot, or frozen campaign was restarted or changed.

See [Gate C checkpoint 017](VERITAS_MISSION2_GATE_C_CHECKPOINT_017.md),
[Gate F checkpoint 032](VERITAS_MISSION2_GATE_F_CHECKPOINT_032.md), and
[research inventory 067](VERITAS_MISSION2_RESEARCH_INVENTORY_067.json).

## Runtime checkpoint — 2026-10-16T05:06:29Z

- The Reality recorder and frozen shadow are active with zero and one
  historical systemd restarts. Midas API and Reality API are active; both
  `/api/health` probes returned `READY` in demo mode with live execution
  disabled. The shadow ordinal lag was not refreshed during this checkpoint.
  Its configured CPU ceiling remains 10%; a prior cgroup sample showed
  throttling in about 97% of quota periods. That resource constraint may
  explain slow shadow catch-up and was left unchanged.
- Observer scan 51 (`scan-20261016T050020Z-5729ddc65f43`) exited 0 at
  05:00:26 UTC with 28/40 quality-valid pairs, 299 discovery IDs, 191 eligible
  IDs, and zero positive top-gross pairs. The fixed pilot is 20/48 scans,
  652/800 valid slots across 492 IDs, with one skipped sequence. Rotating
  selections yield 629/742; frozen controls yield 23/58. This comparison is
  descriptive and nonrandomized; the pilot's fixed stop is 19:00:55 UTC.
- The Director's 04:45:07 UTC cycle exited 0 at 04:45:39. Its scan-50 Arena
  child completed with all economic gates at zero and complete empty
  candidate evidence/replay, while the manifest still projects `QUEUED` and
  records scan 49 as last qualified. The next reconciliation is scheduled for
  05:15:03 UTC.
- The 04:40:23 UTC finalized-source analysis exited 0 at 04:42:06. Its sealed
  prefix remains 5,264/5,264 segments / 1,358,762,036 bytes, with 354,898
  quality-valid states across 87 markets and zero positive top-ask,
  full-depth, or minimum-notional states. The next run is scheduled for
  05:10:39 UTC.
- The 05:05:04 UTC gap-detail batch completed at 05:06:25 UTC with exit 0 and
  zero restarts. Its sealed prefix advanced to 2,907/5,315 replayable
  segments / 714,067,245 bytes, leaving 2,406 segments / 658,840,424 bytes
  pending. The prefix contains 680 campaign-window gap events and reports no
  active-segment reads. The next batch is scheduled for 05:20 UTC.
- The Reality archive unit remains failed after its 30-minute timeout at
  04:33:35 UTC, with zero restarts. This is an archival delay risk; no evidence
  of source loss was established. Its next timer is the following day.
- Load averages were 1.16 / 0.99 / 0.95; RAM available was 9.5 GiB of 15 GiB;
  swap used was 3.6/4 GiB. Root storage was 56% used with 197 GiB free. The
  Reality recordings directory measured 2,347,476,230 bytes and the
  observatory directory 55,597,327 bytes. No sustained growth rate was
  estimated from this single sample.
- No Arena, training, or Veritas analysis worker was active at the capture
  instant; the gap-detail batch had completed. The source-analysis, Director,
  and observer one-shots were idle between timers. No service, collector,
  frozen campaign, or pilot was restarted or changed for this checkpoint.

The local health probes were read-only. The active gap-detail process is left
running. See [research inventory 066](VERITAS_MISSION2_RESEARCH_INVENTORY_066.json)
and [Gate B checkpoint 005](VERITAS_MISSION2_GATE_B_CHECKPOINT_005.md).

## Scheduled source-analysis completion — 2026-10-16T04:42:06Z

The 04:40:23 UTC finalized-source recurrence completed at 04:42:06 UTC with
exit 0 and zero restarts. It processed 58 finalized segments / 12,634,833
bytes, using 5.178 CPU seconds and 120.6 MiB peak memory. The sealed prefix
now covers 5,264/5,264 cataloged segments / 1,358,762,036 bytes, with no
pending segments or bytes. It reports 354,898 quality-valid states across 87
markets and zero positive top-ask, full-depth, or minimum-notional states. No
active segment was read. See [Gate C checkpoint
016](VERITAS_MISSION2_GATE_C_CHECKPOINT_016.md).

## Latest runtime checkpoint — 2026-10-16T04:39:57Z

- The Reality recorder and frozen shadow remain active with zero and one
  historical systemd restarts respectively. Current resident memory is about
  402 MB for the recorder and 301 MB for the shadow. Midas and Reality APIs
  are active; both `/api/health` probes returned HTTP 200 READY in demo mode
  with live execution disabled.
- Scan 50 (`scan-20261016T043140Z-6dbd91418e78`) completed at 04:31:47 UTC
  with exit 0 and zero restarts. Its 50-scan panel has 2,000 observations,
  1,727 quality-valid pairs, and zero positive candidates. The fixed pilot is
  running at 19/48 scans, 624/760 valid slots across 467 IDs, with one skipped
  sequence; its fixed stop is 19:00:55 UTC.
- The 04:35 gap-detail run completed at 04:36:22 UTC with exit 0 and zero
  restarts. It processed 116 finalized segments / 33,217,726 bytes, used
  3.993 CPU seconds. Its prefix covers
  2,661/5,253 replayable segments, with 2,592 / 709,420,880 bytes pending.
  It contains 558 campaign-window gap events across 25 markets, one event
  without reported assets, zero unmapped affected assets, and no active
  segment reads.
- The finalized-source analyzer completed its scheduled 04:40 run at 04:42:06
  UTC; its updated prefix and zero-positive result are recorded above.
- The Director's last cycle completed at 04:15:37 UTC. Its scan-49 Arena child
  is complete, but the manifest still projects `QUEUED` with scan 48 as last
  qualified. The next scheduled reconciliation is 04:45:07 UTC.
- The verified incremental archive service failed its 04:03:35–04:33:35 UTC
  run with a 30-minute startup timeout and SIGTERM; it had zero restarts. This
  leaves an archival delay risk. No recorder or campaign service was
  restarted.
- Load averages were 0.87 / 1.10 / 1.13. RAM use was 5.9/15 GiB with 9.6 GiB
  available; swap use was 3.6/4 GiB. Root disk was 56% full with about 197
  GiB free. The recording root measured 1,360,287,941 bytes and the
  observatory directory 54,301,467 bytes.
- The next scheduled gap batch is 04:50 UTC, observer 05:00:07 UTC, and
  Director 04:45:07 UTC. The API and coverage tests passed 28 cases; Ruff,
  formatting, and strict Mypy passed. No full regression was run.

## Previous runtime checkpoint — 2026-10-16T04:27:21Z

## Runtime checkpoint — 2026-10-16T04:27:21Z

- The Reality recorder and frozen shadow were active. The recorder had zero
  restarts and about 401 MB resident memory; the shadow had one historical
  restart and about 301 MB. Midas API, Reality API, and the Reality and Midas
  web services were active. Both `/api/health` probes returned HTTP 200; the
  API mode remains demo with live execution disabled.
- Scan 49 remains the latest completed observer scan (exit 0, zero restarts at
  04:00:37 UTC); the next observer timer is 04:31:28 UTC. The fixed pilot is
  18/48 scans, with 588/720 valid slots across 434 IDs and one missed
  sequence; its fixed stop remains 19:00:55 UTC.
- The 04:15:06 UTC Director cycle completed at 04:15:37 with exit 0 and no
  restarts. Its scan-49 Arena child completed 49/49 events, but the manifest
  still projects `QUEUED` and scan 48 as last qualified. The next scheduled
  reconciliation is 04:45:07 UTC; no manual poll or retry was made.
- Finalized-source analysis remains current at 5,206/5,206 segments and
  1,346,127,203 bytes, with 351,524 quality-valid states across 87 markets
  and zero positive top-ask/full-depth states. It read no active segment.
- The scheduled 04:20 gap-detail batch exited 0 at 04:21:18 with zero
  restarts. It processed 128 segments / 33,042,875 bytes, used 3.939 CPU
  seconds, and peaked at 62.5 MiB. Its prefix now covers 2,545/5,224
  replayable segments, leaving 2,679 / 736,206,152 bytes pending. It records
  500 campaign-window resynchronization events over 20 markets; it read no
  active segment. The next batch is scheduled for 04:35 UTC.
- The H109 attribution refresh scanned 40,075 censored outcomes, verified 339
  gap-related rows and 157 exact source records across 133 finalized
  segments / 58,443,329 bytes. It reports 63 same-market temporal links, 100
  exact gap references indexed, 79 exact references not yet indexed, and 25
  terminations beyond the current prefix. The frozen journal was opened
  read-only; its hash chain and full SQLite integrity were not reverified.
- Load was 1.09 / 1.16 / 1.09 across six CPUs. RAM was 5.9/15 GiB used with
  9.6 GiB available; swap was 3.6/4 GiB. Root storage was 56% used with
  about 198 GiB free. Recording-root size was 1,355,105,081 bytes, up about
  45.7 MB since the 02:59 UTC sample (roughly 31 MB/hour over that interval).
- The last measured shadow lag remains 165,712 ordinals under its 100 ms/s
  CPU quota; this figure is stale and was not refreshed.

Systemd still lists historical failed Arena/Reality units and an unrelated
Daymark database failure. No current collector or Veritas scheduled service
failure was observed. The next bounded timers are observer 04:31:28, gap
detail 04:35, source analysis 04:40:23, and Director 04:45:07 UTC. No service,
campaign, pilot, or recurring timer was restarted or retried. A bounded
read-only censor-attribution command ran against the sealed gap prefix and a
query-only SQLite snapshot; it did not interact with service writers. Status
checks and read-only API health probes were performed. No authenticated
request or order was used.

## Previous runtime checkpoint — 2026-10-16T04:18:16Z

### Archived snapshot — 2026-10-16T04:18:16Z

- Reality recorder and frozen shadow are active; the recorder has zero restarts and the shadow has one historical restart. Sampled memory is about 402 MB and 299 MB. Midas API, Reality API and both web services are active.
- Both API health probes returned HTTP 200 READY in demo mode with live execution disabled. Caddy, Contact/status, Blueprint, and Echo Archives production/staging units were active.
- Observer scan 49 completed at 04:00:37 UTC with exit 0 and zero restarts. The next observer timer is 04:31:28 UTC.
- The 04:15:06 UTC Director cycle exited successfully at 04:15:37 UTC with zero restarts. It admitted scan 49. The Arena child completed 49/49 events, but the Director manifest still projects QUEUED; its next timer at 04:45:07 UTC is the scheduled reconciliation point. The manifest records scan 48 as the last qualified scan.
- The fixed pilot remains at 18/48 scans, 588/720 valid slots across 434 IDs, and one missed sequence; its fixed stop is 19:00:55 UTC.
- The scheduled source analyzer finished at 04:13:29 UTC with exit 0, zero restarts, 8.398 CPU seconds, 120.4 MiB peak memory, and no swap. The finalized prefix is current at 5,206/5,206 segments / 1,346,127,203 bytes, with no pending segments or bytes. It reports 351,524 valid states across 87 markets and zero positive top-ask/full-depth states. It read no active segment.
- The latest gap-detail index is from 04:06:13 UTC and remains partial at 2,417/5,194 replayable segments, with 435 campaign-window resynchronization events across 15 markets and 2,777 segments / 762,500,134 bytes pending. Its next timer is 04:20:00 UTC.
- Host load was 0.77 / 0.97 / 1.05 across six CPUs; RAM was 6.0/15 GiB with 9.6 GiB available; swap was 3.6/4 GiB; root storage was 56% used with about 198 GiB free. The Reality recording-root size was last measured at 02:59 UTC, so growth has not been refreshed here.
- The last quantified shadow lag remains 165,712 ordinals behind under its 100 ms/s quota; this figure is stale and was not refreshed.

Systemd retains historical failed units: the earlier scan-1 Arena source-revision race and unrelated old Reality verification/canary jobs; the system manager also has the unrelated Daymark DB failure. No failed unit was cleared or restarted.

No manual Director poll/retry, worker start, service restart, deployment, collector/campaign/pilot mutation, authenticated request, or order submission was made. The next bounded timers are gap detail 04:20, observer 04:31:28, source analysis 04:40:23, and Director 04:45:07 UTC.

## Engineering update — 2026-10-16 03:29 UTC

Gate G checkpoint 012 added read-only API validation and dashboard projection
for the frozen gap-censor attribution. This was a source and test change only;
no runtime or host-resource probe was performed, and no service, collector,
campaign, scheduled job, or coverage pilot was restarted or altered. The
runtime state below remains the last recorded operational snapshot, not a
claim about current service health. See [Gate G checkpoint
012](VERITAS_MISSION2_GATE_G_CHECKPOINT_012.md) and [inventory
059](VERITAS_MISSION2_RESEARCH_INVENTORY_059.json).

## Scheduled Veritas state — 2026-10-16 03:31 UTC

The gap-detail service completed its 03:20:04–03:21:20 UTC run with exit
status 0 and zero restarts. Its validated summary covers 2,037/5,108 cataloged
segments, with 3,069 segments / 836,081,401 bytes pending and 251 campaign-
window `book_resynchronization` gaps across 11 affected markets. All reported
affected assets are mapped. The primary source analyzer completed its 03:11:02–
03:14:55 UTC run with exit 0 and zero restarts; its summary remains at
4,997/5,089 segments, with 92 segments / 23,048,067 bytes pending and 331,241
quality-valid campaign-window states over 77 markets. The source summary
reports zero positive gross states at its tracked gates; the gap-detail
summary describes source continuity and gap events.

The Director's 03:15:03–03:15:35 UTC one-shot completed successfully with zero
restarts. Its next scheduled cycle is at 03:45:19 UTC. At 03:31:44 UTC the
observer service had just entered `activating`; its current scan output was not
read. The sampled next timer starts were gap detail at 03:35, source analysis
at 03:40:40, and Director at 03:45:19 UTC. No job was manually triggered,
polled, or retried.

This was a limited systemd and sealed-summary check. Host load, RAM, disk,
Reality recorder/shadow state, and Midas/Reality API or web health were not
sampled; the earlier full host/service snapshot below remains the last such
check. No services, campaign, or fixed pilot were changed.

## Scheduled gap-detail and browser verification — 2026-10-16 03:37 UTC

The 03:35 gap-detail one-shot completed at 03:36:20 UTC with exit status 0
and zero restarts. Its sealed summary advanced the index to 2,161/5,137
cataloged segments, with 2,974 segments / 810,593,712 bytes pending and 311
campaign-window gap events across 11 markets. The summary digest and progress
counters passed the read-only dashboard validator. The prefix remains
incomplete; no active segment was read.

The focused Veritas browser workflow also passed 1 test. Playwright used a
temporary database and isolated API/Vite test servers on ports 18000 and 15173;
the ports were free after the run. No hosted service was restarted or reused.
The next timer starts observed are source analysis 03:40:40, Director 03:45:19,
gap detail 03:50:00, and observer 04:00:18 UTC. Host load, RAM, disk, and
Reality/Midas health remain unrefreshed since the 02:59 full snapshot.

## Latest runtime state — 2026-10-16 02:59 UTC

- Reality recorder and shadow are active under systemd with `Result=success`;
  the recorder has zero restarts and uses about 400 MB, while the shadow has
  one historical restart and uses about 289 MB. The Midas API, Reality API,
  Reality web, and Midas web services are active. No new HTTP health probe was
  made for this check, so these are service-state observations.
- The Veritas observer, source analyzer, gap-detail analyzer, and Director
  one-shots are inactive between timer invocations after successful exits.
  Their timers remain active. The next scheduled UTC starts observed were
  observer 03:01:49, source analysis 03:10:56, Director 03:15, and gap detail
  03:05.
- The latest finalized public panel is scan 46 at 02:30:17 UTC: 33/40 pairs
  passed the quality gate. Its six-query union had 300 unique IDs, 178
  currently eligible pairs, and 122 exclusions. Across 46 scans the v4 panel
  has 1,600/1,840 quality-valid observations over 820 selected IDs and zero
  candidate events. The 24-hour pilot has 15/48 scans, 497/600 valid slots,
  367 distinct selected IDs, and one skipped scan sequence after a scan-45
  code-hash mismatch. Its fixed stop remains 19:00:55 UTC.
- The independent source audit covered all 46 saved snapshots / 1,840
  observations, reproduced all 1,600 v4 validity and edge results with zero
  mismatches, and found no positive gross, depth, minimum, or fee-sensitive
  candidates. Only 349 pairs pass the conservative reported-age/skew filter;
  reported timestamp age is not sequence evidence.
- The offline A1 refresh verified all snapshot, Gamma, and CLOB hashes across
  those 46 scans. The bounded six-frame query union now contains 5,784
  distinct Gamma IDs, 2,115 IDs eligible at least once, and 820 selected IDs;
  the prior 40-scan report had 5,319 / 2,077 / 741. One legacy capture versus
  current-replay validity-counter mismatch remains on scan 1 (5 versus 32).
  The refresh read saved files only and made no public HTTP calls. See [Gate A
  checkpoint 044](VERITAS_MISSION2_GATE_A_CHECKPOINT_044.md).
- The finalized-source analyzer summary at 02:44:41 UTC covers 4,869/5,029
  segments and 318,568 quality-valid states across 77 markets; 160 segments /
  39,330,180 bytes remain pending. The 02:50 gap-detail run processed 115
  finalized segments / 33,465,203 bytes, used 3.656 CPU seconds, and exited 0
  at 02:51:13 UTC with zero restarts. Its latest summary covers 1,791/5,049
  segments / 416,842,757 processed bytes, with 3,256 / 888,351,418 bytes
  pending. It reports 131 campaign-window `book_resynchronization` events
  affecting seven markets, with no missing or unmapped affected assets. The
  prefix is not complete, and the active `.open` segment was not read.
- The 02:45 Director admitted scan 46. Its Arena child completed 46/46 events
  with exit 0 and passed the read-only finding validator. The Director
  manifest still projects the child as `QUEUED` until its next scheduled
  reconciliation at 03:15 UTC. No manual poll or retry was made.
- Host load was 1.15 / 1.02 / 1.07, available RAM 9.6 GiB, swap use 3.5 GiB,
  and root disk 56% used with about 198 GiB available. The configured Reality
  recording root is 1,309,431,325 bytes. Compared with the 01:18 UTC status
  value of 1,261,164,701 bytes, that is a sampled increase of about 48 MB over
  97 minutes (roughly 30 MB/hour if sustained). A previous `du` command
  measured the parent `data/recordings` tree at 1.88 GB; that is not the
  recorder's configured root and is not used for this growth estimate. Midas
  API current RSS was about 1.55 GB (4.44 GB historical peak). There is no
  immediate capacity failure; swap use, API peak, and recording growth merit
  monitoring.
- Historical faults remain visible: the shadow's one restart followed a
  finalized-source integrity/continuity mismatch on 2026-10-15; the collector
  has logged a WebSocket `ConnectionClosedError` and remains unsequenced. One
  older Veritas Arena job for the 2026-10-15 11:01 scan failed because its
  source changed while queued. The current recorder and shadow are running,
  and the scan-46 Arena job completed and validated successfully.
- No observer, recorder, shadow, source-analysis, Director, or gap-detail
  service was restarted or interrupted. No pilot or frozen campaign files
  were changed, and no orders or authenticated requests were used.

See [Gate A checkpoint 043](VERITAS_MISSION2_GATE_A_CHECKPOINT_043.md),
[Gate B checkpoint 001](VERITAS_MISSION2_GATE_B_CHECKPOINT_001.md), [Gate C
checkpoint 011](VERITAS_MISSION2_GATE_C_CHECKPOINT_011.md), [Gate F
checkpoint 028](VERITAS_MISSION2_GATE_F_CHECKPOINT_028.md), and [inventory
057](VERITAS_MISSION2_RESEARCH_INVENTORY_057.json).

## Subsequent scheduled research artifacts — 2026-10-16 03:10 UTC

- The scheduled observer finalized scan 47 at 03:02:03 UTC. It selected 40
  markets, with 28 quality-valid pairs from a 293-ID bounded union: 116 met
  the current eligibility rule and 177 were excluded. All recorded gross,
  depth, minimum, and fee gates were zero. The v4 panel has 47 snapshots,
  1,628/1,880 valid observations, 835 selected IDs, and zero candidate events.
- The unchanged 24-hour coverage pilot now has 16/48 scans, 525/640 valid
  slots, and 388 distinct selected IDs. It retains one skipped sequence after
  the scan-45 code-hash mismatch and ends at 19:00:55 UTC. Its rotating and
  frozen-control comparison remains descriptive.
- The scheduled 03:05 gap-detail batch completed at 03:06:14 UTC, processing
  128 finalized segments / 32,886,676 bytes. Its prefix is 1,919/5,079
  segments / 449,729,433 processed bytes, with 3,158 / 862,240,407 bytes
  pending and 194 campaign-window resynchronization events across ten
  markets. The index remains incomplete; no active `.open` segment was read.
- A read-only attribution pass verified all 1,919 sealed gap-event files and
  scanned all 40,075 censored outcomes. It found 45 candidate prior
  same-market gap links among 160 `book_issue:gap` rows; 29 had no matching
  gap within the processed prefix, and 86 reference events beyond it. Of 179
  explicit gap censors, 38 map into the index and 141 point beyond its prefix.
  Most indirect candidate intervals exceed five minutes, so none is treated
  as causal. See [Gate C checkpoint
  011](VERITAS_MISSION2_GATE_C_CHECKPOINT_011.md) and the [row-level
  artifact](VERITAS_MISSION2_CENSOR_GAP_ATTRIBUTION_001.json).

The service-state and host-resource figures above remain the 02:59 read-only
snapshot. No newer service probe, manual research-job poll, retry, or restart
was made for these artifact updates.

## Subsequent scheduled research artifacts — 2026-10-16 03:19 UTC

- The 03:15 Director cycle reconciled the scan-46 child and admitted scan 47.
  Arena job `job-d5fda223640d4a94893cdf35` completed all 47/47 source events
  with exit status 0 at 03:15:46 UTC. Its finding reports 1,880 observations,
  1,628 valid pairs across 835 IDs, zero positives at all five economic gates,
  and complete empty candidate evidence/replay. The Director manifest was
  updated at 03:15:28 and still projects `RUNNING` / `QUEUED`, retaining scan
  46 as last qualified. The 03:45:19 UTC scheduled cycle is the next
  reconciliation point. Only persisted job, source-manifest, finding, and
  Director files were read; no job API poll or retry was made.
- An offline independent source replay completed at 03:17:32 UTC over all 47
  snapshots and 30,697,840 compressed bytes. It matched all 1,628 v4-valid
  decisions and top edges with zero mismatches. It found no positive gross,
  depth, minimum, or fee-sensitive states. A conservative timestamp filter
  admitted 353 states; 1,275 had at least one reported age above five seconds.
  See [Gate B checkpoint 002](VERITAS_MISSION2_GATE_B_CHECKPOINT_002.md).
- The source summary pinned by the Director was generated at 03:14:52 UTC; it
  covers 4,997/5,089 finalized segments / 1,292,353,290 bytes, with 92 /
  23,048,067 bytes pending. It reports 331,241 quality-valid states and zero
  positive top-ask or full-depth states. Its readiness remains
  `catching_up_finalized_source`.
- A read-only user-timer listing at 03:18:52 UTC showed the next starts at
  03:20 gap detail, 03:31:32 observer, 03:40:40 source analysis, and 03:45:19
  Director. No service-health probe or host-resource sample was taken; the
  latest such figures remain from 02:59 UTC. No service or timer was restarted.

See [Gate F checkpoint 029](VERITAS_MISSION2_GATE_F_CHECKPOINT_029.md), [Gate B
checkpoint 002](VERITAS_MISSION2_GATE_B_CHECKPOINT_002.md), and [inventory
058](VERITAS_MISSION2_RESEARCH_INVENTORY_058.json).

## Previous runtime state — 2026-10-16 01:36 UTC

- The observer completed scan 44 at 01:30:14 UTC with 35/40 quality-valid
  pairs. Its six-page bounded union contained 300 IDs, 204 currently eligible
  pairs, and zero positive top-gross pairs. The v4 panel has 44 scans, 1,534
  valid of 1,760 selected states across 798 selected IDs, and zero candidate
  events. The fixed measurement pilot has 14/48 scans, 464/560 valid slots,
  348 distinct selected IDs, and no skipped scan sequences. It remains
  nonrandomized/descriptive and ends at 19:00:55 UTC.
- The gap-detail timer now runs every 15 minutes at :05, :20, :35, and :50
  UTC. At 01:35 it started the first added off-cycle batch. That one-shot
  exited 0 at 01:36:13 UTC after processing 116 finalized segments /
  33,071,280 bytes. It used 3.674 CPU seconds and 52.2 MiB peak memory, with
  no memory swap peak; its existing 5% CPU, 256-MiB memory, nice 19, and idle
  I/O limits are unchanged. It did not read an active `.open` segment.
- The gap-detail prefix is 1,188/4,901 replayable segments and 257,304,555
  processed bytes; 3,711 segments / 1,011,014,530 bytes remain pending. It
  records 1,911 all-period events. The processed prefix remains pre-campaign,
  so zero campaign-window events is incomplete. The timer is active and next
  due at 01:50 UTC; the one-shot is inactive after success with zero restarts.
- The timer source under `deploy/systemd/user` matches the installed user
  unit. Only `midas-veritas-gap-detail-analysis.timer` was restarted to apply
  the schedule; the analyzer service, Reality recorder/shadow, observer,
  source-analysis, Research Director, APIs, and frozen campaign were not
  restarted or interrupted.
- The local service-unit snapshot reports the Midas/Reality APIs and web
  services plus the Reality recorder and shadow active. At 01:37:51 UTC the
  recorder status briefly read `DEGRADED_BOOKS` with
  `ConnectionClosedError: no close frame received or sent`; the next read one
  second later showed `RECORDING_UNSEQUENCED`, ordinal 681,318, and 16 fresh
  books. The service has zero restarts, but `sequence_verified=false`; the
  error and transient degraded state remain operational cautions.
- This checkpoint did not run a manual research job, HTTP probe, model
  training, full regression, or campaign modification. See [Gate C
  checkpoint 007](VERITAS_MISSION2_GATE_C_CHECKPOINT_007.md).

## Previous runtime state — 2026-10-16 00:12 UTC

- The latest observer scan is 41 (`scan-20261016T000215Z-e6ff8b97e045`),
  captured at 00:02:15 UTC. It has 33/40 request/receipt-quality-valid pairs
  and zero positive top-gross or fee/depth-gated states. Its scan-pinned
  Arena qualification is waiting for the 00:15:04 UTC Director cycle; scan
  40's child completed successfully but its manifest projection is still
  pending. No manual poll or retry was made.
- The unchanged measurement pilot has 11/48 scans, 368/440 valid selected
  pairs across 282 IDs, and zero skipped scan sequences. Its fixed stop
  remains 2026-10-16 19:00:55 UTC.
- The scheduled source-analysis batch started at 00:10:44 UTC and was still
  activating at this check. Its last completed summary, at 23:44 UTC, covers
  4,121/4,673 segments; 552 segments / 140,809,972 bytes remain pending. It
  reports 259,253 campaign-window quality-valid states across 65 markets and
  zero positive gross or minimum-notional states. I did not inspect its
  in-progress outputs; the bounded run is left alone.
- The gap-detail analyzer last completed at 23:51 UTC and covers 786/4,694
  segments, with 3,906 / 1,089,814,211 bytes pending and 1,699 all-period
  gap records. Its campaign-window count is still incomplete and must not be
  read as evidence of no gaps. Its next timer is 00:20 UTC.
- The Reality recorder and shadow, Midas and Reality API/web, Aegis,
  RoadReach, Vanguard, Continental auth/tailnet, and Veritas timers reported
  active or scheduled. The observer and gap-detail one-shots had successful
  exits; the Director remains scheduled for 00:15:04 UTC. The bounded source
  batch is the only active Veritas one-shot. The persisted Arena catalog has
  26 completed jobs, one historical failure, and no active or queued jobs.
- At 00:12 UTC, host available RAM was 10,281,988,096 bytes; swap use was
  3,725,090,816 bytes. Root disk was 56% used with 212,503,977,984 bytes
  available. The Veritas observatory directory measured 40,225,610 bytes at
  00:09:40 UTC.
- A1 remains an offline replay of the 40 saved scans through scan 40. This
  projection added no external requests and no HTTP health probe. No service,
  collector, frozen campaign, pilot, or research job was restarted or
  changed.

See [Gate A checkpoint 038](VERITAS_MISSION2_GATE_A_CHECKPOINT_038.md), the
[coverage artifact](VERITAS_MISSION2_MARKET_UNIVERSE_COVERAGE_001.json),
[Gate G checkpoint 011](VERITAS_MISSION2_GATE_G_CHECKPOINT_011.md), and
[inventory 047](VERITAS_MISSION2_RESEARCH_INVENTORY_047.json).

## Previous runtime state — 2026-10-15 23:57 UTC

The 23:57 runtime capture is preserved in [inventory
046](VERITAS_MISSION2_RESEARCH_INVENTORY_046.json). At that time scan 40 was
the latest observer result, the scan-40 Arena child had completed, and its
Director projection was queued for the next scheduled cycle. The fixed pilot
was at 10/48 scans. No runtime action was taken for that inventory update.

## Previous runtime state — 2026-10-16 00:06 UTC

This read-only check is recorded in [inventory
047](VERITAS_MISSION2_RESEARCH_INVENTORY_047.json). It preceded the current
00:10:44 source-analysis batch; the saved 23:44 prefix summary is the last
completed analysis state and is not presented as the batch's final result.

## Latest runtime state — 2026-10-15 23:34 UTC

- The observer completed scan 40 at 23:32:05 UTC. Six bounded queries
  returned 291 unique IDs, including 77 V1-eligible markets and 214 excluded
  IDs. Thirty of 40 selected pairs passed request/receipt quality; ten failed
  on an empty ask side. There were zero positive top-gross pairs and no
  candidate rows. The next scheduled observer run is at 00:01:47 UTC.
- The fixed 24-hour coverage pilot has 10/48 scans, 335/400 valid selected
  pairs, 65 invalid, and 271 distinct selected IDs, with zero skipped scan
  sequences. Its fixed stop is 2026-10-16 19:00:55 UTC. The role comparison is
  nonrandomized and descriptive.
- Arena completed the scan-39 qualification at 23:16:27 UTC with exit status
  0 and 39/39 source events. It found 1,375/1,560 quality-valid pairs over
  732 selected IDs, with zero positive states at all five gates and complete
  zero-row candidate replay. The Director manifest still reports that child
  as queued and scan 38 as the latest qualified scan. Its next scheduled
  cycle at 23:45:25 UTC is the reconciliation point. Scan 40 remains pending.
  No manual Director run, job retry, or service restart occurred.
- The finalized-source analyzer's 23:14 UTC summary covers 4,038/4,615
  segments and 247,354 quality-valid states across 63 markets; 577 segments /
  159,597,957 bytes remain pending. The gap-detail analyzer's 23:20 UTC
  summary covers 658/4,635 segments, with 3,975 / 1,101,886,466 bytes
  pending and 1,642 all-period gap events. Its campaign-window gap count is
  incomplete and is not interpretable as zero. Both analyzers declare
  `active_segment_read=false`.
- The recorder and shadow worker remain active with zero and one historical
  restarts respectively. At 23:34 UTC the recorder used about 402 MB of its
  512 MiB cap; the shadow used about 265 MB of 512 MiB. Their quotas remain
  250 ms/s and 100 ms/s. The latest detailed recorder status is still the
  23:03 UTC `RECORDING_UNSEQUENCED` snapshot, which had a temporary DNS error
  and `sequence_verified=false`; 16/16 books were flagged fresh, without
  independent continuity assurance. The prior 23:05 throughput sample found
  the shadow advancing at about 25% of recorder ordinal throughput and
  skipping all 21 sample frames under the frozen 250 ms input-age rule.
- Midas and Reality API/web units and all four Veritas timers are active.
  Host load was 0.71 / 0.81 / 0.93, available RAM 9.7 GiB, swap 3.5/4 GiB,
  and disk free 198 GiB (56% used). The Veritas observatory occupies about
  50 MB; the Reality data directory is about 3.0 GB. No HTTP health probe was
  made.
- The Research Director code adds recovery by the canonical scan admission
  key if a persisted job pointer cannot be inspected. Recovery requires a
  unique matching durable child; absent evidence leaves the scan unverified
  without retry. This behavior passed isolated tests. The current scan-39
  job record was present and completed, so no live pointer-loss incident was
  confirmed. The code change does not alter the active worker or campaign.

See [Gate A checkpoint 037](VERITAS_MISSION2_GATE_A_CHECKPOINT_037.md), [Gate
F checkpoint 023](VERITAS_MISSION2_GATE_F_CHECKPOINT_023.md), and [Director
recovery artifact 001](VERITAS_MISSION2_DIRECTOR_RECOVERY_001.json).

## Previous runtime state — 2026-10-15 23:05 UTC

- The scheduled observer completed scan 39 at 23:00:55 UTC. Six bounded
  queries returned 300 unique IDs (174 eligible same-condition pairs, 126
  excluded). The 40 selected pairs include 34 request/receipt-quality-valid
  pairs and six empty-ask invalids. Raw snapshot counts are zero at each of
  the five gross/depth/minimum/fee gates and quantities; the v3 scan-pinned
  qualification awaits the next Director cycle. The read-only pilot has nine
  scans / 360 selected slots / 305 valid / 55 invalid / 257 distinct IDs / no
  skipped sequences. Its rotating cohort is 294/331 valid and frozen controls
  11/29. The scan-39 diagnostic verifies 3/8 frozen controls selected, with
  five absent from the bounded query union. The pilot remains descriptive and
  runs to its fixed stop at 2026-10-16 19:00:55 UTC.
- The scan-38 Arena v3 job is complete, but the Director manifest still has
  `current_job_state=QUEUED` and scan 37 as `last_qualified_scan_id`; scan 39
  is not admitted. The current Director run is scheduled for 23:15:28 UTC.
  No manual poll, retry, or job was started.
- The finalized-source analyzer's 22:43:53 UTC checkpoint covers 3,953/4,554
  segments, 234,315 quality-valid campaign states across 63 markets, and has
  601 segments / 178,425,657 bytes pending. The gap-detail analyzer completed
  successfully at 22:50:48 UTC and covers 530/4,574 replayable segments, with
  4,044 / 1,096,601,919 bytes pending and 1,629 all-period gap events. Its
  campaign-window count is still incomplete and not interpretable as zero.
  Both analyzers read finalized segments only and left the active `.open`
  segment untouched.
- At 23:03:26 UTC the recorder was active in `RECORDING_UNSEQUENCED` state at
  ordinal 641,991 / 464,693 frames / 3,578 gap markers, with 8 markets and
  16/16 books flagged fresh (zero timing-uncertain books). Its status still
  carries one temporary DNS resolution failure; `sequence_verified=false`.
  The latest observation timestamp was current at capture. Recording storage
  was 1,197,411,076 bytes. The worker remained active in
  `WARMING_OR_LAGGED_SOURCE` at ordinal 476,279, with 10,253 decisions, zero
  orders, and last decision at 08:58:06 UTC. Its source receipt was
  14:40:00 UTC, about 8h25m earlier.
- A 23.1-second read-only throughput sample showed recorder +84 ordinals
  (31 frames) while the shadow cursor advanced +21 records and skipped 21
  lagged frames. The shadow cgroup used 2.006 CPU seconds under a 100 ms/s
  quota; all 201 sample periods were throttled. A digest-verified cursor and
  metadata-only segment-size sum estimated 299,424,769 unconsumed source
  bytes at 23:05 UTC. This identifies CPU quota as the proximate catch-up
  constraint in that sample. The frozen plan's 250 ms decision-input limit,
  service quota, and campaign were not changed. See [Gate C checkpoint
  005](VERITAS_MISSION2_GATE_C_CHECKPOINT_005.md) and [diagnostic
  001](VERITAS_MISSION2_SHADOW_LAG_DIAGNOSTIC_001.json).
- The Reality recorder, shadow, Midas API/web, and Reality API/web systemd
  units were active. Recorder and API/web restart counts were zero; the shadow
  retained one historical restart. Recent Veritas one-shots exited 0, and no
  systemd jobs were running at inspection. Host load was 0.53 / 1.04 / 1.09
  on six CPUs; available RAM was 9.7 GiB; swap use was 3.4/4 GiB; disk free
  was 199 GiB (56% used). No HTTP health probe was made. No service, campaign,
  pilot, or source file was restarted or modified.

## Control retrieval diagnostic — 2026-10-15 23:11 UTC

One separate public Gamma request returned all eight frozen controls. Relative
to scan 39's 23:00:55 UTC snapshot, three controls absent from its bounded
query union were open and eligible in the 23:11:44 direct response; two other
absent controls were explicitly closed. The direct response was captured about
11 minutes after scan 39, so it does not assert the exact lifecycle state at
scan time. The call made one HTTP attempt, read no books, and submitted no
orders. The pilot and its pinned code were not changed. See [Gate A checkpoint
035](VERITAS_MISSION2_GATE_A_CHECKPOINT_035.md) and [inventory
043](VERITAS_MISSION2_RESEARCH_INVENTORY_043.json).

## Discovery-frame replay — 2026-10-15 23:21 UTC

The offline frame analyzer verified 234 retained Gamma payload hashes over
39 finalized snapshots, using 25.7 MB of compressed snapshot files. The six
frames averaged 299.05 unique IDs and 164.26 V1-eligible markets. Each frame
contributed about 49–50 unique IDs exclusively; mean eligible contribution
ranged from 5.77 for the near-expiry frame to 49.95 for the tagged near-expiry
frame. A one-snapshot sensitivity found that a direct control lookup cannot
offset removal of five of the six frames. The run made no live requests and
did not touch the active observers, analyzers, pilot, or Reality campaign. The
control response was 47,860 bytes; at 48 scans per day, this would add about
2.3 MB/day of raw payload if its size remained similar. See
[Gate A checkpoint 036](VERITAS_MISSION2_GATE_A_CHECKPOINT_036.md), the
[frame-marginal artifact](VERITAS_MISSION2_DISCOVERY_FRAME_MARGINAL_001.json),
and [inventory 044](VERITAS_MISSION2_RESEARCH_INVENTORY_044.json).

## Previous runtime state — 2026-10-15 20:49 UTC

- Scan 34 completed at 20:31:54 UTC with 35/40 request/receipt-valid pairs
  and zero positive top-gross pairs. The 34-snapshot panel now has 1,202/1,360
  valid observations across 632 IDs, zero positives at all five economic
  gates, and maximum top edge -$0.001/share. The pilot has four scans / 160
  selected slots / 132 valid / 28 invalid / zero missed sequences. Its stop is
  2026-10-16 19:00:55 UTC.
- The 20:40:22 UTC source-analysis recurrence completed at 20:43:30 UTC. It
  processed 128 segments / 30,416,223 bytes in about 188 seconds, using 9.376
  CPU seconds and 133.5 MiB peak memory, with no swap. The current prefix is
  3,516/4,318 cataloged segments, with 802 / 254,804,640 bytes pending through
  ordinal 463,159. It contains 220,589 campaign-window frames, 199,121
  touched states, and 192,716 quality-valid states over 57 markets; all
  top-ask, depth, minimum, and fee candidate counts remain zero. The campaign
  window has 972 `book_resynchronization` records and one
  `connection_failure`. These are reconstruction barriers, not duration or
  complete-feed evidence. Summary digest:
  `b9d23135153f083a57e5332d167685efcafceb78afab688a1c5a3ca40e04ea17`;
  file SHA-256:
  `0fd9245a5b4ad2243d80fa047775f1521c3912701efd250152d5e28457c7898b`.
- The scheduled Director cycle at 20:45:05 UTC reconciled scan 33 and admitted
  `job-e47f6ced4e8f4900965b7179` for scan 34. Arena completed all 34 events at
  20:45:47 UTC with zero positives at each of five gates and a complete
  zero-row candidate replay. The finding is
  `veritas-qualification-v1-ef893dbea8f4dfa4`. The manifest still reports
  `QUEUED` and scan 33 as latest qualified; the scheduled 21:15 UTC cycle is
  the reconciliation point. No manual poll or retry was started. See [Gate F
  checkpoint 020](VERITAS_MISSION2_GATE_F_CHECKPOINT_020.md).
- At 20:49:08 UTC the Reality recorder and frozen shadow were active. The
  recorder has zero restarts; the shadow has one prior restart. Midas API/web
  and Reality API/web units were active with zero restarts. The three
  scheduled Veritas one-shots were idle after completion and their timers
  remained active. The Veritas Arena job archive contained 20 completed jobs
  and one preserved historical failure, with no nonterminal job. The older
  failure is the scan-11 source-drift `ValueError`; it was not retried. Host
  load was 1.45 / 1.34 / 1.32 on six logical CPUs; RAM available was 8.8 GiB;
  swap use was 3.6/4 GiB; disk free was 199 GiB (56% used); the observatory
  files totaled 32,322,459 bytes. Systemd and process state were checked, but
  no HTTP health probe was run. No service or campaign was restarted or
  altered.

## Previous runtime state — 2026-10-15 20:20 UTC

- The observer timer completed scan 33 at 20:00:54 UTC and is next due at
  20:31:39 UTC. The fixed coverage pilot has three scans / 120 selected slots
  / 97 quality-valid pairs / 23 invalid pairs / zero skipped sequences. Its
  fixed stop is 2026-10-16 19:00:55 UTC. The cumulative 33-scan panel has
  1,167/1,320 valid pairs across 616 IDs; all five economic gates remain
  zero-positive and the best top edge is -$0.001/share.
- The finalized-source timer completed at 20:14:36 UTC. It processed 128
  segments / 31,477,866 bytes in 212 seconds, using 10.618 CPU seconds and
  147.7 MiB peak memory with no swap. The current summary is
  `catching_up_finalized_source`: 3,388/4,260 segments / 842,162,936 bytes
  processed, with 872 segments / 269,424,035 bytes pending. Its campaign
  window has 212,048 frame records, 192,293 touched states, and 186,344
  quality-valid states across 47 markets; positive top-ask and full-depth
  counts remain zero. The 912 campaign-window gap markers comprise 911
  `book_resynchronization` and one `connection_failure`; the aggregate provides
  no event timestamps or outage durations. The next timer is due at 20:40:16
  UTC. Summary digest: `c32f8e0796c9c8c814e7fc5eb0538042667a908b0d90ad6b589af551d05608e4`;
  summary-file SHA-256: `f3517dc2950bb5a6436e40d5605ac4ff492ae3e4c70477e982a6be572eee351f`.
- The 20:15:44 UTC Director cycle admitted
  `job-16d651741d304fa098f87cc9` for scan 33. Arena completed all 33 events at
  20:16:26 UTC with exit status 0; finding
  `veritas-qualification-v1-010c9e464077e301` reports zero positives at all
  five economic gates and a complete zero-row candidate replay. The Director
  manifest was last updated before job completion and still projects
  `QUEUED`; the 20:45:05 UTC cycle is the reconciliation point. No manual
  poll or retry was started. See [Gate F checkpoint
  019](VERITAS_MISSION2_GATE_F_CHECKPOINT_019.md).
- At 20:02 UTC, the Reality recorder service was active with zero restarts and
  both configured market-data DNS names resolved. Its last journal warning
  remains `DEGRADED` at 04:57:26 UTC, but a read-only metadata audit found
  1,790 finalized segment files mtime-stamped at or after that warning. The
  first followed within about eight seconds, the largest adjacent mtime gap
  was 36.51 seconds, and the newest was at 20:05:04 UTC. This rules against a
  prolonged recording-output outage in the audited interval. However, the
  20:14 source summary counted 911 `book_resynchronization` markers and one
  `connection_failure` in its campaign window. The analyzer treats gap records
  as reconstruction barriers, but the aggregate does not measure outage
  duration or give event timestamps. This does not prove gap-free frames or
  upstream feed completeness. See [continuity audit
  001](VERITAS_MISSION2_RECORDER_CONTINUITY_001.json). The frozen Reality
  shadow service was observed active after one automatic restart at the prior
  19:57 check; no campaign or service was restarted or changed for this audit.
- A targeted read of the finalized segment covering the connection failure
  verified all 92 records and matched the segment SHA-256 to its catalog
  sidecar. The `connection_failure` at 04:57:26.717847 UTC matches the DNS
  warning; the first later receiver frame was at 04:57:29.162854, 2.445
  seconds later. This does not prove all eight market books recovered or were
  fresh. See [gap-timing artifact
  001](VERITAS_MISSION2_RECORDER_GAP_TIMING_001.json).
- Host memory available was 8.9 GiB; swap use was 3.5/4 GiB, a resource
  pressure indicator in the 20:16 host snapshot. The filesystem
  had 199 GiB free (56% used). Reality recordings occupied about 1.1 GiB at
  the audited count; the Veritas observatory runtime directory was about 38
  MiB at the previous size check. Midas and Reality API health endpoints and
  both local web interfaces returned HTTP 200 at 19:57 UTC; no newer health
  probe was run here.
- The frozen-campaign v1.4 audit found public markouts but no suitable
  strategy target or execution/P&L labels. The 20:16 Director manifest now
  reports `NOT_READY_NO_CANDIDATE_RELEVANT_TARGET`; this remains readiness for
  its separate snapshot dataset and does not ingest the frozen-campaign
  report. See [Gate C checkpoint
  003](VERITAS_MISSION2_GATE_C_CHECKPOINT_003.md).

The one-shot Veritas services are inactive between scheduled runs by design.
The recurring timers remain active; do not manually invoke overlapping runs.

## Historical runtime snapshot — 2026-10-15 15:16 UTC

- All three Veritas user timers are active. Scan 23 finalized at 15:00:26 UTC, the finalized-source replay exited at 15:14:31 UTC, and the Director cycle exited at 15:15:37 UTC. Arena completed its qualification at 15:15:47 UTC. The next scheduled UTC runs are 15:30:10, 15:40:45, and 15:45:00. The oneshot services are inactive between runs as expected.
- Latest scan: `scan-20261015T150026Z-56e1e44d7837`, captured at 15:00:26 UTC and finalized under v4. The analyzer has 23 processed snapshots and no pending snapshots. The cumulative panel has 920 selected observations, 825 request/receipt-valid pairs, 95 invalid pairs, 418 distinct market IDs, and 189 pairs passing the prior reported-age/skew gate. The paired increase is 636/920 (+69.13 percentage points); all five economic gates remain zero-positive.
- The latest six-frame bounded discovery union contains 300 unique IDs: 190 supported same-condition V1 binary pairs and 110 explicit exclusions (84 augmented NegRisk records and 26 unsupported outcome relationships). The selected panel has 40 markets, 36 rotating and four available frozen controls. Scan 23 overlaps scan 22 on five IDs, one rotating and four controls, so 35 rotating selections changed. Liquidity counts are 15 high / 11 medium / 14 low; expiry counts are 19 near / 14 medium / 7 long; spread counts are 21 tight / 14 medium / 5 wide.
- Runtime data uses 21,785,641 bytes under `data/veritas-observatory/`, below the 1 GiB hard cap. Snapshots and derived runtime artifacts are ignored by Git; versioned docs record identities and hashes. Do not prune or raise the cap without a separate retention review.
- The 15:00 v2 scan used seven HTTP attempts (six Gamma frames and one CLOB batch) out of a 14-attempt maximum. Thirty-six selected pairs passed the quality gate; four had empty No ask sides. The frozen control file hash remains `9578217e20dcc7d1c65fa110f0ed7c689b55483b61191f1aae8d30c9b7300d9a`.
- The finalized Reality source analyzer remains `catching_up_finalized_source`: 2,161 of 3,668 cataloged finalized segments processed, with 1,507 segments / 396,434,833 bytes pending through ordinal 269,843. The 15:10 UTC recurrence processed 124 segments / 33,163,975 bytes in 227 seconds, using 11.36 CPU seconds and 155,504,640 bytes peak memory. Its partial prefix contains 70,950 campaign-window frame records, 59,343 touched market-frame states, and 57,798 quality-valid states, with zero positive top-ask and full-depth states. Summary digest: `37715a41a176feb08db23867b5f2c7b9e39647a3f9df43a770df049c497dd6e3`; summary file SHA256: `08bd70741083b0d689c8df5d3bdf9b3fbee7683670261fea5932dbaccba6199a`. The 12:43 source-window interpretation correction is recorded in [Gate A checkpoint 017](VERITAS_MISSION2_GATE_A_CHECKPOINT_017.md).
- The 15:15 Director cycle reconciled scan 22, then admitted `job-bf0dbe4c773f4cfe9832fd8d` for scan 23 using the 15:14 source summary. Arena completed all 23 events at 15:15:47 UTC; finding `veritas-qualification-v1-a695104c7dcbb82a` reports zero positive states at all five gates. The Director manifest last updated at 15:15:32 UTC projects `QUEUED` for scan 23 and retains scan 22's finding, while its event archive records scan 22 completion and scan 23 admission. The next scheduled cycle at 15:45:00 UTC is the reconciliation point. No manual poll or retry was started. See [Gate F checkpoint 011](VERITAS_MISSION2_GATE_F_CHECKPOINT_011.md).
- At 11:30 CEST an observer run failed with `Invalid frozen control cohort` because the deployed scanner rejected the file's legacy version tag. The frozen file remained unchanged, current code accepts both tags, and scheduled scans through 17:00 CEST succeeded. No manual recovery scan was run.
- The protected Reality user services were active during the last explicit read-only check. The separate Reality worktree was clean. No Reality service was restarted or modified, and no campaign data was changed.

## Research Director history projection

The `/api/arena/research-activity` projection now includes a digest-checked
history of each displayed Director's recent events. It scans at most 128
event files per Director, reads at most 64 KiB per event, and returns up to
eight records. The API verifies each event filename against the canonical
payload digest and confirms the Director identity before projecting selected
fields. It does not alter Director manifests or events. The last read-only
projection check at 12:55 UTC returned eight verified entries from the
Director's then-19-file event archive, marked the view truncated, and reported
zero invalid artifacts. The full append-only event directory remains the durable record; the UI and API
history are bounded views. See [Gate G checkpoint
004](VERITAS_MISSION2_GATE_G_CHECKPOINT_004.md).

## Resource and network bounds

| Control | Configuration |
| --- | --- |
| Cohort size | 40 selected markets; service validates 30–50 |
| Stable controls | Target 8; unavailable frozen IDs are reported, not outcome-replaced |
| Discovery | Six Gamma query frames, at most 50 returned rows per frame; rotating 30-minute page offsets |
| Book reads | One public CLOB `/books` batch for selected pair assets |
| Request pacing | One second between public requests; seven logical reads planned, 14 HTTP attempts maximum |
| CPU | `CPUQuota=5%`, `Nice=19` |
| Memory | `MemoryMax=256M` |
| Storage | 1 GiB observatory root cap; scanner fails closed at projected bound |
| Runtime | 10-minute systemd start timeout |
| Privileges | `NoNewPrivileges=true`; no credentials or authenticated requests |
| Director cycle | Timer at :15 and :45 UTC; skips evidence older than two hours; one scan-pinned Arena admission |
| Director service | CPU 5%, memory 512 MiB, private temp, `AF_UNIX` socket family only |
| Qualification job | CPU quota 10%, memory 512 MiB, wall 300 seconds, source cap 64 MiB / 512 events, `AF_UNIX` only |
| Write access | Veritas observatory and this checkout's isolated `data/arena` roots only |

The observer uses public Gamma GET discovery and unauthenticated public CLOB reads. It makes no orders and has no wallet, deposit, or authenticated trading path. Request/receipt timing does not prove response-batch atomicity, venue sequence, upstream queue age, or executable quote lifetime.

## Data lifecycle and versioning

The scanner writes exclusive, content-hashed compressed snapshots. `continuous_analysis.py` verifies finalized snapshot identities and immutable event digests, then atomically updates analyzer state and summary. It accepts at most 100 pending snapshots per run and rejects malformed, oversized, digest-mismatched, or unsafe inputs. v4 records paired legacy/current gate outcomes and per-market sample coverage. Snapshot fingerprint changes are sampled inter-scan changes, not true venue update rates.

The one-shot NegRisk studies cover the complete nine-outcome Strava set and a
second seven-market OpenAI IPO group. The OpenAI group was enumerated by seven
direct Gamma market reads and checked against the adapter's on-chain question
count; the Gamma group filter returned 20 unrelated rows and no matching
members. A second CLOB refresh and a public WebSocket cross-check each returned
all 14 books. Both source captures failed the 5-second age and 250 ms skew
rules. The WebSocket top prices and last-trade prices matched the REST response
for all tokens, while full displayed depth changed and the stream supplied no
sequence field. The new stream replay runner verifies the saved frame and its
REST reference. These fixed-group reads remain separate from the recurring
observer timer. See [Gate A checkpoint
016](VERITAS_MISSION2_GATE_A_CHECKPOINT_016.md).

## Previous Gate A checkpoint 019 — evidence at 14:21 UTC

The 14:01 UTC scan finalized as snapshot 21. The v4 panel contains 840
selected observations, 751 quality-valid pairs, 89 invalid pairs, 176 legacy
age/skew-valid pairs, and 367 distinct markets. The paired yield increase is
575/840 (68.45 percentage points). All five economic gates remain
zero-positive. Scan 21's bounded union has 300 unique IDs, 198 supported
pairs, and 102 explicit exclusions; its 40-market sample retained 37 rotating
markets and three available frozen controls.

The 14:13 finalized-source summary contains 40,459 campaign-window frame
records, 30,809 touched states, and 29,749 quality-valid states. The prefix
remains incomplete with 1,630 finalized segments / 430,839,649 bytes pending;
positive top-ask and full-depth counts remain zero. The earlier 12:43 summary
contained 4,078 campaign-window frames; checkpoint 016's interpretation of
that counter as zero frames was incorrect and was corrected in checkpoint 017.

The 14:15 Director cycle recorded completion of scan 20 and admitted scan 21.
Arena completed all 21 events at 14:16:20 UTC, but the manifest still showed
`QUEUED` for scan 21 and scan 20 as last qualified at this check. The next
Director cycle at 14:45:16 UTC is the scheduled reconciliation point. See
[Gate A checkpoint 019](VERITAS_MISSION2_GATE_A_CHECKPOINT_019.md), [Gate F checkpoint
009](VERITAS_MISSION2_GATE_F_CHECKPOINT_009.md), and [research inventory
022](VERITAS_MISSION2_RESEARCH_INVENTORY_022.json).

## Previous Gate A checkpoint 018 — scan 20 evidence

The 13:31 UTC scan finalized as snapshot 20. The v4 panel contains 800
selected observations, 714 quality-valid pairs, 86 invalid pairs, 167 legacy
age/skew-valid pairs, and 349 distinct markets. The paired yield increase is
547/800 (68.38 percentage points). All five economic gates remain
zero-positive. Scan 20's bounded union has 297 unique IDs, 153 supported
pairs, and 144 explicit exclusions; its 40-market sample retained 37 rotating
markets and three available frozen controls.

The 13:43 finalized-source summary contains 29,198 campaign-window frame
records, 21,747 touched states, and 21,041 quality-valid states. The prefix
remains incomplete with 1,699 finalized segments / 450,044,085 bytes pending;
positive top-ask and full-depth counts remain zero. The earlier 12:43 summary
contained 4,078 campaign-window frames; checkpoint 016's interpretation of
that counter as zero frames was incorrect and was corrected in checkpoint 017.

The 13:45 Director admission completed all 20 events in Arena, but its
manifest still showed `QUEUED` and scan 19 as last qualified at this check.
The next Director cycle at 14:15:29 UTC is the scheduled reconciliation
point. See [Gate A checkpoint 018](VERITAS_MISSION2_GATE_A_CHECKPOINT_018.md),
[Gate F checkpoint 008](VERITAS_MISSION2_GATE_F_CHECKPOINT_008.md), and
[research inventory 021](VERITAS_MISSION2_RESEARCH_INVENTORY_021.json).

## Gate A checkpoint 016 — historical evidence


The 12:31 UTC observer scan remains finalized as snapshot 18. It has 32
quality-valid pairs and eight empty-ask invalid pairs; the cumulative panel has
645/720 quality-valid pairs across 304 distinct markets. All five economic
qualification gates remain zero-positive. The 12:45 Arena qualification
completed all 18 analysis events and found no positive gross state.

The OpenAI IPO stream capture returned a complete 14-token book set in 84 ms,
but its source age reached 17.781 seconds and source timestamp skew was 11.977
seconds. Best bid, best ask, and last-trade prices matched the REST refresh for
14/14 tokens. The current stream schema provides no sequence field, so the
capture does not establish independent sequence freshness. See [Gate A
checkpoint 016](VERITAS_MISSION2_GATE_A_CHECKPOINT_016.md), [Gate F checkpoint
006](VERITAS_MISSION2_GATE_F_CHECKPOINT_006.md), and [inventory
019](VERITAS_MISSION2_RESEARCH_INVENTORY_019.json).

The finalized-source summary referenced by checkpoint 016 contains 4,078
campaign-window frame records, 2,779 touched market-frame states, and 2,739
quality-valid states. Top-ask and full-depth positive counts remain zero, and
the source prefix remains incomplete with finalized segments pending.

The independent Reality source analyzer validates the frozen campaign identity and reads only cataloged finalized `.seg` inputs. It never opens `.open` files. Per run it is limited to 128 segments or 32 MiB of new segment data; each segment is capped at 16 MiB. Catalog scans are bounded. Source state and events retain campaign/code/prefix digests and stop on identity drift. Resource bounds remain CPU 5%, memory 256 MiB, low priority, ten-minute timeout, and Veritas-only writes.

Arena's existing job worker supports a pinned, bounded Veritas qualification task. The recurring Director detects each new finalized v4 scan, checks readiness, admits one idempotent job, verifies the finding digest and source lineage, and reports an evidence-based recommendation. It also validates and records the separate finalized-source summary; it does not coordinate or launch source replay, start strategy/model experiments, or promote a model. See [Gate F checkpoints 001](VERITAS_MISSION2_GATE_F_CHECKPOINT_001.md) and [002](VERITAS_MISSION2_GATE_F_CHECKPOINT_002.md).

## Frozen campaign censoring snapshot

At 08:44 UTC the Gate C analyzer captured 10,165 decisions from one read-only
SQLite transaction. It used `mode=ro` and `PRAGMA query_only=on`; it did not copy
raw observations. The artifact contains 40,660 horizon slots, 930 observed
public measurements, 39,730 censors, and zero pending outcomes in that snapshot.
The campaign writer remains active, so this is an interim view.
`future_observation_unavailable` remains unresolved between quiet venue
activity and feed/cohort coverage. The full event hash chain and a full database
integrity check were not run. See [Gate C checkpoint
001](VERITAS_MISSION2_GATE_C_CHECKPOINT_001.md).

## Read-only inspection

```bash
systemctl --user is-active midas-veritas-observatory.timer
systemctl --user is-active midas-veritas-source-analysis.timer
systemctl --user is-active midas-veritas-research-director.timer
systemctl --user list-timers midas-veritas-observatory.timer --no-pager
systemctl --user list-timers midas-veritas-source-analysis.timer --no-pager
systemctl --user list-timers midas-veritas-research-director.timer --no-pager
systemctl --user status midas-veritas-observatory.service --no-pager
systemctl --user status midas-veritas-source-analysis.service --no-pager
journalctl --user -u midas-veritas-observatory.service -n 30 --no-pager
journalctl --user -u midas-veritas-source-analysis.service -n 30 --no-pager
journalctl --user -u midas-veritas-research-director.service -n 30 --no-pager
du -sb /home/charlie/midas-veritas/data/veritas-observatory
```

Do not launch overlapping manual runs. If a manual run is needed, invoke its oneshot service and wait for completion before reading the relevant summary.

## Preservation

The separate `/home/charlie/midas-reality` checkout remains the protected source of the frozen campaign. Veritas analysis reads finalized source segments only and writes to its own observatory root. Do not restart or alter Reality services for this workflow. No Arena, Laboratory, Prometheus, or historical campaign records are rewritten. No real-money action is permitted.

## 2026-10-15 15:45 UTC scheduled cycle

The 15:30 observer scan completed in 16 seconds using seven public HTTP attempts and 0.622 CPU seconds; the saved store measured 22,696,673 bytes. The 15:40:45 source replay processed 128 finalized segments / 32,016,580 bytes in 225 seconds and 11.290 CPU seconds. It remains within its 128-segment / 32 MiB batch bounds and leaves 1,438 finalized segments pending. The 15:45:04 Director cycle reconciled scan 23 and admitted scan 24. Arena completed the bounded 24-event job in 1.418 seconds; the Director manifest is due for reconciliation at 16:15:11 UTC. The observer, source-analysis, and Director timers remain active. No manual poll or retry occurred.

See [Gate A checkpoint 022](VERITAS_MISSION2_GATE_A_CHECKPOINT_022.md) and [Gate F checkpoint 012](VERITAS_MISSION2_GATE_F_CHECKPOINT_012.md) for artifact hashes, counters, and the current manifest projection.

## 2026-10-15 16:15 UTC scheduled cycle

The 16:00 observer scan completed in 17 seconds after seven public HTTP attempts and used 0.659 CPU seconds. The 16:10:39 source replay processed 128 finalized segments / 32,329,769 bytes in 227 seconds and 11.347 CPU seconds, within its segment and byte bounds. The 16:15:14 Director cycle reconciled scan 24 and admitted scan 25; Arena completed the bounded 25-event qualification in 1.514 seconds. The Director manifest is due for reconciliation at 16:45:03 UTC. The three timers remain active; no manual poll or retry occurred.

See [Gate A checkpoint 023](VERITAS_MISSION2_GATE_A_CHECKPOINT_023.md) and [Gate F checkpoint 013](VERITAS_MISSION2_GATE_F_CHECKPOINT_013.md) for artifact hashes, counters, and the current manifest projection.

## 2026-10-15 16:45 UTC scheduled cycle

The 16:30 observer scan completed in 16 seconds after seven public HTTP attempts and used 0.632 CPU seconds. The 16:40:08 source replay processed 128 finalized segments / 33,042,875 bytes in 221 seconds and 11.037 CPU seconds, within its segment and byte bounds. The 16:45:04 Director cycle reconciled scan 25 and admitted scan 26; Arena completed the bounded 26-event qualification in 1.525 seconds. The Director manifest is due for reconciliation at 17:15:09 UTC. The three timers remain active; no manual poll or retry occurred.

## 2026-10-15 17:15 UTC scheduled cycle

The 17:01 observer scan completed with 40 selected markets, 33 quality-valid pairs, two identical duplicate discovery records, zero identity conflicts, and zero positive economic gates. It used seven public HTTP attempts. The 17:10:17 source replay processed 116 finalized segments / 33,217,726 bytes in 242 seconds, using 12.138 CPU seconds and 122.3 MiB peak memory. Progress is 2,661/3,903 finalized segments; 1,242 / 344,457,128 bytes remain pending. The 17:15:09 Director cycle admitted scan 27. Arena completed all 27 events in 1.619 seconds with zero-positive gates. The Director manifest projection remains queued pending its scheduled 17:45:25 UTC reconciliation. The three timers remain active; no manual poll or retry occurred.

See [Gate A checkpoint 024](VERITAS_MISSION2_GATE_A_CHECKPOINT_024.md) and [Gate F checkpoint 014](VERITAS_MISSION2_GATE_F_CHECKPOINT_014.md) for artifact hashes, counters, and the current manifest projection.

## 2026-10-15 17:33 UTC observer scan 28

The 17:32:11 observer scan finalized with 40 selected markets, 35 quality-valid pairs, five empty No ask sides, and zero positive top, depth, minimum, or fee gates. Its six-frame union contained 300 unique IDs; 190 passed same-condition V1 eligibility and 110 were explicitly excluded. The cumulative v4 panel now has 28 snapshots, 1,120 selected pairs, 996 quality-valid pairs, 513 distinct market IDs, and no positive top-ask state. The read-only economic-comparison v2 function accepted all 28 event files and returned complete candidate evidence with zero candidate rows; it did not write a finding or replace the next scheduled Arena run.

At 17:33 UTC the observer service had completed; its timer, the source-analysis timer, and the Research Director timer were active. The next scheduled runs were 18:00:31, 17:40:03, and 17:45:25 UTC respectively. The Director manifest still reflects its 17:15 admission of scan 27; Arena completed that job at 17:15:51. The next Director cycle is the reconciliation point. No manual poll, retry, or service restart was run. Gate D implementation and tests are recorded in [checkpoint 001](VERITAS_MISSION2_GATE_D_CHECKPOINT_001.md).

## 2026-10-15 17:59 UTC checkpoint — v3 replay ready

The 17:44:13 finalized-source summary processed 119 segments / 32 MiB in its
bounded batch. Cumulative progress is 2,780/3,962 replayable finalized
segments, with 1,182 segments / 327,830,232 bytes pending through ordinal
360,067. The source prefix remains incomplete and reports zero positive
top-ask and full-depth pre-fee states.

The 17:45:31 Director cycle reconciled scan 27 and admitted scan 28. Arena
completed the scan-pinned v2 qualification at 17:46:13 with all 28 events;
the persisted finding has zero positive states across all five gates. A
read-only v3 comparison of those same 28 events produced the same zero-positive
result and a complete empty replay, but did not write a finding. The next
observer, source-analysis, and Director timer runs were scheduled for
18:00:31, 18:10:37, and 18:15:12 UTC. All three timers were active and their
one-shot services idle at inspection. No service was restarted and no manual
run was launched.

See [Gate D checkpoint 002](VERITAS_MISSION2_GATE_D_CHECKPOINT_002.md) for
implementation, exact hashes, synthetic-path coverage, and verification.

## 2026-10-15 18:02 UTC observer scan 29

The scheduled observer completed scan 29 at 18:00:52 UTC with 40 selected
markets, 38 quality-valid pairs, seven public HTTP attempts, and zero positive
gross, full-depth, minimum, or fee states. The read-only v3 comparison now spans
29 snapshots / 1,160 selected pairs / 1,034 quality-valid pairs / 536 unique
markets. Its maximum top-pair edge remains -0.001 per share, with zero positive
states at every economic gate. The observer timer's next run is scheduled for
18:30:45 UTC. The 18:10:37 source-analysis and 18:15:12 Director runs remain
scheduled; the latter will reconcile scan 28 and can admit scan 29. No manual
run, retry, or service restart was used.

Scan 29 source and selection evidence is indexed in [Gate A checkpoint
026](VERITAS_MISSION2_GATE_A_CHECKPOINT_026.md) and the current machine-readable
[inventory 030](VERITAS_MISSION2_RESEARCH_INVENTORY_030.json).

## 2026-10-15 18:20 UTC source replay and Director recovery note

The 18:10 source-analysis service completed at 18:14:33 UTC with 127 finalized
segments / 33,535,604 bytes processed. Cumulative progress is 2,907/4,023
segments and 714,067,245 processed source bytes; 1,116 segments / 316,707,896
bytes remain. It used 11.65 CPU seconds and 160.1 MiB peak memory, below its
5% CPU and 256 MiB memory bounds, and did not open the active segment.

The 18:15:21 Director service exited successfully at the process level but
marked its manifest `UNVERIFIED`: it rejected the completed scan-28 v2 finding
because it predates the v3 replay object. It did not admit scan 29. The
completed job artifact remains unchanged; its manifest projection is stale and
shows `QUEUED`. Commit `9379985` fixes the version compatibility and adds
regression coverage. A read-only validation of the persisted v2 finding now
passes and labels replay unavailable for legacy v2. No manual reconciliation,
retry, or service restart was run.

At inspection, the observer, source-analysis, and Director timers were active;
their next runs were scheduled for 18:30:45, 18:40:08, and 18:45:20 UTC. The
source and Director one-shot services were inactive after completion. See [Gate
F checkpoint 016](VERITAS_MISSION2_GATE_F_CHECKPOINT_016.md) and [inventory
031](VERITAS_MISSION2_RESEARCH_INVENTORY_031.json).

A post-fix targeted regression completed at 18:22 UTC: 43 backend tests passed
across six affected Veritas/Arena modules. Strict Mypy, Ruff, formatting, and
the targeted Veritas browser flow passed. The failure and recovery chronology
remains in [Gate F checkpoint 016](VERITAS_MISSION2_GATE_F_CHECKPOINT_016.md);
the updated evidence is in [inventory
032](VERITAS_MISSION2_RESEARCH_INVENTORY_032.json).

The v4 paired measurement comparison was recomputed over the same 29 finalized
events: 240/1,160 passed the legacy age/skew rule and 1,034/1,160 passed the
request-to-receipt quality rule, a paired recovery of 794 (+68.45 percentage
points). This is a yield comparison only; sequence, atomicity, and upstream
queue age remain unverified. See the [current inventory
033](VERITAS_MISSION2_RESEARCH_INVENTORY_033.json).

## 2026-10-15 19:07 UTC — coverage pilot scan 1

The scheduled 19:00:44 observer run completed scan
`scan-20261015T190055Z-7799523b9d87` at 19:00:55 UTC, with 40 selected pairs,
32 quality-valid pairs, eight empty-ask invalid pairs, and seven public HTTP
attempts. It used the already scheduled discovery and books reads; the new
pilot added no network calls. The v4 panel advanced to 31 snapshots / 1,240
selected pairs / 1,102 quality-valid pairs / 138 invalid pairs / 575 distinct
selected market IDs. No positive top-gross state was found.

Pilot `VERITAS-M2-COVERAGE-PILOT-001` is running with one scan, 40 slots, 32
valid pairs, zero missed scan sequences, and its fixed end at 2026-10-16
19:00:55 UTC. The source/plan hashes and limitations are recorded in [Gate C
checkpoint 002](VERITAS_MISSION2_GATE_C_CHECKPOINT_002.md).

At this checkpoint the finalized-source analyzer remained at 3,019/4,081
segments with 1,062 segments / 312,431,120 bytes pending. Its next timer was
19:10:05 UTC. The Director's scan-30 qualification job had completed, while
the manifest still showed it queued; its next cycle was 19:15:13 UTC. The
observer's next timer was 19:30:19 UTC. There were no active Arena jobs and the
three Veritas one-shot services were inactive between timers. No manual poll,
retry, or service restart was run.

The Reality recorder and frozen shadow were active. The recorder log retained
a prior DNS resolution failure and degraded-state warning; the shadow service
had one automatic restart after an integrity/continuity mismatch and was
running at inspection. No protected campaign or recording was changed.
Available RAM was 8.9 GiB, swap use 3.5/4 GiB, disk use 56% with 199 GiB free,
and the Veritas observatory root was about 29.3 MB. Main Midas and Reality API
and web services were active. See [inventory 036](VERITAS_MISSION2_RESEARCH_INVENTORY_036.json).

## 2026-10-15 19:16 UTC — scheduled source and Director recurrences

The 19:10:05 source-analysis timer ran to completion at 19:14:38 UTC with
exit status 0 and zero restarts. It processed 113 finalized segments /
33,445,857 bytes; cumulative progress is 3,132/4,140 segments and
780,800,513 source bytes, with 1,008 segments / 298,406,538 bytes pending.
The source summary now reports 192,072 campaign-window frame records,
169,253 quality-valid states, 43 markets, and zero positive top-ask or
full-depth states. The batch used 13.619 CPU seconds, peaked at 146.7 MiB,
and used no swap. It reads finalized `.seg` inputs only.

The 19:15:13 Director timer completed normally at 19:15:50 UTC and admitted
scan `scan-20261015T190055Z-7799523b9d87`. Arena job
`job-c2b34af59d624f2ea3081b54` completed 31/31 with exit status 0 in 1.914
seconds. Finding `veritas-qualification-v1-b3744235647f846e` reports 1,102
quality-valid pairs across 575 markets, zero positives at all five gates, and
complete zero-candidate replay evidence. The job record is complete, while
the Director manifest still projects `QUEUED`; its next scheduled cycle is
19:45:26 UTC. No manual poll, retry, or restart occurred. See [Gate F
checkpoint 017](VERITAS_MISSION2_GATE_F_CHECKPOINT_017.md).

At 19:16 UTC the Veritas one-shot services were idle between timers; no Arena
job was running. The next timers were the observer at 19:30:19 UTC, source
analysis at 19:40:45 UTC, and Director at 19:45:26 UTC. Host load average was
1.52 on six CPUs, RAM available 8.9 GiB, swap used 3.5/4 GiB, disk 56% used
with 199 GiB free, and the observatory root was 29,467,543 bytes. The Reality
recorder and shadow remained active; their previously recorded DNS/degraded
warning and one shadow restart remain unresolved operational cautions. No
protected campaign state was changed. See [inventory 036](VERITAS_MISSION2_RESEARCH_INVENTORY_036.json).


## 2026-10-15 19:41 UTC — scan 32 and Gate G dashboard code checkpoint

The scheduled observer completed scan
`scan-20261015T193035Z-7597bbb981fa` at 19:30:35 UTC. Six bounded public
discovery pages returned 300 unique market IDs; 188 met same-condition V1
eligibility. Forty pairs were selected (37 rotating, three available stable
controls); 34 passed the request/receipt quality gate and six had an empty ask
side. The 112 explicit exclusions comprised 46 markets with unverified
augmented NegRisk semantics and 66 unsupported outcome relationships. All
gross, depth, minimum-notional, and fee gates remained zero-positive.

The cumulative v4 panel has 32 snapshots, 1,280 selected pairs, 1,136
quality-valid pairs, 144 invalid pairs, and 598 distinct selected IDs. The
legacy reported-age rule accepts 262 pairs versus 1,136 under request/receipt
completeness (+874, +68.28 percentage points). The maximum top-pair edge
remains -$0.001 per share. These are repeated selected observations, not
independent opportunities or venue-wide coverage.

The 24-hour pilot has completed two scans: 66/80 slots valid, 14 invalid, and
zero missed sequences. Rotating markets yielded 64/74 valid; available
controls yielded 2/6. This is descriptive and nonrandomized. The pilot adds
no requests and remains fixed through 2026-10-16 19:00:55 UTC.

At capture (19:41 UTC), the Reality recorder and frozen shadow were active.
The shadow has one historical automatic restart after a final-source integrity
or continuity mismatch; the recorder retains a prior temporary DNS/degraded
warning. The scheduled source-analysis run started at 19:40:47 UTC and was
still active at capture (PID 528516, 1.0 min elapsed, 3.2 CPU seconds, 171 MiB
RSS); its last completed summary remained at 3,132/4,140 segments (780,800,513
bytes processed; 298,406,538 pending). It is bounded to 128 segments and 32
MiB per run. The Director timer is next at 19:45:26 UTC; the observer timer is
next at 20:00:38 UTC. No Arena job was active.

Host load average was 0.87 / 1.39 / 1.45 across six CPUs, RAM available was
8.9 GiB of 15 GiB, swap used was 3.5/4 GiB, and disk use was 56% with 199 GiB
free. The observatory root measured 30,246,059 bytes. Main Midas and Reality
APIs and web services were active. Gate G checkpoint 005 is committed code on
`project/veritas` but was not deployed; no services, collectors, or campaigns
were restarted or modified for this checkpoint.

See [Gate G checkpoint 005](VERITAS_MISSION2_GATE_G_CHECKPOINT_005.md),
[research inventory 037](VERITAS_MISSION2_RESEARCH_INVENTORY_037.json), and
[the live pilot summary](../data/veritas-observatory/measurement-pilots/VERITAS-M2-COVERAGE-PILOT-001/summary.json).

## 2026-10-15 21:22 UTC checkpoint

The observatory, source-analysis, Director, Arena, and supplemental gap-detail
timers remain enabled. Next planned Veritas runs at capture were the observer
at 21:31:31 UTC, source analysis at 21:40:13, Director reconciliation at
21:45:04, and gap detail at 21:50:00. The Director one-shot and both recent
analysis one-shots exited successfully. The scan-35 Arena job is complete;
the Director's persisted projection remains queued until its next cycle.

| Service | State | Restarts |
| --- | --- | ---: |
| Midas API / web | Active | 0 / 0 |
| Reality recorder | Active | 0 |
| Frozen Reality shadow | Active | 1 prior restart |
| Reality API / web | Active | 0 / 0 |
| Veritas observer / source analysis / Director / gap detail | Inactive after successful bounded one-shot | 0 each |

No HTTP health probe was run at this capture. A historical queued Veritas
Arena job (`job-8cf39368af21426ea3127501`) is failed with
`Research source changed while queued`; the current scan-35 job was admitted
against the current source revision and completed successfully. This is an
old job failure, not an active worker failure. Other failed unit records in
the user manager are from earlier unrelated regression or research runs.

Host load average was 0.96 / 1.02 / 1.18 across six CPUs. RAM available was
9.2 GiB of 15 GiB; swap was 3.6/4 GiB. The root filesystem was 56% used with
199 GiB free. `data/veritas-observatory` occupied 42 MiB and the Reality raw
recording directory 1.2 GiB. Between 20:59 and 21:21 UTC the gap-detail
cataloged source total grew by about 9.9 MB (processed plus pending), or
roughly 27 MB/hour over that short interval. This includes finalized source
growth and is not a long-term rate estimate.

No collector, API, web service, frozen campaign, or existing research job was
restarted or changed for this checkpoint. No HTTP requests were made to probe
health; all health statements above come from systemd state, process state,
and filesystem/resource reads.


## 2026-10-16 05:27 UTC read-only operations snapshot

The Midas API/web, Reality recorder, frozen shadow, Reality API/web were active. The recorder and APIs showed zero restarts; the shadow showed one historical restart and retains its 10% CPU quota. Both local API health probes were HTTP 200 / READY at 05:22 UTC; no new HTTP probe was run at 05:27. Veritas observer, source-analysis, Director, and gap-detail one-shot services were inactive between timers; no Arena job service was active. The Arena scheduler timer was due at 05:28 UTC, followed by observer 05:30:53, gap detail 05:35, source analysis 05:40:08, and Director 05:45:02 UTC. The scan-51 child had completed but the Director manifest still projected QUEUED pending that scheduled cycle.

The archive unit remained failed after the 04:33:35 UTC 30-minute timeout, with zero restarts; archive completeness and data loss remain unverified. The fixed pilot was last refreshed at 05:22 UTC (20/48 scans, 652/800 valid slots, 492 markets, one skipped sequence). Finalized-source analysis was current through 5,324/5,324 available catalog segments with 361,068 quality-valid states across 91 markets and zero positive top-ask/full-depth states. Gap detail had processed 3,019/5,344 segments, with 2,323 / 633,802,218 bytes pending and 735 campaign-window gap events; it read no active segment.

Host load was 1.53 / 1.08 / 0.97; 9.3 GiB RAM was available, swap use was 3.7/4 GiB, and the root filesystem was 56% used with 197 GiB free. `data/veritas-observatory` occupied 55,893,662 bytes. The separately measured Reality research recording directory `/home/charlie/midas-reality/data/research/reality` occupied 1,478,846,486 bytes; this is a path-specific size, not a growth-rate estimate. `systemctl --user --failed` listed 15 loaded historical failed units, including the archive timeout and prior Arena/research/regression units; no active Veritas one-shot unit was failed at capture.

No campaign, collector, service, or research job was restarted or manually triggered for this snapshot. See [research inventory 069](VERITAS_MISSION2_RESEARCH_INVENTORY_069.json).


## 2026-10-16 05:47 UTC scheduled research snapshot

The 05:45 Director cycle exited 0 and reconciled scan 51. It admitted scan 52 to Arena job `job-6c0fa56b47034494a10ccaa1`. The child completed 52/52 events with exit 0; the finding has 1,788 valid pairs and zero positives at all five economic gates, with candidate evidence and source replay complete and empty. The Director manifest still records the completed child as QUEUED and scan 51 as last qualified until its scheduled 06:15:10 UTC cycle. No poll, retry, or manual admission was used.

The 05:40 finalized-source analysis exited 0 at 05:42:25 UTC with zero restarts. It processed all 5,382/5,382 available catalog segments (1,391,469,142 bytes; zero pending), yielding 369,257 quality-valid states across 91 markets. Top-ask, full-depth, and minimum-notional positive counts are zero; the frozen campaign window remains collecting. The separate 05:35 gap-detail run exited 0 at 05:36:25 UTC, with 3,132/5,374 segments processed, 2,240 / 608,836,620 bytes pending, and 789 campaign-window gap events; no active segment was read.

The fixed measurement pilot is running at 21/48 scans: 685/840 valid market-pair slots across 520 selected markets, one missed sequence; comparison remains descriptive and non-randomized. The Reality recorder, frozen shadow, Midas/Reality APIs, and web services are active. The shadow has one historical restart and its lag was not refreshed. Both APIs were HTTP 200 / READY at 05:22 UTC; no new HTTP probe was run at this capture. The archive unit remains failed following its 04:33:35 UTC 30-minute timeout with zero restarts; archive completeness and data loss remain unverified.

Host load was 1.25 / 1.33 / 1.29; available RAM was 9.8 GiB, swap use was 3.8/4 GiB, and root disk use was 56% with 197 GiB free. The Veritas observatory directory occupied 56,914,183 bytes, up 1,020,521 bytes from the 05:27 sample. `/home/charlie/midas-reality/data/research/reality` occupied 1,486,467,696 bytes, up 7,621,210 bytes from 05:27. These two-point changes over about 20 minutes are short-term observations, not long-term growth rates.

No service, collector, frozen campaign, or research job was manually restarted or triggered for this checkpoint. See [research inventory 070](VERITAS_MISSION2_RESEARCH_INVENTORY_070.json).


## 2026-10-16 07:39 UTC runtime and research checkpoint

- The public Reality recorder, frozen shadow, Midas/Reality APIs, and web
  services are active. The recorder and APIs show zero systemd restarts; the
  shadow has one historical restart. The Reality archive unit remains failed
  with exit status 15 and zero restarts after its prior timeout.
- Read-only health probes returned HTTP 200: the Midas API reports `READY` in
  demo mode with live execution disabled; the Reality API reports
  `DEGRADED` in demo mode with live execution disabled. The synthetic Reality
  demo API recorder is separate from the active public recorder.
- The latest observer scan is scan 56
  (`scan-20261016T073034Z-c97112eae9a3`): 29/40 quality-valid pairs and zero
  positive top-gross pairs. The measurement-only coverage pilot is 25/48 scans,
  808/1,000 valid slots across 587 markets, with one skipped sequence. Its
  role-yield comparison is descriptive and nonrandomized.
- A1 coverage and independent-source replay remain verified through scan 55.
  The 07:12 finalized-source summary covers 5,558/5,558 cataloged segments /
  1,430,421,272 bytes and 378,755 quality-valid states across 98 markets. The
  next source-analysis timer is 07:40 UTC.
- The 07:35 gap-detail batch completed by 07:36:23 UTC with zero restarts. Its
  finalized-only prefix covers 4,038/5,606 replayable segments /
  1,039,209,554 bytes, leaving 1,568 segments / 402,129,096 bytes pending. It
  indexes 1,227 campaign-window gaps and read no active segment.
- The 07:15 Director cycle reconciled scan 54 and admitted scan 55. The
  manifest projected the child as `QUEUED`; its scheduled reconciliation is
  due at 07:45:24 UTC. No manual poll, retry, or admission was performed, and
  the Arena package remains pinned.
- At 07:39 UTC, load averages were 0.71 / 0.75 / 0.86; available RAM was
  9.6 GiB of 15 GiB; swap use was 3.8/4 GiB; root storage was 56% used with
  197 GiB free. The configured public recording directory measured
  1,445,297,998 bytes and the Veritas observatory directory 61,568,254 bytes.
  These are point measurements, not a stable growth-rate forecast.
- The observer, gap-detail, source-analysis, and Director one-shot services
  were inactive between runs with zero restarts. No training worker was
  observed. No service, collector, frozen campaign, or research job was
  manually restarted, cancelled, or changed for this checkpoint.


## 2026-10-16 08:01 UTC runtime and research checkpoint

- The latest public observer scan is scan 57
  (scan-20261016T080056Z-49ba7ada7fab), captured at 08:00:56 UTC. The current
  v4 summary covers 57 scans / 2,280 selected pair observations, with 1,945
  quality-valid pairs and zero positive top-gross pairs.
- The immutable measurement pilot is running at 26/48 scans: 842/1,040 valid
  slots across 608 selected market IDs, with one skipped sequence. Audit 002
  remains through 25 scans; the Gate G source projection marks it stale.
- The Reality recorder is active with zero systemd restarts and continues
  writing segments. Its 07:58 status reports RECORDING_UNSEQUENCED, eight
  markets / 16 fresh outcome books, 4,097 gap markers, no verified sequence,
  and a ConnectionClosedError field. This means recording is active but
  continuity is not verified.
- The frozen shadow process remains active with one historical restart. Its
  status is WARMING_OR_LAGGED_SOURCE; at 07:58 its last source receipt was
  about 15 hours 47 minutes old and its last decision about 23 hours old. It
  reports insufficient forward evidence and zero pending horizons.
- Midas and Reality APIs and web services remain active. The last read-only
  probes, at 07:39 UTC, returned HTTP 200; Midas reported READY and Reality
  DEGRADED in demo mode with live execution disabled. No fresh health probes
  were made for this snapshot.
- Finalized-source analysis remains current at 5,617/5,617 segments /
  1,443,975,599 bytes, 382,066 quality-valid states across 98 markets, and
  zero positive top-ask or full-depth states. It read no active segment.
- Gap detail remains partial at 4,121/5,638 replayable segments /
  1,071,968,283 bytes, leaving 1,515 segments / 376,229,972 bytes pending.
  It indexes 1,268 campaign-window gaps and read no active segment.
- The 07:45 Director manifest still projects scan 56 as QUEUED, with scan 55
  last qualified. The scheduled 07:56 Arena scheduler pass exited
  successfully; scan 57 has not yet been reconciled. Keep the admitted Arena
  source revision pinned.
- At 08:01 UTC, load averages were 0.94 / 0.95 / 0.94; available RAM was
  9.7 GiB of 15 GiB; swap use was 3.8/4 GiB; root storage was 56% used with
  197 GiB free. The Veritas observatory directory occupied 62,558,308 bytes;
  the configured public recording directory occupied 1,456,793,716 bytes.
  These are point sizes, not a stable growth-rate estimate.
- Veritas one-shot services were inactive between timer firings with zero
  restarts. The Reality archive unit remains failed with exit status 15 after
  its prior timeout and zero restarts. No model training worker was observed.
- No service, collector, frozen campaign, or research job was manually
  restarted, cancelled, or changed for this checkpoint.
