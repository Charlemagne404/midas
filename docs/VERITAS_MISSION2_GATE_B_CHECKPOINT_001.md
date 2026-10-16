# Gate B checkpoint 001 — independent source opportunity audit

**Captured:** 2026-10-16 02:48 UTC

**Mission status:** active; no candidate or strategy is promoted.

## Independent audit of the saved panel

The new bounded audit in `source_opportunity_audit.py` and
`audit_veritas_source_opportunities.py` replayed all 46 immutable public
snapshots. It verified the stored snapshot evidence, hashed Gamma and CLOB
responses, per-snapshot v4 event digests, and the identity of each selected
market and its books. The 30,058,744 compressed source bytes covered 1,840
selected market observations.

For all 1,600 pairs classified as quality-valid by the stored v4 analysis,
the independent v2 recomputation reproduced both validity and the top-pair
gross edge: **zero validity mismatches and zero edge mismatches**. The v2 path
found 1,600 valid observations, of which 349 pass the conservative
reported-age / timestamp-skew sensitivity. The remaining 1,251 have at least
one reported book update age above five seconds; none of the 1,600 valid pairs
exceeded the 250 ms reported timestamp-skew threshold. This sensitivity is a
diagnostic only. It does not establish sequence ordering, upstream freshness,
or batch atomicity.

There were **zero positive gross top-pair candidates**. Positive full-depth
gross, both-minimum, single-match fee, fragmentation-safe fee, and combined
fee-sensitivity counts were also zero at each tested size: 5, 10, 20, 50,
and 100 shares per leg. No authenticated requests or orders were used. The
saved panel is selected and intermittent, so these counts do not estimate
venue-wide prevalence or quote persistence.

| Evidence | Result |
| --- | --- |
| Snapshot / selected pair count | 46 / 1,840 |
| v4 quality-valid / independent v2-valid | 1,600 / 1,600 |
| Validity / top-edge mismatches | 0 / 0 |
| Strict reported-timestamp sensitivity | 349 / 1,600 |
| Positive gross / depth / both-minimum / fee gates | 0 at all five sizes |
| Source-manifest digest | `48cb2a60aaff815960311542660597288ead54187d6c98052114e0ac495e4cc4` |
| Audit result digest | `6cace7fd04f86a0e3c8a3da9e4abf0cc8de0bc9e1988ddff00453d573db45c0c` |
| Artifact file SHA-256 | `17326dba3160bc9bd6c3de03cbc1d5a78361cb4ff99d7a6f75cb2b0b185d8617` |

See [the full source audit artifact](VERITAS_MISSION2_INDEPENDENT_OPPORTUNITY_AUDIT_001.json).

## Market constraint semantics

A second read-only audit compared the raw Gamma market constraints with both
stored CLOB book legs across the same 46 snapshots. It examined 3,680 book
legs. The minimum values were numerically equal in all 3,680 comparisons, and
the tick values were numerically equal in all 3,680 comparisons. The audit
keeps Gamma `orderMinSize` denominated in USDC and CLOB `min_order_size`
denominated in shares; equality of their numeric strings does not make those
units interchangeable.

The constraint artifact reports result digest
`498865433c62ff10d2028744467c03a275ae3ee26de958839f8a37caf8aacf1c` and file
SHA-256
`ac8afaced1e113bc6e2e8ff47b16d53c5ab9a51f7bd5273805bfbcad12370302`. See
[the full constraint audit](VERITAS_MISSION2_MARKET_CONSTRAINT_AUDIT_001.json).

## Mathematics, fixtures, and implementation limits

The independent pair evaluator supports only an explicitly normalized
same-condition V1 YES/NO pair. It reconstructs asks from the saved raw CLOB
response, sorts price levels, walks requested quantities, checks tick and
minimum constraints, and evaluates fee sensitivities. The adversarial
fixtures cover tiny positive, zero, and negative edges; depth shortfall;
positive gross erased by fees; unsupported protocol/outcome semantics;
off-tick and conflicting constraints; old and skewed timestamps; slow
capture; wrong-condition books; and a positive, source-attested synthetic
case. A synthetic fixture is a detector check, not a market observation.

The independent arithmetic does not call the existing raw-funnel detector or
its depth walker. It does reuse the versioned fee evaluator after its own
price, depth, and constraint calculations, and uses shared source-validation
helpers to verify response lineage. The audit does not claim independently
confirmed fills, venue sequence, settlement, or realized returns. Previously
studied complete-outcome baskets remain negative or fail freshness checks;
this checkpoint does not add a new payoff structure.

One integration issue found during audit construction was that older snapshot
files preserve their original audit schema while v4 quality decisions live
in separately hashed v4 event files. The audit now compares its recomputation
to the v4 event rather than treating legacy snapshot fields as v4 results.
The corrected path passes the synthetic legacy-schema fixture and reproduces
the live panel with zero mismatches.

The focused Veritas and affected Arena suite passed **77 tests**. Ruff lint,
Ruff format check, strict Mypy on nine changed source files, and
`git diff --check` passed. No full regression or training job was run.

## Decision

Keep the no-trade policy. Gate B has a verified independent audit for the
supported same-condition V1 pair path, but it remains in progress because
broader payoff structures and independent venue-time freshness are not
qualified. Continue bounded observation and preserve any future positive
source row for complete-depth, minimum, fee, and freshness replay.
