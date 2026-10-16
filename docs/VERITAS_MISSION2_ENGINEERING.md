## Latest checkpoint — 2026-10-16T09:30:52Z, scan-60 independent replay

The public snapshot directory contains 60 saved snapshots through `scan-20261016T093021Z-b20cf6a3b852`. Independent audit 012 replays 2,400 selected market observations, reproduces all 2,047 stored quality-valid states and top-edge results with zero mismatches, agrees on 2,548 fee calculations, and finds zero positive gross, full-depth, minimum-qualified, single-match-fee, or fragmentation-safe-fee states. The new scheduled scan contributed 32/40 quality-valid pairs and zero positive top-gross pairs. The snapshots are intermittent and correlated. See [Gate B checkpoint 013](VERITAS_MISSION2_GATE_B_CHECKPOINT_013.md), audit 012, and ledger H133.

Economic model v3 now charges both taker-leg fees as collateral entry costs. The synthetic break-even sensitivity is corrected but remains hypothetical; the positive full-depth single-match case does not survive the fragmentation-safe fee bound. The engine is isolated in `economic_feasibility_v3.py`; the previous `economics.py` depth helper remains at its exact source-analysis-pinned hash.

The 09:10 UTC finalized-source run failed once because the v3 edit changed the `economics.py` fingerprint stored with its resumable state. The campaign and cursor were unchanged. After isolating the v3 model and restoring the exact pinned helper, the bounded one-shot completed at 09:23:41 UTC: 5,815/5,815 finalized segments, 1,491,299,688 processed bytes, 394,313 quality-valid states across 102 markets, zero positive gross states, and no pending segments. Campaign SHA remained `aa8acb2b46823c1a1e3ac5d01a57dde917746c2c7471098ae2a4598875e322f5`. See [Gate F checkpoint 035](VERITAS_MISSION2_GATE_F_CHECKPOINT_035.md) and H132.

The hosted Midas API and web process still respond, but the serving API is loaded from `/home/charlie/midas`; its OpenAPI has no Veritas routes and `/api/veritas/overview` returns 404. The branch dashboard update is not deployed. No long-running service was restarted; only the failed, bounded source-analysis one-shot was resumed. Focused Veritas tests pass (120 passed, one upstream deprecation warning); Ruff and formatting pass. The 09:30 UTC observer cycle succeeded; the next scheduled checks are 09:40 UTC source analysis and 09:45 UTC Research Director. Keep the campaign and no-trade decision unchanged.

## Previous checkpoint — 2026-10-16T07:36:47Z, scan-55 independent replay and coverage-design audit

The A1 universe replay and independent raw-source audit are complete through
scan 55 / 2,200 selected pair observations. The independent audit reproduces
all 1,882 v4 quality and edge decisions with zero mismatches; no positive
top-pair, depth, minimum, or fee-qualified result appears. The newest scan 56
is separately recorded by the active measurement pilot at 29/40 valid pairs
and zero positive top-gross pairs, but is not yet included in A1 artifact 009.
See [Gate A checkpoint 051](VERITAS_MISSION2_GATE_A_CHECKPOINT_051.md), [Gate B
checkpoint 010](VERITAS_MISSION2_GATE_B_CHECKPOINT_010.md), and ledgers H123–H124.

The new inclusion-support audit independently verifies all 25 coverage-pilot
events and their snapshot and analysis-event lineage. It finds full rotating
population support in 23 scans, partial support in two, and 99.80% pooled
population support. The 82.96% mean design-weighted yield over fully supported
scans remains descriptive; frozen controls are not randomized against the
rotating cohort. See [Gate A checkpoint
052](VERITAS_MISSION2_GATE_A_CHECKPOINT_052.md), [audit
002](VERITAS_MISSION2_COVERAGE_DESIGN_AUDIT_002.json), and ledger H125.

The latest finalized-source summary covers 5,558/5,558 cataloged segments /
1,430,421,272 bytes and 378,755 quality-valid states across 98 markets, with
zero positive top-ask, full-depth, or minimum-notional states. The gap-detail
prefix covers 4,038/5,606 replayable segments and records 1,227
campaign-window gaps; 1,568 segments / 402,129,096 bytes remain pending. The
07:15 Director cycle admitted scan 55; its next scheduled reconciliation is
07:45:24 UTC. The Arena source remains pinned. Four focused inclusion-audit
tests pass; no full regression or model training was run. Mission 2 remains
active.

## Previous checkpoint — 2026-10-16T05:17:20Z, scan-51 qualification and source catch-up

The 05:15 Director cycle reconciled scan 50 and admitted scan 51 to Arena.
The scan-51 child completed 51/51 events with 1,755/2,040 quality-valid pairs
and zero positive states at all five economic gates. Candidate evidence is
complete with zero rows; independent candidate replay is complete with zero
candidates. The maximum top-pair edge is -$0.001/share. The Director manifest
now records scan 50 as last qualified and scan 51's completed child remains
`QUEUED` in its projection until the scheduled 05:45:02 UTC reconciliation.
See [Gate F checkpoint
032](VERITAS_MISSION2_GATE_F_CHECKPOINT_032.md) and ledger H113.

The scheduled finalized-source replay advanced to 5,324/5,324 cataloged
segments / 1,375,911,587 bytes, with 361,068 quality-valid states across 91
markets and zero positive top-ask, full-depth, or minimum-notional states. It
read no active segment. The campaign window remains in collecting status. See
[Gate C checkpoint 017](VERITAS_MISSION2_GATE_C_CHECKPOINT_017.md).

The reported-timestamp audit remains pinned through 51 snapshots; its
endpoint association finding is recorded in [Gate B checkpoint
005](VERITAS_MISSION2_GATE_B_CHECKPOINT_005.md) and ledger H112. Services and
the frozen shadow were left untouched. Both APIs returned READY in demo mode;
the archive unit remains failed after timeout. No full Mission 2 regression
was run. See [inventory 067](VERITAS_MISSION2_RESEARCH_INVENTORY_067.json)
and [operations](VERITAS_MISSION2_OPERATIONS.md). Mission 2 remains active.

## Previous checkpoint — 2026-10-16T05:01:27Z, reported timestamp audit and scan 51

The bounded offline timestamp/content audit verified and replayed all 51 saved
snapshots (33,318,338 compressed bytes; 4,080 retained book observations;
1,806 outcome assets). Across 2,274 repeated-asset endpoint transitions,
2,197 content changes coincided with an advancing reported timestamp; 37
unchanged-content transitions also had an advancing timestamp, and 40 had an
unchanged timestamp. No content change with a same or regressed timestamp was
observed. Of 1,848 endpoints older than five seconds by the reported field,
1,771 had changed content and 77 had unchanged content. Intermittent endpoint
comparisons do not establish timestamp semantics, sequence freshness, or quote
persistence. See [Gate B checkpoint
005](VERITAS_MISSION2_GATE_B_CHECKPOINT_005.md), [timestamp audit
001](VERITAS_MISSION2_REPORTED_BOOK_TIMESTAMP_AUDIT_001.json), and ledger
H112.

The scheduled observer completed scan 51
(`scan-20261016T050020Z-5729ddc65f43`) with 28/40 quality-valid pairs and zero
positive top-gross pairs. The fixed coverage pilot has 20/48 scans and 652/800
valid slots, including one skipped sequence; its rotating/control comparison
remains descriptive and nonrandomized. The 04:45 Director cycle and 04:50 gap
batch completed successfully. The source analyzer's latest sealed prefix is
5,264/5,264 segments, with 354,898 valid states and no positive top-ask,
full-depth, or minimum-notional state. The Director's scan-50 child has no
positive candidate; its manifest still projects `QUEUED` pending the next
scheduled cycle. See [inventory 066](VERITAS_MISSION2_RESEARCH_INVENTORY_066.json)
and [operations](VERITAS_MISSION2_OPERATIONS.md).

The timestamp audit's four focused tests passed; Ruff, formatting, strict
Mypy, digest verification, and `git diff --check` passed. No full regression
was run. The analysis used finalized local snapshots only and made no public
requests or orders. Mission 2 remains active.

## Previous checkpoint — 2026-10-16T04:42:06Z, scan-50 audit and source catch-up

The offline A1 replay now verifies 50 snapshots / 32,683,291 compressed bytes.
It finds 6,059 Gamma IDs, 2,166 eligible at least once, 887 selected IDs, and
1,727/2,000 current-replay valid pairs. The discovery union is conditional and
not a venue-wide denominator. See [Gate A checkpoint
046](VERITAS_MISSION2_GATE_A_CHECKPOINT_046.md) and [coverage artifact
004](VERITAS_MISSION2_MARKET_UNIVERSE_COVERAGE_004.json).

The independent raw audit also covers 50 scans. It reproduces all 1,727
quality and top-edge decisions with zero mismatches; 374 pass the conservative
reported-age sensitivity, and every gross, depth, minimum, and fee gate is
zero. See [Gate B checkpoint
004](VERITAS_MISSION2_GATE_B_CHECKPOINT_004.md) and [audit artifact
004](VERITAS_MISSION2_INDEPENDENT_OPPORTUNITY_AUDIT_004.json).

The read-only market-coverage route now validates artifact 004 against ledger
H110. H111 records the independent scan-50 audit. The latest offline analyses
made no public requests and used no orders. The dashboard API and coverage
tests passed 28 cases; Ruff, formatting, strict Mypy, and diff checks passed.
The in-process overview and artifact routes returned HTTP 200 and the served
coverage hash matched artifact 004. The scheduled 04:45 Director cycle remains
pending.

The scheduled finalized-source analyzer then completed at 04:42:06 UTC with
zero restarts. Its prefix advanced to 5,264/5,264 segments / 1,358,762,036
bytes and 354,898 quality-valid states across 87 markets. It found zero
positive top-ask, full-depth, or minimum-notional states. The job used 5.178
CPU seconds, peaked at 120.6 MiB, and read no active segment. See [Gate C
checkpoint 016](VERITAS_MISSION2_GATE_C_CHECKPOINT_016.md).

## Previous checkpoint — 2026-10-16T04:29:03Z, gap-index extension and H109 attribution

The scheduled 04:20 UTC gap-detail batch completed at 04:21:18 with exit 0,
zero restarts, 3.939 CPU seconds, and a 62.5 MiB peak. The partial index now
covers 2,545/5,224 replayable finalized segments, with 2,679 segments /
736,206,152 bytes pending. It contains 500 campaign-window resynchronization
events across 20 markets; no active segment was read. See [Gate C checkpoint
015](VERITAS_MISSION2_GATE_C_CHECKPOINT_015.md).

Versioned censor-attribution artifact 002 scanned 40,075 censored outcomes and
verified 339 gap-related rows. It now links 100 exact recorded-gap references
to indexed events and leaves 79 exact references beyond the index. There are
63 same-market preceding-gap links across nine unique gap events; these remain
temporal associations, not causal proof. The ledger records this as H109.

The read-only API now validates artifact 002 against H109's path, file hash,
result digest, and analysis version. Dashboard API and coverage tests passed
28 cases; Ruff, formatting, strict Mypy, and `git diff --check` passed. The
source-only update remains undeployed. See [Gate G checkpoint
014](VERITAS_MISSION2_GATE_G_CHECKPOINT_014.md).

At 04:27 UTC the collector, frozen shadow, and APIs were active; both health
endpoints returned HTTP 200. The 04:20 gap job was inactive after its
successful exit. The next observer, gap-detail, source-analysis, and Director
timers are 04:31:28, 04:35, 04:40:23, and 04:45:07 UTC. No campaign or
collector state was changed. See [operations](VERITAS_MISSION2_OPERATIONS.md)
and [inventory 063](VERITAS_MISSION2_RESEARCH_INVENTORY_063.json).

## Previous checkpoint — 2026-10-16T04:18:16Z, independent scan-49 audit, scheduled qualification, and finalized-source catch-up

The independent raw audit now covers 49 saved scans / 1,960 observations. It reproduces the v4 validity and top-edge decisions for all 1,691 valid states with zero mismatches; strict reported-age sensitivity admits 364, while 1,327 states exceed five seconds on at least one leg. All gross/depth/minimum/fee gates remain zero. See [Gate B checkpoint 003](VERITAS_MISSION2_GATE_B_CHECKPOINT_003.md).

The 04:15 UTC Research Director cycle admitted scan 49 to Arena. Its 49/49 child completed with all five economic gates at zero and complete empty candidate evidence and replay. The Director manifest still projects QUEUED even though the job record is complete; scan 48 remains its last qualified scan. The next scheduled cycle at 04:45 UTC is the reconciliation point. See [Gate F checkpoint 031](VERITAS_MISSION2_GATE_F_CHECKPOINT_031.md).

The finalized-source analyzer caught up at 04:13 UTC: 5,206/5,206 segments, zero pending bytes, 351,524 valid states over 87 markets, and zero positive top-ask/full-depth states. The separate gap-detail prefix remains incomplete at 2,417/5,194 replayable segments, with 435 campaign-window resynchronization events across 15 market IDs.

The source-only dashboard route still targets artifact 003/H105 and remains uncommitted and undeployed. The pilot remains at 18/48 scans. No service, collector, pilot, or frozen campaign was modified.

## Latest checkpoint — 2026-10-16T04:18:16Z, independent scan-49 audit, scheduled qualification, and finalized-source catch-up

The independent raw audit now covers 49 saved scans / 1,960 observations. It reproduces the v4 validity and top-edge decisions for all 1,691 valid states with zero mismatches; strict reported-age sensitivity admits 364, while 1,327 states exceed five seconds on at least one leg. All gross/depth/minimum/fee gates remain zero. See [Gate B checkpoint 003](VERITAS_MISSION2_GATE_B_CHECKPOINT_003.md).

The 04:15 UTC Research Director cycle admitted scan 49 to Arena. Its 49/49 child completed with all five economic gates at zero and complete empty candidate evidence and replay. The Director manifest still projects QUEUED even though the job record is complete; scan 48 remains its last qualified scan. The next scheduled cycle at 04:45 UTC is the reconciliation point. See [Gate F checkpoint 031](VERITAS_MISSION2_GATE_F_CHECKPOINT_031.md).

The finalized-source analyzer caught up at 04:13 UTC: 5,206/5,206 segments, zero pending bytes, 351,524 valid states over 87 markets, and zero positive top-ask/full-depth states. The separate gap-detail prefix remains incomplete at 2,417/5,194 replayable segments, with 435 campaign-window resynchronization events across 15 market IDs.

The source-only dashboard route still targets artifact 003/H105 and remains uncommitted and undeployed. The pilot remains at 18/48 scans. No service, collector, pilot, or frozen campaign was modified.

## Latest checkpoint — 2026-10-16T04:12:21Z, scan 49, Gate E v4 experiment, and gap-index progress

