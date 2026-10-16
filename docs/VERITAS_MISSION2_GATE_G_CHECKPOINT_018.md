# Gate G checkpoint 018 — project selection-support audit and freshness

**Captured:** 2026-10-16T08:01:55Z
**Mission status:** active; dashboard changes are verified in source and remain undeployed.

## Implemented

The read-only dashboard API now projects the independently audited selection-support results from coverage-design audit 002. It verifies the artifact file digest, canonical artifact digest, result digest, exact ledger receipt, analysis version, count reconciliation, role yields, bounded fractions, safety flags, and pilot source identity.

The projection compares the audited pilot scan count and summary digest against the current verified pilot. It reports whether the audit is current, rather than presenting an old audit as current. Artifact selection resolves the highest-numbered existing audit with a matching ledger receipt.

The pilot summary projection now includes both its canonical summary digest and file digest. The dashboard adds an “Independent inclusion-support audit” card with full, partial, and unsupported scan counts, pooled selection support, design-weighted yield and range, audited sample size, skipped sequences, limitations, and a verified artifact link.

## Current source projection

An in-process call to the actual repository overview returned the audit as available and stale: audit 002 covers 25 scans, while the live measurement pilot has advanced to 26 scans. The UI therefore labels it “Audited 25 scans · pilot now at 26.” It continues to report the audit’s 99.80% pooled support and 82.96% weighted yield with their conditional interpretation.

The latest public observatory summary is scan 57, with 1,945 quality-valid pairs from 2,280 selected observations and zero positive top-gross pairs. A1 market coverage and independent opportunity audit 009 remain through scan 55; no extension is claimed here.

## Verification

- Focused dashboard API and coverage-design audit tests: **33 passed**; one existing Starlette TestClient deprecation warning.
- Focused Veritas frontend test: **1 passed**.
- TypeScript typecheck, ESLint, and Prettier checks: passed.
- The prior focused production build passed with the existing Vite large-chunk advisory.
- The H125 audit and its source artifacts remain digest-verified.
- Ledger receipt: H126.
- No authenticated requests, public requests, orders, campaign changes, or service restarts were made for this checkpoint.

## Limits and remaining work

These changes are source-only, uncommitted, and undeployed. The focused UI test verifies rendering and the evidence link; a browser workflow against the updated dashboard and the full Mission 2 regression remain open. The evidence is a measurement-support audit, not a market-wide coverage estimate or economic result.

See [coverage-design audit 002](VERITAS_MISSION2_COVERAGE_DESIGN_AUDIT_002.json), [Gate A checkpoint 052](VERITAS_MISSION2_GATE_A_CHECKPOINT_052.md), and [Gate H checkpoint 001](VERITAS_MISSION2_GATE_H_CHECKPOINT_001.md).
