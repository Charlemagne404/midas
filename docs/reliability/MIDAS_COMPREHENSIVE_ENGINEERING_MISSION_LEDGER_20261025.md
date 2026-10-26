# MIDAS comprehensive engineering mission ledger

**Updated:** 2026-10-26 CEST
**Mission checkout:** `/home/charlie/midas-engineering-mission-20261025`
**Branch:** `codex/midas-comprehensive-engineering-mission-20261025`
**Base commit:** `55601b9a090945cb498806e4878b6ddc33562043`
**Mission HEAD before this closeout update:** `1effd8d Complete MIDAS mission evidence and Veritas replay`

The implementation is isolated in this branch. The main checkout and older
worktrees were inspected and left unchanged. No runtime service was stopped,
restarted, signaled or reconfigured. No production data or archive file was
modified. No Frontier or Atlas work, multi-day campaign, real order, wallet
operation, or historical evidence rewrite was performed.

## Initial inventory and ownership

| Checkout | Branch / commit | State at final inspection | Mission handling |
|---|---|---|---|
| `/home/charlie/midas` | `main` / `55601b9a090945cb498806e4878b6ddc33562043` | 41 dirty entries, 18 untracked | Read-only; all pre-existing changes preserved. |
| `/home/charlie/midas-reality` | `project/reality` / `4f5cb5689548987bf30a33f050284ea8cb2f3c28` | Clean | Active protected Reality service source. |
| `/home/charlie/midas-veritas` | `project/veritas` / `3b102928594323e7886859d348f7b2151663debb` | Clean | Active Veritas runtime checkout; no changes made. |
| `/home/charlie/midas-reality-reliability` | `fix/reality-foundation-20261020` / `4278b5b5e66823e41a5d949b7b7c2e007c5b4ed0` | 26 dirty entries, 24 untracked | Read-only; preserved. |
| `/home/charlie/midas-veritas-research-overhaul` | `codex/real-market-research-overhaul` / `3b102928594323e7886859d348f7b2151663debb` | 25 dirty entries, 8 untracked | Read-only; preserved. |
| Mission checkout | `codex/midas-comprehensive-engineering-mission-20261025` / base commit above | Mission implementation and evidence changes only | Working branch for this mission; not pushed or merged. |

At the latest service inspection, `midas-api.service` ran release
`/home/charlie/.local/share/midas-api/releases/24c7504`, Reality ran from the
older Reality checkout, Veritas ran from `/home/charlie/midas-veritas`, and the
development web service ran Vite from `/home/charlie/midas/apps/web`. The
Research Readiness route is therefore integrated only in this mission branch.

## Implementation inventory and results

### Veritas v6 research overhaul

- Implemented the independent Decimal economic reference in
  `packages/midas/veritas/independent_economics.py`. It independently checks
  binary condition/outcome identity, protocol, crossed/inconsistent books,
  tick and price constraints, ask/depth, quantity and minimum-order evidence,
  collateral/notional, fee rules and rounding, complete-position gross/net
  values, source freshness and quality. Unsupported fee units or execution
  assumptions stay unmeasured.
- The primary scanner and independent reference report economic agreement
  separately from source-lineage agreement. Disagreement evidence is retained;
  no historical result is rewritten or reconciled in place.
- Added per-asset CLOB integrity, bounded targeted retries, a reference-random
  sampling cohort, and durable fair scheduling. Repeated visits are not counted
  as independent markets or independent trials.
- Added versioned SQLite scan and analysis catalogs, checksummed identities,
  restartable rebuilds, corruption detection, and interrupted-publication
  recovery. Summary publication streams and preserves complete evidence while
  bounding API payloads and reporting truncation explicitly.
- The eight-snapshot comparison in the benchmark file remains a historical
  differential result. The later bounded offline v3 replay covers the complete
  519-snapshot manifest through `scan-20261026T000113Z-72ddb4303c0b.json.gz`.
  It selected 20,754 market-pair observations across 3,918 unique markets;
  the independent reference audited 20,753, with 3,908 snapshot-valid pairs,
  14,665 validity disagreements, 14,665 source-quality disagreements, zero
  positive gross observations, zero economically supported pairs and zero
  net-eligible pairs. Repeated visits remain correlated observations, not
  independent trials.