The scheduled scan-48 Arena experiment completed 48/48 events and compared the unchanged top-ask baseline with the depth/minimum/fee-aware qualification rule. Both had zero positive states; complete candidate evidence and zero-row independent replay were recorded. This is an end-to-end economic qualification experiment, not a strategy-P&L test. See [Gate E checkpoint 001](VERITAS_MISSION2_GATE_E_CHECKPOINT_001.md) and [Gate F checkpoint 030](VERITAS_MISSION2_GATE_F_CHECKPOINT_030.md).

The observer finalized scan 49 (scan-20261016T040030Z-56b893816f32) at 04:00:30 UTC: 40 selected markets, 31 valid pairs from a 298-ID union (127 eligible, 171 excluded), and zero positive gross/depth/minimum/fee states. It is outside coverage artifact 003 and awaits the next scheduled Director cycle.

The active pilot remains at 18/48 scans with 588/720 valid slots over 434 selected IDs; rotating yield is 567/666 and control yield is 21/54, descriptive and nonrandomized. The fixed stop is 19:00:55 UTC.

The source analyzer's latest sealed prefix is 5,125/5,147 segments and 342,943 valid states across 81 markets, with 22 segments pending and no positive top-ask/full-depth states. The gap-detail service completed its 04:05 UTC batch successfully, advancing to 2,417/5,196 segments, with 435 campaign-window resynchronization gaps across 15 market IDs and 2,777 segments / 762,500,134 bytes pending. Both source and gap analyses are partial; neither reads active segments.

The source-only coverage route update validates artifact 003 against H105. The latest recorded focused API/coverage test result is 26 passed, with Ruff, formatting, strict Mypy for the API module and diff checks passed. The route is not deployed. No collector, pilot or frozen campaign was modified.

# Veritas Mission 2 Engineering Checkpoint

## Previous checkpoint — 04:02 UTC, scan 49 and scan-48 qualification

The offline A1 coverage replay verified all 48 saved snapshots and retained
Gamma/CLOB evidence hashes across 31,353,007 compressed bytes. Its bounded
union contains 5,903 Gamma IDs, 2,135 eligible IDs, and 849 selected IDs;
1,660/1,920 selected observations pass current replay quality checks. It found
zero positive top-gross pairs. The first-scan capture/replay count mismatch
(5 stored versus 32 replayed valid pairs) remains disclosed. See [Gate A
checkpoint 045](VERITAS_MISSION2_GATE_A_CHECKPOINT_045.md) and [coverage
artifact 003](VERITAS_MISSION2_MARKET_UNIVERSE_COVERAGE_003.json).

The 03:45 Research Director cycle admitted scan 48 to Arena. Its bounded child
completed all 48 events at 03:46 UTC. All five economic qualification gates
remain zero, candidate evidence is complete and empty, and candidate replay
is complete with zero rows. The child result awaits the next scheduled Director
reconciliation. See [Gate F checkpoint
030](VERITAS_MISSION2_GATE_F_CHECKPOINT_030.md).

The observer finalized scan 49 at 04:00:30 UTC, after coverage artifact 003's
48-snapshot cutoff. Scan 49 selected 40 markets, with 31 quality-valid pairs
from a 298-ID union (127 eligible and 171 excluded). All positive economic
gates remain zero. The independent raw-source audit and A1 coverage artifact
remain at scans 47 and 48 respectively; scan 49 is reported as a separate
observation pending the next Director cycle.

The active 24-hour pilot is now 18/48 scans: 588/720 valid selected slots
over 434 distinct IDs, with one skipped sequence after the scan-45 code-hash
mismatch. Rotating yield is 567/666 and frozen-control yield is 21/54; the
comparison remains descriptive and nonrandomized. The fixed stop is
19:00:55 UTC.

The latest finalized-source summary, generated at 03:44:33 UTC, covers
5,125/5,147 segments and 1,324,261,380 processed bytes; 22 segments /
5,883,267 bytes remain pending. It reports 342,943 quality-valid states over
81 markets and zero positive top-ask, full-depth, or minimum-notional states.
The separate gap-detail index, generated at 03:51:18 UTC, covers 2,289/5,165
replayable segments and 548,436,826 processed bytes, with 2,876 segments /
786,842,920 bytes pending. Its partial prefix contains 373 campaign-window
book-resynchronization events across 11 markets. Neither analysis read an
active source segment.

The dashboard coverage route now points to artifact 003 and validates its
H105 ledger receipt and artifact-file digest. The focused API and coverage
tests passed 26 tests; Ruff, formatting, strict Mypy for the changed API
module, and git diff checks passed. This source change is not deployed. See
[Gate G checkpoint 013](VERITAS_MISSION2_GATE_G_CHECKPOINT_013.md). No
service, collector, pilot, or frozen campaign was modified.

## Previous checkpoint — 03:37 UTC, scheduled gap detail and browser verification

The 03:35 scheduled gap-detail batch exited successfully and advanced the
finalized-only prefix to 2,161/5,137 cataloged segments, with 2,974 segments /
810,593,712 bytes pending and 311 campaign-window gaps across 11 markets. The
prefix is partial. The source analyzer's last summary remains at 4,997/5,089
segments and 331,241 quality-valid states across 77 markets, with no positive
gross gates. See [Gate C checkpoint
013](VERITAS_MISSION2_GATE_C_CHECKPOINT_013.md).

The Veritas browser workflow passed one isolated Playwright test, including
the attribution card and hash-validated artifact route. The temporary API and
Vite servers exited after the test; the hosted dashboard remains unchanged.
See [Gate H checkpoint
001](VERITAS_MISSION2_GATE_H_CHECKPOINT_001.md). Mission 2 and Gate H remain
active.

## Gate G implementation checkpoint — 03:29 UTC, gap-attribution projection

The read-only dashboard now validates and summarizes the new frozen-campaign
gap-censor attribution artifact, checks row counts against its digest-protected
aggregates, links to the bounded full artifact, and preserves the temporal vs.
causal distinction. The current saved artifact has 339 gap-labeled follow-ups
among 40,075 scanned; 45 rows have a preceding same-market candidate link,
representing six unique indexed gaps. The gap-detail index is partial at
1,919/5,079 processed segments with 3,158 segments / 862,240,407 bytes
pending. Source verification covers 157 references over 133 finalized
segments; no active source segment was read. The read-only SQLite hash chain
was not reverified. See [Gate G checkpoint
012](VERITAS_MISSION2_GATE_G_CHECKPOINT_012.md).

The focused dashboard API suite passed 23 tests, the Veritas browser test
passed, and Ruff, strict Mypy, ESLint, Prettier, TypeScript typecheck, and the
production build passed. The build retains its large-chunk advisory. This
change is source-only and has not been deployed. No service or research job
was changed, and no host telemetry was refreshed.

### Scheduled source-analysis follow-up — 03:21 UTC

The scheduled 03:20 gap-detail run exited 0 and advanced its finalized-only
prefix to 2,037/5,108 segments, with 251 campaign-window book-resynchronization
events across 11 markets. The indexed prefix remains incomplete at 3,069
segments / 836,081,401 bytes pending. The primary source analyzer remains at
4,997/5,089 segments and 331,241 quality-valid states over 77 markets, with
zero positive top-ask or full-depth gross states. The 03:10 attribution
artifact remains a separate, older 1,919-segment prefix snapshot; a later
version should be generated as a new artifact rather than rewriting it. See
[Gate C checkpoint 012](VERITAS_MISSION2_GATE_C_CHECKPOINT_012.md).

## Previous checkpoint — 03:12 UTC, scan 47 and gap attribution

The latest v4 panel has 47 snapshots, 1,880 selected pair observations,
1,628 quality-valid states, 835 distinct selected markets, and zero candidate
events. The independent source audit covers the first 46 snapshots: it
reproduced all 1,600 v4 validity decisions and top edges with zero mismatches,
and found no positive top-pair gross candidate or positive full-depth,
minimum, or fee-sensitive result at 5, 10, 20, 50, or 100 shares per leg.
Its conservative reported-timestamp sensitivity admits 349 pairs; 1,251 have
at least one reported book age above five seconds. This does not establish
sequence freshness or fills. See [Gate B checkpoint
001](VERITAS_MISSION2_GATE_B_CHECKPOINT_001.md) and the [audit
artifact](VERITAS_MISSION2_INDEPENDENT_OPPORTUNITY_AUDIT_001.json).

The separate market-constraint audit compared both stored book legs for all
1,840 observations: Gamma USDC minimum values and CLOB share minimum values
were numerically equal in all 3,680 comparisons, as were tick values. The
artifact explicitly keeps their units distinct. Focused verification passed
77 tests; Ruff, formatting, strict Mypy on nine changed source files, and
`git diff --check` passed. No full regression or model training was run.

At 03:02 UTC, scan 47 selected 40 markets; 28 passed quality checks. Its
bounded discovery union had 293 IDs, 116 eligible pairs, and 177 exclusions.
It had zero positive top-gross, full-depth, minimum, or fee-sensitive states.
The fixed pilot is 16/48 scans with 525/640 valid slots across 388 IDs and one
skipped sequence after a scan-45 code-hash mismatch. The pilot remains
unchanged and ends at 19:00:55 UTC.

The refreshed offline A1 audit verifies all 46 saved snapshots and their
Gamma/CLOB response hashes. The bounded six-frame union contains 5,784 unique
Gamma market IDs and 2,115 eligible at least once; 820 IDs were selected for
paired observation. Relative to the prior 40-scan report, this adds 465
distinct discovered IDs and 38 eligible IDs, while the selected panel adds
79 IDs. Each of the six frames still has a conditional marginal contribution
to unique eligible IDs. One legacy capture-versus-current-replay counter
mismatch remains on the first scan (5 stored versus 32 replayed valid pairs);
it is preserved as a versioned schema discrepancy. No HTTP call or live
collection was used for this refresh. See [Gate A checkpoint
044](VERITAS_MISSION2_GATE_A_CHECKPOINT_044.md) and the [46-scan coverage
artifact](VERITAS_MISSION2_MARKET_UNIVERSE_COVERAGE_002.json).

The last completed finalized-source summary covers 4,869/5,029 segments,
1,261,406,393 processed bytes, 318,568 quality-valid states across 77 markets,
and zero positive gross/depth states; 160 segments / 39,330,180 bytes remain.
The 03:05 scheduled gap-detail batch advanced the separate prefix to
1,919/5,079 segments and 449,729,433 processed bytes, leaving 3,158 /
862,240,407 bytes pending. It now indexes 194 campaign-window book
resynchronization gaps across ten markets. The new read-only censor join found
45 indirect same-market temporal candidates among 160 `book_issue:gap` rows;
most were hours after the preceding gap, so they do not establish causality.
Another 86 indirect rows and 141 explicit gap rows point beyond the indexed
prefix. See [Gate C checkpoint
011](VERITAS_MISSION2_GATE_C_CHECKPOINT_011.md) and the [attribution
artifact](VERITAS_MISSION2_CENSOR_GAP_ATTRIBUTION_001.json). The 02:45
Director admitted scan 46; its Arena child completed 46/46 events and passed
read-only finding validation, while the Director projection awaits its
scheduled 03:15 UTC reconciliation. A 02:55 check corrected the earlier storage-directory
interpretation: the Reality recorder's configured `recordings/reality` root
is 1,309,431,325 bytes, versus 1,261,164,701 bytes at 01:18 UTC, an increase
of about 48 MB over 97 minutes. See [Gate A checkpoint
043](VERITAS_MISSION2_GATE_A_CHECKPOINT_043.md), [Gate C checkpoint
010](VERITAS_MISSION2_GATE_C_CHECKPOINT_010.md), [Gate F checkpoint
028](VERITAS_MISSION2_GATE_F_CHECKPOINT_028.md), and [inventory
057](VERITAS_MISSION2_RESEARCH_INVENTORY_057.json).

## Latest checkpoint — 03:19 UTC, 47-snapshot replay and scheduled qualification

The v4 panel contains 47 snapshots, 1,880 selected pair observations, 1,628
quality-valid states across 835 selected markets, and zero candidate events.
The independent raw audit now covers all 47 snapshots / 30,697,840 compressed
bytes. It reproduced all 1,628 v4 validity decisions and top edges with zero
mismatches. It found no positive gross, full-depth, per-leg-minimum, or
fee-sensitive state at 5, 10, 20, 50, or 100 shares per leg. Its conservative
reported-timestamp filter admits 353 states; 1,275 have at least one reported
book age above five seconds. This is not venue sequence or fill evidence. See
[Gate B checkpoint 002](VERITAS_MISSION2_GATE_B_CHECKPOINT_002.md) and the
[audit artifact](VERITAS_MISSION2_INDEPENDENT_OPPORTUNITY_AUDIT_002.json).

At 03:02 UTC, scan 47 selected 40 markets; 28 passed quality checks. Its
bounded discovery union had 293 IDs, 116 eligible pairs, and 177 exclusions.
The unchanged pilot is 16/48 scans with 525/640 valid slots across 388 IDs and
one skipped sequence after the scan-45 code-hash mismatch. It remains
unchanged and ends at 19:00:55 UTC.

The offline A1 coverage report still covers 46 saved snapshots. Its six-frame
union contains 5,784 Gamma IDs, 2,115 eligible at least once, and 820 selected
IDs. Scan 47's 293-ID union is recorded separately; neither is a venue census.
The first-scan legacy capture-versus-replay discrepancy (5 stored versus 32
current-replay valid pairs) remains disclosed. See [Gate A checkpoint
044](VERITAS_MISSION2_GATE_A_CHECKPOINT_044.md).

The last completed finalized-source summary, generated at 03:14:52 UTC,
covers 4,997/5,089 segments and 1,292,353,290 processed bytes; 92 segments /
23,048,067 bytes remain. It reports 331,241 valid states and no positive
top-ask or full-depth states. The separate gap-detail prefix last completed
at 03:06 UTC with 1,919/5,079 segments and 194 campaign-window gaps across
ten markets. The censor join found 45 weak temporal candidates among 160
`book_issue:gap` rows; it does not establish causality. See [Gate C checkpoint
011](VERITAS_MISSION2_GATE_C_CHECKPOINT_011.md).

The scheduled 03:15 Director cycle reconciled scan 46 and admitted scan 47.
Arena completed 47/47 events at 03:15:46 UTC with all five positive gates at
zero and complete empty candidate replay. The persisted Director projection
still shows `QUEUED` / scan 46 as last qualified; its next timer is 03:45:19
UTC. See [Gate F checkpoint 029](VERITAS_MISSION2_GATE_F_CHECKPOINT_029.md).

The latest host and service measurements remain the read-only 02:59 snapshot;
only the user timer list was inspected afterward. No health probe or manual job
API poll was made. See [operations checkpoint](VERITAS_MISSION2_OPERATIONS.md)
and [inventory 058](VERITAS_MISSION2_RESEARCH_INVENTORY_058.json).

## Previous runtime update — 01:51 UTC, scan 44 and bounded source catch-up

