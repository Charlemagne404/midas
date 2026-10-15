# Mission 2 Measurement Comparison 002 — Paired Freshness-Gate Yield

**Protocol ID:** `VERITAS-M2-MEASURE-COMPARE-002`
**Analyzer:** `veritas-finalized-snapshot-analysis-v4`
**Mode:** read-only repeated classification of finalized public snapshots
**Decision:** no trading or campaign-policy change

## Question

On the same selected YES/NO book payloads, how many observations pass the repaired request-to-receipt freshness gate compared with the previous rule requiring both reported book ages to be at most five seconds and cross-outcome update timestamp skew to be at most 250 ms?

## Paired classification

Each finalized snapshot market pair is classified by both gate definitions. The current pair/identity, market-status, and nonempty ask checks are shared. The legacy classification additionally applies the prior reported-age and skew limits. The repaired classification uses bounded request-to-receipt duration and retains reported age/skew as diagnostics. Counts, failure reasons, and denominators are cumulative and also stored per market.

Every newly finalized snapshot indexed by v4 receives both classifications automatically. The first v4 indexing pass also reprocessed ten already finalized scans; therefore the initial effect estimate is retrospective on those stored payloads. Future scheduled scans after v4 deployment form the ongoing prospective series under the unchanged 40-market observer. No extra API polling, source writer access, or campaign sampling change is introduced.

## Current evidence and interpretation

The initial ten-snapshot retrospective pass accepted 91/400 observations (22.8%) under the legacy rule and 359/400 (89.8%) under the repaired rule. After one scheduled prospective scan, cumulative yield is 98/440 (22.3%) versus 396/440 (90.0%), or 298 additional valid classifications (+67.7 percentage points). The 44 remaining invalid pairs have an empty ask side. No positive gross candidate was observed.

This is a measurement-yield comparison, not a causal strategy experiment and not a quote-availability guarantee. Request-to-receipt time does not prove response-batch atomicity, venue sequence, upstream queue age, or order arrival. The sample is selected, sparse, and time-correlated. Activity fingerprints are compared only between sampled snapshots.

## Monitoring and stop conditions

The existing 30-minute observer and analyzer timers continue with their current resource and request limits. Record snapshot counts, per-market gate outcomes, invalid reasons, reported age/skew diagnostics, analysis event hashes, and service exits. Stop interpreting a cohort segment if event/source identity checks fail, request bounds are exceeded, the snapshot hash fails, or any protected-system behavior is affected. Preserve all prior analyzer versions and campaign records.

This protocol does not waive the separate 48-hour follow-up-design or dependence gates. It remains an engineering measurement pilot; candidate qualification and any future execution research require separate evidence.
