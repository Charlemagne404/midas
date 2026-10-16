# Gate A checkpoint 052 — coverage-pilot inclusion support audit

**Captured:** 2026-10-16T07:36:47Z
**Mission status:** active; the immutable measurement-only pilot remains running.

## Audit

The new offline audit verifies the pilot's plan digest, append-only event chain,
each event's saved snapshot hash, v4 analysis-event hash, selected market rows,
quality-valid counts, and rotating-stratum inclusion probabilities. It uses only
retained local evidence; it makes no public requests and does not modify the
active pilot or Reality campaign.

| Measure | Result |
| --- | ---: |
| Pilot events | 25 / 48 scans |
| Source snapshots | 15,973,408 compressed bytes; all snapshot and analysis-event links verified |
| Selected pair slots / valid | 1,000 / 808 |
| Distinct selected markets | 587 |
| Rotating stratified | 779 / 931 valid (83.67%) |
| Frozen stable controls | 29 / 69 valid (42.03%) |
| Rotating population with positive inclusion support | 99.80% across scan-population exposure |
| Scans with full rotating-population support | 23 / 25 |
| Partially supported scans / unsupported scans | 2 / 0 |
| Skipped pilot sequence | 1 |

Across the 23 fully supported scans, the mean per-scan design-weighted
quality-valid yield for the rotating population was 82.96%. The supported-scan
weighted yields ranged from 66.65% to 95.72%. These are descriptive,
population-conditional measurements, not independent-trial confidence bounds.
Two scans in the category phase omitted positive-population strata; those
strata are disclosed and excluded from their design-weighted yield rather than
silently assigned zero validity.

The last included scan is `scan-20261016T073034Z-c97112eae9a3` (sequence 55,
07:30:34 UTC). Its bounded Gamma union contained 298 IDs, including 122
eligible markets; 40 were selected, 29 passed quality checks, and none had a
positive top-gross pair. The 55-scan A1 universe replay remains a separate
artifact; this audit does not extend it to scan 56.

## Interpretation and limits

The rotating yield is much higher than the frozen-control yield in this
sample, but the controls were frozen from an earlier query union, were
available in only 69 of 200 intended control slots, and were not randomized
against rotating markets. The difference is not a causal estimate of improved
selection. Selection probabilities and weighted yields apply only to positive-
probability strata within each bounded Gamma response union. They do not
estimate venue-wide availability, continuous coverage, update rates, quote
persistence, execution, or profitability.

The `snapshot_change` stratum measures state changes between intermittent
snapshots; it is not a WebSocket update-rate measure. The pilot remains fixed
through its existing end time and has not been changed.

## Evidence and verification

- Audit artifact: [coverage design audit 002](VERITAS_MISSION2_COVERAGE_DESIGN_AUDIT_002.json)
- Artifact file SHA-256: `6520390afc2fd8f4582c9b06bbc6a9e1908811daf11d0250ba80c3395d5820c4`
- Canonical artifact SHA-256: `1332780f05a6fc1b50a45e03feae39f158cef05c87b32cc1a6cc200b3052df95`
- Result SHA-256: `e9b1ab0856c74e79460ff995001ec10fef293035ef07a7ac9c056450a9e9f8be`
- Analysis source: `scripts/audit_veritas_coverage_design.py`
- Analysis source SHA-256: `2f582fe67a990e090a65d616e59ba4cdd147d86183fcf3e0c37aad4c6d138203`
- Ledger receipt: H125
- Focused tests: **4 passed**; Ruff and formatting checks passed; `git diff --check` passed.

Preliminary audit 001 is retained as an earlier pass. Audit 002 is the
authoritative rerun with its analysis-code digest included in the artifact.