The observer completed scan 44 at 01:30:14 UTC: 35/40 pairs passed quality,
the six-page union contained 300 IDs / 204 currently eligible pairs, and all
gross/depth/minimum/fee counts were zero. The 44-snapshot panel has 1,534/1,760
quality-valid states and 798 selected IDs. The fixed pilot is at 14/48 scans,
464/560 valid slots, 348 selected IDs, and zero skipped sequences.

The scheduled Director admitted scan 44 to Arena. The child completed 44/44
events, and the read-only finding validator accepted its source revision,
finding digest, complete empty candidate evidence, and complete empty replay.
All five gates remain zero. The Director manifest still projects the completed
child as `QUEUED` until its next scheduled reconciliation at about 02:15 UTC.
See [Gate A checkpoint 042](VERITAS_MISSION2_GATE_A_CHECKPOINT_042.md) and
[Gate F checkpoint 027](VERITAS_MISSION2_GATE_F_CHECKPOINT_027.md).

The finalized-source analyzer at 01:44 UTC covers 4,613/4,910 segments,
296,396 quality-valid states across 72 markets, and zero positive economic
states; 297 segments / 72,605,628 bytes remain. The gap-detail timer was
staggered to :05, :20, :35, and :50 UTC without changing its per-run bounds.
Its :35 and :50 batches both exited 0, processing 244 segments / 61.0 MB in
total. The gap prefix is now 1,316/4,931 segments, with 3,613 / 990,355,252
bytes pending and 1,973 all-period events. Its campaign-window count remains
incomplete. See [Gate C checkpoint
008](VERITAS_MISSION2_GATE_C_CHECKPOINT_008.md) and [inventory
054](VERITAS_MISSION2_RESEARCH_INVENTORY_054.json).

## Previous Gate A checkpoint — scan 43 and interim pilot yield

The scheduled observer completed scan 43 at 01:01:47 UTC and exited 0. It
found 32/40 quality-valid pairs, with 300 distinct IDs in its six-page
bounded union and 202 currently eligible pairs. No positive gross candidate
appeared, and all five tested quantities had zero positive full-depth,
minimum-notional, and fee-sensitive states. Across 43 snapshots the v4
summary has 1,499/1,720 quality-valid states, 784 selected market IDs, and
zero candidate events. The descriptive fixed pilot was at 13/48 scans and
429/520 valid slots, with no skipped sequence. Scan 43 awaited the scheduled
Research Director cycle. See [Gate A checkpoint 041](VERITAS_MISSION2_GATE_A_CHECKPOINT_041.md)
and [inventory 052](VERITAS_MISSION2_RESEARCH_INVENTORY_052.json).

## Latest Gate F checkpoint — scan 44 qualification and source catch-up

Scan 44 was admitted by the scheduled Director at 01:45 UTC. Arena child
`job-c8a59c778af54704895630a9` completed 44/44 events with exit status 0;
the read-only validator accepted finding
`veritas-qualification-v1-262313565b399a77`, experiment digest, source
manifest, complete empty candidate evidence, and complete empty replay. All
five economic gates remain zero over 1,534/1,760 quality-valid states and 798
selected IDs. The Director projection remains `QUEUED` until its next cycle.
See [Gate F checkpoint 027](VERITAS_MISSION2_GATE_F_CHECKPOINT_027.md) and
[H091](VERITAS_RESEARCH_LEDGER.json).

## Previous Gate F checkpoint — scan 43 qualification and source catch-up

The scheduled Director admitted scan 43 to Arena at 01:15 UTC. Child
`job-4653ecaf1d5d457f8530c8bc` completed all 43 events with exit status 0;
the read-only finding validator accepted its source hash, digest, scan
identity, complete empty candidate evidence, and complete empty replay. All
five economic gates remain zero over 1,499/1,720 quality-valid states and 784
selected IDs. The Director manifest still awaits the next scheduled
reconciliation at 01:45:26 UTC. The finalized-source analyzer now covers
4,485/4,851 segments, 286,617 valid states across 72 markets, and zero
positive states. See [Gate F checkpoint 026](VERITAS_MISSION2_GATE_F_CHECKPOINT_026.md)
and [inventory 052](VERITAS_MISSION2_RESEARCH_INVENTORY_052.json).

## Previous Gate F checkpoint — scan 42 qualification and source catch-up

The scheduled Research Director admitted scan 42 to Arena at 00:45 UTC.
Child `job-aa54e348ab8347b3b1771479` completed all 42 source events with exit
status 0; its 2.7-second run produced finding
`veritas-qualification-v1-d6329d3c4c93c779`. The read-only finding validator
accepted the finding and its experiment digest, and the job source-manifest
hash matches the submitted source revision.

The result covers 1,467/1,680 quality-valid pairs across 760 selected market
IDs and 42 repeated snapshots. The unchanged top-ask baseline and the
depth/minimum-aware qualification each have zero positive states. Full-depth,
per-leg-minimum, single-match-fee, and fragmentation-safe-fee gates are also
zero; the complete candidate evidence set is empty and its empty source
replay is marked complete. The maximum edge is -$0.001/share and median is
-$0.020/share. This is a qualification experiment, not strategy P&L or
independent market confirmation.

Arena completed the child, but the Director manifest still reports its
current job as `QUEUED` and its last qualified scan as scan 41. The manifest
was last updated during admission at 00:45:28 UTC. The next scheduled
Director cycle is 01:15:26 UTC; no manual reconciliation, retry, or duplicate
admission was made.

The 00:43 source summary covers 4,357/4,791 finalized segments and 278,820
quality-valid campaign-window states across 68 markets, with zero positive
gross or deeper economic states. The 00:51 gap-detail summary covers
944/4,812 catalog segments and 1,793 all-period gap events. Its last retained
event is 16:08 UTC, before the campaign window starts at 21:07 UTC, so the
campaign-window gap count remains incomplete. Both one-shots exited
successfully and were inactive at 00:52 UTC. See [Gate F checkpoint
025](VERITAS_MISSION2_GATE_F_CHECKPOINT_025.md), [inventory
050](VERITAS_MISSION2_RESEARCH_INVENTORY_050.json), and [H088](VERITAS_RESEARCH_LEDGER.json).

## Previous Gate A checkpoint — isolated eight-read discovery successor

The separate `discovery-successor-001` implementation began in `52342dc` and
was hardened in `70144d9`. It retains all six Gamma discovery frames and the
batched CLOB books read, adds one direct lookup for the frozen control IDs,
and produces eight logical reads on a complete scan. It uses its own
non-overlapping artifact root, applies strict control identity checks, rejects
even dangling symlink roots, and refuses to run before the fixed pilot stop.
Focused successor, observer, and control tests passed (19); Ruff, Ruff format,
strict Mypy, and diff checks passed. No live successor scan, service/timer
change, or deployment was made. See [Gate A checkpoint
040](VERITAS_MISSION2_GATE_A_CHECKPOINT_040.md), [checkpoint
039](VERITAS_MISSION2_GATE_A_CHECKPOINT_039.md),
[H086–H087](VERITAS_RESEARCH_LEDGER.json), and [inventory
049](VERITAS_MISSION2_RESEARCH_INVENTORY_049.json).

At 00:32 UTC the unchanged v1 observer completed scan 42 with 29/40
quality-valid pairs, 300 unique bounded discovery IDs, 116 eligible IDs, and
zero positive gross or economic states. Across 42 snapshots, 1,467/1,680
selected pairs pass current v4 quality checks, with zero positive candidates
at any displayed gross, depth, minimum, or fee gate. The fixed pilot has
12/48 scans, 397/480 valid slots across 299 IDs, and no skipped sequences;
it remains descriptive and ends at 19:00:55 UTC. These are intermittent
public observations, not a venue census, execution record, or profitability
result.

The saved source replay through 00:14 UTC covers 4,242/4,733 finalized
segments, with 268,179 quality-valid states across 67 markets and zero
positive top-gross or deeper economic states. The gap-detail extractor through
00:21 UTC covers 908/4,753 catalog segments and has not reached the campaign
window. The 00:32 observer run exited successfully; source, gap-detail, and
Director one-shots were inactive at capture. Reality recorder, shadow, and
Midas web/API services reported active. See [inventory 048](VERITAS_MISSION2_RESEARCH_INVENTORY_048.json)
for resource measurements and saved-summary times.

## Previous Gate G checkpoint — bounded market-coverage dashboard projection

The read-only overview exposes the H084-digest-pinned A1 coverage report.
Its API verifies the report against the ledger receipt and validates internal
counts before projecting the summary. The Market Discovery panel shows the
audited IDs, identities, current v4 quality pairs, metadata bands, the
capture/replay count difference, and bounded-query limitations. The saved
artifact covers 40 scans through scan 40; it is not a venue-wide coverage
estimate. API tests (21), coverage-audit tests (2), the targeted UI test (1),
Ruff, strict Mypy, ESLint, Prettier, TypeScript, and diff checks passed. The
source change is committed at `73b695f` and is not deployed. See [Gate G
checkpoint 011](VERITAS_MISSION2_GATE_G_CHECKPOINT_011.md) and [inventory
047](VERITAS_MISSION2_RESEARCH_INVENTORY_047.json).

The preceding checkpoint recorded scan 41 at 00:02:15 UTC with 33/40
request/receipt-quality-valid pairs and zero positive gross or economic
states. The pilot then had 11/48 scans, 368/440 valid selected pairs across
282 selected IDs, and no missed scan sequences.

## Latest Gate A checkpoint — digest-verified market coverage

An offline A1 audit now summarizes the 40 saved six-frame public discovery
scans from 05:59:28 to 23:32:05 UTC. All 240 Gamma page responses, 40 CLOB
responses, and 40 snapshot evidence digests verified. The observed bounded
unions contain 5,319 distinct market IDs and 2,077 IDs eligible at least once;
the report explicitly does not estimate venue-wide coverage. Current v4
replay finds 1,405 quality-valid selected pairs and zero positive top-gross
pairs across 1,600 slots. It records the one scan-1 counter difference
against the v1 capture field, which matches the legacy freshness count. See
[Gate A checkpoint 038](VERITAS_MISSION2_GATE_A_CHECKPOINT_038.md), the
[coverage artifact](VERITAS_MISSION2_MARKET_UNIVERSE_COVERAGE_001.json), and
[inventory 046](VERITAS_MISSION2_RESEARCH_INVENTORY_046.json). Gate A and
Mission 2 remain active; the Reality collector and fixed pilot were not
changed.

The scan-40 Arena child also completed all 40 events with exit status 0,
complete empty candidate evidence, and zero states at all five economic
gates. Its Director projection remains queued for the scheduled 00:15:04 UTC
reconciliation. See [Gate F checkpoint
024](VERITAS_MISSION2_GATE_F_CHECKPOINT_024.md).

## Previous engineering checkpoint — Director recovery and scan 40

The scheduled observer completed scan 40 at 23:32:05 UTC with 30/40
request/receipt-quality-valid pairs, 291 unique IDs in the bounded discovery
union, 77 eligible markets, and no positive top-gross pair. The measurement
pilot has 10/48 scans, 335/400 valid selected slots, 271 selected IDs, and no
missed scan sequences. Arena completed the scan-39 qualification with all
39/39 events, 1,375 quality-valid pairs across 732 IDs, and zero positives at
all five economic gates. The Director manifest awaits its scheduled
reconciliation. See [Gate A checkpoint
037](VERITAS_MISSION2_GATE_A_CHECKPOINT_037.md) and [Gate F checkpoint
023](VERITAS_MISSION2_GATE_F_CHECKPOINT_023.md).

The Research Director now recovers a missing job pointer only when its
canonical scan-keyed admission resolves to exactly one durable, matching
child. If no such evidence exists, it keeps the scan `UNVERIFIED` and does not
admit a replacement. Ten focused Director tests, Ruff, format, strict Mypy,
and diff validation passed. The current scan-39 child record was present and
completed; the stale-pointer behavior is a tested recovery path, not a
confirmed live incident. See the [versioned recovery
artifact](VERITAS_MISSION2_DIRECTOR_RECOVERY_001.json) and [ledger
H083](VERITAS_RESEARCH_LEDGER.json).

The frozen Reality campaign, collector, pilot protocol, and active jobs were
not modified or restarted. The scheduled Director will reconcile the
completed scan-39 child on its next cycle and may then admit scan 40 under the
same bounded policy.

## Previous engineering checkpoint — discovery-frame marginal value

An offline replay verified all 234 Gamma response hashes across 39 saved scans.
The six frames average 299.05 unique IDs and 164.26 V1-eligible markets.
Removing a frame loses about 49–50 unique IDs on average, so I am not cutting
one to fund control lookup. The new successor design tests one additional
bounded request while preserving all six discovery frames. See [Gate A
checkpoint 036](VERITAS_MISSION2_GATE_A_CHECKPOINT_036.md), the [frame-marginal
artifact](VERITAS_MISSION2_DISCOVERY_FRAME_MARGINAL_001.json), [research ledger
H082](VERITAS_RESEARCH_LEDGER.json), and [inventory
044](VERITAS_MISSION2_RESEARCH_INVENTORY_044.json).

## Previous engineering checkpoint — direct control retrieval

A one-request explicit-ID Gamma diagnostic returned all eight frozen controls
about 11 minutes after scan 39. Three controls absent from that scan's six-query
union were open and eligible in the direct response; two other absent controls
were returned with `closed=true`. This confirms that bounded-frame absence
must remain distinct from lifecycle status. The v1 pilot remains unchanged;
the diagnostic is a separate versioned probe and contains no book or economic
observations. See [Gate A checkpoint 035](VERITAS_MISSION2_GATE_A_CHECKPOINT_035.md),
[research ledger H081](VERITAS_RESEARCH_LEDGER.json), and [inventory
043](VERITAS_MISSION2_RESEARCH_INVENTORY_043.json).

## Latest engineering checkpoint — scan 39 and source-lag diagnosis

The scheduled observer completed scan 39 at 23:00:55 UTC. Six bounded queries returned 300 unique IDs; 174 met the supported same-condition pair rule and 126 were excluded. Thirty-four of 40 selected pairs passed the request/receipt quality gate; six had an empty ask side. The raw snapshot reports zero positive top-gross, depth, minimum, and fee-sensitive counts at all five quantities. Its scan-pinned v3 qualification has not yet run. The 24-hour pilot now has nine scans, 305/360 quality-valid pairs across 257 selected IDs, and no missed scan sequences. The latest control diagnostic verifies 3/8 frozen controls selected; five were absent from the bounded query union. See [Gate A checkpoint 034](VERITAS_MISSION2_GATE_A_CHECKPOINT_034.md), [Gate G checkpoint 010](VERITAS_MISSION2_GATE_G_CHECKPOINT_010.md), and [inventory 042](VERITAS_MISSION2_RESEARCH_INVENTORY_042.json).

