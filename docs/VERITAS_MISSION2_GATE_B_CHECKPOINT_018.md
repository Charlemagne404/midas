# Gate B checkpoint 018 — independent audit through scan 84

**Captured:** 2026-10-16 21:53 UTC  
**Experiment:** `VERITAS-M2-INDEPENDENT-SOURCE-AUDIT-002`  
**Status:** Independent arithmetic and stored-analysis comparison verified through the current 84-scan panel; no positive candidate observed.

## Scope and reproduction

The existing independent v3 audit runner was applied to every immutable saved
public snapshot in `data/veritas-observatory/snapshots`. It read 84 snapshots,
3,360 selected market-pair observations, and 53,961,165 compressed source
bytes. The versioned result is
[audit 020](VERITAS_MISSION2_INDEPENDENT_OPPORTUNITY_AUDIT_020.json); its file
SHA-256 is
`1791541daa965492f37363ce8d70aea714bb8938a09eef4fd2511d59b4546738` and its
internal result digest is
`f4a807d5f393deb21ead9565151b52d33acf5e20abaf9a9c07efddbb02365ced`.
The ledger receipt is hypothesis H154.

## Results

| Check | Result |
| --- | ---: |
| Independent quality-valid states | 2,845 |
| Stored v4 vs independent v3 validity mismatches | 0 |
| Stored v4 vs independent v3 top-edge mismatches | 0 |
| Independent fee calculations | 3,768 |
| Fee disagreements | 0 |
| Strict reported-age and pair-skew sensitivity states | 622 |
| Pairs exceeding the five-second reported-age bound | 2,222 |
| Pairs exceeding the 250 ms reported timestamp-skew bound | 1 |
| Positive best-ask gross candidates | 0 |
| Positive full-depth candidates at 5, 10, 20, 50, or 100 shares | 0 at every quantity |
| Positive after per-leg minimum and fee sensitivities | 0 |

The strict-freshness sensitivity is based on returned timestamps. It does not
establish upstream sequence freshness, atomicity, quote persistence, or
execution. The fee calculations are qualification arithmetic and do not
represent hypothetical or actual fills. These 3,360 observations are repeated
selected snapshots, not 3,360 independent opportunity trials. The first-scan
capture/replay count discrepancy remains a separately disclosed limitation.

## Decision

Keep the current no-trade posture while the scheduled, broad stratified
observer continues. The independent result confirms that the supported
same-condition binary opportunity path and its v4 implementation agree over
the current saved panel; it does not prove that opportunities never occur
outside this panel. The Gate B source and arithmetic verification is current
through scan 84. Do not describe timestamp-qualified states as executable.

No public request, service change, active campaign read, or order was made for
this audit.
