# Gate G checkpoint 005 — coverage pilot visibility

**Captured:** 2026-10-15 19:41 UTC
**Source commit:** `a03a10c`
**Mission status:** active; the coverage pilot remains in progress.

## Implemented

The Veritas read-only API projects the current 24-hour coverage-pilot summary
at `/api/veritas/overview` and exposes the verified summary at the fixed
`/api/veritas/artifacts/coverage-pilot` route. Before projection, it checks
the summary digest, frozen plan hash, pinned pilot implementation digest,
current digest of the pinned source files, control-cohort hash, event IDs,
event hashes and chain, scan rows, totals, and sequence counters. Role and
stratum yields are derived from verified event rows.

The UI adds a “24-hour coverage pilot” panel with status, completed scans,
valid and invalid counts, per-role and per-stratum yields, the fixed study
window, missed sequences, latest scan and snapshot links, verified summary
access, and measurement-only limitations. It does not present the pilot as a
strategy test or claim fills. The feature is committed on `project/veritas`;
the running host UI/API was not restarted or deployed.

## Live pilot state

At capture, `VERITAS-M2-COVERAGE-PILOT-001` remained `running`, with two of a
maximum 48 scans complete. The fixed window ends at
`2026-10-16T19:00:55.062293Z`.

| Measure | Cumulative result |
| --- | ---: |
| Selected market-pair slots | 80 |
| Quality-valid pairs | 66 (82.5%) |
| Invalid pairs | 14 |
| Distinct selected market IDs | 70 |
| Missed scan sequences | 0 |
| Rotating stratified | 64/74 valid (86.5%) |
| Available stable controls | 2/6 valid (33.3%) |

The role comparison is descriptive. Only three of eight frozen controls were
available per scan; controls were not randomized against rotating markets.
The study adds no HTTP requests and does not establish continuous quote
coverage, independent sequence freshness, fills, or profitability.

Scan `scan-20261015T193035Z-7597bbb981fa` completed at
`2026-10-15T19:30:35.832304Z`. Six bounded discovery pages contained 300
unique IDs, of which 188 met the supported same-condition V1 eligibility
rule. Forty pairs were selected (37 rotating, three available controls); 34
passed the request/receipt quality gate and six had an empty ask side. The 112
other IDs were excluded: 46 for unverified augmented NegRisk semantics and 66
for unsupported outcome relationships. There were zero positive top-gross
pairs and zero missed pilot sequences.

## Evidence and verification

- Snapshot evidence SHA-256: `7597bbb981fa445b0d651e400dcba4754ad86821a0922c5794cd2c9875a47b3d`
- Compressed snapshot file SHA-256: `168f1699be0dc8abf2796d54c1c41edbbe44648a52566196e25cb719d50f2507`
- v4 analysis-event SHA-256: `14a941335ce3d61714e09a7560b9b62b8c51cf6986e952c323038ac20641c75f`
- v4 analysis-event file SHA-256: `040f405da892e6617f1ae3b90c65166a5ab2ee97bd521e1e75b3cb57ebf16290`
- Pilot event SHA-256: `d19266d72a6479e3fc7ad35cf4ddf301de125ba82feefabbb04cea9560aecf04`
- Pilot event file SHA-256: `6a9465a9e6a9b92a61694e90f29bdb8dd9f916fd4e46b4cfab38dc192984e9f4`
- Cumulative pilot summary SHA-256: `61d942c6335e573b394b5e1b692e01c4de3139d1dbcfe8b07f5e8a864225a97f`
- Frozen plan SHA-256: `d35f25ef84037f3e9cabf4343e9a01db381b73e8fa6cae0fd0b5fc6e07e279ba`
- Pinned implementation SHA-256: `2cf59cebbb72c0e2990ebfe5c40e53b967e867fff5321f0d1e8c4e9a9207284e`

Focused verification for commit `a03a10c`: 12 dashboard API tests and one
targeted Veritas UI test passed. Ruff lint/format, strict Mypy for the changed
API module, TypeScript, ESLint, Prettier, and the production build passed; the
existing Vite large-chunk advisory remains. A read-only validation of the live
pilot summary passed. The new panel was not browser-tested in this checkpoint,
and no full Mission 2 regression suite was run.

Mission 2 remains active. Leave the pilot on its fixed schedule and interpret
its results as measurement coverage only.
