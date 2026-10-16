# Gate F checkpoint 005 — scheduled qualification of scan 17

**Captured:** 2026-10-15 12:16 UTC
**Branch:** `project/veritas`
**Checkpoint base:** `1342e6a`

## Scan-pinned qualification

At 12:15 UTC the Research Director admitted one bounded Arena qualification
for scan `scan-20261015T120127Z-af0847c75aeb`. Job
`job-97c08fcee4f0407b88c06ca1` consumed the 17 finalized v4 events and
completed in 0.902 seconds, reading 311,541 source bytes. Its submitted source
revision `e78a95e2b3d9c9e4fe8e9a8fcf83da697b8bb17a3d1e65ba3a905aafdd2637cd`
matched the revision used by the worker. Progress reached 17/17.

The job created finding `veritas-qualification-v1-4158e04dd04c8f4f`, whose
manifest SHA256 is
`8fa44c0913e1b23fcd40179c53df56ca0cd715ff060a675ed76c1880e1a36c00`. Its
experiment run is `VERITAS-M2-ECO-QUAL-001-RUN-a8fa16980163`, experiment
SHA256 `e7a71da3adf4b4701e57edefd03aa69f8cfb5b56d6a3e7bc9d15775540288baa`,
and dataset SHA256
`a8fa1698016316f4336a9406f138ae0585e9feeeb6eaa2abd2db57595a220a58`.

Across 680 selected observations, 613 pairs passed the request/receipt
quality gate, covering 284 distinct market IDs. The unchanged top-ask gross
sign, full displayed depth, minimum-notional, single-match fee sensitivity,
and fragmentation-safe fee sensitivity gates each have zero positive states.
The reproducible comparison therefore retains the no-trade decision and does
not support a strategy tournament or model training.

## Reconciliation and source replay

A 12:16:33 UTC no-launch Director cycle verified the completed finding and the
sealed source-replay summary, set the Director to `CURRENT`, and admitted no
additional job. There are no active or queued qualification jobs. The
Director's latest manifest SHA256 is
`dd266f1c0e6d8a434ed5dabf0e2d80eb0f61e912542208b62a151f4b96318cad`.

The 12:10 UTC finalized-source replay processed 122 segments / 33,266,456
bytes in 159 seconds, using 7.970 CPU seconds and 136.4 MiB peak memory. Its
sealed digest is
`12ae77298aaca26f5b402ac9548983a6b34e4e0d7414d1d1a1b8ac858800bf0d`.
The prefix contains 1,438 of 3,313 cataloged segments, with 1,875 segments /
504,775,332 bytes pending through ordinal 166,686 and zero campaign-window
frame records. It remains `catching_up_finalized_source`.

The live read-only activity projection returned eight digest-verified events
from the 19-file Director archive, marked history truncated, and reported zero
invalid artifacts and zero active jobs. No Reality service or protected
campaign data was changed. Mission 2 remains active. See [research inventory
017](VERITAS_MISSION2_RESEARCH_INVENTORY_017.json) and [operations](VERITAS_MISSION2_OPERATIONS.md).
