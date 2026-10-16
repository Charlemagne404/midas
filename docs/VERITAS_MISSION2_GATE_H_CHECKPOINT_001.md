# Gate H checkpoint 001 — isolated Veritas browser workflow

**Captured:** 2026-10-16 03:37 UTC
**Mission status:** active; this is one focused Gate H verification.

The Veritas Playwright workflow now checks the new frozen campaign gap-
attribution card, its direct artifact link, and the full API artifact route.
The workflow asserts schema version, the 339 gap-labeled outcomes in saved
artifact 001, and the explicit `same_market_preceding_gap_is_causal_proof =
false` limitation.

`npm run test:e2e -- e2e/veritas.spec.ts` passed **1 test** in 5.4 seconds.
Playwright started its isolated API and Vite servers on ports 18000 and 15173
with a temporary SQLite database, then exited successfully. The browser
workflow did not reuse those ports before the run; both ports were free after
it completed. The Reality recorder, shadow, hosted APIs, collector, scheduled
research jobs, and pilot were not restarted or changed.

This verifies the source checkout and local read-only artifact route. It does
not verify the hosted dashboard deployment. Gate H remains open: the full
backend and browser regression suites, cross-gate preservation audit, scheduler
recovery/idempotence checks, and complete scientific validation have not been
run in this checkpoint. No full suite or model training was started.