- Fee support was measured for 3,908 audited pairs and unmeasured for 16,845.
  The market-level `restricted` flag was true on all 20,753 reference-audited
  observations and is retained as scope metadata; user geoblock and order
  acceptance remain unmeasured. All economic outcomes remain unsupported
  because the `orderMinSize` notional unit is unverified.
- The active v4 store has since advanced to 522 snapshots. Its 02:31:05 CET
  scan wrote `scan-20261026T013105Z-74db14ad03a0.json.gz`; the run failed at
  02:31:07 CET during analysis publication. The full v6 replay verifies its
  pinned 519-file boundary, not the current live boundary. The receipt and post-run
  verification are preserved under
  `data/veritas-v6-offline-replay-v3-20261026/`.
- **Status:** IMPLEMENTED, DEPLOYMENT PENDING. Active Veritas remains on v4.
  The 02:30:56–02:31:07 CET scheduled run failed during finalized-analysis
  publication on the legacy `research-summary.json` size limit;
  `/api/veritas/overview` returned HTTP 503 at 02:33:58 CET.

### Reality collection, observability and recovery

- Preserved explicit `unsequenced`, `incomplete_observability`, stale and
  degraded states. Local divergence markers are not called exchange-event
  loss counts because the public feed provides no documented global monotonic
  sequence.
- Added bounded queue and transport state, persistence lag/window, current vs
  historical error handling, source and receiver timing, read-only resource
  snapshots, implementation identity and bounded recovery/checkpoint metadata.
- Added deterministic checkpoint identity over source files, manifest
  boundary and state; resumable per-segment replay verifies a segment before
  committing a checkpoint and rechecks the prefix on resume.
- Added guarded fixture-canary copying and a read-only deployment assessment.
  Deployment verification/preflight/apply binds the candidate source and guard
  hashes, active configuration path/content, process identity, current
  finalized boundary, storage commitments and archive inventory. Preflight
  requires a seeded candidate canary, latest-boundary recovery receipt and
  checksum/provenance-verified archive receipt. Apply rechecks the live boundary
  and archive inventory before any write or restart.
- The 95-second schema-4 loopback/captured-fixture canary now matches the final
  candidate source SHA. It used a deterministic one-segment fixture seed, wrote
  765,835 durable bytes in five segments, processed 307 frames, and measured
  41,689,088 bytes process peak RSS and 0.583 process CPU-seconds. All 16
  fixture books were fresh before stop. It is not a production-boundary canary
  or a production capacity estimate.
- The V3 read-only inventory at `2026-10-25T23:51:56Z` found 31,468 finalized
  segments / 8,934,305,682 bytes through ordinal 5,068,661 and one open segment.
  It is a manifest/file-presence check, not content rehash or replay. The
  recorder cgroup had 5,484,544 bytes below `MemoryHigh`; service PID `3007040`
  remained active on the old 24 GiB / 90-day config.
- A separately admitted low-priority copy was interrupted after host I/O PSI
  exceeded the staging bound. It stopped at 697 of 31,468 segments / 103,723,201
  bytes. No recovery worker ran. The exact boundary was not pinned, the full
  destination manifest was not verified, and the partial destination is marked
  `INCOMPLETE`; it must not be resumed or treated as a snapshot. No further
  copy was admitted while a later I/O PSI sample remained above the staging
  threshold.
- **Status:** PARTIALLY VERIFIED. Production remains on the older collector
  and 24 GiB / 90-day config. The staged 112 GiB / 120-day candidate is not
  deployed.

### Archive and storage

- The current staging inventory has 19,833 finalized `.seg` files, 18,695
  manifest entries, 1,138 unmanifested finalized files and 58 `.copying`
  files. Manifest SHA-256 is
  `cc7e3375710fa024f971885f8b04840ec06f2c0cd385b716af73ce99275f7c8d`;
  `source.json` SHA-256 is
  `ae1bcd67331173194efe876f2f7d82e41cd515ebcf256d71a673328c91f26526`.
- A sampled candidate storage commitment fits available raw and archive
  filesystem space, with about 163.4 GB raw free and 635.2 GB archive free.
  This does not prove retention runway, archive ownership, checksums or
  source lineage.
- No ambiguous archive file was deleted, renamed, adopted, copied, published or
  written. No archive writer or timer was enabled.
