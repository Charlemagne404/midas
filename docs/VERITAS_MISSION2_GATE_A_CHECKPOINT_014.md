# Gate A checkpoint 014 — rotating discovery scan 17

**Captured:** 2026-10-15 12:01:32 UTC
**Branch:** `project/veritas`
**Checkpoint base:** `1342e6a`

## Bounded discovery and selection

The 12:01:27 scheduled scan, `scan-20261015T120127Z-af0847c75aeb`, completed
the six-frame rotating Gamma protocol and one public CLOB batch (seven HTTP
attempts total). The bounded 300-ID response union contained 200 supported
same-condition V1 binary pairs and 100 explicit exclusions: 82 augmented
NegRisk records and 18 unsupported outcome relationships.

The 40-market panel contained 37 rotating markets and three available frozen
controls. Liquidity strata were 13 high, 14 medium, and 13 low; expiry strata
were 20 near, 16 medium, and four long; spread strata were 9 tight, 22 medium,
and 9 wide. The panel is selected conditionally on the bounded response union;
it is not a venue-wide sample. The CLOB batch returned the complete unique
asset set in 300 ms. Batch atomicity, venue sequence, and upstream queue age
remain unverified.

Thirty-five selected pairs passed the request/receipt quality gate; eight also
passed the prior reported-age gate. No top-ask, full-depth, minimum-size,
single-match fee, or fragmentation-safe fee gate had a positive state. The
scan made no authenticated requests and submitted no orders.

## Cumulative evidence

Continuous v4 analysis now contains 17 finalized snapshots, 680 selected
observations, 613 quality-valid pairs, and 67 invalid pairs across 284 distinct
markets. The old reported-age/skew gate accepts 148/680. The paired recovery
is 465 observations, or 68.38 percentage points. All five positive gross
qualification counts remain zero. Across the 613 valid states, top-pair edge
ranges from -$0.984 to -$0.001 per share.

The immutable snapshot evidence SHA256 is
`af0847c75aebf8fb58dcef55ae8b1aa4cb88aa3afbf49d72c0255333c20ba9fe`; the v4
analysis event SHA256 is
`10496da3d0b1b2c8b503f45c028ecd09e1e2a90af72a379078d90f97b8334b25`. The
compressed snapshot file SHA256 is
`b0d8fe43f82c543729f7527811194dfb7dc1742e8769435d96821b5c1c8fc60b`, and the
analysis-event file SHA256 is
`92dd04f85a08c3d922bc5c1949a32c679e4d3987ccffecc6f36eb7be3334b0bf`.

## Scheduled qualification and independent source replay

The 12:15 Director cycle admitted one bounded Arena job for this scan.
`job-97c08fcee4f0407b88c06ca1` completed all 17 finalized events against the
committed source revision. It created finding
`veritas-qualification-v1-4158e04dd04c8f4f`, experiment run
`VERITAS-M2-ECO-QUAL-001-RUN-a8fa16980163`, and dataset SHA256
`a8fa1698016316f4336a9406f138ae0585e9feeeb6eaa2abd2db57595a220a58`. All five
qualification gates remain zero-positive. The no-launch poll verified the
finding and set the Director to `CURRENT` without admitting a second job.
Details are in [Gate F checkpoint
005](VERITAS_MISSION2_GATE_F_CHECKPOINT_005.md).

The 12:10 finalized-source recurrence processed 122 segments / 33,266,456
bytes. The prefix now covers 1,438/3,313 cataloged segments, with 1,875
pending / 504,775,332 bytes and zero campaign-window frames. Its sealed
summary digest is
`12ae77298aaca26f5b402ac9548983a6b34e4e0d7414d1d1a1b8ac858800bf0d`.
See [research inventory 017](VERITAS_MISSION2_RESEARCH_INVENTORY_017.json),
[operations](VERITAS_MISSION2_OPERATIONS.md), and the
[research backlog](VERITAS_RESEARCH_BACKLOG.md). Mission 2 remains active.