A read-only throughput sample now identifies a binding resource cap in the frozen Reality shadow worker. Over 23.1 seconds the recorder advanced 84 ordinals (31 frames) while the worker advanced 21 records and skipped 21 lagged frames. The worker's cgroup used 2.006 CPU seconds under a 100 ms/s quota; all 201 observed CFS periods were throttled. Its digest-verified runtime cursor is 165,712 ordinals behind the recorder at capture, with about 299 MB of later source files pending. The code consumes records in order and suppresses new decisions when frame input exceeds its frozen 250 ms limit. This evidence supports CPU-budget-limited catch-up; it does not justify changing or restarting the active campaign. See [Gate C checkpoint 005](VERITAS_MISSION2_GATE_C_CHECKPOINT_005.md) and [the lag diagnostic](VERITAS_MISSION2_SHADOW_LAG_DIAGNOSTIC_001.json).

At 23:03 UTC the recorder status was `RECORDING_UNSEQUENCED`, still carried one DNS resolution failure and 3,578 gap markers, and had a fresh observation timestamp; 16/16 books were flagged fresh and none timing-uncertain. Sequence continuity remains unverified. The shadow remains `WARMING_OR_LAGGED_SOURCE`; its latest decision is from 08:58 UTC. The source analyzer covers 3,953/4,554 segments with 601 / 178 MB pending. The gap-detail analyzer covers 530/4,574 segments with 4,044 / 1.097 GB pending; its campaign-window count remains incomplete. Both the frozen campaign and services were left untouched.

The control-availability API and dashboard passed 18 backend tests and one frontend test. Ruff, format, Prettier, ESLint, TypeScript, and `git diff --check` passed. The code is in this branch and is not deployed to the running host. Gate A, C, F, G, and Mission 2 remain active.

## Previous dashboard update — Gate G checkpoint 008

The opportunity observatory now shows candidate events per elapsed panel
hour, explicitly describing its snapshots as intermittent, and exposes a
size-by-gate table for 5, 10, 20, 50, and 100 shares per leg. The table keeps
full-depth gross, per-leg minimum, single-match fee, and fragmentation-safe
fee counts separate and labels repeated observations as correlated states,
not opportunities or fills. For the latest 37-snapshot artifact, all five
quantities remain zero at every displayed gate. The UI test, TypeScript,
Prettier, production build, and isolated Playwright workflow passed. Vite
reported its existing large-chunk advisory. See [Gate G checkpoint
008](VERITAS_MISSION2_GATE_G_CHECKPOINT_008.md) and the prior [gap evidence
checkpoint 007](VERITAS_MISSION2_GATE_G_CHECKPOINT_007.md). Gate G and Mission
2 remain active.

## Latest Gate A/F checkpoint — scan 37 and scheduled replay

The 37-snapshot public panel contains 1,307 quality-valid pairs across 689
selected market IDs and no positive top-gross, full-depth, minimum-notional,
or fee-qualified state. Its latest Arena qualification completed all 37
events, compared the unchanged top-ask baseline against depth- and
minimum-aware qualification, and produced complete empty candidate evidence
and replay. The paired request/receipt gate accepts 1,307 of 1,480 states,
compared with 290 under the legacy reported-age gate (+1,017; +68.72 points).

The prospective coverage pilot has seven scans / 280 selected slots / 237
quality-valid pairs; its role split is nonrandomized and descriptive. The
primary source analyzer covers 3,852/4,496 segments and 221,768
campaign-window quality-valid states across 63 markets. The supplemental gap
index covers 402/4,514 segments and has not yet reached the campaign window.
See [Gate A checkpoint 033](VERITAS_MISSION2_GATE_A_CHECKPOINT_033.md), [Gate
F checkpoint 022](VERITAS_MISSION2_GATE_F_CHECKPOINT_022.md), and [inventory
040](VERITAS_MISSION2_RESEARCH_INVENTORY_040.json). Gate A and Gate F remain
active.

## Latest engineering checkpoint — Gate C censoring and exact source audit

The current bounded v1.4 read-only forensic snapshot covers 10,253 decisions,
43 markets, and 37 connected families. It records 3,503 valid initial states,
937 public markouts, 40,075 censored horizon slots, and zero pending horizons.
Most censor rows are invalid starts (27,000); the largest remaining causes are
10,233 unavailable future observations, 1,461 stale follow-up books, and 970
source-availability timeouts. A new audit verifies all 179 explicit
`recorded_gap` outcomes against 97 exact finalized source gap records. The
other 160 `book_issue:gap` outcomes remain indirect. See [Gate C checkpoint
004](VERITAS_MISSION2_GATE_C_CHECKPOINT_004.md), [censoring report
004](VERITAS_GATE_A_CENSORING_004.json), and [gap-censor audit
001](VERITAS_MISSION2_CENSOR_GAP_AUDIT_001.json).

The 24-hour coverage pilot has six scans and 202/240 quality-valid pairs
across 177 selected markets: 194/220 in its rotating cohort and 8/20 in the
nonrandomized stable controls. The separate gap-detail extractor has verified
274/4,455 nonempty finalized segments; its terminal record is pre-window and
its current zero campaign-gap count is partial while 4,181 segments remain pending.
The 21:50 batch processed 18 segments / 31.82 MB within the 32 MiB bound.
Its terminal record is at 2026-10-14 10:24:24.977 UTC. Preserve its pinned
code and cursor while it catches up. The
scheduled source analyzer covers 3,763/4,436 segments, with 210,181 valid
states across 63 markets, 1,089 campaign-window resynchronizations, one
connection failure, and zero positive gross states.

Scan 36 has 1,272/1,440 quality-valid pairs across 665 selected IDs and zero
positive gross or economic gates. Its scan-pinned Arena job completed all 36
events and the empty candidate replay; the Director manifest is pending its
next scheduled reconciliation. See [Gate C checkpoint
004](VERITAS_MISSION2_GATE_C_CHECKPOINT_004.md), [Gate A checkpoint
032](VERITAS_MISSION2_GATE_A_CHECKPOINT_032.md), and [Gate F checkpoint
021](VERITAS_MISSION2_GATE_F_CHECKPOINT_021.md).

## Previous engineering checkpoint — Gate G frozen label-feasibility visibility

The dashboard now exposes the frozen-campaign v1.4 label-feasibility report
as a digest-verified, campaign-matched API projection, separate from the
existing v1.3 follow-up summary. The UI shows per-horizon markout counts and
the five-second target and execution support, preserving the finding that
these data do not support strategy training or establish fills/P&L. The
report covers 10,253 decisions; 473 of 3,503 valid starts have a five-second
public markout, all with no initial discrepancy, undefined opportunity
persistence, and unknown counterfactual execution. See [Gate G checkpoint
006](VERITAS_MISSION2_GATE_G_CHECKPOINT_006.md).

Focused verification passed: 15 dashboard API tests, one Veritas UI test,
Ruff, strict Mypy for the API module, Ruff formatting, Prettier, and TypeScript
typecheck. The API test runner emitted one Starlette/httpx deprecation warning.
The subsequent production build passed at 20:29 UTC; Vite repeated its large
bundle advisory (501.86 kB main bundle, 544.41 kB Chart chunk). No full
regression suite, deployment, or service restart was run. Mission 2 remains
active.

## Previous evidence checkpoint — Gate A scan 33 and recorder continuity audit

At 20:05 UTC, scan 33 completed with 31/40 selected pairs quality-valid. The
cumulative panel has 1,167/1,320 valid pairs across 616 selected market IDs,
153 invalid pairs, and zero positive top-gross pairs; the best edge remains
-$0.001/share. The 24-hour rotating-coverage pilot has three scans, 97/120
valid pairs, and no skipped scan sequences. Its comparison remains descriptive
because only three of nine selected control slots were available. See [Gate A
checkpoint 029](VERITAS_MISSION2_GATE_A_CHECKPOINT_029.md).

A read-only segment metadata audit found 1,790 finalized Reality `.seg` files
with mtimes at or after the 04:57:26 UTC DNS warning. The first followed the
warning by about eight seconds; the largest adjacent mtime gap was 36.51
seconds, and the latest file was written at 20:05:04 UTC. At 20:02 UTC the
recorder was active with zero restarts and DNS resolved. This argues against
a prolonged recording-output outage. The 20:14 source summary counted 911
`book_resynchronization` markers and one `connection_failure`; these are
reconstruction barriers, but their aggregate contains no event times or
outage durations. Feed continuity is therefore not established. See
[continuity artifact 001](VERITAS_MISSION2_RECORDER_CONTINUITY_001.json) and
[research ledger H072](VERITAS_RESEARCH_LEDGER.json).

A targeted read of the finalized segment spanning the warning matched the
single source-summary `connection_failure` to the 04:57:26.718 UTC DNS error.
The first later receiver frame appeared 2.445 seconds afterward. All 92
records in that segment passed integrity checks and its file hash matched the
catalog sidecar. This does not establish full-cohort recovery or quote
freshness; see [gap-timing artifact
001](VERITAS_MISSION2_RECORDER_GAP_TIMING_001.json) and ledger H073.

The scheduled 20:14:36 UTC source-analysis run processed 128 segments / 31.48
MB in 212 seconds, using 10.618 CPU seconds and 147.7 MiB peak memory with no
swap. It is catching up at 3,388/4,260 segments, with 872 / 269,424,035 bytes
pending. The partial campaign window has 186,344 quality-valid states across
47 markets, with zero positive top-ask/full-depth states. The next source
timer is 20:40:16 UTC.

Scan 33's Arena qualification completed all 33 events successfully at
20:16:26 UTC and found zero positives at all five gates. The authoritative
job is complete, while the Director manifest still projects it as queued; the
20:45:05 UTC cycle is the reconciliation point. The manifest now reports the
corrected `NOT_READY_NO_CANDIDATE_RELEVANT_TARGET` model readiness. See [Gate
F checkpoint 019](VERITAS_MISSION2_GATE_F_CHECKPOINT_019.md). No manual poll or
restart was used.

The frozen-campaign v1.4 audit found 937 public markouts across 41,012
follow-up slots, with 40,075 censored. At five seconds, 473/3,503 valid initial
decisions have an observed markout, but all report no initial discrepancy,
null opportunity persistence, and unknown-counterfactual execution ground
truth. These are not strategy or P&L labels. The v1.4 code passed 9 focused
tests, Ruff, formatting, and strict Mypy; the artifact remains separate from
the dashboard's pinned v1.3 schema. See [Gate C checkpoint
003](VERITAS_MISSION2_GATE_C_CHECKPOINT_003.md) and [label artifact
001](VERITAS_MISSION2_LABEL_FEASIBILITY_001.json). Mission 2 remains active.

## Gate G checkpoint 005 — coverage dashboard and scan 32

Commit `a03a10c` adds a read-only coverage-pilot panel backed by a
digest- and lineage-verified API projection. Focused verification passed 12
API tests, one targeted UI test, Ruff, formatting, strict Mypy, TypeScript,
ESLint, Prettier, and the production build; the existing Vite large-chunk
advisory remains. No host deployment or service restart occurred.

The live pilot has two scans / 80 selected slots / 66 quality-valid / 14
invalid / zero missed sequences. Scan 32 selected 40 pairs from a 300-ID
bounded discovery union; 34 were quality-valid and none had positive gross.
The 32-snapshot panel contains 1,136/1,280 quality-valid pairs across 598
distinct selected IDs, zero positives at all five economic gates, and a
maximum top edge of -$0.001/share. Finalized-source analysis remains partial.
See [Gate G checkpoint 005](VERITAS_MISSION2_GATE_G_CHECKPOINT_005.md).


## Earlier operational and discovery update — Gate A checkpoint 021 / Gate F checkpoint 011

The 15:00 scheduled scan is snapshot 23. The cumulative panel has 920
selected observations, 825 request/receipt-valid pairs, 95 invalid pairs, and
418 distinct markets. The legacy reported-age/skew gate accepts 189 pairs,
for a paired recovery of 636/920 (+69.13 percentage points). All five
economic qualification gates remain zero-positive.

The 15:10 finalized-source replay processed 124 segments / 33,163,975 bytes.
Its partial prefix now covers 2,161/3,668 finalized segments and contains
70,950 campaign-window frame records, 59,343 touched states, and 57,798
quality-valid states. There are 1,507 segments / 396,434,833 bytes pending;
positive top-ask and full-depth states remain zero. The earlier source-window
interpretation correction remains documented in checkpoint 017.

The 15:15 Director cycle recorded scan 22 completion, admitted scan 23, and
Arena completed the 23-event qualification at 15:15:47 UTC. The finding
remains zero-positive. The manifest last updated at 15:15:32 UTC projects
`QUEUED` for scan 23 and retains scan 22's finding; the next scheduled poll at
15:45:00 UTC is the reconciliation point. No manual poll or retry was started.
See [Gate A checkpoint 021](VERITAS_MISSION2_GATE_A_CHECKPOINT_021.md), [Gate F
checkpoint 011](VERITAS_MISSION2_GATE_F_CHECKPOINT_011.md), [operations](VERITAS_MISSION2_OPERATIONS.md),
and [research inventory 024](VERITAS_MISSION2_RESEARCH_INVENTORY_024.json).

## Latest dashboard update — Gate G checkpoint 004

The read-only Arena activity API now returns a bounded, filename-digest-
verified history of recent Research Director events. The Veritas page exposes
scan/job/finding and experiment/dataset lineage, gate counts, and preserved
failure/recovery notes beside current strategy/model readiness. The last
read-only projection check at 12:55 UTC returned eight verified events from
the Director's then-19-file archive and zero invalid artifacts; the
source-drift failure and subsequent stable-revision qualification were both
visible. Backend, frontend, type, lint, format, build, and browser checks
passed. See [Gate G checkpoint 004](VERITAS_MISSION2_GATE_G_CHECKPOINT_004.md).

## Previous operational update — Gate F checkpoint 005

The 12:15 Director cycle completed a new 17-event qualification for the 12:01
scan on committed source revision `e78a95e2`. Its five opportunity gates
remain zero-positive. A 12:16 no-launch poll verified the finding and admitted
no second job. The 12:10 finalized-source replay advanced to 1,438/3,313
cataloged segments, with no campaign-window frames. See [Gate F checkpoint
005](VERITAS_MISSION2_GATE_F_CHECKPOINT_005.md), [operations](VERITAS_MISSION2_OPERATIONS.md),
and [research inventory 017](VERITAS_MISSION2_RESEARCH_INVENTORY_017.json).

## Previous discovery status — Gate A checkpoint 014

The 12:01 observer scan found 200 supported binary markets among 300 bounded
IDs, with 100 explicit exclusions. Thirty-five of 40 selected pairs were
quality-valid. The 17-snapshot panel has 613 valid pairs across 284 market IDs
and no positive top, depth, minimum-size, or fee-qualified states. The
Director qualification and source-replay recurrences have both completed for
this scan. See [Gate A checkpoint
014](VERITAS_MISSION2_GATE_A_CHECKPOINT_014.md), [research inventory
017](VERITAS_MISSION2_RESEARCH_INVENTORY_017.json), and
[operations](VERITAS_MISSION2_OPERATIONS.md).

