# Gate G checkpoint 008 — per-size economic gates

**Captured:** 2026-10-15 22:21 UTC  
**Mission status:** active; this is a read-only display change.

## Implemented

The opportunity observatory displays recorded candidate events per elapsed
panel hour, with a visible caveat that observations are intermittent
snapshots rather than continuous coverage. A new table reports positive
paired-book states by requested shares per leg (5, 10, 20, 50, and 100) at
four cumulative economic gates: full-depth gross, after per-leg minimums,
after single-match fees, and after fragmentation-safe fees. The explanation
states that repeated market states are correlated observations and do not
represent independent opportunities or fills.

The candidate frequency is guarded when the panel has no elapsed time. The
table obtains its quantities and counts from the existing observatory API
projection; no API calculation, source artifact, collector, campaign, or
research protocol was changed.

## Evidence displayed from the latest observation artifact

The 37-snapshot panel contains 1,480 selected market observations and 1,307
quality-valid paired-book states. It records zero positive top-gross states
and zero positive states at all four displayed economic gates for every
quantity from 5 through 100 shares per leg. The recorded candidate count is
zero over the approximately 16-hour panel window, rendered as `0.000 events /
panel hour`. This rate describes intermittent survey observations; it does
not estimate continuous opportunity duration or executable fills.

## Verification

- `apps/web/src/Veritas.test.tsx`: **1 passed**, including the candidate-rate
  label and the 20-share row across the four economic gates.
- `corepack pnpm --dir apps/web typecheck`: passed.
- `corepack pnpm --dir apps/web format:check`: passed.
- `corepack pnpm --dir apps/web build`: passed. Vite repeated the existing
  advisory for the 544.41 kB Chart chunk (the main bundle is 501.86 kB).
- `corepack pnpm --dir apps/web exec playwright test e2e/veritas.spec.ts`:
  **1 passed** against isolated demo API and Vite servers. The temporary
  servers exited and their ports were free afterward.
- `git diff --check`: passed.

No production service was restarted. The display adds interpretability to
the zero-candidate result without changing its economic meaning. Gate G and
Mission 2 remain in progress.
