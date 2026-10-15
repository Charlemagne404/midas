# Veritas Mission 2 Gate A Checkpoint 006 — Continued Scheduled Replay

- **Captured:** 2026-10-15 07:43 UTC
- **Branch:** `project/veritas`
- **Protected Reality commit:** `714f824`
- **Status:** The second ordinary scheduled source recurrence and ninth public snapshot completed successfully. Source catch-up, observation, and dependence gates remain open.

## Second scheduled source-analysis recurrence

The source timer fired at 07:40:03 UTC. The oneshot completed at 07:42:08 UTC
with exit status 0, in 125 seconds. Systemd recorded 6.265 seconds CPU, a
125.9 MiB peak, and no swap. The batch advanced the full 128-segment limit,
processing 25,719,771 bytes.

The analyzer restored its saved reconstruction context and advanced from 274 to
402 processed segments out of 2,780 replayable segments. Two validated empty
finalized headers remain excluded from replay. The new prefix reaches ordinal
22,352 and contains 86,273,833 processed source bytes. There are 2,378
segments / 594,257,808 bytes pending. Readiness remains
`catching_up_finalized_source`.

The batch contained no campaign-window frames, quality-valid states, or
positive states. The replay remains bootstrap context for the frozen campaign;
it provides no economic observation.

## Source and event lineage

- Pinned campaign ID: `adf91d042ab8f91678834b9258bfde70022a763dfda8c91d1e94be334583aa46`
- Campaign file SHA256: `aa8acb2b46823c1a1e3ac5d01a57dde917746c2c7471098ae2a4598875e322f5`
- Analysis code SHA256: `9f9e2249b49dd1cb10c11713aa2683567aa9cf0914c3ed2b08cf8e3fea25ebf8`
- Latest processed prefix catalog SHA256: `8758862c83e91a2a7a7724b743d908ef498701f8f362fb9f2a6eea17fedfed97`
- Latest event digest: `edbd15787a962be08e891c720e2218b9a9d56aafc02b5968c647ce4a935b3150`
- Cumulative event-chain SHA256: `48fb641da6177335100d900982599613b6103ebbe4a2452841f6a3103c352d6d`
- Latest event file SHA256: `fe08a207068277dbb8d7f89f81d5e6e7386723d79344ad4f047afb212680c714`
- State digest: `0738240335cdda3b86f1eeaf2c7ea5924ffae15ce14e94572522616b5c0bd961`
- State file SHA256: `857a4cda41a2e5bc96b9ed5db459e762aaf29b326fe974b520ef527152742880`
- Summary digest: `31d4c8d547e3f3ea24c0139252cba5a179e4a7194a421d24cd583c956ee48eef`
- Summary file SHA256: `398d0ffaf29fd2f6e0bbbaf615948361a45b64c9d5d8834fe0a1cc4bfde45c77`
- Observatory data root: 6,731,472 bytes, below its 1 GiB limit.

## Ninth public snapshot and cumulative qualification

The public scan `scan-20261015T073110Z-783cc56c1c57` was captured at
07:31:10 UTC, with evidence SHA256
`783cc56c1c57a96e532b8b9beae35de408f2e5cbba2e522ea3ebb36b29c539f4`. It
contained 36 quality-valid pairs out of 40, with no positive candidate. The
snapshot analyzer indexed it by 07:31:15 UTC; nine snapshots are now processed
with zero pending. The panel spans about 92 minutes, with 360 selected
observations, 322 quality-valid pairs, 38 invalid pairs, and 149 distinct
markets.

The deterministic run
`VERITAS-M2-ECO-QUAL-001-RUN-76de7cc7f15e` found zero positive states at top
ask, 20-share full depth, per-leg minimum notional, or either fee sensitivity.
Its top-edge median was -0.025 per share; maximum was -0.001. This remains a
short, selected, correlated candidate-qualification panel, not fill or
profitability evidence.

## Operations and preservation

The source timer remains active and the oneshot is inactive after success. Its
next event is 08:10:03 UTC. The snapshot timer is active, with its next event
at 08:01:02 UTC. Both services retain their configured bounds and write only
to the Veritas observatory root.

The separate Reality checkout remains clean at `714f824`, and
`midas-reality.service` remains active. Source replay read finalized cataloged
`.seg` files only. It did not open `.open`, write the Reality tree, restart any
Reality service, or take a writer lock.

## Evidence and limitation

This is the second successful ordinary scheduled source recurrence. Together
with the earlier timer catch-up, the two scheduled executions show bounded
progress and state restoration across real finalized source segments. They do
not establish long-term timer reliability. Most replayable source remains
pending, and the processed prefix has no campaign-window observations. Keep
the read-only timer active and inspect later progress and resource use.
