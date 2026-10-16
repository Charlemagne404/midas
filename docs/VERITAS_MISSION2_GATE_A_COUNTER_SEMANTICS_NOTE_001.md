# Gate A note 001 — first-scan validity counter semantics

**Reviewed:** 2026-10-16 06:25 UTC
**Status:** counter mismatch explained by unlike fields; analyzer labeling follow-up remains open.

The A1 coverage replay labels one 5-versus-32 difference as a capture-versus-current-replay quality mismatch. A read-only check of the paired saved records shows that the two values come from different counters:

| Saved record | Field | Value |
| --- | --- | ---: |
| Compressed observer snapshot | `counts.valid_quality_pairs` | 5 |
| Same-scan v4 analysis event | `valid_quality_pairs` | 32 |
| Same-scan v4 analysis event | `legacy_freshness_valid_pairs` | 5 |
| Same-scan v4 event | pairs with reported age over 5 seconds | 27 |

The snapshot counter value of 5 exactly matches the paired v4 event's legacy freshness count. The v4 event's 32 quality-valid pairs are independently reproduced by the v2 audit. Snapshot, Gamma, CLOB, and analysis-event source hashes verified. This points to a counter-semantics mismatch, rather than missing or corrupted payloads. It does not establish the complete historical producer semantics for the snapshot counter.

The current coverage implementation reads the stored count from the snapshot and compares it with the v4 event's current `valid_quality_pairs` (`packages/midas/veritas/universe_coverage.py`, around lines 186 and 502–513). The field name `capture_recorded_quality_valid_pairs` therefore overstates comparability for this first scan. For the 52 other scans, the snapshot count and v4 event count agree. Across the panel, 1,791 is the sum of snapshot-stored counters; 1,818 is the sum of v4 event counters and current replay quality-valid pairs.

Keep artifact 007 immutable and preserve both recorded values. After the pending scan-53 Director reconciliation, revise the A1 analyzer to report snapshot-stored counters and v4 event counters separately, then write a successor artifact. Do not rewrite historical source records or treat the 27 as unexplained data loss.

| Evidence | SHA-256 |
| --- | --- |
| Snapshot file | `208b6918879bf46972fbc1c7fc282096ef88ee27177450362fafb3eb28a8e66c` |
| Snapshot evidence | `c9777c1cc30036411ffd05d2b1188b0a15134193543360844c0f989641a7249e` |
| V4 analysis-event file | `d95c33694447b649a64c2dface7a90ea906ad41511f114400c0648739af35a8e` |
| V4 analysis event | `bc9e3b0a127eabb533f47dd23e8b7494a341b7a4f02026d60901cdaa4e598bb1` |

Paths: `data/veritas-observatory/snapshots/scan-20261015T055928Z-c9777c1cc300.json.gz` and `data/veritas-observatory/analysis-events/v4/scan-20261015T055928Z-c9777c1cc300.json`. No code, services, campaign, or research job was changed for this review.
