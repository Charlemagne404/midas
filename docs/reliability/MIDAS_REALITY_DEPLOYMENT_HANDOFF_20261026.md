# Reality collector deployment handoff — 2026-10-26

## Current production identity

The protected service is `midas-reality.service`, PID `3007040`, running from
`/home/charlie/midas-reality` with data root
`/home/charlie/midas-reality/data/recordings/reality`. Its active configuration
is `/home/charlie/midas-reality/deploy/reality.json`, SHA-256
`9d1aeeb5a496ad6971dc461ce87f327266ff25240391897f7bb6091a8307119a`.
It configures 24 GiB and 90 days. Its systemd cgroup limits are
`MemoryHigh=1,207,959,552` and `MemoryMax=1,342,177,280` bytes.

The staged candidate is `deploy/reality-candidate.json` in the isolated
mission branch. Its SHA-256 is
`908816c3dc568a8aa9d22a8d5bd0267d2f421cec6ca37a84901c5a6eae1f85e0` and it
requests 112 GiB / 120 days. It does not change the service memory limits.
This candidate has not been copied into the runtime checkout.

The final-source schema-4 canary ran for 95 seconds in a separate terminal
scope. It used one deterministic fixture segment, loopback WebSocket and
in-process `MockTransport`; it made no external market requests. It processed
307 frames, wrote 765,835 durable bytes across five segments, made five
checkpoints, and measured 41,689,088 bytes process peak RSS and 0.583 process
CPU-seconds. All 16 fixture books were fresh before stop. Its source SHA matches
the final Reality candidate, but this small synthetic seed is not the
production boundary. The canary's estimated 0.647 GiB/day is not a production
capacity estimate. Its execution cgroup totals aggregate the named scope; the
lifetime cgroup peak is not the collector's production peak.

A newer read-only assessment at `2026-10-25T23:30:01.032254Z` found only
1,662,976 bytes below `MemoryHigh` (14,353 cumulative `high` events; zero
`max`/OOM/kill events). It captured 31,425 finalized segments / 8,923,447,888
bytes through ordinal 5,063,282 and one open segment. The status was 9.786
seconds older than the assessment capture; status and catalog reads were not
atomic. This historical assessment is
[`MIDAS_MISSION_20261026_DEPLOYMENT_PREFLIGHT_BLOCKED_V2.json`](evidence/MIDAS_MISSION_20261026_DEPLOYMENT_PREFLIGHT_BLOCKED_V2.json),
SHA-256 `25ea857aeefc39ff6bf0254535ef20768a7228e26702d2aa2e72aa80eb6c825a`.

The later V3 read-only inventory at `2026-10-25T23:51:56Z` found 31,468
finalized segments / 8,934,305,682 bytes through ordinal 5,068,661, manifest
SHA-256 `0270af73720b637c892cbbaf6240e40a411a46009a4345587501f7bf72328b9c`, and
one open segment. It inventories manifest/file presence only; it does not
rehash segment contents or replay them. At that sample PID `3007040` had
5,484,544 bytes below `MemoryHigh`. V3 is an inventory rather than a guarded
preflight: no gate was written. See
[`MIDAS_MISSION_20261026_DEPLOYMENT_PREFLIGHT_BLOCKED_V3.json`](evidence/MIDAS_MISSION_20261026_DEPLOYMENT_PREFLIGHT_BLOCKED_V3.json),
SHA-256 `41bacf1919c42d988b24e7d49c445767548167ddd1afe75f5014b7a93ae622ef`.

A fresh read at `2026-10-25T23:59:44Z` found the same protected PID active,
1,098,846,208 bytes current against `MemoryHigh=1,207,959,552`, and
`memory.events` counters `max=0`, `oom=0`, `oom_kill=0`. Host I/O PSI full was
0.72% avg10 / 1.48% avg60 / 4.28% avg300. A single sample does not satisfy the
60-second continuous admission window required before another staging phase.

## Storage and archival state

- The staged candidate's storage claims target a separate archive filesystem.
  The archive filesystem had approximately 635 GB free; the candidate retains a
  400 GiB archive reserve. The recording filesystem had approximately 163 GB
  free at inspection, with about 8.9 GB of raw data. The proposed 112 GiB
  recording budget and 20 GiB raw reserve fit the sampled free-space total, but
  that is not evidence of a reliable growth rate or of archive correctness.
- The latest archive-mission3 inventory has 19,833 finalized segments and 58
  `.copying` files. Its manifest has 18,695 entries; 1,138 finalized files are
  not in the manifest. The tree's uid/gid does not prove its logical owner or
  source lineage. The deployment guard now requires a separate, current receipt
  that proves archive checksums and ownership/provenance and binds the exact
  manifest, source identity, counts and path. It refuses preflight and apply if
  any inventory entry changes. No qualifying receipt exists.
- Do not delete, rename, adopt, publish or re-copy ambiguous files. Do not
  enable the archive writer or timer until an owner-approved, checksum-verified
  reconciliation plan binds every source and destination segment.

## Readiness assessment

**Status: BLOCKED; no deployment approval has been requested or inferred.**

The final-source fixture canary passes for candidate identity
`6cdfd3c09facaedfa86213fd794c33709bd36e37beb161f156d4cb06a2810d24`, but its
one-segment deterministic fixture does not establish production-boundary
startup or recovery. The latest full archive boundary has not been
cold-recovered; historical R15 stopped at 2,304/20,148 segments; the archive
staging tree has unresolved provenance and manifest gaps; and there is no
production-sized isolated startup peak to compare with recorder limits.

The matching-source canary is deliberately limited to a one-segment fixture
seed. It cannot satisfy the guarded preflight's production-boundary recovery
requirement.