## Previous operational update — Gate F checkpoint 003

The 11:15 job for the 11:01 scan failed before event processing because its
source revision changed while queued. It remains preserved at 0/1 and was not
retried. The next scheduled cycle has since completed successfully against
the stable committed revision; see [Gate F checkpoint
003](VERITAS_MISSION2_GATE_F_CHECKPOINT_003.md) and [checkpoint
004](VERITAS_MISSION2_GATE_F_CHECKPOINT_004.md).

## Previous discovery status — Gate A checkpoint 012

The bounded 11:01 observer scan found 207 eligible binary markets in 300
unique IDs. A pinned, read-only event audit verified one complete nine-outcome
NegRisk event and added replayable economics for both complete Yes and No
baskets. Both have negative gross edge and fail source timestamp age and skew
gates; neither qualifies an opportunity. The audit preserves the protocol
limitation that at-most-one Yes does not ensure at least one Yes.
See [Gate A checkpoint 012](VERITAS_MISSION2_GATE_A_CHECKPOINT_012.md),
[research inventory 015](VERITAS_MISSION2_RESEARCH_INVENTORY_015.json), and
[operations](VERITAS_MISSION2_OPERATIONS.md).

## Earlier status — Gate F checkpoint 002

The Research Director now validates and stores the separately maintained
finalized-source summary on each cycle, including its sealed digest, campaign
identity, replay counters, and economic counters. The API and Veritas activity
panel expose source readiness alongside public-snapshot qualification. A
10:56 UTC no-launch poll reused the existing completed finding, created no job,
and reported 1,072/3,136 source segments processed with no campaign-window
frames yet. See [Gate F checkpoint 002](VERITAS_MISSION2_GATE_F_CHECKPOINT_002.md),
[operations](VERITAS_MISSION2_OPERATIONS.md), and [research inventory
014](VERITAS_MISSION2_RESEARCH_INVENTORY_014.json).

## Earlier status — Gate F checkpoint 001

The recurring Veritas Research Director is enabled at :15 and :45 UTC. It
verifies a current v2 scan and finalized v4 event, admits one scan-pinned
Arena qualification job, and publishes durable readiness and finding lineage.
The first recurring cycle qualified
`scan-20261015T103110Z-b077f9c3d7be` through
`job-1bb0f47d56374e1385503362`, producing
`veritas-qualification-v1-115a375a2bd16454` over 14 events. The cumulative
panel has 507 valid pairs across 210 markets and zero positive states at all
qualification gates. The API and Veritas dashboard expose the current scan,
readiness, sample counts, and no-trade recommendation. See [Gate F checkpoint
001](VERITAS_MISSION2_GATE_F_CHECKPOINT_001.md), [operations](VERITAS_MISSION2_OPERATIONS.md),
and [research inventory 013](VERITAS_MISSION2_RESEARCH_INVENTORY_013.json).

The 10:40 UTC Reality source-analysis recurrence processed 128 finalized
segments / 30,283,274 bytes in 155 seconds (7.737 CPU seconds, 132.1 MiB peak).
The prefix now covers 1,072 of 3,136 replayable segments, with 2,064 pending
(557,814,406 bytes) through ordinal 122,759 and no campaign-window frames. The
observer, source-analysis, and Research Director timers are active. Reality
services and protected evidence were not restarted or changed. Current source
and state hashes are in [research inventory 013](VERITAS_MISSION2_RESEARCH_INVENTORY_013.json).

## Earlier status — Gate A checkpoint 011

The 10:01 UTC scheduled v2 discovery scan (`scan-20261015T100116Z-7d135306c470`)
indexed as the 13th finalized snapshot. The 300-ID bounded union contained 132
eligible binary pairs; 38 of 40 selected pairs were quality-valid, with zero
positive gross candidates. A bounded Arena qualification job consumed the 13
finalized v4 events and persisted an idempotent zero-positive finding. The
dashboard browser workflow passed. Full evidence and current limits are in
[Gate A checkpoint 011](VERITAS_MISSION2_GATE_A_CHECKPOINT_011.md).

The 10:10 UTC source-analysis recurrence also completed within its limits.
The finalized prefix is now 944/3,077 segments, with 2,133 pending and no
campaign-window frames. Reverification of all 944 sealed events matched the
rolling chain in state.

## Earlier checkpoint: paired measurement, censoring, and dashboard

The details below describe the 12-snapshot state at 09:16 UTC. The 13-snapshot
discovery and source-replay continuation is recorded at the top of this report
and in Gate A checkpoint 011.

The incremental snapshot analyzer is now at `veritas-finalized-snapshot-analysis-v4`;
v1–v3 state, summaries, and event histories are retained separately. v4 adds
per-market selected/valid counts, first and last sampled time, sampled book
fingerprint changes, and per-market/cumulative reclassification under the
previous five-second reported-age and 250 ms cross-outcome-skew gate. The
current request/receipt gate remains active. The paired result is a
measurement-yield comparison, with explicit limits around batch atomicity,
sequence freshness, and upstream queue age.

The dashboard exposes cohort strata, paired gate yield, sampled state changes,
a bounded least-covered-market table, and the frozen-campaign censoring view.
See [Gate A checkpoint 008](VERITAS_MISSION2_GATE_A_CHECKPOINT_008.md),
[Gate C checkpoint 001](VERITAS_MISSION2_GATE_C_CHECKPOINT_001.md), [Gate G
checkpoint 002](VERITAS_MISSION2_GATE_G_CHECKPOINT_002.md), [Gate G checkpoint
003](VERITAS_MISSION2_GATE_G_CHECKPOINT_003.md), and [measurement comparison
protocol 002](VERITAS_MISSION2_MEASUREMENT_COMPARISON_002.md).

**Date:** 2026-10-15
**Branch:** `project/veritas`
**Starting commit:** `9a857cc56804bec6b7129171ba090d338e263aa3`

## Architecture delivered

### Public discovery and observation

[`observatory.py`](../packages/midas/veritas/observatory.py) builds a six-frame
Gamma discovery union, retains exclusions and query lineage, selects up to 40
price-blind markets, and retrieves YES/NO books through one bounded public
CLOB `/books` call. It records immutable compressed snapshots, response hashes,
source code hashes, and a compact latest summary. The stable cohort and each
rotation are explicit; selection probabilities apply only within the bounded
query union and conditional frozen controls.

Only same-condition V1 binary pairs pass to economic arithmetic. Multi-outcome,
augmented negative-risk, ambiguous identity, and unsupported payoff semantics
are excluded with reasons. This prevents related event text from being treated
as a payoff identity.

### Independent arithmetic and quality gate

[`opportunity_audit.py`](../packages/midas/veritas/opportunity_audit.py) checks
condition/token identity, exact outcomes, market status, tick/minimum metadata,
book sides, sequence-independent pair matching, top asks, sorted depth walks,
and quantity-specific minimums. It reports independent audit arithmetic and
cross-checks fee behavior. Adversarial fixtures cover positive and negative
edges, invalid pair identities, empty sides, insufficient depth, minimums, and
fee cases.

The measurement comparison changes the freshness basis from last-reported book
update age to request-to-receipt duration for the exact response batch. Reported
book age and cross-outcome skew remain diagnostics. The analyzer labels batch
atomicity and sequence ordering unverified rather than assuming them.

### Incremental research and experiment

[`continuous_analysis.py`](../packages/midas/veritas/continuous_analysis.py)
indexes only completed immutable snapshots. It verifies snapshot identity and
analysis-event digests, uses exclusive event creation and atomic state writes,
resumes after partial work, and processes at most 100 pending snapshots per
run. Version 4 preserves v1–v3 artifacts, re-audits saved books with the
repaired gate, and adds paired legacy-gate plus per-market sampled coverage
metrics. Snapshot transitions do not estimate true venue update rates.

[`finalized_source_analysis.py`](../packages/midas/veritas/finalized_source_analysis.py)
is a separate incremental reader for the frozen Mission 2 Reality campaign. It
checks the campaign file hash and identity on each run, reads only numeric
finalized-segment catalogs and their `.seg` files, and never opens `.open`
files. It validates each new segment hash and record catalog, skips verified
empty finalized headers, and detects catalog-prefix changes behind progress
without hashing old segment payloads on every run. A restored `Context`
reconstructs source state across bounded batches. Each segment gets an
exclusive digest-sealed event before the atomic cursor/state update, so an
interrupted segment can be replayed and compared without duplicate application.
The user service limits each run to 128 segments or 32 MiB, state to 24 MiB,
and source-analysis artifacts to 256 MiB.

[`economic_experiment.py`](../packages/midas/veritas/economic_experiment.py)
compares the unchanged top-ask gross-sign baseline to full displayed depth and
both per-leg minimum checks at 20 shares. It separately counts single-match
and fragmentation-safe fee sensitivities. Event digests, snapshot evidence
hashes, scanner hashes, source event hashes, experiment source hash, and a
result digest are retained. Each input dataset gets a deterministic run ID, so
a later cumulative window creates a new immutable artifact while preserving
prior results. The artifact reports candidate qualification, not PnL.

### API and dashboard

[`apps/api/veritas.py`](../apps/api/veritas.py) adds bounded reads for the
continuous-analysis summary and latest scan, a continuous-analysis artifact,
validated snapshot route, and a separate finalized-source summary and artifact.
It validates summary digests and scan IDs, applies compressed and decompressed
byte bounds, and remains read-only.

[`Veritas.tsx`](../apps/web/src/Veritas.tsx) and
[`veritas.css`](../apps/web/src/veritas.css) add market-discovery and cohort
strata, scan/coverage counts, data quality, concentration, edge and candidate
counts, readiness, paired old/new measurement yield, sampled market-state
transitions, least-covered markets, and immutable snapshot links. Zero
candidates are displayed directly. The page shows finalized Reality replay
progress in its own panel, separate from intermittent public snapshots and
realized execution.

### Gate C censoring analysis and Gate G dashboard

The v1.3 forward-forensics report reads one SQLite transaction from the active
frozen campaign using `mode=ro` and `PRAGMA query_only=on`. It groups outcomes
by market, decision UTC hour, frozen horizon, initial observation-quality
regime, and censor mechanism. An absent outcome row remains pending; it is not
counted as a censor. The 08:44 UTC snapshot covers 10,165 decisions and 40,660
horizon slots: 930 public measurements, 39,730 censors, and zero pending rows.
It includes 168 market/horizon groups, 48 hour/horizon groups, and 32
initial-quality/horizon groups. The full artifact is
[`VERITAS_GATE_A_CENSORING_003.json`](VERITAS_GATE_A_CENSORING_003.json),
SHA256 `4e7d8d2bde0cda1afdc5876de2fbc31c3a54219b95d9baba0bfbfeed454b9b72`.

The API validates campaign identity and count reconciliation before using the
report for follow-up yield. The dashboard shows horizon yields, up to 20
markets and 24 UTC-hour rows at the longest horizon, mechanism totals, and a
link to the full bounded artifact. `future_observation_unavailable` remains
ambiguous: the frozen worker records it after the horizon deadline passes
without a qualifying synchronized future book, without proving venue
inactivity or identifying every feed-selection gap. This audit did not replay
the complete event hash chain or run a full SQLite integrity scan.

Verification already recorded for this code set: 88 Veritas backend tests, 29
frontend tests, Ruff, strict Mypy, frontend lint/typecheck/format/build, and the
Veritas Playwright workflow passed. The production build retains its existing
large-chunk advisory. See [Gate C checkpoint
001](VERITAS_MISSION2_GATE_C_CHECKPOINT_001.md) and [Gate G checkpoint
003](VERITAS_MISSION2_GATE_G_CHECKPOINT_003.md).

### Recurring operation

The observer and snapshot analyzer run every 30 minutes on the existing user
timer. A separate offset timer advances finalized Reality source replay every
30 minutes under its own CPU, memory, byte, and segment limits. Neither
pipeline duplicates Reality's recorder or alters the frozen campaign. Both
timers and services are active and checked in under
[`deploy/systemd/user`](../deploy/systemd/user).

The two read-only analysis cycles advance independently: the snapshot cycle
indexes each newly finalized public scan, while the source cycle replays a
bounded finalized Reality prefix and resumes from its saved context. The API
exposes distinct readiness and source evidence for each. Neither launches an
Arena job or trains a model. With zero gross candidate labels, a strategy
tournament or predictor comparison would not be an evidence-supported
experiment.

## Runtime and evidence at checkpoint

- Latest scan: `scan-20261015T090047Z-6f98ffeaecab`, captured 09:00:47 UTC and indexed by v4 at 09:00:52.
- Latest discovery union: 300 unique IDs, 167 supported pair markets, 133
  explicit exclusions.
- Latest selected panel: 40 markets (six available stable controls, 34
  rotating); 35 quality-valid pairs. Latest liquidity strata are 9/16/15
  high/medium/low, expiry strata 18/21/1 near/medium/long, and spread strata
  16/12/12 tight/medium/wide.
- Indexed panel: twelve snapshots, 480 selected observations, 431
  request/receipt-valid, 49 empty-ask invalids, 161 distinct markets, zero
  pending snapshots. The legacy reported-age/skew gate accepts 107/480; paired
  yield improves by 324 observations (+67.5 percentage points).
- There are 319 sampled consecutive book-state comparisons; 304 fingerprints
  differ. The API bands 54 markets as higher sampled change, 15 as lower, and
  92 unclassified. These remain intermittent comparisons, not venue update
  rates.
- Observation window: about 181 minutes; current API readiness is
  `collecting_repeated_temporal_coverage`.
- Data root: 9,865,838 bytes, below the 1 GiB cap.
- Service configuration: 40 markets, one-second request pacing, seven planned
  network requests per scan, `CPUQuota=5%`, `MemoryMax=256M`, low CPU/IO
  priority, no new privileges, and writes limited to the observatory data root.
- Latest scheduled scan completed successfully at 09:00:52 UTC, using about
  605 ms of CPU. Qualification run
  `VERITAS-M2-ECO-QUAL-001-RUN-b401cd384481` over twelve snapshots found zero
  positive states at all gates (431 quality-valid pairs, 161 distinct
  markets; top-edge median -0.028, maximum -0.001).

### Finalized source replay extension

The source analyzer's first batch, persistent catch-up, and scheduled
recurrences are recorded in checkpoints 003–010. The latest scheduled run
processed 128 segments / 26,555,999 bytes in 158 seconds, using 7.937 seconds
of CPU and 113.4 MiB peak memory. Cumulative progress is 786 of 2,959
replayable segments, through ordinal 55,101, with 2,173 segments
(602,349,214 bytes) pending. Readiness remains
`catching_up_finalized_source`; the processed prefix has no campaign-window
frames. The source timer is active and the Reality checkout remains clean at
`714f824`.

