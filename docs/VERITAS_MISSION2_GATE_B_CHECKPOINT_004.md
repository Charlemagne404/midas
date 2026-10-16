# Gate B checkpoint 004 — independent scan-50 source audit

**Captured:** 2026-10-16T04:37:25Z
**Mission status:** active; independent replay now covers the saved panel through scan 50.

The independent offline evaluator verified 50 snapshots / 2,000 selected
market-pair observations over 32,683,291 compressed bytes. It independently
recomputed 1,727 quality-valid states and reproduced every stored v4 validity
and top-edge decision with zero mismatches.

| Check | Result |
| --- | ---: |
| Independent valid states / stored valid states | 1,727 / 1,727 |
| Validity mismatches / top-edge mismatches | 0 / 0 |
| Strict reported-timestamp sensitivity | 374 states |
| At least one reported age over 5 seconds | 1,353 pairs |
| Positive top-pair gross states | 0 |
| Positive depth / both minimums / fee gates | 0 at quantities 5, 10, 20, 50, 100 |
| Candidate evidence / independent replay | Complete, 0 rows / complete, 0 rows |

Artifact: `docs/VERITAS_MISSION2_INDEPENDENT_OPPORTUNITY_AUDIT_004.json`
File SHA-256: `7989f40abc1cea41f23d78a3051c01bbf4d6ce5123f6b8e4153bfe07e5f1e0b7`
Result SHA-256: `bd693917c3c15f61002cfb67caf0699e686535b7927e608b730d170bb3fa74b9`
Source-manifest SHA-256: `1ea318aef7a09a519fe8f3d91e129ecd39c4f183db4b793ed6a7619be61eeee4`

The 374-state filter is based on reported book age (at most 5 seconds),
reported pair skew (at most 250 ms), and same-response receipt. It does not
prove sequence freshness, atomicity, persistence, or executable quotes. This
audit is selected intermittent evidence, not a venue census, strategy-P&L
comparison, or fill result. No authenticated requests or orders were used.
