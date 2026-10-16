# Gate B checkpoint 002 — independent replay through scan 47

**Captured:** 2026-10-16 03:19 UTC

**Mission status:** active; the supported pair path remains no-trade.

## Expanded immutable-source replay

At 03:17:32 UTC, the existing independent source-audit runner replayed all 47
saved public snapshots from `data/veritas-observatory`. It verified the saved
snapshot evidence, retained Gamma and CLOB payloads, selected-market identity,
book payload lineage, and per-snapshot v4 analysis-event lineage over
30,697,840 compressed source bytes. The replay was offline; it made no public
HTTP requests and did not modify any snapshot or analysis event.

The independent v2 evaluator reproduced the v4 quality and top-edge results
for all 1,880 selected observations: 1,628 valid states and zero validity or
top-edge mismatches. Under the conservative reported-timestamp sensitivity,
353 states pass the 5-second per-leg age and 250 ms pair-skew bounds. Another
1,275 states have at least one reported book age above five seconds; no pair
exceeds the reported skew bound. This timestamp sensitivity does not prove
venue sequence, upstream freshness, or atomic quotes.

There were zero positive top-pair gross states and zero positive full-depth,
both-minimum, single-match-fee, or fragmentation-safe-fee states at each
quantity: 5, 10, 20, 50, and 100 shares per leg. The 47-snapshot sample is
selected and intermittent. It does not establish venue-wide prevalence,
persistence, order arrival, fills, or profitability.

| Evidence | Result |
| --- | ---: |
| Saved snapshots / selected observations | 47 / 1,880 |
| v4 valid / independent v2 valid | 1,628 / 1,628 |
| Validity / top-edge mismatches | 0 / 0 |
| Conservative timestamp sensitivity | 353 / 1,628 |
| Positive gross / depth / both-minimum / fee gates | 0 at all five quantities |
| Source manifest digest | `e100c2c25b23a74f765499648c501b2dc456dead48625de30b948db240ca5cd8` |
| Audit result digest | `7cf0b2b3c887de4037ae2a470e31dedf2a9f7b407487f23bc5ebede7b6e84a1d` |
| Artifact file SHA-256 | `552a6ac301dff6c863be7f322604168781a87c1fe0a0347e5dcb69c457e1a6dd` |

See the [full replay artifact](VERITAS_MISSION2_INDEPENDENT_OPPORTUNITY_AUDIT_002.json)
and the [46-snapshot baseline](VERITAS_MISSION2_GATE_B_CHECKPOINT_001.md).
No production analysis code changed in this replay; no new test suite was run.