The full scan results and immutable source identities are in
[`VERITAS_MISSION2_GATE_A_CHECKPOINT_001.md`](VERITAS_MISSION2_GATE_A_CHECKPOINT_001.md),
[`VERITAS_MISSION2_GATE_A_CHECKPOINT_002.md`](VERITAS_MISSION2_GATE_A_CHECKPOINT_002.md),
[`VERITAS_MISSION2_GATE_A_CHECKPOINT_003.md`](VERITAS_MISSION2_GATE_A_CHECKPOINT_003.md),
[`VERITAS_MISSION2_GATE_A_CHECKPOINT_004.md`](VERITAS_MISSION2_GATE_A_CHECKPOINT_004.md),
[`VERITAS_MISSION2_GATE_A_CHECKPOINT_005.md`](VERITAS_MISSION2_GATE_A_CHECKPOINT_005.md),
[`VERITAS_MISSION2_GATE_A_CHECKPOINT_006.md`](VERITAS_MISSION2_GATE_A_CHECKPOINT_006.md),
[`VERITAS_MISSION2_GATE_A_CHECKPOINT_007.md`](VERITAS_MISSION2_GATE_A_CHECKPOINT_007.md),
[`VERITAS_MISSION2_GATE_A_CHECKPOINT_008.md`](VERITAS_MISSION2_GATE_A_CHECKPOINT_008.md),
[`VERITAS_MISSION2_GATE_A_CHECKPOINT_009.md`](VERITAS_MISSION2_GATE_A_CHECKPOINT_009.md),
and [`VERITAS_MISSION2_GATE_A_CHECKPOINT_010.md`](VERITAS_MISSION2_GATE_A_CHECKPOINT_010.md). Historical and current evidence inventories are
[`VERITAS_MISSION2_RESEARCH_INVENTORY_003.json`](VERITAS_MISSION2_RESEARCH_INVENTORY_003.json),
[`VERITAS_MISSION2_RESEARCH_INVENTORY_004.json`](VERITAS_MISSION2_RESEARCH_INVENTORY_004.json),
[`VERITAS_MISSION2_RESEARCH_INVENTORY_005.json`](VERITAS_MISSION2_RESEARCH_INVENTORY_005.json),
[`VERITAS_MISSION2_RESEARCH_INVENTORY_006.json`](VERITAS_MISSION2_RESEARCH_INVENTORY_006.json),
[`VERITAS_MISSION2_RESEARCH_INVENTORY_007.json`](VERITAS_MISSION2_RESEARCH_INVENTORY_007.json),
[`VERITAS_MISSION2_RESEARCH_INVENTORY_008.json`](VERITAS_MISSION2_RESEARCH_INVENTORY_008.json),
[`VERITAS_MISSION2_RESEARCH_INVENTORY_009.json`](VERITAS_MISSION2_RESEARCH_INVENTORY_009.json),
[`VERITAS_MISSION2_RESEARCH_INVENTORY_010.json`](VERITAS_MISSION2_RESEARCH_INVENTORY_010.json), and
[`VERITAS_MISSION2_RESEARCH_INVENTORY_011.json`](VERITAS_MISSION2_RESEARCH_INVENTORY_011.json), and
[`VERITAS_MISSION2_RESEARCH_INVENTORY_012.json`](VERITAS_MISSION2_RESEARCH_INVENTORY_012.json).

## Verification

| Check | Result |
| --- | --- |
| Full Veritas backend test selection | 88 passed; one Starlette/httpx deprecation warning |
| Ruff on source analysis, API, script, tests, and existing implementation | Passed |
| Mypy on source analysis, API, and CLI script | Passed |
| Frontend unit suite | 29 passed |
| Frontend typecheck, lint, production build | Passed; build reports a large-chunk advisory |
| Veritas Playwright workflow | Passed; discovery, no-candidate state, source link, and API artifact were verified |
| Broader seven-test browser run | Six passed; one Reality workflow failed because the expected exact `Yes` heading was absent |
| `git diff --check` before mission docs | Passed; rerun at checkpoint commit |
| Systemd service and timer deployment definitions | Loaded user units match checkout; latest scan succeeded and timer is active |

The broader browser failure was in `e2e/reality.spec.ts`; no Reality source or
campaign file was changed. A separate Reality regression/browser unit reports
an exit code from 2026-10-14, before this checkpoint. It was not restarted or
modified.

## Explicitly not done

- No Reality collector, source segment, campaign identity, or policy was
  changed. No Arena, Laboratory, Prometheus, or historical Veritas records
  were rewritten.
- No full venue census, WebSocket update-rate study, source sequence proof,
  queue-age proof, fill model, or profitability result exists.
- The original prospective follow-up study's 48-hour, nine-market, and
  dependence-analysis requirements remain unmet. The active snapshot pilot is
  a separate bounded alternative, not a silent waiver.
- No model was trained and no strategy policy promoted. The observed gross
  candidate count is zero.

## Gate A continuation: rotating discovery and Arena qualification

Checkpoint 011 introduces `veritas-public-observatory-v2` with deterministic
half-hour Gamma page offsets, preserved frozen controls, source-aware category
labels, explicit per-market conditional selection probabilities, response
size limits, and actual HTTP attempt counts. The scheduled 10:01 UTC scan
successfully processed six discovery frames and one CLOB batch, indexed a
13th snapshot, and left zero pending v4 analysis events.

The scan union contained 300 IDs and 132 supported binary pairs. The selected
40-market panel had 38 valid pairs, zero positive gross candidates, and no
orders. The bounded Arena qualification job replayed the immutable 13-event
v4 prefix and persisted its idempotent result as an Arena finding. It found no
positive state at the unchanged top-ask, full-depth, minimum-notional, or fee
gates. The Veritas dashboard exposes the collector limits and persisted Arena
activity; the browser workflow passed against the new finalized evidence.

The expanded checkpoint validation passed 132 related backend tests and 29
frontend tests, strict Mypy, Ruff, Python formatting, frontend lint/typecheck/
formatting, production build, and the Veritas discovery Playwright workflow.
See [Gate A checkpoint 011](VERITAS_MISSION2_GATE_A_CHECKPOINT_011.md) and
[research inventory 012](VERITAS_MISSION2_RESEARCH_INVENTORY_012.json).

The probabilities remain conditional on a bounded query-response union and
frozen controls; half-hour offsets do not make the frame representative of the
venue. Quote sequence freshness, a 24-hour pilot review, the 48-hour
follow-up/dependence gates, a complete Research Director workflow, and
independent economic confirmation remain open. The full source replay is still
catching up and contains no campaign-window frames in its processed prefix.

## Gate A checkpoint 015 addendum — scan 18 and second complete group

The scheduled 12:31 UTC scan brought the v4 panel to 18 snapshots, 720 selected
observations, 645 quality-valid pairs, and 304 distinct markets. The prior
reported-age/skew gate accepts 153 pairs; the paired recovery is 492 pairs
(68.33 percentage points). No positive top, depth, minimum-size, or fee state
appeared. The 40-market sample remains conditional on the bounded Gamma frame.

The new pinned study runner verifies the seven-market OpenAI IPO NegRisk group
from direct Gamma market responses, sequential question indices, and the
Polygon adapter question count. Its rules form six contiguous ranges and one
No-IPO outcome. The Gamma group-filter query returned 20 unrelated markets,
which makes the direct member reads and on-chain count the useful completeness
evidence for this case.

One 14-token CLOB batch returned full displayed depth for 5, 20, and 100
shares per outcome. Source data failed freshness qualification at 33,546 ms
maximum age and 20,962 ms cross-book skew. The Yes basket top cost equals its
conditional $1 payout; the No basket costs $6.035 against a $6 protocol
minimum. Both are non-positive before fees at all tested sizes. The captured
artifact replays from its embedded evidence with a matching result digest. The
runner compiles and replay validation passes; no broader suite was run for this
documentation and artifact checkpoint. See [Gate A checkpoint
015](VERITAS_MISSION2_GATE_A_CHECKPOINT_015.md) and [inventory
018](VERITAS_MISSION2_RESEARCH_INVENTORY_018.json).

## Gate A checkpoint 016 addendum — public stream replay

The second REST capture and the official public market WebSocket cross-check
both returned the complete 14-token group, but failed source age and timestamp
skew limits. Their best bid, best ask, and last-trade prices matched exactly
for all 14 tokens; full bid and ask depth matched for six tokens each. The
WebSocket frame contains no sequence field. Its complete-set Yes top gross
edge is $0, while the No set is -$0.035; all tested full-depth and fee-safe
edges are non-positive.

The replay runner now accepts `--replay-market-stream`. It verifies the
WebSocket artifact digest, referenced REST study, complete token set, frame
bytes, timestamps, tick sizes, and basket calculations. The stream schema omits
NegRisk and minimum-size fields, so replay binds those two constraints from
the digest-verified REST/Gamma metadata. The bounded saved capture replayed
successfully; no test suite was run for this documentation and artifact update.
See [Gate A checkpoint 016](VERITAS_MISSION2_GATE_A_CHECKPOINT_016.md), [Gate
F checkpoint 006](VERITAS_MISSION2_GATE_F_CHECKPOINT_006.md), and [research
inventory 019](VERITAS_MISSION2_RESEARCH_INVENTORY_019.json).

The 12:45 Arena qualification completed 18/18 finalized events and returned
zero-positive results at all five gates. Its finding is complete in Arena,
while the Director manifest retains a queued state pending the next scheduled
poll. The 12:43 finalized-source summary contained 4,078 campaign-window frame
records, 2,779 touched market-frame states, and 2,739 quality-valid states;
positive top-ask and full-depth states remained zero.

## Previous Gate A checkpoint 017 addendum — scan 19 and source-window replay

Scan 19 adds 36 quality-valid pairs and four empty-ask invalid pairs. The 19-scan
panel has 681/760 quality-valid observations, 160/760 legacy age/skew-valid
observations, and no positive top, depth, per-leg minimum, or fee state. The
bounded scan union has 298 unique IDs, 138 supported same-condition V1 pairs,
and 160 explicit exclusions. The 40-market selection retains 37 rotating
markets and three available frozen controls.

The finalized-source analyzer counts `period_frame_records` inside the frozen
campaign window. This changes the interpretation of checkpoint 016: its
12:43 prefix had 4,078 campaign-window frames, 2,779 touched states, and 2,739
quality-valid states. The 13:13 summary advances that count to 15,469 frames,
11,367 touched states, and 11,000 quality-valid states, with zero positive
top-ask or full-depth states. Replay remains partial and reads finalized
segments only.

The 13:15 Arena job completed all 19 events at 13:16:07 UTC with zero positive
states at each qualification gate. Its manifest still projects `QUEUED` and
scan 18 as last qualified until the scheduled 13:45:16 UTC cycle. Mission 2
remains active. See [Gate A checkpoint 017](VERITAS_MISSION2_GATE_A_CHECKPOINT_017.md),
[Gate F checkpoint 007](VERITAS_MISSION2_GATE_F_CHECKPOINT_007.md), and
[research inventory 020](VERITAS_MISSION2_RESEARCH_INVENTORY_020.json).
## Previous Gate A checkpoint 018 addendum — scan 20 and source replay

Scan 20 adds 33 quality-valid pairs and seven empty-ask invalid pairs. The
20-scan panel has 714/800 quality-valid observations, 167/800 legacy
age/skew-valid observations, and no positive top, depth, per-leg minimum, or
fee state. The bounded scan union has 297 unique IDs, 153 supported
same-condition V1 pairs, and 144 explicit exclusions. The 40-market selection
retains 37 rotating markets and three available frozen controls.

The 13:43 finalized-source summary counts 29,198 campaign-window frames,
21,747 touched market-frame states, and 21,041 quality-valid states. The
prefix remains partial with 1,699 finalized segments pending and zero positive
top-ask or full-depth states. Checkpoint 016's 12:43 counter interpretation
was corrected in checkpoint 017.

The 13:45 Arena job completed all 20 events at 13:46:06 UTC with zero positive
states at each qualification gate. Its manifest still projects `QUEUED` and
scan 19 as last qualified until the scheduled 14:15:29 UTC cycle. Mission 2
remains active. See [Gate A checkpoint 018](VERITAS_MISSION2_GATE_A_CHECKPOINT_018.md),
[Gate F checkpoint 008](VERITAS_MISSION2_GATE_F_CHECKPOINT_008.md), and
[research inventory 021](VERITAS_MISSION2_RESEARCH_INVENTORY_021.json).

## Gate A checkpoint 019 addendum — scan 21 and source replay

Scan 21 adds 37 quality-valid pairs and three empty-No-ask invalid pairs. The
21-scan panel has 751/840 quality-valid observations, 176/840 legacy
age/skew-valid observations, and no positive top, depth, per-leg minimum, or
fee state. The bounded scan union has 300 unique IDs, 198 supported
same-condition V1 pairs, and 102 explicit exclusions. The 40-market selection
retains 37 rotating markets and three available frozen controls.

The 14:13 finalized-source summary counts 40,459 campaign-window frames,
30,809 touched market-frame states, and 29,749 quality-valid states. The
prefix remains partial with 1,630 finalized segments pending and zero positive
top-ask or full-depth states. Checkpoint 016's 12:43 counter interpretation
was corrected in checkpoint 017.

The 14:15 Director cycle recorded scan 20 completion, then admitted scan 21.
The Arena job completed all 21 events at 14:16:20 UTC with zero positive
states at each qualification gate. Its manifest still projects `QUEUED` for scan 21 and
scan 20 as last qualified until the scheduled 14:45:16 UTC cycle. Mission 2
remains active. See [Gate A checkpoint 019](VERITAS_MISSION2_GATE_A_CHECKPOINT_019.md),
[Gate F checkpoint 009](VERITAS_MISSION2_GATE_F_CHECKPOINT_009.md), and
[research inventory 022](VERITAS_MISSION2_RESEARCH_INVENTORY_022.json).

## Latest operating checkpoint — scan 24

The scheduled observer, finalized-source replay, and Director qualification cycle completed on 2026-10-15. Scan 24 extended the bounded 40-market sample to 24 snapshots and 441 distinct markets; 859/960 pairs pass the current quality gate, while all gross, depth, minimum, and fee qualification gates remain zero-positive. The source prefix reached 2,289/3,727 finalized segments; the Director and Arena completed the scan-pinned qualification without orders or authenticated requests. The Director manifest projection awaits its 16:15:11 UTC scheduled reconciliation. See [Gate A checkpoint 022](VERITAS_MISSION2_GATE_A_CHECKPOINT_022.md), [Gate F checkpoint 012](VERITAS_MISSION2_GATE_F_CHECKPOINT_012.md), and [inventory 025](VERITAS_MISSION2_RESEARCH_INVENTORY_025.json). Mission 2 remains active.