- **Status:** BLOCKED pending owner/provenance verification and an immutable
  checksum receipt bound to the current inventory.

### Research Readiness dashboard

- Added a native Mission Control route backed by existing APIs and evidence.
  It shows current service health and versions, deployment vs staged identity,
  evidence funnel, independent economic audit, recovery/source quality,
  resource/storage freshness and six explicit evidence gates.
- Missing evidence cannot pass. Demo mode is prominent. Old errors are
  distinguished from current errors. Empty results and limitations have
  explanatory text and drill-down artifact identities.
- Final UI audit tightened the correctness gate: a fresh summary timestamp,
  nonempty independent reference sample, nonnegative disagreement counts,
  and a reference version are required before it can pass. The view now shows
  Veritas processed/pending coverage, reads the API's bounded-query-frame field,
  and withholds runway when its sample duration/rate are absent. It visibly
  separates validity, price/edge, fee and other disagreements and shows gross,
  net-eligible and unsupported counts. Integrated
  branch, commit and dirty state are injected consistently in the build and
  test configurations.
- `pnpm run lint`, `pnpm run typecheck`, `pnpm test` (32 passed),
  `pnpm run format:check`, and `pnpm run build` passed. Six selected Playwright
  specs passed 7/7; Arena E2E was excluded because it starts model training and
  policy search. The browser screenshot is fixture-backed UI evidence, not a
  production capture.
- **Status:** COMPLETE AND VERIFIED in the mission branch; deployment pending.

### Cross-component reliability

- Arena scheduling records durable fair decisions and reports stale directors
  and expired admission windows instead of hiding those conditions.
- API health reports available build identity and keeps demo/live execution
  explicit. Recovery and research status projections distinguish incomplete,
  stale and unavailable evidence.
- The broad relevant backend run produced 300 passing tests and two failures
  from a collision on the host-wide `.global-admission.lock`; both passed on
  isolated rerun, for 302 unique passing results. No assertion was weakened.
- The user systemd manager had 91 failed historical one-shot units at final
  inspection, including Arena, validation, Veritas and Reality units. These
  were not reset or cleared. The current Arena scheduler invocation exited
  successfully; the live Veritas observer still fails on its summary reader.
- **Status:** PARTIALLY VERIFIED. No full concurrent-heavy-workload test was
  admitted while Reality's service-specific memory margin was below threshold.

## Verification log

| Verification | Result | Scope / limitation |
|---|---|---|
| Broad backend regression | 300 passed; two global-lock collisions passed on rerun (302 unique pass results). | No production research workload launched by this mission. |
| Reality focused tests | 95 passed; final recovery/deployment/canary subset 75 passed in 7.80 s with `PYTHONPATH` unset. | Pytest now prepends local `packages/`; child process tests explicitly inherit the same mission source path. |
| Python static checks | Ruff check and `ruff format --check` passed for all 48 changed Python files. | No claim about runtime deployment. |
| Veritas differential/catalog/recovery tests | The final focused economics, opportunity-audit, continuous-analysis, scan-catalog and offline-replay suite passed 70 tests. | The complete replay covers the pinned 519-file boundary; the active store is now at 522. |
| Frontend | `pnpm run lint`, `pnpm run typecheck`, `pnpm test` (32 passed), `pnpm run format:check`, and `pnpm run build` passed after the final UI fixes. | Vite 7.3.7 emits 503.01 KiB index and 544.41 KiB chart chunks; the large-chunk warning remains. |
| Browser | Six selected specs passed all 7 tests in a single-worker batch: Laboratory (2), Paper (1), Reality (1), Research Readiness (1), Smoke (1), and Veritas (1). | Arena E2E was not run because it starts model training and policy search, which are excluded from this mission. |
| Recovery fixture | Interrupted checkpoint/resume and deterministic state reconciliation pass. | Fixture only; latest production boundary is unverified. |
| Reality canary | Final-source 95-second schema-4 loopback canary passed; 307 frames, 765,835 durable bytes, 5 segments / checkpoints, 41,689,088 B Python peak RSS, 0.583 CPU s. | One deterministic fixture seed; no external market requests. Does not establish production-boundary startup, recovery or capacity. |
| Reality latest-boundary snapshot | Copy stopped safely at 697/31,468 segments after I/O pressure exceeded admission bounds. | Partial path has an `INCOMPLETE` marker; no whole-snapshot identity, complete checksum receipt or recovery result exists. |
| Runtime API | HTTP 200 `READY`, demo, `live_execution=false`, Laboratory `READY`, paper recovery `CHECKPOINT_VERIFIED` at 666,807 events at 02:33:58 CET. | Time-specific read-only service observation; release is outside mission branch and health does not expose build identity. |
| Runtime Veritas | The 02:30:56–02:31:07 CET observer run failed on oversized legacy `research-summary.json`; the active tree contains 522 snapshots while the v4 summary covers 423, and overview returned HTTP 503 at 02:33:58 CET. | The 519-snapshot v6 offline replay is complete for its earlier pinned boundary. No service restart or output migration was performed; active code remains in `/home/charlie/midas-veritas`. |

