# Gate A checkpoint 019 — scan 21 and source replay progress

**Captured:** 2026-10-15 14:21 UTC

**Branch:** `project/veritas`

**Checkpoint base:** `5dd9b4e`

## Prospective discovery and economics

The scheduled 14:01:50 UTC scan,
`scan-20261015T140150Z-b4ba652d6e9c`, is the 21st finalized v4 snapshot.
Six bounded Gamma frames returned 300 records and 300 unique IDs. The union
contains 198 supported same-condition V1 pairs and 102 explicit exclusions
(33 augmented NegRisk records and 69 unsupported outcome relationships); no
duplicates or identity conflicts were recorded.

The 40-market selection retained all three available frozen controls and
selected 37 rotating markets. It overlaps scan 20 on eight IDs, five of them
rotating, so 32 rotating selections changed. Liquidity counts were 14 high / 11
medium / 15 low; expiry counts were 17 near / 18 medium / 5 long; spread
counts were 13 tight / 13 medium / 14 wide. Selection used the
`snapshot_change` phase. All selection probabilities remain conditional on
the bounded response union and frozen controls.

Thirty-seven pairs passed the current request/receipt quality gate; three had
empty No ask sides. Nine of 40 passed the older reported age/skew gate. The
valid top-edge range was -$0.368 to -$0.001 per share, with a nearest-rank
median of -$0.032. No top-ask, full-depth, per-leg minimum, single-match fee,
or fragmentation-safe fee gate was positive.

Across 21 scans, the cumulative sample has 840 selected observations, 751
quality-valid pairs, 89 invalid pairs, and 367 distinct markets. The prior
reported-age/skew gate accepts 176 pairs. Paired recovery is 575/840 (68.45
percentage points). The cumulative edge range remains -$0.984 to -$0.001 per
share, with a nearest-rank median of -$0.024. These remain selected,
intermittent observations, not independent opportunity counts or a venue-wide
census.

Snapshot evidence SHA256 is
`b4ba652d6e9c94e9fcf69e49de2cf60263263711c94fee487cf4b16f91fc1e7e`; the
compressed snapshot file SHA256 is
`b3299fd25499bc427f81300f017386e97b512541e9381af8343815b905694f93`. The v4
analysis event SHA256 is
`654efc549f84d9fe490541f1314d022f3a02ff6d67795609941fa8771a28e6e8`; its
file SHA256 is
`16eb9dc834bbd321ab39d1535aed02929ceca1d1a7b4a01234264cea89cf9285`. The
21-snapshot research summary digest is
`c69b4e9c97115c8d836fbd302d143d51ca99e97e3a13fa567e5b18813b68580d`; its
file SHA256 is
`dd3c0b2d573505d2a68fc4289db15836910f28f72399d2879af8f48dfdfae4fd`.

## Finalized-source replay

The 14:10:29 UTC scheduled replay completed at 14:13:56 UTC. It processed 128
finalized segments / 32,886,676 source bytes in 207 seconds, using 10.37 CPU
seconds and 144,179,200 bytes peak memory. The prefix now covers 1,919 of 3,549
cataloged segments (449,729,433 bytes), through ordinal 231,603; 1,630
finalized segments / 430,839,649 bytes remain pending.

The cumulative summary counts 40,459 campaign-window frame records, 30,809
touched market-frame states, and 29,749 quality-valid states. Positive
top-ask and full-depth states remain zero. The replay remains partial and
reads only finalized `.seg` files. Its sealed summary digest is
`ed121aceb771923c0070d648c18794e6b1ff378bce7a17afcba4e8f827614495`; the
summary file SHA256 is
`46687b98f003d93c39e753dad4adc33774b020f042d1b36a1b3dc39358106c3a`. The
state file SHA256 is
`868bc144014234239ce97c5c636ffb5a6088440537c2be4022bd2e03fb55a045`.

## Director qualification

The 14:15:40 UTC Director cycle recorded the completed scan 20 qualification,
admitted scan 21 as job `job-979f118b02764225b23ad87b`, and consumed the 14:13
finalized-source summary. Arena completed all 21 events at 14:16:20 UTC in
1.214 seconds. Finding `veritas-qualification-v1-e46e192a082956ab` reports no
positive gross candidate. Its finding manifest SHA256 is
`a96e0e029ce83e2c181aebcaa2b38ef1fc5b816d45fb4a510d5bdbd7f6f8847c`; the
dataset SHA256 is
`fe9b2295cd75246167ad23e6fff017c424f74581036afed3f23f90ee103f6ab6`; the
experiment SHA256 is
`9047457176fb94a8ff5afddc0949b568f47d5ad3ee08b45f5cf8a29e1bef1ae3`.

The Arena job and finding are complete. The Director manifest last updated at
14:16:04 UTC still projects the scan 21 job as `QUEUED` and scan 20 as last
qualified. The append-only Director events record scan 20 completion at
14:16:05 UTC and scan 21 admission at 14:16:07 UTC. The 14:45:16 UTC scheduled
cycle is the next reconciliation point. No manual poll or retry was started.

The observer, source-analysis, and Director timers remain active. Their next
scheduled UTC runs are 14:31:26, 14:40:15, and 14:45:16. Mission 2 remains
active. Preserve the bounded sampling limits, corrected source-window
interpretation, and unchanged zero-exposure baseline. Current state is in
[research inventory 022](VERITAS_MISSION2_RESEARCH_INVENTORY_022.json),
[operations](VERITAS_MISSION2_OPERATIONS.md), and
[engineering](VERITAS_MISSION2_ENGINEERING.md).