The first latest-boundary copy attempt was stopped when host I/O pressure
exceeded the staging admission threshold. It copied 697 of 31,468 segments /
103,723,201 bytes before interruption, but its source boundary was not pinned
and the complete destination manifest was not checked. The partial directory
`/mnt/continental-cloud/data/midas-reality-staging/mission-20261026-recovery-snapshot-75f7cee8b6d14d90a32efb205c4672e9`
has an `INCOMPLETE` marker and must not be used or resumed as a snapshot. The
stop receipt is
[`MIDAS_MISSION_20261026_RECOVERY_COPY_ABORTED.json`](evidence/MIDAS_MISSION_20261026_RECOVERY_COPY_ABORTED.json),
SHA-256 `c1604255e5cd98ec5f2cc0612a01f7702c41ca1e29ad67072d559e5a8c93af4b`.

Before a new preflight can pass, require a 60-second continuous admission
window, pin the exact latest finalized manifest boundary, and create a new
checksummed immutable copy in a distinct path. Verify every segment and the
whole manifest, then use resumable recovery checkpoints; record candidate
source hash, input manifest digest, state digest, completion boundary, process
peak RSS and cgroup peak; replay the same copy again and compare deterministic
state. Bound memory, CPU and I/O before each phase. Leave the gate incomplete if
any step cannot finish safely. Separately reconcile archive ownership and
provenance without deleting or publishing ambiguous files, and verify every
listed source and destination checksum.

## Guarded procedure after blockers clear

From the mission checkout, with no conflicting heavy job active:

1. Run `scripts/reality_deployment.py verify` and retain the receipt. It binds
   test results to the candidate source and deployment-guard script hashes.
2. Run `scripts/reality_fixture_canary.py` against a new isolated root under
   `data/recordings/`. Use captured fixtures/loopback transport only and retain
   the versioned config and receipt. Do not reuse a root or overwrite evidence.
3. Run the exact-boundary replay and independent resource check described
   above, on a checksummed copy with a resumable checkpoint. Do not replay the
   production root concurrently with the recorder.
4. Recheck the active systemd PID, active-config path/hash, cgroup limits and
   resource admission. Run `preflight` with `--active-config
   /home/charlie/midas-reality/deploy/reality.json`, the current candidate,
   current-source seeded canary, exact-boundary recovery evidence, a
   checksum- and provenance-verified `--archive-receipt`, and archive
   destination. Require the gate to bind those identities and show no
   unresolved blocker. The new guard checks the active manifest boundary,
   archive inventory and storage commitment again immediately before apply.
5. Review rollback backup location, ownership, filesystem reserves and the
   expected loss window. The service restart interrupts recording. The public
   feed has no documented global monotonic sequence, so the interval cannot be
   reconstructed as an exact missing-event count; record the interruption as
   source-continuity uncertainty.
6. Obtain explicit operator approval. Only then may the guarded `apply` action
   write candidate config and restart the service. A failed fresh-book health
   check causes a second restart to restore the frozen old config; neither
   restart recovers observations absent during the outage.

The mission did not run `apply`, stop or restart the service, edit the active
config, or change archive policy. It created the explicitly incomplete staging
directory above; the recording source and ambiguous archive tree were not
modified. See the
[comprehensive mission report](MIDAS_COMPREHENSIVE_ENGINEERING_MISSION_20261025.md)
for the complete runtime inventory and test evidence.

## Latest read-only recheck — 2026-10-26 02:33:58 CET

The live sample is bound in
[`MIDAS_MISSION_20261026_LIVE_STATE_RECHECK.json`](evidence/MIDAS_MISSION_20261026_LIVE_STATE_RECHECK.json),
SHA-256 `f89c3be4866ac10a488d50cca777fac78036a52e3a52d78e38dbb7c1a3dc86be`.
No service was signaled or changed.

- The protected recorder remained PID `3007040`, `ActiveState=active`, with
  `NRestarts=2` from `/home/charlie/midas-reality`. It remained on the old
  24 GiB / 90-day config, SHA-256
  `9d1aeeb5a496ad6971dc461ce87f327266ff25240391897f7bb6091a8307119a`.
- Its cgroup sample was 1,122,304,000 bytes against
  `MemoryHigh=1,207,959,552` and `MemoryMax=1,342,177,280`; cumulative
  `memory.events.high=14,379`, with `max`, OOM and kill counters at zero. The
  API reports 16/16 fresh books but keeps source state
  `RECORDING_UNSEQUENCED`, `sequence_verified=false`, and health degraded
  because its recent persistence window, recovery state and transport queue
  depth are unavailable. The current API collector error is null.
- Metadata-only raw inventory found 31,669 finalized files / 8,985,876,498
  bytes and one open file. No segment contents or checksums were read.
- NVMe free space was 161,950,273,536 bytes. With the current raw bytes, the
  staged 112 GiB raw budget, 31.414 GB database high-water allowance, 4 GiB
  Veritas allowance and 20 GiB free reserve require 168,457,185,055 bytes, a
  6,506,911,519-byte deficit. At the historical growth floor, a 120-day raw
  horizon plus those commitments requires 173,963,380,665 bytes, a
  12,013,107,129-byte deficit; the raw budget alone covers about 114.34 days.
  These are declared planning assumptions, not a guarded preflight. The archive
  filesystem had 635,101,380,608 bytes free, but provenance remains unresolved.
- The archive tree still held 19,833 finalized segments, 58 `.copying` files,
  18,695 manifest rows, 1,138 unmanifested segments and no manifest entries
  missing from the directory. Only directory names, file sizes and the
  manifest were checked; segment contents were not hashed. No files changed.

Storage sufficiency is now an additional explicit deployment blocker. Recheck
all usage, database growth and reserve assumptions before any deployment
preflight. Do not use the staged candidate or enable archive writing to work
around the deficit.