The first final-subset pytest invocation loaded an editable package from the
main checkout and failed test collection. The branch now configures pytest to
prepend local `packages/`, and the two subprocess tests explicitly pass that
worktree's package and repository paths to their Python children. The final
run passed all 75 tests with `PYTHONPATH` unset. Ruff also caught a missing
`manifest` import in the added archive mutation test; it was fixed before the
passing run.

### Final read-only runtime recheck — 2026-10-26 01:33:58 UTC

The captured record is
[`MIDAS_MISSION_20261026_LIVE_STATE_RECHECK.json`](evidence/MIDAS_MISSION_20261026_LIVE_STATE_RECHECK.json),
SHA-256 `f89c3be4866ac10a488d50cca777fac78036a52e3a52d78e38dbb7c1a3dc86be`.
No process was signaled and no runtime, research store, or archive file was
modified.

- Main API: HTTP 200 `READY`, demo mode, `live_execution=false`, Laboratory
  `READY`, paper checkpoint verified at 666,807 events. The active release is
  `24c7504`; health does not report a build identity.
- Reality: protected PID `3007040`, old 24 GiB / 90-day config, 1,122,304,000 B
  cgroup current against 1,207,959,552 B `MemoryHigh`; cumulative `high=14,379`
  and `max`/OOM/kill counters are zero. Public observation is unsequenced; 16/16
  books are current, while persistence-window, recovery and queue telemetry are
  unavailable. Metadata-only inventory: 31,669 finalized files / 8,985,876,498
  B and one open file.
- Veritas: active v4 store has 522 snapshots, while its v4 summary covers 423.
  The latest observer run failed at 02:31:07 CET on the 2,097,481-byte summary;
  the API remains HTTP 503. Three snapshots are outside the pinned v6 replay.
- Storage: sampled NVMe free space 161,950,273,536 B; staged current commitment
  scenario deficit 6,506,911,519 B, 120-day historical-growth scenario deficit
  12,013,107,129 B. Archive inventory is 19,833 segments / 5,369,550,131 B,
  18,695 manifest entries, 1,138 unmanifested segments and 58 `.copying` files.
  Segment contents remain unchecked and provenance is unresolved.
- Arena research activity: zero active jobs/directors/schedules and zero
  invalid artifacts; one expired-admission alert remains open.
- Recovery: R15 remains incomplete at 2,304/20,148; the preserved copy attempt
  stopped at 697/31,468 without a pinned boundary or full snapshot receipt.

The full details and calculation assumptions are in the linked capture and
mission report. Staged storage capacity does not pass at this sample.

## Evidence identities

