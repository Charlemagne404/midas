# Veritas Mission 2 Gate A Checkpoint 004 — Timer Resume

- **Captured:** 2026-10-15 06:57 UTC
- **Branch:** `project/veritas`
- **Protected Reality commit:** `714f824`
- **Status:** Persistent timer catch-up batch passed; scheduled recurrence remains active.

## Timer-triggered resume

When `midas-veritas-source-analysis.timer` was enabled, its `Persistent=true`
setting triggered a catch-up run for the earlier 30-minute boundary. The
source-analysis oneshot started at 06:55:44 UTC and completed at 06:57:40 UTC
with exit status 0. It restored the state left by the first batch and advanced
the immutable prefix from 128 to 256 replayable segments, through ordinal
13,113.

At this run's catalog snapshot, there were 2,692 replayable segments and two
empty finalized headers. The analyzer had 2,436 replayable segments
(628,722,061 bytes) pending. The second batch processed 23,084,308 bytes;
cumulative processed source bytes are 28,731,135. Systemd recorded 5.826
seconds CPU, 110.9 MiB peak memory, and no swap. The run completed within the
10-minute timeout and stayed below 256 MiB memory.

Progress and readiness remain separate from public snapshot analysis. The
first 256 source segments contain zero campaign-window frame records, zero
quality-valid paired states, and zero positive states. The readiness remains
`catching_up_finalized_source`; these bootstrap records are not economic
evidence.

## Lineage and runtime state

- Pinned campaign ID: `adf91d042ab8f91678834b9258bfde70022a763dfda8c91d1e94be334583aa46`
- Campaign file SHA256: `aa8acb2b46823c1a1e3ac5d01a57dde917746c2c7471098ae2a4598875e322f5`
- Analysis code SHA256: `9f9e2249b49dd1cb10c11713aa2683567aa9cf0914c3ed2b08cf8e3fea25ebf8`
- Processed prefix catalog SHA256: `50e40cfcd73cad289cedfaec6f995b40c51ec00567f40a8a1efbfe4892908fb5`
- Latest event SHA256: `d0ee4d81aa6548a44a6c7776a7808e70f886abb5e220471811f9f4ea48fda2cd`
- Latest event file SHA256: `65ff7bc0d326e2206f496c28e7e4a47d8244b8105f7ecd1ff6cf6f12569584e4`
- Summary digest: `6b2f98ce01e7b87628336f1254bd819c1becce7e000f781b1fb1a810f5325086`
- Summary file SHA256: `7d9647e51a4eff4869d3741b10b6a543f0d3305349373d6a034bc7afd6bf4595`
- Veritas observatory data root: 5,140,993 bytes, below its 1 GiB limit.

The source timer remains active and the oneshot is inactive after success. Its
next calendar event is 07:10:58 UTC. The existing public snapshot timer is also
active and remains offset from source analysis.

The Reality checkout remains clean at `714f824`, and its recorder remains
active. The source service read finalized cataloged files only; it did not
open `.open`, write the Reality tree, restart a Reality unit, or take the
writer lock.

## Evidence and limitation

This second run confirms state restoration and timer-triggered progress across
a real source prefix. Synthetic tests continue to cover crash recovery,
idempotent event comparison, empty finalized segments, prefix drift, and
one-pass metric agreement. It is one timer catch-up execution and does not
establish long-term recurring reliability. The next scheduled source run
should be checked for service status, updated hashes, residual backlog, and
resource use.