## Latest operating checkpoint — scan 25

The scheduled discovery and qualification pipeline completed scan 25. The bounded six-frame query returned 297 unique IDs after three duplicates were removed; 121 passed same-condition V1 eligibility. The 40-market sample has 35 quality-valid pairs and no positive gross, depth, minimum, or fee state. The source prefix advanced to 2,417/3,786 finalized segments. Arena completed the scan-pinned 25-event qualification; the Director manifest awaits its scheduled reconciliation. See [Gate A checkpoint 023](VERITAS_MISSION2_GATE_A_CHECKPOINT_023.md), [Gate F checkpoint 013](VERITAS_MISSION2_GATE_F_CHECKPOINT_013.md), and [inventory 026](VERITAS_MISSION2_RESEARCH_INVENTORY_026.json). Mission 2 remains active.

## Latest operating checkpoint — scan 26

The scheduled discovery and qualification pipeline completed scan 26. Its deduplicated six-frame union retained 289 unique IDs after removing 11 identical duplicate records; 169 passed same-condition V1 eligibility. The 40-market sample has 34 quality-valid pairs and no positive gross, depth, minimum, or fee state. The source prefix reached 2,545/3,844 finalized segments. Arena completed the 26-event qualification; the Director manifest awaits its scheduled reconciliation. See [Gate A checkpoint 024](VERITAS_MISSION2_GATE_A_CHECKPOINT_024.md), [Gate F checkpoint 014](VERITAS_MISSION2_GATE_F_CHECKPOINT_014.md), and [inventory 027](VERITAS_MISSION2_RESEARCH_INVENTORY_027.json). Mission 2 remains active.

## Latest operating checkpoint — scan 27

The scheduled discovery and qualification pipeline completed scan 27. Its six-frame union contained 298 unique IDs after two identical duplicate records were removed; 123 passed same-condition V1 eligibility. The 40-market sample has 33 quality-valid pairs and no positive gross, depth, minimum, or fee state. The source prefix reached 2,661/3,903 finalized segments, with 1,242 pending. Arena completed the 27-event qualification with zero-positive gates. The Director manifest awaits its scheduled reconciliation. See [Gate A checkpoint 025](VERITAS_MISSION2_GATE_A_CHECKPOINT_025.md), [Gate F checkpoint 015](VERITAS_MISSION2_GATE_F_CHECKPOINT_015.md), and [inventory 028](VERITAS_MISSION2_RESEARCH_INVENTORY_028.json). Mission 2 remains active.

## Gate D improvement — version 2 candidate provenance

The economic qualification now records bounded, hash-linked source pointers
for every quality-valid positive top-ask row. It cross-checks those rows
against each event's positive counter, requires the exact immutable snapshot
path, marks the evidence as not independently replayed, and fails closed at
1,024 evidence rows instead of truncating. The experiment and run identity
are versioned as v2. The read-only v2 comparison over the current 28 finalized
snapshots found 996 valid pairs and no candidate; no research finding was
written by that comparison. Twenty-one targeted backend tests passed, with
Ruff, strict Mypy, and formatting checks. The positive evidence branch is
covered by a synthetic fixture and awaits a genuine candidate. Details are
in [Gate D checkpoint 001](VERITAS_MISSION2_GATE_D_CHECKPOINT_001.md).

## Gate D improvement — version 3 bounded candidate replay

Gate D now independently reopens the immutable source snapshot for each
positive gross candidate, checks source and event lineage, re-derives the
same-condition market and books from the embedded Gamma/CLOB payloads, and
recomputes best asks, quantity depth, minimums, and fee sensitivities under
explicit read bounds. The Director validates the replay summary; Arena exposes
the digest-checked finding through a read-only API, and the dashboard links to
the evidence. Replay is capped and fails closed. It records that request/receipt
timing does not establish venue sequence, atomicity, order arrival, or fills.

The current 29-snapshot read-only v3 comparison remains negative: 1,034 valid
pairs across 536 markets, maximum top-pair edge -0.001 per share, and zero
positive states at every gross or economic gate. The persisted scan-28 finding
is still v2; v3 was exercised with synthetic positive and tampered-source
fixtures and is awaiting the next scheduled persisted qualification. See
[Gate D checkpoint 002](VERITAS_MISSION2_GATE_D_CHECKPOINT_002.md) and
[inventory 030](VERITAS_MISSION2_RESEARCH_INVENTORY_030.json).

## Gate F compatibility correction — legacy v2 finding

The 18:15 Director cycle surfaced a version-compatibility defect: it treated
the completed scan-28 v2 finding as invalid because only v3 results contain the
source-replay object. Commit `9379985` accepts v2 candidate-pointer results as
unreplayed legacy evidence while keeping strict replay validation for v3. It
also makes dashboard projections tolerant of historical ledger entries that
lack status fields. The actual v2 finding now passes read-only validation; no
artifact was rewritten. The next scheduled Director cycle will retry
reconciliation and consider the newest scan. Details and the test evidence are
in [Gate F checkpoint 016](VERITAS_MISSION2_GATE_F_CHECKPOINT_016.md) and
[inventory 031](VERITAS_MISSION2_RESEARCH_INVENTORY_031.json).

## Gate C implementation in operation — coverage pilot scan 1

Commit `de3f764` added a prospective, read-only coverage pilot to the
scheduled observer. At 19:00:55 UTC, scan
`scan-20261015T190055Z-7799523b9d87` enrolled 40 selected pair slots; 32
passed the existing v4 quality checks and eight were invalid because of empty
ask sides. The scan used the existing seven public HTTP attempts. No manual
service invocation was used. The 24-hour window ends at 19:00:55 UTC on
2026-10-16, with a maximum of 48 scans and no early stopping or backfill.

The first descriptive split was 31/37 valid rotating pairs and 1/3 available
stable controls. This is not randomized and supports no causal inference. The
same scan had zero-positive top-gross, full-depth, minimum-notional, and both
fee sensitivity gates. The pilot implementation and plan digests are pinned;
the source files covered by the pilot hash should remain stable while it is
running. The fixed protocol, event lineage, limitations, and next work are in
[Gate C checkpoint 002](VERITAS_MISSION2_GATE_C_CHECKPOINT_002.md) and
[inventory 036](VERITAS_MISSION2_RESEARCH_INVENTORY_036.json).

## Gate F scheduled cycle — scan 31 and finalized-source progress

The scheduled 19:10 UTC source recurrence processed 113 finalized segments /
33,445,857 bytes and advanced the prefix to 3,132/4,140 segments. The
remaining suffix is 1,008 segments / 298,406,538 bytes. The campaign window
now contains 192,072 frame records and 169,253 quality-valid states across 43
markets, with zero positive top-ask or full-depth states. The bounded batch
used 13.619 CPU seconds, 146.7 MiB peak memory, and no swap.

The 19:15 Director cycle admitted scan 31 and Arena completed all 31 events in
1.914 seconds. Its v3 finding has 1,102 quality-valid pairs across 575
markets and zero positive states at all five economic gates. Candidate
provenance/replay is complete for the empty candidate set; the positive
candidate path remains synthetically tested only. The Arena job is complete,
but the Director manifest still projects it as queued until the next scheduled
cycle. See [Gate F checkpoint 017](VERITAS_MISSION2_GATE_F_CHECKPOINT_017.md)
and [inventory 036](VERITAS_MISSION2_RESEARCH_INVENTORY_036.json).

## Gate A / Gate F checkpoint 039 — scan 35 and supplemental gap replay

Scan 35 (`scan-20261015T210215Z-1f43257737f1`) extended the bounded panel to
35 snapshots / 1,400 selected pairs / 1,237 quality-valid pairs / 648 distinct
market IDs. The cumulative maximum top edge remains -$0.001 per share and all
five economic gates remain zero-positive. The five-scan coverage pilot has
200 slots, 167 valid pairs, 33 invalid pairs, 152 distinct IDs, and no skipped
sequences; its nonrandomized cohort split remains descriptive. See [Gate A
checkpoint 032](VERITAS_MISSION2_GATE_A_CHECKPOINT_032.md).

The scheduled source analyzer processed 125 segments / 33.39 MB and now covers
3,641/4,377 cataloged segments, with 736 / 237.91 MB pending. It has 204,052
quality-valid campaign-window states over 57 markets, with zero positive
states at every tracked gross/economic gate. A separate, pinned, bounded
gap-detail extractor now has a 256-segment prefix and 466 all-period gap
records. Independent raw-record and event-chain checks passed for the full
prefix; the indexed prefix ends about 11 hours before campaign start, so its
zero campaign-window gap count is not informative for the campaign. This
supplemental replay preserves the primary analyzer and frozen campaign. See
[Gate F checkpoint 021](VERITAS_MISSION2_GATE_F_CHECKPOINT_021.md) and [gap
detail prefix artifact 001](VERITAS_MISSION2_GAP_DETAIL_PREFIX_001.json).

The 21:15 UTC Director cycle admitted scan 35. Arena completed all 35 events
with a complete zero-candidate replay. The manifest still projects the job as
queued until the next scheduled Director cycle at 21:45 UTC. No strategy or
model is promoted. Focused opportunity-audit and candidate-replay verification
passed 23 tests. The new gap-detail implementation's three isolated tests,
Ruff, strict Mypy, formatting, and systemd unit checks passed before its first
scheduled runs; those runs have since completed with no restart or swap.

## Gate G — sealed scan-level edge distribution

At 22:37 UTC, a read-only projection was added to Arena research activity for
the newest completed, successful v3 Veritas qualification. The API accepts the
distribution only when the completed job, expected source scan, digest-verified
finding, experiment run, sample counts, and unchanged top-ask gross count
reconcile. The dashboard shows the minimum, nearest-rank median, maximum, and
positive-state count, links to the sealed finding, and labels its source scan.
It also explains that the qualification may trail the live observer and that
repeated states are correlated measurements.

The live observatory is at scan 38 (`scan-20261015T223101Z-62913d43b3c1`),
with 1,341 quality-valid states across 38 intermittent snapshots. Its
maximum top-pair edge remains -$0.001 per share, with zero positive states at
all recorded economic gates. The newest completed sealed qualification is
still scan 37 (`scan-20261015T220039Z-1bcb8753082e`): 1,307 quality-valid
states across 37 snapshots, minimum -$0.996, nearest-rank median -$0.020,
maximum -$0.001 per share, and zero positive gross states. The dashboard
preserves that scan-37 boundary instead of presenting it as scan-38 evidence.
No experiment, collector, service, frozen campaign, or pilot-pinned analyzer
was changed or restarted. See [Gate G checkpoint 009](VERITAS_MISSION2_GATE_G_CHECKPOINT_009.md).


## Gate A checkpoint 047 — scan-51 universe coverage replay

The bounded offline A1 replay now covers 51 saved snapshots / 33,318,338 compressed bytes and verifies the retained snapshot, Gamma, and CLOB evidence. Current eligibility counts match stored counts on all 51 scans. It reports 6,118 distinct bounded-union market IDs, 2,168 eligible at least once, 903 selected markets, and 1,755/2,040 current-replay valid pairs; positive top-gross pairs remain zero. The first scan still has a preserved 5-versus-32 capture/replay valid-pair discrepancy. See [Gate A checkpoint 047](VERITAS_MISSION2_GATE_A_CHECKPOINT_047.md), [coverage artifact 005](VERITAS_MISSION2_MARKET_UNIVERSE_COVERAGE_005.json), and ledger H115. The panel remains bounded and intermittent; it is not execution evidence.


## Gate A / Gate B checkpoint — scan 52

The bounded A1 replay is verified through 52 snapshots / 33,957,407 compressed bytes. It reports 6,195 bounded-union Gamma IDs, 2,180 eligible at least once, 926 selected markets, and 1,788/2,080 current-replay valid pairs; all 52 eligibility counts match and positive top-gross pairs remain zero. Independent source replay 006 matches all 1,788 v4 valid states and top edges with no mismatches; all gross, depth, minimum, and fee gates remain zero. The completed scan-52 Arena child awaits the scheduled 06:15 Director manifest reconciliation. See [Gate A checkpoint 048](VERITAS_MISSION2_GATE_A_CHECKPOINT_048.md), [Gate B checkpoint 007](VERITAS_MISSION2_GATE_B_CHECKPOINT_007.md), and inventory 070.


## Gate G checkpoint 015 — latest receipted coverage projection

The source API no longer pins the market-universe route to artifact 004/H110. It resolves the highest numbered existing coverage artifact with a matching ledger receipt, then validates its file hash and analysis version. A direct in-process projection returned coverage artifact 006 at scan 52, 1,788 valid pairs, and zero positive top-gross pairs. Older artifact 004/H110 receipts remain supported. Automated API tests and browser checks were not run; this source-only change is not deployed. See [Gate G checkpoint 015](VERITAS_MISSION2_GATE_G_CHECKPOINT_015.md).


## Gate A / Gate B checkpoint — scan 53

The bounded A1 replay now verifies 53 saved snapshots / 34,505,902 compressed bytes and matches the stored eligibility count on 53/53 scans. It reports 6,248 bounded-union Gamma IDs, 2,183 eligible at least once, 942 selected markets, and 1,818/2,120 current-replay valid pairs. Independent source audit 007 reproduces all valid states and top edges with zero mismatches; strict reported-age sensitivity accepts 388 states. Top-gross, full-depth, minimum, and fee gates remain zero. The first-scan capture/replay mismatch of 5 versus 32 remains unresolved and explicit. See [Gate A checkpoint 049](VERITAS_MISSION2_GATE_A_CHECKPOINT_049.md), [Gate B checkpoint 008](VERITAS_MISSION2_GATE_B_CHECKPOINT_008.md), and inventory 071.

The scan-53 Arena child completed 53/53 events with zero positive states and complete empty candidate evidence/replay. The Director manifest still projects it as `QUEUED`, with scan 52 last qualified, until the scheduled 06:45 UTC reconciliation. The read-only API projection selects coverage artifact 007 after its H118 ledger receipt; automated API/browser checks and deployment remain outstanding. See [Gate G checkpoint 016](VERITAS_MISSION2_GATE_G_CHECKPOINT_016.md).

## Gate A follow-up — first-scan counter semantics

A read-only comparison of the saved first snapshot and its v4 analysis event found that the reported 5-versus-32 count is an unlike-counter comparison. The snapshot stores 5 `valid_quality_pairs`; the paired v4 event stores 32 current `valid_quality_pairs` and 5 `legacy_freshness_valid_pairs`, with 27 pairs over the reported-age threshold. The v2 evaluator reproduces the v4 count, and source hashes verified. Preserve the values and artifact 007; after Director reconciliation, update the A1 analyzer to distinguish snapshot-stored counters from v4 event counters. See [Gate A counter-semantics note 001](VERITAS_MISSION2_GATE_A_COUNTER_SEMANTICS_NOTE_001.md) and [inventory 072](VERITAS_MISSION2_RESEARCH_INVENTORY_072.json).