| Artifact | Identity |
|---|---|
| Candidate config `deploy/reality-candidate.json` | SHA-256 `908816c3dc568a8aa9d22a8d5bd0267d2f421cec6ca37a84901c5a6eae1f85e0` |
| Final Reality package source | SHA-256 `6cdfd3c09facaedfa86213fd794c33709bd36e37beb161f156d4cb06a2810d24` |
| Deployment guard script | SHA-256 `490a4ec9b6c55b6b0a0bfe5375eb5c0d5fb6ecd7cb930000fd66f7b9e3c0b973` |
| Latest read-only blocked inventory | V3 SHA-256 `41bacf1919c42d988b24e7d49c445767548167ddd1afe75f5014b7a93ae622ef`; inventory only, no guarded gate |
| Final-source canary receipt | `docs/reliability/evidence/MIDAS_MISSION_20261026_FIXTURE_CANARY_FINAL.json`; candidate source SHA matches final Reality package |
| Aborted copy receipt | SHA-256 `c1604255e5cd98ec5f2cc0612a01f7702c41ca1e29ad67072d559e5a8c93af4b`; partial destination must not be used as a snapshot |
| Earlier blocked assessment | SHA-256 `e256d90a1702c9d48e1defa4173a8c0a3543b969a1057b3f310b7c721a90a8cb` |
| Finalized boundary at latest inventory | V3 manifest SHA-256 `0270af73720b637c892cbbaf6240e40a411a46009a4345587501f7bf72328b9c` (31,468 segments; inventory only) |
| Archive manifest / source identity | `cc7e3375710fa024f971885f8b04840ec06f2c0cd385b716af73ce99275f7c8d` / `ae1bcd67331173194efe876f2f7d82e41cd515ebcf256d71a673328c91f26526` |
| Veritas bounded benchmark | `docs/REAL_MARKET_RESEARCH_OVERHAUL_001_BENCHMARK.json` |
| Veritas v3 replay receipt | `data/veritas-v6-offline-replay-v3-20261026/veritas-v6-offline-replay-receipt.json`; SHA-256 `5bcbf01437f1ada0b5b73e648e8c8bd9ac42ae5db216836c337f4bfe2a056ca0` |
| Veritas v3 post-run verification | `data/veritas-v6-offline-replay-v3-20261026/veritas-v6-offline-replay-postrun-verification.json`; SHA-256 `22d800358b707f3d8037dbd63607ccd9e193137c46ce4eb901eb764e38d5b272`; status `COMPLETED_OUTPUTS_REVERIFIED` |
| Veritas v3 source manifest | File SHA-256 `4690d53dbc4310dc8e96a145e7be2ae1d8371c210cf7c9dce80210c3e70d07e5`; embedded manifest SHA-256 `e9e38e533c181e0e99ddbe9788d26e91df633a3f542131c191c72184cce74458`; 519 source snapshots |
| Veritas v3 analysis events | 519 events; manifest SHA-256 `0935d6858159c8634d326c9f41e5140c7953c015f755b3b2e23e982b68a06a4e` |
| Veritas v3 published summary | File SHA-256 `81c1bbcf94d92c9bb3bb8c7acef61f321727bfa7108c5a98a813fec944023a31`; summary digest `0ad0dc41cf4f156073a4f191f4f9d6441972522fc4b544a96e5b49d07df7bb51`; 101,332 bytes |
| Newer active snapshot outside v3 replay | `/home/charlie/midas-veritas/data/veritas-observatory/snapshots/scan-20261026T003105Z-1ff325207f36.json.gz`; 631,294 bytes; SHA-256 `843ed98524418f6d1d799b326ebfd0649d86240bd79605a0c82103743bd1ba56` |
| Latest active snapshot outside v3 replay | `/home/charlie/midas-veritas/data/veritas-observatory/snapshots/scan-20261026T010053Z-ed1b5cd8b6a2.json.gz`; 581,481 bytes; SHA-256 `478422c77c48e84b840d5a19e67d64f1a84365e68accb1069b3742bb3ecf9281` |
| Newest active snapshot outside v3 replay | `/home/charlie/midas-veritas/data/veritas-observatory/snapshots/scan-20261026T013105Z-74db14ad03a0.json.gz`; 641,503 bytes; SHA-256 `3cd0da2f7460da912c34465c7bfff671ec537e3f87561d0d7ba0c8050fdb69f0` |
| Live runtime recheck | `docs/reliability/evidence/MIDAS_MISSION_20261026_LIVE_STATE_RECHECK.json`; SHA-256 `f89c3be4866ac10a488d50cca777fac78036a52e3a52d78e38dbb7c1a3dc86be` |
| Research Readiness browser evidence | `docs/reliability/evidence/MIDAS_MISSION_20261026_RESEARCH_READINESS.png` |
| Latest Reality inventory | `docs/reliability/evidence/MIDAS_MISSION_20261026_DEPLOYMENT_PREFLIGHT_BLOCKED_V3.json` |

