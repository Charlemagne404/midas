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

At the last admission measurement the recorder had approximately 6.7 MiB
below `MemoryHigh`; the hard-limit and OOM counters were zero. The host had
about 7.9 GiB available and the short PSI admission checks passed. The bounded
canary ran in a separate terminal scope and made no external market requests.
Its process RSS/CPU measurements describe that fixture process. Its execution
cgroup totals aggregate the named scope; the lifetime cgroup peak is not the
collector's production peak.

A newer read-only assessment at `2026-10-25T23:30:01.032254Z` found only
1,662,976 bytes below `MemoryHigh` (14,353 cumulative `high` events; zero
`max`/OOM/kill events). This is below the 4 MiB concurrency admission floor.
It captured finalized manifest SHA-256
`e5a75cc4cb62c948be891000b12612161ab3f0e31408103ccc84cdb847d12276`, with
31,425 segments / 8,923,447,888 bytes through ordinal 5,063,282 and one open
segment. The status reported `RECORDING_UNSEQUENCED`, 16/16 fresh books, and
was 9.786 seconds older than the assessment capture. The status and catalog
reads are not an atomic boundary. The assessment is
[`MIDAS_MISSION_20261026_DEPLOYMENT_PREFLIGHT_BLOCKED_V2.json`](evidence/MIDAS_MISSION_20261026_DEPLOYMENT_PREFLIGHT_BLOCKED_V2.json),
SHA-256 `25ea857aeefc39ff6bf0254535ef20768a7228e26702d2aa2e72aa80eb6c825a`.
The earlier `..._BLOCKED.json` assessment is preserved as a historical sample.

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

The candidate's changed-code suites pass in the mission worktree, but no current
verification receipt or seeded canary matches its final source identity
(`6cdfd3c09facaedfa86213fd794c33709bd36e37beb161f156d4cb06a2810d24`). The
latest full archive boundary has not been cold-recovered; historical R15
stopped at 2,304/20,148 segments; the staging tree has unresolved provenance
and manifest gaps; and there is no production-sized isolated startup peak to
compare with the recorder limits. The service has only 1.66 MiB below
`MemoryHigh`. An empty-root fixture cannot substitute for seeded boundary
startup and recovery evidence.

The saved schema-3 canary was made before the final recovery changes and its
candidate source hash differs from the current candidate. It was also an
empty-root canary, with no `seed_manifest_sha256`; it cannot satisfy the new
guarded preflight's seeded-boundary requirement.

Before a new preflight can pass, first obtain safe resource admission, then
create a checksummed, immutable copy of the exact latest finalized boundary;
verify it with resumable checkpoints; record the candidate source hash, input
manifest digest, state digest, completion boundary, process peak RSS and cgroup
peak; then replay the same copy again and compare deterministic state. Bound
memory, CPU and I/O admission before each resume. Leave the gate incomplete if
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
config, touch the recording root, or change archive policy. See the
[comprehensive mission report](MIDAS_COMPREHENSIVE_ENGINEERING_MISSION_20261025.md)
for the complete runtime inventory and test evidence.
