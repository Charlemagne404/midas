# Gate C checkpoint 002 — first coverage-pilot observation

**Captured:** 2026-10-15 19:07 UTC
**Mission status:** active. The fixed pilot is running; this is its first scheduled scan.

## Protocol and deployment

`VERITAS-M2-COVERAGE-PILOT-001` began with the first scheduled observer scan
after commit `de3f764`. It has a fixed 24-hour window ending
2026-10-16 19:00:55 UTC, a 48-scan cap, no early stop, and no historical
backfill. It reuses the observer's six bounded Gamma query frames and one
batched public books read, adding zero network requests. The pilot records
selected slots as the denominator, retains invalid pairs, and compares frozen
stable controls with rotating stratified selections descriptively. It does not
modify the Reality campaign or submit orders. The frozen protocol is in
[`coverage pilot plan 001`](VERITAS_MISSION2_COVERAGE_PILOT_001.json).

## First scheduled observation

Scan `scan-20261015T190055Z-7799523b9d87` completed at
`2026-10-15T19:00:55.062293Z`:

- The bounded discovery union contained 300 unique market IDs; 122 were
  eligible same-condition V1 binary pairs and 178 were excluded (128
  unverified augmented negative-risk semantics; 50 unsupported outcome
  relationships).
- The selected cohort contained 40 pairs: 32 passed the existing v4 quality
  gate (80%), while eight failed because one outcome had an empty ask side.
- Of the selected pairs, 37 were rotating and three were available stable
  controls. Rotating yield was 31/37 (83.8%); control yield was 1/3 (33.3%).
  This split is small, non-randomized, and descriptive; it is not evidence of
  causal or venue-wide improvement.
- There were zero positive top-gross states and zero positive full-depth,
  minimum-notional, single-match-fee, or fragmentation-safe-fee states.
- Collection used seven public HTTP attempts. The observer completed normally;
  no additional requests were made for the pilot.

## Evidence lineage

- Snapshot evidence SHA256: `7799523b9d87861de0cf06cc33d7387fb24a87aef75d5991d1b0bdb860af8a57`
- Compressed snapshot file SHA256: `11592446ba9f057de9c8fddab7295dd027d8a61fed4cc2106db14421a6315d3d`
- v4 analysis event SHA256: `c6e1707fee02857610b0828ad5853d71020db0737aa2f3ad1a8c285b011bb5ed`
- Pilot event SHA256: `cd9adf78a361e87a0a1e7ad8a8f09df7087ab874ebbe8a6becf1d33d845b6ce4`
- Pilot summary SHA256: `1aca0353079032f25b8c8cf7aabb92e8f540b7d513262672424a6c46e5864859`
- Frozen plan SHA256: `d35f25ef84037f3e9cabf4343e9a01db381b73e8fa6cae0fd0b5fc6e07e279ba`
- Pinned pilot implementation SHA256: `2cf59cebbb72c0e2990ebfe5c40e53b967e867fff5321f0d1e8c4e9a9207284e`

The persisted pilot summary reports one completed scan, 40 selected slots,
32 quality-valid pairs, eight invalid pairs, and zero missed scan sequences.
It remains `running`. The next scan is scheduled for 19:30:19 UTC. The event
and summary are under
`data/veritas-observatory/measurement-pilots/VERITAS-M2-COVERAGE-PILOT-001/`.

## Interpretation and remaining work

This is a prospective measurement result, not a strategy trial. The bounded
query union is selected; controls were frozen from earlier discovery and are
not randomized against rotating markets. Intermittent snapshots do not
establish continuous quote coverage, quote lifetime, independent sequence
freshness, fills, or profitability. Keep the pilot running through its fixed
window, preserve the pinned implementation, and assess coverage and missing
scan sequences only after the window completes. The original 48-hour
follow-up-study readiness gates remain unchanged.