The machine-readable [source/evidence manifest](MIDAS_COMPREHENSIVE_ENGINEERING_MISSION_SOURCE_MANIFEST_20261026.json)
binds 94 changed code, test, documentation and checked-in evidence files plus
25 replay/live artifact references. The full engineering report is
[MIDAS_COMPREHENSIVE_ENGINEERING_MISSION_20261025.md](MIDAS_COMPREHENSIVE_ENGINEERING_MISSION_20261025.md).

## Outstanding blockers and required follow-up

1. **Protected Reality deployment:** remain blocked until the service has safe
   `MemoryHigh` admission, current-source seeded startup evidence, exact-boundary
   resumable recovery and deterministic second replay. Explicit operator
   approval is required before the guarded apply action can restart the service.
2. **Latest-boundary recovery:** do not resume the earlier unpinned copy. A
   separate pinned staging root now has a validated cold checkpoint at
   2,816/31,742 segments. Preserve it; resume only after repeated fresh host
   I/O and recorder-resource admission passes and its source-prefix identities
   validate. Complete the whole pinned-boundary replay and remaining matrix
   phases before changing the recovery gate.
3. **Archive:** obtain logical owner and provenance, reconcile every segment
   and partial copy without deleting or republishing ambiguous files, verify
   checksums, and produce the receipt required by preflight. Do not enable the
   archive writer until then.
4. **Veritas runtime:** review a separate v6 migration and rollout for
   `/home/charlie/midas-veritas`. Preserve v4 summaries and events, rebuild the
   catalogs from authoritative snapshots, publish through the bounded reader,
   verify API health, then separately review timer ownership. Do not restart the
   active service merely to force this mission branch into production.
5. **Economic evidence:** retain zero candidates as a valid result. Do not claim
   profitability, fills, queue position or market prevalence from the bounded
   snapshot sample.
6. **Mission branch integration:** review the isolated diff and local commit;
   no push, merge, production rollout or runtime store migration occurred.

The mission stops before Frontier, Atlas and the next long-duration validation
campaign. No such project or campaign is authorized by this ledger.

### Bounded latest-boundary recovery attempt — 2026-10-26 02:23 UTC

- A new staging root pinned 31,742 finalized segments / 9,007,651,890 bytes
  through ordinal 5,102,644. The read-only probe passed; no Reality service or
  source file was changed. The immutable catalog and file-identity digests are
  `2c4f1ca2e3c1c91c580f3239b995b820b0e1c334b781ee4f0a12badbc83cb086` and
  `6495920055aabbde671f080190fa82c959504df72b8134cad74007b673e825c5`.
- Cold recovery wrote a checkpoint for 2,816 segments / 690,001,782 prefix
  bytes through ordinal 365,102. The progress receipt, checkpoint framing,
  pinned catalog prefix and reconstructed state hash agree. Its state digest is
  `b27bb39c58ea53c4b6c0cf24aad73c834750fd7b5552a471227ecfac4aa787ab`.
  This is partial recovery, not a full-boundary result; no `cold.json` receipt
  or final matrix result exists.
- The mission-owned validation unit was stopped after the protected recorder's
  `MemoryHigh` margin fell below the 64 MiB buffer. Across 90 worker samples,
  minimum `MemoryHigh` margin was 61,145,088 bytes and minimum `MemoryMax`
  margin was 195,362,816 bytes. Recorder `high`/`max`/OOM/kill counters were
  unchanged. The worker peaked at 671,350,784 bytes under its 768 MiB cap;
  its own soft-limit `high` events reached 285, while max/OOM/kill stayed zero.
  It exited via the requested TERM. A 02:26:43 UTC post-stop sample still had
  only 56,598,528 bytes below the recorder's `MemoryHigh`, so resume is not
  currently admitted.
- Evidence:
  `evidence/MIDAS_REALITY_RECOVERY_PARTIAL_20261026T0222Z.json`, SHA-256
  `0f8d134e3f5e8f581debb454818dd0d03ef144746a4c9b6138e0d01a2f502e86`.
  Preserve the external staging root at
  `/mnt/continental-cloud/data/midas-reality-staging/midas-mission-recovery-20261026T0210Z`.

### Follow-up Veritas v6 replay — 2026-10-26 02:56 CET

- The isolated replay advanced the earlier 519-snapshot pin to the 522 finalized
  snapshots then present in `/home/charlie/midas-veritas/data/veritas-observatory`.
  It copied 324,615,273 bytes through
  `scan-20261026T013105Z-74db14ad03a0.json.gz` and made no network requests.
