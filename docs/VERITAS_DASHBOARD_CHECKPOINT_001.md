# Veritas native dashboard checkpoint 001

**Date:** 2026-10-15

**Branch:** `project/veritas`
**Scope:** read-only evidence presentation; no Reality campaign or runtime changes

## Result

The MIDAS web application now has a native Veritas workspace at **Veritas** in
the primary navigation. The dashboard summarizes the versioned Gate A baseline
and raw opportunity funnel, follow-up yield and censor reasons, Gate B synthetic
execution sensitivities, hypothesis status, and links to the source artifacts.
Observed and derived quantities have separate labels. Synthetic results are
marked as assumptions, while fills and profitability remain unknown.

At this snapshot the measured selected panel contains 29,932 quality-valid
states across 15 markets and 6 connected families. It has no positive
top-ask, quantity-depth, or full-depth pre-fee pair. Public measurements at one
second were 27 of 381 valid initial states (7.1%); the remaining 354 valid
starts were censored, and 1,027 invalid starts are shown separately. These are
bounded panel statistics, not venue-wide rates or execution outcomes. The
100-share execution view is synthetic: its single-match full-depth result is
+1.4178 USDC, its fragmentation-safe fee bound is -0.7822 USDC, and the adverse
unmatched-leg loss is 50.1959 USDC. None of those values estimates fill
likelihood. At half displayed depth, the single-match pair result is -1.0270
USDC.

## Interface contract

- `GET /api/veritas/overview` reads five allowlisted versioned JSON artifacts
  and returns a normalized dashboard summary. It does not include raw market
  records or repository paths.
- `GET /api/veritas/artifacts/{identity}` returns one allowlisted JSON artifact
  with its SHA256 digest. Supported identities are `baseline`, `raw-funnel`,
  `capacity`, `break-even`, `ledger`, and `inventory`.
- Artifact reads are limited to 512 KiB, reject symlinks and unknown identities,
  and only accept JSON objects. The overview omits source paths and raw market
  records; full artifact responses retain provenance fields present in the
  source JSON. The interface has no write or campaign-control routes.
- The web client refreshes the overview every 60 seconds. Artifact links open
  the bounded JSON response directly.

## Verification

- API endpoint tests: 3 passed, including follow-up cohort reconciliation.
- Web suite: 29 passed across 5 test files.
- Web lint and Prettier checks passed.
- Production web build passed. Veritas is lazy-loaded into a separate 10.46 KiB
  JavaScript chunk. Vite still warns that the existing main JavaScript chunk is
  501.84 KiB, just above its 500 KiB advisory threshold.
- Ruff passed for `apps/api/veritas.py`, `apps/api/main.py`, and the new API
  tests.
- No Reality service was restarted; the protected campaign and its source data
  were not modified; no orders were submitted.

## Files

- `apps/api/veritas.py`
- `apps/web/src/Veritas.tsx`
- `apps/web/src/veritas.css`
- `tests/test_veritas_dashboard_api.py`
- `apps/web/src/Veritas.test.tsx`
