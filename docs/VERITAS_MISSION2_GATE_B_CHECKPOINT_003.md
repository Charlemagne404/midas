# Gate B checkpoint 003 — independent source replay through scan 49

**Captured:** 2026-10-16T04:14:35Z
**Mission status:** active; the independent detector agrees on saved scans, while freshness and execution remain unproven.

## Expanded replay

The read-only independent audit replayed all 49 saved public snapshots from data/veritas-observatory. It verified snapshot, Gamma, CLOB, selected-market, source-book, and analysis-event lineage across 32,003,727 compressed bytes.

| Evidence | Result |
| --- | ---: |
| Saved snapshots / selected observations | 49 / 1,960 |
| Independent v2 valid states / stored v4 valid states | 1,691 / 1,691 |
| Validity mismatches / top-edge mismatches | 0 / 0 |
| Conservative reported-age freshness sensitivity | 364 / 1,691 |
| Pairs with a reported age above five seconds | 1,327 |
| Positive top-pair gross states | 0 |
| Positive full-depth / minimum / fee states | 0 at each tested quantity (5, 10, 20, 50, 100 shares per leg) |

The latest scan contributes 40 selected pairs, 31 valid by v4 and independent v2, with zero top-pair gross positives. The 49-scan independent result has zero validity or top-edge mismatches. The conservative timestamp sensitivity admits 364 observations. Reported timestamp age is not sequence freshness, atomicity, persistence, or evidence of an executable quote.

## Provenance and limitations

- Result digest: 4ff66111b849891d28468062459a3315cfcfbe159659238c33ff73d4b731f0c5.
- Source manifest digest: 4f83b8613d053774df3a555e44d4115fb9d627f5d2ce070f99dc7f4d355d1e94.
- Audit implementation digest: 29354d4fb2bf1238e7b77154a8315564846af5b8cd1c902c89fdc832da3fb87d.
- Artifact file SHA-256: fa28e6b4a6cce926583ea41c96ef220a49347f35238f6b6bd2d12d51ce8a09e1.
- Artifact: [independent opportunity audit 003](VERITAS_MISSION2_INDEPENDENT_OPPORTUNITY_AUDIT_003.json).
- No authenticated requests or orders were used.

The sample remains selected and intermittent, limited to same-condition V1 pairs. Zero candidates do not prove venue-wide absence. Fee sensitivities do not establish arrival, fills, recovery, or profitability. No genuine positive candidate exercised the positive-candidate replay path. See [the 47-scan predecessor](VERITAS_MISSION2_INDEPENDENT_OPPORTUNITY_AUDIT_002.json) for the preserved prior artifact.
