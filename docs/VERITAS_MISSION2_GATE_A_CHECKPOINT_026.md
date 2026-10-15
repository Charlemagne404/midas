# Gate A checkpoint 026 — scan 29 market discovery

**Captured:** 2026-10-15T18:04:20Z
**Mission status:** active; the collector continues on its scheduled timer.

## Discovery and selection

Scan `scan-20261015T180052Z-f40aae162609` completed at 2026-10-15T18:00:52.714647+00:00. The six-frame
stratified query returned 300 records,
296 unique IDs, and
4 identical duplicates.
Of those IDs, 189 passed the current
same-condition V1 binary eligibility gate; 107
were excluded (42
with unverified augmented NegRisk semantics and
65
with unsupported outcome relationships).

The category-phase selection retained 40 markets: 37 rotating stratified
selections and three frozen random controls. Selection probabilities are
conditional on the bounded query-response union and the frozen control cohort.
The current scan reports category and selection strata; it does not report
liquidity, expiry, or spread distributions, so those values are not inferred
from this scan. The public snapshot is intermittent coverage, not a continuous
feed.

## Observation and economic result

The scan attempted 40 market pairs; 38 passed the current quality gate. It
used seven public HTTP reads, with no authenticated request or order. The
29-snapshot panel now contains 1,160 selected pairs, 1,034 quality-valid pairs,
and 536 distinct market IDs. Its maximum top-pair gross edge remains -0.001
per share, median -0.022, and positive count zero. No positive top-ask,
full-depth, per-leg minimum, single-match fee, or fragmentation-safe fee state
has appeared. The read-only v3 comparison has zero candidate rows and a
complete empty-replay status; the scheduled Arena finding for scan 28 remains
v2 until the next Director cycle persists a v3 result.

## Source evidence

- Snapshot evidence SHA-256: `f40aae1626099a2d7bc5b5b36a236f81d8f2a1b5f3789100f8434c8aa5ff0789`
- Compressed snapshot file SHA-256: `b527f6b2b1ad5a24a29861dabbf0a3c08bd46c99de2933e5aa164c50b3ae0b30`
- Analysis event SHA-256: `5b1978ae55e0e998c9c516de8fee42dec8387cbf1ce2db1956a6d6b85e2db7c4`
- Analysis event file SHA-256: `dec04c2a0a14a81c2a3b5e53ffd65c63c114ce259606b2b988c88dc6fe98a392`
- Read-only v3 run: `VERITAS-M2-ECO-QUAL-001-V3-RUN-fd9b0c1cdc06`
- v3 result SHA-256: `e927ea7eecf94823b098d51746021f0e1915c55006de0de7118b51a6d6528e0b`

The query union is not the venue-wide market universe. Excluded contract
structures remain outside the current economic claim; the negative result
applies to this bounded, selected and repeated public sample only. See
[inventory 030](VERITAS_MISSION2_RESEARCH_INVENTORY_030.json) for the complete
selection record and [Gate D checkpoint 002](VERITAS_MISSION2_GATE_D_CHECKPOINT_002.md)
for candidate source replay and tests.

## Gate A measurement update — 29-snapshot paired yield

The v4 event panel now contains 1,160 selected market observations. The prior
reported-age/skew rule accepts 240 pairs (20.69%); the current bounded
request-to-receipt rule accepts 1,034 (89.14%), recovering 794 observations
and +68.45 percentage points. This compares the two gates on the same selected
panel. The improvement is a measurement-yield result: request/receipt timing
does not prove venue sequence, atomicity, or upstream queue age. The panel is
repeated and correlated, and still contains zero positive gross candidates.
See [inventory 033](VERITAS_MISSION2_RESEARCH_INVENTORY_033.json) for the
versioned summary and source hashes.
