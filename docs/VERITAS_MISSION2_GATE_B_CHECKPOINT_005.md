# Gate B checkpoint 005 — reported book timestamp/content association

**Captured:** 2026-10-16T05:01:27Z
**Experiment:** `VERITAS-M2-REPORTED-BOOK-TIMESTAMP-001`
**Mission status:** active; freshness semantics remain unresolved.

The bounded offline analysis verified 51 finalized snapshots / 33,318,338
compressed bytes and parsed 4,080 retained CLOB book observations over 1,806
outcome asset IDs. It compared consecutive saved responses for the same asset,
using a canonical full-book content digest that excludes the reported
`timestamp` and response `hash` fields.

| Consecutive endpoint relation | Count |
| --- | ---: |
| Content changed; reported timestamp advanced | 2,197 |
| Content unchanged; reported timestamp advanced | 37 |
| Content unchanged; reported timestamp stayed the same | 40 |
| Content changed with unchanged or regressed timestamp | 0 |
| Reported timestamp regressed | 0 |

There were 2,274 repeated-asset transitions. In 1,848 later endpoints the
reported age exceeded five seconds: 1,771 had different book content from the
prior saved endpoint and 77 had identical endpoint content. The age bands were
150 at 0–1 second, 276 at 1–5 seconds, 630 at 5–30 seconds, 964 at 30 seconds–5
minutes, and 254 over 5 minutes. The median interval between saved receipts for
repeated assets was 3,615,798.559 ms; these are sparse endpoint comparisons.

Within this panel, every observed content change coincided with an advancing
reported timestamp. Timestamp advancement also occurred when the later book
content was identical to the earlier endpoint. Intermediate updates,
reversions, and server refresh behavior are not retained by this sample. The
result supports timestamp/content association, but does not establish the
field's venue-side semantics, source sequencing, atomicity, continuous quote
freshness, queue age, order arrival, or fills. An age over five seconds is not
classified as proof that a book was stale. Keep the existing reported-age
calculation as a conservative sensitivity and seek documented semantics or an
independent sequence signal before changing freshness qualification.

Artifact and provenance:

- [Reported book timestamp audit 001](VERITAS_MISSION2_REPORTED_BOOK_TIMESTAMP_AUDIT_001.json)
- Artifact file SHA-256: `98b95bb563078349dfd8f6272cecd3c0d4738fc7016b7b1fa2ac32ac7a8f5c8d`
- Result SHA-256: `aed483fda621f79221d8095a4d14c8d674b61eb3dadf4726388e03f311d85263`
- Source dataset SHA-256: `4d2825f44f40d81fffe3434078356b3759001a2973b4b0853f27b9193b1b9b92`
- Research ledger: H112.

The four focused tests passed; Ruff, formatting, strict Mypy, result-digest
verification, and `git diff --check` passed. No full suite was run. The audit
used saved local snapshots only, made no public or authenticated requests, and
submitted no orders. This experiment evaluated timestamp behavior only; it did
not recompute economic gates or establish new arbitrage candidates.