- Snapshot catalog v4 indexed 522/522 with zero quarantines and integrity
  issues. Analysis catalog v6 processed 522/522 with zero quarantines. The
  522-event set, all derived output identities and the 100,031-byte summary
  passed the post-run `--resume` verifier.
- The Decimal reference audited 20,873/20,874 selected pairs across 3,932
  unique markets: 3,937 reference snapshot-valid, 14,750 validity disagreements,
  14,750 source-quality disagreements, zero positive gross candidates and zero
  economically supported or net-eligible pairs. These remain selected,
  correlated observations; minimum-order units and execution outcomes are not
  supported.
- Evidence: `evidence/MIDAS_VERITAS_V6_REPLAY_522_20261026.json`. Source
  manifest SHA-256 `c0e93d7fa5e49a7a4bb9f62d120baec4aaf7de6e0e2b0198c4a2b425edb78fa7`;
  replay receipt file SHA-256
  `1ddfe7a27bb7a85b499aaa71f41ac551924649d9c994cee5c870db0b619dc7e6`;
  verifier file SHA-256
  `5d5cb78d9940882d4e3c1b06456c522db84679ccbb242b49e7395664fe94feca`.
- The scope cgroup peak was 537,374,720 bytes, with 887 `high` events and zero
  `max`, OOM or kill events. The receipt also reports a 1,089,118,208-byte
  process peak RSS that does not reconcile with cgroup accounting; do not use
  that value for capacity claims. Active runtime remains v4 and is not migrated.
- **Status remains:** IMPLEMENTED, DEPLOYMENT PENDING. This closes the 519-to-522
  replay coverage gap as of this capture only; the live observer can append new
  snapshots, and a v6 runtime migration still requires a separate rollout.

### Latest scheduled Veritas observation — 2026-10-26 03:02 CET

- The ordinary v4 observer run began at 03:01:24 CET, wrote snapshot 523, then
  failed at 03:01:35 CET with `ValueError: Unsafe or oversized analysis
  artifact: research-summary.json`. `/api/veritas/overview` returned HTTP 503.
- Latest snapshot:
  `scan-20261026T020133Z-f1469881bdbc.json.gz`, 641,953 bytes, SHA-256
  `7625c0aa702594d2f6e022f9c7e5ad462c905046681c2ad8ea0d697a526f17a3`.
  The legacy summary remains 2,097,481 bytes and reports 423 processed.
- This snapshot was written after the 522-file v6 pin and is outside that
  replay. The next ordinary timer is not a reason to repeat a full replay; keep
  the evidence boundary explicit and migrate v6 only through a separately
  reviewed deployment.
- Read-only capture:
  `evidence/MIDAS_VERITAS_20261026_POST_TIMER_RECHECK.json`, SHA-256
  `342ff41ca6a32a41340c0fec3ae798a21e1258c353df28efa2564540d2c54913`.
  No service or production data was changed by the capture.

### Latest Reality admission sample — 2026-10-26 03:05 CET

- The protected PID `3007040` remained on the old config hash
  `9d1aeeb5a496ad6971dc461ce87f327266ff25240391897f7bb6091a8307119a`.
  Cgroup current was 1,131,302,912 bytes, 76,656,640 below `MemoryHigh` and
  210,874,368 below `MemoryMax`; `high=14,379`, `max`/OOM/kill=0.
- Host available memory was 8,000,172,032 bytes and I/O-full PSI was 0.86% over
  60 seconds. The staging admission function passed one point sample only; no
  sustained 60-second window or worker was started. Raw/staging filesystem free
  space was 161,060,818,944 / 635,101,380,608 bytes. Carrying forward the
02:33 requirement assumptions, current commitments are short 7,396,366,111
bytes and the 120-day historical-growth case is short 12,902,561,721 bytes;
the growth rate was not re-estimated.
- The eight-phase recovery command remains a long, resumable matrix with up to
  7,200 seconds per worker. The latest-boundary cold recovery gate remains
  incomplete; a point admission pass is not recovery evidence.
- Capture: `evidence/MIDAS_REALITY_ADMISSION_RECHECK_20261026T0204Z.json`,
  SHA-256 `527ca3ac3d08811863f8458b5418d6ba165450d34990289c589379a6d0cd8ea1`.