## Gate A / Gate B / Gate F checkpoint — scan 54

The bounded A1 replay now covers 54 snapshots / 35,111,892 compressed bytes. The six-frame union contains 6,303 Gamma IDs; 2,185 were eligible at least once and 960 markets were selected. Current replay yields 1,853 quality-valid pairs from 2,160 observations; classifier counts match on 54/54 scans and positive top-gross pairs remain zero. Independent audit 008 reproduces all v4 validity and top-edge decisions with zero mismatches; strict reported-age sensitivity accepts 391 states. Top-gross, depth, minimum, and fee gates remain zero. The first-scan snapshot-counter comparison is explained in [Gate A note 001](VERITAS_MISSION2_GATE_A_COUNTER_SEMANTICS_NOTE_001.md). See [Gate A checkpoint 050](VERITAS_MISSION2_GATE_A_CHECKPOINT_050.md) and [Gate B checkpoint 009](VERITAS_MISSION2_GATE_B_CHECKPOINT_009.md).

The scheduled 06:45 UTC Director cycle reconciled scan 53 and admitted scan 54. Its Arena child completed 54/54 events with zero positives and complete empty candidate evidence/replay. The Director manifest now projects scan 54 as `QUEUED`, pending the scheduled 07:15 UTC reconciliation; keep the Arena research package pinned. The read-only API projection selects coverage artifact 008 after receipt H121; automated API/browser checks and deployment remain open. See [Gate F checkpoint 033](VERITAS_MISSION2_GATE_F_CHECKPOINT_033.md), [Gate G checkpoint 017](VERITAS_MISSION2_GATE_G_CHECKPOINT_017.md), and inventory 073.


## Gate A / Gate B / Gate F checkpoint — scan 55

The 55-snapshot A1 replay verifies 330 Gamma responses and 35,726,316 compressed snapshot bytes. It covers 6,371 bounded-union Gamma IDs, 2,187 eligible at least once, and 967 selected markets. Current replay finds 1,882 quality-valid pairs / 2,200 observations (85.55%) with zero positive top-gross pairs. The independent raw-source replay matches v4 validity and top-edge decisions with zero mismatches; strict reported-age sensitivity accepts 399 states and all gross, depth, minimum, and fee gates remain zero. Preserve the first-scan 5-versus-32 counter note. See [Gate A checkpoint 051](VERITAS_MISSION2_GATE_A_CHECKPOINT_051.md) and [Gate B checkpoint 010](VERITAS_MISSION2_GATE_B_CHECKPOINT_010.md).

The scheduled 07:15 UTC Director cycle reconciled scan 54 and admitted scan 55. Its job is projected as `QUEUED` until the scheduled 07:45 UTC cycle, so keep the Arena source pinned. See [Gate F checkpoint 034](VERITAS_MISSION2_GATE_F_CHECKPOINT_034.md). Automated API/browser checks and deployment remain open.


## Gate A checkpoint 052 — verify selection-probability support

The new offline design audit independently verifies 25 immutable coverage-pilot events, their source snapshots, and their v4 analysis events. All selected rotating-market inclusion probabilities match the recorded within-stratum quota/population ratio. Twenty-three scans fully support the rotating population; two category-phase scans have partial support, leaving 99.80% pooled support across scan-population exposure. The mean design-weighted valid yield across fully supported scans is 82.96%. This is conditional descriptive evidence; the frozen control comparison remains nonrandomized. See [Gate A checkpoint 052](VERITAS_MISSION2_GATE_A_CHECKPOINT_052.md), [audit 002](VERITAS_MISSION2_COVERAGE_DESIGN_AUDIT_002.json), and ledger H125. Four focused tests passed; no campaign or runtime package was changed.


## Gate C checkpoint 018 — shadow frame decode reuse

`Engine.consume` now returns the parsed frame events and `Context.consume`
reuses them to update last-trade diagnostics. This removes a duplicate
`json.loads` call on normal frame records while preserving raw canonical
records, reconstruction behavior, and trade tracking. The change is in the
Veritas worktree only; the frozen Reality worker continues to use its pinned
copy.

The focused Reality shadow and reconstruction tests passed (26), as did Ruff
and focused Mypy. The new test verifies one frame-payload parse and unchanged
trade output. No end-to-end CPU or throughput benchmark has been run, so the
runtime benefit remains unquantified. The active campaign remains lagged and
was not restarted. See [Gate C checkpoint
018](VERITAS_MISSION2_GATE_C_CHECKPOINT_018.md).

## Gate D checkpoint 003 — frozen-code import isolation (2026-10-16T11:29Z)

The editable Veritas checkout had drifted from the Reality code hashes pinned
by the original campaign. Both finalized-source and gap-detail jobs then
failed at `verify_campaign`, even though the frozen campaign files and plan
were intact. The analyzers were importing mutable `packages/midas/reality`
modules from the Veritas checkout.

A persistent import overlay now places the campaign's own `code/midas`
snapshot ahead of the editable Veritas packages for the two read-only replay
services. Their Veritas analysis modules and CLI scripts still load from the
active branch. The user-unit drop-ins are
`midas-veritas-source-analysis.service.d/20-frozen-campaign-import.conf` and
`midas-veritas-gap-detail-analysis.service.d/20-frozen-campaign-import.conf`;
the overlay is under
`/home/charlie/.local/share/midas-veritas/frozen-runtime-overlay`. This
preserves code and state identity checks rather than bypassing them.

Preflight verified all 20 campaign code files against the frozen plan and
matched both existing analysis-state code identities. The bounded source
analysis then processed 85 new segments and completed at 6,055/6,055 with no
pending bytes: 416,513 quality-valid states across 102 markets and zero
positive top-ask or full-depth states. The gap-detail batch processed 128
segments and advanced to 5,885/6,064, leaving 177 segments / 44,891,642 bytes
pending; it read no active segment. Both one-shots exited successfully under
their existing resource bounds. Campaign SHA remains
`aa8acb2b46823c1a1e3ac5d01a57dde917746c2c7471098ae2a4598875e322f5`, and the
separate Reality checkout remains clean. See [checkpoint 003](VERITAS_MISSION2_GATE_D_CHECKPOINT_003.md).

This repairs historical analysis operation; it does not fix the live shadow
lag or measure the decode-reuse optimization's CPU effect. The recurring timer
runs must still confirm that the overlay remains effective.

## Gate C checkpoint 019 — reader CPU bottleneck

Repeated `Tail.refresh()` directory walks measured 68–91 ms CPU over roughly
6,134 source segments at a 0.5-second refresh interval. Under the frozen
worker's 100 ms/s CPU quota, this repeated filesystem work could consume the
entire budget. The Veritas branch now reuses the segment path list until the
recording directory's device/inode/mtime/ctime changes and then rescans with
the existing symlink check. It also reuses parsed frame events for trade
diagnostics.

The focused suite passes (28), as do Ruff and strict Mypy. A bounded replay of
2,970 records / 2,461 frames across 16 sealed segments produced identical
Context state and reduced median `Tail` plus `Context` CPU by 16.16% against
the frozen reader. It does not include worker policy inference, journal writes,
or periodic saves. The optimization is not deployed to the original frozen
campaign; a full isolated successor-path profile is still required. See
[Gate C checkpoint 019](VERITAS_MISSION2_GATE_C_CHECKPOINT_019.md) and
[benchmark 001](VERITAS_MISSION2_SHADOW_READER_BENCHMARK_001.json).

## Gate C checkpoint 020 — full consume-path comparison

The isolated comparison now includes `Shadow.consume()` policy evaluation,
decision and observation journaling, follow-up processing, and periodic saves.
On the same 16 finalized segments, both implementations consumed 2,774 records
and produced identical engine and context digests plus all 768 normalized
decision, commitment, and follow-up rows. The Veritas branch used 10.01 CPU
seconds versus 49.64 seconds for pinned code, about 79.8% lower in this single
bounded pass. The replay ran under equal CPU and memory caps and wrote only to
temporary journals.

Focused shadow tests pass (16), as do Ruff and strict Mypy. A benchmark clock
fix makes periodic saves follow recorded monotonic time in both implementations;
a malformed-frame regression test preserves prior diagnostic trade tracking.
The benchmark runner's peak-RSS reading was corrected after its previous value
conflicted with the observed scope memory peak; memory is omitted from the A/B
claim. The active worker and frozen campaign remain unchanged. This replay
shows reader efficiency, not live catch-up, new market evidence, or economic
improvement. See [Gate C checkpoint 020](VERITAS_MISSION2_GATE_C_CHECKPOINT_020.md)
and [benchmark 002](VERITAS_MISSION2_SHADOW_READER_BENCHMARK_002.json).

## Gate C checkpoint 021 — independent full-consume comparison

A second, non-overlapping finalized window (ordinals 521245–525719) matched
all 768 normalized research rows and both engine/context state digests. In a
single bounded pass, CPU fell from 63.83 to 13.43 seconds and wall time from
255.31 to 53.67 seconds under equal resource bounds. A two-segment sequential
runtime-snapshot preflight also passed: the branch runner wrote a snapshot,
then loaded it to process the next finalized segment. The focused 16-test
shadow suite, Ruff, formatting, and strict Mypy passed. These results verify
the replay path, not live campaign catch-up or economic improvement. The
frozen worker remains untouched. See [checkpoint 021](VERITAS_MISSION2_GATE_C_CHECKPOINT_021.md),
[benchmark 003](VERITAS_MISSION2_SHADOW_READER_BENCHMARK_003.json), and ledger
H140–H141.

## Gate C checkpoint 022 — cursor validation and bounded runtime canary

The read-only runtime exporter now verifies that a cursor's ordinal and byte
offset land on the same finalized source-record boundary, in addition to
checking journal, campaign, segment, and catalog digests. A live snapshot of
the frozen campaign passed those checks without writing its journal. The five
snapshot-specific tests and the 21-test snapshot/shadow group passed; Ruff,
formatting, and strict Mypy also passed.

A 32-segment canary under a 5% CPU cap timed out at 20 minutes without
publishing progress. A smaller eight-segment canary under a 10% cap completed
in 84.69 seconds of process wall time (8.47 CPU seconds; 1,655 records and
1,393 frames). Its decision clock followed recorded timestamps, and its
temporary journal is not evidence of live catch-up or new economic outcomes.
The active campaign remains unchanged. See [Gate C checkpoint
022](VERITAS_MISSION2_GATE_C_CHECKPOINT_022.md).

## Gate A / B — independent 71-scan replay

The saved intermittent snapshot panel now contains 71 scans / 2,840 selected
market-pair observations, of which 2,361 pass the request-to-receipt quality
gate. The independent audit found zero positive top gross states and zero
positive states after displayed depth, per-leg minimums, or either fee
sensitivity. It independently checked 3,006 quantity-specific fee
calculations with no disagreements and found no v4 validity or edge mismatch.
The 7,355-ID bounded Gamma union included 2,378 markets eligible at least
once; 1,181 distinct market IDs were actually selected. The latest scan's
bounded union had 300 IDs / 113 eligible and selected 40. These remain
intermittent, selected observations, not continuous venue coverage. See
[audit 015](VERITAS_MISSION2_INDEPENDENT_OPPORTUNITY_AUDIT_015.json) and
[coverage 012](VERITAS_MISSION2_MARKET_UNIVERSE_COVERAGE_012.json).

Coverage pilot 002 has completed 10/48 scheduled scans: 286/400 selected pair
slots pass the main gate (71.5%), across 283 distinct markets, with no skipped
scan sequence. Its conservative reported-age sensitivity accepts 68 slots;
it verifies neither upstream atomicity nor sequence freshness. This is an
ongoing measurement study, not a strategy evaluation.

The scheduled finalized-source replay at 15:10 UTC completed at 15:13 UTC,
processing 57 new segments / 16.6 MB. It reached 6,498/6,498 cataloged
segments with no pending bytes and 469,501 quality-valid states across 106
markets; all tracked gross and post-depth gates remain zero. This interval
matched the incoming segment count but does not establish sustained surplus
capacity. The frozen campaign digest remains unchanged.

The 15:15 UTC Research Director cycle admitted scan 71 to the bounded Arena
qualification workflow. Its child completed 71/71 scan events in 5.32 seconds
and returned complete zero-candidate evidence at the baseline, depth,
minimum, and fee gates. The Director still awaits its next scheduled manifest
reconciliation. Model and strategy readiness remain blocked on missing
candidate-relevant evidence. See [Gate F checkpoint
036](VERITAS_MISSION2_GATE_F_CHECKPOINT_036.md).

## Gate C checkpoint 023 — maintained top-of-book cache

The branch now maintains best bid/ask values during snapshot and price-delta
reconstruction, rebuilds the derived cache after runtime restore, and uses it
in shadow history and the fast opportunity check. A sequential two-segment
canary matched engine, context, research, and journal hashes against the
baseline. Aggregate CPU fell 4.82% in this single paired pass; the first
segment was unchanged and the second was faster. Treat the reduction as
preliminary. The frozen worker was not restarted or changed. The focused suite
passes 49 tests, with Ruff, formatting, strict Mypy, and diff checks passing.
See [Gate C checkpoint 023](VERITAS_MISSION2_GATE_C_CHECKPOINT_023.md) and
[benchmark 004](VERITAS_MISSION2_SHADOW_READER_BENCHMARK_004.json).


## Gate C checkpoint 024 — durable tail refresh avoidance

The tail reader now skips directory inventory and cached-path stem searches
while a source segment handle is open, then forces an inventory refresh at a
sealed segment boundary. A one-segment paired replay under the same 5% CPU,
384 MiB memory, and zero-swap limits retained identical engine, context,
research, and journal hashes. Process CPU fell 76.48% versus the same branch
before this change. This remains a one-pass microbenchmark, not evidence of
live worker catch-up; the frozen campaign and worker were untouched. The
focused suite passed 51 tests; Ruff and formatting passed, while strict Mypy
for the newest change was not confirmed. See [Gate C checkpoint
024](VERITAS_MISSION2_GATE_C_CHECKPOINT_024.md) and [benchmark
005](VERITAS_MISSION2_SHADOW_READER_BENCHMARK_005.json).


## Gate C checkpoint 025 — four-segment durable replay

A paired replay over four sequential segments preserved the frozen
implementation's engine, context, research and journal hashes on committed
branch `40d1207`. Under identical 10% CPU, 384 MiB memory and zero-swap caps,
CPU fell from 17.29 to 3.23 seconds (81.32%) and wall time from 172.99 to
32.30 seconds. This is one historical window; it does not prove sustained
live catch-up. One public-measurement follow-up was observed and 123 were
censored; no fills or new market collection resulted. See [Gate C checkpoint
025](VERITAS_MISSION2_GATE_C_CHECKPOINT_025.md) and [benchmark
006](VERITAS_MISSION2_SHADOW_READER_BENCHMARK_006.json).
