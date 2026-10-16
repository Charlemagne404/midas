# Gate B checkpoint 016 — independent replay through scan 79

**Captured:** 2026-10-16 UTC after the 19:03 A1 coverage replay

**Mission status:** active; no quality-valid positive gross candidate observed.

## Independent public-source replay

Audit 017 independently replays 79 saved observer snapshots / 3,160 selected
market observations. The additional scan contributes 39 quality-valid states.
Independent v3 replay agrees with stored v4 on all 2,667 valid decisions and
top edges: validity mismatches 0, edge mismatches 0. It checks 3,497 fee
calculations with zero disagreements.

| Check | Result |
| --- | ---: |
| Stored v4 / independent v3 quality-valid states | 2,667 / 2,667 |
| Validity mismatches / top-edge mismatches | 0 / 0 |
| Independent fee checks / disagreements | 3,497 / 0 |
| Strict reported-timestamp sensitivity states | 578 |
| Pairs with reported age over 5 seconds on a leg | 2,088 |
| Pair timestamp skew over 250 ms | 1 |
| Positive top-pair gross states | 0 |
| Positive full-depth gross states at quantities 5, 10, 20, 50, 100 | 0 at each quantity |
| Positive states after minimums and fee sensitivities | 0 at every quantity and gate |
| Strict-freshness positive states | 0 at every tested gate |

Compared with audit 016, the new scan adds 39 valid and nine strict-freshness
states; the age-over-five-seconds count increases by 30 and reported skew
exceedances remain one. These are selected, intermittent, correlated public
snapshots, not independent opportunity trials. Timestamp age is a sensitivity
measure, not proof of book freshness. Fee results are model calculations, not
executed fills.

## Evidence and decision

- Independent replay: [audit 017](VERITAS_MISSION2_INDEPENDENT_OPPORTUNITY_AUDIT_017.json)
- Artifact file SHA-256: `6738e93868506b1a9a6b49e088b28a977901d121dd167e064fd3256fdfcf5b86`
- Result SHA-256: `c4ff5dd90dcb4b20c60f890086c49ad6d5d1130831d18507d32e2718526ef0ee`
- Source manifest SHA-256: `fa30871efc93d98e5e31801424c2f558fe9abcd3affd0381b5226ea6936d83d4`
- Coverage corroboration: [A1 artifact 014](VERITAS_MISSION2_MARKET_UNIVERSE_COVERAGE_014.json)

Keep no-trade. This replay provides no candidate on which to test strategy
selection or train a model. Candidate-specific review becomes justified only
if a future quality-valid positive gross state appears.
